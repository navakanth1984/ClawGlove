# Governance: Agent Delegation & Collaboration Rules

To prevent runaway agentic chains, excessive API costs, and context pollution, this document enforces rules for multi-agent delegation.

---

## 1. The Anti-Chaining Rule (Star Topology Enforcement)

### Prohibited (Linear Chaining)
Avoid deep hierarchical execution pathways where errors propagate unchecked and context gets degraded.
```text
[Main Agent] Ã¢Å¾â€ [Subagent A] Ã¢Å¾â€ [Subagent B] Ã¢Å¾â€ [Subagent C] Ã¢Å¾â€ [Subagent D]
```
*Why this fails*: Debugging becomes impossible, costs explode exponentially, and subsequent agents lose track of the core system intent.

### Enforced (Star Topology)
All delegations must be managed via flat, single-depth patterns controlled by a central Planner.
```text
            [Planner Agent]
           /       |       \
     [Researcher] [Builder] [Reviewer]
```
*Benefits*: The Planner maintains the complete system state and can catch, log, and recover from failures instantly.

---

## 2. Delegation Depth & Context Constraints

1. **Max Depth Gate**: Subagents can spawn descendant subagents to a maximum depth of **2**. Any request to spawn a third-tier subagent must be blocked.
2. **Context Independence**: Spawning subagents must utilize isolated, branched workspaces or inherit strict context bundles (Pruning irrelevant long histories). Do not dump the entire workspace logs into subagent configurations.
3. **Objective Isolation**: Each subagent must receive a single, highly focused, machine-verifiable task. (e.g., "Grep for Babel visitor types" instead of "Build the entire parser").

---

## 3. Concrete Policy Definition (`policies/delegation-limits.yaml`)

This machine-enforceable policy is dynamically validated by our policy engine:

```yaml
policy:
  name: Subagent Workforce Delegation Policy
  enforceable: true
  rules:
    max_delegation_tree_depth: 2
    topology_constraint: "star"
    allow_recursive_agent_spawns: false
    force_isolated_subagent_workspace: true
    max_parallel_workers_count: 5
```

