#!/usr/bin/env bash
# Long-horizon autonomous runner for the unplug-and-fridge / Game-Space mode.
#
# Run on the phone (inside Termux). Survives:
#   - screen turning off          -> termux-wake-lock
#   - SSH session ending          -> tmux detached session
#   - host disconnect             -> independent of host (HF + GitHub via gh)
#   - process crash               -> watchdog restart loop
#   - phone reboot                -> Termux:Boot starts this on boot (separate setup)
#
# Resume semantics:
#   - AuditWriter recovers from the latest event_hash on construction
#   - ELO checkpoints are saved every N steps; resume picks the latest
#   - Pending-upload manifests survive disk persistence; flusher retries
#
# Usage:
#   bash ~/polymath/long_horizon_runner.sh --phase phase0e_experiment0 --config E0.1.yaml
#
# To monitor remotely from host (when WiFi works):
#   adb -s <serial> shell tmux -L polymath attach
#   ssh u0_aXXX@<phone-ip> -p 8022 'tmux -L polymath attach'

set -uo pipefail

PHASE=""
CONFIG=""
ARGS=("$@")

while [[ $# -gt 0 ]]; do
    case "$1" in
        --phase) PHASE="$2"; shift 2;;
        --config) CONFIG="$2"; shift 2;;
        *) shift;;
    esac
done

if [[ -z "${PHASE}" ]]; then
    echo "usage: $0 --phase <phase> [--config <yaml>]"
    exit 2
fi

# Ensure required Termux tooling is present.
for c in termux-wake-lock termux-wake-unlock tmux nohup ; do
    if ! command -v "$c" >/dev/null 2>&1; then
        echo "[long-horizon] missing: $c"
        echo "  pkg install termux-api tmux  (one-time)"
        echo "  also install the Termux:API app from F-Droid"
        exit 3
    fi
done

VENV="${HOME}/polymath/venv"
if [[ ! -d "${VENV}" ]]; then
    echo "[long-horizon] no venv at ${VENV} - run scripts/termux/bootstrap.sh first"
    exit 4
fi

SESSION_NAME="polymath-${PHASE}"
LOG_DIR="${HOME}/polymath/logs/${SESSION_NAME}"
mkdir -p "${LOG_DIR}"
LOG="${LOG_DIR}/runner-$(date -u +%Y%m%dT%H%M%SZ).log"

# 1. Acquire wakelock so the runner survives screen-off.
#    termux-wake-lock requires Termux:API. The lock is process-scoped to
#    the controlling session, so we acquire AFTER tmux starts.

# 2. Build the inner command that tmux will run.
INNER=$(cat <<EOF
set -euo pipefail
echo "[long-horizon \$(date -u +%H:%M:%SZ)] acquiring wakelock"
termux-wake-lock || echo "[long-horizon] termux-wake-lock failed; install Termux:API"
trap 'echo "[long-horizon] releasing wakelock"; termux-wake-unlock || true' EXIT

source "${VENV}/bin/activate"

# Watchdog loop with bounded retries.
RETRIES=0
MAX_RETRIES=20
while true; do
    echo "[long-horizon \$(date -u +%H:%M:%SZ)] attempt \$((RETRIES + 1)) / \${MAX_RETRIES}"
    python -u -m polymath_ai.experiments.runner --phase "${PHASE}" ${CONFIG:+--config "${CONFIG}"}
    rc=\$?
    if [[ \${rc} -eq 0 ]]; then
        echo "[long-horizon] python exited cleanly"
        break
    fi
    RETRIES=\$((RETRIES + 1))
    if [[ \${RETRIES} -ge \${MAX_RETRIES} ]]; then
        echo "[long-horizon] hit MAX_RETRIES; leaving the run for inspection"
        exit 5
    fi
    # Backoff: 60s, 90s, 180s, ... capped at 600s.
    sleep_s=\$((60 + 30 * RETRIES))
    if [[ \${sleep_s} -gt 600 ]]; then sleep_s=600; fi
    echo "[long-horizon] python exited rc=\${rc}; sleeping \${sleep_s}s before retry"
    sleep \${sleep_s}
done

echo "[long-horizon] complete at \$(date -u +%H:%M:%SZ)"
EOF
)

# 3. Spawn tmux detached session that runs the inner command.
#    -L polymath: dedicated socket so Game Space / fridge mode keeps it
#    even if the user opens a regular Termux session.
if tmux -L polymath has-session -t "${SESSION_NAME}" 2>/dev/null ; then
    echo "[long-horizon] tmux session ${SESSION_NAME} already exists. attach with:"
    echo "    tmux -L polymath attach -t ${SESSION_NAME}"
    exit 0
fi

tmux -L polymath new-session -d -s "${SESSION_NAME}" \
    "bash -c '${INNER}' 2>&1 | tee -a '${LOG}'"

echo "[long-horizon] session ${SESSION_NAME} started"
echo "[long-horizon] log: ${LOG}"
echo "[long-horizon] attach with: tmux -L polymath attach -t ${SESSION_NAME}"
echo "[long-horizon] detach from inside tmux with: Ctrl-b d"
echo "[long-horizon] kill from outside with: tmux -L polymath kill-session -t ${SESSION_NAME}"
