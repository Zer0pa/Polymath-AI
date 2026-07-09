# Apex Gate D to Gate E Engineering and Science Report

Date: 2026-07-05

Repository: `/Users/Zer0pa/Polymat AI/Polymath-AI`

Prior report extended: `docs/APEX-GATE-D-ENGINEERING-SCIENCE-REPORT-2026-07-05.md`

Prior report sha256: `013d91b8d7f5150f7a176a7bb595dd9a3a553f520967e91381288fdd2808adac`

Governing PRD: `docs/PRD-APEX-HETEROGENEOUS-CELL-END-TO-END-2026-07-03.md`

Governing PRD sha256 at report time: `b526fdccb6520367699a8a05261ac0d4309daa3a0b766e3093baafdfd21acb68`

Current verdict:

```yaml
gate_d_c1:
  status: accepted_polar_heldout_learning_evidence
  theta_post_sha256: 65b79f6c3127e15b26d756c352c5faa84afa81e99ff8a921f30e02b0a1b24c45
  promoted: false
  promotion_blocker: mandatory_comet_logging_not_logged

gate_d_c2:
  status: d2a_polar_acceptance_report_passed
  theta_post_sha256: f3c1b5476e1f81e4afdeea86a8c4a9c6c4b56570101d5db4e75dcf56fb56bdab
  promoted: false
  promotion_blocker: mandatory_comet_logging_failed

gate_e:
  status: blocked_fail_closed
  first_missing_green_field: gate_e_decoder_probe_blocked:c5_full_decoder_rank16_adapter_payload_size_mismatch
  token_nll_records: absent
  language_model_perplexity_claim: false

gate_d3:
  status: blocked_fail_closed
  first_missing_green_field: gate_d3_gate_e_not_passed
```

No "trained Gemma on a phone" claim is authorized by the current evidence. Gate
D now has repeated polar-surrogate mechanism evidence. Gate E, the first
language-model quality gate, is still blocked before token-level NLL or
perplexity can be computed.

## 1. Purpose of This Report

The previous Gate D engineering/science report documented a C1 phone-local
continuation result with fixed-heldout polar improvement. That was a real
mechanism result, but it was not language-model evidence. The present report
documents what happened after that report:

- the PRD was extended so Gate E, not Gate D, is sovereign for any LM-quality
  claim;
- D2A custody and one-command Gate D reproducibility were added;
- C2 was run through the same D1/D2/D0/D2A discipline used for C1;
- Gate E split identity was built against fixed text heldout material;
- a phone-local C5/full-decoder probe was attempted;
- the real Gate E blocker was isolated as an adapter-interface mismatch;
- D3 comparators were correctly held behind Gate E;
- Comet logging was made mandatory and is currently blocked by absent
  `COMET_API_KEY`.

This document is not a success narrative. It is the current engineering and
science state, including the exact blockers that prevent promotion.

## 2. What Changed Versus the Prior Gate D Report

The prior report established:

```yaml
prior_gate_d_report_scope:
  corpus_stage: C1
  accepted_gate: Gate D2A
  accepted_metric: fixed_heldout_polar_loss_delta
  accepted_delta: -302.8965486097695
  language_model_perplexity: not_measured
  comet_logging: not_logged
```

This report adds:

```yaml
new_scope:
  c2_gate_d_reproducibility: executed
  c2_d2a_polar_delta: -235.78098386604688
  c2_train_heldout_overlap: 0
  c2_gate_e_split_identity: pass
  c2_gate_e_decoder_probe: blocked
  c2_gate_e_token_nll: absent
  c2_d3_comparators: blocked_until_gate_e_passes
```

The most important scientific change is the authority metric. Gate D is now
only a polar-surrogate evidence gate. Gate E is the actual apex gate for
language-model quality because it requires token-level negative log-likelihood
and perplexity on a fixed text heldout set.

## 3. Sovereign Acceptance Logic

The governing sequence in the PRD is now:

```text
D2A custody freeze
  -> one-command D0/D1/D2/D2A reproducibility
  -> C2/C3/C4 under identical D2A discipline
  -> Gate E token-level NLL/perplexity
  -> surrogate-validity decision
  -> D3 comparator suite under Gate E metric
```

