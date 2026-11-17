#!/usr/bin/env bash
# repo init (idempotent). Usage: 02-repo-init.sh [branch=lineage-23.2] [dir=a16]
set -euo pipefail; . "$(dirname "$0")/env.sh"
BR=${1:-lineage-23.2}; DIR=${2:-a16}
mkdir -p "$WS/roms/lineageos/$DIR"; cd "$WS/roms/lineageos/$DIR"
until repo init -u https://github.com/LineageOS/android.git -b "$BR" --git-lfs --depth=1 --no-clone-bundle; do echo retry; sleep 20; done
mkdir -p .repo/local_manifests; cp "$WS/scripts/manifests/bitra-$BR.xml" .repo/local_manifests/bitra.xml
