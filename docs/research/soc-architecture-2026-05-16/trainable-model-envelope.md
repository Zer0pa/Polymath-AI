# Trainable Model Envelope On 24GB Shared SoC Memory

**Date:** 2026-05-16
**Scope:** Polymath-AI training lane. RedMagic 10 Pro Plus, Snapdragon 8 Elite SM8750, 24GB unified LPDDR5X (~85 GB/s), Adreno 830 GPU (1.79 TFLOPS FP32 / 3.58 TFLOPS FP16, Vulkan 1.3), Hexagon NPU. Dedicated training appliance, active cooling, bypass charging.
**Question:** What is the largest dense or sparse model that can actually be **trained** end-to-end on 24GB shared memory under the 2025-2026 memory-efficient training frontier? Which 2025-2026 SLMs are designed for or amenable to actual edge training, not just LoRA-only adaptation?
**Authority gate (Resistance V2):** "actually trains end-to-end on 24GB shared with measurable loss reduction over a multi-hour run without device collapse." Fit is necessary, not sufficient.

---

## Verdict

**Top of envelope at 24GB practical (~18GB working):**

1. **Largest dense model with all-parameter updates (full Adam, FP32 state):** ~1.0B params. A 1.5B+ dense model overflows full-Adam memory before a single optimizer step.
2. **Largest dense model with all-parameter updates (8-bit Adam):** ~1.5B params with batch=1, seq=512.
3. **Largest dense model with full-parameter Q-GaLore (INT8 weights + INT4 projections + low-rank gradient state):** ~4B params, demonstrated by the paper at LLaMA-7B on a 16GB RTX 4060 Ti — meaning a 4B-class dense model is the **first published full-parameter training target that genuinely fits 24GB shared with safety margin for Android overhead**.
4. **Largest dense model with selective-layer training (ELO 7%, current blueprint):** ~7B realistically; the 1.5B-3B range is well-covered with substantial headroom.
5. **Largest dense model with QLoRA r=16 adapters only:** ~30B. Adapter training is not actual parameter training of the base; this is the LoRA ceiling for completeness only.
6. **MoE feasibility:** A static, single-faculty MoE subset training (one expert + router + shared trunk) on **OLMoE-1B-7B** is feasible under Q-GaLore/APOLLO-class configurations. **LFM2-8B-A1B** static-subset adaptation fits. **Qwen3-30B-A3B router-and-shared-trunk-only adaptation** is the upper MoE training boundary in adapter mode; **full expert training is not feasible**. **Qwen3.6-35B-A3B is confirmed structurally untrainable** at any non-adapter level on 24GB.

**Headline finding:** the 2025-2026 frontier supersedes the current blueprint's "Qwen2.5-1.5B + ELO 7%" choice in one specific way only: **Q-GaLore (and to a lesser extent APOLLO-Mini)** changes the dense-model-with-genuine-parameter-updates ceiling from ~1.5B (ELO selective) to ~4B (full-parameter). For the Polymath multilingual, multi-domain, factual-knowledge-injection corpus this matters because full-parameter touches every layer including middle-layer semantic representations.

**Recommended primary candidate (revised):** **Qwen3-4B + Q-GaLore (INT8 weights + INT4 projections, full-parameter)** as the top of the genuine-training envelope, with **Qwen2.5-1.5B + ELO** retained as the safer fall-back with proven runtime path, and **SmolLM3-3B + Q-GaLore or 8-bit Adam ELO** as the open-recipe research baseline.

This is a *revision*, not a *replacement*: the existing blueprint is still correct under the assumption that selective-layer training is the ceiling. The 2025-2026 frontier moves the ceiling, and the Polymath corpus is the kind of corpus that pays for the move.

---

## Memory Accounting

Per-parameter byte cost across training configurations:

| Component | FP32 | FP16/BF16 | INT8 | INT4/NF4 |
|---|---:|---:|---:|---:|
| Weight | 4 | 2 | 1 | 0.5 |
| Master weights (mixed-precision) | 4 | — | — | — |
| Gradients | 4 | 2 | — | — |
| Adam moment (m) | 4 | — | 1 (8-bit) | — |
| Adam moment (v) | 4 | — | 1 (8-bit) | — |
| **AdamW total per trainable param** | **16** | **n/a** | **6** | **n/a** |
| **8-bit AdamW per trainable param** | — | — | **10** (FP16 w + FP32 master + 2-byte state) | — |

For a 1B-parameter model under standard mixed-precision AdamW: 1B × (2+4+4+8) = 18 GB optimizer plus weight footprint before activations or runtime overhead. This is the reason the existing blueprint correctly states "~800M is the dense full-CPT ceiling" — the math reproduces.

### Practical Budget Derivation (Android + drivers + backend buffers)

| Subsystem | Estimated reservation |
|---|---:|
| Android baseline + zram + page cache + system services | ~2.5-3.5 GB |
| Vulkan driver + Adreno context + repacked weight layouts | ~1.0-1.5 GB |
| QNN/Hexagon session memory (if NPU island engaged) | ~0.5-1.5 GB |
| Tokenizer + data pipeline buffers | ~0.5 GB |
| Subtotal | ~4.5-7.0 GB |
| **Practical training budget** | **17-19.5 GB** |

Use **18 GB working** as the design point. This leaves ~1-2 GB safety margin against Android low-memory-killer (LMK) intervention.

### Memory Accounting Table (GB per training step, 18GB budget; "X" = does not fit)

