# C5 / Comet Execution Runbook

Generated: 2026-06-30T20:57:15Z
Owner lane: Pipeline Integrator
Status: contract artifact only; Stage0 remains blocked.

## Purpose

This runbook defines the metadata-only inputs required for C5 evaluation and Comet visibility during the C1 -> C2 -> C2.5 -> C3 -> C4 mobile SoC execution path. It does not authorize execution, Comet calls, HF calls, phone use, secret sourcing, staging, committing, or pushing.

## Required Input Files

An accepted C5/Comet attempt must receive these JSON reports:

- Phase1 metric report for each executed corpus phase.
- Phase2 metric report for each executed corpus phase.
- Phase3 metric report for each executed corpus phase.
- Phase4 metric report for each executed corpus phase.
- C5 eval report after each checkpoint: C1, C2, C2.5, C3, C4, and full curriculum.
- Run identity report with immutable material/code/runtime identities.
- Phase2 binary identity reconciliation report with `stage0_phase2_identity_green=true`.

Raw `.qai1`, `.pqa1`, `.pjp1`, tensor, model, checkpoint, adapter, secret, and env payloads are not valid inputs to this runbook.

## Shared JSON Envelope

Every phase metric report must use this envelope:

```json
{
  "schema_version": "polymath_phase_metric_report_v1",
  "run_label": "string",
  "corpus_phase": "C1|C2|C2_5|C3|C4",
  "created_at_utc": "RFC3339 timestamp",
  "material_identity": {
    "hf_repo_id": "Zer0pa/polymat-gemmalit-c1-c4-commercial-corpus",
    "hf_revision": "immutable commit SHA",
    "package_path": "hf://datasets/<repo_id>/packages/<phase>/",
    "manifest_sha256": "sha256",
    "qa_bridge_sha256": "sha256"
  },
  "code_identity": {
    "repo_head": "git SHA or null",
    "repo_dirty_status": "clean|dirty_with_hash_manifest",
    "code_hash_manifest_sha256": "sha256",
    "canonical_execution_surface_map_sha256": "sha256"
  },
  "runtime_identity": {
    "phone_model": "string",
    "android_api": "string",
    "termux_identity": "string",
    "htp_backend_path": "string|null",
    "qairt_or_qnn_version": "string|null",
    "opencl_device": "string|null"
  },
  "metrics": {},
  "artifacts": {
    "metadata_report_path": "repo-relative or absolute path",
    "metadata_report_sha256": "sha256"
  },
  "pass_fail": {
    "status": "pass|fail|blocked|diagnostic_only",
    "first_missing_or_failing_field": "string|null"
  },
  "nonclaims": []
}
```

## Phase1 Required JSON Metrics

`metrics` must include:

```json
{
  "phase1/<C>/record_count": 0,
  "phase1/<C>/question_bytes_total": 0,
  "phase1/<C>/answer_bytes_total": 0,
  "phase1/<C>/token_ids_total": 0,
  "phase1/<C>/distinct_token_ids": 0,
  "phase1/<C>/vocab_coverage_ratio": 0.0,
  "phase1/<C>/tokens_per_record_mean": 0.0,
  "phase1/<C>/tokens_per_record_p50": 0.0,
  "phase1/<C>/tokens_per_record_p95": 0.0,
  "phase1/<C>/tokens_per_record_p99": 0.0,
  "phase1/<C>/source_kind_counts": {},
  "phase1/<C>/source_kind_mapping": {},
  "phase1/<C>/invalid_record_count": 0,
  "phase1/<C>/duplicate_record_id_count": 0,
  "phase1/<C>/token_ids_per_sec": 0.0,
  "phase1/<C>/latency_ms": 0.0
}
```

Diagnostic pass threshold:

- `invalid_record_count == 0`
- `duplicate_record_id_count == 0`
- source-kind mapping is present
- token throughput and latency are finite
- token length distribution fields are present

## Phase2 Required JSON Metrics

`metrics` must include:

