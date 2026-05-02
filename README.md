# Polymath AI

Polymath AI ahead-of-time-compiles the 26-layer frozen middle of Qwen2.5-1.5B to a 2.3 GB Snapdragon SM8750 NPU context binary and runs it sustained on a consumer phone. **Phase 0G AOT compile** is closed (5/5 scopes ok with the QAIRT 2.44.0.260225 ↔ ai-edge-litert 2.1.4 matching pair). **Phase 1A on-device inference** is closed (proven end-to-end on a REDMAGIC 10 Pro+ Hexagon NPU via `qnn-net-run --retrieve_context` after extracting the embedded QNN context binary from the LiteRT `apply_plugin` wrapper). **Phase 1A.B sustained-load characterisation** is closed (22,850 inferences across 6 h 15 m at 100% rc=0, room ambient, no thermal throttling). **Phase 1A.A real-data ELO Stage-1 training** is next, ETA ~1 week of focused engineering.

## What This Is

Polymath AI is on-device-LLM continuous-pretraining infrastructure: a pipeline that trains the input/output edges of a 1.5-billion-parameter transformer on a host machine while delegating its frozen 26-layer middle to a consumer phone's neural-processing unit (NPU). The phone participates in shaping the model's weights, not just running them.

The training method is **ELO** (Efficient Layer-specific Optimization): train layer 0 + the language-modelling head; freeze layers 1..26 (the "frozen middle"); run that frozen middle on Hexagon NPU. ~16% of trainable parameters, ~7% of gradient FLOPs of full continual pretraining.

The target model is `Qwen/Qwen2.5-1.5B` (Apache 2.0). The reference handset is the **REDMAGIC 10 Pro+** (model NX789J, Snapdragon 8 Elite Gen 4 / SM8750, Hexagon V79 NPU, 16 GB LPDDR5X, active cooling fan, charge bypass). Architecture cross-check uses `HuggingFaceTB/SmolLM3-3B`.

This is research infrastructure. Per the project boundary (see "Boundary" support section after Repo Shape, and `polymath_ai/boundary/text.py:BOUNDARY_SHA256`): no regulatory certification claims; no clinical or human-subject use; no surveillance, biometric profiling, or identity inference; no model weights distributed without an explicit license attestation; no training on copyrighted material without an explicit corpus-license decomposition; no production deployment without a falsifier-traced acceptance gate.

## Pipeline Mechanics

End-to-end on-device-LLM-training pipeline as a falsifier-traced workflow:

| Stage | Where it runs | What it produces |
|---|---|---|
| Stage 0 — substrate | host (any platform) | hash-chained audit log, falsifier registry, boundary scanner, scheduler with per-SoC backend-confirmation locks, dispatch history, knowledge-graph-backed corpus-license store |
| Stage 1 — model preparation | host | ELO freeze plan applied to `Qwen/Qwen2.5-1.5B`: train layer 0 + LM head, freeze layers 1..26, auto-untie tied embeddings if present |
| Stage 2 — AOT compile to Snapdragon SM8750 | Linux x86_64 host | per scope: PyTorch → `litert_torch.convert(...)` → MLIR → TFLite → `ai_edge_litert.aot.aot_compile(target=Qualcomm_SM8750)` → 2.3 GB QNN context binary embedded in an `apply_plugin`-format `.tflite` |
| Stage 3 — on-device deployment | host → phone (ADB) | `scripts/host/extract_qnn_context.py` extracts the QNN binary; `adb push` lands it on `/data/local/tmp/phase1a/`; QAIRT 2.44 aarch64-android subset under `/data/local/tmp/qairt-2.44/` |
| Stage 4 — on-device inference | phone (Hexagon NPU) | `qnn-net-run --retrieve_context <scope>.qnn.bin --backend libQnnHtp.so` loads via `libadsprpc.so` / `libcdsprpc.so`, executes on Hexagon V79, writes FP32 output |
| Stage 5 — sustained-load characterisation | phone (autonomous) | `scripts/phone/overnight_inference_v2.sh` runs detached (`nohup setsid`, PPID=1), writes hash-chained JSONL, auto-halts on temperature / battery / STOP-file |
| Stage 6 — ELO Stage-1 training | host + phone (round-trip per step) | **Phase 1A.A — next**: real tokenized input → host-side embedding lookup → frozen-middle forward on Hexagon → host-side backward + AdamW on layer 0 + LM head → measure tokens/hour |

Plug-replaceable at every stage. Per-SoC backend-confirmation locks gate routing decisions; named falsifiers gate phase closure.

## Key Metrics

