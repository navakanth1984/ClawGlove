import sys
import os
import time
import json
import threading
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from events.event_store import EventStore
from runtime.queue import PriorityTaskQueue, Task
from cluster.autoscaler import ClusterAutoscaler
from cluster.node_registry import NodeRegistry
from metrics.telemetry import TelemetryManager

def run_chaos_004():
    print("==================================================")
    print("   ACDLC v2.0.x CHAOS-004  Disk Freeze")
    print("==================================================")
    
    store_dir = os.path.join(os.path.dirname(__file__), "chaos_data")
    if not os.path.exists(store_dir):
        os.makedirs(store_dir)
        
    event_store = EventStore(storage_dir=store_dir)
    telemetry = TelemetryManager(event_store, node_id="node_chaos")
    queue = PriorityTaskQueue(telemetry_manager=telemetry)
    
    registry = NodeRegistry()
    registry.register_node({"node_id": "worker", "status": "healthy"})
    autoscaler = ClusterAutoscaler(registry, queue, telemetry)
    
    # We will simulate a disk freeze by monkey-patching EventStore's append logic
    # to add a massive artificial delay
    original_append = event_store._on_event
    
    freeze_active = [False]
    
    def slow_append(event_dict):
        if freeze_active[0]:
            time.sleep(0.01) # Simulated backpressure. We keep it 10ms to allow the test to finish but still simulate a 10x slowdown.
        original_append(event_dict)
        
    event_store._on_event = slow_append
    
    # 1. Normal IO
    start_normal = time.time()
    for i in range(100):
        queue.enqueue(Task(f"t_norm_{i}", "Normal", 2, {}))
    duration_normal = time.time() - start_normal
    
    print(f"[*] Normal Enqueue Throughput: 100 tasks in {duration_normal:.4f} seconds.")
    
    # 2. Disk Freeze
    print("[*] Simulating Disk Freeze / Slow IO...")
    freeze_active[0] = True
    
    start_frozen = time.time()
    for i in range(100):
        queue.enqueue(Task(f"t_froz_{i}", "Frozen", 2, {}))
    duration_frozen = time.time() - start_frozen
    
    print(f"[*] Frozen Enqueue Throughput: 100 tasks in {duration_frozen:.4f} seconds.")
    
    # Evaluate backpressure explosion
    queue_depth = queue._get_queue_depth()
    action = autoscaler.evaluate_scale()
    
    print("\n[*] Asserting Chaos Survivability Criteria...")
    assert duration_frozen > duration_normal * 2, "Expected disk freeze to severely impact throughput."
    print("  [PASS] Backpressure properly slowed the enqueue rate without crashing.")
    
    assert queue_depth == 200, "Expected all tasks to be queued despite disk latency."
    print("  [PASS] No tasks were dropped during disk stall.")
    
    assert action == "scale_up", "Autoscaler failed to detect queue explosion caused by disk latency."
    print("  [PASS] Autoscaler detected the backpressure queue explosion and requested scale_up.")
    
    result = {
        "simulation": "CHAOS-004",
        "environment": "chaos-lab",
        "duration_sec": round(duration_normal + duration_frozen, 2),
        "status": "PASS",
        "metrics": {
            "normal_latency_sec": round(duration_normal, 4),
            "frozen_latency_sec": round(duration_frozen, 4),
            "queue_depth": queue_depth
        },
        "resource_snapshot": {
            "event_store_size_mb": round(os.path.getsize(event_store._log_path) / (1024 * 1024), 2) if os.path.exists(event_store._log_path) else 0.0
        },
        "violations": [],
        "timestamp": time.time()
    }
    
    print("\n--- SIMULATION RESULT ENVELOPE ---")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    run_chaos_004()
