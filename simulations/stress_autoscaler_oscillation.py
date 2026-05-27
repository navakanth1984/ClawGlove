import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cluster.node_registry import NodeRegistry
from cluster.autoscaler import ClusterAutoscaler
from runtime.queue import PriorityTaskQueue, Task
from events.event_store import EventStore
from metrics.telemetry import TelemetryManager

def run_oscillation_test():
    print("==================================================")
    print("   ACDLC v2.0.x  Autoscaler Oscillation Test")
    print("==================================================")
    
    store_dir = os.path.join(os.path.dirname(__file__), "stress_data")
    if not os.path.exists(store_dir):
        os.makedirs(store_dir)
        
    event_store = EventStore(storage_dir=store_dir)
    telemetry = TelemetryManager(event_store, node_id="node_stress")
    
    registry = NodeRegistry()
    registry.register_node({"node_id": "node_01", "status": "healthy", "capabilities": ["execution"]})
    registry.register_node({"node_id": "node_02", "status": "healthy", "capabilities": ["execution"]})
    
    # Short cooldown for test purposes (1 second)
    queue = PriorityTaskQueue(telemetry_manager=telemetry)
    autoscaler = ClusterAutoscaler(
        node_registry=registry, 
        queue_manager=queue, 
        telemetry_manager=telemetry,
        cooldown_seconds=1
    )
    
    print("[*] Simulating bursty traffic (0 -> 1000 -> 0 -> 1000) over 4 seconds...")
    
    # Burst 1
    for i in range(100):
        queue.enqueue(Task(f"t1_{i}", "Burst", 2, {}))
    action = autoscaler.evaluate_scale()
    assert action == "scale_up", "Expected immediate scale_up on first burst"
    
    # Immediate clear & Burst 2 (under cooldown)
    while True:
        t = queue.dequeue()
        if not t: break
        queue.complete_task(t)
    
    action2 = autoscaler.evaluate_scale()
    assert action2 is None, "Expected scale_down to be blocked by cooldown"
    assert autoscaler.metrics["cooldown_trigger_count"] == 1, "Expected cooldown trigger"
    
    # Wait for cooldown to expire
    print("  [Waiting 1.5s for cooldown to expire...]")
    time.sleep(1.5)
    
    # Burst 2 triggers oscillation if it rapidly switches directions
    action3 = autoscaler.evaluate_scale()
    assert action3 == "scale_down", "Expected scale_down after cooldown expired with empty queue"
    
    # Wait again
    print("  [Waiting 1.5s for cooldown to expire...]")
    time.sleep(1.5)
    
    for i in range(100):
        queue.enqueue(Task(f"t2_{i}", "Burst", 2, {}))
    action4 = autoscaler.evaluate_scale()
    
    assert action4 == "scale_up", "Expected scale_up on 2nd burst"
    
    # Check that oscillation count tracked the rapid scale_down -> scale_up
    # Oscillation tracks when the action flips within 2x cooldown
    assert autoscaler.metrics["oscillation_count"] >= 1, "Expected oscillation to be detected"
    
    print("\n[*] Asserting Hard Survivability Criteria...")
    print("  [PASS] Cooldowns successfully prevented immediate yo-yo actions.")
    print("  [PASS] Oscillation count successfully detected rapid flipping.")
    print("\n[SUCCESS] Autoscaler Oscillation Test survived.")
    
    import json
    result = {
        "simulation": "SIM-AUTOSCALE-001",
        "environment": "mocked-runtime",
        "duration_sec": 3.0,
        "status": "PASS",
        "metrics": {
            "scale_up_events": autoscaler.metrics["scale_up_events"],
            "scale_down_events": autoscaler.metrics["scale_down_events"],
            "oscillation_count": autoscaler.metrics["oscillation_count"],
            "cooldown_trigger_count": autoscaler.metrics["cooldown_trigger_count"]
        },
        "resource_snapshot": {
            "active_nodes": len([n for n in registry.get_all_nodes() if n["status"] == "healthy"]),
            "queue_depth_final": queue._get_queue_depth()
        },
        "violations": [],
        "timestamp": time.time()
    }
    print("\n--- SIMULATION RESULT ENVELOPE ---")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    run_oscillation_test()
