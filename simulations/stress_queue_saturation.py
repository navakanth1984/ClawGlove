import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from events.event_store import EventStore
from metrics.telemetry import TelemetryManager
from runtime.queue import PriorityTaskQueue, Task

def run_stress_test():
    print("==================================================")
    print("   ACDLC v2.0.x  Queue Saturation Stress Test")
    print("==================================================")
    
    store_dir = os.path.join(os.path.dirname(__file__), "stress_data")
    if not os.path.exists(store_dir):
        os.makedirs(store_dir)
        
    event_store = EventStore(storage_dir=store_dir)
    telemetry = TelemetryManager(event_store, node_id="node_stress")
    queue = PriorityTaskQueue(telemetry_manager=telemetry)
    
    TARGET_TASKS = 100000
    print(f"[*] Enqueuing {TARGET_TASKS} tasks across mixed priorities...")
    
    start_time = time.time()
    
    # 1. Enqueue Phase
    for i in range(TARGET_TASKS):
        # Mix priorities: mostly execution (P2), some research (P3), rare recovery (P0)
        p = 2
        if i % 10 == 0:
            p = 3
        if i % 1000 == 0:
            p = 0
            
        t = Task(f"task_{i}", f"Stress Task {i}", p, {})
        queue.enqueue(t)
        
    enqueue_duration = time.time() - start_time
    print(f"[+] Enqueued {TARGET_TASKS} tasks in {enqueue_duration:.2f} seconds.")
    
    # 2. Dequeue Phase
    print(f"[*] Dequeuing all tasks to validate priority starvation prevention...")
    
    dequeue_start = time.time()
    tasks_processed = 0
    
    while True:
        t = queue.dequeue()
        if not t:
            break
        queue.complete_task(t)
        tasks_processed += 1
        
    dequeue_duration = time.time() - dequeue_start
    print(f"[+] Dequeued and completed {tasks_processed} tasks in {dequeue_duration:.2f} seconds.")
    
    # 3. Hard Survivability Criteria Assertion
    print("\n[*] Asserting Hard Survivability Criteria...")
    
    # 3.1 No Task Loss
    assert tasks_processed == TARGET_TASKS, f"FAIL: Expected {TARGET_TASKS} tasks, processed {tasks_processed}"
    print("  [PASS] No Task Loss (100% processed)")
    
    # 3.2 No Starvation
    assert queue.metrics["priority_starvation_count"] == 0, "FAIL: Detected priority starvation"
    print("  [PASS] No Priority Starvation")
    
    avg_processing_time_ms = (dequeue_duration / TARGET_TASKS) * 1000
    print(f"  [PASS] Avg Latency: {avg_processing_time_ms:.4f} ms per task")
    
    print("\n[SUCCESS] Queue Saturation survived hostile volume.")
    
    # 4. Simulation Result Envelope
    import json
    result = {
        "simulation": "SIM-QUEUE-001",
        "environment": "mocked-runtime",
        "duration_sec": round(enqueue_duration + dequeue_duration, 2),
        "status": "PASS",
        "metrics": {
            "max_queue_depth": TARGET_TASKS,
            "avg_wait_ms": round(avg_processing_time_ms, 2),
            "orphaned_tasks": 0,
            "tasks_processed": tasks_processed
        },
        "resource_snapshot": {
            "event_store_size_mb": round(os.path.getsize(event_store._log_path) / (1024 * 1024), 2) if os.path.exists(event_store._log_path) else 0.0,
            "active_nodes": 1,
            "queue_depth_final": queue._get_queue_depth()
        },
        "violations": [],
        "timestamp": time.time()
    }
    print("\n--- SIMULATION RESULT ENVELOPE ---")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    run_stress_test()
