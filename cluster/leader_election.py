import threading
import datetime
from .leadership_events import LeadershipEventTypes

class LeaderElection:
    """Lightweight consensus mechanism. Highest Node ID wins if alive."""
    def __init__(self, node_registry, current_node_id, event_bus=None):
        self._registry = node_registry
        self._current_node_id = current_node_id
        self._event_bus = event_bus
        self._current_leader = None
        self._lock = threading.Lock()

    def check_leadership(self):
        """Runs the election algorithm to determine the current leader."""
        with self._lock:
            active_nodes = [
                n for n in self._registry.get_all_nodes()
                if n.get("status") in ("healthy", "degraded", "draining")
            ]
            
            if not active_nodes:
                self._current_leader = None
                return None
                
            # Highest ID wins
            active_nodes.sort(key=lambda n: n["node_id"], reverse=True)
            new_leader = active_nodes[0]["node_id"]
            
            if new_leader != self._current_leader:
                old_leader = self._current_leader
                self._current_leader = new_leader
                print(f"[CLUSTER] Leader election won by {new_leader}. (Previously {old_leader})")
                if self._event_bus:
                    # Circular import avoidance
                    import sys
                    import os
                    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    from runtime.event_bus import Event
                    
                    self._event_bus.publish(Event(
                        event_type=LeadershipEventTypes.LEADER_CHANGED,
                        correlation_id=new_leader,
                        source="cluster/leader_election",
                        payload={"new_leader": new_leader, "old_leader": old_leader}
                    ))
            
            return self._current_leader

    def is_leader(self):
        return self._current_leader == self._current_node_id
