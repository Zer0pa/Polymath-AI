# Heterogeneous SoC Research Dialogue

**Status:** living document  
**Started:** 2026-05-16  
**Role:** shared research notebook for operator + orchestrator  
**Boundary:** research infrastructure for on-device AI workloads and training systems. No production, clinical, surveillance, biometric, identity-inference, or unlicensed-corpus claims.

## Purpose

This document records the evolving scientific conversation around using RedMagic 10 Pro Plus class phones as heterogeneous AI computers.

The RedMagic is the archetype, not the boundary. The target class is a phone-scale system-on-chip with CPU, GPU, NPU, unified memory, large local storage, strong thermal handling, and enough operational control to run hours-to-days experiments.

The objective is not to show that a model can run on a phone. That is a demo. The objective is to discover and engineer the natural AI workload shape for this kind of machine.

## Governing Objective

Copy the best-known heterogeneous mobile compute patterns, reproduce them on the RedMagic-class setup, then push beyond them into training-oriented workload shapes.

The work should proceed as long-horizon experimentation, not user-facing status theater. Tests are not reports. Tests are steering signals. An agent that finds a failed path should pivot, preserve the hypothesis, and continue toward the authority metric.

## Resistance Discipline

This line of work is especially exposed to `fp-demogravity`: running a model, producing a benchmark, and calling that the project.

Forbidden collapses:

- Treating phone inference as evidence of training viability.
- Treating QNN execution as evidence of language-model correctness.
- Treating local latency wins as evidence of system-level energy-to-quality improvement.
- Treating a scheduler scaffold as a scheduler.
- Treating a report as progress before the measured object exists.
- Softening the objective into "we used CPU/GPU/NPU" instead of proving the heterogeneous layout improved the authority metric.

Resistance V2 applies: local green is not truth; realism means calibrated maximalism; the governing objective is sovereign.

## Current Scientific Frame

A RedMagic-class phone is not a weak laptop. It is a coupled physical computer:

| Substrate | Natural role |
|---|---|
| CPU | control plane, scheduling, optimizer state, fallback, bookkeeping, host-language glue |
| GPU / Adreno | flexible FP compute, unsupported ops, outlier work, custom OpenCL/Vulkan kernels, maybe backward sidecars |
| NPU / Hexagon | fixed-shape dense compiled inference islands, stable transformer blocks, high-throughput low-energy kernels |
| Unified memory | shared substrate and bottleneck; eliminates PCIe but makes contention central |
| UFS storage | cold weight reservoir, checkpoint stream, corpus/model shard store |
| Fan / thermal system / fridge / charge bypass | part of the compute substrate, not environment noise |

The classical forward/backward pass does not disappear mathematically. Physically, it becomes a scheduled flow through these resources.

The research question is: **what learning algorithm becomes natural when the phone is treated as a heterogeneous physical computer rather than as a small cloud GPU?**

## Iteration 2026-05-16: Forward/Backward Becomes Asymmetric

Two research missions were run:

1. What does forward/backward become on a heterogeneous phone SoC?
2. What is the physical compute envelope of a RedMagic 10 Pro Plus class SM8750 device?

The answer is convergent:

**The phone does not want a normal cloud-GPU training loop. It wants an asymmetric learning loop.**

Classic training assumes one dominant compute surface: forward stores activations, backward walks the reverse graph, optimizer updates weights, and almost everything happens on one GPU. On a RedMagic-class SoC that abstraction is wrong. The physical machine is heterogeneous and memory-bound. The NPU is not a general autograd device. It is a compiled dense-forward island. The GPU is flexible parallel compute. The CPU is control, optimizer state, reductions, unsupported ops, and scheduling.

Candidate physical loop:

```text
CPU scheduler / optimizer
    -> GPU or CPU trainable island
    -> NPU frozen dense island
    -> GPU or CPU head / adapter / loss island
    -> sparse backward, local backward, recompute backward, synthetic backward, or forward-only update
```

The first principle is:

**Make backward smaller before trying to replace it.**

This is not a retreat from the frontier. It is the first honest way to match learning to the substrate.

## Iteration 2026-05-16: Bottlenecks, Gemma, And Faculty-Like Layers

The operator's live hypothesis: if a 4B-class model is small enough to lay out on the phone, perhaps layers or groups of layers can be treated like distinct faculties in a university. Each faculty can be trained, evaluated, routed, or specialized with some independence while still belonging to a common institution.

This is the right metaphor if it stays physical and measured:

- a layer group is not a magic module; it is a memory/computation island
- a domain adapter is not a full retrain; it is a localized plasticity surface
- a curriculum is not just data order; it is a routing policy over faculties
- a scheduler is not a helper; it is the university timetable and power grid

The danger is turning "faculties" into an aesthetic story. The authority metric remains whether discrete layer/domain training improves useful learning per energy, time, memory, and thermal envelope without general regression.

### Bottleneck Principle

The frontier objective is to drive the system until the final remaining bottleneck is exposed.

