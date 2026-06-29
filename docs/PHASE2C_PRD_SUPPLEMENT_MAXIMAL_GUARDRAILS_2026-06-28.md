# Phase 2-C PRD Supplement: Maximal Guardrails, Audit Gates, and NPU-Readiness

Date: 2026-06-28
Status: Binding supplement to `PHASE2C_PRD_MAXIMAL_2026-06-28.md`
Authority runtime: REDMAGIC NX789J / Snapdragon SM8750 / Termux
Scope: Phase 2-C science-hardening and NPU-readiness before Phase 3

## 0. Supplement Purpose

The Phase 2-C PRD is correctly ambitious. This supplement makes it harder to misread ambition as permission to weaken the authority contract.

Phase 2-C must not become a beautiful research detour that forgets what Phase 2 is responsible for:

```text
Phase 1 PQA1 -> Phase 2 binary polar packet substrate -> Phase 3 NPU consumption
```

The promoted Phase 2-B native result may be strong, but it still needs adversarial certification. Phase 2-C must audit, harden, and extend it. It must not silently replace verified machinery with speculative machinery before falsification.

## 1. Culture Lock

Good is the enemy of great.

The top acceptance gate is sovereign.

Objective substitution is failure.

A green metric does not license closure if the governing objective remains unresolved.

No reward-hacking by changing what Phase 2 means after seeing bottlenecks.

No process theater. GPD exists to force implementation, measurement, falsification, and continuation decisions.

We are falsification-first because this is frontier work, not because we are timid.

Alien mechanisms are welcome. They must survive harsher evidence than conventional mechanisms.

Do not move to Phase 3 until Phase 2-C proves that the emitted substrate is correct, reproducible, fast, and physically shaped for Phase 3 consumption.

## 2. Current Evidence Posture

The reported Phase 2-B status is:

```text
phase2b_native_maximal_closure_pass
100k: 462,598 real tokens/sec, 15.038x Python
1M: 598,675 real tokens/sec, 32.331x Python
Comet: aef6f2d8fca649f48cf8694565889e8a
Authority artifacts: runtime/reports/polar_phase2_native_closure/2026-06-28T105404Z-cached-1M
```

This is potentially excellent. It is not self-certifying.

The string `cached-1M` is an audit trigger. It may be legitimate, but Phase 2-C must prove what was cached, what was recomputed, and what timing envelope the promoted throughput actually measured.

Phase 2-C starts by auditing this claim before adding new science.

## 3. Phase 2-C Terminal Objective

Phase 2-C closes only when all are true:

1. The Phase 2-B `cached-1M` result is independently audited and classified.
2. The best native path is reproducible from source, not merely recorded in GPD state.
3. The promoted output contract remains compatible with Phase 2-B `PJP1` until a Phase 3 preflight proves a replacement is consumable.
4. Real-corpus/token-diversity performance is measured, not inferred from the 86-token stress corpus.
5. NPU-readiness is tested through concrete layout, alignment, zero-copy, and reader-preflight evidence.
6. Any new mathematical substrate, including SRHT or Lorenz/reservoir projection, is treated as a non-promoted comparison arm until it beats the incumbent on correctness, information retention, and Phase 3 usefulness.
7. Comet logging is complete and safe.
8. GPD state points to inspected artifacts, not unexamined labels.

## 4. Non-Negotiable First Gate: Cached-1M Authority Audit

Before implementing BLAKE3, SRHT, Arrow, Lorenz projection, or any new format, perform the `cached-1M` audit.

Required questions:

- Was the 1M `PJP1` output recomputed by the native binary during the claimed run?
- If cached data was used, which stages were cached: token projection, pooled projection, packet file, source scan, verification, Comet upload, or all of the above?
- Does `598,675 real tokens/sec` measure full `PQA1 -> PJP1` transformation or a cache-assisted fast path?
- What command produced the promoted 1M metric?
- What binary SHA produced it?
- What source SHA produced the binary?
- What raw output hash was produced?
- Is there a matching Comet experiment with the same numbers, command, binary SHA, and report root?
- Can the 100k promoted result be rerun from cold state within reasonable time and land within 10% of the recorded metric?

Required artifacts:

- `phase2c_cached_1m_audit_report.md`
- `phase2c_cached_1m_provenance.json`
- `phase2c_promoted_metric_reconstruction.json`
- `phase2c_cold_100k_reproduction_report.json`

Status rule:

If the cached audit cannot prove the promoted metric, Phase 2-C must downgrade the prior result to:

```text
phase2b_native_cached_fastpath_pass_reproduction_required
```

That is not failure. It is truth.

## 5. PJP1 Remains The Authority Contract Until Replaced By Evidence

The Phase 2-C PRD proposes Arrow IPC streaming/ring output. This may be the correct Phase 3 substrate, but it cannot silently replace `PJP1`.

Rules:

- `PJP1` remains the canonical audit artifact.
- Arrow/ring output begins as a Phase 3-readiness sidecar.
- Phase 2-C may promote Arrow/ring only if a Phase 3 preflight reader proves direct consumption advantage.
- If Arrow/ring is promoted, the final handoff must include a lossless `PJP1 <-> Arrow/ring` equivalence report.

Required artifacts:

- `phase2c_pjp1_authority_continuity_report.json`
- `phase2c_arrow_sidecar_equivalence_report.json`
- `phase2c_pjp1_to_arrow_roundtrip_report.json`

Pass rule:

No output format replacement is valid unless the old and new formats agree semantically on the same packets.

## 6. NPU-Readiness Is A Gate, Not A Vibe

Phase 2 exists to feed Phase 3. A correct file is not necessarily an efficient NPU substrate.

Phase 2-C must produce a Phase 3 preflight package that answers:

- What exact memory layout will Phase 3 read?
- Is it aligned for the target runtime?
- Is it byte-addressable without CPU unpacking?
- Does QNN/HTP expect `uint8`, `int8`, `uint16`, `float16`, or another shape?
- Are bitpacked 256-bit vectors actually useful to the next runtime, or will the app/Phase 3 immediately unpack them?
- Can the reader mmap or shared-map the batches without copying?
- What is the batch shape Phase 3 sees?
- Does the layout preserve packet boundaries, role masks, target masks, and pooled answer codes?

Minimum Phase 3 preflight:

1. A tiny native reader that maps the proposed sidecar format.
2. A simulated Phase 3 consumer that reads batches in the exact order expected by NPU staging.
3. A copy-count report: zero-copy, one-copy, or multi-copy.
4. An alignment report for every large buffer.
5. A throughput report for read/stage without projection.

Required artifacts:

- `phase2c_phase3_preflight_reader_report.json`
- `phase2c_npu_layout_contract.md`
- `phase2c_copy_count_report.json`
- `phase2c_alignment_report.json`
- `phase2c_phase3_staging_throughput_report.json`

Nonclaim:

This is not an NPU/HTP claim. It is an NPU-readiness preflight.

## 7. Token Diversity Is The Real Performance Falsifier

The 86-unique-token stress corpus is useful but dangerously flattering. It rewards token projection cache behavior that may not survive real training material.

Phase 2-C must treat throughput on low-diversity stress data as a lower-level engineering result, not production truth.

Required diversity ladder:

- 86 unique token IDs
- 1,000 unique token IDs
- 10,000 unique token IDs
- 50,000 unique token IDs
- 100,000 unique token IDs, if available
- real training-material sample, if the corpus workstream can provide it

For each rung:

- source records;
- real tokens;
- unique token IDs;
- token projection cache hit rate;
- answer span cache hit rate;
- pooled projection cache hit rate;
- real tokens/sec;
- packet/sec;
- output MB/sec;
- memory high-water;
- thermal before/after;
- correctness sample count.

Required artifacts:

- `phase2c_token_diversity_sweep.json`
- `phase2c_cache_hit_rate_report.json`
- `phase2c_real_corpus_proxy_report.md`

Pass rule:

The final Phase 2-C throughput claim must be stated separately for stress corpus and high-diversity corpus. Do not average them. Do not let the stress result stand in for production.

## 8. BLAKE3 Adoption Must Preserve Identity Compatibility

BLAKE3 is a good candidate for packet checksums and internal fast hashing. It must not break existing artifact identity.

Rules:

- Keep SHA-256 for external artifact identity where Phase 1/Phase 2-B reports already use SHA-256.
- Add BLAKE3 as an additional fast hash or packet checksum where measured useful.
- Do not replace all SHA-256 fields in a way that breaks existing manifests, Comet comparison, or GPD traceability.
- Measure BLAKE3 on REDMAGIC for the actual payload sizes used here. Do not rely on desktop or unrelated benchmark ratios.