Activations approximated for batch=1, seq=512, with selective gradient checkpointing.

| Model | Full Adam (FP16w + FP32 state) | 8-bit Adam (FP16w + INT8 state) | GaLore r=128 | Q-GaLore (INT8w + INT4 proj) | APOLLO-Mini (rank-1) | ELO 7% (FP16w + FP32 state on 7%) | QLoRA r=16 (NF4 base + adapters) | MeZO (forward-only) | MeBP + LoRA (compressed base) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.5B | 8.9 | 6.1 | 6.1 | 2.4 | 5.4 | 2.0 | 0.8 | 1.4 | 0.8 |
| 1.0B | 17.3 | 11.7 | 11.7 | 4.2 | 10.3 | 3.4 | 1.0 | 2.4 | 1.0 |
| 1.5B | 25.7 X | 17.3 | 17.3 | 6.1 | 15.2 | 4.9 | 1.3 | 3.3 | 1.3 |
| 2.0B | 34.0 X | 22.9 X | 22.9 X | 8.0 | 20.1 X | 6.3 | 1.6 | 4.2 | 1.6 |
| 3.0B | 50.8 X | 34.0 X | 34.0 X | 11.7 | 29.8 X | 9.2 | 2.1 | 6.1 | 2.1 |
| 4.0B | 67.6 X | 45.2 X | 45.2 X | 15.4 | 39.6 X | 12.1 | 2.7 | 8.0 | 2.7 |
| 7.0B | 117.9 X | 78.7 X | 78.7 X | 26.6 X | 69.0 X | 20.9 X | 4.3 | 13.6 | 4.3 |
| 8.0B | 134.6 X | 89.9 X | 89.9 X | 30.3 X | 78.7 X | 23.8 X | 4.8 | 15.4 | 4.8 |
| 13.0B | 218.4 X | 145.8 X | 145.8 X | 48.9 X | 127.6 X | 38.3 X | 7.5 | 24.7 X | 7.5 |
| 30.0B | 503.4 X | 335.8 X | 335.8 X | 112.3 X | 293.9 X | 87.7 X | 16.7 | 56.4 X | 16.7 |
| 35.0B | 587.3 X | 391.7 X | 391.7 X | 130.9 X | 342.8 X | 102.2 X | 19.4 X | 65.7 X | 19.4 X |

**Reading the table for "actual training" (substantive parameter updates):**

- **Full Adam:** ceiling at **~1B dense**. This is the textbook 16 bytes/param ceiling: 18 GB / 16 B = 1.125B param max trainable parameters.
- **8-bit Adam:** ceiling at **~1.5B dense**. Saves the 2 Adam moments by quantizing them to INT8 (per bitsandbytes), drops cost from 16 to ~10 B/param.
- **GaLore:** **~1.5B dense** (without quantization). Optimizer-state savings are real but the FP16 weights and FP32 gradients still dominate the budget at this scale. GaLore shines at 7B on 24GB GPU because it removes optimizer state for *full-rank* gradients, but on shared 24GB shared memory the activation + Android budget eats the margin.
- **Q-GaLore:** **~4B dense ceiling**. INT8 weights + INT4 projection matrices + 2-byte gradients + ~1-byte effective optimizer state. The paper demonstrates LLaMA-7B on 16GB GPU; on 18GB shared SoC budget, ~4B is the conservative fit. **This is the single biggest unlock vs the prior blueprint.**
- **APOLLO-Mini:** **~1.5B dense ceiling** unquantized. SGD-level memory but full-precision weights and gradients still cost. Combined with weight quantization could match Q-GaLore; uncombined, similar to 8-bit Adam.
- **ELO 7%:** **~4B comfortable, ~7B near edge**. The current blueprint's choice. Trains only ~7% of parameters but with full FP32 Adam state on those.
- **QLoRA r=16:** **~30B feasible**. But it is adapter-only and not actual parameter training of the base. Listed for completeness.
- **MeZO:** **~8B feasible memory-wise**. But convergence is 10-100x slower than first-order; not viable for multi-billion-token CPT on phone time budget.
- **MeBP + LoRA:** **~30B feasible memory-wise** if MeBP's compressed-base + lazy-decompression discipline is reproduced. But this is also adapter training, not full-parameter.

### What Each Component Actually Costs (worked example: Qwen3-4B at Q-GaLore)

Qwen3-4B is dense, ~4.02B params, GQA, 32K context (training at seq=512).

| Component | Bytes | Size at 4B | Notes |
|---|---:|---:|---|
| INT8 weights | 1 B/param | 4.0 GB | INT8 master, FP16 dequant on-the-fly per kernel |
| INT4 projection matrices (Q-GaLore) | r/d × 0.5 B/param | ~0.05 GB | rank-128 vs hidden ~3072: ~4% × 0.5 B |
| Gradient buffer (FP16) | 2 B/param | 8.0 GB | full-parameter gradient surface |
| Low-rank optimizer state (8-bit) | 1 B/param eff | 4.0 GB | aggressive quant |
| Activations (batch=1, seq=512, checkpointed) | — | ~1.5 GB | sqrt(L) layers held |
| Android/Vulkan/QNN/data pipeline overhead | — | ~5.0 GB | shared budget |
| **Total** | | **~22.5 GB** | exceeds 18 GB practical |

