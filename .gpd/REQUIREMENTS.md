# Requirements: Polymath Gemma 4 Snapdragon Megakernel Native Training

**Defined:** 2026-05-17
**Core Research Question:** Can Polymath-AI execute and validate a real Gemma 4
training run natively on REDMAGIC SM8750 without substituting Mac or RunPod for
any runtime data-path stage?

## Primary Requirements

### Control Plane

- [x] **CTRL-01**: Preserve the authority PRD, Resistance V2 doctrine, formal
  GPD project files, pivot branch, and import policy in repo files.
- [x] **CTRL-02**: Keep RunPod and REDMAGIC access probes recorded with no
  secrets, no weights, and no forbidden artifacts copied into git.
- [x] **CTRL-03**: Preserve G1 as a regression floor and reject any claim that
  inflates it into fused megakernel, backward, optimizer, training, NPU, or
  sustained thermal proof.

### Import And Regression

- [x] **IMPT-01**: Import Gemma4 Kernel source, schemas, runbooks, and text
  evidence under `integrations/gemma4-snapdragon-megakernel/`.
- [x] **IMPT-02**: Record upstream source commit hashes and per-file import
  status in the manifest.
- [x] **IMPT-03**: Exclude model weights, raw output bins, SDK binaries, build
  trees, caches, tokens, `.venv`, and `node_modules`.
- [x] **IMPT-04**: Provide a local Mac build/CTest command and a G1 phone/RunPod
  regression command path.

### Forward Runtime

- [x] **FWD-01**: Run at least two sequential Gemma E4B decoder layers on phone
  OpenCL unless a memory proof forces a smaller next step.
- [x] **FWD-02**: Produce fixed inputs, RunPod PyTorch reference, phone output,
  per-token cosine report, intermediate tensor dump option, and memory
  high-water report.
- [x] **FWD-03**: Preserve p50 cosine >= `0.99`, failed non-pad tokens `0`, and
  G1 green after expansion.

### Executor Architecture

- [x] **ARCH-01**: Refactor direct runner into explicit `TensorStore`,
  `LayerPackReader`, `BackendExecutor`, `ReferenceComparator`, `TelemetrySink`,
  `Tokenizer`, `SequencePacker`, `CheckpointStore`, and
  `TrainingStepExecutor` boundaries where useful.
- [x] **ARCH-02**: Avoid deep nesting, duplication, opaque names, and decorative
  abstractions.
- [x] **ARCH-03**: Keep G1 and G3 green after refactor.

### Backward And Optimizer

- [x] **BACK-01**: Declare an adapter or low-rank trainable scope attached to
  E4B layer 0 and the minimum adjacent tensors required for a real update.
- [x] **BACK-02**: Produce PyTorch gradient reference, phone gradient output,
  gradient cosine/error report, frozen pre/post hashes, and mutation contract.
- [x] **OPT-01**: Perform a phone-side optimizer update with optimizer state on
  phone, trainable tensor mutation, frozen base hash stability, finite loss,
  deterministic replay where expected, and G1 green.

### Phone Data Pipeline

- [x] **DATA-01**: Stream license-clean HF raw text directly to phone without
  printing or committing tokens.
- [x] **DATA-02**: Run Gemma tokenizer on phone CPU with exact token ID parity
  for fixed samples.
- [x] **DATA-03**: Pack fixed-shape sequence shards on phone UFS with checksums
  and deterministic replay into identical batches.
- [ ] **DATA-04**: Feed packed phone shards into the training runtime without
  Mac or RunPod serving batches.

### Integrated Training And Sustained Run

- [ ] **TRN-01**: Execute at least one real streamed-corpus batch through
  phone-native forward/backward/update.
- [ ] **TRN-02**: Emit a checkpoint or adapter artifact manifest with hashes,
  frozen/trainable tensor evidence, loss trace, telemetry, and replay data.
- [ ] **SUS-01**: Complete a six-hour authority run or a shorter predeclared
  objective before six hours without thermal, memory, checkpoint, or
  correctness collapse.

### Falsification

- [ ] **FALS-01**: Run G10 falsifier review for wrong revision, wrong/random
  weights, backend fallback, pad-token inflation, relaxed tolerances, hidden
  host data path, trainable/frozen scope violation, checkpoint replay failure,
  artifact hash mismatch, thermal/memory hiding, proxy benchmark substitution,
  and narrative pass without artifact pass.

