# Polymath AI — Roadmap with ETAs (2026-05-02)

**State as of this writing:** Phase 0 closed (0A–0G). Phase 1A on-device proof closed (1A.0 + 1A.B). Phase 1A.A (real-data ELO Stage-1 training) is the next active phase.

**ETAs are engineering effort estimates** assuming one focused engineer. They include implementation + falsifier evaluation + documentation, but exclude calendar slip from waiting on third parties (e.g., new QAIRT releases, new handsets, dataset acquisition).

---

## Where we are on the roadmap

```
Phase 0A   substrate                      ✓ closed
Phase 0B   ELO trainer + freeze policy    ✓ closed
Phase 0C   knowledge graph (corpus license) ✓ closed
Phase 0D   reflex scheduler                ✓ closed
Phase 0E   host-mediated ELO smoke         ✓ closed
Phase 0F   tokenizer fertility audit       ✓ closed
Phase 0G   AOT compile to SM8750           ✓ closed (D-030, 5/5 scopes ok)
─────────  Phase 0 complete  ─────────────
Phase 1A.0 overnight chain                  ✓ closed (D-031, 22,850 inferences)
Phase 1A.B steady-state benchmark           ✓ closed (D-032, p50 = 576 ms / 26 layers)
Phase 1A.A real-data ELO Stage-1            ▶ NEXT
Phase 1A.C scheduler wire-up                ▶ NEXT (parallel)
─────────  Phase 1A complete after 1A.A + 1A.C  ─────
Phase 1B   multilingual ELO                  pending
Phase 1C   multi-domain ELO                  pending
─────────  Phase 1 complete after 1B + 1C  ───────
Phase 2A   quantization study                planned
Phase 2B   multi-handset compatibility       planned
Phase 2C   cross-SoC AOT                     planned
Phase 3A   distributed Polymath              research direction (6–12 months)
```

---

## ETA per upcoming phase

### Phase 1A.A — real-data ELO Stage-1 training experiment

**Goal:** train Qwen2.5-1.5B layer 0 + LM head on host while running the frozen middle (layers 1..26) on the phone's Hexagon NPU. Real tokenized input, real loss, real gradient flow.

**Engineering steps:**
1. Real input pipeline: tokenizer → embedding lookup (host) → hidden states for layer 0 → push to phone as `input.bin` (1 day)
2. Backward through the frozen middle: option-A is forward-only on phone, recompute backward host-side (1 day); option-B is AOT-compile a backward subgraph too (3–4 days). Start with option-A (1 day total).
3. Loss + AdamW optimizer on the host: minor wiring on existing `polymath_ai.elo.trainer` (0.5 day)
4. Tokens/hour benchmarking + falsifier: cosine-sim ≥ 0.99 between host CPU reference and phone NPU output on real tokens (1 day)
5. Fix the HF-push bug (broken since v1 iter 530, argv-limit + inline-payload issue): switch to streaming-base64-direct-to-file, no shell variable; or move to per-iteration delta uploads (0.5 day)
6. Documentation + decision row D-033 (0.5 day)

**ETA: 5–6 working days** (~1 week) of focused engineering.

**Could-shorten:** if the host-side backward recompute is acceptably cheap, we skip option-B. Likely.

**Could-stretch:** if option-A backward turns out >5× phone-forward latency, we have to commit to option-B, adding ~3 days.

### Phase 1A.C — scheduler wire-up

**Goal:** make `ReflexScheduler.decide(...) == "litert_qnn_sm8750"` actually invoke `qnn-net-run` on the phone, instead of just returning the backend ID. Closes the loop from the falsifier-traced scheduler decision to the on-device call.

**Engineering steps:**
1. Define the `BackendDispatcher` interface that takes a `Decision` and an input tensor, returns an output tensor (0.5 day)
2. Implement `LiteRtQnnSm8750Dispatcher` that pushes input.bin via ADB, runs `qnn-net-run`, pulls output.bin back (1 day)
3. Wire into existing `ReflexScheduler.decide_and_run()` (or equivalent) (0.5 day)
4. Tests: a synthetic op_key → decide → dispatch round-trip with real Qwen layer 0 (0.5 day)

**ETA: 2–3 working days.** Can run in parallel with 1A.A.

### Phase 1B — multilingual ELO

**Goal:** run an ELO Stage-1 experiment on the post-tokenizer-fertility-audit language mix (33% English + 12 others, see D-017). Per-language perplexity tracked through training.

