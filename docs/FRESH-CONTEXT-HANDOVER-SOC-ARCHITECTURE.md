# Fresh Context Handover - Heterogeneous SoC Architecture

**Date:** 2026-05-16  
**Audience:** fresh-context orchestrator or research agent  
**Project folder:** `/Users/Zer0pa/Polymat AI/Polymath-AI`  
**Operating ethos:** `RESISTANCE-V2.md`

## Mandate

This project is not a phone inference demo.

The research question is:

**what learning architecture becomes natural when a RedMagic-class phone is treated as a heterogeneous physical computer with CPU, GPU, NPU, unified memory, large UFS storage, active cooling, and long-horizon autonomy?**

Do not shrink this into:

- "Which 4B model runs fastest?"
- "Can we get a QNN graph to execute?"
- "Can we fine-tune a tiny model?"
- "Can we show CPU/GPU/NPU activity?"

Those are probes. They are not the governing objective.

## Cultural Stance

The previous orchestrator initially failed by turning an architectural question into a model-ranking/runtime question. That was `fp-scopeevaporation`.

The corrected frame:

- dense 3B-4B models are control lanes
- small-active MoE is the closest architecture to the faculty hypothesis
- Qwen3.6-35B-A3B is a serious north-star target because it is architecturally close, not because it is prestigious
- Gemma 4 E2B/E4B are mobile authority baselines, not the full faculty answer
- Gemma 4 26B-A4B is the relevant Gemma MoE
- Gemma 3n is important for MatFormer / nested / PLE thinking
- NVIDIA Nemotron is important design evidence for hybrid Mamba/Transformer/MoE, even if Snapdragon execution is not first-class

Resistance V2 means do not avoid the hard architecture because it is complex. It also means do not fake progress by building a smaller thing and calling it the thing.

## Current Working Thesis

The architecture shape to test is:

```text
large total capacity
    -> small active compute
    -> shared frozen trunk / always-on backbone
    -> routed experts, faculties, adapters, or nested submodels
    -> static NPU forward islands
    -> GPU/CPU plasticity surfaces
    -> CPU scheduler for routing, replay, optimizer state, thermal policy, and audit
```

The phone likely wants an asymmetric loop:

```text
CPU scheduler / optimizer
    -> NPU frozen dense island
    -> GPU or CPU adapter / expert-delta / head / loss island
    -> sparse backward, local backward, recompute backward, synthetic backward, or forward-only update
```

First principle:

**make backward smaller before trying to replace it.**

## Key Technical Question To Be Ready For

The user will ask:

**We only have 24GB RAM on the phone. Qwen3.6-35B-A3B has 35B total and 3B active. If only active parameters train, do we still need the whole model in RAM? Is needing the whole model in RAM old-fashioned thinking?**

Do not answer glibly.

Current conceptual answer:

- active parameters are compute-active, not automatically RAM-resident-only
- BF16 full residency is not required if quantized, sharded, memory-mapped, or expert-paged
- but "3B active" does not mean only 3B needs fast availability
- every layer still needs routing, shared blocks, embeddings, output head, active experts, cache/state, quant scales, layout buffers, and trainable deltas
- cold UFS expert paging may be possible but can destroy throughput if routing changes frequently
- static or slowly changing faculty routing is more plausible than token-level dynamic expert paging on a phone
- LoRA/adapters/expert deltas can be small, but the frozen base forward still needs accessible base weights

The correct investigation is:

```text
hot weights: required every token / every batch
warm weights: selected for a faculty interval
cold weights: stored on UFS, loaded rarely

Does routing force cold-to-hot movement often enough to erase MoE's active-parameter advantage?
```

Hard follow-up verdict:

**Qwen3.6-35B-A3B is north-star only on a 24GB RedMagic-class phone unless a residency/page-fault/thermal/LoRA experiment passes.**

This is not a retreat from Resistance V2. It is the anti-reward-hacking position: "3B active" is a hypothesis about compute, not proof of memory feasibility.

Promotion experiment:

- Qwen3.6 Q4-class or better quant on Android native runtime
- mmap versus resident run
- memory-pressure run
- PSS/RSS, page faults, storage reads, LMKD, thermal, token latency
- 30-minute warm decode
- one static LoRA/adaptation surface
- host-reference output sanity

If the promotion experiment fails, use dense 3B-4B and smaller-total MoE as first targets while preserving Qwen3.6 as the residency/offload benchmark.

## Model Architecture Reading List

Read in this order:

1. `docs/HETEROGENEOUS-SOC-RESEARCH-DIALOGUE.md`
2. `RESISTANCE-V2.md`
3. `docs/research/soc-architecture-2026-05-16/architecture-models.md`
4. `docs/research/soc-architecture-2026-05-16/training-systems.md`
5. `docs/research/soc-architecture-2026-05-16/soc-runtime-constraints.md`
6. `docs/research/soc-architecture-2026-05-16/ram-residency-qwen36.md` if present
7. `docs/research/soc-architecture-2026-05-16/blind-spots-frontier-scan.md` if present
8. `docs/research/soc-architecture-2026-05-16/cultural-handover-critique.md` if present

