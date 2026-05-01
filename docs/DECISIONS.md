# Decision Log

**Boundary:** Research infrastructure for in silico on-device LLM training and multilingual / multi-domain knowledge model construction. Outputs are research artifacts - model checkpoints, training telemetry, evaluation reports, throughput measurements. No regulatory certification claims. No clinical or human-subject use. No surveillance, biometric profiling, or identity inference. No model weights distributed without explicit license attestation. No training on copyrighted material without explicit corpus-license decomposition. No deployment to production without a falsifier-traced acceptance gate.

Format per row (PRD §Audit Trail And KG Specification > Decision Log):

- `decision id`
- `timestamp` (UTC ISO-8601)
- `agent_role`
- `context`
- `options considered`
- `decision`
- `strongest disconfirming observation`
- `affected configs/artifacts`
- `follow-up owner`

---

## D-001 — Untie `lm_head.weight` from `embed_tokens.weight` for Qwen2.5-1.5B

- **timestamp:** 2026-05-01T03:14:00Z
- **agent_role:** overnight-executor (Claude Opus 4.7)
- **context:** Qwen2.5-1.5B (and most modern small LMs in this size class) ship with weight-tied `lm_head` and `embed_tokens`. The PRD §Training Method Specification ELO default is "embeddings frozen, lm_head trainable." With tied weights, that combination is impossible — they are the same tensor.
- **options considered:**
  1. Drop `lm_head` from the trainable set (faithful tie-respecting freeze).
  2. Drop the "freeze embeddings" rule and accept that lm_head training will retrain the embeddings (tie-respecting but inverts PRD intent).
  3. Untie before applying the freeze plan: clone `lm_head.weight` so the two parameters become independent tensors, then freeze embeddings + train lm_head.
- **decision:** Option 3 (untie). The PRD's ELO contract is materially different if lm_head is dropped, and silently retraining embeddings violates the operator's stated default. Untying costs ~150 MiB BF16 / ~300 MiB FP32 per model — well within the 24 GB budget. Implemented in `polymath_ai.models.adapters.untie_lm_head_if_tied()`, called automatically by `apply_freeze_plan()` when the plan has `freeze_embeddings=True` AND `train_lm_head=True`.
- **strongest disconfirming observation:** if Stage 2 alignment shows the untied lm_head diverges from the embedding table in a way that materially harms English perplexity (catastrophic-forgetting falsifier > 1pp), reconsider option 2.
- **affected configs/artifacts:** `polymath_ai/models/adapters.py`, `tests/test_elo.py`, every Stage 1 checkpoint.
- **follow-up owner:** ELO/model lane.

---

## D-002 — Phase 1A language mix concrete allocation

- **timestamp:** 2026-05-01T03:15:00Z
- **agent_role:** overnight-executor
- **context:** PRD §Seed Corpus v0 > Language Mix gives group-level targets (en 30%, high-resource European 25%, CJK 15%, AR/RU/HI 15%, African/low-resource 10%, classical 5%) but no concrete per-language allocation. The orchestrator deferred concrete allocation to the executor.
- **options considered:**
  1. Equal split within each group.
  2. Fertility-weighted split (more compute budget for languages with higher tokens/word).
  3. Resource-availability-weighted split (more budget for languages with more available CC-licensed text).
- **decision:** Approximation of resource-availability split, codified in `polymath_ai/corpus/manifest.py:_LANGUAGE_MIX_PHASE1A`. en 30%, fr/es/de 7-6-6%, it/pt 3-3%, zh/ja/ko 7-5-3%, ar/ru/hi 5-5-5%, sw/zu/af 4-3-3%, la/el 2.5-2.5%. Sums to 1.0 by construction.
- **strongest disconfirming observation:** if Experiment 1 fertility audit shows a language above 2.5x English, this split must be revised before Phase 1A — a `tokenizer_fertility_high` falsifier hit is the trigger.
- **affected configs/artifacts:** `polymath_ai/corpus/manifest.py`, future Phase 1A corpus manifests.
- **follow-up owner:** Corpus lane.

---

## D-003 — Intel Mac torch ceiling pinned to 2.2.2

