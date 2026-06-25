# PRD Addendum: Polar Phase 1 QA Stream Engine, Zig-Primary

Date: 2026-06-25
Repository: `/Users/Zer0pa/Polymat AI/Polymath-AI`
Authority runtime: REDMAGIC NX789J / Snapdragon SM8750 / Termux on-device
Scope: Phase 1 only
Status: Supersedes the earlier Phase 1 dictionary/megascience split for the
next build agent

## 1. Governing Decision

Phase 1 is now a single QA-native ingestion and chopping engine.

Dictionary material and MegaScience material are not separate hot-path modes.
They are different upstream sources that must be normalized into one QA record
contract before tokenization.

```text
dictionary library -> QA record generator \
                                      -> Phase 1 QA Stream Engine
MegaScience text -> QA extractor      /
```

The engine emits a continuous variable-length numeric token stream plus exact
record and span metadata for Phase 2. Phase 1 must not seal 128-token packets,
perform JL projection, claim NPU/GPU execution, or claim learning.

## 2. Zig Policy

Zig is not optional theater. The next agent must determine now whether Zig can
own Phase 1 on the phone.

The Phase 1 target is:

- Zig-primary QA stream engine;
- C++ retained only as a reference/oracle/fallback after Zig has been honestly
  falsified;
- Rust/Hugging Face tokenizers used as parity oracle outside the hot path;
- Python allowed only for gate orchestration and report generation.

If Zig cannot build and run native Termux executables on the REDMAGIC phone,
that is a hard architecture blocker that must be reported with commands,
outputs, attempted repairs, and the exact reason C++ is required. Do not slide
silently into C++ and call the architecture complete.

Minimum Zig falsification loop:

1. `zig version`
2. `zig env`
3. `zig build-exe` native hello-world on phone
4. `zig test` on phone
5. `zig build` on phone
6. native Zig file I/O test over `/data/data/com.termux/files/home`
7. native Zig allocator discipline test proving explicit allocator ownership
8. native Zig QA token stream skeleton that writes and re-reads the binary
   stream format
9. if any item fails, try Termux package repair, libc/bionic configuration,
   `termux-chroot` where appropriate, and a minimal target override before
   declaring failure

The agent may keep a C++ tokenizer oracle because prior work proved a usable
Gemma BPE path. That does not satisfy the Zig requirement.

## 3. Canonical QA Input Contract

The hot engine consumes QA records. Dictionary and raw textbook parsing are
outside or upstream of the hot tokenizer loop.

Canonical evidence input may be JSONL. The final hot path must also support a
compact binary or line-indexed source form so that JSON parsing does not become
the permanent throughput boundary.

Required QA fields:

- `record_id`: stable string or hash;
- `source_kind`: `dictionary`, `megascience`, `synthetic_stress`, or
  `user_supplied`;
- `question`: UTF-8 question/prompt text;
- `answer`: UTF-8 answer/target text;
- `source_ref`: optional provenance string;
- `relation_type`: optional dictionary relation label, such as `synonym`,
  `definition`, `contrast`, `symbol`, or `referent`;
- `metadata`: optional object for non-hot-path details.

Dictionary examples:

```json
{"record_id":"dict:mass:synonym:inertia","source_kind":"dictionary","relation_type":"synonym","question":"What is a synonym for mass?","answer":"inertia"}
{"record_id":"dict:force:definition:push","source_kind":"dictionary","relation_type":"definition","question":"Define force.","answer":"push"}
```

MegaScience examples:

```json
{"record_id":"mega:physics:000001","source_kind":"megascience","question":"What is inertia?","answer":"Resistance to change in motion."}
```

## 4. Canonical Phase 1 Output Contract

Phase 1 must emit both:

- human-auditable JSONL evidence records;
- a binary token stream intended for Phase 2.

JSONL evidence record fields:

- `schema_version = "polar_phase1_qa_ingest_record_v1"`;
- `record_id`;
- `source_kind`;
- `source_hash`;
- `tokenizer_ref` with model id, revision, vocab hash, merges hash;
- `token_ids`: continuous variable-length token IDs for the QA record;
- `segments`: at least question and answer spans;
- `loss_mask`: answer tokens active, question/delimiter tokens inactive unless
  explicitly configured;
- `position_policy = "monotonic_record_local"`;
- `continuation_policy`;
- `nonclaims`.

Binary stream v1:

- magic: `PQA1`;
- endian: little;
- schema version: u16;
- tokenizer hash references;
- record count if known, otherwise stream sentinel;
- per record: stable record hash, source kind enum, token count, segment count,
  u32 token IDs, segment role/start/end/loss metadata, byte span metadata.

The binary stream is the future-facing handoff. JSONL alone is not enough for
a final Phase 1 pass.

## 5. Acceptance Gate

