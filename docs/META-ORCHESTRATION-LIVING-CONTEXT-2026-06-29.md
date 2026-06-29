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

### Phase 1: Ingestion / Chopping

Current status: backend/native Android path is real and strong.

Authority lane:

- Android app package: `ai.zer0pa.polymath.lab`
- App path: `apps/android-redmagic-lab/`
- REDMAGIC high-performance APK child-exec lane is the product authority lane.
- Standard APK 53-54M token IDs/sec behavior is drift, not fallback.
- Recent high-performance evidence is roughly 60M token IDs/sec class.

Remaining work:

- Product-real UI/operator surface.
- C1 source-to-PQA1 execution contract and run evidence.

### Phase 2: Mechanical Packetization

Current status: native engineering exists; authority is blocked on real PQA1.

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

Current C1 smoke is allowed as real-material pipeline hardening, but it is not
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

When the user says `GO`, run the work through the six lanes in this order:

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

- Repo is dirty and local branch is ahead of origin; Repo Custodian must
  reconcile before broad execution.
- C1/C2 are source material, not PQA1.
- C1/C2 scale is enough for smoke/integration hardening, not 100k/1M authority.
- Local Phase 2 source/binary identity needs reconciliation against promoted
  handoff hashes before Execution treats it as authority.
- GPD state is initialized but stale relative to Phase 2-C handoffs.
