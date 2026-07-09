# Handover: Phase34B Phone-Native, Mac-Light Operations

Created: 2026-07-09

Workspace: `/Users/Zer0pa/Polymat AI/Polymath-AI`

Purpose: operational handover for the next agent. This is not a science report
and not a new authorization to execute. It records the working system that was
built during Phase34B: phone-native storage/compute where practical,
Mac-light metadata custody, GitHub commit discipline, ADB/Termux access, and
Comet metadata logging.

The next agent should use this as a practical runbook. The point is not to
create rituals. The point is to avoid losing the phone-native operating model,
avoid Mac disk-pressure regressions, and keep Gate E authority sovereign.

## 1. Governing State

```yaml
gate_e_status: falsified
promotion_allowed: false
authority_metric: phone_native_decoder_token_nll_per_token
sign_convention: after_minus_before
pass_requires: negative_nll_delta_on_gate_e_authority_report

authority_report:
  path: runtime/reports/apex_heterogeneous_cell/gate_e_phone_native_jl_c2_full27_20260708_timeout12h/gate_e_token_nll_perplexity_report.json
  sha256: 70739a1c78b5d1cea5a98d1826f8a1b4c658929c7b534612e346ee0309e432f0
  before_nll_per_token: 14.538868526231177
  after_nll_per_token: 14.555113501137114
  nll_delta_per_token: +0.01624497490593768
  record_count: 27
  token_count: 27
```

Current Phase34B disposition:

```yaml
phase34b_run_id: 20260709T091440Z
status: blocked_fail_closed
first_missing_green_field: h1_asvd_effective_rank_below_min
final_disposition_report:
  path: runtime/reports/apex_heterogeneous_cell/phase34b_gradient_source_20260709T091440Z/phase34b_task_aligned_projection_final_disposition_report.json
  sha256: a2ec3d0a0d5ff25e1d151f1ed274938eec77963ffed83c6707c603599a954ab6

h1_richer_asvd:
  calibration_record_count: 128
  calibration_row_count: 990
  centered_rank_estimate: 344
  effective_rank: 35.14290814917967
  blocker: activation_effective_rank_below_min
  projection_matrix_built: false

h2_gradient_svd_galore:
  status: blocked_fail_closed
  first_missing_green_field: gradient_matrix_file_absent
  projection_matrix_built: false

downstream_gates_run_after_phase34b:
  h5_controls: false
  d1_micro_correlation: false
  d2_small_correlation: false
  d3_full_correlation: false
  gate_d2a: false
  gate_e_full27: false
```

Do not convert any of this into a pass narrative. The correct state is
fail-closed.

## 2. Required Read-In For Next Agent

Read these in order before taking action:

```text
1. /Users/Zer0pa/Polymat AI/Polymath-AI/AGENTS.md
2. /Users/Zer0pa/Polymat AI/Polymath-AI/docs/APEX-GATE-E-SCIENCE-REPORT-SEQUENCE-2026-07-06/README.md
3. /Users/Zer0pa/Polymat AI/Polymath-AI/docs/APEX-GATE-E-SCIENCE-REPORT-SEQUENCE-2026-07-06/06_APEX-GATE-E-TASK-ALIGNED-PROJECTION-CANDIDATE-EXHAUSTION-ENGINEERING-SCIENCE-REPORT-2026-07-09.md
4. /Users/Zer0pa/Polymat AI/Polymath-AI/docs/APEX-GATE-E-SCIENCE-REPORT-SEQUENCE-2026-07-06/07_APEX-GATE-E-PHASE34B-RICHER-ASVD-GRADIENT-SOURCE-CONTINUATION-FAIL-CLOSED-ENGINEERING-SCIENCE-REPORT-2026-07-09.md
5. /Users/Zer0pa/Polymat AI/Polymath-AI/docs/APEX-GATE-E-SCIENCE-REPORT-SEQUENCE-2026-07-06/HANDOVER_PHASE34B_PHONE_NATIVE_MAC_LIGHT_OPERATIONS_2026-07-09.md
6. /Users/Zer0pa/Polymat AI/Polymath-AI/runtime/reports/apex_heterogeneous_cell/phase34b_gradient_source_20260709T091440Z/phase34b_task_aligned_projection_final_disposition_report.json
7. /Users/Zer0pa/Polymat AI/Task-Aligned Projection Design for Phone-Native Gemma-4-E4B Polar Training.md
8. /Users/Zer0pa/Polymat AI/Polymath-AI/docs/PRD-PHASE34-TASK-ALIGNED-PROJECTION-PHONE-NATIVE-GEMMA4-E4B-POLAR-TRAINING-2026-07-08.md
```

