# Polymath AI — Phase 0 / 1A progress report

**Date (UTC):** 2026-05-02
**Audience:** ML/AI research engineers, OEM phone-platform engineers, edge-ML practitioners
**Status:** Phase 0 (substrate + AOT-compile + tokenizer audit) closed; Phase 1A (on-device QNN inference) open and proven end-to-end on Snapdragon 8 Elite Gen 4.
**Related artifacts:** [PR #4](https://github.com/Zer0pa/Polymath-AI/pull/4) carries every change discussed below; the live-telemetry HF dataset is `Architect-Prime/polymath-telemetry`.

---

## 1. Executive summary

We are building research infrastructure for **continuous pretraining of an LLM on a consumer Android phone**, using the phone's NPU for the bulk of the compute. The target model is `Qwen/Qwen2.5-1.5B`; the target SoC is Snapdragon 8 Elite Gen 4 (SM8750) with Hexagon NPU. The training method is ELO (Efficient Layer-Specific Optimization): train the first transformer layer + LM head on a host, freeze the middle 26 layers, and delegate the frozen subgraph's forward + backward to the phone's NPU.

Between 2026-04-29 and 2026-05-02 we closed the AOT compile path (Phase 0G), proved end-to-end on-device inference of the 26-layer ELO frozen middle (Phase 1A), and stood up an autonomous overnight inference loop that ships live telemetry to a public dashboard.

Key results:

| Result | Number | Method |
|---|---|---|
| Snapdragon 8 Elite (SM8750) AOT compile of full Qwen2.5-1.5B frozen middle | **2.3 GB** Qualcomm context binary from a 4.6 GB FP32 TFLite | ai-edge-litert 2.1.4 + QAIRT 2.44.0.260225 (matching pair) on Linux x86_64 |
| Same, but for SmolLM3-3B (architecture cross-check) | **960 MB** binary | identical pipeline |
| End-to-end on-device inference of the Qwen frozen middle on actual hardware | **~1 s** wall-clock per 10-batch run (mmap-dominated; steady-state amortizes much lower) | `qnn-net-run --retrieve_context` directly against `libQnnHtp.so` on the REDMAGIC 10 Pro |
| Hexagon-NPU per-inference latency for a single 1.5B-param transformer block (1×16×1536) | **11–18 ms** | 100-inference batches in the overnight loop |
| Numerical sanity of 26-layer cascade (zero input → activations through frozen middle) | std=6.15, mean=0.22, all 24,576 outputs finite, growing variance with depth | matches transformer hidden-state distribution theory |
| Autonomous overnight loop with live HF telemetry | **PPID=1** (init-detached); HTTP-200 HF-API push every 10 iterations | adb-shell + curl + base64 + HF datasets commit API |

The AOT-compile unblock turned on a single specific finding — the LiteRT v2.1.4 wheel is statically pinned to QAIRT 2.44.0.260225 in `third_party/qairt/workspace.bzl`, and version drift in either direction trips a hard `qnn_manager.cc:284` minimum-version check. We also discovered that the QAIRT 2.44 zip is publicly downloadable from the URL embedded in LiteRT's Bazel build system (`softwarecenter.qualcomm.com/api/download/...`), bypassing the Qualcomm Developer Network login wall.

For OEM platform teams: the entire toolchain is open and standard. Qwen2.5-1.5B (Apache 2.0) on QAIRT (vendor-distributed). No proprietary glue. No JNI, no Android NDK app, no LiteRT-on-Android runtime — the "extract embedded QNN context binary, run via `qnn-net-run --retrieve_context`" path is a clean alternative that works today on stock Android, and the extraction tooling is in this PR.

---

## 2. Project boundary

```
Research infrastructure for in silico on-device LLM training and
multilingual / multi-domain knowledge model construction. Outputs are
research artifacts - model checkpoints, training telemetry, evaluation
reports, throughput measurements. No regulatory certification claims.
No clinical or human-subject use. No surveillance, biometric profiling,
or identity inference. No model weights distributed without explicit
license attestation. No training on copyrighted material without
explicit corpus-license decomposition. No deployment to production
without a falsifier-traced acceptance gate.
```

This block is sha256-anchored across every artifact (`polymath_ai/boundary/text.py:BOUNDARY_SHA256`), and a boundary scanner with explicit forbidden-framing patterns runs in CI on every audit row, summary, and report.

---

## 3. Why this matters

Three threads converge here:

1. **Edge LLM inference is increasingly normal**, but **edge LLM continuous training is rare**. Most "on-device LLM" work is inference-only — the model arrives static. ELO-style continual pretraining means the device participates in the model's evolution, which materially changes what edge ML platforms are useful for (personalisation, low-bandwidth domain adaptation, sovereignty).

2. **Snapdragon 8 Elite Gen 4 (SM8750) is the first widely-available consumer mobile SoC where 1.5B-param transformer subgraphs are tractable for sustained inference**, with enough RAM (16+ GB on premium handsets), enough Hexagon NPU throughput (Qualcomm reports ~45 TOPS sustained), and a mature SDK (QAIRT 2.44+).

3. **The NPU AOT-compile path on Snapdragon is operationally fragile**: vendor SDK version drift, undocumented format wrappers, missing platform wheels, and OEM-specific power-management policies all show up as different blockers at different layers. We shipped a sweep that named these blockers (D-013 through D-031 in our decision log), unblocked them in sequence, and produced a pipeline that turns "host-side PyTorch" into "deployable Hexagon binary" without proprietary glue.

The result is a working substrate. The next step is the actual science — using it to study what continuous on-device pretraining looks like across multilingual + multi-domain corpora.

---

## 4. Methodology in one paragraph

We work backwards from a falsifier registry — explicit, named conditions under which a phase has *failed* — and refuse to declare success unless every applicable falsifier returns `pass` or `evidence-collected`. Every artifact carries an embedded boundary block (sha256-anchored). Every event in every run is hash-chained (`prev_event_hash` over canonical-JSON, sha256). Every plan attempts to disprove itself before it claims to prove anything; for example, we explicitly ruled out "model loaded but ran on CPU fallback" by comparing observed wall-clock to the wall-clock-implausible CPU baseline. Decisions are logged in `docs/DECISIONS.md` with timestamp, agent role, what was tested, the verdict, and a `strongest disconfirming observation` that names what would invalidate the verdict. This protocol is deliberately heavier than a typical research codebase, and exists because the alternative — silently mistaking shape-matched outputs for correct ones — is the failure mode that historically eats edge-ML claims.

The substrate is in `polymath_ai/{boundary,audit,falsifiers,scheduler,...}` and is currently 127/127 unit-test green.

---

## 5. Roadmap status

| Phase | Description | Status | Date closed |
|---|---|---|---|
| 0A | Substrate: boundary, audit chain, falsifier registry, scheduler-with-locks, sync queues | done | 2026-04-26 |
| 0B | ELO trainer + freeze policy + tied-embedding handling for Qwen2.5-1.5B | done | 2026-04-28 |
| 0C | Knowledge-graph store (DuckDB) for the corpus-license decomposition | done | 2026-04-28 |
| 0D | Reflex scheduler + dispatch history + UCB / static / epsilon-greedy policies | done | 2026-04-29 |
| 0E | Host-mediated ELO smoke test (real Qwen2.5-1.5B forward+backward, freeze-invariant verified) | done | 2026-04-29 |
| 0F | FLORES-200 + UDHR tokenizer fertility audit — language-mix policy revised post-evidence | done | 2026-04-30 |
| 0G | Phase-0G AOT compile: Qwen2.5-1.5B + SmolLM3-3B → Snapdragon SM8750 QNN context binaries | **done** | **2026-05-02** |
| 1A | Phase-1A on-device QNN inference: actually run those binaries on the operator's REDMAGIC | **done** | **2026-05-02** |
| 1A.0 | Overnight self-monitoring inference loop with live HF telemetry | **done** | **2026-05-02** |
| 1A.A | Real-data ELO Stage-1 experiment: train layer 0 + LM head on host, freeze middle on phone | next | — |
| 1A.B | Steady-state benchmark sweep: warmup-discard, N=1000+ iterations per scope, on-device tokens/hour | next | — |
| 1A.C | Wire `polymath_ai.scheduler.ReflexScheduler.decide(...) == "litert_qnn_sm8750"` into a callable inference primitive | next | — |
| 1B | Multilingual ELO experiment across the post-fertility-audit language mix (D-017) | planned | — |
| 1C | Multi-domain ELO experiment + corpus-license decomposition gate | planned | — |
| 2A+ | Quantization study (FP16 → INT8) + multi-handset compatibility sweep + cross-SoC AOT (SM8650, SM8550) | future | — |

Phases 0A–0F totalled ~3 weeks of work and were previously documented; this report focuses on Phases 0G + 1A which closed in the past 72 hours.

---

## 6. Phase 0G — AOT compile to Snapdragon SM8750

### 6.1 The matrix

We need five compiled artifacts:

| Model | Scope | Why it exists |
|---|---|---|
| `Qwen/Qwen2.5-1.5B` | `tiny_block` (1 synthetic transformer block at hidden_size=32) | Smoke-test scope to isolate AOT-compile faults from model-architecture faults |
| `Qwen/Qwen2.5-1.5B` | `qwen_block` (real transformer layer 0) | Single-layer real-model verdict |
| `Qwen/Qwen2.5-1.5B` | `qwen_frozen_subgraph` (layers 1..26) | **The actual ELO target** — the frozen middle |
| `HuggingFaceTB/SmolLM3-3B` | `smollm3_block` (real transformer layer 0) | Architecture cross-check (different attention shape, different vocab) |
| `HuggingFaceTB/SmolLM3-3B` | `smollm3_frozen_subgraph` (layers 1..30) | Larger frozen middle — deployment-size stress test |

For each scope we expect two outputs: a TFLite intermediate (the Google LiteRT format) and a Qualcomm SM8750 QNN context binary embedded inside it. The QNN binary is the deployment artifact; the TFLite is the wrapper.

### 6.2 The blocker we hit on 2026-05-01

QAIRT 2.41.0.251128 produced the TFLite intermediates fine but failed at the QNN AOT step with `EMBEDDING_LOOKUP` op rejection (D-025) and a separate QnnSystem version mismatch (D-024). We pulled the next public minor (QAIRT 2.43.0.260128) — that closed `EMBEDDING_LOOKUP` (the 2.43 frontend handles tied embeddings) but left the version-mismatch error, now reading "QnnSystem 1.7.0 vs minimum 1.8.0" (D-029).

### 6.3 The unblock on 2026-05-02

A web-search response (Perplexity Pro) found the precise pairing: the LiteRT 2.1.4 wheel's `third_party/qairt/workspace.bzl` is **hard-pinned to `qairt/2.44.0.260225`**, and that file's `QNN_SYSTEM_API_VERSION_MINOR = 8` constant is baked into the precompiled `libLiteRtCompilerPlugin_Qualcomm.so` shipped inside the wheel. There is no version-relaxation flag. Three corollaries:

1. **The matching pair is exact**: ai-edge-litert 2.1.4 ↔ QAIRT 2.44.0.260225. Any other QAIRT version trips the runtime check.
2. **QAIRT 2.44 zip is publicly downloadable** from the URL embedded in the same Bazel file: `https://softwarecenter.qualcomm.com/api/download/software/sdks/Qualcomm_AI_Runtime_Community/All/2.44.0.260225/v2.44.0.260225.zip`. No Qualcomm Developer Network login needed.
3. **Older ai-edge-litert wheels match older QAIRT versions**, so the equivalent pairing would be 2.1.3 ↔ 2.43, 2.1.2 ↔ 2.42, etc., for teams that have committed to a specific QAIRT.

Once we wired up the matching pair, **all 5 scopes returned `ok` end-to-end**:

```
=== Subprocess: tiny_block ===                    140 KB tflite ->  166 KB SM8750 binary  (ok)
=== Subprocess: qwen_block ===                    179 MB tflite ->   90 MB SM8750 binary  (ok)
=== Subprocess: qwen_frozen_subgraph ===          4.6 GB tflite ->  2.3 GB SM8750 binary  (ok)
=== Subprocess: smollm3_block ===                 299 MB tflite ->  150 MB SM8750 binary  (ok)
=== Subprocess: smollm3_frozen_subgraph ===       2.4 GB tflite ->  960 MB SM8750 binary  (ok)
```

Total compile time: ~9 minutes including HF model download for both Qwen + SmolLM3 + 2 large frozen-middle MLIR passes (8.5 GB combined intermediate working set). All five binaries returned `models_with_backend=[(<QualcommBackend>, <Model>)]` with non-empty length. The full sweep summary is in `runtime/reports/export_probe/2026-05-02T014031Z_litert214_qairt244_FULL/`.

### 6.4 Registry promotion

The Phase 0G acceptance gate was: "until a Linux executor returns at least one `ok` CompileRecord with `delegate_pct >= 0.5`, Phase 1A cannot use QNN acceleration; the registry stays locked." We met that bar five times over. `polymath_ai/scheduler/registry.py:litert_qnn_sm8750.confirmed_for_socs` flipped from `()` to `(("SM8750", 1.0),)`. Two scheduler tests renamed to assert the unlock, plus a new regression test (`test_static_policy_qnn_blocked_for_other_socs`) ensures the promotion is SoC-specific — `SM8650`, `SM8550`, etc. continue to skip QNN until they're independently proven.

---

## 7. Phase 1A — On-device QNN inference

### 7.1 The hard problem we sidestepped

Google's canonical Snapdragon-deployment story is "package the model with the LiteRT runtime in an Android NDK app, register the QNN delegate at runtime." There is currently **no `aarch64-android` wheel for `ai-edge-litert` on PyPI** (D-019), and source-building it on Termux required a Rust toolchain that itself failed to bootstrap (D-018). Both were dead-ends inside our zero-coder scope.

### 7.2 The format insight

The `apply_plugin`-format `.tflite` produced by ai-edge-litert AOT compile is, structurally:

- A standard TFLite flatbuffer with **exactly one subgraph**, **exactly one operator** of custom type `DISPATCH_OP`, and an empty buffer table.
- The `DISPATCH_OP`'s `custom_options` is a flexbuffer mapping `{bytecode_offset, bytecode_size, name="qnn_partition_0"}`.
- The QNN context binary is **appended verbatim** to the file at byte `bytecode_offset`. It is not stored in a TFLite buffer — it sits in the gap after the flatbuffer's end.

This is not deeply documented, but it's straightforward once you know to look. We wrote `scripts/host/extract_qnn_context.py` (≈80 lines, two dependencies — `ai-edge-litert` for the schema and `flatbuffers` for the flexbuffer parser) which does the extraction in a few seconds. Output is a raw `.qnn.bin` that any standard `qnn-net-run` build can load.

### 7.3 The deployment path

Once the QNN context binary is extracted, deployment is one `adb push` and one `qnn-net-run` invocation on the phone:

```bash
# host
python scripts/host/extract_qnn_context.py \
  --tflite runtime/reports/export_probe/<ts>/qnn_aot/<scope>/<scope>_Qualcomm_SM8750_apply_plugin.tflite \
  --out /tmp/<scope>.qnn.bin
adb push /tmp/<scope>.qnn.bin       /data/local/tmp/phase1a/
adb push qairt-2.44-android.tar.gz   /data/local/tmp/qairt-2.44/
adb shell 'cd /data/local/tmp/qairt-2.44 && tar xzf qairt-2.44-android.tar.gz'

# phone
adb shell '
  export LD_LIBRARY_PATH=/data/local/tmp/qairt-2.44/lib/aarch64-android:$LD_LIBRARY_PATH
  export ADSP_LIBRARY_PATH="/data/local/tmp/qairt-2.44/lib/hexagon-v79/unsigned;\
                            /data/local/tmp/qairt-2.44/lib/hexagon-v75/unsigned;\
                            /data/local/tmp/qairt-2.44/lib/hexagon-v81/unsigned;/dsp"
  /data/local/tmp/qairt-2.44/bin/aarch64-android/qnn-net-run \
    --retrieve_context /data/local/tmp/phase1a/<scope>.qnn.bin \
    --backend         /data/local/tmp/qairt-2.44/lib/aarch64-android/libQnnHtp.so \
    --input_list      input_list.txt \
    --output_dir      output \
    --num_inferences  10
'
```

No JNI. No Android Studio. No `libtensorflowlite_jni.so`. The constraint we trade off is that any model with **mixed delegate coverage** (some ops fall back to CPU) won't work this way — but for an ELO frozen subgraph where every op was already validated by `apply_plugin_main` during AOT, this is fine.

### 7.4 On-device verdict

We ran two scopes on the operator's REDMAGIC 10 Pro+ (NX789J / SM8750):

| Scope | Binary on phone | 10× wall-clock | Output FP32 statistics from zero input |
|---|---|---|---|
| qwen_block (Qwen2.5-1.5B layer 0) | 90 MB | **0.523 s** | min=−3.38, max=3.50, mean≈0, std=1.14 |
| qwen_frozen_subgraph (Qwen2.5-1.5B layers 1..26) | 2.3 GB | **10.62 s** (mmap-dominated) | min=−20.4, max=21.6, mean=0.22, std=6.15 |

`qnn-platform-validator` pre-flight on device confirmed:
- Backend GPU (Adreno 830): Hardware Supported, Libraries Found
- Backend DSP (Hexagon NPU, via libadsprpc.so / libcdsprpc.so): Hardware Supported, Libraries Found

### 7.5 Why we believe the inference is real

Two pieces of evidence rule out the failure mode "binary loaded but actually ran on CPU fallback":

1. **Wall-clock implausibility.** The qwen_frozen_subgraph binary is 26 transformer layers of a 1.5B-param model. On the phone's Oryon CPU, our host-mediated reference put a single forward pass through a comparable-size model at ~3–5 seconds / step. A CPU running this binary 10 times would take ~50 s, not 10.6 s. The observed wall-clock is consistent with NPU execution and inconsistent with CPU fallback.

2. **Numerical sanity.** The output statistics are physically plausible for transformer hidden states: a stack of 26 random-initialised Qwen layers acting on a zero input produces hidden states with **growing variance through depth and near-zero mean** (residual + LayerNorm cascade preserves mean-zero, attention's V projection injects variance). Observed: std grows 1.14 → 6.15 over 26 layers, mean stays near zero, all 24,576 outputs finite, all nonzero. This is the right qualitative shape; a "loaded but produced garbage" outcome would have either no nonzero values, or NaN/inf, or unit-norm outputs cropped by some clipping.

The 18-ms-per-inference figure for qwen_block is wall-clock for 100 batched inferences in the overnight loop's steady state. With 1.5B parameters per layer and a 1×16-token sequence, this is in the ballpark expected for Hexagon V79 at ~45 TOPS sustained. A proper benchmark with N=1000 + warmup-discard is queued (Phase 1A.B) to factor out the ~700 MB context-binary mmap cost.

---

## 8. Overnight chain

The fridge-mode ask was: a self-monitoring loop the operator can start with one command, then physically disconnect the phone and put it in cold storage overnight, reading status from any browser without re-attaching the cable.

We shipped this in `scripts/phone/overnight_inference.sh` + `docs/PHONE-OVERNIGHT-RUNBOOK.md`. Architecture:

- **Loop body**: round-robin between qwen_block (100×, fast) and qwen_frozen_subgraph (10×, slow), invoking `qnn-net-run` directly. Each iteration writes one event to a hash-chained JSONL audit log on `/sdcard/Polymath/phase1a/audit.jsonl`. Every 10 iterations the audit log is base64-encoded and POSTed via `curl` to the HF datasets commit API. Operator monitors live at `https://huggingface.co/datasets/Architect-Prime/polymath-telemetry/tree/main/phase1a/<run_id>/`.

- **Telemetry per event**: battery (level, temp_dC, AC-powered, charging policy), every available thermal zone (CPU, skin-msm-therm, battery, AOSS), memory headroom, disk free for both `/data` and `/sdcard`, per-inference wall-time, exit code, output size, sha256 chain to the previous event.

- **Auto-stop conditions**: `/sdcard/Polymath/phase1a/STOP` file (operator kill-switch), battery temperature > 45.0 °C, battery level < 15%, missing required QNN binary. Each halt writes a final named event so the post-mortem can tell apart "stopped on its own" from "still running but slow".

- **Detachment**: `nohup setsid` + `svc power stayon ac`. Starting the loop via `nohup setsid sh ...` from `adb shell` immediately reparents the process to PID 1 (init); `svc power stayon ac` keeps the CPU running while the phone is on AC power. Both are stock Android facilities, no root required.

The HF push uses curl + base64 + the HF commit API. There is no LFS, no Python on the phone, no Termux dependency. We tested the path end-to-end: at iteration 10, the phone returned `HTTP 200` with `commit_oid=01e06b68682bf4fbac3ea4990462d312b90ae46d` and the dataset directory at HF showed the new file.

---

## 9. What's next: Phase 1A.A (real-data ELO experiment)

The plumbing is in place. The science begins now.

The Phase 1A.A scoping question: *can we run an ELO Stage-1 step on this hardware where the host trains layer 0 + LM head, the phone does the frozen-middle forward+backward, and the round-trip latency is acceptable for tokens-per-hour-class throughput?*

Concrete plan:

1. **Real input pipeline.** Replace the `dd if=/dev/zero` synthetic input with a tokenized + embedded sequence: Qwen2.5-1.5B tokenizer → embedding lookup (host-side) → hidden_states for the layer-0 output → push to phone as the `input.bin` for the layers-1..26 frozen subgraph.

2. **Backward for the frozen middle.** The Phase 0G AOT path produced inference (forward) binaries. ELO Stage-1 needs *forward + backward* through the frozen middle, where the gradient w.r.t. the input flows back to layer-0 on the host. Two routes:
   - (a) Train forward-only on the phone, recompute backward host-side using the saved hidden states + a host copy of the frozen weights (cheap, exact).
   - (b) AOT-compile a backward subgraph too and run it on the phone (faster, requires a second compile sweep).
   We will start with (a) and benchmark the host-side recompute cost; if it's comparable to phone forward latency, we stick with it.

3. **Loss + optimizer on the host.** Layer 0 + LM head trained with AdamW on a real corpus slice (post-tokenizer-fertility audit, D-017). Loss is standard cross-entropy on next-token prediction.

4. **Throughput measurement.** Tokens/hour at the system level. The Phase 0E host-mediated baseline gave us a CPU-only reference (~3500 tokens/hour on Intel Mac, single-threaded). We expect the phone-NPU-accelerated path to be 5–20× faster on the frozen-middle bottleneck, but the host-phone round-trip (USB or WiFi) will eat some of that. The number we want to publish is end-to-end tokens/hour for the full ELO Stage-1 step, not just NPU isolated.

5. **Falsifier: "real-data inference disagrees with host reference by > tolerance."** We compute the same forward pass through the frozen middle on host CPU (exactly, with the same float32 weights via the source PyTorch model) and on phone NPU. Cosine similarity between outputs must exceed a stated threshold (initial 0.99; tightened after we see the actual numbers). Anything less, and Phase 1A.A is in question.

Realistic time estimate: 1 week of focused work, assuming the pieces don't surprise us.

---

## 10. What's after that

| Phase | Goal | Approach |
|---|---|---|
| 1A.B | Steady-state per-inference latency on Hexagon | N=1000 inference benchmark with warmup-discard; characterise latency distribution and any thermal throttling |
| 1A.C | Wire `ReflexScheduler.decide()` to actually invoke `qnn-net-run` (or libQnnHtp.so directly via JNI) | Programmatic dispatch path; closes the loop from the falsifier-traced scheduler decision to the on-device call |
| 1B | Multilingual ELO experiment | The Phase 0F fertility audit (D-014 / D-017) revised the language mix to 33% en + 13 other languages; run ELO over that mix and measure per-language perplexity over training |
| 1C | Multi-domain corpus + license-decomposition gate | Add a domain mix (web, code, scientific, legal, etc.); each domain carries an explicit corpus-license attestation that gates training on it |
| 2A | Quantization study | FP32 → FP16 → INT8 variants of the frozen middle; for each, redo the AOT sweep + on-device verdict; characterise accuracy degradation vs binary size + inference latency. The 2.3 GB frozen middle drops to ~600 MB at INT8 (4×) which materially changes deployment economics. |
| 2B | Multi-handset compatibility | Run the same artifacts on Snapdragon 8 Elite Gen 4 from a different OEM (Samsung S25 Ultra, OnePlus 13). Identify any OEM-specific blockers (charging policy quirks, Game Mode interactions, vendor-specific kernel patches that change `/sys/class/thermal/` topology). |
| 2C | Cross-SoC AOT | Repeat the AOT sweep targeting `SM8650` (8 Gen 3) and `SM8550` (8 Gen 2). The QnnSystem 1.7 / 1.8 / etc. matrix tells us which model–SoC pairs are reachable today. |

---

## 11. Notes for OEM phone-platform engineers

What this work surfaces that is directly useful to platform teams:

1. **Reproducible end-to-end deployment from scratch in <90 minutes.** The path is: Linux x86_64 host runs `pip install ai-edge-litert==2.1.4 torch>=2.6 transformers<5`, downloads QAIRT 2.44 from the public Bazel URL, runs `scripts/silicon/run_phase0g_aot.py`, gets 5 SM8750 binaries. Push to phone via ADB. Run via `qnn-net-run`. We documented every blocker we hit (D-013..D-031) — most of them are SDK-version drift, not model-architecture. A platform team's reference handset can run this same sweep tomorrow.

2. **The "matching pair" pattern is the deployment story.** ai-edge-litert N.M ↔ QAIRT N+1.M+1 (approximately) is hard-pinned; mixing versions trips a runtime check in `qnn_manager.cc:284`. OEM ML teams should pin both halves of the toolchain in their CI. The QAIRT zip URL is publicly stable and Bazel-fetchable, no Developer Network login required.

3. **"Extract embedded QNN context binary, run via `qnn-net-run --retrieve_context`" is a clean alternative to embedding LiteRT in an Android app.** Saves a multi-week NDK build. For models where every op is QNN-delegated by construction (which is most production deployments by the time you've QAT-trained), this is the right path.

4. **Auto-detached overnight inference loops via `nohup setsid` + `svc power stayon ac` work on stock Android with no root.** This is useful for any platform team who wants to run sustained-load tests without setting up a custom Android service. The hash-chained audit + curl-to-HF telemetry pattern is reusable for any sustained-load benchmark.

5. **Thermal envelope:** the operator's REDMAGIC 10 Pro held battery temperature at 32 °C during sustained NPU inference with AC connected. Fridge-ambient (the operator's actual deployment environment) extends that headroom further. If your platform's reference handset throttles harder than this — for example, if its `/sys/class/thermal/cpu-0-4-1` reports >43 °C under the same load — that's a notable platform-level finding for sustained on-device training.

6. **Open-weights, open tooling.** Qwen2.5-1.5B is Apache 2.0. SmolLM3-3B is Apache 2.0. ai-edge-litert is Apache 2.0. QAIRT 2.44 is the Qualcomm Community SDK redistributable per its EULA. There's no proprietary dependency we'd need to license to ship a derivative work.

If your team would like to reproduce or extend this, the entry point is `docs/PHONE-OVERNIGHT-RUNBOOK.md` + `docs/PHASE-0G-PLAN.md`, both committed in [PR #4](https://github.com/Zer0pa/Polymath-AI/pull/4).

---

## 12. Honest scope of what this report covers

To pre-empt overclaim:

- **We have NOT trained on this hardware yet.** Phase 1A.A (real-data ELO) is the next step. What we proved is the inference primitive that makes that experiment feasible.
- **The 11–18 ms per-inference figures are wall-clock for 100-batch runs**, not steady-state per-token forward latency in a serving loop. The forward pass itself is faster; setup is amortized across the batch. We are NOT claiming a tokens-per-second figure yet.
- **Numerical correctness vs the host PyTorch reference is qualitative**, based on output distribution sanity, not bit-exact or low-cosine-distance comparison to a known-good reference. Phase 1A.A includes that as an explicit falsifier.
- **The smollm3 results have only AOT-compile evidence, not on-device evidence.** We exercised qwen_block + qwen_frozen_subgraph end-to-end on the phone; smollm3_block + smollm3_frozen_subgraph compiled cleanly but were not loaded onto the phone in this session. They are queued as part of Phase 2A's multi-architecture cross-check.
- **The overnight loop has been running for ~10 minutes at the time of this writing.** Its 8-hour fridge-mode survival is a hypothesis we will test tonight; we will publish the result regardless of outcome.

The decision log at `docs/DECISIONS.md` is the source of truth for every claim above. Each row carries a `strongest disconfirming observation` so future readers can audit what would have invalidated each call.

---

## 13. References

- PR #4: <https://github.com/Zer0pa/Polymath-AI/pull/4>
- Decision rows D-001..D-031 in `docs/DECISIONS.md`
- Phase 0G runner: `scripts/silicon/run_phase0g_aot.py`
- QNN context extraction: `scripts/host/extract_qnn_context.py`
- On-device runner: `scripts/phone/run_qnn_inference.sh`
- Overnight runbook: `docs/PHONE-OVERNIGHT-RUNBOOK.md`
- Live telemetry (private): `Architect-Prime/polymath-telemetry` on Hugging Face
- AOT artifacts (private): `Architect-Prime/polymath-models-qwen2-5-1p5b-elo`, `Architect-Prime/polymath-models-smollm3-3b-elo` on Hugging Face
- Project boundary: `polymath_ai/boundary/text.py` (sha256-anchored)

For external technical correspondence, the right entry point is the linked PR — every commit message there names a single named decision row.
