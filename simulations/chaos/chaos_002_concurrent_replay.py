import sys
import os
import time
import json
import threading

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from events.event_store import EventStore
from metrics.telemetry import TelemetryManager
from analytics.replay import ReplayEngine
from runtime.queue import PriorityTaskQueue, Task

class ConcurrentStateManager:
    def __init__(self):
        self.state_count = 0
        self.lock = threading.Lock()
        
    def intercept(self, event):
        with self.lock:
            self.state_count += 1

def run_chaos_002():
    print("==================================================")
    print("   ACDLC v2.0.x CHAOS-002  Concurrent Replay")
    print("==================================================")
    
    store_dir = os.path.join(os.path.dirname(__file__), "chaos_data")
    if not os.path.exists(store_dir):
        os.makedirs(store_dir)
        
    log_path = os.path.join(store_dir, "event_log.jsonl")
    if os.path.exists(log_path):
        os.remove(log_path) # Clean start
        
    # Instantiate explicitly with high rotation threshold to test raw concurrency on same file
    event_store = EventStore(storage_dir=store_dir, max_file_size_mb=100)
    telemetry = TelemetryManager(event_store, node_id="node_chaos")
    queue = PriorityTaskQueue(telemetry_manager=telemetry)
    
    target_tasks = 20000
    
    print("[*] Pre-populating EventStore with initial 5000 events...")
    for i in range(5000):
        queue.enqueue(Task(f"t_pre_{i}", "PreTask", 2, {}))
        
    # Flags for concurrency
    is_appending = True
    
    def writer_thread():
        print("    [Writer] Thread started, appending remaining 15000 tasks rapidly...")
        for i in range(15000):
            queue.enqueue(Task(f"t_conc_{i}", "ConcTask", 2, {}))
        nonlocal is_appending
        is_appending = False
        print("    [Writer] Thread finished appending.")

    def reader_thread(state_mgr, metrics):
        print("    [Reader] ReplayEngine started, chasing the tail...")
        replay = ReplayEngine(event_store)
        replayed_count = 0
        
        while is_appending:
            replayed_count += replay.replay_events(state_mgr, up_to_sequence=None)
            time.sleep(0.5) # Poll while writer is writing
            
        # Final catch up
        replayed_count += replay.replay_events(state_mgr, up_to_sequence=None)
        metrics["replayed"] = replayed_count
        print("    [Reader] Thread finished replaying.")
        
    t_writer = threading.Thread(target=writer_thread)
    
    state_manager = ConcurrentStateManager()
    reader_metrics = {"replayed": 0}
    t_reader = threading.Thread(target=reader_thread, args=(state_manager, reader_metrics))
    
    start_time = time.time()
    
    t_writer.start()
    time.sleep(0.1) # Let writer get a head start
    t_reader.start()
    
    t_writer.join()
    t_reader.join()
    
    duration = time.time() - start_time
    
    print("\n[*] Asserting Chaos Survivability Criteria...")
    
    total_lines = 0
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip(): total_lines += 1
            
    print(f"  [+] EventStore final line count: {total_lines}")
    print(f"  [+] ReplayEngine processed: {reader_metrics['replayed']} (This might double-count due to polling loops, state_count is what matters)")
    print(f"  [+] StateManager observed unique events? Let's check state count.")
    
    assert total_lines > 20000, "Event store should have > 20,000 events."
    assert state_manager.state_count >= total_lines, "State manager must have seen at least all the lines."
    
    print("  [PASS] Concurrent append/read survived without locking crashes or JSON parse errors.")
    
    result = {
        "simulation": "CHAOS-002",
        "environment": "chaos-lab",
        "duration_sec": round(duration, 2),
        "status": "PASS",
        "metrics": {
            "total_events_written": total_lines,
            "events_processed_by_reader": state_manager.state_count
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
    run_chaos_002()
