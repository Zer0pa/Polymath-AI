# The Natural Shape Of A Heterogeneous SoC Training Step

**Date:** 2026-05-16
**Role:** Research Agent — SoC training-loop physics
**Scope:** Snapdragon 8 Elite (SM8750) on RedMagic 10 Pro Plus, 24 GB LPDDR5X (~85 GB/s), Adreno 830 GPU (1.79 TFLOPS FP32 / 3.58 TFLOPS FP16, Vulkan 1.3, TBDR), Hexagon NPU via QNN (forward-only baseline), Oryon CPU (2x 4.32 GHz Phoenix L + 6x 3.53 GHz Phoenix M, NEON/SVE2), UFS 4.x storage, active cooling, bypass charging.
**Governing discipline:** Resistance V2. Authority metric: sustained tokens-to-target-quality under fan/bypass thermals, not burst step latency. "Natural" means whatever the SoC's physical structure cheapest sustains, not whatever rhymes with the cloud loop.

## Verdict

The natural shape of one training step on this SoC is **not a step at all in the cloud sense**. It is a **3-stage, 3-microbatch pipeline** continuously in flight across CPU / GPU / NPU, with the optimizer step running on Oryon **concurrently with** the next batch's forward pass, gradients accumulated on Adreno in FP16 with periodic FP32 master-promotion on CPU, and UFS-backed replay/checkpoint I/O scheduled into the unavoidable thermal idle windows.

There are two real synchronization barriers per *effective step* (the unit that updates weights), not eight as in a cloud-GPU step.

The natural shape, concretely:

```text
TIME  ─────────────────────────────────────────────────────────────────────►

Phoenix M  : [tok b3]→ [tok b4]→ [tok b5]→ [tok b6] ───────────────────────►
             (efficiency cores, ring-buffered, ahead-of-batch by 2-3)

Phoenix L  :                              [Adam(b1 grads)] [Adam(b2 grads)] ►
             (one perf core: optimizer step on FP32 master copy of trainable params)
             (the other perf core: scheduler / semaphore dispatch / telemetry)

Adreno Q0  : [FWD b2 trainable-prefix] [BWD b1 trainable-prefix+tail+head] ─►
             [activation save→DRAM]    [grad accum FP16, periodic FP32 promote]
             (compute queue, COMPUTE-only, never FRAGMENT→COMPUTE)

Hexagon    : [FWD b2 frozen-middle (QNN ctx)] [FWD b3 frozen-middle (QNN ctx)]►
             (HVX/HMX matmul-only, output activations → unified DRAM in NHWC
              or whatever the QNN context fixed; layout MUST match Adreno's
              expectation or repack happens on CPU once at compile time)

Adreno Q1  : [prefetch b4 batch DRAM staging]  [async ckpt write to UFS]    ►
             (transfer queue, low priority, scavenges DRAM bandwidth)

UFS        : [replay shard b4 read] ... [b1 ckpt write (delta only)] ...    ►

────────────────────────────────────────────────────────────────────────────►
                ^                                  ^
            SYNC POINT A                      SYNC POINT B
            (Hexagon FWD output                (BWD complete →
             ready → Adreno BWD                 Adam may proceed
             may start needing                  on Phoenix L for
             activations + dL/dh_26)            *previous* batch grads)
```

Two barriers per effective weight update, both expressed as `VkSemaphore` waits inside the GPU queue, not as CPU-side `cudaDeviceSynchronize`-equivalent stalls. Everything else runs ahead.

The cloud-GPU step boundary — "forward → backward → optimizer → next batch, all one device, all synchronous" — does **not appear in this picture**. It cannot, because there is no device on this SoC that owns all three of those workloads efficiently.

## Per-Stage Placement

The four physical work classes do not map 1-to-1 to three compute units. They map by **arithmetic intensity, by precision regime, and by whether the kernel mutates parameters**.

### Forward pass

| Layer class | Where | Why |
|---|---|---|
| Embedding lookup + RoPE on input | Adreno Q0, FP16 | Memory-bound gather, no benefit from Hexagon; on the gradient path. |
| Trainable prefix layer (layer 0) | Adreno Q0, FP16 fwd | Must stay differentiable, must produce activations for BWD. ~6% of model FLOPs but 100% of prefix-gradient origin. |
| Frozen middle (layers 1..L-2) | Hexagon NPU via QNN context binary, INT8 weights / FP16 activations | Highest perf/W per matmul on this SoC; weights pre-quantized once; graph never mutates; output written to a unified DRAM region with layout pre-agreed at compile time so Adreno reads zero-copy. |
| Trainable tail layer (layer L-1) | Adreno Q0, FP16 fwd | Same reasoning as layer 0; head-adjacent gradients originate here. |
| LM head (vocab projection) | Adreno Q0, FP16 fwd, FP32 reduction for loss | Large matmul (151k vocab for Qwen2.5), but bandwidth-dominated; Adreno wins because the loss is computed in the same queue. |
| Loss (cross-entropy + replay/contrastive aux) | Adreno Q0, FP32 reduction | Per-token reduction, naturally fused into the head matmul epilogue in a Vulkan compute shader. |

