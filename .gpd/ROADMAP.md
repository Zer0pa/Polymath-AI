# Roadmap: Polymath Gemma 4 Snapdragon Megakernel Native Training

## Overview

The route runs from control-plane repair and upstream import through multi-layer
forward parity, executor architecture, backward path, optimizer update,
phone-native HF streaming/tokenization/packing, integrated training, sustained
authority run, and falsifier review. G1 remains a permanent regression floor;
the terminal acceptance gate is a phone-native checkpoint or adapter artifact.
Phase 11 converted the latest hardware research synthesis into a sequential
phone-resident POVC campaign rather than another host-driven endurance loop.
Phase 12 repaired the expanded residual-adapter path but also exposed a serious
contamination risk: Qwen/random-init HTP artifacts are invalid for Gemma
heterogeneous claims. Phase 13 completed the Gemma-only correction campaign but
failed the terminal long-run heldout gate: P13-H stopped after `1742 / 5000`
updates under thermal safety, full-heldout baseline/trained evals did not pass,
and no heldout KL improvement is promoted. Phase 14 repairs control-plane
truth, artifact hygiene, full-heldout evaluation, and objective quality before
any new hardware claim or long phone-local run.

## Contract Overview

| Contract Item | Advanced By Phase(s) | Status |
| --- | --- | --- |
| Formal PRD/GPD/branch/import policy | Phase 0 | Complete |
| G1 regression floor | Phase 1 and every material runtime phase | Passed, remained green through G7 changes |
| Phone-native training artifact | Phases 4-8 | G8 repaired and Phase 8 sustained objective passed |
| G10 falsifier survival | Phase 9 | Passed under narrow scope |
| Hardware-max pipeline search | Phase 10+ | First phone A/B candidate passed; ongoing |
| Hardware-native training POVC | Phase 11 | Complete under exact narrow H11-H claim |
| Expanded residual learning | Phase 12 | Complete with residual rank-16/rank-32 learning pass and falsified HTP/Gemma heterogeneous nonclaims |
| Gemma-only heterogeneous corpus-scale correction | Phase 13 | Completed with terminal P13-H failure and P13-I exact claims |
| Scaled heldout/objective repair | Phase 14 | P14-0 through P14-4 passed; objective repair next |

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
- [x] **Phase 7: Integrated Training** - Consume phone-packed batches in
  phone-side forward/backward/update and emit artifact manifest.
- [x] **Phase 8: Sustained Authority Run** - Six-hour or predeclared objective
  phone-native run.
- [x] **Phase 9: Falsifier Review** - Attack and resolve critical claim
  falsifiers before promotion.
- [ ] **Phase 10: Hardware Max Training Pipeline** - Test and integrate only
  performance candidates that improve measured phone training runs without
  regressing authority metrics.
- [x] **Phase 11: Hardware-Native Training POVC** - Run a sequential
  phone-resident experiment campaign for daemonization, performance envelope,
  bottleneck autopsy, recordable queues, trainable scope, objective upgrade,
  QAIRT/HTP mutable sections, and combined POVC.
- [x] **Phase 12: Hardware-Native Learning Correction** - Repair expanded
  residual-adapter learning, preserve compact artifact strategy, and falsify
  current QAIRT/HTP heterogeneous nonclaims without broadening claims.
- [x] **Phase 13: Gemma4-Only Heterogeneous Corpus-Scale Training** - Enforce
  Gemma-only artifact identity, scale phone-native HF corpus, expand gradient
  and multi-site evidence, and prove or falsify a Gemma-compatible
  heterogeneous path before any overnight long run. P13-H failed; P13-I exact
  claims selected Phase 14.
- [ ] **Phase 14: Repair Scaled Heldout Learning Before New Hardware Claims** -
  Clean worktree/control-plane drift, quarantine forbidden artifacts, reconcile
  Mac/phone/RunPod/GPD state, repair full-heldout evaluator and objective path,
  then prove a short thermally bounded phone-local heldout improvement before
  any segmented long run.

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

**Plans:** 1 failed attempt, 1 completed repair

Plans:

- [ ] 07-01: Attempt integrated streamed-corpus training.
  **Outcome:** rejected under falsification because the current training path
  still requires hidden-state fixtures. Next repair must generate
  `layer_input` and `per_layer_input` from phone-packed token IDs.
