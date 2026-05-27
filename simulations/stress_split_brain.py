import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cluster.node_registry import NodeRegistry
from cluster.leader_election import LeaderElection
from cluster.term_store import TermStore
from events.event_store import EventStore

class PartitionedRegistry(NodeRegistry):
    def __init__(self, visible_nodes):
        super().__init__()
        self.visible_nodes = visible_nodes
        
    def get_all_nodes(self):
        nodes = super().get_all_nodes()
        return [n for n in nodes if n["node_id"] in self.visible_nodes]

def run_split_brain():
    print("==================================================")
    print("   ACDLC v2.0.x  Split Brain Simulation")
    print("==================================================")
    
    store_dir = os.path.join(os.path.dirname(__file__), "stress_data")
    if not os.path.exists(store_dir):
        os.makedirs(store_dir)
        
    event_store = EventStore(storage_dir=store_dir)
    term_store = TermStore(storage_dir=store_dir)
    
    # 1. Initialize Global State
    global_registry = NodeRegistry()
    global_registry.register_node({"node_id": "node_A", "status": "healthy"})
    global_registry.register_node({"node_id": "node_B", "status": "healthy"})
    
    print("[*] Normal State: Node A and B can see each other.")
    election_A = LeaderElection(global_registry, "node_A")
    leader_before = election_A.check_leadership()
    assert leader_before == "node_B", "node_B has higher ID, should be leader"
    
    # Node B establishes term
    current_term = term_store.increment_term("node_B")
    
    # 2. Simulate Network Partition
    print("[*] Network Partition: Node A and Node B isolated from each other.")
    
    reg_A_view = PartitionedRegistry(["node_A"])
    reg_A_view.register_node({"node_id": "node_A", "status": "healthy"})
    
    reg_B_view = PartitionedRegistry(["node_B"])
    reg_B_view.register_node({"node_id": "node_B", "status": "healthy"})
    
    election_A_iso = LeaderElection(reg_A_view, "node_A")
    election_B_iso = LeaderElection(reg_B_view, "node_B")
    
    leader_A_view = election_A_iso.check_leadership()
    leader_B_view = election_B_iso.check_leadership()
    
    assert leader_A_view == "node_A"
    assert leader_B_view == "node_B"
    
    # Both think they are leader!
    # 3. Epoch Fencing Enforcement via TermStore
    
    # Node A tries to write to TermStore
    term_A = term_store.increment_term("node_A")
    # TermStore should now be at term 2 owned by A
    assert term_A == current_term + 1
    
    # Node B tries to perform an action using its old term (current_term)
    valid_B = term_store.verify_leadership("node_B", current_term)
    assert not valid_B, "Node B should be fenced out because Node A incremented the term."
    
    print("\n[*] Asserting Hard Survivability Criteria...")
    print("  [PASS] Network partition created transient dual-leadership.")
    print("  [PASS] Epoch fencing successfully revoked Node B's authority upon partition.")
    print("\n[SUCCESS] Split-Brain Simulation survived.")

if __name__ == "__main__":
    run_split_brain()
