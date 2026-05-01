#!/usr/bin/env bash
# Phone probe — runs from the host Mac, talks to the attached REDMAGIC via ADB.
#
# Outputs a probe envelope under runtime/probes/phone/<timestamp>/ with:
#   - adb-devices.txt
#   - getprop.txt
#   - meminfo.txt
#   - df.txt
#   - thermal.txt
#   - battery.txt
#   - vulkan.txt   (if vkmark / vulkaninfo available on host)
#   - termux-version.txt (if Termux is installed)
#
# The Python parser in polymath_ai.device.probe.parse_* turns these into a
# DeviceState envelope. NOTHING in this script does QNN compile or runtime
# probes; those happen only after the SoC target is verified.
#
# Usage: scripts/host/phone_probe.sh [output_root]

set -euo pipefail

OUT_ROOT="${1:-runtime/probes/phone}"
TS="$(date -u +%Y-%m-%dT%H%M%SZ)"
OUT="${OUT_ROOT}/${TS}"
mkdir -p "${OUT}"

echo "[probe] output dir: ${OUT}"

# 1. adb available?
if ! command -v adb >/dev/null 2>&1; then
    echo "[probe] adb not found on PATH"
    echo "adb_missing" > "${OUT}/blocker.txt"
    exit 2
fi

# 2. devices
adb devices -l 2>&1 | tee "${OUT}/adb-devices.txt"

# Pick first authorised device.
DEV="$(adb devices | awk '$2=="device"{print $1; exit}')"
if [[ -z "${DEV:-}" ]]; then
    echo "[probe] no authorised device. Authorise USB debugging on the phone, then retry."
    echo "no_authorized_device" > "${OUT}/blocker.txt"
    exit 3
fi
echo "[probe] device serial: ${DEV}"
echo "${DEV}" > "${OUT}/serial.txt"

run() {
    local label="$1"; shift
    adb -s "${DEV}" shell "$@" > "${OUT}/${label}.txt" 2>&1 || echo "[probe] ${label} failed (continuing)"
}

run getprop          getprop
run meminfo          cat /proc/meminfo
run cpuinfo          cat /proc/cpuinfo
run df               df -h
run thermal          cat /sys/class/thermal/thermal_zone*/type /sys/class/thermal/thermal_zone*/temp
run battery          dumpsys battery
run android-build    cat /system/build.prop
run kernel           uname -a
run gpu-clock        'cat /sys/class/devfreq/*kgsl*/cur_freq /sys/class/devfreq/*kgsl*/max_freq /sys/class/devfreq/*kgsl*/min_freq 2>/dev/null'
run charging         dumpsys battery
run gpuprofiler      pm list packages 2>&1 | grep -iE "(snapdragon|gpu|qualcomm|profiler)"
run termux-shell     'pm list packages 2>&1 | grep com.termux'

# Termux Python version (if installed)
if adb -s "${DEV}" shell "pm list packages com.termux" 2>&1 | grep -q com.termux; then
    echo "[probe] Termux detected"
    adb -s "${DEV}" shell "run-as com.termux /data/data/com.termux/files/usr/bin/python3 --version" \
        > "${OUT}/termux-python.txt" 2>&1 || echo "[probe] could not run termux python (run-as may be blocked)"
fi

# Vulkan info (host-side: if vkmark / vulkaninfo is around).
if command -v vulkaninfo >/dev/null 2>&1; then
    vulkaninfo --summary > "${OUT}/host-vulkan-summary.txt" 2>&1 || true
fi

# Append a JSON summary the python parser can ingest.
python3 - "${OUT}" <<'PY'
import json, os, sys
out = sys.argv[1]
def read(name):
    p = os.path.join(out, name + ".txt")
    return open(p, encoding="utf-8", errors="replace").read() if os.path.exists(p) else ""
summary = {
    "schema_version": "1.0.0",
    "probe_dir": out,
    "files": sorted(os.listdir(out)),
    "adb_devices_text": read("adb-devices"),
    "getprop_text_sample": read("getprop")[:8000],
    "meminfo_text": read("meminfo"),
    "battery_text_sample": read("battery")[:4000],
    "termux_present": os.path.exists(os.path.join(out, "termux-python.txt")),
}
with open(os.path.join(out, "summary.json"), "w") as f:
    json.dump(summary, f, indent=2, sort_keys=True)
print("[probe] summary written to", os.path.join(out, "summary.json"))
PY

echo "[probe] done. Run polymath_ai/device/parse_probe.py against ${OUT} to produce a DeviceState envelope."
