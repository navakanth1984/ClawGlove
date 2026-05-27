import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.event_bus import EventBus, Event
from runtime.worker import ExecutionWorker


class BaseWorkerPool:
    """Abstract worker pool base providing a shared execution interface.

    Subclasses set pool_id, role, default_priority, and pool_capacity as
    class attributes. The submit() method instantiates an ExecutionWorker
    per task and tracks active concurrency for load reporting.

    All pools publish POOL_TASK_SUBMITTED, POOL_TASK_COMPLETED, and
    POOL_CAPACITY_WARNING events to the platform Event Bus.
    """

    pool_id = "base_pool"
    role = "base"
    default_priority = 2    # P2 execution by default
    pool_capacity = 4       # Maximum simultaneous active workers

    def __init__(self, policies=None):
        """
        Args:
            policies: Override policy dict (defaults to platform standard limits)
        """
        self._policies = policies or {
            "active_token_ceiling": 250000,
            "max_tool_calls_sequence_limit": 10,
            "allow_recursive_agent_spawns": False
        }
        self._active_count = 0
        self._event_bus = EventBus()

    def submit(self, task):
        """Accepts a Task and executes it via a governed ExecutionWorker.

        Publishes POOL_CAPACITY_WARNING if at capacity before accepting.
        Returns worker execution result dict.
        """
        if self._active_count >= self.pool_capacity:
            print(f"[{self.pool_id.upper()}] Capacity warning: "
                  f"{self._active_count}/{self.pool_capacity} slots active.")
            self._event_bus.publish(Event(
                event_type="POOL_CAPACITY_WARNING",
                correlation_id=task.task_id,
                source=f"workers/{self.pool_id}",
                severity="warning",
                payload={
                    "pool": self.pool_id,
                    "active": self._active_count,
                    "capacity": self.pool_capacity
                }
            ))

        self._active_count += 1
        worker_label = f"{self.pool_id.upper()}-{self._active_count:03d}"
        worker = ExecutionWorker(worker_id=worker_label, policies=self._policies)

        self._event_bus.publish(Event(
            event_type="POOL_TASK_SUBMITTED",
            correlation_id=task.task_id,
            source=f"workers/{self.pool_id}",
            severity="info",
            payload={"pool": self.pool_id, "task_name": task.name, "worker": worker_label}
        ))

        result = worker.execute(task)
        self._active_count = max(0, self._active_count - 1)

        self._event_bus.publish(Event(
            event_type="POOL_TASK_COMPLETED",
            correlation_id=task.task_id,
            source=f"workers/{self.pool_id}",
            severity="info",
            payload={"pool": self.pool_id, "status": result.get("status")}
        ))

        return result

    def get_load(self):
        """Returns current utilisation ratio [0.0, 1.0]."""
        return round(self._active_count / self.pool_capacity, 3)

    def get_pool_id(self):
        """Returns this pool's identifier string."""
        return self.pool_id
