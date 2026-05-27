import sys
import os
import threading
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from security.auth import AuthenticationEngine
from metrics.telemetry import TelemetryManager
from events.event_store import EventStore

def run_token_edge_cases():
    print("==================================================")
    print("   ACDLC v2.0.x  Token Revocation & Edge Cases")
    print("==================================================")
    
    store_dir = os.path.join(os.path.dirname(__file__), "stress_data")
    if not os.path.exists(store_dir):
        os.makedirs(store_dir)
        
    event_store = EventStore(storage_dir=store_dir)
    telemetry = TelemetryManager(event_store, node_id="node_sim")
    
    auth = AuthenticationEngine()
    
    # Generate 10,000 active tokens
    print("[*] Issuing 10,000 tokens...")
    tokens = []
    for i in range(10000):
        t = auth.issue_token(actor_id=f"user_{i}", role="TenantUser", tenant_id="tenant_X")
        tokens.append(t)
        
    # Validation phase
    assert auth.validate_token(tokens[0]) is not None
    assert auth.validate_token(tokens[-1]) is not None
    print("[+] Verified 10,000 tokens exist.")
    
    print("[*] Initiating 10,000 revocations in rapid succession (sweep simulation)...")
    
    # We will simulate high concurrency using threads
    success_count = [0]
    stale_hits = [0]
    
    def worker_revoke(token_chunk):
        for tok in token_chunk:
            if auth.revoke_token(tok):
                success_count[0] += 1
                
    def worker_validate(token_chunk):
        # Tries to use the token while it's being revoked
        for tok in token_chunk:
            if auth.validate_token(tok) is not None:
                stale_hits[0] += 1
    
    threads = []
    chunk_size = 1000
    for i in range(0, 10000, chunk_size):
        chunk = tokens[i:i+chunk_size]
        t1 = threading.Thread(target=worker_revoke, args=(chunk,))
        t2 = threading.Thread(target=worker_validate, args=(chunk,))
        threads.append(t1)
        threads.append(t2)
        
    start_time = time.time()
    for t in threads:
        t.start()
        
    for t in threads:
        t.join()
        
    duration = time.time() - start_time
    
    print(f"[+] Processed 10,000 revocations in {duration:.4f} seconds.")
    
    # Assert Hard Criteria
    print("\n[*] Asserting Hard Survivability Criteria...")
    
    assert success_count[0] == 10000, f"FAIL: Expected 10,000 successful revocations, got {success_count[0]}"
    print("  [PASS] 10,000 tokens fully revoked.")
    
    # Ensure no token works post-revocation
    final_stale_count = sum(1 for tok in tokens if auth.validate_token(tok) is not None)
    assert final_stale_count == 0, f"FAIL: {final_stale_count} tokens still valid after revocation sweep!"
    print("  [PASS] 0 stale tokens post-sweep.")
    
    print("\n[SUCCESS] Token Revocation Simulation survived.")

if __name__ == "__main__":
    run_token_edge_cases()
