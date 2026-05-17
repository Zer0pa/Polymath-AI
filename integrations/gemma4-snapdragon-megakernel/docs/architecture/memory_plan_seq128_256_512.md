# Memory Plan For Seq128/256/512

## Purpose

This plan sizes the static executor around three sequence profiles: 128, 256, and 512 tokens. It is symbolic because the local Gemma 4 artifacts expose deployment metadata but not all internal dimensions. A backend planner must fill in hidden size, head count, vocabulary size, and adapter site dimensions from a model manifest before claiming fit.

## Symbols

| Symbol | Meaning |
| --- | --- |
| `B` | Micro-batch, fixed at 1 in the tiny-block IR. |
| `S` | Sequence length, one of 128, 256, 512. |
| `H` | Hidden width. Symbolic until model manifest is available. |
| `A` | Attention head count. Symbolic until model manifest is available. |
| `V` | Vocabulary size. Symbolic until model manifest is available. |
| `L_TINY` | Number of trained target blocks, fixed at 2. |
| `r` | LoRA rank, 8 in the example IR. |
| `P_lora` | Total LoRA parameter elements for selected sites. |

Default activation and adapter dtype is f16. Optimizer accumulators are f32 unless the fallback schedule selects an 8-bit or SGD-style update.

## Static Pools

| Pool | Device hint | Formula | Notes |
| --- | --- | --- | --- |
| `host_batch` | CPU | `B*S*(4 + 4 + 1)` bytes | token ids, labels, and boolean loss mask. |
| `frozen_weight_mmap` | CPU/GPU/NPU | runtime-owned | Gemma base weights are read-only and not part of trainable memory. |
| `gpu_activation_ring` | GPU | `3*B*S*H*2` bytes | current hidden, residual/input slot, and remat slot. |
| `gpu_attention_scratch` | GPU/unknown | preferred `O(B*S*H)` | materialized `B*A*S*S*2` is rejected unless explicitly budgeted. |
| `trainable_adapter` | GPU/CPU | `P_lora*2` bytes | persistent LoRA A/B tensors. |
| `adapter_gradients` | GPU/CPU | `P_lora*2` bytes | overwritten after optimizer update. |
| `host_optimizer_state` | CPU | `2*P_lora*4` bytes | Adam moments; optional f32 master weights add `P_lora*4`. |
| `npu_forward_arena` | NPU | backend-owned | forward-only candidate until gradient support is proven. |
| `unknown_backend_arena` | unknown | must be bounded | cannot pass planning while opaque. |

## Sequence Scaling

The activation ring scales linearly with `S`. Materialized attention scales quadratically and is the main rejected shape for seq512.

| Profile | Hidden activation `B*S*H*2` | 3-slot activation ring | Materialized attention scores `B*A*S*S*2` |
| --- | --- | --- | --- |
| seq128 | `256*H` bytes | `768*H` bytes | `32768*A` bytes |
| seq256 | `512*H` bytes | `1536*H` bytes | `131072*A` bytes |
| seq512 | `1024*H` bytes | `3072*H` bytes | `524288*A` bytes |

The executor should prefer fused, tiled, or streaming attention so attention scratch tracks `B*S*H` rather than `B*A*S*S`. If a backend only offers materialized attention, seq512 must fail planning unless the explicit memory budget admits the quadratic tensor.

## Loss Projection

Full logits require:

`B*S*V*2` bytes

That tensor is not part of the default plan. Cross entropy must be streamed or vocabulary-chunked so the temporary logits chunk has a bounded size independent of full `S*V` materialization. If a backend cannot stream or chunk the loss projection, it may run CPU seq128 reference only.

## Adapter Memory

For a LoRA site with dense shape `[out, in]` and rank `r`, parameter elements are:

`r*(in + out)`

For multiple sites:

`P_lora = sum_over_sites(r*(in_site + out_site))`

Default memory with AdamW is:

| Component | Formula |
| --- | --- |
| Adapter params | `2*P_lora` bytes |
| Adapter grads | `2*P_lora` bytes |
| Adam moments | `8*P_lora` bytes |
| Optional f32 master | `4*P_lora` bytes |

The default plan keeps Adam moments on CPU. GPU memory for adapter training is therefore adapter params, adapter grads, activation ring, attention scratch, and runtime-owned frozen-weight residency.

## Per-Profile Policy

| Profile | Primary policy | Fallback trigger | Fallback |
| --- | --- | --- | --- |
| seq128 | GPU adapter train step; CPU reference allowed | No GPU or unknown backend scratch | CPU minimal adapter reference. |
| seq256 | GPU adapter train step with CPU optimizer | All target-site LoRA exceeds budget | Attention-only LoRA q/v/o. |
| seq512 | GPU adapter train step with remat and streamed loss | Materialized attention, full logits, or adapter gradient pressure | q/v LoRA, then minimal adapter; do not shrink below seq512 until these fail. |

NPU is not a training target in this plan. It may be used for frozen forward experiments only after the backend exposes a static arena size and confirms that no mutable training state is hidden inside the NPU runtime.

## LoRA Fallback Ladder

The fallback ladder reduces trainable memory before changing the sequence profile:

1. Train all selected LoRA sites: q, v, o, gate, up, and down.
2. Disable MLP adapters and train q, v, and o only.
3. Disable output adapter and train q and v only.
4. Train a prompt, bias-like adapter, or single projection adapter.
5. Use CPU seq128 reference only for correctness checks.

For seq512, steps 1 through 4 must be attempted or explicitly rejected by formula before the executor claims the profile cannot fit.

## Planning Gates

The static memory planner fails the schedule if any condition holds:

- Any `unknown_backend_arena` lacks a byte bound.
- Any op materializes `B*S*V` logits without chunking.
- Any attention path materializes `B*A*S*S` at seq512 without an explicit budget.
- Any optimizer path copies or mutates frozen base weights.
- Any NPU path is used for backward without proven gradient support.
- Any fallback silently reduces sequence length before reducing adapter scope.

These gates keep the plan aligned with the authority metric: bounded seq128/256/512 selective training memory, not a smaller demo workload.
