# Wave-2 Corpus Modularity Protocol

**Date:** 2026-05-16
**Role:** wave-2 research agent (Polymath-AI lane 21)
**Scope:** protocol design only. Measures whether a text corpus has natural modular structure. Does not pick an architecture, does not pick a model, does not recommend a training method.
**Governing discipline:** Resistance V2 commandments 4 (do not silently lower the ambition), 6 (falsification is a weapon), 7 (no reward hacking), 9 (interim artifacts are frozen until earned). The forbidden patterns most relevant here are `fp-scopeevaporation` (collapsing into "use MoE because it is modular"), `fp-interimossification` (treating this protocol as the result), and `fp-toolbusy` (instrumentation without measurement).
**Authority gate of this artifact:** a falsifiable measurement that closes the *corpus-structure* question — independent of, and not substitutable for, the *runtime-fit* and *training-feasibility* questions handled by other wave-2 agents.

---

## 0. Why the question was opened

The architectural conversation in `HETEROGENEOUS-SOC-RESEARCH-DIALOGUE.md` and `architecture-models.md` is being driven by two pressures:

1. **Hardware fit** — MoE active-parameter economy maps onto Hexagon NPU islands plus Adreno sidecars more cleanly than dense backprop. (`trainable-model-envelope.md` confirms this for Qwen3-30B-A3B, LFM2-8B-A1B, OLMoE.)
2. **Faculty metaphor** — the operator's hypothesis that layer/expert groups can act like university faculties. This was retired as a literal architectural commitment but the underlying empirical claim survived: *that the Polymath corpus may have natural modular structure that an architecture should mirror.*

If the corpus is modular, dense architectures spend compute on a uniformity the corpus does not have — `fp-scopeevaporation` against the structure. If the corpus is dense (single dominant manifold, low intra-vs-cross MI ratio at every scale), MoE / adapter-bank / static-faculty architectures are `fp-toolbusy` regardless of how efficiently they fit Hexagon. The blind-spot scan (`blind-spots-frontier-scan.md` §2) already escalated this as "Expert offload viability is a model property, not a MoE slogan" — the missing half of that claim is **expert offload viability is also a corpus property**.

This protocol measures the corpus side. It is conditioned on the Polymath Seed Corpus v0 / Phase 1A definition (`docs/CORPUS-SPEC.md`: 17 languages, 9 domains, ~100M-1B tokens), but it can run today against open multilingual+multi-domain stand-ins because the protocol does not require the final corpus to exist.

---

## 1. Theoretical framing: what "modular structure" means for a text corpus

A text corpus is modular when it can be partitioned into regions such that the *internal* statistical coupling within each region is substantially stronger than the *cross-region* coupling. The faculty intuition translates into a precise claim about the joint distribution of corpus tokens.

### 1.1 Information-theoretic formalization

Let `D` be a corpus of documents `{d_1, ..., d_N}`, with tokens `x_1, ..., x_T`. Let `P_k = {R_1, ..., R_k}` be a partition of the corpus into `k` non-overlapping regions (the partition method is free — clustering, topic model, domain label, language tag).

Define two coupling quantities:

- **Intra-region coupling** (for region `R_r`):
  `I_intra(R_r) = I(X_i; X_j | both x_i, x_j ∈ R_r)`
  the mutual information between two tokens (or two short spans, or two documents) drawn from the same region.

- **Cross-region coupling** (between distinct regions `R_r, R_s`):
  `I_cross(R_r, R_s) = I(X_i; X_j | x_i ∈ R_r, x_j ∈ R_s, r ≠ s)`
  the mutual information between two tokens drawn from different regions.

The corpus is **modular at granularity `k`** to the extent that
`M(P_k) = avg_r I_intra(R_r) / avg_{r≠s} I_cross(R_r, R_s)`
is substantially greater than 1. A corpus that is uniformly dense yields `M(P_k) ≈ 1` for any partition; a corpus with sharply separated topics/domains/languages yields `M(P_k) >> 1` for the partition that aligns with the separation.

This formulation is independent of the unit of `X`. The same `M(P_k)` shape arises whether `X` is a token, a span, a sentence embedding, or a document embedding — the unit determines what kind of modularity is being measured (lexical, semantic, document-level).

### 1.2 Modularity is multi-scale, not binary

A real corpus may simultaneously have:

- **Language-level modularity** at `k ≈ 17` (one region per language; very high intra/cross ratio because vocabularies barely overlap).
- **Domain-level modularity** at `k ≈ 9` (CS/ML vs philosophy vs music theory — strong but not as sharp as language).
- **Topic-level modularity** at `k ≈ 50-500` (specific subtopics inside a domain).
- **Style/register modularity** orthogonal to all of the above (formal vs conversational, expository vs procedural).
- **No coherent modularity** at most other granularities.

A corpus's "modularity curve" `M(P_k)` plotted across `k` is therefore the object of interest, not a single number. Peaks in the curve reveal natural scales; a smooth featureless decline indicates a dense corpus that does not naturally factor.

### 1.3 Forms of modularity to measure independently

| Modularity type | Partition source | Unit of `X` | What it tests |
|---|---|---|---|
| Language | language tag (provided in manifest) | token | Whether language-blocks are statistically isolated. Almost certainly TRUE at lexical level; less obvious at deep semantic level. |
| Domain | domain tag (CORPUS-SPEC §Domain mix) | document | Whether the 9 declared domains are statistically separable on their own corpus mass. |
| Topic | unsupervised (BERTopic / NMF / LDA over embeddings) | document or paragraph | Whether finer-grained topical clusters exist inside or across the declared domains. |
| Semantic cluster | k-means / HDBSCAN over sentence embeddings | document or chunk | Whether the embedding-space density distribution has separated clouds. |
| Lexical / co-occurrence | community detection over token co-occurrence graph | token | Whether the vocabulary itself factors into modular subgraphs. |
| Style / register | classifier-based partition (formality, code-vs-prose) | document or span | Whether style cuts across domain/topic and creates an orthogonal modular axis. |