- **timestamp:** 2026-05-01T03:00:00Z
- **agent_role:** overnight-executor
- **context:** This dev machine is an Intel Mac (x86_64). PyTorch dropped Intel macOS wheels after 2.2.x. The latest transformers (5.x) requires torch >= 2.4. NumPy 2.x is incompatible with torch 2.2.
- **options considered:**
  1. Pin torch 2.2.2 + transformers 4.46.x + numpy 1.26.x.
  2. Build torch from source on Intel Mac.
  3. Use Conda's `pytorch-cpu` channel (still pinned to 2.2.x for Intel anyway).
- **decision:** Option 1. requirements-host.txt documents the pin and notes that Apple Silicon / Linux hosts can raise torch to 2.5+ in lockstep. None of the substrate code uses APIs added after torch 2.2; if it ever does, the host pin must rise in lockstep.
- **strongest disconfirming observation:** if a required package only ships wheels for torch >= 2.4 (e.g. a new transformers version with a feature we need), revisit and either find a workaround or escalate to operator for Apple Silicon machine.
- **affected configs/artifacts:** `requirements-host.txt`, the entire Mac venv. Termux stack uses an independent pin.
- **follow-up owner:** Repo substrate lane.

---

## D-004 — Default freeze plan is `(0, n-1) + lm_head` with embeddings frozen

- **timestamp:** 2026-05-01T03:30:00Z
- **agent_role:** overnight-executor
- **context:** PRD §Training Method Specification gives the default trainable set: layer 0, layer 27, lm_head, embeddings frozen by default with embedding-unfrozen ablation later. The synthesis flagged the ablation but the orchestrator left it open.
- **decision:** `FreezePlan(trainable_layer_indices=(0, n-1), freeze_embeddings=True, train_lm_head=True, policy_name="elo_first_last")` is the canonical Stage 1 default. Embedding-unfrozen ablation is reachable as `policy_name="elo_first_last_unfrozen_embed"` but lives outside Phase 0 / Phase 1A scope.
- **strongest disconfirming observation:** if a target language has tokenizer fertility above 2.5x English AND embeddings remain frozen, the boundary layers cannot remap embedding-level tokens; this would surface as worse-than-baseline target-language perplexity.
- **affected configs/artifacts:** all Phase 0B / 1A configs.
- **follow-up owner:** ELO/model lane.

---

## D-005 — Phone-arrival path is config-flag-shaped, not runtime branching

- **timestamp:** 2026-05-01T03:35:00Z
- **agent_role:** overnight-executor
- **context:** Phone is not present at execution start. The PRD requires the cutover from "no phone" to "phone attached" to be a config-flag change, not a code rewrite.
- **decision:** `device_state.phone_attached` is a Boolean field on every envelope. Phase 0D, 0E, 0F (when measured on the phone), 0G, and 0H gate on `phone_attached=true`. The host runs every dev-machine phase against simulated probes (ADB output parsed from fixtures, not from a real phone). Phone-attach runbook is `docs/PHONE-ATTACH-RUNBOOK.md`.
- **strongest disconfirming observation:** if the phone exposes a probe shape we did not anticipate (e.g. profiler counter naming we cannot parse), the runbook must be revised but the boundary-, audit-, and falsifier-shape are unchanged.
- **affected configs/artifacts:** every envelope, `docs/PHONE-ATTACH-RUNBOOK.md`, `scripts/host/phone_probe.sh`, `scripts/termux/termux_probe.sh`.
- **follow-up owner:** Device lane.

---

## D-006 — SoC probe is mandatory before any QNN compile

- **timestamp:** 2026-05-01T03:40:00Z
- **agent_role:** overnight-executor
- **context:** Blueprint cites `SM8650` / "Snapdragon 8 Elite" ambiguously. PRD §Hard SoC identity gate forbids QNN compile against a guessed SoC. Newer Snapdragon 8 Elite Gen 5 reports SM8850, not SM8650.
- **decision:** `polymath_ai.device.probe.soc_target_from_reported(reported)` returns `(target, confidence)`. Confidence < 1.0 means the executor must perform an additional probe-side AOT compile attempt against alternative targets before enabling QNN. `device_soc_mismatch` falsifier blocks QNN if the probe contradicts the configured target. The phone-attach runbook makes the probe step blocking.
- **strongest disconfirming observation:** if the reported SoC string is something neither `SM8650`, `SM8750`, nor `SM8850`, fallback to CPU/GPU and log `qnn_exact_path_unproven`.
- **affected configs/artifacts:** `polymath_ai/device/probe.py`, `docs/PHONE-ATTACH-RUNBOOK.md`, every QNN compile attempt envelope.
- **follow-up owner:** Device lane + Export lane.

