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

## Troubleshooting: `fastboot boot boot.img` -> `FAILED (usb_write failed with status e00002ed)` (user report)
0xe00002ed = macOS IOKit kIOReturnNotResponding (USB transfer stalled). Our earlier working RAM image (debug-boot.img) was 59 MB; boot.img is 77 MB (raw 58 MB kernel + 17 MB initramfs). Hypothesis: size/transport. Built `boot-gz.img` (41 MB, gzip kernel, sha256 5376097893739b931b2f7eb0da973f91b776eca43ba5a9c11da7cd4cf2bfa471) — try it first. Also: direct port (no hub), another cable, verify `shasum -a 256`, phone in bootloader fastboot (not fastbootd), retry.

## Update: no USB adapter from Droidian boot images (user report); early-gadget builds
User: after the cable fix, debug-boot.img still gives `en9`, but boot.img / boot-gz.img (Droidian initramfs) gave no adapter. Droidian's own USB comes only from its panic handler, so a hang earlier (or a failing gadget write) shows nothing. Rebuilt both boot images with our known-good NCM gadget as the FIRST init-premount script (`scripts/init-premount/bitra-usb`, 192.168.2.15, DHCP .20-.30, telnet :23, product "droidian-initrd"). New hashes: boot.img 1a502d80…c7149c, boot-gz.img fce28e17…c5b39f.