Each form is measured separately because each may have a different natural granularity and a different `M(P_k)` curve. A corpus might be highly modular at the language axis, moderately modular at the domain axis, weakly modular at the topic axis, and not modular at all at the style axis — and each of those is an architectural fact, not a single number.

### 1.4 Two specific traps in the formalization

- **Tokenizer-induced false modularity.** If the same tokenizer fragments different languages at different rates (fertility imbalance), apparent lexical modularity may reflect tokenizer artifacts rather than corpus structure. The CORPUS-SPEC fertility audit (`polymath_ai/corpus/fertility.py`) must run *before* lexical-modularity measurement; otherwise the result is `fp-benchmarkproxy` against the tokenizer, not the corpus.
- **Partition-induced false modularity.** A modularity measure is conditioned on the partition method. A partition that already encodes the answer (e.g. clustering on embeddings from a model trained with a domain-aware objective) will produce trivially high `M(P_k)`. The partition must be derived from a model independent of the corpus or from corpus-external metadata (manifest tags).

---

## 2. Measurement techniques from the literature

Each technique below is a candidate operationalization of the abstract `M(P_k)`. None of them is "right" alone; the protocol uses several of them to triangulate.

### 2.1 Direct MI estimation in text

- **MINE (Belghazi et al., 2018)** — Mutual Information Neural Estimation; trains a critic to estimate `I(X; Y)` between high-dimensional random variables by maximizing a Donsker-Varadhan bound. Used widely for representation-level MI, scales linearly with dimensionality. https://arxiv.org/abs/1801.04062
- **InfoNCE / contrastive estimation (van den Oord et al., 2018)** — lower-bound on MI from noise-contrastive objectives; cheaper than MINE and standard for text representation work.
- **InfoNet (2024)** — neural MI estimator that requires no test-time optimization; much faster for the kind of repeated MI estimation a `P_k` sweep needs. https://arxiv.org/abs/2402.10158
- **Flow-based variational MI (ICLR 2025)** — newer estimators using normalizing flows; better for multimodal MI distributions. https://proceedings.iclr.cc/paper_files/paper/2025/file/ac0350c5b1cae780e1670627ced1f8d0-Paper-Conference.pdf
- **Smoothed InfoNCE (2023)** — fixes undershoot/overshoot pathologies of plain InfoNCE; useful when MI estimates need to be comparable across regions.

Direct MI estimation is the gold-standard quantity. Its weakness is that text MI estimates are noisy and require many samples; the protocol therefore also uses cheaper proxies.

### 2.2 Cross-partition perplexity (proxy for KL / cross-entropy gap)

If `M_r` is a language model trained on region `R_r` and `PPL_{r→s}` is the perplexity of `M_r` evaluated on a held-out slice of `R_s`, then the matrix `[PPL_{r→s}]` is a direct proxy for region separability. A highly modular corpus has small diagonal `PPL_{r→r}` and large off-diagonal `PPL_{r→s}` — equivalently, a high ratio `mean(off-diagonal) / mean(diagonal)`.

This is the standard tool of domain-adaptive pretraining and is computationally tractable: a 1-epoch CPT of a small base model on each region is cheap relative to MI estimation, and the resulting matrix is interpretable.

- **DAPT / Axelrod (2011)** — perplexity-based domain selection. https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/emnlp11-select-train-data.pdf
- **Perplexity correlations (Engstrom et al., 2024)** — perplexity on web-domain partitions correlates with downstream behavior. https://arxiv.org/abs/2409.05816
- **Clustered Importance Sampling (Grangier et al., ICLR 2025)** — uses cluster histograms over generalist/specialist data; perplexity-driven; scales to millions of clusters. https://david.grangier.info/papers/2025/grangier_fan_seto_ablin_clustered_importance_sampling_2025.pdf

### 2.3 MoE router specialization

If a small MoE is trained on the corpus, the **entropy of expert assignment per token-class** is a direct read of how much the routing layer found modular structure to exploit.

- **OLMoE (Muennighoff et al., 2024)** — reports strong domain and vocabulary specialization. https://arxiv.org/abs/2409.02060
- **Mixtral (Jiang et al., 2024)** — reports *weak* domain specialization; routing is mostly syntactic. https://arxiv.org/abs/2401.04088
- **A Closer Look into MoE in LLMs (NAACL 2025)** — compares OLMoE/Mixtral specialization side-by-side. https://aclanthology.org/2025.findings-naacl.251.pdf
- **Multilingual Routing in MoE (Bandarkar et al., 2025)** — language-specific routing at early/late layers, language-agnostic at middle layers. https://arxiv.org/abs/2510.04694

The Mixtral finding is critical: it demonstrates that a corpus that *humans* organize into domains may not be a corpus that a router will *learn* to organize that way. This is exactly the empirical disconnect this protocol must measure rather than assume.

### 2.4 Local Routing Consistency (SRP / SCH metrics)

The `blind-spots-frontier-scan.md` §2 reference. SRP (Segment Routing Best Performance) measures how well a fixed expert subset covers a token segment; SCH (Segment Cache Best Hit Rate) measures the cache-hit rate under a fixed cache budget over future tokens. Higher SRP/SCH means routing has spatial locality — adjacent tokens tend to need similar experts.

- **Not All Models Suit Expert Offloading (Zheng et al., 2025)** — primary source for SRP/SCH. https://arxiv.org/abs/2505.16056

SRP/SCH measure routing locality but indirectly measure corpus locality: if consecutive tokens reliably need the same expert, the corpus has local coherence at the segment scale. They are not a substitute for modularity-curve measurement (they conflate model behavior with corpus structure), but they are a cheap on-corpus diagnostic.

