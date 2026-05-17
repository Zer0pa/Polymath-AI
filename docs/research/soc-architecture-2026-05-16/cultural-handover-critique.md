# Cultural Handover Critique: Do Not Shrink The SoC Question

Date: 2026-05-16  
Role: fresh-context critique agent  
Scope: critique the orchestrator failure mode and hand over a stance for the next agent. This is not the living dialogue and does not edit it.

## Verdict

The orchestrator's initial failure mode was **objective collapse**: it translated "what learning architecture naturally fits a heterogeneous phone SoC?" into "which model should we rank first?" That is `fp-benchmarkproxy` plus `fp-scopeevaporation`. Model choice matters, but only as a probe of the governing question:

**Can a phone-SoC learning system converge by combining sparse/nested/modular models, active experts, adapters, local or zeroth-order updates, and thermally aware CPU/GPU/NPU scheduling better than a simpler dense baseline under the same authority metric?**

Resistance V2 does **not** say "avoid Qwen3.6-35B-A3B because it is complex." It says the opposite when complexity is architecturally relevant: do not retreat to a dense 4B baseline merely because it is easier to explain, run, or report. But Resistance V2 also does not reward impressive complexity. Qwen3.6 earns a lane only if it produces receipts against the SoC-learning objective.

## Fresh-Agent Stance

Think in two lanes, and do not let either erase the other.

1. **Authority/runtime lane:** dense or regular baselines that expose the real physical bottleneck first: Qwen3-4B, Gemma 4 E2B/E4B, SmolLM3-3B, Qwen2.5-1.5B. This lane proves device attachment, real weights, backend placement, no silent fallback, correctness, memory, thermal drift, and wall-clock-to-quality.
2. **SoC-convergence lane:** sparse/modular/faculty architectures that may actually match the long-run hypothesis: OLMoE-1B-7B, LFM2-8B-A1B, EMO 1B-active/14B-total, Qwen3-30B-A3B, Gemma 4 26B-A4B, Qwen3.6-35B-A3B, Qwen3-Next-80B-A3B.

The dense lane is the ruler. The modular lane is the ambition. Treat a dense 4B pass as a calibration event, not the project.

## Qwen3.6 Position

Do not reject `Qwen/Qwen3.6-35B-A3B` because it is awkward. Its architecture is close to the corrected objective:

- 35B total / 3B active language model.
- Hybrid layout: repeated Gated DeltaNet plus MoE with periodic gated attention.
- 256 experts, 8 routed plus 1 shared active expert.
- Long-context economics that may matter on memory-bound devices.
- Vision encoder and agentic/post-trained surface, which may be either useful later or a distraction now.

The right stance is: **Qwen3.6 is a north-star / hard-branch candidate, not the first proof gate.** It should pressure the architecture design because it combines sparse active experts with linear-attention state. It should not displace first-gate dense/runtime probes until the project has receipts for kernels, quantization, residency, adapter placement, and correctness on RedMagic-class hardware.

If a future agent says "too complex, use dense 4B," require them to state whether they are making a first-gate runtime decision or shrinking the governing architecture. The first is allowed; the second is failure.

## Where To Be Skeptical

- **Active parameters are not resident parameters.** A 3B-active MoE can still require a large quantized/offloaded weight store, expert metadata, router state, vision components, KV or linear-attention state, and runtime buffers.
- **MoE routing is not free on a phone.** Top-k, gather/scatter, small expert matmuls, cache churn, and CPU/GPU/NPU boundary crossings can erase active-parameter wins.
- **Gated DeltaNet may help decode memory but hurt training feasibility.** Long-context inference advantages do not prove backward kernels, LiteRT/QNN lowering, or adapter training support.
- **Vision-language packaging can distort the experiment.** If the immediate question is text learning, skip or strip the vision path only with documented support from the model/runtime.
- **NPU inference is not NPU training.** The Hexagon path remains a frozen-forward island until a backward/update path is proven on-device.
- **Scheduler wins can be fake.** "CPU/GPU/NPU all active" is not success. Success is lower wall-clock or energy-to-authority-quality without regression.
- **Local objectives are dangerous.** Router-only, expert-only, adapter-only, local-loss, synthetic-gradient, and zeroth-order updates must be gated by final quality and forgetting tests.

## What Not To Shrink

- Do not shrink the question to "can a model run on the phone?"
- Do not shrink training to inference plus a tiny toy head.
- Do not shrink the architecture search to dense 4B just because it is the easiest first measurement.
- Do not shrink "heterogeneous" to device-utilization screenshots.
- Do not shrink "faculty" to a metaphor. It must become explicit modules: expert sets, adapters, routers, curricula, replay, and scheduler decisions.
- Do not shrink acceptance to one benchmark. The authority gate is sustained wall-clock/energy-to-quality under memory, thermal, fallback, and regression falsifiers.

