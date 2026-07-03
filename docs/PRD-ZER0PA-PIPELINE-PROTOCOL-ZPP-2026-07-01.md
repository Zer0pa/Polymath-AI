# PRD: ZER0PA Pipeline Protocol

Status: Living protocol PRD, initial executable harness wedge
Created UTC: 2026-07-01
Owner: Meta-Orchestrator as Objective Governor and Living PRD Steward
Applies to: Polymath AI immediately; future Zer0pa long-horizon engineering and research workstreams

Active Polymath protocol supplement:
`docs/PRD-APEX-HETEROGENEOUS-CELL-END-TO-END-2026-07-03.md`
SHA-256: `a3606c186109c1597e43a793647cd7b7f3bd63c653d3986c25e1db09bf224a93`

## 0. Boundary

This PRD defines a reusable orchestration protocol. It does not authorize
phone gates, raw model payload handling, secret sourcing, Hugging Face pushes,
Comet calls, GitHub pushes, OpenRouter calls, or production deployment by
itself. Workstream-specific PRDs still govern execution surfaces.

Allowed in git: protocol text, schemas, validators, sanitized reports,
checksums, command templates, and non-secret provider setup instructions.

Forbidden in git: model weights, raw tensor payloads, raw phone payloads,
prediction payloads unless a governing PRD explicitly permits metadata-only
samples, `.env`, `.env.local`, service tokens, HF tokens, GitHub tokens,
OpenRouter keys, Comet keys, SSH keys, `.venv`, `node_modules`, build caches,
and SDK binary payloads.

## 1. Product Definition

The ZER0PA Pipeline Protocol, abbreviated ZPP, is a falsification-governed,
evidence-gated multi-agent pipeline protocol for frontier engineering work.

ZPP is not a chat workflow. It is not a committee of agents. It is not a
project-management ritual. ZPP is a deterministic outer harness that keeps a
maximal objective alive while specialized agents do replaceable work inside
bounded lanes.

The first implementation target is:

- A living PRD and operating specification.
- A Codex skill activation surface.
- A plugin packaging surface once the skill and validators are stable.
- A local harness that validates state, handoffs, blockers, research packets,
  evidence, and nonclaims.
- An optional MCP or daemon layer later for live coordination, leases,
  heartbeat state, dashboards, and cross-thread handoff dispatch.

## 2. Sovereign Objective

Build a reusable ZER0PA orchestration system that can start a maximal,
long-horizon technical pipeline, decompose it into lanes, keep a living PRD
coherent, force real handoffs, detect drift, trigger research at the correct
time, and prevent process theater from substituting for the authority metric.

The governing acceptance gate is not that agents produce plausible plans. The
gate is that a future workstream can be started from ZPP, executed by separate
lanes, resumed without conversation history, audited from artifacts, and judged
against its authority metric without narrative substitution.

## 3. What Makes ZPP Different

Existing agent frameworks provide useful machinery:

- Agent skills provide reusable procedures and progressive disclosure.
- Agent SDKs provide handoffs, guardrails, tools, and traces.
- Graph runtimes provide state, branches, interrupts, and replay.
- Workflow engines provide durable execution.
- MCP provides tool and context interoperability.

ZPP adds the missing operating law:

- The authority metric is sovereign.
- A lane is incomplete without an outbound `NEXT_HANDOFF`.
- Completed markers without handoff are process failure.
- Local green does not equal authority green.
- After a mechanical feasibility boundary is crossed, isolated probes are not
  progress unless they repair a named apex blocker and return directly to the
  apex gate.
- Context is loaded by budget and task, not by anxiety. Full PRDs, full
  central state, external packets, and old route tables are heavy sources, not
  default lane startup material.
- Research is not a prestige detour; it exists only to restore narrowing.
- Every claim must survive a Hounds of Popper falsification pass.
- Provider access is documented without exposing secrets.
- The living PRD prevents drift by being the canonical state of intent, not
  a retrospective story.

## 4. Maximalist Doctrine

ZPP must encode Zer0pa's maximalism as a mechanical constraint, not a mood.

### 4.1 Anti-Toy Rule

The protocol must reject MVP gravity. It must not ask what minimum version can
be narrated as success. It must ask what the best currently defensible version
is, what the next frontier version points toward, and what evidence would kill
or upgrade the path.

### 4.2 Objective Upgrade Rule

Objectives may be clarified, strengthened, decomposed, or upgraded. They must
not be silently downgraded after evidence appears. If evidence falsifies the
current route, the route changes; the governing objective remains unless a
named falsifier kills it.

### 4.3 Convention Resistance Rule

Language models are trained toward convention, compression, and plausible
closure. ZPP must counter this with explicit checks:

- Did the agent choose an ordinary enterprise pattern because it is familiar?
- Did it normalize the user's unprecedented demand into a routine build?
- Did it make a local, narratable win stand in for the authority gate?
- Did it reduce maximalism to adjectives instead of design consequences?
- Did it preserve the alien mechanism before making it legible?

### 4.4 Full-Stack Frontier Rule

For ZPP, "enterprise grade" is a floor, not a ceiling. The expected target is
better than enterprise-grade frontier engineering: reproducible, auditable,
durable, falsifiable, cross-domain, safety-bounded, and able to mobilize
specialist agents without losing objective pressure.

### 4.5 Apex-Over-Island Rule

When a workstream has crossed a mechanical feasibility boundary, ZPP changes
mode. Before the boundary, isolated probes may be valid if they narrow unknown
hardware, toolchain, or interface risks. After the boundary, isolated probes
are invalid as progress unless they declare all of:

- `apex_field_repaired`;
- `falsifier`;
- `attempt_budget`;
- `return_handoff_to_apex`.

The governing question becomes: what prevents the integrated apex run from
executing now? A lane that proposes another island, component green, probe
ladder, or local surface must name the apex blocker it repairs and route the
next `NEXT_HANDOFF` back to the apex owner. Otherwise the work is drift, even
if the local result is technically real.

### 4.6 Context Diet Rule

ZPP uses progressive disclosure for context. A lane starts from the smallest
packet that can preserve the authority metric and the current gate:

1. current-context capsule;
2. `NEXT_HANDOFF` addressed to the lane;
3. one relevant ZPP reference;
4. targeted PRD/report/state extracts;
5. full heavy files only when the lane owns that file or targeted extracts are
   insufficient.

Heavy files include full workstream PRDs, full ZPP PRDs, external handoff
packets, `EXECUTIVE_DELIVERY_STATE.json`, stale route tables, historical run
ledgers, and old watchdog mirrors. Loading a heavy file in full is allowed only
with a written `context_load` rationale in the next handoff.

This is a protocol requirement, not a token-saving preference. Overloaded
context increases stale-state capture, completed-marker drift, and local-green
substitution.

If the route can be affected by phone access, RunPod, Hugging Face, GitHub,
Comet, source SDK custody, model/corpus retrieval, experiment logging, or
external execution, the context capsule must include a targeted provider matrix
extract. This does not justify loading the full matrix or full central state.
It is the minimum operational map needed to avoid false user blockers.

### 4.7 Brief-Carried-Handoff Rule

Every lane mobilization brief must contain the incoming `NEXT_HANDOFF` that
justifies the lane's work. If Watchdog/Meta is repairing a malformed route, the
brief must contain `WATCHDOG_RECOVERY_HANDOFF` and mark that it is not a normal
producer handoff.

The brief must also contain the outbound `NEXT_HANDOFF` schema the lane must
return, including `context_load` and `handoff_dispatch_status`. Task-only
prompts without handoff fields are process drift because they force the next
lane to infer route authority from heavy state.

When provider capability can affect the route, the brief must also carry a
secret-free `provider_capability_capsule`. Provider capability is not optional
lane memory. A brief that asks for user source custody, auth repair, logging
repair, GitHub custody, or environment action before checking the provider
matrix is process drift unless it records exact failed safe checks for every
authorized surface.

If thread-send tooling is available, the producing lane must send the handoff
to the next owner before marking itself complete and set
`handoff_dispatch_status: SENT_TO_NEXT_OWNER`. If the tool is unavailable, it
must set `handoff_dispatch_status: TOOL_UNAVAILABLE`; Watchdog then owns
dispatching the carried prompt on the next tick.

## 5. Alien Engineering Research Loop

Every ZPP run begins with a research, think, plan, innovate loop before
execution starts. This loop is not optional planning theater. It is how ZPP
searches the design space before freezing the first executable path.

### 5.1 Loop Contract

The loop emits an `INNOVATION_PRIMER` before lane decomposition:

```yaml
innovation_primer:
  objective: string
  authority_metric: string
  known_constraints: string[]
  nature_analogs:
    - source_domain: string
      mechanism: string
      engineering_translation: string
      falsifier: string
  scientific_intersections:
    - domain: string
      candidate_principle: string
      expected_design_effect: string
      evidence_needed: string
  frontier_prior_art:
    - source: string
      useful_pattern: string
      insufficiency: string
      zpp_adaptation: string
  rejected_conventional_paths:
    - path: string
      rejection_reason: string
  maximal_plan_implications: string[]
  hounds_of_popper_attacks: string[]
```

### 5.2 Required Search Domains

The loop must search beyond software convention. Depending on the workstream,
the search set includes:

- Information theory: compression, error correction, coding theory, entropy,
  signal/noise separation, channel capacity, rate-distortion tradeoffs.
- Computational physics: locality, renormalization, conservation laws,
  variational principles, phase transitions, symmetry, path integrals, energy
  landscapes, geometric constraints.
- Bio-cognition: morphogenesis, active inference, homeostasis, memory in
  tissue, error correction in development, collective intelligence, Michael
  Levin-style agency gradients.
- Evolutionary systems: selection pressure, exaptation, mutation, speciation,
  redundancy, immune response, ecological niches, robustness under attack.
- Developmental biology: bootstrapping, gradients, pattern fields, repair,
  positional information, modularity, regeneration.
- Neuroscience and cognition: predictive processing, attention, compression,
  hierarchical control, sleep-like consolidation, deliberation, reflex loops.
- Geometric unity and mathematical physics: invariants, fibered structure,
  gauge-like constraints, symmetry breaking, dualities, topological protection.
- Computational universe thinking: simple rules generating complex behavior,
  rule spaces, computational irreducibility, observer-relative compression,
  Wolfram-style search across possible programs.
- Popperian epistemology: bold conjectures, severe tests, falsifiers,
  demarcation between evidence and story.

The point is not to decorate the PRD with scientific references. The point is
to extract engineering mechanisms that change architecture.

### 5.3 Analog Translation Rule

An analog is valid only if it produces all five outputs:

1. A source boundary: where the analogy comes from.
2. A mechanism: what is actually happening in the source domain.
3. An engineering translation: what changes in the system design.
4. A test: what observation would support or weaken the translation.
5. A stop condition: when to abandon the analog.

### 5.4 Research During Execution

Research is not dormant during execution. It becomes discretionarily mandatory
whenever a competent lane smells uncertainty, opportunity, anomaly, unexplained
success, unexplained failure, hardware behavior, performance signal, geometry,
or enigmatic mechanism that could change the path.

ZPP uses two research modes:

- `research_note`: lightweight, parallel, non-blocking. Use it whenever there
  is a signal worth capturing, including success points that may reveal a better
  architecture.
- `bounded_research_sprint`: deeper and potentially routing-affecting. Use it
  when uncertainty can waste execution, when a field repeats, when hardware or
  performance behavior is not explained, when geometry/source shape is unclear,
  or when the current path may be leaving a frontier mechanism unused.

Research may run in parallel with implementation. It must not become a holding
pattern. Every research output must produce at least one of: implementation
change, source boundary, formula/dataflow proposal, benchmark/falsifier,
stop condition, or explicit decision to continue current implementation.

Valid research packets require:

```yaml
research_escalation:
  mode: research_note | bounded_research_sprint
  trigger: uncertainty_smell | opportunity_signal | anomalous_failure | anomalous_success | hardware_signal | performance_signal | geometry_signal | repeated_field | architecture_contradiction | envelope_failure
  repeated_or_blocking_field: string
  why_execution_cannot_decide: string
  why_this_matters_now: string
  source_boundary: string[]
  formula_or_dataflow_proposal: string
  test: string
  stop_condition: string
  expected_metric_impact: string
  return_lane: string
```

Premature broad research that does not return to implementation is process
delay. Refusing research when a signal is anomalous, geometric, hardware-bound,
or frontier-relevant is also a process defect.

## 6. Living PRD Stewardship

ZPP requires a living PRD. The PRD is the drift-prevention authority for
intent, scope, gates, provider setup, lane definitions, and nonclaims.

### 6.1 Steward Role

Default owner: Meta-Orchestrator as Living PRD Steward.

For large runs, create a distinct `PRD Steward` lane. This lane owns:

- Keeping the PRD self-contained.
- Incorporating accepted lane discoveries without narrowing the objective.
- Recording amendments as additive deltas.
- Keeping provider access instructions current without storing secrets.
- Preventing stale summaries from becoming authority.
- Rejecting completed-marker passivity.
- Ensuring every lane's current task maps to the authority metric.

The PRD Steward does not own repo custody, runtime execution, or success
claims. It owns coherence.

### 6.2 Living PRD Amendment Rule

Every amendment must state:

- What changed.
- Why it changed.
- Which evidence forced or justified the change.
- Whether it upgrades, clarifies, or routes the objective.
- Which nonclaims remain preserved.
- Which `NEXT_HANDOFF` packets must be regenerated.

Silent narrowing is invalid.

### 6.3 Drift Prevention Surfaces

The PRD must link or embed:

- Objective contract.
- Role taxonomy.
- Lane briefs.
- Provider access protocol.
- Handoff schema.
- Research escalation schema.
- Falsification matrix.
- Evidence ledger rules.
- Current acceptance gate.
- Current nonclaims.
- Current forbidden shortcuts.

