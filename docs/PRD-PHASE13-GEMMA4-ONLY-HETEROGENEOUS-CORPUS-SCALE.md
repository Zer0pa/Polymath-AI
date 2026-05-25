# PRD: Phase 13 Gemma4-Only Heterogeneous Corpus-Scale Training

Document Class: AUTHORITY_PRD
Phase: 13
Status: READY_FOR_EXECUTION_AGENT
Created: 2026-05-24
Repository: https://github.com/Zer0pa/Polymath-AI
Branch: gemma4-megakernel-native-training
Authority runtime: REDMAGIC NX789J / SM8750 / serial FY25013101C8
RunPod oracle: pod ltg8fdnxgmzwjy at /workspace/Polymath-AI
RunPod SSH primary: ssh root@38.80.152.147 -p 31002 -i ~/.ssh/id_ed25519
RunPod SSH alternate: ssh ltg8fdnxgmzwjy-64411e59@ssh.runpod.io -i ~/.ssh/id_ed25519
Phone root: /data/local/tmp/polymath_gemma4_gate
Doctrine: RESISTANCE-V2.md

## 1. Objective

Phase 13 corrects the Phase 12 drift and pushes the actual governing objective:
Gemma4 E4B training on the REDMAGIC SM8750 using the hardware in the shape it
wants, with real corpus scale, Gemma-only artifacts, and exact claim control.

The top gate is:

```text
Execute a phone-local, long-horizon Gemma4-only training campaign over a
substantially larger HF-streamed phone-native corpus cache, using only
Gemma4-compatible model artifacts in Gemma gates, proving or falsifying a
Gemma-compatible HTP role, and promoting only claims backed by phone evidence,
kernel-lineage telemetry, heldout learning signal, regression floors, and
falsifier reports.
```

No Qwen, SmolLM, random-init, shape-mismatched, or non-Gemma artifact may appear
inside a promoted Gemma gate. Such artifacts are allowed only in an isolated
negative tool-surface probe whose expected result is rejection.

## 2. Ground Truth

Passed and preserved:

- G1/G3/G8 authority floors passed and remain regression floors.
- H11-H passed a narrow phone-local rank-4 top-k KL POVC.
- Phase 12 passed residual rank-16/rank-32 post-layer0 adapter training with
  AdamW/clipping and phone-local queue execution.
- Phase 12 rank-16 LR `3e-4` continuation improved heldout KL from
  `1.0005755997` to `0.8207082971`, mini metric from `0.1233203377` to
  `0.1625584151`, and agreement from `0.1140456182` to `0.2244897959`.
- Phase 12 finite-difference probes matched two high-gradient residual-adapter
  coordinates with relative error below `2e-6`.

Falsified or still nonclaims:

- Qwen/random-init HTP artifact is invalid for Gemma heterogeneous learning.
- HTP output shape `[1,16,1536]` is incompatible with Gemma hidden size `2560`.
- QAIRT updateable context generation failed for current artifacts before any
  phone `QnnContext_applyBinarySection` proof.
- Integrated heterogeneous Gemma learning is not proven.
- Multi-site adapter training is not proven.
- Full Gemma4 training, broad capability, and public benchmark readiness are
  not proven.
- Phase 12 corpus scale is weak: only a 16-sequence HF-derived cache was
  promoted.

## 3. Sovereign Rules

### Gemma Identity Gate

Every promoted Gemma gate must prove all of:

- `model_id` is `google/gemma-4-E4B`;
- hidden size is `2560`;
- tensor names, layer ids, and adapter shape match Gemma4 assets;
- source weights and revision are declared;
- runtime telemetry declares the actual binary and kernel path used;
- no hidden-state fixtures are consumed;
- no non-Gemma artifact feeds Gemma training, teacher generation, evaluation,
  or HTP bridge claims.

Any mismatch is an immediate gate failure, not a research result.

### Corpus Reality Gate

