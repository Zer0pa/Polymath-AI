# Apex Gate E Task-Aligned Projection Candidate Exhaustion Engineering and Science Report

Date: 2026-07-09

Repository: `/Users/Zer0pa/Polymat AI/Polymath-AI`

Sequence role: follow-on to `05_APEX-GATE-E-PHONE-NATIVE-JL-C2-FULL27-FALSIFICATION-ENGINEERING-SCIENCE-REPORT-2026-07-08.md`.

This is report `06` in the Gate E science-report sequence. Existing report
`05` remains the July 8 phone-native JL C2 full27 falsification report. This
report records what happened after that falsification: the attempt to execute
the task-aligned projection repair program derived from the external design
brief, the staged candidate outcomes, and the final stop state under the
current PRD.

This report is written for engineering and scientific custody. It does not
claim Gate E pass, language-model improvement, D2A authorization, C3/C4/D3
promotion, H5-control authorization, or permission to continue unpredeclared
experiments. The governing acceptance gate remains phone-native decoder-token
NLL per token on the fixed Gate E authority surface. Negative
`after_minus_before` is required for pass. The current value remains positive:

```text
Gate E authority NLL delta per token: +0.01624497490593768
```

## 1. Current Verdict

```yaml
authority_gate:
  status: falsified
  metric: phone-native decoder-token NLL per token
  sign_convention: after_minus_before
  before_nll_per_token: 14.538868526231177
  after_nll_per_token: 14.555113501137114
  nll_delta_per_token: +0.01624497490593768
  record_count: 27
  token_count: 27
  authority_report: runtime/reports/apex_heterogeneous_cell/gate_e_phone_native_jl_c2_full27_20260708_timeout12h/gate_e_token_nll_perplexity_report.json
  authority_report_sha256: 70739a1c78b5d1cea5a98d1826f8a1b4c658929c7b534612e346ee0309e432f0

phase34_task_aligned_projection_run:
  run_id: 20260708T115449Z
  status: current_prd_candidate_set_exhausted
  report_root: runtime/reports/apex_heterogeneous_cell/phase34_task_aligned_projection_20260708T115449Z/
  phone_run_root: /data/data/com.termux/files/home/polymath_phase34_task_projection/20260708T115449Z
  host_scratch_root: /Users/Zer0pa/Polymat AI/runtime/tmp/phase34_task_aligned_projection_20260708T115449Z/

candidate_disposition:
  h0_rademacher: negative_control_only
  h1_asvd_activation_svd: blocked_fail_closed_activation_capture_rank_below_projection_dim
  h2_gradient_svd_galore: blocked_fail_closed_dL_NLL_dh_layer24_gradient_surface_absent
  h3_pgap: d3_falsified_p_value_above_stage_threshold
  h4_rmt: d3_falsified_fraction_aligned_below_stage_threshold
  h5_sign_scale_layer_controls: unauthorized_no_projection_candidate_passed_d3

decision:
  gate_e_pass: false
  promotion_allowed: false
  d2a_authorized: false
  gate_e_full27_authorized_for_phase34_candidate: false
  c3_c4_d3_promotion_path_authorized: false
  unpredeclared_candidate_experiments_authorized: false
  next_allowed_action: explicit_user_authorization_for_prd_or_research_revision_only
```

The short scientific verdict is:

```text
The task-aligned projection repair effort did not produce a promotable
projection candidate under the current PRD. The design document's diagnosis
remains highly consistent with the observed failures, but the full constructive
prescription was not completed because the necessary activation-rank and
gradient-source surfaces were not available in usable form.
```

## 2. Design Brief Referenced

The external design brief evaluated here is:

```text
/Users/Zer0pa/Polymat AI/Task-Aligned Projection Design for Phone-Native Gemma-4-E4B Polar Training.md
sha256: 35cbdf7444268a2132c10dbee889cb9970e83f4fa726153d06572eec0bc9cc5c
```

Its central thesis was that the Gate D/Gate E divergence is structurally
consistent with Goodhart's Law applied to a random Rademacher JL projection.
The JL matrix preserves Euclidean geometry, not the task-specific inner
products that determine next-token NLL movement at layer 24:

```text
< dL_NLL / dh_layer24, delta_h_layer24 >
```

The brief recommended replacing task-agnostic random projection with a
data-driven or gradient-calibrated projection. Its ranked repair ideas were:

1. Activation-covariance SVD / ASVD-style calibration from layer-24 post-PLE-gate activations.
2. Gradient-calibrated SVD / GaLore-style basis from `dL_NLL/dh_layer24`.
3. P-GAP-style gradient-aligned perturbations.
4. RMT spectral fallback only when stronger activation/gradient routes are unavailable.
5. A cheap polar/NLL correlation screen before any full Gate D/Gate E run.

The brief's final recommended path was:

```text
1. Run the cheap n=20 perturbation correlation test with the current Rademacher matrix.
2. Build the ASVD-style calibrated projection using representative calibration forward passes.
3. Rerun the correlation test with the new matrix.
4. Proceed to full Gate D/Gate E only if the correlation test passes.
```

This report's key question is whether that prescription was executed.

## 3. Was The Design Prescription Executed?

The honest answer is: partially, not completely.

The work executed the design's governing scientific discipline: Gate E remained
sovereign, surrogate wins were not promoted, projection candidates were screened
through staged polar/NLL correlation gates, and no full Gate E run was launched
for a Phase34 task-aligned projection candidate after D3 failed.

The work did not fully execute the design's strongest constructive path,
because no candidate reached the state where it could instantiate and pass the
design's intended ASVD or gradient-SVD projection test.

| Design prescription | Execution result | Verdict |
| --- | --- | --- |
| Treat random JL as suspect after surrogate/authority divergence | H0 Rademacher retained as a negative control only; Gate E falsification preserved | Executed |
| Capture layer-24 post-PLE-gate activations for ASVD | Phone-native capture succeeded at `post_ple_gate_hidden_pre_native_polar`; 34 records / 261 rows aggregated | Partially executed |
| Build a full ASVD-style `[256,2560]` projection | Blocked because centered rank was 93, below the 256D projection requirement | Not completed |
| Build a GaLore-style gradient-SVD projection from `dL_NLL/dh_layer24` | Blocked because the required gradient surface was absent | Not completed |
| Build true P-GAP perturbations aligned to a gradient subspace | A bounded finite-difference approximation was built from existing H4 observations, but no true gradient-subspace P-GAP was possible | Partially executed, not the design's true P-GAP |
| Use RMT fallback when stronger routes fail | H4 RMT static matrix was built and screened | Executed and falsified |
| Run staged polar/NLL correlation before any full Gate E candidate run | D1/D2/D3 gates were enforced; no D2A or Gate E full27 after D3 falsification | Executed |

Therefore, the correct classification is:

```text
The current PRD executed a staged, fail-closed approximation of the design
program. It did not fully execute the design brief's primary or strongest
constructive methods because their required data surfaces were blocked.
```

This distinction matters. The result does not prove that ASVD, GaLore, or true
P-GAP cannot work for Apex. It proves that the current Phase34 implementation
and available artifacts did not produce a promotable candidate from those
routes.

## 4. What This Adds To Report 05

Report `05` established that the JL C2 candidate could improve the polar
surrogate while regressing phone-native decoder-token NLL:

```yaml
jl_c2_gate_d2a_polar_metric:
  loss_delta: -46.518436381324136
  verdict: polar_surrogate_improved

jl_c2_gate_e_phone_native_decoder_metric:
  nll_delta_per_token: +0.01624497490593768
  verdict: falsified
```

This report adds the follow-on repair evidence:

| Addition | Result | Meaning |
| --- | --- | --- |
| Task-aligned projection PRD executed under staged gates | Static/preflight and candidate scaffolds were run; raw-boundary discipline preserved | The repair attempt was real engineering work, not just narrative |
| H1 ASVD rank diagnostic | Centered rank estimate `93 < 256` after 34 records / 261 rows | The available activation capture did not support the intended 256D ASVD projection |
| H2 gradient-SVD feasibility | Blocked on absent `dL_NLL_dh_layer24_gradient_surface` | The design's strongest GaLore-style route needs a new gradient-source program |
| H3 finite-difference P-GAP approximation | D1 and D2 passed, D3 failed with `p=0.052507586484463346` | The near-looking correlation did not clear the predeclared statistical gate |
| H4 RMT fallback | D3 falsified on `fraction_aligned=0.5555555555555556` | The fallback did not establish reliable surrogate/NLL direction agreement |
| H5 controls | Not authorized | No projection candidate passed D3, so controls could not be used as promotion scaffolding |

The scientific movement from report `05` to report `06` is:

```text
JL C2 authority falsification
  -> task-aligned projection repair attempt
  -> primary activation-SVD blocked by rank
  -> gradient-SVD blocked by missing gradient surface
  -> finite-difference P-GAP approximation D3-falsified
  -> RMT fallback D3-falsified
  -> current PRD candidate set exhausted
```

## 5. Artifact Index

All listed artifacts are reports, metadata, code-state references, hashes, or
outside-git scratch references. Raw prediction JSONLs, raw token rows, raw
activation rows, raw theta binaries, QNN tensors, model weights, payload dumps,
stdout/stderr dumps, and secrets are not embedded in this report.

