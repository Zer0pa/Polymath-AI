"""Build the immutable L0 Gemma 4 E4B artifact and objective identity lock.

The builder intentionally reads only repository metadata, small identity files,
and SafeTensors headers. Model weights never land on the orchestration host.
Large-file SHA-256 values come from immutable Hugging Face LFS object IDs and
are reverified after provider-local acquisition before any foundry execution.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Any, Mapping, Protocol, Sequence

from polymath_ai.frontier.hardened_hf import HardenedHuggingFaceHubClient
from polymath_ai.frontier.safetensors_identity import (
    SafeTensorsIdentity,
    ShardedSafeTensorsIdentity,
    inspect_safetensors_file,
    inspect_sharded_safetensors,
)


L0_SCHEMA_VERSION = "gemma4_e4b_l0_parent_manifest_v1"
FULL_REVISION = re.compile(r"^[0-9a-f]{40}$")
GIT_OID = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MAX_SAFETENSORS_HEADER_BYTES = 16 * 1024 * 1024
EXPECTED_MODEL_CARD_LICENSE = "apache-2.0"
EXPECTED_MODEL_CARD_LICENSE_LINK = "https://ai.google.dev/gemma/docs/gemma_4_license"


@dataclass(frozen=True)
class ArtifactSpec:
    role: str
    repository: str
    revision: str


DEFAULT_ARTIFACTS = (
    ArtifactSpec(
        role="architecture_oracle",
        repository="google/gemma-4-E4B",
        revision="7aa32e6889efd6300124851b164f8b364314c3d8",
    ),
    ArtifactSpec(
        role="high_precision_task_oracle",
        repository="google/gemma-4-E4B-it",
        revision="a4c2d58be94dda072b918d9db64ee85c8ed34e3f",
    ),
    ArtifactSpec(
        role="qat_mobile_transformers",
        repository="google/gemma-4-E4B-it-qat-mobile-transformers",
        revision="9a78a5adac7bca7a9e421634e4b58f41ca7cbca3",
    ),
    ArtifactSpec(
        role="qat_mobile_compressed_tensors",
        repository="google/gemma-4-E4B-it-qat-mobile-ct",
        revision="d35137f462eb09dbe5acb5924018356d8e057134",
    ),
)

EXPECTED_ARTIFACTS = {artifact.role: artifact for artifact in DEFAULT_ARTIFACTS}
EXPECTED_TYING = {
    "architecture_oracle": True,
    "high_precision_task_oracle": True,
    "qat_mobile_transformers": False,
    "qat_mobile_compressed_tensors": False,
}
EXPECTED_REFERENCE_PACKAGES = {
    "high_precision_task_oracle": {
        "torch": "2.13.0+cpu",
        "transformers": "5.13.0",
        "safetensors": "0.8.0",
        "tokenizers": "0.22.2",
        "accelerate": "1.14.0",
        "numpy": "1.26.4",
    },
    "qat_mobile_transformers": {
        "torch": "2.13.0+cpu",
        "transformers": "5.13.0",
        "safetensors": "0.8.0",
        "tokenizers": "0.22.2",
        "accelerate": "1.14.0",
        "numpy": "1.26.4",
    },
    "qat_mobile_compressed_tensors": {
        "torch": "2.13.0+cpu",
        "transformers": "5.13.0",
        "safetensors": "0.8.0",
        "tokenizers": "0.22.2",
        "accelerate": "1.14.0",
        "numpy": "1.26.4",
        "compressed-tensors": "0.17.1",
    },
}
EXPECTED_ROPE_PARAMETERS = {
    "full_attention": {
        "partial_rotary_factor": 0.25,
        "rope_theta": 1_000_000.0,
        "rope_type": "proportional",
    },
    "sliding_attention": {
        "rope_theta": 10_000.0,
        "rope_type": "default",
    },
}


EXPECTED_ARCHITECTURE = {
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
}


IDENTITY_FILES = (
    "README.md",
    "config.json",
    "generation_config.json",
    "model.safetensors.index.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "chat_template.jinja",
    "processor_config.json",
    "preprocessor_config.json",
)
COMMON_REPOSITORY_FILES = {
    ".gitattributes",
    "README.md",
    "config.json",
    "generation_config.json",
    "model.safetensors",
    "processor_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
}
EXPECTED_REPOSITORY_FILES = {
    "architecture_oracle": COMMON_REPOSITORY_FILES,
    "high_precision_task_oracle": COMMON_REPOSITORY_FILES | {"chat_template.jinja"},
    "qat_mobile_transformers": COMMON_REPOSITORY_FILES
    | {"chat_template.jinja", "preprocessor_config.json"},
    "qat_mobile_compressed_tensors": COMMON_REPOSITORY_FILES
    | {
        "chat_template.jinja",
        "model.safetensors.index.json",
        "preprocessor_config.json",
    },
}

REQUIRED_CONVERTER_LINEAGE = {
    "exporter_revision",
    "converter_and_QAIRT_build",
    "QNN_API_version",
    "target_socModel",
    "target_dspArch",
    "qairt_core_foundry_receipt_sha256",
    "qairt_tool_hashes",
    "execution_runtime",
}
REQUIRED_EDGE_A_PROTOCOL = {
    "template",
    "teacher_forced_objective",
    "decode",
    "length_buckets",
    "evaluator",
    "target_shift",
    "full_answer_mask",
    "reference_qat_tolerance_policy",
}
REQUIRED_REFERENCE_STACK_ROLES = {
    "high_precision_task_oracle",
    "qat_mobile_transformers",
    "qat_mobile_compressed_tensors",
}
REQUIRED_REFERENCE_STACK_FIELDS = {
    "identity_state",
    "python",
    "platform",
    "packages",
    "package_artifacts",
    "package_lock_sha256",
    "package_lock_locator",
    "framework_source_identity",
    "dtype_and_runtime_policy",
    "smoke_receipt",
    "smoke_receipt_sha256",
}
REQUIRED_WEIGHT_RECEIPT_FIELDS = {
    "state",
    "raw_location_class",
    "report_locator",
    "report_sha256",
    "report",
}
REQUIRED_WEIGHT_REPORT_FIELDS = {
    "schema_version",
    "state",
    "role",
    "repository",
    "revision",
    "run_id",
    "completed_at_utc",
    "custody",
    "files",
}
REQUIRED_WEIGHT_CUSTODY_FIELDS = {
    "raw_location_class",
    "orchestration_host_weight_bytes",
    "secret_material_in_report",
    "full_file_streamed_for_hash",
    "verifier_binary",
    "verifier_binary_sha256",
}
ALLOWED_RAW_WEIGHT_LOCATIONS = {"provider_local", "phone_local_authority"}
REQUIRED_PACKAGE_ARTIFACT_FIELDS = {
    "version",
    "filename",
    "bytes",
    "sha256",
    "source",
}
REQUIRED_FRAMEWORK_COMPONENT_FIELDS = {
    "repository",
    "revision",
    "source_files",
}
REQUIRED_REFERENCE_SMOKE_FIELDS = {
    "schema_version",
    "state",
    "role",
    "repository",
    "revision",
    "run_id",
    "executed_at_utc",
    "raw_location_class",
    "framework_imports_passed",
    "tokenizer_load_passed",
    "tokenizer_template_bytes_match_task_oracle",
    "assistant_termination_token_id",
    "assistant_termination_emitted_once",
    "target_shift_and_full_answer_mask_fixture_passed",
    "chat_template_render_sha256",
    "artifact_load_passed",
    "missing_keys",
    "unexpected_keys",
    "artifact_native_quantized_modules_preserved",
    "deterministic_forward_replay_passed",
    "finite_logits_and_nll_passed",
    "peak_rss_bytes",
    "wall_time_seconds",
}
PHONE_AUTHORITY_SCHEMAS = {
    "forward_child": {
        "schema_version": "e4b_forward_phone_child_manifest_v1",
        "required": [
            "parent_L0_manifest_sha256",
            "exporter_converter_and_generator_identity",
            "graph_family_and_tensor_contract_sha256",
            "operator_partition_and_no_fallback_sha256",
            "context_family_sha256_and_sizes",
            "exact_loss_ABI_sha256",
            "quantization_identity",
            "target_socModel",
            "target_dspArch",
            "generated_at_utc",
        ],
    },
    "generation_child": {
        "schema_version": "e4b_generation_phone_child_manifest_v1",
        "required": [
            "parent_L0_manifest_sha256",
            "forward_child_sha256",
            "prefill_decode_or_recompute_context_family_sha256",
            "tokenizer_template_stop_and_decode_protocol_sha256",
            "KV_position_mask_and_shared_KV_contract_sha256",
            "coefficient_ABI_sha256",
            "selected_QAT_framework_reference_sha256",
            "generated_at_utc",
        ],
    },
    "phone_authority_root": {
        "schema_version": "e4b_phone_authority_root_manifest_v1",
        "required": [
            "parent_L0_manifest_sha256",
            "forward_child_sha256",
            "generation_child_sha256",
            "coefficient_ABI_sha256",
            "exact_loss_ABI_sha256",
            "tokenizer_template_and_QAT_reference_sha256",
            "device_runtime_identity_sha256",
            "state",
        ],
    },
}


class HubClient(Protocol):
    """Minimal injected Hub surface used by the deterministic builder."""

    def list_tree(self, artifact: ArtifactSpec) -> Sequence[Mapping[str, Any]]:
        """Return the immutable recursive repository tree."""

    def read_file(self, artifact: ArtifactSpec, path: str) -> bytes:
        """Return one small file at the immutable revision."""

    def read_range(
        self, artifact: ArtifactSpec, path: str, start: int, end: int
    ) -> bytes:
        """Return the inclusive byte range without materializing the full object."""


# Backwards-compatible public name. The implementation is fail-closed: bounded
# streaming, complete paginated inventories, exact range semantics, an explicit
# redirect allowlist, and cross-origin credential stripping.
HuggingFaceHubClient = HardenedHuggingFaceHubClient


def canonical_json_bytes(value: Any) -> bytes:
    reject_non_finite_numbers(value)
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def strict_json_bytes(value: bytes, *, label: str) -> Any:
    """Parse evidence JSON without duplicate keys or non-finite numbers."""

    def reject_constant(_value: str) -> None:
        raise ValueError("non-finite JSON constant")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, child in pairs:
            if key in result:
                raise ValueError("duplicate JSON object key")
            result[key] = child
        return result

    try:
        parsed = json.loads(
            value,
            parse_constant=reject_constant,
            object_pairs_hook=unique_object,
        )
        reject_non_finite_numbers(parsed)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        raise ValueError(f"{label} is not strict finite JSON") from None
    return parsed


def reject_non_finite_numbers(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite number is forbidden in canonical evidence")
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError("canonical evidence object keys must be strings")
            reject_non_finite_numbers(child)
        return
    if isinstance(value, (list, tuple)):
        for child in value:
            reject_non_finite_numbers(child)


class E4bL0Builder:
    """Build and validate one content-addressed L0 parent manifest."""

    def __init__(self, client: HubClient) -> None:
        self._client = client

    def build(
        self,
        artifacts: Sequence[ArtifactSpec],
        *,
        provisional_build_source: str | None,
        reference_stacks: Mapping[str, Mapping[str, Any]],
        converter_lineage: Mapping[str, Any],
        edge_a_protocol: Mapping[str, Any],
        weight_verification_receipts: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        reject_non_finite_numbers(reference_stacks)
        reject_non_finite_numbers(converter_lineage)
        reject_non_finite_numbers(edge_a_protocol)
        reject_non_finite_numbers(weight_verification_receipts)
        by_role = self._validate_artifacts(artifacts)
        inspected = {role: self._inspect(spec) for role, spec in by_role.items()}
        blockers = self._validate_cross_artifact_contract(
            inspected, provisional_build_source
        )
        blockers.extend(self._validate_converter_lineage(converter_lineage))
        blockers.extend(self._validate_edge_a_protocol(edge_a_protocol))
        blockers.extend(
            self._validate_reference_stacks(
                reference_stacks,
                provisional_build_source,
                inspected,
            )
        )
        blockers.extend(
            self._validate_weight_receipts(inspected, weight_verification_receipts)
        )
        blockers = sorted(set(blockers))
        selection_protocol = self._selection_protocol(inspected, reference_stacks)
        manifest = {
            "schema_version": L0_SCHEMA_VERSION,
            "state": "passed_scope" if not blockers else "blocked_fail_closed",
            "architecture_oracle": self._architecture_role(
                inspected["architecture_oracle"]
            ),
            "high_precision_task_oracle": self._task_oracle_role(
                inspected["high_precision_task_oracle"],
                edge_a_protocol,
                reference_stacks.get("high_precision_task_oracle", {}),
                weight_verification_receipts.get("high_precision_task_oracle", {}),
            ),
            "mobile_qat_candidates": {
                role: self._qat_role(
                    inspected[role],
                    reference_stacks.get(role, {}),
                    weight_verification_receipts.get(role, {}),
                )
                for role in ("qat_mobile_transformers", "qat_mobile_compressed_tensors")
            },
            "mobile_qat_selection": {
                "frozen_candidate_set_sha256": canonical_sha256(
                    [
                        {
                            "candidate_id": role,
                            "repository": inspected[role]["repository"],
                            "revision": inspected[role]["revision"],
                            "config_and_weight_shards_sha256": inspected[role][
                                "config_and_weight_shards_sha256"
                            ],
                        }
                        for role in (
                            "qat_mobile_transformers",
                            "qat_mobile_compressed_tensors",
                        )
                    ]
                ),
                "selection_protocol": selection_protocol,
                "selection_protocol_sha256": canonical_sha256(selection_protocol),
                "provisional_build_source_candidate_id": provisional_build_source,
                "numerical_admission_deferred_to": "L2_Edge_A_and_Edge_B",
            },
            "converter_lineage": dict(converter_lineage),
            "declared_phone_authority_schemas": {
                name: {
                    "schema": schema,
                    "schema_sha256": canonical_sha256(schema),
                    "state": "declared_uninstantiated",
                }
                for name, schema in PHONE_AUTHORITY_SCHEMAS.items()
            },
            "license_and_use_constraints": {
                "model_card_license": EXPECTED_MODEL_CARD_LICENSE,
                "license_link": EXPECTED_MODEL_CARD_LICENSE_LINK,
                "public_release_or_visibility_change": "forbidden_by_active_campaign",
                "raw_weight_egress": "provider_or_phone_only",
                "legal_opinion_claimed": False,
            },
            "blockers": blockers,
            "effects": {
                "closes_only": ["L0_artifact_objective_and_protocol_identity"]
                if not blockers
                else [],
                "promotion_allowed": False,
                "execution_authorized": False,
            },
            "custody": {
                "orchestration_host_model_weight_bytes": 0,
                "expected_weight_digests_source": "immutable_provider_metadata",
                "observed_weight_digests_source": "provider_local_full_file_receipts",
                "egress_result": "metadata_only",
            },
            "nonclaims": [
                "No model weights were downloaded to the orchestration host.",
                "L0 freezes identity and protocols; it does not establish numerical parity.",
                "No QNN context, phone execution, learning, or promotion claim is made.",
            ],
        }
        return {
            "manifest": manifest,
            "manifest_sha256": canonical_sha256(manifest),
        }

    def _inspect(self, artifact: ArtifactSpec) -> dict[str, Any]:
        tree = self._client.list_tree(artifact)
        file_index = self._file_index(tree)
        expected_files = EXPECTED_REPOSITORY_FILES[artifact.role]
        if set(file_index) != expected_files:
            missing = sorted(expected_files - set(file_index))
            unexpected = sorted(set(file_index) - expected_files)
            raise ValueError(
                f"{artifact.role}: immutable repository file set differs; "
                f"missing={missing}, unexpected={unexpected}"
            )
        repository_tree = self._repository_tree_identity(file_index)

        small_files = {
            path: self._content_record(artifact, path, file_index[path])
            for path in IDENTITY_FILES
            if path in file_index
        }
        weights = [
            self._weight_record(path, entry)
            for path, entry in sorted(file_index.items())
            if path.endswith(".safetensors")
        ]
        if artifact.role != "architecture_oracle" and not weights:
            raise ValueError(f"no SafeTensors weights found in {artifact.role}")

        config = strict_json_bytes(
            self._client.read_file(artifact, "config.json"),
            label=f"{artifact.role}:config.json",
        )
        if not isinstance(config, Mapping):
            raise ValueError(f"{artifact.role}:config.json root must be an object")
        architecture = self._architecture_snapshot(config)
        tokenizer = self._tokenizer_snapshot(artifact, small_files, file_index)
        safetensors = self._safetensors_snapshot(artifact, weights, file_index)
        model_card = self._model_card_snapshot(artifact, small_files)
        config_and_weights = [small_files["config.json"], *weights]
        if "model.safetensors.index.json" in small_files:
            config_and_weights.append(small_files["model.safetensors.index.json"])

        quantization_config = config.get("quantization_config")
        quantization_identity = {
            "config": quantization_config,
            "config_sha256": canonical_sha256(quantization_config),
            "safetensors": safetensors,
        }
        return {
            "role": artifact.role,
            "repository": artifact.repository,
            "revision": artifact.revision,
            "repository_tree": repository_tree,
            "repository_tree_sha256": canonical_sha256(repository_tree),
            "files": small_files,
            "weights": weights,
            "config": config,
            "architecture": architecture,
            "tokenizer": tokenizer,
            "safetensors": safetensors,
            "model_card": model_card,
            "execution_affecting_files": [
                small_files[path] for path in sorted(small_files)
            ],
            "execution_affecting_files_sha256": canonical_sha256(
                [small_files[path] for path in sorted(small_files)]
            ),
            "config_and_weight_shards_sha256": canonical_sha256(config_and_weights),
            "quantization_identity": quantization_identity,
            "quantization_and_encoding_manifest_sha256": canonical_sha256(
                quantization_identity
            ),
        }

    @staticmethod
    def _file_index(tree: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
        result: dict[str, Mapping[str, Any]] = {}
        casefolded: set[str] = set()
        for item in tree:
            if item.get("type") != "file" or not isinstance(item.get("path"), str):
                raise ValueError(
                    "immutable Hub tree contains a non-file or malformed entry"
                )
            path = str(item["path"])
            folded = path.casefold()
            if path in result or folded in casefolded:
                raise ValueError(f"duplicate or case-conflicting Hub path: {path}")
            result[path] = item
            casefolded.add(folded)
        return result

    @staticmethod
    def _repository_tree_identity(
        file_index: Mapping[str, Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for path, item in sorted(file_index.items()):
            size = item.get("size")
            oid = item.get("oid")
            if not isinstance(size, int) or isinstance(size, bool) or size < 0:
                raise ValueError(f"immutable Hub tree has invalid size: {path}")
            if not isinstance(oid, str) or GIT_OID.fullmatch(oid) is None:
                raise ValueError(f"immutable Hub tree has invalid Git OID: {path}")
            lfs = item.get("lfs")
            lfs_record = None
            if lfs is not None:
                if not isinstance(lfs, Mapping):
                    raise ValueError(
                        f"immutable Hub tree has malformed LFS record: {path}"
                    )
                lfs_oid = lfs.get("oid")
                lfs_size = lfs.get("size")
                if not isinstance(lfs_oid, str) or SHA256.fullmatch(lfs_oid) is None:
                    raise ValueError(
                        f"immutable Hub tree has invalid LFS SHA-256: {path}"
                    )
                if lfs_size != size:
                    raise ValueError(
                        f"immutable Hub tree has inconsistent LFS size: {path}"
                    )
                lfs_record = {"sha256": lfs_oid, "bytes": lfs_size}
            xet_hash = item.get("xetHash")
            if xet_hash is not None and (
                not isinstance(xet_hash, str) or SHA256.fullmatch(xet_hash) is None
            ):
                raise ValueError(f"immutable Hub tree has invalid Xet hash: {path}")
            records.append(
                {
                    "path": path,
                    "bytes": size,
                    "git_oid": oid,
                    "lfs": lfs_record,
                    "xet_hash": xet_hash,
                }
            )
        return records

    def _content_record(
        self, artifact: ArtifactSpec, path: str, tree_entry: Mapping[str, Any]
    ) -> dict[str, Any]:
        content = self._client.read_file(artifact, path)
        expected_size = int(tree_entry.get("size", -1))
        if expected_size != len(content):
            raise ValueError(f"size mismatch for {artifact.role}:{path}")
        return {
            "path": path,
            "bytes": len(content),
            "sha256": bytes_sha256(content),
            "git_oid": tree_entry.get("oid"),
            "hash_evidence": "content_bytes_at_immutable_revision",
        }

    @staticmethod
    def _weight_record(path: str, tree_entry: Mapping[str, Any]) -> dict[str, Any]:
        lfs = tree_entry.get("lfs")
        if not isinstance(lfs, Mapping):
            raise ValueError(f"weight is not LFS-addressed: {path}")
        digest = str(lfs.get("oid", ""))
        if not SHA256.fullmatch(digest):
            raise ValueError(f"invalid LFS SHA-256 for {path}")
        size = int(lfs.get("size", -1))
        if size <= 0 or size != int(tree_entry.get("size", -2)):
            raise ValueError(f"invalid LFS size for {path}")
        return {
            "path": path,
            "bytes": size,
            "sha256": digest,
            "git_oid": tree_entry.get("oid"),
            "xet_hash": tree_entry.get("xetHash"),
            "hash_evidence": "hugging_face_lfs_sha256_reverify_after_provider_download",
        }

    def _tokenizer_snapshot(
        self,
        artifact: ArtifactSpec,
        files: Mapping[str, Mapping[str, Any]],
        file_index: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any] | None:
        required = ("tokenizer.json", "tokenizer_config.json", "chat_template.jinja")
        if not all(path in file_index for path in required):
            return None
        tokenizer_bytes = self._client.read_file(artifact, "tokenizer.json")
        tokenizer_config_bytes = self._client.read_file(
            artifact, "tokenizer_config.json"
        )
        tokenizer = strict_json_bytes(
            tokenizer_bytes,
            label=f"{artifact.role}:tokenizer.json",
        )
        tokenizer_config = strict_json_bytes(
            tokenizer_config_bytes,
            label=f"{artifact.role}:tokenizer_config.json",
        )
        if not isinstance(tokenizer, Mapping) or not isinstance(
            tokenizer_config, Mapping
        ):
            raise ValueError(f"{artifact.role}:tokenizer roots must be objects")
        special_tokens = self._special_token_ids(tokenizer)
        chat_template = self._client.read_file(artifact, "chat_template.jinja")
        return {
            "tokenizer_json_sha256": files["tokenizer.json"]["sha256"],
            "tokenizer_config_sha256": files["tokenizer_config.json"]["sha256"],
            "tokenizer_config_semantic_sha256": canonical_sha256(tokenizer_config),
            "chat_template_sha256": files["chat_template.jinja"]["sha256"],
            "chat_template_emits_turn_terminator": b"<turn|>" in chat_template,
            "special_token_ids": special_tokens,
            "termination_contract": {
                "scored_span": "assistant_answer_plus_turn_termination",
                "assistant_turn_terminator": "<turn|>",
                "assistant_turn_terminator_id": special_tokens.get("<turn|>"),
                "prompt_and_control_tokens_ignored_by_primary_loss": True,
                "all_answer_and_termination_tokens_scored": True,
            },
        }

    def _model_card_snapshot(
        self, artifact: ArtifactSpec, files: Mapping[str, Mapping[str, Any]]
    ) -> dict[str, Any]:
        if "README.md" not in files:
            return {"present": False, "license": None}
        text = self._client.read_file(artifact, "README.md").decode("utf-8")
        match = re.search(r"(?m)^license:\s*([^\s]+)\s*$", text)
        link_match = re.search(r"(?m)^license_link:\s*([^\s]+)\s*$", text)
        return {
            "present": True,
            "sha256": files["README.md"]["sha256"],
            "license": match.group(1) if match else None,
            "license_link": link_match.group(1) if link_match else None,
            "legal_opinion_claimed": False,
        }

    @staticmethod
    def _special_token_ids(tokenizer: Mapping[str, Any]) -> dict[str, int]:
        wanted = {"<bos>", "<eos>", "<pad>", "<unk>", "<|turn>", "<turn|>"}
        result: dict[str, int] = {}
        for token in tokenizer.get("added_tokens", []):
            if not isinstance(token, Mapping):
                continue
            content = token.get("content")
            token_id = token.get("id")
            if content in wanted and isinstance(token_id, int):
                result[str(content)] = token_id
        return dict(sorted(result.items()))

    def _safetensors_snapshot(
        self,
        artifact: ArtifactSpec,
        weights: Sequence[Mapping[str, Any]],
        file_index: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any] | None:
        if not weights:
            return None
        file_sizes = {str(item["path"]): int(item["bytes"]) for item in weights}

        def read_range(path: str, start: int, end: int) -> bytes:
            return self._client.read_range(artifact, path, start, end)

        index_path = "model.safetensors.index.json"
        if index_path in file_index:
            index_bytes = self._client.read_file(artifact, index_path)
            identity: SafeTensorsIdentity | ShardedSafeTensorsIdentity = (
                inspect_sharded_safetensors(
                    index_bytes,
                    file_sizes,
                    read_range,
                    max_header_bytes=MAX_SAFETENSORS_HEADER_BYTES,
                )
            )
        elif len(weights) == 1:
            path = str(weights[0]["path"])
            identity = inspect_safetensors_file(
                path,
                file_sizes[path],
                read_range,
                max_header_bytes=MAX_SAFETENSORS_HEADER_BYTES,
            )
        else:
            raise ValueError(
                f"{artifact.role}: sharded SafeTensors artifact has no exact index"
            )
        return self._safetensors_identity_snapshot(identity)

    @classmethod
    def _safetensors_identity_snapshot(
        cls,
        identity: SafeTensorsIdentity | ShardedSafeTensorsIdentity,
    ) -> dict[str, Any]:
        shards = (
            identity.shards
            if isinstance(identity, ShardedSafeTensorsIdentity)
            else (identity,)
        )
        tensors = tuple(tensor for shard in shards for tensor in shard.tensors)
        tensor_names = sorted(tensor.name for tensor in tensors)
        dtype_counts = Counter(tensor.dtype for tensor in tensors)
        critical = {
            tensor.name: {
                "dtype": tensor.dtype,
                "shape": list(tensor.shape),
                "data_offsets": [tensor.data_start, tensor.data_end],
                "file_name": shard.file_name,
            }
            for shard in shards
            for tensor in shard.tensors
            if cls._critical_tensor_name(tensor.name)
        }
        snapshot: dict[str, Any] = {
            "structural_validation": "strict_header_span_and_exact_inventory_passed",
            "weight_file_count": len(shards),
            "weight_files": [shard.record() for shard in shards],
            "tensor_count": len(tensor_names),
            "tensor_name_root_sha256": canonical_sha256(tensor_names),
            "dtype_counts": dict(sorted(dtype_counts.items())),
            "critical_tensor_contracts": dict(sorted(critical.items())),
            "critical_tensor_contracts_sha256": canonical_sha256(critical),
        }
        if isinstance(identity, ShardedSafeTensorsIdentity):
            snapshot["sharded_inventory"] = identity.record()
        else:
            snapshot.update(
                {
                    "weight_file": identity.file_name,
                    "header_bytes": identity.header_size,
                    "header_sha256": identity.header_sha256,
                    "metadata_sha256": identity.metadata_sha256,
                    "tensor_contracts_sha256": identity.tensor_contracts_sha256,
                }
            )
        return snapshot

    @staticmethod
    def _critical_tensor_name(name: str) -> bool:
        selectors = (
            "lm_head",
            "embed_tokens_per_layer",
            "layers.0.per_layer_",
            "layers.5.per_layer_",
            "layers.24.per_layer_",
            "layers.41.per_layer_",
        )
        return any(selector in name for selector in selectors)

    @staticmethod
    def _architecture_snapshot(config: Mapping[str, Any]) -> dict[str, Any]:
        text = config.get("text_config", config)
        if not isinstance(text, Mapping):
            raise ValueError("config has no text architecture mapping")
        layer_types = list(text.get("layer_types", []))
        snapshot = {key: text.get(key) for key in EXPECTED_ARCHITECTURE}
        snapshot.update(
            {
                "top_level_model_type": config.get("model_type"),
                "text_model_type": text.get("model_type"),
                "architectures": config.get("architectures"),
                "layer_types": layer_types,
                "local_layer_count": layer_types.count("sliding_attention"),
                "global_layer_count": layer_types.count("full_attention"),
                "rope_parameters": text.get("rope_parameters"),
                "tie_word_embeddings": text.get(
                    "tie_word_embeddings", config.get("tie_word_embeddings")
                ),
                "hidden_activation": text.get("hidden_activation"),
                "attention_k_eq_v": text.get("attention_k_eq_v"),
                "attention_bias": text.get("attention_bias"),
                "use_cache": text.get("use_cache"),
            }
        )
        return snapshot

    @staticmethod
    def _validate_artifacts(
        artifacts: Sequence[ArtifactSpec],
    ) -> dict[str, ArtifactSpec]:
        if len(artifacts) != len({artifact.role for artifact in artifacts}):
            raise ValueError("duplicate artifact role")
        by_role = {artifact.role: artifact for artifact in artifacts}
        expected = set(EXPECTED_ARTIFACTS)
        if set(by_role) != expected:
            raise ValueError(f"artifact roles must equal {sorted(expected)}")
        for artifact in artifacts:
            if not FULL_REVISION.fullmatch(artifact.revision):
                raise ValueError(f"revision must be immutable SHA for {artifact.role}")
            expected_artifact = EXPECTED_ARTIFACTS[artifact.role]
            if artifact.repository != expected_artifact.repository:
                raise ValueError(f"unexpected official repository for {artifact.role}")
            if artifact.revision != expected_artifact.revision:
                raise ValueError(f"unexpected immutable revision for {artifact.role}")
        return by_role

    def _validate_cross_artifact_contract(
        self, inspected: Mapping[str, Mapping[str, Any]], provisional: str | None
    ) -> list[str]:
        blockers: list[str] = []
        for role, artifact in inspected.items():
            architecture = artifact["architecture"]
            for key, expected in EXPECTED_ARCHITECTURE.items():
                if architecture.get(key) != expected:
                    blockers.append(f"{role}:architecture:{key}")
            if architecture.get("top_level_model_type") != "gemma4":
                blockers.append(f"{role}:architecture:top_level_model_type")
            if architecture.get("text_model_type") != "gemma4_text":
                blockers.append(f"{role}:architecture:text_model_type")
            if architecture.get("rope_parameters") != EXPECTED_ROPE_PARAMETERS:
                blockers.append(f"{role}:architecture:rope_parameters")
            if architecture.get("hidden_activation") != "gelu_pytorch_tanh":
                blockers.append(f"{role}:architecture:hidden_activation")
            if architecture.get("attention_k_eq_v") is not False:
                blockers.append(f"{role}:architecture:attention_k_eq_v")
            if architecture.get("attention_bias") is not False:
                blockers.append(f"{role}:architecture:attention_bias")
            if architecture.get("use_cache") is not True:
                blockers.append(f"{role}:architecture:use_cache")
            if architecture.get("tie_word_embeddings") is not EXPECTED_TYING[role]:
                blockers.append(f"{role}:architecture:tie_word_embeddings")
            if not self._valid_layer_pattern(architecture.get("layer_types", [])):
                blockers.append(f"{role}:architecture:layer_types")
            if artifact["model_card"].get("license") != EXPECTED_MODEL_CARD_LICENSE:
                blockers.append(f"{role}:license:unexpected_identifier")
            if (
                artifact["model_card"].get("license_link")
                != EXPECTED_MODEL_CARD_LICENSE_LINK
            ):
                blockers.append(f"{role}:license:unexpected_link")
            tokenizer = artifact.get("tokenizer")
            if role != "architecture_oracle" and not tokenizer:
                blockers.append(f"{role}:tokenizer_contract_missing")
            elif (
                tokenizer
                and tokenizer["termination_contract"]["assistant_turn_terminator_id"]
                is None
            ):
                blockers.append(f"{role}:termination_token_missing")
            elif (
                tokenizer
                and tokenizer["chat_template_emits_turn_terminator"] is not True
            ):
                blockers.append(f"{role}:chat_template_does_not_emit_termination")

            if role.startswith("qat_"):
                critical = artifact["safetensors"]["critical_tensor_contracts"]
                if not any(name.startswith("lm_head.") for name in critical):
                    blockers.append(f"{role}:separate_lm_head_tensor_missing")
                if not any("embed_tokens_per_layer" in name for name in critical):
                    blockers.append(f"{role}:PLE_tensor_missing")

        task = inspected["high_precision_task_oracle"]["tokenizer"]
        for role in ("qat_mobile_transformers", "qat_mobile_compressed_tensors"):
            candidate = inspected[role]["tokenizer"]
            if task["tokenizer_json_sha256"] != candidate["tokenizer_json_sha256"]:
                blockers.append(f"{role}:tokenizer_json_differs_from_task_oracle")
            if task["chat_template_sha256"] != candidate["chat_template_sha256"]:
                blockers.append(f"{role}:chat_template_differs_from_task_oracle")
            if (
                task["tokenizer_config_semantic_sha256"]
                != candidate["tokenizer_config_semantic_sha256"]
            ):
                blockers.append(
                    f"{role}:tokenizer_config_semantics_differ_from_task_oracle"
                )

        allowed = {None, "qat_mobile_transformers", "qat_mobile_compressed_tensors"}
        if provisional not in allowed:
            blockers.append("mobile_qat_selection:unknown_provisional_candidate")
        return sorted(blockers)

    @staticmethod
    def _validate_converter_lineage(converter: Mapping[str, Any]) -> list[str]:
        blockers: list[str] = []
        if set(converter) != REQUIRED_CONVERTER_LINEAGE:
            blockers.append("converter_lineage:wrong_field_set")
            return blockers
        if not FULL_REVISION.fullmatch(str(converter.get("exporter_revision", ""))):
            blockers.append("converter_lineage:exporter_revision_not_full_sha")
        if converter.get("converter_and_QAIRT_build") != "v2.44.0.260225143659":
            blockers.append("converter_lineage:wrong_QAIRT_build")
        if converter.get("QNN_API_version") != "2.34.0":
            blockers.append("converter_lineage:wrong_QNN_API_version")
        if converter.get("target_socModel") != 69:
            blockers.append("converter_lineage:wrong_socModel")
        if converter.get("target_dspArch") != 79:
            blockers.append("converter_lineage:wrong_dspArch")
        if converter.get("execution_runtime") != "ubuntu_22_04_direct_chroot":
            blockers.append("converter_lineage:wrong_execution_runtime")
        if not SHA256.fullmatch(
            str(converter.get("qairt_core_foundry_receipt_sha256", ""))
        ):
            blockers.append("converter_lineage:bad_core_foundry_receipt")
        tool_hashes = converter.get("qairt_tool_hashes")
        required_tools = {
            "qnn_context_binary_generator",
            "qnn_context_binary_utility",
            "qnn_net_run",
            "libQnnHtp",
            "libQnnSystem",
        }
        if not isinstance(tool_hashes, Mapping) or set(tool_hashes) != required_tools:
            blockers.append("converter_lineage:wrong_tool_hash_set")
        elif any(not SHA256.fullmatch(str(value)) for value in tool_hashes.values()):
            blockers.append("converter_lineage:bad_tool_hash")
        return blockers

    @staticmethod
    def _validate_edge_a_protocol(protocol: Mapping[str, Any]) -> list[str]:
        blockers: list[str] = []
        if set(protocol) != REQUIRED_EDGE_A_PROTOCOL:
            blockers.append("edge_A_protocol:wrong_field_set")
            return blockers
        if protocol.get("template") != "exact_repository_chat_template":
            blockers.append("edge_A_protocol:wrong_template")
        if (
            protocol.get("teacher_forced_objective")
            != "full_answer_plus_turn_termination_masked_NLL"
        ):
            blockers.append("edge_A_protocol:wrong_teacher_forced_objective")
        if protocol.get("target_shift") != "causal_next_token":
            blockers.append("edge_A_protocol:wrong_target_shift")
        if protocol.get("full_answer_mask") is not True:
            blockers.append("edge_A_protocol:full_answer_mask_not_true")
        if (
            protocol.get("evaluator")
            != "token_weighted_nll_plus_deterministic_generation_behavior"
        ):
            blockers.append("edge_A_protocol:wrong_evaluator")
        buckets = protocol.get("length_buckets")
        if buckets != [16, 64, 128]:
            blockers.append("edge_A_protocol:wrong_initial_length_buckets")
        decode = protocol.get("decode")
        expected_decode = {
            "do_sample": False,
            "max_new_tokens": 64,
            "seed": 0,
            "stop_token": "<turn|>",
        }
        if decode != expected_decode:
            blockers.append("edge_A_protocol:wrong_decode_contract")
        tolerance = protocol.get("reference_qat_tolerance_policy")
        required_tolerance = {
            "policy_state",
            "teacher_forced_logits",
            "teacher_forced_nll",
            "deterministic_decode",
            "behavioral_suite",
        }
        if not isinstance(tolerance, Mapping) or set(tolerance) != required_tolerance:
            blockers.append("edge_A_protocol:missing_tolerance_policy")
        elif tolerance.get("policy_state") != "predeclared_before_target_observation":
            blockers.append("edge_A_protocol:tolerance_policy_not_predeclared")
        else:
            blockers.extend(E4bL0Builder._validate_edge_a_tolerance(tolerance))
        return blockers

    @staticmethod
    def _validate_edge_a_tolerance(tolerance: Mapping[str, Any]) -> list[str]:
        blockers: list[str] = []
        logits = tolerance.get("teacher_forced_logits")
        expected_logits = {
            "metric",
            "centered_nrmse_max",
            "top1_agreement_min",
            "scored_positions_only",
        }
        if not isinstance(logits, Mapping) or set(logits) != expected_logits:
            blockers.append("edge_A_protocol:bad_logit_tolerance_fields")
        else:
            if (
                logits.get("metric")
                != "paired_centered_full_vocab_logit_nrmse_and_top1"
            ):
                blockers.append("edge_A_protocol:bad_logit_metric")
            if not E4bL0Builder._number_in_range(
                logits.get("centered_nrmse_max"), 0.0, 0.05
            ):
                blockers.append("edge_A_protocol:logit_nrmse_tolerance_too_loose")
            if not E4bL0Builder._number_in_range(
                logits.get("top1_agreement_min"), 0.95, 1.0
            ):
                blockers.append("edge_A_protocol:logit_top1_tolerance_too_loose")
            if logits.get("scored_positions_only") is not True:
                blockers.append("edge_A_protocol:logit_positions_not_exact")

        nll = tolerance.get("teacher_forced_nll")
        expected_nll = {
            "metric",
            "paired_upper_95pct_nats_per_scored_token_max",
            "exact_mask_denominator",
        }
        if not isinstance(nll, Mapping) or set(nll) != expected_nll:
            blockers.append("edge_A_protocol:bad_nll_tolerance_fields")
        else:
            if nll.get("metric") != "paired_token_weighted_delta_nll":
                blockers.append("edge_A_protocol:bad_nll_metric")
            if not E4bL0Builder._number_in_range(
                nll.get("paired_upper_95pct_nats_per_scored_token_max"), 0.0, 0.02
            ):
                blockers.append("edge_A_protocol:nll_tolerance_too_loose")
            if nll.get("exact_mask_denominator") is not True:
                blockers.append("edge_A_protocol:nll_denominator_not_exact")

        decode = tolerance.get("deterministic_decode")
        expected_decode = {
            "metric",
            "sequence_exact_match_rate_min",
            "normalized_edit_distance_mean_max",
            "stop_and_max_length_exact",
        }
        if not isinstance(decode, Mapping) or set(decode) != expected_decode:
            blockers.append("edge_A_protocol:bad_decode_tolerance_fields")
        else:
            if decode.get("metric") != "paired_greedy_token_sequence":
                blockers.append("edge_A_protocol:bad_decode_metric")
            if not E4bL0Builder._number_in_range(
                decode.get("sequence_exact_match_rate_min"), 0.90, 1.0
            ):
                blockers.append(
                    "edge_A_protocol:decode_exact_match_tolerance_too_loose"
                )
            if not E4bL0Builder._number_in_range(
                decode.get("normalized_edit_distance_mean_max"), 0.0, 0.02
            ):
                blockers.append("edge_A_protocol:decode_edit_tolerance_too_loose")
            if decode.get("stop_and_max_length_exact") is not True:
                blockers.append("edge_A_protocol:decode_stop_contract_not_exact")

        behavior = tolerance.get("behavioral_suite")
        expected_behavior = {
            "metric",
            "paired_lower_95pct_score_delta_min",
            "evaluator_revision",
        }
        if not isinstance(behavior, Mapping) or set(behavior) != expected_behavior:
            blockers.append("edge_A_protocol:bad_behavior_tolerance_fields")
        else:
            if behavior.get("metric") != "frozen_paired_behavior_score_delta":
                blockers.append("edge_A_protocol:bad_behavior_metric")
            if not E4bL0Builder._number_in_range(
                behavior.get("paired_lower_95pct_score_delta_min"), -0.01, 1.0
            ):
                blockers.append("edge_A_protocol:behavior_tolerance_too_loose")
            if not FULL_REVISION.fullmatch(str(behavior.get("evaluator_revision", ""))):
                blockers.append("edge_A_protocol:behavior_evaluator_not_immutable")
        return blockers

    @staticmethod
    def _number_in_range(value: Any, minimum: float, maximum: float) -> bool:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
            and minimum <= float(value) <= maximum
        )

    @staticmethod
    def _validate_reference_stacks(
        stacks: Mapping[str, Mapping[str, Any]],
        provisional: str | None,
        inspected: Mapping[str, Mapping[str, Any]],
    ) -> list[str]:
        blockers: list[str] = []
        if set(stacks) != REQUIRED_REFERENCE_STACK_ROLES:
            blockers.append("reference_stacks:wrong_role_set")
            return blockers
        for role in sorted(REQUIRED_REFERENCE_STACK_ROLES):
            stack = stacks.get(role)
            if (
                not isinstance(stack, Mapping)
                or set(stack) != REQUIRED_REFERENCE_STACK_FIELDS
            ):
                blockers.append(f"{role}:reference_stack:wrong_field_set")
                continue
            state = stack.get("identity_state")
            if state not in {"frozen_unexecuted", "passed_scope"}:
                blockers.append(f"{role}:reference_stack:bad_identity_state")
            if stack.get("python") != "3.11":
                blockers.append(f"{role}:reference_stack:wrong_python")
            if stack.get("platform") != "linux_x86_64":
                blockers.append(f"{role}:reference_stack:wrong_platform")
            if stack.get("packages") != EXPECTED_REFERENCE_PACKAGES[role]:
                blockers.append(f"{role}:reference_stack:wrong_packages")
            package_artifacts = stack.get("package_artifacts")
            blockers.extend(
                E4bL0Builder._validate_package_artifacts(
                    role,
                    EXPECTED_REFERENCE_PACKAGES[role],
                    package_artifacts,
                )
            )
            if not isinstance(package_artifacts, Mapping) or stack.get(
                "package_lock_sha256"
            ) != canonical_sha256(package_artifacts):
                blockers.append(f"{role}:reference_stack:bad_package_lock_sha256")
            if not E4bL0Builder._valid_reference_locator(
                stack.get("package_lock_locator")
            ):
                blockers.append(f"{role}:reference_stack:missing_package_lock_locator")
            blockers.extend(
                E4bL0Builder._validate_framework_source_identity(
                    role,
                    stack.get("framework_source_identity"),
                )
            )
            blockers.extend(
                E4bL0Builder._validate_dtype_runtime_policy(
                    role,
                    stack.get("dtype_and_runtime_policy"),
                )
            )
            smoke_receipt = stack.get("smoke_receipt")
            smoke_sha = stack.get("smoke_receipt_sha256")
            if smoke_receipt is None:
                if smoke_sha is not None:
                    blockers.append(f"{role}:reference_stack:orphan_smoke_sha256")
            elif not isinstance(smoke_receipt, Mapping):
                blockers.append(f"{role}:reference_stack:bad_smoke_receipt")
            else:
                if smoke_sha != canonical_sha256(smoke_receipt):
                    blockers.append(f"{role}:reference_stack:bad_smoke_receipt_sha256")
                blockers.extend(
                    E4bL0Builder._validate_reference_smoke(
                        role,
                        inspected[role],
                        smoke_receipt,
                    )
                )
            if role == provisional:
                if state != "passed_scope":
                    blockers.append(
                        f"{role}:reference_stack:provisional_not_executable"
                    )
                if not isinstance(smoke_receipt, Mapping):
                    blockers.append(f"{role}:reference_stack:provisional_smoke_missing")
        if provisional is None:
            blockers.append("reference_stacks:no_provisional_build_source_selected")
        return blockers

    @staticmethod
    def _valid_reference_locator(locator: Any) -> bool:
        if (
            not isinstance(locator, str)
            or not locator
            or "?" in locator
            or "#" in locator
        ):
            return False
        return locator.startswith(("runpod://", "immutable://"))

    @staticmethod
    def _validate_package_artifacts(
        role: str,
        expected_packages: Mapping[str, str],
        artifacts: Any,
    ) -> list[str]:
        prefix = f"{role}:reference_stack"
        if not isinstance(artifacts, Mapping) or not set(expected_packages).issubset(
            artifacts
        ):
            return [f"{prefix}:missing_critical_package_artifacts"]
        blockers: list[str] = []
        for package, record in artifacts.items():
            if (
                not isinstance(package, str)
                or not package
                or package != package.lower()
            ):
                blockers.append(f"{prefix}:bad_package_name")
                continue
            if (
                not isinstance(record, Mapping)
                or set(record) != REQUIRED_PACKAGE_ARTIFACT_FIELDS
            ):
                blockers.append(f"{prefix}:{package}:bad_artifact_record")
                continue
            if (
                package in expected_packages
                and record.get("version") != expected_packages[package]
            ):
                blockers.append(f"{prefix}:{package}:artifact_version_mismatch")
            filename = record.get("filename")
            if (
                not isinstance(filename, str)
                or not filename
                or "/" in filename
                or "\\" in filename
            ):
                blockers.append(f"{prefix}:{package}:bad_artifact_filename")
            size = record.get("bytes")
            if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
                blockers.append(f"{prefix}:{package}:bad_artifact_size")
            if not SHA256.fullmatch(str(record.get("sha256", ""))):
                blockers.append(f"{prefix}:{package}:bad_artifact_sha256")
            if record.get("source") not in {
                "pypi_exact_file",
                "pytorch_wheel_index_exact_file",
                "vcs_checkout_exact_revision",
            }:
                blockers.append(f"{prefix}:{package}:bad_artifact_source")
        return blockers

    @staticmethod
    def _validate_framework_source_identity(role: str, source: Any) -> list[str]:
        prefix = f"{role}:reference_stack"
        expected_components = {"torch", "transformers"}
        if role == "qat_mobile_compressed_tensors":
            expected_components.add("compressed_tensors")
        if not isinstance(source, Mapping) or set(source) != expected_components:
            return [f"{prefix}:wrong_framework_component_set"]
        expected_repositories = {
            "torch": "pytorch/pytorch",
            "transformers": "huggingface/transformers",
            "compressed_tensors": "vllm-project/compressed-tensors",
        }
        blockers: list[str] = []
        for component in sorted(expected_components):
            record = source.get(component)
            if (
                not isinstance(record, Mapping)
                or set(record) != REQUIRED_FRAMEWORK_COMPONENT_FIELDS
            ):
                blockers.append(f"{prefix}:{component}:bad_source_record")
                continue
            if record.get("repository") != expected_repositories[component]:
                blockers.append(f"{prefix}:{component}:wrong_repository")
            if not FULL_REVISION.fullmatch(str(record.get("revision", ""))):
                blockers.append(f"{prefix}:{component}:bad_revision")
            source_files = record.get("source_files")
            if not isinstance(source_files, Mapping) or not source_files:
                blockers.append(f"{prefix}:{component}:source_files_missing")
                continue
            for path, digest in source_files.items():
                if (
                    not isinstance(path, str)
                    or not path
                    or path.startswith("/")
                    or ".." in path.split("/")
                    or not SHA256.fullmatch(str(digest))
                ):
                    blockers.append(f"{prefix}:{component}:bad_source_file_identity")
                    break
        return blockers

    @staticmethod
    def _validate_dtype_runtime_policy(role: str, policy: Any) -> list[str]:
        prefix = f"{role}:reference_stack"
        required = {
            "weight_storage",
            "compute_dtype",
            "accumulation_dtype",
            "device",
            "artifact_native_quantization_required",
            "silent_requantization_or_dequantized_substitution",
            "trust_remote_code",
        }
        if not isinstance(policy, Mapping) or set(policy) != required:
            return [f"{prefix}:bad_dtype_runtime_policy_fields"]
        blockers: list[str] = []
        if policy.get("device") != "cpu":
            blockers.append(f"{prefix}:reference_device_not_cpu")
        if policy.get("accumulation_dtype") != "float32":
            blockers.append(f"{prefix}:accumulation_not_float32")
        if (
            policy.get("silent_requantization_or_dequantized_substitution")
            != "forbidden"
        ):
            blockers.append(f"{prefix}:silent_substitution_not_forbidden")
        if policy.get("trust_remote_code") is not False:
            blockers.append(f"{prefix}:trust_remote_code_not_false")
        native_required = policy.get("artifact_native_quantization_required")
        if native_required is not role.startswith("qat_"):
            blockers.append(f"{prefix}:native_quantization_policy_mismatch")
        if not isinstance(policy.get("weight_storage"), str) or not policy.get(
            "weight_storage"
        ):
            blockers.append(f"{prefix}:weight_storage_missing")
        if not isinstance(policy.get("compute_dtype"), str) or not policy.get(
            "compute_dtype"
        ):
            blockers.append(f"{prefix}:compute_dtype_missing")
        return blockers

    @staticmethod
    def _validate_reference_smoke(
        role: str,
        artifact: Mapping[str, Any],
        receipt: Mapping[str, Any],
    ) -> list[str]:
        prefix = f"{role}:reference_stack"
        if set(receipt) != REQUIRED_REFERENCE_SMOKE_FIELDS:
            return [f"{prefix}:smoke_wrong_field_set"]
        expected = {
            "schema_version": "e4b_reference_stack_smoke_v1",
            "state": "passed_scope",
            "role": role,
            "repository": artifact["repository"],
            "revision": artifact["revision"],
            "raw_location_class": "provider_local",
            "framework_imports_passed": True,
            "tokenizer_load_passed": True,
            "tokenizer_template_bytes_match_task_oracle": True,
            "assistant_termination_token_id": 106,
            "assistant_termination_emitted_once": True,
            "target_shift_and_full_answer_mask_fixture_passed": True,
            "artifact_load_passed": True,
            "artifact_native_quantized_modules_preserved": role.startswith("qat_"),
            "deterministic_forward_replay_passed": True,
            "finite_logits_and_nll_passed": True,
        }
        blockers: list[str] = []
        for field, value in expected.items():
            if receipt.get(field) != value:
                blockers.append(f"{prefix}:smoke_{field}_mismatch")
        if receipt.get("missing_keys") != [] or receipt.get("unexpected_keys") != []:
            blockers.append(f"{prefix}:smoke_state_dict_not_exact")
        if not SHA256.fullmatch(str(receipt.get("chat_template_render_sha256", ""))):
            blockers.append(f"{prefix}:smoke_chat_template_render_sha256_invalid")
        if not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", str(receipt.get("run_id", ""))
        ):
            blockers.append(f"{prefix}:smoke_bad_run_id")
        if not re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
            str(receipt.get("executed_at_utc", "")),
        ):
            blockers.append(f"{prefix}:smoke_bad_executed_at_utc")
        peak_rss = receipt.get("peak_rss_bytes")
        if (
            not isinstance(peak_rss, int)
            or isinstance(peak_rss, bool)
            or peak_rss <= 0
            or peak_rss > 16_000_000_000
        ):
            blockers.append(f"{prefix}:smoke_peak_rss_outside_provider_envelope")
        wall_time = receipt.get("wall_time_seconds")
        if (
            not isinstance(wall_time, (int, float))
            or isinstance(wall_time, bool)
            or wall_time <= 0
            or not math.isfinite(float(wall_time))
        ):
            blockers.append(f"{prefix}:smoke_bad_wall_time")
        return blockers

    @staticmethod
    def _validate_weight_receipts(
        inspected: Mapping[str, Mapping[str, Any]],
        receipts: Mapping[str, Mapping[str, Any]],
    ) -> list[str]:
        required_roles = {
            "high_precision_task_oracle",
            "qat_mobile_transformers",
            "qat_mobile_compressed_tensors",
        }
        blockers: list[str] = []
        if set(receipts) != required_roles:
            blockers.append("weight_receipts:wrong_role_set")
            return blockers
        for role in sorted(required_roles):
            receipt = receipts.get(role)
            if (
                not isinstance(receipt, Mapping)
                or set(receipt) != REQUIRED_WEIGHT_RECEIPT_FIELDS
            ):
                blockers.append(f"{role}:weight_receipt:wrong_field_set")
                continue
            if receipt.get("state") != "passed_scope":
                blockers.append(f"{role}:weight_receipt:not_passed_scope")
            raw_location = receipt.get("raw_location_class")
            if raw_location not in ALLOWED_RAW_WEIGHT_LOCATIONS:
                blockers.append(f"{role}:weight_receipt:invalid_raw_location")
            if not E4bL0Builder._valid_weight_report_locator(
                receipt.get("report_locator"), raw_location
            ):
                blockers.append(f"{role}:weight_receipt:missing_report_locator")
            report = receipt.get("report")
            if not isinstance(report, Mapping):
                blockers.append(f"{role}:weight_receipt:report_missing")
                continue
            if receipt.get("report_sha256") != canonical_sha256(report):
                blockers.append(f"{role}:weight_receipt:bad_report_sha256")
            blockers.extend(
                E4bL0Builder._validate_weight_report(
                    role,
                    inspected[role],
                    raw_location,
                    report,
                )
            )
        return blockers

    @staticmethod
    def _valid_weight_report_locator(locator: Any, raw_location: Any) -> bool:
        if (
            not isinstance(locator, str)
            or not locator
            or "?" in locator
            or "#" in locator
        ):
            return False
        prefix = {
            "provider_local": "runpod://",
            "phone_local_authority": "phone://FY25013101C8/",
        }.get(raw_location)
        return prefix is not None and locator.startswith(prefix)

    @staticmethod
    def _validate_weight_report(
        role: str,
        artifact: Mapping[str, Any],
        raw_location: Any,
        report: Mapping[str, Any],
    ) -> list[str]:
        prefix = f"{role}:weight_receipt"
        blockers: list[str] = []
        if set(report) != REQUIRED_WEIGHT_REPORT_FIELDS:
            return [f"{prefix}:report_wrong_field_set"]
        expected_identity = {
            "schema_version": "e4b_provider_weight_verification_v1",
            "state": "passed_scope",
            "role": role,
            "repository": artifact["repository"],
            "revision": artifact["revision"],
        }
        for field, expected in expected_identity.items():
            if report.get(field) != expected:
                blockers.append(f"{prefix}:report_{field}_mismatch")
        if not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", str(report.get("run_id", ""))
        ):
            blockers.append(f"{prefix}:report_bad_run_id")
        if not re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
            str(report.get("completed_at_utc", "")),
        ):
            blockers.append(f"{prefix}:report_bad_completed_at_utc")
        blockers.extend(
            E4bL0Builder._validate_weight_custody(
                role, raw_location, report.get("custody")
            )
        )
        blockers.extend(
            E4bL0Builder._validate_weight_files(role, artifact, raw_location, report)
        )
        return blockers

    @staticmethod
    def _validate_weight_custody(
        role: str, raw_location: Any, custody: Any
    ) -> list[str]:
        prefix = f"{role}:weight_receipt"
        if (
            not isinstance(custody, Mapping)
            or set(custody) != REQUIRED_WEIGHT_CUSTODY_FIELDS
        ):
            return [f"{prefix}:custody_wrong_field_set"]
        blockers: list[str] = []
        expected = {
            "raw_location_class": raw_location,
            "orchestration_host_weight_bytes": 0,
            "secret_material_in_report": False,
            "full_file_streamed_for_hash": True,
        }
        for field, value in expected.items():
            if custody.get(field) != value:
                blockers.append(f"{prefix}:custody_{field}_mismatch")
        if not isinstance(custody.get("verifier_binary"), str) or not custody.get(
            "verifier_binary"
        ):
            blockers.append(f"{prefix}:custody_verifier_missing")
        if not SHA256.fullmatch(str(custody.get("verifier_binary_sha256", ""))):
            blockers.append(f"{prefix}:custody_verifier_sha256_invalid")
        return blockers

    @staticmethod
    def _validate_weight_files(
        role: str,
        artifact: Mapping[str, Any],
        raw_location: Any,
        report: Mapping[str, Any],
    ) -> list[str]:
        prefix = f"{role}:weight_receipt"
        files = report.get("files")
        expected_method = {
            "provider_local": "provider_local_streaming_sha256",
            "phone_local_authority": "phone_local_streaming_sha256",
        }.get(raw_location)
        expected_files = {item["path"]: item for item in artifact["weights"]}
        if not isinstance(files, Mapping) or set(files) != set(expected_files):
            return [f"{prefix}:wrong_file_set"]
        blockers: list[str] = []
        required_fields = {"sha256", "bytes", "verification_method"}
        for path, expected in expected_files.items():
            observed = files.get(path)
            if not isinstance(observed, Mapping) or set(observed) != required_fields:
                blockers.append(f"{prefix}:{path}:wrong_field_set")
                continue
            if observed.get("sha256") != expected["sha256"]:
                blockers.append(f"{prefix}:{path}:sha256_mismatch")
            if observed.get("bytes") != expected["bytes"]:
                blockers.append(f"{prefix}:{path}:size_mismatch")
            if observed.get("verification_method") != expected_method:
                blockers.append(f"{prefix}:{path}:wrong_verification_method")
        return blockers

    @staticmethod
    def _valid_layer_pattern(layer_types: Sequence[str]) -> bool:
        expected = [
            "full_attention" if (index + 1) % 6 == 0 else "sliding_attention"
            for index in range(42)
        ]
        return list(layer_types) == expected

    @staticmethod
    def _selection_protocol(
        inspected: Mapping[str, Mapping[str, Any]],
        reference_stacks: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        return {
            "hard_eligibility": [
                "immutable official E4B-it mobile-QAT revision",
                "exact E4B architecture invariants",
                "tokenizer/template/termination equality or tested mapping",
                "complete quantization and SafeTensors identity",
                "frozen executable framework stack",
                "untied separately quantized LM-head identity preserved",
            ],
            "lexicographic_selection": [
                "executable framework reference load",
                "QAIRT export and required-operator coverage",
                "encoding preservation and no hidden dequantization substitution",
                "full seq16 token-to-exact-loss monolith feasibility",
                "provider-local memory and wall-time envelope",
            ],
            "candidate_static_evidence": {
                role: {
                    "quantization_and_encoding_manifest_sha256": inspected[role][
                        "quantization_and_encoding_manifest_sha256"
                    ],
                    "framework_stack_sha256": canonical_sha256(
                        reference_stacks.get(role, {})
                    ),
                    "tie_word_embeddings": inspected[role]["architecture"][
                        "tie_word_embeddings"
                    ],
                }
                for role in ("qat_mobile_transformers", "qat_mobile_compressed_tensors")
            },
            "converter_success_is_numerical_admission": False,
            "numerical_admission_gate": "L2",
        }

    @staticmethod
    def _architecture_role(artifact: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "repository": artifact["repository"],
            "revision": artifact["revision"],
            "repository_tree": artifact["repository_tree"],
            "repository_tree_sha256": artifact["repository_tree_sha256"],
            "config_sha256": artifact["files"]["config.json"]["sha256"],
            "architecture_contract": artifact["architecture"],
            "architecture_contract_sha256": canonical_sha256(artifact["architecture"]),
            "model_card_and_license": artifact["model_card"],
            "execution_affecting_files_sha256": artifact[
                "execution_affecting_files_sha256"
            ],
            "numerical_authority": False,
        }

    @staticmethod
    def _task_oracle_role(
        artifact: Mapping[str, Any],
        edge_a_protocol: Mapping[str, Any],
        reference_stack: Mapping[str, Any],
        weight_receipt: Mapping[str, Any],
    ) -> dict[str, Any]:
        tokenizer = artifact["tokenizer"]
        return {
            "repository": artifact["repository"],
            "revision": artifact["revision"],
            "repository_tree": artifact["repository_tree"],
            "repository_tree_sha256": artifact["repository_tree_sha256"],
            "config_and_weight_shards_sha256": artifact[
                "config_and_weight_shards_sha256"
            ],
            "weight_shards": artifact["weights"],
            "tokenizer_files_sha256": canonical_sha256(
                {
                    "tokenizer_json": tokenizer["tokenizer_json_sha256"],
                    "tokenizer_config": tokenizer["tokenizer_config_sha256"],
                }
            ),
            "chat_template_sha256": tokenizer["chat_template_sha256"],
            "termination_token_contract": tokenizer["termination_contract"],
            "termination_token_contract_sha256": canonical_sha256(
                tokenizer["termination_contract"]
            ),
            "LM_head_tying_state": artifact["architecture"]["tie_word_embeddings"],
            "executable_reference_stack_and_revision": dict(reference_stack),
            "executable_reference_stack_sha256": canonical_sha256(reference_stack),
            "provider_local_weight_verification_receipt": dict(weight_receipt),
            "provider_local_weight_verification_receipt_sha256": canonical_sha256(
                weight_receipt
            ),
            "edge_A_decode_template_stop_length_seed_and_evaluator_protocol": dict(
                edge_a_protocol
            ),
            "edge_A_decode_template_stop_length_seed_and_evaluator_protocol_sha256": canonical_sha256(
                edge_a_protocol
            ),
            "model_card_and_license": artifact["model_card"],
            "execution_affecting_files": artifact["execution_affecting_files"],
            "execution_affecting_files_sha256": artifact[
                "execution_affecting_files_sha256"
            ],
            "phone_learning_surface": False,
        }

    @staticmethod
    def _qat_role(
        artifact: Mapping[str, Any],
        reference_stack: Mapping[str, Any],
        weight_receipt: Mapping[str, Any],
    ) -> dict[str, Any]:
        tokenizer = artifact["tokenizer"]
        return {
            "repository": artifact["repository"],
            "revision": artifact["revision"],
            "repository_tree": artifact["repository_tree"],
            "repository_tree_sha256": artifact["repository_tree_sha256"],
            "config_and_weight_shards_sha256": artifact[
                "config_and_weight_shards_sha256"
            ],
            "weight_shards": artifact["weights"],
            "quantization_and_encoding_manifest_sha256": artifact[
                "quantization_and_encoding_manifest_sha256"
            ],
            "quantization_identity": artifact["quantization_identity"],
            "LM_head_tying_and_quantization_identity": {
                "tie_word_embeddings": artifact["architecture"]["tie_word_embeddings"],
                "lm_head_is_separate": artifact["architecture"]["tie_word_embeddings"]
                is False,
                "critical_tensor_contracts_sha256": artifact["safetensors"][
                    "critical_tensor_contracts_sha256"
                ],
            },
            "tokenizer_and_template_equality_or_mapping": {
                "tokenizer_json_sha256": tokenizer["tokenizer_json_sha256"],
                "tokenizer_config_sha256": tokenizer["tokenizer_config_sha256"],
                "tokenizer_config_semantic_sha256": tokenizer[
                    "tokenizer_config_semantic_sha256"
                ],
                "chat_template_sha256": tokenizer["chat_template_sha256"],
                "mapping": "byte_equal_tokenizer_and_template_semantic_equal_tokenizer_config",
            },
            "executable_reference_stack_and_revision": dict(reference_stack),
            "executable_reference_stack_sha256": canonical_sha256(reference_stack),
            "provider_local_weight_verification_receipt": dict(weight_receipt),
            "provider_local_weight_verification_receipt_sha256": canonical_sha256(
                weight_receipt
            ),
            "reference_dtype_and_runtime_policy": {
                "master_weight_storage": "artifact_native_packed_quantization",
                "activation_and_scale_dtypes": artifact["safetensors"]["dtype_counts"],
                "silent_requantization_or_dequantized_model_substitution": "forbidden",
                "framework_reference_must_preserve_artifact_quantization_modules": True,
            },
            "model_card_and_license": artifact["model_card"],
            "execution_affecting_files": artifact["execution_affecting_files"],
            "execution_affecting_files_sha256": artifact[
                "execution_affecting_files_sha256"
            ],
        }


def build_default_l0_manifest(
    client: HubClient,
    *,
    provisional_build_source: str | None,
    reference_stacks: Mapping[str, Mapping[str, Any]],
    converter_lineage: Mapping[str, Any],
    edge_a_protocol: Mapping[str, Any],
    weight_verification_receipts: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    return E4bL0Builder(client).build(
        DEFAULT_ARTIFACTS,
        provisional_build_source=provisional_build_source,
        reference_stacks=reference_stacks,
        converter_lineage=converter_lineage,
        edge_a_protocol=edge_a_protocol,
        weight_verification_receipts=weight_verification_receipts,
    )
