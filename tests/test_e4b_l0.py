from __future__ import annotations

import hashlib
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


def config(
    *, tie_word_embeddings: bool, quantization_config: Mapping[str, Any] | None
) -> bytes:
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
            "model_type": "gemma4_text",
            "layer_types": layer_types(),
            "rope_parameters": {
                "full_attention": {
                    "partial_rotary_factor": 0.25,
                    "rope_theta": 1_000_000.0,
                    "rope_type": "proportional",
                },
                "sliding_attention": {
                    "rope_theta": 10_000.0,
                    "rope_type": "default",
                },
            },
            "tie_word_embeddings": tie_word_embeddings,
            "hidden_activation": "gelu_pytorch_tanh",
            "attention_k_eq_v": False,
            "attention_bias": False,
            "use_cache": True,
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
CHAT_TEMPLATE = b"fixture-template <turn|>"


def safetensors_bytes(candidate: str) -> bytes:
    suffix = "weight" if candidate == "transformers" else "weight_packed"
    header = {
        f"lm_head.{suffix}": {"dtype": "U8", "shape": [1], "data_offsets": [0, 1]},
        "model.language_model.embed_tokens_per_layer.weight": {
            "dtype": "I8",
            "shape": [1],
            "data_offsets": [1, 2],
        },
        "model.language_model.layers.0.per_layer_projection.weight": {
            "dtype": "I8",
            "shape": [1],
            "data_offsets": [2, 3],
        },
    }
    encoded = json.dumps(header, sort_keys=True, separators=(",", ":")).encode()
    encoded += b" " * (-len(encoded) % 8)
    return len(encoded).to_bytes(8, "little") + encoded + b"xyz"


