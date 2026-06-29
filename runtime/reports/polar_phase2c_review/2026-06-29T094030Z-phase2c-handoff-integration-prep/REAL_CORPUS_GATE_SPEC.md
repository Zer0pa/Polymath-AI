# Real Corpus Gate Spec

Status: phase2c_real_corpus_required

## Required Material

- Format: Phase 1 PQA1 files.
- Sample sizes: 100k records and 1M records.
- Tokenizer identity: vocab hash, merges hash, tokenizer SHA-256 matching Gemma4 manifests.
- Source identity: source manifest, license/provenance, PQA1 source SHA-256 stream.
- Structure: question/answer segments with answer/loss masks preserved.
- Labels/objectives: real task labels or training objective metadata for information-bottleneck k decisions.

## Pass Gates

- Comet logged from environment only.
- PJP1 readback pass.
- Stratified oracle 100% bit-exact sampled packets.
- At least 50k distinct token IDs for production floor gate.
- Distinct-token throughput >= 200,000 real tok/sec.
- Collision duplicate-token fraction <= 0.1%.
- Margin/Hamming geometry no worse than synthetic proxy baseline without explanation.
- No Phase 3 handoff until NPU consumer preflight is repeated on real PJP1.
