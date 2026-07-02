# Wave C Phase3/4 Architecture Decision

UTC: 2026-07-02T13:58:29Z

Status: `waveC_phase34_architecture_route_ready`

Governing gate: `WaveC_Fused_Megakernel_Reorientation`

Reset artifact: `runtime/reports/orchestration/OBJECTIVE_RESET_FUSED_MEGAKERNEL_REORIENTATION_20260702T135456Z.md`

## Decision

Route: hybrid.

Phase 3 mainline for the next vertical slice is a real QNN/HTP consumed tensor island, not C5 prediction plumbing. Phase 4 mainline is the Adreno/OpenCL adapter-update cell that consumes the Phase 3 tensor.

Pure HTP/NPU is rejected for the immediate mainline because the current HTP artifact is a fixed-shape Gemma-compatible ReLU tensor island, not a full Gemma decoder or language-model forward objective. OpenCL-only is also rejected because it would delete the required NPU/HTP consumed-output edge. The route is therefore:

```text
PJP1 fixed packet -> Termux tensor staging -> QNN/HTP gemma_hidden2560_relu
  -> fixed [1,16,2560] float32 tensor -> OpenCL rank-16 adapter update
  -> compact metadata report + off-git adapter identity
```

This is a mechanical vertical slice back to the fused architecture, not a learning claim. The bounded MSE bridge is an update-surface proof only and must not be relabeled as C5, cross-entropy, perplexity, or model-quality movement.

## Phase3 To Phase4 Tensor Contract

Producer chain:

1. `scripts/termux/run_phase34_pjp1_htp_relu_input_stage.py`
2. `scripts/host/run_phase34_adb_pjp1_derived_htp_relu.py`
3. QAIRT/QNN backend `/data/local/tmp/qairt-2.44/lib/aarch64-android/libQnnHtp.so`
4. QNN context `/data/local/tmp/polymath_gemma4_gate/phase13/20260524T210920Z_phase13_gemma4_only_heterogeneous/p13f/htp/relu/context/gemma_hidden2560_relu.qnn.bin`

Contract:

| Field | Value |
| --- | --- |
| semantic role | Phase 3 consumed forward tensor |
| shape | `[1,16,2560]` |
| dtype | `float32_le` |
| bytes | `163840` |
| memory location | phone storage, `/sdcard/Download/.../pjp1_htp_relu_input/htp_relu_run/run/Result_0/gemma_hidden_relu_out.raw` |
| raw boundary | raw tensor remains on phone; repo receives compact JSON metadata only |
| graph | `gemma_hidden2560_relu` |
| context SHA-256 | `81830ab0c0808843a7528d4c099c852957524c97a3c999c62eaa6e01f250673a` |
| C1 tensor SHA-256 | `eb596435b18457cc511cd7bd6a9530d76bc07379dbae2aa8b8285d4059b918ea` |
| C1 source PJP1 SHA-256 | `a9e191c1e9ec0f7110fabe5991033f3176cf60c152dcc78b54e2e786a66604bc` |
| C1 target tensor SHA-256 | `348cd7afa5636ee54c89a36d69073e42fdecf3efc0913f3063dfe68c8600eb7e` |
| proof of consumption | Phase4 report field `consumed_output_causes_update=true`, matching `phase4/C1/phase3_output_sha256`, nonzero adapter delta, and current-validator blockers `[]` |

Consumer:

`native/polar_phase34_consumer_preflight/phase4_bridge_cell_runner.cpp`

The consumer opens the Phase 3 tensor path, uploads it to OpenCL buffers, executes `compute_q`, `loss_partials`, `grad_update_b`, `post_update_loss_partials`, and `perturb_x`, and emits a compact report. It does not consume metadata in place of the tensor.

## Phase4 Adapter-Update Surface

Cell id: `phase4_opencl_phase3_bridge_rank16_mse_sgd_cell_v0`

