from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib.error import URLError
from urllib.request import Request

import pytest

from polymath_ai.frontier.hardened_hf import (
    HardenedHuggingFaceHubClient,
    HubInventoryError,
    HubResponseError,
    HubTransportError,
    TokenSafeRedirectHandler,
    UnsafeRedirectError,
)


REVISION = "a" * 40
REPOSITORY = "google/gemma-4-E4B-it"
TREE_PATH = f"/api/models/{REPOSITORY}/tree/{REVISION}"
TREE_URL = f"https://huggingface.co{TREE_PATH}"


@dataclass(frozen=True)
class Artifact:
    repository: str = REPOSITORY
    revision: str = REVISION


class FakeResponse:
    def __init__(
        self,
        body: bytes,
        *,
        status: int = 200,
        headers: dict[str, str] | None = None,
        final_url: str = "https://huggingface.co/safe",
    ) -> None:
        self._body = body
        self._offset = 0
        self.status = status
        self.headers = headers or {}
        self._final_url = final_url
        self.read_calls = 0
        self.bytes_read = 0
        self.closed = False

    def read(self, size: int = -1) -> bytes:
        self.read_calls += 1
        if size < 0:
            raise AssertionError("transport must never issue an unbounded read")
        end = min(len(self._body), self._offset + size)
        result = self._body[self._offset : end]
        self._offset = end
        self.bytes_read += len(result)
        return result

    def geturl(self) -> str:
        return self._final_url

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_args: Any) -> None:
        self.closed = True


class FakeOpener:
    def __init__(self, *responses: FakeResponse | Exception) -> None:
        self.responses = list(responses)
        self.requests: list[Request] = []

    def open(self, request: Request, timeout: int) -> FakeResponse:
        assert timeout > 0
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("unexpected request")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FailingReadResponse(FakeResponse):
    def __init__(self, secret: str) -> None:
        super().__init__(b"", headers={"Content-Length": "1"})
        self._secret = secret

    def read(self, size: int = -1) -> bytes:
        raise URLError(f"https://signed.invalid/?{self._secret}")


class MultiHeaders:
    def __init__(self, values: dict[str, list[str]]) -> None:
        self._values = values

    def get_all(self, name: str) -> list[str] | None:
        for key, values in self._values.items():
            if key.lower() == name.lower():
                return values
        return None

    def items(self):
        for key, values in self._values.items():
            for value in values:
                yield key, value


def tree_record(path: str, size: int = 8) -> dict[str, Any]:
    return {"type": "file", "path": path, "size": size, "oid": "git-oid"}


def page_response(
    records: list[dict[str, Any]],
    *,
    link: str | None = None,
) -> FakeResponse:
    body = json.dumps(records, separators=(",", ":")).encode()
    headers = {"Content-Length": str(len(body))}
    if link is not None:
        headers["Link"] = link
    return FakeResponse(body, headers=headers)


def client(opener: FakeOpener, **kwargs: Any) -> HardenedHuggingFaceHubClient:
    return HardenedHuggingFaceHubClient(
        token="sentinel-token",
        opener=opener,
        **kwargs,
    )


def test_rejects_tree_page_size_above_live_hub_limit() -> None:
    with pytest.raises(ValueError, match="live Hub maximum of 100"):
        client(FakeOpener(), tree_page_size=101)


def test_follows_tree_pagination_and_rejects_no_entries() -> None:
    next_url = f"{TREE_URL}?cursor=opaque&recursive=true&expand=true&limit=2"
    opener = FakeOpener(
        page_response([tree_record("config.json")], link=f'<{next_url}>; rel="next"'),
        page_response([tree_record("model.safetensors", 100)]),
    )

    tree = client(opener, tree_page_size=2).list_tree(Artifact())

    assert [entry["path"] for entry in tree] == ["config.json", "model.safetensors"]
    assert len(opener.requests) == 2
    assert all(request.host == "huggingface.co" for request in opener.requests)


def test_rejects_duplicate_path_across_pages() -> None:
    next_url = f"{TREE_URL}?cursor=opaque"
    opener = FakeOpener(
        page_response([tree_record("config.json")], link=f'<{next_url}>; rel="next"'),
        page_response([tree_record("config.json")]),
    )

    with pytest.raises(HubInventoryError, match="duplicate path"):
        client(opener).list_tree(Artifact())


def test_rejects_case_colliding_path_across_pages() -> None:
    next_url = f"{TREE_URL}?cursor=opaque"
    opener = FakeOpener(
        page_response([tree_record("Config.json")], link=f'<{next_url}>; rel="next"'),
        page_response([tree_record("config.json")]),
    )

    with pytest.raises(HubInventoryError, match="duplicate path"):
        client(opener).list_tree(Artifact())


def test_returned_tree_is_deeply_immutable() -> None:
    record = tree_record("model.safetensors")
    record["lfs"] = {"oid": "a" * 64, "size": 8}
    tree = client(FakeOpener(page_response([record]))).list_tree(Artifact())

    with pytest.raises(TypeError):
        tree[0]["lfs"]["oid"] = "b" * 64


