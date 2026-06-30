# Phase3/4 Execution Handoff After Stage0 Green

Status: prepared handoff only. Do not execute until Stage0 drift gates are green and Execution receives explicit GO.

## Scope

This handoff tells Execution how to rerun the Phase3/4 metric-readiness path over the integrated C1-C4 lineage once Stage0 drift is green.

Current Phase3/4 evidence is diagnostic-pass only:

- PJP1-derived HTP smoke passed.
- Phase4 Adreno/OpenCL consumed-output bridge proof passed.
- Phase3/4 PRD metric-readiness report passed for `C1_diagnostic`.
- No Phase3 readiness, Phase4 readiness, learning, model-quality, or C5 authority is claimed.

## Required Stage0 Inputs Before Execution

Execution must not start this handoff until these Stage0 artifacts are green:

- Immutable material revision lock with HF commit SHA, not `main`.
- Clean repo commit or accepted full code-hash manifest.
- Phase2 identity reconciliation:
  - packetizer binary SHA
  - Termux source SHA
  - Termux build-script SHA
  - host source SHA
  - rebuild command
  - comparison result
- Canonical execution surface map.
- Raw-payload scan clean.

## Required Integrated Lineage Inputs

For each corpus phase `C1`, `C2`, `C2_5`, `C3`, `C4`, Execution must provide:

- Phase2 PJP1 phone path under Termux-private or approved phone-local storage.
- PJP1 SHA-256, byte count, packet count, source record count, source real token count.
- Phase2 wrapper report JSON.
- Phase2 native packetizer report JSON.
- Phase2 binary/source/build identity report.
- Material manifest and immutable HF revision.
- Corpus phase label normalized for metrics:
  - `C1`
  - `C2`
  - `C2_5`
  - `C3`
  - `C4`

Raw PJP1/PQA1/model/checkpoint tensors must stay phone-local and out of git.

## Canonical Phase3/4 Files

Source and validators:

- `scripts/termux/run_phase34_pjp1_htp_relu_input_stage.py`
- `scripts/host/run_phase34_adb_pjp1_derived_htp_relu.py`
- `native/polar_phase34_consumer_preflight/phase4_bridge_cell_runner.cpp`
- `native/polar_phase34_consumer_preflight/build_phase4_bridge_cell_runner.sh`
- `scripts/host/run_phase34_metric_readiness_report.py`
- `polymath_ai/polar/phase4_bridge_cell.py`
- `polymath_ai/polar/metrics_contract.py`
- `tests/test_phase4_bridge_cell.py`

Reference diagnostic reports:

- `runtime/reports/polar_phase34_consumer_preflight/active_wave/pjp1_htp_relu_input/phase34_pjp1_htp_relu_input_stage.json`
- `runtime/reports/polar_phase34_consumer_preflight/active_wave/pjp1_htp_relu_run/phase34_pjp1_derived_htp_relu_run.json`
- `runtime/reports/polar_phase34_consumer_preflight/active_wave/phase4_bridge_cell/phase4_bridge_cell_report.json`
- `runtime/reports/polar_phase34_consumer_preflight/active_wave/phase34_metric_readiness/phase34_metric_readiness_report.json`

## Rerun Commands

Set variables per corpus phase:

```bash
CORPUS_PHASE=C1
RUN_LABEL=integrated_c1_c5_<TIMESTAMP>_${CORPUS_PHASE}
PHONE_PJP1=/data/data/com.termux/files/home/<PHASE2_OUTPUT_ROOT>/<RUN_LABEL>.pjp1
PHONE_STAGE_ROOT=/sdcard/Download/polymath_phase34/${RUN_LABEL}/pjp1_htp_relu_input
HOST_REPORT_ROOT=runtime/reports/polar_phase34_consumer_preflight/${RUN_LABEL}
```

### 1. Termux PJP1-Derived HTP Input And Target Staging

Run inside Termux, or via a verified Termux control lane:

```bash
cd ~/Polymath-AI
PYTHONPATH=. python3 scripts/termux/run_phase34_pjp1_htp_relu_input_stage.py \
  --pjp1 "$PHONE_PJP1" \
  --output-root "$PHONE_STAGE_ROOT" \
  --packet-index 0 \
  --tokens 16 \
  --authority-material integrated_metric_diagnostic_only
```

