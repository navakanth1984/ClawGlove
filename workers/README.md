# ACDLC Distributed Worker Pools

Worker pools are the execution layer of the **ACDLC v1.7 Agent OS Core**. Each pool is role-specialized, isolating workload classes from each other to prevent resource contention and enabling the routing engine to target pools with precision.

## Pool Architecture

```text
RoutingEngine
      ↓  (selects pool by required_capability + score)
BaseWorkerPool  ← abstract shared interface
      ├── PlannerPool    (planning, validation)
      ├── BuilderPool    (coding, writing, testing)
      ├── ReviewerPool   (validation, writing)
      ├── OptimizerPool  (optimizing, coding)
      └── RecoveryPool   (all — P0 emergency escalation)
```

## Priority Lane Alignment

| Pool | Role | Priority Lane | SLA |
|---|---|---|---|
| `PlannerPool` | planner | P2 / Execution | 30s |
| `BuilderPool` | builder | P2 / Execution | 30s |
| `ReviewerPool` | reviewer | P1 / Validation | 5s |
| `OptimizerPool` | optimizer | P2 / Execution | 30s |
| `RecoveryPool` | recovery | **P0 / Recovery** | **0s** |

`RecoveryPool` is deliberately isolated on the P0 lane, preventing self-healing tasks from competing with normal execution workloads.

## Events Published

All pools publish the following events to the platform Event Bus:

| Event | Trigger |
|---|---|
| `POOL_TASK_SUBMITTED` | Task accepted into pool |
| `POOL_TASK_COMPLETED` | Task execution finished |
| `POOL_CAPACITY_WARNING` | Active tasks ≥ pool_capacity |

## Load Reporting

Each pool exposes `get_load()` returning a `[0.0, 1.0]` utilisation ratio consumed by `RoutingEngine.route()` during candidate scoring.

## Adding New Pools

1. Subclass `BaseWorkerPool` in a new file
2. Set `pool_id`, `role`, `default_priority`, `pool_capacity`
3. Register the new file in `manifest.yaml`
