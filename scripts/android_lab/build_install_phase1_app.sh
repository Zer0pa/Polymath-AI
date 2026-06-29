#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-build}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
APP_DIR="${REPO_DIR}/apps/android-redmagic-lab"
APK_PATH="${APP_DIR}/app/build/outputs/apk/debug/app-debug.apk"
PACKAGE_NAME="ai.zer0pa.polymath.lab"

usage() {
  printf 'Usage: %s [build|install|build-install]\n' "$0" >&2
}

gradle_cmd() {
  if [[ -n "${GRADLE_BIN:-}" && -x "${GRADLE_BIN}" ]]; then
    printf '%s\n' "${GRADLE_BIN}"
    return 0
  fi
  if [[ -x "${APP_DIR}/gradlew" ]]; then
    printf '%s\n' "${APP_DIR}/gradlew"
    return 0
  fi
  if command -v gradle >/dev/null 2>&1; then
    command -v gradle
    return 0
  fi
  printf 'Gradle is not available and no app-local wrapper is checked in.\n' >&2
  printf 'Install a Gradle version compatible with Android Gradle Plugin 9.2.0, or add an approved wrapper.\n' >&2
  return 2
}

select_adb_serial() {
  if ! command -v adb >/dev/null 2>&1; then
    printf 'adb is not available. Install Android platform-tools and rerun with a connected REDMAGIC.\n' >&2
    return 2
  fi

  if [[ -n "${SERIAL:-}" ]]; then
    adb -s "${SERIAL}" get-state >/dev/null
    printf '%s\n' "${SERIAL}"
    return 0
  fi

  mapfile -t devices < <(adb devices | awk '$2 == "device" {print $1}')
  if [[ "${#devices[@]}" -ne 1 ]]; then
    printf 'Expected exactly one adb device or SERIAL=<serial>; found %s.\n' "${#devices[@]}" >&2
    adb devices -l >&2 || true
    return 2
  fi
  printf '%s\n' "${devices[0]}"
}

build_app() {
  local gradle_bin
  gradle_bin="$(gradle_cmd)"
  (cd "${APP_DIR}" && "${gradle_bin}" :app:assembleDebug)
  if [[ ! -f "${APK_PATH}" ]]; then
    printf 'Expected APK was not produced: %s\n' "${APK_PATH}" >&2
    return 3
  fi
  printf 'Built %s\n' "${APK_PATH}"
}

install_app() {
  local serial
  serial="$(select_adb_serial)"
  if [[ ! -f "${APK_PATH}" ]]; then
    printf 'APK not found: %s\n' "${APK_PATH}" >&2
    printf 'Run `%s build` first.\n' "$0" >&2
    return 3
  fi
  adb -s "${serial}" install -r "${APK_PATH}"
  adb -s "${serial}" shell cmd package resolve-activity --brief "${PACKAGE_NAME}" || true
  printf 'Installed %s on %s\n' "${PACKAGE_NAME}" "${serial}"
}

case "${ACTION}" in
  build)
    build_app
    ;;
  install)
    install_app
    ;;
  build-install)
    build_app
    install_app
    ;;
  *)
    usage
    exit 2
    ;;
esac
