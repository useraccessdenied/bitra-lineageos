#!/usr/bin/env python3
"""Back up critical partitions of the Realme GT Neo 2 (bitra) via adb from OrangeFox.

READ-ONLY on the device (only `dd if=`). Stdlib only; works on Linux/macOS/Windows.

  python3 scripts/backup_partitions.py [--out DIR] [--all] [--max-mb 512] [--serial SER]

Boot OrangeFox, connect USB, `adb devices` must show "recovery". Resumable: partitions already
saved with a matching sha256 are skipped; an incomplete latest run in backups/ is resumed.
"""
import argparse, hashlib, re, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PRIORITY = re.compile(r"^(" + "|".join([
    r"ocdt", r"oplusstanvbk", r"spunvm", r"secdata", r"storsec", r"uefivarstore", r"vm-keystore", r"persist(bak)?", r"modemst[12]", r"oplusreserve\d*", r"devinfo", r"nv(data|ram|cfg)",
    r"fsg(_[ab])?", r"fsc", r"static_nvbk", r"modem(_[ab])?", r"splash", r"logo", r"oplus_sec",
    r"oplusdata", r"oplusdycnvbk", r"apdp(_full)?", r"msadp", r"sec", r"ssd", r"misc", r"frp",
    r"keystore", r"toolsfv", r"mdm1m9kefs[0-9c]*", r"mdm1oemnvbktmp", r"mdm.*efs.*", r"cdt",
    r"engineering_cdt", r"ddr", r"dip", r"limits.*", r"mdmddr", r"multiimgqti", r"mdtp(secapp)?",
    r"vbmeta.*", r"boot(_[ab])?", r"dtbo(_[ab])?", r"vendor_boot(_[ab])?", r"recovery(_[ab])?",
    r"abl(_[ab])?", r"xbl(_[a-z0-9]+)?(_[ab])?", r"xbl_config(_[ab])?", r"tz(_[ab])?", r"hyp(_[ab])?",
    r"aop(_[ab])?", r"devcfg(_[ab])?", r"keymaster(_[ab])?", r"cmnlib(64)?(_[ab])?", r"qupfw(_[ab])?",
    r"uefisecapp(_[ab])?", r"imagefv(_[ab])?", r"multiimgoem(_[ab])?", r"featenabler(_[ab])?",
    r"shrm(_[ab])?", r"cpucp(_[ab])?", r"dsp(_[ab])?", r"bluetooth(_[ab])?",
]) + r")$")
SKIP = re.compile(r"^(userdata|super|cache|metadata|system.*|vendor|product|odm|system_ext|my_.*|vm-bootsys.*)$")
MUST_HAVE = ["ocdt", "persist", "modemst1", "modemst2", "devinfo", "oplusreserve1"]  # warn if absent

ADB = ["adb"]


def adb(*args, check=True, text=True):
    return subprocess.run(ADB + list(args), stdin=subprocess.DEVNULL, capture_output=True, text=text, check=check)


