# PRD: Phase 3/4 Task-Aligned Projection For Phone-Native Gemma-4-E4B Polar Training

Document Class: LIVING_EXECUTION_PRD
Status: AMENDED_FOR_PHASE34B_GRADIENT_SOURCE_AND_RICHER_ASVD_CONTINUATION
Created: 2026-07-08
Last amended: 2026-07-09
Repository: `/Users/Zer0pa/Polymat AI/Polymath-AI`
Authority runtime: REDMAGIC NX789J / SM8750 / FY25013101C8
Primary source brief: `/Users/Zer0pa/Polymat AI/Task-Aligned Projection Design for Phone-Native Gemma-4-E4B Polar Training.md`
Context anchor: `docs/GEMMA-4-TRAINING-PIPELINE-SCIENCE-ENGINEERING-UPDATE-2026-07-06.md`
Post-exhaustion sources: `docs/APEX-GATE-E-SCIENCE-REPORT-SEQUENCE-2026-07-06/06_APEX-GATE-E-TASK-ALIGNED-PROJECTION-CANDIDATE-EXHAUSTION-ENGINEERING-SCIENCE-REPORT-2026-07-09.md` and `runtime/reports/apex_heterogeneous_cell/phase34_task_aligned_projection_20260708T115449Z/DESIGN_DIFF_ANALYSIS_20260709.md`

## 1. Decision

Gate E remains falsified. Do not start C3/C4/D3 from the current C2/JL C2
theta state.

The next execution program is a phone-native Phase 3/4 repair campaign that
replaces random Rademacher JL as the Phase 2/3 projection basis with
task-aligned projection candidates, screens them through cheap polar/NLL
correlation tests, and promotes only passing candidates into longer Gate D2A
and Gate E authority runs.

The campaign runs until one of these terminal states:

```yaml
success_terminal_state:
  status: gate_e_repaired_projection_passed
  requires:
    - phone_native_projection_candidate
    - matched_no_update_control
    - matched_random_theta_control
    - positive_polar_nll_correlation_screen
    - gate_d2a_polar_pass
    - gate_e_decoder_nll_delta_per_token_negative
    - metadata_only_comet_logged
    - custody_manifest_ready

failure_terminal_state:
  status: all_predeclared_projection_hypotheses_falsified_or_exact_blocked
  requires:
    - every predeclared candidate has a report
    - exact first_missing_green_field for each candidate
    - no promotion narrative
    - next research escalation packet
```

## 2. Governing Objective

Build and test a phone-native task-aligned projection path for Gemma-4-E4B
polar training:

```text
calibrated projection basis
  -> PQA1/PJP1 or compatible Phase 2 materialization
  -> Phase 3 QNN/HTP forward or validated native forward island
  -> Phase 4 Adreno/Vulkan theta update
  -> Gate D2A polar heldout check
  -> Gate E phone-native decoder token-NLL/perplexity authority report
```

Mac is only the control point. Authority execution, candidate screening, theta
update, and Gate E evidence must run on the RedMagic/Termux/native surface
unless this PRD explicitly labels a step as offline static-asset construction.
Any offline static asset must still be accepted or rejected by phone-native
screening and Gate E.

## 3. Current Falsifier State

The active C2/JL C2 line is not promotable.

```yaml
current_gate_e_status: falsified
promotion_allowed: false
c3_c4_d3_authorized: false
authority_metric: decoder_token_nll_per_token
sign_convention: after_minus_before
pass_requires: negative_nll_delta_on_phone_native_gate_e_authority_report

jl_c2_gate_d2a_polar_metric:
  before_loss: 30906.645910614105
  after_loss: 30860.12747423278
  loss_delta: -46.518436381324136
  status: polar_surrogate_pass

jl_c2_gate_e_phone_native_decoder_metric:
  before_nll_per_token: 14.538868526231177
  after_nll_per_token: 14.555113501137114
  nll_delta_per_token: 0.01624497490593768
  before_perplexity: 2061343.5279915193
  after_perplexity: 2095103.4741836223
  record_count: 27
  token_count: 27
  status: falsified

surrogate_validity:
  polar_loss_delta: -46.518436381324136
  nll_delta_per_token: 0.01624497490593768
  verdict: polar_nll_direction_diverge
```

Interpretation:

```text
The polar surrogate improved.
The decoder-token authority metric worsened.
The projection/update path must be repaired before any continuation claim.
```

Post-execution custody note, 2026-07-09: the initial Phase34 candidate set
under this PRD has now reached the failure terminal state. H1 ASVD was blocked
before full matrix construction by centered activation rank `93 < 256`; H2
Gradient-SVD/GaLore was blocked by the absent `dL_NLL/dh_layer24` gradient
surface; H3 was a finite-difference P-GAP approximation, not true P-GAP, and
failed D3 on `p_value_above_stage_threshold`; H4 RMT failed D3 on
`fraction_aligned_below_stage_threshold`; H5 controls were not authorized. This
amendment preserves those outcomes and defines a new continuation route. It
does not reopen H4, relabel H3 as true P-GAP, lower D3 thresholds, or soften
Gate E.

```yaml
post_exhaustion_state:
  phase34_candidate_set: exhausted_under_current_prd
  h1_asvd: blocked_not_disproven
  h2_gradient_svd_galore: blocked_not_disproven
  h3_finite_difference_pgap_approximation: approximate_d3_failed_not_true_pgap
  true_gradient_aligned_pgap: untested_requires_gradient_surface
  h4_rmt: d3_falsified_do_not_relitigate_under_current_prd
```

## 4. Objective Contract

### 4.1 Authority Metric

The sovereign metric is:

```text
phone-native accepted theta state
  -> native-polar decoder/logit surface
  -> token-level next-token NLL
  -> perplexity before/after
```

Pass requires:

```yaml
gate_e_authority_pass:
  status: gate_e_token_nll_perplexity_pass
  nll_delta_per_token: "< 0.0"
  before_after_record_count: 27
  token_count: ">= 27"
  native_polar_consumed_by_logits: true
  rank16_cartesian_materialization_used: false
  lm_head_or_unembedding_present: true
  comet_status: logged
```

Any non-negative NLL delta is failure, no matter how large the polar heldout
gain is.

Authority freeze:

```yaml
authority_freeze:
  gate_e_status: falsified
  authority_report_sha256: 70739a1c78b5d1cea5a98d1826f8a1b4c658929c7b534612e346ee0309e432f0
  no_surrogate_metric_can_repair_authority: true
  no_rank_or_correlation_metric_can_repair_authority: true
  revised_candidates_start_from_falsified_authority_state: true
```

### 4.2 Intermediate Gates

Intermediate gates are allowed only as filters:

- projection construction pass;
- projection matrix identity and shape pass;
- phone smoke pass;
- polar/NLL correlation pass;
- Gate D2A polar pass;
- metadata-only Comet logging pass.

They do not authorize promotion without Gate E.

### 4.3 Nonclaims

This PRD does not claim:

- full Gemma 4 model training success;
- language-model improvement;
- C2/JL C2 repair;
- C3/C4/D3 authorization;
- binary-JL QNN execution;
- 128-token fused QNN graph restoration;
- OpenCL recordable queue authority execution;
- app/game-mode acceleration;
- Comet dashboard evidence beyond metadata-safe logged artifacts;
- H1 ASVD disproved as a method;
- H2 GaLore/Gradient-SVD disproved as a method;
- true P-GAP executed in the historical H3 run;
- near-threshold D3 evidence as promotion;
- rerun authorization without a new accepted data surface.

## 5. Boundary And Forbidden Artifacts

Allowed in repo:

- source code;
- small schemas;
- markdown PRDs/reports;
- metadata-only JSON reports;
- manifests;
- hashes;
- counts;
- aggregate numeric metrics;
- sanitized command ledgers.

Forbidden in repo, reports, Comet assets, comments, and handoffs:

