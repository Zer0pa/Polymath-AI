# PRD: Apex Heterogeneous Cell End-To-End Run

Document Class: AUTHORITY_PRD
Status: DRAFT_READY_FOR_REVIEW_AND_MOBILIZATION
Created: 2026-07-03
Owner: MetaOrchestrator #4 / Objective Governor
Repository: /Users/Zer0pa/Polymat AI/Polymath-AI
Branch observed during drafting: gemma4-megakernel-native-training
Authority runtime: REDMAGIC / Snapdragon SM8750 class phone
Prior evidence anchor: 545abb5571a6daba851af861c9e139352171b73d
External packet custody anchor: 581e87cd73176d688c9fff35ea1b69bdd38c61d0

## 0. Decision

The heterogeneous-cell program is past the island-proving phase.

The layer0 evidence closed the hardest mechanical feasibility question:
real Gemma 4 E4B layer0 weights executed through QNN/HTP, produced a
fixed-shape tensor, handed that exact tensor by SHA into an Adreno/Vulkan
consumer, and produced a finite adapter-update surface.

That does not prove full training. It does change the operating law. New work
must now serve one apex end-to-end run or a named falsifier of that run. Further
micro-islands are not progress unless they repair a blocker inside the apex
integration path and return directly to the apex gate.

## 1. Objective Contract

```yaml
OBJECTIVE_CONTRACT:
  terminal_objective: "Phone-native Gemma 4 training on heterogeneous SM8750 compute."
  active_edge: "Apex Heterogeneous Cell."
  current_gate: "protocol_ratification_and_apex_command_package_mobilization"
  authority_metric: "Integrated corpus -> packet -> QNN/HTP -> Adreno/Vulkan -> polar theta-only update loop with finite real Q/A loss and raw-boundary proof."
  acceptance_gate: "One metadata-only phone authority report proves a real corpus sample reached a QNN/HTP Gemma path, the resulting tensor SHA was consumed by the Adreno GPU update path, polar magnitude stayed invariant while theta changed, and repeated supervised update steps produced finite loss/update telemetry or a preregistered falsifier."
  first_missing_green_field: "apex_command_package_for_integrated_corpus_to_qnn_htp_to_vulkan_theta_only_training_loop"
  owner: "MetaOrchestrator #4 / Objective Governor"
  forbidden_shortcuts:
    - "synthetic hidden-state replacement at the apex boundary"
    - "QNN-only or Vulkan-only micro-island promotion"
    - "adapter delta presented as learning"
    - "host, RunPod, server, or Mac gradient/optimizer authority"
    - "dirty worktree or narrative handoff as evidence"
    - "Vulkan silently renamed as OpenCL"
  evidence_required:
    - "corpus/model immutable revision metadata"
    - "tokenizer/FSM/JL packet lineage"
    - "QNN graph/device/context/output shape/dtype/bytes/SHA"
    - "GPU backend/device and consumed tensor SHA"
    - "polar magnitude and theta pre/post hashes"
    - "finite supervised Q/A loss and update norm over repeated steps"
    - "thermal/throughput telemetry for any sustained claim"
    - "raw/secret boundary scan"
  stop_conditions:
    - "CPU fallback under QNN/HTP or GPU claim"
    - "SHA mismatch"
    - "nonfinite loss or update norm"
    - "polar magnitude drift beyond tolerance"
    - "adapter theta unchanged when update is claimed"
    - "raw payload or secret enters git/report"
```

Build and execute a phone-native apex heterogeneous training run that joins the
previously separate chains:

```text
HF C1-C4 corpus row
  -> Phase 1/2 tokenizer + FSM/JL packetizer
  -> Gemma 4 fixed-shape QNN/HTP forward path
  -> SHA-verified Adreno/Vulkan consumer
  -> polar angle-only adapter update
  -> repeated supervised Q/A loss loop
  -> metadata-only authority report
```

The objective is not to create another defensible sub-result. The objective is
to discover whether the integrated phone-native training cell can produce a
real supervised learning signal, or to isolate the first architectural
assumption that fails.