| Artifact | Path | sha256 | Role |
| --- | --- | --- | --- |
| Phase34 task-aligned projection PRD | `docs/PRD-PHASE34-TASK-ALIGNED-PROJECTION-PHONE-NATIVE-GEMMA4-E4B-POLAR-TRAINING-2026-07-08.md` | `b2bffc2b5c819749c42e0d05774f6b8f8f5a9e93f73e18b2b37c3b4e2ae5159b` | Current PRD executed under staged falsification gates |
| External task-aligned projection design brief | `/Users/Zer0pa/Polymat AI/Task-Aligned Projection Design for Phone-Native Gemma-4-E4B Polar Training.md` | `35cbdf7444268a2132c10dbee889cb9970e83f4fa726153d06572eec0bc9cc5c` | Scientific repair design evaluated by this report |
| Final JL C2 Gate E authority report | `runtime/reports/apex_heterogeneous_cell/gate_e_phone_native_jl_c2_full27_20260708_timeout12h/gate_e_token_nll_perplexity_report.json` | `70739a1c78b5d1cea5a98d1826f8a1b4c658929c7b534612e346ee0309e432f0` | Sovereign Gate E falsification retained from report `05` |
| Phase34 drift/preflight report | `runtime/reports/apex_heterogeneous_cell/phase34_task_aligned_projection_20260708T115449Z/DRIFT_AND_PREFLIGHT_REPORT.md` | `f0f2b6b1aa874cc4b86bacdd9dfbe1d2faf10e5293c3b21f178d88c72c8ea126` | Repo, phone, env, provider, and authority custody capsule |
| Static harness gate | `runtime/reports/apex_heterogeneous_cell/phase34_task_aligned_projection_20260708T115449Z/stage_a_static_harness_gate_report.json` | `945974b284092a6379080999b04454dcc29381bfafec9d70324ef0400dd2105b` | Stage A static harness pass with nonclaims |
| Phone preflight | `runtime/reports/apex_heterogeneous_cell/phase34_task_aligned_projection_20260708T115449Z/stage_b_phone_preflight_report.json` | `973261b985c988e3e12c781e41987a57438b0c1d3b3c0e407aa233dae1dabb59` | Phone/SSH execution readiness report |
| ASVD activation concat | `runtime/reports/apex_heterogeneous_cell/phase34_task_aligned_projection_20260708T115449Z/stage_c6_asvd_activation_concat_report.json` | `4b0155aa8ccc6de4efd1a7ec73bf172e9a07e1f6b343e0a15984139aeb395f8a` | Captured layer-24 post-PLE-gate activation matrix metadata |
| H1 ASVD rank diagnostic | `runtime/reports/apex_heterogeneous_cell/phase34_task_aligned_projection_20260708T115449Z/h1_asvd_rank_diagnostic_261rows_report.json` | `2dc1d637293bdb64e4b5bfbf32b0594fb8878609d6c1007f38fdb99a82b993da` | H1 fail-closed rank blocker |
| H2 gradient-SVD blocker | `runtime/reports/apex_heterogeneous_cell/phase34_task_aligned_projection_20260708T115449Z/h2_gradient_svd_feasibility_blocker_report.json` | `e66af04623942fb020c2058870f902eba8767536273b8bd20062d13fd61497b0` | H2 fail-closed absent-gradient blocker |
| H3 finite-difference policy | `runtime/reports/apex_heterogeneous_cell/phase34_task_aligned_projection_20260708T115449Z/h3_pgap_finite_difference_policy_report.json` | `f797ad221688d0bf3b758580be660a7157cb0710250afb12a29de697a8de5133` | H3 approximation policy construction |
| H3 D1 micro correlation | `runtime/reports/apex_heterogeneous_cell/phase34_task_aligned_projection_20260708T115449Z/d1_h3_micro_correlation_report.json` | `ff5e3148e24d448a15781738f1f6f9ccb2071a63f17893364430a4fa39da19b9` | H3 D1 pass |
| H3 D2 small correlation | `runtime/reports/apex_heterogeneous_cell/phase34_task_aligned_projection_20260708T115449Z/d2_h3_small_correlation_report.json` | `ef4295536e73d16236590e221474b90df296e15d36236481409f2969c82a8793` | H3 D2 pass |
| H3 D3 full correlation | `runtime/reports/apex_heterogeneous_cell/phase34_task_aligned_projection_20260708T115449Z/d3_h3_full_correlation_report.json` | `bebadcb4c3045879f7c869ef2a817c66640a0b7cc82bf1de15edc7668bdac4e7` | H3 D3 falsification |
| H4 RMT matrix report | `runtime/reports/apex_heterogeneous_cell/phase34_task_aligned_projection_20260708T115449Z/h4_rmt_matrix_report.json` | `f67f05dc8abdc4c4c0bd8d012364eae05f0670bf4e5dfeef951b423d62a1b2de` | RMT fallback static matrix |
| H4 D3 full correlation | `runtime/reports/apex_heterogeneous_cell/phase34_task_aligned_projection_20260708T115449Z/d3_h4_full_correlation_report.json` | `5c3df67a8890be56bd11b09652affbd2f534b4070a8f3e34facc38bd7d9b946a` | H4 D3 falsification |
| Design diff analysis | `runtime/reports/apex_heterogeneous_cell/phase34_task_aligned_projection_20260708T115449Z/DESIGN_DIFF_ANALYSIS_20260709.md` | `9d42d9b606225529678e6d99ed3d630977273042d4392ce2a0742b496c17073a` | Detailed local diff between executed work and external design brief |
| H3 policy builder script | `scripts/host/build_phase34_h3_pgap_policy.py` | `b173cccfdf2e97d70f8914d28f0bdd87517da68df64117a76de9dfa794385644` | New finite-difference H3 policy builder; untracked at report time |

