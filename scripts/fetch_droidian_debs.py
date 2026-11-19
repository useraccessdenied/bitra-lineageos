#!/usr/bin/env python3
"""Download the Droidian VoLTE/IMS .debs for the image, verified end to end (stdlib + gpgv).

  python3 scripts/fetch_droidian_debs.py

Fetches http://droidian.g.droidian.org/next-upgrade-gbinder/ (trixie/main, arm64): InRelease signature is checked with gpgv against the
Droidian key (scripts/droidian.gpg), Packages.gz against the hash in InRelease, each .deb against the SHA256 in Packages.
Package versions are pinned in VOLTE_PKGS (same set as scripts/phone_volte_enable.py). Output: releases/droidian-install/debs/.
Downloaded files are untrusted until verified; nothing is executed here.
"""
import gzip, hashlib, subprocess, sys, tempfile, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "releases" / "droidian-install" / "debs"
KEYRING = ROOT / "scripts" / "droidian.gpg"
BASE = "http://droidian.g.droidian.org/next-upgrade-gbinder/"
GB = "1.1.45-1~git20260513155336.fad75da.next.upgrade.gbinder"
VOLTE_PKGS = {
    "libgbinder": GB, "libgbinder-tools": GB,
    "libgbinder-radio": "1.6.1-1~git20260513161926.ad6d438.next.upgrade.gbinder",
    "libofonobinderpluginext": "1.1.25-1~git20260513163533.9b9e8bd.next.upgrade.gbinder",
    "ofono-binder-plugin": "1.1.25-1~git20260513163533.9b9e8bd.next.upgrade.gbinder",
    "ofono": "1.29+git13-1~git20260513162426.22605f1.next.upgrade.gbinder",
    "ofono-scripts": "1.29+git13-1~git20260513162426.22605f1.next.upgrade.gbinder",
    "ofono-binder-plugin-ext-qti": "0.0.0+git20260513172526.599bb59.next.upgrade.gbinder",
}


def get(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "InRelease").write_bytes(get(BASE + "dists/trixie/InRelease"))
        r = subprocess.run(["gpgv", "--keyring", str(KEYRING), "--output", str(td / "Release"), str(td / "InRelease")],
                           capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if r.returncode:
            sys.exit("InRelease signature check FAILED:\n" + r.stderr)
        print("InRelease signature OK:", [l for l in r.stderr.splitlines() if "Good signature" in l or "using" in l][:2])
        rel = (td / "Release").read_text()
        want = "main/binary-arm64/Packages.gz"
        h = next(l.split() for l in rel.split("SHA256:")[1].splitlines() if l.strip().endswith(want))
        pk_gz = get(BASE + "dists/trixie/" + want)
        if hashlib.sha256(pk_gz).hexdigest() != h[0] or len(pk_gz) != int(h[1]):
            sys.exit("Packages.gz does not match InRelease")
        pk = gzip.decompress(pk_gz).decode()
    index = {}
    for blk in pk.split("\n\n"):
        d = dict(l.split(": ", 1) for l in blk.splitlines() if ": " in l and not l.startswith(" "))
        if d.get("Package"):
            index[(d["Package"], d["Version"])] = d
    for name, ver in VOLTE_PKGS.items():
        d = index.get((name, ver))
        if not d:
            sys.exit(f"{name}={ver} not in the repo index")
        dest = OUT / Path(d["Filename"]).name
        if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest() == d["SHA256"]:
            print("have  ", dest.name); continue
        data = get(BASE + d["Filename"])
        if hashlib.sha256(data).hexdigest() != d["SHA256"] or len(data) != int(d["Size"]):
            sys.exit(f"{dest.name}: SHA256/size mismatch")
        dest.write_bytes(data)
        print("saved ", dest.name, len(data))


if __name__ == "__main__":
    main()
