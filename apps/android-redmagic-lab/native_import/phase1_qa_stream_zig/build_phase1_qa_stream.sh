#!/data/data/com.termux/files/usr/bin/sh
set -eu

if [ "$#" -lt 1 ]; then
  echo "usage: $0 OUT_DIR" >&2
  exit 64
fi

OUT_DIR=$1
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
mkdir -p "$OUT_DIR"

OBJ="$OUT_DIR/phase1_qa_stream.o"
BIN="$OUT_DIR/phase1_qa_stream"
CACHE="$OUT_DIR/zig-cache"
GLOBAL_CACHE="$OUT_DIR/zig-global-cache"

zig build-obj "$SCRIPT_DIR/phase1_qa_stream.zig" \
  -target aarch64-linux-android \
  -OReleaseFast \
  -fPIC \
  -fno-lld \
  -femit-bin="$OBJ" \
  --cache-dir "$CACHE" \
  --global-cache-dir "$GLOBAL_CACHE"

clang -target aarch64-linux-android35 -pie "$OBJ" -o "$BIN"
termux-elf-cleaner "$BIN" >/dev/null 2>&1 || true
chmod +x "$BIN"
printf '%s\n' "$BIN"