Metadata-only Comet logging was completed to:

```yaml
workspace: zer0pa-imc
project_name: mobile-polymath-ai-training
final_jl_c2_gate_e_url: https://www.comet.com/zer0pa-imc/mobile-polymath-ai-training/0266804deeee44c098b32c9c5031cbd3
h1_rank_diagnostic_url: https://www.comet.com/zer0pa-imc/mobile-polymath-ai-training/a9a92707353f4cd59b0c5228d3f0e12b
h2_blocker_url: https://www.comet.com/zer0pa-imc/mobile-polymath-ai-training/811e9a2243f640e695cfb2613ca9276b
h3_d1_url: https://www.comet.com/zer0pa-imc/mobile-polymath-ai-training/ca0de543883049cda341d20bc1cfbae6
h3_d2_url: https://www.comet.com/zer0pa-imc/mobile-polymath-ai-training/73ad2007fc67495791e1f40325a7da1b
h3_d3_url: https://www.comet.com/zer0pa-imc/mobile-polymath-ai-training/93e3a5889f964d78b16dfc1d8e62c299
h4_matrix_url: https://www.comet.com/zer0pa-imc/mobile-polymath-ai-training/ae3347dd6483413ebc196f300464a87d
h4_d3_url: https://www.comet.com/zer0pa-imc/mobile-polymath-ai-training/8748a6c1d4fe4edb9504abc90a838e69
```

## 6. Chronology Since Report 05

### 6.1 Context Ingestion And Authority Freeze

Execution began from a custody state where Gate E was already falsified by the
phone-native JL C2 full27 run. The inherited authority result was not reopened
or softened:

```yaml
latest_authority_status: falsified
before_nll_per_token: 14.538868526231177
after_nll_per_token: 14.555113501137114
nll_delta_per_token: +0.01624497490593768
promotion_allowed: false
```

The Phase34 PRD and the task-aligned projection design brief were read as
repair instructions, not as permission to lower the Gate E acceptance metric.

### 6.2 Drift, Phone, Env, And Provider Preflight

The run preserved the RedMagic phone as the authority execution target:

```yaml
device: RedMagic 10 Pro / NX789J
adb_serial: FY25013101C8
android_release: 15
soc_model: SM8750
ssh_route: adb forward tcp:18022 tcp:8022
ssh_user: u0_a536
phone_env_file: /data/data/com.termux/files/home/.termux_agent_env
phone_env_sha256: 9874fec9b9998e9e210d32fc71b40c48cf42586cd44c48f9c529c9f9c2118c7f
comet_workspace_forced: zer0pa-imc
comet_project_forced: mobile-polymath-ai-training
```

The worktree was inherited dirty and remained dirty. No unrelated changes were
reverted. No raw artifacts or secret files were committed or embedded.

### 6.3 H0 Rademacher Baseline

H0 was retained as the incumbent random baseline and negative control. The
matrix static contract passed, but H0 was explicitly non-promotable:

```yaml
candidate_id: h0_rademacher
status: phase34_projection_matrix_static_contract_pass
first_missing_green_field: none
promotion_allowed: false
nonclaims:
  - H0 is an incumbent random baseline and cannot promote.
  - No Gate E pass is implied by matrix construction.
```

This aligned with the design brief's diagnosis but did not by itself satisfy
the brief's ideal first step of a fresh n=20 Rademacher correlation screen
inside the final repaired protocol. H0 supplied baseline custody, not a new
promotable candidate.

### 6.4 H1 ASVD / Activation-SVD

H1 implemented the design brief's most hardware-friendly route as far as the
available activation surface allowed.

Activation capture succeeded at the correct conceptual location:

```yaml
candidate_id: h1_asvd
layer_idx: 24
activation_capture_site: post_ple_gate_hidden_pre_native_polar
calibration_record_count: 34
calibration_row_count: 261
shape_width: 2560
raw_rows_embedded: false
raw_rows_in_repo: false
```

The rank diagnostic then blocked H1:

```yaml
status: blocked_fail_closed
first_missing_green_field: activation_capture_rank_below_projection_dim
projection_dim: 256
centered_rank_estimate: 93
singular_value_count: 261
singular_values_at_or_below_tolerance: 168
top256_energy_ratio: 1.0
```

Scientific interpretation:

```text
The ASVD route was not falsified as a research idea. The available capture set
was insufficient or insufficiently diverse to construct a 256D centered
activation-SVD basis under the current PRD.
```

This blocker is directly linked to the design brief. The brief's ASVD path
requires a representative calibration set, with the opportunity claim that
32-128 representative samples should be enough for stable basis construction.
The run collected 34 records and 261 rows, but the centered rank was only 93.
That result points to a calibration-surface problem, not to a Gate E pass.

### 6.5 H4 RMT Spectral Fallback

Because H1's full ASVD matrix was blocked, the fallback RMT route was exercised.
It produced a valid static matrix:

```yaml
candidate_id: h4_rmt
status: phase34_projection_matrix_static_contract_pass
matrix_shape: [256, 2560]
matrix_dtype: float32
matrix_sha256: c2d0e182be0cb2e2a2bdccca16be6e39bb0e25e9f24ed89abd997653a2f8e134
activation_rows: 261
rank_estimate: 93
signal_rank: 5
complement_rank: 251
signal_energy_ratio: 0.6460293696897574
```

H4 then failed D3:

```yaml
status: falsified
first_missing_green_field: fraction_aligned_below_stage_threshold
observation_count: 27
perturbation_seed_count: 23
pearson_r: 0.46722679559187247
p_value: 0.008235128183794014
fraction_aligned: 0.5555555555555556
stage_threshold_fraction_aligned: 0.65
```

Scientific interpretation:

```text
The RMT fallback contained some measurable correlation, but direction agreement
was too weak for promotion. The tiny signal rank and large deterministic
complement are consistent with the design brief's ranking of RMT as fallback,
not as the primary repair.
```

H4 cannot advance to D2A or Gate E under the current PRD.

### 6.6 H2 Gradient-SVD / GaLore

H2 attempted the design brief's strongest analogue: a GaLore-style projection
basis from the NLL gradient at layer 24. It blocked fail-closed:

```yaml
status: blocked_fail_closed
candidate_id: h2_gradient_svd_galore
first_missing_green_field: dL_NLL_dh_layer24_gradient_surface_absent
required_artifact:
  semantic: representative dL_NLL/dh_layer24 gradient row matrix
  expected_surface: current phone-native decoder-token NLL / layer24 post-PLE hidden state
  expected_shape: "[N,2560] before SVD then [256,2560] Phi_GRAD"
blockers:
  - dL_NLL_dh_layer24_gradient_surface_absent
  - phone_native_backward_to_layer24_gradient_absent
  - offline_gradient_asset_not_declared_or_imported
  - historical_gradient_artifacts_scope_mismatch_rank4_adapter_not_layer24_hidden
```

The search did not merely miss a file. It inspected host reports, phone private
storage, historical gradient artifacts, and runtime surfaces. The historical
gradient artifacts were rejected because they described rank4 adapter gradients
or parity probes, not the current layer-24 hidden-state NLL-gradient matrix.

Scientific interpretation:

```text
H2 is blocked exactly at the document's known hard requirement. GaLore-style
projection is not executable without a valid dL_NLL/dh_layer24 source.
```

The document-linked solution is explicit: produce a one-time offline gradient
calibration artifact or implement a limited backward-to-layer24 surface. That
is a new gradient-source program and requires explicit PRD/research revision.

### 6.7 H3 P-GAP Approximation

After H2 blocked, H3 entered as a micro-budget P-GAP lane. Because no true
gradient surface existed, the implemented H3 policy was a finite-difference
ridge estimate built from existing H4 phone-native observations:

```yaml
candidate_id: h3_pgap
policy_status: pass
algorithm: ridge_low_dimensional_finite_difference_gradient_descent
source_projection_candidate_id: h4_rmt
source_projection_status: d3_falsified_not_promoted
new_phone_finite_difference_runs: 0
measured_seed_count: 23
observation_count: 23
observation_record_count: 27
fit_sign_agreement_fraction: 1.0
leave_one_out_pearson_r: 0.10165295353112776
leave_one_out_sign_agreement_fraction: 0.5652173913043478
```

H3 D1 and D2 passed the staged screen:

```yaml
d1:
  status: phase34_projection_correlation_pass
  observation_count: 6
  perturbation_seed_count: 2
  pearson_r: 0.4600201884167021
  p_value: 0.30011429183585897
  fraction_aligned: 1.0

d2:
  status: phase34_projection_correlation_pass
  observation_count: 10
  perturbation_seed_count: 6
  pearson_r: 0.3748684443022382
  p_value: 0.2527530190479616
  fraction_aligned: 1.0
```

H3 D3 then falsified:

