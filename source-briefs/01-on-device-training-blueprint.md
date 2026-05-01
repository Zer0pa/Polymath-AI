# Polymath On-Device Training System
## Blueprint & Engineering Specification
### REDMAGIC 10 Pro+ · Snapdragon 8 Elite · 24GB LPDDR5X

**Document class:** Pre-PRD Research Synthesis — Blueprint / Engineering Specification  
**Status:** Living document — supersedes all prior research briefs in this thread  
**Purpose:** To synthesize every finding from this research thread into a single logically coherent, source-cited blueprint that is immediately actionable as input to a PRD, an engineering sprint plan, or a deep-research agent prompt  
**Audience:** Product engineers, ML engineers, systems architects, and research agents operating downstream of this investigation

---

## Executive Summary

The central question this document resolves is: **what is the optimal end-to-end system for training a multilingual "Polymath" language model on a REDMAGIC 10 Pro+ running Snapdragon 8 Elite with 24GB of unified LPDDR5X memory?**

The answer, converged from hardware analysis, published ML research, runtime ecosystem evidence, and systems architecture reasoning, is a specific and testable stack:

- **Model:** Qwen2.5-1.5B (primary) or SmolLM3-3B (secondary), selected for multilingual breadth, tokenizer quality, memory fit, and Snapdragon deployment signals
- **Training method:** ELO (Efficient Layer-Specific Optimization) selective continual pretraining — trains only the first and last transformer layers, reducing gradient compute to ~7% of full CPT
- **Corpus strategy:** Model-based multilingual data selection, curriculum scheduling, and catastrophic-forgetting replay
- **Runtime:** Vulkan compute on Adreno 830 for gradient-carrying layers, QNN/Hexagon for frozen quantized middle layers, Oryon CPU for orchestration
- **Validation:** A 2-hour Experiment 0 on-device before any corpus investment

This is not the largest model that barely fits. It is not QLoRA because it is cheap. It is a **principled, hardware-matched, research-validated system** designed to exploit the specific heterogeneous compute profile of this device.

---

## Part I — Hardware Ground Truth

### 1.1 Snapdragon 8 Elite — Verified Specifications

The REDMAGIC 10 Pro+ is built on the Qualcomm Snapdragon 8 Elite (SM8650), fabricated on TSMC's 3nm process and released October 2024.

**CPU — Qualcomm Oryon (Phoenix)**

| Core cluster | Count | Clock | Role in this system |
|---|---|---|---|
| Phoenix L (performance) | 2 | 4.32 GHz | Optimizer steps, orchestration dispatch |
| Phoenix M (efficiency) | 6 | 3.53 GHz | Data pipeline, tokenization, logging |
| L1 cache | — | 192 KB | Per-core |
| L2 cache | — | 12 MB | Shared |
| L3 cache | — | 8 MB | Shared |
| ISA | — | ARMv9.2-A | NEON SIMD, SVE2 available |
| TDP (sustained) | — | ~8W | Thermal design point |

The Oryon CPU is the only compute unit that should touch optimizer state — Adam momentum and variance tensors for the ELO-trainable layers live here.

**GPU — Adreno 830**

| Metric | Value | Source note |
|---|---|---|
| Clock speed | 1,100 MHz (sustained) | Corrected from earlier 1,250 MHz estimate |
| FP32 throughput | **1.79 TFLOPS** | This is the training-relevant figure — corrects prior brief's error of citing FP16 as FP32 |
| FP16 throughput | 3.58 TFLOPS | For forward-pass inference operations |
| GPU slices | 3 | Tiled architecture (TBDR) |
| Vulkan support | 1.3 | Full compute shader support |
| OpenCL support | 3.0 Full Profile | Deprecated path — Vulkan preferred |
| L2 (GPU) | 12 MB shared | With CPU complex |
| Unified memory access | Yes | No PCIe copy — zero-copy with CPU |

**Critical corrected insight:** FP32 throughput is **1.79 TFLOPS**, not 3.38 TFLOPS. The 3.38 figure cited in earlier estimates was FP16. Gradient accumulation in standard BF16/FP16 mixed-precision training runs at FP32 precision on GPU, meaning backward-pass throughput runs at the 1.79 TFLOPS ceiling. This halves earlier throughput projections and makes ELO's gradient-scope reduction even more critical.

**NPU — Qualcomm Hexagon AI Engine**

| Metric | Value |
|---|---|
| Precision support | INT4, INT8, INT16, FP16 |
| Key features | Direct Link, Micro Tile Inferencing, large shared memory concurrency |
| Role in this system | Frozen layer forward inference only — no gradient path |
| Speedup vs CPU (quantized models) | 5–100× depending on model and op type |
| NPU delegation rate (LiteRT QNN, 72 models) | 64/72 models achieve full NPU delegation |

The Hexagon NPU cannot backpropagate. It is a compiled-graph inference engine. Its role in this system is acceleration of the frozen middle-layer forward pass only.

**Memory Subsystem**

| Metric | Value |
|---|---|
| Total capacity | 24GB LPDDR5X |
| Architecture | Unified — CPU, GPU, NPU share one pool |
| Bandwidth | ~85 GB/s |
| Key implication | No copy overhead between compute units — zero-copy tensor sharing |
| Key constraint | 85 GB/s vs ~700 GB/s on desktop discrete GPU — bandwidth is the real ceiling |

The unified memory pool is the single most important architectural advantage of this device for on-device training. There is no PCIe bus between CPU and GPU. A tensor written by the GPU is readable by the NPU without copying. This eliminates a major overhead class that desktop training pipelines pay continuously.

### 1.2 Why Full CPT Is Not Viable

Full dense continued pretraining on a model above roughly 800M parameters is not feasible on this device under standard mixed-precision training. The reasoning is not theoretical — it is a direct consequence of the corrected FP32 figure:

- FP32 gradient accumulation requires maintaining gradient tensors in FP32
- A full 1.5B-parameter model has approximately 1.5B gradient values at 4 bytes each = 6GB for gradients alone
- Adam optimizer state doubles that: momentum + variance = another ~12GB
- FP16 weights = 3GB
- Activations at batch size 4, sequence 512 = ~1.2GB
- OS and driver overhead = ~3.5GB
- **Total for full CPT: ~25.7GB — exceeds 24GB**

