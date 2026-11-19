#!/usr/bin/env python3
"""Build patched Droidian packages (arm64) in a podman container (qemu-user emulation) matching the phone's userland.

  python3 scripts/build_droidian_debs.py phosh [--jobs N] [--rebuild-image]

phosh: Droidian's phosh 0.49 branch (group/next/phosh-0.49 @ cf38ab5, the exact commit the phone runs) + patches/phosh-0.49/*.patch.
The container uses ONLY the Droidian "rolling" snapshot repo (same signing key, same pin 1002 as the phone), so build-deps and
libraries are the very versions the phone has. Output: releases/droidian-install/debs/*.deb (picked up by build_droidian_install.py).
Needs: podman, qemu-user-static binfmt for aarch64, git, network. Stdlib only. Resumable: reuses the checkout and the image.
Exception to the project's "no containers" rule, explicitly allowed by the user for building arm64 .debs.
"""
import argparse, os, re, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "roms" / "droidian" / "pkgbuild"
OUT = ROOT / "releases" / "droidian-install" / "debs"
BASE_IMAGE = "mirror.gcr.io/library/debian:trixie"   # Docker Hub was unreachable; same image
IMAGE = "bitra-droidian-build:arm64"
KEY = ROOT / "scripts" / "droidian.gpg"             # the phone's /etc/apt/trusted.gpg.d/droidian.gpg (public repo key)
PHOSH = dict(repo="https://github.com/droidian/phosh.git", branch="group/next/phosh-0.49", commit="cf38ab5",
             patches=ROOT / "patches" / "phosh-0.49", suffix="+bitra1")

CONTAINERFILE = """FROM {base}
ENV DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8
RUN rm -f /etc/apt/sources.list /etc/apt/sources.list.d/* /etc/apt/apt.conf.d/docker-* \\
 && printf 'Package: *\\nPin: release o=Droidian\\nPin-Priority: 1002\\n' > /etc/apt/preferences.d/10-droidian
COPY droidian.gpg /etc/apt/trusted.gpg.d/droidian.gpg
RUN printf 'Types: deb\\nURIs: http://releases.droidian.org/snapshots/current/\\nSuites: rolling\\nComponents: main\\nSigned-By: /etc/apt/trusted.gpg.d/droidian.gpg\\n' > /etc/apt/sources.list.d/droidian.sources \\
 && apt-get -o Acquire::AllowInsecureRepositories=false update \\
 && apt-get -y --no-install-recommends --allow-downgrades dist-upgrade \\
 && apt-get -y --no-install-recommends install build-essential devscripts equivs fakeroot git ca-certificates
COPY control /tmp/control
RUN mk-build-deps -i -r -t 'apt-get -y --no-install-recommends' /tmp/control && rm -f /tmp/*.deb
"""


def run(cmd, **kw):
    print("+", " ".join(map(str, cmd)), flush=True)
    r = subprocess.run(cmd, stdin=subprocess.DEVNULL, **kw)
    if r.returncode:
        sys.exit(f"FAILED ({r.returncode}): {' '.join(map(str, cmd))}")
    return r


def checkout(p):
    d = WORK / "phosh"
    if not (d / ".git").exists():
        WORK.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--branch", p["branch"], p["repo"], str(d)])
    run(["git", "-C", str(d), "checkout", "-f", p["commit"]])
    run(["git", "-C", str(d), "clean", "-fdx"])
    for patch in sorted(p["patches"].glob("*.patch")):
        run(["git", "-C", str(d), "apply", "--whitespace=nowarn", str(patch)])
    cl = d / "debian" / "changelog"
    first = cl.read_text().splitlines()[0]
    ver = re.match(r"phosh \((.+?)\)", first).group(1)
    new = f"0.49.0+git20250824213429.{p['commit']}.next.phosh.0.49{p['suffix']}"
    entry = (f"phosh ({new}) experimental; urgency=medium\n\n  * bitra: {', '.join(x.name for x in sorted(p['patches'].glob('*.patch')))}\n\n"
             f" -- bitra <useraccessdenied@users.noreply.github.com>  {time.strftime('%a, %d %b %Y %H:%M:%S +0000', time.gmtime())}\n\n")
    cl.write_text(entry + cl.read_text())
    print(f"changelog: {ver} -> {new}")
    return d, new


def build_image(d, rebuild):
    r = subprocess.run(["podman", "image", "exists", IMAGE])
    if r.returncode == 0 and not rebuild:
        print(f"image {IMAGE} exists (use --rebuild-image to redo)")
        return
    ctx = WORK / "image-ctx"; shutil.rmtree(ctx, ignore_errors=True); ctx.mkdir(parents=True)
    shutil.copy(KEY, ctx / "droidian.gpg"); shutil.copy(d / "debian" / "control", ctx / "control")
    (ctx / "Containerfile").write_text(CONTAINERFILE.format(base=BASE_IMAGE))
    run(["podman", "build", "--platform", "linux/arm64", "-t", IMAGE, str(ctx)])


def build_pkg(d, jobs):
    out = WORK / "out"; shutil.rmtree(out, ignore_errors=True); out.mkdir()
    # dpkg-buildpackage writes the .debs next to the source dir, so mount a parent dir
    parent = WORK / "build-parent"; shutil.rmtree(parent, ignore_errors=True); parent.mkdir()
    shutil.copytree(d, parent / "phosh", symlinks=True)
    script = ("cd /build/phosh && DEB_BUILD_OPTIONS='nocheck parallel=%d' dpkg-buildpackage -us -uc -b -d -Pnodoc" % jobs)
    run(["podman", "run", "--rm", "--platform", "linux/arm64", "-v", f"{parent}:/build:Z", IMAGE, "bash", "-ec", script])
    OUT.mkdir(parents=True, exist_ok=True)
    debs = sorted(parent.glob("*.deb"))
    for f in debs:
        shutil.copy(f, OUT / f.name)
    print("built:"); [print("  ", f.name, f.stat().st_size) for f in debs]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["phosh"])
    ap.add_argument("--jobs", type=int, default=24)
    ap.add_argument("--rebuild-image", action="store_true")
    a = ap.parse_args()
    if not KEY.exists():
        sys.exit(f"missing {KEY}: copy the phone's /etc/apt/trusted.gpg.d/droidian.gpg there")
    d, ver = checkout(PHOSH)
    build_image(d, a.rebuild_image)
    build_pkg(d, a.jobs)


if __name__ == "__main__":
    main()
