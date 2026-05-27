import time

class ClusterAutoscaler:
    """Dynamically recommends scaling actions based on task queue depth and active agents."""
    def __init__(self, node_registry, queue_manager, telemetry_manager=None, scale_up_threshold=0.75, scale_down_threshold=0.25, cooldown_seconds=60):
        self._registry = node_registry
        self._queue_manager = queue_manager
        self.telemetry = telemetry_manager
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold
        self.cooldown_seconds = cooldown_seconds
        
        self.last_action_time = 0
        self.last_action = None
        
        self.metrics = {
            "scale_up_events": 0,
            "scale_down_events": 0,
            "oscillation_count": 0,
            "cooldown_trigger_count": 0
        }

    def _emit(self, metric_name, value):
        if self.telemetry:
            self.telemetry.emit_metric("autoscaler", metric_name, value)

    def evaluate_scale(self):
        """Calculates global load and returns an action: 'scale_up', 'scale_down', or None."""
        # Simple global queue metric
        # Wait, the queue tasks status was set as 'queued' when enqueued
        tasks_running = sum(1 for t in self._queue_manager.registry.values() if t.status == "running")
        tasks_queued = sum(1 for t in self._queue_manager.registry.values() if t.status == "queued")
        
        active_nodes = len([n for n in self._registry.get_all_nodes() if n.get("status") in ("healthy", "degraded")])
        if active_nodes == 0:
            active_nodes = 1 # Avoid division by zero, assuming 1 local executor
            
        # Let's say each node has a concurrency capacity of 8
        global_capacity = active_nodes * 8.0
        global_load = (tasks_running + tasks_queued) / global_capacity
        
        action = None
        if global_load > self.scale_up_threshold:
            action = "scale_up"
        elif global_load < self.scale_down_threshold and active_nodes > 1:
            action = "scale_down"
            
        now = time.time()
        
        if action:
            if now - self.last_action_time < self.cooldown_seconds:
                self.metrics["cooldown_trigger_count"] += 1
                self._emit("cooldown_trigger_count", self.metrics["cooldown_trigger_count"])
                return None
                
            if self.last_action and self.last_action != action and (now - self.last_action_time < self.cooldown_seconds * 2):
                self.metrics["oscillation_count"] += 1
                self._emit("oscillation_count", self.metrics["oscillation_count"])
                
            self.metrics[f"{action}_events"] += 1
            self._emit(f"{action}_events", self.metrics[f"{action}_events"])
            self.last_action = action
            self.last_action_time = now
            return action
            
        return None
