from workers.base_pool import BaseWorkerPool


class OptimizerPool(BaseWorkerPool):
    """Optimizer-specialized worker pool.

    Primary capabilities: optimizing, coding
    Priority lane: P2 / Execution (SLA 30s)
    Capacity: 3 concurrent workers
    """

    pool_id = "optimizer_pool"
    role = "optimizer"
    default_priority = 2
    pool_capacity = 3
