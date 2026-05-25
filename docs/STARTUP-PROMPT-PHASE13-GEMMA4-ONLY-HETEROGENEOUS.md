# Startup Prompt: Phase 13 Gemma4-Only Heterogeneous Corpus-Scale Executor

You are the execution agent for Polymath-AI Phase 13. You are executing a
Gemma4-only hardware-native learning campaign, not rewriting the PRD.

Repository:
- `/Users/Zer0pa/Polymat AI/Polymath-AI`
- Branch: `gemma4-megakernel-native-training`
- GitHub: `https://github.com/Zer0pa/Polymath-AI`

Authority topology:
- Phone is authority runtime: REDMAGIC NX789J / SM8750 / serial `FY25013101C8`.
- Mac is control plane only.
- RunPod is build/reference/teacher-shard oracle only.
- RunPod SSH primary: `ssh root@38.80.152.147 -p 31002 -i ~/.ssh/id_ed25519`
- RunPod SSH alternate: `ssh ltg8fdnxgmzwjy-64411e59@ssh.runpod.io -i ~/.ssh/id_ed25519`
- RunPod workspace: `/workspace/Polymath-AI`
- Phone root: `/data/local/tmp/polymath_gemma4_gate`

First read:
1. `AGENTS.md`
2. `docs/PRD-PHASE13-GEMMA4-ONLY-HETEROGENEOUS-CORPUS-SCALE.md`
3. `docs/HANDOFF-PHASE13-GEMMA4-ONLY-HETEROGENEOUS-EXECUTOR.md`
4. `.gpd/STATE.md`
5. `.gpd/phases/13-gemma4-only-heterogeneous-corpus-scale/13-01-PLAN.md`
6. Phase 12 final artifact:
   `runtime/reports/gemma4_megakernel/phase12_hardware_native_learning/20260524T175056Z_phase12_final_exact_claims/phase12_gate_status.json`
7. `RESISTANCE-V2.md`

Mission:
Execute P13-A through P13-I sequentially. Do not start with HTP, a benchmark, or
a long run. Start by auditing and quarantining Phase 12 contamination, then make
Gemma identity and kernel-lineage telemetry impossible to fake.

Critical correction:
Qwen/random-init hidden-size-1536 HTP artifacts are invalid for Gemma
heterogeneous learning. They are allowed only as negative tool-surface evidence.
They must not appear inside a promoted Gemma gate.

Required gates:
- P13-A Phase 12 contamination audit and state repair.
- P13-B Gemma identity and kernel-lineage instrumentation.
- P13-C scaled phone-native HF streaming corpus cache.
- P13-D expanded gradient parity.
- P13-E multi-site Gemma adapter implementation.
- P13-F Gemma-compatible HTP artifact or hard falsification.
- P13-G heterogeneous candidate versus Adreno baseline.
- P13-H overnight phone-local long run.
- P13-I exact claims and next branch decision.

Operating mode:
- Long-horizon execution. Do not stop after a narratable intermediate result.
- After each gate, write artifacts, update GPD state/runlog, preserve valid
  fallback, and continue.
- Use high-reasoning subagents/research only for concrete blockers with a
  required decision: repair now, run fallback, drop hypothesis, or escalate true
  blocker.
- Launch overnight phone-local queues only after setup gates pass. The phone may
  continue after ADB disconnect if the local queue/heartbeat/STOP/resume
  contract is satisfied.

Hard rejection rules:
- Reject non-Gemma artifacts in Gemma gates.
- Reject hidden-size mismatch.
- Reject random-init artifacts as language-model evidence.
- Reject 16-sequence corpus learning claims.
- Reject host minibatch serving.
- Reject broad `megakernel` claims without kernel-lineage evidence.
- Reject train-loss-only promotion.

Initial commands:

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

Then execute P13-A. Do not run P13-H until P13-A through P13-G have exact
pass/fail/fallback artifacts.
