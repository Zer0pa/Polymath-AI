# PRD: Gemma4 Polar Learning Fabric

Date: 2026-06-25
Repository: `/Users/Zer0pa/Polymat AI/Polymath-AI`
Authority runtime: REDMAGIC NX789J / Snapdragon SM8750 / serial FY25013101C8
Initial execution target: Codex in Termux on the authority phone
Scope: Full polar learning fabric PRD, with Phase 1 build-agent gate first
Execution posture: autonomous end-to-end Phase 1 build on the phone, not
manual subgate supervision
Phone authority posture: independent executive authority inside Termux

Phase 1 governing addendum:
`docs/PRD-POLAR-PHASE1-QA-ZIG-MAXIMAL-2026-06-25.md` supersedes the
dictionary/megascience hot-path split below for the next Phase 1 build. The new
Phase 1 target is one QA-native stream engine, Zig-primary, with dictionary and
MegaScience material normalized into the same QA contract before tokenization.

## 1. Governing Intent

This project is no longer trying to make the previous residual-adapter OpenCL
lane look successful. The new architecture is a polar learning fabric anchored
to frozen Gemma4 intelligence.

The governing mechanism is:

```text
Stage 0/1 source material
  -> Phase 1 CPU ingestion/chopping
  -> Phase 2 CPU JL binary/polar packetization
  -> Phase 3 NPU binary/polar forward read
  -> Phase 4 GPU polar optimizer
  -> double-buffered checkpoint
```

The pivot is not a conservative variant of standard Gemma inference. The NPU
boundary is the JL-transformed binary polar tensor. Token IDs are not the
accelerator boundary for Phase 3. The CPU performs the heavy lookup and binary
compression so the NPU receives an already shaped binary meal.

The project must preserve the alien mechanism before making it practical. Do
not replace it with token-ID QNN inference, ordinary LoRA, adapter-only proof
narratives, MVPs, demos, or de-risked conventional architectures.

## 2. Doctrine

Never:

- optimize for a narratable win instead of the governing objective;
- let local improvements substitute for the authority metric;
- close early because something defensible-looking exists;
- reward hacks;
- rush;
- downgrade the polar boundary back into standard token-ID inference;
- promote Mac, RunPod, documentation, or scaffold artifacts as phone authority;
- call anything a megakernel unless it is a real fused/static/routed training
  path with measured benefit;
- treat standard Cartesian LoRA as the destination.

Always:

- treat the top acceptance gate as sovereign;
- treat any regression on the authority metric as failure;
- keep docs and handover artifacts frozen until the real gate is met;
- stay in the fix loop instead of converting mixed evidence into a pass
  narrative;
- protect the novel mechanism from premature legibility;
- ask what assumption the design violates and what becomes buildable if it is
  true;
- expand the hypothesis space first, map disruptive implications second, and
  falsify third.

Coding commandments:

- avoid deep nesting;
- avoid code duplication;
- use names a future engineer can understand;
- use dependency injection where it decouples real components;
- use interfaces where they separate ownership boundaries cleanly;
- keep functions to individual responsibilities where it makes sense.

Dependency hygiene:

- do not create arbitrary local Python environments;
- inspect manifests and lockfiles before installing dependencies;
- prefer `uv` and a single `.venv` only when the repo actually needs one;
- do not install project dependencies into global or user Python;
- use Python 3.11 unless the repo declares otherwise;
- for Node work, use the package manager implied by the lockfile;
- do not commit `node_modules`, `.venv`, env files, tokens, model weights, raw
  tensor payloads, SDK binaries, QNN/DLC payloads, or phone secrets.

## 3. Source Modes

The backend learning fabric is mode-agnostic after Phase 1. The difference
between dictionary work and scientific corpus work is the ingestion contract.

### Stage 0: Dictionary Neurosurgery

Stage 0 performs closed-loop semantic cognitive enrichment over supplied
dictionary material. The user supplies the dictionary/library. Phase 1 does not
parse textbook paragraphs or hunt for Q/A triggers. It feeds direct semantic
relations into the packetizer contract.

Examples:

- token A + synonym token B;
- term + definition anchor;
- concept + contrast relation;
- symbol + natural-language referent;
- discipline-specific vocabulary pair.

