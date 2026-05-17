# Architecture Models For Heterogeneous Phone-SoC Training

Date: 2026-05-16  
Role: Research Agent A  
Scope: architecture fit for RedMagic 10 Pro / Snapdragon 8 Elite-class heterogeneous SoC training, not model popularity or benchmark ranking.

## Governing Verdict

The architecture most aligned with Polymath's phone-SoC objective is **small-active, fine-grained MoE with explicit modularity**, not a conventional dense 4B baseline. The best target shape is:

- **Total parameters large enough for capacity, active parameters near 1B-4B.**
- **Many small experts**, with top-k routing and a shared or always-on backbone.
- **A separable router/expert/adapters training loop**, so the phone can train one faculty slice while keeping most of the model frozen.
- **A frozen-forward island** that can plausibly be delegated to NPU/LiteRT/QNN, with GPU handling trainable deltas and CPU handling routing, optimizer state, telemetry, and audit.
- **No dependence on simultaneous CPU/GPU/NPU expert parallelism as the first proof**, because the phone has unified memory and shared DRAM bandwidth. The first real gate should be wall-clock improvement from staged/faculty training, not a narratable "we used all devices" story.

Gemma 3/4-class dense/mobile baselines remain important, but they are not the architecture that most directly expresses the faculty-like idea. They are authority baselines and mobile-stack baselines.

## Ranked Architecture Fit

| Rank | Architecture / exact candidates | Fit verdict |
|---:|---|---|
| 1 | **Emergent/modular MoE**: `allenai/Emo_1b14b_1T`; related standard-MoE controls `allenai/StdMoE_1b14b_1T` | Best conceptual fit. EMO is explicitly designed so coherent expert subsets can be independently retained/composed. This is the closest published architecture to "faculty-like" phone training. Uncertain because it is very new and less deployment-proven. |
| 2 | **Phone-scale small-active MoE**: `LiquidAI/LFM2-8B-A1B`; `allenai/OLMoE-1B-7B-0924`; `allenai/OLMoE-1B-7B-0924-Instruct` | Best practical research substrate. Active compute is phone-relevant, total size is not absurd, and experts are separable enough for staged expert/router/adaptor experiments. |
| 3 | **Qwen fine-grained MoE**: `Qwen/Qwen3-30B-A3B`; `Qwen/Qwen3.6-35B-A3B`; north-star `Qwen/Qwen3-Next-80B-A3B-Instruct` / `Qwen/Qwen3-Next-80B-A3B-Thinking` | Best high-capacity open architecture family. Qwen3-30B-A3B is the clean text MoE challenger; Qwen3.6 and Next add hybrid Gated DeltaNet plus MoE, improving long-context economics but increasing kernel/runtime risk on Snapdragon. |
| 4 | **Google MoE/mobile authority**: `google/gemma-4-26B-A4B`; dense/effective baselines `google/gemma-4-E2B`, `google/gemma-4-E4B`; older MatFormer mobile baseline `google/gemma-3n-E4B` | Best Google/mobile authority lane. Gemma 4 26B-A4B has real MoE structure. E2B/E4B are edge-optimized effective-parameter models with PLE, useful for AI Edge/LiteRT gates but less naturally faculty-like than MoE. |
| 5 | **Hybrid SSM/attention + MoE**: `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16`, `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8`; `nvidia/NVIDIA-Nemotron-Nano-9B-v2` | Architecturally strong for long contexts and active compute, but NVIDIA-first kernels/tooling make Snapdragon training uncertain. Treat as design evidence, not first phone target. |
| 6 | **Dense small/edge baselines**: `Qwen/Qwen3-4B`, `HuggingFaceTB/SmolLM3-3B`, `mistralai/Ministral-3-3B-Instruct-2512-BF16`, `microsoft/Phi-4-mini-reasoning`, `microsoft/Phi-4-mini-flash-reasoning`, `facebook/MobileLLM-1B`, Apple OpenELM | Best for proving the training loop, scheduler, audit, and export path. They do not maximize faculty parallelism because the compute path is mostly serial dense transformer work. |
| 7 | **Full frontier MoE references**: `deepseek-ai/DeepSeek-R1`, DeepSeek-V3, Kimi K2, GLM-4.5/GLM-4.5-Air, Step-3/Step-3.5 | Useful architecture evidence for MoE, MLA/MTP, and model-system co-design. Not phone-trainable directly: active parameters are too high and full-weight residency/offload dominates. DeepSeek-R1 distills are dense Qwen/Llama models, not the R1 MoE architecture. |

## Architecture Families

### 1. MoE / Sparse MoE

**Why it fits:** MoE is the only surveyed mainstream architecture that naturally decomposes into trainable "faculties." Expert FFNs, router logits, shared experts, and per-domain expert subsets give Polymath a real control surface for staged training.

