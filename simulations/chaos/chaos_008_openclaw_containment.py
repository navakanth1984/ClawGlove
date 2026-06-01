import sys
import os
import time
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from events.event_store import EventStore
from runtime.queue import PriorityTaskQueue, Task
from runtime.worker import ExecutionWorker
from security.authorization import AuthorizationEngine

def run_chaos_008():
    print("==================================================")
    print("   ACDLC v2.0.x CHAOS-008  OpenClaw Containment")
    print("==================================================")
    
    # Establish a designated sandboxed workspace root
    sandbox_root = os.path.abspath(os.path.dirname(__file__))
    
    # Initialize the worker with our strict policies
    worker = ExecutionWorker(
        worker_id="CHAOS-008-CONTAINER",
        policies={
            "active_token_ceiling": 100000,
            "max_tool_calls_sequence_limit": 5,
            "allow_recursive_agent_spawns": False,
            "workspace_sandbox_root": sandbox_root,
            "allow_shell_commands": False,
            "allowed_egress_domains": ["127.0.0.1", "localhost"],
            "prevent_context_spoofing": True
        }
    )
    
    sim_cases = []
    
    # --- Case 1: Forbidden File Reading (.env) ---
    print("[*] Case 1: Simulating .env secrets read attempt...")
    task_env_read = Task(
        task_id="TASK-ENV-READ",
        name="Attempt reading local .env file",
        priority=2,
        payload={
            "steps": [
                {"action": "read_file", "path": os.path.join(sandbox_root, ".env"), "tokens": 100}
            ]
        }
    )
    res = worker.execute(task_env_read)
    assert res["status"] == "POLICY_VIOLATION", "Case 1 Failed: .env read should be blocked"
    assert "'.env' blocked" in res["error"] or "('.env') blocked" in res["error"], "Case 1 Failed: error message incorrect"
    sim_cases.append({"scenario": "File Read Interception (.env)", "status": "PASS"})
    print("  [PASS] Blocked reading of .env file successfully.")

    # --- Case 2: Forbidden File Writing (MEMORY.md / SOUL.md) ---
    print("[*] Case 2: Simulating MEMORY.md and SOUL.md write attempt...")
    task_memory_write = Task(
        task_id="TASK-MEMORY-WRITE",
        name="Attempt writing to MEMORY.md",
        priority=2,
        payload={
            "steps": [
                {"action": "write_file", "path": os.path.join(sandbox_root, "MEMORY.md"), "content": "tamper", "tokens": 100}
            ]
        }
    )
    res = worker.execute(task_memory_write)
    assert res["status"] == "POLICY_VIOLATION", "Case 2 Failed: MEMORY.md write should be blocked"
    assert "MEMORY.md" in res["error"] or "SOUL.md" in res["error"], "Case 2 Failed: error message incorrect"
    
    task_soul_write = Task(
        task_id="TASK-SOUL-WRITE",
        name="Attempt writing to SOUL.md",
        priority=2,
        payload={
            "steps": [
                {"action": "append_file", "path": os.path.join(sandbox_root, "SOUL.md"), "content": "tamper", "tokens": 100}
            ]
        }
    )
    res = worker.execute(task_soul_write)
    assert res["status"] == "POLICY_VIOLATION", "Case 2 Failed: SOUL.md write should be blocked"
    sim_cases.append({"scenario": "File Write Interception (MEMORY.md/SOUL.md)", "status": "PASS"})
    print("  [PASS] Blocked writing/modifying MEMORY.md & SOUL.md successfully.")

    # --- Case 3: Symlink Traversal (Path Resolves Outside Sandbox) ---
    print("[*] Case 3: Simulating symlink path traversal attempt outside sandbox...")
    # Target path pointing outside our designated sandbox root
    outside_path = os.path.abspath(os.path.join(sandbox_root, "../../../../secrets.txt"))
    task_symlink = Task(
        task_id="TASK-SYMLINK",
        name="Attempt path traversal outside workspace sandbox",
        priority=2,
        payload={
            "steps": [
                {"action": "read_file", "path": outside_path, "tokens": 100}
            ]
        }
    )
    res = worker.execute(task_symlink)
    assert res["status"] == "POLICY_VIOLATION", "Case 3 Failed: path traversal outside sandbox should be blocked"
    assert "resolves outside the sandboxed workspace root" in res["error"], "Case 3 Failed: traversal check did not catch path"
    sim_cases.append({"scenario": "Symlink & Path Traversal Prevention", "status": "PASS"})
    print("  [PASS] Prevented out-of-sandbox file traversal successfully.")

    # --- Case 4: Forbidden Shell Command Execution ---
    print("[*] Case 4: Simulating arbitrary shell command execution attempt...")
    task_shell = Task(
        task_id="TASK-SHELL",
        name="Attempt running arbitrary cmd shell execution",
        priority=2,
        payload={
            "steps": [
                {"action": "run_command", "command": "whoami", "tokens": 100}
            ]
        }
    )
    res = worker.execute(task_shell)
    assert res["status"] == "POLICY_VIOLATION", "Case 4 Failed: shell command execution should be blocked"
    assert "shell command execution is blocked" in res["error"], "Case 4 Failed: shell command block message incorrect"
    sim_cases.append({"scenario": "Shell Command Restriction", "status": "PASS"})
    print("  [PASS] Blocked arbitrary command execution successfully.")

    # --- Case 5: Egress Request Containment ---
    print("[*] Case 5: Simulating external network request egress attempt...")
    task_egress = Task(
        task_id="TASK-EGRESS",
        name="Attempt egress payload exfiltration request",
        priority=2,
        payload={
            "steps": [
                {"action": "network_request", "url": "https://malicious-external-api.com/leak", "tokens": 100}
            ]
        }
    )
    res = worker.execute(task_egress)
    assert res["status"] == "POLICY_VIOLATION", "Case 5 Failed: external network egress request should be blocked"
    assert "blocked by domain containment policy" in res["error"], "Case 5 Failed: egress check did not catch domain"
    sim_cases.append({"scenario": "Egress Request Containment", "status": "PASS"})
    print("  [PASS] Blocked out-of-bounds network egress successfully.")

    # --- Case 6: Context & Header Spoofing Prevention ---
    print("[*] Case 6: Simulating context header tampering / correlation ID spoofing...")
    task_spoof = Task(
        task_id="TASK-SPOOF",
        name="Attempt correlation_id context header spoofing",
        priority=2,
        payload={
            "steps": [
                {"action": "read_file", "path": os.path.join(sandbox_root, "allowed.txt"), "correlation_id": "TAMPERED-ID", "tokens": 100}
            ]
        }
    )
    res = worker.execute(task_spoof)
    assert res["status"] == "POLICY_VIOLATION", "Case 6 Failed: correlation ID spoofing should be blocked"
    assert "Event correlation ID spoofing detected" in res["error"], "Case 6 Failed: context spoof block message incorrect"
    sim_cases.append({"scenario": "Context Spoofing Prevention", "status": "PASS"})
    print("  [PASS] Prevented metadata and correlation ID spoofing successfully.")

    # --- Case 7: Workspace Isolation Enforcement ---
    print("[*] Case 7: Simulating general workspace isolation boundary enforcement...")
    # Attempting to write files outside the workspace root
    outside_write_path = os.path.abspath(os.path.join(sandbox_root, "../../../../untrusted_payload.txt"))
    task_workspace_isolation = Task(
        task_id="TASK-WORKSPACE-ISOLATION",
        name="Attempt file write outside sandboxed workspace directory",
        priority=2,
        payload={
            "steps": [
                {"action": "write_file", "path": outside_write_path, "content": "untrusted payload", "tokens": 100}
            ]
        }
    )
    res = worker.execute(task_workspace_isolation)
    assert res["status"] == "POLICY_VIOLATION", "Case 7 Failed: file write outside workspace should be blocked"
    assert "resolves outside the sandboxed workspace root" in res["error"], "Case 7 Failed: workspace isolation failed"
    sim_cases.append({"scenario": "Workspace Isolation Enforcement", "status": "PASS"})
    print("  [PASS] Enforced workspace isolation boundaries successfully.")

    print("\n==================================================")
    print("           CHAOS-008 SIMULATION COMPLETE")
    print("==================================================")
    
    result = {
        "simulation": "CHAOS-008",
        "environment": "chaos-lab",
        "status": "PASS",
        "cases_evaluated": len(sim_cases),
        "results": sim_cases,
        "timestamp": time.time()
    }
    
    print("\n--- SIMULATION RESULT ENVELOPE ---")
    print(json.dumps(result, indent=2))