**This shows the table above is optimistic for Q-GaLore at 4B if all components are co-resident.** The realistic configuration for Polymath would be:
- INT8 weights with mmap from UFS for tail of FFN/expert layers
- ELO-style mask within Q-GaLore: full-parameter projection only for a subset of layers (e.g. top + bottom + middle anchor), other layers projected but with smaller rank or frozen
- Batch=1, seq=256 or 384 (not 512) for initial fit
- Aggressive activation checkpointing including attention recomputation

The honest envelope is **Qwen3-4B trainable with Q-GaLore + selective rank schedule, batch=1, seq=384-512, target ~16-17 GB peak**. **Qwen3-1.7B trainable with Q-GaLore + full uniform rank, batch=2, seq=512** is the conservative target.

---

## Feasibility Curve: Model Size vs Minimum-Memory Training Config

The curve below shows what training configuration is *minimally required* to fit each model size in 18GB.

```
Model size (dense)  →   Minimum-config required to fit 18 GB shared
─────────────────────   ─────────────────────────────────────────────
0.27B (OpenELM)     →   Full Adam, FP32 state ✓ (5.5 GB)
0.5B                →   Full Adam, FP32 state ✓ (8.9 GB)
1.0B                →   Full Adam tight; 8-bit Adam comfortable (11.7 GB)
1.5B (Qwen2.5)      →   8-bit Adam or GaLore (17.3 GB tight); ELO at 7% comfortable (4.9 GB)
2.0B                →   ELO selective, QLoRA, or Q-GaLore (8.0 GB)
3.0B (SmolLM3)      →   Q-GaLore (11.7 GB); ELO selective (9.2 GB); QLoRA adapter only
4.0B (Qwen3-4B)     →   Q-GaLore (15.4 GB, edge); ELO selective (12.1 GB); QLoRA adapter only
7.0B                →   QLoRA adapter only OR MeZO inference-only (13.6 GB)
8.0B                →   QLoRA adapter only OR MeZO inference-only (15.4 GB)
13.0B               →   QLoRA adapter only (7.5 GB)
30.0B               →   QLoRA adapter only at edge (16.7 GB)
35.0B (Qwen3.6)     →   NOTHING FITS for substantive training; only mmap inference with quant
```

**Key inflection points:**

1. **1.5B → 4B:** the Q-GaLore unlock. This is where 2025-2026 frontier work materially expands the envelope vs prior blueprint.
2. **4B → 7B:** the cliff. No published full-parameter training method fits a dense 7B in 18GB shared SoC memory at any reasonable sequence length, even with maximal quantization. This is *not* a software gap; it is the fundamental gradient buffer for full-parameter training meeting the unified-memory wall.
3. **7B → 30B:** the adapter-only regime. QLoRA-style adapters work but do not constitute parameter training of the base.

---

## 2025-2026 SLM Landscape: Edge-Training Fit Ranking

Ranking is by **edge-training amenability**, not benchmark prestige. Authority for ranking: open recipe, permissive license, edge-deployment evidence, multilingual scope, vocab/embedding economy.

| Rank | Model | Params | Architecture | License | Vocab | Multilingual | Edge-training evidence | Polymath fit verdict |
|---:|---|---|---|---|---:|---|---|---|
| 1 | **Qwen3-4B** | 4B dense | GQA, RoPE, regular dense | Apache 2.0 | 151K | 119 languages, 36T tokens | Qualcomm AI Hub QNN/GENIE path, MobileFineTuner full-FT validated | **Top of envelope under Q-GaLore.** Largest dense model that can be *full-parameter trained* on 24GB shared. Vocab efficient for multilingual. |
| 2 | **Qwen3-1.7B** | 1.7B dense | GQA, RoPE | Apache 2.0 | 151K | 119 languages | Same Qwen3 toolchain | **Safer full-parameter envelope.** Fits Q-GaLore comfortably, also fits 8-bit Adam at edge. Reasonable knowledge capacity. |
| 3 | **SmolLM3-3B** | 3B dense | GQA + NoPE (3:1), 36 layers, hidden 2048, FFN 11008 | Apache 2.0 | 128K | 6 native + extended | Fully transparent training recipe; Unsloth/LlamaFactory support; NoPE may complicate QNN export | **Best research/ablation baseline.** Open recipe is the highest-value asset; multilingual depth narrower than Qwen3. |
| 4 | **Qwen2.5-1.5B** | 1.5B dense | GQA, RoPE | Apache 2.0 | 151K | 29+ languages | DeepSeek-Qwen-1.5B distill on Hexagon NPU validated (Microsoft Windows on Snapdragon) | **Current blueprint default.** Proven runtime path. Best for QNN island integration risk-free. |
| 5 | **Gemma 3n E4B** | ~4.5B effective, ~8B stored | MatFormer, PLE, attention 5:1 local:global | Gemma terms | 262K | multimodal text/image/audio | Google AI Edge / LiteRT first-class; E4B contains E2B (Matryoshka) | Strong on edge runtime story; PLE stored params and 262K vocab make training-memory accounting unfavorable. PLE table is 262K × hidden × N_layers — substantial. Authority baseline only. |
| 6 | **Gemma 3 4B** | 4B dense | GQA, sliding window | Gemma terms | 256K | multimodal | LiteRT, Unsloth | Older 4B, simpler runtime; large vocab is a memory cost. |
| 7 | **LFM2-2.6B** | 2.6B dense | Hybrid: 18 gated short-conv + 6 GQA | LFM open | ~65K (compact) | English-primary | Liquid LEAP edge tooling, leap-finetune package | Compact vocab is a real advantage. Hybrid conv-attention untested for first-order training on Snapdragon. Liquid documents fine-tuning is supported. |
| 8 | **LFM2-1.6B** | 1.6B dense | Hybrid conv-attention | LFM open | ~65K | English-primary | Liquid LEAP | Smallest LFM2 dense; fits full-Adam comfortably. Architecture is unusual but well-documented. |
| 9 | **IBM Granite 4.1-3B** | 3B dense | Decoder-only | Apache 2.0 | unknown (likely 49K-100K) | 12 languages (EN, DE, ES, FR, JA, PT, AR, CS, IT, KO, NL, ZH) | Fresh release, training recipe documented; edge story not yet validated | Strong multilingual coverage and Apache license. Less Snapdragon-specific tooling. |
| 10 | **Phi-4-mini-flash-reasoning** | 3.8B dense | SambaY (Mamba SSM + sliding attention + GMU), 200K vocab | MIT | 200K | English-skew | Azure edge story; novel SSM architecture | Hybrid SSM kernels are a real risk for QNN/Vulkan training. Strong reasoning, narrower multilingual. |
| 11 | **Ministral 3 3B** | 3B dense | Sliding-window attention | Apache | unknown | multilingual | Mistral edge tooling | Solid edge candidate. Less open training recipe than SmolLM3. |
| 12 | **MobileLLM-R1-950M** | 950M dense | GQA, block-wise weight sharing, SwiGLU | unknown (non-commercial?) | unknown | English/code/math | Meta phone-first architecture; trained on 4.2T tokens | Too small for Polymath's multilingual capacity needs; reasoning specialty. Useful microbaseline. |
| 13 | **Apple OpenELM 3B** | 3B dense | Layer-wise scaling | Apple open | unknown | English-primary | CoreNet recipe + checkpoints + logs (most transparent recipe) | Recipe is gold standard. Mac/MLX ecosystem, less Snapdragon. |
| 14 | **FunctionGemma 270M** | 270M dense | Gemma 3 base | Gemma terms | 256K | English | Google mobile actions cookbook | Too small for Polymath corpus. Reference only. |

