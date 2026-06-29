# Phase 2-C Handoff And Drift Quarantine Mandate

You are the live Termux Codex agent inside:

`/data/data/com.termux/files/home/Polymath-AI`

Authority runtime:

`REDMAGIC NX789J / Snapdragon SM8750 / Termux / serial FY25013101C8`

You are not moving to Phase 3. You are preparing a clean, falsification-first Phase 2-C handoff so a new agent can pick up cold, integrate the promoted work, and know exactly what remains blocked by real training material.

## Culture Lock

Good is the enemy of great. The top acceptance gate is sovereign. Objective substitution is failure. A green metric does not license closure if the governing objective remains unresolved. Treat any regression on authority metrics as failure unless it is a clearly non-promoted comparison arm. Do not reward-hack by narrowing the PRD after the fact. Do not turn mixed evidence into a pass narrative. Preserve the alien mechanism before making it legible.

Phone is authority. Mac is control plane/meta-orchestration. RunPod is build/reference oracle only unless a PRD explicitly says otherwise.

Do not normalize this into standard Gemma inference, conventional LoRA, adapter-only continuation, or benchmark theater. Do not use megakernel language unless there is a real fused/static/routed training path with measured dispatch, traffic, thermal, scope, and learning advantage. No HTP/NPU claim unless HTP/NPU output or routing changes the executed Gemma training route, objective, gradient, update, teacher, or state transition.

Comet logging is mandatory for all runs. Use `COMET_API_KEY` from environment only. Never write or echo secrets. Project: `zer0pa/mobile-polymath-ai-training`.

## Current Known State

The current honest terminal status is:

`phase2c_real_corpus_required`

Read these authority artifacts first:

1. `AGENTS.md`
2. `.gpd/STATE.md`
3. `.gpd/ROADMAP.md`
4. `docs/PHASE2C_PRD_SUPPLEMENT_MAXIMAL_GUARDRAILS_2026-06-28.md`
5. `/sdcard/Download/polymath/polar_phase2c/PHASE2C_PRD_MAXIMAL_2026-06-28.md`
6. `/sdcard/Download/polymath/polar_phase2c/PHASE2C_PRD_SUPPLEMENT_MAXIMAL_GUARDRAILS_2026-06-28.md`
7. `/sdcard/Download/polymath/polar_phase2c/2026-06-28Tphase2c-final/ENGINEERING_REPORT.md`
8. `/sdcard/Download/polymath/polar_phase2c/2026-06-29Tphase2c-high-diversity-opt/ENGINEERING_REPORT.md`
9. `/sdcard/Download/polymath/polar_phase2c/2026-06-29Tphase2c-after-high-diversity-continuation/ENGINEERING_REPORT.md`
10. `/sdcard/Download/polymath/polar_phase2c/2026-06-29Tphase2c-after-high-diversity-continuation/phase2c_gate_result.json`
11. `/sdcard/Download/polymath/polar_phase2c/2026-06-29Tphase2c-after-high-diversity-continuation/phase2c_real_material_required_inputs.json`
12. `/sdcard/Download/polymath/polar_phase2c/2026-06-29Tphase2c-after-high-diversity-continuation/phase2c_next_real_corpus_gate.md`

Known evidence to preserve:

- Phase 2 original Python/NumPy PQA1-to-PJP1 path was correct but not maximal: about 18,517 real tok/sec on the large run. It is a reference/non-promoted historical arm, not the current promoted route.
- Phase 2-B native closure improved the path: about 598,675 real tok/sec at 1M and 462,598 real tok/sec at 100k in the cited closure artifacts.
- Phase 2-C found and fixed the high-diversity performance collapse. The old 50k diversity rung was about 120,970 tok/sec; the optimized native path reached about 347,915 tok/sec. The old 100k diversity rung was about 69,799 tok/sec; the optimized native path reached about 271,713 tok/sec.
- The optimized route uses exact dense Rademacher input-token projection cache construction with a single-token k4 NEON kernel sharded across 8 threads. PQA1 remains promoted input; PJP1 remains promoted audit output.
- Dense Rademacher k=256 remains incumbent for proxy evidence only. SRHT, Lorenz, alternate k, Arrow/ring sidecars, and any NPU execution claims are not promoted.
- Continuation status is `phase2c_real_corpus_required`: synthetic/proxy/engineering gates have been exhausted without real corpus. Final maximal closure, final k/projection promotion, and Phase 3 handoff require real Phase 1 PQA1 training material.

## Mission

