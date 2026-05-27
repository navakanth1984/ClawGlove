# Metrics: Telemetry, Observability & Logs

To ensure transparent agent operations, the system logs execution traces, retries, and errors using standardized structures.

---

## 1. Log Schema for Agent Operations

Every executing subagent must log its lifecycle events using the following structure:

```json
{
  "timestamp": "2026-05-26T14:30:00Z",
  "task_id": "task_abc123",
  "agent_role": "Builder",
  "stage": "Stage 4: Karpathy Development",
  "status": "IN_PROGRESS / SUCCESS / FAILURE",
  "metrics": {
    "tokens_in": 12050,
    "tokens_out": 2100,
    "duration_ms": 4820,
    "tool_calls_count": 3
  },
  "error": null
}
```

---

## 2. Telemetry Triggers & Actions

| Telemetry Event | Trigger Threshold | Required Automated Action |
| :--- | :--- | :--- |
| **High Retries** | Task retried >2 times | Terminate execution pathway; fall back to simple context compression; notify Planner. |
| **High Latency** | Command execution >30,000ms | Halt tool call; inspect process using `manage_task`; report status. |
| **Context Threshold** | Window usage >70% | Trigger **Smart Truncation**; offload memory to persistent store; restart loop. |
| **Hallucination Match** | Regex detection of standard hallucinated code paths | Abort operation; reset builder state; reload context bundle. |

---

## 3. Observation Feedback Loops (Stage 6)
1. **Analyze Failures**: Identify modules with highest retry-count during the build run.
2. **Log Refinement**: Inspect telemetry traces to identify what context or instructions failed to clarify the system requirements.
3. **Continuous Evolution**: If failure count on a module >3 across runs, the master orchestrator must automatically update context priorities in `context-bundle-template.md`.
