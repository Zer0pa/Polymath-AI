# The Hardware-Wants Question

## Reframe

The project should not ask:

```text
How do we make a phone imitate cloud GPU training?
```

It should ask:

```text
What form of learning naturally decomposes across Oryon CPU, Adreno GPU,
Hexagon NPU, shared memory, UFS storage, network stream, and thermal envelope?
```

The current results are strong enough to justify this pause.

## Observed Hardware Preferences

### Adreno GPU

Observed:

- Real Gemma layer forward through OpenCL works.
- Two-layer forward works.
- Rank-4 adapter backward/update works.
- Six-hour narrow-lane endurance works.

Likely preference:

- dense parallel tensor work;
- custom kernels where framework dispatch would be too heavy;
- forward/backward/update for limited trainable scopes;
- repeated small updates if memory and launch overhead are controlled.

Unknown:

- whether fusion beats modular kernels for training;
- whether Vulkan should replace or complement OpenCL;
- how far layer count can expand before memory/launch overhead dominates;
- which adapter placement gives the most capability per joule.

### Oryon CPU

Observed:

- CPU is currently orchestration/control plus token path candidate.
- Phone-native token path exists in repaired G8.

Likely preference:

- streaming raw data;
- tokenization;
- sequence packing;
- scheduling;
- checkpoint/audit;
- scalar optimizer bookkeeping;
- low-rate control decisions.

Unknown:

- tokenization throughput under sustained concurrent GPU training;
- whether CPU should run part of optimizer state or gradient reductions;
- whether CPU can act as the "scribe" coordinating asynchronous learning.

### Hexagon NPU / HTP

Observed:

- Platform and inference path work.
- No backward/gradient/update path executed.

Likely preference:

- fixed-shape forward islands;
- frozen transforms;
- activation recompute if representation allows;
- low-power teacher/critic features;
- compiled inference subgraphs.

Unknown:

- whether QAIRT/QNN exposes any viable update surface beyond adapter binary
  mutation tools;
- whether HTP can serve as a forward island inside a training pipeline while
  gradients route elsewhere;
- whether binary update mechanisms can support a nonstandard learning loop;
- whether Genie/QNN/HTP APIs have newer capabilities not used here.

### UFS Storage

Observed:

- Phone-local token/cache/checkpoint path exists.

Likely preference:

- packed sequence cache;
- replay buffer;
- checkpoint chain;
- audit and telemetry storage.

Unknown:

- optimal shard size;
- write amplification under long training;
- checkpoint cadence before storage becomes a bottleneck.

## Candidate Hardware-Native Training Shapes

These are hypotheses, not conclusions.

1. **GPU-local adapter training**
   - Adreno handles forward/backward/update for small trainable modules.
   - CPU streams and schedules.
   - NPU stays parked or inference-only.

2. **NPU frozen-forward plus GPU adapter backward**
   - HTP computes fixed frozen transforms.
   - Adreno trains adapters around those transforms.
   - CPU controls and caches activations.

3. **Activation recompute island**
   - HTP recomputes frozen activations to reduce memory pressure.
   - GPU performs trainable gradient work.

4. **Online settling loop**
   - Phone sees dense high-signal text shards repeatedly.
   - Tiny trainable state updates over many passes.
   - Selection/curriculum matters more than raw token count.

5. **Teacher-distilled micro-corpus loop**
   - RunPod or external teacher creates high-information targets.
   - Phone trains compact adapters or control state natively.
   - The phone remains the runtime learner; teacher only shapes data.

6. **Hardware-aware sparse trainable state**
   - Instead of full backprop, train modules chosen for memory locality,
     gradient stability, and kernel fit.

## Core Scientific Question

```text
Is useful model improvement on SM8750 best achieved by expanding dense training,
or by finding a sparse/settling/adapter/control-state learning process that
matches the phone's heterogeneous physical structure?
```

The next research cycle should be designed to answer this, not merely to add
another conventional feature.
