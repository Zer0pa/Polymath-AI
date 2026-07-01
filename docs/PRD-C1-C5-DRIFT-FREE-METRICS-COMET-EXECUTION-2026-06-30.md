# PRD: C1-C5 Drift-Free Metrics, Comet Visibility, And Integrated Mobile Training Execution

Date: 2026-06-30

Owner: Executive Orchestrator / Watcher-Driver

Working repo: `/Users/Zer0pa/Polymat AI/Polymath-AI`

Primary execution runtime: REDMAGIC/Nubia phone SoC, with Phase3 on HTP/NPU path and Phase4 on Adreno/OpenCL path.

## 1. Sovereign Objective

Deliver a drift-free, measurable, reproducible C1 -> C2 -> C2.5 -> C3 -> C4 curriculum execution path through Phase1 -> Phase2 -> Phase3 -> Phase4, with C5 as the evaluation boundary after every curriculum phase and after the full curriculum. The system must prove what happened with immutable code identity, immutable material identity, per-phase metrics, Comet visibility, and falsification-first gates.

The target is not a narratable success. The target is a pipeline that can answer, with evidence:

- Which code ran?
- Which dataset revision ran?
- Which binary produced Phase2?
- Did every phase log metrics that can detect failure?
- Did C5 improve against the last stable checkpoint without gradient blow-up, overfitting, throughput collapse, or hidden drift?
- Where is the next bottleneck, and which lane owns it?

## 2. Nonclaims

Until the gates in this PRD pass, do not claim:

- model learning,
- model quality,
- Phase3 readiness,
- Phase4 readiness,
- 100k/1M Phase2 authority,
- production training readiness,
- external reproducibility,
- or that a local diagnostic replaces the authority metric.

Existing integrated C1-C4 evidence is a strong development-cycle diagnostic. It is not enough for stronger claims until drift is eliminated and metrics are logged.

## 3. Governing Evidence

Current integrated run:

- Exec label: `c1_c4_integrated_20260630T164809Z`
- Final report: `/Users/Zer0pa/Polymat AI/Polymath-AI/runtime/reports/integrated_c1_c4_execution/c1_c4_integrated_20260630T164809Z/FINAL_INTEGRATED_C1_C4_EXECUTION_METADATA_REPORT.md`
- External review README: `/Users/Zer0pa/Polymat AI/Polymath-AI/runtime/reports/integrated_c1_c4_execution/c1_c4_integrated_20260630T164809Z/EXTERNAL_REVIEW_README.md`
- External review packet manifest: `/Users/Zer0pa/Polymat AI/Polymath-AI/runtime/reports/integrated_c1_c4_execution/c1_c4_integrated_20260630T164809Z/EXTERNAL_REVIEW_PACKET_MANIFEST.json`

Known drift blockers from the packet manifest:

- HF material revision was recorded as `main`, a moving branch.
- Repo worktree was dirty/untracked at review packaging time.
- Phase2 packetizer binary hash was captured, but Termux-side source and build-script hashes were not captured in the integrated summary.

These are not paperwork issues. They are authority blockers.

## 4. Product Definition

This PRD defines the next product increment: a drift-free metrics-instrumented curriculum execution system.

The output is not just another report. The output is:

1. Immutable dataset identity.
2. Immutable code identity.
3. Phase2 binary/source/build reconciliation.
4. One canonical runner/helper surface per phase.
5. Per-phase metrics for Phase1, Phase2, Phase3, Phase4.
6. C5 evaluation after C1, C2, C2.5, C3, C4, and after the full run.
7. Comet experiments with comparable run metrics.
8. End-to-end throughput and per-phase latency breakdown.
9. External review packet v2 that can be audited without raw payloads in git.

## 5. Team Lanes

