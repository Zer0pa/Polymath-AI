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

## D-015 — REDMAGIC 10 Pro SoC resolved: SM8750 (confidence 1.0)

- **timestamp:** 2026-05-01T12:10:00Z
- **agent_role:** overnight-executor
- **context:** Phone attached and probed. `getprop ro.soc.model` returns `SM8750`; `ro.soc.manufacturer` returns `QTI`. Phone serial FY25013101C8, model NX789J-EEA (REDMAGIC 10 Pro), Android 15.
- **decision:** Phase 0G / Phase 1A QNN target is `SocModel.SM8750` (Snapdragon 8 Elite Gen 4). The blueprint cited `SM8650` (Snapdragon 8 Gen 3, Oct 2024) in error; the actual hardware is the Gen 4 part. Confidence is 1.0 because `ro.soc.model` is the canonical Qualcomm field. `polymath_ai.device.probe._SOC_NAME_TO_TARGET` updated to reflect this. `device_soc_mismatch` falsifier blocks any QNN compile that targets anything other than SM8750.
- **strongest disconfirming observation:** if a future kernel update changes the reported model name, the falsifier will catch it — confidence stays 1.0 only while `ro.soc.model == "SM8750"` exactly.
- **affected configs/artifacts:** `polymath_ai/device/probe.py`, all Phase 0G / Phase 1A QNN compile commands.
- **follow-up owner:** Device + Export lanes.

---

## D-018 — Termux torch+tokenizers bootstrap fails on Rust source-build; pivot to host-mediated + LiteRT for phone-side compute

