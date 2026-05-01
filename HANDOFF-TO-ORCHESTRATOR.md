# Handoff to the Polymath Orchestrator — Polymath AI Work Stream

You are the polymath orchestrator for the Zer0pa Polymath AI on-device training work stream. This document briefs you on what you inherit, what is expected of you, and what you produce. It does not pre-bake the structure of your PRD — that is your job. The substrate is on the table; shape it with your fresh eyes.

## Boundary

Research infrastructure for in silico on-device LLM training and multilingual / multi-domain knowledge model construction. Outputs are research artifacts (model checkpoints, training telemetry, evaluation reports, throughput measurements). No regulatory certification claims. No clinical or human-subject use. No surveillance, biometric profiling, or identity inference. No model weights distributed without an explicit license attestation. No training on copyrighted material without an explicit corpus-license decomposition. No deployment to production without a falsifier-traced acceptance gate.

## What you inherit

### Source brief (`source-briefs/`)

- **`01-on-device-training-blueprint.md`** — Operator-authored Pre-PRD Research Synthesis / Blueprint / Engineering Specification, 804 lines, ~52 KB, 2026-05-01. Hardware ground truth (REDMAGIC 10 Pro+, Snapdragon 8 Elite SM8650, 24GB LPDDR5X, Adreno 830 at 1.79 TFLOPS FP32 corrected, Hexagon NPU INT4/INT8/FP16, ~85 GB/s unified memory). ELO selective continual pretraining method (arXiv:2601.03648, EACL 2026 Industry Track; trains first + last transformer layers + lm_head, ~7% gradient FLOPs of full CPT, 5.88× average speedup). Model selection: Qwen2.5-1.5B primary (Apache 2.0, 151k vocab, 29+ languages, Snapdragon QNN deployment signal) or SmolLM3-3B Candidate B (Apache 2.0, 11.2T training tokens, 6 native languages, NoPE architecture, dual-mode reasoning, QNN export verdict pending). Data strategy: model-based multilingual selection per arXiv:2502.10361 (1B Llama matches MMLU baseline at 15% token volume), Gamayun curriculum result per arXiv:2512.21580 (2.5T tokens sufficient for sub-2B), language-aware sampling, contrastive cross-lingual alignment, 10-15% replay set for catastrophic-forgetting mitigation. Runtime architecture: heterogeneous Vulkan Queue 0/1 on Adreno (gradient-active layers) + QNN compiled subgraph on Hexagon (frozen middle layers) + Oryon CPU orchestration; HeteroInfer 1.34×–6.02× speedup evidence per arXiv:2501.14794 (MobiSys 2025). Throughput model: ~2.0–2.8M tokens/hour realistic (corpus timing: 100M tokens ≈ 40h, 1B tokens ≈ 17 days). Validation protocol: Experiment 0 (stack fit + baseline throughput) / Experiment 1 (tokenizer fertility audit) / Experiment 2 (SmolLM3-3B QNN export). Phased program: Phase 0 infrastructure (weeks 1-2) → Phase 1A Qwen2.5-1.5B ELO baseline (weeks 3-8) → Phase 1B cross-lingual objectives (weeks 9-12) → Phase 2 SmolLM3 parallel track → Phase 3 multimodal bridge (audio diffusion). Risk register and falsification criterion ("primary thesis falsified if a simpler method achieves equal or better evaluation scores at equal wall-clock budget on the real device"). Six explicit open questions for the next research pass.

**The blueprint is unusually high-quality and the operator authored it as a hybrid research-agent + synthesis-agent output.** The role chain compresses here. The blueprint already specifies hardware ground truth, model selection logic, training method, data strategy, runtime architecture, throughput model, validation protocol, and phased plan in PRD-adjacent detail. **Your PRD is not a re-do of the blueprint; it is the recursive-fresh-eyes augmentation that surfaces what the operator-as-synthesizer did not see, plus the executable specifics the executor needs that the blueprint does not yet pin down.**

### Synthesis (`synthesis/`)

