# 14 — Droidian: can it run from userdata files (keeping Lineage)? (research, 2026-11-17)

Source: subagent read of https://github.com/droidian/initramfs-tools-halium (branch droidian, scripts/halium + hooks), droidian-releng/rootfs-templates, android-image-flashing-template, droidian-images README. Claims are from static reading; nothing run. Upstream Halium initramfs not read.

## Verdict
Viable **without touching any partition** (everything via `fastboot boot` + files on userdata), but needs a small patch to Droidian's initramfs script for vendor.

## Findings
- **Boot order (scripts/halium mountroot):** find userdata -> identify_boot_mode -> `mount_vendor_partitions` -> LVM search -> (non-LVM) mount userdata on /tmpmnt -> identify_file_layout -> mount rootfs/system images.
- **Rootfs location:** default = LVM VG `droidian` inside the userdata partition (what the official fastboot `userdata.img` installs; destroys userdata). With cmdline `droidian.lvm.disable` the non-LVM path is used: it mounts userdata on /tmpmnt and, if `/tmpmnt/rootfs.img` exists, loop-mounts it as the Debian rootfs ("halium" layout). Also supports `/tmpmnt/halium-rootfs/` dir and `systempart=`.
- **Android container image:** looked up as `system.img` then `android-rootfs.img` (in /tmpmnt for the halium layout, else inside the rootfs at /var/lib/lxc/android/). GSI based: packages `android-system-gsi-<apilevel>` + `adaptation-hybris-api<apilevel>`; rootfs recipe default apilevel 28, trixie; supported 28/29/30/32/33.
- **Vendor / odm:** `mount_vendor_partitions` loop-attaches `/dev/disk/by-partlabel/super` to loop0 and builds dm-linear maps with `parse-android-dynparts` -> `/dev/mapper/dynpart-vendor`, tried in order: `/tmpmnt/vendor.img`, by-partlabel vendor*, `/dev/mapper/dynpart-vendor`; accepted only if /vendor/build.prop exists. => unpatched it will mount the vendor in **super = our Lineage vendor, not stock**.
- **BUG:** `/tmpmnt/vendor.img` candidate is dead code: that function runs BEFORE userdata is mounted on /tmpmnt. Fix = run it after the userdata mount (or mount userdata first) and use `mount -o loop,ro`; avoid loop0 (hard-coded for super).
- **odm / other fstab entries:** parsed from the Android ramdisk's fstab* by `mount_android_partitions`, looks only under /dev/disk/by-{partlabel,name,label,...}; dynamic partitions (/dev/mapper/dynpart-*) are not searched => odm needs the same file-based treatment (UNVERIFIED how Droidian handles odm on dynpart devices like miatoll).
- **Install procedure (official):** `flash_all.sh` flashes boot/dtbo/vbmeta/vendor_boot (if present) and `userdata.img` only; never system/vendor/super; but it ERASES userdata. Recovery-zip variant drops `data/rootfs.img` (plain ext4 image, IMG_SIZE = rootfs+250MB) — i.e. the rootfs.img layout is an officially produced artifact.
- Initramfs binaries (parse-android-dynparts, dmsetup, lvm, losetup via droidian-minienv) — location in initrd UNVERIFIED.

