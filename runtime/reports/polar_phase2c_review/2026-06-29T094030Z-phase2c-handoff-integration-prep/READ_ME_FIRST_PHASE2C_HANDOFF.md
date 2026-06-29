# Phase 2-C Handoff: Read Me First

Status: phase2c_real_corpus_required

Phase 2-C is not a maximal pass and not a Phase 3 handoff. The phone has pushed all local synthetic/proxy/engineering gates as far as they can honestly go. The remaining blocker is real Phase 1 PQA1 training material.

## What Works

- Current promoted route: Phase 1 PQA1 -> native C++/NEON packetizer -> PJP1 audit output.
- Projection incumbent: dense Rademacher k=256,d=2560.
- Optimized input-token projection cache: exact dense Rademacher single-token k4 NEON kernel sharded across 8 threads.
- High-diversity performance floor is cleared on synthetic valid PQA1: 50k distinct-token rung 347,915 real tok/sec; 100k rung 271,713 real tok/sec.
- Verifier expansion, NPU-readiness preflight, BLAKE3 compatibility, and proxy science arms exist as artifacts.

## What Does Not Work Yet

- There is no real training-material pass.
- There is no final k/projection promotion from real labels.
- There is no Phase 3 handoff.
- There is no NPU/HTP execution claim.
- Arrow/ring, SRHT, Lorenz/reservoir, alternate k, and BLAKE3 replacement are not promoted.

## Why Real Corpus Is The Honest Blocker

Synthetic/proxy gates cannot prove production token diversity, answer-span repetition, label/task information retention, real-corpus collision behavior, or whether Phase 3 can consume the final real PJP1 substrate efficiently.

## First 30 Minutes For A New Agent

1. Read this file, ENGINEERING_HANDOFF.md, PHASE2C_STATUS_MATRIX.json, PROMOTED_PATH_MANIFEST.json, REAL_CORPUS_GATE_SPEC.md, and PHASE3_NOT_READY.md.
2. Validate GPD state: `/data/data/com.termux/files/home/.gpd/venv/bin/python -m gpd.runtime_cli --runtime codex --config-dir ./.codex --install-scope local --raw state validate`.
3. Confirm real PQA1 training material exists before running expensive gates.
4. If real material exists, run the 100k real-corpus gate first. If it does not, do not invent work or move to Phase 3.
