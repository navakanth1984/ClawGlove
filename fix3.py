import pathlib

p = pathlib.Path('docker/agent_harness.py')
c = p.read_text(encoding='utf-8')

old = (
    "def main():\n"
    "    # Run tests immediately on container start\n"
    "    results = run_tests()\n"
    "\n"
    "    all_pass = all(results.values())\n"
    "    if not all_pass:\n"
    "\n"
    "    # Keep container alive for exec-based testing from test_failclosed.ps1\n"
    '    print(f"[{AGENT_NAME}] Container staying alive for external test commands...")\n'
    "    while True:\n"
    "        time.sleep(30)\n"
)

new = (
    "def main():\n"
    "    # Run tests and log results\n"
    "    run_tests()\n"
    "    # Stay alive so docker exec works during test_failclosed.ps1\n"
    '    print(f"[{AGENT_NAME}] Container staying alive for external test commands...")\n'
    "    while True:\n"
    "        time.sleep(30)\n"
)

if old in c:
    p.write_text(c.replace(old, new), encoding='utf-8')
    print("Fixed")
else:
    print("No match — current main():")
    start = c.find("def main():")
    print(repr(c[start:start+400]))
