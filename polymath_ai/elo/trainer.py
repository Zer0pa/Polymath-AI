"""ELO Stage 1 / Stage 2 implementation.

Stage 1 freezes every parameter outside the configured ``FreezePlan`` and
trains only the boundary layers + lm_head. Stage 2 reloads the base model,
swaps the boundary checkpoint in, and runs a brief calibration pass with
all parameters unfrozen.

Frozen-parameter hash invariants are first-class: ``frozen_param_hash_sample``
captures a deterministic SHA over a small sample before the step, the same
sample is recomputed after the step, and a mismatch is a falsifier-grade
event (``checkpoint_hash_mismatch`` blocking).
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from polymath_ai._version import SCHEMA_VERSION
from polymath_ai.boundary.text import boundary_envelope
from polymath_ai.models.adapters import FreezePlan, apply_freeze_plan
from polymath_ai.utils.canonical import canonical_json, hash_mapping, sha256_text


@dataclasses.dataclass
class ELOConfig:
    """Configuration for an ELO Stage 1 / Stage 2 run."""

    learning_rate: float = 2e-4
    weight_decay: float = 0.1
    betas: Tuple[float, float] = (0.9, 0.95)
    grad_clip: float = 1.0
    seed: int = 1234
    accumulation_steps: int = 1
    activation_checkpointing: bool = False  # tiny model doesn't benefit
    use_amp: bool = False  # Mac CPU smoke is fp32; device path may flip


@dataclasses.dataclass
class FreezeValidation:
    trainable_param_names: List[str]
    frozen_param_count: int
    trainable_param_count: int
    optimizer_param_count: int
    optimizer_only_includes_trainable: bool


@dataclasses.dataclass
class TrainStepRecord:
    step: int
    loss: float
    grad_norm: float
    trainable_param_names: Tuple[str, ...]
    frozen_hashes_before: Mapping[str, str]
    frozen_hashes_after: Mapping[str, str]
    frozen_hashes_changed: List[str]


def _deterministic_sample_param_names(model, k: int = 6, seed: int = 0) -> List[str]:
    """Pick a deterministic, repeatable sample of frozen params."""
    import random
    frozen = sorted(name for name, p in model.named_parameters() if not p.requires_grad)
    if not frozen:
        return []
    rng = random.Random(seed)
    return rng.sample(frozen, k=min(k, len(frozen)))


def _tensor_bytes(t) -> bytes:
    """Return the raw byte buffer of ``t`` without going through numpy.

    NumPy does not support BF16; ``untyped_storage().tobytes()`` works for
    every dtype torch supports.
    """
    return bytes(t.detach().contiguous().cpu().untyped_storage())


def frozen_param_hash_sample(model, names: Optional[Sequence[str]] = None, k: int = 6, seed: int = 0) -> Dict[str, str]:
    """Hash a sample of frozen parameters.

    The frozen parameter must be byte-for-byte identical across training
    steps. Any change is a violation of the freeze plan and a
    ``checkpoint_hash_mismatch`` (or freeze-plan violation in tests).
    """
    if names is None:
        names = _deterministic_sample_param_names(model, k=k, seed=seed)
    out: Dict[str, str] = {}
    names_set = set(names)
    for n, p in model.named_parameters():
        if n in names_set:
            out[n] = "sha256:" + hashlib.sha256(_tensor_bytes(p)).hexdigest()
    return out


def trainable_parameter_names(model) -> List[str]:
    return [n for n, p in model.named_parameters() if p.requires_grad]


# ---------- Trainer ----------


class ELOStage1Model:
    """Wrapper that ties a model + freeze plan + optimizer.

    Constructed by ``ELOTrainer.build_stage1_model``. Holds enough state to
    save and resume from boundary checkpoints.
    """

    def __init__(self, model, freeze_plan: FreezePlan, cfg: ELOConfig) -> None:
        import torch

        self.model = model
        self.freeze_plan = freeze_plan
        self.cfg = cfg
        apply_freeze_plan(self.model, self.freeze_plan)
        self.trainable_params = [
            p for _, p in model.named_parameters() if p.requires_grad
        ]
        # Dedupe by id() so tied embeddings don't double-list. Adam sees one
        # tensor per id even when two names point to the same storage.
        seen: set[int] = set()
        unique_params = []
        for p in self.trainable_params:
            if id(p) not in seen:
                unique_params.append(p)
                seen.add(id(p))
        self.optimizer = torch.optim.AdamW(
            unique_params,
            lr=cfg.learning_rate,
            weight_decay=cfg.weight_decay,
            betas=cfg.betas,
        )
        self.step_idx = 0


class ELOTrainer:
    """ELO Stage 1 / Stage 2 trainer."""

    def __init__(self, cfg: Optional[ELOConfig] = None) -> None:
        self.cfg = cfg or ELOConfig()

    # ---- Stage 1 ----

    def build_stage1_model(self, model, freeze_plan: FreezePlan) -> ELOStage1Model:
        return ELOStage1Model(model=model, freeze_plan=freeze_plan, cfg=self.cfg)

    def validate_freeze_plan(self, stage1: ELOStage1Model) -> FreezeValidation:
        names = trainable_parameter_names(stage1.model)
        trainable_ids = {id(p) for p in stage1.trainable_params}
        opt_ids = {id(p) for group in stage1.optimizer.param_groups for p in group["params"]}
        return FreezeValidation(
            trainable_param_names=names,
            frozen_param_count=sum(1 for _, p in stage1.model.named_parameters() if not p.requires_grad),
            trainable_param_count=len(names),
            optimizer_param_count=len(opt_ids),
            optimizer_only_includes_trainable=opt_ids.issubset(trainable_ids),
        )

    def train_step(
        self,
        stage1: ELOStage1Model,
        batch_input_ids,
        batch_labels,
        *,
        sample_names: Optional[Sequence[str]] = None,
    ) -> TrainStepRecord:
        import torch

        before = frozen_param_hash_sample(stage1.model, sample_names)
        stage1.optimizer.zero_grad(set_to_none=True)
        out = stage1.model(batch_input_ids, labels=batch_labels)
        # Three possible shapes:
        #   * tiny model: ``(logits, loss)`` tuple
        #   * HF AutoModelForCausalLM: namespace with ``.loss``
        #   * Custom: bare loss tensor
        if hasattr(out, "loss") and out.loss is not None:
            loss = out.loss
        elif isinstance(out, tuple):
            loss = out[1]
        else:
            loss = out
        loss.backward()
        # gradient clipping on trainable params only
        torch.nn.utils.clip_grad_norm_(stage1.trainable_params, max_norm=stage1.cfg.grad_clip)
        grad_norm = sum(
            (p.grad.detach() ** 2).sum().item() for p in stage1.trainable_params if p.grad is not None
        ) ** 0.5
        stage1.optimizer.step()
        stage1.step_idx += 1
        after = frozen_param_hash_sample(stage1.model, list(before.keys()))
        changed = [k for k in before if before.get(k) != after.get(k)]
        return TrainStepRecord(
            step=stage1.step_idx,
            loss=float(loss.detach()),
            grad_norm=float(grad_norm),
            trainable_param_names=tuple(trainable_parameter_names(stage1.model)),
            frozen_hashes_before=before,
            frozen_hashes_after=after,
            frozen_hashes_changed=changed,
        )

    # ---- Checkpoint save / resume ----

    def save_boundary_checkpoint(
        self,
        stage1: ELOStage1Model,
        out_dir: str | os.PathLike[str],
        *,
        run_id: str,
        config_sha256: str = "sha256:unknown",
        corpus_slice_id: Optional[str] = None,
        base_model_pointer: Optional[str] = None,
        license_attestation_id: Optional[str] = None,
        checkpoint_kind: str = "stage1_boundary",
    ) -> dict:
        """Save trainable weights + optimizer state + manifest. Frozen
        weights are NOT saved here - they are recovered from the base
        checkpoint pointer.
        """
        import torch

        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)

        trainable_state = {
            n: p.detach().cpu()
            for n, p in stage1.model.named_parameters()
            if p.requires_grad
        }
        torch.save(trainable_state, out / "trainable.pt")
        torch.save(stage1.optimizer.state_dict(), out / "optimizer.pt")

        # Frozen-hash sample for the manifest; deterministic seed.
        frozen_sample_names = _deterministic_sample_param_names(stage1.model, k=6, seed=0)
        frozen_sample = frozen_param_hash_sample(stage1.model, frozen_sample_names)

        # Streaming SHA-256 over (sorted name) | b":" | tensor bytes for
        # each trainable. This avoids materialising a multi-GB hex string
        # for production-scale trainables (Qwen2.5-1.5B's lm_head alone is
        # 466 MB BF16); a JSON-of-hex round-trip blew up to >1 GB and hung
        # the save. Streaming form is dtype-agnostic and replay-stable.
        h = hashlib.sha256()
        for n in sorted(trainable_state.keys()):
            h.update(n.encode("utf-8"))
            h.update(b":")
            h.update(_tensor_bytes(trainable_state[n]))
            h.update(b"\n")
        ckpt_sha = "sha256:" + h.hexdigest()

        manifest = {
            "schema_version": SCHEMA_VERSION,
            "boundary": boundary_envelope(),
            "run_id": run_id,
            "checkpoint_kind": checkpoint_kind,
            "model_id": getattr(stage1.model, "config", None).__class__.__name__ if hasattr(stage1.model, "config") else "unknown",
            "checkpoint_sha256": ckpt_sha,
            "trainable_param_names": sorted(trainable_state.keys()),
            "frozen_param_hash_sample": frozen_sample,
            "optimizer_state_keys": sorted(stage1.optimizer.state_dict().keys()),
            "step": stage1.step_idx,
            "tokens_seen": stage1.step_idx,  # caller may overwrite with real
            "config_sha256": config_sha256,
            "corpus_slice_id": corpus_slice_id,
            "base_model_pointer": base_model_pointer,
            "license_attestation_id": license_attestation_id,
            "hf_repo_id": None,
            "hf_path": None,
            "local_path": str(out),
            "freeze_plan": stage1.freeze_plan.to_dict(),
        }
        (out / "manifest.json").write_text(canonical_json(manifest))
        return manifest

    def load_boundary_checkpoint(
        self,
        stage1: ELOStage1Model,
        ckpt_dir: str | os.PathLike[str],
    ) -> dict:
        import torch

        ckpt = Path(ckpt_dir)
        manifest = json.loads((ckpt / "manifest.json").read_text())
        trainable_state: Dict[str, Any] = torch.load(ckpt / "trainable.pt", map_location="cpu")

        # Verify trainable param names match the freeze plan currently active.
        current_trainable = set(trainable_parameter_names(stage1.model))
        if current_trainable != set(trainable_state.keys()):
            raise ValueError(
                f"freeze plan drift: ckpt trainable={sorted(trainable_state.keys())}, "
                f"current trainable={sorted(current_trainable)}"
            )

        # Apply weights.
        for n, p in stage1.model.named_parameters():
            if n in trainable_state:
                p.data.copy_(trainable_state[n].to(p.dtype))

        opt_state = torch.load(ckpt / "optimizer.pt", map_location="cpu")
        stage1.optimizer.load_state_dict(opt_state)
        stage1.step_idx = int(manifest.get("step", 0))
        return manifest

    # ---- Stage 2 ----

    def merge_boundary_checkpoint(
        self,
        base_model,
        stage1: ELOStage1Model,
    ):
        """Copy trained boundary weights from ``stage1`` into ``base_model``
        in-place. Both models must share the same parameter naming.
        """
        for name, p in base_model.named_parameters():
            for src_name, src_p in stage1.model.named_parameters():
                if src_name == name and src_p.requires_grad:
                    p.data.copy_(src_p.data.to(p.dtype))
                    break
        return base_model

    def run_stage2_alignment(
        self,
        base_model,
        calibration_loader,
        *,
        num_steps: int,
        lr: float = 5e-5,
    ):
        """Brief full-model calibration. Returns a list of per-step losses.

        ``calibration_loader`` is any iterable yielding ``(input_ids, labels)``
        torch tensors. Caller manages activation checkpointing if desired.
        """
        import torch

        for p in base_model.parameters():
            p.requires_grad = True
        opt = torch.optim.AdamW(base_model.parameters(), lr=lr)
        losses: List[float] = []
        for i, (input_ids, labels) in enumerate(calibration_loader):
            if i >= num_steps:
                break
            opt.zero_grad(set_to_none=True)
            out = base_model(input_ids, labels=labels)
            loss = out[1] if isinstance(out, tuple) else out
            loss.backward()
            torch.nn.utils.clip_grad_norm_(base_model.parameters(), 1.0)
            opt.step()
            losses.append(float(loss.detach()))
        return losses
