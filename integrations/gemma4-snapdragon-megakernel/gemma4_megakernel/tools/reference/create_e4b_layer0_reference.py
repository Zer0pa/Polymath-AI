#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import torch
from huggingface_hub import snapshot_download
from safetensors.torch import save_file
from transformers import AutoModelForCausalLM, AutoTokenizer


MODEL_ID = "google/gemma-4-E4B"
REVISION = "7aa32e6889efd6300124851b164f8b364314c3d8"
PROMPTS = [
    "A native Gemma kernel must preserve tensor semantics.",
    "Compute 17 * 23, then explain the invariant.",
    "def rms_norm(x, w): return x * inv_rms(x) * w",
    "Qualcomm Adreno execution is measured, not assumed.",
    "Short prompt with punctuation: alpha, beta; gamma.",
    "The layer gate rejects random weights and CPU fallback.",
    "Matrix rows, rotary phases, and residuals must align.",
    "High entropy tokens: qzv 91827 :: @@ kernel parity.",
]


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def write_f32(path: Path, tensor: torch.Tensor) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(tensor.detach().to(torch.float32).cpu().contiguous().numpy().astype("<f4").tobytes())


def write_u32(path: Path, tensor: torch.Tensor) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(tensor.detach().to(torch.int64).cpu().contiguous().numpy().astype("<u4").tobytes())


def write_u8(path: Path, tensor: torch.Tensor) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(tensor.detach().to(torch.uint8).cpu().contiguous().numpy().astype("u1").tobytes())


def build_position_ids(attention_mask: torch.Tensor) -> torch.Tensor:
    position_ids = attention_mask.long().cumsum(dim=-1) - 1
    return position_ids.clamp(min=0)


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


class StopAfterTargetLayer(RuntimeError):
    pass


def capture_layer_io(
    text_model: torch.nn.Module,
    input_ids: torch.Tensor,
    attention_mask: torch.Tensor,
    position_ids: torch.Tensor,
    layer_index: int,
) -> tuple[torch.Tensor, torch.Tensor | None, torch.Tensor]:
    captured: dict[str, torch.Tensor | None] = {}
    layer = text_model.layers[layer_index]

    def pre_hook(_module: torch.nn.Module, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        captured["layer_input"] = args[0].detach()
        if len(args) > 1 and args[1] is not None:
            captured["per_layer_input"] = args[1].detach()
            return
        value = kwargs.get("per_layer_input")
        captured["per_layer_input"] = value.detach() if value is not None else None

    def post_hook(_module: torch.nn.Module, _args: tuple[Any, ...], output: Any) -> None:
        captured["layer_output"] = output.detach() if torch.is_tensor(output) else output[0].detach()
        raise StopAfterTargetLayer()

    pre_handle = layer.register_forward_pre_hook(pre_hook, with_kwargs=True)
    post_handle = layer.register_forward_hook(post_hook)
    try:
        try:
            text_model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                position_ids=position_ids,
                use_cache=False,
            )
        except StopAfterTargetLayer:
            pass
    finally:
        pre_handle.remove()
        post_handle.remove()

    if "layer_input" not in captured or "layer_output" not in captured:
        raise RuntimeError(f"failed to capture layer {layer_index} input/output")
    return (
        captured["layer_input"],  # type: ignore[return-value]
        captured.get("per_layer_input"),
        captured["layer_output"],  # type: ignore[return-value]
    )


def tensor_manifest(paths: list[Path], base: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(paths):
        rows.append({
            "path": str(path.relative_to(base)),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a Gemma 4 E4B single-layer reference pack on RunPod.")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--cache-dir", default="/workspace/models/gemma4_e4b", type=Path)
    parser.add_argument("--seq", default=128, type=int)
    parser.add_argument("--layer", default=0, type=int)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")

    snapshot_dir = Path(snapshot_download(
        repo_id=MODEL_ID,
        revision=REVISION,
        cache_dir=str(args.cache_dir),
        local_dir=str(args.cache_dir / "snapshot"),
        local_dir_use_symlinks=False,
    ))

    tokenizer = AutoTokenizer.from_pretrained(snapshot_dir)
    encoded = tokenizer(
        PROMPTS,
        padding="max_length",
        truncation=True,
        max_length=args.seq,
        return_tensors="pt",
    )
    input_ids = encoded["input_ids"]
    attention_mask = encoded["attention_mask"]
    position_ids = build_position_ids(attention_mask)

    model = AutoModelForCausalLM.from_pretrained(
        snapshot_dir,
        torch_dtype=torch.bfloat16,
        device_map="cpu",
        low_cpu_mem_usage=True,
        trust_remote_code=False,
    )
    model.eval()
    text_model = locate_text_model(model)

    with torch.no_grad():
        layer_input, per_layer_input, layer_output = capture_layer_io(
            text_model, input_ids, attention_mask, position_ids, args.layer
        )

    pack = args.out
    write_u32(pack / "input/input_ids.u32.bin", input_ids)
    write_u32(pack / "input/position_ids.u32.bin", position_ids)
    write_u8(pack / "input/attention_mask.u8.bin", attention_mask)
    write_f32(pack / "input/layer_input.f32.bin", layer_input)
    if per_layer_input is not None:
        write_f32(pack / "input/per_layer_input.f32.bin", per_layer_input)
    write_f32(pack / "reference/layer_output.f32.bin", layer_output)

    layer_state = {
        name: tensor.detach().cpu()
        for name, tensor in text_model.layers[args.layer].state_dict().items()
    }
    (pack / "weights").mkdir(parents=True, exist_ok=True)
    save_file(layer_state, str(pack / f"weights/layer{args.layer}.safetensors"))

    contract = {
        "schema_version": "gemma4_layer_gate_contract_v1",
        "model_id": MODEL_ID,
        "revision": REVISION,
        "layer_index": args.layer,
        "batch": 1,
        "case_count": len(PROMPTS),
        "seq": args.seq,
        "hidden_size": 2560,
        "heads": 8,
        "kv_heads": 2,
        "head_dim": 256,
        "intermediate_size": 10240,
        "rms_norm_epsilon": 1.0e-6,
        "activation": "gelu_pytorch_tanh",
        "comparison": {"metric": "cosine_per_non_pad_token", "p50_threshold": 0.99},
        "fixture_ids": [f"fixture_{index:02d}" for index in range(len(PROMPTS))],
    }
    (pack / "contract.json").write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest = {
        "schema_version": "layer_bundle_v1",
        "model_id": MODEL_ID,
        "revision": REVISION,
        "snapshot_dir": str(snapshot_dir),
        "prompts": [{"id": f"fixture_{index:02d}", "text": text} for index, text in enumerate(PROMPTS)],
        "tensors": tensor_manifest([path for path in pack.rglob("*") if path.is_file()], pack),
    }
    (pack / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (pack / "checksums").mkdir(parents=True, exist_ok=True)
    checksum_lines = [
        f"{row['sha256']}  {row['path']}"
        for row in manifest["tensors"]
        if row["path"] != "checksums/sha256.txt"
    ]
    (pack / "checksums/sha256.txt").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "created", "pack": str(pack), "files": len(manifest["tensors"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
