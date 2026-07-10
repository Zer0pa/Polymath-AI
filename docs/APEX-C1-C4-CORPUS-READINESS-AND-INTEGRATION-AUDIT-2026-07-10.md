# Apex C1–C4 Corpus Readiness and Integration Audit

Document class: CANONICAL_SUPPORTING_AUDIT  
Version: 2.0  
Date: 2026-07-11  
Target model: Gemma 4 E4B only  
Corpus state: PHYSICALLY_VALID_EVIDENCE_ONLY__LEARNING_AND_AUTHORITY_BLOCKED  
Execution authorized by this document: false  
Promotion authorized by this document: false  

Canonical consumers:

- `PRD-GEMMA4-E4B-PHONE-NATIVE-QNN-LEARNING-CELL-2026-07-10.md`
- `APEX-CURRENT-REALITY-CAPSULE-GEMMA4-E4B-QNN-CELL-2026-07-10.yaml`
- workspace-root `Polymath AI - Mobile-Native Gemma 4 E4B Heterogeneous Learning - Living Engineering Concept.md`

Typed aggregate evidence receipt:

- `APEX-C1-C4-CORPUS-READINESS-EVIDENCE-RECEIPT-2026-07-10.json`, SHA-256
  `7dbcfbc5e2dae3b93e117d1753cceb7220c8cd4909faa7726872efc21e021f39`.

---

## 1. Executive verdict

The corpus exists, resolves at an immutable private Hugging Face revision, and
is physically intact. All five phase manifests and all train, validation and
test QA shards pass their recorded hash, byte, row-count and parse checks.
The current 77,023-row artifact is therefore valuable evidence and must not be
deleted, silently repaired or relabeled.

It is not yet an admissible learning or evaluation authority.

Four independent defects govern that conclusion:

1. C3 and C4 were split by phase-specific record IDs rather than one global
   source identity. C4 is mostly a second view of C3 source material, so the
   current validation/test boundary leaks across phases.
2. C1 and C2 promoted material which their own semantic judges marked for
   repair or rejection. Their structural quality score is not a semantic
   correctness result.
3. Provider/model-output rights for the GPT-5.5-generated C1/C2 material are
   not established by the corpus package. Current provider terms make this a
   fail-closed admission question, not a presumed commercial-safe result.
4. No frozen Gemma 4 E4B target packets, answer masks, context-bucket
   decisions or truncation receipts exist yet. The current runtime bridge
   reduces rich master records to question/answer and leaves much of the
   intended curriculum graph unused.

The right response is not to abandon C1–C4. It is to preserve the current
revision as physical evidence, add a content-addressed global split and
quality-admission overlay, compile E4B-native material views, and admit only a
new root that binds all of them.

Until that root passes `CUR-0`:

- synthetic fixtures remain valid only for mechanical invariants;
- frozen train-only rows may be used as explicitly non-authority real-data
  packet/mechanism probes where their source and terms disposition permits;
- the already-inspected current validation/test split is permanently
  non-authoritative and audit-only; successor validation/hidden groups are
  sealed from graph/material design, basis, epsilon, optimizer, early stop and
  promotion immediately after deterministic connected assignment;
- no cumulative C5 result may be called independent held-out authority.

---

## 2. Immutable material identity

The governing physical source is:

```text
hf://datasets/Zer0pa/polymat-gemmalit-c1-c4-commercial-corpus
@504dd91c5a7c8365882d690d52f3de20697c4f7b
```

Repository visibility is private. A revision-pinned read-only audit resolved
146 repository objects and approximately 878 MB of stored material.

The local Mac package/state copies were intentionally offloaded during the
2026-07-09 disk emergency. Their absence from the Mac is not corpus loss and
must not trigger an unplanned duplicate download. The offload receipt points
to the phone-owned path under:

```text
/data/data/com.termux/files/home/polymath_mac_offload/
20260709T_disk_emergency/Polymat_AI/
```

The local offload notices are:

- `corpus_packages/OFFLOADED_TO_PHONE_20260709.md`, SHA-256
  `058ebf3bff67691abcf1fe203fcb091cca23fc56477125907eaa0223a038ef17`;
- `corpus_state/OFFLOADED_TO_PHONE_20260709.md`, SHA-256
  `242ab95b662b057bf3823129a5a3ee53f2d8cf05a8c26c8d4b8363cee0b27350`.

This audit used a revision-pinned read-only temporary Mac download, persisted
aggregate metadata only, and deleted all temporary corpus/tokenizer
directories after verification. It did not live-revalidate the phone's
offloaded contents.

### 2.1 Physical integrity

