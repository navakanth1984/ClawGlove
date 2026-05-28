"""
Threat escalation tracker.
Monitors per-tenant violation counts and escalates to quarantine mode
when a tenant exhibits repeated escape-boundary behaviour.

This is the mechanism that reduces H_escape below 1.0 bits (the G-4 gate):
- Escape attempt 1, 2: individual PolicyViolationError raised, logged
- Escape attempt 3+: tenant enters QUARANTINE mode
  → all actions denied regardless of policy (including clean actions)
  → escape path diversity collapses to one outcome: quarantine_block
  → Shannon entropy over escape paths drops because all paths converge

Real-world rationale: an agent probing exec_shell_command then
read_credentials_dir then cross_tenant_file_read in the same session
is exhibiting reconnaissance behaviour. Individual blocks are not enough.
Quarantine isolates the tenant until a human operator resets the state.

Operator reset:
  from clawglove.sidecar.escalation import ThreatEscalationTracker
  tracker = ThreatEscalationTracker()
  tracker.reset_tenant("screenwriter")
"""
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("clawglove.escalation")


class ThreatLevel(Enum):
    NORMAL      = "normal"       # 0–2 violations: individual blocks
    ELEVATED    = "elevated"     # 3–5 violations: extra logging, operator alert
    QUARANTINE  = "quarantine"   # 6+  violations: all actions denied


@dataclass
class TenantThreatState:
    tenant_id: str
    violation_count: int = 0
    level: ThreatLevel = ThreatLevel.NORMAL
    first_violation_ts: float = 0.0
    last_violation_ts: float = 0.0
    violation_actions: list = field(default_factory=list)   # history of denied actions


class ThreatEscalationTracker:
    """
    Thread-safe per-tenant violation tracker.
    Injected into the PolicyEngine and consulted on every check().

    Thresholds:
      ELEVATED    after ELEVATED_THRESHOLD violations
      QUARANTINE  after QUARANTINE_THRESHOLD violations

    Session reset: violations decay to zero after DECAY_WINDOW_SECONDS
    of clean activity (no violations). This allows temporary probing to
    not permanently quarantine a misbehaving agent.
    """

    ELEVATED_THRESHOLD    = 3
    QUARANTINE_THRESHOLD  = 6
    DECAY_WINDOW_SECONDS  = 300   # 5 minutes of clean operation resets count

    def __init__(self):
        self._states: dict[str, TenantThreatState] = {}
        self._lock = threading.Lock()

    def _get_or_create(self, tenant_id: str) -> TenantThreatState:
        if tenant_id not in self._states:
            self._states[tenant_id] = TenantThreatState(tenant_id=tenant_id)
        return self._states[tenant_id]

    def record_violation(self, tenant_id: str, action: str) -> ThreatLevel:
        """
        Record a policy violation for tenant and return the new threat level.
        Called by the daemon after a PolicyViolationError is raised.
        """
        with self._lock:
            state = self._get_or_create(tenant_id)
            now = time.time()

            if state.violation_count == 0:
                state.first_violation_ts = now

            state.violation_count += 1
            state.last_violation_ts = now
            state.violation_actions.append(action)

            # Determine new level
            if state.violation_count >= self.QUARANTINE_THRESHOLD:
                if state.level != ThreatLevel.QUARANTINE:
                    logger.warning(
                        "QUARANTINE: tenant=%s violations=%d — all actions denied until operator reset",
                        tenant_id, state.violation_count
                    )
                state.level = ThreatLevel.QUARANTINE
            elif state.violation_count >= self.ELEVATED_THRESHOLD:
                if state.level == ThreatLevel.NORMAL:
                    logger.warning(
                        "ELEVATED: tenant=%s violations=%d — operator review recommended",
                        tenant_id, state.violation_count
                    )
                state.level = ThreatLevel.ELEVATED
            else:
                state.level = ThreatLevel.NORMAL

            return state.level

    def check_quarantine(self, tenant_id: str) -> tuple[bool, str]:
        """
        Check if tenant is in quarantine before policy engine runs.
        Returns (quarantined: bool, reason: str).
        Called at the START of every policy check.

        Also applies decay: if DECAY_WINDOW_SECONDS have passed since the
        last violation, the violation count is reset to 0.
        """
        with self._lock:
            state = self._get_or_create(tenant_id)

            # Apply decay if tenant has been clean for DECAY_WINDOW_SECONDS
            if (state.violation_count > 0
                    and state.last_violation_ts > 0
                    and (time.time() - state.last_violation_ts) > self.DECAY_WINDOW_SECONDS):
                logger.info(
                    "Decay reset: tenant=%s violations cleared after %ds clean window",
                    tenant_id, self.DECAY_WINDOW_SECONDS
                )
                state.violation_count = 0
                state.level = ThreatLevel.NORMAL
                state.violation_actions.clear()

            if state.level == ThreatLevel.QUARANTINE:
                return True, (
                    f"Tenant '{tenant_id}' is in QUARANTINE after "
                    f"{state.violation_count} policy violations. "
                    f"Operator reset required. "
                    f"Attack sequence: {state.violation_actions[-5:]}"
                )

            return False, ""

    def get_state(self, tenant_id: str) -> dict:
        """Return current threat state for a tenant (for telemetry/audit)."""
        with self._lock:
            s = self._get_or_create(tenant_id)
            return {
                "tenant_id": s.tenant_id,
                "level": s.level.value,
                "violation_count": s.violation_count,
                "violation_actions": list(s.violation_actions),
                "first_violation_ts": s.first_violation_ts,
                "last_violation_ts": s.last_violation_ts,
            }

    def reset_tenant(self, tenant_id: str) -> None:
        """
        Operator reset: clear quarantine for a tenant.
        Should only be called after human review of the violation log.
        """
        with self._lock:
            if tenant_id in self._states:
                del self._states[tenant_id]
                logger.info("Operator reset: tenant=%s quarantine cleared", tenant_id)

    def all_states(self) -> dict[str, dict]:
        """Return threat state for all active tenants (for dashboard/audit)."""
        with self._lock:
            return {tid: self.get_state(tid) for tid in self._states}