Read-in report-for-duty should be short:

```text
Gate E is falsified. Phase34B is blocked fail-closed. H1 richer ASVD failed
effective-rank Stage 0 despite centered-rank recovery. H2 still lacks the
authentic gradient surface. Phone-native/Mac-light custody is the operating
model. Standing by for the next brief.
```

## 3. Phone-Native / Mac-Light Operating Model

The phone is the primary platform for heavy storage and practical compute.
The Mac is the control plane and metadata/report ledger.

Use this split:

| Material | Correct location |
| --- | --- |
| Raw activation captures | Phone/Termux only |
| Raw token rows or prediction JSONLs | Phone/Termux or already-offloaded phone storage only |
| Theta binaries | Phone/Termux only |
| Corpus state and corpus packages | Phone/Termux only |
| QNN build outputs and model payloads | Phone/Termux only unless a small source patch is needed |
| Metadata reports, hashes, small JSON summaries | Mac repo is allowed |
| Science reports and handovers | Mac repo docs are allowed |
| Comet logging results | Small JSON in Mac repo is allowed |

Large offload destination from the disk incident:

```text
/data/data/com.termux/files/home/polymath_mac_offload/20260709T_disk_emergency/Polymat_AI/
```

Active Phase34B phone custody root:

```text
/data/data/com.termux/files/home/polymath_phase34b_20260709T091440Z/asvd_activation_capture
```

Do not recreate these Mac-local heavy trees:

```text
/Users/Zer0pa/Polymat AI/runtime/tmp
/Users/Zer0pa/Polymat AI/corpus_state
/Users/Zer0pa/Polymat AI/corpus_packages
```

If a workflow tries to write large files under `/Users/Zer0pa/Polymat AI`, stop
and reroute it to Termux storage. A small metadata report under
`/Users/Zer0pa/Polymat AI/Polymath-AI/runtime/reports/...` is acceptable.

## 4. ADB, SSH, And Termux Access

Known phone:

```yaml
adb_serial: FY25013101C8
model: NX789J
platform: RedMagic / Termux
ssh_user: u0_a536
termux_home: /data/data/com.termux/files/home
ssh_port_on_phone: 8022
adb_forward_on_mac: tcp:18022 -> tcp:8022
```

Basic check:

```bash
adb devices
adb shell getprop ro.product.model
adb shell getprop ro.build.version.release
```

Forward SSH:

```bash
adb forward --remove tcp:18022 || true
adb forward tcp:18022 tcp:8022
```

SSH from this Codex/Mac environment has worked with:

```bash
ssh -i /Users/prinivenpillay/.ssh/polymath_host \
  -o IdentitiesOnly=yes \
  -p 18022 \
  -o StrictHostKeyChecking=no \
  -o UserKnownHostsFile=/dev/null \
  -o ConnectTimeout=20 \
  u0_a536@127.0.0.1 pwd
```

If banner exchange times out:

```bash
adb forward --remove tcp:18022 || true
adb forward tcp:18022 tcp:8022
adb shell am start -n com.termux/.app.TermuxActivity
adb shell input keyevent WAKEUP
```

Then retry SSH. Do not treat a banner timeout as proof the phone run failed;
check ADB and phone-side processes separately.

Phone process checks that are safe:

```bash
adb shell pgrep -af gemma4_layer_runner
adb shell pgrep -af phase34b
adb shell pgrep -af tmux
```

At Phase34B close, these checks returned no active Phase34B jobs.

## 5. Comet Logging Discipline

Comet is required for live observability, but only metadata-safe assets should
be logged.

Known Comet target:

```yaml
workspace: zer0pa-imc
project_name: mobile-polymath-ai-training
```

Important Comet URLs:

```yaml
h1_rank_trend: https://www.comet.com/zer0pa-imc/mobile-polymath-ai-training/997fed03f8f4485f97935fd3b063c63a
h2_blocker: https://www.comet.com/zer0pa-imc/mobile-polymath-ai-training/82778d954bea4b3ab1687e5ee757d2e3
phase34b_final_disposition: https://www.comet.com/zer0pa-imc/mobile-polymath-ai-training/4908887e34cd4abc9ad5d0754bacd4bf
```

Do not print, cat, copy, or commit API keys. On phone, the environment has been
loaded from:

```text
$HOME/.termux_agent_env
```

Use it without exposing it:

```bash
ssh -i /Users/prinivenpillay/.ssh/polymath_host \
  -o IdentitiesOnly=yes \
  -p 18022 \
  -o StrictHostKeyChecking=no \
  -o UserKnownHostsFile=/dev/null \
  u0_a536@127.0.0.1 \
  'bash -lc '\''. "$HOME/.termux_agent_env" 2>/dev/null || true; \
  export COMET_WORKSPACE=zer0pa-imc; \
  export COMET_PROJECT_NAME=mobile-polymath-ai-training; \
  cd "$HOME/Polymath-AI"; \
  python3 scripts/host/log_apex_metadata_report_to_comet.py \
    --gate PHASE34 \
    --report /phone/path/to/metadata_report.json \
    --run-name descriptive-run-name \
    --output /phone/path/to/comet_result.json'\'''
```

Pull back only the small Comet result JSON:

```bash
scp -i /Users/prinivenpillay/.ssh/polymath_host \
  -o IdentitiesOnly=yes \
  -P 18022 \
  -o StrictHostKeyChecking=no \
  -o UserKnownHostsFile=/dev/null \
  u0_a536@127.0.0.1:/phone/path/to/comet_result.json \
  runtime/reports/.../comet_result.json
```

Never log raw tensors, raw token rows, raw predictions, model weights, theta
binaries, payload dumps, or secrets to Comet.

## 6. GitHub And Commit Discipline

Remote:

```text
origin https://github.com/Zer0pa/Polymath-AI.git
branch gemma4-megakernel-native-training
```

Latest known pushed commits at handover:

```text
f7ca112 docs: add apex gate e science report sequence
03cebad phase34b: record final projection disposition
271c125 phase34b: record phone asvd custody chunk15
```

Working tree has broad inherited dirty/untracked drift outside the scoped
Phase34B work. Do not clean it globally. Do not use `git reset --hard` or
`git checkout --` to erase user/inherited work.

Use scoped status:

```bash
git status --short docs/APEX-GATE-E-SCIENCE-REPORT-SEQUENCE-2026-07-06
git status --short runtime/reports/apex_heterogeneous_cell/phase34b_gradient_source_20260709T091440Z
git status --short scripts/host/run_phase34b_phone_asvd_custody_snapshot.py
```

Use scoped adds:

```bash
git add path/to/specific_report.json path/to/specific_doc.md
git commit -m "concise: scoped result"
git push origin gemma4-megakernel-native-training
```

If generated drift appears from your own verification, remove only what you
created, for example `scripts/host/__pycache__` or a small accidental
`runtime/tmp` scratch tree. Do not delete unrelated user drift.

## 7. Built Foundations To Preserve

Phone custody runner:

```text
scripts/host/run_phase34b_phone_asvd_custody_snapshot.py
```

Role:

```text
Computes Phase34B ASVD metadata and rank trend on phone/Termux storage, then
pulls only small JSON reports back to the Mac.
```

Mac raw pull guard:

```text
scripts/host/pull_phase34b_asvd_capture_metadata.py
```

Role:

```text
Blocks raw activation capture pulling by default after the disk offload. It
requires explicit break-glass `--allow-mac-raw-captures` for raw pulls.
```

Deprecated old chain follower:

```text
scripts/host/follow_phase34b_asvd_capture_chain.py
```

Role:

```text
Fails closed and directs users to the phone custody snapshot runner instead of
pulling raw activation captures to Mac.
```

Mac concat guard:

```text
scripts/host/build_phase34b_asvd_activation_concat_report.py
```

Role:

```text
Blocks Mac-local raw concat output under `/Users/Zer0pa/Polymat AI`.
```

