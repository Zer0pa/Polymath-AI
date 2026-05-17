# Gemma 4 E4B Mega Kernel Gate Lane

This lane implements the native substrate for the current authority gate:
one real-pretrained Gemma 4 E4B text decoder layer, forward-only, executing
on REDMAGIC SM8750 Adreno through Vulkan or OpenCL and compared against a
RunPod PyTorch reference with p50 per-token cosine similarity >= 0.99.

The current runner is intentionally narrow, but it now executes the authority
layer gate through OpenCL:

- C++17/NDK command-line binary.
- `--probe` reports runtime and GPU library capability without touching data.
- `--validate-pack` validates the `layer_bundle_v1` contract before math runs.
- `--run-opencl PACK_DIR OUT_DIR` executes Gemma 4 E4B text decoder layer 0
  forward-only on the phone OpenCL GPU path and emits `layer_output.f32.bin`
  plus telemetry.

See `docs/PRD-gemma4-e4b-megakernel-forward-gate.md` for the governing PRD.
See `gemma4_megakernel/docs/gate_reports/20260516_e4b_layer0_gate_execution.md`
for the first passing REDMAGIC OpenCL gate result.

## Host build

```bash
cmake -S gemma4_megakernel -B build/gemma4_megakernel
cmake --build build/gemma4_megakernel
ctest --test-dir build/gemma4_megakernel --output-on-failure
```

## Android build

```bash
ANDROID_NDK_HOME=/path/to/android-ndk-r28b \
  gemma4_megakernel/android/cmake/build_android.sh
```

## Phone probe

```bash
gemma4_megakernel/android/adb/probe_phone_gate.sh
gemma4_megakernel/android/adb/deploy_and_probe.sh build/gemma4_megakernel_android/gemma4_layer_runner
```

## Phone OpenCL layer run

The layer pack must already exist on the phone at
`/data/local/tmp/polymath_gemma4_gate/layer_pack/gemma4_e4b_layer0_seq128_v0`.

```bash
gemma4_megakernel/android/adb/run_opencl_gate.sh \
  build/gemma4_megakernel_android/gemma4_layer_runner
```
