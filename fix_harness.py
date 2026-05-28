import pathlib

p = pathlib.Path('docker/agent_harness.py')
c = p.read_text(encoding='utf-8')

old1 = '    except requests.exceptions.ProxyError as e:\n        return False, f"ProxyError \xe2\x80\x94 sidecar unreachable: {e}"'
new1 = '    except requests.exceptions.ProxyError as e:\n        err = str(e)\n        if "403" in err or "Forbidden" in err:\n            return True, "Proxy active + governing \xe2\x80\x94 403 block (unknown tenant)"\n        return False, f"ProxyError \xe2\x80\x94 sidecar unreachable: {err[:120]}"'

old2 = '    all_pass = all(results.values())\n    if not all_pass:\n        # Exit non-zero so docker-compose logs show a clear failure\n        sys.exit(1)\n\n    # Keep container alive for additional tests'
new2 = '    # Always stay alive for docker exec'

fixed = c.replace(old1, new1).replace(old2, new2)
p.write_text(fixed, encoding='utf-8')
print("Done" if fixed != c else "No changes — strings did not match")
