# PRD: Polar Phase 2-B Native Performance Closure

Date: 2026-06-27
Status: Superseding execution PRD for a fresh Termux authority agent
Repository: `/data/data/com.termux/files/home/Polymath-AI` on phone, `/Users/Zer0pa/Polymat AI/Polymath-AI` on Mac
Authority runtime: REDMAGIC NX789J / Snapdragon SM8750 / serial FY25013101C8
Execution target: Termux on the authority phone
Mac role: control plane, audit, orchestration, spec continuity
RunPod role: build/reference oracle only when explicitly needed
Comet workspace: `zer0pa`
Comet project: `mobile-polymath-ai-training`
Comet URL: https://www.comet.com/zer0pa/mobile-polymath-ai-training

## 0. Maximal Culture Lock

Good is the enemy of great.

The top acceptance gate is sovereign.

Objective substitution is failure.

A green metric does not license closure if the governing objective remains unresolved.

Treat regression on authority metrics as failure unless the regressing run is explicitly declared a non-promoted comparison arm before it starts.

Do not reward-hack by narrowing this PRD after seeing evidence.

Do not convert mixed evidence into a pass narrative.

Do not preserve a narratable win at the cost of the real objective.

Artifacts must force implementation, measurement, falsification, or continuation decisions. Anything else is process theater.

Preserve the alien mechanism before making it legible.

Phone is authority. Mac is control plane. RunPod is a build/reference oracle only unless a PRD explicitly says otherwise.

Do not normalize this project back into standard Gemma inference, conventional LoRA, adapter-only continuation, ordinary benchmark theater, or a tidy proof-of-concept.

No megakernel language is allowed in this phase unless there is a real fused/static/routed training path with measured dispatch, traffic, thermal, scope, and learning advantage. Phase 2-B is not a megakernel phase.

No HTP/NPU claim is allowed unless HTP/NPU output or routing changes the executed Gemma training route, objective, gradient, update, teacher, or state transition. Phase 2-B is CPU packetization.

Root repo `README.md` is user-owned and out of bounds.

## 1. Why This PRD Exists

The previous Phase 2 result produced a real and useful artifact, but its closure label was too generous.

Previous reported status:

```text
phase2_maximal_closure_pass
```

Correct classification:

```text
phase2_contract_scale_reference_pass_native_performance_failed
```

The previous work proved that the contract can exist:

```text
PQA1 -> Gemma4 embedding lookup -> dense Rademacher JL k=256 -> PJP1
```

It did not prove that Phase 2 has met the Phase 1 engineering standard. It used a Python/NumPy authority hot path, missed the stated performance floor, and marked an allocation audit as pass while admitting that hot-loop allocations were not instrumented in the Python/NumPy path.

This PRD turns the previous artifact into an oracle/reference floor and orders the next agent to build the native authority path.

The new agent must not redo Phase 2 from zero. It must not accept the previous pass label. It must port the Phase 1 architectural standard into the Phase 2 transform.

## 2. Psychological Failure Modes To Resist

The agent must assume its own default training will pull it toward smaller, safer, narratable work.

Common failure modes:

- writing another plan instead of building the native path;
- treating the Python/NumPy reference as "good enough";
- producing a Zig scaffold with no measured hot path;
- celebrating correctness while the authority throughput remains below gate;
- swapping dense JL for a cheaper projection without predeclared comparison-arm status;
- lowering scale, lowering `k`, dropping target tensors, or dropping pooled targets after performance looks hard;
- reporting "bottleneck identified" as if that closes the bottleneck;
- using a green Comet/hygiene/correctness metric to bury a missed performance gate;
- treating a 10k or 100k result as maximal closure;
- producing Android handoff before Termux authority is native-performance credible;
- saying "blocked by hardware" without a roofline, profile, attempted variants, thermal evidence, and exact blocker.

The agent must be hostile to its own premature closure story. It must treat every "pass" sentence as suspect until the gate matrix proves it.

## 3. Human Summary For Non-Technical Readers

Phase 1 built a very fast, trustworthy machine for turning raw material into token packets. It ran at roughly 62.6 million token IDs per second at 1M scale and had a hard native engineering standard.

Phase 2 takes those Phase 1 packets and turns them into polar training packets. It has more work to do: look up Gemma embedding vectors, project them through a fixed random transform, and write binary polar packets.

The previous Phase 2 agent built the shape of the pipeline, but it built the engine as a Python reference. That is useful as a proof and oracle. It is not the final engine.

This Phase 2-B PRD says: keep the shape, keep the evidence, keep the schema, and replace the engine with a native phone-side implementation that aims at the hardware limit until real physics or platform limits stop it.

