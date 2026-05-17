#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="${1:-runtime/gemma4_megakernel/phone_probe_$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "${OUT_DIR}"

adb devices -l | tee "${OUT_DIR}/adb_devices.txt"
adb shell getprop ro.product.model | tee "${OUT_DIR}/ro.product.model.txt"
adb shell getprop ro.soc.model | tee "${OUT_DIR}/ro.soc.model.txt"
adb shell getprop ro.hardware | tee "${OUT_DIR}/ro.hardware.txt"
adb shell getprop ro.build.version.release | tee "${OUT_DIR}/ro.build.version.release.txt"
adb shell getprop ro.product.cpu.abi | tee "${OUT_DIR}/ro.product.cpu.abi.txt"
adb shell dumpsys battery > "${OUT_DIR}/dumpsys_battery.txt"
adb shell cat /proc/meminfo > "${OUT_DIR}/meminfo.txt"
adb shell df -h > "${OUT_DIR}/df_h.txt"
adb shell 'ls /system/lib64/libvulkan.so /vendor/lib64/libvulkan.so 2>/dev/null || true' > "${OUT_DIR}/vulkan_libs.txt"
adb shell 'ls /system/lib64/libOpenCL.so /vendor/lib64/libOpenCL.so 2>/dev/null || true' > "${OUT_DIR}/opencl_libs.txt"
adb shell 'pm list packages | grep -iE "qualcomm|snapdragon|nubia|gpu" || true' > "${OUT_DIR}/gpu_packages.txt"

printf '{"schema_version":"gemma4_phone_probe_v1","out_dir":"%s"}\n' "${OUT_DIR}" > "${OUT_DIR}/probe_summary.json"
