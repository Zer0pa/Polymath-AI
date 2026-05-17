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

## D004 - Minimal Adapter Training Scope

**Date:** 2026-05-17
**Decision:** Use a rank-4 post-layer0 residual adapter as the first trainable
scope for G5/G6.
**Rationale:** This is the smallest real trainable scope that can exercise
phone-side backward and optimizer update while keeping Gemma base tensors
frozen and hash-stable.
**Outcome:** G5 and G6 passed; scope remains a substrate, not a terminal
training claim.

## D005 - Reject Hidden-State Fixture Path For G8

**Date:** 2026-05-17
**Decision:** Reject G8 promotion while the training step consumes
RunPod-derived hidden-state fixtures.
**Rationale:** The authority runtime path must start from phone-streamed raw
text and phone-packed token IDs. Hidden tensors are allowed only as oracle
comparison outputs, not phone runtime inputs.
**Outcome:** G8 was marked `fail_under_falsification`; next repair is
phone-native `input_ids -> layer_input + per_layer_input` generation.