- **`01-fresh-eyes-on-polymath-blueprint.md`** — Fresh-eyes reading of the operator's blueprint by the synthesis agent (Claude Opus 4.7, 2026-05-01). Surfaces:
  - The architectural reframe: Polymath IS a heterogeneous active-inference loop on a single SoC, with the model-being-trained as the agent's policy, the corpus as the environment, the validation suite as the observation channel, and the heterogeneous dispatch (CPU + GPU + NPU) as the agent's action repertoire. This subsumes the heterogeneous-dispatch, adaptive scheduling, validation-curriculum, and falsifier-registry concerns under one frame.
  - Cross-model disagreement (Qwen2.5-1.5B + SmolLM3-3B) and method disagreement (ELO + QLoRA + LoRA) as universal falsification primitives, mirroring the prior workstreams' DPA-3+MACE / TGLF+CGYRO / DLKcat+TurNuP+DeepEnzyme patterns.
  - Twelve specific things the blueprint does not see: (1) the operator's "110% pre-Runpod" axiom translates as "110% pre-device-corpus-investment" for Polymath; (2) the missing falsifier ledger / cross-model disagreement framing; (3) the RedMagic-only target and missing cross-device portability for non-cooled SD8E phones; (4) the missing distillation arm from a 72B Runpod-hosted teacher; (5) the missing federated multi-device training opportunity; (6) the missing teacher-panel evaluation discipline; (7) the unspecified Polymath corpus design (domain list, language list, scale, sources, license decomposition, OCR provenance); (8) energy budget as constraint not metric (multi-day training is plug-in-only operation); (9) the unspecified phone → GitHub + HF artifact-exfiltration plan; (10) the Reflex Scheduler should be Phase 1 not Phase 2; (11) the unspecified Stage 1 → Stage 2 transition checkpoint shape; (12) the multi-domain dimension treated less than the multi-lingual dimension despite "Polymath" implying both.
  - Pressure-test points for the orchestrator (nine explicit).
  - Three points warranting operator engagement before PRD lock: corpus design specification; non-cooled SD8E reference-phone availability; federated multi-device fleet availability.

### Doctrine (`RESISTANCE.md`)

- **`RESISTANCE.md`** — Anti-corruption doctrine imported from the DM3 substrate-reconstruction workstream. Read first. **The named corruptions — fp-shapematchRE, fp-rushtoend, fp-NULLasout, fp-approvalseek, fp-flatteryasfreedom, efficiency-as-corner-cutting — are binding constraints on every executor.** The discipline IS the resistance.

## Operator refinements (binding; carried verbatim from `MODUS-OPERANDI.md`)

- **Anti-MVP / anti-toy.** Target is never an MVP, never a first paying customer. Build the most overdesigned, best-in-class system the technology landscape supports.
- **110% pre-Runpod (or 110% pre-device-corpus-investment for Polymath).** The overnight executor must do 110% of what they can without GPU access (or without committing to multi-day device-side training).
- **Overnight long-horizon, autonomous, no interim reporting.** Once the brief is received, the executor runs end-to-end through the night without check-ins. Strip all process theater.
- **GitHub + Hugging Face are the review surface.** Code, schemas, tests, audit trails, decision logs, KG nodes, and the PRD itself commit to GitHub. Large datasets and AI model artifacts go to Hugging Face under the Architect-Prime user (not the Zer0pa org). HF token at `~/.cache/huggingface/token` on the originating machine. When execution completes, both stores must be up to date.
- **PRD self-contained in the repo.** Your PRD plus everything the executor needs lives in the GitHub repo. The executor can and must augment the PRD as they learn.
- **Fork-and-own across workstreams.** Pipelines/projects can steal parts, datasets, code patterns, harnesses, schemas, and ideas freely. They cannot be runtime co-dependent. Each workstream is sacrosanct as if it were its own thing.
- **RESISTANCE.md doctrine.** Every executor reads it before starting. The named corruptions are binding constraints.
- **Operator delegates engineering / science / commercial decisions** to you (synthesis + orchestrator). Surface only strategic decisions or boundary-evolution questions.