- [x] 07-02: Repair G8 with phone-native token-to-hidden bridge and streamed
  adapter update.
  **Outcome:** passed. Evidence:
  `runtime/reports/gemma4_megakernel/integrated_training/20260517T071405Z_g8_streamed_corpus_repaired/gate_result.json`.

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

**Plans:** 1 plan

Plans:

- [x] 08-01: Run predeclared three-batch chained phone-native training
  objective.
  **Outcome:** passed. Evidence:
  `runtime/reports/gemma4_megakernel/sustained_authority/20260517T071405Z_g9_three_batch_chain/gate_result.json`.

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

**Plans:** 1 plan

Plans:

- [x] 09-01: Run final G10 falsifier review.
  **Outcome:** passed under narrow scope. Evidence:
  `runtime/reports/gemma4_megakernel/falsifiers/20260517T082637Z_g10_final_falsifier_review/gate_result.json`.

### Phase 10: Hardware Max Training Pipeline

**Goal:** Let REDMAGIC/SM8750 measurements decide which bespoke training-pipeline
optimizations survive.
**Depends on:** Phase 9.
**Requirements:** NPU-01, VULK-01, CORP-01 follow-up requirements.
**Contract Coverage:**
- Advances: theoretical-maximum pursuit through falsifiable hardware-specific
  experiments.
- Deliverables: opt-in instrumentation, phone training A/B reports,
  accept/discard ledger, non-regression falsifier reports.
- Anchor coverage: G8/G9 authority path, G10 final falsifier, current external
  Snapdragon/Android analogue research.
- Forbidden proxies: throughput-only win, backend fallback, host-served data,
  or performance gain that regresses G1/G3/G8/G9 authority metrics.
**Success Criteria** (what must be TRUE):

1. Every optimization candidate is tested by an actual phone training run.
2. Authority metrics do not regress.
3. Accepted candidates improve a measured bottleneck and preserve artifact
   hygiene.
4. Discarded candidates record why they failed.

**Plans:** 1 completed first candidate, continuing backlog

Plans:

- [x] 10-01: Instrument HF-authenticated phone baseline and integrate projected
  PLE row cache.
  **Outcome:** passed. Token-to-hidden bridge improved from `4.232976s` to
  `0.667287s` while token cache, bridge tensors, layer outputs, adapter update,
  checkpoint, and artifact-hygiene gates stayed green. Evidence:
  `runtime/reports/gemma4_megakernel/hardware_max/20260517T084203Z_phase10_projected_ple_cache/gate_result.json`.
- [x] 10-02: Run six-hour endurance and remaining non-claim gates.
  **Outcome:** mixed. Six-hour endurance passed for the narrow rank-4 two-layer
  lane; Hexagon NPU training, full Gemma4 training, public benchmark readiness,
  and theoretical maximum remain blocked. Evidence:
  `.gpd/phases/10-hardware-max-training-pipeline/10-02-SUMMARY.md`.

### Phase 11: Hardware-Native Training POVC

**Goal:** Execute a phone-resident sequential POVC campaign that removes host
per-iteration orchestration, explains the Phase 10 dead time, tests safe device
performance controls, probes OpenCL recordable queues, lifts trainable scope,
replaces parity-MSE with a capability-relevant objective, classifies QAIRT/HTP
mutable-section use, and combines the winning choices into one phone-native
run.
**Depends on:** Phase 10.
**Requirements:** Phase 11 PRD contract in
`docs/PRD-HARDWARE-NATIVE-TRAINING-POVC.md`.
**Contract Coverage:**
- Advances: hardware-native training POVC for REDMAGIC/SM8750.
- Deliverables: phone queue runner, per-gate JSON reports, manifests, checksum
  chain, artifacts outside git where required, and falsifier report.
- Anchor coverage: G1/G3/G8/G9/Phase 10 evidence, research pack
  `08-OPUS-LEVEL-VIEW-AND-POVC.md`, QAIRT 2.44 mutable-section findings.
- Forbidden proxies: documentation-as-progress, host-driven per-iteration loop,
  throughput-only win, HTP inference sold as training, bigger adapter sold as
  capability without metric movement.
**Success Criteria** (what must be TRUE):

1. H11-A through H11-H each emit pass/fail/blocker artifacts.
2. ADB starts/inspects/pulls; it does not drive every training iteration after
   H11-A except as a documented fallback blocker.
3. Any promoted claim preserves G1/G3 and relevant G8 authority regressions.
4. The combined POVC emits replayable checkpoint or adapter manifests and a
   falsifier report with no unresolved critical issue.

**Plans:** 1 plan

