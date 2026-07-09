# Apex Gate E Phone-Native JL C2 Full27 Falsification Engineering and Science Report

Date: 2026-07-08

Repository: `/Users/Zer0pa/Polymat AI/Polymath-AI`

Sequence role: follow-on to `04_APEX-GATE-E-C2-BASELINE-DIAGNOSTIC-ENGINEERING-SCIENCE-REPORT-2026-07-06.md`.

This report records the work performed after the July 6 Gate E baseline
diagnostic. It is written for external scientific and engineering analysis. It
does not claim Gate E pass, Gemma quality improvement, or authorization to
continue C3/C4/D3. The governing acceptance gate remains decoder-token
NLL/perplexity on the fixed Gate E heldout split.

The July 6 sequence ended with this state:

```text
Gate D polar surrogate evidence can improve.
Gate E decoder-token NLL is sovereign.
The prior C2 theta regressed Gate E by +0.0022157230634061165 NLL/token.
E1 no-update was exact zero.
E2 random theta contained the prior trained-theta delta.
```

The work since then tested a new JL C2 candidate, moved Gate E execution back
onto the RedMagic/Termux native surface, completed the full 27-record before
and after arms, and evaluated the fail-closed authority report. The final result
is a stronger falsification:

```text
JL C2 Gate D2A polar heldout metric improved by -46.518436381324136 loss.
The same candidate regressed Gate E phone-native decoder NLL by
+0.01624497490593768 per token.
```

## 1. Current Verdict

```yaml
jl_c2_gate_d2a_polar_metric:
  status: gate_d2_phone_local_heldout_learning_evidence_pass
  before_loss: 30906.645910614105
  after_loss: 30860.12747423278
  loss_delta: -46.518436381324136
  heldout_packet_count: 2500
  evaluated_answer_bearing_steps: 2344
  skipped_empty_answer_packets: 156
  theta_post_layer24_sha256: 118a96c02e04f8ae36156399bc696f29844c944335460272ea6b87f42a7daf66

jl_c2_gate_e_phone_native_decoder_metric:
  status: falsified
  first_missing_green_field: gate_e_nll_regression
  blockers:
    - gate_e_nll_regression
    - gate_e_surrogate_direction_diverged
  before_nll_per_token: 14.538868526231177
  after_nll_per_token: 14.555113501137114
  nll_delta_per_token: 0.01624497490593768
  sign_convention: after_minus_before
  before_perplexity: 2061343.5279915193
  after_perplexity: 2095103.4741836223
  perplexity_delta: 33759.94619210297
  record_count: 27
  token_count: 27

surrogate_validity:
  polar_loss_delta: -46.518436381324136
  nll_delta_per_token: 0.01624497490593768
  direction_agreement: false
  verdict: polar_nll_direction_diverge

comparison_to_report_04_random_theta_context:
  prior_random_theta_min_delta_per_token: -0.0022761499692689068
  prior_random_theta_max_delta_per_token: 0.00400865832950701
  current_delta_exceeds_prior_random_max: true
  current_minus_prior_random_max: 0.01223631657643067
  current_delta_over_prior_random_positive_max: about_4.05x
  note: prior_random_band_was_not_rerun_as_a_matched_phone_native_jl_c2_control

decision:
  gate_e_pass: false
  promotion_allowed: false
  d3_c3_c4_authorized: false
  language_model_improvement_claim: false
  next_allowed_action: repair_polar_update_sign_scale_injection_or_surrogate_alignment
```

The native scorer report has status `gate_e_token_nll_passed`. That status only
means the scorer produced the expected token-NLL evidence under the native
polar contract. It is not the science verdict. The final Gate E authority
report status is `falsified`.

## 2. What This Adds To Report 04

Report 04 classified the earlier C2 Gate E regression as random-theta-scale
motion. The work since then added five material facts.

