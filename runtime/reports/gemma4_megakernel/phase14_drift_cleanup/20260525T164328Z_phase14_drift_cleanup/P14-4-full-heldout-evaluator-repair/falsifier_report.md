# P14-4 Falsifier Report

- Full heldout queues cover the requested heldout shard count for both baseline and candidate arms.
- Both evaluator arms force `apply_update=false`, `learning_rate=0`, and independent checkpoint inputs.
- The launch script has no wait on a train-final manifest or original train-chain state.
- Existing phone eval telemetry aggregates with exact objective, model, hidden-size, and teacher provenance fields.
- Existing eval telemetry shows no applied update and zero checkpoint delta.
