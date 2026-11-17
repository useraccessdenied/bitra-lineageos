# bitra workspace — Realme GT Neo 2 (RMX3370, codename `bitra`, SM8250-AC / kona)

> **AI-assisted, experimental.** See [AI_DISCLOSURE.md](AI_DISCLOSURE.md) and [ATTRIBUTION.md](ATTRIBUTION.md). Not affiliated with LineageOS, Realme/Oplus or any maintainer; no warranty, flash at your own risk.


Long-term goal: custom ROMs (LineageOS first), then Linux ports (Ubuntu Touch / Halium, postmarketOS, mainline).

## Layout

| Path | Purpose |
|---|---|
| `docs/` | All documentation (start with `docs/03-build-plan.md`) |
| `roms/<name>/` | One folder per ROM source tree (`roms/lineageos/` first; add `roms/axion/` etc. later) |
| `reference/` | Shallow clones of third-party trees/manifests, read-only study material (not part of any build) |
| `firmware/` | Stock firmware zips (F.20 IN / F.18 EU / F.18 GLOBAL) and extracted images/dumps |
| `ccache/` | Shared ccache dir, reused across ROMs (same device, same toolchains) |
| `downloads/` | Misc downloads (platform-tools, release zips) |
| `scripts/` | Helper scripts (host-native): env, 00-host-deps, 02-repo-init, 03-sync, 04-build, manifests/ |
| `bin/` | standalone `repo`, `git-lfs` |
| `logs/` | sync/build logs |

## Docs index

1. `docs/00-environment.md` — host analysis and what must be set up
2. `docs/01-device-research.md` — device facts, partition/boot layout, firmware
3. `docs/02-source-map.md` — every repo found, who maintains it, which branch, how fresh
4. `docs/03-build-plan.md` — **the step-by-step LineageOS build plan** (phases, commands, decisions)
5. `docs/04-linux-ports-roadmap.md` — Halium/Ubuntu Touch, postmarketOS, mainline feasibility
6. `docs/05-risks-and-open-questions.md` — what could go wrong, what is unverified
7. `docs/06-edl-recovery.md` — EDL/9008 tools and our recovery package
8. `docs/07-flashing-a16.md` — artifacts and flashing notes
9. `docs/08-proprietary-analysis.md` — proprietary vs open inventory, open-source/Halium path
10. `docs/09-mainline-and-reverse-engineering.md` — mainline SM8250 status, driver gaps, effort estimate
11. `docs/10-hakios-evaluation.md` — HakiOS (iOS on Android) claims vs reality, viability for bitra
12. `docs/worklog.md` — chronological log; append every session

Status: **A16 build done (releases/a16/). Not flashed yet. Next: OrangeFox, flash, bring-up; then A17.**

## Layout additions
- `backups/` — verified device partition backups (see backups/README.md). Read-only; do not modify.
- `releases/recovery/orangefox/` — OrangeFox R12.0 unofficial recovery image (+ sha256).
