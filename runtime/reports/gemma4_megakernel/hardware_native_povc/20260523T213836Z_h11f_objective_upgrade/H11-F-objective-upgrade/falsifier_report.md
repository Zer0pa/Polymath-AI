# H11-F Falsifier Report

- parity-MSE renamed as objective: pass, telemetry uses `loss_topk_kl` from a precomputed full-teacher top-k shard.
- RunPod teacher during phone runtime: pass, teacher shards were pushed to phone before the phone-local runner started.
- train-only loss overfit sold as capability: pass, held-out control comparison governs the gate.
- metric chosen after results: pass, objective_spec.json declares the mini metric before phone training analysis.
