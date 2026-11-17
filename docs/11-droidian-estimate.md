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
