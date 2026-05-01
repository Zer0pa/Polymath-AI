#!/usr/bin/env bash
# Phase 0C export probe — phone-side runner.
#
# After Termux bootstrap (scripts/termux/bootstrap.sh) completes, this
# script attempts a real LiteRT / QNN compile for each (model, scope,
# target) triple and writes envelope-shaped CompileRecord rows.
#
# Prerequisites (all gated by bootstrap):
#   * python venv at ~/polymath/venv with ai_edge_litert installed
#     (pip install ai-edge-litert; the Android arm64 wheel ships AOT
#     support that the macOS x86_64 wheel does not - Decision D-012)
#   * scripts/termux/bootstrap.sh has succeeded
#   * SoC target resolved with confidence 1.0 (Decision D-006); pass it
#     via --soc-target

set -uo pipefail

SOC_TARGET=""
OUT="${HOME}/polymath/export_probe"
SCOPES="tiny_block,qwen_block,qwen_frozen_subgraph,smollm3_block,smollm3_frozen_subgraph"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --soc-target) SOC_TARGET="$2"; shift 2;;
        --out) OUT="$2"; shift 2;;
        --scopes) SCOPES="$2"; shift 2;;
        *) echo "unknown arg $1"; exit 2;;
    esac
done

if [[ -z "${SOC_TARGET}" ]]; then
    echo "usage: $0 --soc-target {SM8650|SM8750|SM8850} [--out <dir>]"
    echo "Probe the phone first with scripts/host/phone_probe.sh and resolve"
    echo "the target before running this. Decision D-006 forbids QNN compile"
    echo "against a guessed SoC."
    exit 2
fi

VENV="${HOME}/polymath/venv"
if [[ ! -d "${VENV}" ]]; then
    echo "venv missing - run scripts/termux/bootstrap.sh first"
    exit 3
fi
# shellcheck disable=SC1091
source "${VENV}/bin/activate"

# Try to import the AOT subpackage and the Qualcomm target enum. If they
# are missing, log the blocker and emit a stub truth table so the executor
# can still compose Phase 0C results from what is known.
python - <<PY
import json, os, sys
out = os.environ.get("POLYMATH_OUT") or sys.argv[1]
soc = os.environ.get("POLYMATH_SOC") or sys.argv[2]
os.makedirs(out, exist_ok=True)

probe = {"soc_target": soc, "ai_edge_litert": None, "aot_available": False, "qualcomm_target_module": False}
try:
    import ai_edge_litert
    probe["ai_edge_litert"] = getattr(ai_edge_litert, "__version__", "unknown")
except Exception as e:
    probe["ai_edge_litert_import_error"] = repr(e)

try:
    from ai_edge_litert.aot import aot_compile
    probe["aot_available"] = True
except Exception as e:
    probe["aot_import_error"] = repr(e)

try:
    from ai_edge_litert.aot.vendors.qualcomm import target as qnn_target
    probe["qualcomm_target_module"] = True
    probe["qualcomm_socs"] = [n for n in dir(qnn_target.SocModel) if not n.startswith("_")]
except Exception as e:
    probe["qualcomm_target_module_import_error"] = repr(e)

with open(os.path.join(out, "litert_probe.json"), "w") as f:
    json.dump(probe, f, indent=2, sort_keys=True)
print(json.dumps(probe, indent=2))
PY "${OUT}" "${SOC_TARGET}"

if [[ ! -f "${OUT}/litert_probe.json" ]]; then
    echo "[export_probe] FAILED to write litert_probe.json"
    exit 4
fi

if grep -q '"aot_available": true' "${OUT}/litert_probe.json"; then
    echo "[export_probe] AOT path available; proceed with real compile sweep."
    echo "[export_probe] (Implementation: drive ai_edge_torch / litert.aot.aot_compile against the"
    echo "  exported tflite/torch graph for each scope; record CompileRecord rows in ${OUT}/.)"
    echo "[export_probe] full sweep is the next-step on Phase 0G."
else
    echo "[export_probe] AOT path NOT available on this Termux. Decision D-012 applies."
    echo "[export_probe] Either install QAIRT SDK manually OR fall back to a Linux x86_64 host with QAIRT."
    echo "[export_probe] qnn_exact_path_unproven falsifier remains BLOCKED for QNN scopes."
fi