| Lane | Thread | Authority |
|---|---|---|
| Executive Orchestrator / Watcher-Driver | current orchestration thread | Owns objective, active cadence, lane routing, status board, blocker escalation, and anti-drift enforcement. |
| Repo Custodian | `019f1ac2-0f0f-7721-bf46-ad402dbd9050` | Owns clean commit, pathset discipline, raw-payload exclusion, canonical runner map, and drift cleanup. |
| Training Material Steward | `019f138b-7bfc-7671-b9fc-22c14ab76342` | Owns HF material revision pin, C1-C4 source authority, C4 expansion, C5 eval material, and material nonclaims. |
| Engineering Orchestrator | `019f138b-d229-7640-98b7-2f185d6beae0` | Owns repo-owned metric instrumentation and runner/helper changes. |
| Pipeline Integrator | `019f138c-35b6-73e1-b26d-3db8c59cf850` | Owns metric schema integration, Phase1-4 continuity, Comet contract, and cross-phase artifact schema. |
| Execution Orchestrator | `019f138c-fb51-7c53-a41a-ab8eac950d9c` | Owns phone/Termux execution only after gates go green, including Phase2 identity recovery and rerun evidence. |
| UI Engineer | `019f138c-8d85-7141-a813-66db51c62b3d` | Owns local/Comet-facing visibility surfaces, summary dashboards, and reviewer ergonomics. |
| Phase3/4 Engineer | `019f13da-d897-7ba2-8ed1-b959892f5ed4` | Owns HTP/OpenCL metric capture, loss/gradient surfaces, and Phase3/4 performance bottleneck repairs. |

No lane may convert a partial local win into a sovereign pass.

## 6. Execution Sequence

### Stage 0: Freeze And Reconcile Before New Claims

This stage runs in parallel, but all outputs must pass before any new authority claim.

| Workstream | Owner | Required Output | Pass Gate | Blocker |
|---|---|---|---|---|
| Dataset freeze | Training Material Steward | `material_revision_lock.json` and updated `material_verification.json` with immutable HF commit SHA, not `main` | Every C1-C4 path, row count, QA SHA, manifest SHA resolves at immutable HF revision | Any moving branch, missing SHA stream, or mismatch |
| Code freeze | Repo Custodian | Clean commit or complete code-hash manifest for exact execution source state | Branch + HEAD or hash manifest is immutable and raw payload scan is clean | Dirty/untracked execution source with no accepted hash manifest |
| Phase2 identity | Execution + Pipeline Integrator | `phase2_binary_identity_reconciliation.json` | Packetizer binary SHA, Termux source SHA, Termux build-script SHA, host source SHA, rebuild command, and comparison result recorded | Binary/source/build mismatch without explanation |
| Drift cleanup audit | Repo Custodian + Engineering | `canonical_execution_surface_map.md` and `drift_cleanup_plan.json` | One canonical runner/helper per phase or explicit quarantine with no active execution route | Temp scripts, duplicate runners, or local hacks remain callable without ownership |

Stage 0 exit condition: `drift_status=green`.

### Stage 1: Metrics Schema And Comet Contract

This stage creates one metric vocabulary shared across phases. Local JSON is required. Comet logging is required for accepted metric runs.

Required outputs:

- `runtime/reports/orchestration/c1_c5_metric_schema.json`
- `runtime/reports/orchestration/comet_logging_contract.md`
- `runtime/reports/orchestration/c5_eval_contract.md`

Comet requirements:

- One Comet experiment per integrated run.
- Experiment name format: `polymath_<run_label>`.
- Tags: `polymath`, `mobile_soc`, `c1_c5`, `phase1`, `phase2`, `phase3`, `phase4`, `c5_eval`, plus corpus phase tags.
- Parameters: immutable HF revision, repo HEAD or code manifest SHA, phone model, Android API, HTP backend path, OpenCL device, Phase2 binary/source/build hashes.
- Metrics: every metric name must include phase family and corpus phase, for example `phase2/C3/collision_rate` or `c5/after_C4/loss_delta_vs_stable`.
- Assets: metadata JSON only. No raw payload assets.

Use Comet SDK primitives for custom metrics and parameters: `log_metric()`, `log_metrics()`, `log_parameter()`, `log_parameters()`. Use plot/curve logging only for summary histograms where the raw data is compact and sanitized.

### Stage 2: Instrument Phase Metrics

Instrumentation must be built into canonical runner/helper surfaces, not sidecar notebooks.