| Addition | Result | Meaning |
| --- | --- | --- |
| Track A sign inversion attempt | `blocked_fail_closed` after phone-native scorer stall | The alpha `-1.0` sign-inversion hypothesis did not produce an authority metric result. It remains unproven and cannot be used as evidence. |
| Track B JL latency investigation | closed with no distinguishable JL latency advantage | JL input compression was not a useful latency lever for the immediate Gate E decision. |
| JL C2 Gate D2A full2500 run | passed the polar heldout metric with loss delta `-46.518436381324136` | A stronger polar-surrogate candidate was produced and bound to theta hash `118a96...`. |
| Host/reuse Gate E attempt | blocked fail-closed on missing source model safetensors path and absent token-NLL rows | The host/reuse path could not provide authority evidence and was not accepted. |
| RedMagic phone-native full27 Gate E | completed 27 before and 27 after records, then falsified | The final authority result is a phone-native decoder-token NLL regression, not a host-path artifact. |

The key scientific update is that the new JL C2 theta is not just
indistinguishable from the prior random-theta band. Its phone-native Gate E
regression is larger than the positive edge of that earlier band. Because the
random band was not rerun as a fully matched JL phone-native control, this
comparison should be treated as contextual rather than as a complete statistical
test. It is still sufficient for the gate: the sovereign metric regressed.

## 3. Artifact Index

All listed artifacts are reports, metadata, hashes, or outside-git scratch
references. Raw prediction rows, raw token rows, raw theta binaries, QNN
tensors, model weights, tokens, stdout, stderr, and secrets are not embedded in
this report.

| Artifact | Path | sha256 | Role |
| --- | --- | --- | --- |
| Track A sign alpha `-1` blocker | `runtime/reports/apex_heterogeneous_cell/track_a_sign_alpha_minus1_blocker_20260707/track_a_sign_alpha_minus1_blocker_report.json` | `3e58503ad7f128947fdc456063225e7e4937f97138642df6f08a520ca130a1de` | Records blocked sign inversion attempt and phone-native stall |
| Track B JL closing report | `runtime/reports/apex_heterogeneous_cell/track_b_jl_gemma_forward_20260707/track_b_closing_report.json` | `a12551b9bac40a4eff50ab01911faf333c1490dd1503f675488901fe4fe59612` | Closes JL latency investigation with no distinguishable advantage |
| JL C2 Gate D2A acceptance | `runtime/reports/apex_heterogeneous_cell/gate_d2a_jl_c2_full2500_20260707T_reuse_complete/gate_d_acceptance_report.json` | `09e297ffb10d55c928517003896d7568a15b13ff0f8d5b5bcccd6a57a73bac74` | Polar surrogate pass and theta binding for JL C2 |
| JL C2 policy builder | `runtime/reports/apex_heterogeneous_cell/gate_e_jl_c2_20260707T_reuse_complete/native_polar_policy_builder_report.json` | `ce100f48e69aea9aa884e03f4c0f027bc2babc2839649ab28de512846b5b134a` | Native-polar policy construction passed with metadata-only boundary |
| JL C2 host/reuse Gate E authority report | `runtime/reports/apex_heterogeneous_cell/gate_e_jl_c2_20260707T_reuse_complete/gate_e_token_nll_perplexity_report.json` | `978bdd87d50da983ff8dc1b2f263cd73e6a9f157dbfbb3e4fff1eb5093c6fe2d` | Fail-closed host/reuse attempt; no token-NLL authority rows |
| JL C2 host/reuse native scorer report | `runtime/reports/apex_heterogeneous_cell/gate_e_jl_c2_20260707T_reuse_complete/native_polar_scorer_report.json` | `29983dd65313ce97a40ada52dd8d95718e8b9254f1414daaadcb9df2a328da34` | Blocked on `source_model_safetensors_path_not_found` |
| Phone-native 60s timebox report | `runtime/reports/apex_heterogeneous_cell/gate_e_phone_native_jl_c2_20260708_timebox60/phone_native_scorer_report.json` | `24cd06e7cba08dbcda799c90e2c7250e30b1b9fec8c0b7a2bef332489ea20bc5` | Proved 60s was too short; before arm returncode `124` |
| Phone-native one-record instrumented probe | `runtime/reports/apex_heterogeneous_cell/gate_e_phone_native_jl_c2_20260708_instrumented_record1/phone_native_scorer_report.json` | `9d78dd6cb108447acdac9b8872a8a12005c73cf3c4ebb66a5587009d9c65df5e` | Proved phone-native before and after arms can emit one row each |
| Phone-native handover | `runtime/reports/apex_heterogeneous_cell/gate_e_phone_native_jl_c2_20260708_handover/HANDOVER_PHONE_NATIVE_GATE_E_20260708.md` | `ccc2216ce79c918292c7daea128ea7688a96779f02132a1d5b5c44b7612c66fc` | Captures detached run protocol, custody rules, and recovery policy |
| Final native scorer contract report | `runtime/reports/apex_heterogeneous_cell/gate_e_phone_native_jl_c2_full27_20260708_timeout12h/native_polar_scorer_report.json` | `528fa52e7f467ecb3ced33d1f23e29e5852a7c5c976f54b3fa20df117e9414cc` | Native scorer produced 27 token-NLL records under contract |
| Final Gate E authority report | `runtime/reports/apex_heterogeneous_cell/gate_e_phone_native_jl_c2_full27_20260708_timeout12h/gate_e_token_nll_perplexity_report.json` | `70739a1c78b5d1cea5a98d1826f8a1b4c658929c7b534612e346ee0309e432f0` | Sovereign science verdict: `falsified` |
| Final Gate E Comet logging result | `runtime/reports/apex_heterogeneous_cell/gate_e_phone_native_jl_c2_full27_20260708_timeout12h/gate_e_comet_logging_result.json` | `634674de214746bfb03a44875741965064c7565d19df15cb4fe4d04bad5a1b28` | Metadata-only Comet logging result |
| Token-NLL JSONL evidence | `/Users/Zer0pa/Polymat AI/runtime/tmp/gate_e_phone_native_full27_20260708_timeout12h/token_nll/token_nll_records.jsonl` | `77cf0abc4ecc6aaa457f1f5affef670b0585ad123add86206f55ac06375d9115` | Outside-git token-NLL records used by authority evaluator |