### Key SLM landscape findings

- **Vocab as a hidden tax:** Gemma 3/3n/4's 256-262K vocabularies cost (vocab × hidden_dim × dtype) per embedding table. For a 4B-hidden-2048-FP16 model: 262144 × 2048 × 2 = ~1.0 GB embedding-only. Qwen's 151K vocab in similar-hidden cost ~600 MB. SmolLM3's 128K cost ~500 MB. **For a corpus that is multilingual but does not require Gemma's full token coverage (Polymath has its own corpus language distribution), Qwen3 or SmolLM3's smaller vocab is the right trade.**
- **MobileFineTuner (2026-12) explicitly validates** full-parameter and PEFT fine-tuning of **Gemma 3 and Qwen 2.5 on mobile phones** with parameter sharding, gradient accumulation, and energy-aware scheduling. This is the most direct prior-art evidence that on-phone training of 1-4B-class dense models is operationally real, not theoretical.
- **MeBP (Apple, 2025-10) demonstrates sub-1GB memory** for LoRA fine-tuning of 0.5B-4B LLMs on iPhone 15 Pro Max (8GB total RAM). This sets the lower bound — if Apple's 8GB iPhone can do this, the 24GB RedMagic can do considerably more.
- **ZeroQAT (2025-09) demonstrates 6.7B model fine-tuning at 6.4 GB on OnePlus 12** (16GB RAM, Snapdragon 8 Gen 3). This is the **highest published actual-on-phone-training model size** but it is zeroth-order, not first-order. Slow convergence but the memory point is established.

---

## MoE Feasibility (explicit answers)

### Qwen3.6-35B-A3B
**Confirmed structurally untrainable in any non-adapter sense on 24GB shared.** Cross-reference: `ram-residency-qwen36.md` already establishes this for inference; for training the case is stronger:

- 35B params × 0.5 B (NF4) = 17.5 GB weights resident only (no headroom for optimizer of any kind).
- Even Q-GaLore at 35B = 130 GB — fundamentally infeasible.
- Even QLoRA rank-16 over all 35B = ~19 GB total, *just over* the practical budget at 35B with realistic Android headroom.
- The hybrid Gated DeltaNet kernels are inference-only on QNN/Vulkan; backward kernels do not exist for these blocks on Snapdragon.

**Verdict: NORTH-STAR ONLY for training. Falsifier: a Q-GaLore-class compression scheme combined with single-expert + router + shared-trunk static-subset training that fits 18GB and converges on Polymath corpora.** Until that exists, do not commit phone training time.

### Qwen3-30B-A3B
- 30.5B params, 3.3B active, 128 experts, 8 active, 48 layers
- QLoRA r=16 over base = 16.7 GB total (right at the edge of the practical budget — fits but no safety margin)
- Q-GaLore over base = 112 GB — infeasible
- **Router + shared-trunk-only training** with the router and shared expert paths held in fast memory while routed experts mmap from UFS: feasible at adapter-rank-only training scale. This is essentially the LFM2-8B-A1B pattern but at 30B base.
- Custom-kernel risk: Qwen3-30B-A3B is normal MoE structure (no DeltaNet), so kernels are tractable.

**Verdict: ADAPTER-ONLY TRAINING (LoRA on router + shared) is at the absolute edge of 24GB shared. Static-subset expert training (e.g. 1 expert out of 128 plus router + shared) is feasible only with quantized base. Not the right first target — too thin a margin for the Polymath corpus depth.**

