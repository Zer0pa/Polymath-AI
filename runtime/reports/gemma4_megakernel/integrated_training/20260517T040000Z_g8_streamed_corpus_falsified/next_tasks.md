# G8 Repair Tasks

G8 was rejected because the current training runtime still consumes
hidden-state fixtures. The next valid attempt must remove those fixtures from
the phone runtime path.

## Required Bridge

Runtime input must be:

```text
HF raw text -> phone curl -> native Gemma BPE tokenizer -> UFS token cache
-> phone-native embedding/per-layer-input generation
-> phone OpenCL layer0/layer1
-> phone adapter backward/update
-> phone checkpoint manifest
```

Do not feed `layer_input.f32.bin`, `per_layer_input.f32.bin`,
`layer0_output.f32.bin`, or `layer1_output.f32.bin` from RunPod into the G8
runtime. These files are allowed only as oracle comparison outputs.

## Engineering Tasks

1. Extend the G7 cache ABI with `labels.u32.bin`, `loss_mask.u8.bin`, and
   `position_ids.u32.bin`.
2. Export immutable Gemma embedding assets for phone use:
   `embed_tokens.weight`, layer-0/1 PLE token slices, layer-0/1 PLE projection
   slices, and PLE norm weights.
3. Implement phone-side BF16 row gather from `input_ids.u32.bin` to
   `layer_input.f32`.
4. Implement phone-side Gemma PLE generation for layer 0 and layer 1
   `per_layer_input.f32`.
5. Re-run layer0/layer1 OpenCL from phone-generated tensors and compare against
   RunPod PyTorch oracle outputs.
6. Feed phone-generated `h0` and a phone-generated stop-gradient `h1` target
   into the rank-4 adapter backward/update path.
7. Emit checkpoint directory with trainable pre/post hashes, frozen pre/post
   hashes, optimizer state, replay manifest, and artifact manifest.
8. Re-run G1/G3 regression with the latest runner before promotion.

## Valid Minimal Objectives

- Two-layer phone distillation: train the post-layer0 rank-4 adapter to map
  phone-produced `h0` toward phone-produced layer1 output treated as
  stop-gradient.
- Chunked tied-embedding next-token NLL: train the same adapter using labels
  from the G7 cache and a memory-bounded vocabulary projection.

Both objectives are valid only if tokenization, packing, embedding generation,
forward, backward, update, and checkpoint writing all execute on the phone.