#### Phase1 Metrics: Data And Tokenizer

Required metrics per corpus phase:

- `phase1/<C>/record_count`
- `phase1/<C>/question_bytes_total`
- `phase1/<C>/answer_bytes_total`
- `phase1/<C>/token_ids_total`
- `phase1/<C>/distinct_token_ids`
- `phase1/<C>/vocab_coverage_ratio`
- `phase1/<C>/tokens_per_record_mean`
- `phase1/<C>/tokens_per_record_p50`
- `phase1/<C>/tokens_per_record_p95`
- `phase1/<C>/tokens_per_record_p99`
- `phase1/<C>/source_kind_counts`
- `phase1/<C>/source_kind_mapping`
- `phase1/<C>/invalid_record_count`
- `phase1/<C>/duplicate_record_id_count`
- `phase1/<C>/token_ids_per_sec`
- `phase1/<C>/latency_ms`

Pass gate:

- no invalid records,
- no duplicate record IDs,
- accepted source-kind mapping only,
- finite throughput,
- distinct token coverage logged,
- length distribution logged.

#### Phase2 Metrics: Packetizer And Geometry

Required metrics per corpus phase:

- `phase2/<C>/pqa1_files_consumed`
- `phase2/<C>/source_record_count`
- `phase2/<C>/source_real_token_count`
- `phase2/<C>/packet_count`
- `phase2/<C>/slot_count`
- `phase2/<C>/pjp1_bytes`
- `phase2/<C>/pjp1_sha256`
- `phase2/<C>/packetizer_binary_sha256`
- `phase2/<C>/packetizer_source_sha256`
- `phase2/<C>/packetizer_build_script_sha256`
- `phase2/<C>/collision_rate`
- `phase2/<C>/collision_count`
- `phase2/<C>/projected_vector_norm_mean`
- `phase2/<C>/projected_vector_norm_p95`
- `phase2/<C>/hamming_distance_mean`
- `phase2/<C>/hamming_distance_p05`
- `phase2/<C>/hamming_distance_p50`
- `phase2/<C>/hamming_distance_p95`
- `phase2/<C>/jl_distance_distortion_mean`
- `phase2/<C>/jl_distance_distortion_p95`
- `phase2/<C>/records_per_sec`
- `phase2/<C>/real_tokens_per_sec`
- `phase2/<C>/output_MB_per_sec`
- `phase2/<C>/latency_ms`

Initial pass gate:

- collision rate measured and less than or equal to `0.001`,
- no NaN/Inf geometry stats,
- source/build/binary identity reconciled,
- throughput logged,
- C3/C4 geometry not silently worse than C1/C2 without flagging.

If the collision or geometry gate fails, route to Engineering + Pipeline Integrator for projection/embedding repair. Research hypotheses may include geometry inspired by biological control systems and developmental computation, but those hypotheses must produce measurable projection improvements before they enter the execution surface.

#### Phase3 Metrics: HTP/NPU Forward Path

Required metrics per corpus phase:

- `phase3/<C>/pjp1_preflight_status`
- `phase3/<C>/native_preflight_status`
- `phase3/<C>/i8_oracle_mismatches`
- `phase3/<C>/htp_backend`
- `phase3/<C>/htp_output_sha256`
- `phase3/<C>/forward_loss`
- `phase3/<C>/forward_mse`
- `phase3/<C>/forward_cross_entropy` when target format supports it
- `phase3/<C>/perplexity` when language-model likelihood is available
- `phase3/<C>/answer_token_accuracy` when supervised answer targets are available
- `phase3/<C>/calibration_ece`
- `phase3/<C>/brier_score`
- `phase3/<C>/tokens_per_sec`
- `phase3/<C>/latency_ms`
- `phase3/<C>/host_to_device_ms`
- `phase3/<C>/device_compute_ms`
- `phase3/<C>/device_to_host_ms`

Initial pass gate:

- i8 oracle mismatches are zero,
- HTP backend identity logged,
- forward metrics finite on the C5 eval slice,
- latency and throughput logged,
- no readiness claim unless forward metrics improve across stable runs.

