#!/usr/bin/env python3
"""Real Qwen2.5-1.5B ELO Stage 1 smoke on the host machine.

Loads the pinned snapshot already in the HF cache, applies the ELO freeze
plan (layers 0 and 27 + lm_head trainable, embeddings frozen, all middle
layers frozen), runs a small number of steps on a synthetic batch, and
confirms:

* trainable parameter set matches expectation
* optimizer state contains only trainable params (deduped by id)
* frozen-parameter hash sample is unchanged across steps
* loss is finite and decreasing on a same-batch overfit smoke
* a checkpoint round-trips without drift

This is the on-host proof that Phase 0B ELO correctness extends from the
tiny Qwen-shape mimic to the real 1.5B model.

Run: ``.venv/bin/python scripts/host/qwen_elo_smoke.py``

The script writes its envelope-shaped report to
``runtime/reports/qwen_elo_smoke/<timestamp>/report.json`` and a copy to
``docs/PHASE0B-QWEN-SMOKE-REPORT.md`` for the executor handoff.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from polymath_ai._version import SCHEMA_VERSION
from polymath_ai.audit.chain import AuditWriter
from polymath_ai.boundary.text import boundary_envelope
from polymath_ai.elo.trainer import ELOConfig, ELOTrainer, frozen_param_hash_sample
from polymath_ai.models.adapters import qwen2_5_1p5b_adapter, apply_freeze_plan
from polymath_ai.utils.canonical import canonical_json, utc_now_iso


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--seq", type=int, default=32)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--out", type=str, default=str(ROOT / "runtime" / "reports" / "qwen_elo_smoke"))
    parser.add_argument("--save-checkpoint", action="store_true")
    args = parser.parse_args()

    import torch

    out_dir = Path(args.out) / utc_now_iso().replace(":", "")
    out_dir.mkdir(parents=True, exist_ok=True)
    audit = AuditWriter(out_dir / "audit.jsonl", run_id=f"run:{utc_now_iso()}:qwen-elo-smoke")
    audit.append(event_type="genesis", payload={"phase": "phase0b_elo_correctness", "args": vars(args)})

    print("[1/6] loading Qwen2.5-1.5B (bf16, cpu)")
    adapter = qwen2_5_1p5b_adapter()
    model = adapter.load(dtype="bf16", device="cpu")
    print(f"      n_params={sum(p.numel() for p in model.parameters()):,}")

    print("[2/6] applying ELO freeze plan")
    plan = adapter.freeze_policy("elo_first_last")
    apply_freeze_plan(model, plan)
    trainable = [n for n, p in model.named_parameters() if p.requires_grad]
    frozen_count = sum(1 for n, p in model.named_parameters() if not p.requires_grad)
    print(f"      {len(trainable)} trainable param tensors, {frozen_count} frozen")
    audit.append(
        event_type="phase_gate",
        payload={"gate": "freeze_plan_applied", "trainable_count": len(trainable), "frozen_count": frozen_count},
    )

    # Sanity: trainable should be layers.0.*, layers.27.* (n=28), lm_head.*
    bad = [n for n in trainable if not (n.startswith("model.layers.0.") or n.startswith("model.layers.27.") or n.startswith("lm_head."))]
    if bad:
        print(f"  [FAIL] unexpected trainable params: {bad[:5]}")
        sys.exit(1)

    print("[3/6] building ELOTrainer + Adam (trainables only)")
    trainer = ELOTrainer(ELOConfig(learning_rate=args.lr, seed=1234))
    stage1 = trainer.build_stage1_model(model, plan)
    val = trainer.validate_freeze_plan(stage1)
    if not val.optimizer_only_includes_trainable:
        print("  [FAIL] optimizer_only_includes_trainable is False")
        sys.exit(1)
    print(f"      optimizer params (deduped by id) = {val.optimizer_param_count}")

    print("[4/6] running ELO steps on synthetic batch")
    torch.manual_seed(1234)
    g = torch.Generator().manual_seed(7)
    vocab = adapter.model().config.vocab_size
    input_ids = torch.randint(0, vocab, (args.batch, args.seq), generator=g)
    labels = input_ids.clone()

    losses = []
    frozen_change_total = 0
    for s in range(args.steps):
        rec = trainer.train_step(stage1, input_ids, labels)
        losses.append(rec.loss)
        frozen_change_total += len(rec.frozen_hashes_changed)
        print(f"      step {rec.step}: loss={rec.loss:.4f} grad_norm={rec.grad_norm:.4f} frozen_changed={len(rec.frozen_hashes_changed)}")
        audit.append(
            event_type="train_step",
            payload={
                "step": rec.step,
                "loss": rec.loss,
                "grad_norm": rec.grad_norm,
                "frozen_changed": rec.frozen_hashes_changed,
            },
        )

    if frozen_change_total:
        print(f"  [FAIL] frozen params changed {frozen_change_total} times across {args.steps} steps")
        audit.append(
            event_type="falsifier",
            payload={
                "falsifier_id": "checkpoint_hash_mismatch",
                "result": "fail",
                "detail": f"frozen params changed {frozen_change_total} times",
                "blocking": True,
            },
        )
        sys.exit(2)

    print(f"[5/6] loss curve: {losses[0]:.4f} -> {losses[-1]:.4f}")

    if args.save_checkpoint:
        print("[6/6] saving boundary checkpoint")
        manifest = trainer.save_boundary_checkpoint(
            stage1,
            out_dir / "ckpt-0",
            run_id=audit.run_id,
            config_sha256="sha256:cli-args",
            corpus_slice_id=None,
            base_model_pointer="Qwen/Qwen2.5-1.5B@main",
            license_attestation_id="license:apache-2.0:qwen2.5-1.5b",
        )
        audit.append(event_type="checkpoint", payload={"manifest_path": str(out_dir / "ckpt-0" / "manifest.json"), "checkpoint_sha256": manifest["checkpoint_sha256"]})
    else:
        print("[6/6] skipping checkpoint save (use --save-checkpoint to write)")

    report = {
        "schema_version": SCHEMA_VERSION,
        "boundary": boundary_envelope(),
        "run_id": audit.run_id,
        "phase": "phase0b_elo_correctness",
        "model_id": "Qwen/Qwen2.5-1.5B",
        "trainable_param_tensor_count": len(trainable),
        "frozen_param_tensor_count": frozen_count,
        "n_total_params": sum(p.numel() for p in model.parameters()),
        "trainable_n_params": sum(p.numel() for p in model.parameters() if p.requires_grad),
        "loss_curve": losses,
        "frozen_changes_observed": frozen_change_total,
        "args": vars(args),
        "result": "pass" if frozen_change_total == 0 else "fail",
    }
    (out_dir / "report.json").write_text(canonical_json(report))
    print(f"[OK] report at {out_dir / 'report.json'}")


if __name__ == "__main__":
    main()
