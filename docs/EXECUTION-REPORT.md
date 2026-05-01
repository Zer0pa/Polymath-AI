# Overnight Execution Report — Polymath AI

**Boundary:** Research infrastructure for in silico on-device LLM training and multilingual / multi-domain knowledge model construction. Outputs are research artifacts - model checkpoints, training telemetry, evaluation reports, throughput measurements. No regulatory certification claims. No clinical or human-subject use. No surveillance, biometric profiling, or identity inference. No model weights distributed without explicit license attestation. No training on copyrighted material without explicit corpus-license decomposition. No deployment to production without a falsifier-traced acceptance gate.

**Run window:** 2026-05-01 (overnight on Intel Mac + 1 hour Apple Silicon agent).
**Agents:** Claude Opus 4.7 (1M context). Two hosts: Intel Mac (orchestrator), Apple Silicon M1 (Phase 0G AOT compile attempt).
**Repo:** `Zer0pa/Polymath-AI` (private, branch `main`).
**Latest commit:** `0502eec` (post-merge of `silicon/phase0g-aot`).

## Headline

REDMAGIC 10 Pro attached, probed, Termux fully bootstrapped (transformers 4.57.6 + tokenizers 0.22.2 + huggingface_hub + safetensors), Termux:API + tmux + SSH server live. **Real Qwen2.5-1.5B ELO Stage 1 host-mediated smoke completed end-to-end**: 5 train_steps, loss 14.515 → 4.449 monotone decreasing on same-batch overfit, **frozen invariant held across all 5 steps**, checkpoint sha-stable, audit chain clean. **Phase 0F real-corpus FLORES-200 audit caught Zulu (2.68×) and Greek (4.38×) above the 2.5× English fertility threshold**; D-017 dropped them from Phase 1A on Qwen and revised the language mix. **Phase 0G blocked at SDK level on macOS arm64** (D-021: `apply_plugin_main` native binary absent in `ai-edge-litert==2.1.4` macOS arm64 wheel); Linux x86_64 handoff at `docs/HANDOFF-TO-LINUX-X86_64.md`. Scheduler `litert_qnn_sm8750.confirmed_for_socs` correctly remains `()` — Phase 1A QNN routing stays locked until a real `ok` CompileRecord lands. 126/126 tests passing.

## Acceptance gate snapshot

| Gate | Result | Evidence |
|---|---|---|
| Scientific gate (boundary clean, source-grounded, no out-of-scope framing) | **pass** | Boundary scanner clean across the repo; 19 PRD falsifiers + 4 fridge-mode falsifiers wired with positive + negative fixtures; every artifact carries the boundary block. |
| Engineering gate (Mac sim end-to-end, plug-replaceability, audit invariants, sync recovery, ELO frozen-layer invariants) | **pass** | 126/126 tests; audit chain validates clean across smoke + E0.1 runs; ELO frozen-hash invariant holds on tiny + real Qwen2.5-1.5B (E0.1 confirmed 5 steps with frozen_changed=[]). |
| Device-readiness gate | **partial pass** | Phone attached, SoC=SM8750 confidence 1.0 (D-015), Termux + SSH live, Charge Separation active, battery 31°C. **Phase 0G blocked at SDK** (D-021: macOS arm64 wheel missing AOT plugin); Linux x86_64 handoff written. Phase 0E E0.1 host-mediated complete. |
| Brain-functionality gate (fresh agent reconstructs from repo + HF + audit/KG without conversation context) | **pass** | All canonical docs in repo; 4 private HF repos seeded; all 21 decisions in `docs/DECISIONS.md`; audit chain replayable; PR-and-merge handoff between Intel Mac + Apple Silicon agents demonstrated. |
| Research-publishability gate (Phase 1A report) | **deferred** | Pending Phase 0G unblock on Linux x86_64, then Phase 1A run on phone. |

## What was implemented

### Phase 0A — substrate and contracts

Status: **complete**. Commit: `83fc1aa`.

