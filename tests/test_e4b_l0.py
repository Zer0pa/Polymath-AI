from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Mapping, Sequence

import pytest

from polymath_ai.frontier.e4b_l0 import (
    ArtifactSpec,
    DEFAULT_ARTIFACTS,
    E4bL0Builder,
    canonical_sha256,
)


def layer_types() -> list[str]:
    return [
        "full_attention" if (index + 1) % 6 == 0 else "sliding_attention"
        for index in range(42)
    ]


def config(*, tie_word_embeddings: bool, quantization_config: Mapping[str, Any] | None) -> bytes:
    payload = {
        "model_type": "gemma4",
        "tie_word_embeddings": tie_word_embeddings,
        "text_config": {
            "hidden_size": 2560,
            "intermediate_size": 10240,
            "num_hidden_layers": 42,
            "num_attention_heads": 8,
            "num_key_value_heads": 2,
            "head_dim": 256,
            "global_head_dim": 512,
            "sliding_window": 512,
            "hidden_size_per_layer_input": 256,
            "vocab_size": 262144,
            "vocab_size_per_layer_input": 262144,
            "num_kv_shared_layers": 18,
            "rms_norm_eps": 1e-6,
            "final_logit_softcapping": 30.0,
            "layer_types": layer_types(),
            "rope_parameters": {
                "full_attention": {"rope_type": "proportional"},
                "sliding_attention": {"rope_type": "default"},
            },
            "tie_word_embeddings": tie_word_embeddings,
            "hidden_activation": "gelu_pytorch_tanh",
            "attention_k_eq_v": False,
        },
    }
    if quantization_config is not None:
        payload["quantization_config"] = quantization_config
    return json.dumps(payload, sort_keys=True).encode()


TOKENIZER = json.dumps(
    {
        "added_tokens": [
            {"id": 0, "content": "<pad>"},
            {"id": 1, "content": "<eos>"},
            {"id": 2, "content": "<bos>"},
            {"id": 105, "content": "<|turn>"},
            {"id": 106, "content": "<turn|>"},
        ]
    },
    sort_keys=True,
).encode()
TOKENIZER_CONFIG = json.dumps(
    {
        "bos_token": "<bos>",
        "eos_token": "<eos>",
        "pad_token": "<pad>",
        "unk_token": "<unk>",
        "add_bos_token": True,
        "add_eos_token": False,
        "chat_template": "fixture-template",
    },
    sort_keys=True,
).encode()
CHAT_TEMPLATE = b"fixture-template"


def safetensors_bytes(candidate: str) -> bytes:
    suffix = "weight" if candidate == "transformers" else "weight_packed"
    header = {
        f"lm_head.{suffix}": {"dtype": "U8", "shape": [262144, 2560], "data_offsets": [0, 1]},
        "model.language_model.embed_tokens_per_layer.weight": {
            "dtype": "I8",
            "shape": [262144, 10752],
            "data_offsets": [1, 2],
        },
        "model.language_model.layers.0.per_layer_projection.weight": {
            "dtype": "I8",
            "shape": [256, 2560],
            "data_offsets": [2, 3],
        },
    }
    encoded = json.dumps(header, sort_keys=True, separators=(",", ":")).encode()
    return len(encoded).to_bytes(8, "little") + encoded + b"x"