## Update 2: ramdisk/dtb overlap (likely root cause of "no adapter")
Header layout was ramdisk@0x1000000 (16.09 MiB -> ends 0x201603d) and dtb@0x1f00000 => 1.09 MiB overlap (debug-boot.img's ramdisk was 1 MB so it fit). Moved ramdisk_offset to 0x2100000 (after the dtb end 0x205d57f). New hashes: boot.img 0756c069…3f27f2 (73 MiB), boot-gz.img 2f1323a6…78dfd7 (41 MiB). If this still fails, fallback = shrink the initramfs (drop hwdb/fonts/plymouth, ~12 MB) so the original offsets fit.

## Update 3 (2026-11-17): the dmesg the user sent was from debug-boot.img, not Droidian
droidian-dmesg.txt + pasted output: `Freeing initrd memory: 972K` (Droidian initrd is ~17 MB), `bitra-debug: …` heartbeats, cmdline lacks `selinux=0 androidboot.selinux=permissive` => debug-boot.img was booted; Droidian images still give no adapter. Next experiments:
- boot.img a9942aef…132219 / boot-gz.img bce9de62…a21cbde: gadget now started from the TOP of Droidian's /init (after /dev mounts; kmsg "bitra: early init hook").
- releases/droidian-debug/debug-big.img a6c1d516…f72ae: debug init + 16 MB random padding ramdisk @0x2100000 (same layout as Droidian images) => tests "big ramdisk/layout breaks boot" vs "Droidian init hangs".
Reading: debug-big works + Droidian images don't => Droidian's /init stalls before our hook; debug-big fails => size/layout problem at the bootloader/kernel level.

## Update 4: results so far + bisect images
- debug-big.img (17 MB ramdisk @0x2100000, raw kernel) WORKS: size/layout are fine. (`Freeing initrd memory: 17364K`.) No ramoops region in DT => pstore gives no previous-boot log.
- Droidian-initrd images (boot.img, boot-gz.img) show no adapter even with the gadget hooked at the top of /init. Bisect images:
  1. debug-big-selinux.img f59e828b…18b42 = debug-big + cmdline `selinux=0 androidboot.selinux=permissive` -> tests the cmdline.
  2. releases/droidian-install/boot-dbg.img 998d3faef5e21e5f711dbee595f157b118927cf1b45d23d91e7f7a952280d7d2 = Droidian initramfs (repacked) but /init = our gadget+wait script; real init kept as /init.droidian -> tests that the repacked initramfs boots, and lets us run `sh -x /init.droidian > /tmp/d.log 2>&1 &` by hand and read the trace over telnet.
- Also check `system_profiler SPUSBDataType` during failing Droidian boots (USB device may enumerate without en9).

## Update 5 (2026-11-17): selinux=0 crash hypothesis -> KSU/SUSFS removed from the Droidian kernel
debug-big-selinux.img (debug-big + `selinux=0 androidboot.selinux=permissive`) did NOT enumerate => the extra cmdline breaks boot on the previous Droidian kernel. Likely cause: ReSukiSU (selinux/rules.c) dereferences selinux_state.ss, NULL when SELinux is disabled -> oops on first /init exec. Halium requires selinux=0 (CONFIG_SECURITY_SELINUX_BOOTPARAM_VALUE=0 in its checker). Per user: KSU and SUSFS removed ENTIRELY from the Droidian kernel: branch `droidian` of the Axion kernel fork is now upstream 5029be34d + 2 small fixes (extract-cert OpenSSL3 guard, fanotify old_memcg), no KSU/SUSFS/Droidspaces code (force-pushed). Clean build: .config has 0 KSU/SUSFS options (the grep hit was CONFIG_NETFILTER_XT_TARGET_CHECKSUM).
New images (clean kernel): releases/droidian-debug/debug-big-selinux.img (sha256 in releases/droidian-debug/SHA256SUMS), releases/droidian-install/boot-dbg.img dc13c4fe…c5e99, boot.img 12feed42…cb6d, boot-gz.img 8c9b2fce…08ea0.

## Update 6 (2026-11-17): all four images enumerate with the KSU/SUSFS-free kernel
User: all images now boot and give the NCM adapter => root cause confirmed: ReSukiSU + `selinux=0` oops. boot-dbg.img trace (`sh -x /init.droidian > /tmp/d.log`) reaches `mountroot` -> local-top (cryptopensc/lvm2/cryptroot) -> local-premount (resume) and then stops at `exec &>/dev/kmsg` (scripts/halium line 626 redirects ALL later output, incl. the trace, to /dev/kmsg). The rest of the Droidian init is therefore in dmesg: use `dmesg | grep -vE "OPLUS_CHG|mp2650|WLCHG|wdog_util|gauge|bq27541|get prop" | tail -150` (look for `initrd:` lines). The job showed "Terminated" (init ended/killed).

## Update 7 (2026-11-17): Test 2 go-ahead (user chose to wipe Lineage)
User output was a plain boot of boot-dbg.img (uptime 14 s; `/init.droidian` not started yet), so no Droidian init lines yet; user decided to proceed with Test 2. Recommended order on the Mac: (0) copy releases/a16-latest zip + releases/recovery/orangefox to the Mac for rollback; (1) verify sha256 of super.img/userdata.img/boot-dbg.img; (2) `fastboot flash super super.img`; (3) `fastboot flash userdata userdata.img`; (4) `fastboot boot boot-dbg.img`, then in the NCM shell `sh -x /init.droidian > /tmp/d.log 2>&1 &` and watch `dmesg | grep "initrd:"`. The boot partition still holds Lineage's kernel, so every boot is a RAM `fastboot boot` until we flash boot.

## Update 8 (2026-11-17): `selinux=0` breaks ALL block-device mounts on this kernel (ENOENT, no kernel message)
Test 2 flashed fine (super.img, userdata.img: blkid shows sda11 ext4, clean). Droidian initrd got to mountroot but `mount: mounting /dev/sda11 on /tmpmnt failed: No such file or directory` — also for /dev/sda7 and busybox mount. Bisect (debug init, RAM boots): Lineage kernel (no selinux param) mounts OK; first Droidian-config kernel (no selinux param) mounts OK; clean Droidian kernel + `selinux=0` => rc=255 ENOENT; + `androidboot.selinux=permissive` => OK. So only `selinux=0` is bad (mechanism not root-caused; this Android 4.19 kernel with backported fs_context API; `source` is lost when SELinux is disabled at boot). Fix: cmdline now `androidboot.selinux=permissive` only (SELinux stays enabled with no policy; Android init in the container sets permissive). Rebuilt boot-dbg.img / boot-gz.img / boot.img. userdata.img/super.img unchanged. Note boot-dbg.img can't complete a full boot (the real init is not PID 1 there); use boot-gz.img / boot.img for the real attempt.
