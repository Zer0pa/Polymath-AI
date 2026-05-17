---
plan_id: 10-01
phase: 10
status: complete
completed: 2026-05-17
---

# Summary: Phase 10 Projected PLE Cache

## Result

Passed. The first hardware-guided Phase 10 candidate was accepted because it
improved the measured phone training path and preserved every authority check.

Baseline gate:
`runtime/reports/gemma4_megakernel/hardware_max/20260517T083219Z_phase10_hf_auth_token_bridge_baseline/gate_result.json`

Optimized gate:
`runtime/reports/gemma4_megakernel/hardware_max/20260517T084203Z_phase10_projected_ple_cache/gate_result.json`

## Decisive Evidence

- Baseline HF-authenticated phone run passed token cache, token-to-hidden,
  layer0, layer1, and adapter update parity.
- Phone telemetry ranked the bottleneck: token-to-hidden took `4.232976s`,
  with PLE projection taking `2.104211s` for layer0 and `2.105825s` for layer1.
- The same cache had `796` active tokens and `285` unique token IDs.
- Projected PLE rows are token-ID-determined in the current bridge, so repeated
  token IDs can reuse the same projected row without changing semantics.
- Optimized token-to-hidden time was `0.667287s`, a `6.343561316195281x`
  speedup and `84.23598432875594%` reduction.
- Optimized token cache, bridge tensors, layer0/layer1 outputs, adapter
  gradients, and updated checkpoint all remained status `pass`.
- Raw tensor binaries and selected text stayed out of the repository; command
  logs are sanitized and contain no HF token.

## Accepted Change

Integrated in
`integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/src/backends/opencl_layer_runner.cpp`:

- token bridge split telemetry;
- unique/active token counting;
- projected PLE row cache keyed by token ID;
- unchanged RunPod oracle and phone authority comparison gates.

## Non-Claims

This does not prove full Gemma4 training, Hexagon NPU training, a six-hour
endurance run, public benchmark readiness, or theoretical maximum reached. It
promotes one narrow optimization in the current REDMAGIC rank-4 two-layer
distillation training path.

## Next Candidates

- Move remaining token bridge work to OpenCL/Vulkan after exact bridge parity.
- Add thermal headroom telemetry and cadence control before longer chains.
- Profile layer kernels with Snapdragon Profiler or equivalent device-side
  instrumentation.
- Evaluate QNN/ExecuTorch/AI Engine Direct only as equal-correctness islands,
  not as a replacement for phone authority runs.
