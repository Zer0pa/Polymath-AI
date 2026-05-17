#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import torch


MODEL_ID = "google/gemma-4-E4B"
REVISION = "7aa32e6889efd6300124851b164f8b364314c3d8"
TOKENS = 8 * 128
HIDDEN = 2560
RANK = 4
SCALE = 1.0 / RANK


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def read_f32(path: Path, count: int) -> np.ndarray:
    values = np.fromfile(path, dtype="<f4")
    if values.size != count:
        raise ValueError(f"{path} has {values.size} f32 values; expected {count}")
    return values.reshape(TOKENS, HIDDEN)


def read_u8(path: Path, count: int) -> np.ndarray:
    values = np.fromfile(path, dtype="u1")
    if values.size != count:
        raise ValueError(f"{path} has {values.size} u8 values; expected {count}")
    return values


def write_f32(path: Path, values: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(np.asarray(values, dtype="<f4").tobytes())


def deterministic_adapter(seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    adapter_a = rng.normal(0.0, 1.0e-4, size=(HIDDEN, RANK)).astype("<f4")
    adapter_b = rng.normal(0.0, 1.0e-4, size=(RANK, HIDDEN)).astype("<f4")
    return adapter_a, adapter_b


def torch_reference(
    layer0: np.ndarray,
    layer1_target: np.ndarray,
    mask: np.ndarray,
    adapter_a_np: np.ndarray,
    adapter_b_np: np.ndarray,
    learning_rate: float,
) -> dict[str, Any]:
    layer0_t = torch.tensor(layer0, dtype=torch.float32)
    target_t = torch.tensor(layer1_target, dtype=torch.float32)
    mask_t = torch.tensor(mask.astype(np.float32).reshape(TOKENS, 1), dtype=torch.float32)
    adapter_a = torch.tensor(adapter_a_np, dtype=torch.float32, requires_grad=True)
    adapter_b = torch.tensor(adapter_b_np, dtype=torch.float32, requires_grad=True)

    z = layer0_t @ adapter_a
    output = layer0_t + (SCALE * (z @ adapter_b))
    diff = (output - target_t) * mask_t
    active_tokens = int(mask.sum())
    if active_tokens == 0:
        raise ValueError("attention mask has zero active tokens")
    loss = 0.5 * (diff * diff).sum() / float(active_tokens * HIDDEN)
    loss.backward()

    grad_a = adapter_a.grad.detach().cpu().numpy().astype("<f4")
    grad_b = adapter_b.grad.detach().cpu().numpy().astype("<f4")
    updated_a = (adapter_a.detach() - (learning_rate * adapter_a.grad.detach())).cpu().numpy().astype("<f4")
    updated_b = (adapter_b.detach() - (learning_rate * adapter_b.grad.detach())).cpu().numpy().astype("<f4")
    return {
        "loss": float(loss.detach().cpu()),
        "active_tokens": active_tokens,
        "grad_a": grad_a,
        "grad_b": grad_b,
        "updated_a": updated_a,
        "updated_b": updated_b,
    }


def manifest_entry(path: Path, base: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(base)),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a G5/G6 rank-4 adapter training fixture and PyTorch oracle."
    )
    parser.add_argument("--layer0-phone-output", required=True, type=Path)
    parser.add_argument("--layer1-reference-output", required=True, type=Path)
    parser.add_argument("--attention-mask", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--seed", default=20260517, type=int)
    parser.add_argument("--learning-rate", default=1.0e-2, type=float)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    fixture_input = args.out / "fixture/input/layer0_output.f32.bin"
    fixture_target = args.out / "fixture/target/layer1_output.f32.bin"
    fixture_mask = args.out / "fixture/input/attention_mask.u8.bin"
    fixture_input.parent.mkdir(parents=True, exist_ok=True)
    fixture_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.layer0_phone_output, fixture_input)
    shutil.copyfile(args.layer1_reference_output, fixture_target)
    shutil.copyfile(args.attention_mask, fixture_mask)

    layer0 = read_f32(fixture_input, TOKENS * HIDDEN)
    layer1_target = read_f32(fixture_target, TOKENS * HIDDEN)
    mask = read_u8(fixture_mask, TOKENS)
    adapter_a, adapter_b = deterministic_adapter(args.seed)

    checkpoint_dir = args.out / "checkpoint"
    write_f32(checkpoint_dir / "adapter_a.f32.bin", adapter_a)
    write_f32(checkpoint_dir / "adapter_b.f32.bin", adapter_b)

    reference = torch_reference(
        layer0,
        layer1_target,
        mask,
        adapter_a,
        adapter_b,
        args.learning_rate,
    )
    write_f32(args.out / "reference/adapter_grad_a.f32.bin", reference["grad_a"])
    write_f32(args.out / "reference/adapter_grad_b.f32.bin", reference["grad_b"])
    write_f32(args.out / "reference/checkpoint/adapter_a.f32.bin", reference["updated_a"])
    write_f32(args.out / "reference/checkpoint/adapter_b.f32.bin", reference["updated_b"])

    contract = {
        "schema_version": "gemma4_adapter_training_fixture_v1",
        "model_id": MODEL_ID,
        "revision": REVISION,
        "trainable_scope": "post_layer0_rank4_residual_adapter",
        "rank": RANK,
        "adapter_scale": SCALE,
        "tokens": TOKENS,
        "hidden_size": HIDDEN,
        "loss": "0.5 * masked_mean_squared_error(output, target)",
        "input": "phone G3 layer0 output",
        "target": "RunPod PyTorch layer1 output",
        "seed": args.seed,
        "learning_rate": args.learning_rate,
        "active_tokens": reference["active_tokens"],
        "loss_half_mse": reference["loss"],
    }
    (args.out / "fixture/contract.json").write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    paths = [path for path in args.out.rglob("*") if path.is_file()]
    manifest = {
        "schema_version": "gemma4_adapter_training_artifact_manifest_v1",
        "contract": contract,
        "files": [manifest_entry(path, args.out) for path in sorted(paths)],
    }
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
