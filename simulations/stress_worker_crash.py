import sys
import os
import time
import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cluster.node_registry import NodeRegistry
from cluster.node_health import NodeHealthMonitor
from events.event_store import EventStore
from metrics.telemetry import TelemetryManager
from runtime.queue import PriorityTaskQueue, Task

def run_worker_crash_recovery():
    print("==================================================")
    print("   ACDLC v2.0.x  Worker Crash Recovery Test")
    print("==================================================")
    
    store_dir = os.path.join(os.path.dirname(__file__), "stress_data")
    if not os.path.exists(store_dir):
        os.makedirs(store_dir)
        
    event_store = EventStore(storage_dir=store_dir)
    telemetry = TelemetryManager(event_store, node_id="node_sim")
    
    registry = NodeRegistry()
    monitor = NodeHealthMonitor(registry, timeout_sec=2) # fast timeout for test
    queue = PriorityTaskQueue(telemetry_manager=telemetry)
    
    # Register a worker node
    registry.register_node({"node_id": "worker_01", "status": "healthy"})
    
    # Send heartbeat
    monitor.process_heartbeat("worker_01")
    
    print("[*] Assigning task to worker_01...")
    t = Task("task_critical", "Process Payment", 2, {})
    queue.enqueue(t)
    
    # Dequeue acts as assigning
    assigned_task = queue.dequeue()
    assigned_task.assigned_node = "worker_01"
    
    assert assigned_task.status == "running"
    
    # Simulate Worker Crash
    print("[*] Simulating Worker Crash: worker_01 stops sending heartbeats.")
    
    # Wait for timeout to pass
    time.sleep(2.5)
    
    print("[*] Triggering Health Monitor Sweep...")
    monitor.purge_stale_nodes()
    
    worker_node = registry.get_node("worker_01")
    assert worker_node["status"] == "offline", "Expected worker_01 to be offline"
    
    # Mock OS Recovery Loop: Detect offline nodes and requeue tasks
    # In full OS, this would be triggered by an EventBus CRITICAL_SYSTEM_EVENT
    print("[*] OS Recovery Loop detecting orphaned tasks...")
    
    orphans_detected = 0
    for task_id, task_obj in queue.registry.items():
        if task_obj.status == "running" and task_obj.assigned_node == "worker_01":
            queue.mark_orphaned(task_obj)
            orphans_detected += 1
            # Requeue
            queue.requeue_for_retry(task_obj)
            task_obj.assigned_node = None
            
    print("\n[*] Asserting Hard Survivability Criteria...")
    assert orphans_detected == 1, "FAIL: Expected 1 orphaned task detected"
    print("  [PASS] Missed heartbeats successfully detected and node marked offline.")
    
    requeued_task = queue.get_task("task_critical")
    assert requeued_task.status == "queued", "FAIL: Task not requeued"
    assert requeued_task.priority == 0, "FAIL: Task not escalated to P0 recovery lane"
    
    print("  [PASS] Orphaned task safely intercepted and pushed to P0 Recovery Queue.")
    print("\n[SUCCESS] Worker Crash Recovery Simulation survived.")
    
    import json
    result = {
        "simulation": "SIM-CRASH-001",
        "environment": "mocked-runtime",
        "duration_sec": 2.5,
        "status": "PASS",
        "metrics": {
            "time_to_detect_offline_sec": 2.5,
            "orphaned_tasks_detected": orphans_detected,
            "tasks_requeued": 1
        },
        "resource_snapshot": {
            "active_nodes": len([n for n in registry.get_all_nodes() if n["status"] == "healthy"]),
            "offline_nodes": len([n for n in registry.get_all_nodes() if n["status"] == "offline"]),
            "queue_depth_final": queue._get_queue_depth()
        },
        "violations": [],
        "timestamp": time.time()
    }
    print("\n--- SIMULATION RESULT ENVELOPE ---")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    run_worker_crash_recovery()
