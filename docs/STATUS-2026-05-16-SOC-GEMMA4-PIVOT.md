# Status: SoC-First Pivot Across Polymath, Gemma4 Kernel, RunPod, Phone, and GitHub

Date: 2026-05-16

Boundary: Research infrastructure for in silico on-device LLM training and multilingual / multi-domain knowledge model construction. Outputs are research artifacts - model checkpoints, training telemetry, evaluation reports, throughput measurements. No regulatory certification claims. No clinical or human-subject use. No surveillance, biometric profiling, or identity inference. No model weights distributed without explicit license attestation. No training on copyrighted material without explicit corpus-license decomposition. No deployment to production without a falsifier-traced acceptance gate.

## Executive Status

The project is not at a model-selection moment. It is at a substrate-reconciliation moment.

Polymath started as a hardware-first hypothesis: the phone is not just a small server, it is a coupled physical computer with CPU, GPU, NPU, memory, storage, thermal, and power behavior that should determine the training regime. The existing Polymath branch work proves that this instinct was directionally right: the RedMagic SM8750 can run a large frozen transformer subgraph through Qualcomm QNN/Hexagon, and it can do so under sustained load.

The open falsifier is equally important: the compiled Qwen frozen-middle binary that ran on the phone used random-init weights. That means the NPU path is real, the sustained execution path is real, and the measurement harness is real, but the language-modeling path is not yet proven until a real-weight recompile passes host-vs-phone cosine validation.

Gemma4 Kernel adds a second, more disciplined executor laboratory: static memory, bounded arenas, CPU/GPU/NPU placement, and native kernel parity. It should be imported into Polymath as a namespaced integration lane, not overlaid into root. It is not a replacement for the Qwen/QNN lane. It is the right substrate for the next generation of executor thinking.

## Plain-Language Picture

The phone is the laboratory. The model is not the laboratory.

The old Polymath lane has already shown that the phone can load and repeatedly run a very large NPU computation. That is a major piece of evidence. But the computation was not yet the trained Qwen computation; it was Qwen-shaped random weights. So the road is open, but the destination was not reached.

The Gemma4 Kernel lane gives us a cleaner way to design the road itself. It asks where tensors live, when memory is allocated, which device owns which part of the work, and what must be proven before a backend gets trusted. This is closer to the original hardware-first idea than ordinary model fine-tuning.

## Technical Picture

The current system has four major evidence layers:

1. Polymath concept and harness
   - ELO / boundary-layer training is implemented and tested on host.
   - Scheduler, falsifier registry, audit chain, corpus policy, phone runbooks, and QNN export probes exist.
   - Remote PR #4 contains the richest phone/NPU evidence, but it is not merged to `main`.

2. QNN / Hexagon phone lane
   - QAIRT 2.44 plus ai-edge-litert 2.1.4 successfully produced SM8750 context binaries on RunPod.
   - The RedMagic 10 Pro ran QNN binaries via `qnn-net-run --retrieve_context` against `libQnnHtp.so`.
   - Sustained run: 22,850 inferences over 6h15m, 100% return-code success, mild thermal envelope.
   - Blocking falsifier: D-033 showed the deployed frozen-middle binary used random-init weights, causing real-data cosine validation to fail.

3. Gemma4 Kernel lane
   - Clean local repo on branch `polymath-native-gemma4`.
   - CPU native kernel gate passes: RMSNorm/matmul forward/backward, 4 cases, 46 compared values, 0 failures.
   - Static executor IR and memory plan enforce bounded memory, device hints, frozen/trainable state, and rejection of unbudgeted logits/attention.
   - OpenCL/Vulkan backends are skeletons only. No RedMagic OpenCL/Vulkan parity proof yet.

4. Live RunPod / phone state
   - RunPod TCP SSH works at `root@38.80.152.147 -p 31002`.
   - `/workspace/Polymath-AI` exists with QAIRT 2.44 and prior AOT artifacts.
   - That pod clone is stale relative to current PR #4: it stops at `6db6aa7`, before D-033 (`e62e42c`) introduced `PHASE0G_REAL_WEIGHTS=1`.
   - The connected phone is NX789J / SM8750 / Android 15 with QAIRT 2.44 installed under `/data/local/tmp/qairt-2.44` and existing Qwen QNN binaries under `/data/local/tmp/phase1a`.

