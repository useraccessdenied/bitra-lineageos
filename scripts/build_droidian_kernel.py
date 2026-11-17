#!/usr/bin/env python3
"""Host-native build of the bitra kernel with Halium/Droidian config fragments (no containers).

Uses the AOSP clang + gcc-4.9 binutils prebuilts already in the a16 tree, builds out-of-tree so the
kernel source tree stays clean. Stdlib only.

  python3 scripts/build_droidian_kernel.py [--tree a16] [--out DIR] [--jobs N] [--no-droidspaces] [--clean]

Output (default roms/droidian/kernel-out): .config, arch/arm64/boot/Image.gz, dtbs, and a config report.
Fragments: scripts/kernel-config/{halium,droidian}.config applied on top of vendor/kona-perf_defconfig.
Resumable (incremental make).
"""
import argparse, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRAGS = ROOT / "scripts" / "kernel-config"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", default=str(ROOT / "roms" / "droidian" / "kernel"),
                    help="separate Droidian kernel checkout (branch 'droidian'); NOT the Lineage kernel trees")
    ap.add_argument("--tree", default="a16", help="Lineage tree used ONLY for its clang/gcc/make prebuilts")
    ap.add_argument("--out", default=str(ROOT / "roms" / "droidian" / "kernel-out"))
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    ap.add_argument("--defconfig", default="vendor/kona-perf_defconfig")
    ap.add_argument("--clang", default="clang-r563880c")
    ap.add_argument("--clean", action="store_true")
    a = ap.parse_args()

    aosp = ROOT / "roms" / "lineageos" / a.tree
    src = Path(a.src).resolve()
    out = Path(a.out).resolve()
    clang_bin = aosp / "prebuilts" / "clang" / "host" / "linux-x86" / a.clang / "bin"
    gcc_bin = aosp / "prebuilts" / "gcc" / "linux-x86" / "aarch64" / "aarch64-linux-android-4.9" / "bin"
    gcc32_bin = aosp / "prebuilts" / "gcc" / "linux-x86" / "arm" / "arm-linux-androideabi-4.9" / "bin"
    tools = aosp / "prebuilts" / "build-tools" / "linux-x86" / "bin"
    for p in (src / "Makefile", clang_bin / "clang", gcc_bin, tools / "make"):
        if not p.exists():
            sys.exit(f"missing: {p}")
    if a.clean and out.exists():
        subprocess.run(["rm", "-rf", str(out)], check=True)
    out.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["PATH"] = f"{clang_bin}:{gcc_bin}:{gcc32_bin}:{tools}:" + env["PATH"]
    env["LC_ALL"] = "C"
    mk = [str(tools / "make"), f"-j{a.jobs}", "-C", str(src), "-I", str(src), f"O={out}", "ARCH=arm64",
          "CC=clang", "CLANG_TRIPLE=aarch64-linux-gnu-", "CROSS_COMPILE=aarch64-linux-android-",
          "CROSS_COMPILE_ARM32=arm-linux-androideabi-", "LD=ld.lld", "AR=llvm-ar", "NM=llvm-nm",
          "OBJCOPY=llvm-objcopy", "OBJDUMP=llvm-objdump", "STRIP=llvm-strip", "HOSTCC=clang", "HOSTCXX=clang++", "HOSTCFLAGS=-DOPENSSL_NO_ENGINE"]

    def run(args, what):
        t = time.time()
        print(f"==> {what}", flush=True)
        r = subprocess.run(args, env=env, stdin=subprocess.DEVNULL)
        if r.returncode:
            sys.exit(f"FAILED ({what}), exit {r.returncode}")
        print(f"    done in {time.time() - t:.0f}s", flush=True)

    cfg = out / ".config"
    if not cfg.exists():
        run(mk + [a.defconfig], f"defconfig {a.defconfig}")
    frags = [FRAGS / "halium.config", FRAGS / "droidian.config"]
    oplus = src / "arch/arm64/configs/vendor/oplus.config"  # Lineage: TARGET_KERNEL_CONFIG = kona-perf_defconfig + oplus.config
    run([str(src / "scripts/kconfig/merge_config.sh"), "-m", "-O", str(out), str(cfg), str(oplus), *map(str, frags)],
        "merge Halium/Droidian fragments")
    run(mk + ["olddefconfig"], "olddefconfig")
    run(mk + ["Image.gz", "dtbs"], "build Image.gz + dtbs")

    img = out / "arch/arm64/boot/Image.gz"
    print(f"\nKernel: {img} ({img.stat().st_size >> 20} MiB)")
    chk = ROOT / "scripts" / "check_kernel_config.py"
    rep = out / "config-report.txt"
    with rep.open("w") as f:
        for fr in frags:
            f.write(f"##### {fr.name}\n")
            f.write(subprocess.run([sys.executable, str(chk), str(fr), str(cfg)], capture_output=True, text=True).stdout)
    print(f"Config report: {rep}")


if __name__ == "__main__":
    main()
