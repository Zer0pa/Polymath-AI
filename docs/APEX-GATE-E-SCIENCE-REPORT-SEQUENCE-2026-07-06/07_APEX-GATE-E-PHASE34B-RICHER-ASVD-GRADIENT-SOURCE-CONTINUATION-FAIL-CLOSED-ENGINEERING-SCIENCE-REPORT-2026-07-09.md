# Apex Gate E Phase34B Richer ASVD and Gradient-Source Continuation Fail-Closed Engineering and Science Report

Date: 2026-07-09

Repository: `/Users/Zer0pa/Polymat AI/Polymath-AI`

Sequence role: follow-on to `06_APEX-GATE-E-TASK-ALIGNED-PROJECTION-CANDIDATE-EXHAUSTION-ENGINEERING-SCIENCE-REPORT-2026-07-09.md`.

This is report `07` in the Gate E science-report sequence. Report `06`
recorded exhaustion of the first Phase34 task-aligned projection candidate set:
H1 activation-SVD was blocked by insufficient activation rank, H2
gradient-SVD/GaLore was blocked by the absent `dL_NLL/dh_layer24` surface, H3
finite-difference P-GAP was D3-falsified, and H4 RMT fallback was
D3-falsified.

This report records the authorized Phase34B continuation after that stop point:
the PRD amendment work to make storage and compute phone-native where
practical, prevent Mac-local raw artifact recreation after a disk-pressure
incident, run richer ASVD activation custody on the RedMagic/Termux platform,
and preserve Comet metadata logging. It is written for external engineering
and scientific review.

This report does not claim Gate E pass, language-model improvement, D2A
authorization, projection-matrix construction, C3/C4/D3 promotion, H5-control
authorization, or permission to continue unpredeclared experiments. The
governing acceptance gate remains phone-native decoder-token NLL per token on
the fixed Gate E authority surface. The authority result remains a regression:

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
  promotion_allowed: false

phase34b_continuation:
  run_id: 20260709T091440Z
  status: blocked_fail_closed
  first_missing_green_field: h1_asvd_effective_rank_below_min
  final_report: runtime/reports/apex_heterogeneous_cell/phase34b_gradient_source_20260709T091440Z/phase34b_task_aligned_projection_final_disposition_report.json
  final_report_sha256: a2ec3d0a0d5ff25e1d151f1ed274938eec77963ffed83c6707c603599a954ab6

h1_richer_asvd:
  status: blocked_fail_closed
  blocker: activation_effective_rank_below_min
  calibration_record_count: 128
  calibration_row_count: 990
  chunk_count_complete: 16
  centered_rank_estimate: 344
  effective_rank: 35.14290814917967
  top256_energy_ratio: 0.9774863300846467
  projection_matrix_built: false

h2_gradient_svd_galore:
  status: blocked_fail_closed
  first_missing_green_field: gradient_matrix_file_absent
  blockers:
    - gradient_matrix_file_absent
    - gradient_row_count_below_256_without_predeclared_adaptive_rank
  projection_matrix_built: false

downstream_gates:
  h5_controls: not_run
  d1_micro_correlation: not_run
  d2_small_correlation: not_run
  d3_full_correlation: not_run
  gate_d2a: not_run
  gate_e_full27: not_run
