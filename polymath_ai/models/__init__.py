"""Model adapters.

Three adapters are required by the PRD:

* ``TinyQwenShapeAdapter`` - tiny randomly initialised Qwen-shape architecture
  for CI smoke tests. No external dependencies, fast on CPU.
* ``Qwen25_15BAdapter`` - Hugging Face wrapper for ``Qwen/Qwen2.5-1.5B``.
* ``SmolLM3_3BAdapter`` - Hugging Face wrapper for ``HuggingFaceTB/SmolLM3-3B``.

Each adapter implements the ``ModelAdapter`` protocol (PRD §Interface
Contracts > ModelAdapter): ``load``, ``tokenizer``, ``freeze_policy``,
``trainable_parameters``, ``forward``, ``generate``, ``save_checkpoint``,
``load_checkpoint``, ``export_probe``.
"""
from polymath_ai.models.tiny_qwen import (
    TinyQwenConfig,
    TinyQwenForCausalLM,
    TinyQwenShapeAdapter,
)
from polymath_ai.models.adapters import (
    FreezePlan,
    ModelAdapter,
    qwen2_5_1p5b_adapter,
    smollm3_3b_adapter,
)

__all__ = [
    "TinyQwenConfig",
    "TinyQwenForCausalLM",
    "TinyQwenShapeAdapter",
    "FreezePlan",
    "ModelAdapter",
    "qwen2_5_1p5b_adapter",
    "smollm3_3b_adapter",
]