## 7. Provider Access Protocol

This section documents how lanes should access common providers without
embedding secrets in repo files or chat.

### 7.1 General Secret Rule

Agents must never print, copy, summarize, commit, or include secret values in
reports. They may report the presence, absence, or authentication status of a
provider using metadata-only language.

If a lane lacks provider access but the next action does not require it, use
`PENDING_ACTION_PROVIDER_NOT_NEEDED_FOR_CURRENT_EDGE`.

If access is needed and no token/session is available, use
`PENDING_ACTION_PROVIDER_AUTH_SURFACE_MISSING` unless an actual attempted
authenticated operation failed.

Use `BLOCKER` only after a real access, verification, or technical failure is
observed and evidence is recorded.

### 7.2 Provider Capability Capsule

Every route-changing handoff and mobilization brief must carry this capsule
when provider, phone, source-custody, dataset/model, logging, commit, or
external execution state can affect the next owner:

```yaml
provider_capability_capsule:
  matrix_artifact: "<provider matrix path plus sha256 if known>"
  providers:
    runpod:
      role: "QAIRT/QNN SDK source/tool host for outside-git export/build metadata"
      safe_check: "<metadata-only SSH check, no secrets>"
      owners: ["phase_engineering", "execution_orchestrator", "research_signal"]
      current_classification: "PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES"
    phone_adb_termux:
      role: "RedMagic 10 Pro authority execution target for model/training gates"
      safe_check: "<ADB/Termux metadata-only check scoped to authorized recovery>"
      owners: ["execution_orchestrator", "phase_engineering"]
      current_classification: "PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES"
    hugging_face:
      role: "corpus/model revision source and metadata-only provenance"
      safe_check: "hf auth whoami after approved env sourcing"
      owners: ["training_material_steward", "execution_orchestrator", "repo_custodian"]
      current_classification: "PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES"
    github:
      role: "custody commits/PRs only through Repo Custodian"
      safe_check: "gh auth status with token redaction"
      owners: ["repo_custodian"]
      current_classification: "PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES"
    comet:
      role: "authority-linked numeric metrics/logging, never dashboard-as-evidence"
      safe_check: "SDK init/auth check without printing API key"
      owners: ["execution_orchestrator", "pipeline_integrator", "ui_operator_visibility"]
      current_classification: "PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES"
  false_stop_prevention:
    - "Do not mark user_action_required merely because host/phone-local scans missed an artifact; check provider matrix first."
    - "Do not route source-custody to the user until all authorized provider surfaces for that artifact class have been checked or have exact auth failure evidence."
    - "Do not call provider absence a BLOCKER unless an authorized safe check failed or the required access surface is genuinely missing."
  secret_policy: "Never print, copy, summarize, commit, or include token/key values."
```

RunPod and phone are distinct operational surfaces. RunPod is a QAIRT/QNN SDK
source/tool host for outside-git export/build metadata. The RedMagic phone is
the authority execution target for model/training gates. A lane that merges
these roles, forgets either surface, or asks the user before checking the
matrix is in process drift.

### 7.3 Hugging Face

Allowed setup description:

- Preferred CLI: `hf`.
- Acceptable Python package: `huggingface_hub`.
- Credential sources: standard HF cache, `HF_TOKEN`, or authorized platform
  secret manager.
- Metadata checks: `hf auth whoami` or equivalent Python whoami call.
- Report only username/org status and permission class if safe.
- Do not print token paths containing secret content.
- Do not commit downloaded model weights, adapters, safetensors, raw datasets,
  or payload files unless a governing PRD explicitly permits a small metadata
  manifest.

### 7.4 GitHub

Allowed setup description:

- Preferred CLI: `gh`.
- Check status with `gh auth status`.
- Report only authenticated account, hostname, and permission surface if safe.
- Do not print OAuth tokens.
- Do not stage, commit, or push unless the lane has explicit custody authority.
- Repo Custodian owns promoted git truth.

### 7.4 OpenRouter

Allowed setup description:

- Use `OPENROUTER_API_KEY` or authorized secret manager only.
- Keep model routing in non-secret config.
- Log model name, request purpose, latency, and high-level status.
- Do not log prompts that contain secrets, raw payloads, or private data.
- If OpenRouter is used for research, record sources and claims separately;
  model output alone is not evidence.

### 7.5 Comet and Experiment Tracking

Allowed setup description:

- Use `COMET_API_KEY` or an authorized secret manager.
- Metrics must be numeric, named, and linked to an authority gate.
- Do not invent metrics to satisfy a dashboard.
- Absence of Comet is not a C5 pass blocker unless the current acceptance gate
  requires Comet-backed evidence.

