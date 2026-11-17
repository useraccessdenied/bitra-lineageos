# source from other scripts. Host-native build (no containers).
export WS=/var/home/kapil/projects/bitra
export PATH="$WS/bin:$PATH"
export HOME_REAL="$HOME"
export CCACHE_DIR="$WS/ccache" USE_CCACHE=1 CCACHE_EXEC="$(command -v ccache || echo /usr/bin/ccache)"
export TMPDIR="$WS/.tmp"; mkdir -p "$TMPDIR"
export LC_ALL=C.UTF-8
