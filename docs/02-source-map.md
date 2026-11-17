# 02 — Source map (researched via GitHub API, 2026-11-08)

## Actively maintained, directly relevant

| Repo | Branches | Last push | Notes |
|---|---|---|---|
| `SM8250-Common/android_device_realme_bitra` | lineage-22.2 … 23.2, **24.0**, ax | 2026-11-07 | Device tree; `lineage_bitra.mk`, `BoardConfig.mk`, overlays, camera cfg, touch include. Cloned: `reference/sm8250c_device_bitra` |
| `SM8250-Common/android_device_realme_sm8250-common` | 22.2 … 23.2, **24.0**, sixteen | 2026-11-07 | Common tree (BoardConfigCommon, HAL manifests, blob fixups, 1521-line proprietary-files). Cloned: `reference/sm8250c_device_common` |
| `SM8250-Common/android_hardware_oplus` | 22.2 … 23.2, **24.0** | 2026-11-07 | Oplus HALs (touch, livedisplay, power, etc.) |
| `SM8250-Common/android_kernel_realme_sm8250` | 22.2, 23.x, **24.0**, rebase, sus, test | 2026-11-07 | 4.19.325, mirrors bijoyv9 "Entropy" |
| `SM8250-Common/android_hardware_dolby` | 23.2 | 2026-07 | Optional Dolby |
| `SM8250-Common/android_packages_apps_RealmeAddons` | 23.0–23.2 | 2026-03 | "realmeaddon" credited in Infinity X post (settings app for Realme features) |
| `SM8250-Common/local_manifest`, `build-script` | 23.2 / main | 2026 | Manifest + python build script template (LineageOS-SE source) |
| `AxionAOSP-devices/android_device_realme_bitra` (+ `sm8250-common`, `kernel`, `hardware_oplus`) | lineage-23.2 | Oct 2026 | Axion's official trees (A16 QPR2); same author lineage |
| `AxionAOSP-devices/proprietary_vendor_realme_bitra` / `…_sm8250-common` | lineage-23.2 (common: 23.0–23.2) | Oct 2026 | **Prebuilt vendor blobs for A16.** Public |
| `gitlab.com/bijoyv9/proprietary_vendor_oplus_camera` | 23.0–23.2, 14.0.0.2100 | — | Oplus camera blobs |
| `bijoyv9/device_manifests` → `bitra.xml` | main | 2026-06 | **Ready-made manifest** for bitra (clone: `reference/bijoy_device_manifests/bitra.xml`) |
| `bijoyv9/android_kernel_realme_sm8250` | Entropy-1.7 | 2026-11-07 | Maintainer's kernel (baseline for Axion/Infinity) |
| `LineageOS/android` | lineage-20 … 23.2, **24.0** | upstream | Official manifest. `LineageOS-SE/android` has 23.0/23.2 (Lineage fork used by build-script) |

Maintainers/people: **bijoyv9** (Axion official, kernel, device tree, RealmeAddons), **SaiChaitanya888** (older lineage-23.0 trees, TWRP), **Subodhkr360** (Infinity X unofficial; `android_device_realme_bitra`).

## Older / historical (reference only)
SathamHussainM, ObsidianMaximus (crDroid 14), Blackmanx (Bigshot kernel, A14), ProjectBlaze-Devices (A13/14), AOSPA (`uvite`, 2025-08), PixelOS-old, AlphaDroid, PalyrimOS, Xtended, erikdrozina (A13). Recovery trees: SathamHussainM `…bitra-twrp`, Saichaitanya888 `…bitra-twrp` (android-14), RAM-UNLOK `…bitra-ofox`.
Kernel stock sources: `realme-kernel-opensource` (GitHub org), `ermyltsor/android_kernel_realme_sm8250` (stock RUI), `yassshhhhh15/…` (RUI5 GT Neo 3T), `ravindu644/…-droidspaces` (container-oriented 4.19 config — relevant to Linux ports).

## Per-developer findings (checked after user hint)
- **bijoyv9 GitHub**: has NO bitra device tree (only `spartan` trees, kernel `Entropy-1.7`, `device_manifests/bitra.xml`). His bitra trees live in org mirrors (AxionAOSP-devices, SM8250-Common).
- **bijoyv9 GitLab** (vendor blobs, public): `proprietary_vendor_realme_sm8250-common` branches 23.0/23.1/23.2/**24.0** (pushed 2026-11-07); `proprietary_vendor_realme_bitra` 23.1/23.2 only (no 24.0 yet); `proprietary_vendor_oplus_camera` 23.0–23.2.
- **Saichaitanya888** (GitHub): `device_realme_bitra`, `vendor_realme_bitra`, `device_realme_sm8250-common`, `vendor_realme_sm8250-common`, `hardware_oplus` all at `lineage-23.0` (Oct 2025); kernel `lineage-22.2`; TWRP `bitra-twrp` android-14. Older, superseded by SM8250-Common/Axion.
- **arsalan-zeus** (AlphaDroid maintainer, A14, last official 2024-09): `device_realme_bitra`/`sm8250-common` `alpha-13.0` (pushed 2026-10), `android_device_realme_bitra` `matrixx-15`; org `AlphaDroid-devices` has `device_realme_bitra` (alpha-14), `vendor_realme_bitra` (aosp-14), `bitra-hardware_oplus` (cam-14), `bitra-kernel_realme_sm8250` (bigshot-AOSP). Useful as an A14 reference and the only trees with RealmeUI-4-era camera.

## Key gaps found
1. **Vendor blobs for `lineage-24.0` are partial**: `sm8250-common` has 24.0 on bijoyv9's GitLab, but `proprietary_vendor_realme_bitra` (device-specific) tops out at 23.2. Device-specific blobs for A17 can likely be reused from 23.2 or re-extracted from firmware (bitra part is small: 97 lines vs 1521 common).
2. `TheMuppets` has no bitra vendor repo (404) — expected, Lineage never officially supported bitra.
3. No `hardware/qcom-caf/sm8250` displayed under Lineage org via API (empty branch list) — likely fetched through Lineage's `lineage.dependencies`/manifest under `hardware/qcom-caf/sm8250`; verify at sync.
4. Android 17 = `lineage-24.0` (inferred from the Lineage version scheme + Infinity X being A17; not independently confirmed).
