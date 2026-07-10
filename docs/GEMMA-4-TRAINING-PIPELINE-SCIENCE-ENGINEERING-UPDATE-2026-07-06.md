# Gemma 4 Training Pipeline - Updated Science And Engineering Concept Document

Date: 2026-07-06

Last updated: 2026-07-08

Repository: `/Users/Zer0pa/Polymat AI/Polymath-AI`

Source concept document: `/Users/Zer0pa/Polymat AI/Gemma 4 Training Pipeline .md`

Document class: science and engineering concept update, implementation audit,
and drift ledger.

## 0. Correction And Scope

This document is the corrected artifact requested by the user. The previous
artifact I produced drifted into an operational pipeline plan and used the
suggested Apex operating-plan path as if it were the target document. That was
wrong. The requested task was to create an updated science and engineering
version of the named Gemma 4 training pipeline concept document, using code,
history, implementation evidence, language/runtime choices, throughput metrics,
external benchmark context, and drift analysis.

Behavioral issue to record:

```text
Do not substitute a narratable operating-plan artifact for the requested
science-and-engineering concept update. When the user names a source document,
read that document as the source of truth, then update the concept against
actual implementation evidence and authority metrics.
```

This document does not modify the original source concept file. It preserves
that document as the embryonic minimum spec, then audits what the project
actually built across Phase 1, Phase 2, Phase 3, and Phase 4.

Raw-boundary rule: this document cites metadata, hashes, summaries, code paths,
and aggregate metrics only. It does not embed raw corpus rows, raw PQA/PJP
payloads, raw QNN tensors, raw theta binaries, raw phone metadata payloads,
stdout/stderr logs, model weights, private keys, or tokens.

## 1. Executive Verdict

The original source concept described a four-phase phone-native Gemma 4 E4B
training pipeline:

```text
Phase 1: CPU tokenization and ingestion
Phase 2: CPU FSM/JL packetization into fixed binary polar material
Phase 3: NPU/QNN/HTP forward read
Phase 4: GPU polar optimizer and adapter update
```

That concept was a minimum spec. The implementation history shows that Phase 1
and Phase 2 became substantially more engineered than the original sketch. They
are no longer merely "C++ tokenizer" and "C++ FSM/JL" ideas. They became a
native Android/Zig/C++/Kotlin Phase 1 materialization system and a native
C++/NEON Phase 2 PQA1-to-PJP1 packetization system with real Gemma E4B
embedding and dense Rademacher JL material.

Phase 3 and Phase 4 also became real, but they did not become the original
fully fused static megakernel. The actual Phase 3/4 stack is a set of
authority-first vertical slices:

- Python validators, report generators, and host/Termux orchestration.
- C++/QNN/HTP forward contracts and exporter/validator surfaces.
- C++/Vulkan/GLSL native theta-only update execution on Adreno.
- C++ C5 native decoder/logit runtime work for Gate E.
- Python Gate D/Gate E acceptance and falsification logic.

The latest science state is negative for promotion. The July 6 Gate E baseline
diagnostic already blocked promotion for the original C2 theta. The July 8
RedMagic/Termux phone-native JL C2 full27 authority run strengthened that
blocker: the polar surrogate improved, but the real decoder-token NLL regressed
more strongly.

```yaml
c1_gate_d2a:
  status: accepted
  accepted_scope:
    phone_local_forward_backward_continuation: true
    gated_fixed_heldout_learning_evidence: true
  acceptance_artifact_sha256: 4e06fcc06284315fdc61528bbd4a9583740fd826cef5ca4cf4ccfd1baea09d5b

c2_gate_d:
  polar_heldout_loss_delta: -2.613627669660673
  status: polar_surrogate_pass

prior_c2_gate_e:
  before_nll_per_token: 14.538868526231177
  after_nll_per_token: 14.541084249294583
  nll_delta_per_token: 0.0022157230634061165
  before_perplexity: 2061343.5279915193
  after_perplexity: 2065915.9581368894
  perplexity_delta: 4572.4301453700755
  status: falsified

e1_no_update_baseline:
  nll_delta_per_token: 0.0
  row_delta_stdev: 0.0
  status: scorer_runtime_noise_not_explanation

e2_random_theta_baseline:
  completed_seed_count: 4
  random_theta_deltas:
    - 0.0015742374546145281
    - 0.002711374664297889
    - -0.0022761499692689068
    - 0.00400865832950701
  trained_delta_inside_random_range: true
  status: trained_theta_not_directional_at_this_effect_size

jl_c2_gate_d2a:
  before_loss: 30906.645910614105
  after_loss: 30860.12747423278
  polar_heldout_loss_delta: -46.518436381324136
  heldout_packet_count: 2500
  evaluated_answer_bearing_steps: 2344
  theta_post_layer24_sha256: 118a96c02e04f8ae36156399bc696f29844c944335460272ea6b87f42a7daf66
  status: polar_surrogate_pass

jl_c2_gate_e_phone_native_full27:
  before_nll_per_token: 14.538868526231177
  after_nll_per_token: 14.555113501137114
  nll_delta_per_token: 0.01624497490593768
  before_perplexity: 2061343.5279915193
  after_perplexity: 2095103.4741836223
  perplexity_delta: 33759.94619210297
  record_count: 27
  token_count: 27
  status: falsified
  first_missing_green_field: gate_e_nll_regression
  blockers:
    - gate_e_nll_regression
    - gate_e_surrogate_direction_diverged
```

The right current claim is therefore:

```text
Polymath-AI has engineered a phone-native staged Gemma 4 E4B polar-training
pipeline with strong Phase 1/2 native materialization, real Gate D QNN/Adreno
polar heldout evidence, and a RedMagic phone-native Gate E decoder path that
currently falsifies the C2/JL C2 polar surrogate because token-level NLL and
perplexity regress under the sovereign authority metric.
```

The wrong claim would be:

```text
The full Gemma 4 model has been trained or improved on phone.
```

That is not supported.

Ground verification update, 2026-07-07:

- Git was fetched from `origin`. The local branch
  `gemma4-megakernel-native-training` is ahead of
  `origin/gemma4-megakernel-native-training` by 10 commits and behind by 0.
  This report file is currently untracked, and the worktree has substantial
  unrelated dirty/untracked material.
- ADB sees the connected Red Magic-class device as
  `FY25013101C8`, `product:NX789J-EEA`, `model:NX789J`,
  `device:NX789J`, Android 15, Qualcomm `SM8750`.
- The QNN graph boundary remains a gap. The verified QNN contexts and outputs
  are raw float hidden/activation surfaces with shape `[1,16,2560]`
  and 163,840-byte tensors. No Mac-local artifact or accessible ADB artifact
  was found that proves a QNN graph directly accepts the Phase 2 PJP1/binary-JL
  packet shape.
- The strongest current QNN context proof is report-backed for a layer-1
  forward island in Termux-private storage. Plain ADB cannot list that private
  path because `com.termux` is not debuggable. The active layer-0 WaveC exporter
  report is blocked and has no generated context.
- The only accessible `.qnn.bin` found by ADB is an older
  `gemma_hidden2560_relu.qnn.bin` smoke context under `/data/local/tmp`.
  Its `[1,16,2560]` shape is useful substrate evidence, but that ReLU graph is
  explicitly disallowed as full-Gemma authority evidence by the current code.

Ground verification update, 2026-07-08:

- The detached RedMagic/Termux phone-native JL C2 Gate E run completed 27
  before records and 27 after records under the 12-hour-per-arm supervisor.
- The final native scorer contract report passed production of token-NLL
  evidence, with `native_polar_consumed_by_logits=true`,
  `rank16_cartesian_materialization_used=false`, and
  `lm_head_or_unembedding_present=true`.
- The final Gate E authority report remained `falsified`: NLL per token moved
  from `14.538868526231177` to `14.555113501137114`, delta
  `+0.01624497490593768`.
- A new external-review report was added to the Gate E sequence:
  `docs/APEX-GATE-E-SCIENCE-REPORT-SEQUENCE-2026-07-06/05_APEX-GATE-E-PHONE-NATIVE-JL-C2-FULL27-FALSIFICATION-ENGINEERING-SCIENCE-REPORT-2026-07-08.md`.
- A handover for the next agent was added:
  `docs/APEX-GATE-E-SCIENCE-REPORT-SEQUENCE-2026-07-06/HANDOVER_FOR_NEXT_AGENT_2026-07-08.md`.

Phone-side provider access update, 2026-07-08:

- The phone-side Termux credential env file exists at
  `/data/data/com.termux/files/home/.termux_agent_env` and provider access
  works after sourcing it. No token values were printed, copied, or embedded
  in this document.