We do not stop at "it runs." We peel bottlenecks:

1. model/runtime correctness
2. accelerator support
3. silent fallback
4. memory capacity
5. accelerator address-space limits
6. CPU/GPU/NPU copy and sync
7. quantize/dequantize overhead
8. activation storage
9. KV cache and long-context pressure
10. scheduler and DVFS overhead
11. storage mmap and page faults
12. thermal/power steady state
13. effective DRAM bandwidth
14. only then raw FLOPS/TOPS

The target is not peak synthetic TOPS. The target is to reach the true physical limiter and name it.

Roofline framing:

```text
achieved throughput <= min(accelerator_peak, effective_bandwidth * operational_intensity)
```

If the NPU is treated as roughly 55 TOPS and memory as roughly 85 GB/s, the ridge point is around 650 ops/byte. Ordinary LLM decode and many training paths are likely below that. They are memory/sync/bandwidth problems before they are compute problems.

### About The "Rest Of RAM"

Unified memory does not mean a flat GPU VRAM pool.

The phone may have 24 GB RAM, but each accelerator path has constraints:

- driver-visible buffers
- FastRPC / QNN session address space
- cache maintenance
- layout repacking
- tensor lifetime and allocator behavior
- Android low-memory killer pressure
- GPU/NPU/CPU contention over the same DRAM fabric

The useful question is not "can the model fit in RAM?" but:

**how many bytes move per useful token or learning update?**

A model spread across RAM can still be slow if each step streams weights, repacks layouts, flushes caches, or roundtrips through CPU.

### Gemma Baseline Clarification

Current discussion uses Gemma as the baseline family. Two targets must be kept distinct:

- **Gemma 3 4B**: older/simple 4B-class baseline for reproducibility and mobile runtime availability.
- **Gemma 4 E4B**: current edge-oriented target, but not a normal dense 4B.

Research finding: Gemma 4 E4B has about 4.5B effective parameters but about 8B stored parameters including embeddings / per-layer embeddings. It is edge-shaped for inference, but not trivially phone-trainable.

Known Gemma 4 E4B shape:

| Property | Value |
|---|---|
| Official IDs | `google/gemma-4-E4B`, `google/gemma-4-E4B-it` |
| Effective / stored params | ~4.5B effective / ~8B with embeddings |
| Layers | 42 |
| Hidden size | 2560 |
| FFN size | 10240 |
| Attention | 8 query heads, 2 KV heads |
| Context | 128K |
| Sliding window | 512 tokens |
| Pattern | 5 sliding/local layers then 1 global layer, repeated; final layer global |
| Vocab | 262,144 |
| Modalities | text, image, audio |
| Official dtype | BF16 |

Implications:

- BF16 E4B raw weights are about 16 GB before runtime overhead.
- Q4 inference is plausible on RedMagic-class hardware.
- Full fine-tuning is not the phone target.
- Adapter/LoRA/bias/norm/head plasticity is the realistic first target.
- Per-layer embeddings should be frozen unless there is a strong token-extension reason.
- 128K context is an inference/eval capability, not a phone-training default.
- Training should start at 256-512 token sequences.

### Domain-Parallel Curriculum

"Train domains in parallel" should not initially mean simultaneous multi-domain GPU-style training inside one phone. The SoC will likely bottleneck on shared DRAM and scheduler contention.

More plausible form:

- shared frozen base
- domain-specific adapters or layer faculties
- one or a few active faculties per batch
- curriculum scheduler selects domain based on loss, novelty, and forgetting risk
- replay protects general ability
- phone can score/filter/evaluate locally
- heavier CPT can happen off-device if the phone proves unable to carry it

Curriculum becomes a routing and plasticity policy.

### Token-Budget Frame

For Gemma-class continued pretraining, official Gemma 4 guidance does not publish a full CPT budget. Evidence from continued-pretraining literature suggests staged budgets:

| Token budget | Use |
|---:|---|
| 10M-100M | narrow domain probes or adapter-only experiments |
| 100M-400M | first serious domain-CPT range |
| 0.5B-5B | upper pilot / broad-domain or long-context curriculum |
| 5B-30B+ | broad, deduped, replay-protected corpus only |
| >4 epochs over same data | repetition-risk zone |

For phone-side experiments, the authority metric is not "tokens trained." It is:

**energy-to-loss-improvement without general regression.**

The phone may train fewer tokens but produce more information per joule if it routes plasticity correctly.

### Faculty Model Candidate

Candidate architecture for the research line:

```text
Shared frozen base
    Faculty A: math/reasoning adapter or selected layer group
    Faculty B: code/systems adapter or selected layer group
    Faculty C: language/cross-lingual adapter or selected layer group
    Faculty D: multimodal perceptual adapter or encoder-side bridge
    Faculty E: self-evaluation / critique head

Scheduler:
    chooses faculty activation, replay ratio, sequence length, backend placement,
    and rest/thermal policy based on loss, novelty, confidence, and device state.
```