```json
{
  "phase2/<C>/pqa1_files_consumed": 0,
  "phase2/<C>/source_record_count": 0,
  "phase2/<C>/source_real_token_count": 0,
  "phase2/<C>/packet_count": 0,
  "phase2/<C>/slot_count": 0,
  "phase2/<C>/pjp1_bytes": 0,
  "phase2/<C>/pjp1_sha256": "sha256",
  "phase2/<C>/packetizer_binary_sha256": "sha256",
  "phase2/<C>/packetizer_source_sha256": "sha256",
  "phase2/<C>/packetizer_build_script_sha256": "sha256",
  "phase2/<C>/collision_rate": 0.0,
  "phase2/<C>/collision_count": 0,
  "phase2/<C>/projected_vector_norm_mean": 0.0,
  "phase2/<C>/projected_vector_norm_p95": 0.0,
  "phase2/<C>/hamming_distance_mean": 0.0,
  "phase2/<C>/hamming_distance_p05": 0.0,
  "phase2/<C>/hamming_distance_p50": 0.0,
  "phase2/<C>/hamming_distance_p95": 0.0,
  "phase2/<C>/jl_distance_distortion_mean": 0.0,
  "phase2/<C>/jl_distance_distortion_p95": 0.0,
  "phase2/<C>/records_per_sec": 0.0,
  "phase2/<C>/real_tokens_per_sec": 0.0,
  "phase2/<C>/output_MB_per_sec": 0.0,
  "phase2/<C>/latency_ms": 0.0
}
```

Diagnostic pass threshold:

- Phase2 identity reconciliation report is green
- `collision_rate <= 0.001`
- geometry stats are finite
- throughput and output bytes are logged
- C3/C4 geometry regressions are flagged instead of hidden

## Phase3 Required JSON Metrics

`metrics` must include:

```json
{
  "phase3/<C>/pjp1_preflight_status": "pass|fail|blocked",
  "phase3/<C>/native_preflight_status": "pass|fail|blocked",
  "phase3/<C>/i8_oracle_mismatches": 0,
  "phase3/<C>/htp_backend": "string",
  "phase3/<C>/htp_output_sha256": "sha256",
  "phase3/<C>/forward_loss": 0.0,
  "phase3/<C>/forward_mse": 0.0,
  "phase3/<C>/forward_cross_entropy": 0.0,
  "phase3/<C>/perplexity": 0.0,
  "phase3/<C>/answer_token_accuracy": 0.0,
  "phase3/<C>/calibration_ece": 0.0,
  "phase3/<C>/brier_score": 0.0,
  "phase3/<C>/tokens_per_sec": 0.0,
  "phase3/<C>/latency_ms": 0.0,
  "phase3/<C>/host_to_device_ms": 0.0,
  "phase3/<C>/device_compute_ms": 0.0,
  "phase3/<C>/device_to_host_ms": 0.0
}
```

Conditional fields may use `null` only when paired with a sibling `not_applicable_reason` in the report.

Diagnostic pass threshold:

- `i8_oracle_mismatches == 0`
- HTP backend identity is logged
- forward metrics are finite on the C5 eval slice
- latency and throughput are logged
- no Phase3 readiness claim is made from smoke-only evidence

## Phase4 Required JSON Metrics

`metrics` must include:

```json
{
  "phase4/<C>/opencl_device": "string",
  "phase4/<C>/phase3_output_sha256": "sha256",
  "phase4/<C>/target_sha256": "sha256",
  "phase4/<C>/adapter_pre_sha256": "sha256",
  "phase4/<C>/adapter_post_sha256": "sha256",
  "phase4/<C>/consumed_output_causes_update": true,
  "phase4/<C>/adapter_changed": true,
  "phase4/<C>/loss_pre_update": 0.0,
  "phase4/<C>/loss_post_update": 0.0,
  "phase4/<C>/loss_delta": 0.0,
  "phase4/<C>/grad_norm_l2": 0.0,
  "phase4/<C>/grad_norm_linf": 0.0,
  "phase4/<C>/update_norm_l2": 0.0,
  "phase4/<C>/adapter_delta_norm_l2": 0.0,
  "phase4/<C>/nan_gradient_count": 0,
  "phase4/<C>/inf_gradient_count": 0,
  "phase4/<C>/opencl_kernel_ms": 0.0,
  "phase4/<C>/tokens_per_sec": 0.0,
  "phase4/<C>/latency_ms": 0.0
}
```