## 2. Authority Metric

### Current Bounded Authority

The existing green field is bounded:

```text
bounded layer0 QNN/HTP -> Adreno/Vulkan -> adapter-update evidence
```

It is green because the metadata report records a real-weight Gemma 4 E4B
layer0 FFN/residual island, QNN output `[1,16,2560]`, exact QNN/GPU SHA
equality, Vulkan execution on Adreno, adapter pre/post SHA delta, finite scalar
loss, finite update norm, and clean raw-boundary scans.

That current field is the platform for the apex run. It is not the apex run.

### Apex Authority

The sovereign metric is an apex end-to-end authority report from the phone that
proves all of the following in one integrated run:

- A real C1-C4 curriculum Q/A sample or approved heldout shard is consumed.
- The sample is transformed through the Phase 1/2 tokenizer, FSM, and JL packet
  sidecar path, not replaced by a synthetic hidden tensor.
- The QNN/HTP Gemma path consumes the resulting fixed-shape model input or a
  recorded, justified bridge from that input.
- The QNN output tensor has declared shape, dtype, byte count, and SHA.
- The Adreno/Vulkan update path consumes the exact QNN output SHA.
- The adapter update is polar angle-only: magnitude buffers remain invariant,
  angle buffers mutate, and the report measures both.
- The loop runs for more than one supervised update step on real Q/A loss.
- Loss is finite at every reported step and shows a predeclared useful signal:
  decreasing trend, non-random directional movement, or a falsifier explaining
  why the signal cannot be produced.
- Frozen base weights, raw payload custody, and secret boundaries remain clean.

The authority metric is not satisfied by:

- another QNN-only island;
- another Vulkan-only adapter update;
- another synthetic `[1,16,2560]` hidden-state input;
- another adapter delta without polar magnitude invariance;
- another single adapter mutation without repeated-step evidence;
- another train-loss scalar not tied to real Q/A data;
- a Mac, RunPod, server, or host-computed gradient/update path;
- a narrative that "integration is obvious" after local component green.

### Backend Policy

The current working GPU backend is Adreno/Vulkan. For this PRD, the apex
minimum accepts an explicit `Adreno GPU consumer` requirement and therefore may
use Vulkan if all SHA, device, and update invariants pass.

OpenCL remains unproven. If a downstream claim specifically requires
`OpenCL`, then Vulkan evidence is adjacent evidence only and an OpenCL parity
gate must be added before that claim can pass.

## 3. Acceptance Gates

### Gate A: Apex Command Package

Phase Engineering must produce one command package that is apex-shaped before
Execution runs anything. It may contain internal stages, but it must not be a
micro-island ladder.

Required fields:

- exact corpus source and immutable dataset/model revision evidence;
- tokenizer/FSM/JL packet path and checksums;
- QNN/HTP graph identity, source identity, shape contract, and selected weight
  manifest;
- Vulkan adapter-update path and polar invariant contract;
- stop conditions wired into the runner;
- raw-boundary scan plan;
- expected metadata-only reports;
- NEXT_HANDOFF target to Execution if command-ready, or Pipeline if validation
  is needed first.

### Gate B: Minimum Apex Run

The minimum non-incremental run may use reduced layer count only if it preserves
the full dataflow from corpus to update.

Minimum acceptable form:

- at least one real Gemma layer0 QNN/HTP island using selected real weights;
- no synthetic hidden-state replacement at the apex boundary;
- one phone-local supervised Q/A sample path;
- at least 8 consecutive update steps or a stop-condition failure before 8;
- exact SHA continuity from QNN producer to Vulkan consumer every step;
- polar magnitude drift measured and bounded;
- finite loss and finite update norm every successful step.

This is not a broad training claim. It is the first integrated apex claim.

### Gate C: Target Apex Run

The target run extends Gate B toward the intended design:

- multiple Gemma decoder layers, with explicit layer coverage;
- layer-cyclic selective backpropagation schedule;
- real heldout before/after measurement on a small fixed C1-C4 shard;
- thermal and throughput telemetry;
- comparison against the current bounded layer0 evidence and any unfused
  adapter baseline that exists under the same data.