This is not yet a design commitment. It is the conceptual form to test against bottlenecks.

## Iteration 2026-05-16: Model Candidates For The Faculty/SoC Lane

Research mission: find recent open-weight models that may be better than the Gemma baseline for RedMagic-class heterogeneous SoC experiments.

Correction after user challenge: this first pass answered a **runtime and dense-baseline selection question**, not the full architectural question. It remains useful for the control lane, but it is not the maximal answer to "which architecture naturally fits faculty-like heterogeneous SoC learning?"

The architectural answer is in the next iteration.

The criterion is not leaderboard rank. The criterion is fit for this substrate:

- permissive license
- Android/runtime reproducibility
- QNN/LiteRT/GENIE/llama.cpp/MNN/MLC/ExecuTorch support
- architecture regularity for partitioning
- tokenizer/vocab memory behavior
- adapter/faculty training suitability
- edge/mobile evidence
- ability to expose bottlenecks cleanly

### Net Position

Gemma is the Google/mobile authority baseline, but not necessarily the best experimental substrate.

**Qwen3-4B is the best first challenger.**

Why:

- Apache 2.0
- dense, regular, GQA-style transformer surface
- strong multilingual/code/math capability
- smaller vocab than Gemma 4 E4B
- broad GGUF / vLLM / MLX support
- Qualcomm AI Hub / GENIE / QNN evidence for the Snapdragon toolchain, while still requiring RedMagic/SM8750 validation
- less architectural complexity than Gemma 4 E4B's multimodal + per-layer embedding shape

### Candidate Ranking

| Rank | Candidate | Why it matters | Risk |
|---:|---|---|---|
| 1 | Qwen3-4B / Qwen3-4B-Instruct-2507 | Best Snapdragon/QNN challenger; Apache; regular dense architecture; strong multilingual/code/math | Qualcomm page currently proves the QNN/GENIE path on Snapdragon X-class devices, not RedMagic SM8750; validate exact Android artifact path and correctness |
| 2 | Gemma 4 E4B / E2B | Official Google mobile/AI Edge baseline; Apache; multimodal; LiteRT/AI Edge path | E4B has 8B stored footprint, large vocab, PLE/multimodal complexity |
| 3 | Ministral 3 3B | Edge-oriented Apache model; compact; plausible clean third path outside Google/Qwen | Less Snapdragon-specific evidence |
| 4 | Phi-4-mini / Phi-4-mini-reasoning | Dense, regular, strong reasoning/math, MIT, ONNX/quant ecosystem | English/math skew; less broad multilingual/domain profile |
| 5 | SmolLM3-3B / SmolLM family | Transparent research baseline; good for ablations, adapters, quantization, training-method experiments | Weaker official mobile/NPU evidence |
| 6 | Llama 3.2 1B/3B | Excellent runtime baseline across llama.cpp, ExecuTorch, Qualcomm examples | Custom license; capability lower than newer Qwen/Gemma/Ministral |
| 7 | Qwen2.5 1.5B | Already in our repo; practical continuity baseline | Smaller model; may understate Gemma/Qwen3 bottlenecks |
| 8 | NVIDIA Nemotron 3 Nano 4B | Interesting efficient reasoning model; FP8/Jetson/vLLM/TRT ecosystem | NVIDIA-first stack; hybrid Mamba/Transformer/custom-code path weak for Snapdragon |
| 9 | MobileLLM / MobileLLM-R1 | Explicitly phone-efficiency oriented; useful microbaseline | Sub-1B / noncommercial / conversion work; not a Gemma-class model |
| 10 | Granite 4.1 3B | Apache, clean, multilingual/tool-use | Less mobile/runtime proof |

### Test-First Set

Use five model lanes:

1. **Gemma 4 E4B or E2B** as the Google/mobile authority baseline.
2. **Qwen3-4B-Instruct-2507** as the Snapdragon/QNN challenger.
3. **Ministral 3 3B** as the edge-oriented non-Google/non-Qwen challenger.
4. **SmolLM3-3B** as the transparent research/ablation model.
5. **Qwen2.5-1.5B** as continuity with existing Polymath artifacts.

Optional runtime baseline:

- **Llama 3.2 1B/3B** for llama.cpp / ExecuTorch / Qualcomm reproducibility.

### Updated Baseline Language

Do not say "Gemma 4B" without specifying which target:

- **Gemma 3 4B**: mature older baseline; useful if tooling is easier.
- **Gemma 4 E4B**: current Google mobile authority; effective 4.5B but 8B stored footprint.
- **Gemma 4 E2B**: possibly better first Google target if E4B bottlenecks obscure the experiment.

For the faculty/layer-training idea, **Qwen3-4B may be cleaner than Gemma 4 E4B** because it is less encumbered by multimodal towers and per-layer embedding storage.

### Model Selection Rule

Choose the model that exposes the scientific question cleanly.

If the question is "Can we run Google's mobile stack well?" use Gemma 4 E2B/E4B.

