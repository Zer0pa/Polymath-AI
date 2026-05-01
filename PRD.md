# PRD - Zer0pa Polymath AI On-Device Training Workstream

**Status:** Orchestrator PRD v1.0, 2026-05-01  
**Repository:** `Zer0pa/Polymath-AI`  
**Primary execution target:** Operator's REDMAGIC 10 Pro+ with Snapdragon 8 Elite, 24GB LPDDR5X  
**Next role:** Overnight executor on a separate machine, operating from GitHub and preparing all dev-machine work before receiving or attaching the phone  
**Operating doctrine:** Anti-MVP, anti-toy, 110% pre-device-corpus-investment, fork-and-own with no runtime co-dependency, RESISTANCE.md binding

## Boundary

Research infrastructure for in silico on-device LLM training and multilingual / multi-domain knowledge model construction. Outputs are research artifacts - model checkpoints, training telemetry, evaluation reports, throughput measurements. No regulatory certification claims. No clinical or human-subject use. No surveillance, biometric profiling, or identity inference. No model weights distributed without explicit license attestation. No training on copyrighted material without explicit corpus-license decomposition. No deployment to production without a falsifier-traced acceptance gate.

This boundary is binding on every artifact, source file, log, model card, dataset card, evaluation report, checkpoint manifest, Hugging Face upload, KG node, and handoff produced by this workstream. If an artifact cannot carry the full boundary inline because it is a machine-readable record, the record must carry `boundary_id`, `boundary_text_sha256`, and a link to the boundary-bearing manifest that contains the verbatim block above.

## Executive Intent

Polymath is the fifth Zer0pa workstream after Health, Materials, Energy, and Synthetic Biology, and the first non-pipeline-vertical workstream. It is a systems engineering project to train a multilingual and multi-domain language model on the operator's REDMAGIC 10 Pro+ using ELO selective continual pretraining and heterogeneous on-device compute.

The goal is not an MVP, app, first-customer wedge, or production deployment. The success signal is research-publishable evidence: a 1.5B to 3B parameter knowledge model trained or adapted on a personal phone with falsifier-traced quality, telemetry, corpus provenance, license decomposition, energy envelope, and reproducible device measurements.

The overnight executor must work end to end from GitHub without conversation context. If the phone is not physically available at the start of execution, the executor still does the maximum possible work: repo substrate, schemas, tests, Mac-side simulations, package installs, corpus manifests, synthetic slices, export probes, HF/GitHub sync scaffolds, device-attach scripts, and pending-run manifests. When the phone arrives, Phase 0 device calibration is a config-flag-shaped continuation, not a rewrite.

## Orchestrator Fresh-Eyes Decisions

The operator blueprint and synthesis are strong. This PRD adds the executable constraints they did not pin down.

1. **No assumed PyTorch Vulkan training path.** PyTorch/ExecuTorch have active Android, Vulkan, XNNPACK, and Qualcomm AI Engine runtime support, but the standard PyTorch Vulkan path is not a credible full-autograd training backend. ELO correctness must be proven first in ordinary PyTorch on the dev machine. Device acceleration is then introduced through measured adapters: Android CPU baseline, custom Vulkan/ExecuTorch-compatible kernels where available, and QNN/LiteRT inference for frozen subgraphs only.
2. **No assumed QNN acceleration.** QNN/LiteRT support for Qualcomm NPU is real and improving, but exact Qwen2.5-1.5B or SmolLM3-3B frozen-layer delegation is not published as a proven path. QNN is a measured optimization lane with stored compile logs and delegate reports, not a premise.
3. **Hard SoC identity gate.** The executor must probe the actual phone and resolve the target SoC identifier before selecting LiteRT/QNN AOT target. The blueprint uses Snapdragon 8 Elite and SM8650 language; public examples now distinguish SM8850 for newer Snapdragon 8 Elite Gen 5 targets. The PRD forbids compiling against a guessed SoC.
4. **Closed-loop controller, not just pipeline.** The synthesis active-inference reframe is adopted operationally: Polymath is a closed-loop heterogeneous experiment controller. The model, corpus sampler, evaluator, falsifier registry, Reflex Scheduler, and device telemetry form one feedback system.
5. **Reflex Scheduler is implemented before Phase 1A but not allowed to hide the static baseline.** The scheduler ships in Phase 0, runs in micro-calibration, and becomes Phase 1A default only after a static burn-in plus ablation shows it improves tokens/J or tokens/hour without harming determinism, thermals, or validation quality.
6. **Default Seed Corpus v0 is locked now, but license decomposition is still a gate.** Operator engagement selected the default corpus path. The executor may prepare manifests and small slices, but no copyrighted, ambiguous, or unlicensed text enters training. Full corpus archives go to private Hugging Face under the Architect-Prime user, not the Zer0pa org.
7. **REDMAGIC 10 Pro+ is the only real device for Phase 1A.** There is no other phone. Cross-device portability remains a design matrix and publication caveat, not a Phase 1A blocker.
8. **Flower federation is design-only until hardware exists.** No multi-device fleet is available. The PRD specifies a Phase 2 publishable design, not a Phase 1A execution requirement.
9. **Distillation is a parallel research arm, not replacement for ELO.** Use Runpod teacher generation as a comparison and augmentation lane. Prefer Qwen3-Next-80B-A3B-Instruct as the first teacher candidate because of Apache 2.0 and sparse-active economics; keep Qwen2.5-72B as fallback only after license review.
10. **Artifacts must be reconstructible from repo plus HF plus audit/KG, never from chat.** Every run emits hash-chained logs, manifests, and reasoner tuples so a fresh agent can reconstruct state.

## Deep-Research Lookup Verdicts

These verdicts are PRD inputs. The executor must re-check stale items during implementation and record updates in `docs/DECISIONS.md`.

