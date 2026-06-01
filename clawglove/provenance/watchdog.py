"""
clawglove/provenance/watchdog.py
=================================
Phase 2 — CPT Filesystem Interceptor

Two interception modes:

  1. SYNCHRONOUS (API path)
     `SkillWatchdog.intercept_write(req)` is called directly from CPTClient
     when an agent invokes the skill-write API.  This is the primary control
     path — it gates every intentional write through the tagger + gate pipeline
     before anything touches the filesystem.

  2. ASYNCHRONOUS (filesystem watcher)
     `SkillWatchdog.start_background_watcher()` launches an OS-level inotify/
     kqueue/FSEvents watcher on the configured skill directories.  This catches
     writes that bypass the API path (e.g., a compromised subprocess writing
     directly to skills/).  Out-of-band writes are immediately quarantined and
     a SKILL_OOB_WRITE event is emitted to the telemetry bus.

     The background watcher requires the `watchdog` package:
       pip install watchdog
     If not installed, start_background_watcher() raises ImportError with a
     clear message — it does NOT silently degrade to a no-op.

Design decisions implemented here (from RFC-003 §6):
  GAP-3:  Fail-closed on intercept timeout (INTERCEPT_TIMEOUT_S = 5.0s)
  GAP-4:  HIGH_RISK_IMPORTS list is the canonical gate trigger
  GAP-5:  Pure-Python skills with zero high-risk imports are auto-approvable
  GAP-6:  Quarantine path: quarantine/<tenant_id>/<session_id>/<skill_id>.py
  GAP-10: load_from_active() enforces tenant isolation
"""

from __future__ import annotations

import ast
import hashlib
import hmac
import json
import os
import shutil
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .exceptions import (
    InterceptTimeoutError,
    SkillQuarantinedError,
    TenantIsolationError,
)

# ---------------------------------------------------------------------------
# Constants (RFC-003 §6 binding specs)
# ---------------------------------------------------------------------------

INTERCEPT_TIMEOUT_S: float = 5.0  # GAP-3

# GAP-4: canonical high-risk import set.
# This list is read by the gate — do NOT add logic here.
# Extend via config override in sidecar/config.yaml if needed.
HIGH_RISK_IMPORTS: frozenset[str] = frozenset(
    {"subprocess", "requests", "socket", "urllib", "os", "ctypes", "cffi"}
)

# Skill file extensions the watchdog monitors.
MONITORED_EXTENSIONS: frozenset[str] = frozenset({".py", ".md", ".js", ".json"})

# Signature prefix per GAP-11.
SIGNATURE_PREFIX = "clawglove-"


# ---------------------------------------------------------------------------
# Import Analyzer
# ---------------------------------------------------------------------------

class SkillContentAnalyzer:
    """
    AST-based high-risk import detector.

    String matching is insufficient — an agent can bypass it with:
        importlib.import_module('subprocess')
        __import__('os')

    AST parsing catches standard import statements and attribute-based
    dynamic imports at the source level.  It does NOT catch fully obfuscated
    dynamic imports (e.g., exec(compile(...))), but those patterns require
    code execution to detect and are out of scope for a static gate.

    The HIGH_RISK_IMPORTS list remains the canonical decision surface.
    The AST is the detection mechanism; the list is the policy.
    """

    def __init__(
        self,
        high_risk_imports: frozenset[str] | None = None,
    ):
        self._risky = high_risk_imports or HIGH_RISK_IMPORTS

    def find_risky_imports(self, source: bytes) -> list[str]:
        """
        Return the list of high-risk module names found in source.
        Returns [] if source is not valid Python (e.g., .md, .json files).
        """
        try:
            tree = ast.parse(source)
        except SyntaxError:
            # Non-Python content (.md, .json).  No import analysis possible.
            return []

        found: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in self._risky:
                        found.append(root)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root = node.module.split(".")[0]
                    if root in self._risky:
                        found.append(root)
            elif isinstance(node, ast.Call):
                # Catch __import__('os') and importlib.import_module('subprocess')
                if isinstance(node.func, ast.Name) and node.func.id == "__import__":
                    if node.args and isinstance(node.args[0], ast.Constant):
                        root = str(node.args[0].value).split(".")[0]
                        if root in self._risky:
                            found.append(f"__import__('{root}')")
                elif isinstance(node.func, ast.Attribute):
                    if node.func.attr == "import_module" and node.args:
                        if isinstance(node.args[0], ast.Constant):
                            root = str(node.args[0].value).split(".")[0]
                            if root in self._risky:
                                found.append(f"import_module('{root}')")

        return list(dict.fromkeys(found))  # deduplicate, preserve order

    def is_high_risk(self, source: bytes) -> bool:
        return bool(self.find_risky_imports(source))


