#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)"
SOURCE="$ROOT/native/e4b_l2_projection_verifier.c"
OUTPUT="${1:?usage: build_e4b_l2_projection_verifier.sh OUTPUT}"
ZIG="${ZIG:-zig}"

test -f "$SOURCE"
test ! -e "$OUTPUT"
mkdir -p "$(dirname -- "$OUTPUT")"

"$ZIG" cc \
  -target aarch64-linux-musl \
  -static \
  -O2 \
  -std=c17 \
  -Wall \
  -Wextra \
  -Werror \
  "$SOURCE" \
  -lm \
  -o "$OUTPUT"

chmod 0750 "$OUTPUT"
file "$OUTPUT"
sha256sum "$OUTPUT"
