"""Common adapter contracts: ``FreezePlan`` and the freeze-plan applicator.

Real Qwen2.5-1.5B and SmolLM3-3B adapters wrap Hugging Face ``transformers``
``AutoModelForCausalLM``. They are constructed lazily because torch and
transformers may not be available in all environments (Termux probe path).
"""
from __future__ import annotations

import dataclasses
from typing import Any, List, Optional, Sequence, Tuple


@dataclasses.dataclass(frozen=True)
class FreezePlan:
    """Specification of which transformer layers, embedding tables, and
    output projections are trainable in ELO Stage 1.
    """

    trainable_layer_indices: Tuple[int, ...]
    freeze_embeddings: bool
    train_lm_head: bool
    policy_name: str

    def to_dict(self) -> dict:
        return {
            "trainable_layer_indices": list(self.trainable_layer_indices),
            "freeze_embeddings": self.freeze_embeddings,
            "train_lm_head": self.train_lm_head,
            "policy_name": self.policy_name,
        }


def _resolve_layer_index(num_layers: int, idx: int) -> int:
    if idx < 0:
        return num_layers + idx
    return idx


def untie_lm_head_if_tied(model) -> bool:
    """If ``lm_head.weight`` shares storage with ``embed_tokens.weight``,
    clone ``lm_head.weight`` so the two parameters become independent.

    Returns True when an untie was performed.

    Why this exists: the ELO freeze plan trains ``lm_head`` while keeping
    embeddings frozen. With tied weights this is impossible. Untying
    creates an independent tensor of ~150 MiB for Qwen2.5-1.5B in BF16 -
    well within the 24 GB budget. The decision is recorded in
    docs/DECISIONS.md (D-001).
    """
    import torch.nn as nn

    embed = _embed_module(model)
    lm_head = _lm_head_module(model)
    if embed is None or lm_head is None or not hasattr(lm_head, "weight"):
        return False
    if lm_head.weight is embed.weight:
        new_w = nn.Parameter(lm_head.weight.detach().clone())
        lm_head.weight = new_w
        return True
    return False


def apply_freeze_plan(model, plan: FreezePlan) -> None:
    """Walk a model that follows the HF Qwen-style ``model.layers`` /
    ``model.embed_tokens`` / ``lm_head`` layout and set ``requires_grad``
    according to ``plan``.

    Untying step: when ``freeze_embeddings`` is True AND ``train_lm_head``
    is True AND the model uses tied weights, ``lm_head`` is untied first.
    The freeze flags then apply to two independent tensors as expected.
    """
    layers = _layers_module(model)
    n = len(layers)
    target_indices = {_resolve_layer_index(n, i) for i in plan.trainable_layer_indices}

    if plan.freeze_embeddings and plan.train_lm_head:
        untie_lm_head_if_tied(model)

    for name, param in model.named_parameters():
        param.requires_grad = False

    # Embeddings.
    embed_module = _embed_module(model)
    if embed_module is not None:
        for p in embed_module.parameters():
            p.requires_grad = not plan.freeze_embeddings

    # Per-layer.
    for i, blk in enumerate(layers):
        rg = i in target_indices
        for p in blk.parameters():
            p.requires_grad = rg

    # LM head.
    lm_head = _lm_head_module(model)
    if lm_head is not None and plan.train_lm_head:
        for p in lm_head.parameters():
            p.requires_grad = True


def _layers_module(model):
    if hasattr(model, "model") and hasattr(model.model, "layers"):
        return model.model.layers
    if hasattr(model, "layers"):
        return model.layers
    raise AttributeError("model has no .model.layers or .layers")


def _embed_module(model):
    if hasattr(model, "model") and hasattr(model.model, "embed_tokens"):
        return model.model.embed_tokens
    if hasattr(model, "embed_tokens"):
        return model.embed_tokens
    return None


def _lm_head_module(model):
    if hasattr(model, "lm_head"):
        return model.lm_head
    return None


# ---------- ModelAdapter Protocol (informal; structural duck-typing) ----------


class ModelAdapter:
    model_id: str
    model_family: str
    license_id: str

    def load(self, revision: str, dtype: str, device: str): ...
    def model(self): ...
    def freeze_policy(self, policy_name: str) -> FreezePlan: ...
    def trainable_parameters(self, freeze_plan: FreezePlan) -> List[str]: ...


# ---------- HF Qwen adapter (lazy) ----------


class _HFAdapter:
    """Common base for HF AutoModelForCausalLM adapters.

    Construction is lazy: ``load()`` triggers the actual download/import.
    Use ``probe()`` first when running on machines where torch may be absent
    (Termux pre-bootstrap, dev-machine before pip install completes).
    """

    model_id: str = ""
    model_family: str = ""
    license_id: str = ""
    default_revision: Optional[str] = None
    n_layers_hint: Optional[int] = None  # known for Qwen2.5-1.5B (28), SmolLM3-3B (36)

    def __init__(self) -> None:
        self._model = None
        self._tokenizer = None

    def probe(self) -> dict:
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401
            ok = True
            err = None
        except Exception as e:  # pragma: no cover - probe path
            ok = False
            err = repr(e)
        return {
            "model_id": self.model_id,
            "torch_transformers_importable": ok,
            "import_error": err,
        }

    def load(self, revision: Optional[str] = None, dtype: str = "bf16", device: str = "cpu"):
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        torch_dtype = {
            "fp32": torch.float32,
            "fp16": torch.float16,
            "bf16": torch.bfloat16,
        }[dtype]

        rev = revision or self.default_revision
        kwargs: dict = {"torch_dtype": torch_dtype}
        if rev:
            kwargs["revision"] = rev
        m = AutoModelForCausalLM.from_pretrained(self.model_id, **kwargs)
        if device != "cpu":
            m = m.to(device)
        self._model = m
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_id, **({"revision": rev} if rev else {}))
        return m

    def model(self):
        if self._model is None:
            self.load()
        return self._model

    def tokenizer(self):
        if self._tokenizer is None:
            self.load()
        return self._tokenizer

    def freeze_policy(self, policy_name: str = "elo_first_last") -> FreezePlan:
        if policy_name != "elo_first_last":
            raise ValueError(f"unknown policy {policy_name!r}")
        if self.n_layers_hint is None:
            n = len(_layers_module(self.model()))
        else:
            n = self.n_layers_hint
        return FreezePlan(
            trainable_layer_indices=(0, n - 1),
            freeze_embeddings=True,
            train_lm_head=True,
            policy_name=policy_name,
        )

    def trainable_parameters(self, freeze_plan: FreezePlan) -> List[str]:
        m = self.model()
        apply_freeze_plan(m, freeze_plan)
        return [n for n, p in m.named_parameters() if p.requires_grad]


class _Qwen25_1p5B(_HFAdapter):
    model_id = "Qwen/Qwen2.5-1.5B"
    model_family = "qwen2.5"
    license_id = "license:apache-2.0:qwen2.5-1.5b"
    default_revision = "main"
    n_layers_hint = 28


class _SmolLM3_3B(_HFAdapter):
    model_id = "HuggingFaceTB/SmolLM3-3B"
    model_family = "smollm3"
    license_id = "license:apache-2.0:smollm3-3b"
    default_revision = "main"
    n_layers_hint = 36  # confirmed at load time


def qwen2_5_1p5b_adapter() -> _Qwen25_1p5B:
    return _Qwen25_1p5B()


def smollm3_3b_adapter() -> _SmolLM3_3B:
    return _SmolLM3_3B()