Smoke tests may use small caches, but learning promotion may not. Phase 13 must
build or reuse a phone-native HF-streamed corpus cache with:

- minimum promoted floor: `>=8192` packed training sequences at seq128 and
  `>=1024` heldout sequences, unless phone storage/network diagnosis proves a
  true boundary blocker;
- stretch target: `>=65536` training sequences;
- raw text fetched or staged through a declared HF-authenticated path without
  printing secrets;
- Gemma tokenizer executed on the phone;
- exact tokenizer parity spot checks against RunPod Transformers;
- license/provenance manifest;
- train/heldout split manifest;
- shard hashes and replay manifests.

RunPod may generate references or teacher top-k shards after the phone cache is
defined. RunPod may not serve runtime minibatches or drive per-iteration
training.

### Kernel-Lineage Gate

Every run must label itself honestly as one of:

- `fused_static_megakernel`;
- `material_fused_opencl_sequence`;
- `two_layer_opencl_runner`;
- `residual_adapter_opencl_training`;
- `cpu_helper_only`;
- `qairt_htp_context_probe`.

The word `megakernel` is forbidden in promoted claims unless a material fused
kernel or static fused sequence is actually used and its dispatch/traffic
benefit is measured. If the run uses the existing two-layer OpenCL runner plus
adapter kernels, say that exactly.

### HTP/Gemma Gate

HTP work counts for Gemma only if it is Gemma-compatible:

- Gemma hidden size `2560`;
- Gemma weights or Gemma-derived teacher tensors;
- valid QNN context with declared graph/tensors;
- output consumed by the Gemma training loop or used as an explicitly staged
  Gemma teacher artifact;
- transfer cost and correctness measured;
- if updateable, `QnnContext_applyBinarySection` must execute on phone and
  change a declared Gemma-compatible output under fixed controls.

Non-Gemma HTP artifacts are quarantined under `negative_tool_surface_probe` and
cannot advance a heterogeneous Gemma claim.

## 4. Operating Mode

The executor is an overnight campaign runner. It must set up gates, start
phone-local sequential queues when safe, and keep going through pass/fail/fallback
decisions. Reporting early is not progress.

After each gate:

- write machine-readable gate result, blockers, falsifier report, artifact
  manifest, commands log, and checksum records;
- update GPD state/runlog;
- preserve the strongest valid config or fallback;
- continue unless a safety stop or true boundary blocker applies.

True boundary blockers only:

- phone or RunPod unavailable after diagnosis;
- credentials unavailable without operator action;
- legal/license ambiguity for corpus;
- destructive phone risk without rollback;
- uncontrolled spend;
- architecture contradiction that invalidates the PRD.

## 5. Safety And Artifact Rules

Safety stops:

- Android thermal status `>=3`;
- battery temperature `>=46 C` for more than `120s`;
- skin temperature `>=50 C` for more than `120s`;
- reported SoC die `>=92 C`;
- free phone storage under phase root `<8 GiB`;
- checkpoint/hash mismatch;
- G1/G3/relevant G8 regression failure after a material runtime change.

No fridge, ice, freezer, or condensation-adjacent cooling is part of this PRD.

Git-allowed:

- source, scripts, JSON/YAML/Markdown reports, manifests, checksums, compact
  telemetry summaries, schemas, sanitized logs.

Git-forbidden:

- model weights, raw tensor payloads, raw token payloads, `.safetensors`, large
  `.bin` checkpoints, QNN/DLC payloads, SDK binaries, env files, HF tokens,
  phone token files, SSH keys, `.venv`, `node_modules`, build caches.

Large payloads remain on phone or RunPod and are referenced by hash and size.

## 6. Sequential Gates

Run P13-A through P13-I in order. A failed gate records why and continues with
the strongest valid fallback unless the failure makes later gates invalid.

### P13-A: Phase 12 Contamination Audit And State Repair

