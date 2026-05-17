#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 3 ]]; then
  cat >&2 <<'USAGE'
Usage: run_opencl_gate.sh BUILD_BINARY [REMOTE_LAYER_PACK] [HOST_OUTPUT_DIR]

Runs the real Gemma 4 E4B layer 0 OpenCL phone path against an already-present
layer pack and pulls only the output tensor plus telemetry back to the Mac.
This script does not push model weights.
USAGE
  exit 2
fi

adb_bin="${ADB:-adb}"
serial="${SERIAL:-}"
build_binary="$1"
remote_layer_pack="${2:-/data/local/tmp/polymath_gemma4_gate/layer_pack/gemma4_e4b_layer0_seq128_v0}"
host_output_dir="${3:-runtime/gemma4_megakernel/opencl_$(date -u +%Y%m%dT%H%M%SZ)}"
remote_dir="/data/local/tmp/polymath_gemma4_gate"
remote_binary="${remote_dir}/gemma4_layer_runner"
remote_output_dir="${remote_dir}/outputs_opencl"

if [[ ! -f "${build_binary}" ]]; then
  echo "runner not found: ${build_binary}" >&2
  exit 2
fi

adb_target=("${adb_bin}")
if [[ -n "${serial}" ]]; then
  adb_target+=("-s" "${serial}")
fi

mkdir -p "${host_output_dir}"
"${adb_target[@]}" shell "mkdir -p '${remote_dir}' '${remote_output_dir}' && rm -rf '${remote_output_dir}'/*"
"${adb_target[@]}" push "${build_binary}" "${remote_binary}"
"${adb_target[@]}" shell "chmod 755 '${remote_binary}'"
"${adb_target[@]}" shell "'${remote_binary}' --validate-pack '${remote_layer_pack}'" \
  > "${host_output_dir}/phone_validate_pack.json"
"${adb_target[@]}" shell "cd '${remote_dir}' && '${remote_binary}' --run-opencl '${remote_layer_pack}' '${remote_output_dir}'"
"${adb_target[@]}" pull "${remote_output_dir}/layer_output.f32.bin" "${host_output_dir}/layer_output.f32.bin"
"${adb_target[@]}" pull "${remote_output_dir}/telemetry.json" "${host_output_dir}/telemetry.json"

printf '%s\n' "${host_output_dir}"
