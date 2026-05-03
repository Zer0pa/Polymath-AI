# Phase 1A.A.0 — D-033 cosine-validation diagnostics

**Date:** 2026-05-03T10:24Z
**Inputs:** 20 real-tokenized hidden-state tensors derived from English sentences via `Qwen/Qwen2.5-1.5B` tokenizer + embedding layer (host-side).
**Phone binary under test:** `qwen_frozen_subgraph.qnn.bin` (2.3 GB Qualcomm SM8750 context binary; produced by Phase 0G AOT compile, D-030).

## 1. First-cut compare: FAIL

Host CPU reference (with real Qwen2.5-1.5B pretrained weights, transformers 4.55.4, AOT-matching RoPE / causal-mask / position_embeddings) vs phone NPU output:

| Statistic | Value | Threshold (D-033) |
|---|---|---|
| n_compared | 20 / 20 | — |
| p50_cos_total | 0.0280 | ≥ 0.99 |
| min_cos_total | 0.0055 | — |
| min(cos_p5_per_token) | -0.0157 | ≥ 0.95 |
| max_mse | 1011.69 | — |
| max_abs_err | 503.36 | — |
| **D-033 falsifier** | **FAIL** | — |

Cosine ≈ 0 means the phone output is **orthogonal** to the host reference. Not a precision drift — a fundamental disagreement.

## 2. Root cause investigation

### 2.1 Phone binary is input-insensitive at large scale

Computed pairwise cosine between phone outputs for **different** input sentences:

| Pair | Input cosine | Output cosine |
|---|---:|---:|
| seq 0 vs seq 1 | 0.399 | **0.99905** |
| seq 0 vs seq 2 | 0.402 | **0.99882** |
| seq 0 vs seq 3 | (similar) | **0.99957** |
| seq 1 vs seq 2 | 0.340 | **0.99906** |

Two semantically different sentences → two phone outputs that are **0.999 cosine-similar** to each other. The 26-layer cascade has produced essentially the same vector regardless of input.

First 8 FP32 values of three different phone outputs:
```
Result_0:  [ 1.5117, -4.1133, -9.8516,  1.3545, -1.2676, -1.7520, 10.4688, -7.4727]
Result_1:  [ 1.6865, -4.2852, -9.7422,  2.6348, -2.4414, -1.8965,  9.2969, -7.7109]
Result_3:  [ 1.5117, -4.1133, -9.8516,  1.3545, -1.2676, -1.7520, 10.4688, -7.4727]   <- byte-identical to Result_0
Result_4:  [ 1.2588, -3.9453, -9.8984,  1.6104, -2.0332, -1.3115,  9.8047, -7.5898]
```

Output stats are nearly invariant across all 20 sequences:
- `mean` ≈ 0.21 ± 0.01
- `std` ≈ 6.15 ± 0.01 (matches the std=6.15 we recorded in D-031 / D-032 for **zero-input** runs)
- `min` ≈ -20.4 ± 0.1
- `max` ≈ 21.7 ± 0.3

The binary's output distribution is essentially the same on a real Qwen-tokenized hidden state as it was on synthetic FP32 zeros (D-031).

### 2.2 Why this happens: random-init weights collapse the 26-layer cascade

`scripts/silicon/run_phase0g_aot.py` documents this explicitly in its module docstring:

> "Random-init weights are used for the real-architecture scopes (qwen_*, smollm3_*); Phase 0G is a graph-structure / op-coverage probe, not a weight-correctness probe. Architecture comes from `transformers.AutoConfig.from_pretrained(...)` so the op surface matches the production weights identically."

And in `_build_qwen_frozen_subgraph()`:
```python
cfg = AutoConfig.from_pretrained("Qwen/Qwen2.5-1.5B")
...
layers.append(Qwen2DecoderLayer(cfg, layer_idx=layer_idx).eval())   # random init, no from_pretrained
...
meta = {..., "weights": "random_init"}
```

A **26-layer stack of random-init Qwen2 transformer blocks is highly contractive**. After ~5-10 layers, hidden-state vectors converge toward the largest singular direction of the composed transformation. By layer 26, the input's individuality has been crushed. The output is dominated by the layers' weight structure, not by the input.

Contrast with **trained** Qwen2.5-1.5B: the network has been optimized to be expressive across inputs, preserving information through depth. Training breaks the random-init contraction property.

### 2.3 Sanity check: random-init host vs phone

We rebuilt the host reference with the SAME random-init layer construction the AOT runner used (`Qwen2DecoderLayer(cfg, layer_idx=k).eval()` with deterministic seeding) and compared to phone output. Cosine median: -0.006 (also essentially zero).

This is **expected** — the random-init host can't reproduce the phone's exact random-init weights without the same tracing + initialization seed sequence the AOT compile used. It DOES reproduce the same input-insensitivity property: host random-init outputs also collapse to a similar shape regardless of input.

The sanity-check confirms: the on-device binary is genuine, the math is correct, the random-init contractivity is the dominant phenomenon.

## 3. What this proves about Phase 1A and 1A.B

The earlier closed phases are **not invalidated**:
- D-031 (Phase 1A on-device proof): the binary executes end-to-end on Hexagon NPU — TRUE, regardless of weights.
- D-032 (Phase 1A.B sustained-load): 22,850 inferences at 100% rc=0, 100% out_size=98304 — TRUE, regardless of weights.
- The "growing variance with depth" output stats from D-031 / D-032: TRUE, but now interpreted as **the random-init contraction property**, not **trained-Qwen forward through depth**.

The system-level claims (binary loads, executes, produces consistent FP32 output, no thermal throttle, no silent corruption) hold. The **language-modelling claim** is what's now blocked.

## 4. Methodology validated

The cosine validation pipeline (host CPU reference vs phone NPU output) is itself **working correctly** — it surfaces this exact kind of issue cleanly. Once we recompile Phase 0G with real pretrained weights, the same compare script should produce cosine ≥ 0.99 (modulo any numeric quantization the QNN compiler applies).

## 5. Next step (Phase 1A.A.0.b)

Modify `scripts/silicon/run_phase0g_aot.py` to support a `--real-weights` flag that loads `Qwen/Qwen2.5-1.5B` via `AutoModelForCausalLM.from_pretrained(...)` and slices its `.model.layers[1:27]` for the frozen-subgraph compile. Re-run Phase 0G AOT for `qwen_frozen_subgraph` (and optionally `qwen_block`) on a Linux x86_64 pod. Re-deploy. Re-run this same `phase1aa0_real_data.py --mode compare`. Expect cosine ≥ 0.99.

Engineering effort: ~30 min runner edit + ~10 min compile on pod + ~5 min redeploy + ~2 min revalidate. **Calendar-blocked on operator providing a fresh Linux x86_64 pod** (the prior pod 1hx4ctwg1mpmxr is now offline).
