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
import os
import re
from typing import Any, Mapping, Protocol, Sequence
from urllib.parse import quote
from urllib.request import Request, urlopen


L0_SCHEMA_VERSION = "gemma4_e4b_l0_parent_manifest_v1"
FULL_REVISION = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MAX_SAFETENSORS_HEADER_BYTES = 16 * 1024 * 1024


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
    "config.json",
    "generation_config.json",
    "model.safetensors.index.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "chat_template.jinja",
    "processor_config.json",
    "preprocessor_config.json",
)


class HubClient(Protocol):
    """Minimal injected Hub surface used by the deterministic builder."""

    def list_tree(self, artifact: ArtifactSpec) -> Sequence[Mapping[str, Any]]:
        """Return the immutable recursive repository tree."""

    def read_file(self, artifact: ArtifactSpec, path: str) -> bytes:
        """Return one small file at the immutable revision."""

    def read_range(self, artifact: ArtifactSpec, path: str, start: int, end: int) -> bytes:
        """Return the inclusive byte range without materializing the full object."""


class HuggingFaceHubClient:
    """Standard-library, token-optional immutable Hugging Face client."""

    def __init__(self, token: str | None = None, timeout_seconds: int = 60) -> None:
        self._token = token if token is not None else os.environ.get("HF_TOKEN")
        self._timeout_seconds = timeout_seconds

    def list_tree(self, artifact: ArtifactSpec) -> Sequence[Mapping[str, Any]]:
        repo = quote(artifact.repository, safe="/")
        revision = quote(artifact.revision, safe="")
        url = f"https://huggingface.co/api/models/{repo}/tree/{revision}?recursive=true&expand=true"
        payload = self._read(Request(url, headers=self._headers()))
        value = json.loads(payload)
        if not isinstance(value, list):
            raise ValueError(f"Hub tree is not a list for {artifact.repository}@{artifact.revision}")
        return value

    def read_file(self, artifact: ArtifactSpec, path: str) -> bytes:
        return self._read(Request(self._resolve_url(artifact, path), headers=self._headers()))

    def read_range(self, artifact: ArtifactSpec, path: str, start: int, end: int) -> bytes:
        if start < 0 or end < start:
            raise ValueError("invalid byte range")
        headers = self._headers()
        headers["Range"] = f"bytes={start}-{end}"
        headers["Accept-Encoding"] = "identity"
        payload = self._read(Request(self._resolve_url(artifact, path), headers=headers))
        expected = end - start + 1
        if len(payload) != expected:
            raise ValueError(f"range length mismatch for {path}: expected {expected}, observed {len(payload)}")
        return payload

    def _read(self, request: Request) -> bytes:
        with urlopen(request, timeout=self._timeout_seconds) as response:
            return response.read()

    def _headers(self) -> dict[str, str]:
        headers = {"User-Agent": "polymath-ai-gemma4-e4b-l0/1"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    @staticmethod
    def _resolve_url(artifact: ArtifactSpec, path: str) -> str:
        repo = quote(artifact.repository, safe="/")
        revision = quote(artifact.revision, safe="")
        encoded_path = quote(path, safe="/")
        return f"https://huggingface.co/{repo}/resolve/{revision}/{encoded_path}"


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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
    ) -> dict[str, Any]:
        by_role = self._validate_artifacts(artifacts)
        inspected = {role: self._inspect(spec) for role, spec in by_role.items()}
        blockers = self._validate_cross_artifact_contract(inspected, provisional_build_source)
        selection_protocol = self._selection_protocol(inspected, reference_stacks)
        manifest = {
            "schema_version": L0_SCHEMA_VERSION,
            "claim_class": "local_verification",
            "state": "passed_scope" if not blockers else "blocked_fail_closed",
            "architecture_oracle": self._architecture_role(inspected["architecture_oracle"]),
            "high_precision_task_oracle": self._task_oracle_role(
                inspected["high_precision_task_oracle"], edge_a_protocol
            ),
            "mobile_qat_candidates": {
                role: self._qat_role(inspected[role], reference_stacks.get(role, {}))
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
                        for role in ("qat_mobile_transformers", "qat_mobile_compressed_tensors")
                    ]
                ),
                "selection_protocol": selection_protocol,
                "selection_protocol_sha256": canonical_sha256(selection_protocol),
                "provisional_build_source_candidate_id": provisional_build_source,
                "numerical_admission_deferred_to": "L2_Edge_A_and_Edge_B",
            },
            "converter_lineage": dict(converter_lineage),
            "blockers": blockers,
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
        missing = [path for path in ("config.json",) if path not in file_index]
        if missing:
            raise ValueError(f"missing required files in {artifact.role}: {missing}")

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

        config = json.loads(self._client.read_file(artifact, "config.json"))
        architecture = self._architecture_snapshot(config)
        tokenizer = self._tokenizer_snapshot(artifact, small_files, file_index)
        safetensors = self._safetensors_snapshot(artifact, weights)
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
            "files": small_files,
            "weights": weights,
            "config": config,
            "architecture": architecture,
            "tokenizer": tokenizer,
            "safetensors": safetensors,
            "config_and_weight_shards_sha256": canonical_sha256(config_and_weights),
            "quantization_identity": quantization_identity,
            "quantization_and_encoding_manifest_sha256": canonical_sha256(quantization_identity),
        }

    @staticmethod
    def _file_index(tree: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
        return {
            str(item["path"]): item
            for item in tree
            if item.get("type") == "file" and isinstance(item.get("path"), str)
        }

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
        tokenizer_config_bytes = self._client.read_file(artifact, "tokenizer_config.json")
        tokenizer = json.loads(tokenizer_bytes)
        tokenizer_config = json.loads(tokenizer_config_bytes)
        special_tokens = self._special_token_ids(tokenizer)
        semantic_config = {
            key: tokenizer_config.get(key)
            for key in (
                "bos_token",
                "eos_token",
                "pad_token",
                "unk_token",
                "add_bos_token",
                "add_eos_token",
                "chat_template",
            )
        }
        return {
            "tokenizer_json_sha256": files["tokenizer.json"]["sha256"],
            "tokenizer_config_sha256": files["tokenizer_config.json"]["sha256"],
            "tokenizer_config_semantic_sha256": canonical_sha256(semantic_config),
            "chat_template_sha256": files["chat_template.jinja"]["sha256"],
            "special_token_ids": special_tokens,
            "termination_contract": {
                "scored_span": "assistant_answer_plus_turn_termination",
                "assistant_turn_terminator": "<turn|>",
                "assistant_turn_terminator_id": special_tokens.get("<turn|>"),
                "prompt_and_control_tokens_ignored_by_primary_loss": True,
                "all_answer_and_termination_tokens_scored": True,
            },
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
        self, artifact: ArtifactSpec, weights: Sequence[Mapping[str, Any]]
    ) -> dict[str, Any] | None:
        if not weights:
            return None
        if len(weights) != 1:
            return {
                "weight_file_count": len(weights),
                "header_inspection": "deferred_for_sharded_artifact",
            }
        path = str(weights[0]["path"])
        prefix = self._client.read_range(artifact, path, 0, 7)
        header_size = int.from_bytes(prefix, "little")
        if header_size <= 0 or header_size > MAX_SAFETENSORS_HEADER_BYTES:
            raise ValueError(f"unsafe SafeTensors header size for {artifact.role}: {header_size}")
        header_bytes = self._client.read_range(artifact, path, 8, 7 + header_size)
        header = json.loads(header_bytes.rstrip(b" "))
        metadata = header.pop("__metadata__", {})
        tensor_names = sorted(header)
        dtype_counts = Counter(str(value.get("dtype")) for value in header.values())
        critical = {
            name: header[name]
            for name in tensor_names
            if self._critical_tensor_name(name)
        }
        return {
            "weight_file": path,
            "header_bytes": header_size,
            "header_sha256": bytes_sha256(header_bytes),
            "tensor_count": len(tensor_names),
            "tensor_name_root_sha256": canonical_sha256(tensor_names),
            "dtype_counts": dict(sorted(dtype_counts.items())),
            "metadata": metadata,
            "critical_tensor_contracts": critical,
            "critical_tensor_contracts_sha256": canonical_sha256(critical),
        }

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
                "layer_types": layer_types,
                "local_layer_count": layer_types.count("sliding_attention"),
                "global_layer_count": layer_types.count("full_attention"),
                "rope_parameters": text.get("rope_parameters"),
                "tie_word_embeddings": text.get("tie_word_embeddings", config.get("tie_word_embeddings")),
                "hidden_activation": text.get("hidden_activation"),
                "attention_k_eq_v": text.get("attention_k_eq_v"),
            }
        )
        return snapshot

    @staticmethod
    def _validate_artifacts(artifacts: Sequence[ArtifactSpec]) -> dict[str, ArtifactSpec]:
        by_role = {artifact.role: artifact for artifact in artifacts}
        expected = {
            "architecture_oracle",
            "high_precision_task_oracle",
            "qat_mobile_transformers",
            "qat_mobile_compressed_tensors",
        }
        if set(by_role) != expected:
            raise ValueError(f"artifact roles must equal {sorted(expected)}")
        for artifact in artifacts:
            if not FULL_REVISION.fullmatch(artifact.revision):
                raise ValueError(f"revision must be immutable SHA for {artifact.role}")
        return by_role

    def _validate_cross_artifact_contract(
        self, inspected: Mapping[str, Mapping[str, Any]], provisional: str | None
    ) -> list[str]:
        blockers: list[str] = []
        for role, artifact in inspected.items():
            for key, expected in EXPECTED_ARCHITECTURE.items():
                if artifact["architecture"].get(key) != expected:
                    blockers.append(f"{role}:architecture:{key}")
            if not self._valid_layer_pattern(artifact["architecture"].get("layer_types", [])):
                blockers.append(f"{role}:architecture:layer_types")
            tokenizer = artifact.get("tokenizer")
            if role != "architecture_oracle" and not tokenizer:
                blockers.append(f"{role}:tokenizer_contract_missing")
            elif tokenizer and tokenizer["termination_contract"]["assistant_turn_terminator_id"] is None:
                blockers.append(f"{role}:termination_token_missing")

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
                blockers.append(f"{role}:tokenizer_config_semantics_differ_from_task_oracle")

        allowed = {None, "qat_mobile_transformers", "qat_mobile_compressed_tensors"}
        if provisional not in allowed:
            blockers.append("mobile_qat_selection:unknown_provisional_candidate")
        return sorted(blockers)

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
                    "framework_stack_sha256": canonical_sha256(reference_stacks.get(role, {})),
                    "tie_word_embeddings": inspected[role]["architecture"]["tie_word_embeddings"],
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
            "config_sha256": artifact["files"]["config.json"]["sha256"],
            "architecture_contract": artifact["architecture"],
            "architecture_contract_sha256": canonical_sha256(artifact["architecture"]),
            "numerical_authority": False,
        }

    @staticmethod
    def _task_oracle_role(
        artifact: Mapping[str, Any], edge_a_protocol: Mapping[str, Any]
    ) -> dict[str, Any]:
        tokenizer = artifact["tokenizer"]
        return {
            "repository": artifact["repository"],
            "revision": artifact["revision"],
            "config_and_weight_shards_sha256": artifact["config_and_weight_shards_sha256"],
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
            "edge_A_decode_template_stop_length_seed_and_evaluator_protocol": dict(edge_a_protocol),
            "edge_A_decode_template_stop_length_seed_and_evaluator_protocol_sha256": canonical_sha256(
                edge_a_protocol
            ),
            "phone_learning_surface": False,
        }

    @staticmethod
    def _qat_role(
        artifact: Mapping[str, Any], reference_stack: Mapping[str, Any]
    ) -> dict[str, Any]:
        tokenizer = artifact["tokenizer"]
        return {
            "repository": artifact["repository"],
            "revision": artifact["revision"],
            "config_and_weight_shards_sha256": artifact["config_and_weight_shards_sha256"],
            "weight_shards": artifact["weights"],
            "quantization_and_encoding_manifest_sha256": artifact[
                "quantization_and_encoding_manifest_sha256"
            ],
            "quantization_identity": artifact["quantization_identity"],
            "LM_head_tying_and_quantization_identity": {
                "tie_word_embeddings": artifact["architecture"]["tie_word_embeddings"],
                "lm_head_is_separate": artifact["architecture"]["tie_word_embeddings"] is False,
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
            "reference_dtype_and_runtime_policy": {
                "master_weight_storage": "artifact_native_packed_quantization",
                "activation_and_scale_dtypes": artifact["safetensors"]["dtype_counts"],
                "silent_requantization_or_dequantized_model_substitution": "forbidden",
                "framework_reference_must_preserve_artifact_quantization_modules": True,
            },
        }


def build_default_l0_manifest(
    client: HubClient,
    *,
    provisional_build_source: str | None,
    reference_stacks: Mapping[str, Mapping[str, Any]],
    converter_lineage: Mapping[str, Any],
    edge_a_protocol: Mapping[str, Any],
) -> dict[str, Any]:
    return E4bL0Builder(client).build(
        DEFAULT_ARTIFACTS,
        provisional_build_source=provisional_build_source,
        reference_stacks=reference_stacks,
        converter_lineage=converter_lineage,
        edge_a_protocol=edge_a_protocol,
    )