Phone-native raw prediction JSONL files were copied only to outside-git scratch
for scoring reuse:

```yaml
outside_git_scratch_root: /Users/Zer0pa/Polymat AI/runtime/tmp/gate_e_phone_native_full27_20260708_timeout12h/
before_predictions_jsonl_sha256: dc0454c05a3a70dbc7c4b01008b80272e93ef0158dcbcefce64161abc08d3d55
after_predictions_jsonl_sha256: 6c38ba5070b2f6dedaed190a063f6524336f11c946fa4950394444ee12dda481
before_native_report_sha256: 9228027ce761a5fe1c73c047a4cf0bac39555551933afa12ba3e9ba1897b8109
after_native_report_sha256: 44ae221d92eb839fd07d2c36cf9ecf62afd0c3dc26dc18ca19b623e1af0b3a5b
before_producer_wrapper_sha256: 2ec7eeeab27db38b7abf186533db0596a065239584d39e25a7979af4da905e3a
after_producer_wrapper_sha256: 06160ed0039c8d307443a8505a373c94a9baf995703f1d83026b52e001e92113
```

Comet experiment URL for the final metadata-only Gate E run:

```text
https://www.comet.com/zer0pa-imc/mobile-polymath-ai-training/0266804deeee44c098b32c9c5031cbd3
```

## 4. Chronology Since Report 04

### 4.1 Track A: Sign Inversion Attempt

Track A tested an alpha `-1.0` sign inversion candidate:

```yaml
experiment: sign_inversion_alpha_minus1
stage_id: C2
records: 27
authority_metric: decoder_token_nll_per_token
candidate_layer24_theta_sha256: 38351d33807a0eb05c40bb0f737657dad35b3823b6657ba6a4c1cb36c253775d
status: blocked_fail_closed
```

