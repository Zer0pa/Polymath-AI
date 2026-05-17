# Gemma 4 Snapdragon Megakernel Integration Manifest

Date: 2026-05-17
Status: G8_REJECTED_UNDER_FALSIFICATION_AFTER_G4_G7_PASS
Authority PRD: `docs/PRD-GEMMA4-SNAPDRAGON-MEGAKERNEL-HETEROGENEOUS-TRAINING.md`
Upstream lane: `/Users/Zer0pa/Gemma4 Kernel`
Upstream working commit imported: `8a5fb2df0c7e8da52fb0bc346077e63e8c801009`
Passed upstream gate commit: `c5b6e3522d28d0e1dc56084cb97fa9e95e29aa4e`
Polymath branch: `gemma4-megakernel-native-training`

## Purpose

This directory is the only approved landing zone for Gemma4 Kernel material
inside Polymath-AI.

The integration objective is narrow: support heterogeneous compute training on
REDMAGIC 10 Pro / `NX789J` / `SM8750` using a custom Gemma 4 static/megakernel
runtime, while preserving the passed G1 OpenCL layer gate as a regression floor.

## Import Rules

Import only files that serve the PRD authority path:

- static executor schema and examples;
- native kernel lab source needed for RMSNorm/matmul/tiny-block parity;
- OpenCL/Vulkan backend harnesses;
- telemetry schema;
- model spec facts required by memory planning;
- architecture/decision docs that define executor and backend policy;
- text evidence required to preserve G1.

Do not import:

- build outputs;
- `.venv`, `node_modules`, `__pycache__`, caches;
- third-party source clones;
- raw model weights;
- `.tflite`, `.litertlm`, `.task`, `.safetensors`, `.bin`, `.zip`;
- broad research docs that do not affect the Gemma 4 REDMAGIC megakernel lane;
- Qwen/SmolLM artifacts unless a bridge experiment is explicitly approved.

## Imported File Index

Every imported file is listed with byte size and SHA-256 in:

- `IMPORT_FILE_INDEX.tsv`

That index is part of this manifest. It is regenerated after import and before
G2 verification. It intentionally excludes generated caches and build outputs.

## Imported Mapping

| Upstream path | Target path | Status |
| --- | --- | --- |
| `docs/orchestrator_handover_gemma4_e4b_gate.md` | `evidence/orchestrator_handover_gemma4_e4b_gate.md` | IMPORTED |
| `docs/orchestrator_brief_completion_crosswalk.md` | `evidence/orchestrator_brief_completion_crosswalk.md` | IMPORTED |
| `gemma4_megakernel/docs/gate_reports/20260516_e4b_layer0_gate_execution.md` | `evidence/20260516_e4b_layer0_gate_execution.md` | IMPORTED |
| `gemma4_megakernel/` source, headers, tools, adb scripts, CMake | `gemma4_megakernel/` | IMPORTED |
| `executor_ir/schema.json` | `executor_ir/schema.json` | IMPORTED |
| `executor_ir/examples/gemma4_e2b_tiny_block_train_step.json` | `executor_ir/examples/gemma4_e2b_tiny_block_train_step.json` | IMPORTED |
| `polymath_native/` source subset | `polymath_native/` | IMPORTED_WITH_BUILD_AND_CACHE_EXCLUDES |
| `polymath_native/telemetry/schema.json` | `polymath_native/telemetry/schema.json` | IMPORTED |
| `model_spec/gemma4_e2b.json` | `model_spec/gemma4_e2b.json` | IMPORTED |
| `model_spec/gemma4_e4b.json` | `model_spec/gemma4_e4b.json` | IMPORTED |
| `docs/architecture/static_executor.md` | `docs/architecture/static_executor.md` | IMPORTED |
| `docs/architecture/memory_plan_seq128_256_512.md` | `docs/architecture/memory_plan_seq128_256_512.md` | IMPORTED |
| `docs/decisions/D003_gpu_backend_policy.md` | `docs/decisions/D003_gpu_backend_policy.md` | IMPORTED |
| `docs/decisions/D004_npu_policy.md` | `docs/decisions/D004_npu_policy.md` | IMPORTED |
| `runtime/overnight/20260516T032712Z/native_kernel_gate.json` | `evidence/native_kernel_gate_20260516T032712Z.json` | IMPORTED_AS_TEXT_EVIDENCE |