**Reasoning:** ELO-style frozen-middle is not a hack to fit memory; it is the *natural decomposition* because Hexagon is forward-only via QNN. The "two trainable boundary layers" are exactly the layers that must be on Adreno. The frozen middle is *exactly* what Hexagon is best at: a large fixed-shape compiled island. The blueprint specifies this for ELO; the same shape is natural for **any** training method that treats most of the model as frozen (LoRA on frozen base, faculty adapters, MoE expert-frozen-during-non-routed-step).

If the trainable surface is LoRA adapters across all layers (not just boundary layers), the picture changes: the frozen-middle Hexagon forward still happens, but the LoRA delta `BAx` for each middle layer is computed on Adreno in parallel and *added back into the activation that returns from Hexagon* before it enters the next Hexagon layer. This forces a per-layer Hexagon→Adreno→Hexagon ping-pong, which is the killer pattern for unified-memory heterogeneous systems (layout-correct but bandwidth-loud). **The natural LoRA placement is therefore "LoRA only on the trainable boundary layers", or batched-merged LoRA where deltas are pre-fused into the QNN-compiled weights between training intervals** — not per-step ping-pong. This is a real architectural constraint, not a preference.

### Backward pass

| Kernel | Where | Why |
|---|---|---|
| `dL/dlogits → dL/dhead_in` | Adreno Q0, FP16 forward graph, FP32 grad output | Symmetric to fwd; activations are already in DRAM at the right Vulkan buffer. |
| Head weight grad accumulation | Adreno Q0, FP16 accum tile, **periodic FP32 promote on CPU** | FP16 matmul accum keeps Adreno at 3.58 TFLOPS not 1.79 TFLOPS. FP32 master is updated every K microbatches via a CPU-side promote (small kernel, cheap on Phoenix L NEON). |
| Tail layer (L-1) gradient | Adreno Q0, FP16 accum | Same. |
| **Backward THROUGH frozen middle** | **Adreno Q0, FP16 forward-recompute + VJP** | This is the painful one and the place the cloud pattern breaks hardest. See "Backward through frozen middle" below. |
| Prefix layer (0) gradient | Adreno Q0, FP16 accum | Same. |
| Embedding gradient | Adreno Q0, sparse scatter (FP32 accum to small live-tokens set) | Embedding gradient is sparse (only updated for tokens seen this batch); naturally maps to a Vulkan compute shader doing atomic-add on FP32. |

**Backward through frozen middle:** even if middle weights do not receive gradients, the chain rule needs `dL/dh_l` to be propagated from layer L-1 back to layer 0. There are three options, in cost order:

1. **Cheapest (chosen):** Hexagon emits forward activations into DRAM during the forward pass; Adreno reads them and performs the *backward* VJP (vector-Jacobian product) per middle layer using the same FP16 weights, in Vulkan compute shaders. This requires that the frozen-middle weights are *also* accessible to Adreno (either dequantized to FP16 in a second DRAM region, or accessed via a Vulkan shader that does INT8→FP16 on the fly). The dequant cost is paid once per training interval, not per step.
2. **Cheaper if middle is small and shallow:** recompute the middle forward on Adreno during backward (gradient checkpointing). Trades 1× extra Hexagon-equivalent FLOPs on Adreno for activation-memory savings.
3. **Forbidden:** sending `dL/dh_l` back to Hexagon. QNN does not provide an autograd / VJP path, and even if a custom path existed, the Hexagon→Adreno transfer of the *gradient signal* would cost a full activation tensor per microbatch per layer.

The natural choice is **option 1 for the frozen middle, option 2 only when activation memory is tight**. This means the frozen-middle weights have two residencies: an INT8 QNN-compiled context on Hexagon for forward, and a Vulkan `VkBuffer` of FP16 (or INT8 with shader-side dequant) for backward VJP. This doubles the frozen-middle weight footprint vs forward-only deployment. For Qwen2.5-1.5B with 26 frozen middle layers at ~50M params each, that is ~1.3 GB INT8 (Hexagon side) + ~2.6 GB FP16 (Adreno side) = ~3.9 GB vs ~1.3 GB inference-only. The 24 GB budget tolerates this.

This is the single biggest memory cost the SoC pays for the heterogeneous shape. **If activation memory pressure forces option 2 (recompute), the natural recompute device is Adreno, not Hexagon, because Adreno owns the BWD anyway.** Recompute on Adreno costs ~1.79 TFLOPS FP32 (or 3.58 FP16) and competes with the gradient kernels; sustained throughput drops ~30-50% during the recompute window.

### Optimizer step

| Kernel | Where | Why |
|---|---|---|
| Adam moment update (`m`, `v`) for trainable params | Phoenix L (one perf core), FP32, NEON SIMD | ~210M params (ELO 2-layer + head): ~1.7 GB of optimizer state. CPU has the right bandwidth/compute ratio (Adam is ~10 FLOPs/param, memory-bound). Phoenix L at 4.32 GHz with NEON delivers ~30 GFLOPS per core. ~210M params × 10 FLOPs / 30 GFLOPS = ~70 ms per optimizer step. Negligible vs the multi-second BWD window of the *next* batch. |
| FP32 master weight update | Phoenix L, FP32 | Same place as Adam moments; trivial. |
| FP16 working copy refresh (cast FP32→FP16) | Phoenix L → DMA to Adreno `VkBuffer` | Phoenix L narrows FP32 master back to FP16 in cache, writes to the Vulkan-visible DRAM region. Adreno picks up the new weights on the *next* forward of those layers. |
| Optimizer state residency | DRAM, Phoenix L L2/L3 hot | Adam `m`+`v` = 2 × FP32 × 210M = 1.7 GB. Stays warm in DRAM, streamed through Phoenix L L2 (12 MB) per step. |
| LR schedule / weight decay / grad clip | Phoenix L, scalar | Tiny. Same core. |