```yaml
d3:
  status: falsified
  first_missing_green_field: no_promotable_candidate_passed_correlation
  candidate_first_missing_green_field: p_value_above_stage_threshold
  observation_count: 27
  perturbation_seed_count: 23
  pearson_r: 0.36155592617665516
  p_value: 0.052507586484463346
  fraction_aligned: 0.9259259259259259
  nll_improvement_mean: 0.004382125847226427
  polar_improvement_mean: 10.481646978787207
```

Scientific interpretation:

```text
H3 produced a positive-looking signal but did not meet the predeclared D3
statistical threshold. The p-value miss cannot be converted into a pass without
rewarding threshold drift.
```

It is also important that this was not true P-GAP as described in the design
brief. The design's P-GAP requires a gradient subspace and perturbations whose
inner product with the NLL gradient is controlled. The implemented H3 was a
bounded finite-difference approximation because the gradient source was absent.

### 6.8 Stop State

After H3 D3 falsification, all authorized projection candidates under the
current PRD were either blocked or falsified:

```yaml
h1: blocked
h2: blocked
h3: d3_falsified
h4: d3_falsified
h0: negative_control_only
h5: unauthorized
```

Oversight accepted the stop state. Further Phase34 task-aligned projection
execution under the current PRD is not authorized.

## 7. Final Science Result

The final scientific result is not an authority improvement. It is a negative
repair result under staged falsification:

| Surface | Result | Scientific meaning |
| --- | --- | --- |
| Gate E authority | `+0.01624497490593768` NLL/token regression | Promotion remains falsified |
| H1 ASVD | rank blocker, centered rank `93 < 256` | Available activation capture did not support full 256D ASVD |
| H2 GaLore | missing `dL_NLL/dh_layer24` | Strongest gradient-SVD route lacks required gradient source |
| H3 P-GAP approximation | D3 p-value `0.052507586484463346` | Positive-looking signal did not meet threshold |
| H4 RMT fallback | fraction aligned `0.5555555555555556` | Direction agreement too weak |
| H5 controls | unauthorized | No candidate passed D3 |

The design brief's diagnosis is reinforced:

```text
Random/proxy projection-space success is not enough. The system needs an
activation or gradient basis that demonstrably correlates polar movement with
decoder-token NLL improvement before any authority run can be trusted.
```

The design brief's constructive prescription remains unresolved:

```text
The current execution did not deliver a valid ASVD or gradient-SVD basis.
Therefore the design's best proposed repair has not yet been fully tested.
```

## 8. Interpretation

### 8.1 Scientific Interpretation

The sequence now has a sharper picture:

```text
Gate D polar heldout loss can be improved.
Phone-native Gate E decoder-token NLL can be measured.
The incumbent random JL polar update worsens Gate E.
Baseline controls reject scorer noise as the explanation.
Task-aligned projection candidates did not yet produce a promotable replacement.
```

This is a useful negative result. It prevents the project from converting
surrogate gains or near-threshold correlation into language-model progress.

The most important scientific distinction is between two claims:

```yaml
claim_rejected:
  text: The current Phase34 task-aligned projection PRD produced a candidate that can advance.
  status: rejected

claim_not_yet_tested:
  text: A properly sourced ASVD, GaLore, or true P-GAP projection cannot solve the alignment problem.
  status: not established
```

H1, H2, and H3 were limited by the available data surfaces. They do not close
the broader research direction. They close the current PRD's candidate set.

### 8.2 Engineering Interpretation

The engineering stack improved in several ways:

```yaml
phone_authority_surface_available: true
static_projection_contract_available: true
post_ple_gate_activation_capture_available: true
metadata_only_comet_logging_available: true
staged_correlation_report_builder_available: true
h3_finite_difference_policy_builder_available: true
raw_boundary_discipline_preserved: true
```

But the engineering blockers are now more fundamental:

```yaml
missing_or_insufficient_surfaces:
  - representative full-rank activation calibration for 256D ASVD
  - current layer24 dL_NLL/dh gradient matrix
  - true gradient-aligned P-GAP perturbation constructor
  - matched controls for a candidate that actually passes D3
```

The next repair must address those source surfaces. More phone runs with the
same blocked or falsified candidates would be process drift.

### 8.3 Relationship To Goodhart's Law

The original JL C2 failure showed a strong Goodhart pattern: a larger polar
surrogate improvement produced a larger NLL regression. The task-aligned
projection work did not disprove that diagnosis. It strengthened it by showing
that weak substitute alignments are not enough:

- RMT had statistically significant correlation but failed direction agreement.
- H3 had high direction agreement but missed significance at D3.
- H1 could not produce the intended 256D basis from the available capture.
- H2 could not access the actual gradient surface.

The common theme is that partial proxies remain partial proxies. The authority
metric still demands direct NLL improvement.