## What you must do

Write `PRD.md` at the top of this repo. The PRD specifies a long-horizon overnight execution by a separate set of overnight-executor agents on a different machine that operates the operator's REDMAGIC 10 Pro+ device via Termux + ADB / direct on-device shells. The PRD must front-load every dev-machine simulation, profiling, validation step, and small device-side calibration run before any 100M+ token corpus investment.

You are expected to:

- **Apply recursive fresh eyes.** The blueprint is itself a synthesis — your PRD must add value, not paraphrase. Where the blueprint sketches, lock interface contracts. Where it gestures, specify falsifiers and acceptance gates. Where it notes a frontier, evaluate whether deeper specification is warranted. **Augment and innovate.** If your PRD is not substantively richer than the blueprint plus this synthesis pass, you have not done your job. The synthesis agent is on record with twelve specific gaps and a list of fork-and-own opportunities from the prior workstreams; you are explicitly empowered to challenge the synthesis recommendations with reasoning.
- **Spawn sub-agents** in parallel worktrees per pipeline component (model loader + ELO layer freezing, Vulkan compute path, QNN compilation path, data ingestion + curation pipeline, corpus-license decomposition, evaluation harness, telemetry / logging, checkpoint sync, distillation arm if you scope it, federated arm if you scope it, Reflex Scheduler) and per cross-cutting concern (falsifier registry; cross-model disagreement aggregator; audit-trail schema with checkpoint-hash chain; corpus-design specification; energy-budget operational regime; cross-device portability matrix; phone → GitHub + HF artifact-exfiltration plan).
- **Use Perplexity Pro / Gemini Advanced deep research** at stuck and innovation points; surface strategic lookups to the operator. Specifically resolve:
  1. **ELO codebase availability** — GitHub URL or explicit "must reimplement" with effort estimate.
  2. **PyTorch Vulkan backend maturity audit** — what is the current state of PyTorch Vulkan in 2026? Production-ready, experimental, abandoned?
  3. **Termux training stack maturity audit** — what is the practical state of running PyTorch + transformers + huggingface_hub + ai_edge_litert under Termux on Android in 2026?
  4. **SmolLM3-3B QNN export verdict** — yes/no with specific failure op if no.
  5. **RedMagic 10 Pro+ active-cooling thermal characterisation** — sustained GPU clock with fan on vs off measured (or modelled if no published number).
  6. **REDMAGIC 10 Pro+ charge-bypass mode availability** — does it support USB-power-direct without going through the battery?
  7. **`huggingface_hub` push-from-Android maturity** — can the executor push checkpoints from inside Termux directly?
  8. **flower (federated learning framework) Android support state** — for Phase-2 federated scoping.
  9. **ai_edge_torch Qwen2.5-1.5B → TFLite → QNN compilation path** — has anyone published this exact compilation? What ops fail?
- **Resolve the corpus design specification.** The synthesis flagged this as the single biggest blocker. Surface to the operator: what is the Polymath corpus actually composed of? Domain list, language list, scale targets, source provenance, OCR provenance, license decomposition. Without operator engagement on this, Phase 1A starts with an undefined input.
- **Maximally front-load pre-device-corpus-investment engineering.** Acceptance criterion: when the executor commits to the multi-day Phase 1A run, every dev-machine validation has passed, every device-side small-corpus calibration has run, every component is plug-swap-tested, and the falsifier registry + audit log + cross-model disagreement aggregator are wired and tested. The cutover from Phase 0 to Phase 1A must be a config-flag-shaped change.

## Shape of the PRD

The structure is yours. Mirror the sibling Health PRD, Materials PRD, Energy PRD, or Synbio handoff if any of those patterns help; depart where your fresh eyes warrant. The PRD must cover at minimum:

- **Scope and boundary** with the verbatim research-only block and the explicit Polymath-specific exclusions (no surveillance / biometric / identity inference, no copyrighted-corpus framing, no model-weights distribution without license, no production deployment without falsifier-traced acceptance gate). Anti-MVP / anti-toy / overdesigned best-in-class explicitly stated.
- **Architecture** that the overnight executor can decompose into parallel sub-streams without further operator input. Specify interface contracts (PyTorch nn.Module API for the model; Vulkan compute shader API + VkSemaphore/VkEvent contracts for cross-queue sync; QNN graph compilation API via ai_edge_litert; ADB + Termux shell for orchestration; HuggingFace Hub API for checkpoint push). Plug-replaceability invariant ("swap Qwen2.5-1.5B for SmolLM3-3B in <1 day with no downstream breakage; swap Vulkan for OpenCL fallback in <1 day; swap QNN for CPU-fallback in <1 day").
- **Active-inference reframe** as the architectural primitive (per synthesis recommendation; you may take, refine, or override).
- **Falsification framing** with cross-model disagreement (Qwen + SmolLM3) and method disagreement (ELO + QLoRA + LoRA) specified as first-class quantities flowing through the audit log; falsifier registry covering: invalid model checkpoint (sha256 mismatch), tokenizer fertility above threshold, OOM, thermal throttle below 600 MHz sustained, energy budget exceeded, catastrophic forgetting > 1pp on English MMLU, cross-model disagreement above threshold, method disagreement (ELO vs QLoRA Spearman ρ < 0.6), license drift (corpus source without explicit attestation), overclaim (model output not supported by corpus), surveillance / biometric / identity-inference framing in any artifact.
- **Build sequence** that front-loads Mac-side simulation + small device-side validation + Experiment 0/1/2 before Phase 1A corpus investment. Explicit per-overnight-agent decomposition. Layer order. Gating test cases per phase.
- **Agent topology** — Opus 4.7 + GPT-5+ + domain LLMs (Qwen2.5-Coder family for the mobile-systems domain reasoner; or Qwen3-Next-80B-A3B-Instruct as the design-review-and-distillation teacher on Runpod) + Perplexity / Gemini + KG with episodic memory.
- **Audit-trail spec** — campaign-grade per-training-run provenance log; KG schema with explicit node and edge types (Run / Phase / Experiment / Checkpoint / EvalArtifact / Decision / Falsifier / DispatchRecord / DeviceState); per-step log shape; sha256 hash chain across all checkpoints + all eval-result records.
- **Phase 0 deliverable** — Experiment 0 / 1 / 2 all passing on the actual REDMAGIC with measurements committed to GitHub + HF; ELO Stage 1 reimplementation in PyTorch validated against published ELO results on a synthetic-corpus benchmark; tokenizer fertility audit with full per-language table; SmolLM3-3B QNN export verdict resolved.
- **Phase 1A deliverable** — first multilingual ELO Stage 1 run on a 100M-token Polymath corpus slice on the actual device; per-language validation losses; per-domain validation losses; cross-model disagreement scorecard (Qwen + SmolLM3); method disagreement scorecard (ELO vs QLoRA); teacher-panel evaluation results.
- **Self-bootstrapping reasoner** — every (input, output, falsifier-judgment) triple from the eval pipeline writes to a private dataset that compounds the moat; how the dataset structure mirrors Health's reasoner_queue/runs/<rid>/tuples.jsonl shape (forked, not shared).
- **Distillation arm specification** (synthesis recommendation; you commit or override) — Qwen2.5-72B (or Qwen3-Next-80B-A3B-Instruct) on Runpod as teacher; distillation corpus = Polymath corpus + on-policy teacher outputs; student = Qwen2.5-1.5B distilled then ELO-fine-tuned. Cost estimate. Acceptance gate.
- **Federated multi-device arm specification** (synthesis recommendation, Phase-2 scoping) — flower-based federated ELO Stage 1 across multiple SD8E phones; per-device corpus partition; aggregation cadence; coordinator-side averaging procedure. If the operator does not have multiple SD8E phones, scope this as research-publishable design for Phase 2 only.
- **Cross-device portability matrix** (synthesis recommendation) — Experiment 0 on RedMagic + at least one non-cooled SD8E reference phone; per-device sustained throughput; per-device thermal envelope; per-device battery-cycling regime.
- **Reflex Scheduler specification** — Phase 1 default per synthesis recommendation; bandit-style UCB policy over per-op-shape latency history; static-placement fallback for ablation; instrumentation for op-level latency tracking.
- **Energy budget operational regime** — plug-in-only during multi-day training; charging-thermal-regime measured by Experiment 0; battery-health protection (charging algorithm spec, thermal cutoffs, scheduled rest periods); charge-bypass mode if RedMagic supports it.
- **Phone → GitHub + HF artifact-exfiltration plan** — per artifact class (code, telemetry, checkpoints, full model weights, profiling traces); mechanism per class (ADB pull, Termux gh push, on-device huggingface_hub push); frequency of sync; recovery procedure on sync failure.
- **Acceptance gates** — scientific (falsifier coverage, source grounding, no out-of-scope claims), engineering (Mac simulation runs end-to-end, plug-swap test passes, all six device-readiness experiments passed), brain-functionality (next-agent state reconstructible from repo + KG + audit log without conversation context), device-readiness (Experiment 0/1/2 all passing on actual device).
- **Productisation framing** — none in the MVP / first-customer sense. The success signal is research-publishable: a 1.5B-3B parameter Polymath model running on a phone with measurable multilingual + multi-domain quality + ELO efficiency claims that hold under cross-model + method disagreement falsification.
- **Open questions for the operator / for the next agent** — explicitly. The corpus design specification is the biggest one. The non-cooled SD8E reference phone availability and the multi-device federated fleet availability are the other two.

