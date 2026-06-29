# PRD: Polar Phase 2 Maximal CPU JL Binary/Polar Packetization

Date: 2026-06-26
Status: Accepted execution PRD for a fresh Termux authority agent
Repository: `/Users/Zer0pa/Polymat AI/Polymath-AI`
Authority runtime: REDMAGIC NX789J / Snapdragon SM8750 / serial FY25013101C8
Phone execution target: Termux on the authority phone
Mac role: control plane, spec/audit/orchestration, no per-iteration authority
RunPod role: build/reference oracle only, never promotion authority
Comet project: `zer0pa/mobile-polymath-ai-training`
Comet URL: https://www.comet.com/zer0pa/mobile-polymath-ai-training

## 1. Governing Objective

Phase 2 must turn the Phase 1 `PQA1` token stream into fixed-size binary polar
tensor packets that can become the accelerator boundary for Phase 3 and the
target substrate for Phase 4.

The active pipeline is:

```text
Phase 1 CPU QA/PQA1 ingestion and chopping
  -> Phase 2 CPU JL binary/polar packetization
  -> Phase 3 NPU binary/polar forward read
  -> Phase 4 GPU polar optimizer
```

Phase 2 is not a demonstration of file conversion. It is the first real
construction of the polar tensor meal:

```text
PQA1 record stream
  -> record-local 128-token packet sealing
  -> phone-local Gemma4 embedding lookup
  -> fixed dense Rademacher JL projection
  -> bitpacked polar input and target tensors
  -> PJP1 packet file plus independent verifier
  -> Comet-logged authority report
```

The governing objective is a phone-native, deterministic, inspectable,
falsifiable `PQA1 -> PJP1` boundary. A green submetric does not close Phase 2 if
this boundary is missing, fake, JSON-only, embedding-fixture-only, unlogged, or
unverified.

## 2. Doctrine

Never:

- optimize for a narratable win instead of the governing objective;
- let local improvements substitute for the authority metric;
- close early because something defensible-looking exists;
- reward-hack by weakening this PRD after seeing mixed evidence;
- turn mixed evidence into a pass narrative;
- use JSON-only input or output as final evidence;
- claim Phase 2 from synthetic toy fixtures;
- normalize the project back into ordinary Gemma inference, standard LoRA,
  adapter-only continuation, or benchmark theater;
- call anything NPU, HTP, GPU optimizer, learning, or megakernel evidence in
  this phase;
- use EmbeddingGemma, sentence embeddings, pooled retrieval embeddings, or any
  non-Gemma4 artifact as the promoted authority embedding source;
- use root `README.md` as a scratchpad or edit it for this phase.

Always:

- treat the top acceptance gate as sovereign;
- treat any regression on governing correctness as failure;
- preserve the alien mechanism before making it legible;
- make every artifact force implementation, measurement, falsification, or a
  continuation decision;
- keep the phone as runtime authority;
- use Comet logging for every future Phase 2 run unless technically blocked
  with exact evidence;
- use `COMET_API_KEY` from the environment only, never printed, written, or
  copied;
- protect raw `.qai1`, `.pqa1`, `.pjp1`, model weights, tensor payloads,
  secrets, `.venv`, `node_modules`, build caches, SDK payloads, and real env
  files from git, compact mirrors, and Comet assets.

## 3. Executive Autonomy

The fresh Termux agent has executive mandate to run the Phase 2 lifecycle
without interim user reporting.

The agent may and should:

- use GPT/Codex/GPD tools to research, plan, implement, verify, and falsify;
- spawn high-reasoning subagents if available for format audit, embedding
  provenance, JL math, verifier design, performance profiling, and final
  falsification;
- use web research for technical decisions, preferring primary sources and
  recording source URLs in the research report;
- install minimal Termux dependencies after inspecting manifests and existing
  lockfiles;
- create missing Phase 2 implementation directories and scripts;
- run long phone-native jobs overnight;
- repair failures without asking for subgate approval;
- continue until the maximal gate passes or a hard blocker is proven.

The agent must not:

- ask the user for approval between ordinary research, planning, coding,
  benchmarking, and verification steps;