## Current Authority Gates

| Gate | Current verdict | Evidence |
| --- | --- | --- |
| SoC identity | pass | RedMagic reports QTI SM8750, Android 15, arm64-v8a. |
| QNN compile path | pass for graph/op coverage | QAIRT 2.44 + ai-edge-litert 2.1.4 produced SM8750 binaries for five scopes. |
| QNN physical execution | pass for random-init compiled graphs | Phone ran QNN context binaries through Hexagon path. |
| Sustained NPU execution | pass for random-init inference loop | 22,850 inferences, 100% success, mild thermal envelope. |
| Real Qwen frozen-middle correctness | fail / blocked | D-033: binary held random-init weights; host-vs-phone cosine about 0.03. |
| Real-weight Qwen NPU forward | not yet proven | Requires real-weight recompile and cosine validation. |
| Backward/training through heterogeneous schedule | not yet proven | Requires forward proof first, then host/GPU/NPU training-step experiment. |
| Gemma4 native CPU kernel parity | pass | 4 cases, 46 compared values, 0 failures. |
| Gemma4 RedMagic OpenCL/Vulkan parity | not yet proven | Backends are skeletons. |
| Final model/architecture choice | not reached | Evidence supports substrate work, not final architecture selection. |

## GitHub / Branch Status

Local checkout:

- Path: `/Users/Zer0pa/Polymat AI/Polymath-AI`
- Branch: `main`
- Tracks: `origin/main`
- Status: no tracked modifications, but important untracked local research docs exist.

Remote:

- Repo: `https://github.com/Zer0pa/Polymath-AI`
- Visibility: public
- Default branch: `main`

Important PRs:

- PR #4: `linux/phase0g-qairt-v2.43` -> `main`
  - Open and conflicting.
  - Contains QNN/phone proof, overnight run, D-033 random-init diagnosis, and phone scripts.
  - Must not be merged blindly because it conflicts with later `main` packaging/public-status work and would delete some later files if applied as a simple branch replacement.
- PR #7: `docs/g1-truth-sync-2026-05-07` -> `main`
  - Open and clean.
  - Documentation/front-door truth sync.

Key conflict implication: the real engineering evidence is currently on PR #4, while the current public/default branch has later public-status and packaging state. The pivot must reconcile them.

## RunPod Status

Provided live pod:

- Pod ID: `ltg8fdnxgmzwjy`
- Working SSH route: `ssh root@38.80.152.147 -p 31002 -i ~/.ssh/id_ed25519`
- Proxy username route rejected the key during this inspection.

Observed `/workspace`:

- `/workspace/Polymath-AI`
- `/workspace/qairt-2.43`
- `/workspace/qairt-2.44`
- `/workspace/qairt-v2.44.0.zip`
- `/workspace/Polymath-AI/.venv-litert213`
- prior AOT artifacts under `runtime/reports/export_probe/2026-05-02T014031Z_litert214_qairt244_FULL/`

Important state:

- `.venv-litert213` has Python 3.10.18, `torch 2.11.0+cpu`, `transformers 4.55.4`, `ai-edge-litert 2.1.4`, `ai-edge-torch 0.2.1`, and `litert-torch 0.9.0`.
- QAIRT 2.44 includes host and Android QNN binaries/libraries, including `libQnnSystem.so`, `libQnnHtp.so`, `qnn-net-run`, and HTP V75/V79/V81 stubs.
- The pod clone is behind the latest remote branch and lacks D-033 real-weight flag code until updated.
- `/workspace/models` does not contain Qwen weights; it contains unrelated RFdiffusion assets. Real-weight recompile will need Hugging Face model download/cache or explicit model path.

## Hugging Face Status

Local authentication:

- `hf auth whoami` reports `Architect-Prime`, with org membership in `Zer0pa`.
- HF token is available through the normal Hugging Face cache. No token value was printed or copied.
- No relevant `.env` file was found under `/Users/Zer0pa/Polymat AI` during shallow search. Other unrelated `.env.local` / `.env.example` files exist elsewhere under `/Users/Zer0pa`.

Private repos observed:

