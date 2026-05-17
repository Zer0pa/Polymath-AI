# Phase 07: Integrated Training Remediation - Research

**Researched:** 2026-05-17
**Domain:** Phone-native Gemma 4 training runtime, token-to-hidden bridge, adapter update validation
**Confidence:** HIGH for the G8 remediation path; MEDIUM for post-correctness backend optimization candidates.

## User Constraints

- Write scope for this research pass is this file only: `.gpd/phases/07-integrated-training/07-RESEARCH.md`.
- The sovereign gate is not throughput, SDK integration, or a clean local test. It is a REDMAGIC SM8750 phone-native Gemma 4 training update from phone-streamed text through phone checkpoint/adapters.
- Mac remains control plane only. RunPod remains build/reference oracle only. Neither may serve runtime tokenization, batches, hidden states, gradients, optimizer updates, or checkpoint writes.
- G8 is falsified until the phone runtime derives `layer_input` and per-layer `per_layer_input` tensors from phone-packed `input_ids`. `layer_input.f32.bin`, `per_layer_input.f32.bin`, `layer0_output.f32.bin`, and `layer1_output.f32.bin` from RunPod are oracle outputs only.
- Do not mutate frozen base Gemma tensors. The current trainable substrate remains the rank-4 post-layer0 residual adapter unless a later PRD amendment changes scope.
- G1 and G3 remain regression floors after material runtime changes. A G8 repair that regresses them fails.
- External SDK/compiler documentation cited below is research input only. It cannot replace the phone authority gate or promote a run without phone artifacts.
- No phase `*-CONTEXT.md` or project `.gpd/research/SUMMARY.md`, `METHODS.md`, or `PITFALLS.md` exists in this repo snapshot; this research builds from `.gpd/STATE.md`, `.gpd/ROADMAP.md`, `.gpd/REQUIREMENTS.md`, the G8 falsifier report, and the authority PRD.

## Active Anchor References

| Anchor / Artifact | Type | Why It Matters Here | Required Action | Where It Must Reappear |
| --- | --- | --- | --- | --- |
| `.gpd/STATE.md` | State | Declares current blocker: G8 hidden-host-data-path falsifier. | Keep blocker language exact. | PLAN, gate result, falsifier report |
| `.gpd/ROADMAP.md` | Roadmap | Phase 7 pass requires streamed-corpus batch, update, artifact, stable frozen hashes, no hidden host path. | Plan only work that closes these criteria. | PLAN success criteria |
| `.gpd/REQUIREMENTS.md` | Requirements | `DATA-04`, `TRN-01`, `TRN-02`, and `FALS-01` define decisive outputs. | Map every task to one of these requirements. | PLAN traceability |
| `docs/PRD-GEMMA4-SNAPDRAGON-MEGAKERNEL-HETEROGENEOUS-TRAINING.md` | Authority PRD | Defines topology: phone runtime, RunPod oracle, Mac control plane. | Treat as binding. | All G8 reports |
| `runtime/reports/gemma4_megakernel/integrated_training/20260517T040000Z_g8_streamed_corpus_falsified/gate_result.json` | Falsifier | Explains exactly why G8 failed. | Repair only the token-to-hidden gap before claiming training. | PLAN blocker resolution |
| `runtime/reports/gemma4_megakernel/phone_data_pipeline/20260517T040000Z_g7_hf_native_token_pack/gate_result.json` | Passed prerequisite | Phone stream/tokenize/pack path passed exact token and mask parity. | Reuse as data source; extend ABI, do not replace. | Batch manifest |
| `runtime/reports/gemma4_megakernel/backward_path/20260517T040000Z_g5_rank4_adapter_opencl/gate_result.json` | Passed prerequisite | Adapter gradient path exists and passed RunPod PyTorch comparison. | Reuse kernels and comparison harness. | Gradient/update report |
| `runtime/reports/gemma4_megakernel/optimizer_update/20260517T040000Z_g6_rank4_adapter_sgd/gate_result.json` | Passed prerequisite | Phone-side SGD update and hash behavior already passed for fixtures. | Reuse update/checkpoint substrate after replacing fixtures. | Checkpoint manifest |
| Hugging Face Transformers Gemma4 docs: `https://huggingface.co/docs/transformers/model_doc/gemma4` | Official docs | Documents PLE inputs and Gemma4 forward contract. | Use for formula parity only; not phone evidence. | Tensor bridge design |
| HF Gemma4 docs source: `https://github.com/huggingface/transformers/blob/main/docs/source/en/model_doc/gemma4.md` | Official source docs | States PLE token-identity and context-aware components. | Use as implementation reference, verify against pinned model revision. | Reference generator |
| Hugging Face Datasets streaming docs: `https://huggingface.co/docs/datasets/en/stream` | Official docs | Supports direct streaming model used by G7. | Keep as data pipeline reference only. | Data provenance |
| Hugging Face Hub env docs: `https://huggingface.co/docs/huggingface_hub/en/package_reference/environment_variables` | Official docs | Token/cache env handling; avoid token leaks. | Use for phone auth hygiene. | Commands/log redaction |
| Android NDK Thermal API: `https://developer.android.com/ndk/reference/group/thermal` | Official docs | Native thermal status/headroom APIs. | Use for sustained cadence after correctness. | G9 telemetry |
| Qualcomm AI Engine Direct SDK: `https://www.qualcomm.com/developer/software/qualcomm-ai-engine-direct-sdk` | Official docs | QNN/AI Engine Direct abstraction context. | Research only; not G8 backend proof. | Optimization backlog |
| Qualcomm AI Hub docs: `https://app.aihub.qualcomm.com/docs/hub/index.html` | Official docs | Compile/profile/inference job reference. | Research only; do not substitute for local phone gate. | Optimization backlog |
| ExecuTorch Qualcomm backend: `https://docs.pytorch.org/executorch/stable/backends-qualcomm.html` | Official docs | Documents Qualcomm AI Engine Direct / Hexagon delegation path. | Candidate analogue for frozen-forward islands only. | Optimization backlog |
| IREE Vulkan docs: `https://iree.dev/guides/deployment-configurations/gpu-vulkan/` | Official docs | Vulkan deployment and Android/Adreno support expectations. | Candidate scheduling reference only. | Backend comparison plan |
| TVM Adreno docs: `https://tvm.apache.org/docs/v0.12.0/how_to/deploy/adreno.html` | Official docs | Adreno OpenCL layout/texture/OpenCLML ideas. | Mine scheduling ideas after OpenCL correctness. | Optimization backlog |
| MLC LLM docs: `https://llm.mlc.ai/docs/get_started/introduction.html` | Official docs | Mobile/Vulkan LLM deployment analogue. | Research input only. | Optimization backlog |
| Hexagon-MLIR arXiv: `https://arxiv.org/abs/2602.19762` | Paper | MLIR path for Qualcomm Hexagon NPU; work-in-progress. | Research only; not a G8 authority route. | Future NPU notes |
| LoRA paper: `https://arxiv.org/abs/2106.09685` | Paper | Justifies adapter-only trainable scope conceptually. | Cite; do not re-derive. | Training scope rationale |