| Stage | Rows | Train / validation / test | Full QA SHA-256 | Build-manifest SHA-256 |
|---|---:|---:|---|---|
| C1 | 5,180 | 4,931 / 196 / 53 | `a752cafde223b0203be9478c3f28cf672d2ba0962394377f61a926da771c8088` | `7349512beadd2da2f678c3229425fc291576912f274450f3186f8c695fe8e305` |
| C2 | 3,198 | 3,042 / 129 / 27 | `676d985fff59d4a60c36d3e5142ac679a45db6082003fe98fa440b8cdbc517a3` | `3ed5a4d0190911744716f7e294a59271b54b319c0d80bab67f9cca3a1dbdeaee` |
| C2.5 | 20 | 19 / 1 / 0 | `ec5a85f111ba42bf778fffd98212f3f92ec871e9eb0a757196393cef99d2ba83` | `b1b7ed6f03cc2da281959c87dfa6ffb84cddfb23805e76c3682fc916a6284316` |
| C3 | 56,138 | 53,379 / 2,211 / 548 | `c6c3e98ebd1c583fc92588160922aad758af6a0d56c75ca7fb6cd8c7d0d1a87a` | `f95b1569f01b8c541d0cbe1c359d81dcbe8d1b036d9ddc6838780cdf1ae215be` |
| C4 | 12,487 | 11,883 / 492 / 112 | `0bfe358075383a74dbd0b6cf763e2ea5d5407ce3e3a894cccea4b67f41dcdcc6` | `451b879c2ab4df71db2b11da7868fb0a71664a09b35b8f7d73aec56dea5bf490` |

Independent checks passed for all 20 manifest/shard targets and all 77,023
rows: JSON parsing, required fields, stage/split labels, recorded counts,
full/split unions and record-ID uniqueness.

Local evidence anchors:

- `runtime/reports/orchestration/material_revision_lock.json`, SHA-256
  `078a9a208fb6fae06db64b5306cd4069912af867062a6689ecc0340de2be2edc`;
- `runtime/reports/integrated_c1_c4_execution/c1_c4_integrated_20260630T164809Z/material_verification.json`,
  SHA-256
  `871a9c4b2b7d05148ef12be55172a70e1bc1185bb114db07ce64013dad1396bb`.

The existing builder suite also passes 30/30 focused tests under Python
3.11.14 and pytest 9.1.1. The output receipt is
`APEX-C1-C4-CORPUS-BUILDER-TEST-RECEIPT-2026-07-10.json`, SHA-256
`1baecb6060206d7d09c583377ab3bb33b0769a3790fb0bd3ccd0f571ecf519c7`.
That confirms its current deterministic mechanics; it does not repair what
those tests omit:
global source grouping, provider/source-rights admission, semantic-quality
quarantine and target-E4B material compilation.

That is a physical-integrity pass only. It does not prove semantic quality,
source-group independence, licensing, target packetization or learning value.

### 2.2 Identity corrections

- The canonical revision is `504dd91c...`. A historical report containing
  `504dd91b...` is a typo or different identity and must never be merged with
  the verified root.
- The material lock's old prose blocker referring to `main` is stale. Its
  status and later material-verification evidence bind the immutable revision.
  The historical lock remains immutable rather than being cosmetically edited.
- C3 is not one-source SciInstruct material. Its promoted composition is
  42,173 SciInstruct, 8,960 QASC and 5,005 OpenStax rows. Prefix-only metadata
  inspection concealed that distribution.
- C4 is QASC/OpenStax material. Historical OpenMath, MegaScience or
  TextbookReasoning C4 candidates are not the target corpus.

---

## 3. Target curriculum versus current physical artifact

The user-restated target semantics are sovereign. They are not what the
current stage labels prove.

| Stage | Sovereign target | Current evidence-backed role | Verdict |
|---|---|---|---|
| C1 | lexical self-expansion: known vocabulary explains/expands itself | roots, definitions, semantic neighbors, register and word-family material | useful source pool; ordered closure unproved |
| C2 | new vocabulary defined only by admitted known vocabulary | technical definitions and related material | target identity unproved; no per-definition closure certificates |
| C2.5 / B23 | familiar-language-to-science bridge | 20 anchor-to-science-term links | congruent sentinel/canary, not authority phase |
| C3 | science dictionary resolving through C1/C2/B23 closure | long-form science QA/reasoning/application | target identity falsified; cannot be relabeled |
| C4 | prerequisite-ordered science syllabus comparable in quality to MegaScience | shorter evidence/reasoning/term/unit views over mostly C3 sources | target identity falsified; not a syllabus or independent authority |
| C5 | globally heldout evaluation | current cumulative/test surfaces are exposed | invalid as authority; rebuild required |

C2.5 is a bridge artifact, not a statistically meaningful fifth training
phase. Nineteen train rows, one validation row and no test row cannot support
an independent phase authority. All 20 bridge terms occur in C3, so the
artifact remains useful as a frozen transition sentinel.

The word *fractal* is currently a useful hypothesis: lexical elements recur
inside terms and terms recur inside scientific explanations. It is not yet a
measured curriculum graph. The corpus has no admitted sense-level
lexeme/concept dependency topology, frozen seed/base-vocabulary policy,
topological order, closure certificate, no-forward-reference proof,
connectivity/recurrence metric or syllabus prerequisite root.

Vocabulary closure is semantic, not token-level. Gemma can tokenize an
unknown word into subwords without the definition being comprehensible from
known vocabulary. C2 therefore requires normalized lexeme/concept IDs and an
explicit allowed function-word/base-vocabulary policy.

The current runtime QA bridge compounds that gap. It emits question/answer
while dropping much of the master-row structure—relations, bridges, examples,
evidence, reasoning steps and unit metadata. A curriculum can be richly
structured in storage while becoming flat at the learning boundary.

Therefore the admitted status is:

```yaml
curriculum_relationship:
  state: implicit_progression_hypothesis
  explicit_graph_authority: false
  C2_5_disposition: retained_bridge_B23
  current_C3_disposition: science_reasoning_source_pool_not_target_dictionary
  current_C4_disposition: paired_refinement_view_not_target_syllabus
  required_successor: content_addressed_C1_C2_closure_C3_dictionary_C4_syllabus_root
```