## Plan (no partition writes)
1. Obtain a Droidian generic rootfs (recovery-zip style `rootfs.img`, arm64, apilevel TBD 30 vs 32) from droidian-images releases — verify asset names/sizes first (not yet checked).
2. Build our boot image = OUR kernel (releases/droidian-kernel) + a Droidian initrd (taken from a Droidian boot image/package, repacked with Python cpio — no root) with `scripts/halium` patched: mount userdata first, loop-mount `/tmpmnt/vendor.img` (+ odm.img), then proceed. cmdline adds `droidian.lvm.disable` (+ stock cmdline pieces).
3. Put on userdata (f2fs, Android FBE: root dir files are not encrypted): `rootfs.img`, `vendor.img` (stock raw EROFS from firmware/stock-a13/vendor.raw), `odm.img`. Write them from the running Lineage with root (su/adb) or from the debug initramfs shell — userdata gets ~4-6 GB extra files; delete to undo.
4. Boot with `fastboot boot` from the Mac (nothing flashed); debug over USB NCM (needs Droidian's USB debug to be NCM-friendly: usb gadget in initramfs is RNDIS by default -> patch to NCM for macOS).
## Open questions / risks
- Halium api level for an Android 12-level vendor under Android 13 (30 vs 32).
- Does f2fs userdata mount cleanly in initramfs (Android's userdata is f2fs with encryption; mount option handling in scripts/halium assumes ext4 `data=journal`).
- Reboot after use: vol-up+power 6 s works; from our debug shell `reboot -f`.

## Update: user allows wiping Lineage / flashing stock vendor / repartitioning super (2026-11-17)
Everything is open, so use the standard Droidian shape instead of the userdata-files trick.
Verified by range-reading the official release zips (scripts/remote_zip.py; releases https://github.com/droidian-images/droidian/releases, stable `droidian/101.20261023`, nightly `nightly`):
- `droidian-OFFICIAL-phosh-phone-rootfs-api{28,29,30,32,33}-arm64-*.zip` (~1.4-1.5 GB each) = generic recovery-zip: `data/rootfs.img` (4.3 GB ext4), setup.sh, tools/busybox.
- Device images (e.g. sony_bahamut-api30, 1.6 GB): `data/{boot.img (36 MB), recovery.img, userdata.img (LVM sparse, 4 GB), dtbo.img, vbmeta.img, device-configuration.conf}` + `flash_all.sh`. Fetched boot.img + conf + flash_all.sh to downloads/droidian-ref/bahamut/.
- bahamut boot.img (header v1, 4.14 kernel) carries a **46 MB Droidian initramfs** (gzip cpio): scripts/halium (986 lines), scripts/panic/telnet (USB debug, **RNDIS**, 192.168.2.15), dmsetup, parse-android-dynparts, cryptsetup, dropbear, plymouth, unl0kr. We can reuse it with OUR kernel (initrd is kernel-agnostic; drivers are built in) and edit it in Python (no root).
- In THIS initrd version: LVM only with `droidian.lvm.prefer`; otherwise userdata is mounted and `/tmpmnt/rootfs.img` (halium layout) is used. /vendor comes from the Android ramdisk fstab via by-partlabel lookup; no dynamic-partition (super) handling is visible in scripts/halium (parse-android-dynparts binary shipped but not referenced) => our initramfs patch must set up dm-linear devices for vendor/odm from super and mount them.
- Vendor API level: stock vendor fingerprint `qti/kona/kona:12/RKQ1.211119.001` -> RKQ1 = Android 11 (R) build => Droidian **api30**.
- Host has: lvm, mke2fs/mkfs.ext4, resize2fs, e2fsdroid, img2simg/simg2img, lpmake/lpdump (AOSP host bins in the a16 tree), dmsetup, qemu-aarch64-static, bwrap, unshare. `sudo` needs a password (not usable by me); debootstrap/debos not installed.
### Install plan (artifacts built here, flashed by the user on the Mac)
1. `super.img` (lpmake, sparse): stock vendor.img + odm.img only, same geometry as stock (size 10200547328, group qti_dynamic_partitions 10196353024, metadata 65536, 1 slot).
2. `userdata.img` (ext4, sparse, rootless `mke2fs -d`): contains `rootfs.img` from the api30 rootfs zip, enlarged with resize2fs (no LVM, no root).
3. `boot.img`: our kernel + patched Droidian initrd (NCM gadget for macOS, vendor/odm dm-linear mount) + header v2 offsets; can be `fastboot boot`-ed first (RAM only) before flashing boot.
4. stock dtbo + vbmeta (flash vbmeta with --disable-verity --disable-verification).
Rollback: OrangeFox + releases/a16-latest zip, or backups/20261116-213951 partitions.