| Metric | Value | Baseline |
|---|---|---|
| ON_DEVICE_INFERENCE_SUCCESS_RATE | 22,850 / 22,850 = 100% | 6 h 15 m sustained on REDMAGIC SM8750, FP32, room ambient |
| ELO_FROZEN_MIDDLE_P50_LATENCY_HEXAGON | 576 ms | Qwen2.5-1.5B layers 1..26 (2.3 GB QNN context binary), seq 1×16, FP32 |
| AOT_COMPILE_SCOPES_PASSING | 5 / 5 | QAIRT 2.44.0.260225 + ai-edge-litert 2.1.4 (matching pair) |
| SUSTAINED_LOAD_BATTERY_TEMP_PEAK | 32.0 °C | room ambient, AC connected, 60-s-sleep duty cycle, no fridge cooling |

> Source: live-PR-#4 artefacts under `runtime/reports/export_probe/2026-05-02T014031Z_litert214_qairt244_FULL/` and `runtime/reports/phase1a/2026-05-02T1802Z-overnight-v2/`; cited in `docs/DECISIONS.md` rows D-030, D-031, D-032 (D-022..D-032 land on `main` when PR #4 merges).

## Repo Identity

| Field | Value |
|---|---|
| Architecture | ON_DEVICE_TRAINING_PIPELINE |
| Encoding | POLYMATH_ELO_CONTINUAL_PRETRAINING_V1 |

## Readiness

| Field | Value |
|---|---|
| Verdict | RESEARCH_SUBSTRATE_COMPLETE_PHASE_1A_PROVEN |
| Commit SHA | see current `main` HEAD |
| Confidence | scoped by per-row `strongest disconfirming observation` clauses in `docs/DECISIONS.md` |
| Source | `docs/DECISIONS.md` (canonical truth); `docs/EXECUTION-REPORT.md`; `PRD.md`; live PR #4 |

Open blockers (all engineering-time, not science-blocked): Phase 1A.A real-data ELO Stage-1 training experiment not yet run; corpus + tokenization + backward-path scaffolding pending. Visibility: PRIVATE — operator-controlled.

## What We Prove

- The 26-layer ELO frozen middle of `Qwen/Qwen2.5-1.5B` AOT-compiles to a 2.3 GB Qualcomm SM8750 context binary and executes on the Hexagon V79 NPU of the operator's REDMAGIC 10 Pro+. Wall-clock per-inference latency on the actual phone, after a warm mmap, is 576 ms (p50) / 811 ms (p95) / 817 ms (max).
- The same pipeline produces a 960 MB binary for `HuggingFaceTB/SmolLM3-3B`'s 30-layer frozen middle, demonstrating architecture portability across model families. AOT-compile-only at this stage; on-device deployment for SmolLM3 is queued for Phase 2B.
- Sustained-load reliability over 22,850 inferences across 6 h 15 m at 100% rc=0 and 100% out_size=98304 (correct 1×16×1536 FP32 output every time). Zero silent corruption events; no thermal throttling; no battery temperature above 32 °C.
- Output FP32 statistics from a zero-input forward pass through random-init weights match transformer hidden-state distribution theory: standard deviation grows from 1.14 over a single layer to 6.15 over 26 layers, mean stays near zero, all 24,576 outputs finite.
- A reusable "matching-pair" SDK pinning insight: ai-edge-litert 2.1.4 ↔ QAIRT 2.44.0.260225, with the QAIRT zip publicly downloadable from the URL embedded in LiteRT's Bazel build system. No Qualcomm Developer Network login required.
- A reusable "extract embedded QNN context binary" deployment path that bypasses the absent aarch64-android LiteRT runtime (D-019). The `apply_plugin` TFLite wrapper holds a single `DISPATCH_OP` whose `custom_options` flexbuffer carries `{bytecode_offset, bytecode_size, name="qnn_partition_0"}`; the QNN binary is appended verbatim. Tooling in `scripts/host/extract_qnn_context.py` (~80 lines).
- The reflex scheduler's per-SoC backend-confirmation lock was promoted only after on-device proof: `litert_qnn_sm8750.confirmed_for_socs = (("SM8750", 1.0),)`. The lock REMAINS for SM8650 / SM8550 / SM8450 / SM8350 / SA8295 / SA8255 — those SoCs continue to refuse routing until they are independently proven by their own decision rows.

## What We Don't Claim