def die(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pick_outdir(arg):
    base = ROOT / "backups"
    if arg:
        return Path(arg).expanduser().resolve()
    if base.is_dir():
        runs = sorted(d for d in base.iterdir() if d.is_dir())
        if runs and not (runs[-1] / ".complete").exists():
            print(f"Resuming incomplete run {runs[-1].name}")
            return runs[-1]
    return base / time.strftime("%Y%m%d-%H%M%S")


def list_partitions():
    script = ('for p in /dev/block/by-name/*; do n=${p##*/}; r=$(readlink -f $p); b=${r##*/}; '
              's=$(cat /sys/class/block/$b/size 2>/dev/null); echo "$n $((s*512))"; done')
    out = adb("shell", script).stdout.replace("\r", "")
    parts = {}
    for line in out.splitlines():
        bits = line.split()
        if len(bits) == 2 and bits[1].isdigit():
            parts[bits[0]] = int(bits[1])
    return parts


def dump_partition(name, size, dest: Path):
    """Stream partition to dest via adb exec-out. Returns (ok, message)."""
    part = dest.with_suffix(".img.part")
    h = hashlib.sha256()
    got = 0
    proc = subprocess.Popen(ADB + ["exec-out", f"dd if=/dev/block/by-name/{name} bs=1048576 2>/dev/null"],
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE)
    with part.open("wb") as f:
        while True:
            chunk = proc.stdout.read(1 << 20)
            if not chunk:
                break
            f.write(chunk); h.update(chunk); got += len(chunk)
    proc.wait()
    if got != size:
        return False, f"size mismatch (got {got}, want {size})"
    digest = h.hexdigest()
    r = adb("shell", f"sha256sum /dev/block/by-name/{name}", check=False)
    dev = r.stdout.split()[0] if r.returncode == 0 and r.stdout.strip() else None
    if dev and dev != digest:
        return False, "hash mismatch vs device"
    part.replace(dest)
    Path(str(dest) + ".sha256").write_text(f"{digest}  {dest.name}\n")
    return True, "verified on device" if dev else "size ok (device hash unavailable)"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out"); ap.add_argument("--serial")
    ap.add_argument("--all", action="store_true", help="also dump every non-priority partition under --max-mb")
    ap.add_argument("--max-mb", type=int, default=512)
    a = ap.parse_args()
    if a.serial:
        ADB.extend(["-s", a.serial])

    try:
        state = adb("get-state", check=False).stdout.strip()
    except FileNotFoundError:
        die("adb not found in PATH")
    if not state:
        die("no adb device. Boot OrangeFox and connect USB.")
    if state != "recovery":
        print(f"WARNING: adb state is '{state}', expected 'recovery'")
    if "uid=0" not in adb("shell", "id").stdout:
        die("adb shell is not root")

    out = pick_outdir(a.out)
    (out / "parts").mkdir(parents=True, exist_ok=True)
    (out / "info").mkdir(exist_ok=True)
    for p in (out / "parts").glob("*.part"):
        p.unlink()
    print(f"Output: {out}")

    # device info
    for fname, cmd in [("getprop.txt", ["shell", "getprop"]), ("by-name.txt", ["shell", "ls", "-l", "/dev/block/by-name"]),
                       ("proc-partitions.txt", ["shell", "cat", "/proc/partitions"]),
                       ("cmdline.txt", ["shell", "cat", "/proc/cmdline"]), ("mounts.txt", ["shell", "cat", "/proc/mounts"])]:
        (out / "info" / fname).write_text(adb(*cmd, check=False).stdout)

    parts = list_partitions()
    if not parts:
        die("could not enumerate /dev/block/by-name")
    (out / "info" / "parts.txt").write_text("".join(f"{n} {s}\n" for n, s in parts.items()))

    # decide what to dump
    plan = []
    for name, size in parts.items():
        if SKIP.match(name):
            print(f"skip  {name} (big/regenerable)")
        elif PRIORITY.match(name) or (a.all and size <= a.max_mb << 20):
            plan.append((name, size))
        else:
            print(f"skip  {name} ({size >> 20} MiB, not in priority list)")
    missing = [n for n in MUST_HAVE if n not in parts]
    if missing:
        print(f"WARNING: expected partitions not found on this device: {', '.join(missing)}")
    print(f"\nPlanned: {len(plan)} partitions, {sum(s for _, s in plan) >> 20} MiB\n")

    done, failed = [], []
    for i, (name, size) in enumerate(plan, 1):
        dest = out / "parts" / f"{name}.img"
        shaf = Path(str(dest) + ".sha256")
        if dest.exists() and shaf.exists() and dest.stat().st_size == size \
                and sha_file(dest) == shaf.read_text().split()[0]:
            print(f"[{i}/{len(plan)}] have  {name}")
            done.append(name); continue
        print(f"[{i}/{len(plan)}] dump  {name:<22} {size >> 10:>8} KiB ... ", end="", flush=True)
        ok, msg = dump_partition(name, size, dest)
        print(("ok " if ok else "FAILED ") + msg)
        (done if ok else failed).append(name)

    # GPT headers of every UFS LUN
    for lun in "abcdef":
        f = out / "info" / f"gpt-sd{lun}.bin"
        if f.exists() or adb("shell", f"[ -e /dev/block/sd{lun} ]", check=False).returncode != 0:
            continue
        r = subprocess.run(ADB + ["exec-out", f"dd if=/dev/block/sd{lun} bs=1048576 count=1 2>/dev/null"],
                           stdin=subprocess.DEVNULL, capture_output=True)
        f.write_bytes(r.stdout)

    # sanity: everything planned must exist on disk and verify
    on_disk = {p.name[:-4] for p in (out / "parts").glob("*.img")}
    absent = [n for n, _ in plan if n not in on_disk]
    if failed or absent or len(done) != len(plan):
        print(f"\nINCOMPLETE: {len(done)}/{len(plan)} saved. Failed: {failed}; absent: {absent}. Re-run to retry.")
        sys.exit(2)
    (out / "SHA256SUMS").write_text("".join(
        f"{Path(str(p) + '.sha256').read_text().split()[0]}  {p.name}\n" for p in sorted((out / 'parts').glob('*.img'))))
    (out / ".complete").touch()
    total = sum(p.stat().st_size for p in (out / "parts").glob("*.img")) >> 20
    print(f"\nDONE. {len(done)}/{len(plan)} partitions, {total} MiB in {out}")
    print("Copy this folder to a second location OFF this machine. Write down your IMEIs (*#06# or retail box).")


if __name__ == "__main__":
    main()
