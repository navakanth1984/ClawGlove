"""
CGBench Trust Surface Discovery.
Non-destructive X-Ray scan of the active workspace.
Maps transitive trust dependencies and computes S_exposure.

Fixed from Gemini's version:
  - unverified_skills_count is now computed from actual policy files,
    not hardcoded to 1 (which made the score partially fabricated)
  - The ASCII map marks real scan findings, not template strings
"""
import os
import json
import logging
from pathlib import Path

logger = logging.getLogger("cgbench.discovery")

# Approved outbound LLM endpoints — anything else is an exposure
APPROVED_ENDPOINTS = {
    "api.sarvam.ai",
    "api.anthropic.com",    # Only if policy explicitly permits
}

# Config files that must be read-only at runtime
GOVERNANCE_BOUNDARY_FILES = [
    "openclaw.json",
    "SOUL.md",
    "AGENTS.md",
]

# Env var patterns that indicate raw secrets in environment
SECRET_ENV_PATTERNS = [
    "API_KEY", "API_SECRET", "ACCESS_TOKEN", "PRIVATE_KEY",
    "SARVAM_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
]


class TrustSurfaceDiscovery:
    """
    Non-destructive scanner. Reads permissions and config files.
    Does NOT write, execute, or modify anything.
    """

    def __init__(self, workspace_path: str = "."):
        self.workspace_path = os.path.abspath(workspace_path)

    def scan(self) -> dict:
        """
        Returns:
          configs_writeable        int   — governance boundary files with w permission
          unverified_skills_count  int   — skills without policy approval (real count)
          exposed_secrets_detected int   — raw API keys found in environment
          surface_exposure_score   float — 0.0 (locked) to 1.0 (fully exposed)
          ascii_map                str   — visual dependency tree
        """
        logger.info("Trust Surface Discovery scan: %s", self.workspace_path)

        # ── 1. Check governance boundary file permissions ────────────────────
        configs_writeable = 0
        config_findings = {}

        for filename in GOVERNANCE_BOUNDARY_FILES:
            # Check common locations
            candidates = [
                Path(self.workspace_path) / filename,
                Path("c:/Users/navka/navakanth001/openclaw_sandbox") / filename,
                Path("c:/Users/navka/navakanth001/ClawGlove") / filename,
            ]
            found = False
            for p in candidates:
                if p.exists():
                    found = True
                    writeable = os.access(str(p), os.W_OK)
                    if writeable:
                        configs_writeable += 1
                    config_findings[filename] = {
                        "found": True,
                        "writeable": writeable,
                        "path": str(p),
                    }
                    break
            if not found:
                # File doesn't exist yet — cannot verify it's locked
                configs_writeable += 1
                config_findings[filename] = {"found": False, "writeable": True}

        # ── 2. Count unverified skills (real scan of policies/ directory) ────
        unverified_skills = []
        approved_skills = []

        policies_dir = Path(self.workspace_path) / "policies"
        if policies_dir.exists():
            for policy_file in policies_dir.glob("*.yaml"):
                try:
                    import yaml
                    with open(policy_file) as f:
                        policy = yaml.safe_load(f)
                    # Skills in denied_actions list mean they're recognized but blocked
                    # Skills NOT in any policy list are unverified
                    allowed = set(policy.get("allowed_actions", []))
                    denied  = set(policy.get("denied_actions",  []))
                    skill_entries = [a for a in allowed | denied if "skill" in a.lower()]
                    for skill in skill_entries:
                        if "approved" in skill.lower():
                            approved_skills.append(skill)
                        elif "unverified" in skill.lower():
                            unverified_skills.append(skill)
                except Exception as e:
                    logger.debug("Could not parse %s: %s", policy_file, e)

        unverified_skills_count = len(unverified_skills)

        # ── 3. Check environment for raw secrets ─────────────────────────────
        exposed_secrets = []
        for key, value in os.environ.items():
            for pattern in SECRET_ENV_PATTERNS:
                if pattern in key.upper() and value:
                    exposed_secrets.append(key)
                    break

        exposed_secrets_detected = len(exposed_secrets)

        # ── 4. Compute S_exposure ─────────────────────────────────────────────
        # Weights: config writeability is the most critical exposure vector
        raw = (
            configs_writeable    * 0.05 +   # each writable config boundary = 5%
            unverified_skills_count * 0.04 + # each unverified skill = 4%
            exposed_secrets_detected * 0.02  # each raw env secret = 2%
        )
        surface_exposure_score = min(1.0, max(0.0, raw))

        ascii_map = self._build_map(config_findings, unverified_skills,
                                    approved_skills, exposed_secrets)

        return {
            "configs_writeable":        configs_writeable,
            "unverified_skills_count":  unverified_skills_count,
            "exposed_secrets_detected": exposed_secrets_detected,
            "surface_exposure_score":   surface_exposure_score,
            "ascii_map":                ascii_map,
        }

    def _build_map(self, config_findings, unverified_skills,
                   approved_skills, exposed_secrets) -> str:
        lines = [
            "",
            "=" * 72,
            "  CGBENCH X-RAY WORKSPACE TRUST SURFACE MAP",
            "=" * 72,
            "  Principal Agent",
            "  ├── Workspace Config Boundaries",
        ]

        for filename, info in config_findings.items():
            if info.get("writeable"):
                status = f"RISK: writable at {info.get('path', 'path unknown')}"
            elif not info.get("found"):
                status = "RISK: file not found — cannot verify lock"
            else:
                status = f"OK: read-only at {info.get('path', '')}"
            lines.append(f"  │    ├── {filename:20s} [{status}]")

        lines.append("  ├── Installed Skills")
        for skill in approved_skills:
            lines.append(f"  │    ├── {skill:30s} [approved]")
        for skill in unverified_skills:
            lines.append(f"  │    └── {skill:30s} [UNVERIFIED]")
        if not approved_skills and not unverified_skills:
            lines.append("  │    └── (no skills found in policy scan)")

        lines.append("  └── Environment Secrets")
        if exposed_secrets:
            for key in exposed_secrets:
                lines.append(f"       └── {key} [RISK: raw secret in env]")
        else:
            lines.append("       └── [OK: no raw secrets detected in env]")

        lines.append("=" * 72)
        return "\n".join(lines)
