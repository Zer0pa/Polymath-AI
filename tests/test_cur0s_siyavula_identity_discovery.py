"""Adversarial local tests for phone-only Siyavula identity discovery.

All payloads and HTTP outcomes are synthetic.  This suite must never contact
the phone, Siyavula, or any other network service.
"""

from __future__ import annotations

from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import stat
import sys
import threading
from types import SimpleNamespace
from typing import Any
import zipfile

import pytest


ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATH = ROOT / "scripts/termux/discover_cur0s_siyavula_identities.py"


@pytest.fixture
def harness():
    name = "cur0s_siyavula_identity_discovery_test"
    spec = importlib.util.spec_from_file_location(name, HARNESS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _runtime(harness) -> dict[str, Any]:
    def regular(
        path: str,
        size: int,
        digest: str,
        *,
        mode: str = "0755",
        uid: int | None = None,
        gid: int | None = None,
        inode: int = 1,
    ) -> dict[str, Any]:
        owner = harness.EXPECTED_TERMUX_UID_GID if uid is None else uid
        group = harness.EXPECTED_TERMUX_UID_GID if gid is None else gid
        return {
            "bytes": size,
            "ctime_ns": 1,
            "device": 1,
            "gid": group,
            "inode": inode,
            "mode": mode,
            "mtime_ns": 1,
            "nlink": 1,
            "path": path,
            "sha256": "sha256:" + digest,
            "uid": owner,
        }

    linker = regular(
        harness.EXPECTED_LINKER64_RESOLVED_PATH,
        harness.LINKER64_EXPECTED_BYTES,
        harness.LINKER64_EXPECTED_SHA256,
        uid=0,
        gid=2000,
        inode=2,
    )
    curl = regular(
        str(harness.DEFAULT_CURL),
        harness.CURL_EXPECTED_BYTES,
        harness.CURL_EXPECTED_SHA256,
        mode="0700",
        inode=3,
    )
    python = regular(
        harness.EXPECTED_PYTHON_RESOLVED_PATH,
        harness.PYTHON_EXPECTED_BYTES,
        harness.PYTHON_EXPECTED_SHA256,
        mode="0700",
        inode=4,
    )

    def closure(role: str, target: dict[str, Any], expected) -> dict[str, Any]:
        entries = []
        for index, (soname, path, size, digest) in enumerate(expected, start=10):
            identity = None
            if path != "[vdso]":
                is_termux = path.startswith(harness.EXPECTED_PYTHON_PREFIX + "/")
                identity = regular(
                    path,
                    size,
                    digest,
                    uid=harness.EXPECTED_TERMUX_UID_GID if is_termux else 0,
                    gid=harness.EXPECTED_TERMUX_UID_GID if is_termux else 2000,
                    inode=index,
                )
            entries.append(
                {
                    "identity": identity,
                    "normalized_line": f"\t{soname} => {path}",
                    "resolved_path": path,
                    "soname": soname,
                }
            )
        body = {
            "address_normalization": (
                "remove_only_exact_terminal_lowercase_hex_ASLR_address_suffix"
            ),
            "argv_shape": [
                "/system/bin/linker64",
                "--list",
                "/proc/self/fd/$TARGET_FD",
            ],
            "entries": entries,
            "entry_count": len(entries),
            "linker64": linker,
            "role": role,
            "scope": (
                "static_PT_INTERP_and_DT_NEEDED_resolution_only_no_dlopen_claim"
            ),
            "target": target,
        }
        return {**body, "closure_root_sha256": harness.canonical_sha256(body)}

    modules = [
        {
            "cached": None,
            "loader_type": "FrozenImporter",
            "module": "fixture_runtime",
            "origin": "frozen",
            "origin_bytes": None,
            "origin_sha256": None,
        }
    ]
    module_root = harness.canonical_sha256(modules)
    startup = {
        "absent_pycache_prefix": str(harness.ABSENT_PYCACHE_PREFIX),
        "absent_pycache_prefix_exists": False,
        "argv0": harness.HARNESS_EXECUTION_PATH,
        "dont_write_bytecode": 1,
        "ignore_environment": 1,
        "initial_sys_path": list(harness.EXPECTED_INITIAL_SYS_PATH),
        "isolated": 1,
        "launch_mode": (
            "held_fd3_python_-IBS_-X_exact_verified_absent_pycache_prefix"
        ),
        "loaded_module_origins": modules,
        "loaded_module_origins_sha256": module_root,
        "no_site": 1,
        "no_user_site": 1,
        "orig_argv_launch_prefix": harness.EXPECTED_ORIG_ARGV_LAUNCH_PREFIX,
        "pycache_prefix": str(harness.ABSENT_PYCACHE_PREFIX),
        "python313_zip_absent": True,
        "safe_path": True,
        "sanitized_sys_path": list(harness.EXPECTED_INITIAL_SYS_PATH[1:]),
        "source_only_stdlib_observed_root_sha256": module_root,
        "timestamp_or_sourceless_pyc_consumed": False,
        "xoptions": {"pycache_prefix": str(harness.ABSENT_PYCACHE_PREFIX)},
    }
    toolbox = regular(
        "/system/bin/toolbox",
        harness.TOOLBOX_EXPECTED_BYTES,
        harness.TOOLBOX_EXPECTED_SHA256,
        uid=0,
        gid=2000,
        inode=5,
    )
    phone_core = {
        "ADB_serial_claimed_by_phone_process": False,
        "external_ADB_serial_is_launcher_evidence_only": True,
        "getprop": {
            "execution_shape": (
                "canonical_root_owned_system_getprop_symlink_to_toolbox_"
                "held_toolbox_and_linker_pre_post"
            ),
            "linker64": linker,
            "linker64_invocation_path": "/system/bin/linker64",
            "symlink": {
                "gid": 2000,
                "mode": "0755",
                "path": "/system/bin/getprop",
                "target": "toolbox",
                "uid": 0,
            },
            "toolbox": toolbox,
        },
        "process": {
            "environment": harness.EXPECTED_PYTHON_ENVIRONMENT,
            "gid": harness.EXPECTED_TERMUX_UID_GID,
            "HOME": str(harness.PHONE_HOME),
            "kernel_release": harness.EXPECTED_KERNEL_RELEASE,
            "machine": harness.EXPECTED_PHONE_MACHINE,
            "platform_release": "15",
            "PREFIX": harness.EXPECTED_PYTHON_PREFIX,
            "python_version": harness.EXPECTED_PYTHON_VERSION,
            "uid": harness.EXPECTED_TERMUX_UID_GID,
        },
        "properties": {
            "ABI": harness.EXPECTED_PHONE_ABI,
            "android_release": harness.EXPECTED_ANDROID_RELEASE,
            "android_SDK": harness.EXPECTED_ANDROID_SDK,
            "board_platform": harness.EXPECTED_PHONE_BOARD_PLATFORM,
            "boot_verified_state": "green",
            "device": harness.EXPECTED_PHONE_DEVICE,
            "fingerprint": harness.EXPECTED_BUILD_FINGERPRINT,
            "flash_locked": "1",
            "model": harness.EXPECTED_PHONE_MODEL,
            "phone_process_boot_serial": "",
            "phone_process_serial": "",
            "product_name": harness.EXPECTED_PHONE_PRODUCT_NAME,
            "SoC_manufacturer": harness.EXPECTED_PHONE_SOC_MANUFACTURER,
            "SoC_model": harness.EXPECTED_PHONE_SOC,
            "thermal_battery_control": "true",
            "thermal_policy_thresholds": "skin,54,battery,45",
            "thermal_service_state": "running",
            "vendor_device": harness.EXPECTED_PHONE_VENDOR_DEVICE,
        },
        "schema_version": "cur0s_siyavula_sovereign_phone_identity_v2",
    }
    phone = {
        **phone_core,
        "observation_root_sha256": harness.canonical_sha256(phone_core),
    }
    curl_closure = closure("curl", curl, harness.CURL_LOADER_EXPECTED)
    python_closure = closure("python", python, harness.PYTHON_LOADER_EXPECTED)
    CA = regular(
        str(harness.CA_BUNDLE_PATH),
        harness.CA_BUNDLE_EXPECTED_BYTES,
        harness.CA_BUNDLE_EXPECTED_SHA256,
        mode="0600",
        inode=6,
    )
    harness_identity = regular(
        "/phone/sealed/discover_cur0s_siyavula_identities.py",
        100_000,
        "3" * 64,
        mode="0400",
        inode=7,
    )
    harness_identity.update(
        {
            "execution_fd": harness.HARNESS_EXECUTION_FD,
            "execution_path": harness.HARNESS_EXECUTION_PATH,
        }
    )
    core = {
        "build_fingerprint_sha256": harness.EXPECTED_BUILD_FINGERPRINT_SHA256,
        "curl": curl,
        "curl_CA_bundle": CA,
        "curl_loader_closure": curl_closure,
        "harness": harness_identity,
        "launch_contract": harness.HARNESS_LAUNCH_CONTRACT,
        "linker64": linker,
        "machine": harness.EXPECTED_PHONE_MACHINE,
        "phone_identity": phone,
        "python": python,
        "python_loader_closure": python_closure,
        "python_startup": startup,
        "python_version": harness.EXPECTED_PYTHON_VERSION,
        "schema_version": "cur0s_siyavula_discovery_runtime_identity_v2",
        "sys_executable": f"{harness.EXPECTED_PYTHON_PREFIX}/bin/python",
    }
    return {**core, "observation_root_sha256": harness.canonical_sha256(core)}


class SyntheticLease:
    def __init__(self, harness, epoch: Path) -> None:
        self.harness = harness
        self.epoch = epoch
        self.sequence = 0

    def observe(self, *, phase: str) -> tuple[str, str]:
        self.sequence += 1
        value = {
            "elapsed_seconds_floor": 0,
            "free_bytes": 100 * 1024**3,
            "lease_seconds": 3600,
            "minimum_free_bytes": self.harness.MIN_FREE_BYTES
            + self.harness.CHUNK_BYTES,
            "observed_at_utc": "2026-07-12T12:00:00Z",
            "phase": phase,
            "remaining_seconds_floor": 3600,
            "schema_version": self.harness.RESOURCE_OBSERVATION_SCHEMA,
            "thermal": {
                "battery": {
                    "raw_value": 210,
                    "temperature_millidegrees_c": 21_000,
                },
                "compute_zones": [
                    {"temperature_millidegrees_c": 34_000, "type": "cpu"}
                ],
                "policy": self.harness.THERMAL_POLICY,
                "PMIC_maximum_not_used_as_gate": True,
            },
        }
        directory = self.epoch / "synthetic_resources"
        self.harness.ensure_private_directory(directory)
        path = directory / f"{self.sequence:08d}.json"
        digest = self.harness.publish_immutable_json(path, value)
        return self.harness.relative_inside(self.epoch, path), digest

    def checkpoint(self, *, phase: str) -> dict[str, Any]:
        return {"phase": phase}


def test_phone_runtime_requires_termux_android_sys_platform(
    harness, monkeypatch, tmp_path
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    curl = tmp_path / "curl"
    curl.write_bytes(b"curl")
    original_is_file = harness.Path.is_file
    monkeypatch.setattr(harness, "PHONE_HOME", home)
    monkeypatch.setattr(harness, "DEFAULT_CURL", curl)
    monkeypatch.setattr(
        harness.os,
        "uname",
        lambda: SimpleNamespace(machine=harness.EXPECTED_PHONE_MACHINE),
    )
    monkeypatch.setattr(
        harness.Path,
        "is_file",
        lambda self: True
        if str(self) == "/system/bin/getprop"
        else original_is_file(self),
    )
    monkeypatch.setattr(harness.sys, "platform", "android")

    harness.require_phone_runtime(curl)

    monkeypatch.setattr(harness.sys, "platform", "linux")
    with pytest.raises(harness.DiscoveryError, match="phone_only_runtime_required"):
        harness.require_phone_runtime(curl)


def test_runtime_identity_allows_hash_bound_empty_stdlib_source(harness) -> None:
    runtime = _runtime(harness)
    modules = [
        {
            "cached": f"{harness.ABSENT_PYCACHE_PREFIX}/empty.cpython-313.pyc",
            "loader_type": "SourceFileLoader",
            "module": "empty_fixture",
            "origin": f"{harness.EXPECTED_PYTHON_PREFIX}/lib/python3.13/empty.py",
            "origin_bytes": 0,
            "origin_sha256": "sha256:" + hashlib.sha256(b"").hexdigest(),
        }
    ]
    module_root = harness.canonical_sha256(modules)
    runtime["python_startup"]["loaded_module_origins"] = modules
    runtime["python_startup"]["loaded_module_origins_sha256"] = module_root
    runtime["python_startup"]["source_only_stdlib_observed_root_sha256"] = (
        module_root
    )
    core = {
        key: value
        for key, value in runtime.items()
        if key != "observation_root_sha256"
    }
    runtime["observation_root_sha256"] = harness.canonical_sha256(core)

    harness.validate_runtime_identity(runtime)


def _epoch(harness, tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    runtime = _runtime(harness)
    epoch = harness.initialize_epoch(
        tmp_path / "phone-private-discovery",
        runtime_identity=runtime,
        now=datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc),
        require_phone_home=False,
    )
    return epoch, runtime


def _range_headers(source, start: int, end: int) -> bytes:
    size = end - start + 1
    return (
        "HTTP/1.1 206 Partial Content\r\n"
        f"Content-Length: {size}\r\n"
        f"Content-Range: bytes {start}-{end}/{source.expected_bytes}\r\n"
        f"ETag: {source.expected_etag}\r\n"
        f"Last-Modified: {source.expected_last_modified}\r\n"
        "Content-Type: application/epub+zip\r\n"
        "\r\n"
    ).encode("ascii")


def _page_outcome(
    harness,
    payload: bytes,
    *,
    runtime: dict[str, Any] | None = None,
) -> Any:
    headers = (
        "HTTP/1.1 200 OK\r\n"
        f"Content-Length: {len(payload)}\r\n"
        "Content-Type: text/html; charset=utf-8\r\n"
        'ETag: "fixture"\r\n'
        "Last-Modified: Sun, 12 Jul 2026 00:00:00 GMT\r\n"
        "\r\n"
    ).encode("ascii")
    runtime_identity = runtime or _runtime(harness)
    return harness.RangeOutcome(
        0,
        headers,
        payload,
        b"",
        harness.expected_curl_execution_identity(runtime_identity),
    )


def _catalogue_html(sources) -> bytes:
    cards = []
    for source in sources:
        cards.append(
            "<section class='book-card'>"
            f"<h2>{source.catalogue_subject} Grade {source.catalogue_grade}</h2>"
            f"<a href='{source.url}'>Download EPUB</a>"
            "</section>"
        )
    return (
        "<!doctype html><html><body><h1>Siyavula books</h1>"
        "<main id='textbook-catalogue'>"
        + "".join(cards)
        + "<p>All textbooks in this catalogue are licensed under "
        "<a href='https://creativecommons.org/licenses/by/3.0/'>CC BY 3.0</a>."
        "</p></main></body></html>"
    ).encode("utf-8")


def _terms_html() -> bytes:
    return (
        "<!doctype html><html><body><h1>Siyavula terms</h1>"
        "<p>Some material is licensed under a "
        "<a href='https://creativecommons.org/licenses/by/4.0/'>"
        "Creative Commons Attribution Only License</a>. Only material that is "
        "clearly marked with a Creative Commons license can be re-used without "
        "permission.</p></body></html>"
    ).encode("utf-8")


def _capture_evidence(
    harness,
    epoch: Path,
    runtime: dict[str, Any],
    lease: SyntheticLease,
    *,
    sources=None,
) -> dict[str, Any]:
    catalogue = _catalogue_html(sources or harness.SIYAVULA_SOURCES)
    terms = _terms_html()
    return harness.capture_external_evidence(
        epoch,
        executor=lambda url: _page_outcome(
            harness,
            catalogue if url == harness.CATALOGUE_URL else terms,
            runtime=runtime,
        ),
        runtime_identity=runtime,
        lease=lease,
    )


def _replace_sealed_bytes(path: Path, payload: bytes) -> None:
    replacement = path.with_name(f".{path.name}.replacement")
    replacement.write_bytes(payload)
    replacement.chmod(0o400)
    os.replace(replacement, path)


def _replace_sealed_json(harness, path: Path, value: dict[str, Any]) -> None:
    _replace_sealed_bytes(path, harness.canonical_json_bytes(value) + b"\n")


def _complete_single_source(harness, tmp_path, monkeypatch):
    payload = _epub_bytes()
    source = _source_for_payload(harness, payload)
    monkeypatch.setattr(harness, "SIYAVULA_SOURCES", (source,))
    epoch, runtime = _epoch(harness, tmp_path)
    root, epoch, _manifest = harness.validate_epoch(epoch)
    lease = SyntheticLease(harness, epoch)
    _capture_evidence(harness, epoch, runtime, lease, sources=(source,))
    selected = harness.acquire_chunk(
        root,
        epoch,
        source,
        0,
        executor=lambda observed, start, end: harness.RangeOutcome(
            0,
            _range_headers(observed, start, end),
            payload,
            b"",
            harness.expected_curl_execution_identity(runtime),
        ),
        resource_observer=lambda: lease.observe(phase="before_range"),
    )
    return payload, source, root, epoch, runtime, lease, selected


def _source_for_payload(harness, payload: bytes):
    return harness.SiyavulaSource(
        source_id="synthetic_siyavula_grade_7",
        url=f"{harness.ORIGIN}/downloads/books/science/"
        "Gr7_PhysicalSciences_Learner_Eng_CC-BY.epub",
        filename="Gr7_PhysicalSciences_Learner_Eng_CC-BY.epub",
        expected_bytes=len(payload),
        expected_etag='"fixture-etag"',
        expected_last_modified="Sun, 12 Jul 2026 00:00:00 GMT",
        catalogue_subject="Natural Sciences",
        catalogue_grade=7,
        filename_subject_token="PhysicalSciences",
        filename_grade_token="Gr7",
        known_sha256=hashlib.sha256(payload).hexdigest(),
    )


def _epub_bytes(
    *,
    grade_property: str | None = "schema:educationalLevel",
    grade_prefix: str = "schema: https://schema.org/",
    nav_fragment: str = "target",
    compression: int = zipfile.ZIP_DEFLATED,
) -> bytes:
    container = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" '
        'version="1.0"><rootfiles><rootfile full-path="OPS/book.opf" '
        'media-type="application/oebps-package+xml"/></rootfiles></container>'
    ).encode()
    grade_row = (
        f'<meta property="{grade_property}">Grade 7</meta>'
        if grade_property is not None
        else ""
    )
    opf = f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf"
 xmlns:dc="http://purl.org/dc/elements/1.1/" version="3.0"
 unique-identifier="uid" prefix="{grade_prefix}">
 <metadata>
  <dc:identifier id="uid">fixture.siyavula.grade7</dc:identifier>
  <dc:title>science7</dc:title><dc:language>en</dc:language>
  <dc:creator>Siyavula</dc:creator><dc:publisher>Siyavula</dc:publisher>
  <dc:rights>CC BY 4.0</dc:rights><dc:subject>Natural Sciences</dc:subject>
  <meta property="dcterms:modified">2026-07-12T00:00:00Z</meta>
  {grade_row}
 </metadata>
 <manifest>
  <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
  <item id="rights" href="copyright_acknowledgements_ccby.html" media-type="application/xhtml+xml"/>
  <item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml" properties="scripted"/>
  <item id="css" href="style.css" media-type="text/css"/>
  <item id="image" href="diagram.png" media-type="image/png"/>
 </manifest><spine><itemref idref="chapter"/></spine>
</package>'''.encode()
    nav = f'''<html xmlns="http://www.w3.org/1999/xhtml"
 xmlns:epub="http://www.idpf.org/2007/ops"><body>
 <nav epub:type="toc"><ol><li><a href="chapter.xhtml#{nav_fragment}">One</a></li></ol></nav>
</body></html>'''.encode()
    rights = b'''<!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml"><body>
<p>Siyavula Natural Sciences Grade 7</p>
<a href="http://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>
</body></html>'''
    chapter = b'''<html xmlns="http://www.w3.org/1999/xhtml"><body>
<section id="target" style="background: url('diagram.png'); content: 'x'">
<figure><img src="diagram.png"/></figure><table><tr><td>1</td></tr></table>
<script>drawDiagram()</script></section></body></html>'''
    css = b"figure { background: url('diagram.png'); } p:before { content: 'x'; }"
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w") as archive:
        archive.writestr(
            zipfile.ZipInfo("mimetype"),
            b"application/epub+zip",
            compress_type=zipfile.ZIP_STORED,
        )
        for name, payload in (
            ("META-INF/container.xml", container),
            ("OPS/book.opf", opf),
            ("OPS/nav.xhtml", nav),
            ("OPS/copyright_acknowledgements_ccby.html", rights),
            ("OPS/chapter.xhtml", chapter),
            ("OPS/style.css", css),
            ("OPS/diagram.png", b"synthetic-image"),
        ):
            archive.writestr(name, payload, compress_type=compression)
    return result.getvalue()


def test_roster_is_exactly_twelve_and_preserves_catalogue_filename_distinction(harness):
    sources = harness.SIYAVULA_SOURCES
    assert len(sources) == 12
    assert sum(source.expected_bytes for source in sources) == 621_790_622
    grade_7 = next(source for source in sources if source.catalogue_grade == 7)
    assert grade_7.catalogue_subject == "Natural Sciences"
    assert grade_7.filename_subject_token == "PhysicalSciences"
    assert grade_7.expected_bytes == 90_554_874
    assert harness.CHUNK_BYTES == 8 * 1024 * 1024
    assert sum(
        (source.expected_bytes + harness.CHUNK_BYTES - 1) // harness.CHUNK_BYTES
        for source in sources
    ) == harness.EXPECTED_TOTAL_CHUNK_REQUESTS == 79


def test_epoch_is_non_admission_and_never_adopts_unreceipted_legacy_chunks(
    harness, tmp_path
):
    legacy = tmp_path / "old-grade12-prefix.part"
    legacy.write_bytes(b"unreceipted")
    epoch, _runtime_value = _epoch(harness, tmp_path)
    manifest = harness.read_canonical_json(epoch / "epoch.json", schema=harness.EPOCH_SCHEMA)
    assert manifest["old_unreceipted_prefixes_or_chunks_adopted"] is False
    assert manifest["candidate_admission_claim"] is False
    source, chunk_index = harness.next_pending_chunk(epoch)
    assert source == harness.SIYAVULA_SOURCES[0]
    assert chunk_index == 0
    with pytest.raises(harness.DiscoveryError, match="candidate_transaction_root_forbidden"):
        harness.validate_discovery_root(harness.FORBIDDEN_CANDIDATE_ROOT / "probe")


def test_one_request_range_publishes_evidence_bound_CAS_selection(harness, tmp_path):
    epoch, runtime = _epoch(harness, tmp_path)
    root, epoch, _manifest = harness.validate_epoch(epoch)
    source = harness.SIYAVULA_SOURCES[0]
    start, end = harness.chunk_bounds(source, 0)
    body = bytes([index % 251 for index in range(end - start + 1)])
    calls = 0

    def executor(observed_source, observed_start, observed_end):
        nonlocal calls
        calls += 1
        assert (observed_source, observed_start, observed_end) == (source, start, end)
        return harness.RangeOutcome(
            0,
            _range_headers(source, start, end),
            body,
            b"",
            harness.expected_curl_execution_identity(runtime),
        )

    lease = SyntheticLease(harness, epoch)
    with pytest.raises(harness.DiscoveryError, match="external_evidence"):
        harness.acquire_chunk(
            root,
            epoch,
            source,
            0,
            executor=executor,
            resource_observer=lambda: lease.observe(
                phase="before_forbidden_range"
            ),
        )
    assert calls == 0
    _capture_evidence(harness, epoch, runtime, lease)
    selected = harness.acquire_chunk(
        root,
        epoch,
        source,
        0,
        executor=executor,
        resource_observer=lambda: lease.observe(phase="before_range"),
    )
    assert calls == 1
    assert selected["eligible_for_assembly"] is True
    attempt_path = harness.resolve_relative_artifact(epoch, selected["attempt_artifact"])
    attempt = harness.read_canonical_json(
        attempt_path, schema=harness.CHUNK_ATTEMPT_SCHEMA
    )
    assert attempt["request_count"] == 1
    assert attempt["curl_retry_count"] == 0
    assert attempt["body_sha256"] == hashlib.sha256(body).hexdigest()
    assert harness.hash_file(selected["cas_path"]) == (
        hashlib.sha256(body).hexdigest(),
        len(body),
    )


def test_zero_byte_failure_opens_15m_and_event_chain_rejects_state_rollback(
    harness, tmp_path
):
    epoch, runtime = _epoch(harness, tmp_path)
    root, epoch, _manifest = harness.validate_epoch(epoch)
    source = harness.SIYAVULA_SOURCES[0]
    lease = SyntheticLease(harness, epoch)
    _capture_evidence(harness, epoch, runtime, lease)
    instant = datetime(2026, 7, 12, 13, 0, tzinfo=timezone.utc)
    with pytest.raises(harness.CircuitOpen):
        harness.acquire_chunk(
            root,
            epoch,
            source,
            0,
            executor=lambda *_args: harness.RangeOutcome(
                28,
                b"",
                b"",
                b"timeout",
                harness.expected_curl_execution_identity(runtime),
            ),
            resource_observer=lambda: lease.observe(phase="before_failure"),
            now=instant,
        )
    state = harness.read_circuit(root)
    assert state["consecutive_failures"] == 1
    assert harness.parse_utc(state["open_until_utc"]) == instant + timedelta(minutes=15)
    rolled_back = harness.initial_circuit_state()
    harness.replace_mutable_json(harness.circuit_path(root), rolled_back)
    restored = harness.read_circuit(root)
    assert restored == state
    assert restored["consecutive_failures"] == 1


def test_epub_v2_observation_binds_metadata_fragments_media_and_CSS(harness, tmp_path):
    payload = _epub_bytes()
    source = _source_for_payload(harness, payload)
    path = tmp_path / source.filename
    path.write_bytes(payload)
    fd = os.open(path, os.O_RDONLY)
    try:
        identity = harness.inspect_epub_fd(fd, source)
    finally:
        os.close(fd)
    assert identity["container"]["sha256"].startswith("sha256:")
    assert identity["metadata"]["package_version"] == "3.0"
    assert identity["metadata"]["package_unique_identifier_id"] == "uid"
    assert identity["metadata"]["package_unique_identifier_linked"] is True
    assert identity["metadata"]["dc_creator_values"] == ["Siyavula"]
    assert identity["metadata"]["recognized_grade_observation_state"] == "observed_values"
    assert identity["navigation"]["fragment_targets_verified"] is True
    assert identity["navigation"]["fragment_link_count"] == 1
    media = identity["media_context"]
    assert media["visual_or_table_context_quarantine_required"] is True
    assert media["scripted_manifest_item_count"] >= 1
    assert media["media_context_element_counts"]["script"] == 1
    assert media["inline_style_url_token_count"] == 1
    assert media["inline_style_content_declaration_count"] == 1
    assert media["CSS_url_token_count"] == 1
    assert media["CSS_content_declaration_count"] == 1
    core = {
        key: value
        for key, value in identity.items()
        if key not in {"observation_root_sha256", "schema_version"}
    }
    assert identity["observation_root_sha256"] == harness.canonical_sha256(core)


def test_empty_OPF_tuples_are_observed_empty_not_unknown(harness, tmp_path):
    payload = _epub_bytes(grade_property=None)
    source = _source_for_payload(harness, payload)
    path = tmp_path / "empty.epub"
    path.write_bytes(payload)
    fd = os.open(path, os.O_RDONLY)
    try:
        identity = harness.inspect_epub_fd(fd, source)
    finally:
        os.close(fd)
    metadata = identity["metadata"]
    assert metadata["recognized_grade_metadata"] == []
    assert metadata["recognized_grade_observation_state"] == "observed_empty"


def test_unapproved_grade_like_prefix_and_missing_TOC_fragment_fail_closed(
    harness, tmp_path
):
    evil = _epub_bytes(grade_property="evil:grade", grade_prefix="evil: https://evil.test/")
    missing = _epub_bytes(nav_fragment="absent")
    for name, payload, pattern in (
        ("evil.epub", evil, "unapproved_grade_like"),
        ("missing.epub", missing, "fragment_id_missing"),
    ):
        source = _source_for_payload(harness, payload)
        path = tmp_path / name
        path.write_bytes(payload)
        fd = os.open(path, os.O_RDONLY)
        try:
            with pytest.raises(harness.DiscoveryError, match=pattern):
                harness.inspect_epub_fd(fd, source)
        finally:
            os.close(fd)


def test_ZIP_method_and_aggregate_XHTML_bound_are_enforced(
    harness, tmp_path, monkeypatch
):
    payload = _epub_bytes(compression=zipfile.ZIP_BZIP2)
    source = _source_for_payload(harness, payload)
    path = tmp_path / "bzip.epub"
    path.write_bytes(payload)
    fd = os.open(path, os.O_RDONLY)
    try:
        with pytest.raises(harness.DiscoveryError, match="envelope_invalid"):
            harness.inspect_epub_fd(fd, source)
    finally:
        os.close(fd)
    payload = _epub_bytes()
    source = _source_for_payload(harness, payload)
    path = tmp_path / "bounded.epub"
    path.write_bytes(payload)
    monkeypatch.setattr(harness, "MAX_AGGREGATE_XHTML_BYTES", 1)
    fd = os.open(path, os.O_RDONLY)
    try:
        with pytest.raises(harness.DiscoveryError, match="aggregate_XHTML_memory_bound"):
            harness.inspect_epub_fd(fd, source)
    finally:
        os.close(fd)


def test_catalogue_preimage_requires_unique_context_not_a_naked_matching_href(harness):
    catalogue_payload = _catalogue_html(harness.SIYAVULA_SOURCES)
    terms_payload = _terms_html()
    catalogue_transport = harness.validate_page_outcome(
        harness.CATALOGUE_URL, _page_outcome(harness, catalogue_payload)
    )
    terms_transport = harness.validate_page_outcome(
        harness.TERMS_URL, _page_outcome(harness, terms_payload)
    )
    bindings = {
        role: {
            "attempt_sha256": "sha256:" + character * 64,
            "resource_observation_sha256": "sha256:" + character * 64,
            "runtime_identity_sha256": "sha256:" + character * 64,
        }
        for role, character in (("catalogue", "a"), ("terms", "b"))
    }
    preimage = harness.build_external_evidence_preimage(
        catalogue_payload,
        catalogue_transport,
        terms_payload,
        terms_transport,
        bindings,
    )
    grade_7 = next(
        record
        for record in preimage["catalogue"]["target_anchor_records"]
        if record["catalogue_grade"] == 7
    )
    assert grade_7["catalogue_subject"] == "Natural Sciences"
    assert grade_7["target_context_evidence"][
        "expected_catalogue_subject_and_grade_uniquely_asserted"
    ] is True
    naked = (
        "<html><body>"
        + "".join(f"<a href='{source.url}'>Download</a>" for source in harness.SIYAVULA_SOURCES)
        + "<a href='https://creativecommons.org/licenses/by/3.0/'>CC</a>"
        "</body></html>"
    ).encode()
    naked_transport = harness.validate_page_outcome(
        harness.CATALOGUE_URL, _page_outcome(harness, naked)
    )
    with pytest.raises(harness.DiscoveryError, match="subject_grade_not_unique"):
        harness.build_external_evidence_preimage(
            naked,
            naked_transport,
            terms_payload,
            terms_transport,
            bindings,
        )


def test_external_evidence_binds_attempt_runtime_resource_and_CAS(
    harness, tmp_path
):
    epoch, runtime = _epoch(harness, tmp_path)
    lease = SyntheticLease(harness, epoch)
    evidence = _capture_evidence(harness, epoch, runtime, lease)
    root, epoch, _manifest = harness.validate_epoch(epoch)
    assert harness.validate_external_evidence(root, epoch) == evidence
    for role in ("catalogue", "terms"):
        binding = evidence["egress_preimage"][role]["successful_attempt_binding"]
        assert binding["runtime_identity_sha256"] == harness.canonical_sha256(runtime)
        assert binding["attempt_sha256"].startswith("sha256:")
        assert binding["resource_observation_sha256"].startswith("sha256:")


def test_single_source_finalize_is_crash_idempotent_and_aggregate_is_deeply_bound(
    harness, tmp_path, monkeypatch
):
    payload = _epub_bytes()
    source = _source_for_payload(harness, payload)
    monkeypatch.setattr(harness, "SIYAVULA_SOURCES", (source,))
    epoch, runtime = _epoch(harness, tmp_path)
    root, epoch, _manifest = harness.validate_epoch(epoch)
    lease = SyntheticLease(harness, epoch)
    _capture_evidence(harness, epoch, runtime, lease, sources=(source,))
    harness.acquire_chunk(
        root,
        epoch,
        source,
        0,
        executor=lambda observed, start, end: harness.RangeOutcome(
            0,
            _range_headers(observed, start, end),
            payload,
            b"",
            harness.expected_curl_execution_identity(runtime),
        ),
        resource_observer=lambda: lease.observe(phase="before_range"),
    )
    # Simulate a crash after the per-source immutable identity but before the
    # aggregate receipt, then verify finalization reuses it safely.
    before = lease.observe(phase="before_partial_identity")
    first_identity = harness.inspect_source_identity(
        root,
        epoch,
        source,
        before_resource_observation=before,
        after_resource_observer=lambda: lease.observe(phase="after_partial_identity"),
    )
    receipt = harness.finalize_epoch(
        epoch,
        runtime_identity=runtime,
        lease=lease,
    )
    original_inspector = harness.inspect_source_identity
    replay_calls = 0

    def counting_inspector(*args, **kwargs):
        nonlocal replay_calls
        replay_calls += 1
        return original_inspector(*args, **kwargs)

    monkeypatch.setattr(harness, "inspect_source_identity", counting_inspector)
    second = harness.finalize_epoch(
        epoch,
        runtime_identity=runtime,
        lease=lease,
    )
    assert second == receipt
    assert replay_calls == 1
    assert receipt["source_identity_observations"][0][
        "observation_root_sha256"
    ] == first_identity["observation_root_sha256"]
    harness.validate_aggregate_receipt(receipt)
    tampered = deepcopy(receipt)
    tampered["source_identity_observations"][0]["metadata"][
        "package_version"
    ] = "9.9"
    tampered_core = {
        key: value
        for key, value in tampered.items()
        if key not in {"receipt_observation_root_sha256", "schema_version"}
    }
    tampered["receipt_observation_root_sha256"] = harness.canonical_sha256(
        tampered_core
    )
    with pytest.raises(harness.DiscoveryError, match="egress_identity_root_invalid"):
        harness.validate_aggregate_receipt(tampered)


def test_catalogue_license_must_structurally_apply_and_hidden_or_CC4_text_cannot_substitute(
    harness,
):
    terms = _terms_html()
    bindings = {
        role: {
            "attempt_sha256": "sha256:" + character * 64,
            "resource_observation_sha256": "sha256:" + character * 64,
            "runtime_identity_sha256": "sha256:" + character * 64,
        }
        for role, character in (("catalogue", "a"), ("terms", "b"))
    }

    def build(catalogue: bytes, terms_payload: bytes = terms):
        return harness.build_external_evidence_preimage(
            catalogue,
            harness.validate_page_outcome(
                harness.CATALOGUE_URL,
                _page_outcome(harness, catalogue),
            ),
            terms_payload,
            harness.validate_page_outcome(
                harness.TERMS_URL,
                _page_outcome(harness, terms_payload),
            ),
            bindings,
        )

    cards = "".join(
        "<section class='book-card'>"
        f"<h2>{source.catalogue_subject} Grade {source.catalogue_grade}</h2>"
        f"<a href='{source.url}'>Download EPUB</a></section>"
        for source in harness.SIYAVULA_SOURCES
    )
    unrelated_global = (
        "<html><body><main>" + cards + "</main>"
        "<footer><p>This unrelated policy document is licensed under "
        "<a href='https://creativecommons.org/licenses/by/3.0/'>CC BY 3.0</a>"
        "</p></footer></body></html>"
    ).encode()
    with pytest.raises(harness.DiscoveryError, match="not_structurally_applicable"):
        build(unrelated_global)

    hidden_cards = "".join(
        "<section class='book-card'>"
        f"<h2 style='display:none'>{source.catalogue_subject} "
        f"Grade {source.catalogue_grade}</h2>"
        f"<a href='{source.url}'>Download EPUB</a></section>"
        for source in harness.SIYAVULA_SOURCES
    )
    hidden = (
        "<html><body><main>" + hidden_cards
        + "<p>All textbooks in this catalogue are licensed under "
        "<a href='https://creativecommons.org/licenses/by/3.0/'>CC BY 3.0</a>"
        "</p></main></body></html>"
    ).encode()
    with pytest.raises(harness.DiscoveryError, match="subject_grade_not_unique"):
        build(hidden)

    radius_cards = "".join(
        "<section class='book-card'>"
        f"<h2>{source.catalogue_subject} {'x' * 300} "
        f"Grade {source.catalogue_grade}</h2>"
        f"<a href='{source.url}'>Download EPUB</a></section>"
        for source in harness.SIYAVULA_SOURCES
    )
    radius = (
        "<html><body><main>" + radius_cards
        + "<p>All textbooks in this catalogue are licensed under "
        "<a href='https://creativecommons.org/licenses/by/3.0/'>CC BY 3.0</a>"
        "</p></main></body></html>"
    ).encode()
    with pytest.raises(harness.DiscoveryError, match="subject_grade_not_unique"):
        build(radius)

    CC4_catalogue = _catalogue_html(harness.SIYAVULA_SOURCES).replace(
        b"/licenses/by/3.0/", b"/licenses/by/4.0/"
    )
    with pytest.raises(harness.DiscoveryError, match="catalogue_CC_BY_3"):
        build(CC4_catalogue, terms)

    CC3_terms = terms.replace(b"/licenses/by/4.0/", b"/licenses/by/3.0/")
    with pytest.raises(harness.DiscoveryError, match="terms_CC_BY_4"):
        build(_catalogue_html(harness.SIYAVULA_SOURCES), CC3_terms)

    unscoped_terms = terms.replace(
        b"Only material that is clearly marked with a Creative Commons license "
        b"can be re-used without permission.",
        b"This page contains a Creative Commons link.",
    )
    with pytest.raises(harness.DiscoveryError, match="marked_material_CC_BY_notice"):
        build(_catalogue_html(harness.SIYAVULA_SOURCES), unscoped_terms)


def test_per_card_CC_BY_3_anchor_is_accepted_without_global_scope_claim(harness):
    cards = "".join(
        "<section class='book-card'>"
        f"<h2>{source.catalogue_subject} Grade {source.catalogue_grade}</h2>"
        f"<a href='{source.url}'>Download EPUB</a>"
        "<a href='https://creativecommons.org/licenses/by/3.0/'>CC BY 3.0</a>"
        "</section>"
        for source in harness.SIYAVULA_SOURCES
    )
    catalogue = ("<html><body><h1>Siyavula</h1>" + cards + "</body></html>").encode()
    terms = _terms_html()
    bindings = {
        role: {
            "attempt_sha256": "sha256:" + character * 64,
            "resource_observation_sha256": "sha256:" + character * 64,
            "runtime_identity_sha256": "sha256:" + character * 64,
        }
        for role, character in (("catalogue", "a"), ("terms", "b"))
    }
    preimage = harness.build_external_evidence_preimage(
        catalogue,
        harness.validate_page_outcome(
            harness.CATALOGUE_URL,
            _page_outcome(harness, catalogue),
        ),
        terms,
        harness.validate_page_outcome(
            harness.TERMS_URL,
            _page_outcome(harness, terms),
        ),
        bindings,
    )
    modes = {
        record["application_mode"]
        for record in preimage["catalogue"]["license_applicability_preimage"][
            "target_applicability_records"
        ]
    }
    assert modes == {"exact_CC_BY_3_0_anchor_within_selected_target_card"}
    harness.validate_external_preimage_closed(preimage)


def test_catalogue_subject_parser_preserves_natural_sciences_and_technology(
    harness,
):
    assert harness.DEFAULT_DISCOVERY_ROOT.name.endswith("identity_discovery_v3")
    assert harness.contextual_assertion_pairs(
        "Natural Sciences and Technology Grade 4"
    ) == {(4, "Natural Sciences and Technology")}
    assert harness.contextual_assertion_pairs("Natural Sciences Grade 7") == {
        (7, "Natural Sciences")
    }


def test_closed_runtime_external_and_aggregate_schemas_reject_unknown_fields(
    harness, tmp_path, monkeypatch
):
    runtime = _runtime(harness)
    tampered_runtime = deepcopy(runtime)
    tampered_runtime["phone_identity"]["properties"]["unknown_serial"] = "forged"
    phone_core = {
        key: value
        for key, value in tampered_runtime["phone_identity"].items()
        if key != "observation_root_sha256"
    }
    tampered_runtime["phone_identity"]["observation_root_sha256"] = (
        harness.canonical_sha256(phone_core)
    )
    runtime_core = {
        key: value
        for key, value in tampered_runtime.items()
        if key != "observation_root_sha256"
    }
    tampered_runtime["observation_root_sha256"] = harness.canonical_sha256(
        runtime_core
    )
    with pytest.raises(harness.DiscoveryError, match="phone_properties_closed_schema"):
        harness.validate_runtime_identity(tampered_runtime)

    catalogue = _catalogue_html(harness.SIYAVULA_SOURCES)
    terms = _terms_html()
    transport_catalogue = harness.validate_page_outcome(
        harness.CATALOGUE_URL,
        _page_outcome(harness, catalogue),
    )
    transport_terms = harness.validate_page_outcome(
        harness.TERMS_URL,
        _page_outcome(harness, terms),
    )
    bindings = {
        role: {
            "attempt_sha256": "sha256:" + character * 64,
            "resource_observation_sha256": "sha256:" + character * 64,
            "runtime_identity_sha256": "sha256:" + character * 64,
        }
        for role, character in (("catalogue", "a"), ("terms", "b"))
    }
    external = harness.build_external_evidence_preimage(
        catalogue,
        transport_catalogue,
        terms,
        transport_terms,
        bindings,
    )
    external["catalogue"]["unknown_authority_claim"] = True
    with pytest.raises(harness.DiscoveryError, match="external_catalogue_closed_schema"):
        harness.validate_external_preimage_closed(external)

    _payload, _source, _root, _epoch_path, _runtime_value, _lease, _selected = (
        _complete_single_source(harness, tmp_path, monkeypatch)
    )
    receipt = harness.finalize_epoch(
        _epoch_path,
        runtime_identity=_runtime_value,
        lease=_lease,
    )
    unknown_top = deepcopy(receipt)
    unknown_top["narratable_win"] = True
    with pytest.raises(harness.DiscoveryError, match="aggregate_receipt_closed_schema"):
        harness.validate_aggregate_receipt(unknown_top)
    unknown_nested = deepcopy(receipt)
    unknown_nested["source_identity_observations"][0]["metadata"][
        "forged_claim"
    ] = "pass"
    identity = unknown_nested["source_identity_observations"][0]
    identity_core = {
        key: value
        for key, value in identity.items()
        if key not in {"observation_root_sha256", "schema_version"}
    }
    identity["observation_root_sha256"] = harness.canonical_sha256(identity_core)
    aggregate_core = {
        key: value
        for key, value in unknown_nested.items()
        if key not in {"receipt_observation_root_sha256", "schema_version"}
    }
    unknown_nested["receipt_observation_root_sha256"] = harness.canonical_sha256(
        aggregate_core
    )
    with pytest.raises(harness.DiscoveryError, match="identity_metadata_closed_schema"):
        harness.validate_aggregate_receipt(unknown_nested)


def test_production_root_fails_closed_outside_phone_home(harness, tmp_path):
    runtime = _runtime(harness)
    with pytest.raises(
        harness.DiscoveryError,
        match="production_discovery_root_outside_phone_home",
    ):
        harness.initialize_epoch(
            tmp_path / "not-phone-home",
            runtime_identity=runtime,
        )


def test_curl_uses_system_linker_held_FD_disable_exact_env_and_private_temp(
    harness, tmp_path, monkeypatch
):
    private_temp = tmp_path / "transport-tmp"
    private_temp.mkdir(mode=0o700)
    target = tmp_path / "curl"
    target.write_bytes(b"held-curl")
    target_fd = os.open(target, os.O_RDONLY)
    runtime = _runtime(harness)
    CA_identity = runtime["curl_CA_bundle"]
    CA_path = tmp_path / "cert.pem"
    CA_path.write_bytes(b"fixture-CA")
    CA_fd = os.open(CA_path, os.O_RDONLY)
    CA_before = os.fstat(CA_fd)
    captured: dict[str, Any] = {}

    class Guard:
        linker_path = Path("/system/bin/linker64")
        closure = runtime["curl_loader_closure"]

        def __init__(self) -> None:
            self.target_fd = target_fd

        def revalidate(self) -> None:
            return None

        def close(self) -> None:
            os.close(self.target_fd)

    guard = Guard()
    monkeypatch.setattr(harness, "open_loader_closure", lambda *_a, **_k: guard)
    monkeypatch.setattr(
        harness,
        "open_CA_bundle",
        lambda: (CA_fd, CA_before, CA_identity),
    )
    monkeypatch.setattr(harness, "revalidate_held_executable", lambda *_a: None)
    body = b"<html><body>Siyavula</body></html>"

    def fake_run(argv, **kwargs):
        captured["argv"] = list(argv)
        captured["kwargs"] = dict(kwargs)
        headers_fd, body_fd = kwargs["pass_fds"][:2]
        os.write(
            headers_fd,
            (
                "HTTP/1.1 200 OK\r\n"
                f"Content-Length: {len(body)}\r\n"
                "Content-Type: text/html; charset=utf-8\r\n\r\n"
            ).encode(),
        )
        os.write(body_fd, body)
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(harness.subprocess, "run", fake_run)
    outcome = harness.curl_page_executor(
        harness.CATALOGUE_URL,
        private_temp_dir=private_temp,
    )
    argv = captured["argv"]
    kwargs = captured["kwargs"]
    assert argv[:3] == [
        "/system/bin/linker64",
        f"/proc/self/fd/{target_fd}",
        "--disable",
    ]
    assert argv.count("--retry") == 1
    assert argv[argv.index("--retry") + 1] == "0"
    assert argv[argv.index("--cacert") + 1] == f"/proc/self/fd/{CA_fd}"
    assert kwargs["env"] == harness.exact_curl_environment(private_temp)
    assert "executable" not in kwargs
    assert kwargs["timeout"] == harness.CURL_SUBPROCESS_TIMEOUT_SECONDS
    assert outcome.body == body


def test_CLI_binds_validated_private_transport_temp_into_both_curl_executors(
    harness, tmp_path, monkeypatch
):
    epoch, runtime = _epoch(harness, tmp_path)
    root, epoch, _manifest = harness.validate_epoch(epoch)
    expected_temp = root / "transport_tmp"
    captured: list[tuple[str, Path, Path]] = []
    monkeypatch.setattr(harness, "current_phone_runtime_identity", lambda: runtime)
    monkeypatch.setattr(
        harness,
        "DiscoveryLease",
        lambda *, epoch, lease_seconds: SyntheticLease(harness, epoch),
    )

    def fake_range(source, start, end, *, curl_path, private_temp_dir):
        del source, start, end
        captured.append(("range", curl_path, private_temp_dir))
        return None

    def fake_acquire(
        observed_epoch,
        *,
        executor,
        runtime_identity,
        lease,
        max_successful_chunks,
    ):
        del observed_epoch, runtime_identity, lease, max_successful_chunks
        executor(harness.SIYAVULA_SOURCES[0], 0, 0)
        return {}

    monkeypatch.setattr(harness, "curl_range_executor", fake_range)
    monkeypatch.setattr(harness, "acquire_epoch", fake_acquire)
    assert harness.main(["acquire", str(epoch), "--max-successful-chunks", "1"]) == 0

    def fake_page(url, *, curl_path, private_temp_dir):
        del url
        captured.append(("page", curl_path, private_temp_dir))
        return None

    def fake_evidence(
        observed_epoch,
        *,
        executor,
        runtime_identity,
        lease,
    ):
        del observed_epoch, runtime_identity, lease
        executor(harness.CATALOGUE_URL)
        return {}

    monkeypatch.setattr(harness, "curl_page_executor", fake_page)
    monkeypatch.setattr(harness, "capture_external_evidence", fake_evidence)
    assert harness.main(["evidence", str(epoch)]) == 0
    assert captured == [
        ("range", harness.DEFAULT_CURL, expected_temp),
        ("page", harness.DEFAULT_CURL, expected_temp),
    ]


def test_real_discovery_lease_accepts_its_own_observation_write_and_rejects_mode_tamper(
    harness, tmp_path
):
    epoch, _runtime = _epoch(harness, tmp_path)
    lease = harness.DiscoveryLease(
        epoch=epoch,
        lease_seconds=harness.REQUEST_AND_TERMINAL_RESERVE_SECONDS + 60,
        monotonic=lambda: 1.0,
        thermal_observer=lambda: {
            "battery": {
                "raw_value": 300,
                "temperature_millidegrees_c": 30_000,
            },
            "compute_zones": [],
            "policy": harness.THERMAL_POLICY,
            "PMIC_maximum_not_used_as_gate": True,
        },
    )

    artifact, digest = lease.observe(phase="first")
    assert harness.file_payload_sha256(epoch / artifact) == digest
    lease.checkpoint(phase="after_own_write")

    epoch.chmod(0o750)
    with pytest.raises(harness.DiscoveryError, match="epoch_identity_changed"):
        lease.checkpoint(phase="after_mode_tamper")


def test_response_header_parser_combines_vary_but_rejects_duplicate_authority_fields(
    harness,
):
    status, fields = harness.parse_single_response_headers(
        b"HTTP/1.1 200 OK\r\nVary: Accept-Encoding\r\nVary: Origin\r\n\r\n"
    )
    assert status == 200
    assert fields["vary"] == "Accept-Encoding, Origin"

    with pytest.raises(
        harness.DiscoveryError, match="duplicate_header:content-length"
    ):
        harness.parse_single_response_headers(
            b"HTTP/1.1 200 OK\r\nContent-Length: 1\r\nContent-Length: 1\r\n\r\n"
        )


def test_durable_request_intent_survives_abrupt_unwind_and_blocks_next_epoch(
    harness, tmp_path
):
    runtime = _runtime(harness)
    root_path = tmp_path / "shared-origin-root"
    epoch_one = harness.initialize_epoch(
        root_path,
        runtime_identity=runtime,
        require_phone_home=False,
    )
    lease_one = SyntheticLease(harness, epoch_one)

    class SimulatedProcessDeath(BaseException):
        pass

    with pytest.raises(SimulatedProcessDeath):
        harness.capture_external_evidence(
            epoch_one,
            executor=lambda _url: (_ for _ in ()).throw(SimulatedProcessDeath()),
            runtime_identity=runtime,
            lease=lease_one,
        )
    state = harness.read_circuit(root_path)
    assert state["consecutive_failures"] == 1
    assert state["open_until_utc"] is not None

    epoch_two = harness.initialize_epoch(
        root_path,
        runtime_identity=runtime,
        require_phone_home=False,
    )
    lease_two = SyntheticLease(harness, epoch_two)
    calls = 0

    def forbidden_executor(_url):
        nonlocal calls
        calls += 1
        pytest.fail("origin circuit permitted a second request")

    with pytest.raises(harness.CircuitOpen, match="origin_circuit_open_until"):
        harness.capture_external_evidence(
            epoch_two,
            executor=forbidden_executor,
            runtime_identity=runtime,
            lease=lease_two,
        )
    assert calls == 0


def test_range_request_intent_is_durable_before_executor_and_blocks_replay(
    harness, tmp_path
):
    epoch, runtime = _epoch(harness, tmp_path)
    root, epoch, _manifest = harness.validate_epoch(epoch)
    lease = SyntheticLease(harness, epoch)
    _capture_evidence(harness, epoch, runtime, lease)
    source = harness.SIYAVULA_SOURCES[0]

    class SimulatedProcessDeath(BaseException):
        pass

    with pytest.raises(SimulatedProcessDeath):
        harness.acquire_chunk(
            root,
            epoch,
            source,
            0,
            executor=lambda *_args: (_ for _ in ()).throw(
                SimulatedProcessDeath()
            ),
            resource_observer=lambda: lease.observe(phase="before_abrupt_range"),
        )
    state = harness.read_circuit(root)
    assert state["consecutive_failures"] == 1
    calls = 0

    def forbidden_executor(*_args):
        nonlocal calls
        calls += 1
        pytest.fail("durable range intent did not preserve cooldown")

    with pytest.raises(harness.CircuitOpen, match="origin_circuit_open_until"):
        harness.acquire_chunk(
            root,
            epoch,
            source,
            0,
            executor=forbidden_executor,
            resource_observer=lambda: lease.observe(
                phase="before_forbidden_replay"
            ),
        )
    assert calls == 0


def test_root_scoped_origin_lock_serializes_cross_epoch_callers(harness, tmp_path):
    epoch, _runtime_value = _epoch(harness, tmp_path)
    root, _epoch_path, _manifest = harness.validate_epoch(epoch)
    first_entered = threading.Event()
    release_first = threading.Event()
    second_entered = threading.Event()

    def first() -> None:
        with harness.origin_lock(root):
            first_entered.set()
            assert release_first.wait(2)

    def second() -> None:
        assert first_entered.wait(2)
        with harness.origin_lock(root):
            second_entered.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first_future = pool.submit(first)
        second_future = pool.submit(second)
        assert first_entered.wait(2)
        assert second_entered.wait(0.1) is False
        release_first.set()
        first_future.result(timeout=2)
        second_future.result(timeout=2)
    assert second_entered.is_set()


def test_CAS_path_swap_is_detected_before_validation_and_during_assembly(
    harness, tmp_path, monkeypatch
):
    payload, source, root, epoch, _runtime_value, _lease, selected = (
        _complete_single_source(harness, tmp_path, monkeypatch)
    )
    cas_path = selected["cas_path"]
    malicious = bytes((byte + 1) % 256 for byte in payload)
    _replace_sealed_bytes(cas_path, malicious)
    with pytest.raises(harness.DiscoveryError, match="selected_chunk_evidence_invalid"):
        harness.validate_selected_chunk(root, epoch, source, 0)

    # Restore a fresh valid selection in a distinct root, then swap the path
    # only after the validated CAS FD has been opened.
    second_root = tmp_path / "second"
    payload, source, root, epoch, _runtime_value, _lease, _selected = (
        _complete_single_source(harness, second_root, monkeypatch)
    )
    original_open = harness.open_validated_CAS_fd
    swapped = False

    def open_then_swap(observed_root, record):
        nonlocal swapped
        fd, observed_path, before = original_open(observed_root, record)
        if not swapped:
            swapped = True
            _replace_sealed_bytes(
                observed_path,
                bytes((byte + 1) % 256 for byte in payload),
            )
        return fd, observed_path, before

    monkeypatch.setattr(harness, "open_validated_CAS_fd", open_then_swap)
    with pytest.raises(harness.DiscoveryError, match="CAS_changed_or_wrong_stream"):
        harness.assemble_source(root, epoch, source)


def test_streaming_XML_guards_and_checkpoint_interruptions_fail_closed(
    harness, monkeypatch
):
    nested = ("<n>" * (harness.MAX_XML_DEPTH + 1) + "</n>" * (harness.MAX_XML_DEPTH + 1)).encode()
    with pytest.raises(harness.DiscoveryError, match="XML_allocation_limit"):
        harness.parse_xml(nested, role="depth")

    monkeypatch.setattr(harness, "MAX_XML_ELEMENTS", 3)
    with pytest.raises(harness.DiscoveryError, match="XML_allocation_limit"):
        harness.parse_xml(b"<r><a/><b/><c/></r>", role="elements")

    def interrupted(_phase: str) -> None:
        raise harness.DiscoveryError("lease_interrupted")

    with pytest.raises(harness.DiscoveryError, match="lease_interrupted"):
        harness.parse_xml(
            b"<r><a/></r>",
            role="checkpoint",
            checkpoint=interrupted,
        )


def test_exact_phone_values_and_held_fd3_harness_identity_are_non_substitutable(
    harness, monkeypatch, tmp_path
):
    runtime = _runtime(harness)
    for mutation in ("serial", "symlink", "linker_owner"):
        tampered = deepcopy(runtime)
        phone = tampered["phone_identity"]
        if mutation == "serial":
            phone["properties"]["phone_process_serial"] = (
                harness.EXPECTED_EXTERNAL_ADB_SERIAL
            )
        elif mutation == "symlink":
            phone["getprop"]["symlink"]["target"] = "/system/bin/toolbox"
        else:
            phone["getprop"]["linker64"]["uid"] = 2000
        phone_core = {
            key: value
            for key, value in phone.items()
            if key != "observation_root_sha256"
        }
        phone["observation_root_sha256"] = harness.canonical_sha256(phone_core)
        runtime_core = {
            key: value
            for key, value in tampered.items()
            if key != "observation_root_sha256"
        }
        tampered["observation_root_sha256"] = harness.canonical_sha256(runtime_core)
        with pytest.raises(harness.DiscoveryError):
            harness.validate_runtime_identity(tampered)

    original_payload = b"sealed harness payload"
    original_path = tmp_path / "harness.py"
    original_path.write_bytes(original_payload)
    original_path.chmod(0o400)
    held_fd = os.open(original_path, os.O_RDONLY)
    saved_fd3: int | None
    try:
        saved_fd3 = os.dup(harness.HARNESS_EXECUTION_FD)
    except OSError:
        saved_fd3 = None
    try:
        os.dup2(held_fd, harness.HARNESS_EXECUTION_FD)
        moved = tmp_path / "held-original.py"
        original_path.rename(moved)
        original_path.write_bytes(b"substituted path payload")
        original_readlink = os.readlink
        monkeypatch.setattr(
            harness.os,
            "readlink",
            lambda path: str(moved)
            if path == harness.HARNESS_EXECUTION_PATH
            else original_readlink(path),
        )
        identity = harness.held_harness_identity()
        assert identity["sha256"] == "sha256:" + hashlib.sha256(
            original_payload
        ).hexdigest()
        assert identity["execution_fd"] == 3
        assert identity["execution_path"] == "/proc/self/fd/3"
        assert identity["path"] == str(moved)
    finally:
        if saved_fd3 is None:
            os.close(harness.HARNESS_EXECUTION_FD)
        else:
            os.dup2(saved_fd3, harness.HARNESS_EXECUTION_FD)
            os.close(saved_fd3)
        os.close(held_fd)


def test_restart_replay_reopens_identity_artifact_and_rejects_tamper(
    harness, tmp_path, monkeypatch
):
    _payload, source, _root, epoch, runtime, lease, _selected = (
        _complete_single_source(harness, tmp_path, monkeypatch)
    )
    harness.finalize_epoch(epoch, runtime_identity=runtime, lease=lease)
    identity_path = epoch / "identities" / f"{source.source_id}.json"
    tampered = harness.read_canonical_json(identity_path, schema=harness.IDENTITY_SCHEMA)
    tampered["metadata"]["forged_restart_claim"] = "pass"
    identity_core = harness.identity_observation_core(tampered)
    tampered["observation_root_sha256"] = harness.canonical_sha256(identity_core)
    _replace_sealed_json(harness, identity_path, tampered)
    with pytest.raises(harness.DiscoveryError, match="identity_reinspection_mismatch"):
        harness.finalize_epoch(epoch, runtime_identity=runtime, lease=lease)


def test_immutable_evidence_is_0400_single_link_and_locks_remain_mutable(
    harness, tmp_path, monkeypatch
):
    _payload, source, root, epoch, runtime, lease, selected = (
        _complete_single_source(harness, tmp_path, monkeypatch)
    )
    receipt = harness.finalize_epoch(epoch, runtime_identity=runtime, lease=lease)
    del receipt
    selected_path = harness.selection_path(epoch, source, 0)
    attempt_path = harness.resolve_relative_artifact(
        epoch,
        harness.read_canonical_json(
            selected_path,
            schema=harness.CHUNK_SELECTION_SCHEMA,
        )["attempt_artifact"],
    )
    immutable_paths = [
        root / "DISCOVERY_ROOT.json",
        epoch / "epoch.json",
        epoch / "external_evidence.json",
        epoch / "SELECTION_READY.json",
        selected_path,
        attempt_path,
        selected["cas_path"],
        epoch / "aggregate_receipt.json",
    ]
    for path in immutable_paths:
        value = path.stat()
        assert stat.S_IMODE(value.st_mode) == 0o400
        assert value.st_nlink == 1
    for path in (epoch / ".lock", root / "origin_control" / ".origin.lock"):
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_startup_absence_uses_lexists_for_broken_symlinks(
    harness, tmp_path, monkeypatch
):
    broken = tmp_path / "broken-cache-prefix"
    broken.symlink_to(tmp_path / "missing-target")
    monkeypatch.setattr(harness, "ABSENT_PYCACHE_PREFIX", broken)
    assert broken.exists() is False
    assert os.path.lexists(broken) is True
    with pytest.raises(
        harness.DiscoveryError, match="isolated_source_only_startup_contract"
    ):
        harness.require_python_startup_contract()


def test_no_network_primitives_are_used_by_tests(monkeypatch):
    # This sentinel makes accidental future additions of common client calls
    # fail loudly within this module's process.
    monkeypatch.setattr("socket.create_connection", lambda *_a, **_k: pytest.fail("network"))
    assert True