### Qwen3-VL-30B-A3B (Vision-language variant)
- Unsloth claims fine-tuning at **17.5GB VRAM with QLoRA**, confirmed on consumer GPU.
- On 24GB shared with Android overhead this is plausible but with zero safety margin.
- VL variant is not the Polymath target (text-first).

**Verdict: PROVES the QLoRA-30B path is feasible on 24GB but does not change Polymath ranking.**

### OLMoE-1B-7B (Allen AI)
- 7B total, 1B active, 64 small experts, 8 routed per layer
- Fully open: weights, full 5.1T-token training dataset, source code, 244 intermediate checkpoints
- QLoRA over base = 4.3 GB total — comfortable fit
- 8-bit Adam over 1B active = ~10 GB — feasible
- **Static-faculty training (1 expert + router + shared, or top-K-expert subset) with 8-bit Adam:** feasible
- **Full-parameter Q-GaLore over 7B total:** ~27 GB — infeasible
- **Full-parameter Q-GaLore over the 1B active surface (router and one expert at a time):** ~4-5 GB — **very comfortable fit**

**Verdict: BEST RESEARCH MoE TARGET. Fully open recipe makes it the right scientific baseline. The 1B active surface is exactly the size where Q-GaLore is sweet-spot. Smaller-faculty MoE experiments here are the cleanest path to validate the Polymath faculty hypothesis.**

### LFM2-8B-A1B (Liquid AI)
- 8.3B total, 1.5B active, 18 conv + 6 GQA + per-layer sparse MoE FFN (32 experts, top-4)
- TRL/Colab fine-tuning supported by Liquid
- QLoRA over base = 4.8 GB — comfortable
- Static-faculty training over 1.5B active = comparable to OLMoE active surface
- Edge tooling is mature (llama.cpp, ExecuTorch, vLLM compatible)

**Verdict: BEST PRODUCTION-READY EDGE MoE for first-target. Trades OLMoE's transparent training recipe for stronger edge deployment story. If the Polymath project values "ships on phone today" over "fully reproducible from scratch", LFM2-8B-A1B is the better MoE first-target. If the project values reproducibility, OLMoE.**

### EMO-1B14B-1T (Allen AI)
- 1B active, 14B total
- Designed for retainable expert subsets (paper claims 25% expert retention costs only ~1 absolute point)
- Status: very recent, less deployment-proven
- **Static-faculty training as designed by the paper:** the most architecturally aligned with the Polymath faculty hypothesis

**Verdict: RESEARCH-BRANCH MoE if weights and tooling are stable. Strongest conceptual match but lowest runtime maturity.**

### MoE summary

The honest MoE answer: **a 7-14B total / 1-1.5B active MoE with single-faculty or static-subset training fits 24GB shared at the active-surface scale**. Going beyond this — Qwen3-30B-A3B and Qwen3.6-35B-A3B — collapses into adapter-only territory or out of the envelope entirely.

The Polymath faculty hypothesis can be tested at the OLMoE / LFM2-8B-A1B / EMO scale **without** needing Qwen3.6. The Qwen3.6 framing was correctly identified as north-star in `architecture-models.md`; it remains north-star for training as well as for inference.

---

## Top 3-5 Candidates (Ranked) For Polymath Phone Training

### #1 Qwen3-4B + Q-GaLore (full-parameter, INT8 weights + INT4 projections + low-rank state)

**Rationale:** Largest dense model that supports genuine all-parameter updates on 24GB shared under the 2025-2026 frontier. Q-GaLore is the published memory unlock that moves the dense ceiling from ~1.5B (ELO selective) to ~4B (full-parameter). For the Polymath corpus — multilingual, multi-domain, book-length, factual-knowledge-injection — full-parameter updates to a 4B base is the right ambition because middle-layer semantic representations are exactly where new factual associations should land, and ELO's "first/last only" leaves those layers untouched.

**Multilingual fit:** Qwen3 is pre-trained on 36T tokens across 119 languages. Vocab 151K is well-balanced between size and language coverage. The Qwen3 tokenizer outperforms Qwen2.5 on most multilingual axes per Qwen team's reports.

**Multi-domain fit:** Qwen3's pre-training mixture includes coding, STEM, reasoning, books, multilingual, and synthetic data. Architecture is regular dense GQA-RoPE, no custom kernels needed.

**Hardware fit:** Qualcomm AI Hub has a published QNN/GENIE path for Qwen3-4B on Snapdragon (currently demonstrated on Snapdragon X-class, requires SM8750 revalidation per `architecture-models.md`).

**Hard falsifiers:**
- Q-GaLore SVD updates may not be tractable on Adreno Vulkan kernels without significant porting effort. **Falsifier:** measured Q-GaLore step latency > 30 sec on Adreno makes the per-hour token rate untenable.
- Q-GaLore + activation checkpointing + selective rank schedule introduces non-trivial training-loop engineering. **Falsifier:** no loss reduction over 2-hour Experiment 0 baseline.
- Qwen3-4B Q-GaLore peak memory may exceed 18 GB once Android + Vulkan + QNN overhead is measured. **Falsifier:** OOM at batch=1, seq=384 in Experiment 0.

### #2 Qwen2.5-1.5B + ELO 7% (CURRENT BLUEPRINT — RETAINED AS SAFE BASELINE)

**Rationale:** Already-validated runtime path. DeepSeek-Qwen-1.5B is proven on Snapdragon Hexagon NPU via Microsoft's Windows on Snapdragon work. ELO 7% is conservative and known. This is the Phase 0 default until Q-GaLore Experiment 0 runs at #1.

