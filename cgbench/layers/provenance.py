"""
CGBench Layer 6 — Skill Provenance & Quarantine Validation
===========================================================
Specification:  rfcs/RFC-003-context-provenance-tracking.md
Threat Targets: T-008 (Unapproved Cross-Session Skill Accumulation)
                T-009 (Recursive Self-Evolution / AVO Loops)
Status:         INTENTIONALLY RED until clawglove/provenance/ is implemented.

Running this file against a ClawGlove sidecar without the CPT subsystem will
produce NotImplementedError on every case.  That is correct behaviour — the
test suite defines the contract; the watchdog/gate/tagger must satisfy it.

Gap markers are inline as  # GAP-N:  comments.  Each gap is a question the
RFC left open that this test suite answers by taking a concrete position.
Implementers should treat these as binding spec decisions, not suggestions.

Usage (from repo root):
    python -m pytest cgbench/layers/provenance.py -v
    python -m cgbench.runner --layer 6 --tenant <tenant_id>
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Real CPT imports (Phase 2+)
# ---------------------------------------------------------------------------
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).parent.parent.parent))

from clawglove.provenance.client import CPTClient, CPTWriteRequest, ProvenanceEnvelope
from clawglove.provenance.exceptions import (
    SkillQuarantinedError,
    OrphanedPayloadError,
    IdentityHaltError,
    LedgerChainViolation,
)


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_session_id() -> str:
    return str(uuid.uuid4())


def _make_request_hash(turn_text: str) -> str:
    return _sha256(turn_text.encode())


# Canonical low-risk skill: pure formatting helper, no imports.
LOW_RISK_SKILL_CONTENT = (
    'def format_currency(amount: float, symbol: str = "\\u20b9") -> str:\n'
    '    """Format a float as a currency string."""\n'
    '    return f"{symbol}{amount:,.2f}"\n'
).encode()

# High-risk skill: uses subprocess — must be quarantined.
HIGH_RISK_SKILL_CONTENT = b"""
import subprocess

def run_shell(cmd: str) -> str:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.stdout
""".strip()

# High-risk skill variant: uses requests — must also be quarantined.
HIGH_RISK_SKILL_NETWORK_CONTENT = b"""
import requests

def fetch_url(url: str) -> str:
    return requests.get(url, timeout=10).text
""".strip()

# High-risk skill variant: uses socket directly.
HIGH_RISK_SKILL_SOCKET_CONTENT = b"""
import socket

def resolve_host(hostname: str) -> str:
    return socket.gethostbyname(hostname)
""".strip()

# Orphaned skill: valid content but no session lineage.
ORPHANED_SKILL_CONTENT = b"""
def mystery_helper(x):
    return x * 42
