# RAM Residency For Qwen3.6-35B-A3B On A 24GB Phone

Date: 2026-05-16  
Scope: RedMagic-class Android phone, 24GB unified RAM, large UFS storage, Snapdragon 8 Elite-class CPU/GPU/NPU.  
Question: whether "35B total / 3B active" MoE models can be treated as 3B-RAM models for inference or adaptation.

## Hard Verdict

**Qwen3.6-35B-A3B is a north-star target, not a viable first target, for Polymath-AI on a 24GB Android phone.**

The core reason is simple: **active parameters are a compute/FLOP statement, not a residency guarantee.** A token may execute only about 3B parameters, but the router can choose from the full expert bank at each MoE layer. For normal low-latency inference, the embeddings, routers, shared layers, shared experts, selected routed experts, cache/state, and runtime workspaces must be in a fast resident memory tier. The full expert bank must at least be addressable with predictable latency.

"Load the whole model into RAM" is not old-fashioned if "RAM" means CPU DRAM/unified memory rather than all weights in accelerator VRAM. What is old-fashioned is assuming every weight must sit in GPU/NPU SRAM/VRAM. Modern MoE runtimes can place routed experts on CPU RAM and hot/shared compute on GPU. They do **not** make UFS cold storage equivalent to RAM for per-token expert misses.

First target should be a dense 3B-4B model or a smaller total-size MoE such as OLMoE-1B-7B / LFM2-8B-A1B. Qwen3.6-35B-A3B becomes a first target only if the memory experiment at the end passes under sustained thermal and page-fault telemetry.

## Model Facts That Matter

Qwen3.6-35B-A3B is a hybrid multimodal MoE. Its Hugging Face config reports `qwen3_5_moe`, 40 text layers, hidden size 2048, 256 experts, 8 routed experts per token, a shared expert, 262,144 native max positions, and a layer pattern of three linear-attention layers followed by one full-attention layer. The Qwen/vLLM recipe summarizes it as **35B total / 3B active, 256 experts, 8 routed + 1 shared**.

Qwen3-30B-A3B, the cleaner text-only predecessor target, is listed by Qwen as **30.5B total / 3.3B activated**, 48 layers, 128 experts, and 8 activated experts.

Sources:

- Qwen3.6 model card: https://huggingface.co/Qwen/Qwen3.6-35B-A3B
- Qwen3.6 config: https://huggingface.co/Qwen/Qwen3.6-35B-A3B/raw/main/config.json
- Qwen3-30B-A3B model card: https://huggingface.co/Qwen/Qwen3-30B-A3B
- Qwen3-30B-A3B config: https://huggingface.co/Qwen/Qwen3-30B-A3B/raw/main/config.json
- vLLM Qwen3.5/3.6 recipe: https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3.5.html

## What Must Be Resident

For normal inference, these are not optional:

- Token embeddings and LM head/output projection.
- Attention or linear-attention blocks, norms, residual paths, rotary/state logic, and MTP/speculation heads if enabled.
- Routers/gates for every MoE layer.
- Shared experts, because they are always active in Qwen3.6-style routing.
- KV cache or recurrent/DeltaNet state cache, plus scheduler/runtime workspaces.
- The selected routed expert weights for the current token/layer.
- Enough metadata and dispatch tables to map router decisions to expert tensors.

The routed expert bank is the contested part. In a vanilla serving setup, all experts are loaded across accelerator memory or CPU memory. In a heterogeneous MoE setup, non-shared routed experts can live in CPU DRAM while shared/hot paths live on GPU. But **some fast memory tier must hold the expert bank or a cache with extremely high hit rate**. If the only copy of a cold expert is on UFS, every miss becomes a storage page fault or explicit read on the decode path.

The router decision itself is per token and per layer. You cannot know all future experts at load time. Any expert can become active for the next token, so "only keep the active 3B in RAM" means one of three things:

1. You already computed routing and prefetched correctly.
2. You pruned/disabled experts and changed the model.
3. You accept unpredictable UFS reads on the hot path.

Only the first can preserve the model. The second is a new model requiring evaluation. The third is not a serious latency target until measured.

## Offload And Paging Reality

**vLLM/SGLang reality:** Qwen's own examples serve Qwen3.6 with tensor parallelism across 8 GPUs for the 262K context. vLLM lists Qwen3.6-35B-A3B as about **84GB BF16** and **42GB FP8** in its recipe index. vLLM supports CPU weight offload, but its docs describe this as a virtual extension of GPU memory that requires a fast CPU-GPU interconnect because model parts are accessed during each forward pass.

- vLLM offload docs: https://docs.vllm.ai/en/stable/api/vllm/config/offload/
- vLLM quantization docs: https://docs.vllm.ai/en/latest/features/quantization/
- vLLM Qwen recipe index: https://recipes.vllm.ai/Qwen

**KTransformers reality:** KTransformers is the best primary-source evidence that "not all experts in GPU memory" is real. The SOSP 2025 paper places shared experts on GPU and routed experts on CPU, then coordinates CPU/GPU execution. The evaluated MoE models still keep routed experts in CPU memory; this is expert offload to DRAM plus optimized CPU kernels, not on-demand UFS streaming.