Adapter site: residual adapter applied to the consumed hidden tensor:

```text
z = x + ((x @ A) @ B) / rank
```

Adapter shape:

| Tensor | Shape | Dtype | Init |
| --- | --- | --- | --- |
| A | `[2560,16]` | `float32` | deterministic seed `3407` |
| B | `[16,2560]` | `float32` | zero |

Update:

```text
loss = mean((z - y)^2)
B -= 0.0003 * dloss/dB
```

Current slice only updates `B`; `A` is deterministic and included in the adapter pre/post identity. Frozen base mutation count must remain zero. Objective, gradient, and update execute on Adreno/OpenCL; CPU is allowed only for deterministic initialization, compact hash/reporting, and reference parity.

Loss source for this slice: bounded MSE between the Phase 3 QNN/HTP tensor `x` and a PJP1 `target_polar`-derived tensor `y`. This is not a language-model objective and is not a C5 scorer substitute.

Checkpoint identity proof from accepted C1 lineage-repair report:

| Field | SHA-256 |
| --- | --- |
| adapter pre | `e0d1c66ac876c2b6fbbe9e88f1b02dd37201d8ffba10afcd44f1c558fc32f7c9` |
| adapter post | `1ba7faed815cec7e802bb297d4056934f81eae51be93f38a98f915fbaa94d78f` |
| adapter delta | nonzero, `adapter_delta_norm_l2=2.18221383802E-7` |

Proof the update came from the Phase 3 tensor:

- The runner reads `--phase3-output` as raw `float32` tensor bytes and computes `shell_sha256(args.phase3_output)` in the report.
- The OpenCL kernels use `x_mem` for `compute_q`, `loss_partials`, `grad_update_b`, `post_update_loss_partials`, and `perturb_x`.
- The report records `phase4/C1/phase3_output_sha256=eb596435b18457cc511cd7bd6a9530d76bc07379dbae2aa8b8285d4059b918ea`.
- The current validator returns `[]` for the C1 lineage-repair Phase4 report and metric report.

## Smallest Source Pathset

No source change is required to state the Wave C route. The source pathset to freeze for a rerunnable smallest slice is:

| Path | SHA-256 |
| --- | --- |
| `scripts/termux/run_phase34_pjp1_htp_relu_input_stage.py` | `df666f957ee26fd42c8d86a7a4fda448e58138f8296074b8e11576a2b75927ff` |
| `scripts/host/run_phase34_adb_pjp1_derived_htp_relu.py` | `8e00a731ca0b13c75e0832a144d303261f6f60ef24d61a75879cd6931be73db1` |
| `scripts/host/run_phase34_adb_htp_relu_smoke.py` | `5e5fa10cb296011e80429c642810bc6da65578c1daaa6f5a9df14fb7f29f679a` |
| `scripts/host/run_phase34_metric_readiness_report.py` | `98b854f59856ea4871500e71bf528ce195df9a255fe406c09bf2b802265d424f` |
| `native/polar_phase34_consumer_preflight/phase4_bridge_cell_runner.cpp` | `7df10844eeea7cc10c0f66a24669fedc9656cad39068a60e90c7bf059cb2c0e6` |
| `native/polar_phase34_consumer_preflight/build_phase4_bridge_cell_runner.sh` | `fc75497c0a3dfdb5703138495fd3c7cf7b170628f61c1f041f58ff170d93ee95` |
| `polymath_ai/polar/phase4_bridge_cell.py` | `c7da2ea73ceb21d21262561b3f179f3120d293b3d5611e4a14abdabb06abcd83` |
| `tests/test_phase4_bridge_cell.py` | `d06c1eff236a9d247eae5d6d69c3fd1cfb69540c75f28ef8af92c0cc4803ad3d` |

## Validation Evidence

Current local validation:

```bash
python3.11 -m pytest tests/test_phase4_bridge_cell.py
```

Result: `19 passed`.

Current-source compact report validation:

```text
validate_phase4_bridge_report(C1 lineage-repair phase4 report) -> []
validate_phase34_metric_readiness(C1 lineage-repair metric report, corpus_phase="C1") -> []
```

Accepted metadata-only reports:

| Artifact | SHA-256 |
| --- | --- |
| `runtime/reports/integrated_c1_c4_execution/c1_c4_waveB_rerun_20260630T230411Z/phase34_lineage_repair/phase34_lineage_repair_summary.json` | `1348895a1d5ca8e7e5276de1ab2022d9f64a300b288aa7169550263b27a0e304` |
| `runtime/reports/integrated_c1_c4_execution/c1_c4_waveB_rerun_20260630T230411Z/phase34_lineage_repair/C1/pjp1_htp_relu_run/phase34_pjp1_derived_htp_relu_run.json` | `483b1531b649b71cbbce37ea8f1f716f8ba4b309e0d4a9cfca274da50c37babb` |
| `runtime/reports/integrated_c1_c4_execution/c1_c4_waveB_rerun_20260630T230411Z/phase34_lineage_repair/C1/phase4_bridge_cell/phase4_bridge_cell_report.json` | `c8eeee9a7ce54a9780b584dfb5d343c33db00c7aa3bebd803e95ab114a48e831` |
| `runtime/reports/integrated_c1_c4_execution/c1_c4_waveB_rerun_20260630T230411Z/phase34_lineage_repair/C1/phase34_metric_readiness/phase34_metric_readiness_report.json` | `ab8fb945b34645e72b1e607b4e3ce87d18dde082fa285e1d34ea8331363e0fc6` |

This satisfies the requested minimum: one fixed-shape input, one consumed HTP tensor, one OpenCL adapter update, and one metadata-only report. It does not authorize C5 scoring.

## Bounded Rerun Command

Use this only after Engineering/Meta issues a Wave C execution GO and Termux/ADB control is available. It keeps raw PJP1, raw QNN output, and adapter binaries off git.

Termux staging command:

```bash
CORPUS_PHASE=C1
RUN_LABEL=waveC_phase34_${CORPUS_PHASE}_$(date -u +%Y%m%dT%H%M%SZ)
PHONE_PJP1=<termux_private_pjp1_for_${CORPUS_PHASE}>
PHONE_STAGE_ROOT=/sdcard/Download/polymath_phase34/${RUN_LABEL}/pjp1_htp_relu_input

cd ~/Polymath-AI
PYTHONPATH=. python3 scripts/termux/run_phase34_pjp1_htp_relu_input_stage.py \
  --pjp1 "$PHONE_PJP1" \
  --output-root "$PHONE_STAGE_ROOT" \
  --packet-index 0 \
  --tokens 16 \
  --authority-material waveC_vertical_slice_only \
  --corpus-phase "$CORPUS_PHASE"
```

Mac/ADB command, using the same `RUN_LABEL`, `CORPUS_PHASE`, and `PHONE_STAGE_ROOT` chosen for the Termux step:

```bash
CORPUS_PHASE=C1
RUN_LABEL=<same_run_label_as_termux_step>
PHONE_STAGE_ROOT=/sdcard/Download/polymath_phase34/${RUN_LABEL}/pjp1_htp_relu_input
HOST_REPORT_ROOT=runtime/reports/polar_phase34_consumer_preflight/${RUN_LABEL}
CONTEXT=/data/local/tmp/polymath_gemma4_gate/phase13/20260524T210920Z_phase13_gemma4_only_heterogeneous/p13f/htp/relu/context/gemma_hidden2560_relu.qnn.bin
CONTEXT_SHA256=81830ab0c0808843a7528d4c099c852957524c97a3c999c62eaa6e01f250673a
SOURCE_PJP1_SHA256=<sha256_of_termux_private_pjp1_for_${CORPUS_PHASE}>

python3.11 scripts/host/run_phase34_adb_pjp1_derived_htp_relu.py \
  --stage-report "$PHONE_STAGE_ROOT/phase34_pjp1_htp_relu_input_stage.json" \
  --report "$HOST_REPORT_ROOT/pjp1_htp_relu_run/phase34_pjp1_derived_htp_relu_run.json" \
  --corpus-phase "$CORPUS_PHASE"

native/polar_phase34_consumer_preflight/build_phase4_bridge_cell_runner.sh
adb push native/polar_phase34_consumer_preflight/bin/phase4_bridge_cell_runner /data/local/tmp/phase4_bridge_cell_runner
adb shell chmod 755 /data/local/tmp/phase4_bridge_cell_runner

PHONE_PHASE3_OUTPUT="$PHONE_STAGE_ROOT/htp_relu_run/run/Result_0/gemma_hidden_relu_out.raw"
PHONE_PHASE4_TARGET="$PHONE_STAGE_ROOT/pjp1_packet0_tokens16_phase4_target.f32.bin"
PHONE_PHASE4_OUT=/sdcard/Download/polymath_phase34/${RUN_LABEL}/phase4_bridge_cell
adb shell "rm -rf '$PHONE_PHASE4_OUT' && /data/local/tmp/phase4_bridge_cell_runner \
  --phase3-output '$PHONE_PHASE3_OUTPUT' \
  --target '$PHONE_PHASE4_TARGET' \
  --out-dir '$PHONE_PHASE4_OUT' \
  --corpus-phase '$CORPUS_PHASE' \
  --source-pjp1-sha256 '$SOURCE_PJP1_SHA256' \
  --context '$CONTEXT' \
  --context-sha256 '$CONTEXT_SHA256'"

mkdir -p "$HOST_REPORT_ROOT/phase4_bridge_cell"
adb pull "$PHONE_PHASE4_OUT/phase4_bridge_cell_report.json" "$HOST_REPORT_ROOT/phase4_bridge_cell/phase4_bridge_cell_report.json"

python3.11 scripts/host/run_phase34_metric_readiness_report.py \
  --htp-report "$HOST_REPORT_ROOT/pjp1_htp_relu_run/phase34_pjp1_derived_htp_relu_run.json" \
  --phase4-report "$HOST_REPORT_ROOT/phase4_bridge_cell/phase4_bridge_cell_report.json" \
  --output "$HOST_REPORT_ROOT/phase34_metric_readiness/phase34_metric_readiness_report.json" \
  --corpus-phase "$CORPUS_PHASE"
```

Stop conditions:

- stop after one packet, 16 tokens;
- stop if QNN output SHA does not match expected ReLU SHA;
- stop if Phase4 report has non-empty validator blockers;
- stop if `consumed_output_causes_update` is not true;
- stop if adapter pre/post SHA-256 are equal;
- stop if any raw `.pjp1`, `.raw`, `.f32.bin`, model, adapter, checkpoint, or tensor payload is pulled into git;
- do not run C5 scorer in this Wave C slice.

## Exact Unresolved Technical Gap

The unresolved technical gap for the original maximal architecture is:

```text
full_gemma_htp_forward_tensor_not_yet_consumed_by_real_lm_loss_or_adapter_update
```

Smallest next implementation action after this route packet:

Replace the `gemma_hidden2560_relu` QNN context with the smallest Gemma decoder subgraph that can consume a fixed-shape hidden tensor and emit a hidden tensor with the same `[1,16,2560] float32_le` contract, then feed that output into the same OpenCL adapter-update cell. If QNN compilation/runtime fails, record the exact unsupported op/runtime field and keep the OpenCL bridge as the fallback mainline.

## Nonclaims

- no C5 pass
- no C5 scorer execution
- no learning/model-quality claim until real eval
- no Phase3 readiness
- no Phase4 readiness
- no 100k/1M authority
- no raw payloads in git
- no Comet-backed accepted run