#### Phase4 Metrics: OpenCL/GPU Update Path

Required metrics per corpus phase:

- `phase4/<C>/opencl_device`
- `phase4/<C>/phase3_output_sha256`
- `phase4/<C>/target_sha256`
- `phase4/<C>/adapter_pre_sha256`
- `phase4/<C>/adapter_post_sha256`
- `phase4/<C>/consumed_output_causes_update`
- `phase4/<C>/adapter_changed`
- `phase4/<C>/loss_pre_update`
- `phase4/<C>/loss_post_update`
- `phase4/<C>/loss_delta`
- `phase4/<C>/grad_norm_l2`
- `phase4/<C>/grad_norm_linf`
- `phase4/<C>/update_norm_l2`
- `phase4/<C>/adapter_delta_norm_l2`
- `phase4/<C>/nan_gradient_count`
- `phase4/<C>/inf_gradient_count`
- `phase4/<C>/opencl_kernel_ms`
- `phase4/<C>/tokens_per_sec`
- `phase4/<C>/latency_ms`

Initial pass gate:

- consumed output causes update,
- adapter pre/post hashes differ,
- gradient norms finite,
- no NaN/Inf gradients,
- loss pre/post measured,
- no learning claim unless C5 confirms improvement against stable checkpoint.

### Stage 3: Phase5 / C5 Evaluation Contract

Phase5 is the evaluation layer. `C5` is the corpus-specific evaluation instance for the C1-C4 curriculum, not a fifth source corpus. The naming rule is:

- use `Phase5` for the pipeline stage that evaluates a trained or updated checkpoint,
- use `C5_after_<C>` for the evaluation point tied to a specific curriculum phase,
- use `C5_full_curriculum_postrun` for the full C1-C4 postrun evaluation,
- never promote C5 into source material or confuse it with C4 expansion.

C5 is always evaluation. It is the evaluation boundary after each curriculum phase and after the whole sequence.

C5 eval points:

- `C5_after_C1`
- `C5_after_C2`
- `C5_after_C2_5`
- `C5_after_C3`
- `C5_after_C4`
- `C5_full_curriculum_postrun`

Required C5 metrics:

- `c5/<eval_point>/loss`
- `c5/<eval_point>/loss_delta_vs_last_stable`
- `c5/<eval_point>/accuracy`
- `c5/<eval_point>/answer_exact_match`
- `c5/<eval_point>/answer_token_f1`
- `c5/<eval_point>/perplexity` when available
- `c5/<eval_point>/calibration_ece`
- `c5/<eval_point>/brier_score`
- `c5/<eval_point>/overfit_gap_train_vs_val`
- `c5/<eval_point>/grad_norm_max_observed`
- `c5/<eval_point>/checkpoint_sha256`
- `c5/<eval_point>/stable_checkpoint_baseline_sha256`
- `c5/<eval_point>/learning_score`

C5 pass gate:

- loss improves or stays within accepted tolerance against last stable checkpoint,
- accuracy/exact-match/token-F1 does not regress beyond accepted tolerance,
- calibration does not degrade beyond accepted tolerance,
- gradient norms remain finite and within configured band,
- overfit gap remains below configured threshold,
- throughput does not collapse without a routed performance blocker.

If C5 fails after a phase, the next curriculum phase does not advance as a learning claim. The lane may still run diagnostics if explicitly labeled diagnostic.

#### Phase5 Recursive Improvement Contract

After the first metric-complete C5 run, the operating mode changes from one-off execution to recursive hardening. Every cycle must:

1. Run the canonical Phase1 -> Phase2 -> Phase3 -> Phase4 -> Phase5 path for the authorized curriculum scope.
2. Compare C5 metrics against the last stable checkpoint and the immediately previous run.
3. Identify the dominant failure mode before proposing changes.
4. Route exactly one primary repair hypothesis to the owning lane.
5. Re-run the smallest falsifying path that can prove or reject that repair.
6. Delete or quarantine drift paths that were bypassed, contradicted, or replaced by the repair.
7. Preserve all nonclaims until C5 metrics show real improvement without regressions.

