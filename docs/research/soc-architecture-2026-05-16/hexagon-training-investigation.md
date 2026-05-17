# Hexagon NPU Training Investigation

**Date:** 2026-05-16
**Role:** Research Agent
**Target hardware:** RedMagic 10 Pro+ (NX789J), Snapdragon 8 Elite (SM8750), Hexagon v79, 24 GB LPDDR5X, ~85 GB/s
**Scope:** below the QNN/LiteRT/ExecuTorch layer. Is Hexagon a forward-only inference engine by hardware design, or is the inference-only character a tooling artifact removable via Hexagon SDK / HVX intrinsics / HMX direct programming / FastRPC / Triton via Hexagon-MLIR?

## Verdict

**Partial — and the partial line is sharp.** Hexagon on SM8750 is *not* a hardware appliance that can only do forward inference. The HVX scalar/vector core is a general-purpose VLIW SIMD with IEEE-class FP32 and FP16, gather/scatter, predication, and arbitrary control flow — clearly Turing-complete for compute and clearly capable of running gradient kernels in principle. The HMX matrix unit *is* the inference-only piece, and its constraints are real: undocumented instruction set, proprietary Crouton tile layout, FP16-output-only converter from the internal accumulator, and an HMX→TCM-only memory addressing model. Qualcomm's own open-source compiler (Hexagon-MLIR / Triton, Feb 2026) ships only forward LLM kernels (matmul, softmax, GELU, SiLU, rms_norm, flash_attention, rope, rsqrt, sum) and no backward, optimizer, or gradient op exists in any open-source code I could find for Hexagon.

The honest decomposition is:

| Training subtask | Hexagon feasibility | Why |
|---|---|---|
| Forward pass of frozen layers (FP16 weights, FP16 activation) | Strong — already production code | HMX FP16 matmul + HVX softmax/norm — covered by ggml-hexagon, hexagon-mlir, htp-ops-lib, QNN. ~12 TFLOPS HMX FP16. |
| Forward pass with FP32 weights / FP32 activations | Weak | HMX is FP16-tile-locked. HVX has FP32 (32-element vectors, 1024-bit) but at ~33 GFLOPs FP16-equivalent per HVX thread — orders of magnitude slower than HMX. |
| Backward of frozen layers (activation recomputation) | Strong (it IS just forward) | Identical to forward. Hexagon can do this fine. |
| Backward of trainable layers (matmul-transpose, outer-product) | Weak-to-medium | Requires writing custom HMX or HVX kernels for `dW = X^T · dY` and `dX = dY · W^T`. HMX needs Crouton-layout transpose kernels which would need to be reverse-engineered (Qualcomm has not published them and removed the qhl_hmx sample from SDK 6.x). HVX-only matmul is too slow to be useful at training scale. |
| Gradient accumulation in FP32 across microbatches | Weak | HMX accumulator can only flush back to TCM as FP16 (`cvt.hf = acc`); the internal accumulator format is wider but the converter is FP16-out only as documented. HVX FP32 accumulation in software works but at ~33 GFLOPs. |
| Optimizer step (AdamW: requires sqrt, division, FP32 m/v state) | Medium | HVX FP32 + sqrt/inv intrinsics exist and would work; ~105M trainable params (per ELO Stage 1) is ~210 MB optimizer state and a tiny FLOP count vs the matmul itself, so FastRPC overhead would dominate, not compute. Better on CPU. |
| Scatter/gather (embedding tables, attention indices) | Weak | `vgather` exists but with 24–48 instruction-packet latency on V75, and HMX *cannot address* anything outside TCM. Authors of EuroSys '26 paper had to design custom LUT layouts to avoid it. |
| Forward-Forward training (Hinton's no-backward algorithm) | Strong-at-forward, Weak-at-novelty | Two forward passes per step with per-layer local goodness loss. Hexagon does the forward fine; the local-loss compute is small enough for CPU/HVX. But Forward-Forward has not been shown competitive with backprop for LLM-scale models — this is a research bet, not a known win. |
| Predictive-coding-style local error compute | Same as Forward-Forward | Per-layer local loss, no global backward. Hexagon forward + HVX local op. Algorithm immaturity for LLMs is the gate, not Hexagon capability. |
| Zeroth-order / MeZO finite-difference gradient | Strong | Pure forward-pass-only training. Two forward passes per step. The current bottleneck would be ELO trainable count × forward cost × number of perturbations to converge — not Hexagon capability. |

**Operator's hypothesis (Hexagon underutilized due to tooling rather than hardware) is partly right and partly wrong.** Right: the HVX scalar/vector core is far more programmable than QNN exposes, and Hexagon-MLIR + the open Hexagon SDK + ggml-hexagon prove you can author custom kernels in Triton/C/inline-assembly that bypass QNN entirely. Wrong: even at the lowest level you reach, the HMX matrix unit — which is where the 12 TFLOPS FP16 throughput actually lives — has a deliberately narrow programmable surface (proprietary tile layout, undocumented instructions, FP16-out converter, TCM-only addressing). You cannot wave away the HMX constraints by going lower; lower *is* the FP16-Crouton-tile model.

**The recommendation that follows for Polymath-AI:** keep Hexagon as a frozen-layer FP16 forward engine (which is what the existing brief calls for), and do not attempt to put backward, optimizer, or gradient accumulation on the HMX. Put backward on Adreno Vulkan and optimizer on Oryon CPU as already planned. This is not a soft refusal — this is recognising that fixing HMX takes Qualcomm-or-equivalent engineering investment (reverse-engineering more of the undocumented HMX ISA, building Crouton-layout transpose kernels, building a FP32 readout path) for a result that the Adreno Vulkan path can deliver today with documented APIs.

## Hexagon Programmable Surface

What you actually have access to on SM8750 / Hexagon v79, ranked from most-supported (top) to least (bottom):

| Layer | Public? | What it exposes | What it costs to use |
|---|---|---|---|
| QNN / QAIRT / Qualcomm AI Engine Direct | Closed-source, supported | Compiled context binaries for a static FP16/INT8 graph. AOT-compiled. No per-step graph mutation. | Already empirically failed on this project (per CURRENT_PUBLIC_STATUS.md). |
| LiteRT QNN Accelerator | Closed-source, supported, Google-Qualcomm | LiteRT delegate → QNN context binaries. Same constraint. | Same failure mode. |
| ExecuTorch Qualcomm backend | Open-source partitioner around QNN | PyTorch graph → QNN partition. Quant schemes 8a8w/16a16w/16a8w/16a4w. | Same QNN backend underneath. |
| **Hexagon-MLIR + Triton** (Qualcomm, Feb 2026) | Open-source | Triton kernels in Python → MLIR → LLVM → Hexagon binary. Targets v73/v75/v79. Compile-once-to-binary, not JIT. Up to 80% of hand-tuned kernel performance. | Setup is heavy (Hexagon SDK + custom LLVM build + Python 3.11). Demonstrated kernels: matmul, layer_norm, rms_norm, gelu, silu, softmax, flash_attention (forward), rope, rsqrt, sum, vector add — **all forward-pass**. Matmul is FP16 with `atol=0.2` tolerance, suggesting FP16 accumulation, not FP32-accumulate-FP16-out. |
| **Hexagon Kernel Library (HexKL)** | "Available on request" — not fully open | C/C++ matmul-hexkl kernels using HMX intrinsics directly. Integrated as `matmul_hexkl` in Hexagon-MLIR. | Gated availability. Source not in the GitHub mirror. |
| llama.cpp Snapdragon backend (ggml-hexagon) | Open-source (in ggml-org/llama.cpp main) | C kernels using HVX intrinsics + inline HMX assembly. FastRPC from Android app to cDSP. Supports HTP libraries for v73/v75/v79/v81. Op list: MUL_MAT (Q4_0/Q8_0/IQ4_NL/MXFP4 × FP16), softmax, RMS_NORM, ROPE, FLASH_ATTN_EXT, GET_ROWS/SET_ROWS, CPY, ADD/SUB/MUL/DIV, SQRT, SQR, ARGSORT, CUMSUM, FILL, REPEAT, SUM_ROWS, UNARY, GLU, SSM_CONV, GATED_DELTA_NET, L2_NORM, SCALE, DIAG, SOLVE_TRI. | None of `OUT_PROD`, `OPT_STEP_ADAMW`, `CROSS_ENTROPY_LOSS_BACK`, `REPEAT_BACK`, `RMS_NORM_BACK`, `SOFT_MAX_BACK`, `SILU_BACK`, `ROPE_BACK` (the ggml backward/optimizer ops) are supported on Hexagon. They would need to be written. |
| Hexagon NPU SDK / Hexagon DSP SDK | Open-tools (gated download) | LLVM-based Hexagon compiler (Q6 toolchain), HVX intrinsics in C, IDL→stub/skel codegen, FastRPC. | Direct programming. You write `libfoo.so` for AArch64 (CPU stub) and `libfoo_skel.so` for Hexagon (Q6 skeleton), exchange via FastRPC. This is the surface htp-ops-lib uses. |
| Halide-for-HVX | Documented | DSL for HVX kernels — image-processing oriented. INT8/INT16 strongest; FP added later. | Mature for vision workloads; underused for ML. |
| **Direct HVX intrinsics + inline assembly** | Open-instruction-set | 32×1024-bit vector registers (32 elements at FP32, 64 at FP16, 128 at INT8). Floating point on HVX v68+. IEEE-754 round-to-even on v79. QFloat internal format. Arithmetic + reductions + sqrt/inverse via Newton iteration + scatter/gather (vgather, vscatter). | Fully open ISA — Hexagon is the only mobile NPU with a publicly documented vector ISA (this is acknowledged in the llm.npu paper). FP32 is supported but the throughput is much lower than HMX. |
| **HMX (Hexagon Matrix Extension) direct programming** | Mostly undocumented | 1–2 HMX units per NPU. 32×32 FP16 tiles (2 KiB each). ~12 TFLOPS FP16 GEMM. Internal accumulator is wider than FP16 (described as upcast to 32-bit for row-wise reductions) but the only converter path documented in user-visible HMX assembly is `cvt.hf = acc` which downcasts to FP16. Crouton tile layout. Inputs/outputs in TCM only. Per-channel bias/scale (256 B region). | The `qhl_hmx` sample that documented HMX assembly was **removed from Hexagon SDK 6.x**. Microsoft Research's htp-ops-lib (and the EuroSys '26 paper) explicitly reverse-engineered HMX instructions from binary libraries. There is an open issue in TileLang asking for HMX support that remains unanswered. Hexagon-MLIR's HMX path goes through HexKL which is access-gated. |
| **FastRPC** | Open-source (qualcomm/fastrpc, GitHub) | RPC dispatch from Android user process to cDSP/aDSP. IDL-defined contract. Overhead measured: ~75 µs for 0 KB noop; ~238 µs at 32 KB; ~400 µs typical decode-step synchronization; ~4 ms for 1 MB transfer. | Per-call overhead dominates for small ops; batch work into one mega-kernel rather than many small dispatches. This is exactly why Hexagon-MLIR emphasises "mega-kernels that maximize data locality in TCM." |