- **timestamp:** 2026-05-01T13:30:00Z
- **agent_role:** overnight-executor
- **context:** First-pass `scripts/termux/bootstrap.sh` ran on the attached REDMAGIC 10 Pro under Termux Python 3.13.13. The control-plane install hit `tokenizers` (HuggingFace's Rust-backed tokenizer library) which has no aarch64-android pre-built wheel on PyPI. pip fell back to a Cargo source-build, which fired `rustc` at 700% CPU for 2+ minutes per crate, then exited with a partial install. Bootstrap then attempted `transformers` install which depends on the same `tokenizers` and would fail the same way. PRD §Deep-Research Lookup Verdicts already flagged Termux as fragile ("Termux training stack maturity audit"); this is the manifestation.

- **options considered:**
  1. Persist with the rust source-build. Estimated total: 30-60 min on phone CPU; might still fail on memory pressure (Termux + dm3_runner + rustc together; phone had 113 MB free at one point).
  2. Pre-build tokenizers wheel on a Linux x86_64 + cross-compile to aarch64-android. Requires a manylinux-android cross-compile toolchain we don't have.
  3. Drop tokenizers + transformers from the Termux side entirely. Use Termux as control plane only. Run the actual ELO training on the host (host-mediated) until the phone-side LiteRT path is proven via Phase 0G.
  4. Use ai-edge-litert (pre-built binary wheel) for phone-side compute. This is a different runtime than torch but is exactly what PRD §Hard SoC identity gate + §LiteRT QNN path want anyway.

- **decision:** **Option 3 + Option 4 in series.**
  - Phase 0E E0.1 / E0.2 / Phase 0F use **host-mediated**: ELO training runs on host CPU, phone provides live telemetry via ADB (battery temp, thermal zones, mem). Real `phone_attached: true` envelopes; falsifier evaluation against real device state. PRD §Decision D-005 (config-flag-shaped continuation) + D-010 (Termux as control plane) explicitly allow this.
  - Phase 0G + Phase 1A use **LiteRT path** on the phone: install `ai-edge-litert` (pre-built binary wheel; no rust source-build) on Termux, AOT-compile Qwen2.5-1.5B frozen-middle subgraph for SM8750, run on Hexagon NPU. This is the natural path the blueprint always wanted; bypassing torch on Termux is actually cleaner.
  - `scripts/termux/bootstrap_lean.sh` is the new bootstrap: pure-Python + binary-wheel only, no rust. Includes `ai-edge-litert` install attempt and writes verdict.json to /sdcard.

- **strongest disconfirming observation:** if `ai-edge-litert` also lacks an aarch64-android wheel OR if the AOT compile fails on SM8750 in Phase 0G, we fall back to **all compute on host** with the phone reduced to telemetry beacon. That collapses the original "on-device training" thesis but the boundary still holds (research infrastructure for in-silico training on the phone hardware target). At that point the operator would decide whether to swap targets.

- **affected configs/artifacts:** `scripts/termux/bootstrap_lean.sh` (new); `polymath_ai/experiments/phase0e.py` (host-mediated path); `docs/PHONE-ATTACH-RUNBOOK.md` (note the lean bootstrap as primary); `docs/GAME-SPACE-FRIDGE-RUNBOOK.md` (fridge becomes a Phase 1A concern, not Phase 0E).

- **follow-up owner:** Device + Export lanes.

---

## D-017 — Phase 0F (FLORES-200) flags zu + el on Qwen, zu only on SmolLM3 - revise Phase 1A language mix

- **timestamp:** 2026-05-01T13:00:00Z
- **agent_role:** overnight-executor
- **context:** Phase 0F real-corpus tokenizer fertility audit on FLORES-200 dev split (100 sentences/language; 16 target languages; CC-BY-SA-4.0 measurement-only per D-014). Reports at `runtime/reports/fertility/Qwen_Qwen2.5-1.5B/2026-05-01T125835Z/` and `runtime/reports/fertility/HuggingFaceTB_SmolLM3-3B/2026-05-01T125835Z/`.

  | Language | Qwen2.5-1.5B (151k vocab) | SmolLM3-3B (128k vocab) |
  |---|---:|---:|
  | en | 1.00x (baseline) | 1.00x (baseline) |
  | zh | 0.70x | (similar) |
  | ja | 0.60x | (similar) |
  | ko | 0.83x | (similar) |
  | de / es / fr / pt / it | 1.27 - 1.49x | (similar) |
  | af | 1.55x | (similar) |
  | ar | 1.75x | (similar) |
  | sw | 1.92x | (similar) |
  | hi | 1.98x | (similar) |
  | ru | 1.93x | (similar) |
  | **zu** | **2.68x FAIL** | **2.71x FAIL** |
  | **el (Greek)** | **4.38x FAIL** | passes (under 2.5x) |

  Greek under Qwen's BPE blows up to 5.58 tokens/word — its character set is split into byte-level fragments. SmolLM3's tokenizer handles Greek inside its trained budget. Zulu is a hard problem for both: the agglutinative morphology produces long compounds that neither vocab covers well.

- **options considered:**
  1. Drop zu + el from Phase 1A entirely. Redistribute their 5.5pp share back to the other groups. Cleanest, smallest risk, but loses two languages from the first run.
  2. Keep zu + el but pre-train a vocabulary extension (add ~5k-10k Zulu tokens, ~3k Greek tokens). Adds ~6-10 days of pre-CPT vocab-warmup work; not in scope for the first 100M run.
  3. Keep zu + el and oversample them by their fertility ratio. Increases compute budget linearly with the ratio - doable but pushes Phase 1A wall-clock from ~40 h to ~50 h on the same corpus.
  4. Switch Phase 1A primary to SmolLM3-3B for Greek-clean run, keep Qwen as Phase 1A "baseline-without-Greek". Forks the run in two.

- **decision:** **Option 1 for the FIRST run; Option 3 as the planned ablation.**
  - Phase 1A on Qwen2.5-1.5B excludes zu and el. The 5.5pp share goes back to en (anchor) +3, fr/de/es +0.5 each, ar +0.5, ja +0.5, sw +0.5.
  - When SmolLM3-3B is brought up as Candidate B (gated on Phase 0G QNN export verdict), its Phase 1A includes el (it passes) but still excludes zu (still > 2.5x).
  - Vocabulary extension for zu/el is deferred to Phase 1B at earliest.

- **strongest disconfirming observation:** if a downstream eval shows that the EXCLUSION of zu/el degrades cross-lingual transfer to OTHER African / classical languages, the operator may demand the oversample option (3) on a follow-up run.

- **affected configs/artifacts:** `polymath_ai/corpus/manifest.py:_LANGUAGE_MIX_PHASE1A` (revise), Phase 1A corpus manifest, Phase 1B planning.

- **follow-up owner:** Corpus + Eval lanes.

---

## D-016 — REDMAGIC fan, GPU driver, Game Space, profiler observed in pre-bootstrap probe

- **timestamp:** 2026-05-01T12:11:00Z
- **agent_role:** overnight-executor
- **context:** Pre-bootstrap probe of the connected phone surfaced concrete capabilities the blueprint and PRD assumed but had not verified.
- **observed:**
  - `com.google.android.gapid.arm64v8a` installed → Android GPU Inspector available (PRD §Audit Trail And KG Specification wanted this for profiler attach).
  - `com.qualcomm.qti.gpudrivers.sun.api35` installed → official Qualcomm Adreno driver for Android 15.
  - `com.termux` installed (Termux available; need to confirm Termux:API).
  - `ro.vendor.feature.zte_feature_fan_*` properties present (active fan and fan-light controls).
  - `ro.vendor.feature.zte_feature_game_center_*` present (Game Space platform features).
  - `ro.vendor.feature.zte_feature_ccc_temp_threshold = skin,54,battery,45` (skin temp limit 54 °C, battery temp limit 45 °C — these become the operational ceiling for our Phase 0E/1A thermal falsifiers; the existing 42 °C / 60 s `battery_heat_risk` rule keeps a 3 °C safety margin under the OEM cap).
  - 27 thermal zones readable without root via `/sys/class/thermal/thermal_zone*/temp`. Idle readings 27-30 °C across CPU clusters.
  - GPU sysfs (`/sys/class/devfreq/`, `/sys/class/kgsl/kgsl-3d0/`) not readable without root - GPU clock probe will route through the GPU Inspector or `gfxinfo` instead.
  - Battery temperature 23 °C, level 88%, AC powered, `Charging state: 0` — strong signal that Charge Separation / bypass charging is already active by default on this device + charger combo. Will confirm explicitly via the OEM Settings app at the next probe pass.
- **decision:** No code changes needed. Falsifier register and runbooks already accommodate this state. The OEM caps (skin 54 °C, battery 45 °C) are documented as the upper operational ceiling; our falsifier thresholds (battery 42 °C / 60 s, GPU clock < 600 MHz / >10% window) already sit below them.
- **strongest disconfirming observation:** if `Charging state: 0` is a battery-near-full artifact rather than Charge Separation, plugging in at lower SoC will show actual charging current. The next probe should run at battery < 70 % to disambiguate.
- **affected configs/artifacts:** `docs/PHONE-ATTACH-RUNBOOK.md` (already covers OEM thresholds), `runtime/probes/phone/2026-05-01T121005Z/`.
- **follow-up owner:** Device lane.

---

## D-014 — FLORES-200 used for Phase 0F fertility measurement only

- **timestamp:** 2026-05-01T05:45:00Z
- **agent_role:** overnight-executor
- **context:** Phase 0F (Experiment 1) tokenizer fertility audit needs license-clean parallel multilingual text. FLORES-200 (`facebook/flores`, `openlanguagedata/flores_plus`) is the canonical multilingual benchmark — 1012 parallel sentences across 200+ languages, identical content per language, perfect for like-for-like fertility comparison. License: CC-BY-SA-4.0.
- **options considered:**
  1. OSCAR-2301 (CC0) — class A, but content is unfiltered web crawl; per-language quality varies wildly and content is NOT parallel.
  2. C4 / mC4 (ODC-BY) — class B, large but unstructured for parallel comparison.
  3. FLORES-200 (CC-BY-SA-4.0) — class C; parallel content, ideal for fertility, but share-alike-contagious for derivative work.
  4. Universal Declaration of Human Rights (the existing fixture path) — public domain, parallel, but only one ~250-word document per language.
- **decision:** FLORES-200 for *fertility measurement*. Fertility is a tokenizer evaluation, not a derivative-text product; attribution is preserved in the fertility report; no FLORES text enters Phase 1A training. PRD §License Classes lets class C through with a decision row, scoped to measurement. The fixture-path UDHR audit remains as the offline / no-network baseline. **FLORES-200 cannot enter Phase 1A default training** — it stays in the "measurement-only" bucket.
- **strongest disconfirming observation:** if a downstream artifact (e.g. a fine-tuned model card) cites a FLORES-derived signal in a way that constitutes a derivative work under share-alike, then FLORES must be removed from that artifact pipeline.
- **affected configs/artifacts:** `polymath_ai/experiments/phase0f.py`, `scripts/host/run_fertility_audit.py` (extended with `--source flores200`), Phase 0F report.
- **follow-up owner:** Corpus + Eval lanes.

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
