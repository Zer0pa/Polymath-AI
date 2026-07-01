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
INTERMEDIATE_SIZE = 10_240
NUM_ATTENTION_HEADS = 8
NUM_KEY_VALUE_HEADS = 2
HEAD_DIM = 256
SMALL_INPUT_SIZE = 256
ADAPTER_RANK = 16
RMS_NORM_EPS = 1.0e-6
ROPE_THETA = 10_000.0
FINAL_LOGIT_SOFTCAP = 30.0
ACTIVATION = "gelu_pytorch_tanh"
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
TENSOR_ROLE_SPECS = {
    "input_layernorm": {
        "suffix": "input_layernorm.weight",
        "shape": [HIDDEN_SIZE],
    },
    "self_attn_q_proj": {
        "suffix": "self_attn.q_proj.weight",
        "shape": [NUM_ATTENTION_HEADS * HEAD_DIM, HIDDEN_SIZE],
    },
    "self_attn_k_proj": {
        "suffix": "self_attn.k_proj.weight",
        "shape": [NUM_KEY_VALUE_HEADS * HEAD_DIM, HIDDEN_SIZE],
    },
    "self_attn_v_proj": {
        "suffix": "self_attn.v_proj.weight",
        "shape": [NUM_KEY_VALUE_HEADS * HEAD_DIM, HIDDEN_SIZE],
    },
    "self_attn_o_proj": {
        "suffix": "self_attn.o_proj.weight",
        "shape": [HIDDEN_SIZE, NUM_ATTENTION_HEADS * HEAD_DIM],
    },
    "self_attn_q_norm": {
        "suffix": "self_attn.q_norm.weight",
        "shape": [NUM_KEY_VALUE_HEADS * HEAD_DIM],
    },
    "self_attn_k_norm": {
        "suffix": "self_attn.k_norm.weight",
        "shape": [NUM_KEY_VALUE_HEADS * HEAD_DIM],
    },
    "post_attention_layernorm": {
        "suffix": "post_attention_layernorm.weight",
        "shape": [HIDDEN_SIZE],
    },
    "pre_feedforward_layernorm": {
        "suffix": "pre_feedforward_layernorm.weight",
        "shape": [HIDDEN_SIZE],
    },
    "mlp_gate_proj": {
        "suffix": "mlp.gate_proj.weight",
        "shape": [INTERMEDIATE_SIZE, HIDDEN_SIZE],
    },
    "mlp_up_proj": {
        "suffix": "mlp.up_proj.weight",
        "shape": [INTERMEDIATE_SIZE, HIDDEN_SIZE],
    },
    "mlp_down_proj": {
        "suffix": "mlp.down_proj.weight",
        "shape": [HIDDEN_SIZE, INTERMEDIATE_SIZE],
    },
    "post_feedforward_layernorm": {
        "suffix": "post_feedforward_layernorm.weight",
        "shape": [HIDDEN_SIZE],
    },
    "per_layer_input_gate": {
        "suffix": "per_layer_input_gate.weight",
        "shape": [SMALL_INPUT_SIZE, HIDDEN_SIZE],
    },
    "per_layer_projection": {
        "suffix": "per_layer_projection.weight",
        "shape": [HIDDEN_SIZE, SMALL_INPUT_SIZE],
    },
    "post_per_layer_input_norm": {
        "suffix": "post_per_layer_input_norm.weight",
        "shape": [HIDDEN_SIZE],
    },
    "layer_scalar": {
        "suffix": "layer_scalar",
        "shape": [1],
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


def sha256_file_range(path: Path, start: int, length: int) -> str:
    hasher = hashlib.sha256()
    remaining = length
    with path.open("rb") as handle:
        handle.seek(start)
        while remaining:
            chunk = handle.read(min(1024 * 1024, remaining))
            if not chunk:
                raise ValueError("safetensors_tensor_range_truncated")
            hasher.update(chunk)
            remaining -= len(chunk)
    return hasher.hexdigest()


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
        "runtime_dependencies": {
            "python": "stdlib only for safetensors metadata/range parsing",
            "torch_required": False,
            "safetensors_python_package_required": False,
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
            "source_model_safetensors": {
                "required_fields": ["path", "sha256", "size_bytes"],
            },
            "architecture_config": build_architecture_config(),
            "tensor_role_inventory": {
                "layer_roles": sorted(TENSOR_ROLE_SPECS),
                "per_layer_attention_layout": [
                    "query_heads",
                    "key_value_heads",
                    "head_dim",
                    "query_to_key_value_group_size",
                ],
                "per_role_required_fields": [
                    "key",
                    "dtype",
                    "shape",
                    "data_offsets",
                    "absolute_data_offsets",
                    "byte_length",
                ],
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


def normalize_safetensors_dtype(dtype: Any) -> str:
    value = str(dtype).replace("torch.", "").upper()
    if value in {"BF16", "BFloat16".upper()}:
        return "bf16"
    if value in {"F16", "FLOAT16", "HALF"}:
        return "f16"
    if value in {"F32", "FLOAT32", "FLOAT"}:
        return "f32"
    return value.lower()


def read_safetensors_header(path: Path) -> tuple[dict[str, Any], int]:
    with path.open("rb") as handle:
        header_len_bytes = handle.read(8)
        if len(header_len_bytes) != 8:
            raise ValueError("safetensors_header_length_missing")
        header_len = int.from_bytes(header_len_bytes, "little", signed=False)
        if header_len <= 0:
            raise ValueError("safetensors_header_length_invalid")
        if header_len > 256 * 1024 * 1024:
            raise ValueError("safetensors_header_length_unbounded")
        header_bytes = handle.read(header_len)
        if len(header_bytes) != header_len:
            raise ValueError("safetensors_header_truncated")
    try:
        header = json.loads(header_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("safetensors_header_json_invalid") from error
    if not isinstance(header, dict):
        raise ValueError("safetensors_header_not_object")
    return header, 8 + header_len


def tensor_entry(header: dict[str, Any], key: str) -> dict[str, Any]:
    entry = header.get(key)
    if not isinstance(entry, dict):
        raise ValueError(f"{key}_missing")
    dtype = normalize_safetensors_dtype(entry.get("dtype"))
    shape = entry.get("shape")
    offsets = entry.get("data_offsets")
    if not isinstance(shape, list) or not all(isinstance(value, int) for value in shape):
        raise ValueError(f"{key}_shape_invalid")
    if (
        not isinstance(offsets, list)
        or len(offsets) != 2
        or not all(isinstance(value, int) for value in offsets)
        or offsets[0] < 0
        or offsets[1] < offsets[0]
    ):
        raise ValueError(f"{key}_data_offsets_invalid")
    return {
        "dtype": dtype,
        "shape": shape,
        "data_offsets": offsets,
    }


def shape_mismatch_message(role: str, expected: Any, actual: Any) -> str:
    return (
        f"{role}_shape_mismatch"
        f"_expected_{json.dumps(expected, separators=(',', ':'))}"
        f"_actual_{json.dumps(actual, separators=(',', ':'))}"
    )


def validate_tensor_role_shape(
    *,
    role: str,
    base_role: str,
    shape: list[int],
    expected_shape: list[int],
) -> None:
    if base_role in {"self_attn_q_proj", "self_attn_k_proj", "self_attn_v_proj"}:
        if len(shape) != 2 or shape[1] != HIDDEN_SIZE or shape[0] <= 0 or shape[0] % HEAD_DIM:
            raise ValueError(
                shape_mismatch_message(
                    role,
                    {"rank": 2, "dim1": HIDDEN_SIZE, "dim0_multiple_of": HEAD_DIM},
                    shape,
                )
            )
        return
    if base_role == "self_attn_o_proj":
        if len(shape) != 2 or shape[0] != HIDDEN_SIZE or shape[1] <= 0 or shape[1] % HEAD_DIM:
            raise ValueError(
                shape_mismatch_message(
                    role,
                    {"rank": 2, "dim0": HIDDEN_SIZE, "dim1_multiple_of": HEAD_DIM},
                    shape,
                )
            )
        return
    if base_role in {"self_attn_q_norm", "self_attn_k_norm"}:
        if len(shape) != 1 or shape[0] <= 0 or shape[0] % HEAD_DIM:
            raise ValueError(
                shape_mismatch_message(
                    role,
                    {"rank": 1, "dim0_multiple_of": HEAD_DIM},
                    shape,
                )
            )
        return
    if shape != expected_shape:
        raise ValueError(shape_mismatch_message(role, expected_shape, shape))


def tensor_role_entry(
    header: dict[str, Any],
    *,
    key: str,
    base_role: str,
    expected_shape: list[int],
    tensor_data_start: int,
    file_size: int,
    role: str,
) -> dict[str, Any]:
    entry = tensor_entry(header, key)
    shape = entry["shape"]
    dtype = entry["dtype"]
    validate_tensor_role_shape(
        role=role,
        base_role=base_role,
        shape=shape,
        expected_shape=expected_shape,
    )
    if dtype not in {"bf16", "f16", "f32"}:
        raise ValueError(f"{role}_dtype_unsupported")
    start, stop = entry["data_offsets"]
    if file_size < tensor_data_start + stop:
        raise ValueError(f"{role}_range_exceeds_file_size")
    return {
        "key": key,
        "dtype": dtype,
        "shape": shape,
        "data_offsets": [start, stop],
        "absolute_data_offsets": [tensor_data_start + start, tensor_data_start + stop],
        "byte_length": stop - start,
    }


def attention_layout_for_layer(layer_index: int, roles: dict[str, Any]) -> dict[str, Any]:
    q_shape = roles["self_attn_q_proj"]["shape"]
    k_shape = roles["self_attn_k_proj"]["shape"]
    v_shape = roles["self_attn_v_proj"]["shape"]
    o_shape = roles["self_attn_o_proj"]["shape"]
    q_norm_shape = roles["self_attn_q_norm"]["shape"]
    k_norm_shape = roles["self_attn_k_norm"]["shape"]
    query_heads = q_shape[0] // HEAD_DIM
    key_heads = k_shape[0] // HEAD_DIM
    value_heads = v_shape[0] // HEAD_DIM
    output_heads = o_shape[1] // HEAD_DIM
    if key_heads != value_heads:
        raise ValueError(f"decoder_layer_{layer_index}_kv_head_shape_mismatch")
    if query_heads != output_heads:
        raise ValueError(f"decoder_layer_{layer_index}_q_o_head_shape_mismatch")
    if key_heads == 0 or query_heads == 0 or query_heads % key_heads:
        raise ValueError(f"decoder_layer_{layer_index}_attention_head_grouping_invalid")
    validate_attention_norm_shape(
        layer_index=layer_index,
        role_name="q_norm",
        norm_shape=q_norm_shape,
        q_proj_rows=q_shape[0],
        projected_rows=q_shape[0],
    )
    validate_attention_norm_shape(
        layer_index=layer_index,
        role_name="k_norm",
        norm_shape=k_norm_shape,
        q_proj_rows=q_shape[0],
        projected_rows=k_shape[0],
    )
    return {
        "query_heads": query_heads,
        "key_value_heads": key_heads,
        "head_dim": HEAD_DIM,
        "query_to_key_value_group_size": query_heads // key_heads,
        "q_proj_shape": q_shape,
        "k_proj_shape": k_shape,
        "v_proj_shape": v_shape,
        "o_proj_shape": o_shape,
        "q_norm_shape": q_norm_shape,
        "k_norm_shape": k_norm_shape,
    }


def validate_attention_norm_shape(
    *,
    layer_index: int,
    role_name: str,
    norm_shape: list[int],
    q_proj_rows: int,
    projected_rows: int,
) -> None:
    norm_width = norm_shape[0]
    expected_layout = {
        "rank": 1,
        "dim0_multiple_of": HEAD_DIM,
        "dim0_at_most_q_proj_dim0": True,
        "q_proj_dim0_multiple_of_dim0": True,
        "dim0_compatible_with_projection_dim0": True,
    }
    norm_tiles_query = norm_width <= q_proj_rows and q_proj_rows % norm_width == 0
    norm_matches_projection = (
        projected_rows % norm_width == 0 or norm_width % projected_rows == 0
    )
    if norm_tiles_query and norm_matches_projection:
        return
    raise ValueError(
        shape_mismatch_message(
            f"decoder_layer_{layer_index}_self_attn_{role_name}",
            expected_layout,
            norm_shape,
        )
    )


def build_architecture_config() -> dict[str, Any]:
    return {
        "num_hidden_layers": NUM_LAYERS,
        "hidden_size": HIDDEN_SIZE,
        "vocab_size": VOCAB_SIZE,
        "logits_vocabulary_size": VOCAB_SIZE,
        "intermediate_size": INTERMEDIATE_SIZE,
        "num_attention_heads": NUM_ATTENTION_HEADS,
        "num_key_value_heads": NUM_KEY_VALUE_HEADS,
        "head_dim": HEAD_DIM,
        "small_input_size": SMALL_INPUT_SIZE,
        "rms_norm_eps": RMS_NORM_EPS,
        "rope_theta": ROPE_THETA,
        "activation": ACTIVATION,
        "final_logit_softcap": FINAL_LOGIT_SOFTCAP,
        "dtype_policy": "bf16_f16_f32_metadata_only; runtime converts explicitly",
        "attention_layout_source": "tensor_role_inventory.per_layer_attention_layout",
        "materializes_full_bsv_logits": False,
    }


def build_tensor_role_inventory(
    header: dict[str, Any],
    *,
    tensor_data_start: int,
    file_size: int,
) -> dict[str, Any]:
    layers: list[dict[str, Any]] = []
    for layer_index in range(NUM_LAYERS):
        prefix = LAYER_PREFIX_TEMPLATE.format(layer_index=layer_index)
        roles: dict[str, Any] = {}
        for role, spec in TENSOR_ROLE_SPECS.items():
            key = prefix + str(spec["suffix"])
            roles[role] = tensor_role_entry(
                header,
                key=key,
                base_role=role,
                expected_shape=list(spec["shape"]),
                tensor_data_start=tensor_data_start,
                file_size=file_size,
                role=f"decoder_layer_{layer_index}_{role}",
            )
        layers.append(
            {
                "layer_index": layer_index,
                "roles": roles,
                "attention_layout": attention_layout_for_layer(layer_index, roles),
            }
        )

    embed_entry = tensor_role_entry(
        header,
        key=EMBED_TOKENS_KEY,
        base_role="embed_tokens",
        expected_shape=[VOCAB_SIZE, HIDDEN_SIZE],
        tensor_data_start=tensor_data_start,
        file_size=file_size,
        role="embed_tokens",
    )
    return {
        "format": "safetensors_header_metadata_only",
        "required_roles": sorted(TENSOR_ROLE_SPECS),
        "layers": layers,
        "token_embedding": embed_entry,
        "lm_head": {
            **embed_entry,
            "source": "tied_word_embeddings",
            "shares_storage_with": "token_embedding",
        },
    }


def extract_model_metadata(
    path: Path,
) -> tuple[list[dict[str, Any]], str, str, dict[str, Any], dict[str, Any]]:
    header, tensor_data_start = read_safetensors_header(path)
    keys = [key for key in header if key != "__metadata__"]
    if EMBED_TOKENS_KEY not in keys:
        raise ValueError("embed_tokens_weight_missing")
    layers = build_layer_inventory(keys)
    entry = tensor_entry(header, EMBED_TOKENS_KEY)
    shape = entry["shape"]
    dtype = entry["dtype"]
    if shape != [VOCAB_SIZE, HIDDEN_SIZE]:
        raise ValueError("embed_tokens_shape_mismatch")
    if dtype not in {"bf16", "f16", "f32"}:
        raise ValueError("embed_tokens_dtype_unsupported")
    start, stop = entry["data_offsets"]
    absolute_start = tensor_data_start + start
    length = stop - start
    if path.stat().st_size < tensor_data_start + stop:
        raise ValueError("embed_tokens_range_exceeds_file_size")
    tensor_sha256 = sha256_file_range(path, absolute_start, length)
    architecture_config = build_architecture_config()
    tensor_role_inventory = build_tensor_role_inventory(
        header,
        tensor_data_start=tensor_data_start,
        file_size=path.stat().st_size,
    )
    return layers, dtype, tensor_sha256, architecture_config, tensor_role_inventory


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
        "sha256_kind": "safetensors_raw_tensor_bytes",
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
    architecture_config: dict[str, Any],
    tensor_role_inventory: dict[str, Any],
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
        "architecture_config": architecture_config,
        "tensor_role_inventory": tensor_role_inventory,
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
        (
            layers,
            dtype,
            lm_head_sha256,
            architecture_config,
            tensor_role_inventory,
        ) = extract_model_metadata(args.model_safetensors)
    except Exception as error:  # noqa: BLE001 - exporter must convert runtime failures into metadata.
        first_missing = str(error) if str(error) else "model_safetensors_read_failed"
        return fail_closed(
            first_missing,
            [first_missing],
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
        architecture_config=architecture_config,
        tensor_role_inventory=tensor_role_inventory,
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
        "lm_head_unembedding_sha256_kind": "safetensors_raw_tensor_bytes",
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
