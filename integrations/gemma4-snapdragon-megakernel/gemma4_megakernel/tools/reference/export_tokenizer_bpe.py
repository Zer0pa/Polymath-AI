#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def token_hex(token: str) -> str:
    return token.encode("utf-8").hex()


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Gemma tokenizer.json BPE tables for native C++ loading.")
    parser.add_argument("--tokenizer-json", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    data: dict[str, Any] = json.loads(args.tokenizer_json.read_text(encoding="utf-8"))
    model = data["model"]
    if model.get("type") != "BPE":
        raise ValueError(f"expected BPE tokenizer model, got {model.get('type')}")
    args.out.mkdir(parents=True, exist_ok=True)
    vocab_path = args.out / "vocab.hex.tsv"
    merges_path = args.out / "merges.hex.tsv"

    with vocab_path.open("w", encoding="utf-8") as handle:
        for token, token_id in sorted(model["vocab"].items(), key=lambda item: item[1]):
            handle.write(f"{token_hex(token)}\t{int(token_id)}\n")

    with merges_path.open("w", encoding="utf-8") as handle:
        for rank, pair in enumerate(model["merges"]):
            if isinstance(pair, str):
                left, right = pair.split(" ", 1)
            else:
                left, right = pair
            handle.write(f"{token_hex(left)}\t{token_hex(right)}\t{rank}\n")

    manifest = {
        "schema_version": "gemma4_bpe_export_v1",
        "source_tokenizer_json": str(args.tokenizer_json),
        "source_tokenizer_json_sha256": sha256_file(args.tokenizer_json),
        "model_type": model.get("type"),
        "byte_fallback": bool(model.get("byte_fallback")),
        "fuse_unk": bool(model.get("fuse_unk")),
        "normalizer": data.get("normalizer"),
        "pre_tokenizer": data.get("pre_tokenizer"),
        "post_processor": data.get("post_processor"),
        "vocab_size": len(model["vocab"]),
        "merge_count": len(model["merges"]),
        "files": {
            "vocab.hex.tsv": {
                "bytes": vocab_path.stat().st_size,
                "sha256": sha256_file(vocab_path),
            },
            "merges.hex.tsv": {
                "bytes": merges_path.stat().st_size,
                "sha256": sha256_file(merges_path),
            },
        },
    }
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