- stop after writing a plan, schema, scaffold, or smoke test;
- stop after a partial `PQA1` parser or fake embedding pipeline works;
- let GPD lifecycle artifacts substitute for phone-local build/test/runtime
  evidence;
- convert a hard blocker into a pass.

Only these return conditions are valid:

1. `phase2_maximal_closure_pass`: full gate passed.
2. `phase2_authority_floor_pass_continuation_required`: real phone authority
   floor passed, but maximal 1M closure remains blocked or incomplete and is
   clearly marked as continuation, not closure.
3. `phase2_blocked`: a real hard blocker remains after repeated repair
   attempts, with logs, commands, and a recovery path.
4. `phase2_failed`: a correctness, hygiene, Comet, or artifact gate failed.

## 4. Phase 1 Handoff Floor

Primary closure package:

```text
runtime/reports/polar_phase1_maximal_closure/2026-06-26T171915Z/
```

Shared phone mirror:

```text
/sdcard/Download/polymath/polar_phase1_scaling/agent_artifacts/maximal_closure/2026-06-26T171915Z/
```

Selected promoted Phase 1 Termux results:

| Scale | Records | Token IDs | Token IDs/sec |
| --- | ---: | ---: | ---: |
| 10k | 10,000 | 242,340 | 16,402,897.6177 |
| 100k | 100,000 | 2,616,577 | 49,068,772.5901 |
| 1M | 1,000,000 | 28,161,180 | 62,634,625.4288 |

Phase 1 correctness and hygiene passed:

- HF/Gemma parity;
- span integrity;
- repeated-scan equivalence;
- deterministic repeat hash;
- `PQA1` roundtrip;
- hot-loop allocations `0`;
- forbidden payload scan;
- mirror hygiene;
- Comet logging.

Selected Phase 1 Comet experiment:

```text
https://www.comet.com/zer0pa/mobile-polymath-ai-training/05c0149dfc0e4abcbc4f0c597b9fcdec
```

Remaining Phase 1 blocker:

- Android/REDMAGIC accepted-mode throughput A/B.

That blocker belongs to the Android app stream. It does not block Termux Phase
2 engineering. Phase 2 must not claim Android/Game Mode/Game Space benefit.

## 5. Raw Input Reality

The compact Phase 1 mirror intentionally excludes raw `.qai1`, `.pqa1`, and
`.jsonl` payloads. Therefore Phase 2 must first establish an authority input.

Valid promoted inputs:

1. Recovered raw Phase 1 `PQA1` from phone-local runtime directories.
2. Regenerated `PQA1` through the Phase 1 engine on the phone, using declared
   placeholder/stress material while the real training material workstream is
   separate.

Invalid promoted inputs:

- JSON-only records;
- Mac-generated token streams;
- hand-authored token IDs;
- tiny synthetic fixtures except for smoke/unit tests;
- Phase 1 report summaries treated as if they were `PQA1`;
- undeclared placeholder data.

If no valid `PQA1` can be recovered or regenerated, Phase 2 is blocked. The
agent may still implement smoke tests, but it must return `phase2_blocked`, not
`pass`.

## 6. Implemented `PQA1` Contract To Consume

The Phase 1 source snapshot on the phone records the current implemented binary
layout:

```text
/sdcard/Download/polymath/polar_phase1_scaling/agent_artifacts/source_files/native/polar_phase1_zig/phase1_qa_stream.zig
```

The Phase 2 agent must inspect the live phone checkout and source snapshot
before finalizing the reader, but the known current shape is:

Header, little endian:

| Offset | Field | Type | Notes |
| ---: | --- | --- | --- |
| 0 | magic | 4 bytes | `PQA1` |
| 4 | schema_version | u16 | current `1` |
| 6 | endian_marker | u16 | current `1` |
| 8 | record_count | u64 | exact record count |
| 16 | vocab_sha256_ascii | 64 bytes | tokenizer vocab hash |
| 80 | merges_sha256_ascii | 64 bytes | tokenizer merges hash |

Total header length: `144` bytes.

Per record:

| Field | Type | Notes |
| --- | --- | --- |
| record_hash | u64 | current implementation uses FNV-1a64 of record ID |
| source_kind | u8 | 1 dictionary, 2 megascience, 3 synthetic_stress, 4 user_supplied |
| token_count | u32 | number of token IDs for this QA record |
| segment_count | u16 | current normal value `2` |
| token_ids | `u32[token_count]` | Gemma token IDs |
| segments | `segment[segment_count]` | 18 bytes each |

Per segment, little endian:

| Field | Type |
| --- | --- |
| role | u8 |
| token_start | u32 |
| token_end | u32 |
| byte_start | u32 |
| byte_end | u32 |
| loss_mask | u8 |

Current normal roles:

- `1`: question, loss inactive;
- `2`: answer, loss active.

The Phase 2 reader must reject unknown schema versions unless explicitly mapped.
It must reject truncated records, invalid token spans, invalid segment counts,
out-of-range segment token spans, malformed loss masks, and non-little-endian
payloads.

## 7. Phase 2 Promoted Contract Decisions

These decisions are frozen for the promoted Phase 2 v1 path.

### 7.1 Packet Sealing

Promoted packet mode: `record_local`.

Rules:

- each QA record produces one or more fixed 128-slot packets;
- record boundaries are never crossed;
- long records are chunked into continuation packets;
- short final packets are padded mechanically;
- padding never participates in loss;
- padding never performs embedding lookup;
- padding polar bits are zero;
- every packet carries `real_token_count`, `pad_count`, source record hash,
  source kind, continuation index, and continuation count;
- token, role, segment, loss, and position metadata are propagated exactly.

`stream_fill` is not a promoted Phase 2 mode. It may be researched only as a
non-promoted future arm.

### 7.2 Embedding Source

Promoted embedding source: phone-local Gemma4-compatible input embedding table
matching the Phase 1 tokenizer hashes.

Required manifest fields:

- model ID;
- model revision;
- tokenizer vocab hash;
- tokenizer merges hash or tokenizer hash;
- tensor source path on phone;
- dtype;
- layout;
- vocab row count;
- embedding dimension `d`;
- full file hash;
- extraction/conversion command ledger;
- statement that the raw tensor is excluded from git, compact mirrors, and
  Comet assets.

Recommended artifact shape:

```text
~/polymath_polar_phase2/embeddings/gemma4_input_embedding.f16
~/polymath_polar_phase2/embeddings/gemma4_input_embedding_manifest.json
```

Recommended layout:

```text
row-major f16[vocab_size][d], little endian
offset = token_id * d * sizeof(f16)
```

Authority requires real Gemma4-compatible rows. A deterministic small embedding
fixture may test plumbing only. EmbeddingGemma or any non-Gemma4 embedding
model is a research/comparison arm only unless a later PRD explicitly changes
the model anchor.

### 7.3 JL Transform

Promoted JL path: dense Rademacher Johnson-Lindenstrauss projection.

Promoted JL dimension: `k = 256`.

Projection:

```text
R[j, i] in {-1, +1}
y[j] = (1 / sqrt(k)) * sum_i R[j, i] * x[i]
polar_bit[j] = 1 if y[j] >= 0 else 0
```

Implementation requirements:

- deterministic seed-derived sign matrix;
- no runtime matrix construction in the hot path;
- sign generation reproducible by an independent verifier;
- f32 accumulation from f16 input is the reference path;
- tie policy is `>= 0 -> 1`;
- output row order is token-major, then JL bit index;
- generated/baked matrix or deterministic sign function must be reported.

Recommended seed material:

```text
polymath-polar-phase2-jl-v1|gemma4|dense-rademacher|k=256|d=<embedding_dim>
```

Recommended PRNG: SplitMix64 or another tiny deterministic generator whose
source is embedded and tested. The report must record the exact generator.

SRHT is a required research note and optional non-promoted comparison arm. It is
not the promoted path for Phase 2 v1 because it changes verifier shape,
padding/alignment assumptions, and future Phase 3 input format. If the agent
finds overwhelming phone evidence that SRHT is necessary, it may implement it
as a comparison arm and return a recommendation, but it must not silently swap
the promoted gate.

