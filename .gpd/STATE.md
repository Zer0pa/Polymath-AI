# Research State

## Project Reference

See: `.gpd/PROJECT.md` (updated 2026-05-17)

**Machine-readable scoping contract:** `.gpd/state.json` field
`project_contract`

**Core research question:** Can Polymath-AI execute and validate a real Gemma 4
training run natively on REDMAGIC SM8750 without substituting Mac or RunPod for
any runtime data-path stage?
**Current focus:** Phase 9: Final Falsifier Review after sustained authority pass

## Current Position

**Current Phase:** 09
**Current Phase Name:** Falsifier Review
**Total Phases:** 10
**Current Plan:** 0
**Total Plans in Phase:** TBD
**Status:** Ready to plan
**Last Activity:** 2026-05-17
**Last Activity Description:** G8 repaired and passed, then Phase 8 passed a predeclared three-batch chained phone-native training objective. Each batch used phone token caches, immutable Gemma assets, OpenCL layer0/layer1, phone-side adapter SGD, checkpoint chaining, RunPod PyTorch comparisons, and final G1/G3 regressions.

**Progress:** [█████████░] 90%

## Active Calculations

- Next phase: perform the final adversarial falsifier review across G1-G9
  before any promotion wording is allowed.

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
- G8 integrated streamed-corpus training was repaired and passed:
  `runtime/reports/gemma4_megakernel/integrated_training/20260517T071405Z_g8_streamed_corpus_repaired/gate_result.json`.
- Phase 8 sustained authority objective passed:
  `runtime/reports/gemma4_megakernel/sustained_authority/20260517T071405Z_g9_three_batch_chain/gate_result.json`.

## Open Questions

- Whether the final promotion claim should remain "rank-4 adapter training
  pipeline" or be further narrowed to "two-layer distillation adapter chain"
  until chunked next-token NLL exists.
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
| G8 token cache | exact parity | 8 HF-streamed sequences, seq128 | Phone CPU/UFS |
| G8 token-to-hidden p50 min | `0.9999982087594611` | layer input + layer0/1 PLE | Phone asset bridge vs RunPod HF |
| G8 layer0/layer1 p50 | `0.9999895268153007` / `0.9999936773992628` | phone OpenCL | RunPod PyTorch oracle |
| G8 adapter update cosine min | `0.9999981024312786` | gradient/update/checkpoint | RunPod PyTorch oracle |
| Phase 8 sustained chain | pass | 3 batches, checkpoint chaining | Phone runtime + RunPod oracle |

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
- Phase 7: Repaired G8 promotion is valid only because training consumes
  phone-packed token IDs plus immutable Gemma assets, not host hidden fixtures.

### Active Approximations

| Approximation | Validity Range | Controlling Parameter | Current Value | Status |
| --- | --- | --- | --- | --- |
| Adapter/low-rank first trainable scope | G5/G6/G8 | rank `r` | 4 | Passed for fixture and streamed phone-native gradient/update; still a minimal training scope, not full-model training |

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
| G8 token mismatches | `0` | Exact ID/mask/label/loss-mask/position comparison | Phase 7 | RunPod Transformers oracle |
| G8 max RSS | `2169344` KB | Android getrusage high-water semantics | Phase 7 | Phone telemetry |
| Phase 8 adapter cosine min | `0.9999977029847468` | Worst batch in 3-batch chain | Phase 8 | RunPod PyTorch oracle |

### Pending Todos

- Execute Phase 9 falsifier review over wrong revision, hidden data path,
  backend fallback, pad-token inflation, checkpoint replay, frozen/trainable
  violations, and overclaiming.

### Blockers/Concerns

- Formal GPD one-shot project writer is not exposed by the installed CLI; the
  contract validator and state persistence commands are available and were used.
- Phase 8 passed a predeclared three-batch objective, but it is not a six-hour
  endurance proof and must not be narrated as one.

## Session Continuity

**Last session:** 2026-05-17
**Stopped at:** Phase 8 sustained authority objective passed; next work is
Phase 9 final falsifier review.
**Resume file:** `.gpd/STATE.md`
