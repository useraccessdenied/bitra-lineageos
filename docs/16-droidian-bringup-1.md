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

## Bring-up #2 findings (2026-11-18) — ROOT CAUSE of the HAL aborts
logcat (bringup2.tgz): `servicemanager/hwservicemanager: getDeviceHalManifest: VINTF parse error: Illformed file: /odm/etc/vintf/manifest/device_manifest_subsys.xml: ... Could not parse text "1" in element <version>` (36x). The Android-11 (api30) libvintf cannot parse the Android-13 odm's `<hal format="aidl"> <version>1</version>` => device manifest rejected => hwservicemanager declares NO HAL => `HidlServiceManagement: Service X must be in VINTF manifest in order to register/get` for ~every HAL => registerAsService = -2147483648 => aborts: display allocator@3.0 / composer@3.0, keymaster 4.1, wifi 1.4, usb 1.2, nfc, drm widevine/clearkey, capabilityconfigstore, secure_element, ... (phoc then "failed to get hwcomposer service" -> phosh crash loop).
Secondary (maybe harmless): `libprocessgroup: Failed to make and chown /acct/uid_1000: Read-only file system`; `couldn't write pid to /dev/cpuset/display/tasks: No such file`.
Fix: scripts/vintf_sanitize.py removes the AIDL <hal> entries from odm (22 files) and vendor (2 files) manifests into overlay trees; rootfs: /usr/lib/droid-odm-overlay + /usr/lib/droid-vendor-overlay/etc/vintf; mount-android.sh mounts the odm overlay AFTER the fstab loop (which mounts the real odm). Helper `bitra-collect` (rootfs) gathers logs. Delivered as releases/droidian-install/vintf-live-patch.tgz (apply on the running phone over /) and in userdata.img (full image, rebuilt).