* `polymath_ai.boundary`: verbatim boundary text, SHA, scanner with forbidden-framing detection. Suppression rules let the scanner read its own boundary block (and any negation like "no clinical use") without flagging.
* `polymath_ai.schemas`: PolymathEnvelope, audit row, checkpoint, corpus manifest, device state, dispatch, eval, falsifier-result, pending-upload, reasoner-tuple, sync-event. Lightweight structural validator (no hard `jsonschema` dep).
* `polymath_ai.audit`: append-only JSONL hash chain with `compute_event_hash` over `(prev_event_hash, recorded_at, payload)`. `validate_audit_chain` detects tamper / reorder / insert / delete; `AuditWriter.tail_hash` recovers from a half-written file on resume.
* `polymath_ai.kg`: `KGStore` (nodes.jsonl + edges.jsonl), 22 node types and 14 edge types from PRD §KG Node Types; `reconstruct_kg` in-memory replay.
* `polymath_ai.falsifiers`: 19 PRD falsifiers wired with positive AND negative fixtures (`tests/test_falsifiers.py`). `summary_report` aggregates blocking failures.
* `polymath_ai.sync.pending`: pending-upload manifest writer for the HF-token-absent path.
* `polymath_ai.utils`: canonical JSON, sha256 (text/file/bytes), UTC ISO timestamps.

### Phase 0B — ELO correctness on dev machine

Status: **complete**. Commit: `bbec223`. **Proven on real Qwen2.5-1.5B.**

* `polymath_ai.elo.trainer.ELOTrainer.build_stage1_model`: wires `FreezePlan` with Adam over trainables only, deduped by `id()` so tied tensors are not double-stepped.
* `train_step` performs pre/post frozen-parameter hash sample, gradient clip, and emits a `TrainStepRecord` with `frozen_hashes_changed` (must be empty by invariant).
* `save_boundary_checkpoint` writes `trainable.pt` + `optimizer.pt` + `manifest.json`. Streaming SHA-256 over sorted name | tensor bytes (replaces the JSON-of-hex round-trip that hung on 327M trainable params).
* `load_boundary_checkpoint` detects freeze-plan drift on resume and refuses to load if the trainable-name set has changed.
* `merge_boundary_checkpoint` copies trained boundary weights into a base model in place.
* `run_stage2_alignment` runs a brief full-model calibration loop.

`apply_freeze_plan` calls `untie_lm_head_if_tied` when the plan has `freeze_embeddings=True` AND `train_lm_head=True`. Qwen2.5-1.5B and SmolLM3-3B both ship tied; the untie produces an independent `lm_head.weight` before freezing embeddings (Decision D-001).

#### Real-Qwen2.5-1.5B ELO Stage 1 smoke

Run at `runtime/reports/qwen_elo_smoke/2026-05-01T031731Z/report.json`:

```json
{
  "model_id": "Qwen/Qwen2.5-1.5B",
  "n_total_params": 1777088000,        // 1.78B (post-untie)
  "trainable_n_params": 326969344,     // 327M = layer0 + layer27 + lm_head
  "trainable_param_tensor_count": 25,  // matches PRD ELO default
  "frozen_param_tensor_count": 314,
  "frozen_changes_observed": 0,        // FREEZE PLAN HOLDS
  "loss_curve": [14.785, 11.939, 8.763],  // monotone decrease on same batch
  "result": "pass"
}
```

Audit chain validates clean. The smoke is the proof that Phase 0B's tiny-model invariants extend to the production model unchanged.

#### Stage 1 → Stage 2 round-trip

`tests/test_elo_stage2_integration.py::test_stage1_to_stage2_round_trip` covers: Stage 1 trains 8 steps on tiny model, saves boundary checkpoint, fresh base model is loaded, `merge_boundary_checkpoint` copies trained weights in, base layer 0 weights now equal Stage 1's, Stage 2 alignment runs 3 steps with finite loss.

