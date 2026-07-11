from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

import pytest

from polymath_ai.frontier.safetensors_identity import (
    SafeTensorsIdentityError,
    inspect_safetensors_file,
    inspect_sharded_safetensors,
    parse_safetensors_index,
    validate_safetensors_header,
    validate_sharded_safetensors_inventory,
)


VALID_HEADER = {
    "a.weight": {"dtype": "F32", "shape": [2], "data_offsets": [0, 8]},
    "b.scale": {"dtype": "I8", "shape": [3], "data_offsets": [8, 11]},
    "__metadata__": {"format": "pt"},
}


def encode_header(root: dict[str, Any]) -> bytes:
    encoded = json.dumps(root, sort_keys=True, separators=(",", ":")).encode()
    return encoded + b" " * (-len(encoded) % 8)


def parts(
    root: dict[str, Any] = VALID_HEADER,
    *,
    data_size: int = 11,
) -> tuple[bytes, bytes, int]:
    header = encode_header(root)
    prefix = len(header).to_bytes(8, "little")
    return prefix, header, 8 + len(header) + data_size


def validate(
    root: dict[str, Any] = VALID_HEADER,
    *,
    data_size: int = 11,
    file_name: str = "model.safetensors",
):
    prefix, header, file_size = parts(root, data_size=data_size)
    return validate_safetensors_header(file_name, prefix, header, file_size)


class RangeStore:
    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files
        self.calls: list[tuple[str, int, int]] = []

    def __call__(self, path: str, start: int, end: int) -> bytes:
        self.calls.append((path, start, end))
        return self.files[path][start : end + 1]


def make_file(root: dict[str, Any], data: bytes) -> bytes:
    header = encode_header(root)
    return len(header).to_bytes(8, "little") + header + data


def test_validates_exact_tensor_spans_and_payload_coverage() -> None:
    identity = validate()

    assert identity.asserted_file_size == 8 + identity.header_size + 11
    assert identity.data_size == 11
    assert identity.tensor_names == ("a.weight", "b.scale")
    assert identity.tensors[0].element_count == 2
    assert identity.tensors[0].byte_count == 8
    assert len(identity.header_sha256) == 64
    assert len(identity.tensor_contracts_sha256) == 64


def test_inspector_reads_only_prefix_and_declared_header_ranges() -> None:
    file_bytes = make_file(VALID_HEADER, b"x" * 11)
    store = RangeStore({"model.safetensors": file_bytes})

    identity = inspect_safetensors_file(
        "model.safetensors",
        len(file_bytes),
        store,
    )

    assert identity.data_size == 11
    assert store.calls == [
        ("model.safetensors", 0, 7),
        ("model.safetensors", 8, 7 + identity.header_size),
    ]


def test_inspector_rejects_short_range_without_fallback_read() -> None:
    def short_reader(_path: str, _start: int, _end: int) -> bytes:
        return b"short"

    with pytest.raises(SafeTensorsIdentityError, match="prefix range is not exact"):
        inspect_safetensors_file("model.safetensors", 100, short_reader)


@pytest.mark.parametrize(
    "header_size,file_size,message",
    [
        (0, 100, "outside the bound"),
        (16 * 1024 * 1024 + 8, 32 * 1024 * 1024, "outside the bound"),
        (16, 24, "no complete payload"),
    ],
)
def test_rejects_unsafe_header_prefix(
    header_size: int,
    file_size: int,
    message: str,
) -> None:
    prefix = header_size.to_bytes(8, "little")

    with pytest.raises(SafeTensorsIdentityError, match=message):
        validate_safetensors_header(
            "model.safetensors",
            prefix,
            b" " * header_size,
            file_size,
        )


@pytest.mark.parametrize(
    "raw",
    [
        b'{"a":{"dtype":"U8","shape":[1],"data_offsets":[0,1]},"a":{"dtype":"U8","shape":[1],"data_offsets":[0,1]}}',
        b'{"a":{"dtype":"U8","shape":[NaN],"data_offsets":[0,1]}}',
    ],
)
def test_rejects_duplicate_keys_and_nonfinite_json(raw: bytes) -> None:
    header = raw + b" " * (-len(raw) % 8)
    prefix = len(header).to_bytes(8, "little")

    with pytest.raises(SafeTensorsIdentityError, match="strict JSON"):
        validate_safetensors_header(
            "model.safetensors",
            prefix,
            header,
            8 + len(header) + 1,
        )