## 9. Anomalies And Unexpected Findings

### 9.1 H1 Captured Enough Rows Numerically But Not Enough Rank

The H1 activation aggregate reached 261 rows, just above the 256D projection
minimum. However, centered rank was only 93. This indicates the limiting factor
was not just row count. It was likely calibration diversity, surface semantics,
or both.

This links directly to the design brief's calibration recommendation. A future
ASVD revision should measure rank trend and context diversity before treating
row count as sufficient.

### 9.2 H4 Had Pearson Signal But Failed Direction Agreement

H4 produced `pearson_r=0.46722679559187247` and `p=0.008235128183794014`, but
only `fraction_aligned=0.5555555555555556`. This is not contradictory. It means
the linear correlation statistic alone did not guarantee enough per-observation
directional reliability for staged promotion.

The stage threshold correctly blocked advancement.

### 9.3 H3 Looked Better Than H4 On Direction But Still Failed D3

H3 produced `fraction_aligned=0.9259259259259259`, but `p=0.052507586484463346`.
Under the PRD, that is a falsifier. The result is close enough to motivate a
future research revision, but not close enough to advance.

### 9.4 H3 Was Called P-GAP But Was Not Full P-GAP

This is a naming risk. The implemented H3 was a micro-budget finite-difference
policy because the gradient source was absent. It should not be treated as a
complete execution of the design brief's P-GAP method.

Future PRD text should distinguish:

```yaml
finite_difference_pgap_approximation: current_h3
true_gradient_aligned_pgap: requires_dL_NLL_dh_layer24
```

### 9.5 Provider And Phone Issues Were Secondary

Phone SSH and runner stalls required recovery discipline, and the phone
Hugging Face CLI wrapper pointed at a missing Python 3.12. These issues were
managed or bypassed without changing the science result. The final blockers
were not provider custody or phone access. They were projection-source
blockers.

## 10. Acceptance Ledger

Accepted:

```yaml
accepted:
  authority_gate_e_falsification_preserved: true
  report_05_final_jl_c2_state_preserved: true
  phase34_static_harness_run: true
  phone_preflight_run: true
  post_ple_gate_activation_capture_produced_metadata: true
  h1_rank_blocker_recorded: true
  h2_gradient_surface_blocker_recorded: true
  h3_d1_d2_d3_staged_screen_completed: true
  h4_d3_falsification_preserved: true
  metadata_only_comet_logging_completed_for_major_gates: true
  raw_boundary_preserved: true
```

Rejected claims:

```yaml
rejected_claims:
  gate_e_pass: rejected
  language_model_perplexity_improvement: rejected
  surrogate_win_as_authority_win: rejected
  h1_asvd_projection_promotable: rejected
  h2_gradient_svd_projection_available: rejected
  h3_pgap_promotable_after_d3: rejected
  h4_rmt_promotable_after_d3: rejected
  h5_controls_authorized: rejected
  c3_c4_d3_promotion_path_authorized: rejected
```

Open:

```yaml
open_questions:
  richer_asvd_calibration_can_reach_rank_256: unresolved
  exact_post_gelu_ple_gate_capture_semantics: needs_reverification_before_revised_asvd
  offline_or_limited_backward_gradient_source_feasible: unresolved
  true_gradient_aligned_pgap_can_pass_d3: untested
  matched_controls_for_future_d3_pass_candidate: pending_future_candidate
```

## 11. Required Next Repair

No further Phase34 task-aligned projection execution is authorized under the
current PRD. The next work must be a PRD or research revision explicitly
authorized by the user.

The document-linked repair routes are:

1. Gradient-source program:
   - Produce a valid `dL_NLL/dh_layer24` matrix with shape `[N,2560]`.
   - Prefer one-time offline calibration if phone-native backward is not feasible.
   - Bind the artifact to model identity, tokenizer identity, calibration corpus, layer index, capture site, dtype, shape, and SHA-256.

2. Richer ASVD calibration program:
   - Expand and stratify calibration beyond the 34-record / 261-row capture.
   - Verify exact post-GELU PLE gate semantics.
   - Track centered rank, effective rank, unique token/context distribution, and sensitivity to ASVD alpha before matrix construction.

3. True P-GAP program:
   - Build perturbations from a validated gradient subspace.
   - Prove the alignment condition and perturbation magnitude before D1.
   - Do not reuse an H4-falsified projection as if it were a promoted basis.

4. Gate discipline:
   - Keep D1/D2/D3 correlation screens as necessary predecessors.
   - Do not relax `p < 0.05`, `fraction_aligned >= 0.65`, or authority NLL thresholds after observing results.
   - Launch Gate E full27 only after a projection candidate passes D3 and predecessor controls.

## 12. Final Statement

The Phase34 task-aligned projection work did not rescue Gate E. It correctly
kept the authority metric sovereign and stopped after all authorized projection
candidates were blocked or falsified.

