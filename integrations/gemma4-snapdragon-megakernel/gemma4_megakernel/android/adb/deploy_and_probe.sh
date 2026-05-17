#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /path/to/gemma4_layer_runner" >&2
  exit 2
fi

RUNNER="$1"
REMOTE_DIR="/data/local/tmp/polymath_gemma4_gate"
OUT_DIR="runtime/gemma4_megakernel/runner_probe_$(date -u +%Y%m%dT%H%M%SZ)"

if [[ ! -f "${RUNNER}" ]]; then
  echo "runner not found: ${RUNNER}" >&2
  exit 2
fi

mkdir -p "${OUT_DIR}"
adb shell "mkdir -p ${REMOTE_DIR}"
adb push "${RUNNER}" "${REMOTE_DIR}/gemma4_layer_runner" | tee "${OUT_DIR}/adb_push.txt"
adb shell "chmod 755 ${REMOTE_DIR}/gemma4_layer_runner"
adb shell "${REMOTE_DIR}/gemma4_layer_runner --help" | tee "${OUT_DIR}/runner_help.txt"
adb shell "${REMOTE_DIR}/gemma4_layer_runner --probe" | tee "${OUT_DIR}/runner_probe.json"
