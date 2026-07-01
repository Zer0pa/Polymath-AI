from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "build/gemma4_megakernel_host/gemma4_layer_runner"
MODEL_ID = "google/gemma-4-E4B"
REVISION = "7aa32e6889efd6300124851b164f8b364314c3d8"
STABLE_SHA = "e0d1c66ac876c2b6fbbe9e88f1b02dd37201d8ffba10afcd44f1c558fc32f7c9"
ADAPTER_PAYLOAD_BYTES = 2560 * 16 * 2 * 4


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
    paths = _write_component_pack(tmp_path, include_layer0_compute_tensors=True)

    result = _run_native(paths)

    assert result.returncode == 13
    payload = json.loads(result.stdout)
    assert payload["first_missing_green_field"].startswith(
        "c5_full_decoder_opencl_parity_runtime_unavailable:"
    )
    assert (
        "c5_full_decoder_multi_token_qa_prompt_sequence_orchestration_missing"
        not in payload["blockers"]
    )
    assert (
        "c5_full_decoder_rank16_adapter_stream_injection_missing"
        not in payload["blockers"]
    )
    assert payload["raw_boundary_proof"]["raw_payload_bytes_in_report"] is False
    assert payload["raw_boundary_proof"]["prediction_jsonl_written"] is False
    assert not paths["output_jsonl"].exists()


def test_native_c5_runtime_rejects_short_rank16_adapter_payload_before_opencl(
    tmp_path: Path,
) -> None:
    paths = _write_component_pack(tmp_path, include_layer0_compute_tensors=True)
    paths["checkpoint"].write_bytes(b"\x00" * 16)
    paths["checkpoint_sha"] = _sha256_file(paths["checkpoint"])
    policy_path = paths["pack"] / "adapter_site_policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["candidate_adapter_sha256"] = paths["checkpoint_sha"]
    policy_path.write_text(json.dumps(policy, sort_keys=True), encoding="utf-8")

    result = _run_native(paths)
    payload = json.loads(result.stdout)

    assert result.returncode == 13
    assert payload["first_missing_green_field"] == (
        "c5_full_decoder_rank16_adapter_payload_size_mismatch"
    )
    assert not any(
        item.startswith("c5_full_decoder_opencl_parity_runtime_unavailable:")
        for item in payload["blockers"]
    )
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

    paths = _write_component_pack(
        tmp_path,
        include_layer0_compute_tensors=True,
        tensor_mutation=mutate_layer5_attention,
    )

    result = _run_native(paths)
    payload = json.loads(result.stdout)

    assert result.returncode == 13
    assert payload["first_missing_green_field"].startswith(
        "c5_full_decoder_opencl_parity_runtime_unavailable:"
    )
    assert not paths["output_jsonl"].exists()


def test_native_c5_runtime_accepts_independent_k_norm_width(tmp_path: Path) -> None:
    def mutate_layer0_k_norm(key: str, entry: dict) -> None:
        if not key.endswith("layers.0.self_attn.k_norm.weight"):
            return
        entry["shape"] = [256]
        entry["data_offsets"][1] = entry["data_offsets"][0] + (256 * 2)

    paths = _write_component_pack(
        tmp_path,
        include_layer0_compute_tensors=True,
        tensor_mutation=mutate_layer0_k_norm,
    )

    result = _run_native(paths)
    payload = json.loads(result.stdout)

    assert result.returncode == 13
    assert payload["first_missing_green_field"].startswith(
        "c5_full_decoder_opencl_parity_runtime_unavailable:"
    )
    assert not paths["output_jsonl"].exists()


def test_native_c5_runtime_accepts_cli_opencl_library_config(tmp_path: Path) -> None:
    paths = _write_component_pack(tmp_path, include_layer0_compute_tensors=True)
    configured_library = tmp_path / "missing-vendor-libOpenCL.so"

    result = _run_native(
        paths,
        extra_args=["--opencl-library", str(configured_library)],
    )
    payload = json.loads(result.stdout)

    assert result.returncode == 13
    assert payload["first_missing_green_field"] == (
        "c5_full_decoder_opencl_parity_runtime_unavailable:"
        "opencl_single_token_layer_runtime_unavailable:"
        "opencl_library_configured_path_not_found"
    )
    assert payload["opencl_runtime_discovery_contract"] == {
        "opencl_library_path_configured": True,
        "opencl_library_cli_path_configured": True,
        "opencl_library_env_path_configured": False,
        "opencl_library_path_string_sha256": hashlib.sha256(
            str(configured_library).encode("utf-8")
        ).hexdigest(),
        "path_redacted": True,
        "env_library_variable": "POLYMATH_GEMMA4_OPENCL_LIBRARY",
        "env_library_paths_variable": "POLYMATH_GEMMA4_OPENCL_LIBRARY_PATHS",
        "android_vendor_paths_preferred_before_generic_soname": True,
        "android_sphal_loader_fallback_enabled": True,
        "android_sphal_loader_support_library": "libvndksupport.so",
    }
    assert not paths["output_jsonl"].exists()


