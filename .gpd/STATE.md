# Research State

## Project Reference

See: `.gpd/PROJECT.md` (updated 2026-05-17)

**Machine-readable scoping contract:** `.gpd/state.json` field
`project_contract`

**Core research question:** Can Polymath-AI execute and validate a real Gemma 4
training run natively on REDMAGIC SM8750 without substituting Mac or RunPod for
any runtime data-path stage?
**Current focus:** Phase 14: repair scaled heldout learning before new hardware claims

## Current Position

**Current Phase:** 14
**Current Phase Name:** Repair Scaled Heldout Learning Before New Hardware Claims
**Total Phases:** 14
**Current Plan:** 1
**Total Plans in Phase:** 1
**Status:** Phase 14 P14-0 through P14-3 passed without training; P14-4 heldout evaluator repair and P14-5 objective repair remain next.
**Last Activity:** 2026-05-25
**Last Activity Description:** P14-3 passed at runtime/reports/gemma4_megakernel/phase14_drift_cleanup/20260525T164328Z_phase14_drift_cleanup/P14-3-state-reconciliation/gate_result.json. Mac and GitHub are reconciled on gemma4-megakernel-native-training, RunPod stale workspace remains quarantined, clean RunPod Phase 14 worktree is detached at the reconciled commit, ADB still sees FY25013101C8, and no training was launched.

