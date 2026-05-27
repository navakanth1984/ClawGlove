# ACDLC Execution Trace Service

The Trace Service, introduced in **ACDLC v1.7**, adds **relationship tracking** to the telemetry warehouse. While the existing warehouse stores individual events, the trace service records the *connections between events* — enabling end-to-end task reconstruction across distributed worker pool boundaries.

## Warehouse Before vs After v1.7

| v1.6 Warehouse | v1.7 Warehouse |
|---|---|
| Individual events | Events + Relationships |
| Point-in-time logs | Causal execution chains |
| Source/severity filtering | Trace-based root-cause analysis |

## Trace Event Structure

Trace files are stored as JSON in this directory, named `{trace_id}_{event_id}.json`:

```json
{
  "schema_name": "trace-event",
  "schema_version": "1.0",
  "trace_id": "trace_abc123",
  "parent_event_id": "evt_001",
  "child_event_id": "evt_002",
  "agent_id": "builder_001",
  "tenant_id": "default",
  "session_id": "session_xyz",
  "routing_decision_id": "evt_route_001",
  "timestamp": "2026-05-27T00:00:00Z",
  "span_type": "child",
  "duration_ms": 342,
  "status": "COMPLETED"
}
```

## Span Types

| Type | Description |
|---|---|
| `root` | The originating task span (first event in the chain) |
| `child` | An intermediate delegation or pool submission event |
| `leaf` | A terminal execution event (no further children) |

## Forensic Fields (v1.7)

- **`session_id`**: Groups all traces within a single user or pipeline session
- **`routing_decision_id`**: Links the trace span back to the `ROUTE_SELECTED` event that assigned the agent, enabling post-hoc routing quality analysis

## Observability Use Cases

```text
Execution Replay:
    Reconstruct task execution order from parent → child chains

Root-Cause Analysis:
    Walk child → parent until the root span, locate the failure origin

Latency Tracing:
    Sum duration_ms across spans for end-to-end task latency

Distributed Debugging:
    Correlate spans across different worker pools using trace_id

Routing Quality Audit:
    Join routing_decision_id with ROUTE_SELECTED warehouse events
    to evaluate whether the routing engine made optimal decisions
```

## Integration

The State Manager writes trace JSON files here when it processes `ROUTE_SELECTED` events that chain to `POOL_TASK_COMPLETED` events. The schema is validated against `schemas/trace-event.json`.
