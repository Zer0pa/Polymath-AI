# Note to the repo-frontdoor agent (2026-05-02)

**You are invited** to update the repository's external-facing surface area to reflect the current state. This note is written by the executor agent that just closed Phases 0G + 1A. It tells you exactly what changed, where the canonical sources are, and what the front-door reader should see.

## What's currently outdated

The following files are the project's "front door" and currently reflect a pre-2026-05-02 state. They predate the Phase 0G unblock, the Phase 1A on-device proof, and the Phase 1A.0 + 1A.B overnight characterisation:

- `README.md` — top-level project description. Likely still says Phase 0G is pending or QAIRT-blocked.
- `PRD.md` — product requirements doc. Phase 1A status / acceptance criteria are pre-D-030.
- `MODUS-OPERANDI.md` — methodology doc. Should be cross-referenced from the new comprehensive report.

## What to bring forward

### Headline (one-line update)

Phase 0 is **closed**. Phase 1A on-device QNN inference is **proven** on actual Snapdragon 8 Elite Gen 4 hardware with **22,850 successful inferences over 6h15m at 100% success rate**. Phase 1A.B steady-state benchmark is **closed**. Phase 1A.A (real-data ELO Stage-1 training experiment) is the next step.

### Numbers to put in the README (verified, not projections)

| Metric | Value | Source |
|---|---|---|
| Snapdragon SM8750 AOT compile success rate | 5 / 5 scopes | `runtime/reports/export_probe/2026-05-02T014031Z_litert214_qairt244_FULL/summary.json` |
| Qwen2.5-1.5B 26-layer ELO frozen middle, on-device steady-state per-inference latency | **576 ms (p50), 811 ms (p95), 817 ms (max)** | `runtime/reports/phase1a/2026-05-02T1802Z-overnight-v2/summary.json` |
| Qwen2.5-1.5B single transformer block, on-device steady-state per-inference latency | **19 ms (p50), 22 ms (p95)** | same |
| Sustained-load reliability across 22,850 inferences over 6h15m | **100% success rate** (rc=0, out_size=98304 every time) | same |
| Unplugged battery life of REDMAGIC SM8750 at the proven duty cycle | **~25 hours from 100% → 15% halt** | extrapolation from observed 3.2%/hour drain over 2.5h unplugged segment |
| Thermal envelope (room ambient, no fridge needed) | battery peaked 32 °C, CPU0 peaked 58 °C startup → 28–36 °C steady state | same |
| Unit test suite | 127 / 127 pass | `pytest tests/` |
| Cumulative engineering decisions logged | 32 (D-001 through D-032) | `docs/DECISIONS.md` |

### Status badges (suggested for README)

```markdown
[![Phase 0G](https://img.shields.io/badge/Phase_0G-AOT_compile-green)]()
[![Phase 1A](https://img.shields.io/badge/Phase_1A-on--device_proven-green)]()
[![Phase 1A.B](https://img.shields.io/badge/Phase_1A.B-22850_inferences_100%25-green)]()
[![Phase 1A.A](https://img.shields.io/badge/Phase_1A.A-next-yellow)]()
[![Tests](https://img.shields.io/badge/tests-127%2F127-brightgreen)]()
```

### Authoritative documents to link from README

These are the documents that should be visible from the front door, in this priority order:

1. **`docs/REPORT-2026-05-02-comprehensive.md`** — the 8.6k-word zero-context-friendly technical report. This is what an external ML engineer or OEM platform engineer should land on. Self-contained; no other reading required.
2. **`docs/REPORT-2026-05-02-phase-0-1a-progress.md`** — shorter (~3.5k word) executive companion, for readers already familiar with edge ML.
3. **`docs/PHONE-OVERNIGHT-RUNBOOK.md`** — operator runbook for the proven overnight chain.
4. **`docs/DECISIONS.md`** — full 32-row decision log; canonical source of truth for every claim.
5. **`docs/NOTE-TO-REPO-AGENT-2026-05-02.md`** — this file (for context if the agent re-runs in a future session).
6. **`PR #4`** on GitHub — every change in this period is in one PR for review/merge.

### What to edit in README.md

I'd suggest the README looks like:

