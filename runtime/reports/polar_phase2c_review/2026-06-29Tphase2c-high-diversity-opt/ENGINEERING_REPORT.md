Status: phase2c_high_diversity_50k_pass
Report root: runtime/reports/polar_phase2c/2026-06-29Tphase2c-high-diversity-opt/
Authority runtime: REDMAGIC NX789J / Termux
Comet: https://www.comet.com/zer0pa/mobile-polymath-ai-training/2f4042f5f24a4578bc4b62dfd62f85cd
Scope: 50k diversity perf gate only; no Phase 2-C maximal pass and no Phase 3 handoff claim

# Phase 2-C High-Diversity Optimization Continuation

## Decision

The previous blocker is cleared for the requested gate: 50k distinct-token diversity now reaches 347915 real tokens/sec, above the 200000 floor. The harder 100k distinct-token sanity rung reaches 271713 real tokens/sec.

## Optimization

The promoted semantics are unchanged. The native packetizer now builds the exact dense Rademacher input-token projection cache with a single-token k4 NEON kernel sharded over 8 threads. This removes the single-threaded cache-preparation wall without changing PJP1 layout, sections, CRCs, token hashes, or projected bits.

## Evidence

- 50k old: 120970 real tok/sec; new: 347915 real tok/sec; speedup 2.876x.
- 50k cache prepare: 17.427s -> 2.331s.
- 100k old: 69798.7 real tok/sec; new: 271713 real tok/sec; speedup 3.893x.
- PJP1 sections match previous outputs after the timestamped 4096-byte header for both 50k and 100k rungs.
- PJP1 readback passes for both optimized outputs.

## Nonclaims

This does not claim Phase 2-C maximal pass, NPU readiness, Phase 3 handoff, science-arm promotion, learning movement, GPU execution, or model quality movement.