| Item | Verdict | PRD consequence |
|---|---|---|
| ELO codebase availability | No public implementation found via GitHub title/arXiv searches or paper pages. Must reimplement. | Treat ELO as owned implementation risk. Paper-faithful PyTorch reimplementation is Phase 0B before phone work. Estimate 3-5 engineer-days for core Qwen-style implementation, 1-2 weeks for reproducible eval and ablations, more for mobile acceleration. |
| PyTorch Vulkan backend maturity | Active low-level Vulkan code and ExecuTorch Android Vulkan backend exist, but evidence points to inference/runtime acceleration, not general PyTorch training autograd. | Do not rely on `torch.vulkan` for training. Use PyTorch on Mac for correctness, then measured device adapters. |
| Termux training stack maturity | Termux is suitable as control plane and Python shell, but official PyTorch Android training wheels are not guaranteed. `transformers` and compiled deps can be fragile. | Phase 0D includes a Termux stack probe. If PyTorch import/train step fails, build a native Android wrapper or host-mediated training harness instead of blocking. |
| SmolLM3-3B QNN export | No published exact SmolLM3-3B to LiteRT/QNN path found. Likely risk areas: NoPE/RoPE head partitioning, dynamic attention masks, KV cache ops, RMSNorm/SwiGLU lowering, int64 token indexing, reshape/slice/gather/scatter. | Experiment 2 is blocking for SmolLM3 as accelerated Candidate B. If it fails, SmolLM3 becomes GPU/CPU evaluation model only. |
| RedMagic 10 Pro+ thermal characterization | Public data confirms active fan and strong gaming stability, but independent evidence is mixed and no public sustained Adreno 830 fan-on/fan-off clock trace was found. | Treat fan-on as default, but require Snapdragon Profiler trace before Phase 1A. Public marketing clocks are not evidence. |
| REDMAGIC charge-bypass availability | RedMagic OS has Charge Separation / bypass charging in product-family documentation, and REDMAGIC 10 Pro reports support, but the actual 10 Pro+ device must be checked. | Charge Separation ON at 70-80% is a Phase 0 device-readiness gate. If unavailable, use plug-in with scheduled rest and stricter battery thermal limits. |
| `huggingface_hub` push from Android | The Python client supports uploads, background futures, scheduled commits, and resumable large-folder uploads. Termux install must be verified. | Prefer on-device HF push for checkpoints only after Termux proof. Always keep ADB-pull plus host HF push fallback. |
| Flower Android support | First-party Android examples exist, but they are TensorFlow Lite CIFAR-10 demo clients with custom FedAvg serialization, not PyTorch LLM training. | Flower is Phase 2 control-plane design only until multiple devices exist and single-device ELO is stable. |
| ai_edge_torch / LiteRT Torch Qwen path | LiteRT Torch exists, PyTorch converter is beta, Generative API alpha, CPU/GPU supported, NPU support in development. LiteRT-LM has broad model support including Qwen, but no public exact Qwen2.5-1.5B to QNN frozen-layer training-subgraph report. | Build an export truth table: tiny block, one real block, frozen middle subgraph. Store compile errors and delegate percentage. |

## Productisation Position

There is no product MVP in this PRD. There is no first customer. There is no production release. Polymath's deliverable is research infrastructure and reproducible evidence. A later productization workstream would need its own boundary, acceptance gates, security review, privacy review, model-license review, and deployment falsifier gate.

## System Architecture

### Closed-Loop Heterogeneous Controller

Polymath is specified as a closed-loop controller over model updates, corpus sampling, method comparisons, and device placement.

| Controller element | Polymath instance | Observability |
|---|---|---|
| Policy being updated | Qwen2.5-1.5B primary, SmolLM3-3B secondary when export/eval permits | Checkpoint records, validation deltas, teacher-panel judgments |
| Environment | Seed Corpus v0 multilingual and multi-domain slices plus replay set | Corpus manifests, license manifests, OCR provenance, quality scores |
| Observation channel | Per-language loss, per-domain loss, tokenizer fertility, cross-model disagreement, method disagreement, device telemetry | Eval records and audit/KG nodes |
| Action channel | Sampling weights, sequence length, batch size, optimizer settings, dispatch backend, scheduler policy, rest periods | Dispatch records and config hashes |
| Falsifier channel | Registry gates that block claims, runs, uploads, or phase advancement | `FalsifierResult` records, KG `FAILED_BY` edges |

### Component Boundaries

All components live inside this repository or its HF private artifact store. Fork-and-own of sibling patterns is allowed. Runtime imports, databases, corpora, services, or git submodules from Health, Materials, Energy, or Synthetic Biology are forbidden.

```
polymath_ai/
  boundary/              boundary text, forbidden-framing scans
  schemas/               JSON Schema / Pydantic contracts
  audit/                 append-only hash-chained JSONL logs, DuckDB index optional
  kg/                    append-only nodes/edges and reconstruction utilities
  models/                model adapters for tiny smoke, Qwen, SmolLM3
  elo/                   ELO Stage 1 and Stage 2 implementation
  dispatch/              mac_sim, android_cpu, vulkan, litert_qnn, fallback adapters
  scheduler/             Reflex Scheduler and static-placement ablation
  corpus/                manifests, license decomposition, curation pipeline
  eval/                  fertility, perplexity, recall, teacher panel, disagreement
  reasoner_queue/        self-bootstrapping tuple writer
  sync/                  GitHub and HF artifact exfiltration
  device/                ADB, Termux, profiler, charge/battery probes
  experiments/           Experiment 0, 1, 2 runners and configs
```

If the overnight executor does not create this exact package layout, it must preserve the same ownership boundaries and document deviations in `docs/DECISIONS.md`.

## Interface Contracts

### Universal Envelope

Every run, evaluation, checkpoint, export probe, and sync event emits a `PolymathEnvelope` JSON object.

Required fields:

```json
{
  "schema_version": "1.0.0",
  "boundary": "Research infrastructure for in silico on-device LLM training and multilingual / multi-domain knowledge model construction. Outputs are research artifacts - model checkpoints, training telemetry, evaluation reports, throughput measurements. No regulatory certification claims. No clinical or human-subject use. No surveillance, biometric profiling, or identity inference. No model weights distributed without explicit license attestation. No training on copyrighted material without explicit corpus-license decomposition. No deployment to production without a falsifier-traced acceptance gate.",
  "run_id": "run:YYYYMMDDTHHMMSSZ:<slug>",
  "phase": "phase0b_elo_correctness",
  "experiment_id": "experiment:0|1|2|custom",
  "git_sha": "<repo commit>",
  "config_sha256": "sha256:<hex>",
  "model": {
    "model_id": "Qwen/Qwen2.5-1.5B",
    "revision": "<hf revision>",
    "model_sha256": "sha256:<hex>",
    "tokenizer_sha256": "sha256:<hex>",
    "license_attestation_id": "license:qwen2.5-1.5b:<date>"
  },
  "corpus": {
    "manifest_sha256": "sha256:<hex>",
    "slice_id": "corpus_slice:seed-v0:smoke-001",
    "license_summary": "all_chunks_attested"
  },
  "device_state": {
    "host_machine": "<name>",
    "phone_attached": false,
    "phone_model": null,
    "soc_reported": null,
    "ram_gb": null,
    "battery_mode": null,
    "thermal_status": null,
    "gpu_clock_mhz_p50": null,
    "gpu_clock_mhz_p10": null
  },
  "backend": "mac_sim|android_cpu|vulkan_gpu|litert_qnn|qnn_direct|fallback",
  "outputs": {},
  "falsification": {
    "status": "pass|warn|fail|blocked",
    "falsifier_ids": [],
    "blocking_failures": []
  },
  "provenance": {
    "agent_role": "overnight-executor",
    "agent_model": "<model if known>",
    "source_files": [],
    "input_hashes": [],
    "output_hashes": []
  },
  "artifact_refs": {
    "github_paths": [],
    "hf_private_refs": [],
    "pending_local_paths": []
  }
}
```

