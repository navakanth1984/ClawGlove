import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from events.event_store import EventStore
from metrics.telemetry import TelemetryManager
from analytics.replay import ReplayEngine

class DummyStateManager:
    def __init__(self):
        self.state_count = 0
    def intercept(self, event):
        if event.event_type == "VALID_TEST":
            self.state_count += 1

def run_replay_corruption_test():
    print("==================================================")
    print("   ACDLC v2.0.x  Replay Corruption Test")
    print("==================================================")
    
    store_dir = os.path.join(os.path.dirname(__file__), "stress_data")
    if not os.path.exists(store_dir):
        os.makedirs(store_dir)
        
    log_path = os.path.join(store_dir, "event_log_corrupt.jsonl")
    
    # 1. Generate Baseline Data
    print("[*] Generating baseline events...")
    with open(log_path, "w", encoding="utf-8") as f:
        for i in range(100):
            if i % 10 == 0:
                # Inject 10% corrupted lines
                f.write('{"event_type": "CORRUPT_TEST", "malformed_json: \n')
            else:
                f.write(json.dumps({"event_type": "VALID_TEST", "sequence": i}) + "\n")
                
    # 2. Initialize EventStore explicitly pointing to this file
    # We'll mock the internal path for testing
    event_store = EventStore(storage_dir=store_dir)
    event_store._log_path = log_path
    
    # 3. Replay Engine Verification
    print("[*] Starting ReplayEngine over corrupted EventStore...")
    replay = ReplayEngine(event_store)
    
    state_manager = DummyStateManager()
    
    # This should not crash despite the JSONDecodeErrors
    replayed_count = replay.replay_events(state_manager)
    
    corrupted_skipped = getattr(event_store, "last_corrupted_skipped", 0)
    
    print("\n[*] Asserting Hard Survivability Criteria...")
    assert corrupted_skipped == 10, f"FAIL: Expected 10 corrupted lines skipped, got {corrupted_skipped}"
    print("  [PASS] Malformed events successfully skipped (10%).")
    
    assert replayed_count == 90, f"FAIL: Expected 90 valid events replayed, got {replayed_count}"
    assert state_manager.state_count == 90, f"FAIL: State manager reconstructed incorrect state ({state_manager.state_count})"
    print("  [PASS] Partial state restored perfectly from valid delta.")
    print("  [PASS] ReplayEngine survived EventStore corruption without runtime crash.")
    
    print("\n[SUCCESS] Replay Corruption Recovery Test survived.")
    
    import time
    result = {
        "simulation": "SIM-REPLAY-001",
        "environment": "mocked-runtime",
        "duration_sec": 0.0, # instantaneous test
        "status": "PASS",
        "metrics": {
            "events_replayed": replayed_count,
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
    
    # Cleanup
    if os.path.exists(log_path):
        os.remove(log_path)

if __name__ == "__main__":
    run_replay_corruption_test()