## Follow-up Requirements

- **NPU-01**: Evaluate Hexagon/QNN frozen-forward or recompute islands only
  after Adreno training route gates justify it.
- **VULK-01**: Promote Vulkan only after equal-correctness phone evidence.
- **CORP-01**: Expand corpora only after first phone-native training slice is
  correct and replayable.

## Out of Scope

| Topic | Reason |
| --- | --- |
| Qwen frozen-middle correctness | Deprecated for this lane |
| Host-only training | Violates phone authority topology |
| Product UI or chat demo | Does not advance terminal gate |
| Public claims before G10 | Falsifier and license gates must close first |

## Accuracy and Validation Criteria

| Requirement | Accuracy Target | Validation Method |
| --- | --- | --- |
| IMPT-04 | Imported host tests pass locally | CMake configure/build and CTest |
| FWD-03 | p50 cosine >= `0.99`; failed non-pad tokens `0` | RunPod PyTorch comparator |
| BACK-02 | Default gradient p50 cosine >= `0.99` unless GPD numerical analysis changes threshold | PyTorch gradient reference |
| OPT-01 | Frozen hashes unchanged; trainable hashes change; finite loss | Phone hash and replay manifest |
| DATA-02 | Exact token ID parity | Fixed-sample tokenizer comparator |
| TRN-02 | Replayable checkpoint/adapter hash manifest | Re-read and validate artifact |
| FALS-01 | No unresolved critical falsifier | G10 report |

## Contract Coverage

| Requirement | Decisive Output / Deliverable | Anchor / Benchmark / Reference | Prior Inputs / Baselines | False Progress To Reject |
| --- | --- | --- | --- | --- |
| IMPT-01 | Imported source tree | Import manifest | Upstream commit `8a5fb2d` | Broad copy with forbidden artifacts |
| IMPT-04 | Build/test/regression commands | G1 gate result | Upstream G1 report | Local build as authority pass |
| FWD-03 | Multi-layer cosine report | RunPod PyTorch oracle | G1 cosine report | Pad-token-inflated pass |
| OPT-01 | Phone update manifest | Frozen hash contract | Trainable mutation contract | CPU/host update masquerading as phone |
| DATA-04 | UFS cache manifest | PRD runtime topology | Phone tokenizer parity | Hidden host batch serving |
| FALS-01 | Falsifier report | Resistance V2 | All gate evidence | Narrative pass |

## Traceability

| Requirement | Phase | Status |
| --- | --- | --- |
| CTRL-01 | Phase 0: Control Plane | Complete |
| CTRL-02 | Phase 0: Control Plane | Complete |
| CTRL-03 | Phase 0: Control Plane | Complete |
| IMPT-01 | Phase 1: Import And Regression | Complete |
| IMPT-02 | Phase 1: Import And Regression | Complete |
| IMPT-03 | Phase 1: Import And Regression | Complete |
| IMPT-04 | Phase 1: Import And Regression | Complete |
| FWD-01 | Phase 2: Forward Expansion | Complete |
| FWD-02 | Phase 2: Forward Expansion | Complete |
| FWD-03 | Phase 2: Forward Expansion | Complete |
| ARCH-01 | Phase 3: Executor Architecture | Complete |
| ARCH-02 | Phase 3: Executor Architecture | Complete |
| ARCH-03 | Phase 3: Executor Architecture | Complete |
| BACK-01 | Phase 4: Backward Path | Complete |
| BACK-02 | Phase 4: Backward Path | Complete |
| OPT-01 | Phase 5: Optimizer Update | Complete |
| DATA-01 | Phase 6: Phone Data Pipeline | Complete |
| DATA-02 | Phase 6: Phone Data Pipeline | Complete |
| DATA-03 | Phase 6: Phone Data Pipeline | Complete |
| DATA-04 | Phase 6: Phone Data Pipeline | Pending |
| TRN-01 | Phase 7: Integrated Training | Pending |
| TRN-02 | Phase 7: Integrated Training | Pending |
| SUS-01 | Phase 8: Sustained Authority Run | Pending |
| FALS-01 | Phase 9: Falsifier Review | Pending |

**Coverage:**

- Primary requirements: 24 total
- Mapped to phases: 24
- Unmapped: 0

---

_Requirements defined: 2026-05-17_