- Hypothesis: Phase 12 evidence can be made safe for continuation by separating
  valid Gemma/Adreno learning from invalid Qwen/HTP artifacts.
- Action: Audit Phase 12 final artifacts, git status, GPD state, and dirty
  files. Repair stale state language. Classify all Phase 12 artifacts as
  Gemma-valid, negative probe, or forbidden-for-Gemma.
- Pass condition: No next gate can accidentally use Qwen/random-init/hidden1536
  artifacts for Gemma; GPD state reflects Phase 12 final result; dirty worktree
  is understood and artifact scans are clean.
- Falsifiers: Qwen artifact path appears in any promoted Gemma gate; stale H11
  state routes executor backward; untracked raw payloads in reports.

### P13-B: Gemma Identity And Kernel-Lineage Instrumentation

- Hypothesis: Current telemetry can be hardened so every future run states the
  actual model, hidden size, runner, and kernel path.
- Action: Add or verify mandatory telemetry fields for model id, revision,
  hidden size, runner binary sha, source commit, kernel-lineage class, backend,
  trainable scope, fixture usage, and teacher provenance.
- Pass condition: A phone smoke run emits the full identity/kernel-lineage
  record and rejects a deliberately mismatched non-Gemma artifact.
- Falsifiers: missing model id, missing hidden size, false `megakernel` label,
  silent fixture consumption, non-Gemma artifact accepted.

### P13-C: Corpus Scale And Phone-Native HF Stream

- Hypothesis: The phone can build a useful Gemma token cache from HF-streamed
  raw text at material scale.
- Action: Build phone-native train/heldout caches with minimum `8192/1024`
  seq128 split and stretch `65536` train sequences. Use stored HF credentials
  without printing secrets. Record dataset source, license/provenance, retry
  behavior, tokenizer parity, storage timing, and shard hashes.
- Pass condition: Minimum corpus floor exists on phone, exact token parity spot
  checks pass, shards replay, and no host minibatch serving exists.
- Falsifiers: 16-sequence cache reused as learning corpus; host tokenization
  sold as phone-native; raw token payloads committed; no heldout split.

### P13-D: Full/Sampled Gradient Parity Expansion

- Hypothesis: Residual rank-16/rank-32 top-k KL gradients are correct beyond two
  cherry-picked coordinates.
- Action: Run finite-difference or RunPod oracle checks over a seeded sample of
  at least `64` coordinates across adapter A/B, multiple iterations, and both
  rank-16 and rank-32 where feasible.
- Pass condition: Predeclared tolerance passes, gradients finite, checkpoint
  mutation matches declared optimizer semantics, and failures are isolated.
- Falsifiers: only high-gradient cherry-picks; tolerance chosen after results;
  host gradient substitution; frozen tensor mutation.

### P13-E: Multi-Site Gemma Adapter Implementation

- Hypothesis: The next material learning jump requires a second real Gemma
  adaptation site, not endless post-layer0 residual tuning.
- Action: Implement the smallest honest second site: later residual adapter,
  projection adapter, or other Gemma-compatible insertion point. Include
  checkpoint layout, backward kernels, gradient validation, and memory budget.
- Pass condition: At least one second Gemma site performs phone-side
  forward/backward/update with parity/falsifier evidence and no G1/G3/G8
  regression.
- Falsifiers: parameter-count inflation without a second site; CPU/host
  backward hidden in the path; shape mismatch; no checkpoint replay.

### P13-F: Gemma-Compatible HTP Artifact Or Hard Falsification

- Hypothesis: HTP can participate only if a Gemma-compatible context exists.
- Action: Attempt a Gemma-compatible QAIRT/HTP context from Gemma tensors or a
  Gemma-derived teacher island. Use QAIRT tools only through a clean,
  reproducible host environment. Reject all Qwen/random-init artifacts.
- Pass condition: Either a valid Gemma hidden-2560 HTP context runs on phone
  with measured outputs, or the exact QAIRT/compiler blocker is recorded.