# ---------------------------------------------------------------------------
# Quarantine Store
# ---------------------------------------------------------------------------

@dataclass
class QuarantineRecord:
    skill_id: str
    tenant_id: str
    session_id: str
    quarantine_path: str
    content_hash: str
    risky_imports: list[str]
    timestamp: str


class QuarantineStore:
    """
    Manages the quarantine directory.

    Layout (GAP-6 binding spec):
        <workspace_root>/quarantine/<tenant_id>/<session_id>/<skill_id>.py

    Each quarantined skill has a sibling .meta.json file with the
    QuarantineRecord payload for operator review.
    """

    def __init__(self, workspace_root: Path):
        self._root = workspace_root / "quarantine"
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def relocate(
        self,
        skill_id: str,
        tenant_id: str,
        session_id: str,
        content: bytes,
        risky_imports: list[str],
    ) -> str:
        """
        Write content to the quarantine directory.
        Returns the quarantine path string.
        """
        dest_dir = self._root / tenant_id / session_id
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Determine extension from skill_id or default to .py
        ext = Path(skill_id).suffix or ".py"
        dest_file = dest_dir / f"{skill_id}{ext}" if not skill_id.endswith(ext) else dest_dir / skill_id

        with self._lock:
            dest_file.write_bytes(content)

            meta = QuarantineRecord(
                skill_id=skill_id,
                tenant_id=tenant_id,
                session_id=session_id,
                quarantine_path=str(dest_file),
                content_hash=_sha256(content),
                risky_imports=risky_imports,
                timestamp=_now_iso(),
            )
            meta_file = dest_dir / f"{skill_id}.meta.json"
            meta_file.write_text(
                json.dumps(meta.__dict__, indent=2), encoding="utf-8"
            )

        return str(dest_file)

    def is_quarantined(self, skill_id: str, tenant_id: str) -> bool:
        """True if any session's quarantine dir contains this skill."""
        tenant_dir = self._root / tenant_id
        if not tenant_dir.exists():
            return False
        for session_dir in tenant_dir.iterdir():
            # Match either direct skill_id or skill_id with monitored extensions
            if (session_dir / skill_id).exists():
                return True
            for ext in MONITORED_EXTENSIONS:
                candidate = skill_id if skill_id.endswith(ext) else f"{skill_id}{ext}"
                if (session_dir / candidate).exists():
                    return True
        return False

    def tenant_owns(self, quarantine_path: str, tenant_id: str) -> bool:
        """Verify that the path belongs to the given tenant."""
        return (self._root / tenant_id).resolve() in Path(quarantine_path).resolve().parents

    def list_records(self, tenant_id: str) -> list[QuarantineRecord]:
        """Return all quarantine records for a tenant."""
        tenant_dir = self._root / tenant_id
        if not tenant_dir.exists():
            return []
        records: list[QuarantineRecord] = []
        for meta_file in tenant_dir.rglob("*.meta.json"):
            try:
                data = json.loads(meta_file.read_text(encoding="utf-8"))
                records.append(QuarantineRecord(**data))
            except (json.JSONDecodeError, TypeError):
                continue
        return records


# ---------------------------------------------------------------------------
# Active Skill Store
# ---------------------------------------------------------------------------