**Missing or weak anchors:** No project-level research summary files are present. There is also no promoted G8 artifact manifest because the attempt failed under falsification; planners must not treat the failed run as a partial pass.

## Mathematical Framework

### Runtime Tensor Contract

The valid G8 runtime path is:

```text
HF raw text -> phone curl/stream -> native Gemma BPE -> UFS token cache
-> phone input_ids/attention_mask/position_ids/labels/loss_mask
-> phone Gemma embedding + PLE generation
-> phone OpenCL layer0/layer1
-> phone adapter backward/update
-> phone checkpoint or adapter manifest
```

The first remediation is not a new optimizer. It is a new phone-native bridge from token cache to the tensors already consumed by the OpenCL layer runner.

### Key Equations And Starting Points

| Quantity | Prescriptive Formula / Contract | Source | Role |
| --- | --- | --- | --- |
| Position IDs | `position_ids = max(cumsum(attention_mask) - 1, 0)` per row. | Existing `create_e4b_layer0_reference.py` | Reproduce RunPod/HF fixture semantics for left-padded rows. |
| Labels for NLL | `labels[t] = input_ids[t+1]`; `loss_mask[t] = attention_mask[t] & attention_mask[t+1]`; last position masked. | Standard causal LM labeling; HF CausalLM labels docs | Extend G7 ABI without forcing NLL as first objective. |
| Main embedding | `layer_input[b,s,:] = embed_tokens[input_ids[b,s],:] * embed_scale_main`. | HF Gemma4 scaled embedding source/docs | Replace hidden fixture `layer_input.f32.bin`. |
| PLE token-identity | `token_ple_l = embed_tokens_per_layer[input_ids, l_slice] * sqrt(hidden_size_per_layer_input)`. | HF Gemma4 PLE docs | Per-layer input component for layers 0 and 1. |
| PLE context-aware | `ctx_ple_l = RMSNorm((layer_input @ projection_l^T) * hidden_size^-0.5, ple_norm_weight, eps=1e-6)`. | HF Gemma4 PLE docs | Required; token-only PLE is incomplete. |
| Final PLE | `per_layer_input_l = (token_ple_l + ctx_ple_l) * 2^-0.5`. | HF Gemma4 PLE docs | Feed existing layer runner's `per_layer_input` for layer `l`. |
| Layer forward | Existing OpenCL runner consumes `layer_input`, `per_layer_input`, mask, positions, and layer safetensors. | Local `opencl_layer_runner.cpp` | Reuse, after replacing file-source hidden fixtures. |
| Adapter objective | `z = h0 A`; `out = h0 + (1/r)(z B)`; masked half-MSE to stop-gradient target. | Existing G5/G6 implementation; LoRA paper | Minimal valid training update after phone h0/h1 exist. |

