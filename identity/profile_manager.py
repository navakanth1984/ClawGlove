import re

VALID_ROLES = {"planner", "researcher", "builder", "reviewer", "optimizer"}
VALID_TRUST_LEVELS = {"high", "standard", "restricted"}
VALID_COMPETENCY_LEVELS = {"expert", "advanced", "intermediate", "standard"}
AGENT_ID_PATTERN = re.compile(r"^[a-z0-9_-]+_[0-9]+$")


class ProfileManager:
    """Constructs and validates AgentProfile objects.

    All produced profiles conform to schemas/agent-profile.json including
    the agent_id pattern constraint (role_NNN format).
    """

    def build(self, agent_id, name, role, capabilities,
              trust_level, tenant_id="default"):
        """Creates a validated AgentProfile dict ready for IdentityRegistry.

        Args:
            agent_id:     Unique identifier in pattern role_NNN (e.g. builder_001)
            name:         Human-readable display name
            role:         One of planner/researcher/builder/reviewer/optimizer
            capabilities: Dict mapping capability name → competency level
            trust_level:  One of high/standard/restricted
            tenant_id:    Execution tenant context (default: "default")

        Returns:
            dict: Validated AgentProfile

        Raises:
            ValueError: If any field fails validation
        """
        if not AGENT_ID_PATTERN.match(agent_id):
            raise ValueError(
                f"Invalid agent_id format '{agent_id}'. Expected pattern: <name>_<digits>  (e.g. builder_001)"
            )
        if role not in VALID_ROLES:
            raise ValueError(f"Invalid role '{role}'. Must be one of: {sorted(VALID_ROLES)}")
        if trust_level not in VALID_TRUST_LEVELS:
            raise ValueError(f"Invalid trust_level '{trust_level}'. Must be one of: {sorted(VALID_TRUST_LEVELS)}")
        for cap, level in capabilities.items():
            if level not in VALID_COMPETENCY_LEVELS:
                raise ValueError(
                    f"Invalid competency level '{level}' for capability '{cap}'. "
                    f"Must be one of: {sorted(VALID_COMPETENCY_LEVELS)}"
                )

        return {
            "schema_name": "agent-profile",
            "schema_version": "1.0",
            "agent_id": agent_id,
            "name": name,
            "role": role,
            "capabilities": capabilities,
            "trust_level": trust_level,
            "tenant_id": tenant_id,
            # Runtime-mutable counters used by TrustEngine and ReputationEngine
            "_policy_violations": 0,
            "_recent_successes": 0
        }

    def validate(self, profile):
        """Validates that a profile dict contains all required fields.

        Returns:
            True if valid

        Raises:
            ValueError: listing missing required fields
        """
        required = ["agent_id", "name", "role", "capabilities", "trust_level"]
        missing = [f for f in required if f not in profile]
        if missing:
            raise ValueError(f"Profile missing required fields: {missing}")
        return True