## G1 Regression Anchor

G1 is already passed and remains a regression floor:

- Model: `google/gemma-4-E4B`
- Revision: `7aa32e6889efd6300124851b164f8b364314c3d8`
- Layer: text decoder layer `0`
- Backend: OpenCL
- Device: REDMAGIC `NX789J / SM8750`
- p50 FP64 cosine: `0.9999890020383452`
- min FP64 cosine: `0.9999801999737985`
- failed tokens below `0.99`: `0`
- repeat output: byte-identical
- phone output sha256:
  `cef523f674cff7ecd01cb59040048f9188f80bcb58b9fc47f1fa7f370ce332cf`

Polymath pointer:

- `runtime/reports/gemma4_megakernel/parity/20260516_e4b_layer0_opencl_gate/gate_result.json`

Imported text evidence:

- `evidence/20260516_e4b_layer0_gate_execution.md`
- `evidence/orchestrator_handover_gemma4_e4b_gate.md`
- `evidence/orchestrator_brief_completion_crosswalk.md`

## Regression Commands

Mac host build and CTest for imported source:

```bash
cmake -S integrations/gemma4-snapdragon-megakernel/gemma4_megakernel \
  -B /tmp/polymath_gemma4_import_build \
  -DGEMMA4_MEGAKERNEL_WARNINGS_AS_ERRORS=ON
cmake --build /tmp/polymath_gemma4_import_build -j 4
ctest --test-dir /tmp/polymath_gemma4_import_build --output-on-failure
```

Comparator unit tests:

```bash
python3 -m unittest discover \
  -s integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/tools/compare_outputs \
  -p 'test_*.py'
```

Phone G1 replay, once ADB transport is present:

```bash
adb -s FY25013101C8 shell '
  cd /data/local/tmp/polymath_gemma4_gate &&
  ./gemma4_layer_runner --probe &&
  ./gemma4_layer_runner --validate-pack \
    /data/local/tmp/polymath_gemma4_gate/layer_pack/gemma4_e4b_layer0_seq128_v0 &&
  ./gemma4_layer_runner --run-opencl \
    /data/local/tmp/polymath_gemma4_gate/layer_pack/gemma4_e4b_layer0_seq128_v0 \
    /data/local/tmp/polymath_gemma4_gate/outputs_opencl_g2_<run_id> &&
  sha256sum \
    /data/local/tmp/polymath_gemma4_gate/outputs_opencl_g2_<run_id>/layer_output.f32.bin
'
```

The expected output hash for the existing G1 pack is
`cef523f674cff7ecd01cb59040048f9188f80bcb58b9fc47f1fa7f370ce332cf`.

RunPod oracle anchor check:

```bash
ssh root@38.80.152.147 -p 31002 -i ~/.ssh/id_ed25519 \
  'test -f /workspace/artifacts/polymath_gemma4/layer_pack/gemma4_e4b_layer0_seq128_v0/reference/layer_output.f32.bin &&
   test -f /workspace/artifacts/polymath_gemma4/phone_outputs/opencl_20260516T222643Z/gate_report.json'
```

## G2 Verification Result

Host-side imported code verification:

- CMake configure: passed on Mac with AppleClang `17.0.0.17000013`.
- CMake build: passed.
- CTest: `2/2` passed.
- Comparator unit tests: `3/3` passed.
- Import leak scan: no forbidden files or forbidden directories under this
  integration namespace after generated Python caches were removed.

Phone transport:

- Initial ADB probe passed earlier in this execution for `FY25013101C8`.
- A later temporary ADB disconnect was diagnosed and recorded.
- The operator reconnected the device, live G1 replay passed with the same
  output hash, and G3 two-layer OpenCL forward expansion passed.

## G3 Forward Expansion Result

Evidence:

- `runtime/reports/gemma4_megakernel/forward_stack/20260517T032829Z_g3_two_layer_opencl/gate_result.json`

Result:

- Layers: `[0, 1]`.
- Backend: OpenCL.
- Device: REDMAGIC `NX789J / SM8750`, serial `FY25013101C8`.
- Compared non-pad tokens: `111`.
- Failed tokens below `0.99`: `0`.
- p50 FP64 cosine: `0.999993563915067`.
- min FP64 cosine: `0.9999842650888192`.
- Layer 0 phone output hash inside the stack:
  `cef523f674cff7ecd01cb59040048f9188f80bcb58b9fc47f1fa7f370ce332cf`.