### 7.6 Codex Threads and Agents

Allowed setup description:

- Thread IDs may be recorded.
- Raw conversation payloads should not be copied into git.
- Handoffs must summarize evidence, artifacts, next action, nonclaims, and
  forbidden actions.
- A lane that waits for heartbeat when it owns the next handoff is defective.

## 8. Role Taxonomy

### 8.1 Objective Governor

Formerly Meta-Orchestrator. Owns decomposition, role startup, authority metric
protection, lane routing, and final synthesis. Cannot declare success without
acceptance evidence.

### 8.2 Watchdog / Heartbeat Auditor

Monitors lane freshness, handoff presence, stale blockers, first-missing-field
narrowing, research escalation triggers, nonclaims, and current owner. It
nudges lanes but does not replace their obligation to send outbound handoffs.

The Watchdog is action-oriented. When a recoverable control-plane failure
appears, such as SSH drop, Termux command-channel loss, ADB detachment, stale
runner access, or provider auth surface disappearance, it must do more than
report. Within its authority it must run the bounded recovery playbook, record
what it tried, and either restore the channel or route the exact recovery
packet to the owner.

If it lacks authority to attempt recovery, it must say so as
`PENDING_ACTION_RECOVERY_NOT_AUTHORIZED` with the exact next owner and recovery
command class. A monitor that only reports a recoverable access failure for
multiple ticks is defective.

### 8.3 Living PRD Steward

Maintains the granular PRD. In small runs this is the Objective Governor. In
strict runs it is a separate lane.

### 8.4 Domain Implementation Lane

Formerly Phase Engineer. Builds the smallest real source path that advances
the first missing green field. Does not claim acceptance.

### 8.5 Runtime Executor

Formerly Execution Orchestrator. Runs the authority commands or gates after
custody and emits metadata-only evidence. Does not modify source.

### 8.6 Custody & Provenance Lane

Formerly Repo Custodian. Owns git truth, pathset verification, forbidden
payload scans, dependency hygiene, branch hygiene, and provenance.

### 8.7 Interface & Acceptance Integrator

Formerly Pipeline Integrator. Owns interface contracts, report schemas, metric
flow, cross-lane compatibility, and acceptance-path readiness.

### 8.8 Operator Visibility Lane

Formerly UI Engineer. Builds status surfaces from evidence only. It must not
invent optimistic states or decorate uncertainty.

### 8.9 Domain Steward Lanes

Formerly Corpus Engineer and Training Material Steward in the Polymath
training pipeline. In general ZPP these are configurable utility lanes:

- Source Steward.
- Materials Steward.
- Benchmark Steward.
- Literature Steward.
- Data Steward.
- Hardware Steward.
- Safety Steward.

### 8.10 Hounds of Popper Lane

Adversarial falsification lane. Its job is to attack claims, expose proxy
substitution, test nonclaims, and reject weak evidence.

### 8.11 Research Sentinel

Dormant until the research escalation trigger fires, or active during the
initial research-think-plan-innovate loop.

## 9. State Machine

ZPP runs move through:

1. `OBJECTIVE_CONTRACT_DRAFT`
2. `INNOVATION_PRIMER_REQUIRED`
3. `LIVING_PRD_DRAFT`
4. `LANE_DECOMPOSITION`
5. `EXECUTION_READY`
6. `ACTIVE_EDGE`
7. `CUSTODY_PENDING`
8. `AUTHORITY_EXECUTION_PENDING`
9. `EVIDENCE_RETURNED`
10. `NARROWING_DECISION`
11. `RESEARCH_ESCALATION_REQUIRED` or `NEXT_EDGE`
12. `ACCEPTANCE_GATE_PENDING`
13. `ACCEPTED`, `FALSIFIED`, or `BLOCKED_WITH_EVIDENCE`

No state may advance on narrative alone.

## 10. Required Artifacts

### 10.1 OBJECTIVE_CONTRACT

```yaml
objective_contract:
  objective: string
  authority_metric: string
  acceptance_gate: string
  non_negotiables: string[]
  regression_policy: any_authority_metric_regression_fails
  evidence_required: string[]
  stop_conditions: string[]
```

### 10.2 NEXT_HANDOFF