The acceptance hierarchy is strict:

1. A D2A polar pass can show that the phone-local continuation mechanism moved
   the declared polar objective in the right direction.
2. A D2A polar pass cannot show that Gemma improved as a language model.
3. Gate E must consume the accepted theta state through a decoder/logit surface
   and compute token-level NLL/perplexity.
4. Surrogate validity is inside Gate E. The polar delta and NLL delta must be
   compared by sign before the polar metric may be treated as meaningful for
   LM quality.
5. D3 comparators are meaningful only after Gate E exists. Running comparator
   arms against an unvalidated surrogate would waste compute and create false
   confidence.
6. Promoted evidence requires Comet logging with `status: logged`. Dry-runs and
   missing-key reports do not satisfy promotion.

## 4. Pipeline Map

The pipeline actually used in this work has two layers: Gate D polar
continuation and Gate E decoder/perplexity evaluation.

```text
C2 training PJP1
  -> Gate D1 phone-local QNN/HTP forward evidence
  -> native Adreno/Vulkan theta update continuation
  -> chained theta_post_step_015.bin identity
  -> Gate D2 fixed C1-C4 heldout polar evaluation
  -> Gate D0 binding preflight
  -> Gate D2A aggregate polar acceptance report
  -> mandatory Comet logging
  -> D2A custody manifest

C2 accepted theta identity
  + C2 fixed text heldout QA JSONL
  + Gemma 4 E4B decoder manifest/tokenizer identity
  -> Gate E heldout split identity
  -> phone C5/full-decoder probe
  -> token-level before/after NLL JSONL
  -> Gate E token NLL/perplexity report
  -> surrogate-validity decision
  -> D3 comparators
```

Current breakpoints:

```yaml
gate_d_breakpoint:
  field: mandatory_comet_logging_failed
  reason: COMET_API_KEY environment not present

gate_e_breakpoint:
  field: c5_full_decoder_rank16_adapter_payload_size_mismatch
  reason: "accepted polar theta payload is 1024 bytes and is not the rank-16 adapter payload shape expected by the C5 full-decoder scorer"

gate_d3_breakpoint:
  field: gate_d3_gate_e_not_passed
  reason: no Gate E token NLL/perplexity result exists
```

## 5. Artifact Ledger

All artifacts below are metadata reports. They do not embed raw QNN tensors,
theta binaries, model weights, raw stdout/stderr, secrets, or raw corpus rows.

