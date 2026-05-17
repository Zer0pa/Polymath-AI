# Wave-2: Corpus Characterization

Date: 2026-05-16  
Role: Wave-2 Research Agent — corpus question  
Wave-1 skipped this. The architectural lane has been arguing about Qwen2.5-1.5B vs Qwen3-4B vs SmolLM3 vs OLMoE vs Qwen3.6-35B-A3B without grounding any of those choices in what the corpus *is*. That is `fp-scopeevaporation`. This document does not answer the architectural question; it sharpens what the corpus is so the architectural question can be answered honestly.

Boundary: research infrastructure for in silico on-device LLM training and multilingual / multi-domain knowledge model construction. Outputs are research artifacts.

---

## 1. The corpus as currently specified in project artifacts

This section quotes what exists. It does not interpret.

### 1.1 The PRD's specification

`PRD.md` § Seed Corpus v0 Specification (line 380) names a corpus: "Seed Corpus v0". It specifies five **scale targets** (PRD line 385–392):

- Smoke slice: 10K-100K tokens, "CI, Mac, and device smoke"
- Experiment 0 slice: 10M tokens, "Device stack and throughput"
- Phase 1A corpus: 100M tokens, "First real ELO Stage 1 run"
- Phase 1B expansion: 500M tokens, "Curriculum and cross-lingual/domain objectives"
- Phase 2 optional: 1B tokens, "Publishable scale extension"

These are stage targets. They are not corpus identities. None of these table rows names a single document, source, or shard.

The PRD specifies a **domain mix** for Phase 1A (PRD line 396–410): nine domain buckets summing to 100% — CS/ML 15%, math 12%, physics 12%, bio/chem/materials/energy/synbio 12%, music 12%, philosophy 10%, linguistics 10%, code 10%, general replay 7%. Acceptable source classes are named per row ("Open textbooks, permissive docs, arXiv CC-licensed papers, public-domain texts") but no specific source IDs are pinned at the PRD level.

The PRD specifies a **language mix** (PRD line 414–446): 16 named languages, grouped into English (30%), high-resource European (25%), CJK (15%), Arabic/Russian/Hindi (15%), African/low-resource (10%), classical (5%). It explicitly defers concrete per-language allocation to a downstream Decision (D-002).

The PRD specifies **license classes A–E** with training and redistribution rights (line 449–460). It locks "Only A/B sources enter default training. C sources require a decision record and isolation. D/E sources are excluded."

The PRD specifies **OCR provenance fields** (line 462–476): per-document hash, scanner, OCR engine, settings, page confidence, normalization, header/footer removal, perplexity-damage score, repair notes.

What the PRD does **not** specify: which books, which papers, which Wikipedia revisions, which arXiv IDs, which OCR pipeline, which language detector, which deduplication scheme threshold, which redundancy structure across the nine domains, which mutual information is expected across the natural partitions, which sequence-length distribution, which factual density target, which provenance attestation mechanism beyond "license_attestation_id" as a field name.

### 1.2 What `docs/CORPUS-SPEC.md` adds

`CORPUS-SPEC.md` adds a **source register** (line 89–105) — but it explicitly labels itself "a register of *candidate* sources":

| Source ID | Class | Languages | Domains | Status |
|---|---|---|---|---|
| `gutenberg:public-domain` | A | en, fr, de, es, it, la, el | philosophy, linguistics | candidate, no manifest |
| `wikipedia:cc-by-sa-3.0` | C | all | all | flagged: share-alike "contagious; isolate or exclude pending license decision" |
| `wikisource:public-domain` | A | many | philosophy, linguistics | candidate, no manifest |
| `arxiv:cc-by-4.0` | B | en (mostly) | CS, math, physics, bio | "full-corpus subset must be filtered by license metadata" |
| `flores-200` | B | many | linguistics | reclassified to C in D-014 — "measurement-only", barred from Phase 1A training |
| `musictheory:public-domain` | A | en, de, fr, it | music | candidate, no manifest |
| `tatoeba:cc-by` | B | many | linguistics | candidate, no manifest |
| `oscar:cc-clean` | C | many | general replay | "CC subset filtered for permissive license; class C and isolate" |
| `unicodebooks:public-domain` | A | la, el | philosophy | candidate, no manifest |

CORPUS-SPEC.md line 7 states: "Bulk corpus content lives on private Hugging Face under Architect-Prime; the repo carries manifests, license attestations, and tiny fixtures only." Line 91: "None of these enter training until a per-source license attestation row is added to the manifest." Line 105: "The above is intentionally a register of *candidate* sources."

So the source register names possibilities. It does not constitute a corpus.

### 1.3 What has actually been measured

D-017 (DECISIONS.md line 384–422) records a real empirical event: a tokenizer fertility audit ran on **FLORES-200 dev split, 100 sentences per language, 16 target languages**. This produced numbers — Qwen tokenizer ratios per language. Two languages failed the 2.5x English fertility gate: Zulu (2.68x) and Greek (4.38x).

These numbers are not a corpus characterization. They are a tokenizer-side property of a *substitute* dataset (FLORES-200) used as a fertility proxy. FLORES-200 is explicitly barred from Phase 1A training per D-014. The 16 fertility samples are 100 sentences each — total surface ~250 words per language. This proves the audit pipeline works. It does not characterize Polymath's actual corpus.