def test_native_c5_runtime_reports_configured_opencl_dlopen_detail_redacted(
    tmp_path: Path,
) -> None:
    paths = _write_component_pack(tmp_path, include_layer0_compute_tensors=True)
    configured_library = tmp_path / "invalid-vendor-libOpenCL.so"
    configured_library.write_text("not a native shared library", encoding="utf-8")

    result = _run_native(
        paths,
        extra_args=["--opencl-library", str(configured_library)],
    )
    payload = json.loads(result.stdout)

    assert result.returncode == 13
    first_missing = payload["first_missing_green_field"]
    assert first_missing.startswith(
        "c5_full_decoder_opencl_parity_runtime_unavailable:"
        "opencl_single_token_layer_runtime_unavailable:"
        "opencl_library_configured_load_failed:dlerror_category="
    )
    assert ":dlerror_redacted_sha256=" in first_missing
    assert ":dlerror_detail=" in first_missing
    assert str(configured_library) not in first_missing
    assert str(configured_library) not in result.stdout
    assert payload["opencl_runtime_discovery_contract"][
        "opencl_library_cli_path_configured"
    ] is True
    assert payload["opencl_runtime_discovery_contract"][
        "android_sphal_loader_fallback_enabled"
    ] is True
    assert not paths["output_jsonl"].exists()


def test_native_c5_runtime_accepts_env_opencl_library_config(tmp_path: Path) -> None:
    paths = _write_component_pack(tmp_path, include_layer0_compute_tensors=True)
    env = os.environ.copy()
    env["POLYMATH_GEMMA4_OPENCL_LIBRARY"] = str(
        tmp_path / "missing-env-libOpenCL.so"
    )

    result = _run_native(paths, env=env)
    payload = json.loads(result.stdout)

    assert result.returncode == 13
    assert payload["first_missing_green_field"] == (
        "c5_full_decoder_opencl_parity_runtime_unavailable:"
        "opencl_single_token_layer_runtime_unavailable:"
        "opencl_library_configured_path_not_found"
    )
    discovery_contract = payload["opencl_runtime_discovery_contract"]
    assert discovery_contract["opencl_library_path_configured"] is True
    assert discovery_contract["opencl_library_cli_path_configured"] is False
    assert discovery_contract["opencl_library_env_path_configured"] is True
    assert discovery_contract["opencl_library_path_string_sha256"] == hashlib.sha256(
        env["POLYMATH_GEMMA4_OPENCL_LIBRARY"].encode("utf-8")
    ).hexdigest()
    assert discovery_contract["env_library_variable"] == (
        "POLYMATH_GEMMA4_OPENCL_LIBRARY"
    )
    assert discovery_contract["android_sphal_loader_fallback_enabled"] is True
    assert discovery_contract["android_sphal_loader_support_library"] == (
        "libvndksupport.so"
    )
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


def test_native_c5_runtime_rejects_missing_per_layer_input_runtime(tmp_path: Path) -> None:
    paths = _write_component_pack(tmp_path)
    manifest_path = paths["pack"] / "decoder_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("per_layer_input_runtime")
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")

    result = _run_native(paths)
    payload = json.loads(result.stdout)

    assert result.returncode == 13
    assert payload["first_missing_green_field"] == "decoder_manifest_per_layer_input_runtime_missing"
    assert (
        "c5_full_decoder_single_layer_attention_mlp_kernel_missing_after_ple_derivation"
        not in payload["blockers"]
    )
    assert not paths["output_jsonl"].exists()


def test_native_c5_runtime_rejects_malformed_per_layer_input_runtime(tmp_path: Path) -> None:
    paths = _write_component_pack(tmp_path)
    manifest_path = paths["pack"] / "decoder_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["per_layer_input_runtime"] = {
        "source": "derive_from_input_ids_with_ple_assets"
    }
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")

    result = _run_native(paths)
    payload = json.loads(result.stdout)

    assert result.returncode == 13
    assert payload["first_missing_green_field"] == "decoder_manifest_per_layer_input_runtime_missing"
    assert not paths["output_jsonl"].exists()


