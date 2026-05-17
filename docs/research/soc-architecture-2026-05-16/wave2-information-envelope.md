# Wave-2 Information Envelope: Is The Phone Compute-Bound Or Information-Bound?

**Date:** 2026-05-16
**Wave:** 2 (post wave-1 memory-budget analysis)
**Scope:** Bound the question of how much *model information* a RedMagic-class SM8750 phone can absorb from the Polymath corpus per training session, per device-day, and per device-month — and identify the conditions under which the bottleneck stops being compute and starts being signal.
**Authority gate (Resistance V2):** This artifact is an *input to architectural reasoning*, not an architectural decision. Forbidden patterns explicitly avoided: `fp-scopeevaporation` (do not collapse to "scaling laws say X parameters"), `fp-interimossification` (bounds are not commitments), `fp-benchmarkproxy` (information-gain is itself a proxy until anchored to held-out task improvement).

**Critical reading note:** every numerical range in this document is a *bound*, not a *prediction*. Where bounds span an order of magnitude, the right move is to name the conditions that select between regions of the range, not to halve the range with false precision. The user is technical and will rightly reject misleading specificity.

---

## 0. The Question, Restated

> Given the Polymath corpus and the SM8750 phone's realistic compute/thermal envelope, what is the information-theoretic upper bound and the empirically achievable bound on model-information per training token, per 6-hour session, per device-day, per device-month? At what point does the phone become information-bound rather than compute-bound — and how does that constraint reshape what architectural choices are even worth comparing?

This question is upstream of the architectural question wave-1 answered. Wave-1 (`trainable-model-envelope.md`) established: under 2025-2026 memory-efficient training, the phone can hold and update parameters of a ~4B dense model (Q-GaLore) or run smaller models at full Adam. That is the *capacity* envelope. This wave bounds the *signal* envelope: even with capacity, how much novel statistical structure can the phone actually capture per unit time, per unit corpus, per joule?

The two envelopes interact. A capacity envelope without a signal envelope is `fp-demogravity` — it tells you what fits, not what learns. A signal envelope without a capacity envelope is academic — it tells you what is theoretically extractable, not what your machine can extract.

The framing motive: if the phone is information-bound over realistic session lengths, then optimizing tokens-per-hour is misdirected. Tokens-per-hour is a compute metric; information-per-token is the actual scarce resource. None of the wave-1 agents engaged with this.

---

## 1. Scaling-Law Context And What The Literature Implies For Phone-Scale Training

### 1.1 Three scaling-law positions that frame the bound

**Kaplan et al. 2020** (arXiv:2001.08361) — pre-Chinchilla scaling laws. Loss is a power-law in compute, parameters, and dataset size. The original claim: bigger models are dominant; data scales sub-linearly. Wrong in detail (overspent compute on parameters), correct in framing (loss is a smooth function of resources, not a phase transition).

**Hoffmann et al. 2022** (arXiv:2203.15556, "Chinchilla") — compute-optimal training. For a fixed FLOP budget, optimal allocation puts ~20 training tokens per parameter. A 1B model wants ~20B tokens; a 3B model wants ~60B; a 4B model wants ~80B. Below this ratio, the model is *under-trained* (more data would improve loss for the same parameter count). Above it, *over-trained* (more parameters would have been a better use of compute).

**Sardana et al. 2024** (arXiv:2401.00448, "Beyond Chinchilla-Optimal") — over-training is justified when inference cost matters. Production models routinely train at 200-2000+ tokens/parameter because the inference savings dominate the additional training cost. LLaMA-3-8B was trained on ~15T tokens (~1875 tokens/param). This is the regime modern open models actually live in.

### 1.2 What this implies for the phone-scale regime

The Polymath phone scenario is *continued pretraining* (CPT), not pretraining from scratch. The base models being considered (Qwen3-4B, Qwen2.5-1.5B, SmolLM3-3B) are all *over-trained* per Sardana's frame — they have already absorbed 18T-36T tokens. They are deep into diminishing-returns territory for the kinds of general signal that scaling laws describe.

CPT operates in a different regime entirely. Scaling laws describe loss reduction *from scratch* on a generic corpus. CPT moves a model that has already converged on Internet-text statistics toward a *new* distribution. The relevant question is not "where on the Chinchilla curve are we" but "how much KL divergence is there between the base model's induced distribution and the Polymath corpus's true distribution, and how many tokens does it take to close it?"

For phone-scale session counts (15M-90M tokens per 6-hour-to-day session), let us be concrete about position on the curves:

| Model | Chinchilla-optimal training | Already-trained (pretrain) | One phone session (15M tokens) | Phone session as fraction of pretrain |
|---|---:|---:|---:|---:|
| Qwen2.5-1.5B | ~30B tokens | ~18T tokens | 15M | 8e-7 |
| SmolLM3-3B | ~60B tokens | ~11T tokens | 15M | 1.4e-6 |
| Qwen3-4B | ~80B tokens | ~36T tokens | 15M | 4e-7 |

A single 6-hour phone session is between 4e-7 and 1.4e-6 of the model's pretraining budget. **Scaling-law intuitions calibrated against pretraining-from-scratch budgets do not apply meaningfully at this fraction.** The phone is operating in the CPT diminishing-returns tail of an already-over-trained model. The relevant literature is *not* Chinchilla; it is the continued-pretraining and domain-adaptation literature.

### 1.3 What the CPT literature actually shows

The CPT literature is much less clean than Chinchilla. Three patterns recur:

**Pattern 1 — Sub-1B-token CPT can move domain-specific held-out metrics meaningfully.** Gururangan et al. 2020 (DAPT/TAPT) showed that 5-100M tokens of in-domain CPT raise downstream task scores on the target domain by 1-5 absolute points, with the move concentrated in the first few hundred million tokens. Most recent domain-CPT papers (BioMedLM, Code-LLaMA, MathPile-derived models) follow this shape: large early gain, then a long shallow tail.