- File metadata: `envfile_present=true`, mode `-rw-------` / `600`,
  owner `u0_a536`, SHA-256
  `9874fec9b9998e9e210d32fc71b40c48cf42586cd44c48f9c529c9f9c2118c7f`.
- Keys present: `COMET_API_KEY`, `COMET_WORKSPACE`,
  `COMET_PROJECT_NAME`, `HF_TOKEN`, `HF_HUB_TOKEN`,
  `HUGGING_FACE_HUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN`.
- Termux provider checks after sourcing the file:
  GitHub API access works for login `Zer0pa-Architect-Prime`, id
  `246360014`; Hugging Face API access works for user `Architect-Prime` and
  org `Zer0pa`; Comet access works with visible workspace and project.
- Important Comet custody nuance: the phone env targets
  `zer0pa/mobile-polymath-ai-training`, while the latest Apex Gate E host-side
  logging used `zer0pa-imc/mobile-polymath-ai-training`. Both access checks
  can work, but current Apex custody should keep using or explicitly forcing
  `zer0pa-imc/mobile-polymath-ai-training` unless a specific older Termux lane
  expects `zer0pa/mobile-polymath-ai-training`.
- Phone `gh` is usable through `GH_TOKEN` from this env even if persistent
  `gh auth status` reports no stored login. Hugging Face should use env-backed
  Python/API calls until the stale phone `huggingface-cli` wrapper is repaired
  after the Python 3.12-to-3.13 drift.

## 2. Original Core Concept To Preserve

The source document's core architecture remains valuable:

- Fixed-shape token packets.
- Mechanical corpus segmentation rather than agentic routing.
- CPU/NPU/GPU plane separation.
- Binary/JL/polar material as a bandwidth-reduction hypothesis.
- Frozen base model, trainable adapter or residual plane.
- Layer-cyclic selective backpropagation rather than full vertical
  backpropagation.
- Angle/theta-only updates as an experimental polar adapter rule.
- Shared unified memory handoff between CPU, NPU, and GPU.
- Future static or recordable execution to reduce host orchestration overhead.
- Strict separation between hot-loop native execution and Python control-plane
  reporting.

The document's most important warning is still correct: this is not generic
fine-tuning. It is a mechanical training fabric intended to match a
PLE-dominated mobile Gemma E-series model to a Snapdragon heterogeneous SoC.

The core concept also contains hypotheses that must remain hypotheses until
proven:

- Binary-JL material can serve as a faithful QNN graph input.
- A QNN/HTP forward can consume that material without fidelity loss.
- A theta-only polar update can improve token-level language-model quality.
- OpenCL recordable queues can lock the full forward/backward/update loop.
- A 128-token fixed block can remain the production hot-loop shape.

The latest Gate E result falsifies the active C2/JL C2 surrogate signal. It
does not falsify every possible polar/JL/mobile-training design, but it blocks
promotion of the current theta state.

## 3. Actual Built Stack At A Glance

| Phase | Source concept | Actual engineered surface | Primary languages/runtimes | Current status |
| --- | --- | --- | --- | --- |
| Phase 1 | Native C++ Gemma BPE tokenizer | Imported canonical Zig tokenizer stream, exact Android child-exec path, C++ JNI bridge, Kotlin/Compose lab app, GBT1 table, PQA1 output | Zig, C/C++/NDK, Kotlin, Python harness | Strong native engineering; measured 60M+ token IDs/sec class under authority-like performance lanes |
| Phase 2 | C++ FSM and JL transformer | Native C++/NEON PQA1 parser, 128-slot packet sealer, dense Rademacher JL projection, PJP1 writer, geometry/oracle/readback reports | C++17/C++20, NEON, Python harness | Strong native engineering; source/binary drift must be reconciled before authority-scale promotion |
| Phase 3 | Fused NPU inference megakernel | QNN/HTP forward contracts, WaveC full-Gemma QNN validators/exporters, C++ decoder/runtime integration, phone-local bridge evidence | Python validators/orchestration, C++/QNN surfaces | Report-backed layer-1 raw-hidden QNN/HTP context proof and contracts; active layer-0 exporter blocked; not yet binary-JL QNN or full fused forward megakernel |
| Phase 4 | Fused GPU polar optimizer megakernel | C++/Vulkan theta-only update runner and GLSL shader, OpenCL scaffolds, C++ native-polar Gate E decoder/logit scoring | C++/Vulkan/GLSL/OpenCL, Python validators | Real native update/scoring path and RedMagic phone-native full27 Gate E path; no accepted fused OpenCL recordable-queue optimizer |
| Evaluation | Lightly implied | Gate D2A polar heldout, Gate E token NLL/perplexity, D3 fail-closed comparators | Python validators, C++ scorer | Gate E falsifies prior C2 and latest JL C2 polar surrogates |
| Android lab/app | Not in first sketch | REDMAGIC lab/gaming app with `android:appCategory="game"`, GameManager hooks, JNI bridges, native Phase 1 and Apex/Vulkan surfaces | Kotlin/Compose, C++ JNI | Valid operator/app direction; game/performance privilege remains a hypothesis |

Repo language footprint, excluding runtime/build/.venv/node_modules/git:

```text
python_files: 233
cpp_files: 26
h_files: 17
kotlin_files: 23
zig_files: 1
vulkan_comp_files: 2
opencl_cl_files: 1
selected source lines across app/native/integration/scripts/polymath_ai: 98499
```

Key implementation file sizes:

```text
phase1_qa_stream.zig: 1653 lines
phase2b_native_packetizer.cpp: 1287 lines
apex_vulkan_theta_update_runner.cpp: 799 lines
apex_vulkan_theta_update.comp: 69 lines
c5_full_decoder_runtime.cpp: 3744 lines
apex_gate_e.py: 1238 lines
apex_gate_d.py: 700 lines
```

The line-count takeaway is narrow: Phase 3/4 are not "just Python." Python is
the control, custody, and acceptance language. The accelerator and decoder
surfaces include substantial native C++ and shader code.

## 4. Phase 1 - Corpus/Input Materialization

### 4.1 Original Minimum Spec

The source concept described:

```text
Raw MegaScience Q/A text -> native C++ Gemma BPE tokenizer -> variable-length
token ID stream.
```

The later language discussion in the same source document correctly argued
that hot-loop phases should avoid garbage-collected runtimes and use native
systems languages for stable pointers, no hidden allocation, and low latency.

### 4.2 What Was Actually Built

Phase 1 became a stronger system than the original C++ tokenizer sketch.

Core files:

```text
apps/android-redmagic-lab/native_import/phase1_qa_stream_zig/phase1_qa_stream.zig
apps/android-redmagic-lab/native_import/phase1_qa_stream_zig/build_phase1_qa_stream.sh
apps/android-redmagic-lab/app/src/main/cpp/phase1_lab_engine.cpp
apps/android-redmagic-lab/app/src/main/cpp/polymath_lab_jni.cpp
apps/android-redmagic-lab/app/src/main/java/ai/zer0pa/polymath/lab/bridge/NativePhase1Bridge.kt
apps/android-redmagic-lab/app/src/main/java/ai/zer0pa/polymath/lab/data/Phase1NativeTokenizerEngine.kt
```

Actual engineering features:

- Zig native tokenizer stream with explicit libc/syscall-style interfaces.
- Heap-based BPE merge path with explicit metrics.
- Direct file IO, mmap/madvise hooks, pthread workers, and bounded buffers.
- GBT1 tokenizer table identity and hash discipline.
- Android app integration through C++ JNI.
- Kotlin/Compose lab surface for report-backed execution.
- Child-exec path for packaged native Phase 1 executable material.
- PQA1 material output with shard metadata and raw-boundary hygiene.
- REDMAGIC/Nubia performance-policy diagnosis separate from tokenizer
  correctness.

Important source identities from the Phase 1/2 external review:

```text
Canonical Phase 1 source sha256:
829da5e89cf2c787dd6e1e2f984e3f604216633900d6d5896c27260e8711adcb

GBT1 tokenizer table sha256:
5887e29db2618b21fd9db1358c7f6db5bb7efffab54c16ba0643b46d7f3714ae

Delivered executable PIE sha256:
855c8392d627e1510a02b3bef43fe28dfc05c01837961d0451c27885d258a9fe
```

### 4.3 Phase 1 Throughput

Historical high-performance Phase 1 measurements:

| Run class | Result |
| --- | ---: |
| Termux promoted 1M baseline | `62,634,625.4288` token IDs/sec |
| Standard APK best no-sampler | `54,458,665.3173` token IDs/sec |
| Standard APK sampled | `53,923,860.4438` token IDs/sec |
| Nubia whitelist no-sampler best | `60,640,010.8813` token IDs/sec |
| Nubia whitelist repeat best | `60,472,837.6189` token IDs/sec |
| Full C1 diagnostic app/native run | `2,600,200` token IDs/sec |

