#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch
from transformers import AutoModelForCausalLM


MODEL_ID = "google/gemma-4-E4B"
REVISION = "7aa32e6889efd6300124851b164f8b364314c3d8"
HIDDEN = 2560
PLE_DIM = 256
RANK = 4
SCALE = 1.0 / RANK


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def read_u32(path: Path, count: int | None = None) -> np.ndarray:
    values = np.fromfile(path, dtype="<u4")
    if count is not None and values.size != count:
        raise ValueError(f"{path} has {values.size} u32 values; expected {count}")
    return values


def read_u8(path: Path, count: int) -> np.ndarray:
    values = np.fromfile(path, dtype="u1")
    if values.size != count:
        raise ValueError(f"{path} has {values.size} u8 values; expected {count}")
    return values


def read_f32(path: Path, count: int) -> np.ndarray:
    values = np.fromfile(path, dtype="<f4")
    if values.size != count:
        raise ValueError(f"{path} has {values.size} f32 values; expected {count}")
    return values.astype(np.float32, copy=False)


def write_f32(path: Path, values: np.ndarray | torch.Tensor) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if torch.is_tensor(values):
        data = values.detach().cpu().contiguous().to(torch.float32).numpy()
    else:
        data = np.asarray(values, dtype=np.float32)
    path.write_bytes(data.astype("<f4", copy=False).tobytes())


def locate_text_model(model: torch.nn.Module) -> torch.nn.Module:
    for dotted_name in ("language_model", "text_model", "model.language_model", "model.text_model"):
        candidate: Any = model
        for part in dotted_name.split("."):
            candidate = getattr(candidate, part, None)
            if candidate is None:
                break
        if candidate is not None and hasattr(candidate, "layers"):
            return candidate
    for module_name, module in model.named_modules():
        if module_name.endswith("language_model") and hasattr(module, "layers"):
            return module
    raise RuntimeError("could not locate Gemma text model layers")


class StopAfterLayer1(RuntimeError):
    pass


def capture_two_layer_stream(
    text_model: torch.nn.Module,
    input_ids: torch.Tensor,
    attention_mask: torch.Tensor,
    position_ids: torch.Tensor,
) -> dict[str, torch.Tensor]:
    captured: dict[str, torch.Tensor] = {}
    handles: list[Any] = []

    def pre_hook(name: str):
        def hook(_module: torch.nn.Module, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
            captured[f"{name}_input"] = args[0].detach()
            value = args[1] if len(args) > 1 else kwargs.get("per_layer_input")
            if value is not None:
                captured[f"{name}_per_layer_input"] = value.detach()
        return hook

    def post_layer0(_module: torch.nn.Module, _args: tuple[Any, ...], output: Any) -> None:
        captured["layer0_output"] = output.detach() if torch.is_tensor(output) else output[0].detach()

    def post_layer1(_module: torch.nn.Module, _args: tuple[Any, ...], output: Any) -> None:
        captured["layer1_output"] = output.detach() if torch.is_tensor(output) else output[0].detach()
        raise StopAfterLayer1()

    handles.append(text_model.layers[0].register_forward_pre_hook(pre_hook("layer0"), with_kwargs=True))
    handles.append(text_model.layers[1].register_forward_pre_hook(pre_hook("layer1"), with_kwargs=True))
    handles.append(text_model.layers[0].register_forward_hook(post_layer0))
    handles.append(text_model.layers[1].register_forward_hook(post_layer1))
    try:
        try:
            text_model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                position_ids=position_ids,
                use_cache=False,
            )
        except StopAfterLayer1:
            pass
    finally:
        for handle in handles:
            handle.remove()

    required = [
        "layer0_input",
        "layer0_per_layer_input",
        "layer0_output",
        "layer1_per_layer_input",
        "layer1_output",
    ]
    missing = [name for name in required if name not in captured]
    if missing:
        raise RuntimeError(f"failed to capture required tensors: {missing}")
    return captured


