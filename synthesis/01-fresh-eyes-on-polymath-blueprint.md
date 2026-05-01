# Fresh-Eyes Synthesis on the Polymath On-Device Training Blueprint

Synthesis-agent output. Captures the operator-read on the source brief (`source-briefs/01-on-device-training-blueprint.md`) by Claude Opus 4.7 (1M context), 2026-05-01. Read by the polymath orchestrator as the substrate for their own fresh-eyes augmentation.

## Boundary

Research infrastructure for in silico on-device LLM training and multilingual / multi-domain knowledge model construction. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. No surveillance, biometric profiling, or identity inference. No model weights distributed without explicit license attestation. No training on copyrighted material without explicit corpus-license decomposition.

## Acknowledgement

The Polymath blueprint is unusually high-quality. It is the first Zer0pa source document that is **operator-authored as a hybrid research + synthesis output** — the role chain compresses and the doc explicitly says so ("Pre-PRD Research Synthesis — Blueprint / Engineering Specification ... supersedes all prior research briefs in this thread"). The hardware ground truth (corrected FP32 figure 1.79 TFLOPS, not 3.38; 24GB shared LPDDR5X with ~85 GB/s; Adreno 830 TBDR queue rules), the ELO selection (EACL 2026 Industry Track, arXiv:2601.03648), the model selection logic (Qwen2.5-1.5B primary on tokenizer + Snapdragon QNN deployment signal; SmolLM3-3B as Candidate B), the data strategy (model-based multilingual selection per arXiv:2502.10361; Gamayun 2.5T-tokens result per arXiv:2512.21580; replay 10-15% as catastrophic-forgetting mitigation), the runtime architecture (Vulkan Queue 0/1 + QNN compiled subgraph + Oryon orchestration; HeteroInfer 1.34×–6.02× heterogeneous-dispatch evidence per arXiv:2501.14794), the throughput model (~2.0–2.8M tokens/hour realistic), the validation protocol (Experiment 0 / 1 / 2 as blocking gates), the phased plan (Phase 0 → 1A → 1B → 2 → 3), and the falsification criterion ("primary thesis falsified if a simpler method matches at equal wall-clock") — all of these are decisive engineering judgments that this synthesis does not repeat.

This synthesis augments where the blueprint does not yet see. The operator-as-synthesizer is closer to the work than any prior research-agent-only input has been; the recursive-fresh-eyes principle requires this synthesis to find what the operator's own synthesis missed.

## The architectural reframe — Polymath is a heterogeneous active-inference loop on a single SoC, not a forward training pipeline

The blueprint describes ELO Stage 1 → Stage 2 as a forward training pipeline with heterogeneous dispatch. This is correct but stops one step short of the architectural primitive that subsumes the existing intersections.

**Polymath is best framed as an active-inference loop on a single SoC, with the model-being-trained as the agent's policy, the corpus as the environment, the validation suite as the observation channel, and the heterogeneous dispatch (CPU + GPU + NPU) as the agent's action repertoire.** Stated precisely:

- **Hidden state** the agent infers about: the target multilingual / multi-domain distribution. Initially uncertain (base checkpoint); gets updated as ELO Stage 1 progresses.
- **Generative model**: Qwen2.5-1.5B (or SmolLM3-3B) as a probabilistic model from (token sequence, language tag, domain tag) → next-token distribution.
- **Free energy F(θ)** the agent minimises: cross-entropy loss on the curated corpus + a complexity penalty (the metabolic-burden analog here is *parameter update cost* — gradient FLOPs × wall-clock × thermal-throttle factor).
- **Expected free energy G(π)** the agent uses to choose actions: per-language sampling weight, per-domain curriculum stage, per-batch sequence length, per-step optimizer hyperparameters. The blueprint's "language-aware sampling curriculum tied to per-language validation loss" is *exactly* this — the agent picks the next sampling weight to maximise expected information gain on the worst-performing language.
- **Action repertoire** = heterogeneous dispatch decisions: which op to NPU vs GPU vs CPU; which queue priority; when to recompile QNN graph; when to flip from Stage 1 to Stage 2.

