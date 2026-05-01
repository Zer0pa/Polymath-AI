# Handoff to the Apple Silicon Agent — Phase 0G AOT compile only

**Boundary:** Research infrastructure for in silico on-device LLM training and multilingual / multi-domain knowledge model construction. Outputs are research artifacts - model checkpoints, training telemetry, evaluation reports, throughput measurements. No regulatory certification claims. No clinical or human-subject use. No surveillance, biometric profiling, or identity inference. No model weights distributed without explicit license attestation. No training on copyrighted material without explicit corpus-license decomposition. No deployment to production without a falsifier-traced acceptance gate.

**Status:** prepared 2026-05-01 by the overnight executor on the Intel Mac. The Intel Mac cannot run `torch >= 2.4` and therefore cannot run `ai-edge-torch` / `ai-edge-litert` AOT compile. **Apple Silicon agent's job is exactly that one thing**, then hand back.

**Repo:** `Zer0pa/Polymath-AI` at HEAD `a34c934`. Branch `main`.

## Hard scope

You do **only** Phase 0G — the LiteRT/QNN AOT compile sweep — then push results and stop.

Do **not** touch:
- Phase 0A substrate (`polymath_ai/boundary,schemas,audit,kg,falsifiers,sync,utils,scheduler`)
- Phase 0B ELO trainer (`polymath_ai/elo`, `polymath_ai/models`)
- Phase 0E host-mediated runner (still running on the Intel Mac as of this brief)
- Phase 0F fertility (already done)
- The `RESISTANCE.md` / `MODUS-OPERANDI.md` / `PRD.md` / `HANDOFF-TO-*` docs
- Any decision log entries for D-001..D-019

If you discover something that *forces* a change to one of the above, **add a Decision row D-020+ explaining why instead of editing existing rows**.

## What the Intel Mac is doing in parallel

While you run, the Intel Mac continues:
- Letting the in-flight E0.1 host-mediated run finish (5 ELO steps on real Qwen2.5-1.5B; loss already 14.5 → 9.6 across 3 steps; freeze invariant held).
- Possibly E0.2 host-mediated (100K-token version) afterwards.
- Documentation polish, falsifier extension tests, audit-chain validators.

You will not collide. We work on separate sub-trees.

## Read-first (in order)

1. `RESISTANCE.md` — anti-corruption doctrine. Read first. Headspace.
2. `README.md` — workstream overview.
3. `PRD.md` — sections **§Phase 0G - Experiment 2: SmolLM3 QNN Export Verdict**, **§Hard SoC identity gate**, **§Falsifier Registry**, **§Plug-Replaceability Invariant**.
4. `docs/DECISIONS.md` rows **D-006** (SoC probe), **D-012** (LiteRT AOT host unavailability), **D-013** (QAIRT), **D-015** (SoC=SM8750 confidence 1.0), **D-019** (ai-edge-litert no aarch64-android wheel; SSH replaces RUN_COMMAND).
5. `docs/PHASE-0G-PLAN.md` — the three viable paths and the recommended sweep.
6. `polymath_ai/dispatch/export_probe.py` — the runner shape your output must conform to.
7. `polymath_ai/dispatch/adapters.py` — `BackendProbeRecord`, `CompileRecord`, `DelegateReport` dataclasses.
8. `polymath_ai/scheduler/registry.py` — the `litert_qnn_sm8750` backend record (`requires_soc_confirmation=True`, `confirmed_for_socs=()` by design — your job promotes that to `("SM8750", 1.0)` when at least one scope returns ok).

## Environment requirements

- macOS Apple Silicon (M1+) with Python 3.11 or 3.12.
- `pip install torch>=2.4 ai-edge-torch ai-edge-litert transformers tokenizers safetensors huggingface_hub numpy<2`. Apple Silicon has these wheels prebuilt.
- HF token at `~/.cache/huggingface/token` (under Architect-Prime user, NOT Zer0pa org). The Intel Mac uses the same path.
- `gh` CLI authenticated. `gh auth status` should show `Zer0pa-Architect-Prime`.

```bash
# One-line bootstrap
git clone https://github.com/Zer0pa/Polymath-AI && cd Polymath-AI && \
python3.11 -m venv .venv-silicon && \
.venv-silicon/bin/pip install --upgrade pip wheel && \
.venv-silicon/bin/pip install "torch>=2.4" ai-edge-torch ai-edge-litert "transformers<5" "tokenizers<0.21" "huggingface_hub<1.0" safetensors "numpy<2" pytest pyyaml && \
.venv-silicon/bin/python -m pytest tests/ -q   # 126+ tests must still pass
```

If the venv install fails on torch>=2.4, **stop and add a D-row**. Do not downgrade.

## What you produce

For each `(model, scope, target)` triple in the matrix below, attempt the AOT compile and emit one `ExportProbeRecord`-shaped row:

| Model | Scope | Target |
|---|---|---|
| `Qwen/Qwen2.5-1.5B` | `tiny_block` (a single transformer block) | `litert_qnn_sm8750` |
| `Qwen/Qwen2.5-1.5B` | `qwen_block` (one real Qwen block) | `litert_qnn_sm8750` |
| `Qwen/Qwen2.5-1.5B` | `qwen_frozen_subgraph` (layers 1..26 = the ELO frozen middle) | `litert_qnn_sm8750` |
| `HuggingFaceTB/SmolLM3-3B` | `smollm3_block` | `litert_qnn_sm8750` |
| `HuggingFaceTB/SmolLM3-3B` | `smollm3_frozen_subgraph` | `litert_qnn_sm8750` |

