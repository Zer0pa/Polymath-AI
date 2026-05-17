#!/usr/bin/env bash
set -euo pipefail

adb_bin="${ADB:-adb}"
serial="${SERIAL:-}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
out_dir="${OUT_DIR:-runtime/probes/redmagic_gpu/${timestamp}}"

usage() {
  cat <<'USAGE'
Usage:
  ADB=adb SERIAL=<device-serial> OUT_DIR=<output-dir> \
    bash gemma4_megakernel/android/adb/probe_gpu_shell.sh

This probe is read-only. It collects Vulkan/OpenCL capability signals from
ADB shell commands and filesystem listings. It does not set properties,
change thermal or GPU settings, start apps, push files, or remove files.

Environment:
  ADB      adb binary path. Defaults to "adb".
  SERIAL   target device serial. Required when more than one device is attached.
  OUT_DIR  host output directory. Defaults to runtime/probes/redmagic_gpu/<UTC>.
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

mkdir -p "${out_dir}"

adb_target=("${adb_bin}")
if [[ -n "${serial}" ]]; then
  adb_target+=("-s" "${serial}")
fi

run_host_probe() {
  local name="$1"
  shift
  {
    echo "$ $*"
    "$@" || true
  } > "${out_dir}/${name}.txt" 2>&1
}

run_shell_probe() {
  local name="$1"
  shift
  {
    printf '$'
    printf ' %q' "${adb_target[@]}" shell "$@"
    printf '\n'
    "${adb_target[@]}" shell "$@" || true
  } > "${out_dir}/${name}.txt" 2>&1
}

run_shell_blob() {
  local name="$1"
  local script="$2"
  {
    printf '$'
    printf ' %q' "${adb_target[@]}" shell "$script"
    printf '\n'
    "${adb_target[@]}" shell "$script" || true
  } > "${out_dir}/${name}.txt" 2>&1
}

run_host_probe adb_devices "${adb_bin}" devices -l
run_shell_blob device_identity 'getprop ro.product.manufacturer; getprop ro.product.model; getprop ro.product.device; getprop ro.soc.manufacturer; getprop ro.soc.model; getprop ro.board.platform; getprop ro.hardware; getprop ro.product.cpu.abi; getprop ro.build.version.release; getprop ro.build.version.sdk'
run_shell_blob graphics_properties 'getprop | grep -iE "vulkan|gpu|adreno|egl|gles|angle|graphics|qcom|soc|vendor.api|ro.hardware|ro.board.platform|ro.product.cpu.abi|ro.build.version" || true'
run_shell_probe package_features cmd package list features
run_shell_blob gpu_package_features 'cmd package list features | grep -iE "vulkan|opengl|gles|gpu|compute" || true'
run_shell_probe cmd_gpu_help cmd gpu help
run_shell_probe vulkan_vkjson cmd gpu vkjson
run_shell_probe vulkan_vkprofiles cmd gpu vkprofiles
run_shell_probe dumpsys_gpu dumpsys gpu
run_shell_blob surfaceflinger_graphics 'dumpsys SurfaceFlinger 2>/dev/null | grep -iE "GLES|Vulkan|RenderEngine|Gpu|Adreno|driver|pipeline|gralloc" || true'
run_shell_probe battery dumpsys battery
run_shell_blob thermal_readonly 'cmd thermalservice status 2>/dev/null || dumpsys thermalservice 2>/dev/null || true'

run_shell_blob gpu_libraries '
for d in /vendor/lib64 /vendor/lib /system/vendor/lib64 /system/vendor/lib /system/lib64 /odm/lib64 /product/lib64 /apex/com.android.vndk.v*/lib64; do
  echo "## ${d}"
  ls -la "${d}" 2>/dev/null | grep -Ei "(libOpenCL|OpenCL|libvulkan|vulkan|adreno|kgsl|gsl|llvm-glnext|libEGL|libGLES|libVkLayer)" || true
done
'

run_shell_blob gpu_sysfs_readonly '
for p in \
  /proc/gpuinfo \
  /proc/adreno_gpu \
  /sys/class/kgsl/kgsl-3d0/gpu_model \
  /sys/class/kgsl/kgsl-3d0/gpu_busy_percentage \
  /sys/class/kgsl/kgsl-3d0/gpubusy \
  /sys/class/kgsl/kgsl-3d0/devfreq/available_frequencies \
  /sys/class/kgsl/kgsl-3d0/devfreq/cur_freq \
  /sys/class/kgsl/kgsl-3d0/devfreq/max_freq \
  /sys/class/kgsl/kgsl-3d0/devfreq/min_freq \
  /sys/class/devfreq/*kgsl*/available_frequencies \
  /sys/class/devfreq/*kgsl*/cur_freq; do
  echo "## ${p}"
  cat "${p}" 2>/dev/null || true
done
'

run_shell_blob gpu_packages 'pm list packages | grep -iE "qualcomm|qti|adreno|gpu|vulkan|nubia|redmagic" || true'

{
  cat <<EOF
# REDMAGIC GPU Shell Capability Probe

Timestamp: ${timestamp}

This packet is read-only. It records shell-visible Vulkan/OpenCL capability
signals but does not prove a backend can execute the Gemma 4 layer gate.

Primary files:

- \`vulkan_vkjson.txt\`: Android GPU service Vulkan JSON. Best shell signal.
- \`vulkan_vkprofiles.txt\`: Vulkan profile JSON when supported.
- \`gpu_package_features.txt\`: Android feature declarations for Vulkan/OpenGL.
- \`gpu_libraries.txt\`: visible Vulkan/OpenCL/Adreno library names.
- \`dumpsys_gpu.txt\`: Android GPU driver package/service state when available.
- \`gpu_sysfs_readonly.txt\`: read-only KGSL/sysfs model/frequency signals when readable.

Do not treat OpenCL library visibility as execution proof. Confirm OpenCL with
the native probe runner and \`clGetPlatformIDs\` / \`clGetDeviceIDs\`.
EOF
} > "${out_dir}/README.md"

find "${out_dir}" -type f ! -name manifest.sha256 -exec shasum -a 256 {} \; | sort > "${out_dir}/manifest.sha256"

echo "${out_dir}"
