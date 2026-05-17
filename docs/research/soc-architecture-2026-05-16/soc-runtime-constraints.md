# SoC Runtime Constraints For Adaptation Architectures

**Date:** 2026-05-16  
**Role:** Research Agent C  
**Scope:** Snapdragon 8 Elite / SM8750-class Android phone with Oryon CPU, Adreno GPU, Hexagon NPU, unified memory, active cooling.  
**Question:** which model/adaptation shapes exploit heterogeneous SoC physics instead of producing a phone demo?

## Verdict

The best first architecture is a **regular dense transformer with static sequence buckets, low-bit weights, frozen NPU-forward islands, and small trainable adapter/head/norm surfaces on Adreno/CPU**.

Do **not** start with dynamic MoE, nested routing, full fine-tuning, or SSM-heavy custom blocks. They may be interesting later, but they obscure the real bottleneck because current Qualcomm/Android NPU paths are built around **compiled, fixed-shape, quantized inference graphs**. Dynamic control, unsupported ops, layout churn, and graph boundary copies will dominate before raw TOPS matters.

The SoC wants this loop:

```text
CPU scheduler / thermal controller
  -> fixed-shape quantized dense block(s) on Hexagon NPU
  -> trainable LoRA/adapter/head/norm sidecar on Adreno GPU or CPU
  -> sparse/local backward or forward-only update on sidecar
  -> NPU graph reused, not recompiled
```

## Runtime Evidence

| Runtime path | What it proves | Architecture implication |
|---|---|---|
| Qualcomm AI Engine Direct / QNN | QNN is a low-level hardware abstraction over CPU/GPU/HTP, but parsing and partitioning are left to higher frameworks. | Design for explicit partitioning. NPU is a dense compiled island, not an autograd device. |
| Qualcomm Genie / AI Hub ChatApp | Genie runs LLMs through QAIRT/QNN context binaries on Snapdragon NPU; setup is version- and Android-meta-build-sensitive. | Treat NPU LLM execution as a compiled artifact pipeline. Prebuild contexts, pin QAIRT version, avoid per-step graph changes. |
| ONNX Runtime QNN EP | Supports HTP backend, QNN context binary caching, profiling, shared memory allocator, mixed precision, and LoRAv2 inference via precompiled EPContext. | Use QDQ/static quantized models and cache contexts. LoRA can be an inference-time adapter artifact, but phone-side training still belongs outside the NPU graph. |
| ExecuTorch QNN backend | Partitions supported subgraphs with `QnnOperatorSupport`; SM8750 is listed; quant schemes include `8a8w`, `16a16w`, `16a8w`, `16a4w`, `16a4w_block`. | Good PyTorch-to-QNN route for supported ops. Unsupported ops fragment the graph, so architecture should stay boring: matmul/linear, RMSNorm/layer norm, softmax, elementwise, reshape/gather only when proven. |
| LiteRT Qualcomm QNN Accelerator | Google reports broad LiteRT op delegation, AOT or on-device compilation, partial CPU/GPU fallback, and special transformer kernels. AOT is recommended for large models because on-device compilation can cost init time and peak memory. | Strong production-ish Android path for inference. For research, force visibility into fallback and graph boundaries so "fallback succeeded" is not mistaken for NPU success. |
| MediaPipe LLM Inference | Deprecated in favor of LiteRT-LM, still useful. LoRA support is attention-layer-only and GPU-only in this API. | Confirms adapter inference is practical, but not a Hexagon-training story. Use it as a GPU adapter baseline, not the authority path. |
| llama.cpp Snapdragon backend | Current Snapdragon docs expose CPU, Adreno OpenCL, and experimental Hexagon HTP devices. Example output shows large HTP repack buffers and graph reuse. | Excellent physical probe: compare CPU/OpenCL/HTP on same GGUF shapes, but do not assume Hexagon backend maturity equals QNN/LiteRT production coverage. |
| MLC / MNN mobile GPU paths | MLC compiles Adreno OpenCL kernels; MNN defaults CPU and can build OpenCL. | These are Adreno baselines for flexible kernels and sidecar training/adaptation. They are not primary NPU paths. |

