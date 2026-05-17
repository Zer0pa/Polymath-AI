# Research State

## Project Reference

See: `.gpd/PROJECT.md` (updated 2026-05-17)

**Machine-readable scoping contract:** `.gpd/state.json` field
`project_contract`

**Core research question:** Can Polymath-AI execute and validate a real Gemma 4
training run natively on REDMAGIC SM8750 without substituting Mac or RunPod for
any runtime data-path stage?
**Current focus:** Phase 7: Integrated Training blocked under falsification

## Current Position

**Current Phase:** 07
**Current Phase Name:** Integrated Training
**Total Phases:** 10
**Current Plan:** 1
**Total Plans in Phase:** 1
**Status:** Blocked
**Last Activity:** 2026-05-17
**Last Activity Description:** G4 minimal executor architecture, G5 adapter backward, G6 phone SGD update, and G7 phone-native HF stream/tokenize/pack passed. G8 integrated training was rejected because the current training step still consumes hidden-state fixtures instead of deriving Gemma hidden/per-layer inputs from phone-packed token IDs.

**Progress:** [███████░░░] 70%

## Active Calculations

- Next valid G8 repair: implement phone-native `input_ids -> layer_input +
  per_layer_input` generation from frozen Gemma embedding/per-layer-input
  assets, then feed phone-produced tensors into layer0/layer1 and adapter
  backward/update without host hidden fixtures.

## Intermediate Results

- G1 passed before this phase and is preserved as a regression floor:
  `runtime/reports/gemma4_megakernel/parity/20260516_e4b_layer0_opencl_gate/gate_result.json`.
- G2 import/regression harness passed:
  `runtime/reports/gemma4_megakernel/import_and_regression/20260517T030510Z_g2_import_regression/gate_result.json`.
- G3 two-layer phone OpenCL forward stack passed:
  `runtime/reports/gemma4_megakernel/forward_stack/20260517T032829Z_g3_two_layer_opencl/gate_result.json`.
- G4 minimal executor architecture passed:
  `runtime/reports/gemma4_megakernel/executor_architecture/20260517T040000Z_g4_minimal_executor/gate_result.json`.
- G5 rank-4 post-layer0 adapter backward passed against RunPod PyTorch:
  `runtime/reports/gemma4_megakernel/backward_path/20260517T040000Z_g5_rank4_adapter_opencl/gate_result.json`.
- G6 phone-side SGD update passed with frozen base hashes stable:
  `runtime/reports/gemma4_megakernel/optimizer_update/20260517T040000Z_g6_rank4_adapter_sgd/gate_result.json`.
- G7 phone-native HF stream, Gemma BPE tokenization, and UFS packing passed
  exact token/mask parity:
  `runtime/reports/gemma4_megakernel/phone_data_pipeline/20260517T040000Z_g7_hf_native_token_pack/gate_result.json`.
- G8 integrated streamed-corpus training was rejected under falsification:
  `runtime/reports/gemma4_megakernel/integrated_training/20260517T040000Z_g8_streamed_corpus_falsified/gate_result.json`.

## Open Questions

- Which minimal G8 objective should be promoted after phone-native embedding
  generation: two-layer phone distillation to a stop-gradient layer1 target or
  chunked tied-embedding next-token CE/NLL?
- Whether OpenCL remains the first training backend or Vulkan earns the route
  after equal correctness evidence.

## Performance Metrics

| Label | Duration | Tasks | Files |
| --- | --- | --- | --- |
| G1 OpenCL elapsed | `5.750567s` | E4B layer 0 forward | Upstream gate |
| G1 repeat elapsed | `5.658739s` | E4B layer 0 forward repeat | Upstream gate |
| G5 adapter grad elapsed | `0.600701s` | Rank-4 adapter backward | Phone OpenCL |
| G6 adapter SGD elapsed | `0.602772s` | Rank-4 adapter update | Phone OpenCL |
| G7 token cache | exact parity | 3 HF-streamed sequences, seq128 | Phone CPU/UFS |

## Accumulated Context

### Decisions

Full log: `.gpd/DECISIONS.md`

**Recent high-impact:**
- Phase 0: Treat `docs/PRD-GEMMA4-SNAPDRAGON-MEGAKERNEL-HETEROGENEOUS-TRAINING.md`
  as authority PRD and `RESISTANCE-V2.md` as doctrine.
- Phase 0: Use branch `gemma4-megakernel-native-training`.
- Phase 0: Import Gemma4 Kernel only under
  `integrations/gemma4-snapdragon-megakernel/`.
- Phase 0: Treat G1 as regression floor only.
- Phase 7: Reject G8 promotion while training still consumes hidden-state
  fixtures; the next valid gate must derive Gemma hidden/per-layer inputs from
  phone-packed token IDs.

### Active Approximations

| Approximation | Validity Range | Controlling Parameter | Current Value | Status |
| --- | --- | --- | --- | --- |
| Adapter/low-rank first trainable scope | G5/G6 and next G8 repair | rank `r` | 4 | Passed for fixture gradient/update; insufficient for streamed training until token-to-hidden bridge exists |

**Convention Lock:**

- Tensor layout: batch-major sequence tensors unless manifest states otherwise.
- Numeric comparison: FP64 cosine over non-pad tokens for forward and gradient
  gate reports unless a validated numerical-analysis amendment supersedes it.
- Backend claim: CPU fallback must be explicit and cannot satisfy an
  Adreno/OpenCL/Vulkan gate.
- Runtime topology: phone is authority; RunPod is build/reference oracle only;
  Mac is control plane only.

### Propagated Uncertainties

| Quantity | Current Value | Uncertainty | Last Updated (Phase) | Method |
| --- | --- | --- | --- | --- |
| G1 p50 cosine | `0.9999890020383452` | Comparator/report precision | Phase 0 | RunPod PyTorch oracle |
| G1 min cosine | `0.9999801999737985` | Comparator/report precision | Phase 0 | RunPod PyTorch oracle |
| G3 p50 cosine | `0.999993563915067` | Comparator/report precision | Phase 2 | RunPod PyTorch oracle |
| G3 max RSS | `818764` KB | Android getrusage high-water semantics | Phase 2 | Phone telemetry |
| G5 gradient cosine min | `0.9999999999999384` | Comparator/report precision | Phase 4 | RunPod PyTorch oracle |
| G6 update cosine min | `0.9999999999999384` | Comparator/report precision | Phase 5 | RunPod PyTorch oracle |
| G7 token mismatches | `0` | Exact ID/mask comparison | Phase 6 | RunPod Transformers oracle |

### Pending Todos

- Implement phone-native embedding gather from packed `input_ids` to
  `layer_input.f32`.
- Implement phone-native Gemma PLE/per-layer-input generation for layers 0 and
  1.
- Extend phone cache ABI with `labels`, `loss_mask`, and `position_ids`.
- Emit G8 checkpoint manifests with replay validation once streamed-corpus
  training consumes phone-produced tensors.

### Blockers/Concerns

- Formal GPD one-shot project writer is not exposed by the installed CLI; the
  contract validator and state persistence commands are available and were used.
- G8 is currently falsified by hidden-host-data-path risk. Current G5/G6 update
  consumes hidden-state fixtures and cannot be claimed as streamed-corpus
  training.

## Session Continuity

**Last session:** 2026-05-17
**Stopped at:** G8 rejected under falsification; next repair is the
phone-native token-to-hidden bridge.
**Resume file:** `.gpd/STATE.md`