Stage 0 is not a toy. It is a legitimate first gear of the system: direct,
closed-loop semantic adjustment before large scientific corpus training.

### Stage 1: MegaScience Corpus

Stage 1 ingests structured scientific text, especially textbook Q/A material.
Phase 1 enables the finite-state machine for raw paragraphs and emits fixed
training spans from delimiters such as `Q:`, `?`, `A:`, final punctuation, and
continuation boundaries.

Stage 1 must not be weakened to fit Stage 0. It is a separate data gear that
feeds the same downstream polar packetization and learning substrate.

## 4. Phase Architecture

### Phase 1: Ingestion and Chopping on CPU

Artifact:

- native phone-resident ingestion engine;
- Zig first, C++ fallback where existing Gemma BPE code is clearly superior;
- mode switch: `dictionary` or `megascience`.

Input:

- Stage 0 dictionary relations supplied by the user;
- Stage 1 raw MegaScience text or already extracted Q/A text.

Output:

- deterministic token stream and span metadata for Phase 2;
- mode-tagged records with loss-mask intent, segment roles, position policy,
  and continuation policy;
- no hot-loop heap allocation after initialization.

Phase 1 is the first Termux build-agent target.

### Phase 2: Mechanical Packetization on CPU

Artifact:

- Zig packetizer and JL transformer, C++ fallback only if it beats the Zig path
  under the acceptance gate.

Input:

- token stream and span metadata from Phase 1.

Action:

- seal exactly 128-token records;
- pad mechanically;
- perform embedding lookup on CPU;
- apply fixed Rademacher JL transform;
- emit binary polar tensor blocks.

Language lock:

- Zig is official for Phase 2 because `comptime` bakes the fixed JL `R` matrix
  into the binary. The phone pays zero runtime construction cost.

Output:

- fixed 128-token binary polar tensor meal in shared memory;
- answer/target binary polar representation for Phase 4 hinge loss;
- mask and metadata fields needed by the GPU optimizer.

### Phase 3: NPU Binary/Polar Forward Read

Artifact:

- fused/static NPU forward-read path over the binary polar tensor boundary.

Input:

- JL-transformed binary polar tensors from Phase 2, not raw token IDs.

Action:

- consume pre-shaped binary polar blocks;
- run frozen Gemma-anchored forward read over active adapters;
- write activation tensor to shared memory.

The key design assumption is that moving embedding lookup and binary
compression before the NPU creates a frictionless accelerator boundary. The
engineering job is to build that world, not retreat to a familiar graph
boundary.

### Phase 4: GPU Polar Optimizer

Artifact:

- fused GPU optimizer path over Adreno/OpenCL or successor GPU substrate.

Input:

- activation tensor from Phase 3;
- true answer transformed into the same binary polar space;
- active rank-8 polar residual adapter state.

Action:

- binary hinge loss in polar space;
- LCSB horizontal adapter gradient for the selected layer band;
- fp16 angle-space accumulation;
- periodic snapping into permanent binary space;
- double-buffered UFS checkpoint every configured interval.

Training scope:

- explicitly not full model training;
- explicitly not standard Cartesian LoRA;
- frozen Gemma4 anchor plus rank-8 polar residual adapters;
- angle updates are the trainable state.

## 5. Language Decisions

### Locked Choices

Phase 1:

- Zig first where the component is new and deterministic.
- C++ fallback for existing Gemma BPE/tokenizer code if reuse is materially
  better than rewrite.

Phase 2:

- Zig locked for packetization and JL transform.
- C++ fallback only as an evidence-backed escape hatch.

Phase 3:

- C/C++ ABI boundary to Qualcomm/QNN/HTP tools where required.
- Zig may produce support libraries, but the QNN/HTP integration layer must
  obey the hardware SDK reality.

Phase 4:

- OpenCL C/C++ runner first because Adreno/OpenCL and
  `cl_qcom_recordable_queues` are already proven tool surfaces in this repo.
- Zig/Rust may own control-plane or state tooling only if they strengthen the
  hot path.

Python:

- allowed for upstream corpus preparation, report mining, reference checks, and
  orchestration outside the phone hot loop;