**This is the most natural placement of the entire loop.** The optimizer step is the wrong workload for a wide SIMD GPU (it is per-parameter scalar arithmetic with state), it is *forbidden* on Hexagon (no autograd, no mutable persistent state outside the compiled graph), and Oryon Phoenix L has exactly the right cache hierarchy (12 MB L2 + 8 MB L3 shared) to stream the moment tensors. The blueprint already says this. The blueprint is correct.

The non-obvious gain is **the optimizer step happens in parallel with the next batch's forward+backward, not after it.** This is structurally Hogwild!-adjacent (the GPU is reading slightly stale weights while the CPU updates them), but the staleness is bounded to 1 step and 1 step staleness is well-tolerated in practice in mixed-precision optimizer setups. See "Async design" below.

### Replay / checkpoint / telemetry

| Kernel | Where | Why |
|---|---|---|
| Replay buffer storage | UFS 4.x, sequential reads | 10-15% replay tokens. Reads happen on Phoenix M efficiency cores in advance of the batch they support, into a DRAM ring buffer. UFS 4.x sequential read is ~4 GB/s, more than enough at training token rates. |
| Replay token sampling / mixing | Phoenix M | Free. |
| Checkpoint write | UFS 4.x, sequential writes via Phoenix M, delta-only after first ckpt | Only ELO-trainable params + optimizer state change; full ckpt is ~1.9 GB but per-interval delta is ~210M params × 4B + optimizer state delta. Write happens during thermal-idle windows (between curriculum batches) or async during forward. |
| Telemetry (tokens/s, temp, GPU clock, PSS) | Phoenix M, low priority | Logged to a circular SQLite or jsonl on UFS. |

## Memory Hierarchy Assignment Table

The 24 GB of unified DRAM is not a flat pool. Every tensor class has a specific residency, a specific *backend-visible buffer type*, and a specific lifetime. Total DRAM at peak: ~14-16 GB resident under ELO; ~21-23 GB resident under MoE-faculty experiments with one expert hot. Budget assumes 3.5 GB Android baseline and 1-2 GB headroom for the low-memory killer.

| Tensor class | Where it lives | Buffer/backend | Precision | Size (Qwen2.5-1.5B ELO) | Lifetime | Notes |
|---|---|---|---|---|---|---|
| Frozen middle weights, Hexagon side | DRAM, QNN context binary region | QNN tensor | INT8 (W8A16) | ~1.3 GB | Whole training interval | Compiled once via QAIRT, never mutated. Allocation is via FastRPC / QNN session. |
| Frozen middle weights, Adreno side (BWD VJP) | DRAM, Vulkan-visible | `VkBuffer` HOST_COHERENT or DEVICE_LOCAL | FP16 (or INT8 + shader dequant) | ~2.6 GB (FP16) or ~1.3 GB (INT8) | Whole training interval | Second copy is the cost of doing BWD without sending grad back to Hexagon. The INT8 option saves 1.3 GB but adds dequant cost per BWD layer. |
| Trainable layers (prefix L0, tail L_{L-1}, head), Adreno side, FP16 working | DRAM, Vulkan-visible | `VkBuffer` DEVICE_LOCAL | FP16 | ~420 MB | Step-to-step, refreshed by CPU optimizer | This is what Adreno computes against. |
| Trainable layers, **FP32 master copy** | DRAM, CPU-visible | `malloc` aligned | FP32 | ~840 MB | Whole training interval | The authoritative weights. Adam updates this. |
| Embedding table | DRAM, dual-visible | `VkBuffer` + CPU pointer (host-coherent or with explicit cache maint) | FP16 working, FP32 master for trainable rows | ~388 MB (Qwen 151k × 1536 × 2B) | Whole training interval | If embedding is frozen (common), single FP16 copy on Adreno. If trainable, sparse FP32 grad accumulation on Adreno + sparse FP32 master on CPU. |
| Activations, transient (forward → backward chain) | DRAM, Vulkan-visible | `VkBuffer` ring-allocated | FP16 | ~1.5 GB for seq=512, B=4, 28 layers (no checkpointing) | One microbatch | The dominant memory consumer during a step. Gradient checkpointing on frozen middle drops this to ~300 MB. |
| Activations from Hexagon FWD into Adreno BWD | DRAM, shared Vulkan/QNN-visible region | Pre-agreed layout (NHWC, contiguous, 16-byte aligned) | FP16 | ~600 MB at peak | One microbatch | Layout must be pre-agreed at QNN compile time; otherwise CPU repack kills the win. Use ION/dma-buf allocator with both QNN and Vulkan import. |
| Gradient buffers, trainable layers | DRAM, Adreno-side | `VkBuffer` DEVICE_LOCAL | FP16 accum, FP32 reduction at gradient-accumulation boundary | ~420 MB | Microbatch → accumulation boundary | FP16 accum buys 2× throughput on Adreno; FP32 promote is small and per-K-microbatches. |
| Adam optimizer state (m, v) | DRAM, CPU L2/L3 hot | `malloc` aligned 64 B | FP32 | ~1.68 GB (2 × 210M × 4B) | Whole training interval | Streamed through Phoenix L. If 8-bit Adam (bitsandbytes-style), drops to ~420 MB; tradeoff is small accuracy loss, examined per-faculty. |
| Token batch (input ids) | DRAM ring buffer | CPU malloc → Vulkan import | INT32 | ~32 KB per microbatch (seq=512, B=4) | Microbatch | Phoenix M fills this ahead of the GPU. |
| KV cache during training | Per-microbatch, Vulkan-visible | `VkBuffer` | FP16 | seq=512 → ~120 MB at training shapes (much smaller than inference) | One forward | At seq=512 the KV cache is small. At seq=2048+ it becomes the dominant memory consumer and forces a smaller microbatch. |
| Replay buffer (cold) | UFS 4.x | mmap or sequential read | tokenized INT32 | Multi-GB to multi-TB on disk | Long-lived | Phoenix M reads ahead. |
| Cold weights (warm expert / unloaded faculty / cold checkpoint) | UFS 4.x | mmap | INT8 / FP16 packed | up to UFS capacity | Long-lived | Loading takes ~0.5-1 s/GB at UFS 4.x sustained read; not on hot path. |
| Checkpoint delta (write) | UFS 4.x | sequential write | FP32 master + FP16 working | ~840 MB per ckpt | Long-lived | Written async by Phoenix M. |
| Telemetry log | UFS 4.x | append SQLite/jsonl | ASCII | trivial | Long-lived | |

