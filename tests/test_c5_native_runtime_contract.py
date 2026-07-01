from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "build/gemma4_megakernel_host/gemma4_layer_runner"
MODEL_ID = "google/gemma-4-E4B"
REVISION = "7aa32e6889efd6300124851b164f8b364314c3d8"
STABLE_SHA = "e0d1c66ac876c2b6fbbe9e88f1b02dd37201d8ffba10afcd44f1c558fc32f7c9"


pytestmark = pytest.mark.skipif(
    not RUNNER.exists(),
    reason="native gemma4_layer_runner build is required for C5 runtime contract tests",
)


ROLE_SHAPES = {
    "input_layernorm": ("input_layernorm.weight", [2560]),
    "self_attn_q_proj": ("self_attn.q_proj.weight", [2048, 2560]),
    "self_attn_k_proj": ("self_attn.k_proj.weight", [512, 2560]),
    "self_attn_v_proj": ("self_attn.v_proj.weight", [512, 2560]),
    "self_attn_o_proj": ("self_attn.o_proj.weight", [2560, 2048]),
    "self_attn_q_norm": ("self_attn.q_norm.weight", [512]),
    "self_attn_k_norm": ("self_attn.k_norm.weight", [512]),
    "post_attention_layernorm": ("post_attention_layernorm.weight", [2560]),
    "pre_feedforward_layernorm": ("pre_feedforward_layernorm.weight", [2560]),
    "mlp_gate_proj": ("mlp.gate_proj.weight", [10240, 2560]),
    "mlp_up_proj": ("mlp.up_proj.weight", [10240, 2560]),
    "mlp_down_proj": ("mlp.down_proj.weight", [2560, 10240]),
    "post_feedforward_layernorm": ("post_feedforward_layernorm.weight", [2560]),
    "per_layer_input_gate": ("per_layer_input_gate.weight", [256, 2560]),
    "per_layer_projection": ("per_layer_projection.weight", [2560, 256]),
    "post_per_layer_input_norm": ("post_per_layer_input_norm.weight", [2560]),
    "layer_scalar": ("layer_scalar", [1]),
}


def test_native_c5_runtime_validates_pack_then_stops_at_compute_kernel(tmp_path: Path) -> None:
    paths = _write_component_pack(tmp_path)

    result = _run_native(paths)

    assert result.returncode == 13
    payload = json.loads(result.stdout)
    assert payload["first_missing_green_field"] == "c5_full_decoder_streamed_compute_kernel_missing"
    assert payload["raw_boundary_proof"]["raw_payload_bytes_in_report"] is False
    assert payload["raw_boundary_proof"]["prediction_jsonl_written"] is False
    assert not paths["output_jsonl"].exists()


def test_native_c5_runtime_accepts_layer_variant_attention_layout(tmp_path: Path) -> None:
    def mutate_layer5_attention(key: str, entry: dict) -> None:
        if key.endswith("layers.5.self_attn.q_proj.weight"):
            entry.update({"shape": [2560, 2560]})
        if key.endswith("layers.5.self_attn.k_proj.weight"):
            entry.update({"shape": [256, 2560]})
        if key.endswith("layers.5.self_attn.v_proj.weight"):
            entry.update({"shape": [256, 2560]})
        if key.endswith("layers.5.self_attn.o_proj.weight"):
            entry.update({"shape": [2560, 2560]})

    paths = _write_component_pack(tmp_path, tensor_mutation=mutate_layer5_attention)

    result = _run_native(paths)
    payload = json.loads(result.stdout)

    assert result.returncode == 13
    assert payload["first_missing_green_field"] == "c5_full_decoder_streamed_compute_kernel_missing"
    assert payload["blockers"][:2] == [
        "c5_full_decoder_streamed_compute_kernel_missing",
        "c5_full_decoder_tensor_value_loader_missing",
    ]
    assert not paths["output_jsonl"].exists()


def test_native_c5_runtime_accepts_independent_k_norm_width(tmp_path: Path) -> None:
    paths = _write_component_pack(
        tmp_path,
        tensor_mutation=lambda key, entry: entry.update({"shape": [256]})
        if key.endswith("layers.0.self_attn.k_norm.weight")
        else None,
    )

    result = _run_native(paths)
    payload = json.loads(result.stdout)

    assert result.returncode == 13
    assert payload["first_missing_green_field"] == "c5_full_decoder_streamed_compute_kernel_missing"
    assert payload["blockers"][:2] == [
        "c5_full_decoder_streamed_compute_kernel_missing",
        "c5_full_decoder_tensor_value_loader_missing",
    ]
    assert not paths["output_jsonl"].exists()