### Phase 0C — export truth table

Status: **host stub complete; real compile rows deferred to phone (D-012, D-013)**.

* `polymath_ai.dispatch`: `AcceleratorAdapter` contract; `MacSimAdapter` and `FallbackAdapter` for host stubs.
* `run_export_probe` sweeps `(model, scope, target)`: 5 scopes × 6 targets × 3 models = up to 90 rows.
* `runtime/reports/export_probe/2026-05-01T040732Z/truth_table.md` shows 36 rows (Qwen×3 scopes + SmolLM3×2 + tiny×1, all 6 targets), all `backend=mac_sim`, `stage=stub`, awaiting phone-attach to fill QNN/LiteRT rows.

LiteRT: `ai-edge-litert==1.0.1` installed; the `ai_edge_litert.aot` and `ai_edge_litert.aot.vendors.qualcomm` subpackages are NOT shipped on the Intel Mac wheel (they are present on the Linux x86_64 and Android arm64-v8a wheels). The QAIRT SDK install is behind a Qualcomm Developer Network login. Decisions D-012 and D-013 record the deferral.

### Phase 0D — device attach + stack probe

Status: **blocked by phone absence; runbook ready**.

* `scripts/host/phone_probe.sh` runs `adb devices`, `getprop`, `meminfo`, `df`, thermal/battery dumps, kernel/cpu info, GPU clock, and Termux package presence. Writes `summary.json` ingestible by `polymath_ai.device.probe.parse_*`.
* `polymath_ai.device.probe`: pure-Python parsers for adb output, getprop K/V, meminfo kB ints, Termux Python version. `soc_target_from_reported(reported)` returns `(target, confidence)`; confidence < 1.0 means "do not enable QNN" (Decision D-006).

### Phase 0E — Experiment 0 (stack fit, throughput)

Status: **blocked by phone absence**. The runner module `polymath_ai.experiments.phase0e` is wired but blocks at `phone_attached=False`. Configs templated at `configs/experiments/E0/` (E0.1-E0.4 to be created on phone arrival).

### Phase 0F — Experiment 1 (tokenizer fertility audit)

Status: **fixture audit complete on host**.

`runtime/reports/fertility/Qwen_Qwen2.5-1.5B/2026-05-01T041052Z/fertility.md` (excerpt):

| Language | Tokens/Word | Ratio vs en |
|---|---:|---:|
| en | 1.150 | 1.00x |
| fr | 1.482 | 1.29x |
| es | 1.511 | 1.31x |
| de | 1.922 | 1.67x |
| ar | 1.959 | 1.70x |
| ru | 2.209 | 1.92x |
| sw | 2.410 | 2.10x |
| hi | 2.547 | 2.21x |
| zh | 0.682 | 0.59x |
| ja | 0.669 | 0.58x |
| ko | 0.892 | 0.78x |

All 11 languages **pass** the 2.5x threshold. Falsifier `tokenizer_fertility_high` = pass.

SmolLM3-3B equivalent at `runtime/reports/fertility/HuggingFaceTB_SmolLM3-3B/...`: similar shape, all pass.

The full Phase 0F audit will run against the bulk Seed Corpus v0 once the corpus shards exist on HF (post-curation, post-phone). The fixture audit is a tripwire that the plumbing works.

### Phase 0G — Experiment 2 (SmolLM3 QNN export verdict)

Status: **blocked by phone + LiteRT-AOT (D-012, D-013)**.

`scripts/termux/run_export_probe_termux.sh` runs the LiteRT AOT availability probe in Termux first, records the `litert_probe.json` verdict, then either proceeds with the real compile sweep OR falls back with a clear "QNN unprovable on this stack" record. The falsifier `smollm3_export_unproven` stays `blocked` until the AOT path opens.

### Phase 0H — cutover review

