#!/usr/bin/env bash
set -euo pipefail

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
out_dir="${1:-runtime/probes/redmagic/${timestamp}}"
mkdir -p "${out_dir}"

run_probe() {
  local name="$1"
  shift
  {
    echo "$ $*"
    "$@" || true
  } > "${out_dir}/${name}.txt" 2>&1
}

run_probe adb_devices adb devices -l
run_probe product_model adb shell getprop ro.product.model
run_probe soc_model adb shell getprop ro.soc.model
run_probe hardware adb shell getprop ro.hardware
run_probe battery adb shell dumpsys battery
run_probe meminfo adb shell sh -c "cat /proc/meminfo | head"
run_probe disk adb shell df -h
run_probe thermal_override adb shell cmd thermalservice override-status 0
run_probe system_libs adb shell sh -c "ls /system/lib64 | grep -iE 'qnn|hexagon|qairt|adreno' || true"
run_probe packages adb shell sh -c "pm list packages | grep -iE 'qualcomm|snapdragon|redmagic|nubia' || true"

cat > "${out_dir}/README.md" <<EOF
# REDMAGIC Probe

Timestamp: ${timestamp}

Review every \`.txt\` file in this directory. Public specs are advisory only; these ADB probes are the authority.
EOF

echo "${out_dir}"