Primary failure domains:

- `material_failure`: eval split, source authority, answer leakage, unit/evidence/provenance, or C4 expansion problem.
- `phase1_tokenization_failure`: bad token distribution, low vocabulary coverage, invalid spans/masks, or unstable tokenizer identity.
- `phase2_geometry_failure`: collision rate, Hamming/JL distortion, projection norm, or PJP1 continuity failure.
- `phase3_npu_handoff_failure`: PJP1-to-HTP shape mismatch, quantization mismatch, oracle mismatch, NPU throughput collapse, or forward-loss signal loss.
- `phase4_gpu_update_failure`: OpenCL update instability, gradient blow-up/vanishing, adapter update not caused by Phase3 output, or loss not measured.
- `phase5_eval_failure`: loss/perplexity/accuracy/calibration regression, overfit gap, missing metrics, or checkpoint/baseline identity mismatch.
- `orchestration_failure`: idle lane, stale status, completed marker with owned next action, duplicate runner drift, or unowned artifact.

Each recursive cycle must emit a compact improvement record with:

- run label and immutable material/code identity,
- last stable checkpoint identity,
- candidate checkpoint identity,
- Phase1-Phase5 metric summary,
- slowest phase and data-move overhead,
- dominant failure domain,
- repair hypothesis,
- owner lane,
- next command or artifact,
- falsifier for the repair,
- drift paths deleted/quarantined,
- whether C5 improved, regressed, or remained inconclusive.

Research escalation is allowed when the metrics point to a real unknown, not as a substitute for execution. Research may draw from machine learning, information theory, computational physics, hardware architecture, biological computation, developmental systems, and natural memory/control ecologies. A research hypothesis enters the pipeline only when it produces a measurable intervention, a falsifier, and a bounded owner. Nature-inspired or cross-science ideas are welcome; they must still improve C5, throughput, geometry, stability, or handoff quality under measured gates.

## 7. Throughput Contract

The integrated pipeline must report both phase-local and end-to-end throughput.

Required throughput metrics:

- `throughput/e2e_tokens_per_sec`
- `throughput/e2e_records_per_sec`
- `throughput/phase1_tokens_per_sec`
- `throughput/phase2_real_tokens_per_sec`
- `throughput/phase3_htp_tokens_per_sec`
- `throughput/phase4_opencl_tokens_per_sec`
- `latency/phase1_ms`
- `latency/phase2_ms`
- `latency/phase3_htp_ms`
- `latency/phase4_opencl_ms`
- `latency/host_to_phone_transfer_ms`
- `latency/phone_to_host_transfer_ms`
- `latency/termux_bridge_ms`
- `latency/reporting_ms`

Performance gates:

- Every run must expose the slowest stage.
- Every optimization must preserve correctness hashes and C5 metrics.
- No throughput improvement counts if it regresses authority metrics, hides data movement, or skips validation.

## 8. HF Streaming Contract

HF streaming must be authenticated for Pro-account quota behavior. Do not print or commit tokens.

Authorized command pattern:

```bash
set -a
source /Users/prinivenpillay/.polymath-ai-corpus.env
set +a

export HUGGINGFACE_HUB_TOKEN="$HF_TOKEN"
export HF_XET_HIGH_PERFORMANCE=1
export HF_HUB_DOWNLOAD_TIMEOUT=120
export HF_HUB_ETAG_TIMEOUT=30

hf auth whoami
```

Python loader pattern:

```python
from datasets import load_dataset

repo_id = "Zer0pa/polymat-gemmalit-c1-c4-commercial-corpus"
revision = "<immutable_hf_commit_sha>"

ds = load_dataset(
    "json",
    data_files={
        "train": f"hf://datasets/{repo_id}/packages/C2_5/phase_C2.5_train.jsonl"
    },
    split="train",
    streaming=True,
    token=True,
    revision=revision,
)
```

Gate:

- `revision` must be immutable.
- `token=True` or explicit token must be used for private material.
- `hf://datasets/...` paths are preferred for streaming.
- No local material cache becomes source of truth unless its SHA stream is tied back to the immutable HF revision.