---

## 4. Falsifiers and blockers

### 4.1 Global source leakage

The builder derives `record_id` from stage and transformed content, then
derives split from that record ID. The same source item transformed in C3 and
C4 therefore receives a different record ID and may enter a different split.
The QA bridge then drops `source_local_id`, making the error harder to see.

The implementation points are concrete:

- `corpus_pipeline/records.py::stable_record_id` includes corpus phase and
  transformed question/answer/template identity;
- `corpus_pipeline/packager.py::assign_split` hashes that phase-specific ID;
- the QA bridge omits the source-local grouping key;
- existing split validators consequently prove record-ID non-overlap rather
  than source-group independence.

The source-level audit found:

- 12,387 of 12,487 C4 rows, or 99.199%, share the same
  `(source, source_local_id)` with a C3 row;
- all 112 current C4 test rows were semantically exposed in C3: 111 share the
  same `(source, source_local_id)` and the remaining QASC row has a
  near-equivalent question/answer concept in C3 train under a different source
  ID; the source-ID membership counts are 99 train-only, 11 validation-only,
  one in both and one source-unmatched/semantic-near-match;
- 3,421 exact question-answer pairs recur across C3 and C4;
- within-stage source grouping also crosses splits: 49 C3 source groups and
  33 C4 source groups span more than one split;
- exact-question duplication is also substantial, so statistical clustering
  by row ID would understate dependence.

The current C4 test and cumulative C5 surface therefore cannot measure
generalization after sequential C1→C4 learning. Passing a record-ID overlap
check does not repair source or semantic leakage.

One provenance hash is not sufficient because two provider IDs can carry the
same semantic item. The repair uses three identities:

```text
source_instance_id = SHA256(dataset_id || dataset_revision || source_local_id)
semantic_cluster_id = exact_and_near_content_cluster(normalized_material)
split_group_id = content_hash(
  connected_component(source_instance_edges UNION semantic_cluster_edges)
)
```

Every view and every stage occurrence in one connected `split_group_id`
receives one globally frozen split. Split assignment and confidence intervals
use that group, not the transformed row ID or either constituent identity
alone.

Semantic edges must use a frozen high-precision joint question/material
predicate, never answer-only similarity. CUR-0S reports component-size
distribution, maximum component and giant-component share against
predeclared anti-percolation thresholds. Chaining collapse—especially among
short C1/C2 definitions—is a hard failure, not aggressive deduplication.

### 4.2 C1/C2 semantic admission failure

C1/C2 were promoted from structural and vocabulary-anatomy checks despite
their own sampled semantic-judge results.

The stored C1 evidence is internally inconsistent: 500 explicit row verdicts
sum to 127 promote, 294 repair and 79 reject, while an aggregate summary
claims 517 verdicts with 130 promote, 302 repair and 85 reject. Both readings
contradict blanket promotion. C2 records 116 promote, 196 repair and 21 reject
among 333 judged rows, yet all remain admitted.

Rows marked repair/reject, suspicious tokenizer fragments and high
artifact-risk records were never quarantined. A deterministic row-shape pass
was labeled like a semantic DeepEval result even though it did not establish
factual correctness or training usefulness.

Required disposition:

- reject rows are excluded;
- repair rows are repaired and independently rejudged;
- unjudged generated enrichment does not inherit blanket semantic approval;
- quality scores are recomputed from evidence, never accepted because a
  generated record already contains a high value;
- the immutable current revision is preserved; all changes form a successor
  quality overlay or new material root.

### 4.3 Provider and source-rights admission

C1/C2 metadata says the content was generated through `openai/gpt-5.5` using
OpenRouter. OpenRouter's current terms make model-specific output rights
dependent on the applicable model terms. Current OpenAI consumer and service
terms restrict using output to develop competing AI models. Because the
corpus package does not preserve an applicable June 2026 terms snapshot,
separate permission or a legal determination, the label `commercial-safe`
does not establish training rights for C1/C2. This is a provider-terms
admission blocker, not a final legal conclusion.

Primary references:

- [OpenRouter Terms of Service](https://openrouter.ai/terms)
- [OpenAI Terms of Use](https://openai.com/policies/terms-of-use/)
- [OpenAI Services Agreement](https://openai.com/policies/services-agreement/)

C2.5 is different: 15 rows are Gemma-4-31B generated and five are manual.
Gemma's terms explicitly address model derivatives trained on output and
state that Google claims no rights in generated output, subject to the user's
other obligations. C2.5 still requires row-level provenance, but it is not
silently assigned C1/C2's provider problem. See the
[Gemma Terms of Use](https://ai.google.dev/gemma/terms).

Source-dataset dispositions also require precision:

- QASC's official dataset card declares CC BY 4.0 and is the strongest
  provisional real-data source: [AllenAI QASC](https://huggingface.co/datasets/allenai/qasc).
- SciInstruct's dataset card has weak underlying-source documentation despite
  a CC BY 4.0 tag; upstream provenance must be established or the source
  replaced: [SciInstruct](https://huggingface.co/datasets/zd21/SciInstruct).
- The OpenStax material comes from a 2024 derivative snapshot tagged CC BY,
  while OpenStax changed licensing for newly released or updated content in
  2026. Prior derivatives may retain prior terms, but this package lacks
  per-book edition/version lineage. Obtain edition-level attestation before
  commercial admission. See [OpenStax licensing update](https://openstax.org/blog/openstax-licensing),
  [license](https://openstax.org/license/) and [terms](https://openstax.org/tos/).

### 4.4 C3/C4 content limitations

- C3 is the dominant long-form phase and presently lacks the proposed
  structured evidence/reasoning/failure-mode/unit fields on its runtime QA
  surface.
- C4's numeric verifier never programmatically recomputed a quantitative
  answer; every source row was structurally checked only. The current report
  cannot be treated as numerical-correctness authority.
- A prior pattern screen flagged C3/C4 rows that may refer to absent figures,
  images or tables, but its detector rule and row-ID manifest were not
  preserved. The counts are not admitted typed evidence. Rerun a
  content-addressed detector and quarantine every confirmed row before
  text-only admission.
- C4's current risk scan sampled a prefix rather than the full corpus.
- C4 remains useful as a paired evidence-structured view of C3 sources, but
  not as an independent novelty/test distribution.

---

## 5. Exact Gemma 4 E4B geometry of the current drifted artifact

A revision-pinned audit used the current observed E4B-it tokenizer/template
surface. These revisions are observations made on 2026-07-10, not the future
L0 authority freeze:

| Artifact | Observed revision |
|---|---|
| `google/gemma-4-E4B-it` | `a4c2d58be94dda072b918d9db64ee85c8ed34e3f` |
| `google/gemma-4-E4B-it-qat-mobile-transformers` | `9a78a5adac7bca7a9e421634e4b58f41ca7cbca3` |
| `google/gemma-4-E4B-it-qat-mobile-ct` | `d35137f462eb09dbe5acb5924018356d8e057134` |

All three tokenizer JSON files were byte-identical with SHA-256
`cc8d3a0ce36466ccc1278bf987df5f71db1719b9ca6b4118264f45cb627bfe0f`.
All three chat templates were byte-identical with SHA-256
`2f1b4d75d067bae3fe44e676721c7f077d243bc007156cb9c2f8b5836613d082`.
Their `tokenizer_config.json` byte hashes differ because of key ordering in a
response-schema object; semantic equivalence does not permit a future byte
identity claim. L0 still freezes exact files.

The verified supervised serialization is:

```text
<bos><|turn>user\nQUESTION<turn|>\n<|turn>model\nANSWER<turn|>\n
```

The prompt is an exact token prefix. The scored span is the assistant answer
plus its `<turn|>` termination. All 77,023 current rows produced a nonempty,
recoverable scored span under this observed packetization.

These measurements do not freeze successor geometry. Target C3 changes from
long QA/reasoning to a science dictionary and target C4 changes from paired
short refinement to a science syllabus. CUR-0P must recompute lengths,
scored-token counts and natural-bucket coverage after the semantic rebuild.
The table below is a hardware-capacity prior only.

### 5.1 Full-packet token lengths

| Stage | p50 | p95 | p99 | Maximum | Natural bucket coverage |
|---|---:|---:|---:|---:|---|
| C1 | 52 | — | 60 | 66 | 100% ≤128 |
| C2 | 57 | — | 66 | 77 | 100% ≤128 |
| C2.5 | 80 | — | 103 | 103 | 100% ≤128 |
| C3 | 510 | 1,107 | 1,341 | 2,193 | 20.583% ≤128; 50.390% ≤512; 92.930% ≤1,024; 99.995% ≤2,048; 100% ≤4,096 |
| C4 | 109 | 239 | 424 | 1,420 | 77.993% ≤128; 95.932% ≤256; 99.487% ≤512; 100% ≤2,048 |

No complete real row fits sequence 16, so 16 remains synthetic mechanism
only. Real diagnostics need not wait for 128: C1 p99=60 proves at least 99%
fits a candidate 64-token bucket, and C2 p50=57 proves at least half fits.
Exact 32/64 coverage was not persisted and must be computed in CUR-0P before
admission. Sequence 128 is the first measured bucket with full C1/C2/B23
coverage, not the first possible real-data rung. Hardware bucket order need
not equal semantic stage order, and no answer may be truncated merely to fit
an already-built graph. Select pre-frozen rows that naturally fit the admitted
bucket and report exact coverage.

C3 currently supplies the strongest reason to treat context length as a graph family:
use 128/256/512 for bounded early diagnostics, then 1,024/2,048/4,096 for
meaningful coverage after memory and causal/KV fidelity pass.

---

## 6. Real-versus-synthetic fixture policy

Every packet has exactly one categorical fixture class.

### 6.1 `synthetic_mechanical`

Purpose:

- poison and overwrite detection;
- empty-mask and target-shift failure;
- overflow, underflow and NaN policy;
- padding and maximum-shape behavior;
- fence, copy, ownership and teardown;
- provider/fallback isolation;
- the sequence-16 graph/mechanism rung.

It can close only mechanical claims. Synthetic success never establishes
target semantics, corpus readiness, learning or authority.

### 6.2 `real_probe_non_authority`

CUR-PROBE-passed immutable train-only rows used before composite CUR-0. They
may support bounded mechanism, semantic-fidelity and science-diagnostic
claims, but no optimizer commit, heldout result or authority claim.

The candidate first lane is to build a QASC train subset assigned by the new
connected split-group rule, with missing-context rows excluded. Current C1/C2
use remains quarantined by terms/quality; C2.5 may serve as a bridge sentinel;
C3/C4 same-group pairs may serve as non-heldout multi-view diagnostics after
CUR-PROBE.

### 6.3 `real_target_diagnostic`

Deterministic, immutable train/development rows from admitted sources. These
are required wherever shape permits for packetization, reference/native
parity, alternating persistent calls, compact exact loss, mutation
discrimination and coefficient-signal diagnostics.

They exist only after composite CUR-0 and may close scoped semantic-fidelity
and science-diagnostic gates. They cannot close heldout authority alone.

### 6.4 `real_authority`

Globally split-grouped frozen heldout material plus independent target and
retention suites. It is unavailable to:

- graph/material design or admission;
- bucket selection;
- material-view design;
- basis/dimension choice;
- perturbation-scale choice;
- optimizer selection;
- early stopping or repair.

After the final candidate and protocol freeze, only the blinded evaluator may
feed this material through the already-admitted graph. The current corpus has
no admitted `real_authority` root.

### 6.5 Pairing rule

Real data should replace synthetic convenience, not synthetic adversaries.
Every gate that can accept natural packets uses both:

1. synthetic edge cases for the invariant; and
2. CUR-PROBE real probes before CUR-0 or frozen real target diagnostics after
   CUR-0 for the intended distribution.

If a real diagnostic is impossible for a shape, the exception and promotion
ceiling are recorded. Sequence 16 is the first justified exception.

---

## 7. Curriculum-native learning architecture

### 7.1 Do not let C3 erase the curriculum

Exact answer-masked target totals under the current observed E4B serialization
were:

| Stage | Scored target tokens | Share of naïve global target pool |
|---|---:|---:|
| C1 | 205,597 | 0.8682% |
| C2 | 131,809 | 0.5566% |
| C2.5 | 1,214 | 0.0051% |
| C3 | 22,613,947 | 95.4925% |
| C4 | 728,822 | 3.0776% |

A single all-target-token loss would make the curriculum approximately a C3
objective. Exact NLL remains token-weighted *within* each stage:

```text
L_s(theta) = sum(nll_sum_i for i in stage s)
             / sum(scored_token_count_i for i in stage s)
```

Across stages, preserve the vector and use predeclared weights or explicit
constraints:

```text
J(theta) = sum_s w_s * L_s(theta)

subject to:
  L_prior_s(theta_new) - L_prior_s(theta_checkpoint) <= tolerance_s
```

Across admitted authority stages, `w_s >= 0` and the weights sum to one.
`w_B23 = 0`; no other authority stage can be silently zero-weighted. The full
stage vector and each per-stage constraint remain sovereign over scalar J.

Every stage transition emits an immutable checkpoint. Optimizer replay draws
only from admitted prior-stage *train* groups under a frozen schedule.
Separate validation sentinels measure earlier-stage retention and never feed
an update. Hidden C5 is never replayed or used for early stopping. Worst
prior-stage validation regression is sovereign; a large C3 gain cannot
compensate lexical or retention failure.

### 7.2 C2.5 is a bridge, not a 65% sampling phase

Historical replay schedules assigned C2.5 a dominant share during its stage.
With 19 train rows that would repeatedly overfit the bridge. Treat B23 as:

- a graph-connectivity sentinel;
- a transition probe;
- `stage_weight: 0` in the learning objective;
- `authority_role: diagnostic_canary`;
- never an independently weighted authority phase.

Its single validation row cannot establish standalone retention or
generalization.

### 7.3 Coefficient conflict matrix

The 1–8 dimensional Lane-A control creates a hardware-native way to test the
fractal hypothesis rather than merely narrate it.

For each admitted stage/view (s), estimate an exact-NLL finite-difference
fingerprint (g_s) on identical frozen packets. The NPU performs the
`theta+`/`theta-` forwards; the CPU aggregates exact stage losses and computes
the small cosine/conflict matrix:

```text
M[s,t] = dot(g_s, g_t) / (norm(g_s) * norm(g_t))
```

A zero-norm fingerprint is `no_detected_signal` and has no cosine; never
impute zero alignment or divide by zero. In one coefficient dimension the
comparison is signed agreement only, so retain magnitude and uncertainty and
make no multi-dimensional geometry claim.

Interpretation:

- aligned C1/C2/C3 directions support one shared compact control;
- C3/C4 same-source alignment supports a shared semantic refinement;
- C4-only improvement suggests format/evidence adaptation rather than new
  scientific capability;
- negative alignment identifies catastrophic interference or insufficient
  control capacity;
- basis growth or stage-segmented coefficients are earned only by that
  evidence.

The CPU may then solve a tiny trust-region or constrained update. This is an
engineering hypothesis, not a measured result, but it is congruent with the
forward-only NPU evaluator and avoids pretending that the NPU supplies
backpropagation.

### 7.4 C3/C4 paired views

Same-source C3/C4 pairs are invalid as independent heldout evidence but
valuable as developmental diagnostics:

- long/plain versus short/evidence-structured loss response;
- answer consistency across views;
- sensitivity to required terms, reasoning steps and units;
- retention of the source concept after format refinement.

They must share one `split_group_id`, one global split and one statistical
cluster. The scheduler may sample paired train views deliberately, but cannot
count them as independent examples or replay validation/hidden views.

---

## 8. CorpusMaterialCompiler contract

Add a deterministic `CorpusMaterialCompiler` between the immutable master
corpus and the target packetizer. It emits named, lineage-preserving views
instead of discarding the master structure.

Required view examples:

- C1: lexical atom, definition, semantic relation, word family, usage and
  closure expansion;
- C2: new-term definition, contrast, domain/register and collocation with
  known-vocabulary dependency set and closure certificate;
- B23: anchor-to-science bridge and reverse recall;
- C3: science-dictionary definition, relation, example, counterexample,
  evidence and prerequisite;
- C4: syllabus unit, lesson, worked example, exercise, assessment,
  remediation, recurrence and unit/numeric view only when source evidence is
  valid.

An intentional shortening or decomposition is a new named, content-addressed
view with parent lineage and independent semantic validation. Transport
truncation is always `none`.

The ABI has four layers:

1. `MaterialView`: semantic content, normalized lexeme/concept IDs,
   dependency/prerequisite edges, closure proof and full source lineage;
2. `E4BSequencePacket`: one exact L0-templated causal sequence with separately
   addressable input IDs, targets and shifted answer mask;
3. `BatchPlan`: ordered packet digests plus independent-row,
   explicitly-admitted block-diagonal or exact-continuation strategy;
4. `EpochTicket`: packet/batch identity joined to phone root, candidate,
   coefficient digest, antithetic sibling, stage objective and update frontier.

The semantic view binds:

```yaml
material_view_identity:
  corpus_family_and_source_revision: required
  corpus_and_successor_root_sha256: required
  quality_rights_and_global_split_overlay_sha256: required
  vocabulary_seed_and_base_policy_sha256: required
  dependency_or_prerequisite_DAG_sha256: required
  stage_and_named_view: required
  master_source_semantic_and_split_group_ids: required
  normalized_lexeme_and_concept_ids: required
  dependency_set_and_closure_certificate: required
  topological_rank_and_cycle_disposition: required
  source_license_quality_and_context_disposition: required
  material_content_sha256: required
```

Each sequence packet binds:

```yaml
E4B_sequence_packet_identity:
  material_view_sha256: required
  corpus_stage_id:
    one_of: [C1, C2, B23, C3, C4]
  material_view_id: required
  master_record_id: required
  source_instance_id: required
  semantic_cluster_id: required
  split_group_id: required
  split:
    one_of: [train, validation, hidden_test]
  source_and_license_disposition: required
  fixture_and_access_class: required
  tokenizer_files_sha256: required
  chat_template_sha256: required
  termination_contract_sha256: required
  target_shift_contract_sha256: required
  input_ids_sha256: required
  position_ids_or_derivation_sha256: required
  attention_validity_or_mask_sha256: required
  target_ids_sha256: required
  answer_mask_sha256: required
  scored_token_count: required
  natural_fit_context_bucket: required
  truncation_disposition: none
  fixture_class:
    one_of:
      - synthetic_mechanical
      - real_probe_non_authority
      - real_target_diagnostic
      - real_authority
  packet_sha256: required
```

The logical packet digest is independent of file offset, shard and physical
alignment. Physical padding is initialized, poison-tested and excluded or
normalized in logical hashing. An SoA container may store
`input_ids[N,S]`, positions, attention validity, `target_ids[N,S]`, shifted
answer masks, lengths/counts and a row directory. Authority packets require a
positive scored-token count.

Candidate state never enters packet identity. Batching B, candidate count K
and async depth D remain separate axes. For B>1 or K>1, compact loss remains
attributable as `[candidate,row] nll_sum` and `scored_token_count`; otherwise
the invocation is restricted to one logical row.

Naive sequence concatenation is forbidden because E4B global-attention layers
allow cross-row contamination. Sequence packing requires exact block-diagonal
attention, position/RoPE reset, segmented KV and independent-run parity. A
curriculum composite is a new MaterialView, never a packing optimization.

PQA1/PJP1, FNV-1a64 record identity, fixed 128 slots, JL/polar fields and
`source_kind=0` are legacy import/diagnostic material. The old Phase 1/2 full
C1 contained 50,994 records; current immutable C1 contains 5,180. No old row,
split, packet or tokenizer readiness transfers. A JL or hidden sidecar binds
the exact source packet, graph cut, shape/dtype/strides, active/padded lengths,
projection and packing identity, and can never become source truth.

The CPU compiles/tokenizes once. The QNN hot path consumes immutable numeric
packets and never parses JSON or retokenizes. Every antithetic sibling receives
the same packet bytes and differs only in the declared coefficient state.

### 8.1 C4 commercial/research source separation

`C4-COM` is the sovereign commercial candidate. It admits only row-level
commercial-eligible sources, target syllabus semantics and the frozen quality
bar. `C4-RX` is a separate research-only lineage.

Current revision-pinned discovery facts:

| Candidate | Observed revision | Viewer rows | Card license | Disposition |
|---|---|---:|---|---|
| MegaScience/TextbookReasoning | `ca7ecbec76d01bff2e99f3dc17735b02f87d4e96` | 651,840 | CC-BY-NC-SA-4.0 | C4-RX/reference only |
| MegaScience/MegaScience | `8df5586005374acba25aecc4f5469ce30fec605c` | 1,253,230 | CC-BY-NC-SA-4.0 | C4-RX/reference only |
| nvidia/OpenScienceReasoning-2 | `174b02c9cdf231f220765b2a1d5ece4550921894` | Viewer partial at 307,862 observed rows; card states 1.6M | CC-BY-4.0 | commercial discovery candidate only |

None is admitted by this table. Card labels do not replace upstream rights,
row quality, contamination, target-semantic fitness, connected splitting or
authority construction. The NVIDIA candidate is synthetic science reasoning,
not a ready science dictionary/syllabus.

Source cards: [TextbookReasoning](https://huggingface.co/datasets/MegaScience/TextbookReasoning),
[MegaScience](https://huggingface.co/datasets/MegaScience/MegaScience), and
[OpenScienceReasoning-2](https://huggingface.co/datasets/nvidia/OpenScienceReasoning-2).

MegaScience comparability is a vector of hard minima: science/prerequisite
coverage, factual/reference correctness, evidence sufficiency, pedagogical
order, explanation depth, worked-example/exercise/assessment diversity,
numeric/unit recomputation, missing-context rate, recurrence/retention design,
duplication/source concentration and equal-budget development-heldout learning
value. Size cannot compensate a failed dimension.

C4-RX content, packets, checkpoints, reports and model derivatives never merge
with C4-COM. Large artifacts live on revision-pinned private Hugging Face or
phone storage. The Mac retains hashes, counts, schemas and aggregate receipts
only; a temporary bounded audit must preflight free space and delete verified
scratch.

---

## 9. CUR-0 acceptance gate

### 9.1 CUR-PROBE partial gate

`CUR-PROBE` permits a bounded real train-only diagnostic before full CUR-0.
It is not partial authority and cannot close a learning, heldout or promotion
gate.

Pass requires, for every included row:

- immutable source revision, row and packet hashes;
- admitted source/license/provider disposition for the diagnostic use;
- row-level semantic-quality and missing-context disposition;
- connected `split_group_id` computed against the full current source corpus,
  with the row assigned to train and no validation/test member exposed;
- an immutable target-E4B diagnostic tokenizer/template/termination revision,
  answer mask and natural-fit bucket recorded; if it predates L0 it has no
  transfer, and packets are regenerated under L0 before CUR-0P;
- `real_probe_non_authority` fixture class;
- an append-only exposure receipt that permanently excludes every exposed
  source-instance and semantic-cluster member from future validation, hidden
  C5 and real-authority roots; any successor component containing one remains
  train-only even if its membership or hash changes;
- no optimizer commit, early stopping, authority reuse or hidden-C5 access.

CUR-PROBE can support packetization, numerical parity, persistent execution,
exact-loss, mutation-discrimination and bounded coefficient-signal
diagnostics. It never implies CUR-0.

### 9.2 CUR-0 full gate

`CUR-0 — Curriculum identity and E4B material readiness` is composite.
`CUR-0S` source admission runs in parallel with L0. `CUR-0P` packet admission
joins CUR-0S to the L0-frozen tokenizer/template/termination contract.
Composite CUR-0 precedes all target-data learning or authority. Pure synthetic
compiler and lifecycle work may continue without it, with a mechanical-only
ceiling.

CUR-0 passes only when:

1. the five current manifests remain preserved as immutable evidence and the
   corrected successor root resolves at an immutable revision;
2. successor source-instance, semantic-cluster and connected split-group
   overlays assign every source/view to one split with zero
   train/validation/test leakage across stages;
3. exact and near-duplicate policy is frozen and independently audited,
   including joint-content semantic edges and anti-percolation component
   limits;
4. row-level source, transformation, provider/model and license provenance is
   admitted or quarantined;
5. C1/C2 rejects are excluded, repair rows are repaired/rejudged, C1 emits an
   admitted lexical self-expansion closure and every C2 definition has a
   machine-checkable known-vocabulary certificate;
6. C3 is compiled/admitted as a science dictionary resolving through prior
   closure, and C4 is compiled/admitted as a prerequisite-ordered science
   syllabus which passes the frozen vector-valued MegaScience-comparability
   bar;
7. the semantic root reports normalized lexeme/concept IDs, dependency and
   prerequisite edges, seed/base-vocabulary policy, topological order,
   cycle/SCC disposition, connectivity/recurrence and zero unresolved
   references;
8. missing visual/table context and unverified numeric/unit rows are excluded
   from incompatible text-only or quantitative views;
9. exact L0-frozen E4B-it/QAT tokenizer, template, termination and target-shift
   rules produce byte-stable packets with nonempty masks;
10. full length/coverage reports are recomputed for successor stages/views,
   with no silent answer
   truncation;
11. deterministic real diagnostic manifests exist for every admitted
   stage/view/bucket;
12. B23 is retained explicitly with `stage_weight: 0` and
    `authority_role: diagnostic_canary`, not silently treated as C2 or an
    authority phase;
13. C4-COM and any C4-RX roots, storage, packets, checkpoints and reports are
    categorically separated with no content leakage;
14. independent behavior and retention suites are frozen outside optimizer
    access; hidden C5 is never replayed, used for early stopping or unblinded
    before the final candidate/protocol freeze;
15. raw location, egress and deletion/custody policy passes.

CUR-0 outputs one immutable curriculum root. It is independent from the E4B
graph root; both are joined in packet, epoch-ticket, checkpoint and scientific
ledger identities. A corpus repair does not falsely change graph identity,
and a graph rebuild does not silently change curriculum identity.

---

## 10. Repair and admission plan

### 10.1 Preserve

- Freeze revision `504dd91c...` as `physically_valid_evidence_only`.
- Preserve all failures, judge reports, material locks and historical split
  receipts unchanged.
- Do not mutate the private repository in place.

### 10.2 Build overlays or a successor root

1. Recover full source lineage and compute `source_instance_id`,
   `semantic_cluster_id` and connected `split_group_id`.
2. Assign one global split by `split_group_id` across all stages/views.
3. Emit an exact overlap report with source, question, answer and near-duplicate
   units separated.
4. Quarantine C1/C2 pending provider-rights resolution; rebuild from Gemma,
   local/manual or otherwise permissive sources if permission is unavailable.
5. Repair/rejudge C1/C2 semantic failures.
6. Freeze normalized lexeme/sense/concept IDs and the seed/function-word/base
   policy; compile the C1/C2 dependency DAG, closure certificates, topological
   order and zero-unresolved-reference report.
7. Treat current C3/C4 as source pools only; build/admit a C3 science
   dictionary and a C4 prerequisite-ordered science syllabus.
8. Run a commercial-source tournament for C4-COM and freeze the
   MegaScience-comparability rubric before judging it.
9. Establish SciInstruct upstream provenance or replace it.
10. Bind OpenStax book, edition, snapshot revision and license.
11. Quarantine missing visual/table context.
12. Programmatically recompute quantitative answers and validate units before
   emitting numeric C4 views.
13. Compile four-layer E4B-native material, packet, batch and epoch identities;
   recompute all target-stage length geometry.
14. Freeze stage-balanced objective weights, transition constraints and
    earlier-stage retention sentinels.
15. Rebuild C5 from globally heldout groups; keep C5 evaluation-only.
16. If a commercial source cannot meet the frozen bar, instantiate C4-RX under
    a separate research lease and preserve permanent lineage isolation.

### 10.3 Immediate safe real-data lane

Before full repair, bounded non-authority work may use a CUR-PROBE candidate
only after that partial gate is actually built and passed:

- immutable train-only QASC rows with freshly computed connected split-group
  assignment;
- no missing figure/table context;
- natural fit in the target bucket;
- a frozen packet manifest and `real_probe_non_authority` label;
- no reuse for heldout authority.

A raw QASC QA row is sufficient for mechanics only. Semantic-fidelity
diagnostics for corrected C3/C4 require a small independently admitted
dictionary-entry or syllabus-unit MaterialView, and exposure permanently burns
its connected group from future authority.

Synthetic poison/shape fixtures remain paired with these rows. Current C1/C2
text does not enter learning while the provider/quality blockers remain.

---

## 11. Governing disposition

```yaml
corpus_readiness:
  immutable_physical_integrity:
    state: passed_scope
    scope: five_manifests_fifteen_QA_shards_77023_rows
  target_E4B_material_compilation:
    state: blocked_fail_closed
  target_curriculum_semantics:
    state: blocked_fail_closed
    reasons:
      - C1_lexical_closure_unproved
      - C2_known_vocabulary_definition_closure_unproved
      - current_C3_is_not_science_dictionary
      - current_C4_is_not_science_syllabus
      - MegaScience_comparability_not_instantiated
  current_split_generalization_authority:
    state: invalidated
    reason: global_source_group_leakage
  C1_C2_learning_admission:
    state: blocked_fail_closed
    reasons:
      - provider_model_output_terms_unresolved
      - semantic_repair_and_reject_rows_promoted
  C3_C4_learning_admission:
    state: blocked_fail_closed
    reasons:
      - source_group_resplit_required
      - provenance_and_content_quarantine_incomplete
      - successor_dictionary_and_syllabus_roots_absent
  C4_lineages:
    commercial_C4_COM: proposed_unbuilt
    research_C4_RX: optional_isolated_noncommercial
    cross_lineage_merge: forbidden
  bounded_real_probe_lane:
    state: proposed
    scope: source_admitted_globally_grouped_train_only_packets
    authority_ceiling: mechanism_and_science_diagnostic_only
  fractal_claim:
    state: design_hypothesis
    admitted_label: implicit_progression_hypothesis
    target_required_label: explicit_dependency_and_syllabus_DAG_after_CUR-0S
```

The corpus is in good enough shape to preserve, study and repair. It is not in
good enough shape to train the sovereign model or judge success without that
repair. That distinction is the basis for using more real data immediately
without converting contaminated or weakly admitted material into a false
authority result.

---

## 12. Version 2.0 correction record

Version 2.0 does not alter the version 1.0 physical measurements. It changes
their architectural interpretation after the target curriculum was restated:

- current C3/C4 are source/evidence pools, not the target science dictionary
  and syllabus;
- current token quantiles are capacity priors, not successor atlas authority;
- semantic vocabulary closure precedes Gemma tokenization;
- the material ABI is four-layer and PQA1/PJP1/JL are legacy;
- C4-COM and C4-RX are permanently separate;
- MegaScience is an operational quality reference and optional
  research-only corpus, never a commercial-root ingredient;
- large artifacts remain on Hugging Face or the phone rather than the Mac.
