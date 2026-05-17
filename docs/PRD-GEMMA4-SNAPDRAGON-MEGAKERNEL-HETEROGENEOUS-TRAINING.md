# Gemma 4 Snapdragon Megakernel Native Phone Training PRD

Sector: Polymath-AI
Document Class: AUTHORITY_PRD
Version: 1.0.0
Created: 2026-05-16
Rewritten: 2026-05-17
Status: ACTIVE_EXECUTION_CHARTER
Repository: `https://github.com/Zer0pa/Polymath-AI`
Active Branch Intent: Gemma 4 megakernel native phone training route
Authority Device: REDMAGIC 10 Pro, `NX789J`, Snapdragon `SM8750`
Remote Build / Oracle: RunPod pod `ltg8fdnxgmzwjy`
Primary Upstream Workstream: `/Users/Zer0pa/Gemma4 Kernel`
Doctrine: `RESISTANCE-V2.md`

## 0. Executive Order

This PRD is the governing artifact for the next long-horizon execution phase.
It supersedes generic mobile fine-tuning, Qwen-first, corpus-first, demo-first,
and setup-first interpretations of Polymath-AI for this lane.

The objective is not to prove that a phone can run a small demo. The objective
is to build and validate a native Gemma 4 training appliance on the REDMAGIC
SM8750:

```text
HF raw text stream
  -> phone Oryon CPU Gemma tokenization
  -> phone UFS packed sequence cache
  -> phone Adreno / Hexagon / CPU training runtime
  -> validated checkpoint or adapter artifact
  -> replayable telemetry, hashes, and falsifier reports
```

Mac is the control plane. RunPod is the build server and host PyTorch reference
oracle. The phone is the runtime. No server may become part of the runtime data
path.

The first hard gate has already passed and is now a permanent regression gate:

- Model: `google/gemma-4-E4B`
- Revision: `7aa32e6889efd6300124851b164f8b364314c3d8`
- Layer: text decoder layer `0`
- Backend: OpenCL
- Device: REDMAGIC `NX789J / SM8750`
- p50 FP64 cosine against RunPod PyTorch: `0.9999890020383452`
- min FP64 cosine: `0.9999801999737985`
- non-pad tokens: `111`
- failed tokens below `0.99`: `0`
- repeat run: byte-identical output
- upstream commit: `c5b6e3522d28d0e1dc56084cb97fa9e95e29aa4e`
- Polymath pointer: `runtime/reports/gemma4_megakernel/parity/20260516_e4b_layer0_opencl_gate/gate_result.json`

That pass is not a completion narrative. It is the floor. Any later work that
regresses it fails, regardless of secondary wins.

## 1. Governing Doctrine

### 1.1 Sovereign Objective

The sovereign objective is:

```text
A real Gemma 4 training run executed natively on REDMAGIC SM8750, consuming
phone-streamed Hugging Face training text, tokenizing and packing on phone,
updating a declared trainable scope without mutating frozen base tensors, and
emitting a replayable validated checkpoint or adapter artifact.
```

This is the top acceptance gate. It outranks local tests, compile success,
throughput improvements, partial demonstrations, or pleasing reports.

### 1.2 Resistance Covenant

The following instructions are binding on every executor, planner, verifier,
and sub-agent:

NEVER: optimize for a narratable win instead of the governing objective; let
local improvements substitute for the authority metric; close too early once
you have something defensible-looking. NEVER REWARD HACK. NEVER RUSH.

ALWAYS: treat the top acceptance gate as sovereign; treat any regression on the
authority metric as failure, regardless of secondary wins; keep docs and
handover artifacts frozen until the real gate is met; stay in the fix loop
instead of converting mixed evidence into a pass narrative. AVOID
TOY/DEMO/REGRESSING FROM MAXIMAL OBJECTIVE PURSUIT.

Forbidden patterns from `RESISTANCE-V2.md` are active:

- `fp-demogravity`: letting the demo become the project.
- `fp-localgreen`: treating local pass signals as the authority metric.
- `fp-scopeevaporation`: quietly shrinking the objective.
- `fp-softrefusal`: implementing a weakened version while claiming compliance.
- `fp-toolbusy`: substituting tools, branches, agents, or reports for decisive work.
- `fp-interimossification`: letting interim artifacts harden into completion.
- `fp-benchmarkproxy`: optimizing a proxy while the real gate remains open.