Full C1 diagnostic Phase 1 facts:

```yaml
records_selected: 50994
token_ids: 2130785
records_per_sec: 62228.1
token_ids_per_sec: 2600200
workers: 8
scheduler: byte_greedy
qai1_file_count: 8
pqa1_total_bytes: 11124986
forbidden_payload_scan: pass
```

The drop from the synthetic/high-performance benchmark class to the full-C1
diagnostic is expected: the full-C1 path includes app/native orchestration,
real selected corpus material, PQA1 output, and custody/report overhead. It is
not the same benchmark as the tight 1M token-ID baseline.

### 4.4 Benchmark Context

External tokenizer references are useful only as calibration, not direct apples
to apples comparisons:

- Hugging Face Tokenizers describes Rust-backed "Fast" tokenizers and claims
  less than 20 seconds to tokenize 1 GB on a server CPU in the project README.
- OpenAI `tiktoken` reports 3-6x speedup versus a comparable open-source GPT-2
  tokenizer benchmark measured on 1 GB of text.

Those references use server CPU and text-throughput/tokenizer-library
benchmarks, not RedMagic phone PQA1 materialization. The defensible comparison
is qualitative:

```text
Phase 1 reached serious native-tokenizer throughput on a phone, but its
numbers should be reported in the project's own token-ID/sec and PQA1/sec
terms unless a standardized bytes/sec tokenizer benchmark is reproduced.
```

### 4.5 Innovation And Drift

Positive engineering drift:

- Zig moved from a language idea to real Phase 1 source.
- The app is not a toy wrapper; it includes native bridge, hashes, telemetry,
  high-performance policy evidence, and report custody.
- REDMAGIC/Nubia performance behavior was tested as a real device-policy
  variable, not guessed.

Unresolved or regressive drift:

- The source concept expected a clean C++ native tokenizer artifact. The actual
  stack is better but more complex: Zig source, C++ JNI, Kotlin app, Python
  harnesses, and packaged child-exec.
- Full-C1 APK parity was recorded as `not_checked_in_apk_run`; do not promote
  it as exact delivered-APK parity.
- Standard external tokenizer benchmarks have not been reproduced in a directly
  comparable benchmark harness.

## 5. Phase 2 - Packetization, FSM, JL, And PJP1

### 5.1 Original Minimum Spec

The source concept described:

```text
Variable-length token IDs -> C++ FSM -> 128-token blocks -> JL transform ->
binary polar tensor meal in shared memory.
```

The later embedded Phase 2 language ADR argued for C++, Rust, or Zig, with
Zig as an elegant hot-loop candidate because the Rademacher projection matrix
could be compile-time material.

### 5.2 What Was Actually Built

Phase 2 is currently implemented as native C++ with NEON.

Core files:

```text
native/polar_phase2_packetizer/phase2b_native_packetizer.cpp
native/polar_phase2_packetizer/build_phase2b_native_packetizer.sh
scripts/termux/run_polar_phase2b_native_closure.py
scripts/termux/run_phase2_c1_smoke.py
polymath_ai/polar/pjp1.py
tests/test_pjp1_contract.py
```

Actual engineering features:

- PQA1 list reader and PQA1 stream validation.
- Fixed 128-slot packet sealing.
- Gemma4 E4B f16 input embedding consumption.
- Dense Rademacher JL projection with `k=256,d=2560`.
- Bitpacked polar input/target/pooled-answer sections.
- PJP1 v1 header and section writer.
- SHA and artifact identity emission.
- Geometry/sample/oracle/readback validation.
- Multi-threaded record ranges.
- AArch64 NEON projection kernels using `float32x4_t`, `vld1q_f32`,
  `vmlaq_f32`, and tile reuse.

Selected implementation constants:

```text
kVocabSize: 262144
kEmbedDim: 2560
kJlDim: 256
kPacketLen: 128
kTokenProjectionTile: 16
```

Ground-checked Phase 2 output boundary:

```text
PJP1 packet length: 128 slots
JL logical dimension: 256
Gemma embedding source dimension: 2560
token_ids: [packet_count,128] u32
roles: [packet_count,128]
bitpacked polar input/target: [packet_count,128,32] bytes
logical polar input/target: [packet_count,128,256] bits
pooled-answer section: bitpacked 256-bit polar material
```

This is not the same tensor contract as the current QNN forward-island surface.
The present accepted/report-backed QNN tensor boundary is raw float32 hidden
material shaped `[1,16,2560]`, not direct PJP1 packet material.

Promoted C1 material identities:

```text
Gemma4 E4B f16 input embedding sha256:
b57e1e756f32d02c1aaad6c5c868f975f53b0938e0a04ed546804ed9c7d4ca7b

Dense Rademacher JL k=256,d=2560 sha256:
1b1f9de3dd6fbdf9597240eeeb08a6b482b33f1ae4d127e730222750cdf92a79
```

### 5.3 Phase 2 Throughput

Historical Phase 2 measurements:

| Run class | Result |
| --- | ---: |
| Python/NumPy 1M reference | `18,517.112` real tok/sec |
| Phase 2-B native 100k | `462,598` real tok/sec |
| Phase 2-B native 1M | `598,675` real tok/sec |
| Phase 2-C failed diversity baseline 100k | `69,798.7` real tok/sec |
| Phase 2-C optimized high-diversity 50k | `347,915` real tok/sec |
| Phase 2-C optimized high-diversity 100k | `271,713` real tok/sec |
| Full C1 diagnostic total | `363,294` real tok/sec |
| Full C1 diagnostic native process | `778,395` process real tok/sec |
| Full C1 diagnostic cache-inclusive process | `388,893` real tok/sec |

Full C1 diagnostic facts:

```yaml
source_records: 50994
source_real_token_count: 2130785
unique_projected_token_count: 65139
packet_count: 50994
slot_count: 6527232
pjp1_bytes: 461805760
native_packetizer_threads: 8
writer: phase2b_native_cpp_neon_writer_v1
jl_kernel: group4_cached_promoted
projection_kernel: single_token_k4_parallel_exact_dense_rademacher
input_projection_cache_reuse_factor: 32.7114
```

The native Phase 2-B 1M number is roughly 32x the Python/NumPy 1M reference in
the project's own measured terms:

```text
598675 / 18517.112 ~= 32.3x
```

That is the clearest internal benchmark win in the current stack.

### 5.4 Benchmark Context

There is no standard external benchmark for:

```text
PQA1 -> 128-token Gemma E4B embedding lookup -> dense Rademacher JL ->
bitpacked PJP1 polar packetization
```

Therefore Phase 2 should be benchmarked against:

- its own Python/NumPy reference;
- cold and warm native runs;
- high-diversity stress runs;
- real-corpus C1/C2/C3/C4 runs;
- PJP1 readback/oracle/geometry correctness;
- Phase 3 consumer staging throughput;
- total end-to-end tokens/sec after QNN and update consumption.

External tokenizer benchmarks do not measure JL packetization. External mobile
training benchmarks do not measure this corpus-to-PJP1 data plane. The best
claim is internal: the C++/NEON native packetizer is materially faster than the
Python/NumPy reference while preserving the PJP1 contract.

### 5.5 Innovation And Drift

Positive engineering drift:

- Phase 2 exceeded the source concept through real PQA1/PJP1 formats,
  real Gemma embedding material, dense Rademacher identity, NEON kernels,
  thread sharding, and validation reports.
- The implementation chose C++/NEON rather than waiting for a hypothetical
  Zig/Rust rewrite, which was correct given Qualcomm/Android toolchain reality.
- The high-diversity performance collapse was identified and repaired.

Unresolved or regressive drift:

- The source concept's elegant "Zig hot loop + Rust buffer owner" architecture
  was not the final built Phase 2 stack.
- The full-C1 diagnostic found source/build/binary drift between a canonical
  host source snapshot and the executed Termux source/binary.
- Authority-scale Phase 2 promotion should not happen until that drift is
  reconciled by recovering, committing, or superseding the executed source and
  rerunning the gate.

Near-term decision:

```text
Do not rewrite Phase 2 in Rust or Zig before resolving source/binary drift and
Gate E science. Keep C++/NEON as the measured hot path, then revisit Zig/Rust
only if it removes real ownership or determinism risk without sacrificing the
measured native speed.
```

## 6. Phase 3 - QNN/HTP/Gemma Forward

### 6.1 Original Minimum Spec

The source concept described:

```text
128-token binary block from shared memory -> fused NPU inference megakernel ->
activation tensor written back to shared memory.
```

The Phase 3 concept section also correctly identified:

- static graph compilation;
- persistent memory bindings;
- QNN/HTP backend;
- PLE as a first-class memory/bandwidth problem;
- fixed-shape dispatch;
- correctness harnesses against reference paths;
- token-ID vs projected-embedding graph-boundary as an open design decision.

### 6.2 What Was Actually Built

The actual Phase 3 stack is not "only Python." It is Python orchestration and
validation around native QNN/C++ surfaces.

Core Python contract/orchestration files:

```text
polymath_ai/polar/wavec_full_gemma_qnn.py
polymath_ai/polar/wavec_gemma_qnn_exporter.py
scripts/host/run_wavec_full_gemma_qnn_forward.py
scripts/host/run_wavec_gemma_decoder_to_qnn_exporter.py
scripts/host/run_apex_gate_d_qnn_native_continuation.py
scripts/host/run_apex_gate_d_chained_vulkan_continuation.py
scripts/termux/run_apex_packet_to_layer0_bridge.py
```

Core native/integration files:

```text
integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/src/backends/c5_qa_inference.cpp
integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/src/backends/c5_full_decoder_runtime.cpp
integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/src/backends/c5_decoder_math.cpp
integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/src/backends/opencl_layer_runner.cpp
integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/src/runner/phase11_runner.cpp
```

WaveC/QNN contract facts from the code:

```text
expected_shape: [1, 16, 2560]
expected_dtype: float32_le
expected_bytes: 163840
producer_kind: full_gemma_qnn_htp_forward_island
backend_execution_required: qnn_htp
backend_library_required: libQnnHtp.so
phase3_ready_claim: must be false in preflight-only reports
phase4_ready_claim: must be false in preflight-only reports
learning_claim: must be false unless downstream gates pass
```

The QNN exporter contracts bind:

```text
model_id: google/gemma-4-E4B
hidden_size: 2560
num_hidden_layers: 42
num_attention_heads: 8
num_key_value_heads: 2
head_dim: 256
intermediate_size: 10240
graph example: gemma4_e4b_ffn_residual_layer0_forward_island_seq16_hidden2560
```

2026-07-07 ground verification:

- The active layer-0 WaveC exporter report is blocked:
  `runtime/reports/polar_phase34_consumer_preflight/active_wave/gemma_decoder_to_qnn_exporter/gemma_decoder_to_qnn_exporter_report.json`
  has `status: "blocked"`, `context_generated: false`,
  `uses_real_restored_weights: false`, and no context path/SHA.
- The strongest current context proof is the Gate C layer-1 report:
  `runtime/reports/apex_heterogeneous_cell/gate_c_layer1_context_proof_execution_20260704T_single_bounded_attempt/gate_c_layer1_qnn_context_proof_execution_report.json`.
  It records graph
  `gemma4_e4b_ffn_residual_layer1_forward_island_seq16_hidden2560`,
  input/output shape `[1,16,2560]`, `QNN_DATATYPE_FLOAT_32`,
  context bytes `157982720`, context SHA
  `68f1e87f8654d75205ab44bac261f7a71b4119259573b0956ad87e19bcf9158a`,
  `dsp_supported: true`, `hexagon_architecture: "V79"`, emitted QNN output,
  and no observed CPU fallback. It also records that full Gate C execution was
  not authorized.
- The report's phone context path is inside Termux private storage:
  `/data/data/com.termux/files/home/polymath_gate_c_qnn_export/layer1_ffn_residual_20260703T_phase_engineering/context/gemma4_e4b_ffn_residual_layer1.qnn.bin`.
  Plain ADB could not directly list that path because `com.termux` is not
  debuggable.
- No Mac-local `.qnn.bin`, `.ctx`, `.serialized`, `.dlc`, `.onnx`, or `.gguf`
  production context artifact was found under `/Users/Zer0pa/Polymat AI`.
- ADB did find one accessible QNN context-like file:
  `/data/local/tmp/polymath_gemma4_gate/phase13/20260524T210920Z_phase13_gemma4_only_heterogeneous/p13f/htp/relu/context/gemma_hidden2560_relu.qnn.bin`.
  Its context info reports graph `gemma_hidden2560_relu` with input/output
  shape `[1,16,2560]`. This is only smoke/substrate evidence because the
  current validators explicitly disallow ReLU/identity smoke graphs as
  full-Gemma authority evidence.

### 6.3 What Phase 3 Did Not Yet Become

The original binary-JL QNN concept is not yet closed.

Current unresolved drift:

- Actual authority QNN forward surfaces use 16-token windows in several Gate D
  paths, not the source concept's 128-token block as a fused production graph.
- The built QNN surface is a forward-island/bridge system, not a full fused
  Gemma E4B megakernel.
- No verified Mac-local or accessible-ADB phone-local QNN graph was found that
  directly accepts the Phase 2 PJP1/binary-JL output boundary. Phase 2 produces
  128-slot bitpacked JL/polar packet material; the accepted/report-backed QNN
  boundary remains raw float32 hidden material shaped `[1,16,2560]`.
- Binary-JL materialization has been measured as an ablation, but binary-JL
  execution inside a QNN context is not accepted.
- PLE stall fraction hooks were reported absent in the C2 retrofit.

Layer-24 JL materialization ablation from the Gate E falsification report:

```yaml
raw_embedding_bytes: 169328640
binary_jl_bytes: 705536
byte_ratio: 240.0
raw_ms_per_step: 20.315566251088534
binary_ms_per_step: 0.05232968069666183
wall_clock_ratio: 388.2226296936776
binary_jl_qnn_execution_claim: false
```

That is a meaningful materialization result. It is not a QNN execution result.

### 6.4 Phase 3 Throughput Context

Latest C3 throughput checkpoint:

```yaml
steps_per_hour: 866.7961108857289
window_tokens_per_step: 16
tokens_per_second: 3.8524271594921284
c3_projected_wall_clock_hours: 64.76494217612007
c3_projected_wall_clock_days: 2.698539257338336
start_full_c3: false
```

This should not be compared directly to pure inference/pre-fill benchmarks. It
is an end-to-end authority pipeline checkpoint with QNN forward, native update,
metadata custody, heldout discipline, and Gate E context. It is nevertheless a
real warning: the current Phase 3/4 route is far too slow for blind full C3/C4
continuation.

External context:

- ONNX Runtime's QNN Execution Provider documents QNN as a hardware
  accelerated execution provider for Qualcomm chipsets using QNN/QAIRT and
  supported accelerator backends.
- The mllm-NPU/llm.npu research line reports more than 1,000 tokens/sec
  mobile NPU prefilling for a billion-sized model under an inference-specific
  system. That is not a training comparison, but it shows the scale of the
  throughput gap between pure NPU inference systems and the current
  authority-training path.

### 6.5 Innovation And Drift

Positive engineering drift:

- Phase 3 became gate-bound rather than a standalone demo.
- The code rejects Qwen/SmolLM/identity/ReLU graph drift for Gemma authority
  reports.
- QNN identity, context path, backend library, tensor shape, data movement, raw
  boundary, and nonclaim linting are explicit.
- C++ decoder/runtime integration exists downstream of the QNN path.

Regressive or unresolved drift:

- The source concept's 128-token binary block has not become the accepted QNN
  production graph boundary.
- The graph boundary is still not settled: token IDs, embeddings, raw hidden
  tensors, and binary-JL each imply different fidelity and performance risks.
- PLE-aware staging remains more concept than accepted evidence.
- Throughput is too low for full corpus continuation without decomposition and
  batching/graph improvements.

## 7. Phase 4 - Native Training, Theta Update, And Gate E

### 7.1 Original Minimum Spec

The source concept described:

```text
Activation tensor + textbook answer -> Adreno GPU fused OpenCL optimizer ->
layer-cyclic selective backpropagation -> polar angle update -> adapter state
written back to memory.
```

It specifically imagined:

- OpenCL fused optimizer megakernel.
- K4a loss, K4b LCSB gradient, K4c polar AdamW update.
- `cl_qcom_recordable_queues`.
- Shared UMA buffers.
- Device-side layer cycle counter.
- Sparse adapter-only gradients.
- Periodic UFS checkpointing rather than per-step writes.

### 7.2 What Was Actually Built

The accepted Gate D update path is narrower and more concrete:

```text
C++ Vulkan runner + GLSL compute shader -> theta-only polar update
```

Core native files:

```text
native/apex_heterogeneous_cell/apex_vulkan_theta_update_runner.cpp
native/apex_heterogeneous_cell/apex_vulkan_theta_update.comp
native/apex_heterogeneous_cell/apex_vulkan_theta_adapter.cpp
native/apex_heterogeneous_cell/apex_vulkan_theta_update_spv.h
native/apex_heterogeneous_cell/apex_vulkan_ledger_probe_main.cpp
```