## 4. Governing Objective

Build and verify a phone-native native-code Phase 2 packetizer that consumes valid Phase 1 `PQA1`, uses the real Gemma4 embedding artifact and the frozen dense Rademacher JL `k=256` policy, emits `PJP1`, and meets or falsifies the performance gate with hard evidence.

The promoted boundary remains:

```text
PQA1 records
  -> record-local 128-slot packet sealing
  -> phone-local Gemma4 input embedding lookup
  -> dense Rademacher JL projection, k=256, d=2560
  -> bitpacked input polar bits
  -> bitpacked target polar bits
  -> pooled answer polar bits
  -> PJP1 binary packet file
  -> independent verifier
  -> Comet-logged authority report
```

The main difference from the previous result:

```text
Python/NumPy reference path -> native hot path with measured hardware pursuit
```

## 5. Relationship To Phase 1

Phase 2-B is an adaptation of the Phase 1 architecture, not a copy of Phase 1 math.

Reuse Phase 1 standards:

- binary input contract discipline;
- chunked streaming or mmap processing;
- schema-locked reader and writer;
- native hot path;
- zero or explicitly measured hot-loop allocation behavior;
- correctness oracle separate from fast path;
- scale ladder: smoke, 10k, 100k, 1M;
- Comet for all benchmark/gate/falsifier runs;
- forbidden payload hygiene;
- compact mirror discipline;
- final adversarial review;
- refusal to close with unresolved authority blockers.

Do not reuse Phase 1 blindly:

- Phase 1 scanned/tokenized/chopped.
- Phase 2 performs embedding lookup, JL projection, bitpacking, and large binary output.
- The Phase 2 bottleneck is mathematically different and much heavier.

Phase 1 is the architectural bar and input source. Phase 2-B must build the new native engine inside that bar.

## 6. Previous Phase 2 Evidence To Preserve

Previous report root on phone:

```text
/data/data/com.termux/files/home/Polymath-AI/runtime/reports/polar_phase2/2026-06-26T235142Z
```

Previous engineering review mirror:

```text
/sdcard/Download/polymath/polar_phase2/engineering_review/2026-06-26T235142Z
```

Mac-side pulled review bundle:

```text
runtime/reports/polar_phase2_engineering_review/2026-06-26T235142Z
```

Previous Comet evidence:

```text
Gate experiment:
https://www.comet.com/zer0pa/mobile-polymath-ai-training/27d52eca29ac4f7e94ea2d756562d3e5

Final artifact/metrics experiment:
https://www.comet.com/zer0pa/mobile-polymath-ai-training/54a39298b00047e8ade8b12730ce405e
```

Previous 1M reference output:

```text
Path:
/data/data/com.termux/files/home/Polymath-AI/runtime/reports/polar_phase2/2026-06-26T235142Z/raw_1M.pjp1

SHA-256:
efc355c518c637c0519fbb2b007390091798a068763ea097b18473fa8690159d
```

Previous 1M scale:

```text
source records: 1,000,000
real tokens: 28,161,180
packets: 1,006,024
PJP1 bytes: 9,110,557,440
```

Previous valid components:

- recovered/regenerated Phase 1 `PQA1` source existed;
- real Gemma4 embedding artifact existed;
- dense Rademacher JL `k=256, d=2560` config existed;
- `PJP1` schema existed;
- smoke, 10k, 100k, and 1M outputs existed;
- hygiene and Comet reports existed.

Previous invalid closure claims:

- `phase2_maximal_closure_pass`;
- allocation audit `pass` despite `hot_loop_allocations: not instrumented in Python/NumPy path`;
- maximal closure despite 1M throughput below the stated 100,000 real tokens/sec policy floor;
- native-path readiness implied by a native directory containing only a README.

## 7. Previous Bottleneck Evidence

Previous performance report:

```text
runtime/reports/polar_phase2_engineering_review/2026-06-26T235142Z/reports/phase2_performance_policy_report.json
```

Previous 100k:

```text
wall elapsed: 85.05959871807136 sec
source records: 100,000
real tokens: 2,616,577
packets: 100,606
real tokens/sec: 30,761.689914298815
packet slots/sec: 151,394.64791836706
```

Previous 1M:

```text
wall elapsed: 1,520.8192168679088 sec
source records: 1,000,000
real tokens: 28,161,180
packets: 1,006,024
real tokens/sec: 18,517.112150908564
packet slots/sec: 84,672.17574038878
```

Previous 1M stage timing:

```text
read_validate: 4.207373280078173 sec
seal: 37.41002258379012 sec
embedding_lookup: 263.57850063219666 sec
jl_project: 999.560832537245 sec
bitpack: 120.9512702380307 sec
write: 30.80632625706494 sec
total: 1520.8192168679088 sec
```

Dominant bottleneck:

```text
dense JL projection: 65.725% of 1M wall time
```

This is not closure. This is a map.

## 8. Frozen Promoted Contract

The next agent must not silently change these promoted decisions.

### 8.1 Input

Promoted input:

- valid Phase 1 `PQA1`;
- recovered from phone-local Phase 1/Phase 2 runtime state or regenerated through the Phase 1 engine;
- declared as recovered, regenerated placeholder/stress, or blocked.

Invalid promoted input:

- JSON-only data;
- hand-authored token IDs;
- Mac-generated data sold as authority;
- tiny synthetic fixture sold as scale evidence;
- Phase 1 report summaries treated as if they were payloads.

### 8.2 Packet Sealing

Promoted packet mode:

```text
record_local
```

Rules:

- 128 token slots per packet;
- record boundaries are never crossed;
- long records become continuation packets;
- short packets are padded;
- pad slots do not perform embedding lookup;
- pad slots produce zero polar bits;
- loss masks and roles are preserved exactly;
- every packet carries source record hash, source kind, continuation index/count, source token start, real token count, pad count, loss mask, pad mask, token IDs or token hash, roles, and section offsets.

### 8.3 Embedding

Promoted embedding:

```text
google/gemma-4-E4B input embedding table
tensor: model.language_model.embed_tokens.weight
dtype source: BF16
flat artifact dtype: f16
shape: [262144, 2560]
```

Known previous artifact:

```text
/data/data/com.termux/files/home/polymath_polar_phase2/embeddings/gemma4_E4B_input_embedding.f16
bytes: 1,342,177,280
sha256: b57e1e756f32d02c1aaad6c5c868f975f53b0938e0a04ed546804ed9c7d4ca7b
```

If this artifact exists and hash matches, reuse it.

If it does not exist, recreate it through the prior extraction path or a better audited path. Do not log weights or embed tensors to git, Comet, or compact mirrors.

### 8.4 JL Projection

Promoted projection:

```text
dense Rademacher Johnson-Lindenstrauss projection
k = 256
d = 2560
tie policy: y >= 0 -> 1
row order: token-major, JL bit index increasing
bit order: LSB-first within each byte
```

Known previous JL config:

```text
seed material:
polymath-polar-phase2-jl-v1|gemma4|dense-rademacher|k=256|d=2560

matrix path:
/data/data/com.termux/files/home/polymath_polar_phase2/jl/gemma4_dense_rademacher_k256_d2560_i8.bin

matrix bytes:
655,360

matrix sha256:
1b1f9de3dd6fbdf9597240eeeb08a6b482b33f1ae4d127e730222750cdf92a79

PRNG:
SplitMix64 sequential over JL-major then embedding-index order, stored as d x k int8

scale:
0.0625
```

SRHT, lower `k`, different embedding dimensions, quantized approximate projection, or pooled-only output are comparison arms only unless a later PRD changes the promoted contract before evidence is collected.

### 8.5 Output

Promoted output:

```text
PJP1 schema v1 compatible with the previous reference
```

Required sections:

- 4096-byte header;
- metadata: 192 bytes per packet;
- token IDs: 128 little-endian u32 values per packet;
- roles: 128 u8 values per packet;
- input polar: 4096 bytes per packet, token-major `[128, 256]`;
- target polar: 4096 bytes per packet, token-major `[128, 256]`, zero outside loss-active slots;
- pooled answer: 32 bytes per packet, `[256]`, LSB-first.

Required behavior:

- schema documented;
- independent readback passes;
- per-packet checksums verified;
- source `PQA1`, embedding, JL config, and writer source hashes linked.

## 9. Native Engineering Mandate

The promoted Phase 2-B hot path must be native code.

Preferred language:

```text
Zig
```

Allowed native fallback:

```text
C or C++ with explicit justification
```

Allowed non-hot-path languages:

- Python for orchestration, Comet, report collation, independent oracle, and hygiene;
- Rust for verifier/schema tooling if it strengthens safety and does not slow the promoted hot path.

Not allowed as promoted authority hot path:

- Python/NumPy;
- Python multiprocessing sold as native closure;
- external BLAS-only solution with no source-controlled native authority path;
- unmeasured opaque binary;
- GPU/NPU path sold as CPU Phase 2-B.

The previous Python/NumPy implementation is now a reference implementation and oracle source. It is not the promoted implementation.

