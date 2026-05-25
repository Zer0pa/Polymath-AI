# Handoff: Phase 13 Gemma4-Only Heterogeneous Corpus-Scale Executor

This is an execution handoff. It is not a status report and not a substitute
for phone evidence.

## Read First

1. `AGENTS.md`
2. `docs/PRD-PHASE13-GEMMA4-ONLY-HETEROGENEOUS-CORPUS-SCALE.md`
3. `.gpd/STATE.md`
4. `.gpd/phases/13-gemma4-only-heterogeneous-corpus-scale/13-01-PLAN.md`
5. `runtime/reports/gemma4_megakernel/phase12_hardware_native_learning/20260524T175056Z_phase12_final_exact_claims/phase12_gate_status.json`
6. `docs/PRD-HARDWARE-NATIVE-TRAINING-POVC.md`
7. `docs/research-packs/gemma4-heterogeneous-training-frontier-2026-05-18/08-OPUS-LEVEL-VIEW-AND-POVC.md`
8. `RESISTANCE-V2.md`

## Known Endpoints

- Repository: `/Users/Zer0pa/Polymat AI/Polymath-AI`
- Branch: `gemma4-megakernel-native-training`
- GitHub: `https://github.com/Zer0pa/Polymath-AI`
- Phone serial: `FY25013101C8`
- Phone root: `/data/local/tmp/polymath_gemma4_gate`
- RunPod pod ID: `ltg8fdnxgmzwjy`
- RunPod SSH primary: `ssh root@38.80.152.147 -p 31002 -i ~/.ssh/id_ed25519`
- RunPod SSH alternate: `ssh ltg8fdnxgmzwjy-64411e59@ssh.runpod.io -i ~/.ssh/id_ed25519`
- RunPod workspace: `/workspace/Polymath-AI`
- RunPod artifacts: `/workspace/artifacts/polymath_gemma4`

## Correction From Phase 12

The Phase 12 HTP/QNN lane used Qwen/random-init hidden-size-1536 artifacts.
That is invalid for Gemma heterogeneous learning. Treat it only as a negative
tool-surface probe. It cannot advance a Gemma claim.

The valid Phase 12 learning lane is Adreno/OpenCL Gemma4 E4B residual-adapter
training:

- `model_id: google/gemma-4-E4B`
- hidden size `2560`
- `gemma4_layer_runner --run-h11f-topk-kl-compact`
- phone CPU token-to-hidden and objective helper path
- OpenCL layer/adapter path
- rank-16/rank-32 post-layer0 residual adapters

That lane is real but narrow. Phase 13 must not confuse it with full Gemma4
training, fused megakernel training, multi-site training, or heterogeneous
training.

## Execution Shape

Execute P13-A through P13-I in order:

- P13-A: contamination audit and state repair;
- P13-B: Gemma identity and kernel-lineage instrumentation;
- P13-C: corpus scale and phone-native HF stream;
- P13-D: full/sampled gradient parity expansion;
- P13-E: multi-site Gemma adapter implementation;
- P13-F: Gemma-compatible HTP artifact or hard falsification;
- P13-G: heterogeneous candidate versus Adreno baseline;
- P13-H: overnight phone-local long run;
- P13-I: exact claims and next branch decision.

Do not begin with HTP, a benchmark, or a long run. The first executable work is
to make non-Gemma contamination impossible.

## Hard Rejection Rules

Reject immediately:

- `Qwen`, `SmolLM`, random-init, hidden-size-1536, or non-Gemma artifacts inside
  any Gemma gate;
- HTP output not consumed by Gemma runtime but claimed as heterogeneous
  training;
- 16-sequence corpus cache promoted as learning scale;
- host tokenization or host minibatch serving sold as phone-native training;
- vague `megakernel` wording without kernel-lineage telemetry;
- train-loss-only promotion without heldout and fixed-control comparison.

## Long-Run Policy

The executor may launch an overnight phone-local sequential queue only after:

- P13-A contamination audit passes;
- P13-B identity/kernel-lineage telemetry passes;
- P13-C scaled corpus cache exists or has a true blocker;
- P13-D gradient evidence is materially stronger than Phase 12;
- P13-E/P13-F/P13-G have pass/fail/fallback artifacts.

The long run must use compact artifacts. Raw payloads stay on phone or RunPod
with hashes in git-allowed manifests.

## Artifact Policy

Commit only source, scripts, schemas, text reports, JSON results, manifests,
checksums, summaries, and sanitized command logs.

Do not commit model weights, raw tensor payloads, raw token payloads, SDK
binaries, QNN/DLC payloads, environment files, HF tokens, phone token files,
SSH keys, `.venv`, `node_modules`, or build caches.

Every promoted gate needs:

- `gate_result.json`;
- `artifact_manifest.json`;
- `blockers.md`;
- `falsifier_report.md`;
- sanitized `commands.log`;
- checksum or compact artifact index.

## First Commands

```bash
cd "/Users/Zer0pa/Polymat AI/Polymath-AI"
git status --short --branch
adb -s FY25013101C8 devices
ssh root@38.80.152.147 -p 31002 -i ~/.ssh/id_ed25519 'cd /workspace/Polymath-AI && git status --short --branch'
```

If primary RunPod SSH fails:

```bash
ssh ltg8fdnxgmzwjy-64411e59@ssh.runpod.io -i ~/.ssh/id_ed25519 'cd /workspace/Polymath-AI && git status --short --branch'
```

Then run P13-A. Fix stale GPD state before any phone experiment.