## Concrete Bottlenecks

1. **Operator support and graph fragmentation.** Every unsupported op creates fallback or a graph break. Graph breaks are fatal for small trainable islands if they force CPU/NPU/GPU round trips each token.

2. **Quantization format, not parameter count, controls viability.** Qualcomm's public material emphasizes INT4/INT8 for memory-bound generative models; LiteRT's Qualcomm NPU blog calls out int8 weights + int16 activations for high-speed kernels. Mixed precision helps accuracy but inserts Q/DQ boundaries when precision changes.

3. **Dynamic shapes are expensive.** NPU runtimes prefer static compile targets and context binaries. Variable sequence lengths should be bucketed, not freely dynamic. Prefill and decode should be separate compiled shapes.

4. **Routing is not free.** Token-level routers require softmax/top-k, gather/scatter, expert dispatch, and many smaller matmuls. On this SoC, that is likely memory/sync-bound and fallback-prone unless the routing decision is made outside the compiled graph and maps to a preselected static expert/faculty.

5. **Unified memory does not eliminate copies.** CPU, Adreno, and Hexagon share DRAM, but runtimes still allocate backend-specific buffers, repack weights, transform layouts, maintain caches, and synchronize through drivers/FastRPC/QNN sessions. The real metric is bytes moved per useful update.

6. **KV cache and activations fight the same DRAM.** Long-context inference, activation storage, optimizer state, and adapter training all consume the same memory bandwidth and thermal budget. Full backprop through a 3B-4B model is the wrong first target.

7. **Graph compilation/finalization is part of runtime cost.** ORT QNN context binaries and LiteRT AOT exist because compilation and finalization can be large. Any method that mutates the NPU graph every step is structurally wrong for this substrate.

8. **Thermal state is an algorithm variable.** NPU likely wins perf/W for supported inference; Adreno wins flexibility but competes for thermal headroom. Fan/fridge/bypass charging help only if sustained throughput and correctness are measured after warm-up, not just at burst.

## Architecture Shape Assessment

| Shape | Fit | Reason |
|---|---:|---|
| Dense decoder transformer, GQA, regular block stack | Strong | Maps to compiled matmul-heavy NPU islands, stable quantization, and predictable sequence buckets. Best first substrate. |
| Frozen base + LoRA/adapters/head/norm training | Strong | Keeps NPU graph static while adaptation happens on GPU/CPU. Minimizes optimizer state and activation storage. |
| Faculty/domain adapters selected by CPU scheduler | Strong if static | Good if the scheduler chooses one adapter/expert before invocation. Bad if token-level dynamic routing fragments the graph. |
| MoE with dynamic top-k routing | Weak first target | Router/top-k/gather/scatter plus many small expert matmuls will punish memory, copy/sync, and operator coverage. Use only as static expert-bank/faculty routing initially. |
| Nested/recursive/dynamic-depth models | Weak | Control flow and variable shape create compile variants or fallback. Avoid until static dense baseline is falsified or bounded. |
| SSM/Mamba-style blocks | Medium-to-weak first target | Attractive for KV-cache reduction, but custom scan/state kernels are less obviously covered by QNN/LiteRT than transformer blocks. Try on Adreno after dense baseline, then only NPU if operator lowering is proven. |
| Full fine-tuning | Bad first target | Backward activations and optimizer state swamp memory/thermal budget; NPU stack is inference-oriented. |
| Zeroth-order / forward-only adapter updates | Worth second wave | Could exploit cheap repeated forward if NPU forward is truly cheap, but only after graph reuse and copy overhead are measured. |

## What To Test First

Run a **fixed-shape dense-block physical bottleneck probe** before any architecture invention.

Test matrix:

1. Real pretrained transformer block or 4-block strip, not random weights.
2. Shapes: `batch=1, seq=1` decode; `batch=1, seq=128`; `batch=1, seq=512`.
3. Backends: CPU, Adreno OpenCL/Vulkan path, Hexagon via QNN/ORT or LiteRT/Genie, plus llama.cpp Snapdragon if available.
4. Quantization: at least `w4/a16` or `w8/a16`; include one higher-precision control if the runtime allows.
5. Boundaries: one large NPU island, then 2/4/8 islands with identical math to expose sync/copy overhead.
6. Sidecar: attach a tiny LoRA/head adapter on Adreno/CPU and measure the extra crossing cost.