| Repo | Type | Status |
| --- | --- | --- |
| `Architect-Prime/polymath-corpus-seed-v0` | dataset | Exists; only `.gitattributes` and `README.md`. |
| `Architect-Prime/polymath-telemetry` | dataset | Exists; contains Phase 1A audit JSONL telemetry from 2026-05-02. |
| `Architect-Prime/polymath-models-qwen2-5-1p5b-elo` | model | Exists; model-type repo only has `.gitattributes` and `README.md`. |
| `Architect-Prime/polymath-models-smollm3-3b-elo` | model | Exists; model-type repo only has `.gitattributes` and `README.md`. |
| `Architect-Prime/polymath-models-qwen2-5-1p5b-elo` | dataset | Exists; contains Qwen AOT export artifacts. |
| `Architect-Prime/polymath-models-smollm3-3b-elo` | dataset | Exists; contains SmolLM3 AOT export artifacts. |

Important artifact locations:

- Qwen dataset repo:
  - `exports/qwen-aot/2026-05-02/tiny_block/tiny_block_Qualcomm_SM8750_apply_plugin.tflite`
  - `exports/qwen-aot/2026-05-02/qwen_block/qwen_block_Qualcomm_SM8750_apply_plugin.tflite`
  - `exports/qwen-aot/2026-05-02/qwen_frozen_subgraph/qwen_frozen_subgraph_Qualcomm_SM8750_apply_plugin.tflite` (~2.44 GB)
- SmolLM3 dataset repo:
  - `exports/smollm3-aot/2026-05-02/smollm3_block/smollm3_block_Qualcomm_SM8750_apply_plugin.tflite`
  - `exports/smollm3-aot/2026-05-02/smollm3_frozen_subgraph/smollm3_frozen_subgraph_Qualcomm_SM8750_apply_plugin.tflite` (~1.01 GB)

Interpretation: the large AOT artifacts were pushed, but into private dataset repos with model-like names, not into the HF model repos. They are still the random-init artifacts described by D-033 unless a later real-weight export is created under a new date/run namespace.

## Phone Status

Connected device:

- Model: RedMagic 10 Pro / `NX789J`
- SoC: QTI SM8750
- Android: 15 / API 35
- ABI: `arm64-v8a`
- GPU: Adreno 830 with Vulkan 1.3 compute and OpenCL libraries present.
- Current health snapshot during inspection: AC powered, battery about 73-75%, battery temp about 22-23 C, RAM and storage healthy.

Existing phone artifacts:

- `/data/local/tmp/qairt-2.44` contains QAIRT/QNN runtime.
- `/data/local/tmp/phase1a` contains:
  - `qwen_block.qnn.bin`
  - `qwen_frozen_subgraph.qnn.bin`
  - `qwen_block_sm8750.tflite`
  - prior outputs/profiling directories
- `/sdcard/Polymath/phase1a` contains prior runner scripts, audit logs, status, and STOP marker.
- No current QNN/Polymath process was running during inspection.

Important caution: `/sdcard/Polymath/.hf-token` exists and must not be printed, copied into git, or included in any artifact.

## Gemma4 Kernel Status

Local path:

- `/Users/Zer0pa/Gemma4 Kernel`
- Branch: `polymath-native-gemma4`
- Commits:
  - `34bc98c Add orchestrator handover for native Gemma 4 lane`
  - `449cf7e Initialize native Gemma 4 REDMAGIC runtime research lane`
- No remote configured at inspection time.

What is valuable:

- `polymath_native/`: native C++ CPU parity lab, CMake, tests, OpenCL/Vulkan skeletons, telemetry schema.
- `executor_ir/`: static executor schema and Gemma4 E2B tiny-block train-step example.
- `model_spec/`: Gemma4 E2B/E4B model facts.
- `docs/`: PRD, architecture, decisions, research, overnight summary.
- `deferrals/`: RedMagic, RunPod, Rampard/QAIRT packets.
- `runtime/overnight/20260516T032712Z/native_kernel_gate.json`: committed CPU proof.

What must be excluded from import:

- build outputs
- `polymath_native/build`
- third-party source clones
- raw model/cache folders
- `.tflite`, `.litertlm`, `.task`, `.venv`, `node_modules`, `__pycache__`, probe dumps

Recommended import namespace:

- `integrations/gemma4-kernel/`

Do not overlay into Polymath root. Root overlay would collide conceptually with `docs/`, `runtime/`, and `scripts/`, even though exact tracked path collision is currently minimal.

## What This Changes

