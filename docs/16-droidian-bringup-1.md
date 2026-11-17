# 16 — Droidian bring-up #1 (2026-11-18): userspace runs, display HAL does not

Source: user's bringup.tgz (dmesg, journalctl -b, systemctl --failed, mounts, ps, lxc-ls) -> logs/bringup1/ (not tracked).

## Works
- Kernel (Droidian build, KSU/SUSFS-free, `console=tty0`, `androidboot.selinux=permissive`), Droidian initramfs -> Debian rootfs (systemd), LXC `android` container RUNNING (IPs 10.15.19.82 / 192.168.2.15).
- `/vendor` and `/odm` = stock Android-13 images from `super` (erofs via dynpart-vendor/odm, overlay /usr/lib/droid-vendor-overlay on vendor), firmware_mnt (modem), dsp, bt_firmware, persist, metadata, cache mounted. apexes (vndk.v30, runtime, ...) mounted in the container.
- Android side: servicemanager, hwservicemanager, vndservicemanager, allocator@1.0 (hidl), BT HAL (qti), power HAL, sensors multihal, camera provider 2.4, adbd running. Wi-Fi (cnss WLFW connected), ADSP/CDSP/SLPI sysmon up. Android init logs go to the host journal (`init:` lines).
## Fails (systemctl --failed): phosh (crash loop), bluebinder, ofono, ModemManager, nfcd, droidian-fpd, iio-sensor-proxy, lxc-net.
## Root cause of no UI (so far)
- phoc (hwcomposer backend) -> `libminisf.so not found` (warning) and `failed to get hwcomposer service` -> phosh ABRT, restart loop.
- Android `vendor.qti.hardware.display.allocator` and `...composer` exit with status 234 (-EINVAL) right after start; reason not in the journal (need Android logcat). `init: createProcessGroup(...) failed: Read-only file system` for many services (cgroup mount in the container is read-only; possibly harmless, possibly related). Several vendor HALs die with signal 6 (keymaster-4-1, widevine, misc-aidl, charger_hal): abort at start.
## Next data needed
`lxc-attach -n android -- /system/bin/logcat -d -b all > /tmp/logcat.txt`, composer run by hand, `ls -l /dev/dri /dev/kgsl-3d0`, container `getprop`.