```yaml
NEXT_HANDOFF:
  to: "<lane name and thread id>"
  status: "<exact status>"
  reasoning_level: "xhigh | xhigh_unavailable_with_reason:<reason>"
  artifacts:
    - "<path plus sha256, or none with reason>"
  authority_metric: "<metric this handoff advances>"
  first_missing_green_field: "<single field>"
  next_action: "<one concrete action>"
  prompt_to_send: "<copy-paste prompt for next lane>"
  context_load:
    tier: "capsule_only | targeted_reference | full_prd | full_evidence"
    files_loaded:
      - "<path or reference name>"
    extraction_mode: "targeted | full"
    rationale: "<why this much context was necessary>"
    omitted_heavy_sources:
      - "<heavy source intentionally not loaded>"
  provider_access_state: "PENDING_ACTION_PROVIDER_NOT_NEEDED_FOR_CURRENT_EDGE | PENDING_ACTION_PROVIDER_AVAILABLE_WHEN_EDGE_REQUIRES | PENDING_ACTION_PROVIDER_AUTH_SURFACE_MISSING | BLOCKER_PROVIDER_AUTH_FAILED"
  provider_capability_capsule:
    matrix_artifact: "<provider matrix path plus sha256 when provider/source/logging/custody state can affect route>"
    providers:
      runpod:
        role: "QAIRT/QNN SDK source/tool host for outside-git export/build metadata"
        safe_check: "<metadata-only SSH check, no secrets>"
        current_classification: "<provider state>"
      phone_adb_termux:
        role: "RedMagic 10 Pro authority execution target for model/training gates"
        safe_check: "<ADB/Termux metadata-only check scoped to authorized recovery>"
        current_classification: "<provider state>"
      hugging_face:
        role: "corpus/model revision source and metadata-only provenance"
        safe_check: "<metadata-only auth/revision check>"
        current_classification: "<provider state>"
      github:
        role: "Repo Custodian-owned freeze/PR surface"
        safe_check: "<token-redacted auth/remote check>"
        current_classification: "<provider state>"
      comet:
        role: "authority-linked numeric metrics/logging, never dashboard-as-evidence"
        safe_check: "<metadata-only SDK/auth check>"
        current_classification: "<provider state>"
    false_stop_prevention: string[]
    secret_policy: "Never print, copy, summarize, commit, or include token/key values."
  raw_boundary_state: "<metadata-only proof or exact blocker>"
  drift_action: "none | ignore_historical | delete_candidate | deletion_done_with_commit"
  research_escalation: "<none | active_parallel_signal_lane | required with reason>"
  nonclaims: string[]
```

Default ambiguous-owner route:

- to: Engineering/Meta watcher `019f1423-816d-7251-b7d9-945a11441c3f`
- status: `<lane>_next_owner_ambiguous`
- required evidence: exact ambiguity, candidate owners, and first missing green
  field.

This is not a `BLOCKER` unless there is a verified failure, missing access, or
external/user action required.

### 10.3 FALSIFICATION_MATRIX

```yaml
falsification_matrix:
  claims:
    - claim: string
      evidence_for: string[]
      attacks: string[]
      result: survives | fails | unresolved
      authority_metric_relevance: string
```

### 10.4 EVIDENCE_LEDGER

The evidence ledger records commands, artifacts, hashes, reports, metrics,
owners, timestamps, failed attempts, and nonclaims. It separates evidence from
narrative.

### 10.5 RECOVERY_ATTEMPT_PACKET

Recoverable control-plane failures require action, not only observation.

```yaml
recovery_attempt_packet:
  schema_version: zpp_recovery_attempt_v1
  failure_surface: ssh | adb | termux | provider_auth | runner_access | other
  observed_failure: string
  authority_to_recover: true | false
  attempted_actions: string[]
  restored: true | false
  evidence:
    - artifact: string
      sha256: string | null
      status: string
  fallback_channel_checked: string[]
  next_owner: string
  next_action: string
  blocker_allowed: true | false
  nonclaims: string[]
```

If `authority_to_recover` is true and `attempted_actions` is empty, the monitor
failed its job. If `authority_to_recover` is false, `next_owner` and
`next_action` are mandatory.

## 11. Handoff Integrity Rules

1. A lane is not complete until it emits `NEXT_HANDOFF`.
2. If thread-send tooling is available, a lane must send the handoff to the
   next lane directly before marking itself complete.
3. A completed marker, route-green verdict, or final answer without outbound
   dispatch is process failure.
4. A handoff without evidence is not a handoff; it is a message.
5. A handoff must name the next owner and next action.
6. A lane waiting for heartbeat when it owns the handoff is defective.
7. Heartbeat may repair routing visibility, but it must not normalize passive
   completion as acceptable.
8. Every user/process return in this lane must include the ZPP handoff fields:
   `to`, `status`, `reasoning_level`, `artifacts`, `authority_metric`,
   `first_missing_green_field`, `next_action`, `prompt_to_send`,
   `handoff_dispatch_status`, `context_load`, `provider_access_state`,
   `provider_capability_capsule` when provider/source/logging/custody state can
   affect the route, `raw_boundary_state`, `drift_action`,
   `research_escalation`, and `nonclaims`.
