"""ELO correctness on the tiny Qwen-shape model.

Phase 0B gates from PRD:

* Frozen middle layers do not change.
* Optimizer state excludes frozen parameters.
* Same seed produces deterministic smoke loss within tolerance.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

from polymath_ai.elo.trainer import ELOConfig, ELOTrainer, frozen_param_hash_sample
from polymath_ai.models.adapters import FreezePlan, apply_freeze_plan
from polymath_ai.models.tiny_qwen import (
    TinyQwenConfig,
    TinyQwenForCausalLM,
    TinyQwenShapeAdapter,
)


def _deterministic_batch(cfg: TinyQwenConfig, batch: int = 2, seq: int = 16, seed: int = 7):
    g = torch.Generator().manual_seed(seed)
    input_ids = torch.randint(0, cfg.vocab_size, (batch, seq), generator=g)
    labels = input_ids.clone()
    return input_ids, labels


def test_freeze_plan_excludes_middle_layers():
    cfg = TinyQwenConfig()
    model = TinyQwenForCausalLM(cfg)
    plan = FreezePlan(
        trainable_layer_indices=(0, cfg.num_hidden_layers - 1),
        freeze_embeddings=True,
        train_lm_head=True,
        policy_name="elo_first_last",
    )
    apply_freeze_plan(model, plan)
    trainable = {n for n, p in model.named_parameters() if p.requires_grad}
    # First and last layer params + lm_head only.
    for n in trainable:
        assert n.startswith("model.layers.0.") or n.startswith(f"model.layers.{cfg.num_hidden_layers - 1}.") or n.startswith("lm_head.")
    # Middle layers must be frozen.
    for i in range(1, cfg.num_hidden_layers - 1):
        for name, p in model.named_parameters():
            if name.startswith(f"model.layers.{i}."):
                assert not p.requires_grad, f"layer {i} param {name} not frozen"


def test_optimizer_state_excludes_frozen_params():
    torch.manual_seed(1234)
    adapter = TinyQwenShapeAdapter()
    adapter.load()
    plan = adapter.freeze_policy("elo_first_last")
    trainer = ELOTrainer(ELOConfig(seed=1234))
    stage1 = trainer.build_stage1_model(adapter.model(), plan)
    val = trainer.validate_freeze_plan(stage1)
    assert val.optimizer_only_includes_trainable, val
    assert val.frozen_param_count > 0
    assert val.trainable_param_count > 0


def test_frozen_layers_do_not_change_after_step():
    torch.manual_seed(1234)
    adapter = TinyQwenShapeAdapter()
    adapter.load()
    plan = adapter.freeze_policy("elo_first_last")
    trainer = ELOTrainer(ELOConfig(seed=1234, learning_rate=1e-2))
    stage1 = trainer.build_stage1_model(adapter.model(), plan)

    input_ids, labels = _deterministic_batch(adapter.cfg)

    rec = trainer.train_step(stage1, input_ids, labels)
    assert rec.frozen_hashes_changed == [], f"frozen params changed: {rec.frozen_hashes_changed}"

    # Multi-step: hashes still equal.
    for _ in range(4):
        rec = trainer.train_step(stage1, input_ids, labels)
        assert rec.frozen_hashes_changed == [], rec.frozen_hashes_changed


def test_trainable_layers_DO_change_after_step():
    """Sanity: the *trainable* boundary layers must move under a step."""
    torch.manual_seed(1234)
    adapter = TinyQwenShapeAdapter()
    adapter.load()
    plan = adapter.freeze_policy("elo_first_last")
    trainer = ELOTrainer(ELOConfig(seed=1234, learning_rate=1e-2))
    stage1 = trainer.build_stage1_model(adapter.model(), plan)
    input_ids, labels = _deterministic_batch(adapter.cfg)

    # Snapshot trainable params.
    snap = {n: p.detach().clone() for n, p in stage1.model.named_parameters() if p.requires_grad}
    trainer.train_step(stage1, input_ids, labels)
    moved = 0
    for n, p in stage1.model.named_parameters():
        if n in snap and not torch.allclose(p.detach(), snap[n], atol=0):
            moved += 1
    assert moved > 0, "no trainable params moved - learning rate or freeze plan broken"


def test_deterministic_seed_reproduces_loss():
    cfg = TinyQwenConfig()

    def run():
        torch.manual_seed(1234)
        adapter = TinyQwenShapeAdapter(cfg)
        adapter.load()
        plan = adapter.freeze_policy("elo_first_last")
        trainer = ELOTrainer(ELOConfig(seed=1234, learning_rate=1e-3))
        stage1 = trainer.build_stage1_model(adapter.model(), plan)
        input_ids, labels = _deterministic_batch(cfg)
        losses = []
        for _ in range(5):
            rec = trainer.train_step(stage1, input_ids, labels)
            losses.append(rec.loss)
        return losses

    a = run()
    b = run()
    for la, lb in zip(a, b):
        assert abs(la - lb) < 1e-5, f"non-determinism: {la} vs {lb}"


def test_checkpoint_save_and_resume(tmp_path):
    torch.manual_seed(1234)
    adapter = TinyQwenShapeAdapter()
    adapter.load()
    plan = adapter.freeze_policy("elo_first_last")
    trainer = ELOTrainer(ELOConfig(seed=1234, learning_rate=1e-3))
    stage1 = trainer.build_stage1_model(adapter.model(), plan)

    input_ids, labels = _deterministic_batch(adapter.cfg)

    # Run a few steps.
    losses_before = []
    for _ in range(3):
        rec = trainer.train_step(stage1, input_ids, labels)
        losses_before.append(rec.loss)
    manifest = trainer.save_boundary_checkpoint(
        stage1,
        tmp_path / "ckpt-0",
        run_id="run:test:elo",
        config_sha256="sha256:cfg-test",
        corpus_slice_id="corpus_slice:test",
        base_model_pointer="tiny.qwen.shape@base",
    )
    assert manifest["checkpoint_kind"] == "stage1_boundary"
    assert manifest["step"] == 3

    # Reset model + optimizer; load checkpoint; continue.
    torch.manual_seed(9999)  # different seed - resume must not depend on it
    adapter2 = TinyQwenShapeAdapter()
    adapter2.load()
    plan2 = adapter2.freeze_policy("elo_first_last")
    trainer2 = ELOTrainer(ELOConfig(seed=1234, learning_rate=1e-3))
    stage1_b = trainer2.build_stage1_model(adapter2.model(), plan2)

    trainer2.load_boundary_checkpoint(stage1_b, tmp_path / "ckpt-0")
    assert stage1_b.step_idx == 3

    # Compare trainable params: must be byte-equal.
    snap_a = {n: p.detach().clone() for n, p in stage1.model.named_parameters() if p.requires_grad}
    snap_b = {n: p.detach().clone() for n, p in stage1_b.model.named_parameters() if p.requires_grad}
    assert set(snap_a.keys()) == set(snap_b.keys())
    for k in snap_a:
        assert torch.allclose(snap_a[k], snap_b[k], atol=1e-6), f"resume drift on {k}"


def test_checkpoint_records_freeze_plan(tmp_path):
    torch.manual_seed(1234)
    adapter = TinyQwenShapeAdapter()
    adapter.load()
    plan = adapter.freeze_policy("elo_first_last")
    trainer = ELOTrainer()
    stage1 = trainer.build_stage1_model(adapter.model(), plan)
    manifest = trainer.save_boundary_checkpoint(
        stage1,
        tmp_path / "ckpt",
        run_id="run:test",
        config_sha256="sha256:cfg",
    )
    assert manifest["freeze_plan"]["policy_name"] == "elo_first_last"
    assert 0 in manifest["freeze_plan"]["trainable_layer_indices"]
    assert manifest["freeze_plan"]["trainable_layer_indices"][-1] == adapter.cfg.num_hidden_layers - 1


def test_loss_is_finite_and_decreasing_over_short_run():
    """ELO Stage 1 must actually train. We don't claim convergence on a
    random target, just that loss is finite and the boundary parameters
    move so loss does not stay constant.
    """
    torch.manual_seed(1234)
    cfg = TinyQwenConfig(vocab_size=64, hidden_size=24, num_hidden_layers=4, num_attention_heads=2, num_key_value_heads=1, intermediate_size=48, head_dim=12)
    adapter = TinyQwenShapeAdapter(cfg)
    adapter.load()
    plan = adapter.freeze_policy("elo_first_last")
    trainer = ELOTrainer(ELOConfig(seed=1234, learning_rate=5e-3))
    stage1 = trainer.build_stage1_model(adapter.model(), plan)

    input_ids, labels = _deterministic_batch(cfg, seq=12)
    losses = []
    for _ in range(20):
        rec = trainer.train_step(stage1, input_ids, labels)
        assert torch.isfinite(torch.tensor(rec.loss)), rec
        losses.append(rec.loss)
    # Loss at step 19 should be lower than at step 0 by a non-trivial margin
    # since we're training on the same batch repeatedly.
    assert losses[-1] < losses[0] * 0.95, f"loss not improving: {losses[0]:.4f} -> {losses[-1]:.4f}"


def test_stage2_merge_round_trip():
    torch.manual_seed(0)
    cfg = TinyQwenConfig(num_hidden_layers=4)
    adapter = TinyQwenShapeAdapter(cfg)
    adapter.load()
    plan = adapter.freeze_policy("elo_first_last")
    trainer = ELOTrainer(ELOConfig(learning_rate=1e-2))
    stage1 = trainer.build_stage1_model(adapter.model(), plan)

    input_ids, labels = _deterministic_batch(cfg)
    for _ in range(5):
        trainer.train_step(stage1, input_ids, labels)

    base = TinyQwenForCausalLM(cfg)  # fresh
    # Merge boundary.
    trainer.merge_boundary_checkpoint(base, stage1)

    # Layer-0 weights of base must now equal stage1's.
    base_w = dict(base.named_parameters())
    s1_w = dict(stage1.model.named_parameters())
    layer0_keys = [k for k in base_w if k.startswith("model.layers.0.")]
    assert layer0_keys, "no layer-0 keys"
    for k in layer0_keys:
        assert torch.allclose(base_w[k], s1_w[k], atol=1e-6), f"merge missed {k}"
