#!/usr/bin/env bash
# Run ONCE on the immutable host, then reboot. Layers only packages that are missing
# (rpm-ostree errors on packages already in the base image). android-tools is separate.
set -euo pipefail
PKGS=(
  autoconf213 bison bzip2 ccache clang curl flex gawk gcc gcc-c++ glibc-devel glibc-static
  libstdc++-static libX11-devel make mesa-libGL-devel ncurses-devel ncurses-compat-libs
  libxcrypt-compat openssl openssl-devel patch zlib-devel perl-Digest-SHA lz4 lzop gperf xxd
  aria2 erofs-utils git-lfs squashfs-tools xmlstarlet ImageMagick elfutils-libelf-devel
)
missing=()
for p in "${PKGS[@]}"; do rpm -q --whatprovides "$p" >/dev/null 2>&1 || missing+=("$p"); done
if [ ${#missing[@]} -eq 0 ]; then echo "All deps already present."; exit 0; fi
echo "Layering: ${missing[*]}"
sudo rpm-ostree install --idempotent --allow-inactive "${missing[@]}"
echo "Now reboot to apply."