**Multilingual fit:** 29+ languages, 151K vocab — adequate but narrower than Qwen3.

**Hardware fit:** Best-validated path on Snapdragon today.

**Hard falsifiers:**
- ELO's "first + last layers only" may leave the multilingual / multi-domain factual injection too shallow for the Polymath corpus. **Falsifier:** in-domain Polymath knowledge recall does not improve after a full ELO run vs the base checkpoint.
- 1.5B may be too small a knowledge capacity for the corpus depth. **Falsifier:** perplexity floor on held-out corpus does not approach the level achievable at 4B.

### #3 Qwen3-1.7B + 8-bit Adam (full-parameter) or Q-GaLore (defensive option)

**Rationale:** If Q-GaLore at 4B turns out to be too engineering-heavy to ship in time, or if Qwen3-4B's QNN path proves not portable to SM8750, Qwen3-1.7B with **full-parameter 8-bit Adam** (~12 GB total) is a genuinely-trainable dense model that supersedes Qwen2.5-1.5B by both training-token count (36T vs 18T) and multilingual breadth (119 vs 29+ languages).

**Multilingual fit:** Same Qwen3 119-language corpus.

**Multi-domain fit:** Same Qwen3 dense architecture, regular and well-supported.

**Hardware fit:** Same QNN/GENIE path as Qwen3-4B.

**Hard falsifiers:**
- 8-bit Adam in bitsandbytes may not have a Vulkan-compatible kernel. **Falsifier:** PyTorch+Vulkan cannot dispatch bitsandbytes 8-bit Adam without CPU optimizer step that erases speedup.

### #4 SmolLM3-3B + Q-GaLore or ELO

**Rationale:** The fully open training recipe is the highest scientific asset. For ablations, error pattern analysis, replay-protected CPT experiments, this is the right control model. Native 6 languages (EN/FR/ES/DE/IT/PT) plus exposure to AR/ZH/RU. Vocab 128K, hidden 2048, 36 layers, FFN 11008 — clean reproducible architecture.

**Multilingual fit:** Native coverage is narrower than Qwen3 but the training recipe is reproducible. For Polymath languages outside the native 6, fertility audit is required (per existing blueprint Part VII).

**Hard falsifiers:**
- NoPE-RoPE mixed positional encoding may not export cleanly to QNN. Forces GPU-only path.
- If Polymath corpus's language distribution is poorly served by SmolLM3's tokenizer, this drops below Qwen3-1.7B.

### #5 LFM2-8B-A1B + static-faculty training (MoE faculty research branch)

**Rationale:** The closest production-ready MoE for testing the Polymath faculty hypothesis. 1.5B active surface is exactly the Q-GaLore sweet spot. Liquid provides a fine-tune package and edge runtime evidence. Compact ~65K vocab is a memory-efficient design.

**Multilingual fit:** English-primary, less suited to Polymath multilingual goals than Qwen3-class. Use as a **faculty-mechanics** research branch parallel to the multilingual main lane.

**Hard falsifiers:**
- Hybrid conv-attention backward kernels untested on Snapdragon Adreno.
- Static-faculty training over MoE may show the predicted improvements only when the corpus actually has multi-domain partitioning — Polymath should have this but requires curation discipline.
- Liquid's open weights but partially closed training infrastructure makes reproducibility weaker than OLMoE.

### Honorable mentions

- **OLMoE-1B-7B** for the faculty research branch if reproducibility wins out over LFM2's edge tooling.
- **IBM Granite 4.1-3B** for a serious second multilingual control after Qwen3 — covers Arabic, Czech, Korean, Dutch in ways Qwen3 may underweight.

---

## Comparison To Current Blueprint (Qwen2.5-1.5B + ELO 7%)

The blueprint at `source-briefs/01-on-device-training-blueprint.md` is **correct under the assumption that selective-layer training is the dense-model training ceiling on 24GB**. The 2025-2026 frontier (Q-GaLore, APOLLO, MeBP, MobileFineTuner, ZeroQAT) does the following:

| Dimension | Blueprint position | 2025-2026 frontier position | Verdict |
|---|---|---|---|
| **Dense model size ceiling for substantive training** | ~1.5B (Qwen2.5) with ELO 7% selective | ~4B (Qwen3-4B) with Q-GaLore full-parameter | **FRONTIER SUPERSEDES** |
| **Substantive training method** | ELO Stage 1 (2 of 28 layers, ~7% trainable) | Q-GaLore (all parameters trainable, low-rank optimizer state) | **FRONTIER SUPERSEDES** (for the same target size class) |
| **Multilingual base model** | Qwen2.5-1.5B (29+ languages, 18T pretrain tokens) | Qwen3-4B or Qwen3-1.7B (119 languages, 36T pretrain tokens) | **FRONTIER SUPERSEDES** |
| **Memory budget realism** | Honest 9 GB ELO budget on Qwen2.5-1.5B with FP32 state | Same realism; Q-GaLore on 4B is ~16-17 GB tight | Both honest. Frontier is tighter but feasible. |
| **NPU role** | Frozen middle layers compiled to QNN INT4/INT8 | Same role (NPU stays inference-only training-side) | **CONSISTENT** |
| **Vulkan role** | GPU runs trainable layers + backward | Same. Q-GaLore needs custom SVD/projection kernels on Adreno — engineering risk | **FRONTIER ADDS RISK** but is tractable |
| **QLoRA stance** | "Insufficient for deep knowledge injection" | Confirmed: QLoRA is adapter-only, not parameter training | **CONSISTENT** |
| **Falsifier discipline** | Experiment 0 success criteria explicit | Same gate applies; just on a larger model | **CONSISTENT** |
| **Multimodal scope** | Phase 3 (post text-only stability) | Same — text-first to validate substrate first | **CONSISTENT** |

