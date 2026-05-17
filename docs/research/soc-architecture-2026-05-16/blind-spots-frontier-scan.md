# Blind Spots Frontier Scan

Date: 2026-05-16
Role: fresh-context research agent  
Scope: architecture/training/SoC blind spots for RedMagic/Snapdragon heterogeneous training and adaptation. This file does not edit the living dialogue.

## Governing Read

The existing local notes correctly identify the first-order plan: dense authority baselines, frozen NPU-forward islands, adapter/faculty sidecars, static routing before dynamic MoE, and measured wall-clock/energy-to-quality as the gate. The blind spots below are the places where that plan could still be too small, too demo-shaped, or pointed at the wrong bottleneck.

Do not treat any item below as a pass narrative. Each item is useful only if it survives the same authority metric: sustained quality under memory, thermal, backend-placement, energy, and regression receipts.

## Ranked Blind Spots

### 1. Real on-phone backprop is no longer safe to dismiss

**Why it matters:** The current stance leans toward frozen-base adapters and zeroth-order updates because mobile backprop is assumed to be memory-prohibitive. Newer work makes that assumption falsifiable instead of axiomatic: MeBP reports sub-1GB fine-tuning memory for 0.5B-4B LLMs on iPhone 15 Pro Max; MobileFineTuner reports full-parameter and PEFT fine-tuning for GPT-2, Gemma 3, and Qwen 2.5 on real phones; ZeroQAT reports forward-only QAT, including a 6.7B model on a OnePlus 12.

**Copy:** Add a RedMagic "first-order training" baseline beside LoRA and MeZO: MeBP-style rematerialized backprop for LoRA/norm/head, then Qwen/Gemma 0.5B-4B full or partial fine-tuning if memory receipts allow.

**Falsify:** Kill it if examples/sec-to-authority-quality loses to ZO/adapters after warm thermal state, or if Android/Adreno/QNN hidden allocations break the sub-GB story.

**Sources:** https://arxiv.org/abs/2510.03425 ; https://arxiv.org/abs/2512.08211 ; https://arxiv.org/abs/2509.00031

### 2. Expert offload viability is a model property, not a MoE slogan

**Why it matters:** "3B active" does not imply a good phone MoE. Expert paging depends on whether consecutive tokens reuse similar experts. Local Routing Consistency introduces SRP and SCH metrics and shows that cacheability varies across MoE models; shared experts and expert semantics can affect locality.

**Copy:** Before choosing OLMoE, LFM2, EMO, Qwen3-30B-A3B, Gemma 4 26B-A4B, or Qwen3.6, trace router decisions on Polymath corpora and simulate cache sizes around 1x-4x active experts. Rank models by quality plus cacheability, not active-parameter count.

**Falsify:** Any candidate with poor SCH/SRP at a realistic cache budget should be demoted even if its architecture looks faculty-like.

**Sources:** https://arxiv.org/abs/2505.16056

### 3. MoE scheduling is part of the architecture

**Why it matters:** D2MoE, HybriMoE, MoE-Lens, and KTransformers all say the hard part is not just selecting a sparse model; it is expert bit-width, cache policy, prefetching, CPU/GPU split, and hardware-limit modeling. On a phone, this becomes CPU/GPU/NPU plus UFS storage, with tighter thermal and DRAM-bandwidth limits.

**Copy:** Build a small expert-scheduler simulator before dynamic MoE training. Include hottest-expert-bit-first scheduling, impact-driven prefetch, score-based caching, and a performance model that predicts bytes moved per token/update.

**Falsify:** If scheduler overhead, graph fragmentation, or backend crossings erase the dense baseline's wall-clock-to-quality, dynamic MoE is not first-wave.

**Sources:** https://arxiv.org/abs/2504.15299 ; https://arxiv.org/abs/2504.05897 ; https://arxiv.org/abs/2504.09345 ; https://madsys.cs.tsinghua.edu.cn/publication/ktransformers-unleashing-the-full-potential-of-cpu/gpu-hybrid-inference-for-moe-models/

### 4. Storage-backed inference/training is only viable if the model is flash-shaped

**Why it matters:** Large phone storage is not extra RAM. Apple LLM-in-a-flash, PowerInfer-2, FlexInfer, MNN-LLM, SSDTrain, and MemAscend all optimize data movement explicitly. NVLLM goes further and treats NAND as a compute substrate. The shared lesson is that naive streaming is a trap; useful storage paths need large contiguous reads, activation/expert locality, prefetch overlap, pinned-memory discipline, and a cost model.

**Copy:** Add a UFS/offload gate: measure sequential/random read bandwidth, energy proxy, page-cache behavior, thermal drift, and per-token page volume. Store experts/FFN clusters in runtime page order, not checkpoint order.

