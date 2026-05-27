class NodeRegistry:
    def __init__(self):
        self._nodes = {} # node_id -> node_profile dict

    def register_node(self, node_profile):
        node_id = node_profile.get("node_id")
        if not node_id:
            raise ValueError("node_id is required")
        self._nodes[node_id] = node_profile
        print(f"[CLUSTER] Registered node: {node_id}")

    def deregister_node(self, node_id):
        if node_id in self._nodes:
            del self._nodes[node_id]
            print(f"[CLUSTER] Deregistered node: {node_id}")

    def get_node(self, node_id):
        return self._nodes.get(node_id)

    def get_all_nodes(self):
        return list(self._nodes.values())