**The non-trivial point:** the frozen middle layers have **two DRAM residencies** (Hexagon INT8 context + Adreno FP16 BWD). This is the memory tax for doing real training across a heterogeneous SoC where one of the devices cannot backward. It is the reason the natural shape works at 1.5B-3B model scale on 24 GB but does not naively scale to 8B+ without paging.

## Sync Pattern

The training step has exactly **two hard sync points per effective weight update**, plus three classes of "soft" async barriers that the OS / Vulkan driver / QNN runtime handle internally.

### Hard sync points (per effective step)

**SYNC POINT A — Hexagon FWD output → Adreno BWD input (per microbatch):**
- `VkSemaphore S_A` signaled by the QNN runtime when frozen-middle output activation tensor `h_{L-2}` is written to DRAM and visible.
- `VkSemaphore S_A` waited on by the Adreno BWD compute pipeline before it starts the `dL/dh_{L-2}` traversal back through the recomputed/precomputed middle layers.
- Implementation: external semaphore (`VK_KHR_external_semaphore`) shared between QNN and Vulkan. On Snapdragon this works via the FastRPC / dma-buf path. If unavailable, fall back to CPU-side semaphore polled by Phoenix L (adds ~50-200 µs latency per microbatch).

**SYNC POINT B — Adreno BWD complete → CPU optimizer step (per accumulation boundary, NOT per microbatch):**
- `VkSemaphore S_B` signaled by the Adreno BWD pipeline when FP32 gradient promote has finished for the trainable parameters.
- `VkSemaphore S_B` waited on by Phoenix L (CPU-side wait or eventfd) before Adam moment update begins.
- Crucial: Adam runs **concurrently with the next microbatch's forward**. The forward reads the *previous* FP16 working weights; the new weights become visible on the *next-next* microbatch. Staleness is 1 effective step.

### Soft/internal sync (handled by drivers)

- **Vulkan Q0 internal:** intra-queue COMPUTE→COMPUTE barriers (Vulkan `vkCmdPipelineBarrier` with `COMPUTE_SHADER_BIT` to `COMPUTE_SHADER_BIT`) for activation → grad dependencies. Cheap; no host involvement.
- **Vulkan Q0 vs Q1:** transfer queue (Q1, low priority) runs prefetch and checkpoint I/O completely async to compute queue (Q0). No `VkSemaphore` between Q0/Q1 except at batch ring-buffer wrap-around.
- **QNN runtime:** internal pipelining of Hexagon HVX/HMX stages; we do not control or sync to internals.
- **CPU dispatch thread:** uses `epoll`/`eventfd` to react to Vulkan timeline semaphores; no busy-wait.

### Forbidden synchronizations (cost is high enough to violate the natural shape)

- **`vkQueueWaitIdle` anywhere in the hot path.** This stalls the whole queue. Use timeline semaphores with monotonic counter values.
- **`vkDeviceWaitIdle` anywhere except shutdown.** Same.
- **FRAGMENT → COMPUTE dependencies on Adreno.** TBDR rule: the tile-deferred fragment pass forces a memory barrier through the binning unit before compute can resume. We use compute-only queues; no fragment work is ever scheduled in training. Restated for emphasis: this is not a "best practice", it is a **physical property of Adreno's tile rasterizer**. Any compute task that depends on a fragment task forces the binner to drain. The blueprint forbids it; the natural shape requires the prohibition.
- **CPU-side `mmap` page fault during compute.** Touching a not-yet-paged-in weight page on the hot path causes a multi-millisecond stall. Solution: `madvise(MADV_WILLNEED)` on Phoenix M ahead of the batch that needs the page.
- **QNN context recompile during training.** Multi-second cost. Forbidden during a training interval; allowed at curriculum boundaries.

## Microbatching, Accumulation, Pipelining

### Natural microbatch size

Bounded by **activation memory at chosen sequence length**, not by gradient batch quality.