**Falsify:** Reject storage-backed MoE/training if UFS enters the hot path without overlap, if write amplification threatens device health, or if energy/token exceeds an in-RAM dense baseline.

**Sources:** https://arxiv.org/abs/2312.11514 ; https://arxiv.org/abs/2406.06282 ; https://arxiv.org/abs/2503.03777 ; https://arxiv.org/abs/2506.10443 ; https://arxiv.org/abs/2408.10013 ; https://arxiv.org/abs/2505.23254 ; https://arxiv.org/abs/2604.25699

### 5. Heterogeneous SoC work points to tensor/phase partitioning, not just one frozen NPU island

**Why it matters:** HeteroInfer/HeteroLLM reports GPU-NPU heterogeneous execution on mobile SoCs, and mobile-NPU test-time scaling reports using underutilized NPU matrix units for parallel inference strategies. This challenges the current "large NPU island plus sidecar" default: the better split may vary between prefill, decode, verification, beam/search, and adapter evaluation.

**Copy:** Add a phase-partition probe: prefill on NPU/GPU split, decode on the best sustained path, and use spare NPU capacity for verifier/reward/draft branches in test-time compute.

**Falsify:** If Qualcomm graph constraints, synchronization, or quantization loss negate the split, keep NPU as a frozen island and stop narrating heterogeneous wins.

**Sources:** https://arxiv.org/abs/2501.14794 ; https://arxiv.org/abs/2509.23324

### 6. Multi-LoRA can make "faculties" a runtime input instead of a graph mutation

**Why it matters:** A 2026 Samsung/Qualcomm SM8650/SM8750 system reports application LoRAs as runtime inputs to one frozen graph; MobiLoRA and EdgeLoRA optimize mobile/edge LoRA serving; aLoRA enables adapter activation while reusing base KV cache. This is directly aligned with faculty routing and avoids repeated QNN/LiteRT graph recompilation.

**Copy:** Represent faculty adapters as runtime tensors selected by a CPU scheduler. Test aLoRA-style activation for multi-step workflows and adapter-cache pooling for many small faculties.

**Falsify:** Reject it if LoRA-as-input prevents delegation, if adapter switching burns more memory bandwidth than static selection, or if multi-adapter composition regresses authority tasks.

**Sources:** https://arxiv.org/abs/2604.18655 ; https://aclanthology.org/2025.acl-long.1140/ ; https://arxiv.org/abs/2507.01438 ; https://arxiv.org/abs/2504.12397 ; https://arxiv.org/abs/2512.17910

### 7. Low-memory optimizer research should be a first-class baseline, not a footnote

**Why it matters:** GaLore/GaLore2, Q-GaLore, APOLLO, Sparse MeZO, QuZO, and ZO2 are all attempts to reduce optimizer/gradient memory without accepting the representational ceiling of ordinary LoRA. Polymath should not compare only "LoRA vs zeroth-order" and miss low-rank-gradient or sparse-sensitive-parameter paths.

**Copy:** Run a memory ladder on the same small model and corpus: LoRA Adam, MeBP LoRA, Q-GaLore/GaLore2 partial full-parameter, APOLLO-Mini, Sparse MeZO, QuZO/ZO2. Keep identical authority and replay gates.

**Falsify:** Reject methods whose lower memory comes from slower convergence, host-only kernels, hidden CPU RAM blowups, or brittle hyperparameters.

**Sources:** https://arxiv.org/abs/2403.03507 ; https://arxiv.org/abs/2504.20437 ; https://arxiv.org/abs/2407.08296 ; https://proceedings.mlsys.org/paper_files/paper/2025/file/437bc4ccafd3fc6d4289bd10940be42b-Paper-Conference.pdf ; https://arxiv.org/abs/2402.15751 ; https://huggingface.co/papers/2502.12346 ; https://huggingface.co/papers/2503.12668

### 8. Test-time training and self-adaptation may be the phone-native learning surface

**Why it matters:** TTT, Transformer-Squared, and SEAL suggest a different interpretation of on-device learning: do not force the phone to continually pretrain; let it update fast weights, singular components, generated self-edits, or session-level adapter state. This aligns with privacy and personalization while limiting persistent weight churn.

**Copy:** Create an ephemeral adaptation lane: fast-weight/session adapter updates with replay protection, then optional promotion into a durable faculty adapter only if authority and forgetting gates pass.

**Falsify:** Kill it if local adaptation improves the immediate prompt while degrading retained knowledge, calibration, or cross-domain ELO.