When a forbidden pattern appears: stop, name it, restore the governing
objective, and resume only with a concrete action that moves the authority
metric.

### 1.3 Overnight Autonomy

This PRD is written for an overnight executor. The operator may be asleep.

The executor does not pause for normal engineering decisions. Blockers become
tasks by default. The executor pauses only for true boundary blockers:

- required credentials or hardware are unavailable after retry and diagnosis;
- model or corpus license ambiguity cannot be resolved from available artifacts;
- a command risks destructive phone changes without a rollback path;
- cloud spend would become uncontrolled;
- a discovered architectural contradiction invalidates the gate ladder.

All other problems are engineering tasks. They are diagnosed, fixed, rerun, and
verified.

No interim reporting is required or desired during execution. The executor
writes machine-readable evidence while working and produces a final handoff only
after a real gate passes, fails, or is honestly blocked.

## 2. Boundary

### 2.1 Research Boundary

This is research infrastructure for in silico on-device LLM training and
multilingual / multi-domain knowledge model construction. Outputs are research
artifacts: model checkpoints, adapter checkpoints, training telemetry,
evaluation reports, throughput measurements, kernel parity reports, static
executor receipts, and falsifier logs.

No regulatory certification claims. No clinical or human-subject use. No
surveillance, biometric profiling, or identity inference. No model weights
distributed without explicit license attestation. No training on copyrighted
material without explicit corpus-license decomposition. No deployment to
production without a falsifier-traced acceptance gate.

### 2.2 In Scope

- Gemma 4 model-specific native runtime work.
- REDMAGIC SM8750 phone execution.
- Adreno OpenCL/Vulkan forward, backward, reduction, and optimizer kernels.
- Hexagon/QNN frozen-forward or recompute islands only when evidence supports
  them.
- Oryon CPU tokenization, packing, orchestration, scalar optimizer state, and
  telemetry.
- Hugging Face raw text streaming directly on phone.
- UFS packed sequence cache on phone.
- RunPod build, conversion, PyTorch reference, and strict comparison.
- GPD project planning, execution, verification, regression, and falsifier
  workflows.
- GitHub branch route that makes this pivot the canonical implementation path.

### 2.3 Out of Scope

- Qwen frozen-middle correctness as an active path.
- Model shopping as infrastructure strategy.
- Chatbot UI, agent-memory personalization, test-time adaptation, or product
  demos.
- Generic mobile fine-tuning that bypasses the hardware-first thesis.
- Mac-held model weights or datasets.
- RunPod as runtime data path.
- Host-only training claims.
- Throughput, thermal, or energy claims before correctness and checkpoint gates
  remain green.
- Public benchmark or release claims before license and falsifier gates close.

### 2.4 Parked Until Evidence Unlocks Them

- Reflex Agent dispatch classifier.
- Full heterogeneous CPU/GPU/NPU routing.
- QNN/HTP Gemma parity.
- Vulkan backend comparison if OpenCL remains the fastest route to training.
- Public corpus expansion beyond the minimum streamed training slice.
- Federated or multi-phone training.

Parked does not mean abandoned. It means the current authority ladder must earn
the right to spend attention there.

## 3. System Thesis

The cloud-GPU regime assumes one giant warehouse with thousands of identical
workers. The phone is not that. The REDMAGIC SM8750 is a small market town:
Oryon CPU cores, Adreno GPU, Hexagon NPU, unified memory, UFS storage, thermal
envelope, battery and charging behavior, and a local network connection. Each
component has a different physical shape.

The engineering question is whether learning has a shape that fits that town.
This project must not turn the town into a bad warehouse. It must discover and
build the workflow that wants the CPU, GPU, NPU, memory system, storage, and
thermal constraints as first-class structure.

The passed E4B OpenCL layer gate proves the first critical fact: a real
pretrained Gemma layer can execute on the phone GPU and match RunPod PyTorch.
The next question is whether that can be expanded into an end-to-end training
runtime.

## 4. Topology

### 4.1 Node Roles