Expected phone report:

```text
$PHONE_STAGE_ROOT/phase34_pjp1_htp_relu_input_stage.json
```

Expected compact host copy:

```text
$HOST_REPORT_ROOT/pjp1_htp_relu_input/phase34_pjp1_htp_relu_input_stage.json
```

### 2. ADB QNN/HTP Forward Run

Run from Mac control plane:

```bash
python3.11 scripts/host/run_phase34_adb_pjp1_derived_htp_relu.py \
  --stage-report "$PHONE_STAGE_ROOT/phase34_pjp1_htp_relu_input_stage.json" \
  --report "$HOST_REPORT_ROOT/pjp1_htp_relu_run/phase34_pjp1_derived_htp_relu_run.json" \
  --corpus-phase "$CORPUS_PHASE"
```

Expected compact report:

```text
$HOST_REPORT_ROOT/pjp1_htp_relu_run/phase34_pjp1_derived_htp_relu_run.json
```

Required pass fields:

- `status=pass`
- `qnn.actual_matches_expected_relu=true`
- `qnn.backend`
- `qnn.actual_output_sha256`
- `qnn.latency_ms`
- `qnn.tokens_per_sec`
- `phase3_ready_claim=false`
- `learning_claim=false`

### 3. Build Phase4 Android OpenCL Bridge Runner

Run from Mac control plane:

```bash
/usr/local/Caskroom/android-ndk/29/AndroidNDK14206865.app/Contents/NDK/toolchains/llvm/prebuilt/darwin-x86_64/bin/aarch64-linux-android29-clang++ \
  -std=c++17 -O3 -Wall -Wextra -Werror -static-libstdc++ \
  native/polar_phase34_consumer_preflight/phase4_bridge_cell_runner.cpp \
  -ldl \
  -o build/phase4_bridge_android/phase4_bridge_cell_runner
```

Push:

```bash
adb push build/phase4_bridge_android/phase4_bridge_cell_runner /data/local/tmp/phase4_bridge_cell_runner
adb shell chmod 755 /data/local/tmp/phase4_bridge_cell_runner
```

### 4. Run Phase4 Consumed-Output Bridge

Run from Mac control plane:

```bash
PHONE_PHASE3_OUTPUT="$PHONE_STAGE_ROOT/htp_relu_run/run/Result_0/gemma_hidden_relu_out.raw"
PHONE_PHASE4_TARGET="$PHONE_STAGE_ROOT/pjp1_packet0_tokens16_phase4_target.f32.bin"
PHONE_PHASE4_OUT=/sdcard/Download/polymath_phase34/${RUN_LABEL}/phase4_bridge_cell

adb shell "rm -rf '$PHONE_PHASE4_OUT' && \
  /data/local/tmp/phase4_bridge_cell_runner \
    --phase3-output '$PHONE_PHASE3_OUTPUT' \
    --target '$PHONE_PHASE4_TARGET' \
    --out-dir '$PHONE_PHASE4_OUT'"
```

Pull compact report only:

```bash
mkdir -p "$HOST_REPORT_ROOT/phase4_bridge_cell"
adb pull "$PHONE_PHASE4_OUT/phase4_bridge_cell_report.json" \
  "$HOST_REPORT_ROOT/phase4_bridge_cell/phase4_bridge_cell_report.json"
```

Do not pull raw `.raw`, `.f32.bin`, adapter binaries, PJP1, PQA1, model weights, or checkpoints into the repo.

### 5. Validate Phase4 Bridge Report

```bash
python3.11 - <<PY
import json
from pathlib import Path
from polymath_ai.polar.phase4_bridge_cell import validate_phase4_bridge_report
p = Path("$HOST_REPORT_ROOT/phase4_bridge_cell/phase4_bridge_cell_report.json")
blockers = validate_phase4_bridge_report(json.loads(p.read_text()))
print({"bridge_blockers": blockers})
raise SystemExit(0 if not blockers else 1)
PY
```

### 6. Build Combined Phase3/4 Metric-Readiness Report