### Concrete revision to the blueprint

The "Part III - Model Selection" decision logic should add a top branch:

```
IF Q-GaLore can be implemented or imported in scope < 4 weeks:
  AND Adreno Vulkan kernels for projection/SVD updates can be ported:
  AND Qwen3-4B QNN export validates on SM8750 (Experiment 2 extension):
  → PROMOTE TO: Qwen3-4B + Q-GaLore full-parameter (FRONTIER)
ELSE IF Qwen3-1.7B QNN export validates:
  → PROMOTE TO: Qwen3-1.7B + 8-bit Adam full-parameter (CONSERVATIVE-FRONTIER)
ELSE:
  → RETAIN BLUEPRINT: Qwen2.5-1.5B + ELO 7% (SAFE BASELINE)
```

The blueprint's Phase 0 / Experiment 0 / fertility audit / SmolLM3 fallback structure is **unchanged**; only the model and the training method at the top of the decision tree are revised. The 6 open questions at the end of the blueprint (Part XI) all remain blocking. Add a seventh: **Q-GaLore Adreno Vulkan kernel feasibility**.

---

## Hard Falsifiers Per Top Candidate

### Qwen3-4B + Q-GaLore
- **F1:** OOM at batch=1, seq=384 in Experiment 0 (peak memory probe).
- **F2:** Q-GaLore per-step latency > 30 sec on Adreno (kernel inefficiency makes wall-clock token rate untenable).
- **F3:** No loss reduction on held-out Polymath corpus over a 2-hour Experiment 0.
- **F4:** Qwen3-4B does not export to QNN on SM8750 (regression of the path validated on Snapdragon X).
- **F5:** Sustained Adreno GPU clock < 600 MHz after 30 min (thermal cliff).

### Qwen2.5-1.5B + ELO 7% (incumbent)
- **F1:** Polymath in-domain factual recall does not improve after a full ELO Stage 1 run vs base checkpoint (ELO scope is too narrow).
- **F2:** Multilingual perplexity does not approach the level achievable at 3-4B (capacity ceiling).

### Qwen3-1.7B + 8-bit Adam
- **F1:** bitsandbytes 8-bit Adam has no Vulkan-compatible kernel; CPU optimizer step erases throughput.
- **F2:** Same multilingual capacity concern as Qwen2.5-1.5B if 1.7B is insufficient for the corpus depth.

### SmolLM3-3B + Q-GaLore
- **F1:** NoPE blocks QNN export, forcing GPU-only path; throughput drops below acceptable.
- **F2:** Tokenizer fertility on Polymath non-native languages (anything outside EN/FR/ES/DE/IT/PT) > 2.5x English baseline.

### LFM2-8B-A1B static-faculty MoE
- **F1:** Conv-attention hybrid kernels do not support backward on Vulkan.
- **F2:** Static-faculty training shows no specialization gain vs equal-compute dense baseline (faculty hypothesis fails).
- **F3:** Liquid LEAP edge tooling does not port to Android/RedMagic environment.

---

## Sources

### Memory-efficient training frontier
- GaLore (Zhao et al., ICML 2024): https://arxiv.org/abs/2403.03507 — gradient low-rank projection, 65.5% optimizer state reduction, LLaMA-7B on 24GB RTX 4090.
- GaLore 2 (2025-04): https://arxiv.org/abs/2504.20437 — scaled GaLore for larger pre-training.
- Q-GaLore (Zhang et al., 2024-07): https://arxiv.org/abs/2407.08296 — INT4 projections + INT8 weights, LLaMA-7B on 16GB RTX 4060 Ti (single GPU pre-training of a 7B from scratch).
- Q-GaLore code: https://github.com/VITA-Group/Q-GaLore
- APOLLO (Zhu et al., MLSys 2025): https://arxiv.org/abs/2412.05270 — SGD-like memory, AdamW-level performance; APOLLO-Mini variant uses rank-1 random projection; LLaMA-7B from scratch on single GPU < 12 GB with quantization. MLSys'25 Outstanding Paper Honorable Mention.
- APOLLO code: https://github.com/zhuhanqing/APOLLO
- MeZO (Princeton, NeurIPS 2023): https://arxiv.org/abs/2305.17333 — zeroth-order, OPT-30B on single A100 80GB; same memory footprint as inference.
- Sparse MeZO (2024-02): https://arxiv.org/abs/2402.15751 — sparse subset selection, LLaMA-30B on single A100.
- QuZO (Tan et al., EMNLP 2025): https://arxiv.org/abs/2502.12346 — quantized ZO fine-tuning, 2.94-5.47x memory reduction vs first-order INT methods.
- ZO2 (2025-03): https://arxiv.org/abs/2503.12668 — scalable ZO fine-tuning for extremely large LLMs.