Prepare a handoff package and clean active working paths so the next agent can read itself in without being pulled into obsolete lower-performing regimes.

This is not a performance sprint unless a tiny verification step is required to prove the handoff. Do not run expensive 100k/1M packetization again unless an existing artifact is missing or corrupt. Do not claim `phase2c_maximal_pass`. Do not claim Phase 3 handoff. Do not claim NPU execution.

## Required Output Locations

Create one timestamped report root:

`runtime/reports/polar_phase2c/<UTC>-phase2c-handoff-integration-prep/`

Create one ADB-pullable mirror:

`/sdcard/Download/polymath/polar_phase2c/handoff/<UTC>-phase2c-handoff-integration-prep/`

The mirror must contain only safe review artifacts. Do not copy raw `.pjp1`, `.pqa1`, `.qai1`, `.jsonl`, `.safetensors`, or `.bin` payloads into the handoff mirror. Instead, index them by path, byte size, and hash where available.

## Required Handoff Files

Produce all of these files in the report root and safe mirror:

1. `READ_ME_FIRST_PHASE2C_HANDOFF.md`
   - Plain-English status for a nontechnical project owner.
   - What works.
   - What does not work yet.
   - Why real corpus is now the honest blocker.
   - Exact current promoted route.
   - Exact non-promoted routes.
   - The first 30 minutes of work for a new agent.

2. `ENGINEERING_HANDOFF.md`
   - Phase 2/2-C architecture: Phase 1 PQA1 input, PJP1 output, packet structure, projection cache, native packetizer, verifier stack.
   - Source files and scripts that matter.
   - Build commands.
   - Reproduction commands for cheap sanity checks.
   - Full real-corpus gate commands or command templates.
   - Known performance numbers with report paths and Comet URLs.
   - Quality boundaries and nonclaims.

3. `NEW_AGENT_STARTUP_PROMPT.md`
   - A copy-paste prompt for a fresh Termux Codex agent.
   - It must force the agent to read the handoff first, obey GPD lifecycle, preserve evidence, avoid Phase 3, and only resume Phase 2-C when real training material exists or when integration hardening remains clearly bounded.

4. `PHASE2C_STATUS_MATRIX.json`
   - Machine-readable gate matrix.
   - Include status, evidence file, pass/fail/blocker, promoted/non-promoted, and whether real corpus is required.

5. `PROMOTED_PATH_MANIFEST.json`
   - Canonical current route only.
   - Include source files, scripts, build command, binary path and sha256 if available, source hash if available, PQA1/PJP1 schema versions, projection type, k, thread count, and key performance reports.

6. `DEPRECATED_PATHS.md`
   - List lower-performing or misleading historical paths.
   - Explain why each is deprecated.
   - Explicitly include:
     - Python/NumPy Phase 2 route as reference-only.
     - Phase 2-B failed native variants and lower-throughput configs.
     - Old single-thread or non-parallel projection-cache preparation route that collapsed at 50k/100k diversity.
     - Any label implying `phase2_maximal_closure_pass` where performance or real-corpus proof is not sovereign.
     - Arrow/ring sidecars, SRHT, Lorenz, and alternate k comparison arms unless they have separate promotion evidence.
     - Any NPU/HTP claims that are only staging/preflight and not execution.

7. `DRIFT_QUARANTINE_MANIFEST.json`
   - Record every stale file, config, prompt, script path, wrapper, or generated artifact that could mislead a new agent into an old regime.
   - For each item, include action: `deleted`, `moved_to_deprecated`, `made_fail_closed`, `documented_only`, or `kept_for_evidence`.
   - Authority evidence must be `kept_for_evidence`, not deleted.

8. `SOURCE_CLEANUP_DIFF.md`
   - Explain any repository changes made for drift cleanup.
   - If deletion is unsafe, say so and record the safer action.
   - Never edit root `README.md`.

9. `GIT_STATUS_AND_DIFF.patch`
   - Capture `git status --short --branch`.
   - Capture a unified diff of all handoff/drift-cleanup source/doc changes.
   - Do not include secrets.

10. `ARTIFACT_INDEX.md`
    - Index all relevant Phase 2, Phase 2-B, and Phase 2-C report roots and mirrors.
    - Include exact paths, one-line purpose, status, and whether the artifact is promoted, reference-only, failed, or proxy-only.

11. `RAW_PAYLOAD_MANIFEST.json`
    - List raw payloads that are intentionally not copied into the mirror.
    - Include local phone path, size, sha256 if available, producing report, and purpose.

