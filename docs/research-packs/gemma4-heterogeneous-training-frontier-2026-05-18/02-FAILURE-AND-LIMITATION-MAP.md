# Failure And Limitation Map

## Summary

The system did not fail by crashing. It failed to justify the largest claims.

The current state is:

```text
Narrow OpenCL/CPU phone training lane: real and stable.
Full Gemma4 training: not proven.
Hexagon/NPU training: not proven.
Public benchmark readiness: not proven.
Theoretical maximum: not reached.
```

## F1 - NPU Training Did Not Materialize

What worked:

- QNN/HTP platform validation.
- HTP inference/context execution.
- Hexagon V79 availability.

What did not work:

- No HTP backward pass.
- No HTP gradient computation.
- No HTP optimizer update.
- No QNN training API surface was exercised.

Interpretation:

The NPU is currently a forward/inference island, not a learning engine. That
may be a real hardware/software boundary, or it may be a tooling/representation
failure. Do not assume either until researched.

Research question:

```text
Can Hexagon contribute to training indirectly through frozen-forward, activation
recompute, teacher signal generation, low-precision feature transforms, or
pipeline overlap, even if it cannot run backward/update?
```

## F2 - The Training Scope Is Narrow

Current trainable scope:

- rank-4 post-layer0 residual adapter;
- two-layer forward path;
- SGD update;
- fixed sequence length `128`.

What this means:

- We have a real update.
- The update is tiny relative to Gemma4 E4B.
- It may not move model capability meaningfully unless the training objective
  and adapter placement are chosen well.

Research question:

```text
What is the highest-information trainable scope that fits this hardware:
adapter rank, location, layer count, residual injection point, optimizer state,
and sequence profile?
```

## F3 - Active Training Time Is Much Smaller Than Wall Time

Six-hour endurance:

- Wall-clock: about `6.03` hours.
- Active training: about `1.29` hours.
- Chained iterations: `465`.

This is not necessarily bad. It may reflect staging, sampling, validation,
sleep, I/O, cooling, or orchestration overhead. But it means the current system
is not yet an efficient continuous training appliance.

Research question:

```text
Is the bottleneck compute, launch overhead, I/O, validation, checkpointing,
thermal pacing, CPU tokenization, or orchestration?
```

## F4 - The Data Path Exists But Is Not Yet A Corpus Strategy

The repaired path proves phone token cache to training update. It does not yet
prove:

- a high-quality Polymath corpus;
- source/license decomposition at scale;
- streaming resilience over long runs;
- curriculum design;
- capability gain;
- checkpoint selection.

Research question:

```text
What data regime is native to this hardware: dense small slices, repeated
settling, online replay, micro-curricula, teacher-distilled shards, or another
shape?
```

## F5 - "Full Gemma4 Training" Is Undefined

The blocked non-claim says full Gemma4 training is not proven. That is correct,
but the phrase must be sharpened.

Possible meanings:

- train every Gemma weight;
- train a useful adapter on top of frozen Gemma;
- train selected layers;
- train routing/control state;
- train memory/adapter modules;
- train under a biologically or information-theoretically inspired settling
  regime.

Research question:

```text
What does "training Gemma4 on this phone" mean if the hardware wants selective
state updates rather than dense cloud-style backprop?
```

## F6 - We May Be Backsliding Into Conventional Software Engineering

Symptoms:

- treating the next gate as the next feature;
- interpreting NPU failure as "ignore NPU" rather than "ask what role it wants";
- treating adapter training as a conventional LoRA/SGD lane;
- optimizing for passable gates rather than discovering the hardware-native
  learning process.

Correction:

Pause and conduct a hardware-led theory/engineering review. Then design the
next experiment to distinguish between competing hypotheses about the phone's
natural learning workflow.