---

## D-007 — Distillation arm uses Qwen3-Next-80B-A3B-Instruct on Runpod, fallback Qwen2.5-72B

- **timestamp:** 2026-05-01T03:45:00Z
- **agent_role:** overnight-executor
- **context:** PRD §Distillation Arm picks Qwen3-Next as primary teacher (Apache 2.0, sparse-active economics) with Qwen2.5-72B as fallback. Phase 0 only scaffolds; actual teacher generation is Phase 1A parallel arm.
- **decision:** Repo carries a teacher-config skeleton at `configs/distillation/teacher.yaml` (deferred — created when the executor reaches Phase 1A scaffolding). For the overnight run this stays a documented intent, not active scaffolding, since neither phone nor Runpod is the gating path tonight.
- **strongest disconfirming observation:** if Qwen3-Next license terms change, fall back to Qwen2.5-72B with explicit license attestation.
- **affected configs/artifacts:** future `configs/distillation/`, future Phase 1A run logs.
- **follow-up owner:** Distillation lane.

---

## D-008 — Pending-upload manifests are the HF-token-absent fallback, never silently dropped

- **timestamp:** 2026-05-01T03:50:00Z
- **agent_role:** overnight-executor
- **context:** PRD §Phone To GitHub And Hugging Face Artifact Exfiltration: when HF push fails or token is absent, the artifact must be queued so a future agent can flush.
- **decision:** `polymath_ai.sync.pending.PendingUploadStore` writes append-only JSONL with sha256, size, and intended HF target. Each row carries the boundary envelope. Tested in `tests/test_pending_uploads.py`. Never silent: every blocked upload goes through this.
- **strongest disconfirming observation:** if a future agent flushes a pending row but the on-disk artifact's sha256 has drifted from the manifest, it is a `checkpoint_hash_mismatch` (the flusher must verify before pushing).
- **affected configs/artifacts:** `polymath_ai/sync/pending.py`, every artifact upload path.
- **follow-up owner:** Sync lane.

---

## D-009 — Tokenizer fertility audit ships with Seed Corpus v0 fixture samples; phone runs full audit

- **timestamp:** 2026-05-01T03:55:00Z
- **agent_role:** overnight-executor
- **context:** Phase 0F (Experiment 1) is tokenizer fertility per-language. The Seed Corpus v0 source list is locked but the actual text corpus is bulk-only on HF. The host machine ships fertility plumbing + tiny per-language fixtures so the gate can be exercised before the phone arrives.
- **decision:** Fertility module (`polymath_ai/corpus/fertility.py`) is pure-Python with a tokenizer-agnostic encode path. Sample fixtures live in `data/fixtures/fertility/<lang>.txt` (CC0 / public-domain only). Full Phase 0F audit runs against the HF Seed Corpus v0 dataset, after the phone is attached or whenever the operator consents to the bulk download on the host.
- **strongest disconfirming observation:** if a fixture-level audit passes but the full-corpus audit shows a language above 2.5x, the falsifier fires and Phase 1A is blocked.
- **affected configs/artifacts:** `polymath_ai/corpus/fertility.py`, `data/fixtures/fertility/`, future Phase 0F report.
- **follow-up owner:** Corpus + Eval lanes.

---

## D-010 — Termux Python is control-plane first; on-device PyTorch training is measured before assumed

- **timestamp:** 2026-05-01T04:00:00Z
- **agent_role:** overnight-executor
- **context:** PRD §Deep-Research Lookup Verdicts: Termux PyTorch is fragile. Cannot assume Termux PyTorch training works without measurement.
- **decision:** Termux bootstrap installs Python + git + huggingface_hub + tokenizers + safetensors + numpy and *attempts* torch via `pip install torch`. If torch import fails or wheels are unavailable, Termux runs as control plane only: pulls checkpoints from HF, posts progress to GitHub, talks to a host-mediated training process via ADB. Phase 0D records the verdict.
- **strongest disconfirming observation:** the attached phone returns a working PyTorch import + a successful one-step train on a tiny model. Then we promote to on-device training. Until measured, host-mediated is the default.
- **affected configs/artifacts:** `scripts/termux/bootstrap.sh`, `scripts/termux/training_runner.sh`.
- **follow-up owner:** Device lane.

---

