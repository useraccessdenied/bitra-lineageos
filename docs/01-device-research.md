# 01 — Device research: Realme GT Neo 2 (bitra)

## Identity
- Marketing: realme GT Neo 2 (5G); **model RMX3370** (don't mix with RMX3371/`spartan` = GT Neo 3T / Q5 Pro, a different device sharing the sm8250 common tree)
- Codename: `bitra`; Oplus project `21619` (the `_21619` suffix in blobs, e.g. `libarcsoft_*_skel_21619.so`); `TARGET_OTA_ASSERT_DEVICE := RE5473,RE879AL1,bitra`
- SoC: Snapdragon 870 (**SM8250-AC**, platform `kona`), Cortex-A77/A55 "kryo385" runtime variant in trees
- Display 1080×2400, density 450, 120 Hz AMOLED
- Shipped with Android 11 (RUI 2.0), shipping API level 30 (`PRODUCT_SHIPPING_API_LEVEL := 30` — matters for VNDK/vintf)
- Stock baseline used by trees for blobs: **RMX3370_13.1.0.1000(EX01)** (Android 13)
- Family: realme sm8250 siblings share one common tree: `spartan` (GT Neo 3T/Q5 Pro), and RMX3366 `rivena` (GT Master Explorer; has its own separate tree).

## Partition / boot layout (from tree BoardConfig)
- **Not A/B** — CONFIRMED on hardware 2026-11-16 (user; partition dump has unsuffixed `boot`, `abl`, `xbl`, `recovery`, `vbmeta*`). Recovery partition + cache apply; no slot suffixes. Dynamic partitions: `super` 10,200,547,328 B, group `qti_dynamic_partitions` 10,196,353,024 B with `odm product system system_ext vendor`.
- Boot header v2, kernel `Image` (uncompressed) + DTB in boot, separate `dtbo`; boot 96 MiB, dtbo 24 MiB, recovery 128 MiB.
- Filesystems: system/system_ext/product ext4, vendor/odm **erofs**; userdata f2fs; metadata partition.
- Kernel cmdline: `androidboot.hardware=qcom ... androidboot.usbcontroller=a600000.dwc3 ... swiotlb=2048`.
- `product` has a reserved-size workaround (tree commits "Decrease product reserved size xN") → super space is tight; keep GApps builds in mind.
- AVB: tree commit "fstab: Drop AVB keys". **Observed 2026-11-16: the A16 build booted WITHOUT flashing `vbmeta.img` (stock vbmeta kept, bootloader unlocked)** — flashing it with disable flags was not needed on this device.

## Kernel
- Downstream **4.19.325** (`kernel/realme/sm8250`), configs `vendor/kona-perf_defconfig` + `vendor/oplus.config`; based on LineageOS `android_kernel_qcom_sm8250` (lineage-20) merged with Realme/Oplus OSS drops. Newest head: bijoyv9 "Entropy-1.7" branch / SM8250-Common `lineage-24.0` (merge 2026-11-07).
- Kernel source origin of truth: `realme-kernel-opensource` org on GitHub (stock drops), plus community forks.
- KernelSU variant exists (Axion "KSU" build; Infinity X points to a root kernel).

## Firmware
- ROMs require firmware **F.20 (IN) / F.18 (EU) / F.18 (GLOBAL)** flashed first (modem, tz, hyp, abl, xbl, dsp, etc. + camera/FP/face tuning). If coming from OOS/COS ports, flash the latest stock RUI of the region first or **camera / fingerprint / face unlock break**.
- User will provide the firmware zip → place in `firmware/`. We will: (1) identify layout (payload.bin vs ozip/ofp), (2) extract with `payload-dumper-go` / `oppo_ozip_decrypt` + `lpunpack`/`erofs` tools, (3) use it as the extraction source for `extract-files.py` and as a dump for Linux-port research (DT, firmware blobs for `linux-firmware`/`qcom-firmware` extraction).

## Hardware inventory (to confirm from dump)
Touch (Oplus touch HAL, `touch/include` in tree), audio (TFA98xx amp, `tfa98xx.cnt`), cameras (IMX471 front?, Hi846, OV02B, S5KGW1, OIS BU63169 — Oplus camera stack, proprietary `vendor/oplus/camera`), NFC (sn-nci kernel driver, recently patched for 4.19), fingerprint (under-display via Oplus HAL), vibrator, Dolby (`hardware/dolby`), wifi (QCA, `bitraWifiResTarget`), BT, UFS 3.1, ADSP/CDSP/SLPI remoteproc.

## Bootloader unlock
Realme: Deep Testing app / `fastboot flashing unlock` flow; realme *discontinued* the in-depth-test route on some regions. **Unverified for this unit** — user states ROM support is good, so presumably unlocked already. Check with `fastboot getvar unlocked` (TODO).