ELO's selective training of only the first and last transformer layers reduces this to ~9GB, as detailed in the memory budget section below. This is not a choice among equals — it is the only CPT path that fits.

---

## Part II — The Training Method

### 2.1 ELO: Efficient Layer-Specific Optimization

ELO was published at EACL 2026 Industry Track (arXiv:2601.03648). It is the most directly applicable method for this hardware profile identified in this research thread.

**Abstract mechanism:**

ELO consists of two sequential stages, each with a specific engineering role:

**Stage 1 — ELO Pretraining**

A small subset of transformer layers — specifically the first and last layers, identified as critically important through ablation experiments — are detached from the original model. Only these layers are trained on the target language corpus. All middle layers are frozen. This achieves two simultaneous effects:
1. The number of trainable parameters is reduced dramatically
2. The frozen middle layers are excluded from the gradient graph during backpropagation, meaning they are not differentiated and do not contribute to gradient memory or compute

**Stage 2 — Layer Alignment**

After Stage 1 converges, the trained first and last layers are reintegrated into the full original model. A brief fine-tuning step on a small dataset is then run with the full model unfrozen, aligning the updated boundary layers with the preserved middle-layer representations.

**Verified empirical results:**

| Metric | Result |
|---|---|
| Training speedup vs full fine-tuning | Up to **6.46×** |
| Average speedup across experiments | **~5.88×** |
| Target language quality improvement | Up to **6.2%** on qualitative benchmarks |
| Source language preservation | Better than standard CPT baselines |
| Published venue | EACL 2026 Industry Track |

**Why first and last layers specifically:**

The first transformer layers handle tokenization-level feature extraction — the statistical properties of the target language's token sequences. These are most disturbed when a new language is introduced. The last layers handle output projection onto the vocabulary distribution — the generation-side representation of the target language. Middle layers encode semantic representations that transfer more readily across languages and require less updating. This is an empirically validated finding from ablations in the paper, not a hypothesis.

**Mobile hardware implication — gradient FLOP reduction:**

For Qwen2.5-1.5B with 28 transformer layers, ELO Stage 1 trains 2 layers out of 28. The gradient computation scope is approximately 2/28 ≈ 7% of full CPT. At the corrected Adreno 830 FP32 throughput of 1.79 TFLOPS with ~35% utilization efficiency, and with ELO reducing the gradient graph to 7% of full size, the effective gradient compute load drops by a factor of approximately 14× in FLOP terms. The wall-clock speedup (6.46×) is lower than this because data loading, the frozen forward pass, and synchronization overhead are unchanged.

**Implementation note — codebase status:**

As of this document's research closure date, no official public implementation repository has been confirmed tied to the ELO paper authors. The GitHub search surfaces only generic continual pretraining repositories unrelated to the paper. **The working assumption is that ELO must be reimplemented.** The PyTorch implementation is tractable given the clear mechanism:

```python
# ELO Stage 1 — freeze middle layers, train first and last only
for name, param in model.named_parameters():
    param.requires_grad = False  # freeze all

# Unfreeze only the boundary layers
for param in model.model.layers[0].parameters():
    param.requires_grad = True
for param in model.model.layers[-1].parameters():
    param.requires_grad = True
# Also unfreeze the LM head (output projection)
for param in model.lm_head.parameters():
    param.requires_grad = True
```

PyTorch correctly handles this: `requires_grad=False` on intermediate layers prevents gradient computation for those layers while still allowing the forward pass to execute. Gradients still flow through frozen layers in the backward pass (the graph is traversed), but no gradient tensors are accumulated for the frozen parameters, which is the memory-saving mechanism.

**Activation checkpointing compatibility:**

Activation checkpointing (trading compute for memory by recomputing activations during backward pass rather than storing them) is compatible with ELO's partial freezing. Under ELO, the gradient graph only spans the boundary layers, so recomputation cost is proportionally tiny. Recommended: apply activation checkpointing to the two ELO-trainable layers at sequence lengths above 512. PyTorch 2.x's flexible activation checkpointing policy can be set to `MUST_SAVE` for compute-intensive ops (matmul, bmm, attention) and `PREFER_RECOMPUTE` for elementwise ops.

### 2.2 Why QLoRA Alone Is Not Sufficient

QLoRA injects low-rank adapter matrices into frozen layer projections and trains only those adapters. It is computationally cheap and widely tooled. However, for the specific goal of **deep multilingual knowledge injection**, it is structurally insufficient:

- QLoRA primarily modifies access patterns and behavioral distribution of the model — how it responds, what format it produces, what style it adopts
- For a Polymath corpus that contains novel factual knowledge, cross-lingual structure, and domain concepts not present in the base model's training data, QLoRA cannot write new statistical associations into the model's weight structure with the same fidelity as continued pretraining
- Domain knowledge injection studies consistently show CPT-based methods outperform LoRA/QLoRA for factual knowledge embedding

QLoRA remains valuable as:
- A rapid pilot baseline for early experiments
- A behavior-shaping step after CPT completes (instruction tuning, formatting)
- A low-cost specialty adapter for narrow tasks
- A first comparison arm in benchmarks

It should not be the primary adaptation method for the Polymath corpus. The research direction is ELO-selective CPT, with QLoRA as a comparison baseline.

### 2.3 Adaptation Regime Decision Matrix

| Regime | Memory cost | Knowledge injection | Multilinguality preservation | Mobile viability | Verdict |
|---|---|---|---|---|---|
| Full dense CPT | >24GB (OOM) | Strongest | Depends on curriculum | Infeasible | Eliminated |
| Standard LoRA | Low | Weak for novel knowledge | Moderate | Viable | Baseline only |
| QLoRA | Lowest | Weakest for novel knowledge | Moderate | Viable | Baseline only |
| Full CPT + replay | >24GB (OOM) | Strong | Good with replay | Infeasible | Eliminated |
| **ELO selective CPT** | **~9GB** | **Strong** | **Best in class** | **Primary path** | **Selected** |
| Hybrid ELO + LoRA | ~9.5GB | Strong | Strong | Viable | Phase 2 option |

