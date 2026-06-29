# Meta-Orchestration Living Context

**Project:** Polymath AI / Gemma 4 mobile training pipeline  
**Created:** 2026-06-29  
**Authority thread:** Meta-orchestrator conversation in Codex  
**Working folder:** `/Users/Zer0pa/Polymat AI`  
**Canonical repo:** `/Users/Zer0pa/Polymat AI/Polymath-AI`  
**Canonical branch at creation:** `gemma4-megakernel-native-training`  
**Phone authority runtime:** REDMAGIC / `FY25013101C8` / `NX789J`

This document is the drift lock for the current meta-orchestration system. It
must evolve when orchestration facts change. It does not replace phase PRDs,
engineering handoffs, reports, or GPD state; it tells future agents how to
interpret and sequence them.

## Operating Doctrine

- We are anti-toy, anti-demo, anti-process-theatre.
- Authority gates are sovereign. A local win, proxy pass, UI display, or
  narratable milestone is not a pass unless the authority metric passes.
- Do not convert mixed evidence into success language.
- Do not promote Phase 3 or Phase 4 from Phase 2 proxy/synthetic evidence.
- Do not treat C1/C2 corpus packages as PQA1. They are upstream QA source
  candidates until Phase 1 generates or recovers real PQA1.
- Do not expose lower-performance standard APK behavior as a product mode.
- Do not source, print, copy, commit, or summarize secrets.
- Mac is control/orchestration. Phone is authority runtime. RunPod, if used,
  is build/reference/teacher support only, not an authority runtime data path.

## GPD Relationship

This repo is a GPD project: `.gpd/STATE.md` and `.gpd/state.json` exist.

GPD is useful as a secondary state ledger and research discipline layer. It is
not the live authority for this orchestration until synchronized. At creation,
`.gpd/state.json` still says Polar Phase 2 has PRD/startup readiness but no
implementation/authority run; newer evidence shows full-C1 Phase 1 and Phase 2
diagnostic execution has passed while 100k/1M authority remains blocked.
Therefore:

- Treat this document plus the listed handoffs as live orchestration authority.
- Treat `.gpd` as initialized but stale on the Polar Phase 2 current state.
- Do not run GPD repair/sync/write commands until the Meta-Orchestrator
  authorizes Repo Custodian to reconcile state.
- After repo hygiene, GPD should be reconciled to reflect the six-thread
  orchestration, the full-C1 diagnostic pass, and the current 100k/1M
  real-corpus authority blocker.

## Six Orchestration Threads

All six threads were launched as independent local Codex project threads in
`/Users/Zer0pa/Polymat AI`. Their first task was read-only context intake and
report-for-duty only.

| Lane | Thread ID | Owns | Does Not Own |
| --- | --- | --- | --- |
| Repo Custodian | `019f138b-288e-7d91-b426-7cdee9f62e28` | Git truth, dirty-state classification, safe staging, forbidden artifact control, remote push after authorization | Engineering decisions |
| Training Material Steward | `019f138b-7bfc-7671-b9fc-22c14ab76342` | Corpus quality, provenance, scale, repair policy, source acceptance/rejection, PQA1 readiness | Running phases |
| Engineering Orchestrator | `019f138b-d229-7640-98b7-2f185d6beae0` | Phase development and debugging across Phase 1/2/3/4/future phases | UI, repo custody, final run authority |
| Pipeline Integrator | `019f138c-35b6-73e1-b26d-3db8c59cf850` | Phase contracts, artifact paths, handoff surfaces, report schemas, integration hardening | Kernel invention, UI design, gate execution |
| UI Engineer | `019f138c-8d85-7141-a813-66db51c62b3d` | Cross-phase operator UI from evidence-backed surfaces | Backend claims, execution, invented states |
| Execution Orchestrator | `019f138c-fb51-7c53-a41a-ab8eac950d9c` | Execution sequencing, authority gates, run evidence, fail routing | Developing or fixing the thing under test |

Termux/ADB/SSH is a capability available to engineering, integration, and
execution lanes when authorized. It is not a separate orchestration lane.

## Adjacent Exploratory Threads

These threads are independent user-managed workspaces adjacent to the six-lane
orchestration system. They do not create new authority lanes unless this
document and the board are explicitly updated.