Required artifacts:

- `phase2c_blake3_microbench_redmagic.json`
- `phase2c_hash_identity_compatibility_report.md`
- `phase2c_dual_hash_manifest.json`

Pass rule:

Promote BLAKE3 only for lanes where REDMAGIC measurement beats the incumbent and identity compatibility is preserved.

## 9. SRHT Must Not Corrupt The Promoted Contract

SRHT for pooled-answer projection is plausible. It is not automatically equivalent to dense Rademacher.

Rules:

- Dense Rademacher remains the incumbent promoted contract.
- SRHT begins as a comparison arm.
- If SRHT is only used for pooled targets while input token polar bits remain dense Rademacher, the output is a hybrid representation and must be labeled as such.
- Hybrid output cannot be called the same `PJP1` semantic contract unless downstream semantics are explicitly updated.

Required comparisons:

- dense-vs-SRHT pooled target Hamming agreement;
- answer-class separability;
- correlation with Gemma embedding cosine;
- collision rate;
- margin distribution;
- Phase 3 layout impact;
- speedup under high-diversity token load.

Required artifacts:

- `phase2c_srht_comparison_arm_report.json`
- `phase2c_hybrid_projection_semantics.md`
- `phase2c_dense_vs_srht_geometry_report.json`

Pass rule:

SRHT may be promoted only if it improves speed without weakening target semantics, oracle agreement, or Phase 3 utility.

## 10. Lorenz/Reservoir Projection Is Science, Not A JL Claim

The Lorenz-seeded/reservoir projection idea is worth testing. It must not be described as retaining JL guarantees unless a proof or empirical substitute is supplied.

Rules:

- Treat Lorenz/reservoir projection as a non-promoted science arm.
- Do not call it JL unless the report proves the relevant distance-preservation behavior.
- Compare it against dense Rademacher and SRHT on geometry and downstream proxy utility.
- The burden of proof is higher because it is alien.

Required artifacts:

- `phase2c_lorenz_projection_science_arm.md`
- `phase2c_lorenz_distance_preservation_report.json`
- `phase2c_lorenz_vs_rademacher_falsifier.json`

Promotion rule:

Lorenz/reservoir projection can only become a future promoted contract after outperforming the incumbent on information retention and Phase 3 usefulness without hiding behind narrative novelty.

## 11. Information Bottleneck k-Sweep Must Use Real Labels Or Honest Proxies

The PRD correctly asks whether `k=256` is scientifically justified. The supplement tightens the method.

Rules:

- If real training labels/objectives are unavailable, label the sweep as proxy-only.
- Do not claim answer predictability from token-pair cosine alone.
- Include task-relevant separability: question-vs-answer, answer-active-vs-nonanswer, record-local target discrimination.
- Include memory and Phase 3 cost for each `k`.

Required `k` values:

```text
64, 128, 192, 256, 320, 512
```

Optional:

```text
768, 853
```

Required artifacts:

- `phase2c_ib_k_sweep_report.json`
- `phase2c_k_memory_cost_report.json`
- `phase2c_k_phase3_cost_report.md`
- `phase2c_proxy_label_limitations.md`

Promotion rule:

Keep `k=256` unless a different `k` wins on information retention, collision behavior, memory, and Phase 3 cost. Do not promote a bigger `k` merely because it looks more expressive.

## 12. Profiler Integrity

Phase 2-C must not disable profiling at the exact scale where we need truth.

Required:

- profiled 100k run;
- profiled 1M run, accepting up to 5% overhead;
- stage timings for read, seal, token projection, pooled projection, hashing, bitpack, write, flush, verify;
- worker-sum and wall-time separated;
- thread-count sweep;
- thermal samples during run;
- memory high-water from the native process, not only Python runner.

Required artifacts:

- `phase2c_stage_timing_100k.json`
- `phase2c_stage_timing_1M.json`
- `phase2c_thread_sweep_report.json`
- `phase2c_thermal_trace.json`
- `phase2c_native_memory_report.json`
- `phase2c_roofline_report.md`

Pass rule:

No "maximal" claim without profiled 1M evidence.