def safetensors_index(weights: bytes) -> bytes:
    header_size = int.from_bytes(weights[:8], "little")
    header = json.loads(weights[8 : 8 + header_size].rstrip(b" "))
    payload = {
        "metadata": {"total_size": len(weights) - 8 - header_size},
        "weight_map": {name: "model.safetensors" for name in header},
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


class FakeHubClient:
    def __init__(self) -> None:
        self.files: dict[str, dict[str, bytes]] = {}
        self.weight_bytes: dict[str, bytes] = {}
        self.full_weight_reads = 0
        for artifact in DEFAULT_ARTIFACTS:
            is_qat = artifact.role.startswith("qat_")
            quantization = {"quant_method": artifact.role} if is_qat else None
            tie = not is_qat
            files = {
                ".gitattributes": b"*.safetensors filter=lfs diff=lfs merge=lfs -text\n",
                "README.md": (
                    b"---\nlicense: apache-2.0\n"
                    b"license_link: https://ai.google.dev/gemma/docs/gemma_4_license\n---\n"
                ),
                "config.json": config(
                    tie_word_embeddings=tie, quantization_config=quantization
                ),
                "generation_config.json": b"{}",
                "processor_config.json": b"{}",
                "tokenizer.json": TOKENIZER,
                "tokenizer_config.json": TOKENIZER_CONFIG,
            }
            if artifact.role != "architecture_oracle":
                files["chat_template.jinja"] = CHAT_TEMPLATE
            if is_qat:
                files["preprocessor_config.json"] = b"{}"
            self.files[artifact.role] = files
            kind = (
                "ct" if artifact.role.endswith("compressed_tensors") else "transformers"
            )
            self.weight_bytes[artifact.role] = safetensors_bytes(kind)
            if artifact.role == "qat_mobile_compressed_tensors":
                files["model.safetensors.index.json"] = safetensors_index(
                    self.weight_bytes[artifact.role]
                )

    def list_tree(self, artifact: ArtifactSpec) -> Sequence[Mapping[str, Any]]:
        records = [
            {
                "type": "file",
                "path": path,
                "size": len(value),
                "oid": hashlib.sha1(path.encode()).hexdigest(),
            }
            for path, value in self.files[artifact.role].items()
        ]
        weights = self.weight_bytes[artifact.role]
        records.append(
            {
                "type": "file",
                "path": "model.safetensors",
                "size": len(weights),
                "oid": "1" * 40,
                "xetHash": "2" * 64,
                "lfs": {"oid": "a" * 64, "size": len(weights)},
            }
        )
        return records

    def read_file(self, artifact: ArtifactSpec, path: str) -> bytes:
        if path == "model.safetensors":
            self.full_weight_reads += 1
            raise AssertionError("builder must never read a complete weight object")
        return self.files[artifact.role][path]

    def read_range(
        self, artifact: ArtifactSpec, path: str, start: int, end: int
    ) -> bytes:
        assert path == "model.safetensors"
        return self.weight_bytes[artifact.role][start : end + 1]


def build(
    client: FakeHubClient, artifacts: Sequence[ArtifactSpec] = DEFAULT_ARTIFACTS
) -> dict[str, Any]:
    stacks = reference_stacks()
    return E4bL0Builder(client).build(
        artifacts,
        provisional_build_source="qat_mobile_transformers",
        reference_stacks=stacks,
        converter_lineage=converter_lineage(),
        edge_a_protocol=edge_a_protocol(),
        weight_verification_receipts=weight_receipts(client),
    )


def reference_stacks() -> dict[str, dict[str, Any]]:
    packages = {
        "torch": "2.13.0+cpu",
        "transformers": "5.13.0",
        "safetensors": "0.8.0",
        "tokenizers": "0.22.2",
        "accelerate": "1.14.0",
        "numpy": "1.26.4",
    }
    result: dict[str, dict[str, Any]] = {}
    for role in (
        "high_precision_task_oracle",
        "qat_mobile_transformers",
        "qat_mobile_compressed_tensors",
    ):
        role_packages = dict(packages)
        if role == "qat_mobile_compressed_tensors":
            role_packages["compressed-tensors"] = "0.17.1"
        package_artifacts = {
            package: {
                "version": version,
                "filename": f"{package}-{version}.whl",
                "bytes": 1,
                "sha256": hashlib.sha256(package.encode()).hexdigest(),
                "source": "pypi_exact_file",
            }
            for package, version in role_packages.items()
        }
        source_identity = {
            "torch": {
                "repository": "pytorch/pytorch",
                "revision": "cf30153c4c131c8164ee7798e5022d810682e2cb",
                "source_files": {"version.txt": "1" * 64},
            },
            "transformers": {
                "repository": "huggingface/transformers",
                "revision": "6af945f436d85f2b0c5dff9b14feccd27b1d470b",
                "source_files": {
                    "src/transformers/models/gemma4/modeling_gemma4.py": "2" * 64
                },
            },
        }
        if role == "qat_mobile_compressed_tensors":
            source_identity["compressed_tensors"] = {
                "repository": "vllm-project/compressed-tensors",
                "revision": "c18a0fa8b969d789f33b7912eef57cd69c56bd9e",
                "source_files": {"src/compressed_tensors/__init__.py": "3" * 64},
            }
        smoke_receipt = None
        if role == "qat_mobile_transformers":
            artifact = next(item for item in DEFAULT_ARTIFACTS if item.role == role)
            smoke_receipt = {
                "schema_version": "e4b_reference_stack_smoke_v1",
                "state": "passed_scope",
                "role": role,
                "repository": artifact.repository,
                "revision": artifact.revision,
                "run_id": "fixture-smoke",
                "executed_at_utc": "2026-07-11T00:00:00Z",
                "raw_location_class": "provider_local",
                "framework_imports_passed": True,
                "tokenizer_load_passed": True,
                "tokenizer_template_bytes_match_task_oracle": True,
                "assistant_termination_token_id": 106,
                "assistant_termination_emitted_once": True,
                "target_shift_and_full_answer_mask_fixture_passed": True,
                "chat_template_render_sha256": "4" * 64,
                "artifact_load_passed": True,
                "missing_keys": [],
                "unexpected_keys": [],
                "artifact_native_quantized_modules_preserved": True,
                "deterministic_forward_replay_passed": True,
                "finite_logits_and_nll_passed": True,
                "peak_rss_bytes": 1_000_000,
                "wall_time_seconds": 1.0,
            }
        result[role] = {
            "identity_state": "passed_scope"
            if role == "qat_mobile_transformers"
            else "frozen_unexecuted",
            "python": "3.11",
            "platform": "linux_x86_64",
            "packages": role_packages,
            "package_artifacts": package_artifacts,
            "package_lock_sha256": canonical_sha256(package_artifacts),
            "package_lock_locator": f"runpod://fixture/{role}/reference-stack.lock",
            "framework_source_identity": source_identity,
            "dtype_and_runtime_policy": {
                "weight_storage": "artifact_native",
                "compute_dtype": "artifact_declared",
                "accumulation_dtype": "float32",
                "device": "cpu",
                "artifact_native_quantization_required": role.startswith("qat_"),
                "silent_requantization_or_dequantized_substitution": "forbidden",
                "trust_remote_code": False,
            },
            "smoke_receipt": smoke_receipt,
            "smoke_receipt_sha256": (
                canonical_sha256(smoke_receipt) if smoke_receipt is not None else None
            ),
        }
    return result


def converter_lineage() -> dict[str, Any]:
    return {
        "exporter_revision": "f" * 40,
        "converter_and_QAIRT_build": "v2.44.0.260225143659",
        "QNN_API_version": "2.34.0",
        "target_socModel": 69,
        "target_dspArch": 79,
        "qairt_core_foundry_receipt_sha256": "1" * 64,
        "qairt_tool_hashes": {
            "qnn_context_binary_generator": "2" * 64,
            "qnn_context_binary_utility": "3" * 64,
            "qnn_net_run": "4" * 64,
            "libQnnHtp": "5" * 64,
            "libQnnSystem": "6" * 64,
        },
        "execution_runtime": "ubuntu_22_04_direct_chroot",
    }


def edge_a_protocol() -> dict[str, Any]:
    return {
        "template": "exact_repository_chat_template",
        "teacher_forced_objective": "full_answer_plus_turn_termination_masked_NLL",
        "decode": {
            "do_sample": False,
            "max_new_tokens": 64,
            "seed": 0,
            "stop_token": "<turn|>",
        },
        "length_buckets": [16, 64, 128],
        "evaluator": "token_weighted_nll_plus_deterministic_generation_behavior",
        "target_shift": "causal_next_token",
        "full_answer_mask": True,
        "reference_qat_tolerance_policy": {
            "policy_state": "predeclared_before_target_observation",
            "teacher_forced_logits": {
                "metric": "paired_centered_full_vocab_logit_nrmse_and_top1",
                "centered_nrmse_max": 0.05,
                "top1_agreement_min": 0.95,
                "scored_positions_only": True,
            },
            "teacher_forced_nll": {
                "metric": "paired_token_weighted_delta_nll",
                "paired_upper_95pct_nats_per_scored_token_max": 0.02,
                "exact_mask_denominator": True,
            },
            "deterministic_decode": {
                "metric": "paired_greedy_token_sequence",
                "sequence_exact_match_rate_min": 0.90,
                "normalized_edit_distance_mean_max": 0.02,
                "stop_and_max_length_exact": True,
            },
            "behavioral_suite": {
                "metric": "frozen_paired_behavior_score_delta",
                "paired_lower_95pct_score_delta_min": -0.01,
                "evaluator_revision": "9" * 40,
            },
        },
    }


def weight_receipts(client: FakeHubClient) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for role in (
        "high_precision_task_oracle",
        "qat_mobile_transformers",
        "qat_mobile_compressed_tensors",
    ):
        report = {
            "schema_version": "e4b_provider_weight_verification_v1",
            "state": "passed_scope",
            "role": role,
            "repository": next(
                artifact.repository
                for artifact in DEFAULT_ARTIFACTS
                if artifact.role == role
            ),
            "revision": next(
                artifact.revision
                for artifact in DEFAULT_ARTIFACTS
                if artifact.role == role
            ),
            "run_id": "fixture-run",
            "completed_at_utc": "2026-07-11T00:00:00Z",
            "custody": {
                "raw_location_class": "provider_local",
                "orchestration_host_weight_bytes": 0,
                "secret_material_in_report": False,
                "full_file_streamed_for_hash": True,
                "verifier_binary": "/usr/bin/sha256sum",
                "verifier_binary_sha256": "8" * 64,
            },
            "files": {
                "model.safetensors": {
                    "sha256": "a" * 64,
                    "bytes": len(client.weight_bytes[role]),
                    "verification_method": "provider_local_streaming_sha256",
                }
            },
        }
        result[role] = {
            "state": "passed_scope",
            "raw_location_class": "provider_local",
            "report_locator": f"runpod://fixture/{role}/receipt.json",
            "report_sha256": canonical_sha256(report),
            "report": report,
        }
    return result


def test_builds_passed_content_addressed_l0_without_weight_download() -> None:
    client = FakeHubClient()

    payload = build(client)

    manifest = payload["manifest"]
    assert manifest["state"] == "passed_scope"
    assert manifest["blockers"] == []
    assert payload["manifest_sha256"] == canonical_sha256(manifest)
    assert (
        manifest["architecture_oracle"]["architecture_contract"]["global_layer_count"]
        == 7
    )
    assert manifest["high_precision_task_oracle"]["LM_head_tying_state"] is True
    assert (
        manifest["mobile_qat_candidates"]["qat_mobile_transformers"][
            "LM_head_tying_and_quantization_identity"
        ]["lm_head_is_separate"]
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


def test_empty_external_contracts_block_instead_of_passing() -> None:
    client = FakeHubClient()

    result = E4bL0Builder(client).build(
        DEFAULT_ARTIFACTS,
        provisional_build_source="qat_mobile_transformers",
        reference_stacks={},
        converter_lineage={},
        edge_a_protocol={},
        weight_verification_receipts={},
    )

    assert result["manifest"]["state"] == "blocked_fail_closed"
    assert "converter_lineage:wrong_field_set" in result["manifest"]["blockers"]
    assert "reference_stacks:wrong_role_set" in result["manifest"]["blockers"]


def test_rejects_foreign_repository_even_with_full_revision() -> None:
    client = FakeHubClient()
    artifacts = list(DEFAULT_ARTIFACTS)
    artifacts[0] = ArtifactSpec(
        role=artifacts[0].role,
        repository="attacker/substitute",
        revision=artifacts[0].revision,
    )

    with pytest.raises(ValueError, match="unexpected official repository"):
        build(client, artifacts)


def test_non_finite_contract_is_rejected_before_hashing() -> None:
    client = FakeHubClient()
    protocol = edge_a_protocol()
    protocol["reference_qat_tolerance_policy"]["teacher_forced_nll"] = float("nan")

    with pytest.raises(ValueError, match="non-finite"):
        E4bL0Builder(client).build(
            DEFAULT_ARTIFACTS,
            provisional_build_source="qat_mobile_transformers",
            reference_stacks=reference_stacks(),
            converter_lineage=converter_lineage(),
            edge_a_protocol=protocol,
            weight_verification_receipts=weight_receipts(client),
        )


def test_chat_template_must_emit_declared_terminator() -> None:
    client = FakeHubClient()
    client.files["qat_mobile_transformers"]["chat_template.jinja"] = b"no terminator"

    result = build(client)

    assert result["manifest"]["state"] == "blocked_fail_closed"
    assert (
        "qat_mobile_transformers:chat_template_does_not_emit_termination"
        in result["manifest"]["blockers"]
    )


def test_weight_report_mutation_cannot_reuse_detached_hash() -> None:
    client = FakeHubClient()
    receipts = weight_receipts(client)
    receipts["qat_mobile_transformers"]["report"]["files"]["model.safetensors"][
        "sha256"
    ] = "f" * 64

    result = E4bL0Builder(client).build(
        DEFAULT_ARTIFACTS,
        provisional_build_source="qat_mobile_transformers",
        reference_stacks=reference_stacks(),
        converter_lineage=converter_lineage(),
        edge_a_protocol=edge_a_protocol(),
        weight_verification_receipts=receipts,
    )

    assert (
        "qat_mobile_transformers:weight_receipt:bad_report_sha256"
        in result["manifest"]["blockers"]
    )
    assert (
        "qat_mobile_transformers:weight_receipt:model.safetensors:sha256_mismatch"
        in result["manifest"]["blockers"]
    )


def test_canonical_weight_report_cannot_claim_wrong_repository() -> None:
    client = FakeHubClient()
    receipts = weight_receipts(client)
    receipt = receipts["high_precision_task_oracle"]
    receipt["report"]["repository"] = "attacker/substitute"
    receipt["report_sha256"] = canonical_sha256(receipt["report"])

    result = E4bL0Builder(client).build(
        DEFAULT_ARTIFACTS,
        provisional_build_source="qat_mobile_transformers",
        reference_stacks=reference_stacks(),
        converter_lineage=converter_lineage(),
        edge_a_protocol=edge_a_protocol(),
        weight_verification_receipts=receipts,
    )

    assert (
        "high_precision_task_oracle:weight_receipt:report_repository_mismatch"
        in result["manifest"]["blockers"]
    )


def test_reference_package_lock_must_bind_exact_artifact_inventory() -> None:
    client = FakeHubClient()
    stacks = reference_stacks()
    stacks["qat_mobile_transformers"]["package_artifacts"]["torch"]["sha256"] = "f" * 64

    result = E4bL0Builder(client).build(
        DEFAULT_ARTIFACTS,
        provisional_build_source="qat_mobile_transformers",
        reference_stacks=stacks,
        converter_lineage=converter_lineage(),
        edge_a_protocol=edge_a_protocol(),
        weight_verification_receipts=weight_receipts(client),
    )

    assert (
        "qat_mobile_transformers:reference_stack:bad_package_lock_sha256"
        in result["manifest"]["blockers"]
    )


def test_provisional_reference_smoke_rejects_nonexact_state_dict() -> None:
    client = FakeHubClient()
    stacks = reference_stacks()
    stack = stacks["qat_mobile_transformers"]
    stack["smoke_receipt"]["missing_keys"] = ["lm_head.weight"]
    stack["smoke_receipt_sha256"] = canonical_sha256(stack["smoke_receipt"])

    result = E4bL0Builder(client).build(
        DEFAULT_ARTIFACTS,
        provisional_build_source="qat_mobile_transformers",
        reference_stacks=stacks,
        converter_lineage=converter_lineage(),
        edge_a_protocol=edge_a_protocol(),
        weight_verification_receipts=weight_receipts(client),
    )

    assert (
        "qat_mobile_transformers:reference_stack:smoke_state_dict_not_exact"
        in result["manifest"]["blockers"]
    )


def test_unreviewed_repository_file_fails_closed() -> None:
    client = FakeHubClient()
    client.files["qat_mobile_transformers"]["modeling_override.py"] = b"pass\n"

    with pytest.raises(ValueError, match="immutable repository file set differs"):
        build(client)


def test_duplicate_config_key_is_rejected_as_nonauthoritative_json() -> None:
    client = FakeHubClient()
    client.files["architecture_oracle"]["config.json"] = (
        b'{"model_type":"gemma4","model_type":"gemma4"}'
    )

    with pytest.raises(ValueError, match="not strict finite JSON"):
        build(client)


def test_sharded_index_total_size_must_join_exact_payload() -> None:
    client = FakeHubClient()
    index = json.loads(
        client.files["qat_mobile_compressed_tensors"]["model.safetensors.index.json"]
    )
    index["metadata"]["total_size"] += 1
    client.files["qat_mobile_compressed_tensors"]["model.safetensors.index.json"] = (
        json.dumps(index, sort_keys=True, separators=(",", ":")).encode()
    )

    with pytest.raises(ValueError, match="total_size disagrees"):
        build(client)


def test_edge_a_quality_tolerance_cannot_be_relaxed_past_authority_ceiling() -> None:
    client = FakeHubClient()
    protocol = edge_a_protocol()
    protocol["reference_qat_tolerance_policy"]["teacher_forced_nll"][
        "paired_upper_95pct_nats_per_scored_token_max"
    ] = 0.5

    result = E4bL0Builder(client).build(
        DEFAULT_ARTIFACTS,
        provisional_build_source="qat_mobile_transformers",
        reference_stacks=reference_stacks(),
        converter_lineage=converter_lineage(),
        edge_a_protocol=protocol,
        weight_verification_receipts=weight_receipts(client),
    )

    assert "edge_A_protocol:nll_tolerance_too_loose" in result["manifest"]["blockers"]


def test_l0_allows_no_provisional_candidate_without_claiming_execution() -> None:
    client = FakeHubClient()
    stacks = reference_stacks()
    transformers_stack = stacks["qat_mobile_transformers"]
    transformers_stack["identity_state"] = "frozen_unexecuted"
    transformers_stack["smoke_receipt"] = None
    transformers_stack["smoke_receipt_sha256"] = None

    result = E4bL0Builder(client).build(
        DEFAULT_ARTIFACTS,
        provisional_build_source=None,
        reference_stacks=stacks,
        converter_lineage=converter_lineage(),
        edge_a_protocol=edge_a_protocol(),
        weight_verification_receipts=weight_receipts(client),
    )

    assert result["manifest"]["state"] == "passed_scope"
    assert (
        result["manifest"]["mobile_qat_selection"][
            "provisional_build_source_candidate_id"
        ]
        is None
    )
    assert result["manifest"]["effects"]["execution_authorized"] is False