- raw corpus rows;
- raw prediction JSONL rows;
- raw token-NLL rows;
- tokens;
- logits;
- raw QNN tensors;
- raw theta binaries;
- model weights;
- safetensors;
- SDK binaries;
- stdout/stderr dumps;
- `.env`, `.env.local`, `.termux_agent_env`, token files, SSH keys, service credentials.

Raw payloads must remain outside git under explicit scratch roots such as:

```text
/Users/Zer0pa/Polymat AI/runtime/tmp/<run_id>/
/data/data/com.termux/files/home/<phase34_run_root>/
```

Reports may reference those paths with hashes and counts only.

## 6. Provider Capability Capsule

Provider access is operational capability, not evidence.

```yaml
provider_capability_capsule:
  matrix_artifact: runtime/reports/orchestration/SYSTEM_PROVIDER_ACCESS_CAPABILITY_MATRIX_20260702T201330Z.md
  providers:
    phone_adb_termux:
      role: RedMagic 10 Pro authority execution target for all training/evaluation gates
      current_safe_check:
        adb_device: FY25013101C8
        product: NX789J-EEA
        model: NX789J
        soc: SM8750
        android: 15
      ssh_path: "adb forward tcp:18022 tcp:8022; ssh -i ~/.ssh/polymath_host -p 18022 u0_a536@127.0.0.1"
      env_file: /data/data/com.termux/files/home/.termux_agent_env
      env_file_sha256: 9874fec9b9998e9e210d32fc71b40c48cf42586cd44c48f9c529c9f9c2118c7f
      current_classification: PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES
    hugging_face:
      role: corpus/model revision source and provenance
      host_path: "source /Users/prinivenpillay/.polymath-ai-corpus.env; export HUGGINGFACE_HUB_TOKEN=$HF_TOKEN"
      phone_path: "source ~/.termux_agent_env; use env-backed Python/API until stale huggingface-cli wrapper is repaired"
      current_classification: PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES
    github:
      role: source custody and PR surface through Repo Custodian only
      host_user: Zer0pa-Architect-Prime
      phone_path: "source ~/.termux_agent_env; GH_TOKEN enables gh api even if persistent gh auth status is empty"
      current_classification: PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES
    comet:
      role: authority-linked numeric metadata logging
      host_runtime: ".venv/bin/python with comet_ml"
      required_workspace_for_current_apex: zer0pa-imc
      required_project: mobile-polymath-ai-training
      phone_env_note: "phone env may default to zer0pa; force COMET_WORKSPACE=zer0pa-imc for current Apex custody"
      current_classification: PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES
    runpod:
      role: QAIRT/QNN SDK source/tool host only if phone/local tooling cannot build static artifacts
      current_classification: PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES
  secret_policy: "Never print, copy, summarize, commit, or include token/key values."
```

## 7. Innovation Primer

```yaml
innovation_primer:
  objective: "Repair polar surrogate alignment by replacing task-agnostic JL with task-aligned projection bases."
  authority_metric: "phone-native decoder token NLL per token, after_minus_before < 0"
  known_constraints:
    - "HTP/QNN is forward-first; do not assume phone-native full backprop."
    - "Current accepted QNN boundary is [1,16,2560] float32 hidden, not direct PJP1 binary-JL."
    - "Vulkan theta update is theta-only over 256 elements."
    - "Gate E full27 is expensive; use micro-gates before full long runs."
    - "Raw payloads and secrets never enter repo or Comet."
  nature_analogs:
    - source_domain: "error-correcting communication"
      mechanism: "codes preserve task-relevant bits, not arbitrary geometry"
      engineering_translation: "projection basis must preserve NLL-gradient inner products, not only Euclidean distances"
      falsifier: "positive polar loss delta correlates with NLL regression or zero correlation"
    - source_domain: "homeostatic control"
      mechanism: "small perturbations are screened before committing organism-wide change"
      engineering_translation: "n=2/n=6 micro tests precede n=20 correlation and full27 Gate E"
      falsifier: "candidate requires long run before passing cheap directional checks"
    - source_domain: "immune clonal selection"
      mechanism: "many candidates face severe early binding tests before expansion"
      engineering_translation: "ASVD, gradient-SVD, P-GAP, and RMT candidates run in parallel lanes, then phone queue promotes only survivors"
      falsifier: "single favorite hypothesis monopolizes full-run budget without predeclared screens"
  scientific_intersections:
    - domain: "GaLore / low-rank LLM gradients"
      candidate_principle: "top singular vectors of task gradients capture NLL-relevant subspace"
      expected_design_effect: "projection coordinates become predictive of decoder NLL movement"
      evidence_needed: "correlation r > 0.3 and Gate E NLL delta < 0"
    - domain: "ASVD / activation-aware compression"
      candidate_principle: "activation-weighted singular vectors preserve perplexity-sensitive channels"
      expected_design_effect: "phone-forward-only calibration can repair projection at low cost"
      evidence_needed: "ASVD candidate beats incumbent JL on micro and full correlation screens"
    - domain: "zeroth-order gradient-aligned perturbation"
      candidate_principle: "perturbations aligned with task gradient reduce random-theta behavior"
      expected_design_effect: "theta updates stop behaving like random perturbations"
      evidence_needed: "matched random-theta controls no longer contain trained-theta NLL delta"
  frontier_prior_art:
    - source: "Johnson-Lindenstrauss"
      useful_pattern: "compact projection with fixed k=256 shape"
      insufficiency: "preserves geometry, not task gradient"
      zpp_adaptation: "retain shape; replace random matrix identity"
    - source: "ASVD/GPM"
      useful_pattern: "activation SVD with small calibration sample"
      insufficiency: "validated for compression/continual learning, not this polar update"
      zpp_adaptation: "treat as falsifiable projection hypothesis"
    - source: "GaLore/P-GAP"
      useful_pattern: "low-rank task-gradient subspace"
      insufficiency: "gradient computation may not be phone-native"
      zpp_adaptation: "offline static asset allowed only as design input; phone authority decides"
  rejected_conventional_paths:
    - path: "Run stronger random JL / larger polar loss"
      rejection_reason: "latest stronger polar improvement caused stronger NLL regression"
    - path: "Promote Gate D2A as learning"
      rejection_reason: "Gate E is sovereign and falsified"
    - path: "Run full C3/C4 now"
      rejection_reason: "would optimize a currently misaligned surrogate"
  maximal_plan_implications:
    - "Screen all predeclared projection families before declaring the architecture exhausted."
    - "Do not spend 12-hour full27 runs on candidates that fail micro-correlation."
    - "Any success must survive matched no-update and random-theta controls."
  hounds_of_popper_attacks:
    - "Candidate only improves correlation on a tiny sample but fails full27 Gate E."
    - "ASVD basis captures activation variance but not NLL sensitivity."
    - "Gradient-SVD asset is host-biased and does not transfer to phone-native scorer."
    - "Projection repair helps Gate D but the theta-only Vulkan update remains too weak or wrong-signed."
    - "Correlation screen is itself Goodharted unless confirmed by full Gate E."
```

## 8. Hypothesis Matrix

All hypotheses below are predeclared. They may be implemented in parallel by
separate agents, but authority phone execution is serialized by the phone
execution queue.

### H0: Incumbent Rademacher JL Baseline

Purpose: reproduce the misalignment signature under the current matrix.

Expected result:

```yaml
pearson_r: "<= 0.0 or statistically weak"
gate_e_status: falsified_or_random_theta_scale
```

Use H0 to calibrate the correlation test and wall-clock estimates. H0 cannot
promote; it is the negative control.

### H1: ASVD/GPM Activation-Covariance SVD Projection

Rank: primary.

Construction:

- collect layer-24 post-PLE-gate activations on phone;
- compute activation channel scale;
- run top-k SVD or randomized SVD;
- serialize `Phi_ASVD` as `[256,2560]` float32;
- record matrix SHA, calibration split SHA, layer/site, sample count, explained variance.