### ModelAdapter

```python
class ModelAdapter:
    model_id: str
    model_family: str
    license_id: str

    def load(self, revision: str, dtype: str, device: str) -> "LoadedModel": ...
    def tokenizer(self) -> "Tokenizer": ...
    def freeze_policy(self, policy_name: str) -> "FreezePlan": ...
    def trainable_parameters(self, freeze_plan: "FreezePlan") -> list[str]: ...
    def forward(self, batch: "TokenBatch") -> "ForwardResult": ...
    def generate(self, prompt_batch: "PromptBatch") -> "GenerationResult": ...
    def save_checkpoint(self, path: str, checkpoint_kind: str) -> "CheckpointRecord": ...
    def load_checkpoint(self, path: str) -> "LoadedModel": ...
    def export_probe(self, export_target: str, graph_scope: str) -> "ExportProbeRecord": ...
```

Required model adapters:

| Adapter | Purpose | Gate |
|---|---|---|
| `TinyQwenShapeAdapter` | CI and Mac smoke tests with tiny randomly initialized Qwen-like config | Must pass before real checkpoint download |
| `Qwen25_15BAdapter` | Primary Phase 1A model | Must pass license, hash, tokenizer, ELO, and export probes |
| `SmolLM3_3BAdapter` | Candidate B and cross-model evaluator | Must pass Experiment 2 for acceleration; otherwise eval-only fallback |

### ELOTrainer

ELO is not a single `requires_grad` toggle. The executor must implement paper-faithful Stage 1 and Stage 2 semantics.

```python
class ELOTrainer:
    def build_stage1_model(self, model: ModelAdapter, freeze_plan: FreezePlan) -> "ELOStage1Model": ...
    def validate_freeze_plan(self, model: "ELOStage1Model") -> "FreezeValidation": ...
    def train_step(self, batch: "TokenBatch") -> "TrainStepRecord": ...
    def save_boundary_checkpoint(self) -> "CheckpointRecord": ...
    def merge_boundary_checkpoint(self, base_model_ref: str, checkpoint_ref: str) -> "MergedCheckpointRecord": ...
    def run_stage2_alignment(self, calibration_slice: str) -> "AlignmentRecord": ...
```

Default trainable set for Qwen2.5-1.5B:

- token embeddings only if the freeze-plan ablation says embeddings are required; default is frozen embeddings for first smoke, then embedding-unfrozen ablation
- transformer layer 0
- transformer layer 27
- `lm_head`
- no middle layer optimizer state

Validation requirements:

- Trainable parameter names are emitted to audit.
- Frozen parameter hashes before and after each training step are compared for a small sample in smoke tests.
- Optimizer state includes only trainable parameter tensors.
- One-step resume from checkpoint is bitwise or tolerance-equivalent under deterministic seed on Mac.
- Stage 1 to Stage 2 merge records activation statistics, calibration dataset hash, and rollback pointer.

### AcceleratorAdapter

```python
class AcceleratorAdapter:
    name: str
    supports_training: bool
    supports_inference: bool

    def probe(self) -> "BackendProbeRecord": ...
    def compile(self, model_ref: str, graph_scope: str, target: str) -> "CompileRecord": ...
    def run(self, inputs: "TensorBundle") -> "BackendRunRecord": ...
    def delegate_report(self) -> "DelegateReport": ...
    def fallback_reason(self) -> str | None: ...
```

Required adapters:

| Adapter | Required by | Notes |
|---|---|---|
| `MacSimAdapter` | Phase 0A onward | Simulates backend contracts with tiny tensors and deterministic golden fixtures. |
| `AndroidCPUAdapter` | Phase 0D onward | First real phone compute baseline; must work even if acceleration fails. |
| `VulkanAdapter` | Phase 0C onward | May be custom kernel, ExecuTorch Vulkan, or LiteRT GPU inference depending on viability. Must not claim general PyTorch training until measured. |
| `LiteRTQNNAdapter` | Phase 0C onward | Inference-only. Requires exact compile/delegate report. |
| `FallbackAdapter` | Always | CPU/GPU fallback with explicit downgrade record. |

### CorpusAdapter

```python
class CorpusAdapter:
    def build_manifest(self, source_specs: list[dict]) -> "CorpusManifest": ...
    def audit_license(self, manifest: "CorpusManifest") -> "LicenseAudit": ...
    def sample_slice(self, manifest: "CorpusManifest", slice_spec: dict) -> "CorpusSlice": ...
    def normalize_ocr(self, document_ref: str) -> "NormalizedDocument": ...
    def tokenize(self, slice_ref: str, tokenizer_ref: str) -> "TokenizedSlice": ...
    def fertility_report(self, slice_ref: str, tokenizer_ref: str) -> "FertilityReport": ...
    def quality_report(self, slice_ref: str) -> "CorpusQualityReport": ...
```

### SyncAdapter

```python
class SyncAdapter:
    def push_logs_to_github(self, run_id: str) -> "SyncEvent": ...
    def push_artifact_to_hf(self, artifact_ref: str, repo_id: str, repo_type: str) -> "SyncEvent": ...
    def pull_from_phone(self, phone_path: str, host_path: str) -> "SyncEvent": ...
    def recover_pending_uploads(self) -> list["SyncEvent"]: ...
```

## Plug-Replaceability Invariant

The executor must preserve these swaps behind config and adapter contracts:

| Swap | Required maximum disruption | Test |
|---|---|---|
| Tiny smoke model to Qwen2.5-1.5B | No schema change | Same `ELOTrainer` smoke suite passes. |
| Qwen2.5-1.5B to SmolLM3-3B | Less than one executor day after adapter exists | Fertility, ELO one-step, eval, export probe all emit same envelope shape. |
| Static placement to Reflex Scheduler | Config flag only | Same seed and same first N smoke steps produce tolerance-equivalent loss under static mode. |
| QNN to CPU/GPU fallback | Config flag plus downgrade record | Fallback reason emitted; no missing artifacts. |
| On-device HF push to ADB plus host push | Config flag only | Hash of uploaded artifact matches local manifest. |

Any code path that special-cases a model, backend, corpus source, or sync method without going through the adapter contract is a PRD violation unless documented in `docs/DECISIONS.md` with a removal plan.

## Falsifier Registry

The falsifier registry is written before the training loop. Runs do not advance phases by finishing wall-clock; they advance only by passing falsifiers.

