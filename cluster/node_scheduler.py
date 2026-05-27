import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.event_bus import EventBus, Event

class DistributedNodeScheduler:
    """Distributes tasks to external worker nodes via the EventBus."""
    
    def __init__(self, node_registry, routing_engine):
        self._node_registry = node_registry
        self._routing_engine = routing_engine
        self._event_bus = EventBus()

    def dispatch_task(self, task, available_agents, task_tenant_id="default"):
        """Selects an agent and publishes a DISTRIBUTED_TASK_DISPATCH event."""
        # Note: In a fully distributed model, we'd also select a node_id based on node capabilities.
        # Here we route to an agent, and let the cluster pick it up.
        best_agent, score = self._routing_engine.route(
            getattr(task, "capability", "generic"), available_agents, task_tenant_id=task_tenant_id
        )
        
        if best_agent:
            agent_id = best_agent.get("agent_id", best_agent.get("id"))
            self._event_bus.publish(Event(
                event_type="DISTRIBUTED_TASK_DISPATCH",
                correlation_id=task.task_id,
                source="cluster/node_scheduler",
                severity="info",
                agent_id=agent_id,
                tenant_id=task_tenant_id,
                payload={
                    "task_id": task.task_id,
                    "target_agent": agent_id,
                    "score": score
                }
            ))
            return True
        else:
            print(f"[CLUSTER-SCHEDULER] Dispatch failed for task {task.task_id}: no capable agents.")
            return False