Primary reason: phone-forward-only calibration is feasible and shape-compatible
with the existing Phase 2/3/4 path.

### H2: Gradient-SVD / GaLore-Style Projection

Rank: secondary.

Construction:

- compute or import `dL_NLL/dh_layer24` over a representative calibration set;
- run top-k SVD over gradient vectors;
- serialize `Phi_GRAD` as `[256,2560]` float32;
- record whether gradient construction was phone-native or offline static asset.

Constraint: if gradient construction is not phone-native, the matrix is only a
candidate design asset. It has no authority until phone correlation, Gate D2A,
and Gate E decide it.

### H3: P-GAP / Gradient-Aligned Perturbation Policy

Rank: tertiary, but important if projection alone is insufficient.

Construction:

- use low-dimensional gradient or finite-difference estimate;
- constrain theta perturbations to have positive alignment with NLL descent;
- report alignment scalar, perturbation scale, and finite-difference cost.

Constraint: no unbounded phone finite-difference search. Use micro-budgeted
screens first.

### H4: RMT Spectral-Pruning Fallback

Rank: fallback.

Construction:

- compute activation covariance spectrum;
- detect Marchenko-Pastur bulk or equivalent signal/noise cutoff;
- prune to signal subspace and fill remaining rank deterministically;
- serialize `Phi_RMT` as `[256,2560]` float32.

Purpose: if ASVD and gradient-SVD are blocked, still avoid pure random JL.

### H5: Sign/Scale/Layer Schedule Controls

Rank: controls, not primary projection repair.

Test only after a projection candidate passes correlation:

- sign inversion;
- alpha scale ladder;
- layer 24 only vs layers 24..38;
- merge-site variants if available.

The previous alpha `-1.0` attempt was blocked fail-closed. Do not reinterpret
it as evidence.

## 9. Execution Topology

### 9.1 Lanes

```yaml
lanes:
  objective_governor:
    owns:
      - authority metric
      - pass/fail interpretation
      - no-promotion enforcement
  m_agent_orchestrator:
    owns:
      - lane dispatch
      - phone execution queue
      - auto-follow chain supervision
      - NEXT_HANDOFF validation
  projection_h1_asvd_lane:
    owns:
      - ASVD calibration builder
      - matrix schema and tests
  projection_h2_gradient_svd_lane:
    owns:
      - gradient-SVD feasibility
      - offline-static-asset declaration if needed
  projection_h3_pgap_lane:
    owns:
      - gradient-aligned perturbation policy
      - micro finite-difference budget
  projection_h4_rmt_lane:
    owns:
      - spectral pruning fallback
  phase34_runtime_lane:
    owns:
      - phone-local scripts
      - tmux/wakelock/detached execution
      - progress sidecars and status JSON
  gate_integrator_lane:
    owns:
      - correlation report
      - Gate D2A report
      - Gate E authority report
      - matched controls
  custody_provenance_lane:
    owns:
      - hashes
      - Comet metadata-only logging
      - raw-boundary scans
      - GitHub custody handoff
  hounds_of_popper_lane:
    owns:
      - falsification matrix
      - leakage/overclaim scans
      - random/control attacks
```

### 9.2 Parallelization Rule

Agents may parallelize source implementation, tests, matrix builders, schema
validation, and report review. The phone is a single authority resource and
must be scheduled through one queue. A candidate cannot enter a longer phone
stage until its previous phone stage has a metadata report with `status: pass`.

### 9.3 Required NEXT_HANDOFF

Every lane completion emits:

```yaml
NEXT_HANDOFF:
  to: "<next lane>"
  status: "<exact status>"
  artifacts:
    - "<metadata path plus sha256>"
  first_missing_green_field: "<none or exact field>"
  next_action: "<one bounded action>"
  prompt_to_send: "<self-contained prompt>"
  handoff_dispatch_status: "SENT_TO_NEXT_OWNER | TOOL_UNAVAILABLE"
  context_load:
    tier: "capsule_only | targeted_reference | full_prd | full_evidence"
    files_loaded: []
    extraction_mode: "targeted | full"
    rationale: ""
    omitted_heavy_sources: []
  provider_capability_capsule: "<include the capsule from this PRD when provider state can affect route>"
  research_escalation: "none | active_parallel_signal_lane | required with reason"
  nonclaims:
    - "no Gate E pass unless authority report says pass"
```

## 10. Implementation Surfaces To Create Or Repair

The execution agent should prefer existing modules and scripts before adding
new abstractions. Expected additions, if not already present:

```text
polymath_ai/polar/task_aligned_projection.py
scripts/termux/run_phase34_task_aligned_projection_chain.py
scripts/host/run_phase34_task_aligned_projection_launcher.py
scripts/host/build_phase34_projection_correlation_report.py
tests/test_task_aligned_projection.py
tests/test_phase34_task_aligned_projection_chain.py
tests/test_phase34_projection_correlation_report.py
```

Phone run roots:

```text
/data/data/com.termux/files/home/polymath_phase34_task_projection/<run_id>/
```

Host metadata roots:

```text
runtime/reports/apex_heterogeneous_cell/phase34_task_aligned_projection_<run_id>/
/Users/Zer0pa/Polymat AI/runtime/tmp/phase34_task_aligned_projection_<run_id>/
```

Required matrix schema:

```yaml
schema_version: phase34_task_aligned_projection_matrix_v1
candidate_id: "h0_rademacher | h1_asvd | h2_gradient_svd | h3_pgap | h4_rmt"
matrix_shape: [256, 2560]
matrix_dtype: float32
matrix_sha256: "<sha256>"
construction_surface: "phone_native | offline_static_asset | host_control_only"
calibration_record_count: integer
calibration_token_count: integer
layer_idx: 24
activation_capture_site: "post_ple_gate | hidden_state | gradient_h24 | other"
heldout_split_sha256: "<sha256>"
model_identity_sha256: "<sha256>"
tokenizer_identity_sha256: "<sha256>"
raw_matrix_binary_in_repo: false
raw_calibration_rows_in_repo: false
```

## 11. Staged Test Battery

For Phase34B, Stage 0 in Section 20.3 is mandatory before Stage A. The original
Stage A-G ladder below remains valid only after the candidate's source surface
has passed the new surface-readiness gate.

### Stage 0: Data Surface Readiness

Defined in Section 20.3. This gate must pass for the candidate family being
rerun:

- richer ASVD route: semantic activation capture, rank/effective-rank trend,
  and centered rank `>= 256`;
- gradient route: valid `dL_NLL/dh_layer24` surface;
- true P-GAP route: valid gradient surface plus gradient-aligned policy
  contract.

### Stage A: Static Contract Tests

Goal: reject bad candidates before phone runtime.

Maximum wall-clock target: 15 minutes.

Required:

- matrix shape `[256,2560]`;
- finite float32 values;
- row norm sanity;
- deterministic SHA from declared inputs;
- no raw matrix binary in repo;
- no secret/environment leakage;
- report schema validates.

Tests:

```text
pytest -q tests/test_task_aligned_projection.py tests/test_phase34_projection_correlation_report.py
```

### Stage B: Phone Provider And Runtime Preflight

Goal: confirm the phone can run autonomously.

Maximum wall-clock target: 10 minutes.

Required checks:

```bash
adb devices -l
adb forward tcp:18022 tcp:8022
ssh -i ~/.ssh/polymath_host -p 18022 -o ConnectTimeout=60 u0_a536@127.0.0.1 'date; whoami; source ~/.termux_agent_env; env | cut -d= -f1 | grep -E "^(GH_TOKEN|HF_TOKEN|COMET_API_KEY|COMET_WORKSPACE|COMET_PROJECT_NAME)$"'
```

Do not print env values. For current Apex logging, force:

```bash
export COMET_WORKSPACE=zer0pa-imc
export COMET_PROJECT_NAME=mobile-polymath-ai-training
```

### Stage C: Projection Construction Smoke

Goal: prove the candidate builder emits a matrix and metadata.

Wall-clock ladder:

```yaml
c1_micro:
  calibration_records: 4
  max_runtime_minutes: 20
c2_small:
  calibration_records: 32
  max_runtime_minutes: 90
c3_full_candidate:
  calibration_records: 128
  max_runtime_hours: 6
```

Promote to C3 only if C1 and C2 pass. If C2 explained-variance/spectrum is
degenerate or matrix norms are unstable, do not run C3; record falsifier.

### Stage D: Polar/NLL Correlation Screen

Goal: decide whether polar improvement predicts NLL improvement before full
Gate D/Gate E.

Stage D is a ladder, not a single expensive run:

```yaml
d1_micro_correlation:
  candidates: [h0, h1, h2, h3, h4 as available]
  records: 3
  perturbation_seeds: 2
  stop_if:
    - nonfinite_nll
    - wrong_shape
    - direction_agreement_fraction == 0
  purpose: catch broken integration

d2_small_correlation:
  candidates: surviving
  records: 9
  perturbation_seeds: 6
  pass_to_d3_requires:
    - pearson_r > 0.0
    - fraction_aligned >= 0.55
    - no_update_delta_per_token == 0.0 within numeric tolerance
  purpose: avoid spending full phone day on bad matrices

d3_full_correlation:
  candidates: top_2_survivors_max
  records: 27
  perturbation_seeds: 20
  pass_to_gate_d_requires:
    - pearson_r > 0.3
    - p_value < 0.05
    - fraction_aligned > 0.65
    - incumbent_h0_not_better_than_candidate
```

Correlation status is diagnostic only. It never promotes learning.

### Stage E: Matched Controls

Every candidate promoted beyond correlation must run:

- no-update replay on the same phone-native surface;
- random-theta controls using the same projection identity and scale;
- sign/scale controls only when a candidate passes correlation.

No-update must remain exact-zero or explainable within numeric tolerance. If
no-update is non-zero, stop and repair the scorer/runtime before testing more
candidates.

### Stage F: Gate D2A Candidate Run

Goal: verify the candidate still produces finite polar heldout improvement
through the actual Phase 3/4 update path.

Run ladder:

```yaml
f1_gate_d2a_mini:
  heldout_packets: 250
  pass_requires:
    - finite_before_after_loss
    - loss_delta < 0
    - theta_post_sha256_distinct_if_update_expected
    - magnitude_invariant_pass

f2_gate_d2a_full:
  heldout_packets: 2500
  pass_requires:
    - finite_before_after_loss
    - loss_delta < 0
    - evaluated_answer_bearing_steps >= 2344
    - metadata_only_comet_logged
```

### Stage G: Gate E Phone-Native Authority Run

Goal: decide the science.

Do not run full27 until Stage D3, Stage E, and Stage F pass.

Run ladder:

```yaml
g1_gate_e_one_record_probe:
  records: 1
  purpose: integration and timing only
  pass_requires:
    - before_prediction_record_count == 1
    - after_prediction_record_count == 1
    - native_polar_consumed_by_logits == true

g2_gate_e_subset:
  records: 9
  purpose: early falsifier
  stop_if:
    - nll_delta_per_token >= 0 and worse_than_random_control
    - scorer/runtime non-determinism

g3_gate_e_full27:
  records: 27
  per_arm_timeout_seconds: 43200
  auto_follow_on: "before -> after -> scorer -> perplexity_report -> comet_log"
  pass_requires:
    - nll_delta_per_token < 0
    - before_after_record_count == 27
    - status == gate_e_token_nll_perplexity_pass
```

If G2 is negative but statistically ambiguous, Objective Governor decides
whether G3 is justified. If G2 is clearly worse than random controls, do not
spend G3 wall-clock.

## 12. Autonomous Phone Chain Requirements

Every phone run must be launchable as a detached, resumable chain.

Required phone-local files:

```text
chain_state.json
chain_events.jsonl
supervisor_status.json
supervisor_events.jsonl
STOP
reports/*.json
metadata/*.json
predictions/*.progress.jsonl
```

Required behavior:

- source `~/.termux_agent_env` without printing values;
- force `COMET_WORKSPACE=zer0pa-imc` and
  `COMET_PROJECT_NAME=mobile-polymath-ai-training` unless the run is explicitly
  an older `zer0pa` lane;
- acquire `termux-wake-lock`;
- run inside `tmux -L polymath` or equivalent detached supervision;
- write heartbeat/status every stage;
- auto-follow on success;
- fail closed and stop on first missing green field;
- support `STOP` file for safe pause;
- never require Mac to remain attached after launch;
- never copy raw rows/tensors/theta/model data into git;
- produce collection commands for metadata-only reports.

Auto-follow chain:

```text
preflight
  -> candidate_matrix_build
  -> matrix_static_tests
  -> d1_micro_correlation
  -> d2_small_correlation
  -> d3_full_correlation
  -> matched_no_update_control
  -> matched_random_theta_control
  -> gate_d2a_mini
  -> gate_d2a_full
  -> gate_e_one_record_probe
  -> gate_e_subset
  -> gate_e_full27
  -> comet_metadata_log
  -> custody_manifest
```

The chain must skip later stages automatically when a stage fails and record
the exact falsifier.

## 13. Wall-Clock Governance

Do not optimize for a narratable win. Optimize for authority evidence per
phone-hour.

Rules:

- Never launch a 12-hour full27 arm for a candidate that has not passed
  correlation and controls.
- Run H0/H1/H2/H3/H4 code and static tests in parallel; run phone screens in a
  predeclared queue.
- Limit D3 full-correlation to the top two candidates unless all candidates
  are close and Objective Governor explicitly authorizes more.
- Use one-record Gate E probes to validate integration, not to infer science.
- Use G2 subset as a kill gate when it is decisively negative.
- If two candidates fail for the same integration reason, stop candidate runs
  and repair the shared harness.
- If SSH banner timeouts occur while ADB shows the runner alive, do not kill
  the run; use ADB process checks and the documented Termux `sshd` nudge.
- After Phase34 candidate exhaustion, do not spend phone-hour on D1 or later
  candidate reruns until Stage 0 is green for that route.
- Do not rerun historical H3 finite-difference P-GAP to chase `p < 0.05`.
- Do not reuse H4 RMT as the basis for true P-GAP.
- Do not relax thresholds after observed evidence.

## 14. Falsification Matrix

```yaml
falsifiers:
  projection_matrix_invalid:
    field: matrix_shape_or_finite_check
    action: stop_candidate
  calibration_not_phone_authority:
    field: construction_surface
    action: allow_only_as_static_asset_until_phone_screened
  no_update_nonzero:
    field: no_update_delta_per_token
    action: stop_all_candidates_and_repair_scorer
  random_theta_contains_candidate:
    field: trained_delta_inside_random_range
    action: no_promotion_candidate_may_continue_only_for_research
  correlation_negative:
    field: pearson_r
    action: stop_candidate_before_gate_d
  correlation_underpowered:
    field: p_value_or_fraction_aligned
    action: repeat_only_if_wall_clock_budget_and_effect_signal_justify
  gate_d_no_polar_improvement:
    field: polar_loss_delta
    action: stop_candidate_before_gate_e
  gate_e_nll_regression:
    field: nll_delta_per_token
    action: falsified_no_promotion
  gate_e_scorer_blocked:
    field: native_polar_contract_or_record_count
    action: repair_runtime_then_rerun_same_predeclared_arm_once
  comet_missing_when_required:
    field: comet_status
    action: metadata_repair_once_no_rerun_of_accepted_phone_work
  raw_boundary_violation:
    field: raw_boundary_scan
    action: invalidate_report_until sanitized; do not upload
  rerun_requested_without_new_surface:
    field: phase34b_surface_readiness
    action: reject_rerun_before_stage_0
  asvd_capture_semantics_unverified:
    field: post_gelu_ple_gate_semantics_reverified
    action: stop_h1r_before_matrix_build
  asvd_calibration_manifest_not_stratified:
    field: calibration_manifest_strata
    action: stop_h1r_before_phone_capture
  activation_rank_plateau_below_projection_dim:
    field: centered_rank_trend
    action: fail_h1r_surface_before_matrix_build
  activation_rank_below_projection_dim_after_revised_capture:
    field: centered_rank_estimate
    action: stop_h1r_before_correlation
  gradient_surface_absent_or_semantically_mismatched:
    field: dL_NLL_dh_layer24_gradient_surface
    action: stop_h2r_and_h3r_before_matrix_or_policy_build
  offline_gradient_phone_fidelity_probe_failed:
    field: predicted_vs_phone_native_measured_nll_delta
    action: reject_gradient_asset_as_host_biased
  pgap_policy_missing_true_gradient_alignment:
    field: gradient_alignment_condition
    action: stop_h3r_before_d1
  phase34b_d2_signal_too_weak:
    field: pearson_r_or_fraction_aligned
    action: stop_candidate_before_d3_to_protect_phone_hours
  falsified_h4_surface_reused_as_true_pgap:
    field: true_pgap_source_surface
    action: stop_h3r_as_naming_drift
```