def test_native_c5_runtime_rejects_incompatible_norm_width(tmp_path: Path) -> None:
    paths = _write_component_pack(
        tmp_path,
        tensor_mutation=lambda key, entry: entry.update({"shape": [768]})
        if key.endswith("layers.5.self_attn.q_norm.weight")
        else None,
    )

    result = _run_native(paths)
    payload = json.loads(result.stdout)

    assert result.returncode == 13
    assert "safetensors_attention_q_norm_shape_mismatch:5" in payload["blockers"]
    assert not paths["output_jsonl"].exists()


def test_native_c5_runtime_rejects_safetensors_dtype_mismatch(tmp_path: Path) -> None:
    paths = _write_component_pack(
        tmp_path,
        tensor_mutation=lambda key, entry: entry.update({"dtype": "I32"})
        if key.endswith("layers.0.self_attn.q_proj.weight")
        else None,
    )

    result = _run_native(paths)
    payload = json.loads(result.stdout)

    assert result.returncode == 13
    assert any("safetensors_tensor_dtype_unsupported" in item for item in payload["blockers"])
    assert not paths["output_jsonl"].exists()


def test_native_c5_runtime_rejects_safetensors_shape_mismatch(tmp_path: Path) -> None:
    paths = _write_component_pack(
        tmp_path,
        tensor_mutation=lambda key, entry: entry.update({"shape": [1]})
        if key.endswith("layers.0.self_attn.q_proj.weight")
        else None,
    )

    result = _run_native(paths)
    payload = json.loads(result.stdout)

    assert result.returncode == 13
    assert any("safetensors_tensor_shape_mismatch" in item for item in payload["blockers"])
    assert not paths["output_jsonl"].exists()


def test_native_c5_runtime_rejects_safetensors_offset_bounds(tmp_path: Path) -> None:
    paths = _write_component_pack(
        tmp_path,
        tensor_mutation=lambda key, entry: entry.update({"data_offsets": [0, 999_999]})
        if key.endswith("layers.0.self_attn.q_proj.weight")
        else None,
    )

    result = _run_native(paths)
    payload = json.loads(result.stdout)

    assert result.returncode == 13
    assert "safetensors_tensor_range_exceeds_file_size" in payload["blockers"]
    assert not paths["output_jsonl"].exists()