- **No production model.** Polymath AI is research infrastructure. Phase 1A inference is proven; Phase 1A.A real-data ELO Stage-1 training is the next experiment. The 6 h 15 m run was inference-only on synthetic FP32-zeros input — a system-level reliability proof, not language modelling.
- **No clinical or human-subject use, no surveillance / biometric profiling / identity-inference application.** Per the boundary block. Off-limits regardless of how good the on-device numbers get.
- **No undisclosed weight distribution.** Every model weight redistributed by this project carries an explicit license-attestation row in the Phase 0C knowledge-graph store. Qwen2.5-1.5B is Apache 2.0; SmolLM3-3B is Apache 2.0; both attestations live with the artefact.
- **No unlicensed corpus use.** Phase 1B / 1C training corpora must pass the corpus-license decomposition gate (see `docs/CORPUS-SPEC.md`) before training proceeds. Defence / weapons / dual-use applications are excluded under operator policy.
- **The 576 ms p50 latency is steady-state inference, not steady-state training.** End-to-end ELO Stage-1 has additional host-side cost (tokenization, embedding lookup, layer-0 forward + backward, LM-head forward + backward, AdamW step) which is unmeasured at this point.
- **"100% success rate" applies to operational reliability** (rc=0, out_size=98304) over 22,850 inferences. It does NOT mean numerical bit-exact parity vs a host PyTorch reference; that comparison is an explicit Phase 1A.A falsifier (cosine similarity ≥ 0.99 on real tokens between host CPU and phone NPU).
- **The 25-hour unplugged battery-life extrapolation** is from a 2.5-hour observed segment at ~3.2 %/hour drain. A full 100% → 15% halt run has not been performed.
- **The "matching-pair" pattern is verified for SM8750 only.** Cross-SoC verification (SM8650 / SM8550) is Phase 2C.
- **The smollm3 compile artefacts have AOT-compile evidence only**, not on-device proof.
- **No production deployment without a falsifier-traced acceptance gate.** Per the boundary block. Productisation requires a separate programme not on the current roadmap.

## Verification Status