### 7.4 Target Representation

Promoted `PJP1` must preserve both token-level and record-level target options
for Phase 4:

1. `input_polar_bits[128, k]` for real token slots, zero for pad slots.
2. `target_polar_bits[128, k]` active only where the propagated loss mask is
   active; zero elsewhere.
3. `pooled_answer_polar_bits[k]` computed by projecting the mean embedding of
   answer-active tokens in the source record or continuation span.
4. `loss_mask_bits[128]`.
5. `pad_mask_bits[128]`.
6. `segment_role_codes[128]` or equivalent role bitsets.

Margin summaries are optional in Phase 2 v1. If implemented, they must be
separate fields and must not be required by the core verifier.

## 8. Proposed `PJP1` Output Contract

The agent must write an exact schema file during implementation. This PRD
freezes the required semantic fields, not every byte offset.

Recommended output magic:

```text
PJP1
```

Required file-level metadata:

- magic `PJP1`;
- schema version;
- endian marker;
- header length;
- packet length fixed at `128`;
- JL dimension `k = 256`;
- embedding dimension `d`;
- source `PQA1` file hash;
- tokenizer vocab hash;
- tokenizer merges hash;
- embedding artifact hash;
- embedding manifest hash;
- JL config hash;
- polar encoding policy;
- packet count;
- source record count;
- source token count;
- slot token count, including padding;
- created UTC timestamp;
- writer version and git/source snapshot;
- nonclaims.

Required per-packet metadata:

- packet ID;
- source record hash;
- source kind;
- continuation index;
- continuation count;
- source token start in record;
- real token count;
- pad count;
- packet-local token IDs or token hash summary;
- role metadata;
- loss mask;
- pad mask;
- position policy;
- input polar bit offset and byte length;
- target polar bit offset and byte length;
- pooled answer polar bit offset and byte length;
- packet checksum.

Required tensor buffers:

- bitpacked input polar tensor, token-major `[packet_count, 128, 256]`;
- bitpacked target polar tensor, token-major `[packet_count, 128, 256]`;
- bitpacked pooled answer target `[packet_count, 256]`;
- masks and role metadata in aligned buffers.

Alignment:

- all large buffers should be at least 64-byte aligned;
- prefer 128-byte alignment where practical for future QNN/HTP handoff;
- little endian throughout;
- row-major bit order must be specified and verified.

`PJP1` is a Phase 2 artifact. It is not an NPU artifact until Phase 3 consumes
it through an actual HTP/QNN path.

## 9. Implementation Stack

Primary implementation:

```text
native/polar_phase2_packetizer/
```

Primary Termux runner:

```text
scripts/termux/run_polar_phase2_gate.py
```

Report root:

```text
runtime/reports/polar_phase2/<UTC>/
```

Compact phone mirror:

```text
/sdcard/Download/polymath/polar_phase2/agent_artifacts/<UTC>/
```

Recommended component boundaries:

- `PQA1` reader and validator;
- packet sealer;
- embedding manifest loader;
- embedding mmap row reader;
- JL sign generator;
- JL projector;
- polar bitpacker;
- `PJP1` writer;
- `PJP1` reader/verifier;
- Python oracle;
- report/Comet logger;
- artifact hygiene scanner.

Zig is the promoted hot-path language. C/C++ fallback is allowed only if it is
evidence-backed and preserves the contract. Python is allowed for
orchestration, reference checks, artifact validation, Comet logging, and
oracle computation outside the hot path. Rust is allowed for verifier or schema
tooling if it strengthens safety without slowing the hot path, but it is not a
required dependency.

## 10. Work Packages

### P2-0: Context, GPD, and Phone Footing

Goal: establish authority context and local lifecycle discipline.

Required actions:

- read `AGENTS.md`;
- read this PRD;
- read `.gpd/STATE.md`, `.gpd/ROADMAP.md`, and `.gpd/state.json` if present;
- read Phase 1 closure reports;
- inspect shared Phase 1 source snapshot;
- inspect current phone repo checkout;
- resolve whether local lifecycle tooling uses `.gpd/` or `GPD/`;
- if GPD tooling is absent or incompatible, create equivalent research, plan,
  execution, verification, and summary artifacts manually.