If the question is "Can a Snapdragon SoC train or adapt a regular 4B-class transformer faculty-by-faculty?" use Qwen3-4B first.

If the question is "Can the training algorithm work at all?" use SmolLM3 or Qwen2.5-1.5B first.

If the question is "Can the Android runtime path be reproduced by anyone?" use Llama 3.2 1B/3B.

This avoids `fp-demogravity`: no model is chosen because it sounds impressive. The model is chosen because it attacks a specific bottleneck.

### Source Anchors

Current model claims are anchored in official or primary model pages checked on 2026-05-16:

- Google Gemma 4 family / deployment matrix: https://ai.google.dev/gemma/docs/get_started
- Gemma 4 parameter counts and Hugging Face checkpoints: https://huggingface.co/docs/google-cloud/examples/vertex-ai-notebooks-fine-tune-gemma-4
- Qwen3-4B-Instruct-2507 model card: https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507
- Qualcomm AI Hub Qwen3-4B QNN/GENIE page: https://aihub.qualcomm.com/compute/models/qwen3_4b
- Ministral 3 3B GGUF model page: https://huggingface.co/mistralai/Ministral-3-3B-Instruct-2512-GGUF
- Phi-4-mini-reasoning model card: https://huggingface.co/microsoft/Phi-4-mini-reasoning
- SmolLM3-3B model card: https://huggingface.co/HuggingFaceTB/SmolLM3-3B
- Llama 3.2 3B Instruct model card: https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct
- NVIDIA Nemotron 3 Nano 4B release/model context: https://huggingface.co/blog/nvidia/nemotron-3-nano-4b

## Iteration 2026-05-16: Architectural Correction - Faculty Means Sparse Modular Plasticity

The user challenged the previous answer correctly. The real question is not "which dense 4B model should we try?" The real question is:

**which open architecture makes heterogeneous, partially parallel, faculty-like phone training physically and mathematically plausible?**

The corrected answer:

**the closest existing architecture family is small-active modular MoE, not an ordinary dense 4B transformer.**

Dense 3B-4B models remain necessary controls. They prove runtime correctness, quantization, backend placement, thermal behavior, and the authority metric. They are not the maximal architecture for the Polymath training hypothesis.

### Corrected Architecture Shape

The target shape is:

```text
large total capacity
    -> small active compute per token or batch
    -> shared frozen trunk / always-on backbone
    -> routed experts, faculties, adapters, or nested submodels
    -> static NPU forward islands where possible
    -> GPU/CPU plasticity surfaces
    -> CPU scheduler for routing, replay, optimizer state, thermal policy, and audit
```

This maps directly to the operator's "faculties in a university" metaphor:

- experts or adapter banks are faculties
- the shared trunk is the common institution
- the router/curriculum scheduler is the timetable and admissions office
- replay/eval is the academic standards body
- the phone thermal/power state is part of the learning system

The mathematical warning is equally important:

**arbitrarily training ordinary dense layers independently is not exact next-token backprop.**

Parallel or discrete faculty training is valid only under one of these frames:

1. exact pipeline/model parallelism with synchronization or bounded stale gradients
2. exact sparse-MoE objective where routed experts train on routed tokens
3. frozen-base adaptation where only adapters/heads/norms/expert deltas are trainable
4. local/synthetic/delayed-gradient objectives, which are surrogate objectives and must be judged by final authority metrics
5. zeroth-order or forward-only adaptation, which trades activation memory for repeated forward passes

### Architecture Ranking For The Corrected Question

| Rank | Architecture / Candidate | Why It Matters | First Risk |
|---:|---|---|---|
| 1 | **Small-active modular MoE**: `allenai/OLMoE-1B-7B`, `LiquidAI/LFM2-8B-A1B`, `allenai/Emo_1b14b_1T` | Closest direct match to faculty-like training; active compute can be phone-scale while total capacity is larger | runtime maturity, expert paging, Android support |
| 2 | **Qwen sparse/hybrid MoE**: `Qwen/Qwen3-30B-A3B`, `Qwen/Qwen3.6-35B-A3B`, `Qwen/Qwen3-Next-80B-A3B` | Best high-capacity open architecture line; Qwen3.6 is 35B total / 3B active with Gated DeltaNet + MoE | model residency, custom kernels, dynamic routing, 24GB RAM pressure |
| 3 | **Gemma MoE / mobile authority**: `google/gemma-4-26B-A4B`, `google/gemma-4-E2B`, `google/gemma-4-E4B`, `google/gemma-3n-E4B` | Gemma 4 A4B is the real Gemma MoE; E2B/E4B are mobile authority baselines; Gemma 3n is MatFormer/PLE mobile reference | large vocab/embeddings, PLE complexity, LiteRT path may be inference-first |
| 4 | **Hybrid SSM/attention + MoE**: NVIDIA Nemotron 3 Nano 30B-A3B, Nemotron Nano 9B-v2, Qwen3-Next | Architecturally aligned with long-context memory pressure and active-parameter economy | NVIDIA-first tooling; Mamba/DeltaNet lowering/backward on Snapdragon unproven |
| 5 | **Dense 3B-4B controls**: Qwen3-4B, SmolLM3-3B, Ministral 3B, Phi-4-mini, Llama 3.2 | Establish correctness, physical bottlenecks, and authority metrics | can become `fp-demogravity` if mistaken for the project |