| Sequence length | Microbatch size | Activation memory | Notes |
|---|---:|---:|---|
| 256 | 8 | ~1.2 GB | Cheapest probe; debug regime. |
| 512 | 4 | ~1.5 GB | **Default for ELO Stage 1.** Matches the blueprint. Activation memory + KV cache fits with ~10 GB headroom. |
| 1024 | 2 | ~2.0 GB | Faculty/domain CPT regime. |
| 2048 | 1 | ~2.8 GB | Long-context CPT or alignment probe; rare. |

The microbatch is intentionally small. The reason is *not* "the GPU is weak"; the reason is that **at small microbatch the Hexagon-Adreno crossing happens often enough to keep both devices busy**. A microbatch of 32 on cloud GPU is natural because the GPU is the only device and dependencies are intra-step. A microbatch of 4 on this SoC is natural because Adreno is busy with the *previous* microbatch's BWD while Hexagon does the *current* microbatch's FWD. Microbatch of 32 would idle Hexagon for the entire BWD window.

### Natural gradient accumulation

| Microbatch size | Accumulation steps | Effective batch | Notes |
|---:|---:|---:|---|
| 8 | 4 | 32 | seq=256 probe regime |
| 4 | 8 | 32 | **Default ELO regime** (matches blueprint Experiment 0) |
| 2 | 16 | 32 | seq=1024 |

Accumulation is in FP16 on Adreno with FP32 promote on Phoenix L *once per accumulation boundary*, not per microbatch. The promote is small (~1.7 GB FP16 → FP32 = ~25 ms on Phoenix L NEON) and is fused into the SYNC POINT B path.

### Pipeline depth (number of microbatches in flight)

**Three.** Not arbitrary; constrained by:

- Adreno is processing microbatch `b_{k}`'s BWD.
- Hexagon is processing microbatch `b_{k+1}`'s FWD.
- Phoenix M is tokenizing microbatch `b_{k+2}`.
- Phoenix L is updating params from microbatch `b_{k-1}`'s grads (only at accumulation boundary).

Going to depth 4 would either require a second Hexagon QNN context (you can have multiple contexts but they contend on the same HMX/HVX units) or hold a second activation set (1.5 GB × additional in-flight microbatch). Memory is the binding constraint past depth 3 at seq=512.

### Pipeline bubble analysis (the GPipe / 1F1B question)

GPipe/1F1B were designed for **multi-node training** where each "device" has its own DRAM and inter-device transfers (NVLink, IB) are the bottleneck. The bubble in GPipe comes from `(num_stages - 1) / num_microbatches × step_time` — the stages must drain at the end of each "batch".

On this SoC: **memory is unified.** A microbatch's activations do not have to be *moved* between Adreno and Hexagon; they are already there. The bubble structure is therefore different:

- GPipe's drain bubble: minimal. There is no "shipping activations between stages"; the next stage's input is already in DRAM at the address the next stage will read.
- The real bubble: **the *first* microbatch and the *last* microbatch of a training interval have nothing to overlap with.** The first microbatch's Hexagon FWD has nothing to be concurrent with on Adreno (Adreno has no prior BWD). The last microbatch's Adreno BWD has nothing to be concurrent with on Hexagon (Hexagon has no next FWD to start).
- Bubble cost: ~2 × single-microbatch latency per training *interval* (where an interval is a faculty-switch or curriculum boundary), not per *step*. At a 100M-token interval running at ~2.5M tokens/hr, the bubble is 2 microbatches × ~200 ms = ~400 ms per 40-hour interval. **Negligible.**

**1F1B vs GPipe schedule choice:** 1F1B is preferable here because it interleaves forward and backward of different microbatches across the pipeline. On a unified-memory SoC the choice is more about memory peak than throughput: 1F1B has lower peak activation memory (only `num_stages` worth of microbatches need activations alive concurrently, not all of them as in GPipe). Since activations are *the* memory pressure on this SoC, **1F1B is the natural schedule**.

The pseudocode of the natural 1F1B at depth 3 across CPU/GPU/NPU:

```text
# Warm-up phase (fills the pipeline):
t=0:  Phoenix M: tokenize b0
t=1:  Phoenix M: tokenize b1;   Hexagon: FWD(frozen middle) b0
t=2:  Phoenix M: tokenize b2;   Hexagon: FWD b1; Adreno Q0: FWD(prefix+tail+head) b0 + BWD b0

# Steady state:
t=k:  Phoenix M: tokenize b_{k+2}
      Hexagon: FWD middle b_{k+1}
      Adreno Q0: FWD trainable b_{k+1} + BWD b_k
      Phoenix L: idle OR (at accumulation boundary) Adam(b_{k-K..k-1} accumulated grads)
      Adreno Q1: prefetch b_{k+3} batch DRAM; UFS async ckpt delta

# Drain phase (only at curriculum/faculty boundary):
t=N:  Adreno Q0: BWD b_{N-1}
t=N+1: Phoenix L: final Adam step
```

This is the protocol. It does not look like the cloud-GPU training step diagram. It looks like a stream-processing graph.

## Asynchronous Design (Beyond Pipelining)

### Async optimizer step (1-step weight staleness)

