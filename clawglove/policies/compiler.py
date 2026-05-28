"""
Policy compiler.
Loads YAML policy definitions at init time and compiles them into
an in-memory rule set. Fail-closed: if a policy file cannot be loaded,
the engine denies all actions until policies are corrected and reloaded.
"""
import logging
import yaml
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CompiledPolicy:
    tenant_id: str
    allowed_actions: set[str]
    denied_actions: set[str]
    max_token_budget: int
    max_delegation_depth: int
    allowed_tool_patterns: list[str]


class PolicyCompiler:
    """
    Compiles YAML policy files into CompiledPolicy objects.

    Expected YAML structure:
        tenant_id: tenant_alpha
        allowed_actions:
          - llm_call
          - tool_use
          - file_read
        denied_actions:
          - file_write_cross_tenant
          - escalate_privileges
        max_token_budget: 100000
        max_delegation_depth: 3
        allowed_tool_patterns:
          - "search_*"
          - "read_*"
    """

    def compile(self, policy_path: str | Path) -> CompiledPolicy:
        path = Path(policy_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Policy file not found: {path}. "
                "Fail-closed: engine will deny all actions."
            )

        with open(path) as f:
            raw = yaml.safe_load(f)

        if not raw:
            raise ValueError(f"Empty policy file: {path}")

        return CompiledPolicy(
            tenant_id=raw["tenant_id"],
            allowed_actions=set(raw.get("allowed_actions", [])),
            denied_actions=set(raw.get("denied_actions", [])),
            max_token_budget=int(raw.get("max_token_budget", 50000)),
            max_delegation_depth=int(raw.get("max_delegation_depth", 3)),
            allowed_tool_patterns=raw.get("allowed_tool_patterns", []),
        )

    def compile_directory(self, policies_dir: str | Path) -> dict[str, CompiledPolicy]:
        """Load all .yaml files in a directory. Returns {tenant_id: CompiledPolicy}."""
        policies_dir = Path(policies_dir)
        compiled = {}
        for policy_file in policies_dir.glob("*.yaml"):
            try:
                policy = self.compile(policy_file)
                compiled[policy.tenant_id] = policy
                logger.info("Policy compiled: tenant=%s file=%s", policy.tenant_id, policy_file.name)
            except Exception as e:
                logger.error("Policy compile error: file=%s err=%s", policy_file, e)
                raise
        return compiled
