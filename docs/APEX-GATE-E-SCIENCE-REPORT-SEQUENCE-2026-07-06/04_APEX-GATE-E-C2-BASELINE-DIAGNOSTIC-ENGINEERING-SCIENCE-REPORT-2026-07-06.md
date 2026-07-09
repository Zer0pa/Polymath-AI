# Apex Gate E C2 Baseline Diagnostic Engineering and Science Report

Date: 2026-07-06

Repository: `/Users/Zer0pa/Polymat AI/Polymath-AI`

Sequence role: follow-on to `03_APEX-GATE-E-NATIVE-POLAR-FALSIFICATION-ENGINEERING-SCIENCE-REPORT-2026-07-06.md`.

This report completes the July 6 Gate E science report sequence by recording the
bounded post-falsification diagnostic result. It does not restate the Gate D
mechanism report, the Gate D-to-E transition report, or the native-polar Gate E
falsification report. Those reports already established:

```text
01: phone-local polar continuation can improve the fixed heldout polar metric
02: Gate E decoder token NLL/perplexity is the sovereign language-model gate
03: native polar theta is consumed by logits, but trained C2 theta regresses NLL
```

The missing question after report 03 was narrower:

```text
Is the trained-theta Gate E regression a directional training signal, runtime
noise, or merely random-theta-scale perturbation at this sample/effect size?
```

The answer after E1 and E2 is:

```text
E1 rules out no-update scorer/runtime noise at this surface.
E2 falsifies the directional-learning interpretation of the trained theta delta.
No promotion or long-horizon continuation is authorized from the C2 evidence.
```

## 1. Current Verdict

```yaml
c2_gate_e_trained_theta:
  before_nll_per_token: 14.538868526231177
  after_nll_per_token: 14.541084249294583
  nll_delta_per_token: 0.0022157230634061165
  sign_convention: after_minus_before
  interpretation: regression

e1_no_update_baseline:
  status: pass
  classification: native_no_update_replay_exact_zero
  nll_delta_per_token: 0.0
  row_delta_stdev: 0.0
  record_count: 27
  token_count: 27
  conclusion: scorer_reuse_and_no_update_runtime_noise_not_explanation

e2_random_theta_baseline:
  status: fail_trained_theta_not_distinguishable_from_random_theta_baseline
  completed_seed_count: 4
  blocked_excluded_seed_count: 1
  random_theta_deltas: [0.0015742374546145281, 0.002711374664297889, -0.0022761499692689068, 0.00400865832950701]
  random_mean_delta_per_token: 0.0015045301197876301
  random_sample_stdev_delta_per_token: 0.0027095837868353987
  random_min_delta_per_token: -0.0022761499692689068
  random_max_delta_per_token: 0.00400865832950701
  trained_delta_inside_random_min_max: true
  trained_abs_delta_less_than_random_abs_max: true
  same_sign_random_regressions_exceeding_trained_delta_count: 2
  opposite_sign_random_improvements_count: 1

decision:
  promotion_allowed: false
  d3_c3_long_horizon_authorized: false
  surrogate_gate_authority: false
  trained_regression_directional_vs_random_theta: false
  measurement_dominated_by_random_theta_scale: true
  next_allowed_action: repair_polar_update_sign_scale_injection_and_effect_size
```

Negative NLL delta means language-model improvement. Positive NLL delta means
language-model regression. The trained update regressed by `+0.0022157230634061165`.
The random-theta controls produced both larger regressions and one improvement
of comparable magnitude. That is the decisive fact.

## 2. What This Adds To The Prior Reports

Report 03 proved that native-polar Gate E is now measuring the real decoder
surface and that the trained C2 theta state failed that surface. It did not yet
classify whether the failed delta was:

- deterministic scorer/reuse noise;
- random perturbation at the measured effect size;
- wrong-sign or wrong-scale coupling;
- a weak effect too small for this heldout surface;
- a genuine but adverse learned direction.

This report adds the first two controls:

| Diagnostic | Result | Scientific meaning |
| --- | --- | --- |
| E1 no-update | exact zero NLL delta, zero row stdev, matching stable prediction SHA | The scorer and native runtime can reproduce the no-update surface exactly for this heldout set. |
| E2 random theta | random deltas span `[-0.0022761499692689068, +0.00400865832950701]` and contain the trained delta | The trained theta effect is not distinguishable from random theta perturbation at this scale. |