### Qwen3.6 And Resistance V2

Resistance V2 does **not** mean avoiding Qwen3.6 because it is complex. If Qwen3.6-35B-A3B is architecturally closest to the real hypothesis, then it must remain a sovereign target.

But Resistance V2 also forbids a fake victory. The right stance is:

**Qwen3.6 is the north-star architecture, not a trophy name.**

Smaller MoE and dense models are not retreats if they are used as physics probes that clear the path to Qwen3.6. They become retreats only if they replace the north-star objective.

So the ladder is:

1. dense 3B-4B blocks to measure backend truth
2. small-active MoE to prove faculty/router/adaptation mechanics
3. Qwen3-30B-A3B to scale MoE faculty behavior
4. Qwen3.6-35B-A3B as the main architectural target
5. Qwen3-Next / Nemotron-style hybrid MoE as long-context north-star variants

Each rung must be explicitly tied to the next. No rung is allowed to ossify into the project.

### The 24GB RAM Concern

The next key question:

**If Qwen3.6 is 35B total / 3B active, can a 24GB phone train or adapt it, or does the whole model need to be resident in RAM?**

Current working answer:

Active parameters do **not** automatically mean only 3B parameters need to exist in RAM. "Active" means the forward computation touches a subset per token. Practical residency depends on routing, runtime, quantization, storage bandwidth, KV cache, buffers, and whether the graph supports expert paging.

For a MoE model, several things may still need fast availability:

- token embeddings and output head
- router weights and routing activations
- shared experts / shared trunk / attention or DeltaNet blocks
- all experts that may be selected during the current batch or static faculty interval
- quantization scales, layout-repacked weights, backend buffers
- KV cache or recurrent state
- trainable adapters / expert deltas
- optimizer state for any trainable parameters
- activations or recomputation plan for the trainable region

Old-fashioned thinking says "load the whole BF16 model into RAM." That is not required if weights are quantized, memory-mapped, sharded, or expert-paged. But the opposite simplification is also false: "3B active means only 3B resident" is not generally true.

The architecture must answer:

```text
Which weights must be hot?
Which weights can be warm?
Which weights can be cold on UFS?
How often does routing force cold-to-hot movement?
Does that movement erase the active-parameter advantage?
```

For phone training, the likely first viable form is not full Qwen3.6 training. It is:

```text
quantized frozen base / selected active faculty
    + static or slowly changing routing
    + LoRA/adapters/expert deltas for one faculty interval
    + short sequence buckets
    + replay-protected eval
    + profiler proof that storage/RAM transfers do not dominate
```

This preserves Qwen3.6 as the real target while refusing to pretend that active parameter count alone solves memory.

Hard RAM verdict from follow-up research:

**Qwen3.6-35B-A3B is north-star only on a 24GB RedMagic-class phone unless a residency/page-fault/thermal/LoRA experiment passes.**

That verdict is not a retreat. It is the falsifier that prevents "3B active" from becoming a reward-hacked slogan.

First experiment that can promote Qwen3.6 from north-star to first target:

```text
Qwen3.6 Q4-class or better quant
Android native runtime
mmap vs resident run
memory-pressure run
30-minute warm decode
page-fault / storage-read / PSS / LMKD / thermal receipts
adapter-training probe on one small static surface
```

Promotion gate:

- peak PSS leaves Android/backend headroom
- no LMK or swap/page-fault storm
- low major-fault and storage-read rates during decode
- sustained token latency remains stable after warm-up
- output sanity matches host reference quant
- adapter steps reduce held-out loss without retention regression

If this fails, the correct first targets are dense 3B-4B or smaller-total MoE models, while Qwen3.6 remains the north-star residency/offload benchmark.

### New Blind Spots From Fresh-Context Scan

Fresh-context research found several places where the current plan may still be too small:

1. **Real on-phone backprop may be less impossible than assumed.**  
   MeBP, MobileFineTuner, and ZeroQAT-style work make first-order or forward-only training on phones a falsifiable branch. Frozen-base LoRA is still the strongest default, but it must be compared against first-order memory-reduced training, not assumed sovereign.

2. **Expert offload viability is model-specific.**  
   "MoE" is not enough. Router locality matters. We need SRP/SCH-style traces or equivalent cacheability metrics for OLMoE, LFM2, EMO, Qwen3-30B, Gemma 4 A4B, and Qwen3.6 on Polymath corpora.

3. **MoE scheduling is part of the architecture.**  
   Expert bit-width, hot expert cache, prefetch, CPU/GPU/NPU split, and storage order are not runtime details. They are architectural variables.