---

## Part III — Model Selection

### 3.1 Selection Criteria

The model selection criteria for this system are, in order of weight:

1. **Memory fit under ELO selective CPT** — must not OOM on 24GB under the full budget including OS overhead
2. **Multilingual tokenizer coverage** — tokenizer must cover target corpus languages without excessive token fertility (>2.5× English baseline is a flag)
3. **Minimal post-training distortion** — base checkpoint must be suitable for continued pretraining, not heavily instruction-tuned or RLHF-distorted
4. **Snapdragon deployment signal** — evidence of successful QNN/Genie export for the frozen layer inference path
5. **License** — Apache 2.0 or equivalent permissive license for research and commercial use
6. **Tooling maturity** — HuggingFace compatibility, LlamaFactory or Unsloth pretraining support

### 3.2 Primary Candidate: Qwen2.5-1.5B

**Architecture:**

| Property | Value |
|---|---|
| Parameters | 1.5 billion (dense) |
| Architecture | Decoder-only, Grouped Query Attention (GQA), SwiGLU, RoPE, RMSNorm |
| Context length | 32,768 native; 128K with YaRN |
| Pre-training tokens | 7–18 trillion (quality-filtered multi-stage) |
| Tokenizer type | BPE (byte-level) |
| Vocabulary size | 151,643 regular tokens + 3 control tokens |
| Multilingual coverage | 29+ languages documented |
| License | Apache 2.0 |

**Why Qwen2.5-1.5B is the default:**

The tokenizer is the largest vocabulary in the 1B–2B class. A larger vocabulary directly reduces token fertility for non-English scripts — more concepts have dedicated tokens rather than being decomposed into byte-level fragments. Qwen's technical report explicitly states that the BPE tokenizer was designed for strong multilingual compression efficiency across Chinese, Japanese, Korean, Arabic, and European languages.

The Snapdragon deployment signal is concrete: Microsoft has demonstrated DeepSeek-distilled Qwen 1.5B running on the Hexagon NPU through the Windows on Snapdragon / Copilot+ PC ecosystem. The Qualcomm Genie runtime has documented Qwen2 model family support. This confirms that the Qwen 1.5B architecture exports to the QNN graph compilation path without fundamental blockers.

**Memory budget under ELO selective CPT (Qwen2.5-1.5B, 28 layers):**

| Component | Precision | Size | Calculation |
|---|---|---|---|
| Full model weights (resident) | FP16 | 3.00 GB | 1.5B × 2 bytes |
| ELO trainable layer weights — FP32 master copy | FP32 | 0.21 GB | 2 layers × ~105M params × 4 bytes |
| Gradient tensors (ELO layers only) | FP32 | 0.21 GB | Same as above |
| Adam optimizer state (ELO layers only) | FP32 | 0.42 GB | Momentum + variance × 2 |
| Activations (full forward pass, seq=512, batch=4) | FP16 | 1.20 GB | Forward pass all layers |
| Data pipeline buffer | — | 0.50 GB | Tokenized batch prefetch |
| OS + driver + Android baseline | — | 3.50 GB | Measured typical on Snapdragon 8 Elite |
| **Total** | | **~9.04 GB** | **~15 GB headroom** |

The 15GB headroom is substantial. It accommodates:
- Larger sequence lengths (up to 2048 with ~3GB additional activation memory)
- Larger batch sizes
- A second model or pipeline component simultaneously (e.g., audio diffusion inference)
- QNN compiled graph resident alongside training

### 3.3 Secondary Candidate: SmolLM3-3B

**Architecture:**

| Property | Value |
|---|---|
| Parameters | 3 billion (dense) |
| Architecture | Decoder-only, GQA, NoPE (3:1 ratio with RoPE) |
| Context length | 64K trained; 128K with YaRN |
| Pre-training tokens | 11.2 trillion (staged curriculum: web → code → math → reasoning) |
| Mid-training | 175B reasoning tokens |
| Multilingual native | 6 languages (English, French, Spanish, German, Italian, Portuguese) |
| Additional training exposure | Arabic, Chinese, Russian (fewer tokens) |
| Reasoning mode | Dual-mode: `/think` and `/no_think` toggles |
| License | Apache 2.0 |
| Training reproducibility | Unusually high — full configs, data details, LlamaFactory and Unsloth notebooks published |

**Why SmolLM3-3B is Candidate B:**

The 3B scale may yield meaningfully stronger knowledge retention for a dense Polymath corpus — more parameters means more capacity to hold factual associations. The dual-mode reasoning architecture is architecturally aligned with the Polymath use case. The training reproducibility is the highest in the class, which benefits iterative experimentation.

**The blocker:** No confirmed Snapdragon QNN export signal has been found for SmolLM3-3B specifically. The NoPE architecture (no positional encoding on 3 of every 4 attention heads) is non-standard and may introduce export friction to QNN's compiled graph path. Until export is validated, SmolLM3 cannot use the NPU for frozen-layer acceleration, forcing all computation onto the GPU/CPU path.

**Memory budget under ELO selective CPT (SmolLM3-3B):**

| Component | Precision | Size |
|---|---|---|
| Full model weights (resident) | FP16 | 6.00 GB |
| ELO trainable layer FP32 master | FP32 | 0.28 GB |
| Gradient tensors (ELO layers only) | FP32 | 0.28 GB |
| Adam optimizer state (ELO layers only) | FP32 | 0.56 GB |
| Activations (seq=512, batch=4) | FP16 | 2.00 GB |
| Data pipeline buffer | — | 0.50 GB |
| OS + driver baseline | — | 3.50 GB |
| **Total** | | **~13.12 GB** |

SmolLM3-3B also fits, with ~11GB headroom. It is viable for Phase 1 training if QNN export is validated. If export fails, it loses the NPU acceleration path and the ELO hybrid architecture advantage reverts to a GPU-only pipeline.

### 3.4 Model Decision Logic

