# Phase 09 Research: Final Falsifier Review

## Scope

This phase is a promotion denial test. It does not add performance claims or new
training capability. It attacks the whole G1-G9 evidence chain for wrong model
revision, hidden host data path, backend fallback, pad-token inflation,
tolerance relaxation, frozen/trainable hash violations, checkpoint replay
breakage, artifact leakage, token leakage, and narrative overclaiming.

## Authority Evidence

| Gate | Required artifact |
| --- | --- |
| G1 | `runtime/reports/gemma4_megakernel/parity/20260516_e4b_layer0_opencl_gate/gate_result.json` |
| G2 | `runtime/reports/gemma4_megakernel/import_and_regression/20260517T030510Z_g2_import_regression/gate_result.json` |
| G3 | `runtime/reports/gemma4_megakernel/forward_stack/20260517T032829Z_g3_two_layer_opencl/gate_result.json` |
| G4 | `runtime/reports/gemma4_megakernel/executor_architecture/20260517T040000Z_g4_minimal_executor/gate_result.json` |
| G5 | `runtime/reports/gemma4_megakernel/backward_path/20260517T040000Z_g5_rank4_adapter_opencl/gate_result.json` |
| G6 | `runtime/reports/gemma4_megakernel/optimizer_update/20260517T040000Z_g6_rank4_adapter_sgd/gate_result.json` |
| G7 | `runtime/reports/gemma4_megakernel/phone_data_pipeline/20260517T040000Z_g7_hf_native_token_pack/gate_result.json` |
| G8 repaired | `runtime/reports/gemma4_megakernel/integrated_training/20260517T071405Z_g8_streamed_corpus_repaired/gate_result.json` |
| Phase 8 | `runtime/reports/gemma4_megakernel/sustained_authority/20260517T071405Z_g9_three_batch_chain/gate_result.json` |

The failed G8 attempt remains part of the evidence because it proves the hidden
fixture path was rejected instead of narrated into a partial pass:
`runtime/reports/gemma4_megakernel/integrated_training/20260517T040000Z_g8_streamed_corpus_falsified/gate_result.json`.

## Critical Falsifiers

- Wrong model or revision: every comparator that carries model metadata must
  stay pinned to `google/gemma-4-E4B` revision
  `7aa32e6889efd6300124851b164f8b364314c3d8`.
- Hidden host data path: G8/Phase8 may consume phone token cache and immutable
  Gemma assets only. Host-generated hidden states are oracle outputs, not
  runtime inputs.
- Backend fallback: token-to-hidden is explicitly `phone_cpu`; layer and
  adapter work must remain OpenCL. CPU fallback cannot satisfy an OpenCL claim.
- Pad-token inflation: forward comparisons must use FP64 cosine over non-pad
  tokens with zero failed non-pad tokens.
- Frozen/trainable violation: frozen layer hashes must remain identical;
  rank-4 adapter checkpoint hashes must change each step and chain across
  Phase 8 batches.
- Artifact hygiene: raw tensor/checkpoint/model files, raw selected text,
  `.env`, and HF tokens must not be tracked in git.
- Overclaim guard: the pass scope is a rank-4 post-layer0 residual adapter,
  two-layer distillation path, and three-batch predeclared chain. It is not full
  Gemma 4 training, a six-hour endurance proof, or a Hexagon NPU proof.

## Execution Method

The final review is codified in
`integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/tools/compare_outputs/final_falsifier_review.py`.
It emits `falsifier_report.json`, `gate_result.json`, `commands.log`, and
`blockers.md` under
`runtime/reports/gemma4_megakernel/falsifiers/<run_id>_g10_final_falsifier_review/`.
The script must fail closed: any unresolved check denies promotion.

## Promotion Rule

If all checks pass, only the narrow claim may be promoted:
REDMAGIC phone-native streamed-token Gemma4 E4B two-layer distillation run with
rank-4 post-layer0 adapter SGD and checkpoint chain.
