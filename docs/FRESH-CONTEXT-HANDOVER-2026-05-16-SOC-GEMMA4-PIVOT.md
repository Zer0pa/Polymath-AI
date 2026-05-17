# Fresh Context Handover: SoC-First Polymath / Gemma4 Pivot

Date: 2026-05-16

Use this document to start a fresh thinking thread. It compiles the current status from:

- `docs/STATUS-2026-05-16-SOC-GEMMA4-PIVOT.md`
- local Polymath-AI checkout
- remote GitHub PR state
- live RunPod inspection
- connected RedMagic ADB inspection
- Hugging Face artifact inspection
- `/Users/Zer0pa/Gemma4 Kernel`

Boundary: Research infrastructure for in silico on-device LLM training and multilingual / multi-domain knowledge model construction. Outputs are research artifacts - model checkpoints, training telemetry, evaluation reports, throughput measurements. No regulatory certification claims. No clinical or human-subject use. No surveillance, biometric profiling, or identity inference. No model weights distributed without explicit license attestation. No training on copyrighted material without explicit corpus-license decomposition. No deployment to production without a falsifier-traced acceptance gate.

## Role For The Next Agent

You are not being asked to choose a final model.

You are being asked to think from first principles about a hardware-first learning regime for a consumer-phone SoC:

- CPU as orchestration, scheduling, optimizer/control plane, and fallback.
- GPU/Adreno as flexible parallel compute, especially for custom kernels and backward paths.
- NPU/Hexagon as fixed-shape, compiled, forward-strong compute.
- Memory bandwidth, storage, thermal, power, and backend launch overhead as real physical constraints, not implementation details.

Treat transformer, Qwen, Gemma4, ELO, LoRA, QNN, Vulkan, OpenCL, and static executors as materials to test against the SoC. None is sacred.

## Core Thesis

The project started hardware-first and should remain hardware-first.

The phone is not a small server. It is a coupled physical computer. A training regime that ignores CPU/GPU/NPU asymmetry, memory residency, launch overhead, thermal stability, and battery/power behavior is not Polymath. It is ordinary fine-tuning squeezed onto a phone.

The current evidence says:

- The NPU path is physically real.
- The phone can run a large compiled transformer-shaped subgraph for hours.
- Static executor thinking is the right direction.
- The current authority gate is not yet met because the strongest Qwen frozen-middle run used random-init weights.

## Current State In One Paragraph

Polymath-AI already has a serious QNN/Hexagon lane: QAIRT 2.44 plus ai-edge-litert 2.1.4 compiled Qwen2.5-1.5B and SmolLM3 graph scopes to SM8750 artifacts, and the RedMagic 10 Pro ran QNN binaries on device under sustained load. However, D-033 showed that the deployed Qwen frozen-middle binary held random-init weights, so real language-model correctness is blocked until a real-weight recompile passes host-vs-phone cosine validation. In parallel, Gemma4 Kernel provides a cleaner static-executor/native-kernel lane, with CPU RMSNorm/matmul parity proven but no RedMagic OpenCL/Vulkan parity yet. The correct pivot is to reconcile these lanes, not to discard one for the other.

## What Is Actually Proven

### RedMagic / Phone

- Device is connected by ADB.
- Device: RedMagic 10 Pro / `NX789J`.
- SoC: QTI `SM8750`.
- OS: Android 15 / API 35.
- GPU: Adreno 830.
- Vulkan 1.3 compute support is present.
- OpenCL libraries are present.
- QAIRT 2.44 is installed under `/data/local/tmp/qairt-2.44`.
- Prior Qwen QNN artifacts exist under `/data/local/tmp/phase1a`.
- No current QNN/Polymath training process was running during inspection.

### QNN / Hexagon

Proven:

- QAIRT 2.44 plus ai-edge-litert 2.1.4 can compile SM8750 artifacts.
- The RedMagic can run those artifacts via `qnn-net-run --retrieve_context` and `libQnnHtp.so`.
- Sustained run evidence exists: 22,850 inferences over about 6h15m, 100% return-code success, mild thermal envelope.

Not proven:

- Real pretrained Qwen frozen-middle correctness on NPU.
- Phone-side training.
- Backward pass through a heterogeneous CPU/GPU/NPU training step.

Blocking issue:

- D-033: the Qwen frozen-middle binary used random-init weights, not real pretrained Qwen weights.
- Real-data host-vs-phone cosine validation failed around cosine 0.03.
- Pairwise phone outputs across different inputs were about 0.999 similar, consistent with random-init contraction / input-insensitive output.

### Gemma4 Kernel

Local path:

- `/Users/Zer0pa/Gemma4 Kernel`

Branch:

- `polymath-native-gemma4`

Proven:

- Native CPU kernel gate passes.
- RMSNorm/matmul forward/backward: 4 cases, 46 compared values, 0 failures.
- Static executor IR and memory plan exist.
- Bounded memory, device hints, frozen/trainable separation, and unbudgeted arena rejection are explicitly encoded.

