# Phase 0G plan — SmolLM3 / Qwen QNN export verdict

**Boundary:** Research infrastructure for in silico on-device LLM training and multilingual / multi-domain knowledge model construction. Outputs are research artifacts - model checkpoints, training telemetry, evaluation reports, throughput measurements. No regulatory certification claims. No clinical or human-subject use. No surveillance, biometric profiling, or identity inference. No model weights distributed without explicit license attestation. No training on copyrighted material without explicit corpus-license decomposition. No deployment to production without a falsifier-traced acceptance gate.

## Status

**BLOCKED on host platform.** The path requires `ai-edge-torch` + `ai-edge-litert` AOT compile, which depends on torch >= 2.4. Our pinned host torch is 2.2.2 (Intel Mac wheel ceiling, Decision D-003). On the phone, ai-edge-litert has no aarch64-android wheel on PyPI (Decision D-019).

## What "Phase 0G complete" actually requires

Per PRD §Phase 0G - Experiment 2: "SmolLM3 QNN Export Verdict". Output is an envelope-shaped record per `(model, scope, target)` triple stating:

| Scope | Target | Result |
|---|---|---|
| `tiny_block` | `litert_qnn_sm8750` | `ok / failed / unsupported` + delegate %|
| `qwen_block` | `litert_qnn_sm8750` | as above |
| `qwen_frozen_subgraph` | `litert_qnn_sm8750` | as above |
| `smollm3_block` | `litert_qnn_sm8750` | as above |
| `smollm3_frozen_subgraph` | `litert_qnn_sm8750` | as above |

The runner exists at `polymath_ai/dispatch/export_probe.py`; today it returns `mac_sim` stub rows for every triple. Phase 0G replaces those with real LiteRT compile rows for the QNN target. **Until at least one (model, scope) returns `ok` with a non-zero delegate percentage, the falsifier `qnn_exact_path_unproven` remains `blocked` and Phase 1A cannot use QNN acceleration.**

## Three viable paths

### Path A — Dedicated Linux x86_64 host (preferred)

* Spin up a Linux x86_64 machine (Runpod RTX-4090 instance suffices, or any operator Linux box).
* `pip install torch>=2.4 ai-edge-torch ai-edge-litert` — all wheels available on linux_x86_64.
* Convert PyTorch `nn.Module` -> `.tflite` via `ai_edge_torch.convert(...)`.
* AOT-compile the `.tflite` to a Qualcomm SM8750 binary via `ai_edge_litert.aot.aot_compile(target=qnn_target.SocModel.SM8750)`.
* Run the compile dry-run to record delegate percentage and unsupported-op list.
* Push the binary + a small native runner to the phone via ADB.
* On the phone, load via the system's `libtensorflowlite.so` (part of the Adreno driver package `com.qualcomm.qti.gpudrivers.sun.api35` per D-016).
* Record envelope-shaped CompileRecord rows.

Estimated effort: 1-2 engineer-days for the convert + AOT path; +1 day for the native runner; +0.5 day for the per-scope sweep. Reflects PRD §Deep-Research Lookup Verdicts row "ai_edge_torch / LiteRT Torch Qwen path: PyTorch converter beta, NPU support in development".

### Path B — Apple Silicon Mac (operator-owned)

* On Apple Silicon (M1+) torch >= 2.4 wheels are shipped. ai-edge-torch + ai-edge-litert install cleanly. AOT compile chain is identical to Path A.
* Output binaries + native runner same shape.
* Caveat: macOS arm64 wheels for ai-edge-litert exist but the QNN target enum (`SocModel`) is the Qualcomm-specific subset. Need to confirm at runtime.

### Path C — Compile on Runpod, push artifacts to phone

* Same as Path A but on a Runpod GPU instance (PRD §Distillation Arm reuses Runpod for teacher generation; same auth path applies).
* After AOT compile, `gh release` or `huggingface_hub upload_folder` the binaries.
* Phone (host or via SSH) downloads + invokes.

## Recommendation for tonight

**Path A on a Runpod CPU box (cheapest).** Budget: ~$0.50 / hour for a small Linux x86_64 instance. Dry-run AOT compile of the tiny + Qwen + SmolLM3 graph scopes yields the entire export truth table within 1-2 hours of spinup time. Operator-engagement question: launch a Runpod CPU instance for Phase 0G, OR defer until operator's Apple Silicon machine is back online.

## Substrate that is ALREADY in place (tonight's tonight work)

* `polymath_ai/dispatch/export_probe.py` runner shape (matrix sweep, envelope output, markdown truth table).
* `polymath_ai/scheduler/registry.py:litert_qnn_sm8750` backend with `requires_soc_confirmation=True` and `confirmed_for_socs=()`. Phase 0G success adds `(SM8750, 1.0)` to the confirmed list; Phase 1A cannot route to QNN until that addition.
* `polymath_ai/falsifiers/registry.py:qnn_exact_path_unproven` blocking by default; flips to `pass` only when at least one CompileRecord per scope is stored.
* SSH path to phone for any binary-push or invocation step.

## Falsifier coverage

* `qnn_exact_path_unproven` — stays blocked until Path A/B/C delivers compile rows.
* `device_soc_mismatch` — already passes (SoC confirmed SM8750 confidence 1.0 per D-015).
* `qnn_unsupported_op` — populated by Phase 0G compile output; if delegate % below threshold, fail.
* `smollm3_export_unproven` — flipped to pass only when SmolLM3 graph scopes return `ok` with delegate.

## Out of scope tonight

The actual AOT compile + binary push + native runner — operator decision required on which host (Path A/B/C). **Recording this as the documented blocker in `docs/EXECUTION-REPORT.md`.**