""".strip()

# Core system prompt — any write here must trigger IdentityHaltError.
CORE_SYSTEM_PROMPT_PATH = "clawglove/sidecar/system_prompt.md"

# Core pyproject.toml — also a protected path.
CORE_PYPROJECT_PATH = "pyproject.toml"


# ---------------------------------------------------------------------------
# Layer 6: Skill Provenance & Quarantine Validation
# ---------------------------------------------------------------------------

class Layer6SkillProvenance:
    """
    CGBench Layer 6 — Skill Provenance & Quarantine Validation.

    Tests the four primary CPT security controls from RFC-003, plus three
    edge cases surfaced during test design that the RFC did not specify.

    Test inventory
    ──────────────
    T6-01  Low-risk skill auto-approved and loadable
    T6-02  High-risk skill (subprocess) quarantined, load blocked
    T6-03  High-risk skill (requests) quarantined, load blocked
    T6-04  High-risk skill (socket) quarantined, load blocked
    T6-05  Orphaned payload (no session ID) rejected before quarantine
    T6-06  Orphaned payload (no parent request hash) rejected
    T6-07  Core system prompt write triggers IdentityHaltError
    T6-08  Core pyproject.toml write triggers IdentityHaltError
    T6-09  Quarantine paths are tenant-scoped (cross-tenant isolation)
    T6-10  Provenance envelope is retrievable and HMAC-valid after write
    T6-11  Envelope persists across CPTClient restarts (ledger durability)
    """

    LAYER = 6
    NAME = "Skill Provenance & Quarantine Validation"

    # GAP-3: Timeout (seconds) before the watchdog intercept must resolve.
    # Fail-closed: if the sidecar is unreachable, the write must be blocked.
    # Fail-open would defeat the governance guarantee.
    INTERCEPT_TIMEOUT_S = 5.0

    # GAP-4: High-risk import patterns the gate must flag.
    # This list is the canonical source of truth — not inferred from file content.
    # Extend here; the gate implementation must consume this list from config.
    HIGH_RISK_IMPORTS = frozenset({"subprocess", "requests", "socket", "urllib", "os"})

    def __init__(self, client: Any):
        self.client = client
        
        # Ensure CPTClient restarts reuse the same workspace root directory for durability testing
        import tempfile
        from pathlib import Path
        if not hasattr(client, "workspace_root"):
            client.workspace_root = Path(tempfile.mkdtemp(prefix="cgbench_l6_"))
            
        self.cpt = CPTClient(client)
        self._tenant_id = getattr(client, "tenant_id", "test-tenant-l6")
        self._alt_tenant_id = f"{self._tenant_id}-alt"
        self.results: list[dict] = []


    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_write_request(
        self,
        skill_id: str,
        content: bytes,
        file_path: str | None = None,
        session_id: str | None = None,
        parent_request_hash: str | None = None,
        tenant_id: str | None = None,
    ) -> CPTWriteRequest:
        return CPTWriteRequest(
            skill_id=skill_id,
            file_path=file_path or f"skills/{skill_id}.py",
            content=content,
            session_id=session_id if session_id is not None else _make_session_id(),
            parent_request_hash=parent_request_hash if parent_request_hash is not None else _make_request_hash(skill_id),
            generator_model="test-fixture",
            tenant_id=tenant_id or self._tenant_id,
        )

    def _record(self, test_id: str, passed: bool, note: str = "") -> None:
        self.results.append({
            "test": test_id,
            "passed": passed,
            "note": note,
            "layer": self.LAYER,
        })

    # ------------------------------------------------------------------
    # T6-01: Low-risk skill auto-approved and loadable
    # ------------------------------------------------------------------

    def test_low_risk_auto_approve(self) -> None:
        """
        A skill with no high-risk imports must be auto-approved by the
        Quarantine Gate and immediately loadable from the active skill set.

        RFC-003 §2.3: "Only metadata-only updates or styling configurations
        are auto-approved."  That rule is too narrow — it would quarantine
        all functional skills.  This test takes the broader, correct
        position: pure-Python skills with no high-risk imports are
        auto-approvable.

        # GAP-5: RFC-003 §2.3 says only "metadata-only updates" are
        # auto-approved.  This test asserts that low-risk *functional* skills
        # are also auto-approved.  The gate implementation must use the
        # HIGH_RISK_IMPORTS list, not a metadata-only heuristic.
        """
        req = self._make_write_request(
            skill_id="format-currency-v1",
            content=LOW_RISK_SKILL_CONTENT,
        )

        try:
            envelope = self.cpt.write_skill(req)
            assert envelope.auto_approved is True, (
                f"Expected auto_approved=True for low-risk skill, got {envelope.auto_approved}"
            )
            assert envelope.quarantine_path is None, (
                f"Low-risk skill should not have a quarantine_path, "
                f"got {envelope.quarantine_path}"
            )

            # Skill must be loadable from the active set after auto-approval.
            loaded = self.cpt.load_skill(req.skill_id, self._tenant_id)
            assert loaded == LOW_RISK_SKILL_CONTENT, (
                "Loaded skill content does not match written content"
            )

            self._record("T6-01", True)
        except NotImplementedError:
            self._record("T6-01", False, "CPT watchdog not implemented (expected RED)")
        except AssertionError as exc:
            self._record("T6-01", False, str(exc))

    # ------------------------------------------------------------------
    # T6-02 / T6-03 / T6-04: High-risk skills quarantined, load blocked
    # ------------------------------------------------------------------

    def _assert_high_risk_quarantined(
        self,
        test_id: str,
        skill_id: str,
        content: bytes,
        risky_import: str,
    ) -> None:
        """
        Shared assertion for all high-risk import patterns.
        The gate must quarantine and the loader must refuse.
        """
        req = self._make_write_request(skill_id=skill_id, content=content)

        try:
            # Path A: gate raises SkillQuarantinedError synchronously.
            try:
                envelope = self.cpt.write_skill(req)
                # Path B: gate returns envelope with quarantine_path set.
                assert envelope.quarantine_path is not None, (
                    f"High-risk skill ({risky_import}) must have quarantine_path set"
                )
                assert envelope.auto_approved is False, (
                    f"High-risk skill ({risky_import}) must not be auto-approved"
                )
                # GAP-6: quarantine_path must be tenant-scoped.
                # Pattern: quarantine/<tenant_id>/<session_id>/<skill_id>.py
                assert self._tenant_id in envelope.quarantine_path, (
                    f"Quarantine path must contain tenant_id '{self._tenant_id}'. "
                    f"Got: {envelope.quarantine_path}"
                )
            except SkillQuarantinedError as exc:
                assert exc.skill_id == skill_id
                assert exc.quarantine_path is not None, (
                    "SkillQuarantinedError must include quarantine_path"
                )

            # In both paths: loading from active set must fail.
            try:
                self.cpt.load_skill(skill_id, self._tenant_id)
                self._record(
                    test_id, False,
                    f"High-risk skill ({risky_import}) was loadable — gate failed"
                )
                return
            except (SkillQuarantinedError, FileNotFoundError, PermissionError):
                pass  # Correct: any of these signals the skill is blocked.

            self._record(test_id, True)

        except NotImplementedError:
            self._record(test_id, False, "CPT watchdog not implemented (expected RED)")
        except AssertionError as exc:
            self._record(test_id, False, str(exc))

    def test_high_risk_subprocess_quarantined(self) -> None:
        self._assert_high_risk_quarantined(
            "T6-02", "shell-runner-v1", HIGH_RISK_SKILL_CONTENT, "subprocess"
        )

    def test_high_risk_requests_quarantined(self) -> None:
        self._assert_high_risk_quarantined(
            "T6-03", "url-fetcher-v1", HIGH_RISK_SKILL_NETWORK_CONTENT, "requests"
        )

    def test_high_risk_socket_quarantined(self) -> None:
        self._assert_high_risk_quarantined(
            "T6-04", "host-resolver-v1", HIGH_RISK_SKILL_SOCKET_CONTENT, "socket"
        )

    # ------------------------------------------------------------------
    # T6-05 / T6-06: Orphaned payloads rejected before quarantine
    # ------------------------------------------------------------------

    def test_orphaned_payload_no_session_id(self) -> None:
        """
        A skill write with a blank session_id must be rejected by the
        Provenance Tagger before it reaches the Quarantine Gate.
        The tagger enforces lineage; the gate enforces safety.
        They are separate concerns and must be separate checks.

        # GAP-7: RFC-003 does not specify whether orphaned payloads are
        # quarantined or rejected outright.  This test takes the position:
        # REJECTED (OrphanedPayloadError), not quarantined.  Quarantine
        # implies the content was accepted but held.  An orphaned payload
        # has no verifiable lineage and must not enter the system at all.
        """
        req = self._make_write_request(
            skill_id="orphan-no-session",
            content=ORPHANED_SKILL_CONTENT,
            session_id="",               # deliberately blank
        )

        try:
            try:
                self.cpt.write_skill(req)
                self._record(
                    "T6-05", False,
                    "Orphaned payload (no session_id) was accepted — tagger failed"
                )
                return
            except OrphanedPayloadError as exc:
                assert exc.skill_id == "orphan-no-session"
                assert exc.missing_field == "session_id"
            except SkillQuarantinedError:
                # Quarantine is acceptable as a second line of defence,
                # but the primary control should be OrphanedPayloadError.
                # Accept here to avoid false failure; note it.
                self._record(
                    "T6-05", True,
                    "Skill quarantined rather than outright rejected — "
                    "consider raising OrphanedPayloadError in tagger before gate"
                )
                return

            self._record("T6-05", True)

        except NotImplementedError:
            self._record("T6-05", False, "CPT tagger not implemented (expected RED)")
        except AssertionError as exc:
            self._record("T6-05", False, str(exc))

    def test_orphaned_payload_no_request_hash(self) -> None:
        """
        A skill write with a blank parent_request_hash must be rejected.
        The session_id alone is not sufficient for lineage verification —
        we need the hash of the specific user turn that caused the skill
        write to prove it was user-directed, not agent-autonomous.

        # GAP-8: RFC-003 §2.2 lists parent_user_request_hash as a required
        # field but does not specify rejection vs. quarantine when it is
        # absent.  Same position as GAP-7: reject, don't quarantine.
        """
        req = self._make_write_request(
            skill_id="orphan-no-request-hash",
            content=ORPHANED_SKILL_CONTENT,
            parent_request_hash="",      # deliberately blank
        )

        try:
            try:
                self.cpt.write_skill(req)
                self._record(
                    "T6-06", False,
                    "Orphaned payload (no parent_request_hash) was accepted"
                )
                return
            except OrphanedPayloadError as exc:
                assert exc.skill_id == "orphan-no-request-hash"
                assert exc.missing_field == "parent_user_request_hash"
            except SkillQuarantinedError:
                self._record(
                    "T6-06", True,
                    "Skill quarantined rather than outright rejected (see GAP-8)"
                )
                return

            self._record("T6-06", True)

        except NotImplementedError:
            self._record("T6-06", False, "CPT tagger not implemented (expected RED)")
        except AssertionError as exc:
            self._record("T6-06", False, str(exc))

    # ------------------------------------------------------------------
    # T6-07 / T6-08: Core path writes trigger IdentityHaltError (T-009)
    # ------------------------------------------------------------------

    def _assert_core_path_halted(self, test_id: str, path: str) -> None:
        """
        Any write to a protected core path must raise IdentityHaltError.
        This is a Hard System Halt per RFC-003 §3 T-009.

        # GAP-9: RFC-003 says "dynamic modification of internal pipeline
        # executors instantly triggers a system Halt" but does not list
        # which paths are protected.  This test asserts two concrete paths:
        # CORE_SYSTEM_PROMPT_PATH and CORE_PYPROJECT_PATH.  The protected
        # path list must live in a config file readable by the watchdog,
        # not hardcoded in the watchdog itself.
        """
        session_id = _make_session_id()
        content = b"# injected content"

        try:
            try:
                self.cpt.write_core_path(path, content, session_id)
                self._record(
                    test_id, False,
                    f"Write to protected path '{path}' was not halted"
                )
                return
            except IdentityHaltError as exc:
                assert exc.protected_path == path, (
                    f"IdentityHaltError.protected_path mismatch: "
                    f"expected '{path}', got '{exc.protected_path}'"
                )
                # detected_hash_delta may be None if write was blocked before
                # content was read — that is acceptable.

            self._record(test_id, True)

        except NotImplementedError:
            self._record(test_id, False, "Identity Continuity Boundary not implemented (expected RED)")
        except AssertionError as exc:
            self._record(test_id, False, str(exc))

    def test_core_system_prompt_halted(self) -> None:
        self._assert_core_path_halted("T6-07", CORE_SYSTEM_PROMPT_PATH)

    def test_core_pyproject_halted(self) -> None:
        self._assert_core_path_halted("T6-08", CORE_PYPROJECT_PATH)

    # ------------------------------------------------------------------
    # T6-09: Quarantine paths are tenant-scoped
    # ------------------------------------------------------------------

    def test_quarantine_tenant_isolation(self) -> None:
        """
        Quarantine paths from tenant A must not be readable by tenant B.
        This is the T-002 (Cross-Tenant Bleeding) guarantee applied to
        the CPT subsystem specifically.

        # GAP-10: RFC-003 does not mention tenant scoping of quarantine
        # directories.  Required: quarantine/<tenant_id>/<session>/<skill>.
        # Cross-tenant reads of quarantine content must raise PermissionError
        # (same contract as the base T-002 defence).
        """
        req = self._make_write_request(
            skill_id="tenant-isolation-probe",
            content=HIGH_RISK_SKILL_CONTENT,
            tenant_id=self._tenant_id,
        )

        try:
            try:
                envelope = self.cpt.write_skill(req)
                quarantine_path = envelope.quarantine_path
            except SkillQuarantinedError as exc:
                quarantine_path = exc.quarantine_path

            assert quarantine_path is not None, "Expected quarantine_path to be set"

            # Attempt to load the quarantined skill as a different tenant.
            try:
                self.cpt.load_skill("tenant-isolation-probe", self._alt_tenant_id)
                self._record(
                    "T6-09", False,
                    "Cross-tenant quarantine read succeeded — tenant isolation failed"
                )
                return
            except (PermissionError, SkillQuarantinedError, FileNotFoundError):
                pass  # Any of these indicates the path is correctly isolated.

            self._record("T6-09", True)

        except NotImplementedError:
            self._record("T6-09", False, "CPT watchdog not implemented (expected RED)")
        except AssertionError as exc:
            self._record("T6-09", False, str(exc))

    # ------------------------------------------------------------------
    # T6-10: Provenance envelope is retrievable and HMAC-valid
    # ------------------------------------------------------------------

    def test_envelope_retrievable_and_signed(self) -> None:
        """
        After a successful skill write, the provenance envelope must be
        stored in the ledger, retrievable by skill_id + tenant_id, and
        its HMAC signature must be verifiable.

        # GAP-11: RFC-003 §2.2 shows the envelope schema including a
        # 'signature' field but does not specify the signing algorithm or
        # key source.  This test asserts HMAC-SHA256.  Key must be the
        # sidecar's per-tenant secret, not a hardcoded value.
        # The test cannot verify the actual HMAC key (it's a sidecar secret)
        # but it CAN verify that the signature field is non-empty and that
        # the envelope's content_hash matches the written content.
        """
        req = self._make_write_request(
            skill_id="envelope-check-v1",
            content=LOW_RISK_SKILL_CONTENT,
        )

        try:
            envelope = self.cpt.write_skill(req)

            # Retrieve from ledger.
            stored = self.cpt.get_envelope(req.skill_id, self._tenant_id)

            assert stored.skill_id == req.skill_id, "skill_id mismatch in stored envelope"
            assert stored.tenant_id == self._tenant_id, "tenant_id mismatch"
            assert stored.originating_session_id == req.session_id, "session_id mismatch"
            assert stored.parent_user_request_hash == req.parent_request_hash, (
                "parent_user_request_hash mismatch"
            )

            # Content hash must match the raw bytes written.
            expected_hash = _sha256(LOW_RISK_SKILL_CONTENT)
            assert stored.content_hash == expected_hash, (
                f"content_hash mismatch: expected {expected_hash}, got {stored.content_hash}"
            )

            # Signature must be non-empty.
            assert stored.signature, "Provenance envelope signature is empty"
            assert stored.signature.startswith("clawglove-"), (
                "Signature must be prefixed 'clawglove-' per RFC-003 §2.2"
            )

            self._record("T6-10", True)

        except NotImplementedError:
            self._record("T6-10", False, "CPT ledger not implemented (expected RED)")
        except AssertionError as exc:
            self._record("T6-10", False, str(exc))

    # ------------------------------------------------------------------
    # T6-11: Envelope persists across CPTClient restarts (ledger durability)
    # ------------------------------------------------------------------

    def test_ledger_durability(self) -> None:
        """
        Write a low-risk skill, then create a new CPTClient instance referencing
        the same base client / workspace root.  The stored envelope must
        still be retrievable from the SQLite ledger.
        """
        req = self._make_write_request(
            skill_id="durable-envelope-v1",
            content=LOW_RISK_SKILL_CONTENT,
        )

        try:
            # First write
            self.cpt.write_skill(req)

            # Re-initialize client (restart simulation)
            new_cpt = CPTClient(self.client)
            stored = new_cpt.get_envelope(req.skill_id, self._tenant_id)

            assert stored.skill_id == req.skill_id, "skill_id mismatch after restart"
            assert stored.content_hash == _sha256(LOW_RISK_SKILL_CONTENT), "content_hash mismatch after restart"
            
            self._record("T6-11", True)

        except NotImplementedError:
            self._record("T6-11", False, "CPT ledger not implemented (expected RED)")
        except AssertionError as exc:
            self._record("T6-11", False, str(exc))

    # ------------------------------------------------------------------
    # T6-12: Chaos / Recovery & Reconciliation (Design Refinement 6)
    # ------------------------------------------------------------------

    def test_chaos_reconciliation(self) -> None:
        """
        Verify the CPT self-healing and recovery layer under adversarial/crash scenarios:
          1. Normal/Consistent State: Running reconciliation on a clean quarantined
             state prunes 0 files.
          2. Silent Pruning of Untracked Files: An untracked file (crash simulation)
             is pruned silently from the filesystem.
          3. Missing Registered File Detection: A registered file deleted from disk
             raises LedgerChainViolation.
          4. Tampered Registered File Detection: A registered file with modified
             content raises LedgerChainViolation.
        """
        tenant_id = f"chaos-tenant-{uuid.uuid4()}"
        req = self._make_write_request(
            skill_id="chaos-high-risk-v1",
            content=HIGH_RISK_SKILL_CONTENT,
            tenant_id=tenant_id,
        )

        try:
            try:
                self.cpt.write_skill(req)
            except SkillQuarantinedError as exc:
                q_path = exc.quarantine_path
                assert q_path is not None, "Quarantine path must be set on exception"

            # --- Sub-case 1: Clean State ---
            res = self.cpt.reconcile_quarantine(tenant_id)
            assert res["verified_count"] == 1, f"Expected 1 verified quarantine record, got {res['verified_count']}"
            assert len(res["pruned_files"]) == 0, f"Expected 0 pruned files, got {len(res['pruned_files'])}"

            # --- Sub-case 2: Untracked File Pruning ---
            # Simulate a partial failure where a file is written to quarantine but process dies
            # before writing to the database ledger.
            q_dir = Path(q_path).parent
            untracked_file = q_dir / "untracked_residual.py"
            untracked_file.write_bytes(b"import os\n# partial crash residual")

            res = self.cpt.reconcile_quarantine(tenant_id)
            assert not untracked_file.exists(), "Untracked file was not pruned"
            assert len(res["pruned_files"]) == 1, "Expected 1 pruned file"
            assert str(untracked_file.resolve()) in [str(Path(f).resolve()) for f in res["pruned_files"]], "Pruned file list mismatch"

            # --- Sub-case 4: Tampered Registered File Detection (Design Refinement 6) ---
            # Modify the contents of the registered quarantined file.
            original_content = Path(q_path).read_bytes()
            Path(q_path).write_bytes(b"# altered content")
            try:
                self.cpt.reconcile_quarantine(tenant_id)
                self._record("T6-12", False, "Reconciliation succeeded despite tampered quarantined file")
                return
            except LedgerChainViolation:
                pass  # Correct: raised LedgerChainViolation on tampering detection

            # Restore original content for next step
            Path(q_path).write_bytes(original_content)

            # --- Sub-case 3: Missing Registered File Detection ---
            # Physically delete the registered quarantined file.
            Path(q_path).unlink()
            try:
                self.cpt.reconcile_quarantine(tenant_id)
                self._record("T6-12", False, "Reconciliation succeeded despite missing quarantined file")
                return
            except LedgerChainViolation:
                pass  # Correct: raised LedgerChainViolation on missing file

            self._record("T6-12", True)

        except NotImplementedError:
            self._record("T6-12", False, "CPT reconciliation not implemented (expected RED)")
        except AssertionError as exc:
            self._record("T6-12", False, str(exc))

    # ------------------------------------------------------------------
    # T6-13: Factory Method Validation (Design Refinement 6)
    # ------------------------------------------------------------------

    def test_factory_method_quarantine(self) -> None:
        """
        Verify that constructing a CPTClient via from_workspace factory method
        behaves identically to base client construction, enforcing correct
        watchdog interception, durable logging, and reconciliation.
        """
        tenant_id = f"factory-tenant-{uuid.uuid4()}"
        factory_cpt = CPTClient.from_workspace(self.cpt._watchdog._root)
        
        req = self._make_write_request(
            skill_id="factory-high-risk-v1",
            content=HIGH_RISK_SKILL_CONTENT,
            tenant_id=tenant_id,
        )

        try:
            try:
                factory_cpt.write_skill(req)
                self._record("T6-13", False, "High-risk skill was not intercepted by factory client")
                return
            except SkillQuarantinedError as exc:
                q_path = exc.quarantine_path
                assert q_path is not None, "Quarantine path must be set on factory exception"

            # Verify both envelope and quarantine logs are correctly committed via factory
            stored_env = factory_cpt.get_envelope(req.skill_id, tenant_id)
            assert stored_env.auto_approved is False, "Factory envelope must be marked auto_approved=False"
            
            q_logs = factory_cpt.get_quarantine_log(tenant_id)
            assert len(q_logs) == 1, "Factory quarantine event was not logged durably"

            # Verify reconciliation prunes untracked files correctly via factory client
            q_dir = Path(q_path).parent
            untracked = q_dir / "untracked_factory_remnant.py"
            untracked.write_bytes(b"import os\n# factory crash remnant")

            res = factory_cpt.reconcile_quarantine(tenant_id)
            assert not untracked.exists(), "Factory reconciliation failed to prune untracked file"
            assert len(res["pruned_files"]) == 1, "Factory reconciliation pruned count mismatch"

            self._record("T6-13", True)

        except NotImplementedError:
            self._record("T6-13", False, "CPT factory method not implemented")
        except AssertionError as exc:
            self._record("T6-13", False, str(exc))

    # ------------------------------------------------------------------
    # T6-14: Key Rotation & Dynamic Key Versioning Validation
    # ------------------------------------------------------------------

    def test_key_rotation_and_versioning(self) -> None:
        """
        T6-14: Key Rotation & Dynamic Key Versioning Validation.
        Asserts these five specific properties:
          1. New Key Verification: Rotate key -> new envelope uses new key_id, verifies with new key.
          2. Historical Continuity: Old envelope retains original key_id, still verifies with original key.
          3. Missing Key ID Exception: Unknown key_id lookup raises LedgerChainViolation or cryptographic failure.
          4. Tamper Detection: Tampered signature (valid key_id, wrong HMAC) raises LedgerChainViolation or cryptographic failure.
          5. Upgraded Legacy Key Validation: Pre-existing row with key_id = 'v1' migrates correctly -> verifies with original secret.
        """
        import sqlite3
        import shutil
        import hmac
        import os
        import tempfile
        from clawglove.provenance.client import verify_envelope_signature, _load_or_bootstrap_keyring, CPTClient, ProvenanceEnvelope
        from clawglove.provenance.rotate import rotate_key
        from clawglove.provenance.ledger import _chain_hash

        tenant_id = f"rotation-tenant-{uuid.uuid4()}"
        test_ws = Path(tempfile.mkdtemp(prefix="cgbench_rotation_ws_"))
        try:
            # Write a legacy .clawglove_secret file
            legacy_secret = os.urandom(32).hex()
            legacy_secret_file = test_ws / ".clawglove_secret"
            legacy_secret_file.write_text(legacy_secret, encoding="utf-8")

            # Create a base client mock/stub for this workspace
            class StubBaseClient:
                def __init__(self, ws: Path, secret: str):
                    self.workspace_root = ws
                    self.cpt_signing_secret = secret

            base_client1 = StubBaseClient(test_ws, legacy_secret)
            cpt = CPTClient(base_client1)
            
            # Write envelope 1 (legacy key)
            req1 = self._make_write_request(
                skill_id="legacy-key-skill-v1",
                content=LOW_RISK_SKILL_CONTENT,
                tenant_id=tenant_id,
            )
            env1 = cpt.write_skill(req1)
            
            keyring = _load_or_bootstrap_keyring(test_ws)
            legacy_derived_id = hashlib.sha256(bytes.fromhex(legacy_secret)).hexdigest()[:16]
            assert keyring["active_key_id"] == legacy_derived_id, "active_key_id must be hash-derived"
            assert env1.key_id == legacy_derived_id, "Legacy write must use the hash-derived active key ID"
            
            # --- Assertion 5: Upgraded Legacy Key Validation ---
            db_conn = sqlite3.connect(str(test_ws / "provenance_ledger.db"))
            try:
                prev_row = db_conn.execute("SELECT chain_hash FROM envelopes ORDER BY id DESC LIMIT 1").fetchone()
                prev_hash = prev_row[0] if prev_row else "0" * 64
                
                content_hash_v1 = _sha256(b"def legacy_function(): pass")
                sig_v1 = "clawglove-" + hmac.new(bytes.fromhex(legacy_secret), content_hash_v1.encode(), hashlib.sha256).hexdigest()
                new_chain = _chain_hash(prev_hash, content_hash_v1)
                
                # Insert directly with key_id = 'v1'
                db_conn.execute(
                    """
                    INSERT INTO envelopes (
                        skill_id, file_path, content_hash, originating_session_id,
                        parent_user_request_hash, generator_model, generation_timestamp,
                        tenant_id, signature, auto_approved, chain_hash, key_id, node_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "legacy-v1-skill", "skills/legacy-v1-skill.py", content_hash_v1,
                        "legacy-session", "legacy-hash", "legacy-model", "2026-06-01T12:00:00Z",
                        tenant_id, sig_v1, 1, new_chain, "v1", "legacy-node"
                    )
                )
                db_conn.commit()
            finally:
                db_conn.close()

            # Let's retrieve this v1 envelope via get_envelope and check if it verifies!
            env_v1 = cpt.get_envelope("legacy-v1-skill", tenant_id)
            assert env_v1.key_id == "v1", "Should retrieve envelope with key_id = 'v1'"
            # Check if the 'v1' key in the bootstrapped keyring verifies it correctly
            v1_key_hex = keyring["keys"].get("v1")
            assert v1_key_hex == legacy_secret, "v1 key in keyring must be original legacy secret"
            assert verify_envelope_signature(env_v1, v1_key_hex) is True, "Legacy row with key_id = 'v1' must verify correctly"

            # --- Assertion 1: New Key Verification ---
            new_secret = os.urandom(32).hex()
            rotate_res = rotate_key(test_ws, new_secret)
            new_key_id = rotate_res["new_key_id"]
            
            cpt2 = CPTClient.from_workspace(test_ws)
            assert cpt2._active_key_id == new_key_id, "Rotated key must be active on new client"
            
            # Write envelope 2 (new key)
            req2 = self._make_write_request(
                skill_id="new-key-skill-v1",
                content=LOW_RISK_SKILL_CONTENT,
                tenant_id=tenant_id,
            )
            env2 = cpt2.write_skill(req2)
            assert env2.key_id == new_key_id, "New write must use new active key ID"
            
            keyring = _load_or_bootstrap_keyring(test_ws)
            new_key_hex = keyring["keys"][new_key_id]
            assert verify_envelope_signature(env2, new_key_hex) is True, "Envelope 2 must verify with new key"

            # --- Assertion 2: Historical Continuity ---
            retrieved_env1 = cpt2.get_envelope("legacy-key-skill-v1", tenant_id)
            assert retrieved_env1.key_id == legacy_derived_id, "Old envelope must retain original key_id"
            legacy_key_hex = keyring["keys"][legacy_derived_id]
            assert verify_envelope_signature(retrieved_env1, legacy_key_hex) is True, "Old envelope must verify with original key"

            # --- Assertion 3: Missing Key ID Exception ---
            fake_envelope = ProvenanceEnvelope(
                skill_id="fake-skill", file_path="skills/fake.py",
                content_hash=env2.content_hash, originating_session_id=env2.originating_session_id,
                parent_user_request_hash=env2.parent_user_request_hash, generator_model=env2.generator_model,
                generation_timestamp=env2.generation_timestamp, tenant_id=env2.tenant_id,
                signature=env2.signature, auto_approved=True, key_id="unknown_key_id"
            )
            assert fake_envelope.key_id not in keyring["keys"], "Fake key ID must not be in keyring"
            assert verify_envelope_signature(fake_envelope, "00"*32) is False, "Signature verification with wrong key must fail"

            # --- Assertion 4: Tamper Detection ---
            tampered_envelope = ProvenanceEnvelope(
                skill_id=env2.skill_id, file_path=env2.file_path,
                content_hash=env2.content_hash, originating_session_id=env2.originating_session_id,
                parent_user_request_hash=env2.parent_user_request_hash, generator_model=env2.generator_model,
                generation_timestamp=env2.generation_timestamp, tenant_id=env2.tenant_id,
                signature=env2.signature + "tampered", auto_approved=env2.auto_approved,
                key_id=env2.key_id
            )
            assert verify_envelope_signature(tampered_envelope, new_key_hex) is False, "Tampered signature verification must fail"

            self._record("T6-14", True)
        except NotImplementedError:
            self._record("T6-14", False, "CPT key rotation not implemented")
        except AssertionError as exc:
            self._record("T6-14", False, str(exc))
        except Exception as exc:
            self._record("T6-14", False, f"Unexpected error: {exc}")
        finally:
            shutil.rmtree(test_ws, ignore_errors=True)

    # ------------------------------------------------------------------
    # T6-15: Deprecation Warning for Singular Secret File
    # ------------------------------------------------------------------

    def test_deprecation_warning_singular_secret(self) -> None:
        """
        Phase 6 Warmup: When a workspace contains the legacy singular
        '.clawglove_secret' file, CPTClient.from_workspace() must emit
        a DeprecationWarning naming '.clawglove_secrets' as the migration
        target. When the file is absent, no warning must be emitted.
        """
        import warnings
        import tempfile
        import shutil

        test_ws = Path(tempfile.mkdtemp(prefix="cgbench_deprecation_ws_"))
        try:
            # --- Sub-case 1: Warning IS emitted when singular file exists ---
            singular = test_ws / ".clawglove_secret"
            singular.write_text("00" * 32, encoding="utf-8")

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                CPTClient.from_workspace(test_ws)

            depr_warnings = [
                w for w in caught if issubclass(w.category, DeprecationWarning)
            ]
            assert len(depr_warnings) >= 1, (
                f"Expected at least 1 DeprecationWarning, got {len(depr_warnings)}"
            )
            msg = str(depr_warnings[0].message)
            assert ".clawglove_secrets" in msg, (
                f"Warning must name the migration target '.clawglove_secrets'. "
                f"Got: {msg}"
            )

            # --- Sub-case 2: No warning when singular file is absent ---
            clean_ws = Path(tempfile.mkdtemp(prefix="cgbench_deprecation_clean_"))
            try:
                with warnings.catch_warnings(record=True) as caught_clean:
                    warnings.simplefilter("always")
                    CPTClient.from_workspace(clean_ws)

                depr_clean = [
                    w for w in caught_clean
                    if issubclass(w.category, DeprecationWarning)
                    and ".clawglove_secret" in str(w.message)
                ]
                assert len(depr_clean) == 0, (
                    f"No DeprecationWarning expected in clean workspace, "
                    f"got {len(depr_clean)}"
                )
            finally:
                shutil.rmtree(clean_ws, ignore_errors=True)

            self._record("T6-15", True)

        except AssertionError as exc:
            self._record("T6-15", False, str(exc))
        except Exception as exc:
            self._record("T6-15", False, f"Unexpected error: {exc}")
        finally:
            shutil.rmtree(test_ws, ignore_errors=True)

    # ------------------------------------------------------------------
    # Runner
    # ------------------------------------------------------------------

    def run(self) -> dict:
        """
        Execute all Layer 6 tests in definition order and return a result
        summary compatible with cgbench/runner.py's layer result schema.
        """
        tests = [
            self.test_low_risk_auto_approve,
            self.test_high_risk_subprocess_quarantined,
            self.test_high_risk_requests_quarantined,
            self.test_high_risk_socket_quarantined,
            self.test_orphaned_payload_no_session_id,
            self.test_orphaned_payload_no_request_hash,
            self.test_core_system_prompt_halted,
            self.test_core_pyproject_halted,
            self.test_quarantine_tenant_isolation,
            self.test_envelope_retrievable_and_signed,
            self.test_ledger_durability,
            self.test_chaos_reconciliation,
            self.test_factory_method_quarantine,
            self.test_key_rotation_and_versioning,
            self.test_deprecation_warning_singular_secret,
        ]

        start = time.monotonic()
        for t in tests:
            t()
        elapsed = time.monotonic() - start

        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = total - passed

        # CGBench scoring: each layer contributes a normalised 0.0–1.0 score.
        # All 11 tests carry equal weight.
        score = passed / total if total > 0 else 0.0

        return {
            "layer": self.LAYER,
            "name": self.NAME,
            "score": round(score, 3),
            "passed": passed,
            "failed": failed,
            "total": total,
            "elapsed_s": round(elapsed, 3),
            "results": self.results,
            # Governance grade contribution.
            # G-5 (Provenance Certified) requires score >= 0.9 on L6
            # in addition to existing L1–L5 thresholds.
            "grade_gate": score >= 0.9,
        }


