from .event_bus import EventBus, Event

class Scheduler:
    """Orchestrates multi-queue schedules, capability-based routing, and preemption safety."""
    def __init__(self, max_concurrency=5, topology="star"):
        self.max_concurrency = max_concurrency
        self.topology = topology
        self.active_jobs = {}
        self.dependencies = {}  # task_id -> list of task_ids it depends on
        self.completed_tasks = set()
        self.event_bus = EventBus()
        self.skill_registry = None  # Reference to service catalog active skills list

    def set_registry(self, skill_registry):
        """Sets active skill catalog to resolve capability routing queries."""
        self.skill_registry = skill_registry

    def register_task(self, task_id, dependencies=None):
        """Maps a task and its parent dependencies inside the active scheduler."""
        self.dependencies[task_id] = dependencies or []
        print(f"[SCHEDULER] Registered task '{task_id}' with parent dependencies: {self.dependencies[task_id]}")
        
        self.event_bus.publish(Event(
            event_type="TASK_REGISTERED",
            correlation_id=task_id,
            source="runtime/scheduler",
            severity="info",
            payload={"dependencies": self.dependencies[task_id]}
        ))

    def verify_topology_compliance(self, task_id, delegation_tree_depth):
        """Enforces star workforce routing bounds (rejecting deep chaining)."""
        if self.topology == "star" and delegation_tree_depth > 1:
            print(f"[SCHEDULER] Safety Warning: Star topology compliance breach at '{task_id}' (Depth: {delegation_tree_depth}).")
            
            # Publish delegation violation event to Bus (severity warning from policy_engine)
            self.event_bus.publish(Event(
                event_type="DELEGATION_VIOLATION",
                correlation_id=task_id,
                source="policy_engine",
                severity="warning",
                payload={"depth": delegation_tree_depth}
            ))
            return False
        return True

    def find_capable_skill(self, required_capability):
        """Dynamic capability lookup routing against active registry skills, matching dynamic level-maps."""
        if not self.skill_registry:
            print(f"[SCHEDULER] Skill catalog registry empty. Capability routing failed.")
            return None
        
        # Traverse catalog registry skills to match requested capabilities (checking level map dictionary)
        for skill in self.skill_registry:
            caps = skill.get("capabilities", {})
            # Supports both dictionary-based capability levels (expert/advanced) and older flat list formats
            if isinstance(caps, dict) and required_capability in caps:
                level = caps[required_capability]
                print(f"[SCHEDULER] Capability '{required_capability}' [{level}] routed to skill '{skill['id']}'.")
                return skill
            elif isinstance(caps, list) and required_capability in caps:
                print(f"[SCHEDULER] Capability '{required_capability}' routed successfully to skill '{skill['id']}'.")
                return skill
                
        print(f"[SCHEDULER] No skill found matching required capability: '{required_capability}'")
        return None

    def get_runnable_tasks(self, queue_manager):
        """Yields tasks whose parent dependencies have completed successfully, sorted by priority SLA lanes."""
        runnable = []
        if len(self.active_jobs) >= self.max_concurrency:
            print(f"[SCHEDULER] Concurrency block. Concurrency limit ({self.max_concurrency}) active.")
            return runnable

        for task_id, deps in self.dependencies.items():
            if task_id in self.completed_tasks or task_id in self.active_jobs:
                continue

            # Verify parent dependency resolutions
            if all(dep in self.completed_tasks for dep in deps):
                task = queue_manager.get_task(task_id)
                if task and task.status == "queued":
                    runnable.append(task)

        # Sort tasks by priority (0: Highest Priority Recovery, 3: Lowest Priority Research) to enforce SLA preemption
        runnable.sort(key=lambda t: t.priority)
        return runnable

    def mark_started(self, task_id):
        """Updates active execution counters and publishes scheduled execution events."""
        self.active_jobs[task_id] = "running"
        print(f"[SCHEDULER] Task '{task_id}' successfully scheduled to run.")
        
        self.event_bus.publish(Event(
            event_type="TASK_SCHEDULED",
            correlation_id=task_id,
            source="runtime/scheduler",
            severity="info",
            payload={"active_concurrency": len(self.active_jobs)}
        ))

    def mark_completed(self, task_id):
        """Frees active concurrency slots, resolves dependent tasks, and publishes completion event tracks."""
        if task_id in self.active_jobs:
            del self.active_jobs[task_id]
        self.completed_tasks.add(task_id)
        print(f"[SCHEDULER] Task '{task_id}' completed. Dynamic dependencies resolved.")
        
        self.event_bus.publish(Event(
            event_type="TASK_COMPLETED",
            correlation_id=task_id,
            source="runtime/scheduler",
            severity="info",
            payload={"remaining_concurrency": len(self.active_jobs)}
        ))