```
IF ELO codebase exists or reimplementation is scoped as < 2 weeks:
  AND Qwen2.5 tokenizer fertility is < 2.5× for target languages:
  AND QNN export for Qwen2.5-1.5B is confirmed (already evidenced):
  → DEFAULT STACK: Qwen2.5-1.5B + ELO

IF SmolLM3-3B QNN export is validated:
  AND 3B knowledge capacity is judged worth the narrower multilingual base:
  → UPGRADE TO: SmolLM3-3B + ELO

IF Qwen tokenizer fertility fails for key Polymath languages:
  → BRANCH TO: Qwen2.5-1.5B + vocabulary extension before CPT
  → OR BRANCH TO: SmolLM3-3B (if export validated)

IF neither QNN export path validates:
  → FALLBACK: GPU-only ELO (Vulkan only, no NPU acceleration)
  → Revisit model choice under GPU-only constraint
```

### 3.5 Deprioritized Candidates

| Model class | Reason for deprioritization |
|---|---|
| LLaDA / diffusion-language | Sub-2B trainable checkpoints not publicly confirmed; Snapdragon export path unknown; Phase 2 research track only |
| Gemma 2B family | Strong multilingual community work (Swahili, Italian fine-tunes) but tokenizer fertility issues for Arabic and CJK; CPT tooling less mature than Qwen |
| Full 7B+ dense models | Memory exceeds 24GB under any CPT regime with gradients — eliminated |
| Large multimodal stacks | Alignment complexity, data complexity, and uncertainty too high for Phase 1 |

---

## Part IV — Data Strategy

### 4.1 Why the Corpus May Matter More Than the Architecture

A 2025 paper (arXiv:2502.10361) demonstrates that model-based multilingual data selection allows a 1B-parameter Llama model to match baseline MMLU score using only 15% of the standard training token volume. Put differently, high-quality curated data can match 6× more unfiltered data. For a Polymath corpus where curation is inherently high — the source material is selected books, scholarly texts, and structured knowledge — this result is directly relevant. The training method and corpus quality interact: ELO is more efficient, and a higher-quality corpus makes ELO's reduced token budget even less of a liability.

A complementary result from the Gamayun multilingual model work (arXiv:2512.21580) shows that 2.5T tokens are sufficient to train a sub-2B model that surpasses Qwen2.5-1.5B on most multilingual tasks except deep STEM benchmarks — suggesting that curriculum design and language balance matter more than raw volume even at the pretraining scale.

### 4.2 Pipeline Architecture

**Stage 1 — Ingestion**

- OCR normalization: strip header/footer artifacts, fix hyphenation line breaks, normalize Unicode to NFC, identify and remove page numbers and running headers
- Language detection: run at paragraph level, not document level — books regularly contain multilingual footnotes, quotations in other languages, bibliographies, and index entries in multiple scripts
- Document segmentation: split into chunks of 1,024–2,048 tokens with 128-token overlap to preserve sentence context across chunk boundaries
- Metadata recovery: retain author, date, domain tag, language ID, and source provenance per chunk

**Stage 2 — Quality Scoring**

- Perplexity-based OCR damage detection: run Qwen2.5-1.5B in inference mode on corpus samples before CPT begins; unusually high-perplexity chunks are candidates for OCR damage or garbled text
- Deduplication: MinHash LSH at 5-gram level with Jaccard similarity threshold ~0.85 — book corpora frequently contain near-duplicate material from different editions, translations, and reprints
- Boilerplate detection: identify and remove chapter headers repeated identically, table-of-contents fragments, index pages, and license boilerplate
- Transformer-based quality classifier: use a FastText or small-transformer classifier trained to identify "structured and knowledge-rich samples" versus web-noise — the 2025 model-based filtering paper provides the conceptual template

**Stage 3 — Language Balancing**

- Do not use equal sampling across languages — this is the "curse of multilinguality" problem, where equal weighting degrades high-resource language quality
- Recommended mixing: target languages at 40–60% of training tokens, English at 20–30%, other high-resource languages at the remainder
- For low-resource languages with corpus representation (e.g., classical Latin, isiZulu, Afrikaans, Swahili): oversample relative to their proportion in the raw corpus to prevent underrepresentation in the learned distribution
- Gamayun's validated approach: initial balanced multilingual training for cross-lingual alignment, followed by increased high-quality English data for performance transfer — adopt this as the curriculum structure

**Stage 4 — Replay Set**

- Maintain 10–15% of training tokens as general-domain English text (e.g., a Common Crawl slice or cleaned Wikipedia subset)
- Interleave replay throughout training at every epoch, not only at the end
- This is the most effective and best-validated catastrophic-forgetting mitigation strategy for continual pretraining

**Stage 5 — Curriculum Scheduling**

- Phase A: clean monolingual high-confidence strata first (clean English books, then clean French/German/Spanish)
- Phase B: multilingual cross-lingual passages with high translation quality or known alignment
- Phase C: low-resource languages, morphologically complex languages, archaic vocabulary, noisy OCR survivors
- Harder material last maximizes the model's capacity to absorb it, because ELO has already updated boundary-layer representations to accommodate the target language distribution

### 4.3 Cross-Lingual Training Objectives

Plain next-token prediction CPT leaves multilingual cross-lingual alignment performance on the table. April 2026 research on cross-lingual mapping in pretraining confirms gains on machine translation, cross-lingual NLU, and cross-lingual QA from embedding cross-lingual objectives directly into pretraining.

**Priority order for implementation:**

1. **Contrastive cross-lingual alignment** (highest priority): When parallel or near-parallel passages exist — same text in two languages, semantically matched passages from different books — add a contrastive objective that brings their representations closer in embedding space. This is the largest cross-lingual quality gain per unit of compute
2. **Language-aware sampling curriculum** (medium priority): Adjust per-language sampling probabilities dynamically based on validation loss per language — underperforming languages receive higher sampling weight in the following epoch
3. **Translation consistency loss** (lower priority, higher engineering cost): For machine-translated passage pairs, add a consistency objective. Worth implementing only if the corpus contains or can be augmented with translation pairs

