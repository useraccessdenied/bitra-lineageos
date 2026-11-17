# 05 — Risks & open questions

## Risks
| # | Risk | Mitigation |
|---|---|---|
| 1 | Third-party vendor blobs (Axion repo) are unaudited code that runs as root on a personal phone | Prefer our own extraction from the stock firmware (Phase 3); diff against theirs |
| 2 | Wrong firmware/ROM combo → camera, FP, face unlock broken | Match F.20/F.18 firmware to region; flash stock RUI first when coming from OOS/COS |
| 3 | Bricking from partition/vbmeta/persist mistakes | Back up `persist`, `modemst*`, `oplusreserve*`, `devinfo`; keep EDL/MSM tool (needs signed programmer from realme) path in mind; never flash `abl/xbl` casually |
| 4 | Kinoite host vs AOSP toolchain | Build in Ubuntu container (done by design) |
| 5 | RAID0 disk — single device failure loses everything | Push docs/scripts/trees you modify to a git remote regularly |
| 6 | `lineage-24.0` assumption = Android 17 | Verify on first sync (`PLATFORM_VERSION`) |
| 7 | Oplus camera/face/FP blobs from Android 13 on an A16/A17 framework | Already works on A16 in Axion; A17 is untested by us → expect HAL/VINTF breakage |
| 8 | Old Haswell CPU — slow builds | ccache; avoid unnecessary full rebuilds; use `-j56` but watch memory |
| 9 | Search tool results were thin on Linux-port state | Re-verify directly on pmOS wiki/UBports before investing |

## Open questions for the user
1. Firmware zip path, region, and version.
2. Current ROM on the phone, bootloader unlocked? Is the phone ever flashed with a custom recovery (which one)?
3. Fine to start with Android 16 (23.2) and move to 17 afterwards?
4. adb/fastboot install route (see 03 §Decisions).
5. Any Telegram/GoFile upload automation wanted? (default: no)
6. Should this workspace become a git repo with a private remote (for scripts/docs only)?

## Not verified (explicitly)
- Exact Lineage 24.0 = Android 17 mapping
- Any prior Linux-port work for bitra
- Which of Axion's patches (frameworks/base etc. in bijoyv9 forks) are needed vs. pure Lineage

## Verified on hardware (2026-11-16)
- Bootloader unlocked; phone is NOT A/B; A16 build boots without flashing vbmeta.img.
- Stock Oplus camera crashed: missing `com.oplus.util.OplusTypeCastingHelper` in oplus-fwk (fix added in hardware/oplus/oplus-fwk, rebuild in progress); snapcam needs GMS (gsf provider).
