#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


EXPECTED_MODEL_ID = "google/gemma-4-E4B"
EXPECTED_REVISION = "7aa32e6889efd6300124851b164f8b364314c3d8"
DEFAULT_EXPECTED_LAYER_INDEX = 0
EXPECTED_DEVICE_MODEL = "NX789J"
EXPECTED_SOC = "SM8750"
P50_THRESHOLD = 0.99
TOKEN_FAILURE_THRESHOLD = 0.99
ALLOWED_BACKENDS = {"vulkan", "opencl"}


@dataclass(frozen=True)
class TensorSpec:
    path: Path
    dtype: str
    shape: tuple[int, ...]


@dataclass(frozen=True)
class TokenCosine:
    flat_index: int
    index: tuple[int, ...]
    cosine: float | None
    reason: str | None = None


class ComparisonError(RuntimeError):
    pass


def normalize_dtype(dtype: str) -> str:
    aliases = {
        "float32": "f32",
        "fp32": "f32",
        "f32": "f32",
        "float64": "f64",
        "fp64": "f64",
        "f64": "f64",
        "float16": "f16",
        "fp16": "f16",
        "half": "f16",
        "f16": "f16",
        "bfloat16": "bf16",
        "bf16": "bf16",
        "uint8": "u8",
        "u8": "u8",
        "uint32": "u32",
        "u32": "u32",
    }
    key = dtype.strip().lower()
    if key not in aliases:
        raise ComparisonError(f"unsupported dtype: {dtype}")
    return aliases[key]


def dtype_size(dtype: str) -> int:
    sizes = {"f16": 2, "bf16": 2, "f32": 4, "f64": 8, "u8": 1, "u32": 4}
    return sizes[normalize_dtype(dtype)]


def parse_shape(text: str) -> tuple[int, ...]:
    parts = text.replace("x", ",").split(",")
    shape = tuple(int(part.strip()) for part in parts if part.strip())
    if not shape or any(dimension <= 0 for dimension in shape):
        raise ComparisonError(f"invalid shape: {text}")
    return shape