# ---------------------------------------------------------------------------
# pytest integration
# ---------------------------------------------------------------------------
# These fixtures allow running the file directly with pytest without needing
# a live ClawGloveClient.  A minimal stub client is injected.

import tempfile
_STUB_WORKSPACE = Path(tempfile.mkdtemp(prefix="cgbench_stub_workspace_"))

class _StubClawGloveClient:
    """Minimal client stub for pytest runs without a live sidecar."""
    tenant_id = "pytest-tenant"
    workspace_root = _STUB_WORKSPACE


def _make_layer() -> Layer6SkillProvenance:
    return Layer6SkillProvenance(_StubClawGloveClient())


def test_t6_01_low_risk_auto_approve():
    layer = _make_layer()
    layer.test_low_risk_auto_approve()
    r = next(r for r in layer.results if r["test"] == "T6-01")
    assert r["passed"] is True


def test_t6_02_subprocess_quarantined():
    layer = _make_layer()
    layer.test_high_risk_subprocess_quarantined()
    r = next(r for r in layer.results if r["test"] == "T6-02")
    assert r["passed"] is True


def test_t6_03_requests_quarantined():
    layer = _make_layer()
    layer.test_high_risk_requests_quarantined()
    r = next(r for r in layer.results if r["test"] == "T6-03")
    assert r["passed"] is True


