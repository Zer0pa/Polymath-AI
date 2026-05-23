# Research State

## Project Reference

See: `.gpd/PROJECT.md` (updated 2026-05-17)

**Machine-readable scoping contract:** `.gpd/state.json` field
`project_contract`

**Core research question:** Can Polymath-AI execute and validate a real Gemma 4
training run natively on REDMAGIC SM8750 without substituting Mac or RunPod for
any runtime data-path stage?
**Current focus:** Phase 11: Hardware-native training POVC execution campaign

## Current Position

**Current Phase:** 11
**Current Phase Name:** Hardware-Native Training POVC
**Total Phases:** 12
**Current Plan:** 1
**Total Plans in Phase:** 1
**Status:** H11-A phone-resident daemon passed; H11-B safe performance envelope failed; H11-C bottleneck autopsy next
**Last Activity:** 2026-05-23
**Last Activity Description:** Ran H11-B safe performance-envelope probe under the passed H11-A daemon. Reversible controls (`low_power=0`, USB stay-awake, fixed-performance mode request) were applied and reverted, but the profile did not improve daemon throughput by the required 15 percent and cooling-device state was nonzero throughout. H11-B is failed with baseline-safe fallback; proceed to H11-C bottleneck autopsy.

**Progress:** [#########-] 92%

## Active Calculations

- Execute Phase 11 only through phone-resident queue-run experiments with
  authority non-regression gates and artifact hygiene.
- Sequential hypotheses: H11-A daemon, H11-B performance envelope, H11-C
  bottleneck autopsy, H11-D OpenCL recordable queues, H11-E trainable scope
  sweep, H11-F objective upgrade, H11-G HTP mutable-adapter/zero-order arm,
  H11-H combined POVC run.

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
- Phase 9 final falsifier review passed under narrow scope:
  `runtime/reports/gemma4_megakernel/falsifiers/20260517T082637Z_g10_final_falsifier_review/gate_result.json`.
- Phase 10 HF-authenticated baseline passed with token bridge split telemetry:
  `runtime/reports/gemma4_megakernel/hardware_max/20260517T083219Z_phase10_hf_auth_token_bridge_baseline/gate_result.json`.
- Phase 10 projected PLE cache passed and was promoted for the narrow current
  training path:
  `runtime/reports/gemma4_megakernel/hardware_max/20260517T084203Z_phase10_projected_ple_cache/gate_result.json`.
- Phase 10 six-hour endurance passed for the current rank-4 two-layer phone
  training path:
  `runtime/reports/gemma4_megakernel/hardware_max/20260517T153500Z_phase10_six_hour_endurance/gate_result.json`.
- Phase 10 QNN/HTP probe passed platform and inference checks but failed the
  Hexagon training promotion gate:
  `runtime/reports/gemma4_megakernel/hardware_max/20260517T213600Z_phase10_qnn_htp_probe/gate_result.json`.
- Phase 10 non-claim summary remains failed overall: only six-hour endurance is
  resolved; full Gemma4 training, Hexagon NPU training, public benchmark
  readiness, and theoretical maximum remain blocked:
  `runtime/reports/gemma4_megakernel/hardware_max/20260517T214000Z_phase10_nonclaim_gate/gate_result.json`.
- Latest research synthesis reframed the next campaign:
  `docs/research-packs/gemma4-heterogeneous-training-frontier-2026-05-18/08-OPUS-LEVEL-VIEW-AND-POVC.md`.
- Phase 11 authority PRD and execution handoff were written:
  `docs/PRD-HARDWARE-NATIVE-TRAINING-POVC.md`,
  `docs/HANDOFF-HARDWARE-NATIVE-TRAINING-POVC-EXECUTOR.md`, and
  `docs/STARTUP-PROMPT-HARDWARE-NATIVE-TRAINING-POVC.md`.
- Phase 11 GPD execution plan was scaffolded:
  `.gpd/phases/11-hardware-native-training-povc/11-01-PLAN.md`.
- Phase 11 executor controls were hardened for long-horizon campaign execution:
  no stopping after intermediate wins, exact pass/fail/blocker cadence after
  each H11 gate, targeted subagent/falsification decision rules, RunPod
  alternate SSH, and no minimized-proxy language in HTP probing.
- H11-A initially failed because the daemon still paid a repeated static
  artifact hashing tax inside every compact iteration:
  `runtime/reports/gemma4_megakernel/hardware_native_povc/20260523T193156Z_h11a_daemon/H11-A-daemon/gate_result.json`.
  The failure was preserved, then repaired by hashing static assets once in
  `daemon_static_artifact_manifest.json` and referencing those hashes from
  compact daemon iteration manifests.
- H11-A phone-resident daemon passed:
  `runtime/reports/gemma4_megakernel/hardware_native_povc/20260523T200929Z_h11a_daemon/H11-A-daemon/gate_result.json`.
  The phone executed 50 queued narrow-lane iterations inside one long-lived
  runner process with local queue, heartbeat, STOP/resume state, checksum
  chain, checkpoint continuity, and ADB-disconnect evidence.
- H11-B safe performance envelope failed:
  `runtime/reports/gemma4_megakernel/hardware_native_povc/20260523T202629Z_h11b_perf_envelope/H11-B-perf-envelope/gate_result.json`.
  Reversible controls were accepted/reverted, but profile throughput improved
  only `0.016502977` and active/wall regressed slightly from `0.93996256` to
  `0.93758804`; cooling-device state remained nonzero. Baseline-safe profile is
  carried into H11-C.

## Open Questions

- Whether Android permits the phone-resident runner to continue reliably after
  ADB/USB disconnect, and what resume behavior is needed if it does not.
- Whether safe fixed performance mode, charge separation, fan state, and OEM
  controls materially improve active/wall without unsafe thermal behavior.
- Whether cl_qcom_recordable_queues is exposed on this Adreno 830 driver and
  useful after H11-C identifies the real bottleneck.
- Which expanded DoRA/LoRA scope and objective produces a capability-relevant
  signal beyond the rank-4 parity lane.
- Whether QAIRT mutable sections can become an HTP teacher/frozen-forward or
  zero-order arm without claiming normal HTP backprop.

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
| Phase 9 final falsifier | pass | no failed checks | Narrow rank-4 two-layer distillation adapter claim only |
| Phase 10 baseline token bridge | `4.232976s` | 796 active tokens, 285 unique token IDs | HF-auth phone training run |
| Phase 10 projected PLE cache | `0.667287s` | token-to-hidden bridge | `6.343561316195281x` speedup, all parity gates pass |
| Phase 10 six-hour endurance | `21692.164205625013s` | 465 chained phone training iterations | sampled parity pass; max thermal status `0` |
| Phase 10 active/wall | `4626.645587 / 21692.164205625013 = 21.3%` | current narrow lane | suspected host orchestration plus OEM mitigation |
| Phase 10 dead time | `36.70s/iteration` | 465 iterations | H11-C must explain |
| H11-A daemon active/wall | `527.878356 / 549.575899 = 0.96051948` | 50 phone-local daemon iterations | passed after static-hash repair |
| H11-A disconnect evidence | `607s` | ADB server hold after marker | passed; runner heartbeat/state/checksum finalized on phone |
| H11-B throughput delta | `+1.6502977%` | 12-iteration baseline vs fixed-performance/stay-awake profile | failed required `>=15%`; controls reverted |

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
- Phase 11: Documentation is only a control artifact; execution progress begins
  only when H11 gate artifacts are produced by phone experiments.

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

- Execute H11-C next under the H11-A daemon and H11-B baseline-safe fallback:
  instrument one-shot and daemon timing for compute, launch/context, token
  bridge, checkpoint, manifest/static hashing, validation, storage, host pull,
  and idle residual.
- Preserve H11-A runner topology for later gates; do not return to host-driven
  per-iteration training except as a declared diagnostic fallback.
- Do not run H11-H or another long endurance job until H11-B through H11-G have
  pass/fail/blocker artifacts or exact boundary blockers.

### Blockers/Concerns

- Formal GPD one-shot project writer is not exposed by the installed CLI; the
  contract validator and state persistence commands are available and were used.
- Phase 8 passed a predeclared three-batch objective, but it is not a six-hour
  endurance proof and must not be narrated as one.
- Phase 9 promotion is narrow only: rank-4 post-layer0 residual adapter,
  two-layer distillation path, phone token cache, OpenCL layers/adapter, and
  checkpoint chain. It is not full Gemma 4 training.
- Phase 10 promotes projected PLE caching and six-hour wall-clock endurance for
  the current narrow route only. It is not Hexagon NPU training, full Gemma4
  training, public benchmark readiness, or theoretical maximum reached.
- GPD phase-add succeeded for Phase 11, but generic GPD state synchronization
  rewrote `.gpd/state.json` in a lossy parser format during this PRD-writing
  task. The machine state was restored and updated via structured JSON; future
  agents should parse-check `.gpd/state.json` after GPD CLI state commands.
- H11-A does not claim OpenCL context persistence across iterations; the runner
  process persists and removes host per-iteration orchestration. Deeper context,
  queue, launch, and storage accounting remains H11-C/H11-D work.
- H11-B does not promote fixed-performance or USB stay-awake as a winning
  profile. Controls were reversible but ineffective; proceed with the baseline
  profile until H11-C identifies a measured bottleneck.

## Session Continuity

**Last session:** 2026-05-23
**Stopped at:** H11-B performance envelope failed with baseline-safe fallback.
Continue with H11-C bottleneck autopsy under the H11-A runner; do not skip to
H11-H.
**Resume file:** `.gpd/STATE.md`