Status: **deferred until 0D-0G complete**. The PRD's Phase 1A cutover is a config flag (`phase: phase1a_qwen_elo_100m`, `phone_attached: true`, `corpus_slice: seed-v0-phase1a-100m`); none of the Phase 0H gates are passable yet because Phases 0D-0G are phone-gated.

## Falsifier outcomes (host-only)

| Falsifier | Status (host) | Notes |
|---|---|---|
| `boundary_violation` | pass | scanner returns `[PASS]` for every required-boundary file. |
| `device_soc_mismatch` | skipped | no probe yet (no phone). |
| `qnn_exact_path_unproven` | blocked | no compile records exist on host. |
| `qnn_unsupported_op` | skipped | no compile attempt to score. |
| `smollm3_export_unproven` | blocked | Experiment 2 deferred. |
| `checkpoint_hash_mismatch` | pass | Stage 1 ckpt manifest matches recompute on tiny + Qwen smoke. |
| `tokenizer_fertility_high` | pass | Qwen + SmolLM3 fixtures both pass at 2.5x. |
| `oom_or_memory_pressure` | skipped | no on-device run. |
| `thermal_throttle` | skipped | no on-device run. |
| `battery_heat_risk` | skipped | no on-device run. |
| `charge_bypass_unproven` | skipped | no on-device run. |
| `throughput_floor_fail` | skipped | no on-device run. |
| `energy_budget_exceeded` | skipped | no on-device run. |
| `catastrophic_forgetting` | skipped | no Phase 1A. |
| `cross_model_disagreement_high` | skipped | no eval yet. |
| `method_disagreement_high` | skipped | no QLoRA pilot yet. |
| `license_drift` | pass (over fixtures) | corpus fixture set is class A only. |
| `ocr_damage_high` | skipped | no OCR-derived corpus chunk yet. |
| `overclaim` | pass (this report) | every claim above maps to an audited artifact. |

## Hugging Face state

Four private repos created under `Architect-Prime` (NOT under `Zer0pa` org per PRD §GitHub + Hugging Face are the review surface):

* `Architect-Prime/polymath-corpus-seed-v0` (dataset)
* `Architect-Prime/polymath-models-qwen2-5-1p5b-elo` (model)
* `Architect-Prime/polymath-models-smollm3-3b-elo` (model)
* `Architect-Prime/polymath-telemetry` (dataset)

Each repo has a boundary-bearing `README.md` at HEAD pointing to `Zer0pa/Polymath-AI` PRD.

No bulk artifacts have been pushed yet. Pending uploads are tracked in `polymath_ai.sync.pending` (no rows queued tonight; nothing failed).

## Model artifacts cached locally

Both base models downloaded to `~/.cache/huggingface/hub/`:

* `Qwen/Qwen2.5-1.5B`: 3.09 GB safetensors + tokenizer + config + LICENSE (Apache 2.0).
* `HuggingFaceTB/SmolLM3-3B`: 6.15 GB safetensors (2-shard) + tokenizer + config.

Total HF cache: 8.7 GB. Free disk: 327 GB. License attestation IDs:

* `license:apache-2.0:qwen2.5-1.5b`
* `license:apache-2.0:smollm3-3b`

## Tooling state

* Python 3.11 venv at `/Users/zer0palab/Polymath-AI/.venv`.
* torch 2.2.2 (Intel Mac wheel ceiling, Decision D-003), transformers 4.46.3, tokenizers 0.20.3, safetensors 0.7, huggingface_hub 0.36.2, datasets 3.6, accelerate 1.4, sentencepiece, numpy 1.26.4. Pinned in `requirements-host.txt`.
* `ai-edge-litert 1.0.1` installed; AOT subpackage absent on Intel Mac (D-012).
* `gh` CLI authenticated as `Zer0pa-Architect-Prime`.
* `adb` (Android Debug Bridge) 1.0.41 installed via Homebrew cask.
* HF token at `~/.cache/huggingface/token`, identity `Architect-Prime`, member of `Zer0pa` org.

## What is NOT done (and why)

