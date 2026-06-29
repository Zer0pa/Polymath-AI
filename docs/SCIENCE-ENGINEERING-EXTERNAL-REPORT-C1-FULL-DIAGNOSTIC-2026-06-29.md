# Science and Engineering External Report: Full C1 Phase 1 to Phase 2 Diagnostic

**Date:** 2026-06-29
**Repository:** `/Users/Zer0pa/Polymat AI/Polymath-AI`
**Branch:** `gemma4-megakernel-native-training`
**Report commit base:** `945d438 Add full C1 Phase 2 metadata report`
**Authority runtime:** REDMAGIC / `FY25013101C8` / `NX789J`
**Scope:** Full C1 source material through Phase 1 PQA1 generation, bridge, and Phase 2 native PJP1 packetization
**Status:** Full-C1 diagnostic pass; not 100k/1M Phase 2 authority; not Phase 3 readiness

## Executive Verdict

The team moved the supplied C1 material through the current Phase 1 -> Phase 2
pipeline on the authority phone path:

- Phase 1 consumed full C1 source material: `50,994` records and `2,130,785` token IDs.
- Phase 1 emitted `8` PQA1 shards, `11,124,986` total bytes, with recorded per-shard SHA-256 values.
- The PQA1 bridge copied those shards to phone shared storage for Phase 2 without pulling raw payloads into git.
- Phase 2 consumed the verified PQA1 list and emitted a raw PJP1 packet file outside git:
  `461,805,760` bytes, SHA-256 `e347676432fa7a76489f402f3c3e38ab492b6554f71930f14bc7d36ed1b3ecf5`.

This is the first useful full-C1 pipeline diagnostic from source material to PJP1
packets. It is not the governing 100k/1M Phase 2 authority gate, not Phase 3
authorization, and not learning or model-quality evidence.

## Authority Boundary

Accepted as evidence:

- Full C1 source identity, row count, and SHA-256 are recorded.
- Phase 1 app/native path processed all `50,994` selected C1 records.
- Phase 1 PQA1 shard metadata is complete and hash-addressed.
- Phase 1 -> Phase 2 bridge preserved shard count, total bytes, and list identity.
- Phase 2 native packetizer consumed all `8` PQA1 files and wrote PJP1 outside the git worktree.
- Phase 2 wrapper and native reports both returned `pass`.
- No raw C1, QAI1, PQA1, PJP1, embedding, JL matrix, model weight, secret, or env payload was committed.

Not accepted:

- No 100k or 1M Phase 2 authority pass.
- No Phase 3 execution authorization.
- No learning, optimizer, loss, convergence, or model-quality claim.
- No NPU/HTP execution claim.
- No UI product-completion claim.
- No C2 run in this report.

The scripts and report paths still contain legacy `smoke` labels. In this report,
`smoke` means wiring/diagnostic evidence unless an authority gate explicitly says
otherwise.

## Team Organization

| Lane | Responsibility in this event | Result |
| --- | --- | --- |
| Training Material Steward | Selected and identified the full C1 package and source bridge. | Full C1 accepted as source material: `50,994` rows, SHA-256 `4c8bb5a208d416bc4dae49ddf89e8e7845c459aef42b83ff15aac1a8aa76ce97`. |
| Engineering Orchestrator | Corrected runner identity and Phase 1 execution semantics. | Prevented the full-C1 runner from inheriting diagnostic warm sequences; established single-pass child-exec default. |
| Pipeline Integrator | Bound Phase 1 PQA1 outputs to Phase 2 packetization contract. | PQA1 list and bridge metadata made Phase 2 consumable without raw payloads entering git. |
| Execution Orchestrator | Ran Phase 1, bridge, and Phase 2 on the authority phone/Termux path. | Phase 1 and Phase 2 completed with evidence and raw outputs outside git. |
| Repo Custodian | Scoped custody for canonical evidence. | Relevant commits were pushed without broad-adding unrelated dirty files. |
| UI Engineer | Evidence surface consumer. | UI review remains downstream; current report provides truthful evidence boundaries. |