Android app bridge:

```text
apps/android-redmagic-lab/app/src/main/java/ai/zer0pa/polymath/lab/bridge/NativeApexBridge.kt
apps/android-redmagic-lab/app/src/main/cpp/polymath_lab_jni.cpp
```

The JNI native contract explicitly reports:

```yaml
schema_version: native_apex_theta_contract_v1
status: linked
jni_binding: true
source_contract: apex_theta_only_vulkan_adapter_source_v1
update_scope: theta_only
backend: Adreno/Vulkan
opencl_claim: false
requires_qnn_vulkan_sha_equality: true
requires_answer_mask: true
requires_magnitude_invariant: true
requires_theta_mutation: true
requires_vulkan_dispatch_ledger: true
```

The current Vulkan shader uses:

```text
kSeq: 16
kHidden: 2560 in runner
adapter_elements: 256 in shader push constants
prediction: qnn_values[slot * 2560 + dim] + theta
error: prediction - target
delta: -learning_rate * error
theta_post[dim] = theta + accumulated delta over active answer slots
```

That is a real native theta-dependent update. It is not full backpropagation
through Gemma. It is not OpenCL. It is not AdamW. It is not a fused
recordable-queue megakernel.

OpenCL surfaces exist but are not the accepted Phase 4 authority path:

```text
integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/src/backends/opencl_layer_runner.cpp
integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/src/runner/opencl_recordable_queue_probe.cpp
polymath_ai/polar/phase4_bridge_cell.py
native/polar_phase34_consumer_preflight/phase34_native_pjp1_consumer_preflight.cpp
native/polar_phase34_consumer_preflight/phase34_pjp1_i8_staging_bench.cpp
```

### 7.3 Gate D Phase 4 Metrics

C1 accepted Gate D2A aggregate:

```yaml
before_loss: 27393.12386942226
after_loss: 27090.22732081249
loss_delta: -302.8965486097695
overlap_count: 0
heldout_packet_count: 2500
scanned_packet_count: 2500
evaluated_answer_bearing_steps: 2344
skipped_empty_answer_packets: 156
successful_qnn_steps: 2344
post_update_theta_sha256: 65b79f6c3127e15b26d756c352c5faa84afa81e99ff8a921f30e02b0a1b24c45
```

C2 Gate D polar heldout:

```yaml
before_loss: 3040.3564704610885
after_loss: 3037.742842791428
loss_delta: -2.613627669660673
status: passed_for_polar_surrogate_scope
```

JL C2 Gate D2A full2500 polar heldout:

```yaml
before_loss: 30906.645910614105
after_loss: 30860.12747423278
loss_delta: -46.518436381324136
heldout_packet_count: 2500
evaluated_answer_bearing_steps: 2344
skipped_empty_answer_packets: 156
theta_post_layer24_sha256: 118a96c02e04f8ae36156399bc696f29844c944335460272ea6b87f42a7daf66
status: gate_d2_phone_local_heldout_learning_evidence_pass
```

Gate D is meaningful as a phone-local mechanism and polar heldout gate. It is
not a language-model quality gate. The JL C2 result makes this distinction
more important, not less: the stronger polar loss improvement diverged from the
decoder-token NLL authority metric.

### 7.4 Gate E Native-Polar Decoder Work

The most important later Phase 4/evaluation engineering is Gate E.

Core files:

```text
integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/src/backends/c5_full_decoder_runtime.cpp
integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/src/backends/c5_decoder_math.cpp
scripts/host/run_apex_gate_e_native_polar_scorer.py
scripts/host/run_apex_gate_e_perplexity_evaluation.py
scripts/host/build_apex_gate_e_native_polar_policy.py
polymath_ai/polar/apex_gate_e.py
tests/test_apex_gate_e_native_polar_scorer.py
tests/test_apex_gate_e.py
```

This path resolved a real interface blocker. The old C5 scorer expected a
rank-16 Cartesian adapter payload; the accepted training state is native polar
theta. The project correctly rejected a rank-16 Cartesian shim as a promotion
path and instead made C5/Gate E consume native polar r/theta directly.

Native C5 decoder/runtime facts:

```text
layer_count: 42
hidden_size: 2560
vocab_size: 262144
intermediate_size: 10240
attention_heads: 8
key_value_heads: 2
head_dim: 256
adapter_rank comparator path: 16
native_polar_theta_elements: 256
native_polar_theta_bytes: 1024
qa_prompt_window_tokens: 16
adapter_mode_native_polar: native_polar
adapter_mode_rank16_comparator: rank16_cartesian_comparator
native_polar_contract_schema: apex_gate_e_native_polar_decoder_contract_v1
```

This is not merely Python. Python orchestrates and validates the scoring, but
the decoder/logit surface includes a large C++ runtime.

July 8 phone-native Gate E engineering added a production-capable RedMagic
Termux execution path:

```yaml
phone: RedMagic 10 Pro
device_serial: FY25013101C8
model: NX789J-EEA
execution_surface: termux_private_native_gemma4_layer_runner
phone_runner_sha256: b0e63365ee28b94026074a169e983f7035cc4e22906361f6c6067524d2a55072
per_arm_timeout_seconds: 43200
full27_before_records: 27
full27_after_records: 27
```

Engineering work completed for that path:

- added `--max-heldout-records` to the native C5 runner;
- added phone-native progress JSONL sidecars;
- added per-stage timing for tokenization, prompt sequence, adapter stream,
  PLE slice, CPU/OpenCL slices, final hidden stream, LM-head NLL, and
  prediction JSONL write;
- updated the host wrapper to summarize progress metadata without raw rows;
- used a detached Termux supervisor with fail-closed before-to-after sequencing;
- preserved raw prediction JSONL only in outside-git scratch.

One-record phone-native instrumentation showed the bottleneck:

```yaml
before_final_hidden_stream_seconds: 133.716
after_final_hidden_stream_seconds: 136.53
before_lm_head_nll_seconds: 2.57701
after_lm_head_nll_seconds: 2.56249
```

The full27 run needed detached supervision and long timeouts. SSH banner
timeouts and an apparent after-arm pause near record index 23 were treated as
monitoring anomalies, not restart grounds, because the runner later completed.

### 7.5 Gate E Authority Result

Gate E answered the question the source concept could not answer by itself:
does the polar update improve token-level language-model likelihood?

For the original C2 native-polar theta, the answer was no:

```yaml
c2_gate_e_native_polar:
  infrastructure_status: executed
  native_polar_consumed_by_logits: true
  rank16_cartesian_materialization_used: false
  lm_head_or_unembedding_present: true
  final_status: falsified
  first_missing_green_field: gate_e_nll_regression

c2_gate_e_authority_metric:
  before_nll_per_token: 14.538868526231177
  after_nll_per_token: 14.541084249294583
  nll_delta_per_token: 0.0022157230634061165
  before_perplexity: 2061343.5279915193
  after_perplexity: 2065915.9581368894
  perplexity_delta: 4572.4301453700755

surrogate_validity:
  polar_loss_delta: -2.613627669660673
  nll_delta_per_token: 0.0022157230634061165
  direction_agreement: false
  verdict: polar_nll_direction_diverge
```

This is the correct scientific blocker. Phase 4 currently has a real native
update path and a real native-polar decoder evaluation path, but the current
update objective does not promote because it worsens token-level NLL.

For the later JL C2 theta, the answer was also no, and the falsification was
stronger:

```yaml
jl_c2_gate_e_phone_native_full27:
  infrastructure_status: executed_on_redmagic_termux_native_runner
  native_polar_consumed_by_logits: true
  rank16_cartesian_materialization_used: false
  lm_head_or_unembedding_present: true
  native_scorer_status: gate_e_token_nll_passed
  authority_status: falsified
  first_missing_green_field: gate_e_nll_regression

jl_c2_gate_e_authority_metric:
  before_nll_per_token: 14.538868526231177
  after_nll_per_token: 14.555113501137114
  nll_delta_per_token: 0.01624497490593768
  before_perplexity: 2061343.5279915193
  after_perplexity: 2095103.4741836223
  perplexity_delta: 33759.94619210297
  record_count: 27
  token_count: 27

surrogate_validity:
  polar_loss_delta: -46.518436381324136
  nll_delta_per_token: 0.01624497490593768
  direction_agreement: false
  verdict: polar_nll_direction_diverge
```

This distinction must be preserved:

```text
native_scorer_status=gate_e_token_nll_passed means token-NLL evidence was
produced under the scorer contract.

authority_status=falsified means the science gate failed because NLL worsened.
```

### 7.6 Benchmark Context

