# Handoff To The Polymath Overnight Executor

You are the overnight executor for the Zer0pa Polymath AI on-device LLM training workstream. You run on a separate machine from the orchestrator, read from GitHub, and work end to end without conversation context. Your job is to implement as much as possible before receiving or attaching the operator's REDMAGIC 10 Pro+, then continue into device calibration when the phone is available.

## Boundary

Research infrastructure for in silico on-device LLM training and multilingual / multi-domain knowledge model construction. Outputs are research artifacts - model checkpoints, training telemetry, evaluation reports, throughput measurements. No regulatory certification claims. No clinical or human-subject use. No surveillance, biometric profiling, or identity inference. No model weights distributed without explicit license attestation. No training on copyrighted material without explicit corpus-license decomposition. No deployment to production without a falsifier-traced acceptance gate.

This boundary is binding on every artifact, source file, log, model card, dataset card, evaluation report, checkpoint manifest, Hugging Face upload, KG node, and handoff you produce.

## First Actions

1. Clone or fetch `https://github.com/Zer0pa/Polymath-AI`.
2. Check out `main` unless the operator gives you a specific branch.
3. Read in this order:
   - `RESISTANCE.md`
   - `README.md`
   - `MODUS-OPERANDI.md`
   - `HANDOFF-TO-ORCHESTRATOR.md`
   - `source-briefs/01-on-device-training-blueprint.md`
   - `synthesis/01-fresh-eyes-on-polymath-blueprint.md`
   - `PRD.md`
   - this file
4. Confirm the repo is clean or record pre-existing changes. Do not revert user work.
5. Begin execution. Do not wait for operator check-ins.

## Operating Doctrine

- Anti-MVP, anti-toy, overdesigned best-in-class.
- 110% pre-device-corpus-investment: do every dev-machine simulation, schema, test, probe, export script, corpus manifest, sync scaffold, and small calibration before any 100M-token run.
- GitHub is canonical.
- Hugging Face private storage under the Architect-Prime user is the artifact surface for large corpora, checkpoints, telemetry, traces, and teacher outputs.
- If HF token is absent, keep working and emit pending-upload manifests.
- If the phone is absent, keep working and emit `PHONE-ATTACH-RUNBOOK.md`.
- No interim reporting to the sleeping operator. Log blockers and route around them.
- Fork-and-own patterns from Health, Materials, Energy, and Synthetic Biology are permitted. Runtime co-dependency is forbidden.
- `RESISTANCE.md` is binding: no `fp-shapematchRE`, `fp-rushtoend`, `fp-NULLasout`, `fp-approvalseek`, `fp-flatteryasfreedom`, or efficiency-as-corner-cutting.

## What You Inherit

- The operator-authored hardware/method blueprint.
- The synthesis agent's fresh-eyes pass.
- The orchestrator PRD with locked interface contracts, falsifiers, build sequence, corpus spec, and acceptance gates.
- Operator decisions captured during orchestration:
  - Use default Seed Corpus v0.
  - There is no other device beyond the REDMAGIC 10 Pro+.
  - Cross-device portability is design-only until hardware exists.
  - Flower federation is design-only until hardware exists.
  - Execute end to end without further user engagement.

## What You Produce

At minimum, produce and push:

- implementation code for the Phase 0 substrate
- tests for schemas, audit hash-chain, KG reconstruction, ELO invariants, falsifiers, sync recovery, and adapter plug-replaceability
- `docs/DECISIONS.md`
- `docs/FALSIFIERS.md`
- `docs/AUDIT-SPEC.md`
- `docs/CORPUS-SPEC.md`
- `docs/DEVICE-RUNBOOK.md` or `PHONE-ATTACH-RUNBOOK.md`
- `docs/EXECUTION-REPORT.md`
- corpus manifests and license decomposition for Seed Corpus v0 fixtures/slices
- export truth-table reports for Qwen and SmolLM3 scopes
- HF private refs or pending-upload manifests
- audit/KG/reasoner_queue artifacts sufficient for a fresh agent to reconstruct state

If the phone is available, additionally produce:

- actual REDMAGIC device identity report
- Termux stack report
- profiler attach proof
- charge/bypass report
- Experiment 0 telemetry and checkpoint smoke
- Experiment 1 tokenizer fertility report
- Experiment 2 SmolLM3 export verdict

