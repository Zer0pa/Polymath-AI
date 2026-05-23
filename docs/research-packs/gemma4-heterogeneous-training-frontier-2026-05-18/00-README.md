# Gemma 4 Heterogeneous Training Frontier Pack

Date: 2026-05-18
Status: HANDOFF_PACK_FOR_ENGINEERING_AND_DEEP_RESEARCH
Scope: REDMAGIC `NX789J` / Snapdragon `SM8750`, Gemma 4 E4B, native phone training

## Purpose

This pack is for an engineering and science team, or a deep research agent, to
pause the execution treadmill and reason from the evidence.

The project has crossed beyond a toy proof. It has also exposed that the
current path can become conventional incrementalism if we simply keep scaling
the narrow OpenCL adapter lane. The question is no longer only "what code next?"
The question is:

```text
What training workflow does this phone hardware want?
```

The phone is not a small cloud GPU. It is a heterogeneous computer with CPU,
Adreno GPU, Hexagon NPU, UFS storage, shared memory, thermals, and bandwidth
constraints. The goal is not to force it into a miniature warehouse pattern.
The goal is to discover a learning process that fits this town of specialized
workers.

## Pack Documents

Read these documents in order:

1. `00-README.md` - orientation and use.
2. `01-EVIDENCE-LEDGER.md` - what actually passed.
3. `02-FAILURE-AND-LIMITATION-MAP.md` - what failed or remains unproven.
4. `03-HARDWARE-WANTS-QUESTION.md` - the core scientific/engineering reframing.
5. `04-DEEP-RESEARCH-BRIEF.md` - prompt for a current external research agent.
6. `05-EXPERIMENT-AGENDA.md` - next experiments that answer hardware questions.
7. `06-ARTIFACT-INDEX.md` - source artifact pointers.

That is seven docs total. Do not expand the pack unless a new gate changes the
research question.

## One-Line Situation

We have a stable narrow phone-native Gemma 4 training lane, but not full Gemma 4
training, not Hexagon/NPU training, not public benchmark readiness, and not
anything close to theoretical maximum. The next move should be hardware-led
research and experiment design, not simple feature scaling.

## Non-Negotiable Reading Rule

Do not convert "six-hour endurance passed" into "we solved phone training."
Do not convert "Hexagon inference works" into "NPU training works."
Do not convert "OpenCL adapter training works" into "this is the right
heterogeneous schedule."

These are signals. Treat them as signals.