The fixture files at `data/fixtures/fertility/<lang>.txt` (12 languages present, see `data/fixtures/fertility/`) are public-domain or CC0 sentence samples used to exercise the fertility code path before phone arrival. They are not the corpus.

### 1.4 What the operator-facing blueprint says

`source-briefs/01-on-device-training-blueprint.md` Part IV ("Data Strategy") is the closest existing engagement with the corpus question. It is conspicuously vague.

Quoting verbatim:

- Line 322 (§4.1): "A 2025 paper (arXiv:2502.10361) demonstrates that model-based multilingual data selection allows a 1B-parameter Llama model to match baseline MMLU score using only 15% of the standard training token volume."
- Line 322 continues: "For a Polymath corpus where curation is inherently high — the source material is selected books, scholarly texts, and structured knowledge — this result is directly relevant."

The phrase "selected books, scholarly texts, and structured knowledge" is the entire concrete corpus claim in Part IV. No source IDs. No domain coverage targets. No language list. No factual-density estimate. No redundancy expectation.

Lines 327–360 describe a **pipeline** for ingesting hypothetical corpus content (OCR normalization, language detection, deduplication, language balancing, replay set construction, curriculum scheduling, cross-lingual objectives). The pipeline is detailed; the inputs to it are not.

Part IV §4.4 names a **fertility audit** as a "blocking pre-condition for finalizing the model choice" but says nothing about what corpus the fertility audit must run on. The fertility audit must run on samples *from the Polymath corpus*, but the Polymath corpus is what is missing.

### 1.5 What the synthesis already flagged

`synthesis/01-fresh-eyes-on-polymath-blueprint.md` § "Twelve specific things the blueprint does not see", point #7 (line 135–149), titled "The 'Polymath corpus' itself is unspecified":

> "The blueprint's data strategy (§4) is structurally sound — pipeline architecture, balancing, replay, curriculum, cross-lingual objectives — but it does not specify **which corpus**. Domain coverage, language list, scale targets, source provenance, OCR origin, IP licensing decomposition, ethical-sourcing audit — these are all left for downstream resolution."

> "For an 'anti-toy / overdesigned best-in-class' build, the corpus IS the moat. The blueprint's own §4.1 says 'the corpus may matter more than the architecture.' The synthesis recommendation: **the corpus design must be a first-class spec component in the orchestrator's PRD**, not a downstream concern."

The synthesis lists what the corpus design must include: domain list, language list, scale target, source provenance (which book corpora? which open-access set? which structured knowledge?), license decomposition (the four-column license audit pattern), OCR provenance. The synthesis closes (line 251): "All other open questions are within the orchestrator's delegated authority per the operator's 2026-05-01 refinement... 1. The corpus design (domain list, language list, scale, sources, license decomposition). The synthesis cannot resolve this without operator input — what is the Polymath corpus actually composed of?"

