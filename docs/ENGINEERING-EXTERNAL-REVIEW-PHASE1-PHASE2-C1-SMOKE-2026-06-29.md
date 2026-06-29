# Engineering External Review: Phase 1/2 Mobile Data Plane And C1 Smoke

**Date:** 2026-06-29  
**Scope:** Phase 1 ingestion/tokenization and Phase 2 PQA1-to-PJP1 packetization evidence for external engineering review  
**Device lane:** REDMAGIC / Snapdragon SM8750 phone authority path  
**Repository:** `/Users/Zer0pa/Polymat AI/Polymath-AI`  
**Status:** Phase 1/2 engineering evidence review; **not** Phase 3 authorization

## Executive Summary

The current system has credible phone-side evidence for two concrete data-plane components:

1. Phase 1 can run a C1 corpus slice through the Android app/native Phase 1 path and produce real PQA1 shards with hash/size metadata while keeping raw payloads out of git reports.
2. Phase 2 can consume those PQA1 shards through the native C++/NEON packetizer, use the real Gemma 4 E4B input embedding and dense Rademacher JL matrix, and emit a PJP1 artifact outside the git worktree.

The latest C1 run is an integration smoke, not an authority-scale pass. It validates the bridge across Phase 1 and Phase 2 on 64 C1 records. It does not satisfy the Phase 2 real-corpus authority gate, does not authorize Phase 3, and does not prove product-complete Phase 1 UI.

The engineering novelty is strongest in the deterministic native data plane: app/native artifact identity discipline, Android/OEM runtime-policy diagnosis, PQA1/PJP1 schema hygiene, real embedding/JL packetization, and hard separation between raw payloads and reviewable metadata. Phase 3/4 concepts remain planning hypotheses until the Phase 2 real-corpus gate and a separate Phase 3 PRD authorize execution.

## Authority Boundary

Accepted as evidence:

- C1 Phase 1 app/native smoke completed on 64 records.
- Phase 1 produced 8 PQA1 shards with app-reported hashes and sizes.
- PQA1 bridge into Termux-readable storage preserved hashes and counts.
- C1 Phase 2 native packetizer smoke completed with wrapper status `pass` and native status `pass`.
- Raw PJP1 was written outside the git worktree.
- No Comet/API logging, secrets, or raw payloads were required for this smoke.

Not accepted:

- No 100k/1M real Phase 2 authority pass.
- No Phase 3 handoff.
- No NPU/HTP execution claim.
- No learning, optimizer, or model-quality claim.
- No fused megakernel claim.
- No product-complete Phase 1 UI claim.
- No final `k`/projection promotion from real labels.

Phase 3 remains blocked until the real Phase 1 PQA1 material passes 100k and 1M real-corpus gates, PJP1 readback/oracle/collision/margin/Hamming validation passes on real outputs, final `k`/projection decisions are made from real-label evidence, NPU/app consumer preflight is repeated on real PJP1, and a separate PRD authorizes Phase 3.

## Phase 1 Architecture And Evidence

Phase 1 owns ingestion and tokenization into PQA1 material. The Android app path is `apps/android-redmagic-lab/`, package `ai.zer0pa.polymath.lab`, with `android:appCategory="game"` preserved. The backend integrates Kotlin/Compose, NDK/CMake, JNI, imported canonical Zig source, and an exact child-exec path for packaged Phase 1 executable material.

The important architectural result is a runtime-policy harness, not just a tokenizer app. The same Phase 1 material can be exercised through app/native paths to separate implementation drift from Android/OEM scheduling and DVFS policy.

Canonical Phase 1 identity recorded in `docs/ENGINEERING-PHASE1-ANDROID-NATIVE-RUNTIME-2026-06-27.md`:

| Artifact | SHA-256 |
| --- | --- |
| Canonical Phase 1 source | `829da5e89cf2c787dd6e1e2f984e3f604216633900d6d5896c27260e8711adcb` |
| GBT1 tokenizer table | `5887e29db2618b21fd9db1358c7f6db5bb7efffab54c16ba0643b46d7f3714ae` |
| Delivered executable PIE | `855c8392d627e1510a02b3bef43fe28dfc05c01837961d0451c27885d258a9fe` |
| Export manifest | `4f1720f804b28c56493769ffcfe80ad824c18c5fc95a7fd143d9d7165a19ae71` |