The older Polymath lane proves that the NPU/Hexagon path is not fantasy. The phone can run a large compiled transformer-shaped subgraph for hours.

The D-033 failure proves that graph shape is not enough. The authority metric must be semantic correctness against real pretrained weights, not successful binary execution.

The Gemma4 Kernel lane gives us the missing discipline for the next step: static executor, explicit memory, bounded arenas, and backend-specific parity before claims. It should become the executor design lane inside Polymath.

The combined path is:

1. Preserve and reconcile PR #4 evidence.
2. Update the live RunPod clone to include D-033 real-weight flag code.
3. Recompile Qwen frozen-middle with real weights.
4. Extract the real-weight QNN context binary.
5. Deploy it to the phone.
6. Re-run host-vs-phone cosine validation.
7. Only if that passes, reopen the training-step question.
8. Import Gemma4 Kernel as an integration lane for static-executor/native-backend evolution.

## Immediate Pivot Plan

Do not choose a final model yet. Do not declare Gemma4 the replacement model. Do not declare Qwen solved. The near-term pivot is evidence reconciliation plus executor unification.

1. Protect current local state
   - Preserve untracked local V2 handover/research docs.
   - Do not overwrite them with PR #4 or Gemma4 import.

2. Reconcile GitHub PR #4
   - Create a new integration branch from current `main`.
   - Cherry-pick or merge the useful PR #4 commits while preserving `main` packaging/public-status files.
   - Drop or move large accidental artifacts such as `runtime/reports/phase1aa0/.../.d033_patch_backup.patch` before merge unless explicitly needed as evidence outside git.

3. Re-arm RunPod
   - Fetch/pull the current remote PR #4 branch on the pod.
   - Confirm `PHASE0G_REAL_WEIGHTS=1` exists in `scripts/silicon/run_phase0g_aot.py`.
   - Confirm the QAIRT 2.44 environment still works.
   - Confirm or populate the Qwen2.5-1.5B pretrained weights cache.

4. Re-run the real-weight authority gate
   - Compile only `qwen_frozen_subgraph` first.
   - Extract QNN context.
   - Deploy to `/data/local/tmp/phase1a/qwen_frozen_subgraph.qnn.bin` on phone only after preserving the old random-init binary by name or checksum.
   - Run `phase1aa0_real_data.py` compare.
   - Gate is cosine-per-token p50 >= 0.99, or a named falsifier.

5. Import Gemma4 Kernel
   - Use subtree or equivalent history-preserving import under `integrations/gemma4-kernel/`.
   - Keep generated/third-party/model artifacts excluded.
   - Treat Gemma4 CPU parity as a local proof, not phone backend proof.

6. Write the next architecture note after evidence, not before
   - If real-weight Qwen passes, the QNN frozen-forward island becomes a proven primitive.
   - If it fails, the static executor/Gemma4/native path becomes more central.
   - In either case, the final training regime remains SoC-first and authority-metric-driven.

## Key Non-Claims

- We do not yet have proven phone-side training.
- We do not yet have proven real-weight Qwen frozen-middle correctness on NPU.
- We do not yet have Gemma4 OpenCL/Vulkan parity on RedMagic.
- We do not yet have a final Polymath architecture.
- We do not yet know that Gemma4, Qwen, MoE, dense, LoRA, ELO, or another regime is final.
- We do know that the phone/NPU path is physically real enough to deserve the next authority gate.

## Files And Evidence Anchors

- `docs/DECISIONS.md`
- `docs/CURRENT_PUBLIC_STATUS.md`
- `docs/FRESH-CONTEXT-HANDOVER-SOC-ARCHITECTURE-V2.md`
- `runtime/reports/export_probe/2026-05-02T014031Z_litert214_qairt244_FULL/`
- `runtime/reports/phase1a/2026-05-02T1802Z-overnight-v2/`
- remote branch `origin/linux/phase0g-qairt-v2.43`
- PR #4: `Phase 0G UNBLOCKED + Phase 1A on-device QNN inference proven on Hexagon NPU (SM8750)`
- `/Users/Zer0pa/Gemma4 Kernel/ORCHESTRATOR_HANDOVER.md`
- `/Users/Zer0pa/Gemma4 Kernel/docs/architecture/static_executor.md`
- `/Users/Zer0pa/Gemma4 Kernel/runtime/overnight/20260516T032712Z/native_kernel_gate.json`