12. `COMET_INDEX.md`
    - Include all known Phase 2/2-B/2-C Comet URLs and what each run means.
    - Include the handoff Comet experiment if logging succeeds.

13. `COMET_STATUS.json`
    - Must be `logged` if `COMET_API_KEY` is available and Comet works.
    - If blocked, include exact technical evidence without exposing secrets.

14. `REPRODUCTION_RUNBOOK.md`
    - Minimal cheap sanity sequence.
    - Full real-corpus gate sequence.
    - How to avoid old paths.
    - How to verify PJP1 readback, stratified oracle, collision/margin/Hamming behavior, and Comet logging.

15. `REAL_CORPUS_GATE_SPEC.md`
    - Exact expected real training material format.
    - Required sample sizes: 100k and 1M.
    - Required metadata: source manifest, license/provenance, tokenizer hashes, PQA1 source SHA-256 stream, answer/loss masks, real labels/objective metadata.
    - Pass gates:
      - Comet logged.
      - PJP1 readback pass.
      - Stratified oracle 100% bit-exact sampled packets.
      - At least 50k distinct token IDs for production floor gate.
      - Distinct-token throughput at or above 200,000 real tok/sec.
      - Collision duplicate-token fraction at or below 0.1%.
      - Margin/Hamming geometry no worse than synthetic proxy baseline without explanation.
      - No Phase 3 handoff until NPU consumer preflight is repeated on real PJP1.

16. `PHASE3_NOT_READY.md`
    - State why Phase 3 is not authorized yet.
    - State exactly what evidence would unlock it.

17. `APP_AGENT_INTEGRATION_NOTES.md`
    - Explain what the Android app stream can consume now.
    - Explain what must wait for real corpus and app-side integration.
    - No gaming privileges or REDMAGIC/Game Mode claim unless the app stream proves it.

18. `HYGIENE_SCAN.json`
    - Scan the handoff mirror and report root for forbidden payload suffixes and secret literals.
    - Include file count, skipped large/raw payloads, findings, and pass/fail.

19. `GPD_RECONCILIATION.md`
    - State how `.gpd/STATE.md`, `.gpd/ROADMAP.md`, and `GPD/state.json` describe the Phase 2-C state.
    - If you update GPD, validate it.
    - State explicitly that this is not Phase 3 closure.

20. `FINAL_TERMINAL_STATUS.json`
    - Include status, report root, mirror root, Comet status, hygiene status, drift action count, blocker, and next authorized work.

## Drift Cleanup Rules

User intent: remove drift, stale configs, stale paths, and old lower-performing regimes that would cause the next agent to waste time or regress.

Mandatory boundary:

- Do not delete authority evidence.
- Do not delete raw payloads unless they are duplicate temporary scratch files and you have exact hashes and a manifest entry proving they are non-authority.
- Do not delete Comet evidence, reports, gate JSON, engineering reports, or source history.
- Do not edit root `README.md`.
- Do not commit unless the user explicitly asks.

Safe cleanup preference:

1. Make the promoted path unmistakable.
2. Move stale non-authority prompts/configs/wrappers into a `deprecated/` or `drift_quarantine/` area when safe.
3. Add fail-closed warnings to stale launch wrappers if they can launch lower-performing paths.
4. If a file must be kept for evidence, mark it `kept_for_evidence` in `DRIFT_QUARANTINE_MANIFEST.json`.
5. If deletion is risky, do not delete; document the risk and make the new handoff route authoritative.

Do not mistake deletion theater for engineering quality. The goal is to prevent regression while preserving falsification evidence.

## Verification

Before final terminal response:

1. Validate all JSON files with `jq empty`.
2. Run a hygiene scan on the report root and mirror.
3. Verify the mirror is ADB-pullable and contains the required files.
4. Record `git status --short --branch`.
5. If Comet is available, log a handoff/prep experiment with summary metrics and artifact references only. Do not upload raw training payloads.
6. If GPD state is touched, run the available GPD validation command and include its result.

## Final Response Format

Return only a concise terminal status block:

`phase2c_handoff_prepared`

Then include:

- report root
- mirror root
- Comet URL or exact Comet blocker
- hygiene status
- drift actions summary
- next authorized work

If blocked, return:

`phase2c_handoff_blocked`

Then include the exact command, file, permission, or missing evidence that blocks handoff.

Do not narrate a win. Do not claim Phase 3. Do not claim maximal closure. Do not stop halfway with only a status report.