Diagnostic pass threshold:

- consumed Phase3 output causes update
- adapter pre/post hashes differ
- gradient and update norms are finite
- `nan_gradient_count == 0`
- `inf_gradient_count == 0`
- pre/post loss is measured
- no learning claim is made until C5 confirms the eval boundary

## C5 Evaluation Checkpoints

Required C5 eval points:

- `C5_after_C1`
- `C5_after_C2`
- `C5_after_C2_5`
- `C5_after_C3`
- `C5_after_C4`
- `C5_full_curriculum_postrun`

Each C5 report must include:

```json
{
  "schema_version": "polymath_c5_eval_report_v1",
  "run_label": "string",
  "eval_point": "C5_after_C1|C5_after_C2|C5_after_C2_5|C5_after_C3|C5_after_C4|C5_full_curriculum_postrun",
  "created_at_utc": "RFC3339 timestamp",
  "c5_material_identity": {
    "hf_repo_id": "string",
    "hf_revision": "immutable commit SHA",
    "eval_split_path": "hf://datasets/... or metadata-only path",
    "eval_split_sha256": "sha256",
    "record_count": 0
  },
  "checkpoint_identity": {
    "checkpoint_sha256": "sha256",
    "stable_checkpoint_baseline_sha256": "sha256",
    "checkpoint_payload_location": "outside_git"
  },
  "metrics": {
    "c5/<eval_point>/loss": 0.0,
    "c5/<eval_point>/loss_delta_vs_last_stable": 0.0,
    "c5/<eval_point>/accuracy": 0.0,
    "c5/<eval_point>/answer_exact_match": 0.0,
    "c5/<eval_point>/answer_token_f1": 0.0,
    "c5/<eval_point>/perplexity": 0.0,
    "c5/<eval_point>/calibration_ece": 0.0,
    "c5/<eval_point>/brier_score": 0.0,
    "c5/<eval_point>/overfit_gap_train_vs_val": 0.0,
    "c5/<eval_point>/grad_norm_max_observed": 0.0,
    "c5/<eval_point>/checkpoint_sha256": "sha256",
    "c5/<eval_point>/stable_checkpoint_baseline_sha256": "sha256",
    "c5/<eval_point>/learning_score": 0.0
  },
  "diagnostic_thresholds": {
    "loss_delta_vs_last_stable_max": 0.0,
    "accuracy_regression_max_abs": 0.02,
    "exact_match_regression_max_abs": 0.02,
    "token_f1_regression_max_abs": 0.02,
    "calibration_ece_regression_max_abs": 0.02,
    "overfit_gap_train_vs_val_max": 0.10,
    "grad_norm_must_be_finite": true,
    "throughput_collapse_max_relative": 0.25
  },
  "pass_fail": {
    "status": "pass|fail|blocked|diagnostic_only",
    "first_missing_or_failing_field": "string|null"
  },
  "nonclaims": []
}
```

Initial thresholds are diagnostic gates. They may block learning claims, but they do not create model-quality claims.

## End-To-End Throughput And Latency Fields

The integrated summary report must include:

```json
{
  "throughput/e2e_tokens_per_sec": 0.0,
  "throughput/e2e_records_per_sec": 0.0,
  "throughput/phase1_tokens_per_sec": 0.0,
  "throughput/phase2_real_tokens_per_sec": 0.0,
  "throughput/phase3_htp_tokens_per_sec": 0.0,
  "throughput/phase4_opencl_tokens_per_sec": 0.0,
  "latency/phase1_ms": 0.0,
  "latency/phase2_ms": 0.0,
  "latency/phase3_htp_ms": 0.0,
  "latency/phase4_opencl_ms": 0.0,
  "latency/host_to_phone_transfer_ms": 0.0,
  "latency/phone_to_host_transfer_ms": 0.0,
  "latency/termux_bridge_ms": 0.0,
  "latency/reporting_ms": 0.0,
  "slowest_stage": "phase1|phase2|phase3|phase4|transfer|reporting",
  "slowest_stage_ms": 0.0
}
```

