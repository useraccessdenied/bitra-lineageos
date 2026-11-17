# 15 — Droidian install artifacts + Mac procedure (2026-11-17)

Built by `python3 scripts/build_droidian_install.py` (rootless, host-native) into `releases/droidian-install/`:
| File | What | SHA-256 |
|---|---|---|
| boot.img (74 MiB) | our Halium/Droidian kernel + official Droidian initramfs (panic/telnet patched RNDIS->NCM), cmdline = stock + `selinux=0` | d87066de0b52e9eadcef4fd8dd8298a3a0b4a4c2a22b33552e07b3b712159b8b |
| super.img (1.7 GB sparse) | lpmake: stock Android-13 vendor + odm only, stock geometry (10200547328 B, 1 slot) | 6a1961ce70d2fc9e7173674f7dd13f28722317294df03e24a7a278acee3d4127 |
| userdata.img (3.9 GB sparse) | ext4 (14 GB, grows to fill partition on first boot) containing `rootfs.img` (official Droidian api30 rootfs, 8 GB, patched) + android-rootfs.img symlink | 805207fbe3cb539474e47b80998c680367bfd00251d585940d830483ce787c2f |

Rootfs patches: `bitra-usb-debug.service` (temporary: host-side USB CDC-NCM gadget, `usb0` 10.15.19.82/24, udhcpd 10.15.19.100-110, **unauthenticated root telnet :23** — remove before real use) and `mount-android.sh` (exposes dynamic partitions as /dev/disk/by-partlabel/* so odm is mounted). Sources: official Droidian release 101.20261023 (rootfs-api30 zip sha256 afd357eb…db5c5 verified).

## Test 1 — safe, NO wipe, nothing flashed (RAM boot with the Droidian initramfs)
Current Lineage userdata is f2fs/encrypted so Droidian's initrd cannot find a rootfs and drops to its **panic shell over USB** — that is the expected result and proves kernel+initramfs+USB.
1. `adb reboot bootloader` ; `fastboot boot boot.img`
2. On the Mac (wait ~30 s): `system_profiler SPUSBDataType | grep -B2 -A10 -i "Failed to boot"` (vendor "Halium initrd"), `ifconfig -a` (new enN), the initrd runs udhcpd so the Mac should get 192.168.2.x by DHCP, else `sudo ifconfig enN 192.168.2.20 netmask 255.255.255.0 up`.
3. `nc 192.168.2.15 23` -> shell (busybox). Useful: `cat /proc/cmdline`, `ls /dev/disk/by-partlabel`, `dmesg | grep initrd`, `cat /proc/mounts`.
4. Send me what you see. Reboot: vol-up+power 6 s.

## Test 2 — DESTRUCTIVE: wipes Lineage (super + userdata). Do only after Test 1 and a backup check
Before: confirm backups/20261116-213951 is copied off the build machine; the phone's user data will be erased.
```
fastboot flash super super.img
fastboot flash userdata userdata.img
fastboot boot boot.img          # RAM boot first; nothing else is changed
```
Expected: kernel -> initramfs mounts /tmpmnt (userdata ext4) -> loop-mounts rootfs.img -> switch_root -> systemd -> bitra-usb-debug brings USB up: Mac sees `droidian-bitra` (1d6b:0104), DHCP 10.15.19.1xx, `nc 10.15.19.82 23` gives a root shell (bash). Display/UI likely NOT up yet (hybris/hwcomposer is the next stage). Useful: `systemctl --failed`, `journalctl -b | tail -100`, `mount | grep -E "vendor|odm"`, `lxc-ls -f`, `ls /vendor`.
When satisfied: `fastboot flash boot boot.img` makes it permanent (boot partition currently holds Lineage's kernel).

## Rollback to Lineage (from the Mac)
Boot OrangeFox (releases/recovery/orangefox), `adb sideload` releases/a16-latest/lineage-23.2-20261117-UNOFFICIAL-bitra.zip (same procedure as the first install; recreates dynamic partitions), format data, reboot. Last resort: backups/20261116-213951 partitions / EDL package in firmware/EDL.

## Caveats (unverified)
- Whether `fastboot flash super` of a sparse super.img works from bootloader fastboot on this Oplus abl (it should; super is a normal GPT partition). If it refuses, report the exact error.
- Droidian initrd resize2fs on first boot expands userdata to ~225 GB (takes a while on first boot).
- SELinux is disabled by cmdline; no AppArmor in this kernel.