4. **Large phone storage is not extra RAM unless the model is flash-shaped.**  
   UFS-backed experts require locality, contiguous layout, prefetch overlap, and measured low page-fault rates. Naive cold expert streaming is a likely failure.

5. **Multi-LoRA may express faculties without graph mutation.**  
   If LoRA/adapters can be runtime inputs to a frozen graph, faculties can become scheduler-selected tensors rather than recompilation events.

6. **Low-memory optimizer research deserves a first-class lane.**  
   GaLore, Q-GaLore, APOLLO, Sparse MeZO, QuZO/ZO2, MeBP, and MobiZO should be compared on the same small model/corpus under identical authority gates.

7. **Test-time training and ephemeral adaptation may be phone-native.**  
   The phone may be best at session/faculty fast weights with promotion into durable adapters only after replay-protected validation.

8. **Elastic active-parameter models may fit thermal reality better than fixed-active models.**  
   Variable expert count, variable depth, and budget-conditioned execution may matter because the phone's thermal headroom changes over time.

### Revised Experiment Matrix

The project now has two synchronized lanes:

**Authority/runtime lane**

- dense 3B-4B and smaller models
- real weights
- no silent fallback
- backend placement receipts
- memory/thermal truth
- LoRA, MeBP, MobiZO, GaLore/ZO variants under the same authority gate

**SoC-convergence lane**

- small-active MoE first: OLMoE, LFM2, EMO if stable
- router locality and expert-cache simulation
- static faculty routing before dynamic token MoE
- Qwen3-30B-A3B as serious sparse MoE scale-up
- Qwen3.6-35B-A3B as north-star once residency/offload gates pass
- Gemma 4 26B-A4B and Nemotron/Qwen3-Next as architectural comparison branches

Dense baselines are how we measure. Modular/sparse/faculty architectures are what we are testing. Qwen3.6 is not disqualified by complexity, but every complexity claim must pay rent in receipts.

### Research Artifacts From This Iteration

Supporting notes:

- `docs/research/soc-architecture-2026-05-16/architecture-models.md`
- `docs/research/soc-architecture-2026-05-16/training-systems.md`
- `docs/research/soc-architecture-2026-05-16/soc-runtime-constraints.md`

Open follow-up artifacts:

- `docs/research/soc-architecture-2026-05-16/ram-residency-qwen36.md`
- `docs/research/soc-architecture-2026-05-16/blind-spots-frontier-scan.md`
- `docs/research/soc-architecture-2026-05-16/cultural-handover-critique.md`
- `docs/FRESH-CONTEXT-HANDOVER-SOC-ARCHITECTURE.md`

## Prior-Art Anchors

These are not citations for decoration. They are patterns to copy and reproduce.

### Heterogeneous LLM Inference

**HeteroInfer / Heterogeneous LLM Inference on Mobile SoCs**  
Pattern: CPU control plane, NPU primary compute, GPU secondary compute, phase-aware partitioning, unified-memory-aware synchronization, profiler-driven tensor split solver.  
Polymath copy target: reproduce the architecture on RedMagic-class hardware, then adapt the scheduler to training-shaped loops.

### NPU-Centric LLM Execution

**llm.npu / mllm**  
Pattern: fixed-shape chunk-sharing graphs, QNN-backed NPU execution, CPU/GPU shadow work for activation outliers, out-of-order subgraph scheduling to reduce NPU stalls.  
Polymath copy target: fixed-shape compiled islands for transformer regions; sidecar path for unsupported or numerically difficult operations.

### CPU/GPU Co-Execution

**CoDL**  
Pattern: operator-level CPU/GPU partitioning, small latency predictors, OpenCL execution, concurrency-aware planning.  
Polymath copy target: use as the baseline planner for CPU plus Adreno before NPU complexity enters.

### Graph Partitioning And Delegation

**Band, TFLite delegates, ONNX Runtime QNN EP, ExecuTorch QNN partitioner**  
Pattern: capability query, supported subgraph extraction, delegate execution, explicit fallback.  
Polymath copy target: every backend must expose support, fallback, and proof of real execution. Silent fallback is a falsifier.

### Sparse / Partial Training

**TinyTL, TinyTrain, PockEngine, MobiZO, Mandheling, Swan**  
Pattern: avoid full backward where possible; train tiny regions; prune backward; use inference engines for forward; measure energy-to-accuracy; schedule against thermal constraints.  
Polymath copy target: training experiments should begin with frozen forward islands and small trainable regions, not full phone NPU backprop.

### Alternative Credit-Assignment Frames

**Equilibrium propagation, predictive coding, forward-forward, feedback alignment, synthetic gradients, zeroth-order optimization**  
Pattern: reduce or replace exact global reverse-mode backprop with local, settling, synthetic, or forward-only update signals.  
Polymath copy target: treat these as second-wave candidates after the asymmetric-backprop baseline exists. They may become important if NPU forward passes are cheap enough and backward remains the bottleneck.

