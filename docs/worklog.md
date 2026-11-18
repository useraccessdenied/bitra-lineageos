# Worklog

## 2026-11-08 — Research & planning (session 1)
- Analyzed host (Fedora 44 Kinoite, 56 threads, 125 GiB RAM, 1.8 TiB free, podman/toolbox present, no build deps).
- Searched GitHub API/web for bitra trees; shallow-cloned into `reference/`: SM8250-Common (device bitra + common, local_manifest, build-script), bijoyv9 (local_manifest, device_manifests).
- Found: device/common/kernel/hardware trees have `lineage-24.0`; vendor blobs only up to `lineage-23.2` (AxionAOSP-devices, public).
- Wrote docs 00–05 and created workspace dirs (`docs roms/lineageos firmware ccache downloads scripts reference`).
- Nothing synced/built. Next: user answers open questions in `05`, then Phase 0.

- Follow-up (user hint): checked bijoyv9/Saichaitanya888/arsalan-zeus accounts. bijoyv9 GitLab has `vendor_realme_sm8250-common` on lineage-24.0; bitra vendor stops at 23.2. See `02-source-map.md` per-developer section.

## 2026-11-08 — Setup & sync start (session 1, cont.)
- User decisions: no podman (host-native build), start with Android 16, bootloader unlocked, android-tools installed by user, firmware zips to be copied later (dirs `firmware/IN-F.20|EU-F.18|GLOBAL-F.18` created), slow internet -> resumable.
- Installed `bin/repo` (2.71), `bin/git-lfs` (3.8.1). Wrote `scripts/` (env, 00-host-deps, 02-repo-init, 03-sync, 04-build).
- `repo init` lineage-23.2 done; `03-sync.sh a16 3` started in background (network-only phase first, then checkout).
- Host still lacks gcc/make/ccache/bison/flex/etc.: run `scripts/00-host-deps.sh` + reboot before building (rpm-ostree was busy with another transaction when checked).

## 2026-11-08 (evening) — Sync complete, firmware arrived
- A16 sync finished 21:42 IST (119 GB in `roms/lineageos/a16`; all device/vendor/kernel/hardware projects present, kernel at "Bump kernel version to 1.7"). `scripts/status.sh` project counter is a rough heuristic; the authoritative signal is `.sync-complete`.
- Firmware zips arrived and were sorted into `firmware/{IN-F.20,EU-F.18,GLOBAL-F.18}/` (flashable "firmware-update" zips: modem, tz, xbl, hyp, aop, dspso, etc.; not full ROMs).
- `firmware/EDL/prog_firehose_ddr4_fwupdate.elf` plus `firmware/RMX3370export_11_13.1.0.1100EX01_*.zip` (~8 GB, user still downloading) = EDL/MSM recovery package for hard-brick recovery. Do not touch until the download finishes.
- Pending: user installing platform-tools and running `scripts/00-host-deps.sh` (+ reboot) before the first build.

