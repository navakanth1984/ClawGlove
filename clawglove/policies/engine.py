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
        2. Explicitly denied action → DENY
        3. Token budget exceeded → DENY
        4. Delegation depth exceeded → DENY
        5. Action not in allowed set and not matching allowed_tool_patterns → DENY
        6. Otherwise → ALLOW
        """
        policy = self._policies.get(tenant_id)
        if policy is None:
            return False, f"Unknown tenant: {tenant_id}. Fail-closed."

        # Rule 2: explicit deny list
        if action in policy.denied_actions:
            return False, f"Action explicitly denied: {action}"

        # Rule 3: token budget
        tokens_used = context.get("tokens_used", 0)
        if tokens_used > policy.max_token_budget:
            return False, (
                f"Token budget exceeded: used={tokens_used} "
                f"limit={policy.max_token_budget}"
            )

        # Rule 4: delegation depth
        depth = context.get("delegation_depth", 0)
        if depth > policy.max_delegation_depth:
            return False, (
                f"Delegation depth exceeded: depth={depth} "
                f"limit={policy.max_delegation_depth}"
            )

        # Rule 5: allowed actions and patterns
        if action in policy.allowed_actions:
            return True, "allowed"

        for pattern in policy.allowed_tool_patterns:
            if fnmatch.fnmatch(action, pattern):
                return True, f"allowed by pattern: {pattern}"

        return False, f"Action not in allowed set: {action}"
