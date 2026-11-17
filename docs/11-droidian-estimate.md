# 11 — Droidian port estimate (2026-11-17)

Droidian = Debian + Halium (Android vendor stack via libhybris) + Phosh. Reuses the phone's Android vendor/odm blobs, so no mainline driver work (contrast docs/09). Sources: docs.droidian.org/porting-guide (+ kernel-compilation, image-creation, debugging-tips). Unverified: whether Droidian already ships any sm8250 / Realme device (search returned no device list) — check droidian.org device list / community chat BEFORE starting.

## What Droidian needs (from its docs)
- Device launched with Android 9+; Halium-compliant kernel (config fragments `halium.config` + `droidian.config`, device fragments on top). Kernel source must be a git repo; built with Droidian's cross toolchain.
- Generic Droidian system image for devices launched on 8.1+; vendor/odm come from the device (must match the Halium system API level — UNVERIFIED which Halium version supports our vendor).
- Boot via halium-boot/initramfs; debug via USB RNDIS/telnet.

## State of our kernel (4.19.325, built .config of the A16 Lineage kernel)
Present: NAMESPACES, NET_NS, UTS_NS, CGROUP_FREEZER, MEMCG, OVERLAY_FS, VETH, BRIDGE, NETFILTER, BINDERFS (+binder devices binder/hwbinder/vndbinder), USB_CONFIGFS_F_FS, DM_VERITY.
Missing (typical Halium requirements; fixable via fragments): PID_NS, USER_NS, CGROUP_DEVICE, CGROUP_PIDS, DEVTMPFS, FHANDLE, SQUASHFS, SYSVIPC, AUTOFS4_FS, USB_CONFIGFS_RNDIS. (IPC_NS / ANDROID_PARANOID_NETWORK lines not conclusive.) Caveat: this is only the config our Lineage build uses; run the halium_kernel_config_fragments checker for the full list.

## Work breakdown (estimates: focused part-time days, wide uncertainty)
| Stage | Work | Est. | Risk |
|---|---|---|---|
| 0. Recon | confirm Droidian/Halium version fit for our vendor Android version; confirm `fastboot boot` works; set up Droidian build env (Python/Debian tooling, host build — no containers, see memory) | 2–3 d | med |
| 1. Kernel | add Halium+Droidian fragments, fix any build breaks, build with Droidian toolchain, boot.img for non-A/B + dynamic partitions | 3–6 d | med |
| 2. Boot to userspace | initramfs/rootfs placement on userdata, vendor from `super`, RNDIS/telnet debug, systemd/Android container (LXC) start | 4–8 d | med-high |
| 3. Display+input+GPU | hwcomposer/Adreno 650 EGL via libhybris, touch, buttons, brightness, (UDFPS panel HBM quirks as in docs/known-issues.md) | 3–7 d | med |
| 4. Core phone | audio (WCD938x/TFA98xx/AW8697 haptics), Wi-Fi, Bluetooth, sensors, vibrator, charging/VOOC reporting | 7–15 d | med-high |
| 5. Modem | RIL/ofono-binder against vendor radio HAL, data, SMS, calls, VoLTE | 5–15 d | HIGH |
| 6. Long tail | camera (Oplus proprietary stack, droidmedia), fingerprint (optical UDFPS via fprintd/biometrics HAL), NFC, GPS | 15+ d each, may not be achievable | HIGH |
| 7. Packaging | adaptation repo (`adaptation-droidian-bitra`), image build, install script/docs | 3–5 d | low |

Totals (rough): boots to Phosh with display+touch+USB net ≈ 2–4 weeks; basic daily-usable (calls/data/audio/Wi-Fi/BT) ≈ +1.5–3 months; camera+fingerprint+NFC = open-ended. Dominant risks: modem/RIL, vendor-version mismatch, camera.

## Security note
Stays on the 4.19 kernel (same CVE exposure as the current ROM, see earlier kernel discussion); Droidian does not solve that.

## Suggested first steps
1. Check Droidian device list/community for sm8250 + Android-13-vendor devices and existing adaptations to copy.
2. Identify our stock vendor Android version (firmware zips in firmware/) and the matching Halium level.
3. Run the Halium config checker on the bitra kernel config; draft fragment.
4. Try `fastboot boot` of a halium-boot image (non-destructive RAM boot) before touching partitions. Backups exist in backups/20261116-213951.