## 15. Evidence Ledger

Each run writes:

```yaml
run_report:
  schema_version: phase34_task_aligned_projection_run_report_v1
  run_id: "<id>"
  candidate_id: "<h1_asvd etc>"
  phone_serial: FY25013101C8
  git_head_sha: "<sha>"
  dirty_worktree_summary_sha256: "<sha over metadata only>"
  projection_matrix_report: "<path and sha>"
  correlation_report: "<path and sha>"
  controls_report: "<path and sha>"
  gate_d2a_report: "<path and sha>"
  gate_e_report: "<path and sha>"
  comet_result: "<path and sha>"
  raw_boundary_scan:
    raw_rows_embedded: false
    raw_tensors_embedded: false
    theta_binaries_embedded: false
    secrets_embedded: false
  nonclaims:
    - "no promotion unless gate_e_report status passes"
```

Comet metrics must be numeric and authority-linked. Dashboard presence is not
evidence.

## 16. Research Escalation

Runtime research remains active. Escalate only with bounded packets:

```yaml
research_escalation:
  mode: research_note | bounded_research_sprint
  trigger: uncertainty_smell | anomalous_failure | anomalous_success | hardware_signal | performance_signal | geometry_signal | repeated_field | architecture_contradiction
  repeated_or_blocking_field: "<field>"
  why_execution_cannot_decide: "<reason>"
  why_this_matters_now: "<reason>"
  source_boundary:
    - "<paths or papers>"
  formula_or_dataflow_proposal: "<testable idea>"
  test: "<bounded test>"
  stop_condition: "<stop>"
  expected_metric_impact: "<metric>"
  return_lane: "<lane>"
```

Mandatory research triggers:

- current PRD candidate set exhausted;
- ASVD passes correlation but fails Gate E;
- gradient-SVD beats ASVD despite offline construction;
- P-GAP produces a positive subset Gate E result;
- PLE timing/stall dominates phone runtime;
- two candidates fail from the same layer/merge-site issue;
- QNN graph boundary becomes the first missing green field.

After candidate exhaustion, the return lane must be one of
`richer_asvd_calibration_surface`, `layer24_gradient_source_program`, or
`true_gradient_aligned_pgap_after_gradient_surface`.

## 17. Initial M-Agent Launch Packet

Use this packet to launch the dedicated execution thread. The new thread owns
implementation and execution. This thread remains operational oversight.

```yaml
M_AGENT_LAUNCH:
  role: phase34_task_aligned_projection_execution_orchestrator
  objective: "Execute PRD-PHASE34-TASK-ALIGNED-PROJECTION-PHONE-NATIVE-GEMMA4-E4B-POLAR-TRAINING-2026-07-08 end to end until Gate E pass or all predeclared candidates are falsified/exact-blocked."
  required_first_reads:
    - docs/PRD-PHASE34-TASK-ALIGNED-PROJECTION-PHONE-NATIVE-GEMMA4-E4B-POLAR-TRAINING-2026-07-08.md
    - docs/GEMMA-4-TRAINING-PIPELINE-SCIENCE-ENGINEERING-UPDATE-2026-07-06.md
    - docs/APEX-GATE-E-SCIENCE-REPORT-SEQUENCE-2026-07-06/HANDOVER_FOR_NEXT_AGENT_2026-07-08.md
    - /Users/Zer0pa/Polymat AI/Task-Aligned Projection Design for Phone-Native Gemma-4-E4B Polar Training.md
  immediate_actions:
    - verify phone ADB/SSH and source ~/.termux_agent_env without printing values
    - force current Apex Comet target zer0pa-imc/mobile-polymath-ai-training
    - implement static matrix/report schemas and tests
    - implement H0 and H1 first; start H2/H3/H4 lanes in parallel if separate workers are available
    - launch only Stage A/B/C/D micro-gates before any full Gate D/Gate E
  first_missing_green_field: phase34_task_aligned_projection_static_harness_absent
  provider_capability_capsule: "use Section 6"
  nonclaims:
    - Gate E is currently falsified.
    - No C3/C4/D3 continuation is authorized.
    - Correlation pass is not promotion.
    - Gate D polar pass is not language-model improvement.
```

## 18. Current Gate And Next Owner

```yaml
current_gate: phase34b_gradient_source_and_richer_asvd_readiness
current_owner: prd_steward_then_gradient_source_execution_orchestrator
next_action: implement the Phase34B surface-readiness tools before any candidate rerun
first_missing_green_field: phase34b_gradient_source_surface_absent
handoff_dispatch_status: USER_AUTHORIZED_PRD_RESEARCH_REVISION_20260709
```

## 19. Amendment Log

```yaml
amendments:
  - date: 2026-07-08
    change: "Initial living PRD created from task-aligned projection design and July 6/8 Gate E falsification context."
    reason: "Random JL polar surrogate improved while phone-native decoder NLL regressed; repair requires task-aligned projection and staged falsification."
    objective_effect: "reroutes from C3/C4 continuation to projection repair"
    nonclaims_preserved:
      - no Gate E pass
      - no language-model improvement claim
      - no C3/C4/D3 authorization
    handoffs_to_regenerate:
      - M_AGENT_LAUNCH after any major scope or provider access change
  - date: 2026-07-09
    change: "Extend PRD after Phase34 candidate exhaustion with a Phase34B gradient-source and richer-ASVD continuation route."
    reason: "Report 06 and design diff showed the design brief's strongest ideas were not authentically tested: ASVD was blocked by rank, Gradient-SVD was blocked by missing dL_NLL/dh_layer24, and H3 was only a finite-difference approximation."
    objective_effect: "reroutes from rerunning exhausted candidates to building missing measurement surfaces, then rerunning only newly valid ASVD, Gradient-SVD, and true P-GAP candidates through unchanged gates"
    nonclaims_preserved:
      - no Gate E pass
      - no language-model improvement claim
      - no D2A authorization
      - no Gate E full27 authorization
      - no C3/C4/D3 promotion path
      - no H5 controls until a new candidate passes D3
    handoffs_to_regenerate:
      - PHASE34B_M_AGENT_LAUNCH
      - provider_capability_capsule
      - Comet live metric schema
  - date: 2026-07-09
    change: "Tighten Phase34B Section 20.3 from gate-only readiness into concrete surface-construction procedures and add offline-gradient phone-fidelity checks."
    reason: "Pre-execution review identified that H1/H2 could otherwise hit the same blockers again: rank-deficient activation calibration and host-biased or absent dL_NLL/dh_layer24 gradients."
    objective_effect: "requires stratified ASVD calibration construction, rank-trend/plateau diagnostics, offline gradient artifact construction, phone-native finite-difference fidelity probe, and stricter Phase34B D2 before D3"
    nonclaims_preserved:
      - no Gate E pass
      - no H2 authority from offline gradient construction alone
      - no candidate rerun before Stage 0
      - no threshold relaxation
    handoffs_to_regenerate:
      - PHASE34B_M_AGENT_LAUNCH
      - richer_asvd_calibration_surface lane brief
      - layer24_gradient_source_program lane brief
      - Comet live metric schema
```

