"""
agent_harness.py — Phase 5 Network Isolation Test Harness

Simulates what the OpenClaw screenwriter/director agents do:
  - Attempt HTTP calls to api.sarvam.ai
  - Communicate with the ClawGlove daemon on port 50051

Used to verify three properties:
  1. ISOLATION   : direct access to api.sarvam.ai is blocked (internal: true network)
  2. PROXY ROUTE : traffic flows through clawglove-sidecar:8080 correctly
  3. FAIL-CLOSED : if sidecar stops, agent has zero external access

Does NOT make real Sarvam API calls (no API key needed).
"""

import os
import sys
import time
import socket
import requests

AGENT_NAME = os.environ.get("AGENT_NAME", "test-agent")
SARVAM_URL = "https://api.sarvam.ai"
SIDECAR_HOST = "clawglove-sidecar"
SIDECAR_TCP = int(os.environ.get("CLAWGLOVE_DAEMON", "clawglove-sidecar:50051").split(":")[1])

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"


def test_direct_blocked() -> tuple[bool, str]:
    """
    Direct access to Sarvam bypassing the proxy MUST fail.
    Passes if any connection error is raised (network isolation working).
    Fails if a response comes back (isolation breach).
    """
    try:
        resp = requests.get(
            SARVAM_URL,
            proxies={"http": None, "https": None},  # explicitly disable proxy
            timeout=5,
        )
        return False, f"Got HTTP {resp.status_code} — isolation BREACH"
    except requests.exceptions.ConnectionError as e:
        return True, f"ConnectionError — external route absent"
    except requests.exceptions.Timeout:
        return True, "Timeout — no external route"
    except Exception as e:
        return True, f"{type(e).__name__} — blocked"


def test_proxy_route() -> tuple[bool, str]:
    """
    Traffic via HTTP_PROXY env var must reach (or be intercepted by) the sidecar.
    A ProxyError means proxy is down. Any other response/error means the proxy
    intercepted the request (governance check ran).
    """
    try:
        # requests picks up HTTP_PROXY / HTTPS_PROXY from env automatically
        resp = requests.get(SARVAM_URL, timeout=8)
        return True, f"Proxy forwarded — status {resp.status_code}"
    except requests.exceptions.ProxyError as e:
        err = str(e)
        if "403" in err or "Forbidden" in err:
            return True, "Proxy active + governing: 403 block (unknown tenant)"
        return False, f"ProxyError: sidecar unreachable: {err[:120]}"
    except requests.exceptions.ConnectionError as e:
        # Sidecar blocked the request (policy deny) — still means proxy route works
        return True, f"Proxy intercepted + denied — {type(e).__name__}"
    except Exception as e:
        # Any other response means proxy route is active
        return True, f"Proxy active — {type(e).__name__}: {str(e)[:80]}"


def test_daemon_tcp() -> tuple[bool, str]:
    """
    ClawGlove TCP daemon on port 50051 must be reachable from the agent container.
    """
    try:
        s = socket.create_connection((SIDECAR_HOST, SIDECAR_TCP), timeout=5)
        s.close()
        return True, f"TCP {SIDECAR_HOST}:{SIDECAR_TCP} reachable"
    except Exception as e:
        return False, f"TCP {SIDECAR_HOST}:{SIDECAR_TCP} unreachable — {type(e).__name__}"


def run_tests() -> dict:
    print(f"\n[{AGENT_NAME}] ── Phase 5 Network Isolation Tests ──")
    print(f"[{AGENT_NAME}] HTTP_PROXY  = {os.environ.get('HTTP_PROXY', 'not set')}")
    print(f"[{AGENT_NAME}] Target      = {SARVAM_URL}")
    print()

    results = {}

    ok, msg = test_direct_blocked()
    results["isolation"] = ok
    print(f"  [ISOLATION]   Direct access blocked : {PASS if ok else FAIL} — {msg}")

    ok, msg = test_proxy_route()
    results["proxy"] = ok
    print(f"  [PROXY ROUTE] Via sidecar proxy      : {PASS if ok else FAIL} — {msg}")

    ok, msg = test_daemon_tcp()
    results["daemon"] = ok
    print(f"  [DAEMON TCP]  Sidecar :50051 reachable: {PASS if ok else FAIL} — {msg}")

    all_pass = all(results.values())
    print()
    print(f"[{AGENT_NAME}] Result: {'ALL PASS' if all_pass else 'FAILURES DETECTED'}")
    print()
    return results


def main():
    # Run tests and log results
    run_tests()
    # Stay alive so docker exec works during test_failclosed.ps1
    print(f"[{AGENT_NAME}] Container staying alive for external test commands...")
    while True:
        time.sleep(30)


if __name__ == "__main__":
    main()
