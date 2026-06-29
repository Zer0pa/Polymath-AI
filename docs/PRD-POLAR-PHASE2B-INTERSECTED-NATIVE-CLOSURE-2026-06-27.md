# PRD: Polar Phase 2-B Intersected Native Closure

Date: 2026-06-27
Authority runtime: REDMAGIC NX789J / Snapdragon SM8750 in Termux
Control plane: Mac only

## Classification

Previous Phase 2 is reclassified as
`phase2_contract_scale_reference_pass_native_performance_failed`.

The previous artifact is valid reference-scale evidence, not native closure:
valid PQA1 was consumed, Gemma4 E4B f16 embedding and dense Rademacher JL were
used, and PJP1 was emitted at 1M scale, but the promoted hot path was
Python/NumPy and missed the native floor.

## Merged Objective

The merged objective is not to produce another proof of concept. It is to keep
the Phase 2 promoted contract intact while replacing the Python/NumPy hot path
with a native phone-side implementation that can falsify or satisfy the
`>=100,000` real tokens/sec floor.

The Phase 1 build-identity discipline applies here: preserve the exact artifact
contract, prove source and artifact identity, and never narrate a secondary win
as closure if the authority metric fails.

## Sovereign Gates

1. Input must be valid Phase 1 `PQA1`; JSON/token text is invalid.
2. Output must be `PJP1` v1 with the existing section layout and metadata
   offsets.
3. Dense JL must use the existing `k=256,d=2560` Rademacher matrix and `>=0`
   tie policy.
4. Correctness must pass before performance can be promoted.
5. Native 100k scale must reach `>=100,000` real tokens/sec and `>=3x` the
   Python baseline.
6. Native 1M scale must reach `>=100,000` real tokens/sec for maximal closure.
7. Comet logging is attempted only when `COMET_API_KEY` is present in the
   process environment; secrets are never read from files, printed, or copied.

## Execution Plan

1. Read the phone PRD and startup prompt from `/sdcard`.
2. Build a native Termux CLI under `native/polar_phase2_packetizer`.
3. Use Python only for orchestration, verifier reuse, report generation, and
   Comet/hygiene.
4. Run smoke and 10k exact section parity against the existing Python reference
   PJP1 where available.
5. Run 100k performance gate.
6. Run 1M only if 100k reaches the floor, unless explicitly requested for
   falsification.
7. Emit only one of the Phase 2-B terminal statuses.

## Terminal Statuses

- `phase2b_native_maximal_closure_pass`
- `phase2b_native_floor_pass_1m_continuation_required`
- `phase2b_correctness_pass_perf_failed`
- `phase2b_correctness_pass_perf_blocked`
- `phase2b_blocked`
- `phase2b_failed`
