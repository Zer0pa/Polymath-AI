# Export truth table

Boundary: see polymath_ai.boundary.text.

Stage column distinguishes a *dry-run stub* (host MacSim adapter, no real compile happened) from a *measured* row (real LiteRT / QNN / Vulkan compile log). Stub rows do NOT satisfy qnn_exact_path_unproven; they only show the matrix shape.

| Model | Scope | Target | Backend | Stage | Result | Delegate % | Unsupported ops |
|---|---|---|---|---|---|---:|---|
| Qwen/Qwen2.5-1.5B | tiny_block | litert_qnn_sm8750 | litert_qnn_sm8750 | measured | ok | - | - |
| Qwen/Qwen2.5-1.5B | qwen_block | litert_qnn_sm8750 | litert_qnn_sm8750 | measured | ok | - | - |
| Qwen/Qwen2.5-1.5B | qwen_frozen_subgraph | litert_qnn_sm8750 | litert_qnn_sm8750 | measured | ok | - | - |
| HuggingFaceTB/SmolLM3-3B | smollm3_block | litert_qnn_sm8750 | litert_qnn_sm8750 | measured | ok | - | - |
| HuggingFaceTB/SmolLM3-3B | smollm3_frozen_subgraph | litert_qnn_sm8750 | litert_qnn_sm8750 | measured | ok | - | - |
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

* platform: `Linux-6.17.0-1008-nvidia-x86_64-with-glibc2.35`
* machine: `x86_64`
* python: `3.10.12`

## Versions

* `litert_torch` = `0.9.0`
* `torch` = `2.11.0+cpu`
* `ai_edge_litert` = `2.1.4`
* `transformers` = `4.55.4`
* `tokenizers` = `0.21.4`
* `numpy` = `2.2.6`

## QNN failure signatures

* none — all QNN scopes returned `ok`.