- Falsifiers: Qwen/random-init artifact used; hidden size not `2560`; graph not
  connected to Gemma; tool help output sold as context proof.

### P13-G: Heterogeneous Candidate Versus Adreno Baseline

- Hypothesis: A hardware-native heterogeneous shape can beat or meaningfully
  complement the Adreno-only residual lane when measured honestly.
- Action: Compare selected Adreno-only baseline against any valid CPU/Adreno/HTP
  candidate. Measure active/wall, transfer payloads, correctness, energy proxy
  if available, thermal state, and heldout movement per token.
- Pass condition: Heterogeneous path is Gemma-compatible, consumes/produces
  compatible tensors, and beats baseline on a predeclared metric without
  authority regression. If no valid HTP path exists, promote only the falsifier.
- Falsifiers: HTP execution not consumed by Gemma; different corpus; different
  objective; transfer cost omitted; throughput replacing heldout signal.

### P13-H: Overnight Phone-Local Long Run

- Hypothesis: The strongest valid Gemma-only configuration can run overnight on
  phone-local queues over a real corpus cache and improve heldout metrics.
- Action: Launch a phone-local `nohup` or daemon queue after P13-A through P13-G
  have pass/fail/fallback artifacts. The run must use the scaled corpus cache,
  selected trainable scope, declared optimizer/objective, and compact artifact
  strategy. It may continue after ADB disconnect.
- Pass condition: Predeclared run completes `>=5000` updates or `>=4` wall
  hours, unless a predeclared heldout objective is reached earlier. Heldout KL
  and mini metric improve versus fixed and previous best controls; active/wall
  `>=0.85`; regression floors pass; artifacts replay by manifest.
- Falsifiers: small corpus reused; host-driven iterations; no heldout split;
  checkpoint corruption; safety stop hidden; run promoted on train loss only.

### P13-I: Exact Claims And Next Branch Decision

- Hypothesis: Phase 13 can decide the next route by evidence, not narrative.
- Action: Produce exact promoted claims, nonclaims, blockers, and the next
  highest-leverage Phase 14 branch.
- Pass condition: Claims are no broader than evidence. If heterogeneous fails,
  the next branch either builds a Gemma-compatible HTP context or abandons HTP
  temporarily and intensifies Adreno/multi-site/corpus work.
- Falsifiers: broad capability claim; benchmark claim without benchmark;
  `Gemma training` used without scope; failed HTP narrated as progress.

## 7. Promotion Rules

Phase 13 may promote:

- scaled phone-native Gemma corpus cache;
- improved residual or multi-site Gemma adapter learning;
- validated gradient correctness over expanded samples;
- Gemma-compatible HTP context execution;
- true heterogeneous improvement over Adreno-only baseline;
- overnight phone-local learning over scaled corpus.

Phase 13 may not promote without direct proof:

- full Gemma4 training;
- HTP backprop;
- successful `QnnContext_applyBinarySection` on phone;
- public benchmark readiness;
- broad capability improvement;
- fused megakernel status;
- heterogeneous training from a non-Gemma artifact.

## 8. First Executor Action

The next execution agent must read:

1. `AGENTS.md`
2. this PRD
3. `docs/HANDOFF-PHASE13-GEMMA4-ONLY-HETEROGENEOUS-EXECUTOR.md`
4. `docs/STARTUP-PROMPT-PHASE13-GEMMA4-ONLY-HETEROGENEOUS.md`
5. `.gpd/STATE.md`
6. `.gpd/phases/13-gemma4-only-heterogeneous-corpus-scale/13-01-PLAN.md`
7. Phase 12 final gate result:
   `runtime/reports/gemma4_megakernel/phase12_hardware_native_learning/20260524T175056Z_phase12_final_exact_claims/phase12_gate_status.json`

Then execute P13-A. Do not start with HTP, a long run, or a benchmark. The
first action is contamination audit and state repair.
