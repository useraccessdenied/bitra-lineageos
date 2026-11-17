#!/usr/bin/env python3
"""Compare a kernel fragment against a built .config. Read-only.
Usage: check_kernel_config.py FRAGMENT DOTCONFIG"""
import re, sys
def parse(p):
    d = {}
    for l in open(p):
        l = l.strip()
        m = re.match(r"CONFIG_(\w+)=(.*)", l) or None
        if m: d[m[1]] = m[2]; continue
        m = re.match(r"# CONFIG_(\w+) is not set", l)
        if m: d[m[1]] = "n"
    return d
want, have = parse(sys.argv[1]), parse(sys.argv[2])
ok, change, absent = [], [], []
for k, v in want.items():
    h = have.get(k)
    (ok if h == v else absent if h is None else change).append((k, v, h))
print(f"already OK: {len(ok)}")
print(f"explicitly off/different, must change: {len(change)}")
for k, v, h in change: print(f"  CONFIG_{k}: have {h}, want {v}")
print(f"absent from .config (dependency missing, or option doesn't exist in 4.19): {len(absent)}")
for k, v, _ in absent: print(f"  CONFIG_{k}")