Not proven:

- RedMagic OpenCL parity.
- RedMagic Vulkan parity.
- Gemma4 training.
- Gemma4 as final Polymath architecture.

## GitHub State

Local checkout:

- Path: `/Users/Zer0pa/Polymat AI/Polymath-AI`
- Branch: `main`
- Tracks: `origin/main`
- Dirty only through untracked local research docs.

Remote:

- Repo: `https://github.com/Zer0pa/Polymath-AI`
- Visibility: public
- Default branch: `main`

Important PRs:

- PR #4: `linux/phase0g-qairt-v2.43` -> `main`
  - Open and conflicting.
  - Contains QNN/phone proof, overnight run, D-033 random-init diagnosis, and phone scripts.
  - Must not be merged blindly.
- PR #7: `docs/g1-truth-sync-2026-05-07` -> `main`
  - Open and clean.
  - Documentation/front-door truth sync.

Important distinction:

- `main` has later packaging/public-status state.
- PR #4 has the richest QNN/phone engineering state.
- The pivot must reconcile both.

## RunPod State

Working SSH route:

```bash
ssh root@38.80.152.147 -p 31002 -i ~/.ssh/id_ed25519
```

Observed:

- `/workspace/Polymath-AI`
- `/workspace/qairt-2.43`
- `/workspace/qairt-2.44`
- `/workspace/qairt-v2.44.0.zip`
- `.venv-litert213` with Python 3.10.18, `torch 2.11.0+cpu`, `transformers 4.55.4`, `ai-edge-litert 2.1.4`, `ai-edge-torch 0.2.1`, `litert-torch 0.9.0`.

Critical state:

- Pod clone is stale at `6db6aa7`, before D-033 commit `e62e42c`.
- It does not currently contain the `PHASE0G_REAL_WEIGHTS=1` flag unless updated.
- Prior random-init AOT artifacts exist.
- Full Qwen pretrained weights were not observed in `/workspace/models`; real-weight recompile will need download/cache or explicit path.

## Hugging Face State

Auth:

- `hf auth whoami` reports `Architect-Prime`.
- Org membership includes `Zer0pa`.
- Token exists through normal HF cache; do not print or copy it.

Private repos observed:

- `Architect-Prime/polymath-corpus-seed-v0` dataset: README only.
- `Architect-Prime/polymath-telemetry` dataset: Phase 1A telemetry JSONL exists.
- `Architect-Prime/polymath-models-qwen2-5-1p5b-elo` model repo: README only.
- `Architect-Prime/polymath-models-smollm3-3b-elo` model repo: README only.
- `Architect-Prime/polymath-models-qwen2-5-1p5b-elo` dataset repo: contains Qwen AOT exports.
- `Architect-Prime/polymath-models-smollm3-3b-elo` dataset repo: contains SmolLM3 AOT exports.

Important:

- Large AOT artifacts are in private dataset repos with model-like names.
- The Qwen frozen-subgraph AOT wrapper exists at about 2.44 GB.
- These are still the random-init artifacts unless a later real-weight namespace is created.

## Main Authority Gate Now

The next hard gate is:

```text
real pretrained Qwen frozen-middle on phone NPU
vs
host PyTorch reference
with cosine-per-token p50 >= 0.99
```

Until that passes, the project must not claim real Qwen NPU correctness.

If it passes, QNN frozen-forward becomes a proven SoC primitive.

If it fails after real-weight recompile, the issue is deeper than random-init weights and may implicate AOT input handling, graph capture, layout, or backend lowering.

## Immediate Executor Sequence

Do this only after preserving current local state and deciding how to handle PR #4 conflicts.

1. Update RunPod clone.

```bash
cd /workspace/Polymath-AI
git fetch origin
git checkout linux/phase0g-qairt-v2.43
git reset --hard origin/linux/phase0g-qairt-v2.43
grep -n "PHASE0G_REAL_WEIGHTS" scripts/silicon/run_phase0g_aot.py
```

2. Confirm QAIRT/LiteRT environment.

```bash
cd /workspace/Polymath-AI
source .venv-litert213/bin/activate
python --version
python - <<'PY'
import importlib.metadata as m
for p in ["torch", "transformers", "ai-edge-litert", "ai-edge-torch", "litert-torch"]:
    print(p, m.version(p))
PY
```

3. Ensure real Qwen weights are available.

Use Hugging Face auth as `Architect-Prime`. Do not print token values.

4. Recompile only the authority target first.

```bash
cd /workspace/Polymath-AI
source .venv-litert213/bin/activate
export LD_LIBRARY_PATH=/workspace/qairt-2.44/qairt/2.44.0.260225/lib/x86_64-linux-clang:${LD_LIBRARY_PATH:-}
export PHASE0G_REAL_WEIGHTS=1
python scripts/silicon/run_phase0g_aot.py \
  --scope qwen_frozen_subgraph \
  --out-dir runtime/reports/export_probe/$(date -u +%Y%m%dT%H%M%SZ)_real_weights
```