def product(values: Iterable[int]) -> int:
    result = 1
    for value in values:
        result *= value
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_entry(path: Path, dtype: str | None = None, shape: tuple[int, ...] | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    if dtype is not None:
        entry["dtype"] = dtype
    if shape is not None:
        entry["shape"] = list(shape)
    return entry


def read_raw_values(spec: TensorSpec) -> list[float]:
    dtype = normalize_dtype(spec.dtype)
    expected_count = product(spec.shape)
    byte_count = spec.path.stat().st_size
    expected_bytes = expected_count * dtype_size(dtype)
    if byte_count != expected_bytes:
        raise ComparisonError(
            f"{spec.path} has {byte_count} bytes, expected {expected_bytes} for "
            f"shape={spec.shape} dtype={dtype}"
        )

    data = spec.path.read_bytes()
    if dtype == "f32":
        return read_array_values(data, "f")
    if dtype == "f64":
        return read_array_values(data, "d")
    if dtype == "f16":
        return [float(value[0]) for value in struct.iter_unpack("<e", data)]
    if dtype == "bf16":
        return read_bf16_values(data)
    raise ComparisonError(f"{dtype} is not a supported output tensor dtype")


def read_array_values(data: bytes, typecode: str) -> list[float]:
    values = array(typecode)
    values.frombytes(data)
    if sys.byteorder != "little":
        values.byteswap()
    return [float(value) for value in values]


def read_bf16_values(data: bytes) -> list[float]:
    values: list[float] = []
    for (raw_value,) in struct.iter_unpack("<H", data):
        fp32_bits = raw_value << 16
        values.append(struct.unpack("<f", struct.pack("<I", fp32_bits))[0])
    return values


def read_mask_values(path: Path, dtype: str, shape: tuple[int, ...]) -> list[int]:
    normalized = normalize_dtype(dtype)
    if normalized not in {"u8", "u32"}:
        raise ComparisonError(f"mask dtype must be u8 or u32, got {dtype}")

    expected_count = product(shape)
    byte_count = path.stat().st_size
    expected_bytes = expected_count * dtype_size(normalized)
    if byte_count != expected_bytes:
        raise ComparisonError(
            f"{path} has {byte_count} bytes, expected {expected_bytes} for "
            f"mask_shape={shape} dtype={normalized}"
        )

    data = path.read_bytes()
    if normalized == "u8":
        return list(data)
    return [int(value[0]) for value in struct.iter_unpack("<I", data)]


def count_non_finite(values: Iterable[float]) -> int:
    return sum(1 for value in values if not math.isfinite(value))


def unravel_index(flat_index: int, shape: tuple[int, ...]) -> tuple[int, ...]:
    if not shape:
        return (flat_index,)
    remaining = flat_index
    coordinates = []
    for dimension in reversed(shape):
        coordinates.append(remaining % dimension)
        remaining //= dimension
    return tuple(reversed(coordinates))


def cosine_fp64(reference: list[float], phone: list[float]) -> tuple[float | None, str | None]:
    dot = 0.0
    reference_norm = 0.0
    phone_norm = 0.0
    for reference_value, phone_value in zip(reference, phone):
        if not math.isfinite(reference_value) or not math.isfinite(phone_value):
            return None, "non_finite_value"
        dot += reference_value * phone_value
        reference_norm += reference_value * reference_value
        phone_norm += phone_value * phone_value

    if reference_norm == 0.0 or phone_norm == 0.0:
        return None, "zero_norm"

    cosine = dot / math.sqrt(reference_norm * phone_norm)
    if not math.isfinite(cosine):
        return None, "non_finite_cosine"
    return cosine, None


def percentile_linear(sorted_values: list[float], percentile: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]

    rank = (len(sorted_values) - 1) * (percentile / 100.0)
    low_index = math.floor(rank)
    high_index = math.ceil(rank)
    if low_index == high_index:
        return sorted_values[low_index]

    low_value = sorted_values[low_index]
    high_value = sorted_values[high_index]
    return low_value + (high_value - low_value) * (rank - low_index)


def compare_non_pad_tokens(
    reference_values: list[float],
    phone_values: list[float],
    output_shape: tuple[int, ...],
    mask_values: list[int],
    max_failed_tokens: int,
) -> dict[str, Any]:
    hidden_size = output_shape[-1]
    token_shape = output_shape[:-1]
    token_slots = product(token_shape)
    if len(mask_values) != token_slots:
        raise ComparisonError(f"mask has {len(mask_values)} entries, expected {token_slots}")

    cosines: list[float] = []
    failed_tokens: list[TokenCosine] = []
    invalid_tokens: list[TokenCosine] = []
    compared_scalar_non_finite = 0
    non_pad_token_count = sum(1 for value in mask_values if value != 0)

    for flat_index, mask_value in enumerate(mask_values):
        if mask_value == 0:
            continue

        vector_start = flat_index * hidden_size
        vector_stop = vector_start + hidden_size
        reference_vector = reference_values[vector_start:vector_stop]
        phone_vector = phone_values[vector_start:vector_stop]
        compared_scalar_non_finite += count_non_finite(reference_vector)
        compared_scalar_non_finite += count_non_finite(phone_vector)

        cosine, reason = cosine_fp64(reference_vector, phone_vector)
        coordinates = unravel_index(flat_index, token_shape)
        if reason is not None:
            invalid_tokens.append(TokenCosine(flat_index, coordinates, None, reason))
            continue

        assert cosine is not None
        cosines.append(cosine)
        if cosine < TOKEN_FAILURE_THRESHOLD and len(failed_tokens) < max_failed_tokens:
            failed_tokens.append(TokenCosine(flat_index, coordinates, cosine))

    sorted_cosines = sorted(cosines)
    percentiles = {
        "p10": percentile_linear(sorted_cosines, 10.0),
        "p50": percentile_linear(sorted_cosines, 50.0),
        "p90": percentile_linear(sorted_cosines, 90.0),
        "min": sorted_cosines[0] if sorted_cosines else None,
        "max": sorted_cosines[-1] if sorted_cosines else None,
    }

    failing_token_count = sum(1 for cosine in cosines if cosine < TOKEN_FAILURE_THRESHOLD)
    return {
        "method": "fp64_cosine_per_non_pad_token",
        "percentile_method": "linear",
        "token_count": non_pad_token_count,
        "finite_cosine_count": len(cosines),
        "token_slots": token_slots,
        "pad_token_count": token_slots - non_pad_token_count,
        "hidden_size": hidden_size,
        "shape": list(output_shape),
        "mask_shape": list(token_shape),
        "percentiles": percentiles,
        "failed_token_threshold": TOKEN_FAILURE_THRESHOLD,
        "failed_token_count": failing_token_count,
        "failed_token_indexes": token_entries(failed_tokens),
        "invalid_token_count": len(invalid_tokens),
        "invalid_token_indexes": token_entries(invalid_tokens[:max_failed_tokens]),
        "compared_scalar_non_finite_count": compared_scalar_non_finite,
    }


def token_entries(tokens: list[TokenCosine]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for token in tokens:
        entry: dict[str, Any] = {
            "flat_token_index": token.flat_index,
            "index": list(token.index),
        }
        if token.cosine is not None:
            entry["cosine"] = token.cosine
        if token.reason is not None:
            entry["reason"] = token.reason
        entries.append(entry)
    return entries


def load_json_file(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    with path.open("r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    if not isinstance(loaded, dict):
        raise ComparisonError(f"{path} must contain a JSON object")
    return loaded


def get_path(document: dict[str, Any], keys: tuple[str, ...]) -> Any:
    current: Any = document
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def first_metadata_value(documents: list[dict[str, Any]], paths: tuple[tuple[str, ...], ...]) -> Any:
    for document in documents:
        for path in paths:
            value = get_path(document, path)
            if value is not None:
                return value
    return None


def extract_output_shape(documents: list[dict[str, Any]]) -> tuple[int, ...] | None:
    paths = (
        ("expected_output_shape",),
        ("output_shape",),
        ("shape",),
        ("shapes", "expected_output"),
        ("shapes", "layer_output"),
        ("outputs", "layer_output", "shape"),
        ("reference", "layer_output", "shape"),
    )
    value = first_metadata_value(documents, paths)
    if value is None:
        return None
    if isinstance(value, str):
        return parse_shape(value)
    if isinstance(value, list) and all(isinstance(item, int) for item in value):
        return tuple(value)
    raise ComparisonError(f"metadata output shape has unsupported form: {value}")


def extract_backend(args: argparse.Namespace, telemetry: dict[str, Any] | None) -> str | None:
    if args.backend:
        return str(args.backend).strip().lower()
    if telemetry is None:
        return None
    value = first_metadata_value(
        [telemetry],
        (
            ("backend",),
            ("execution", "backend"),
            ("runtime", "backend"),
            ("device", "backend"),
        ),
    )
    return str(value).strip().lower() if value is not None else None


def flatten_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, int, float, bool)):
        return [str(value)]
    if isinstance(value, list):
        flattened: list[str] = []
        for item in value:
            flattened.extend(flatten_strings(item))
        return flattened
    if isinstance(value, dict):
        flattened = []
        for item in value.values():
            flattened.extend(flatten_strings(item))
        return flattened
    return [str(value)]


def extract_device_text(args: argparse.Namespace, telemetry: dict[str, Any] | None) -> str:
    parts = []
    if args.device_identity:
        parts.append(args.device_identity)
    if telemetry is not None:
        device_value = first_metadata_value(
            [telemetry],
            (
                ("device_identity",),
                ("device",),
                ("device_info",),
                ("target_device",),
            ),
        )
        parts.extend(flatten_strings(device_value))
    return " ".join(parts)


def build_dtype_path(args: argparse.Namespace, telemetry: dict[str, Any] | None) -> dict[str, Any]:
    telemetry_dtype_path: dict[str, Any] = {}
    if telemetry is not None:
        value = first_metadata_value([telemetry], (("dtype_path",), ("dtypes",)))
        if isinstance(value, dict):
            telemetry_dtype_path = value

    return {
        "input": args.input_dtype or telemetry_dtype_path.get("input"),
        "weights": args.weight_dtype or telemetry_dtype_path.get("weights") or telemetry_dtype_path.get("weight"),
        "accumulation": args.accumulation_dtype or telemetry_dtype_path.get("accumulation"),
        "phone_output": args.phone_dtype,
        "reference_output": args.reference_dtype,
        "comparison": "fp64",
    }


def extract_contract_provenance(documents: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "model_id": first_metadata_value(
            documents,
            (
                ("model_id",),
                ("hf_model_id",),
                ("model", "id"),
                ("model", "model_id"),
                ("source", "model_id"),
            ),
        ),
        "revision": first_metadata_value(
            documents,
            (
                ("revision",),
                ("hf_revision",),
                ("model", "revision"),
                ("source", "revision"),
                ("source", "hf_revision"),
            ),
        ),
        "layer_index": first_metadata_value(
            documents,
            (
                ("layer_index",),
                ("layer", "index"),
                ("layer", "layer_index"),
            ),
        ),
    }


def layer_index_matches(value: Any, expected_layer_index: int) -> bool:
    if value is None:
        return False
    try:
        return int(value) == expected_layer_index
    except (TypeError, ValueError):
        return False


def check_entry(name: str, passed: bool, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": "pass" if passed else "fail",
        "details": details or {},
    }


def build_checks(
    args: argparse.Namespace,
    documents: list[dict[str, Any]],
    output_shape: tuple[int, ...],
    backend: str | None,
    device_text: str,
    dtype_path: dict[str, Any],
) -> list[dict[str, Any]]:
    contract_provenance = extract_contract_provenance(documents)
    metadata_shape = extract_output_shape(documents) if documents else None
    command_details = {
        "phone_command_present": bool(args.phone_command),
        "reference_command_present": bool(args.reference_command),
    }
    dtype_path_complete = all(dtype_path.get(key) for key in ("input", "weights", "accumulation", "phone_output", "reference_output"))
    expected_layer_index = int(args.expected_layer_index)

    return [
        check_entry("model_id", contract_provenance["model_id"] == EXPECTED_MODEL_ID, {"actual": contract_provenance["model_id"], "expected": EXPECTED_MODEL_ID}),
        check_entry("revision", contract_provenance["revision"] == EXPECTED_REVISION, {"actual": contract_provenance["revision"], "expected": EXPECTED_REVISION}),
        check_entry("layer_index", layer_index_matches(contract_provenance["layer_index"], expected_layer_index), {"actual": contract_provenance["layer_index"], "expected": expected_layer_index}),
        check_entry("output_shape", metadata_shape in (None, output_shape), {"metadata": list(metadata_shape) if metadata_shape else None, "actual": list(output_shape)}),
        check_entry("backend", backend in ALLOWED_BACKENDS, {"actual": backend, "allowed": sorted(ALLOWED_BACKENDS)}),
        check_entry("device_identity", EXPECTED_DEVICE_MODEL in device_text and EXPECTED_SOC in device_text, {"actual": device_text, "expected_model": EXPECTED_DEVICE_MODEL, "expected_soc": EXPECTED_SOC}),
        check_entry("dtype_path", dtype_path_complete, dtype_path),
        check_entry("commands", bool(args.phone_command) and bool(args.reference_command), command_details),
    ]


def resolve_shape(args: argparse.Namespace, documents: list[dict[str, Any]]) -> tuple[int, ...]:
    if args.shape:
        return parse_shape(args.shape)
    metadata_shape = extract_output_shape(documents) if documents else None
    if metadata_shape is None:
        raise ComparisonError("output shape must be supplied with --shape or manifest/contract metadata")
    return metadata_shape


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    manifest = load_json_file(args.manifest)
    contract = load_json_file(args.contract)
    telemetry = load_json_file(args.phone_telemetry)
    documents = [document for document in (contract, manifest) if document is not None]
    output_shape = resolve_shape(args, documents)
    if len(output_shape) < 2:
        raise ComparisonError(f"output shape must include token dimensions and hidden size: {output_shape}")

    mask_shape = parse_shape(args.mask_shape) if args.mask_shape else output_shape[:-1]
    if product(mask_shape) != product(output_shape[:-1]):
        raise ComparisonError(f"mask shape {mask_shape} does not match output token shape {output_shape[:-1]}")

    reference_spec = TensorSpec(args.reference_output, normalize_dtype(args.reference_dtype), output_shape)
    phone_spec = TensorSpec(args.phone_output, normalize_dtype(args.phone_dtype), output_shape)
    reference_values = read_raw_values(reference_spec)
    phone_values = read_raw_values(phone_spec)
    mask_values = read_mask_values(args.attention_mask, args.mask_dtype, mask_shape)

    backend = extract_backend(args, telemetry)
    device_text = extract_device_text(args, telemetry)
    dtype_path = build_dtype_path(args, telemetry)
    contract_provenance = extract_contract_provenance(documents)
    checks = build_checks(args, documents, output_shape, backend, device_text, dtype_path)
    comparison = compare_non_pad_tokens(
        reference_values,
        phone_values,
        output_shape,
        mask_values,
        args.max_failed_tokens,
    )
    non_finite = {
        "reference_output_scalar_count": count_non_finite(reference_values),
        "phone_output_scalar_count": count_non_finite(phone_values),
        "compared_scalar_count": comparison["compared_scalar_non_finite_count"],
    }
    comparison["non_finite"] = non_finite
    comparison["non_finite_count"] = non_finite["reference_output_scalar_count"] + non_finite["phone_output_scalar_count"]

    p50 = comparison["percentiles"]["p50"]
    gate_passed = (
        all(check["status"] == "pass" for check in checks)
        and comparison["token_count"] > 0
        and comparison["invalid_token_count"] == 0
        and comparison["compared_scalar_non_finite_count"] == 0
        and comparison["non_finite_count"] == 0
        and p50 is not None
        and p50 >= P50_THRESHOLD
    )

    report = {
        "schema_version": "gemma4_compare_outputs_v1",
        "status": "pass" if gate_passed else "fail",
        "gate": {
            "authority": "Gemma 4 E4B layer 0 phone Vulkan/OpenCL output vs RunPod PyTorch reference",
            "p50_threshold": P50_THRESHOLD,
            "threshold_relaxed": False,
        },
        "tensor_name": args.tensor_name,
        "comparison": comparison,
        "checks": checks,
        "inputs": {
            "reference_output": file_entry(args.reference_output, reference_spec.dtype, output_shape),
            "phone_output": file_entry(args.phone_output, phone_spec.dtype, output_shape),
            "attention_mask": file_entry(args.attention_mask, normalize_dtype(args.mask_dtype), mask_shape),
            "manifest": file_entry(args.manifest) if args.manifest else None,
            "contract": file_entry(args.contract) if args.contract else None,
            "phone_telemetry": file_entry(args.phone_telemetry) if args.phone_telemetry else None,
        },
        "provenance": {
            "model_id": contract_provenance["model_id"],
            "revision": contract_provenance["revision"],
            "layer_index": contract_provenance["layer_index"],
            "expected_model_id": EXPECTED_MODEL_ID,
            "expected_revision": EXPECTED_REVISION,
            "expected_layer_index": int(args.expected_layer_index),
            "backend": backend,
            "device_identity": device_text,
            "dtype_path": dtype_path,
        },
        "commands": {
            "phone": args.phone_command,
            "reference": args.reference_command,
            "compare": " ".join(sys.argv),
        },
    }
    return report


def build_error_report(args: argparse.Namespace, error: Exception) -> dict[str, Any]:
    return {
        "schema_version": "gemma4_compare_outputs_v1",
        "status": "fail",
        "gate": {
            "authority": "Gemma 4 E4B layer 0 phone Vulkan/OpenCL output vs RunPod PyTorch reference",
            "p50_threshold": P50_THRESHOLD,
            "threshold_relaxed": False,
        },
        "error": {
            "type": type(error).__name__,
            "message": str(error),
        },
        "checks": [check_entry("comparison_tool_error", False, {"message": str(error)})],
        "commands": {
            "phone": getattr(args, "phone_command", None),
            "reference": getattr(args, "reference_command", None),
            "compare": " ".join(sys.argv),
        },
    }


def write_report(report: dict[str, Any], path: Path | None) -> None:
    encoded = json.dumps(report, indent=2, sort_keys=True, allow_nan=False)
    if path is None:
        print(encoded)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded + "\n", encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare REDMAGIC phone layer output to RunPod reference with FP64 per-token cosine."
    )
    parser.add_argument("--phone-output", type=Path, required=True, help="Raw phone output tensor.")
    parser.add_argument("--reference-output", type=Path, required=True, help="Raw RunPod reference tensor.")
    parser.add_argument("--attention-mask", type=Path, required=True, help="Raw attention mask; non-zero means compare token.")
    parser.add_argument("--phone-dtype", default="f32", help="Phone output dtype: f32, f64, f16, or bf16.")
    parser.add_argument("--reference-dtype", default="f32", help="Reference output dtype: f32, f64, f16, or bf16.")
    parser.add_argument("--mask-dtype", default="u8", help="Attention mask dtype: u8 or u32.")
    parser.add_argument("--shape", help="Output shape, e.g. 8,1,128,2560. Last dimension is hidden size.")
    parser.add_argument("--mask-shape", help="Mask shape. Defaults to output shape without hidden dimension.")
    parser.add_argument("--manifest", type=Path, help="Layer pack manifest JSON.")
    parser.add_argument("--contract", type=Path, help="Frozen gate contract JSON.")
    parser.add_argument("--phone-telemetry", type=Path, help="Phone runtime telemetry JSON.")
    parser.add_argument("--backend", help="Phone backend. Must be Vulkan or OpenCL for the gate.")
    parser.add_argument("--device-identity", help="Device identity string containing NX789J and SM8750.")
    parser.add_argument("--input-dtype", help="Runtime input activation dtype for dtype-path reporting.")
    parser.add_argument("--weight-dtype", help="Runtime weight dtype for dtype-path reporting.")
    parser.add_argument("--accumulation-dtype", help="Runtime accumulation dtype for dtype-path reporting.")
    parser.add_argument("--phone-command", help="Exact command used to produce the phone output.")
    parser.add_argument("--reference-command", help="Exact command used to produce the RunPod reference.")
    parser.add_argument("--expected-layer-index", type=int, default=DEFAULT_EXPECTED_LAYER_INDEX, help="Expected layer index for provenance checks.")
    parser.add_argument("--tensor-name", default="layer_output", help="Tensor name being compared.")
    parser.add_argument("--max-failed-tokens", type=int, default=128, help="Maximum failed/invalid token records to include.")
    parser.add_argument("--report-json", type=Path, help="Report path. Defaults to stdout.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    try:
        report = build_report(args)
    except Exception as error:
        report = build_error_report(args, error)
    write_report(report, args.report_json)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
