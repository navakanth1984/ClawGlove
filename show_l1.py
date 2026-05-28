"""
show_l1.py - prints the relevant sections of runtime.py and runner.py
so we can find exactly where to inject the operator reset.
"""
import pathlib

for fname in ['cgbench/layers/runtime.py', 'cgbench/runner.py']:
    p = pathlib.Path(fname)
    if not p.exists():
        print(f"\n--- {fname} NOT FOUND ---")
        continue
    lines = p.read_text(encoding='utf-8').splitlines()
    print(f"\n{'='*60}")
    print(f"  {fname}  ({len(lines)} lines)")
    print(f"{'='*60}")
    for i, line in enumerate(lines, 1):
        print(f"{i:4d}  {line}")