### 4.4 Tokenizer Fertility Audit — Mandatory Pre-Flight

Before committing to Qwen2.5-1.5B as the base model, run a fertility audit on actual Polymath corpus samples. Calculate for each target language:
- Tokens per word
- Tokens per character
- Ratio versus English baseline

Any language with a fertility ratio above ~2.5× the English baseline should be flagged. Options:
- Oversample that language in training (compensates at cost of more compute)
- Extend the tokenizer vocabulary before CPT (adds embedding rows, requires warm-up training)
- Accept the higher token cost and plan for proportionally more training time

This audit is a blocking pre-condition for finalizing the model choice.

---

## Part V — Runtime and Systems Architecture

### 5.1 Architectural Principle

The architecture is **heterogeneous by design**, not by approximation. Snapdragon 8 Elite is explicitly designed for heterogeneous execution: Qualcomm's own documentation describes the Hexagon NPU as part of a system where AI workloads are dispatched across multiple compute units based on their characteristics. HeteroInfer, the published research system built specifically for Snapdragon 8 Elite, demonstrates 1.34× to 6.02× end-to-end speedup over single-unit (GPU-only or NPU-only) execution through heterogeneous dispatch. This is the architecture this system adopts for training.

### 5.2 Execution Stack Design

```
╔══════════════════════════════════════════════════════════════════╗
║              TRAINING LOOP — ELO STAGE 1 EXECUTION              ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  INPUT BATCH (tokenized, in unified memory)                      ║
║       │                                                          ║
║       ▼                                                          ║
║  ┌─────────────────────────────────────┐                         ║
║  │  ADRENO 830 — Vulkan Queue 0        │  HIGH PRIORITY          ║
║  │  (Compute — gradient-active layers) │                         ║
║  │                                     │                         ║
║  │  • Layer 0 forward (FP16) ────────► activate gradient graph   ║
║  │  • Frozen layers 1..26 (FP16) ────► forward only, no grad     ║
║  │  • Layer 27 forward (FP16) ───────► activate gradient graph   ║
║  │  • LM head forward (FP16) ────────► activate gradient graph   ║
║  │  • Loss computation (FP32)                                    ║
║  │  • Backward pass — layers 0,27 only (FP32 grad accumulation)  ║
║  └─────────────────────────────────────┘                         ║
║       │                                                          ║
║       │ Vulkan semaphore synchronization                         ║
║       ▼                                                          ║
║  ┌─────────────────────────────────────┐                         ║
║  │  HEXAGON NPU — QNN compiled graph  │  ASYNC, LOWER PRIORITY  ║
║  │  (Frozen middle layers 1..26)      │                          ║
║  │                                    │                          ║
║  │  • INT4/INT8 quantized execution   │                          ║
║  │  • Output activations → unified    │                          ║
║  │    memory (zero-copy to Vulkan)    │                          ║
║  │  • No gradient path                │                          ║
║  └─────────────────────────────────────┘                         ║
║                                                                  ║
║  ┌─────────────────────────────────────┐                         ║
║  │  Vulkan Queue 1 — Transfer         │  LOW PRIORITY           ║
║  │  • Async data loading              │                          ║
║  │  • Tokenization staging            │                          ║
║  │  • Next-batch prefetch             │                          ║
║  └─────────────────────────────────────┘                         ║
║                                                                  ║
║  ┌─────────────────────────────────────┐                         ║
║  │  ORYON CPU                         │                          ║
║  │  • Semaphore dispatch              │                          ║
║  │  • Adam optimizer step             │                          ║
║  │    (ELO layer params only)         │                          ║
║  │  • Checkpoint write                │                          ║
║  │  • Logging and telemetry           │                          ║
║  └─────────────────────────────────────┘                         ║
╚══════════════════════════════════════════════════════════════════╝
```

### 5.3 Vulkan Implementation Rules for Adreno TBDR

Adreno is a **Tile-Based Deferred Renderer (TBDR)** GPU. This architecture differs fundamentally from NVIDIA's streaming multiprocessor design. TBDR GPUs process geometry in screen-space tiles before rasterization, which creates specific queue dependency pitfalls.

**The cardinal TBDR rule:** never create a FRAGMENT → COMPUTE dependency within the same Vulkan queue. This barrier forces the fragment queue to stall, then the compute queue must wait for fragment to resume before proceeding — eliminating parallelism.

**Implementation:**

- Declare two separate `VkQueue` objects at device creation time
- Queue 0: high priority, compute-family — handles gradient computation
- Queue 1: low priority, transfer/compute — handles data staging
- Queue priorities are set at `VkDeviceQueueCreateInfo` and cannot be changed at runtime — this must be configured before device creation
- Use `VkSemaphore` for cross-queue synchronization between the GPU compute path and the QNN activation output
- Use `VkEvent` for lightweight intra-queue synchronization within the gradient computation

```cpp
// Priority setup — must happen at device creation time
float queuePriorities[2] = {1.0f, 0.3f};  // high, low
VkDeviceQueueCreateInfo queueCreateInfo = {
    .sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
    .queueFamilyIndex = computeFamilyIndex,
    .queueCount = 2,
    .pQueuePriorities = queuePriorities
};
```

Qualcomm publishes a Vulkan Adreno Layer tool that detects suboptimal Vulkan API usage and suggests Adreno-specific optimizations — this should be integrated into the development workflow from the start.

### 5.4 QNN / Hexagon Role and Boundaries

QNN (Qualcomm AI Engine Direct) is the NPU-targeting runtime. Its role in this system is:

**What QNN does:**
- Compiles a frozen subgraph (transformer layers 1 through 26 in the 28-layer Qwen2.5-1.5B model) into an optimized INT4/INT8 binary
- Executes that binary on the Hexagon NPU at high efficiency
- Writes output activations to unified memory, where the GPU Vulkan pipeline reads them without copying
- Provides up to 100× speedup over CPU for quantized ops in the LiteRT/QNN benchmark suite; 64 of 72 tested models achieve full NPU delegation

**What QNN does not do:**
- It cannot backpropagate
- It cannot execute custom training kernels
- It cannot dynamically modify network weights during execution

