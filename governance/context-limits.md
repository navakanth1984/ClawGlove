# Governance: Context Window Management & Memory Limits

This document establishes the operational boundaries to prevent context window saturation and the "vicious loop" of data growth.

---

## 1. Context Window Usage Limits

| Agent Role | Target Context Limit | Absolute Threshold (Abort Gate) | Smart Truncation Action |
| :--- | :--- | :--- | :--- |
| **Main Orchestrator** | <40% (lean) | >70% | Truncate middle; offload history to persistent memory. |
| **Researcher Subagent** | <60% | >80% | Apply deep compression; filter out non-essential docs. |
| **Builder Subagent** | <50% | >75% | Target specific code ranges (`StartLine`, `EndLine`). |
| **Reviewer Subagent** | <30% | >60% | Focus on test traces and compile logs only. |

---
# Governance: Context Window Management & Memory Limits

This document establishes the operational boundaries to prevent context window saturation and the "vicious loop" of data growth.

---

## 1. Context Window Usage Limits

| Agent Role | Target Context Limit | Absolute Threshold (Abort Gate) | Smart Truncation Action |
| :--- | :--- | :--- | :--- |
| **Main Orchestrator** | <40% (lean) | >70% | Truncate middle; offload history to persistent memory. |
| **Researcher Subagent** | <60% | >80% | Apply deep compression; filter out non-essential docs. |
| **Builder Subagent** | <50% | >75% | Target specific code ranges (`StartLine`, `EndLine`). |
| **Reviewer Subagent** | <30% | >60% | Focus on test traces and compile logs only. |

---

## 2. Smart Truncation Protocol

When context consumption triggers the **Smart Truncation Threshold (>70%)**:
1. **Preserve Head**: Keep the first **1000 characters** containing core system instructions, global goals, and safety parameters.
2. **Preserve Tail**: Keep the last **1000 characters** capturing the latest tool results, execution state, and exact error responses.
3. **Prune & DB Offload**: Compress the bulky middle conversational steps and log history, offload them to database memory logs, and assign a unique retrieval ID (`memory_id_xxx`).
4. **Agent-Driven Retrieval**: If the orchestrator requires past transaction history details, it must execute a targeted lookup query using the specific `memory_id` rather than loading the whole history back into the window.

---

## 3. Concrete Policy Definition (`policies/token-limits.yaml`)

This machine-enforceable policy is dynamically validated by our policy engine:

```yaml
policy:
  name: Token Consumption Limits Policy
  enforceable: true
  rules:
    active_token_ceiling: 250000
    smart_truncation_trigger_ratio: 0.70
    prune_history_on_subagent_branch: true
    allow_unlimited_context_window: false
```
