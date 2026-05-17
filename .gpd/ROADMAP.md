# Roadmap: Polymath Gemma 4 Snapdragon Megakernel Native Training

## Overview

The route runs from control-plane repair and upstream import through multi-layer
forward parity, executor architecture, backward path, optimizer update,
phone-native HF streaming/tokenization/packing, integrated training, sustained
authority run, and falsifier review. G1 remains a permanent regression floor;
the terminal acceptance gate is a phone-native checkpoint or adapter artifact.

## Contract Overview

| Contract Item | Advanced By Phase(s) | Status |
| --- | --- | --- |
| Formal PRD/GPD/branch/import policy | Phase 0 | Complete |
| G1 regression floor | Phase 1 and every material runtime phase | Passed, remained green through G7 changes |
| Phone-native training artifact | Phases 4-8 | Blocked at G8 token-to-hidden bridge |
| G10 falsifier survival | Phase 9 | Planned |

## Phases

- [x] **Phase 0: Control Plane** - Formal GPD state, pivot branch, hardware
  probes, and import policy.
- [x] **Phase 1: Import And Regression** - Import Gemma4 Kernel source/evidence
  under policy and build the G1 replay harness.
- [x] **Phase 2: Forward Expansion** - Expand from one layer to at least two
  sequential E4B layers on phone OpenCL with strict parity.
- [x] **Phase 3: Executor Architecture** - Refactor runner into maintainable
  runtime boundaries without tensor semantic drift.
- [x] **Phase 4: Backward Path** - Implement phone backward kernels for the
  declared trainable scope.
- [x] **Phase 5: Optimizer Update** - Perform a real phone-side optimizer update
  with frozen hash stability.
- [x] **Phase 6: Phone Data Pipeline** - HF stream to phone CPU tokenizer to UFS
  packed cache.
- [ ] **Phase 7: Integrated Training** - Consume phone-packed batches in
  phone-side forward/backward/update and emit artifact manifest.
- [ ] **Phase 8: Sustained Authority Run** - Six-hour or predeclared objective
  phone-native run.
- [ ] **Phase 9: Falsifier Review** - Attack and resolve critical claim
  falsifiers before promotion.

## Phase Details

### Phase 0: Control Plane

**Goal:** Make the pivot executable from repo files, not chat memory.
**Depends on:** Nothing.
**Requirements:** CTRL-01, CTRL-02, CTRL-03.
**Contract Coverage:**
- Advances: formal scoping, branch route, G1 regression floor preservation.
- Deliverables: `.gpd/PROJECT.md`, `.gpd/config.json`, `.gpd/REQUIREMENTS.md`,
  `.gpd/ROADMAP.md`, `.gpd/STATE.md`, `.gpd/state.json`, phase directories.
- Anchor coverage: authority PRD, Resistance V2, G1 result, import manifest.
- Forbidden proxies: treating GPD artifacts as gate completion.
**Success Criteria** (what must be TRUE):

1. Formal GPD project files exist and state contract validates.
2. Pivot branch exists.
3. RunPod and ADB probes are recorded.
4. G1 is explicitly recorded as regression floor only.

**Plans:** 1 plan

Plans:

- [x] 00-01: Repair formal GPD control plane.

### Phase 1: Import And Regression

**Goal:** Make Gemma4 Kernel the canonical implementation lane inside Polymath
without artifact leakage.
**Depends on:** Phase 0.
**Requirements:** IMPT-01, IMPT-02, IMPT-03, IMPT-04.
**Contract Coverage:**
- Advances: `deliv-g1-regression-harness`.
- Deliverables: imported source tree, manifest update, build/test report,
  G1 replay runbook.
- Anchor coverage: upstream commit `8a5fb2d`, G1 gate report, G1 result.
- Forbidden proxies: broad copy with forbidden artifacts; local build as
  authority pass.
**Success Criteria** (what must be TRUE):

1. Every imported file is policy-allowed and listed or covered in the manifest.
2. No weights, raw `.bin` outputs, SDKs, build directories, caches, tokens,
   `.venv`, or `node_modules` are under the import.
