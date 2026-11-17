# 09 — Mainline status for SM8250 and reverse-engineering effort for bitra

Verified 2026-11-09 by fetching torvalds/linux master (files exist = HTTP 200) unless marked [K] (background knowledge) or [?].

## Mainline SM8250 SoC support (arch/arm64/boot/dts/qcom/sm8250.dtsi, 7067 lines)
Present: Adreno 650 + GMU + zap shader nodes, DPU (sm8250-dpu) + DSI + 7nm DSI PHY, camss + camcc, Venus (sm8250-venus) + videocc,
dispcc/gpucc, ADSP/CDSP/SLPI remoteproc (`*-pas`), FastRPC, UFS + QMP PHYs, USB HS/SS PHYs, PCIe, LPASS macros (rx/tx/va/wsa) and Q6 ASM/ADM/AFE
audio stack, cpufreq (EPSS), coresight. Drivers: `camss-vfe-480.c`, `dpu_6_0_sm8250.h`, `fastrpc.c`, `sound/soc/qcom/sm8250.c`, ath11k, `iris` (newer video driver), all present.
NOT present in sm8250.dtsi: modem (`mpss-pas`) and IPA nodes (only reserved-memory for IPA), so cellular data is not upstream for this SoC [verified absent in dtsi; may exist in forks].
Boards in mainline: sm8250-hdk, -mtp, Samsung r8q/x1q, Sony Xperia 1 II/5 II (edo), Xiaomi Mi Pad 5 Pro/Poco F3 class (elish, pipa).
OnePlus 8/8T and realme are NOT in mainline master; OnePlus 8T (kebab) is carried by postmarketOS's sm8250 fork and the mailing list (v4 patch series seen).

## Per-chip driver check (mainline master)
| Device chip | Driver in mainline? |
|---|---|
| Camera sensors IMX471, HI846, OV02A10 (~OV02B) | imx471.c, hi846.c, ov02a10.c exist; **S5KGW1 (64 MP main) none** |
| NXP NFC | nxp-nci exists (QTI NQ-NCI may need check) |
| IMUs LSM6DSO, ICM42600 | st_lsm6dsx, inv_icm42600 present |
| Touch Synaptics S3908, ST FTS | Synaptics RMI4 + ST drivers exist, but Oplus firmware/protocol variants likely need adaptation |
| Haptics AW8697 | **no** (only aw86927; chip differs) |
| Panel Samsung AMS662ZS01 | **no**; similar Samsung DSI panels exist (e.g. sofef00) as templates |
| TFA98xx amp | in-tree `tfa98xx`? [?] (out-of-tree NXP driver commonly used) |
| Fingerprint Goodix/Jiiov UDFPS (TEE) | **no** |
| Charger MP2650 / VOOC MCU RK826/STM8S / DA9313 | **no** (Oplus protocols) |
| Pixelworks Iris5 | **no**, bypass |

## How hard is reverse engineering the rest?
Good news: most of the work is NOT reverse engineering. The downstream 4.19 kernel is GPL source in `kernel/realme/sm8250`
(the Oplus drivers are all there, e.g. aw8697 haptics, qbt-handler, fastcg, touch), so writing a mainline driver means *porting from source*,
not decompiling. Difficulty, rough:
- Easy-moderate (days): bitra DTS from downstream DTS, USB, UFS, regulators, GPIO keys, Wi-Fi/BT, GPU, display with a ported panel driver.
- Moderate (weeks): audio topology (WCD938x + TFA98xx), touch, haptics (port aw8697), sensors, charging basics, NFC.
- Hard (months): camera (S5KGW1 driver from vendor datasheet-less sources + libcamera tuning), modem/IPA nodes and rmtfs bring-up.
- Real reverse engineering needed only for: fingerprint/TEE (TrustZone applets, practically unachievable), VOOC fast-charge protocol (partly documented in downstream source), Iris5, Oplus camera ISP tuning, closed firmware internals.
- Impossible / out of scope: XBL/TZ/hyp/modem/DSP firmware replacement (signed, fused).

## Strategy
1. Do not RE; port from the downstream GPL source into a mainline-based tree (start from postmarketOS `linux-postmarketos-qcom-sm8250` and OnePlus 8T DTS).
2. Reuse prior work: Xiaomi elish/pipa, Sony edo, OnePlus kebab for SoC-level pieces; only board-level bits are new.
3. Upstream our bitra DTS + panel/haptics drivers when done (helps long-term maintenance).
4. First milestone: serial/USB console + framebuffer, then GPU/Wi-Fi, then audio/touch.