## Stage 0 recon results (2026-11-17, after A16/A17 verified working)
Sources: github.com/droidian/porting-guide (docs.droidian.org/porting-guide/ returns 404), github.com/droidian-images/droidian devices.yml,
github.com/orgs/droidian-devices/repositories (53 repos). Subagent report; claims below that are marked UNVERIFIED were not confirmed.
- **Supported Android bases:** devices.yml apilevel 28/29/30/32/33 = Android 9/10/11/12(.1)/13. No Android 14+ device; Android 14 kernel base exists but no devices. => our vendor must be Android <= 13.
- **No sm8250 / Snapdragon 865 / Realme device** in devices.yml or the 53 org repos (closest: Xiaomi miatoll, Sony kumano, Volla, Pixel 3a). bitra would be a brand-new port; nobody to copy an adaptation from.
- **Vendor provenance (verified locally):** the blobs in vendor/realme/sm8250-common come from stock RMX3370 **Android 13** (fingerprint realme/RMX3370/RE879AL1:13/TP1A.220905.001, first_api_level 30) but the Lineage vendor/odm *images* are rebuilt as Android 16/17. Droidian/Halium needs a coherent Android-13 vendor, i.e. the *stock* RUI 4.0 vendor/odm, not our Lineage-built images. We only hold firmware-only zips (firmware/*/), no stock vendor.img => need the full stock RUI 4.0 OTA (Android 13) for RMX3370 first.
- **Docker conflict:** Droidian's kernel packaging (releng-build-package) and rootfs-builder (debos image quay.io/droidian/rootfs-builder) are Docker based. Our rule is no containers: use the AOSP clang prebuilts + plain `make` for the kernel (already how we build), and host-native debos/debootstrap (needs root/sudo, may need layering on this Fedora Atomic host) for the rootfs.
- **Non-A/B + dynamic partitions (super):** UNVERIFIED in Droidian docs. Droidian puts its rootfs in an image (LVM/rootfs.img, flashable to userdata) rather than system, so super only needs to carry vendor/odm; legacy flag FLASH_IS_LEGACY_DEVICE=1 for non-A/B.
- Kernel: no Halium config checker script found; use lxc-checkconfig after first boot + diff against halium.config/droidian.config fragments; CONFIG_USB_CONFIGFS_RNDIS needed for debug. Packaging via debian/kernel-info.mk (offsets from unpackbootimg of stock boot.img).
- Adaptation package generator: github.com/droidian-releng/droidian-build-tools `droidian-new-device -v realme -n bitra -c arm64 -a 33 -r phone -d droidian` (not yet read/verified).

### Next steps (stage 1 prerequisites)
1. Obtain full stock RUI 4.0 (Android 13) RMX3370 OTA (IN/EU/GLOBAL) -> extract vendor/odm/boot/dtbo/vbmeta (scripts/unpack_blockota.py handles block OTAs).
2. Draft Halium/Droidian kernel fragment from the bitra .config (missing list in this doc) and build it host-native.
3. First test without flashing partitions: `fastboot boot` of a halium-boot image (RAM only). Needs user go-ahead per step.

### Correction (2026-11-17): the full stock Android 13 package IS already in firmware/EDL
`firmware/EDL/RMX3370export_11_13.1.0.1100EX01_2024101810120100.zip` (RUI 13.1.0.1100 EX01, 2024-10) holds IMAGES/{system,system_ext,vendor,odm,boot,recovery,dtbo,vbmeta*}.img. I missed it in the first recon.
Extracted (python zipfile, untrusted) to firmware/stock-a13/: boot, dtbo, vbmeta, vbmeta_system, vbmeta_vendor, vendor, odm, recovery (+ simg2img raw vendor.raw / odm.raw, vendor tree in v-extract/vendor).
- vendor.img: sparse EROFS; props: ro.vendor.build.version.release=12, sdk=30, fingerprint qti/kona/kona:12/RKQ1.211119.001, first_api_level 30 => a **Treble vendor of Android 12 level (API 30)** under an Android 13 system. => Droidian/Halium apilevel **30** (Android 11 halium) or 32; vendor itself is within Droidian's supported range.
- Stock boot.img: header v2, page 4096, kernel load 0x8000, ramdisk 0x1000000, dtb 0x1f00000 (15.8 MB appended in boot), tags 0x100, os 12.0.0, cmdline console=ttyMSM0 ... androidboot.hardware=qcom swiotlb=2048 kpti=off (unpacked in firmware/stock-a13/boot-unpacked). These feed debian/kernel-info.mk.
- Stock partition layout/ super_def json in the package: super 10200547328 bytes, group qti_dynamic_partitions (dynamic partitions confirmed).
=> Prerequisite (vendor) is satisfied. Remaining unknown: which Halium system API level/Android version to base the Droidian system image on given vendor API 30 under Android 13 (ask Droidian community).

## Stage 1 result: Halium/Droidian kernel builds (2026-11-17)
- Separate source: roms/droidian/kernel (own clone of fork branch `droidian` of android_kernel_realme_sm8250-axion, based on bitra/a16; Lineage trees untouched). Local fixes: scripts/extract-cert.c guard for OpenSSL 3 hosts; fanotify old_memcg decl + fdinfo callback signature (Android's FANOTIFY backport never compiled).
- Build: `python3 scripts/build_droidian_kernel.py` (host-native, AOSP clang-r563880c + gcc-4.9 binutils prebuilts, out-of-tree in roms/droidian/kernel-out; needs `-I <src>` so OplusKernelEnvConfig.mk is found; config = kona-perf_defconfig + vendor/oplus.config (what Lineage uses) + scripts/kernel-config/{halium,droidian}.config).
- Fragments from github.com/droidian-devices/common_fragments (branch 4.19-android); 58 options applied, 0 conflicts; 8 "absent" are non-4.19/x86-only options (WATCHDOG_NOWAYOUT, LBDAF, NETPRIO_CGROUP(=CGROUP_NET_PRIO already on), RTC_DRV_CMOS, CGROUP_SCHEDTUNE, ANDROID_PARANOID_NETWORK, SW_SYNC_USER, PSTORE_RAM_ANNOTATION_APPEND).
- Output: releases/droidian-kernel/{Image.gz (23 MiB), dtb (kona-v2.1 + kona-v2 + kona dtbs concatenated IN THAT ORDER, byte-identical to Lineage's dtb.img; order matters for bootloader dtb selection), kernel.config}.
- USB debug on the Mac: macOS has no RNDIS driver. Kernel has CONFIG_USB_CONFIGFS_NCM (CDC-NCM works natively on macOS) and RNDIS; ACM/ECM are NOT enabled -> add USB_CONFIGFS_ACM / ECM in a debug fragment if a serial console is wanted.
- AppArmor is not in the kernel (Droidian images pass `apparmor=1 security=apparmor`); Droidian 4.19 fragments don't require it; add SECURITY_APPARMOR later if the rootfs needs it.
- Next: initramfs (halium-boot / Droidian initramfs) + boot.img (header v2, offsets in this doc), then RAM-only `fastboot boot` on the Mac.

## Stage 2 result: RAM boot succeeded (2026-11-17, user test on Mac)
- `fastboot boot debug-boot.img` is accepted by the bootloader (no flashing). Kernel 4.19.325-cip136-st20-Entropy-1.7 (our Droidian-config build, uname date 19:47 IST) boots, runs our /init, binds UDC `a600000.dwc3`, and the macOS host sees USB `halium-debug` (1d6b:0104, serial bitra0001, 480 Mb/s), brings up `en9` (CDC-NCM), ping 192.168.2.15 ~1.5 ms 0% loss, root shell via `nc 192.168.2.15 23`.
- Bootloader appended to our cmdline: androidboot.mode=fastboot, verifiedbootstate=orange, bootdevice=1d84000.ufshc, boot_devices=soc/1d84000.ufshc, panel `qcom,mdss_dsi_oppo21619samsung_ams662zs01_1080_2400_cmd_dvt`, dtbo_idx=5, project_codename=instantnoodle(sic), plus Oplus extras. Useful for the real cmdline.
- dmesg after ~5 min: Oplus charger/gauge drivers (mp2650, bq27541, VOOC) run fine (battery 89%); `servloc: Unable to connect to service locator` / adsprpc PDR down = EXPECTED without Android userspace (pd-mapper/qrtr-ns/rmt_storage not running); no panics.
- Lesson: macOS needs NCM, not RNDIS — works. fastboot boot works on this bootloader, so iterating needs no flashing.
