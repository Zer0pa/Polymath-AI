#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="$ROOT/native/polar_phase2_packetizer/bin"
SRC="$ROOT/native/polar_phase2_packetizer/phase2b_native_packetizer.cpp"
OUT="$OUT_DIR/phase2b_native_packetizer"

mkdir -p "$OUT_DIR"

CXX="${CXX:-clang++}"
CXXFLAGS=(
  -std=c++20
  -O3
  -DNDEBUG
  -fno-rtti
  -Wall
  -Wextra
  -Wshadow
  -Wconversion
  -Wno-deprecated-declarations
  -pthread
)

if [[ "$(uname -m)" == "aarch64" || "$(uname -m)" == "arm64" ]]; then
  CXXFLAGS+=(-march=armv8.2-a+fp16+simd)
fi

"$CXX" "${CXXFLAGS[@]}" "$SRC" -o "$OUT" $(pkg-config --libs openssl zlib 2>/dev/null || printf '%s\n' '-lcrypto -lz')

printf '%s\n' "$OUT"
