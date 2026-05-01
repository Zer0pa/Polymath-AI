#!/usr/bin/env bash
# Termux LEAN bootstrap - control-plane-only, no Rust source-builds.
#
# Why this exists (Decision D-018 - documented in docs/DECISIONS.md):
# The full bootstrap (scripts/termux/bootstrap.sh) tried to install
# `tokenizers` which requires a Rust source-build on Termux because no
# pre-built aarch64-android wheel is published on PyPI. The build takes
# 15+ min and routinely fails on Termux's Python 3.13 + cargo combo.
#
# This LEAN bootstrap installs ONLY pure-Python or pre-built-aarch64
# wheels:
#   * huggingface_hub  (pure Python; HF artifact pull/push from phone)
#   * safetensors      (pre-built aarch64 wheel via maturin)
#   * numpy<2          (pre-built aarch64 wheel)
#   * sentencepiece    (pre-built aarch64 wheel)
#   * pyyaml requests  (pure Python)
#
# That's enough for the phone to act as Polymath control plane:
#   * pull Polymath checkpoints + corpus shards from HF
#   * push run telemetry / new checkpoints to HF
#   * receive instructions via host-mediated SSH
#   * coexist with dm3_runner and other on-device work
#
# For actual phone-side LLM compute, use the LiteRT path
# (ai-edge-litert is a pure-binary wheel, no Rust source-build) - see
# scripts/termux/run_export_probe_termux.sh + scripts/host/qwen_litert_aot.sh
# (TODO).
#
# Idempotent. Safe to re-run.

set -uo pipefail

LOG="${HOME}/polymath/lean-bootstrap-$(date -u +%Y%m%dT%H%M%SZ).log"
mkdir -p "$(dirname "${LOG}")"

step() { echo "[lean $(date -u +%H:%M:%SZ)] $*" | tee -a "${LOG}"; }
ok()   { echo "[lean OK]   $*" | tee -a "${LOG}"; }
warn() { echo "[lean WARN] $*" | tee -a "${LOG}"; }
fail() { echo "[lean FAIL] $*" | tee -a "${LOG}"; exit 2; }

step "starting Polymath lean Termux bootstrap. log: ${LOG}"

if ! command -v pkg >/dev/null 2>&1; then
    fail "not Termux - pkg command missing"
fi

# 1. Update Termux package index (no-op if just updated).
step "pkg update"
pkg update -y >>"${LOG}" 2>&1 || warn "pkg update non-zero (continuing)"

# 2. Core OS packages only - no rust, no clang for source-builds we don't need.
PKG_CORE="python git openssh rsync wget curl jq tmux nano termux-api"
step "installing core packages (lean): ${PKG_CORE}"
pkg install -y ${PKG_CORE} >>"${LOG}" 2>&1 || fail "core package install failed"

# 3. Set up venv.
VENV="${HOME}/polymath/venv"
mkdir -p "$(dirname "${VENV}")"
if [[ ! -d "${VENV}" ]]; then
    step "creating venv at ${VENV}"
    python -m venv "${VENV}"
fi
# shellcheck disable=SC1091
source "${VENV}/bin/activate"
step "venv python: $(python --version)"

# 4. Pip-install the LEAN control-plane deps (no tokenizers / no transformers).
step "upgrading pip + wheel"
pip install --upgrade pip wheel setuptools >>"${LOG}" 2>&1 || warn "pip upgrade partial"

LEAN_PY=(
    "huggingface_hub"
    "safetensors>=0.4.5"
    "numpy<2"
    "sentencepiece>=0.2.0"
    "pyyaml>=6.0"
    "requests>=2.31"
)
step "installing LEAN python deps: ${LEAN_PY[*]}"
pip install --no-cache-dir --only-binary=:all: "${LEAN_PY[@]}" >>"${LOG}" 2>&1 \
    && ok "lean python deps installed" \
    || fail "lean python deps install failed - check log"

# 5. Allow external apps for Termux:RunCommandService (so the host agent
# can drive Termux via 'am startservice ...' from outside).
TERMUX_PROPS="${HOME}/.termux/termux.properties"
if [[ ! -f "${TERMUX_PROPS}" ]] || ! grep -q "^allow-external-apps=true" "${TERMUX_PROPS}" ; then
    mkdir -p "$(dirname "${TERMUX_PROPS}")"
    if [[ -f "${TERMUX_PROPS}" ]]; then
        sed -i.bak '/^allow-external-apps=/d' "${TERMUX_PROPS}"
    fi
    echo "allow-external-apps=true" >> "${TERMUX_PROPS}"
    ok "allow-external-apps=true written to ${TERMUX_PROPS}"
fi
# Reload Termux properties so the change takes effect this session.
if command -v termux-reload-settings >/dev/null 2>&1; then
    termux-reload-settings 2>>"${LOG}" || warn "termux-reload-settings failed"
fi

# 6. Optional: try installing ai-edge-litert (pre-built binary wheel).
step "attempting ai-edge-litert (LiteRT) install"
pip install --no-cache-dir "ai-edge-litert" 2>>"${LOG}" \
    && ok "ai-edge-litert installed (LiteRT runtime available)" \
    || warn "ai-edge-litert NOT installed - LiteRT path not on this Termux"

# 7. Record verdict.
VERDICT="${HOME}/polymath/termux-verdict.json"
mkdir -p "$(dirname "${VERDICT}")"
cat > "${VERDICT}" <<EOF
{
  "schema_version": "1.0.0",
  "bootstrap_kind": "lean",
  "bootstrap_completed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "termux_python_version": "$(python --version 2>&1 | awk '{print $2}')",
  "huggingface_hub_present": "$(python -c 'import huggingface_hub; print(huggingface_hub.__version__)' 2>/dev/null || echo absent)",
  "safetensors_present": "$(python -c 'import safetensors; print(safetensors.__version__)' 2>/dev/null || echo absent)",
  "numpy_present": "$(python -c 'import numpy; print(numpy.__version__)' 2>/dev/null || echo absent)",
  "sentencepiece_present": "$(python -c 'import sentencepiece; print(sentencepiece.__version__)' 2>/dev/null || echo absent)",
  "ai_edge_litert_present": "$(python -c 'import ai_edge_litert; print(ai_edge_litert.__version__)' 2>/dev/null || echo absent)",
  "torch_install_result": "skipped_in_lean_bootstrap",
  "transformers_present": "skipped_in_lean_bootstrap",
  "tokenizers_present": "skipped_in_lean_bootstrap",
  "termux_api_present": "$(command -v termux-wake-lock >/dev/null && echo true || echo false)",
  "tmux_present": "$(command -v tmux >/dev/null && echo true || echo false)",
  "log_path": "${LOG}"
}
EOF

# Also copy the verdict to /sdcard so the host can read it without
# Termux:RunCommand.
cp "${VERDICT}" /sdcard/Download/polymath/termux-verdict.json 2>/dev/null \
    && ok "verdict copied to /sdcard/Download/polymath/termux-verdict.json" \
    || warn "could not copy verdict to /sdcard (storage permission missing?)"

step "lean bootstrap done."