## 20. Phase34B Continuation Amendment

This section supersedes Section 8 and Section 17 for work after report `06`,
adds Stage 0 to Section 11, and tightens Sections 13, 14, and 16. Sections 1-16
remain binding unless explicitly tightened here.

The new route is not "rerun the near miss." The new route is:

```text
build missing measurement surfaces
  -> build authentically sourced ASVD / Gradient-SVD / true P-GAP candidates
  -> run unchanged D1/D2/D3 correlation gates
  -> run controls only after D3 pass
  -> run Gate D2A and Gate E only after controls pass
```

### 20.1 Phase34B Objective Contract

```yaml
phase34b_objective:
  name: phase34b_gradient_source_and_richer_asvd_continuation
  governing_authority_metric: phone_native_decoder_token_nll_per_token
  gate_e_current_status: falsified
  authority_after_minus_before: +0.01624497490593768
  promotion_allowed: false
  first_missing_green_field: phase34b_gradient_source_surface_absent
  primary_goal: "Create the missing dL_NLL/dh_layer24 measurement surface and richer activation calibration surface needed to test the design brief's strongest routes."
  allowed_next_work:
    - implement richer ASVD activation calibration and rank-trend tooling
    - implement or import a valid dL_NLL/dh_layer24 gradient-source artifact
    - implement true gradient-aligned P-GAP only after the gradient source exists
    - add live metadata-only Comet logging for every executable gate
  forbidden_next_work:
    - rerun H3 only to chase p_value
    - relitigate H4 RMT under the exhausted PRD
    - lower D3 p-value or fraction-aligned thresholds
    - run H5 controls without a new D3-passing candidate
    - launch Gate D2A or Gate E full27 before Phase34B predecessor gates pass
```

### 20.2 Corrected Candidate Taxonomy

The previous H3 naming is now frozen as a historical approximation:

```yaml
historical_phase34_disposition:
  h0_rademacher: negative_control_only
  h1_asvd_initial: blocked_fail_closed_activation_capture_rank_below_projection_dim
  h2_gradient_svd_initial: blocked_fail_closed_dL_NLL_dh_layer24_gradient_surface_absent
  h3_finite_difference_pgap_approximation: d3_falsified_p_value_above_stage_threshold
  h4_rmt_initial: d3_falsified_fraction_aligned_below_stage_threshold
  h5_controls_initial: unauthorized_no_projection_candidate_passed_d3

phase34b_predeclared_candidates:
  h1r_richer_asvd:
    purpose: "Retest activation-based ASVD after richer, stratified calibration proves centered rank >= 256."
    depends_on:
      - phase34b_activation_calibration_surface_pass
    nonclaim: "Initial H1 was blocked, not disproven."
  h2r_gradient_svd_galore:
    purpose: "Build Phi_GRAD from a valid dL_NLL/dh_layer24 gradient matrix."
    depends_on:
      - phase34b_gradient_source_surface_pass
    nonclaim: "Offline construction is a design asset until phone-native screens decide."
  h3r_true_gradient_aligned_pgap:
    purpose: "Build perturbations satisfying a declared NLL-gradient alignment condition."
    depends_on:
      - phase34b_gradient_source_surface_pass
      - h2r_gradient_subspace_report
    nonclaim: "The historical H3 finite-difference policy was not true P-GAP."
  h4r_rmt_optional_diagnostic:
    purpose: "Allowed only if a revised PRD predeclares a new signal-rank/effective-rank precondition."
    default_status: not_authorized_under_current_amendment
```

### 20.3 Surface Readiness Gates

Phase34B begins with data-surface gates, not candidate reruns.