class FakeHubClient:
    def __init__(self) -> None:
        self.files: dict[str, dict[str, bytes]] = {}
        self.weight_bytes: dict[str, bytes] = {}
        self.full_weight_reads = 0
        for artifact in DEFAULT_ARTIFACTS:
            is_qat = artifact.role.startswith("qat_")
            quantization = {"quant_method": artifact.role} if is_qat else None
            tie = not is_qat
            self.files[artifact.role] = {
                "config.json": config(tie_word_embeddings=tie, quantization_config=quantization),
                "tokenizer.json": TOKENIZER,
                "tokenizer_config.json": TOKENIZER_CONFIG,
                "chat_template.jinja": CHAT_TEMPLATE,
            }
            kind = "ct" if artifact.role.endswith("compressed_tensors") else "transformers"
            self.weight_bytes[artifact.role] = safetensors_bytes(kind)

    def list_tree(self, artifact: ArtifactSpec) -> Sequence[Mapping[str, Any]]:
        records = [
            {
                "type": "file",
                "path": path,
                "size": len(value),
                "oid": f"git-{path}",
            }
            for path, value in self.files[artifact.role].items()
        ]
        weights = self.weight_bytes[artifact.role]
        records.append(
            {
                "type": "file",
                "path": "model.safetensors",
                "size": len(weights),
                "oid": "git-model",
                "xetHash": "xet-model",
                "lfs": {"oid": "a" * 64, "size": len(weights)},
            }
        )
        return records

    def read_file(self, artifact: ArtifactSpec, path: str) -> bytes:
        if path == "model.safetensors":
            self.full_weight_reads += 1
            raise AssertionError("builder must never read a complete weight object")
        return self.files[artifact.role][path]

    def read_range(self, artifact: ArtifactSpec, path: str, start: int, end: int) -> bytes:
        assert path == "model.safetensors"
        return self.weight_bytes[artifact.role][start : end + 1]


def build(client: FakeHubClient, artifacts: Sequence[ArtifactSpec] = DEFAULT_ARTIFACTS) -> dict[str, Any]:
    stacks = {
        "qat_mobile_transformers": {"transformers": "5.13.0"},
        "qat_mobile_compressed_tensors": {"transformers": "5.13.0"},
    }
    return E4bL0Builder(client).build(
        artifacts,
        provisional_build_source="qat_mobile_transformers",
        reference_stacks=stacks,
        converter_lineage={
            "exporter_revision": "fixture",
            "converter_and_QAIRT_build": "2.44.0.260225",
            "target_socModel": 69,
            "target_dspArch": 79,
        },
        edge_a_protocol={"teacher_forced_objective": "full_answer_masked_nll"},
    )


def test_builds_passed_content_addressed_l0_without_weight_download() -> None:
    client = FakeHubClient()

    payload = build(client)

    manifest = payload["manifest"]
    assert manifest["state"] == "passed_scope"
    assert manifest["blockers"] == []
    assert payload["manifest_sha256"] == canonical_sha256(manifest)
    assert manifest["architecture_oracle"]["architecture_contract"]["global_layer_count"] == 7
    assert manifest["high_precision_task_oracle"]["LM_head_tying_state"] is True
    assert (
        manifest["mobile_qat_candidates"]["qat_mobile_transformers"]
        ["LM_head_tying_and_quantization_identity"]["lm_head_is_separate"]
        is True
    )
    assert client.full_weight_reads == 0


def test_tokenizer_drift_blocks_candidate() -> None:
    client = FakeHubClient()
    changed = json.loads(TOKENIZER)
    changed["added_tokens"][-1]["id"] = 999
    client.files["qat_mobile_transformers"]["tokenizer.json"] = json.dumps(
        changed, sort_keys=True
    ).encode()

    payload = build(client)

    assert payload["manifest"]["state"] == "blocked_fail_closed"
    assert (
        "qat_mobile_transformers:tokenizer_json_differs_from_task_oracle"
        in payload["manifest"]["blockers"]
    )


def test_rejects_mutable_revision_name() -> None:
    client = FakeHubClient()
    artifacts = list(DEFAULT_ARTIFACTS)
    artifacts[0] = ArtifactSpec(
        role=artifacts[0].role,
        repository=artifacts[0].repository,
        revision="main",
    )

    with pytest.raises(ValueError, match="immutable SHA"):
        build(client, artifacts)


def test_rejects_wrong_layer_pattern() -> None:
    client = FakeHubClient()
    payload = json.loads(client.files["qat_mobile_compressed_tensors"]["config.json"])
    payload["text_config"]["layer_types"][0] = "full_attention"
    client.files["qat_mobile_compressed_tensors"]["config.json"] = json.dumps(
        payload, sort_keys=True
    ).encode()

    result = build(client)

    assert result["manifest"]["state"] == "blocked_fail_closed"
    assert (
        "qat_mobile_compressed_tensors:architecture:layer_types"
        in result["manifest"]["blockers"]
    )