```

The short scientific verdict is:

```text
Phase34B materially improved the authenticity of the H1 ASVD test by moving
the richer activation custody and rank calculation onto phone/Termux storage
and compute. That richer ASVD attempt cleared the old centered-rank blocker,
but still failed the predeclared Stage 0 effective-rank requirement. H2 remains
blocked because the authentic decoder-NLL gradient surface still does not
exist. No projection candidate was authorized for downstream correlation,
controls, D2A, or Gate E.
```

## 2. What Report 07 Adds To Report 06

Report `06` ended with the correct conclusion that the strongest design ideas
had not been fully tested: H1 ASVD had been blocked before a valid 256D
candidate could be built, and H2/GaLore had not been attempted because the
`dL_NLL/dh_layer24` measurement surface was absent.

Report `07` records the next bounded step:

| Gap from report 06 | Phase34B action | Result |
| --- | --- | --- |
| H1 ASVD had only 34 records / 261 rows and centered rank 93 < 256 | Built a richer 128-record calibration manifest and executed phone-side chunk custody through chunk15 | Centered rank rose to 344, but effective rank was only 35.1429, below the Stage 0 minimum |
| Mac-local scratch and raw pulls were unsafe after disk pressure | Disabled Mac raw ASVD capture pulls and Mac raw concat output by default; kept raw captures on phone | Metadata-only reports returned to Mac; raw boundary preserved |
| Comet visibility was required | Logged H1 rank trend, H2 blocker, and final disposition to Comet | Live metadata tracking exists without raw tensor/token payload exposure |
| H2 gradient surface was absent | Wrote and logged a fail-closed H2 blocker report | No synthetic gradient substitute was promoted as authentic H2 |
| Downstream phone-hours could be wasted by weak candidates | Stopped before D1/D2/D3/H5/D2A/Gate E because no candidate passed Stage 0 | No unauthorized downstream rerun occurred |

The most important change relative to report `06` is not a pass. It is a more
defensible negative result for H1: richer phone-native ASVD calibration was
actually run far enough to replace the old centered-rank blocker with a sharper
effective-rank blocker.

## 3. Execution Summary

### 3.1 Phone-Native Custody And Disk Discipline

During Phase34B, oversight reported a Mac disk-pressure incident and completed
an offload of large trees from `/Users/Zer0pa/Polymat AI` to RedMagic Termux
storage:

```text
/data/data/com.termux/files/home/polymath_mac_offload/20260709T_disk_emergency/Polymat_AI/
```

The operating rule after offload was:

```text
Do not recreate large corpus, runtime scratch, model material, activation
captures, token files, theta binaries, prediction JSONLs, QNN build outputs, or
raw payloads on the Mac. Route them to phone storage and keep only
metadata/hash manifests on the Mac.
```

Phase34B honored that rule after the incident. The host-side tooling now blocks
or deprecates the old raw-pull path:

| Tooling change | Purpose |
| --- | --- |
| `scripts/host/run_phase34b_phone_asvd_custody_snapshot.py` | Phone-side metadata/rank custody runner; pulls JSON metadata only |
| `scripts/host/follow_phase34b_asvd_capture_chain.py` | Deprecated fail-closed for Mac raw activation capture pulling |
| `scripts/host/pull_phase34b_asvd_capture_metadata.py` | Blocks `--pull-raw-captures` unless explicit break-glass flag is used |
| `scripts/host/build_phase34b_asvd_activation_concat_report.py` | Blocks Mac-local raw concat output under `/Users/Zer0pa/Polymat AI` |

This is an operational correction, not a scientific pass. It reduces the risk
that future projection work invalidates custody by silently rematerializing raw
data on the wrong storage platform.

### 3.2 H1 Richer ASVD Continuation

The H1 continuation used a richer calibration set:

```yaml
calibration_manifest_status: pass
calibration_record_count: 128
calibration_manifest_sha256: fe66f30505127c61c1ec7fc16297c995437984ba06a702af7d839f8bb7d17233
phone_chunk_count_complete: 16
cumulative_activation_rows: 990
```

The final phone-side rank report was:

```yaml
path: runtime/reports/apex_heterogeneous_cell/phase34b_gradient_source_20260709T091440Z/phase34b_asvd_rank_trend_chunk15_report.json
sha256: 480cff756656a3f17771d275ad66d995a40e31e9f3584c74eeaebbf12a182ae6
status: blocked_fail_closed
first_missing_green_field: activation_effective_rank_below_min
centered_rank_estimate: 344
effective_rank: 35.14290814917967
singular_value_1: 1031.6451863022082
singular_value_256: 41.173152119682314
singular_value_last: 3.4042300330801224e-14
top256_energy_ratio: 0.9774863300846467
```

Interpretation:

```text
The old H1 failure mode was centered rank below projection dimension
(93 < 256). Phase34B fixed that specific blocker: centered rank reached 344.
But the richer activation surface remained spectrally concentrated. Effective
rank was only 35.1429, below the predeclared Stage 0 minimum. Therefore the
ASVD projection matrix was not built.
```

This is the correct fail-closed behavior. Building a `[256,2560]` projection
from a surface with low effective rank would convert a known measurement
problem into a candidate narrative.

### 3.3 H2 Gradient-SVD / GaLore

The H2 state did not improve:

```yaml
path: runtime/reports/apex_heterogeneous_cell/phase34b_gradient_source_20260709T091440Z/h2_layer24_gradient_source_absent_report.json
sha256: 1d61cf6876efe3a2547f4ad4189df935a76f12bc7e56e18c2df9cd3f83949a4a
status: blocked_fail_closed
first_missing_green_field: gradient_matrix_file_absent
blockers:
  - gradient_matrix_file_absent
  - gradient_row_count_below_256_without_predeclared_adaptive_rank