That converts the Gate E conclusion from "C2 trained theta regressed" to a
stronger operational statement:

```text
The current polar update cannot be treated as a directional language-model
learning update. The governing metric sees it as random-theta-scale motion.
```

## 3. Artifact Index

All listed artifacts are metadata or report artifacts. Raw prediction JSONL,
token-NLL JSONL, logits, theta binaries, model weights, and secrets are not
embedded in this report.

| Artifact | Path | sha256 | Role |
| --- | --- | --- | --- |
| Diagnostic PRD | `docs/PRD-APEX-GATE-E-C2-POLAR-BINARY-DIAGNOSTIC-2026-07-06.md` | `a3a8a7386be4321c7153dd3c66bef62c8990de9acb6c6a73a0e41227ab780fd2` | Defines E1/E2 diagnostic plan after Gate E falsification |
| E1 no-update diagnostic | `runtime/reports/apex_heterogeneous_cell/apex_gate_e_c2_e1_one_fresh_no_update_20260706T141719Z/e1_no_update_diagnostic_report.json` | `3e32896bc79022bc36baf283b59e33a834f69f418a29cf91bde2bc5d61116cc7` | Exact-zero no-update replay result |
| E1 Comet logging result | `runtime/reports/apex_heterogeneous_cell/apex_gate_e_c2_e1_one_fresh_no_update_20260706T141719Z/e1_no_update_diagnostic_comet_logging_result.json` | `92ad8f3515d0c9fc32e3d6776cc914c4b3d9115c952b2a4059e8051fe0794b0c` | Comet live comments and safe metadata logging |
| E2 random seed 2026070601 | `runtime/reports/apex_heterogeneous_cell/apex_gate_e_c2_e2_random_theta_seed_2026070601_20260706T154849Z/random_theta_comparator_report.json` | `9ad73f531130ae67dc5633c561bcca8c46a3864280ce4f22f3e25464730e808f` | Random-theta comparator |
| E2 random seed 2026070602 | `runtime/reports/apex_heterogeneous_cell/apex_gate_e_c2_e2_random_theta_seed_2026070602_20260706T165538Z/random_theta_comparator_report.json` | `b53fffd471265dd0b56fc6b54358ff63a11ec0eae1c49e62ca34579aaeed97ba` | Random-theta comparator |
| E2 random seed 2026070603 | `runtime/reports/apex_heterogeneous_cell/apex_gate_e_c2_e2_random_theta_seed_2026070603_20260706T180233Z/random_theta_comparator_report.json` | `6ed780d93ed715325772fc8d6ace58417eaa2d8da1773fde9f267005c0cf2f4e` | Opposite-sign random improvement |
| E2 random seed 2026070604 | `runtime/reports/apex_heterogeneous_cell/apex_gate_e_c2_e2_random_theta_seed_2026070604_20260706T191002Z/random_theta_comparator_report.json` | `636711d8cea2f278d5566840ad1993e4efc46ccde41844695865030e39b52be8` | Largest random-theta regression |
| E2 blocked seed 2026070605 | `runtime/reports/apex_heterogeneous_cell/apex_gate_e_c2_e2_random_theta_seed_2026070605_20260706T203521Z/e2_random_theta_seed_2026070605_blocked_report.json` | `1f11b342c4a02f6e1fc3e78c7a26aac009e498139d434ef841e3d9326ff7e736` | Stalled at 5/27 rows and excluded |
| E2 aggregate report | `runtime/reports/apex_heterogeneous_cell/apex_gate_e_c2_e2_random_theta_aggregate_20260706T214031Z/e2_random_theta_aggregate_report.json` | `8c6a2e005efc297954fa43072d48c888b634353a682fe2d964f29f58e82fd61d` | Decisive random-theta baseline comparison |
| E2 aggregate Comet result | `runtime/reports/apex_heterogeneous_cell/apex_gate_e_c2_e2_random_theta_aggregate_20260706T214031Z/e2_random_theta_aggregate_comet_logging_result.json` | `293465a725d909442a40a925df22352e1bc1235cbc6a8cc76381e6699e18bf41` | Safe Comet aggregate logging with live comments |
| GPD comparison contract | `GPD/comparisons/apex-gate-e-c2-e2-random-theta-COMPARISON.md` | `1d0618c27c940bdce9bf90be5cc082b410e2279c0ccfe4f0f64b3df22b001d58` | Machine-readable fail verdict |