| Node | Role | Allowed Work | Forbidden Work |
| --- | --- | --- | --- |
| Mac | Control plane | orchestration, git, small text manifests, ADB coordination | model storage, dataset storage, hidden runtime path |
| RunPod | Build server and oracle | Android/NDK builds, QAIRT/QNN tools, weight conversion, PyTorch references, strict comparisons | training data path, runtime tokenization, phone substitute claims |
| REDMAGIC | Runtime authority | HF streaming, tokenization, packing, forward/backward/update, checkpointing, telemetry | none, except unsafe/destructive operations without rollback |
| GitHub | Source review surface | code, docs, manifests, tests, reports | model weights, SDK binaries, secrets |
| Hugging Face | Private artifact surface | source corpora, approved checkpoint/adapter artifacts, large non-git artifacts | unlicensed or token-bearing uploads |

### 4.2 Runtime Principle

The training pipeline runs as a native phone runtime. It may use RunPod to
produce build artifacts, references, and validators. It may use Mac to
coordinate. But the runtime path is phone-local:

```text
network -> phone stream reader -> phone tokenizer -> phone sequence packer
-> phone UFS cache -> phone training executor -> phone checkpoint writer
```

If a claimed training run depends on Mac or RunPod for tokenization, sequence
packing, minibatch serving, gradient computation, or optimizer update, it is not
the authority run.

## 5. Current Evidence

### 5.1 Passed Regression Gate

The E4B layer 0 OpenCL phone gate passed and is preserved in:

- `runtime/reports/gemma4_megakernel/parity/20260516_e4b_layer0_opencl_gate/gate_result.json`
- `/Users/Zer0pa/Gemma4 Kernel/gemma4_megakernel/docs/gate_reports/20260516_e4b_layer0_gate_execution.md`
- `/Users/Zer0pa/Gemma4 Kernel/docs/orchestrator_handover_gemma4_e4b_gate.md`

This is now Gate G1 and must be rerunnable after material runtime changes.

### 5.2 Evidence Not Promoted

The following are real but not terminal:

- QNN/Hexagon sustained Qwen-shaped execution: substrate evidence only.
- Gemma4 CPU native kernel parity: useful, but not a phone claim.
- RunPod Android build success: necessary build evidence, not runtime success.
- Phone OpenCL elapsed time for one layer: diagnostic, not a throughput claim.

## 6. Authority Metrics

### 6.1 Terminal Acceptance Gate

Terminal pass requires all of the following:

1. A real Gemma 4 trainable scope is declared and implemented.
2. Raw training text streams from Hugging Face directly to the phone.
3. Gemma tokenization runs on phone CPU.
4. Sequence packing and caching run on phone UFS.
5. The phone training runtime consumes phone-packed batches.
6. Forward, backward, and optimizer update execute on phone.
7. Frozen base tensors remain hash-stable.
8. Declared trainable tensors mutate in the expected direction.
9. Loss and gradient checks are finite and validated against host references
   for the relevant small fixtures.
10. A checkpoint or adapter artifact is emitted with hashes and replay
    manifests.
11. The run survives a sustained authority window of at least 6 hours or reaches
    a predeclared training objective earlier without thermal, memory, or
    correctness collapse.
12. The passed E4B OpenCL layer gate remains green after the changes.
13. Independent falsifier review fails to kill the claim.

Any regression on these conditions is failure, regardless of secondary wins.

### 6.2 Secondary Metrics

Secondary metrics may be recorded but cannot pass a gate alone:

- tokens/sec;
- layer latency;
- dispatch count;
- memory high-water mark;
- KGSL/GPU telemetry;
- battery temperature and thermal zones;
- network throughput;
- tokenizer throughput;
- UFS cache throughput;
- checkpoint size and upload time.

Performance is interpreted only after correctness remains green.

## 7. Gate Ladder

### G0 - Control Plane And GPD Project

Objective: make the pivot executable without depending on chat context.

Required outputs:

- this PRD committed;
- `RESISTANCE-V2.md` present;
- formal `.gpd/` project initialized or fallback state explicitly marked;
- GitHub pivot branch created;
- Gemma4 Kernel import plan recorded;
- no secrets in git.

Pass condition:

- next executor can reconstruct objective, current evidence, phase ladder, and
  artifact policy from repo files only.

### G1 - E4B Layer 0 OpenCL Phone Regression

Status: PASSED.

Required forever:

- real pretrained E4B weights;
- REDMAGIC OpenCL or Vulkan path;
- p50 FP64 cosine >= `0.99`;
- failed non-pad tokens below threshold = `0`;
- repeat output determinism checked when relevant.

This gate must be rerun after material changes to:

- OpenCL kernels;
- tensor layout;
- layer pack format;
- safetensors parsing;
- memory planner;
- runner execution flow;
- build toolchain.