**Pattern 2 — Domain shift dominates token count.** Cheng et al. 2023 and follow-ups consistently find that the *distributional distance* between the base model's pretraining mixture and the CPT corpus matters more than the token count once both are above ~10M tokens. For a Polymath corpus that is highly curated, structured, and multilingual, the relevant question becomes: how far from the base Qwen3/SmolLM3 mixture is the Polymath distribution? Wave-1's "tokenizer fertility audit" is a partial answer in the tokenization domain; a full answer requires measured held-out NLL on the Polymath corpus under the base model before CPT.

**Pattern 3 — Replay protects but caps gain.** Continual-learning literature (Scialom et al. 2022, Ibrahim et al. 2024) consistently finds that replay (10-30% of CPT tokens drawn from general data) prevents catastrophic forgetting but reduces the per-token signal extracted from the target corpus by the replay fraction. A 15% replay configuration extracts ~85% of the signal-per-token rate of a no-replay configuration. This is a structural cost the phone cannot avoid if general capability is to be preserved.

### 1.4 What this means for the bound

The literature gives us only weak bounds on per-token gain in the phone-CPT regime:

- **Lower bound:** ~0.01 nats/token (1.5% relative perplexity reduction over the 15M-token range) is consistent with "the corpus is close enough to base that CPT mostly memorizes a few facts and adjusts a few weights."
- **Upper bound:** ~0.2 nats/token (sustained for the first few million tokens, decaying after) is consistent with "the corpus contains substantial novel structure the base model never saw."

This 20x range is not a failure of the literature — it is a real feature of the CPT regime. The actual position within the range is *property of the corpus*, not property of the algorithm or the hardware. **Therefore the per-token information gain on the Polymath corpus cannot be predicted from the literature alone. It must be measured.** This is the first thing the on-device-physical wave must measure.

---

## 2. Shannon / MDL View Of The Training Signal

### 2.1 The information-theoretic accounting

Information theory provides a hard upper bound on what *any* learning algorithm can extract from a corpus given a fixed base model.

Define:
- `H_true(C)` — true entropy of the corpus C, in nats/token. This is the entropy of the data-generating distribution.
- `H_base(C)` — cross-entropy of the base model on C, in nats/token. This is the NLL of the base model.
- `H_post(C)` — cross-entropy of the post-CPT model on C.

