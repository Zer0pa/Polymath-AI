---
plan_id: 10-02
phase: 10
status: mixed
completed: 2026-05-17
---

# Summary: Phase 10 Non-Claim Gates

## Result

Mixed, with no narrative promotion of failed gates.

The six-hour endurance non-claim is promoted only for the current REDMAGIC
rank-4 two-layer phone-native training lane. The other four non-claims remain
blocked: this is not full Gemma4 training, not Hexagon NPU training, not public
benchmark readiness, and not theoretical maximum reached.

## Passed Gate

Six-hour endurance gate:
`runtime/reports/gemma4_megakernel/hardware_max/20260517T153500Z_phase10_six_hour_endurance/gate_result.json`

Evidence:
- `wall_seconds = 21692.164205625013`, exceeding the 21600 second gate.
- `iteration_count = 465` chained phone training iterations.
- `active_training_seconds = 4626.6455870000045`.
- `max_thermal_status = 0`, below the critical threshold.
- Checkpoint chain stayed unbroken across repeated updates.
- Sampled parity passed for iterations `0`, `240`, and `464`.
- Sample adapter update cosine minima were `0.9999981024312784`,
  `0.9999991281373523`, and `0.9999993917530322`.
- Raw tensor samples stayed outside the repository.

Promoted claim:
the current narrow phone-native training path has a six-hour wall-clock
endurance proof.

## Failed Or Blocked Gates

Hexagon/QNN/HTP probe:
`runtime/reports/gemma4_megakernel/hardware_max/20260517T213600Z_phase10_qnn_htp_probe/gate_result.json`

Status: `fail`.
QNN platform validation passed and an HTP inference/context workload executed
on Hexagon Architecture V79 with HVX threads. That is not a training update.
No HTP backward, gradient, or optimizer path executed, so Hexagon NPU training
is not promoted.

Scope/readiness/theoretical gate:
`runtime/reports/gemma4_megakernel/hardware_max/20260517T214000Z_phase10_nonclaim_gate/gate_result.json`

Status: `fail`.
Resolved non-claims: `six-hour endurance`.
Blocked non-claims: `full Gemma4 training`, `Hexagon NPU training`,
`public benchmark readiness`, and `theoretical maximum reached`.

## Implementation Notes

Added compact endurance execution so the six-hour run could keep audit JSON in
the repo while holding sampled raw tensors outside git:

- `scripts/host/run_gemma4_phone_endurance.py`
- `scripts/host/verify_gemma4_endurance_samples.py`
- `scripts/host/run_phase10_qnn_htp_probe.py`
- `scripts/host/generate_phase10_nonclaim_gate.py`
- `integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/src/runner/main.cpp`
- `integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/src/backends/opencl_layer_runner.cpp`
- `integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/include/polymath/gemma4/adapter_training.h`

## Non-Claims Still Active

This phase did not prove full Gemma4 training, Hexagon NPU training, public
benchmark readiness, or theoretical maximum reached. Those gates failed or were
blocked by missing authority evidence.
