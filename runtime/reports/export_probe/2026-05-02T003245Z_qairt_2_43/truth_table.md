# Phase 0G AOT compile sweep — QAIRT 2.43 + ai-edge-litert 2.1.4

**Host:** Linux x86_64 (Runpod 1hx4ctwg1mpmxr, 128 cores, 2 TiB RAM)
**Date (UTC):** 2026-05-02T00:32:45Z
**QAIRT SDK:** v2.43.0.260127150333 (latest, via Qualcomm AI Hub Workbench)
**ai-edge-litert:** 2.1.4 (latest from PyPI, requires QnnSystem ≥ 1.8)
**LD_LIBRARY_PATH:** /workspace/qairt-2.43/qairt/2.43.0.260128/lib/x86_64-linux-clang
**libQnnSystem.so version (in QAIRT 2.43):** **1.7.0** (from `qnn_manager.cc:284` runtime check)
**SocModel.SM8750:** **available** in ai-edge-litert (so the strongest disconfirming observation from HANDOFF-TO-APPLE-SILICON.md does NOT fire today; this is purely a runtime-version mismatch)

## Verdict matrix

| Model | Scope | Target | TFLite output | TFLite size | QNN AOT verdict | Named root cause |
|---|---|---|---|---|---|---|
| Qwen/Qwen2.5-1.5B | tiny_block | litert_qnn_sm8750 | ok | 143,024 B | failed | Qnn System library version 1.7.0 is mismatched. The minimum supported version is 1.8.0 |
| Qwen/Qwen2.5-1.5B | qwen_block | litert_qnn_sm8750 | ok | 179 MB | failed | Qnn System library version 1.7.0 is mismatched. The minimum supported version is 1.8.0 |
| Qwen/Qwen2.5-1.5B | qwen_frozen_subgraph (layers 1..26) | litert_qnn_sm8750 | ok | 4.6 GB | failed | aot_compile_sdk_binary_missing (large module path; 2GB+ TFLite triggers different SDK code path; underlying cause likely same QnnSystem 1.7 vs 1.8 mismatch) |
| HuggingFaceTB/SmolLM3-3B | smollm3_block | litert_qnn_sm8750 | not run | n/a | spurious | venv-qairt python binary disappeared mid-sweep (MFS race with concurrent pip install in sibling venv) — independent of QNN |
| HuggingFaceTB/SmolLM3-3B | smollm3_frozen_subgraph | litert_qnn_sm8750 | not run | n/a | spurious | same as above |

## Net change vs yesterday (QAIRT 2.41 sweep on this same pod's predecessor)

| Blocker | QAIRT 2.41 verdict | QAIRT 2.43 verdict |
|---|---|---|
| D-024 (QnnSystem version) | 1.6 vs 1.8 (gap=2) | 1.7 vs 1.8 (gap=1) — half-resolved |
| D-025 (TFLite EMBEDDING_LOOKUP rejection on tied-embed) | failed | resolved (qwen_block + qwen_frozen_subgraph TFLite-converted cleanly with 2.43 frontend) |
| D-026 (QAIRT ONNX frontend incompat with onnx 1.21) | n/a (not exercised) | not exercised |
| D-027 (TFLite tied-embed dead-end) | failed | resolved (same as D-025) |

## Decision

- `litert_qnn_sm8750.confirmed_for_socs` stays at `()`. **Phase 1A QNN routing remains gated.**
- D-024 remains the active blocker (now 1.7 vs 1.8 — needs QAIRT 2.44+ which ships QnnSystem 1.8).
- D-025 / D-027 are RESOLVED — the actual model architecture (tied embeddings, the Qwen frozen middle of 26 layers) DOES convert via the 2.43 TFLite frontend.

## Strongest disconfirming observation

If a future ai-edge-litert release loosens the `qnn_manager.cc` minimum version check from 1.8 to 1.7, all three Qwen scopes would recheck and likely succeed. Alternatively, if Qualcomm publishes QAIRT 2.44+ with QnnSystem ≥ 1.8, the same matrix re-runs unchanged should pass for at least tiny_block and qwen_block.
