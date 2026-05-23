# Artifact Index

Use this index to reach the raw evidence. The research pack summarizes these
artifacts; inspect originals when making claims.

## Authority And State

- Active PRD:
  `docs/PRD-GEMMA4-SNAPDRAGON-MEGAKERNEL-HETEROGENEOUS-TRAINING.md`
- GPD state:
  `.gpd/STATE.md`
- Roadmap:
  `.gpd/ROADMAP.md`
- Decisions:
  `.gpd/DECISIONS.md`
- Integration manifest:
  `integrations/gemma4-snapdragon-megakernel/MANIFEST.md`

## Passed Gates

- G1 layer0 OpenCL:
  `runtime/reports/gemma4_megakernel/parity/20260516_e4b_layer0_opencl_gate/gate_result.json`
- G2 import/regression:
  `runtime/reports/gemma4_megakernel/import_and_regression/20260517T030510Z_g2_import_regression/gate_result.json`
- G3 two-layer forward:
  `runtime/reports/gemma4_megakernel/forward_stack/20260517T032829Z_g3_two_layer_opencl/gate_result.json`
- G5 adapter backward:
  `runtime/reports/gemma4_megakernel/backward_path/20260517T040000Z_g5_rank4_adapter_opencl/gate_result.json`
- G6 optimizer update:
  `runtime/reports/gemma4_megakernel/optimizer_update/20260517T040000Z_g6_rank4_adapter_sgd/gate_result.json`
- G8 repaired integrated training:
  `runtime/reports/gemma4_megakernel/integrated_training/20260517T071405Z_g8_streamed_corpus_repaired/gate_result.json`
- G9 three-batch chain:
  `runtime/reports/gemma4_megakernel/sustained_authority/20260517T071405Z_g9_three_batch_chain/gate_result.json`
- Phase 10 six-hour endurance:
  `runtime/reports/gemma4_megakernel/hardware_max/20260517T153500Z_phase10_six_hour_endurance/gate_result.json`

## Failed Or Blocked Gates

- Original G8 hidden-fixture rejection:
  `runtime/reports/gemma4_megakernel/integrated_training/20260517T040000Z_g8_streamed_corpus_falsified/gate_result.json`
- QNN/HTP training non-claim:
  `runtime/reports/gemma4_megakernel/hardware_max/20260517T213600Z_phase10_qnn_htp_probe/gate_result.json`
- Phase 10 nonclaim gate:
  `runtime/reports/gemma4_megakernel/hardware_max/20260517T214000Z_phase10_nonclaim_gate/gate_result.json`

## GPD Summaries

- Phase 7 integrated training:
  `.gpd/phases/07-integrated-training/07-02-SUMMARY.md`
- Phase 8 sustained authority:
  `.gpd/phases/08-sustained-authority-run/08-01-SUMMARY.md`
- Phase 9 falsifier review:
  `.gpd/phases/09-falsifier-review/09-01-SUMMARY.md`
- Phase 10 hardware max pipeline:
  `.gpd/phases/10-hardware-max-training-pipeline/10-01-SUMMARY.md`
  `.gpd/phases/10-hardware-max-training-pipeline/10-02-SUMMARY.md`

## Source Code Entry Points

- Runner:
  `integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/src/runner/main.cpp`
- OpenCL runner:
  `integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/src/backends/opencl_layer_runner.cpp`
- Adapter training header:
  `integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/include/polymath/gemma4/adapter_training.h`
- Host endurance script:
  `scripts/host/run_gemma4_phone_endurance.py`
- QNN/HTP probe:
  `scripts/host/run_phase10_qnn_htp_probe.py`

## External Context

- Upstream Gemma4 Kernel:
  `/Users/Zer0pa/Gemma4 Kernel`
- RunPod workspace:
  `/workspace/Polymath-AI`
- RunPod artifacts:
  `/workspace/artifacts/polymath_gemma4`
- Phone runtime root:
  `/data/local/tmp/polymath_gemma4_gate`
