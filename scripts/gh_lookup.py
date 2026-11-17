#!/usr/bin/env python3
"""Wait for all ROM builds to finish, then read kernel branch history and the TWRP tree from GitHub.
Output: logs/gh-lookup.txt. Work happens in a throwaway dir under .tmp (never executed)."""
import subprocess, sys, time, shutil, os
from pathlib import Path
ws = Path(__file__).resolve().parent.parent
out = ws / "logs" / "gh-lookup.txt"
work = ws / ".tmp" / "gh-lookup"

def busy():
    return any(subprocess.run(["pgrep", "-f", p], capture_output=True).returncode == 0
               for p in ("04-build.sh", "queue_after.py"))

while busy():
    time.sleep(60)

def run(args, cwd, timeout=300):
    for attempt in range(3):
        try:
            r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
            if r.returncode == 0:
                return r.stdout
            err = r.stderr[-200:]
        except subprocess.TimeoutExpired:
            err = "timeout"
        time.sleep(10)
    return f"FAILED after retries: {err}\n"

shutil.rmtree(work, ignore_errors=True); work.mkdir(parents=True)
lines = []
k = work / "k"; k.mkdir()
run(["git", "init", "-q"], k)
run(["git", "remote", "add", "o", "https://github.com/SM8250-Common/android_kernel_realme_sm8250"], k)
for b in ["sus", "test", "rebase", "lineage-24.0", "lineage-23.2-07102026"]:
    res = run(["git", "fetch", "-q", "--depth", "15", "--filter=blob:none", "o", f"refs/heads/{b}:refs/remotes/o/{b}"], k, 400)
    lines.append(f"== kernel {b}\n" + (res if res.startswith("FAILED") else
        run(["git", "log", "--format=%ad %h %an | %s", "--date=short", "-15", f"o/{b}"], k)))
t = work / "twrp"; t.mkdir()
run(["git", "init", "-q"], t)
run(["git", "remote", "add", "o", "https://github.com/Saichaitanya888/android_device_realme_bitra-twrp"], t)
res = run(["git", "fetch", "-q", "--depth", "15", "o", "android-14"], t, 400)
if res.startswith("FAILED"):
    lines.append("== twrp\n" + res)
else:
    lines.append("== twrp log\n" + run(["git", "log", "--format=%ad %h %an | %s", "--date=short", "-15", "FETCH_HEAD"], t))
    lines.append("== twrp files\n" + run(["git", "ls-tree", "-r", "--name-only", "FETCH_HEAD"], t))
    lines.append("== twrp BoardConfig/kernel hints\n" + run(["git", "grep", "-nE", "TARGET_KERNEL|BOARD_KERNEL|TARGET_PREBUILT_KERNEL|AB_OTA|dynamic|PLATFORM_VERSION", "FETCH_HEAD", "--", "*.mk", "*.bp"], t))
out.write_text("\n".join(lines))
print("done ->", out)