| Code | Check | Verdict |
|---|---|---|
| V_01 | First-ten README spine present in correct order: What This Is / Pipeline Mechanics / Key Metrics / Repo Identity / Readiness / What We Prove / What We Don't Claim / Verification Status / Proof Anchors / Repo Shape | PASS |
| V_02 | Lead sentence ≤ 30 words (currently 26) | PASS |
| V_03 | Key Metrics table has exactly 4 rows | PASS |
| V_04 | Proof Anchors ≤ 6 and every path resolves on GitHub `main` | PASS |
| V_05 | Boundary block sha256-anchored at `polymath_ai/boundary/text.py:BOUNDARY_SHA256`; boundary scanner CI-enabled | PASS |
| V_06 | `pytest tests/` returns 127 / 127 on Mac and Linux x86_64 pod | PASS |
| V_07 | Phase 0G AOT compile sweep: 5 / 5 scopes ok with QAIRT 2.44 + LiteRT 2.1.4 matching pair (D-030; PR #4) | PASS |
| V_08 | Phase 1A on-device inference proven on REDMAGIC SM8750 / Hexagon NPU (D-031; PR #4) | PASS |
| V_09 | Phase 1A.0 + 1A.B sustained-load: 22,850 inferences / 100% rc=0 / 100% out_size=98304 (D-032; PR #4) | PASS |
| V_10 | Decision-log monotone-append discipline preserved (D-001 → D-021 on `main`; D-022 → D-032 land on `main` when PR #4 merges) | PASS |

## Proof Anchors

Each path below is verified to resolve on GitHub `main` at the time this README was last updated.

| Path | State |
|---|---|
| `PRD.md` | VERIFIED |
| `RESISTANCE.md` | VERIFIED |
| `docs/DECISIONS.md` | VERIFIED |
| `docs/AUDIT-SPEC.md` | VERIFIED |
| `docs/EXECUTION-REPORT.md` | VERIFIED |
| `docs/FALSIFIERS.md` | VERIFIED |

## Repo Shape

| Field | Value |
|---|---|
| Proof Anchors | 6 |
| Modality Lanes | 1 (on-device-training) |
| Authority Source | `docs/DECISIONS.md` (canonical truth) |
| Canonical References | `polymath_ai/boundary/text.py` (BOUNDARY_TEXT, BOUNDARY_SHA256); `LICENSE`; `PRD.md` |
| Python Package | `polymath_ai` |
| Engineering Lane | `scripts/{host,phone,silicon,linux,termux}/` + `runtime/reports/` |

---

## Boundary

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

The block is verbatim, sha256-anchored at `polymath_ai/boundary/text.py:BOUNDARY_SHA256`. A boundary scanner with explicit forbidden-framing patterns runs in CI on every audit row, summary, and report. Drift between this string and any artifact carrying the boundary is a `boundary_violation` falsifier hit.

## Sibling Research Artefact — DM3

`Zer0pa/DM3` is a structural diagnostic on a closed Android aarch64 Rust binary running on the same operator handset (REDMAGIC 10 Pro / SM8750 / Adreno 830 / Hexagon V79). DM3 exercises the device's deterministic-runtime envelope and reports cross-platform ARM64 determinism (Claim τ); Polymath AI exercises the device's NPU-AOT-compile envelope and reports cross-handset Hexagon-binary execution (D-031, D-032). The two repos share the same boundary-block discipline, the same RESISTANCE.md anti-corruption doctrine (`fp-shapematchRE`, `fp-rushtoend`, `fp-NULLasout`, `fp-approvalseek`, `fp-flatteryasfreedom`), and the same "explicitly named falsifiers + decision-row append-only log" pattern. They are independent at runtime; no shared state, no shared dependencies. Cross-repository pointer: `Zer0pa/DM3` (visibility operator-controlled).

## Reproducer (90-minute clean-slate)

```bash
# Host (Linux x86_64)
python3.10 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip wheel
pip install "torch>=2.6" --index-url https://download.pytorch.org/whl/cpu
pip install "ai-edge-litert==2.1.4" "litert-torch" "transformers<5" "tokenizers<0.22" \
            safetensors "huggingface_hub<1.0"

# QAIRT 2.44 — public CDN URL embedded in LiteRT's Bazel build system
wget https://softwarecenter.qualcomm.com/api/download/software/sdks/Qualcomm_AI_Runtime_Community/All/2.44.0.260225/v2.44.0.260225.zip
unzip v2.44.0.260225.zip
source qairt/2.44.0.260225/bin/envsetup.sh

# AOT compile — emits 5 SM8750 context binaries in runtime/reports/export_probe/<ts>/
python scripts/silicon/run_phase0g_aot.py

# Extract the QNN context binary from the apply_plugin TFLite wrapper
python scripts/host/extract_qnn_context.py \
  --tflite runtime/reports/export_probe/<ts>/qnn_aot/qwen_frozen_subgraph/qwen_frozen_subgraph_Qualcomm_SM8750_apply_plugin.tflite \
  --out /tmp/qwen_frozen_subgraph.qnn.bin

# Push to phone via ADB
adb push /tmp/qwen_frozen_subgraph.qnn.bin /data/local/tmp/phase1a/

# Run on phone via qnn-net-run
adb shell sh /sdcard/Polymath/phase1a/run_qnn_inference.sh qwen_frozen_subgraph 10
```

## Operator runbooks

- `docs/PHONE-OVERNIGHT-RUNBOOK.md` (lands on `main` when PR #4 merges) — start the autonomous overnight inference chain; auto-detached from ADB; live HF telemetry; kill-switch documented.
- `docs/PHASE-0G-PLAN.md` — Phase 0G plan and the three viable AOT-compile paths.

## Read order for the next agent

If a fresh agent picks up this repo:

1. `RESISTANCE.md` — anti-corruption doctrine. Read first. Headspace.
2. `MODUS-OPERANDI.md` — multi-agent role chain; cross-workstream principles.
3. `PRD.md` — product requirements (the operator-authored Pre-PRD blueprint synthesis).
4. `docs/DECISIONS.md` — the decision log; canonical truth for every claim.
5. `docs/EXECUTION-REPORT.md` — current execution state.
6. Source: `polymath_ai/{boundary,audit,falsifiers,scheduler,elo,models,sync,kg}/` — substrate.

Once PR #4 lands on `main`, additional reading: `docs/REPORT-2026-05-02-comprehensive.md` (zero-context-friendly technical report) and `docs/ROADMAP-ETA-2026-05-02.md` (every upcoming phase with engineering ETAs).

## Provenance

- Initial commit: 2026-05-01.
- Phase 0A–0F closure: 2026-04-26 → 2026-05-01.
- Phase 0G closure (AOT compile to SM8750): 2026-05-02. D-030.
- Phase 1A closure (on-device inference proven): 2026-05-02. D-031.
- Phase 1A.0 + 1A.B closure (sustained-load characterisation): 2026-05-02. D-032.
- Operator: Architect-Prime, Zer0pa.
- Reference handset: REDMAGIC 10 Pro+ (NX789J), Snapdragon 8 Elite Gen 4 (SM8750), Hexagon V79 NPU.

## Cross-workstream principle

This workstream runs in parallel with `Zer0pa/Health`, `Zer0pa/Materials`, `Zer0pa/Energy`, and `Zer0pa/Synthetic-Biology`. Each is built end-to-end as an independent pipeline. **No substrate is shared at runtime.** Redundancy across workstreams is a deliberate asset.

**Fork-and-own is explicitly permitted.** Implementation patterns, falsifier-registry shapes, audit-log schemas, plug-replaceability harnesses, KG-node taxonomies, code structures, and architectural details may be copied between workstreams freely. **What is rejected is runtime co-dependency** — no shared running services, no shared databases or corpora, no shared git imports.

## License

Project source code: MIT.
Models: per upstream model card (`Qwen/Qwen2.5-1.5B`: Apache 2.0; `HuggingFaceTB/SmolLM3-3B`: Apache 2.0).
SDK: QAIRT 2.44.0.260225 under Qualcomm Community redistributable EULA.
Datasets: per upstream data card.
