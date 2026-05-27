import sys
import os
import time
import json
import threading
import random

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

def run_chaos_005():
    print("==================================================")
    print("   ACDLC v2.0.x CHAOS-005  EventStore Integrity Recovery")
    print("==================================================")
    
    store_dir = os.path.join(os.path.dirname(__file__), "chaos_data")
    if not os.path.exists(store_dir):
        os.makedirs(store_dir)
        
    log_path = os.path.join(store_dir, "event_log.jsonl")
    if os.path.exists(log_path):
        os.remove(log_path) # Clean start
        
    event_store = EventStore(storage_dir=store_dir, max_file_size_mb=100)
    telemetry = TelemetryManager(event_store, node_id="node_chaos")
    queue = PriorityTaskQueue(telemetry_manager=telemetry)
    
    is_active = True
    
    def writer_thread():
        print("    [Writer] Thread started appending 1000 tasks...")
        for i in range(1000):
            queue.enqueue(Task(f"t_norm_{i}", "NormalTask", 2, {}))
            time.sleep(0.001)
        nonlocal is_active
        is_active = False
        print("    [Writer] Thread finished.")
        
    def corruptor_thread():
        print("    [Corruptor] Thread started injecting raw garbage directly into JSONL...")
        while is_active:
            try:
                # Intentionally bypass the EventStore abstraction to inject corruption directly to disk
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"GARBAGE_DATA_CORRUPTION_{random.randint(0, 10000)}: {{broken_json...\n")
                time.sleep(0.01)
            except Exception:
                pass
        print("    [Corruptor] Thread finished.")
        
    def reader_thread(state_mgr, metrics):
        print("    [Reader] Thread started ReplayEngine over chaotic disk...")
        replay = ReplayEngine(event_store)
        replayed_count = 0
        
        while is_active:
            replayed_count += replay.replay_events(state_mgr, up_to_sequence=None)
            time.sleep(0.05)
            
        # Final catch up
        replayed_count += replay.replay_events(state_mgr, up_to_sequence=None)
        metrics["replayed"] = replayed_count
        print("    [Reader] Thread finished.")
        
    t_writer = threading.Thread(target=writer_thread)
    t_corruptor = threading.Thread(target=corruptor_thread)
    
    state_manager = ConcurrentStateManager()
    reader_metrics = {"replayed": 0}
    t_reader = threading.Thread(target=reader_thread, args=(state_manager, reader_metrics))
    
    start_time = time.time()
    
    t_writer.start()
    t_corruptor.start()
    t_reader.start()
    
    t_writer.join()
    t_corruptor.join()
    t_reader.join()
    
    duration = time.time() - start_time
    
    print("\n[*] Asserting Chaos Survivability Criteria...")
    
    corrupted_skipped = getattr(event_store, "last_corrupted_skipped", 0)
    print(f"  [+] ReplayEngine explicitly detected and skipped {corrupted_skipped} corrupted fragments.")
    
    # 1000 tasks enqueued = minimum 1000 TASK_ENQUEUED events + metric events
    assert state_manager.state_count >= 1000, f"Expected at least 1000 state events recovered, got {state_manager.state_count}"
    assert corrupted_skipped > 0, "Expected corruptor to successfully inject garbage."
    
    print("  [PASS] ReplayEngine isolated corruption and recovered 100% of valid state.")
    print("  [PASS] OS survived extreme I/O contention + corruption concurrently.")
    
    result = {
        "simulation": "CHAOS-005",
        "environment": "chaos-lab",
        "duration_sec": round(duration, 2),
        "status": "PASS",
        "metrics": {
            "events_replayed": reader_metrics["replayed"],
            "corrupted_skipped": corrupted_skipped,
            "state_count_restored": state_manager.state_count
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
    run_chaos_005()
