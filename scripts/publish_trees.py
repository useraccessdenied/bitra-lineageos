#!/usr/bin/env python3
"""Publish bitra tree changes to the user's GitHub account (stdlib only; uses the gh CLI).

Modified *source* trees (device/hardware/kernel) are forked from their upstream maintainers
(history + author attribution preserved) and our work is pushed on branch `bitra/<tree>`.
Projects we only tweak lightly or that hold proprietary blobs (frameworks/base, build/soong,
vendor/*) are NOT pushed; their diffs are saved as patches in patches/<tree>/.

  python3 scripts/publish_trees.py            # dry run: show what would happen
  python3 scripts/publish_trees.py --go       # fork, commit, push, write patches/manifests

Idempotent: re-running commits only new changes and re-pushes.
"""
import argparse, glob, os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOS = ROOT / "roms" / "lineageos"
GH = next(iter(glob.glob(os.path.expanduser("~/.local/share/mise/installs/gh/*/gh_*/bin/gh"))), "gh")
OWNER = "useraccessdenied"
NOREPLY = f"{OWNER}@users.noreply.github.com"
TRAILER = "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
KSU_URL = "https://github.com/ReSukiSU/ReSukiSU.git"
AI_NOTICE = """# AI usage disclosure

The local changes on the `bitra/*` branches of this repository (everything after the upstream
history) were written with substantial help from an AI assistant (Claude Code, Anthropic) working
under the direction of the repository owner. They are **experimental, only partly tested on
hardware, and provided as-is with no warranty**. Review the diffs before using them and flash at
your own risk. Commits made with AI assistance carry a `Co-Authored-By: Claude` trailer.

All upstream history, code and authorship (the original device/kernel maintainers) is preserved
unmodified; this fork only adds commits on top. See the tracking repository's ATTRIBUTION.md.
"""

# (tree, path, upstream "owner/repo", our fork name)
FORKS = [
    ("a16", "device/realme/sm8250-common", "AxionAOSP-devices/android_device_realme_sm8250-common", "android_device_realme_sm8250-common-axion"),
    ("a16", "hardware/oplus", "AxionAOSP-devices/android_hardware_oplus", "android_hardware_oplus-axion"),
    ("a16", "kernel/realme/sm8250", "AxionAOSP-devices/android_kernel_realme_sm8250", "android_kernel_realme_sm8250-axion"),
    ("a17", "device/realme/sm8250-common", "SM8250-Common/android_device_realme_sm8250-common", "android_device_realme_sm8250-common-sm8250common"),
    ("a17", "hardware/oplus", "SM8250-Common/android_hardware_oplus", "android_hardware_oplus-sm8250common"),
    ("a17", "kernel/realme/sm8250", "SM8250-Common/android_kernel_realme_sm8250", "android_kernel_realme_sm8250-sm8250common"),
]
PATCH_ONLY = ["build/soong", "frameworks/base", "vendor/oplus/camera", "vendor/realme/sm8250-common"]
CRED = ["-c", f"credential.helper=!{GH} auth git-credential"]


def run(cmd, cwd=None, check=True, capture=True):
    r = subprocess.run(cmd, cwd=cwd, text=True, capture_output=capture, stdin=subprocess.DEVNULL)
    if check and r.returncode:
        sys.exit(f"FAILED: {' '.join(map(str, cmd))}\n{r.stdout}{r.stderr}")
    return r


def git(repo, *a, check=True):
    return run(["git", *CRED, *a], cwd=repo, check=check)


def commit_msg(tree, path):
    what = {
        "a16": "Android 16 / LineageOS 23.2 bitra build: KernelSU (ReSukiSU) + SUSFS, Droidspaces config, OplusCamera removal, brightness/UDFPS fixes",
        "a17": "Android 17 / LineageOS 24.0 bitra build: KernelSU (ReSukiSU) + SUSFS, Droidspaces config, Face HAL removal, VINTF/treble fixes",
    }[tree]
    return (f"bitra {tree}: local changes for {path}\n\n{what}.\n"
            "Upstream history and authorship are preserved; see ATTRIBUTION.md in the tracking repo.\n\n" + TRAILER)


