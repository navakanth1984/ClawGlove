# Workflows: Stage 2 - Agentic Engineering

Establishing a highly collaborative, isolated, and well-governed workforce.

## Ã°Å¸â€ºÂ Ã¯Â¸ Step-by-Step Execution Plan

### Step 1: Agent Role Definition
Identify which specialized agent roles are needed to accomplish the target milestone.
1. **Planner**: Tracks system state, manages overall milestones, and routes tasks.
2. **Researcher**: Reads files, Traverses knowledge graphs (`graphify`), and fetches documentation.
3. **Builder**: Modifies/writes files, executes compilations, runs CLI commands.
4. **Reviewer**: Evaluates code correctness and runs tests independently.
5. **Optimizer**: Identifies refactoring and performance bottlenecks.

### Step 2: Establish the Flat Delegation Star (Star Topology)
Do not chain agents deep (e.g. Agent A asks Agent B, who asks Agent C, who asks Agent D). Chaining degrades context, accumulates errors, and is difficult to debug.
Instead, use a star layout where a **Planner** controls individual workers:

```text
       [Planner Agent]
        /      |      \
 [Researcher] [Builder] [Reviewer]
```

### Step 3: Tool Boundary Mapping
For each active subagent, map its exact tool access bounds:

| Role | Allowed Tool Types | Prohibited Tool Types |
| :--- | :--- | :--- |
| **Researcher** | `view_file`, `grep_search`, `graphify` | `write_to_file`, `replace_file_content`, command execution |
| **Builder** | `write_to_file`, `replace_file_content`, execution tools | Long-running non-essential terminal execution |
| **Reviewer** | Test execution commands (`run_command`), lint tools | Direct file writing/editing tools |
| **Optimizer** | Code inspection, profiling command tools | Modifying core functionality |

---

## Ã°Å¸â€â€™ Transition Gate to Stage 3
You **CANNOT** proceed to Stage 3 until:
- [ ] The **Execution Graph** (roles, objectives, and bounds) is formulated.
- [ ] Clean delegation pathways are established with isolated context bounds.
