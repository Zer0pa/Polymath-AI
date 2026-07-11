"""Oracle-gated provider package for the final authority-correct S16 v2 head."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import re
import secrets
from typing import Any

from .e4b_f5_probe import QAT_MODEL_SHA256, TRANSFORMERS_COMMIT
from .e4b_f5_qnn_exporter import (
    LM_HEAD_GRAPH,
    Q_PROJ_GRAPH,
    TENSOR_FILENAMES,
    publish_directory_noreplace,
)
from .e4b_l2_int16_head import FP16_FALSIFICATION_GATE_SHA256
from .e4b_l2_int16_package import (
    _file_record,
    _load_base_package,
    _read_regular,
    _strict_load_canonical,
    _verify_record,
    _verify_sidecar,
    _write_exclusive,
)
from .e4b_l2_int16_v2 import (
    FRONTIER_SELECTOR_SHA256,
    FULL_REVISION,
    FULL_WIDTH_DOT_PRODUCTS_PER_CASE,
    INPUT_FEATURES,
    INPUT_SCALE,
    NUMERIC_THRESHOLD_SUBSET_SHA256,
    ORIGINAL_SCALE_BYTES,
    ORIGINAL_SCALE_SHA256,
    OUTPUT_FEATURES,
    OUTPUT_SCALE,
    PACKED_WEIGHT_BYTES,
    PACKED_WEIGHT_SHA256,
    PARENT_CAPSULE_SHA256 as GOVERNING_PARENT_CAPSULE_SHA256,
    V2_CANDIDATE_ID,
    V2_ORACLE_SCHEMA,
    bf16_rne_scales_as_exact_f32,
    render_int16_v2_head_cpp,
)
from .e4b_l2_int16_v2_verifier import (
    VERIFICATION_SCHEMA,
    validate_sanitized_phone_authorization,
)
from .e4b_l2_projection_gate import (
    REFERENCE_GATE_SCHEMA_VERSION,
    ProjectionGateError,
    canonical_json,
    sha256_bytes,
    sha256_path,
    write_hashed_json,
)


V2_CONTEXT_GATE_SCHEMA = "gemma4_e4b_l2_int16_context_gate_v2"
V2_VARIANT_PACKAGE_SCHEMA = "gemma4_e4b_f5_direct_qnn_int16_head_package_v2"
V2_PROVIDER_BUILD_AUTH_SCHEMA = "gemma4_e4b_l2_int16_v2_provider_build_authorization_v1"
SCALE_BASE_RELATIVE_PATH = f"tensors/{TENSOR_FILENAMES['lm_head.weight_scale']}"
PACKED_BASE_RELATIVE_PATH = f"tensors/{TENSOR_FILENAMES['lm_head.weight']}"
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _validate_identity_inputs(
    *,
    source_revision: str,
    parent_capsule_sha256: str,
    frontier_selector_sha256: str,
) -> None:
    if not FULL_REVISION.fullmatch(source_revision):
        raise ProjectionGateError("v2 source revision must be immutable")
    if parent_capsule_sha256 != GOVERNING_PARENT_CAPSULE_SHA256:
        raise ProjectionGateError(
            "v2 parent capsule is not the exact governing v5 capsule"
        )
    if frontier_selector_sha256 != FRONTIER_SELECTOR_SHA256:
        raise ProjectionGateError(
            "v2 frontier selector is not the governing immutable event"
        )


def _load_fp16_gate(path: Path) -> dict[str, Any]:
    if sha256_path(path) != FP16_FALSIFICATION_GATE_SHA256:
        raise ProjectionGateError("FP16 falsification gate digest mismatch")
    gate = _strict_load_canonical(path)
    required = {
        "schema_version": REFERENCE_GATE_SCHEMA_VERSION,
        "status": "falsified_scope",
        "qat_model_sha256": QAT_MODEL_SHA256,
        "transformers_commit": TRANSFORMERS_COMMIT,
        "phone_execution_count": 0,
        "qnn_output_observed": False,
    }
    for name, expected in required.items():
        if gate.get(name) != expected:
            raise ProjectionGateError(f"FP16 falsification contract mismatch: {name}")
    return gate


def _q_probe(parent_gate: dict[str, Any]) -> dict[str, Any]:
    record = next(
        (
            candidate
            for candidate in parent_gate.get("case_records", [])
            if candidate.get("graph_name") == Q_PROJ_GRAPH
        ),
        None,
    )
    if not isinstance(record, dict):
        raise ProjectionGateError("FP16 gate lacks a frozen Q-projection record")
    return {
        "input_sha256": record["input"]["sha256"],
        "reference_output_sha256": record["reference_output"]["sha256"],
        "primary_case_id": record["case_id"],
    }


def _derive_provider_scale(
    prereg: dict[str, Any], original_scale_path: Path
) -> tuple[bytes, str]:
    original = _read_regular(original_scale_path)
    if (
        len(original) != ORIGINAL_SCALE_BYTES
        or sha256_bytes(original) != ORIGINAL_SCALE_SHA256
    ):
        raise ProjectionGateError(
            "provider-local original LM-head scale identity mismatch"
        )
    transformed = bf16_rne_scales_as_exact_f32(
        original,
        expected_count=ORIGINAL_SCALE_BYTES // 4,
    )
    transformed_sha256 = sha256_bytes(transformed)
    expected = prereg["candidate_contract"]["transformed_scale_sha256"]
    if transformed_sha256 != expected:
        raise ProjectionGateError(
            "provider-derived BF16-RNE scale differs from phone preregistration digest"
        )
    return transformed, transformed_sha256


def _v2_context_gate_payload(
    *,
    parent_gate: dict[str, Any],
    prereg: dict[str, Any],
    prereg_sha256: str,
    oracle: dict[str, Any],
    oracle_sha256: str,
    verification: dict[str, Any],
    verification_sha256: str,
    provider_scale_sha256: str,
    source_revision: str,
    parent_capsule_sha256: str,
) -> dict[str, Any]:
    head = prereg["cases"][0]
    oracle_head = next(
        record
        for record in oracle["case_records"]
        if record["case_id"] == head["case_id"]
    )
    return {
        "schema_version": REFERENCE_GATE_SCHEMA_VERSION,
        "status": "passed_scope",
        "scope": "S16_v2_preregistration_and_full_width_exact_INT32_oracle_pass_only",
        "qat_model_sha256": QAT_MODEL_SHA256,
        "transformers_commit": TRANSFORMERS_COMMIT,
        "l2_threshold_policy_sha256": prereg["threshold_policy_sha256"],
        "numeric_and_ranking_threshold_subset_sha256": NUMERIC_THRESHOLD_SUBSET_SHA256,
        "int16_context_gate_schema": V2_CONTEXT_GATE_SCHEMA,
        "int16_v2_preregistration_sha256": prereg_sha256,
        "int16_v2_oracle_gate_sha256": oracle_sha256,
        "int16_v2_phone_verification_receipt_sha256": verification_sha256,
        "int16_v2_phone_verification_evidence_root_sha256": verification[
            "verification_evidence_root_sha256"
        ],
        "fp16_falsification_gate_sha256": FP16_FALSIFICATION_GATE_SHA256,
        "candidate_id": V2_CANDIDATE_ID,
        "source_revision": source_revision,
        "parent_capsule_sha256": parent_capsule_sha256,
        "frontier_selector_sha256": FRONTIER_SELECTOR_SHA256,
        "probes": {
            Q_PROJ_GRAPH: _q_probe(parent_gate),
            LM_HEAD_GRAPH: {
                "input_sha256": head["s16_input_sha256"],
                "reference_output_sha256": head["authority_output"]["sha256"],
                "exact_dot_oracle_output_sha256": oracle_head["candidate_output"][
                    "sha256"
                ],
                "primary_case_id": head["case_id"],
            },
        },
        "exact_int32_oracle_passed": True,
        "independent_phone_exact_dot_verification_passed": True,
        "provider_derived_scale_sha256": provider_scale_sha256,
        "oracle_execution_count": 3,
        "provider_build_allowed": True,
        "provider_context_generated": False,
        "qnn_execution_count": 0,
        "phone_native_exact_oracle_execution_count": 1,
        "phone_native_independent_verification_count": 1,
        "phone_qnn_execution_count": 0,
        "full_L2_passed": False,
        "claim_boundary": "allows_oracle_bound_provider_build_and_context_attempt_only",
    }


def build_int16_v2_context_gate(
    *,
    fp16_falsification_gate: Path,
    int16_v2_prereg_dir: Path,
    int16_v2_oracle_gate: Path,
    int16_v2_verification_receipt: Path,
    provider_original_scale: Path,
    output_path: Path,
    source_revision: str,
    parent_capsule_sha256: str,
    frontier_selector_sha256: str,
) -> dict[str, Any]:
    """Emit the provider context gate only after the exact-dot gate passes."""

    _validate_identity_inputs(
        source_revision=source_revision,
        parent_capsule_sha256=parent_capsule_sha256,
        frontier_selector_sha256=frontier_selector_sha256,
    )
    parent_gate = _load_fp16_gate(fp16_falsification_gate)
    prereg, prereg_sha256, oracle, oracle_sha256, verification, verification_sha256 = (
        validate_sanitized_phone_authorization(
            prereg_metadata_dir=int16_v2_prereg_dir,
            oracle_gate_path=int16_v2_oracle_gate,
            verification_receipt_path=int16_v2_verification_receipt,
        )
    )
    _, provider_scale_sha256 = _derive_provider_scale(prereg, provider_original_scale)
    if prereg["source_revision"] != source_revision:
        raise ProjectionGateError(
            "v2 context source revision differs from preregistration"
        )
    payload = _v2_context_gate_payload(
        parent_gate=parent_gate,
        prereg=prereg,
        prereg_sha256=prereg_sha256,
        oracle=oracle,
        oracle_sha256=oracle_sha256,
        verification=verification,
        verification_sha256=verification_sha256,
        provider_scale_sha256=provider_scale_sha256,
        source_revision=source_revision,
        parent_capsule_sha256=parent_capsule_sha256,
    )
    digest = write_hashed_json(output_path, payload)
    return {"context_gate_sha256": digest, "status": payload["status"]}


def _provider_authorization(
    *,
    prereg_sha256: str,
    oracle_sha256: str,
    verification_receipt_sha256: str,
    verification_evidence_root_sha256: str,
    context_gate_sha256: str,
    transformed_scale_sha256: str,
    source_revision: str,
) -> dict[str, Any]:
    return {
        "schema_version": V2_PROVIDER_BUILD_AUTH_SCHEMA,
        "candidate_id": V2_CANDIDATE_ID,
        "frontier_selector_sha256": FRONTIER_SELECTOR_SHA256,
        "source_revision": source_revision,
        "preregistration_sha256": prereg_sha256,
        "oracle_gate_sha256": oracle_sha256,
        "verification_receipt_sha256": verification_receipt_sha256,
        "verification_receipt_schema": VERIFICATION_SCHEMA,
        "verification_evidence_root_sha256": verification_evidence_root_sha256,
        "context_gate_sha256": context_gate_sha256,
        "oracle_gate_schema": V2_ORACLE_SCHEMA,
        "required_oracle_status": "passed_scope",
        "required_oracle_execution_count": 3,
        "required_every_case_passed": True,
        "required_provider_build_allowed": True,
        "numeric_and_ranking_threshold_subset_sha256": NUMERIC_THRESHOLD_SUBSET_SHA256,
        "packed_weight_sha256": PACKED_WEIGHT_SHA256,
        "transformed_scale_sha256": transformed_scale_sha256,
        "input_scale": INPUT_SCALE,
        "output_scale": OUTPUT_SCALE,
    }


def render_v2_provider_build_verifier(authorization: dict[str, Any]) -> str:
    """Render a dependency-free gate checked by every provider compilation."""

    expected_authorization = repr(canonical_json(authorization).decode("utf-8"))
    template = """#!/usr/bin/env python3
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