**Graph compilation cost:** QNN graph compilation is expensive — it converts the model subgraph into a hardware-specific binary and can take seconds to minutes depending on subgraph size. Under ELO's two-stage structure, this cost is paid twice: once at the start of Stage 1 (compile frozen layers 1–26 for NPU), and once during the Stage 1 → Stage 2 transition (retire the NPU graph, full model moves to Vulkan for alignment). This is acceptable.

**LiteRT / QNN compilation API (Python):**
```python
from ai_edge_litert.aot import aot_compile as aot_lib
from ai_edge_litert.aot.vendors.qualcomm import target as qnn_target

sm8650_target = qnn_target.Target(qnn_target.SocModel.SM8650)
compiled_models = aot_lib.aot_compile(
    tflite_model_path,
    target=sm8650_target
)
```

### 5.5 CPU Orchestration

The Oryon CPU's role is narrow but load-bearing:

1. **Semaphore dispatch:** signal and wait on Vulkan semaphores to coordinate between GPU queues and QNN NPU output
2. **Adam optimizer step:** apply gradient updates to ELO-trainable parameter tensors — this is a small operation (only ~105M parameters per stage for 1.5B ELO) and runs efficiently on Oryon
3. **Checkpoint management:** write checkpoint files, manage resume state
4. **Telemetry:** log tokens/sec, memory consumption, GPU temperature, and clock frequency for thermal adaptation

The CPU should not be in the forward pass or backward pass hot path. Data preprocessing (tokenization) should be parallelized across the efficiency cores (Phoenix M) and pipelined to complete before the GPU needs the next batch.

### 5.6 The Reflex Scheduler — From Concept to Specification

The earlier "Reflex Agent" concept from this research thread is now formally specified as an **adaptive heterogeneous scheduler**. Its role is operator-to-device placement.

**Static placement (Phase 1 default):**

| Op category | Assigned to | Reason |
|---|---|---|
| Matrix multiply (frozen layers) | NPU (QNN) | Highest efficiency at INT4/INT8 |
| Layer normalization (frozen layers) | NPU (QNN) | Compiled into QNN graph |
| Attention computation (trainable layers) | GPU (Vulkan) | Must be differentiable |
| Activation functions (trainable layers) | GPU (Vulkan) | Must be differentiable |
| Backward pass | GPU (Vulkan) | Cannot run on NPU |
| Gradient accumulation | GPU (Vulkan) + CPU | FP32 accumulation, CPU for Adam |
| Data tokenization | CPU (Phoenix M) | Parallelizable, not memory-bandwidth-bound |
| Optimizer step | CPU (Phoenix L) | Small tensor operation |

**Online adaptive variant (Phase 2, if warranted):**

If the static placement leaves measurable compute slack on any unit under thermal steady-state, an online policy can be introduced that monitors queue depth, thermal headroom, and recent latency to dynamically reassign borderline operations. The prior research thread framed this as a bandit-style online learning problem. The implementation would maintain a dispatch table with per-op latency history and adjust placement based on a simple UCB (Upper Confidence Bound) policy per operation shape class.

The Phase 1 recommendation is to measure whether static placement already captures 80%+ of the theoretical heterogeneous speedup before investing in adaptive scheduling complexity.

---

## Part VI — Throughput Model

### 6.1 Theoretical Ceiling

Under ELO Stage 1 with Qwen2.5-1.5B:

- Gradient FLOP per token = 6 GFLOPs (full CPT) × (2/28) ≈ **0.43 GFLOPs/token**
- Adreno 830 FP32: 1.79 TFLOPS at ~35% sustained utilization = 0.626 TFLOPS effective
- Theoretical tokens/second = 0.626 × 10¹² / 0.43 × 10⁹ ≈ **1,456 tokens/second**
- Per hour: **~5.2 million tokens/hour** (theoretical ceiling)

### 6.2 Reality Adjustments

| Degradation factor | Estimated impact |
|---|---|
| Thermal throttling (sustained, fan on) | –30% clock reduction → –30% throughput |
| Memory bandwidth saturation (weight reloading) | –15% |
| Data pipeline and tokenization overhead | –10% |
| QNN synchronization overhead | –5% |

**Realistic sustained throughput estimate: ~2.0–2.8 million tokens/hour** under ELO Stage 1.

The RedMagic 10 Pro+ has an active cooling fan — a differentiating feature of the RedMagic product line. With the fan active, the thermal throttling estimate improves, and the upper end of the realistic range (2.8M tokens/hour) is more credible. With the fan inactive, the lower end (2.0M tokens/hour) is more conservative and appropriate.

### 6.3 Corpus Timing at Midpoint (2.5M tokens/hour)

| Corpus scale | Estimated time (1 pass) | Wall-clock |
|---|---|---|
| 10M tokens (pilot) | 4 hours | Same day |
| 100M tokens (~1,000 books) | 40 hours | ~2 days |
| 500M tokens (~5,000 books) | 200 hours | ~8 days |
| 1B tokens (~10,000 books) | 400 hours | ~17 days |

These are estimates for ELO Stage 1 only. Stage 2 alignment adds approximately 5–10% additional wall-clock time.

**Critical caveat:** These are calculated from corrected hardware specs and efficiency assumptions. They must be validated by Experiment 0 (see Part VII) before any corpus investment is made.

---

## Part VII — Validation Protocol

### 7.1 Experiment 0 — Stack Fit and Baseline Throughput

This is the single most important experiment in the program. It should be run before any corpus work, before any model modification, and before any architecture decisions are finalized based on theoretical estimates.

**Specification:**