The external task-aligned projection design brief remains scientifically useful.
Its central diagnosis matches the observed failure mode: task-agnostic polar
surrogate improvement is not enough for decoder-token NLL improvement. Its
proposed repairs were not fully executed to completion because the current
system lacked either a full-rank activation basis for H1 or a valid
`dL_NLL/dh_layer24` gradient surface for H2 and true H3.

The current state is:

```text
Gate E falsified.
Current PRD candidate set exhausted.
No promotion authorized.
Further execution requires explicit PRD or research revision.
```

## 13. NEXT_HANDOFF

```yaml
NEXT_HANDOFF:
  to: oversight_or_next_research_prd_author
  status: phase34_task_aligned_projection_current_prd_candidate_set_exhausted
  artifacts:
    - path: docs/APEX-GATE-E-SCIENCE-REPORT-SEQUENCE-2026-07-06/06_APEX-GATE-E-TASK-ALIGNED-PROJECTION-CANDIDATE-EXHAUSTION-ENGINEERING-SCIENCE-REPORT-2026-07-09.md
      sha256: see_external_checksum_after_finalization
    - path: runtime/reports/apex_heterogeneous_cell/phase34_task_aligned_projection_20260708T115449Z/DESIGN_DIFF_ANALYSIS_20260709.md
      sha256: 9d42d9b606225529678e6d99ed3d630977273042d4392ce2a0742b496c17073a
  first_missing_green_field: no_promotable_projection_candidate_under_current_prd
  next_action: await_explicit_user_authorization_for_prd_or_research_revision
  prompt_to_send: |
    Gate E remains falsified at after_minus_before +0.01624497490593768.
    H1 ASVD is blocked on activation_capture_rank_below_projection_dim.
    H2 Gradient-SVD/GaLore is blocked on absent dL_NLL_dh_layer24_gradient_surface.
    H3 finite-difference P-GAP approximation is D3-falsified on p_value_above_stage_threshold.
    H4 RMT is D3-falsified on fraction_aligned_below_stage_threshold.
    H5 remains unauthorized because no projection candidate passed D3.
    Do not launch further Phase34 execution under the current PRD. Continue only with explicit PRD/research revision or a new predeclared gradient-source/candidate program.
  handoff_dispatch_status: TOOL_UNAVAILABLE
  context_load:
    tier: targeted_reference
    files_loaded:
      - /Users/prinivenpillay/.codex/skills/zpp-orchestrate/SKILL.md
      - /Users/prinivenpillay/.codex/skills/zpp-orchestrate/references/context-load.md
      - /Users/prinivenpillay/.codex/skills/zpp-orchestrate/references/next-handoff.md
      - /Users/Zer0pa/Polymat AI/Task-Aligned Projection Design for Phone-Native Gemma-4-E4B Polar Training.md
      - docs/APEX-GATE-E-SCIENCE-REPORT-SEQUENCE-2026-07-06/05_APEX-GATE-E-PHONE-NATIVE-JL-C2-FULL27-FALSIFICATION-ENGINEERING-SCIENCE-REPORT-2026-07-08.md
      - runtime/reports/apex_heterogeneous_cell/phase34_task_aligned_projection_20260708T115449Z/DESIGN_DIFF_ANALYSIS_20260709.md
      - selected metadata-only Phase34 reports listed in this artifact index
    extraction_mode: targeted_plus_full_design_diff
    rationale: create report 06 as a follow-on science/engineering report in the existing sequence
    omitted_heavy_sources:
      - raw activation rows
      - raw prediction JSONL files
      - raw token rows
      - theta binaries
      - model weights
      - env files
      - token or secret files
  provider_capability_capsule:
    matrix_artifact: runtime/reports/apex_heterogeneous_cell/phase34_task_aligned_projection_20260708T115449Z/DRIFT_AND_PREFLIGHT_REPORT.md sha256:f0f2b6b1aa874cc4b86bacdd9dfbe1d2faf10e5293c3b21f178d88c72c8ea126
    providers:
      phone_adb_termux:
        role: RedMagic 10 Pro authority execution target for model/training gates
        current_classification: PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES
      comet:
        role: authority-linked numeric metrics and metadata-only logging
        current_classification: PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES
      github:
        role: custody commits and PR surface only when explicitly authorized
        current_classification: PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES
      hugging_face:
        role: corpus/model revision source and metadata-only provenance
        current_classification: PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES
    secret_policy: Never print, copy, summarize, commit, or include token/key values.
  research_escalation: required_for_any_continuation
  nonclaims:
    - no Gate E pass
    - no language-model improvement claim
    - no D2A authorization
    - no Gate E full27 authorization for Phase34 candidates
    - no C3/C4/D3 promotion path
    - no H5 controls
    - no unpredeclared candidate experiments
```