**Memory hierarchy on Hexagon NPU (v75 reference, v79 similar):** 1 MiB L2 cache, 8 MiB software-managed TCM ("VTCM"), 32-bit virtual address space (limits any single Hexagon graph to ~3B params on older devices). HVX accesses L2 and TCM. **HMX accesses TCM only.** DMA engines deliver 60+ GB/s into TCM from DDR; HVX-via-L2 is ~26 GB/s.

**The cDSP/aDSP distinction matters for power but not for compute.** On SM8750, all AI workloads go to the cDSP (compute DSP); aDSP is for low-power audio. The Hexagon NPU as Qualcomm markets it is the cDSP with its HVX/HMX coprocessors. The user-space FastRPC binding `libggml-htp-v79.so?...&_dom=cdsp` is the canonical entry point.

## Evidence of Training on Hexagon

I searched arxiv, GitHub, IEEE Xplore, ACM (MobiSys/EuroSys/ASPLOS/MLSys), and Qualcomm/Google/Microsoft developer blogs through 2026-05. **There is no public evidence of anyone training a neural network on Hexagon as the training device** — not for fine-tuning, not for personalization, not for proof-of-concept demos. The negative evidence is strong and direct:

| Work | Verdict | Quote / behaviour |
|---|---|---|
| MobiLLM (arXiv:2502.20421, 2025) | Explicitly rules out Hexagon for training | "Mobile accelerators are tailored for inference rather than training" and "[Hexagon, Edge TPU] lack acceleration support for backpropagation-specific operations." They keep frozen backbone on device, ship activations to a server for backward. |
| MobileFineTuner (arXiv:2512.08211, 2025) | Trains on CPU only | Pixel 7/8 (Tensor G2/G3 — not Hexagon) and Apple M2. No Hexagon use even when fine-tuning Gemma 3 / Qwen 2.5 on commodity phones. Bottleneck described as RAM, not NPU. |
| PAE MobiLLM (arXiv:2507.01216, 2025) | Same as MobiLLM | Side-tuning offloads backward to server. |
| Microsoft Research test-time scaling on Hexagon (arXiv:2509.23324, EuroSys '26) | Forward-only LLM inference | Three Snapdragon generations (V73/V75/V79). 12 TFLOPS FP16 GEMM on HMX measured. **All work is inference compute, no backward.** Reverse-engineered HMX instructions. |
| Hexagon-MLIR (Qualcomm, arXiv:2602.19762, Feb 2026) | Forward-only kernels | Triton kernels for matmul, softmax, gelu, silu, rms_norm, flash_attention (forward), rope, rsqrt, sum. Targets v73/v75/v79. No backward, no optimizer kernel demonstrated. |
| ggml-hexagon (llama.cpp main, 2025–2026) | Forward-only | HTP libraries for v73/v75/v79/v81. Op set listed above. No backward, no optimizer. |
| htp-ops-lib (Microsoft Research, github.com/haozixu/htp-ops-lib) | Forward-only | "Operator library supporting LLM inference on Qualcomm Hexagon NPU." Inline HMX assembly. No training ops. |
| Qualcomm "Unlocking on-device GenAI with NPU" whitepaper | Forward-only positioning | Whole document positions NPU as inference accelerator for generative AI. Training is not in scope of any Qualcomm-published artifact for mobile Hexagon. |
| llm.npu (ASPLOS '25, arXiv:2407.05858) | Forward-only | Built on top of QNN, no QNN bypass, primary goal "reduce the prefill latency." Notes Hexagon is "the only mobile NPU with an open instruction set" — but does not train. |
| HeteroLLM (Shanghai Jiao Tong, arXiv:2501.14794, MobiSys '25) | Heterogeneous inference dispatch | Uses NPU+GPU+CPU on SM8750 for *inference*, no backward. Reports 1.34×–6.02× speedup vs single-unit inference. |
| MICRO '23 interleaved gradient order for NPU training | Not Hexagon-specific | This paper proposes gradient-order optimizations for NPU on-chip memory — for hypothetical training-class NPUs (server/edge generic), not Hexagon. They model both edge and server NPUs but the work is hardware-design-space, not Hexagon-implementation. |

So zero training receipts on Hexagon. The reason given consistently across the literature is **not** "we tried and the silicon couldn't do it" — it is "the SDK exposes inference paths only; building backward paths would require building the whole stack ourselves." This is exactly the operator's hypothesis, and the existence of open Hexagon-MLIR + open ggml-hexagon shows the stack *is* now buildable. But it has not been built. There is no production or research-prototype demonstration of Hexagon doing a backward pass.

## Training-Relevant Op Coverage

What you would actually need for transformer training, by op class:

| Op | Forward existence on Hexagon | Backward existence on Hexagon | Comment |
|---|---|---|---|
| **Matmul FP16, FP16 weights × FP16 activation** | Yes (HMX, ~12 TFLOPS; HVX fallback ~33 GFLOPs per thread) | No published kernel | Forward is the hot ggml-hexagon / Hexagon-MLIR path. Backward needs `dW = X^T · dY` and `dX = dY · W^T`. Both reduce to two more matmuls of the same shape class, so they map to HMX in principle. The blocker is that HMX inputs are Crouton-tiled and you would need a transposed Crouton layout for one operand. None of the open-source code demonstrates this. |
| **Matmul with FP32 accumulator output** | Internally yes (HMX accumulator is described as 32-bit wider for row-reductions) | n/a | The user-visible converter is `cvt.hf = acc(2); mxmem = cvt` which outputs FP16. There is no documented `cvt.sf = acc` instruction in any source I found. The accumulator state appears to be inaccessible as FP32 to user code. If you want FP32 gradient accumulation, you do it in HVX FP32 after the HMX output is unpacked — at HVX throughput, ~30× slower than HMX. |
| **BF16 native** | No | No | BF16 is not in the supported precision list anywhere (HMX is INT4/INT8/INT16/FP16; HVX is INT8/INT16/INT32/FP16/FP32). The bfloat range/precision tradeoff for training has no native Hexagon path; you would emulate. |
| **FP32 native compute on HVX** | Yes (32-element FP32 vectors per 1024-bit register, v68+ floating point) | Same hardware | This is the answer to "can I do an Adam step on Hexagon?" — technically yes. Throughput is HVX-class not HMX-class, so it is a CPU-replacement, not a CPU-massive-speedup. |
| **Transpose** | HVX has shuffle/permute and there is a separate `TRANSPOSE` ggml op handled by reshape/permute (no compute) on Hexagon | No physical-transpose-with-stride backward kernel | For training you need *physical* transpose of activation tensors (because backward uses `X^T`), and on HMX you need to produce Crouton-layout transposed input. Neither htp-ops-lib nor ggml-hexagon nor Hexagon-MLIR demonstrate this. |
| **Scatter / gather** | `vgather` exists; latency 24–48 instruction packets on V75; HMX cannot address outside TCM | Same constraints | EuroSys '26 paper explicitly designs custom LUT layouts to avoid vgather. Embedding gradient (sparse scatter into the embedding table) would be CPU-or-Adreno work, not Hexagon. |
| **Reduction (sum, mean)** | `SUM_ROWS`, `CUMSUM` exist as HVX kernels; `hvx_vec_reduce_sum_qf32x2` is in ggml-hexagon | Backward of sum is broadcast, trivial | Reductions are fine. |
| **Softmax** | Yes (numerically stable online softmax; HVX exp/inv intrinsics) | No `SOFT_MAX_BACK` kernel | Backward softmax is one matmul and one elementwise; would map to HMX/HVX. |
| **RMSNorm / LayerNorm** | Yes | No `RMS_NORM_BACK` | Backward needs reduction + scaled vector ops, all of which HVX can do. |
| **GeLU / SiLU / SwiGLU activations** | Yes | No `SILU_BACK` | Backward is elementwise scalar function evaluation; trivial on HVX. |
| **RoPE** | Yes | No `ROPE_BACK` | Backward is just running the same rotation with negated angle. |
| **Embedding gather** | `GET_ROWS` exists | `SET_ROWS` exists for forward scatter; **embedding backward** is the sparse-scatter-into-table case which is what scatter-on-TCM cannot do across the full embedding table (table size ~150K × hidden_dim FP16 ≈ ~900 MB at Qwen2.5-1.5B; will not fit in 8 MiB TCM). | This is one of the hard infeasibility cases. Embedding backward must run on CPU/Adreno. |
| **Adam optimizer state update** | No `OPT_STEP_ADAMW` Hexagon kernel | n/a | Tiny FLOP count compared to matmul. Writing one in HVX FP32 is feasible but unrewarding — CPU or Adreno is fine. |
| **Cross-entropy loss + backward** | No `CROSS_ENTROPY_LOSS_BACK` | No | Last layer can be on Adreno; no value adding to Hexagon. |

The pattern is consistent: **every forward op required for transformer inference has a Hexagon kernel; zero of the corresponding backward / optimizer ops do.** This is not a hardware fact — most of the backward kernels would be straightforward to write on HVX, and the matmul-backward ones could leverage HMX with the missing Crouton-transpose kernel. It is a tooling fact, and the cost to close it is real engineering work, not weeks of cleanup.

## Path To Use (if pursued)

Minimum viable engineering investment to put part of training on Hexagon:

**Step 0 (zero investment):** Keep Hexagon as the frozen-layer forward engine, exactly as the existing brief specifies. Use Hexagon-MLIR's Triton flash_attention and matmul kernels — these are open-source today and target v79. **This is the recommended path.**

**Step 1 (~2 engineer-weeks):** Add HVX kernels for backward of the elementwise / norm ops (`SILU_BACK`, `RMS_NORM_BACK`, `SOFT_MAX_BACK`, `ROPE_BACK`). These are small and follow the existing forward kernels. Useful only if you have committed to running gradient compute on Hexagon — otherwise Adreno does this fine.

**Step 2 (~4–6 engineer-weeks):** Write HVX FP32 kernels for the matmul backward (`OUT_PROD` and matmul-transpose variants), at ~30× lower throughput than HMX. This makes Hexagon a CPU-replacement-class trainer for the trainable layers, which is slower than the Adreno Vulkan FP32 path (1.79 TFLOPS) and pointless.

**Step 3 (~3–6 engineer-months, high risk):** Reverse-engineer the HMX instruction set for (a) FP32 accumulator readout if it exists, (b) Crouton-layout transpose of activation tiles, (c) per-channel-scale-and-bias use in the backward direction. Build matmul-backward HMX kernels. This is what would actually unlock training throughput on Hexagon. Risk: if Qualcomm continues closing HMX (they already removed the qhl_hmx sample from SDK 6.x), the result is undocumented-and-officially-deprecated code that may break on future SoCs or with firmware updates. Reward: ~12 TFLOPS FP16 training-class matmul throughput on a phone, which is unique.

**Step 4 (~6+ engineer-months, very high risk):** Build a real FP32 path inside HMX if one exists in silicon but is not exposed. There is no public evidence that FP32 HMX exists; the precision list across all generations of Hexagon NPU is INT4/INT8/INT16/FP16. Going beyond requires Qualcomm partnership or much deeper RE.

For Polymath-AI under Resistance V2: **Steps 0 is the right choice now. Steps 1–4 are not justified by the project's authority metric.** The governing objective is multilingual continual pretraining of a 1.5B model on phone, with ELO Stage 1 keeping the trainable surface at ~7% of full CPT. The bottleneck is *not* Hexagon FLOPs — it is Adreno FP32 throughput (1.79 TFLOPS) and 85 GB/s memory bandwidth. Even if Step 3 succeeded, the training would still be Adreno-bandwidth-bound or thermal-bound long before Hexagon-compute-bound. Step 3 is a "research bet on closing a Qualcomm tooling gap," which is a *different* governing objective than Polymath-AI's.

## Compromise Architectures (training subtasks that could realistically live on Hexagon)

Ordered by ratio of value-delivered to engineering-required:

1. **Forward pass of frozen layers in FP16 via HMX.** Already-built. Zero engineering. Already in the brief. This is the answer.

2. **Forward-Forward (Hinton 2022) or predictive-coding-style local-loss training, where there is no global backward at all.** Each step is two forward passes + a tiny local loss; Hexagon does both forwards. Algorithm risk dominates engineering risk — Forward-Forward has not been shown to match backprop on LLM-scale models. If you are willing to take a research bet on the algorithm, the hardware is fine.

3. **MeZO / Zeroth-order optimization (Malladi et al. 2023).** Pure forward-pass training using finite-difference gradients. Two forward passes per step with a Rademacher random perturbation. Hexagon supports the forwards at full throughput. The catch is that MeZO needs many more steps than first-order training, so wall-clock can be worse. For a 1.5B model with ELO restricting trainable params to ~105M, MeZO might actually be competitive, and the Hexagon-only execution would be unusually clean.

4. **Forward-only adapter inference for hot-swappable adapters (not training).** If an Adreno/CPU training loop produces an adapter weight, that adapter can be merged into a frozen-quantized base on Hexagon at the next graph rebuild. Hexagon never sees the gradient. This is what the brief already describes.

5. **Static-graph optimizer state update for ELO trainable layer params.** Adam's compute is fixed-shape across steps (param shape doesn't change, only values do), so in principle you could compile it once as a QNN graph and just push new gradient values each step. But the gradient values are FP32 and QNN graphs are FP16/INT8 — you would have to live with FP16 optimizer state, which destabilizes Adam, especially the variance term `v_t`. Not recommended; the Oryon CPU does this in microseconds.

6. **Frozen-layer activation recomputation in service of activation checkpointing.** When the backward pass needs an activation that was checkpointed (not stored), you recompute via the frozen forward. That recompute is just inference, so HMX does it at 12 TFLOPS. This is meaningful — it would mean activation checkpointing on Hexagon-frozen-forward is nearly free, which makes the Adreno backward memory-budget more relaxed.

7. **Embedding gather for training input batches.** `GET_ROWS` on Hexagon. Input embedding gather is fine; the embedding *backward* (sparse scatter to update the embedding table) is the hard case and stays on Adreno/CPU.

## Hard Falsifiers

What observation would close this question definitively, in either direction:

**A. Falsifier for "Hexagon can do training-relevant matmul backward."**
Build a custom kernel that computes `dW = X^T · dY` with FP16 inputs, FP32-accumulated, FP16 or FP32 output, using HMX. Measure throughput. If you get within 2× of forward HMX throughput (~6 TFLOPS for backward), the answer is "tooling closable." If you cannot get above 1 TFLOPS, the HMX surface really is forward-locked and the answer is "structurally inference-locked."

**B. Falsifier for "FastRPC overhead does not destroy small-step training."**
Measure the wall-clock cost of a single Hexagon dispatch for a training-step-shaped op: 1 matmul forward + 1 matmul backward + 1 optimizer step. If it is >2 ms per step including FastRPC overhead, then at the throughput needed for Polymath-AI's ~2M tokens/hour gate, Hexagon is sync-bound. If <500 µs, it is not the bottleneck.

**C. Falsifier for "training algorithms exist that map to Hexagon's forward-only character."**
Train a small model (say a 125M GPT-2 variant) for 1 hour on Hexagon-only using Forward-Forward or MeZO. Compare to 1 hour of backprop training on Adreno. If the Hexagon-only runs achieve >50% of the loss reduction of backprop, the compromise architecture is viable.

**D. Falsifier for "Qualcomm will not close the HMX surface further."**
Track Hexagon SDK 7.x and Hexagon NPU SDK releases through Q3 2026. If `qhl_hmx` or equivalent HMX-direct samples reappear in the public SDK, the tooling situation is opening. If undocumented HMX instructions in v79 and v81 binary libraries continue to require reverse-engineering, the surface is closing.

**E. Falsifier for the practical Polymath-AI assumption.**
Run Experiment 0 from the existing brief: Qwen2.5-1.5B ELO Stage 1 on real hardware. If sustained throughput is >500K tokens/hour with the existing Adreno-and-CPU plan, Hexagon-for-training is not on the critical path and need not be pursued. If <100K tokens/hour and the bottleneck is Adreno FP32 throughput, then Hexagon-training-acceleration becomes a candidate for Phase 2.

## Sources

Primary technical documentation:

- Hexagon V79 Programmer Reference Manual: https://docs.qualcomm.com/bundle/publicresource/topics/80-N2040-60
- Hexagon V79 HVX Programmer Reference Manual: https://docs.qualcomm.com/bundle/publicresource/topics/80-N2040-61
- Hexagon V79 HVX Programmer Reference Manual (mirror, full PDF): https://docs.alexrp.com/hexagon/hexagon_v79_hvx.pdf
- HVX floating point chapter (v79): https://docs.qualcomm.com/bundle/publicresource/topics/80-N2040-61/hvx-floating-point.html
- Halide for HVX User Guide: https://docs.qualcomm.com/bundle/publicresource/80-PD002-1_REV_F_Halide_for_Qualcomm_Hexagon_Vector_Extensions__HVX__User_Guide.pdf
- Hexagon NPU SDK landing page: https://www.qualcomm.com/developer/software/hexagon-npu-sdk
- Snapdragon 8 Elite SM8750 Product Brief: https://www.qualcomm.com/content/dam/qcomm-martech/dm-assets/documents/Snapdragon-8-Elite-SM8750-3-AB-Product-Brief.pdf

Open-source Hexagon programming:

- Qualcomm Hexagon-MLIR repository: https://github.com/qualcomm/hexagon-mlir
- Hexagon-MLIR FAQ: https://github.com/qualcomm/hexagon-mlir/blob/main/docs/faq.md
- Hexagon-MLIR user guide: https://github.com/qualcomm/hexagon-mlir/blob/main/docs/user-guide.md
- Hexagon-MLIR Triton kernel tests directory: https://github.com/qualcomm/hexagon-mlir/tree/main/test/python/triton
- Hexagon-MLIR matmul test (FP16 with atol=0.2): https://github.com/qualcomm/hexagon-mlir/blob/main/test/python/triton/test_matmul.py
- Hexagon-MLIR flash attention test (forward only): https://github.com/qualcomm/hexagon-mlir/blob/main/test/python/triton/test_flash_attention.py
- Qualcomm blog announcing Hexagon-MLIR (Feb 2026): https://www.qualcomm.com/developer/blog/2026/02/build-faster-on-hexagon-npu-tritor-pytorch-with-hexagon-mlir-open-source
- Qualcomm FastRPC open-source repository: https://github.com/qualcomm/fastrpc
- llama.cpp Snapdragon backend documentation: https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/snapdragon/README.md
- llama.cpp Hexagon backend ops (`ggml-hexagon` source): https://github.com/ggml-org/llama.cpp/tree/master/ggml/src/ggml-hexagon
- llama.cpp Hexagon HMX matmul source: https://github.com/ggml-org/llama.cpp/blob/master/ggml/src/ggml-hexagon/htp/hmx-matmul-ops.c
- htp-ops-lib (Microsoft Research self-implemented Hexagon ops with HMX inline assembly): https://github.com/haozixu/htp-ops-lib
- ggml-hexagon HMX usage discussion: https://github.com/ggml-org/llama.cpp/discussions/17655
- ggml-hexagon (original reference impl, archived): https://github.com/jeffzhou2000/ggml-hexagon

Peer-reviewed and preprint research on Hexagon LLM compute:

- Hao, Wei, Wang, Huang, Jiang, Jiang, Cao, Ren. "Scaling LLM Test-Time Compute with Mobile NPU on Smartphones." EuroSys '26 / arXiv:2509.23324. — measured HMX FP16 throughput, FastRPC overheads, vgather latency on V73/V75/V79, reverse-engineered HMX. https://arxiv.org/abs/2509.23324
- Baskaran et al. "Hexagon-MLIR: An AI Compilation Stack For Qualcomm's Neural Processing Units." arXiv:2602.19762, Feb 2026. https://arxiv.org/abs/2602.19762
- Xu et al. "Fast On-device LLM Inference with NPUs." llm.npu, ASPLOS '25. arXiv:2407.05858. https://arxiv.org/abs/2407.05858
- Chen et al. "HeteroLLM: Accelerating Large Language Model Inference on Mobile SoCs with Heterogeneous AI Accelerators." MobiSys '25 / arXiv:2501.14794. https://arxiv.org/abs/2501.14794
- Hexagon-MLIR LLVM dev meeting talk slides (Oct 2025): https://llvm.org/devmtg/2025-10/slides/quick_talks/baskaran_slama.pdf

Mobile on-device training research (all of which avoid Hexagon for backward):

- Li et al. "MobiLLM: Enabling LLM Fine-Tuning on the Mobile Device via Server Assisted Side Tuning." arXiv:2502.20421. Explicitly states Hexagon and Edge TPU "lack acceleration support for backpropagation-specific operations." https://arxiv.org/abs/2502.20421
- Zhang et al. "PAE MobiLLM: Privacy-Aware and Efficient LLM Fine-Tuning on the Mobile Device via Additive Side-Tuning." arXiv:2507.01216. https://arxiv.org/abs/2507.01216
- Park et al. "MobileFineTuner: A Unified End-to-End Framework for Fine-Tuning LLMs on Mobile Phones." arXiv:2512.08211. CPU-only fine-tuning of GPT-2, Gemma 3, Qwen 2.5 on Pixel and M2; never touches Hexagon. https://arxiv.org/abs/2512.08211

Architectural deep-dives:

- Chester Lam. "Qualcomm's Hexagon DSP, and now, NPU." Chips and Cheese, Oct 2023. https://old.chipsandcheese.com/2023/10/04/qualcomms-hexagon-dsp-and-now-npu/
- Babbage. "Qualcomm's Hexagon AI Accelerators." The Chipletter (Substack). https://thechipletter.substack.com/p/qualcomms-hexagon-ai-accelerators
- Qualcomm. "Qualcomm Hexagon Tensor Processor." HotChips 2023 slides. https://www.hc2023.hotchips.org/assets/program/conference/day2/ML%20Inference/HC2023%20Qualcomm%20Hexagon%20NPU.pdf
- Wikipedia, Qualcomm Hexagon: https://en.wikipedia.org/wiki/Qualcomm_Hexagon
- Wikichip, Hexagon microarchitecture: https://en.wikichip.org/wiki/qualcomm/microarchitectures/hexagon
- DeepWiki, Hexagon NPU Hardware Features (Hexagon-MLIR project): https://deepwiki.com/qualcomm/hexagon-mlir/3.2-hexagon-npu-hardware-features

Forward-only training algorithm candidates (if Hexagon-only training is pursued):

- Hinton. "The Forward-Forward Algorithm: Some Preliminary Investigations." 2022. https://www.cs.toronto.edu/~hinton/FFA13.pdf
- Malladi et al. "Fine-Tuning Language Models with Just Forward Passes." MeZO. NeurIPS 2023. https://arxiv.org/abs/2305.17333
- Salvatori et al. "Predictive Coding Networks and Inference Learning: Tutorial and Survey." ACM Computing Surveys 2025. https://dl.acm.org/doi/10.1145/3797870
- Kim et al. "Predictive Coding-based Deep Neural Network Fine-tuning for On-Device Domain Adaptation." arXiv:2509.20269.