### Asset Slices Required On Phone

Export these as frozen model assets with hashes and model revision, not as runtime data:

- `embed_tokens.weight` plus the exact main embedding scale used by the pinned HF implementation.
- `embed_tokens_per_layer.weight` slices for layers 0 and 1 only: columns `[l * 256, (l + 1) * 256)`.
- `per_layer_model_projection.weight` slices for layers 0 and 1 only: rows `[l * 256, (l + 1) * 256)`.
- `per_layer_projection_norm.weight` and `rms_norm_eps`.
- Existing layer0/layer1 safetensors and adapter checkpoint tensors.

Prefer sliced assets for G8. Full PLE embedding across all 42 layers is much larger than the two-layer gate needs and increases UFS/memory risk without improving correctness.

## Standard Approaches

### Approach 1: Bridge-First Two-Layer Distillation (Recommended)

**What:** Generate `layer_input`, `per_layer_input_0`, and `per_layer_input_1` on the phone from G7 `input_ids`; run phone OpenCL layer0 and layer1; treat the phone-produced layer1 output as a stop-gradient target for the existing rank-4 post-layer0 adapter update.

**Why this is the right next gate:** It directly removes the falsifier while reusing the proven G5/G6 adapter math and G3 two-layer forward path. It avoids introducing a memory-bounded vocabulary projection before the phone data path is clean.

**Implementation sequence:**

1. Extend the token cache ABI with `position_ids.u32.bin`, `labels.u32.bin`, and `loss_mask.u8.bin`; keep manifest hashes for all files.
2. Add a `TokenHiddenBridge` or equivalent component that reads phone cache files and frozen model assets, then emits phone-generated tensors with provenance.
3. Add OpenCL kernels or CPU-on-phone diagnostic code for BF16 row gather and PLE generation. CPU-on-phone may be a diagnostic bridge only if clearly labeled; an Adreno gate requires OpenCL/Vulkan for the claimed backend work.
4. Refactor the layer runner so `layer_input` and `per_layer_input` can come from the bridge in memory or from a phone-generated cache directory, not from RunPod layer-pack fixture inputs.
5. Run layer0/layer1 from phone-generated tensors and compare against RunPod PyTorch oracle outputs for the same selected texts.
6. Feed phone-generated `h0` and phone-generated stop-gradient `h1` into the adapter update path; write adapter checkpoint, loss trace, trainable/frozen hashes, and replay manifest.
7. Rerun G1 and G3 before any G8 promotion.

**Switch criteria:** If the bridge passes token-to-hidden parity but distillation is challenged as too indirect for the training objective, keep the same bridge and move to Approach 2. Do not discard the bridge work.

### Approach 2: Chunked Tied-Embedding Next-Token NLL (Next Correctness Expansion)

**What:** Use `labels` and `loss_mask` from the extended G7 ABI; compute next-token NLL using tied `embed_tokens.weight`/LM head in chunks so full `[B*S, vocab]` logits are never materialized.

**When to use:** After Approach 1 proves the phone runtime consumes real streamed text through embedding/PLE/forward/backward/update/checkpoint. This is the more semantically direct language-model training objective.

**Key constraints:** The vocabulary is 262144 and hidden is 2560 for E4B; full logits are a memory trap. Use vocabulary chunks, streaming log-sum-exp, and masked token loss. Preserve exact label masking so pad tokens cannot inflate metrics.

### Anti-Patterns To Avoid

- Promoting G8 by copying `layer_input.f32.bin` or `per_layer_input.f32.bin` from RunPod into the phone runtime.
- Generating hidden tensors on Mac and pushing them to the phone under a new filename.
- Implementing only `embed_tokens` and omitting Gemma4 PLE context projection.
- Treating QNN, AI Hub, ExecuTorch, IREE, TVM, or MLC success as phone training proof.
- Running optimizer or checkpoint serialization on RunPod because it is easier to inspect.
- Reporting throughput/thermal wins before correctness and artifact replay are green.