## 10. Required Native Components

Create or complete:

```text
native/polar_phase2_packetizer/
```

Recommended files:

```text
native/polar_phase2_packetizer/build_phase2_packetizer.sh
native/polar_phase2_packetizer/pqa1_reader.zig
native/polar_phase2_packetizer/packet_sealer.zig
native/polar_phase2_packetizer/embedding_table.zig
native/polar_phase2_packetizer/jl_dense_rademacher.zig
native/polar_phase2_packetizer/polar_bitpack.zig
native/polar_phase2_packetizer/pjp1_writer.zig
native/polar_phase2_packetizer/pjp1_reader.zig
native/polar_phase2_packetizer/phase2_packetizer.zig
native/polar_phase2_packetizer/README.md
```

The agent may choose a better local file split, but the boundaries must exist in the design and reports:

- `PQA1` reader and validator;
- record-local packet sealer;
- embedding mmap row reader;
- dense JL projector;
- polar bitpacker;
- `PJP1` writer;
- `PJP1` readback/verifier;
- benchmark/profiler hooks.

Avoid deep nesting. Avoid duplicate parser logic. Use names that a future Android app agent can understand.

## 11. Native Hot Path Requirements

The native path must avoid the previous waste pattern:

- no full Python list of records for authority scale;
- no materialized full bool `[tokens, 256]` arrays in the hot path;
- no runtime sign matrix construction in the hot path;
- no repeated embedding extraction;
- no recomputing static hashes inside per-packet loops;
- no per-token heap allocation;
- no per-packet heap allocation in the inner loop;
- no self-certifying writer-only verifier.

Required architecture:

1. Open `PQA1` shards by mmap or streaming buffered read.
2. Validate and seal records into 128-slot packet work units.
3. Lookup f16 embedding rows by mmap offset.
4. Accumulate dense Rademacher JL using f32 reference-equivalent accumulation unless a faster path proves bit-identical or oracle-equivalent.
5. Emit sign bits directly into packed output buffers.
6. Write target bits by copying/zeroing based on loss mask without re-projecting when possible.
7. Compute pooled answer bits without materializing avoidable large intermediates.
8. Write `PJP1` through mmap, `pwrite`, or a measured sequential writer.
9. Record exact timing for read, seal, embedding, JL, bitpack, write, flush, and verify.

## 12. JL Kernel Mandate

Dense JL is the known bottleneck. The agent must attack it directly.

Baseline math:

```text
per real token:
d * k = 2560 * 256 = 655,360 signed add/sub contributions
```

Native variants to implement or explicitly falsify:

1. Scalar native correctness baseline.
2. Single-thread NEON or compiler-vectorized tiled kernel.
3. Multi-thread tiled kernel over packets/tokens.
4. Fused projection plus bitpack path that avoids storing boolean matrices.
5. Precomputed sign layout variant if the previous `d x k int8` layout is cache-unfriendly.
6. Batch-size sweep.
7. Thread-count sweep.
8. Optional external BLAS/OpenBLAS comparison as non-promoted reference only.

The agent must not stop after variant 1.

Minimum JL reports:

- exact algorithm;
- sign matrix layout;
- memory access pattern;
- tile sizes;
- thread count and CPU affinity if available;
- batch sizes;
- scalar vs vectorized vs threaded timings;
- per-stage counters;
- why the winning variant won;
- why rejected variants lost.

If NEON intrinsics are unavailable in Zig, use a C/C++ kernel through a small C ABI and keep the rest of the pipeline in Zig or clean native code. Do not let language purity defeat the hardware objective.

## 13. Performance Gate

Correctness is sovereign, but correctness alone does not close Phase 2-B.

Previous Python/NumPy baselines:

```text
100k: 30,761.689914 real tokens/sec
1M:   18,517.112151 real tokens/sec
```

Mandatory floor for any native promoted pass:

```text
100k real tokens/sec at 100k scale
100k real tokens/sec at 1M scale if 1M is claimed
```

Native speedup floor:

```text
>= 3x previous Python/NumPy throughput at the same scale
```

Stretch target:

```text
500k real tokens/sec
```

The stretch target is not a pass requirement on day one, but the agent must pursue it until profiling shows the next physical or platform blocker.

Pass is forbidden if:

- 100k scale remains below 100,000 real tokens/sec;
- 1M is claimed while below 100,000 real tokens/sec;
- native speedup is less than 3x the previous Python baseline;
- the performance report says "bottleneck identified" but the bottleneck was not attacked with measured variants;
- thermal throttling is asserted without thermal evidence;
- hardware limit is asserted without a roofline-style bound.