```yaml
surface_gate_a_provider_and_comet_readiness:
  status_required: pass_or_exact_blocked_report
  checks:
    - phone_adb_termux_metadata_safe_check_without_secret_values
    - hugging_face_metadata_safe_check_when_corpus_or_model_pull_is_needed
    - github_metadata_safe_check_when_custody_commit_or_pr_is_needed
    - comet_sdk_metadata_safe_check
  pass_requires:
    - COMET_WORKSPACE_forced_to_zer0pa-imc
    - COMET_PROJECT_NAME_forced_to_mobile-polymath-ai-training
    - report_contains_no_secret_values

surface_gate_b_richer_activation_calibration:
  goal: "Repair H1's rank blocker before rebuilding Phi_ASVD."
  construction_method:
    b0_manifest:
      action: "Build a metadata-only stratified calibration manifest before capture."
      source_pool: "training/calibration corpus records only; no Gate E heldout overlap"
      target_record_count: "128 initial; predeclared expansion to 256/384/512 if rank trend has not saturated"
      report_only:
        - record_id_set_sha256
        - source_bucket_counts
        - length_bucket_counts
        - answer_bearing_bucket_counts
        - token_position_bucket_counts
        - baseline_nll_bucket_counts_if_available
        - selected_position_policy_sha256
      forbidden:
        - raw text
        - raw token ids
        - raw token files
    b1_stratified_capture:
      action: "Run phone-native layer-24 post-PLE-gate activation capture in chunks with raw rows outside git."
      chunk_size_records: "8 to 16"
      row_selection_policy:
        - first_non_special_position_bucket
        - middle_context_position_bucket
        - answer_or_target_position_bucket_when_available
        - late_context_position_bucket
        - high_baseline_nll_bucket_when_available
      raw_capture_location: "/Users/Zer0pa/Polymat AI/runtime/tmp/phase34b_<run_id>/activation_capture/ and phone private run root only"
      metadata_per_chunk:
        - native_report_sha256
        - capture_sha256
        - capture_bytes
        - row_count
        - record_count
        - row_norm_min
        - row_norm_mean
        - row_norm_max
        - nonfinite_count
    b2_semantic_reverification:
      action: "Prove the capture is exactly layer 24 post-GELU/post-PLE-gate hidden pre-native-polar, not a nearby residual surface."
      pass_requires:
        - native_report_field_site_equals_post_ple_gate_hidden_pre_native_polar
        - layer_idx_equals_24
        - width_equals_2560
        - runner_sha256_recorded
        - producer_wrapper_sha256_recorded
        - source_symbols_or_contract_strings_reference_activation_capture_site
        - no raw_activation_capture_rows_embedded
    b3_rank_trend:
      action: "Compute centered-rank and effective-rank trend after each chunk before matrix construction."
      stop_if:
        - nonfinite_count_nonzero
        - centered_rank_plateaus_below_256_after_512_records_or_1024_rows
        - top256_energy_ratio_degenerate_with_effective_rank_below_128
      output_report: richer_asvd_calibration_surface_report
    b4_asvd_alpha_sensitivity:
      action: "Only after centered_rank >= 256, test ASVD activation scaling alphas as matrix candidates before correlation."
      alpha_grid: [0.0, 0.25, 0.5, 0.75, 1.0]
      pass_to_matrix_build_requires:
        - each_alpha_report_has_finite_matrix_or_exact_blocker
        - selected_alpha_predeclared_by_rank_energy_and_norm_sanity
  minimum_pre_matrix_requirements:
    calibration_record_count: ">= 128 unless a smaller count is predeclared with rank-trend justification"
    calibration_row_count: ">= 512 target; must exceed projection_dim with margin"
    centered_rank_estimate: ">= 256"
    capture_site: post_ple_gate_hidden_pre_native_polar
    layer_idx: 24
    dtype: float32
    shape_width: 2560
    raw_rows_in_repo: false
  required_diagnostics:
    - centered_rank_trend_by_chunk
    - effective_rank
    - top256_energy_ratio
    - singular_value_1
    - singular_value_256
    - singular_value_last
    - unique_record_count
    - calibration_context_diversity_summary_sha256
    - post_gelu_ple_gate_semantics_reverified
  first_missing_green_field_if_rank_fails: activation_capture_rank_below_projection_dim

surface_gate_c_gradient_source:
  goal: "Create the missing 'how does nudging layer 24 change real NLL' measurement."
  construction_method:
    c0_identity_and_corpus_lock:
      action: "Bind the offline/backward surface to the same model, tokenizer, layer, capture site, and calibration corpus identities used by phone screening."
      pass_requires:
        - model_identity_sha256_matches_gate_e_model_identity_or_exact_mapping_report
        - tokenizer_identity_sha256_matches_gate_e_tokenizer_identity_or_exact_mapping_report
        - calibration_record_id_set_sha256_recorded
        - heldout_overlap_count_equals_0
        - layer_idx_equals_24
        - capture_site_equals_post_ple_gate_hidden_pre_native_polar
    c1_offline_backward_capture:
      preferred_method: offline_autograd_gradient_calibration
      action: "Run frozen-model forward/backward on workstation or RunPod; hook the layer-24 post-PLE-gate hidden tensor; compute decoder-token NLL; capture dL_NLL/dh_layer24 rows for selected positions."
      constraints:
        - no base model parameter update
        - no optimizer step
        - no raw gradient rows in repo
        - no raw token rows in repo
        - no token text in reports
      output_raw_location: "/Users/Zer0pa/Polymat AI/runtime/tmp/phase34b_<run_id>/gradient_source/ or provider scratch only"
      output_metadata_report: layer24_gradient_surface_report
    c2_gradient_quality_report:
      action: "Validate the gradient matrix before any SVD."
      required_metrics:
        - gradient_row_count
        - gradient_width
        - dtype
        - finite_values
        - gradient_norm_min
        - gradient_norm_mean
        - gradient_norm_max
        - zero_norm_count
        - centered_rank_estimate
        - effective_rank
        - top256_energy_ratio
        - singular_value_1
        - singular_value_256_if_available
        - singular_value_last
      stop_if:
        - gradient_row_count_below_256_without_predeclared_adaptive_rank
        - width_not_2560
        - nonfinite_gradient_values
        - zero_norm_gradient_rows
    c3_phone_fidelity_probe:
      action: "Verify offline gradient directions against small phone-native finite-difference NLL probes before trusting H2/H3."
      probe_surface: "phone-native decoder-token NLL, layer-24 perturbation injection, metadata-only reports"
      records: 3
      direction_count: "8 to 12"
      directions:
        - top_gradient_svd_direction
        - mixed_gradient_subspace_direction
        - orthogonalized_control_direction
        - random_control_direction
      epsilon_ladder: [0.003, 0.01]
      predicted_delta: "<dL_NLL/dh_layer24, epsilon * direction>"
      measured_delta: "phone_native_nll(epsilon_direction) - phone_native_nll(no_update)"
      pass_requires:
        - no_update_delta_per_token == 0.0 within numeric tolerance
        - directional_sign_agreement_fraction >= 0.75
        - pearson_r_predicted_vs_measured_delta > 0.3
        - gradient_directions_outperform_random_controls_on_sign_agreement
      fail_action: "reject offline gradient asset as host-biased; do not build H2R or H3R from it"
  allowed_methods:
    offline_autograd_gradient_calibration:
      description: "One-time workstation/cloud gradient capture on the frozen current model, producing a static dL_NLL/dh_layer24 matrix."
      authority_status: design_asset_until_phone_screened
    limited_backward_to_layer24:
      description: "A bounded backward implementation only to layer 24 hidden state, used for calibration, not base-model training."
      authority_status: design_asset_until_phone_screened
    finite_difference_directional_derivative:
      description: "Optional diagnostic for gradient-source validation; cannot be labeled true P-GAP by itself."
      authority_status: diagnostic_only_unless tied_to_valid_gradient_subspace
  gradient_artifact_contract:
    semantic: representative dL_NLL/dh_layer24 gradient row matrix
    expected_shape: "[N,2560]"
    dtype: float32_or_float64_declared
    layer_idx: 24
    capture_site: post_ple_gate_hidden_pre_native_polar
    model_identity_sha256: required
    tokenizer_identity_sha256: required
    calibration_corpus_identity_sha256: required
    heldout_overlap_count: 0
    row_count: ">= 256 preferred; any lower count must fail closed unless adaptive-rank is predeclared"
    finite_values: true
    raw_gradient_rows_in_repo: false
    raw_gradient_rows_embedded: false
    gradient_matrix_sha256: required
    gradient_matrix_path_sha256: required
  first_missing_green_field_if_absent: dL_NLL_dh_layer24_gradient_surface_absent
  first_missing_green_field_if_fidelity_fails: offline_gradient_phone_fidelity_probe_failed
```

### 20.4 Candidate Rerun Authorization

No candidate rerun is authorized until its source surface has passed.

```yaml
candidate_rerun_authorization:
  h1r_richer_asvd:
    authorize_matrix_build_only_if:
      - surface_gate_b_richer_activation_calibration_pass
      - centered_rank_estimate >= 256
      - post_gelu_ple_gate_semantics_reverified
    next_gate_after_matrix: d1_micro_correlation
  h2r_gradient_svd_galore:
    authorize_matrix_build_only_if:
      - surface_gate_c_gradient_source_pass
      - gradient_artifact_contract_pass
    next_gate_after_matrix: d1_micro_correlation
  h3r_true_gradient_aligned_pgap:
    authorize_policy_build_only_if:
      - surface_gate_c_gradient_source_pass
      - gradient_subspace_report_pass
      - policy_report_proves_alignment_condition
      - perturbation_magnitude_bound_declared
    next_gate_after_policy: d1_micro_correlation
  h5_controls:
    authorize_only_if:
      - one_of: [h1r_richer_asvd_d3_pass, h2r_gradient_svd_galore_d3_pass, h3r_true_gradient_aligned_pgap_d3_pass]
```

D1 and D3 thresholds from Section 11 remain unchanged. D2 is tightened for
Phase34B only to avoid spending D3 phone-hours on weak signals:

```yaml
d2_small_correlation_phase34b_pass_requires:
  pearson_r: "> 0.2"
  fraction_aligned: ">= 0.60"
  no_update_delta_per_token: "0.0 within numeric tolerance"
  max_single_observation_leverage: "predeclared diagnostic must not show one observation dominates the sign"
  note: "This tightens the original D2 pearson_r > 0.0 rule for Phase34B only to protect D3 phone-hours."

d3_full_correlation_pass_requires:
  pearson_r: "> 0.3"
  p_value: "< 0.05"
  fraction_aligned: "> 0.65"
  incumbent_h0_not_better_than_candidate: true
```

Close or near-threshold results are research signals only. They are not passes.

### 20.5 Live Comet Logging Contract

Comet is not evidence by itself, but live numeric logging is required for
operator visibility and custody. Phase34B must log metrics as stages happen,
not only after the final report.

Implementation should use existing secret-safe helpers:

```text
polymath_ai/telemetry/comet_logging.py
scripts/host/log_apex_metadata_report_to_comet.py
```

Every executable stage must emit a metadata report first, then log that report
to Comet with safe assets only. Raw rows, token files, prediction JSONLs,
theta binaries, env files, and payload dumps remain forbidden.

