# Polymath Gemma 4 Snapdragon Megakernel Native Training

## What This Is

This project builds a native Gemma 4 training appliance on REDMAGIC `NX789J` /
Snapdragon `SM8750`. The runtime claim is phone-native: Hugging Face raw text
streams to the phone, Gemma tokenization runs on phone CPU, packed sequence
cache lives on phone UFS, and forward/backward/update execute on the phone
before emitting a validated checkpoint or adapter artifact.

## Core Research Question

Can Polymath-AI execute and validate a real Gemma 4 training run natively on
REDMAGIC SM8750 without substituting Mac or RunPod for any runtime data-path
stage?

## Scoping Contract Summary

### Contract Coverage

- Terminal claim: phone-native Gemma 4 stream, tokenize, pack, train, and
  checkpoint path.
- Regression floor: the passed `google/gemma-4-E4B` layer 0 OpenCL phone gate
  remains green after material runtime changes.
- False progress to reject: host-only training, compile-only success,
  throughput-only claims, G1 inflation into training, or hidden host-side
  tokenization/packing/minibatch serving.

### User Guidance To Preserve

- **User-stated observables:** G1 p50 cosine `0.9999890020383452`, min cosine
  `0.9999801999737985`, failed tokens `0`, repeat output byte-identical.
- **User-stated deliverables:** validated checkpoint or adapter artifact with
  hashes, replay manifests, telemetry, and falsifier report.
- **Must-have references / prior outputs:** authority PRD, `RESISTANCE-V2.md`,
  G1 Polymath pointer, upstream gate report, upstream orchestrator handover,
  integration manifest.
- **Stop / rethink conditions:** G1 regression, hidden host runtime path,
  frozen base tensor mutation, destructive phone risk without rollback,
  unresolved license ambiguity, or uncontrolled cloud spend.

### Scope Boundaries

**In scope**

- Gemma 4 model-specific native runtime work.
- REDMAGIC SM8750 authority execution.
- Adreno OpenCL/Vulkan forward, backward, reduction, and optimizer kernels.
- Phone CPU tokenization, UFS packing, telemetry, checkpoint/adapters.
- RunPod builds, conversions, and PyTorch references only.

**Out of scope**

- Qwen frozen-middle correctness as an active path.
- Host-only training claims.
- Mac-held model weights or datasets in the authority runtime path.
- Product UI, chat demo, benchmark promotion, or corpus expansion before the
  phone-native training slice works.

### Active Anchor Registry

- `ref-authority-prd`: `docs/PRD-GEMMA4-SNAPDRAGON-MEGAKERNEL-HETEROGENEOUS-TRAINING.md`
  - Why it matters: defines terminal gate, ladder, artifact policy, and
    boundary blockers.
  - Carry forward: planning, execution, verification, writing.
  - Required action: read, use, compare.
- `ref-resistance-v2`: `RESISTANCE-V2.md`
  - Why it matters: blocks proxy wins and completion narratives before the
    governing objective is met or falsified.
  - Carry forward: planning, execution, verification, writing.
  - Required action: read, use.
- `ref-g1-result`: `runtime/reports/gemma4_megakernel/parity/20260516_e4b_layer0_opencl_gate/gate_result.json`
  - Why it matters: permanent regression floor for all later runtime changes.
  - Carry forward: planning, execution, verification.
  - Required action: read, compare, use.
- `ref-upstream-gate-report`: `/Users/Zer0pa/Gemma4 Kernel/gemma4_megakernel/docs/gate_reports/20260516_e4b_layer0_gate_execution.md`
  - Why it matters: command and evidence ledger for the passed G1 phone gate.
  - Carry forward: planning, execution, verification.
  - Required action: read, use, compare.
- `ref-upstream-handover`: `/Users/Zer0pa/Gemma4 Kernel/docs/orchestrator_handover_gemma4_e4b_gate.md`
  - Why it matters: inspection entry points and non-claims after G1.
  - Carry forward: planning, execution.
  - Required action: read, use.
- `ref-import-manifest`: `integrations/gemma4-snapdragon-megakernel/MANIFEST.md`
  - Why it matters: only approved Polymath landing zone and exclusion policy.
  - Carry forward: planning, execution, verification.
  - Required action: read, use, compare.

### Carry-Forward Inputs

- Upstream Gemma4 Kernel commit `8a5fb2df0c7e8da52fb0bc346077e63e8c801009`.
- Passed upstream gate commit `c5b6e3522d28d0e1dc56084cb97fa9e95e29aa4e`.
- REDMAGIC serial `FY25013101C8`.
- RunPod pod `ltg8fdnxgmzwjy`, remote workspace `/workspace/Polymath-AI`.

### Skeptical Review

- **Weakest anchor:** first trainable-scope memory and correctness budget is
  not yet proven on phone.
