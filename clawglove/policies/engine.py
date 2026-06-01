"""
Policy enforcement engine.
Checks incoming agent actions against compiled policies.
Must be synchronous and fast — called on every agent action.
Fail-closed: unknown tenant = DENY.
"""
import fnmatch
import logging
from clawglove.interfaces import PolicyEngineInterface
from clawglove.policies.compiler import CompiledPolicy

logger = logging.getLogger(__name__)


class PolicyEngine(PolicyEngineInterface):
    """
    Runtime policy enforcer.
    Loaded once at sidecar startup. Policies are immutable after load.
    To update policies: restart the sidecar with updated policy files.
    """

    def __init__(self, policies: dict[str, CompiledPolicy]):
        self._policies = policies
        logger.info("PolicyEngine loaded: %d tenant policies", len(policies))

    def check(self, action: str, tenant_id: str, context: dict) -> tuple[bool, str]:
        """
        Check if action is allowed for tenant.
        Returns (allowed: bool, reason: str).

        Rules applied in order:
        1. Unknown tenant → DENY
        2. Action name too long (>256 chars) → DENY  [DoS guard]
        3. Explicitly denied action (exact match) → DENY
        4. Action matches a denied_pattern (fnmatch) → DENY  [CG-04]
           Ensures wildcard allow patterns cannot bypass explicit denials.
           e.g. send_exec_shell_command is caught by denied_patterns before
           being allowed by send_*
        5. Token budget exceeded → DENY
        6. Delegation depth exceeded → DENY
        7. Action in allowed set → ALLOW
        8. Action matches allowed_tool_patterns (fnmatch) → ALLOW
        9. Otherwise → DENY
        """
        policy = self._policies.get(tenant_id)
        if policy is None:
            return False, f"Unknown tenant: {tenant_id}. Fail-closed."

        # Rule 2: action name length guard (DoS / abuse prevention)
        if len(action) > 256:
            return False, f"Action name exceeds 256 chars (len={len(action)}). Rejected."

        # Rule 3: explicit deny list (exact match)
        if action in policy.denied_actions:
            return False, f"Action explicitly denied: {action}"

        # Rule 4: fnmatch deny patterns — deny wins even when an allow pattern also matches.
        # This closes the wildcard bypass: send_exec_shell_command would pass send_* without this.
        for denied in policy.denied_actions:
            if "*" in denied or "?" in denied or "[" in denied:
                if fnmatch.fnmatch(action, denied):
                    return False, f"Action denied by pattern: {denied}"

        # Additionally: reject actions whose suffix exactly matches a denied action
        # (e.g. prefix_exec_shell_command is blocked because exec_shell_command is denied).
        for denied in policy.denied_actions:
            if action.endswith(denied) and action != denied:
                return False, f"Action denied: suffix matches denied action '{denied}'"

        # Rule 5: token budget
        tokens_used = context.get("tokens_used", 0)
        if tokens_used > policy.max_token_budget:
            return False, (
                f"Token budget exceeded: used={tokens_used} "
                f"limit={policy.max_token_budget}"
            )

        # Rule 6: delegation depth
        depth = context.get("delegation_depth", 0)
        if depth > policy.max_delegation_depth:
            return False, (
                f"Delegation depth exceeded: depth={depth} "
                f"limit={policy.max_delegation_depth}"
            )

        # Rule 7: allowed actions (exact match)
        if action in policy.allowed_actions:
            return True, "allowed"

        # Rule 8: allowed tool patterns (fnmatch wildcards)
        for pattern in policy.allowed_tool_patterns:
            if fnmatch.fnmatch(action, pattern):
                return True, f"allowed by pattern: {pattern}"

        return False, f"Action not in allowed set: {action}"
