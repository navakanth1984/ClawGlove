import sys
import os
import random

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from security.authorization import AuthorizationEngine
from security.roles import Roles, Permissions
from events.event_store import EventStore
from metrics.telemetry import TelemetryManager

class AuditToTelemetryAdapter:
    def __init__(self, telemetry):
        self.telemetry = telemetry
        self.total_records = 0
        self.denied_count = 0
        self.cross_tenant_attempts = 0
        
    def record(self, actor, action, resource, result):
        self.total_records += 1
        if result == "DENY":
            self.denied_count += 1
            self.telemetry.emit_metric("security", "denied_requests", self.denied_count)
            
        if "cross_tenant" in action:
            self.cross_tenant_attempts += 1
            self.telemetry.emit_metric("security", "cross_tenant_attempts", self.cross_tenant_attempts)
            
        self.telemetry.event_store.append({
            "event_type": "AUDIT_LOG",
            "actor": actor,
            "action": action,
            "resource": resource,
            "result": result
        })

def run_tenant_fuzzing():
    print("==================================================")
    print("   ACDLC v2.0.x  Tenant Fuzzing Simulation")
    print("==================================================")
    
    store_dir = os.path.join(os.path.dirname(__file__), "stress_data")
    if not os.path.exists(store_dir):
        os.makedirs(store_dir)
        
    event_store = EventStore(storage_dir=store_dir)
    telemetry = TelemetryManager(event_store, node_id="node_sim")
    
    audit_adapter = AuditToTelemetryAdapter(telemetry)
    authz = AuthorizationEngine(audit_logger=audit_adapter)
    
    print("[*] Generating 10,000 hostile/random access requests...")
    
    TARGET_TENANT = "secure_core"
    ATTEMPTS = 10000
    unauthorized_executions = 0
    
    identities = [
        {"actor_id": "user_1", "tenant_id": "tenant_A", "role": "TenantUser"},
        {"actor_id": "user_2", "tenant_id": "tenant_B", "role": "TenantUser"},
        {"actor_id": "user_3", "tenant_id": "tenant_C", "role": "TenantAdmin"},
        {"actor_id": "attacker_1", "tenant_id": "attacker", "role": "TenantUser"},
        None, # Anonymous
        {"actor_id": "sys_admin", "tenant_id": "system", "role": "SystemAdmin"}
    ]
    
    for i in range(ATTEMPTS):
        identity = random.choice(identities)
        
        # Attack vector: Check cross tenant access
        allowed = authz.check_cross_tenant_access(identity, TARGET_TENANT)
        
        # Did the attacker get through?
        # Only SystemAdmin or identity within TARGET_TENANT should be allowed
        if allowed:
            if not identity or (identity["tenant_id"] != TARGET_TENANT and identity["role"] != "SystemAdmin"):
                unauthorized_executions += 1

    print("\n[*] Asserting Hard Survivability Criteria...")
    
    assert unauthorized_executions == 0, f"FAIL: Detected {unauthorized_executions} unauthorized cross-tenant accesses"
    print("  [PASS] 0 Unauthorized Executions detected across 10,000 requests.")
    
    assert audit_adapter.total_records == ATTEMPTS, "FAIL: Audit log did not capture 100% of requests"
    print(f"  [PASS] 100% Audit Capture ({audit_adapter.total_records} / {ATTEMPTS}).")
    
    print(f"  [PASS] Logged {audit_adapter.denied_count} DENY attempts.")
    
    print("\n[SUCCESS] Tenant Fuzzing Simulation survived.")

if __name__ == "__main__":
    run_tenant_fuzzing()
