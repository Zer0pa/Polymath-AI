# Decisions

## D001 - Authority PRD And Doctrine

**Date:** 2026-05-17
**Decision:** Use `docs/PRD-GEMMA4-SNAPDRAGON-MEGAKERNEL-HETEROGENEOUS-TRAINING.md`
as the governing PRD and `RESISTANCE-V2.md` as the anti-proxy doctrine.
**Rationale:** The top-level `PRD.md` points to this route and the previous
Qwen/ELO/mobile-fine-tuning framing is deprecated for this lane.
**Outcome:** Active.

## D002 - G1 Is A Regression Floor

**Date:** 2026-05-17
**Decision:** Preserve the passed E4B layer 0 OpenCL phone gate as G1 regression
floor only.
**Rationale:** The gate proves one-layer forward parity; it does not prove
fused megakernel, backward, optimizer, training, NPU, or sustained stability.
**Outcome:** Active.

## D003 - Import Namespace

**Date:** 2026-05-17
**Decision:** Import Gemma4 Kernel only under
`integrations/gemma4-snapdragon-megakernel/`.
**Rationale:** The manifest policy prevents root overlay drift and forbids
weights, raw binaries, SDKs, build trees, caches, and secrets.
**Outcome:** Active.
