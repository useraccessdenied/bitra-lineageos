#!/usr/bin/env bash
# Resumable sync. Re-run after crash/power loss; git keeps partial fetches.
# Usage: 03-sync.sh [dir=a16] [jobs=3]   (low jobs suits a slow link)
set -uo pipefail; . "$(dirname "$0")/env.sh"
DIR=${1:-a16}; JOBS=${2:-3}; cd "$WS/roms/lineageos/$DIR"
n=0; until repo sync -n -c -j"$JOBS" --no-clone-bundle --no-tags --optimized-fetch --prune --retry-fetches=5 --force-sync; do
  n=$((n+1)); echo "[$(date)] network attempt $n failed, retry in 60s"; sleep 60; done
echo "[$(date)] network done; checking out"
until repo sync -l -j8 --force-sync; do echo "checkout retry"; sleep 10; done
echo "[$(date)] fetching git-lfs objects (repo checkout leaves LFS pointers otherwise)"
until repo forall -j8 -c "git lfs pull"; do echo "lfs retry"; sleep 30; done
echo "[$(date)] SYNC COMPLETE"; touch .sync-complete
