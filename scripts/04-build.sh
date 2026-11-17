#!/usr/bin/env bash
# Usage: 04-build.sh [dir=a16] [variant=userdebug] [target=bacon]. Needs 00-host-deps.sh applied.
set -euo pipefail; . "$(dirname "$0")/env.sh"
export WITH_SU=${WITH_SU:-false}  # Lineage su unusable; root comes from KernelSU
DIR=${1:-a16}; VAR=${2:-userdebug}; TGT=${3:-bacon}; cd "$WS/roms/lineageos/$DIR"
bash -c "source build/envsetup.sh && breakfast bitra $VAR && ccache -M 200G && mka $TGT -j\$(nproc)" 2>&1 | tee "$WS/logs/build-$DIR-$(date +%F-%H%M).log"
