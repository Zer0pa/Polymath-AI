"""Atomic package materializer for the full-width V79 INT16 LM-head pivot."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import re
import secrets
import stat
from typing import Any

from .e4b_f5_probe import QAT_MODEL_SHA256, TRANSFORMERS_COMMIT
from .e4b_f5_qnn_exporter import LM_HEAD_GRAPH, publish_directory_noreplace
from .e4b_l2_int16_head import (
    FP16_FALSIFICATION_GATE_SHA256,
    INPUT_SCALE,
    INT16_CANDIDATE_ID,
    INT16_PREREG_SCHEMA,
    OUTPUT_SCALE,
    render_int16_head_cpp,
)
from .e4b_l2_projection_gate import (
    REFERENCE_GATE_SCHEMA_VERSION,
    ProjectionGateError,
    canonical_json,
    sha256_bytes,
    sha256_path,
    write_hashed_json,
)


INT16_PREREG_SHA256 = "51f1e9977258d8d61c7eb1ff76964b293a15d38eb852da1b5692cb58aaeea284"
INT16_POLICY_SHA256 = "36d4689f6c59f8ce8d9d99c6dc4085d7e63089a6448c20517fd0fcc74964ad05"
INT16_CONTEXT_GATE_SCHEMA = "gemma4_e4b_l2_int16_context_gate_v1"
VARIANT_PACKAGE_SCHEMA = "gemma4_e4b_f5_direct_qnn_int16_head_package_v1"
FULL_REVISION = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _strict_load(path: Path) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise ProjectionGateError(f"non-finite JSON constant: {value}")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ProjectionGateError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    raw = path.read_bytes()
    result = json.loads(
        raw,
        parse_constant=reject_constant,
        object_pairs_hook=reject_duplicates,
    )
    if not isinstance(result, dict):
        raise ProjectionGateError(f"JSON root must be an object: {path}")
    return result


def _strict_load_canonical(path: Path) -> dict[str, Any]:
    result = _strict_load(path)
    if canonical_json(result) != _read_regular(path):
        raise ProjectionGateError(f"JSON is not canonical: {path}")
    return result


def _read_regular(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ProjectionGateError(f"not a regular file: {path}")
        chunks = []
        while chunk := os.read(descriptor, 8 * 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _write_exclusive(path: Path, payload: bytes, *, executable: bool = False) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o750 if executable else 0o640)
    try:
        view = memoryview(payload)
        while view:
            count = os.write(descriptor, view)
            if count <= 0:
                raise OSError(f"short write to {path}")
            view = view[count:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _file_record(path: Path, root: Path) -> dict[str, Any]:
    return {
        "relative_path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_path(path),
    }


def _verify_record(root: Path, record: dict[str, Any]) -> Path:
    relative = record.get("relative_path")
    if not isinstance(relative, str) or relative.startswith("/") or ".." in Path(relative).parts:
        raise ProjectionGateError("unsafe package relative path")
    path = root / relative
    payload = _read_regular(path)
    if len(payload) != record.get("bytes") or sha256_bytes(payload) != record.get("sha256"):
        raise ProjectionGateError(f"base package file identity mismatch: {relative}")
    return path


def _verify_sidecar(path: Path, digest: str) -> None:
    expected = f"{digest}  {path.name}\n".encode("ascii")
    if _read_regular(path.with_suffix(path.suffix + ".sha256")) != expected:
        raise ProjectionGateError(f"digest sidecar mismatch: {path}")


def _load_int16_prereg(root: Path) -> dict[str, Any]:
    manifest_path = root / "preregistration.json"
    policy_path = root / "threshold_policy.json"
    if sha256_path(manifest_path) != INT16_PREREG_SHA256:
        raise ProjectionGateError("INT16 preregistration digest mismatch")
    if sha256_path(policy_path) != INT16_POLICY_SHA256:
        raise ProjectionGateError("INT16 threshold policy digest mismatch")
    _verify_sidecar(manifest_path, INT16_PREREG_SHA256)
    _verify_sidecar(policy_path, INT16_POLICY_SHA256)
    manifest = _strict_load_canonical(manifest_path)
    _strict_load_canonical(policy_path)
    if manifest.get("schema_version") != INT16_PREREG_SCHEMA or manifest.get("state") != "frozen_unobserved":
        raise ProjectionGateError("INT16 preregistration schema/state mismatch")
    if manifest.get("candidate_id") != INT16_CANDIDATE_ID:
        raise ProjectionGateError("INT16 candidate identity mismatch")
    if manifest.get("candidate_output_files_present") is not False:
        raise ProjectionGateError("INT16 preregistration already contains candidate output")
    for record in manifest.get("cases", []):
        relative = record.get("s16_input_relative_path")
        if not isinstance(relative, str):
            raise ProjectionGateError("INT16 case lacks an input path")
        payload = _read_regular(root / relative)
        if len(payload) != record.get("s16_input_bytes") or sha256_bytes(payload) != record.get(
            "s16_input_sha256"
        ):
            raise ProjectionGateError(f"INT16 input identity mismatch: {relative}")
    return manifest


def _context_gate_payload(
    parent_gate: dict[str, Any],
    prereg: dict[str, Any],
    *,
    source_revision: str,
    parent_capsule_sha256: str,
    frontier_selector_sha256: str,
) -> dict[str, Any]:
    q_record = next(
        (
            record
            for record in parent_gate.get("case_records", [])
            if record.get("graph_name") != LM_HEAD_GRAPH
        ),
        None,
    )
    if not isinstance(q_record, dict):
        raise ProjectionGateError("FP16 gate lacks the frozen Q-projection record")
    head_record = prereg["cases"][0]
    return {
        "schema_version": REFERENCE_GATE_SCHEMA_VERSION,
        "status": "passed_scope",
        "scope": "INT16_candidate_preregistration_and_reference_binding_only",
        "qat_model_sha256": QAT_MODEL_SHA256,
        "transformers_commit": TRANSFORMERS_COMMIT,
        "l2_threshold_policy_sha256": INT16_POLICY_SHA256,
        "int16_context_gate_schema": INT16_CONTEXT_GATE_SCHEMA,
        "int16_preregistration_sha256": INT16_PREREG_SHA256,
        "fp16_falsification_gate_sha256": FP16_FALSIFICATION_GATE_SHA256,
        "candidate_id": INT16_CANDIDATE_ID,
        "source_revision": source_revision,
        "parent_capsule_sha256": parent_capsule_sha256,
        "frontier_selector_sha256": frontier_selector_sha256,
        "probes": {
            q_record["graph_name"]: {
                "input_sha256": q_record["input"]["sha256"],
                "reference_output_sha256": q_record["reference_output"]["sha256"],
                "primary_case_id": q_record["case_id"],
            },
            LM_HEAD_GRAPH: {
                "input_sha256": head_record["s16_input_sha256"],
                "reference_output_sha256": head_record["authority_output"]["sha256"],
                "primary_case_id": head_record["case_id"],
            },
        },
        "candidate_output_observed": False,
        "provider_context_generated": False,
        "phone_execution_count": 0,
        "qnn_execution_count": 0,
        "full_L2_passed": False,
        "claim_boundary": "allows_provider_context_attempt_only",
    }


def build_int16_context_gate(
    *,
    fp16_falsification_gate: Path,
    int16_prereg_dir: Path,
    output_path: Path,
    source_revision: str,
    parent_capsule_sha256: str,
    frontier_selector_sha256: str,
) -> dict[str, Any]:
    """Emit the compatibility gate consumed by the existing context runner."""

    if not FULL_REVISION.fullmatch(source_revision):
        raise ProjectionGateError("context-gate source revision must be immutable")
    if not SHA256.fullmatch(parent_capsule_sha256):
        raise ProjectionGateError("context-gate parent capsule digest is invalid")
    if not SHA256.fullmatch(frontier_selector_sha256):
        raise ProjectionGateError("context-gate frontier selector digest is invalid")
    if sha256_path(fp16_falsification_gate) != FP16_FALSIFICATION_GATE_SHA256:
        raise ProjectionGateError("FP16 falsification gate digest mismatch")
    parent_gate = _strict_load_canonical(fp16_falsification_gate)
    prereg = _load_int16_prereg(int16_prereg_dir)
    payload = _context_gate_payload(
        parent_gate,
        prereg,
        source_revision=source_revision,
        parent_capsule_sha256=parent_capsule_sha256,
        frontier_selector_sha256=frontier_selector_sha256,
    )
    digest = write_hashed_json(output_path, payload)
    return {"context_gate_sha256": digest, "status": payload["status"]}


def _load_base_package(root: Path) -> tuple[dict[str, Any], str]:
    manifest_path = root / "package_manifest.json"
    manifest_digest = sha256_path(manifest_path)
    sidecar = _read_regular(root / "package_manifest.sha256")
    expected_sidecar = f"{manifest_digest}  package_manifest.json\n".encode("ascii")
    if sidecar != expected_sidecar:
        raise ProjectionGateError("base package manifest sidecar mismatch")
    manifest = _strict_load(manifest_path)
    if manifest.get("schema_version") != "gemma4_e4b_f5_direct_qnn_probe_package_v1":
        raise ProjectionGateError("base package schema mismatch")
    if manifest.get("status") != "proposed_executable_backend_unvalidated":
        raise ProjectionGateError("base package state mismatch")
    artifact = manifest.get("artifact", {})
    if artifact.get("carrier_sha256") != QAT_MODEL_SHA256 or artifact.get("full_provider_identity_green") is not True:
        raise ProjectionGateError("base package artifact identity mismatch")
    tensor_files = manifest.get("tensor_files")
    generated_files = manifest.get("generated_files")
    if not isinstance(tensor_files, list) or len(tensor_files) != 8:
        raise ProjectionGateError("base package tensor set mismatch")
    if not isinstance(generated_files, list) or len(generated_files) != 6:
        raise ProjectionGateError("base package generated-file set mismatch")
    for record in tensor_files + generated_files:
        _verify_record(root, record)
    return manifest, manifest_digest


def materialize_int16_variant(
    *,
    base_package_dir: Path,
    fp16_falsification_gate: Path,
    int16_prereg_dir: Path,
    context_gate: Path,
    output_dir: Path,
    source_revision: str,
    parent_capsule_sha256: str,
    frontier_selector_sha256: str,
) -> dict[str, Any]:
    """Create a no-replace INT16 package without mutating the base package."""

    if not FULL_REVISION.fullmatch(source_revision):
        raise ProjectionGateError("variant source revision must be immutable")
    if not SHA256.fullmatch(parent_capsule_sha256):
        raise ProjectionGateError("variant parent capsule digest is invalid")
    if not SHA256.fullmatch(frontier_selector_sha256):
        raise ProjectionGateError("variant frontier selector digest is invalid")
    if output_dir.exists():
        raise ProjectionGateError(f"variant output already exists: {output_dir}")
    if sha256_path(fp16_falsification_gate) != FP16_FALSIFICATION_GATE_SHA256:
        raise ProjectionGateError("FP16 falsification gate digest mismatch")
    parent_gate = _strict_load_canonical(fp16_falsification_gate)
    prereg = _load_int16_prereg(int16_prereg_dir)
    gate = _strict_load_canonical(context_gate)
    gate_sha256 = sha256_path(context_gate)
    _verify_sidecar(context_gate, gate_sha256)
    expected_gate = _context_gate_payload(
        parent_gate,
        prereg,
        source_revision=source_revision,
        parent_capsule_sha256=parent_capsule_sha256,
        frontier_selector_sha256=frontier_selector_sha256,
    )
    if gate != expected_gate:
        raise ProjectionGateError("INT16 context gate mismatch")
    base, base_sha256 = _load_base_package(base_package_dir)

    output_dir.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    temporary = output_dir.with_name(f".{output_dir.name}.tmp.{secrets.token_hex(16)}")
    temporary.mkdir(mode=0o750)
    try:
        (temporary / "tensors").mkdir(mode=0o750)
        (temporary / "source").mkdir(mode=0o750)
        (temporary / "config").mkdir(mode=0o750)
        tensor_files = []
        for record in base["tensor_files"]:
            source = _verify_record(base_package_dir, record)
            destination = temporary / record["relative_path"]
            _write_exclusive(destination, _read_regular(source))
            tensor_files.append({**record, **_file_record(destination, temporary)})

        generated_files = []
        for record in base["generated_files"]:
            relative = record["relative_path"]
            destination = temporary / relative
            if relative == "source/direct_qnn_probes.cpp":
                payload = render_int16_head_cpp().encode("utf-8")
            else:
                payload = _read_regular(_verify_record(base_package_dir, record))
            _write_exclusive(destination, payload, executable=relative.endswith(".sh"))
            generated_files.append(_file_record(destination, temporary))

        manifest = copy.deepcopy(base)
        manifest["schema_version"] = VARIANT_PACKAGE_SCHEMA
        manifest["status"] = "proposed_executable_backend_unvalidated"
        manifest["claim_class"] = "INT16_variant_source_generation_only"
        manifest["variant_identity"] = {
            "candidate_id": INT16_CANDIDATE_ID,
            "source_revision": source_revision,
            "parent_capsule_sha256": parent_capsule_sha256,
            "frontier_selector_sha256": frontier_selector_sha256,
            "variant_module_sha256": sha256_path(Path(__file__)),
            "base_package_manifest_sha256": base_sha256,
            "int16_preregistration_sha256": INT16_PREREG_SHA256,
            "int16_threshold_policy_sha256": INT16_POLICY_SHA256,
            "context_gate_sha256": gate_sha256,
            "fp16_falsification_gate_sha256": FP16_FALSIFICATION_GATE_SHA256,
        }
        manifest["lowering"]["lm_head"]["activation_abi"] = {
            "input_dtype": "QNN_DATATYPE_SFIXED_POINT_16",
            "input_scale": INPUT_SCALE,
            "output_dtype": "QNN_DATATYPE_SFIXED_POINT_16",
            "output_scale": OUTPUT_SCALE,
            "candidate_output_observed": False,
        }
        for graph in manifest["graphs"]:
            if graph["name"] != LM_HEAD_GRAPH:
                continue
            graph["tensor_abi"] = {
                "input": {"dtype": "int16", "shape": [1, 1, 2560], "bytes": 5120, "scale": INPUT_SCALE},
                "output": {
                    "dtype": "int16",
                    "shape": [1, 1, 262144],
                    "bytes": 524288,
                    "scale": OUTPUT_SCALE,
                    "surface": "full_pre_softcap_logits",
                },
                "pass_rule": "phone_local_dequantize_then_apply_unchanged_combined_threshold_subset",
            }
        manifest["tensor_files"] = tensor_files
        manifest["generated_files"] = generated_files
        manifest["execution_preconditions"]["context_generation"] = (
            f"exact INT16 compatibility gate {gate_sha256} required"
        )
        manifest["nonclaims"] = [
            "no HTP backend acceptance",
            "no phone execution",
            "no INT16 QAT-to-QNN numerical fidelity",
            "no L1 or L2 pass",
            "no capsule advancement",
        ]
        manifest["int16_preregistration_state"] = prereg["state"]
        encoded = (json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
        manifest_path = temporary / "package_manifest.json"
        _write_exclusive(manifest_path, encoded)
        digest = sha256_bytes(encoded)
        _write_exclusive(
            temporary / "package_manifest.sha256",
            f"{digest}  package_manifest.json\n".encode("ascii"),
        )
        directory = os.open(temporary, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        publish_directory_noreplace(temporary, output_dir)
        return {
            "output_dir": str(output_dir),
            "manifest_sha256": digest,
            "status": manifest["status"],
        }
    except Exception:
        # A failed staging directory is preserved for diagnosis; it can never
        # be mistaken for the requested no-replace output path.
        raise