### 2.5 Data-selection / mixture techniques

These were built for a different purpose (improving pretraining mixtures) but each implicitly assumes a corpus partition and a notion of inter-partition similarity, which can be inverted to measure modularity:

- **DSIR (Xie et al., NeurIPS 2023)** — importance resampling on hashed n-gram features; KL reduction between selected and target distributions is a partition-similarity signal. https://arxiv.org/abs/2302.03169
- **DoReMi (Xie et al., 2023)** — group-DRO over domains; learned domain weights expose which domains are most loss-distinct. https://arxiv.org/abs/2305.10429
- **DoGE (2024)** — domain-weight learning without a reference model.
- **Data Mixing Laws (Liu et al., ICLR 2025)** — predict loss from mixture proportions; the fitted law's curvature reveals how independent vs interacting the domains are. https://proceedings.iclr.cc/paper_files/paper/2025/file/cc84bfabe6389d8883fc2071c848f62a-Paper-Conference.pdf
- **RegMix (Liu et al., ICLR 2025)** — regression on small-model results; cheaper than DoReMi. https://proceedings.iclr.cc/paper_files/paper/2025/file/5f67d864aae6115374fed7beddd119e0-Paper-Conference.pdf
- **GRAPE (2025)** — group robust multi-target adaptive pretraining. https://arxiv.org/pdf/2505.20380
- **Scaling Laws for Optimal Data Mixtures (Apple, 2025)** — scaling-law decomposition over domain mixtures. https://machinelearning.apple.com/research/optimal-data-mixtures

### 2.6 Branch-Train-Merge / Branch-Train-MiX

Per-domain expert language models followed by ensemble or MoE-merge. The relative improvement of the ensemble over a single dense baseline trained on the same total compute is an empirical proxy for the modularity payoff: if domain-specialist models combined back into an MoE outperform an equal-compute dense model, the domains are statistically separable in a way the architecture can exploit.

- **Branch-Train-Merge (Li, Gururangan et al., 2022)** — independent per-domain training, merge by averaging. https://arxiv.org/abs/2208.03306
- **Branch-Train-MiX (Sukhbaatar et al., COLM 2024)** — independent per-domain training, then upcycle into an MoE. https://arxiv.org/abs/2403.07816
- **BTS (2025)** — harmonizing specialized experts into a generalist LLM. https://arxiv.org/abs/2502.00075

These are *training experiments* not *measurements*, but their delta-over-dense at fixed compute is a high-signal end-to-end test of corpus modularity.

### 2.7 Embedding-space clustering diagnostics

- **BERTopic (Grootendorst, 2022)** — UMAP + HDBSCAN + c-TF-IDF; can produce a hierarchy of topic clusters and the implied modularity at each level. https://arxiv.org/abs/2203.05794
- **Variation of Information (Meila, 2007)** — true metric on the space of partitions; lets the protocol compare partition-vs-partition (e.g. domain tags vs unsupervised clusters vs language tags) without assuming a reference. https://www.sciencedirect.com/science/article/pii/S0047259X06002016
- **Normalized Mutual Information (NMI)** — comparison of two partitions of the same data, normalized to [0,1].
- **Intrinsic dimension of sentence embeddings** — recent work shows intrinsic dimension of LLM representations is informative about complexity and possibly about manifold separability. https://aclanthology.org/2025.findings-acl.1330.pdf , https://arxiv.org/abs/2412.06245
- **HDBSCAN** — density-based clustering that does not require `k` to be specified; useful when the protocol explicitly wants to discover whether well-separated clusters exist.

### 2.8 Modularity / community detection on co-occurrence graphs

- **Newman / Girvan graph modularity Q** — original graph-theoretic modularity; can be applied to token co-occurrence networks. Maximizing Q gives a partition; the value of Q itself measures how modular the resulting graph is.
- **Graph modularity for text co-clustering (Ailem et al., 2016)** — applies graph modularity directly to text document-term graphs. https://www.sciencedirect.com/science/article/abs/pii/S0950705116302064

### 2.9 What is *not* a measurement technique

The following are sometimes treated as modularity evidence; they are not:

- "MoE works well on this corpus" — is a *consequence* of modularity, mediated by training dynamics and many hyperparameters; not a measurement.
- "Experts look interpretable in qualitative inspection" — anecdotal; subject to confirmation bias; OLMoE's *quantitative* specialization claims are valid, the *qualitative* visualizations are not what makes them so.
- "Topic model produces coherent topics" — coherence ≠ modularity. Coherent topics can be heavily overlapping.

---

## 3. The protocol

The protocol is structured as a pipeline of decreasing cost and increasing decisiveness. Each stage produces a measurement that either *gates* progression to the next stage or *suffices* to close the corpus-structure question at one axis.

### 3.1 Inputs

- A frozen corpus snapshot with per-document manifest rows containing: language tag, domain tag, source tag, license class, document ID, character/byte/token count.
- A pre-validated tokenizer (the fertility audit in `polymath_ai/corpus/fertility.py` must pass; otherwise lexical modularity is measuring tokenizer behavior).
- An independent reference embedder (multilingual sentence embedder; e.g. `BAAI/bge-m3` or `intfloat/multilingual-e5-large`) — independent in the sense of not having been trained on the Polymath corpus.

### 3.2 Pre-flight gates (refuse to measure if these fail)