## 2026-11-08 (night) — EDL package + rpm-ostree network issue
- EDL package verified (`unzip -t` OK, 360 files, 9.5 GB uncompressed) and moved to `firmware/EDL/` with sha256 + README. Contains full Android 13 images, so it can serve as the blob-extraction source too.
- rpm-ostree/dnf failing: diagnosed as **IPv6 path to Fedora hosts is dead** (every AAAA address of mirrors/dl.fedoraproject.org times out; every IPv4 address works at ~0.2 s; Google over IPv6 works, so it is specific to the route/ISP to Fedora's v6 ranges). Clients that try IPv6 first stall. Fix: prefer IPv4 in `/etc/gai.conf` (needs sudo, user to apply).
- Dropped java-21-openjdk-headless from 00-host-deps.sh (not in Fedora 44 repos; unnecessary, build uses prebuilts/jdk).

## 2026-11-09 — Deps installed, host on Fedora 45, first build started
- User finished deps + Fedora 45 upgrade. Fixed `breakfast` target (use `bitra`, not `lineage_bitra`). Config OK: Android 16 (BP4A.251205.006), `lineage_bitra`, LINEAGE_VERSION 23.2.
- Build started 01:14 IST via `scripts/04-build.sh a16 userdebug`; logs `logs/build-a16-*.log`, console `logs/build-a16-console.log`. Monitored in background; fix recoverable errors.
- EDL tools researched: see `docs/06-edl-recovery.md` (qdl, bkerler/edl both available).
- 03:3x IST: build hit 86% and failed on `external/chromium-webview/prebuilt/*/webview.apk` ("failed opening zip"): they were git-lfs pointer files (sync's checkout does not smudge LFS because `repo sync -l` + `--depth`). Fix: `repo forall -j8 -c "git lfs pull"` (done; 4 APKs 98–359 MB). `03-sync.sh` now runs it before writing `.sync-complete`. Rebuild resumes incrementally.
- 2nd build failure (75%): `check_boot_jars` rejects `net.oneplus.odm` in `hardware/oplus/oplus-fwk` boot jar. Local patch to `build/soong/scripts/check_boot_jars/package_allowed_list.txt` adds `net\.oneplus\.odm` and `oplus\.content\.res` (saved: `scripts/patches/build-soong-allow-oneplus-odm.patch`; re-apply with `git apply` in `build/soong` after any resync that resets it).
- 04:2x IST: **A16 BUILD SUCCEEDED**. `lineage-23.2-20261108-UNOFFICIAL-bitra.zip` (2.07 GB) + boot/dtbo/recovery/vbmeta copied to `releases/a16/`. Needed three fixes: git-lfs pull (webview), boot-jar allow list x2 packages. Flash notes: `docs/07-flashing-a16.md`. Not flashed yet.

## 2026-11-09 — Android 17 sync started
- New `roms/lineageos/a17` (lineage-24.0), local manifest `scripts/manifests/bitra-lineage-24.0.xml`: device/common/hardware/kernel from SM8250-Common lineage-24.0, sm8250-common vendor from bijoyv9 GitLab lineage-24.0. **Pinned to 23.2** (no 24.0 branch exists): vendor/realme/bitra, vendor/oplus/camera, hardware/dolby, RealmeAddons.
- `scripts/03-sync.sh a17 3` running in background; log `logs/sync-a17.log`. Re-run same command to resume. User flashing the A16 build via OrangeFox meanwhile.
- Reminder: re-apply `scripts/patches/build-soong-allow-oneplus-odm.patch` in a17 `build/soong` if the boot-jar check fails again.

## 2026-11-09 — Proprietary-component analysis
- Wrote docs/08-proprietary-analysis.md (inventory from proprietary-files.txt: 1,601 entries, 857 libs; DTS chip list; paths: postmarketOS mainline vs Halium vs Android).

- Wrote docs/09 (mainline SM8250 status checked against torvalds/linux master).

- Wrote docs/10 (HakiOS evaluation; found Mu-Silicium bitraPkg UEFI port).

## 2026-11-12
- Added scripts/backup_partitions.py (OrangeFox adb partition backup, incl. ocdt); warning in docs/07 about never flashing generic ocdt. A17 sync completed 09:31 IST (not built yet).
- Organized workspace: moved OrangeFox image to releases/recovery/orangefox/, verified+locked backups/20261116-213951 (67 partitions), added backups/README.md.
- 2026-11-16: A16 booted on device (flashed by user). Facts: non-A/B confirmed; vbmeta NOT needed. Camera app crash -> added OplusTypeCastingHelper stub to hardware/oplus/oplus-fwk; rebuilding (log: logs/build-a16-2026-11-16-*.log).
- 2026-11-16: A16 rebuild (oplus-fwk OplusTypeCastingHelper fix) running. A17 prepared (soong allow-list patch applied in a17/build/soong, same OplusTypeCastingHelper stub added) and queued via scripts/queue_after.py to start when the A16 build ends. An accidental early A17 start was killed; logs/build-a17-2026-11-16-2223.log is from that aborted attempt.
- 2026-11-16: logged brightness-flash-on-lock issue (UDFPS optical FOD) in docs/known-issues.md.
- 2026-11-16: diagnosed brightness flash: dimlayer_hbm=1 asserted at going-to-sleep via UDFPS overlay (see docs/known-issues.md).
- 2026-11-16: A16 rebuild OK (16:35): releases/a16-oplusfwk-fix/lineage-23.2-20261116-UNOFFICIAL-bitra.zip sha256 2a6ad2c0...8b22 (has OplusTypeCastingHelper fix). A17 build: first attempt failed in soong (vendor/realme/sm8250-common prebuilt deps android.hardware.common-V2-ndk_platform / keymaster-V3-ndk_platform undefined in A17 -> renamed to -ndk in a17 vendor tree, uncommitted local edit). Second attempt running (logs/build-a17-2026-11-16-2248.log).
- 2026-11-16: wrote UDFPS brightness-flash fix (UdfpsController defers overlay until screen off) in a16 frameworks/base; patch saved in scripts/patches/. A16 rebuild queued (queue_after.py a16) behind the running A17 build. Spawned research for Subodh Evolution-X A17 bitra trees.
- 2026-11-17: wrote docs/11-droidian-estimate.md (Droidian port effort estimate).
- 2026-11-17: wrote docs/12-postmarketos-estimate.md (nura wiki unreachable; used docs/09 + pmOS wiki).
- 2026-11-17: queued scripts/gh_lookup.py (waits for builds, then reads SM8250-Common kernel branches + Saichaitanya888 TWRP tree -> logs/gh-lookup.txt).

## 2026-11-17 — A16 UDFPS fix built; A17 VINTF failure fixed; A17 rebuild
- A16 with UdfpsController brightness fix built: releases/a16-udfps-fix/ (sha256 29b1f7a8…8a3ab3a62518). Untested on device.
- A17 failed at 97% in check_vintf: `android.hardware.biometrics.face.IFace/default (@1)` — Oplus face HAL is AIDL v1, A17 FCM 7/8/202404+ requires IFace >= 3.
  Fix (option 1): removed manifest_oplus_face.xml (sm8250-common-vendor.mk + Android.bp) and the vendor.oplus.hardware.biometrics.face@1.0-service package (common.mk). Face unlock unsupported on A17 build; fingerprint unaffected.
- Applied scripts/patches/frameworks-base-udfps-defer-overlay-on-sleep.patch to a17 frameworks/base.
- Oplus camera (OplusCamera / com.oplus.camera) is already in both trees via vendor/oplus/camera (opluscamera.mk); no extra work needed.
- GitHub lookups: logs/gh-lookup.txt (kernel lineage-24.0 = Entropy-1.7 newest; TWRP tree is prebuilt-kernel recovery).
- Note: queue_after.py polls `pgrep -f 04-build.sh`, which matches any shell command containing that text; start builds directly when needed.
- A17 rebuild started: logs/build-a17-2026-11-17-0832.log (the second launch collided on out/.lock; harmless)

## 2026-11-17 — AVF/Terminal app feasibility; containers direction
- A17 tree contains Terminal app + AVF (packages/modules/Virtualization) but SM8250 runs Android at EL1 under Qualcomm's hypervisor (hyp.img strings: "unmap Hypervisor from HLOS Stage 2", "remap region from EL2"). KVM unusable; hyp is signed firmware -> not replaceable. Terminal app not feasible here.
- Chosen direction: containers on the Android kernel. Kernel .config (a17/out/.../KERNEL_OBJ/.config) status:
  - ON: NAMESPACES, UTS_NS, NET_NS, OVERLAY_FS, VETH, BRIDGE, NF_NAT, IP_NF_TARGET_MASQUERADE, CGROUP_BPF, MEMCG(+SWAP), SECCOMP_FILTER, KEYS, FUSE, TUN
  - OFF: PID_NS, USER_NS, IPC_NS (absent), CGROUP_DEVICE, CGROUP_PIDS, CFS_BANDWIDTH, POSIX_MQUEUE, FHANDLE, BINFMT_MISC, NETFILTER_XT_MATCH_ADDRTYPE, MACVLAN, VXLAN, CHECKPOINT_RESTORE, SQUASHFS, BLK_DEV_THROTTLING

## 2026-11-17 — Droidspaces kernel prep; root status
- A16/A17 builds are NOT rooted: userdebug with Lineage's PRODUCT_NOT_DEBUGGABLE_IN_USERDEBUG (ro.debuggable=0, ro.secure=1), no `su` in image (vendor/lineage common.mk adds `su` only if WITH_SU=true; adb_root package is present). Droidspaces needs root (su/Magisk/KernelSU/WITH_SU).
- Droidspaces non-GKI fragment saved: scripts/kernel-config/droidspaces.config; scripts/check_kernel_config.py compares it with the built .config (38 ok, 15 must change, 8 absent/nonexistent in 4.19).
- Droidspaces non-GKI patches (Droidspaces-OSS@cdadb9e): 02 cgroup file prefix applies to our kernel (cgroup.c offset 455); 01 xt_qtaguid panic fix N/A (xt_qtaguid.c not in our tree). Nothing applied to the tree: waiting for the A17 build to finish.
- A17 retry (08:32 build) failed again after 10 min in check_elf_file for android.hardware.biometrics.face-V1-ndk_platform (blob DT_NEEDED *-ndk_platform vs our -ndk rename). Since face HAL is dropped, also removed the face lib, face service package and its init rc copy from vendor/realme/sm8250-common/sm8250-common-vendor.mk (generated file; re-apply if blobs are re-extracted). Rebuild started: logs/build-a17-console-retry2.log.

## 2026-11-17 — KernelSU check; WITH_SU
- Neither kernel tree has KernelSU: no drivers/kernelsu, no KSU configs in a16 (AxionAOSP-devices) or a17 (SM8250-Common lineage-24.0). Only CONFIG_KPROBES=y. KernelSU/susfs/manual hooks exist only on SM8250-Common branches `sus` and `test` (bijoyv9 Entropy), see logs/gh-lookup.txt.
- Decision: use WITH_SU=true for both trees. scripts/04-build.sh now exports WITH_SU=true by default (override: WITH_SU=false). Builds started after this carry `su` (/system/xbin/su). A16 needs a rebuild to get it.
- A17 build restarted with WITH_SU=true: logs/build-a17-console-retry3.log (previous run stopped at ~95% of analysis, nothing lost except minutes).

## 2026-11-17 — Build stopped; KernelSU plan (user: Lineage su unusable, wants KernelSU + SusFS)
- Stopped the A17 build (WITH_SU retry). 04-build.sh still defaults WITH_SU=true: revert/decide before the next build.
- SM8250-Common branches: lineage-24.0 (Entropy-1.7) has NO KSU/susfs. `sus` branch (Entropy-1.5, 2026-06-05) has: 3be72cd6a "Import susfs 2.1.0" (fs/susfs.c, include/linux/susfs*.h), 13ae07457 "KSU: Add manual hooks" (CONFIG_KSU_MANUAL_HOOK in input.c, exec.c, open.c, read_write.c, stat.c, reboot.c, sys.c). `test` branch 02bd78213 "defconfig: Add KernelSU configs": CONFIG_KSU=y, CONFIG_KSU_MANUAL_HOOK=y, KPROBES/HAVE_KPROBES/KPROBE_EVENTS off (in kona-perf_defconfig).
- The KernelSU driver itself (drivers/kernelsu) is NOT in the branch: drivers/Makefile and Kconfig have no ksu entries, so it must be added from a KernelSU variant repo. Variant not yet chosen. Manager app also needed.

## 2026-11-17 — A16 test feedback: camera + HBM fixes did not fully work (log: camera-crash.log, captured 09:18–09:34 on the new A16 build)
**Camera (com.oplus.camera):**
- Fixed: the OplusTypeCastingHelper NoClassDefFoundError is gone; the app now starts and opens camera 0.
- New failure: CameraService `endConfigure: Error configuring streams: Function not implemented (-38)`. HAL (CamX, pid 1189) log: `configure_streams() Number of streams: 4` -> `CHIUSECASE AdvancedCameraUsecase::Initialize usecaseId:1 num_streams:4` -> `~OPMetaManager` -> fails silently. App then logs "stream surface error 10002 ... camera app will kill self" and SIGKILLs itself; the launcher respawns it -> crash loop (54 identical attempts).
- Failing config (CameraBuddy): operationmode 0x8001 (vendor mode), streams RAW16 4608x3456 (input, type 1), YUV 1440x1080, RAW16 4608x3456, YUV 4608x3456. A plain 1-stream PRIVATE/preview usecase (operationmode 0, from another client) initializes fine, so the HAL itself works; only the Oplus advanced/reprocess mode fails.
- Also seen: `hal_camera_default` (172x), `vendor_pd_mapper`, `vendor_mdm_helper` denied `read` on property area u:object_r:system_prop:s0 (labels sys./dev./net./hw./service./ro.hw.). Probably harmless but unproven as cause.
- Not yet known: why AdvancedCameraUsecase::Initialize fails. CamX log level is INFO only. Needs verbose CamX logging (needs root) or comparison with a working reference build (Axion A16 for bitra); candidates: missing feature/algo libs, odm camera config (odm/etc/camera/*), vendor props, operation-mode support in the A13 CamX HAL.
**Lock-screen HBM flash:** log shows the UDFPS overlay is now added AFTER screen off (09:19:32.577), so UdfpsController deferral works, but the flash remains. Actual trigger: at going-to-sleep KeyguardUpdateMonitor starts fingerprint listening (shouldListenKeyguardState has `|| mGoingToSleep`), BiometricScheduler starts FingerprintAuthenticationClient at 09:19:31.606; 2 ms later the kernel logs `oplus_display_set_dimlayer_hbm set = 1`, then `OnscreenFingerprint mode: Enter`, `qcom,mdss-dsi-hbm-on-command` (31.622) — ~0.43 s before the panel goes off (32.055). So the Oplus fingerprint HAL asserts HBM at authenticate() time.
- Fix #2 (both a16 and a17, UNBUILT/UNTESTED): KeyguardUpdateMonitor.shouldListenForFingerprint no longer listens for UDFPS while mGoingToSleep; listening restarts in handleFinishedGoingToSleep (display off). Patch: scripts/patches/frameworks-base-udfps-defer-fp-listen-on-sleep.patch. Risk: fingerprint-listening gap at sleep start; verify screen-off unlock/AOD behaviour.
- 04-build.sh default WITH_SU reverted to false.

## 2026-11-17 — KernelSU + SuSFS + Droidspaces in A17 kernel (in progress)
- Variant chosen: **ReSukiSU** (github.com/ReSukiSU/ReSukiSU @7b65bde, 2026-11-16). Reason: its Kconfig has CONFIG_KSU_MANUAL_HOOK and CONFIG_KSU_SUSFS (inline hook), and it exports every symbol the maintainers' hooks reference (ksu_handle_stat, ksu_init_rc_hook, ksu_input_hook, ksu_execveat_hook, ...). KernelSU-Next's current Kconfig has no KSU_MANUAL_HOOK (my earlier assumption that it did was wrong). Non-GKI 4.19 is supported through the manual / susfs-inline methods.
- a17 kernel (kernel/realme/sm8250): cherry-picked SM8250-Common `sus` commits 13ae07457 (KSU hooks) and 3be72cd6a (susfs 2.1.0) cleanly; committed locally as 578d6f30a0c. ReSukiSU cloned in full (Kbuild needs a git checkout) at kernel/KernelSU, symlink drivers/kernelsu -> ../KernelSU/kernel, drivers/Makefile + drivers/Kconfig hooked (as ReSukiSU setup.sh would).
- Config appended to arch/arm64/configs/vendor/kona-perf_defconfig: KSU=y, KSU_SUSFS=y (+SUS_PATH/MOUNT/KSTAT, SPOOF_UNAME, OPEN_REDIRECT, SUS_MAP), KSU_MANUAL_HOOK off (hooks are mutually-exclusive choices; the susfs inline hooks are the active set), plus the Droidspaces fragment. Droidspaces cgroup patch 02 applied (kernel/cgroup/cgroup.c). 01 (xt_qtaguid) N/A.
- Manager app: ReSukiSU manager APK must be installed separately (matching the kernel driver).
- Validation: 04-build.sh now takes a 3rd arg (target); started `04-build.sh a17 userdebug bootimage` (logs/build-a17-bootimage.log) to compile only the kernel + boot image first. A16 kernel (Axion tree) not ported yet.
- ReSukiSU @7b65bde (latest) failed inline_hook_check: "ksu_input_hook is incompatible hook" — current ReSukiSU requires the newer susfs static_key hooks (susfs commit 00be2d47), but the maintainers' susfs 2.1.0 port uses old `bool` hooks. Pinned kernel/KernelSU to b6ec6e08 (2026-04-18, last commit before the 2026-04-19 "bool hook as incompatible" check). Rebuilding bootimage: logs/build-a17-bootimage2.log. Manager APK must match this older ReSukiSU (~April 2026) — to verify.

## 2026-11-17 — Axion reference comparison (ref/axion-2.9-NOESIS-20261023-OFFICIAL-CORE-bitra.zip, Android 16, block-based OTA)
- Added scripts/unpack_blockota.py (stdlib; new.dat.br + transfer.list -> raw .img). odm/vendor are EROFS (fsck.erofs --extract), system/system_ext/product are ext4 (debugfs rdump). Extracted to ref/axion-img (raw) and ref/axion (trees).
- Findings vs our A16 build (out/target/product/bitra): odm+vendor file lists identical for all camera/oplus files; camera blobs/configs byte-identical; vendor/odm build.prop identical except userdebug/test-keys; camera props identical (persist.vendor.camera.privapp.list, lens packages). OplusCamera.apk same size (differs by a few bytes); oplus-support-wrapper.jar identical; Axion's oplus-fwk.jar does NOT contain OplusTypeCastingHelper (ours is +380 B because of our stub). Kernel: both 4.19.325-cip136-st20-Entropy-1.7, identical kernel size and IKCONFIG (0 option diffs), but different binaries (different build).
- Conclusion: nothing obvious in the camera blobs/props/kernel config differs. Remaining candidates: Axion framework/SELinux/Oplus app behaviour, or Axion's camera also failing the same way. Need to know whether the Oplus camera actually works on the Axion build.
- A17 kernel link failed (ksu_init_rc_hook_key_false, ksu_input_hook_key_false, ksu_input_hook, ksu_init_rc_hook, ksu_execveat_hook undefined): ReSukiSU's SUSFS mode expects static-key hooks from the kernel side; susfs 2.1.0 port uses bool hooks. Added glue in fs/susfs.c (bools + static keys enabled at early_initcall; ksu_execveat_hook=false). Rebuilding: logs/build-a17-bootimage3.log.
- User confirmed the Oplus camera works on the Axion build. Extra property diff (Axion vs ours): Axion adds persist.sys.device_camera_info_front=16 / _rear=64,8,2 (not referenced by OplusCamera.apk dex: dead end), ro.face.sense_service=true, ro.adb.secure=1, and many Axion-specific persist.sys.ax_* props (incl. ax_hbm_file=/sys/class/backlight/panel0-backlight/hbm_mode, ax_hbm_supp=false). init.axion.rc / init.axion.modules.rc exist only on Axion. Vendor camera blobs/props otherwise identical. Next: need an Axion logcat of the camera launch to diff requested stream config (CameraBuddy / CHIUSECASE lines) and avc denials.

## 2026-11-17 — KernelSU/SuSFS/Droidspaces kernel builds OK (A17 bootimage); A16 ported + full build started
- A17 `bootimage` build succeeded (logs/build-a17-bootimage3.log, 07:17): .config has CONFIG_KSU=y, KSU_SUSFS=y (+SUS_PATH/MOUNT/KSTAT, SPOOF_UNAME, OPEN_REDIRECT, ...), kernel string v4.1.0-b6ec6e08@ReSukiSU. Droidspaces check: 55 options OK, 0 conflicting; 6 absent = options that do not exist in 4.19 (FW_LOADER_COMPRESS, NETFILTER_XT_TARGET_MASQUERADE -> IP_NF_TARGET_MASQUERADE=y, NF_CONNTRACK_NETLINK -> NF_CT_NETLINK=y, NF_CONNTRACK_IPV4/6 merged into NF_CONNTRACK=y, ANDROID_PARANOID_NETWORK).
- Patch for reuse: scripts/patches/kernel-ksu-susfs-droidspaces-a17-base.patch (everything except the KernelSU checkout/symlink). Applied cleanly to the A16 kernel (Axion tree, HEAD 5029be34d). KernelSU cloned to a16 kernel/KernelSU pinned b6ec6e08, symlink drivers/kernelsu.
- A16 full build started (WITH_SU=false): logs/build-a16-ksu.log. Contains: camera stub (earlier), UDFPS deferral #1+#2, KernelSU+SuSFS+Droidspaces kernel. NOT yet tested on device.
- To do after flashing: install matching ReSukiSU manager (kernel is ReSukiSU v4.1.0 @ b6ec6e08, 2026-04-18), check `su`/root manager, run Droidspaces "Check Requirements".
- A16 build failed at check_vintf (kernel FCM level 7 requires SYSVIPC=n, IP6_NF_NAT=n). Set PRODUCT_OTA_ENFORCE_VINTF_KERNEL_REQUIREMENTS := false in sm8250-common/common.mk (a16 + a17). Rebuild: logs/build-a16-ksu2.log.
- A16 build SUCCEEDED (logs/build-a16-ksu2.log): releases/a16-ksu-droidspaces/lineage-23.2-20261117-UNOFFICIAL-bitra.zip, sha256 cda1094caeda1a8c61334d7f8f51e7a1b8d49bca19d790866ef40f2837cda8ab. Built kernel .config: KSU=y, SYSVIPC/PID_NS/USER_NS=y. Contains: camera stub, UDFPS deferral #1+#2 (fp listening deferred until display off), KernelSU(ReSukiSU)+SuSFS, Droidspaces kernel opts. No Lineage su (WITH_SU=false). UNTESTED on device.
- A17 full build started: logs/build-a17-full.log (Face HAL removed, brightness fixes, KSU kernel, VINTF kernel check off).
- A17 full build failed at check-selinux-treble-labeling (opluscamera_app is a platform app with a non-coredomain label; enforced for BOARD_API_LEVEL>=202604). Added vendor/oplus/camera/sepolicy/private/opluscamera_app.te: userdebug_or_eng typeattribute opluscamera_app treble_labeling_violators (userdebug only; a user build would need the app moved to coredomain or odm). Rebuild: logs/build-a17-full2.log
- A17 full build SUCCEEDED (logs/build-a17-full2.log): releases/a17-ksu-droidspaces/lineage-24.0-20261117-UNOFFICIAL-bitra.zip. Includes Face HAL removal, UDFPS fp-listen deferral, ReSukiSU+SuSFS+Droidspaces kernel, treble-labeling exemption. UNTESTED on device.

## 2026-11-17 — Drop OplusCamera, use Lineage Aperture
- HBM fix #2 confirmed working on device. Oplus camera still broken (AdvancedCameraUsecase 0x8001).
- Removed `OplusCamera` from vendor/oplus/camera/camera-vendor.mk (a16+a17; generated file, re-apply after re-extract). The
  OplusCamera android_app_import `overrides` Aperture/Camera2, so removing it lets Aperture (common_mobile_full.mk) build.
- Support libs/blobs/oplus-support-wrapper left in place (HAL deps). Needs rebuild + test.

## 2026-11-17 — Published to GitHub (all public)
- gh 2.104 installed via mise (user-level). Account `useraccessdenied`.
- Forks (upstream history/authorship kept; our commits on `bitra/a16` / `bitra/a17`, each with AI_DISCLOSURE.md):
  android_{device_realme_sm8250-common,hardware_oplus,kernel_realme_sm8250}-axion (a16) and -sm8250common (a17).
  Kernel branches pin ReSukiSU as submodule `KernelSU` (b6ec6e08).
- Tracking repo: https://github.com/useraccessdenied/bitra-lineageos (docs, scripts, manifests/<tree>/bitra.xml pointing at the forks,
  patches/<tree>/ for frameworks/base, build/soong, vendor/* — blobs are never pushed). ATTRIBUTION.md + AI_DISCLOSURE.md.
- Re-publish with `python3 scripts/publish_trees.py --go`.
- Started rebuild: A16 (Aperture instead of OplusCamera) then A17.

## 2026-11-17 — Custom ReSukiSU manager signing key
- A16 Aperture build finished (releases/a16-aperture, sha 044fef17…). A17 paused (killed early) to add manager key.
- No usable ReSukiSU manager exists for kernel b6ec6e08 (releases need >=35002). Building manager from pinned source.
- Kernel only trusts manager APKs with known cert (size+sha256). Generated own key: keys/bitra-ksu.jks (+ keys/sign.properties,
  git-ignored; BACK THIS UP). Cert size 747, sha256 206b094c…8478. Added `export KSU_EXPECTED_SIZE/HASH` to drivers/Makefile in both kernels.
- Rebuilding A16 then A17 with this kernel.
- Built manager from pinned source (b6ec6e08): ksud via cargo-ndk (rust stable 1.100, NDK 28.2, arm64 only, tools via mise/rustup),
  APK via Gradle 9.4.1 + AOSP jdk21, signed with keys/bitra-ksu.jks. Version code 34830 = kernel's. Cert sha256 verified = kernel's
  KSU_EXPECTED_HASH. Output: releases/resukisu-manager/ReSukiSU_v4.1.0_34830-arm64-v8a-release.apk. Works only with kernels built with the key patch.

## 2026-11-17 — Final builds with manager key
- A16 (Aperture, no OplusCamera) and A17 built OK; boot.img kernel contains the manager cert hash. Zips: releases/a16-latest, releases/a17-latest (sha in SHA256SUMS).
- Deleted superseded releases (a16-oplusfwk-fix, a16-udfps-fix, a16-ksu-droidspaces, a16-aperture, a17-ksu-droidspaces). Kept releases/a16 (first
  known-booting baseline + images), recovery/, resukisu-manager/. Kernel changes pushed to the forks.

## 2026-11-17 — A16 and A17 verified by user; Droidian stage 0
- User: A16 + A17 both work (root, ReSukiSU manager, Droidspaces, HBM fix, battery good). Starting Droidian.
- Recon summary in docs/11-droidian-estimate.md. Blocker: need stock Android 13 vendor (full RUI 4.0 OTA); Droidian caps at Android 13; Docker-based tooling replaced with host-native.
- Droidian: stock A13 package found in firmware/EDL; vendor (API30/Android12-level Treble vendor) + boot extracted to firmware/stock-a13/. See docs/11.
- Droidian stage 1: kernel builds with Halium/Droidian fragments in a separate tree (roms/droidian/kernel, branch droidian pushed to fork). Artifacts releases/droidian-kernel/. Test machine is a Mac (see docs/11).
- Droidian stage 2: debug initramfs + RAM boot image built (releases/droidian-debug); Mac test procedure in docs/13.
- Droidian stage 2 PASSED: RAM boot, USB NCM shell from Mac (docs/11).
- Droidian: userdata-files install researched (docs/14): viable via patched initramfs (vendor.img dead-code bug), no partition writes. User reboots RAM-boot with vol-up+power 6s.
- Droidian: user OK'd wiping Lineage. Verified official rootfs/initrd assets; plan in docs/14 (super.img via lpmake, userdata ext4 w/ rootfs.img, patched initrd).
- Droidian install artifacts built (releases/droidian-install: boot/super/userdata). Mac test procedure docs/15. Test 1 (RAM-boot, no wipe) first.
- 2026-11-18: Droidian boots to systemd userspace on bitra (RAM boot): plymouth logo, root shell over USB NCM.

## 2026-11-18 — Droidian bring-up #3–#6
- Phosh up; fixed touch (kernel abs axes + notify_panel_blank resume), audio (policy overlay + HAL rc), BT/modem boot services, device name, auto-brightness curve, persistent journal, Wi-Fi route workaround (bitra-net-watch). Details + open issues: docs/17-droidian-bringup-3-to-6.md.
- Open: clean Wi-Fi route fix, Bluetooth Settings toggle/name, splash gap. Scripts: scripts/build_droidian_install.py, scripts/audio_sanitize.py.