def test_rejects_non_space_header_padding() -> None:
    header = encode_header(VALID_HEADER)
    header = header[:-1] + b"\n"
    prefix = len(header).to_bytes(8, "little")

    with pytest.raises(SafeTensorsIdentityError, match="non-space padding"):
        validate_safetensors_header(
            "model.safetensors",
            prefix,
            header,
            8 + len(header) + 11,
        )


def invalid_tensor(**changes: Any) -> dict[str, Any]:
    root = {"tensor": {"dtype": "U8", "shape": [4], "data_offsets": [0, 4]}}
    root["tensor"].update(changes)
    return root


@pytest.mark.parametrize(
    "root,data_size,message",
    [
        (invalid_tensor(dtype="UNKNOWN"), 4, "dtype is unknown"),
        (invalid_tensor(shape=[True]), 4, "dimensions"),
        (invalid_tensor(shape=[-1]), 4, "dimensions"),
        (invalid_tensor(shape=[1] * 65), 4, "shape is invalid"),
        (invalid_tensor(data_offsets=[0]), 4, "data_offsets"),
        (invalid_tensor(data_offsets=[-1, 3]), 4, "outside the payload"),
        (invalid_tensor(data_offsets=[0, 5]), 4, "outside the payload"),
        (invalid_tensor(data_offsets=[0, 3]), 4, "span disagrees"),
        (
            {
                "tensor": {
                    "dtype": "U8",
                    "shape": [4],
                    "data_offsets": [0, 4],
                    "unknown": True,
                }
            },
            4,
            "missing or unknown fields",
        ),
        ({"__metadata__": {"not": 1}, **invalid_tensor()}, 4, "metadata"),
    ],
)
def test_rejects_malformed_tensor_contracts(
    root: dict[str, Any],
    data_size: int,
    message: str,
) -> None:
    with pytest.raises(SafeTensorsIdentityError, match=message):
        validate(root, data_size=data_size)


def test_rejects_shape_that_cannot_fit_asserted_payload() -> None:
    root = invalid_tensor(shape=[262_144, 2_560], data_offsets=[0, 1])

    with pytest.raises(SafeTensorsIdentityError, match="shape exceeds"):
        validate(root, data_size=1)


@pytest.mark.parametrize(
    "root,data_size,message",
    [
        (
            {
                "a": {"dtype": "U8", "shape": [3], "data_offsets": [0, 3]},
                "b": {"dtype": "U8", "shape": [3], "data_offsets": [2, 5]},
            },
            5,
            "overlap",
        ),
        (
            {
                "a": {"dtype": "U8", "shape": [2], "data_offsets": [0, 2]},
                "b": {"dtype": "U8", "shape": [2], "data_offsets": [3, 5]},
            },
            5,
            "unclaimed gap",
        ),
        (
            {"a": {"dtype": "U8", "shape": [2], "data_offsets": [0, 2]}},
            3,
            "not covered exactly",
        ),
    ],
)
def test_rejects_overlap_gap_and_unclaimed_tail(
    root: dict[str, Any],
    data_size: int,
    message: str,
) -> None:
    with pytest.raises(SafeTensorsIdentityError, match=message):
        validate(root, data_size=data_size)


def index_bytes(
    weight_map: dict[str, str],
    total_size: int,
    **extra: Any,
) -> bytes:
    payload = {
        "metadata": {"total_size": total_size},
        "weight_map": weight_map,
        **extra,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def shard_fixture() -> tuple[bytes, dict[str, bytes], dict[str, int]]:
    shard_a = make_file(
        {"a": {"dtype": "U8", "shape": [2], "data_offsets": [0, 2]}},
        b"aa",
    )
    shard_b = make_file(
        {"b": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]}},
        b"bbbb",
    )
    files = {"part-1.safetensors": shard_a, "part-2.safetensors": shard_b}
    index = index_bytes(
        {"a": "part-1.safetensors", "b": "part-2.safetensors"},
        6,
    )
    return index, files, {name: len(value) for name, value in files.items()}