Required artifact:

- `phase2_gpd_lifecycle_report.md`

### P2-1: Authority `PQA1` Source

Goal: recover or regenerate valid promoted `PQA1`.

Required actions:

- search phone-local runtime directories for raw Phase 1 `.pqa1` files;
- if usable raw `PQA1` exists, hash and validate it;
- otherwise regenerate declared placeholder/stress `PQA1` through Phase 1 on
  the phone;
- record source material status: recovered, regenerated placeholder, or
  blocked;
- do not mirror raw `.pqa1` into compact artifacts.

Required artifacts:

- `phase2_pqa1_source_report.json`
- `phase2_pqa1_schema_lock.md`
- `phase2_pqa1_validation_report.json`

### P2-2: `PQA1` Reader and Packet Sealer

Goal: parse `PQA1`, validate records, and seal exact 128-slot record-local
packets.

Required behavior:

- reject malformed `PQA1`;
- preserve record boundaries;
- propagate question/answer roles and loss masks;
- split long records into continuation packets;
- pad final packets with explicit pad metadata;
- never perform embedding lookup for pad slots;
- reconstruct source records from packet metadata in the verifier.

Required artifacts:

- `phase2_packet_sealing_schema.md`
- `phase2_packet_sealing_report.json`
- small synthetic fixture and verifier report, if safe;
- no raw promoted payloads mirrored.

### P2-3: Gemma4 Embedding Artifact

Goal: create or locate a phone-local Gemma4-compatible embedding table.

Required actions:

- determine the exact model/tokenizer anchor from Phase 1 metadata;
- locate existing Gemma4 weights or fetch/extract if credentials and storage
  permit;
- convert the input embedding tensor into a flat mmap-friendly artifact;
- write manifest and hashes;
- spot-check rows against a trusted loader/oracle;
- refuse to promote fake or incompatible embeddings.

Required artifacts:

- `phase2_embedding_manifest.json`
- `phase2_embedding_provenance_report.md`
- `phase2_embedding_spotcheck_report.json`

If real Gemma4 embeddings cannot be obtained, continue smoke implementation
with a declared deterministic fixture only if useful, then return
`phase2_blocked`.

### P2-4: Dense Rademacher JL Projector

Goal: implement deterministic `k=256` dense Rademacher JL projection.

Required behavior:

- deterministic sign generation;
- reproducible independent oracle;
- f32 accumulation reference;
- zero runtime matrix construction in hot path;
- measured dispatch and memory behavior;
- tie policy recorded and tested.

Required artifacts:

- `phase2_jl_config.json`
- `phase2_jl_reference_vectors.json`
- `phase2_jl_oracle_agreement_report.json`
- `phase2_jl_performance_report.json`

Optional non-promoted artifact:

- `phase2_srht_comparison_note.md`

### P2-5: Polar Bitpacking and `PJP1` Writer

Goal: write the Phase 2 binary polar packet file.

Required behavior:

- bitpack `[128, 256]` input polar bits per packet;
- bitpack answer-active target bits per packet;
- bitpack pooled answer target bits per packet;
- write masks, roles, packet metadata, and checksums;
- write a schema/readme that makes independent parsing possible;
- use aligned buffers where practical.

Required artifacts:

- `phase2_pjp1_schema.md`
- `phase2_pjp1_writer_report.json`
- `phase2_bitpack_roundtrip_report.json`

### P2-6: Independent Verifier and Oracle

Goal: prove the writer is not self-certifying.

Minimum verifier lanes:

1. `PQA1` parser verifier.
2. Packet sealer verifier.
3. Embedding row verifier.
4. JL deterministic sign verifier.
5. JL numerical oracle agreement.
6. Polar bitpack unpack verifier.
7. `PJP1` readback and checksum verifier.
8. Source linkage verifier from `PJP1` back to `PQA1`.
9. Artifact hygiene verifier.
10. Comet verifier.

Required artifacts:

- `phase2_verifier_matrix.json`
- `phase2_oracle_agreement_report.json`
- `phase2_final_adversarial_review.md`

### P2-7: Termux Gate Runner and Comet

Goal: one command launches the gate, logs safe artifacts, and writes a compact
report tree.

Required behavior:

- capture environment, git status, command ledger, and device metadata;
- run smoke, 10k, 100k, and maximal closure attempts as configured;
- log safe metrics and safe report artifacts to Comet;
- never log secrets, raw payloads, weights, `.pqa1`, `.pjp1`, or large binary
  tensors to Comet;
- write exact evidence if Comet is technically blocked.

Required artifacts:

- `phase2_environment.json`
- `commands.json`
- `phase2_comet_logging_result.json`
- `phase2_gate_result.json`

### P2-8: Scale, Profile, and Falsify

Goal: determine whether Phase 2 is correct, phone-native, and performance-real.

Required scales:

- smoke: tiny synthetic fixture, no promotion;
- 10k source records or equivalent recovered Phase 1 source floor;
- 100k source records minimum authority floor;
- 1M source records maximal closure target.

If the real training material is not ready, regenerated declared Phase 1
placeholder/stress material may serve the engineering gate. This must be stated
in every report.

Required measurements:

- source records/sec;
- source real tokens/sec;
- packet slots/sec;
- packet count/sec;
- projected real tokens/sec;
- bytes/sec read and written;
- peak RSS and PSS where available;
- thermal before/after and during long runs if available;
- CPU/core/thread topology;
- hot-loop allocation counts;
- per-stage timing: read, seal, embedding, JL, bitpack, write, verify;
- verifier time separate from writer time.

Performance policy:

- correctness is sovereign;
- no throughput number can promote a wrong packetizer;
- if projected real tokens/sec is below `100,000` on the 100k floor, the agent
  must profile and attempt the obvious fixes before returning;
- `500,000` projected real tokens/sec is the initial stretch target, not a
  substitute for correctness;
- the agent must not conflate packets/sec with tokens/sec. A packet contains
  128 slots.

Required artifacts:

- `phase2_10k_100k_1m_stress_report.json`
- `phase2_stage_timing_report.json`
- `phase2_pss_rss_memory_report.json`
- `phase2_thermal_scheduler_report.json`
- `phase2_bottleneck_map.md`

### P2-9: Android App Handoff Package

Goal: after Termux authority is real, prepare the next stream to absorb Phase 2
one phase behind.

Required behavior:

- do not wait for Android app work to finish before doing Termux Phase 2;
- do not claim app authority from Termux results;
- produce a compact app handoff after Termux gate/floor/blocker;
- include schema, verifier, JNI-facing field map, and safe tiny fixtures only.

Required artifacts:

- `phase2_android_app_handoff.md`
- `phase2_android_jni_contract_sketch.h`
- `phase2_app_agent_startup_prompt.md`

## 11. Top Acceptance Gate

Phase 2 maximal closure passes only if all required conditions below are met on
the REDMAGIC phone in Termux.

### 11.1 Authority Runtime

- Runs on REDMAGIC NX789J / Snapdragon SM8750 in Termux.
- Does not use Mac per-iteration control.
- Records device, shell, compiler, storage, memory, thermal, and git status.
- Uses phone-local repo/workspace and phone-local runtime artifacts.

### 11.2 Input

- Consumes valid `PQA1` recovered from Phase 1 or regenerated through Phase 1
  on the phone.
- Input provenance is declared.
- Placeholder/stress material is declared if real training material is absent.
- JSON-only input is rejected as final evidence.

### 11.3 Packetization

- Emits fixed 128-slot record-local packets.
- Preserves record boundaries.
- Preserves roles, spans, loss masks, source kind, continuation, and padding.
- Independent verifier reconstructs packet-to-record relationships.

### 11.4 Embedding

- Uses real phone-local Gemma4-compatible embedding rows.
- Embedding artifact has manifest, shape, dtype, layout, and hash evidence.
- Token IDs are bounds-checked.
- Pad slots do not perform embedding lookup.
- Fixture embeddings are never promoted.