def fail(message):
    raise SystemExit(message)

def reject_constant(value):
    fail(f"non-finite JSON constant: {value}")

def reject_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            fail(f"duplicate JSON key: {key}")
        result[key] = value
    return result

def read_regular(path):
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            fail(f"not a regular file: {path}")
        chunks = []
        while chunk := os.read(descriptor, 8 * 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)

def strict_load(path):
    raw = read_regular(path)
    value = json.loads(raw, parse_constant=reject_constant, object_pairs_hook=reject_duplicates)
    canonical = json.dumps(value, allow_nan=False, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    if canonical != raw:
        fail(f"non-canonical JSON: {path}")
    return value, raw

expected_authorization_raw = __EXPECTED_AUTHORIZATION__.encode("utf-8")
expected_authorization = json.loads(expected_authorization_raw)
oracle_path = Path(sys.argv[1])
receipt_path = Path(sys.argv[2])
authorization_path = Path(sys.argv[3])
oracle, oracle_raw = strict_load(oracle_path)
receipt, receipt_raw = strict_load(receipt_path)
authorization, authorization_raw = strict_load(authorization_path)
if authorization_raw != expected_authorization_raw or authorization != expected_authorization:
    fail("provider build authorization differs from the package-bound contract")
oracle_sha256 = hashlib.sha256(oracle_raw).hexdigest()
if oracle_sha256 != authorization.get("oracle_gate_sha256"):
    fail("oracle gate digest is not authorized")
sidecar = read_regular(oracle_path.with_suffix(oracle_path.suffix + ".sha256"))
if sidecar != f"{oracle_sha256}  {oracle_path.name}\\n".encode("ascii"):
    fail("oracle gate sidecar mismatch")
receipt_sha256 = hashlib.sha256(receipt_raw).hexdigest()
if receipt_sha256 != authorization.get("verification_receipt_sha256"):
    fail("phone verification receipt digest is not authorized")
receipt_sidecar = read_regular(receipt_path.with_suffix(receipt_path.suffix + ".sha256"))
if receipt_sidecar != f"{receipt_sha256}  {receipt_path.name}\\n".encode("ascii"):
    fail("phone verification receipt sidecar mismatch")
required = {
    "schema_version": authorization.get("oracle_gate_schema"),
    "status": authorization.get("required_oracle_status"),
    "candidate_id": authorization.get("candidate_id"),
    "frontier_selector_sha256": authorization.get("frontier_selector_sha256"),
    "source_revision": authorization.get("source_revision"),
    "preregistration_sha256": authorization.get("preregistration_sha256"),
    "numeric_and_ranking_threshold_subset_sha256": authorization.get("numeric_and_ranking_threshold_subset_sha256"),
    "packed_weight_sha256": authorization.get("packed_weight_sha256"),
    "transformed_scale_sha256": authorization.get("transformed_scale_sha256"),
    "input_scale": authorization.get("input_scale"),
    "output_scale": authorization.get("output_scale"),
    "oracle_execution_count": authorization.get("required_oracle_execution_count"),
    "every_case_passed": authorization.get("required_every_case_passed"),
    "provider_build_allowed": authorization.get("required_provider_build_allowed"),
}
for key, expected in required.items():
    if oracle.get(key) != expected:
        fail(f"oracle gate does not authorize provider build: {key}")
records = oracle.get("case_records")
if not isinstance(records, list) or len(records) != 3:
    fail("oracle gate case set mismatch")
if any(record.get("passed") is not True or record.get("failures") != [] for record in records):
    fail("oracle gate contains a failed case")
receipt_required = {
    "schema_version": authorization.get("verification_receipt_schema"),
    "status": "passed_scope",
    "candidate_id": authorization.get("candidate_id"),
    "source_revision": authorization.get("source_revision"),
    "preregistration_sha256": authorization.get("preregistration_sha256"),
    "oracle_gate_sha256": authorization.get("oracle_gate_sha256"),
    "packed_weight_sha256": authorization.get("packed_weight_sha256"),
    "transformed_scale_sha256": authorization.get("transformed_scale_sha256"),
    "numeric_and_ranking_threshold_subset_sha256": authorization.get("numeric_and_ranking_threshold_subset_sha256"),
    "verification_evidence_root_sha256": authorization.get("verification_evidence_root_sha256"),
    "phone_native_exact_oracle_execution_count": 1,
    "phone_native_independent_verification_count": 1,
    "phone_qnn_execution_count": 0,
    "every_case_passed": True,
    "provider_build_allowed": True,
}
for key, expected in receipt_required.items():
    if receipt.get(key) != expected:
        fail(f"phone verification receipt does not authorize provider build: {key}")
"""
    return template.replace("__EXPECTED_AUTHORIZATION__", expected_authorization)


def _gate_build_script(source: bytes) -> bytes:
    marker = b'ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"\n'
    if source.count(marker) != 1:
        raise ProjectionGateError("cannot identify provider build-script root")
    injected = marker + (
        b'python3 "$ROOT/source/verify_v2_provider_build.py" '
        b'"$ROOT/config/v2_phone_oracle_gate.json" '
        b'"$ROOT/config/v2_phone_verification_receipt.json" '
        b'"$ROOT/config/v2_provider_build_authorization.json"\n'
    )
    return source.replace(marker, injected)


def render_v2_context_gate_verifier(authorization: dict[str, Any]) -> str:
    """Render a package-bound verifier for the exact provider context gate."""

    expected_authorization = repr(canonical_json(authorization).decode("utf-8"))
    template = """#!/usr/bin/env python3
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

def fail(message):
    raise SystemExit(message)

def reject_constant(value):
    fail(f"non-finite JSON constant: {value}")

def reject_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            fail(f"duplicate JSON key: {key}")
        result[key] = value
    return result

def read_regular(path):
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            fail(f"not a regular file: {path}")
        chunks = []
        while chunk := os.read(descriptor, 8 * 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)

def strict_load(path):
    raw = read_regular(path)
    value = json.loads(raw, parse_constant=reject_constant, object_pairs_hook=reject_duplicates)
    canonical = json.dumps(value, allow_nan=False, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    if canonical != raw:
        fail(f"non-canonical JSON: {path}")
    return value, raw

expected_authorization_raw = __EXPECTED_AUTHORIZATION__.encode("utf-8")
expected_authorization = json.loads(expected_authorization_raw)
gate_path = Path(sys.argv[1])
authorization_path = Path(sys.argv[2])
gate, gate_raw = strict_load(gate_path)
authorization, authorization_raw = strict_load(authorization_path)
if authorization_raw != expected_authorization_raw or authorization != expected_authorization:
    fail("provider build authorization differs from the package-bound contract")
gate_sha256 = hashlib.sha256(gate_raw).hexdigest()
if gate_sha256 != authorization.get("context_gate_sha256"):
    fail("context gate digest is not authorized")
sidecar = read_regular(gate_path.with_suffix(gate_path.suffix + ".sha256"))
if sidecar != f"{gate_sha256}  {gate_path.name}\\n".encode("ascii"):
    fail("context gate sidecar mismatch")
required = {
    "schema_version": "gemma4_e4b_f5_reference_gate_v1",
    "status": "passed_scope",
    "candidate_id": authorization.get("candidate_id"),
    "frontier_selector_sha256": authorization.get("frontier_selector_sha256"),
    "source_revision": authorization.get("source_revision"),
    "int16_v2_preregistration_sha256": authorization.get("preregistration_sha256"),
    "int16_v2_oracle_gate_sha256": authorization.get("oracle_gate_sha256"),
    "int16_v2_phone_verification_receipt_sha256": authorization.get("verification_receipt_sha256"),
    "int16_v2_phone_verification_evidence_root_sha256": authorization.get("verification_evidence_root_sha256"),
    "numeric_and_ranking_threshold_subset_sha256": authorization.get("numeric_and_ranking_threshold_subset_sha256"),
    "exact_int32_oracle_passed": True,
    "independent_phone_exact_dot_verification_passed": True,
    "oracle_execution_count": authorization.get("required_oracle_execution_count"),
    "provider_build_allowed": True,
    "provider_context_generated": False,
    "qnn_execution_count": 0,
    "phone_native_exact_oracle_execution_count": 1,
    "phone_native_independent_verification_count": 1,
    "phone_qnn_execution_count": 0,
}
for key, expected in required.items():
    if gate.get(key) != expected:
        fail(f"context gate does not authorize provider generation: {key}")
"""
    return template.replace("__EXPECTED_AUTHORIZATION__", expected_authorization)


def _gate_context_script(source: bytes) -> bytes:
    marker = b'OUT="$ROOT/context"\n'
    if source.count(marker) != 1:
        raise ProjectionGateError("cannot identify provider context-script output root")
    injected = marker + (
        b'python3 "$ROOT/source/verify_v2_context_gate.py" "$REFERENCE_GATE" '
        b'"$ROOT/config/v2_provider_build_authorization.json"\n'
    )
    return source.replace(marker, injected)


def _expected_context_gate(
    *,
    context_gate: Path,
    parent_gate: dict[str, Any],
    prereg: dict[str, Any],
    prereg_sha256: str,
    oracle: dict[str, Any],
    oracle_sha256: str,
    verification: dict[str, Any],
    verification_sha256: str,
    provider_scale_sha256: str,
    source_revision: str,
    parent_capsule_sha256: str,
) -> str:
    gate = _strict_load_canonical(context_gate)
    gate_sha256 = sha256_path(context_gate)
    _verify_sidecar(context_gate, gate_sha256)
    expected = _v2_context_gate_payload(
        parent_gate=parent_gate,
        prereg=prereg,
        prereg_sha256=prereg_sha256,
        oracle=oracle,
        oracle_sha256=oracle_sha256,
        verification=verification,
        verification_sha256=verification_sha256,
        provider_scale_sha256=provider_scale_sha256,
        source_revision=source_revision,
        parent_capsule_sha256=parent_capsule_sha256,
    )
    if gate != expected:
        raise ProjectionGateError("v2 context gate mismatch")
    return gate_sha256


def materialize_int16_v2_variant(
    *,
    base_package_dir: Path,
    fp16_falsification_gate: Path,
    int16_v2_prereg_dir: Path,
    int16_v2_oracle_gate: Path,
    int16_v2_verification_receipt: Path,
    context_gate: Path,
    output_dir: Path,
    source_revision: str,
    parent_capsule_sha256: str,
    frontier_selector_sha256: str,
) -> dict[str, Any]:
    """Create an atomic provider package that is impossible before oracle pass."""

    _validate_identity_inputs(
        source_revision=source_revision,
        parent_capsule_sha256=parent_capsule_sha256,
        frontier_selector_sha256=frontier_selector_sha256,
    )
    if output_dir.exists():
        raise ProjectionGateError(f"variant output already exists: {output_dir}")
    parent_gate = _load_fp16_gate(fp16_falsification_gate)
    prereg, prereg_sha256, oracle, oracle_sha256, verification, verification_sha256 = (
        validate_sanitized_phone_authorization(
            prereg_metadata_dir=int16_v2_prereg_dir,
            oracle_gate_path=int16_v2_oracle_gate,
            verification_receipt_path=int16_v2_verification_receipt,
        )
    )
    if prereg["source_revision"] != source_revision:
        raise ProjectionGateError(
            "v2 package source revision differs from preregistration"
        )
    base, base_sha256 = _load_base_package(base_package_dir)
    transformed_scale, provider_scale_sha256 = _derive_provider_scale(
        prereg,
        base_package_dir / SCALE_BASE_RELATIVE_PATH,
    )
    context_gate_sha256 = _expected_context_gate(
        context_gate=context_gate,
        parent_gate=parent_gate,
        prereg=prereg,
        prereg_sha256=prereg_sha256,
        oracle=oracle,
        oracle_sha256=oracle_sha256,
        verification=verification,
        verification_sha256=verification_sha256,
        provider_scale_sha256=provider_scale_sha256,
        source_revision=source_revision,
        parent_capsule_sha256=parent_capsule_sha256,
    )
    scale_contract = prereg["candidate_contract"]

    output_dir.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    temporary = output_dir.with_name(f".{output_dir.name}.tmp.{secrets.token_hex(16)}")
    temporary.mkdir(mode=0o750)
    (temporary / "tensors").mkdir(mode=0o750)
    (temporary / "source").mkdir(mode=0o750)
    (temporary / "config").mkdir(mode=0o750)

    tensor_files: list[dict[str, Any]] = []
    found_scale = False
    found_packed = False
    for record in base["tensor_files"]:
        source = _verify_record(base_package_dir, record)
        relative = record["relative_path"]
        destination = temporary / relative
        payload = _read_regular(source)
        if relative == SCALE_BASE_RELATIVE_PATH:
            if (
                len(payload) != ORIGINAL_SCALE_BYTES
                or sha256_bytes(payload) != ORIGINAL_SCALE_SHA256
            ):
                raise ProjectionGateError(
                    "base package original LM-head scale mismatch"
                )
            payload = transformed_scale
            found_scale = True
        if relative == PACKED_BASE_RELATIVE_PATH:
            if (
                len(payload) != PACKED_WEIGHT_BYTES
                or sha256_bytes(payload) != PACKED_WEIGHT_SHA256
            ):
                raise ProjectionGateError("base package packed LM-head weight mismatch")
            found_packed = True
        _write_exclusive(destination, payload)
        tensor_files.append(_file_record(destination, temporary))
    if not found_scale or not found_packed:
        raise ProjectionGateError("base package lacks exact LM-head weight artifacts")

    authorization = _provider_authorization(
        prereg_sha256=prereg_sha256,
        oracle_sha256=oracle_sha256,
        verification_receipt_sha256=verification_sha256,
        verification_evidence_root_sha256=verification[
            "verification_evidence_root_sha256"
        ],
        context_gate_sha256=context_gate_sha256,
        transformed_scale_sha256=scale_contract["transformed_scale_sha256"],
        source_revision=source_revision,
    )
    generated_files: list[dict[str, Any]] = []
    for record in base["generated_files"]:
        relative = record["relative_path"]
        destination = temporary / relative
        payload = _read_regular(_verify_record(base_package_dir, record))
        if relative == "source/direct_qnn_probes.cpp":
            payload = render_int16_v2_head_cpp().encode("utf-8")
        elif relative == "build_model_library.sh":
            payload = _gate_build_script(payload)
        elif relative == "run_context_generation.sh":
            payload = _gate_context_script(payload)
        _write_exclusive(destination, payload, executable=relative.endswith(".sh"))
        generated_files.append(_file_record(destination, temporary))

    verifier_path = temporary / "source/verify_v2_provider_build.py"
    _write_exclusive(
        verifier_path,
        render_v2_provider_build_verifier(authorization).encode("utf-8"),
        executable=True,
    )
    generated_files.append(_file_record(verifier_path, temporary))
    context_verifier_path = temporary / "source/verify_v2_context_gate.py"
    _write_exclusive(
        context_verifier_path,
        render_v2_context_gate_verifier(authorization).encode("utf-8"),
        executable=True,
    )
    generated_files.append(_file_record(context_verifier_path, temporary))
    authorization_path = temporary / "config/v2_provider_build_authorization.json"
    _write_exclusive(authorization_path, canonical_json(authorization))
    generated_files.append(_file_record(authorization_path, temporary))
    for source_path, filename, digest in (
        (int16_v2_oracle_gate, "v2_phone_oracle_gate.json", oracle_sha256),
        (
            int16_v2_verification_receipt,
            "v2_phone_verification_receipt.json",
            verification_sha256,
        ),
    ):
        destination = temporary / "config" / filename
        _write_exclusive(destination, _read_regular(source_path))
        generated_files.append(_file_record(destination, temporary))
        sidecar = destination.with_suffix(destination.suffix + ".sha256")
        _write_exclusive(sidecar, f"{digest}  {filename}\n".encode("ascii"))
        generated_files.append(_file_record(sidecar, temporary))

    manifest = copy.deepcopy(base)
    manifest["schema_version"] = V2_VARIANT_PACKAGE_SCHEMA
    manifest["status"] = "proposed_executable_backend_unvalidated"
    manifest["claim_class"] = "oracle_passed_S16_v2_provider_source_generation_only"
    manifest["variant_identity"] = {
        "candidate_id": V2_CANDIDATE_ID,
        "source_revision": source_revision,
        "parent_capsule_sha256": parent_capsule_sha256,
        "frontier_selector_sha256": FRONTIER_SELECTOR_SHA256,
        "variant_module_sha256": sha256_path(Path(__file__)),
        "candidate_module_sha256": prereg["implementation_module_sha256"],
        "base_package_manifest_sha256": base_sha256,
        "int16_v2_preregistration_sha256": prereg_sha256,
        "int16_v2_threshold_policy_sha256": prereg["threshold_policy_sha256"],
        "int16_v2_oracle_gate_sha256": oracle_sha256,
        "int16_v2_phone_verification_receipt_sha256": verification_sha256,
        "int16_v2_phone_verification_evidence_root_sha256": verification[
            "verification_evidence_root_sha256"
        ],
        "context_gate_sha256": context_gate_sha256,
        "fp16_falsification_gate_sha256": FP16_FALSIFICATION_GATE_SHA256,
    }
    manifest["lowering"]["lm_head"] = {
        "packed_sha256": PACKED_WEIGHT_SHA256,
        "logical_weight_shape": [OUTPUT_FEATURES, INPUT_FEATURES],
        "signed_shift": -2,
        "qnn_weight_dtype": "QNN_DATATYPE_SFIXED_POINT_8",
        "qnn_encoding": "QNN_QUANTIZATION_ENCODING_BW_AXIS_SCALE_OFFSET",
        "bitwidth": 2,
        "axis": 0,
        "transpose_in1": True,
        "scale_semantics": {
            "original_f32_sha256": ORIGINAL_SCALE_SHA256,
            "transformed_bf16_rne_exact_f32_sha256": scale_contract[
                "transformed_scale_sha256"
            ],
            "transform": "float32_to_bfloat16_RNE_then_exact_float32_storage",
        },
        "activation_abi": {
            "input_dtype": "QNN_DATATYPE_SFIXED_POINT_16",
            "input_scale": INPUT_SCALE,
            "output_dtype": "QNN_DATATYPE_SFIXED_POINT_16",
            "output_scale": OUTPUT_SCALE,
            "candidate_qnn_output_observed": False,
        },
        "pre_provider_oracle": {
            "schema_version": V2_ORACLE_SCHEMA,
            "gate_sha256": oracle_sha256,
            "status": "passed_scope",
            "case_count": 3,
            "dot_products_total": FULL_WIDTH_DOT_PRODUCTS_PER_CASE * 3,
            "threshold_subset_sha256": NUMERIC_THRESHOLD_SUBSET_SHA256,
            "independent_phone_verification_schema": VERIFICATION_SCHEMA,
            "independent_phone_verification_receipt_sha256": verification_sha256,
            "provider_consumed_phone_raw_artifact_count": 0,
            "provider_scale_derivation": "independent_from_provider_local_original_F32_scale",
        },
    }
    for graph in manifest["graphs"]:
        if graph["name"] == LM_HEAD_GRAPH:
            graph["tensor_abi"] = {
                "input": {
                    "dtype": "int16",
                    "shape": [1, 1, INPUT_FEATURES],
                    "bytes": INPUT_FEATURES * 2,
                    "scale": INPUT_SCALE,
                },
                "output": {
                    "dtype": "int16",
                    "shape": [1, 1, OUTPUT_FEATURES],
                    "bytes": OUTPUT_FEATURES * 2,
                    "scale": OUTPUT_SCALE,
                    "surface": "full_pre_softcap_logits",
                },
                "pass_rule": "phone_local_dequantize_then_apply_unchanged_combined_threshold_subset",
            }
    manifest["tensor_files"] = tensor_files
    manifest["generated_files"] = generated_files
    manifest["execution_preconditions"]["model_library_compile"] = (
        f"embedded sanitized oracle {oracle_sha256} and independent phone receipt "
        f"{verification_sha256} must both remain passed_scope; no phone raw artifact is admissible"
    )
    manifest["execution_preconditions"]["context_generation"] = (
        f"exact v2 context gate {context_gate_sha256} required after oracle-gated compile"
    )
    manifest["command_matrix"] = [
        {
            "stage": "compile",
            "command": "QAIRT_ROOT=/opt/qairt ./build_model_library.sh",
        },
        {
            "stage": "context",
            "command": "REFERENCE_GATE=/absolute/path/context_gate.json QAIRT_ROOT=/opt/qairt ./run_context_generation.sh",
        },
    ]
    manifest["nonclaims"] = [
        "no HTP provider context acceptance",
        "no phone QNN execution",
        "no v2 QNN-to-authority numerical fidelity",
        "no L1 or L2 pass",
        "no capsule advancement",
    ]
    encoded = (
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")
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
        "oracle_gate_sha256": oracle_sha256,
        "status": manifest["status"],
    }