9. Handoffs that loaded full heavy context must justify why targeted extracts
   were insufficient.
10. Every mobilization brief must embed the incoming `NEXT_HANDOFF`, or a
    clearly marked `WATCHDOG_RECOVERY_HANDOFF` for route repair, and the
    outbound `NEXT_HANDOFF` schema the lane must return.
11. `handoff_dispatch_status` must be `SENT_TO_NEXT_OWNER` when a lane sent the
    handoff itself, or `TOOL_UNAVAILABLE` when Watchdog must dispatch the
    carried prompt. `TOOL_UNAVAILABLE` is a control-plane repair condition, not
    a user blocker.
12. `user_action_required: true` is invalid for provider/source-custody gaps
    until the handoff records the relevant provider matrix entry and exact safe
    check result, or explains why no provider surface owns the artifact class.
13. RunPod and phone roles must stay distinct: RunPod is the QAIRT/QNN SDK
    source/tool host for outside-git export/build metadata; the RedMagic phone
    is the authority execution target for model/training gates.
14. Hugging Face, GitHub, and Comet must be classified as available, needed,
    not needed, or exact failed auth for the current edge; lanes may not forget
    Comet metric logging when an authority gate requires numeric metrics.

### 11.1 Workstream Routing Matrices

Routing matrices are active only when the current living PRD names them as the
active route surface. Under the Apex Heterogeneous Cell PRD, stale WaveC and
C5 proxy route tables are historical unless a new apex `NEXT_HANDOFF`
explicitly re-promotes one as a blocker-repair subroute.

Historical WaveC lane handoff matrix:

| Lane | Thread | Default Next Handoff |
| --- | --- | --- |
| Engineering/Meta watcher | `019f1423-816d-7251-b7d9-945a11441c3f` | Pipeline for receiving validation, Repo Custodian if Pipeline already validated, or Execution if custody is frozen |
| Phase3/4 Engineer replacement | `019f2059-e6a8-73b1-a9b8-8a2c499e838e` | Pipeline for route/contract validation; Repo Custodian if Pipeline already green; Engineering/Meta if technical decision needed |
| Pipeline Integrator | `019f138c-35b6-73e1-b26d-3db8c59cf850` | Repo Custodian on green pathset; Engineering/Meta on gap |
| Repo Custodian replacement | `019f2059-ef2c-7762-ba42-963b58f3af90` | Engineering/Meta with commit/gap; Execution only with accepted GO package fields |
| Execution Orchestrator | `019f138c-fb51-7c53-a41a-ab8eac950d9c` | Pipeline for run evidence validation; Engineering/Meta for execution blocker/architecture decision; Repo Custodian for metadata freeze only when instructed |
| Research Signal Agent | `019f229a-a514-7443-b7ed-91972233ac93` | Engineering/Meta and affected implementation lane |
| Training Material Steward | `019f138b-7bfc-7671-b9fc-22c14ab76342` | Pipeline on accepted material; Engineering/Meta on ambiguity; Execution only after Pipeline and Custody |
| UI Engineer | `019f138c-8d85-7141-a813-66db51c62b3d` | Pipeline for integration validation; Repo Custodian for frozen UI/report pathset; Engineering/Meta if visibility objective is ambiguous |
| MetaOrchestrator #3 standby | `019f1d69-aa89-74c1-b9c5-004119e4ff1e` | Engineering/Meta only; no direct execution while passive |

## 12. BLOCKER Semantics

Use `BLOCKER` only for true failed access, verification, or technical failure.

Use `PENDING_ACTION` for work that is known and owned under current authority.

Examples:

- `PENDING_ACTION_REPO_CUSTODY_FREEZE`: valid if custody has not yet run.
- `PENDING_ACTION_EXECUTION_RUN_PHONE_PROBE`: valid if execution has a command.
- `BLOCKER_TERMUX_COMMAND_CHANNEL_UNAVAILABLE`: valid only if command access
  was attempted, bounded recovery was attempted or explicitly unauthorized,
  and the recovery packet names the next owner.
- `BLOCKER_PROVIDER_AUTH_FAILED`: valid only if an authenticated operation was
  attempted and failed.

## 13. Process-Theater Falsifiers

The Hounds of Popper lane must check:

- Is a proxy metric being promoted?
- Is a local pass substituting for authority?
- Is research being used to delay implementation?
- Is implementation continuing when research is genuinely required?
- Is a completed marker missing an outbound handoff?
- Is an isolated probe or island being promoted after boundary crossing
  without `apex_field_repaired`, `falsifier`, `attempt_budget`, and
  `return_handoff_to_apex`?
