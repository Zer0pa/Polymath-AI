# Deep Research Brief

## Role

You are a deep research agent supporting a frontier engineering team. You are
not being asked for generic mobile ML advice. You are being asked to investigate
what form of Gemma 4 learning fits Snapdragon SM8750 hardware.

Use current sources. Prefer primary documentation, papers, official SDK docs,
measured reports, and code over blog summaries. Time-sensitive claims must be
verified with current web research.

## Context

The project has built a Gemma-specific native phone runtime and proved:

- E4B layer0 OpenCL forward parity on REDMAGIC.
- E4B layer0+layer1 OpenCL forward parity.
- rank-4 post-layer0 adapter backward against RunPod PyTorch.
- phone-side SGD update with frozen base hashes stable.
- repaired phone-native token-cache to OpenCL adapter update path.
- three-batch chained training.
- six-hour endurance for the current narrow lane.

It has not proved:

- full Gemma4 training;
- Hexagon/NPU training;
- public benchmark readiness;
- theoretical maximum.

## Research Goal

Find the strongest next technical direction for heterogeneous Gemma training on
SM8750.

Do not default to conventional "scale the current code" thinking. Ask what the
hardware wants.

## Research Questions

### Q1 - Hexagon/QAIRT/QNN Training Surface

What, if anything, in current Qualcomm AI Stack / QAIRT / QNN / Genie / HTP
tooling can support training-like updates?

Investigate:

- QNN context binary update mechanisms;
- LoRA adapter binary updater semantics;
- Genie LoRA/adapters;
- support for dynamic weights or mutable adapter state;
- limitations of HTP backends for backward/gradient computation;
- whether HTP can be used for frozen-forward or activation recompute inside a
  training loop;
- relevant SM8750 / Hexagon V79 details.

Deliverable:

- classify HTP as one of:
  - no training role;
  - frozen-forward only;
  - mutable-adapter support but no backward;
  - possible training primitive;
  - unknown due to closed documentation.

### Q2 - Adreno OpenCL/Vulkan Training Kernel Strategy

What is the best direction for Adreno training kernels?

Investigate:

- OpenCL vs Vulkan compute on recent Adreno for long-running kernels;
- launch overhead and fusion strategy;
- memory coalescing and tiling for transformer layers;
- FP32/BF16/FP16 behavior and accumulation risk;
- whether persistent kernels or command-buffer strategies are viable on
  Android/Adreno;
- tools: Android GPU Inspector, Snapdragon Profiler, perfetto, KGSL telemetry.

Deliverable:

- recommend whether to continue OpenCL, branch Vulkan, or run both;
- identify the next fusion target that tests hardware fit, not just speed.

### Q3 - Hardware-Native Trainable Scope

What trainable module gives the most capability per phone resource?

Compare:

- post-layer residual adapters;
- LoRA on attention projections;
- LoRA on MLP projections;
- trainable layer norms;
- last-layer or early-layer selective updates;
- prefix/prompt/key-value memory modules;
- sparse routing/control-state modules.

Deliverable:

- ranked trainable scopes for SM8750, with memory, gradient, and kernel
  implications.

### Q4 - Learning Objective And Data Regime

What data and objective shape fits the phone?

Investigate:

- dense high-signal small corpora;
- repeated settling passes;
- online replay;
- teacher-distilled targets;
- contrastive or reconstruction objectives;
- whether next-token loss is the right first objective for this hardware;
- information density per joule / per byte / per update.

Deliverable:

- recommend first capability-moving objective beyond parity/update correctness.

### Q5 - Systems Bottleneck Diagnosis

What does the six-hour result imply?

Given:

- wall-clock about 6 hours;
- active training about 1.29 hours;
- 465 chained iterations;
- thermal status stayed low;
- sampled parity stayed green.

Investigate:

- likely bottleneck classes;
- instrumentation needed to separate compute, launch, I/O, validation,
  checkpointing, and orchestration overhead;
- whether thermal headroom means we are underutilizing the hardware.

Deliverable:

- diagnostic plan to identify the limiting resource.

### Q6 - Full Gemma4 Training Definition

What should "full Gemma4 training on phone" mean for this project?

Avoid cloud-GPU definitions by default. Propose a frontier but measurable
definition grounded in:

- useful update;
- trainable scope;
- runtime independence;
- checkpoint validity;
- measurable loss/capability movement;
- hardware-native decomposition.

Deliverable:

- a revised authority metric that is ambitious but not a proxy.

## Required Output

Produce a research memo with:

1. executive recommendation;
2. hardware-role map;
3. current tooling capability table;
4. strongest next experiment;
5. top five risks;
6. sources with links;
7. assumptions and unknowns;
8. what would falsify the recommendation.

Do not write a generic literature review. Write an engineering science decision
memo.