def test_validates_exact_shard_and_index_inventory() -> None:
    index, files, sizes = shard_fixture()
    store = RangeStore(files)

    identity = inspect_sharded_safetensors(index, sizes, store)

    assert identity.shard_count == 2
    assert identity.tensor_count == 2
    assert identity.total_data_size == 6
    assert identity.total_file_size == sum(sizes.values())
    assert len(store.calls) == 4


@pytest.mark.parametrize(
    "sizes",
    [
        {"part-1.safetensors": 100},
        {
            "part-1.safetensors": 100,
            "part-2.safetensors": 100,
            "extra.safetensors": 100,
        },
    ],
)
def test_rejects_missing_or_extra_asserted_shards(sizes: dict[str, int]) -> None:
    index, files, _valid_sizes = shard_fixture()

    with pytest.raises(SafeTensorsIdentityError, match="exactly match"):
        inspect_sharded_safetensors(index, sizes, RangeStore(files))


@pytest.mark.parametrize(
    "payload,message",
    [
        (
            index_bytes({"a": "../part.safetensors"}, 1),
            "safe relative path",
        ),
        (
            index_bytes({"a": "part.bin"}, 1),
            "non-SafeTensors shard",
        ),
        (
            index_bytes(
                {"a": "Part.safetensors", "b": "part.safetensors"},
                2,
            ),
            "case-colliding shard paths",
        ),
        (
            index_bytes({"a": "part.safetensors"}, 1, unknown=True),
            "unknown root fields",
        ),
        (
            b'{"metadata":{"total_size":NaN},"weight_map":{"a":"part.safetensors"}}',
            "strict JSON",
        ),
        (
            b'{"metadata":{"total_size":1},"weight_map":{"a":"one.safetensors","a":"two.safetensors"}}',
            "strict JSON",
        ),
    ],
)
def test_rejects_malformed_index(payload: bytes, message: str) -> None:
    with pytest.raises(SafeTensorsIdentityError, match=message):
        parse_safetensors_index(payload)


def test_rejects_index_tensor_owner_mismatch() -> None:
    index, files, _sizes = shard_fixture()
    parsed = parse_safetensors_index(
        index_bytes({"a": "part-2.safetensors", "b": "part-1.safetensors"}, 6)
    )
    store = RangeStore(files)
    identities = {
        name: inspect_safetensors_file(name, len(value), store)
        for name, value in files.items()
    }

    with pytest.raises(SafeTensorsIdentityError, match="ownership disagrees"):
        validate_sharded_safetensors_inventory(parsed, identities)


def test_rejects_index_total_size_mismatch() -> None:
    _index, files, _sizes = shard_fixture()
    parsed = parse_safetensors_index(
        index_bytes({"a": "part-1.safetensors", "b": "part-2.safetensors"}, 7)
    )
    store = RangeStore(files)
    identities = {
        name: inspect_safetensors_file(name, len(value), store)
        for name, value in files.items()
    }

    with pytest.raises(SafeTensorsIdentityError, match="total_size disagrees"):
        validate_sharded_safetensors_inventory(parsed, identities)


def test_rejects_duplicate_tensor_present_in_multiple_shards() -> None:
    index, files, _sizes = shard_fixture()
    duplicate = make_file(
        {"a": {"dtype": "F32", "shape": [1], "data_offsets": [0, 4]}},
        b"bbbb",
    )
    files["part-2.safetensors"] = duplicate
    store = RangeStore(files)
    identities = {
        name: inspect_safetensors_file(name, len(value), store)
        for name, value in files.items()
    }

    with pytest.raises(SafeTensorsIdentityError, match="more than one shard"):
        validate_sharded_safetensors_inventory(
            parse_safetensors_index(index), identities
        )


def test_index_parse_does_not_mutate_caller_data() -> None:
    payload = {"metadata": {"total_size": 1}, "weight_map": {"a": "one.safetensors"}}
    before = deepcopy(payload)

    parse_safetensors_index(json.dumps(payload).encode())

    assert payload == before