## D-012 — LiteRT QNN AOT path absent on Intel Mac wheels; verdict deferred to phone

- **timestamp:** 2026-05-01T04:14:00Z
- **agent_role:** overnight-executor
- **context:** Phase 0C export truth-table requires real LiteRT / QNN compile attempts. On the Intel Mac host, `pip install ai-edge-litert` succeeds (1.0.1) but the `ai_edge_litert.aot` subpackage (and the Qualcomm `SocModel.SM8650 / SM8750 / SM8850` enums) fails to import — Mac x86_64 wheels do not ship the AOT path. Furthermore, `ai-edge-torch` requires torch >= 2.4 and our pinned torch 2.2.2 (Decision D-003) cannot be raised on this machine.
- **options considered:**
  1. Attempt to build LiteRT from source on Intel Mac.
  2. Try a Linux Docker container (no Docker on host per PRD constraints).
  3. Move the host export-probe step to MacSim dry-run only and run real LiteRT + QNN compiles on the phone in Termux (which has the right wheels) or on a separate Linux box.
  4. Defer Phase 0C real-compile rows to phone attach.
- **decision:** Option 4. The host produces the truth-table skeleton with `mac_sim` and `fallback` rows (`stage=stub`); real LiteRT + QNN rows are filled by `scripts/termux/run_export_probe_termux.sh` after Termux bootstrap succeeds. Until that runs, the falsifier `qnn_exact_path_unproven` stays in `blocked` for QNN-target scopes. This is consistent with PRD §Hard SoC identity gate (no QNN compile against a guessed SoC).
- **strongest disconfirming observation:** if the Termux bootstrap also fails to install ai-edge-litert with AOT support on Android arm64-v8a, the QNN path is deferred to a Linux x86_64 host with QAIRT SDK installed; no QNN claim possible until then.
- **affected configs/artifacts:** `polymath_ai/dispatch/export_probe.py`, `runtime/reports/export_probe/`, `scripts/termux/run_export_probe_termux.sh` (to be created on phone arrival).
- **follow-up owner:** Export lane.

---

## D-013 — Qualcomm QNN / QAIRT SDK install behind developer login; not on host

- **timestamp:** 2026-05-01T04:15:00Z
- **agent_role:** overnight-executor
- **context:** Qualcomm AI Engine Direct (QNN) SDK / QAIRT downloads require a Qualcomm Developer Network login and license click-through. No public wheel or brew cask. Mac host cannot install QNN SDK without manual operator action.
- **decision:** Defer. The phone ships with Qualcomm's runtime libraries built into Android (`/system/lib64/libQnn*.so` etc.); we use those on-device via the LiteRT QNN delegate when the Termux bootstrap installs ai-edge-litert with AOT. The host is not a QNN compile target.
- **strongest disconfirming observation:** if the runtime libraries on REDMAGIC 10 Pro+ are too old or not present at all, we will need a Linux x86_64 box with the Qualcomm SDK to AOT-compile binaries that we then push to the phone — that machine does not exist tonight.
- **affected configs/artifacts:** `docs/PHONE-ATTACH-RUNBOOK.md` (Step 7), Phase 0G runner.
- **follow-up owner:** Export lane + Device lane.

---

## D-011 — Pretrained weight downloads cache to ~/.cache/huggingface/hub, never to repo

- **timestamp:** 2026-05-01T03:10:00Z
- **agent_role:** overnight-executor
- **context:** Both Qwen2.5-1.5B (3.09 GB) and SmolLM3-3B (6.15 GB) are now in HF cache. Repo MUST NOT vendor weights.
- **decision:** `.gitignore` already path-anchors `/models/`, `/checkpoints/`, and `*.safetensors`. HF cache stays at `~/.cache/huggingface/hub/` per default. License files for both models recorded in `docs/CORPUS-SPEC.md` and per-model attestation IDs are `license:apache-2.0:qwen2.5-1.5b` and `license:apache-2.0:smollm3-3b`.
- **strongest disconfirming observation:** if a weight file ever ends up under `polymath_ai/` or `runtime/checkpoints/` that is not gitignored, the boundary scanner does not catch it - this is enforced by `.gitignore` discipline only. A pre-commit hook or CI check could harden this further (Phase 0H scope).
- **affected configs/artifacts:** `.gitignore`, `docs/CORPUS-SPEC.md`.
- **follow-up owner:** Repo substrate lane.