## Existing Results To Leverage

| Result | What It Gives | How To Use |
| --- | --- | --- |
| G1 layer0 OpenCL gate | Real-weight E4B layer0 parity and command path. | Permanent regression after bridge changes. |
| G3 two-layer OpenCL stack | Existing layer0->layer1 phone forward substrate. | Reuse once layer inputs are phone-generated. |
| G5 rank-4 adapter backward | Gradient kernels and RunPod comparison harness. | Reuse math and comparator; replace hidden fixture source. |
| G6 adapter SGD update | Trainable mutation, frozen hash stability, checkpoint write substrate. | Reuse for first phone-generated update. |
| G7 phone token cache | Phone-native HF stream, tokenization, UFS pack, exact ID/mask parity. | Extend ABI; do not rebuild from scratch. |
| HF Gemma4 PLE docs | Exact PLE component structure. | Implement token-identity + context-aware PLE. |
| Existing C++ runner interfaces | `TensorStore`, `BackendExecutor`, `Tokenizer`, `SequencePacker`, `CheckpointStore`, `TrainingStepExecutor`. | Add the bridge without decorative architecture drift. |
| Existing comparators | Token cache, layer output, adapter training comparisons. | Add token-to-hidden and PLE comparison reports. |

## Don't Re-Derive

- Do not re-derive LoRA/adapter theory. The current rank-4 adapter substrate has already passed gradient/update gates; cite LoRA and use the local G5/G6 formulas.
- Do not re-derive the Hugging Face streaming/tokenization route. G7 already passed exact token and mask parity.
- Do not re-derive Gemma4 PLE from observed tensors. Use the HF Gemma4 PLE docs and verify numerically against the pinned model revision.
- Do not re-derive OpenCL layer0/layer1 correctness. Rerun G1/G3 as regression gates after the bridge.
- Do not re-derive thermal APIs, QNN/AI Engine Direct semantics, or IREE/TVM/MLC compiler models during G8 remediation. They are post-correctness research inputs.

## Common Pitfalls

| Pitfall | Why It Fails | Prevention |
| --- | --- | --- |
| Hidden tensor laundering | Same falsifier under a new file path. | Manifest runtime inputs must start from token cache and frozen model assets only. |
| PLE token-only implementation | Gemma4 PLE also includes context projection from main embeddings. | Compare `per_layer_input_0/1` against RunPod oracle before layer forward. |
| Wrong scale precision | Gemma4 scaled embeddings can be sensitive to exact scalar/dtype behavior. | Export scale values in the asset manifest; compare embedding rows directly. |
| Wrong PLE slice axis | Token PLE slices are packed by layer; projection slices are rows by layer. | Add shape checks and layer-indexed hash entries. |
| Position mismatch on left padding | RoPE phases drift and attention parity collapses. | Generate `position_ids` from `attention_mask` with the existing reference formula. |
| Pad-token metric inflation | Masked rows make cosine/loss look better than real tokens. | Report non-pad counts, failed non-pad tokens, and loss_mask counts. |
| CPU fallback ambiguity | PRD allows CPU orchestration, not CPU masquerading as Adreno gate. | Telemetry must declare backend per operation. |
| Frozen weight mutation | Invalidates adapter-only claim. | Hash all frozen assets before and after update. |
| Checkpoint write without replay | Artifact may be corrupt or unreproducible. | Re-open checkpoint, verify hashes, replay one validation step. |
| Optimization before correctness | Can hide falsifier with better-looking performance. | Freeze docs/handover claims until G8 gate is green. |

## Validation Strategies

| Gate | Validation | Expected Result |
| --- | --- | --- |
| ABI extension | Read G7 cache and verify `input_ids`, `attention_mask`, `position_ids`, `labels`, `loss_mask` sizes and hashes. | Deterministic replay; no token/mask regression. |
| Embedding gather | Compare phone-generated `layer_input` against RunPod HF captured `inputs_embeds`/layer0 pre-hook for same texts. | Non-pad cosine near existing G1/G3 tolerance; investigate any systematic scale drift. |
| PLE generation | Compare `per_layer_input_0` and `per_layer_input_1` against RunPod HF captured PLE slices. | No shape/slice mismatch; finite values; high non-pad cosine. |
| Layer0 forward | Run layer0 from phone-generated tensors. | Matches RunPod oracle; G1 still green. |
| Layer1 forward | Run layer1 with phone `h0` and phone-generated `per_layer_input_1`. | Matches RunPod oracle and preserves G3-style two-layer parity. |
| Adapter update | Train adapter using phone `h0`, phone stop-gradient `h1`, and phone mask. | Finite loss/gradients; trainable hashes change; frozen hashes stable. |
| Runtime provenance | Inspect command logs and artifact manifest. | No RunPod/Mac hidden tensors in runtime input set. |
| Replay | Re-read adapter checkpoint and rerun validation step. | Hashes match manifest; replay loss/comparator is deterministic where expected. |
| Regression | Rerun G1/G3 after bridge and training changes. | No correctness regression. |
| Falsifier precheck | Run G10-style checks focused on wrong revision, fallback, pad inflation, hidden host path, frozen mutation, checkpoint replay. | No unresolved critical issue before G8 promotion. |

