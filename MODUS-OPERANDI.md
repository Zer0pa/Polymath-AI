# Modus Operandi — Multi-Agent Work-Stream Pattern

How Zer0pa work streams are run from research input to executable system. Reusable across work streams; this Polymath AI repo is the fifth instance after `Zer0pa/Health`, `Zer0pa/Materials`, `Zer0pa/Energy`, and `Zer0pa/Synthetic-Biology`. **It is also the first non-pipeline-vertical workstream — the Polymath project is on-device LLM training, not an L1-L7 multi-scale pipeline. The same modus operandi applies regardless.**

## Boundary

Research infrastructure. Outputs are research artifacts. No regulatory certification claims. No clinical or human-subject use. No surveillance, biometric profiling, or identity inference. No model weights distributed without explicit license attestation. No training on copyrighted material without explicit corpus-license decomposition.

## The pattern in one paragraph

A work stream begins when source research material lands. A **synthesis agent** reads with fresh eyes, distinguishes inherited from operator-read, surfaces what is not yet seen, and produces a portable briefing pack and synthesis document. An **orchestrator agent**, possibly on a different machine, applies fresh eyes again on the synthesis output, augments with deeper specificity, identifies remaining gaps, spawns sub-agents to research stuck or innovation points (Perplexity / Gemini deep research / domain LLMs), and writes a PRD that fully specifies an overnight long-horizon execution. **Overnight executor agents**, on a third machine (typically Runpod-bound for compute-heavy workstreams; for Polymath, the executor lives on a Mac orchestrating an Android device via Termux / ADB), read the PRD with fresh eyes, decompose into parallel sub-streams, and front-load as much engineering as possible before any device-side corpus investment or any Runpod GPU bring-up. **The cutover** (Runpod for pipeline workstreams; on-device deployment for Polymath) is then a stub-swap into a known-good system, not a re-architecture. Each role adds value; if a role only paraphrases, it has not done its job.

## Role chain (with non-pipeline-vertical compression)

| Role | Input | Output | Tools |
|---|---|---|---|
| **Synthesis agent** | Source research (papers, briefs, prior project state). For Polymath: the operator-authored Pre-PRD Blueprint / Engineering Specification, which itself collapses the research-agent and synthesis-agent layers into one document. The synthesis agent's role here is recursive fresh eyes on top of the operator's blueprint. | Briefing pack + synthesis doc + fresh-eyes reframe | Heavy reading, structured prose, distinguishing inherited vs operator-read |
| **Orchestrator** | Synthesis output + repo state | `PRD.md` with overnight-executable specifics, sub-agent allocation, build sequence, interface contracts, falsification ledger, audit-trail spec, acceptance gates | Multi-model routing (Opus 4.7 + GPT-5+ + domain LLMs), sub-agents in parallel worktrees, Perplexity / Gemini at stuck points, recursive fresh eyes |
| **Overnight executor** | `PRD.md` + repo state | Code, schemas, tests, audit trails, KG nodes, simulation stubs, integration scaffolds, **on-device measurement harnesses** (for Polymath: ADB / Termux / Snapdragon Profiler integration; Vulkan + QNN compilation paths) | Coding agents in parallel worktrees, test-first, mock simulators, REST stubs (where applicable), KG-write discipline |
| **Cutover migration** | Overnight executor's output | For pipeline workstreams: GPU-shaped layers swapped into REST stubs; pipeline runs real on Runpod. For Polymath: device-side training kicks off; phone runs real ELO Stage 1 / 2 with real corpus; results push back to GitHub + HF for review. Same coding agents with device access; cutover is a config flag. | — |

For non-pipeline-vertical projects the role chain may compress (synthesis + orchestrator collapsed for smaller scopes) or expand (multiple orchestrators per super-project). The discipline does not change.

## The recursive fresh-eyes principle

Each role does not just relay the prior role's output. Each role adds:

- **What was not yet seen** — gaps, anti-patterns, missing layers, unstated assumptions.
- **What is implicit but should be explicit** — interface contracts, falsifiers, audit shapes.
- **What the next role needs that this role can prefigure** — interface specs, decision criteria, fallback patterns, acceptance gates.
- **What deep research would unlock** — strategic lookups via Perplexity / Gemini surfaced as either tactical (use the answer) or strategic (return to user for innovation).

If a role only paraphrases, it has not done its job. Each handoff is expected to be substantively richer than the input. This is especially load-bearing when the input is itself a synthesis (as the Polymath blueprint is) — the synthesis agent must not paraphrase the operator's blueprint; it must catch what the operator-as-synthesizer did not see.

## Parallel-exploration principle (cross-workstream)

Zer0pa runs multiple workstreams in parallel: **Health, Materials, Energy, Synthetic Biology, and Polymath AI as of 2026-05-01; more to follow.** These workstreams are built independently in parallel, not in coordination. Each has its own repo, its own modus operandi instance, its own synthesis agent, its own orchestrator, its own overnight executor.