## Current Evidence From Our Setup

- RedMagic is attached and usable over ADB.
- Phone reports `SM8750`, Android 15, arm64-v8a.
- Phone storage is large enough for model/checkpoint/corpus artifacts.
- Prior QNN/QAIRT artifacts exist on device.
- QAIRT 2.44 plus LiteRT 2.1.4 can produce SM8750 QNN artifacts in the old branch.
- QNN execution on phone has been demonstrated for compiled artifacts.
- D-033 remains decisive: the previous frozen-middle QNN binary used random-init weights, so language-model correctness is not proven.

Authority implication: the QNN lane is operationally real but scientifically blocked until real-weight cosine validation passes.

## Physical Envelope: RedMagic-Class SM8750

Current best research synthesis:

| Resource | Envelope | Implication |
|---|---|---|
| CPU | Snapdragon 8 Elite Oryon, 2 high cores around 4.32 GHz + 6 performance cores around 3.53 GHz | Control plane, scheduling, unsupported ops, optimizer state, reductions, fallback |
| CPU ISA | NEON, FP16, dotprod, i8mm class features observed in public Geekbench metadata | INT8/FP16 CPU fallback is viable but not the sustained dense-matmul target |
| GPU | Adreno 830, Vulkan 1.3, OpenCL 3.0 FP, OpenGL ES 3.2 | Most accessible custom accelerator; likely home for flexible FP kernels and backward sidecars |
| GPU compute | Few-TFLOP FP32-class mobile GPU by inferred public estimates; exact practical throughput must be measured | Expect memory-bound LLM behavior; benchmark on actual shapes, not peak FLOPs |
| NPU | Hexagon NPU with scalar/vector/tensor accelerators; INT4, INT8, INT16, FP16, mixed precision support | Best perf/W for supported compiled inference islands through QNN/QAIRT |
| NPU TOPS | Qualcomm gives relative improvement publicly but not a clean consumer SM8750 absolute TOPS number | Do not use marketing TOPS as authority. Use measured QNN latency and correctness |
| RAM | 12-24 GB LPDDR5X Ultra device class | 24 GB variants are the serious local LLM target |
| Memory bandwidth | Roughly 77 GB/s inferred for 9600 Mbps on a 64-bit LPDDR bus; up to ~85 GB/s class depending config | Primary limiter for LLMs; avoid unnecessary CPU/GPU/NPU copies |
| Storage | UFS 4.1-class, large enough for model/corpus/checkpoint artifacts | Useful for load/checkpoint/cold storage; not a substitute for RAM bandwidth |
| Thermal | Active fan, liquid metal/VC stack, bypass charging, fridge operation available in our regime | Thermal state is a control variable and should enter the scheduler |

Governing constraint:

**not peak TOPS; graph support + memory movement + thermals + correctness.**

## Working Hypotheses

1. **Heterogeneous scheduling beats monolithic execution only when placement is phase- and shape-aware.**  
   Generic "run each op where fastest" is too weak.

2. **NPU is best treated as a compiled dense-island engine.**  
   It should receive stable, fixed-shape subgraphs with proven coverage and no silent fallback.

3. **GPU is the flexible frontier device.**  
   Adreno/OpenCL/Vulkan is likely where unsupported ops, training sidecars, and experimental kernels live.

4. **Training viability depends on shrinking or restructuring backward.**  
   Full backward through large models on phone is not the first serious target. Sparse, adapter, bias-only, LoRA-like, zeroth-order, or recompute-based methods are better first-class candidates.

5. **Energy-to-quality is a stronger authority metric than raw latency.**  
   The system must improve useful learning per watt-hour and per thermal envelope, not just run faster locally.

6. **Thermal state is part of the algorithm.**  
   Fan mode, fridge ambient, charge bypass, and rest scheduling are control variables, not afterthoughts.

7. **Forward is an accelerator problem; backward is an algorithm design problem.**  
   The forward trunk can be compiled and placed. The backward path must be shrunk, localized, recomputed, synthesized, or replaced.

8. **NPU is not "the training device."**  
   NPU is a dense-island engine. Training emerges from how the CPU/GPU/NPU loop is arranged around that island.

9. **The scheduler is a scientific instrument.**  
   It should expose the structure of the workload, not merely chase fastest backend labels.

## Executive Mandate For Agents

Agents working this line are not asked to produce a demo. They are asked to reproduce and extend a research system.

Mandate:

1. Start from best-known prior art. Copy patterns before inventing replacements.
2. Reproduce real baselines on the actual phone class.
3. Instrument every run for latency, energy proxy, memory, thermal state, backend placement, and correctness.
4. Treat failed experiments as steering signals. Pivot and continue.
5. Never convert a partial result into a pass narrative.
6. Keep artifacts reconstructible from repo, phone, RunPod, and Hugging Face surfaces.
7. Use RunPod only when it materially unlocks host-side compilation, teacher generation, or analysis.
8. Keep Mac as a minimal control plane.
9. Store large model/corpus/checkpoint artifacts on phone or Hugging Face, not Mac.
10. Advance only against the authority metric, not against visible activity.

