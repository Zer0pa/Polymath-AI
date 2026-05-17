# Gemma 4 Single-Layer Forward Parity Gate

Date: 2026-05-17
Authority PRD: `docs/PRD-GEMMA4-SNAPDRAGON-MEGAKERNEL-HETEROGENEOUS-TRAINING.md`
Status: PASSED

## Purpose

Validate the smallest real Mega Kernel unit that matters:

```text
one real-pretrained-weight Gemma layer, forward-only, running on RedMagic 10 Pro Adreno GPU through Vulkan or OpenCL, matched against a RunPod/host PyTorch reference with per-token cosine p50 >= 0.99.
```

This gate passed via upstream Gemma4 Kernel commit `c5b6e3522d28d0e1dc56084cb97fa9e95e29aa4e`.

Polymath text-only evidence:

```text
runtime/reports/gemma4_megakernel/parity/20260516_e4b_layer0_opencl_gate/
```

The gate is now a regression check. It is not a demo and not a general harness exercise.

## Non-Negotiables

- Use real pretrained Gemma weights, not random initialization.
- Run the candidate on the RedMagic phone. Host-only success does not pass.
- Use Vulkan or OpenCL on Adreno for the phone run.
- Compare against a host PyTorch reference generated from the same layer, weights, and fixed input set.
- Report per-token cosine min, p10, p50, p90, and max.
- Pass requires p50 >= 0.99.
- Do not measure throughput, thermal, energy, sustained load, backward pass, optimizer, Reflex routing, corpus streaming, or NPU parity in this gate.

## Passing Result

- Model: `google/gemma-4-E4B`
- Revision: `7aa32e6889efd6300124851b164f8b364314c3d8`
- Layer: text decoder layer `0`
- Backend: OpenCL
- Device: REDMAGIC `NX789J / SM8750`
- Compared non-pad tokens: `111`
- Failed tokens below `0.99`: `0`
- p50 cosine: `0.9999890020383452`
- min cosine: `0.9999801999737985`
- Repeat run: byte-identical output

## System Roles

| Node | Role | Forbidden For This Gate |
| --- | --- | --- |
| Mac | Control plane and orchestrator | model storage, dataset storage, large intermediates |
| RunPod | Build server and host PyTorch reference oracle | runtime data path, training data staging |
| RedMagic 10 Pro | Authority runtime device | none; this is the target |

## Required Inputs

The executor or Mega Kernel agent must provide:

- source commit or artifact identity for the one-layer forward candidate;
- exact Gemma model variant and layer index;
- weight source and license attestation path;
- fixed test input set identity;
- host PyTorch reference output path;
- phone executable/library path;
- backend used: `vulkan` or `opencl`;
- comparator script path.

If any item is missing, the gate is blocked.

## Output Contract

Each attempt writes:

```text
runtime/reports/gemma4_megakernel/parity/<UTC_RUN_ID>/
  gate_result.json
  commands.log
  artifact_manifest.json
  host_reference_manifest.json
  phone_device_manifest.txt
  phone_run.log
  cosine_report.json
  blockers.md
```

No model weights, SDK binaries, tokens, private keys, raw caches, `.tflite`, `.safetensors`, `.bin`, `.zip`, or phone token files are copied into git.

## Gate Result Schema

`gate_result.json` must include:

```json
{
  "run_id": "<UTC_RUN_ID>",
  "status": "pass_or_fail_or_blocked",
  "model": "<gemma_variant>",
  "layer_index": 0,
  "backend": "vulkan_or_opencl",
  "device": "RedMagic 10 Pro / SM8750",
  "real_weights": true,
  "cosine_p50": 0.0,
  "pass_threshold_p50": 0.99,
  "host_reference": "<path_or_hash>",
  "phone_output": "<path_or_hash>",
  "notes": []
}
```

## Execution Order

1. Confirm the candidate artifact is the one-layer forward-only Gemma gate, not a broader demo.
2. Freeze artifact identity and hashes before deployment.
3. Generate or verify the host PyTorch reference on RunPod.
4. Push only required runtime artifacts to the phone.
5. Preserve any existing phone binary or harness by checksum before overwrite.
6. Execute the phone forward pass.
7. Pull only text reports and numeric outputs needed for comparison.
8. Run the cosine comparator.
9. Declare only `pass`, `fail`, or `blocked`.

## Failure Handling

- If phone execution fails, diagnose phone runtime or backend bring-up.
- If cosine is below threshold, diagnose numerical parity.
- If real-weight provenance is missing, block the gate.
- If the run is host-only, block the gate.
- If the candidate silently uses CPU instead of Adreno Vulkan/OpenCL, fail the gate.

Do not convert any failure into progress narrative. The next action must either fix the blocker or falsify the current candidate.