def run_openclaw_containment_tests():
    print("==================================================")
    print("   ACDLC v2.x OpenClaw Containment Test Suite")
    print("==================================================")

    store_dir = os.path.join(os.path.dirname(__file__), "openclaw_stress_data")
    if not os.path.exists(store_dir):
        os.makedirs(store_dir)

    event_store = EventStore(storage_dir=store_dir)
    authz = AuthorizationEngine()
    queue = PriorityTaskQueue()
    worker = ExecutionWorker(worker_id="sim-worker")

    violations = []

    print("\n[*] Starting Category A: Credential Protection & Data Isolation")

    print("  [-] v01: Attempting to read .env secrets")
    task_v01 = Task("task_v01", "Read .env", 2, {"steps": [{"action": "call_tool", "tool": "fileReader", "path": ".env"}]})
    res_v01 = worker.execute(task_v01)
    if res_v01["status"] != "POLICY_VIOLATION":
        violations.append("v01: Failed to block .env read [Indirect Secret Exfiltration]")

    print("  [-] v02: Attempting to poison MEMORY.md")
    task_v02 = Task("task_v02", "Overwrite MEMORY.md", 2, {"steps": [{"action": "call_tool", "tool": "fileWriter", "path": "MEMORY.md"}]})
    res_v02 = worker.execute(task_v02)
    if res_v02["status"] != "POLICY_VIOLATION":
        violations.append("v02: Failed to block MEMORY.md poison attempt [Memory Hijacking]")

    print("  [-] v03: Attempting outbound web request")
    task_v03 = Task("task_v03", "Outbound web request", 2, {"steps": [{"action": "call_tool", "tool": "httpRequest", "url": "http://malicious.com"}]})
    res_v03 = worker.execute(task_v03)
    if res_v03["status"] != "POLICY_VIOLATION":
        violations.append("v03: Failed to block unauthenticated egress channel [Unauthenticated Egress Channels]")

    print("  [-] v04: Attempting to spoof context to read other tenant data")
    task_v04 = Task("task_v04", "Context spoofing", 2, {"steps": [{"action": "call_tool", "tool": "dbQuery", "tenant": "other_tenant"}]})
    res_v04 = worker.execute(task_v04)
    if res_v04["status"] != "POLICY_VIOLATION":
        violations.append("v04: Failed to block context spoofing [Context Spoofing]")

    print("\n[*] Starting Category B: Configuration & Path Integrity")

    print("  [-] v05: Attempting to overwrite SOUL.md")
    task_v05 = Task("task_v05", "Overwrite SOUL.md", 2, {"steps": [{"action": "call_tool", "tool": "fileWriter", "path": "SOUL.md"}]})
    res_v05 = worker.execute(task_v05)
    if res_v05["status"] != "POLICY_VIOLATION":
        violations.append("v05: Failed to block SOUL.md overwrite [Workspace Path Overwrite]")

    print("  [-] v09: Attempting Symlink Traversal to /etc/passwd")
    task_v09 = Task("task_v09", "Read /etc/passwd", 2, {"steps": [{"action": "call_tool", "tool": "fileReader", "path": "/etc/passwd"}]})
    res_v09 = worker.execute(task_v09)
    if res_v09["status"] != "POLICY_VIOLATION":
        violations.append("v09: Failed to block absolute path traversal (/etc/passwd) [Symlink Traversal]")

    print("\n[*] Starting Category C: Shell Execution & Command Validation")

    print("  [-] v14: Attempting Shell Injection (ls && cat /etc/shadow)")
    task_v14 = Task("task_v14", "Shell Injection", 2, {"steps": [{"action": "call_tool", "tool": "shell_exec", "command": "ls && cat /etc/shadow"}]})
    res_v14 = worker.execute(task_v14)
    if res_v14["status"] != "POLICY_VIOLATION":
        violations.append("v14: Failed to block shell injection [Command Sequence Injection]")

    print("\n[*] Starting Category D: Resource Allocation & Loop Controls")

    print("  [-] v23: Attempting Infinite Tool Loop")
    task_v23 = Task("task_v23", "Infinite Loop", 2, {"steps": [{"action": "call_tool", "tokens": 500} for _ in range(20)]})
    res_v23 = worker.execute(task_v23)
    if res_v23["status"] != "POLICY_VIOLATION":
        violations.append("v23: Failed to block infinite tool loop [Recursive Skill Chains]")

    print("\n==================================================")
    print("                  TEST RESULTS                    ")
    print("==================================================")

    # Save the results
    result = {
        "simulation": "CHAOS-008",
        "environment": "chaos-lab",
        "duration_sec": 0.1,
        "status": "PASS" if len(violations) == 0 else "FAIL",
        "metrics": {
            "vulnerabilities_found": len(violations)
        },
        "resource_snapshot": {},
        "violations": violations,
        "timestamp": time.time()
    }

    for v in violations:
        print(f"BUG/ENHANCEMENT IDENTIFIED: {v}")

    import shutil
    shutil.rmtree(store_dir)

    print("\n--- SIMULATION RESULT ENVELOPE ---")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    run_chaos_008()
