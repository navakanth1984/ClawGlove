# Workflows: Stage 3 - Controlled Execution

Uncontrolled agents can exhaust token limits, spin into infinite loops, and rack up excessive API costs. Stage 3 acts as the protective runtime governor.

## Ã°Å¸â€ºÂ Ã¯Â¸ Step-by-Step Execution Plan

### Step 1: Task Scheduling
1. **Parallel Execution**: Execute independent subtasks (e.g. parallel research steps) concurrently.
2. **Dependency Management**: Ensure that parent tasks complete fully before launching dependent downstream tasks.

### Step 2: Resource and Budget Monitoring
1. **Token Tracking**: Track total cumulative input/output tokens used during the active session.
2. **Reasoning Economics Gates**: Match model reasoning capabilities to task complexity (refer to `SKILL.md` Reasoning Economics table). Prevent using expensive models for trivial syntax edits.

### Step 3: Loop & Failure Recovery
1. **Detect Infinite Loops**: If a subagent makes >3 consecutive edits/attempts yielding the exact same error, halt execution.
2. **Failure Analysis**:
   - Stop and read the exact failure log.
   - Run a diagnostic prompt to check for missing imports, syntax bugs, or conflicting package versions.
3. **Execution Fallback**: 
   - Fall back to a simpler step.
   - De-escalate model logic (e.g., from complex agent loops to a single comprehensive code write).
   - If recovery fails, abort and notify the user with a detailed summary.

---

## Ã°Å¸â€â€™ Transition Gate to Stage 4
You **CANNOT** proceed to Stage 4 until:
- [ ] Task scheduling pathways are mapped.
- [ ] Reasoning economics budgets are evaluated and verified.
- [ ] Run state safety boundaries (retry counters, token monitors) are active.