Required reports for the repaired G8 run:

- `gate_result.json` with explicit `status`.
- `commands.log` with redacted secrets and source-node annotations.
- `artifact_manifest.json` listing runtime inputs, frozen assets, generated tensors, trainable outputs, and hashes.
- `device_manifest.txt`.
- `batch_manifest.json` for G7 cache files and ABI extension.
- `token_to_hidden_compare.json`.
- `layer_forward_compare.json`.
- `adapter_update_compare.json`.
- `telemetry.json` with backend declarations and RSS/thermal/storage basics.
- `blockers.md`, even if empty.

## Caveats And Alternatives

- The two-layer distillation objective is a valid minimal G8 repair only if every tensor in the training step is phone-produced from streamed tokens or frozen model assets. It is not a substitute for G9 sustained training.
- A phone CPU diagnostic bridge can accelerate debugging, but it cannot satisfy an Adreno/OpenCL/Vulkan backend claim unless the gate explicitly labels it as diagnostic and then reruns on the claimed backend.
- If PLE parity fails, first suspect scale dtype, slice orientation, RMSNorm epsilon, and left-padding position IDs before touching layer kernels.
- If memory pressure blocks full `embed_tokens.weight` use, a token-row asset subset may be acceptable only if it is declared as a frozen model asset for the fixed streamed slice, hashed, and falsifier-approved as not runtime hidden data.

## Bespoke Snapdragon/Gemma4 Optimization Candidates To Test After Correctness

These are deliberately after G8 correctness. None may be used to promote the phone authority claim by itself.

| Candidate | Test After Correctness | What To Measure | Research Inputs |
| --- | --- | --- | --- |
| Memory allocator and UFS layout | Use sliced layer0/1 PLE assets, mmap/read-only frozen weights, aligned shard files, and a unique-token row cache for embedding gathers. | RSS high-water, UFS read latency, page faults, checkpoint write latency. | PRD UFS requirement; HF Hub cache/env docs |
| Adreno OpenCL scheduling | Fuse row gather + scale where safe; batch PLE projection per unique token; tune workgroups for `B*S x H` and `B*S x 256`; avoid extra host/device copies. | Kernel time, dispatch count, buffer bytes, cosine stability. | Existing OpenCL runner; TVM Adreno OpenCL docs |
| Vulkan/IREE route | Prototype only after OpenCL bridge passes; compare SPIR-V/Vulkan dispatch overhead and memory behavior against OpenCL. | Same correctness comparators first, then latency/RSS. | IREE Vulkan docs; MLC LLM Android/Vulkan docs |
| Thermal-aware cadence | Add native `AThermal_*` polling/callbacks, KGSL/GPU clock snapshots, and pause/resume policy before G9. | Thermal status/headroom, throttling events, loss continuity after cooldown. | Android NDK Thermal API |
| Optimizer and checkpoint serialization | Keep adapter/optimizer state phone-local; write temp files, fsync, atomic rename, manifest hash, replay readback. | Checkpoint corruption rate, write time, replay determinism. | Existing G6 checkpoint substrate |
| Chunked tied-embedding NLL | Stream vocabulary chunks through tied embedding/LM head; log-sum-exp over chunks; masked next-token loss. | Peak memory, NLL parity, gradient finite checks. | HF Gemma4 CausalLM labels contract |
| QNN/Hexagon/ExecuTorch | Consider frozen-forward or recompute islands only; no backward assumption. | Correctness parity before speed; offload boundary copy cost. | Qualcomm AI Engine Direct, ExecuTorch Qualcomm backend, Hexagon-MLIR |
| Qualcomm AI Hub | Use for compile/profile reconnaissance only, not runtime evidence. | Candidate op support and profiling hints. | Qualcomm AI Hub docs |
| TVM/MLC analogues | Mine Adreno layouts, Vulkan dispatch, and compiler scheduling ideas; do not import their runtime as proof. | Whether generated schedules beat hand kernels after identical gate checks. | TVM Adreno docs; MLC LLM docs |
