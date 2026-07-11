"""Governed Adreno OpenCL fallback for the Gemma 4 E4B packed INT2 LM head.

This module is control-plane code only.  It freezes and validates the exact
phone-native OpenCL experiment without ever reading candidate logits on the
orchestration host.  The phone runner imports the conversion and metric helpers
so the preregistration and execution paths share one fail-closed contract.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import ctypes
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import stat
import struct
import subprocess
import sys
import tempfile
from typing import Any

PREREGISTRATION_SCHEMA = "gemma4_e4b_adreno_int2_lm_head_preregistration_v1"
OPENCL_CONTRACT_SCHEMA = "gemma4_e4b_adreno_opencl_execution_contract_v1"
PHONE_RECEIPT_SCHEMA = "gemma4_e4b_adreno_int2_lm_head_phone_receipt_v1"
CANDIDATE_ID = (
    "adreno_opencl_direct_packed_w2_scalar_bf16_product_fp32_tree_bf16_rne_v1"
)
S16_FALSIFICATION_SCHEMA = "gemma4_e4b_l2_int16_v2_oracle_falsification_report_v1"
S16_CANDIDATE_ID = "w2_s16_activation_bw2_weight_bf16_rne_scale_s16_output_2m10_v2"
FROZEN_FRONTIER_SELECTOR_SHA256 = (
    "a3ab8f26d5c794e2235a65a93cfc5b4eea7a40d479d9d83be34fabf2ee4a9647"
)
FROZEN_OPENCL_EVIDENCE_SHA256 = (
    "6b0605334c085a4fe7f404ff0723ffe295283796e1048dfdbfdda1bf5a2fe3a2"
)
FROZEN_S16_FALSIFICATION_SHA256 = (
    "44ba89a8ff760d89d05e5ddd2146b2e584f99496ca25fe81091361372bcc5e59"
)
S16_ORACLE_GATE_SHA256 = (
    "aa063f64473de95fdd3208995a51dd314f0e4947c78adc1826a2358ea65693b1"
)
FROZEN_PARENT_FRONTIER_ROOT_SHA256 = (
    "bb045f0761405b521705609d473fa1cb7b504634197256b2b684c061e1fc4d78"
)
FROZEN_PARENT_CAPSULE_SHA256 = (
    "66072e0dee357c9d7c178c3fa3628a6230fa5992659325b80e7eefa6e4dbdd2b"
)

INPUT_FEATURES = 2_560
OUTPUT_FEATURES = 262_144
PACKED_BYTES_PER_ROW = INPUT_FEATURES // 4
PACKED_WEIGHT_BYTES = OUTPUT_FEATURES * PACKED_BYTES_PER_ROW
SCALE_F32_BYTES = OUTPUT_FEATURES * 4
SCALE_BF16_BYTES = OUTPUT_FEATURES * 2
INPUT_BYTES = INPUT_FEATURES * 2
OUTPUT_BYTES = OUTPUT_FEATURES * 2
LOCAL_SIZE = 64
ROWS_PER_WORKGROUP = 8
WORKGROUP_COUNT = OUTPUT_FEATURES // ROWS_PER_WORKGROUP
DISPATCH_COUNT = 8
REPLAY_COUNT_PER_CASE = 2

MODEL_BYTES = 3_525_094_516
MODEL_SHA256 = "391946da2e0bec22288e9fe50a4d31d2401c9570ba3baaf0ba43d644dadeb1d4"
MODEL_REVISION = "9a78a5adac7bca7a9e421634e4b58f41ca7cbca3"
MODEL_REPOSITORY = "google/gemma-4-E4B-it-qat-mobile-transformers"
SCALE_ABSOLUTE_OFFSET = 418_624
PACKED_WEIGHT_ABSOLUTE_OFFSET = 433_630_324
PACKED_WEIGHT_SHA256 = (
    "4733d4ef634f781c7b4094e0df6c432b53e3390e161d546951ea6806de9e0d07"
)
SCALE_F32_SHA256 = "870e405117e2b9b91a86a4210dc66de2d46af52c9274ea46c3193dd69b437eb6"
SCALE_BF16_RNE_AS_F32_SHA256 = (
    "489f4400faaf5f20984bc798d2e1ca581aaf7237e1f37cb6ce505df747e01633"
)
ANDROID_BUILD_FINGERPRINT_STDOUT_SHA256 = (
    "fce358a6cdd6535afbecf6f72088412abaccf9b9902c05800ee8852512f9882f"
)
VENDOR_RUNTIME_FILES = (
    {
        "role": "opencl_icd",
        "absolute_path": "/vendor/lib64/libOpenCL.so",
        "bytes": 87_504,
        "sha256": "cd35cf1ecbfb2053e45566421aa605f819b69ceb5264706ed4feb15bed0942f9",
    },
    {
        "role": "adreno_opencl_driver",
        "absolute_path": "/vendor/lib64/libOpenCL_adreno.so",
        "bytes": 200_392,
        "sha256": "7571bd91b0bb8cad06ce50873865c4161778aa0bf3d2af159a9098a5aa7497ac",
    },
    {
        "role": "adreno_opencl_compiler",
        "absolute_path": "/vendor/lib64/libadreno_compiler_cl.so",
        "bytes": 32_978_208,
        "sha256": "8102c13cd4dedbd26c0aeed63393d44c492879feffb09e2b4026d28f24dbd9fd",
    },
    {
        "role": "adreno_utils",
        "absolute_path": "/vendor/lib64/libadreno_utils.so",
        "bytes": 134_224,
        "sha256": "9616f5dddff3ac30e060950bc4a0f8a20763b4cf51b27bcd752df20d5523b28a",
    },
)
TERMUX_CLANGXX_PATH = "/data/data/com.termux/files/usr/bin/clang++"
TERMUX_CLANGXX_RESOLVED_BYTES = 120_848
TERMUX_CLANGXX_RESOLVED_SHA256 = (
    "34da8e3a9b71793eb70c25670e1fe2bce4d37f1e2837ba8dc0c516c2ca0ffc83"
)
TERMUX_CLANGXX_VERSION_STDOUT_SHA256 = (
    "ba8cc9283b3d1015d7534124eee8908cc5e9b42955e66d10f27a86009c8e76c1"
)

REQUIRED_DEVICE_EXTENSIONS = (
    "cl_khr_subgroups",
    "cl_qcom_bfloat16_product",
)
OPENCL_DEVICE_EXTENSIONS_BYTES = 1_583
OPENCL_DEVICE_EXTENSIONS_SHA256 = (
    "17ee35214eed83330ea64b7b5e476d75bf916e4700da047b024afafbee328b23"
)

SENTINEL_CASE_ID = "off_s16_lattice_bf16_0x3a80"
SENTINEL_INPUT_SHA256 = (
    "8caaaaa8532593127a04ee96fca610df3fc17b44d51e72e5117f5451a94857d6"
)

FROZEN_THRESHOLDS: dict[str, Any] = {
    "max_abs": 0.1875,
    "rms": 0.03,
    "relative_l2": 0.0075,
    "cosine_min": 0.99998,
    "softmax_js_divergence_max": 2.0e-6,
    "top_k_set_overlap_min": 0.9375,
    "top_1_equal": True,
}

FROZEN_CASES: tuple[dict[str, Any], ...] = (
    {
        "case_id": "structured_dynamic",
        "s16_source_relative_path": (
            "inputs/gemma4_e4b_f5_w2_lm_head.structured_dynamic.s16.raw"
        ),
        "s16_source_sha256": (
            "360e7c9f22a0dbb0c135b3a1b696d206e66d02b57b6320eb3e8210d1e880e236"
        ),
        "bf16_input_sha256": (
            "5cca991319c94de485360d2b05b87a80b9b88bc3fe636c8a478ccda9461bada8"
        ),
        "authority_relative_path": (
            "references/structured_dynamic.w2_qat_authority.bf16.raw"
        ),
        "authority_sha256": (
            "30e624bdbad91be77ef6f3d18d46eef2cec6dc5b7a23e7fb4438bf74ae54a30a"
        ),
    },
    {
        "case_id": "balanced_splitmix64",
        "s16_source_relative_path": (
            "inputs/gemma4_e4b_f5_w2_lm_head.balanced_splitmix64.s16.raw"
        ),
        "s16_source_sha256": (
            "8ac246d9328dca16ae2c182906bdb11b8080f0dc71161d28838291eb27f1bf90"
        ),
        "bf16_input_sha256": (
            "2065c350db9e1b835193f7b369b4561bae099eb20931562bede7687727af16aa"
        ),
        "authority_relative_path": (
            "references/balanced_splitmix64.w2_qat_authority.bf16.raw"
        ),
        "authority_sha256": (
            "4d61ad4b4c98089646a6c11e825fb7486090c94fba376d6de1c0a5127c20e26a"
        ),
    },
    {
        "case_id": "low_amplitude_splitmix64",
        "s16_source_relative_path": (
            "inputs/gemma4_e4b_f5_w2_lm_head.low_amplitude_splitmix64.s16.raw"
        ),
        "s16_source_sha256": (
            "05b0526761aa7a5c83156a6bcdf3954a784b23d8b97ffc864e3acc963a3b490a"
        ),
        "bf16_input_sha256": (
            "0d0d93d4562b91ee90d129e0e7c277654659e27a7a87cbc4e4a62276e61dcbe3"
        ),
        "authority_relative_path": (
            "references/low_amplitude_splitmix64.w2_qat_authority.bf16.raw"
        ),
        "authority_sha256": (
            "9769af1ba2b21d3d7803f9bb139c17eb96c0ae0a893ef763b87060d3c68bebd2"
        ),
    },
)

SOURCE_CLOSURE = (
    "polymath_ai/frontier/e4b_adreno_int2_lm_head.py",
    "scripts/host/build_e4b_adreno_int2_prereg.py",
    "scripts/termux/run_e4b_adreno_int2_phone_gate.py",
    "native/e4b_adreno_int2_lm_head/opencl_dynamic_runtime.h",
    "native/e4b_adreno_int2_lm_head/opencl_dynamic_runtime.cpp",
    "native/e4b_adreno_int2_lm_head/e4b_adreno_int2_lm_head.cpp",
    "native/e4b_adreno_int2_lm_head/build_phone.sh",
)
SOURCE_EXECUTABLES = frozenset({"native/e4b_adreno_int2_lm_head/build_phone.sh"})


class AdrenoGateError(RuntimeError):
    """Raised when the OpenCL candidate cannot preserve its frozen contract."""


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _open_regular(path: Path) -> int:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode):
        os.close(descriptor)
        raise AdrenoGateError(f"not a regular file: {path}")
    return descriptor


def read_regular(path: Path) -> bytes:
    descriptor = _open_regular(path)
    try:
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 8 * 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def sha256_path(path: Path) -> str:
    descriptor = _open_regular(path)
    digest = hashlib.sha256()
    try:
        while chunk := os.read(descriptor, 8 * 1024 * 1024):
            digest.update(chunk)
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def hash_range(path: Path, *, offset: int, length: int) -> str:
    if offset < 0 or length <= 0:
        raise AdrenoGateError("range offset and length must be positive")
    descriptor = _open_regular(path)
    digest = hashlib.sha256()
    remaining = length
    cursor = offset
    try:
        metadata = os.fstat(descriptor)
        if offset + length > metadata.st_size:
            raise AdrenoGateError(f"range exceeds file: {path}")
        while remaining:
            chunk = os.pread(descriptor, min(8 * 1024 * 1024, remaining), cursor)
            if not chunk:
                raise AdrenoGateError(f"short range read: {path}")
            digest.update(chunk)
            cursor += len(chunk)
            remaining -= len(chunk)
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def read_range(path: Path, *, offset: int, length: int) -> bytes:
    if offset < 0 or length <= 0:
        raise AdrenoGateError("range offset and length must be positive")
    descriptor = _open_regular(path)
    chunks: list[bytes] = []
    remaining = length
    cursor = offset
    try:
        metadata = os.fstat(descriptor)
        if offset + length > metadata.st_size:
            raise AdrenoGateError(f"range exceeds file: {path}")
        while remaining:
            chunk = os.pread(descriptor, min(8 * 1024 * 1024, remaining), cursor)
            if not chunk:
                raise AdrenoGateError(f"short range read: {path}")
            chunks.append(chunk)
            cursor += len(chunk)
            remaining -= len(chunk)
    finally:
        os.close(descriptor)
    return b"".join(chunks)


def validate_regular(path: Path, *, expected_bytes: int, expected_sha256: str) -> None:
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        raise AdrenoGateError(f"unsafe or non-regular file: {path}")
    if metadata.st_size != expected_bytes:
        raise AdrenoGateError(f"byte count mismatch: {path}")
    if sha256_path(path) != expected_sha256:
        raise AdrenoGateError(f"SHA-256 mismatch: {path}")


def strict_json_decode(payload: bytes, *, source: str) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise AdrenoGateError(f"non-finite JSON constant: {value}")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise AdrenoGateError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    try:
        result = json.loads(
            payload,
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicates,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AdrenoGateError(f"invalid JSON: {source}") from exc
    if not isinstance(result, dict):
        raise AdrenoGateError(f"JSON root must be an object: {source}")
    return result


def strict_json_load(path: Path) -> dict[str, Any]:
    return strict_json_decode(read_regular(path), source=str(path))


def write_exclusive(path: Path, payload: bytes, *, mode: int = 0o600) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, mode)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError(f"short write: {path}")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def resolve_relative(root: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative:
        raise AdrenoGateError("relative path must be a nonempty string")
    value = Path(relative)
    if value.is_absolute() or ".." in value.parts:
        raise AdrenoGateError(f"unsafe relative path: {relative}")
    return root / value


def float32_to_bf16_rne_bits(value: float) -> int:
    bits = struct.unpack("<I", struct.pack("<f", value))[0]
    exponent = bits & 0x7F800000
    mantissa = bits & 0x007FFFFF
    if exponent == 0x7F800000 and mantissa:
        return (bits >> 16) | 0x0040
    rounded = bits + 0x7FFF + ((bits >> 16) & 1)
    return (rounded >> 16) & 0xFFFF


def bf16_bits_to_float(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", (bits & 0xFFFF) << 16))[0]


def s16_input_to_bf16(payload: bytes) -> bytes:
    if len(payload) != INPUT_BYTES:
        raise AdrenoGateError("S16 source input byte count mismatch")
    result = bytearray(INPUT_BYTES)
    for index, (quantized,) in enumerate(struct.iter_unpack("<h", payload)):
        value = quantized * (1.0 / 512.0)
        struct.pack_into("<H", result, index * 2, float32_to_bf16_rne_bits(value))
    return bytes(result)


def off_s16_lattice_sentinel() -> bytes:
    """Build the frozen one-feature BF16 input that S16 factorization cannot encode."""

    result = bytearray(INPUT_BYTES)
    struct.pack_into("<H", result, 0, 0x3A80)
    if bf16_bits_to_float(0x3A80) != 2.0**-10:
        raise AdrenoGateError("sentinel BF16 value drift")
    if (bf16_bits_to_float(0x3A80) * 512.0).is_integer():
        raise AdrenoGateError("sentinel accidentally entered the S16 lattice")
    payload = bytes(result)
    if sha256_bytes(payload) != SENTINEL_INPUT_SHA256:
        raise AdrenoGateError("off-S16-lattice sentinel digest drift")
    return payload


def bf16_rne_scales(source_f32: bytes) -> tuple[bytes, bytes]:
    """Return exact-F32 BF16 values and compact BF16 bits.

    The exact-F32 form is checked against the preregistered S16-v2 transform
    digest.  The compact form is the only scale payload uploaded to the GPU.
    """

    if len(source_f32) != SCALE_F32_BYTES:
        raise AdrenoGateError("source scale byte count mismatch")
    exact_f32 = bytearray(SCALE_F32_BYTES)
    compact_bf16 = bytearray(SCALE_BF16_BYTES)
    for index, (value,) in enumerate(struct.iter_unpack("<f", source_f32)):
        if not math.isfinite(value) or value <= 0.0:
            raise AdrenoGateError(f"invalid row scale at index {index}")
        bf16_bits = float32_to_bf16_rne_bits(value)
        rounded = bf16_bits_to_float(bf16_bits)
        struct.pack_into("<f", exact_f32, index * 4, rounded)
        struct.pack_into("<H", compact_bf16, index * 2, bf16_bits)
    return bytes(exact_f32), bytes(compact_bf16)


def sentinel_reference_output(packed_weight: bytes, compact_scale_bf16: bytes) -> bytes:
    """Compute the exact full-width single-product reference for the 0x3a80 sentinel."""

    if len(packed_weight) != PACKED_WEIGHT_BYTES:
        raise AdrenoGateError("sentinel packed-weight byte count mismatch")
    if len(compact_scale_bf16) != SCALE_BF16_BYTES:
        raise AdrenoGateError("sentinel scale byte count mismatch")
    input_value = bf16_bits_to_float(0x3A80)
    result = bytearray(OUTPUT_BYTES)
    for row in range(OUTPUT_FEATURES):
        scale_bits = struct.unpack_from("<H", compact_scale_bf16, row * 2)[0]
        scale = bf16_bits_to_float(scale_bits)
        unsigned_code = packed_weight[row * PACKED_BYTES_PER_ROW] & 0x03
        weight_bits = float32_to_bf16_rne_bits((unsigned_code - 2) * scale)
        weight = bf16_bits_to_float(weight_bits)
        product_f32 = struct.unpack("<f", struct.pack("<f", input_value * weight))[0]
        struct.pack_into("<H", result, row * 2, float32_to_bf16_rne_bits(product_f32))
    return bytes(result)


def decode_bf16(
    payload: bytes, *, expected_count: int = OUTPUT_FEATURES
) -> list[float]:
    if len(payload) != expected_count * 2:
        raise AdrenoGateError("BF16 payload byte count mismatch")
    return [bf16_bits_to_float(bits) for (bits,) in struct.iter_unpack("<H", payload)]


def _top_k_indices(values: Sequence[float], k: int = 32) -> list[int]:
    if k <= 0 or k > len(values):
        raise AdrenoGateError("invalid top-k metric request")
    return sorted(range(len(values)), key=lambda index: (-values[index], index))[:k]


def vector_metrics(
    reference: Sequence[float], candidate: Sequence[float]
) -> dict[str, Any]:
    if len(reference) != len(candidate) or not reference:
        raise AdrenoGateError("metric vectors must have equal nonzero length")
    if any(not math.isfinite(value) for value in reference) or any(
        not math.isfinite(value) for value in candidate
    ):
        raise AdrenoGateError("non-finite projection output")
    errors = [right - left for left, right in zip(reference, candidate, strict=True)]
    squared_error = math.fsum(value * value for value in errors)
    squared_reference = math.fsum(value * value for value in reference)
    squared_candidate = math.fsum(value * value for value in candidate)
    dot = math.fsum(
        left * right for left, right in zip(reference, candidate, strict=True)
    )
    reference_top = _top_k_indices(reference)
    candidate_top = _top_k_indices(candidate)
    return {
        "max_abs": max(abs(value) for value in errors),
        "rms": math.sqrt(squared_error / len(errors)),
        "relative_l2": (
            math.sqrt(squared_error / squared_reference)
            if squared_reference
            else math.inf
        ),
        "cosine": (
            dot / math.sqrt(squared_reference * squared_candidate)
            if squared_reference and squared_candidate
            else 0.0
        ),
        "top_k_set_overlap": len(set(reference_top) & set(candidate_top)) / 32,
        "top_1_equal": reference_top[0] == candidate_top[0],
    }


def softmax_js_divergence(
    reference: Sequence[float], candidate: Sequence[float]
) -> float:
    if len(reference) != len(candidate) or not reference:
        raise AdrenoGateError("JSD vectors must have equal nonzero length")

    def probabilities(values: Sequence[float]) -> list[float]:
        maximum = max(values)
        exponentials = [math.exp(value - maximum) for value in values]
        denominator = math.fsum(exponentials)
        return [value / denominator for value in exponentials]

    left = probabilities(reference)
    right = probabilities(candidate)
    terms = []
    for left_value, right_value in zip(left, right, strict=True):
        midpoint = 0.5 * (left_value + right_value)
        term = 0.0
        if left_value:
            term += 0.5 * left_value * math.log(left_value / midpoint)
        if right_value:
            term += 0.5 * right_value * math.log(right_value / midpoint)
        terms.append(term)
    return math.fsum(terms)


def adjudicate_metrics(
    metrics: Mapping[str, Any], limits: Mapping[str, Any]
) -> tuple[bool, list[str]]:
    failures = []
    for metric in ("max_abs", "rms", "relative_l2"):
        if float(metrics[metric]) > float(limits[metric]):
            failures.append(f"{metric}_above_{limits[metric]}")
    if float(metrics["cosine"]) < float(limits["cosine_min"]):
        failures.append(f"cosine_below_{limits['cosine_min']}")
    if float(metrics["softmax_js_divergence"]) > float(
        limits["softmax_js_divergence_max"]
    ):
        failures.append(
            f"softmax_js_divergence_above_{limits['softmax_js_divergence_max']}"
        )
    if float(metrics["top_k_set_overlap"]) < float(limits["top_k_set_overlap_min"]):
        failures.append(f"top_k_set_overlap_below_{limits['top_k_set_overlap_min']}")
    if limits["top_1_equal"] and not metrics["top_1_equal"]:
        failures.append("top_1_changed")
    return not failures, failures


def frozen_thresholds() -> dict[str, Any]:
    return dict(FROZEN_THRESHOLDS)


def adjudicate_bf16_output(reference: bytes, candidate: bytes) -> dict[str, Any]:
    left = decode_bf16(reference)
    right = decode_bf16(candidate)
    metrics = vector_metrics(left, right)
    metrics["softmax_js_divergence"] = softmax_js_divergence(left, right)
    passed, failures = adjudicate_metrics(metrics, frozen_thresholds())
    return {"passed": passed, "failures": failures, "metrics": metrics}


def _extension_tokens(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        tokens = tuple(value.split())
    elif isinstance(value, list) and all(isinstance(item, str) for item in value):
        tokens = tuple(value)
    else:
        raise AdrenoGateError("device_extensions must be a string or string list")
    if not tokens or len(tokens) != len(set(tokens)):
        raise AdrenoGateError("device extension list is empty or duplicated")
    return tokens


def normalize_opencl_contract(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != OPENCL_CONTRACT_SCHEMA:
        raise AdrenoGateError("OpenCL contract schema mismatch")
    if payload.get("state") != "passed_scope":
        raise AdrenoGateError("OpenCL contract is not passed_scope")
    if payload.get("candidate_output_observed") is not False:
        raise AdrenoGateError("OpenCL contract contains candidate observations")
    if payload.get("model_or_tensor_access_count") != 0:
        raise AdrenoGateError("OpenCL contract probe accessed model or tensor state")
    loader = payload.get("loader")
    identity = payload.get("identity")
    limits = payload.get("limits")
    compiler = payload.get("compiler_probe")
    if not all(
        isinstance(value, dict) for value in (loader, identity, limits, compiler)
    ):
        raise AdrenoGateError("OpenCL contract sections are incomplete")
    assert isinstance(loader, dict)
    assert isinstance(identity, dict)
    assert isinstance(limits, dict)
    assert isinstance(compiler, dict)
    required_strings = (
        "platform_name",
        "platform_vendor",
        "platform_version",
        "device_name",
        "device_vendor",
        "driver_version",
        "device_version",
        "opencl_c_version",
    )
    for field in required_strings:
        if not isinstance(identity.get(field), str) or not identity[field]:
            raise AdrenoGateError(f"OpenCL identity field missing: {field}")
    expected_identity = {
        "platform_name": "QUALCOMM Snapdragon(TM)",
        "platform_vendor": "QUALCOMM",
        "platform_version": "OpenCL 3.0 QUALCOMM build: 0800.40",
        "device_name": "QUALCOMM Adreno(TM) 830",
        "device_vendor": "QUALCOMM",
        "driver_version": ("OpenCL 3.0 QUALCOMM build: 0800.40 Compiler E031.47.18.30"),
        "device_version": "OpenCL 3.0 Adreno(TM) 830",
        "opencl_c_version": "OpenCL C 3.0 Adreno(TM) 830",
    }
    if any(identity.get(key) != value for key, value in expected_identity.items()):
        raise AdrenoGateError("OpenCL device identity drifted")
    extension_string = identity.get("device_extensions")
    if (
        not isinstance(extension_string, str)
        or len(extension_string.encode("utf-8")) != OPENCL_DEVICE_EXTENSIONS_BYTES
        or sha256_bytes(extension_string.encode("utf-8"))
        != OPENCL_DEVICE_EXTENSIONS_SHA256
    ):
        raise AdrenoGateError("OpenCL device extensions set drifted")
    extensions = _extension_tokens(extension_string)
    missing = [item for item in REQUIRED_DEVICE_EXTENSIONS if item not in extensions]
    if missing:
        raise AdrenoGateError(f"required OpenCL extensions absent: {missing}")
    max_group = limits.get("max_work_group_size")
    production_max_group = limits.get("production_kernel_max_work_group_size")
    local_mem = limits.get("local_mem_bytes")
    max_alloc = limits.get("max_mem_alloc_bytes")
    if max_group != 1_024:
        raise AdrenoGateError("OpenCL maximum workgroup size drifted")
    if (
        not isinstance(production_max_group, int)
        or isinstance(production_max_group, bool)
        or production_max_group < LOCAL_SIZE
        or production_max_group > max_group
    ):
        raise AdrenoGateError("production kernel did not admit local size 64")
    if local_mem != 32_768:
        raise AdrenoGateError("OpenCL local memory size drifted")
    if max_alloc != 1_073_741_824:
        raise AdrenoGateError("OpenCL maximum allocation size drifted")
    if identity.get("endian_little") is not True or identity.get("address_bits") != 64:
        raise AdrenoGateError(
            "OpenCL device ABI is not the frozen little-endian 64-bit ABI"
        )
    loaded_path = loader.get("loaded_path")
    route = loader.get("route")
    if not isinstance(loaded_path, str) or not loaded_path:
        raise AdrenoGateError("OpenCL loader path is missing")
    if route != "android_sphal" or loaded_path != "/vendor/lib64/libOpenCL.so":
        raise AdrenoGateError("OpenCL loader is not the frozen Android SPHAL route")
    expected_compiler = {
        "build_options": "-cl-std=CL3.0",
        "build_succeeded": True,
        "production_kernel_compiled": True,
        "local_size_64_succeeded": True,
        "bf16_product_succeeded": True,
        "bf16_intrinsic_signature": ("float_qcom_mad32_bf16_ushort_ushort_float"),
        "intrinsic_and_rne_runtime_conformance": True,
        "production_buffer_allocation_succeeded": True,
        "production_buffer_bytes": [
            PACKED_WEIGHT_BYTES,
            SCALE_BF16_BYTES,
            INPUT_BYTES,
            OUTPUT_BYTES,
        ],
        "production_kernel_arguments_bound": True,
        "fast_math_enabled": False,
        "subgroup_reduce_used": False,
    }
    if compiler.get("build_options") != expected_compiler["build_options"]:
        raise AdrenoGateError("OpenCL language standard drifted")
    if compiler.get("fast_math_enabled") is not False:
        raise AdrenoGateError("OpenCL fast math is forbidden")
    if compiler != expected_compiler:
        raise AdrenoGateError("OpenCL compiler and arithmetic probe drifted")
    arithmetic_bits = payload.get("arithmetic_observed_bits")
    if arithmetic_bits != [
        "0x40a00000",
        "0xbfc00000",
        "0x40800000",
        "0x3f820200",
        "0x00003f80",
        "0x00003f82",
    ]:
        raise AdrenoGateError("OpenCL arithmetic observed bits drifted")
    return {
        "schema_version": OPENCL_CONTRACT_SCHEMA,
        "state": "passed_scope",
        "candidate_output_observed": False,
        "model_or_tensor_access_count": 0,
        "loader": {"loaded_path": loaded_path, "route": route},
        "identity": {
            **{field: identity[field] for field in required_strings},
            "device_extensions": extension_string,
            "address_bits": 64,
            "endian_little": True,
        },
        "limits": {
            "max_work_group_size": max_group,
            "production_kernel_max_work_group_size": production_max_group,
            "local_mem_bytes": local_mem,
            "max_mem_alloc_bytes": max_alloc,
        },
        "compiler_probe": expected_compiler,
        "arithmetic_observed_bits": list(arithmetic_bits),
    }


def _validate_s16_falsification(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != S16_FALSIFICATION_SCHEMA:
        raise AdrenoGateError("S16 falsification schema mismatch")
    if payload.get("status") != "falsified_scope":
        raise AdrenoGateError("S16 predecessor is not falsified_scope")
    if payload.get("candidate_id") != S16_CANDIDATE_ID:
        raise AdrenoGateError("unexpected S16 predecessor candidate")
    adjudication = payload.get("adjudication")
    transition = payload.get("branch_transition")
    if not isinstance(adjudication, dict) or not isinstance(transition, dict):
        raise AdrenoGateError("S16 falsification decision is incomplete")
    if adjudication.get("standard_htp_s16_family_exhausted") is not True:
        raise AdrenoGateError("S16 family is not exhaustively falsified")
    if transition.get("mandatory_successor") != (
        "Adreno_OpenCL_direct_packed_INT2_BF16_product_FP32_accumulation_BF16_RNE_output"
    ):
        raise AdrenoGateError("OpenCL candidate is not the mandatory successor")
    bindings = payload.get("governing_bindings")
    if not isinstance(bindings, dict) or bindings.get("oracle_gate_sha256") != (
        S16_ORACLE_GATE_SHA256
    ):
        raise AdrenoGateError("S16 oracle gate binding drifted")


def _validate_frontier_selector(selector: Mapping[str, Any]) -> None:
    selected = selector.get("immutable_candidate_contract")
    sentinel = selector.get("off_lattice_sentinel_contract")
    authority = selector.get("frozen_authority_gate")
    if not all(isinstance(value, dict) for value in (selected, sentinel, authority)):
        raise AdrenoGateError("frontier selector contracts are incomplete")
    assert isinstance(selected, dict)
    assert isinstance(sentinel, dict)
    assert isinstance(authority, dict)
    expected_selected = {
        "candidate_id": CANDIDATE_ID,
        "model_sha256": MODEL_SHA256,
        "packed_weight_sha256": PACKED_WEIGHT_SHA256,
        "packed_weight_bytes": PACKED_WEIGHT_BYTES,
        "original_scale_sha256": SCALE_F32_SHA256,
        "original_scale_bytes": SCALE_F32_BYTES,
        "scale_transform": (
            "float32_to_bfloat16_RNE_then_signed_INT2_product_to_bfloat16_RNE"
        ),
        "input_dtype": "bfloat16_bits_in_ushort",
        "input_shape": [1, 1, INPUT_FEATURES],
        "weight_storage": "direct_U2_four_lanes_per_byte_no_dense_expansion",
        "signed_lane_mapping": [-2, -1, 0, 1],
        "output_dtype": "bfloat16_bits_in_ushort",
        "output_shape": [1, 1, OUTPUT_FEATURES],
        "product_intrinsic": "qcom_mad32_bf16_scalar_ushort_ushort_float",
        "accumulator_dtype": "float32",
        "workgroup_size": LOCAL_SIZE,
        "rows_per_workgroup": ROWS_PER_WORKGROUP,
        "workgroup_count": WORKGROUP_COUNT,
        "packed_byte_lane_mapping": "lane_l_consumes_byte_l_plus_64t_for_t_0_through_9",
        "lane_accumulators": 4,
        "lane_accumulator_combine": "(a0_plus_a1)_plus_(a2_plus_a3)",
        "workgroup_reduction": "fixed_local_memory_strides_32_16_8_4_2_1",
        "subgroup_reduce_builtin_used": False,
        "output_rounding": "bit_exact_bfloat16_round_to_nearest_even",
        "weight_residency": "one_upload_one_context_all_cases_and_replays",
        "full_case_replays": 2,
        "byte_identical_replay_required": True,
        "dense_weight_expansion_allowed": False,
        "numeric_ranking_threshold_subset_sha256": sha256_bytes(
            canonical_json(FROZEN_THRESHOLDS)
        ),
        "thresholds_changed": False,
        "candidate_output_observed": False,
    }
    for key, expected in expected_selected.items():
        if selected.get(key) != expected:
            raise AdrenoGateError(f"frontier selector candidate field drifted: {key}")
    expected_sentinel = {
        "input_shape": [1, 1, INPUT_FEATURES],
        "construction": "all_zero_BF16_except_one_preregistered_feature_equal_to_2^-10_BF16",
        "nonzero_feature_index": 0,
        "nonzero_value_bfloat16_bits": "0x3a80",
        "value_is_multiple_of_2^-9": False,
        "input_bytes": INPUT_BYTES,
        "input_sha256": SENTINEL_INPUT_SHA256,
        "reference_output_bytes": OUTPUT_BYTES,
        "reference_rule": "single_product_exact_BF16_semantics_without_reduction_order_ambiguity",
        "pass_rule": (
            "full_width_524288_byte_reference_candidate_equality_and_byte_identical_replays"
        ),
        "candidate_output_observed": False,
    }
    for key, expected in expected_sentinel.items():
        if sentinel.get(key) != expected:
            raise AdrenoGateError(f"frontier selector sentinel field drifted: {key}")
    expected_authority = {
        "case_ids": [case["case_id"] for case in FROZEN_CASES],
        "authority_output_sha256": [case["authority_sha256"] for case in FROZEN_CASES],
        **FROZEN_THRESHOLDS,
        "every_metric_every_case_must_pass": True,
        "replay_outputs_must_be_byte_identical": True,
    }
    for key, expected in expected_authority.items():
        if authority.get(key) != expected:
            raise AdrenoGateError(f"frontier selector authority field drifted: {key}")


def _validate_opencl_evidence(
    report: Mapping[str, Any], selector: Mapping[str, Any], report_sha256: str
) -> dict[str, Any]:
    if report.get("schema_version") != "gemma4_e4b_adreno_opencl_contract_report_v1":
        raise AdrenoGateError("OpenCL evidence report schema mismatch")
    if report.get("status") != "passed_scope":
        raise AdrenoGateError("OpenCL evidence report is not passed_scope")
    custody = report.get("custody")
    identity = report.get("device_identity")
    loader = report.get("loader_contract")
    extension = report.get("extension_contract")
    product = report.get("bfloat16_product_contract")
    arithmetic = report.get("arithmetic_conformance")
    workgroup = report.get("workgroup_contract")
    if not all(
        isinstance(value, dict)
        for value in (
            custody,
            identity,
            loader,
            extension,
            product,
            arithmetic,
            workgroup,
        )
    ):
        raise AdrenoGateError("OpenCL evidence report is incomplete")
    if custody.get("model_or_tensor_access_count") != 0:
        raise AdrenoGateError("OpenCL evidence report accessed model tensors")
    if identity.get("android_build_fingerprint_sha256") != (
        ANDROID_BUILD_FINGERPRINT_STDOUT_SHA256
    ):
        raise AdrenoGateError("Android build fingerprint evidence drifted")
    loader_roles = {
        "opencl_icd": "opencl_icd",
        "adreno_opencl_driver": "adreno_opencl_driver",
        "adreno_opencl_compiler": "adreno_opencl_compiler",
        "adreno_utils": "adreno_utils",
    }
    for frozen in VENDOR_RUNTIME_FILES:
        observed = loader.get(loader_roles[str(frozen["role"])])
        if not isinstance(observed, dict):
            raise AdrenoGateError("OpenCL vendor runtime evidence is incomplete")
        if (
            observed.get("bytes") != frozen["bytes"]
            or observed.get("sha256") != frozen["sha256"]
        ):
            raise AdrenoGateError("OpenCL vendor runtime evidence drifted")
    if extension.get("required_extensions_present") != [
        "cl_qcom_bfloat16_product",
        "cl_khr_subgroups",
    ]:
        raise AdrenoGateError("OpenCL required extension evidence drifted")
    if product.get("required_build_option") != "-cl-std=CL3.0":
        raise AdrenoGateError("OpenCL build-option evidence drifted")
    if product.get("exact_signature") != "float_qcom_mad32_bf16_ushort_ushort_float":
        raise AdrenoGateError("OpenCL BF16 ABI evidence drifted")
    if arithmetic.get("bf16_3f81_times_bf16_3f81_f32_bits") != "0x3f820200":
        raise AdrenoGateError("OpenCL BF16 arithmetic evidence drifted")
    if (
        arithmetic.get("bfloat16_rne_tie_3f808000") != "0x3f80"
        or arithmetic.get("bfloat16_rne_tie_3f818000") != "0x3f82"
    ):
        raise AdrenoGateError("OpenCL BF16 RNE evidence drifted")
    if workgroup.get("selected_local_workgroup_size") != LOCAL_SIZE:
        raise AdrenoGateError("OpenCL workgroup evidence drifted")
    if workgroup.get("required_reduction") != "explicit_fixed_local_memory_binary_tree":
        raise AdrenoGateError("OpenCL reduction evidence drifted")
    selector_contract = selector.get("live_opencl_contract")
    if not isinstance(selector_contract, dict):
        raise AdrenoGateError("frontier selector lacks live OpenCL contract")
    if selector_contract.get("report_sha256") != report_sha256:
        raise AdrenoGateError("frontier selector OpenCL report binding mismatch")
    if selector_contract.get("opencl_icd_sha256") != VENDOR_RUNTIME_FILES[0]["sha256"]:
        raise AdrenoGateError("frontier selector ICD binding drifted")
    if (
        selector_contract.get("adreno_opencl_driver_sha256")
        != VENDOR_RUNTIME_FILES[1]["sha256"]
    ):
        raise AdrenoGateError("frontier selector driver binding drifted")
    if (
        selector_contract.get("adreno_opencl_compiler_sha256")
        != VENDOR_RUNTIME_FILES[2]["sha256"]
    ):
        raise AdrenoGateError("frontier selector compiler binding drifted")
    return {
        "report_sha256": report_sha256,
        "android_build_fingerprint_stdout_sha256": (
            ANDROID_BUILD_FINGERPRINT_STDOUT_SHA256
        ),
        "vendor_runtime_files": [dict(item) for item in VENDOR_RUNTIME_FILES],
    }


def _git_output(root: Path, *arguments: str) -> str:
    try:
        process = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise AdrenoGateError("git source binding failed") from exc
    value = process.stdout.strip()
    if not value:
        raise AdrenoGateError("git source binding returned empty output")
    return value


def _git_tree_entry(root: Path, revision: str, relative: str) -> tuple[str, str]:
    fields = _git_output(root, "ls-tree", revision, "--", relative).split(maxsplit=3)
    if len(fields) != 4:
        raise AdrenoGateError(f"git tree entry is invalid: {relative}")
    mode, kind, object_id, observed_relative = fields
    if (
        mode not in {"100644", "100755"}
        or kind != "blob"
        or observed_relative != relative
    ):
        raise AdrenoGateError(f"git tree entry drifted: {relative}")
    return mode, object_id


def _working_git_mode(path: Path) -> str:
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise AdrenoGateError(f"source closure path is not regular: {path}")
    return "100755" if metadata.st_mode & 0o111 else "100644"


def source_closure(root: Path) -> tuple[str, list[dict[str, Any]]]:
    revision = _git_output(root, "rev-parse", "HEAD")
    records = []
    for relative in SOURCE_CLOSURE:
        path = resolve_relative(root, relative)
        payload = read_regular(path)
        head_blob = _git_output(root, "rev-parse", f"HEAD:{relative}")
        head_mode, tree_blob = _git_tree_entry(root, revision, relative)
        working_blob = _git_output(root, "hash-object", "--", relative)
        working_mode = _working_git_mode(path)
        if working_blob != head_blob or tree_blob != head_blob:
            raise AdrenoGateError(f"source blob is not committed at HEAD: {relative}")
        if working_mode != head_mode:
            raise AdrenoGateError(f"source mode is not committed at HEAD: {relative}")
        if relative in SOURCE_EXECUTABLES and (
            head_mode != "100755" or not os.access(path, os.X_OK)
        ):
            raise AdrenoGateError(f"required source is not executable: {relative}")
        records.append(
            {
                "relative_path": relative,
                "bytes": len(payload),
                "sha256": sha256_bytes(payload),
                "git_blob_oid": head_blob,
                "git_mode": head_mode,
            }
        )
    return revision, records


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _rename_noreplace(source: Path, destination: Path) -> None:
    library = ctypes.CDLL(None, use_errno=True)
    source_bytes = os.fsencode(source)
    destination_bytes = os.fsencode(destination)
    renameat2 = getattr(library, "renameat2", None)
    linux_or_android = sys.platform.startswith("linux") or sys.platform == "android"
    if linux_or_android and renameat2 is not None:
        renameat2.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        renameat2.restype = ctypes.c_int
        result = renameat2(-100, source_bytes, -100, destination_bytes, 1)
    elif linux_or_android:
        syscall_numbers = {
            "aarch64": 276,
            "arm64": 276,
            "riscv64": 276,
            "x86_64": 316,
            "amd64": 316,
            "armv7l": 382,
            "i386": 353,
            "i686": 353,
        }
        number = syscall_numbers.get(platform.machine().casefold())
        syscall = getattr(library, "syscall", None)
        if number is None or syscall is None:
            raise AdrenoGateError("atomic no-replace rename is unavailable")
        syscall.restype = ctypes.c_long
        result = syscall(number, -100, source_bytes, -100, destination_bytes, 1)
    elif sys.platform == "darwin":
        renamex_np = getattr(library, "renamex_np", None)
        if renamex_np is None:
            raise AdrenoGateError("atomic no-replace rename is unavailable")
        renamex_np.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        renamex_np.restype = ctypes.c_int
        result = renamex_np(source_bytes, destination_bytes, 0x00000004)
    else:
        raise AdrenoGateError("atomic no-replace rename is unsupported")
    if result == 0:
        return
    error = ctypes.get_errno()
    if error in {errno.EEXIST, errno.ENOTEMPTY}:
        raise FileExistsError(destination)
    raise OSError(error, os.strerror(error), destination)


def _publish_preregistration_directory(
    output_dir: Path, preregistration: Mapping[str, Any]
) -> None:
    parent = output_dir.parent
    parent_metadata = parent.lstat()
    if not stat.S_ISDIR(parent_metadata.st_mode) or parent.is_symlink():
        raise AdrenoGateError("preregistration parent must be a real directory")
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.tmp-", dir=parent))
    os.chmod(temporary, 0o700)
    try:
        encoded = canonical_json(preregistration)
        prereg_path = temporary / "preregistration.json"
        write_exclusive(prereg_path, encoded)
        digest = sha256_bytes(encoded)
        write_exclusive(
            prereg_path.with_suffix(".json.sha256"),
            f"{digest}  {prereg_path.name}\n".encode("ascii"),
        )
        _fsync_directory(temporary)
        _rename_noreplace(temporary, output_dir)
        _fsync_directory(parent)
    except Exception:
        if temporary.exists():
            for child in temporary.iterdir():
                child.unlink()
            temporary.rmdir()
        raise


def _case_contracts() -> list[dict[str, Any]]:
    records = []
    for case in FROZEN_CASES:
        case_id = case["case_id"]
        records.append(
            {
                **case,
                "s16_source_bytes": INPUT_BYTES,
                "bf16_input_bytes": INPUT_BYTES,
                "bf16_input_relative_path": f"private_inputs/{case_id}.bf16.raw",
                "authority_bytes": OUTPUT_BYTES,
                "output_bytes": OUTPUT_BYTES,
                "replay_output_relative_paths": [
                    f"private_outputs/{case_id}.replay0.bf16.raw",
                    f"private_outputs/{case_id}.replay1.bf16.raw",
                ],
                "candidate_output_present": False,
            }
        )
    return records


def build_preregistration(
    *,
    repository_root: Path,
    frontier_selector_path: Path,
    s16_falsification_path: Path,
    opencl_evidence_report_path: Path,
    opencl_contract_path: Path,
    output_dir: Path,
    created_at_utc: str,
) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(output_dir)
    s16_raw = read_regular(s16_falsification_path)
    if sha256_bytes(s16_raw) != FROZEN_S16_FALSIFICATION_SHA256:
        raise AdrenoGateError("S16 falsification ancestor digest drifted")
    s16 = strict_json_decode(s16_raw, source=str(s16_falsification_path))
    _validate_s16_falsification(s16)
    selector_raw = read_regular(frontier_selector_path)
    if sha256_bytes(selector_raw) != FROZEN_FRONTIER_SELECTOR_SHA256:
        raise AdrenoGateError("frontier selector ancestor digest drifted")
    selector = strict_json_decode(selector_raw, source=str(frontier_selector_path))
    selected_contract = selector.get("immutable_candidate_contract")
    if selector.get("schema_version") != "gemma4_e4b_frontier_event_v1":
        raise AdrenoGateError("frontier selector schema mismatch")
    if selector.get("state") != "selected" or not isinstance(selected_contract, dict):
        raise AdrenoGateError("frontier selector is not selected")
    if selected_contract.get("candidate_id") != CANDIDATE_ID:
        raise AdrenoGateError("frontier selector candidate mismatch")
    if selector.get("phone_execution_started") is not False:
        raise AdrenoGateError("frontier selector is no longer unexecuted")
    if selector.get("candidate_output_observed") is not False:
        raise AdrenoGateError("frontier selector contains candidate output")
    _validate_frontier_selector(selector)
    opencl_evidence_raw = read_regular(opencl_evidence_report_path)
    if sha256_bytes(opencl_evidence_raw) != FROZEN_OPENCL_EVIDENCE_SHA256:
        raise AdrenoGateError("OpenCL evidence ancestor digest drifted")
    opencl_evidence = _validate_opencl_evidence(
        strict_json_decode(
            opencl_evidence_raw, source=str(opencl_evidence_report_path)
        ),
        selector,
        sha256_bytes(opencl_evidence_raw),
    )
    opencl_raw = read_regular(opencl_contract_path)
    opencl = normalize_opencl_contract(
        strict_json_decode(opencl_raw, source=str(opencl_contract_path))
    )
    opencl_source_sha256 = sha256_bytes(opencl_raw)
    opencl_canonical_sha256 = sha256_bytes(canonical_json(opencl))
    opencl_evidence = {
        **opencl_evidence,
        "execution_contract_source_sha256": opencl_source_sha256,
        "execution_contract_canonical_sha256": opencl_canonical_sha256,
        "execution_contract_generator_relative_path": (
            "native/e4b_adreno_int2_lm_head/e4b_adreno_int2_lm_head.cpp"
        ),
    }
    thresholds = frozen_thresholds()
    source_revision, closure = source_closure(repository_root)
    preregistration = {
        "schema_version": PREREGISTRATION_SCHEMA,
        "state": "frozen_unobserved",
        "created_at_utc": created_at_utc,
        "candidate_id": CANDIDATE_ID,
        "candidate_output_observed": False,
        "phone_execution_count": 0,
        "frontier_selector_sha256": sha256_bytes(selector_raw),
        "parent_frontier_root_sha256": selector["parent_frontier_root_sha256"],
        "parent_capsule_sha256": selector["parent_capsule_sha256"],
        "mandatory_predecessor": {
            "schema_version": S16_FALSIFICATION_SCHEMA,
            "sha256": sha256_bytes(s16_raw),
            "oracle_gate_sha256": s16["governing_bindings"]["oracle_gate_sha256"],
            "status": "falsified_scope",
            "standard_htp_s16_family_exhausted": True,
        },
        "model": {
            "repository": MODEL_REPOSITORY,
            "revision": MODEL_REVISION,
            "bytes": MODEL_BYTES,
            "sha256": MODEL_SHA256,
            "raw_location": "phone_private_authority",
            "execution_dependency": False,
            "role": "immutable_lineage_only_runtime_uses_exact_extracted_tensors",
        },
        "tensor_contract": {
            "packed_weight": {
                "dtype": "U8",
                "logical_shape": [OUTPUT_FEATURES, INPUT_FEATURES],
                "storage_shape": [OUTPUT_FEATURES, PACKED_BYTES_PER_ROW],
                "absolute_offset": PACKED_WEIGHT_ABSOLUTE_OFFSET,
                "bytes": PACKED_WEIGHT_BYTES,
                "sha256": PACKED_WEIGHT_SHA256,
                "lane_mapping": [-2, -1, 0, 1],
                "bits_per_weight": 2,
                "dense_expansion_forbidden": True,
                "runtime_source": "phone_private_hash_bound_regular_file",
            },
            "row_scale": {
                "source_dtype": "F32",
                "shape": [OUTPUT_FEATURES, 1],
                "absolute_offset": SCALE_ABSOLUTE_OFFSET,
                "source_bytes": SCALE_F32_BYTES,
                "source_sha256": SCALE_F32_SHA256,
                "transform": "F32_to_BF16_RNE",
                "transformed_exact_f32_sha256": SCALE_BF16_RNE_AS_F32_SHA256,
                "gpu_dtype": "BF16_bits_in_U16",
                "gpu_bytes": SCALE_BF16_BYTES,
                "runtime_source": "phone_private_hash_bound_regular_file",
            },
        },
        "kernel_contract": {
            "input_dtype": "BF16_bits_in_U16",
            "output_dtype": "BF16_bits_in_U16",
            "weight_dequantization": (
                "signed_INT2_code_times_BF16_RNE_row_scale_then_BF16_RNE_weight"
            ),
            "product": "exact_FP32_product_of_two_BF16_operands",
            "accumulation": (
                "four_ascending_10_term_FP32_lane_chains_pairwise_combined_then_"
                "fixed_local_tree_strides_32_16_8_4_2_1"
            ),
            "output_rounding": "explicit_BF16_RNE_bits",
            "local_size": LOCAL_SIZE,
            "rows_per_workgroup": ROWS_PER_WORKGROUP,
            "workgroup_count": WORKGROUP_COUNT,
            "global_size": WORKGROUP_COUNT * LOCAL_SIZE,
            "dense_weight_expansion": False,
            "fast_relaxed_math": False,
            "fp_contract": False,
        },
        "residency_and_replay": {
            "process_count": 1,
            "context_count": 1,
            "program_build_count": 1,
            "packed_weight_upload_count": 1,
            "scale_upload_count": 1,
            "authority_case_count": 3,
            "sentinel_case_count": 1,
            "replays_per_case": REPLAY_COUNT_PER_CASE,
            "dispatch_count": DISPATCH_COUNT,
            "replay_must_be_byte_identical": True,
        },
        "opencl_contract": opencl,
        "opencl_contract_source_sha256": opencl_source_sha256,
        "opencl_contract_canonical_sha256": opencl_canonical_sha256,
        "opencl_evidence": opencl_evidence,
        "toolchain_contract": {
            "compiler_path_class": "termux_prefix_bin_clangxx",
            "compiler_resolved_bytes": TERMUX_CLANGXX_RESOLVED_BYTES,
            "compiler_resolved_sha256": TERMUX_CLANGXX_RESOLVED_SHA256,
            "compiler_version_stdout_sha256": TERMUX_CLANGXX_VERSION_STDOUT_SHA256,
            "arbitrary_CXX_override_allowed": False,
        },
        "required_device_extensions": list(REQUIRED_DEVICE_EXTENSIONS),
        "cases": _case_contracts(),
        "off_s16_lattice_sentinel": {
            "case_id": SENTINEL_CASE_ID,
            "purpose": "reject_exact_INT32_or_S16_lattice_specialization",
            "construction": "all_zero_BF16_except_feature_0_equal_to_0x3a80_2m10",
            "nonzero_feature_index": 0,
            "nonzero_value_bfloat16_bits": "0x3a80",
            "input_dtype": "BF16_bits_in_U16",
            "input_bytes": INPUT_BYTES,
            "input_sha256": SENTINEL_INPUT_SHA256,
            "input_relative_path": f"private_inputs/{SENTINEL_CASE_ID}.bf16.raw",
            "contains_value_off_s16_2m9_lattice": True,
            "reference_rule": "full_width_single_product_exact_BF16_semantics",
            "authority_metric_gate": False,
            "replay_output_relative_paths": [
                f"private_outputs/{SENTINEL_CASE_ID}.replay0.bf16.raw",
                f"private_outputs/{SENTINEL_CASE_ID}.replay1.bf16.raw",
            ],
            "replay_must_be_byte_identical": True,
            "candidate_output_present": False,
        },
        "numeric_and_ranking_thresholds": thresholds,
        "thresholds_sha256": sha256_bytes(canonical_json(thresholds)),
        "source_binding": {
            "repository": "Zer0pa/Polymath-AI",
            "revision": source_revision,
            "head_equals_revision": True,
            "every_closure_file_matches_head_blob": True,
            "every_closure_file_matches_head_mode": True,
        },
        "source_closure": closure,
        "phone_execution_envelope": {
            "execution_plane": "phone_native_termux",
            "raw_inputs_outputs_and_tensors": "phone_private_no_egress",
            "sanitized_hash_bound_receipt_only": True,
            "thermal_sensor_type": "pmih010x_lite_tz",
            "thermal_stop_at_or_above_millidegrees_c": 90_000,
            "minimum_available_memory_bytes": 2_147_483_648,
            "minimum_available_storage_bytes": 2_147_483_648,
            "maximum_wall_time_seconds": 14_400,
        },
        "failure_rule": (
            "falsify_this_OpenCL_candidate_without_threshold_relaxation_if_any_case_metric_"
            "replay_runtime_source_or_tensor_contract_fails"
        ),
        "custody": {
            "raw_model_weight_input_reference_and_candidate_egress": False,
            "raw_phone_private_upload_to_provider": False,
            "repository_or_comet_raw_payload_storage": False,
            "sanitized_hash_bound_metadata_only": True,
        },
        "nonclaims": [
            "no_OpenCL_candidate_output_observed",
            "no_full_L1_or_L2_pass",
            "no_learning_or_authority_quality_pass",
            "no_performance_claim_before_authority_fidelity",
        ],
    }
    _publish_preregistration_directory(output_dir, preregistration)
    return preregistration


def validate_source_closure(root: Path, preregistration: Mapping[str, Any]) -> None:
    binding = preregistration.get("source_binding")
    if not isinstance(binding, dict):
        raise AdrenoGateError("source binding is absent")
    revision = binding.get("revision")
    if binding.get("repository") != "Zer0pa/Polymath-AI" or not isinstance(
        revision, str
    ):
        raise AdrenoGateError("source repository or revision binding mismatch")
    if _git_output(root, "rev-parse", "HEAD") != revision:
        raise AdrenoGateError("execution checkout HEAD drifted from preregistration")
    records = preregistration.get("source_closure")
    if not isinstance(records, list) or not records:
        raise AdrenoGateError("source closure is empty")
    expected = set(SOURCE_CLOSURE)
    observed: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise AdrenoGateError("invalid source closure record")
        relative = record.get("relative_path")
        if (
            not isinstance(relative, str)
            or relative not in expected
            or relative in observed
        ):
            raise AdrenoGateError("source closure path mismatch")
        path = resolve_relative(root, relative)
        validate_regular(
            path,
            expected_bytes=int(record["bytes"]),
            expected_sha256=str(record["sha256"]),
        )
        head_blob = _git_output(root, "rev-parse", f"HEAD:{relative}")
        head_mode, tree_blob = _git_tree_entry(root, revision, relative)
        working_blob = _git_output(root, "hash-object", "--", relative)
        working_mode = _working_git_mode(path)
        if (
            record.get("git_blob_oid") != head_blob
            or tree_blob != head_blob
            or working_blob != head_blob
        ):
            raise AdrenoGateError("execution source blob drifted")
        if record.get("git_mode") != head_mode or working_mode != head_mode:
            raise AdrenoGateError("execution source mode drifted")
        if relative in SOURCE_EXECUTABLES and (
            head_mode != "100755" or not os.access(path, os.X_OK)
        ):
            raise AdrenoGateError("required execution source is not executable")
        observed.add(relative)
    if observed != expected:
        raise AdrenoGateError("source closure is incomplete")


def validate_preregistration(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != PREREGISTRATION_SCHEMA:
        raise AdrenoGateError("preregistration schema mismatch")
    if payload.get("state") != "frozen_unobserved":
        raise AdrenoGateError("preregistration is not frozen-unobserved")
    if payload.get("candidate_id") != CANDIDATE_ID:
        raise AdrenoGateError("candidate identity mismatch")
    if payload.get("candidate_output_observed") is not False:
        raise AdrenoGateError("preregistration contains candidate observations")
    if payload.get("phone_execution_count") != 0:
        raise AdrenoGateError("preregistration phone execution count is not zero")
    expected_ancestry = {
        "frontier_selector_sha256": FROZEN_FRONTIER_SELECTOR_SHA256,
        "parent_frontier_root_sha256": FROZEN_PARENT_FRONTIER_ROOT_SHA256,
        "parent_capsule_sha256": FROZEN_PARENT_CAPSULE_SHA256,
    }
    for field, expected in expected_ancestry.items():
        if payload.get(field) != expected:
            raise AdrenoGateError(f"preregistration {field} drifted")
    if payload.get("numeric_and_ranking_thresholds") != FROZEN_THRESHOLDS:
        raise AdrenoGateError("preregistered thresholds drifted")
    if payload.get("thresholds_sha256") != sha256_bytes(
        canonical_json(FROZEN_THRESHOLDS)
    ):
        raise AdrenoGateError("threshold digest mismatch")
    normalized_opencl = normalize_opencl_contract(payload.get("opencl_contract", {}))
    source_contract_sha256 = payload.get("opencl_contract_source_sha256")
    canonical_contract_sha256 = payload.get("opencl_contract_canonical_sha256")
    if (
        not isinstance(source_contract_sha256, str)
        or len(source_contract_sha256) != 64
        or any(
            character not in "0123456789abcdef" for character in source_contract_sha256
        )
    ):
        raise AdrenoGateError("OpenCL execution contract source digest is invalid")
    if canonical_contract_sha256 != sha256_bytes(canonical_json(normalized_opencl)):
        raise AdrenoGateError("OpenCL execution contract canonical digest drifted")
    model = payload.get("model")
    expected_model = {
        "repository": MODEL_REPOSITORY,
        "revision": MODEL_REVISION,
        "bytes": MODEL_BYTES,
        "sha256": MODEL_SHA256,
        "raw_location": "phone_private_authority",
        "execution_dependency": False,
        "role": "immutable_lineage_only_runtime_uses_exact_extracted_tensors",
    }
    if model != expected_model:
        raise AdrenoGateError("model lineage contract drifted")
    cases = payload.get("cases")
    if not isinstance(cases, list) or len(cases) != 3:
        raise AdrenoGateError("exactly three cases are required")
    expected_cases = _case_contracts()
    if cases != expected_cases:
        raise AdrenoGateError("case contract drifted")
    sentinel = payload.get("off_s16_lattice_sentinel")
    if not isinstance(sentinel, dict):
        raise AdrenoGateError("off-S16-lattice sentinel is absent")
    if sentinel.get("input_sha256") != SENTINEL_INPUT_SHA256:
        raise AdrenoGateError("off-S16-lattice sentinel drifted")
    expected_sentinel = {
        "case_id": SENTINEL_CASE_ID,
        "purpose": "reject_exact_INT32_or_S16_lattice_specialization",
        "construction": "all_zero_BF16_except_feature_0_equal_to_0x3a80_2m10",
        "nonzero_feature_index": 0,
        "nonzero_value_bfloat16_bits": "0x3a80",
        "input_dtype": "BF16_bits_in_U16",
        "input_bytes": INPUT_BYTES,
        "input_sha256": SENTINEL_INPUT_SHA256,
        "input_relative_path": f"private_inputs/{SENTINEL_CASE_ID}.bf16.raw",
        "contains_value_off_s16_2m9_lattice": True,
        "reference_rule": "full_width_single_product_exact_BF16_semantics",
        "authority_metric_gate": False,
        "replay_output_relative_paths": [
            f"private_outputs/{SENTINEL_CASE_ID}.replay0.bf16.raw",
            f"private_outputs/{SENTINEL_CASE_ID}.replay1.bf16.raw",
        ],
        "replay_must_be_byte_identical": True,
        "candidate_output_present": False,
    }
    if sentinel != expected_sentinel:
        raise AdrenoGateError("off-S16-lattice sentinel contract drifted")
    tensor = payload.get("tensor_contract")
    if not isinstance(tensor, dict):
        raise AdrenoGateError("tensor contract missing")
    packed = tensor.get("packed_weight")
    if (
        not isinstance(packed, dict)
        or packed.get("dense_expansion_forbidden") is not True
    ):
        raise AdrenoGateError("direct-packed invariant missing")
    expected_packed = {
        "dtype": "U8",
        "logical_shape": [OUTPUT_FEATURES, INPUT_FEATURES],
        "storage_shape": [OUTPUT_FEATURES, PACKED_BYTES_PER_ROW],
        "absolute_offset": PACKED_WEIGHT_ABSOLUTE_OFFSET,
        "bytes": PACKED_WEIGHT_BYTES,
        "sha256": PACKED_WEIGHT_SHA256,
        "lane_mapping": [-2, -1, 0, 1],
        "bits_per_weight": 2,
        "dense_expansion_forbidden": True,
        "runtime_source": "phone_private_hash_bound_regular_file",
    }
    expected_scale = {
        "source_dtype": "F32",
        "shape": [OUTPUT_FEATURES, 1],
        "absolute_offset": SCALE_ABSOLUTE_OFFSET,
        "source_bytes": SCALE_F32_BYTES,
        "source_sha256": SCALE_F32_SHA256,
        "transform": "F32_to_BF16_RNE",
        "transformed_exact_f32_sha256": SCALE_BF16_RNE_AS_F32_SHA256,
        "gpu_dtype": "BF16_bits_in_U16",
        "gpu_bytes": SCALE_BF16_BYTES,
        "runtime_source": "phone_private_hash_bound_regular_file",
    }
    if packed != expected_packed or tensor.get("row_scale") != expected_scale:
        raise AdrenoGateError("tensor contract drifted")
    kernel = payload.get("kernel_contract")
    expected_kernel = {
        "input_dtype": "BF16_bits_in_U16",
        "output_dtype": "BF16_bits_in_U16",
        "weight_dequantization": (
            "signed_INT2_code_times_BF16_RNE_row_scale_then_BF16_RNE_weight"
        ),
        "product": "exact_FP32_product_of_two_BF16_operands",
        "accumulation": (
            "four_ascending_10_term_FP32_lane_chains_pairwise_combined_then_"
            "fixed_local_tree_strides_32_16_8_4_2_1"
        ),
        "output_rounding": "explicit_BF16_RNE_bits",
        "local_size": LOCAL_SIZE,
        "rows_per_workgroup": ROWS_PER_WORKGROUP,
        "workgroup_count": WORKGROUP_COUNT,
        "global_size": WORKGROUP_COUNT * LOCAL_SIZE,
        "dense_weight_expansion": False,
        "fast_relaxed_math": False,
        "fp_contract": False,
    }
    if kernel != expected_kernel:
        raise AdrenoGateError("kernel arithmetic contract drifted")
    expected_residency = {
        "process_count": 1,
        "context_count": 1,
        "program_build_count": 1,
        "packed_weight_upload_count": 1,
        "scale_upload_count": 1,
        "authority_case_count": 3,
        "sentinel_case_count": 1,
        "replays_per_case": REPLAY_COUNT_PER_CASE,
        "dispatch_count": DISPATCH_COUNT,
        "replay_must_be_byte_identical": True,
    }
    if payload.get("residency_and_replay") != expected_residency:
        raise AdrenoGateError("residency and replay contract drifted")
    toolchain = payload.get("toolchain_contract")
    expected_toolchain = {
        "compiler_path_class": "termux_prefix_bin_clangxx",
        "compiler_resolved_bytes": TERMUX_CLANGXX_RESOLVED_BYTES,
        "compiler_resolved_sha256": TERMUX_CLANGXX_RESOLVED_SHA256,
        "compiler_version_stdout_sha256": TERMUX_CLANGXX_VERSION_STDOUT_SHA256,
        "arbitrary_CXX_override_allowed": False,
    }
    if toolchain != expected_toolchain:
        raise AdrenoGateError("toolchain contract drifted")
    evidence = payload.get("opencl_evidence")
    if not isinstance(evidence, dict):
        raise AdrenoGateError("OpenCL evidence binding is absent")
    expected_evidence = {
        "report_sha256": FROZEN_OPENCL_EVIDENCE_SHA256,
        "android_build_fingerprint_stdout_sha256": (
            ANDROID_BUILD_FINGERPRINT_STDOUT_SHA256
        ),
        "vendor_runtime_files": [dict(item) for item in VENDOR_RUNTIME_FILES],
        "execution_contract_source_sha256": source_contract_sha256,
        "execution_contract_canonical_sha256": canonical_contract_sha256,
        "execution_contract_generator_relative_path": (
            "native/e4b_adreno_int2_lm_head/e4b_adreno_int2_lm_head.cpp"
        ),
    }
    if evidence != expected_evidence:
        raise AdrenoGateError("OpenCL evidence runtime binding drifted")
    binding = payload.get("source_binding")
    if not isinstance(binding, dict):
        raise AdrenoGateError("source binding is absent")
    if binding.get("repository") != "Zer0pa/Polymath-AI":
        raise AdrenoGateError("source repository binding drifted")
    revision = binding.get("revision")
    if (
        not isinstance(revision, str)
        or len(revision) not in {40, 64}
        or any(character not in "0123456789abcdef" for character in revision)
    ):
        raise AdrenoGateError("source revision binding is invalid")
    if (
        binding.get("head_equals_revision") is not True
        or binding.get("every_closure_file_matches_head_blob") is not True
        or binding.get("every_closure_file_matches_head_mode") is not True
    ):
        raise AdrenoGateError("source cleanliness binding drifted")
    expected_envelope = {
        "execution_plane": "phone_native_termux",
        "raw_inputs_outputs_and_tensors": "phone_private_no_egress",
        "sanitized_hash_bound_receipt_only": True,
        "thermal_sensor_type": "pmih010x_lite_tz",
        "thermal_stop_at_or_above_millidegrees_c": 90_000,
        "minimum_available_memory_bytes": 2_147_483_648,
        "minimum_available_storage_bytes": 2_147_483_648,
        "maximum_wall_time_seconds": 14_400,
    }
    if payload.get("phone_execution_envelope") != expected_envelope:
        raise AdrenoGateError("phone execution envelope drifted")
    expected_custody = {
        "raw_model_weight_input_reference_and_candidate_egress": False,
        "raw_phone_private_upload_to_provider": False,
        "repository_or_comet_raw_payload_storage": False,
        "sanitized_hash_bound_metadata_only": True,
    }
    if payload.get("custody") != expected_custody:
        raise AdrenoGateError("phone custody contract drifted")
    expected_failure_rule = (
        "falsify_this_OpenCL_candidate_without_threshold_relaxation_if_any_case_metric_"
        "replay_runtime_source_or_tensor_contract_fails"
    )
    if payload.get("failure_rule") != expected_failure_rule:
        raise AdrenoGateError("failure rule drifted")
    expected_predecessor = {
        "schema_version": S16_FALSIFICATION_SCHEMA,
        "sha256": FROZEN_S16_FALSIFICATION_SHA256,
        "oracle_gate_sha256": S16_ORACLE_GATE_SHA256,
        "status": "falsified_scope",
        "standard_htp_s16_family_exhausted": True,
    }
    if payload.get("mandatory_predecessor") != expected_predecessor:
        raise AdrenoGateError("mandatory predecessor binding drifted")
    if payload.get("required_device_extensions") != list(REQUIRED_DEVICE_EXTENSIONS):
        raise AdrenoGateError("required device extensions drifted")


def runtime_environment(opencl_contract: Mapping[str, Any]) -> dict[str, str]:
    normalized = normalize_opencl_contract(opencl_contract)
    identity = normalized["identity"]
    loader = normalized["loader"]
    names = {
        "POLYMATH_EXPECT_OPENCL_LOADED_PATH": loader["loaded_path"],
        "POLYMATH_EXPECT_OPENCL_LOAD_ROUTE": loader["route"],
        "POLYMATH_EXPECT_OPENCL_PLATFORM_NAME": identity["platform_name"],
        "POLYMATH_EXPECT_OPENCL_PLATFORM_VENDOR": identity["platform_vendor"],
        "POLYMATH_EXPECT_OPENCL_PLATFORM_VERSION": identity["platform_version"],
        "POLYMATH_EXPECT_OPENCL_DEVICE_NAME": identity["device_name"],
        "POLYMATH_EXPECT_OPENCL_DEVICE_VENDOR": identity["device_vendor"],
        "POLYMATH_EXPECT_OPENCL_DRIVER_VERSION": identity["driver_version"],
        "POLYMATH_EXPECT_OPENCL_DEVICE_VERSION": identity["device_version"],
        "POLYMATH_EXPECT_OPENCL_C_VERSION": identity["opencl_c_version"],
        "POLYMATH_EXPECT_OPENCL_DEVICE_EXTENSIONS": identity["device_extensions"],
    }
    return {key: str(value) for key, value in names.items()}


__all__ = [
    "AdrenoGateError",
    "CANDIDATE_ID",
    "FROZEN_CASES",
    "FROZEN_THRESHOLDS",
    "INPUT_BYTES",
    "MODEL_BYTES",
    "MODEL_SHA256",
    "OUTPUT_BYTES",
    "PACKED_WEIGHT_ABSOLUTE_OFFSET",
    "PACKED_WEIGHT_BYTES",
    "PACKED_WEIGHT_SHA256",
    "PHONE_RECEIPT_SCHEMA",
    "PREREGISTRATION_SCHEMA",
    "SCALE_ABSOLUTE_OFFSET",
    "SCALE_BF16_RNE_AS_F32_SHA256",
    "SCALE_F32_BYTES",
    "SCALE_F32_SHA256",
    "SENTINEL_CASE_ID",
    "SENTINEL_INPUT_SHA256",
    "adjudicate_bf16_output",
    "bf16_rne_scales",
    "build_preregistration",
    "canonical_json",
    "decode_bf16",
    "frozen_thresholds",
    "hash_range",
    "normalize_opencl_contract",
    "off_s16_lattice_sentinel",
    "read_range",
    "read_regular",
    "resolve_relative",
    "runtime_environment",
    "sentinel_reference_output",
    "s16_input_to_bf16",
    "sha256_bytes",
    "sha256_path",
    "strict_json_decode",
    "strict_json_load",
    "validate_preregistration",
    "validate_regular",
    "validate_source_closure",
    "write_exclusive",
]