**Sources:** https://arxiv.org/abs/2505.23884 ; https://arxiv.org/abs/2501.06252 ; https://arxiv.org/abs/2506.10943 ; https://arxiv.org/abs/2407.04620

### 9. Elastic active-parameter models are a better SoC target than fixed-k active models

**Why it matters:** Phone thermal headroom changes over minutes. Fixed active experts or fixed depth do not match that. Matryoshka MoE, Elastic MoE, Mixture-of-Depths, and Chain-of-Model/CoLM point to models trained to run at multiple active budgets or depths.

**Copy:** Add a "budget-elastic" architecture branch: train or adapt routers under variable expert count, variable depth, and per-layer budget schedules. The scheduler should be able to lower active compute under heat without switching checkpoints.

**Falsify:** If dynamic budgets require too many compiled graph variants or quality collapses below a dense baseline at lower budgets, treat elasticity as deployment-only, not training-core.

**Sources:** https://arxiv.org/abs/2509.26520 ; https://arxiv.org/abs/2509.21892 ; https://arxiv.org/abs/2404.02258 ; https://arxiv.org/abs/2505.11820 ; https://research.nvidia.com/labs/lpr/publication/cai2024llamaflex/

### 10. Quantization-aware local learning deserves its own branch

**Why it matters:** The current notes treat quantization mostly as a runtime/export concern. ZeroQAT frames low-bit quantization as an end-to-end on-device training problem, and mobile-NPU test-time scaling shows quantization layout can determine whether NPU compute is actually usable.

**Copy:** Add device-local QAT for adapters, heads, and maybe expert subsets. Optimize the deployed quantized graph directly, not only the host-side fp/bf checkpoint.

**Falsify:** Reject if forward-query count, quant/dequant boundaries, or low-bit accuracy loss makes QAT slower to authority quality than PTQ plus ordinary adapter training.

**Sources:** https://arxiv.org/abs/2509.00031 ; https://arxiv.org/abs/2509.23324

### 11. KV-cache and adapter-cache reuse may dominate "training" wins in agent workflows

**Why it matters:** Multi-turn faculty systems repeatedly switch skills, retrieve documents, and revise outputs. MobiLoRA, aLoRA, and cross-model KV reuse show that cache reuse across adapter states can reduce recomputation dramatically. If Polymath ignores cache continuity, it may overtrain modules to compensate for a runtime layout bug.

**Copy:** Track KV/adaptation cache hit rate as a first-class metric. Design faculty invocation so base prefixes, retrieval chunks, and adapter activation boundaries maximize cache reuse.

**Falsify:** If the cache policy changes answers, corrupts adapter isolation, or only helps toy multi-turn traces, do not count it as learning progress.

**Sources:** https://aclanthology.org/2025.acl-long.1140/ ; https://arxiv.org/abs/2504.12397 ; https://arxiv.org/abs/2512.17910

### 12. Progressive/modular curriculum should shape training order, not just model choice

**Why it matters:** Chain-of-Model and elastic MoE work imply a curriculum where smaller chains/experts learn first and larger capacity is added progressively. This is closer to a phone-relevant training ladder than trying to update a full Qwen3.6-class model immediately.

**Copy:** Train or adapt in staged faculties: base dense skill, then one domain adapter/expert set, then router, then additional experts/chains. Promote only modules that improve the authority metric with replay.

**Falsify:** If staged modules create local competence but hurt global ELO, calibration, or retention, the curriculum is reward hacking.

**Sources:** https://arxiv.org/abs/2505.11820 ; https://arxiv.org/abs/2509.26520 ; https://arxiv.org/abs/2605.06663

## Immediate Additions To The Experiment Matrix

1. **Backprop challenger:** MeBP/MobileFineTuner-style first-order LoRA/norm/head training on RedMagic, compared against MeZO/MobiZO and ordinary LoRA.
2. **Router locality gate:** SRP/SCH traces for every MoE candidate before any phone MoE claim.
3. **Storage cost model:** UFS/DRAM/thermal measurement before expert paging or flash-backed training is treated as viable.
4. **Multi-LoRA graph probe:** LoRA-as-runtime-input and aLoRA/KV reuse against QNN/LiteRT delegation receipts.
5. **Elastic-budget branch:** variable expert count/depth under thermal throttling, gated by authority quality.

## Hard Falsifiers

- If dense 3B-4B plus honest adapters reaches the authority target faster than every MoE/offload path, the sparse/faculty story fails for this gate.
- If a method improves utilization but worsens quality, replay, or forgetting, it fails.
- If a method depends on silent CPU fallback, unmeasured storage traffic, or burst-only thermal numbers, it fails.
- If a result cannot name bytes moved per accepted token/update, it is not yet an SoC result.
