# H11-A Daemon Design Note

- `phase11_runner` starts once from ADB and then reads the phone-local JSONL queue.
- H11-A iterations run inside one long-lived process; ADB does not issue per-iteration commands.
- `runner_state.json` is rewritten after each completed checkpoint boundary so a restart can resume from the last output checkpoint.
- `heartbeat.json` is emitted by a native heartbeat thread every 10 seconds during work and disconnect hold.
- `STOP` is honored before each iteration and during disconnect hold.
- `checksum_chain.jsonl` lives under the run directory and chains small JSON artifacts plus adapter checkpoint payload hashes.
- Existing one-shot `gemma4_layer_runner --run-g8-distill[-compact]` behavior remains untouched as the diagnostic fallback.
- This H11-A build removes host process restart per iteration; deeper OpenCL context reuse remains measurable in H11-C/H11-D.