Gate C is not allowed to regress into a sequence of unrelated local greens.
Every scale step must preserve the full corpus-to-update chain.

### Gate D: Learning And Quality Evidence

After the first integrated run exists, progress toward "Gemma can be trained on
this phone" requires quality movement, not just update movement.

Required preregistration before any learning claim:

- training loss trajectory on real supervised Q/A data;
- heldout loss or perplexity on a fixed small shard;
- instruction-following regression tolerance;
- polar LCSB convergence comparison against a declared baseline when feasible;
- JL binary projection signal check against the float embedding source when
  feasible;
- thermal envelope and steps/hour for any sustained-throughput statement.

Gate D fails if the adapter mutates but the preregistered quality metric does
not move, or if movement is explainable only by a synthetic or mismasked scalar.

## 4. Nonclaims

Until the apex gates emit authority evidence, the project does not claim:

- full heterogeneous closure;
- full Gemma HTP/QNN forward;
- OpenCL success;
- Phase 3/4 readiness;
- C1-C4 corpus-scale training;
- C5 pass;
- 100k or 1M authority;
- model-quality improvement;
- Comet-backed accepted training;
- raw payload custody in git.

After Gate B, the only new claim allowed is:

```text
bounded integrated corpus-to-QNN-to-Vulkan polar-adapter update evidence
```

Anything stronger requires Gate C or later evidence.

## 5. Boundary And Forbidden Artifacts

Allowed in git:

- source code;
- small schemas;
- text PRDs and reports;
- JSON gate results;
- manifests;
- checksums;
- summaries;
- sanitized command logs;
- metadata-only run ledgers.

Forbidden in git:

- model weights;
- raw large tensor binaries;
- raw phone output payloads;
- adapter binary checkpoints unless explicitly whitelisted as metadata-only;
- SDK binaries;
- `.env`, `.env.local`, service-token files, HF tokens, GitHub tokens, Comet
  tokens, phone token files, SSH keys;
- `.venv`, `venv`, `node_modules`, build caches.

Phone is the authority runtime. Mac is the control plane. RunPod is a
build/reference oracle only. GitHub is custody/distribution only. Comet is a
metrics mirror only. Hugging Face is corpus/model retrieval only.

## 6. Innovation Primer

```yaml
innovation_primer:
  objective: "Run one phone-native apex heterogeneous training cell from real corpus row to polar adapter update."
  authority_metric: "Integrated corpus -> packet -> QNN/HTP -> Vulkan -> theta-only update loop with finite real Q/A loss and raw-boundary proof."
  known_constraints:
    - "Phone is the authority runtime."
    - "Raw model/tensor/adapter payloads stay out of git."
    - "The layer0 result proves mechanical crossing, not full training."
    - "OpenCL failed on the final path; Vulkan is the working GPU consumer unless policy requires OpenCL parity."
    - "Gemma 4 promoted gates cannot use Qwen, SmolLM, random-init, hidden-size bridged, or synthetic substitutes."
  frontier_prior_art:
    - source: "MobileFineTuner"
      useful_pattern: "Native C++ phone fine-tuning validates that mobile training can be real."
      insufficiency: "Does not prove NPU-forward/GPU-update split across accelerators."
      zpp_adaptation: "Use it as a baseline class, not as the architecture."
    - source: "MobiLLM"
      useful_pattern: "Keeps frozen mobile backbone and trains side network."
      insufficiency: "Offloads backward to server, so it does not answer phone-native backward."
      zpp_adaptation: "Reject server backward as authority substitution."
    - source: "MobiZO"
      useful_pattern: "Avoids backward through forward-only gradient estimation."
      insufficiency: "Does not test gradient-based polar adapter training."
      zpp_adaptation: "Use as contrast, not as fallback unless apex falsifies gradient path."
    - source: "PockEngine and TinyTrain"
      useful_pattern: "Sparse, compile-aware update scopes reduce edge training cost."
      insufficiency: "Data-driven or conventional sparse backprop, not deterministic polar LCSB on Adreno."
      zpp_adaptation: "Pre-register LCSB falsifiers and compare only after integrated phone path exists."
    - source: "Qualcomm heterogeneous AI stack and NPU RAG findings"
      useful_pattern: "NPU is the correct forward engine; GPU can serve non-inference compute."
      insufficiency: "Does not publish on-device LLM backward split across NPU and GPU."
      zpp_adaptation: "Promote the proven HTP-to-Vulkan crossing as platform, then test integration and scale."
  rejected_conventional_paths:
    - path: "Continue validating isolated QNN operator islands."
      rejection_reason: "Feasibility crossing is already proven at layer0; islands now reward incrementalism."
    - path: "Use host or RunPod gradients to accelerate apex."
      rejection_reason: "Destroys phone-native training authority."
    - path: "Treat Vulkan as OpenCL success."
      rejection_reason: "Backend substitution must be explicit policy, not silent claim drift."
    - path: "Train on synthetic hidden tensors."
      rejection_reason: "Bypasses the corpus-to-packet gap now governing the apex."
  maximal_plan_implications:
    - "One integrated run is more informative than another micro-ladder."
    - "A failed apex run is valuable if it identifies the first broken architectural assumption."
    - "All lanes must reason at xhigh when mobilized."
    - "Protocol must delete drift instead of preserving stale apparent progress."
  hounds_of_popper_attacks:
    - "The loss moves because the scalar objective is synthetic, not because Q/A training works."
    - "The adapter changed but not by theta-only update."
    - "The QNN tensor consumed by Vulkan is not causally from the corpus packet."
    - "The run uses phone as a shell while host computes gradients or optimizer updates."
    - "A backend label hides CPU fallback, stale handoff labels, or raw payload leakage."
```

