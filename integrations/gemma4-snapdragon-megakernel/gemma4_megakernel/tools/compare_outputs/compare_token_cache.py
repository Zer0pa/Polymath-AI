#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from transformers import AutoTokenizer


MODEL_ID = "google/gemma-4-E4B"
REVISION = "7aa32e6889efd6300124851b164f8b364314c3d8"


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def read_texts(path: Path) -> list[str]:
    return [line.rstrip("\n") for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare phone token cache against Transformers Gemma tokenizer.")
    parser.add_argument("--phone-cache", required=True, type=Path)
    parser.add_argument("--tokenizer-dir", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--seq", required=True, type=int)
    args = parser.parse_args()

    texts = read_texts(args.phone_cache / "selected_text.txt")
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer_dir)
    encoded = tokenizer(
        texts,
        padding="max_length",
        truncation=True,
        max_length=args.seq,
        return_tensors="np",
    )
    reference_ids = encoded["input_ids"].astype("<u4")
    reference_mask = encoded["attention_mask"].astype("u1")
    phone_ids = np.fromfile(args.phone_cache / "input_ids.u32.bin", dtype="<u4").reshape(reference_ids.shape)
    phone_mask = np.fromfile(args.phone_cache / "attention_mask.u8.bin", dtype="u1").reshape(reference_mask.shape)

    id_mismatches = np.argwhere(phone_ids != reference_ids)
    mask_mismatches = np.argwhere(phone_mask != reference_mask)
    examples: list[dict[str, Any]] = []
    for row, col in id_mismatches[:10]:
        examples.append({
            "row": int(row),
            "col": int(col),
            "phone": int(phone_ids[row, col]),
            "reference": int(reference_ids[row, col]),
        })

    report = {
        "schema_version": "gemma4_token_cache_compare_v1",
        "status": "pass" if len(id_mismatches) == 0 and len(mask_mismatches) == 0 else "fail",
        "model_id": MODEL_ID,
        "revision": REVISION,
        "sequence_count": len(texts),
        "sequence_length": args.seq,
        "input_id_mismatch_count": int(len(id_mismatches)),
        "attention_mask_mismatch_count": int(len(mask_mismatches)),
        "input_ids_sha256": sha256_file(args.phone_cache / "input_ids.u32.bin"),
        "attention_mask_sha256": sha256_file(args.phone_cache / "attention_mask.u8.bin"),
        "selected_text_sha256": sha256_file(args.phone_cache / "selected_text.txt"),
        "mismatch_examples": examples,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
