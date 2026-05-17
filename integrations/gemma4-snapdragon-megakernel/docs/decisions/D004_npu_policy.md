# D004 NPU Policy

Decision: NPU is a proof lane for fixed-shape frozen-forward subgraphs, not a blocker for the training runtime.

## Evidence

- QNN/QAIRT/SNPE CLIs were not found in PATH during Mac census.
- Prior art shows mobile NPU success when prompts/subgraphs are made static, quantized, and hardware-aware.
- No evidence found tonight supports Hexagon/QNN as a practical backward/optimizer path for Gemma 4 selective training.

## Consequence

The NPU lane may accelerate frozen forward, drafter/evaluator work, or future Hexagon-MLIR experiments. It does not block CPU/GPU kernel parity.