def test_native_c5_runtime_rejects_empty_tensor_value_before_compute(tmp_path: Path) -> None:
    paths = _write_component_pack(
        tmp_path,
        tensor_mutation=lambda key, entry: entry.update({"data_offsets": [4, 4]})
        if key.endswith("layers.0.layer_scalar")
        else None,
    )

    result = _run_native(paths)
    payload = json.loads(result.stdout)

    assert result.returncode == 13
    assert (
        "safetensors_tensor_empty:model.language_model.layers.0.layer_scalar"
        in payload["blockers"]
    )
    assert (
        "c5_full_decoder_single_layer_attention_mlp_kernel_missing_after_ple_derivation"
        not in payload["blockers"]
    )
    assert not paths["output_jsonl"].exists()


def test_native_c5_runtime_rejects_malformed_tokenizer_before_compute(tmp_path: Path) -> None:
    paths = _write_component_pack(tmp_path)
    merges = paths["tokenizer"] / "merges.hex.tsv"
    merges.write_text("61 62\t63\n", encoding="utf-8")
    _rewrite_manifest_tokenizer_merges_sha(paths["pack"] / "decoder_manifest.json", _sha256_file(merges))

    result = _run_native(paths)
    payload = json.loads(result.stdout)

    assert result.returncode == 13
    assert any(
        item.startswith("c5_qa_prompt_token_runtime_error:malformed merge line")
        for item in payload["blockers"]
    )
    assert (
        "c5_full_decoder_single_layer_attention_mlp_kernel_missing_after_ple_derivation"
        not in payload["blockers"]
    )
    assert not paths["output_jsonl"].exists()


def test_native_c5_runtime_rejects_out_of_vocab_prompt_before_opencl(
    tmp_path: Path,
) -> None:
    paths = _write_component_pack(tmp_path)
    vocab = paths["tokenizer"] / "vocab.hex.tsv"
    vocab.write_text("61\t262144\n", encoding="utf-8")
    _rewrite_manifest_tokenizer_vocab_sha(
        paths["pack"] / "decoder_manifest.json", _sha256_file(vocab)
    )
    paths["heldout"].write_text(
        json.dumps({"record_id": "r1", "question": "a", "answer": "a"}) + "\n",
        encoding="utf-8",
    )

    result = _run_native(paths)
    payload = json.loads(result.stdout)

    assert result.returncode == 13
    assert payload["first_missing_green_field"] == (
        "c5_full_decoder_token_id_out_of_vocab"
    )
    assert not any(
        item.startswith("c5_full_decoder_opencl_parity_runtime_unavailable:")
        for item in payload["blockers"]
    )
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
        tensor_mutation=lambda key, entry: entry.update({"data_offsets": [0, 999_999_999]})
        if key.endswith("layers.0.self_attn.q_proj.weight")
        else None,
    )

    result = _run_native(paths)
    payload = json.loads(result.stdout)

    assert result.returncode == 13
    assert "safetensors_tensor_range_exceeds_file_size" in payload["blockers"]
    assert not paths["output_jsonl"].exists()


def _run_native(
    paths: dict[str, Path],
    *,
    extra_args: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
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
    ]
    if extra_args:
        command.extend(extra_args)
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _write_component_pack(
    tmp_path: Path,
    *,
    include_layer0_compute_tensors: bool = False,
    tensor_mutation=None,
) -> dict[str, Path]:
    pack = tmp_path / "component_pack"
    pack.mkdir()
    tokenizer = tmp_path / "tokenizer"
    tokenizer.mkdir()
    vocab = tokenizer / "vocab.hex.tsv"
    merges = tokenizer / "merges.hex.tsv"
    vocab.write_text("61\t0\n", encoding="utf-8")
    merges.write_text("61\t62\t63\n", encoding="utf-8")
    checkpoint = tmp_path / "adapter_post_rank16.f32.bin"
    checkpoint.write_bytes(b"\x00" * ADAPTER_PAYLOAD_BYTES)
    checkpoint_sha = _sha256_file(checkpoint)
    heldout = tmp_path / "phase_C1_test.qa.jsonl"
    heldout.write_text(
        json.dumps({"record_id": "r1", "question": "q", "answer": "a"}) + "\n",
        encoding="utf-8",
    )
    model = tmp_path / "model.safetensors"
    entries = _write_mock_safetensors(
        model,
        include_layer0_compute_tensors=include_layer0_compute_tensors,
        tensor_mutation=tensor_mutation,
    )
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
        "per_layer_input_runtime": _per_layer_input_runtime(entries),
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


