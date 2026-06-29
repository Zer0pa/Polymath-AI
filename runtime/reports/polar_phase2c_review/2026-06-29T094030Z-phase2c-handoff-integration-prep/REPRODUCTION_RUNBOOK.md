# Reproduction Runbook

## Minimal Cheap Sanity

```sh
/data/data/com.termux/files/home/.gpd/venv/bin/python -m gpd.runtime_cli --runtime codex --config-dir ./.codex --install-scope local --raw state validate
jq empty runtime/reports/polar_phase2c/2026-06-29Tphase2c-after-high-diversity-continuation/phase2c_gate_result.json
jq '.terminal_status' runtime/reports/polar_phase2c/2026-06-29Tphase2c-after-high-diversity-continuation/phase2c_gate_result.json
sha256sum native/polar_phase2_packetizer/bin/phase2b_native_packetizer native/polar_phase2_packetizer/phase2b_native_packetizer.cpp
```

## Full Real-Corpus Gate Sequence

1. Prepare real PQA1 list files for 100k and 1M records with matching tokenizer hashes.
2. Run native packetizer to PJP1 using the promoted binary and dense Rademacher k=256 JL matrix.
3. Log Comet from `COMET_API_KEY` in environment only.
4. Run PJP1 readback.
5. Run stratified oracle on beginning, middle, end, and random packets.
6. Run collision, margin, and Hamming geometry reports.
7. Re-run NPU-readiness preflight on the real PJP1 output.
8. Update GPD only after artifacts exist.

## Avoid Old Paths

Do not use the Python/NumPy route for performance claims. Do not use old single-thread cache preparation. Do not promote Arrow/ring, SRHT, Lorenz, or alternate k from proxy reports. Do not claim NPU/HTP execution from staging preflight.
