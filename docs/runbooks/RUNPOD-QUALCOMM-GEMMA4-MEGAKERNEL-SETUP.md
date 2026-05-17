# RunPod Qualcomm Setup Runbook - Gemma 4 Snapdragon Megakernel

Date: 2026-05-16  
PRD: `docs/PRD-GEMMA4-SNAPDRAGON-MEGAKERNEL-HETEROGENEOUS-TRAINING.md`  
Status: DRAFT

## Purpose

Use the existing RunPod environment and Qualcomm tooling to make the Gemma 4 Snapdragon megakernel lane measurable and reproducible.

This runbook does not store live SSH routes, private keys, tokens, or host secrets. Operators should supply access through local shell config or environment variables.

## Required Inputs

```bash
export RUNPOD_SSH_TARGET="<user@host>"
export RUNPOD_SSH_PORT="<port>"
export RUNPOD_SSH_KEY="<absolute-path-to-private-key>"
```

The current known live pod details exist in private operator context and prior local status docs. They must not be committed into this runbook.

## Output Contract

Every run creates:

```text
runtime/reports/gemma4_megakernel/runpod/<UTC_RUN_ID>/
  commands.log
  toolchain_manifest.json
  filesystem_inventory.txt
  python_env_manifest.txt
  qairt_manifest.txt
  gemma4_model_cache_report.txt
  compile_probe_plan.md
  blockers.md
```

No SDK binaries, model weights, tokens, private keys, or raw caches are copied into git.

## Step 0: Connect Without Leaking Secrets

```bash
ssh -p "$RUNPOD_SSH_PORT" -i "$RUNPOD_SSH_KEY" "$RUNPOD_SSH_TARGET"
```

If connection fails, record the failure locally in `blockers.md`. Do not paste private key material or tokens into logs.

## Step 1: Create Run Directory

On RunPod:

```bash
cd /workspace
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)_gemma4_megakernel_setup"
mkdir -p "/workspace/Polymath-AI/runtime/reports/gemma4_megakernel/runpod/${RUN_ID}"
cd /workspace/Polymath-AI
REPORT_DIR="runtime/reports/gemma4_megakernel/runpod/${RUN_ID}"
```

## Step 2: Freeze Repository State

```bash
{
  date -u
  git status --short
  git branch --show-current
  git rev-parse HEAD
  git remote -v
} | tee "${REPORT_DIR}/repo_state.txt"
```

Required interpretation:

- if the clone is stale, update only after recording current state;
- do not `reset --hard` unless the branch and purpose are recorded;
- do not merge PR #4 blindly.

## Step 3: Freeze Python Environment

```bash
{
  which python || true
  python --version || true
  python -m pip list || true
  if [ -d .venv-litert213 ]; then
    . .venv-litert213/bin/activate
    which python
    python --version
    python -m pip list
  fi
} | tee "${REPORT_DIR}/python_env_manifest.txt"
```

## Step 4: Inventory Qualcomm / QAIRT

```bash
{
  find /workspace -maxdepth 3 \( -iname '*qairt*' -o -iname '*qnn*' -o -iname '*snpe*' \) -print
  find /workspace/qairt-2.44 -maxdepth 5 -type f 2>/dev/null | sed -n '1,240p'
} | tee "${REPORT_DIR}/qairt_manifest.txt"
```

Expected known useful tools include QNN host and Android libraries, `qnn-net-run`, and HTP backend libraries. Exact paths must be recorded from the live pod.

## Step 5: Inventory Gemma 4 Availability

```bash
{
  find /workspace -maxdepth 4 \( -iname '*gemma*' -o -iname '*litertlm*' -o -iname '*.safetensors' \) -print
  du -sh /workspace/models 2>/dev/null || true
  du -sh ~/.cache/huggingface 2>/dev/null || true
} | tee "${REPORT_DIR}/gemma4_model_cache_report.txt"
```

If Gemma 4 weights are absent, record that. Do not download full weights until disk and license gates are explicit.

## Step 6: Write Toolchain Manifest

Create `toolchain_manifest.json` with at least:

```json
{
  "run_id": "<UTC_RUN_ID>",
  "repo_sha": "<git_sha>",
  "python": "<version>",
  "torch": "<version_or_absent>",
  "transformers": "<version_or_absent>",
  "ai_edge_litert": "<version_or_absent>",
  "qairt_roots": [],
  "qnn_tools": [],
  "android_targets_present": [],
  "host_targets_present": [],
  "notes": []
}
```

Use a script if available; otherwise write it manually from recorded command outputs.

## Step 7: Compile Probe Plan

Before compiling anything, write `compile_probe_plan.md` naming:

- target model or synthetic graph;
- exact graph scope;
- expected input/output tensors;
- target SoC;
- expected output artifact path;
- correctness comparator;
- phone deployment plan;
- rollback plan.

No compile probe runs without this plan.

## Step 8: First Compile Candidates

Order:

1. Synthetic tiny RMSNorm/matmul graph.
2. Tiny Gemma-shaped block from static executor.
3. Gemma 4 E2B frozen-forward subgraph only if model artifacts and licensing are clean.

QNN/NPU is not the training backend by default. It is a frozen-forward proof lane.

## Step 9: Exfiltration Back To Repo

Only text manifests and reports come back:

```bash
rsync -av --exclude '*.safetensors' --exclude '*.tflite' --exclude '*.bin' --exclude '*.zip' \
  -e "ssh -p ${RUNPOD_SSH_PORT} -i ${RUNPOD_SSH_KEY}" \
  "${RUNPOD_SSH_TARGET}:/workspace/Polymath-AI/runtime/reports/gemma4_megakernel/runpod/${RUN_ID}/" \
  "runtime/reports/gemma4_megakernel/runpod/${RUN_ID}/"
```

Large artifacts require explicit artifact policy before transfer.

## Pass Condition

This runbook passes when the local repo contains a complete text-only RunPod manifest proving:

- exact repo state;
- exact Python/toolchain versions;
- exact QAIRT/QNN availability;
- Gemma 4 model/cache state;
- compile probe plan;
- blockers.

It does not pass by merely connecting to RunPod.