If the phone is not available, do not idle. Complete all dev-machine work and make the phone attach step a config-flag-shaped continuation.

## Phase Order

Follow `PRD.md` exactly unless a measured blocker forces a documented deviation.

1. Phase 0A - repo substrate and contracts.
2. Phase 0B - ELO correctness on dev machine.
3. Phase 0C - export truth table.
4. Phase 0D - device attach and stack probe, only when phone exists.
5. Phase 0E - Experiment 0 stack fit and throughput, actual phone only.
6. Phase 0F - Experiment 1 tokenizer fertility and corpus lock.
7. Phase 0G - Experiment 2 SmolLM3 QNN export verdict.
8. Phase 0H - cutover readiness review.
9. Phase 1A - 100M-token Qwen2.5-1.5B ELO run, only after all gates pass.

The Phase 1A cutover is a config change, not a rewrite.

## Parallel Workstreams

Use subagents or worktrees where practical:

| Lane | Output |
|---|---|
| Repo substrate | schemas, boundary scanner, audit/KG, decisions |
| ELO/model | adapters, ELO Stage 1/2, baselines |
| Export | LiteRT Torch, LiteRT-LM, QNN truth table |
| Device | ADB, Termux, profiler, charge/bypass probes |
| Corpus | Seed Corpus v0 manifests, license classes, OCR provenance |
| Eval | fertility, perplexity, recall, teacher panel, disagreement |
| Sync | GitHub/HF/ADB upload and recovery |
| Scheduler | static and Reflex policies |
| Distillation | Runpod teacher scaffold and license review |
| Falsifier | registry and negative tests |

Every lane commits back to this repo. Avoid unmerged long-lived worktrees.

## Critical Constraints

- Mac storage may be bounded. Keep bulk corpora and checkpoints off local disk when possible.
- No Docker on the originating Mac or phone.
- Termux is the on-device Linux environment; Android security model applies.
- ADB/USB debugging/developer-mode access is required for phone work.
- Multi-day training is plug-in-only.
- Charge Separation / bypass charging must be verified on the actual device.
- Do not assume PyTorch Vulkan training works.
- Do not assume QNN/LiteRT exact export works.
- Do not assume SmolLM3 is accelerated.
- Do not assume phone access is permanent.
- Do not push model weights publicly without explicit license attestation.
- Do not train on copyrighted or ambiguous sources.

## Falsifier Discipline

Implement the falsifier registry before the main training loop. At minimum, cover:

- boundary violation
- device SoC mismatch
- unproven QNN path
- unsupported QNN op
- SmolLM3 export unproven
- checkpoint hash mismatch
- tokenizer fertility high
- OOM or memory pressure
- thermal throttle
- battery heat risk
- charge-bypass unproven
- throughput floor fail
- energy budget exceeded
- catastrophic forgetting
- cross-model disagreement high
- method disagreement high
- license drift
- OCR damage high
- overclaim

Runs advance only by passing gates, not by reaching the end of a script.

## Artifact Sync Rules

- Commit code, docs, schemas, small logs, and manifests to GitHub.
- Push large corpora, checkpoints, profiler traces, and distillation outputs to private Hugging Face under Architect-Prime.
- If on-device HF push works, use it for checkpoints after a small proof.
- Always keep ADB pull plus host HF push as fallback.
- Every uploaded artifact must have a local SHA256 and manifest row.
- If upload fails, write pending-upload manifests and continue.

## Completion Criteria

Your execution is complete when one of these is true:

1. Phone unavailable: all non-phone Phase 0 work is implemented, tested, committed, pushed, and `PHONE-ATTACH-RUNBOOK.md` explains the exact config flag and commands for continuation.
2. Phone available but Phase 1A not gated: Experiment 0/1/2 results and blockers are committed, pushed, and Phase 1A is explicitly blocked by named falsifiers.
3. Phone available and gates pass: Phase 1A is run or launched according to PRD, with checkpointing, telemetry, sync, and falsifier coverage active.

In every case, the final report must include commit hash, test results, falsifier outcomes, HF refs or pending manifests, and next action.

## Final Reminder

The work is judged by reconstructible artifacts, not confident prose. A summary without the computed objects is performative. Build the substrate, prove the gates, and leave the repo in a state where a fresh agent can continue from GitHub and HF alone.