**Engineering steps:**
1. Multilingual corpus assembly: ~100 GB across 13 languages, license-attested (corpus-license decomposition gate from Phase 0C). This is mostly data engineering, not novel code. (3 days)
2. Per-language eval pipeline: reuse existing `transformers` perplexity eval, instrument for per-language buckets (1 day)
3. Run the experiment: ELO Stage-1 across mixed-language batches, measure per-language perplexity at intervals. Minimum useful run is ~1000 ELO steps (~10 hours of phone-NPU compute given current 576 ms/step + host-side overhead). Multiple runs with different mix ratios. (3–4 days of compute, mostly unattended)
4. Analysis + decision row D-034 (1 day)

**ETA: 7–9 working days** (~1.5–2 weeks). Some calendar overlap possible while compute runs unattended.

### Phase 1C — multi-domain ELO

**Goal:** add a domain mix (web, code, scientific, legal) to the multilingual mix. Each domain carries an explicit corpus-license attestation that gates training on it.

**Engineering steps:**
1. Domain corpus assembly with license attestations: web (Common Crawl + license-cleared subset), code (The Stack v2 with permissive-only filter), scientific (S2ORC license-cleared subset), legal (jurisdictional samples from public records). (5 days; this is the heaviest data-engineering phase)
2. Knowledge-graph corpus-license decomposition gate: each domain proceeds only after its license decomposition is signed off (1 day)
3. Mixed-domain ELO experiment: similar shape to 1B but with domain bucketing as well as language bucketing (3–4 days of compute)
4. Per-domain eval suite: domain-specific benchmarks (HumanEval / MBPP for code, MMLU subsets for scientific, ...) (2 days)
5. Analysis + decision row D-035 (1 day)

**ETA: 12–14 working days** (~2.5–3 weeks). Calendar overlap with 1B's compute runs is possible.

### Phase 2A — quantization study

**Goal:** FP32 → FP16 → INT8 variants of the frozen middle. For each: redo the AOT sweep, redo the on-device verdict, characterise accuracy degradation vs binary size + inference latency.

**Engineering steps:**
1. FP16 path: ai-edge-litert's AOT compile already supports FP16 via a flag. Re-run sweep, push to phone, benchmark. (1 day)
2. INT8 path: needs Quantization-Aware Training (QAT) or post-training quantization with calibration. The latter is faster — feed ~1000 calibration examples through the frozen middle, learn per-tensor scales, emit INT8 binary. (3 days)
3. Accuracy degradation eval: use Phase 1B's per-language perplexity suite as the reference. FP16 expected to lose <1% perplexity; INT8 expected to lose 2–8% depending on calibration. (2 days)
4. Latency / size matrix: reproduce Phase 1A.B's 576 ms/inference number for each precision. INT8 expected at ~150 ms (4× speedup, ~600 MB binary instead of 2.3 GB). (1 day)
5. Decision row D-036 (0.5 day)

**ETA: 7–8 working days** (~1.5 weeks).

### Phase 2B — multi-handset compatibility

**Goal:** run the same Phase 0G + 1A pipeline on Samsung S25 Ultra, OnePlus 13, and any other SM8750-bearing handset. Identify OEM-specific blockers.

**Engineering steps:**
1. Acquire 1–2 additional SM8750 handsets (calendar-blocked on procurement; not engineering effort)
2. Reproducer dry-run on each: same QAIRT 2.44 + same QNN binary + same `qnn-net-run` invocation. Expect: same 576 ms/inference, same 100% success rate. (0.5 day per handset)
3. Identify OEM divergences: charging policy quirks, vendor kernel patches that change `/sys/class/thermal/` topology, Game-Mode-equivalent power-management policies. (1 day per handset)
4. Decision row D-037 + multi-handset compatibility matrix (1 day)

**ETA: 3–4 working days per handset, plus calendar slip on procurement.** If 2 handsets, ~1 week + procurement.

### Phase 2C — cross-SoC AOT

**Goal:** target SM8650 (8 Gen 3, 2024), SM8550 (8 Gen 2, 2023). Characterise the QnnSystem version matrix vs ai-edge-litert versions. Identify the matching-pair for each SoC.

**Engineering steps:**
1. For each SoC: identify the LiteRT version that pins the right QAIRT (likely 2.1.3 ↔ 2.43, 2.1.2 ↔ 2.42, ...). Re-run the Phase 0G sweep with each pair. (1 day per SoC)
2. Document the matching-pair table for community use (1 day)
3. On-device verification on actual handsets (operator has SM8650 access? unclear; could need procurement) (1 day per SoC)
4. Decision row D-038 + cross-SoC compatibility matrix (1 day)