The authority gate is phone-native and all evidence must be generated inside
Termux on REDMAGIC.

Pass requires every item below:

1. Zig toolchain status is resolved:
   - `zig_primary_pass`, or
   - `zig_blocked_with_full_falsification_report`.
2. One canonical QA contract feeds dictionary-derived and MegaScience-derived
   records.
3. No separate dictionary hot-path parser remains in the engine.
4. MegaScience raw extraction, if implemented, is a converter into canonical QA
   records, not a separate tokenizer path.
5. Exact token parity against a trusted Gemma tokenizer reference passes on:
   - short ASCII;
   - punctuation;
   - scientific notation;
   - math symbols;
   - Unicode accents;
   - non-Latin scripts where tokenizer supports them;
   - emoji;
   - long QA records near capacity;
   - dictionary relation templates.
6. Span metadata is exact:
   - question byte spans exclude `Q:` markers;
   - answer byte spans exclude `A:` markers;
   - token spans match token IDs exactly;
   - bad/empty/malformed records are either rejected or reported explicitly.
7. Hot loop has zero heap allocation after initialization.
8. Throughput is measured on phone:
   - records/sec;
   - tokens/sec;
   - MB/sec input;
   - peak RSS;
   - elapsed wall time;
   - device thermal state before and after.
9. Stress run is non-toy:
   - at least 10,000 QA records synthetic stress if user corpus is unavailable;
   - all user-supplied dictionary or MegaScience sample if available;
   - deterministic repeat hashes match.
10. Binary stream output is produced and re-read by an independent verifier.
11. C++ reference/oracle, if retained, is compared against Zig on the same
    inputs; if Zig is slower by more than 10 percent, the agent must profile,
    fix, or report a blocker.
12. Forbidden payload scan passes before any commit or handoff.
13. The final report contains explicit nonclaims:
    - no JL packetization;
    - no NPU forward read;
    - no GPU optimizer;
    - no learning;
    - no megakernel.

The gate must report `fail` or `blocked`, not `pass`, if any item is missing.

## 6. Falsification Requirements

The build agent must run independent falsification lanes, preferably as
parallel subagents where available.

Required lanes:

1. Zig toolchain falsifier: tries to break Zig build/run/test assumptions.
2. Tokenizer correctness falsifier: searches for parity drift and span bugs.
3. QA contract falsifier: tries malformed, long, multilingual, escaped, empty,
   duplicated, and delimiter-heavy records.
4. Memory/performance falsifier: verifies allocation counters, RSS, and timing
   under stress.
5. Architecture falsifier: checks that Phase 1 did not leak into Phase 2 or
   retreat into old seq128 cache packing.
6. Artifact hygiene falsifier: scans for tokens, weights, binary payloads,
   giant outputs, `.venv`, build caches, SDK payloads, and root README edits.

Qualitative review must grade:

- clarity of component boundaries;
- absence of deep nesting and duplication;
- meaningful naming;
- separation between source conversion, tokenization, stream writing, and gate
  reporting;
- whether the code looks production-directed or demo-shaped.

Quantitative review must grade:

- percent of specification items complete;
- pass/fail for each gate item;
- performance against C++ oracle where available;
- test coverage against required input classes;
- deterministic repeat status.

## 7. Required Artifacts

Write all final evidence under `runtime/reports/polar_phase1/<timestamp>/`.

Required files:

- `phase1_gate_result.json`
- `phase1_zig_falsification_report.json`
- `phase1_qa_schema.json`
- `phase1_binary_stream_schema.md`
- `phase1_token_parity_report.json`
- `phase1_span_integrity_report.json`
- `phase1_performance_report.json`
- `phase1_allocation_audit.json`
- `phase1_dictionary_to_qa_report.json`
- `phase1_megascience_to_qa_report.json`
- `phase1_binary_stream_roundtrip_report.json`
- `phase1_qualitative_code_review.md`
- `phase1_falsifier_matrix.json`
- `commands.json`
- `README.md`

Mirror a compact handoff to:

`/sdcard/Download/polymath/polar_phase1/agent_artifacts`

The mirror must include source patches, reports, validation logs, and the final
prompt/result summary. It must not include secrets, model weights, raw corpus,
raw large token dumps, build directories, or virtual environments.

## 8. Commit Policy

Do not commit until the full gate passes or a real blocker is documented.

Allowed commit contents:

- source;
- tests;
- schemas;
- compact reports;
- prompt/spec docs;
- sanitized command logs;
- small fixtures.

Forbidden commit contents:

- repo root `README.md` edits;
- Hugging Face or GitHub tokens;
- `.env`;
- model weights;
- SDK binaries;
- raw tensor dumps;
- large token payloads;
- `.venv`;
- `node_modules`;
- build caches.

If the gate fails, commit only if the commit is explicitly framed as a blocker
report and contains the reproducible failure evidence.