```bash
python3.11 scripts/host/run_phase34_metric_readiness_report.py \
  --htp-report "$HOST_REPORT_ROOT/pjp1_htp_relu_run/phase34_pjp1_derived_htp_relu_run.json" \
  --phase4-report "$HOST_REPORT_ROOT/phase4_bridge_cell/phase4_bridge_cell_report.json" \
  --output "$HOST_REPORT_ROOT/phase34_metric_readiness/phase34_metric_readiness_report.json" \
  --corpus-phase "$CORPUS_PHASE"
```

Expected compact report:

```text
$HOST_REPORT_ROOT/phase34_metric_readiness/phase34_metric_readiness_report.json
```

Required pass fields:

- `status=pass`
- `bridge_validator_blockers=[]`
- `metric_readiness_blockers=[]`
- `metrics.phase3/<C>/htp_output_sha256`
- `metrics.phase3/<C>/forward_loss`
- `metrics.phase3/<C>/forward_mse`
- `metrics.phase3/<C>/tokens_per_sec`
- `metrics.phase3/<C>/latency_ms`
- `metrics.phase4/<C>/opencl_device`
- `metrics.phase4/<C>/phase3_output_sha256`
- `metrics.phase4/<C>/target_sha256`
- `metrics.phase4/<C>/adapter_pre_sha256`
- `metrics.phase4/<C>/adapter_post_sha256`
- `metrics.phase4/<C>/consumed_output_causes_update=true`
- `metrics.phase4/<C>/adapter_changed=true`
- `metrics.phase4/<C>/loss_pre_update`
- `metrics.phase4/<C>/loss_post_update`
- `metrics.phase4/<C>/loss_delta`
- `metrics.phase4/<C>/grad_norm_l2`
- `metrics.phase4/<C>/grad_norm_linf`
- `metrics.phase4/<C>/update_norm_l2`
- `metrics.phase4/<C>/adapter_delta_norm_l2`
- `metrics.phase4/<C>/nan_gradient_count=0`
- `metrics.phase4/<C>/inf_gradient_count=0`
- `metrics.phase4/<C>/opencl_kernel_ms`
- `metrics.phase4/<C>/tokens_per_sec`
- `metrics.phase4/<C>/latency_ms`
- `c5_compatibility.status=metric_names_aligned_no_c5_authority`

## C5 Compatibility Fields

The Phase3/4 metric-readiness report must include:

```json
{
  "c5_compatibility": {
    "status": "metric_names_aligned_no_c5_authority",
    "requires_c5_eval_points": [
      "C5_after_C1",
      "C5_after_C2",
      "C5_after_C2_5",
      "C5_after_C3",
      "C5_after_C4",
      "C5_full_curriculum_postrun"
    ],
    "nonclaim": "no C5 evaluation has been run by this Phase3/4 metric readiness proof"
  }
}
```

Phase3/4 does not own C5 pass/fail. It only emits compatible metrics and gradient/update telemetry for C5 consumers.

## Raw Payload Boundaries

Allowed in repo:

- Compact JSON reports.
- SHA-256 hashes.
- Source files.
- Runner source/binary identity hashes.
- Timing and metric scalars.

Forbidden in repo:

- `.qai1`
- `.pqa1`
- `.pjp1`
- raw `.raw`
- `.f32.bin`, `.i8.bin`, `.f16`
- model weights/checkpoints/adapters
- env files or secrets
- raw tokenizer/material payloads

Phone-local only:

- PJP1
- HTP raw output
- Phase4 target tensor
- adapter pre/post binary artifacts

## First Missing Field For Authority

First missing green field after this handoff is executed:

```text
C5 eval authority over the integrated C1-C4 lineage, with stable checkpoint comparison.
```

This requires:

- C5 after C1, C2, C2.5, C3, C4, and full curriculum postrun.
- Loss delta vs last stable checkpoint.
- Accuracy / exact match / token F1 where valid.
- Calibration metrics where probability outputs exist.
- Gradient norm max observed.
- Overfit gap.
- Checkpoint and stable-baseline hashes.

Without C5 passing, Phase3/4 metrics remain diagnostic or preflight evidence only.

## Nonclaims

- No Phase3 readiness.
- No Phase4 readiness.
- No learning claim.
- No model-quality claim.
- No C5 authority.
- No production training readiness.