Comet experiment URLs:

| Run | URL |
| --- | --- |
| E1 no-update | `https://www.comet.com/zer0pa-imc/mobile-polymath-ai-training/91793c708a9846ce8f22fdb2229918db` |
| E2 seed 2026070601 | `https://www.comet.com/zer0pa-imc/mobile-polymath-ai-training/1b9d090c40094109887a14f435a9844b` |
| E2 seed 2026070602 | `https://www.comet.com/zer0pa-imc/mobile-polymath-ai-training/097c38672a0d466688e03af63ff4319d` |
| E2 seed 2026070603 | `https://www.comet.com/zer0pa-imc/mobile-polymath-ai-training/84acc9346d7f4483836145d182a69873` |
| E2 seed 2026070604 | `https://www.comet.com/zer0pa-imc/mobile-polymath-ai-training/6f9dd75ea3c048648a2609cf7fca47ff` |
| E2 seed 2026070605 blocked | `https://www.comet.com/zer0pa-imc/mobile-polymath-ai-training/78cd91eb51754f0bac5c2772d27d09ec` |
| E2 aggregate | `https://www.comet.com/zer0pa-imc/mobile-polymath-ai-training/3eb01ad3eab64e3b94c1c651f2a999b7` |

## 4. E1: No-Update Runtime Noise Floor

E1 replayed the native decoder path with no update. The result was exact zero:

```yaml
classification: native_no_update_replay_exact_zero
nll_delta_per_token: 0.0
row_delta_stdev: 0.0
bootstrap_95_ci_mean_delta: [0.0, 0.0]
fresh_prediction_matches_original_sha256: true
record_count: 27
token_count: 27
```

This matters because it closes an easy escape hatch. The C2 trained-theta
regression is not explained by the scorer randomly changing outputs between
before and after arms. The instrument can hold a no-update state fixed on this
surface.

The zero result does not prove the trained update is meaningful. It only
establishes that the next comparison should be against actual perturbation
baselines, not against a suspected runtime wobble.

## 5. E2: Random-Theta Baseline

E2 materialized random native-polar theta states and scored them through the
same decoder-token NLL comparison surface. Four seeds completed:

| Seed | Before NLL/token | After NLL/token | Delta | Improved rows | Worsened rows | Row delta stdev |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026070601 | 14.538868526231177 | 14.54044276368579 | +0.0015742374546145281 | 10 | 17 | 0.019354849861492603 |
| 2026070602 | 14.538868526231177 | 14.541579900895474 | +0.002711374664297889 | 13 | 14 | 0.01760177152444759 |
| 2026070603 | 14.538868526231177 | 14.536592376261908 | -0.0022761499692689068 | 15 | 12 | 0.02649785940515947 |
| 2026070604 | 14.538868526231177 | 14.542877184560682 | +0.00400865832950701 | 13 | 14 | 0.016971756983310982 |

Seed `2026070605` stalled at `5/27` rows with a partial
`after_predictions.jsonl.tmp` and stable runner CPU time. It was terminated,
recorded as blocked, and excluded from the aggregate. Including partial raw
rows would have contaminated the authority comparison.

The completed E2 distribution is decisive enough for the current question:

```yaml
trained_delta: +0.0022157230634061165
random_min: -0.0022761499692689068
random_max: +0.00400865832950701
trained_inside_random_range: true
random_abs_max_exceeds_trained_abs: true
same_sign_random_regressions_exceeding_trained: [2026070602, 2026070604]
opposite_sign_random_improvement: [2026070603]
```

The trained update does not separate from random theta. Worse, random theta can
move the authority metric in the improving direction at comparable magnitude.
Therefore the current trained theta update is not evidence of aligned descent
on decoder-token NLL.

## 6. Scientific Interpretation

The natural analog is not adaptation yet. It is perturbation response.

