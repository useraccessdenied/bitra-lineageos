# 03 — LineageOS build plan for bitra

## Strategy: two tracks, de-risk first

**Track A (recommended first): `lineage-23.2` (Android 16 QPR2).**
Device, common, kernel, hardware/oplus AND vendor blobs all exist on `lineage-23.2` and are exactly what the official Axion 2.9 build (A16-qpr2, Oct 2026) uses. Lowest risk → first boot quickly, validates toolchain, signing, flashing.

**Track B: `lineage-24.0` (Android 17).** Device/common/kernel/hardware have `lineage-24.0` branches (pushed daily); common vendor blobs have `lineage-24.0` on bijoyv9's GitLab, but the **bitra-specific vendor repo only goes to 23.2** (small; re-extract from firmware or reuse 23.2). Needs small fixes. Do after Track A boots.

Rationale: the Axion/Infinity maintainers already ship vendor blobs on 23.2; Track A is almost "sync and build". Track B is where the user's firmware zip earns its keep.

## Decisions needed from user (defaults in bold)
1. Start on Track A (23.2) then B? **Yes**
2. Source manifest: **upstream `LineageOS/android`** (pure Lineage) vs `LineageOS-SE/android` (the fork SM8250-Common's build-script uses). Default upstream; SE only if a patch is required.
3. adb/fastboot: **download platform-tools into `downloads/`** vs `rpm-ostree install android-tools` (reboot).
4. GApps: **none (vanilla)** first; add MindTheGapps later.
5. Which firmware region you have (IN/EU/GLOBAL) and where the zip is.
6. Is the bootloader already unlocked and the phone currently on which ROM?

## Phase 0 — Host setup (host-native, no container)
`bash scripts/00-host-deps.sh` (rpm-ostree layer) then reboot. `bin/repo` and `bin/git-lfs` already in place. ccache is sized by `04-build.sh` (`ccache -M 200G`).

## Phase 1 — Sync source (≈1–3 h, ~100+ GB download)
```
scripts/02-repo-init.sh lineage-23.2 a16     # DONE (local manifest = scripts/manifests/bitra-lineage-23.2.xml)
scripts/03-sync.sh a16 3                      # RUNNING; log: logs/sync-a16.log; marker: roms/lineageos/a16/.sync-complete
# Resume after power loss / reboot: just run the same 03-sync.sh again (setsid nohup scripts/03-sync.sh a16 3 > logs/sync-a16.log 2>&1 &)
```
- Keep each Android version in its own dir: `roms/lineageos/a16`, later `roms/lineageos/a17`. Lineage objects are shared through `--reference` / a local mirror (`repo init --mirror` in `roms/.mirror/`) if disk becomes a concern (1.8 TB is OK without).
- Local manifest origin: bijoyv9 `bitra.xml` (remotes: AxionAOSP-devices, SM8250-Common, gitlab bijoyv9). Pin to `lineage-23.2`; **audit before sync**: it pulls proprietary blobs from a third party — we read `proprietary-files.txt` against our own extraction in Phase 3.
- `hardware/qcom-caf/sm8250`, `vendor/qcom/opensource/*` come from the Lineage manifest — confirm they appear after sync.

## Phase 2 — First build (Track A)
```
# or simply: scripts/04-build.sh a16 userdebug
source build/envsetup.sh
breakfast bitra userdebug     # user for release
croot; export USE_CCACHE=1 CCACHE_EXEC=/usr/bin/ccache
brunch lineage_bitra                  # or: m bacon -j$(nproc)
```
Expected output: `out/target/product/bitra/lineage-23.2-<date>-UNOFFICIAL-bitra.zip` plus `boot.img`, `dtbo.img`, `vendor_boot` (if any), `super_empty`.
Common first-build failures (pre-diagnosed):
- Missing `hardware/oplus` namespace / soong namespace imports → check device `Android.bp` and `PRODUCT_SOONG_NAMESPACES` (recent commits "extract-files: add missing namespace imports").
- Kernel build uses prebuilt clang from `prebuilts/clang/host/linux-x86` — 4.19 kernels with Oplus drivers sometimes break with newer clang → fix by warnings-as-non-errors (`KCFLAGS=-Wno-error`) or the commits the maintainer already added.
- `PRODUCT_RESERVED_SIZE`/super overflow ("exceeds size") → raise reserved-size cuts as in tree commits, or drop apps.
- erofs vendor requires `erofs-utils` on host (Lineage ships its own).

## Phase 3 — Own the blobs (Track B prerequisite; also verification of A)
1. Place firmware zip in `firmware/`. Identify format (OPLUS `payload.bin` OTA zip vs ozip/ofp).
2. Dump: `payload-dumper-go` → `system/system_ext/product/vendor/odm.img` (+ `boot, dtbo, vbmeta, modem` etc.) into `firmware/<region>-<version>/`; `lpunpack` if `super.img`; mount erofs/ext4 read-only to `firmware/<…>/mnt/` (or `fsck.erofs --extract`).
3. In the device tree: `./extract-files.py ~/…/firmware/<…>/mnt` for `bitra` (common first). This regenerates `vendor/realme/{sm8250-common,bitra}` locally; diff against Axion's vendor repo (A16) to validate our pipeline, then use for A17.
4. Fixups: the tree's `extract-files.py` has `blob_fixups` (patchelf of libs, vintf, etc.); on A17 expect new `lib_fixups` (e.g. `_vendor` suffix on shared libs).
5. Commit the vendor tree into a **local git repo** (`roms/vendor-local/…`) so it's reproducible; do NOT publish proprietary blobs publicly.

## Phase 4 — Track B: Android 17
```
mkdir -p roms/lineageos/a17 && cd roms/lineageos/a17
repo init -u https://github.com/LineageOS/android.git -b lineage-24.0 --git-lfs --depth=1
# local manifest: device/common/hardware_oplus/kernel from SM8250-Common lineage-24.0; vendor from our local extraction
```
Expected work items: vendor blob extraction (Phase 3), `Android.bp` / VINTF manifest bumps (HAL versions), sepolicy denials, possibly framework API changes in `hardware/oplus` HALs, kernel merge with latest Lineage `android_kernel_qcom_sm8250` (maintainer already does this).
Reference the working A17 ROM: **Infinity X V‑4.1** (Subodhkr360 / `android_device_realme_bitra`) — study its device tree diffs from lineage-23.2 for what needed changing.

## Phase 5 — Flashing & testing
```
# bitra is non-A/B w/ dynamic partitions → recovery-based flashing
fastboot flash boot boot.img ; fastboot flash dtbo dtbo.img ; (vendor_boot if produced)
# enter recovery (Lineage recovery or the ROM's), "Apply update" zip via adb sideload
```
- Use the **same firmware** required by ROM descriptions (F.20 IN / F.18 EU/GLOBAL) first. Flash order from Infinity X: FW → ROM → format data → reboot.
- Back up first: `fastboot getvar all`, EDL-capable backup of modem/persist/oplusreserve (persist holds fingerprint/sensor calibration — **back up `persist`, `modemst1/2`, `oplusreserve*`, `devinfo`**) before anything experimental.
- Test matrix: boot, WiFi, BT, RIL/data/VoLTE, camera (all sensors, video, OIS), FP (UDFPS), face unlock, NFC, audio (speaker/headset/calls), sensors, USB/OTG, fast charge (VOOC), 120 Hz, DRM L1 (Widevine), vibration, GPS.

## Phase 6 — Signing, OTA, release hygiene
Generate our own release keys (`development/tools/make_key`), `sign_target_files_apks`, `ota_from_target_files`; keep keys offline and *not* in the workspace tree that gets backed up to git. Optional: Lineage Updater with self-hosted OTA JSON.

## Phase 7 — Automation
Adapt `reference/sm8250c_build-script/build.py` (device/source JSON, Telegram/GoFile optional) → `scripts/`. Strip uploader parts unless wanted.

## Timeline guide (realistic)
Phase 0–1: day 1. Phase 2 first build: day 1–2 (+ fix loops). Phase 3: day 2. Boot on A16: day 2–4. Track B: 1–2 weeks of intermittent fixing.
