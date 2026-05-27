import queue
from .event_bus import EventBus, Event

class Task:
    """Represents a governed unit of execution with SLA priorities and capabilities."""
    def __init__(self, task_id, name, priority, payload, capability=None, max_retries=3):
        self.task_id = task_id
        self.name = name
        self.priority = priority  # 0: Recovery (P0), 1: Validation (P1), 2: Execution (P2), 3: Research (P3)
        self.payload = payload
        self.capability = capability  # planning, research, writing, testing, optimizing, coding, validation
        self.retries = 0
        self.max_retries = max_retries
        self.status = "queued"  # queued, running, completed, failed, escalated

    def __lt__(self, other):
        # High priority (0) will be ordered before low priority (3)
        return self.priority < other.priority

import time

class PriorityTaskQueue:
    """Multi-queue SLA management engine mapping recovery, validation, execution, and research lanes."""
    def __init__(self, telemetry_manager=None):
        # Dedicated priority-weighted queues
        self.queues = {
            0: queue.PriorityQueue(),  # recovery (P0 / SLA: 0 sec)
            1: queue.PriorityQueue(),  # validation (P1 / SLA: 5 sec)
            2: queue.PriorityQueue(),  # execution (P2 / SLA: 30 sec)
            3: queue.PriorityQueue()   # research (P3 / SLA: 300 sec)
        }
        self.registry = {}
        self.event_bus = EventBus()
        self.telemetry = telemetry_manager
        
        # Lifecycle counters
        self.metrics = {
            "task_created": 0,
            "task_started": 0,
            "task_completed": 0,
            "task_requeued": 0,
            "task_orphaned": 0,
            "priority_starvation_count": 0
        }

    def _get_queue_depth(self):
        return sum(q.qsize() for q in self.queues.values())

    def _emit(self, metric_name, value):
        if self.telemetry:
            self.telemetry.emit_metric("queue", metric_name, value)

    def enqueue(self, task):
        """Pushes a task onto its matching SLA priority queue and publishes queue events."""
        task.created_at = time.time()
        self.registry[task.task_id] = task
        p = task.priority
        if p not in self.queues:
            p = 2  # default to execution priority
            task.priority = p
            
        self.queues[p].put((p, task))
        
        self.metrics["task_created"] += 1
        self._emit("task_created", self.metrics["task_created"])
        self._emit("queue_depth", self._get_queue_depth())
        
        # Publish queue event
        self.event_bus.publish(Event(
            event_type="TASK_ENQUEUED",
            correlation_id=task.task_id,
            payload={
                "task_name": task.name,
                "priority": p,
                "capability": task.capability
            }
        ))

    def dequeue(self):
        """Fetches the next highest priority task across recovery -> validation -> execution -> research lanes."""
        for p in sorted(self.queues.keys()):
            if not self.queues[p].empty():
                _, task = self.queues[p].get()
                task.status = "running"
                task.started_at = time.time()
                wait_time_ms = (task.started_at - task.created_at) * 1000
                
                self.metrics["task_started"] += 1
                self._emit("task_started", self.metrics["task_started"])
                self._emit("queue_depth", self._get_queue_depth())
                self._emit("avg_wait_ms", wait_time_ms)
                
                return task
                
        return None

    def requeue_for_retry(self, task):
        """Attempts a retry cycle, promoting the task to the P0 recovery lane, or escalates upon breach."""
        if task.retries < task.max_retries:
            task.retries += 1
            task.status = "queued"
            # Upgrade failing task to recovery queue (Priority 0) for immediate healing priority
            task.priority = 0
            self.queues[0].put((0, task))
            
            self.metrics["task_requeued"] += 1
            self._emit("task_requeued", self.metrics["task_requeued"])
            self._emit("queue_depth", self._get_queue_depth())
            return True
        else:
            task.status = "escalated"
            return False

    def complete_task(self, task):
        """Marks a task as completed."""
        task.status = "completed"
        self.metrics["task_completed"] += 1
        self._emit("task_completed", self.metrics["task_completed"])

    def mark_orphaned(self, task):
        """Marks a task as orphaned if it disappeared quietly during execution."""
        task.status = "orphaned"
        self.metrics["task_orphaned"] += 1
        self._emit("task_orphaned", self.metrics["task_orphaned"])

    def get_task(self, task_id):
        """Retrieves task state and history metadata."""
        return self.registry.get(task_id)