def test_identity_file_content_is_read_once_per_immutable_path() -> None:
    payload = b"{}"
    opener = FakeOpener(
        page_response([tree_record("config.json", len(payload))]),
        FakeResponse(
            payload,
            headers={"Content-Length": str(len(payload))},
            final_url=f"https://huggingface.co/{REPOSITORY}/resolve/{REVISION}/config.json",
        ),
    )
    hub = client(opener)

    assert hub.read_file(Artifact(), "config.json") == payload
    assert hub.read_file(Artifact(), "config.json") == payload
    assert len(opener.requests) == 2


def test_rejects_full_final_page_without_completeness_cursor() -> None:
    opener = FakeOpener(page_response([tree_record("config.json")]))

    with pytest.raises(HubInventoryError, match="no completeness cursor"):
        client(opener, tree_page_size=1).list_tree(Artifact())


def test_rejects_pagination_cycle() -> None:
    repeated = f"{TREE_URL}?recursive=true&expand=true&limit=1"
    first = page_response([tree_record("one")], link=f'<{repeated}>; rel="next"')
    second = page_response([tree_record("two")], link=f'<{repeated}>; rel="next"')
    opener = FakeOpener(first, second)

    with pytest.raises(HubInventoryError, match="cycle"):
        client(opener, tree_page_size=1).list_tree(Artifact())


def test_rejects_pagination_that_leaves_official_endpoint_without_exposing_query() -> (
    None
):
    secret = "SIGNED-QUERY-MUST-NOT-APPEAR"
    evil = f"https://evil.example/tree?X-Amz-Signature={secret}"
    opener = FakeOpener(
        page_response([tree_record("config.json")], link=f'<{evil}>; rel="next"')
    )

    with pytest.raises(UnsafeRedirectError) as failure:
        client(opener).list_tree(Artifact())

    assert secret not in str(failure.value)
    assert "?" not in str(failure.value)


@pytest.mark.parametrize(
    "body",
    [
        b'[{"type":"file","path":"a","size":NaN}]',
        b'[{"type":"file","path":"a","path":"b","size":1}]',
    ],
)
def test_rejects_nonfinite_or_duplicate_key_tree_json(body: bytes) -> None:
    opener = FakeOpener(FakeResponse(body, headers={"Content-Length": str(len(body))}))

    with pytest.raises(HubInventoryError, match="strict JSON"):
        client(opener).list_tree(Artifact())


def test_exact_range_requires_206_content_range_length_and_total() -> None:
    tree = page_response([tree_record("model.safetensors", 100)])
    ranged = FakeResponse(
        b"abcdefgh",
        status=206,
        headers={"Content-Length": "8", "Content-Range": "bytes 0-7/100"},
        final_url="https://us.aws.cdn.hf.co/object?X-Amz-Signature=redacted",
    )
    opener = FakeOpener(tree, ranged)
    hub = client(opener)

    result = hub.read_range(Artifact(), "model.safetensors", 0, 7)

    assert result == b"abcdefgh"
    assert ranged.bytes_read == 8
    request = opener.requests[-1]
    assert request.get_header("Range") == "bytes=0-7"
    assert request.get_header("Accept-encoding") == "identity"


def test_rejects_full_object_response_before_reading_body() -> None:
    tree = page_response([tree_record("model.safetensors", 10_000_000)])
    full = FakeResponse(
        b"x" * 1024,
        status=200,
        headers={"Content-Length": "10000000"},
        final_url="https://us.aws.cdn.hf.co/object",
    )
    hub = client(FakeOpener(tree, full))

    with pytest.raises(HubResponseError, match="requires HTTP 206"):
        hub.read_range(Artifact(), "model.safetensors", 0, 7)

    assert full.read_calls == 0


def test_rejects_oversized_requested_range_before_opening_object() -> None:
    tree = page_response([tree_record("model.safetensors", 100)])
    opener = FakeOpener(tree)
    hub = client(opener, max_range_bytes=8)

    with pytest.raises(HubResponseError, match="configured byte bound"):
        hub.read_range(Artifact(), "model.safetensors", 0, 8)

    assert len(opener.requests) == 1


@pytest.mark.parametrize(
    "headers",
    [
        {"Content-Length": "8", "Content-Range": "bytes 1-8/100"},
        {"Content-Length": "8", "Content-Range": "bytes 0-7/101"},
        {"Content-Length": "7", "Content-Range": "bytes 0-7/100"},
        {"Content-Length": "8"},
        {
            "Content-Length": "8",
            "Content-Range": "bytes 0-7/100",
            "Content-Encoding": "gzip",
        },
        {
            "Content-Length": "8",
            "Content-Range": "bytes 0-7/100",
            "Transfer-Encoding": "chunked",
        },
    ],
)
def test_rejects_inexact_range_metadata(headers: dict[str, str]) -> None:
    tree = page_response([tree_record("model.safetensors", 100)])
    ranged = FakeResponse(
        b"abcdefgh",
        status=206,
        headers=headers,
        final_url="https://us.aws.cdn.hf.co/object",
    )
    hub = client(FakeOpener(tree, ranged))

    with pytest.raises(HubResponseError):
        hub.read_range(Artifact(), "model.safetensors", 0, 7)