| Artifact | Path | sha256 | Status |
| --- | --- | --- | --- |
| Prior Gate D report | `docs/APEX-GATE-D-ENGINEERING-SCIENCE-REPORT-2026-07-05.md` | `013d91b8d7f5150f7a176a7bb595dd9a3a553f520967e91381288fdd2808adac` | C1 Gate D report |
| Gate D/E PRD | `docs/PRD-APEX-HETEROGENEOUS-CELL-END-TO-END-2026-07-03.md` | `b526fdccb6520367699a8a05261ac0d4309daa3a0b766e3093baafdfd21acb68` | Gate E extension present |
| C1 D2A acceptance | `runtime/reports/apex_heterogeneous_cell/gate_d_acceptance_clean_c1_fullheldout_20260705T134658Z/gate_d_acceptance_report.json` | `4e06fcc06284315fdc61528bbd4a9583740fd826cef5ca4cf4ccfd1baea09d5b` | polar pass |
| C1 D2A custody | `runtime/reports/apex_heterogeneous_cell/gate_d2a_custody_extension_20260705T143154Z/gate_d2a_custody_manifest.json` | `874b7249b2a19e4be559d96e8442534e09468b97c00e4ef076964807b8bee7fb` | blocked on Comet |
| C2 full authority path | `runtime/reports/apex_heterogeneous_cell/gate_d_full_c2_20260705T1432Z/gate_d_full_authority_path_result.json` | `1fac3c340949cb73139723ec9c0c56903ec18f92feb408cb377c99691cc32b72` | blocked_fail_closed |
| C2 D2A acceptance | `runtime/reports/apex_heterogeneous_cell/gate_d_full_c2_20260705T1432Z/gate_d_acceptance_report.json` | `99c9dd820ca4348b5f446f24d2a84da6a74eb454191beeca5b1c34040ab41608` | polar pass |
| C2 D2A custody | `runtime/reports/apex_heterogeneous_cell/gate_d_full_c2_20260705T1432Z/gate_d2a_custody_manifest.json` | `9dedfae15fa297ab38688a58368ea399944f100f73f3beff51147e5ce1764abd` | blocked on Comet |
| C2/C3/C4 stage manifest | `runtime/reports/apex_heterogeneous_cell/gate_d_full_c2_20260705T1432Z/gate_d_corpus_stage_manifest.json` | `b380a2e8aa0483f930558fe2413381c228ad25870f90754ada11c5e1e6ef8a8e` | pass |
| C2 Gate E split identity | `runtime/reports/apex_heterogeneous_cell/gate_d_full_c2_20260705T1432Z/gate_e_heldout_split_identity.json` | `4e5eb8ca097640daee5477c0f321719af8e853d2319209e04abb1d0506280bf5` | pass |
| C3 Gate E split identity | `runtime/reports/apex_heterogeneous_cell/gate_d_full_c2_20260705T1432Z/gate_e_heldout_split_identity_C3.json` | `278e0751a955c7fe5ade35faed2de2f0dfb8d2f68094b1a7bf06d025254a4b77` | pass |
| C4 Gate E split identity | `runtime/reports/apex_heterogeneous_cell/gate_d_full_c2_20260705T1432Z/gate_e_heldout_split_identity_C4.json` | `6f6402d8474f71f0e7b7e24e823531ec4d74603abb306ab09632f780de885d07` | pass |
| C2 host decoder probe | `runtime/reports/apex_heterogeneous_cell/gate_d_full_c2_20260705T1432Z/gate_e_c2_decoder_probe_report.json` | `1fe267d9bd45ec612f6a0c904fa407195a50eedc99afdfacf048304f3e277522` | blocked on source model path |
| C2 phone decoder probe | `runtime/reports/apex_heterogeneous_cell/gate_d_full_c2_20260705T1432Z/gate_e_c2_phone_decoder_probe_report.json` | `f7b9bf4118a5e18ff430c66b787cc8dfe89f936fc2da97956e2d8a21e968aa2b` | blocked |
| C2 Gate E report | `runtime/reports/apex_heterogeneous_cell/gate_d_full_c2_20260705T1432Z/gate_e_token_nll_perplexity_report.json` | `35a5191a162d92049b2b4d731c06e469da0cadcda6d0f51824bb6f6cebb7b2ad` | blocked_fail_closed |
| C2 D3 comparator report | `runtime/reports/apex_heterogeneous_cell/gate_d_full_c2_20260705T1432Z/gate_d3_comparator_suite_report.json` | `7c45da7a2b670e0e3b4163fd41f69f2b1991a7a3ac8708265dc5cbeb90b78247` | blocked_fail_closed |
| C2 D2A Comet result | `runtime/reports/apex_heterogeneous_cell/gate_d_full_c2_20260705T1432Z/gate_d2a_comet_logging_result.json` | `78ef5571d8bf9cce5a4715a142487504d9707061733fe787e8ccbb3e1bc50acd` | blocked on missing API key |
| C2 Gate E Comet result | `runtime/reports/apex_heterogeneous_cell/gate_d_full_c2_20260705T1432Z/gate_e_comet_logging_result.json` | `78ef5571d8bf9cce5a4715a142487504d9707061733fe787e8ccbb3e1bc50acd` | blocked on missing API key |
| C2 D3 Comet result | `runtime/reports/apex_heterogeneous_cell/gate_d_full_c2_20260705T1432Z/gate_d3_comet_logging_result.json` | `78ef5571d8bf9cce5a4715a142487504d9707061733fe787e8ccbb3e1bc50acd` | blocked on missing API key |

## 6. Gate D Baseline From Prior Report

The prior C1 result remains the baseline mechanism evidence:

```yaml
c1_gate_d2a:
  status: gate_d2_phone_local_heldout_learning_evidence_pass
  before_loss: 27393.12386942226
  after_loss: 27090.22732081249
  loss_delta: -302.8965486097695
  overlap_count: 0
  heldout_packet_count: 2500
  scanned_packet_count: 2500
  evaluated_answer_bearing_steps: 2344
  skipped_empty_answer_packets: 156
  successful_qnn_steps: 2344
  theta_post_sha256: 65b79f6c3127e15b26d756c352c5faa84afa81e99ff8a921f30e02b0a1b24c45
```

Scientific meaning:

- phone-local QNN/HTP forward evidence existed;
- native Adreno/Vulkan theta-update continuation existed;
- theta was chained across 16 steps;
- the accepted theta improved the declared polar heldout objective;
- the heldout scan covered the full 2500 packet set;
- train/heldout overlap was zero.

Scientific limit:

- no token-level language-model likelihood was computed;
- no decoder/logit probability surface consumed the accepted theta;
- no Gemma model-quality or perplexity claim followed from the result;
- no promoted Comet custody existed.

## 7. C2 Continuation Under Identical D2A Discipline

C2 was run through the bounded one-command authority path:

```text
scripts/host/run_apex_gate_d_full_authority_path.py
```

The full path status is:

```yaml
status: blocked_fail_closed
first_missing_green_field: mandatory_comet_logging_failed
corpus_stage: C2
```

The one-command path executed:

| Step | Return code | Elapsed seconds | Interpretation |
| --- | ---: | ---: | --- |
| D1 | 0 | 53.26975112501532 | phone-local continuation completed |
| D2 | 0 | 5901.22765799996 | full heldout polar evaluation completed |
| D0 | 0 | 0.6133470000349917 | binding preflight completed |
| D2A | 0 | 0.501862374949269 | aggregate polar acceptance report completed |
| Comet | 2 | 0.45479716698173434 | mandatory logging failed closed |

Return-code files written after the full path and follow-on Gate E/D3 probes:

| RC file | Value | Meaning |
| --- | ---: | --- |
| `stage_manifest_rc.txt` | 0 | C2/C3/C4 stage manifest passed |
| `custody_rc.txt` | 2 | custody manifest blocked on mandatory Comet |
| `gate_e_rc.txt` | 2 | Gate E blocked fail-closed |
| `gate_e_comet_rc.txt` | 2 | Gate E Comet logging blocked |
| `gate_d3_rc.txt` | 2 | D3 blocked fail-closed |
| `gate_d3_comet_rc.txt` | 2 | D3 Comet logging blocked |
| `gate_e_c2_phone_decoder_probe_rc.txt` | 13 | native decoder probe failed at adapter payload contract |

The C2 D2A/D2 heldout evidence chain says:

```yaml
c2_gate_d2a:
  status: gate_d2_phone_local_heldout_learning_evidence_pass
  metric_family: phone_local_qnn_polar_adapter_mse_v1
  before_loss: 27393.12386942226
  after_loss: 27157.342885556212
  loss_delta: -235.78098386604688
  overlap_count: 0
  heldout_packet_count: 2500
  scanned_packet_count: 2500
  evaluated_answer_bearing_steps: 2344
  skipped_empty_answer_packets: 156
  successful_qnn_steps: 2344
  theta_post_sha256: f3c1b5476e1f81e4afdeea86a8c4a9c6c4b56570101d5db4e75dcf56fb56bdab
```

This is an important generalization signal relative to C1. The C2 run did not
merely replay the same theta SHA; it produced a new post-update theta identity
and again reduced the fixed polar heldout objective. However, because Comet is
mandatory for promotion, C2 is not a promoted result.

## 8. Corpus Stage Readiness

The stage manifest records C2/C3/C4 inputs and the fixed heldout target:

```yaml
fixed_heldout:
  phone_path: /data/data/com.termux/files/home/polymath_apex_gate_d/runs/gate_d2_fixed_heldout_materialization_20260705T114922Z/raw_fixed_c1_c4_heldout.pjp1
  sha256: 8516b7e4f5b342bd5b2edd3d782a35137fef97327e669097363c0eab78e4a95a
  packet_count: 2500
```