```markdown
# Polymath AI

Research infrastructure for **continuous pretraining of an LLM directly on a consumer Android phone**.

Target model: `Qwen/Qwen2.5-1.5B`. Target hardware: Snapdragon 8 Elite Gen 4 (SM8750).
Reference handset: REDMAGIC 10 Pro+. Method: ELO continuous pretraining (train layer 0 + LM head, freeze middle layers, run frozen middle on phone NPU).

## Status (2026-05-02)

Phase 0G AOT compile: **closed** (5/5 scopes ok, QAIRT 2.44 + LiteRT 2.1.4 matching pair).
Phase 1A on-device inference: **closed** (22,850 inferences, 100% success rate, 576 ms p50 for full 26-layer Qwen frozen middle on Hexagon NPU).
Phase 1A.A (real-data ELO Stage-1 training): **next**.

See `docs/REPORT-2026-05-02-comprehensive.md` for the full technical report.

## Headline number

A 1.5-billion-parameter transformer's frozen middle (26 of 28 Qwen2.5-1.5B layers) AOT-compiles to a 2.3 GB Qualcomm SM8750 context binary and runs on a consumer phone's Hexagon NPU at **0.576 seconds per forward pass, sustained for 6+ hours at 100% reliability, room-temperature ambient, no thermal throttling**.

## Quick links

- [Comprehensive technical report](docs/REPORT-2026-05-02-comprehensive.md)
- [Decision log (32 rows)](docs/DECISIONS.md)
- [Phone overnight runbook](docs/PHONE-OVERNIGHT-RUNBOOK.md)
- [Live PR](https://github.com/Zer0pa/Polymath-AI/pull/4)

## Boundary

(Verbatim self-imposed scope; sha256-anchored across artifacts.)

> Research infrastructure for in silico on-device LLM training and multilingual / multi-domain knowledge model construction. Outputs are research artifacts — model checkpoints, training telemetry, evaluation reports, throughput measurements. No regulatory certification claims. No clinical or human-subject use. No surveillance, biometric profiling, or identity inference. No model weights distributed without explicit license attestation. No training on copyrighted material without explicit corpus-license decomposition. No deployment to production without a falsifier-traced acceptance gate.

## Reproducer

90-minute clean-slate reproducer: see `docs/REPORT-2026-05-02-comprehensive.md` §11 + §15.
```

### Things you should NOT change

- **The boundary block.** Verbatim, sha256-anchored. Already correct in `polymath_ai/boundary/text.py`.
- **The decision log entries.** D-001 through D-032 are immutable historical record. Add D-033+ if you make new decisions; never edit prior rows.
- **The phase numbers.** 0A through 3A are stable. Don't renumber.
- **Anything in `runtime/reports/`.** Those are dated artifacts; they belong to the run that produced them.
- **The `polymath_ai/` source code unless it has actual new functionality** — this note is asking for a docs-only update.

### What to merge first

PR #4 (`linux/phase0g-qairt-v2.43`) carries every change this report references. The PR has been kept in a coherent state with running test suite (127/127 pass) and a working overnight chain (closed cleanly with `stop_signal_received`). After PR #4 merges, your README + PRD updates can be a separate PR with a clean diff, or appended to PR #4 if your workflow prefers a single roll-up.

### Verification before you publish

1. `pytest tests/` → expect 127/127 pass.
2. `cat polymath_ai/boundary/text.py | grep BOUNDARY_SHA256` → confirm the sha256 anchor is present and matches what the boundary scanner expects.
3. `python -c "from polymath_ai.scheduler.registry import default_registry; r = default_registry(); print(r.get('litert_qnn_sm8750').confirmed_for_socs)"` → expect `(('SM8750', 1.0),)` (the Phase 0G promotion).
4. Visit <https://huggingface.co/datasets/Architect-Prime/polymath-telemetry/tree/main/phase1a> → confirm the latest run's audit.jsonl exists (the live-monitoring proof).

## Why this matters externally

The work in this period unlocks two reusable patterns for the broader on-device-ML community, beyond Polymath's own roadmap:

1. **The "matching-pair" SDK pinning insight** — LiteRT's `third_party/qairt/workspace.bzl` hard-pins QAIRT version with a public CDN URL. Reusable by any team hitting QnnSystem-version-mismatch errors.
2. **The "extract embedded QNN context binary" pattern** — saves a multi-week NDK build for production QNN-delegated models. Tooling in `scripts/host/extract_qnn_context.py` (~80 lines, two dependencies).

Both are documented in §7 of the comprehensive report; consider linking from the README for community discoverability.

---

*Written 2026-05-02 by the executor agent. The next agent can append to this note or supersede with a fresh `NOTE-TO-REPO-AGENT-<date>.md`.*