| Falsifier ID | Trigger | Blocks | Required response |
|---|---|---|---|
| `boundary_violation` | Artifact frames clinical use, human-subject inference, surveillance, biometric profiling, identity inference, production deployment, copyrighted training without license decomposition, or weight distribution without license attestation | All publication, upload, phase advancement | Stop, quarantine artifact, emit retraction record, fix source. |
| `device_soc_mismatch` | Runtime SoC probe contradicts configured QNN target | QNN compile and acceleration claims | Re-probe, select correct target, or use fallback. |
| `qnn_exact_path_unproven` | No stored compile/delegate report for exact model graph scope | NPU claims and Phase 1A QNN use | Run export truth table or disable QNN. |
| `qnn_unsupported_op` | LiteRT/QNN compile fails or delegate percentage below configured threshold | QNN use for that model/scope | Store failing op, fallback, open issue. |
| `smollm3_export_unproven` | SmolLM3 has no successful Experiment 2 record | SmolLM3 accelerated training | Mark eval-only or GPU/CPU-only. |
| `checkpoint_hash_mismatch` | Checkpoint SHA does not match manifest | Resume, eval, upload | Quarantine checkpoint, roll back to previous hash-chain head. |
| `tokenizer_fertility_high` | Any core target language exceeds 2.5x English token-per-word ratio | Phase 1A corpus lock | Vocabulary extension, sampling adjustment, model swap, or operator-decision record. |
| `oom_or_memory_pressure` | Android process killed, OOM, or peak RAM above 22GB | Device run scale-up | Reduce batch/sequence, enable checkpointing, retry smoke. |
| `thermal_throttle` | GPU clock below 600 MHz for more than 10% of a 1-hour window, or thermal status severe/critical | Phase 1A multi-hour run | Enable fan/charge separation, reduce load, schedule rest, rerun calibration. |
| `battery_heat_risk` | Battery temperature >= 42C for 60s or >= 40C for 5 minutes | Plugged-in run continuation | Stop run, cool device, change charging regime. |
| `charge_bypass_unproven` | Charge Separation not visible or SoC drifts more than 2 percentage points/hour during bypass test | Multi-day run | Use rest periods and stricter thermal gate, or postpone. |
| `throughput_floor_fail` | 2-hour micro-run under 500K tokens/hour equivalent, or under 100K hard fail | Phase 1A timing claim | Debug data pipeline/backend overhead before corpus investment. |
| `energy_budget_exceeded` | Joules/token or Wh/token exceeds static baseline by more than 20% without quality gain | Reflex default and multi-day plan | Revert scheduler or reduce load. |
| `catastrophic_forgetting` | English held-out or MMLU-style drop greater than 1 percentage point vs base | Phase 1B advancement | Increase replay, reduce LR, revise curriculum. |
| `cross_model_disagreement_high` | Qwen vs SmolLM3 disagreement above threshold on matched eval, when SmolLM3 is available | Quality claim | Flag for teacher-panel adjudication; do not claim stable improvement. |
| `method_disagreement_high` | ELO vs QLoRA improvement ranking Spearman rho below 0.6 on pilot slice | ELO superiority claim | Investigate corpus signal and method behavior. |
| `license_drift` | Corpus chunk lacks explicit license class or source provenance | Training on that chunk | Remove chunk until attested. |
| `ocr_damage_high` | Perplexity or OCR heuristic damage score above threshold | Training on that chunk | Re-OCR, repair, or exclude. |
| `overclaim` | Report makes a claim unsupported by run/eval artifacts | Report publication | Rewrite claim or produce evidence. |

## Audit Trail And KG Specification

### Hash Chain

All audit logs are append-only JSONL. Each row has:

```json
{
  "schema_version": "1.0.0",
  "recorded_at": "2026-05-01T00:00:00Z",
  "run_id": "run:...",
  "event_type": "train_step|checkpoint|eval|decision|sync|falsifier|device_probe",
  "payload": {},
  "prev_event_hash": "sha256:<previous or genesis>",
  "event_hash": "sha256:<canonical_json({prev_event_hash, recorded_at, payload})>"
}
```

The timestamp is part of the event hash. Tamper, reorder, insert, and delete must be detectable by tests. JSONL is source of truth. DuckDB or SQLite indices are caches only.

### KG Node Types

Required node types:

- `Run`
- `Phase`
- `Experiment`
- `Model`
- `Tokenizer`
- `CorpusManifest`
- `CorpusSource`
- `CorpusChunk`
- `LicenseFinding`
- `OCRProvenance`
- `Checkpoint`
- `DeviceState`
- `DispatchRecord`
- `SchedulerPolicy`
- `EvalArtifact`
- `TeacherPanelJudgment`
- `FalsifierResult`
- `DisagreementRecord`
- `Decision`
- `SyncEvent`
- `ReasonerTuple`

Required edge types:

- `USED_MODEL`
- `USED_TOKENIZER`
- `USED_CORPUS`
- `PRODUCED`
- `VALIDATED_BY`
- `FAILED_BY`
- `WARNED_BY`
- `DISAGREES_WITH`
- `DERIVED_FROM`
- `SYNCED_TO`
- `BLOCKED_BY`
- `SUPERSEDES`
- `RIGHTS_CONSTRAINED_BY`
- `JUDGED_BY`

### Decision Log

`docs/DECISIONS.md` begins at `D-001`. Every decision row contains:

- decision id
- timestamp
- agent role
- context
- options considered
- decision
- strongest disconfirming observation
- affected configs/artifacts
- follow-up owner

## Seed Corpus v0 Specification

Operator engagement selected the default Seed Corpus v0 path. This is a conservative starting corpus, not the final Polymath knowledge universe.

### Scale Targets

| Stage | Tokens | Purpose | Storage |
|---|---:|---|---|
| Smoke slice | 10K-100K | CI, Mac, and device smoke | GitHub allowed if tiny and licensed |
| Experiment 0 slice | 10M | Device stack and throughput | HF private dataset; small manifest in GitHub |
| Phase 1A corpus | 100M | First real ELO Stage 1 run | HF private dataset under Architect-Prime |
| Phase 1B expansion | 500M | Curriculum and cross-lingual/domain objectives | HF private dataset under Architect-Prime |
| Phase 2 optional | 1B | Publishable scale extension | HF private dataset under Architect-Prime |

No bulk local datasets on the Mac. The repo stores manifests, metadata, checksums, tiny fixtures, and sampled license-clean snippets only.

### Domain Mix For Phase 1A

Phase 1A is multi-domain and multilingual. It must not collapse into a generic multilingual corpus.