## Material Identity

| Field | Value |
| --- | --- |
| C1 package root | `/Users/Zer0pa/Polymat AI/corpus_packages/commercial/2026-06-27T041511Z/phase_C1_lexatlas_gemma4_v4_full_strict` |
| QA bridge input | `/Users/Zer0pa/Polymat AI/corpus_packages/commercial/2026-06-27T041511Z/phase_C1_lexatlas_gemma4_v4_full_strict/qa_bridge/phase_C1_full.qa.jsonl` |
| Input rows | `50,994` |
| Input SHA-256 | `4c8bb5a208d416bc4dae49ddf89e8e7845c459aef42b83ff15aac1a8aa76ce97` |
| Raw source kind | `lexatlas`: `50,994` |
| Normalized source kind | `dictionary`: `50,994` |
| Source-kind mapping | `lexatlas -> dictionary` |
| Selected record ID stream SHA-256 | `df39d21de923d98cb7b22f1c5ac343e3cb1d4212d2a0978d95178ca6f82dbc68` |
| Selected source SHA-256 stream | `c9771515a55e9f0d9f7701492d21670a17a0e84112165bf976adbd4b3d4aea57` |
| Package manifest SHA-256 | `ca8448755a0fe76c7edbeddc4aed78b197ba21bb4d28d2f004c0d287ab64da7f` |
| Phase 1 source manifest SHA-256 | `5cd0286b172095eba33e95509991884288d364ad7c55a4b4f22c180407bf88d5` |

Raw C1 JSONL stayed outside the repository.

## Engineering Changes Made Before the Full-C1 Pass

| Commit | Change | Why it mattered |
| --- | --- | --- |
| `f927880` | Fixed C1 full-package runner identity. | Bound the full runner to the selected C1 package and corrected limit handling so `0` means full package rather than an accidental empty or diagnostic subset. |
| `6b341bd` | Fixed C1 runner warm sequence default. | Stopped inherited diagnostic warm flags from causing repeated full-dataset passes before the measured run. Full C1 now defaults to one child-exec pass with warm sequences opt-in. |
| `945d438` | Added full C1 Phase 2 metadata report. | Preserved Phase 2 wrapper/native evidence and metadata hashes in the canonical repo while keeping raw payloads out of git. |

Root cause corrected: `CHILD_EXEC_WARM_FLAGS` leaked diagnostic warm-sequence behavior
into the full-C1 runner. That turned full material execution into repeated
pre-marker passes. The corrected run used `run_flags=16`, with native warm
sequences disabled.

## Phase 1 Full C1 Result

| Field | Value |
| --- | --- |
| Run label | `c1_phase1_v4_full_rerun_20260629T170920Z` |
| App run id | `2026-06-29T170931Z` |
| Package | `ai.zer0pa.polymath.lab` |
| Serial | `FY25013101C8` |
| Status | `phase1_c1_smoke_complete` |
| Records selected | `50,994` |
| Token IDs | `2,130,785` |
| Records/sec | `62,228.1` |
| Token IDs/sec | `2,600,200` |
| Run flags | `16` |
| Native warm sequence enabled | `false` |
| Native extended warm sequence enabled | `false` |
| Runtime sampler enabled | `false` |
| Workers | `8` |
| Scheduler | `byte_greedy` |
| QAI1 file count | `8` |
| QAI1 total bytes | `12,751,742` |
| Material hash hex | `bf6e8fcc5dae9bd331067559ced9803012e4806cfc571f8b4d99d9f23e414afb` |
| GBT1 tokenizer table SHA-256 | `5887e29db2618b21fd9db1358c7f6db5bb7efffab54c16ba0643b46d7f3714ae` |
| Generation manifest SHA-256 | `c8b0bd88ca55881503f1e74bb614016072a76f8d6c133a33166533e46439565a` |
| Forbidden payload scan | `pass` |
| Remote PQA1 all outputs present | `true` |
| High-performance settings final target match | `true` |
| APK parity state | `not_checked_in_apk_run` |
| App report root | `/sdcard/Android/data/ai.zer0pa.polymath.lab/files/reports/phase1/2026-06-29T170931Z` |
| Host report root | `runtime/reports/polar_phase1_c1_pipeline/c1_phase1_v4_full_rerun_20260629T170920Z_phase1_c1_pipeline_smoke` |

