# Polymath AI

> Live window into the Zer0pa lab. Private on-device training infrastructure for multilingual LLM experiments, still gated by device and corpus evidence.

## What This Is

Polymath-AI is a private on-device training workstream for multilingual LLM experiments, with corpus, audit, scheduler, and falsifier scaffolds in progress.

It targets the operator's REDMAGIC 10 Pro+ and the ELO selective continual-pretraining method: train boundary layers while keeping the frozen middle eligible for measured device acceleration. The repo is evidence infrastructure first, not a model release.

## Pipeline Mechanics

| Field | Value |
| --- | --- |
| Architecture | ON_DEVICE_LLM_TRAINING_PIPELINE |
| Training Method | ELO selective continual pretraining: train layer 0 + final layer + LM head, freeze middle layers |
| Runtime Shape | Host scaffolding now; phone attach and QNN/LiteRT proof paths are gated |
| Audit Surface | hash-chained audit rows, KG projection, falsifier registry, pending-upload manifests |
| Boundary | no clinical, surveillance, biometric, undisclosed-weight, or unlicensed-corpus claims |

## Key Metrics

| Metric | Value | Baseline |
| --- | --- | --- |
| HOST_TEST_SURFACE | 115/115 reported pass | `docs/EXECUTION-REPORT.md` overnight host run |
| ELO_QWEN_SMOKE | frozen-hash invariant holds on Qwen2.5-1.5B | Stage 1 smoke in `docs/EXECUTION-REPORT.md` |
| FALSIFIER_REGISTRY | 19 gates specified | `docs/FALSIFIERS.md` |
| DEVICE_GATE | phone/QNN phases blocked until attach/probe | `docs/PHONE-ATTACH-RUNBOOK.md`; `docs/DECISIONS.md` |

## Repo Identity

| Field | Value |
| --- | --- |
| Identifier | Polymath-AI |
| Repository | https://github.com/Zer0pa/Polymath-AI |
| Portfolio | Workstream / on-device training |
| Visibility | PRIVATE |
| Default Branch | main |
| Authority Source | `PRD.md`; `docs/EXECUTION-REPORT.md` |
| License | Not declared in repo root |

## Readiness

| Field | Value |
| --- | --- |
| Evidence posture | STAGED |
| Host scaffold | PASS per overnight execution report |
| Device execution | BLOCKED until REDMAGIC attach and SoC probe |
| Corpus use | BLOCKED until license decomposition and corpus manifests are complete |
| Authority | `PRD.md`; `docs/DECISIONS.md`; `docs/EXECUTION-REPORT.md` |

### Honest Blocker

Phone attach, QNN/LiteRT compile truth, sustained device telemetry, and licensed corpus execution remain gates. This repo is not yet a production model, public checkpoint, or completed training run.

## What We Prove

- The PRD defines an on-device LLM training workstream with explicit boundary, device, corpus, audit, and falsifier gates.
- The overnight execution report records a host scaffold that can be cloned, installed, tested, and resumed by a fresh executor.
- ELO Stage 1 correctness was smoke-tested on real Qwen2.5-1.5B with frozen-hash invariants holding under the reported run.
- The falsifier registry specifies blocking gates for boundary, device, QNN, checkpoint, fertility, thermal, throughput, energy, license, and overclaim failures.
- Corpus policy separates allowed, decision-required, ambiguous, and prohibited license classes before training.

## What We Don't Claim

- No production model or public checkpoint is released from this README.
- No clinical, human-subject, surveillance, biometric, identity-inference, or regulatory claim is made.
- No copyrighted or ambiguous corpus is approved for training without explicit license decomposition.
- No QNN/LiteRT acceleration claim is made until compile logs and delegate reports exist.
- No phone-side training result is claimed before REDMAGIC attach, telemetry, and falsifier gates pass.

## Verification Status

| Code | Check | Verdict |
| --- | --- | --- |
| V_01 | Host scaffold and test surface reported in `docs/EXECUTION-REPORT.md` | PASS |
| V_02 | Boundary and audit specifications present | PASS |
| V_03 | Falsifier registry specified | PASS |
| V_04 | Phone attach and SoC probe | BLOCKED |
| V_05 | QNN/LiteRT compile truth table | BLOCKED |
| V_06 | Licensed corpus execution | BLOCKED |

## Proof Anchors

