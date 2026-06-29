# Engineering Spec: Polar Phase 2 CPU JL Binary/Polar Packetization

Date: 2026-06-26
Status: Draft for review, not a PRD
Authority runtime: REDMAGIC NX789J / Snapdragon SM8750 / Termux on-device
Mac role: control plane, spec/audit/orchestration only
RunPod role: reference oracle only
Comet project: `zer0pa/mobile-polymath-ai-training`

## 1. Purpose

Phase 2 turns the Phase 1 `PQA1` token stream into fixed-size binary polar
tensor packets for downstream NPU/GPU stages.

The current polar pipeline is:

```text
Phase 1 CPU QA/PQA1 ingestion and chopping
  -> Phase 2 CPU JL binary/polar packetization
  -> Phase 3 NPU binary/polar forward read
  -> Phase 4 GPU polar optimizer
```

Phase 1 is still being hardened in the Android app stream for accepted
REDMAGIC/Game Mode/Game Space authority. That app work may improve performance
later, but Phase 2 engineering can proceed against the `PQA1` contract.

This document is for agent review before a Phase 2 PRD is written.

## 2. Nonclaims

This spec does not claim:

- Phase 2 has passed;
- JL packetization has been implemented;
- NPU/HTP execution;
- GPU optimizer execution;
- learning or model quality movement;
- megakernel status;
- Android/Game Mode/REDMAGIC benefit.

Any future Phase 2 run without Comet logging is incomplete unless blocked with
exact evidence.

## 3. Phase 1 Handoff Floor

Primary closure package:

`runtime/reports/polar_phase1_maximal_closure/2026-06-26T171915Z/`

Selected Phase 1 results:

| Scale | Token IDs/sec |
| --- | ---: |
| 10k | `16,402,897.6177` |
| 100k | `49,068,772.5901` |
| 1M | `62,634,625.4288` |

Correctness and hygiene passed: HF/Gemma parity, repeated-scan equivalence,
repeat hash, `PQA1` roundtrip, span integrity, hot-loop allocations `0`,
forbidden payload scan, mirror hygiene, and Comet logging.

Important input caveat: raw `.qai1`, `.pqa1`, and `.jsonl` payloads were
intentionally excluded from the shared mirror. Phase 2 should prefer one of:

1. recover raw Phase 1 authority payloads from phone-local storage;
2. regenerate declared placeholder `PQA1` through the Phase 1 engine on phone;
3. use tiny synthetic fixtures only for unit smoke tests, never for an authority
   Phase 2 pass.

## 4. Engineering Stack

Recommended implementation stack:

| Layer | Proposed Owner | Notes |
| --- | --- | --- |
| `PQA1` reader | Zig | `mmap`/stream parse, schema validation, record/span/loss-mask checks |
| packet sealer | Zig | exact `128` token packet construction and padding |
| embedding loader | Zig/C ABI if needed | phone-local Gemma embedding table, hash-attested, not committed |
| JL projector | Zig | fixed Rademacher matrix generated at compile time |
| polar encoder | Zig | sign/tie policy, bit packing, optional reference hashes |
| packet writer | Zig | proposed `PJP1` binary packet output |
| independent verifier | Zig plus Python oracle | writer-independent roundtrip and sampled/full transform checks |
| report runner | Python orchestration | Comet logging, reports, artifact hygiene, command ledger |

Suggested repo paths for later implementation:

```text
native/polar_phase2_packetizer/
scripts/termux/run_polar_phase2_gate.py
runtime/reports/polar_phase2/<timestamp>/
```

Do not create these until the PRD freezes the contract.

## 5. Input Contract

Required authority input:

- valid Phase 1 `PQA1` binary stream;
- tokenizer metadata and hash references;
- record IDs or record hashes;
- token IDs;
- question/answer segment spans;
- loss-mask intent;
- continuation metadata;
- source-kind metadata.

Phase 2 must reject or explicitly mark incomplete:

- JSON-only input sold as final Phase 2 evidence;
- token IDs without Phase 1 span/loss metadata;
- regenerated placeholder data that is not declared as placeholder;
- unknown tokenizer hash or incompatible schema version.

## 6. Packet Sealing Policy

Recommended initial policy: `record_local`.

Rules:

- each QA record produces one or more 128-token packets;
- short records are padded mechanically;
- long records are chunked into continuation packets;
- QA record boundaries are not crossed in the first authority implementation;
- question/answer segment roles and loss masks are propagated exactly;
- padding tokens are loss-inactive and carry explicit pad metadata.

Reason: record-local sealing avoids semantic bleed and makes independent
verification much simpler. A later `stream_fill` mode may pack across record
boundaries only if boundary metadata, loss masks, and downstream semantics remain
exact and separately verified.

Open decision for PRD: whether `record_local` is the only passable Phase 2 mode
or just the first promoted mode.

## 7. Embedding Lookup

Phase 2 performs CPU embedding lookup before the accelerator boundary.

Required embedding metadata:

- model ID;
- model revision;
- embedding tensor hash;
- dtype and layout;
- vocab/tokenizer hash;
- source path on phone;
- no raw weights in git or compact mirrors.

For each token ID:

```text
token_id -> Gemma embedding vector x
```

If real Gemma embedding weights are unavailable, a small deterministic embedding
fixture can test plumbing only. It cannot satisfy the authority gate.

## 8. Fixed Rademacher JL Transform

Phase 2 applies a fixed Rademacher Johnson-Lindenstrauss transform on CPU.

Proposed mathematical shape:

```text
R[j, i] in {-1, +1}, deterministic from frozen seed
y[j] = scale * sum_i R[j, i] * x[i]
polar_bit[j] = 1 if y[j] >= 0 else 0
```