The orchestrator PRD then defers the same question (PRD line 1082 — open question #8): "**Seed Corpus v0 source availability:** Default corpus spec is selected, but every source still needs license decomposition."

### 1.6 Summary of what exists

What exists as a concrete object:

- A nine-row domain mix target (percentages)
- A 16-language language mix target (percentages, with two languages — zu, el — dropped per D-017 for the first Qwen run)
- License classes A–E with policy gates
- OCR provenance schema (fields, not data)
- Nine candidate source IDs, none yet bound to a manifest
- A working fertility audit pipeline tested on FLORES-200 (a different dataset, used as a tokenizer probe, not as training corpus)

What does not exist as a concrete object:

- An enumerated list of training documents
- Per-source token counts
- Per-source license attestation
- Per-source OCR provenance records (no OCR has yet been done)
- Per-source factual-density estimate
- Per-source-pair redundancy / overlap measurement
- A measured sequence-length distribution
- A measured cross-domain mutual-information structure
- A measured cross-language structural overlap
- A held-out evaluation split with stated separation guarantees from training
- A single byte of corpus text in either the repo or the announced HF private dataset (`Architect-Prime/polymath-corpus-seed-v0` per CORPUS-SPEC.md line 119; the spec notes this dataset is "created at first real ingestion" — meaning it does not yet exist)

The Polymath corpus is currently a **specification of a future object**, not an object. Architectural choices that depend on properties of this object are choices made against a placeholder.

---

## 2. What must be true to characterize the corpus defensibly

This section names the minimum spec for the corpus to function as a load-bearing input to architectural choice. "Minimum defensible" — not "best possible".

The architectural question (dense vs MoE vs adapter-bank, base model selection, tokenizer extension yes/no, faculty boundary placement) reduces to the question "what is the agent being asked to compress?" Until the corpus is a measurable object, that question has no answer and any architectural choice is unfalsifiable.

### 2.1 Identity properties (without these, the corpus is not an object)

1. **A frozen enumeration of source artifacts**. Either a list of document hashes, or a deterministic procedure (source URL + revision + extraction script + commit hash) that produces a list of document hashes. Without this, "the corpus" refers to something different each time it is built.

2. **A measured total token count under a chosen tokenizer**. The PRD names target token counts (10M, 100M, 500M, 1B). It does not specify a chosen tokenizer for that measurement. Tokens are tokenizer-dependent units. A 100M-token Qwen-tokenized corpus is not the same physical text as a 100M-token SmolLM3-tokenized corpus. The token count is a property of the corpus *and* a tokenizer jointly. Until a tokenizer is named for the token-count target, "100M tokens" is ambiguous.

3. **A frozen train/eval split**. With explicit guarantees about non-overlap. Without this, "in-domain recall" (PRD line 798) and "catastrophic forgetting on held-out English" (line 678) are not well-defined.

4. **A per-document license attestation** for every document in the enumeration. License class (A/B/C/D/E), license attestation ID, redistribution policy. The repo specifies this schema; it does not yet have the data.

### 2.2 Structural properties (without these, architectural choice is unfalsifiable)

5. **A measured per-language token-share distribution**. Not the target distribution (which is named) but the realized distribution after deduplication, quality filtering, and license filtering. Targets and realized shares routinely diverge by 10–40% in real corpus construction; that divergence is itself a corpus property.

6. **A measured per-domain token-share distribution**, similarly post-filter. Domain assignment requires either source-side metadata (arXiv categories, Gutenberg subject tags) or a classifier. Either choice is a corpus design decision that must be recorded; the classifier itself becomes a corpus dependency.

7. **A measured tokenizer fertility per (language, tokenizer, domain) triple on actual corpus samples**. The existing FLORES-200 audit measures (language, tokenizer) only — and on a dataset that will not enter training. Domain-stratified fertility is needed because mathematical notation, code, and OCR'd 19th-century Gothic-script German have very different fertility profiles than FLORES news translations.

8. **A measured deduplication ratio**. Both within-document (paragraph-level) and across-document (passage-level). Book corpora — explicitly named in the blueprint — have known high redundancy structures: multiple editions, translations of identical works, abridged-vs-full editions, anthologies that reprint chapters. A naive 100M-token target without dedup measurement may be 60M unique tokens. This matters because effective epochs over unique content are what the model actually trains on.

9. **A measured sequence-length distribution at the document level**. Books are long. Tatoeba sentence pairs are short. arXiv abstracts are medium. The PRD specifies "1,024–2,048 tokens with 128-token overlap" as a chunking target (blueprint line 333). But the distribution of source-document lengths before chunking determines whether the model sees coherent multi-paragraph context (long source documents) or stitched-together short fragments (sentence-corpus sources). For long-context training, this is decisive; for short-context smoke, less so.

### 2.3 Properties whose values determine architectural fit

10. **Cross-domain mutual information structure**. This is load-bearing for the dense-vs-MoE-vs-adapter-bank question (see §5). It measures: given an embedding model E, for each domain pair (A, B), what is the empirical MI between representations of A-documents and B-documents? High cross-domain MI argues for a dense shared trunk; low cross-domain MI plus high within-domain MI argues for modular / faculty / MoE structure. This is **the** measurable corpus property most directly relevant to the architectural question, and it is currently unmeasured.

11. **Cross-lingual structural overlap**. For the multilingual question. If the same conceptual content is present in multiple languages (parallel or near-parallel passages), cross-lingual transfer objectives become tractable. If the per-language slices are content-disjoint, cross-lingual transfer is asking the model to learn cross-lingual structure from zero overlap — an inherently harder problem. The blueprint's §4.3 ("Contrastive cross-lingual alignment") assumes near-parallel passages exist; this is a corpus property that must be measured before that pipeline branch is committed.

12. **Factual density / knowledge claim density**. Tokens-per-factual-claim varies enormously by source class — Wikipedia is high-density, novels are low-density, mathematical proofs are extremely high-density per token but extremely narrow per claim. The blueprint argues (§4.1) that "high-quality curated data can match 6× more unfiltered data" — that claim depends on density measurement, which currently does not exist for Polymath's corpus.

13. **OCR damage profile**. The PRD names `ocr_damage_score` as a field. No OCR has been run. The realized OCR damage distribution determines what fraction of the corpus enters training and what fraction is quarantined. If 30% of OCR'd material falls above threshold, the realized corpus is 30% smaller than the source-side estimate.

14. **Per-source factual reliability flags**. Where corpus pieces contradict each other (different editions of the same work; competing theoretical claims; outdated science), the corpus has internal inconsistency structure. A faculty / MoE architecture might isolate this by source partition; a dense architecture must average it. This is a corpus property that determines architectural pressure.

### 2.4 Properties whose absence is itself architecturally informative

15. **The set of corpus regions for which no clean license attestation can be obtained**. The PRD bars D and E classes. The size of this exclusion set, post-attempt, is a corpus property — if 80% of candidate music-theory texts turn out to be D/E, the music-theory domain target may not be achievable at the planned 12% share. This produces a real downstream constraint that the architectural lane is currently ignoring.

16. **The set of tokens / character ranges for which the base tokenizer has zero or near-zero coverage**. The FLORES audit revealed Greek under Qwen at 4.38x and Zulu at 2.68x. There are likely other regions of the actual corpus where coverage is poor — domain-specific notation (musical, mathematical, chemical, programming-language-specific), classical-language ligatures, OCR'd glyphs that don't map to NFC, emoji or modern web artifacts. The realized list is unknown.

These eight identity properties (§2.1) plus eight structural-and-architectural properties (§2.2–§2.4) constitute the minimum defensible corpus specification. The current spec covers ~3 of these 16 (license schema, target percentages, OCR field schema). The remaining 13 are unmeasured.

---

## 3. Measurable corpus properties that matter for the architectural question — with proposed measurement methods

For each property, the measurement method is named in enough detail that an executor can begin work without re-deriving it.

### 3.1 Domain partition mutual-information matrix

**What is measured**: For nine domains D1..D9 (PRD mix), the empirical mutual information matrix MI(Di, Dj) over a chosen embedding space.

**Why it matters**: Argued in §5. This is the single most architecturally informative corpus measurement.

**Method**:
- Choose an embedding model. A small multilingual sentence-transformer (e.g., `intfloat/multilingual-e5-small`, ~120M params, runs on Mac CPU) is sufficient.
- For each domain, embed N (≥1000) documents from the candidate sources.
- Compute pairwise CKA (Centered Kernel Alignment) or mutual information lower bounds (e.g., InfoNCE estimator) between domain representations.
- Output: 9x9 matrix of cross-domain similarity / MI estimates, with within-domain (diagonal) values as reference.

**Falsifier proxy**: if the off-diagonal cross-domain MI is within 10–20% of the within-domain MI, the corpus is more homogeneous than nine separate "faculties" — the dense architecture is empirically supported. If off-diagonal is <50% of within-domain, modularity is empirically supported.

**Cost**: ~2 hours on a Mac with 1000 documents/domain. Can begin today using publicly available probe corpora (see §4).

### 3.2 Per-(language, tokenizer, domain) fertility table

**What is measured**: tokens_per_word, tokens_per_char, ratio_vs_english_baseline, for each cell of (16 languages × 9 domains × 3 candidate tokenizers).

**Why it matters**: extends D-017 from (language, tokenizer) to (language, tokenizer, domain). Math notation, code, classical languages, OCR damage all produce per-domain fertility deviations that the FLORES-only audit cannot detect. If domain X under language Y under tokenizer Z is >2.5x, that cell cannot enter Phase 1A — and the realized domain mix shifts.

**Method**:
- Existing `polymath_ai/corpus/fertility.py` already does the (language, tokenizer) cell. Extend the input to accept (language, domain) samples.
- For each cell, draw ~10K-word samples from candidate probe corpora.
- Run the existing pipeline. Emit a 16 × 9 × 3 = 432-cell table.

**Cost**: hours to days, parallelizable.

### 3.3 Sequence-length distribution at source-document level

**What is measured**: For each candidate source, the distribution of document-level token counts (5th, 50th, 95th percentiles; mean; max).

**Why it matters**: Determines whether long-context training is even possible from this corpus, and at what token cost. The base models under consideration have native contexts from 8K (older Qwen) to 128K (Gemma 4 E4B). If 95% of source documents are under 2K tokens, the long-context training target is corpus-limited regardless of model context window.

**Method**: Sample-tokenize. For each candidate source, draw 1000 documents, tokenize, record lengths.

**Cost**: Hours.

### 3.4 Deduplication ratio (MinHash-LSH)

**What is measured**: Fraction of total tokens that are unique at the paragraph level (5-gram MinHash with Jaccard threshold 0.85, per blueprint §4.2 Stage 2). Both within-source and cross-source.

**Why it matters**: Determines realized vs target corpus size. If dedup ratio is 0.6 across the candidate sources, a 100M-target corpus produces 60M unique tokens.

**Method**: Standard tooling (e.g., `datasketch.MinHashLSH`, `text-dedup`). Library implementations exist; this is engineering, not research.

**Cost**: Single-digit hours on a Mac per ~10M-token slice.

### 3.5 Factual density estimator (proxy)

**What is measured**: For each domain, the rate of (subject, relation, object) triples extracted per 1000 tokens. Used as a proxy for factual claim density.

**Why it matters**: The blueprint's curation thesis ("high-quality curated data can match 6× more unfiltered data") depends on density being measurably higher than uncurated baselines. If Polymath's curated corpus has density comparable to OSCAR or CommonCrawl on the same domains, the curation premium is unproven.

**Method**: Run a small open-information-extraction model (e.g., a fine-tuned T5 OIE; ~200M params; runs on Mac) over a sample. Record triples/1000-tokens per domain.

**Cost**: ~hours per sample; output is a per-domain density vector.

### 3.6 Cross-lingual structural overlap

**What is measured**: For each language pair (en, X), the fraction of the X-side corpus that has any near-parallel passage on the en side. Measured by cross-lingual embedding similarity (e.g., LaBSE).

**Why it matters**: The blueprint's "contrastive cross-lingual alignment" objective (§4.3) assumes overlap exists. The realized overlap determines how much of that pipeline branch is exercisable.

**Method**: LaBSE-embed both sides at chunk level; for each X-side chunk, retrieve k-nearest en-side chunks; threshold on cosine. Emit per-language-pair overlap fraction.

**Cost**: Single-digit hours.

### 3.7 Tokenizer coverage gap analysis

**What is measured**: For each candidate tokenizer, the set of characters / character sequences in the corpus for which the tokenizer produces fallback bytes (single-byte tokens) rather than learned merges.

**Why it matters**: Direct evidence for vocabulary extension necessity. Greek under Qwen at 4.38x is a known symptom; the cause is byte-level fragmentation. The corpus may contain other byte-fragmented regions (mathematical Unicode, music notation, programming-language operators in code domain) that the FLORES-only audit cannot reveal.

**Method**: Tokenize corpus samples; for each token, check whether it appears as a single-byte fallback in the tokenizer's special-byte range. Emit per-character-class fragmentation rate.

**Cost**: ~1 hour per tokenizer per corpus sample.

### 3.8 OCR damage profile (when OCR is performed)

**What is measured**: Per-chunk perplexity under a small reference LM (e.g., the base Qwen2.5-1.5B), normalized by chunk length. Outlier chunks flagged as OCR-damaged.

**Why it matters**: Determines the realized quarantine rate, which determines realized corpus size and balance across sources.

**Method**: Per blueprint §4.2 Stage 2. Run base Qwen on samples; emit perplexity distribution; threshold.

**Cost**: GPU-hours if scaling up; sample-scale feasible on Mac CPU.

### 3.9 Per-source license-attainability rate

**What is measured**: For each candidate source on the register, the fraction of documents that pass per-document license attestation (the CORPUS-SPEC requirement). Particularly relevant for Wikipedia (CC-BY-SA contagion concern; CORPUS-SPEC line 96), arXiv (per-paper license metadata needed; CORPUS-SPEC line 98), OSCAR (filtered subset only; line 102).

**Why it matters**: Determines whether the source-register percentages can be realized. If only 12% of arXiv is CC-licensed and the target was 15% from arXiv-class sources, the gap must be filled from elsewhere or the target reduced.

**Method**: Manifest-walk. For each source, query the license metadata field; tally pass-rates.

**Cost**: Hours, mostly data engineering.

### 3.10 Held-out separation guarantee

**What is measured**: For the chosen evaluation set, the fraction whose 13-gram (or longer) presence in the training set is zero, per established eval-contamination practice.

**Why it matters**: Catastrophic-forgetting metrics (PRD line 296) and in-domain recall (PRD line 798) are not interpretable without a contamination guarantee. The MMLU baselines used as anchor are known to leak into web-crawl-derived corpora; whether they leak into Polymath's curated corpus is a measurable property.

**Method**: Standard n-gram-overlap audit (e.g., Llama 3 paper's methodology).

**Cost**: Hours.

---

## 4. The minimum work that could begin without further operator input

This section names work that does not require the operator to specify what the Polymath corpus is. It produces a **probe corpus** — a public, license-clean stand-in whose properties expose the architectural question's measurement space.

### 4.1 Probe corpus construction (Mac-only, today)

A defensible probe corpus can be assembled from class-A/B public sources within the next executor session:

- **Project Gutenberg PD slice** (English, French, German, Spanish, Italian, Latin, Greek): philosophy, history, fiction. Class A. ~3B tokens available, sample 50–500MB.
- **arXiv abstract-only CC-BY slice**: per-paper license metadata is in the arXiv OAI-PMH dump. Filter to CC-BY. Class B. Provides math, physics, CS, biology coverage. Sample ~100MB.
- **Wikisource public-domain**: multilingual, structured knowledge. Class A. Sample ~100MB per language.
- **Tatoeba CC-BY**: sentence pairs, multilingual. Class B. ~5MB per language.
- **The Stack v2 permissive-only slice** (Apache-2.0, MIT, BSD code): code domain. Class B with attribution requirements. Sample ~100MB.
- **OSCAR CC-BY filtered subset** as the multilingual general-domain baseline. Class C — measurement-only, per the FLORES precedent (D-014).

This probe corpus is **not** the Polymath corpus. It is a public stand-in whose only purpose is to make the measurements in §3 executable today. Every measurement run on the probe corpus is a falsifiable prediction about what the same measurement will produce on the eventual Polymath corpus, provided the operator confirms the probe's structural similarity to their intended sources.

### 4.2 Measurement runs that can complete this week on probe corpus

In approximate order of architectural informativeness:

- §3.1 (domain MI matrix) on probe corpus → first empirical evidence on the dense-vs-modular question
- §3.2 (per-domain fertility) on probe corpus → extends D-017 to detect domain-specific tokenizer failures
- §3.3 (sequence-length distribution) on probe corpus → bounds the long-context training claim
- §3.4 (dedup ratio) on probe corpus → exposes redundancy structure typical of book corpora
- §3.7 (tokenizer coverage gap) on probe corpus → identifies the next likely-blocked vocabulary regions beyond Greek/Zulu

§3.5 (factual density) and §3.6 (cross-lingual overlap) require more setup but remain Mac-feasible.

### 4.3 Baseline-corpus surveys to import

Public corpus papers that have published the §3-style measurements on related corpora — useful as reference distributions:

- **RedPajama v2**: dedup-ratio statistics by source. Public.
- **The Pile**: per-source token shares and quality scores. Public.
- **CulturaX**: per-language statistics with cleaning details.
- **FineWeb-Edu / FineWeb-2**: factual-density curation methodology.
- **Gamayun (cited in blueprint §4.1 as arXiv:2512.21580)**: published per-language allocations and curriculum results at 2.5T scale.
- **Dolma**: per-source license decomposition (the closest published methodology to PRD's class A–E scheme).

Each of these provides a reference distribution against which Polymath's measured probe-corpus values can be compared, exposing how Polymath is similar to or different from existing well-characterized corpora.

### 4.4 Two operator-light decisions that the executor can stage

These are not operator decisions; they are executor-stageable choices presented in pairs so the operator can resolve them with a one-line confirmation:

- **Tokenizer for the canonical token-count unit**: Qwen2.5-1.5B's tokenizer (already selected as primary; vocab 151,643) vs SmolLM3-3B's tokenizer (vocab 128k). Pick one as the canonical unit for "100M tokens". The architectural lane currently uses these interchangeably.
- **Probe corpus shard size**: 100MB total vs 1GB total. Larger gives tighter measurements at the cost of Mac storage. The PRD bars bulk on Mac, but a temporary probe shard is consistent with the spec.

Neither requires operator deliberation; both can be defaulted (Qwen tokenizer; 100MB probe shard) with a one-line override if the operator disagrees.

---

## 5. Implications for the open architectural question — stated as tensions and conditional implications, not as recommendations

The architectural question is: dense vs MoE vs faculty-adapter-bank, base model selection, tokenizer extension, faculty boundary placement. The corpus structure determines which of these is defensible. The implications below are conditional — they say "if the corpus has property X, then architectural choice Y is supported / falsified."

### 5.1 The dense-vs-MoE tension is corpus-determined

If the measured cross-domain MI matrix (§3.1) shows high off-diagonal values — i.e., the nine domain partitions share substantial structure — then:
- the dense shared-trunk architecture is empirically supported
- "faculties" as discrete partitions is a category error against this corpus
- the architectural lane's pivot toward MoE/faculty becomes corpus-unjustified

If the measured matrix shows low off-diagonal values relative to high diagonal values — i.e., the domains are genuinely structurally separate — then:
- modular / MoE / adapter-bank architectures are empirically supported
- the dense 4B baseline becomes a measurement instrument, not the architecture
- the faculty metaphor has empirical purchase

This tension is **currently unresolved by measurement**. The architectural lane has already pivoted toward MoE (HETEROGENEOUS-SOC-RESEARCH-DIALOGUE.md line 388 ranks "Small-active modular MoE" first). That pivot is justified by phone-substrate-fit arguments (active-parameter economy on 24GB RAM). It is not justified by corpus-side measurement. The two justifications can both be true, but they are independent — the substrate fit does not imply the corpus structure.

### 5.2 The base-model question is corpus-determined

The architectural lane has been arguing about Qwen2.5-1.5B vs Qwen3-4B vs Gemma 4 E4B vs OLMoE vs Qwen3.6-35B-A3B. Each of these has a fixed pretraining corpus that has already determined where its representations are dense and where they are sparse. The compression operation in continued pretraining is the *relative* compression — how much novel structure the Polymath corpus contains beyond what the base model has already compressed.

Conditional implications:

- If the Polymath corpus is dominantly text-domain content that overlaps heavily with the base model's pretraining (which itself spans 7–18T tokens for Qwen2.5, 11.2T for SmolLM3), then the ELO 100M-token CPT target is **adapting representations**, not teaching new structure. The base-model choice matters less; the base-model size matters more (more parameters = better retention of existing representations under boundary-layer updates).

- If the Polymath corpus contains novel structure — domain-specific notation outside the base tokenizer's coverage; languages where the base model has shallow representations (per the FLORES audit, this is already known for Zulu); curated structured-knowledge density above the base model's exposure — then the base-model choice is decisive in a way none of the wave-1 model selection arguments addressed. Different base models will have very different *novel-structure exposure profiles*.

The current architectural lane treats base-model selection as a runtime/deployment question (Snapdragon export, vocabulary size, regularity for partitioning). The corpus-side question (how much novel structure does this corpus contain relative to each candidate base?) is unmeasured.

### 5.3 The tokenizer extension question is corpus-determined

The PRD specifies that languages above 2.5x fertility trigger the falsifier `tokenizer_fertility_high` (line 289). D-017 dropped Zulu and Greek under Qwen. This is a corpus-token interaction — and the FLORES-based measurement is a proxy. The actual corpus may have:

- More byte-fragmented regions in non-FLORES domains (math, music, code, classical languages) that the FLORES audit cannot reveal
- Better fertility in domain-restricted slices (e.g., Greek philosophy in classical Greek may have different per-domain fertility than FLORES Greek news translations)

The architectural implication: tokenizer extension is currently a "no" decision driven by a substitute measurement. Whether it is a sound decision against the actual corpus is unknown until §3.7 runs on the actual corpus. A wrong "no" here forces the corpus to be reshaped to fit the tokenizer (oversampling, language drops) rather than the tokenizer reshaped to fit the corpus.

### 5.4 The faculty-boundary-placement question is corpus-determined

If the corpus shows the structural property "high MI within domain A, low MI between A and any other domain" — i.e., one or more domains are structurally isolated — then those domains are natural faculty boundaries. The architectural lane is currently arguing about faculty placement in the abstract; the corpus would tell it where the natural cleavage lines are.

The blueprint's domain mix (CS 15%, math 12%, physics 12%, bio/chem 12%, music 12%, philosophy 10%, linguistics 10%, code 10%, replay 7%) is a *target*, not a measurement. The measured structure could be entirely different — for example, "code" and "math" may share enough symbolic structure to act as one faculty; "philosophy" and "linguistics" may be near-indistinguishable in representation space; "music" may stand entirely alone. The faculty count and placement are corpus-empirical questions that the wave-1 architectural debate has been treating as design choices.

### 5.5 The base-checkpoint-assumption falsifier

The PRD assumes Qwen2.5-1.5B and SmolLM3-3B as the base candidates. Properties that, if measured on the actual corpus, would falsify this base assumption:

1. **Dominantly low-resource language content**: if >40% of the actual corpus is in languages where the base tokenizer fertility is above 2.5x and oversample/extension is not viable, the base is wrong. The current language mix targets cap low-resource African content at 7% (sw 4% + zu 3%, with zu dropped — so 4%), so this is unlikely to fire as specified. But: if the operator's actual interests include heavy isiZulu content (the language being explicitly named suggests so), and the target distribution is shifted toward 20%+ Zulu, the base assumption breaks.

2. **Dominantly domain-specific notation outside base coverage**: e.g., a Polymath corpus where the music domain is dominated by Standard Music Notation rendered as text, or the math domain is dominated by LaTeX that the base tokenizer fragments aggressively, or chemistry is dominated by SMILES strings. The base assumption assumes natural-language-prose-typical token distributions.

3. **Modality content beyond text**: if the corpus is intended to include audio (music technology domain, per PRD) or image content, neither Qwen2.5-1.5B nor SmolLM3-3B is the appropriate base. The blueprint Part VIII Phase 3 ("multimodal bridge") defers this, but the corpus design has not yet been split into a text-only first slice with a multimodal second slice.

4. **Corpus dominated by long-form content > base context**: if the corpus is dominantly book-length texts where the long-range structure is the load-bearing learning signal, both candidate bases (Qwen2.5 32k native; SmolLM3 64k native) are workable but the training plan's 512-token sequences (PRD line 596) cannot exploit the structure. The base choice doesn't break — the *training-sequence-length choice* breaks. The corpus shows this.

5. **Corpus where novel-structure density is low**: if the corpus turns out to be dominantly content the base already saw, ELO Stage 1 is teaching style (which is the blueprint's risk-register entry, PRD line 297 — `method_disagreement_high`) and the entire CPT-vs-LoRA debate inverts.

None of these falsifiers can fire until the corpus exists as a measurable object. The "Qwen2.5-1.5B / SmolLM3-3B" base assumption is therefore currently held against zero corpus evidence.

### 5.6 The substrate-vs-corpus separation

The architectural lane's pivot toward small-active MoE on heterogeneous SoC (per HETEROGENEOUS-SOC-RESEARCH-DIALOGUE.md and architecture-models.md) is justified by **substrate properties** — 24GB RAM, NPU compiled-island shape, GPU as plastic surface, thermal envelope. The pivot is not justified by **corpus properties**.

These are two independent justification axes. The substrate axis says "the phone wants modular execution"; the corpus axis says "the data wants modular representation" — or does not. Both must say the same thing for an MoE/faculty architecture to be defensible on both axes. Currently only the substrate axis has been argued; the corpus axis is unmeasured.

If the substrate wants modular execution but the corpus is structurally homogeneous, the resulting architecture is a substrate-driven choice imposed on data that does not benefit from it. That can still work (the substrate constraint is real), but it should be named as a substrate-driven choice, not as a corpus-validated one. The wave-1 dialogue blurs this; the corpus measurement separates it.

---

## 6. Open questions for the operator

These are questions only the operator can resolve. Not engineering or science decisions; identity decisions about what Polymath is.

1. **Is "Polymath" a thing the operator wants to learn from, or a thing the operator wants the model to know?** These produce different corpora. The first emphasizes breadth and discovery; the second emphasizes the operator's existing knowledge and reference texts. The blueprint and PRD use "Polymath" interchangeably for both.

2. **Does the operator have a specific source list in mind?** Personal book library? A working set of papers? A reference set of music-theory texts? The CORPUS-SPEC names public-domain Gutenberg and music-theory texts but leaves "scholarly texts" undefined. If the operator has a real source set, the corpus characterization should be done against *that*, not against a public-domain probe.

3. **Is multilingual breadth a goal or a constraint?** The PRD targets 16 languages with English at 30%. If the operator works primarily in English with secondary use of two or three other languages, the 16-language target is over-broad — and the architectural choices made to support 16 languages (vocab size, fertility constraint, balanced sampling) are over-constraints. If the operator genuinely wants the model to operate in all 16, the target is correct but the corpus engineering required to source license-clean text in zu/sw/af/la/el at meaningful scale is substantial.

4. **Is the multi-domain breadth a goal of the corpus, or an aesthetic choice?** "Polymath" as a name implies breadth. The PRD operationalizes this as the nine-domain mix. If the operator's actual use case is dominated by one or two domains (music + audio + signal processing, for example, given the Phase 3 framing), the 12% music share is a tail, and the cross-domain MI structure becomes much less load-bearing for architecture.

5. **What is the test the operator wants the trained model to pass?** Without this, the corpus cannot be sized or scoped. The PRD names "research-publishable evidence" as the success signal (PRD line 19) and lists evaluation metrics (line 794 onward), but the metrics are means, not ends. What does success look like in the operator's hands?

6. **Are there sources the operator considers in-scope that fall into license class C, D, or E?** The corpus is currently bounded to A/B only. If the operator's intended source set includes copyrighted material the operator owns (legally distinct from copyright violation; ownership grants training rights), the license-class scheme needs an extension. The PRD's binary "A/B yes, C/D/E no" cannot represent operator-owned licensed content.

7. **Is OCR a planned pipeline step, or are sources expected to be pre-digitized?** The PRD specifies OCR provenance fields. If no scanned material is in the source set, the OCR pipeline is unused infrastructure. If scanned material is expected, the OCR damage profile (§3.8) is a load-bearing measurement that has not started.

8. **What is the realistic time horizon between corpus construction and Phase 1A?** If the answer is "weeks", the probe-corpus + measurement work in §3–§4 is the right path. If the answer is "months" with significant per-source license attestation work, the architectural lane's current model-selection debate is premature regardless of which model wins.

---

## 7. Tensions surfaced, not resolved

For the synthesis that follows this wave:

- **Substrate axis vs corpus axis** (§5.6): the architectural pivot toward MoE/faculty is currently substrate-justified only. Resolution requires corpus measurement.

- **Target distribution vs realized distribution**: the PRD's domain and language mix targets (§1.1) are specifications of intent. The realized distribution after license filtering, dedup, OCR damage, and fertility-driven exclusion may diverge substantially. Architectural choices made against the target may be invalid against the realized.

- **Probe corpus vs actual corpus**: §3–§4 measurements can begin today on a probe corpus. Every such measurement is a falsifiable prediction about the actual corpus. Resolution requires the operator to confirm structural similarity, or to provide actual sources.

- **Tokenizer-driven exclusion (zu, el) vs corpus integrity**: D-017 drops Zulu and Greek to fit the existing tokenizer. If the corpus is reshaped to fit the model rather than the model reshaped to fit the corpus, the corpus is no longer an independent object. The current direction may be correct but is corpus-modifying.

- **Curated-density premium vs measurement**: the blueprint argues curation justifies smaller token budgets. The premium is unmeasured. The architectural choices that depend on it (smaller scale, ELO viability over QLoRA, the entire "the corpus is the moat" thesis) are held against an unmeasured assumption.

- **CPT-vs-LoRA collapse risk**: if measurement reveals the corpus contains low novel-structure relative to the base, ELO Stage 1 is teaching style not knowledge — and the falsifier `method_disagreement_high` is the right falsifier but cannot fire until measurement exists.

- **"Faculty" as metaphor vs as architectural primitive**: the wave-1 dialogue treats faculties as a metaphor that translates to MoE/adapters. The corpus may or may not contain structure that justifies this translation. Both readings are currently live.

These tensions are inputs to the synthesis wave that follows. They are not for this document to resolve.

---

## 8. Sources

**Project artifacts (read in full for this document)**:
- `/Users/Zer0pa/Polymat AI/Polymath-AI/RESISTANCE-V2.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/PRD.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/MODUS-OPERANDI.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/docs/CORPUS-SPEC.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/docs/HETEROGENEOUS-SOC-RESEARCH-DIALOGUE.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/docs/FRESH-CONTEXT-HANDOVER-SOC-ARCHITECTURE.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/source-briefs/01-on-device-training-blueprint.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/synthesis/01-fresh-eyes-on-polymath-blueprint.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/polymath_ai/corpus/manifest.py`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/polymath_ai/corpus/fertility.py`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/docs/DECISIONS.md` (D-002, D-009, D-014, D-016, D-017 read in depth)
- `/Users/Zer0pa/Polymat AI/Polymath-AI/runtime/reports/fertility/Qwen_Qwen2.5-1.5B/2026-05-01T125835Z/fertility.md`
- `/Users/Zer0pa/Polymat AI/Polymath-AI/docs/research/soc-architecture-2026-05-16/architecture-models.md` (style reference)

**External primary references (anchors for the measurement methods)**:
- FLORES-200 (license CC-BY-SA-4.0, parallel multilingual benchmark): https://huggingface.co/datasets/openlanguagedata/flores_plus
- The Pile (per-source token statistics methodology): https://arxiv.org/abs/2101.00027
- RedPajama-Data v2 (dedup methodology and per-source statistics): https://www.together.ai/blog/redpajama-data-v2
- CulturaX (multilingual per-language cleaning): https://arxiv.org/abs/2309.09400
- FineWeb / FineWeb-Edu (factual-density curation): https://arxiv.org/abs/2406.17557
- Dolma (per-source license decomposition): https://arxiv.org/abs/2402.00159
- Llama 3 paper (n-gram contamination methodology): https://arxiv.org/abs/2407.21783
- Gamayun (cited in blueprint §4.1, multilingual curriculum at 2.5T): arXiv:2512.21580
- Model-based multilingual data selection (cited in blueprint §4.1, 15% tokens match baseline): arXiv:2502.10361
- arXiv per-paper license metadata via OAI-PMH: https://info.arxiv.org/help/oa/index.html
- Project Gutenberg PD corpus: https://www.gutenberg.org/
- The Stack v2 (permissive code subset): https://huggingface.co/datasets/bigcode/the-stack-v2
- OSCAR (CC-filtered subset): https://oscar-project.org/
- intfloat/multilingual-e5-small (proposed embedding for §3.1): https://huggingface.co/intfloat/multilingual-e5-small
- LaBSE (proposed embedding for §3.6 cross-lingual overlap): https://huggingface.co/sentence-transformers/LaBSE
- MinHash dedup reference (datasketch): https://ekzhu.github.io/datasketch/lsh.html

---

## Resistance V2 reminder applied

This document does not recommend a model. Does not recommend a training method. Does not produce a Path A/B/C structure. Does not contain "the next step is" or "the recommended action is" framing. Does name unresolved tensions, measurable properties, and the line between assumable and unknown.

The architectural question remains open. The corpus question has been sharpened from "the corpus is unspecified" to a specification of (a) what minimum properties the corpus must have to function as architectural input, (b) what those properties imply conditionally for the architecture, (c) what measurement work can begin today on a probe corpus, and (d) what only the operator can resolve.

The next synthesis wave reads this document and the wave-1 architectural artifacts together. Its job is to surface where the substrate axis and the corpus axis agree, where they disagree, and what measurement would resolve the disagreements.
