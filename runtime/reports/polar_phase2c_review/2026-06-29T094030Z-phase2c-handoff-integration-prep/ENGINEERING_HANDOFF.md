# Phase 2-C Engineering Handoff

## Architecture

Input is Phase 1 PQA1. Output authority is PJP1. Native path is `native/polar_phase2_packetizer/phase2b_native_packetizer.cpp`, built by `native/polar_phase2_packetizer/build_phase2b_native_packetizer.sh` into `native/polar_phase2_packetizer/bin/phase2b_native_packetizer`.

PJP1 layout: 4096-byte header followed by metadata, token_ids, roles, input_polar, target_polar, and pooled_answer sections. Packet length is 128 tokens. k=256 means each polar code is 32 bytes.

Projection cache: exact dense Rademacher input-token projection reuse. The current optimized high-diversity path builds cache entries with a single-token k4 NEON kernel across 8 threads.

## Source And Build

Source: `native/polar_phase2_packetizer/phase2b_native_packetizer.cpp` sha256 `ba2d4dd48e2d9afeabf69b84019af0375aa739b26e982d69e8084a94a264c61f`.
Build script: `native/polar_phase2_packetizer/build_phase2b_native_packetizer.sh` sha256 `3c284c858aaa0d1e7697c4b63a12330d2e24d62a2391f109f34133463a631716`.
Binary: `native/polar_phase2_packetizer/bin/phase2b_native_packetizer` sha256 `11c81138d181f09dd1a9a4715952c8a5357a91e3f1c1562f2fb9761d4d4c336a`.

Build command:

```sh
native/polar_phase2_packetizer/build_phase2b_native_packetizer.sh
```

## Cheap Sanity Checks

```sh
/data/data/com.termux/files/home/.gpd/venv/bin/python -m gpd.runtime_cli --runtime codex --config-dir ./.codex --install-scope local --raw state validate
jq empty runtime/reports/polar_phase2c/2026-06-29Tphase2c-after-high-diversity-continuation/phase2c_gate_result.json
jq '.terminal_status' runtime/reports/polar_phase2c/2026-06-29Tphase2c-after-high-diversity-continuation/phase2c_gate_result.json
sha256sum native/polar_phase2_packetizer/bin/phase2b_native_packetizer native/polar_phase2_packetizer/phase2b_native_packetizer.cpp
```

## Real-Corpus Gate Template

Use the optimized native binary with real PQA1 input lists at 100k and 1M scale. Preserve PJP1 as the audit artifact. Log Comet from `COMET_API_KEY` in environment only. Then run PJP1 readback, stratified oracle, collision, margin, Hamming geometry, and NPU preflight again on real outputs.

The real-corpus pass/fail details are in REAL_CORPUS_GATE_SPEC.md.

## Known Performance Numbers

- Phase 2 Python/NumPy 1M: 18,517.112 real tok/sec; reference-only, not promoted. Evidence: `runtime/reports/polar_phase2/2026-06-26T235142Z`.
- Phase 2-B native 100k: 462,598 real tok/sec; 1M: 598,675 real tok/sec. Evidence: `runtime/reports/polar_phase2_native_closure/2026-06-28T105404Z-cached-1M`. Comet: https://www.comet.com/zer0pa/mobile-polymath-ai-training/aef6f2d8fca649f48cf8694565889e8a.
- Phase 2-C failed diversity baseline: 50k 120,970 real tok/sec; 100k 69,798.7 real tok/sec. Evidence: `runtime/reports/polar_phase2c/2026-06-28Tphase2c-final`.
- Phase 2-C optimized high diversity: 50k 347,915 real tok/sec; 100k 271,713 real tok/sec. Evidence: `runtime/reports/polar_phase2c/2026-06-29Tphase2c-high-diversity-opt`. Comet: https://www.comet.com/zer0pa/mobile-polymath-ai-training/2f4042f5f24a4578bc4b62dfd62f85cd.
- Phase 2-C post-high-diversity continuation: phase2c_real_corpus_required. Evidence: `runtime/reports/polar_phase2c/2026-06-29Tphase2c-after-high-diversity-continuation`. Comet: https://www.comet.com/zer0pa/mobile-polymath-ai-training/0231809361bf4ca48fef4e79b865bafb.

## Quality Boundaries

No Phase 3, NPU/HTP execution, Arrow/ring promotion, SRHT promotion, Lorenz promotion, alternate-k promotion, BLAKE3 identity replacement, megakernel, learning, or model-quality movement is supported by current evidence.
