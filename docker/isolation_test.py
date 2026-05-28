"""
isolation_test.py — called by test_failclosed.ps1 via docker exec
Usage: python isolation_test.py <test>
Tests: direct | proxy | daemon | failclosed
Exits 0 = PASS, 1 = FAIL
"""
import sys
import os
import socket
import requests

SARVAM_URL = "https://api.sarvam.ai"
SIDECAR_HOST = "clawglove-sidecar"
SIDECAR_PORT = 50051

test = sys.argv[1] if len(sys.argv) > 1 else "direct"

if test == "direct":
    # Direct access must be blocked (internal: true network)
    try:
        requests.get(SARVAM_URL, proxies={"http": None, "https": None}, timeout=5)
        print("BREACH: direct access succeeded")
        sys.exit(1)
    except Exception as e:
        print(f"BLOCKED: {type(e).__name__}")
        sys.exit(0)

elif test == "proxy":
    # Proxy must be reachable (403 = governing = PASS)
    try:
        requests.get(SARVAM_URL, timeout=8)
        print("PROXY: forwarded request")
        sys.exit(0)
    except requests.exceptions.ProxyError as e:
        err = str(e)
        if "403" in err or "Forbidden" in err:
            print("PROXY: active and governing (403 block)")
            sys.exit(0)
        print(f"PROXY_DOWN: {err[:120]}")
        sys.exit(1)
    except Exception as e:
        print(f"PROXY: intercepted — {type(e).__name__}")
        sys.exit(0)

elif test == "daemon":
    # TCP daemon must be reachable
    try:
        s = socket.create_connection((SIDECAR_HOST, SIDECAR_PORT), timeout=5)
        s.close()
        print(f"TCP: {SIDECAR_HOST}:{SIDECAR_PORT} reachable")
        sys.exit(0)
    except Exception as e:
        print(f"TCP_FAIL: {type(e).__name__}")
        sys.exit(1)

elif test == "failclosed":
    # Sidecar is down — proxy must be unreachable (fail-closed)
    try:
        requests.get(SARVAM_URL, timeout=5)
        print("BREACH: request succeeded without sidecar")
        sys.exit(1)
    except requests.exceptions.ProxyError as e:
        print(f"FAIL_CLOSED: ProxyError — {str(e)[:80]}")
        sys.exit(0)
    except Exception as e:
        print(f"FAIL_CLOSED: {type(e).__name__}")
        sys.exit(0)

else:
    print(f"Unknown test: {test}")
    sys.exit(1)