If a real physics/platform limit blocks the floor, the correct status is `phase2b_correctness_pass_perf_blocked` or `phase2b_blocked`, not pass.

## 14. Roofline And Hardware Reality Requirement

The agent must estimate whether the measured result is close to plausible hardware limits.

At minimum, report:

- dense JL contributions per second;
- effective embedding bytes read per second;
- effective `PJP1` write bytes per second;
- output bytes per real token;
- CPU cores visible;
- CPU affinity/cpus allowed;
- thermal zones before/during/after;
- governor/scheduler facts available without root;
- thread scaling curve;
- stage fractions at 10k, 100k, and 1M.

Required derived metrics:

```text
jl_signed_contributions_per_sec = real_tokens_per_sec * 655360
embedding_read_bytes_per_sec = real_tokens_per_sec * 2560 * 2
output_bytes_per_real_token = pjp1_bytes / source_real_token_count
native_speedup_vs_python = native_real_tokens_per_sec / python_baseline_same_scale
```

The agent must explain whether the run is compute-bound, memory-bound, write-bound, thermal-bound, or implementation-bound. If it cannot tell, it must say so and keep the status out of pass.

## 15. Correctness Gate

The native path must match the reference contract.

Required verifier lanes:

1. `PQA1` parser verification.
2. Packet sealer verification.
3. Embedding row bounds and spot checks.
4. JL sign matrix/config verification.
5. Native scalar vs Python oracle on fixture vectors.
6. Native vectorized/threaded vs scalar on fixture vectors.
7. Bitpack roundtrip.
8. `PJP1` header and section readback.
9. Packet metadata readback.
10. Source hash linkage.
11. Large-output sampled oracle.
12. Hygiene scan.
13. Comet logging verification.

Small fixtures must be exact. Large runs must include explicit sample counts and sample selection policy. A report that says "sampled" without sample count is insufficient.

Minimum large sampling:

```text
10k: full or >= 10,000 packet samples if full is too expensive
100k: >= 10,000 packet samples
1M: >= 20,000 packet samples, stratified across beginning, middle, end, and random packets
```

If the native path intentionally differs in header timestamp or writer label, compare semantic sections and document excluded fields. Do not hide mismatches behind whole-file hash differences.

## 16. Allocation Gate

The allocation audit must be real.

Invalid:

```text
hot_loop_allocations: not instrumented
status: pass
```

Required:

- define the hot loop boundaries;
- instrument allocator calls if Zig allocator is used;
- record whether hot loops use no allocator;
- count or prove absence of allocations during projection/bitpack/write loops;
- separate setup allocation from hot-path allocation;
- fail the allocation lane if instrumentation is absent.

Allowed pass wording:

```text
hot_loop_allocator_calls: 0
instrumentation: enabled
native_hot_path: true
status: pass
```

Allowed non-pass wording:

```text
status: blocked_or_incomplete
reason: allocation instrumentation unavailable
```

## 17. Comet Policy

Comet logging is mandatory for all Phase 2-B runs.

Workspace:

```text
zer0pa
```

Project:

```text
mobile-polymath-ai-training
```

Use:

```text
COMET_API_KEY
```

from environment only.

Never print, write, echo, copy, include in command logs, or mirror secrets.

Any benchmark, training, gate, falsifier, or performance run without Comet is incomplete unless Comet is technically blocked with exact evidence.

Log safe metrics and reports only. Do not log raw `.pqa1`, raw `.pjp1`, `.qai1`, `.jsonl`, model weights, embedding tensors, `.safetensors`, `.bin`, `.env`, token files, SDK payloads, `.venv`, `node_modules`, or build caches.

## 18. Work Packages

### P2B-0: Context And Evidence Intake

Read:

1. `AGENTS.md`
2. this PRD
3. `.gpd/STATE.md`
4. `.gpd/ROADMAP.md`
5. previous Phase 2 PRD:
   `docs/PRD-POLAR-PHASE2-PACKETIZATION-MAXIMAL-2026-06-26.md`
6. previous Phase 2 startup prompt:
   `docs/TERMUX-POLAR-PHASE2-PACKETIZATION-STARTUP-PROMPT-2026-06-26.md`
7. previous engineering review bundle:
   `/sdcard/Download/polymath/polar_phase2/engineering_review/2026-06-26T235142Z`
8. previous report root:
   `/data/data/com.termux/files/home/Polymath-AI/runtime/reports/polar_phase2/2026-06-26T235142Z`
9. Phase 1 closure reports and source snapshots.

Deliver:

