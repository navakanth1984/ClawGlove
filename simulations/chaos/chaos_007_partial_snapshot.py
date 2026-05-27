import sys
import os
import time
import json
import shutil

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from events.event_store import EventStore
from analytics.replay import ReplayEngine
from security.authorization import AuthorizationEngine

class MockStateManager:
    def __init__(self):
        self.state = {
            "processed_count": 0,
            "last_event_seen": None
        }
        
    def intercept(self, event):
        self.state["processed_count"] += 1
        self.state["last_event_seen"] = event.event_type

def run_chaos_007():
    print("==================================================")
    print("   ACDLC v2.1 CHAOS-007  Partial Snapshot Write")
    print("==================================================")
    
    store_dir = os.path.join(os.path.dirname(__file__), "chaos_data_007")
    if os.path.exists(store_dir):
        shutil.rmtree(store_dir)
    os.makedirs(store_dir)
        
    event_store = EventStore(storage_dir=store_dir)
    authz = AuthorizationEngine()
    
    tenant_id = "tenant_gamma"
    admin_identity = {
        "actor_id": "sys_admin_forensics",
        "role": "SystemAdmin",
        "tenant_id": "system"
    }
    
    replay_engine = ReplayEngine(event_store=event_store, domain="operational", authz_engine=authz)
    state_mgr = MockStateManager()
    
    # 1. Enqueue and verify first 100 events
    print("[*] Enqueueing initial 100 events...")
    for i in range(100):
        event_store.append({
            "event_type": f"EVENT_{i}",
            "tenant_id": tenant_id,
            "payload": {"index": i}
        })
        
    replayed = replay_engine.replay_events(state_mgr, tenant_id=tenant_id, identity=admin_identity)
    assert replayed == 100, f"Expected 100 replayed, got {replayed}"
    
    # 2. Export a clean snapshot anchor
    print("[*] Exporting verified Snapshot Anchor 1...")
    snap_name = replay_engine.export_snapshot(state_mgr, tenant_id, last_sequence=100)
    print(f"  [+] Clean snapshot created: {snap_name}")
    
    # 3. Simulate power failure / crash mid-way through a second snapshot write
    print("\n[*] Simulating CHAOS-007: Power outage mid-way through Snapshot 2 write...")
    snapshot_dir = os.path.join(store_dir, "snapshots", tenant_id)
    temp_corrupt_path = os.path.join(snapshot_dir, "snapshot_9999999999.json.tmp")
    
    # Write a broken/partial temp file
    with open(temp_corrupt_path, 'w', encoding='utf-8') as f:
        f.write('{"tenant_id": "tenant_gamma", "last_sequence": 200, "state": {')  # Interrupted JSON
        
    print(f"  [+] Incomplete temp write left on disk: {os.path.basename(temp_corrupt_path)}")
    
    # 4. Verify system recovery successfully bypasses the temp file
    print("[*] Performing system recovery sweep...")
    rebooted_state_mgr = MockStateManager()
    
    # Hydration should load Snapshot 1 (.json) and completely bypass the .tmp file
    replayed_delta = replay_engine.replay_events(rebooted_state_mgr, tenant_id=tenant_id, identity=admin_identity)
    print(f"  [+] Replayed post-recovery delta count: {replayed_delta}")
    assert replayed_delta == 0, f"Expected 0 deltas, got {replayed_delta}"
    assert rebooted_state_mgr.state["processed_count"] == 100, "Should have hydrated exactly 100 events from Snapshot 1."
    print("  [PASS] Temp files successfully bypassed! Rebuilt correct state from completed Snapshot 1.")
    
    # 5. Simulate Hard Disk Sector Corruption of a finished snapshot (poisoned completed anchor)
    print("\n[*] Simulating CHAOS-007: Poisoned completed snapshot anchor (sector corruption)...")
    latest_snap_file = os.path.join(snapshot_dir, sorted([f for f in os.listdir(snapshot_dir) if f.endswith(".json")])[-1])
    
    # Mutate the completed JSON to be malformed
    with open(latest_snap_file, 'w', encoding='utf-8') as f:
        f.write("{ corrupt_json: nil ")
        
    print(f"  [+] Snapshot 1 physically poisoned: {os.path.basename(latest_snap_file)}")
    
    # 6. Verify load fails gracefully and falls back to O(N) event log replay
    print("[*] Performing second system recovery sweep under poisoned anchor...")
    rebooted_state_mgr_2 = MockStateManager()
    
    # Since snapshot load fails due to corruption, the engine should gracefully fallback 
    # to cold replaying all 100 events from the EventStore
    replayed_fallback = replay_engine.replay_events(rebooted_state_mgr_2, tenant_id=tenant_id, identity=admin_identity)
    print(f"  [+] Replayed fallback count: {replayed_fallback}")
    assert replayed_fallback == 100, f"Expected cold fallback of 100 events, got {replayed_fallback}"
    assert rebooted_state_mgr_2.state["processed_count"] == 100, "Failed to reconstruct state via event store fallback."
    print("  [PASS] Graceful fallback to O(N) cold EventStore replay succeeded! Poisoned anchor bypassed safely.")
    
    # Cleanup data
    if os.path.exists(store_dir):
        shutil.rmtree(store_dir)
        
    print("\n[CHAOS-007 PASS] Atomic snapshot swapping and fallback recovery successfully certified!")
    print("==================================================")
    
    # Return metrics for envelope
    return {
        "status": "PASS",
        "metrics": {
            "temp_file_bypassed": True,
            "fallback_cold_replay_executed": True,
            "replayed_fallback_count": replayed_fallback
        }
    }

if __name__ == "__main__":
    run_chaos_007()