- forbidden as a phone authority hot-loop dependency.

Rust:

- valuable for deterministic host tooling and ownership-heavy state machines;
- not the first hot-loop choice while Zig `comptime` is central to Phases 1/2.

Go/Julia/Mojo/Nim:

- not hot-loop authority defaults for this milestone.
- They may be researched later for isolated roles, but no novelty language may
  slow the phone acceptance gate.

## 6. Full-System Acceptance Gate

The full polar learning fabric is accepted only when the REDMAGIC phone runs
the end-to-end loop with:

- Stage 0 or Stage 1 source material ingested on phone;
- Phase 2 binary polar packets emitted on phone;
- Phase 3 NPU forward read consuming binary polar tensors;
- Phase 4 GPU polar optimizer updating rank-8 angle-space adapter state;
- double-buffered checkpoint persistence;
- no Mac/RunPod runtime substitution;
- fixed-shape loop telemetry;
- thermal safety maintained;
- useful learning movement under the predeclared mode-specific metric.

No partial scaffold can promote the full claim.

## 7. Phase 1 Acceptance Gate

Phase 1 is not accepted because a tokenizer compiled, a sample ran, or a log
looks good. Phase 1 is accepted only when the phone-resident ingestion engine:

- runs inside Termux on the REDMAGIC without Mac per-iteration control;
- supports `dictionary` and `megascience` modes through one explicit interface;
- consumes real user-supplied dictionary material for Stage 0 once supplied;
- consumes a real or predeclared MegaScience-format text fixture for Stage 1;
- emits deterministic token records and span metadata;
- preserves exact Gemma BPE token parity against the existing trusted reference
  for a fixed test set;
- performs no dynamic allocation inside the sealed hot loop after
  initialization;
- writes compact artifacts only: JSON summaries, hashes, schemas, sanitized
  logs, and small fixtures where policy permits;
- produces a handoff contract that Phase 2 can consume without reinterpretation.

The gate is sovereign, but it is not a manual pause point. The Termux agent must
keep working through build, test, repair, and evidence generation until the full
Phase 1 gate is met or a real hard blocker prevents further progress. It must
not stop after a subcomponent compiles, after a first fixture passes, or after a
defensible-looking partial result.

Phase 1 nonclaims:

- no JL transform claim;
- no NPU claim;
- no GPU optimizer claim;
- no learning claim;
- no megakernel claim;
- no scientific-corpus training claim.

## 8. Termux Agent Operating Model

The phone Codex agent is the executive authority for Phase 1 once launched. It
is king of the castle inside the phone workspace. It can run long, build
locally, inspect local telemetry, fix failures, spawn local research/planning
subtasks where the available Codex/GPD tools support that, and emit evidence.
It cannot promote a gate by persuasion.

Supervision occurs at stage boundaries. Once Phase 1 is launched, the agent does
not ask the user to approve each internal workstream, test, refactor, or repair.
It drives Phase 1 end-to-end on the phone.

The Termux agent must:

- work in the phone checkout of this repo;
- read this PRD and `AGENTS.md` first;
- confirm device-local context: model, board platform, storage, memory,
  thermal baseline, shell, compiler availability;
- own its phone-local plan/execute/verify loop using the available GPD
  scaffolding;
- use high-reasoning subagents or parallel workers when the local Codex surface
  supports them, especially for evidence mining, implementation alternatives,
  tokenizer parity, allocation auditing, and falsifier review;
- inspect dependency manifests before installing anything;
- install only the minimum required Termux packages for the phase;
- avoid global Python project dependency installs;
- keep all forbidden payloads out of git;
- continue through all internal Phase 1 workstreams without manual subgate
  pauses;
- stop only when the full Phase 1 gate is met or a real hard blocker repeats
  after the agent has tried the obvious repair paths.

The Mac agent may prepare files, push code, and collect evidence, but the Phase
1 authority run belongs to the phone. Mac-side assistance must not convert the
phone run into a tethered Mac workflow.

Today objective:

- get Phase 1 working end-to-end on the phone if the phone toolchain and Codex
  environment allow it;