## 9. C4 Expansion Contract

C4 can expand. Expansion is encouraged if it improves C5 and does not break source authority.

C4 expansion is owned by Training Material Steward. Accepted domains:

- physics,
- chemistry,
- computational science,
- numerical methods,
- materials science,
- engineering science where source/provenance/license is explicit.

Forbidden C4 substitutions:

- math-only material promoted as science authority,
- OpenMath substitute as C4 authority,
- unlicensed or unverifiable material,
- rows without verifier/evidence/unit/provenance where required,
- deleting only bad rows while leaving an invalid package identity.

C4 expansion pass gate:

- new HF package root,
- immutable revision,
- manifest,
- QA bridge,
- row/split counts,
- SHA streams,
- license/provenance pass,
- unit/evidence/answer-leak pass,
- C5 comparison against prior stable C4.

## 10. Drift-Kill Contract

The repo must converge to one canonical execution surface per phase.

Required artifact:

`runtime/reports/orchestration/canonical_execution_surface_map.md`

Required fields per phase:

- canonical runner path,
- canonical helper path,
- allowed inputs,
- allowed outputs,
- raw-payload restrictions,
- owner lane,
- current source SHA,
- tests/checks,
- deprecated/quarantined paths,
- deletion/archive decision.

Rules:

- Temp scripts are deleted or archived unless tied to a current canonical route.
- Experimental kernels are quarantined unless they are under an active PRD workstream.
- Duplicate runners are blocked until one is selected.
- Reports may mention old artifacts, but execution must not route through stale helpers.
- Raw payload suffixes remain forbidden in repo reports: `.qai1`, `.pqa1`, `.pjp1`, `.bin`, `.raw`, `.f16`, env files, model/checkpoint/adapter payloads.

## 11. Watcher-Driver Cadence

Heartbeat cadence: every 10 minutes while active.

Each heartbeat must:

1. Read `EXECUTIVE_DELIVERY_STATE.json`.
2. Read this PRD.
3. Check Stage 0 gates first.
4. If a gate is blocked, send a targeted lane message with one concrete next action.
5. If a lane is idle despite an owned blocker, re-prompt it.
6. If the same blocker persists for 3 heartbeats, escalate in the current orchestration thread with exact owner and artifact missing.
7. Update the central state with active bottleneck, owner, next command, and expected artifact.
8. Refuse to treat status narration as progress.
9. After C5 executed metrics exist, maintain the recursive improvement loop: identify the slowest or weakest measured point, route one falsifiable repair, ensure the repair is tested, and delete drift found during the cycle.
10. If all lanes show completed markers but the sovereign gate has not advanced, treat that as an orchestration failure and nudge the lane that owns the next artifact.

Heartbeat output must include:

- `now`
- `current_gate`
- `owner`
- `artifact_waiting_on`
- `last_concrete_action`
- `next_concrete_action`
- `blocked_or_moving`
- `dominant_failure_domain`
- `drift_deleted_or_pending`
- `recursive_improvement_next_step`

## 12. Sequential And Parallel Plan

### Parallel Wave A: Freeze

Run immediately:

- Steward pins HF revision.
- Repo Custodian freezes code or code-hash manifest.
- Execution/Pipeline recover Phase2 Termux source/build identity.
- Engineering drafts metric schema implementation path.
- UI drafts Comet/dashboard visibility path.

Exit: all Stage 0 blockers resolved.

### Parallel Wave B: Metrics Implementation

Run after Stage 0 green or with explicit diagnostic-only branch:

- Engineering implements Phase1/2/3/4 metric logging.
- Pipeline Integrator validates metric schema and Comet contract.
- Phase3/4 Engineer wires HTP/OpenCL loss/gradient/throughput metrics.
- UI Engineer builds summary view and Comet panel checklist.

Exit: local compile/static checks pass, local dry-run/report generation passes, Comet dry-run with sanitized metadata passes if credentials are authorized.

### Sequential Wave C: Integrated Metric Run

Run only after Wave A and Wave B pass:

1. Phase1 C1.
2. C5 after C1.
3. Phase1/2/3/4 C1 integrated section if configured.
4. Phase1 C2.
5. C5 after C2.
6. Continue through C2.5, C3, C4.
7. C5 full curriculum postrun.
8. Publish external review packet v2.

No phase advances as a learning claim if its C5 gate fails.

### Parallel Wave D: Optimization

Run after first metric-complete integrated run:

- Optimize slowest measured phase.
- Improve Phase2 geometry if collision/distance metrics fail.
- Improve HTP throughput if Phase3 bottleneck dominates.
- Improve OpenCL update kernel if Phase4 bottleneck dominates.
- Expand C4 only through Steward authority gates.

Every optimization must compare against the last stable checkpoint in Comet and local JSON.

### Sequential Wave E: Smooth Operation Hardening

Run after the current C5 input chain is complete enough to execute a real C5 metrics run. This wave is not a documentation wave; it is the transition from debug-driven execution to repeatable operation.

1. Freeze the current canonical source state and raw-payload boundary.
2. Run Phase1 -> Phase2 -> Phase3 -> Phase4 -> Phase5 for C1.
3. If C5_after_C1 passes or fails with real metrics, record the dominant failure domain.
4. Apply one repair or optimization.
5. Re-run the minimum path needed to falsify that repair.
6. Continue C2, C2.5, C3, C4 only when prior C5 evidence does not regress the learning claim.
7. Run `C5_full_curriculum_postrun`.
8. Produce a smooth-operation hardening report.

The hardening report must include:

- command sequence actually used,
- phone/Termux/host handoff timing,
- end-to-end tokens/sec,
- per-phase latency,
- NPU handoff shape/hash/quantization summary,
- GPU update stability summary,
- C5 metric deltas against last stable checkpoint,
- bottleneck ranking,
- drift deleted during the cycle,
- next optimization target.

The target state is a pipeline that can be re-run without bespoke debugging and that automatically routes failures to the owning lane.

## 13. Acceptance Criteria

The PRD is complete when:

- HF revision is immutable in `material_verification.json`.
- Code state is immutable by commit or accepted full hash manifest.
- Phase2 binary/source/build identity is reconciled.
- Canonical execution surface map exists and stale drift paths are deleted or quarantined.
- Phase1 metrics are logged for C1, C2, C2.5, C3, C4.
- Phase2 geometry metrics are logged for C1, C2, C2.5, C3, C4.
- Phase3 forward/loss/throughput metrics are logged for C1, C2, C2.5, C3, C4.
- Phase4 gradient/loss/update metrics are logged for C1, C2, C2.5, C3, C4.
- C5 eval runs after each curriculum phase and after the full sequence.
- End-to-end throughput and per-phase latency are logged.
- Comet contains the run, metrics, parameters, and sanitized metadata assets.
- External review packet v2 has no raw payloads and no secret values.

## 14. Falsifiers

Any of these falsifies a pass:

- `hf_revision=main` or any moving material revision.
- Dirty/untracked execution source without accepted hash manifest.
- Missing Phase2 Termux source/build-script hash.
- Any raw payload inside repo report tree.
- Any secret value in repo or report tree.
- Missing Comet metrics for an accepted metric run.
- Missing C5 eval after any curriculum phase.
- NaN/Inf loss or gradient.
- Gradient blow-up without blocker routing.
- Collision rate missing or above threshold without blocker routing.
- Throughput reported without data movement overhead.
- C4 math substitute promoted as science authority.
- Local diagnostic represented as authority or learning.

## 15. References

- Comet custom metrics and parameters: https://www.comet.com/docs/v2/guides/experiment-management/log-data/metrics-and-parameters/
- Comet curves and plots: https://www.comet.com/docs/v2/guides/experiment-management/log-data/curves-and-plots/
- Hugging Face dataset streaming: https://huggingface.co/docs/datasets/stream
- Hugging Face dataset loading and revision parameter: https://huggingface.co/docs/datasets/loading
- Hugging Face Hub environment variables: https://huggingface.co/docs/huggingface_hub/package_reference/environment_variables