Phase 1 output is useful PQA1 material for Phase 2 diagnostics. The APK parity
state remains `not_checked_in_apk_run`, so this result must not be used as a
final exact delivered-APK parity claim.

## Phase 1 PQA1 Shards

| Shard | Record count planned | Bytes | SHA-256 |
| --- | ---: | ---: | --- |
| `out_0000.pqa1` | `6,374` | `1,390,766` | `d101994f9f43b50c2ece5872eb6432d092bebcc72655e93fec89e1e30a89a816` |
| `out_0001.pqa1` | `6,374` | `1,389,510` | `087192895b7654f3b2d8846d659dfdedf90fc1deccc59811b06ecced8821b204` |
| `out_0002.pqa1` | `6,374` | `1,391,030` | `df52883e32849a4ad57bbcb939d1025c108c34f3444be89fc56fd3020bbde8dc` |
| `out_0003.pqa1` | `6,375` | `1,390,889` | `06f1c3427916e3956fdbeceab1da29e602de4a1f6dad1d044a880652c89d2c61` |
| `out_0004.pqa1` | `6,375` | `1,391,765` | `40422726bb1d24fc37d285c5d9129d6a555713ecfd991dcb477ba839123af315` |
| `out_0005.pqa1` | `6,374` | `1,390,826` | `5d1d7aa799a132250ec05cc9c4fbe7db7771ccceba9b30a26b69f0e593f037ab` |
| `out_0006.pqa1` | `6,374` | `1,390,462` | `143477bed817a6c1d4b2f302a86201a8351358911d6019d8e560d0e9eeede364` |
| `out_0007.pqa1` | `6,374` | `1,389,738` | `2f21f4ade42ef9c08ce980a3b26bf0dda37c896f07c1b381fa8472b80df9e0a9` |

Total PQA1 shard bytes: `11,124,986`.

## Phase 1 to Phase 2 Bridge

| Field | Value |
| --- | --- |
| Bridge staging root | `/sdcard/Download/polymath/polar_phase1_c1/c1_phase1_v4_full_rerun_20260629T170920Z` |
| PQA1 list | `/sdcard/Download/polymath/polar_phase1_c1/c1_phase1_v4_full_rerun_20260629T170920Z/c1_pqa1_list.txt` |
| PQA1 list SHA-256 | `37c9f65fb88a1cbb3a0de375dcb6f8946a04d680136ac7d243f27cbcdc6195b8` |
| Listed files | `8` |
| Copied shards | `8` |
| Copied bytes | `11,124,986` |
| Hash match | `pass` |
| Raw bridge payload inside git | `false` |

The bridge evidence is a contract between Phase 1 and Phase 2. The original app
private paths are not the Phase 2 contract; the shared PQA1 list is.

## Phase 2 Full C1 Native Packetization Result

| Field | Value |
| --- | --- |
| Run label | `c1_phase2_v4_full_20260629T173243Z` |
| Wrapper status | `pass` |
| Native status | `pass` |
| Native return code | `0` |
| Termux repo | `/data/data/com.termux/files/home/Polymath-AI` |
| Termux repo branch/head | `main` / `54d9aa1` |
| Termux worktree state | dirty |
| Native packetizer threads | `8` |
| PQA1 files consumed | `8` |
| Source records | `50,994` |
| Source real token count | `2,130,785` |
| Unique/projected token count | `65,139` |
| Packet count | `50,994` |
| Slot count | `6,527,232` |
| Raw PJP1 output | `/data/data/com.termux/files/home/polymath_phase2_outputs/c1_phase2_v4_full_20260629T173243Z/raw_c1_phase2_v4_full_20260629T173243Z.pjp1` |
| PJP1 bytes | `461,805,760` |
| PJP1 SHA-256 | `e347676432fa7a76489f402f3c3e38ab492b6554f71930f14bc7d36ed1b3ecf5` |
| PQA1 source SHA-256 stream | `7acdbe6fd607584c1281ca4b065340fed18da0fc633ffea467a0e1eab15548f3` |
| Writer | `phase2b_native_cpp_neon_writer_v1` |
| JL kernel | `group4_cached_promoted` |
| Projection kernel | `single_token_k4_parallel_exact_dense_rademacher` |
| Input projection cache reuse factor | `32.7114` |
| Raw output inside git | `false` |