The phone-native scorer stalled before a complete after prediction or token-NLL
report was produced. The report records stable native runner CPU time while
elapsed wall time increased, failed ADB signal permissions for the Termux UID,
and SSH cleanup timing out during banner exchange.

Scientific consequence:

```text
The sign-inversion hypothesis remains untested on the authority metric.
It cannot be interpreted as pass, fail, or repair.
```

Engineering consequence:

```text
The run exposed the need for per-record progress sidecars, longer explicit
timeouts, owner-context process control, and fail-closed detached supervision.
```

### 4.2 Track B: JL Latency Investigation

Track B tested whether JL input compression produced a useful latency advantage
over raw hidden-state input paths. The closing verdict was:

```text
Across seq16/64/128/256, with properly powered wall-clock sampling and
accelerator-cycle profiling, JL input compression shows no statistically
distinguishable latency advantage over the raw-hidden path.
```

Wall-clock n20 medians were close:

| Sequence | Raw median ns | JL median ns | JL minus raw ns | JL/raw |
| --- | ---: | ---: | ---: | ---: |
| seq128 | 315095833.5 | 309933931.5 | -5161902.0 | 0.9836179934762609 |
| seq256 | 358425390.5 | 352344192.5 | -6081198.0 | 0.9830335736217883 |

The observed raw-path FFN matmul nonlinearity was attributed to QNN HTP
static-shape scheduling, tiling, or kernel-selection behavior, not to a proven
JL compression advantage. Track B was therefore closed as a non-blocker for
Gate E.

### 4.3 JL C2 Gate D2A Polar Acceptance

The JL C2 candidate passed the Gate D2A polar heldout acceptance report:

```yaml
status: gate_d2_phone_local_heldout_learning_evidence_pass
before_loss: 30906.645910614105
after_loss: 30860.12747423278
loss_delta: -46.518436381324136
full_heldout_required: true
full_heldout_evaluated: true
heldout_packet_count: 2500
scanned_packet_count: 2500
successful_qnn_steps: 2344
evaluated_answer_bearing_steps: 2344
qnn_steps_match_evaluated: true
overlap_count: 0
```

This was legitimate Gate D2A evidence only. It did not include a language-model
perplexity claim and did not authorize promotion without Gate E.

The new JL C2 theta was different from the prior July 6 C2 theta:

```yaml
prior_report_03_04_theta_post_sha256: e39db9f0bef0d422f85d54a1ba77860248c3721d18985eb88b535959295d983b
jl_c2_theta_post_layer24_sha256: 118a96c02e04f8ae36156399bc696f29844c944335460272ea6b87f42a7daf66
```

The baseline before NLL remained the same because the stable before surface and
heldout identity were preserved.

### 4.4 Host/Reuse Gate E Attempt

The first JL C2 Gate E attempt through the host/reuse path failed closed:

```yaml
status: blocked_fail_closed
first_missing_green_field: gate_e_native_polar_scorer_blocked:source_model_safetensors_path_not_found
record_count: 0
token_count: 0
native_polar_consumed_by_logits: false
rank16_cartesian_materialization_used: true
lm_head_or_unembedding_present: null
prediction_jsonl_written: false
```

The associated native scorer report also recorded:

```yaml
first_missing_green_field: source_model_safetensors_path_not_found
blockers:
  - source_model_safetensors_path_not_found
  - before_prediction_jsonl_absent
```

This path supplied no authority evidence. It was used only to clarify that the
model-host execution route was not acceptable for the JL C2 Gate E decision.

### 4.5 Phone-Native Gate E Engineering

The execution surface was moved to the RedMagic/Termux native runner:

```yaml
phone: RedMagic 10 Pro
device_serial: FY25013101C8
model: NX789J-EEA
phone_execution_surface: termux_private_native_gemma4_layer_runner
mac_model_host_allowed: false
runner_sha256: b0e63365ee28b94026074a169e983f7035cc4e22906361f6c6067524d2a55072
```

Functional engineering changes for this phase included:

```yaml
native_runner:
  added_max_heldout_records: true
  added_progress_jsonl_sidecar: true
  added_per_stage_timing: true
  kept_raw_progress_rows_out_of_reports: true

host_wrapper:
  passes_max_heldout_records: true
  summarizes_progress_metadata_without_raw_rows: true
  preserves_raw_stdout_stderr_boundary: true

supervision:
  detached_termux_supervisor: true
  per_arm_timeout_seconds: 43200
  sequence: before_then_after
  fail_closed_if_before_incomplete: true
  termux_wake_lock_requested: true
```

Validation recorded in the handover:

```yaml
local_cpp_build: passed
focused_tests: 26_passed_in_152.33s
earlier_wrapper_focused_tests: 35_passed_in_152.54s
phone_termux_build: passed
```

The first phone-native timebox was too short:

```yaml
run_id: apex-gate-e-phone-native-jl-c2-20260708-timebox60
status: blocked_fail_closed
before_arm_returncode: 124
elapsed_sec: 61.000368458000594
interpretation: timeout_too_short_not_science_evidence
```

The one-record instrumented probe then succeeded for both before and after:

```yaml
run_id: apex-gate-e-phone-native-jl-c2-20260708-instrumented-record1
status: gate_e_phone_native_scorer_pass
before_prediction_record_count: 1
after_prediction_record_count: 1
before_final_hidden_stream_seconds: 133.716
after_final_hidden_stream_seconds: 136.53
before_lm_head_nll_seconds: 2.57701
after_lm_head_nll_seconds: 2.56249
stderr_bytes: 0
```

This probe proved row emission on the target phone-native surface, but it was
not an authority result because it covered only one heldout record.

### 4.6 Detached Full27 Phone Run

The final full27 run used a detached 12-hour-per-arm supervisor:

```yaml
phone_root: /data/data/com.termux/files/home/polymath_phone_native_gate_e_20260708/gate_e_c2_jl
detached_root: /data/data/com.termux/files/home/polymath_phone_native_gate_e_20260708/gate_e_c2_jl/detached_full27_20260708_timeout12h
per_arm_timeout_seconds: 43200
expected_records_per_arm: 27
```

A prior shorter detached attempt was preserved as failed metadata:

```yaml
failed_root: detached_full27_20260708
status: blocked_fail_closed
before_returncode: 124
last_observed_record_index: 20
interpretation: timeout_too_short_under_detached_conditions
```

The 12-hour retry completed:

```yaml
supervisor_status: detached_phone_native_scorer_pass
before_records: 27
after_records: 27
before_completed_phone_time_sast: 2026-07-08 10:30:41
after_completed_phone_time_sast: 2026-07-08 12:15:21
before_prediction_sha256: dc0454c05a3a70dbc7c4b01008b80272e93ef0158dcbcefce64161abc08d3d55
after_prediction_sha256: 6c38ba5070b2f6dedaed190a063f6524336f11c946fa4950394444ee12dda481
```

During monitoring, the after arm appeared stale around record index 23. The
recovery policy required no restart unless progress age and `/proc` CPU/context
sampling proved a real stall. The run later completed without after-arm
termination. A metadata-only stall snapshot was preserved on the phone under:

```text
/data/data/com.termux/files/home/polymath_phone_native_gate_e_20260708/gate_e_c2_jl/detached_full27_20260708_timeout12h/stall_debug_after_20260708_115205/
```

## 5. Final Gate E Science Result

The final phone-native Gate E result is:

| Metric | Before | After | Delta |
| --- | ---: | ---: | ---: |
| NLL total | 392.54945020824175 | 392.9880645307021 | +0.43861432246035 |
| NLL per token | 14.538868526231177 | 14.555113501137114 | +0.01624497490593768 |
| Perplexity | 2061343.5279915193 | 2095103.4741836223 | +33759.94619210297 |

Negative NLL delta would indicate language-model improvement. Positive NLL
delta indicates regression. This candidate regressed.

Identity and custody checks in the final authority report:

```yaml
stage_id: C2
record_count: 27
token_count: 27
heldout_split_sha256: 2ff348e4b7776eb348b774cb8ea2fd04f7bb57ab8303ed9e4b5c6c1564767fae
heldout_record_id_set_sha256: a302851064f0b11377669fa738303161cd7582759aa5849eea2da307a1fde9a9
model_identity_sha256: b8cfd8264f3e61a1b340869d7cbffe11e771ba33cb2ff868c9941896413e70d4
tokenizer_identity_sha256: 99bc7dff78966a39b19dc8efaffebe95f34eeab6361018c0a7621bd12ac4995f
theta_pre_layer24_sha256: 5f70bf18a086007016e948b04aed3b82103a36bea41755b6cddfaf10ace3c6ef
theta_post_layer24_sha256: 118a96c02e04f8ae36156399bc696f29844c944335460272ea6b87f42a7daf66
lm_head_or_unembedding_present: true
overlap_count: 0
```

The native scorer contract also confirmed:

```yaml
native_polar_consumed_by_logits: true
rank16_cartesian_materialization_used: false
prediction_record_count: 27
token_nll_record_count: 27
token_nll_jsonl_sha256: 77cf0abc4ecc6aaa457f1f5affef670b0585ad123add86206f55ac06375d9115
native_returncode: 0
raw_boundary:
  prediction_jsonl_outside_git: true
  raw_logits_embedded: false
  raw_payload_bytes_in_report: false
  raw_stdout_stderr_embedded: false
  raw_tensors_embedded: false
  raw_theta_binaries_embedded: false
  secrets_embedded: false
```

The scientific contradiction is direct:

```text
The polar surrogate improved strongly.
The decoder-token NLL worsened strongly.
The surrogate and authority metric point in opposite directions.
```

## 6. Interpretation

### 6.1 Scientific Interpretation

The new JL C2 result is a fail on the only metric that can authorize promotion.
The candidate reduces the Gate D2A polar loss but increases decoder-token NLL.
That means the current polar objective, theta update, injection site, scale, or
sign is not aligned with the decoder-token language-model surface.

The July 6 random-theta result should be interpreted carefully. It showed that
the earlier trained-theta delta `+0.0022157230634061165` was inside random
perturbation motion. The new phone-native JL C2 delta
`+0.01624497490593768` is larger than that prior positive random edge. That
makes the new result worse than "indistinguishable from random" in operational
terms. It is an adverse, phone-native authority regression.

However, because a matched JL C2 phone-native random-theta band was not rerun,
the report should not overclaim a full new distributional statement. The gate
does not require that overclaim. Any positive NLL delta is a fail.

### 6.2 Engineering Interpretation

The evaluation stack is stronger after this work:

```yaml
phone_native_full27_gate_e_available: true
native_polar_consumed_by_logits: true
rank16_cartesian_materialization_used: false
lm_head_or_unembedding_present: true
progress_sidecar_available: true
per_stage_timing_available: true
metadata_only_comet_logging_available: true
outside_git_raw_prediction_custody_enforced: true
```

The failure is not absence of a Gate E instrument. The failure is that the
candidate state generated by the polar-learning stack regresses the real
decoder-token objective.

The engineering direction is therefore:

```text
Stop trying to narrate Gate D2A success as Gate E success.
Repair the update and coupling until Gate E NLL improves.
```

## 7. Anomalies And Unexpected Findings

### 7.1 Gate D2A Improvement Became A Larger Gate E Regression

The JL C2 candidate improved the polar heldout loss by `-46.518436381324136`,
far larger than the prior July 6 polar loss delta `-2.613627669660673`, but it
regressed NLL by `+0.01624497490593768`, also far larger than the prior Gate E
regression `+0.0022157230634061165`.

This is the central anomaly for the science team. Stronger movement on the
surrogate did not produce even a weak language-model improvement. It produced a
larger adverse authority movement.

### 7.2 The Before Surface Repeated Exactly While The After Surface Changed

The before NLL per token remained `14.538868526231177`, matching the earlier
Gate E reports. The after NLL changed because the JL C2 theta is a different
candidate from the July 6 theta. This supports stable baseline custody while
emphasizing that the new candidate is not a repair.

