# 07 — First A16 build: artifacts and flashing notes

Build: `lineage-23.2-20261108-UNOFFICIAL-bitra`, **userdebug** (test-keys, adb root available), built 2026-11-09 on the host in ~16 min for the final incremental run (full cold build ≈ 1h 20m wall incl. fixes).
Copied to `releases/a16/` (originals in `roms/lineageos/a16/out/target/product/bitra/`).

| File | Size | Notes |
|---|---|---|
| `lineage-23.2-20261108-UNOFFICIAL-bitra.zip` | 2.07 GB | Recovery-flashable (brotli `.new.dat.br`, dynamic partitions op list). sha256 `2d0705e3637841fa99ed5472e31d44896b2cc1e5f3290da82bb4759fc1c134cd` |
| `boot.img` / `dtbo.img` | 96 MiB / 24 MiB | also inside the zip |
| `recovery.img` | 128 MiB | Lineage recovery (zip also carries it); user plans OrangeFox instead |
| `vbmeta.img` | 64 KiB | for AVB handling |

## Local patches needed to build (must be re-applied after a resync of build/soong)
- `scripts/patches/build-soong-allow-oneplus-odm.patch` — allows `net.oneplus.odm` and `oplus.content.res` in the boot-jar package allow list (oplus-fwk).
- git-lfs objects must be pulled (webview APKs) — `03-sync.sh` now does it.

## Suggested flash procedure (NOT yet performed; this is the user's call)
1. **Back up first** — run `scripts/backup_partitions.py` from OrangeFox (adb root; saves to `backups/<timestamp>/`, hash-verified, resumable; covers `ocdt`, persist, modemst*, oplusreserve*, devinfo, boot chain, GPT). **NEVER flash an `ocdt.img` from a guide/another phone** (RMX3370 users lost IMEI + got 5-min reboots this way; xdaforums thread 4778230). Original list (adb root or EDL): `persist`, `modemst1`, `modemst2`, `oplusreserve*`, `devinfo`, plus userdata if needed. Keep `firmware/EDL/` handy.
2. Flash matching firmware zip (`firmware/<region>/Firmware_*.zip`) from recovery (the ROM threads require F.20 IN / F.18 EU / F.18 GLOBAL).
3. Install recovery (OrangeFox or this `recovery.img`): `fastboot flash recovery recovery.img` (bitra is non-A/B — confirmed on hardware; no slot flags needed).
4. ~~`fastboot flash vbmeta ...`~~ **NOT needed** — verified 2026-11-16: with the bootloader unlocked the A16 build booted with the stock `vbmeta` untouched. Only flash it if a bootloop/AVB warning appears (stock copies are in `backups/20261116-213951/parts/vbmeta*.img`).
5. In recovery: format data (required coming from another ROM), then sideload/flash the ROM zip, reboot.
6. First boot can take several minutes. Collect `adb logcat -b all`, `adb shell dmesg`, `/sys/fs/pstore/*` on any bootloop.

## Known risks of this first build
- Never booted on hardware; unknown: camera/FP/face (firmware must match), VoLTE, audio, DRM L1.
- userdebug + test-keys: fine for bring-up, not for daily use; use `user` + own release keys later (docs/03 Phase 6).
- Vendor blobs came from Axion/bijoyv9 repos (third-party); see docs/05 risk #1.