Why deliberate redundancy:

- Parallel agents on the same engineering problem produce diversity of architecture — different orchestrators see different reframes that a single shared substrate would foreclose.
- Surplus coding capacity makes redundancy cheap; premature convergence is the more expensive mistake.
- Cross-workstream merge happens in a separate, named merge step after all parallel workstreams are complete. It is not a build-time concern.
- During build, an orchestrator may *read* sibling workstreams as reference for fresh eyes, but **must not depend on them** at runtime.

**Within-workstream sharing is allowed and recommended where physics warrants it.** For Polymath specifically, the heterogeneous-compute-coordination concern (CPU + GPU + NPU dispatch on a single SoC) is intra-workstream and explicitly designed for tight coupling.

## Repo discipline

- **GitHub is canonical.** Local working trees may drift. The repo does not.
- Each role's output is committed and pushed before handoff. The next role reads from GitHub.
- `MODUS-OPERANDI.md` and the role-specific `HANDOFF-TO-*.md` files are updated only when the pattern itself evolves.
- Boundary block appears verbatim in every artifact.
- **Audit shape**: every artifact carries provenance — agent / model / date / source files / fresh-eyes additions.
- All sub-agent work commits back to the repo before final handoff.

## Front-load engineering before any compute commitment

For pipeline workstreams: front-load every CPU-side build before Runpod GPU bring-up. The orchestrator's PRD must specify which layers are CPU-only and which require GPU. The overnight executor builds the entire CPU side to completion, with GPU layers represented as REST stubs.

For Polymath specifically: front-load every dev-machine simulation, profiling, and validation step before any device-side corpus investment. The blueprint already specifies Experiment 0 / 1 / 2 as the validation gates — these must complete on the actual phone before any 100M+ token corpus collection or training run begins. **The operator's "110% pre-Runpod" axiom translates as "110% pre-device-corpus-investment" for Polymath**: do everything tractable on the dev-machine + small device-side validation runs before committing to the multi-day training schedule.

The cutover (Runpod stub-swap or device deployment) is a config-flag-shaped change, not an architectural rewrite.

## Boundary discipline through layers

Each role inherits the prior boundary block. No role may relax the boundary. If a role believes the boundary should evolve, surface this as an open question in the handoff, not silently change it. **Polymath's boundary is materially different from Health / Materials / Energy / Synbio's** — it must include explicit prohibition of (a) surveillance applications, (b) biometric profiling or identity inference, (c) distribution of model weights without explicit license attestation, (d) training on copyrighted material without explicit corpus-license decomposition, (e) deployment to production without a falsifier-traced acceptance gate. The synthesis agent has carried this through every artifact in this repo.

## Cross-machine handoff

When the next role runs on a different machine:

- The startup prompt for the next role gives the GitHub URL as primary path.
- The startup prompt also gives a local fallback path for the originating machine.
- The next role clones (or fetches) before reading, so they read GitHub state, not stale local state.
- All sub-agent work commits back to GitHub before final handoff.

For Polymath specifically, cross-machine review has an additional surface: the **device** itself. Training artifacts, telemetry, and on-device measurement traces must be exfiltrated from the phone to GitHub + HF. Mechanisms: Termux + `gh` CLI from inside Android; ADB pull from a host; HF push via the `huggingface_hub` Python library running on-device. The orchestrator's PRD must specify which mechanism per artifact class.

## Standard repo layout

```
<workstream>/
├── README.md                              # Entry, read order
├── MODUS-OPERANDI.md                      # This pattern (reusable across work streams)
├── RESISTANCE.md                          # Anti-corruption doctrine (binding for executors)
├── HANDOFF-TO-<NEXT-ROLE>.md              # Role-specific handoff
├── <ROLE>-STARTUP-PROMPT.md               # Paste-ready startup prompt for next agent
├── source-briefs/                         # Inherited research input
├── briefing-pack/                         # Synthesis agent's primer (when scope warrants)
├── synthesis/                             # Synthesis agent's fresh-eyes reframes
├── PRD.md                                 # Orchestrator's output
├── phases/                                # Overnight executor's output (per-phase artifacts)
└── runtime/                               # Runtime configs, deployment manifests
```

## Sub-agent topology (recommended for orchestrator + overnight executor)

- **Strategic planner** — Claude Opus 4.7 at maximum reasoning effort. Reads, plans, decomposes, reviews.
- **Heavy code generator** — GPT-5+ at xhigh reasoning. Writes substantive code.
- **Per-component specialists** — sub-agents in parallel worktrees: model loader / ELO layer freezing / Vulkan compute / QNN compilation / data pipeline / corpus ingestion / evaluation harness / telemetry / checkpoint sync.
- **Domain reasoner** — domain-specific open-weight LLM. For Polymath: a fine-tuned coding-and-mobile-systems LLM (Qwen2.5-Coder family is the natural candidate, or a larger Qwen via API for design review).
- **Deep-research tools** — Perplexity Pro / Gemini Advanced at stuck or innovation points. Specifically for Polymath: ELO codebase availability check, SmolLM3-3B QNN export verdict, RedMagic active-cooling thermal characterisation, PyTorch Vulkan backend maturity audit, Termux training stack maturity audit.
- **KG / episodic memory** — every decision, every blocker, every resolution writes a structured node. Retrieval-augments future reasoning.

