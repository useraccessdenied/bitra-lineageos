#!/usr/bin/env python3
"""Build a RAM-boot image for the mainline (roms/mainline) kernel on bitra. Stdlib only.

Reuses scripts/build_debug_initramfs.py (busybox + NCM gadget initramfs, header v2 mkbootimg) but:
  * the DTB passed to ABL is Droidian's base kona tree (releases/droidian-kernel/dtb): ABL only accepts
    trees it can merge the vendor dtbo into; the kernel swaps in its embedded tree (BITRA_DTB_SHIM).
  * the heartbeat is quiet so the on-screen early console (earlycon=efifb) is not scrolled away.

  python3 scripts/build_mainline_boot.py NAME [--cmdline-extra STR]
Output: releases/mainline-debug/NAME.img
Always boot via `ssh mac to-fastboot` (a manually entered fastboot makes ABL refuse images: 'Load Error').
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_debug_initramfs as b

ROOT = b.ROOT
b.INIT = b.INIT.replace(
    'while true; do log "alive $(cat /proc/uptime | cut -d\' \' -f1)s"; sleep 10; done',
    'while true; do sleep 600; log "alive $(cat /proc/uptime | cut -d\' \' -f1)s"; done')
MAIN = ROOT / "roms/mainline/out/arch/arm64/boot"
name = sys.argv[1]
extra = "clk_ignore_unused pd_ignore_unused ignore_loglevel panic=0 consoleblank=0 earlycon=efifb keep_bootcon"
rest = sys.argv[2:]
if rest[:1] == ["--cmdline-extra"]:
    extra = rest[1]
sys.argv = ["x", "--kernel", str(MAIN / "Image.gz"), "--dtb", str(ROOT / "releases/droidian-kernel/dtb"),
            "--out", str(ROOT / "releases/mainline-debug"), "--boot-name", name + ".img",
            "--cmdline-extra", extra]
b.main()
