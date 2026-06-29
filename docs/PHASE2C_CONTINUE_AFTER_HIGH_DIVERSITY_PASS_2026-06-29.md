# Phase 2-C Continuation: After High-Diversity Pass

Date: 2026-06-29
Authority runtime: REDMAGIC NX789J / Snapdragon SM8750 / Termux
Purpose: Continue Phase 2-C as far as possible before the only remaining blocker is real training material.

## Current Verified Position

The previous `phase2c_correctness_pass_perf_failed` blocker has been cleared for the requested gate.

Latest high-diversity report:

```text
/sdcard/Download/polymath/polar_phase2c/2026-06-29Tphase2c-high-diversity-opt/
```

Key result:

```text
50k unique-token rung: 347,915 real tok/sec, above 200,000 floor
100k unique-token rung: 271,713 real tok/sec, above 200,000 floor
Comet: https://www.comet.com/zer0pa/mobile-polymath-ai-training/2f4042f5f24a4578bc4b62dfd62f85cd
PJP1 contract preserved
PJP1 readback passed
PJP1 section parity passed after timestamped header
```

Optimization:

```text
Exact dense Rademacher input-token projection-cache construction now uses a single-token k4 NEON kernel sharded across 8 threads.
```

This is a real engineering advance. It is not Phase 2-C maximal pass.

## User Directive

Do not move to Phase 3.

Do not claim Phase 3 handoff.

Do not stop merely because the high-diversity gate passed.

Push Phase 2-C engineering as far as possible under the PRD and supplement until the only defensible remaining blocker is the absence of real training material.

No interim reporting. Continue end-to-end and return only with a real terminal status.

## Binding Culture

Good is the enemy of great.

The top acceptance gate is sovereign.

Objective substitution is failure.

Do not turn a solved subgate into final closure.

Do not replace the Phase 2-C PRD with a narrower success story.

Do not promote science arms by narrative.

No process theater. Every artifact must force implementation, measurement, falsification, or a continuation decision.

## Next Execution Order

You have already cleared:

1. cached-1M audit;
2. cold 100k reproduction;
3. Comet logging;
4. profiled 100k and 1M;
5. high-diversity 50k and 100k performance floor.

Now continue with all remaining Phase 2-C gates that can be done without real corpus:

### A. Verifier Expansion

Run and produce:

- `phase2c_stratified_oracle_100k.json`
- `phase2c_stratified_oracle_1M.json`
- `phase2c_collision_falsifier.json`
- `phase2c_margin_distribution.json`
- `phase2c_hamming_geometry_report.json`
- `phase2c_verifier_matrix.json`

Rules:

- state sample counts and selection policy;
- sample beginning, middle, end, and random packets;
- preserve PJP1 as the authority audit artifact;
- fail honestly if any oracle or geometry check is weak.

### B. NPU-Readiness Preflight, Not Phase 3

This is not an NPU execution claim and not a Phase 3 handoff.

Run and produce:

- `phase2c_npu_layout_contract.md`
- `phase2c_phase3_preflight_reader_report.json`
- `phase2c_phase3_staging_throughput_report.json`
- `phase2c_copy_count_report.json`
- `phase2c_alignment_report.json`

Required questions:

- Can the planned substrate be read without CPU unpacking?
- Are buffers aligned?
- What batch shape does a Phase 3 consumer see?
- How many copies are required?
- Is PJP1 sufficient as-is, or is Arrow/ring sidecar still needed?
- If Arrow/ring is attempted, prove equivalence to PJP1 before promotion.

### C. BLAKE3 And Hash Identity

Run and produce:

- `phase2c_blake3_microbench_redmagic.json`
- `phase2c_hash_identity_compatibility_report.md`
- `phase2c_dual_hash_manifest.json`

Rules:

- do not break SHA-256 artifact continuity;
- promote BLAKE3 only where REDMAGIC measurement beats the incumbent and identity compatibility is preserved.

### D. Proxy Science Arms

Run only as non-promoted comparison arms unless the evidence is overwhelming and contract-safe.

Produce:

- `phase2c_srht_comparison_arm_report.json`
- `phase2c_dense_vs_srht_geometry_report.json`
- `phase2c_hybrid_projection_semantics.md`
- `phase2c_ib_k_sweep_report.json`
- `phase2c_k_memory_cost_report.json`
- `phase2c_k_phase3_cost_report.md`
- `phase2c_proxy_label_limitations.md`
- `phase2c_hdc_alignment_note.md`
- `phase2c_lorenz_projection_science_arm.md`
- `phase2c_lorenz_vs_rademacher_falsifier.json`

Rules:

- Dense Rademacher k=256 remains the incumbent until beaten.
- SRHT begins as a comparison arm.
- Lorenz/reservoir projection is science, not a JL claim, unless distance-preservation evidence exists.
- k changes require information retention, collision, memory, and Phase 3 cost evidence.
- If real labels are absent, mark the result as proxy-only.

### E. Real Corpus Boundary Audit

Determine exactly what cannot be done without the real training material workstream.

Produce:

- `phase2c_real_corpus_boundary_report.md`
- `phase2c_real_material_required_inputs.json`
- `phase2c_next_real_corpus_gate.md`

Answer:

- What synthetic/proxy gates are now complete?
- What remains invalid until real corpus arrives?
- What exact corpus shape is needed: records, token diversity, labels/spans, answer structure, size, tokenizer identity?
- What pass/fail thresholds should be applied once the corpus arrives?

## Status Rules

Valid returns:

- `phase2c_maximal_pass`
- `phase2c_engineering_pass_science_open`
- `phase2c_npu_readiness_blocked`
- `phase2c_cached_metric_reproduction_required`
- `phase2c_correctness_pass_perf_failed`
- `phase2c_science_arm_inconclusive`
- `phase2c_real_corpus_required`
- `phase2c_blocked`
- `phase2c_failed`

Do not use `phase2c_maximal_pass` unless all PRD and supplement gates pass, including verifier expansion, NPU-readiness preflight, Comet, hygiene, and a clear real-corpus stance.

If every synthetic/proxy/engineering gate is done and only real training material remains, return:

```text
phase2c_real_corpus_required
```

with exact required corpus contract.

## Final Instruction

Continue now.

Do not report interim progress.

Do not move to Phase 3.

Do not stop at high-diversity pass.

Push until the next honest blocker is real corpus or a measured technical wall.