| Thread | Thread ID | Purpose | Authority Boundary |
| --- | --- | --- | --- |
| Phase Three and Four Engineer | `019f13da-d897-7ba2-8ed1-b959892f5ed4` | Explore Phase 3/4 architecture, read current handoffs, and prepare planning context for the user | Planning only; no Phase 3/4 execution authorization from C1 smoke |

## Monitoring Automation

Heartbeat automation: `polymath-orchestration-monitor`.

Cadence: every 15 minutes.

Before explicit `GO` from the user, the heartbeat may inspect thread status and
prepare orchestration prompts. It must not authorize edits, commits, pushes,
secrets, API calls, ADB/Termux execution, or gate runs.

After `GO`, it should drive the sequence below and only escalate to the user for
major blockers with no obvious engineering route or for successful Phase 1 plus
Phase 2 C1 execution.

## Current Material Facts

Canonical C1 material used for the full diagnostic:

`/Users/Zer0pa/Polymat AI/corpus_packages/commercial/2026-06-27T041511Z/phase_C1_lexatlas_gemma4_v4_full_strict`

Full C1 QA bridge:

`/Users/Zer0pa/Polymat AI/corpus_packages/commercial/2026-06-27T041511Z/phase_C1_lexatlas_gemma4_v4_full_strict/qa_bridge/phase_C1_full.qa.jsonl`

Full C1 rows/SHA-256:

- Rows: `50,994`
- SHA-256: `4c8bb5a208d416bc4dae49ddf89e8e7845c459aef42b83ff15aac1a8aa76ce97`
- Source-kind mapping: `lexatlas -> dictionary`

Known C2 material:

`/Users/Zer0pa/Polymat AI/corpus_packages/commercial/20260629T100304Z/phase_C2_vocabexpansion_frontier_gpt_enriched_scale_v1`

Material interpretation:

- Full C1 v4 is valid QA source material and has now been converted through
  Phase 1 PQA1 and Phase 2 PJP1 as a diagnostic run.
- Known enriched C2 has `3,198` records.
- Conservative C1 + known C2 count: `54,192`.
- Gap to `100,000`: `45,808`.
- Gap to `1,000,000`: `945,808`.
- If the largest local valid C2 candidate at `11,324` records is authorized,
  C1 + C2 would be `62,318`, leaving `37,682` to 100k and `937,682` to 1M.
- Existing C1 variants are not additive scale unless global dedup proves they
  are not duplicate laundering.
- Current C1/C2 material does not satisfy the 100k/1M Phase 2 authority gate.

## Current Phase Facts

### Current C1 Full Diagnostic Evidence

Status: full canonical C1 v4 passed Phase 1, bridge, and Phase 2 diagnostic on
the REDMAGIC phone/Termux path.

This is engineering diagnostic evidence for the source-to-PQA1-to-PJP1 path. It
is not the 100k/1M Phase 2 authority gate and does not authorize Phase 3.

External science/engineering report:

`docs/SCIENCE-ENGINEERING-EXTERNAL-REPORT-C1-FULL-DIAGNOSTIC-2026-06-29.md`

Phase 1 source-of-record:

- Run label: `c1_phase1_v4_full_rerun_20260629T170920Z`
- Report root:
  `runtime/reports/polar_phase1_c1_pipeline/c1_phase1_v4_full_rerun_20260629T170920Z_phase1_c1_pipeline_smoke`
- App report run id: `2026-06-29T170931Z`
- Records selected: `50,994`
- Token IDs: `2,130,785`
- Records/sec: `62,228.1`
- Token IDs/sec: `2,600,200`
- Run flags: `16`
- Native warm sequences: `false`
- PQA1 outputs: `8` shards, `11,124,986` bytes total, all hash recorded.
- Forbidden payload scan: pass.

Bridge:

- Staging root:
  `/sdcard/Download/polymath/polar_phase1_c1/c1_phase1_v4_full_rerun_20260629T170920Z`
- PQA1 list:
  `/sdcard/Download/polymath/polar_phase1_c1/c1_phase1_v4_full_rerun_20260629T170920Z/c1_pqa1_list.txt`
- PQA1 list SHA-256:
  `37c9f65fb88a1cbb3a0de375dcb6f8946a04d680136ac7d243f27cbcdc6195b8`
- Copied shards: `8`
- Copied bytes: `11,124,986`
- Raw bridge payload inside git: false.

Phase 2 full-C1 diagnostic:

- Run label: `c1_phase2_v4_full_20260629T173243Z`
- Report root:
  `runtime/reports/polar_phase2_c1_smoke/c1_phase2_v4_full_20260629T173243Z`
- Wrapper status: pass.
- Native packetizer status: pass.
- PQA1 files consumed: `8`.
- Source records: `50,994`.
- Source real tokens: `2,130,785`.
- Distinct/projected token count: `65,139`.
- Packets: `50,994`.
- Slots: `6,527,232`.
- PJP1 path on phone:
  `/data/data/com.termux/files/home/polymath_phase2_outputs/c1_phase2_v4_full_20260629T173243Z/raw_c1_phase2_v4_full_20260629T173243Z.pjp1`
- PJP1 SHA-256:
  `e347676432fa7a76489f402f3c3e38ab492b6554f71930f14bc7d36ed1b3ecf5`
- PJP1 bytes: `461,805,760`.
- Records/sec: `8,694.35`.
- Real tokens/sec: `363,294`.
- Raw PJP1 inside git worktree: false.

Verified Phase 2 diagnostic identities:

- Packetizer binary SHA-256:
  `11c81138d181f09dd1a9a4715952c8a5357a91e3f1c1562f2fb9761d4d4c336a`
- Packetizer source SHA-256:
  `ba2d4dd48e2d9afeabf69b84019af0375aa739b26e982d69e8084a94a264c61f`
- Build script SHA-256:
  `3c284c858aaa0d1e7697c4b63a12330d2e24d62a2391f109f34133463a631716`
- Embedding SHA-256:
  `b57e1e756f32d02c1aaad6c5c868f975f53b0938e0a04ed546804ed9c7d4ca7b`
- Embedding manifest SHA-256:
  `0bf2dc2ec4487c079da94d8c8a37f54bb7c45ed2f9a29dbbd73edc0ababaf8bd`
- JL SHA-256:
  `1b1f9de3dd6fbdf9597240eeeb08a6b482b33f1ae4d127e730222750cdf92a79`

Historical 64-record smoke remains wiring-only evidence and should not be cited
as current state, authority progress, or Phase 3 readiness.

### Phase 1: Ingestion / Chopping

Current status: backend/native Android path is real and strong. The full
canonical C1 v4 source-to-PQA1 diagnostic passed on `50,994` real C1 source
records.

Authority lane:

- Android app package: `ai.zer0pa.polymath.lab`
- App path: `apps/android-redmagic-lab/`
- REDMAGIC high-performance APK child-exec lane is the product authority lane.
- Standard APK 53-54M token IDs/sec behavior is drift, not fallback.
- Recent high-performance evidence is roughly 60M token IDs/sec class.

Remaining work:

- Product-real UI/operator surface.
- Scale authority material beyond full C1 diagnostic.

### Phase 2: Mechanical Packetization

Current status: native engineering exists; full-C1 real-material diagnostic
passed; authority remains blocked on 100k/1M real PQA1/PJP1 plus verifier
surfaces.

Promoted engineering route from handoff:

- Phase 1 PQA1 input.
- Native C++/NEON packetizer.
- PJP1 output.
- Dense Rademacher projection incumbent: `k=256,d=2560`.
- Synthetic/proxy high-diversity path passed engineering floors.

Blocking gate:

- Real Phase 1 PQA1 at 100k and 1M.
- PJP1 readback.
- Stratified oracle.
- Collision analysis.
- Margin/Hamming geometry.
- NPU/app consumer preflight repeated on real PJP1.

Full C1 diagnostic passed as real-material pipeline hardening, but it is not
the 100k/1M Phase 2 authority gate.

### Phase 3: NPU Forward Read

Not authorized.

Required before Phase 3:

- Real 100k/1M PQA1-to-PJP1 pass.
- Real-output readback/oracle/collision/geometry pass.
- Real-label `k`/projection decision.
- NPU/app consumer preflight on real PJP1.
- Separate PRD or explicit meta-orchestrator authorization.

### Phase 4: GPU Polar Optimizer

Concept only.

Do not engineer or promote Phase 4 until Phase 3 has a real activation/output
contract.

## GO Sequence

The 2026-06-29 full-C1 diagnostic sequence has completed through Phase 1,
bridge, Phase 2, metadata custody, external reporting, and board update. The
next real moves are engineering review, UI evidence surfacing, Phase 2
source/binary identity reconciliation, and material scaling toward 100k/1M.