5. Extract the QNN context.

```bash
python scripts/host/extract_qnn_context.py \
  --tflite <new_real_weight_apply_plugin.tflite> \
  --out /tmp/qwen_frozen_subgraph_real.qnn.bin
```

6. Preserve the old phone binary before replacement.

Do not overwrite the old random-init binary without preserving its checksum/name.

7. Deploy new binary to phone.

```bash
adb push /tmp/qwen_frozen_subgraph_real.qnn.bin /data/local/tmp/phase1a/qwen_frozen_subgraph.qnn.bin
```

8. Re-run Phase 1A.A.0 real-data comparison.

Use the existing host/phone scripts from PR #4:

- `scripts/host/phase1aa0_real_data.py`
- `scripts/phone/run_phase1aa0_real.sh`

Gate:

- cosine-per-token p50 >= 0.99.

## Gemma4 Kernel Import Plan

Do not overlay Gemma4 Kernel into Polymath root.

Import under:

```text
integrations/gemma4-kernel/
```

Use a history-preserving import after local untracked state is protected:

```bash
git -C "/Users/Zer0pa/Polymat AI/Polymath-AI" switch -c import/gemma4-kernel
git -C "/Users/Zer0pa/Polymat AI/Polymath-AI" remote add gemma4-kernel "/Users/Zer0pa/Gemma4 Kernel"
git -C "/Users/Zer0pa/Polymat AI/Polymath-AI" fetch gemma4-kernel polymath-native-gemma4
git -C "/Users/Zer0pa/Polymat AI/Polymath-AI" subtree add --prefix=integrations/gemma4-kernel gemma4-kernel polymath-native-gemma4
```

Import:

- `polymath_native/`
- `executor_ir/`
- `model_spec/`
- `docs/`
- `deferrals/`
- tracked `third_party_maps/` docs only
- `runtime/overnight/20260516T032712Z/native_kernel_gate.json`
- `ORCHESTRATOR_HANDOVER.md`

Exclude:

- build outputs
- `polymath_native/build`
- third-party source clones
- raw model/cache folders
- `.tflite`, `.litertlm`, `.task`, `.venv`, `node_modules`, `__pycache__`, probe dumps

## Things Not To Do

- Do not declare Qwen solved before real-weight cosine validation.
- Do not declare Gemma4 the final architecture.
- Do not merge PR #4 blindly into `main`.
- Do not overwrite phone binaries without preserving old checksums.
- Do not print or commit HF tokens.
- Do not vendor third-party clones or large model artifacts into git.
- Do not treat CPU native kernel parity as phone backend proof.
- Do not convert a failed or mixed gate into a success narrative.

## Thinking Questions For The Next Thread

The next thinking agent should reason about these before execution:

1. What is the minimal training-step wave that truly uses CPU, GPU, NPU, and memory according to their physical strengths?
2. Is QNN frozen-forward plus host/GPU backward a real training regime or only an inference accelerator?
3. Where should active token/sample selection live in the executor: before NPU scoring, after NPU scoring, or as a CPU control layer?
4. What must the static executor express so Qwen, Gemma4, LoRA, ELO, ZO, and future MoE hypotheses can compete under one authority metric?
5. What is the smallest authority metric that prevents reward hacking: cosine correctness, loss delta per joule, retention, thermal stability, or a tuple?
6. How should Gemma4 Kernel’s static executor lane intersect with the existing QNN lane without erasing either?
7. What would genuinely falsify the whole SoC-first thesis?

## Read Order For Fresh Agent

1. `docs/FRESH-CONTEXT-HANDOVER-2026-05-16-SOC-GEMMA4-PIVOT.md`
2. `docs/STATUS-2026-05-16-SOC-GEMMA4-PIVOT.md`
3. `docs/FRESH-CONTEXT-HANDOVER-SOC-ARCHITECTURE-V2.md`
4. `docs/CURRENT_PUBLIC_STATUS.md`
5. `docs/DECISIONS.md`
6. remote PR #4, especially D-030 through D-033
7. `/Users/Zer0pa/Gemma4 Kernel/ORCHESTRATOR_HANDOVER.md`
8. `/Users/Zer0pa/Gemma4 Kernel/docs/architecture/static_executor.md`

## One-Sentence Handover

Polymath has proven that the RedMagic SM8750 can sustain large QNN/Hexagon transformer-shaped forward execution, but the real language-model correctness gate is blocked by a random-init compiled binary; Gemma4 Kernel should now be imported as a static-executor/native-kernel integration lane while the next authority step recompiles Qwen frozen-middle with real weights and validates host-vs-phone cosine before any training claims.
