# Orchestrator Handover — Gemma 4 E4B Phone Gate

Status: **authority gate passed**

The current governing objective was the E4B layer 0 forward gate from
`docs/PRD-gemma4-e4b-megakernel-forward-gate.md`: real pretrained
`google/gemma-4-E4B`, revision `7aa32e6889efd6300124851b164f8b364314c3d8`,
text decoder layer 0, forward-only, on REDMAGIC NX789J / SM8750 Adreno through
OpenCL or Vulkan, compared against RunPod PyTorch reference with FP64 cosine per
non-pad token and `p50 >= 0.99`.

## Result

- Backend: OpenCL.
- Device: `nubia NX789J SM8750 FY25013101C8`.
- Compared non-pad tokens: `111`.
- Failed tokens below `0.99`: `0`.
- p50 cosine: `0.9999890020383452`.
- min cosine: `0.9999801999737985`.
- Phone output sha256:
  `cef523f674cff7ecd01cb59040048f9188f80bcb58b9fc47f1fa7f370ce332cf`.
- First passing phone elapsed time: `5.750567` seconds.
- Repeat run output was byte-identical; repeat elapsed time: `5.658739` seconds.

Primary report:

- `gemma4_megakernel/docs/gate_reports/20260516_e4b_layer0_gate_execution.md`
- `docs/orchestrator_brief_completion_crosswalk.md`

## Inspection Entry Points

- PRD: `docs/PRD-gemma4-e4b-megakernel-forward-gate.md`
- Latest summary: `docs/overnight_summary.md`
- Native lane README: `gemma4_megakernel/README.md`
- Runner CLI: `gemma4_megakernel/src/runner/main.cpp`
- OpenCL layer implementation:
  `gemma4_megakernel/src/backends/opencl_layer_runner.cpp`
- OpenCL public entrypoint:
  `gemma4_megakernel/include/polymath/gemma4/opencl_layer_runner.h`
- Phone execution script:
  `gemma4_megakernel/android/adb/run_opencl_gate.sh`
- Strict comparator:
  `gemma4_megakernel/tools/compare_outputs/compare_outputs.py`
- Reference generator:
  `gemma4_megakernel/tools/reference/create_e4b_layer0_reference.py`

## External Artifacts

RunPod:

- Layer pack:
  `/workspace/artifacts/polymath_gemma4/layer_pack/gemma4_e4b_layer0_seq128_v0`
- Passing phone output packet:
  `/workspace/artifacts/polymath_gemma4/phone_outputs/opencl_20260516T222643Z`

Phone:

- Runner:
  `/data/local/tmp/polymath_gemma4_gate/gemma4_layer_runner`
- Layer pack:
  `/data/local/tmp/polymath_gemma4_gate/layer_pack/gemma4_e4b_layer0_seq128_v0`
- Output:
  `/data/local/tmp/polymath_gemma4_gate/outputs_opencl`

Mac:

- Pulled gate artifacts:
  `runtime/gemma4_megakernel/opencl_20260516T222643Z`
- Repeat-run artifacts:
  `runtime/gemma4_megakernel/opencl_20260516T223001Z`

## Non-Claims

This is not yet a fused megakernel, not Vulkan parity, not training, not a
backward pass, not NPU/QAIRT proof, and not a sustained thermal result. It is
the first real model-specific phone forward gate.

## Next Work

1. Preserve this pass as a regression gate.
2. Add optional intermediate tensor dumps for substage bisection.
3. Run sustained repeats with battery, thermal, and KGSL telemetry.
4. Refactor the OpenCL runner into smaller executor components without changing
   tensor semantics.
5. Add Vulkan parity or OpenCL fusion only if the authority metric remains
   green.