projection_matrix_built: false
```

The scientific meaning is unchanged from report `06`: the strongest design
route still requires a real measurement of how nudging layer 24 changes the
phone-native decoder-token NLL surface. No finite-difference fallback, RMT
fallback, polar surrogate, or host-only approximation was promoted as that
surface.

## 4. Downstream Gate Discipline

No downstream stage was launched after the Phase34B Stage 0 blockers:

```yaml
not_run:
  - h5_controls
  - d1_micro_correlation
  - d2_small_correlation
  - d3_full_correlation
  - gate_d2a
  - gate_e_full27

reason:
  - H1 did not produce an admissible ASVD projection matrix
  - H2 did not produce an admissible gradient-SVD/GaLore projection matrix
  - H3/H4 had already been falsified under report 06 and were not relitigated
```

This preserves the ladder:

```text
candidate construction
  -> Stage 0 admissibility
  -> D1/D2/D3 correlation
  -> H5 controls
  -> Gate D2A
  -> Gate E full27
```

Phase34B stopped at Stage 0. Therefore it cannot and does not modify the Gate E
authority verdict.

## 5. Artifact Index

All listed artifacts are metadata reports, code-state references, hashes, or
Comet metadata links. Raw activation tensors, token rows, prediction JSONLs,
theta binaries, QNN tensors, model weights, payload dumps, stdout/stderr dumps,
and secrets are not embedded in this report.

| Artifact | Path | sha256 | Role |
| --- | --- | --- | --- |
| Final Phase34B disposition | `runtime/reports/apex_heterogeneous_cell/phase34b_gradient_source_20260709T091440Z/phase34b_task_aligned_projection_final_disposition_report.json` | `a2ec3d0a0d5ff25e1d151f1ed274938eec77963ffed83c6707c603599a954ab6` | Final fail-closed disposition for Phase34B |
| Final disposition Comet result | `runtime/reports/apex_heterogeneous_cell/phase34b_gradient_source_20260709T091440Z/phase34b_task_aligned_projection_final_disposition_comet_result.json` | `0c9ef192b6f957938e1474de686c74fbc5e006889e329828ad35375c73f87396` | Metadata-only Comet logging result |
| H1 final rank trend | `runtime/reports/apex_heterogeneous_cell/phase34b_gradient_source_20260709T091440Z/phase34b_asvd_rank_trend_chunk15_report.json` | `480cff756656a3f17771d275ad66d995a40e31e9f3584c74eeaebbf12a182ae6` | H1 richer ASVD Stage 0 blocker |
| H2 gradient-source blocker | `runtime/reports/apex_heterogeneous_cell/phase34b_gradient_source_20260709T091440Z/h2_layer24_gradient_source_absent_report.json` | `1d61cf6876efe3a2547f4ad4189df935a76f12bc7e56e18c2df9cd3f83949a4a` | H2 absent-gradient fail-closed report |
| H1 stratified calibration manifest | `runtime/reports/apex_heterogeneous_cell/phase34b_gradient_source_20260709T091440Z/phase34b_asvd_stratified128_manifest.json` | `fe66f30505127c61c1ec7fc16297c995437984ba06a702af7d839f8bb7d17233` | 128-record richer ASVD calibration manifest |
| Phase34B provider readiness | `runtime/reports/apex_heterogeneous_cell/phase34b_gradient_source_20260709T091440Z/phase34b_provider_readiness_report.json` | `365856c84f53f8d930924829573f7cb02acf74505053ecf4d82fee2b5f80812c` | Stage 0 provider/readiness pass |
| Gate E authority report | `runtime/reports/apex_heterogeneous_cell/gate_e_phone_native_jl_c2_full27_20260708_timeout12h/gate_e_token_nll_perplexity_report.json` | `70739a1c78b5d1cea5a98d1826f8a1b4c658929c7b534612e346ee0309e432f0` | Sovereign Gate E falsification retained from reports `05` and `06` |

Metadata-only Comet logging:

```yaml
workspace: zer0pa-imc
project_name: mobile-polymath-ai-training
h1_rank_trend_url: https://www.comet.com/zer0pa-imc/mobile-polymath-ai-training/997fed03f8f4485f97935fd3b063c63a
h2_blocker_url: https://www.comet.com/zer0pa-imc/mobile-polymath-ai-training/82778d954bea4b3ab1687e5ee757d2e3
final_disposition_url: https://www.comet.com/zer0pa-imc/mobile-polymath-ai-training/4908887e34cd4abc9ad5d0754bacd4bf
```

Code-state commits at the end of this report:

```text
03cebad phase34b: record final projection disposition
271c125 phase34b: record phone asvd custody chunk15
88f6b1e phase34b: record phone asvd custody chunk14
f5b4417 phase34b: record phone asvd custody chunk13
dd96e87 phase34b: record phone asvd custody chunk12
```

The branch was pushed to:

```text
origin/gemma4-megakernel-native-training
head: 03cebadf3b4c55e12ea3f7b2587596e98e683f4b
```

## 6. Raw Boundary And Custody

```yaml
raw_boundary:
  metadata_only_report: true
  raw_rows_embedded: false
  raw_tensors_embedded: false
  tokens_embedded: false
  logits_embedded: false
  theta_binaries_embedded: false
  secrets_embedded: false