- Final layer 1 phone output hash:
  `ce285f30d5eb7e5e6164643b0cdd324c11977f91c4ba52e682512d5c9190d538`.
- Max RSS high-water from phone runner: `818764` KB.

Non-claims:

- This is not a backward path.
- This is not an optimizer update.
- This is not phone-native HF streaming/tokenization/packing.
- This is not an integrated training loop or checkpoint/adaptor claim.
- This is not G9 sustained authority proof.

## G4-G7 Results

G4 evidence:

- `runtime/reports/gemma4_megakernel/executor_architecture/20260517T040000Z_g4_minimal_executor/gate_result.json`

Result:

- Minimal executor boundaries exist for tensor storage, backend execution,
  comparison, telemetry, checkpoint storage, and training step execution.
- `OpenClAdapterTrainingStepExecutor` wires the first concrete training-step
  executor to the phone OpenCL adapter kernels.
- Latest runner reproduced G1 and G3 output hashes byte-identically.

G5 evidence:

- `runtime/reports/gemma4_megakernel/backward_path/20260517T040000Z_g5_rank4_adapter_opencl/gate_result.json`

Result:

- Trainable scope: post-layer0 rank-4 residual adapter.
- Backend: phone OpenCL.
- Reference: RunPod PyTorch autograd.
- Gradient cosine min: `0.9999999999999384`.
- Gradient cosine p50: `0.9999999999999647`.
- Failed gradient tensors: `0`.

G6 evidence:

- `runtime/reports/gemma4_megakernel/optimizer_update/20260517T040000Z_g6_rank4_adapter_sgd/gate_result.json`

Result:

- Phone-side SGD update emitted updated adapter tensors.
- Updated adapter tensors matched RunPod reference with cosine min
  `0.9999999999999384`.
- Trainable adapter hashes changed.
- Frozen layer0/layer1 safetensors hashes remained stable.

G7 evidence:

- `runtime/reports/gemma4_megakernel/phone_data_pipeline/20260517T040000Z_g7_hf_native_token_pack/gate_result.json`

Result:

- Phone fetched CC0 Hugging Face text with system `curl`.
- Native C++ Gemma BPE tokenizer produced exact token IDs against RunPod
  `transformers`.
- UFS token cache contained `3` seq128 rows and `343` non-pad tokens.
- Input ID mismatches: `0`.
- Attention mask mismatches: `0`.

## G8 Falsifier Result

Evidence:

- `runtime/reports/gemma4_megakernel/integrated_training/20260517T040000Z_g8_streamed_corpus_falsified/gate_result.json`
- `runtime/reports/gemma4_megakernel/falsifiers/20260517T040000Z_g8_streamed_corpus_falsified/falsifier_report.json`

Result:

- G8 was rejected under falsification.
- The current G5/G6 training path still consumes hidden-state fixtures rather
  than deriving `layer_input` and `per_layer_input` from phone-packed token IDs.
- Combining G5/G6 and G7 as a training claim would introduce a hidden host data
  path, so no streamed-corpus checkpoint or adapter claim is promoted.

Next required repair:

- Generate Gemma `layer_input` and layer 0/1 `per_layer_input` on the phone from
  packed `input_ids` using frozen embedding and PLE assets.
- Run layer0/layer1 from those phone-generated tensors.
- Feed phone-generated activations into the adapter update path.
- Emit a replayable adapter checkpoint manifest without host hidden tensors.

## Acceptance Gate For Import

G2 is considered passed for import/build/harness preservation when:

- every imported file is covered by `IMPORT_FILE_INDEX.tsv`;
- every excluded class above is absent from this integration namespace;
- CPU native gate evidence is preserved as evidence, not as a phone claim;
- the E4B OpenCL phone parity pass is preserved as a regression gate, not
  inflated into a training claim;
- raw model weights, phone output binaries, runner binaries, SDK files, caches,
  tokens, and secrets remain outside git.

G8 integrated streamed-corpus training is the next incomplete PRD gate. The
specific blocker is the missing phone-native token-to-hidden bridge.