## Claims That Require Receipts

Require concrete receipts before accepting any of these claims:

| Claim | Receipt required |
|---|---|
| "Qwen3.6 fits in 24GB" | Quantization format, full resident set, runtime buffers, context state, Android headroom, and measured peak RSS/PSS on device or a defensible physical model. |
| "3B active means phone-feasible" | End-to-end latency/memory profile including router, active experts, inactive expert storage/offload, backend buffers, and thermal drift. |
| "NPU accelerates this architecture" | QNN/LiteRT/ORT/Genie profile showing real HTP/NPU execution, no silent CPU fallback, and correctness versus host reference. |
| "Adapters/local training work" | Same eval gate as dense baseline: validation loss, domain score, forgetting/replay score, and wall-clock/energy-to-target-quality. |
| "DeltaNet is better for phone" | Measured state memory, kernel support, prefill/decode latency, and training/update feasibility for the relevant sequence lengths. |
| "MoE is better than dense" | Equal-budget comparison against dense baseline, including quality, energy, thermal state, memory traffic, and scheduler overhead. |
| "The scheduler improved the system" | A/B against static placement with identical model, data, thermal regime, and correctness gates. |

## 24GB RAM Concern

Conceptually, 24GB is not a single clean VRAM pool. It is shared LPDDR used by Android, CPU, GPU, NPU, drivers, backend-specific heaps, graph contexts, repacked weights, KV or linear-attention state, activations, optimizer state, telemetry, and data buffers.

For Qwen3.6-style MoE, the active 3B parameter count helps compute, but it does not make the 35B total model disappear. The phone may stream, mmap, quantize, offload, or page expert weights, but each strategy has a cost in memory traffic and scheduler stalls. The right question is not "does it fit?" but:

**How many bytes must move per accepted token or learning update, and does that movement still beat the dense baseline at the authority metric?**

Leave detailed RAM arithmetic to the RAM agent. This handover only fixes the conceptual discipline: active parameters reduce per-token compute, not necessarily resident memory, update memory, or SoC traffic.

## Reading List For The Next Agent

Read local files first:

- `/Users/Zer0pa/Polymat AI/Polymath-AI/RESISTANCE-V2.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/docs/HETEROGENEOUS-SOC-RESEARCH-DIALOGUE.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/docs/research/soc-architecture-2026-05-16/architecture-models.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/docs/research/soc-architecture-2026-05-16/training-systems.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/docs/research/soc-architecture-2026-05-16/soc-runtime-constraints.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/source-briefs/01-on-device-training-blueprint.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/synthesis/01-fresh-eyes-on-polymath-blueprint.md`

Then read external anchors:

- Qwen3.6-35B-A3B model card: https://huggingface.co/Qwen/Qwen3.6-35B-A3B
- Qwen model evolution and Qwen3/Qwen3-Next overview: https://qwen.moe/
- Qwen3-30B-A3B model card: https://huggingface.co/Qwen/Qwen3-30B-A3B
- Qwen3-Next-80B-A3B-Instruct model card: https://huggingface.co/Qwen/Qwen3-Next-80B-A3B-Instruct
- EMO paper: https://arxiv.org/abs/2605.06663
- OLMoE model card: https://huggingface.co/allenai/OLMoE-1B-7B-0924
- Liquid LFM2 docs: https://docs.liquid.ai/lfm/models/text-models
- Qualcomm AI Engine Direct SDK: https://www.qualcomm.com/developer/software/qualcomm-ai-engine-direct-sdk
- ExecuTorch Qualcomm backend: https://docs.pytorch.org/executorch/stable/backends-qualcomm.html
- ONNX Runtime QNN Execution Provider: https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html
- LiteRT Qualcomm QNN Accelerator: https://developers.googleblog.com/unlocking-peak-performance-on-qualcomm-npu-with-litert/
- LoRA: https://arxiv.org/abs/2106.09685
- MeZO: https://arxiv.org/abs/2305.17333
- MobiZO: https://arxiv.org/abs/2409.15520
- Switch Transformer: https://arxiv.org/abs/2101.03961
- MatFormer: https://arxiv.org/abs/2310.07707

## Handover Rule

The next agent should preserve this sentence as the guardrail:

**Dense baselines are how we measure; modular/sparse/faculty architectures are what we are testing; Qwen3.6 is not disqualified by complexity, but every complexity claim must pay rent in receipts.**