Gate:

- cosine/MSE against host reference for the compiled island;
- proof of backend placement, no silent CPU fallback;
- QNN/LiteRT/llama.cpp profiling output;
- context compile time vs steady-state run time;
- resident memory, backend buffer/repack size, and KV/cache bytes;
- sustained 20-60 minute thermal drift under fan/bypass/fridge settings;
- tokens/sec or examples/sec per degree/watt-hour proxy, not burst latency.

Interpretation:

- If boundary count kills throughput, the architecture must use larger NPU islands and fewer adapter crossings.
- If compile/repack dominates, precompile fixed buckets and forbid step-level graph mutation.
- If quant/dequant dominates, keep adapter precision boundaries coarse and avoid mixed precision inside hot loops.
- If Adreno beats NPU for target shapes, use NPU only for larger prefill/frozen trunk and keep decode/adaptation on GPU/CPU.
- If thermal throttling dominates, scheduler policy matters more than model topology.
- If memory bandwidth dominates, shrink KV/activation traffic before chasing more TOPS.

## Engineering Recommendation

Start with **dense Qwen/Gemma/Llama-class blocks plus adapter sidecars**, not MoE or SSM. The first research deliverable should be a profiler-backed placement map:

```text
shape -> backend -> latency -> bytes moved -> compile/repack cost -> temperature drift -> correctness
```

Only after that map exists should Polymath-AI choose a higher-level learning architecture. Otherwise architecture selection will optimize for a narratable model idea instead of the governing physical bottleneck.

## Source URLs

- Qualcomm AI Engine Direct SDK: https://www.qualcomm.com/developer/software/qualcomm-ai-engine-direct-sdk
- Snapdragon 8 Elite product brief: https://docs.qualcomm.com/bundle/publicresource/87-83196-1_REV_C_Snapdragon_8_Elite_Mobile_Platform_Product_Brief.pdf
- Qualcomm heterogeneous/NPU generative AI whitepaper: https://www.qualcomm.com/content/dam/qcomm-martech/dm-assets/documents/Unlocking-on-device-generative-AI-with-an-NPU-and-heterogeneous-computing.pdf
- ONNX Runtime QNN Execution Provider: https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html
- ExecuTorch Qualcomm backend: https://docs.pytorch.org/executorch/stable/backends-qualcomm.html
- ExecuTorch Qualcomm Android/QNN details: https://docs.pytorch.org/executorch/stable/android-qualcomm.html
- Qualcomm AI Hub Android ChatApp / Genie: https://aihub.qualcomm.com/apps/chatapp_android
- Qualcomm AI Hub ChatApp source: https://github.com/qualcomm/ai-hub-apps/tree/v0.29.0/apps/chatapp_android
- Qualcomm AI Hub Llama 3.2 3B QNN/Genie model page: https://aihub.qualcomm.com/mobile/models/llama_v3_2_3b_instruct
- LiteRT GenAI overview: https://ai.google.dev/edge/litert/genai/overview
- Google LiteRT Qualcomm QNN Accelerator blog: https://developers.googleblog.com/unlocking-peak-performance-on-qualcomm-npu-with-litert/
- MediaPipe LLM Inference Android: https://ai.google.dev/edge/mediapipe/solutions/genai/llm_inference/android
- LiteRT-LM repository: https://github.com/google-ai-edge/LiteRT-LM
- llama.cpp Snapdragon backend: https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/snapdragon/README.md
- MLC LLM docs: https://llm.mlc.ai/docs/get_started/introduction.html
- MLC Android GPU deployment note: https://blog.mlc.ai/2023/05/08/bringing-hardware-accelerated-language-models-to-android-devices
- MNN LLM build docs: https://mnn-llm.readthedocs.io/en/latest/compile.html
- llm.npu paper: https://arxiv.org/abs/2407.05858