Then:
- `H_base(C) - H_true(C)` = total compressible structure the base model has missed (Kullback-Leibler divergence from the base model's induced distribution to the true distribution, integrated over the corpus token distribution).
- `H_base(C) - H_post(C)` = information actually absorbed during training, in nats/token.
- `H_post(C) - H_true(C)` = irreducible residual (what no model can do better than).

**The information bound on what CPT can extract per token is `H_base(C) - H_true(C)`.** This is a strict upper bound. No optimizer, no architecture, no curriculum can exceed it because there is no signal beyond it.

### 2.2 Numerical anchors from the literature

The literature provides reasonable ranges for these quantities on general English text:

- **Reference-model entropy estimates:** LLaMA-3-70B achieves perplexity ~3.5-4.0 on diverse English text (Pile, RefinedWeb, etc.) — that is ~1.25-1.40 nats/token cross-entropy. Frontier models (GPT-4, Claude-class) likely approach ~1.0-1.2 nats/token on the same. The true entropy of English is plausibly 0.6-1.0 nats/token (Shannon's original 1951 estimate was 0.6-1.3 bits/character ≈ 1.7-3.6 bits/token at ~5 chars/token, equivalent to ~1.2-2.5 nats/token; modern estimates settle near the lower end).
- **Multilingual penalty:** For non-English text the same model surfaces commonly show 1.5-2x higher cross-entropy due to tokenizer fertility and capacity allocation. For a multilingual Polymath corpus, expect base-model cross-entropy in the 1.5-3.0 nats/token range.
- **Domain-specific text:** Highly specialized text (math derivations, code, certain scholarly genres) can show cross-entropy 2-4x baseline because the base model lacks the relevant local statistics.

For a 4B-class base model (the Qwen3-4B candidate), a reasonable starting estimate is:
- `H_base(Polymath)` ≈ 1.5-2.5 nats/token (broad multilingual scholarly corpus)
- `H_true(Polymath)` ≈ 1.0-1.5 nats/token (best a model of any size could plausibly achieve)
- **Maximum extractable signal per token = `H_base - H_true` ≈ 0.0-1.5 nats/token.**

The wide range reflects real uncertainty. If the Polymath corpus is mostly already-compressed-by-Qwen3 (curated English/multilingual web-class material that overlaps with the 36T-token Qwen3 pretraining mixture), the extractable signal is near the bottom (~0.0-0.3 nats/token). If the Polymath corpus is genuinely novel (specialized scholarly material, low-resource languages, structured knowledge the base model never saw at scale), the extractable signal is near the top (~0.5-1.5 nats/token).

### 2.3 Per-step achievable gain (the practical bound)

The maximum extractable signal is a strict upper bound; the per-training-step achievable gain is bounded much more tightly by optimization dynamics. From the CPT literature:

- **First few million tokens:** achievable gain can briefly approach 0.1-0.3 nats/token if the optimizer warm-up is well-tuned and the corpus is genuinely novel. This is the "easy wins" regime where the model learns global distributional shifts (new vocabulary frequencies, new genre conventions).
- **5M-50M tokens:** typical achievable gain 0.01-0.1 nats/token; the corpus's "easy" structure has been learned and the optimizer is grinding into harder local structure.
- **50M-500M tokens:** typical achievable gain 0.001-0.02 nats/token; deep CPT into the long tail.
- **Above 500M tokens:** typically 1e-4 nats/token or below per token; replay overhead and forgetting risk start to dominate the marginal token's value.

For a 15M-token session (one 6-hour phone day), the integrated information extraction lies in:
- **Low signal regime** (close-to-base corpus, ELO-style selective training, replay-protected): ~150K-1.5M nats per session (10K-100K bits per session equivalent).
- **High signal regime** (genuinely novel corpus, full-parameter Q-GaLore, well-tuned curriculum): ~750K-3M nats per session (100K-400K bits).

This is the *signal envelope per session*. It is a wide range, and it should remain wide until the corpus has been measured under a base model.

### 2.4 What "information into the model" actually means

A subtle but critical point: the "nats absorbed per token" is the held-out NLL improvement. But that is not the same as "bits stored in the model's parameters." Parameter changes during training carry information about both the absorbed signal *and* the noise of the optimizer steps. A model with 4B parameters at FP16 storage has ~64 Gbits of parameter capacity, which dwarfs any plausible per-session signal. The bottleneck is not parameter capacity. It is the signal-to-noise ratio of the gradient updates extracting the signal from individual tokens.

This matters for the architectural implication: parameter-efficient methods (LoRA, Q-GaLore selective rank, ELO) reduce the parameter surface that absorbs the signal, but if the signal-per-token is small, the surface area was never the bottleneck. **You cannot allocate the noise away; you can only collect more signal or extract more from each token.** Architectures that allocate more parameter surface to a corpus that has little signal to give are over-parameterizing the noise, not the signal.

### 2.5 The compressibility frame

Equivalent restatement: the maximum signal CPT can extract is the *additional compression* the post-CPT model achieves over the base model on the corpus. If the base model already compresses the corpus to 1.5 nats/token, and the post-CPT model compresses it to 1.3 nats/token, then 0.2 nats/token times the corpus size is the *total* information transferred from corpus to model. For a 100M-token Polymath corpus, that is 20M nats ≈ 28 Mbits ≈ 3.5 MB of pure information transferred. Even at the favorable end of the CPT signal range, a 1B-token corpus would contribute at most ~1.5 GB of pure information (1B × 1.5 nats/token / 8 / 1e9). The model has the parameter capacity to absorb this many times over. The bottleneck is not capacity; it is the per-token signal extraction rate and the corpus size itself.

---

## 3. Information-Per-Joule And Per-Session Estimates

### 3.1 Energy budget grounding

From wave-1 and the source brief Part VI:

- Realistic sustained throughput (ELO Stage 1, Qwen2.5-1.5B, fan on): 2.0-2.8M tokens/hour. Take **2.5M tokens/hour midpoint**.
- For Q-GaLore on Qwen3-4B, per-step compute is ~3-4x ELO's per-step compute. Sustained throughput drops proportionally: estimate **0.5-1.0M tokens/hour** for full-parameter Q-GaLore on Qwen3-4B (this is itself only an estimate from the per-token FLOP scaling; needs phone measurement).
- Phone TDP under sustained training load: 6-10W with fan, 4-6W passive. Take **8W** as the sustained-with-fan midpoint.
- Session length: 6 hours = 21,600 seconds. Energy per session = 8W × 21,600s = **172,800 J = 48 Wh**.

### 3.2 Tokens-per-session, information-per-session, information-per-joule (ranges)

Computed as ranges over (training method, signal regime) cells. All ranges should be read as "the answer lies somewhere in here; physical measurement narrows it":

| Configuration | Tokens/session | Info/token (nats) | Info/session (nats) | J/session | nats/J | bits/J |
|---|---:|---:|---:|---:|---:|---:|
| ELO Qwen2.5-1.5B, low signal | 15M | 0.01-0.05 | 150K-750K | 173K | 0.9-4.3 | 1.3-6.2 |
| ELO Qwen2.5-1.5B, high signal | 15M | 0.05-0.2 | 750K-3M | 173K | 4.3-17 | 6.2-25 |
| Q-GaLore Qwen3-4B, low signal | 4-6M | 0.02-0.08 | 80K-480K | 173K | 0.5-2.8 | 0.7-4.0 |
| Q-GaLore Qwen3-4B, high signal | 4-6M | 0.08-0.3 | 320K-1.8M | 173K | 1.8-10 | 2.6-15 |

A 6-hour phone session captures somewhere between **80K and 3M nats** of model information, depending on the (method, corpus) cell. This is a 35x range and is correctly wide given current uncertainty.

### 3.3 Per device-day and per device-month

A "device-day" of training is bounded by thermal sustainability and battery/charging cycles. With active cooling, charge bypass, and a fan, sustained training over a full 24-hour day is plausible but requires sustained scheduling discipline. Assume:

- **6-hour day** (single charged session, conservative): 1x session.
- **18-hour day** (sustained with bypass charge, active fan, fridge in worst-case): 3x sessions. Wave-1 thermal sustainability is not yet measured; assume this is the *upper bound* of what is plausible without device damage.
- **Device-month:** 30 device-days at the relevant per-day rate, minus 10-30% for thermal/maintenance/idle. Effective range: 20-25 device-days/month of sustained training.

| Cell | 1-day info | 1-month info | Equivalent stored bits |
|---|---:|---:|---:|
| ELO low-signal, 6h/day | 150-750K nats | 3-22.5M nats | 0.5-3.2 MB |
| ELO high-signal, 6h/day | 0.75-3M nats | 22.5-90M nats | 3.2-13 MB |
| ELO high-signal, 18h/day | 2.25-9M nats | 45-225M nats | 6.5-32 MB |
| Q-GaLore high-signal, 18h/day | 1-5.4M nats | 24-160M nats | 3.5-23 MB |

Reading: **the most optimistic information-yield from a month of sustained phone training is in the tens of megabytes of pure information transferred from corpus to model.** The least optimistic is in the hundreds of kilobytes.

This number is small relative to the model's parameter capacity but is *not* small relative to what is needed to inject substantial new factual/structural knowledge. A 10-100MB-scale CPT can plausibly add domain-specialized vocabulary, restructure attention patterns over a target distribution, and shift the model's prior over a specific topic area — but cannot, in a month, fundamentally restructure a 4B model's worldview. This is consistent with the CPT literature.

### 3.4 Comparison to cloud baseline

For calibration: a single H100 SXM5 at 700W draws ~2.5MJ over a 1-hour run and processes ~1-3M tokens at 4B-class CPT throughput (depending on batch size and context length). At equivalent high-signal NLL improvement (0.1-0.3 nats/token), that is ~200K-900K nats/hour at 2.5MJ/hour, equivalent to ~0.08-0.36 nats/J. The phone, at the high end of its range, achieves ~10-17 nats/J. **The phone is plausibly 30-200x more energy-efficient per nat of model information than a cloud H100 in the high-signal regime.**

The mechanism: the phone amortizes a much smaller machine across the same per-token gradient update, and the gradient update — not the FLOP — is the unit that carries the signal. This is consistent with the broader edge-AI energy-efficiency story (LLM decode on a phone NPU achieves comparable nats/J to LLM decode on a cloud H100; the asymmetry is in throughput, not efficiency).

Caveat: this comparison is *information per joule of total system energy*, not *information per joule of accelerator-only energy*. Including the phone's display, charging losses, idle baseline, and infrastructure overhead, the gap narrows. But the qualitative point holds: phone-scale training is not just feasible energetically — it may be substantially more energy-efficient per unit of model information absorbed.

This recasts the case for on-device training. The compelling argument is not "the phone is convenient" but "the phone is energetically efficient at the actual scarce-resource scale." Cloud training wastes most of its energy on FLOPs that do not carry signal at the CPT margin. The phone wastes much less because it has much less to spend in the first place — every joule must do useful work.

---

## 4. Compute-Bound Vs Information-Bound Crossover

### 4.1 The two regimes, defined operationally

**Compute-bound regime:** More compute on the same token stream produces measurably more held-out NLL improvement. The model has not yet extracted all the available signal per token — additional forward/backward passes, smaller batch sizes (more updates per token), longer training, or higher-rank optimizer state would still pay off.

**Information-bound regime:** More compute on the same token stream produces vanishingly small held-out NLL improvement. The model has substantially compressed the corpus relative to the achievable bound; only *new* tokens (corpus growth, different distribution) or *more signal-per-token* (curriculum, novelty weighting, active filtering) can improve held-out NLL.

### 4.2 The diagnostic test

The operational way to distinguish: hold corpus constant, scale compute (e.g., extra epochs, longer training, higher-rank optimizer). If held-out NLL keeps improving roughly proportionally, you are compute-bound. If it plateaus, you are information-bound on that corpus.

For phone-scale sessions, the crossover depends on the (model size, corpus size, signal-per-token regime) triple. Concrete cases:

### 4.3 Crossover analysis for the candidate configurations

**Case A: Qwen2.5-1.5B + ELO, Polymath corpus = 100M tokens (small corpus, small surface)**
- 100M tokens × 2-3 epochs = 200-300M training tokens budget.
- Phone throughput: 2.5M tokens/hour. Total training time: 80-120 hours = ~14-20 device-days at 6h/day.
- Signal extractable: at 0.02-0.1 nats/token average (decaying through the run) over 200-300M tokens = 4M-30M nats total. With ELO's 7% trainable surface, the per-step compute is light.
- **Verdict:** Almost certainly information-bound by the third epoch on this corpus. Adding compute (extra epochs) plateaus quickly. The bottleneck is corpus signal exhaustion.

**Case B: Qwen3-4B + Q-GaLore, Polymath corpus = 100M tokens (small corpus, large surface)**
- 100M tokens × 1-2 epochs = 100-200M training tokens budget.
- Phone throughput at Q-GaLore: 0.5-1M tokens/hour. Training time: 100-400 hours = ~17-67 device-days at 6h/day.
- Signal extractable: similar 0.02-0.1 nats/token range but with larger trainable surface.
- **Verdict:** Information-bound earlier than Case A in absolute time because Q-GaLore extracts more per token. But the surface is also wider, so it can absorb more before saturating. Likely information-bound after 1.5-2 epochs. Most of the value lies in the first 30-50M tokens. After that, the phone is spending compute to chase increasingly small signal.

**Case C: Qwen3-4B + Q-GaLore, Polymath corpus = 1B tokens (large corpus, large surface)**
- 1B tokens × 1 epoch.
- Training time at 0.5-1M tokens/hour: 1000-2000 hours = ~5-11 device-months at 6h/day.
- **Verdict:** Compute-bound for the *entire* duration the phone can practically train. The corpus has more signal than the phone can extract in any realistic schedule. The bottleneck is compute throughput. *In this regime, optimizing tokens-per-hour is correct.*

**Case D: Qwen2.5-1.5B + ELO, Polymath corpus = 1B tokens (large corpus, small surface)**
- Training time at 2.5M tokens/hour: 400 hours = ~67 device-days = ~3 device-months at 6h/day.
- ELO's 7% surface has limited information capacity; the model saturates the surface's representation power well before exhausting the corpus signal.
- **Verdict:** Mixed. The phone is compute-bound on traversing the corpus once but representation-bound (a sub-form of information-bound at the parameter-surface level) on how much that traversal can be compressed into 7% of 1.5B parameters. **Adding compute does not help; widening the trainable surface (going to Q-GaLore full-parameter) does help.**

### 4.4 The crossover formula (heuristic)

Let `S` = corpus size in tokens, `r` = effective extraction rate in nats/token averaged over the run (decreases with cumulative tokens), `T_phone` = annual tokens the phone can process at the given method (~5-20B/year sustained). The phone is information-bound when:

```
S * average_r << T_phone * marginal_r
```

That is, the corpus is small enough that even the small marginal information gain on the last passes saturates the available compute. For a 100M-token corpus, even at low extraction rates, the phone can re-pass it ~100x in a year — far past the information bound. For a 1B-token corpus the phone can re-pass it ~10x in a year — still past the information bound for most CPT regimes. For a 10B-token corpus the phone is just at one full pass in a year — straddling the bound. For 100B+ tokens the phone is firmly compute-bound.

**The crossover for the Polymath corpus depends entirely on its actual size.** Wave-1 and the blueprint estimate "100M-1B tokens of meaningful curated content." That means the phone is almost certainly information-bound for the smaller end of that range and compute-bound only on the upper end. The actual corpus size measurement is therefore a first-order architectural input, not a logistics detail.

### 4.5 The mixed-regime reality

The regimes are not binary. Most realistic CPT runs traverse both:

1. **First few million tokens:** compute-bound. The optimizer is doing rapid first-pass adjustment; more compute produces more gain.
2. **Middle ten to hundreds of millions of tokens:** transitional. Compute helps but marginal returns are visibly diminishing.
3. **Long tail:** information-bound. Additional compute on the same tokens produces almost no held-out improvement.

For a 6-hour session of 15M tokens, the entire session likely lies in regime 1 or early regime 2 on a fresh CPT run — the phone has not run long enough to be in regime 3. But across a *month* of sustained training on a fixed 100M-token corpus, the phone walks through all three regimes and spends the latter half of the month in regime 3.

This is a strong implication: **the optimal strategy is not constant across a month of training.** Early days are compute-bound — throughput matters. Late days are information-bound — token quality matters. A monotonic schedule that treats every day the same is mistuned in one direction or the other.

---

## 5. Architectural Implications (Stated As Tensions, Not Recommendations)

The wave-1 architecture conversation centered on (a) which model fits (memory envelope), and (b) which training method fits (Q-GaLore vs ELO vs LoRA). The information-envelope question reshapes the architecture conversation along a different axis. Below are the resulting tensions — each is a *real architectural decision the system will have to make*, not a recommendation.

### 5.1 Tension: Throughput-optimized vs information-density-optimized data path

If the phone is information-bound on a fixed corpus, then optimizing tokens-per-hour is optimizing the wrong variable. The relevant variable becomes *nats-extracted-per-hour* = *tokens-per-hour × nats-per-token*. A scheduler that filters or reweights tokens to improve nats-per-token can win even at lower raw throughput.

This pulls the architecture toward:
- A scoring path that ranks candidate tokens before training (active learning, novelty estimation, base-model uncertainty estimation).
- A skip-this-token decision step that can be executed cheaply (fast forward pass on NPU is the natural fit).
- A training step that can vary in cost per token (curriculum scheduling, adaptive batch size).

But this conflicts with:
- The wave-1 finding that the NPU is best as a *fixed-shape compiled island*. Dynamic per-token routing fights the NPU's nature.
- The simplicity of a constant-throughput training loop. Variable-throughput introduces scheduler complexity and may introduce performance variance.

The architecture cannot simultaneously be (a) maximally throughput-optimized via NPU fixed shapes and (b) maximally information-density-optimized via dynamic per-token filtering. **It must choose where on this spectrum to operate, and the choice depends on whether the phone is in the compute-bound or information-bound regime at the relevant timescale.**

### 5.2 Tension: Wide-surface plasticity vs deep-surface plasticity

If extractable signal per token is small, the parameter surface absorbing the signal is over-parameterized. The information goes somewhere — either into the trainable parameters that need it or, more likely, into noise smeared across the trainable surface.

ELO's 7% surface is *narrow but shallow* — it concentrates plasticity in boundary layers, which are good at distribution shift but cannot restructure middle-layer semantic representations. Q-GaLore's full-parameter surface is *wide but information-thin* — it allows every parameter to update but with low rank constraints, which limits how much novel structure can be written per parameter.

For a low-signal regime (information-bound on a small corpus), wide-but-thin surfaces may be writing mostly noise into middle layers. **Narrowing the surface is the right move when signal is scarce.** For a high-signal regime (compute-bound on a large novel corpus), wide-but-thin surfaces are productively distributing the abundant signal. **Widening is right when signal is abundant.**

The architecture's choice between selective-layer training and full-parameter low-rank training is not a hardware-fit question (wave-1 framing) but a *signal-density question*. The wave-1 verdict "Q-GaLore for 4B" presumes the high-signal regime. If the actual Polymath corpus turns out to be low-signal under the base Qwen3-4B, ELO Stage 1 may actually be the more information-efficient choice — not the compromise fallback wave-1 framed it as.

### 5.3 Tension: Replay protection costs vs forgetting risk

Replay overhead is a fixed tax on signal extraction per token. At 15% replay, ~15% of training tokens contribute zero (or even negative) signal to the target corpus while protecting against forgetting. In a compute-bound regime, the replay tax is paid against an abundant resource. In an information-bound regime, the replay tax is paid against the bottleneck — every replay token is a token that did not extract Polymath signal.

This pulls the architecture toward:
- *More* replay in compute-bound regimes (cheap, useful).
- *Less* replay in information-bound regimes (expensive in the scarce resource).

But under-replaying in an information-bound regime risks catastrophic forgetting because the same target-corpus tokens are seen repeatedly — exactly the conditions under which forgetting is most likely. The architecture is squeezed between two failure modes: too much replay wastes the scarce signal, too little replay damages general capability.

The exit from this tension is *selective consolidation*: replay only when the held-out general metric drifts past a threshold, not on a fixed schedule. This connects directly to the "natural learning loops" wave-2 line of work — replay becomes event-driven, not scheduled.

### 5.4 Tension: NPU's strength (cheap forward) becomes the architectural lever

If active learning, novelty estimation, and curriculum routing all require fast forward passes to score candidate tokens, then the NPU's nature as a fixed-shape compiled inference island becomes the *enabling* substrate, not a limitation. The same NPU that wave-1 framed as inference-only becomes the *information-density amplifier* for training.

Concretely: the NPU runs the base model forward over a corpus chunk to compute per-token uncertainty / novelty / base-model surprise. The training loop on CPU+GPU then operates only on the highest-signal tokens. This pattern is architecturally heterogeneous in exactly the way the wave-1 dialogue called natural — and it specifically exploits the NPU's strength to address the *information* bottleneck, not the compute one.

The architectural implication: **NPU forward passes are not "wasted" by being non-trainable. They are the substrate of the information-extraction loop that wraps around the training loop.** This reframes the wave-1 conclusion that the NPU is "inference-only on the training side." It is more accurate to say the NPU's inference is the *scoring layer* that selects which tokens the trainable surface ever sees.

### 5.5 Tension: Storage-resident replay buffer becomes load-bearing

If novelty-based filtering means rejecting most tokens before training, the corpus throughput on the storage path becomes a multiple of the training throughput. To extract 2.5M trained tokens/hour from a 4x-filtered corpus, the storage path must deliver ~10M tokens/hour from UFS. That is well within UFS 4.1 capability for sequential read, but the access pattern (potentially random over a large replay buffer) is closer to UFS random IOPS, which is the more constrained spec.

This pulls the architecture toward:
- UFS-resident replay buffer with carefully managed access locality.
- Pre-staged corpus shards organized by domain/novelty/language to maintain sequential locality during a training interval.
- Pre-computed base-model NLL scores per chunk, cached alongside the corpus shard, so the scoring layer does not need to recompute on every pass.

This is the wave-1 finding "large phone storage is not extra RAM unless the model is flash-shaped" applied to the *corpus*: large phone storage is not infinite replay buffer unless the buffer is access-pattern-shaped.

### 5.6 The single most consequential implication

The information-envelope frame says: **the architecture must internalize whether it is compute-bound or information-bound in the regime it is currently operating in.** A static architecture committed to one or the other is mistuned for the other. The system that wins this lane is one that can move along the compute-bound ↔ information-bound spectrum, not one that picks a point.

Concretely, this means the scheduler — the "university timetable" in the operator's metaphor — is not just a thermal/placement scheduler. It is also a *regime detector*. It measures the held-out NLL improvement rate per token over a recent window and uses that signal to decide whether the next training interval should optimize throughput or information density.

This is upstream of every model and method choice in wave-1. It is not a recommendation for a specific architecture; it is a constraint on what kind of architecture can be coherent.

---

## 6. What Numbers Must Come From Physical Measurement

The bounds in sections 1-4 are wide because the literature does not narrow them at phone-scale CPT on a curated multilingual corpus. The following physical measurements would narrow them substantially. Each is a direct input to the on-device-physical wave.

### 6.1 First-order measurements (block on these before architectural commitment)

**M1. Base-model NLL on a representative Polymath corpus slice.**
- *What:* Compute per-token cross-entropy of Qwen3-4B (and Qwen2.5-1.5B as baseline) on a stratified sample of the Polymath corpus.
- *Why:* Anchors `H_base(C)`. Determines whether the corpus is low-signal or high-signal under the base model.
- *Resources:* Single phone, no training, ~1 hour for 1M tokens.
- *Output:* nats/token per language/domain stratum.

**M2. NLL trajectory under short CPT.**
- *What:* Run 2-hour Experiment 0 with corpus-NLL evaluation every 30 minutes on a held-out Polymath slice.
- *Why:* Anchors the extraction-rate decay curve. Distinguishes the per-token gain trajectory (regime 1 vs 2 vs 3).
- *Resources:* Single phone, ~6 hours total (2h train + eval overhead, repeated for 3 cells).
- *Output:* held-out NLL vs cumulative training tokens, with confidence intervals.

**M3. Sustained throughput in tokens/hour for each candidate (model, method).**
- *What:* Measure tokens/hour after thermal settling (>30 min) for at least Qwen2.5-1.5B + ELO and Qwen3-4B + Q-GaLore configurations. With and without fan; with and without bypass charging.
- *Why:* Anchors the compute envelope of section 3. Distinguishes the 2.5M ELO estimate and the 0.5-1M Q-GaLore estimate.
- *Resources:* Single phone, several hours per cell.
- *Output:* sustained tokens/hour, with thermal trajectory.

**M4. Energy per training token under each thermal regime.**
- *What:* Measure phone-wall watts with an inline meter (or use Android battery-stats integration as a coarser proxy) during sustained training in each thermal regime.
- *Why:* Anchors J/token, which is the denominator of nats/J. Closes the section 3 estimate.
- *Resources:* Inline USB power meter + the throughput runs above.
- *Output:* J/token for each (method, thermal regime) cell.

### 6.2 Second-order measurements (needed to make tensions in section 5 actionable)

**M5. Held-out general-capability metric trajectory under sustained CPT.**
- *What:* Track a small fixed evaluation suite (e.g., 100-question MMLU-style stratified probe) every N tokens during a sustained multi-day CPT run.
- *Why:* Quantifies catastrophic-forgetting rate. Determines the replay-vs-signal-extraction tension (5.3) quantitatively.
- *Resources:* Phone for ~3-7 days continuous training; eval suite must be small enough to run between training intervals.
- *Output:* general-capability score vs training tokens, by replay fraction.

**M6. Active-learning scoring overhead.**
- *What:* Measure forward-pass time on NPU for the base model over a corpus chunk vs full training-step time. Compute the ratio.
- *Why:* Determines whether the active-learning loop (5.4) is cheap enough to amortize at typical filter ratios. If NPU forward is 5% of training-step cost, a 2x filter is worth it whenever per-token signal varies by >5%. If NPU forward is 50%, the trade is harder.
- *Resources:* Single phone, focused benchmark.
- *Output:* (NPU forward, GPU training step) time ratio in ms, per typical sequence length.

**M7. Effective Polymath corpus size after deduplication and quality filtering.**
- *What:* Run the wave-1 Stage 1-3 ingestion pipeline on the actual corpus and report effective token count after dedup, OCR-damage filtering, and quality thresholding.
- *Why:* Determines whether the phone is in case A/B (small corpus, information-bound) or case C/D (large corpus, compute-bound or representation-bound). This is the single biggest crossover-determining number.
- *Resources:* Host-side preprocessing; not a phone task but blocking on the architecture choice.
- *Output:* effective token count per language/domain stratum.

### 6.3 What is structurally unmeasurable from literature

Some quantities cannot be inferred from any published number, even in principle:
- The actual H_true(Polymath) — only an asymptote of a series of larger and larger reference models.
- The actual long-tail decay rate of CPT extraction on this specific corpus.
- The actual interaction between the chosen training method and the corpus distribution — every paper measures this on its own corpus.

These are bounded by physical measurement (M1-M2 narrow them substantially) but not closed by it. Any architecture that claims to have settled these is reward-hacking the bounds.

---

## 7. Open Questions And Unresolved Tensions

### 7.1 What is the actual size of the curated Polymath corpus?

This is the single most consequential unanswered question for the architectural conversation. Without it, the compute-bound/information-bound crossover cannot be located, and section 5's tensions cannot be resolved. The wave-1 estimate "100M-1B tokens" spans the entire crossover region — both regimes are plausible inside that range.

### 7.2 How heavy-tailed is the Polymath corpus distribution under the base model?

Equivalent: is per-token signal uniform or concentrated in a small fraction of tokens? If concentrated, active learning is enormously valuable. If uniform, active learning is overhead with little benefit. This determines whether tension 5.1 leans toward dynamic filtering or static throughput.

### 7.3 At what signal-extraction rate does the marginal joule fail to pay for itself?

A frontier framing: every joule the phone spends should produce information that the model will actually use downstream. At what extraction rate does the joule cost exceed the eventual utility? This requires defining "utility," which is downstream of the actual deployment scenarios — not derivable from the training metrics alone.

### 7.4 Does the regime-detecting scheduler exist anywhere in the literature?

Section 5.6 hypothesizes a scheduler that internalizes regime detection. The CPT literature has *learning-rate* schedulers that adapt to loss curves, but not, to current knowledge, *resource-allocation* schedulers that move between throughput-optimized and density-optimized policies based on extraction-rate measurement. This may be novel architectural territory, in which case it deserves explicit research-line allocation rather than absorption into existing scheduler work.

### 7.5 Is there a self-consistent loop where the phone's training improves its own scoring layer?

If the NPU's base-model forward pass is the scoring layer (5.4), and the trained model becomes the new base, then a recursive loop exists: training updates the scoring layer, which changes which tokens are selected, which changes the training distribution. This is architecturally a different system from a fixed-base CPT. Whether it is *stable* (improves both training and scoring monotonically) or *unstable* (over-fits to the scoring layer's biases) is a serious open question with no clean literature anchor.

### 7.6 Where does the multimodal Polymath corpus put this analysis?

The blueprint Phase 3 is multimodal. Image and audio tokens have very different signal-per-token properties from text. The information-envelope analysis above is text-only. A multimodal extension would need to bound per-modality signal and per-modality energy cost separately — particularly because vision tokens on NPU have a very different J/token from text tokens. This is out of scope for wave-2 but is an architectural assumption that should not be allowed to harden silently.

### 7.7 Falsifiable predictions this wave makes (anchors for later regression)

- **P1.** For a Polymath corpus ≤ 200M effective tokens, no training method on the phone will show monotonically improving held-out NLL past ~2 full epochs. If it does, this analysis is wrong about the information bound.
- **P2.** For the same corpus, Q-GaLore on Qwen3-4B will show higher per-token information gain *only in the first 10-50M tokens*. Past that, ELO on Qwen2.5-1.5B will match or exceed it per joule. If Q-GaLore continues to dominate past 50M tokens, the signal-density regime is higher than this analysis assumes.
- **P3.** An active-learning loop that filters tokens by base-model NLL at a 2x ratio will extract >1.5x more information per training-token-step than uniform sampling, provided the corpus is non-uniform. If filtering provides <1.2x improvement, either the corpus is uniform or the NPU scoring layer is not seeing the heterogeneity this analysis predicts.

These predictions are not commitments. They are anchors against which later measurements can be checked, and they are deliberately stated in a way that can fail.

---

## 8. Resistance V2 Self-Audit

Before close, audit against forbidden patterns:

- `fp-scopeevaporation`: Did this collapse to "scaling laws say X parameters"? No — section 1.2 explicitly rejects scaling-law application to the phone-CPT regime and section 1.3 names CPT-literature as the actual relevant frame, while keeping uncertainty wide.
- `fp-interimossification`: Did the bounds harden into decisions? No — every numerical range explicitly names the conditions that select within it, and section 6 names the measurements that would narrow them. Section 7 lists what is unresolved.
- `fp-demogravity`: Did this collapse to "compute the wave-1 verdict in different units"? No — the information-bound vs compute-bound frame surfaces a question wave-1 did not engage with at all.
- `fp-benchmarkproxy`: Is "nats per token" itself a proxy that could be optimized while the real metric remains open? Partially — yes, NLL improvement is a proxy for downstream utility. This is named explicitly in 7.3 and 7.6. The information-envelope is the *right* proxy for "what the phone can do," but it is not the authority metric (which is energy-to-target-quality, per the blueprint). The relationship between information-extracted and target-quality-achieved is itself an open question (5.4 of the heterogeneous SoC dialogue) that this wave does not close.
- `fp-softrefusal`: Did this say "yes, here is the bound" while shipping a weaker form? No — the bounds are wide because the underlying uncertainty is wide, and the document names why narrowing them requires physical measurement, not more analysis.

The discipline holds.

---

## 9. Sources

### Scaling laws and compute-optimal training
- Kaplan et al. 2020, "Scaling Laws for Neural Language Models" — https://arxiv.org/abs/2001.08361
- Hoffmann et al. 2022, "Training Compute-Optimal Large Language Models" (Chinchilla) — https://arxiv.org/abs/2203.15556
- Sardana et al. 2024, "Beyond Chinchilla-Optimal" — https://arxiv.org/abs/2401.00448
- Hoffmann et al. 2022 erratum and DeepMind follow-up scaling-law replication discussion — https://arxiv.org/abs/2404.10102

### Continued pretraining and domain adaptation
- Gururangan et al. 2020, "Don't Stop Pretraining" (DAPT/TAPT) — https://arxiv.org/abs/2004.10964
- Cheng et al. 2023, "Adapting Large Language Models via Reading Comprehension" — https://arxiv.org/abs/2309.09530
- Ibrahim et al. 2024, "Simple and Scalable Strategies to Continually Pre-train Large Language Models" — https://arxiv.org/abs/2403.08763
- Scialom et al. 2022, "Continual-T0: Progressively Instructing 50+ Tasks to LMs Without Forgetting" — https://arxiv.org/abs/2205.12393
- Lin et al. 2024, "Rho-1: Not All Tokens Are What You Need" — https://arxiv.org/abs/2404.07965 (selective-token training; directly relevant to information-density framing)

### Information theory of language
- Shannon 1951, "Prediction and Entropy of Printed English" — Bell System Technical Journal 30:1 (foundational entropy estimate)
- Brown et al. 1992, "An Estimate of an Upper Bound for the Entropy of English" — Computational Linguistics 18:1
- Bentz and Alikaniotis 2016, "The Word Entropy of Natural Languages" — https://arxiv.org/abs/1606.06996 (cross-lingual entropy comparison)
- Mielke et al. 2019, "What Kind of Language Is Hard to Language-Model?" — https://arxiv.org/abs/1906.04726 (multilingual entropy variation)

### Data quality and information density
- Du et al. 2025 (arXiv:2502.10361) — multilingual data selection at 15% volume matches baseline MMLU (referenced in blueprint Part IV.1).
- Penedo et al. 2024, "The FineWeb Datasets" — https://arxiv.org/abs/2406.17557 (data quality at scale)
- Marion et al. 2023, "When Less is More: Investigating Data Pruning for Pretraining LLMs at Scale" — https://arxiv.org/abs/2309.04564

### Active learning and curriculum
- Mindermann et al. 2022, "Prioritized Training on Points That Are Learnable, Worth Learning, and Not Yet Learned" (RHO-loss) — https://arxiv.org/abs/2206.07137
- Sorscher et al. 2022, "Beyond neural scaling laws: beating power law scaling via data pruning" — https://arxiv.org/abs/2206.14486

### Energy and efficiency of training
- Patterson et al. 2021, "Carbon Emissions and Large Neural Network Training" — https://arxiv.org/abs/2104.10350
- Luccioni et al. 2023, "Power Hungry Processing: Watts Driving the Cost of AI Deployment?" — https://arxiv.org/abs/2311.16863
- Strubell et al. 2019, "Energy and Policy Considerations for Deep Learning in NLP" — https://arxiv.org/abs/1906.02243

### Polymath-AI prior research artifacts
- `RESISTANCE-V2.md` — frontier engineering commandments (governing discipline).
- `docs/HETEROGENEOUS-SOC-RESEARCH-DIALOGUE.md` — heterogeneous SoC research dialogue (architectural context).
- `docs/research/soc-architecture-2026-05-16/trainable-model-envelope.md` — wave-1 memory-budget analysis (capacity envelope, prerequisite reading).
- `source-briefs/01-on-device-training-blueprint.md` — current blueprint (Part IV.1 corpus-mattering; Part VI throughput model).
- `docs/research/soc-architecture-2026-05-16/architecture-models.md` — architecture ranking for faculty/SoC lane.
- `docs/research/soc-architecture-2026-05-16/blind-spots-frontier-scan.md` — blind-spot scan (low-memory optimizer ladder; test-time training; elastic active parameters).

---

## 10. One-paragraph synthesis (for orchestrator handoff)

The phone is plausibly information-bound on the Polymath corpus over the timescales we care about (weeks-to-months), but the literature alone cannot prove this — only physical measurement of the corpus's base-model cross-entropy can. A 6-hour phone session captures somewhere between 80K and 3M nats of model information depending on (training method, corpus signal-density) cell, with a plausible energy efficiency of 1-17 nats/J — comparable to and potentially exceeding cloud baselines per joule. The compute-bound vs information-bound crossover depends on the (model size, corpus size, training method) triple and is well within the range of the candidate configurations: small corpus + small surface (ELO on 100M tokens) is information-bound after 2 epochs; large corpus + large surface (Q-GaLore on 1B+ tokens) is compute-bound for months. The architectural implication is *not* to pick a regime — it is that the architecture must internalize which regime it is in at any moment, which makes the scheduler a regime-detector as well as a thermal/placement controller, and makes the NPU's fixed-shape forward pass load-bearing as the *scoring layer* for active token selection, not merely as inference-only deadweight on the training side. The most consequential unknown is the actual size and base-model cross-entropy of the Polymath corpus — both numbers are first-order architectural inputs and must be measured before commitment.
