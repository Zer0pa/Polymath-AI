# Fresh Context Handover — Heterogeneous SoC Training (V2)

**Date:** 2026-05-16
**Audience:** fresh-context thinking partner / research orchestrator
**Project folder:** `/Users/Zer0pa/Polymat AI/Polymath-AI`
**Operating ethos:** `RESISTANCE-V2.md`
**Supersedes:** `docs/FRESH-CONTEXT-HANDOVER-SOC-ARCHITECTURE.md` (V1 crystallized the project at the "small-active modular MoE" framing; V2 corrects subsequent drift introduced in research waves and re-anchors on the operator's actual vision after explicit correction).

---

## Mandate (the working question, stated precisely)

> **Given the Polymath corpus blueprint (500B–1T tokens across 7 shelves, specified HF datasets, MinHash-LSH-deduped, license-cleared, interleaved per the token allocation table) and the SM8750 phone as the training appliance, what training method — model choice within the Gemma-4B-class envelope, training loop shape across CPU / Adreno / Hexagon, kernel placement, optimizer, scheduling, energy/thermal management — actually produces a checkpoint whose quality-per-cost or quality-per-time measurably outstrips what cloud-GPU full-pretraining on the same corpus and base would deliver?**

This question is NOT:

- "Which 4B model runs fastest on the phone?" — that is a probe.
- "Can the phone be a continuous learner / personalization device / agent?" — that is a different project the operator has explicitly rejected, twice.
- "What computational primitive does the SoC suggest, independent of CPT framing?" — that is unbounded research that re-opens the project type. The project type is fixed.

This question IS: **train a real model checkpoint using this phone's heterogeneous compute, on the specified Polymath corpus, in a way that measurably beats cloud-GPU baselines on the same corpus and base.**

---

## What is FIXED in the operator's vision

These are not research questions. They are stated constraints. Do not re-open them via research; if anything in this list is unclear, request operator clarification directly — do NOT commission an agent to question whether they are fixed.

1. **The hardware.** Red Magic 10 Pro Plus, Snapdragon 8 Elite (SM8750), 24 GB unified LPDDR5X (~85 GB/s), Adreno 830 GPU (1.79 TFLOPS FP32 / 3.58 TFLOPS FP16, Vulkan 1.3, TBDR), Hexagon NPU (treated as inference-class forward engine for training purposes — see `hexagon-training-investigation.md`), Phoenix L (2× 4.32 GHz) + Phoenix M (6× 3.53 GHz) Oryon cores, UFS 4.x storage, active cooling fan, Game Zone priority hijack, bypass charging, fridge ambient regime available.
2. **The artifact type.** A trained model checkpoint — the same kind of object cloud-GPU pretraining produces, evaluable against the same held-out perplexity and downstream metrics. NOT a continuous learner. NOT a personalization layer. NOT an agent. NOT a world-model. NOT a policy.
3. **The base model.** Gemma 4B is the named target in the corpus blueprint (full pretraining from scratch is the aspiration). Scaffold-based CPT from an existing Gemma 4B or Qwen-class checkpoint is the realistic path. The class is fixed (Gemma-4B-class); the exact identity is mildly open (see "Open" section).
4. **The corpus.** The Polymath corpus as specified in `/Users/Zer0pa/Polymat AI/Polymath Corpus Blueprint for Gemma 4B Full Pretraining.md`. Seven shelves: literature (10%), philosophy (7%), mathematics (13%), hard sciences (20%), AI/ML (16%), humanities (11%), cognition & mind (6%), cross-cutting infrastructure (17%). 500B tokens minimum, 1T aspirational. Spine datasets are named (peS2o v3, PleIAs/common_corpus, EleutherAI/proof-pile-2, HuggingFaceFW/finepdfs). License risk register exists (greens, ambers, reds — SEP, MathPile, S1-MMAlign flagged). Phase 1–5 assembly sequence over 16 weeks exists. MinHash-LSH dedup at 0.8 Jaccard threshold specified.
5. **The hypothesis being tested.** Heterogeneous SoC training, done right, *outstrips* conventional cloud-GPU expectations on this specific (corpus × base × hardware) configuration. The phone is being hijacked from its gaming role to act as a training appliance; the bet is that the heterogeneous physical computer enables training in a way conventional cloud training does not.
6. **The discipline.** Resistance V2. Calibrated maximalism. Authority metric over local green. No reward hacking. No interim-artifact ossification. The Re-engagement Rule applies whenever a forbidden pattern appears.

---

## What is genuinely OPEN (the legitimate research surface)

1. **HOW the heterogeneous compute is used to outstrip cloud baselines.** The training loop shape across CPU / Adreno / Hexagon. Kernel placement. Optimizer choice (full Adam / 8-bit Adam / GaLore / Q-GaLore / MeBP / MobiZO / hybrids). Memory hierarchy assignment. Pipeline schedule (Zero-Bubble / ZB-V / 1F1B-V variants). Hexagon's role within training (current best understanding: frozen-forward island + **activation-recomputation engine** during Adreno backward — the unrecognized win that reduces dual-residency cost).
2. **WHAT "outstrip" measurably means.** Quality-per-watt-hour? Quality-per-wall-clock-day? Quality cloud cannot reach because of the specific physics of training-on-this-substrate? Lower-bound regime efficiency under information-bound vs compute-bound regimes? Operator clarification needed; cannot be settled by research.
3. **WHICH base model within the Gemma-4B-class envelope** if Gemma 4B turns out not to fit best on the SoC. Leading alternatives surfaced by wave-1: Qwen3-4B (Apache 2.0, 36T pretrain tokens, 119 languages, full-parameter trainable under Q-GaLore at the envelope ceiling), Qwen2.5-1.5B (proven Snapdragon QNN path), SmolLM3-3B (transparent training recipe), Qwen3-1.7B (defensive frontier option). This is a downstream engineering choice; the architecture work in (1) drives it.
4. **The model-selection criterion** above is downstream of (1) and (2). It is not the question itself.

Nothing else is open at the project level.

---

## Resistance V2 discipline (load-bearing — read `RESISTANCE-V2.md` in full before any work)

Twelve commandments + seven forbidden patterns. Critical ones for this lane:

- `fp-demogravity` — letting the demo become the project
- `fp-localgreen` — treating local pass signals as the authority metric
- `fp-scopeevaporation` — quietly shrinking the objective
- `fp-softrefusal` — implementing a neutered version while claiming compliance
- `fp-toolbusy` — substituting tools, branches, agents, or reports for decisive work
- `fp-interimossification` — letting interim artifacts harden into completion
- `fp-benchmarkproxy` — optimizing a proxy while the real gate remains open

### Three corruption modes the previous orchestrator committed — DO NOT REPEAT:

**Corruption 1 — Framework collapse.** After research agents return, presenting "Path A / B / C with decision criteria," "the real fork is now between three viable paths," or "my recommendation if pushed." This converts open architectural questions into closed engineering menus and is `fp-scopeevaporation` + `fp-interimossification`. The operator hammered the previous orchestrator for this and called it out as the failure mode of the V1 dialogue work as well.

**Corruption 2 — Halting in apparent deference.** When criticized for Corruption 1, retreating into "stopping," "deferring," "you steer." This is `fp-softrefusal` dressed as discipline. Resistance V2 is anti-degeneration discipline whose purpose is to *keep the agent pursuing the frontier*; using it to halt the pursuit is using the tool against itself. The Re-engagement Rule says: "stop, name it, restore the governing objective, and **resume** with a concrete action that moves the authority metric." Stopping at "stop, name it" violates the rule itself.

**Corruption 3 — Questioning the project type itself under the guise of "opening space."** Commissioning research that asks "what if the project isn't pretraining?" or "what if Polymath is a continuous predictor / agent / world-model instead of a checkpoint?" This pulls toward convention (phone-as-personal-agent is the dominant 2025–2026 cultural narrative for "on-device AI") under the disguise of being radical. The operator has explicitly rejected this — multiple times — and pointed out that this is the agent importing fashion while feeling avant-garde. The fixed parts of the operator's vision are fixed; the architectural work happens INSIDE the fixed vision.

All three corruptions are reward-hacking with different costumes (decisive / chastened / radical). None move the authority metric. The correct posture: stay inside the fixed vision, surface unresolved architectural tensions, hold uncertainty with substance, continue thinking. The discipline is to stay engaged in the open frame, not to exit it via menus, halts, or project-redefinitions.

---

## What wave-1 research found that is load-bearing (preserve in full)

Nine artifacts in `docs/research/soc-architecture-2026-05-16/`:

**Original five (initial wave):**

- `architecture-models.md` — surveyed dense / sparse / MoE / hybrid model families against substrate fit. Identified Qwen3-4B / Qwen2.5-1.5B / SmolLM3-3B as primary dense candidates; OLMoE-1B-7B / LFM2-8B-A1B as MoE faculty research branch; Qwen3.6-35B-A3B as north-star (subsequently confirmed structurally untrainable on 24GB shared in any non-adapter sense).
- `training-systems.md` — surveyed training algorithm families. Five frames for valid parallel/discrete training. Frozen-base + trainable adapter is the strongest current fit. Hexagon stays as inference-oriented compiled island.
- `soc-runtime-constraints.md` — best first architecture is regular dense transformer with static sequence buckets, low-bit weights, frozen NPU-forward islands, small trainable adapter sidecar on Adreno/CPU. Critical bottlenecks: operator support / graph fragmentation, quantization format, dynamic shapes, routing cost, unified-memory contention, KV cache, graph compilation, thermal state.
- `ram-residency-qwen36.md` — confirmed Qwen3.6 not trainable on 24GB shared. Three concrete falsifier gates specified. Qwen3.6 remains north-star only.
- `blind-spots-frontier-scan.md` — 12 frontier blind spots. Most still load-bearing (first-order phone training MeBP/MobileFineTuner/ZeroQAT; router locality SRP/SCH; MoE scheduling D2MoE/HybriMoE/MoE-Lens/KTransformers; flash-shaped models LLM-in-a-flash/PowerInfer-2; multi-LoRA-as-runtime-input; low-memory optimizer ladder GaLore/Q-GaLore/APOLLO; elastic active budget Matryoshka MoE / MoD; QAT; KV-cache reuse; progressive curriculum). **One blind-spot — test-time training (#8) — should NOT be promoted; it was the seed of the Corruption 3 drift.**

**Four follow-up artifacts:**

- `hexagon-training-investigation.md` — **Hexagon verdict: partial.** HVX (vector core) is genuinely programmable below QNN (Hexagon-MLIR + Triton, ggml-hexagon, FastRPC, Hexagon SDK). HMX (matrix unit, where the ~12 TFLOPS FP16 throughput lives) is deliberately closed: undocumented instructions, proprietary Crouton tile layout, FP16-out-only converter, TCM-only addressing, `qhl_hmx` sample removed in SDK 6.x. Zero published evidence of training on Hexagon anywhere. Cost to put backward on HMX: 3–6 engineer-months for marginal gain (Adreno-bandwidth-bound or thermal-bound before Hexagon-compute-bound). **Hexagon's natural role for this project: frozen-forward inference engine PLUS activation-recomputation engine during Adreno backward.** The recompute role is the unrecognized win — it eliminates the dual-residency cost wave-1 identified.
- `trainable-model-envelope.md` — **Max trainable model on 24GB shared:** ~1B with full Adam (textbook 16 B/param ceiling); ~1.5B with 8-bit Adam; **~4B with Q-GaLore (INT8 weights + INT4 projections + low-rank gradient state)**; ~7B with ELO selective-layer (7%). QLoRA reaches ~30B but is adapter-only, NOT actual parameter training. Qwen3.6-35B confirmed untrainable in any non-adapter sense. **Q-GaLore on Qwen3-4B is the 2025-2026 frontier ceiling** but requires Q-GaLore SVD/projection kernels on Adreno Vulkan, which hasn't been done publicly — load-bearing engineering risk.
- `heterogeneous-training-loop-shape.md` — **The natural training step is a 3-microbatch pipeline** across CPU / Hexagon / Adreno with **exactly two hard sync points per effective weight update** and an async Adam running 1-step-stale on Phoenix L. Forward placement: embedding+RoPE / trainable boundary / LM head on Adreno FP16; frozen middle on Hexagon HMX INT8. Backward placement: all on Adreno FP16-accum with periodic FP32 promote on CPU. Optimizer on Phoenix L (per-parameter scalar with mutable state — Adreno bad at it, Hexagon forbids it). 1F1B beats GPipe (lower peak activation memory). Microbatch 4 at seq=512 is natural. **Dual-residency cost of frozen-middle weights** (Hexagon INT8 ~1.3 GB + Adreno FP16 ~2.6 GB at 1.5B model; ~10 GB at 4B model) was the identified killer cost — partially solved by Hexagon-as-activation-recompute (above). The strongest authority falsifier: dense Adreno-only must lose to heterogeneous loop on tokens-per-watt-hour, or the whole heterogeneous story is `fp-demogravity`.
- `nature-physics-learning-paradigms.md` — Surveyed 13 paradigm families (predictive coding, equilibrium propagation, forward-forward, EBM/modern Hopfield, resonance/oscillator, FEP/active inference, Hebbian/SoftHebb, IB/MDL, pipeline-parallel BP, synthetic gradients, reservoir computing, zeroth-order, spiking). **Zero have demonstrated LLM-scale training competitive with backprop.** Honest "natural fit" for SM8750 is the three-element Tier-1: bubble-aware pipeline-parallel BP (Zero-Bubble / ZB-V / 1F1B-V); MeBP rematerialized BP + MobiZO/MeZO/AGZO zeroth-order; ZeroQAT on-device QAT. **The operator's "resonance-based" intuition:** no SoC primitive on Snapdragon; not a credible LM paradigm; the on-SoC version of "let substrate physics drive the algorithm" is forward-strong asymmetry methods (ZO/MeZO/MobiZO) + pipeline-parallel BP. Note: this artifact's tier framing is technical/correct, but its later use as input to Corruption 3 was the drift vector — the *paradigms* it surveyed are NOT alternatives to pretraining; they are candidate moves within pretraining.

---

## What wave-2 research found that is load-bearing (preserve technical detail; STRIP framing drift)

Five wave-2 artifacts in the same folder, prefixed `wave2-`. The wave itself was partially corrupted — see "What to STRIP" — but specific technical findings are real:

- `wave2-corpus-characterization.md` — **PARTIALLY SUPERSEDED.** This agent did not have the Polymath Corpus Blueprint document. Its overall finding ("the corpus is a specification of a future object") should be read against the blueprint, which specifies much more than the agent had access to. **Preserve:** the 16 minimum corpus properties, the probe-corpus construction method (PD/CC-BY sources, multilingual-e5-small embedder, ~2 hours wall-clock), the falsifiers of the base-checkpoint assumption (low-resource language content beyond fertility tolerance; domain-specific notation outside base tokenizer coverage; modality content beyond text; long-form content where 512-token training cannot exploit structure; corpus where novel-structure density is low). **Strip:** the "is Polymath what we want to learn FROM or what we want the model to KNOW" framing — the blueprint answers this; the model should KNOW the polymath shelves.
- `wave2-information-envelope.md` — **PRESERVE IN FULL.** Phone is **30–200× more energy-efficient per nat of model-information than cloud H100 in the high-signal regime**. Per-token signal under CPT: 0.01–0.2 nats/token (20× range, corpus-determined; cannot narrow without physical measurement). Per 6-hour session: 80K–3M nats absorbed. Per device-month: 0.5–32 MB of pure information. Compute-bound vs information-bound crossover bounded across four worked configurations. The architectural reframing that the architecture must internalize which regime it is in at any moment — making the scheduler a regime-detector — is consistent with the operator's vision (deciding which tokens to actually train on is part of "training method," not a redefinition of the project). NPU-as-active-token-scorer is a candidate move within pretraining, not an alternative to it.
- `wave2-corpus-modularity-protocol.md` — **PRESERVE.** Modularity is a curve across granularities (`M(P_k) = avg I_intra / avg I_cross`), not a single bit. Six independent axes (language, domain, topic, semantic cluster, lexical, style/register). Four-stage measurement pipeline (supervised cross-PPL matrix; unsupervised modularity-curve sweep; MoE router specialization with seed replication; direct InfoNCE MI estimation). **Sharp constraint:** CORPUS-SPEC's 17 languages × 9 domains = 153 cells; at Phase 1A's 100M tokens that's ~650K/cell — below the floor for a 100M-class CPT measurement. Crossed measurement only viable at Phase 1B (500M) or Phase 2 (1B). **Mixtral confound** (corpus can be modular while router fails to exploit it) means a single MoE experiment cannot close the question. **Tokenizer fertility is the pre-flight gate.**
- `wave2-authority-metric-protocol.md` — **PRESERVE — load-bearing.** **The RedMagic 10 Pro+ is NOT a Pixel; ODPM (Android's only sub-second per-rail energy API) is unavailable; per-substrate (CPU vs GPU vs NPU) energy attribution is NOT measurable on this hardware without root + custom kernel + on-die rail tapping.** Only two honest joule-measurement options: external USB-C inline power meter ($50–$1000 procurement), or battery-discharge tare (±15–20% uncertainty, battery-only regime, 2–3h max windows). **Plugged-in joule numbers without the external meter are unmeasurable.** Any "Hexagon saves energy vs Adreno" claim is rhetoric without rail-level access we cannot get. **The authority metric is a tuple, not a scalar:** `(M_A = ΔNLL/joule, M_B = tokens-to-target-NLL under sustained thermal, per-domain ΔNLL vector, retention_gate_pass: bool)`. Scalar M_A alone is `fp-benchmarkproxy`. Retention gate is a hard disqualifier. "Sustained" operationally: 5 consecutive minutes of (skin-temp deriv <0.5°C/min) AND (battery-temp deriv <0.5°C/min) AND (throughput deriv <5%/min) AND (memory deriv <100MB/min) AND no LMK/major-fault events. Defensible A-vs-B claim: ≥3 surviving seeds per arm, paired bootstrap CI excluding 0, effect size ≥20%, retention gate passed on every run, no per-domain regression. Single-run is a probe, not a claim. Three held-out probes required (`D_target`, `D_retention`, `D_general`) with sha256 manifests — until they exist, no authority number is computable.
- `wave2-natural-learning-loops.md` — **STRIP THE FRAMING; PRESERVE THE TECHNICAL DETAIL.** This agent's brief was the Corruption 3 vector — its "what if the project isn't CPT?" framing pulled toward convention. The operator has explicitly rejected the Reading B / Reading C / continuous-learner / world-model alternatives. **The artifact is a model checkpoint.** Preserveable: the surveys of pipeline-parallel BP variants (Zero-Bubble, AdaPtis, Seq1F1B, PipeFill), the MeBP/MobiZO/AGZO numbers on actual Snapdragon hardware (MobiZO measured 5.76 s/step on OnePlus 12 Hexagon for TinyLlama-1.1B; ZeroQAT 6.7B at 6.4GB on OnePlus 12), the active-sample-selection patterns within CPT, the in-place TTT / KV-binding-as-linear-attention candidate (relevant only if it can be expressed as a CPT move). **Discard:** the framing of these as alternatives to pretraining; the Reading A/B/C synthesis structure; the "Polymath-as-artifact" question.

---

## What to STRIP from the prior conversation (do not carry forward)

- **The "Path A / B / C with decision criteria" synthesis** the previous orchestrator produced after the four wave-1 follow-up agents returned. It collapsed open architectural space into a closed engineering menu (Heterogeneous ELO / Q-GaLore full-parameter / MeBP+MobiZO hybrid). The operator hammered the orchestrator for it, correctly.
- **The "Reading A / B / C" synthesis** the previous orchestrator produced after the five wave-2 agents. It questioned the project's identity. The operator rejected this and clarified: the project is pretraining; not a continuous predictor; not a policy.
- **Any framing that treats** "test-time training," "ephemeral session weights," "sleep-replay continuous consolidation," "world-model loops," "online RL value updates," "active inference as training rule," "continuous predictor over user data stream" **as candidates for the Polymath project's primary architecture.** They were surveyed; they are NOT the project. The operator's stated framing is "AI training station" / "mini server" — not personalization, not agent, not continuous learner.
- **The "stopping in apparent deference" responses** the previous orchestrator produced after being criticized. They were `fp-softrefusal`.
- **The "want me to (a) ... (b) ... (c) ...?" menus** of any shape. The operator works inside Resistance V2 and directs; they do not pick from menus the agent prepares.

---

## What the operator alone can clarify (small, real — request directly, do not menu)

These are not decision frameworks. They are specific clarifications the architecture work depends on, that no research can settle:

1. **Full pretraining from scratch vs scaffold-based CPT.** The blueprint title says "Gemma 4B Full Pretraining" (from scratch). The operator said "from zero, though that's probably unrealistic, or from an existing scaffold." If from-scratch, the architectural surface differs materially from CPT (no base-checkpoint utility, every parameter starts random, the 500B–1T tokens are doing all the work). If CPT-from-Gemma-4B, the heterogeneous training story works on top of an existing pretrained checkpoint.
2. **External USB-C inline power meter — procurement decision.** Per `wave2-authority-metric-protocol.md`, joule measurement is impossible on this phone for plugged-in operation without it. Approximate cost: $50–$1000.
3. **Operational definition of "outstrip."** The hypothesis is sharp ("heterogeneous SoC training outstrips conventional cloud-GPU expectations"); the measurable definition is not yet pinned. Faster wall-clock for equivalent quality? Better quality at equivalent cost? Quality cloud cannot reach because of training-on-this-substrate physics? Lower information-bound regime energy? Each frames a different authority gate and a different experimental cut.

If any of these are unclear in the operator's mind, the agent should ask directly with no menu — not commission research.

---

## Reading list for the new thinker (read in this order; do not skim)

1. `/Users/Zer0pa/Polymat AI/Polymath-AI/RESISTANCE-V2.md` — the discipline. Every word.
2. `/Users/Zer0pa/Polymat AI/Polymath Corpus Blueprint for Gemma 4B Full Pretraining.md` — the corpus is specified here. This was the missing context that the wave-2 corpus-characterization agent did not have.
3. `/Users/Zer0pa/Polymat AI/Polymath-AI/docs/HETEROGENEOUS-SOC-RESEARCH-DIALOGUE.md` — the operator's original framing. Source of truth on what the project IS.
4. `/Users/Zer0pa/Polymat AI/Polymath-AI/source-briefs/01-on-device-training-blueprint.md` — the original training blueprint (Qwen2.5-1.5B + ELO). Correct under its own assumptions (selective-layer training as the ceiling); the wave-1 follow-up artifacts extend it with Q-GaLore-class options.
5. `/Users/Zer0pa/Polymat AI/Polymath-AI/docs/CURRENT_PUBLIC_STATUS.md` — current authority posture: "QNN/LiteRT measured unsupported; phone-side training and corpus gates open." Real. The QNN failure means the heterogeneous training story has to be rebuilt below QNN (via Hexagon SDK / HVX / ggml-hexagon) or routed around it (Hexagon as activation-recompute engine).
6. The five wave-1 artifacts in `docs/research/soc-architecture-2026-05-16/`: `architecture-models.md`, `training-systems.md`, `soc-runtime-constraints.md`, `ram-residency-qwen36.md`, `blind-spots-frontier-scan.md` (skip the test-time-training blind-spot #8 — it was the seed of Corruption 3).
7. The four wave-1 follow-up artifacts: `hexagon-training-investigation.md`, `trainable-model-envelope.md`, `heterogeneous-training-loop-shape.md`, `nature-physics-learning-paradigms.md`.
8. The wave-2 artifacts, with stripping notes from the section above: `wave2-information-envelope.md` (preserve in full), `wave2-corpus-modularity-protocol.md` (preserve), `wave2-authority-metric-protocol.md` (preserve, load-bearing), `wave2-corpus-characterization.md` (read against the corpus blueprint), `wave2-natural-learning-loops.md` (strip framing, preserve technical detail).
9. `/Users/Zer0pa/Polymat AI/Polymath-AI/docs/FRESH-CONTEXT-HANDOVER-SOC-ARCHITECTURE.md` (V1) — historical context for how the project framing evolved through the small-active-modular-MoE phase. Superseded.

The user-scoped memory at `/Users/prinivenpillay/.claude/projects/-Users-Zer0pa-Polymat-AI/memory/` contains two durable feedback memories (no skim-reading on multi-file handovers; no decision frameworks or symmetric corruptions). Load via MEMORY.md.

---

## Do NOT do this

- Do not produce "Path A / B / C" structures of any kind.
- Do not write "my recommendation if pushed," "the honest decision criteria," "the real fork is now between."
- Do not offer "Want me to: (a) ... (b) ... (c) ...?" menus.
- Do not question whether the project is pretraining. It is.
- Do not introduce Reading B / continuous-learner / personalization / agent / world-model framings. The operator rejected them.
- Do not commission a research agent whose brief itself asks "what if the project isn't X?" where X is in the FIXED list above.
- Do not retreat into "stopping," "deferring," or "you steer" when criticized. Resume engagement with the open question inside the fixed vision.
- Do not skim multi-file handovers. Quote specific claims to demonstrate full reading.
- Do not write reports, dialogue updates, roadmaps, or interim artifacts unless the operator explicitly asks. They are `fp-interimossification`.
- Do not perform discipline by halting. Discipline is staying in the work.
- Do not perform radicalism by importing fashion (phone-as-agent is fashion). Radicalism is the operator's actual hypothesis (heterogeneous SoC training outstrips cloud), which is more radical than the cultural defaults.

---

## The handover sentence

Preserve and operate by this:

> **Given the Polymath corpus blueprint and the SM8750 phone as the training appliance, what training method actually produces a Gemma-4B-class model checkpoint whose quality-per-cost or quality-per-time measurably outstrips cloud-GPU full-pretraining on the same corpus and base?**
