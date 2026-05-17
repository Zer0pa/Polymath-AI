#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from safetensors import safe_open
import torch


MODEL_ID = "google/gemma-4-E4B"
REVISION = "7aa32e6889efd6300124851b164f8b364314c3d8"
VOCAB_SIZE = 262_144
HIDDEN = 2_560
PLE_DIM = 256
NUM_LAYERS = 42


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def write_bf16(path: Path, tensor: torch.Tensor) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = tensor.detach().cpu().contiguous().to(torch.bfloat16).view(torch.int16).numpy()
    path.write_bytes(data.astype("<i2", copy=False).tobytes())


def write_f32(path: Path, tensor: torch.Tensor) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = tensor.detach().cpu().contiguous().to(torch.float32).numpy()
    path.write_bytes(data.astype("<f4", copy=False).tobytes())


def load_slice(model: Any, name: str, row_slice: slice, col_slice: slice) -> torch.Tensor:
    sliced = model.get_slice(name)
    return sliced[row_slice, col_slice]


def file_row(path: Path, description: str, rows: int, cols: int, dtype: str) -> dict[str, Any]:
    return {
        "path": path.name,
        "description": description,
        "rows": rows,
        "cols": cols,
        "dtype": dtype,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export immutable Gemma 4 assets needed for phone-native token-to-hidden generation."
    )
    parser.add_argument("--model-safetensors", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--layers", nargs="+", default=["0", "1"])
    args = parser.parse_args()

    layers = [int(value) for value in args.layers]
    if layers != [0, 1]:
        raise ValueError("the current G8 runtime expects exactly layers 0 and 1")

    args.out.mkdir(parents=True, exist_ok=True)
    with safe_open(args.model_safetensors, framework="pt", device="cpu") as model:
        embed_tokens = model.get_tensor("model.language_model.embed_tokens.weight")
        ple_norm = model.get_tensor("model.language_model.per_layer_projection_norm.weight")

        write_bf16(args.out / "embed_tokens.bf16.bin", embed_tokens)
        write_f32(args.out / "ple_projection_norm.f32.bin", ple_norm)
        for layer in layers:
            start = layer * PLE_DIM
            stop = start + PLE_DIM
            write_bf16(args.out / f"ple_token_layer{layer}.bf16.bin",
                       load_slice(model, "model.language_model.embed_tokens_per_layer.weight",
                                  slice(None), slice(start, stop)))
            write_bf16(args.out / f"ple_projection_layer{layer}.bf16.bin",
                       load_slice(model, "model.language_model.per_layer_model_projection.weight",
                                  slice(start, stop), slice(None)))

    files = [
        file_row(args.out / "embed_tokens.bf16.bin", "scaled later by bf16(sqrt(hidden_size))", VOCAB_SIZE, HIDDEN, "bf16"),
        file_row(args.out / "ple_projection_norm.f32.bin", "RMSNorm weight shared by PLE projection slices", 1, PLE_DIM, "f32"),
    ]
    for layer in layers:
        files.append(file_row(args.out / f"ple_token_layer{layer}.bf16.bin",
                              f"embed_tokens_per_layer slice for layer {layer}, scaled later by sqrt(PLE_DIM)",
                              VOCAB_SIZE, PLE_DIM, "bf16"))
        files.append(file_row(args.out / f"ple_projection_layer{layer}.bf16.bin",
                              f"per_layer_model_projection output rows for layer {layer}",
                              PLE_DIM, HIDDEN, "bf16"))

    manifest = {
        "schema_version": "gemma4_streamed_training_assets_v1",
        "model_id": MODEL_ID,
        "revision": REVISION,
        "source_model_safetensors": str(args.model_safetensors),
        "source_model_safetensors_sha256": sha256_file(args.model_safetensors),
        "layers": layers,
        "hidden_size": HIDDEN,
        "hidden_size_per_layer_input": PLE_DIM,
        "num_hidden_layers": NUM_LAYERS,
        "scales": {
            "embed_tokens": "bf16_round(sqrt(2560))",
            "embed_tokens_per_layer": 16.0,
            "per_layer_model_projection": "1/sqrt(2560)",
            "per_layer_input_scale": "1/sqrt(2)",
        },
        "files": files,
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "created", "out": str(args.out), "files": len(files)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
