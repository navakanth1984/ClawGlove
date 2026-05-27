# Metrics: Reasoning Economics & Cost Control

This document defines the budgeting and token conservation guidelines under the Reasoning Economics model.

---

## 1. Intelligence Routing Matrix

To prevent the "Reasoning Waste" phenomenon (using deep reasoning models on low-complexity syntax edits), the system allocates tasks based on the following schedule:

```mermaid
graph TD
    Task[Incoming Task] --> Identify{Complexity}
    Identify -->|Simple / Low| Flash[Gemini 3.5 Flash / Fast Model]
    Identify -->|Moderate| Balanced[Gemini 3.5 Sonnet / Pro - Direct run]
    Identify -->|Complex| Reasoning[Gemini 3.1 Pro / deep reasoning models]
    Identify -->|Research| Parallel[Planner + Parallel Subagents]
```

---

## 2. Token Conservation & Budgeting Guidelines

### Financial Budget Targets
- **Simple Feature**: <$0.10 total API spend.
- **Moderate Integration**: <$0.50 total API spend.
- **Complex System Launch**: <$2.00 total API spend.

### Execution Loop Limits (Safety Constraints)
1. **Loop Depth**: No execution path may invoke subagents >3 tiers deep.
2. **Subagent Limit**: Max 5 parallel subagents can be active for a research task to conserve token usage.
3. **Runaway Guard**: Max **10 sequential tool calls** per subagent. If a task exceeds 10 tool calls, it must pause, summarize its state, and request input from the Planner or User.

---

## 3. Optimizing Context Consumption
1. **Smart Truncation Rule**: Preserve the first **1000 characters** (system instruction and global rules) and the last **1000 characters** (latest errors, recent state results). Compress and truncate the large middle content.
2. **File Reading Standard**: Use targeted lines range reads (`StartLine`, `EndLine` parameters in `view_file`) instead of loading entire multi-hundred line files repeatedly.