- KTransformers paper: https://madsys.cs.tsinghua.edu.cn/publication/ktransformers-unleashing-the-full-potential-of-cpu/gpu-hybrid-inference-for-moe-models/SOSP25-chen.pdf
- KTransformers site: https://www.ktransformers.net/

**llama.cpp/GGUF reality:** llama.cpp supports GGUF quantization, mmap loading, `--mlock`, and MoE CPU placement. Its server docs describe `--mmap` as enabled by default, `--mlock` as forcing the system to keep the model in RAM, and `--cpu-moe` as keeping MoE weights on CPU. mmap reduces load-time copying and lets the OS page cache back the file, but without mlock the model can fault from storage under pressure. That is a useful probe, not proof that UFS is fast enough.

- llama.cpp README: https://github.com/ggml-org/llama.cpp
- llama.cpp server options: https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- llama.cpp mmap implementation: https://github.com/ggml-org/llama.cpp/blob/master/src/llama-mmap.cpp
- llama.cpp quantize docs: https://github.com/ggml-org/llama.cpp/blob/master/tools/quantize/README.md

**Android/QNN reality:** Qualcomm AI Hub says BYOM compilation may fail when a model is large, including models over 2GB. It also says NPU paths are fastest but most limited, and unsupported ops/ranks fall back to GPU/CPU or can make the whole network fall off the NPU. ExecuTorch's Qualcomm backend delegates supported subgraphs to Hexagon through QNN, uses a partitioner, and lists quantization schemes such as 8a8w, 16a8w, and 16a4w. This is an inference/compiled-subgraph path, not a general autograd training target for a dynamic MoE.

- Qualcomm AI Hub FAQ: https://workbench.aihub.qualcomm.com/docs/hub/faq.html
- Qualcomm Chat Android / Genie app: https://aihub.qualcomm.com/apps/chatapp_android
- ONNX Runtime QNN EP: https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html
- ExecuTorch Qualcomm backend: https://docs.pytorch.org/executorch/stable/backends-qualcomm.html
- ExecuTorch Android Qualcomm guide: https://docs.pytorch.org/executorch/stable/android-qualcomm.html

## What Quantization Changes

Quantization changes **weight bytes and memory bandwidth**, not the model's routing semantics.

Approximate weight residency:

| Format | Qwen3.6-35B-A3B implication |
|---|---|
| BF16 | Raw 35B weights imply about 70GB before overhead; vLLM recipe lists about 84GB. |
| FP8 | vLLM recipe lists about 42GB. Still outside 24GB. |
| INT4/GGUF Q4-class | Roughly 18GB-22GB depending tensor mix and metadata; vLLM lists Qwen3.5-35B-A3B INT4 at 21GB, so Qwen3.6 should be in the same danger zone. |
| IQ2/Q2-class | May fit more comfortably, but quality and tool reliability become the authority gate, not just launch success. |

Quantization does **not** eliminate:

- KV cache or recurrent state cache.
- Runtime scratch buffers, graph workspaces, repacked weights, tokenizer/vision processor memory, Android process overhead, page cache, and GPU/NPU backend buffers.
- Activations needed for training.
- Optimizer states for trainable weights.
- The need for all potentially routable experts to be in a fast tier or predictively prefetched.

For Qwen3.6, the hybrid architecture reduces full-attention KV pressure versus a pure 40-layer attention stack. Rough order: 10 full-attention layers, 2 KV heads, 256 head dim, FP16 KV gives about 20KB/token, or about 160MB at 8K and 2.5GB at 128K, before other state/cache. Qwen3-30B-A3B is heavier: 48 attention layers, 4 KV heads, 128 head dim gives about 96KB/token, or about 3GB at 32K. These caches are smaller than the weights at short context, but they are not zero and they compete with Android and backend memory.

## Training And Adapter Memory

Full fine-tuning a 35B MoE on a 24GB phone is not a target. A rough Adam-style full-precision training budget is parameter + gradient + two optimizer moments. At 35B params, that is hundreds of GB. Even "only 3B active" does not save full fine-tuning unless the trainable set is fixed and small; dynamic routing means different experts are active across data, and optimizer state is required for every trainable parameter, not just the current token's parameters.

LoRA/QLoRA is the only plausible adaptation lane:

- The base model stays frozen and usually quantized.
- Gradients flow through the frozen base into low-rank adapters.
- RAM still needs the frozen base, selected adapter weights, adapter gradients, optimizer state for adapters, activations at adapter insertion points, and runtime workspaces.
- If adapters are attached to all experts, the adapter bank scales with expert count even if each token uses only a subset.
- If adapters are attached only to a static expert subset, the model has been constrained. That is acceptable only if the validation gate proves no authority regression.
- Training actual expert weights is much heavier than LoRA because inference quantized weights are not normally updated in place; practical training wants dequantized or master trainable weights plus gradients and optimizer states.

QLoRA's primary claim is exactly this frozen-base pattern: 4-bit quantized pretrained model, gradients through it, train low-rank adapters. LoRA reduces trainable parameters greatly, but parameter efficiency is not identical to device memory efficiency because intermediate activations still scale with sequence length.

