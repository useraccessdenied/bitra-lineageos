# 00 — Host environment analysis (2026-11-08)

## Facts (measured)

| Item | Value | Verdict |
|---|---|---|
| OS | Fedora 44 **Kinoite** (rpm-ostree, immutable) | Do **not** layer build deps on the host; use a container |
| CPU | Xeon E5-2697 v3, 56 threads (Haswell, 2.6 GHz) | Many cores but old/slow per core; expect a full A16/A17 build in roughly 2–4 h cold, ~20–40 min with warm ccache |
| RAM | 125 GiB, 8 GiB zram swap | Plenty. `-j56` is OK; Java/Soong/R8 peaks ~30–40 GB |
| Disk | 1.8 TiB free on `/var` (XFS on LVM over 2×NVMe RAID0) | Enough: source ~150–200 GB synced, out/ ~150–250 GB, ccache 100–200 GB |
| `/tmp` | tmpfs 63 GB | Fine for scratch; keep `TMPDIR` off it for builds that spill |
| Network | online | OK |
| SELinux | Enforcing | Bind mounts into containers need `:Z` (or `--security-opt label=disable`) |
| Shell | fish (login), bash available | Build scripts should be `#!/usr/bin/env bash`; envsetup.sh does not work in fish |
| nofile ulimit | 524288 | OK |
| Layered pkgs | fish, lshw, tailscale, tmux | Keep it that way |

Note: RAID0 means no redundancy — keep patches/scripts/docs in git remotely; sources are re-fetchable.

## Present
git 2.56, python 3.14, curl, wget, rsync, zstd, unzip, 7z, xz, bc, **podman**, **toolbox**.

## Missing (all needed for AOSP/LineageOS)
`repo`, java (JDK 21 for A16/A17 — verify per branch; the build ships its own prebuilt JDK, host JDK is mostly for tools), adb/fastboot, ccache, make/gcc/clang, bison, flex, gperf, lz4, aria2c, and the usual libs (ncurses-compat, libxml2, zlib-dev, openssl-dev, etc.).

## Decision (user): build on the host directly, NO containers
- Build tools live on the host. `repo` and `git-lfs` are standalone binaries in `bin/` (no install needed; scripts add it to PATH).
- Compile deps are layered once with `scripts/00-host-deps.sh` (runs `sudo rpm-ostree install ...`, then **reboot**). adb/fastboot (`android-tools`) installed by the user.
- Risk accepted: Fedora 44 host glibc/gcc are newer than what AOSP is tested on. Soong uses AOSP's own prebuilt clang/JDK for almost everything, so it usually works; if a host-tool build breaks, the fix is a patch or `ALLOW_MISSING_DEPENDENCIES`, not a container.
- Everything is resumable: scripts retry forever, git keeps partial fetches, ccache persists in `ccache/`.

## Setup checklist
- [x] `bin/repo`, `bin/git-lfs`
- [x] `repo init` lineage-23.2 in `roms/lineageos/a16` with local manifest
- [x] Background sync started (`logs/sync-a16.log`)
- [ ] Run `scripts/00-host-deps.sh` + reboot (needed before the build, not before the sync)
- [ ] Firmware zips into `firmware/{IN-F.20,EU-F.18,GLOBAL-F.18}/`
