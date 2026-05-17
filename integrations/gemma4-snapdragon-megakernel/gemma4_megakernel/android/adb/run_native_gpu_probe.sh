#!/usr/bin/env bash
set -euo pipefail

adb_bin="${ADB:-adb}"
serial="${SERIAL:-}"
native_probe_bin="${NATIVE_PROBE_BIN:-${1:-}}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
out_dir="${OUT_DIR:-runtime/probes/redmagic_gpu_native/${timestamp}}"
remote_dir="${REMOTE_DIR:-/data/local/tmp/gemma4_gpu_probe}"
remote_bin="${remote_dir}/$(basename "${native_probe_bin:-gpu_capability_probe}")"

usage() {
  cat <<'USAGE'
Usage:
  ADB=adb SERIAL=<device-serial> NATIVE_PROBE_BIN=/abs/path/gpu_capability_probe \
    OUT_DIR=<output-dir> bash gemma4_megakernel/android/adb/run_native_gpu_probe.sh

This opt-in runner pushes one supplied arm64 Android native executable to
/data/local/tmp/gemma4_gpu_probe, marks it executable, runs it with --json, and
pulls the stdout/stderr transcript into OUT_DIR. It does not set properties,
change settings, root, remount, kill apps, or delete files.

The native executable should only query capabilities:
  Vulkan: vkEnumerateInstanceExtensionProperties, vkEnumerateInstanceLayerProperties,
          vkCreateInstance, vkEnumeratePhysicalDevices,
          vkGetPhysicalDeviceProperties2, vkGetPhysicalDeviceFeatures2,
          vkGetPhysicalDeviceQueueFamilyProperties,
          vkEnumerateDeviceExtensionProperties.
  OpenCL: dlopen libOpenCL.so read-only, clGetPlatformIDs, clGetPlatformInfo,
          clGetDeviceIDs, clGetDeviceInfo.
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ -z "${native_probe_bin}" ]]; then
  usage >&2
  exit 2
fi

if [[ ! -f "${native_probe_bin}" ]]; then
  echo "Native probe binary not found: ${native_probe_bin}" >&2
  exit 2
fi

mkdir -p "${out_dir}"

adb_target=("${adb_bin}")
if [[ -n "${serial}" ]]; then
  adb_target+=("-s" "${serial}")
fi

run_capture() {
  local name="$1"
  shift
  {
    echo "$ $*"
    "$@"
  } > "${out_dir}/${name}.txt" 2>&1
}

run_capture adb_devices "${adb_bin}" devices -l
run_capture mkdir_remote "${adb_target[@]}" shell mkdir -p "${remote_dir}"
run_capture push_native "${adb_target[@]}" push "${native_probe_bin}" "${remote_bin}"
run_capture chmod_native "${adb_target[@]}" shell chmod 755 "${remote_bin}"

{
  printf '$'
  printf ' %q' "${adb_target[@]}" shell "cd ${remote_dir} && ${remote_bin} --json"
  printf '\n'
  "${adb_target[@]}" shell "cd ${remote_dir} && ${remote_bin} --json"
} > "${out_dir}/native_gpu_probe.jsonl" 2> "${out_dir}/native_gpu_probe.stderr.txt" || {
  status=$?
  echo "${status}" > "${out_dir}/native_gpu_probe.exit_status"
  find "${out_dir}" -type f ! -name manifest.sha256 -exec shasum -a 256 {} \; | sort > "${out_dir}/manifest.sha256"
  exit "${status}"
}

echo "0" > "${out_dir}/native_gpu_probe.exit_status"

{
  cat <<EOF
# REDMAGIC Native GPU Capability Probe

Timestamp: ${timestamp}
Remote directory: ${remote_dir}
Remote binary: ${remote_bin}

This packet records an opt-in native capability probe. The runner intentionally
does not remove the remote binary so failure evidence remains inspectable.
Use a separate cleanup command only after the orchestrator approves it.
EOF
} > "${out_dir}/README.md"

find "${out_dir}" -type f ! -name manifest.sha256 -exec shasum -a 256 {} \; | sort > "${out_dir}/manifest.sha256"

echo "${out_dir}"