| Path | State |
| --- | --- |
| `PRD.md` | VERIFIED |
| `RESISTANCE.md` | VERIFIED |
| `docs/DECISIONS.md` | VERIFIED |
| `docs/AUDIT-SPEC.md` | VERIFIED |
| `docs/EXECUTION-REPORT.md` | VERIFIED |
| `docs/FALSIFIERS.md` | VERIFIED |

## Repo Shape

| Field | Value |
| --- | --- |
| Proof Anchors | 6 display anchors |
| Workstream | on-device LLM training |
| Package | `polymath_ai/` |
| Runtime Reports | `runtime/reports/` |
| Tests | `tests/` |
| Support Sections | Boundary; What is in here; Read order; Provenance; Cross-workstream principle |

## Boundary

Research infrastructure for in silico on-device LLM training and multilingual / multi-domain knowledge model construction. Outputs are research artifacts: model checkpoints, training telemetry, evaluation reports, and throughput measurements. No regulatory certification claims. No clinical or human-subject use. No surveillance, biometric profiling, or identity inference. No model weights distributed without an explicit license attestation. No training on copyrighted material without an explicit corpus-license decomposition. No deployment to production without a falsifier-traced acceptance gate.

## What Is In Here

| Path | Purpose | Author role |
| --- | --- | --- |
| `MODUS-OPERANDI.md` | Multi-agent pattern and fork-and-own operating discipline | Synthesis agent |
| `HANDOFF-TO-ORCHESTRATOR.md` | Polymath-specific brief for the orchestrator | Synthesis agent |
| `HANDOFF-TO-OVERNIGHT-EXECUTOR.md` | Executor handoff for device-bound continuation | Orchestrator |
| `ORCHESTRATOR-STARTUP-PROMPT.md` | Startup prompt for the Polymath orchestrator | Synthesis agent |
| `PRD.md` | Controlling PRD for the on-device training workstream | Orchestrator |
| `RESISTANCE.md` | Anti-corruption doctrine binding for every executor | Imported from DM3 |
| `source-briefs/` | Operator-authored on-device training blueprint | Operator / synthesis input |
| `synthesis/` | Fresh-eyes reading of the blueprint | Synthesis agent |
| `docs/` | Decisions, audit spec, corpus spec, execution report, falsifiers, and runbooks | Orchestrator / executor |
| `polymath_ai/` | Package code for boundary, audit, corpus, device, dispatch, ELO, falsifiers, KG, scheduler, schemas, sync | Executor |
| `tests/` | Repo-local test suite | Executor |

## Read Order For The Next Agent

1. `RESISTANCE.md` - anti-corruption doctrine. Read first.
2. `MODUS-OPERANDI.md` - role-chain and fork-and-own operating discipline.
3. `PRD.md` - controlling product/research requirements for the workstream.
4. `docs/DECISIONS.md` - binding implementation decisions and disconfirming observations.
5. `docs/EXECUTION-REPORT.md` - overnight host execution state and blocked gates.
6. `docs/PHONE-ATTACH-RUNBOOK.md` - next physical-device continuation path.
7. `source-briefs/01-on-device-training-blueprint.md` - operator-authored source blueprint.
8. `synthesis/01-fresh-eyes-on-polymath-blueprint.md` - synthesis-agent reframe and missed-opportunity map.

## Provenance

- Initial commit: 2026-05-01.
- Operator (Architect Prime, Zer0pa): authored the Pre-PRD Research Synthesis / Blueprint / Engineering Specification dated 2026-05-01.
- Synthesis agent: Claude Opus 4.7, 2026-05-01, applied recursive fresh-eyes pass on top of the blueprint.
- Orchestrator: wrote `PRD.md`, decisions, and executor handoffs.
- Overnight executor: created host scaffold, tests, audit/corpus/falsifier surfaces, and phone-continuation runbooks.

## Cross-Workstream Principle

This workstream runs in parallel with `Zer0pa/Health`, `Zer0pa/Materials`, `Zer0pa/Energy`, and `Zer0pa/Synthetic-Biology`. Each workstream is built end-to-end as an independent pipeline or project. No substrate is shared at runtime.

Fork-and-own is explicitly permitted. The orchestrator may copy implementation patterns, falsifier-registry shapes, audit-log schemas, plug-replaceability harnesses, KG-node taxonomies, test patterns, and architectural ideas from sibling workstreams and reimplement them inside Polymath. Runtime co-dependency is rejected: no shared running services, databases, corpora, or git imports across workstreams.
