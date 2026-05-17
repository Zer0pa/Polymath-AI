# Static Executor Architecture

## Scope

This document defines the static executor contract for a Gemma-4-shaped selective training step. It is not a CUDA design and does not prescribe a backend kernel language. The executor IR lives in `executor_ir/schema.json`, with a concrete tiny-block example in `executor_ir/examples/gemma4_e2b_tiny_block_train_step.json`.

The local source anchors are:

- `third_party_maps/_sources/gallery/model_allowlists/1_0_14.json`: Gemma-4-E2B-it is listed as `gemma-4-E2B-it.litertlm`, with `maxContextLength` 32000, `accelerators` `gpu,cpu`, multimodal flags, and speculative decoding capability.
- `third_party_maps/_sources/LiteRT-LM/README.md`: LiteRT-LM records Gemma 4 MTP support and runtime-level CPU/GPU/NPU acceleration.

The executor treats unlisted internal Gemma dimensions as symbolic. It must not hard-code hidden size, head count, intermediate size, or vocabulary size until a model manifest exposes them.

## Governing Objective

The acceptance gate is a static train-step plan that can prove bounded memory for seq128, seq256, and seq512 before any backend implementation is written. A schedule that improves local throughput while regressing the bounded-memory authority metric fails.

The static executor must prove:

- Every tensor has a lifetime, memory pool, dtype, layout, mutability, and CPU/GPU/NPU/unknown device hint.
- Frozen base weights are never rewritten.
- Trainable state is limited to declared selective tensors.
- Full `B*S*V` logits and unbudgeted `B*A*S*S` attention scores are rejected.
- Unknown backend arenas are named and bounded before use.

## IR Shape

The IR is intentionally small:

- `model`: family, variant, symbolic dimensions, sequence profiles, and local source facts.
- `training_step`: objective, micro-batch, precision, trainable scope, and optimizer state location.
- `devices`: explicit CPU, GPU, NPU, and unknown entries.
- `memory_pools`: host batch, frozen weight map, activation ring, attention scratch, adapter state, gradients, optimizer state, NPU arena, and unknown backend arena.
- `tensors`: tokens, labels, masks, frozen weights, adapters, activations, scratch, loss, gradients, optimizer state, and checkpoint output.
- `ops`: coarse static operations, not kernels.
- `schedules`: primary path plus LoRA/adapters fallback ladder and unknown-backend validation.

The schema allows composite ops such as `tiny_blocks_forward` because the goal is an executor contract, not a lowered graph. A later lowering pass can expand a composite block into RMSNorm, projections, RoPE, attention, gated MLP, residuals, backward fragments, and reductions.

## Static Execution Model

The executor borrows these principles from megakernel and persistent-kernel systems:

- Fixed sequence profiles are selected before execution.
- Device memory pools are allocated once per profile.
- Frozen weights and trainable adapters remain resident when the backend supports residency.
- A small command schedule drives repeated transformer block work.
- Intermediates are ring-reused or recomputed instead of dynamically allocated.
- Barriers occur only at input staging, loss handoff, gradient reduction, and optimizer update.

The design stops at the IR boundary. It does not include CUDA, shader code, Metal code, OpenCL code, or vendor NPU command streams.

## Device Hints

| Hint | Meaning in this executor |
| --- | --- |
| CPU | Host-side data prep, labels, masks, scalar bookkeeping, fallback optimizer, serialization, and seq128 reference path. |
| GPU | Primary static forward/backward target for adapter training, activation ring, fused or chunked attention, and gradient reductions. |
| NPU | Frozen-forward candidate only until mutable adapter or gradient support is proven for the specific backend. |
| unknown | Explicit unresolved placement. It is not free memory. A backend-specific lowering must publish byte bounds before it can pass planning. |

The local Gemma 4 E2B allowlist names GPU and CPU accelerators. NPU remains a hint because LiteRT-LM advertises NPU acceleration generally, but the local Gemma 4 E2B allowlist does not make NPU training support a fact.

## Trainable Scope

Default trainable state is adapter-only:

- `blocks[0..1].attn.q_proj.lora`
- `blocks[0..1].attn.v_proj.lora`
- `blocks[0..1].attn.o_proj.lora`
- `blocks[0..1].mlp.gate_proj.lora`
- `blocks[0..1].mlp.up_proj.lora`
- `blocks[0..1].mlp.down_proj.lora`

Dense selective training is an upgrade path, not a default. It requires mutable f16 shadow weights, matching gradient reductions, and a memory plan that still passes seq128/256/512. Without that proof, dense mutation remains disabled.

## LoRA And Adapter Fallback Schedule

The fallback ladder is part of the executor contract:

| Level | Entry condition | Trainable state | Device posture |
| --- | --- | --- | --- |
| S0 selective dense upgrade | Backend exposes mutable dense shadows and bounded gradients | Declared dense slices plus adapters | GPU primary, CPU optimizer fallback |
| S1 LoRA all target sites | Dense upgrade unavailable | q, v, o, gate, up, down LoRA in target blocks | GPU forward/backward, CPU AdamW state |
| S2 attention LoRA | seq512 or memory budget rejects all target sites | q, v, o LoRA only | GPU preferred, CPU seq128 reference |
| S3 minimal adapter | Adapter gradients still exceed budget | q/v only, bias-like adapter, or prompt adapter | CPU/GPU bounded path |
| S4 CPU reference | No accelerator training path is proven | Minimal adapter at seq128 only | CPU only |

The fallback order reduces trainable parameter memory before reducing sequence length. This keeps the authority metric focused on bounded seq128/256/512 planning instead of hiding failure by silently shrinking the workload.

## Optimizer Placement

The default optimizer is CPU-hosted AdamW for adapters. GPU optimizer state is allowed only when the profile budget admits it. The executor transfers adapter gradients and adapter deltas only; it never transfers full frozen base weights for update.

AdamW memory is:

`2 * P_lora * sizeof(f32)`

An optional f32 master copy adds:

`P_lora * sizeof(f32)`

If seq512 cannot fit with AdamW state pressure, the fallback is an 8-bit optimizer or SGD-style adapter update, not dense base mutation.

## Required Lowering Checks

A backend-specific executor can claim a schedule only after it resolves:

- Static shape profile: seq128, seq256, or seq512.
- Attention scratch bytes. Fused or tiled attention is preferred; materialized `B*A*S*S` scores require explicit budget admission.
- Loss projection mode. Streamed or chunked cross entropy is preferred; full `B*S*V` logits are rejected by default.
- Adapter update path. Only adapter-sized gradients and deltas may cross CPU/GPU boundaries.
- Unknown arenas. Every `unknown` pool must be replaced by a byte formula or rejected.

## Handoff

Next agents can build a planner that reads the JSON example, chooses a sequence profile, evaluates symbolic memory formulas after model dimensions are known, and emits a backend-specific execution plan. They should not add CUDA while this IR remains the authority artifact.