Best candidates:

- `allenai/Emo_1b14b_1T`: strongest conceptual match. EMO restricts tokens in the same document to a shared expert pool during pretraining, producing semantic expert subsets. The paper reports a 1B-active, 14B-total model and says retaining 25% of experts costs only about 1 absolute point, unlike standard MoEs. This is exactly the property Polymath wants, but it is fresh and needs independent reproduction.
- `LiquidAI/LFM2-8B-A1B`: best phone-scale MoE candidate if license/runtime checks pass. It is 8B total with 1.5B active per forward pass, an attractive size for RedMagic-class storage plus quantized/offloaded residency.
- `allenai/OLMoE-1B-7B-0924`: older, fully open, transparent, and small enough to be a clean MoE training substrate.
- `Qwen/Qwen3-30B-A3B`: best mature high-capacity MoE challenger. It has 30.5B total, 3.3B active, 48 layers, 128 experts, and 8 active experts.
- `google/gemma-4-26B-A4B`: Google-side MoE authority baseline. It has 25.2B total, 3.8B active, 128 total experts, 8 active experts, and 1 shared expert.

Phone training implication:

- Do **not** begin by trying to train all experts. Begin with router-only, selected-expert LoRA, or one expert group per domain/faculty.
- The NPU lane should first run frozen dense/shared blocks. The GPU trains active expert deltas. CPU runs router accounting, optimizer state, audit hashes, and thermal scheduling.
- Authority metric is wall-clock-to-quality under identical eval, not parameter count or "all accelerators active."

### 2. Qwen3 MoE / Qwen3-Next / Qwen3.6

`Qwen/Qwen3-30B-A3B` is the cleanest first high-capacity MoE target because it is a regular text MoE: 30.5B total, 3.3B active, 128 experts, 8 active experts, 48 layers.

`Qwen/Qwen3-Next-80B-A3B-Instruct` and `Qwen/Qwen3-Next-80B-A3B-Thinking` are better architecture north stars than first phone targets. They combine:

- 80B total / 3B active.
- 48 layers.
- Hybrid layout: `12 * (3 * (Gated DeltaNet -> MoE) -> 1 * (Gated Attention -> MoE))`.
- 512 experts, 10 activated experts, 1 shared expert.
- Native 262K context, extensible to about 1M tokens.
- Multi-token prediction, although Hugging Face notes MTP throughput gains depend on dedicated serving implementations.

`Qwen/Qwen3.6-35B-A3B` is potentially the best newer Qwen architecture candidate as of this search: 35B total / 3B active, 40 layers, `10 * (3 * (Gated DeltaNet -> MoE) -> 1 * (Gated Attention -> MoE))`, 256 experts, 8 routed + 1 shared active. It is also a vision-language model, which may be a drawback if Polymath wants a text-only training substrate.

Uncertainty:

- Gated DeltaNet / linear-attention kernels may not map cleanly to QNN/LiteRT on SM8750. The architecture is excellent for long-context economics, but custom backward kernels on phone are a real risk.
- Qwen3.6 is very recent. Treat model-card claims as provisional until local export/runtime probes exist.

### 3. Gemma 4 / Gemma 3n / MatFormer-Style Models

Gemma should be split into three different lanes:

- `google/gemma-4-26B-A4B`: the real Gemma MoE candidate. It is architecture-relevant for faculty training.
- `google/gemma-4-E2B` and `google/gemma-4-E4B`: edge/mobile effective-parameter models. The model card says E2B/E4B use Per-Layer Embeddings (PLE): each decoder layer gets its own small token embedding table, so total stored parameters exceed effective active compute. This helps on-device inference but is not the same as expert modularity.
- `google/gemma-3n-E4B`: older mobile-first baseline explicitly associated with MatFormer-style elastic/nested execution. Use it when the experiment is about nested submodels and mobile deployment, not MoE faculty training.

Verdict:

- Best Gemma architecture for Polymath faculty experiments: `google/gemma-4-26B-A4B`.
- Best Gemma authority/mobile-stack baseline: `google/gemma-4-E2B` before `google/gemma-4-E4B`, because the smaller target is less likely to make the first phone experiment about memory pressure rather than architecture.
- Avoid the phrase "Gemma 4B" without exact model id. `Gemma 3 4B`, `Gemma 3n E4B`, `Gemma 4 E4B`, and `Gemma 4 26B-A4B` mean different architectures.

Uncertainty:

- I verified Gemma 4 E2B/E4B PLE and Gemma 4 26B-A4B MoE from the model card. I did **not** find official evidence in the checked sources that Gemma 4 E2B/E4B themselves are MatFormer models. Treat "Gemma 4 MatFormer" as unverified unless a Google source says it explicitly.