These guards matter. They are not bureaucracy. They prevent a repeat of the
disk-pressure incident and preserve the phone-native objective.

## 8. How To Work Without Process Theater

The next agent should be direct:

1. Read the required context.
2. Confirm current gate state.
3. If asked to execute, execute the predeclared next step.
4. Keep raw data on phone.
5. Log metadata to Comet.
6. Commit scoped artifacts.
7. Stop at real blockers without narrating them as wins.

Do not:

```text
- ask for permission when the user has already given a concrete execution brief
- relitigate H3/H4 under the old PRD
- rerun H3 to chase p-value
- lower Stage 0, D3, D2A, or Gate E thresholds
- convert centered-rank recovery into an ASVD pass
- use a synthetic gradient substitute as H2/GaLore
- launch D1/D2/D3/H5/D2A/Gate E when no admissible candidate exists
- write raw captures, token rows, theta binaries, or model payloads to Mac
- print secrets or raw payloads
- use the ZPP skill/plugin for this line of work unless the user explicitly reverses that instruction
```

Do:

```text
- preserve Gate E as sovereign
- treat positive NLL delta as failure
- use the phone as the practical compute/storage platform
- use the Mac as control plane and metadata ledger
- keep Comet logging live for metadata reports
- commit and push small, scoped artifacts
- keep reports honest and fail-closed
```

## 9. Real Next Technical Options

No downstream candidate exists at this handover. The next valid technical
program should be explicitly predeclared and should target one of these gaps:

### 9.1 Authentic Gradient Source

Goal:

```text
Produce a valid dL_NLL/dh_layer24 surface tied to the phone-native
decoder-token NLL authority metric.
```

Minimum design requirements:

```yaml
gradient_surface:
  must_bind_to_model_identity: true
  must_bind_to_tokenizer_identity: true
  must_bind_to_heldout_record_ids: true
  must_bind_to_layer24_hidden_contract: true
  must_include_phone_fidelity_probe: true
  must_log_metadata_to_comet: true
  must_not_claim_authority_until_phone_correlation_passes: true
```

The key review question is fidelity: does the offline or calibration gradient
predict small phone-native NLL changes on matched probes?

### 9.2 Higher-Diversity Activation Calibration

Goal:

```text
Produce an activation surface whose effective rank, not only centered rank,
passes Stage 0.
```

Minimum design requirements:

```yaml
activation_surface:
  stratify_by_context: true
  stratify_by_token_position: true
  stratify_by_record_family: true
  report_centered_rank: true
  report_effective_rank: true
  fail_closed_if_effective_rank_below_threshold: true
  keep_raw_captures_on_phone: true
```

The Phase34B result already shows that adding rows can improve centered rank
while leaving effective rank too low. Do not repeat that mistake by measuring
only centered rank.

## 10. Copy-Paste Startup Prompt For Next Agent

Use this prompt to start the next agent:

```text
You are resuming Polymath-AI Apex Gate E / Phase34B phone-native, Mac-light projection custody.

Work in:
/Users/Zer0pa/Polymat AI/Polymath-AI

Do not use the ZPP skill/plugin. Your first task is context ingestion only. Do not launch Phase34/Phase34B execution, D1/D2/D3, H5 controls, Gate D2A, Gate E full27, C3/C4/D3 promotion, gradient-source experiments, ASVD reruns, or unpredeclared experiments. Do not write large artifacts to the Mac.

Read these in order:

1. /Users/Zer0pa/Polymat AI/Polymath-AI/AGENTS.md
2. /Users/Zer0pa/Polymat AI/Polymath-AI/docs/APEX-GATE-E-SCIENCE-REPORT-SEQUENCE-2026-07-06/README.md
3. /Users/Zer0pa/Polymat AI/Polymath-AI/docs/APEX-GATE-E-SCIENCE-REPORT-SEQUENCE-2026-07-06/06_APEX-GATE-E-TASK-ALIGNED-PROJECTION-CANDIDATE-EXHAUSTION-ENGINEERING-SCIENCE-REPORT-2026-07-09.md
4. /Users/Zer0pa/Polymat AI/Polymath-AI/docs/APEX-GATE-E-SCIENCE-REPORT-SEQUENCE-2026-07-06/07_APEX-GATE-E-PHASE34B-RICHER-ASVD-GRADIENT-SOURCE-CONTINUATION-FAIL-CLOSED-ENGINEERING-SCIENCE-REPORT-2026-07-09.md
5. /Users/Zer0pa/Polymat AI/Polymath-AI/docs/APEX-GATE-E-SCIENCE-REPORT-SEQUENCE-2026-07-06/HANDOVER_PHASE34B_PHONE_NATIVE_MAC_LIGHT_OPERATIONS_2026-07-09.md
6. /Users/Zer0pa/Polymat AI/Polymath-AI/runtime/reports/apex_heterogeneous_cell/phase34b_gradient_source_20260709T091440Z/phase34b_task_aligned_projection_final_disposition_report.json
7. /Users/Zer0pa/Polymat AI/Task-Aligned Projection Design for Phone-Native Gemma-4-E4B Polar Training.md
8. /Users/Zer0pa/Polymat AI/Polymath-AI/docs/PRD-PHASE34-TASK-ALIGNED-PROJECTION-PHONE-NATIVE-GEMMA4-E4B-POLAR-TRAINING-2026-07-08.md

Current sovereign authority state:

- Gate E remains falsified.
- Authority report:
  runtime/reports/apex_heterogeneous_cell/gate_e_phone_native_jl_c2_full27_20260708_timeout12h/gate_e_token_nll_perplexity_report.json
- SHA-256:
  70739a1c78b5d1cea5a98d1826f8a1b4c658929c7b534612e346ee0309e432f0
- before_nll_per_token: 14.538868526231177
- after_nll_per_token: 14.555113501137114
- after_minus_before / nll_delta_per_token: +0.01624497490593768
- record_count: 27
- token_count: 27
- Promotion is not allowed.

Current Phase34B disposition:

- Run id: 20260709T091440Z
- Final report:
  runtime/reports/apex_heterogeneous_cell/phase34b_gradient_source_20260709T091440Z/phase34b_task_aligned_projection_final_disposition_report.json
- Final report SHA-256:
  a2ec3d0a0d5ff25e1d151f1ed274938eec77963ffed83c6707c603599a954ab6
- Status: blocked_fail_closed
- H1 richer ASVD: centered_rank_estimate 344, effective_rank 35.14290814917967, blocker activation_effective_rank_below_min, no projection matrix built.
- H2 Gradient-SVD/GaLore: blocked on gradient_matrix_file_absent; no projection matrix built.
- H3/H4 were not relitigated after report 06.
- D1/D2/D3/H5/Gate D2A/Gate E full27 were not run after Phase34B because no admissible candidate existed.

Operational guardrails:

- Phone/Termux is the heavy storage and practical compute platform.
- Mac is control plane and metadata/report ledger only.
- Do not recreate runtime/tmp, corpus_state, corpus_packages, raw activation captures, token files, theta binaries, prediction JSONLs, model payloads, QNN build outputs, or raw payload dumps under /Users/Zer0pa/Polymat AI.
- Phone offload root:
  /data/data/com.termux/files/home/polymath_mac_offload/20260709T_disk_emergency/Polymat_AI/
- Phase34B phone custody root:
  /data/data/com.termux/files/home/polymath_phase34b_20260709T091440Z/asvd_activation_capture
- Use ADB/Termux for phone operations and Comet metadata logging.
- Do not print secrets, raw rows, tensors, tokens, prediction JSONLs, theta binaries, env files, or payload dumps.
- Preserve raw-boundary discipline.
- The repo has broad inherited dirty/untracked drift; do not revert unrelated changes.
- Do not convert mixed evidence into a pass narrative.
- Do not relitigate H3/H4 under the current PRD.
- Do not rerun H3 merely to chase p-value.
- Do not lower Stage 0, D3, D2A, or Gate E thresholds.
- Further execution requires a concrete user brief for a new predeclared gradient-source or candidate program.

After reading, respond with a short duty report:

1. Confirm Gate E authority remains falsified.
2. Confirm Phase34B is blocked fail-closed.
3. Name the key blockers: H1 effective rank, H2 missing gradient surface, no admissible projection candidate.
4. Confirm phone-native/Mac-light custody is the operating model.
5. State that you are standing by for the next user brief and will not launch execution without explicit authorization.
```
