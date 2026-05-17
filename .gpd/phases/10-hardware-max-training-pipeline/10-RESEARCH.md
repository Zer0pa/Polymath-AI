# Phase 10: Hardware-Max Training Pipeline - Research

**Researched:** 2026-05-17
**Scope:** Convert the post-G10 phone-native training lane into a falsifiable
hardware-max search. The hardware is allowed to nominate bottlenecks, but only
actual REDMAGIC training runs can promote an optimization.

## Governing Rule

Performance is subordinate to authority. A candidate is accepted only when it
improves a measured phone-training bottleneck and all correctness gates remain
green: token cache parity, token-to-hidden parity, layer0/layer1 OpenCL parity,
adapter-gradient/update parity, artifact hygiene, and no hidden host data path.

## Current Phone Evidence

- Phase 9 G10 final falsifier passed:
  `runtime/reports/gemma4_megakernel/falsifiers/20260517T082637Z_g10_final_falsifier_review/gate_result.json`.
- Phase 10 HF-authenticated baseline passed:
  `runtime/reports/gemma4_megakernel/hardware_max/20260517T083219Z_phase10_hf_auth_token_bridge_baseline/gate_result.json`.
- Baseline bottleneck: `token_to_hidden_elapsed_seconds = 4.232976`, of which
  PLE projection consumed `2.104211s + 2.105825s`.
- The baseline token cache had `796` active tokens but only `285` unique token
  IDs, making repeated-token PLE projection the first measurable target.

## External Research Inputs

- Qualcomm AI Engine Direct SDK exposes lower-level access over Kryo CPU,
  Adreno GPU, and Hexagon NPU/QNN backends:
  https://www.qualcomm.com/developer/software/qualcomm-ai-engine-direct-sdk
- ExecuTorch Qualcomm backend delegates computations through Qualcomm AI Engine
  Direct/QNN and is a candidate for later Hexagon/HTP inference islands:
  https://docs.pytorch.org/executorch/stable/backends-qualcomm.html
- Qualcomm AI Hub supports compile/profile workflows and hosted Snapdragon
  device profiling; useful as a comparative oracle, not as a replacement for the
  physical REDMAGIC authority run:
  https://app.aihub.qualcomm.com/docs/hub/
- Qualcomm Snapdragon Profiler can inspect CPU, GPU, DSP, Vulkan, OpenCL, and
  OpenGL ES activity:
  https://www.qualcomm.com/developer/software/snapdragon-profiler
- IREE Vulkan targets Android Vulkan and emits SPIR-V plus runtime scheduling;
  candidate for a later backend A/B once exact correctness parity exists:
  https://iree.dev/guides/deployment-configurations/gpu-vulkan/
- TVM Adreno documentation records OpenCL/OpenCLML deployment, Adreno-friendly
  layouts, texture-memory ideas, and ADB-target tuning:
  https://tvm.apache.org/docs/v0.12.0/how_to/deploy/adreno.html
- MLC LLM documents Android/Vulkan LLM deployment and compilation-oriented
  runtime design:
  https://llm.mlc.ai/docs/get_started/introduction.html
- llama.cpp's Adreno OpenCL backend is a current analogue for hand-tuned
  Snapdragon GPU LLM kernels:
  https://github.com/ggml-org/llama.cpp/blob/master/docs/backend/OPENCL.md
- Android NDK thermal APIs expose thermal status and headroom, including
  `AThermal_getThermalHeadroom`, for later cadence control:
  https://developer.android.com/ndk/reference/group/thermal
- Hugging Face Hub documents `HF_TOKEN`, `HF_HOME`, and token-file behavior; the
  phone fetch path must use tokens without printing or committing them:
  https://huggingface.co/docs/huggingface_hub/en/package_reference/environment_variables
- Hugging Face Datasets streaming remains the host-side analogue for large
  corpus streaming; in this project, the phone-side stream is the authority:
  https://huggingface.co/docs/datasets/en/stream

## Candidate Matrix

| Candidate | Why It Might Matter | First Gate | Status |
| --- | --- | --- | --- |
| Projected PLE row cache by token ID | `layer_input`, PLE identity, and projection output are token-ID-determined in the current bridge; repeated tokens should not redo the same 256x2560 matvec. | Same HF-auth token cache, same checkpoint, actual phone `--run-g8-distill`, parity plus timing. | Accepted in 10-01. |
| Move PLE projection to OpenCL/Vulkan | CPU bridge remains nontrivial after caching. | Kernel output parity for layer0/1 PLE tensors before training A/B. | Deferred. |
| OpenCL layer kernel cadence/fusion | Layer runtime remains larger than the adapter update. | Actual training run and G1/G3 regression floor. | Deferred. |
| QNN/ExecuTorch/AI Engine Direct island | Hexagon/HTP may help frozen-forward or quantized inference islands, but training/backward support is not yet proven. | Equal-correctness frozen island with no CPU fallback. | HTP inference/platform pass in 10-02; training update still blocked. |
| Thermal-aware scheduler/LR cadence | Longer runs require avoiding thermal collapse. | NDK thermal telemetry plus non-regressing chained training. | Six-hour wall-clock endurance passed in 10-02 for current lane; adaptive cadence still deferred. |
| Checkpoint I/O layout | UFS writes may matter in longer chains. | Multi-batch checkpoint timing with hash replay. | Deferred. |

## First Accepted Finding

The first hardware-guided result is not a generic allocator or scheduler rewrite.
The phone telemetry said PLE projection dominated the bridge, and the token cache
showed repeated token IDs. A projected PLE row cache was therefore the first
candidate with a direct authority metric.

Accepted evidence:
`runtime/reports/gemma4_megakernel/hardware_max/20260517T084203Z_phase10_projected_ple_cache/gate_result.json`.

Measured result:
- Token-to-hidden elapsed improved from `4.232976s` to `0.667287s`.
- Speedup: `6.343561316195281x`.
- Reduction: `84.23598432875594%`.
- Token cache, bridge tensors, layer outputs, adapter gradients, and checkpoint
  update all remained status `pass`.

## Second Accepted Finding

The six-hour endurance non-claim is now promoted only for the current rank-4
two-layer phone-native training lane.

Accepted evidence:
`runtime/reports/gemma4_megakernel/hardware_max/20260517T153500Z_phase10_six_hour_endurance/gate_result.json`.

Measured result:
- Wall-clock duration: `21692.164205625013s`.
- Iterations: `465` chained phone training updates.
- Active training time: `4626.6455870000045s`.
- Max Android thermal status: `0`.
- Sampled parity passed for iterations `0`, `240`, and `464`.

## Blocked Non-Claims

The non-claim summary gate remains `fail`:
`runtime/reports/gemma4_megakernel/hardware_max/20260517T214000Z_phase10_nonclaim_gate/gate_result.json`.

The blocked items are full Gemma4 training, Hexagon NPU training, public
benchmark readiness, and theoretical maximum reached. QNN/HTP platform and
inference evidence exists, but no HTP backward/gradient/optimizer update
executed.

## Falsifiers

- Any accepted candidate with a failed parity report.
- Any throughput win that consumes hidden host fixtures or host-served batches.
- Any CPU fallback presented as Adreno, Vulkan, or Hexagon authority.
- Any performance improvement that breaks artifact hygiene or leaks HF tokens.
- Any claim that Phase 10 reaches full Gemma4 training, Hexagon NPU training,
  public benchmark readiness, or theoretical maximum without the corresponding
  gate.
