# DM3 Vulkan/WebGPU prior art (fork-and-own reference for Polymath Gate B)

**Boundary:** Research infrastructure for in silico on-device LLM training and multilingual / multi-domain knowledge model construction. Outputs are research artifacts - model checkpoints, training telemetry, evaluation reports, throughput measurements. No regulatory certification claims. No clinical or human-subject use. No surveillance, biometric profiling, or identity inference. No model weights distributed without explicit license attestation. No training on copyrighted material without explicit corpus-license decomposition. No deployment to production without a falsifier-traced acceptance gate.

**Status:** captured 2026-05-01 from REDMAGIC 10 Pro+ at `/data/local/tmp/SoC_Harness/` and `/data/local/tmp/shaders.wgsl`. The DM3 substrate-reconstruction workstream had a working WebGPU/wgpu compute pipeline running on the phone's Adreno 830 GPU **before Polymath started**. Per MODUS-OPERANDI.md fork-and-own discipline, Polymath may copy patterns / code shape / receipt formats from this prior art but NOT establish runtime co-dependency.

## What is here

| File | Source on phone | What it is |
|---|---|---|
| `shaders.wgsl` | `/data/local/tmp/shaders.wgsl` | Six WebGPU compute kernels: `k_relax`, `k_ecc`, `k_holography`, `k_spectral`, `k_transformer` (note!), and one more. Bindings, workgroup_size, structured FieldState/Adjacency/Params layout. |
| `dm3_probe_vulkan.jsonl` | `phase_01_2_3_4_1_1_quarantine_20260405T202459Z/root_surface/` | One probe receipt with `verdict: PASS` for `t1_contraction`. Hash-chain shape (state_hash_before, state_hash_after, previous_hash, jit_hash, driver_hash). |
| `dm3_probe_vulkan_stdout.txt` | same dir | "Initializing DM3 Transformer Mesh V1... Vertices: 380... T1 Complete. Receipt logged." |

The actual runtime (`snic_rust`, ~2.2 MB) lives on the phone at `/data/local/tmp/SoC_Harness/bin/snic_rust`. Not pulled here (it's a DM3-specific binary; we adapt the pattern, not the artefact).

## What Polymath inherits structurally

1. **wgpu (WebGPU) → Adreno path is proven on this phone.** The `dm3_probe_vulkan.jsonl` receipt is a real artefact of a successful compute dispatch.
2. **The harness shape:** Rust binary loads wgsl, builds compute pipelines via wgpu, dispatches workgroups, writes receipts to disk. This is the canonical Linux/Android wgpu pattern.
3. **Receipt schema** (kept here as direct reference for the Polymath `polymath_ai.audit.chain` shape): `run_id`, `abi_version`, `schema_hash`, `jit_hash`, `driver_hash`, `workgroup_size`, `subgroup_size`, `device_id`, `thermal_state`, `clocks`, `build_mode`, `input_hash`, `state_hash_before`, `state_hash_after`, `metrics`, `verdict`, `timestamp`, `previous_hash`. Polymath's existing audit chain already covers most of these (`prev_event_hash`, `event_hash`, `recorded_at`, `payload`); the GPU-specific fields (`driver_hash`, `workgroup_size`, `subgroup_size`, `device_id`) get added when a Vulkan dispatch event is emitted.
4. **The `k_transformer` kernel name** suggests DM3 already ran *some* transformer-shape compute on the phone GPU. Worth code-reading their snic_rust (in a separate pass) to see exactly what shape — could meaningfully shorten Polymath's Gate B engineering scope.

## What Polymath does NOT inherit

- DM3's specific physics kernels (`k_relax`, `k_ecc`, `k_holography`, `k_spectral`) — these are physics-substrate-specific; not relevant to LLM compute.
- DM3's specific binary `snic_rust` — runtime co-dependency forbidden by fork-and-own.
- DM3's `CONFIG.json` acceptance criteria (those are physics-substrate gates: `R_plus_T_err_max`, `alpha_target`, `eigs_inside_unit_disk`, etc. — not LLM gates).

## Gate B engineering scope for Polymath (estimated)

For Polymath's ELO Stage 1 forward pass on Adreno via Vulkan compute:

| Kernel | Scope | Effort |
|---|---|---|
| `polymath_matmul` | Q*K^T, attention output * V, MLP gate/up/down projections | 2-3 days (with subgroup-aware tiling for Adreno's 32-wide warps) |
| `polymath_rmsnorm` | per-token RMSNorm (already in DM3 stack as part of k_transformer? to be confirmed) | 0.5 day |
| `polymath_swiglu` | SwiGLU activation in MLP | 0.5 day |
| `polymath_softmax` | attention softmax with online-softmax for memory efficiency | 1 day |
| `polymath_rope` | rotary positional embeddings on Q/K | 1 day |
| `polymath_runner` (Rust binary) | wgpu pipeline setup, buffer management, dispatch loop, receipt writer | 3-4 days |
| Backward pass kernels (ELO trainable layers only) | matmul backward, layer-wise grad accumulation | 4-5 days |
| Integration with `polymath_ai.elo.trainer` | host-driven training loop via ADB SSH | 2 days |
| End-to-end smoke + checkpoint + sync | Phase 0E E0.1 equivalent on Adreno | 1 day |
| **Total** | First-cut Gate B implementation | **~3 weeks engineer time** |

Reference implementations (open-source, Apache 2.0):
- mlc-llm Vulkan kernels for Llama-shape transformer (https://github.com/mlc-ai/mlc-llm)
- ggml Vulkan compute shaders (https://github.com/ggml-org/ggml)
- candle-core's Metal shaders (Apple-specific but transferable to wgpu)

## Files in this directory

`shaders.wgsl`, `dm3_probe_vulkan.jsonl`, `dm3_probe_vulkan_stdout.txt`, this README. All artefacts here are committed for reference; their content is DM3 workstream output and remains under DM3's confidentiality terms — they are kept as "prior art the operator owns" reference material per MODUS-OPERANDI.md.
