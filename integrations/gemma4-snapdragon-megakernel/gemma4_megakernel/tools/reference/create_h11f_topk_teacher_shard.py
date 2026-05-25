#!/usr/bin/env python3
"""Create an H11-F precomputed full-teacher top-k shard."""
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
TELEMETRY_OBJECTIVE = "full_gemma_teacher_topk_kl_v1"
OBJECTIVE_CONTRACT = (
    "precomputed_full_teacher_topk_to_phone_tied_embedding_student_kl_no_runtime_teacher_service"
)
TEACHER_PROVENANCE = "runpod_precomputed_full_gemma4_topk_from_p13c_phone_defined_tokens"
TEACHER_SCOPE = "full_gemma4_e4b_causal_lm_logits"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_u32(path: Path) -> np.ndarray:
    return np.fromfile(path, dtype="<u4")


def read_u8(path: Path, expected: int) -> np.ndarray:
    values = np.fromfile(path, dtype="u1")
    if values.size != expected:
        raise ValueError(f"{path} has {values.size} values; expected {expected}")
    return values


def write_u32(path: Path, values: np.ndarray | torch.Tensor) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    array = values.detach().cpu().numpy() if torch.is_tensor(values) else values
    path.write_bytes(np.asarray(array, dtype="<u4").tobytes())


def write_f32(path: Path, values: np.ndarray | torch.Tensor) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    array = values.detach().cpu().numpy() if torch.is_tensor(values) else values
    path.write_bytes(np.asarray(array, dtype="<f4").tobytes())


def write_u8(path: Path, values: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(np.asarray(values, dtype="u1").tobytes())


def manifest_entry(path: Path, base: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(base)),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-dir", required=True, type=Path)
    parser.add_argument("--token-cache", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--split", required=True)
    parser.add_argument("--top-k", default=8, type=int)
    parser.add_argument("--seq", default=128, type=int)
    parser.add_argument(
        "--max-cases",
        default=None,
        type=int,
        help="Optionally limit the number of sequences read from the token cache for bounded smokes.",
    )
    args = parser.parse_args()

    input_ids_np = read_u32(args.token_cache / "input_ids.u32.bin")
    if input_ids_np.size % args.seq != 0:
        raise ValueError("input_ids size is not divisible by sequence length")
    source_cases = input_ids_np.size // args.seq
    cases = source_cases
    if args.max_cases is not None:
        if args.max_cases <= 0:
            raise ValueError("--max-cases must be positive")
        cases = min(source_cases, args.max_cases)
    tokens = cases * args.seq
    source_tokens = source_cases * args.seq
    input_ids_np = input_ids_np[:tokens]
    attention_mask_np = read_u8(args.token_cache / "attention_mask.u8.bin", source_tokens)[:tokens]
    loss_mask_np = read_u8(args.token_cache / "loss_mask.u8.bin", source_tokens)[:tokens]
    labels_np = read_u32(args.token_cache / "labels.u32.bin")[:tokens]
    position_ids_np = read_u32(args.token_cache / "position_ids.u32.bin")[:tokens]
    if labels_np.size != tokens or position_ids_np.size != tokens:
        raise ValueError("labels or position_ids has invalid length after max-cases slicing")

    input_ids = torch.tensor(input_ids_np.reshape(cases, args.seq).astype(np.int64))
    attention_mask = torch.tensor(attention_mask_np.reshape(cases, args.seq).astype(np.int64))
    position_ids = torch.tensor(position_ids_np.reshape(cases, args.seq).astype(np.int64))

    model = AutoModelForCausalLM.from_pretrained(
        args.snapshot_dir,
        torch_dtype=torch.bfloat16,
        device_map="cpu",
        low_cpu_mem_usage=True,
        trust_remote_code=False,
    )
    model.eval()
    with torch.no_grad():
        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            position_ids=position_ids,
            use_cache=False,
        )
        log_probs = torch.log_softmax(outputs.logits.to(torch.float32), dim=-1)
        top_log_probs, top_ids = torch.topk(log_probs, k=args.top_k, dim=-1)
        top_probs = torch.exp(top_log_probs)
        conditional_probs = top_probs / top_probs.sum(dim=-1, keepdim=True).clamp_min(1.0e-30)

    args.out.mkdir(parents=True, exist_ok=True)
    write_u32(args.out / "topk_token_ids.u32.bin", top_ids.reshape(tokens, args.top_k))
    write_f32(
        args.out / "topk_probabilities.f32.bin",
        conditional_probs.reshape(tokens, args.top_k),
    )
    write_u8(args.out / "loss_mask.u8.bin", loss_mask_np)
    write_u32(args.out / "labels.u32.bin", labels_np)

    manifest = {
        "schema_version": "phase11_h11f_topk_teacher_shard_v1",
        "model_id": MODEL_ID,
        "revision": REVISION,
        "telemetry_objective": TELEMETRY_OBJECTIVE,
        "objective_contract": OBJECTIVE_CONTRACT,
        "teacher_provenance": TEACHER_PROVENANCE,
        "teacher_scope": TEACHER_SCOPE,
        "student_scope": "two_layer_phone_runtime_rank4_residual_adapter",
        "objective": "conditional_topk_kl_over_full_teacher_topk",
        "probability_normalization": "conditional_within_topk",
        "full_teacher_logits_used": True,
        "split": args.split,
        "top_k": args.top_k,
        "sequence_length": args.seq,
        "source_sequence_count": source_cases,
        "sequence_count": cases,
        "token_count": tokens,
        "max_cases": args.max_cases,
        "loss_tokens": int(loss_mask_np.sum()),
        "token_cache": {
            "input_ids_sha256": sha256_file(args.token_cache / "input_ids.u32.bin"),
            "attention_mask_sha256": sha256_file(args.token_cache / "attention_mask.u8.bin"),
            "loss_mask_sha256": sha256_file(args.token_cache / "loss_mask.u8.bin"),
            "labels_sha256": sha256_file(args.token_cache / "labels.u32.bin"),
            "position_ids_sha256": sha256_file(args.token_cache / "position_ids.u32.bin"),
        },
        "metric_predeclared": {
            "heldout_primary": "mean_student_teacher_top1_probability",
            "heldout_guardrail": "student_teacher_top1_agreement_non_regression",
            "train_signal": "loss_topk_kl_decrease",
        },
        "files": [
            manifest_entry(args.out / "topk_token_ids.u32.bin", args.out),
            manifest_entry(args.out / "topk_probabilities.f32.bin", args.out),
            manifest_entry(args.out / "loss_mask.u8.bin", args.out),
            manifest_entry(args.out / "labels.u32.bin", args.out),
        ],
    }
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "created", "out": str(args.out), "split": args.split}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