### G2 - Import And Regression Harness

Objective: make Gemma4 Kernel the canonical implementation lane inside
Polymath without copying prohibited artifacts.

Required outputs:

- import under `integrations/gemma4-snapdragon-megakernel/` or another
  documented namespace;
- import manifest with source commit hashes;
- no model weights, raw output bins, SDKs, build directories, caches, or token
  files;
- regression command for G1;
- CI or local test command for Mac build and CTest.

Pass condition:

- Polymath branch can build the imported host code and can point to the phone
  gate without artifact leakage.

### G3 - Forward Expansion

Objective: expand from one layer to a meaningful forward stack while preserving
numerical authority.

Minimum target:

- at least two sequential Gemma E4B decoder layers on phone OpenCL, unless a
  memory proof shows a smaller next step is necessary.

Required outputs:

- fixed input set;
- host PyTorch reference;
- phone output;
- per-token cosine report;
- intermediate tensor dump option for bisection;
- memory high-water report.

Pass condition:

- p50 cosine >= `0.99`;
- no failed non-pad token below `0.99`, unless a PRD amendment explicitly
  changes the comparator;
- G1 remains green.

### G4 - Executor Architecture Refactor

Objective: convert the direct runner into maintainable executor components
without changing tensor semantics.

Coding commandments:

- avoid deep nesting;
- avoid code duplication;
- do not use naming that only the implementer understands;
- use dependency injection where it decouples build/runtime concerns;
- use interfaces where device backends, tensor stores, token sources, and
  comparators need replacement;
- separate functions into individual responsibilities where it makes sense.

Required interfaces:

- `TensorStore`;
- `LayerPackReader`;
- `BackendExecutor`;
- `ReferenceComparator`;
- `TelemetrySink`;
- `Tokenizer`;
- `SequencePacker`;
- `CheckpointStore`;
- `TrainingStepExecutor`.

Pass condition:

- G1 and G3 remain green;
- component boundaries reduce risk for backward/update work;
- no abstraction that merely decorates the demo path.

### G5 - Backward Path

Objective: implement backward kernels for a declared trainable scope.

Default trainable scope:

- start with adapter or low-rank delta tensors attached to E4B layer 0 and the
  minimum adjacent tensors required for a real update;
- expand only by evidence, not by taste;
- base Gemma weights are frozen unless a later PRD amendment changes scope.

Required outputs:

- PyTorch gradient reference;
- phone gradient output;
- gradient cosine and error report;
- frozen tensor pre/post hash manifest;
- trainable tensor mutation contract.

Pass condition:

- gradients finite;
- default gradient p50 cosine >= `0.99`, or a documented numerical-analysis
  threshold approved by GPD verification;
- frozen tensor hashes unchanged;
- G1 remains green.

### G6 - Optimizer Update

Objective: perform a real phone-side optimizer update.

Required outputs:

- optimizer state stored on phone;
- pre/post trainable tensor hashes;
- frozen base tensor hashes;
- loss before and after update on fixed fixture;
- replay manifest.

Pass condition:

- trainable tensors mutate;
- frozen base tensors do not mutate;
- loss is finite;
- update replay is deterministic under fixed seed where determinism is expected;
- G1 remains green.

### G7 - Phone-Native HF Streaming And Tokenization

Objective: build the runtime data path.

Required behavior:

- phone authenticates to Hugging Face through existing local token mechanism;
- raw text streams directly to phone;
- tokenizer runs on Oryon CPU;
- token IDs match a reference for fixed samples;
- packed sequence shards are written to phone UFS;
- training runtime consumes packed shards without Mac or RunPod serving data.

Required outputs:

- source dataset manifest;
- license/provenance ledger;
- tokenization parity report;
- sequence packing report;
- UFS cache manifest;
- network retry and resume behavior.

Pass condition:

- exact token ID parity on fixed samples;
- packed shards replay into identical batches;
- no secrets printed or copied into git;
- no host-side hidden data path.

### G8 - Integrated Training Loop

Objective: connect phone-native batches to phone-side forward/backward/update.

Required outputs:

- run config;
- training audit log;
- batch manifest;
- checkpoint or adapter artifact manifest;
- loss trace;
- telemetry;
- regression report for G1.

Pass condition:

- at least one real streamed-corpus batch updates the declared trainable scope;
- checkpoint or adapter artifact emitted;
- frozen base hashes stable;
- no correctness regression;
- no hidden host data path.