def test_rejects_duplicate_content_length_headers() -> None:
    tree = page_response([tree_record("model.safetensors", 100)])
    ranged = FakeResponse(
        b"abcdefgh",
        status=206,
        headers={},
        final_url="https://us.aws.cdn.hf.co/object",
    )
    ranged.headers = MultiHeaders(
        {
            "Content-Length": ["8", "8"],
            "Content-Range": ["bytes 0-7/100"],
        }
    )
    hub = client(FakeOpener(tree, ranged))

    with pytest.raises(HubResponseError, match="duplicate Content-Length"):
        hub.read_range(Artifact(), "model.safetensors", 0, 7)


def test_exact_file_read_probes_only_one_byte_beyond_declared_bound() -> None:
    tree = page_response([tree_record("config.json", 8)])
    body = FakeResponse(
        b"123456789" + b"unreachable",
        headers={"Content-Length": "8"},
        final_url="https://huggingface.co/resolved",
    )
    hub = client(FakeOpener(tree, body))

    with pytest.raises(HubResponseError, match="exceeds the byte bound"):
        hub.read_file(Artifact(), "config.json")

    assert body.bytes_read == 9


def test_identity_file_bound_is_checked_before_opening_object() -> None:
    tree = page_response([tree_record("tokenizer.json", 65)])
    opener = FakeOpener(tree)
    hub = client(opener, max_identity_file_bytes=64)

    with pytest.raises(HubResponseError, match="exceeds"):
        hub.read_file(Artifact(), "tokenizer.json")

    assert len(opener.requests) == 1


def test_cross_origin_redirect_strips_credentials_and_preserves_range() -> None:
    handler = TokenSafeRedirectHandler()
    original = Request(
        "https://huggingface.co/google/model/resolve/"
        + REVISION
        + "/model.safetensors",
        headers={
            "Authorization": "Bearer sentinel",
            "Cookie": "session=sentinel",
            "Range": "bytes=0-7",
            "Accept-Encoding": "identity",
        },
    )

    redirected = handler.redirect_request(
        original,
        None,
        302,
        "Found",
        {},
        "https://us.aws.cdn.hf.co/object?X-Amz-Signature=secret",
    )

    assert redirected is not None
    assert redirected.get_header("Authorization") is None
    assert redirected.get_header("Cookie") is None
    assert redirected.get_header("Range") == "bytes=0-7"
    assert redirected.get_header("Accept-encoding") == "identity"


def test_same_origin_redirect_can_retain_authorization() -> None:
    handler = TokenSafeRedirectHandler()
    original = Request(
        "https://huggingface.co/start",
        headers={"Authorization": "Bearer sentinel"},
    )

    redirected = handler.redirect_request(
        original,
        None,
        302,
        "Found",
        {},
        "https://huggingface.co/finish",
    )

    assert redirected is not None
    assert redirected.get_header("Authorization") == "Bearer sentinel"


@pytest.mark.parametrize(
    "target",
    [
        "http://us.aws.cdn.hf.co/object",
        "https://evil.example/object",
        "https://huggingface.co:444/object",
        "https://huggingface.co./object",
        "https://user:password@huggingface.co/object",
    ],
)
def test_redirect_allowlist_is_exact_and_error_never_exposes_signed_query(
    target: str,
) -> None:
    handler = TokenSafeRedirectHandler()
    original = Request("https://huggingface.co/start")
    target = target + "?X-Amz-Signature=must-not-appear"

    with pytest.raises(UnsafeRedirectError) as failure:
        handler.redirect_request(original, None, 302, "Found", {}, target)

    assert "must-not-appear" not in str(failure.value)
    assert target not in str(failure.value)


def test_transport_error_is_sanitized() -> None:
    secret = "X-Amz-Signature=must-not-appear"
    opener = FakeOpener(URLError(f"https://signed.invalid/?{secret}"))

    with pytest.raises(HubTransportError) as failure:
        client(opener).list_tree(Artifact())

    assert secret not in str(failure.value)
    assert failure.value.__cause__ is None


def test_response_read_error_is_sanitized() -> None:
    secret = "X-Amz-Signature=must-not-appear"
    opener = FakeOpener(FailingReadResponse(secret))

    with pytest.raises(HubTransportError) as failure:
        client(opener).list_tree(Artifact())

    assert secret not in str(failure.value)
    assert failure.value.__cause__ is None


@pytest.mark.parametrize(
    "artifact,path",
    [
        (Artifact(repository="google/../evil"), "config.json"),
        (Artifact(revision="main"), "config.json"),
        (Artifact(), "../config.json"),
        (Artifact(), "/config.json"),
    ],
)
def test_rejects_mutable_or_unsafe_identity_before_object_read(
    artifact: Artifact,
    path: str,
) -> None:
    hub = client(FakeOpener())

    with pytest.raises(HubInventoryError):
        hub.read_file(artifact, path)