In a physical system, a control vector has earned directional meaning only when
its effect separates from isotropic random kicks under the observable that
matters. Here, the observable that matters is decoder-token NLL. The trained
polar vector does not separate. The observed trained regression lives within the
random-theta response envelope.

That points to one or more of these failure modes:

- the polar surrogate objective is misaligned with decoder-token NLL;
- the sign of the injected update is wrong for the decoder surface;
- the scale is too large or too small relative to the local decoder geometry;
- the injection point is weakly coupled or coupled to the wrong computation;
- the effective update is too small to survive the real evaluation surface;
- the polar representation carries perturbation energy without task-gradient direction.

This is not a reason to weaken Gate E. It is the reason Gate E exists. Nature
does not reward an internal state variable for moving unless it lowers the
system's governing energy under the real dynamics. For this project, the task
energy proxy is decoder-token NLL. The polar update must lower that, not merely
lower a surrogate.

## 7. Engineering Interpretation

The execution path itself is stronger than it was before this sequence:

```yaml
native_polar_consumed_by_logits: true
rank16_cartesian_materialization_used: false
lm_head_or_unembedding_present: true
no_update_runtime_noise_floor_known: true
random_theta_baseline_known: true
live_comet_comments_integrated: true
raw_payloads_excluded_from_reports_and_comet: true
gpd_comparison_contract_validated: true
```

The failure is not that the evaluation stack is absent. The failure is that the
current polar training/update stack does not produce a verified directional
language-model improvement.

Operationally, this changes the repair target:

```text
Do not spend compute proving the current update harder.
Instrument and repair the coupling until a candidate beats no-update and
random-theta baselines on decoder-token NLL.
```

## 8. Acceptance Ledger

Accepted:

```yaml
accepted:
  gate_e_authority_metric_sovereign: true
  e1_no_update_exact_zero: true
  e2_random_theta_completed_seed_count: 4
  e2_seed5_blocked_and_excluded: true
  random_theta_distribution_contains_trained_delta: true
  comet_live_comments_for_runs: true
  metadata_only_artifact_boundary_preserved: true
  gpd_comparison_verdict: fail
```

Not accepted:

```yaml
not_accepted:
  gate_e_pass: false
  c2_language_model_improvement: false
  trained_theta_directional_learning_signal: false
  d3_execution: false
  c3_long_horizon_execution: false
  surrogate_metric_as_promotion_authority: false
```

## 9. Required Next Repair

The next valid work is repair, not scale-out. A valid repair plan must preserve
the same authority hierarchy:

1. Decoder-token NLL remains sovereign.
2. No-update baseline remains part of acceptance.
3. Random-theta baseline remains part of acceptance.
4. Raw predictions/logits/theta stay out of docs and Comet.
5. Live Comet comments remain required for every run.
6. No D3 or full C3 run starts until a repaired candidate passes Gate E.

The repair should target the coupling directly:

| Repair target | Question to answer | Required evidence |
| --- | --- | --- |
| Sign | Does negating or inverting the polar update improve NLL? | Same heldout decoder-token NLL with no-update/random controls |
| Scale | Is the trained effect hidden by wrong alpha? | Bounded alpha sweep with fail-closed metadata logging |
| Injection point | Is theta entering the wrong decoder site or layer schedule? | Layer/site ablation under the native-polar path |
| Effective size | Is the update too weak for the authority surface? | Norm/effect-size instrumentation tied to NLL movement |
| Objective alignment | Does polar loss predict target-token NLL at all? | Correlation or rank test across controlled perturbations |

The minimum successful repair is not "polar loss improves again." The minimum
successful repair is:

```text
decoder-token NLL improves, no-update stays stable, trained theta beats
random-theta controls, and the report logs enough metadata to reproduce the
decision without raw payload exposure.
```

## 10. Completion Of The Report Sequence

The July 6 sequence now has a closed scientific arc:

```text
01 mechanism evidence
  -> 02 authority metric contract and interface blocker
  -> 03 native-polar authority falsification
  -> 04 baseline classification of the falsification
```

The final state is not success and not ambiguity:

```text
Gate E caught a surrogate failure.
E1 showed the measurement stack can be stable.
E2 showed the trained effect is random-theta-scale and non-directional.
The project should now repair the polar update, not run longer.
```