Decisions to freeze in the PRD:

- JL output dimension `k`;
- seed and PRNG/hash derivation;
- row/column order;
- scale factor, likely `1 / sqrt(k)` for reference values;
- tie policy for `y[j] == 0`;
- whether Phase 2 stores only sign bits or also margin/checksum summaries;
- exact binary layout and endian policy.

Implementation posture:

- Zig `comptime` or generated source should bake the fixed transform structure;
- no runtime matrix construction in the hot path;
- matrix/sign generation must be reproducible by the independent verifier.

## 9. Proposed Output Contract

Proposed binary magic: `PJP1` for Polar JL Packet v1.

This is a proposal for review, not frozen.

Header fields:

- magic `PJP1`;
- schema version;
- endian marker;
- packet sequence length, fixed `128`;
- tokenizer hash reference;
- embedding hash reference;
- JL config hash;
- JL dimension `k`;
- polar encoding policy;
- source `PQA1` hash;
- packet count if known.

Per-packet fields:

- packet ID;
- source record hash;
- continuation index;
- real token count;
- pad count;
- token IDs or optional token hash summary;
- segment-role bitsets;
- loss-mask bitset;
- position policy;
- input polar bits, shape `[128, k]`;
- target/answer polar bits for answer-active tokens or the PRD-selected target
  representation;
- packet checksum.

Target representation is the biggest unresolved design point. The PRD must
decide whether Phase 4 wants per-answer-token polar targets, a pooled answer
polar target, or both.

## 10. Verification Stack

Minimum verifier lanes:

1. `PQA1` parser verifier: independent read and schema validation.
2. Packet sealer verifier: exact 128-token chunking, padding, span propagation,
   and loss-mask propagation.
3. Embedding verifier: token ID to embedding row hash/spot-check against an
   oracle.
4. JL verifier: deterministic `R` generation and sampled/full projection
   agreement.
5. Polar verifier: sign/tie/bitpack roundtrip.
6. Output verifier: `PJP1` readback, packet checksums, and source hash linkage.
7. Hygiene verifier: no model weights, raw payloads, secrets, build caches,
   `.venv`, `node_modules`, SDK binaries, or root `README.md` edits in shared
   artifacts.
8. Comet verifier: safe report assets logged; secrets read only from
   environment.

## 11. Execution Plan Shape

Suggested work packages after PRD approval:

| Work Package | Goal | Authority Status |
| --- | --- | --- |
| P2-A Contract skeleton | Parse tiny `PQA1`, seal 128-token packets, write/read proposed output with fake embeddings | engineering smoke only |
| P2-B Real `PQA1` source | Consume recovered or regenerated Phase 1 `PQA1` on phone | required for authority |
| P2-C Real embedding/JL | Phone-local Gemma embedding lookup plus fixed Rademacher JL and polar encoding | required for authority |
| P2-D Scale and falsify | 10k/100k/1M or PRD-selected non-toy scale, memory/PSS/thermal, allocation, correctness | required for promotion |
| P2-E Android handoff | Compact package and prompts for Android app integration | after Termux gate |

## 12. Acceptance Gate Proposal

This is a proposal for discussion, not the final PRD.

A Phase 2 pass should require:

1. Runs on REDMAGIC in Termux without Mac per-iteration control.
2. Consumes valid `PQA1` from Phase 1 or declared `PQA1` regenerated by Phase 1.
3. Emits fixed 128-token packet blocks with exact padding, continuation, spans,
   roles, and loss masks.
4. Uses a real phone-local Gemma embedding artifact with hash/provenance
   evidence.
5. Applies fixed Rademacher JL projection with reproducible seed/config and no
   runtime matrix construction.
6. Emits binary polar packet output with independent roundtrip verification.
7. Passes embedding/JL/polar correctness against an independent oracle on all
   small fixtures and sampled large-scale packets.
8. Measures packet/sec, token/sec, bytes/sec, PSS/RSS, thermal before/after, and
   hot-loop allocations.
9. Includes a non-toy stress run. Suggested starting discussion: 10k required,
   100k preferred, 1M stretch unless embedding/JL cost makes a different floor
   more honest.
10. Logs all safe reports to Comet. Missing Comet logging makes the run
    incomplete unless technically blocked with evidence.
11. Passes artifact hygiene and root `README.md` protection.
12. Explicitly reports nonclaims: no NPU/HTP, no GPU optimizer, no learning, no
    megakernel.

## 13. Review Questions For Other Agents

Ask reviewers to focus on these:

- Is `record_local` packet sealing the right first authority mode?
- What JL dimension `k` is technically credible for Phase 3/4 without exploding
  CPU cost or starving NPU/GPU utility?
- Should the binary polar output store sign bits only, or sign bits plus margin
  summaries/checksums?
- What exact target/answer polar representation does Phase 4 need for hinge
  loss?
- Where should the real Gemma embedding artifact come from, and how should it be
  represented on phone without violating artifact policy?
- What is the smallest scale gate that is non-toy but does not reward-hack the
  engineering objective?
- Which parts must be Zig from day one, and which verifier/oracle pieces should
  stay Python/C++ outside the hot path?

## 14. Current Recommendation

Start Phase 2 with a narrow but real contract:

```text
PQA1 -> record-local 128-token packets -> Gemma embedding lookup
     -> fixed Rademacher JL -> bitpacked polar packet file
     -> independent verifier + Comet report
```

Keep the first PRD focused on making this boundary correct, inspectable,
deterministic, and phone-native. Performance matters, but only after the
contract is exact. A faster packetizer that weakens tokenizer provenance,
padding semantics, loss masks, embedding hashes, or JL reproducibility is a
failure.
