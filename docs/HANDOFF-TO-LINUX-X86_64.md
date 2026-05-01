# Handoff to the Linux x86_64 Agent — Phase 0G AOT compile only

**Boundary:** Research infrastructure for in silico on-device LLM training and multilingual / multi-domain knowledge model construction. Outputs are research artifacts - model checkpoints, training telemetry, evaluation reports, throughput measurements. No regulatory certification claims. No clinical or human-subject use. No surveillance, biometric profiling, or identity inference. No model weights distributed without explicit license attestation. No training on copyrighted material without explicit corpus-license decomposition. No deployment to production without a falsifier-traced acceptance gate.

**Status:** prepared 2026-05-01 by the Intel Mac executor after the Apple Silicon executor completed the matrix and proved Phase 0G is **blocked at the SDK level on macOS arm64** (D-021: `apply_plugin_main` native binary absent in `ai-edge-litert==2.1.4` macOS arm64 wheel). The Linux x86_64 wheel ships it. Your job is to redo the matrix on a Linux x86_64 host where AOT actually works, then hand back.

**Repo:** `Zer0pa/Polymath-AI` at HEAD `0502eec` (post-merge of `silicon/phase0g-aot`).

## Hard scope

You do **only** Phase 0G — the LiteRT/QNN AOT compile sweep — then push results and stop.

Do **not** touch:
- Phase 0A substrate (`polymath_ai/{boundary,schemas,audit,kg,falsifiers,sync,utils,scheduler}`)
- Phase 0B ELO trainer (`polymath_ai/{elo,models}`)
- Phase 0E host-mediated runner (just finished its E0.1 cleanly on the Intel Mac; loss 14.5→4.4 over 5 steps, freeze invariant held)
- Phase 0F fertility audits (already done; D-017 dropped zu+el)
- The doctrine docs (`RESISTANCE.md`, `MODUS-OPERANDI.md`, `PRD.md`, `HANDOFF-TO-*`)
- Decision rows D-001..D-021. If you discover something that *forces* a change, **add D-022+ explaining why instead of editing existing rows**.

## What changed since the Apple Silicon attempt

Read `runtime/reports/export_probe/2026-05-01T150027Z/truth_table.md` — the existing artifact records the Silicon agent's matrix. All 5 QNN scopes returned `unsupported` at the same failure stage `aot_compile_sdk_binary_missing`. Their per-scope CompileRecord JSONs are at `runtime/reports/export_probe/2026-05-01T150027Z/compile_records/`. The full failure logs are at `compile_logs/`. Your output goes under a NEW timestamp.

The `silicon/phase0g-aot` script at `scripts/silicon/run_phase0g_aot.py` is reusable on Linux with light adaptation — the convert step is identical, only the AOT binary path resolves differently on Linux. **Strongly prefer reusing that script** rather than writing a new one.

## Read-first (in order)