### 11.5 JL and Polar Encoding

- Uses dense Rademacher JL, `k=256`.
- Uses deterministic seed/config with no hot-path runtime matrix construction.
- Independent oracle agrees on all small fixtures and sampled large packets.
- Tie policy and bit order are tested.
- Bitpack roundtrip passes.

### 11.6 Output

- Emits `PJP1` or a named v1 binary packet file with exact schema.
- Includes input polar bits, target polar bits, pooled answer bits, masks, roles,
  packet metadata, and checksums.
- Independent readback passes.
- Source `PQA1`, embedding, and JL config hashes link through the report.

### 11.7 Scale

- Smoke pass does not promote.
- 10k floor pass is not closure.
- 100k source-record or equivalent non-toy authority floor is required for any
  promoted Phase 2 floor.
- 1M source-record maximal closure is required for `phase2_maximal_closure_pass`.
- If 1M cannot complete overnight, the agent must return continuation or
  blocker status with evidence, not final closure.

### 11.8 Metrics

- Records/sec, real tokens/sec, packet slots/sec, packets/sec, bytes/sec,
  PSS/RSS, thermal, allocations, and per-stage timings are reported.
- Writer and verifier timings are separated.
- Any performance regression or collapse is explained by bottleneck evidence,
  not narrative.

### 11.9 Comet

- Safe metrics and safe reports are logged to Comet.
- `COMET_API_KEY` is read from the environment only.
- Missing Comet logging makes the run incomplete unless technically blocked
  with exact evidence.

### 11.10 Hygiene

- No raw `.qai1`, `.pqa1`, `.pjp1`, `.jsonl`, model weights, embedding tensors,
  secrets, `.venv`, `node_modules`, build caches, SDK payloads, APK/AAB files,
  or root `README.md` edits appear in compact mirror, git, or Comet assets.
- Compact source snapshot contains changed source, schemas, reports, command
  ledgers, and safe manifests only.

### 11.11 Nonclaims

The final report must explicitly state:

- no NPU/HTP claim;
- no GPU optimizer claim;
- no learning claim;
- no model quality claim;
- no megakernel claim;
- no Android/Game Mode/Game Space benefit claim;
- no real training-material claim if placeholder/stress material was used.

If any required gate item is missing, status is `fail`, `blocked`, or
`continuation_required`, not `pass`.

## 12. Required Final Artifacts

Write final reports under:

```text
runtime/reports/polar_phase2/<UTC>/
```

Required files:

- `phase2_gate_result.json`
- `ENGINEERING_REPORT.md`
- `MANIFEST.md`
- `commands.json`
- `phase2_gpd_lifecycle_report.md`
- `phase2_source_research_map.md`
- `phase2_pqa1_source_report.json`
- `phase2_pqa1_schema_lock.md`
- `phase2_pqa1_validation_report.json`
- `phase2_packet_sealing_schema.md`
- `phase2_packet_sealing_report.json`
- `phase2_embedding_manifest.json`
- `phase2_embedding_provenance_report.md`
- `phase2_embedding_spotcheck_report.json`
- `phase2_jl_config.json`
- `phase2_jl_reference_vectors.json`
- `phase2_jl_oracle_agreement_report.json`
- `phase2_jl_performance_report.json`
- `phase2_pjp1_schema.md`
- `phase2_pjp1_writer_report.json`
- `phase2_bitpack_roundtrip_report.json`
- `phase2_verifier_matrix.json`
- `phase2_oracle_agreement_report.json`
- `phase2_10k_100k_1m_stress_report.json`
- `phase2_stage_timing_report.json`
- `phase2_pss_rss_memory_report.json`
- `phase2_thermal_scheduler_report.json`
- `phase2_allocation_audit.json`
- `phase2_forbidden_payload_scan.json`
- `phase2_comet_logging_result.json`
- `phase2_final_adversarial_review.md`
- `phase2_prd_falsification_matrix.json`
- `phase2_bottleneck_map.md`
- `phase2_android_app_handoff.md`
- compact source snapshot for changed files;
- git status/diff/stat snapshots.

Compact mirror:

```text
/sdcard/Download/polymath/polar_phase2/agent_artifacts/<UTC>/
```

The mirror must exclude raw payloads and weights.

## 13. Suggested Source Tree

The agent may adjust names if the existing repo dictates a better pattern, but
the implementation should keep this separation:

```text
native/polar_phase2_packetizer/
  build_phase2_packetizer.sh
  pqa1_reader.zig
  packet_sealer.zig
  embedding_table.zig
  jl_dense_rademacher.zig
  polar_bitpack.zig
  pjp1_writer.zig
  pjp1_reader.zig
  phase2_packetizer.zig

scripts/termux/
  run_polar_phase2_gate.py
  log_polar_phase2_to_comet.py

tests/
  test_polar_phase2_pqa1_reader.py
  test_polar_phase2_pjp1_schema.py
```

Do not create unnecessary abstractions. Do decouple reader, sealer, embedding,
JL, writer, verifier, and runner so each can be falsified independently.

## 14. Research Context, Not Authority

The augmented engineering spec raised useful research options. The PRD locks
the promoted path above, while preserving these as research context:

- Zig `comptime` and vector support are relevant to the dense JL hot path.
- Arrow-style separation of schema/header from aligned buffers is a useful
  layout reference.
- BLAKE3 is preferred for new content hashes if available; SHA-256 remains
  acceptable for compatibility with Phase 1 fields and when BLAKE3 is blocked.
- SRHT may become a future projection path if phone evidence shows dense
  Rademacher is the wrong wall.
- EmbeddingGemma may be useful for a future embedding/retrieval lane, but it is
  not a promoted Phase 2 authority embedding source for the frozen Gemma4
  polar boundary.
- QNN/HTP alignment considerations should shape `PJP1`, but Phase 2 does not
  make an HTP claim.

Reference URLs for the agent to inspect if it uses these ideas:

- Zig language reference: https://ziglang.org/documentation/master/
- BLAKE3 project: https://github.com/BLAKE3-team/BLAKE3
- Apache Arrow format: https://arrow.apache.org/docs/format/Columnar.html
- Google AI Edge LiteRT Qualcomm documentation:
  https://developers.google.com/edge/litert/next/qualcomm
- EmbeddingGemma announcement:
  https://developers.googleblog.com/introducing-embeddinggemma/
- Ailon and Chazelle Fast Johnson-Lindenstrauss Transform:
  https://doi.org/10.1137/060673096
- Tropp SRHT analysis:
  https://tropp.caltech.edu/papers/Tro11-Improved-Analysis-preprint.pdf
- Johnson-Lindenstrauss transform survey:
  https://arxiv.org/abs/2103.00564

External papers, blogs, and benchmarks do not promote Phase 2. Only the phone
run can do that.

## 15. Final Report Template

The final `ENGINEERING_REPORT.md` must start with:

```text
Status: phase2_maximal_closure_pass | phase2_authority_floor_pass_continuation_required | phase2_blocked | phase2_failed
Report root: runtime/reports/polar_phase2/<UTC>/
Comet experiment: <URL or blocked evidence>
Authority runtime: REDMAGIC NX789J / Snapdragon SM8750 / Termux
Input status: recovered_pqa1 | regenerated_placeholder_pqa1 | blocked
Embedding status: real_gemma4_embedding | fixture_only_blocked | blocked
JL policy: dense_rademacher_k256
Output schema: PJP1 v1
Nonclaims: no NPU/HTP, no GPU optimizer, no learning, no megakernel, no Android/Game Mode benefit
```

Then include:

- promoted results table;
- correctness/verifier table;
- performance/stage timing table;
- memory/thermal table;
- artifact hygiene table;
- open blockers and next valid attacks;
- Android app handoff status.

## 16. Success Definition

Phase 2 succeeds only when the authority phone produces verified binary polar
packet artifacts from valid Phase 1 `PQA1` using real Gemma4 embeddings, dense
Rademacher JL `k=256`, exact record-local 128-token packet semantics, independent
verification, Comet evidence, and clean handoff artifacts.

Anything less is a smoke result, floor result, continuation, blocker, or fail.