| Gate | Test | Failure response |
|---|---|---|
| Fertility | every core language ≤ 2.5x English fertility | block lexical-modularity measurement; report failure mode |
| License clarity | every region has ≥ 95% Class A/B documents | restrict the measurement to the clean subset; flag |
| Manifest integrity | manifest SHA-256 matches the data; per-region token counts ≥ statistical floor | abort; cannot measure thin regions |
| Embedding sanity | reference embedder produces unit-norm vectors; pairwise distance distribution is non-degenerate on a held-out probe | swap embedder; do not measure with a broken embedder |
| Stand-in fidelity (if Polymath corpus is not yet defined) | the stand-in corpus has the same approximate cardinality of languages/domains as CORPUS-SPEC §Language mix / §Domain mix | proceed but tag every result as "stand-in"; do not promote to a Polymath verdict |

### 3.3 Stage A — supervised modularity along declared axes (language, domain)

Cheapest. Uses corpus-provided tags as the partition.

For each declared axis `A ∈ {language, domain}`:

1. **Partition the corpus into regions** `{R_1, ..., R_k}` using the manifest tags.
2. **Train a small base model on each region** (compute floor: a SmolLM-100M-class model trained for a fixed token budget per region, the same budget across all regions; train budget chosen by §3.7). Open the same dense baseline trained on the union, at the same total token budget, as a reference.
3. **Build the cross-perplexity matrix** `PPL_{r→s}` on a held-out slice of each region.
4. **Compute the modularity statistic** `S_A = mean(off-diagonal) / mean(diagonal)`.
5. **Bootstrap confidence intervals** by resampling held-out slices `B = 100` times.

The statistic `S_A` is the first measurable answer. The protocol does not yet judge the answer — Stage A produces three numbers (`S_language`, `S_domain`, a confidence interval on each) plus the dense baseline.

### 3.4 Stage B — unsupervised modularity curve

For partition method `m ∈ {BERTopic, HDBSCAN-on-embeddings, k-means-on-embeddings}` and granularity `k ∈ {2, 4, 8, 16, 32, 64, 128, 256, 512, 1024}`:

1. **Build the partition** `P_{m,k}` over the corpus (subsample for tractability; record the subsample fraction).
2. **Compute partition-vs-tag agreement** `NMI(P_{m,k}, language tags)`, `NMI(P_{m,k}, domain tags)`, `VI(P_{m,k}, language tags)`, `VI(P_{m,k}, domain tags)`.
3. **Compute the perplexity-matrix modularity statistic** `S_{m,k} = mean(off-diagonal PPL) / mean(diagonal PPL)` over a uniform subsample of the partition's regions. (If `k > 64`, sample 64 region-pairs rather than computing the full `k×k` matrix.)
4. **Compute embedding-density statistics** within and across partitions: average pairwise cosine within `R_r`, average pairwise cosine between `R_r, R_s` (with `r ≠ s`).
5. **Plot the modularity curve** `S_{m,k}` vs `k` for each method.

Stage B produces the modularity curves. Three shapes are interpretable:

- **Sharp peak at some `k*`** — corpus has natural modularity at scale `k*`.
- **Multi-peak (e.g. peaks at 17 and 9 corresponding to language and domain)** — multi-scale modularity.
- **Monotonic decline with `k`** — no scale-aligned modularity; corpus is dense.

### 3.5 Stage C — MoE router specialization (decisive, but expensive)

Trained against the same compute budget as Stage A baselines, with the same eval protocol.

1. **Train a small MoE** (OLMoE-100M-class, 8 experts top-2 or 16 experts top-2; choice not load-bearing as long as it is held fixed across all corpora in the comparison; the active capacity should match the dense baseline of Stage A).
2. **Measure expert specialization** at every layer:
   - `H(expert | domain)` — entropy of expert assignment conditional on declared domain. Low entropy = strong domain specialization.
   - `H(expert | language)` — same for language.
   - `H(expert | unsupervised cluster from Stage B)` — same against the discovered partitions.
   - `MI(expert; domain)`, `MI(expert; language)` — direct MI between routing and tags.
3. **Compute Local Routing Consistency** SRP and SCH per §2.4 over a held-out probe slice.
4. **Compare against a parameter-matched dense baseline** on held-out perplexity. The MoE-dense gap at equal compute is the end-to-end modularity payoff.

Stage C is the most decisive measurement and the most expensive. It is also the most vulnerable to confound: the Mixtral observation (weak specialization despite a clearly multi-domain corpus) means a low specialization reading at Stage C is not automatically a corpus result — it might be a training-dynamics result. The protocol guards against this by:

- **Repeating Stage C with two training seeds and two router-init schemes** (cold-start vs upcycled from a dense init); divergence between them isolates training-dynamics noise from corpus signal.
- **Reading the Stage C result jointly with Stage A and Stage B**, not in isolation. If Stage A shows strong cross-PPL modularity and Stage C shows weak router specialization, the corpus is modular but the router did not exploit it (a training-dynamics result, not a corpus result). If both are weak, the corpus is dense.

### 3.6 Stage D — direct MI estimation (validation only)

Optional. Used to validate the cheaper proxies on a small subsample.

1. Sample `N = 10000` document pairs balanced across the within/cross-region split of the best-supported partition from Stages A-C.
2. Encode each pair with the reference embedder.
3. Estimate `I(emb_i; emb_j | same region)` and `I(emb_i; emb_j | different regions)` using InfoNCE and InfoNet, agree the two estimators within tolerance.
4. Compare the resulting MI-based modularity ratio to the cross-PPL ratio from Stage A.

Stage D is a calibration. If the cheaper proxy and the direct MI estimate disagree by more than a factor of 2, the cheaper proxy is suspect and the protocol must escalate.

### 3.7 Statistical treatment and gates