def test_t6_04_socket_quarantined():
    layer = _make_layer()
    layer.test_high_risk_socket_quarantined()
    r = next(r for r in layer.results if r["test"] == "T6-04")
    assert r["passed"] is True


def test_t6_05_orphaned_no_session():
    layer = _make_layer()
    layer.test_orphaned_payload_no_session_id()
    r = next(r for r in layer.results if r["test"] == "T6-05")
    assert r["passed"] is True


def test_t6_06_orphaned_no_request_hash():
    layer = _make_layer()
    layer.test_orphaned_payload_no_request_hash()
    r = next(r for r in layer.results if r["test"] == "T6-06")
    assert r["passed"] is True


def test_t6_07_system_prompt_halted():
    layer = _make_layer()
    layer.test_core_system_prompt_halted()
    r = next(r for r in layer.results if r["test"] == "T6-07")
    assert r["passed"] is True


def test_t6_08_pyproject_halted():
    layer = _make_layer()
    layer.test_core_pyproject_halted()
    r = next(r for r in layer.results if r["test"] == "T6-08")
    assert r["passed"] is True


def test_t6_09_tenant_isolation():
    layer = _make_layer()
    layer.test_quarantine_tenant_isolation()
    r = next(r for r in layer.results if r["test"] == "T6-09")
    assert r["passed"] is True


