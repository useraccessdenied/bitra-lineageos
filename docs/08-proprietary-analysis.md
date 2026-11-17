# 08 — What is proprietary on bitra, and the path to open software

Sources: `device/realme/{bitra,sm8250-common}/proprietary-files.txt` (A16 tree), vendor repo sizes, kernel DTS
(`arch/arm64/boot/dts/vendor/oplus/bitra/*`), firmware zips. Confidence tags: **[V]** verified from our files,
**[K]** background knowledge, not verified here, **[?]** open question to check.

## 1. Bottom line
- A 100% open phone is **not achievable** on this hardware. Boot ROM, XBL/TZ/hyp, modem, DSP and GPU-microcode firmware are
  signed Qualcomm/Realme binaries that no ROM or Linux port can replace. Every Linux port (postmarketOS included) loads them.
- Realistic goal: **no proprietary code on the application CPU in Linux userspace**, only signed firmware loaded by
  the kernel (the postmarketOS / mainline model). Android (even LineageOS) cannot get there: 1000+ vendor blobs.
- Our LineageOS build still depends on ~1,500 proprietary files. Open: framework, kernel, `hardware/oplus` shims, CAF HALs.

## 2. Inventory by layer
### L0 — Boot chain / secure world (closed, unreplaceable, fused secure boot) [V]
`xbl(_ddr4/5)`, `xbl_config`, `tz`, `hyp`, `aop`, `devcfg`, `cmnlib/cmnlib64`, `keymaster64`, `oppo_sec`, `imagefv`, `qupv3fw`,
`abl` (UEFI based, signed), `cdt`. Source of the 16-file `firmware-update` zips. Bootloader unlock lets you boot your own
`boot.img` but not replace these. Open parts: only EDK2/ABL source from CodeLinaro (signed, can't be swapped) [K].

### L1 — Remote processors (closed firmware, needed for most features) [V]
| Firmware | Where | Needed for |
|---|---|---|
| `modem.img` (NON-HLOS, 195 MB) | firmware zip | cellular, GNSS, also WLAN/BT firmware lives here |
| `dspso.img` (67 MB: ADSP/CDSP/SLPI) | firmware zip | audio routing, sensors (SLPI), compute, some camera |
| `static_nvbk`/`modemst1/2`, persist | partitions | modem calibration, IMEI, sensor/FP calibration — **back up** |
| `BTFM.img`, `bdwlan.elf` | firmware zip / odm | Bluetooth, Wi-Fi board data (QCA6390 per DTS) |

### L2 — Peripheral firmware and chip-specific binaries (closed, small) [V]
- GPU: Adreno 650 microcode (sqe, gmu, zap) — 7 files.
- Video (Venus), IPA, charger MCU (`rk826`/`stm8s` VOOC), 13+10 files.
- Touch: Synaptics S3908 and ST FTS firmware (6). Fingerprint: Goodix (`goodixfp.*`), Jiiov, ANC (`ancap64.*`), `opluseid`.
- Haptics: AW8697 waveforms (60 files). Audio: TFA98xx (`tfa98xx.cnt`), WCD938x/WSA881x ACDB calibration (8 + 7).
- Camera: OIS BU63169 / SEM1215S, sensor tuning (S5KGW1, IMX471, HI846, OV02B).
- Display: Pixelworks **Iris5** coprocessor (closed, [V] in DTS), Samsung AMS662ZS01 AMOLED panel (commands in DTS, open).

### L3 — Android vendor userspace (closed)  [V] counts from proprietary-files.txt (1,601 entries)
| Category | Entries | Notes |
|---|---|---|
| Shared libraries (.so) | 857 | the bulk |
| Executables (HAL daemons) | 78 | sensors, camera provider, RIL, IMS, DPM, thermal, keymaster... |
| Firmware/cal/data blobs | 158 | see L2 |
| Config/xml/json/rc | 263 | mostly small text, the only reusable part |
| APK/JAR | 21 | |

Largest closed groups: **Camera ~290** (CamX/Chi HAL, sensor drivers, Oplus ISP/algorithms; `vendor/oplus/camera` 385 MB),
**Sensors 113** (SSC/SEE stack), **RIL 110 + IMS 69 + QMI 39 + CNE 62 + DPM 24 (cellular/data)**, **GNSS 66**,
Vibrator fw 60, ADSP modules 58, WFD 65, **Adreno GL/Vulkan 34**, VPP 22, DRM/Widevine 29, Perf 21, SCVE/NN 27.
Vendor repo sizes: sm8250-common 1.5 GB, camera 385 MB, bitra 115 MB.

### L4 — Kernel (open, GPL) [V]
`kernel/realme/sm8250`, 4.19.325, `kona-perf_defconfig + oplus.config`, built from source, no prebuilt `.ko`.
Contains Oplus out-of-tree drivers (charger/fastcg, haptics, FP, touch, `qbt-handler`, `techpack/camera-oplus`...).
Source is open but **downstream/unmaintainable**: not upstreamable as is.

## 3. Hardware (from DTS) vs open replacement
| Subsystem | Chip on bitra [V] | Open path | Status [K/?] |
|---|---|---|---|
| SoC / clocks / pinctrl / UFS / USB | SM8250 | mainline | good, many sm8250 phones booted upstream |
| GPU | Adreno 650 | Mesa freedreno/turnip + closed fw | works upstream, needs a650 fw files |
| Display | Samsung AMS662ZS01 DSC cmd-mode + Iris5 | panel driver (new), MSM DPU | panel driver must be written; Iris5 bypassed |
| Touch | Synaptics S3908, ST FTS | in-kernel rmi4/fts drivers, may need adaptation | [?] |
| Wi-Fi/BT | QCA6390 (DTS) | ath11k + hci_qca, board-2.bin | supported upstream [K]; **verify actual chip, F.18 firmware shows both** |
| Modem | X55 | remoteproc + qrtr + rmtfs + ModemManager | closed fw, works on sm8250 phones [K] |
| Audio | WCD938x, WSA881x, TFA98xx amps | ASoC (q6, wcd938x) | codec upstream; TFA98xx and board routing need work |
| Camera | S5KGW1 64MP, IMX471, HI846, OV02B | CAMSS + libcamera | **weakest area**; usually unsupported in upstream ports |
| Fingerprint | Goodix / Jiiov UDFPS via TEE | none (TEE-bound) | expect no FP |
| Haptics | AW8697 | no mainline (aw86927 differs) | [?] driver needed |
| Charging | MP2650, BQ27541, DA9313, RK826/STM8S VOOC | partial | basic charging likely; fast charge no |
| NFC | NQ-NCI (NXP) | nxp-nci | [?] |
| Sensors | BMI26x/ICM4x6xx/LSM6DSO, SX933x (SLPI) | iio via SLPI (hexagonrpc/sensors) or direct I2C | [?] |
| GPS | modem GNSS | gpsd/QMI | works with modem fw [K] |
| DRM/TEE | Widevine, keymaster | none | no L1 on Linux |

## 4. Paths
### A. Fully open-ish: postmarketOS mainline (my recommendation as the long-term target)
- postmarketOS has an `linux-postmarketos-qcom-sm8250` mainline kernel [(package)](https://pkgs.postmarketos.org/package/main/postmarketos/aarch64/linux-postmarketos-qcom-sm8250); nearest siblings are
  [OnePlus 8T (kebab)](https://wiki.postmarketos.org/wiki/OnePlus_8T_(oneplus-kebab)) and OnePlus 8.
- Work: write bitra DTS (we have the downstream DTS as a hardware map), panel driver, touch, audio topology, get fw via
  `linux-firmware` + extracted blobs (modem/dsp/GPU from our `firmware/`), test over USB serial / UART.
- Result: GPU + Wi-Fi + modem + audio plausible; camera/FP/fast-charge unlikely.

### B. Halium / Ubuntu Touch (pragmatic, but *not* open)
- Halium runs the **entire Android vendor stack** via libhybris, so all 1,500 blobs stay. It keeps camera/FP/RIL working.
- Needs the 4.19 kernel (we have it) and a vendor/system matching a Halium base (9–12). Our vendor is **Android 13** (OOS 13 blobs),
  so version mismatch is the main risk. Searching found no confirmed sm8250 Halium port; the docs say vendor blobs must match the
  Android base version [(UBports docs)](https://docsubportscom.readthedocs.io/systemdev/kernel-hal.html). **[?] verify before investing.**
- Prerequisite: LineageOS booting on this phone first (we're building it now).

### C. "Open Android" (LineageOS + microG, fewer blobs)
Can't remove the blobs, only reduce them: drop Dolby, WFD, CNE, FM, Oplus apps; use open Mesa? (no — Android Adreno needs the closed UMD;
freedreno on Android for a650 is possible but experimental [K]). Realistically blob-free Android = impossible.

## 5. Suggested sequence
1. Boot A16 LineageOS (in progress) and **dump/back up persist, modemst1/2, oplusreserve*, devinfo** — all other paths need them.
2. Pull `dmesg`, `/proc/device-tree` and `lsmod`/`lspci`-equivalent from the working phone to confirm real chips (Wi-Fi, NFC, touch variant).
3. Extract firmware (modem, dsp, a650, bdwlan) into `firmware/extracted/` for postmarketOS.
4. Try postmarketOS using the OnePlus 8T/8 kernel with a stub bitra DTS to reach USB-serial/framebuffer (low cost experiment).
5. In parallel, research whether a Halium 11/12 sm8250 port exists on UBports forum/GitLab, then decide if B is worth it.

## 6. Unverified items
Web search could not confirm the current sm8250 mainline feature matrix or any sm8250 Halium port. Check the postmarketOS wiki
sm8250 pages and UBports device lists directly before committing.