1. `RESISTANCE.md` — anti-corruption doctrine. Read first.
2. `docs/HANDOFF-TO-LINUX-X86_64.md` — this file.
3. `docs/HANDOFF-TO-APPLE-SILICON.md` — the prior brief (do not re-execute it; it's context).
4. `docs/PHASE-0G-PLAN.md` — the three viable paths.
5. `docs/DECISIONS.md` rows D-006, D-012, D-013, D-015, D-019, **D-020** (Silicon host capture), **D-021** (Silicon SDK blocker).
6. `runtime/reports/export_probe/2026-05-01T150027Z/truth_table.md` — Silicon's matrix.
7. `scripts/silicon/run_phase0g_aot.py` — the runner script you'll reuse.
8. `polymath_ai/dispatch/export_probe.py`, `polymath_ai/scheduler/registry.py` — output shape + the registry you may promote.

## Environment requirements

- Linux x86_64 (Ubuntu 22.04 / 24.04, Debian 12, Rocky 9 — anything with glibc >= 2.34).
- Python 3.11 or 3.12.
- `pip install torch>=2.4 ai-edge-torch ai-edge-litert transformers tokenizers safetensors huggingface_hub numpy<2`.
- HF token at `~/.cache/huggingface/token` (Architect-Prime user, NOT the Zer0pa org).
- `gh` CLI authenticated against `Zer0pa-Architect-Prime`.

```bash
# One-line bootstrap (Runpod CPU pod or any Linux x86_64 box)
git clone https://github.com/Zer0pa/Polymath-AI && cd Polymath-AI && \
python3.11 -m venv .venv-linux && \
.venv-linux/bin/pip install --upgrade pip wheel && \
.venv-linux/bin/pip install "torch>=2.4" ai-edge-torch ai-edge-litert "transformers<5" "tokenizers<0.21" "huggingface_hub<1.0" safetensors "numpy<2" pytest pyyaml && \
.venv-linux/bin/python -m pytest tests/ -q   # 126+ tests must pass
```

## Sanity check the SDK BEFORE running the matrix

The whole point of running on Linux x86_64 is the AOT plugin binary. Verify it is actually present:

```bash
.venv-linux/bin/python -c "
import ai_edge_litert
import os, glob
pkg = os.path.dirname(ai_edge_litert.__file__)
print('ai_edge_litert root:', pkg)
candidates = glob.glob(os.path.join(pkg, '**', 'apply_plugin_main*'), recursive=True)
print('apply_plugin_main candidates:', candidates)
from ai_edge_litert.aot import aot_compile  # must NOT raise FileNotFoundError on import
from ai_edge_litert.aot.vendors.qualcomm import target as qnn_target
print('QNN SocModel members:', [m for m in dir(qnn_target.SocModel) if not m.startswith('_')])
assert hasattr(qnn_target.SocModel, 'SM8750'), 'SM8750 missing from this wheel'
print('SM8750 enum present')
"
```

If this fails or `apply_plugin_main` is absent, **stop** and add a Decision row D-022 with the exact wheel version and OS detail. Do not try to install patched versions; report the platform-level state and stop.

## Run the matrix

Same matrix as `docs/HANDOFF-TO-APPLE-SILICON.md` §"What you produce". Five `(model, scope)` triples against `litert_qnn_sm8750`:

| Model | Scope |
|---|---|
| `Qwen/Qwen2.5-1.5B` | `tiny_block` (a single transformer block, random init) |
| `Qwen/Qwen2.5-1.5B` | `qwen_block` (one real Qwen block, random init from real config) |
| `Qwen/Qwen2.5-1.5B` | `qwen_frozen_subgraph` (layers 1..26 = the ELO frozen middle) |
| `HuggingFaceTB/SmolLM3-3B` | `smollm3_block` (one real SmolLM3 block) |
| `HuggingFaceTB/SmolLM3-3B` | `smollm3_frozen_subgraph` (frozen subgraph; reduce layer count if RAM tight, annotate in record) |

Reuse `scripts/silicon/run_phase0g_aot.py` — just pass a NEW output directory (the Silicon dir is now read-only artifact). Output goes under `runtime/reports/export_probe/<utc_timestamp>/` on a fresh topic branch `linux/phase0g-aot`.

## Per-scope output (same shape as Silicon)

For each AOT attempt, emit:
- `compile_records/<scope>__<target>.json` — `result` (`ok|failed|unsupported|skipped`), `delegate_pct` (float `[0,1]`), `unsupported_ops` (list when delegate < 1.0), `target` (`SM8750`), full `meta` block.
- `compile_logs/<scope>__<target>.log` — full stdout/stderr.
- `delegate_report.json` per scope when AOT succeeds.
- `tflite/<scope>.tflite` — kept locally; HF-bound, NOT committed.

Plus aggregated `summary.json` + `truth_table.md` carrying the boundary envelope.

## Where outputs go

- **GitHub branch `linux/phase0g-aot`**: small JSON/MD only under `runtime/reports/export_probe/<utc>/` (`.gitignore` already excludes `*.tflite` from being staged).
- **HF private under Architect-Prime**: `.tflite` intermediates + QNN binaries. The model repos exist (`init_hf_repos.py` created them earlier under D-008 / EXECUTION-REPORT.md):
  - `Architect-Prime/polymath-models-qwen2-5-1p5b-elo` (model, private)
  - `Architect-Prime/polymath-models-smollm3-3b-elo` (model, private)
  
  If `HfApi().repo_info(...)` returns 404 to your token (the Silicon agent reported this — likely a token-scope difference), call `HfApi().create_repo(..., private=True, exist_ok=True)` BEFORE pushing. Path-in-repo: `exports/qwen-aot/<utc>/...` and `exports/smollm3-aot/<utc>/...`.

If HF push fails, emit `pending-upload` rows via `polymath_ai.sync.pending` (Silicon agent's pending_uploads.jsonl is the template).

## Decision rows you must add

**D-022** — Phase 0G AOT compile redone on Linux x86_64. Records the host platform (e.g. Ubuntu 22.04, Runpod RTX-A4000 instance), the torch + ai-edge-torch + ai-edge-litert versions, the per-scope verdict.

If at least one Qwen scope returns `ok` with `delegate_pct >= 0.5`:
- Promote `litert_qnn_sm8750.confirmed_for_socs` to `(("SM8750", 1.0),)` in `polymath_ai/scheduler/registry.py`.
- Update `tests/test_scheduler.py::test_qnn_backend_is_locked_until_proof` and `test_static_policy_qnn_blocked_by_soc_lock` to verify the post-promotion shape.
- This **is** the unblocking event for Phase 1A QNN routing. The `qnn_exact_path_unproven` falsifier flips from `blocked` to `pass` for that scope.

If any QNN scope fails: add D-023 capturing the failing op or graph pattern. The unsupported_ops list feeds the `qnn_unsupported_op` falsifier.

## Hand-back protocol

1. Push the topic branch: `git push origin linux/phase0g-aot`.
2. Open a PR titled `Phase 0G AOT compile — <verdict>` with the truth table inline.
3. **Do NOT merge.** The Intel Mac agent reviews + merges.
4. Comment on the PR with the exact next-step command (likely `git pull && python -m pytest tests/test_scheduler.py tests/test_falsifiers.py -q`).
5. Stop.

## Out of scope (NOT yours)

- Phase 0E / 0F / Phase 1A actual training runs.
- Termux / phone-side bootstrap.
- Pushing model weights anywhere other than the two Architect-Prime model repos.
- Anything that requires the operator's REDMAGIC 10 Pro to be present.
- Anything that bypasses the falsifier registry's `boundary_violation` / `license_drift` checks.

## Cost / time budget

Estimated **30-90 min** on a Runpod CPU pod (~$0.50-1.50). The convert step is identical to Silicon's run (same `litert_torch.convert(...)`); only the AOT step now actually executes instead of failing at `apply_plugin_main`. Five compiles × <5 min each + the boilerplate.

Hard cap: 4 hours. If not done by then, push partial state with whatever scopes succeeded and stop.

## RESISTANCE.md reminders

- `fp-rushtoend` — Phase 0G is complete only when at least one scope returns `ok` with non-zero delegate, OR every scope is recorded as failed with the named failing op. The convert step succeeding alone is not enough.
- `fp-shapematchRE` — `.tflite` conversion working is **not** Phase 0G success. The QNN AOT compile is the gate.
- `fp-NULLasout` — if the matrix fails identically on Linux as it did on macOS arm64, that is a real and important result. Record it (D-023). Do not loop, do not downgrade scopes, do not pretend success.
- `fp-flatteryasfreedom` — the Silicon agent's clean RESISTANCE.md discipline is the standard. Match it.

## Strongest disconfirming observation

If `apply_plugin_main` is present but the AOT compile fails with `KeyError: SM8750` or similar, the Qualcomm AOT vendor plugin doesn't actually ship the SM8750 binary on this wheel. That's a real SDK gap (different from the apply_plugin_main absence on macOS) and gets its own D-row.

If `apply_plugin_main` is present AND `SM8750` is in the enum AND compile still fails: that would be a Polymath-side issue (graph shape, op coverage). Capture the unsupported op list — that's gold.

## Existing artifact you are building on

`scripts/silicon/run_phase0g_aot.py` is 761 lines. It does:
- Subprocess-isolated per-scope runs (necessary on a 16 GB M1; less critical on a Linux box with more RAM).
- Per-scope record + log + tflite output.
- Aggregated summary + truth table.
- HF push attempt with pending-upload fallback.
- Boundary envelope on every record.

Reuse it. Patch the parts that need changing (probably very few — the hostname / venv / output dir are CLI args). If the script needs a Linux-specific tweak, document it in D-022.
