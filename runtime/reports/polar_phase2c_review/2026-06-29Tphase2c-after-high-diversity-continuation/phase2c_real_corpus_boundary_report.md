# Phase 2-C Real Corpus Boundary Report

Status: phase2c_real_corpus_required

Synthetic/proxy/engineering gates now complete under the post-high-diversity continuation: stratified PJP1 oracle sampling, NPU-readiness preflight, staging/copy/alignment reports, BLAKE3 microbench and dual-hash compatibility, SRHT/Lorenz/k comparison arms, and high-diversity 50k/100k performance recovery.

Remaining invalid without real corpus:
- production token-diversity and answer-span repetition;
- real-label information-bottleneck k selection;
- final projection promotion beyond dense Rademacher k=256;
- real-corpus margin/Hamming/collision behavior;
- final Phase 3 handoff contract.

Collision boundary: the synthetic 100k high-diversity PJP1 full-token scan found sparse exact k=256 polar-code collisions below the supplement 0.1% rate gate. Strict zero collision is not claimed. Real corpus must re-run the same falsifier before any maximal closure or Phase 3 handoff.
