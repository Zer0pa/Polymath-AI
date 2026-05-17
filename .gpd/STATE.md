# Research State

## Project Reference

See: `.gpd/PROJECT.md` (updated 2026-05-17)

**Machine-readable scoping contract:** `.gpd/state.json` field
`project_contract`

**Core research question:** Can Polymath-AI execute and validate a real Gemma 4
training run natively on REDMAGIC SM8750 without substituting Mac or RunPod for
any runtime data-path stage?
**Current focus:** Phase 3: Executor Architecture

## Current Position

**Current Phase:** 03
**Current Phase Name:** Executor Architecture
**Total Phases:** 10
**Current Plan:** 1
**Total Plans in Phase:** 1
**Status:** Ready to plan
**Last Activity:** 2026-05-17
**Last Activity Description:** G2 import/regression and G3 two-layer phone OpenCL forward expansion passed; G1 remained green.

**Progress:** [███░░░░░░░] 30%

## Active Calculations

- Phase 3 executor architecture planning is next.

## Intermediate Results

- G1 passed before this phase and is preserved as a regression floor:
  `runtime/reports/gemma4_megakernel/parity/20260516_e4b_layer0_opencl_gate/gate_result.json`.
- G2 import/regression harness passed:
  `runtime/reports/gemma4_megakernel/import_and_regression/20260517T030510Z_g2_import_regression/gate_result.json`.
- G3 two-layer phone OpenCL forward stack passed:
  `runtime/reports/gemma4_megakernel/forward_stack/20260517T032829Z_g3_two_layer_opencl/gate_result.json`.

## Open Questions

- Which minimum adapter or low-rank trainable scope fits the first phone
  backward/update gate without violating frozen base hashes?
- Which license-clean Hugging Face text slice is acceptable for the first
  phone-native streamed batch?
- Whether OpenCL remains the first training backend or Vulkan earns the route
  after equal correctness evidence.

## Performance Metrics

| Label | Duration | Tasks | Files |
| --- | --- | --- | --- |
| G1 OpenCL elapsed | `5.750567s` | E4B layer 0 forward | Upstream gate |
| G1 repeat elapsed | `5.658739s` | E4B layer 0 forward repeat | Upstream gate |

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

### Active Approximations

| Approximation | Validity Range | Controlling Parameter | Current Value | Status |
| --- | --- | --- | --- | --- |
| Adapter/low-rank first trainable scope | G5/G6 only until evidence expands scope | rank `r` | TBD | Pending |

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

### Pending Todos

None yet.

### Blockers/Concerns

- Formal GPD one-shot project writer is not exposed by the installed CLI; the
  contract validator and state persistence commands are available and were used.
- Next gate is G4 executor architecture; do not treat G3 forward expansion as
  backward/update/training progress.

## Session Continuity

**Last session:** 2026-05-17
**Stopped at:** Ready to plan Phase 3 / G4 executor architecture.
**Resume file:** `.gpd/STATE.md`