**ETA: 5–6 working days** if operator has the SoC handsets. Add procurement slip otherwise.

### Phase 3A — distributed Polymath

**Goal:** the longest-horizon thread. A model that is expert across many domains and languages, distributed across many handsets. Each handset gets a copy of the model that is biased by the local data it has seen. An aggregator collects per-device updates and produces a global model that subsumes them.

This phase is **a 6–12 month research program**, not a near-term engineering commitment. Prerequisites (all done): Phase 1A.A proves on-device training works at all; Phase 1B–1C prove the model can absorb diverse training data without forgetting; Phase 2A–2C prove the deployment story is portable across hardware.

The actual research questions:
- Does ELO frozen-middle structure compose under federated aggregation, when only the trainable strips are averaged?
- Does gradient inversion leak training data through ELO updates? (Privacy / sovereignty question.)
- Can per-device biasing produce locally-useful specialisation while still aggregating to a coherent global model?
- What's the right aggregator scheduling (synchronous, asynchronous, gossip-based)?

**ETA: 6–12 months minimum.** Multiple papers' worth of work.

---

## Cumulative timeline

| Milestone | Working days | Calendar (assuming ~3 days/week of focused effort) |
|---|---:|---:|
| Phase 1A.A complete | 5–6 | ~2 weeks |
| Phase 1A.C complete (parallel with A) | +0 (parallel) | same |
| **Phase 1A entirely closed** | 5–6 | **~2 weeks from now (end of May 2026)** |
| Phase 1B complete | +7–9 | ~3 weeks more |
| Phase 1C complete | +12–14 | ~5 weeks more |
| **Phase 1 entirely closed (multilingual + multi-domain ELO proven on phone)** | 24–29 | **~10 weeks from now (mid-July 2026)** |
| Phase 2A (quantization) | +7–8 | ~3 weeks more |
| Phase 2B (multi-handset) | +3–4 per handset + procurement | ~3–4 weeks more |
| Phase 2C (cross-SoC) | +5–6 | ~2 weeks more |
| **Phase 2 entirely closed** | 39–47 | **~5 months from now (Oct 2026)** |
| Phase 3A (distributed Polymath) | 6–12 months | research direction; not on critical path |

Calendar dates assume sustained engineering focus and no major SDK churn (a new QAIRT release that changes the matching-pair would add 1–2 weeks of recompile + reverification). Hardware-procurement slips for Phases 2B / 2C are not in this estimate.

---

## What's not on the roadmap (deliberately)

- **No commercial product.** This is research infrastructure. Productisation requires a distinct programme (compliance review, deployment certification, customer-acquisition motion). The boundary block forbids "deployment to production without a falsifier-traced acceptance gate" — research artifacts only.
- **No clinical / regulated use.** Same boundary clause.
- **No surveillance / biometric / identity-inference applications.** Same boundary clause.
- **No model weights distributed without license attestation.** Phase 0C's knowledge-graph store enforces this.
- **No comparison study against LoRA / IA³ / prefix tuning** as an explicit phase, but it should happen opportunistically during Phase 1B as a sanity check on whether ELO is competitive.

---

## Risk factors that could shift these ETAs

1. **QAIRT release churn.** A new QAIRT minor (2.45, 2.46, ...) that breaks the LiteRT 2.1.4 matching pair would require either (a) waiting for a new ai-edge-litert wheel that re-pins, or (b) source-rebuilding the LiteRT QNN plugin against the new QAIRT. ~1–2 weeks of delay if it happens.
2. **Hardware procurement.** Phase 2B / 2C need additional handsets. Procurement is calendar-bound, not engineering-bound.
3. **Corpus licensing.** Phase 1B / 1C's corpus assembly may surface license edge cases that require legal review before training. ~1–4 weeks of delay if it happens.
4. **Phone hardware reliability.** If the REDMAGIC handset develops issues over weeks of sustained NPU load (e.g., USB-C wear, battery degradation, fan failure), we lose the reference handset until repair / replace. Unlikely but possible.

None of these are showstoppers; they're calendar slip risks.

---

*This roadmap is a snapshot. The decision log at `docs/DECISIONS.md` is the canonical source of truth; if any ETA in this document conflicts with a future D-row, the D-row wins.*
