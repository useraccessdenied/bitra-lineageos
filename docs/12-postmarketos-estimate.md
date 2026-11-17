# 12 — postmarketOS (mainline) port estimate (2026-11-17)

NOTE: https://wiki.nura.eco/wiki/Sm8250_kernels could NOT be fetched (timeouts, twice; a web search did not surface it) — its content is NOT used here. Re-read it when reachable. Sources used: docs/09 (verified against torvalds/linux 2026-11-09), pmOS wiki "Qualcomm Snapdragon 865/865+/870 (SM8250)" and OnePlus 8 Pro page, pkgs.postmarketos.org (linux-postmarketos-qcom-sm8250 = 6.17.0-r3, mainline fork).

## Starting point
- Mainline SM8250 SoC support is broad (GPU, DPU/DSI, camss, venus, ADSP/CDSP/SLPI, fastrpc, UFS, USB, PCIe, Q6 audio); modem/IPA nodes absent upstream (docs/09). Reference boards in mainline: hdk, mtp, Samsung r8q/x1q, Sony edo, Xiaomi elish/pipa. OnePlus 8T (kebab) lives in the pmOS fork/mailing list = closest relative (same SoC, OnePlus/Oplus hardware family).
- pmOS wiki (SM8250 page) lists CPU SMP, cpufreq, cpuidle, UART as working at SoC level, and WARNS that enabling UFS on Sony Xperia with non-vendor kernels can erase the chip. => treat UFS bring-up on our phone as dangerous until checked; backups exist in backups/20261116-213951 (67 partitions).
- This path fixes the "old 4.19 kernel / CVEs" concern (mainline gets security fixes), unlike Halium/Droidian.

## Work breakdown (focused part-time days, wide uncertainty; AI-assisted)
| Stage | Work | Est. | Risk |
|---|---|---|---|
| 0 Recon | re-read nura wiki + pmOS sm8250 pages, diff kebab/pipa/edo DTS, confirm `fastboot boot` works, find simple-framebuffer address from ABL, pstore/ramoops | 3–5 d | med |
| 1 Boot skeleton | `sm8250-realme-bitra.dts` (from kebab/hdk + downstream DTS), regulators, GPIO keys, USB gadget (RNDIS/ACM), simplefb, pmOS initramfs shell over USB; boot from RAM | 1–2 wk | med-high |
| 2 Storage | UFS (careful, see warning), rootfs on userdata or free partition; never touch persist/modemst/ocdt etc. | 3–7 d | HIGH (data risk) |
| 3 Display | port Samsung AMS662ZS01 panel (DSC, 120 Hz) from downstream; bypass Pixelworks Iris5 | 1–3 wk | high |
| 4 GPU | Adreno 650 freedreno/Mesa, zap + GMU firmware from stock vendor partitions | 3–7 d | med |
| 5 Input | touch (Synaptics S3908 / ST FTS), keys, haptics AW8697 port | 1–2 wk | med |
| 6 Remoteprocs | ADSP/CDSP/SLPI, pd-mapper, qrtr, firmware loading | ~1 wk | med |
| 7 Wi-Fi/BT | ath11k (real chip to confirm; DTS said QCA6390), board-2.bin, BT | 3–7 d | med |
| 8 Audio | Q6 stack + WCD938x + TFA98xx + WSA881x, UCM profiles, speakers/headset/mics | 2–5 wk | high |
| 9 Power | battery gauge BQ27541, MP2650/DA9313 charging, VOOC (partial) | 1–3 wk | med-high |
| 10 Modem | no upstream mpss/IPA nodes: add modem remoteproc + IPA, rmtfs (uses modemst1/2 — IMEI risk), ModemManager/oFono, VoLTE | 1–3 mo | HIGH |
| 11 Sensors/NFC | IMUs, light/prox, NQ-NCI NFC | 1–2 wk | med |
| 12 Camera | S5KGW1 etc. no drivers; libcamera tuning | months / maybe never | very high |
| 13 Fingerprint | Goodix/Jiiov UDFPS TEE — not feasible | n/a | — |
| 14 Packaging | pmaports `device-realme-bitra` (+kernel pkg), upstream DTS patches | 1–2 wk | low |

Rough totals: USB shell + simplefb ≈ 2–3 wk; usable "tablet" (display, touch, GPU, Wi-Fi, USB, charging) ≈ 2–3 months; real phone (audio+modem) ≈ 6+ months; camera/fingerprint indefinite. Faster if the sm8250-mainline community already has Oplus/realme bits (check #sm8250-mainline on OFTC/Matrix, gitlab.com/sm8250-mainline/linux).

## vs Droidian (docs/11)
Droidian: faster to a usable phone (reuses Android blobs: modem, camera, audio) but stays on 4.19 and fragile. pmOS: far more work, better security/longevity and upstreamable, but modem/camera are the long poles. A sensible order: Droidian for usability sooner, pmOS bring-up in parallel only if you want the mainline route; both share the DTS/hardware knowledge and the same debug harness.

## Safety rules for this path
- Only `fastboot boot` until RAM boot works; no partition writes without confirmation.
- Never write persist, modemst1/2, mdm1m9kefs*, *nvbk*, ocdt, oplusreserve*, abl/xbl. rmtfs must be configured read-only/with copies first (modem EFS = IMEI).
- Keep the UFS-erase warning in mind; dry-run any UFS-related change on RAM boot only.
