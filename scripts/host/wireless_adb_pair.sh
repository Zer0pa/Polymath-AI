#!/usr/bin/env bash
# Wireless ADB pairing helper.
#
# Use when USB-cable ADB is unavailable (charge-only cable, no USB port,
# or when the phone is sealed in fridge mode and we want OTA monitoring).
#
# Operator steps on the phone (one-time per host):
#   1. Settings -> System -> Developer options -> Wireless debugging -> ON.
#   2. Tap "Pair device with pairing code".
#   3. Note the IP:PORT (top of dialog) and the 6-digit code.
#   4. Run this script with those values.
#
# After pairing, persistent connect uses the *connect* IP:PORT (different
# from pair port - shown on the main Wireless debugging screen).

set -uo pipefail

PAIR_ENDPOINT=""
PAIR_CODE=""
CONNECT_ENDPOINT=""

usage() {
    cat <<EOF
usage: $0 --pair <ip:port> --code <6-digit> [--connect <ip:port>]

If --connect is omitted, $0 only pairs. To establish the persistent
connection, run again with just --connect <ip:port>.

example:
    $0 --pair 192.168.1.42:35341 --code 123456
    # later:
    $0 --connect 192.168.1.42:5555
EOF
    exit 2
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --pair) PAIR_ENDPOINT="$2"; shift 2;;
        --code) PAIR_CODE="$2"; shift 2;;
        --connect) CONNECT_ENDPOINT="$2"; shift 2;;
        *) usage;;
    esac
done

if [[ -z "${PAIR_ENDPOINT}${CONNECT_ENDPOINT}" ]]; then
    usage
fi

if [[ -n "${PAIR_ENDPOINT}" ]]; then
    if [[ -z "${PAIR_CODE}" ]]; then
        echo "[wireless-adb] --pair requires --code"
        exit 3
    fi
    echo "[wireless-adb] pairing with ${PAIR_ENDPOINT}"
    echo "${PAIR_CODE}" | adb pair "${PAIR_ENDPOINT}"
fi

if [[ -n "${CONNECT_ENDPOINT}" ]]; then
    echo "[wireless-adb] connecting to ${CONNECT_ENDPOINT}"
    adb connect "${CONNECT_ENDPOINT}"
fi

echo ""
echo "[wireless-adb] devices:"
adb devices -l