## 13. Verifier Expansion

Phase 2-C verification must exceed Phase 2-B.

Required:

- full section parity against incumbent for smoke and 10k where applicable;
- 100k stratified oracle sampling;
- 1M stratified oracle sampling;
- packet samples from beginning, middle, end, and random positions;
- collision falsifier;
- margin distribution;
- Hamming geometry statistics;
- output format roundtrip;
- Comet asset audit;
- source snapshot audit.

Required artifacts:

- `phase2c_verifier_matrix.json`
- `phase2c_stratified_oracle_100k.json`
- `phase2c_stratified_oracle_1M.json`
- `phase2c_collision_falsifier.json`
- `phase2c_margin_distribution.json`
- `phase2c_hamming_geometry_report.json`

Pass rule:

Any verifier that says "sampled" must state sample count and selection policy.

## 14. GPD And State Discipline

GPD state repair is not a substitute for runtime evidence.

Rules:

- GPD may record a pass only after artifact inspection.
- Every promoted state line must point to report root, Comet experiment, binary SHA, source SHA, command, and output hash.
- If Mac `.gpd` and phone `GPD` diverge, report the divergence. Do not pretend they are reconciled.

Required artifacts:

- `phase2c_gpd_state_binding_report.md`
- `phase2c_mac_phone_state_reconciliation.md`

## 15. Terminal Status Vocabulary

Only these statuses are valid:

- `phase2c_maximal_pass`
- `phase2c_engineering_pass_science_open`
- `phase2c_npu_readiness_blocked`
- `phase2c_cached_metric_reproduction_required`
- `phase2c_correctness_pass_perf_failed`
- `phase2c_science_arm_inconclusive`
- `phase2c_blocked`
- `phase2c_failed`

Do not emit `phase2c_maximal_pass` unless:

- cached-1M audit passes;
- cold 100k reproduction passes;
- 1M profiled run passes;
- token diversity sweep passes;
- NPU-readiness preflight passes;
- verifier expansion passes;
- Comet passes;
- artifact hygiene passes;
- Phase 3 handoff contract is complete.

## 16. Final Report Opening

The final `ENGINEERING_REPORT.md` must open with:

```text
Status: phase2c_maximal_pass | phase2c_engineering_pass_science_open | phase2c_npu_readiness_blocked | phase2c_cached_metric_reproduction_required | phase2c_correctness_pass_perf_failed | phase2c_science_arm_inconclusive | phase2c_blocked | phase2c_failed
Report root: runtime/reports/polar_phase2c/<UTC>/
Mirror: /sdcard/Download/polymath/polar_phase2c/<UTC>/
Comet experiment(s): <URL or blocked evidence>
Authority runtime: REDMAGIC NX789J / Snapdragon SM8750 / Termux
Promoted input: PQA1
Promoted audit output: PJP1
Promoted sidecar output: none | Arrow/ring
Projection status: dense_rademacher_incumbent | srht_promoted | lorenz_nonpromoted | other
k status: k256_confirmed | k_changed_to_<N> | proxy_only_no_change
Corpus status: stress_only | diversity_sweep | real_corpus_sample
NPU-readiness: pass | blocked | not_attempted
Nonclaims: no NPU execution, no GPU optimizer, no learning, no model quality movement, no megakernel
```

## 17. Overnight Execution Order

Use this order. Do not start with the most interesting science arm.

1. Read PRD and supplement.
2. Audit cached 1M result.
3. Reproduce cold 100k.
4. Restore Comet if needed.
5. Profile 100k and 1M.
6. Run token diversity sweep.
7. Build NPU-readiness preflight.
8. Run verifier expansion.
9. Only then run BLAKE3/SRHT/Arrow/Lorenz science arms.
10. Decide promotions with falsification matrix.
11. Write Phase 3 handoff contract.
12. Update GPD state only after artifacts exist.

## 18. Final Instruction

The goal is not to make Phase 2-C sound revolutionary.

The goal is to make Phase 2-C impossible to dismiss.

If the alien mechanism wins, prove it.

If the conservative incumbent wins, keep it.

If the NPU cannot consume the new layout efficiently, say so before Phase 3 inherits a bad substrate.

If the cached 1M metric is not what it appears to be, downgrade it.

Truth is the acceleration path.