## First Copy Targets

These are the initial systems to mimic, in order.

1. **HeteroInfer-style profiling and partitioning**
   - Build per-shape CPU/GPU/NPU latency table.
   - Measure sync overhead and memory movement.
   - Compare prefill-like and decode-like shapes.

2. **Adreno GPU baseline**
   - Reproduce `llama.cpp` OpenCL or equivalent Adreno 830 path.
   - Measure sustained throughput under fan/fridge/charge settings.
   - Use as flexible compute baseline.

3. **SM8750 NPU baseline**
   - Reproduce Google AI Edge Gallery or QNN/QAIRT NPU execution.
   - Prove real NPU use and no CPU fallback.
   - Re-run with real pretrained weights where model correctness matters.

4. **Tiny heterogeneous training benchmark**
   - Frozen encoder on NPU/GPU.
   - Small head/adapter trained on CPU/GPU.
   - Authority metric: energy-to-target-accuracy with hard correctness gate.

5. **LLM-shaped training loop**
   - Fixed dense transformer islands on NPU.
   - Flexible trainable strips on GPU/CPU.
   - Compare ELO, LoRA/adapters, bias-only, and zeroth-order variants.

## Heterogeneous Pass Laboratory

The next platform should be a laboratory for the physical pass structure, not a model demo.

It should measure:

- CPU/GPU/NPU per-shape latency
- memory copy and synchronization overhead
- sustained thermal drift under fan, fridge, and charge-bypass regimes
- correctness against host reference for every compiled island
- backend fallback and silent fallback detection
- energy proxy per useful unit of learning
- idle bubbles across CPU/GPU/NPU

Initial pass families:

1. **Dense forward island**
   - fixed-shape transformer block or frozen encoder on NPU
   - correctness: cosine/MSE against reference
   - authority: measured latency, thermal stability, no fallback

2. **Flexible GPU sidecar**
   - OpenCL/Vulkan kernels for unsupported ops, adapter layers, or backward pieces
   - authority: beats CPU on sustained energy-to-work for target shapes

3. **Small trainable island**
   - CPU/GPU head, LoRA, bias, norm-shift, or adapter update
   - authority: target accuracy or loss improvement with bounded energy and memory

4. **Recompute backward**
   - discard activations, rerun forward where needed
   - authority: lower memory pressure without destroying wall-clock or thermal envelope

5. **Forward-only probe**
   - zeroth-order or forward-forward candidate over very small trainable surface
   - authority: beats sparse-backward baseline on energy-to-quality, not novelty

The lab should make it impossible to hide behind "it ran." Every pass must say what physical substrate it used and what authority metric moved.

## Authority Metrics

Candidate top-level metrics:

- correctness versus reference: cosine / MSE / exact task accuracy where applicable
- energy-to-target-quality
- sustained tokens/hour or examples/hour under thermal constraints
- wall-clock-to-target-quality
- backend utilization and idle-bubble reduction
- memory traffic and artifact movement
- thermal stability over hours
- recovery from failed backend or fallback

Latency alone is not sovereign.

For training-shaped work, strongest candidate authority metric:

**energy-to-target-quality under sustained thermal constraints.**

Secondary metrics:

- memory-to-target-quality
- wall-clock-to-target-quality
- correctness versus reference
- fallback-free accelerator coverage
- sustained operating envelope over hours

## Open Questions

- What is the smallest benchmark that genuinely captures heterogeneous training rather than inference plus a toy head?
- Can Adreno run meaningful backward sidecars faster or more energy-efficiently than CPU?
- Can QNN/Hexagon compiled islands be used inside a training loop without transfer overhead erasing the benefit?
- Is zeroth-order optimization viable on phone if NPU forward passes are cheap enough?
- Does the fridge/fan/charge regime change optimal scheduling policy?
- What is the right scheduler objective: latency, energy, temperature, memory pressure, or learning progress?
- How much of HeteroInfer can be recreated without its code?
- Which backend stack gives the least distorted path: QNN direct, ExecuTorch QNN, ONNX Runtime QNN, TFLite, MNN, MLC, llama.cpp, or custom Vulkan/OpenCL?

## Current Conclusion

This is a real research lane. It should not be framed as "phone training" in the generic sense.

The more precise frame is:

**heterogeneous thermally-aware learning systems on phone-scale SoCs.**

The RedMagic-class phone is a physical AI substrate. The next work is to copy the best existing heterogeneous inference systems, establish real baselines, then discover the training algorithm that fits the substrate instead of forcing cloud training assumptions onto it.

The new synthesis is:

**Forward becomes a compiled physical flow. Backward becomes a design choice.**

That design choice may be exact, truncated, recomputed, sparse, local, synthetic, or forward-only. The point is not to preserve the inherited shape of backprop. The point is to find the learning loop that the SoC can sustain.
