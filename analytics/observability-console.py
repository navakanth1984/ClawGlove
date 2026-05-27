"""
ACDLC Observability Console (v1.6+)

This module is a programmatic interface to the Observability Dashboard.
For the HTML dashboard, see: analytics/dashboard.html
For the dashboard generator, see: scripts/generate_dashboard.py

This stub is registered in manifest.yaml for structural validation.
Full implementation is delegated to the dashboard generator script
which reads warehouse telemetry and renders the 4-tab HTML interface.
"""

import os
import subprocess
import sys


def launch_dashboard():
    """Regenerates the HTML observability dashboard from current warehouse data."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    generator = os.path.join(base_dir, "scripts", "generate_dashboard.py")

    if not os.path.exists(generator):
        print("[ERROR] Dashboard generator not found at:", generator)
        sys.exit(1)

    print("[OBSERVABILITY] Launching dashboard regeneration...")
    result = subprocess.run([sys.executable, generator], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)


if __name__ == "__main__":
    launch_dashboard()