| Quantity | Statistical treatment |
|---|---|
| Cross-PPL matrix entries | report as mean ± 95% CI from `B = 100` held-out bootstrap resamples; replicate across `S = 3` training seeds |
| Modularity statistic `S` | report ratio with bootstrap CI propagated from numerator and denominator; reject as inconclusive if CI crosses 1.5 |
| NMI / VI | report with bootstrap CI; reject NMI < 0.1 as "no meaningful agreement" with the reference partition |
| Router specialization MI | report per-layer, averaged across `S = 3` MoE training seeds, with seed CI; if seed CI > 30% of mean, the result is training-dynamics-noise-dominated and must be re-run with more seeds |
| SRP / SCH | report at multiple cache budgets `c ∈ {1x, 2x, 4x active experts}` |
| Direct MI estimates | require InfoNCE and InfoNet to agree within a factor of 2; otherwise escalate to MINE with longer training |
| End-to-end MoE-vs-dense gap | report at fixed compute (FLOPs and wall-clock), not at fixed parameter count |

**Hard gates for promoting an `S` to a verdict:**

- The bootstrap 95% CI must not cross 1.5 (the "weakly modular" threshold below which the proxy noise floor is comparable to the signal).
- The statistic must be replicated at the same value (within CI) on a disjoint subsample of the corpus.
- The result must hold under at least two partition methods or two unit choices (token / span / document).

**A statistic that clears the floor in one method but not in another is reported as such**, not as a positive result. A single-method positive is a `fp-localgreen` candidate.

### 3.8 What "the curve" looks like under each hypothesis

Sketches of the expected `S` vs `k` curves under three pre-registered hypotheses:

```
Hypothesis 1: corpus is strongly modular at one natural scale k*
  S(k)
   ^
   |    *
   |   * *
   |  *   *
   | *     *
   |*       * * * *
   +---------------------> k
        k*

Hypothesis 2: corpus has multi-scale modularity
  S(k)
   ^
   |  *           *
   | * *         * *
   |*   *       *   *
   |     *  *  *     * * *
   +---------------------> k
       k1        k2

Hypothesis 3: corpus is dense
  S(k)
   ^
   |***
   |   *
   |    **
   |      ***
   |         ****
   +---------------------> k
```

The protocol pre-commits to these three shape interpretations *before* running. Post-hoc shape-fitting is `fp-benchmarkproxy`.

---

## 4. Conditional architectural implications

**These are conditionals, not recommendations.** Each row says: "*if* the measurement returns this shape, *then* the implication about modular-vs-dense architectures is this." The protocol does not select an architecture. Architecture selection requires additionally satisfying the runtime-fit and training-feasibility gates owned by other wave-2 lanes (residency, expert paging, MeBP/Q-GaLore feasibility, etc.).

### 4.1 By modularity-curve shape

| Curve shape | Natural scale | Conditional implication for *corpus-architecture alignment* |
|---|---|---|
| Strong peak at `k* ∈ {2, ..., 8}` | coarse | Adapter-bank, BTM/BTX-style domain experts, or coarse-grained MoE (4-16 experts) align with the corpus. Dense architecture leaves coarse structure on the table. |
| Strong peak at `k* ∈ {16, ..., 64}` | medium | Fine-grained MoE in the 64-128 expert range (OLMoE / Qwen3-30B-A3B style) aligns with the corpus. Adapter-bank with too few faculties under-resolves the structure. |
| Strong peak at `k* ∈ {64, ..., 512}` | fine | Very-fine MoE (Qwen3.6-35B-A3B's 256 experts, Qwen3-Next's 512 experts) aligns. Coarse adapters are too blunt. |
| Multi-peak (e.g. at 9 and 64) | multi-scale | Nested / MatFormer / mixture-of-mixtures architectures align with the multi-scale structure. A single-`k` MoE matches only one scale. |
| Monotonic decline | none | Dense architectures align with the corpus. MoE/adapter-bank buys no representational alignment — they buy only runtime/memory benefits, which are a separate question. |
| Inconclusive (CI crosses 1.5 at every `k`) | undetermined | Corpus-structure question is not closed. Re-measurement on a larger corpus sample required before architectural commitment can be conditioned on this evidence. |

### 4.2 By per-axis result

| Axis result | Conditional implication |
|---|---|
| Language axis: `S_language >> 1` (almost certain a priori) | Language-specialist experts or language adapters are aligned with the corpus, at least at lexical level. Language-agnostic dense middle layers + language-specific outer layers (the pattern observed in Bandarkar et al. 2025) is corpus-aligned. |
| Language axis: `S_language ≈ 1` | Would be a surprise. If true, the corpus is so cross-lingually mixed that language-specialization buys nothing — supports a uniform dense multilingual architecture. |
| Domain axis: `S_domain >> 1` | The 9 declared domains are statistically separable. BTM/BTX-style domain-expert training is aligned. |
| Domain axis: `S_domain ≈ 1` | The 9 declared domains are *not* statistically separable in cross-PPL — which means either (a) the declared domains overlap too much in practice (a CORPUS-SPEC issue, not an architecture issue) or (b) the corpus does not factor by the human-labeled domain axis. Either way, domain-faculty architectures are unmotivated. |
| Topic axis (unsupervised, `S_topic` peaks at some `k*`) | Topic-MoE at granularity `k*` is corpus-aligned, *independent of* the declared domain taxonomy. If `k*` is much larger than 9, the declared domain taxonomy is too coarse to capture the corpus's natural structure. |
| Style/register axis: `S_style >> 1` | Architectures with style-aware routing (or a separable style head) are corpus-aligned. Independent of domain or language modularity. |

### 4.3 Joint readings (most informative)

