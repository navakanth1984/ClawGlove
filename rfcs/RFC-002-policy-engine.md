# RFC-002: Machine-Enforceable Policy Engine

- **Author**: Platform Architect
- **Status**: APPROVED
- **Version Target**: ACDLC v1.3

---

## 1. Problem Space
Implicit execution guidelines are easily ignored by LLMs and builder agents. Enforcing bounds (like token ceilings, tree depth, and budget spent ratios) directly in markdown triggers comprehension drift.

## 2. Proposed System
Isolate operational controls under a central `policies/` directory.

### Structural Manifestations
- `token-limits.yaml`: Rule limits for context memory caps.
- `delegation-limits.yaml`: Flat star topologies and maximum subagent depth bounds.
- `budget-limits.yaml`: Reasoning economics thresholds.

## 3. Benefits
- Framework rules become programmatically parseable.
- Integrates with active automated pipeline validators (`validate_policies.py`).
- Prevents token explosions and recursive loop hazards dynamically.