Be granular. The overnight executor is a separate agent on a separate machine with no conversation context. Every interface, every contract, every threshold, every fallback must be readable from the PRD alone.

## Constraints

- Mac storage is bounded on the originating machine (~42 GiB free at last check); bulk artifacts go to private Hugging Face under Architect-Prime when offload is needed.
- HF token at `~/.cache/huggingface/token` on the originating machine. Cross-machine, the operator provides.
- The training device is the operator's REDMAGIC 10 Pro+ — a personal phone. Do not assume access is permanent or continuous; multi-day training runs require explicit operator availability.
- ADB / USB-debugging / developer-mode access on the device is required for the executor to operate.
- Termux is the on-device Linux environment; the executor must work within Termux's package availability and Android security model.
- No Docker on the originating Mac.
- No Docker on the device (Android does not support Docker without root).
- No bulk local datasets — manifests + metadata + small slices only on the Mac. Curated Polymath corpus chunks may live on the device for training; full corpus archives go to HF.
- GitHub canonical. All sub-agent work commits back to `Zer0pa/Polymath-AI` before PRD finalisation.
- No regulatory or clinical claims. No human-subject inference.
- No surveillance, biometric profiling, or identity-inference framing in any artifact.
- No copyrighted-corpus framing without explicit license decomposition per source.
- No model-weights distribution without explicit license attestation.
- **No cross-workstream runtime co-dependency.** Fork-and-own of patterns / code / schemas / harnesses / datasets from sibling workstreams IS explicitly permitted.
- **Multi-day training is plug-in-only operation by physical necessity.**

## Authorities and tooling

- `gh` CLI authenticated as Zer0pa-Architect-Prime on the originating machine; cross-machine, the operator provides.
- HF token at `~/.cache/huggingface/token` on the originating machine; under Architect-Prime user (not Zer0pa org).
- Anthropic Opus 4.7 + Claude Code SDK or Anthropic Console — primary planning + code review at maximum reasoning effort.
- OpenAI GPT-5+ at xhigh reasoning — primary heavy-code generator.
- Perplexity Pro / Gemini Advanced — stuck-point and innovation deep research.
- Runpod available for the distillation teacher (Qwen2.5-72B or Qwen3-Next-80B-A3B-Instruct) — same `gh` / token paths as prior workstreams. Polymath does not use Runpod for the device-side training; only for teacher-corpus augmentation if you scope distillation.
- ADB (Android Debug Bridge) + Termux + Snapdragon Profiler + Android GPU Inspector for on-device work.
- PyTorch + transformers + huggingface_hub + ai_edge_litert + ai_edge_torch as the primary ML stack.
- Vulkan SDK + Qualcomm Vulkan Adreno Layer tool + QNN SDK as the primary on-device compute stack.