3. Mac CMake/CTest command passes for imported host code or the exact build
   blocker is recorded.
4. G1 regression command path is present and points to phone/RunPod authority
   evidence.

**Plans:** 1 plan

Plans:

- [x] 01-01: Import Gemma4 Kernel and preserve G1 regression harness.

### Phase 2: Forward Expansion

**Goal:** Expand from one layer to a meaningful forward stack while preserving
numerical authority.
**Depends on:** Phase 1.
**Requirements:** FWD-01, FWD-02, FWD-03.
**Contract Coverage:**
- Advances: phone forward stack evidence.
- Deliverables: fixed input set, PyTorch reference, phone output, cosine
  report, intermediate dump option, memory high-water report.
- Anchor coverage: G1 floor and RunPod oracle.
- Forbidden proxies: one-layer re-run sold as expansion.
**Success Criteria** (what must be TRUE):

1. At least two sequential E4B decoder layers run on phone OpenCL unless memory
   proof forces a smaller next step.
2. p50 cosine >= `0.99` and failed non-pad tokens `0`.
3. G1 remains green.

**Plans:** 1 plan

Plans:

- [x] 02-01: Run two sequential E4B decoder layers on phone OpenCL.

### Phase 3: Executor Architecture

**Goal:** Refactor the direct runner into durable executor components without
changing tensor semantics.
**Depends on:** Phase 2.
**Requirements:** ARCH-01, ARCH-02, ARCH-03.
**Contract Coverage:**
- Advances: maintainable runtime for backward/update/data pipeline.
- Deliverables: interfaces and tests for tensor store, backend executor,
  comparator, tokenizer, packer, checkpoint store, and training step executor.
- Anchor coverage: G1/G3 parity.
- Forbidden proxies: decorative abstraction or refactor-only completion.
**Success Criteria** (what must be TRUE):

1. Required component boundaries exist where useful.
2. Code standards are enforced.
3. G1 and G3 remain green.

**Plans:** 1 plan

Plans:

- [x] 03-01: Add minimal executor boundaries and keep G1/G3 green.

### Phase 4: Backward Path

**Goal:** Implement backward kernels for a declared trainable scope.
**Depends on:** Phase 3.
**Requirements:** BACK-01, BACK-02.
**Contract Coverage:**
- Advances: gradient correctness for phone training.
- Deliverables: trainable scope, PyTorch gradient reference, phone gradient,
  cosine/error report, frozen hashes, mutation contract.
- Anchor coverage: G1, gradient oracle.
- Forbidden proxies: fake update, CPU/host gradient substitution.
**Success Criteria** (what must be TRUE):

1. Gradients are finite.
2. Default gradient p50 cosine >= `0.99` unless numerical analysis changes it.
3. Frozen tensor hashes stay unchanged.
4. G1 remains green.

**Plans:** 1 plan

Plans:

- [x] 04-01: Run rank-4 post-layer0 adapter backward on phone OpenCL.

### Phase 5: Optimizer Update

**Goal:** Perform a real phone-side optimizer update.
**Depends on:** Phase 4.
**Requirements:** OPT-01.
**Contract Coverage:**
- Advances: trainable mutation under phone runtime.
- Deliverables: optimizer state, pre/post hashes, finite loss, replay manifest.
- Anchor coverage: frozen hash contract and G1.
- Forbidden proxies: host-side optimizer update.
**Success Criteria** (what must be TRUE):

1. Trainable tensors mutate.
2. Frozen base tensors do not mutate.
3. Loss is finite and update replay is deterministic under fixed seed where
   determinism is expected.
4. G1 remains green.

**Plans:** 1 plan

Plans:

- [x] 05-01: Run phone-side SGD update for rank-4 adapter.

### Phase 6: Phone Data Pipeline

**Goal:** Build HF raw text stream to phone tokenizer to UFS packed cache.
**Depends on:** Phase 5.
**Requirements:** DATA-01, DATA-02, DATA-03, DATA-04.
**Contract Coverage:**
- Advances: phone-native runtime data path.
- Deliverables: dataset manifest, license/provenance ledger, tokenizer parity,
  packing report, UFS cache manifest, retry/resume behavior.