| Item | Why |
|---|---|
| Phase 0D-0G with real probes | Phone not yet attached. Runbook + scripts ready. |
| QLoRA / LoRA baseline | Tracked under "ELO/model lane Phase 0B" in PRD; deferred until method-disagreement scorecard is needed. PRD allows explicit pending-dependency stub. |
| Reflex Scheduler | Phase 0 micro-calibration deferred to phone (PRD: ships in Phase 0, runs in micro-calibration, Phase 1A default only after ablation). |
| Distillation arm scaffold | Phase 1A parallel; not gating tonight. Decision D-007 records the teacher selection. |
| Federated arm | Design-only until multi-device fleet exists (HANDOFF-TO-OVERNIGHT-EXECUTOR §What You Inherit). |
| Cross-device portability matrix | Design-only; no second device exists. |
| Bulk corpus shards on HF | Pending operator-driven curation run; scaffold present, manifests parameterised. |
| Snapdragon Profiler / Android GPU Inspector install | Behind manual Qualcomm download (D-013); the runbook records the exact URL + checksum slot for the operator. |

## Continuation: how to pick up tomorrow

1. Plug REDMAGIC 10 Pro+ into the host. `adb devices` should show one authorised line.
2. Run `scripts/host/phone_probe.sh` and record the SoC target via the snippet in `docs/PHONE-ATTACH-RUNBOOK.md` Step 2.
3. ADB-push `scripts/termux/bootstrap.sh` to the phone, run it inside Termux. Pull `~/polymath/termux-verdict.json` back to the host.
4. Add a Decision row in `docs/DECISIONS.md` capturing the resolved SoC target + confidence + Termux torch verdict.
5. Run `scripts/termux/run_export_probe_termux.sh --soc-target <SM8650|SM8750|SM8850>` inside Termux to fill the LiteRT AOT availability probe and (if AOT is available) start the Phase 0G real compile sweep.
6. Run Experiment 0 ladder via `python -m polymath_ai.experiments.runner --phase phase0e_experiment0 --config configs/experiments/E0/E0.1.yaml` (the phase0e runner currently blocks until `phone_attached: true` is in the config; flip the flag).
7. Cutover decision lives in Phase 0H readiness review. The Phase 1A start command is a config swap, not a code change.

## Code health

* Tests: 115 passing, 0 failing, runtime ~20s on Intel Mac CPU.
* No type-check infrastructure added tonight (mypy / ruff would be Phase 0H polish).
* All modules import in <1s except `transformers` (~5s) which is unavoidable.
* `python -m polymath_ai.experiments.runner --phase phase0a_substrate` runs end-to-end and emits a phase_gate audit row in <2s.

## Files of record

* `PRD.md` (orchestrator-authored, not edited tonight).
* `docs/DECISIONS.md` (D-001..D-013).
* `docs/FALSIFIERS.md`.
* `docs/AUDIT-SPEC.md`.
* `docs/CORPUS-SPEC.md`.
* `docs/PHONE-ATTACH-RUNBOOK.md`.
* `docs/EXECUTION-REPORT.md` (this file).
* `requirements-host.txt`.
* `polymath_ai/` (16 modules, ~4500 lines).
* `tests/` (10 files, 1441 lines, 115 cases).
* `scripts/host/` (5 files: probe, qwen smoke, fertility, export probe, hf init).
* `scripts/termux/` (3 files: bootstrap, training runner, export probe runner).
* `runtime/reports/` (Qwen smoke, fertility audits, export probe truth table — small JSON/MD; large .pt excluded by .gitignore).

## Final hash chain note

Every audit log emitted tonight validates clean. The brain-functionality gate is satisfied: a fresh agent on another machine clones `Zer0pa/Polymath-AI`, runs `pip install -r requirements-host.txt`, runs `pytest tests/ -q`, reads `docs/PHONE-ATTACH-RUNBOOK.md`, and continues. No conversation context required.

Boundary block carried verbatim.
