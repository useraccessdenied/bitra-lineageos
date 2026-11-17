# 04 — Linux ports roadmap (Halium / Ubuntu Touch, postmarketOS, mainline)

Honest summary: the Android build is the foundation and nearly everything for the Linux ports comes out of it (kernel, firmware, vendor HALs). Ordering: Android → Halium → downstream-kernel pmOS → mainline.

## What I found (search, 2026-11-08) and what I could NOT confirm
- No existing Ubuntu Touch, postmarketOS or mainline support for bitra/RMX3370 turned up in searches. Treat as greenfield.
- SM8250 mainline is mature: `sm8250-mainline` GitLab fork + postmarketOS `linux-postmarketos-qcom-sm8250` (6.13 in v25.06); OnePlus 8/8T (instantnoodle/kebab) via pmaports; Xiaomi elish/others. Newer kernels (6.x) in-tree for the SoC itself: GPU (Adreno 650 via freedreno, needs ZAP shader firmware), UFS, USB, remoteprocs, audio partly.
- UBports docs: new ports should use **Halium ≥ 9**; Halium 12 work is active but sparse. I found no confirmed Halium-12 + Qualcomm 4.19 success story → verify on UBports forum/Telegram before committing.
- *Not verified*: whether pmOS wiki lists any realme sm8250 device; check `wiki.postmarketos.org` category "Realme" and pmaports `device/testing`.

## Track 1 — Ubuntu Touch via Halium (best near-term)
Why first: reuses our **4.19 downstream kernel + Android vendor image**; no display/GPU/modem bring-up from scratch.
1. Kernel: add Halium kernel config fragments (`kernel/configs` from halium: cgroups, namespaces, binder, overlayfs, etc.). Starting point: `ravindu644/android_kernel_realme_sm8250-droidspaces` (already does container-oriented config on this exact kernel family).
2. Build Halium rootfs/boot with `halium-generic-adaptation-build-tools` (see UBports porting docs, Halium 11/12 branch matching our vendor Android version — vendor is A13-based blobs, so Halium 12/13-ish boundary: **risk**).
3. Port tree: `device_realme_bitra` (halium variant) with `deviceinfo`, fstab, ueventd; mount vendor from `super`.
4. Bring up in layers: boot→adb/telnet → display (hwcomposer/ Mir) → touch → WiFi → RIL (ofono/ ril via binder) → audio (pulse droid) → camera (gst-droid).
5. Kernel is shared with Lineage: keep Lineage kernel branch and a `halium` overlay config branch.

## Track 2 — postmarketOS (downstream first, mainline later)
- **2a (Halium-less downstream)**: `device-realme-bitra` in pmaports using our 4.19 kernel (like many Qualcomm "vendor kernel" ports): boot, USB networking, display via simple-framebuffer/fbdev — limited (no GPU accel without Android blobs, no modem). Good smoke test for initramfs/bootimg tooling (header v2, DTB appended, `deviceinfo_*` values copy from BoardConfig: base 0x0, pagesize 4096, cmdline).
- **2b (mainline)**: needs a `sm8250-realme-bitra.dts`. Steps: dump stock DTB from boot.img / `/proc/device-tree` (from running Android), diff against `sm8250-oneplus-instantnoodle.dtsi`/`kebab` (nearest Oplus siblings: similar PMICs, touch IC family, UFS), then enable pieces incrementally: UART/earlycon → UFS → USB peripheral → display panel (find panel driver; DSI panel init sequence from vendor DT `qcom,mdss-dsi-on-command`) → touchscreen → GPU (needs zap shader from firmware) → WiFi (ath11k? check — SM8250 uses WCN6855/WCN3998 depending on board; check firmware) → BT → modem (remoteproc `modem` + `qrtr`, firmware from our dump) → audio (WCD938x, TFA98xx amp) → camera (hardest; Oplus sensors, camss) → fingerprint (UDFPS needs a userspace/ display hack).
- Firmware: copy from the dump (`/vendor/firmware_mnt`, `modem`, `adsp`, `cdsp`, `venus`, `a650_*`, `wlan`) → `firmware-realme-bitra` package in pmaports.
- Bootloader: Oplus aboot handles `boot.img` v2 with appended DTB; mainline kernels need a proper appended DTB or `dtbo`-style handling; test with `fastboot boot`.
- Hardware-level safety: `fastboot boot` only; keep EDL/firmware recovery ready.

## Track 3 — Other ports
Droidian/Halium-based distros share Track 1 work. Mobian/postmarketOS share Track 2.

## Prerequisites that fall out of the Android work (do these anyway)
- Full firmware dump (`firmware/`), partition table backup (`gpt`/`sgdisk -p` from Android via adb root).
- Decompiled stock DTB: `dtc -I dtb -O dts` of `kona.dtb`/`kona-v2.1` variants from boot.img + dtbo.
- A way to see logs: **UART is unavailable** on this phone → use `pstore/ramoops` (`console-ramoops` in 4.19) and USB serial gadget.
- Boot image tooling: `mkbootimg`, `unpack_bootimg`, `avbtool`.

## Realistic expectations
Halium: usable daily-ish with effort, camera/modem fiddly. Mainline: months; WiFi/BT/display/touch/USB achievable, cellular/camera/fingerprint are long-tail.
