#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT_DIR="$ROOT/native/polar_phase34_consumer_preflight/bin"
SRC="$ROOT/native/polar_phase34_consumer_preflight/phase34_native_pjp1_consumer_preflight.cpp"
OUT="$OUT_DIR/phase34_native_pjp1_consumer_preflight"

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
)

if [[ "$(uname -m)" == "aarch64" || "$(uname -m)" == "arm64" ]]; then
  CXXFLAGS+=(-march=armv8.2-a+fp16+simd)
fi

"$CXX" "${CXXFLAGS[@]}" "$SRC" -o "$OUT"

printf '%s\n' "$OUT"