1. **Repo Custodian:** reconcile dirty repo, classify lanes, secret-scan
   candidate files, commit/push safe canonical state.
2. **Training Material Steward:** define the additive real-material route to
   100k/1M without duplicate laundering or toy augmentation.
3. **Engineering Orchestrator:** reconcile Phase 2 source/build/binary identity
   before any authority-scale execution.
4. **Pipeline Integrator:** keep the full-C1 diagnostic review surface distinct
   from 100k/1M authority and Phase 3 readiness.
5. **UI Engineer:** implement only evidence-backed diagnostic/blocked/authority
   states after explicit UI GO.
6. **Execution Orchestrator:** hold for an evidence-backed 100k/1M execution
   contract before any new gate run.
7. **Repo Custodian:** commit and push only scoped canonical updates after
   authorization, never broad-add the dirty tree.
8. **Meta-Orchestrator:** report a new success only if a real authority gate
   passes. Full-C1 diagnostic evidence is review material, not Phase 3/4
   authorization.

## Fail Routing

- Corpus/source failure goes to Training Material Steward.
- Phase 1 contract/runtime failure goes to Engineering Orchestrator and
  Pipeline Integrator.
- Phase 1 UI display issue goes to UI Engineer after backend truth is preserved.
- Phase 2 input/schema/source/binary mismatch goes to Pipeline Integrator and
  Engineering Orchestrator.
- Gate failure goes to Execution Orchestrator for evidence and fail-route
  classification, then back to the owner lane.
- Git safety failure goes to Repo Custodian.
- GPD/state drift goes to Repo Custodian plus Meta-Orchestrator.

Do not bypass failure routing by creating a new success narrative.

## Repository Rules

Allowed in git:

- Source code.
- Small schemas.
- Text reports.
- JSON gate results.
- Manifests.
- Checksums.
- Summaries.
- Sanitized command logs.

Forbidden in git:

- Model weights.
- Raw large tensor binaries.
- SDK binaries.
- Environment files.
- HF/OpenRouter/Comet tokens.
- SSH keys.
- `.venv`, `node_modules`, build caches.
- APK/AAB unless explicitly authorized for a release artifact.
- Raw `.pqa1`, `.qai1`, `.pjp1`, `.safetensors`, `.pt`, `.pth`, `.onnx`,
  `.tflite`, or similar payloads unless a specific artifact policy overrides.

No broad `git add -A`. Stage by lane and evidence class.

## Secrets And External Services

Secret file:

`/Users/prinivenpillay/.polymath-ai-corpus.env`

Known variables:

- `OPENROUTER_API_KEY`
- `COMET_API_KEY`
- `HF_TOKEN`

`HUGGINGFACE_HUB_TOKEN` is absent and should be exported from `HF_TOKEN` only in
authorized execution environments that require the alias.

Secrets must never be printed, copied into docs, committed, or included in
reports.

GitHub auth is available via OAuth/keyring as `Zer0pa-Architect-Prime`.

## Living Update Protocol

Update this document when any of these change:

- Thread roster or lane ownership.
- Authority gate.
- Phase status.
- Corpus/material status.
- Phone/runtime identity.
- GPD synchronization status.
- Git branch/remote policy.
- New nonclaim or forbidden promotion rule.
- Successful Phase 1/Phase 2 C1 execution.

Also update:

`runtime/reports/orchestration/current_board.json`

The board is the machine-readable status surface. This document is the human
drift lock.

## Current Non-Emergency Blockers

- Repo still has pre-existing unrelated dirty/untracked material. Canonical
  evidence should be staged narrowly and pushed without broad cleanup.
- Full C1 diagnostic passed, but C1/C2 scale is still short of 100k/1M
  authority.
- Material Steward reports conservative C1 + known C2 = `54,192` records, with
  a `45,808` record gap to 100k and `945,808` gap to 1M.
- Existing C1 variants are not additive scale without global dedup proof.
- Phase 2 source/binary identity is recorded for the full-C1 diagnostic, but
  Termux reported branch `main`, head `54d9aa1`, and dirty worktree. This needs
  explicit reconciliation before 100k/1M authority-scale promotion.
- GPD state is initialized but stale relative to Phase 2-C handoffs.
