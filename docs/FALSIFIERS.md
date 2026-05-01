# Falsifier Specification

**Boundary:** Research infrastructure for in silico on-device LLM training and multilingual / multi-domain knowledge model construction. Outputs are research artifacts - model checkpoints, training telemetry, evaluation reports, throughput measurements. No regulatory certification claims. No clinical or human-subject use. No surveillance, biometric profiling, or identity inference. No model weights distributed without explicit license attestation. No training on copyrighted material without explicit corpus-license decomposition. No deployment to production without a falsifier-traced acceptance gate.

The falsifier registry is implemented in `polymath_ai/falsifiers/registry.py`. Runs do not advance phases by finishing wall-clock; they advance only by passing falsifiers.

Each falsifier ID below is callable via `polymath_ai.falsifiers.evaluate(falsifier_id, evidence)` and returns a `FalsifierResult(result, detail, blocking)`. `summary_report` aggregates a sequence of results and reports `overall = pass | warn | fail | blocked`. A run with any `blocking_failures` cannot advance.

| Falsifier ID | Trigger | Evidence shape | Blocking by default | Required response |
|---|---|---|---|---|
| `boundary_violation` | Boundary scanner reports MISSING / DRIFT / FORBIDDEN_FRAMING | `{scan_failures: [BoundaryScanResult-like, ...]}` | yes | Stop, quarantine, retract, fix source. |
| `device_soc_mismatch` | Probed `soc_reported` differs from `soc_target` | `{soc_reported, soc_target}` | yes | Re-probe; correct target or use fallback. |
| `qnn_exact_path_unproven` | No stored compile/delegate report for the model graph scope | `{qnn_compile_records: [{graph_scope, result}, ...]}` | yes | Run export truth table or disable QNN. |
| `qnn_unsupported_op` | Delegate percentage below threshold | `{delegate_pct, delegate_threshold, unsupported_ops}` | yes | Store failing op, fallback. |
| `smollm3_export_unproven` | Experiment 2 status not pass | `{experiment_2_status: "pass"\|"fail"\|"deferred"}` | yes | SmolLM3 acceleration disabled; eval-only. |
| `checkpoint_hash_mismatch` | Recomputed sha differs from manifest | `{expected_sha256, actual_sha256}` | yes | Quarantine, roll back to prior chain head. |
| `tokenizer_fertility_high` | Any core language above 2.5x English | `{per_language: {<lang>: {ratio_vs_english, ...}}, threshold}` | yes | Vocab extension, sampling fix, or model swap. |
| `oom_or_memory_pressure` | OOM or peak RAM >= 22 GB | `{oom: bool, peak_ram_gb}` | yes | Reduce batch/seq, retry. |
| `thermal_throttle` | GPU clock below 600 MHz for >10% of a 1-hour window | `{gpu_clock_below_600_pct}` | yes | Fan/charge bypass, reduce load, rest. |
| `battery_heat_risk` | Battery >=42C for 60s OR >=40C for 5 min | `{battery_temp_samples_c: [{temp_c}, ...]}` | yes | Stop, cool, change charging regime. |
| `charge_bypass_unproven` | SoC drift > 2pp/hour under bypass test | `{battery_pct_drift_per_hour}` | yes | Rest periods + stricter thermal gate, or postpone. |
| `throughput_floor_fail` | tokens/hour < 500K (warn) or < 100K (fail) | `{tokens_per_hour}` | yes | Debug data pipeline / backend overhead. |
| `energy_budget_exceeded` | joules/token > 1.2x baseline AND no quality gain | `{joules_per_token, joules_per_token_baseline, quality_gain_pct}` | yes | Revert scheduler or reduce load. |
| `catastrophic_forgetting` | English anchor drop > 1pp vs base | `{english_anchor_drop_pp}` | yes | More replay, lower LR, revise curriculum. |
| `cross_model_disagreement_high` | Disagreement metric above threshold | `{disagreement_metric, disagreement_threshold}` | no (warn) | Teacher panel adjudication. |
| `method_disagreement_high` | ELO vs QLoRA Spearman rho < 0.6 | `{elo_qlora_spearman_rho}` | no (warn) | Investigate corpus signal vs method behavior. |
| `license_drift` | Source missing class or class D/E | `{corpus_sources: [{source_id, license_class}, ...]}` | yes | Remove until attested. |
| `ocr_damage_high` | OCR damage score above threshold | `{ocr_damage_score, ocr_damage_threshold}` | yes | Re-OCR, repair, or exclude. |
| `overclaim` | Report claim has no run/eval support | `{unsupported_claims: [...]}` | yes | Rewrite or produce evidence. |

## Result codes

| Code | Meaning |
|---|---|
| `pass` | Evidence supports the gate. |
| `warn` | Evidence is concerning but does not block. |
| `fail` | Evidence shows the gate is broken. Blocks if `blocking_default=True`. |
| `blocked` | Gate cannot be evaluated until prerequisite work is done (e.g. QNN with no compile records). Treated as a fail for advancement. |
| `skipped` | Required evidence keys are missing. Caller must populate evidence before advancing. |

## Wiring into the audit log

Every falsifier evaluation MUST emit an event of `event_type=falsifier` to the run's audit chain:

```python
from polymath_ai.audit.chain import AuditWriter
from polymath_ai.falsifiers import evaluate, summary_report

audit = AuditWriter("audit.jsonl", run_id="run:...")
results = [evaluate("oom_or_memory_pressure", evidence_dict)]
report = summary_report(results)
for r in report["results"]:
    audit.append(event_type="falsifier", payload=r)
```

A run that advances phases without a `falsifier`-typed audit row for each gate is a `phase_gate` violation and itself an overclaim under `overclaim`.

## Phase-gate checklist

| Phase | Required passing falsifiers |
|---|---|
| 0A substrate | `boundary_violation`, `license_drift` (on any tiny fixtures) |
| 0B ELO correctness | tests-as-falsifiers: trainable param check, frozen-hash-invariant, optimizer-only-trainable, deterministic-seed, checkpoint round-trip, real-Qwen smoke |
| 0C export truth table | `qnn_exact_path_unproven` resolved (pass) for any QNN claim |
| 0D device attach | `device_soc_mismatch` (against the resolved target) |
| 0E Experiment 0 | `oom_or_memory_pressure`, `thermal_throttle`, `throughput_floor_fail`, `battery_heat_risk`, `charge_bypass_unproven` |
| 0F Experiment 1 | `tokenizer_fertility_high` |
| 0G Experiment 2 | `smollm3_export_unproven` (resolved) |
| 0H cutover | every prior gate passes; `qnn_exact_path_unproven` set true if QNN is enabled in Phase 1A |
| 1A 100M run | every gate above + `catastrophic_forgetting`, `energy_budget_exceeded`, `cross_model_disagreement_high`, `method_disagreement_high`, `overclaim` (final report check) |