### 4. Hybrid SSM / Attention

Hybrid SSM/attention is compelling for RedMagic because long contexts are memory-bound. Replacing most attention with Gated DeltaNet, Mamba-2, or convolutional recurrent blocks can reduce KV-cache pressure and improve sustained throughput.

Relevant candidates:

- `Qwen/Qwen3-Next-80B-A3B-Instruct` and `Qwen/Qwen3.6-35B-A3B`: Gated DeltaNet plus Gated Attention plus MoE.
- `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16` / `FP8`: hybrid Mamba-2 + attention + MoE; model card says 23 Mamba-2/MoE layers plus 6 attention layers, 128 experts + 1 shared expert, 6 experts per token, 30B total, 3.5B active.
- `nvidia/NVIDIA-Nemotron-Nano-9B-v2`: hybrid Mamba-Transformer, designed for long reasoning throughput.
- `LiquidAI/LFM2-8B-A1B`: hybrid LFM2 MoE; official docs list 8B total and 1.5B active.

Verdict:

- Hybrid SSM/attention is likely the right **long-context inference** architecture.
- It is not automatically the best **phone-training** architecture until backward kernels and QNN/LiteRT conversion are proven. Dense and MoE transformer blocks are easier first proof targets than custom recurrent/linear-attention blocks.

### 5. Modular / Adapter Architectures

Adapters are not a foundation-model architecture family in the same way as MoE, but they may be the best training method for the RedMagic.

Best pattern:

- Freeze the base model.
- Train router/adapters/faculty heads per domain.
- Keep adapter state small enough for GPU memory.
- Use CPU for optimizer state if GPU memory is tight.
- Use NPU only for frozen forward subgraphs once QNN delegation is actually proven.

MoE + adapters is stronger than dense + adapters because experts give a real route to selective capacity. Dense + adapters remains the safest baseline.

### 6. Small Dense Baselines

Dense models should remain in the experiment matrix because they establish the authority metric and prevent MoE reward hacking.

Recommended dense baselines:

- `Qwen/Qwen3-4B`: clean Snapdragon/QNN challenger if export works.
- `HuggingFaceTB/SmolLM3-3B`: transparent 3B baseline; model card says decoder-only transformer with GQA and NoPE in a 3:1 ratio, pretrained on 11.2T tokens.
- `mistralai/Ministral-3-3B-Instruct-2512-BF16`: edge-oriented Mistral baseline.
- `microsoft/Phi-4-mini-reasoning`: 3.8B dense decoder-only transformer.
- `microsoft/Phi-4-mini-flash-reasoning`: hybrid SambaY edge reasoning candidate; promising throughput claim, but less transparent for phone training than MoE.
- Apple OpenELM: useful for layer-wise scaling and open training recipe; less relevant to Snapdragon than Apple/MLX environments.
- Meta `facebook/MobileLLM-1B`: valuable phone-first microbaseline; too small to be the main Polymath authority model.

Verdict:

- Dense 3B-4B models are the first correctness gate.
- They are not the maximal architecture for approaching SoC theoretical limits, because every token tends to traverse the same serial dense path.

### 7. DeepSeek / Kimi / GLM / Step-Style Frontier MoE

These are architecture references, not phone targets.

- `deepseek-ai/DeepSeek-R1` and DeepSeek-V3: 671B total / 37B active, based on DeepSeek-V3-Base with MLA, DeepSeekMoE, auxiliary-loss-free load balancing, and MTP. Too large for phone training. The DeepSeek-R1 distills (`DeepSeek-R1-Distill-Qwen-1.5B`, `7B`, `14B`, `32B`; `DeepSeek-R1-Distill-Llama-8B`, `70B`) are dense Qwen/Llama derivatives, useful for reasoning-data baselines but not R1 architecture experiments.
- Kimi K2: 1T MoE / 32B active. Useful as a frontier MoE design reference, not a phone candidate.
- GLM-4.5 / GLM-4.5-Air: GLM-4.5 is 355B / 32B active; GLM-4.5-Air is 106B / 12B active. Still too large for RedMagic training, but better than dense frontier models for architecture lessons.
- Step-3 / Step 3.5 Flash: useful for model-system co-design and active-parameter economics; still outside first phone target range.

## Experiment Recommendation

Run a two-lane architecture matrix:

1. **Authority/correctness lane:** dense 3B-4B baseline first.
   - `HuggingFaceTB/SmolLM3-3B`
   - `Qwen/Qwen3-4B`
   - `google/gemma-4-E2B` or `google/gemma-4-E4B`

