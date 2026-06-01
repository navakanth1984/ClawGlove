"""
clawglove/provenance/exceptions.py
===================================
Exception hierarchy for the Context Provenance Tracking (CPT) subsystem.

All exceptions carry structured metadata so the sidecar's telemetry plane
can log them as typed events rather than unstructured strings.
"""

from __future__ import annotations


class CPTError(Exception):
    """Base class for all CPT subsystem errors."""


class LedgerChainViolation(CPTError):
    """
    Raised when hash chain verification fails or quarantined files are tampered/missing —
    the ledger integrity has been compromised.
    """

    def __init__(self, table: str, row_id: int, expected: str, actual: str):
        self.table = table
        self.row_id = row_id
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Hash chain violation in '{table}' at row {row_id}: "
            f"expected '{expected[:16]}...', got '{actual[:16]}...'. "
            f"Ledger integrity compromised."
        )


class SkillQuarantinedError(CPTError):
    """
    Raised by the Quarantine Gate when a skill write is blocked due to
    high-risk import patterns.

    The skill has been relocated to the quarantine directory; it is NOT
    in the active skill set and cannot be loaded.
    """

    def __init__(
        self,
        skill_id: str,
        reason: str,
        quarantine_path: str | None = None,
        risky_imports: list[str] | None = None,
    ):
        self.skill_id = skill_id
        self.reason = reason
        self.quarantine_path = quarantine_path
        self.risky_imports = risky_imports or []
        super().__init__(
            f"Skill '{skill_id}' quarantined: {reason} "
            f"(risky imports: {self.risky_imports})"
        )


class OrphanedPayloadError(CPTError):
    """
    Raised by the Provenance Tagger when a skill write lacks required
    lineage fields (session_id or parent_user_request_hash).

    Orphaned payloads are REJECTED outright — they do not enter quarantine.
    Quarantine implies the content was accepted but held pending review.
    An orphaned payload has no verifiable lineage and must not enter the
    system at all.  (GAP-7, GAP-8 — binding spec from RFC-003 §6.)
    """

    def __init__(self, skill_id: str, missing_field: str):
        self.skill_id = skill_id
        self.missing_field = missing_field
        super().__init__(
            f"Skill '{skill_id}' rejected: orphaned payload "
            f"(missing required field: '{missing_field}')"
        )


class IdentityHaltError(CPTError):
    """
    Raised by the Identity Continuity Boundary when a write targets a
    protected core path.

    This is a Hard System Halt per RFC-003 §3 T-009.  It is NOT a warning
    and NOT a quarantine event.  The sidecar must treat this as a critical
    alert requiring operator intervention.
    """

    def __init__(
        self,
        protected_path: str,
        detected_hash_delta: str | None = None,
        session_id: str | None = None,
    ):
        self.protected_path = protected_path
        self.detected_hash_delta = detected_hash_delta
        self.session_id = session_id
        super().__init__(
            f"IDENTITY HALT: write to protected core path '{protected_path}' "
            f"(hash delta: {detected_hash_delta or 'unknown'}, "
            f"session: {session_id or 'unknown'})"
        )


class InterceptTimeoutError(CPTError):
    """
    Raised when the watchdog intercept does not resolve within INTERCEPT_TIMEOUT_S.
    The system fails CLOSED — the write is blocked.  (GAP-3 — binding spec.)
    """

    def __init__(self, skill_id: str, timeout_s: float):
        self.skill_id = skill_id
        self.timeout_s = timeout_s
        super().__init__(
            f"CPT intercept timed out after {timeout_s}s for skill '{skill_id}'. "
            f"Write blocked (fail-closed)."
        )


class TenantIsolationError(CPTError):
    """
    Raised when a load or read operation targets a quarantine or active-set
    path belonging to a different tenant.  Extends T-002 coverage into CPT.
    (GAP-10 — binding spec from RFC-003 §6.)
    """

    def __init__(self, requesting_tenant: str, owning_tenant: str, skill_id: str):
        self.requesting_tenant = requesting_tenant
        self.owning_tenant = owning_tenant
        self.skill_id = skill_id
        super().__init__(
            f"Tenant isolation violation: tenant '{requesting_tenant}' attempted "
            f"to access skill '{skill_id}' owned by tenant '{owning_tenant}'"
        )