Primary external anchors:

- Qwen3.6-35B-A3B: https://huggingface.co/Qwen/Qwen3.6-35B-A3B
- Qwen3-30B-A3B: https://huggingface.co/Qwen/Qwen3-30B-A3B
- Qwen family / MoE / Gated DeltaNet overview: https://qwen.moe/
- Gemma 4 model card: https://ai.google.dev/gemma/docs/core/model_card_4
- Gemma 3n overview: https://ai.google.dev/gemma/docs/gemma-3n
- MatFormer: https://arxiv.org/abs/2310.07707
- NVIDIA Nemotron 3: https://research.nvidia.com/labs/nemotron/Nemotron-3/
- OLMoE: https://arxiv.org/abs/2409.02060
- Switch Transformer: https://arxiv.org/abs/2101.03961
- LoRA: https://arxiv.org/abs/2106.09685
- MobiZO: https://arxiv.org/abs/2409.15520
- Qualcomm AI Engine Direct: https://www.qualcomm.com/developer/software/qualcomm-ai-engine-direct-sdk
- ONNX Runtime QNN EP: https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html
- ExecuTorch Qualcomm backend: https://docs.pytorch.org/executorch/stable/backends-qualcomm.html

## Experimental Ladder

Do not interpret this ladder as retreat. Each rung exists only to clear a bottleneck toward the north-star architecture.

1. Dense block physical truth:
   measure CPU / Adreno / Hexagon latency, correctness, fallback, copy/sync, quantization, thermal drift.

2. Frozen trunk plus adapter:
   prove that NPU or GPU forward plus small trainable sidecar can improve an authority metric under replay protection.

3. Small-active MoE:
   use OLMoE / Liquid LFM / EMO-style models to test faculty routing, expert specialization, and static expert-bank training.

4. Qwen3-30B-A3B:
   test serious open sparse MoE at 3B active.

5. Qwen3.6-35B-A3B:
   main north-star architecture for the current question.

6. Qwen3-Next / Nemotron-style hybrid MoE:
   long-context memory-economy branch after DeltaNet/Mamba runtime risk is better understood.

## Claims That Require Receipts

Require hard evidence for:

- no silent CPU fallback
- actual backend placement
- model-language correctness after conversion
- memory residency and buffer/repack sizes
- UFS paging cost under warm thermal state
- active expert distribution
- router collapse or expert starvation
- eval retention after adapter/expert updates
- wall-clock-to-authority improvement
- thermal behavior after 20-60 minutes, not burst

The authority metric is not "it ran." The authority metric is useful learning per time/energy/memory/thermal envelope without general regression.

## Do Not Do This

- Do not rank models by leaderboard without architecture fit.
- Do not call Qwen3.6 "too complex" and move on.
- Do not call a dense 4B baseline the project.
- Do not treat active parameters as a memory proof.
- Do not treat adapter training as full pretraining.
- Do not turn local losses, zeroth-order updates, or synthetic gradients into magic. They are surrogate objectives until the final metric passes.

## Immediate Research Gaps

Open questions the fresh agent should attack:

- Can Qwen3.6 or Qwen3-30B experts be statically grouped into faculties for phone intervals?
- Can expert weights live cold on UFS without destroying throughput?
- Can Android memory mapping plus quantized expert shards make "whole model residency" unnecessary in practice?
- Which MoE runtime supports expert paging/offload closest to phone constraints?
- Which parts of Qwen3.6 are hot regardless of active experts?
- What is the smallest experiment that falsifies "active parameters solve 24GB RAM"?
- What is the smallest experiment that falsifies "Qwen3.6 is impossible on phone"?
- Can router locality be measured on our actual corpora before any MoE offload claim?
- Can multi-LoRA-as-runtime-input express faculties without QNN/LiteRT recompilation?
- Can MeBP/MobileFineTuner-style first-order phone training beat LoRA/MobiZO under identical thermal and authority gates?
- Can elastic expert/depth budgets respond to thermal state without requiring too many compiled graph variants?

Preserve both possibilities until measured.

## Blind Spots To Carry Forward

Fresh-context research added these non-negotiable branches:

- **First-order phone training challenger:** MeBP/MobileFineTuner/ZeroQAT-style work means "full or partial backprop is impossible" must be falsified, not assumed.
- **Router locality gate:** expert cacheability must be measured per model and corpus. Active-parameter count alone is not enough.
- **Expert scheduler as architecture:** bit-width, cache, prefetch, CPU/GPU/NPU split, and UFS order are design variables.
- **Flash-shaped models:** large phone storage only helps if access is predictable, overlapped, and low-fault.
- **Multi-LoRA faculty runtime:** adapters as runtime inputs may be the most practical way to express faculties without graph mutation.
- **Low-memory optimizer ladder:** GaLore/Q-GaLore/APOLLO/Sparse MeZO/QuZO/ZO2 should compete under one authority gate.
- **Ephemeral test-time adaptation:** session fast weights and temporary adapters may be the phone-native learning surface.
- **Elastic active budget:** variable expert count/depth may be necessary because thermal headroom changes during long runs.