### Phase 2 Timing

| Stage | Seconds |
| --- | ---: |
| Scan/validate | `0.021077` |
| Projection cache prepare | `2.74169` |
| Output prepare | `0.000988073` |
| Native process | `2.73741` |
| Flush/sync | `0.360984` |
| Sample hash | `0.000147813` |
| Total | `5.86519` |

### Phase 2 Throughput

| Metric | Value |
| --- | ---: |
| Records/sec | `8,694.35` |
| Packets/sec | `8,694.35` |
| Real tokens/sec | `363,294` |
| Process real tokens/sec | `778,395` |
| Cache-inclusive process real tokens/sec | `388,893` |
| Packet slots/sec | `1,112,880` |
| Output MB/sec | `78.7367` |

### Phase 2 Artifact Identity

| Artifact | Path / identity | SHA-256 |
| --- | --- | --- |
| Wrapper JSON | `runtime/reports/polar_phase2_c1_smoke/c1_phase2_v4_full_20260629T173243Z/c1_phase2_v4_full_20260629T173243Z_phase2_c1_smoke_wrapper_report.json` | `38a0909bce90549668351b02006d4051fd2853f9c7adaf9828f483be2507afe5` |
| Native JSON | `runtime/reports/polar_phase2_c1_smoke/c1_phase2_v4_full_20260629T173243Z/c1_phase2_v4_full_20260629T173243Z_native_packetizer_report.json` | `611118aab3c1a1e664b472d709e63e78d2c240194fb75a99086962dfb7068df3` |
| Termux log | `runtime/reports/polar_phase2_c1_smoke/c1_phase2_v4_full_20260629T173243Z/termux_phase2_c1_v4_full.log` | see committed metadata directory |
| Packetizer binary | `/data/data/com.termux/files/home/Polymath-AI/native/polar_phase2_packetizer/bin/phase2b_native_packetizer` | `11c81138d181f09dd1a9a4715952c8a5357a91e3f1c1562f2fb9761d4d4c336a` |
| Packetizer source | `/data/data/com.termux/files/home/Polymath-AI/native/polar_phase2_packetizer/phase2b_native_packetizer.cpp` | `ba2d4dd48e2d9afeabf69b84019af0375aa739b26e982d69e8084a94a264c61f` |
| Packetizer build script | `/data/data/com.termux/files/home/Polymath-AI/native/polar_phase2_packetizer/build_phase2b_native_packetizer.sh` | `3c284c858aaa0d1e7697c4b63a12330d2e24d62a2391f109f34133463a631716` |
| Gemma4 E4B f16 input embedding | `/data/data/com.termux/files/home/polymath_polar_phase2/embeddings/gemma4_E4B_input_embedding.f16` | `b57e1e756f32d02c1aaad6c5c868f975f53b0938e0a04ed546804ed9c7d4ca7b` |
| Embedding manifest | metadata hash | `0bf2dc2ec4487c079da94d8c8a37f54bb7c45ed2f9a29dbbd73edc0ababaf8bd` |
| Dense Rademacher JL | `/data/data/com.termux/files/home/polymath_polar_phase2/jl/gemma4_dense_rademacher_k256_d2560_i8.bin` | `1b1f9de3dd6fbdf9597240eeeb08a6b482b33f1ae4d127e730222750cdf92a79` |

## Termux Access and Execution Channel

The Termux problem was command-channel access, not Phase 2 capability:

- ADB saw the phone as `FY25013101C8`, model `NX789J`.
- Direct ADB shell could not access Termux private home.
- Termux service execution required unavailable/internal permissions.
- SSH attempts did not provide a usable command channel in this session:
  port `18022` closed connection, port `18023` closed before banner, and port
  `8872` was identified as `btsnoop`, not a command channel.
- The successful execution route was the already-open foreground Termux Codex
  session, driven through controlled ADB text input, with no second uncoordinated
  packetizer run.

This matters for reproducibility. Future authority runs need either a clean
foreground Termux Codex contract, a repaired SSH channel, or another controlled
Termux execution path that preserves source/binary identity and raw-payload
custody.

## Data Custody

| Payload class | Custody result |
| --- | --- |
| C1 JSONL | Outside repository under corpus package root. |
| QAI1 | Generated under temp/app staging; not committed. |
| PQA1 | App-private then shared phone staging; metadata only in repo. |
| PJP1 | Termux private output; metadata only in repo. |
| Embedding/JL | Termux private payloads; hashes only in repo. |
| Secrets/env | Not sourced, printed, copied, or committed for this report. |
| Git staging | Scoped metadata/docs only; unrelated dirty worktree entries ignored. |

Raw payload suffixes remain forbidden in git for this pipeline event:
`.bin`, `.onnx`, `.pjp1`, `.pqa1`, `.pt`, `.pth`, `.qai1`, `.safetensors`,
`.tflite`.

## Limitations and Risks

1. The run is full C1 but still below the governing 100k/1M Phase 2 authority
   scale.
2. C1 contains `50,994` records. It cannot by itself satisfy a `100k` or `1M`
   record authority gate without additional material or repeat-policy semantics
   that must be explicitly authorized.
3. The Termux repo used for Phase 2 reported branch `main`, head `54d9aa1`, and
   a dirty worktree. Source/binary identity must be reconciled against canonical
   branch `gemma4-megakernel-native-training` before authority-scale claims.
4. Phase 1 reports `parity_state=not_checked_in_apk_run`; do not treat this as
   final APK parity.
5. The Phase 2 run proves deterministic packet production and throughput on this
   material. It does not prove downstream readback/oracle, collision, margin,
   Hamming, training, or learning behavior.
6. C2 was not run.
7. UI review remains downstream. The UI must present this as full-C1 diagnostic
   evidence and must not imply authority completion or Phase 3 readiness.

## External Review Checklist

Reviewers should verify:

- Source material identity: C1 input path, row count, and SHA-256.
- Phase 1 run settings: single child-exec pass, `run_flags=16`, warm sequences
  disabled.
- Phase 1 outputs: `8` PQA1 shards, exact bytes, exact SHA-256 values.
- Bridge: PQA1 list SHA-256 `37c9f65fb88a1cbb3a0de375dcb6f8946a04d680136ac7d243f27cbcdc6195b8`.
- Phase 2 native result: wrapper/native `pass`, `50,994` packets, `461,805,760`
  byte PJP1, PJP1 SHA-256 `e347676432fa7a76489f402f3c3e38ab492b6554f71930f14bc7d36ed1b3ecf5`.
- Data custody: raw payloads outside git; only metadata and report docs in repo.
- Nonclaims: no 100k/1M authority, no Phase 3, no learning/model-quality claim.

## Next Engineering Actions

1. Reconcile Termux packetizer source, binary, build script, branch, and dirty
   worktree state against the canonical repository branch.
2. Decide the authority-scale material route: add more real corpus, define an
   explicit repeat-policy gate, or stage C2/other corpora under a material
   steward contract.
3. Run the 100k and 1M Phase 2 authority gates only after material identity and
   source/binary identity are clean.
4. Add PJP1 readback/oracle/collision/margin/Hamming validation on real outputs
   before any Phase 3 readiness discussion.
5. Update the UI evidence surface to distinguish 64-record smoke, full-C1
   diagnostic, and 100k/1M authority states.
6. Preserve this report as an external review document. Do not rewrite it into a
   pass narrative until the governing authority gate is actually met.