## 7. Anti-Incrementalism Protocol Amendment

This PRD adds the Apex-Over-Island rule to ZPP/ZPB operating law.

After a mechanical feasibility boundary has been crossed, the protocol must
change mode:

- Before boundary crossing, isolated probes may be valid if they narrow unknown
  hardware/toolchain risks.
- After boundary crossing, isolated probes are invalid as progress unless they
  repair a named blocker in the apex run.
- A lane proposing an island must include:
  - the apex field it repairs;
  - the exact falsifier it tests;
  - the maximum time or attempt budget;
  - the NEXT_HANDOFF route back to the apex owner.

The default question changes from:

```text
Can we make another component green?
```

to:

```text
What prevents the integrated apex run from executing now?
```

## 8. Reasoning And Agent Standard

All future mobilization prompts for this PRD must run at `xhigh` reasoning when
the tool surface supports it.

Required standard:

- Codex thread follow-ups must be sent with `thinking="xhigh"` when the API
  supports a thinking override.
- Sub-agents must be spawned with `reasoning_effort="xhigh"`.
- Existing threads that cannot have defaults changed must be mobilized only by
  a new message sent with the `xhigh` override where the tool supports it.
- If a tool cannot change an existing thread's default reasoning level, the
  mobilization prompt must explicitly state `XHIGH_REASONING_REQUIRED` and any
  actual send call must use the highest available reasoning override.
- No lane may claim route completion if it used lower reasoning for a
  route-changing decision, unless the platform made xhigh unavailable and the
  handoff records that limitation.

This is not cosmetic. It is a control against local-green compression and
premature closure.

## 9. Provider Access Protocol

Provider access is operational capability, not authority evidence.

### Hugging Face

Allowed uses:

- read approved model/dataset revisions;
- stream approved C1-C4 package files;
- record metadata-only revision/hash evidence.

Forbidden:

- print tokens;
- commit datasets, model weights, or raw payloads;
- use moving `main` as authority without immutable revision evidence;
- call absent auth a blocker before an authorized safe check fails.

### GitHub And Git Custody

Repo Custodian owns staging, committing, and pushing. Other lanes may inspect
status and propose custody packets but must not mutate git unless explicitly
authorized.

Every custody commit must include or be paired with:

