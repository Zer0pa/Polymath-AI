"""Fail-closed Hugging Face metadata and bounded-byte transport.

This module deliberately contains no L0 policy.  It supplies a hardened Hub
boundary that can be injected into the L0 builder after independent review.
It never exposes redirect URLs and never permits an unbounded response read.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
import os
from types import MappingProxyType
import re
from typing import Any, Iterable, Iterator, Mapping, Protocol, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)


OFFICIAL_HUB_HOST = "huggingface.co"
OFFICIAL_HUB_ORIGIN = f"https://{OFFICIAL_HUB_HOST}"
HUB_TREE_MAX_PAGE_SIZE = 100
DEFAULT_REDIRECT_HOSTS = frozenset(
    {
        OFFICIAL_HUB_HOST,
        "cdn-lfs.huggingface.co",
        "cdn-lfs-us-1.huggingface.co",
        "cdn-lfs-eu-1.huggingface.co",
        "cas-bridge.xethub.hf.co",
        "cas-server.xethub.hf.co",
        "us.aws.cdn.hf.co",
        "eu.aws.cdn.hf.co",
    }
)
FULL_REVISION = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,95})/"
    r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,95})$"
)
CONTENT_RANGE = re.compile(r"^bytes ([0-9]+)-([0-9]+)/([0-9]+)$")
NEXT_LINK = re.compile(r'<([^>]*)>\s*;[^,]*\brel\s*=\s*"?next"?', re.IGNORECASE)


class HardenedHubError(RuntimeError):
    """Base class for sanitized, URL-free Hub failures."""


class UnsafeRedirectError(HardenedHubError):
    """A redirect crossed the explicit HTTPS host boundary."""


class HubTransportError(HardenedHubError):
    """A bounded request failed without exposing its URL."""


class HubResponseError(HardenedHubError):
    """A response violated its declared byte or identity contract."""


class HubInventoryError(HardenedHubError):
    """A repository tree was incomplete, ambiguous, or malformed."""


class ArtifactLike(Protocol):
    """Artifact fields consumed by :class:`HardenedHuggingFaceHubClient`."""

    repository: str
    revision: str


class ResponseOpener(Protocol):
    """Small injection surface used by deterministic transport tests."""

    def open(self, request: Request, timeout: int) -> Any:
        """Open one request and return a context-managed response."""


@dataclass(frozen=True)
class FileInventoryEntry:
    """Validated file facts from a complete immutable tree inventory."""

    path: str
    size: int
    record: Mapping[str, Any]


class TokenSafeRedirectHandler(HTTPRedirectHandler):
    """Allow only explicit HTTPS hosts and strip cross-origin credentials."""

    _CROSS_ORIGIN_HEADERS = frozenset(
        {"authorization", "proxy-authorization", "cookie", "cookie2", "host"}
    )

    def __init__(self, allowed_hosts: Iterable[str] = DEFAULT_REDIRECT_HOSTS) -> None:
        super().__init__()
        hosts = frozenset(_normalize_host(host) for host in allowed_hosts)
        if OFFICIAL_HUB_HOST not in hosts:
            raise ValueError("redirect allowlist must include the official Hub host")
        self._allowed_hosts = hosts

    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Mapping[str, str],
        newurl: str,
    ) -> Request | None:
        target_origin = _validated_origin(newurl, self._allowed_hosts)
        source_origin = _validated_origin(req.full_url, self._allowed_hosts)
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is None:
            return None

        cross_origin = source_origin != target_origin
        forwarded_headers = {
            name: value
            for name, value in redirected.header_items()
            if not (cross_origin and name.lower() in self._CROSS_ORIGIN_HEADERS)
        }
        return Request(
            redirected.full_url,
            method=redirected.get_method(),
            headers=forwarded_headers,
            origin_req_host=req.origin_req_host,
            unverifiable=True,
        )


class HardenedHuggingFaceHubClient:
    """Token-safe, paginated, bounded implementation of the L0 Hub surface."""

    def __init__(
        self,
        token: str | None = None,
        *,
        timeout_seconds: int = 60,
        redirect_hosts: Iterable[str] = DEFAULT_REDIRECT_HOSTS,
        max_identity_file_bytes: int = 64 * 1024 * 1024,
        max_range_bytes: int = 16 * 1024 * 1024,
        max_tree_page_bytes: int = 8 * 1024 * 1024,
        tree_page_size: int = 100,
        max_tree_pages: int = 1000,
        max_tree_entries: int = 100_000,
        opener: ResponseOpener | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        for name, value in (
            ("max_identity_file_bytes", max_identity_file_bytes),
            ("max_range_bytes", max_range_bytes),
            ("max_tree_page_bytes", max_tree_page_bytes),
            ("tree_page_size", tree_page_size),
            ("max_tree_pages", max_tree_pages),
            ("max_tree_entries", max_tree_entries),
        ):
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if tree_page_size > HUB_TREE_MAX_PAGE_SIZE:
            raise ValueError(
                f"tree_page_size exceeds the live Hub maximum of {HUB_TREE_MAX_PAGE_SIZE}"
            )

        self._token = token if token is not None else os.environ.get("HF_TOKEN")
        self._timeout_seconds = timeout_seconds
        self._allowed_hosts = frozenset(
            _normalize_host(host) for host in redirect_hosts
        )
        if OFFICIAL_HUB_HOST not in self._allowed_hosts:
            raise ValueError("redirect allowlist must include the official Hub host")
        self._max_identity_file_bytes = max_identity_file_bytes
        self._max_range_bytes = max_range_bytes
        self._max_tree_page_bytes = max_tree_page_bytes
        self._tree_page_size = tree_page_size
        self._max_tree_pages = max_tree_pages
        self._max_tree_entries = max_tree_entries
        self._opener = opener or build_opener(
            TokenSafeRedirectHandler(self._allowed_hosts)
        )
        self._tree_cache: dict[tuple[str, str], tuple[Mapping[str, Any], ...]] = {}
        self._file_cache: dict[tuple[str, str], Mapping[str, FileInventoryEntry]] = {}
        self._content_cache: dict[tuple[str, str, str], bytes] = {}

    def list_tree(self, artifact: ArtifactLike) -> Sequence[Mapping[str, Any]]:
        """Return a complete, duplicate-free immutable recursive tree."""

        repository, revision = _artifact_identity(artifact)
        key = (repository, revision)
        cached = self._tree_cache.get(key)
        if cached is not None:
            return cached

        first_url, expected_path = self._tree_url(repository, revision)
        url = first_url
        seen_page_urls: set[str] = set()
        seen_paths: set[str] = set()
        seen_casefolded_paths: set[str] = set()
        records: list[Mapping[str, Any]] = []
        file_records: dict[str, FileInventoryEntry] = {}

        for _page_number in range(1, self._max_tree_pages + 1):
            if url in seen_page_urls:
                raise HubInventoryError("tree pagination cycle detected")
            seen_page_urls.add(url)
            self._validate_tree_page_url(url, expected_path)
            request = Request(url, headers=self._headers())
            response = self._open(request, "tree inventory")
            with _managed_response(response, "tree inventory") as response:
                self._validate_response_endpoint(response, {OFFICIAL_HUB_HOST})
                self._require_status(response, 200, "tree inventory")
                self._require_identity_encoding(response)
                declared_length = _optional_content_length(response)
                payload = _read_bounded(
                    response,
                    self._max_tree_page_bytes,
                    declared_length=declared_length,
                )
                link_header = _header(response, "Link")

            page = _strict_json(
                payload, HubInventoryError, "tree page is not strict JSON"
            )
            if not isinstance(page, list):
                raise HubInventoryError("tree page root must be a list")
            if len(records) + len(page) > self._max_tree_entries:
                raise HubInventoryError("tree inventory exceeds the entry bound")

            for raw_record in page:
                record, path = _validate_tree_record(raw_record)
                casefolded_path = path.casefold()
                if path in seen_paths or casefolded_path in seen_casefolded_paths:
                    raise HubInventoryError("tree inventory contains a duplicate path")
                seen_paths.add(path)
                seen_casefolded_paths.add(casefolded_path)
                records.append(record)
                if record.get("type") == "file":
                    size = _nonnegative_int(record.get("size"), "file size")
                    file_records[path] = FileInventoryEntry(
                        path=path,
                        size=size,
                        record=record,
                    )

            next_url = _next_link(link_header)
            if next_url is None:
                if len(page) >= self._tree_page_size:
                    raise HubInventoryError(
                        "full final tree page has no completeness cursor"
                    )
                frozen_records = tuple(records)
                self._tree_cache[key] = frozen_records
                self._file_cache[key] = MappingProxyType(dict(file_records))
                return frozen_records
            url = next_url

        raise HubInventoryError("tree pagination exceeds the page bound")

    def read_file(self, artifact: ArtifactLike, path: str) -> bytes:
        """Read one inventoried identity file with an exact bounded body."""

        repository, revision = _artifact_identity(artifact)
        safe_path = _safe_relative_path(path)
        cache_key = (repository, revision, safe_path)
        cached = self._content_cache.get(cache_key)
        if cached is not None:
            return cached
        entry = self._file_entry(repository, revision, safe_path, artifact)
        if entry.size > self._max_identity_file_bytes:
            raise HubResponseError("identity file exceeds the configured byte bound")

        request = Request(
            self._resolve_url(repository, revision, safe_path),
            headers=self._headers(identity_encoding=True),
        )
        response = self._open(request, "identity file")
        with _managed_response(response, "identity file") as response:
            self._validate_response_endpoint(response, self._allowed_hosts)
            self._require_status(response, 200, "identity file")
            self._require_identity_encoding(response)
            declared_length = _required_content_length(response)
            if declared_length != entry.size:
                raise HubResponseError(
                    "identity file Content-Length disagrees with inventory"
                )
            payload = _read_exact(response, entry.size)
        self._content_cache[cache_key] = payload
        return payload

    def read_range(
        self,
        artifact: ArtifactLike,
        path: str,
        start: int,
        end: int,
    ) -> bytes:
        """Read an exact inclusive range without accepting a full-object reply."""

        repository, revision = _artifact_identity(artifact)
        safe_path = _safe_relative_path(path)
        entry = self._file_entry(repository, revision, safe_path, artifact)
        if not _is_int(start) or not _is_int(end) or start < 0 or end < start:
            raise ValueError("invalid byte range")
        if end >= entry.size:
            raise HubResponseError("byte range exceeds the inventoried file size")
        expected_length = end - start + 1
        if expected_length > self._max_range_bytes:
            raise HubResponseError("byte range exceeds the configured byte bound")

        headers = self._headers(identity_encoding=True)
        headers["Range"] = f"bytes={start}-{end}"
        request = Request(
            self._resolve_url(repository, revision, safe_path),
            headers=headers,
        )
        response = self._open(request, "bounded byte range")
        with _managed_response(response, "bounded byte range") as response:
            self._validate_response_endpoint(response, self._allowed_hosts)
            self._require_status(response, 206, "bounded byte range")
            self._require_identity_encoding(response)
            declared_length = _required_content_length(response)
            if declared_length != expected_length:
                raise HubResponseError("range Content-Length is not exact")
            observed_range = _header(response, "Content-Range")
            match = CONTENT_RANGE.fullmatch(observed_range or "")
            if match is None:
                raise HubResponseError("range response has no exact Content-Range")
            observed_start, observed_end, observed_total = (
                int(value) for value in match.groups()
            )
            if (observed_start, observed_end, observed_total) != (
                start,
                end,
                entry.size,
            ):
                raise HubResponseError("range Content-Range disagrees with inventory")
            return _read_exact(response, expected_length)

    def _file_entry(
        self,
        repository: str,
        revision: str,
        path: str,
        artifact: ArtifactLike,
    ) -> FileInventoryEntry:
        key = (repository, revision)
        if key not in self._file_cache:
            self.list_tree(artifact)
        entry = self._file_cache[key].get(path)
        if entry is None:
            raise HubInventoryError("requested path is absent from the immutable tree")
        return entry

    def _open(self, request: Request, operation: str) -> Any:
        _validated_origin(request.full_url, {OFFICIAL_HUB_HOST})
        try:
            return self._opener.open(request, timeout=self._timeout_seconds)
        except HardenedHubError:
            raise
        except HTTPError as error:
            raise HubTransportError(
                f"{operation} failed with HTTP status {error.code}"
            ) from None
        except (URLError, OSError, ValueError):
            raise HubTransportError(f"{operation} transport failed") from None
        except Exception:
            raise HubTransportError(f"{operation} transport failed") from None

    @staticmethod
    def _require_status(response: Any, expected: int, operation: str) -> None:
        observed = _response_status(response)
        if observed != expected:
            raise HubResponseError(
                f"{operation} requires HTTP {expected}, observed {observed}"
            )

    @staticmethod
    def _require_identity_encoding(response: Any) -> None:
        encoding = _header(response, "Content-Encoding")
        if encoding is not None and encoding.strip().lower() != "identity":
            raise HubResponseError("compressed transfer encoding is forbidden")

    @staticmethod
    def _validate_response_endpoint(
        response: Any, allowed_hosts: Iterable[str]
    ) -> None:
        geturl = getattr(response, "geturl", None)
        if not callable(geturl):
            raise HubResponseError("response does not expose its final endpoint")
        try:
            final_url = geturl()
        except Exception:
            raise HubResponseError("response final endpoint is unavailable") from None
        _validated_origin(final_url, allowed_hosts)

    def _headers(self, *, identity_encoding: bool = False) -> dict[str, str]:
        headers = {"User-Agent": "polymath-ai-gemma4-e4b-l0-hardened/1"}
        if identity_encoding:
            headers["Accept-Encoding"] = "identity"
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _tree_url(self, repository: str, revision: str) -> tuple[str, str]:
        repo = quote(repository, safe="/")
        rev = quote(revision, safe="")
        path = f"/api/models/{repo}/tree/{rev}"
        query = urlencode(
            {
                "recursive": "true",
                "expand": "true",
                "limit": str(self._tree_page_size),
            }
        )
        return f"{OFFICIAL_HUB_ORIGIN}{path}?{query}", path

    @staticmethod
    def _resolve_url(repository: str, revision: str, path: str) -> str:
        repo = quote(repository, safe="/")
        rev = quote(revision, safe="")
        encoded_path = quote(path, safe="/")
        return f"{OFFICIAL_HUB_ORIGIN}/{repo}/resolve/{rev}/{encoded_path}"

    @staticmethod
    def _validate_tree_page_url(url: str, expected_path: str) -> None:
        _validated_origin(url, {OFFICIAL_HUB_HOST})
        parsed = urlparse(url)
        if parsed.path != expected_path or parsed.fragment:
            raise HubInventoryError("tree pagination escaped the immutable endpoint")


def _artifact_identity(artifact: ArtifactLike) -> tuple[str, str]:
    repository = getattr(artifact, "repository", None)
    revision = getattr(artifact, "revision", None)
    if not isinstance(repository, str) or REPOSITORY.fullmatch(repository) is None:
        raise HubInventoryError("repository identity is malformed")
    if not isinstance(revision, str) or FULL_REVISION.fullmatch(revision) is None:
        raise HubInventoryError("revision must be a full lowercase commit SHA")
    return repository, revision


def _normalize_host(host: str) -> str:
    if not isinstance(host, str):
        raise ValueError("redirect host must be text")
    normalized = host.strip().lower()
    if (
        not normalized
        or normalized.endswith(".")
        or ":" in normalized
        or "/" in normalized
    ):
        raise ValueError("redirect host must be an exact hostname")
    return normalized


def _validated_origin(url: str, allowed_hosts: Iterable[str]) -> tuple[str, str, int]:
    if not isinstance(url, str):
        raise UnsafeRedirectError("endpoint URL is malformed")
    try:
        parsed = urlparse(url)
        port = parsed.port
    except (TypeError, ValueError):
        raise UnsafeRedirectError("endpoint URL is malformed") from None
    host = (parsed.hostname or "").lower()
    allowed = frozenset(_normalize_host(value) for value in allowed_hosts)
    if (
        parsed.scheme != "https"
        or not host
        or host not in allowed
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
    ):
        raise UnsafeRedirectError(
            "endpoint is outside the explicit HTTPS host allowlist"
        )
    return "https", host, 443


def _safe_relative_path(path: str) -> str:
    if not isinstance(path, str) or not path or path.startswith("/") or "\\" in path:
        raise HubInventoryError("repository path is malformed")
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts) or "\x00" in path:
        raise HubInventoryError("repository path is not a safe relative path")
    return path


def _validate_tree_record(raw_record: Any) -> tuple[Mapping[str, Any], str]:
    if not isinstance(raw_record, dict):
        raise HubInventoryError("tree entry must be an object")
    path = _safe_relative_path(raw_record.get("path"))
    entry_type = raw_record.get("type")
    if entry_type not in {"file", "directory"}:
        raise HubInventoryError("tree entry has an unsupported type")
    if entry_type == "file":
        _nonnegative_int(raw_record.get("size"), "file size")
    return _freeze_json(raw_record), path


def _freeze_json(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType(
            {key: _freeze_json(child) for key, child in value.items()}
        )
    if isinstance(value, list):
        return tuple(_freeze_json(child) for child in value)
    return value


def _strict_json(
    payload: bytes, error_type: type[HardenedHubError], message: str
) -> Any:
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
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
        raise error_type(message) from None


def _next_link(header: str | None) -> str | None:
    if not header:
        return None
    matches = NEXT_LINK.findall(header)
    if len(matches) > 1:
        raise HubInventoryError("tree page has multiple next cursors")
    return matches[0] if matches else None


def _header(response: Any, name: str) -> str | None:
    headers = getattr(response, "headers", None)
    if headers is None:
        raise HubResponseError("response headers are unavailable")
    get_all = getattr(headers, "get_all", None)
    if callable(get_all):
        observed = get_all(name)
        values = [] if observed is None else [str(value) for value in observed]
    else:
        values = []
    items = getattr(headers, "items", None)
    if not values and callable(items):
        for key, value in items():
            if str(key).lower() == name.lower():
                values.append(str(value))
    if not values:
        return None
    if name.lower() == "link":
        return ",".join(values)
    if len(values) != 1:
        raise HubResponseError(f"response has duplicate {name} headers")
    return values[0]


@contextmanager
def _managed_response(response: Any, operation: str) -> Iterator[Any]:
    try:
        with response as managed:
            yield managed
    except HardenedHubError:
        raise
    except Exception:
        raise HubTransportError(f"{operation} response failed") from None


def _response_status(response: Any) -> int:
    status = getattr(response, "status", None)
    if status is None:
        getcode = getattr(response, "getcode", None)
        status = getcode() if callable(getcode) else None
    if not _is_int(status):
        raise HubResponseError("response status is unavailable")
    return int(status)


def _required_content_length(response: Any) -> int:
    if _header(response, "Transfer-Encoding") is not None:
        raise HubResponseError("bounded response must not use Transfer-Encoding")
    value = _header(response, "Content-Length")
    if value is None:
        raise HubResponseError("response has no Content-Length")
    return _parse_decimal_header(value, "Content-Length")


def _optional_content_length(response: Any) -> int | None:
    value = _header(response, "Content-Length")
    return None if value is None else _parse_decimal_header(value, "Content-Length")


def _parse_decimal_header(value: str, label: str) -> int:
    normalized = value.strip()
    if not normalized.isascii() or not normalized.isdigit():
        raise HubResponseError(f"{label} is not a nonnegative decimal")
    return int(normalized)


def _read_exact(response: Any, expected_bytes: int) -> bytes:
    payload = _read_bounded(response, expected_bytes)
    if len(payload) != expected_bytes:
        raise HubResponseError("response body length is not exact")
    return payload


def _read_bounded(
    response: Any,
    max_bytes: int,
    *,
    declared_length: int | None = None,
) -> bytes:
    if max_bytes < 0:
        raise ValueError("max_bytes must be nonnegative")
    if declared_length is not None and declared_length > max_bytes:
        raise HubResponseError("response Content-Length exceeds the byte bound")
    limit = max_bytes + 1
    payload = bytearray()
    while len(payload) < limit:
        request_bytes = min(64 * 1024, limit - len(payload))
        chunk = response.read(request_bytes)
        if not chunk:
            break
        if not isinstance(chunk, bytes) or len(chunk) > request_bytes:
            raise HubResponseError("response violated bounded streaming semantics")
        payload.extend(chunk)
    if len(payload) > max_bytes:
        raise HubResponseError("response body exceeds the byte bound")
    if declared_length is not None and len(payload) != declared_length:
        raise HubResponseError("response body disagrees with Content-Length")
    return bytes(payload)


def _nonnegative_int(value: Any, label: str) -> int:
    if not _is_int(value) or value < 0:
        raise HubInventoryError(f"{label} must be a nonnegative integer")
    return int(value)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


__all__ = [
    "DEFAULT_REDIRECT_HOSTS",
    "FileInventoryEntry",
    "HUB_TREE_MAX_PAGE_SIZE",
    "HardenedHubError",
    "HardenedHuggingFaceHubClient",
    "HubInventoryError",
    "HubResponseError",
    "HubTransportError",
    "TokenSafeRedirectHandler",
    "UnsafeRedirectError",
]