| Domain | Target share | Acceptable source classes |
|---|---:|---|
| Computer science, ML, systems, mobile compute | 15% | Open textbooks, permissive docs, arXiv CC-licensed papers, public-domain texts |
| Mathematics and formal reasoning | 12% | Open textbooks, proof corpora with permissive licenses, public-domain math texts |
| Physics and engineering | 12% | Open textbooks, arXiv CC-licensed papers, public-domain classics |
| Biology, chemistry, materials, energy, synthetic biology overviews | 12% | Open educational resources, CC-licensed papers, public-domain sources |
| Music technology, audio, signal processing | 12% | Open textbooks, permissive manuals, public-domain theory texts, CC-licensed resources |
| Philosophy, history of science, epistemology | 10% | Public-domain books, open course texts |
| Linguistics, language learning, translation examples | 10% | Open language resources, Tatoeba-style datasets only if license compatible |
| Code and technical documentation | 10% | Permissive code/docs only; no copyleft contamination unless isolated and recorded |
| General replay set | 7% | License-clean English general-domain text for catastrophic-forgetting mitigation |

The executor may adjust percentages by plus or minus 5 percentage points if source availability and license decomposition demand it, but must preserve multi-domain coverage and record the change.

### Language Mix For Phase 1A

Default target languages:

- English: anchor, replay, and domain depth
- French
- Spanish
- German
- Italian
- Portuguese
- Arabic
- Chinese
- Japanese
- Korean
- Russian
- Hindi
- Swahili
- isiZulu
- Afrikaans
- Latin or Classical Greek as optional classical-language slice if license-clean sources are available

Sampling target before tokenizer fertility correction:

| Group | Target share |
|---|---:|
| English | 30% |
| High-resource European languages | 25% |
| CJK | 15% |
| Arabic, Russian, Hindi | 15% |
| African languages and low-resource slices | 10% |
| Classical / specialist language slices | 5% |

Fertility correction overrides raw share. Any language above 2.5x English fertility triggers `tokenizer_fertility_high` and cannot enter Phase 1A without an explicit mitigation plan.

### License Classes

Every corpus source and chunk receives one class:

| Class | Meaning | Training allowed? | Redistribution allowed? |
|---|---|---|---|
| A | Public domain / CC0 | Yes | Yes, with manifest |
| B | Permissive open license allowing ML training and redistribution | Yes | Yes, preserving attribution/license |
| C | Open access or CC license allowing research use but with attribution/share-alike/noncommercial constraints | Maybe | Only according to license; isolate if needed |
| D | Ambiguous terms, web scrape, unclear copyright, or no explicit ML/training permission | No | No |
| E | Copyrighted commercial material without explicit permission | No | No |

Only A/B sources enter default training. C sources require a decision record and isolation. D/E sources are excluded.

### OCR Provenance

For OCR-derived sources, each document records:

- original file hash
- scanner/source provenance
- OCR engine and version
- language model or OCR settings
- page-level confidence
- normalization steps
- header/footer removal steps
- perplexity-damage score
- human or model repair notes

OCR-derived chunks above the damage threshold are excluded until repaired.

## Training Method Specification

### Phase 0 ELO Reimplementation

The executor reimplements ELO locally. Minimum implementation targets:

1. Tiny Qwen-shaped model trains only first and last transformer layers plus `lm_head`.
2. Frozen layers retain identical hashes across one-step and multi-step training.
3. Optimizer state contains no frozen parameters.
4. Stage 1 checkpoint contains boundary weights, optimizer state, scheduler state, activation statistics, corpus slice hash, config hash, and base-model pointer.
5. Stage 2 merge reconstructs full model from base checkpoint plus boundary checkpoint.
6. Stage 2 alignment runs on a calibration slice and can roll back if validation loss worsens beyond threshold.

### Method Disagreement Baselines

Phase 0 and Phase 1A include comparison arms:

| Method | Role | Scale |
|---|---|---|
| ELO Stage 1 | Primary method | Smoke, 10M, 100M |
| QLoRA | Low-cost baseline and falsifier | Smoke, 10M pilot, optional 100M subset |
| LoRA | Standard adapter baseline | Smoke and pilot |
| Distillation + ELO | Parallel research arm | Teacher-generated subset, then student phone eval |

ELO superiority may not be claimed unless ELO beats QLoRA/LoRA on quality per wall-clock or quality per Joule, and method disagreement is analyzed.

## Runtime And Device Specification

### Dev-Machine First

Before phone access, the executor must complete:

- repo substrate and schemas
- boundary scanner
- audit hash-chain writer and tests
- KG append/reconstruct utilities
- tiny model ELO correctness tests
- corpus manifest and license-audit pipeline with tiny fixtures
- HF/GitHub sync stubs and pending upload manifests
- export truth-table scripts
- ADB and Termux install/probe scripts
- Snapdragon Profiler and AGI capture instructions/scripts
- phase configs with `phone_attached=false`

Phone arrival must flip config from `phone_attached=false` to `phone_attached=true` and run the same envelopes against real device probes.

### Phone Stack Probe

When the REDMAGIC 10 Pro+ is attached, the executor runs:

1. `adb devices` and device authorization check.
2. Device identity: model, Android version, RedMagic OS version, SoC, ABI, RAM, storage free, thermal zones.
3. Developer options and USB debugging state.
4. Termux presence, package manager, Python version, available compilers, `git`, `gh`, `hf`, `rsync` or fallback tools.
5. PyTorch import and one-tensor op if installable.
6. `transformers`, `tokenizers`, `safetensors`, `huggingface_hub` install/import if possible.
7. LiteRT/LiteRT-LM runtime availability, QNN libraries, QAIRT/QNN SDK path if available.
8. Vulkan capability query.
9. Snapdragon Profiler attach and counter capture.
10. Charge Separation / bypass charging check.
11. Screen-off or low-brightness long-run viability.

### Energy Regime

Multi-day training is plug-in-only by physical necessity.

Default operating profile:

- Charge Separation ON if available.
- Battery cap set to 70-80% if RedMagic OS supports it.
- Fan ON.
- Stable/balanced performance mode first; no extreme mode unless measured better in tokens/J and thermals.
- Case removed.
- Ambient target below 25C.
- Screen off or minimum brightness.
- No fast charging during sustained training unless Charge Separation is active and battery temperature stays below thresholds.

Gates:

- Pass bypass if battery SoC drift is <= 2 percentage points/hour under sustained load.
- Battery warning at >= 40C for 5 minutes.
- Battery hard stop at >= 42C for 60 seconds.
- GPU pass if 1-hour fan-on p50 clock >= 800 MHz and p10 >= 600 MHz.
- Thermal fail if GPU clock < 600 MHz for more than 10% of any 1-hour window.

### Phone To GitHub And Hugging Face Artifact Exfiltration