phone_storage:
  raw_activation_captures: retained_on_termux_storage
  representative_phone_path: /data/data/com.termux/files/home/polymath_phase34b_20260709T091440Z/asvd_activation_capture

mac_storage:
  raw_capture_pull: blocked_by_default
  raw_concat_output_under_polymat_ai: blocked_by_default
  retained_artifacts: metadata_and_hash_reports_only
```

This boundary is part of the scientific result because the report depends on
custody of large raw artifacts without exposing or duplicating them into the
external-review document.

## 7. Falsification Matrix

| Claim | Status | Evidence |
| --- | --- | --- |
| Gate E passes | False | Authority NLL delta is `+0.01624497490593768` |
| H1 ASVD can now build a projection matrix | False | Effective rank `35.1429` below Stage 0 minimum |
| H1 old centered-rank blocker remains unchanged | False | Centered rank improved to `344`, but the replacement blocker is effective rank |
| H2/GaLore has a usable gradient matrix | False | `gradient_matrix_file_absent` |
| H3/H4 were reopened | False | They were not relitigated in Phase34B |
| H5 controls are authorized | False | No projection candidate passed construction gates |
| D1/D2/D3/D2A/Gate E reruns are authorized from this result | False | No admissible projection candidate exists |
| Raw phone artifacts were copied into this report | False | Report is metadata/hash only |

## 8. External Reviewer Checklist

A reviewer should be able to evaluate this report using only metadata artifacts:

1. Verify the final disposition report hash:

```text
shasum -a 256 runtime/reports/apex_heterogeneous_cell/phase34b_gradient_source_20260709T091440Z/phase34b_task_aligned_projection_final_disposition_report.json
```

Expected:

```text
a2ec3d0a0d5ff25e1d151f1ed274938eec77963ffed83c6707c603599a954ab6
```

2. Inspect `h1_asvd.final_stats` and confirm:

```yaml
centered_rank_estimate: 344
effective_rank: 35.14290814917967
```

3. Inspect `h2_gradient_svd` and confirm:

```yaml
status: blocked_fail_closed
first_missing_green_field: gradient_matrix_file_absent
```

4. Inspect `authority_gate_e` and confirm:

```yaml
status: falsified
nll_delta_per_token: 0.01624497490593768
promotion_allowed: false
```

5. Confirm the downstream gates are listed as not run:

```text
h5_controls, d1_micro_correlation, d2_small_correlation, d3_full_correlation,
gate_d2a, gate_e_full27
```

## 9. Conclusion

Phase34B did not close Gate E. It also did not produce an admissible
task-aligned projection candidate.

What Phase34B did establish is narrower and important:

```text
Richer phone-native ASVD custody removed the previous centered-rank blocker,
but exposed a stronger effective-rank blocker. The gradient-source blocker
remains unresolved. Therefore the current repair program remains fail-closed
until a new predeclared candidate or authentic gradient-source program exists.
```

The next scientifically valid step is not another downstream phone Gate E run
with the same candidate state. It is a new predeclared program that either:

1. Produces an authentic `dL_NLL/dh_layer24` surface with fidelity checks
against the phone-native decoder-token NLL surface, or
2. Produces a higher-diversity activation calibration surface whose effective
rank, not merely centered rank, clears the Stage 0 admissibility requirement.

Until then:

```yaml
gate_e_pass: false
promotion_allowed: false
projection_candidate_available: false
downstream_gate_execution_authorized: false
```
