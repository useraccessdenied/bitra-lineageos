#!/usr/bin/env python3
"""Wait until no ROM build (04-build.sh) is running, then run 04-build.sh for the given tree.
Usage: queue_after.py a17 [userdebug]"""
import subprocess, sys, time, os
ws = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tree, var = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "userdebug")
while subprocess.run(["pgrep", "-f", "04-build.sh"], capture_output=True).returncode == 0:
    time.sleep(30)
sys.exit(subprocess.call(["bash", f"{ws}/scripts/04-build.sh", tree, var]))