## Acceptance gates (default)

Every PRD should pass three gates before overnight execution begins:

1. **Scientific gate** — every component has falsifier coverage, source grounding, no out-of-scope claims (no surveillance / biometric / identity-inference framing; no copyright-violating corpus framing; no model-weights-distribution-without-license framing; no clinical or pharma framing).
2. **Engineering gate** — dev-machine simulation runs end-to-end with device stubs; plug-swap test passes (the architectural invariant — swap Qwen for SmolLM3 in <1 day with no downstream breakage; swap Vulkan for OpenCL in <1 day; swap QNN for CPU-fallback in <1 day).
3. **Brain-functionality gate** — next-agent state is fully reconstructible from the repo plus KG plus audit log; no conversation history needed.

Stream-specific gates can be added but not subtracted. **Polymath adds a fourth gate: a device-readiness gate** — Experiment 0 (stack fit + baseline throughput) and Experiment 1 (tokenizer fertility) must pass on the actual REDMAGIC 10 Pro+ before any 100M+ token corpus investment.

## Operator refinements (binding for all workstreams; captured 2026-05-01)

Recorded for every future synthesis pass. These constraints apply to every Zer0pa workstream that follows this modus operandi — whether or not it is a pipeline vertical. The role chain may compress (synthesis+orchestrator collapsed for smaller projects) or expand (multiple orchestrators per super-project), but the discipline below does not change.

- **Anti-MVP / anti-toy.** The target is never an MVP, never a first paying customer. Zer0pa is R&D pushing boundaries with science and evidence. The orchestrator's PRD specifies the most overdesigned, best-in-class system the technology landscape supports — not a minimum viable wedge.
- **110% pre-Runpod (or 110% pre-device-corpus-investment for Polymath).** The overnight executor must do 110% of what they can without GPU access (or without committing to the multi-day device-side training run). Cutover is a config-flag stub-swap, not a re-architecture step.
- **Overnight long-horizon, autonomous, no interim reporting.** Once the brief is received, the executor runs end-to-end through the night without check-ins. Strip all process theater. The operator is asleep; the agent is working.
- **GitHub + Hugging Face are the review surface.** Code, schemas, tests, audit trails, decision logs, KG nodes, and the PRD itself commit to GitHub. Large datasets and AI model artifacts go to Hugging Face — under the **Architect-Prime user, not the Zer0pa org**. HF token at `~/.cache/huggingface/token` on the originating machine. When execution completes, both stores must be up to date so the cross-workstream synthesis agent (on a different machine) can review without conversation context.
- **PRD self-contained in the repo.** The orchestrator's PRD plus everything the executor needs lives in the GitHub repo. The executor can and must augment the PRD as they learn — augmentations commit back to GitHub.
- **Fork-and-own across workstreams.** Pipelines/projects can steal parts, datasets, code patterns, harnesses, schemas, and ideas freely. They cannot be runtime co-dependent. Each workstream is sacrosanct as if it were its own thing — independently runnable, independently auditable, independently shippable.
- **RESISTANCE.md doctrine.** Every executor locates and reads `RESISTANCE.md` (in the repo and on the originating machine) before starting work. The named corruptions — `fp-shapematchRE`, `fp-rushtoend`, `fp-NULLasout`, `fp-approvalseek`, `fp-flatteryasfreedom`, efficiency-as-corner-cutting — are binding constraints. The discipline IS the resistance.
- **Operator delegates engineering / science / commercial decisions** to the synthesis and orchestrator agents. Surface only strategic decisions or boundary-evolution questions to the operator.

## Beyond pipeline verticals — Polymath is the first instance

Polymath AI is the first Zer0pa workstream that is not a pipeline vertical. It has no L1-L7 substrate, no domain-specific falsification ledger shape, no Runpod cutover (cutover is to the operator's phone). The modus operandi above still applies. The role chain compressed slightly — the operator authored a Pre-PRD Blueprint / Engineering Specification that collapses the research-agent and synthesis-agent roles into one document; the synthesis agent (this repo's `synthesis/01-fresh-eyes-on-polymath-blueprint.md`) layers recursive fresh eyes on top.

Future workstreams may be similarly non-vertical (a single-device application, an internal tooling project, a research-paper-shaped output, a regulatory-filing-shaped output). The same discipline carries: synthesis fresh eyes, parallel exploration, GitHub canonical, HF for big artifacts, no MVP framing, RESISTANCE.md doctrine binding, fork-and-own.