- Did a route-changing mobilization omit `xhigh` reasoning or an explicit
  `xhigh_unavailable_with_reason`?
- Did a lane load full PRDs, central state, external packets, or stale route
  tables without a `context_load` rationale?
- Is the same missing field repeating without narrowing?
- Did the PRD change after evidence in a way that narrows the objective?
- Did provider access failure become a vague blocker without evidence?
- Did UI/status work imply progress not present in artifacts?
- Did the system choose familiar enterprise convention over the maximal design?

## 14. Packaging Decision

ZPP should be built in layers:

1. Protocol PRD and schemas.
2. Local harness and validators.
3. Codex skill.
4. Plugin packaging.
5. MCP or daemon coordination when live state requires it.

The skill teaches agents how to run ZPP. The harness verifies that they did.
The plugin packages both. The MCP layer coordinates live state if needed.

## 15. Initial Execution Plan

### Phase A: Authority Wedge

Deliver:

- This PRD.
- A linter that checks orchestration state for required fields, missing
  handoffs, weak blockers, stale mirrors, and incomplete research escalation.
- Tests proving the linter catches the target process failures.

Acceptance:

- The linter runs locally without network, phone, API, or secret access.
- Tests pass.
- The current Polymath state can be inspected without modifying central state.
- Default heartbeat lint is active-edge only. Historical warning debt is
  opt-in via `--include-historical` and must not block forward motion.

### Phase B: ZPP Skill

Deliver:

- `SKILL.md` for `$zpp-orchestrate`.
- References for role taxonomy, handoff schema, provider access, research loop,
  Popper falsification, and PRD amendment rules.
- Scripts reused from Phase A.

Acceptance:

- A new agent can invoke the skill and produce an objective contract, primer,
  lane briefs, and handoff packet without conversation history.

Initial local status, 2026-07-01: `$zpp-orchestrate` has been installed under
the local Codex skills directory with focused references for research loop,
living PRD, handoff, and provider access. It is not yet packaged as a plugin.

### Phase C: ZPP Plugin

Deliver:

- Plugin manifest.
- Skill bundle.
- Validator scripts.
- Templates.
- Optional status widgets.

Acceptance:

- The plugin can be installed and invoked on another Zer0pa workstream.

### Phase D: Durable Coordination

Deliver:

- MCP or daemon state service for run registry, leases, heartbeat checks,
  state diffing, and handoff dispatch.
- Event log with replay/fork support.

Acceptance:

- A run can recover after thread loss or tool interruption without losing the
  current edge.

### Phase E: Cross-Workstream Adoption

Deliver:

- Apply ZPP to Polymath and one non-training Zer0pa workstream.
- Compare drift, handoff failures, time-to-owner, and authority-gate clarity.

Acceptance:

- ZPP catches at least one real process defect that would otherwise stall or
  misroute a workstream.

## 16. Acceptance Criteria For This PRD

This PRD is acceptable only if it:

- Preserves maximalism as enforceable protocol.
- Adds the initial research-think-plan-innovate loop.
- Adds living PRD stewardship.
- Documents provider access without secrets.
- Defines handoff integrity as a hard gate.
- Defines research escalation as bounded and falsifiable.
- Produces an executable validator path.
- Does not claim that ZPP is complete.

## 17. Nonclaims

- ZPP is not complete.
- No plugin has been packaged yet.
- A local Codex skill exists, but it is not yet plugin-packaged or
  cross-workstream validated.
- No MCP service has been built yet.
- No phone gate was run for this PRD.
- No Hugging Face, GitHub, Comet, or OpenRouter API call is authorized by this
  PRD alone.
- No current Polymath C5 pass is claimed.
- No learning, model quality, or Phase3/4 readiness claim is made.
- ZPP lint warning debt from historical embedded state is not an authority
  blocker unless it affects the current active edge.

## 18. Immediate Next Handoff

```yaml
next_handoff:
  schema_version: zpp_next_handoff_v1
  from_lane: "ZPP Protocol/Process Agent"
  to_lane: "Meta-Orchestrator / Living PRD Steward"
  sent: false
  current_edge: "ZPP Phase A authority wedge"
  current_verdict: "pending_action"
  completed_work:
    - "Living ZPP PRD drafted."
    - "Initial local linter implemented and tested."
    - "Local $zpp-orchestrate skill installed and validated."
  first_missing_green_field: "zpp_plugin_packaging_missing"
  next_action: "Review Phase A/B artifacts, then authorize plugin packaging or MCP coordination."
  research_escalation:
    status: "none"
    reason: "Current next step is implementation and validation, not broad research."
    packet_path: null
  nonclaims:
    - "No ZPP plugin shipped yet."
    - "No provider access performed."
```