### 7.3 Host/Reuse Path Was Not Authority-Capable

The host/reuse attempt failed closed on missing model safetensors and absent
prediction/token-NLL records. The final report must not merge that failure with
the phone-native result. The host/reuse path supplied engineering evidence
about an unacceptable execution route, not science evidence about NLL.

### 7.4 SSH Banner Timeouts Coincided With CPU-Bound Native Work

During phone monitoring, SSH sometimes timed out during banner exchange while
ADB still showed the scorer process alive. The safe policy was to refresh SSH
non-destructively and avoid killing the scorer unless `/proc` sampling showed
real CPU/context stagnation. This policy prevented premature termination of the
after arm, which later completed.

### 7.5 Apparent After-Arm Stall At Record 23 Was Not A Proven Stall

The after arm was last readable around record index 23 during
`final_hidden_stream`. It had stale-looking progress metadata, but the run later
finished without restart. The anomaly points to long final-hidden phases,
limited progress granularity inside that phase, and Termux/SSH responsiveness
under sustained native load.

### 7.6 One-Record Timing Underpredicted Operational Friction

The one-record probe showed final-hidden stream time around 134 to 137 seconds
per record and LM-head NLL around 2.56 seconds. The full27 run still required
detached supervision, long timeouts, progress sidecars, and careful monitoring.
The bottleneck is the final-hidden stream, not the LM-head NLL computation.

### 7.7 The Word "Passed" Appears In A Non-Authority Report

`native_polar_scorer_report.json` says `gate_e_token_nll_passed`. That is a
contract-level production status, not a Gate E promotion verdict. The final
authority report says `falsified`.

## 8. Acceptance Ledger

Accepted:

```yaml
accepted:
  report_04_baseline_state_preserved: true
  jl_c2_gate_d2a_polar_metric_passed: true
  phone_native_gate_e_full27_completed: true
  before_prediction_record_count: 27
  after_prediction_record_count: 27
  native_polar_consumed_by_logits: true
  rank16_cartesian_materialization_used: false
  lm_head_or_unembedding_present: true
  metadata_only_comet_logging_completed: true
  raw_prediction_jsonl_kept_outside_git: true
```

Rejected claims:

```yaml
rejected_claims:
  gate_e_pass: rejected
  language_model_perplexity_improvement: rejected
  gate_d2a_as_gate_e_substitute: rejected
  host_reuse_path_as_authority_evidence: rejected
  sign_inversion_track_a_as_evidence: rejected
  c3_c4_d3_authorization: rejected
```

Open:

```yaml
open_questions:
  matched_phone_native_jl_c2_random_theta_band: not_run
  sign_inversion_authority_metric: blocked_not_measured
  exact_source_of_polar_nll_direction_divergence: unresolved
  final_hidden_stream_bottleneck_root_cause: unresolved
  robust_termux_owner_control_during_cpu_bound_native_work: needs_hardening
```

## 9. Required Next Repair

No continuation or promotion should proceed from this candidate. The next work
must be repair work against the authority metric:

1. Audit polar update sign, scale, layer mapping, and injection semantics against decoder-token NLL.
2. Rerun no-update and random-theta baselines on the exact JL phone-native surface for any new candidate.
3. Add targeted per-record metadata analysis for which records worsened or improved, without embedding raw rows or tokens in repo reports.
4. Improve final-hidden-stream observability and add safe resumability or checkpointing for full27 phone-native runs.
5. Treat Gate D2A as a necessary precursor only. Gate E NLL must go negative before any pass narrative is allowed.

## 10. Final Statement

The July 8 phone-native JL C2 Gate E run closes the immediate question. The
system can now execute the real native-polar decoder-token NLL gate on the
RedMagic phone for the full 27-record heldout split. The candidate did not pass
that gate. It improved the polar surrogate while worsening the language-model
authority metric.

The correct scientific status is:

```text
Gate E falsified.
Surrogate direction diverged.
No promotion authorized.
Repair required before further continuation.
```