- do not stop at a demo;
- do not stop at a partial scaffold;
- do not stop at documentation;
- do not stop at "ready for implementation";
- stop only at Phase 1 gate completion or a concrete blocker that prevents the
  phone from continuing autonomously.

### Independent Executive Authority

The phone agent is not a remote shell for the Mac. It owns the phone-local
execution loop:

```text
discuss frozen PRD intent once
  -> inspect phone workspace
  -> map current repo/toolchain state
  -> plan Phase 1 work
  -> execute until the Phase 1 gate is met
  -> verify with phone-local evidence
  -> repair failures without asking for subgate approval
  -> emit compact artifacts and handoff
```

The Mac may bootstrap files, install missing phone prerequisites through ADB
when required, and collect final artifacts. After launch, Mac must not be in the
per-iteration build/test/research loop.

The phone agent may use GPD as its local research discipline:

- route the pivot into the correct milestone/phase once the user accepts this
  PRD;
- map research before coding when the implementation surface is unclear;
- plan the Phase 1 build from the accepted PRD;
- execute the plan autonomously;
- verify and falsify before emitting the final handoff.

The GPD loop is a discipline, not theater. GPD artifacts do not count as Phase 1
evidence unless the corresponding phone-local build/test/runtime artifacts also
exist.

### External Authority Tokens

The phone may need authenticated access to external services:

- Hugging Face for gated/source data and tokenizer/model metadata;
- GitHub for repository clone/pull/push or PR work if required;
- optional package registries only as needed by the accepted build.

Secrets policy:

- never commit tokens;
- never print tokens into logs;
- never place tokens in repo files;
- use Termux home config files, credential helpers, or environment files outside
  the repo;
- when Mac transfers a token to the phone, transfer it directly into a
  phone-local secret file with restrictive permissions and immediately verify
  only that authentication works, not the token contents.

Default phone secret locations:

- Hugging Face token: `$HOME/.cache/huggingface/token` or
  `$HOME/.huggingface/token`, whichever the phone tooling uses;
- GitHub auth: `gh auth login` state under Termux home, or SSH key managed
  outside the repo.

If no token is present, the agent should continue Phase 1 work that does not
require authenticated data access and report the missing credential as an
external-access blocker only when it blocks the accepted Phase 1 gate.

## 9. Phase 1 Build Workstreams

### Workstream A: Repo and Toolchain Footing

Goal:

- make Termux capable of building the Phase 1 ingestion engine without pulling
  the architecture back to Mac.

Deliverables:

- phone-local repo path;
- compiler/toolchain inventory;
- Zig version, C++ compiler version, Android/Termux ABI facts;
- build command;
- environment manifest with no secrets.

### Workstream B: Ingestion IR

Goal:

- define the narrow record contract between Phase 1 and Phase 2.

Deliverables:

- schema for `IngestRecord`;
- fields for mode, token IDs, segment roles, loss-mask intent,
  continuation tag, source hash, and deterministic record ID;
- zero ambiguity between dictionary and MegaScience modes.

### Workstream C: Dictionary Mode

Goal:

- support direct semantic relation ingestion without paragraph parsing.

Deliverables:

- parser for supplied dictionary relation format;
- deterministic relation-to-token-stream output;
- token parity checks;
- compact relation manifest.

### Workstream D: MegaScience Mode

Goal:

- support mechanical Q/A chopping without reasoning.

Deliverables:

- FSM for `Q:` / `?` / `A:` / terminal punctuation / continuation;
- span roles and loss-mask intent;
- deterministic output over fixed text fixtures.

### Workstream E: Gemma BPE Boundary

Goal:

- reuse or wrap the existing trusted Gemma BPE path without semantic drift.

Deliverables:

- exact token parity test set;
- reference comparison report;
- error taxonomy for tokenizer mismatches.

### Workstream F: Hot-Loop Allocation Audit

Goal:

- prove the sealed ingestion/chopping path does not allocate after init.

Deliverables:

- allocation instrumentation strategy appropriate to Zig/C++;
- phone-local report;
- failure mode if allocator use is detected.

## 10. Phase 1 Evidence Artifacts

Required compact artifacts:

- `phase1_termux_environment.json`
- `phase1_ingest_record.schema.json`
- `phase1_dictionary_mode_report.json`
- `phase1_megascience_mode_report.json`
- `phase1_token_parity_report.json`
- `phase1_allocation_audit.json`
- `phase1_gate_result.json`
- `README.md` summarizing commands and nonclaims

Forbidden artifacts:

- model weights;
- raw large token dumps;
- raw tensor payloads;
- `.safetensors`, `.pt`, `.pth`, `.npy`, `.npz`, `.gguf`, `.dlc`;
- SDK binaries;
- `.env`, tokens, SSH keys;
- `node_modules`, `.venv`, build caches.

## 11. Termux Codex Launch Prompt

Use this prompt after the phone repo and Codex-in-Termux environment are ready.
The prompt is intentionally stage-scoped.

```text
You are the Phase 1 Termux build agent for the Polymath-AI Gemma4 Polar
Learning Fabric.

Repository:
<PHONE_REPO_PATH>

Authority runtime:
REDMAGIC NX789J / Snapdragon SM8750 / Termux on-device

Authority role:
You are the independent executive authority inside the phone for Phase 1. You
are not a Mac-controlled script. Run the phone-local plan/execute/verify loop
autonomously until Phase 1 passes or a hard blocker prevents progress.

Read first:
1. AGENTS.md
2. docs/PRD-GEMMA4-POLAR-LEARNING-FABRIC-TERMUX-PHASE1-2026-06-25.md
3. Existing Gemma tokenizer/packer source under integrations/gemma4-snapdragon-megakernel/

Your mission:
Build Phase 1 only: phone-resident ingestion and chopping for the polar learning
fabric. Support two source gears:
- dictionary mode: direct supplied semantic relation records;
- megascience mode: mechanical Q/A text chopping.

Execution contract:
- You are autonomous for Phase 1 after launch.
- Do not pause after internal subgates.
- Do not ask whether to continue after a fixture, parser, schema, build, or
  parity check passes.
- Use the local GPD scaffolding for route/map/plan/execute/verify discipline
  where available.
- Use subagents or parallel high-reasoning workers where the local Codex
  environment supports them.
- Keep repairing until the full Phase 1 acceptance gate passes or a real hard
  blocker prevents continuation.
- The user supervises stage boundaries, not every internal step.

You are not building Phase 2 JL packetization, Phase 3 NPU forward read, Phase 4
GPU optimizer, or any learning claim.

Doctrine:
- Preserve the polar learning fabric. Do not normalize it into standard Gemma
  token-ID inference or ordinary LoRA.
- No demos, MVPs, safe wins, or narratable half-passes.
- The Phase 1 gate is sovereign.
- If evidence is mixed, stay in the fix loop.
- Do not edit docs/handover claims to create a pass narrative before the gate is
  actually met.

Phase 1 acceptance gate:
- runs locally in Termux without Mac per-iteration control;
- supports dictionary and megascience modes through one explicit interface;
- emits deterministic IngestRecord outputs and span metadata;
- passes exact Gemma BPE parity on a fixed test set;
- performs no dynamic allocation inside the sealed hot loop after init;
- writes compact artifacts only;
- emits phase1_gate_result.json with nonclaims.

Autonomous work loop:
1. Inspect repo, toolchain, and constraints.
2. Choose the smallest architecture that satisfies the full Phase 1 gate.
3. Implement dictionary and megascience ingestion through one shared
   IngestRecord contract.
4. Reuse the existing Gemma tokenizer where it is first-class; wrap from Zig or
   call C++ rather than rewriting blindly.
5. Add deterministic fixtures and parity checks.
6. Add allocation audit evidence for the sealed hot loop.
7. Run the tests and phone-local build.
8. Fix failures.
9. Repeat until the Phase 1 gate passes.
10. Emit compact evidence and a final handoff for Phase 2.

Initial commands:
pwd
uname -a
getprop ro.product.model
getprop ro.board.platform
df -h .
free -h || cat /proc/meminfo | head -40
git status --short --branch
rg --files | head -200
command -v codex || true
command -v zig || true
command -v clang || true
command -v gpd || true
command -v gh || true
python --version || true

Before installing anything:
inspect pyproject.toml, uv.lock, requirements.txt, package.json, lockfiles, and
existing build files. Do not install dependencies globally except Termux system
packages required for compilers/tools.

Stop conditions:
- tokenizer parity cannot be reproduced;
- Zig cannot build on-device and C++ fallback must be adjudicated by the user;
- hot-loop allocation cannot be measured or eliminated;
- dictionary and MegaScience modes cannot share a clean Phase 1 output
  interface;
- any step would require committing forbidden payloads.
- required Hugging Face or GitHub authentication is absent and the accepted
  Phase 1 gate cannot proceed without it.

Do not treat these as ordinary pauses. Before stopping, write the exact blocker,
the commands tried, the failing outputs, and the next concrete repair path.
```