Historical Phase 1 performance evidence:

| Run class | Key result |
| --- | ---: |
| Termux promoted 1M baseline | `62,634,625.4288` token IDs/sec |
| Standard APK best no-sampler | `54,458,665.3173` token IDs/sec |
| Standard APK sampled | `53,923,860.4438` token IDs/sec |
| Nubia whitelist no-sampler best | `60,640,010.8813` token IDs/sec |
| Nubia whitelist repeat best | `60,472,837.6189` token IDs/sec |

The REDMAGIC/Nubia diagnosis is technically important. Standard APK child-exec presented `/top-app`, CPUs `0-7`, policy `0`, nice `0`, and uclamp max `1024`, yet lower frequency ceilings. Whitelist/high-performance policy recovered CPU0-5 `3.5328GHz` and CPU6-7 `4.32GHz` classes. The defensible claim is that the largest APK/Termux gap is OEM performance policy, not tokenizer substitution or simple JNI overhead.

### Latest C1 Phase 1 Smoke

Report root:

```text
runtime/reports/polar_phase1_c1_pipeline/c1_phase1_smoke_internal_20260629T143408Z_phase1_c1_pipeline_smoke
```

Summary:

| Metric | Value |
| --- | --- |
| status | `phase1_c1_smoke_complete` |
| app report run id | `2026-06-29T143414Z` |
| selected records | `64` |
| token IDs | `2674` |
| token IDs/sec | `219,869` |
| records/sec | `5,262.39` |
| material hash | `243f8b5349988ca0a288dcdc90445254c4b5dd6c3691a762cc683d4c72154f8d` |
| source manifest SHA-256 | `d0b83dd599041bc0d98caaa9201cd18e5edb185503fe799a9e113cd6cae3652b` |
| generation manifest SHA-256 | `60bdde88b5e6c23bb8cdcbae8de02da5b80e955bd50237df3ebbbb8736b27191` |
| forbidden payload scan | `pass` |
| remote PQA1 outputs present | `true` |
| high-performance settings final target match | `true` |

PQA1 shard metadata:

| Shard | Bytes | SHA-256 |
| --- | ---: | --- |
| `out_0000.pqa1` | `1924` | `c0d91d428c7038784d9cf77e3c9b1b37789db2f259a23ae1077fdcfe51e60bd8` |
| `out_0001.pqa1` | `1924` | `72c06aa9dd8e1f34fdf6d2818e23553eaae5cd6d12df140f8f0d6ea8a8a58e13` |
| `out_0002.pqa1` | `1880` | `28ae413590df63d21816d8b1dbdd0f67f9169931459f7165bb202ccd85e905f1` |
| `out_0003.pqa1` | `1884` | `f7268d4c1f091ca4056f76572acac1a790612cb8519f0c0c74c4ac63df2cb1b4` |
| `out_0004.pqa1` | `1860` | `2ad141f658c1c9b37fd174cd9ddaec64187ed2e3cf0dbaf2021123c7223fed81` |
| `out_0005.pqa1` | `1880` | `c3cd70fac480f2126bc22a5d03f00d379817243778ca88183ebbea45230b9ce5` |
| `out_0006.pqa1` | `1872` | `8b5f5e43722049d92407bcaab5ffd36a9ff4bec0774b27298ea5db0c15bc0715` |
| `out_0007.pqa1` | `1888` | `ec0642d553f15a86774e324725fba0e16d8a97e44e7fb21295e7504c94e7d1a2` |

Phase 1 caveat for review: the latest C1 smoke is a probe with `parity_state=not_checked_in_apk_run` and `promotion_eligible=false`. It proves C1 app-path integration and PQA1 metadata, but it must not be used as exact delivered-PIE parity evidence. The packaged executable hash observed in the C1 app report differs from the canonical delivered PIE hash.

## Phase 2 Architecture And Evidence

Phase 2 owns deterministic mechanical packetization:

```text
PQA1 -> native packet reader -> 128-slot packet sealing -> Gemma4 embedding lookup
     -> dense Rademacher JL projection k=256,d=2560
     -> bitpacked input/target/pooled-answer polar sections -> PJP1
```

The promoted native implementation lives at:

```text
native/polar_phase2_packetizer/phase2b_native_packetizer.cpp
native/polar_phase2_packetizer/build_phase2b_native_packetizer.sh
native/polar_phase2_packetizer/bin/phase2b_native_packetizer
```

Identities from Phase 2-C handoff:

| Artifact | SHA-256 |
| --- | --- |
| native source | `ba2d4dd48e2d9afeabf69b84019af0375aa739b26e982d69e8084a94a264c61f` |
| build script | `3c284c858aaa0d1e7697c4b63a12330d2e24d62a2391f109f34133463a631716` |
| native binary | `11c81138d181f09dd1a9a4715952c8a5357a91e3f1c1562f2fb9761d4d4c336a` |

Source identity caveat: the local working-tree packetizer source may not match
the source snapshot executed in older Phase 2-B reports or the latest C1 phone
run. Reviewers should bind each claim to the report-recorded source and binary
hashes, not to the current file alone. The latest C1 phone run records source
`ba2d4dd48e2d9afeabf69b84019af0375aa739b26e982d69e8084a94a264c61f` and
binary `11c81138d181f09dd1a9a4715952c8a5357a91e3f1c1562f2fb9761d4d4c336a`.

The important engineering transition is from Python/NumPy reference packetization to native phone-side packetization. Prior reported evidence includes:

| Run class | Result |
| --- | ---: |
| Python/NumPy 1M reference | `18,517.112` real tok/sec |
| Phase 2-B native 100k | `462,598` real tok/sec |
| Phase 2-B native 1M | `598,675` real tok/sec |
| Phase 2-C failed diversity baseline 100k | `69,798.7` real tok/sec |
| Phase 2-C optimized high-diversity 50k | `347,915` real tok/sec |
| Phase 2-C optimized high-diversity 100k | `271,713` real tok/sec |

The high-diversity Phase 2-C path uses exact dense Rademacher input-token projection reuse with a single-token k4 NEON cache preparation kernel across 8 threads. It clears useful engineering floors on synthetic/proxy material, but it remains blocked on real Phase 1 PQA1 training material. The strongest throughput numbers are stress-corpus and cache-sensitive; they are not a substitute for the real-corpus gate.

Promoted Phase 2 artifacts for the C1 smoke:

| Artifact | Path | SHA-256 |
| --- | --- | --- |
| Gemma4 E4B f16 input embedding | `/data/data/com.termux/files/home/polymath_polar_phase2/embeddings/gemma4_E4B_input_embedding.f16` | `b57e1e756f32d02c1aaad6c5c868f975f53b0938e0a04ed546804ed9c7d4ca7b` |
| embedding manifest | metadata hash only | `0bf2dc2ec4487c079da94d8c8a37f54bb7c45ed2f9a29dbbd73edc0ababaf8bd` |
| dense Rademacher JL `k=256,d=2560` | `/data/data/com.termux/files/home/polymath_polar_phase2/jl/gemma4_dense_rademacher_k256_d2560_i8.bin` | `1b1f9de3dd6fbdf9597240eeeb08a6b482b33f1ae4d127e730222750cdf92a79` |

### Latest C1 Phase 2 Smoke

Run label:

```text
c1_phase2_smoke_20260629T144238Z
```

Shared metadata/log directory:

```text
/sdcard/Download/polymath/polar_phase2_c1_smoke/c1_phase2_smoke_20260629T144238Z/
```

Raw output path, outside git:

```text
/data/data/com.termux/files/home/polymath_phase2_outputs/c1_phase2_smoke_20260629T144238Z/raw_c1_phase2_smoke_20260629T144238Z.pjp1
```

Wrapper/native result:

| Metric | Value |
| --- | --- |
| wrapper status | `pass` |
| native status | `pass` |
| native return code | `0` |
| PQA1 files consumed | `8` |
| source records | `64` |
| source real tokens | `2674` |
| packet count | `64` |
| slot count | `8192` |
| PJP1 bytes | `583,680` |
| PJP1 SHA-256 | `7ffb81ab1fc129fcaf7de84a50a196ebac30d366d49e59471486e51a323ee340` |
| PQA1 source SHA-256 stream | `bbef1fb60ffd76fffc7556b2e266258b6d80049e1c95a8faf7c925ddaf64a13d` |
| PQA1 list SHA-256 | `fe0bc428472e79f2f9d7dd95a99bb8a6c50f04d78c4f04897236104993a484e0` |
| PQA1 list inside git worktree | `false` |
| PJP1 inside git worktree | `false` |