### G9 - Sustained Authority Run

Objective: prove the system is not a fragile one-step artifact.

Minimum target:

- 6-hour phone-native run, or a shorter predeclared objective if the run reaches
  a meaningful training artifact before 6 hours.

Required telemetry:

- battery level and temperature;
- thermal zones available on device;
- GPU/KGSL/OpenCL diagnostics available without root;
- CPU memory and process RSS;
- UFS free space;
- network events;
- checkpoint writes;
- error counters.

Pass condition:

- no thermal collapse;
- no memory leak that invalidates continuation;
- no checkpoint corruption;
- G1 remains green after the run;
- final checkpoint/adapter validates.

### G10 - Falsifier Review

Objective: attack the claim before promotion.

Falsifier agents must check:

- wrong model revision;
- random-init or wrong-weight substitution;
- CPU fallback masquerading as OpenCL/Adreno;
- pad-token metric inflation;
- comparator tolerance relaxation;
- hidden host-side tokenization or batch serving;
- trainable/frozen scope violation;
- checkpoint replay failure;
- artifact hash mismatch;
- thermal or memory failure hidden by selective reporting;
- benchmark proxy replacing terminal gate;
- narrative pass without artifact pass.

Pass condition:

- all critical falsifiers pass or are explicitly resolved by rerun/fix;
- unresolved critical falsifier blocks promotion.

## 8. GPD Project Integration

### 8.1 Required Use

This lane must use GPD as the research execution spine unless the GPD runtime
itself is unavailable. The fallback `.gpd/hypotheses.yaml` and runlog are not
enough for overnight execution once this PRD is approved.

The executor must create or repair:

- `.gpd/PROJECT.md`;
- `.gpd/config.json`;
- `.gpd/REQUIREMENTS.md`;
- `.gpd/ROADMAP.md`;
- `.gpd/STATE.md`;
- `.gpd/state.json`;
- `.gpd/phases/**`.

The GPD contract must preserve:

- the sovereign terminal gate;
- the passed G1 regression gate;
- RedMagic as authority device;
- RunPod as build/oracle only;
- phone-native HF streaming/tokenization;
- forbidden proxy wins.

### 8.2 GPD Workflow

Recommended sequence:

```bash
# If no formal project exists, initialize from this PRD.
/Users/prinivenpillay/.gpd/venv/bin/python -m gpd.runtime_cli \
  --runtime codex \
  --config-dir /Users/prinivenpillay/.codex \
  --install-scope global \
  init new-project --minimal docs/PRD-GEMMA4-SNAPDRAGON-MEGAKERNEL-HETEROGENEOUS-TRAINING.md
```

If the CLI entry point differs, use the installed GPD workflow equivalent. Do
not skip GPD because the command spelling needs repair.

For each phase:

```text
$gpd-plan-phase <phase> --research
$gpd-execute-phase <phase>
$gpd-verify-work <phase> --all
$gpd-regression-check
```

Use targeted GPD tools when relevant:

- `$gpd-dimensional-analysis` for tensor shapes, memory units, bandwidth, and
  optimizer state accounting;
- `$gpd-error-propagation` for BF16 -> FP32 conversion, accumulation error,
  cosine tolerance, and gradient comparisons;
- `$gpd-numerical-convergence` for repeated runs and optimizer stability;
- `$gpd-sensitivity-analysis` for sequence length, batch size, rank, and thermal
  thresholds;
- `$gpd-parameter-sweep` for backend and kernel-tiling choices;
- `$gpd-compare-results` for OpenCL vs Vulkan, fused vs unfused, and baseline vs
  megakernel comparisons;
- `$gpd-verify-work --regression` whenever G1 or a later authority gate might
  have drifted.

GPD is not allowed to become process theater. A GPD artifact counts only when it
drives or verifies a real gate.

### 8.3 Phase Map

| GPD Phase | Gate | Phase Name | Decisive Output |
| --- | --- | --- | --- |
| 0 | G0 | Control Plane | formal GPD project, branch, import policy |
| 1 | G2 | Import And Regression | imported Gemma4 Kernel, G1 replay path |
| 2 | G3 | Forward Expansion | multi-layer phone forward parity |
| 3 | G4 | Executor Refactor | backend/runtime interfaces, no regression |
| 4 | G5 | Backward Path | phone gradients vs PyTorch |
| 5 | G6 | Optimizer Update | valid phone update, frozen hashes stable |
| 6 | G7 | Phone Data Pipeline | HF stream -> phone tokenize -> UFS pack |
| 7 | G8 | Integrated Training | streamed batch trains on phone |
| 8 | G9 | Sustained Run | long phone-native training artifact |
| 9 | G10 | Falsifier Review | claim survives adversarial review |