This reframe matters for the orchestrator's PRD because it suggests the **Reflex Scheduler** (blueprint §5.6) should be specified as a Phase-1 first-class component, not a Phase-2 if-needed component. Under the active-inference framing, the dispatch policy IS the agent's action policy — it cannot be Phase-2 without admitting that the agent is acting blind in Phase 1. Best-in-class is a Phase-1 adaptive scheduler with measured baseline.

Within the Zer0pa portfolio, this is the same reframe Health applied (falsification-engine), Materials applied (variational unification), Energy applied (information-theoretic channels), and Synthetic Biology applied (active-inference loop with cell-free TX-TL as Build-Test substrate). For Polymath, the substrate is the SoC itself — heterogeneous compute as the action surface.

## Cross-model disagreement is the universal falsification primitive — here too

The blueprint specifies Qwen2.5-1.5B as primary and SmolLM3-3B as Candidate B with a decision rule based on QNN export validation. This treats them as a **selection** problem (pick one). **The synthesis recommendation: treat them as an ensemble at evaluation time.** Concretely:

- Train Qwen2.5-1.5B + ELO on the Polymath corpus.
- In parallel (or sequentially if Phase 1 timeline allows), train SmolLM3-3B + ELO on the same corpus (assumes QNN export validates per Experiment 2).
- At evaluation, compute the **disagreement metric** between the two models on (a) per-language perplexity, (b) in-domain Polymath recall, (c) cross-lingual transfer, (d) catastrophic-forgetting delta.
- High agreement = high confidence in the ELO method on this corpus. High disagreement = a prediction whose model-dependence flags it for human review.

This is the same primitive Materials applied with DPA-3 + MACE, Energy applied with TGLF + CGYRO + GACODE, and Synbio specified for DLKcat + TurNuP + DeepEnzyme + CatPred. **The Polymath orchestrator should specify cross-model disagreement as a first-class quantity flowing through the audit log alongside primary outputs.** It costs roughly 1.5-2× more device wall-clock (one of the two could run on a Mac as a CPU-only baseline; only the primary needs the full ELO + Vulkan + QNN heterogeneous stack), but produces a falsification trace per evaluation that single-model results cannot match.

A second cross-model layer: **method disagreement.** Run ELO + QLoRA + standard LoRA in parallel on a small corpus slice. The blueprint already names QLoRA as a comparison baseline; this synthesis upgrades that to a falsifier signal — when ELO and QLoRA disagree on which examples the model improves on, that disagreement IS the evidence about which method is doing the right kind of update. The blueprint's risk-register entry "if ELO yields no improvement over QLoRA on in-domain Polymath evaluation, the corpus may be teaching behavioral style not factual structure" is correct; the synthesis recommendation is to bake this comparison into the evaluation harness from the start.

## Twelve specific things the blueprint does not see

### 1. The "110% pre-Runpod" axiom translates as "110% pre-device-corpus-investment" for Polymath

The operator's binding axiom (`MODUS-OPERANDI.md` § Operator refinements 2026-05-01) is "Agent must do 110% of what they can before Runpod port." Polymath has no Runpod. **The translation: the executor must do 110% of what they can before any device-side multi-day training run begins on a curated 100M+ token Polymath corpus.** That includes:

- Full ELO Stage 1 reimplementation in PyTorch on a Mac, validated against published ELO results on a synthetic-corpus benchmark before any phone-side execution.
- Full Vulkan + QNN dispatch path validated on small (10K-100K token) device-side runs before scaling to corpus volume.
- Full corpus-ingestion pipeline (OCR normalisation, language detection, deduplication, quality scoring, replay-set construction) validated end-to-end on a small corpus slice before the production corpus is committed.
- Experiment 0 / 1 / 2 all passed on the device with their published thresholds.
- Tokenizer fertility audit (Experiment 1) completed and resolved (vocabulary extension if needed) before the production tokenizer is locked.
- Cross-model disagreement harness wired into evaluation before the first corpus run.
- Distillation arm (see #4 below) implemented and benchmarked before deciding final method.

The phrase "110% pre-device-corpus-investment" should appear verbatim in the orchestrator's PRD as the Phase-0/Phase-1A boundary criterion.

### 2. The blueprint has no falsification ledger / cross-model disagreement framing

The Risk Register (blueprint §10) is sound but it is a *risk* register, not a *falsifier* registry. The distinction matters: a risk is a probability-weighted future event; a falsifier is a structural disconfirmation gate that fires on a current observation. Per the RESISTANCE.md doctrine and the prior workstream patterns, Polymath needs:

- **`fp-shapematchRE` analog**: do not declare a model "Polymath-quality" because it matches a benchmark distribution; require cross-model disagreement + per-domain recall + held-out blind evaluation.
- **`fp-rushtoend` analog**: do not declare Phase 1A complete because Stage 1 wall-clock is exhausted; require all six Phase-1A acceptance criteria measured.
- **Cross-model disagreement gate**: Qwen2.5-1.5B and SmolLM3-3B (when available) must disagree below threshold on the validation set, or both predictions are flagged.
- **Method disagreement gate**: ELO and QLoRA must rank candidate samples by improvement-credibility within Spearman ρ > 0.6, or the corpus is teaching style not knowledge.
- **Tokenizer-fertility gate**: any language with fertility > 2.5× English baseline cannot enter the production curriculum without explicit vocabulary extension.
- **Catastrophic-forgetting gate**: English MMLU degradation > 1 percentage point vs base checkpoint blocks Phase 1B advancement.
- **Energy-budget gate**: joules/token above (TBD threshold) blocks the run from being pushed to multi-day operation.
- **Thermal-stability gate**: GPU clock < 600 MHz sustained for > 10% of any 1-hour window blocks the run.

### 3. The blueprint treats RedMagic 10 Pro+ as the only target

Snapdragon 8 Elite ships in many phones — Galaxy S25, OnePlus 13, Xiaomi 14T Pro, Asus Zenfone 12, etc. The RedMagic 10 Pro+ is the first device because the operator owns one and because of its active fan. **The synthesis recommends specifying Polymath as hardware-portable across SD8E devices**, with RedMagic-specific enhancements (active cooling) as a Phase-1A optimisation rather than a Phase-1A precondition.

The portability question: which assumptions in the blueprint break on a non-cooled SD8E phone?

- **Sustained throughput** (blueprint §6.2): the 30% thermal-throttling estimate is RedMagic-with-fan-on. Without active cooling, expect 40-50% throttling under sustained training.
- **Phase 1A 6-week timeline** (blueprint §8): assumes 2.5M tokens/hour midpoint. On a non-cooled SD8E phone at 1.5M tokens/hour, the 100M-token Phase 1A run takes ~67 hours instead of 40 hours. Still tractable, but the curriculum scheduling assumptions need adjustment.
- **Battery-life floor**: a non-cooled phone may also have less aggressive battery management; sustained training at high GPU load drains faster.

The orchestrator should specify a **cross-device validation matrix** as part of Phase 1A — at minimum, Experiment 0 should run on the RedMagic plus one non-cooled SD8E reference phone (commercially available; can be borrowed or rented for a 2-hour run).

### 4. Distillation from a larger teacher is missed

The blueprint treats CPT (continued pretraining) and ELO as the only adaptation paths. **Distillation is a structural alternative the blueprint does not consider.** Concretely:

- **Teacher**: Qwen2.5-72B (or 32B if hardware constrains; or Qwen3-Next-80B-A3B-Instruct as a more recent option) running on Runpod.
- **Distillation corpus**: the Polymath corpus + on-policy outputs from the teacher conditioned on prompts that elicit Polymath-domain knowledge.
- **Student**: Qwen2.5-1.5B (or SmolLM3-3B), distilled from teacher logits + ground-truth corpus tokens, then ELO-fine-tuned on the same corpus.

Why distillation often beats direct CPT for sub-2B students:

- The teacher's logit distribution is denser supervision than next-token cross-entropy on the corpus alone.
- Out-of-distribution corpus passages (which a 1.5B student would otherwise compress poorly) get teacher-mediated guidance.
- The teacher can be queried for synthetic Q&A pairs that broaden the student's coverage of the corpus's implied knowledge.

The cost: a Runpod-hosted 72B teacher run is roughly $0.50/hour at current pricing; distillation over 100M tokens ≈ 30-50 GPU-hours ≈ $15-25. Negligible relative to the ELO student training time. **The orchestrator should specify a distillation arm as a Phase-1A parallel track**, evaluated against the ELO-only baseline at the Phase-1A gate.

This is also where Polymath touches Runpod after all — not for the device-side training (which stays on the phone), but for the teacher-side distillation. Runpod is not eliminated from Polymath; it is repositioned as the teacher-corpus-augmentation layer.

### 5. Federated / multi-device training is missed

If the operator has access to multiple SD8E phones (or can recruit a small fleet), federated learning is a structural option the blueprint does not explore. Concretely:

- Each device holds a partial corpus partition (e.g., partitioned by language, by domain, or by temporal slice).
- Each device runs ELO Stage 1 locally on its partition.
- Periodically (e.g., once per hour, or once per Stage-1 epoch), devices sync weight deltas via a coordinator (a Mac running flower / Federated Scenario or an AWS Lambda-shaped aggregator).
- The aggregator computes a weighted average of the deltas and pushes the updated boundary-layer weights back to every device.

Why this is overdesigned-best-in-class territory:

- Per-device wall-clock is reduced proportionally to fleet size.
- Per-device thermal envelope is relaxed (each device runs less, cools more).
- The aggregated model converges with the same total token-volume as a single-device run, but parallel-in-wall-clock.
- It demonstrates that Polymath scales beyond the single-operator phone — making it research-publishable rather than personal-device-tooling.

Cost: minimal. flower (the federated learning framework, Apache-2.0) supports PyTorch and runs on Android. The aggregator is a Mac process. The model-decomposition step (which Polymath layers are federated-shared) is already structurally clean under ELO — only the boundary layers need to be federated; middle layers stay frozen and identical across devices.

The orchestrator may scope this as Phase-2 if a single-device baseline must complete first; it should not be unscoped entirely.

### 6. No teacher-model ensemble for evaluation

Beyond cross-model disagreement (#2 above), the blueprint specifies eval primarily as perplexity + MMLU + custom recall. **A frontier-teacher-judged eval is missing.** Concretely:

- Take the Polymath model's outputs on a hold-out evaluation set (closed-book Q&A, generation prompts, cross-lingual translation tasks).
- Submit each output to a panel of 3 frontier teachers (e.g., Claude Opus 4.7, GPT-5+, Gemini 2.5 Ultra) with a structured rubric.
- Compute Polymath-vs-base-checkpoint preference rates on each rubric dimension.
- Cross-validate: a teacher panel that internally disagrees flags the eval item.

Cost: minimal. Each eval run is a few hundred API calls per teacher; total budget < $50. The signal-to-noise ratio of frontier-teacher judgment is much higher than benchmark-leaderboard scores for novel multilingual / multi-domain knowledge. **The orchestrator should specify this teacher-panel eval as the primary acceptance signal for Phase 1A**, with perplexity / MMLU as supporting metrics.

### 7. The "Polymath corpus" itself is unspecified

The blueprint's data strategy (§4) is structurally sound — pipeline architecture, balancing, replay, curriculum, cross-lingual objectives — but it does not specify **which corpus**. Domain coverage, language list, scale targets, source provenance, OCR origin, IP licensing decomposition, ethical-sourcing audit — these are all left for downstream resolution.

For an "anti-toy / overdesigned best-in-class" build, the corpus IS the moat. The blueprint's own §4.1 says "the corpus may matter more than the architecture." The synthesis recommendation: **the corpus design must be a first-class spec component in the orchestrator's PRD**, not a downstream concern.

Concretely, the orchestrator should specify:

- **Domain list**: music technology / music production / audio (per blueprint §8 Phase 3 framing); plus what else? Polymath suggests breadth — philosophy, history, mathematics, physics, biology, computer science, languages.
- **Language list**: at minimum the languages the operator personally needs (English + ?). At maximum, the 29+ Qwen2.5-1.5B-supported languages with fertility audit prioritising the operator's working set.
- **Scale target**: 100M tokens for Phase 1A pilot; 500M tokens for Phase 1B; 1B tokens optional Phase 2.
- **Source provenance**: book corpora (which?), academic papers (which open-access set?), structured knowledge (Wikipedia? Stack Exchange?). Specifically, what is the Project-Gutenberg-equivalent baseline for Phase 0 Experiment 0?
- **License decomposition**: per Synbio's four-column license audit pattern, every corpus source should be classified A/B/C/D/E with explicit attribution and redistribution rights.
- **OCR provenance**: which OCR pipeline (Tesseract? GPT-4V?) for non-textual sources; perplexity-damage detection threshold per blueprint §4.2 Stage 2.

Without this, Phase 1A starts with an undefined input. The orchestrator must close this gap.

### 8. Energy budget is a metric, not a constraint, in the blueprint

The blueprint mentions joules/token as a metric (§9 Primary metrics — hardware/system) and notes battery drain as a Phase-2 concern. **For multi-day on-device training, the energy budget is a constraint, not a metric.**

Concretely:

- A REDMAGIC 10 Pro+ has a ~6500 mAh battery at ~3.85V nominal ≈ 25 Wh.
- Sustained training at 8W TDP draws ~3 hours of battery life per full charge.
- A 100M-token Phase-1A run at 2.5M tokens/hour ≈ 40 hours of training. That is 13+ full charge cycles.
- **Multi-day training is plug-in-only operation by physical necessity.**
- Charging at 80W (RedMagic spec) generates significant heat that interacts with the active-cooling design.
- Continuous plug-in + sustained 8W draw for 40+ hours is a battery-cycling scenario the device manufacturer did not test.

The orchestrator's PRD must specify:

- **Plug-in-only operation** during Phase 1A and beyond.
- **Charging-during-training thermal regime**: does the active fan handle charging heat + GPU heat simultaneously? Experiment 0 should measure this.
- **Battery health protection**: charging algorithm specifications, thermal cutoffs, scheduled rest periods.
- **Alternative: external power bank + bypass charging**: some phones support charge-bypass mode where USB power feeds the SoC directly without going through the battery. This eliminates the battery-cycling concern. Whether REDMAGIC 10 Pro+ supports this needs verification.

### 9. Cross-machine review surface for phone artifacts is unspecified

Health, Materials, Energy, Synbio all commit to GitHub from a Mac/Linux dev machine. Polymath runs on Android. **The artifact-exfiltration mechanism from phone → GitHub + HF is not specified in the blueprint.**

Concretely:

- **Code lives on the dev Mac**, pushed to Zer0pa/Polymath-AI on every commit. ✓ (same as prior workstreams)
- **Telemetry / logs** generated on-device. Mechanism: ADB `pull` from the dev Mac at end of session, or Termux `gh` push from inside Android during training. Decision needed.
- **Checkpoints** generated on-device. ELO Stage 1 checkpoints are small (the trainable layers are ~210M params * 4 bytes = ~840 MB; gzipped ~500 MB). Push to HF (Architect-Prime user) via `huggingface_hub` running on-device. Tractable.
- **Full final model weights** for distribution. The full 1.5B FP16 model is 3 GB; HF push handles it. Same mechanism.
- **Profiling traces** from Snapdragon Profiler. These are large binary files. ADB pull to Mac, then Mac pushes to HF or to a Zer0pa-Architect-Prime cloud bucket.

The orchestrator's PRD must specify which mechanism per artifact class, the frequency of sync, and the recovery procedure if a sync fails mid-training.

### 10. The Reflex Scheduler should be Phase 1, not Phase 2

The blueprint (§5.6) frames the Reflex Scheduler as a Phase-2 if-needed component, with the Phase-1 default being static placement. **Per the active-inference reframe (architectural reframe section above) and the operator's anti-toy / overdesigned best-in-class mandate, the Reflex Scheduler should be Phase 1.**

The static-placement-then-measure-then-adaptivate sequence is the *minimum-viable-product* pattern the operator has explicitly rejected. The best-in-class pattern is to ship the adaptive scheduler from the start, with a static-placement fallback for ablation.

Implementation cost is low — the bandit-style UCB policy over per-op-shape latency history is a few hundred lines of Python; the dispatch table is a dict; the per-op latency history is a sqlite table. The orchestrator should specify the Reflex Scheduler as Phase-1 default.

### 11. The Stage 1 → Stage 2 transition checkpoint is unspecified

The blueprint specifies that Stage 1 → Stage 2 retires the QNN graph and moves the full model to Vulkan for alignment. **What is the checkpoint shape at the boundary?**

Concretely:
- Stage 1 produces updated weights for layers 0, 27, and lm_head.
- Stage 2 starts from a "merged" model where these new boundary weights are reintegrated into the original 28-layer network.
- The merge step is non-trivial: the boundary-layer activations may have shifted distribution; the middle frozen layers may produce different outputs given the new boundary inputs.
- The checkpoint at the Stage 1 → Stage 2 boundary should carry: (a) the updated boundary weights, (b) the original middle-layer weights, (c) a calibration dataset for the alignment fine-tune, (d) per-layer activation statistics from Stage 1 final state, (e) the QNN graph compilation artifact for re-use if rolled back.

The orchestrator's PRD should specify the boundary checkpoint shape and the recovery procedure (roll-back to Stage 1 if Stage 2 alignment fails).

### 12. "Polymath" implies multi-domain + multi-lingual, but the blueprint emphasises multi-lingual

The blueprint's data strategy (§4) is dominantly multilingual — language balancing, tokenizer fertility, cross-lingual objectives. The multi-domain dimension (philosophy, history, music, mathematics, etc. — what makes the model a *polymath*) is not structurally specified. Phase 3 mentions audio diffusion for music technology, but multi-domain knowledge construction in the text-only Phase 1 is not explicit.

The synthesis recommendation: **the orchestrator's PRD should treat multi-domain alignment as at least equally important as multi-lingual alignment.** Concretely:

- Per-domain validation loss (analogous to per-language validation loss) drives the curriculum sampling weight.
- Cross-domain transfer benchmarks (does the model that learned music theory help with mathematics? does the philosophy corpus benefit from the mathematics corpus?) must be measured.
- Domain-specific tokenizer additions (musical notation, mathematical notation, chemistry SMILES, code) should be considered alongside language-specific vocabulary extension.

The "Polymath" framing is the moat: a single 1.5B-3B-parameter model that is genuinely cross-domain on a curated corpus, running on a phone, is a research-publishable result. A multilingual model alone is well-trodden ground (Qwen2.5, SmolLM3 already do this); the multi-domain dimension is what Zer0pa's curated corpus uniquely provides.

## A non-cross-workstream substrate proposal — but a fork-and-own opportunity

Polymath does not yet have a Materials/Energy/Synbio-shaped cross-workstream substrate-sharing recommendation, because the Polymath blueprint did not propose one. The operator-as-synthesizer was disciplined here.

That said, the synthesis agent surfaces a **fork-and-own opportunity** (explicitly permitted under the operator's 2026-05-01 refinement):

- **Health's TxGemma fine-tuning queue + reasoner-tuple discipline** translates directly to Polymath's evaluation-feedback loop. Each (input, output, falsifier-judgment) triple from the teacher-panel eval feeds a dataset that compounds the moat. Polymath should fork Health's `reasoner_queue/runs/<rid>/tuples.jsonl` shape and own its own copy.
- **Materials' DPA-3 + MACE ensemble disagreement** translates as Qwen2.5-1.5B + SmolLM3-3B disagreement, plus ELO + QLoRA method disagreement, plus per-fold ensemble variance on the eval set. Fork the disagreement-aggregator code from Materials' `wave 4c` cross-layer integration.
- **Energy's same-shape Runpod cutover with `httpx.MockTransport` golden-fixture invariance** translates as device-cutover invariance — the same training run with the same seed should produce bit-identical updates whether the dispatch is static-placement-on-Mac (simulation), static-placement-on-device (Phase 1A), or adaptive-on-device (Phase 1A with Reflex Scheduler). Fork the golden-fixture pattern from Energy's Wave 4.
- **Synbio's SBOL3-attested audit-trail + sha256 hash chain** translates as ONNX/TFLite-attested checkpoint-trail with sha256 hash chain. Fork the audit-log discipline from Synbio's PRD framework.
- **All four prior workstreams' falsifier-registry-first pattern** (write the registry + audit-log shape + back-edge router *first*, then plug adapters into it) is the architectural discipline Polymath should adopt. Fork the test-pattern depth (768 tests in Health; 3,535 in Materials) as the bar.

These are forks. Polymath carries its own copy. Runtime co-dependency is not introduced.

## What the orchestrator should pressure-test before locking the PRD

Same shape as Materials, Energy, and Synbio — pressure-test points, not pre-baked answers:

- **Is the active-inference reframe the right architectural primitive for Polymath?** The synthesis argues yes (it subsumes the heterogeneous-dispatch, adaptive scheduling, validation-curriculum, and falsifier-registry concerns under one frame). The orchestrator may have a stronger frame.
- **Should the Reflex Scheduler be Phase 1 or Phase 2?** The synthesis argues Phase 1 (best-in-class mandate); the blueprint argues Phase 2 (measure first). The orchestrator commits.
- **Should distillation from a 72B teacher run as a parallel arm to ELO-only?** The synthesis argues yes (often beats direct CPT for sub-2B students; small Runpod cost). The blueprint does not consider this.
- **Should federated multi-device training be scoped for Phase 2?** The synthesis argues yes (overdesigned best-in-class territory; small marginal cost). The blueprint does not consider this.
- **Should the cross-device validation matrix include a non-cooled SD8E reference phone?** The synthesis argues yes (portability is a real concern for any work that wants to publish or distribute beyond the operator's own phone). The blueprint targets RedMagic only.
- **What is the corpus design specification?** The blueprint leaves this open; the synthesis argues it must be a first-class PRD component (domain list, language list, scale, sources, OCR provenance, license decomposition, ethical-sourcing audit).
- **Is the multi-domain dimension treated equally with the multi-lingual dimension?** The synthesis argues yes (the Polymath framing requires it; the moat is the cross-domain knowledge construction). The blueprint emphasises multilingual.
- **What is the energy-budget operational regime?** The synthesis argues plug-in-only with charging-thermal-regime measured by Experiment 0; possibly external-power-bank-bypass-charging if RedMagic supports it. The blueprint mentions battery as a concern but not as a constraint.
- **What is the cross-machine artifact-exfiltration plan from phone → GitHub + HF?** The synthesis argues this must be specified per artifact class. The blueprint does not specify.

These are pressure-test points. Take them or override them with reasoning.

## What the synthesis agent recommends and the operator should weigh in on

Three points warrant operator engagement before the orchestrator locks the PRD:

1. **The corpus design (domain list, language list, scale, sources, license decomposition).** The synthesis cannot resolve this without operator input — what is the Polymath corpus actually composed of? The blueprint Phase 3 mentions music technology / audio; the operator's broader interests likely span more.
2. **The non-cooled SD8E reference phone for cross-device validation.** Does the operator have access to one, or should this be Phase 2?
3. **The federated multi-device fleet.** Does the operator have multiple SD8E phones, or is this Phase-2-research-only?

All other open questions are within the orchestrator's delegated authority per the operator's 2026-05-01 refinement ("Operator delegates engineering / science / commercial decisions to synthesis and orchestrator agents").

## Provenance

- Synthesis agent: Claude Opus 4.7 (1M context).
- Source: `source-briefs/01-on-device-training-blueprint.md` (operator-authored Pre-PRD Research Synthesis / Blueprint / Engineering Specification, 804 lines, ~52 KB, 2026-05-01). Reference reading of sibling repos `Zer0pa/Health`, `Zer0pa/Materials`, `Zer0pa/Energy`, and `Zer0pa/Synthetic-Biology` permitted at the orchestrator level for cross-workstream pattern observation only (read for fork-and-own; no runtime co-dependency).
- Date: 2026-05-01.
- Operator refinements (binding for all workstreams) as captured in `MODUS-OPERANDI.md` § Operator refinements 2026-05-01.
- Next role: polymath orchestrator (writes `PRD.md`).