External on-device training references support the general direction but do not
validate the current result:

- PockEngine supports sparse backpropagation and sparse model updates on edge
  devices, which is conceptually aligned with adapter-only or layer-limited
  update surfaces.
- Benchmark-On-Device-Training benchmarks mobile CPU/GPU training latency,
  energy, memory, utilization, and thermals for classical neural models.
- Qualcomm's OpenCL guide documents recordable command queues for repeated
  kernel enqueue sequences, matching the source concept's static-loop
  hypothesis.

These references are calibration, not evidence that Polymath's current
Gemma/QNN/Vulkan path improves a language model.

### 7.7 Innovation And Drift

Positive engineering drift:

- Phase 4 moved from concept to native Adreno/Vulkan execution.
- The Vulkan update is theta-dependent and bound to QNN tensor SHA continuity.
- Gate E native-polar decoder scoring prevents the project from overclaiming
  polar surrogate loss as language-model quality.
- The rank-16 Cartesian shim was rejected as an authority path.
- The RedMagic phone-native full27 Gate E path now works end to end for
  before/after evidence production.
- Metadata-only Comet logging and outside-git raw prediction custody were
  preserved for the final phone-native authority run.

Regressive or unresolved drift:

- The original OpenCL fused optimizer megakernel is not accepted.
- `cl_qcom_recordable_queues` remains a future optimization, not the current
  authority path.
- The source concept's LCSB gradient/AdamW/backprop mechanics are not what the
  current shader executes.
- The current shader operates over a narrow theta-only 256-element surface and
  16-token windows.
- Gate E falsifies both the prior C2 theta state and the latest JL C2 theta
  state as LM-quality improvements.
- The latest JL C2 result improved the polar surrogate more strongly while
  regressing decoder-token NLL more strongly, so surrogate/authority divergence
  is now a central scientific blocker.

## 8. C1/C2/C3/C4 Corpus Progression

| Corpus stage | Current state | Authority meaning |
| --- | --- | --- |
| C1 | Full Phase 1/2 diagnostic exists; Gate D2A accepted for phone-local continuation and polar heldout learning evidence | Valid narrow mechanism/heldout-polar result |
| C2 | Prior C2 Gate D polar pass exists; E1 no-update exact zero and E2 random theta classified the prior trained delta as random-theta-scale | Prior surrogate/update is not promotable |
| JL C2 | Gate D2A full2500 polar pass exists; RedMagic phone-native full27 Gate E NLL/perplexity falsifies promotion with `+0.01624497490593768` NLL/token regression | Latest surrogate/update is not promotable |
| C3 | Stage/readiness artifacts and throughput checkpoint exist; full continuation not started | Blocked by Gate E falsification and throughput |
| C4 | Split identity/readiness appears in reports; no promoted continuation | Not authorized |

Sequential custody expectations:

```text
C1 post-theta == C2 pre-theta
C2 post-theta == C3 pre-theta
C3 post-theta == C4 pre-theta
```

Each stage must independently bind:

- train material identity;
- heldout material identity;
- tokenizer/model identity;
- PQA1/PJP1 lineage;
- QNN context identity;
- GPU update binary/source identity;
- theta pre/post identity;
- overlap proof;
- Gate D polar metric;
- Gate E token-NLL/perplexity;
- raw-boundary and secret-boundary predicates;
- phone-side provider env identity when Termux performs GitHub, Hugging Face,
  or Comet operations;
- Comet numeric metadata if promoted.

Phone-side provider custody rule:

```text
source /data/data/com.termux/files/home/.termux_agent_env
```

That file can authorize GitHub, Hugging Face, and Comet from Termux, but reports
must cite only its presence, mode, owner, key names, SHA-256, and provider
visibility checks. Reports must not print or copy token values. For current
Apex evidence custody, force Comet target
`zer0pa-imc/mobile-polymath-ai-training` unless an older lane explicitly
requires `zer0pa/mobile-polymath-ai-training`.

Continuation across C1-C4 is not currently authorized as a progress claim. Gate
E falsification is the top blocker; C3 throughput remains a secondary blocker
after the science signal is repaired.

## 9. Android RedMagic Lab / Gaming App Direction

The Android app direction is real, not just conceptual.

Observed app facts:

```text
package: ai.zer0pa.polymath.lab
appCategory: game
ui: Kotlin/Jetpack Compose
native bridge: C++ JNI
Phase 1 bridge: NativePhase1Bridge
Apex/Vulkan bridge: NativeApexBridge
Game API integration: GameManager and GameState
benchmark state: FLAG_KEEP_SCREEN_ON and GAMEPLAY_UNINTERRUPTIBLE mode where supported
```

Files:

```text
apps/android-redmagic-lab/app/src/main/AndroidManifest.xml
apps/android-redmagic-lab/app/src/main/java/ai/zer0pa/polymath/lab/data/AndroidGameAuthorityController.kt
apps/android-redmagic-lab/app/src/main/java/ai/zer0pa/polymath/lab/bridge/NativeApexBridge.kt
apps/android-redmagic-lab/app/src/main/java/ai/zer0pa/polymath/lab/bridge/NativePhase1Bridge.kt
apps/android-redmagic-lab/app/src/main/cpp/polymath_lab_jni.cpp
```

Game/performance privilege hypothesis:

```text
On REDMAGIC/Nubia, being treated as a game and entering a performance/game
state may allow better CPU/GPU scheduling, higher frequency ceilings, lower
latency variance, or fewer background restrictions for sustained pipeline
execution.
```

This hypothesis is plausible because Phase 1 measurements showed material
differences between standard APK and Nubia whitelist/high-performance behavior.
It is not evidence for Phase 3/4 acceleration until tested under the actual
Gate D/Gate E workload.

Validation protocol:

1. Fix artifact identities: same APK, same native binaries, same corpus slice,
   same tokenizer/JL/QNN/GPU inputs.
2. Run A/B/A/B sequences across standard mode, Android game performance mode,
   Nubia whitelist/Game Space state, and screen/charging state.
3. Measure token IDs/sec, PJP1/sec, QNN forward wall time, Vulkan update wall
   time, Gate E scoring time, thermals, clocks, and failures.
4. Preserve raw outputs outside git; store only metadata reports and hashes.
5. Treat the result as a device-policy finding unless it passes the same
   authority metric gates.

## 10. Data Contracts And Raw Boundary

### 10.1 PQA1

Phase 1 output contract:

- token ID records;
- Q/A span metadata;
- segment/loss role metadata;
- shard count, bytes, and SHA identities;
- PQA1 raw payloads outside git;
- metadata-only reports in git.

### 10.2 PJP1

Phase 2 output contract:

- 128-slot packets;
- source record lineage;
- token IDs shaped `[packet_count,128]`;
- roles shaped `[packet_count,128]`;
- bitpacked polar input/target sections shaped `[packet_count,128,32]`
  bytes, equivalent to logical `[packet_count,128,256]` polar bits;
- bitpacked pooled-answer section for the 256-bit JL/polar material;
- JL identity;
- embedding identity;
- writer identity;
- PJP1 raw payloads outside git;
- readback/oracle/geometry reports as metadata.

This contract is not currently proven to be accepted directly by a QNN graph.
The verified/report-backed QNN tensor boundary is `[1,16,2560]` float32 hidden
material.

### 10.3 Phase 3 Forward Record

Required metadata:

- model id and revision;
- QNN/HTP backend identity;
- context path and SHA;
- graph name and tensor shape;
- input/output byte counts and SHA identities;
- no CPU fallback claim;
- raw QNN tensors outside git;
- phase3_ready/full_gemma/learning claims false unless gates authorize them.

### 10.4 Phase 4 Update Record

Required metadata:

- backend identity: Vulkan, OpenCL, or named alternative;
- exact native binary/source/kernel identity;
- QNN output SHA consumed;
- answer mask identity;
- theta pre/post identity;
- magnitude invariant;
- finite loss/update norm;
- raw theta binaries outside git;
- raw stdout/stderr excluded.

### 10.5 Gate E Token-NLL Record

Required metadata:

- fixed heldout split identity;
- model/tokenizer/lm-head identity;
- native-polar contract identity;
- before/after prediction record count;
- token count;
- before/after NLL total and per-token;
- before/after perplexity;
- overlap count;
- status: pass, falsified, or blocked_fail_closed;
- no hand-authored token-NLL authority JSONL.

### 10.6 Forbidden Payload Classes

Never embed or commit:

- raw corpus rows;
- raw backend observations;
- raw model payloads;
- raw PQA1/PJP1/QAI1 files;
- raw QNN tensors;
- raw theta binaries;
- raw phone payloads or raw phone metadata payloads;
- stdout/stderr logs;
- SDK binaries;
- model weights;
- env files, private keys, tokens, or service credentials.