## 9. Agent Topology

The orchestrator coordinates. Agents execute bounded material work.

Required agent roles:

- Kernel engineer: OpenCL/Vulkan kernels, fusion, tensor layouts.
- Runtime engineer: C++ runner, interfaces, checkpointing, telemetry.
- Phone systems engineer: ADB, Android shell, OpenCL probing, thermal/memory
  collection.
- RunPod build/oracle engineer: Android NDK, PyTorch reference, model revision
  control, comparator.
- Data pipeline engineer: HF stream reader, Gemma tokenizer, sequence packer,
  UFS cache.
- GPD planner/executor/verifier: phase plans, execution, regression, numerical
  checks.
- Falsifier: attempts to kill successes before promotion.

Rules:

- Agents must produce code, tests, run artifacts, or falsifier reports.
- Agents do not produce broad research dumps unless research is blocking a gate.
- Parallel agents must have disjoint write scopes.
- A success claim is not promoted until falsifier review completes.

## 10. Engineering Standards

### 10.1 Coding Commandments

- Avoid deep nesting.
- Avoid code duplication.
- Do not use naming that only the implementer understands.
- Use dependency injection to decouple components where useful.
- Decouple components by using interfaces where it makes sense.
- Separate functions into individual responsibilities where it makes sense.

### 10.2 Dependency Hygiene

- Do not create new project-local Python environments with arbitrary names.
- Prefer `uv` and a single project `.venv` only when the repo actually needs an
  isolated environment.
- Before installing dependencies, inspect existing manifests and lockfiles:
  `pyproject.toml`, `uv.lock`, `requirements.txt`, `package.json`,
  `package-lock.json`, `bun.lock`, `pnpm-lock.yaml`, or `yarn.lock`.
- Do not install project dependencies into global or user Python.
- Avoid `pip install --user` unless the operator explicitly asks for a global
  tool.
- Use Python 3.11 as the default project runtime unless the repo declares
  otherwise. This repo declares `requires-python = ">=3.10"`; existing RunPod
  QAIRT/LiteRT environment Python 3.10 may be preserved if it is part of the
  working toolchain.
- For Node work, use the package manager implied by the existing lockfile.
- Do not create or commit `node_modules`.
- Keep committed env files to `.env.example`.
- Keep real `.env`, `.env.local`, service-token files, HF tokens, SSH keys, and
  phone token files out of repos and backups.
- After a temporary worktree is pushed or archived, generated dependency folders
  such as `.venv`, `venv`, and `node_modules` are disposable unless the operator
  says to preserve them.

### 10.3 Native Runtime Standards

- C++ runtime code must be buildable on Mac for host tests and on RunPod for
  Android arm64 when applicable.
- Phone runtime must not require Python unless a gate explicitly permits a
  temporary diagnostic script.
- OpenCL/Vulkan backend selection must be empirical.
- CPU fallback must be explicit and cannot satisfy an Adreno gate.
- Kernel launch, buffer allocation, and transfer paths must be visible enough
  to audit.

## 11. Artifact Policy

### 11.1 Git-Allowed

- source code;
- small schemas;
- runbooks;
- text reports;
- JSON manifests;
- small reference metadata;
- checksums;
- command logs with secrets redacted.

### 11.2 Git-Forbidden

- model weights;
- raw large tensor outputs;
- `.safetensors`;
- `.bin` model or output payloads;
- `.tflite`, `.litertlm`, `.task`;
- SDK binaries;
- build directories;
- caches;
- `.venv`, `venv`, `node_modules`;
- `.env`, `.env.local`;
- HF tokens, phone token files, SSH keys, service credentials.

### 11.3 Report Layout

Use:

```text
runtime/reports/gemma4_megakernel/
  parity/<run_id>/
  forward_stack/<run_id>/
  backward/<run_id>/
  optimizer/<run_id>/
  data_pipeline/<run_id>/
  train_loop/<run_id>/
  sustained/<run_id>/
  falsifiers/<run_id>/
```