- owner, branch, HEAD, and dirty-tree status;
- artifact paths and SHA-256 hashes;
- validation commands;
- committed file count and scope;
- raw/secret scan result;
- commit SHA and push result;
- current authority metric;
- first missing green field resolved or remaining;
- nonclaims;
- NEXT_HANDOFF to the next owner.

GitHub push requires explicit route authority. A local commit is custody, not
external publication. A dirty worktree is never an evidence anchor.

### Comet

Comet may mirror metrics after local JSON exists. Comet absence is not a
blocker unless the current gate explicitly requires dashboard evidence.

### RunPod

RunPod may build, inspect, or provide QAIRT/reference-oracle support. It must
not serve runtime minibatches, gradients, optimizer updates, or authority
training steps.

### Phone

The phone owns authority execution. Phone reports must be metadata-only when
entering git. Any command package must stop on CPU fallback under HTP/GPU
claims, SHA mismatch, nonfinite loss, magnitude drift violation, unchanged
adapter, raw payload leakage, or missing ledger fields.

Phone authority reports must include device identity, command, binary/source
SHA, backend identity, process exit status, QNN/profile identity where
applicable, tensor SHA lineage, adapter pre/post SHA, finite loss/update norm,
bytes moved, thermal/storage context, and raw-boundary proof.

## 10. Lane Topology

Active lanes for this PRD:

- MetaOrchestrator #4 / Objective Governor:
  owns objective contract, anti-drift pressure, route decisions, and final
  claim language.
  Thread: `019f27dd-2ddd-7fe1-8f55-59d7fe019a2d`.
- Phase Engineering:
  owns apex command package design and implementation pathset.
  Thread: `019f27dd-3879-79d0-9235-2a068349a706`.
- Pipeline Integrator:
  owns receiving validation of command packages and evidence reports against
  the authority metric.
  Thread: `019f27dd-4085-7d30-85e2-af95e5302a44`.
- Execution Orchestrator:
  owns bounded phone execution only after a command-ready package exists.
  Thread: `019f27dd-48a7-7012-a248-d2e070a96124`.
- Repo Custodian:
  owns staging, commits, pushes, provenance, and raw-boundary custody.
  Thread: `019f27dd-51e0-7012-a167-74c3a7ff4a2c`.
- Training Material Steward:
  owns model/corpus revision identity, hashes, and approved material manifests.
  Thread: `019f27dd-6793-78e3-9535-5df3ed6046c9`.
- Research Signal:
  owns bounded route-changing research signals, not narrative literature.
  Thread: `019f27dd-5cf7-7891-8218-49bf4956ec25`.
- Protocol and Process Steward:
  owns ZPP/ZPB amendments, drift deletion protocol, and linter/schema updates.
  Thread: `019f27dd-8231-7173-abc9-6c1d2011c460`.
- External Science Liaison:
  owns external-review framing and reviewer question packets.
  Thread: `019f27dd-90c1-7b50-88b2-a29a7344dbe6`.
- UI Operator Visibility:
  owns operator-facing status without overclaiming.
  Thread: `019f27dd-7366-7923-85eb-6322cd3172fb`.

Deprecated pre-new-epoch thread IDs and old refresh routes are historical unless
MetaOrchestrator #4 explicitly re-promotes them in a NEXT_HANDOFF.

## 11. Mobilization Plan

Mobilization is not "wake everyone." It is a single apex route.

### Step 1: Protocol and PRD Ratification

Owner: Protocol and Process Steward.

Task:

- accept this PRD as the current living objective;
- encode Apex-Over-Island into protocol/linter language;
- mark old island-validation lanes as historical unless tied to apex blockers.

NEXT_HANDOFF goes to MetaOrchestrator #4 and Phase Engineering.

### Step 2: Training Material Contract

Owner: Training Material Steward.

Task:

- specify the exact HF corpus shard, model revision, tokenizer/config identity,
  and allowed local cache paths;
- produce metadata-only material manifest;
- prohibit stale local package roots unless hash-matched.

NEXT_HANDOFF goes to Phase Engineering.

### Step 3: Apex Command Package

Owner: Phase Engineering.

Task:

- produce one command-ready package for the minimum apex run;
- include tokenizer/FSM/JL to QNN bridge;
- wire layer0 QNN/HTP output into Vulkan polar adapter update;
- include repeated-step supervised loss;
- include all stop conditions and raw-boundary scans.

NEXT_HANDOFF goes to Pipeline Integrator if validation is needed, otherwise
Execution Orchestrator with Pipeline cc.

### Step 4: Pipeline Receiving Validation

Owner: Pipeline Integrator.

Task:

- reject command packages that are disguised micro-islands;
- validate shape/SHA/polar/loss/raw-boundary contracts;
- decide if Execution may run.

NEXT_HANDOFF goes to Execution Orchestrator or back to Phase Engineering with
the exact first missing green field.

### Step 5: Phone Execution

Owner: Execution Orchestrator.

Task:

- run only the validated command package on phone;
- emit JSON evidence;
- stop immediately on falsifiers;
- no provider mutation unless explicitly routed.

NEXT_HANDOFF goes to Pipeline Integrator.

### Step 6: Evidence Freeze And External Framing

Owners: Repo Custodian, then External Science Liaison.

Task:

- freeze metadata-only reports;
- produce external claim language bounded to actual evidence;
- preserve nonclaims.

## 12. Handoff Schema

Every completion must emit:

```yaml
NEXT_HANDOFF:
  to: "<lane name and thread id>"
  status: "<exact status>"
  reasoning_level: "xhigh | xhigh_unavailable_with_reason"
  artifacts:
    - "<path plus sha256, or none with reason>"
  authority_metric: "<metric this handoff advances>"
  first_missing_green_field: "<one field>"
  next_action: "<concrete action>"
  prompt_to_send: "<ready prompt for next owner>"
  provider_access_needed: "none | hf | phone | runpod | comet | github"
  provider_access_state: "PENDING_ACTION_PROVIDER_NOT_NEEDED_FOR_CURRENT_EDGE | PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES | PENDING_ACTION_PROVIDER_AUTH_SURFACE_MISSING | BLOCKER_PROVIDER_AUTH_FAILED"
  provider_access:
    provider: "<none | hf | phone | runpod | comet | github>"
    owner_lane: "<lane>"
    bounded_command_family: "<exact safe check or command family, credential names only>"
    expected_metadata_artifact: "<path/hash or none>"
    stop_condition: "<condition>"
  raw_boundary_state: "<metadata-only proof or blocker>"
  research_escalation: "none | research_note | bounded_research_sprint"
  drift_action: "none | ignore_historical | delete_candidate | deletion_done_with_commit"
  nonclaims:
    - "<claim not made>"
```

Completed without NEXT_HANDOFF is a process defect. `BLOCKER` requires real
failed evidence. Known work is `PENDING_ACTION`.

## 13. Evidence Ledger

Current foundation:

- commit: `545abb5571a6daba851af861c9e139352171b73d`
- claim: bounded layer0 QNN/HTP -> Adreno/Vulkan -> adapter-update evidence
- QNN output shape: `[1,16,2560]`
- QNN/GPU SHA equality: true
- adapter delta: true
- finite scalar loss/update norm: true
- raw payload in git: false

External packet:

- path: `runtime/reports/external_handoff/POLYMATH_HETEROGENEOUS_CELL_EXTERNAL_TECHNICAL_PACKET_20260703.md`
- SHA-256: `8e78df8b4660b6162e343fdd9063418082e35e3e97601b8df2d801ce600ed019`
- local custody commit: `581e87cd73176d688c9fff35ea1b69bdd38c61d0`

Prior-art brief:

- path: `/Users/Zer0pa/Polymat AI/Mobile-Native LLM Training on Heterogeneous Compute  Prior Art & Research Brief for the Polymath AI   Zer0pa Gemma 4 E2B Pipeline.md`
- role: prior-art and research-gap substrate, not authority evidence.

## 14. Falsification Matrix

