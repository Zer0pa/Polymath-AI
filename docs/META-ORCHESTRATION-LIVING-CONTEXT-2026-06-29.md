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
implementation/authority run; newer handoffs show Phase 2-C native engineering
has advanced to a real-corpus blocker. Therefore:

- Treat this document plus the listed handoffs as live orchestration authority.
- Treat `.gpd` as initialized but stale on the Polar Phase 2 current state.
- Do not run GPD repair/sync/write commands until the Meta-Orchestrator
  authorizes Repo Custodian to reconcile state.
- After repo hygiene, GPD should be reconciled to reflect the six-thread
  orchestration and the current Phase 2-C real-corpus blocker.

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

Primary current corpus handoff:

`/Users/Zer0pa/Polymat AI/runtime/reports/corpus_pipeline/c1_c2_frontier_scale_20260629T100304Z/handover/c1_c2_enriched_handover_manifest.md`

C1 package:

`/Users/Zer0pa/Polymat AI/corpus_packages/commercial/20260629T100304Z/phase_C1_lexatlas_frontier_gpt_enriched_scale_v1`

C2 package:

`/Users/Zer0pa/Polymat AI/corpus_packages/commercial/20260629T100304Z/phase_C2_vocabexpansion_frontier_gpt_enriched_scale_v1`

Current corpus interpretation:

- C1 has 5,180 promoted records.
- C2 has 3,198 promoted records.
- Combined promoted records: 8,378.
- These packages are valid enriched QA source material.
- They are not PQA1 and do not satisfy the 100k/1M Phase 2 authority gate.
- Default training-safe enriched fields are: `formal_definition`,
  `related_terms`, `usage_example`, `register`, `domain`, `collocations`,
  `sentiment_potential`, `word_family`, `pragmatic_note`, and `frame`.
- `cultural_note`, `scenario`, and `poetic_example` are experimental and not
  default primary SFT fields.

## Current Phase Facts

### Current C1 Smoke Evidence

Status: C1 Phase 1 plus Phase 2 smoke passed on the REDMAGIC phone.

This is integration evidence for the source-to-PQA1-to-PJP1 path. It is not the
100k/1M Phase 2 authority gate and does not authorize Phase 3.

Phase 1 source-of-record:

- Run label: `c1_phase1_smoke_internal_20260629T143408Z`
- Report root:
  `runtime/reports/polar_phase1_c1_pipeline/c1_phase1_smoke_internal_20260629T143408Z_phase1_c1_pipeline_smoke`
- App report run id: `2026-06-29T143414Z`
- Status: `phase1_c1_smoke_complete`
- Records selected: 64
- Token IDs: 2,674
- Material hash:
  `243f8b5349988ca0a288dcdc90445254c4b5dd6c3691a762cc683d4c72154f8d`
- PQA1 outputs: 8 shards, all present with hash/size metadata.
- Forbidden payload scan: pass.

Phase 2 smoke:

- Run label: `c1_phase2_smoke_20260629T144238Z`
- Report root:
  `runtime/reports/polar_phase2_c1_smoke/c1_phase2_smoke_20260629T144238Z`
- Wrapper status: pass.
- Native packetizer status: pass.
- PQA1 files consumed: 8.
- Source records: 64.
- Source real tokens: 2,674.
- Packets: 64.
- PJP1 path on phone:
  `/data/data/com.termux/files/home/polymath_phase2_outputs/c1_phase2_smoke_20260629T144238Z/raw_c1_phase2_smoke_20260629T144238Z.pjp1`
- PJP1 SHA-256:
  `7ffb81ab1fc129fcaf7de84a50a196ebac30d366d49e59471486e51a323ee340`
- PJP1 bytes: 583,680.
- Raw PJP1 inside git worktree: false.

Verified Phase 2 identities:

- Packetizer SHA-256:
  `11c81138d181f09dd1a9a4715952c8a5357a91e3f1c1562f2fb9761d4d4c336a`
- Embedding SHA-256:
  `b57e1e756f32d02c1aaad6c5c868f975f53b0938e0a04ed546804ed9c7d4ca7b`
- Embedding manifest SHA-256:
  `0bf2dc2ec4487c079da94d8c8a37f54bb7c45ed2f9a29dbbd73edc0ababaf8bd`
- JL SHA-256:
  `1b1f9de3dd6fbdf9597240eeeb08a6b482b33f1ae4d127e730222750cdf92a79`

### Phase 1: Ingestion / Chopping

Current status: backend/native Android path is real and strong. The C1 smoke
source-to-PQA1 path passed on 64 real C1 source records.

Authority lane:

- Android app package: `ai.zer0pa.polymath.lab`
- App path: `apps/android-redmagic-lab/`
- REDMAGIC high-performance APK child-exec lane is the product authority lane.
- Standard APK 53-54M token IDs/sec behavior is drift, not fallback.
- Recent high-performance evidence is roughly 60M token IDs/sec class.

Remaining work:

- Product-real UI/operator surface.
- Scale authority material beyond C1 smoke.

### Phase 2: Mechanical Packetization

Current status: native engineering exists; C1 real-material smoke passed;
authority remains blocked on 100k/1M real PQA1.

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

Current C1 smoke passed as real-material pipeline hardening, but it is not the
100k/1M Phase 2 authority gate.

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

When the user says `GO`, run the work through the six lanes in this order. For
the 2026-06-29 C1 smoke, steps 1 through 7 completed, and step 8 is the current
repo-evidence freeze/push step.

1. **Repo Custodian:** reconcile dirty repo, classify lanes, secret-scan
   candidate files, commit/push safe canonical state.
2. **Training Material Steward:** accept/reject C1 as first source specimen and
   define what fields and records enter Phase 1 conversion.
3. **Engineering Orchestrator:** define or repair the exact Phase 1 C1-to-PQA1
   execution contract.
4. **Pipeline Integrator:** bind material, Phase 1 reports, PQA1 identity, and
   Phase 2 input assumptions into an executable handoff.
5. **Execution Orchestrator:** run Phase 1 on C1 only after receiving material
   and engineering/integration handoffs.
6. **Engineering Orchestrator / Pipeline Integrator:** use real C1 PQA1 output
   to debug and harden Phase 2 input handling.
7. **Execution Orchestrator:** run Phase 2 on the C1-derived real PQA1 output.
8. **Repo Custodian:** commit and push converged pipeline evidence.
9. **Meta-Orchestrator:** report success only if Phase 1 and Phase 2 C1
   execution are clean; then begin Phase 3/4 planning.

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
  C1 smoke evidence should be staged narrowly and pushed without broad cleanup.
- C1/C2 are source material, not PQA1.
- C1/C2 scale is enough for smoke/integration hardening, not 100k/1M authority.
- Phase 2 source/binary identity is recorded for the C1 smoke, but still needs
  explicit reconciliation before 100k/1M authority-scale promotion.
- GPD state is initialized but stale relative to Phase 2-C handoffs.