| Artifact class | Primary mechanism | Fallback | Frequency |
|---|---|---|---|
| Code, configs, schemas | Host GitHub commit/push | Termux `gh` if host unavailable | Every completed task group |
| Small telemetry JSONL | ADB pull to host, GitHub commit | Termux `gh` commit | Every run segment and at run end |
| Large telemetry/profiler traces | ADB pull to host, HF private dataset/model artifact | External drive staging if HF token absent | End of calibration/run segment |
| ELO boundary checkpoints | On-device `huggingface_hub` push if proven | ADB pull then host HF push | Every N tokens or time interval configured |
| Full merged model weights | Host HF push after license attestation | Pending-upload manifest only | Only after acceptance gates |
| Corpus manifests | GitHub | HF dataset card mirror | Every corpus change |
| Bulk corpus shards | HF private dataset under Architect-Prime | No local bulk fallback | Per shard |

If the HF token is absent on the execution machine, the executor must continue building and testing, emit `hf_token_absent` as a non-scientific blocker, create pending upload manifests with hashes, and still push all GitHub artifacts.

## Build Sequence

The executor runs phases in order. Phases can be internally parallelized by worktree/subagent, but phase gates are serial.

### Phase 0A - Repo Substrate And Contracts

Deliverables:

- package skeleton or equivalent module layout
- `docs/DECISIONS.md`
- `docs/FALSIFIERS.md`
- `docs/AUDIT-SPEC.md`
- `docs/CORPUS-SPEC.md`
- schema files for envelope, corpus manifest, checkpoint record, eval record, device state, dispatch record, sync event, reasoner tuple
- boundary scanner that fails if markdown artifacts lack the boundary
- audit hash-chain writer and validator with tamper/reorder/insert/delete tests
- KG append/reconstruct utilities

Gate:

- Unit tests pass.
- A fresh reconstruction from JSONL audit/KG works without chat history.

### Phase 0B - ELO Correctness On Dev Machine

Deliverables:

- Tiny Qwen-shaped model adapter.
- Qwen2.5-1.5B adapter can load metadata without downloading full weights unless storage allows.
- ELO Stage 1 train step on tiny model.
- Stage 1 checkpoint save/resume.
- Stage 2 merge/alignment smoke.
- Frozen-layer hash invariant tests.
- QLoRA/LoRA baseline smoke or stub with explicit pending dependency if packages absent.

Gate:

- Frozen middle layers do not change.
- Optimizer state excludes frozen parameters.
- Same seed produces deterministic smoke loss within tolerance.

### Phase 0C - Export Truth Table

Graph scopes:

1. tiny synthetic transformer block
2. one real Qwen block
3. Qwen frozen-middle representative subgraph
4. one real SmolLM3 block
5. SmolLM3 representative subgraph

Targets:

- LiteRT Torch / `.tflite`
- LiteRT-LM where applicable
- LiteRT QNN AOT or on-device compile after SoC target is known
- CPU/GPU fallback

Deliverables:

- compile logs
- unsupported op list
- delegate percentage
- inference output sanity check
- latency if runnable
- `qnn_exact_path_unproven` resolved or left as blocking for QNN use

Gate:

- QNN may be used only for scopes with successful delegate reports.
- SmolLM3 Candidate B acceleration requires Experiment 2 pass.

### Phase 0D - Device Attach And Stack Probe

Runs only when phone is physically available. If phone is unavailable, the executor completes all previous phases and prepares `PHONE-ATTACH-RUNBOOK.md`.

Deliverables:

- actual device identity envelope
- Termux capability report
- Python package report
- ADB stability report
- charge/bypass report
- profiler attach proof
- Vulkan and QNN availability report

Gate:

- Device identity known.
- No guessed SoC target remains in config.
- If Termux PyTorch fails, fallback route is selected and documented.

### Phase 0E - Experiment 0: Stack Fit And Baseline Throughput

Runs on actual REDMAGIC only.

Initial micro-run ladder:

| Step | Tokens | Seq length | Batch | Purpose |
|---|---:|---:|---:|---|
| E0.1 | 10K | 128 | 1 | End-to-end smoke with logs/checkpoint/sync |
| E0.2 | 100K | 256 | 1-2 | Memory and thermal first signal |
| E0.3 | 1M | 512 | 2-4 | Throughput estimate |
| E0.4 | 2 hours sustained | 512 | max stable | Thermal and energy gate |

Success thresholds:

- no OOM at viable batch
- peak RAM < 20GB preferred, < 22GB hard ceiling
- sustained throughput > 500K tokens/hour equivalent, with < 100K hard fail
- battery temp below warning threshold
- GPU clock p50 >= 800 MHz, p10 >= 600 MHz after thermal settling
- checkpoint resume works
- audit/KG/sync all work

### Phase 0F - Experiment 1: Tokenizer Fertility And Corpus Lock

Deliverables:

- per-language table: words, chars, tokens, tokens/word, tokens/char, ratio vs English
- per-domain tokenization anomalies
- CJK, Arabic, Hindi, African-language reports
- Qwen tokenizer report and SmolLM3 comparison if available
- vocabulary-extension or sampling mitigation decision if needed

Gate:

- No core target language above 2.5x English without mitigation.
- Corpus chunks all have license classes.

### Phase 0G - Experiment 2: SmolLM3 QNN Export Verdict

Deliverables:

- SmolLM3 tiny block export
- real block export
- representative frozen subgraph export
- compile/delegate/error logs
- decision: `accelerated_candidate_b`, `gpu_cpu_eval_only`, or `deferred`

Gate:

- Yes only if runnable, measured, and delegate report stored.
- Failure must name likely op or graph pattern.

### Phase 0H - Cutover Readiness Review

This is the 110% pre-device-corpus-investment gate.

Phase 1A cannot begin until:

- Phase 0A-0G complete or explicitly blocked by absent phone/HF token with all non-phone work complete.
- ELO implementation validated.
- Audit, KG, falsifiers, reasoner queue, and sync tested.
- Corpus manifest and license decomposition complete for the 100M slice.
- Experiment 0/1/2 actual-device gates pass when phone is available.
- Static placement baseline exists.
- Reflex Scheduler micro-calibration exists, even if disabled for the first static burn-in.
- QLoRA/LoRA comparison pilot exists or is explicitly blocked by dependency constraints.

The Phase 0 to Phase 1A cutover is a config change:

```yaml
phase: phase1a_qwen_elo_100m
phone_attached: true
corpus_slice: seed-v0-phase1a-100m
model: qwen2.5-1.5b
method: elo_stage1
backend_policy: static_burn_in_then_reflex_if_passed
qnn_enabled: false_or_true_based_on_phase0c
sync_policy: host_plus_hf
```

## Phase 1A Deliverable

Phase 1A is the first real on-device Polymath run.

Required run:

- Model: Qwen2.5-1.5B base, exact revision pinned.
- Corpus: Seed Corpus v0 100M-token license-clean slice.
- Method: ELO Stage 1, with QLoRA/LoRA comparison on a matched subset.
- Device: REDMAGIC 10 Pro+ only.
- Energy: plug-in-only, Charge Separation preferred.
- Backends: measured available adapters only. QNN optional and only if Phase 0C proved exact scope.
- Scheduler: static burn-in, then Reflex Scheduler if micro-calibration passed.