Stage readiness:

| Stage | Training packets | Training PJP1 sha256 | Status |
| --- | ---: | --- | --- |
| C2 | 3198 | `8faba670c559474c4fd20840f614d6212a047cfd4b8f894da6b74b831df3ea42` | ready and executed through C2 D2A |
| C3 | 247500 | `c22fd5978829b85e93b419726dfb7c9228a89003c5faa1777b785e66d2997416` | ready, not executed through D2A |
| C4 | 15341 | `f80abf3b0090cb05efa66429a363aee29b7b259ab2fb5a475649305181d383b7` | ready, not executed through D2A |

The manifest explicitly does not claim C2/C3/C4 completion. C3 and C4 have
ready sources, not continuation evidence.

## 9. Gate E Split Identity

Gate E requires a text heldout split identity before any NLL/perplexity
measurement. For C2, the split identity report passed:

```yaml
c2_gate_e_split_identity:
  status: pass
  first_missing_green_field: none
  corpus_stage: C2
  canonical_uri: hf://datasets/Zer0pa/polymat-gemmalit-c1-c4-commercial-corpus@504dd91b0448f93b90c9452131868d05a13ccbe0/packages/C2/qa_bridge/phase_C2_test.qa.jsonl
  heldout_jsonl_sha256: 2ff348e4b7776eb348b774cb8ea2fd04f7bb57ab8303ed9e4b5c6c1564767fae
  heldout_record_count: 27
  train_record_count: 3042
  overlap_count: 0
  model_id: google/gemma-4-E4B
  hf_revision: 7aa32e6889efd6300124851b164f8b364314c3d8
  source_model_safetensors_sha256: 43fb96cec3045b72852c787540300dc5b258634b7a025f7c80355ac0788b9651
  model_identity_sha256: b8cfd8264f3e61a1b340869d7cbffe11e771ba33cb2ff868c9941896413e70d4
  tokenizer_identity_sha256: 99bc7dff78966a39b19dc8efaffebe95f34eeab6361018c0a7621bd12ac4995f
```

C3 and C4 split identity reports also passed:

```yaml
c3_gate_e_split_identity:
  heldout_record_count: 548
  train_record_count: 53379
  heldout_split_sha256: 4a4251f4d0f2f177a02d5373fa7bdf49fbd9f00a1c794d0f6691a48fc5248ac9
  overlap_count: 0

c4_gate_e_split_identity:
  heldout_record_count: 112
  train_record_count: 11883
  heldout_split_sha256: a6cc3bb51e45b5645abbd81d698335e163f575035802c90b2c8d684e4247c022
  overlap_count: 0
```

Split identity is necessary but not sufficient. It proves fixed text heldout
identity, train/heldout disjointness, and decoder/tokenizer identity. It does
not compute token probabilities.

## 10. Gate E Decoder Probe

The C2 accepted theta identity was tested twice against the C5/full-decoder
surface. The first host-side probe established that the checkpoint SHA and
heldout split identity were being carried forward, but it failed before the
phone-local scorer because the decoder manifest pointed at a phone-local model
path that was not present on the host:

```yaml
host_decoder_probe:
  report: runtime/reports/apex_heterogeneous_cell/gate_d_full_c2_20260705T1432Z/gate_e_c2_decoder_probe_report.json
  status: blocked
  first_missing_green_field: source_model_safetensors_path_not_found
  native_returncode: 13
```

After checking the phone model/source surface, the phone-local probe advanced
past that file-location issue and exposed the real interface mismatch. The
phone probe report is:

```text
runtime/reports/apex_heterogeneous_cell/gate_d_full_c2_20260705T1432Z/gate_e_c2_phone_decoder_probe_report.json
```

Result:

```yaml
status: blocked
first_missing_green_field: c5_full_decoder_rank16_adapter_payload_size_mismatch
native_returncode: 13
checkpoint_payload:
  expected_sha256: f3c1b5476e1f81e4afdeea86a8c4a9c6c4b56570101d5db4e75dcf56fb56bdab
  actual_sha256: f3c1b5476e1f81e4afdeea86a8c4a9c6c4b56570101d5db4e75dcf56fb56bdab
  size_bytes: 1024
heldout_qa:
  sha256: 2ff348e4b7776eb348b774cb8ea2fd04f7bb57ab8303ed9e4b5c6c1564767fae
  record_count: 27
prediction_jsonl_written: false
prediction_record_count: 0
raw_payload_bytes_in_report: false
checkpoint_payload_copied_to_repo: false
```

This is the central engineering blocker. The polar D2A theta state is a
1024-byte payload. The C5 full-decoder scorer currently expects a rank-16
adapter payload contract. Therefore the accepted polar theta cannot yet be
consumed by the decoder/logit evaluator.

This is not a missing-report problem and not a dashboard problem. It is an
interface mismatch between the trained state produced by Gate D and the model
state consumed by Gate E.

The probe also recorded that `lm_head_or_unembedding_present` was false in the
runtime component discovery. That may become the next concrete blocker after
the adapter payload contract is fixed, but it is not the current
first-missing-green-field. The current first missing field is the adapter
payload size/shape mismatch.

## 11. Gate E Token NLL/Perplexity Report

The Gate E report failed closed:

```yaml
status: blocked_fail_closed
first_missing_green_field: gate_e_decoder_probe_blocked:c5_full_decoder_rank16_adapter_payload_size_mismatch
blockers:
  - gate_e_decoder_probe_blocked:c5_full_decoder_rank16_adapter_payload_size_mismatch
  - gate_e_token_nll_records_absent
  - mandatory_comet_logging_not_logged:blocked
```

The report carries the correct identities forward:

```yaml
theta_post_sha256: f3c1b5476e1f81e4afdeea86a8c4a9c6c4b56570101d5db4e75dcf56fb56bdab
heldout_split_sha256: 2ff348e4b7776eb348b774cb8ea2fd04f7bb57ab8303ed9e4b5c6c1564767fae
model_identity_sha256: b8cfd8264f3e61a1b340869d7cbffe11e771ba33cb2ff868c9941896413e70d4
tokenizer_identity_sha256: 99bc7dff78966a39b19dc8efaffebe95f34eeab6361018c0a7621bd12ac4995f
overlap_count: 0
```

But the actual language-model metrics are absent:

```yaml
before_nll_per_token: null
after_nll_per_token: null
nll_delta_per_token: null
before_perplexity: null
after_perplexity: null
token_count: 0
record_count: 0
decoder_logit_sha256_set_sha256: null
target_token_sha256_set_sha256: null
```

Therefore there is no Gate E pass and no perplexity delta.

## 12. Surrogate Validity

The C2 polar delta is negative:

```yaml
polar_loss_delta: -235.78098386604688
```

The Gate E NLL delta is absent:

```yaml
nll_delta_per_token: null
```

The surrogate-validity verdict is:

```yaml
verdict: insufficient_gate_e_data
direction_agreement: null
```

This is the correct scientific result. A polar improvement cannot be
retroactively treated as LM evidence unless token-level NLL/perplexity is
measured and the sign relation is checked. If future Gate E data show polar
improvement with NLL regression, the polar metric becomes a surrogate
falsifier for LM quality.

## 13. D3 Comparator Suite

D3 is correctly blocked behind Gate E:

```yaml
status: blocked_fail_closed
first_missing_green_field: gate_d3_gate_e_not_passed
blockers:
  - gate_d3_gate_e_not_passed
  - gate_d3_gate_e_nll_delta_missing
  - gate_d3_comparator_missing:no_update_theta
  - gate_d3_comparator_missing:random_theta
  - gate_d3_comparator_missing:conventional_adapter
  - gate_d3_comparator_missing:runpod_reference
  - gate_d3_comparator_missing:alternate_layer_schedule
  - mandatory_comet_logging_not_logged:blocked
```

The required arms are:

- no-update theta;
- random theta;
- conventional adapter baseline;
- RunPod reference update on the same packet subset;
- alternate layer schedule.