- `phase2b_evidence_intake_report.md`
- `phase2b_previous_claim_reclassification.json`

### P2B-1: Source And Artifact Reuse

Find and validate:

- Phase 1 `PQA1` shards;
- previous embedding artifact;
- previous JL matrix;
- previous Python runner;
- previous `PJP1` schema;
- previous raw PJP1 hashes.

Deliver:

- `phase2b_reuse_manifest.json`
- `phase2b_input_artifact_validation.json`

### P2B-2: Native Skeleton With Real CLI

Create a native packetizer CLI.

Required features:

- `--input-pqa1` repeated or manifest file;
- `--embedding-f16`;
- `--jl-matrix`;
- `--output-pjp1`;
- `--max-records`;
- `--threads`;
- `--batch-records` or `--batch-slots`;
- `--report-json`;
- `--verify-samples`;
- `--mode smoke|10k|100k|1m`;
- nonzero exit on correctness failure.

Deliver:

- native source files;
- build script;
- CLI help text captured;
- smoke command captured.

### P2B-3: Native Parser, Sealer, Writer Equivalence

Implement parser/sealer/writer without optimizing JL first.

Required:

- parse `PQA1`;
- seal record-local packets;
- write `PJP1` with zeros or scalar projection for smoke only;
- read back and verify metadata.

Deliver:

- `phase2b_native_parser_report.json`
- `phase2b_packet_sealer_equivalence_report.json`
- `phase2b_pjp1_writer_equivalence_report.json`

This package cannot promote closure.

### P2B-4: Native Scalar JL Correctness

Implement scalar dense JL.

Required:

- reproduce SplitMix64 sign generation/matrix interpretation;
- project f16 embedding rows with f32 accumulation;
- generate exact sign bits under tie policy;
- compare with Python oracle and previous reference vectors.

Deliver:

- `phase2b_scalar_jl_correctness_report.json`
- `phase2b_jl_reference_vector_report.json`

This package cannot promote closure.

### P2B-5: Native Optimized JL

Attack the bottleneck.

Required:

- vectorized/tiled implementation;
- multi-thread implementation;
- fused projection/bitpack implementation;
- layout sweep if useful;
- batch and thread sweep;
- compare each variant against scalar correctness.

Deliver:

- `phase2b_jl_variant_matrix.json`
- `phase2b_thread_scaling_report.json`
- `phase2b_native_bottleneck_report.md`

### P2B-6: Full Native PJP1 Production

Produce native `PJP1` at smoke, 10k, 100k, and 1M when possible.

Required:

- no raw payloads in compact mirror;
- raw payload paths and hashes in manifest;
- exact source counts;
- exact throughput counts;
- exact stage timing.

Deliver:

- `phase2b_smoke_packetizer_report.json`
- `phase2b_10k_packetizer_report.json`
- `phase2b_100k_packetizer_report.json`
- `phase2b_1m_packetizer_report.json` if 1M completes
- `phase2b_raw_payload_manifest.json`

### P2B-7: Independent Verification

Verify writer independence.

Required:

- Python oracle remains separate from native writer;
- sample counts explicit;
- native scalar used as secondary oracle for optimized path;
- compare semantic `PJP1` sections, not just whole-file hash;
- large samples stratified.

Deliver:

- `phase2b_verifier_matrix.json`
- `phase2b_oracle_agreement_report.json`
- `phase2b_large_sample_report.json`

### P2B-8: Performance Closure Or Blocker

Decide honestly.

Required:

- compare against previous Python baseline;
- test at least 100k;
- test 1M if claiming maximal closure;
- measure memory, thermal, thread scaling, and stage timings;
- include roofline-style analysis;
- state whether remaining limit is implementation, compute, memory, write, thermal, storage, or unknown.

Deliver:

- `phase2b_performance_gate_report.json`
- `phase2b_roofline_report.md`
- `phase2b_stage_timing_report.json`
- `phase2b_memory_report.json`
- `phase2b_thermal_scheduler_report.json`

### P2B-9: Hygiene, Comet, Handoff

Package safely.

Required:

- Comet logging;
- forbidden payload scan;
- compact mirror;
- final adversarial review;
- app handoff only if Termux result is real enough.

Deliver:

- `phase2b_comet_logging_result.json`
- `phase2b_forbidden_payload_scan.json`
- `phase2b_final_adversarial_review.md`
- `phase2b_gate_result.json`
- `phase2b_android_app_handoff.md`
- `phase2b_app_agent_startup_prompt.md`

## 19. Required Report Tree

Write all final reports under:

```text
runtime/reports/polar_phase2_native_closure/<UTC>/
```

Compact mirror:

```text
/sdcard/Download/polymath/polar_phase2/native_closure/<UTC>/
```

Required final files:

- `phase2b_gate_result.json`
- `ENGINEERING_REPORT.md`
- `MANIFEST.md`
- `commands.json`
- `git_status.txt`
- `git_diff_stat.txt`
- `phase2b_evidence_intake_report.md`
- `phase2b_previous_claim_reclassification.json`
- `phase2b_reuse_manifest.json`
- `phase2b_input_artifact_validation.json`
- `phase2b_native_parser_report.json`
- `phase2b_packet_sealer_equivalence_report.json`
- `phase2b_pjp1_writer_equivalence_report.json`
- `phase2b_scalar_jl_correctness_report.json`
- `phase2b_jl_reference_vector_report.json`
- `phase2b_jl_variant_matrix.json`
- `phase2b_thread_scaling_report.json`
- `phase2b_native_bottleneck_report.md`
- `phase2b_smoke_packetizer_report.json`
- `phase2b_10k_packetizer_report.json`
- `phase2b_100k_packetizer_report.json`
- `phase2b_1m_packetizer_report.json` or `phase2b_1m_blocker_report.md`
- `phase2b_raw_payload_manifest.json`
- `phase2b_verifier_matrix.json`
- `phase2b_oracle_agreement_report.json`
- `phase2b_large_sample_report.json`
- `phase2b_performance_gate_report.json`
- `phase2b_roofline_report.md`
- `phase2b_stage_timing_report.json`
- `phase2b_memory_report.json`
- `phase2b_thermal_scheduler_report.json`
- `phase2b_allocation_audit.json`
- `phase2b_comet_logging_result.json`
- `phase2b_forbidden_payload_scan.json`
- `phase2b_final_adversarial_review.md`
- `phase2b_android_app_handoff.md`
- `phase2b_app_agent_startup_prompt.md`

## 20. Forbidden Artifacts

Forbidden in git, compact mirror, and Comet:

- raw `.qai1`;
- raw `.pqa1`;
- raw `.pjp1`;
- raw `.jsonl`;
- model weights;
- embedding tensors;
- `.safetensors`;
- `.bin` tensor dumps;
- secrets;
- `.env`, `.env.local`, token files;
- `.venv`, `venv`;
- `node_modules`;
- build caches;
- SDK payloads;
- root `README.md` edits;
- APK/AAB files unless an app PRD explicitly requests them.

Allowed:

- source code;
- schemas;
- small test fixtures that do not contain real payloads;
- hashes;
- manifests;
- JSON reports;
- markdown reports;
- command ledgers;
- compact source snapshots.

## 21. Status Vocabulary

Only these terminal statuses are valid.

### `phase2b_native_maximal_closure_pass`

Allowed only if all are true:

- native hot path used;
- 1M source-record run completed;
- valid `PQA1` consumed;
- real Gemma4 embedding used;
- dense JL `k=256,d=2560` used;
- `PJP1` emitted;
- independent verifier passed;
- Comet passed;
- hygiene passed;
- allocation audit instrumented and passed;
- 1M throughput >= 100,000 real tokens/sec;
- native 1M speedup >= 3x previous Python 1M baseline;
- final adversarial review finds no unresolved blocker.

### `phase2b_native_floor_pass_1m_continuation_required`

Allowed only if:

- native 100k floor passes correctness;
- 100k throughput >= 100,000 real tokens/sec;
- native 100k speedup >= 3x previous Python 100k baseline;
- 1M was not completed due to time/storage/thermal and has exact continuation plan.

This is not final closure.

### `phase2b_correctness_pass_perf_failed`

Use when:

- native correctness passes;
- 100k or 1M throughput floor fails;
- no proven hardware blocker yet.

This is a useful engineering result, not closure.

### `phase2b_correctness_pass_perf_blocked`

Use when:

- native correctness passes;
- performance floor fails;
- roofline/profile/thermal/storage evidence shows a real platform or physics blocker after multiple serious variants.

This is not closure.

### `phase2b_blocked`

Use when:

- missing artifacts, storage, compiler, dependencies, permissions, Comet, or phone platform issues prevent meaningful completion after repair attempts.

### `phase2b_failed`

Use when:

- correctness fails;
- hygiene fails;
- Comet is skipped without blocker evidence;
- raw payloads leak;
- root `README.md` is edited;
- promoted contract is silently narrowed.

## 22. Final Engineering Report Opening

The final `ENGINEERING_REPORT.md` must start with:

```text
Status: phase2b_native_maximal_closure_pass | phase2b_native_floor_pass_1m_continuation_required | phase2b_correctness_pass_perf_failed | phase2b_correctness_pass_perf_blocked | phase2b_blocked | phase2b_failed
Report root: runtime/reports/polar_phase2_native_closure/<UTC>/
Mirror: /sdcard/Download/polymath/polar_phase2/native_closure/<UTC>/
Comet experiment(s): <URL(s) or blocked evidence>
Authority runtime: REDMAGIC NX789J / Snapdragon SM8750 / Termux
Input status: recovered_pqa1 | regenerated_placeholder_pqa1 | blocked
Implementation status: native_hot_path | native_correctness_only | python_reference_only
Embedding status: real_gemma4_embedding | blocked
JL policy: dense_rademacher_k256_d2560
Output schema: PJP1 v1
Previous Phase 2 classification: contract_scale_reference_pass_native_performance_failed
Nonclaims: no NPU/HTP, no GPU optimizer, no learning, no model quality, no megakernel, no Android/Game Mode benefit
```

Then include:

- plain-language verdict;
- promoted result table;
- previous baseline comparison;
- correctness/verifier table;
- performance/stage timing table;
- roofline/hardware limit discussion;
- memory/thermal table;
- allocation audit;
- artifact hygiene;
- Comet evidence;
- blockers and next valid attacks;
- Android app handoff status.

## 23. Acceptance Gate Matrix

The final gate must answer each row with `pass`, `fail`, `blocked`, or `not_applicable_non_promoted`.

| Gate | Required For Maximal Pass |
| --- | --- |
| Phone Termux authority runtime | pass |
| Valid Phase 1 `PQA1` input | pass |
| Real Gemma4 embedding artifact | pass |
| Dense Rademacher JL `k=256,d=2560` | pass |
| PJP1 v1 output | pass |
| Native hot path | pass |
| Python path demoted to oracle | pass |
| No runtime JL matrix construction in hot path | pass |
| Record-local 128-slot packet sealing | pass |
| Pad/loss/role preservation | pass |
| Independent verifier | pass |
| Large sample counts explicit | pass |
| Hot-loop allocation audit instrumented | pass |
| 100k throughput >= 100k real tokens/sec | pass |
| 1M throughput >= 100k real tokens/sec | pass |
| Native speedup >= 3x previous Python baseline | pass |
| Roofline/profile analysis | pass |
| Comet logging | pass |
| Forbidden payload scan | pass |
| Root README untouched | pass |
| Nonclaims explicit | pass |

Any required row that is not pass blocks `phase2b_native_maximal_closure_pass`.

## 24. Android App Relationship

The Android/REDMAGIC app stream is one phase behind and owns accepted-mode/Game Mode/Game Space hardening.

Phase 2-B Termux execution does not wait for the app stream.

Phase 2-B must not claim:

- Android app integration;
- Game Mode benefit;
- Game Space privilege benefit;
- accepted-mode throughput.

After Termux Phase 2-B has a native correctness/performance result, it must produce a compact app handoff:

- `PJP1` schema;
- JNI-facing field map;
- native packetizer build notes;
- safe tiny fixture;
- verifier commands;
- nonclaims and known blockers;
- app agent startup prompt.

Do not hand off a fake finish. If Phase 2-B is still performance-failed, hand off as reference/floor/blocker only.

## 25. Startup Discipline

The fresh Termux agent must operate autonomously. It should not ask the user whether to proceed after each subgate. It should use its mandate to research, build, test, profile, repair, falsify, and continue.

It may stop only when one terminal status is real.

It must not stop after:

- reading docs;
- writing a plan;
- creating directories;
- compiling a scalar baseline;
- passing smoke;
- passing 10k;
- matching Python correctness while missing performance;
- identifying JL as the bottleneck;
- logging to Comet;
- making a good-looking mirror.

The agent's job is not to produce a pleasant report. Its job is to move the authority boundary toward the hardware limit and tell the truth when it cannot.

## 26. Final Culture Lock

Do not be satisfied by the fact that the previous Phase 2 made a 9 GB file.

Do not be satisfied by the fact that it used real Gemma4 embeddings.

Do not be satisfied by the fact that Comet and hygiene passed.

Those are foundations. They are not maximal closure.

The current governing objective is native phone-side Phase 2 performance closure.

If the native path works, prove it.

If it is slower than the Python reference, say so and fix it.

If it is correct but below the floor, do not call it pass.

If the hardware cannot do it, prove the limit with measurements strong enough that another serious engineer would stop arguing.

Until then, continue.
