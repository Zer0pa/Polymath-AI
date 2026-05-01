#!/usr/bin/env bash
# Polymath autonomous on-device runner.
#
# Operating mode (PRD §Energy Regime + Decision D-005):
#   - The phone runs unplugged-to-host but plugged-to-power.
#   - The runner reads a config from ~/polymath/config.yaml, does work, writes
#     telemetry + checkpoints, and pushes them to GitHub + HF on a cadence.
#   - Watchdog: if the python process dies, the loop sleeps and restarts.
#   - Resume: every restart picks up the latest audit-chain tail.
#
# Args:
#   --phase     phase string (e.g. phase0e_experiment0)
#   --config    path to a YAML config (overrides ~/polymath/config.yaml)
#   --dry-run   parse the config, log it, then exit (used for first-attach test)

set -uo pipefail

PHASE=""
CONFIG="${HOME}/polymath/config.yaml"
DRY_RUN=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --phase) PHASE="$2"; shift 2;;
        --config) CONFIG="$2"; shift 2;;
        --dry-run) DRY_RUN=1; shift;;
        *) echo "unknown arg $1"; exit 2;;
    esac
done

if [[ -z "${PHASE}" ]]; then
    echo "usage: $0 --phase <phase> [--config <yaml>] [--dry-run]"
    exit 2
fi

VENV="${HOME}/polymath/venv"
if [[ ! -d "${VENV}" ]]; then
    echo "venv missing - run scripts/termux/bootstrap.sh first"
    exit 3
fi
# shellcheck disable=SC1091
source "${VENV}/bin/activate"

RUN_ID="run:$(date -u +%Y%m%dT%H%M%SZ):${PHASE}"
RUN_DIR="${HOME}/polymath/runs/${RUN_ID//[:]/_}"
mkdir -p "${RUN_DIR}"

echo "[runner] phase=${PHASE} run_id=${RUN_ID}"
echo "[runner] run_dir=${RUN_DIR}"
echo "[runner] config=${CONFIG}"

if [[ "${DRY_RUN}" == "1" ]]; then
    echo "[runner] dry-run: exiting after config print"
    cat "${CONFIG}" 2>/dev/null || echo "(no config file - using defaults)"
    exit 0
fi

# Watchdog loop: keep restarting on transient failures up to 10 retries.
RETRIES=0
MAX_RETRIES=10

while true; do
    echo "[runner] starting attempt $((RETRIES + 1)) at $(date -u +%H:%M:%SZ)"
    python -u -m polymath_ai.experiments.runner \
        --phase "${PHASE}" \
        --config "${CONFIG}" \
        --run-id "${RUN_ID}" \
        --run-dir "${RUN_DIR}" \
        2>&1 | tee -a "${RUN_DIR}/runner.log"
    rc=$?
    if [[ ${rc} -eq 0 ]]; then
        echo "[runner] python exited cleanly"
        break
    fi
    RETRIES=$((RETRIES + 1))
    if [[ ${RETRIES} -ge ${MAX_RETRIES} ]]; then
        echo "[runner] exceeded max retries (${MAX_RETRIES}); leaving the run for inspection"
        exit 4
    fi
    echo "[runner] python exited rc=${rc}; sleeping 60s before retry"
    sleep 60
done

echo "[runner] complete at $(date -u +%H:%M:%SZ)"
