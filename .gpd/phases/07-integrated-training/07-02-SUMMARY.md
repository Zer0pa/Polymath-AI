---
plan_id: 07-02
phase: 07
status: complete
completed: 2026-05-17
---

# Summary: G8 Phone-Native Streamed-Corpus Repair

## Result

Passed. The repaired G8 run starts from phone-streamed HF text, phone-native Gemma BPE tokenization, and immutable Gemma asset files on REDMAGIC NX789J. It generates `layer_input`, layer0 PLE, and layer1 PLE tensors on the phone, runs OpenCL layer0/layer1, performs a rank-4 adapter SGD update on phone, and emits a checkpoint with frozen/trainable hashes.

Primary gate:
`runtime/reports/gemma4_megakernel/integrated_training/20260517T071405Z_g8_streamed_corpus_repaired/gate_result.json`

Falsifier:
`runtime/reports/gemma4_megakernel/falsifiers/20260517T071405Z_g8_streamed_corpus_repaired/falsifier_report.json`

## Decisive Evidence

- Token cache ABI passed exact parity for `input_ids`, `attention_mask`, `labels`, `loss_mask`, and `position_ids`.
- Phone-generated token-to-hidden bridge passed RunPod HF tensor comparisons; minimum p50 across bridge tensors was `0.9999982087594611`.
- Phone OpenCL layer0/layer1 outputs passed RunPod PyTorch comparison with p50 `0.9999895268153007` and `0.9999936773992628`.
- Phone adapter gradients and checkpoint update passed PyTorch oracle comparison with cosine min `0.9999981024312786`.
- Frozen layer hashes were stable and trainable adapter hashes changed.
- G1 and G3 regressions passed after the G8 runtime changes.

## Remaining Work

Phase 8 must prove this is not a fragile one-step artifact. The next plan should define a predeclared sustained authority run with repeated phone-local batches/checkpoints, thermal/memory/storage telemetry, replay validation, and preserved G1/G3 regression floors.
