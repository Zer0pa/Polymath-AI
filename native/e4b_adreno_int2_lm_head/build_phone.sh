#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
unset LD_PRELOAD LD_LIBRARY_PATH CPATH CPLUS_INCLUDE_PATH C_INCLUDE_PATH LIBRARY_PATH
unset OPENCL_VENDOR_PATH OCL_ICD_FILENAMES OCL_ICD_VENDORS PYTHONPATH BASH_ENV ENV

usage() {
  printf 'usage: %s OUTPUT_BINARY\n' "$0" >&2
  exit 64
}

[[ $# -eq 1 ]] || usage
[[ "$(uname -m)" == "aarch64" ]] || {
  printf 'refusing non-aarch64 authority build\n' >&2
  exit 65
}

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SOURCE_DIR="$ROOT/native/e4b_adreno_int2_lm_head"
OUTPUT="$1"
OUTPUT_DIR="$(dirname "$OUTPUT")"
[[ -d "$OUTPUT_DIR" && ! -L "$OUTPUT_DIR" ]] || {
  printf 'output directory must already exist and must not be a symlink\n' >&2
  exit 66
}
[[ ! -e "$OUTPUT" && ! -L "$OUTPUT" ]] || {
  printf 'refusing to replace output binary\n' >&2
  exit 67
}

CXX="/data/data/com.termux/files/usr/bin/clang++"
[[ -x "$CXX" ]] || {
  printf 'frozen Termux clang++ is unavailable\n' >&2
  exit 68
}
TEMP="$(mktemp "$OUTPUT_DIR/.e4b_adreno_int2.XXXXXX")"
cleanup() {
  rm -f "$TEMP"
}
trap cleanup EXIT

"$CXX" \
  -std=c++20 \
  -O3 \
  -DNDEBUG \
  -fvisibility=hidden \
  -Wall \
  -Wextra \
  -Wpedantic \
  -Wshadow \
  -Wconversion \
  -Wsign-conversion \
  "$SOURCE_DIR/opencl_dynamic_runtime.cpp" \
  "$SOURCE_DIR/e4b_adreno_int2_lm_head.cpp" \
  -ldl \
  -o "$TEMP"

chmod 0700 "$TEMP"
ln "$TEMP" "$OUTPUT"
rm -f "$TEMP"
trap - EXIT
printf '%s\n' "$OUTPUT"