These arms should not be run for promotion until Gate E produces a real
language-model metric. D3 comparators must compare token-level NLL/perplexity,
not only polar heldout loss.

## 14. Comet Logging and Custody

Comet is mandatory for promoted D2A, Gate E, and D3 evidence. The current
Comet result is:

```yaml
status: blocked
blocker_reason: missing_COMET_API_KEY_environment
blocker_evidence: test -n "$COMET_API_KEY" returned false
workspace: zer0pa-imc
project_name: mobile-polymath-ai-training
project_url: https://www.comet.com/zer0pa-imc/mobile-polymath-ai-training
dry_run: false
```

This is an access/configuration blocker for promotion. It does not invalidate
the local metadata reports, but it prevents any promoted custody claim.

The custody rule is:

```yaml
promotion_requires:
  comet_status: logged
  raw_assets_logged: false
  metadata_assets_only: true
  no_secrets_in_report: true
```

Dry-run logging is useful only for shape validation. It is not a promoted
result.

## 15. Engineering Work Added for This Gate

The following components were added or hardened to enforce the D-to-E pipeline.

Core validators:

```text
polymath_ai/polar/apex_gate_e.py
polymath_ai/polar/apex_gate_d3.py
polymath_ai/polar/apex_gate_d_custody.py
polymath_ai/polar/apex_gate_d_stages.py
```

Host runners and logging surfaces:

```text
scripts/host/run_apex_gate_d_full_authority_path.py
scripts/host/run_apex_gate_d_custody_manifest.py
scripts/host/run_apex_gate_d_stage_manifest.py
scripts/host/run_apex_gate_e_heldout_split_identity.py
scripts/host/run_apex_gate_e_perplexity_evaluation.py
scripts/host/run_apex_gate_d3_comparator_suite.py
scripts/host/log_apex_metadata_report_to_comet.py
scripts/host/log_apex_gate_d_acceptance_to_comet.py
```

Tests:

```text
tests/test_apex_gate_d.py
tests/test_apex_gate_e.py
tests/test_comet_logging.py
```

Validation performed:

```yaml
pytest:
  command: python3 -m pytest -q tests/test_apex_gate_d.py tests/test_comet_logging.py tests/test_apex_gate_e.py
  result: 21 passed

py_compile:
  modules:
    - polymath_ai/polar/apex_gate_e.py
    - polymath_ai/polar/apex_gate_d3.py
    - polymath_ai/polar/apex_gate_d_custody.py
    - polymath_ai/polar/apex_gate_d_stages.py
    - scripts/host/run_apex_gate_d_full_authority_path.py
    - scripts/host/run_apex_gate_e_heldout_split_identity.py
    - scripts/host/run_apex_gate_e_perplexity_evaluation.py
    - scripts/host/run_apex_gate_d3_comparator_suite.py
    - scripts/host/log_apex_metadata_report_to_comet.py
    - scripts/host/log_apex_gate_d_acceptance_to_comet.py
  result: pass
```

## 16. Scientific Interpretation

What is now supported:

- C1 produced accepted phone-local polar heldout learning evidence.
- C2 repeated the polar mechanism under the same D2A discipline.
- C2 reduced the same fixed heldout polar objective from `27393.12386942226`
  to `27157.342885556212`.
- The C2 result had zero train/heldout overlap for the fixed polar heldout
  evaluation.
- Gate E split identity exists for C2 and binds text heldout, tokenizer, model,
  and revision identity.
- The project now knows the precise interface gap between D2A theta output and
  Gate E decoder scoring.

What is not supported:

- no full Gemma model-quality claim;
- no token-level perplexity improvement;
- no token-level NLL improvement;
- no validated correlation between polar loss delta and language-model quality;
- no promoted C2 custody due missing Comet logging;
- no C3 or C4 continuation completion;
- no D3 comparator conclusion;
- no releaseable adapter/model artifact claim.

The science state is therefore:

```text
phone-local polar continuation mechanism: supported for C1 and C2
language-model improvement: unmeasured
apex gate: blocked at decoder adapter interface
```

## 17. Primary Blocker: Polar Theta to Decoder Adapter Interface

The critical interface question is:

```text
How does the 1024-byte D2A polar theta state become a state that the
Gemma 4 E4B decoder/logit evaluator can apply to token prediction?
```

There are two legitimate repair paths:

1. Materialize a rank-16 adapter payload from the polar theta state plus a
   fixed, predeclared basis/magnitude policy.
2. Modify the C5/full-decoder scorer to consume the polar theta representation
   directly at the declared adapter site.

Either repair must preserve:

- accepted theta SHA identity;
- deterministic adapter construction;
- explicit shape contract;
- before/after scoring of the same fixed heldout split;
- metadata-only raw boundary;
- no fabricated decoder logits;
- no post-hoc basis selection from heldout outcomes.

The repair must output a decoder-probe pass report before Gate E can proceed
to token-NLL aggregation.

## 18. Required Next Actions

The next work should proceed in this order:

1. Fix the Gate E adapter contract.
   Define whether the decoder scorer consumes a materialized rank-16 adapter or
   native polar theta. Write the shape contract and fail-closed validator before
   rerunning phone inference.

2. Re-run the C2 phone decoder probe.
   Required pass fields: accepted theta SHA match, C2 heldout split SHA match,
   model/tokenizer identity match, prediction JSONL written outside git, record
   count matching 27, and no raw payload bytes in the report.

3. Build token-level NLL records.
   Required rows: record identity, target-token identity, before/after decoder
   logit identities, masked-token count, per-record NLL, and split SHA.

4. Rebuild the Gate E report.
   Required pass fields: finite before/after NLL per token, finite before/after
   perplexity, `nll_delta_per_token <= 0.0`, token count greater than zero,
   overlap count zero, no synthetic/fabricated metric, Comet logged.

5. Decide surrogate validity.
   Compare C2 polar delta against C2 NLL delta. If the signs disagree, the
   polar surrogate is not valid for LM-quality claims.

6. Only then run D3 comparators.
   Required arms: no-update theta, random theta, conventional adapter, RunPod
   reference, alternate layer schedule.

7. Run C3/C4 continuation only under the same discipline.
   Stage readiness exists, but promotion requires independent D2A pass, Gate E
   evidence where relevant, and Comet logging.

## 19. Stop Conditions

The team must stop and write a falsification report if any of these occur:

- Gate E NLL regresses while polar loss improves;
- decoder logits are synthetic, fabricated, or not bound to the accepted theta;
- train/heldout overlap becomes nonzero;
- C2/C3/C4 promotion is attempted from prefix-heldout evidence;
- D3 is run as a promotional comparator before Gate E produces a real metric;
- Comet logging is bypassed for promoted evidence;
- raw model weights, raw tensors, raw theta binaries, raw payloads, raw rows,
  stdout/stderr dumps, or secrets are embedded in repo reports.

## 20. Current Owner and Handoff

Current owner:

```text
Gate E adapter-interface repair owner
```

Immediate objective:

```text
Make the accepted C2 polar theta state consumable by the Gemma 4 E4B
decoder/logit evaluator without changing the accepted theta identity or
lowering the Gate E metric.
```

Next evidence required before advancement:

```yaml
decoder_probe:
  status: pass
  prediction_jsonl_written: true
  prediction_record_count: 27
  theta_post_sha256: f3c1b5476e1f81e4afdeea86a8c4a9c6c4b56570101d5db4e75dcf56fb56bdab
  heldout_split_sha256: 2ff348e4b7776eb348b774cb8ea2fd04f7bb57ab8303ed9e4b5c6c1564767fae
  model_identity_sha256: b8cfd8264f3e61a1b340869d7cbffe11e771ba33cb2ff868c9941896413e70d4
  tokenizer_identity_sha256: 99bc7dff78966a39b19dc8efaffebe95f34eeab6361018c0a7621bd12ac4995f
  raw_payload_bytes_in_report: false
```

Nonclaims preserved:

```yaml
no_trained_gemma_on_phone_claim: true
no_language_model_perplexity_claim: true
no_surrogate_validity_claim: true
no_d3_comparator_claim: true
no_c3_c4_completion_claim: true
no_comet_promoted_custody_claim: true
```
