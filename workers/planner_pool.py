from workers.base_pool import BaseWorkerPool


class PlannerPool(BaseWorkerPool):
    """Planner-specialized worker pool.

    Primary capabilities: planning, validation
    Priority lane: P2 / Execution (SLA 30s)
    Capacity: 4 concurrent workers
    """

    pool_id = "planner_pool"
    role = "planner"
    default_priority = 2
    pool_capacity = 4