def publish_fork(tree, path, upstream, fork, go):
    repo = LOS / tree / path
    branch = f"bitra/{tree}"
    st = git(repo, "status", "--porcelain").stdout
    print(f"\n[{tree}] {path} -> {OWNER}/{fork}:{branch}  ({len(st.splitlines())} changed paths)")
    for l in st.splitlines()[:40]:
        print("   ", l)
    if not go:
        return
    if run([GH, "repo", "view", f"{OWNER}/{fork}"], check=False).returncode:
        run([GH, "repo", "fork", upstream, "--clone=false", "--fork-name", fork])
    url = f"https://github.com/{OWNER}/{fork}.git"
    if git(repo, "remote", "get-url", "mine", check=False).returncode:
        git(repo, "remote", "add", "mine", url)
    cur = git(repo, "branch", "--show-current").stdout.strip()
    if cur != branch:
        git(repo, "checkout", "-B", branch)
    (repo / "AI_DISCLOSURE.md").write_text(AI_NOTICE)
    git(repo, "add", "-f", "AI_DISCLOSURE.md")
    if (repo / "KernelSU" / ".git").exists():  # KernelSU stays a pinned submodule, not copied files
        sha = git(repo / "KernelSU", "rev-parse", "HEAD").stdout.strip()
        (repo / ".gitmodules").write_text(f'[submodule "KernelSU"]\n\tpath = KernelSU\n\turl = {KSU_URL}\n')
        git(repo, "add", "-A", "--", ".", ":!KernelSU")
        git(repo, "add", "-f", ".gitmodules")
        git(repo, "update-index", "--add", "--cacheinfo", f"160000,{sha},KernelSU")
    else:
        git(repo, "add", "-A")
    if git(repo, "diff", "--cached", "--quiet", check=False).returncode:
        git(repo, "-c", f"user.name={OWNER}", "-c", f"user.email={NOREPLY}", "commit", "-q", "-m", commit_msg(tree, path))
    git(repo, "push", "-u", "mine", branch)
    print("    pushed", url)


def save_patches(go):
    for tree in ("a16", "a17"):
        out = ROOT / "patches" / tree
        for path in PATCH_ONLY:
            repo = LOS / tree / path
            if not (repo / ".git").exists():
                continue
            run(["git", "add", "-N", "."], cwd=repo, check=False)
            diff = run(["git", "diff", "HEAD", "--binary"], cwd=repo).stdout
            run(["git", "reset", "-q"], cwd=repo, check=False)
            name = path.replace("/", "_") + ".patch"
            print(f"[patch] {tree}/{path}: {len(diff)} bytes" + ("" if diff else " (no changes)"))
            if go and diff:
                out.mkdir(parents=True, exist_ok=True)
                (out / name).write_text(diff)


def write_manifests(go):
    for tree in ("a16", "a17"):
        src = LOS / tree / ".repo" / "local_manifests" / "bitra.xml"
        text = src.read_text()
        text = text.replace("</manifest>", "").rstrip() + "\n"
        text = re.sub(r'(<manifest>\s*)', r'\1\n    <remote name="mine" fetch="https://github.com/%s" revision="bitra/%s" />\n' % (OWNER, tree), text, count=1)
        for t, path, upstream, fork in FORKS:
            if t != tree:
                continue
            text = re.sub(r'<project path="%s" name="[^"]+" remote="[^"]+"' % re.escape(path),
                          f'<project path="{path}" name="{fork}" remote="mine"', text)
        text += "\n</manifest>\n"
        print(f"[manifest] manifests/{tree}/bitra.xml")
        if go:
            d = ROOT / "manifests" / tree
            d.mkdir(parents=True, exist_ok=True)
            (d / "bitra.xml").write_text(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()
    if run([GH, "auth", "status"], check=False).returncode:
        sys.exit("gh not authenticated")
    for f in FORKS:
        publish_fork(*f, go=a.go)
    save_patches(a.go)
    write_manifests(a.go)
    print("\nDONE" if a.go else "\nDry run only; re-run with --go")


if __name__ == "__main__":
    main()