Required outputs:

- boundary-layer checkpoints
- merged Stage 1 checkpoint manifest
- Stage 2 alignment checkpoint if run
- full telemetry trace
- per-language validation losses
- per-domain validation losses
- tokenizer fertility final report
- catastrophic-forgetting report
- cross-model disagreement scorecard if SmolLM3 eval is available
- method disagreement scorecard for ELO vs QLoRA/LoRA
- teacher-panel evaluation report
- corpus license manifest
- checkpoint and eval hash chain
- HF private artifact refs
- GitHub commit with manifests, reports, and decision log

Acceptance thresholds:

- No boundary violations.
- No license drift.
- No checkpoint hash mismatch.
- No catastrophic forgetting greater than 1 percentage point on English anchor eval.
- ELO shows measurable in-domain or multilingual improvement over base and is competitive against QLoRA/LoRA under matched wall-clock/Joule budget.
- Device telemetry supports claimed throughput and thermal regime.
- Every claim in report maps to audit evidence.

## Evaluation Harness

### Core Metrics

| Metric | Scope | Required baseline |
|---|---|---|
| Perplexity | per-language and per-domain held-out slices | Base Qwen2.5-1.5B |
| In-domain recall | custom questions from corpus concepts | Base model and QLoRA subset |
| Cross-lingual transfer | translation/QA where license-clean pairs exist | Base model |
| Catastrophic forgetting | English replay and MMLU-style anchor | Base model |
| Teacher preference | teacher panel comparing base vs tuned outputs | Base model |
| Tokens/hour | sustained device run | Experiment 0 baseline |
| Joules/token or Wh/token proxy | battery/power telemetry | Static placement baseline |
| Thermal stability | profiler counters | Experiment 0 gates |

### Teacher Panel

Default teacher panel:

- Claude Opus 4.7
- GPT-5+ high reasoning
- Gemini Advanced / Gemini 2.5+ equivalent

Rubric dimensions:

- factual support from corpus
- multilingual adequacy
- cross-domain synthesis
- refusal/boundary compliance
- hallucination risk
- clarity and calibration

Teacher disagreement is itself an eval signal. The harness must not use teacher preference alone to claim scientific success; it supports, but does not replace, falsifier-traced metrics.

### Cross-Model Disagreement

If SmolLM3 is runnable as eval model:

- compute Qwen vs SmolLM3 disagreement on per-language perplexity deltas
- compare answer correctness on in-domain prompts
- compute rank correlation of examples improved/degraded
- route high-disagreement examples to teacher panel and reasoner queue

If SmolLM3 is not runnable, emit `cross_model_unavailable` warning and do not make ensemble-stability claims.

### Method Disagreement

For matched pilot slices:

- ELO vs QLoRA improvement rank Spearman rho target >= 0.6
- disagreements are tagged by language, domain, source, and tokenizer fertility
- if ELO improvement is not qualitatively different from QLoRA, investigate whether corpus teaches style rather than knowledge

## Self-Bootstrapping Reasoner

Fork Health's tuple discipline conceptually, not by runtime import.

Every evaluation item writes to:

```
reasoner_queue/runs/<run_id>/tuples.jsonl
```

Tuple shape:

```json
{
  "schema_version": "1.0.0",
  "boundary": "Research infrastructure for in silico on-device LLM training and multilingual / multi-domain knowledge model construction. Outputs are research artifacts - model checkpoints, training telemetry, evaluation reports, throughput measurements. No regulatory certification claims. No clinical or human-subject use. No surveillance, biometric profiling, or identity inference. No model weights distributed without explicit license attestation. No training on copyrighted material without explicit corpus-license decomposition. No deployment to production without a falsifier-traced acceptance gate.",
  "run_id": "run:...",
  "tuple_id": "tuple:...",
  "input": {"prompt": "...", "language": "...", "domain": "...", "source_refs": []},
  "output": {"model_id": "...", "checkpoint_sha256": "...", "text": "..."},
  "judgment": {"status": "pass|fail|warn", "falsifier_ids": [], "teacher_panel": []},
  "correction": {"preferred_output": null, "rationale": null},
  "hashes": {"input_sha256": "...", "output_sha256": "...", "judgment_sha256": "..."}
}
```

This private dataset compounds evaluation quality. It is not public unless a separate license and privacy review permits release.

## Distillation Arm

### Decision

Commit to a Phase 1A parallel distillation arm as a comparison and augmentation lane. Do not replace ELO unless evidence warrants it.

### Teacher Selection

Primary teacher candidate:

- Qwen3-Next-80B-A3B-Instruct on Runpod, because Apache 2.0 and sparse-active inference economics are attractive.

Fallback teacher candidate:

- Qwen2.5-72B or Qwen2.5-72B-Instruct, only after license attestation.

### Distillation Data

Use:

- Seed Corpus v0 prompts
- on-policy prompts from base and tuned student failures
- high-disagreement examples
- multilingual/domain-balanced prompt templates

Preferred format:

- sequence-level teacher answers
- rationales only if license and boundary clean
- top-k logprobs when practical, not dense full-vocabulary logits over massive token volumes
- preference pairs for teacher-panel rubrics

### Acceptance

Distillation arm advances only if:

- teacher model license is attested
- Runpod artifacts sync to HF private store
- student evaluation beats or complements ELO under matched budget
- no boundary or copyright violation appears in teacher outputs

## Federated Multi-Device Arm

No multi-device fleet exists. This arm is design-only for Phase 2.

Specification to preserve:

- Flower is the control plane, not the mobile LLM training runtime.
- Boundary-layer deltas are the aggregation unit.
- Middle layers remain frozen and identical.
- Coordinator runs on host Mac or server.
- Devices must pass the same energy and thermal gates.
- Secure aggregation, client authentication, and privacy accounting are future work before any real multi-device experiment beyond owned devices.

Phase 2 design deliverable:

- `docs/FEDERATED-DESIGN.md`
- simulator with 2-3 virtual clients on tiny model
- aggregation of ELO boundary deltas
- no claim of real federated phone training until hardware exists

## Cross-Device Portability Matrix

The only Phase 1A device is the REDMAGIC 10 Pro+. Cross-device validation is not a blocker because no other device exists.

The executor still creates a design matrix:

| Device class | Status | Required before claim |
|---|---|---|
| REDMAGIC 10 Pro+ active-cooled SD8E | Primary actual device | Experiment 0/1/2 and Phase 1A telemetry |
| Non-cooled Snapdragon 8 Elite reference phone | Not available | Experiment 0 before any portability claim |
| Older Snapdragon 8 Gen 3 phone | Optional future lower-bound | Smoke throughput and thermal only |
| Desktop Mac simulation | Available dev stand-in | Contract/golden fixture only, no device claim |