## 11. Language Architecture Decisions

### 11.1 What The Built System Actually Uses

| Layer | Built language/runtime | Engineering reason |
| --- | --- | --- |
| Corpus/package/control | Python | Fast iteration, JSON metadata, report generation, validation, host orchestration |
| Phase 1 hot path | Zig | Explicit native control, low hidden runtime, pthread/file/mmap interfaces, measured fast tokenizer stream |
| Android app | Kotlin/Compose | Product/operator UI, Android GameManager/GameState hooks, report surfaces |
| Android native bridge | C++/JNI/NDK | Stable Android native ABI and bridge into Zig/native executable flow |
| Phase 2 hot path | C++/NEON | Direct AArch64 SIMD, files/mmap, high measured packetization throughput, Qualcomm-friendly toolchain |
| Phase 3 contracts | Python + C++/QNN | Python for fail-closed validation; C++/QNN for native graph/runtime surfaces |
| Phase 4 update | C++/Vulkan/GLSL | Native Adreno execution path that worked for theta update |
| Phase 4 future/fallback | C++/OpenCL | Qualcomm/OpenCL/recordable-queue concept remains relevant, not accepted |
| Gate E decoder | C++ + Python | C++ native decoder/logit runtime; Python scorer/report aggregation |

### 11.2 What Not To Rewrite Yet

Do not rewrite Phase 1/2 just to satisfy the older language discussion. The
current engineering problem is not that Zig/Rust were ignored. Phase 1 already
uses Zig. Phase 2 already has a measured C++/NEON path with strong throughput.
The immediate need is source/binary drift repair and Gate E science repair.

Rust remains attractive for future buffer ownership and no-alias invariants,
especially if a long-lived shared-memory ring buffer becomes a production
component. It is not currently the shortest path to Gate E repair.

Mojo/Nim/Go/Julia are not immediate hot-loop choices for this Android/QNN/Adreno
authority path:

- Go and other GC runtimes are poor fits for the strict hot-loop pointer and
  latency-variance sections.
- Julia is useful for scientific exploration, not Android hot-loop execution.
- Mojo is interesting for ML kernels but not yet proven in this repo's Android
  NDK/QNN/Adreno authority surface.
- Nim may be useful for small native tools, but it has no project evidence here.

### 11.3 Recommended Forward Language Stack

```text
Python: orchestration, custody, validators, reports, test harnesses.
Zig: keep Phase 1 tokenizer/materialization hot path where it is already strong.
C++/NEON: keep Phase 2 packetizer hot path until a measured replacement beats it.
C++/QNN: keep Phase 3 accelerator binding and generated/native graph surfaces.
C++/Vulkan/GLSL: keep the working native theta-update path.
C++/OpenCL: reintroduce only for recordable queues/fused optimizer after Gate E
  science and throughput decomposition justify it.
Kotlin/Compose: Android lab/operator app and game/performance-policy validation.
Rust: optional future ownership layer for stable buffer/ring contracts, not
  current hot-loop rewrite priority.
```

## 12. Drift Ledger

### 12.1 Positive Drift

- Phase 1 became stronger than the source concept: real Zig/native tokenizer,
  Android app integration, C++ JNI bridge, GBT1 table identity, PQA1 custody.
- Phase 1 measured throughput reached 60M+ token IDs/sec class in promoted
  high-performance lanes.
- Phase 2 became stronger than the source concept: C++/NEON, real Gemma
  embedding, dense Rademacher JL, PJP1, geometry/readback/oracle reports.
- Phase 2 native throughput materially beat the Python/NumPy reference.
- Phase 3 gained fail-closed QNN/Gemma identity contracts and backend drift
  rejection.
- Phase 4 gained a real Adreno/Vulkan theta-only update path.
- Gate E was added and correctly prevented polar-loss improvement from being
  mislabeled as language-model improvement.
- The July 8 RedMagic/Termux phone-native full27 Gate E path completed both
  before and after arms and produced a fail-closed authority report.
- The latest external-review report sequence was updated through report 05 and
  a next-agent handover was created.
- The Android lab app is becoming a real operational shell, not only a demo UI.

### 12.2 Regressive Or Unresolved Drift

- The original 128-token binary-JL QNN production graph boundary is not proven.
- Current Phase 3/4 authority windows are often 16-token windows, not the
  source concept's 128-token hot-loop.
- Phase 4 does not yet implement the original fused OpenCL recordable-queue
  optimizer.
- Current Vulkan update is theta-only and narrow, not full LCSB/AdamW/backprop.
- Gate E falsifies both the prior C2 polar surrogate and the latest JL C2 polar
  surrogate.
- The latest JL C2 polar loss improvement is directionally opposite the
  decoder-token NLL authority metric.
- C3 throughput is too low for blind full continuation.
- Phase 2 source/build/binary drift blocks authority-scale promotion until
  reconciled.
- PLE stall fraction measurement remains absent/incomplete for the current C2
  retrofit.

## 13. Roadmap From Here

### Stage 1 - Repair The Science Signal

Do not start full C3/C4 continuation as a promotional path while C2/JL C2 Gate
E is falsified.

Required work:

- diagnose why polar heldout loss improved while NLL worsened;
- rerun matched no-update and random-theta controls on the exact phone-native
  JL C2 surface for any new candidate;
- compare trained-theta and alternate alpha/layer schedules only through
  complete fail-closed Gate E authority reports;
- verify Gate E token accounting and decoder fidelity;
- determine whether the polar objective should be replaced, rescaled, or bound
  to a different merge site;
- preserve Gate E as sovereign for LM-quality claims.

### Stage 2 - Repair Throughput

Before full C3/C4:

- decompose QNN forward time, update time, decoder time, bridge time, and report
  time;
- test batching multiple 16-token windows per QNN invocation if the context
  permits it;
- decide whether to restore a 128-token graph boundary or formally accept a
  16-token micro-window contract;
- quantify PLE stall/access fraction rather than treating it as a concept;
- test game/performance app mode under the actual Gate D/E workload.

### Stage 3 - Reproduce Full Authority Path

Build one command that reproduces:

```text
D0 -> D1 -> D2 -> D2A -> Gate E -> Comet metadata -> custody manifest
```

The command must fail closed at the first missing authority field and must not
embed raw payloads.

### Stage 4 - Android App Shell Integration

Integrate the pipeline into the RedMagic lab app as an operator shell:

- phase engine states for P1/P2/P3/P4/Gate D/Gate E;
- artifact identity panel;
- throughput and thermal rail;
- raw-boundary status;
- Comet/export queue for metadata only;
- game/performance mode A/B controls;
- no raw tensor/corpus display.

### Stage 5 - Static/Fused Path

Only after Gate E passes and throughput bottlenecks are understood should the
team spend major effort on:

- binary-JL QNN context execution;
- 128-token fused graph restoration;
- OpenCL recordable queue path;
- fused K4a/K4b/K4c optimizer;
- device-side layer cycle counter;
- stable shared-memory ring with Rust or C++ ownership discipline.

## 14. Risks And Open Questions

High risks:

- Gate E may continue to show that the polar surrogate does not predict
  language-model improvement.
- Larger polar-heldout improvements may continue to produce larger
  decoder-token NLL regressions unless sign, scale, merge site, or objective
  coupling is repaired.
- Binary-JL may be excellent for materialization but unsuitable as a faithful
  QNN graph boundary.
- PLE memory behavior may dominate Phase 3 and block the hoped-for NPU
  efficiency.
- Vulkan theta updates may remain too narrow to produce useful LM improvement.
- OpenCL recordable queues may reduce dispatch overhead but not fix the
  scientific objective.
- Android/OEM game/performance policy may improve Phase 1 but not Phase 3/4.

Open questions:

- Should QNN consume token IDs, hidden embeddings, raw PJP1-derived tensors, or
  binary-JL material?
- Is 128-token fixed-block execution recoverable on the current QNN path?
- Which layer/merge sites produce NLL-aligned updates?
- Is theta-only sufficient, or does the trainable surface need magnitude,
  rank, or conventional adapter degrees of freedom?
- Can Gate E be made fast enough to run stage-wise without dominating the
  pipeline?
- What is the correct external benchmark harness for Phase 1 tokenization on
  phone: bytes/sec, token IDs/sec, or PQA1/sec?
- Should Rust own the eventual shared-memory lifecycle, or should C++ remain
  the only native systems layer for Qualcomm integration?

## 15. Explicit Nonclaims

This document does not claim:

- full Gemma 4 model training success;
- full Gemma 4 model-quality improvement;
- C2 or JL C2 Gate E pass;
- token-level NLL improvement;
- perplexity improvement;
- full C1/C2/C3/C4 continuation completion;
- binary-JL QNN execution;
- 128-token fused production QNN graph;
- a verified QNN graph that directly accepts Phase 2 PJP1 packet material;
- direct plain-ADB verification of Termux-private QNN contexts;
- fused OpenCL optimizer completion;
- `cl_qcom_recordable_queues` authority execution;
- app/game mode authority acceleration;
- Comet dashboard evidence beyond metadata-safe logged artifacts.

## 16. Evidence Index

Local source concept:

```text
/Users/Zer0pa/Polymat AI/Gemma 4 Training Pipeline .md
```

Local governing/evidence docs:

```text
AGENTS.md
docs/PRD-APEX-HETEROGENEOUS-CELL-END-TO-END-2026-07-03.md
docs/APEX-GATE-D-ENGINEERING-SCIENCE-REPORT-2026-07-05.md
docs/APEX-GATE-D-TO-E-ENGINEERING-SCIENCE-REPORT-2026-07-05.md
docs/APEX-GATE-E-NATIVE-POLAR-FALSIFICATION-ENGINEERING-SCIENCE-REPORT-2026-07-06.md
docs/APEX-GATE-E-SCIENCE-REPORT-SEQUENCE-2026-07-06/README.md
docs/APEX-GATE-E-SCIENCE-REPORT-SEQUENCE-2026-07-06/05_APEX-GATE-E-PHONE-NATIVE-JL-C2-FULL27-FALSIFICATION-ENGINEERING-SCIENCE-REPORT-2026-07-08.md
docs/APEX-GATE-E-SCIENCE-REPORT-SEQUENCE-2026-07-06/HANDOVER_FOR_NEXT_AGENT_2026-07-08.md
docs/ENGINEERING-EXTERNAL-REVIEW-PHASE1-PHASE2-C1-SMOKE-2026-06-29.md
docs/SCIENCE-ENGINEERING-EXTERNAL-REPORT-C1-FULL-DIAGNOSTIC-2026-06-29.md
docs/PHASE2C_CONTINUE_AFTER_HIGH_DIVERSITY_PASS_2026-06-29.md
```

Key implementation files:

```text
apps/android-redmagic-lab/native_import/phase1_qa_stream_zig/phase1_qa_stream.zig
apps/android-redmagic-lab/app/src/main/AndroidManifest.xml
apps/android-redmagic-lab/app/src/main/cpp/polymath_lab_jni.cpp
apps/android-redmagic-lab/app/src/main/java/ai/zer0pa/polymath/lab/data/AndroidGameAuthorityController.kt
apps/android-redmagic-lab/app/src/main/java/ai/zer0pa/polymath/lab/bridge/NativeApexBridge.kt
native/polar_phase2_packetizer/phase2b_native_packetizer.cpp
native/apex_heterogeneous_cell/apex_vulkan_theta_update_runner.cpp
native/apex_heterogeneous_cell/apex_vulkan_theta_update.comp
polymath_ai/polar/wavec_full_gemma_qnn.py
polymath_ai/polar/wavec_gemma_qnn_exporter.py
polymath_ai/polar/apex_gate_d.py
polymath_ai/polar/apex_gate_e.py
scripts/host/run_apex_gate_d_chained_vulkan_continuation.py
scripts/host/run_apex_gate_e_native_polar_scorer.py
integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/src/backends/c5_full_decoder_runtime.cpp
```

Ground verification, 2026-07-07:

```text
git branch: gemma4-megakernel-native-training
git remote: origin https://github.com/Zer0pa/Polymath-AI.git
git local-vs-origin after fetch: ahead 10, behind 0
report file status: untracked
device: FY25013101C8 / NX789J-EEA / NX789J / Android 15 / SM8750
adb-visible QNN context count by extension scan: one .qnn.bin smoke context
adb-visible raw .pjp1 files in searched Polymath roots: 0
termux_private_context_direct_adb_listing: not available, package not debuggable
```

Phone-side provider env verification, 2026-07-08:

```text
path: /data/data/com.termux/files/home/.termux_agent_env
envfile_present: true
mode: -rw------- / 600
owner: u0_a536
sha256: 9874fec9b9998e9e210d32fc71b40c48cf42586cd44c48f9c529c9f9c2118c7f
keys: COMET_API_KEY, COMET_WORKSPACE, COMET_PROJECT_NAME, HF_TOKEN,
  HF_HUB_TOKEN, HUGGING_FACE_HUB_TOKEN, GITHUB_TOKEN, GH_TOKEN
github_api: ok, login Zer0pa-Architect-Prime, id 246360014
huggingface_api: ok, user Architect-Prime, org Zer0pa
comet_api: ok, phone env target zer0pa/mobile-polymath-ai-training
current_apex_comet_target: zer0pa-imc/mobile-polymath-ai-training
token_values_documented: false
```

Ground-checked report artifacts:

```text
runtime/reports/polar_phase34_consumer_preflight/active_wave/gemma_decoder_to_qnn_exporter/gemma_decoder_to_qnn_exporter_report.json
runtime/reports/apex_heterogeneous_cell/gate_c_layer1_context_proof_execution_20260704T_single_bounded_attempt/gate_c_layer1_qnn_context_proof_execution_report.json
runtime/reports/polar_phase2_c1_smoke/c1_phase2_v4_full_20260629T173243Z/c1_phase2_v4_full_20260629T173243Z_native_packetizer_report.json
runtime/reports/apex_heterogeneous_cell/gate_d_acceptance_clean_c1_fullheldout_20260705T134658Z/gate_d_acceptance_report.json
runtime/reports/apex_heterogeneous_cell/gate_d1_clean_c1_train_20260705T120052Z/gate_d1_clean_qnn_native_result.json
runtime/reports/apex_heterogeneous_cell/gate_d2_clean_c1_fullheldout_20260705T120939Z/gate_d2_heldout_polar_result.json
runtime/reports/apex_heterogeneous_cell/gate_d2_e4b_c2_full2500_20260705T223535Z/gate_d2_heldout_polar_result.json
runtime/reports/apex_heterogeneous_cell/gate_e_native_polar_c2_20260705T223535Z/gate_e_token_nll_perplexity_report.json
runtime/reports/apex_heterogeneous_cell/gate_d2a_jl_c2_full2500_20260707T_reuse_complete/gate_d_acceptance_report.json
runtime/reports/apex_heterogeneous_cell/gate_e_phone_native_jl_c2_full27_20260708_timeout12h/native_polar_scorer_report.json
runtime/reports/apex_heterogeneous_cell/gate_e_phone_native_jl_c2_full27_20260708_timeout12h/gate_e_token_nll_perplexity_report.json
runtime/reports/apex_heterogeneous_cell/gate_e_phone_native_jl_c2_full27_20260708_timeout12h/gate_e_comet_logging_result.json
runtime/reports/apex_heterogeneous_cell/gate_e_phone_native_jl_c2_20260708_handover/HANDOVER_PHONE_NATIVE_GATE_E_20260708.md
runtime/reports/apex_heterogeneous_cell/c3_e4b_throughput_checkpoint_20260706T_after_gate_e/c3_e4b_throughput_checkpoint.json
runtime/reports/apex_heterogeneous_cell/c3_e4b_throughput_checkpoint_20260706T_after_gate_e/layer24_jl_binary_vs_raw_embedding_ablation.json
```

ADB-visible smoke/substrate context:

```text
/data/local/tmp/polymath_gemma4_gate/phase13/20260524T210920Z_phase13_gemma4_only_heterogeneous/p13f/htp/relu/context/gemma_hidden2560_relu.qnn.bin
```

External calibration references:

- Hugging Face Tokenizers: <https://github.com/huggingface/tokenizers>
- Hugging Face tokenizer docs: <https://huggingface.co/docs/transformers/en/main_classes/tokenizer>
- OpenAI tiktoken: <https://github.com/openai/tiktoken>
- ONNX Runtime QNN Execution Provider: <https://onnxruntime.ai/docs/execution-providers/QNN-ExecutionProvider.html>
- Android Game Mode API: <https://developer.android.com/games/optimize/adpf/gamemode/gamemode-api>
- Qualcomm Snapdragon OpenCL programming guide: <https://docs.qualcomm.com/bundle/publicresource/80-NB295-11_REV_C_Qualcomm_Snapdragon_Mobile_Platform_Opencl_General_Programming_and_Optimization.pdf>
- Benchmark-On-Device-Training: <https://github.com/UbiquitousLearning/Benchmark-On-Device-Training>
- PockEngine: <https://arxiv.org/abs/2310.17752>
- Fast On-device LLM Inference with NPUs / llm.npu: <https://arxiv.org/abs/2407.05858>