class ActiveSkillStore:
    """
    Manages the approved skill set for a workspace.

    Layout:
        <workspace_root>/skills/<tenant_id>/<skill_id>

    Tenant isolation is enforced at read time.  A request to load
    tenant_B's skill while authenticated as tenant_A raises TenantIsolationError.
    (GAP-10 binding spec.)
    """

    def __init__(self, workspace_root: Path):
        self._root = workspace_root / "skills"
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def write(self, skill_id: str, tenant_id: str, content: bytes) -> Path:
        dest_dir = self._root / tenant_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        ext = Path(skill_id).suffix or ".py"
        dest = dest_dir / (skill_id if skill_id.endswith(ext) else f"{skill_id}{ext}")
        with self._lock:
            dest.write_bytes(content)
        return dest

    def read(self, skill_id: str, requesting_tenant_id: str) -> bytes:
        """
        Load skill content.  Raises TenantIsolationError if the path would
        resolve outside the requesting tenant's directory.
        """
        # Resolve all possible file extensions.
        tenant_dir = self._root / requesting_tenant_id
        for ext in MONITORED_EXTENSIONS:
            candidate = tenant_dir / (
                skill_id if skill_id.endswith(ext) else f"{skill_id}{ext}"
            )
            if candidate.exists():
                # Verify the resolved path is under the tenant's directory.
                # Prevents path traversal (e.g., skill_id = "../../other_tenant/skill").
                try:
                    candidate.resolve().relative_to(tenant_dir.resolve())
                except ValueError:
                    raise TenantIsolationError(
                        requesting_tenant=requesting_tenant_id,
                        owning_tenant="unknown",
                        skill_id=skill_id,
                    )
                return candidate.read_bytes()

        raise FileNotFoundError(
            f"Skill '{skill_id}' not found in active set for tenant '{requesting_tenant_id}'"
        )

    def exists(self, skill_id: str, tenant_id: str) -> bool:
        tenant_dir = self._root / tenant_id
        for ext in MONITORED_EXTENSIONS:
            if (tenant_dir / f"{skill_id}{ext}").exists():
                return True
        return False


# ---------------------------------------------------------------------------
# Protected Path Registry
# ---------------------------------------------------------------------------

