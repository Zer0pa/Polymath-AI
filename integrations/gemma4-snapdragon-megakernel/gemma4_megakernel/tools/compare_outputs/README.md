# Gemma 4 Gate Output Comparator

`compare_outputs.py` is the strict gate-auditor comparator for the Gemma 4 E4B
layer-0 forward gate. It compares raw phone output against the RunPod PyTorch
reference with FP64 cosine per non-pad token and emits a JSON report.

The pass rule is fixed:

```text
np.percentile(cosines, 50, method="linear") >= 0.99
```

The tool also fails the report when the model id, frozen revision, layer index,
backend, REDMAGIC device identity, dtype path, commands, shape, or compared
token finiteness checks do not satisfy the PRD contract. It does not lower the
`p50 >= 0.99` gate.

## Example

```bash
python3.11 gemma4_megakernel/tools/compare_outputs/compare_outputs.py \
  --reference-output layer_pack/gemma4_e4b_layer0_seq128_v0/reference/layer_output.f32.bin \
  --phone-output runtime/gemma4_megakernel/phone/layer_output.f32.bin \
  --attention-mask layer_pack/gemma4_e4b_layer0_seq128_v0/input/attention_mask.u8.bin \
  --shape 8,1,128,2560 \
  --manifest layer_pack/gemma4_e4b_layer0_seq128_v0/manifest.json \
  --contract layer_pack/gemma4_e4b_layer0_seq128_v0/contract.json \
  --phone-telemetry runtime/gemma4_megakernel/phone/telemetry.json \
  --backend vulkan \
  --device-identity "nubia NX789J SM8750 FY25013101C8" \
  --input-dtype f32 \
  --weight-dtype f16 \
  --accumulation-dtype f32 \
  --phone-command "adb shell /data/local/tmp/polymath_gemma4_gate/gemma4_layer_runner --pack /data/local/tmp/polymath_gemma4_gate/layer_pack --backend vulkan --dump-output /data/local/tmp/polymath_gemma4_gate/layer_output.f32.bin" \
  --reference-command "uv run python tools/extract_layer_pack/reference_layer0.py --pack layer_pack/gemma4_e4b_layer0_seq128_v0" \
  --report-json reports/gemma4_e4b_layer0_phone_parity.json
```

Use the same command shape for intermediate tensors by changing `--tensor-name`,
`--shape`, and the two tensor paths. Intermediate reports are diagnostic only;
the layer-output report remains the authority gate.
