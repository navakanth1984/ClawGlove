from workers.base_pool import BaseWorkerPool


class BuilderPool(BaseWorkerPool):
    """Builder-specialized worker pool.

    Primary capabilities: coding, writing, testing
    Priority lane: P2 / Execution (SLA 30s)
    Capacity: 6 concurrent workers (largest pool; builders handle most workload)
    """

    pool_id = "builder_pool"
    role = "builder"
    default_priority = 2
    pool_capacity = 6