- **Unvalidated assumptions:** imported OpenCL source can build inside
  Polymath without semantic drift; existing phone artifacts remain sufficient
  for G1 replay until the imported build replaces them.
- **Competing explanation:** G1 proves one-layer forward correctness, but
  backward/update or phone-native data path may still fail.
- **Disconfirming observation:** G1 fails after import/refactor, host serves a
  runtime data-path stage, or frozen base hashes mutate.
- **False progress to reject:** compile/test/report-only success promoted as
  training progress.

### Open Contract Questions

- Which minimum adapter or low-rank trainable scope fits the first phone
  backward/update gate?
- Which license-clean Hugging Face text slice should be used for the first
  phone-native streamed batch?
- Does OpenCL remain the training backend after equal-correctness Vulkan
  comparison, or does evidence force a switch?

## Research Questions

### Answered

- G1: one real pretrained Gemma 4 E4B layer can run forward-only on REDMAGIC
  Adreno OpenCL and match RunPod PyTorch at p50 cosine above `0.99`.

### Active

- [ ] Can the imported G1 source build and preserve the phone regression path
  inside Polymath without forbidden artifacts?
- [ ] Can the phone run at least two sequential Gemma E4B decoder layers with
  p50 cosine >= `0.99` and zero failed non-pad tokens?
- [ ] Can a declared adapter/low-rank trainable scope produce finite phone
  gradients and deterministic updates while frozen base hashes remain stable?
- [ ] Can the phone stream HF raw text, tokenize, pack, cache, train, and emit
  a replayable checkpoint/adaptor without hidden host data-path help?

### Out of Scope

- Qwen frozen-middle correctness as an active route.
- Product or chatbot UI.
- Public release or benchmark claims before license and falsifier gates close.

## Research Context

### Physical System

REDMAGIC 10 Pro class phone, model `NX789J`, Snapdragon `SM8750`, Oryon CPU,
Adreno GPU, Hexagon NPU, unified memory, UFS storage, Android 15.

### Theoretical Framework

Numerical ML systems research for on-device LLM training. Correctness is
defined by tensor contracts, host PyTorch oracle comparisons, frozen/trainable
hash invariants, replay manifests, and adversarial falsifier review.

### Key Parameters and Scales

| Parameter | Symbol | Regime | Notes |
| --- | --- | --- | --- |
| Cosine floor | `c_p50` | `>= 0.99` | G1/G3 forward and G5 gradient default threshold |
| Failed non-pad tokens | `n_fail` | `0` | No non-pad token may fall below gate threshold |
| Sequence length | `T` | 128/256/512 candidates | Memory plan decides expansion |
| Trainable rank | `r` | TBD | Starts adapter/low-rank, expands only by evidence |
| Sustained window | `t_run` | 6 hours or predeclared objective | G9 authority run |

### Known Results

- G1 OpenCL phone gate passed on `FY25013101C8`.
- Upstream Mac host CMake/CTest passed for the G1 code path.
- RunPod Android arm64 runner built successfully for the G1 code path.

### What Is New

The project is not an inference demo. It attempts to establish a complete
phone-native Gemma 4 training runtime with authority evidence and falsifier
protection.

### Target Venue

Internal research infrastructure first. External claims are blocked until
license review, sustained gate evidence, and G10 falsification pass.

### Computational Environment

- Mac: control plane and git orchestration.
- RunPod: Android/NDK build server and PyTorch oracle.
- REDMAGIC: authority runtime.
- GitHub: source, text reports, manifests, and review surface.

## Notation and Conventions

See `.gpd/CONVENTIONS.md` for runtime and tensor conventions.

## Unit System

Tensor values are unitless ML activations/weights unless a report states
otherwise. Times are seconds. Storage is bytes/GiB. Temperatures are Celsius.

## Requirements

See `.gpd/REQUIREMENTS.md`.

## Key References

The contract-critical references are mirrored in the Active Anchor Registry
above and stored in `.gpd/state.json`.

## Constraints

- **Artifact policy:** do not commit weights, raw tensor outputs, SDK binaries,
  caches, `.env`, tokens, `.venv`, or `node_modules`.
- **Runtime topology:** phone is authority; RunPod and Mac cannot serve runtime
  data-path stages.
- **Regression floor:** G1 remains green after material runtime changes.
- **Safety:** phone operations must preserve rollback and avoid destructive
  changes without explicit rollback path.

## Key Decisions

| Decision | Rationale | Outcome |
| --- | --- | --- |
| Use `gemma4-megakernel-native-training` pivot branch | Main branch is pre-pivot and deprecated for this lane | Active |
| Import Gemma4 Kernel under `integrations/gemma4-snapdragon-megakernel/` | Preserves namespace and artifact policy | Active |
| Treat G1 as regression floor only | Prevents G1 inflation into training claim | Active |

---

_Last updated: 2026-05-17 after formal GPD repair from authority PRD._