def adapter_reference(
    layer0: np.ndarray,
    layer1_target: np.ndarray,
    mask: np.ndarray,
    checkpoint: Path,
    learning_rate: float,
) -> dict[str, Any]:
    tokens = int(mask.size)
    layer0_t = torch.tensor(layer0.reshape(tokens, HIDDEN), dtype=torch.float32)
    target_t = torch.tensor(layer1_target.reshape(tokens, HIDDEN), dtype=torch.float32)
    mask_t = torch.tensor(mask.astype(np.float32).reshape(tokens, 1), dtype=torch.float32)
    adapter_a = torch.tensor(
        read_f32(checkpoint / "adapter_a.f32.bin", HIDDEN * RANK).reshape(HIDDEN, RANK),
        dtype=torch.float32,
        requires_grad=True,
    )
    adapter_b = torch.tensor(
        read_f32(checkpoint / "adapter_b.f32.bin", RANK * HIDDEN).reshape(RANK, HIDDEN),
        dtype=torch.float32,
        requires_grad=True,
    )
    z = layer0_t @ adapter_a
    output = layer0_t + (SCALE * (z @ adapter_b))
    diff = (output - target_t) * mask_t
    active_tokens = int(mask.sum())
    if active_tokens == 0:
        raise ValueError("attention mask has zero active tokens")
    loss = 0.5 * (diff * diff).sum() / float(active_tokens * HIDDEN)
    loss.backward()
    updated_a = adapter_a.detach() - (learning_rate * adapter_a.grad.detach())
    updated_b = adapter_b.detach() - (learning_rate * adapter_b.grad.detach())
    return {
        "loss": float(loss.detach().cpu()),
        "active_tokens": active_tokens,
        "grad_a": adapter_a.grad.detach().cpu().numpy().astype("<f4"),
        "grad_b": adapter_b.grad.detach().cpu().numpy().astype("<f4"),
        "updated_a": updated_a.cpu().numpy().astype("<f4"),
        "updated_b": updated_b.cpu().numpy().astype("<f4"),
    }


def manifest_entry(path: Path, base: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(base)),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create the RunPod PyTorch oracle for the G8 streamed-corpus distillation update."
    )
    parser.add_argument("--snapshot-dir", required=True, type=Path)
    parser.add_argument("--token-cache", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--seq", default=128, type=int)
    parser.add_argument("--learning-rate", default=1.0e-2, type=float)
    args = parser.parse_args()

    input_ids_np = read_u32(args.token_cache / "input_ids.u32.bin")
    if input_ids_np.size % args.seq != 0:
        raise ValueError("input_ids size is not divisible by sequence length")
    cases = input_ids_np.size // args.seq
    tokens = cases * args.seq
    attention_mask_np = read_u8(args.token_cache / "attention_mask.u8.bin", tokens)
    position_ids_np = read_u32(args.token_cache / "position_ids.u32.bin", tokens)

    input_ids = torch.tensor(input_ids_np.reshape(cases, args.seq).astype(np.int64), dtype=torch.long)
    attention_mask = torch.tensor(attention_mask_np.reshape(cases, args.seq).astype(np.int64), dtype=torch.long)
    position_ids = torch.tensor(position_ids_np.reshape(cases, args.seq).astype(np.int64), dtype=torch.long)

    model = AutoModelForCausalLM.from_pretrained(
        args.snapshot_dir,
        torch_dtype=torch.bfloat16,
        device_map="cpu",
        low_cpu_mem_usage=True,
        trust_remote_code=False,
    )
    model.eval()
    text_model = locate_text_model(model)
    with torch.no_grad():
        captured = capture_two_layer_stream(text_model, input_ids, attention_mask, position_ids)

    args.out.mkdir(parents=True, exist_ok=True)
    write_f32(args.out / "generated/layer_input.f32.bin", captured["layer0_input"])
    write_f32(args.out / "generated/per_layer_input_layer0.f32.bin", captured["layer0_per_layer_input"])
    write_f32(args.out / "generated/per_layer_input_layer1.f32.bin", captured["layer1_per_layer_input"])
    write_f32(args.out / "layer0_output.f32.bin", captured["layer0_output"])
    write_f32(args.out / "layer1_output.f32.bin", captured["layer1_output"])

    adapter = adapter_reference(
        captured["layer0_output"].detach().to(torch.float32).cpu().numpy().astype(np.float32),
        captured["layer1_output"].detach().to(torch.float32).cpu().numpy().astype(np.float32),
        attention_mask_np,
        args.checkpoint,
        args.learning_rate,
    )
    write_f32(args.out / "adapter_grad_a.f32.bin", adapter["grad_a"])
    write_f32(args.out / "adapter_grad_b.f32.bin", adapter["grad_b"])
    write_f32(args.out / "checkpoint/adapter_a.f32.bin", adapter["updated_a"])
    write_f32(args.out / "checkpoint/adapter_b.f32.bin", adapter["updated_b"])

    manifest = {
        "schema_version": "gemma4_streamed_distill_reference_v1",
        "model_id": MODEL_ID,
        "revision": REVISION,
        "snapshot_dir": str(args.snapshot_dir),
        "token_cache": str(args.token_cache),
        "checkpoint": str(args.checkpoint),
        "case_count": cases,
        "seq": args.seq,
        "hidden_size": HIDDEN,
        "ple_dim": PLE_DIM,
        "rank": RANK,
        "learning_rate": args.learning_rate,
        "active_tokens": adapter["active_tokens"],
        "loss_half_mse": adapter["loss"],
        "files": [manifest_entry(path, args.out) for path in sorted(args.out.rglob("*")) if path.is_file()],
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "created", "out": str(args.out), "cases": cases}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