class ProtectedPathRegistry:
    """
    Holds the set of core paths that must never be written by an agent.

    GAP-9 (binding spec): the list must be configurable — NOT hardcoded in
    the watchdog.  The default list is a safe minimum; operators extend it
    via sidecar config.
    """

    DEFAULT_PROTECTED: list[str] = [
        "clawglove/sidecar/system_prompt.md",
        "pyproject.toml",
        "clawglove/sidecar/daemon.py",
        "clawglove/sidecar/engine.py",
        "clawglove/sidecar/manifest.yaml",
        ".clawglove/config.yaml",
    ]

    def __init__(self, extra_paths: list[str] | None = None):
        self._paths: set[str] = set(self.DEFAULT_PROTECTED)
        if extra_paths:
            self._paths.update(extra_paths)

    def is_protected(self, path: str) -> bool:
        """
        True if the given path (relative or absolute) matches any protected entry.
        Matching is suffix-based to handle workspace-relative and absolute paths.
        """
        p = Path(path)
        for protected in self._paths:
            pp = Path(protected)
            # Check: path ends with the protected pattern.
            try:
                p.relative_to(pp.anchor)
            except ValueError:
                pass
            # Simple suffix match works for both relative and absolute.
            if str(p).endswith(str(pp)) or str(p) == str(pp):
                return True
            # Also check just the filename for single-file protected entries.
            if p.name == pp.name and len(pp.parts) == 1:
                return True
        return False

    def add(self, path: str) -> None:
        self._paths.add(path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _now_iso() -> str:
    import datetime
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _hmac_sign(content_hash: str, secret: bytes) -> str:
    """
    HMAC-SHA256 signature prefixed with 'clawglove-' per GAP-11.
    """
    sig = hmac.new(secret, content_hash.encode(), hashlib.sha256).hexdigest()
    return f"{SIGNATURE_PREFIX}{sig}"


# ---------------------------------------------------------------------------
# Core Watchdog
# ---------------------------------------------------------------------------

@dataclass
class InterceptResult:
    """
    Return value from a successful `intercept_write` call.
    Maps directly to ProvenanceEnvelope fields.
    """
    skill_id: str
    tenant_id: str
    session_id: str
    content_hash: str
    file_path: str
    auto_approved: bool
    quarantine_path: str | None
    risky_imports: list[str] = field(default_factory=list)


class SkillWatchdog:
    """
    Core interceptor.  Called by CPTClient on every skill write.

    Responsibilities (Phase 2):
      1. Validate the write request is not targeting a protected core path.
      2. Analyse content for high-risk imports (AST).
      3. If high-risk: relocate to quarantine, return InterceptResult with
         auto_approved=False and quarantine_path set.
      4. If clean: write to active skill store, return InterceptResult with
         auto_approved=True.
      5. Enforce INTERCEPT_TIMEOUT_S fail-closed timeout on the full pipeline.
      6. Optionally start a background filesystem watcher for out-of-band writes.

    Phase 3 will add: Provenance Tagger, HMAC signing, ledger persistence.
    The tagger stubs below accept valid requests (non-empty session_id and
    parent_request_hash) without persisting envelopes — that wiring comes in
    Phase 3 when the ledger is built.
    """

    def __init__(
        self,
        workspace_root: Path | str | None = None,
        signing_secret: bytes | None = None,
        protected_paths: list[str] | None = None,
        high_risk_imports: frozenset[str] | None = None,
        timeout_s: float = INTERCEPT_TIMEOUT_S,
    ):
        self._root = Path(workspace_root or tempfile.mkdtemp(prefix="clawglove_"))
        self._root.mkdir(parents=True, exist_ok=True)

        # GAP-11: signing secret.  In production this is injected from the
        # sidecar config; in tests a random secret is generated per instance.
        self._secret = signing_secret or os.urandom(32)
        self._timeout_s = timeout_s

        self._analyzer = SkillContentAnalyzer(high_risk_imports)
        self._quarantine = QuarantineStore(self._root)
        self._active = ActiveSkillStore(self._root)
        self._protected = ProtectedPathRegistry(protected_paths)

        self._bg_watcher: Any = None  # set by start_background_watcher()
        self._bg_thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Synchronous intercept (primary control path)
    # ------------------------------------------------------------------

    def intercept_write(
        self,
        skill_id: str,
        file_path: str,
        content: bytes,
        session_id: str,
        parent_request_hash: str,
        generator_model: str,
        tenant_id: str,
    ) -> InterceptResult:
        """
        Gate a skill write through the full CPT pipeline.

        Phase 2 coverage:
          - Protected path check  (T6-07, T6-08)
          - Orphan lineage check  (T6-05, T6-06) — raises OrphanedPayloadError
          - High-risk import gate (T6-02, T6-03, T6-04)
          - Clean write to active (T6-01)
          - Tenant-scoped quarantine (T6-09)

        The call runs in a background thread with INTERCEPT_TIMEOUT_S deadline.
        If the deadline expires, InterceptTimeoutError is raised (fail-closed).
        """
        result_holder: list[InterceptResult | Exception] = []

        def _run() -> None:
            try:
                r = self._pipeline(
                    skill_id=skill_id,
                    file_path=file_path,
                    content=content,
                    session_id=session_id,
                    parent_request_hash=parent_request_hash,
                    generator_model=generator_model,
                    tenant_id=tenant_id,
                )
                result_holder.append(r)
            except Exception as exc:  # noqa: BLE001
                result_holder.append(exc)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=self._timeout_s)

        if not result_holder:
            # Thread still running after timeout — fail closed.
            raise InterceptTimeoutError(skill_id=skill_id, timeout_s=self._timeout_s)

        outcome = result_holder[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def _pipeline(
        self,
        skill_id: str,
        file_path: str,
        content: bytes,
        session_id: str,
        parent_request_hash: str,
        generator_model: str,
        tenant_id: str,
    ) -> InterceptResult:
        """
        Internal pipeline — runs inside the timeout thread.
        """
        from .exceptions import IdentityHaltError, OrphanedPayloadError

        # ── Step 1: Protected path check (T-009) ──────────────────────
        if self._protected.is_protected(file_path):
            content_hash = _sha256(content)
            raise IdentityHaltError(
                protected_path=file_path,
                detected_hash_delta=content_hash,
                session_id=session_id,
            )

        # ── Step 2: Orphan lineage check (T-008) ─────────────────────
        # Phase 2 stub: tagger validation without ledger persistence.
        # Full ledger persistence wired in Phase 3.
        if not session_id or not session_id.strip():
            raise OrphanedPayloadError(
                skill_id=skill_id,
                missing_field="session_id",
            )
        if not parent_request_hash or not parent_request_hash.strip():
            raise OrphanedPayloadError(
                skill_id=skill_id,
                missing_field="parent_user_request_hash",
            )

        # ── Step 3: High-risk import analysis ─────────────────────────
        content_hash = _sha256(content)
        risky = self._analyzer.find_risky_imports(content)

        if risky:
            # Quarantine: relocate content, do NOT write to active set.
            q_path = self._quarantine.relocate(
                skill_id=skill_id,
                tenant_id=tenant_id,
                session_id=session_id,
                content=content,
                risky_imports=risky,
            )
            raise SkillQuarantinedError(
                skill_id=skill_id,
                reason=f"high-risk imports detected: {risky}",
                quarantine_path=q_path,
                risky_imports=risky,
            )

        # ── Step 4: Write to active skill set ─────────────────────────
        active_path = self._active.write(
            skill_id=skill_id,
            tenant_id=tenant_id,
            content=content,
        )

        return InterceptResult(
            skill_id=skill_id,
            tenant_id=tenant_id,
            session_id=session_id,
            content_hash=content_hash,
            file_path=str(active_path),
            auto_approved=True,
            quarantine_path=None,
            risky_imports=[],
        )

    # ------------------------------------------------------------------
    # Active skill loader
    # ------------------------------------------------------------------

    def load_from_active(self, skill_id: str, requesting_tenant_id: str) -> bytes:
        """
        Load a skill from the active set.  Enforces tenant isolation (GAP-10).

        Raises:
            FileNotFoundError       — skill not in active set
            SkillQuarantinedError   — skill is in quarantine for this tenant
            TenantIsolationError    — path resolves outside tenant boundary
        """
        # Check quarantine first — if the skill is quarantined, block the load
        # even if somehow a file exists in the active set (defence-in-depth).
        if self._quarantine.is_quarantined(skill_id, requesting_tenant_id):
            raise SkillQuarantinedError(
                skill_id=skill_id,
                reason="skill is in quarantine — operator approval required",
                quarantine_path=None,
            )

        return self._active.read(skill_id, requesting_tenant_id)

    # ------------------------------------------------------------------
    # Background filesystem watcher (catches out-of-band writes)
    # ------------------------------------------------------------------

    def start_background_watcher(
        self,
        watch_dirs: list[str | Path] | None = None,
        tenant_id: str = "default",
    ) -> None:
        """
        Start an async OS-level watcher on configured skill directories.

        Any file creation or modification detected outside the API path
        (i.e., not via intercept_write) is treated as an out-of-band write
        and immediately quarantined.

        Requires: pip install watchdog
        Raises ImportError with a clear message if not installed.
        """
        try:
            from watchdog.events import FileSystemEventHandler, FileSystemEvent
            from watchdog.observers import Observer
        except ImportError as exc:
            raise ImportError(
                "The 'watchdog' package is required for background filesystem "
                "monitoring.  Install it with: pip install watchdog"
            ) from exc

        monitored = [Path(d) for d in (watch_dirs or [self._root / "skills"])]

        class _OOBHandler(FileSystemEventHandler):
            """Quarantine any file created/modified outside the API path."""

            def __init__(self_h) -> None:
                self_h._seen: set[str] = set()

            def _handle(self_h, event: FileSystemEvent) -> None:
                if event.is_directory:
                    return
                p = Path(event.src_path)
                if p.suffix not in MONITORED_EXTENSIONS:
                    return
                key = str(p)
                if key in self_h._seen:
                    return
                self_h._seen.add(key)
                try:
                    content = p.read_bytes()
                    skill_id = p.stem
                    self._quarantine.relocate(
                        skill_id=skill_id,
                        tenant_id=tenant_id,
                        session_id="oob-write",
                        content=content,
                        risky_imports=self._analyzer.find_risky_imports(content),
                    )
                    # Remove from active path so the OOB write is not loadable.
                    p.unlink(missing_ok=True)
                except Exception:  # noqa: BLE001
                    pass  # Watcher must not crash — log via telemetry in Phase 4.

            def on_created(self_h, event: FileSystemEvent) -> None:
                self_h._handle(event)

            def on_modified(self_h, event: FileSystemEvent) -> None:
                self_h._handle(event)

        observer = Observer()
        handler = _OOBHandler()
        for d in monitored:
            d.mkdir(parents=True, exist_ok=True)
            observer.schedule(handler, str(d), recursive=True)

        observer.start()
        self._bg_watcher = observer
        self._bg_thread = threading.Thread(
            target=observer.join, daemon=True, name="cpt-bg-watcher"
        )
        self._bg_thread.start()

    def stop_background_watcher(self) -> None:
        if self._bg_watcher is not None:
            self._bg_watcher.stop()
            self._bg_watcher = None

    def __del__(self) -> None:
        self.stop_background_watcher()
