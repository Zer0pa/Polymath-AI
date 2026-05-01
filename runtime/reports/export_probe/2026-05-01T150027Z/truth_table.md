# Export truth table

Boundary: see polymath_ai.boundary.text.

Stage column distinguishes a *dry-run stub* (host MacSim adapter, no real compile happened) from a *measured* row (real LiteRT / QNN / Vulkan compile log). Stub rows do NOT satisfy qnn_exact_path_unproven; they only show the matrix shape.

| Model | Scope | Target | Backend | Stage | Result | Delegate % | Unsupported ops |
|---|---|---|---|---|---|---:|---|
| Qwen/Qwen2.5-1.5B | tiny_block | litert_qnn_sm8750 | litert_qnn_sm8750 | measured | unsupported | - | - |
| Qwen/Qwen2.5-1.5B | qwen_block | litert_qnn_sm8750 | litert_qnn_sm8750 | measured | unsupported | - | - |
| Qwen/Qwen2.5-1.5B | qwen_frozen_subgraph | litert_qnn_sm8750 | litert_qnn_sm8750 | measured | unsupported | - | - |
| HuggingFaceTB/SmolLM3-3B | smollm3_block | litert_qnn_sm8750 | litert_qnn_sm8750 | measured | unsupported | - | - |
| HuggingFaceTB/SmolLM3-3B | smollm3_frozen_subgraph | litert_qnn_sm8750 | litert_qnn_sm8750 | measured | unsupported | - | - |
| Qwen/Qwen2.5-1.5B | tiny_block | cpu | mac_sim | stub | ok | 100% | - |
| Qwen/Qwen2.5-1.5B | tiny_block | vulkan_gpu | mac_sim | stub | ok | 100% | - |
| Qwen/Qwen2.5-1.5B | qwen_block | cpu | mac_sim | stub | ok | 100% | - |
| Qwen/Qwen2.5-1.5B | qwen_block | vulkan_gpu | mac_sim | stub | ok | 100% | - |
| Qwen/Qwen2.5-1.5B | qwen_frozen_subgraph | cpu | mac_sim | stub | ok | 100% | - |
| Qwen/Qwen2.5-1.5B | qwen_frozen_subgraph | vulkan_gpu | mac_sim | stub | ok | 100% | - |
| HuggingFaceTB/SmolLM3-3B | smollm3_block | cpu | mac_sim | stub | ok | 100% | - |
| HuggingFaceTB/SmolLM3-3B | smollm3_block | vulkan_gpu | mac_sim | stub | ok | 100% | - |
| HuggingFaceTB/SmolLM3-3B | smollm3_frozen_subgraph | cpu | mac_sim | stub | ok | 100% | - |
| HuggingFaceTB/SmolLM3-3B | smollm3_frozen_subgraph | vulkan_gpu | mac_sim | stub | ok | 100% | - |

## Host

* platform: `macOS-15.5-arm64-arm-64bit`
* machine: `arm64`
* python: `3.11.14`

## Versions

* `litert_torch` = `0.9.0`
* `ai_edge_torch` = `0.7.2`
* `torch` = `2.11.0`
* `ai_edge_litert` = `2.1.4`
* `transformers` = `4.55.4`
* `tokenizers` = `0.21.4`
* `numpy` = `1.26.4`

## QNN failure signatures

* `tiny_block` (Qwen/Qwen2.5-1.5B) — stage `aot_compile_sdk_binary_missing` — FileNotFoundError: Failed to find apply plugin binary. AOT might not be available on your platform.
* `qwen_block` (Qwen/Qwen2.5-1.5B) — stage `aot_compile_sdk_binary_missing` — FileNotFoundError: Failed to find apply plugin binary. AOT might not be available on your platform.
* `qwen_frozen_subgraph` (Qwen/Qwen2.5-1.5B) — stage `aot_compile_sdk_binary_missing` — FileNotFoundError: Failed to find apply plugin binary. AOT might not be available on your platform.
* `smollm3_block` (HuggingFaceTB/SmolLM3-3B) — stage `aot_compile_sdk_binary_missing` — FileNotFoundError: Failed to find apply plugin binary. AOT might not be available on your platform.
* `smollm3_frozen_subgraph` (HuggingFaceTB/SmolLM3-3B) — stage `aot_compile_sdk_binary_missing` — FileNotFoundError: Failed to find apply plugin binary. AOT might not be available on your platform.
