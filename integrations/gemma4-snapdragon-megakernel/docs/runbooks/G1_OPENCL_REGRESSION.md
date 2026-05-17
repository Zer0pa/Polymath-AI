# G1 OpenCL Regression Runbook

Purpose: rerun or audit the passed Gemma 4 E4B layer 0 OpenCL phone gate without
promoting it beyond its scope.

## Authority

- Model: `google/gemma-4-E4B`
- Revision: `7aa32e6889efd6300124851b164f8b364314c3d8`
- Layer: text decoder layer `0`
- Device: REDMAGIC `NX789J / SM8750`
- Serial: `FY25013101C8`
- Backend: OpenCL
- Expected output hash:
  `cef523f674cff7ecd01cb59040048f9188f80bcb58b9fc47f1fa7f370ce332cf`
- Gate report:
  `runtime/reports/gemma4_megakernel/parity/20260516_e4b_layer0_opencl_gate/gate_result.json`

## Phone Replay

Use a fresh output directory and do not overwrite the passed output packet.

```bash
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)_g1_replay"
adb -s FY25013101C8 shell "
  cd /data/local/tmp/polymath_gemma4_gate &&
  ./gemma4_layer_runner --probe &&
  ./gemma4_layer_runner --validate-pack \
    /data/local/tmp/polymath_gemma4_gate/layer_pack/gemma4_e4b_layer0_seq128_v0 &&
  rm -rf outputs_opencl_${RUN_ID} &&
  ./gemma4_layer_runner --run-opencl \
    /data/local/tmp/polymath_gemma4_gate/layer_pack/gemma4_e4b_layer0_seq128_v0 \
    /data/local/tmp/polymath_gemma4_gate/outputs_opencl_${RUN_ID} &&
  sha256sum \
    /data/local/tmp/polymath_gemma4_gate/outputs_opencl_${RUN_ID}/layer_output.f32.bin &&
  cat /data/local/tmp/polymath_gemma4_gate/outputs_opencl_${RUN_ID}/telemetry.json
"
```

Pass condition for replay against the existing G1 pack:

- output hash matches
  `cef523f674cff7ecd01cb59040048f9188f80bcb58b9fc47f1fa7f370ce332cf`;
- telemetry reports OpenCL execution;
- no phone output binary is committed.

## RunPod Oracle Anchor

```bash
ssh root@38.80.152.147 -p 31002 -i ~/.ssh/id_ed25519 '
  test -f /workspace/artifacts/polymath_gemma4/layer_pack/gemma4_e4b_layer0_seq128_v0/reference/layer_output.f32.bin &&
  test -f /workspace/artifacts/polymath_gemma4/phone_outputs/opencl_20260516T222643Z/gate_report.json
'
```

The strict comparator remains:

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

## Non-Claims

This runbook does not claim fused megakernel, Vulkan parity, backward pass,
optimizer update, training, NPU/QAIRT proof, sustained thermal stability, or
phone-native HF streaming/tokenization/packing.
