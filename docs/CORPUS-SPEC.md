# Corpus Specification — Seed Corpus v0

**Boundary:** Research infrastructure for in silico on-device LLM training and multilingual / multi-domain knowledge model construction. Outputs are research artifacts - model checkpoints, training telemetry, evaluation reports, throughput measurements. No regulatory certification claims. No clinical or human-subject use. No surveillance, biometric profiling, or identity inference. No model weights distributed without explicit license attestation. No training on copyrighted material without explicit corpus-license decomposition. No deployment to production without a falsifier-traced acceptance gate.

## Scope

PRD §Seed Corpus v0 Specification: a conservative starting corpus, not the final Polymath knowledge universe. Operator engagement (HANDOFF-TO-OVERNIGHT-EXECUTOR §What You Inherit) selected the default Seed Corpus v0 path. Bulk corpus content lives on private Hugging Face under Architect-Prime; the repo carries manifests, license attestations, and tiny fixtures only.

## Stage targets

| Stage | Tokens | Purpose | Storage |
|---|---:|---|---|
| Smoke | 10K-100K | CI / Mac / device smoke | GitHub allowed if tiny + license-clean |
| Experiment 0 | 10M | Device stack + throughput | HF private dataset; manifest in GitHub |
| Phase 1A | 100M | First real ELO Stage 1 | HF private dataset (Architect-Prime) |
| Phase 1B | 500M | Curriculum + cross-lingual / domain | HF private dataset |
| Phase 2 | 1B | Publishable scale extension | HF private dataset |

## Domain mix (Phase 1A)

PRD-targeted shares; the executor may adjust ±5pp per domain if source availability and license decomposition demand it.

| Domain | Target share |
|---|---:|
| CS / ML / systems / mobile compute | 15% |
| Mathematics + formal reasoning | 12% |
| Physics + engineering | 12% |
| Biology / chemistry / materials / energy / synbio | 12% |
| Music technology / audio / signal processing | 12% |
| Philosophy / history of science / epistemology | 10% |
| Linguistics / language learning / translation | 10% |
| Code + technical documentation (permissive only) | 10% |
| General replay (catastrophic-forgetting mitigation) | 7% |

Codified at `polymath_ai/corpus/manifest.py:_DOMAIN_MIX_PHASE1A`.

## Language mix (Phase 1A)

Concrete per-language allocation — see Decision D-002. Group totals match PRD targets.

| Language | Code | Share |
|---|---|---:|
| English (anchor + replay + depth) | en | 30% |
| French | fr | 7% |
| Spanish | es | 6% |
| German | de | 6% |
| Italian | it | 3% |
| Portuguese | pt | 3% |
| Chinese | zh | 7% |
| Japanese | ja | 5% |
| Korean | ko | 3% |
| Arabic | ar | 5% |
| Russian | ru | 5% |
| Hindi | hi | 5% |
| Swahili | sw | 4% |
| isiZulu | zu | 3% |
| Afrikaans | af | 3% |
| Latin | la | 2.5% |
| Greek (Classical or Modern slice) | el | 2.5% |

Fertility correction overrides raw share (PRD §Language Mix). Any language above 2.5x English fertility triggers `tokenizer_fertility_high` and cannot enter Phase 1A.

## License classes

| Class | Meaning | Training | Redistribution |
|---|---|---|---|
| A | Public domain / CC0 | yes | yes (with manifest) |
| B | Permissive open license allowing ML training | yes | yes (preserve attribution) |
| C | Open access with attribution / share-alike / non-commercial | maybe (decision required) | per license |
| D | Ambiguous, web scrape, unclear copyright | NO | NO |
| E | Copyrighted commercial without permission | NO | NO |

Default training accepts A and B only. C requires an explicit `Decision` row in `docs/DECISIONS.md`. D and E are excluded from all training and redistribution.

## OCR provenance

For OCR-derived sources, each document records:
* original file hash
* scanner / source provenance
* OCR engine + version
* language model / OCR settings
* page-level confidence
* normalisation steps (header / footer removal, hyphenation, NFC)
* perplexity-damage score (`ocr_damage_score`)
* human or model repair notes

OCR-derived chunks above the damage threshold are excluded until repaired. Falsifier: `ocr_damage_high`.

## Source register (initial seed; expanded via curation runs)

Class A / B candidates. None of these enter training until a per-source license attestation row is added to the manifest. The executor maintains the actual register in the HF private dataset's `dataset_card.md`; what appears below is the on-repo skeleton.

| Source ID | Class | Languages | Domains | Notes |
|---|---|---|---|---|
| `gutenberg:public-domain` | A | en, fr, de, es, it, la, el | philosophy_history_epistemology, linguistics_language_translation | Project Gutenberg corpus, public-domain US works. Manifest pulls per-book metadata. |
| `wikipedia:cc-by-sa-3.0` | C | all | all | CC-BY-SA - share-alike contagious; isolate or exclude pending license decision. |
| `wikisource:public-domain` | A | en, fr, de, ru, ar, zh, ja, ko, hi, sw, zu, af | philosophy_history_epistemology, linguistics_language_translation | PD-only Wikisource subset. |
| `arxiv:cc-by-4.0` | B | en (mostly) | cs_ml_systems_mobile_compute, math_formal_reasoning, physics_engineering, biology_chemistry_materials_energy_synbio | arXiv CC-licensed papers only; full-corpus subset must be filtered by license metadata. |
| `flores-200` | B | many | linguistics_language_translation | CC-BY-SA-4.0; class C - decision row required. |
| `musictheory:public-domain` | A | en, de, fr, it | music_audio_signal_processing | Public-domain music theory texts (Kostka, etc., Gutenberg-hosted only). |
| `tatoeba:cc-by` | B | many | linguistics_language_translation | CC-BY-2.0 sentence pairs; license-checked subset. |
| `oscar:cc-clean` | C | many | general_replay | CC subset filtered for permissive license; class C and isolate. |
| `unicodebooks:public-domain` | A | la, el | philosophy_history_epistemology | Classical-language texts in PD. |

The above is intentionally a register of *candidate* sources. License-attestation must be explicit before any chunk enters Phase 1A training; falsifier `license_drift` blocks training otherwise.

## Manifest emission

Manifests are produced by `polymath_ai.corpus.manifest.build_manifest`. Every row carries the boundary envelope and SHA-256s every source list deterministically. Manifests are saved to `corpus/manifests/<stage>-<id>.json` and to the corresponding HF private dataset's `manifests/` directory.

## Tokenizer fertility audit (Phase 0F)

Implementation: `polymath_ai/corpus/fertility.py`. Runs as Experiment 1 once the phone is attached or when the operator consents to the bulk corpus on the host. Gate: every core target language at or below 2.5x English fertility. Failure response in `docs/DECISIONS.md` (vocabulary extension, sampling adjustment, model swap).

## Storage discipline

* Repo carries: manifests, license attestations, fixture samples (tiny, license-clean), this spec.
* HF private dataset carries: bulk shards under `Architect-Prime/polymath-corpus-seed-v0` (created at first real ingestion).
* Mac local: HF cache only; `~/.cache/huggingface/hub/`.
* Phone: ADB-pushed slice for current run; full corpus never persisted on the phone.
