# Polar Phase 2 Native Packetizer

This directory owns the Phase 2-B native authority hot path. The implementation
consumes valid Phase 1 `PQA1` shards, the phone-local Gemma 4 E4B f16 input
embedding, and the dense Rademacher JL matrix, then emits `PJP1` v1 without
changing the promoted Phase 2 schema.

Raw `.pqa1`, `.pjp1`, embedding tensors, and JL `.bin` artifacts stay out of
git, compact mirrors, and Comet assets.