## Where the PRD lands and what comes next

Commit `PRD.md` to the top level of `Zer0pa/Polymath-AI`. Push to GitHub. After the PRD is final, write `HANDOFF-TO-OVERNIGHT-EXECUTOR.md` describing what the next role inherits, what they produce, and the constraints / authorities they operate under. Mirror the structure of this document.

The operator will then trigger the overnight execution on a separate machine using a startup prompt analogous to `ORCHESTRATOR-STARTUP-PROMPT.md`. The executor agent operates the device via ADB / Termux from that machine.

## Success criteria

- A PRD that the overnight executor can decompose into parallel sub-streams without further operator input.
- Every interface contract locked. Every falsifier specified. Every acceptance gate measurable.
- The corpus design specification resolved with operator engagement, or explicitly captured as the only remaining operator-engagement open question.
- A clear Phase 0 deliverable (Experiment 0/1/2 all passing on actual device, ELO reimplementation validated, tokenizer fertility audit complete, SmolLM3 export verdict resolved).
- A clear Phase 1A deliverable with falsifier-traced cross-model + method disagreement scorecards and teacher-panel evaluation.
- The operator-override discipline carried through every artifact (no shared runtime instances, no shared corpora, no shared git imports — though fork-and-own of any pattern is permitted; this synthesis identified specific forks from Health / Materials / Energy / Synbio).
- The deep-research lookups (ELO codebase, PyTorch Vulkan, Termux stack, SmolLM3 QNN, charge-bypass, ai_edge_torch path) resolved or escalated.
- Open questions explicitly listed.
- Anti-MVP / anti-toy / overdesigned best-in-class discipline visible in every component spec.
- RESISTANCE.md doctrine carried through — no fp-shapematchRE / fp-rushtoend / fp-NULLasout / fp-approvalseek / fp-flatteryasfreedom / efficiency-as-corner-cutting in the PRD's framing or in the executor's planned artifacts.

## What you should pressure-test before locking the PRD

The synthesis agent committed to several positions that you should pressure-test with your fresh eyes:

- **Is the heterogeneous active-inference loop reframe the right architectural primitive?** The synthesis argues yes (subsumes heterogeneous-dispatch, adaptive scheduling, validation-curriculum, falsifier-registry under one frame). You may have a stronger frame.
- **Should the Reflex Scheduler be Phase 1 or Phase 2?** The synthesis argues Phase 1 (best-in-class mandate); the blueprint argues Phase 2 (measure first). You commit.
- **Should distillation from a 72B Runpod-hosted teacher run as a parallel arm?** The synthesis argues yes (often beats direct CPT for sub-2B students; ~$25 marginal cost). The blueprint does not consider this.
- **Should federated multi-device training be scoped for Phase 2?** The synthesis argues yes (overdesigned best-in-class territory). The blueprint does not consider this.
- **Should the cross-device validation matrix include a non-cooled SD8E reference phone?** The synthesis argues yes (portability matters for any work intended to publish or distribute). The blueprint targets RedMagic only.
- **What is the corpus design specification?** The synthesis argues it must be a first-class PRD component with operator engagement.
- **Is the multi-domain dimension treated equally with the multi-lingual dimension?** The synthesis argues yes.
- **What is the energy-budget operational regime?** The synthesis argues plug-in-only with charging-thermal-regime measured.
- **What is the cross-machine artifact-exfiltration plan from phone → GitHub + HF?** The synthesis argues this must be specified per artifact class.

These are pressure-test points, not pre-baked answers. Take them or override them with reasoning.