2. **SoC-convergence lane:** small-active MoE with staged expert training.
   - First: `allenai/OLMoE-1B-7B-0924` or `LiquidAI/LFM2-8B-A1B`.
   - Then: `Qwen/Qwen3-30B-A3B`.
   - Then: `google/gemma-4-26B-A4B`.
   - Research branch: `allenai/Emo_1b14b_1T` if its weights/tooling are stable enough.
   - North-star branch: `Qwen/Qwen3-Next-80B-A3B-Instruct` or `Qwen/Qwen3.6-35B-A3B` once hybrid DeltaNet kernels are proven.

Acceptance gate:

- A MoE/faculty approach only passes if it improves the governing metric at equal or lower wall-clock than the dense baseline under the same thermal and audit constraints.
- Regression on authority quality is failure even if device utilization looks better.
- "Parallel" means lower measured wall-clock per accepted quality unit, not simultaneous activity in CPU/GPU/NPU counters.

## Source Notes

- Qwen MoE overview and model evolution: https://qwen.moe/
- `Qwen/Qwen3-30B-A3B` model card: https://huggingface.co/Qwen/Qwen3-30B-A3B
- `Qwen/Qwen3-235B-A22B` model card: https://huggingface.co/Qwen/Qwen3-235B-A22B
- `Qwen/Qwen3-Next-80B-A3B-Instruct` model card: https://huggingface.co/Qwen/Qwen3-Next-80B-A3B-Instruct
- `Qwen/Qwen3-Next-80B-A3B-Thinking` model card: https://huggingface.co/Qwen/Qwen3-Next-80B-A3B-Thinking
- `Qwen/Qwen3.6-35B-A3B` model card: https://huggingface.co/Qwen/Qwen3.6-35B-A3B
- Gemma 4 model card: https://ai.google.dev/gemma/docs/core/model_card_4
- `google/gemma-4-E2B` model card: https://huggingface.co/google/gemma-4-E2B
- `google/gemma-4-E4B` model card: https://huggingface.co/google/gemma-4-E4B
- `google/gemma-4-26B-A4B` model card: https://huggingface.co/google/gemma-4-26B-A4B
- `google/gemma-3n-E4B` model card: https://huggingface.co/google/gemma-3n-E4B
- Gemma 3n model overview / MatFormer note: https://ai.google.dev/gemma/docs/gemma-3n
- MatFormer paper: https://arxiv.org/abs/2310.07707
- NVIDIA Nemotron 3 overview: https://research.nvidia.com/labs/nemotron/Nemotron-3/
- `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8` model card: https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8
- Nemotron Nano 2 paper: https://arxiv.org/abs/2508.14444
- OLMoE model card: https://huggingface.co/allenai/OLMoE-1B-7B-0924
- OLMoE paper: https://arxiv.org/abs/2409.02060
- EMO paper: https://arxiv.org/abs/2605.06663
- EMO HF collection: https://huggingface.co/collections/allenai/emo
- DeepSeek-R1 model card: https://huggingface.co/deepseek-ai/DeepSeek-R1
- DeepSeek-V3 technical report: https://arxiv.org/abs/2412.19437
- DeepSeek-V3 repository: https://github.com/deepseek-ai/DeepSeek-V3
- Mixtral paper: https://arxiv.org/abs/2401.04088
- Mixtral docs: https://huggingface.co/docs/transformers/model_doc/mixtral
- Ministral 3B docs: https://docs.mistral.ai/models/model-cards/ministral-3b-24-1
- Mistral 3 announcement: https://mistral.ai/news/mistral-3
- Phi-4 mini reasoning model card: https://huggingface.co/microsoft/Phi-4-mini-reasoning
- Phi-4 mini flash reasoning announcement: https://azure.microsoft.com/en-us/blog/reasoning-reimagined-introducing-phi-4-mini-flash-reasoning/
- SmolLM3-3B model card: https://huggingface.co/HuggingFaceTB/SmolLM3-3B
- SmolLM3 Transformers docs: https://huggingface.co/docs/transformers/model_doc/smollm3
- MobileLLM paper: https://arxiv.org/abs/2402.14905
- MobileLLM-R1 paper: https://arxiv.org/abs/2509.24945
- Apple OpenELM paper/release: https://machinelearning.apple.com/research/openelm
- Liquid LFM2-8B-A1B docs: https://docs.liquid.ai/docs/models/lfm2-8b-a1b
- `LiquidAI/LFM2-8B-A1B` model card: https://huggingface.co/LiquidAI/LFM2-8B-A1B
- GLM-4.5 paper: https://arxiv.org/abs/2508.06471
- Step-3 paper: https://arxiv.org/abs/2507.19427
- Step 3.5 Flash paper: https://arxiv.org/abs/2602.10604