**Progress:** [#########-] 94%

## Active Calculations

- Execute Phase 14 in gate order. P14-0 through P14-3 are passed; no training
  may launch until full-heldout evaluator repair, objective repair, and the
  short proof scope are coherent.
- Repair the authority path before any long run: P14-1 phone reconnection and
  thermal/process baseline, P14-2 compact artifact manifest repair, P14-3
  Mac/RunPod/GitHub/GPD reconciliation, P14-4 independent full-heldout
  evaluator repair, P14-5 stronger Gemma teacher/objective repair, P14-6 short
  thermally bounded phone-local heldout proof, then P14-7 segmented long run.
- Current truth: P13-H failed; P13-I exact claims are authoritative; the P13-F
  HTP ReLU island is execution-only; residual-adapter OpenCL training is not a
  fused megakernel; train-loss movement cannot replace full-heldout movement.

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
- H11-C bottleneck autopsy passed:
  `runtime/reports/gemma4_megakernel/hardware_native_povc/20260523T203448Z_h11c_bottleneck_autopsy/H11-C-bottleneck-autopsy/gate_result.json`.
  A 30-iteration daemon trial accounted for `95.2561994%` of wall time with
  residual `0.365645667s/iter`. Phase 10 dead time is explained by
  host/process orchestration and repeated static artifact hashing; the repaired
  daemon path leaves residual below the PRD threshold.
- H11-D OpenCL recordable queue probe passed:
  `runtime/reports/gemma4_megakernel/hardware_native_povc/20260523T205951Z_h11d_recordable_queues/H11-D-recordable-queues/gate_result.json`.
  The selected Adreno 830 driver advertises `cl_qcom_recordable_queues`, accepts
  recordable queue property `0x40000000`, resolves QCOM recording functions,
  and passes no-op, fixed-arg, and mutable-arg output comparisons. Recordable
  queues are eligible for narrow A/B use only; H11-H must still prove any
  end-to-end relevance.
- H11-E trainable scope sweep failed with the rank-4 baseline retained:
  `runtime/reports/gemma4_megakernel/hardware_native_povc/20260523T211427Z_h11e_scope_sweep/H11-E-scope-sweep/gate_result.json`.
  The first H11-E attempt is preserved as an implementation failure:
  `runtime/reports/gemma4_megakernel/hardware_native_povc/20260523T211134Z_h11e_scope_sweep/H11-E-scope-sweep/gate_result.json`.
  Rank-4 completed two phone-local daemon iterations with finite losses
  `[1.6465152695, 1.6465152694]`, changed checkpoint, active seconds
  `12.500036`, and loss delta per active second `7.999977622e-12`. Rank-16 and
  rank-32 completed with finite losses and changed checkpoints but zero
  two-iteration loss reduction, so no expanded rank crossed the promotion gate.
  Projection LoRA across q/o/gate/up projections remains `blocked_not_promoted`
  because layer-internal backward kernels and checkpoint layout are not present.
- H11-F objective upgrade passed narrowly:
  `runtime/reports/gemma4_megakernel/hardware_native_povc/20260523T213836Z_h11f_objective_upgrade/H11-F-objective-upgrade/gate_result.json`.
  Teacher shards were generated on RunPod before phone runtime and pushed to the
  phone; no runtime teacher service was used. The 100-iteration train arm
  reduced `loss_topk_kl` from `1.3055719031` to `1.3055716601`
  (`2.43e-7`). Held-out fixed control had KL `1.1291671114` and teacher top-1
  probability `0.1137876831`; trained held-out eval had KL `1.12916688` and
  teacher top-1 probability `0.1137876981`, with top-1 agreement unchanged at
  `0.093637455`. This promotes only the top-k KL objective path for later
  Phase 11 gates, not broad capability or benchmark readiness.
- H11-G HTP mutable-adapter / zero-order arm classified HTP as
  frozen-forward/teacher only:
  `runtime/reports/gemma4_megakernel/hardware_native_povc/20260523T223147Z_h11g_htp_mutable_adapter/H11-G-htp-mutable-adapter/gate_result.json`.
  Phone QAIRT 2.44 `qnn-net-run` completed one HTP inference on
  `qwen_block.qnn.bin`, and RunPod compiled a QNN apply-binary-section API probe
  against QAIRT 2.44 headers. However, phone `qnn-context-binary-utility`
  reported `numUpdateableTensors = 0` for the active context, so there was no
  valid section to apply and no legitimate SPSA/MeZO perturbation target.
  Mutable-section, zero-order, and normal HTP backprop claims remain blocked.
- H11-H combined POVC passed under exact narrow scope:
  `runtime/reports/gemma4_megakernel/hardware_native_povc/20260523T225149Z_h11h_combined_povc/H11-H-combined-povc/gate_result.json`.
  The promoted claim is phone-local Gemma4 E4B two-layer rank-4 top-k KL
  residual adapter training, not full Gemma4 training, benchmark readiness, or
  heterogeneous learning.
- Phase 12 final exact claims resolved by pass/falsify/fallback artifacts:
  `runtime/reports/gemma4_megakernel/phase12_hardware_native_learning/20260524T175056Z_phase12_final_exact_claims/phase12_gate_status.json`.
  Residual rank-16/rank-32 post-layer0 adapters with AdamW/clipping and
  phone-local queue execution passed. Rank-16 LR `3e-4` continuation improved
  heldout KL from `1.0005755997` to `0.8207082971`, mini metric from
  `0.1233203377` to `0.1625584151`, and agreement from `0.1140456182` to
  `0.2244897959`.
- Phase 12 also exposed a hard contamination boundary: Qwen/random-init
  hidden-size-1536 HTP artifacts are invalid for Gemma4 hidden-size-2560
  heterogeneous claims and may only be used as isolated negative tool-surface
  probes.
- Phase 13 authority PRD and executor handoff were written:
  `docs/PRD-PHASE13-GEMMA4-ONLY-HETEROGENEOUS-CORPUS-SCALE.md`,
  `docs/HANDOFF-PHASE13-GEMMA4-ONLY-HETEROGENEOUS-EXECUTOR.md`, and
  `docs/STARTUP-PROMPT-PHASE13-GEMMA4-ONLY-HETEROGENEOUS.md`.
  Phase 13 GPD plan:
  `.gpd/phases/13-gemma4-only-heterogeneous-corpus-scale/13-01-PLAN.md`.
- P13-A contamination audit passed:
  `runtime/reports/gemma4_megakernel/phase13_gemma4_only_heterogeneous/20260524T210920Z_phase13_gemma4_only_heterogeneous/P13-A-contamination-audit/gate_result.json`.
  The audit found no raw payloads in the Phase 12 report tree, validated
  `.gpd/state.json`, classified `cde`, `gradient_parity`, `long_native_lr`, and
  `preflight` as Gemma-valid narrow/control evidence, and classified `qairt_f`
  and `heterogeneous_g` as forbidden for promoted Gemma gates.
- P13-B Gemma identity/kernel-lineage instrumentation passed:
  `runtime/reports/gemma4_megakernel/phase13_gemma4_only_heterogeneous/20260524T210920Z_phase13_gemma4_only_heterogeneous/P13-B-identity-kernel-lineage/gate_result.json`.
  The valid phone smoke emitted `model_id=google/gemma-4-E4B`, revision
  `7aa32e6889efd6300124851b164f8b364314c3d8`, hidden size `2560`,
  runner binary SHA `1dbb56566ba0119db01e5e4a6898cc56dd7f838bbc4154b896c9ba4252ab63a4`,
  and kernel lineage `residual_adapter_opencl_training`. A deliberate
  `Qwen/Qwen2.5-1.5B` hidden-size-1536 config failed before training.

## Open Questions

- Whether the phone can build and sustain a material HF-streamed Gemma corpus
  cache at minimum `8192/1024` train/heldout seq128 scale.
- Whether residual rank-16/rank-32 gradient correctness survives a sampled
  parity sweep beyond two high-gradient coordinates.
- Whether a real second Gemma-compatible trainable site can be implemented
  without host gradients or tensor semantic drift.
- Whether a Gemma hidden-size-2560 HTP context can be built, or whether HTP
  must be temporarily abandoned for Gemma learning.
- Whether any true heterogeneous candidate beats the Adreno/OpenCL baseline on
  identical corpus/objective after transfer cost and correctness are included.

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
| H11-C residual | `0.365645667s/iter` | 30-iteration daemon autopsy | passed; accounted fraction `0.952561994` |
| H11-D recordable queue launch | `1.968636098x` best speedup | 100 no-op/fixed/mutable OpenCL dispatches | passed; mutable output `300 == 300`, property `0x40000000` |
| H11-E rank-4 loss delta | `1.000000082740371e-10` | two phone-local daemon iterations | retained baseline; loss delta per active second `7.999977622e-12` |
| H11-E expanded rank loss delta | `0.0` | rank-16 and rank-32 scope trials | failed promotion despite finite losses and changed checkpoints |
| H11-F train top-k KL delta | `2.429999998998511e-7` | 100 phone-local train iterations | passed narrow objective signal |
| H11-F held-out top-k KL | `1.1291671114 -> 1.12916688` | fixed-adapter control vs trained held-out eval | non-regression with tiny improvement |
| H11-F held-out teacher top-1 probability | `0.1137876831 -> 0.1137876981` | instruction-format held-out shard | tiny improvement; top-1 agreement unchanged |
| H11-G active QNN updateable tensors | `0` | `qwen_block.qnn.bin` via phone `qnn-context-binary-utility` | mutable-section and zero-order blocked |
| H11-G HTP inference | `1` completed inference | phone QAIRT 2.44 `qnn-net-run` on `qnn_partition_0` | frozen-forward/teacher role only |

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

- Keep all forbidden payloads outside the commit path.
- P14-4: make full-heldout baseline/trained evaluation runnable independently
  before any new long training campaign.
- P14-5: decide whether full Gemma teacher top-k/logit-KL shards are feasible
  from the P13-C phone-defined corpus using RunPod only as offline oracle; if
  infeasible, document the boundary and stronger fallback falsifiers.
- Treat Phase 12 promoted learning as residual rank-16 post-layer0 only. Full
  Gemma4 training, multi-site adapter training, HTP backprop, updateable QNN
  application, benchmark readiness, and broad capability remain nonclaims.

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
- H11-C does not claim all remaining residual is categorized; it passes because
  residual is below `5s/iter` and the dominant Phase 10 dead-time source was
  falsified by repair evidence.
- H11-D does not claim end-to-end training speedup. It proves OpenCL extension
  support, mutable-arg correctness, and launch-level benefit; later gates may
  use recordable queues only through narrow A/B evidence.
- H11-E does not promote rank-16, rank-32, or projection LoRA. Expanded ranks
  were finite and mutable but did not reduce loss over two iterations; projection
  LoRA remains blocked until layer-internal backward kernels and checkpoint
  layout exist.
- H11-F promotes only a narrow top-k KL objective path. The measured held-out
  improvement is deterministic but tiny; do not describe it as public benchmark
  readiness, full Gemma4 training, or a broad capability result.
- H11-G does not promote mutable QAIRT sections or HTP zero-order training. The
  active QNN context has zero updateable tensors, and RunPod x86 LoRA tooling is
  not fully runnable in the current shell environment (`onnx`/`pydantic` and
  `libc++.so.1` gaps). HTP may only be used as frozen-forward/teacher evidence
  unless a later context is compiled with updateable tensors and applied on
  phone.
- H11-H promoted only the exact combined narrow POVC claim captured in
  `runtime/reports/gemma4_megakernel/hardware_native_povc/20260523T225149Z_h11h_combined_povc/H11-H-combined-povc/gate_result.json`;
  it was not a broad training or benchmark win.
- Phase 12 Gate C/D/E promoted residual rank-16/rank-32 expanded-scope AdamW
  top-k KL training from a phone-native HF-derived token cache. The strongest
  follow-up selected rank-16 LR `3e-4` continuation: heldout KL improved from
  `1.0005755997` to `0.8207082971`, mini metric from `0.1233203377` to
  `0.1625584151`, and agreement from `0.1140456182` to `0.2244897959`.
- Phase 12 gradient parity is single-parameter finite-difference evidence only:
  high-gradient `adapter_a` and `adapter_b` probes matched phone gradients with
  relative errors below `2e-6`. This is not full-gradient or multi-site parity.
- Phase 12 Gate F falsified the updateable QNN path for current artifacts:
  QAIRT host tools ran, but generated updateable contexts were rejected before a
  phone `QnnContext_applyBinarySection` proof. Gate G falsified integrated
  heterogeneous Gemma learning because the measured HTP frozen-forward context
  is Qwen/random-init hidden-1536 and incompatible with the Gemma hidden-2560
  training island.
- Phase 13 forbids non-Gemma artifacts inside promoted Gemma gates. Any Qwen,
  SmolLM, random-init, hidden-size mismatch, or artifact not bridged into the
  Gemma runtime is an immediate failure and can only be retained as a negative
  tool-surface probe.
- Phase 13 requires real corpus scale before learning promotion. A 16-sequence
  cache is a smoke test only, not a corpus-scale learning gate.
- P13-C scaled phone-native HF corpus passed: `runtime/reports/gemma4_megakernel/phase13_gemma4_only_heterogeneous/20260524T210920Z_phase13_gemma4_only_heterogeneous/P13-C-phone-native-hf-corpus/gate_result.json`. The phone streamed `databricks/databricks-dolly-15k` revision `bdd27f4d94b9c1f951818a7da7fd7aeea5dbff1a`, built `8192` train / `1024` heldout seq`128` caches with native C++ Gemma BPE, and RunPod Transformers parity passed on `3` rows. Host minibatch serving remained false.
- P13-D expanded gradient parity passed: `runtime/reports/gemma4_megakernel/phase13_gemma4_only_heterogeneous/20260524T210920Z_phase13_gemma4_only_heterogeneous/P13-D-expanded-gradient-parity/gate_result.json`. Seeded phone finite-difference checks covered `64` residual-adapter coordinates across rank16/rank32, adapter A/B, and init/final checkpoint states; max relative error `1`, max absolute error `6.73384e-08`.
- P13-E second Gemma-compatible adapter site passed: `runtime/reports/gemma4_megakernel/phase13_gemma4_only_heterogeneous/20260524T210920Z_phase13_gemma4_only_heterogeneous/P13-E-layer1-adapter-site/gate_result.json`. A post-layer1 rank16 residual adapter ran phone-side forward/backward/update, passed `8` finite-difference checks, and preserved G1/G3/G8/post-layer0 smoke paths.
- P13-F passed at runtime/reports/gemma4_megakernel/phase13_gemma4_only_heterogeneous/20260524T210920Z_phase13_gemma4_only_heterogeneous/P13-F-gemma-compatible-htp-context/gate_result.json: phone QAIRT generated and executed a Gemma hidden-size-2560 HTP context from a megakernel layer0 hidden tensor; selected HTP island=relu. This proves only Gemma-compatible HTP execution, not HTP backprop or heterogeneous learning.
- P13-G heterogeneous comparison completed: `runtime/reports/gemma4_megakernel/phase13_gemma4_only_heterogeneous/20260524T210920Z_phase13_gemma4_only_heterogeneous/P13-G-heterogeneous-vs-adreno-baseline/gate_result.json`. Gemma hidden-2560 HTP ReLU execution is valid as an execution-only island, but it is not consumed by training and has no heldout improvement; P13-H used the Adreno/OpenCL post-layer0 rank16 lr3e-4 fallback.
- P13-H failed: `runtime/reports/gemma4_megakernel/phase13_gemma4_only_heterogeneous/20260524T210920Z_phase13_gemma4_only_heterogeneous/P13-H-overnight-phone-local-long-run/gate_result.json`. The phone-local chain stopped after `1742 / 5000` updates under thermal safety. Full-heldout baseline and trained eval did not pass, full-heldout KL delta is `None`, and no full-heldout learning claim is promoted.
- P13-I exact claims were written: `runtime/reports/gemma4_megakernel/phase13_gemma4_only_heterogeneous/20260524T210920Z_phase13_gemma4_only_heterogeneous/P13-I-exact-claims-and-next-branch/gate_result.json`. Next branch is `phase14_repair_scaled_heldout_learning_before_new_hardware_claims`.
- P14-0 live control-plane snapshot: Mac is on `gemma4-megakernel-native-training`, ADB sees `FY25013101C8`, RunPod `/workspace/Polymath-AI` is quarantined as stale on `linux/phase0g-qairt-v2.43`, and forbidden raw/bin/build-cache artifacts were moved to `/Users/Zer0pa/Polymat AI/.artifact_quarantine/Polymath-AI/20260525T164328Z_phase14_p14_0`.
- P14-1 phone baseline passed: `runtime/reports/gemma4_megakernel/phase14_drift_cleanup/20260525T164328Z_phase14_drift_cleanup/P14-1-phone-thermal-process-baseline/gate_result.json`. ADB sees `FY25013101C8`; no stale runner matched; thermalservice status is `0`; battery is `28.0 C`; storage/memory are adequate; RedMagic Game Zone packages and Termux are present, but no activation or authority claim was made.
- P14-2 artifact quarantine and compact manifest repair passed: `runtime/reports/gemma4_megakernel/phase14_drift_cleanup/20260525T164328Z_phase14_drift_cleanup/P14-2-artifact-quarantine-compact-manifest-repair/gate_result.json`. P13-G forbidden raw/bin payloads remain outside the repo and `P13-G-heterogeneous-vs-adreno-baseline/artifact_manifest.json` has compact quarantine metadata with no forbidden payload entries in its `artifacts` list.
- P14-3 Mac/RunPod/GitHub/GPD reconciliation passed: `runtime/reports/gemma4_megakernel/phase14_drift_cleanup/20260525T164328Z_phase14_drift_cleanup/P14-3-state-reconciliation/gate_result.json`. Mac/GitHub reconciled on `gemma4-megakernel-native-training`, clean RunPod worktree `/workspace/Polymath-AI-phase14-gemma4` is detached at the reconciled commit for offline-oracle work, stale `/workspace/Polymath-AI` remains quarantined, and forbidden payload scans are clean.

## Session Continuity

**Last session:** 2026-05-25
**Stopped at:** Phase 14 P14-3 Mac/RunPod/GitHub/GPD reconciliation.
Do not launch training until P14-4 heldout evaluator repair and P14-5
objective repair are complete and P14-6 short proof is explicitly scoped.
**Resume file:** `.gpd/STATE.md`
