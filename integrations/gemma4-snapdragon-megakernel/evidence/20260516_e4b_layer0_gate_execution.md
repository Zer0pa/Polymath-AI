# Gemma 4 E4B Layer 0 Gate Execution Report

Date: 2026-05-16 UTC / 2026-05-17 Africa/Johannesburg

Status: **PASSED**

The sovereign gate passed on the attached REDMAGIC phone with a real Gemma 4
E4B layer 0 forward pass through the OpenCL path. The run used real pretrained
layer weights, real captured layer inputs, the per-layer input branch, and
RunPod PyTorch reference output for comparison.

## Authority Gate

Pass requires:

- `google/gemma-4-E4B` base revision `7aa32e6889efd6300124851b164f8b364314c3d8`.
- Text decoder layer `0`, forward-only.
- Real pretrained layer weights.
- REDMAGIC `NX789J` / `SM8750` Adreno execution through Vulkan or OpenCL.
- FP64 cosine per non-pad token vs RunPod PyTorch reference.
- `p50 >= 0.99`.

## Gate Result

- Status: `pass`.
- Backend: `opencl`.
- Device identity: `nubia NX789J SM8750 FY25013101C8`.
- Compared tokens: `111` non-pad tokens.
- Failed tokens below `0.99`: `0`.
- FP64 per-token cosine:
  - min: `0.9999801999737985`
  - p10: `0.999983707486152`
  - p50: `0.9999890020383452`
  - p90: `0.9999917046730411`
  - max: `0.9999933292849964`
- Phone OpenCL elapsed time: `5.750567` seconds.
- Phone output sha256: `cef523f674cff7ecd01cb59040048f9188f80bcb58b9fc47f1fa7f370ce332cf`.
- Repeat phone run through `android/adb/run_opencl_gate.sh` produced a
  byte-identical `layer_output.f32.bin`; repeat elapsed time was `5.658739`
  seconds.

## Evidence Locations

RunPod:

- Layer pack:
  - `/workspace/artifacts/polymath_gemma4/layer_pack/gemma4_e4b_layer0_seq128_v0`
- Phone output and gate report:
  - `/workspace/artifacts/polymath_gemma4/phone_outputs/opencl_20260516T222643Z/layer_output.f32.bin`
  - `/workspace/artifacts/polymath_gemma4/phone_outputs/opencl_20260516T222643Z/telemetry.json`
  - `/workspace/artifacts/polymath_gemma4/phone_outputs/opencl_20260516T222643Z/gate_report.json`

Mac:

- Pulled phone output packet:
  - `runtime/gemma4_megakernel/opencl_20260516T222643Z/layer_output.f32.bin`
  - `runtime/gemma4_megakernel/opencl_20260516T222643Z/telemetry.json`
  - `runtime/gemma4_megakernel/opencl_20260516T222643Z/gate_report.json`

Phone:

- Runner:
  - `/data/local/tmp/polymath_gemma4_gate/gemma4_layer_runner`
- Layer pack:
  - `/data/local/tmp/polymath_gemma4_gate/layer_pack/gemma4_e4b_layer0_seq128_v0`
- Output directory:
  - `/data/local/tmp/polymath_gemma4_gate/outputs_opencl`

## Commands

Reference and layer pack were produced on RunPod from the pinned model
revision. The successful phone run used:

```bash
adb -s FY25013101C8 shell \
  'cd /data/local/tmp/polymath_gemma4_gate && \
   ./gemma4_layer_runner --run-opencl \
   /data/local/tmp/polymath_gemma4_gate/layer_pack/gemma4_e4b_layer0_seq128_v0 \
   /data/local/tmp/polymath_gemma4_gate/outputs_opencl'
```

The comparison was run on RunPod:

```bash
python gemma4_megakernel/tools/compare_outputs/compare_outputs.py \
  --reference-output /workspace/artifacts/polymath_gemma4/layer_pack/gemma4_e4b_layer0_seq128_v0/reference/layer_output.f32.bin \
  --phone-output /workspace/artifacts/polymath_gemma4/phone_outputs/opencl_20260516T222643Z/layer_output.f32.bin \
  --attention-mask /workspace/artifacts/polymath_gemma4/layer_pack/gemma4_e4b_layer0_seq128_v0/input/attention_mask.u8.bin \
  --shape 8,128,2560 \
  --manifest /workspace/artifacts/polymath_gemma4/layer_pack/gemma4_e4b_layer0_seq128_v0/manifest.json \
  --contract /workspace/artifacts/polymath_gemma4/layer_pack/gemma4_e4b_layer0_seq128_v0/contract.json \
  --phone-telemetry /workspace/artifacts/polymath_gemma4/phone_outputs/opencl_20260516T222643Z/telemetry.json \
  --backend opencl \
  --device-identity 'nubia NX789J SM8750 FY25013101C8' \
  --input-dtype f32 \
  --weight-dtype f32 \
  --accumulation-dtype f32 \
  --phone-command 'adb shell /data/local/tmp/polymath_gemma4_gate/gemma4_layer_runner --run-opencl ...' \
  --reference-command 'create_e4b_layer0_reference.py revision 7aa32e6889efd6300124851b164f8b364314c3d8' \
  --report-json /workspace/artifacts/polymath_gemma4/phone_outputs/opencl_20260516T222643Z/gate_report.json
```

## Implementation Notes

The passing path is intentionally direct:

- Dynamic OpenCL loading through `dlopen("libOpenCL.so")`.
- C++17/NDK runner with no Python on phone.
- Safetensors BF16 layer weights parsed on device and converted to FP32.
- GPU buffers for the captured `layer_input`, `per_layer_input`,
  attention mask, position ids, and all layer weights.
- OpenCL kernels for RMSNorm, Q/K/V/O projections, Q/K/V norms, RoPE,
  causal masked attention, GELU-tanh MLP, residuals, per-layer input gate,
  projection, post-per-layer norm, and final layer scalar.
- Output is written as `f32` and audited externally by the strict comparator.

## Tests Run

Mac host:

```bash
cmake -S gemma4_megakernel -B build/gemma4_megakernel
cmake --build build/gemma4_megakernel -j 4
ctest --test-dir build/gemma4_megakernel --output-on-failure
```

Result: `2/2` CTest tests passed.

RunPod Android build:

```bash
ANDROID_NDK_HOME=/workspace/android-ndk-r28b \
  bash gemma4_megakernel/android/cmake/build_android.sh
```

Result: Android arm64 runner built successfully.

Phone:

```bash
/data/local/tmp/polymath_gemma4_gate/gemma4_layer_runner --probe
/data/local/tmp/polymath_gemma4_gate/gemma4_layer_runner --validate-pack \
  /data/local/tmp/polymath_gemma4_gate/layer_pack/gemma4_e4b_layer0_seq128_v0
/data/local/tmp/polymath_gemma4_gate/gemma4_layer_runner --run-opencl \
  /data/local/tmp/polymath_gemma4_gate/layer_pack/gemma4_e4b_layer0_seq128_v0 \
  /data/local/tmp/polymath_gemma4_gate/outputs_opencl
```

Result: OpenCL layer output generated and passed strict comparison.

Repeat run:

```bash
SERIAL=FY25013101C8 bash gemma4_megakernel/android/adb/run_opencl_gate.sh \
  runtime/gemma4_megakernel/android_build_20260516T222626Z/gemma4_layer_runner
cmp -s \
  runtime/gemma4_megakernel/opencl_20260516T222643Z/layer_output.f32.bin \
  runtime/gemma4_megakernel/opencl_20260516T223001Z/layer_output.f32.bin
```

Result: `cmp` exit code `0`.

## Non-Claims

This pass does not claim:

- A fused megakernel.
- Vulkan parity.
- Training or backward pass.
- Thermal stability across sustained runs.
- Quantized or FP16 kernel performance.

The next authority gate should be sustained repeated runs plus intermediate
telemetry, then kernel fusion and Vulkan/OpenCL backend comparison without
relaxing the p50 threshold.
