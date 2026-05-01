"""ELO (Efficient Layer-Specific Optimization) Stage 1 / Stage 2 trainer.

Reimplementation of the EACL 2026 Industry Track method (arXiv:2601.03648).
The PRD treats ELO as owned implementation risk; no public reference code
was found.

Stage 1 - boundary-only pretraining
    * Freeze every transformer layer except the first and last (configurable
      via ``FreezePlan``).
    * Freeze embeddings by default; ``lm_head`` trainable.
    * Optimizer state is restricted to trainable parameters (saves ~20 GB
      of Adam state on Qwen2.5-1.5B).
    * Activation checkpointing on the trainable layers when sequence length
      >= 512.

Stage 2 - alignment
    * Reload base checkpoint, swap in trained boundary weights.
    * Brief full-model fine-tune on a small calibration slice.
    * Save merged checkpoint with rollback pointer.

Frozen-parameter hash invariants are enforced as falsifier-grade tests: if a
frozen parameter changes hash across a training step, the freeze plan is
broken and the run aborts.
"""
from polymath_ai.elo.trainer import (
    ELOConfig,
    ELOStage1Model,
    ELOTrainer,
    FreezeValidation,
    TrainStepRecord,
    frozen_param_hash_sample,
    trainable_parameter_names,
)

__all__ = [
    "ELOConfig",
    "ELOStage1Model",
    "ELOTrainer",
    "FreezeValidation",
    "TrainStepRecord",
    "frozen_param_hash_sample",
    "trainable_parameter_names",
]