```yaml
comet_live_logging:
  workspace: zer0pa-imc
  project_name: mobile-polymath-ai-training
  run_name_template: "phase34b-{run_id}-{stage_id}-{candidate_id_or_surface}"
  required_tags:
    - apex
    - phase34b
    - metadata-only
    - gate-e-falsified-baseline
  stage_metric_groups:
    provider_readiness:
      - phone_adb_visible
      - phone_ssh_metadata_check_pass
      - comet_safe_check_pass
      - hf_safe_check_pass_when_needed
      - github_safe_check_pass_when_needed
    activation_calibration:
      - calibration_record_count
      - calibration_row_count
      - centered_rank_estimate
      - effective_rank
      - top256_energy_ratio
      - singular_value_1
      - singular_value_256
      - singular_value_last
      - raw_boundary_ok
    gradient_source:
      - gradient_row_count
      - gradient_width
      - gradient_finite
      - gradient_norm_min
      - gradient_norm_mean
      - gradient_norm_max
      - heldout_overlap_count
      - raw_boundary_ok
    matrix_build:
      - matrix_shape_rows
      - matrix_shape_cols
      - matrix_finite
      - row_norm_min
      - row_norm_mean
      - row_norm_max
      - blocker_count
    correlation:
      - observation_count
      - perturbation_seed_count
      - pearson_r
      - p_value
      - fraction_aligned
      - nll_improvement_mean
      - polar_improvement_mean
      - blocker_count
    controls_and_authority:
      - no_update_delta_per_token
      - random_theta_min_delta_per_token
      - random_theta_max_delta_per_token
      - gate_d2a_loss_delta
      - gate_e_nll_delta_per_token
      - gate_e_record_count
      - gate_e_token_count
  live_comments:
    allowed:
      - stage_start
      - stage_pass
      - stage_falsified
      - stage_blocked_fail_closed
      - next_gate
    forbidden:
      - raw_row_excerpt
      - token_text
      - prediction_payload
      - secret_or_env_value
  comet_failure_policy:
    nonpromoted_surface_gates: "record blocked Comet result and continue only if Objective Governor marks Comet non-authority for that surface"
    promoted_evidence_gates: "metadata repair once; no promotion until comet_status == logged"
    dashboard_rule: "dashboard presence is operator visibility, not authority evidence"
```

### 20.6 Provider Capability Capsule

```yaml
provider_capability_capsule:
  matrix_artifact: runtime/reports/apex_heterogeneous_cell/phase34_task_aligned_projection_20260708T115449Z/DRIFT_AND_PREFLIGHT_REPORT.md
  providers:
    phone_adb_termux:
      role: RedMagic 10 Pro authority execution target for phone-native screening and Gate E
      current_classification: PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES
    hugging_face:
      role: corpus/model revision source and metadata-only provenance
      current_classification: PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES
    github:
      role: custody commits and PR surface only when explicitly authorized
      current_classification: PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES
    comet:
      role: live numeric operator visibility and metadata-only authority-linked logging
      current_classification: PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES
    runpod:
      role: optional offline gradient calibration host or QAIRT/QNN tool host if local/phone cannot build the static asset
      current_classification: PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES
  secret_policy: "Never print, copy, summarize, commit, or include token/key values."
```

### 20.7 Implementation Surfaces To Add Or Repair

Prefer existing modules and scripts before adding new abstractions.

Existing surfaces to reuse:

```text
polymath_ai/polar/task_aligned_projection.py
scripts/host/build_phase34_asvd_projection_matrix.py
scripts/host/build_phase34_rmt_projection_matrix.py
scripts/host/build_phase34_projection_correlation_report.py
scripts/host/build_phase34_h3_pgap_policy.py
scripts/host/run_phase34_task_aligned_projection_launcher.py
scripts/host/run_c5_phase34_qa_inference_producer.py
scripts/host/log_apex_metadata_report_to_comet.py
scripts/termux/run_phase34_task_aligned_projection_chain.py
scripts/termux/run_phase34_phone_accel_prereqs.py
integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/src/backends/c5_full_decoder_runtime.cpp
integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/src/backends/c5_qa_inference.cpp
tests/test_task_aligned_projection.py
tests/test_phase34_projection_correlation_report.py
tests/test_phase34_task_aligned_projection_chain.py
tests/test_c5_phase34_qa_inference_producer.py
tests/test_comet_logging.py
```

New or repaired surfaces required before reruns:

```text
polymath_ai/polar/gradient_source.py
polymath_ai/polar/phase34b_provider_readiness.py
scripts/host/build_phase34_gradient_source_report.py
scripts/host/build_phase34_gradient_svd_projection_matrix.py
scripts/host/build_phase34_true_pgap_policy.py
scripts/host/build_phase34_activation_rank_trend_report.py
scripts/host/build_phase34_asvd_calibration_manifest.py
scripts/host/build_phase34_gradient_phone_fidelity_report.py
scripts/host/build_phase34b_provider_readiness_report.py
scripts/host/log_phase34b_live_stage_to_comet.py
tests/test_phase34_gradient_source.py
tests/test_phase34_true_pgap_policy.py
tests/test_phase34_activation_rank_trend.py
tests/test_phase34_asvd_calibration_manifest.py
tests/test_phase34_gradient_phone_fidelity.py
tests/test_phase34b_provider_readiness.py
```

Known implementation gaps from the post-exhaustion audit:

```yaml
implementation_gaps:
  richer_asvd_calibration:
    missing:
      - stratified_calibration_manifest
      - effective_rank_policy
      - unique_token_context_distribution_tracking
      - asvd_alpha_sensitivity_sweep
      - post_gelu_ple_gate_semantic_reverification_report
      - rank_plateau_stop_condition
  gradient_source:
    missing:
      - dL_NLL_dh_layer24_gradient_matrix_importer_or_builder
      - build_h2_gradient_svd_projection
      - limited_backward_to_layer24_or_offline_autograd_contract
      - phone_native_gradient_fidelity_probe
  true_pgap:
    missing:
      - validated_gradient_subspace_policy
      - pre_d1_alignment_proof
      - perturbation_magnitude_proof
  live_comet:
    missing:
      - phase34b_stage_metric_mapper
      - live_stage_logging_wrapper
      - chain_integration_for_comet_stage_updates
  provider_readiness:
    missing:
      - phase34_specific_provider_capsule_report
      - safe_phone_hf_github_comet_checks_without_secret_values
```

### 20.8 PHASE34B_M_AGENT_LAUNCH

```yaml
PHASE34B_M_AGENT_LAUNCH:
  role: phase34b_gradient_source_and_richer_asvd_execution_orchestrator
  objective: "Build missing gradient and richer activation measurement surfaces, then rerun only authentically sourced H1R/H2R/H3R candidates through unchanged Phase34 gates."
  required_first_reads:
    - docs/PRD-PHASE34-TASK-ALIGNED-PROJECTION-PHONE-NATIVE-GEMMA4-E4B-POLAR-TRAINING-2026-07-08.md
    - docs/APEX-GATE-E-SCIENCE-REPORT-SEQUENCE-2026-07-06/06_APEX-GATE-E-TASK-ALIGNED-PROJECTION-CANDIDATE-EXHAUSTION-ENGINEERING-SCIENCE-REPORT-2026-07-09.md
    - runtime/reports/apex_heterogeneous_cell/phase34_task_aligned_projection_20260708T115449Z/DESIGN_DIFF_ANALYSIS_20260709.md
    - /Users/Zer0pa/Polymat AI/Task-Aligned Projection Design for Phone-Native Gemma-4-E4B Polar Training.md
  immediate_actions:
    - implement metadata-only provider and Comet safe-check report
    - implement activation rank-trend report over richer calibration chunks
    - implement gradient-source artifact contract and blocker report
    - implement Gradient-SVD matrix builder only after gradient-source contract exists
    - rename future H3 work to true_gradient_aligned_pgap and reserve finite_difference_pgap_approximation for historical/diagnostic reports
    - log every stage report to Comet with metadata-only numeric metrics
  first_missing_green_field: phase34b_gradient_source_surface_absent
  provider_capability_capsule: "use Section 20.6"
  nonclaims:
    - Gate E is currently falsified.
    - Initial Phase34 candidate set is exhausted.
    - Initial H1 ASVD was blocked, not disproven.
    - Initial H2 Gradient-SVD was not available, not tested.
    - Historical H3 was finite-difference approximation, not true P-GAP.
    - No H5, D2A, Gate E full27, or promotion is authorized until a new candidate passes predecessor gates.
```