Plans:

- [ ] 11-01: Execute Hardware-Native Training POVC campaign.
  **Plan:** `.gpd/phases/11-hardware-native-training-povc/11-01-PLAN.md`.
  **Current outcome:** H11-A phone-resident daemon passed with 50 phone-local
  queued iterations, active/wall `0.96051948`, checkpoint chain acceptance, and
  607 seconds of ADB-disconnect evidence. Evidence:
  `runtime/reports/gemma4_megakernel/hardware_native_povc/20260523T200929Z_h11a_daemon/H11-A-daemon/gate_result.json`.
  H11-B safe performance envelope failed; reversible controls were ineffective
  and baseline-safe profile carries forward. Evidence:
  `runtime/reports/gemma4_megakernel/hardware_native_povc/20260523T202629Z_h11b_perf_envelope/H11-B-perf-envelope/gate_result.json`.
  H11-C bottleneck autopsy passed with residual `0.365645667s/iter` and
  accounted fraction `0.952561994`; Phase 10 dead time is explained by
  host/process orchestration and repeated static artifact hashing. Evidence:
  `runtime/reports/gemma4_megakernel/hardware_native_povc/20260523T203448Z_h11c_bottleneck_autopsy/H11-C-bottleneck-autopsy/gate_result.json`.
  H11-D OpenCL recordable queue probe passed on Adreno 830: extension advertised,
  QCOM symbols resolved, property `0x40000000` accepted, no-op/fixed/mutable
  output comparisons passed, and best launch speedup was `1.968636098x`.
  Recordable queues are eligible for narrow A/B integration, not default
  end-to-end training. Evidence:
  `runtime/reports/gemma4_megakernel/hardware_native_povc/20260523T205951Z_h11d_recordable_queues/H11-D-recordable-queues/gate_result.json`.
  H11-E trainable scope sweep failed with the rank-4 baseline retained.
  Rank-16 and rank-32 trials completed with finite losses and changed
  checkpoints, but neither reduced loss over two phone-local daemon iterations;
  projection LoRA remains blocked by missing layer-internal backward kernels and
  checkpoint layout. Evidence:
  `runtime/reports/gemma4_megakernel/hardware_native_povc/20260523T211427Z_h11e_scope_sweep/H11-E-scope-sweep/gate_result.json`.
  H11-F objective upgrade passed narrowly with precomputed full-teacher top-k
  shards pushed to the phone before runtime. The 100-iteration phone-local train
  arm reduced top-k KL by `2.43e-7`; held-out KL and teacher top-1 probability
  improved versus fixed-adapter control by tiny deterministic amounts, with
  top-1 agreement unchanged. Evidence:
  `runtime/reports/gemma4_megakernel/hardware_native_povc/20260523T213836Z_h11f_objective_upgrade/H11-F-objective-upgrade/gate_result.json`.
  H11-G classified HTP as frozen-forward/teacher only. RunPod QAIRT 2.44 exposes
  and compiles the QNN apply-binary-section API, and the phone reran HTP
  inference successfully, but the active context reports zero updateable tensors;
  no mutable section or zero-order path is promoted. Evidence:
  `runtime/reports/gemma4_megakernel/hardware_native_povc/20260523T223147Z_h11g_htp_mutable_adapter/H11-G-htp-mutable-adapter/gate_result.json`.

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
| 7. Integrated Training | 1/2 | Complete after repaired G8 | 2026-05-17 |
| 8. Sustained Authority Run | 1/1 | Complete | 2026-05-17 |
| 9. Falsifier Review | 1/1 | Complete | 2026-05-17 |
| 10. Hardware Max Training Pipeline | 2/ongoing | Six-hour narrow endurance passed; remaining nonclaims blocked | - |
| 11. Hardware-Native Training POVC | 1/1 | H11-H completed under exact narrow POVC claim; no broad/full/benchmark claim | 2026-05-23 |
| 12. Hardware-Native Learning Correction | 1/1 | Residual rank-16/rank-32 learning passed narrowly; Qwen/random-init HTP contamination boundary recorded | 2026-05-24 |
| 13. Gemma4-Only Heterogeneous Corpus-Scale Training | 1/1 | P13-A through P13-G produced narrow artifacts; P13-H failed; P13-I exact claims written | 2026-05-25 |
| 14. Repair Scaled Heldout Learning Before New Hardware Claims | 0/1 | P14-0 through P14-4 passed without training; P14-5 objective repair next | - |
