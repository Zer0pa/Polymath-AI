# Zer0pa Polymath AI — Workstream Repository

Canonical home for the Zer0pa Polymath AI on-device training work stream. Multi-agent handoff: synthesis → orchestrator → overnight executor → device deployment. Repo is the source of truth across machines.

**Polymath AI is the first non-pipeline-vertical workstream in the Zer0pa portfolio.** It is a systems engineering project — train a multilingual / multi-domain "Polymath" language model on the operator's REDMAGIC 10 Pro+ (Snapdragon 8 Elite, 24GB LPDDR5X) using ELO selective continual pretraining on heterogeneous on-device compute (Adreno 830 GPU + Hexagon NPU + Oryon CPU). The same modus operandi as Health / Materials / Energy / Synthetic Biology applies — anti-MVP, anti-toy, overdesigned best-in-class, overnight long-horizon execution, GitHub + Hugging Face as review surface, fork-and-own across workstreams, RESISTANCE.md doctrine binding.

## Boundary

Research infrastructure for in silico on-device LLM training and multilingual / multi-domain knowledge model construction. Outputs are research artifacts (model checkpoints, training telemetry, evaluation reports, throughput measurements). No regulatory certification claims. No clinical or human-subject use. No surveillance, biometric profiling, or identity inference. No model weights distributed without an explicit license attestation. No training on copyrighted material without an explicit corpus-license decomposition. No deployment to production without a falsifier-traced acceptance gate.

## What is in here

| Path | Purpose | Author role |
|---|---|---|
| `MODUS-OPERANDI.md` | Reusable multi-agent pattern + parallel-exploration principle (5th instance after Health, Materials, Energy, Synthetic Biology); explicit recognition that this is a non-pipeline-vertical project and that the same discipline applies | Synthesis agent |
| `HANDOFF-TO-ORCHESTRATOR.md` | Polymath-specific brief for the next agent (the polymath orchestrator) — defines what they inherit, what they must produce, the operator-policy refinements (anti-MVP, 110% pre-device-corpus-investment, overnight long-horizon, GitHub + HF review surface, fork-and-own) | Synthesis agent |
| `ORCHESTRATOR-STARTUP-PROMPT.md` | The exact prompt the user pastes into a fresh agent session to spin up the polymath orchestrator | Synthesis agent |
| `RESISTANCE.md` | Anti-corruption doctrine — fp-shapematchRE / fp-rushtoend / fp-NULLasout / fp-approvalseek / fp-flatteryasfreedom / efficiency-as-corner-cutting; binding for every executor before work starts | Imported from DM3 |
| `source-briefs/` | Inherited research input — the operator-authored Pre-PRD Research Synthesis / Blueprint / Engineering Specification (`01-on-device-training-blueprint.md`, ~52 KB / 804 lines, dated 2026-05-01); structurally a hybrid research-agent + synthesis-agent output | External (consumer of synthesis) |
| `synthesis/` | Fresh-eyes reading of the operator's blueprint by the synthesis agent — the twelve specific things the blueprint does not see; the recursive-fresh-eyes principle applied to a doc that is itself already a synthesis; the operator-policy translation for a non-Runpod / on-device project | Synthesis agent |
| `PRD.md` (to be written) | The PRD that drives the overnight long-horizon execution by the executor agent on a device-bound machine (Mac → Android via Termux + ADB; phone-side execution for actual training) | Polymath orchestrator |

## Read order for the next agent

1. `RESISTANCE.md` — anti-corruption doctrine. Read first. Headspace.
2. `MODUS-OPERANDI.md` — how the role chain works; § Operator refinements (binding for all workstreams, 2026-05-01) and § Beyond pipeline verticals.
3. `HANDOFF-TO-ORCHESTRATOR.md` — what you (polymath orchestrator) inherit and produce. Includes the operator-policy translation for a non-Runpod / on-device project.
4. `source-briefs/01-on-device-training-blueprint.md` — the operator-authored Pre-PRD Research Synthesis / Blueprint / Engineering Specification. Hardware ground truth, ELO training method, model selection (Qwen2.5-1.5B / SmolLM3-3B), data strategy, runtime architecture, throughput model, validation protocol (Experiment 0/1/2), phased program plan, evaluation metrics, risk register, open questions.
5. `synthesis/01-fresh-eyes-on-polymath-blueprint.md` — synthesis-agent reframe; this is the substrate for your own fresh-eyes augmentation. Twelve things the blueprint does not see including the cross-model disagreement / falsification primitive, the distillation-vs-CPT alternative, the federated multi-device opportunity, the cross-device portability concern, the corpus design as first-class spec, and the energy-budget-as-constraint reframe.

## Provenance

- Initial commit: 2026-05-01.
- Operator (Architect Prime, Zer0pa): authored the Pre-PRD Research Synthesis / Blueprint / Engineering Specification dated 2026-05-01. This collapses the research-agent + synthesis-agent roles into a single operator-authored document.
- Synthesis agent: Claude Opus 4.7 (1M context), 2026-05-01 — applied recursive fresh-eyes pass on top of the blueprint.
- Next agent: polymath orchestrator (writes `PRD.md`).
- Following: overnight executor on a device-bound machine (Mac orchestrating Android device via Termux / ADB).

## Cross-workstream principle (deliberate)

This workstream runs in parallel with `Zer0pa/Health`, `Zer0pa/Materials`, `Zer0pa/Energy`, and `Zer0pa/Synthetic-Biology`. Each workstream is built end-to-end as an independent pipeline / project. **No substrate is shared at runtime.** Redundancy across workstreams is a deliberate asset.

**Fork-and-own is explicitly permitted.** The orchestrator may copy any implementation pattern, falsifier-registry shape, audit-log schema, plug-replaceability harness, runpod-cutover scaffold (where applicable), KG-node taxonomy, code structure, test pattern, or architectural detail from a sibling workstream and reimplement it inside Polymath. Tools, datasets, components, and design patterns are stealable freely. **What is rejected is runtime co-dependency** — no shared running services, no shared databases or corpora, no shared git imports across workstreams.

The Polymath workstream specifically borrows the heterogeneous-orchestration pattern (CPU + GPU + NPU dispatch) from Energy's L6 control-plane discipline; the model-fine-tuning + corpus discipline from Health's TxGemma fine-tuning queue; the cross-model disagreement primitive (DPA-3 + MACE in Materials, DLKcat + TurNuP + DeepEnzyme in Synbio) and translates it as Qwen2.5-1.5B + SmolLM3-3B at evaluation; and the falsifier-registry + audit-log shape from all four prior workstreams. None of these are shared at runtime — Polymath carries its own copy of each.