def _per_layer_input_runtime(entries: dict[str, dict]) -> dict:
    ple_token_key = "model.language_model.embed_tokens_per_layer.weight"
    ple_norm_key = "model.language_model.per_layer_projection_norm.weight"
    ple_projection_key = "model.language_model.per_layer_model_projection.weight"
    return {
        "source": "derive_from_input_ids_with_ple_assets",
        "hidden_size_per_layer_input": 256,
        "vocab_size_per_layer_input": 262144,
        "num_hidden_layers": 42,
        "scales": {
            "embed_tokens_per_layer": 16.0,
            "per_layer_model_projection": "1/sqrt(2560)",
            "per_layer_input_scale": "1/sqrt(2)",
        },
        "roles": {
            "embed_tokens_per_layer": {"key": ple_token_key, **entries[ple_token_key]},
            "per_layer_projection_norm": {"key": ple_norm_key, **entries[ple_norm_key]},
            "per_layer_model_projection": {
                "key": ple_projection_key,
                **entries[ple_projection_key],
            },
        },
    }


def _write_mock_safetensors(
    path: Path,
    *,
    include_layer0_compute_tensors: bool,
    tensor_mutation=None,
) -> dict[str, dict]:
    data = bytearray()

    def add_tensor(key: str, dtype: str, shape: list[int], byte_count: int) -> None:
        start = len(data)
        data.extend(b"\x00" * byte_count)
        header[key] = {"dtype": dtype, "shape": shape, "data_offsets": [start, len(data)]}
        if tensor_mutation:
            tensor_mutation(key, header[key])

    header: dict[str, dict] = {
    }
    add_tensor("model.language_model.embed_tokens.weight", "BF16", [262144, 2560], 4 * 2560 * 2)
    add_tensor(
        "model.language_model.embed_tokens_per_layer.weight",
        "BF16",
        [262144, 42 * 256],
        4 * 42 * 256 * 2,
    )
    add_tensor("model.language_model.per_layer_projection_norm.weight", "BF16", [256], 256 * 2)
    add_tensor(
        "model.language_model.per_layer_model_projection.weight",
        "BF16",
        [42 * 256, 2560],
        256 * 2560 * 2,
    )
    for layer_index in range(42):
        prefix = f"model.language_model.layers.{layer_index}."
        for _role, (suffix, shape) in ROLE_SHAPES.items():
            key = prefix + suffix
            element_count = 1
            for dimension in shape:
                element_count *= dimension
            if layer_index == 0 and (
                include_layer0_compute_tensors or suffix in {"input_layernorm.weight", "layer_scalar"}
            ):
                if suffix == "layer_scalar":
                    start = len(data)
                    data.extend(b"\x00\x3f")
                    offsets = [start, len(data)]
                else:
                    start = len(data)
                    data.extend(b"\x00" * (element_count * 2))
                    offsets = [start, len(data)]
            elif layer_index == 0 and suffix == "layer_scalar":
                start = len(data)
                data.extend(b"\x00\x3f")
                offsets = [start, len(data)]
            else:
                offsets = [len(data), len(data)]
            header[key] = {"dtype": "BF16", "shape": shape, "data_offsets": offsets}
            if tensor_mutation:
                tensor_mutation(key, header[key])
    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    tensor_data_start = 8 + len(header_bytes)
    path.write_bytes(len(header_bytes).to_bytes(8, "little") + header_bytes + data)
    entries = {}
    for key, entry in header.items():
        start, end = entry["data_offsets"]
        entries[key] = {
            **entry,
            "absolute_data_offsets": [tensor_data_start + start, tensor_data_start + end],
            "byte_length": end - start,
        }
    return entries


def _rewrite_manifest_tokenizer_merges_sha(path: Path, merges_sha: str) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["tokenizer_identity"]["merges_hex_tsv_sha256"] = merges_sha
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _rewrite_manifest_tokenizer_vocab_sha(path: Path, vocab_sha: str) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["tokenizer_identity"]["vocab_hex_tsv_sha256"] = vocab_sha
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
