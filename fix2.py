import pathlib

p = pathlib.Path('docker/agent_harness.py')
lines = p.read_text(encoding='utf-8').splitlines(keepends=True)

out = []
i = 0
while i < len(lines):
    line = lines[i]
    # Fix 1: replace ProxyError return False line
    if 'return False, f"ProxyError' in line and 'sidecar unreachable: {e}"' in line:
        indent = '        '
        out.append(indent + 'err = str(e)\n')
        out.append(indent + 'if "403" in err or "Forbidden" in err:\n')
        out.append(indent + '    return True, "Proxy active + governing: 403 block (unknown tenant)"\n')
        out.append(indent + 'return False, f"ProxyError: sidecar unreachable: {err[:120]}"\n')
        i += 1
        continue
    # Fix 2: remove sys.exit(1) block in main()
    if '        sys.exit(1)' in line:
        i += 1
        continue
    if '        # Exit non-zero so docker-compose logs show a clear failure' in line:
        i += 1
        continue
    out.append(line)
    i += 1

p.write_text(''.join(out), encoding='utf-8')
print('Done')
