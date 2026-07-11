"""Strict structural identity for SafeTensors files and shard inventories.

The validator consumes only the eight-byte prefix and declared JSON header.
It proves header and inventory structure against an independently asserted file
size; it deliberately does not claim to authenticate the unobserved payload.
Whole-file SHA-256 verification remains a separate provider-local custody gate.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence


SAFETENSORS_PREFIX_BYTES = 8
MAX_SAFETENSORS_HEADER_BYTES = 16 * 1024 * 1024
MAX_SAFETENSORS_INDEX_BYTES = 16 * 1024 * 1024
MAX_TENSOR_RANK = 64
MAX_TENSOR_COUNT = 1_000_000
KNOWN_DTYPE_BYTES = MappingProxyType(
    {
        "BOOL": 1,
        "U8": 1,
        "I8": 1,
        "F8_E4M3": 1,
        "F8_E5M2": 1,
        "F8_E8M0": 1,
        "U16": 2,
        "I16": 2,
        "F16": 2,
        "BF16": 2,
        "U32": 4,
        "I32": 4,
        "F32": 4,
        "U64": 8,
        "I64": 8,
        "F64": 8,
    }
)


class SafeTensorsIdentityError(ValueError):
    """A SafeTensors structural or inventory invariant failed."""


@dataclass(frozen=True)
class TensorIdentity:
    """One validated tensor span relative to the payload region."""

    name: str
    dtype: str
    shape: tuple[int, ...]
    data_start: int
    data_end: int
    element_count: int
    byte_count: int

    def record(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "dtype": self.dtype,
            "shape": list(self.shape),
            "data_offsets": [self.data_start, self.data_end],
            "element_count": self.element_count,
            "byte_count": self.byte_count,
        }


@dataclass(frozen=True)
class SafeTensorsIdentity:
    """Validated structural identity for one complete SafeTensors file."""

    file_name: str
    asserted_file_size: int
    header_size: int
    data_size: int
    header_sha256: str
    metadata_sha256: str
    tensor_contracts_sha256: str
    tensors: tuple[TensorIdentity, ...]

    @property
    def tensor_names(self) -> tuple[str, ...]:
        return tuple(tensor.name for tensor in self.tensors)

    def record(self) -> dict[str, Any]:
        return {
            "file_name": self.file_name,
            "asserted_file_size": self.asserted_file_size,
            "header_size": self.header_size,
            "data_size": self.data_size,
            "header_sha256": self.header_sha256,
            "metadata_sha256": self.metadata_sha256,
            "tensor_count": len(self.tensors),
            "tensor_contracts_sha256": self.tensor_contracts_sha256,
        }


@dataclass(frozen=True)
class SafeTensorsIndexIdentity:
    """Strict parsed identity for ``model.safetensors.index.json``."""

    index_sha256: str
    declared_total_data_size: int
    tensor_to_shard: tuple[tuple[str, str], ...]
    shard_files: tuple[str, ...]
    tensor_to_shard_sha256: str

    def mapping(self) -> Mapping[str, str]:
        return MappingProxyType(dict(self.tensor_to_shard))


@dataclass(frozen=True)
class ShardedSafeTensorsIdentity:
    """Validated exact join between an index and all named shards."""

    index_sha256: str
    shard_count: int
    tensor_count: int
    total_data_size: int
    total_file_size: int
    tensor_to_shard_sha256: str
    shard_contracts_sha256: str
    shards: tuple[SafeTensorsIdentity, ...]

    def record(self) -> dict[str, Any]:
        return {
            "index_sha256": self.index_sha256,
            "shard_count": self.shard_count,
            "tensor_count": self.tensor_count,
            "total_data_size": self.total_data_size,
            "total_file_size": self.total_file_size,
            "tensor_to_shard_sha256": self.tensor_to_shard_sha256,
            "shard_contracts_sha256": self.shard_contracts_sha256,
        }


RangeReader = Callable[[str, int, int], bytes]


def inspect_safetensors_file(
    file_name: str,
    asserted_file_size: int,
    read_range: RangeReader,
    *,
    max_header_bytes: int = MAX_SAFETENSORS_HEADER_BYTES,
    dtype_widths: Mapping[str, int] = KNOWN_DTYPE_BYTES,
) -> SafeTensorsIdentity:
    """Read exactly the prefix/header ranges and validate one file."""

    safe_name = _safe_relative_path(file_name)
    file_size = _positive_int(asserted_file_size, "asserted file size")
    prefix = read_range(safe_name, 0, SAFETENSORS_PREFIX_BYTES - 1)
    if not isinstance(prefix, bytes) or len(prefix) != SAFETENSORS_PREFIX_BYTES:
        raise SafeTensorsIdentityError("SafeTensors prefix range is not exact")
    header_size = int.from_bytes(prefix, "little", signed=False)
    _validate_header_size(header_size, file_size, max_header_bytes)
    header = read_range(
        safe_name,
        SAFETENSORS_PREFIX_BYTES,
        SAFETENSORS_PREFIX_BYTES + header_size - 1,
    )
    if not isinstance(header, bytes) or len(header) != header_size:
        raise SafeTensorsIdentityError("SafeTensors header range is not exact")
    return validate_safetensors_header(
        safe_name,
        prefix,
        header,
        file_size,
        max_header_bytes=max_header_bytes,
        dtype_widths=dtype_widths,
    )


def validate_safetensors_header(
    file_name: str,
    prefix: bytes,
    header_bytes: bytes,
    asserted_file_size: int,
    *,
    max_header_bytes: int = MAX_SAFETENSORS_HEADER_BYTES,
    dtype_widths: Mapping[str, int] = KNOWN_DTYPE_BYTES,
) -> SafeTensorsIdentity:
    """Validate strict JSON, tensor contracts, and exact payload coverage."""

    safe_name = _safe_relative_path(file_name)
    file_size = _positive_int(asserted_file_size, "asserted file size")
    if not isinstance(prefix, bytes) or len(prefix) != SAFETENSORS_PREFIX_BYTES:
        raise SafeTensorsIdentityError(
            "SafeTensors prefix must contain exactly eight bytes"
        )
    header_size = int.from_bytes(prefix, "little", signed=False)
    _validate_header_size(header_size, file_size, max_header_bytes)
    if not isinstance(header_bytes, bytes) or len(header_bytes) != header_size:
        raise SafeTensorsIdentityError(
            "SafeTensors header length disagrees with its prefix"
        )

    trimmed_header = header_bytes.rstrip(b" ")
    if not trimmed_header.startswith(b"{") or not trimmed_header.endswith(b"}"):
        raise SafeTensorsIdentityError(
            "SafeTensors header has non-space padding or invalid framing"
        )
    root = _strict_json(trimmed_header, "SafeTensors header is not strict JSON")
    if not isinstance(root, dict):
        raise SafeTensorsIdentityError("SafeTensors header root must be an object")

    metadata = root.pop("__metadata__", {})
    _validate_metadata(metadata)
    if not root:
        raise SafeTensorsIdentityError("SafeTensors header has no tensor entries")
    if len(root) > MAX_TENSOR_COUNT:
        raise SafeTensorsIdentityError("SafeTensors tensor count exceeds the bound")

    widths = _validate_dtype_widths(dtype_widths)
    data_size = file_size - SAFETENSORS_PREFIX_BYTES - header_size
    tensors = tuple(
        _parse_tensor(name, value, widths, data_size) for name, value in root.items()
    )
    ordered_by_span = tuple(
        sorted(tensors, key=lambda item: (item.data_start, item.data_end, item.name))
    )
    _validate_exact_payload_coverage(ordered_by_span, data_size)
    ordered_by_name = tuple(sorted(tensors, key=lambda item: item.name))
    tensor_records = [tensor.record() for tensor in ordered_by_name]

    return SafeTensorsIdentity(
        file_name=safe_name,
        asserted_file_size=file_size,
        header_size=header_size,
        data_size=data_size,
        header_sha256=_bytes_sha256(header_bytes),
        metadata_sha256=_canonical_sha256(metadata),
        tensor_contracts_sha256=_canonical_sha256(tensor_records),
        tensors=ordered_by_name,
    )


def parse_safetensors_index(index_bytes: bytes) -> SafeTensorsIndexIdentity:
    """Parse and validate a strict Hugging Face SafeTensors shard index."""

    if not isinstance(index_bytes, bytes) or not index_bytes:
        raise SafeTensorsIdentityError("SafeTensors index must be nonempty bytes")
    if len(index_bytes) > MAX_SAFETENSORS_INDEX_BYTES:
        raise SafeTensorsIdentityError("SafeTensors index exceeds the byte bound")
    root = _strict_json(index_bytes, "SafeTensors index is not strict JSON")
    if not isinstance(root, dict):
        raise SafeTensorsIdentityError("SafeTensors index root must be an object")
    if set(root) != {"metadata", "weight_map"}:
        raise SafeTensorsIdentityError(
            "SafeTensors index has missing or unknown root fields"
        )

    metadata = root["metadata"]
    weight_map = root["weight_map"]
    if not isinstance(metadata, dict):
        raise SafeTensorsIdentityError("SafeTensors index metadata must be an object")
    total_size = _positive_int(metadata.get("total_size"), "index total_size")
    if not isinstance(weight_map, dict) or not weight_map:
        raise SafeTensorsIdentityError("SafeTensors index weight_map must be nonempty")

    relations: list[tuple[str, str]] = []
    for tensor_name, shard_name in weight_map.items():
        if (
            not isinstance(tensor_name, str)
            or not tensor_name
            or tensor_name == "__metadata__"
        ):
            raise SafeTensorsIdentityError(
                "SafeTensors index has an invalid tensor name"
            )
        if not isinstance(shard_name, str):
            raise SafeTensorsIdentityError("SafeTensors index shard name must be text")
        safe_shard = _safe_relative_path(shard_name)
        if not safe_shard.endswith(".safetensors"):
            raise SafeTensorsIdentityError(
                "SafeTensors index names a non-SafeTensors shard"
            )
        relations.append((tensor_name, safe_shard))

    relations.sort()
    shard_files = tuple(sorted({shard for _, shard in relations}))
    if len({shard.casefold() for shard in shard_files}) != len(shard_files):
        raise SafeTensorsIdentityError(
            "SafeTensors index has case-colliding shard paths"
        )
    return SafeTensorsIndexIdentity(
        index_sha256=_bytes_sha256(index_bytes),
        declared_total_data_size=total_size,
        tensor_to_shard=tuple(relations),
        shard_files=shard_files,
        tensor_to_shard_sha256=_canonical_sha256(
            [{"tensor": tensor, "shard": shard} for tensor, shard in relations]
        ),
    )


def inspect_sharded_safetensors(
    index_bytes: bytes,
    asserted_file_sizes: Mapping[str, int],
    read_range: RangeReader,
    *,
    max_header_bytes: int = MAX_SAFETENSORS_HEADER_BYTES,
    dtype_widths: Mapping[str, int] = KNOWN_DTYPE_BYTES,
) -> ShardedSafeTensorsIdentity:
    """Validate an index and every exact shard it names."""

    index = parse_safetensors_index(index_bytes)
    if not isinstance(asserted_file_sizes, Mapping):
        raise SafeTensorsIdentityError("asserted shard file sizes must be a mapping")
    normalized_sizes = {
        _safe_relative_path(path): _positive_int(size, "asserted shard file size")
        for path, size in asserted_file_sizes.items()
    }
    if set(normalized_sizes) != set(index.shard_files):
        raise SafeTensorsIdentityError(
            "asserted shard inventory does not exactly match the index"
        )

    shards = {
        path: inspect_safetensors_file(
            path,
            normalized_sizes[path],
            read_range,
            max_header_bytes=max_header_bytes,
            dtype_widths=dtype_widths,
        )
        for path in index.shard_files
    }
    return validate_sharded_safetensors_inventory(index, shards)


def validate_sharded_safetensors_inventory(
    index: SafeTensorsIndexIdentity,
    shards: Mapping[str, SafeTensorsIdentity],
) -> ShardedSafeTensorsIdentity:
    """Require exact index/shard tensor ownership and total payload size."""

    if not isinstance(index, SafeTensorsIndexIdentity):
        raise SafeTensorsIdentityError("index identity has the wrong type")
    if not isinstance(shards, Mapping):
        raise SafeTensorsIdentityError("shard identities must be a mapping")
    if set(shards) != set(index.shard_files):
        raise SafeTensorsIdentityError(
            "validated shard set does not exactly match the index"
        )

    actual_owner: dict[str, str] = {}
    ordered_shards: list[SafeTensorsIdentity] = []
    for shard_name in index.shard_files:
        identity = shards[shard_name]
        if (
            not isinstance(identity, SafeTensorsIdentity)
            or identity.file_name != shard_name
        ):
            raise SafeTensorsIdentityError("shard identity is bound to the wrong file")
        ordered_shards.append(identity)
        for tensor_name in identity.tensor_names:
            if tensor_name in actual_owner:
                raise SafeTensorsIdentityError(
                    "tensor is present in more than one shard"
                )
            actual_owner[tensor_name] = shard_name

    expected_owner = dict(index.tensor_to_shard)
    if actual_owner != expected_owner:
        raise SafeTensorsIdentityError(
            "index tensor ownership disagrees with shard headers"
        )
    total_data_size = sum(shard.data_size for shard in ordered_shards)
    if total_data_size != index.declared_total_data_size:
        raise SafeTensorsIdentityError(
            "index total_size disagrees with shard payload spans"
        )

    shard_records = [shard.record() for shard in ordered_shards]
    return ShardedSafeTensorsIdentity(
        index_sha256=index.index_sha256,
        shard_count=len(ordered_shards),
        tensor_count=len(actual_owner),
        total_data_size=total_data_size,
        total_file_size=sum(shard.asserted_file_size for shard in ordered_shards),
        tensor_to_shard_sha256=index.tensor_to_shard_sha256,
        shard_contracts_sha256=_canonical_sha256(shard_records),
        shards=tuple(ordered_shards),
    )


def _validate_header_size(
    header_size: int, file_size: int, max_header_bytes: int
) -> None:
    if not _is_int(max_header_bytes) or max_header_bytes <= 0:
        raise ValueError("max_header_bytes must be a positive integer")
    if header_size <= 0 or header_size > max_header_bytes:
        raise SafeTensorsIdentityError("SafeTensors header size is outside the bound")
    if SAFETENSORS_PREFIX_BYTES + header_size >= file_size:
        raise SafeTensorsIdentityError(
            "SafeTensors file has no complete payload region"
        )


def _validate_metadata(metadata: Any) -> None:
    if not isinstance(metadata, dict):
        raise SafeTensorsIdentityError("SafeTensors __metadata__ must be an object")
    for key, value in metadata.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise SafeTensorsIdentityError(
                "SafeTensors metadata keys and values must be text"
            )


def _validate_dtype_widths(dtype_widths: Mapping[str, int]) -> Mapping[str, int]:
    if not isinstance(dtype_widths, Mapping) or not dtype_widths:
        raise ValueError("dtype_widths must be a nonempty mapping")
    result: dict[str, int] = {}
    for dtype, width in dtype_widths.items():
        if not isinstance(dtype, str) or not dtype or not _is_int(width) or width <= 0:
            raise ValueError("dtype_widths contains an invalid entry")
        result[dtype] = int(width)
    return MappingProxyType(result)


def _parse_tensor(
    name: Any,
    value: Any,
    dtype_widths: Mapping[str, int],
    data_size: int,
) -> TensorIdentity:
    if not isinstance(name, str) or not name or name.startswith("__"):
        raise SafeTensorsIdentityError("SafeTensors tensor name is invalid")
    if not isinstance(value, dict) or set(value) != {"dtype", "shape", "data_offsets"}:
        raise SafeTensorsIdentityError(
            "SafeTensors tensor contract has missing or unknown fields"
        )

    dtype = value["dtype"]
    if not isinstance(dtype, str) or dtype not in dtype_widths:
        raise SafeTensorsIdentityError("SafeTensors tensor dtype is unknown")
    shape_value = value["shape"]
    if not isinstance(shape_value, list) or len(shape_value) > MAX_TENSOR_RANK:
        raise SafeTensorsIdentityError("SafeTensors tensor shape is invalid")
    shape: list[int] = []
    element_count = 1
    for dimension in shape_value:
        if not _is_int(dimension) or dimension < 0:
            raise SafeTensorsIdentityError(
                "SafeTensors tensor dimensions must be nonnegative integers"
            )
        shape.append(int(dimension))
        element_count *= int(dimension)
        if element_count > data_size and dtype_widths[dtype] > 0:
            raise SafeTensorsIdentityError(
                "SafeTensors tensor shape exceeds the payload bound"
            )

    offsets = value["data_offsets"]
    if (
        not isinstance(offsets, list)
        or len(offsets) != 2
        or not all(_is_int(offset) for offset in offsets)
    ):
        raise SafeTensorsIdentityError("SafeTensors data_offsets must be two integers")
    start, end = (int(offset) for offset in offsets)
    if start < 0 or end < start or end > data_size:
        raise SafeTensorsIdentityError(
            "SafeTensors tensor offsets are outside the payload"
        )
    byte_count = element_count * dtype_widths[dtype]
    if end - start != byte_count:
        raise SafeTensorsIdentityError(
            "SafeTensors tensor span disagrees with dtype and shape"
        )

    return TensorIdentity(
        name=name,
        dtype=dtype,
        shape=tuple(shape),
        data_start=start,
        data_end=end,
        element_count=element_count,
        byte_count=byte_count,
    )


def _validate_exact_payload_coverage(
    tensors: Sequence[TensorIdentity],
    data_size: int,
) -> None:
    cursor = 0
    for tensor in tensors:
        if tensor.data_start < cursor:
            raise SafeTensorsIdentityError("SafeTensors tensor spans overlap")
        if tensor.data_start > cursor:
            raise SafeTensorsIdentityError("SafeTensors payload has an unclaimed gap")
        cursor = tensor.data_end
    if cursor != data_size:
        raise SafeTensorsIdentityError("SafeTensors payload is not covered exactly")


def _strict_json(payload: bytes, message: str) -> Any:
    def reject_constant(_value: str) -> None:
        raise ValueError("non-finite JSON constant")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON object key")
            result[key] = value
        return result

    try:
        return json.loads(
            payload,
            parse_constant=reject_constant,
            object_pairs_hook=unique_object,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        raise SafeTensorsIdentityError(message) from None


def _safe_relative_path(path: Any) -> str:
    if not isinstance(path, str) or not path or path.startswith("/") or "\\" in path:
        raise SafeTensorsIdentityError("SafeTensors path is malformed")
    if "\x00" in path or any(part in ("", ".", "..") for part in path.split("/")):
        raise SafeTensorsIdentityError("SafeTensors path is not a safe relative path")
    return path


def _positive_int(value: Any, label: str) -> int:
    if not _is_int(value) or value <= 0:
        raise SafeTensorsIdentityError(f"{label} must be a positive integer")
    return int(value)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _canonical_sha256(value: Any) -> str:
    try:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise SafeTensorsIdentityError(
            "identity record is not canonical JSON"
        ) from None
    return _bytes_sha256(payload)


def _bytes_sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


__all__ = [
    "KNOWN_DTYPE_BYTES",
    "MAX_SAFETENSORS_HEADER_BYTES",
    "SafeTensorsIdentity",
    "SafeTensorsIdentityError",
    "SafeTensorsIndexIdentity",
    "ShardedSafeTensorsIdentity",
    "TensorIdentity",
    "inspect_safetensors_file",
    "inspect_sharded_safetensors",
    "parse_safetensors_index",
    "validate_safetensors_header",
    "validate_sharded_safetensors_inventory",
]
