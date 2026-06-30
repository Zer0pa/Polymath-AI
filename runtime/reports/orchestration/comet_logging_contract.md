# Comet Logging Contract

Generated: 2026-06-30
Owner lane: Pipeline Integrator
PRD: `docs/PRD-C1-C5-DRIFT-FREE-METRICS-COMET-EXECUTION-2026-06-30.md`

## Purpose

Accepted metric runs must have one local JSON evidence stream and one matching Comet experiment. Comet is visibility and comparison infrastructure; it does not replace local JSON reports, hash manifests, C5 gates, or external review packets.

## Experiment Identity

- One Comet experiment per integrated run.
- Experiment name: `polymath_<run_label>`.
- Required tags: `polymath`, `mobile_soc`, `c1_c5`, `phase1`, `phase2`, `phase3`, `phase4`, `c5_eval`.
- Required corpus tags: `C1`, `C2`, `C2_5`, `C3`, `C4`.
- Optional diagnostic tags must include `diagnostic_only` when the run is not an authority candidate.

## Required Parameters

Log these with `log_parameter()` or `log_parameters()` before metrics:

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

Fail the run as an accepted metric run if `hf_revision` is `main`, the repo state is dirty without an accepted code-hash manifest, or the Phase2 identity fields are missing.

## Metric Naming

Use exactly the metric names from `runtime/reports/orchestration/c1_c5_metric_schema.json`.

Patterns:

- `phase1/<C>/...`
- `phase2/<C>/...`
- `phase3/<C>/...`
- `phase4/<C>/...`
- `c5/<eval_point>/...`
- `throughput/...`
- `latency/...`

Examples:

- `phase2/C3/collision_rate`
- `phase4/C4/loss_delta`
- `c5/C5_after_C4/loss_delta_vs_last_stable`
- `throughput/e2e_tokens_per_sec`

All local JSON metric keys and Comet metric keys must match. If a metric is conditional and unavailable, the local JSON report must include a `not_applicable_reason` field for that metric family.

## Logging Primitives

Use Comet SDK primitives only after credentials are explicitly authorized:

- `log_parameter()` / `log_parameters()` for run identity.
- `log_metric()` / `log_metrics()` for scalar metrics.
- Plot or curve logging only for compact sanitized summaries.
- Asset logging only for metadata JSON, Markdown summaries, manifests, and small sanitized plots.

Do not log raw payload assets.

## Allowed Assets

Allowed:

- metric summary JSON
- material verification JSON
- Phase2 identity reconciliation JSON
- C5 eval summary JSON
- external review packet manifest
- sanitized compact histograms
- Markdown handoffs

Forbidden:

- `.qai1`, `.pqa1`, `.pjp1`
- raw tensor payloads
- `.bin`, `.raw`, `.f16`
- model weights
- checkpoint or adapter payloads
- env files
- tokens, secrets, SSH keys, phone token files
- full raw corpus package files

## Pass Gate

Comet logging is acceptable only when:

- local JSON report exists and matches Comet metric names;
- immutable HF revision is logged;
- repo/code identity is logged;
- Phase2 binary/source/build reconciliation is logged;
- Phase1 through Phase4 metrics are present for every executed corpus phase;
- C5 metrics are present after each executed curriculum phase and at full postrun when applicable;
- no raw payload or secret is logged as an asset;
- failures are logged as failures, not omitted metrics.

## Routing

- Missing credential authorization: route to Execution/Meta for authorization; keep local JSON required.
- Missing metric field: route to the owning engineering lane.
- Missing immutable material/code/Phase2 identity: block accepted metric run and route to Steward, Repo Custodian, or Execution/Pipeline respectively.
- Comet available but local JSON absent: fail the evidence contract.

## Nonclaims

Comet visibility does not claim model learning, model quality, Phase3 readiness, Phase4 readiness, production readiness, or external reproducibility by itself.