- Anchor coverage: PRD topology.
- Forbidden proxies: host-side tokenization or batch serving.
**Success Criteria** (what must be TRUE):

1. Fixed samples have exact token ID parity.
2. Packed shards replay into identical batches.
3. No secrets are printed or committed.
4. No hidden host-side data path exists.

**Plans:** 1 plan

Plans:

- [x] 06-01: Stream CC0 HF text to phone, tokenize with native Gemma BPE, and
  pack seq128 UFS cache with exact token parity.

### Phase 7: Integrated Training

**Goal:** Connect phone-native batches to phone-side forward/backward/update.
**Depends on:** Phase 6.
**Requirements:** TRN-01, TRN-02.
**Contract Coverage:**
- Advances: terminal phone training artifact.
- Deliverables: run config, audit log, batch manifest, checkpoint/adapter
  manifest, loss trace, telemetry, G1 regression report.
- Anchor coverage: terminal gate and G1.
- Forbidden proxies: a synthetic batch or host batch sold as streamed corpus.
**Success Criteria** (what must be TRUE):

1. At least one real streamed-corpus batch updates the trainable scope.
2. Checkpoint or adapter artifact is emitted.
3. Frozen base hashes are stable.
4. No correctness regression or hidden host data path.

**Plans:** 1 failed attempt

Plans:

- [ ] 07-01: Attempt integrated streamed-corpus training.
  **Outcome:** rejected under falsification because the current training path
  still requires hidden-state fixtures. Next repair must generate
  `layer_input` and `per_layer_input` from phone-packed token IDs.

### Phase 8: Sustained Authority Run

**Goal:** Prove the system is not a fragile one-step artifact.
**Depends on:** Phase 7.
**Requirements:** SUS-01.
**Contract Coverage:**
- Advances: sustained terminal authority evidence.
- Deliverables: six-hour or predeclared-objective telemetry, checkpoint
  writes, memory/thermal/network/storage/error logs.
- Anchor coverage: G1 after sustained run.
- Forbidden proxies: short smoke test as sustained proof.
**Success Criteria** (what must be TRUE):

1. No thermal collapse.
2. No invalidating memory leak.
3. No checkpoint corruption.
4. Final checkpoint or adapter validates and G1 remains green.

**Plans:** TBD

### Phase 9: Falsifier Review

**Goal:** Attack the claim before promotion.
**Depends on:** Phase 8.
**Requirements:** FALS-01.
**Contract Coverage:**
- Advances: final promotion safety.
- Deliverables: falsifier report and resolved critical issues.
- Anchor coverage: all gate evidence.
- Forbidden proxies: narrative pass without artifact pass.
**Success Criteria** (what must be TRUE):

1. Wrong revision, wrong/random weights, backend fallback, pad-token inflation,
   tolerance relaxation, hidden host data path, frozen/trainable violation,
   checkpoint replay failure, artifact mismatch, thermal/memory hiding, and
   benchmark proxy substitution are all checked.
2. No unresolved critical falsifier remains.

**Plans:** TBD

## Progress

| Phase | Plans Complete | Status | Completed |
| --- | --- | --- | --- |
| 0. Control Plane | 1/1 | Complete | 2026-05-17 |
| 1. Import And Regression | 1/1 | Complete | 2026-05-17 |
| 2. Forward Expansion | 1/1 | Complete | 2026-05-17 |
| 3. Executor Architecture | 1/1 | Complete | 2026-05-17 |
| 4. Backward Path | 1/1 | Complete | 2026-05-17 |
| 5. Optimizer Update | 1/1 | Complete | 2026-05-17 |
| 6. Phone Data Pipeline | 1/1 | Complete | 2026-05-17 |
| 7. Integrated Training | 0/1 | Failed under falsification | - |
| 8. Sustained Authority Run | 0/TBD | Not started | - |
| 9. Falsifier Review | 0/TBD | Not started | - |