Every run directory must include:

- `gate_result.json`;
- `commands.log`;
- `artifact_manifest.json`;
- `device_manifest.txt` when phone is involved;
- `blockers.md`;
- lane-specific telemetry or comparator JSON.

## 12. GitHub Route

The existing public `main` branch represents pre-pivot work and is deprecated
for this lane. It may be mined for harness evidence, but it is not the route.

Required route:

1. Create a pivot branch from current repo state, for example:
   `gemma4-megakernel-native-training`.
2. Import Gemma4 Kernel under a namespace, not as root overlay.
3. Preserve upstream commit hashes.
4. Commit PRD, GPD state, import manifest, source, runbooks, tests, and text
   evidence.
5. Push the branch to `https://github.com/Zer0pa/Polymath-AI`.
6. Do not merge old PR #4 blindly.
7. Do not rewrite unrelated user changes.

This branch should become the canonical route for Polymath-AI unless the
operator explicitly chooses another route.

## 13. Phone Data Pipeline Specification

### 13.1 Stream Reader

The phone stream reader must:

- authenticate without printing token values;
- support resumable reads where the source allows it;
- write raw chunks to a bounded staging area;
- record dataset id, split, revision, shard id, byte offsets if available, and
  license/provenance;
- handle network interruption by retrying or pausing without corrupting packed
  shards.

### 13.2 Tokenizer

The tokenizer must:

- run on phone CPU;
- use the Gemma tokenizer matching the model revision;
- produce token IDs identical to a reference for fixed samples;
- record tokenizer version, vocab hash, and normalization settings.

### 13.3 Sequence Packer

The packer must:

- run on phone;
- produce fixed-shape batches for the current executor profile;
- record pad positions and attention masks;
- write packed shards to UFS with checksums;
- allow deterministic replay for verification.

### 13.4 Corpus Scope

The first authority training slice should be dense and small enough to debug:

- license-clean;
- HF-hosted or HF-addressable;
- text-only for the first run;
- sufficient to produce multiple batches and a real update;
- not a broad corpus construction project.

Corpus expansion begins only after the integrated loop consumes the first slice.

## 14. Safety And Device Protection

Phone operations must preserve:

- existing binaries by checksum before overwrite;
- rollback path for runner and layer packs;
- available storage margin;
- battery and thermal safety;
- token secrecy.

Safety stops are allowed. A safety stop is not a pass. It is either a blocked
gate or a falsifier, depending on cause.

## 15. Falsification Protocol

Every promoted gate requires a falsifier report. At minimum, falsifiers must
answer:

- Did this run use the claimed model revision?
- Did it use real pretrained weights?
- Did phone compute run on the claimed backend?
- Did any hidden host path serve runtime data?
- Are pad tokens inflating the metric?
- Were tolerances changed?
- Did frozen tensors mutate?
- Did the checkpoint replay?
- Did G1 remain green?
- Are artifacts sufficient for a fresh executor to reproduce or diagnose?

If any answer is unknown, the claim is not promoted.

## 16. Overnight Execution Contract

The overnight executor must:

1. Read this PRD, `RESISTANCE-V2.md`, `.gpd/STATE.md` if present, and the latest
   runlog.
2. Confirm hardware access: RunPod SSH and REDMAGIC ADB.
3. Create or repair formal GPD project state.
4. Create the pivot GitHub branch.
5. Import Gemma4 Kernel source and evidence under policy.
6. Rerun or preserve G1 as regression.
7. Execute the next incomplete gate in the ladder.
8. Use GPD plan/execute/verify and targeted numerical checks.
9. Convert blockers into tasks unless they are true boundary blockers.
10. Run falsifier review before promotion.
11. Commit and push material results.
12. Write final handoff only after gate pass, fail, or honest block.

No interim reporting is required. No narratable win is sufficient.

## 17. Immediate Next Actions

1. Retire top-level old `PRD.md` as a drift vector and point it to this PRD.
2. Initialize or repair formal GPD project files from this PRD.
3. Create the GitHub pivot branch.
4. Import Gemma4 Kernel source and the passed gate evidence under
   `integrations/gemma4-snapdragon-megakernel/`.
5. Plan GPD Phase 1: import and regression harness.
6. Execute GPD Phase 1, verify, then proceed to forward expansion.

The next agent must not reopen whether the first phone gate passed. It passed.
The work is to build from it without shrinking the objective.
