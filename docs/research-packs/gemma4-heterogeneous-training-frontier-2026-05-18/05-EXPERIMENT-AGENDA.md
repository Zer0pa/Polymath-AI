# Experiment Agenda

## Principle

The next experiments should distinguish between hardware-native learning
hypotheses. They should not merely extend the current code path because it is
available.

## Experiment A - Bottleneck Autopsy Of Six-Hour Run

Question:

```text
Why was active training only about 1.29 hours inside a six-hour wall-clock run?
```

Measure:

- kernel time;
- CPU tokenization time;
- launch overhead;
- checkpoint write time;
- validation/oracle sampling time;
- idle/sleep/pacing time;
- network and UFS wait;
- thermal throttling, if any.

Decision:

- If idle/orchestration dominates, redesign scheduler and loop.
- If launch overhead dominates, fuse or persist.
- If checkpoint/validation dominates, change cadence.
- If compute dominates, optimize kernels or trainable scope.

## Experiment B - Trainable Scope Sweep

Question:

```text
Which small trainable state gives the best signal per resource?
```

Compare:

- current rank-4 post-layer0 residual adapter;
- rank `8`, `16`, `32`;
- adapter after layer1;
- LoRA on attention output projection;
- LoRA on MLP down/up projections;
- trainable norm scale/bias if model architecture permits;
- small memory/prefix module.

Metrics:

- gradient parity;
- memory high-water;
- active training seconds per update;
- loss movement on fixed stream shard;
- checkpoint size;
- stability over chained updates.

Decision:

- Choose trainable scope by evidence, not convention.

## Experiment C - NPU Role Reinterpretation

Question:

```text
If Hexagon cannot train directly, what role can it play in learning?
```

Try:

- frozen-forward layer island;
- activation recompute candidate;
- feature transform feeding GPU adapter;
- low-power validation/teacher feature pass;
- no-NPU baseline.

Metrics:

- correctness;
- data movement cost;
- memory savings;
- wall-clock impact;
- active training impact;
- complexity burden.

Decision:

- Keep HTP only if it improves the training system, not because it is present.

## Experiment D - Fusion Target Selection

Question:

```text
What fusion actually tests the megakernel thesis?
```

Candidate fusions:

- RMSNorm + projection;
- QKV projection group;
- adapter gradient reduction;
- layer forward plus adapter update;
- token-to-hidden bridge plus layer input preparation.

Avoid:

- fusion that only looks impressive but does not reduce the real bottleneck.

Decision:

- Pick fusion target after Experiment A, not before.

## Experiment E - Data Regime Probe

Question:

```text
What data pattern produces measurable useful change in the narrow lane?
```

Compare:

- repeated dense technical paragraphs;
- teacher-distilled target pairs;
- contrastive/reconstruction micro-objective;
- small Polymath shard with replay;
- random/control text.

Metrics:

- loss movement;
- adapter norm growth;
- validation replay;
- forgetting or instability;
- update efficiency.

Decision:

- Do not scale corpus until the objective produces meaningful signal.

## Experiment F - Authority Metric Revision

Question:

```text
What is the next authority metric after "can update stably"?
```

Candidate metrics:

- useful loss reduction on held-out streamed shard;
- teacher-agreement improvement;
- retrieval/recall improvement on dense Polymath facts;
- stable checkpoint over sustained run;
- energy-normalized update quality if measurement is available.

Decision:

- Choose one metric before scaling training.

## Immediate Recommendation

Run Experiment A and B before another long endurance run.

Reason:

- The current lane is stable.
- Stability without bottleneck understanding can waste days.
- Trainable scope is likely the strongest lever for capability movement.
- Fusion and NPU decisions should follow bottleneck evidence.