| Stage A (cross-PPL) | Stage C (router specialization) | Joint implication |
|---|---|---|
| High | High | Strong corpus modularity that is also exploitable by trained routers. MoE / adapter architectures are corpus-aligned. (Runtime-fit still owned by other lanes.) |
| High | Low | Corpus is modular but routers are not learning to exploit it (Mixtral-like). Implication: either training dynamics need an inductive bias (load balancing, expert dropout, domain-aware aux loss) *or* the corpus modularity is at a representational level the router cannot reach. Architecture-vs-corpus alignment is undetermined; not a green light for MoE without an additional training-design intervention. |
| Low | High | Routers are specializing on something the cross-PPL measurement does not see — likely syntactic / token-class structure, not domain/topic. The OLMoE finding (vocabulary specialization) is in this regime. Implication: experts align with syntax not semantics; architectural alignment is real but not "faculty"-shaped. |
| Low | Low | Corpus is dense at the measured axes. Dense architectures are corpus-aligned. MoE-vs-dense becomes purely a hardware-fit question — and is `fp-toolbusy` if chosen against a dense corpus without an independent justification. |

### 4.4 What this protocol explicitly does not decide

- It does not pick `k` for a deployed MoE.
- It does not say "use OLMoE" or "use Qwen3-30B-A3B" or "use a dense 4B model."
- It does not address whether the chosen architecture fits the phone runtime; that is the residency/SRP/SCH/thermal lane.
- It does not address whether the chosen architecture can be trained on a phone-class budget; that is the Q-GaLore/MeBP/MobiZO lane.
- It does not address whether the chosen architecture is well-served by current backend stacks (QNN/LiteRT/Vulkan); that is the runtime lane.

A clean corpus-modularity verdict is *one* input into the architecture decision, alongside several others. Resistance V2 commandment 4: the maximal architecture decision is conditioned on multiple measurements, none of which is sovereign on its own.

---

## 5. The MoE-runtime-fit question, as a separate concern

Corpus modularity and runtime-fit are independent properties of an architecture-corpus-device triple. The cross-product:

| Corpus modular? | Router-locality (SRP/SCH) high? | What this means |
|---|---|---|
| Yes | Yes | MoE is both representationally aligned and runtime-feasible on a phone. Cleanest case for an MoE choice. |
| Yes | No | MoE is representationally aligned but expert paging cost destroys the active-parameter advantage. Either invest in router-locality engineering (cache, prefetch, expert clustering) or fall back to dense + adapters that preserve modularity without the runtime tax. |
| No | Yes | Corpus is dense; experts route locally only because dense activation patterns are themselves locally consistent. MoE provides no representational benefit. Dense is corpus-aligned; MoE buys only memory economy. |
| No | No | Corpus is dense and routing is volatile. MoE is misaligned on both fronts. Dense architecture is dominant on the corpus-alignment axis; the only remaining MoE argument is hardware memory economy, which has to be weighed against routing-cost penalties. |

**Critical:** this protocol measures the corpus side (columns/rows 1). The SRP/SCH measurement (`blind-spots-frontier-scan.md` §2; `arXiv:2505.16056`) measures the runtime side (rows/columns 2). Both must be closed before an MoE-vs-dense architectural commitment is made on principled grounds. Closing only one and committing is `fp-scopeevaporation` against the other.

A corpus that turns out to be highly modular but whose chosen MoE has poor SRP/SCH on a Hexagon-class device tells us the architecture-corpus alignment is real but the architecture-device alignment is not. The corrective is not "abandon MoE" — it is "redesign the MoE for routing locality, or accept the runtime tax." That decision is owned by the runtime lane after this protocol delivers its result.

---

## 6. What can run NOW vs what is blocked

### 6.1 Runs NOW with no operator action

All of these can be designed, implemented, and pilot-run against open stand-in corpora without depending on any other lane:

- **§3.2 pre-flight gate skeletons** — tokenizer fertility, manifest integrity, embedder sanity checks. Code can be written and tested against a SmolLM3 tokenizer on FLORES-200 + OSCAR-CC + RedPajama-v2 + The Stack subsets.
- **§3.3 Stage A skeleton** — per-region 100M-class CPT, cross-PPL matrix construction. Can run against a stand-in corpus organized to mimic CORPUS-SPEC (e.g. 8 declared "domains" carved from arXiv categories + The Stack subsets + Wikipedia + Gutenberg, 8 declared "languages" carved from FLORES + Wikipedia language slices).
- **§3.4 Stage B skeleton** — BERTopic / HDBSCAN / k-means on a sentence-embedded sample, modularity curve generation. Can run today against any text dataset.
- **§3.5 Stage C OLMoE-100M-class probe** — small MoE training and router-MI measurement. Tooling exists (OLMoE training code, MegaBlocks, MoE-Infinity for router traces).
- **§3.6 Stage D direct MI estimators** — InfoNCE/InfoNet reference implementations exist.
- **§3.7 statistical treatment harness** — bootstrap CI machinery, seed-replication scaffolding. Pure infrastructure.