Plus the same five against the `cpu` and `vulkan_gpu` targets for falsifier-coverage parity (these can use the existing `MacSimAdapter`/`FallbackAdapter` rather than real compile if you prefer; the `litert_qnn_sm8750` rows are what unlock the gate).

For each AOT attempt, output:
- `compile_record.json` with: `result` (`ok|failed|unsupported|skipped`), `delegate_pct` (float in `[0,1]` or null), `unsupported_ops` (list of op names), `log_path` (path to full compile log), `target` (`SM8750`).
- The full compile stdout/stderr at the path referenced by `log_path`.
- A `delegate_report.json` per scope when a compile succeeds.
- The `.tflite` intermediate (kept for reproducibility; pushed to HF).

## Where outputs go

- **GitHub commit on a topic branch `silicon/phase0g-aot`** under `runtime/reports/export_probe/<utc_timestamp>/`:
  - `summary.json` (envelope-shaped; pass through `polymath_ai.dispatch.export_probe.run_export_probe` if you can, otherwise hand-form it to match `polymath_ai/schemas/records.py`).
  - `truth_table.md` listing every row.
  - `compile_logs/<scope>__<target>.log` per attempt.
  - `compile_records/<scope>__<target>.json` per attempt.
  - **NO .tflite or large binaries in git.** Those go to HF.
- **HF private dataset under Architect-Prime** at `Architect-Prime/polymath-models-qwen2-5-1p5b-elo/exports/qwen-aot/<utc>/` and `Architect-Prime/polymath-models-smollm3-3b-elo/exports/smollm3-aot/<utc>/`:
  - `.tflite` intermediates per scope.
  - QNN binaries when AOT succeeds.
  - License files copied from the base model card so attribution travels with the artifact.

If HF push fails, emit `pending-upload` rows via `polymath_ai.sync.pending` (already imported and tested).

## Decision rows you must add

**D-020 — Phase 0G AOT compile dispatched to Apple Silicon agent.** Records the host platform (e.g. M2 Max + macOS 15), the torch + ai-edge-torch + ai-edge-litert versions installed, the target SoC (must be `SM8750`), and the per-scope verdict.

**D-021** if any scope fails compile. Captures the exact failing op or graph pattern. PRD §Falsifier Registry > `qnn_unsupported_op`: failing scope contributes its op list to that falsifier's evidence.

If `Qwen/qwen_frozen_subgraph` succeeds with high delegate %: add `confirmed_for_socs=(("SM8750", 1.0),)` to `litert_qnn_sm8750` in `polymath_ai/scheduler/registry.py`. That promotion *is* the unblocking event for Phase 1A QNN routing. Tests in `tests/test_scheduler.py` will need to be updated (the `test_qnn_backend_is_locked_until_proof` test is the canary).

If any scope fails: leave the registry locked. Add `D-021` describing the blocker.

## Falsifier outcomes you trigger

- `qnn_exact_path_unproven` flips to `pass` IFF at least one Qwen frozen-middle compile returns `ok` with delegate_pct >= 0.5.
- `qnn_unsupported_op` flips to `fail` if delegate_pct < 0.5 on any scope. Capture the unsupported_ops list.
- `smollm3_export_unproven` resolves to `pass` / `gpu_cpu_eval_only` / `deferred` based on SmolLM3 results.
- Every emitted row carries the boundary envelope (`polymath_ai.boundary.text.boundary_envelope()`).

## Hand-back protocol

1. Push your topic branch: `git push origin silicon/phase0g-aot`.
2. Open a PR with title `Phase 0G AOT compile — <verdict>` and the truth table summary inline (`gh pr create`).
3. **Do not merge yourself.** The Intel Mac agent reviews + merges.
4. Comment on the PR with the **exact next-step command** the Intel Mac should run after merge (it's likely `git pull && python -m pytest tests/test_scheduler.py -q && python -m pytest tests/test_falsifiers.py -q`).
5. Stop. The Intel Mac picks up.

## Out of scope (NOT yours)

- Phase 0E E0.1 / E0.2 / Phase 1A actual training runs.
- Termux / phone-side bootstrap (already done).
- ELO trainer correctness tests (already passing 126/126).
- Documentation outside `docs/PHASE-0G-PLAN.md` and the Decision rows you add.
- Anything that requires the operator's REDMAGIC 10 Pro to be present (the Apple Silicon machine is host-only).

## Cost / time budget

Estimated 1-2 engineer-hours for an experienced operator-of-tools agent. AOT compile of a single Qwen block on Apple Silicon is fast (seconds to minutes); the sweep across 5 scopes × 1 QNN target = 5 compiles. The hand-back PR + Decision rows add ~30 min.

Hard cap: 4 hours. If not done by then, push partial state with whatever scopes succeeded and stop.

## RESISTANCE.md reminders

- `fp-rushtoend`: do not declare Phase 0G "complete" because the script ran. Phase 0G is complete only when at least one scope's CompileRecord proves `ok` with a non-zero delegate, OR every attempted scope is recorded as failed with the failing op named.
- `fp-shapematchRE`: do not promote `confirmed_for_socs` based on a successful `.tflite` conversion alone. The QNN AOT compile (the second step) is what gates promotion.
- `fp-NULLasout`: if the entire matrix fails, that is a real result. Record it. Do NOT loop further; do NOT downgrade scopes; do NOT pretend success.

## Strongest disconfirming observation

If the Apple Silicon `ai-edge-litert` wheel has the AOT subpackage but the Qualcomm SocModel enum lacks `SM8750`, the compile fails immediately with `KeyError: SM8750`. In that case Phase 0G is blocked at the SDK level, not at our model. Record as `D-021` and stop.
