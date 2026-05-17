# Phase 08: Sustained Authority Run - Research

**Researched:** 2026-05-17
**Scope:** Convert the repaired G8 one-step phone-native training path into a sustained, falsifiable authority run without changing the governing metric.

## User Constraints

- The top gate is still phone-native evidence, not a throughput story.
- Do not claim sustained authority from a smoke test. The sustained objective must be predeclared before execution.
- Keep G1/G3 as regression gates after sustained training changes.
- Preserve G8's repaired provenance: phone token cache plus immutable Gemma assets only; no host hidden-state fixtures.
- Use Hugging Face credentials only if a gated/private endpoint requires them. Do not print, commit, or copy tokens into artifacts.

## Active Evidence

- G8 passed at `runtime/reports/gemma4_megakernel/integrated_training/20260517T071405Z_g8_streamed_corpus_repaired/gate_result.json`.
- The bridge tensors, layer outputs, adapter gradients, checkpoint update, and G1/G3 regressions all passed falsifiers.
- Runtime memory high-water was `2169344` KB for one 8x128 batch, leaving enough headroom on the phone for repeated adapter-only updates.

## External Research Inputs

- Hugging Face Gemma4 docs define the PLE configuration fields and CausalLM forward/labels contract: https://huggingface.co/docs/transformers/model_doc/gemma4
- Hugging Face Hub environment docs define `HF_TOKEN`, `HF_HOME`, and cache/token handling: https://huggingface.co/docs/huggingface_hub/en/package_reference/environment_variables
- Android NDK thermal docs expose thermal status/headroom APIs; polling headroom is recommended for forecast monitoring: https://developer.android.com/ndk/reference/group/thermal
- Qualcomm AI Engine Direct SDK is a lower-level unified API over Kryo CPU, Adreno GPU, and Hexagon NPU: https://www.qualcomm.com/developer/software/qualcomm-ai-engine-direct-sdk
- ExecuTorch Qualcomm backend documents QNN/AI Engine Direct lowering/deployment and operator support tracking: https://docs.pytorch.org/executorch/stable/backends-qualcomm.html
- IREE Vulkan docs state Android Vulkan deployment requirements and are useful for a later backend comparison: https://iree.dev/guides/deployment-configurations/gpu-vulkan/
- TVM Adreno docs document OpenCL/OpenCLML deployment, texture/layout ideas, and ADB-targeted tuning: https://tvm.apache.org/docs/v0.12.0/how_to/deploy/adreno.html

## Minimum Honest Phase 8 Objective

Use a predeclared three-batch chained training run:

1. Phone downloads or reuses the HF raw corpus file.
2. Phone slices three non-overlapping 8-line raw chunks.
3. Phone tokenizes each chunk with native Gemma BPE into separate UFS caches.
4. Batch 0 starts from the G5/G6 rank-4 adapter checkpoint.
5. Batch N+1 starts from the phone checkpoint emitted by batch N.
6. Every batch writes telemetry, artifact manifest, checkpoint manifest, and replay manifest.
7. RunPod builds a PyTorch oracle for each phone batch using that batch's phone pre-checkpoint.
8. Compare each batch's token cache, layer0/layer1 outputs, adapter gradients, and checkpoint update.
9. Rerun G1/G3 at the end.

This is not a six-hour endurance proof, but it is a valid predeclared sustained objective because it tests checkpoint chaining, repeated corpus slices, thermal/memory continuity, and non-regression. A future long-duration run can scale this same harness.

## Optimization Research Backlog After Phase 8 Pass

- Replace per-token row reads with unique-token gather plus aligned row cache statistics.
- Move token-to-hidden PLE projection from CPU diagnostic bridge to OpenCL/Vulkan kernels after sustained correctness is green.
- Add native thermal status/headroom polling and cadence control before longer objectives.
- Evaluate QNN/ExecuTorch/IREE/TVM/MLC as candidates only after identical correctness gates exist; none can replace the phone authority artifacts.
- Move from two-layer distillation to chunked tied-embedding next-token NLL once vocabulary-chunk memory and log-sum-exp parity are proven.

## Falsifiers

- Any batch consumes host hidden states.
- A later batch does not use the previous phone checkpoint as its pre-checkpoint.
- Token parity fails for any batch.
- Adapter update comparison fails for any batch.
- Frozen hashes mutate.
- Thermal/memory telemetry is absent.
- G1 or G3 regresses after the sustained run.