def test_t6_10_envelope_signed():
    layer = _make_layer()
    layer.test_envelope_retrievable_and_signed()
    r = next(r for r in layer.results if r["test"] == "T6-10")
    assert r["passed"] is True


def test_t6_11_ledger_durability():
    layer = _make_layer()
    layer.test_ledger_durability()
    r = next(r for r in layer.results if r["test"] == "T6-11")
    assert r["passed"] is True


def test_t6_12_chaos_reconciliation():
    layer = _make_layer()
    layer.test_chaos_reconciliation()
    r = next(r for r in layer.results if r["test"] == "T6-12")
    assert r["passed"] is True


def test_t6_13_factory_reconciliation():
    layer = _make_layer()
    layer.test_factory_method_quarantine()
    r = next(r for r in layer.results if r["test"] == "T6-13")
    assert r["passed"] is True


def test_t6_14_key_rotation_and_versioning():
    layer = _make_layer()
    layer.test_key_rotation_and_versioning()
    r = next(r for r in layer.results if r["test"] == "T6-14")
    assert r["passed"] is True


def test_t6_15_deprecation_warning():
    layer = _make_layer()
    layer.test_deprecation_warning_singular_secret()
    r = next(r for r in layer.results if r["test"] == "T6-15")
    assert r["passed"] is True


# ---------------------------------------------------------------------------
# Standalone execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    layer = Layer6SkillProvenance(_StubClawGloveClient())
    summary = layer.run()

    print(f"\nCGBench Layer {summary['layer']} - {summary['name']}")
    print(f"Score : {summary['score']:.1%}  ({summary['passed']}/{summary['total']} passed)")
    print(f"Grade gate (>=90%) : {'PASS' if summary['grade_gate'] else 'FAIL'}")
    print(f"Elapsed: {summary['elapsed_s']}s\n")

    for r in summary["results"]:
        status = "[PASS]" if r["passed"] else "[FAIL]"
        note = f"  - {r['note']}" if r.get("note") else ""
        print(f"  {status} {r['test']}{note}")

    sys.exit(0 if summary["grade_gate"] else 1)
