# Handoff: Phase 11 Hardware-Native Training POVC Executor

This is the execution handoff for the next long-horizon agent. It is not a
status report and not a substitute for phone evidence.

## Read First

1. docs/PRD-HARDWARE-NATIVE-TRAINING-POVC.md
2. docs/PRD-GEMMA4-SNAPDRAGON-MEGAKERNEL-HETEROGENEOUS-TRAINING.md
3. RESISTANCE-V2.md
4. .gpd/STATE.md
5. .gpd/phases/11-hardware-native-training-povc/11-01-PLAN.md
6. docs/research-packs/gemma4-heterogeneous-training-frontier-2026-05-18/08-OPUS-LEVEL-VIEW-AND-POVC.md

## Role Split

- Phone is authority runtime. It owns the queue, runner, heartbeat, manifests,
  checksum chain, checkpoints, and telemetry.
- Mac is control plane only. Use ADB to start, inspect, stop, and pull
  artifacts. Do not drive every iteration from the Mac.
- RunPod is build/reference oracle only. Use it for Android builds, QAIRT host
  compile, PyTorch references, and comparator work. Do not make it a runtime
  teacher service during authority phone execution.

## Known Endpoints

- Repository: /Users/Zer0pa/Polymat AI/Polymath-AI
- Branch: gemma4-megakernel-native-training
- GitHub: https://github.com/Zer0pa/Polymath-AI
- RunPod SSH primary: ssh root@38.80.152.147 -p 31002 -i ~/.ssh/id_ed25519
- RunPod SSH alternate: ssh ltg8fdnxgmzwjy-64411e59@ssh.runpod.io -i ~/.ssh/id_ed25519
- RunPod pod ID: ltg8fdnxgmzwjy
- RunPod workspace: /workspace/Polymath-AI
- RunPod artifacts: /workspace/artifacts/polymath_gemma4
- Phone serial: FY25013101C8
- Phone root: /data/local/tmp/polymath_gemma4_gate
- Phase 11 phone root: /data/local/tmp/polymath_gemma4_gate/phase11

## Execution Shape

Execute H11-A through H11-H in order. A failure is data and should usually
advance the campaign with the best valid fallback. Stop only for the PRD's true
boundary blockers.

The first implementation objective is the phone-resident runner:

- local queue file;
- local run directory per experiment;
- heartbeat file;
- manifest and checksum chain;
- local STOP file;
- resume behavior;
- ADB start/inspect/pull only;
- no secrets printed;
- phone can continue after disconnection if Android permits.

## Campaign Cadence

Do not stop after the first defensible gate. Execute the chain. After each
H11 gate:

- write gate_result.json, blockers.md, falsifier_report.md, manifests, and
  checksum records;
- update GPD state/runlog with exact pass/fail/blocker status;
- preserve the winning config or strongest fallback for the next gate;
- commit and push git-allowed source/control/report artifacts when the worktree
  is coherent and artifact scans are clean;
- continue to the next gate unless the PRD's true boundary blockers apply.

If a gate fails, treat it as evidence. Repair immediately when the fix is local
and bounded. If the blocker is scientific or hardware-facing, use targeted
research/falsification side work if available, then decide: repair now, run
fallback, drop hypothesis, or escalate true blocker.

## Artifact Rules

Commit only source, schemas, text reports, JSON results, manifests, checksums,
and sanitized command logs. Do not commit model weights, raw tensors, SDK
binaries, environment files, HF tokens, phone token files, SSH keys, .venv,
node_modules, or build caches.

Every promoted gate needs:

- gate_result.json;
- artifact_manifest.json;
- timing_breakdown.json or telemetry.jsonl where relevant;
- checksum_chain.jsonl;
- blockers.md;
- falsifier_report.md;
- sanitized commands.log.

## Current Nonclaims

Do not promote these without new gate evidence:

- full Gemma4 training;
- Hexagon NPU backprop/training;
- public benchmark readiness;
- theoretical maximum.

HTP may be investigated as frozen-forward, teacher, updateable-section, or
zero-order forward-only arm. Normal HTP backprop is false until proven by API
and parity evidence.

## First Commands For Executor

These are inspection/start-shape commands, not commands for this PRD-writing
task:

```bash
cd "/Users/Zer0pa/Polymat AI/Polymath-AI"
git status --short --branch
adb -s FY25013101C8 devices
ssh root@38.80.152.147 -p 31002 -i ~/.ssh/id_ed25519 'cd /workspace/Polymath-AI && git status --short --branch'
```

If the primary RunPod SSH route fails, try:

```bash
ssh ltg8fdnxgmzwjy-64411e59@ssh.runpod.io -i ~/.ssh/id_ed25519 'cd /workspace/Polymath-AI && git status --short --branch'
```

Then implement H11-A. Do not start with H11-E, H11-G, a long endurance run, or
a public benchmark. The daemon/queue and bottleneck evidence are the spine of
the campaign.