Diagnostic pass threshold:

- every stage is present
- transfer and bridge overhead are not hidden
- slowest stage is named
- throughput improvements do not count if correctness hashes or C5 metrics regress

## Comet Experiment Contract

Experiment name:

- `polymath_<run_label>`

Required tags:

- `polymath`
- `mobile_soc`
- `c1_c5`
- `phase1`
- `phase2`
- `phase3`
- `phase4`
- `c5_eval`
- `C1`
- `C2`
- `C2_5`
- `C3`
- `C4`
- `diagnostic_only` when Stage0 or learning gates are not green

Required parameters:

- `run_label`
- `hf_repo_id`
- `hf_revision`
- `hf_revision_is_immutable`
- `material_manifest_sha256`
- `transition_gate_plan_sha256`
- `replay_schedule_sha256`
- `repo_head`
- `repo_dirty_status`
- `code_hash_manifest_sha256`
- `canonical_execution_surface_map_sha256`
- `phone_model`
- `android_api`
- `termux_identity`
- `htp_backend_path`
- `qairt_or_qnn_version`
- `opencl_device`
- `phase2_packetizer_binary_sha256`
- `phase2_packetizer_source_sha256`
- `phase2_packetizer_build_script_sha256`
- `phase2_identity_reconciliation_status`

Metric families:

- `phase1/<C>/...`
- `phase2/<C>/...`
- `phase3/<C>/...`
- `phase4/<C>/...`
- `c5/<eval_point>/...`
- `throughput/...`
- `latency/...`

Local JSON metric names and Comet metric names must match exactly.

## Sanitized Asset Rules

Allowed Comet assets after explicit authorization:

- metric summary JSON
- material verification JSON
- Phase2 identity reconciliation JSON
- C5 eval summary JSON
- external review packet manifest
- sanitized compact histograms
- Markdown handoffs

Forbidden Comet assets:

- `.qai1`
- `.pqa1`
- `.pjp1`
- `.bin`
- `.raw`
- `.f16`
- raw tensor payloads
- model weights
- checkpoint or adapter payloads
- env files
- tokens
- secrets
- SSH keys
- phone token files
- full raw corpus package files

## Minimal Authorization Request For Comet

Before any Comet call, Meta or the user must explicitly authorize:

```text
Authorize Execution/UI to use COMET_API_KEY for one run label <run_label>, with metadata-only Comet logging under experiment polymath_<run_label>. Authorization excludes raw payload assets, model/checkpoint/adapter uploads, env-file printing, token printing, and any HF/phone action not separately authorized.
```

Execution must confirm:

- `COMET_API_KEY` is available in the authorized runtime without printing it.
- local JSON metric reports exist before Comet logging.
- Stage0 status is recorded as `green`, `blocked`, or `diagnostic_only`.
- all uploaded assets are metadata-only.

## Blocking Conditions

Block C5/Comet executable green if any field is missing:

1. immutable HF revision;
2. code identity or accepted code-hash manifest;
3. Stage0 Phase2 identity green report;
4. local Phase1/2/3/4 metric JSON reports;
5. C5 material identity and eval split hash;
6. stable checkpoint baseline hash;
7. C5 eval report after each executed phase;
8. explicit COMET_API_KEY authorization for live Comet logging;
9. sanitized asset manifest.

## Nonclaims

This runbook does not claim Stage0 green, model learning, model quality, Phase3 readiness, Phase4 readiness, production readiness, 100k/1M Phase2 authority, external reproducibility, or permission to call Comet.
