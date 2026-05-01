#!/usr/bin/env bash
# Termux bootstrap for Polymath on-device runner.
#
# Strategy (PRD §Runtime And Device Specification, Decision D-010):
#   1. Refresh package index, install python + git + ssh + clang + build deps.
#   2. Install python wheels for huggingface_hub, tokenizers, safetensors,
#      numpy, sentencepiece (these are well-supported in Termux).
#   3. ATTEMPT torch + transformers. If wheels are unavailable on
#      arm64-v8a Android, fall back to Termux-as-control-plane: the host
#      machine runs the model and Termux only orchestrates ADB pulls / HF
#      pushes.
#   4. Always succeed at least at the control-plane level. Never fail the
#      bootstrap if torch is unavailable; record the verdict instead.
#
# Idempotent. Safe to re-run.

set -uo pipefail

LOG="${HOME}/polymath/bootstrap-$(date -u +%Y%m%dT%H%M%SZ).log"
mkdir -p "$(dirname "${LOG}")"

step() { echo "[bootstrap $(date -u +%H:%M:%SZ)] $*" | tee -a "${LOG}"; }
ok()   { echo "[bootstrap OK]    $*" | tee -a "${LOG}"; }
warn() { echo "[bootstrap WARN]  $*" | tee -a "${LOG}"; }
fail() { echo "[bootstrap FAIL]  $*" | tee -a "${LOG}"; }

step "starting Polymath Termux bootstrap. log: ${LOG}"

# 1. Update Termux package index (no-op if just updated).
if command -v pkg >/dev/null 2>&1; then
    step "pkg update"
    pkg update -y >>"${LOG}" 2>&1 || warn "pkg update non-zero (continuing)"
    step "pkg upgrade -y"
    pkg upgrade -y >>"${LOG}" 2>&1 || warn "pkg upgrade non-zero (continuing)"
else
    fail "pkg command not found - is this really Termux?"
    exit 2
fi

# 2. Core OS packages.
PKG_CORE="python git openssh rsync wget curl which jq tmux nano clang make cmake ninja pkg-config"
step "installing core packages: ${PKG_CORE}"
pkg install -y ${PKG_CORE} >>"${LOG}" 2>&1 || fail "core package install failed"

# 3. Python build deps for native wheels.
PKG_PY_BUILD="rust binutils libffi openssl zlib"
step "installing python-build deps: ${PKG_PY_BUILD}"
pkg install -y ${PKG_PY_BUILD} >>"${LOG}" 2>&1 || warn "python-build deps partial"

# 4. Set up venv.
VENV="${HOME}/polymath/venv"
mkdir -p "$(dirname "${VENV}")"
if [[ ! -d "${VENV}" ]]; then
    step "creating venv at ${VENV}"
    python -m venv "${VENV}"
fi
# shellcheck disable=SC1091
source "${VENV}/bin/activate"
step "venv python: $(python --version)"

# 5. Pip-install control-plane Python deps. These are reliable in Termux.
step "upgrading pip + wheel"
pip install --upgrade pip wheel setuptools >>"${LOG}" 2>&1 || warn "pip upgrade partial"

CONTROL_PLANE_PY="huggingface_hub safetensors numpy<2 tokenizers sentencepiece pyyaml requests"
step "installing control-plane python deps"
pip install --no-cache-dir ${CONTROL_PLANE_PY} >>"${LOG}" 2>&1 \
    && ok "control-plane python deps installed" \
    || fail "control-plane python install failed - this IS a hard fail"

# 6. Try transformers (lighter than torch; CPU-only models work without torch
#    via the tokenizers-only path).
step "attempting transformers install"
pip install --no-cache-dir "transformers<5" >>"${LOG}" 2>&1 \
    && ok "transformers installed" \
    || warn "transformers unavailable - host-mediated path required"

# 7. Try torch. This is the high-risk install on Termux.
step "attempting torch install (this is the high-risk step)"
TORCH_RESULT="failed"
pip install --no-cache-dir torch 2>>"${LOG}" \
    && TORCH_RESULT="ok" \
    || TORCH_RESULT="failed"

if [[ "${TORCH_RESULT}" == "ok" ]]; then
    if python -c "import torch; t = torch.zeros(3, 4); _ = t @ t.T; print('torch ok', torch.__version__)" >>"${LOG}" 2>&1; then
        ok "torch import + tiny matmul OK"
        TORCH_RESULT="working"
    else
        warn "torch installed but failed at import / tiny op"
        TORCH_RESULT="installed_but_broken"
    fi
fi

# 8. Record the verdict so the host-side Phase 0D probe can read it.
VERDICT="${HOME}/polymath/termux-verdict.json"
cat > "${VERDICT}" <<EOF
{
  "schema_version": "1.0.0",
  "boundary": {
    "boundary_id": "boundary:polymath:v1",
    "boundary_text_sha256": "<filled by host parser>"
  },
  "termux_python_version": "$(python --version 2>&1 | awk '{print $2}')",
  "torch_install_result": "${TORCH_RESULT}",
  "transformers_present": "$(python -c 'import transformers; print(transformers.__version__)' 2>/dev/null || echo absent)",
  "huggingface_hub_present": "$(python -c 'import huggingface_hub; print(huggingface_hub.__version__)' 2>/dev/null || echo absent)",
  "tokenizers_present": "$(python -c 'import tokenizers; print(tokenizers.__version__)' 2>/dev/null || echo absent)",
  "safetensors_present": "$(python -c 'import safetensors; print(safetensors.__version__)' 2>/dev/null || echo absent)",
  "log_path": "${LOG}"
}
EOF
ok "verdict recorded at ${VERDICT}"

step "done."