The optimizer runs on Phoenix L *during* the next microbatch's forward on Adreno. The forward reads FP16 working weights that are 1 effective-step stale. New weights become visible after Phoenix L finishes the FP32→FP16 cast and DMAs to Adreno's `VkBuffer`. This is essentially **bounded-staleness SGD** with staleness = 1. Empirical evidence from large-batch SGD literature (e.g., asynchronous SGD with bounded delay, Lian et al. 2015; PipeDream's 1F1B-2BW) shows staleness ≤ 2 has negligible quality impact at the learning rates used in fine-tuning / CPT.

This is **not Hogwild!** in the strict lock-free shared-memory sense; the Adreno write of FP16 weights from CPU is serialized to a write fence between optimizer end and next-next forward begin. It is "1-step delayed read" not "racing read".

### Double-buffering / triple-buffering

- **Token batches:** triple-buffered in a 3-slot ring. Phoenix M writes slot `(k+2) mod 3`; Adreno/Hexagon read slot `(k+1) mod 3` and `k mod 3`.
- **Activations Hexagon → Adreno:** double-buffered. Two pre-allocated `VkBuffer`s, written by QNN, read by Adreno, alternating.
- **FP16 working weights for trainable layers:** double-buffered. Phoenix L writes one copy while Adreno reads the other.

### Async data prefetch (overlapping with compute)

- UFS replay shards: Phoenix M issues `pread()`+ `madvise(WILLNEED)` 2-3 batches ahead. UFS 4.x sequential read is ~4 GB/s, training token rate is ~700 tokens/s × 4B/token = ~3 KB/s of replay tokens. UFS bandwidth is 6 orders of magnitude over need; the only failure mode is random access from a poorly designed replay buffer. **Shard the replay buffer by sequence-length bucket and store sequentially.**
- Tokenization: Phoenix M (6 cores) tokenize 2-3 batches ahead into the ring buffer. With Qwen2.5 tokenizer at ~1M tokens/s/core on Phoenix M, tokenization is never the bottleneck.

### Async checkpoint save

- Delta checkpoint write happens on Phoenix M to UFS during the *forward* of the next batch, NOT during backward. Forward is shorter and BWD memory pressure is higher; sharing UFS DMA bandwidth during BWD risks page-cache pressure.
- Full checkpoints (every N intervals) happen during scheduled thermal-cool windows.

### What is NOT async

- The Vulkan compute queue Q0 is a single serialized command stream. Adreno cannot do forward and backward of the *same microbatch* concurrently; the dependency is intra-microbatch. The pipelining is *across microbatches*.
- Gradient accumulation does not run async; it is a sequential add into a single FP16 buffer per parameter.

## Why This Differs From The Cloud-GPU Training Loop

The cloud-GPU loop assumes seven things. Each is false here, and each falsity costs measurable tokens/sec.

| Cloud assumption | Cloud reality | This SoC reality | Cost if you copy the cloud loop |
|---|---|---|---|
| One dominant device (GPU) owns FWD, BWD, optimizer | True (NVIDIA H100/A100/MI300) | False — 3 devices, each best at different workload class | If you force everything onto Adreno: lose 5-30× perf/W on the frozen forward (Hexagon's strength) and lose ~70 ms/step of "free" CPU optimizer parallelism. |
| Step boundary is synchronous (`optimizer.step()` then next `loss.backward()`) | Convention; one device, easy to enforce | False — natural shape is pipelined with 1-step optimizer staleness | If you force sync step: idle Hexagon during BWD (50%+ of step) and idle Adreno during CPU optimizer. Throughput halves. |
| Memory is HBM-bandwidth (~3 TB/s) | True (HBM3 stacks on H100/MI300) | False — LPDDR5X ~85 GB/s, 35× slower | The same model size that's compute-bound on HBM is memory-bandwidth-bound here. Optimizer-fused-into-grad-kernel (cloud trick) becomes optimizer-on-CPU because the CPU's effective bandwidth to its L2/L3 is higher than what GPU can get from DRAM. |
| Activations dominate memory; recompute is a tradeoff | True at large batch | Different here: at microbatch=4 seq=512, activations are ~1.5 GB; **frozen-middle weight duplication** (Hexagon INT8 + Adreno FP16) is ~3.9 GB. Weight footprint can equal or exceed activation footprint. | If you assume "activations dominate" you over-invest in checkpointing and under-invest in weight residency optimization. |
| Optimizer step is short, fuse it into the gradient kernel | True; modern Adam fuses with grad accum | **False** — fusing Adam into Adreno costs 2× DRAM bandwidth for moment state during the BWD kernel (BWD already saturates DRAM). | Fused-Adam on Adreno measurably slows the BWD because the moment-state reads compete with the gradient accumulation reads at the 85 GB/s ceiling. CPU-side Adam is faster. |
| Pipeline parallelism is for multi-node | True at cloud scale | **False** — single-SoC pipelining across CPU/GPU/NPU is the natural shape because devices are heterogeneous in role. Bubbles are different (small, intra-interval), not the multi-node drain pattern. | Skipping pipelining leaves 30-60% throughput on the table because two of three devices are idle at any given moment. |
| FRAGMENT and COMPUTE queues can interact | True on NVIDIA SM (no TBDR) | **False** — Adreno is TBDR. FRAGMENT→COMPUTE forces a binner drain (~ms cost). | Any graphics-textured pipeline that touches the training queue stalls training. Training queue must be COMPUTE-only. |

**The summary:** the cloud-GPU loop assumes a hardware shape (one device, HBM, sync step boundary, fused optimizer) that does not exist on this SoC. Copying it loses 2-5× sustained throughput and burns thermal budget on idle devices that are still leaking power. Resistance V2: this is `fp-demogravity` if you copy it because it looks normal.

## What Changes If Hexagon Training Paths Open

If a Hexagon-side autograd path becomes available (full QNN/HTP training extension, or a community path through ExecuTorch HTP backward, or a direct Hexagon SDK build with custom HVX/HMX backward kernels), the natural shape **does not invert** — but it shifts in three measurable ways.

### Change 1: Frozen-middle weight footprint halves

The Adreno-side FP16 BWD copy of the frozen middle (~2.6 GB) is no longer needed. Hexagon emits both forward activations *and* the backward `dL/dh_l` traversal natively. Memory recovered: ~2.6 GB.

That memory recovery unlocks:
- Larger microbatch (8 at seq=512 instead of 4 → fewer Hexagon-Adreno crossings, lower SYNC POINT A overhead).
- Or larger seq (seq=1024 at microbatch 4).
- Or a second trainable adapter set held resident (faculty parallelism).

### Change 2: Pipeline depth can rise to 4

With Hexagon doing both directions, the pipeline becomes:
- Phoenix M tokenizes `b_{k+3}`.
- Hexagon FWD `b_{k+2}`.
- Hexagon BWD `b_{k+1}` (was: Adreno's BWD-through-frozen-middle).
- Adreno trainable FWD+BWD `b_k`.

Adreno is freed from the frozen-middle VJP and concentrates on the trainable boundary kernels (where it is already strong). Adreno utilization on the *useful* gradient work rises. Total throughput estimate: **~1.5-2× the Hexagon-forward-only baseline**, assuming Hexagon BWD perf/W is similar to Hexagon FWD perf/W (a strong assumption that must be measured, not asserted).

### Change 3: A new failure mode appears — Hexagon optimizer

The temptation will be to put the Adam optimizer on Hexagon too (since "the NPU is fast"). **Do not.** Adam is per-parameter scalar arithmetic with mutable state; the CPU is still the natural place because:
- HVX/HMX excels at structured matmul, not scalar update loops.
- Mutable persistent state on Hexagon competes with the compiled-graph residency.
- The CPU is otherwise idle during the steady state and is bandwidth-rich relative to its compute.

The natural shape keeps Adam on Phoenix L even with Hexagon BWD. Hexagon would do FWD and BWD; Adreno would do trainable FWD+BWD and head; CPU would do optimizer + scheduler + data.

### Change 4 (longer-horizon): Hexagon-trained adapter islands

If full Hexagon training is available, the natural extension is to compile **small trainable adapter islands** (e.g., LoRA `A` and `B` matrices for one layer) directly into Hexagon. The compile cost is non-trivial but amortizes over a training interval. This would let LoRA-on-middle-layers stop being ping-pong-forbidden.

### What does NOT change

- DRAM is still 85 GB/s. The memory-bandwidth-bound diagnosis stands.
- Activations still pass through unified DRAM (no PCIe).
- The optimizer step still belongs on Phoenix L.
- The 1F1B schedule is still natural; only the per-stage placement changes.
- Microbatch size is still bounded by activation memory, not by compute.
- TBDR queue rules still apply to Adreno.

**Sensitivity verdict:** Hexagon training is an *upside lever* of ~1.5-2× sustained throughput and ~2.6 GB recovered memory. It is **not** an architectural inversion. The natural shape is robust to Hexagon's availability.

## Falsifiers

The natural shape is wrong (or at least mis-specified) if any of the following is observed in instrumented runs:

1. **Activation transfer Hexagon→Adreno costs more than 5% of the BWD time.** If true, the layout pre-agreement at QNN compile time is failing (CPU repack is happening on the hot path). Verify with `simpleperf` and Adreno GPU profiler; check `dma-buf` import latency. Mitigation: redesign the QNN compile output layout to match Adreno's expected `VkBuffer` layout exactly.

2. **Adreno BWD-through-frozen-middle is slower than recomputing the middle forward on Adreno.** If true, the dual-residency strategy (option 1) fails and option 2 (recompute) is natural instead. Measured by running both and comparing tokens/sec at the same authority gate.

3. **CPU optimizer step latency exceeds half the Adreno per-microbatch latency.** If true, the 1-step staleness pipeline collapses (Adreno catches up to CPU). Move to 8-bit Adam (4× smaller moment state, ~70 ms → ~18 ms on Phoenix L) or batch the optimizer over more accumulation steps.

4. **Sustained Adreno clock drops below 600 MHz under fan + bypass charging.** If true, the throughput model collapses and the natural microbatch may need to drop to keep within the per-step thermal budget. The shape is unchanged; the depth and microbatch size adapt.

5. **`madvise(MADV_WILLNEED)` ahead of UFS-resident weight pages does not prevent hot-path page faults.** If true, expert paging is not viable; faculties must stay DRAM-resident. The shape's expert/cold-weight residency assumption fails.

6. **Hexagon QNN context binary fails to expose external `VkSemaphore`-equivalent or `dma-buf` sync.** If true, SYNC POINT A becomes a CPU-side poll (Phoenix L spinning on a flag), adding ~50-200 µs per microbatch. At microbatch=4 and seq=512, ~80 µs × ~4 microbatches/sec = 320 µs/sec wasted; acceptable. At higher microbatch rates it would be a problem. Verify on SM8750 specifically.

7. **DRAM bandwidth saturates below 60 GB/s sustained under the three-device concurrent load.** If true, the heterogeneous-concurrent assumption fails and serialized execution may match or beat pipelined. Measured via system-wide bus monitor counters.

8. **The dense baseline (Adreno-only forward+backward+optimizer, no Hexagon) outperforms the heterogeneous loop on tokens-per-watt-hour to target validation loss.** This is the **authority falsifier**. If true, the entire heterogeneous shape is `fp-demogravity` and ELO on Adreno-only is the natural answer. Must be the first comparison in Experiment 0.

9. **Weight staleness of 1 effective step degrades convergence of ELO Stage 1 measurably vs synchronous step.** If true, drop the async optimizer (Phoenix L waits for next Adreno BWD to start before beginning Adam). Cost: ~70 ms idle on Phoenix L per step; still tolerable.

10. **Hexagon FWD output activations cannot be made bit-exact reproducible with Adreno's FP16 fwd recompute path.** If true, the BWD-via-Adreno-VJP option (1) produces wrong gradients (the activations the BWD differentiates against are not the activations the FWD actually produced). Mitigation: switch to option 2 (recompute middle on Adreno during BWD using Adreno's own kernels, guaranteed self-consistent). This is a real risk because FP16 numerics differ across HVX/HMX vs Adreno's FP16 path.

## Sources

Primary:
- Snapdragon 8 Elite product brief: https://docs.qualcomm.com/bundle/publicresource/87-83196-1_REV_C_Snapdragon_8_Elite_Mobile_Platform_Product_Brief.pdf
- Qualcomm AI Engine Direct SDK (QNN/QAIRT): https://www.qualcomm.com/developer/software/qualcomm-ai-engine-direct-sdk
- Qualcomm heterogeneous compute whitepaper: https://www.qualcomm.com/content/dam/qcomm-martech/dm-assets/documents/Unlocking-on-device-generative-AI-with-an-NPU-and-heterogeneous-computing.pdf
- Adreno Vulkan TBDR documentation / Qualcomm Vulkan Adreno Layer: https://docs.qualcomm.com/bundle/publicresource/topics/80-78185-2/vulkan-adreno-layer.html

Heterogeneous mobile inference (patterns to adapt for training):
- HeteroInfer / Heterogeneous LLM Inference on Snapdragon 8 Elite: https://arxiv.org/abs/2501.14794
- llm.npu / mllm: https://arxiv.org/abs/2407.05858
- CoDL CPU/GPU co-execution: https://dl.acm.org/doi/10.1145/3498361.3538932
- HeteroLLM / mobile-NPU test-time scaling: https://arxiv.org/abs/2509.23324
- llama.cpp Snapdragon backend (CPU/Adreno OpenCL/Hexagon HTP): https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/snapdragon/README.md

On-device training (the training-specific patterns):
- MeBP — Memory-efficient backpropagation on mobile: https://arxiv.org/abs/2510.03425
- MobileFineTuner: https://arxiv.org/abs/2512.08211
- ZeroQAT (forward-only QAT on phone): https://arxiv.org/abs/2509.00031
- MobiZO / edge fine-tuning via inference engines: https://arxiv.org/abs/2409.15520
- MeZO / fine-tuning with just forward passes: https://arxiv.org/abs/2305.17333
- PockEngine: mobile training engine: https://arxiv.org/abs/2310.17752
- TinyTrain: on-device training under resource constraints: https://arxiv.org/abs/2307.09988
- ELO (selective layer optimization): https://arxiv.org/abs/2601.03648 / https://aclanthology.org/2026.eacl-industry.55
- LoRA: https://arxiv.org/abs/2106.09685
- 8-bit Adam (bitsandbytes): https://arxiv.org/abs/2110.02861

Pipeline parallelism (the schedule patterns being adapted):
- GPipe pipeline parallelism: https://arxiv.org/abs/1811.06965
- PipeDream / 1F1B: https://arxiv.org/abs/1806.03377
- PipeDream-2BW (1F1B with bounded weight staleness): https://arxiv.org/abs/2006.09503
- Async SGD with bounded staleness (Lian et al.): https://arxiv.org/abs/1506.08272

Storage-backed training / activation streaming (UFS-relevance):
- SSDTrain — activation streaming to SSD: https://arxiv.org/abs/2408.10013
- LLM-in-a-flash (Apple): https://arxiv.org/abs/2312.11514
- PowerInfer-2: https://arxiv.org/abs/2406.06282

Memory-efficient optimizers (sensitivity branch):
- GaLore / Q-GaLore: https://arxiv.org/abs/2403.03507 ; https://arxiv.org/abs/2407.08296
- APOLLO: https://arxiv.org/abs/2504.20437

Project-internal prior research:
- `/Users/Zer0pa/Polymat AI/Polymath-AI/RESISTANCE-V2.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/docs/HETEROGENEOUS-SOC-RESEARCH-DIALOGUE.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/docs/research/soc-architecture-2026-05-16/training-systems.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/docs/research/soc-architecture-2026-05-16/soc-runtime-constraints.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/docs/research/soc-architecture-2026-05-16/blind-spots-frontier-scan.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/source-briefs/01-on-device-training-blueprint.md`
