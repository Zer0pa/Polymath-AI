#!/usr/bin/env python3
"""Export C5 full-decoder component metadata from a real Gemma 4 E4B snapshot.

This is a bounded bridge from the historical full-model source into the C5 QA
runtime contract. It does not copy raw model tensors into git. The output
directory must be outside the repository and contains metadata-only manifests
that prove the model, LM-head/unembedding identity, tokenizer alignment, and
rank-16 adapter site policy needed by ``--run-c5-qa-predict``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


MODEL_ID = "google/gemma-4-E4B"
REVISION = "7aa32e6889efd6300124851b164f8b364314c3d8"
DECODER_MANIFEST_SCHEMA = "polymath_c5_full_decoder_manifest_v1"
ADAPTER_SITE_POLICY_SCHEMA = "polymath_c5_adapter_site_policy_v1"
EXPORT_REPORT_SCHEMA = "polymath_c5_full_decoder_component_pack_export_v1"
DECODER_KIND = "full_gemma4_text_decoder_logits"
VOCAB_SIZE = 262_144
HIDDEN_SIZE = 2_560
NUM_LAYERS = 42
ADAPTER_RANK = 16
EMBED_TOKENS_KEY = "model.language_model.embed_tokens.weight"
LAYER_PREFIX_TEMPLATE = "model.language_model.layers.{layer_index}."
TOKENIZER_VOCAB_HEX_SHA256 = (
    "0e43bafc96037bed92fabea31282eb10ad094ec921748a58f6be10dbf9796f74"
)
TOKENIZER_MERGES_HEX_SHA256 = (
    "6c99efe1bfe6b70092d531cad0a57278182652a2380aa5fb33e99d4e4eeb905f"
)
SUPPORTED_ADAPTER_SITES = {
    "post_layer1_residual": {
        "decoder_layer_index": 1,
        "description": "rank-16 adapter consumes and updates the layer-1 residual stream",
    },
    "post_layer0_residual": {
        "decoder_layer_index": 0,
        "description": "rank-16 adapter consumes and updates the layer-0 residual stream",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-safetensors", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--candidate-adapter-sha")
    parser.add_argument("--stable-baseline-sha")
    parser.add_argument("--adapter-site", default="post_layer1_residual")
    parser.add_argument("--adapter-layer-index", type=int)
    parser.add_argument(
        "--tokenizer-vocab-sha",
        default=TOKENIZER_VOCAB_HEX_SHA256,
    )
    parser.add_argument(
        "--tokenizer-merges-sha",
        default=TOKENIZER_MERGES_HEX_SHA256,
    )
    parser.add_argument("--print-schema", action="store_true")
    return parser.parse_args()


def is_sha256(value: str | None) -> bool:
    return bool(value and re.fullmatch(r"[0-9a-f]{64}", value))


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def find_git_root(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def fail_closed(
    first_missing_green_field: str,
    blockers: list[str],
    *,
    status: str = "blocked",
    extra: dict[str, Any] | None = None,
) -> int:
    payload: dict[str, Any] = {
        "schema_version": EXPORT_REPORT_SCHEMA,
        "status": status,
        "first_missing_green_field": first_missing_green_field,
        "blockers": blockers,
        "raw_boundary_proof": {
            "raw_model_payload_copied_to_git": False,
            "raw_tensor_payload_copied_to_git": False,
            "output_is_metadata_only": True,
        },
    }
    if extra:
        payload.update(extra)
    print(json.dumps(payload, sort_keys=True))
    return 2


def schema_contract() -> dict[str, Any]:
    return {
        "schema_version": EXPORT_REPORT_SCHEMA,
        "exporter": "export_c5_full_decoder_component_pack.py",
        "model_id": MODEL_ID,
        "hf_revision": REVISION,
        "accepted_input": {
            "model_safetensors": "outside-git single safetensors snapshot",
            "output_dir": "outside-git metadata-only component pack directory",
        },
        "decoder_manifest_schema": {
            "schema_version": DECODER_MANIFEST_SCHEMA,
            "model_id": MODEL_ID,
            "hf_revision": REVISION,
            "decoder": {
                "kind": DECODER_KIND,
                "hidden_size": HIDDEN_SIZE,
                "num_hidden_layers": NUM_LAYERS,
                "vocab_size": VOCAB_SIZE,
                "logits_vocabulary_size": VOCAB_SIZE,
            },
            "lm_head": {
                "embedded_in_decoder": True,
                "source": "tied_word_embeddings",
                "tensor_key": EMBED_TOKENS_KEY,
                "required_shape": [VOCAB_SIZE, HIDDEN_SIZE],
                "required_dtype": "bf16|f16|f32",
            },
        },
        "adapter_site_policy_schema": {
            "schema_version": ADAPTER_SITE_POLICY_SCHEMA,
            "model_id": MODEL_ID,
            "adapter_rank": ADAPTER_RANK,
            "supported_adapter_sites": sorted(SUPPORTED_ADAPTER_SITES),
            "input_shape": [1, ADAPTER_RANK, HIDDEN_SIZE],
            "output_shape": [1, ADAPTER_RANK, HIDDEN_SIZE],
            "bridge_mse_is_c5_loss": False,
        },
    }


def normalize_torch_dtype(dtype: Any) -> str:
    value = str(dtype).replace("torch.", "")
    if value in {"bfloat16", "bf16"}:
        return "bf16"
    if value in {"float16", "half", "f16"}:
        return "f16"
    if value in {"float32", "float", "f32"}:
        return "f32"
    return value


def tensor_bytes_for_identity(tensor: Any, dtype: str) -> bytes:
    import torch

    contiguous = tensor.detach().cpu().contiguous()
    if dtype in {"bf16", "f16"}:
        return contiguous.view(torch.int16).numpy().astype("<i2", copy=False).tobytes()
    if dtype == "f32":
        return contiguous.to(torch.float32).numpy().astype("<f4", copy=False).tobytes()
    return contiguous.numpy().tobytes()


def build_layer_inventory(keys: list[str]) -> list[dict[str, Any]]:
    layers: list[dict[str, Any]] = []
    for layer_index in range(NUM_LAYERS):
        prefix = LAYER_PREFIX_TEMPLATE.format(layer_index=layer_index)
        matching = sorted(key for key in keys if key.startswith(prefix))
        if not matching:
            raise ValueError(f"decoder_layer_{layer_index}_weights_missing")
        layers.append(
            {
                "layer_index": layer_index,
                "key_prefix": prefix,
                "key_count": len(matching),
            }
        )
    return layers


def build_lm_head_identity(
    *,
    dtype: str,
    tensor_sha256: str,
    tokenizer_vocab_sha256: str,
    tokenizer_merges_sha256: str,
) -> dict[str, Any]:
    return {
        "embedded_in_decoder": True,
        "source": "tied_word_embeddings",
        "tensor_key": EMBED_TOKENS_KEY,
        "dtype": dtype,
        "shape": [VOCAB_SIZE, HIDDEN_SIZE],
        "sha256": tensor_sha256,
        "vocab_size": VOCAB_SIZE,
        "logits_vocabulary_alignment": {
            "tokenizer_vocab_hex_tsv_sha256": tokenizer_vocab_sha256,
            "tokenizer_merges_hex_tsv_sha256": tokenizer_merges_sha256,
            "logits_vocab_size": VOCAB_SIZE,
        },
    }


def build_decoder_manifest(
    *,
    source_model_path: Path,
    source_model_sha256: str,
    source_model_size_bytes: int,
    layers: list[dict[str, Any]],
    lm_head_identity: dict[str, Any],
    tokenizer_vocab_sha256: str,
    tokenizer_merges_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_version": DECODER_MANIFEST_SCHEMA,
        "model_id": MODEL_ID,
        "hf_revision": REVISION,
        "component_pack_kind": "manifest_backed_source_safetensors",
        "decoder": {
            "kind": DECODER_KIND,
            "hidden_size": HIDDEN_SIZE,
            "num_hidden_layers": NUM_LAYERS,
            "vocab_size": VOCAB_SIZE,
            "logits_vocabulary_size": VOCAB_SIZE,
            "layer_inventory": layers,
        },
        "source_model_safetensors": {
            "path": str(source_model_path),
            "sha256": source_model_sha256,
            "size_bytes": source_model_size_bytes,
        },
        "tokenizer_identity": {
            "vocab_hex_tsv_sha256": tokenizer_vocab_sha256,
            "merges_hex_tsv_sha256": tokenizer_merges_sha256,
        },
        "lm_head": lm_head_identity,
        "runtime_contract": {
            "runner_flag": "--run-c5-qa-predict",
            "required_output_rows": [
                "record_id",
                "prediction",
                "finite_nonnegative_loss",
                "confidence_in_0_1",
            ],
            "candidate_train_loss_source": "same real logits/training objective; bridge MSE is forbidden",
        },
    }


def build_adapter_site_policy(
    *,
    candidate_adapter_sha256: str,
    stable_baseline_adapter_sha256: str,
    adapter_site: str,
    adapter_layer_index: int | None = None,
) -> dict[str, Any]:
    if adapter_site not in SUPPORTED_ADAPTER_SITES:
        raise ValueError("adapter_site_unknown")
    default_layer = SUPPORTED_ADAPTER_SITES[adapter_site]["decoder_layer_index"]
    layer_index = default_layer if adapter_layer_index is None else adapter_layer_index
    if not 0 <= layer_index < NUM_LAYERS:
        raise ValueError("adapter_layer_index_invalid")
    return {
        "schema_version": ADAPTER_SITE_POLICY_SCHEMA,
        "model_id": MODEL_ID,
        "hf_revision": REVISION,
        "adapter_rank": ADAPTER_RANK,
        "decoder_layer_index": layer_index,
        "adapter_site": adapter_site,
        "adapter_site_description": SUPPORTED_ADAPTER_SITES[adapter_site]["description"],
        "input_shape": [1, ADAPTER_RANK, HIDDEN_SIZE],
        "output_shape": [1, ADAPTER_RANK, HIDDEN_SIZE],
        "candidate_adapter_sha256": candidate_adapter_sha256,
        "stable_baseline_adapter_sha256": stable_baseline_adapter_sha256,
        "bridge_mse_is_c5_loss": False,
        "qa_loss_source": "teacher_forced_answer_token_nll_from_full_decoder_logits",
    }


def validate_args(args: argparse.Namespace) -> tuple[int | None, list[str]]:
    blockers: list[str] = []
    if args.model_safetensors is None:
        blockers.append("model_safetensors_arg_missing")
    elif not args.model_safetensors.is_file():
        blockers.append("model_safetensors_missing")

    if args.out is None:
        blockers.append("out_arg_missing")
    else:
        repo_root = find_git_root(Path(__file__).resolve())
        if repo_root and is_under(args.out, repo_root):
            blockers.append("output_dir_inside_git_worktree")

    if not is_sha256(args.candidate_adapter_sha):
        blockers.append("candidate_adapter_sha_invalid")
    if not is_sha256(args.stable_baseline_sha):
        blockers.append("stable_baseline_sha_invalid")
    if not is_sha256(args.tokenizer_vocab_sha):
        blockers.append("tokenizer_vocab_sha_invalid")
    if not is_sha256(args.tokenizer_merges_sha):
        blockers.append("tokenizer_merges_sha_invalid")
    if args.adapter_site not in SUPPORTED_ADAPTER_SITES:
        blockers.append("adapter_site_unknown")
    if args.adapter_layer_index is not None and not 0 <= args.adapter_layer_index < NUM_LAYERS:
        blockers.append("adapter_layer_index_invalid")

    if blockers:
        return fail_closed(blockers[0], blockers), blockers
    return None, blockers


def export_component_pack(args: argparse.Namespace) -> int:
    status_code, blockers = validate_args(args)
    if status_code is not None:
        return status_code

    assert args.model_safetensors is not None
    assert args.out is not None
    try:
        from safetensors import safe_open
    except ImportError:
        return fail_closed("safetensors_python_package_missing", ["safetensors_python_package_missing"])

    try:
        with safe_open(args.model_safetensors, framework="pt", device="cpu") as model:
            keys = list(model.keys())
            if EMBED_TOKENS_KEY not in keys:
                return fail_closed("embed_tokens_weight_missing", ["embed_tokens_weight_missing"])
            try:
                layers = build_layer_inventory(keys)
            except ValueError as error:
                return fail_closed(str(error), [str(error)])

            embed_tokens = model.get_tensor(EMBED_TOKENS_KEY)
            shape = list(embed_tokens.shape)
            dtype = normalize_torch_dtype(embed_tokens.dtype)
            if shape != [VOCAB_SIZE, HIDDEN_SIZE]:
                return fail_closed(
                    "embed_tokens_shape_mismatch",
                    ["embed_tokens_shape_mismatch"],
                    extra={"observed_shape": shape},
                )
            if dtype not in {"bf16", "f16", "f32"}:
                return fail_closed(
                    "embed_tokens_dtype_unsupported",
                    ["embed_tokens_dtype_unsupported"],
                    extra={"observed_dtype": dtype},
                )
            lm_head_sha256 = sha256_bytes(tensor_bytes_for_identity(embed_tokens, dtype))
    except Exception as error:  # noqa: BLE001 - exporter must convert runtime failures into metadata.
        return fail_closed(
            "model_safetensors_read_failed",
            ["model_safetensors_read_failed"],
            extra={"error": str(error)},
        )

    source_model_sha256 = sha256_file(args.model_safetensors)
    lm_head_identity = build_lm_head_identity(
        dtype=dtype,
        tensor_sha256=lm_head_sha256,
        tokenizer_vocab_sha256=args.tokenizer_vocab_sha,
        tokenizer_merges_sha256=args.tokenizer_merges_sha,
    )
    decoder_manifest = build_decoder_manifest(
        source_model_path=args.model_safetensors,
        source_model_sha256=source_model_sha256,
        source_model_size_bytes=args.model_safetensors.stat().st_size,
        layers=layers,
        lm_head_identity=lm_head_identity,
        tokenizer_vocab_sha256=args.tokenizer_vocab_sha,
        tokenizer_merges_sha256=args.tokenizer_merges_sha,
    )
    adapter_site_policy = build_adapter_site_policy(
        candidate_adapter_sha256=args.candidate_adapter_sha,
        stable_baseline_adapter_sha256=args.stable_baseline_sha,
        adapter_site=args.adapter_site,
        adapter_layer_index=args.adapter_layer_index,
    )

    args.out.mkdir(parents=True, exist_ok=True)
    decoder_manifest_path = args.out / "decoder_manifest.json"
    adapter_site_policy_path = args.out / "adapter_site_policy.json"
    write_json(decoder_manifest_path, decoder_manifest)
    write_json(adapter_site_policy_path, adapter_site_policy)

    report = {
        "schema_version": EXPORT_REPORT_SCHEMA,
        "status": "created",
        "model_id": MODEL_ID,
        "hf_revision": REVISION,
        "output_dir": str(args.out),
        "artifacts": {
            "decoder_manifest": {
                "path": str(decoder_manifest_path),
                "sha256": sha256_file(decoder_manifest_path),
            },
            "adapter_site_policy": {
                "path": str(adapter_site_policy_path),
                "sha256": sha256_file(adapter_site_policy_path),
            },
        },
        "source_model_safetensors_sha256": source_model_sha256,
        "lm_head_unembedding_sha256": lm_head_sha256,
        "raw_boundary_proof": {
            "raw_model_payload_copied_to_git": False,
            "raw_tensor_payload_copied_to_git": False,
            "output_is_metadata_only": True,
        },
        "nonclaims": [
            "no logits emitted",
            "no prediction JSONL emitted",
            "no C5 pass",
            "no loss or confidence fabricated",
            "no bridge MSE relabeled as C5 loss",
        ],
    }
    report_path = args.out / "export_report.json"
    write_json(report_path, report)
    print(
        json.dumps(
            {
                "status": "created",
                "out": str(args.out),
                "decoder_manifest_sha256": report["artifacts"]["decoder_manifest"]["sha256"],
                "adapter_site_policy_sha256": report["artifacts"]["adapter_site_policy"]["sha256"],
                "export_report_sha256": sha256_file(report_path),
            },
            sort_keys=True,
        )
    )
    return 0


def main() -> int:
    args = parse_args()
    if args.print_schema:
        print(json.dumps(schema_contract(), indent=2, sort_keys=True))
        return 0
    return export_component_pack(args)


if __name__ == "__main__":
    raise SystemExit(main())