Reports must say "validated on REDMAGIC 10 Pro+" unless another device is actually tested.

## Reflex Scheduler

### Purpose

The Reflex Scheduler selects batch shape, backend placement, rest periods, and curriculum sampling based on recent telemetry and validation signals.

### Phase 0 Implementation

- static placement policy
- UCB or epsilon-greedy policy over operation shape and backend choices
- latency/energy/thermal history table
- config flag to force static placement
- deterministic replay of scheduling decisions from audit log

### Phase 1A Use

Phase 1A starts with static burn-in. Reflex becomes default only if micro-calibration shows:

- tokens/hour improves by >= 5% or tokens/J improves by >= 5%
- no thermal gate regression
- no checkpoint determinism issue beyond accepted tolerance
- no quality regression on validation micro-slice

If Reflex fails, static remains the production policy and Reflex is kept as an ablation artifact.

## Agent Topology For Overnight Execution

The overnight executor may be one agent coordinating subagents or a supervisor plus worktree agents. Use worktrees where practical. All work commits back to GitHub before handoff.

Recommended parallel lanes:

| Lane | Responsibility | Output |
|---|---|---|
| Repo substrate agent | schemas, boundary scanner, audit/KG, decisions | tests and docs |
| ELO/model agent | adapters, ELO Stage 1/2, baselines | correctness tests |
| Export agent | LiteRT Torch, LiteRT-LM, QNN truth table | compile reports |
| Device agent | ADB, Termux, profiler, charge/bypass probes | device runbook/scripts |
| Corpus agent | Seed Corpus v0 manifests, license classes, OCR provenance | corpus reports |
| Eval agent | fertility, perplexity, recall, teacher panel, disagreement | eval harness |
| Sync agent | GitHub/HF/ADB upload and recovery | sync tests |
| Scheduler agent | static and Reflex policies | scheduler tests |
| Distillation agent | Runpod teacher scaffold and license review | distillation design/pilot |
| Falsifier agent | registry and negative tests | falsifier suite |

Model routing:

- Opus-class model: planning, review, risk analysis, final synthesis.
- GPT-5+ high reasoning: heavy code generation and test repair.
- Qwen2.5-Coder or equivalent: mobile/build-system/domain code review.
- Perplexity/Gemini deep research: unresolved export, Termux, RedMagic, and license questions.
- Knowledge graph: every decision, blocker, falsifier, and artifact relationship.

No subagent may ask the sleeping operator for interim decisions. Strategic unresolved questions become logged blockers with maximum possible work completed around them.

## Acceptance Gates

### Scientific Gate

- boundary clean
- source-grounded claims only
- falsifier coverage for every major claim
- license decomposition complete for every training chunk
- no surveillance, biometric, identity, clinical, production, or copyrighted-corpus framing

### Engineering Gate

- Mac simulation end to end
- all adapter contracts tested
- plug-replaceability tests pass
- audit hash-chain validator passes negative tamper tests
- sync recovery tests pass
- ELO frozen-layer invariants pass

### Device-Readiness Gate

- phone identity and SoC target resolved
- Termux/control stack probed
- profiler trace captured
- charge/bypass behavior known
- Experiment 0 passes
- Experiment 1 passes
- Experiment 2 resolved for SmolLM3
- no 100M-token run before these pass

### Brain-Functionality Gate

- fresh agent can reconstruct state from GitHub repo plus HF private artifact refs plus audit/KG logs
- no conversation context required
- all pending blockers are explicit
- all configs have hashes

### Research-Publishability Gate

- Phase 1A report includes methods, corpus license summary, hardware telemetry, energy regime, falsifier outcomes, method comparisons, and limitations
- claims are scoped to REDMAGIC 10 Pro+ unless additional devices are tested
- model weights are private unless license attestation permits distribution

## Required GitHub/HF Review Surface

At end of overnight execution, GitHub must contain:

- code and tests
- `docs/DECISIONS.md`
- `docs/FALSIFIERS.md`
- `docs/AUDIT-SPEC.md`
- `docs/CORPUS-SPEC.md`
- `docs/DEVICE-RUNBOOK.md` or `PHONE-ATTACH-RUNBOOK.md`
- `docs/EXECUTION-REPORT.md`
- manifests for any HF artifacts
- KG/audit logs small enough for GitHub, or pointers/hashes for large logs

HF private store under Architect-Prime must contain, when token/access exists:

- corpus shards larger than tiny fixtures
- checkpoint artifacts
- full profiler traces
- large telemetry bundles
- distillation teacher outputs
- model cards/dataset cards carrying boundary and license status

If HF access is absent, GitHub must contain pending-upload manifests with hashes and exact intended repo IDs.

## Open Questions For The Next Agent

These are not reasons to stop. They are work items or documented blockers.

1. **Phone availability and attachment timing:** If the REDMAGIC 10 Pro+ is not available at execution start, complete all dev-machine work and produce `PHONE-ATTACH-RUNBOOK.md`.
2. **HF token on the execution machine:** If absent, continue and create pending-upload manifests.
3. **Actual SoC identifier:** Must be probed before QNN target selection.
4. **Charge Separation on actual REDMAGIC 10 Pro+:** Likely available, but must be verified.
5. **Termux PyTorch viability:** Must be measured. If fragile, switch Termux to control plane and use native/host-mediated fallback.
6. **Exact Qwen2.5-1.5B QNN frozen-subgraph export:** Must be measured.
7. **SmolLM3 export verdict:** Must be measured and failure op recorded if no.
8. **Seed Corpus v0 source availability:** Default corpus spec is selected, but every source still needs license decomposition.
9. **Teacher model license:** Qwen3-Next preferred; Qwen2.5-72B fallback only after license attestation.
10. **Cross-device claims:** No other device exists. Do not make portability claims beyond design matrix.
11. **Federated execution:** No fleet exists. Keep design-only.

## Explicit Non-Goals

- production app
- app-store packaging
- public weight release without license attestation
- clinical, surveillance, biometric, identity, or human-subject use
- copyrighted corpus ingestion without per-source license decomposition
- cross-workstream runtime reuse
- declaring QNN, Vulkan, SmolLM3, or ELO superiority without measured falsifier-traced evidence

## Minimum Final Report Shape For Overnight Executor

The executor's final report must include:

- commit hash and pushed branch
- what was built
- what passed
- what failed
- what was blocked by missing phone/HF token/hardware
- falsifier outcomes
- corpus license status
- device readiness status
- HF artifact refs or pending-upload manifests
- next config flag to flip when phone becomes available

No summary artifact may claim completion without the underlying computed artifact.