| Falsifier | Stop Condition | Owner | Consequence |
| --- | --- | --- | --- |
| Corpus chain absent | Input is synthetic hidden tensor or stale cache without manifest | Pipeline | Reject command package |
| QNN causality broken | QNN tensor cannot be traced to packetized corpus input or declared bridge | Pipeline | Return to Phase Engineering |
| SHA handoff fails | Vulkan consumed SHA differs from QNN output SHA | Execution | Stop run, emit failure report |
| Backend fallback | CPU fallback under QNN/HTP or GPU claim | Execution | Stop run, no authority claim |
| Polar invariant fails | magnitude buffer changes beyond declared tolerance | Execution/Pipeline | Reject theta-only claim |
| Adapter inert | angle/post SHA unchanged or zero update norm | Execution | Stop or classify no-learning surface |
| Adapter delta overclaimed | adapter changes but quality metric is absent or flat | Pipeline | Reject learning claim |
| Loss invalid | nonfinite supervised loss | Execution | Stop run |
| Loss meaningless | scalar not tied to real Q/A target/mask | Pipeline | Reject evidence |
| JL signal absent | binary projection preserves formal invariants but destroys adaptation signal | Pipeline/Research | Reroute or falsify JL hot-path assumption |
| LCSB weak | cyclic schedule completes but fails preregistered convergence floor | Pipeline/Research | Reroute schedule or falsify LCSB assumption |
| Thermal envelope fails | throttling invalidates sustained-throughput claim | Execution/Pipeline | Reject throughput/scale claim |
| Raw leak | raw tensor/model/profile/adapter payload enters git | Repo Custodian | Reject custody, quarantine by policy |
| Secret leak | token/credential appears in report/log | Repo Custodian | Stop and remediate |
| Micro-island drift | command package only validates a component without apex chain | Meta/Pipeline | Reject as process drift |

## 15. Drift Deletion And Cleanup

Drift must be removed from the active operating surface, not merely narrated
around.

Rules:

- Live use of C5 proxy loops as mainline, one-field-at-a-time patching as
  mainline, passive heartbeat routing, stale WaveC route tables, deprecated
  thread IDs, placeholder GO packages, and old immediate-next-action lists that
  conflict with this PRD is deleted from the active route surface immediately.
- Historical artifacts are not deleted by default; they are demoted from active
  authority unless a custody lane approves deletion.
- Stale central state that points to deprecated owners must be ignored as
  authority immediately and queued for Protocol/Repo cleanup.
- Deletion requires:
  - candidate path list;
  - why each path is stale;
  - whether the file is historical evidence or active-state drift;
  - raw/secret boundary check;
  - Repo Custodian commit or explicit non-deletion rationale.
- No implementation lane may use old pathsets, deprecated threads, or
  pre-layer0 authority claims as current route truth.

The cleanup objective is a lean active surface:

```text
living PRD + current lane map + current evidence ledger + current command package + current handoffs
```

Everything else is historical unless explicitly re-promoted.

## 16. Current Gate And Next Owner

Current gate:

```text
protocol_ratification_and_apex_command_package_mobilization
```

Recommended next owner:

```text
Protocol and Process Steward -> Phase Engineering
```

First missing green field:

```text
apex_command_package_for_integrated_corpus_to_qnn_htp_to_vulkan_theta_only_training_loop
```

No phone, provider, GitHub push, or raw payload action is authorized by this
PRD alone. Those require lane-specific NEXT_HANDOFF and custody/execution
authority.

## 17. Amendment Log

| Date | Change | Why | Evidence | Objective Effect | Nonclaims Preserved |
| --- | --- | --- | --- | --- | --- |
| 2026-07-03 | Created apex PRD and Apex-Over-Island rule | Layer0 real-weight QNN/HTP -> Vulkan adapter update crossed the prior-art mechanical feasibility boundary | commit `545abb5571a6daba851af861c9e139352171b73d`, packet SHA `8e78df8b4660b6162e343fdd9063418082e35e3e97601b8df2d801ce600ed019` | Upgrades route from micro-island validation to integrated apex run | no full closure, no full Gemma forward, no OpenCL pass, no C1-C4/C5/100k/1M/model-quality claim |
