import datetime

class NodeHealthMonitor:
    def __init__(self, registry, timeout_sec=60):
        self._registry = registry
        self._timeout_sec = timeout_sec

    def process_heartbeat(self, node_id):
        node = self._registry.get_node(node_id)
        if node:
            node["last_seen"] = datetime.datetime.utcnow().isoformat() + "Z"
            if node.get("status") != "healthy":
                node["status"] = "healthy"
                print(f"[CLUSTER-HEALTH] Node {node_id} is healthy")
        else:
            # We don't want to log 50k times if it's an unknown node storm, but a warning is needed
            pass

    def purge_stale_nodes(self):
        now = datetime.datetime.utcnow()
        for node in self._registry.get_all_nodes():
            node_id = node["node_id"]
            last_seen_str = node.get("last_seen")
            if not last_seen_str:
                continue
                
            # Strip 'Z' and parse
            try:
                last_seen = datetime.datetime.fromisoformat(last_seen_str.replace("Z", ""))
                delta = (now - last_seen).total_seconds()
                if delta > self._timeout_sec:
                    node["status"] = "offline"
                    print(f"[CLUSTER-HEALTH] Node {node_id} marked offline (no heartbeat in {delta:.1f}s)")
            except ValueError:
                pass