```
Model:           Qwen2.5-1.5B base checkpoint (download from HuggingFace)
Dataset:         10M-token English public-domain slice
                 (Project Gutenberg or equivalent — no IP concerns)
Training mode:   ELO Stage 1
                 model.model.layers[0]: requires_grad = True
                 model.model.layers[1:27]: requires_grad = False
                 model.model.layers[27]: requires_grad = True
                 model.lm_head: requires_grad = True
Batch size:      4 (gradient accumulation 8 steps → effective batch 32)
Sequence length: 512 tokens
Precision:       BF16 forward pass, FP32 gradient accumulation on ELO layers
Optimizer:       AdamW, lr=2e-4, warmup 100 steps
Duration:        2 hours sustained

Instruments:
  - Peak RAM: Android GPU Inspector or equivalent (Snapdragon Profiler)
  - Sustained tokens/sec: measured after 10-minute thermal settling period
  - GPU core clock frequency: continuous logging (detects thermal throttling)
  - GPU temperature: continuous logging
  - OOM event: binary — occurred or did not occur
```

**Experiment 0 success criteria:**

| Metric | Success | Failure |
|---|---|---|
| OOM | No OOM at batch=4 | OOM at any viable batch size |
| Peak RAM | < 20GB | > 22GB (close to ceiling) |
| Sustained throughput | > 500K tokens/hour | < 100K tokens/hour |
| GPU temperature | < 80°C sustained | > 85°C sustained |
| GPU clock frequency | > 800 MHz sustained | < 600 MHz sustained (heavy throttle) |

**Failure responses:**

- OOM: reduce batch size to 2, then 1, then reduce sequence length to 256
- Temperature > 85°C: enable active fan (RedMagic cooling mode), retest
- Throughput < 100K: indicates framework overhead, not hardware — debug data pipeline and PyTorch operator dispatch before assuming hardware limit

### 7.2 Experiment 1 — Multilingual Tokenizer Fertility Audit

Run this in parallel with or immediately after Experiment 0.

**Specification:**

For each target language in the Polymath corpus:
1. Take a 10,000-word sample of representative text
2. Tokenize with Qwen2.5-1.5B tokenizer
3. Record tokens per word and tokens per character
4. Calculate ratio versus English baseline from the same corpus

**Decision threshold:**
- < 1.5× English fertility: excellent coverage
- 1.5–2.5×: acceptable — plan for proportionally more training budget
- > 2.5×: flag for vocabulary extension or language-specific handling

If fertility is problematic for core Polymath languages, evaluate SmolLM3-3B tokenizer on the same samples for comparison.

### 7.3 Experiment 2 — SmolLM3-3B QNN Export Validation

**Specification:**

1. Export SmolLM3-3B (or a representative subgraph of layers 1–N-2) to TFLite via `ai_edge_torch`
2. Compile to QNN binary targeting SM8650 via LiteRT QNN API
3. Run inference check on a sample batch
4. Record: success or failure; if failure, identify the specific op or graph pattern that fails compilation

**Decision rule:**
- If export succeeds: SmolLM3-3B becomes a viable Candidate B option for ELO selective CPT with NPU frozen-layer acceleration
- If export fails on non-standard ops (NoPE, custom attention): SmolLM3 can still be trained GPU-only, but loses the NPU acceleration path — evaluate whether the 3B quality gain justifies the throughput cost

---

## Part VIII — Phased Program Plan

### Phase 0 — Infrastructure (Weeks 1–2)

- Set up Android development environment with Snapdragon Profiler, Android GPU Inspector
- Install Termux or equivalent Linux-on-Android environment for training pipeline
- Download Qwen2.5-1.5B base checkpoint
- Prepare 10M-token English corpus slice for Experiment 0
- Implement ELO Stage 1 layer freezing in PyTorch
- Run Experiment 0 — validate stack fit, throughput, and thermal envelope
- Run tokenizer fertility audit on representative Polymath corpus sample

**Phase 0 gate:** Experiment 0 succeeds (no OOM, throughput > 500K tokens/hour, temperature < 80°C)

### Phase 1A — Qwen2.5-1.5B ELO Baseline (Weeks 3–8)

- Implement full ELO Stage 1 training loop with Vulkan-compatible PyTorch backend
- Build corpus ingestion pipeline: OCR normalization, language detection, chunking, deduplication
- Run first multilingual ELO training run on a 100M-token Polymath corpus slice
- Evaluate: multilingual quality on per-language validation sets, in-domain recall on Polymath concepts, catastrophic forgetting on held-out English
- Instrument: tokens/hour, joules/token (battery drain proxy), checkpoint size

**Phase 1A gate:** Model shows measurable improvement on target-language evaluation vs base checkpoint without catastrophic English quality degradation

### Phase 1B — Cross-Lingual Objectives (Weeks 9–12)

- Add contrastive cross-lingual alignment objective for parallel/near-parallel corpus passages
- Implement language-aware sampling curriculum tied to per-language validation loss
- Run ELO Stage 2 alignment fine-tuning
- Evaluate cross-lingual transfer quality on machine translation and cross-lingual QA benchmarks

### Phase 2 — SmolLM3 Parallel Track (Concurrent with Phase 1B, if export validates)

- Validate SmolLM3-3B QNN export
- Run equivalent ELO Stage 1 experiment with SmolLM3-3B on same corpus slice
- Compare: knowledge retention quality, throughput, memory envelope, evaluation scores
- Make model decision: continue Qwen2.5 line or switch primary to SmolLM3-3B

### Phase 3 — Multimodal Bridge (Post Phase 1B)

- Text-only backbone must be stable before multimodal extension
- Initial multimodal target: audio diffusion, given domain relevance (music technology)
- Architecture: separate audio encoder trained independently, then cross-modal bridge
- Evaluate: joint text-audio understanding on music description and transcription tasks

---

## Part IX — Evaluation Metrics

The evaluation framework must measure what matters on-device, not generic leaderboard prestige.

**Primary metrics (training outcome):**

| Metric | Measurement method |
|---|---|
| Multilingual quality | Per-language perplexity on held-out corpus; MMLU multilingual subsets |
| In-domain Polymath recall | Custom question set over corpus-covered concepts |
| Cross-lingual transfer | Cross-lingual QA, machine translation BLEU on known pairs |
| Source language preservation | English MMLU and general perplexity vs base checkpoint baseline |
| Catastrophic forgetting delta | Performance gap vs base on English held-out set |

**Primary metrics (hardware / system):**