Measured throughput for this small smoke:

| Metric | Value |
| --- | ---: |
| records/sec | `954.609` |
| real tokens/sec | `39,884.8` |
| process real tokens/sec | `288,891` |
| cache-inclusive process real tokens/sec | `46,165.9` |
| packets/sec | `954.609` |
| packet slots/sec | `122,190` |
| output MB/sec | `8.70604` |

Timing:

| Stage | Seconds |
| --- | ---: |
| scan/validate | `0.00082349` |
| projection cache prepare | `0.0486655` |
| output prepare | `0.000479375` |
| native process | `0.00925609` |
| flush/sync | `0.00753927` |
| sample hash | `0.000123854` |
| total | `0.0670431` |

The C1 smoke demonstrates that the end-to-end C1 path can cross Phase 1 and Phase 2 without raw payloads entering the repo. It does not demonstrate scale, production token diversity, final projection choice, Phase 3 consumer readiness, or model learning.

## Language And Runtime Decisions

The measured evidence supports a conservative language stack:

| Layer | Recommended language/runtime | Reason |
| --- | --- | --- |
| Phase 1 hot path | Zig/C/NDK integration as already built | Existing native path is measured and integrated with Android app packaging. |
| Phase 1 app/control surface | Kotlin/Compose + JNI/NDK | Matches Android product surface and lets the UI expose real report-backed state. |
| Phase 2 hot path | C++17/NDK or Termux native C++ with NEON | Current packetizer is measured, uses real embedding/JL artifacts, and has direct file/mmap-style control. |
| Orchestration and reports | Python 3.11 | Fast iteration, JSON/report generation, ADB/Termux control, low risk outside hot loops. |
| Verification/oracles | Python plus native readback where needed | Keeps correctness independent from the hot path. |
| Phase 3/4 exploratory kernels | C++/OpenCL/QNN SDK surfaces first | These are the available phone accelerator interfaces; language choice must follow SDK and driver reality. |

Rust and Zig remain credible candidates for bounded surfaces where memory safety or compile-time generation matters, but they are not promoted replacements for the measured Phase 2 C++ packetizer until they reproduce PQA1/PJP1 parity and match authority throughput. Mojo, Julia, Go, and Nim are not recommended for Phase 1-4 hot paths at this stage. Python remains valuable for corpus tooling, orchestration, and oracle generation, not for the runtime hot loop.

The definitive engineering rule is not "which language is fastest in general." It is whether the runtime can enforce stable addresses, no hot-loop allocation, raw binary schema control, accelerator SDK compatibility, and reproducible performance on the phone. C++ currently has the strongest evidence in Phase 2 because it already passed the native packetizer path.

## Phase 3/4 Planning Boundary

A new independent thread was created for user-managed Phase 3/4 exploration. That thread is planning context only. It is not Phase 3 execution authorization.

Phase 3 should own:

- QNN/HTP forward-read substrate.
- Declared graph boundary.
- Memory import/staging and copy-count measurement.
- Correctness versus OpenCL/PyTorch reference.
- Sustained latency and thermal profiling.
- Activation handoff contract for Phase 4.

Phase 4 should own:

- Adreno learning/update substrate.
- Loss boundary and adapter update parity.
- Frozen-weight integrity checks.
- Checkpoint cadence.
- Thermal behavior.
- Fused/recorded-sequence comparison against unfused OpenCL residual-adapter baseline.

Speculative ideas that require falsification before promotion:

- "Frictionless" NPU read.
- Normalization removal or constant-folded normalization claims.
- Polar theta-only optimizer.
- Layer-cyclic selective backpropagation.
- Zero-copy GPU/NPU handoff.
- Autonomous recordable-queue loop.
- Any SRHT/Lorenz/alternate-k replacement.
- Fused megakernel status.

## Required Falsification Tests

Phase 2 real-corpus gate:

- 100k and 1M real Phase 1 PQA1.
- At least 50k distinct token IDs.
- Throughput at or above `200,000` real tok/sec on the distinct-token production floor.
- PJP1 readback pass.
- Stratified oracle 100% bit-exact sampled packets.
- Collision duplicate-token fraction at or below `0.1%`.
- Margin/Hamming geometry no worse than proxy baseline without explanation.
- NPU/app consumer preflight repeated on real PJP1.

Phase 3:

- QNN/HTP Gemma E4B graph runs on phone without fallback.
- Exact graph boundary declared.
- Copy count measured.
- Output compared against OpenCL/PyTorch reference over fixed 128-token samples.
- HTP output must feed objective, gradient, update, or teacher path before any heterogeneous training claim.

Phase 4:

- Gradient/update parity versus unfused OpenCL or RunPod reference.
- Frozen base hashes stable before and after update.
- Finite gradients and stable checkpointing.
- Heldout non-regression.
- Dispatch count at least 2x lower or traffic at least 30% lower before "fused" promotion.
- Sustained thermal profile measured under repeated update loops.

## Externally Defensible Claims

Defensible:

- Phase 1 Android/native architecture exists and can execute the app-path C1 smoke with real PQA1 outputs and safe metadata.
- Historical high-profile APK Phase 1 runs reached roughly 60-61M token IDs/sec, while Termux 1M reference is about 62.63M token IDs/sec.
- The major APK/Termux gap is defensibly tied to REDMAGIC/Nubia DVFS/performance policy rather than tokenizer drift or simple JNI overhead.
- Phase 2 has a native phone-side C++ packetizer consuming PQA1, Gemma4 embedding, and dense Rademacher JL to emit PJP1.
- Latest C1 smoke proves 64-record C1 wiring from Phase 1 PQA1 through Phase 2 PJP1 with hashable artifacts and raw payload hygiene.

Not defensible:

- Final Phase 1 APK product promotion.
- Phase 2 real-corpus authority pass.
- Phase 3 readiness.
- NPU/HTP execution or training.
- Fused megakernel execution.
- Full Gemma4 learning or model-quality improvement.
- Strict zero-collision claims for `k=256`.
- Commercial-use corpus claims without license decisions.

## Review Artifact Index

Primary documents:

- `docs/ENGINEERING-PHASE1-ANDROID-NATIVE-RUNTIME-2026-06-27.md`
- `native/polar_phase2_packetizer/README.md`
- `runtime/reports/polar_phase2c_review/2026-06-29T094030Z-phase2c-handoff-integration-prep/READ_ME_FIRST_PHASE2C_HANDOFF.md`
- `runtime/reports/polar_phase2c_review/2026-06-29T094030Z-phase2c-handoff-integration-prep/ENGINEERING_HANDOFF.md`
- `runtime/reports/polar_phase2c_review/2026-06-29T094030Z-phase2c-handoff-integration-prep/REAL_CORPUS_GATE_SPEC.md`
- `runtime/reports/polar_phase2c_review/2026-06-29T094030Z-phase2c-handoff-integration-prep/PHASE3_NOT_READY.md`

Latest C1 evidence:

- `runtime/reports/polar_phase1_c1_pipeline/c1_phase1_smoke_internal_20260629T143408Z_phase1_c1_pipeline_smoke/phase1_c1_pipeline_smoke_summary.json`
- `runtime/reports/polar_phase1_c1_pipeline/c1_phase1_smoke_internal_20260629T143408Z_phase1_c1_pipeline_smoke/phase1_c1_remote_pqa1_manifest.json`
- `runtime/reports/polar_phase2_c1_smoke/c1_phase2_smoke_20260629T144238Z/` when present in the local mirror
- `/sdcard/Download/polymath/polar_phase2_c1_smoke/c1_phase2_smoke_20260629T144238Z/c1_phase2_smoke_20260629T144238Z_phase2_c1_smoke_wrapper_report.json`
- `/sdcard/Download/polymath/polar_phase2_c1_smoke/c1_phase2_smoke_20260629T144238Z/c1_phase2_smoke_20260629T144238Z_native_packetizer_report.json`

Raw artifacts intentionally excluded from this document:

- Raw `.qai1`, `.pqa1`, `.pjp1`.
- Gemma embedding tensor.
- JL `.bin`.
- APK/AAB/build outputs.
- Secrets and environment files.
