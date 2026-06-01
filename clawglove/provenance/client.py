"""
clawglove/provenance/client.py
================================
CPTClient — the public API surface for the CPT subsystem.

This replaces the stub in cgbench/layers/provenance.py.
After Phase 2 ships, update the import in provenance.py:

    # Remove stub classes and replace with:
    from clawglove.provenance.client import CPTClient
    from clawglove.provenance.exceptions import (
        SkillQuarantinedError,
        OrphanedPayloadError,
        IdentityHaltError,
    )

Phase 2 coverage  → write_skill(), load_skill(), write_core_path()
Phase 3 (pending) → get_envelope(), get_quarantine_log()
"""

from __future__ import annotations

import dataclasses
import datetime
import hashlib
import hmac
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .exceptions import (
    IdentityHaltError,
    OrphanedPayloadError,
    SkillQuarantinedError,
    TenantIsolationError,
    LedgerChainViolation,
)
from .ledger import ProvenanceLedger, EnvelopeNotFound
from .watchdog import (
    SIGNATURE_PREFIX,
    InterceptResult,
    SkillWatchdog,
    _hmac_sign,
    _now_iso,
    _sha256,
)


# ---------------------------------------------------------------------------
# Keyring Helpers
# ---------------------------------------------------------------------------

def _load_or_bootstrap_keyring(workspace_root: Path) -> dict[str, Any]:
    secrets_file = workspace_root / ".clawglove_secrets"
    secret_file = workspace_root / ".clawglove_secret"

    if secrets_file.exists():
        try:
            return json.loads(secrets_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Keyring does not exist, try single-key migration
    if secret_file.exists():
        try:
            old_secret = secret_file.read_text(encoding="utf-8").strip()
            derived_id = hashlib.sha256(bytes.fromhex(old_secret)).hexdigest()[:16]
            keyring = {
                "active_key_id": derived_id,
                "keys": {
                    "v1": old_secret,
                    derived_id: old_secret
                }
            }
            secrets_file.write_text(json.dumps(keyring, indent=2), encoding="utf-8")
            return keyring
        except Exception:
            pass

    # Fresh initialization
    new_secret_hex = os.urandom(32).hex()
    derived_id = hashlib.sha256(bytes.fromhex(new_secret_hex)).hexdigest()[:16]
    keyring = {
        "active_key_id": derived_id,
        "keys": {
            derived_id: new_secret_hex
        }
    }
    secrets_file.write_text(json.dumps(keyring, indent=2), encoding="utf-8")
    if not secret_file.exists():
        try:
            secret_file.write_text(new_secret_hex, encoding="utf-8")
        except Exception:
            pass

    return keyring


def verify_envelope_signature(envelope: ProvenanceEnvelope, key_hex: str) -> bool:
    sig_str = envelope.signature
    if sig_str.startswith("clawglove-"):
        sig_hex = sig_str[len("clawglove-"):]
    else:
        parts = sig_str.split(":")
        if len(parts) == 3 and parts[0] == "clawglove":
            sig_hex = parts[2]
        else:
            return False

    try:
        secret_bytes = bytes.fromhex(key_hex)
        expected = hmac.new(secret_bytes, envelope.content_hash.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, sig_hex)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Provenance Envelope (matches RFC-003 §2.2 schema)
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class ProvenanceEnvelope:
    skill_id: str
    file_path: str
    content_hash: str
    originating_session_id: str
    parent_user_request_hash: str
    generator_model: str
    generation_timestamp: str
    tenant_id: str
    signature: str
    auto_approved: bool = False
    quarantine_path: str | None = None
    key_id: str = "v1"
    node_id: str = "unknown"



# ---------------------------------------------------------------------------
# Write Request (public API input)
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class CPTWriteRequest:
    skill_id: str
    file_path: str
    content: bytes
    session_id: str
    parent_request_hash: str
    generator_model: str
    tenant_id: str


# ---------------------------------------------------------------------------
# CPTClient
# ---------------------------------------------------------------------------

class CPTClient:
    """
    Public API for the Context Provenance Tracking subsystem.

    Wraps ClawGloveClient to extract workspace root and per-tenant signing
    secrets.  (GAP-2 binding spec from RFC-003 §6.)

    If the base client does not expose .workspace_root, a temporary directory
    is used — appropriate for testing; operators must configure the real path.
    """

    @classmethod
    def from_workspace(cls, workspace_root: Path | str) -> CPTClient:
        """
        Construct a CPTClient directly from a workspace root path.
        Retrieves or generates a persistent keyring under Path(workspace_root) / ".clawglove_secrets".
        """
        workspace_path = Path(workspace_root)
        workspace_path.mkdir(parents=True, exist_ok=True)
        
        # Load/bootstrap keyring
        keyring = _load_or_bootstrap_keyring(workspace_path)
        active_key_id = keyring["active_key_id"]
        active_secret_hex = keyring["keys"][active_key_id]

        class WorkspaceBaseClient:
            def __init__(self, ws: Path, secret: str):
                self.workspace_root = ws
                self.cpt_signing_secret = secret

        return cls(WorkspaceBaseClient(workspace_path, active_secret_hex))

    def __init__(self, base_client: Any):
        self._base = base_client

        # Resolve workspace root from base client or fall back to temp dir.
        workspace_root = getattr(base_client, "workspace_root", None)
        if workspace_root is None:
            workspace_root = Path(tempfile.mkdtemp(prefix="clawglove_cpt_"))

        # Load/bootstrap keyring
        self._keyring = _load_or_bootstrap_keyring(workspace_root)

        # Resolve active secret from base client or dynamic keyring
        signing_secret_hex = getattr(base_client, "cpt_signing_secret", None)
        if signing_secret_hex:
            # Check if this specific key is in keyring, register it if not
            found_id = None
            for kid, kh in self._keyring["keys"].items():
                if kh == signing_secret_hex and kid != "v1":
                    found_id = kid
                    break
            if found_id is None:
                derived_id = hashlib.sha256(bytes.fromhex(signing_secret_hex)).hexdigest()[:16]
                self._keyring["keys"][derived_id] = signing_secret_hex
                # If it's the legacy key, keep "v1" registered too for pre-existing rows
                sec_file = Path(workspace_root) / ".clawglove_secret"
                if sec_file.exists() and sec_file.read_text(encoding="utf-8").strip() == signing_secret_hex:
                    self._keyring["keys"]["v1"] = signing_secret_hex
                # Save keyring updates
                secrets_file = Path(workspace_root) / ".clawglove_secrets"
                secrets_file.write_text(json.dumps(self._keyring, indent=2), encoding="utf-8")
                found_id = derived_id
            
            self._active_key_id = found_id
            signing_secret = bytes.fromhex(signing_secret_hex)
        else:
            self._active_key_id = self._keyring["active_key_id"]
            if self._active_key_id == "v1":
                secret_hex = self._keyring["keys"]["v1"]
                derived_id = hashlib.sha256(bytes.fromhex(secret_hex)).hexdigest()[:16]
                self._keyring["keys"][derived_id] = secret_hex
                self._keyring["active_key_id"] = derived_id
                secrets_file = Path(workspace_root) / ".clawglove_secrets"
                secrets_file.write_text(json.dumps(self._keyring, indent=2), encoding="utf-8")
                self._active_key_id = derived_id
            
            signing_secret = bytes.fromhex(self._keyring["keys"][self._active_key_id])

        # Extract protected path overrides from config.
        extra_protected = getattr(base_client, "cpt_protected_paths", None)

        self._watchdog = SkillWatchdog(
            workspace_root=workspace_root,
            signing_secret=signing_secret,
            protected_paths=extra_protected,
        )

        # Phase 3: durable ledger.
        db_path = Path(workspace_root) / "provenance_ledger.db"
        self._ledger = ProvenanceLedger(db_path)

    # ------------------------------------------------------------------
    # write_skill — primary interception point
    # ------------------------------------------------------------------

    def write_skill(self, req: CPTWriteRequest) -> ProvenanceEnvelope:
        """
        Gate a skill write through the CPT pipeline.

        Returns a ProvenanceEnvelope on success (auto_approved=True) or
        raises SkillQuarantinedError if the content is blocked.

        All other CPT exceptions (OrphanedPayloadError, IdentityHaltError,
        InterceptTimeoutError) propagate directly to the caller.
        """
        try:
            result: InterceptResult = self._watchdog.intercept_write(
                skill_id=req.skill_id,
                file_path=req.file_path,
                content=req.content,
                session_id=req.session_id,
                parent_request_hash=req.parent_request_hash,
                generator_model=req.generator_model,
                tenant_id=req.tenant_id,
            )
        except SkillQuarantinedError as exc:
            # Construct a ProvenanceEnvelope with auto_approved=False
            content_hash = _sha256(req.content)
            signature = _hmac_sign(content_hash, self._watchdog._secret)
            envelope = ProvenanceEnvelope(
                skill_id=req.skill_id,
                file_path=exc.quarantine_path or req.file_path,
                content_hash=content_hash,
                originating_session_id=req.session_id,
                parent_user_request_hash=req.parent_request_hash,
                generator_model=req.generator_model,
                generation_timestamp=_now_iso(),
                tenant_id=req.tenant_id,
                signature=signature,
                auto_approved=False,
                quarantine_path=exc.quarantine_path,
                key_id=self._active_key_id,
                node_id=self._ledger.node_id,
            )
            # Atomically write both in a single SQLite transaction
            self._ledger.write_quarantine_with_envelope(
                envelope=envelope,
                risky_imports=exc.risky_imports,
                timestamp=envelope.generation_timestamp,
            )
            raise exc

        # Build and persist the provenance envelope on success path.
        envelope = self._build_envelope(req, result)
        self._ledger.write_envelope(envelope)
        return envelope

    # ------------------------------------------------------------------
    # load_skill
    # ------------------------------------------------------------------

    def load_skill(self, skill_id: str, tenant_id: str) -> bytes:
        """
        Load a skill from the active set.

        Raises:
            FileNotFoundError      — skill not approved / not found
            SkillQuarantinedError  — skill is quarantined
            TenantIsolationError   — cross-tenant access attempt
        """
        return self._watchdog.load_from_active(skill_id, tenant_id)

    # ------------------------------------------------------------------
    # write_core_path — Identity Continuity Boundary (T-009)
    # ------------------------------------------------------------------

    def write_core_path(self, path: str, content: bytes, session_id: str) -> None:
        """
        Attempt to write to a path.  If the path is protected, raises
        IdentityHaltError immediately — this is a Hard System Halt.

        Legitimate (non-protected) paths are written through the watchdog
        pipeline so they are still subject to import analysis.
        """
        if self._watchdog._protected.is_protected(path):
            raise IdentityHaltError(
                protected_path=path,
                detected_hash_delta=_sha256(content),
                session_id=session_id,
            )
        # Non-protected path: treat as a regular skill write with minimal
        # lineage — the caller is responsible for providing context.
        # (Out of scope for T-009 testing; no-op here.)

    # ------------------------------------------------------------------
    # get_envelope — Phase 3 (durable ledger)
    # ------------------------------------------------------------------

    def get_envelope(self, skill_id: str, tenant_id: str) -> ProvenanceEnvelope:
        """Retrieve the most recent provenance envelope. Phase 3: durable ledger."""
        try:
            row = self._ledger.get_envelope(skill_id, tenant_id)
        except EnvelopeNotFound:
            raise KeyError(f"No envelope for skill '{skill_id}' in tenant '{tenant_id}'.")
        return ProvenanceEnvelope(
            skill_id=row.skill_id, file_path=row.file_path,
            content_hash=row.content_hash,
            originating_session_id=row.originating_session_id,
            parent_user_request_hash=row.parent_user_request_hash,
            generator_model=row.generator_model,
            generation_timestamp=row.generation_timestamp,
            tenant_id=row.tenant_id, signature=row.signature,
            auto_approved=row.auto_approved, quarantine_path=row.quarantine_path,
            key_id=row.key_id, node_id=row.node_id,
        )

    # ------------------------------------------------------------------
    # get_quarantine_log
    # ------------------------------------------------------------------

    def get_quarantine_log(self, tenant_id: str) -> list[dict]:
        """
        Return all quarantine events for a tenant.
        Phase 3: durable SQLite ledger as canonical audit trail.
        """
        rows = self._ledger.get_quarantine_log(tenant_id)
        return [{"skill_id":r.skill_id,"tenant_id":r.tenant_id,"session_id":r.session_id,
                 "quarantine_path":r.quarantine_path,"content_hash":r.content_hash,
                 "risky_imports":r.risky_imports,"timestamp":r.timestamp,
                 "chain_hash":r.chain_hash, "node_id":r.node_id} for r in rows]

    def reconcile_quarantine(self, tenant_id: str) -> dict[str, Any]:
        """
        Reconcile the physical quarantine files against the ledger database.

        Assurance Contract (Design Refinement 4):
          - Untracked File on Disk (possible crash before DB write) -> Prune silently
            to prevent unapproved out-of-band accumulation.
          - Registered File Missing from Disk (possible exfiltration/tampering) ->
            Raise LedgerChainViolation (fail-closed signal).
          - Registered File Tampered (content hash mismatch) -> Raise LedgerChainViolation
            (fail-closed signal).
        """
        rows = self._ledger.get_quarantine_log(tenant_id)
        registered_paths = set()

        for row in rows:
            q_path = Path(row.quarantine_path).resolve()
            if not q_path.exists():
                raise LedgerChainViolation(
                    table="quarantine_log",
                    row_id=row.id,
                    expected="file_exists",
                    actual="file_missing",
                )

            # Check file hash match (tampering detection)
            try:
                content = q_path.read_bytes()
                computed_hash = hashlib.sha256(content).hexdigest()
            except Exception as e:
                raise LedgerChainViolation(
                    table="quarantine_log",
                    row_id=row.id,
                    expected=row.content_hash,
                    actual=f"read_failed: {e}",
                )

            if computed_hash != row.content_hash:
                raise LedgerChainViolation(
                    table="quarantine_log",
                    row_id=row.id,
                    expected=row.content_hash,
                    actual=computed_hash,
                )

            registered_paths.add(q_path)

            # Keep the meta.json sibling path
            meta_path = q_path.parent / f"{row.skill_id}.meta.json"
            if meta_path.exists():
                registered_paths.add(meta_path.resolve())

        # Walk physical quarantine directory and silently prune unregistered/untracked files
        tenant_q_dir = (self._watchdog._quarantine._root / tenant_id).resolve()
        pruned_files = []
        if tenant_q_dir.exists():
            for p in tenant_q_dir.rglob("*"):
                if p.is_file():
                    resolved_p = p.resolve()
                    if resolved_p not in registered_paths:
                        try:
                            p.unlink()
                            pruned_files.append(str(resolved_p))
                        except Exception:
                            pass

            # Clean up empty subdirectories
            for root, dirs, files in os.walk(str(tenant_q_dir), topdown=False):
                for name in dirs:
                    dir_path = Path(root) / name
                    try:
                        if not any(dir_path.iterdir()):
                            dir_path.rmdir()
                    except Exception:
                        pass

        return {
            "verified_count": len(rows),
            "pruned_files": pruned_files,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_envelope(
        self, req: CPTWriteRequest, result: InterceptResult
    ) -> ProvenanceEnvelope:
        content_hash = result.content_hash
        signature = _hmac_sign(content_hash, self._watchdog._secret)
        return ProvenanceEnvelope(
            skill_id=req.skill_id,
            file_path=result.file_path,
            content_hash=content_hash,
            originating_session_id=req.session_id,
            parent_user_request_hash=req.parent_request_hash,
            generator_model=req.generator_model,
            generation_timestamp=_now_iso(),
            tenant_id=req.tenant_id,
            signature=signature,
            auto_approved=result.auto_approved,
            quarantine_path=result.quarantine_path,
            key_id=self._active_key_id,
            node_id=self._ledger.node_id,
        )
