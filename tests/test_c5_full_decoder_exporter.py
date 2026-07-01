from __future__ import annotations

import importlib.util
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORTER = (
    ROOT
    / "integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/tools/reference/"
    "export_c5_full_decoder_component_pack.py"
)
VALID_SHA = "a" * 64
VALID_STABLE_SHA = "b" * 64


def load_exporter_module():
    spec = importlib.util.spec_from_file_location("c5_full_decoder_exporter", EXPORTER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_c5_full_decoder_exporter_prints_schema_contract() -> None:
    result = subprocess.run(
        ["python3.11", str(EXPORTER), "--print-schema"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    contract = json.loads(result.stdout)
    assert contract["schema_version"] == "polymath_c5_full_decoder_component_pack_export_v1"
    assert contract["decoder_manifest_schema"]["schema_version"] == "polymath_c5_full_decoder_manifest_v1"
    assert contract["decoder_manifest_schema"]["decoder"]["num_hidden_layers"] == 42
    assert contract["decoder_manifest_schema"]["decoder"]["hidden_size"] == 2560
    assert contract["decoder_manifest_schema"]["decoder"]["logits_vocabulary_size"] == 262144
    assert contract["decoder_manifest_schema"]["lm_head"]["source"] == "tied_word_embeddings"
    assert contract["decoder_manifest_schema"]["architecture_config"]["num_key_value_heads"] == 2
    assert contract["decoder_manifest_schema"]["architecture_config"]["materializes_full_bsv_logits"] is False
    assert "self_attn_q_proj" in contract["decoder_manifest_schema"]["tensor_role_inventory"]["layer_roles"]
    assert contract["adapter_site_policy_schema"]["bridge_mse_is_c5_loss"] is False
    assert contract["runtime_dependencies"]["torch_required"] is False
    assert contract["runtime_dependencies"]["safetensors_python_package_required"] is False


def test_c5_full_decoder_exporter_missing_model_fails_closed(tmp_path: Path) -> None:
    output_dir = tmp_path / "component_pack"

    result = subprocess.run(
        [
            "python3.11",
            str(EXPORTER),
            "--model-safetensors",
            str(tmp_path / "missing_model.safetensors"),
            "--out",
            str(output_dir),
            "--candidate-adapter-sha",
            VALID_SHA,
            "--stable-baseline-sha",
            VALID_STABLE_SHA,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert payload["first_missing_green_field"] == "model_safetensors_missing"
    assert payload["raw_boundary_proof"]["raw_model_payload_copied_to_git"] is False
    assert not output_dir.exists()


def test_c5_full_decoder_exporter_rejects_repo_output() -> None:
    repo_output = ROOT / "runtime/reports/orchestration/forbidden_c5_decoder_pack"

    result = subprocess.run(
        [
            "python3.11",
            str(EXPORTER),
            "--model-safetensors",
            "/tmp/missing_model.safetensors",
            "--out",
            str(repo_output),
            "--candidate-adapter-sha",
            VALID_SHA,
            "--stable-baseline-sha",
            VALID_STABLE_SHA,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    blockers = json.loads(result.stdout)["blockers"]
    assert "output_dir_inside_git_worktree" in blockers
    assert not repo_output.exists()


def test_c5_full_decoder_exporter_writes_metadata_from_mock_safetensors(tmp_path: Path) -> None:
    model = tmp_path / "model.safetensors"
    output_dir = tmp_path / "component_pack"
    _write_mock_full_decoder_safetensors(model, embed_bytes=b"abcd")

    result = subprocess.run(
        [
            "python3.11",
            str(EXPORTER),
            "--model-safetensors",
            str(model),
            "--out",
            str(output_dir),
            "--candidate-adapter-sha",
            VALID_SHA,
            "--stable-baseline-sha",
            VALID_STABLE_SHA,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    stdout = json.loads(result.stdout)
    assert stdout["status"] == "created"
    decoder_manifest = json.loads((output_dir / "decoder_manifest.json").read_text())
    adapter_policy = json.loads((output_dir / "adapter_site_policy.json").read_text())
    export_report = json.loads((output_dir / "export_report.json").read_text())

    assert decoder_manifest["schema_version"] == "polymath_c5_full_decoder_manifest_v1"
    assert decoder_manifest["decoder"]["num_hidden_layers"] == 42
    assert len(decoder_manifest["decoder"]["layer_inventory"]) == 42
    assert decoder_manifest["architecture_config"]["num_attention_heads"] == 8
    assert decoder_manifest["architecture_config"]["num_key_value_heads"] == 2
    assert (
        decoder_manifest["architecture_config"]["attention_layout_source"]
        == "tensor_role_inventory.per_layer_attention_layout"
    )
    assert decoder_manifest["architecture_config"]["materializes_full_bsv_logits"] is False
    first_layer_roles = decoder_manifest["tensor_role_inventory"]["layers"][0]["roles"]
    assert first_layer_roles["self_attn_q_proj"]["shape"] == [2048, 2560]
    assert first_layer_roles["self_attn_k_proj"]["shape"] == [512, 2560]
    assert first_layer_roles["self_attn_q_norm"]["shape"] == [512]
    assert first_layer_roles["self_attn_k_norm"]["shape"] == [512]
    assert first_layer_roles["mlp_down_proj"]["shape"] == [2560, 10240]
    assert decoder_manifest["tensor_role_inventory"]["layers"][0]["attention_layout"] == {
        "head_dim": 256,
        "key_value_heads": 2,
        "k_proj_shape": [512, 2560],
        "k_norm_shape": [512],
        "o_proj_shape": [2560, 2048],
        "q_norm_shape": [512],
        "q_proj_shape": [2048, 2560],
        "query_heads": 8,
        "query_to_key_value_group_size": 4,
        "v_proj_shape": [512, 2560],
    }
    assert decoder_manifest["tensor_role_inventory"]["lm_head"]["shares_storage_with"] == "token_embedding"
    assert decoder_manifest["lm_head"]["sha256"] == hashlib.sha256(b"abcd").hexdigest()
    assert decoder_manifest["lm_head"]["sha256_kind"] == "safetensors_raw_tensor_bytes"
    assert adapter_policy["bridge_mse_is_c5_loss"] is False
    assert export_report["lm_head_unembedding_sha256_kind"] == "safetensors_raw_tensor_bytes"


def test_c5_full_decoder_exporter_records_layer_variant_attention_layout(tmp_path: Path) -> None:
    model = tmp_path / "model.safetensors"
    output_dir = tmp_path / "component_pack"
    layer5_overrides = {
        "self_attn.q_proj.weight": [2560, 2560],
        "self_attn.o_proj.weight": [2560, 2560],
    }
    _write_mock_full_decoder_safetensors(
        model,
        embed_bytes=b"abcd",
        per_layer_role_shapes={5: layer5_overrides},
    )

    result = subprocess.run(
        [
            "python3.11",
            str(EXPORTER),
            "--model-safetensors",
            str(model),
            "--out",
            str(output_dir),
            "--candidate-adapter-sha",
            VALID_SHA,
            "--stable-baseline-sha",
            VALID_STABLE_SHA,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    decoder_manifest = json.loads((output_dir / "decoder_manifest.json").read_text())
    layer5 = decoder_manifest["tensor_role_inventory"]["layers"][5]
    assert layer5["roles"]["self_attn_q_proj"]["shape"] == [2560, 2560]
    assert layer5["roles"]["self_attn_o_proj"]["shape"] == [2560, 2560]
    assert layer5["attention_layout"]["query_heads"] == 10
    assert layer5["attention_layout"]["key_value_heads"] == 2
    assert layer5["attention_layout"]["query_to_key_value_group_size"] == 5


def test_c5_full_decoder_exporter_accepts_reduced_kv_rows_with_512_norms(
    tmp_path: Path,
) -> None:
    model = tmp_path / "model.safetensors"
    output_dir = tmp_path / "component_pack"
    layer5_overrides = {
        "self_attn.k_proj.weight": [256, 2560],
        "self_attn.v_proj.weight": [256, 2560],
        "self_attn.q_norm.weight": [512],
        "self_attn.k_norm.weight": [512],
    }
    _write_mock_full_decoder_safetensors(
        model,
        embed_bytes=b"abcd",
        per_layer_role_shapes={5: layer5_overrides},
    )

    result = subprocess.run(
        [
            "python3.11",
            str(EXPORTER),
            "--model-safetensors",
            str(model),
            "--out",
            str(output_dir),
            "--candidate-adapter-sha",
            VALID_SHA,
            "--stable-baseline-sha",
            VALID_STABLE_SHA,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    decoder_manifest = json.loads((output_dir / "decoder_manifest.json").read_text())
    layer5 = decoder_manifest["tensor_role_inventory"]["layers"][5]
    assert layer5["attention_layout"]["key_value_heads"] == 1
    assert layer5["attention_layout"]["query_to_key_value_group_size"] == 8
    assert layer5["attention_layout"]["k_proj_shape"] == [256, 2560]
    assert layer5["attention_layout"]["q_norm_shape"] == [512]
    assert layer5["attention_layout"]["k_norm_shape"] == [512]


def test_c5_full_decoder_exporter_accepts_independent_k_norm_width(
    tmp_path: Path,
) -> None:
    model = tmp_path / "model.safetensors"
    output_dir = tmp_path / "component_pack"
    _write_mock_full_decoder_safetensors(
        model,
        embed_bytes=b"abcd",
        per_layer_role_shapes={0: {"self_attn.k_norm.weight": [256]}},
    )

    result = subprocess.run(
        [
            "python3.11",
            str(EXPORTER),
            "--model-safetensors",
            str(model),
            "--out",
            str(output_dir),
            "--candidate-adapter-sha",
            VALID_SHA,
            "--stable-baseline-sha",
            VALID_STABLE_SHA,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    decoder_manifest = json.loads((output_dir / "decoder_manifest.json").read_text())
    layer0 = decoder_manifest["tensor_role_inventory"]["layers"][0]
    assert layer0["attention_layout"]["q_norm_shape"] == [512]
    assert layer0["attention_layout"]["k_norm_shape"] == [256]


def test_c5_full_decoder_exporter_rejects_incompatible_norm_width(
    tmp_path: Path,
) -> None:
    model = tmp_path / "model.safetensors"
    output_dir = tmp_path / "component_pack"
    _write_mock_full_decoder_safetensors(
        model,
        embed_bytes=b"abcd",
        per_layer_role_shapes={5: {"self_attn.q_norm.weight": [768]}},
    )

    result = subprocess.run(
        [
            "python3.11",
            str(EXPORTER),
            "--model-safetensors",
            str(model),
            "--out",
            str(output_dir),
            "--candidate-adapter-sha",
            VALID_SHA,
            "--stable-baseline-sha",
            VALID_STABLE_SHA,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert (
        payload["first_missing_green_field"]
        == "decoder_layer_5_self_attn_q_norm_shape_mismatch_expected_{\"rank\":1,\"dim0_multiple_of\":256,\"dim0_at_most_q_proj_dim0\":true,\"q_proj_dim0_multiple_of_dim0\":true,\"dim0_compatible_with_projection_dim0\":true}_actual_[768]"
    )
    assert not output_dir.exists()


def test_c5_full_decoder_manifest_builder_schema() -> None:
    exporter = load_exporter_module()
    lm_head = exporter.build_lm_head_identity(
        dtype="bf16",
        tensor_sha256=VALID_SHA,
        tokenizer_vocab_sha256=exporter.TOKENIZER_VOCAB_HEX_SHA256,
        tokenizer_merges_sha256=exporter.TOKENIZER_MERGES_HEX_SHA256,
    )
    layers = [
        {
            "layer_index": layer_index,
            "key_prefix": f"model.language_model.layers.{layer_index}.",
            "key_count": 8,
        }
        for layer_index in range(42)
    ]

    manifest = exporter.build_decoder_manifest(
        source_model_path=Path("/outside/model.safetensors"),
        source_model_sha256=VALID_STABLE_SHA,
        source_model_size_bytes=123,
        layers=layers,
        lm_head_identity=lm_head,
        architecture_config=exporter.build_architecture_config(),
        tensor_role_inventory={
            "format": "safetensors_header_metadata_only",
            "required_roles": sorted(exporter.TENSOR_ROLE_SPECS),
            "layers": [],
            "token_embedding": {},
            "lm_head": {},
        },
        tokenizer_vocab_sha256=exporter.TOKENIZER_VOCAB_HEX_SHA256,
        tokenizer_merges_sha256=exporter.TOKENIZER_MERGES_HEX_SHA256,
    )

    assert manifest["schema_version"] == "polymath_c5_full_decoder_manifest_v1"
    assert manifest["decoder"]["kind"] == "full_gemma4_text_decoder_logits"
    assert manifest["decoder"]["num_hidden_layers"] == 42
    assert manifest["decoder"]["hidden_size"] == 2560
    assert manifest["architecture_config"]["num_key_value_heads"] == 2
    assert "self_attn_q_proj" in manifest["tensor_role_inventory"]["required_roles"]
    assert manifest["lm_head"]["embedded_in_decoder"] is True
    assert manifest["lm_head"]["shape"] == [262144, 2560]
    assert manifest["runtime_contract"]["candidate_train_loss_source"].endswith(
        "bridge MSE is forbidden"
    )


def test_c5_full_decoder_adapter_policy_rejects_unknown_site() -> None:
    exporter = load_exporter_module()

    try:
        exporter.build_adapter_site_policy(
            candidate_adapter_sha256=VALID_SHA,
            stable_baseline_adapter_sha256=VALID_STABLE_SHA,
            adapter_site="unknown_site",
        )
    except ValueError as error:
        assert str(error) == "adapter_site_unknown"
    else:
        raise AssertionError("unknown adapter site must fail closed")


def test_c5_full_decoder_adapter_policy_preserves_bridge_mse_nonclaim() -> None:
    exporter = load_exporter_module()

    policy = exporter.build_adapter_site_policy(
        candidate_adapter_sha256=VALID_SHA,
        stable_baseline_adapter_sha256=VALID_STABLE_SHA,
        adapter_site="post_layer1_residual",
    )

    assert policy["schema_version"] == "polymath_c5_adapter_site_policy_v1"
    assert policy["decoder_layer_index"] == 1
    assert policy["input_shape"] == [1, 16, 2560]
    assert policy["output_shape"] == [1, 16, 2560]
    assert policy["bridge_mse_is_c5_loss"] is False
    assert policy["qa_loss_source"] == "teacher_forced_answer_token_nll_from_full_decoder_logits"


def _write_mock_full_decoder_safetensors(
    path: Path,
    *,
    embed_bytes: bytes,
    per_layer_role_shapes: dict[int, dict[str, list[int]]] | None = None,
) -> None:
    offset = len(embed_bytes)
    header = {
        "model.language_model.embed_tokens.weight": {
            "dtype": "BF16",
            "shape": [262144, 2560],
            "data_offsets": [0, len(embed_bytes)],
        }
    }
    role_shapes = {
        "input_layernorm.weight": [2560],
        "self_attn.q_proj.weight": [2048, 2560],
        "self_attn.k_proj.weight": [512, 2560],
        "self_attn.v_proj.weight": [512, 2560],
        "self_attn.o_proj.weight": [2560, 2048],
        "self_attn.q_norm.weight": [512],
        "self_attn.k_norm.weight": [512],
        "post_attention_layernorm.weight": [2560],
        "pre_feedforward_layernorm.weight": [2560],
        "mlp.gate_proj.weight": [10240, 2560],
        "mlp.up_proj.weight": [10240, 2560],
        "mlp.down_proj.weight": [2560, 10240],
        "post_feedforward_layernorm.weight": [2560],
        "per_layer_input_gate.weight": [256, 2560],
        "per_layer_projection.weight": [2560, 256],
        "post_per_layer_input_norm.weight": [2560],
        "layer_scalar": [1],
    }
    for layer_index in range(42):
        for suffix, shape in role_shapes.items():
            actual_shape = shape
            if per_layer_role_shapes and layer_index in per_layer_role_shapes:
                actual_shape = per_layer_role_shapes[layer_index].get(suffix, shape)
            header[f"model.language_model.layers.{layer_index}.{suffix}"] = {
                "dtype": "BF16",
                "shape": actual_shape,
                "data_offsets": [offset, offset],
            }
    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    path.write_bytes(len(header_bytes).to_bytes(8, "little") + header_bytes + embed_bytes)
