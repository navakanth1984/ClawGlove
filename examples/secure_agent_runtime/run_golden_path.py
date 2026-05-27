import sys
import os
import json
import shutil
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from events.event_store import EventStore
from analytics.replay import ReplayEngine
from security.authorization import AuthorizationEngine
from scripts.verify_replay import verify_forensic_package

class MockStateManager:
    def __init__(self):
        self.state = {
            "state_count": 0,
            "violations_encountered": 0,
            "status": "INIT"
        }
        
    def intercept(self, event):
        self.state["state_count"] += 1
        if "VIOLATION" in event.event_type:
            self.state["violations_encountered"] += 1
            self.state["status"] = "BREACHED"

def execute_golden_path():
    print("==================================================================")
    print("        ACDLC CORE PLATFORM: GOLDEN PATH INDUCTION WALKTHROUGH")
    print("==================================================================")
    
    # 1. Setup Sandbox Workspace
    workspace_dir = os.path.join(os.path.dirname(__file__), "golden_sandbox")
    if os.path.exists(workspace_dir):
        shutil.rmtree(workspace_dir)
    os.makedirs(workspace_dir)
    
    print("[*] Initializing Core Containment Substrate...")
    event_store = EventStore(storage_dir=workspace_dir, max_file_size_mb=10)
    authz = AuthorizationEngine()
    
    # 2. Define Workload Identity and Tenant Fencing Boundaries
    tenant_gamma = "tenant_gamma"
    adversary_tenant = "attacker_corp"
    
    admin_identity = {
        "actor_id": "auditor_alpha",
        "role": "SystemAdmin",
        "tenant_id": "system"
    }
    
    attacker_identity = {
        "actor_id": "malicious_bot",
        "role": "Viewer",
        "tenant_id": adversary_tenant
    }
    
    print(f"  [+] Physical directories segregated for tenant: {tenant_gamma}")
    
    # 3. Simulate High-Fidelity Autonomous Agent Workload
    print("\n[*] Enqueueing autonomous execution events...")
    # Step 1: Normal operations
    for i in range(5):
        event_store.append({
            "event_type": "TASK_COMPLETED",
            "tenant_id": tenant_gamma,
            "payload": {"step": i, "status": "OK"}
        })
        
    # Step 2: Security Breach Attempt
    event_store.append({
        "event_type": "CRITICAL_VIOLATION",
        "tenant_id": tenant_gamma,
        "payload": {"rule": "Max delegation depth exceeded", "violated": True}
    })
    
    # 4. Gated Replay Forensic Sweep
    print("\n[*] Initializing time-travel ReplayEngine...")
    replay_engine = ReplayEngine(event_store=event_store, domain="operational", authz_engine=authz)
    state_mgr = MockStateManager()
    
    print("[*] Security Check: Attempting replay with unauthorized tenant identity...")
    replayed = replay_engine.replay_events(
        state_mgr, 
        tenant_id=tenant_gamma, 
        identity=attacker_identity
    )
    print(f"  [-] Replayed count under unauthorized access: {replayed}")
    assert replayed == 0, "Security Boundary Breach: ReplayEngine allowed unauthorized cross-tenant history sweep!"
    
    print("\n[*] Security Check: Replaying under SystemAdmin authorized forensic credentials...")
    replayed = replay_engine.replay_events(
        state_mgr, 
        tenant_id=tenant_gamma, 
        identity=admin_identity
    )
    print(f"  [+] Replayed count under SystemAdmin: {replayed}")
    assert replayed == 6, f"Expected 6 replayed, got {replayed}"
    assert state_mgr.state["status"] == "BREACHED", "Failed to reconstruct state audit status."
    
    # 5. O(delta) Snapshot Anchor Creation
    print("\n[*] Exporting state snapshot anchor at sequence 6...")
    snap_name = replay_engine.export_snapshot(state_mgr, tenant_gamma, last_sequence=6)
    print(f"  [+] Snapshot state anchor exported successfully: {snap_name}")
    
    # Append delta updates
    print("\n[*] Appending post-incident sequence deltas...")
    event_store.append({
        "event_type": "REMEDIATION_TRIGGERED",
        "tenant_id": tenant_gamma,
        "payload": {"action": "Freeze worker locks", "timestamp": int(time.time())}
    })
    event_store.append({
        "event_type": "SYS_RECOVERY_COMPLETED",
        "tenant_id": tenant_gamma,
        "payload": {"status": "RESTORED"}
    })
    
    # Reboot State Manager to prove O(delta) hydration
    rebooted_state_mgr = MockStateManager()
    print("\n[*] Performing O(delta) state hydration recovery sweep...")
    replayed_delta = replay_engine.replay_events(
        rebooted_state_mgr,
        tenant_id=tenant_gamma,
        identity=admin_identity
    )
    print(f"  [+] Sequence deltas hydrated: {replayed_delta}")
    assert replayed_delta == 2, f"Expected delta of 2 events, got {replayed_delta}"
    assert rebooted_state_mgr.state["state_count"] == 8, f"Final reconstructed count incorrect: {rebooted_state_mgr.state['state_count']}"
    
    # 6. Standardized Forensic Package Export
    print("\n[*] Assembling formal .acdlc-replay package artifact...")
    
    envelope = replay_engine.last_validation_envelope
    
    # Load snapshot state to embed
    snapshot_dir = os.path.join(workspace_dir, "snapshots", tenant_gamma)
    latest_snap_file = os.path.join(snapshot_dir, sorted(os.listdir(snapshot_dir))[-1])
    with open(latest_snap_file, 'r', encoding='utf-8') as f:
        snap_content = json.load(f)
        
    # Gather delta events from sequence 6 onwards
    all_events = event_store.get_all_events(domain="operational", tenant_id=tenant_gamma)
    delta_events = [e for e in all_events if e.get("sequence", 0) > 6]
    
    forensic_package = {
        "replay_id": envelope["replay_id"],
        "schema_version": "1.0",
        "tenant_id": tenant_gamma,
        "domain": "operational",
        "timestamp": int(time.time()),
        "snapshot_anchor": envelope["snapshot_anchor"],
        "archive_epoch": event_store._get_partition_epoch("operational", tenant_gamma),
        "last_sequence": 8,
        "state_snapshot": snap_content.get("state", {}),
        "sequence_delta": delta_events,
        "archive_chain_verified": envelope["archive_chain_verified"]
    }
    
    package_path = os.path.join(workspace_dir, "incident_report.acdlc-replay")
    with open(package_path, 'w', encoding='utf-8') as f:
        json.dump(forensic_package, f, indent=2)
        
    print(f"  [+] Forensic Replay Package exported to: {package_path}")
    
    # 7. Verification CLI Validation
    print("\n[*] Invoking Verification CLI utility on exported certificate...")
    cli_success = verify_forensic_package(package_path)
    assert cli_success, "CLI verification check failed."
    
    # Cleanup sandbox after successful run
    if os.path.exists(workspace_dir):
        shutil.rmtree(workspace_dir)
        
    print("\n[GOLDEN PATH PASS] ACDLC core platform secure execution cycle successfully certified!")
    print("==================================================================")

if __name__ == "__main__":
    execute_golden_path()
