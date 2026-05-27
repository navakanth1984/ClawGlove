from workers.base_pool import BaseWorkerPool


class ReviewerPool(BaseWorkerPool):
    """Reviewer-specialized worker pool.

    Primary capabilities: validation, writing
    Priority lane: P1 / Validation (SLA 5s) — faster SLA than execution pools
    Capacity: 3 concurrent workers
    """

    pool_id = "reviewer_pool"
    role = "reviewer"
    default_priority = 1   # P1 Validation SLA lane
    pool_capacity = 3