def _run_native(paths: dict[str, Path]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(RUNNER),
            "--run-c5-qa-predict",
            "--run-label",
            "unit",
            "--eval-point",
            "C5_after_C1",
            "--checkpoint-role",
            "candidate",
            "--checkpoint-payload",
            str(paths["checkpoint"]),
            "--checkpoint-sha256",
            str(paths["checkpoint_sha"]),
            "--heldout-qa-jsonl",
            str(paths["heldout"]),
            "--output-jsonl",
            str(paths["output_jsonl"]),
            "--tokenizer-dir",
            str(paths["tokenizer"]),
            "--decoder-component-pack",
            str(paths["pack"]),
            "--vocab-chunk-size",
            "4096",
            "--max-generation-tokens",
            "1",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _write_component_pack(
    tmp_path: Path,
    *,
    tensor_mutation=None,
) -> dict[str, Path]:
    pack = tmp_path / "component_pack"
    pack.mkdir()
    tokenizer = tmp_path / "tokenizer"
    tokenizer.mkdir()
    vocab = tokenizer / "vocab.hex.tsv"
    merges = tokenizer / "merges.hex.tsv"
    vocab.write_text("61\t0\n", encoding="utf-8")
    merges.write_text("61 62\t63\n", encoding="utf-8")
    checkpoint = tmp_path / "adapter_post_rank16.f32.bin"
    checkpoint.write_bytes(b"candidate")
    checkpoint_sha = _sha256_file(checkpoint)
    heldout = tmp_path / "phase_C1_test.qa.jsonl"
    heldout.write_text(
        json.dumps({"record_id": "r1", "question": "q", "answer": "a"}) + "\n",
        encoding="utf-8",
    )
    model = tmp_path / "model.safetensors"
    entries = _write_mock_safetensors(model, tensor_mutation=tensor_mutation)
    model_sha = _sha256_file(model)

    (pack / "decoder_manifest.json").write_text(
        json.dumps(
            _decoder_manifest(
                model=model,
                model_sha=model_sha,
                model_size=model.stat().st_size,
                vocab_sha=_sha256_file(vocab),
                merges_sha=_sha256_file(merges),
                entries=entries,
            ),
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (pack / "adapter_site_policy.json").write_text(
        json.dumps(
            {
                "schema_version": "polymath_c5_adapter_site_policy_v1",
                "model_id": MODEL_ID,
                "hf_revision": REVISION,
                "adapter_rank": 16,
                "decoder_layer_index": 1,
                "adapter_site": "post_layer1_residual",
                "input_shape": [1, 16, 2560],
                "output_shape": [1, 16, 2560],
                "candidate_adapter_sha256": checkpoint_sha,
                "stable_baseline_adapter_sha256": STABLE_SHA,
                "bridge_mse_is_c5_loss": False,
                "qa_loss_source": "teacher_forced_answer_token_nll_from_full_decoder_logits",
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return {
        "pack": pack,
        "tokenizer": tokenizer,
        "checkpoint": checkpoint,
        "checkpoint_sha": checkpoint_sha,
        "heldout": heldout,
        "output_jsonl": tmp_path / "predictions.jsonl",
    }


def _decoder_manifest(
    *,
    model: Path,
    model_sha: str,
    model_size: int,
    vocab_sha: str,
    merges_sha: str,
    entries: dict[str, dict],
) -> dict:
    return {
        "schema_version": "polymath_c5_full_decoder_manifest_v1",
        "model_id": MODEL_ID,
        "hf_revision": REVISION,
        "component_pack_kind": "manifest_backed_source_safetensors",
        "decoder": {
            "kind": "full_gemma4_text_decoder_logits",
            "hidden_size": 2560,
            "num_hidden_layers": 42,
            "vocab_size": 262144,
            "logits_vocabulary_size": 262144,
            "layer_inventory": [
                {
                    "layer_index": layer_index,
                    "key_prefix": f"model.language_model.layers.{layer_index}.",
                    "key_count": len(ROLE_SHAPES),
                }
                for layer_index in range(42)
            ],
        },
        "source_model_safetensors": {
            "path": str(model),
            "sha256": model_sha,
            "size_bytes": model_size,
        },
        "architecture_config": {
            "num_hidden_layers": 42,
            "hidden_size": 2560,
            "vocab_size": 262144,
            "logits_vocabulary_size": 262144,
            "intermediate_size": 10240,
            "num_attention_heads": 8,
            "num_key_value_heads": 2,
            "head_dim": 256,
            "small_input_size": 256,
            "rms_norm_eps": 1e-6,
            "rope_theta": 10000.0,
            "activation": "gelu_pytorch_tanh",
            "final_logit_softcap": 30.0,
            "materializes_full_bsv_logits": False,
        },
        "tensor_role_inventory": _tensor_role_inventory(entries),
        "tokenizer_identity": {
            "vocab_hex_tsv_sha256": vocab_sha,
            "merges_hex_tsv_sha256": merges_sha,
        },
        "lm_head": {
            "embedded_in_decoder": True,
            "source": "tied_word_embeddings",
            "tensor_key": "model.language_model.embed_tokens.weight",
            "dtype": entries["model.language_model.embed_tokens.weight"]["dtype"].lower(),
            "shape": [262144, 2560],
            "sha256": hashlib.sha256(b"abcd").hexdigest(),
            "sha256_kind": "safetensors_raw_tensor_bytes",
        },
        "runtime_contract": {
            "candidate_train_loss_source": "same real logits/training objective; bridge MSE is forbidden"
        },
    }


def _tensor_role_inventory(entries: dict[str, dict]) -> dict:
    layers = []
    for layer_index in range(42):
        prefix = f"model.language_model.layers.{layer_index}."
        roles = {}
        for role, (suffix, _shape) in ROLE_SHAPES.items():
            key = prefix + suffix
            entry = entries[key]
            roles[role] = {
                "key": key,
                "dtype": entry["dtype"].lower(),
                "shape": entry["shape"],
                "data_offsets": entry["data_offsets"],
                "absolute_data_offsets": entry["absolute_data_offsets"],
                "byte_length": entry["byte_length"],
            }
        layers.append({"layer_index": layer_index, "roles": roles})
    token_embedding = entries["model.language_model.embed_tokens.weight"]
    return {
        "format": "safetensors_header_metadata_only",
        "required_roles": sorted(ROLE_SHAPES),
        "layers": layers,
        "token_embedding": token_embedding,
        "lm_head": {
            **token_embedding,
            "source": "tied_word_embeddings",
            "shares_storage_with": "token_embedding",
        },
    }


def _write_mock_safetensors(path: Path, *, tensor_mutation=None) -> dict[str, dict]:
    header: dict[str, dict] = {
        "model.language_model.embed_tokens.weight": {
            "dtype": "BF16",
            "shape": [262144, 2560],
            "data_offsets": [0, 4],
        }
    }
    for layer_index in range(42):
        prefix = f"model.language_model.layers.{layer_index}."
        for _role, (suffix, shape) in ROLE_SHAPES.items():
            key = prefix + suffix
            header[key] = {"dtype": "BF16", "shape": shape, "data_offsets": [4, 4]}
            if tensor_mutation:
                tensor_mutation(key, header[key])
    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    tensor_data_start = 8 + len(header_bytes)
    path.write_bytes(len(header_bytes).to_bytes(8, "little") + header_bytes + b"abcd")
    entries = {}
    for key, entry in header.items():
        start, end = entry["data_offsets"]
        entries[key] = {
            **entry,
            "absolute_data_offsets": [tensor_data_start + start, tensor_data_start + end],
            "byte_length": end - start,
        }
    return entries


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