## 12. Deployment Defaults

These are execution defaults so the phone agent can start without turning setup
into a planning session.

1. Phone repo path default:
   `/data/data/com.termux/files/home/Polymath-AI`
2. Repository transfer default:
   use Git clone/pull inside Termux if credentials/network permit; otherwise
   Mac pushes the working tree by ADB once, then the phone continues locally.
3. Stage 0 dictionary format default:
   JSONL, one relation per line, because it preserves typed fields without CSV
   quoting ambiguity.
4. Tokenizer default:
   use the existing C++ Gemma tokenizer as the source of truth immediately.
   Zig owns the new ingestion/chopping layer and calls or wraps the tokenizer
   until a Zig tokenizer replacement has parity evidence.
5. If a default fails on the phone, the Termux agent chooses the closest
   evidence-preserving fallback and records why.

## 13. Current Issues To Handle

There is no conceptual issue with the pivot. The practical issues are execution
surface issues:

- Termux autonomy is desirable, but Codex-in-Termux must be treated as a phone
  executor, not a proof authority by narration.
- Zig on Android/Termux must be verified on the device before the Phase 1 agent
  assumes it is available.
- Existing C++ Gemma tokenizer code is likely first-class evidence and should
  not be rewritten blindly if reuse preserves parity faster.
- The first Stage 0 dictionary file format needs to be fixed before the Phase 1
  dictionary parser is implemented.
- GPD state should be updated only after this PRD is accepted, because the pivot
  changes the architectural authority.

## 14. Phone Bootstrap Status

ADB facts observed on 2026-06-25:

- `adb devices -l` sees `FY25013101C8` as device `NX789J`;
- `getprop ro.product.model` returns `NX789J`;
- `getprop ro.board.platform` returns `sun`;
- Termux and Termux:API are installed;
- `run-as com.termux` is blocked because the installed Termux package is not
  debuggable;
- Termux external `RUN_COMMAND` service is not available on this build;
- normal ADB shell therefore cannot execute directly inside Termux private
  home.

Bootstrap path staged on the phone:

```text
/sdcard/Download/polymath/polar_phase1/
  AGENTS.md
  PRD-GEMMA4-POLAR-LEARNING-FABRIC-TERMUX-PHASE1-2026-06-25.md
  TERMUX-POLAR-PHASE1-CODEX-LAUNCH-PROMPT-2026-06-25.md
  bootstrap_polar_phase1_exec.sh
  Polymath-AI-working-tree.tar.gz
  RUN_THIS_IN_TERMUX.txt
```

The required user/phone-local handoff command is:

```bash
bash /sdcard/Download/polymath/polar_phase1/bootstrap_polar_phase1_exec.sh
```

After that command runs inside Termux, the phone-local executive environment is
expected to create:

```text
~/Polymath-AI/
~/polymath_polar_phase1/reports/phase1_phone_executive_readiness.json
```

If GitHub clone fails, the bootstrap extracts the staged working-tree tarball.
If `/sdcard/Polymath/.hf-token` exists, the bootstrap copies it into
Termux-private Hugging Face cache without printing token contents.

## 15. GPD Routing Recommendation

This pivot changes the prior architectural conclusion rather than adding a
small layer to the old Phase 15 path. The clean GPD move after user acceptance
is to treat this as a new milestone or a Phase 15 revision, not as a routine
subphase. The old SCHTM/Phase 15 artifacts become quarry evidence.

Do not update GPD state until the user accepts the PRD direction.
