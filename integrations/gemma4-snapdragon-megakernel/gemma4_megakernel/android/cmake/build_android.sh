#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LANE_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REPO_DIR="$(cd "${LANE_DIR}/.." && pwd)"
BUILD_DIR="${REPO_DIR}/build/gemma4_megakernel_android"

if [[ -z "${ANDROID_NDK_HOME:-}" ]]; then
  echo "ANDROID_NDK_HOME must point to an Android NDK directory" >&2
  exit 2
fi

TOOLCHAIN="${ANDROID_NDK_HOME}/build/cmake/android.toolchain.cmake"
if [[ ! -f "${TOOLCHAIN}" ]]; then
  echo "Android toolchain file not found: ${TOOLCHAIN}" >&2
  exit 2
fi

cmake -S "${LANE_DIR}" -B "${BUILD_DIR}" \
  -DCMAKE_TOOLCHAIN_FILE="${TOOLCHAIN}" \
  -DANDROID_ABI=arm64-v8a \
  -DANDROID_PLATFORM=android-29 \
  -DCMAKE_BUILD_TYPE=Release

cmake --build "${BUILD_DIR}" --target gemma4_layer_runner -- -j"$(getconf _NPROCESSORS_ONLN 2>/dev/null || sysctl -n hw.ncpu)"