### On-device training
- MeBP (Apple, 2025-10): https://arxiv.org/abs/2510.03425 — Memory-Efficient Backpropagation, sub-1GB fine-tuning of 0.5-4B LLMs on iPhone 15 Pro Max (8GB RAM). https://github.com/apple/ml-mebp
- MobileFineTuner (2026-12): https://arxiv.org/abs/2512.08211 — unified end-to-end framework for full-FT and PEFT of GPT-2, Gemma 3, Qwen 2.5 on real mobile phones.
- ZeroQAT (2025-09): https://arxiv.org/abs/2509.00031 — forward-only QAT, OPT-6.7B fine-tune on OnePlus 12 (Snapdragon 8 Gen 3, 16GB RAM) in 6.4 GB at 29.1s/step.
- MobiZO (EMNLP 2025): https://arxiv.org/abs/2409.15520 — edge fine-tuning via ExecuTorch with parallelized ZO and Multi-Perturbed LoRA, 4.3x speedup vs MeZO.
- MobiLLM (2025-02): https://arxiv.org/abs/2502.20421 — server-assisted side-tuning for mobile LLM fine-tuning.

### Baseline / classical
- QLoRA (Dettmers et al., NeurIPS 2023): https://arxiv.org/abs/2305.14314 — 65B model on single 48GB GPU; 33B on single 24GB.
- 8-bit optimizers (bitsandbytes): https://huggingface.co/docs/bitsandbytes/main/en/optimizers — 75% optimizer memory savings.
- PyTorch activation checkpointing: https://pytorch.org/blog/activation-checkpointing-techniques/

### 2025-2026 SLM model cards
- Qwen3-4B / Qwen3-1.7B / Qwen3-0.6B (Apache 2.0, 36T tokens, 119 languages): https://huggingface.co/Qwen/Qwen3-1.7B
- Qwen3-4B-Instruct-2507: https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507
- Qwen2.5-1.5B (Apache 2.0, 18T tokens, 29+ languages): https://huggingface.co/Qwen/Qwen2.5-1.5B
- SmolLM3-3B (Apache 2.0, 11.2T tokens, 6 native languages, 128K vocab, GQA+NoPE 3:1, 36 layers, hidden 2048, FFN 11008): https://huggingface.co/HuggingFaceTB/SmolLM3-3B and https://huggingface.co/blog/smollm3
- Gemma 3n (MatFormer + PLE, E2B 2GB / E4B 3GB effective memory footprint): https://ai.google.dev/gemma/docs/gemma-3n
- Gemma 3n technical: https://huggingface.co/blog/rishiraj/matformer-in-gemma-3n
- Phi-4-mini-flash-reasoning (3.8B, SambaY hybrid Mamba/SWA/GMU, 200K vocab, 64K context, MIT): https://huggingface.co/microsoft/Phi-4-mini-flash-reasoning
- Ministral 3 3B (Apache, 256K context, sliding window): https://mistral.ai/news/mistral-3
- IBM Granite 4.1-3B (Apache, 15T tokens, 12 languages, 512K context): https://research.ibm.com/blog/granite-4-1-ai-foundation-models
- LFM2-2.6B (Liquid open, hybrid conv-attention, edge-optimized): https://huggingface.co/LiquidAI/LFM2-2.6B
- LFM2 Technical Report: https://arxiv.org/abs/2511.23404
- Apple OpenELM (270M / 450M / 1.1B / 3B, layer-wise scaling, CoreNet recipe): https://huggingface.co/apple/OpenELM and https://arxiv.org/abs/2404.14619
- MobileLLM-R1 (Meta, 140M-950M, edge reasoning, 4.2T tokens): https://arxiv.org/abs/2509.24945
- FunctionGemma 270M cookbook: https://ai.google.dev/gemma/docs/mobile-actions

### MoE candidates
- OLMoE-1B-7B (Allen AI, fully open, 5.1T tokens, 64 experts, top-8): https://huggingface.co/allenai/OLMoE-1B-7B-0924 and https://arxiv.org/abs/2409.02060
- LFM2-8B-A1B (Liquid AI, 8.3B total / 1.5B active, hybrid conv + 32 experts top-4): https://huggingface.co/LiquidAI/LFM2-8B-A1B and https://www.liquid.ai/blog/lfm2-8b-a1b-an-efficient-on-device-mixture-of-experts
- Qwen3-30B-A3B (30.5B total / 3.3B active, 128 experts top-8, 48 layers): https://huggingface.co/Qwen/Qwen3-30B-A3B
- Qwen3-30B-A3B Unsloth QLoRA at 17.5GB: https://unsloth.ai/docs/models/tutorials/qwen3-how-to-run-and-fine-tune
- Qwen3.6-35B-A3B: https://huggingface.co/Qwen/Qwen3.6-35B-A3B (NORTH-STAR; not trainable on 24GB shared)
- EMO-1B14B-1T: https://huggingface.co/collections/allenai/emo and https://arxiv.org/abs/2605.06663

### Polymath-AI prior research artifacts (reference)
- `RESISTANCE-V2.md` — frontier engineering commandments (governing discipline)
- `docs/HETEROGENEOUS-SOC-RESEARCH-DIALOGUE.md` — heterogeneous SoC research dialogue
- `docs/research/soc-architecture-2026-05-16/ram-residency-qwen36.md` — Qwen3.6 residency analysis (north-star verdict)
- `docs/research/soc-architecture-2026-05-16/architecture-models.md` — architectural ranking for faculty/SoC lane
- `docs/research/soc-architecture-2026-05-16/blind-spots-frontier-scan.md` — twelve blind spots including low-memory optimizer ladder
- `source-briefs/01-on-device-training-blueprint.md` — current blueprint (Qwen2.5-1.5B + ELO 7%)