| Metric | Measurement method |
|---|---|
| Tokens/hour (sustained) | Measured over 1-hour sustained runs, logged continuously |
| Joules per token | Battery drain / tokens logged — proxy for energy efficiency |
| Peak RAM | Android GPU Inspector peak allocation |
| GPU clock frequency (sustained) | Snapdragon Profiler clock trace |
| GPU temperature (sustained) | Thermal sensor logging |
| Checkpoint size | Disk footprint of saved adapter/ELO-layer checkpoints |

**Falsification criterion:**

The primary thesis is falsified if a simpler method — QLoRA alone, or a smaller model without ELO — achieves equal or better evaluation scores at equal wall-clock budget on the real device. The evaluation suite must include this comparison arm.

---

## Part X — Risk Register and Disconfirming Signals

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| ELO reimplementation cost is high | Medium | Medium | Scope first; the mechanism is simple and PyTorch support is confirmed |
| Qwen tokenizer fertility fails for key languages | Medium | High | Run fertility audit before any corpus investment; vocabulary extension or SmolLM3 as fallback |
| SmolLM3-3B QNN export fails | Medium | Low | GPU-only path still viable; lower throughput, still sufficient |
| Thermal throttling more severe than estimated | Low | Medium | RedMagic active fan mitigates; test with fan on/off; design for sustained 60% clock |
| Vulkan training kernels too high engineering cost | Low-Medium | Medium | PyTorch Vulkan backend may be sufficient without custom SPIR-V shaders initially |
| QNN compilation time disrupts ELO curriculum | Low | Low | Compile once per stage; cost is bounded and acceptable |
| Active cooling draws too much power | Low | Low | Battery drain is a constraint, not a blocker; schedule long runs at plugged-in |
| Bandwidth ceiling dominates over compute ceiling | Medium | Medium | Operator tiling, weight reuse, and batch size tuning can push bandwidth efficiency |

**Disconfirming signals to actively monitor:**

1. If Experiment 0 throughput is below 100K tokens/hour: the bottleneck is framework overhead or data pipeline, not hardware — investigate before hardware-level optimization
2. If ELO yields no improvement over QLoRA on in-domain Polymath evaluation: the corpus may be teaching behavioral style, not factual structure — reevaluate whether CPT is the right signal
3. If multilingual ELO degrades English quality despite replay: increase replay proportion before adding cross-lingual objectives
4. If thermal throttling makes sustained training infeasible without charger: the program design is valid but impractical for long runs — reschedule as overnight/plugged-in only

---

## Part XI — Open Questions for the Next Research Pass

These questions are the only remaining blockers to a final implementation decision. They are ordered by blocking priority:

1. **ELO codebase availability** — GitHub URL or explicit "must reimplement" with effort estimate
2. **Tokenizer fertility table** — Qwen2.5-1.5B on actual Polymath target languages, with ratio vs English
3. **SmolLM3-3B QNN export verdict** — yes/no, with specific failure op if no
4. **Experiment 0 results** — measured RAM, temperature, tokens/sec, OOM/no-OOM
5. **QNN graph compile time** — measured on a real export, not estimated
6. **RedMagic active cooling thermal delta** — sustained GPU clock with fan on vs off

When these six questions are answered, the implementation decision is complete. No further research loops are required.

---

## Appendix A — Source Reference Map

This appendix maps every major claim in this document to its source evidence.

| Claim | Source |
|---|---|
| Snapdragon 8 Elite CPU clock: 4.32 GHz / 3.53 GHz | Nanoreview SoC specification database |
| Adreno 830 FP32: 1.79 TFLOPS | Corrected from FP16 figure; derived from GPU clock × shader count |
| Vulkan 1.3 and OpenCL 3.0 support | Qualcomm Snapdragon 8 Elite documentation |
| TBDR queue architecture and async compute rules | Vulkan official documentation — async compute sample |
| Queue priority declaration at VkDeviceQueueCreateInfo | Vulkan documentation, ARM Mali async compute blog |
| HeteroInfer 1.34×–6.02× speedup on Snapdragon 8 Elite | arXiv:2501.14794 — published ACM MobiSys 2025 |
| Hexagon NPU INT4/INT8/INT16/FP16 and Direct Link | Qualcomm Snapdragon 8 Elite product brief |
| LiteRT QNN — 64/72 models achieve full NPU delegation | Google / InfoQ LiteRT QNN announcement, November 2025 |
| LiteRT NPU vs CPU speedup up to 100× | Google AI Edge LiteRT documentation |
| ELO mechanism: first/last layers, two stages | arXiv:2601.03648 / ACL Anthology 2026.eacl-industry.55 |
| ELO speedup: 6.46× and ~5.88× average | arXiv:2601.03648 |
| ELO quality improvement: 6.2% | arXiv:2601.03648 |
| PyTorch requires_grad freezing — gradients stop but values don't | PyTorch Forums discussion thread |
| Activation checkpointing policy API | PyTorch 2.x documentation |
| Qwen2.5-1.5B architecture, vocab 151k, 29+ languages, Apache 2.0 | HuggingFace Qwen/Qwen2.5-1.5B model card |
| DeepSeek-Qwen 1.5B on Snapdragon NPU (Windows) | Microsoft Windows Developer Blog, January 2025 |
| SmolLM3-3B: 3B params, 11.2T tokens, 6 languages, NoPE, Apache 2.0 | HuggingFace SmolLM3 release, tinyweights.dev, Cordatus AI blog |
| SmolLM3 dual reasoning mode | LinkedIn announcement by Lewis Tunstall, HuggingFace |
| Model-based multilingual data selection — 15% tokens match baseline | arXiv:2502.10361 |
| Gamayun 2.5T tokens sufficient, multilingual curriculum design | arXiv:2512.21580 |
| Cross-lingual mapping in pretraining — April 2026 gains | Referenced in thread research |
| QLoRA insufficient for deep knowledge injection vs CPT | Domain knowledge injection research cited in thread |
| QNN LiteRT compilation API with SM8650 target | Google AI Edge LiteRT / Qualcomm documentation |
| Qualcomm Vulkan Adreno Layer tool | docs.qualcomm.com/vk_adreno_layer |

