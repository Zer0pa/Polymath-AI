#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 3 ]]; then
  cat >&2 <<'USAGE'
Usage: run_layer_gate.sh BUILD_BINARY [REMOTE_DIR] [REMOTE_LAYER_PACK]

Pushes gemma4_layer_runner to an attached Android device, runs --help, then
runs --probe. REMOTE_LAYER_PACK is an already-present device path; this script
does not push model weights or layer packs.
USAGE
  exit 2
fi

build_binary="$1"
remote_dir="${2:-/data/local/tmp/gemma4_megakernel}"
remote_layer_pack="${3:-}"
remote_binary="${remote_dir}/gemma4_layer_runner"

adb shell "mkdir -p '${remote_dir}'"
adb push "${build_binary}" "${remote_binary}"
adb shell "chmod 755 '${remote_binary}'"
adb shell "${remote_binary}" --help
adb shell "${remote_binary}" --probe

if [[ -n "${remote_layer_pack}" ]]; then
  adb shell "${remote_binary}" --validate-pack "${remote_layer_pack}"
fi
