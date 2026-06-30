# C5 Evaluation Contract

Generated: 2026-06-30
Owner lane: Pipeline Integrator
PRD: `docs/PRD-C1-C5-DRIFT-FREE-METRICS-COMET-EXECUTION-2026-06-30.md`

## Role

C5 is always an evaluation boundary. It is not a pre-execution material blocker for a C1-C4 Phase1->4 preparation run. It becomes mandatory after each curriculum phase and after the full curriculum for any learning or model-quality claim.

## Evaluation Points

Required eval points:

- `C5_after_C1`
- `C5_after_C2`
- `C5_after_C2_5`
- `C5_after_C3`
- `C5_after_C4`
- `C5_full_curriculum_postrun`

If a curriculum phase is run only as a diagnostic, the corresponding C5 result must be labeled diagnostic and must not advance a learning claim.

## Required Inputs

Each C5 eval report must identify:

- eval point;
- run label;
- immutable HF material revision;
- C5 eval material ID and SHA stream;
- current checkpoint SHA;
- last stable checkpoint SHA;
- training phase that produced the checkpoint;
- Phase3 output identity when relevant;
- Phase4 adapter/checkpoint identity when relevant;
- runtime identity;
- metric schema version;
- Comet experiment name or explicit reason Comet was not authorized.

## Required Metrics

Required per eval point:

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

## Pass Gate

C5 passes only when:

- loss improves or stays within accepted tolerance against the last stable checkpoint;
- accuracy, exact match, and token F1 do not regress beyond accepted tolerance;
- calibration does not degrade beyond accepted tolerance;
- gradient norms are finite and within the configured band;
- overfit gap remains below configured threshold;
- throughput does not collapse without a routed performance blocker;
- checkpoint and baseline hashes are present;
- local JSON and Comet metric names match the shared schema.

Tolerance values must be declared in the C5 report. Missing tolerance values block learning claims.

## Fail Routing

- Loss regression: stop learning claim for the next phase and route to Engineering/Phase3/4.
- Accuracy or F1 regression: route to Training Material Steward and Engineering for data/objective inspection.
- Calibration regression: route to Phase3/4 and UI for surfaced risk labeling.
- Gradient NaN/Inf or blow-up: route to Phase3/4 Engineer and block advancement.
- Throughput collapse: route to Execution/Phase3/4 with slowest-stage evidence.
- Missing stable checkpoint: route to Execution/Repo Custodian.
- Missing C5 eval material identity: route to Training Material Steward.

Diagnostics may continue only when explicitly labeled diagnostic and cannot be promoted as learning evidence.

## Required Report Fields

Each C5 eval report must include:

- `schema_version`
- `run_label`
- `eval_point`
- `created_at_utc`
- `material_identity`
- `checkpoint_identity`
- `stable_baseline_identity`
- `runtime_identity`
- `metrics`
- `tolerances`
- `pass_fail`
- `blockers`
- `comet_identity`
- `raw_payload_boundaries`
- `nonclaims`

## Raw Payload Boundary

Reports may include hashes, paths, counts, scalar metrics, compact histograms, and sanitized summaries. Reports must not include raw corpus files, raw tensors, model weights, checkpoint payloads, adapter payloads, env files, tokens, or secrets.

## Nonclaims

A C5 pass supports the declared eval boundary only. It does not by itself claim production readiness, 100k/1M Phase2 authority, external reproducibility, or fused megakernel progress.