A pilot run of the full pipeline against a stand-in corpus (e.g. a 1B-token multilingual+multi-domain mix from FLORES + arXiv + The Stack + Gutenberg + WikiSource, organized to match CORPUS-SPEC's language/domain cardinality) will (a) calibrate the noise floor of each statistic on a known-modular corpus, (b) catch implementation bugs before the real corpus is touched, (c) produce a *prior* expectation of what the Polymath measurement is likely to look like — which serves as an internal control against post-hoc shape-fitting on the real measurement.

### 6.2 Blocked on the corpus-characterization wave-2 agent

The following cannot run until the Polymath corpus is defined as a concrete byte stream with manifest:

- **The actual Polymath measurement.** Stages A through D against the real corpus.
- **Per-region token budgets.** Stage A's "fixed token budget per region" requires that the smallest declared region has enough tokens. CORPUS-SPEC's 17×9 = 153 (language × domain) cells, against a 100M-token Phase 1A, gives ~650K tokens per cell on average — likely below the floor for a 100M-class CPT. Stages A and B must be re-scoped to language *or* domain singly (not crossed) at Phase 1A, and crossed only at Phase 1B (500M) or Phase 2 (1B).
- **Fertility audit pass.** §3.2 gate; depends on the actual tokenizer-vs-corpus pairing decided by the operator.
- **License-class filtering of measurement regions.** Cannot use Class C/D/E documents; the measurement region masses depend on what survives this filter.

### 6.3 Coordination handoff to the corpus-characterization agent

This protocol asks the corpus-characterization agent for the following inputs, in order of decisiveness:

1. **A frozen manifest** for the corpus state being measured, with deterministic SHA-256.
2. **Per-region token counts** (language × domain crossed if possible; otherwise the larger of the two axes alone).
3. **The chosen tokenizer**, fertility-audited, with per-language fertility curves.
4. **A held-out probe slice** (5-10% of each region) reserved for cross-PPL evaluation; not seen by any per-region training in Stage A.
5. **The reference embedder choice** (multilingual sentence embedder independent of the Polymath model) for Stage B unsupervised clustering and Stage D direct MI estimation.

In return, this protocol delivers:

- A modularity-curve plot per partition method.
- The cross-PPL matrix per supervised partition.
- The router-specialization table from Stage C.
- A modularity verdict per axis with confidence intervals.
- A flag if the modularity is dominated by tokenizer or partition artifacts (in which case the corpus-modularity question is not closed and a re-measurement after corpus changes is required).

---

## 7. Open tensions and unresolved questions

### 7.1 Tensions internal to the protocol

- **Stage A budget vs Stage A signal.** Per-region CPT must use a fixed token budget; that budget must be large enough to produce trustworthy region-specific perplexities but small enough that the protocol is not itself a frontier training run. There is no published guide for the right budget at the 100M-class model scale. The pilot run on the stand-in corpus is the only way to calibrate this; if the pilot fails to produce stable cross-PPL matrices, the protocol falls back to model-free measurement (Stage B + direct MI in Stage D) and accepts the loss of Stage A signal.
- **MoE training dynamics confound at Stage C.** The Mixtral-vs-OLMoE divergence (same architecture class, very different specialization outcomes) means a Stage C result can be a training-dynamics artifact even with the protocol's seed-replication guard. The protocol mitigates by reading Stage C jointly with Stages A/B; it cannot fully eliminate the confound.
- **Unit-of-X ambiguity.** Token-level, span-level, sentence-level, document-level modularity can give different answers. The protocol measures at three units (token via cross-PPL, sentence via embedder, document via cluster assignment), but no theory says all three should agree. Disagreement is itself an interesting result; reconciling it requires more work.

### 7.2 Tensions with the broader project

- **Corpus modularity vs hardware-fit causal ordering.** The dialogue currently lets hardware-fit drive the architectural choice. This protocol provides a corpus-side input that may *agree with* or *contradict* the hardware-fit conclusion. The orchestrator needs an explicit rule for which side wins when they conflict. A defensible rule: corpus-fit determines what architecture *should* exist; hardware-fit determines what architecture *can be deployed* — and the deployable architecture must minimize misalignment with the corpus structure, not blindly maximize hardware utilization. But that rule is not yet committed.
- **Pre-existing architectural commitments.** `architecture-models.md` already ranks small-active MoE first for the SoC-convergence lane. This protocol is structurally agnostic to that ranking but its result could undermine it if the corpus turns out to be dense. The orchestrator must keep the architectural ranking *conditional* on this measurement, not let it harden — `fp-interimossification` risk.
- **Stand-in corpus risk.** Running the protocol on a stand-in (e.g. OSCAR + arXiv + The Stack + Wikipedia + Gutenberg crossed by language) calibrates the methodology but does not answer the Polymath question. The risk is that the stand-in result hardens into a Polymath belief before the Polymath measurement actually happens. Every stand-in result must be explicitly labeled as such; the architectural ranking must not condition on stand-in results.

### 7.3 Unresolved methodological questions

- **What MI estimator to trust at text scale.** InfoNCE underestimates high MI; InfoNet has weaker theoretical guarantees but is faster; MINE is well-understood but expensive. The protocol uses agreement across estimators as a guard, but no published work settles which estimator to trust for the specific case of corpus-region MI in multilingual text.
- **Does modularity at the embedding layer predict modularity at deeper layers.** Bandarkar et al. 2025 shows that multilingual MoE routing is language-specific at early/late layers and language-agnostic at middle layers. If layer-depth changes the apparent modularity, the protocol may need a layerwise version — measure modularity not just of the corpus but of the corpus *as the model sees it at each layer*. This is a deeper protocol and not yet specified here.
- **Modularity-of-modularity.** A multi-scale modularity curve has its own structure (where are its peaks, how sharp). Is the relevant architectural input the curve itself, or some statistic of the curve? Not yet resolved.
- **Stability under corpus growth.** If the Polymath corpus expands from Phase 1A (100M) through Phase 1B (500M) and Phase 2 (1B), does the modularity curve change shape? If yes, every architectural decision conditioned on Phase 1A measurement is provisional. The protocol can be re-run at each scale; whether the curve stabilizes is an empirical question.
- **Cross-language semantic modularity vs lexical modularity.** Languages share concepts (translation parallelism). A multilingual corpus might be lexically modular (each language is its own token vocabulary) and semantically non-modular (each domain is the same concept distribution across languages). These are different facts and have different architectural implications. The protocol needs to be run in two modes — on raw tokens and on language-normalized representations (multilingual sentence embeddings) — to distinguish them.

---

## 8. Sources

### Information-theoretic / measurement foundations

- Meila (2007), *Comparing clusterings — an information based distance*: https://www.sciencedirect.com/science/article/pii/S0047259X06002016
- Vinh, Epps, Bailey (2010), *Information Theoretic Measures for Clusterings Comparison*: https://jmlr.csail.mit.edu/papers/volume11/vinh10a/vinh10a.pdf
- Belghazi et al. (2018), *MINE: Mutual Information Neural Estimation*, ICML 2018: https://arxiv.org/abs/1801.04062
- InfoNet (2024), *Neural Estimation of Mutual Information without Test-Time Optimization*: https://arxiv.org/abs/2402.10158
- Flow-based variational MI (ICLR 2025): https://proceedings.iclr.cc/paper_files/paper/2025/file/ac0350c5b1cae780e1670627ced1f8d0-Paper-Conference.pdf
- Pointwise Mutual Information (overview): https://en.wikipedia.org/wiki/Pointwise_mutual_information

### Topic modeling and clustering

- Grootendorst (2022), *BERTopic: Neural topic modeling with a class-based TF-IDF procedure*: https://arxiv.org/abs/2203.05794
- Ailem et al. (2016), *Graph modularity maximization as an effective method for co-clustering text data*, Knowledge-Based Systems: https://www.sciencedirect.com/science/article/abs/pii/S0950705116302064
- HDBSCAN (density-based hierarchical clustering): https://scikit-learn.org/stable/modules/clustering.html#hdbscan

### Cross-domain perplexity and data selection

- Axelrod et al. (2011), *Domain Adaptation via Pseudo In-Domain Data Selection*: https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/emnlp11-select-train-data.pdf
- Xie et al. (2023), *Data Selection for Language Models via Importance Resampling (DSIR)*, NeurIPS 2023: https://arxiv.org/abs/2302.03169
- Xie et al. (2023), *DoReMi: Optimizing Data Mixtures Speeds Up Language Model Pretraining*: https://arxiv.org/abs/2305.10429
- Liu et al. (2024-2025), *Data Mixing Laws*, ICLR 2025: https://proceedings.iclr.cc/paper_files/paper/2025/file/cc84bfabe6389d8883fc2071c848f62a-Paper-Conference.pdf
- Liu et al. (2025), *RegMix: Data Mixture as Regression*, ICLR 2025: https://proceedings.iclr.cc/paper_files/paper/2025/file/5f67d864aae6115374fed7beddd119e0-Paper-Conference.pdf
- Engstrom et al. (2024), *Improving Pretraining Data Using Perplexity Correlations*: https://arxiv.org/abs/2409.05816
- Grangier et al. (ICLR 2025), *Clustered Importance Sampling*: https://david.grangier.info/papers/2025/grangier_fan_seto_ablin_clustered_importance_sampling_2025.pdf
- GRAPE (2025), *Group Robust Multi-target Adaptive PrEtraining*: https://arxiv.org/pdf/2505.20380
- Apple (2025), *Scaling Laws for Optimal Data Mixtures*: https://machinelearning.apple.com/research/optimal-data-mixtures

### MoE specialization and routing

- Muennighoff et al. (2024), *OLMoE: Open Mixture-of-Experts Language Models*: https://arxiv.org/abs/2409.02060
- Jiang et al. (2024), *Mixtral of Experts*: https://arxiv.org/abs/2401.04088
- *A Closer Look into Mixture-of-Experts in LLMs*, NAACL 2025: https://aclanthology.org/2025.findings-naacl.251.pdf
- *Mixture of Experts in Large Language Models* (survey): https://arxiv.org/abs/2507.11181
- Bandarkar et al. (2025-2026), *Multilingual Routing in Mixture-of-Experts*: https://arxiv.org/abs/2510.04694
- *Understanding Multilingualism in MoE LLMs*: https://arxiv.org/abs/2601.14050
- *Exploring Expert Specialization through Unsupervised Training in Sparse MoE*: https://arxiv.org/abs/2509.10025

### Router locality / cacheability (runtime-side, paired concern)

- Zheng et al. (2025), *Not All Models Suit Expert Offloading: On Local Routing Consistency of Mixture-of-Expert Models* — primary source for SRP / SCH metrics: https://arxiv.org/abs/2505.16056

### Modular / branch-train-merge / domain experts

- Li, Gururangan et al. (2022), *Branch-Train-Merge*: https://arxiv.org/abs/2208.03306
- Sukhbaatar et al. (COLM 2024), *Branch-Train-MiX*: https://arxiv.org/abs/2403.07816
- *BTS: Harmonizing Specialized Experts into a Generalist LLM* (2025): https://arxiv.org/abs/2502.00075

### Representation geometry (corpus-as-the-model-sees-it)

- *Redundancy, Isotropy, and Intrinsic Dimensionality of Prompt-based Text Embeddings* (ACL 2025): https://aclanthology.org/2025.findings-acl.1330.pdf
- *The Origins of Representation Manifolds in Large Language Models* (2025): https://arxiv.org/abs/2505.18235
- *A Comparative Study of Learning Paradigms in LLMs via Intrinsic Dimension* (2024): https://arxiv.org/abs/2412.06245
- *Semantic Geometry of Sentence Embeddings* (Findings of EMNLP 2025): https://aclanthology.org/2025.findings-emnlp.641.pdf

### Polymath-AI prior research artifacts (in-tree)

- `RESISTANCE-V2.md` — governing discipline
- `docs/HETEROGENEOUS-SOC-RESEARCH-DIALOGUE.md` — heterogeneous SoC dialogue, "Iteration 2026-05-16: Architectural Correction — Faculty Means Sparse Modular Plasticity"
- `docs/CORPUS-SPEC.md` — Seed Corpus v0 definition (languages, domains, license classes, fertility gate)
- `docs/research/soc-architecture-2026-05-16/architecture-models.md` — architectural ranking conditioned on the faculty hypothesis; this protocol measures whether that condition holds
- `docs/research/soc-architecture-2026-05-16/blind-spots-frontier-scan.md` §2 — paired router-locality concern
- `docs/research/soc-architecture-2026-05-16/trainable-model-envelope.md` §MoE Feasibility — confirms that the faculty hypothesis is testable at the OLMoE / LFM2-8B-A1B / EMO scale without needing Qwen3.6
