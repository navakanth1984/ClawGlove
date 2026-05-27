from workers.base_pool import BaseWorkerPool


class RecoveryPool(BaseWorkerPool):
    """P0 recovery pool for emergency self-healing and rollback operations.

    Capabilities: all (emergency escalation accepts any task type)
    Priority lane: P0 / Recovery (SLA 0s — immediate)
    Capacity: 2 dedicated workers (deliberately small to keep recovery fast
              and prevent normal workloads from consuming recovery slots)

    The RecoveryPool is isolated on P0 so that self-healing tasks never compete
    with planner, builder, reviewer, or optimizer workloads. When the queue
    requeue_for_retry() promotes a task to P0, it will be served by this pool.
    """

    pool_id = "recovery_pool"
    role = "recovery"
    default_priority = 0   # P0 — highest priority SLA lane
    pool_capacity = 2
