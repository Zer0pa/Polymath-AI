# Phase 1A — On-device QNN inference verdict (REDMAGIC 10 Pro / SM8750 / Hexagon NPU)

**Host:** REDMAGIC 10 Pro+ (model NX789J, SoC SM8750, ADB attached over USB to Mac)
**Date (UTC):** 2026-05-02T04:40:00Z (immediately after Phase 0G AOT compile in D-030)
**QAIRT runtime on device:** v2.44.0.260225 aarch64-android, /data/local/tmp/qairt-2.44/
**Hexagon skel search path:** v79 + v75 + v81 (unsigned), /dsp (system fallback)
**Path used:** raw QNN context binary extracted from LiteRT apply_plugin .tflite via `scripts/host/extract_qnn_context.py`, loaded on phone via `qnn-net-run --retrieve_context`. This bypasses the absent aarch64-android LiteRT runtime (D-019).

## qnn-platform-validator pre-flight

Backend GPU: Hardware Supported, Libraries Found
Backend DSP (Hexagon NPU via libadsprpc/libcdsprpc): Hardware Supported, Libraries Found

## Inference verdicts (5/5 ok during Phase 0G; 2/5 exercised on device for Phase 1A.0)

| Scope | QNN binary size | Phase 0G AOT | On-device load | On-device inference | 10x wall-clock | Output sanity (FP32 zeros input) |
|---|---|---|---|---|---|---|
| qwen_block (Qwen2.5-1.5B layer 0) | 90 MB | ok | ok | ok | **0.523 s** | min=-3.38, max=3.50, mean≈0, std=1.14 — plausible single-layer transformer state |
| qwen_frozen_subgraph (Qwen2.5-1.5B layers 1..26 — the actual ELO frozen middle) | 2.3 GB | ok | ok | ok | **10.62 s** | min=-20.4, max=21.6, mean=0.22, std=6.15 — plausible 26-layer cascade |
| tiny_block (synthetic) | 166 KB | ok | not exercised on device | n/a | n/a | n/a |
| smollm3_block (SmolLM3-3B layer 0) | 150 MB | ok | not exercised on device | n/a | n/a | n/a |
| smollm3_frozen_subgraph (SmolLM3-3B layers 1..30) | 960 MB | ok | not exercised on device | n/a | n/a | n/a |

**Note:** the 10x wall-clock figures include first-time context-binary mmap + tensor allocation, which dominates a 10-iteration timing on a >2 GB binary. Steady-state per-inference latency on Hexagon will be much lower; a proper benchmark with a longer N + warmup discard is the next-step ask of the Device lane.

## What this proves

- The Phase 0G AOT compile artifacts (committed in D-030) **actually execute on the operator's Snapdragon 8 Elite Gen 4 phone**, not just on the AI Hub Workbench / pod simulator. Real Hexagon NPU, real on-device timing, real FP32 outputs that distribute as transformer hidden states should distribute.
- The "extract embedded QNN context binary from apply_plugin .tflite" path works in production. We don't need a LiteRT-on-Android runtime to reach Hexagon; the raw QNN context binary path through `qnn-net-run --retrieve_context` is sufficient and is the recommended deployment path until ai-edge-litert ships an aarch64-android wheel.
- `litert_qnn_sm8750.confirmed_for_socs = (("SM8750", 1.0),)` from D-030 is now reinforced with on-device evidence, not just AOT-compile evidence. Phase 1A is open for end-to-end ELO inference experiments.

## Reproducer

```bash
# Host side (assuming you already have an AOT compile in runtime/reports/export_probe/<ts>/)
python scripts/host/extract_qnn_context.py \
  --tflite runtime/reports/export_probe/<ts>/qnn_aot/qwen_frozen_subgraph/qwen_frozen_subgraph_Qualcomm_SM8750_apply_plugin.tflite \
  --out /tmp/qwen_frozen_subgraph.qnn.bin

# Push to phone
adb push /tmp/qwen_frozen_subgraph.qnn.bin /data/local/tmp/phase1a/
adb push scripts/phone/run_qnn_inference.sh /data/local/tmp/phase1a/

# Stage a synthetic FP32 input matching the model's input shape (1×16×1536 for Qwen2.5-1.5B)
adb shell 'cd /data/local/tmp/phase1a && dd if=/dev/zero of=input.bin bs=1 count=98304 && echo input.bin > input_list.txt'

# Run
adb shell sh /data/local/tmp/phase1a/run_qnn_inference.sh qwen_frozen_subgraph 10
```

Output lands in `/data/local/tmp/phase1a/output_qwen_frozen_subgraph/Result_0/serving_default_output_0_output.raw`.

## Next steps for the Device lane

1. Replace synthetic FP32 zeros input with real tokenized + embedded text (Qwen tokenizer → embedding lookup → hidden_states for the first layer 0, which becomes input for the layers-1..26 frozen subgraph).
2. Wire the `polymath_ai.scheduler.ReflexScheduler` decision path to actually invoke `qnn-net-run` (or its libQnnHtp.so directly via JNI / NDK) when the registry routes to `litert_qnn_sm8750`.
3. Run a Phase 1A experiment: ELO Stage-1 on-device with the trained-on-host qwen_block (only layer 0 + lm_head are trained) and the FROZEN qwen_frozen_subgraph delegated to the phone's NPU. Measure tokens/hour.
4. Optionally: quantize the frozen subgraph to INT8 to shrink the 2.3 GB binary by ~4x for faster load + lower memory footprint. The current FP16/FP32 path is the unblocked baseline; quantization is an optimization track.