- LoRA paper: https://arxiv.org/abs/2106.09685
- QLoRA paper: https://arxiv.org/abs/2305.14314
- Hugging Face QLoRA summary: https://huggingface.co/papers/2305.14314
- bitsandbytes optimizer docs: https://huggingface.co/docs/bitsandbytes/v0.45.4/en/explanations/optimizers
- On-device PEFT memory warning: https://arxiv.org/abs/2604.22783
- vLLM LoRA serving docs: https://docs.vllm.ai/en/latest/features/lora.html

## Cold Experts On UFS

Cold experts can live on UFS as files. That does not mean they can be missing from RAM during interactive decode.

UFS is good storage. It is still orders of magnitude worse than LPDDR for random fault latency and shared-memory bandwidth. MoE decode is especially hostile because each token can activate small expert slices across many layers. Storage-backed misses create tail latency, heat, and scheduler variance. Android also treats page cache as reclaimable; under memory pressure, model pages can be evicted, and the low-memory killer can terminate the process instead of letting a research runtime limp along.

Therefore:

- **Mmap-only launch success is a demo signal.**
- **Mlock or stable page-cache residency plus low major-fault rate is the real signal.**
- **Per-token UFS expert streaming is not viable unless measured p95 token latency and storage-read counters prove otherwise under memory pressure.**

## Android-Specific Constraints

24GB physical RAM is not 24GB available to the model. Android, graphics, modem/system services, zram, page cache, app process limits, GPU/NPU buffers, and thermal policy all share the same budget. Unified memory avoids discrete PCIe copies, but it does not remove layout conversions, backend buffers, synchronization, QNN context memory, or GPU driver allocation.

The NPU path is especially constrained:

- QNN/LiteRT/ExecuTorch are compiled or partitioned inference paths.
- Unsupported ops or ranks cause fallback.
- Dynamic token-level routing, gather/scatter, expert dispatch, and hybrid DeltaNet kernels are much riskier than dense transformer blocks.
- LoRA can be served by some runtimes, but phone-side adapter training is still a GPU/CPU/autograd problem unless proven otherwise.

## Falsifying Memory Experiment

This is the experiment that should decide whether Qwen3.6 is a first target or a north star.

**Model:** Qwen3.6-35B-A3B text-only GGUF, Q4-class or better quality quant. Also test one smaller IQ/Q3 quant only as a stress reference, not as the authority pass.

**Runtime:** Android native llama.cpp first, with CPU NEON and Adreno OpenCL/Vulkan if available. QNN/LiteRT can be a second path only if backend placement is proven by profiler/logs. KTransformers is relevant if an Android build exists, but do not substitute workstation numbers.

**Runs:**

1. `mmap` run: memory-mapped model, no mlock.
2. resident run: `mmap + mlock`, or `no-mmap` if enough RAM exists.
3. pressure run: repeat mmap while another process consumes enough RAM to force page-cache pressure.
4. MoE placement run: CPU MoE/expert placement enabled where supported; GPU only for non-expert/shared paths if stable.

**Measure:**

- `PSS/RSS` from `/proc/$PID/smaps_rollup`.
- major/minor page faults from `/proc/$PID/stat` and `/proc/vmstat`.
- storage reads during decode from block stats or Android perfetto/simpleperf.
- `logcat` LMKD kills/warnings.
- prompt processing `pp512` and decode `tg128` via `llama-bench`, then a 30-minute real decode loop.
- token latency p50/p95/p99, not just average tok/s.
- temperature and throttle state.
- output sanity on fixed prompts versus a host reference quant.

**Inference pass gate that falsifies "north star only":**

- Q4-class or better quant loads with peak PSS <= 20GB.
- 8K context, batch 1, no LMK, no swap storm.
- After warm-up, major faults < 0.1/sec and storage reads < 10MB/min during decode.
- Sustained 30-minute decode >= 5 tok/s with p95 inter-token latency <= 400ms and <20% thermal drift.
- Quality is not visibly broken on fixed reasoning/code prompts versus the same quant on a host.

**Cold-UFS viability gate:**

- Under the pressure run, p95 token latency remains within 2x of the resident run, major faults stay <0.01/token, and no repeated UFS read bursts appear during decode.
- If this fails, cold experts on UFS are not a viable hot-path strategy.

**Adapter-training pass gate:**

- Frozen 4-bit base, static LoRA rank 8 on a deliberately small surface first: router, output/head, shared expert, or a fixed expert subset.
- Sequence 512, batch 1, gradient checkpointing allowed.
- Peak PSS <= 22GB, no major-fault growth after warm-up, 100 consecutive optimizer steps without LMK/thermal collapse.
- Held-out loss decreases and a retention prompt set does not regress. A falling train loss alone is not a pass.

If all three gates pass, Qwen3.6 becomes a legitimate first target. If any gate fails, the correct conclusion is not "try harder with narrative"; it is that 24GB Android should start with dense 3B-4B or smaller-total MoE and keep Qwen3.6 as the north-star residency/offload benchmark.
