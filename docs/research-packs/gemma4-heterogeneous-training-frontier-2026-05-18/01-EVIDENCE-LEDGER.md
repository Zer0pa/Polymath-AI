# Evidence Ledger

## E0 - Passed First Authority Gate

Gemma4 Kernel proved a real pretrained Gemma 4 E4B layer can run on the phone
GPU and match RunPod PyTorch.

- Model: `google/gemma-4-E4B`
- Revision: `7aa32e6889efd6300124851b164f8b364314c3d8`
- Layer: decoder layer `0`
- Backend: OpenCL
- Device: REDMAGIC `NX789J / SM8750`
- p50 FP64 cosine: `0.9999890020383452`
- min FP64 cosine: `0.9999801999737985`
- failed tokens: `0`
- repeat output: byte-identical

Meaning:

- Real model-specific OpenCL phone forward execution is real.
- The comparator method is useful.
- This is only a forward-layer gate, not training.

## E1 - Two-Layer Forward Expansion Passed

Two sequential E4B layers ran on REDMAGIC OpenCL.

- Layers: `[0, 1]`
- p50 cosine: `0.999993563915067`
- min cosine: `0.9999842650888192`
- failed tokens: `0`
- G1 layer-0 hash remained preserved.
- Max RSS high-water: `818764` KB.

Meaning:

- The phone can chain real Gemma layers through OpenCL without immediately
  losing numerical validity.
- Memory for two layers is not the current blocker.

## E2 - Minimal Training Scope Passed

The system implemented a rank-4 post-layer0 residual adapter.

Backward path:

- Trainable scope: post-layer0 rank-4 residual adapter.
- Reference: RunPod PyTorch autograd.
- Gradient cosine min: `0.9999999999999384`.
- Gradient p50: `0.9999999999999647`.
- Failed gradient tensors: `0`.

Optimizer update:

- Optimizer: SGD.
- Learning rate: about `0.01`.
- Frozen layer hashes stable.
- Trainable adapter tensors mutated.

Meaning:

- We have a real, narrow phone-side gradient/update path.
- It is not full-layer training.
- It is not proof that this is the best trainable scope.

## E3 - Phone-Native Input Path Was Repaired

The first integrated training attempt was rejected because it consumed hidden
state fixtures. The repaired path moved to:

```text
phone token cache -> phone generated hidden state -> OpenCL layer0/layer1
-> OpenCL adapter update
```

Evidence from repaired G8:

- Active tokens: `796`.
- Sequence count: `8`.
- Token-to-hidden p50 minimum: `0.9999982087594611`.
- Layer0 p50: `0.9999895268153007`.
- Layer1 p50: `0.9999936773992628`.
- Adapter update cosine min: `0.9999981024312786`.
- Frozen hashes stable.
- Trainable checkpoint changed.
- G1 and G3 regressions stayed green.

Meaning:

- The project correctly caught and repaired hidden fixture dependence.
- A phone-side token-to-training path now exists for the narrow lane.

## E4 - Three-Batch Sustained Chain Passed

The system ran three phone-native batches through the narrow training lane.

- Batch count: `3`.
- Active tokens per batch: `796`, `841`, `828`.
- All token, layer, adapter comparisons passed.
- Frozen hashes stable.
- Trainable hashes changed across batches.

Meaning:

- The system can chain multiple updates, not only one isolated update.
- It is still a narrow rank-4 two-layer lane.

## E5 - Six-Hour Endurance Passed For Current Narrow Lane

Phase 10 endurance passed for the current rank-4 two-layer phone-native
training lane.

- Wall-clock: `21692.164s`.
- Chained iterations: `465`.
- Active training: `4626.646s`.
- Max thermal status: `0`.
- Sampled parity passed at iterations `0`, `240`, `464`.
- Adapter update cosine minima:
  - `0.9999981024312784`
  - `0.9999991281373523`
  - `0.9999993917530322`

Meaning:

- The narrow lane is stable enough to keep running.
- This is important and should not be minimized.
- It does not prove full Gemma4 training.

## E6 - Hexagon/QNN Evidence Is Inference-Only

QNN/HTP platform validation passed. HTP inference/context execution ran.

Evidence:

- Hexagon Architecture V79 reported.
- QNN backend supported and unit test passed.
- `qnn-net-run` executed an existing context graph.
- HVX threads used in inference.

Meaning:

- Hexagon is physically available and usable through QAIRT/QNN.
- No HTP backward, gradient, or optimizer path executed.
- NPU training is not proven.
