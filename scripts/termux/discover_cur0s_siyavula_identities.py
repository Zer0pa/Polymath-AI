#!/usr/bin/env python3
"""Phone-only, non-admission Siyavula EPUB identity discovery.

This program intentionally lives outside the CUR-0S candidate transaction.  It
downloads exact 4 MiB ranges into an evidence-bound content-addressed store,
assembles only chunks with immutable successful-attempt records, and emits a
single aggregate discovery receipt.  The receipt is evidence for a later
preregistration; it is never a source-admission, semantic, or authority claim.

Raw EPUB bytes, range bodies, member payloads, and per-chunk evidence are
phone-private and must not be copied off the phone.  Only the final aggregate
receipt schema is designed for egress.
"""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any, BinaryIO, Callable, Iterator, Mapping, Sequence
from urllib.parse import unquote, urljoin, urlsplit
import uuid
import xml.etree.ElementTree as ElementTree
import zipfile


DISCOVERY_SCHEMA = "cur0s_siyavula_identity_discovery_v2"
EPOCH_SCHEMA = "cur0s_siyavula_identity_discovery_epoch_v2"
CHUNK_ATTEMPT_SCHEMA = "cur0s_siyavula_range_attempt_v2"
CHUNK_SELECTION_SCHEMA = "cur0s_siyavula_chunk_selection_v2"
ASSEMBLY_SCHEMA = "cur0s_siyavula_epub_assembly_v2"
IDENTITY_SCHEMA = "cur0s_siyavula_epub_identity_observation_v2"
AGGREGATE_RECEIPT_SCHEMA = "cur0s_siyavula_identity_discovery_receipt_v2"
RESOURCE_OBSERVATION_SCHEMA = "cur0s_siyavula_discovery_resource_observation_v2"
EXTERNAL_EVIDENCE_SCHEMA = "cur0s_siyavula_catalogue_terms_evidence_v2"
PAGE_ATTEMPT_SCHEMA = "cur0s_siyavula_external_page_attempt_v2"
PAGE_SELECTION_SCHEMA = "cur0s_siyavula_external_page_selection_v2"
SELECTION_BINDING_SCHEMA = "cur0s_siyavula_selection_ready_binding_v2"
CHUNK_BYTES = 8 * 1024 * 1024
EXPECTED_TOTAL_CHUNK_REQUESTS = 79
HASH_READ_BYTES = 1024 * 1024
MAX_ARCHIVE_ENTRIES = 100_000
MAX_MEMBER_BYTES = 1024 * 1024 * 1024
MAX_COLLECTED_XML_BYTES = 32 * 1024 * 1024
MAX_AGGREGATE_XHTML_BYTES = 256 * 1024 * 1024
MAX_AGGREGATE_CSS_BYTES = 64 * 1024 * 1024
MAX_XHTML_MEMBERS = 20_000
ADMITTED_ZIP_COMPRESSION_METHODS = frozenset(
    {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
)
BACKOFF_SECONDS = (15 * 60, 60 * 60, 4 * 60 * 60, 12 * 60 * 60)
MAX_DISCOVERY_LEASE_SECONDS = 60 * 60
REQUEST_AND_TERMINAL_RESERVE_SECONDS = 16 * 60
CURL_MAX_TIME_SECONDS = 300
CURL_SUBPROCESS_TIMEOUT_SECONDS = 330
MIN_FREE_BYTES = 4 * 1024**3
THERMAL_SENTINELS_MILLIDEGREES_C = frozenset({-273_000})
COMPUTE_THERMAL_TYPE_RE = re.compile(
    r"(?i)^(?:cpu|soc|cluster|tsens)(?:[-_a-z0-9].*)?$"
)
EXCLUDED_THERMAL_TYPE_RE = re.compile(r"(?i)(?:pmic|pmih|charger|modem)")
THERMAL_POLICY = {
    "battery_path": "/sys/class/power_supply/battery/temp",
    "battery_threshold_millidegrees_c": 45_000,
    "compute_threshold_millidegrees_c": 85_000,
    "compute_type_selector": COMPUTE_THERMAL_TYPE_RE.pattern,
    "excluded_type_selector": EXCLUDED_THERMAL_TYPE_RE.pattern,
    "normal_PMIC_zones_explicitly_not_selected": True,
    "required_observation": "battery_supply",
    "sentinel_values_millidegrees_c": sorted(THERMAL_SENTINELS_MILLIDEGREES_C),
}
SAFE_COMPONENT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
XML_FORBIDDEN_RE = re.compile(r"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)
CONTENT_RANGE_RE = re.compile(r"bytes ([0-9]+)-([0-9]+)/([0-9]+)\Z")
PHONE_HOME = Path("/data/data/com.termux/files/home")
DEFAULT_DISCOVERY_ROOT = PHONE_HOME / "polymath_gemma4_e4b_identity_discovery_v3"
FORBIDDEN_CANDIDATE_ROOT = PHONE_HOME / "polymath_gemma4_e4b_frontier"
DEFAULT_CURL = Path("/data/data/com.termux/files/usr/bin/curl")
ABSENT_PYCACHE_PREFIX = PHONE_HOME / ".cur0s_siyavula_discovery_absent_pycache_v2"
HARNESS_EXECUTION_FD = 3
HARNESS_EXECUTION_PATH = f"/proc/self/fd/{HARNESS_EXECUTION_FD}"
EXPECTED_PHONE_MODEL = "NX789J"
EXPECTED_PHONE_DEVICE = "NX789J"
EXPECTED_PHONE_SOC = "SM8750"
EXPECTED_PHONE_MACHINE = "aarch64"
EXPECTED_EXTERNAL_ADB_SERIAL = "FY25013101C8"
EXPECTED_PHONE_SOC_MANUFACTURER = "QTI"
EXPECTED_PHONE_BOARD_PLATFORM = "sun"
EXPECTED_PHONE_PRODUCT_NAME = "NX789J-EEA"
EXPECTED_PHONE_VENDOR_DEVICE = "NX789J"
EXPECTED_PHONE_ABI = "arm64-v8a"
EXPECTED_ANDROID_RELEASE = "15"
EXPECTED_ANDROID_SDK = "35"
EXPECTED_TERMUX_UID_GID = 10_536
EXPECTED_KERNEL_RELEASE = "6.6.56-android15-8-g38447e018c92-ab12829524-4k"
EXPECTED_PYTHON_VERSION = "3.13.13"
EXPECTED_PYTHON_PREFIX = "/data/data/com.termux/files/usr"
EXPECTED_PYTHON_RESOLVED_PATH = f"{EXPECTED_PYTHON_PREFIX}/bin/python3.13"
EXPECTED_LINKER64_RESOLVED_PATH = "/apex/com.android.runtime/bin/linker64"
EXPECTED_PYTHON_ENVIRONMENT = {
    "ANDROID_ROOT": "/system",
    "HOME": str(PHONE_HOME),
    "LC_ALL": "C",
    "PATH": f"{EXPECTED_PYTHON_PREFIX}/bin:/system/bin",
    "PREFIX": EXPECTED_PYTHON_PREFIX,
}
EXPECTED_BUILD_FINGERPRINT = (
    "nubia/NX789J-EEA/NX789J:15/AQ3A.240812.002/"
    "20251031.123842:user/release-keys"
)
EXPECTED_BUILD_FINGERPRINT_SHA256 = (
    "sha256:ae59a6c6e85fdd4b2148912dafa60cca579f6af27832a696e1dabbce58d67402"
)
EXPECTED_INITIAL_SYS_PATH = (
    f"{EXPECTED_PYTHON_PREFIX}/lib/python313.zip",
    f"{EXPECTED_PYTHON_PREFIX}/lib/python3.13",
    f"{EXPECTED_PYTHON_PREFIX}/lib/python3.13/lib-dynload",
)
HARNESS_LAUNCH_CONTRACT = {
    "execution_fd": HARNESS_EXECUTION_FD,
    "execution_path": HARNESS_EXECUTION_PATH,
    "linker_path": "/system/bin/linker64",
    "python_path": f"{EXPECTED_PYTHON_PREFIX}/bin/python",
    "python_flags": ["-I", "-B", "-S"],
    "pycache_prefix": str(ABSENT_PYCACHE_PREFIX),
    "required_launcher_shape": (
        "open_sealed_harness_O_RDONLY_dup2_to_fd3_clear_CLOEXEC_then_exec_"
        "system_linker64_python_-IBS_-X_pycache_prefix_exact_/proc/self/fd/3"
    ),
}
EXPECTED_ORIG_ARGV_LAUNCH_PREFIX = [
    f"{EXPECTED_PYTHON_PREFIX}/bin/python",
    "-IBS",
    "-X",
    f"pycache_prefix={ABSENT_PYCACHE_PREFIX}",
    HARNESS_EXECUTION_PATH,
]
ORIGIN = "https://www.siyavula.com"
CATALOGUE_URL = f"{ORIGIN}/read"
TERMS_URL = f"{ORIGIN}/info/terms-and-conditions"
EPUB_CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"
OPF_NS = "http://www.idpf.org/2007/opf"
DC_NS = "http://purl.org/dc/elements/1.1/"
XHTML_NS = "http://www.w3.org/1999/xhtml"
EPUB_OPS_NS = "http://www.idpf.org/2007/ops"
MAX_XML_DEPTH = 96
MAX_XML_ELEMENTS = 250_000
MAX_XML_ATTRIBUTES_PER_ELEMENT = 64
MAX_XML_ATTRIBUTE_CHARACTERS = 64 * 1024
MAX_XML_TEXT_CHARACTERS = 256 * 1024 * 1024
MAX_HTML_DEPTH = 128
MAX_HTML_ELEMENTS = 250_000
MAX_HTML_ATTRIBUTES_PER_ELEMENT = 64
MAX_HTML_ATTRIBUTE_CHARACTERS = 64 * 1024
MAX_HTML_VISIBLE_TEXT_CHARACTERS = 32 * 1024 * 1024
MAX_HTML_CARD_TEXT_CHARACTERS = 32 * 1024
MAX_HTML_SCOPE_TEXT_CHARACTERS = 4 * 1024 * 1024
MAX_HTML_AGGREGATE_SCOPE_TEXT_CHARACTERS = 64 * 1024 * 1024
MAX_ANCHORS = 50_000
LOADER_LIST_LINE_RE = re.compile(
    rb"\t(?P<soname>[A-Za-z0-9_+.-]*) => "
    rb"(?P<path>\[vdso\]|/[^\x00\x09\x0a\x0d ]+) "
    rb"\(0x(?P<address>[0-9a-f]+)\)\Z"
)
CURL_LOADER_EXPECTED = (
    ("linux-vdso.so.1", "[vdso]", None, None),
    ("libcurl.so", f"{EXPECTED_PYTHON_PREFIX}/lib/libcurl.so", 884_688, "d654a8face01e897871d99a636d89e3c25dfcc0e2500f4ffe22e455984eb443c"),
    ("libz.so.1", f"{EXPECTED_PYTHON_PREFIX}/lib/libz.so.1.3.2", 72_232, "6d1a271adb9864fd66d696c746eac7a43faaa158b1370d32774ef73f1fe799ef"),
    ("libc.so", "/apex/com.android.runtime/lib64/bionic/libc.so", 1_143_072, "b4d95dc39a379dbe5049ce033f019b01a2f10dcf507562e83c72eef901d6ebcf"),
    ("libnghttp3.so", f"{EXPECTED_PYTHON_PREFIX}/lib/libnghttp3.so", 149_504, "d8a05e811b2fbf23fb48400a0f21e79ec5b3eec1126e67e1833f8bace3ff038e"),
    ("libngtcp2_crypto_ossl.so", f"{EXPECTED_PYTHON_PREFIX}/lib/libngtcp2_crypto_ossl.so", 43_616, "7dbe51f07d80a4385171ea44a96e2a46f80c827da897cda23dbe8978100082c8"),
    ("libngtcp2.so", f"{EXPECTED_PYTHON_PREFIX}/lib/libngtcp2.so", 342_128, "a12fc16d01ea00f0e94c59b8271df75dbd4b0a174ed5af1f7b9f7ae95a8c1158"),
    ("libnghttp2.so", f"{EXPECTED_PYTHON_PREFIX}/lib/libnghttp2.so", 154_080, "75f4514179c2f4e57ba1f1ff01dfc1ee49f83828bf83259ad84ed840c1d41d67"),
    ("libssh2.so", f"{EXPECTED_PYTHON_PREFIX}/lib/libssh2.so", 247_520, "3e72aa886e7a273bb3081bddda195144b5ce3c112e52d10417acd8315728e840"),
    ("libssl.so.3", f"{EXPECTED_PYTHON_PREFIX}/lib/libssl.so.3", 816_264, "9197a4a8bfb4239ee0c0fc475c2704cdb655caed2593863ef125808a3f3e75e8"),
    ("libcrypto.so.3", f"{EXPECTED_PYTHON_PREFIX}/lib/libcrypto.so.3", 4_611_704, "28534a11feb019f149032374c88d1c52f87baa241bc9ee7ab0bb1f3d24d21118"),
    ("libdl.so", "/apex/com.android.runtime/lib64/bionic/libdl.so", 50_760, "7abc47c96a4f49d52647e7f1d2045d3eb9ba4d9766c1d7f225e6aa229fa9f479"),
)
PYTHON_LOADER_EXPECTED = (
    ("linux-vdso.so.1", "[vdso]", None, None),
    ("", f"{EXPECTED_PYTHON_PREFIX}/lib/libandroid-posix-semaphore.so", 7_136, "adc7a3aa24f7e3baadc6149dea370bceeb11f058f19e22d8ca46e19f19e9e803"),
    ("libpython3.13.so", f"{EXPECTED_PYTHON_PREFIX}/lib/libpython3.13.so", 5_153_728, "7ca4f4f00ae2e1afde50bb3ce01926ec6edb582719c7731a416235833d4d2319"),
    ("libdl.so", "/apex/com.android.runtime/lib64/bionic/libdl.so", 50_760, "7abc47c96a4f49d52647e7f1d2045d3eb9ba4d9766c1d7f225e6aa229fa9f479"),
    ("liblog.so", "/system/lib64/liblog.so", 101_848, "b9d6a5f515686068e0a66d3d56c248701745f59273b20051a62bec4d44bedd9e"),
    ("libc.so", "/apex/com.android.runtime/lib64/bionic/libc.so", 1_143_072, "b4d95dc39a379dbe5049ce033f019b01a2f10dcf507562e83c72eef901d6ebcf"),
    ("libm.so", "/apex/com.android.runtime/lib64/bionic/libm.so", 249_192, "2a99c9ac7a12461663ec31b8d4ee3404ee99a1dca53f7c30b248bcccb155eefc"),
    ("libc++.so", "/system/lib64/libc++.so", 1_083_168, "794eb8fafd7be35da3725e9ec0b15189c6f4f2544f5b78afd8a647dde5b69195"),
)
CA_BUNDLE_PATH = Path(f"{EXPECTED_PYTHON_PREFIX}/etc/tls/cert.pem")
CA_BUNDLE_EXPECTED_BYTES = 189_462
CA_BUNDLE_EXPECTED_SHA256 = "86a1f3366afac7c6f8ae9f3c779ac221129328c43f0ab2b8817eb2f362a5025c"
CURL_EXPECTED_BYTES = 274_936
CURL_EXPECTED_SHA256 = "ae614749dea3653ec219919d852b1072030a0961de766610da21449f64a91624"
PYTHON_EXPECTED_BYTES = 4_728
PYTHON_EXPECTED_SHA256 = "1d3987c39c03b764d629a8c8c6fdc5979d8f8e28beb7193f312fc39d63b70404"
LINKER64_EXPECTED_BYTES = 2_160_952
LINKER64_EXPECTED_SHA256 = "6aa1b8bcf1da7e8b48f67f78eebaa2d9356c76ad3c9809bd5576b579907d7f9e"
TOOLBOX_EXPECTED_BYTES = 153_016
TOOLBOX_EXPECTED_SHA256 = "e336522f057ca8c094a24ecb467469313906d5eac62873b5e355e400fbe51600"


class DiscoveryError(RuntimeError):
    """A discovery invariant failed closed."""


class CircuitOpen(DiscoveryError):
    """The origin-wide circuit breaker forbids a request."""


@dataclass(frozen=True)
class SiyavulaSource:
    source_id: str
    url: str
    filename: str
    expected_bytes: int
    expected_etag: str
    expected_last_modified: str
    catalogue_subject: str
    catalogue_grade: int
    filename_subject_token: str
    filename_grade_token: str
    known_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _source(
    *,
    source_id: str,
    directory: str,
    filename: str,
    expected_bytes: int,
    expected_etag: str,
    expected_last_modified: str,
    catalogue_subject: str,
    catalogue_grade: int,
    filename_subject_token: str,
    known_sha256: str | None = None,
) -> SiyavulaSource:
    return SiyavulaSource(
        source_id=source_id,
        url=f"{ORIGIN}/downloads/books/{directory}/{filename}",
        filename=filename,
        expected_bytes=expected_bytes,
        expected_etag=expected_etag,
        expected_last_modified=expected_last_modified,
        catalogue_subject=catalogue_subject,
        catalogue_grade=catalogue_grade,
        filename_subject_token=filename_subject_token,
        filename_grade_token=f"Gr{catalogue_grade}",
        known_sha256=known_sha256,
    )


# Order closes the lower-grade prerequisite spine before exercising the known
# slow Grade-12 physical-sciences route.  Catalogue subject and filename token
# are deliberately separate for Grades 7--9.
SIYAVULA_SOURCES: tuple[SiyavulaSource, ...] = (
    _source(
        source_id="siyavula_natural_sciences_grade_4_cc_by",
        directory="science",
        filename="Gr4_NaturalSciences_Learner_Eng_CC-BY.epub",
        expected_bytes=40_926_007,
        expected_etag='"d8d7d076ea79476b84d5be0ffe1766bf-3"',
        expected_last_modified="Fri, 26 Jun 2026 16:57:41 GMT",
        catalogue_subject="Natural Sciences and Technology",
        catalogue_grade=4,
        filename_subject_token="NaturalSciences",
    ),
    _source(
        source_id="siyavula_natural_sciences_grade_5_cc_by",
        directory="science",
        filename="Gr5_NaturalSciences_Learner_Eng_CC-BY.epub",
        expected_bytes=46_100_488,
        expected_etag='"2a8c0146afc3c35effd6d26cff0dfa69-3"',
        expected_last_modified="Fri, 26 Jun 2026 16:57:43 GMT",
        catalogue_subject="Natural Sciences and Technology",
        catalogue_grade=5,
        filename_subject_token="NaturalSciences",
    ),
    _source(
        source_id="siyavula_natural_sciences_grade_6_cc_by",
        directory="science",
        filename="Gr6_NaturalSciences_Learner_Eng_CC-BY.epub",
        expected_bytes=31_912_860,
        expected_etag='"0c719d271daad6387bceca5f67b8a5f2-2"',
        expected_last_modified="Fri, 26 Jun 2026 16:57:42 GMT",
        catalogue_subject="Natural Sciences and Technology",
        catalogue_grade=6,
        filename_subject_token="NaturalSciences",
    ),
    _source(
        source_id="siyavula_natural_sciences_grade_7_cc_by",
        directory="science",
        filename="Gr7_PhysicalSciences_Learner_Eng_CC-BY.epub",
        expected_bytes=90_554_874,
        expected_etag='"faa667b1ba36190f8eaab737cd484802-6"',
        expected_last_modified="Fri, 26 Jun 2026 16:57:47 GMT",
        catalogue_subject="Natural Sciences",
        catalogue_grade=7,
        filename_subject_token="PhysicalSciences",
    ),
    _source(
        source_id="siyavula_natural_sciences_grade_8_cc_by",
        directory="science",
        filename="Gr8_PhysicalSciences_Learner_Eng_CC-BY.epub",
        expected_bytes=59_195_734,
        expected_etag='"5300f002ce3f4ff0a37617df2425036f-4"',
        expected_last_modified="Fri, 26 Jun 2026 16:57:49 GMT",
        catalogue_subject="Natural Sciences",
        catalogue_grade=8,
        filename_subject_token="PhysicalSciences",
    ),
    _source(
        source_id="siyavula_natural_sciences_grade_9_cc_by",
        directory="science",
        filename="Gr9_PhysicalSciences_Learner_Eng_CC-BY.epub",
        expected_bytes=71_408_313,
        expected_etag='"ece8c11956aafbc6638205d12c29411f-5"',
        expected_last_modified="Fri, 26 Jun 2026 16:57:46 GMT",
        catalogue_subject="Natural Sciences",
        catalogue_grade=9,
        filename_subject_token="PhysicalSciences",
    ),
    _source(
        source_id="siyavula_mathematics_grade_10_cc_by",
        directory="maths",
        filename="Gr10_Mathematics_Learner_Eng_CC-BY.epub",
        expected_bytes=49_009_925,
        expected_etag='"8bc76385d940a36dd75b9f9acd6a970c-3"',
        expected_last_modified="Fri, 26 Jun 2026 16:57:48 GMT",
        catalogue_subject="Mathematics",
        catalogue_grade=10,
        filename_subject_token="Mathematics",
        known_sha256="881f0968936e797a6f0fa4df305b92641c52add3812871ae39a791c2ee1e4a99",
    ),
    _source(
        source_id="siyavula_mathematics_grade_11_cc_by",
        directory="maths",
        filename="Gr11_Mathematics_Learner_Eng_CC-BY.epub",
        expected_bytes=34_751_539,
        expected_etag='"9f8bcfbe8eec4cedafbbfe5a13be79ef-3"',
        expected_last_modified="Fri, 26 Jun 2026 16:57:17 GMT",
        catalogue_subject="Mathematics",
        catalogue_grade=11,
        filename_subject_token="Mathematics",
        known_sha256="45be47abfdb209bad368522c49643dc431d285d6b0a8261da55d0b597c7db807",
    ),
    _source(
        source_id="siyavula_mathematics_grade_12_cc_by",
        directory="maths",
        filename="Gr12_Mathematics_Learner_Eng_CC-BY.epub",
        expected_bytes=40_361_251,
        expected_etag='"604c42c5c20042a278360f033499fea2-3"',
        expected_last_modified="Fri, 26 Jun 2026 16:57:26 GMT",
        catalogue_subject="Mathematics",
        catalogue_grade=12,
        filename_subject_token="Mathematics",
        known_sha256="0d7554f2d0df805133f3be38a3a5ffe20e5963fd5318e40e77c63490a413adc8",
    ),
    _source(
        source_id="siyavula_physical_sciences_grade_10_cc_by",
        directory="science",
        filename="Gr10_PhysicalSciences_Learner_Eng_CC-BY.epub",
        expected_bytes=31_675_351,
        expected_etag='"11e81361d79ff4a7370bb90d4c2704bd-2"',
        expected_last_modified="Fri, 26 Jun 2026 16:57:29 GMT",
        catalogue_subject="Physical Sciences",
        catalogue_grade=10,
        filename_subject_token="PhysicalSciences",
        known_sha256="366c2f0beb5d3c4cf0789e0dc49cd12dd07c20d47cd5c9e3e4dc5d1ca49ce3db",
    ),
    _source(
        source_id="siyavula_physical_sciences_grade_11_cc_by",
        directory="science",
        filename="Gr11_PhysicalSciences_Learner_Eng_CC-BY.epub",
        expected_bytes=47_417_044,
        expected_etag='"dc57cdc3110e200afcb325a3070de995-3"',
        expected_last_modified="Fri, 26 Jun 2026 16:57:49 GMT",
        catalogue_subject="Physical Sciences",
        catalogue_grade=11,
        filename_subject_token="PhysicalSciences",
        known_sha256="3d893a4364f52efe1991360302cfccb06030e03ad67d725867fb48f0f177a0f9",
    ),
    _source(
        source_id="siyavula_physical_sciences_grade_12_cc_by",
        directory="science",
        filename="Gr12_PhysicalSciences_Learner_Eng_CC-BY.epub",
        expected_bytes=78_477_236,
        expected_etag='"bb8df0c46219abbd746ad64a1a8aaf69-5"',
        expected_last_modified="Fri, 26 Jun 2026 16:57:47 GMT",
        catalogue_subject="Physical Sciences",
        catalogue_grade=12,
        filename_subject_token="PhysicalSciences",
    ),
)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def canonical_sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def require_exact_keys(value: Any, keys: set[str], *, role: str) -> Mapping[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise DiscoveryError(f"{role}_closed_schema_invalid")
    return value


def require_bounded_string(
    value: Any,
    *,
    role: str,
    maximum: int = 4096,
    allow_empty: bool = False,
) -> str:
    if (
        type(value) is not str
        or len(value) > maximum
        or (not allow_empty and not value)
    ):
        raise DiscoveryError(f"{role}_string_invalid")
    return value


def require_sha256(value: Any, *, role: str, prefixed: bool = True) -> str:
    text = require_bounded_string(value, role=role, maximum=71)
    digest = text.removeprefix("sha256:") if prefixed else text
    if SHA256_RE.fullmatch(digest) is None or (prefixed and not text.startswith("sha256:")):
        raise DiscoveryError(f"{role}_SHA256_invalid")
    return text


REGULAR_IDENTITY_KEYS = {
    "bytes",
    "ctime_ns",
    "device",
    "gid",
    "inode",
    "mode",
    "mtime_ns",
    "nlink",
    "path",
    "sha256",
    "uid",
}


def validate_regular_identity(value: Any, *, role: str) -> None:
    identity = require_exact_keys(value, REGULAR_IDENTITY_KEYS, role=role)
    for field in ("bytes", "ctime_ns", "device", "gid", "inode", "mtime_ns", "nlink", "uid"):
        if type(identity[field]) is not int or identity[field] < 0:
            raise DiscoveryError(f"{role}_{field}_invalid")
    if identity["bytes"] <= 0 or identity["nlink"] <= 0:
        raise DiscoveryError(f"{role}_file_identity_invalid")
    if re.fullmatch(r"[0-7]{4}", require_bounded_string(identity["mode"], role=role)) is None:
        raise DiscoveryError(f"{role}_mode_invalid")
    require_bounded_string(identity["path"], role=role, maximum=4096)
    require_sha256(identity["sha256"], role=role)


def validate_loader_closure(
    value: Any,
    *,
    role: str,
    expected: Sequence[tuple[str, str, int | None, str | None]],
) -> None:
    closure = require_exact_keys(
        value,
        {
            "address_normalization",
            "argv_shape",
            "closure_root_sha256",
            "entries",
            "entry_count",
            "linker64",
            "role",
            "scope",
            "target",
        },
        role=f"{role}_loader_closure",
    )
    body = {key: item for key, item in closure.items() if key != "closure_root_sha256"}
    if (
        closure["closure_root_sha256"] != canonical_sha256(body)
        or closure["role"] != role
        or closure["entry_count"] != len(expected)
        or closure["argv_shape"]
        != ["/system/bin/linker64", "--list", "/proc/self/fd/$TARGET_FD"]
        or closure["address_normalization"]
        != "remove_only_exact_terminal_lowercase_hex_ASLR_address_suffix"
        or closure["scope"]
        != "static_PT_INTERP_and_DT_NEEDED_resolution_only_no_dlopen_claim"
        or type(closure["entries"]) is not list
        or len(closure["entries"]) != len(expected)
    ):
        raise DiscoveryError(f"{role}_loader_closure_value_invalid")
    validate_regular_identity(closure["linker64"], role=f"{role}_closure_linker")
    validate_regular_identity(closure["target"], role=f"{role}_closure_target")
    for entry, expected_record in zip(closure["entries"], expected, strict=True):
        record = require_exact_keys(
            entry,
            {"identity", "normalized_line", "resolved_path", "soname"},
            role=f"{role}_loader_entry",
        )
        soname, path, expected_bytes, expected_sha256 = expected_record
        if (
            record["soname"] != soname
            or record["resolved_path"] != path
            or record["normalized_line"] != f"\t{soname} => {path}"
        ):
            raise DiscoveryError(f"{role}_loader_entry_value_invalid")
        if path == "[vdso]":
            if record["identity"] is not None:
                raise DiscoveryError(f"{role}_vdso_identity_invalid")
            continue
        validate_regular_identity(record["identity"], role=f"{role}_loader_DSO")
        if (
            record["identity"]["path"] != path
            or record["identity"]["bytes"] != expected_bytes
            or record["identity"]["sha256"] != f"sha256:{expected_sha256}"
        ):
            raise DiscoveryError(f"{role}_loader_DSO_value_invalid")


RUNTIME_IDENTITY_KEYS = {
    "build_fingerprint_sha256",
    "curl",
    "curl_CA_bundle",
    "curl_loader_closure",
    "harness",
    "launch_contract",
    "linker64",
    "machine",
    "observation_root_sha256",
    "phone_identity",
    "python",
    "python_loader_closure",
    "python_startup",
    "python_version",
    "schema_version",
    "sys_executable",
}


def validate_runtime_identity(value: Any) -> None:
    runtime = require_exact_keys(
        value,
        RUNTIME_IDENTITY_KEYS,
        role="runtime_identity",
    )
    core = {key: item for key, item in runtime.items() if key != "observation_root_sha256"}
    if (
        runtime["schema_version"]
        != "cur0s_siyavula_discovery_runtime_identity_v2"
        or runtime["build_fingerprint_sha256"] != EXPECTED_BUILD_FINGERPRINT_SHA256
        or runtime["machine"] != EXPECTED_PHONE_MACHINE
        or runtime["python_version"] != EXPECTED_PYTHON_VERSION
        or runtime["sys_executable"] != f"{EXPECTED_PYTHON_PREFIX}/bin/python"
        or runtime["launch_contract"] != HARNESS_LAUNCH_CONTRACT
        or runtime["observation_root_sha256"] != canonical_sha256(core)
    ):
        raise DiscoveryError("runtime_identity_value_invalid")
    validate_regular_identity(runtime["curl"], role="runtime_curl")
    validate_regular_identity(runtime["curl_CA_bundle"], role="runtime_CA_bundle")
    validate_regular_identity(runtime["python"], role="runtime_python")
    validate_regular_identity(runtime["linker64"], role="runtime_linker64")
    if (
        runtime["curl"]["path"] != str(DEFAULT_CURL)
        or runtime["curl"]["mode"] != "0700"
        or runtime["curl"]["uid"] != EXPECTED_TERMUX_UID_GID
        or runtime["curl"]["gid"] != EXPECTED_TERMUX_UID_GID
        or runtime["curl"]["bytes"] != CURL_EXPECTED_BYTES
        or runtime["curl"]["sha256"] != f"sha256:{CURL_EXPECTED_SHA256}"
        or runtime["python"]["path"] != EXPECTED_PYTHON_RESOLVED_PATH
        or runtime["python"]["mode"] != "0700"
        or runtime["python"]["uid"] != EXPECTED_TERMUX_UID_GID
        or runtime["python"]["gid"] != EXPECTED_TERMUX_UID_GID
        or runtime["python"]["bytes"] != PYTHON_EXPECTED_BYTES
        or runtime["python"]["sha256"] != f"sha256:{PYTHON_EXPECTED_SHA256}"
        or runtime["linker64"]["path"] != EXPECTED_LINKER64_RESOLVED_PATH
        or runtime["linker64"]["mode"] != "0755"
        or runtime["linker64"]["uid"] != 0
        or runtime["linker64"]["gid"] != 2000
        or runtime["linker64"]["bytes"] != LINKER64_EXPECTED_BYTES
        or runtime["linker64"]["sha256"]
        != f"sha256:{LINKER64_EXPECTED_SHA256}"
    ):
        raise DiscoveryError("runtime_executable_frozen_identity_invalid")
    validate_loader_closure(
        runtime["curl_loader_closure"],
        role="curl",
        expected=CURL_LOADER_EXPECTED,
    )
    validate_loader_closure(
        runtime["python_loader_closure"],
        role="python",
        expected=PYTHON_LOADER_EXPECTED,
    )
    if (
        runtime["curl_loader_closure"]["target"] != runtime["curl"]
        or runtime["python_loader_closure"]["target"] != runtime["python"]
        or runtime["curl_loader_closure"]["linker64"] != runtime["linker64"]
        or runtime["python_loader_closure"]["linker64"] != runtime["linker64"]
    ):
        raise DiscoveryError("runtime_loader_closure_identity_binding_invalid")
    if (
        runtime["curl_CA_bundle"]["path"] != str(CA_BUNDLE_PATH)
        or runtime["curl_CA_bundle"]["mode"] != "0600"
        or runtime["curl_CA_bundle"]["uid"] != EXPECTED_TERMUX_UID_GID
        or runtime["curl_CA_bundle"]["gid"] != EXPECTED_TERMUX_UID_GID
        or runtime["curl_CA_bundle"]["bytes"] != CA_BUNDLE_EXPECTED_BYTES
        or runtime["curl_CA_bundle"]["sha256"]
        != f"sha256:{CA_BUNDLE_EXPECTED_SHA256}"
    ):
        raise DiscoveryError("runtime_CA_bundle_value_invalid")
    harness = require_exact_keys(
        runtime["harness"],
        REGULAR_IDENTITY_KEYS | {"execution_fd", "execution_path"},
        role="runtime_harness",
    )
    validate_regular_identity(
        {key: harness[key] for key in REGULAR_IDENTITY_KEYS},
        role="runtime_harness",
    )
    if (
        harness["execution_fd"] != HARNESS_EXECUTION_FD
        or harness["execution_path"] != HARNESS_EXECUTION_PATH
        or harness["mode"] != "0400"
        or harness["nlink"] != 1
        or harness["uid"] != EXPECTED_TERMUX_UID_GID
        or harness["gid"] != EXPECTED_TERMUX_UID_GID
    ):
        raise DiscoveryError("runtime_harness_execution_binding_invalid")
    validate_phone_identity(runtime["phone_identity"])
    if runtime["phone_identity"]["getprop"]["linker64"] != runtime["linker64"]:
        raise DiscoveryError("runtime_phone_linker_identity_binding_invalid")
    validate_python_startup(runtime["python_startup"])


def validate_phone_identity(value: Any) -> None:
    phone = require_exact_keys(
        value,
        {
            "ADB_serial_claimed_by_phone_process",
            "external_ADB_serial_is_launcher_evidence_only",
            "getprop",
            "observation_root_sha256",
            "process",
            "properties",
            "schema_version",
        },
        role="phone_identity",
    )
    core = {key: item for key, item in phone.items() if key != "observation_root_sha256"}
    if (
        phone["schema_version"] != "cur0s_siyavula_sovereign_phone_identity_v2"
        or phone["ADB_serial_claimed_by_phone_process"] is not False
        or phone["external_ADB_serial_is_launcher_evidence_only"] is not True
        or phone["observation_root_sha256"] != canonical_sha256(core)
    ):
        raise DiscoveryError("phone_identity_value_invalid")
    getprop = require_exact_keys(
        phone["getprop"],
        {
            "execution_shape",
            "linker64",
            "linker64_invocation_path",
            "symlink",
            "toolbox",
        },
        role="phone_getprop",
    )
    validate_regular_identity(getprop["linker64"], role="phone_getprop_linker")
    validate_regular_identity(getprop["toolbox"], role="phone_getprop_toolbox")
    symlink = require_exact_keys(
        getprop["symlink"],
        {"gid", "mode", "path", "target", "uid"},
        role="phone_getprop_symlink",
    )
    if (
        getprop["execution_shape"]
        != "canonical_root_owned_system_getprop_symlink_to_toolbox_held_toolbox_and_linker_pre_post"
        or symlink["path"] != "/system/bin/getprop"
        or symlink["target"] != "toolbox"
        or symlink["mode"] != "0755"
        or symlink["uid"] != 0
        or symlink["gid"] != 2000
        or getprop["toolbox"]["path"] != "/system/bin/toolbox"
        or getprop["toolbox"]["mode"] != "0755"
        or getprop["toolbox"]["uid"] != 0
        or getprop["toolbox"]["gid"] != 2000
        or getprop["toolbox"]["bytes"] != TOOLBOX_EXPECTED_BYTES
        or getprop["toolbox"]["sha256"] != f"sha256:{TOOLBOX_EXPECTED_SHA256}"
        or getprop["linker64_invocation_path"] != "/system/bin/linker64"
        or getprop["linker64"]["path"] != EXPECTED_LINKER64_RESOLVED_PATH
        or getprop["linker64"]["mode"] != "0755"
        or getprop["linker64"]["uid"] != 0
        or getprop["linker64"]["gid"] != 2000
        or getprop["linker64"]["bytes"] != LINKER64_EXPECTED_BYTES
        or getprop["linker64"]["sha256"]
        != f"sha256:{LINKER64_EXPECTED_SHA256}"
    ):
        raise DiscoveryError("phone_getprop_value_invalid")
    properties = require_exact_keys(
        phone["properties"],
        {
            "ABI",
            "android_release",
            "android_SDK",
            "board_platform",
            "boot_verified_state",
            "device",
            "fingerprint",
            "flash_locked",
            "model",
            "phone_process_boot_serial",
            "phone_process_serial",
            "product_name",
            "SoC_manufacturer",
            "SoC_model",
            "thermal_battery_control",
            "thermal_policy_thresholds",
            "thermal_service_state",
            "vendor_device",
        },
        role="phone_properties",
    )
    expected_properties = {
        "ABI": EXPECTED_PHONE_ABI,
        "android_release": EXPECTED_ANDROID_RELEASE,
        "android_SDK": EXPECTED_ANDROID_SDK,
        "board_platform": EXPECTED_PHONE_BOARD_PLATFORM,
        "boot_verified_state": "green",
        "device": EXPECTED_PHONE_DEVICE,
        "fingerprint": EXPECTED_BUILD_FINGERPRINT,
        "flash_locked": "1",
        "model": EXPECTED_PHONE_MODEL,
        "phone_process_boot_serial": "",
        "phone_process_serial": "",
        "product_name": EXPECTED_PHONE_PRODUCT_NAME,
        "SoC_manufacturer": EXPECTED_PHONE_SOC_MANUFACTURER,
        "SoC_model": EXPECTED_PHONE_SOC,
        "thermal_battery_control": "true",
        "thermal_policy_thresholds": "skin,54,battery,45",
        "thermal_service_state": "running",
        "vendor_device": EXPECTED_PHONE_VENDOR_DEVICE,
    }
    if dict(properties) != expected_properties:
        raise DiscoveryError("phone_properties_value_invalid")
    process = require_exact_keys(
        phone["process"],
        {
            "environment",
            "gid",
            "HOME",
            "kernel_release",
            "machine",
            "platform_release",
            "PREFIX",
            "python_version",
            "uid",
        },
        role="phone_process",
    )
    if dict(process) != {
        "environment": EXPECTED_PYTHON_ENVIRONMENT,
        "gid": EXPECTED_TERMUX_UID_GID,
        "HOME": str(PHONE_HOME),
        "kernel_release": EXPECTED_KERNEL_RELEASE,
        "machine": EXPECTED_PHONE_MACHINE,
        "platform_release": "15",
        "PREFIX": EXPECTED_PYTHON_PREFIX,
        "python_version": EXPECTED_PYTHON_VERSION,
        "uid": EXPECTED_TERMUX_UID_GID,
    }:
        raise DiscoveryError("phone_process_value_invalid")


def validate_python_startup(value: Any) -> None:
    startup = require_exact_keys(
        value,
        {
            "absent_pycache_prefix",
            "absent_pycache_prefix_exists",
            "argv0",
            "dont_write_bytecode",
            "ignore_environment",
            "initial_sys_path",
            "isolated",
            "launch_mode",
            "loaded_module_origins",
            "loaded_module_origins_sha256",
            "no_site",
            "no_user_site",
            "orig_argv_launch_prefix",
            "pycache_prefix",
            "python313_zip_absent",
            "safe_path",
            "sanitized_sys_path",
            "source_only_stdlib_observed_root_sha256",
            "timestamp_or_sourceless_pyc_consumed",
            "xoptions",
        },
        role="python_startup",
    )
    modules = startup["loaded_module_origins"]
    if type(modules) is not list or not 1 <= len(modules) <= 1024:
        raise DiscoveryError("python_loaded_module_roster_invalid")
    for record in modules:
        module = require_exact_keys(
            record,
            {
                "cached",
                "loader_type",
                "module",
                "origin",
                "origin_bytes",
                "origin_sha256",
            },
            role="python_loaded_module",
        )
        require_bounded_string(module["module"], role="python_module", maximum=512)
        require_bounded_string(
            module["loader_type"], role="python_loader", maximum=256
        )
        for field in ("cached", "origin"):
            if module[field] is not None:
                require_bounded_string(
                    module[field], role=f"python_module_{field}", maximum=4096
                )
        if module["origin_sha256"] is not None:
            require_sha256(module["origin_sha256"], role="python_module_origin")
            if type(module["origin_bytes"]) is not int or module["origin_bytes"] < 0:
                raise DiscoveryError("python_module_origin_bytes_invalid")
        elif module["origin_bytes"] is not None:
            raise DiscoveryError("python_module_origin_nullability_invalid")
        origin = module["origin"]
        cached = module["cached"]
        if origin in {None, "built-in", "frozen"}:
            if (
                module["origin_sha256"] is not None
                or module["origin_bytes"] is not None
                or cached is not None
            ):
                raise DiscoveryError("python_frozen_module_origin_invalid")
            continue
        origin_path = Path(origin)
        allowed = any(
            root == origin_path or root in origin_path.parents
            for root in (
                Path(EXPECTED_INITIAL_SYS_PATH[1]),
                Path(EXPECTED_INITIAL_SYS_PATH[2]),
            )
        )
        if (
            not origin_path.is_absolute()
            or not allowed
            or "site-packages" in origin_path.parts
            or "__pycache__" in origin_path.parts
            or origin_path.suffix in {".pyc", ".pyo"}
            or module["origin_sha256"] is None
        ):
            raise DiscoveryError("python_source_module_origin_invalid")
        if cached is not None and (
            not cached.startswith(str(ABSENT_PYCACHE_PREFIX) + os.sep)
            or cached.endswith((".pyo",))
        ):
            raise DiscoveryError("python_source_module_cache_invalid")
    expected_values = {
        "absent_pycache_prefix": str(ABSENT_PYCACHE_PREFIX),
        "absent_pycache_prefix_exists": False,
        "argv0": HARNESS_EXECUTION_PATH,
        "isolated": 1,
        "no_site": 1,
        "no_user_site": 1,
        "dont_write_bytecode": 1,
        "ignore_environment": 1,
        "safe_path": True,
        "pycache_prefix": str(ABSENT_PYCACHE_PREFIX),
        "xoptions": {"pycache_prefix": str(ABSENT_PYCACHE_PREFIX)},
        "initial_sys_path": list(EXPECTED_INITIAL_SYS_PATH),
        "sanitized_sys_path": list(EXPECTED_INITIAL_SYS_PATH[1:]),
        "python313_zip_absent": True,
        "timestamp_or_sourceless_pyc_consumed": False,
        "launch_mode": (
            "held_fd3_python_-IBS_-X_exact_verified_absent_pycache_prefix"
        ),
        "orig_argv_launch_prefix": EXPECTED_ORIG_ARGV_LAUNCH_PREFIX,
    }
    observed_module_root = canonical_sha256(modules)
    if (
        startup["loaded_module_origins_sha256"] != observed_module_root
        or startup["source_only_stdlib_observed_root_sha256"]
        != observed_module_root
    ):
        raise DiscoveryError("python_startup_value_invalid:module_root_self_check")
    for field, expected in expected_values.items():
        if startup[field] != expected:
            raise DiscoveryError(f"python_startup_value_invalid:{field}")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise DiscoveryError("UTC_timestamp_invalid") from None
    return parsed.replace(tzinfo=timezone.utc)


def source_roster_root() -> str:
    return canonical_sha256([source.to_dict() for source in SIYAVULA_SOURCES])


def validate_source_roster() -> None:
    if len(SIYAVULA_SOURCES) != 12:
        raise DiscoveryError("source_roster_cardinality_invalid")
    if sum(source.expected_bytes for source in SIYAVULA_SOURCES) != 621_790_622:
        raise DiscoveryError("source_roster_total_bytes_invalid")
    if sum(source.known_sha256 is not None for source in SIYAVULA_SOURCES) != 5:
        raise DiscoveryError("source_roster_known_sha256_cardinality_invalid")
    if (
        sum(
            (source.expected_bytes + CHUNK_BYTES - 1) // CHUNK_BYTES
            for source in SIYAVULA_SOURCES
        )
        != EXPECTED_TOTAL_CHUNK_REQUESTS
    ):
        raise DiscoveryError("source_roster_chunk_request_count_invalid")
    ids = [source.source_id for source in SIYAVULA_SOURCES]
    urls = [source.url for source in SIYAVULA_SOURCES]
    if len(ids) != len(set(ids)) or len(urls) != len(set(urls)):
        raise DiscoveryError("source_roster_duplicate")
    for source in SIYAVULA_SOURCES:
        if (
            SAFE_COMPONENT_RE.fullmatch(source.source_id) is None
            or source.url != f"{ORIGIN}{urlsplit(source.url).path}"
            or urlsplit(source.url).query
            or urlsplit(source.url).fragment
            or source.filename != PurePosixPath(urlsplit(source.url).path).name
            or source.expected_bytes <= 0
            or not source.expected_etag.startswith('"')
            or not source.expected_etag.endswith('"')
            or source.filename_grade_token != f"Gr{source.catalogue_grade}"
            or not source.filename.startswith(
                f"{source.filename_grade_token}_{source.filename_subject_token}_"
            )
            or not 1 <= source.catalogue_grade <= 12
            or (
                source.known_sha256 is not None
                and SHA256_RE.fullmatch(source.known_sha256) is None
            )
        ):
            raise DiscoveryError(f"source_roster_entry_invalid:{source.source_id}")


validate_source_roster()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def hash_stream(stream: BinaryIO) -> tuple[str, int]:
    digest = hashlib.sha256()
    consumed = 0
    while True:
        chunk = stream.read(HASH_READ_BYTES)
        if not chunk:
            break
        consumed += len(chunk)
        digest.update(chunk)
    return digest.hexdigest(), consumed


def stat_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_uid,
        value.st_gid,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def mutable_directory_identity(value: os.stat_result) -> tuple[int, ...]:
    """Bind a directory inode without rejecting its own child mutations."""
    if not stat.S_ISDIR(value.st_mode):
        raise DiscoveryError("mutable_directory_identity_not_directory")
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_uid,
        value.st_gid,
    )


def hash_file(path: Path) -> tuple[str, int]:
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except OSError as error:
        raise DiscoveryError(f"file_open_failed:{path.name}") from error
    try:
        before = os.fstat(fd)
        path_before = os.stat(path, follow_symlinks=False)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat_identity(before) != stat_identity(path_before)
        ):
            raise DiscoveryError(f"file_not_regular:{path.name}")
        with os.fdopen(os.dup(fd), "rb", closefd=True) as stream:
            digest, consumed = hash_stream(stream)
        after = os.fstat(fd)
        path_after = os.stat(path, follow_symlinks=False)
        if (
            stat_identity(before) != stat_identity(after)
            or stat_identity(after) != stat_identity(path_after)
            or consumed != before.st_size
        ):
            raise DiscoveryError(f"file_changed_while_hashing:{path.name}")
        return digest, consumed
    finally:
        os.close(fd)


def fsync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def ensure_private_directory(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    value = path.lstat()
    if (
        not stat.S_ISDIR(value.st_mode)
        or stat.S_IMODE(value.st_mode) != 0o700
        or value.st_uid != os.geteuid()
        or value.st_gid != os.getegid()
    ):
        raise DiscoveryError(f"private_directory_identity_invalid:{path.name}")


def _write_temp_file(directory: Path, payload: bytes, mode: int) -> Path:
    ensure_private_directory(directory)
    temporary = directory / f".tmp-{os.getpid()}-{uuid.uuid4().hex}"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC
    fd = os.open(temporary, flags, mode)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise DiscoveryError("atomic_write_zero_length")
            view = view[written:]
        os.fsync(fd)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
    finally:
        os.close(fd)
    return temporary


def publish_immutable_bytes(path: Path, payload: bytes, *, mode: int = 0o400) -> None:
    if path.exists() or path.is_symlink():
        raise DiscoveryError(f"immutable_artifact_already_exists:{path.name}")
    ensure_private_directory(path.parent)
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW
    fd = -1
    try:
        fd = os.open(path, flags, mode)
        initial = os.fstat(fd)
        if (
            not stat.S_ISREG(initial.st_mode)
            or initial.st_nlink != 1
            or initial.st_uid != os.geteuid()
            or initial.st_gid != os.getegid()
        ):
            raise DiscoveryError(f"immutable_artifact_created_inode_invalid:{path.name}")
        view = memoryview(payload)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise DiscoveryError("atomic_write_zero_length")
            view = view[written:]
        os.fsync(fd)
        os.fchmod(fd, mode)
        os.fsync(fd)
        observed = bytearray()
        offset = 0
        while offset < len(payload):
            chunk = os.pread(fd, min(HASH_READ_BYTES, len(payload) - offset), offset)
            if not chunk:
                raise DiscoveryError(f"immutable_artifact_short_read:{path.name}")
            observed.extend(chunk)
            offset += len(chunk)
        final = os.fstat(fd)
        entry = os.stat(path, follow_symlinks=False)
        if (
            bytes(observed) != payload
            or stat_identity(initial)[:2] != stat_identity(final)[:2]
            or stat_identity(final) != stat_identity(entry)
        ):
            raise DiscoveryError(f"immutable_artifact_readback_invalid:{path.name}")
        fsync_directory(path.parent)
    except FileExistsError:
        raise DiscoveryError(f"immutable_artifact_race:{path.name}") from None
    finally:
        if fd >= 0:
            os.close(fd)
    value = path.lstat()
    if (
        not stat.S_ISREG(value.st_mode)
        or stat.S_IMODE(value.st_mode) != mode
        or value.st_nlink != 1
        or value.st_uid != os.geteuid()
        or value.st_gid != os.getegid()
    ):
        raise DiscoveryError(f"immutable_artifact_seal_invalid:{path.name}")


def publish_immutable_json(path: Path, value: Mapping[str, Any]) -> str:
    payload = canonical_json_bytes(dict(value)) + b"\n"
    publish_immutable_bytes(path, payload)
    return "sha256:" + sha256_bytes(payload)


def replace_mutable_json(path: Path, value: Mapping[str, Any]) -> str:
    payload = canonical_json_bytes(dict(value)) + b"\n"
    temporary = _write_temp_file(path.parent, payload, 0o600)
    os.replace(temporary, path)
    fsync_directory(path.parent)
    return "sha256:" + sha256_bytes(payload)


def read_canonical_json(
    path: Path,
    *,
    schema: str,
    max_bytes: int = 4 * 1024 * 1024,
    immutable: bool = True,
) -> dict[str, Any]:
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except OSError as error:
        raise DiscoveryError(f"JSON_artifact_open_failed:{path.name}") from error
    try:
        before = os.fstat(fd)
        path_before = os.stat(path, follow_symlinks=False)
        expected_mode = 0o400 if immutable else 0o600
        if (
            not stat.S_ISREG(before.st_mode)
            or stat_identity(before) != stat_identity(path_before)
            or stat.S_IMODE(before.st_mode) != expected_mode
            or before.st_nlink != 1
            or before.st_uid != os.geteuid()
            or before.st_gid != os.getegid()
        ):
            raise DiscoveryError(f"JSON_artifact_metadata_invalid:{path.name}")
        if before.st_size <= 1 or before.st_size > max_bytes:
            raise DiscoveryError(f"JSON_artifact_size_invalid:{path.name}")
        payload = bytearray()
        while len(payload) <= max_bytes:
            chunk = os.read(fd, min(HASH_READ_BYTES, max_bytes + 1 - len(payload)))
            if not chunk:
                break
            payload.extend(chunk)
        after = os.fstat(fd)
        path_after = os.stat(path, follow_symlinks=False)
        if (
            stat_identity(before) != stat_identity(after)
            or stat_identity(after) != stat_identity(path_after)
            or len(payload) != before.st_size
        ):
            raise DiscoveryError(f"JSON_artifact_changed:{path.name}")
    finally:
        os.close(fd)
    payload_bytes = bytes(payload)
    digest = sha256_bytes(payload_bytes)
    size = len(payload_bytes)
    if size <= 1 or size > max_bytes:
        raise DiscoveryError(f"JSON_artifact_size_invalid:{path.name}")
    try:
        value = json.loads(payload_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise DiscoveryError(f"JSON_artifact_invalid:{path.name}") from None
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != schema
        or canonical_json_bytes(value) + b"\n" != payload_bytes
        or sha256_bytes(payload_bytes) != digest
    ):
        raise DiscoveryError(f"JSON_artifact_noncanonical:{path.name}")
    return value


def require_phone_runtime(curl_path: Path) -> None:
    if (
        sys.platform != "android"
        or os.uname().machine != EXPECTED_PHONE_MACHINE
        or not PHONE_HOME.is_dir()
        or not Path("/system/bin/getprop").is_file()
        or curl_path != DEFAULT_CURL
        or not curl_path.is_file()
    ):
        raise DiscoveryError("phone_only_runtime_required")


def validate_discovery_root(
    root: Path, *, require_phone_home: bool = True
) -> Path:
    if not root.is_absolute():
        raise DiscoveryError("discovery_root_must_be_absolute")
    resolved = root.resolve(strict=False)
    forbidden = FORBIDDEN_CANDIDATE_ROOT.resolve(strict=False)
    if resolved == forbidden or forbidden in resolved.parents or resolved in forbidden.parents:
        raise DiscoveryError("candidate_transaction_root_forbidden")
    if require_phone_home:
        try:
            phone_home = PHONE_HOME.resolve(strict=True)
            resolved_parent = root.parent.resolve(strict=True)
            resolved_parent.relative_to(phone_home)
        except (FileNotFoundError, ValueError):
            raise DiscoveryError("production_discovery_root_outside_phone_home") from None
        if root.name in {"", ".", ".."} or resolved != resolved_parent / root.name:
            raise DiscoveryError("production_discovery_root_resolution_invalid")
    return resolved


def validate_phone_private_ancestry(root: Path) -> None:
    try:
        phone_home = PHONE_HOME.resolve(strict=True)
        resolved = root.resolve(strict=True)
        relative = resolved.relative_to(phone_home)
    except (FileNotFoundError, ValueError):
        raise DiscoveryError("production_discovery_root_outside_phone_home") from None
    cursor = phone_home
    for part in relative.parts:
        cursor = cursor / part
        value = cursor.lstat()
        if (
            not stat.S_ISDIR(value.st_mode)
            or stat.S_ISLNK(value.st_mode)
            or stat.S_IMODE(value.st_mode) != 0o700
            or value.st_uid != os.geteuid()
            or value.st_gid != os.getegid()
        ):
            raise DiscoveryError("phone_private_root_ancestry_invalid")


def create_mutable_lock(path: Path, payload: bytes) -> None:
    if os.path.lexists(path):
        value = path.lstat()
        if (
            not stat.S_ISREG(value.st_mode)
            or stat.S_IMODE(value.st_mode) != 0o600
            or value.st_nlink != 1
            or value.st_uid != os.geteuid()
            or value.st_gid != os.getegid()
        ):
            raise DiscoveryError("mutable_lock_identity_invalid")
        return
    try:
        publish_immutable_bytes(path, payload, mode=0o600)
    except DiscoveryError as error:
        if str(error).startswith("immutable_artifact_race:"):
            raise DiscoveryError("mutable_lock_publication_race") from None
        raise


def regular_file_identity(path: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    value = resolved.stat()
    digest, size = hash_file(resolved)
    if size != value.st_size:
        raise DiscoveryError("runtime_artifact_size_changed")
    return {
        "bytes": size,
        "ctime_ns": value.st_ctime_ns,
        "device": value.st_dev,
        "gid": value.st_gid,
        "inode": value.st_ino,
        "mode": f"{stat.S_IMODE(value.st_mode):04o}",
        "mtime_ns": value.st_mtime_ns,
        "nlink": value.st_nlink,
        "path": str(resolved),
        "sha256": "sha256:" + digest,
        "uid": value.st_uid,
    }


def held_harness_identity(fd: int = HARNESS_EXECUTION_FD) -> dict[str, Any]:
    if fd != HARNESS_EXECUTION_FD:
        raise DiscoveryError("held_harness_FD_number_invalid")
    try:
        descriptor_flags = fcntl.fcntl(fd, fcntl.F_GETFD)
        before = os.fstat(fd)
        target_before = os.readlink(HARNESS_EXECUTION_PATH)
    except OSError as error:
        raise DiscoveryError("held_harness_FD_unavailable") from error
    require_sealed_regular_stat(before, role="held_harness")
    if (
        descriptor_flags & fcntl.FD_CLOEXEC
        or before.st_size <= 0
        or not target_before.startswith("/")
        or target_before.endswith(" (deleted)")
    ):
        raise DiscoveryError("held_harness_FD_contract_invalid")
    digest = hashlib.sha256()
    consumed = 0
    while consumed < before.st_size:
        payload = os.pread(fd, min(HASH_READ_BYTES, before.st_size - consumed), consumed)
        if not payload:
            raise DiscoveryError("held_harness_FD_short_read")
        consumed += len(payload)
        digest.update(payload)
    after = os.fstat(fd)
    try:
        target_after = os.readlink(HARNESS_EXECUTION_PATH)
    except OSError as error:
        raise DiscoveryError("held_harness_FD_unavailable") from error
    if (
        stat_identity(before) != stat_identity(after)
        or consumed != before.st_size
        or target_after != target_before
    ):
        raise DiscoveryError("held_harness_FD_changed")
    return {
        "bytes": consumed,
        "ctime_ns": after.st_ctime_ns,
        "device": after.st_dev,
        "execution_fd": fd,
        "execution_path": HARNESS_EXECUTION_PATH,
        "gid": after.st_gid,
        "inode": after.st_ino,
        "mode": f"{stat.S_IMODE(after.st_mode):04o}",
        "mtime_ns": after.st_mtime_ns,
        "nlink": after.st_nlink,
        "path": target_after,
        "sha256": "sha256:" + digest.hexdigest(),
        "uid": after.st_uid,
    }


def observe_runtime_identity(
    *,
    curl_path: Path,
    build_fingerprint: str,
    harness_identity: Mapping[str, Any],
    phone_identity: Mapping[str, Any],
    startup_identity: Mapping[str, Any] | None = None,
    python_path: Path | None = None,
) -> dict[str, Any]:
    fingerprint_sha256 = "sha256:" + sha256_bytes(build_fingerprint.encode("utf-8"))
    if (
        build_fingerprint != EXPECTED_BUILD_FINGERPRINT
        or fingerprint_sha256 != EXPECTED_BUILD_FINGERPRINT_SHA256
    ):
        raise DiscoveryError("build_fingerprint_observation_invalid")
    python_target = python_path or Path(sys.executable)
    curl_guard = open_loader_closure(
        curl_path,
        role="curl",
        expected=CURL_LOADER_EXPECTED,
    )
    try:
        python_guard = open_loader_closure(
            python_target,
            role="python",
            expected=PYTHON_LOADER_EXPECTED,
        )
        try:
            CA_fd, CA_before, CA_identity = open_CA_bundle()
            try:
                curl_guard.revalidate()
                python_guard.revalidate()
                revalidate_held_executable(CA_fd, CA_before, CA_BUNDLE_PATH)
                identity = {
                    "build_fingerprint_sha256": fingerprint_sha256,
                    "curl": regular_file_identity(curl_path),
                    "curl_CA_bundle": CA_identity,
                    "curl_loader_closure": curl_guard.closure,
                    "harness": dict(harness_identity),
                    "launch_contract": HARNESS_LAUNCH_CONTRACT,
                    "linker64": regular_file_identity(Path("/system/bin/linker64")),
                    "machine": platform.machine(),
                    "phone_identity": dict(phone_identity),
                    "python": regular_file_identity(python_target),
                    "python_loader_closure": python_guard.closure,
                    "python_version": platform.python_version(),
                    "schema_version": "cur0s_siyavula_discovery_runtime_identity_v2",
                    "sys_executable": sys.executable,
                    "python_startup": dict(
                        startup_identity or observe_python_startup_state()
                    ),
                }
            finally:
                os.close(CA_fd)
        finally:
            python_guard.close()
    finally:
        curl_guard.close()
    result = {**identity, "observation_root_sha256": canonical_sha256(identity)}
    validate_runtime_identity(result)
    return result


def observe_python_startup_state() -> dict[str, Any]:
    module_origins: list[dict[str, Any]] = []
    for name, module in sorted(sys.modules.items()):
        spec = getattr(module, "__spec__", None)
        if spec is None:
            continue
        origin = getattr(spec, "origin", None)
        cached = getattr(spec, "cached", None)
        loader = getattr(spec, "loader", None)
        record = {
            "cached": cached,
            "loader_type": type(loader).__name__,
            "module": name,
            "origin": origin,
            "origin_bytes": None,
            "origin_sha256": None,
        }
        if isinstance(origin, str) and origin not in {"built-in", "frozen"}:
            origin_path = Path(origin)
            digest, size = hash_file(origin_path)
            record["origin_bytes"] = size
            record["origin_sha256"] = "sha256:" + digest
        module_origins.append(record)
    return {
        "absent_pycache_prefix": str(ABSENT_PYCACHE_PREFIX),
        "absent_pycache_prefix_exists": os.path.lexists(ABSENT_PYCACHE_PREFIX),
        "argv0": sys.argv[0],
        "dont_write_bytecode": sys.flags.dont_write_bytecode,
        "ignore_environment": sys.flags.ignore_environment,
        "isolated": sys.flags.isolated,
        "loaded_module_origins": module_origins,
        "loaded_module_origins_sha256": canonical_sha256(module_origins),
        "no_site": sys.flags.no_site,
        "no_user_site": sys.flags.no_user_site,
        "orig_argv": list(getattr(sys, "orig_argv", ())),
        "pycache_prefix": sys.pycache_prefix,
        "safe_path": sys.flags.safe_path,
        "source_only_stdlib_observed_root_sha256": canonical_sha256(module_origins),
        "sys_path": list(sys.path),
        "xoptions": dict(sys._xoptions),
    }


def require_python_startup_contract() -> dict[str, Any]:
    state = observe_python_startup_state()
    expected_prefix = str(ABSENT_PYCACHE_PREFIX)
    loaded = state["loaded_module_origins"]
    original_argv = state["orig_argv"]
    script_positions = [
        index
        for index, value in enumerate(original_argv)
        if value == HARNESS_EXECUTION_PATH
    ]
    pycache_argument_present = any(
        value == f"pycache_prefix={expected_prefix}" for value in original_argv
    )
    source_cache_invalid = any(
        (
            isinstance(record["origin"], str)
            and record["origin"].endswith((".pyc", ".pyo"))
        )
        or record["loader_type"] == "SourcelessFileLoader"
        or (
            isinstance(record["cached"], str)
            and (
                not record["cached"].startswith(expected_prefix + os.sep)
                or os.path.lexists(record["cached"])
            )
        )
        for record in loaded
    )
    allowed_source_roots = (
        Path(EXPECTED_INITIAL_SYS_PATH[1]),
        Path(EXPECTED_INITIAL_SYS_PATH[2]),
    )
    source_origin_invalid = False
    for record in loaded:
        origin = record["origin"]
        if origin in {None, "built-in", "frozen"}:
            continue
        if not isinstance(origin, str) or not Path(origin).is_absolute():
            source_origin_invalid = True
            break
        origin_path = Path(origin)
        try:
            origin_path.relative_to(allowed_source_roots[0])
        except ValueError:
            try:
                origin_path.relative_to(allowed_source_roots[1])
            except ValueError:
                source_origin_invalid = True
                break
        if (
            "site-packages" in origin_path.parts
            or "__pycache__" in origin_path.parts
            or origin_path.suffix in {".pyc", ".pyo"}
        ):
            source_origin_invalid = True
            break
    python_zip = Path(EXPECTED_INITIAL_SYS_PATH[0])
    if (
        sys.flags.isolated != 1
        or sys.flags.no_site != 1
        or sys.flags.no_user_site != 1
        or sys.flags.dont_write_bytecode != 1
        or sys.flags.ignore_environment != 1
        or not sys.flags.safe_path
        or sys.pycache_prefix != expected_prefix
        or sys._xoptions.get("pycache_prefix") != expected_prefix
        or os.path.lexists(ABSENT_PYCACHE_PREFIX)
        or sys.argv[0] != HARNESS_EXECUTION_PATH
        or len(script_positions) != 1
        or not pycache_argument_present
        or source_cache_invalid
        or source_origin_invalid
        or tuple(sys.path) != EXPECTED_INITIAL_SYS_PATH
        or os.path.lexists(python_zip)
    ):
        raise DiscoveryError("python_isolated_source_only_startup_contract_required")
    state["launch_mode"] = (
        "held_fd3_python_-IBS_-X_exact_verified_absent_pycache_prefix"
    )
    script_index = script_positions[0]
    state["orig_argv_launch_prefix"] = original_argv[: script_index + 1]
    del state["orig_argv"]
    state["initial_sys_path"] = state.pop("sys_path")
    sys.path[:] = list(EXPECTED_INITIAL_SYS_PATH[1:])
    state["sanitized_sys_path"] = list(sys.path)
    state["python313_zip_absent"] = True
    state["timestamp_or_sourceless_pyc_consumed"] = False
    return state


def initialize_epoch(
    root: Path,
    *,
    runtime_identity: Mapping[str, Any],
    now: datetime | None = None,
    require_phone_home: bool = True,
) -> Path:
    validate_runtime_identity(runtime_identity)
    root = validate_discovery_root(root, require_phone_home=require_phone_home)
    ensure_private_directory(root)
    if require_phone_home:
        validate_phone_private_ancestry(root)
    marker_path = root / "DISCOVERY_ROOT.json"
    marker = {
        "candidate_admission_claim": False,
        "legacy_artifact_adoption": "forbidden_without_v2_per_range_evidence",
        "phone_raw_custody_required": True,
        "production_phone_home_enforced": require_phone_home,
        "raw_egress_forbidden": True,
        "schema_version": DISCOVERY_SCHEMA,
        "source_roster_sha256": source_roster_root(),
    }
    if marker_path.exists():
        if read_canonical_json(marker_path, schema=DISCOVERY_SCHEMA) != marker:
            raise DiscoveryError("discovery_root_marker_mismatch")
    else:
        publish_immutable_json(marker_path, marker)
    epochs = root / "epochs"
    ensure_private_directory(epochs)
    timestamp = format_utc(now or utc_now()).replace("-", "").replace(":", "")
    epoch_id = f"{timestamp}_{uuid.uuid4().hex[:12]}_siyavula_identity_v2"
    epoch = epochs / epoch_id
    ensure_private_directory(epoch)
    for child in ("assembled", "identities", "sources"):
        ensure_private_directory(epoch / child)
    ensure_private_directory(root / "transport_tmp")
    manifest = {
        "aggregate_egress_only": True,
        "candidate_admission_claim": False,
        "chunk_bytes": CHUNK_BYTES,
        "created_at_utc": format_utc(now or utc_now()),
        "epoch_id": epoch_id,
        "old_unreceipted_prefixes_or_chunks_adopted": False,
        "origin": ORIGIN,
        "runtime_identity": dict(runtime_identity),
        "runtime_identity_sha256": canonical_sha256(dict(runtime_identity)),
        "schema_version": EPOCH_SCHEMA,
        "source_count": len(SIYAVULA_SOURCES),
        "source_roster_sha256": source_roster_root(),
    }
    publish_immutable_json(epoch / "epoch.json", manifest)
    create_mutable_lock(epoch / ".lock", b"identity-discovery-v2\n")
    create_mutable_lock(root / "origin_control" / ".origin.lock", b"origin-lock-v2\n")
    fsync_directory(epoch)
    return epoch


def validate_epoch(epoch: Path) -> tuple[Path, Path, dict[str, Any]]:
    epoch = epoch.resolve(strict=True)
    provisional_root = epoch.parent.parent
    marker = read_canonical_json(
        provisional_root / "DISCOVERY_ROOT.json", schema=DISCOVERY_SCHEMA
    )
    require_exact_keys(
        marker,
        {
            "candidate_admission_claim",
            "legacy_artifact_adoption",
            "phone_raw_custody_required",
            "production_phone_home_enforced",
            "raw_egress_forbidden",
            "schema_version",
            "source_roster_sha256",
        },
        role="discovery_root_marker",
    )
    phone_home_enforced = marker.get("production_phone_home_enforced")
    if (
        type(phone_home_enforced) is not bool
        or marker["candidate_admission_claim"] is not False
        or marker["legacy_artifact_adoption"]
        != "forbidden_without_v2_per_range_evidence"
        or marker["phone_raw_custody_required"] is not True
        or marker["raw_egress_forbidden"] is not True
    ):
        raise DiscoveryError("discovery_root_phone_home_policy_invalid")
    root = validate_discovery_root(
        provisional_root,
        require_phone_home=phone_home_enforced,
    )
    if phone_home_enforced:
        validate_phone_private_ancestry(root)
    manifest = read_canonical_json(epoch / "epoch.json", schema=EPOCH_SCHEMA)
    require_exact_keys(
        manifest,
        {
            "aggregate_egress_only",
            "candidate_admission_claim",
            "chunk_bytes",
            "created_at_utc",
            "epoch_id",
            "old_unreceipted_prefixes_or_chunks_adopted",
            "origin",
            "runtime_identity",
            "runtime_identity_sha256",
            "schema_version",
            "source_count",
            "source_roster_sha256",
        },
        role="epoch_manifest",
    )
    validate_runtime_identity(manifest.get("runtime_identity"))
    parse_utc(manifest["created_at_utc"])
    if (
        marker["source_roster_sha256"] != source_roster_root()
        or manifest["source_roster_sha256"] != source_roster_root()
        or manifest["chunk_bytes"] != CHUNK_BYTES
        or manifest["source_count"] != len(SIYAVULA_SOURCES)
        or manifest["origin"] != ORIGIN
        or manifest["aggregate_egress_only"] is not True
        or manifest["candidate_admission_claim"] is not False
        or SAFE_COMPONENT_RE.fullmatch(manifest["epoch_id"]) is None
        or not isinstance(manifest.get("runtime_identity"), dict)
        or manifest.get("runtime_identity_sha256")
        != canonical_sha256(manifest.get("runtime_identity"))
        or manifest["old_unreceipted_prefixes_or_chunks_adopted"] is not False
        or epoch.name != manifest["epoch_id"]
    ):
        raise DiscoveryError("epoch_manifest_mismatch")
    return root, epoch, manifest


def require_epoch_runtime(
    manifest: Mapping[str, Any], runtime_identity: Mapping[str, Any]
) -> None:
    validate_runtime_identity(runtime_identity)
    if (
        dict(runtime_identity) != manifest.get("runtime_identity")
        or canonical_sha256(dict(runtime_identity))
        != manifest.get("runtime_identity_sha256")
    ):
        raise DiscoveryError("epoch_runtime_identity_changed")


def require_lease_epoch(lease: Any, epoch: Path) -> None:
    lease_epoch = getattr(lease, "epoch", None)
    if not isinstance(lease_epoch, Path) or lease_epoch.resolve(strict=True) != epoch:
        raise DiscoveryError("discovery_lease_epoch_mismatch")


def validate_resource_observation_binding(
    epoch: Path,
    observation: tuple[str, str],
) -> tuple[str, str]:
    if type(observation) is not tuple or len(observation) != 2:
        raise DiscoveryError("resource_observation_binding_invalid")
    relative_path, expected_sha256 = observation
    require_sha256(expected_sha256, role="resource_observation_artifact")
    path = resolve_relative_artifact(epoch, relative_path)
    record = read_canonical_json(path, schema=RESOURCE_OBSERVATION_SCHEMA)
    require_exact_keys(
        record,
        {
            "elapsed_seconds_floor",
            "free_bytes",
            "lease_seconds",
            "minimum_free_bytes",
            "observed_at_utc",
            "phase",
            "remaining_seconds_floor",
            "schema_version",
            "thermal",
        },
        role="resource_observation",
    )
    thermal = require_exact_keys(
        record["thermal"],
        {"battery", "compute_zones", "policy", "PMIC_maximum_not_used_as_gate"},
        role="resource_observation_thermal",
    )
    battery = require_exact_keys(
        thermal["battery"],
        {"raw_value", "temperature_millidegrees_c"},
        role="resource_observation_battery",
    )
    compute = thermal["compute_zones"]
    if type(compute) is not list or len(compute) > 1024:
        raise DiscoveryError("resource_observation_compute_roster_invalid")
    for zone in compute:
        closed_zone = require_exact_keys(
            zone,
            {"temperature_millidegrees_c", "type"},
            role="resource_observation_compute_zone",
        )
        zone_type = require_bounded_string(
            closed_zone["type"],
            role="resource_observation_compute_type",
            maximum=256,
        )
        temperature = closed_zone["temperature_millidegrees_c"]
        if (
            type(temperature) is not int
            or COMPUTE_THERMAL_TYPE_RE.fullmatch(zone_type) is None
            or EXCLUDED_THERMAL_TYPE_RE.search(zone_type) is not None
            or temperature in THERMAL_SENTINELS_MILLIDEGREES_C
            or temperature >= THERMAL_POLICY["compute_threshold_millidegrees_c"]
        ):
            raise DiscoveryError("resource_observation_compute_value_invalid")
    if (
        type(record["elapsed_seconds_floor"]) is not int
        or record["elapsed_seconds_floor"] < 0
        or type(record["remaining_seconds_floor"]) is not int
        or record["remaining_seconds_floor"]
        <= REQUEST_AND_TERMINAL_RESERVE_SECONDS
        or type(record["lease_seconds"]) is not int
        or not REQUEST_AND_TERMINAL_RESERVE_SECONDS
        < record["lease_seconds"]
        <= MAX_DISCOVERY_LEASE_SECONDS
        or record["elapsed_seconds_floor"] + record["remaining_seconds_floor"]
        not in {record["lease_seconds"] - 1, record["lease_seconds"]}
        or type(record["free_bytes"]) is not int
        or record["free_bytes"] < record["minimum_free_bytes"]
        or record["minimum_free_bytes"] != MIN_FREE_BYTES + CHUNK_BYTES
        or thermal["policy"] != THERMAL_POLICY
        or thermal["PMIC_maximum_not_used_as_gate"] is not True
        or type(battery["raw_value"]) is not int
        or type(battery["temperature_millidegrees_c"]) is not int
        or battery["temperature_millidegrees_c"]
        != (
            battery["raw_value"] * 100
            if abs(battery["raw_value"]) < 1_000
            else battery["raw_value"]
        )
        or battery["temperature_millidegrees_c"]
        in THERMAL_SENTINELS_MILLIDEGREES_C
        or battery["temperature_millidegrees_c"]
        >= THERMAL_POLICY["battery_threshold_millidegrees_c"]
        or expected_sha256 != file_payload_sha256(path)
    ):
        raise DiscoveryError("resource_observation_value_invalid")
    parse_utc(record["observed_at_utc"])
    require_bounded_string(record["phase"], role="resource_observation_phase")
    return relative_path, expected_sha256


def _read_integer(path: Path) -> int:
    try:
        text = path.read_text(encoding="ascii").strip()
        return int(text)
    except (OSError, UnicodeDecodeError, ValueError):
        raise DiscoveryError(f"thermal_observation_unavailable:{path.name}") from None


def observe_admitted_thermal() -> dict[str, Any]:
    battery_path = Path(THERMAL_POLICY["battery_path"])
    battery_raw = _read_integer(battery_path)
    battery_millidegrees = battery_raw * 100 if abs(battery_raw) < 1_000 else battery_raw
    if battery_millidegrees in THERMAL_SENTINELS_MILLIDEGREES_C:
        raise DiscoveryError("battery_thermal_sentinel_rejected")
    compute: list[dict[str, Any]] = []
    for type_path in sorted(Path("/sys/class/thermal").glob("thermal_zone*/type")):
        try:
            zone_type = type_path.read_text(encoding="ascii").strip()
        except (OSError, UnicodeDecodeError):
            continue
        if (
            EXCLUDED_THERMAL_TYPE_RE.search(zone_type)
            or COMPUTE_THERMAL_TYPE_RE.fullmatch(zone_type) is None
        ):
            continue
        temperature_path = type_path.with_name("temp")
        try:
            value = _read_integer(temperature_path)
        except DiscoveryError:
            continue
        if value in THERMAL_SENTINELS_MILLIDEGREES_C:
            continue
        compute.append(
            {
                "temperature_millidegrees_c": value,
                "type": zone_type,
            }
        )
    if battery_millidegrees >= THERMAL_POLICY["battery_threshold_millidegrees_c"]:
        raise DiscoveryError("battery_thermal_threshold_reached")
    if any(
        record["temperature_millidegrees_c"]
        >= THERMAL_POLICY["compute_threshold_millidegrees_c"]
        for record in compute
    ):
        raise DiscoveryError("compute_thermal_threshold_reached")
    return {
        "battery": {
            "raw_value": battery_raw,
            "temperature_millidegrees_c": battery_millidegrees,
        },
        "compute_zones": compute,
        "policy": THERMAL_POLICY,
        "PMIC_maximum_not_used_as_gate": True,
    }


@dataclass
class DiscoveryLease:
    epoch: Path
    lease_seconds: int
    monotonic: Callable[[], float] = time.monotonic
    thermal_observer: Callable[[], dict[str, Any]] = observe_admitted_thermal

    def __post_init__(self) -> None:
        if (
            type(self.lease_seconds) is not int
            or not REQUEST_AND_TERMINAL_RESERVE_SECONDS < self.lease_seconds
            <= MAX_DISCOVERY_LEASE_SECONDS
        ):
            raise DiscoveryError("finite_discovery_lease_invalid")
        self.epoch = self.epoch.resolve(strict=True)
        _root, validated_epoch, manifest = validate_epoch(self.epoch)
        if validated_epoch != self.epoch or manifest["epoch_id"] != self.epoch.name:
            raise DiscoveryError("discovery_lease_epoch_mismatch")
        self._epoch_stat_identity = mutable_directory_identity(
            self.epoch.stat(follow_symlinks=False)
        )
        self._started = self.monotonic()

    def checkpoint(self, *, phase: str) -> dict[str, Any]:
        if (
            mutable_directory_identity(self.epoch.stat(follow_symlinks=False))
            != self._epoch_stat_identity
        ):
            raise DiscoveryError("discovery_lease_epoch_identity_changed")
        elapsed = self.monotonic() - self._started
        remaining = self.lease_seconds - elapsed
        if remaining <= REQUEST_AND_TERMINAL_RESERVE_SECONDS:
            raise DiscoveryError("finite_discovery_lease_reserve_reached")
        usage = shutil.disk_usage(self.epoch)
        if usage.free < MIN_FREE_BYTES + CHUNK_BYTES:
            raise DiscoveryError("identity_discovery_free_space_reserve_reached")
        thermal = self.thermal_observer()
        return {
            "elapsed_seconds_floor": int(elapsed),
            "free_bytes": usage.free,
            "lease_seconds": self.lease_seconds,
            "minimum_free_bytes": MIN_FREE_BYTES + CHUNK_BYTES,
            "observed_at_utc": format_utc(utc_now()),
            "phase": phase,
            "remaining_seconds_floor": int(remaining),
            "thermal": thermal,
        }

    def observe(self, *, phase: str) -> tuple[str, str]:
        record = {
            **self.checkpoint(phase=phase),
            "schema_version": RESOURCE_OBSERVATION_SCHEMA,
        }
        observations = self.epoch / "resource_observations"
        ensure_private_directory(observations)
        name = f"{format_utc(utc_now()).replace(':', '').replace('-', '')}-{uuid.uuid4().hex}.json"
        path = observations / name
        artifact_sha256 = publish_immutable_json(path, record)
        return relative_inside(self.epoch, path), artifact_sha256


@contextmanager
def epoch_lock(epoch: Path) -> Iterator[None]:
    fd = os.open(epoch / ".lock", os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise DiscoveryError("identity_discovery_epoch_already_locked") from None
    try:
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


@contextmanager
def origin_lock(root: Path) -> Iterator[None]:
    lock_path = circuit_path(root).parent / ".origin.lock"
    create_mutable_lock(lock_path, b"origin-lock-v2\n")
    fd = os.open(lock_path, os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        value = os.fstat(fd)
        if (
            not stat.S_ISREG(value.st_mode)
            or stat.S_IMODE(value.st_mode) != 0o600
            or value.st_nlink != 1
            or value.st_uid != os.geteuid()
            or value.st_gid != os.getegid()
        ):
            raise DiscoveryError("origin_lock_identity_invalid")
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def initial_circuit_state() -> dict[str, Any]:
    return {
        "consecutive_failures": 0,
        "event_sequence": 0,
        "last_event_sha256": None,
        "open_until_utc": None,
        "origin": ORIGIN,
        "schema_version": "cur0s_siyavula_origin_circuit_v2",
    }


def circuit_path(root: Path) -> Path:
    control = root / "origin_control"
    ensure_private_directory(control)
    ensure_private_directory(control / "events")
    return control / "circuit.json"


def read_circuit(root: Path) -> dict[str, Any]:
    path = circuit_path(root)
    if not path.exists():
        replace_mutable_json(path, initial_circuit_state())
    value = read_canonical_json(
        path,
        schema="cur0s_siyavula_origin_circuit_v2",
        immutable=False,
    )
    replayed = replay_circuit_events(root)
    if value != replayed:
        sequence = value.get("event_sequence")
        if type(sequence) is not int or not 0 <= sequence <= replayed["event_sequence"]:
            raise DiscoveryError("origin_circuit_state_event_chain_mismatch")
        checkpoint = replay_circuit_events(root, through_sequence=sequence)
        if value != checkpoint:
            raise DiscoveryError("origin_circuit_state_event_chain_mismatch")
        # Event publication is the write-ahead commit.  Restore a rolled-back
        # or crash-lagged mutable cache from the fully verified immutable chain.
        replace_mutable_json(path, replayed)
        return replayed
    return value


def replay_circuit_events(
    root: Path, *, through_sequence: int | None = None
) -> dict[str, Any]:
    state = initial_circuit_state()
    events_directory = circuit_path(root).parent / "events"
    event_paths = sorted(events_directory.glob("*.json"))
    if through_sequence is not None:
        if type(through_sequence) is not int or not 0 <= through_sequence <= len(
            event_paths
        ):
            raise DiscoveryError("origin_circuit_replay_bound_invalid")
        event_paths = event_paths[:through_sequence]
    for sequence, event_path in enumerate(event_paths, start=1):
        if re.fullmatch(rf"{sequence:08d}-[0-9a-f]{{32}}\.json", event_path.name) is None:
            raise DiscoveryError("origin_circuit_event_sequence_gap")
        event = read_canonical_json(
            event_path,
            schema="cur0s_siyavula_origin_circuit_event_v2",
        )
        event_sha256 = file_payload_sha256(event_path)
        if (
            event.get("event_sequence") != sequence
            or event.get("origin") != ORIGIN
            or event.get("previous_event_sha256") != state["last_event_sha256"]
        ):
            raise DiscoveryError("origin_circuit_event_chain_invalid")
        source_id = require_bounded_string(
            event.get("source_id"),
            role="origin_circuit_source",
            maximum=256,
        )
        chunk_index = event.get("chunk_index")
        source_by_id = {source.source_id: source for source in SIYAVULA_SOURCES}
        source = source_by_id.get(source_id)
        valid_external = source_id in {"external_catalogue", "external_terms"}
        if (
            type(chunk_index) is not int
            or (valid_external and chunk_index != -1)
            or (
                source is not None
                and not 0
                <= chunk_index
                < (source.expected_bytes + CHUNK_BYTES - 1) // CHUNK_BYTES
            )
            or (source is None and not valid_external)
        ):
            raise DiscoveryError("origin_circuit_source_chunk_invalid")
        require_sha256(event.get("attempt_sha256"), role="origin_circuit_attempt")
        event_kind = event.get("event_kind")
        if event_kind == "failure":
            require_exact_keys(
                event,
                {
                    "attempt_sha256",
                    "chunk_index",
                    "consecutive_failures",
                    "downloaded_bytes",
                    "event_kind",
                    "event_sequence",
                    "failure_reason",
                    "observed_at_utc",
                    "open_for_seconds",
                    "open_until_utc",
                    "origin",
                    "previous_event_sha256",
                    "request_intent_resource_observation_sha256",
                    "schema_version",
                    "source_id",
                    "zero_byte_failure_opened_circuit",
                },
                role="origin_circuit_failure_event",
            )
            expected_failures = state["consecutive_failures"] + 1
            expected_delay = BACKOFF_SECONDS[
                min(expected_failures - 1, len(BACKOFF_SECONDS) - 1)
            ]
            observed_at = parse_utc(event.get("observed_at_utc", ""))
            expected_open_until = format_utc(
                datetime.fromtimestamp(
                    observed_at.timestamp() + expected_delay,
                    timezone.utc,
                )
            )
            if (
                event.get("consecutive_failures") != expected_failures
                or event.get("open_for_seconds") != expected_delay
                or event.get("open_until_utc") != expected_open_until
                or type(event.get("downloaded_bytes")) is not int
                or event["downloaded_bytes"] < 0
                or event.get("zero_byte_failure_opened_circuit")
                is not (event["downloaded_bytes"] == 0)
                or event.get("failure_reason")
                != "durable_request_intent_unresolved_until_response"
                or event.get("downloaded_bytes") != 0
                or event.get("attempt_sha256")
                != canonical_sha256(
                    {
                        "chunk_index": event["chunk_index"],
                        "observed_at_utc": event["observed_at_utc"],
                        "resource_observation_sha256": event[
                            "request_intent_resource_observation_sha256"
                        ],
                        "source_id": event["source_id"],
                    }
                )
            ):
                raise DiscoveryError("origin_circuit_failure_event_invalid")
            require_sha256(
                event["request_intent_resource_observation_sha256"],
                role="origin_circuit_resource_observation",
            )
            state["consecutive_failures"] = expected_failures
            state["open_until_utc"] = expected_open_until
        elif event_kind == "success_reset":
            require_exact_keys(
                event,
                {
                    "attempt_sha256",
                    "chunk_index",
                    "consecutive_failures_before_reset",
                    "event_kind",
                    "event_sequence",
                    "observed_at_utc",
                    "open_until_before_reset",
                    "origin",
                    "previous_event_sha256",
                    "schema_version",
                    "source_id",
                },
                role="origin_circuit_success_event",
            )
            parse_utc(event.get("observed_at_utc", ""))
            if (
                state["consecutive_failures"] <= 0
                or event.get("consecutive_failures_before_reset")
                != state["consecutive_failures"]
                or event.get("open_until_before_reset") != state["open_until_utc"]
            ):
                raise DiscoveryError("origin_circuit_success_event_invalid")
            state["consecutive_failures"] = 0
            state["open_until_utc"] = None
        else:
            raise DiscoveryError("origin_circuit_event_kind_invalid")
        state["event_sequence"] = sequence
        state["last_event_sha256"] = event_sha256
    return state


def _publish_circuit_event(
    root: Path,
    current: Mapping[str, Any],
    event: Mapping[str, Any],
) -> str:
    sequence = current["event_sequence"] + 1
    if type(sequence) is not int or sequence <= 0:
        raise DiscoveryError("origin_circuit_state_invalid")
    event_name = f"{sequence:08d}-{uuid.uuid4().hex}.json"
    events = circuit_path(root).parent / "events"
    return publish_immutable_json(events / event_name, dict(event))


def ensure_circuit_allows(root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    state = read_circuit(root)
    open_until = state["open_until_utc"]
    if open_until is not None and (now or utc_now()) < parse_utc(open_until):
        raise CircuitOpen(f"origin_circuit_open_until:{open_until}")
    return state


def record_circuit_failure(
    root: Path,
    *,
    source_id: str,
    chunk_index: int,
    downloaded_bytes: int,
    reason: str,
    attempt_sha256: str,
    request_intent_resource_observation_sha256: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    instant = now or utc_now()
    current = read_circuit(root)
    failures = current["consecutive_failures"] + 1
    delay = BACKOFF_SECONDS[min(failures - 1, len(BACKOFF_SECONDS) - 1)]
    open_until = datetime.fromtimestamp(instant.timestamp() + delay, timezone.utc)
    event = {
        "attempt_sha256": attempt_sha256,
        "chunk_index": chunk_index,
        "consecutive_failures": failures,
        "downloaded_bytes": downloaded_bytes,
        "event_kind": "failure",
        "event_sequence": current["event_sequence"] + 1,
        "failure_reason": reason,
        "observed_at_utc": format_utc(instant),
        "open_for_seconds": delay,
        "open_until_utc": format_utc(open_until),
        "origin": ORIGIN,
        "previous_event_sha256": current["last_event_sha256"],
        "request_intent_resource_observation_sha256": (
            request_intent_resource_observation_sha256
        ),
        "schema_version": "cur0s_siyavula_origin_circuit_event_v2",
        "source_id": source_id,
        "zero_byte_failure_opened_circuit": downloaded_bytes == 0,
    }
    event_sha = _publish_circuit_event(root, current, event)
    updated = {
        "consecutive_failures": failures,
        "event_sequence": current["event_sequence"] + 1,
        "last_event_sha256": event_sha,
        "open_until_utc": format_utc(open_until),
        "origin": ORIGIN,
        "schema_version": "cur0s_siyavula_origin_circuit_v2",
    }
    replace_mutable_json(circuit_path(root), updated)
    return updated


def record_request_intent(
    root: Path,
    *,
    source_id: str,
    chunk_index: int,
    resource_observation_sha256: str,
    now: datetime,
) -> dict[str, Any]:
    intent = {
        "chunk_index": chunk_index,
        "observed_at_utc": format_utc(now),
        "resource_observation_sha256": resource_observation_sha256,
        "source_id": source_id,
    }
    return record_circuit_failure(
        root,
        source_id=source_id,
        chunk_index=chunk_index,
        downloaded_bytes=0,
        reason="durable_request_intent_unresolved_until_response",
        attempt_sha256=canonical_sha256(intent),
        request_intent_resource_observation_sha256=resource_observation_sha256,
        now=now,
    )


def record_circuit_success(
    root: Path,
    *,
    source_id: str,
    chunk_index: int,
    attempt_sha256: str,
    now: datetime | None = None,
) -> None:
    current = read_circuit(root)
    if current["consecutive_failures"] == 0 and current["open_until_utc"] is None:
        return
    event = {
        "attempt_sha256": attempt_sha256,
        "chunk_index": chunk_index,
        "consecutive_failures_before_reset": current["consecutive_failures"],
        "event_kind": "success_reset",
        "event_sequence": current["event_sequence"] + 1,
        "observed_at_utc": format_utc(now or utc_now()),
        "open_until_before_reset": current["open_until_utc"],
        "origin": ORIGIN,
        "previous_event_sha256": current["last_event_sha256"],
        "schema_version": "cur0s_siyavula_origin_circuit_event_v2",
        "source_id": source_id,
    }
    event_sha = _publish_circuit_event(root, current, event)
    updated = {
        "consecutive_failures": 0,
        "event_sequence": current["event_sequence"] + 1,
        "last_event_sha256": event_sha,
        "open_until_utc": None,
        "origin": ORIGIN,
        "schema_version": "cur0s_siyavula_origin_circuit_v2",
    }
    replace_mutable_json(circuit_path(root), updated)


@dataclass(frozen=True)
class RangeOutcome:
    exit_code: int
    headers: bytes
    body: bytes
    stderr: bytes
    tool_identity_sha256: str | None = None


RangeExecutor = Callable[[SiyavulaSource, int, int], RangeOutcome]


def expected_curl_execution_identity(runtime_identity: Mapping[str, Any]) -> str:
    return canonical_sha256(
        {
            "CA_bundle": runtime_identity["curl_CA_bundle"],
            "loader_closure": runtime_identity["curl_loader_closure"],
        }
    )


def open_held_executable(path: Path) -> tuple[int, os.stat_result, dict[str, Any]]:
    resolved = path.resolve(strict=True)
    fd = os.open(resolved, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        path_before = os.stat(resolved, follow_symlinks=False)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat_identity(before) != stat_identity(path_before)
        ):
            raise DiscoveryError("held_executable_preidentity_invalid")
        digest = hashlib.sha256()
        consumed = 0
        while consumed < before.st_size:
            payload = os.pread(
                fd,
                min(HASH_READ_BYTES, before.st_size - consumed),
                consumed,
            )
            if not payload:
                raise DiscoveryError("held_executable_short_read")
            consumed += len(payload)
            digest.update(payload)
        identity = {
            "bytes": consumed,
            "ctime_ns": before.st_ctime_ns,
            "device": before.st_dev,
            "gid": before.st_gid,
            "inode": before.st_ino,
            "mode": f"{stat.S_IMODE(before.st_mode):04o}",
            "mtime_ns": before.st_mtime_ns,
            "nlink": before.st_nlink,
            "path": str(resolved),
            "sha256": "sha256:" + digest.hexdigest(),
            "uid": before.st_uid,
        }
        return fd, before, identity
    except BaseException:
        os.close(fd)
        raise


def revalidate_held_executable(
    fd: int,
    before: os.stat_result,
    path: Path,
) -> None:
    after = os.fstat(fd)
    path_after = os.stat(path.resolve(strict=True), follow_symlinks=False)
    if (
        stat_identity(before) != stat_identity(after)
        or stat_identity(after) != stat_identity(path_after)
    ):
        raise DiscoveryError("held_executable_changed")


def parse_loader_list(payload: bytes) -> list[dict[str, str]]:
    if not payload or not payload.endswith(b"\n") or b"\r" in payload:
        raise DiscoveryError("loader_list_framing_invalid")
    lines = payload.split(b"\n")
    if lines[-1] != b"" or any(not line for line in lines[:-1]):
        raise DiscoveryError("loader_list_framing_invalid")
    records: list[dict[str, str]] = []
    for line in lines[:-1]:
        match = LOADER_LIST_LINE_RE.fullmatch(line)
        if match is None or int(match.group("address"), 16) == 0:
            raise DiscoveryError("loader_list_record_invalid")
        records.append(
            {
                "normalized_line": (
                    "\t"
                    + match.group("soname").decode("ascii")
                    + " => "
                    + match.group("path").decode("ascii")
                ),
                "resolved_path": match.group("path").decode("ascii"),
                "soname": match.group("soname").decode("ascii"),
            }
        )
    return records


@dataclass
class LoaderClosureGuard:
    closure: dict[str, Any]
    target_path: Path
    target_fd: int
    target_before: os.stat_result
    linker_path: Path
    linker_fd: int
    linker_before: os.stat_result
    dependency_holds: list[tuple[Path, int, os.stat_result]]

    def revalidate(self) -> None:
        revalidate_held_executable(
            self.target_fd,
            self.target_before,
            self.target_path,
        )
        revalidate_held_executable(
            self.linker_fd,
            self.linker_before,
            self.linker_path,
        )
        for path, fd, before in self.dependency_holds:
            revalidate_held_executable(fd, before, path)

    def close(self) -> None:
        for _path, fd, _before in self.dependency_holds:
            os.close(fd)
        os.close(self.target_fd)
        os.close(self.linker_fd)


def open_loader_closure(
    target_path: Path,
    *,
    role: str,
    expected: Sequence[tuple[str, str, int | None, str | None]],
) -> LoaderClosureGuard:
    target_fd, target_before, target_identity = open_held_executable(target_path)
    linker_path = Path("/system/bin/linker64")
    linker_fd, linker_before, linker_identity = open_held_executable(linker_path)
    dependency_holds: list[tuple[Path, int, os.stat_result]] = []
    try:
        argv = [str(linker_path), "--list", f"/proc/self/fd/{target_fd}"]
        result = subprocess.run(
            argv,
            check=False,
            close_fds=True,
            env={"ANDROID_ROOT": "/system", "LC_ALL": "C", "PATH": "/system/bin"},
            pass_fds=(target_fd, linker_fd),
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            timeout=30,
        )
        if result.returncode != 0 or result.stderr != b"":
            raise DiscoveryError(f"{role}_loader_list_execution_failed")
        parsed = parse_loader_list(result.stdout)
        if len(parsed) != len(expected):
            raise DiscoveryError(f"{role}_loader_list_cardinality_invalid")
        entries: list[dict[str, Any]] = []
        for record, expected_record in zip(parsed, expected, strict=True):
            soname, resolved_path, expected_bytes, expected_sha256 = expected_record
            if (
                record["soname"] != soname
                or record["resolved_path"] != resolved_path
            ):
                raise DiscoveryError(f"{role}_loader_list_exact_entry_mismatch")
            identity: dict[str, Any] | None = None
            if resolved_path != "[vdso]":
                dependency_path = Path(resolved_path)
                dependency_fd, dependency_before, identity = open_held_executable(
                    dependency_path
                )
                dependency_holds.append(
                    (dependency_path, dependency_fd, dependency_before)
                )
                if (
                    identity["bytes"] != expected_bytes
                    or identity["sha256"] != f"sha256:{expected_sha256}"
                ):
                    raise DiscoveryError(f"{role}_loader_dependency_identity_mismatch")
            entries.append({**record, "identity": identity})
        body = {
            "address_normalization": (
                "remove_only_exact_terminal_lowercase_hex_ASLR_address_suffix"
            ),
            "argv_shape": [str(linker_path), "--list", "/proc/self/fd/$TARGET_FD"],
            "entries": entries,
            "entry_count": len(entries),
            "linker64": linker_identity,
            "role": role,
            "scope": "static_PT_INTERP_and_DT_NEEDED_resolution_only_no_dlopen_claim",
            "target": target_identity,
        }
        closure = {**body, "closure_root_sha256": canonical_sha256(body)}
        guard = LoaderClosureGuard(
            closure=closure,
            target_path=target_path,
            target_fd=target_fd,
            target_before=target_before,
            linker_path=linker_path,
            linker_fd=linker_fd,
            linker_before=linker_before,
            dependency_holds=dependency_holds,
        )
        guard.revalidate()
        return guard
    except BaseException:
        for _path, fd, _before in dependency_holds:
            os.close(fd)
        os.close(target_fd)
        os.close(linker_fd)
        raise


def open_CA_bundle() -> tuple[int, os.stat_result, dict[str, Any]]:
    fd, before, identity = open_held_executable(CA_BUNDLE_PATH)
    if (
        identity["bytes"] != CA_BUNDLE_EXPECTED_BYTES
        or identity["sha256"] != f"sha256:{CA_BUNDLE_EXPECTED_SHA256}"
        or identity["mode"] != "0600"
        or identity["uid"] != EXPECTED_TERMUX_UID_GID
        or identity["gid"] != EXPECTED_TERMUX_UID_GID
    ):
        os.close(fd)
        raise DiscoveryError("curl_CA_bundle_identity_mismatch")
    return fd, before, identity


def curl_range_executor(
    source: SiyavulaSource,
    start: int,
    end: int,
    *,
    curl_path: Path = DEFAULT_CURL,
    private_temp_dir: Path,
) -> RangeOutcome:
    expected = end - start + 1
    validate_transport_temp_directory(private_temp_dir)
    with tempfile.TemporaryFile(
        dir=private_temp_dir
    ) as headers, tempfile.TemporaryFile(dir=private_temp_dir) as body:
        guard = open_loader_closure(
            curl_path,
            role="curl",
            expected=CURL_LOADER_EXPECTED,
        )
        try:
            CA_fd, CA_before, CA_identity = open_CA_bundle()
            try:
                argv = [
                    str(guard.linker_path),
                    f"/proc/self/fd/{guard.target_fd}",
                    "--disable",
                    "--silent",
                    "--show-error",
                    "--http1.1",
                    "--proto",
                    "=https",
                    "--proto-redir",
                    "=https",
                    "--max-redirs",
                    "0",
                    "--noproxy",
                    "*",
                    "--retry",
                    "0",
                    "--tlsv1.2",
                    "--tls-max",
                    "1.3",
                    "--connect-timeout",
                    "30",
                    "--speed-limit",
                    "1",
                    "--speed-time",
                    "180",
                    "--max-time",
                    str(CURL_MAX_TIME_SECONDS),
                    "--max-filesize",
                    str(expected),
                    "--cacert",
                    f"/proc/self/fd/{CA_fd}",
                    "--range",
                    f"{start}-{end}",
                    "--header",
                    f"If-Match: {source.expected_etag}",
                    "--header",
                    f"If-Unmodified-Since: {source.expected_last_modified}",
                    "--header",
                    "Accept-Encoding: identity",
                    "--dump-header",
                    f"/proc/self/fd/{headers.fileno()}",
                    "--output",
                    f"/proc/self/fd/{body.fileno()}",
                    source.url,
                ]
                completed = subprocess.run(
                    argv,
                    check=False,
                    close_fds=True,
                    env=exact_curl_environment(private_temp_dir),
                    pass_fds=(
                        headers.fileno(),
                        body.fileno(),
                        guard.target_fd,
                        CA_fd,
                    ),
                    stderr=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    timeout=CURL_SUBPROCESS_TIMEOUT_SECONDS,
                )
                guard.revalidate()
                revalidate_held_executable(CA_fd, CA_before, CA_BUNDLE_PATH)
                headers.seek(0)
                body.seek(0)
                return RangeOutcome(
                    exit_code=completed.returncode,
                    headers=headers.read(256 * 1024 + 1),
                    body=body.read(CHUNK_BYTES + 1),
                    stderr=completed.stderr[:256 * 1024],
                    tool_identity_sha256=canonical_sha256(
                        {
                            "CA_bundle": CA_identity,
                            "loader_closure": guard.closure,
                        }
                    ),
                )
            finally:
                os.close(CA_fd)
        finally:
            guard.close()


def validate_transport_temp_directory(path: Path) -> None:
    resolved = path.resolve(strict=True)
    value = resolved.lstat()
    if (
        not stat.S_ISDIR(value.st_mode)
        or stat.S_IMODE(value.st_mode) != 0o700
        or value.st_uid != os.geteuid()
        or value.st_gid != os.getegid()
    ):
        raise DiscoveryError("transport_temp_directory_identity_invalid")


def exact_curl_environment(private_temp_dir: Path) -> dict[str, str]:
    return {
        "ANDROID_ROOT": "/system",
        "HOME": str(PHONE_HOME),
        "LC_ALL": "C",
        "PATH": "/data/data/com.termux/files/usr/bin:/system/bin",
        "TMPDIR": str(private_temp_dir.resolve(strict=True)),
    }


def parse_single_response_headers(payload: bytes) -> tuple[int, dict[str, str]]:
    if not payload or len(payload) > 256 * 1024:
        raise DiscoveryError("range_response_headers_size_invalid")
    normalized = payload.replace(b"\r\n", b"\n")
    blocks = [block for block in normalized.split(b"\n\n") if block.strip()]
    if len(blocks) != 1:
        raise DiscoveryError("range_response_header_block_cardinality")
    try:
        lines = blocks[0].decode("iso-8859-1").split("\n")
    except UnicodeDecodeError:
        raise DiscoveryError("range_response_headers_encoding_invalid") from None
    status_match = re.fullmatch(r"HTTP/1\.[01] ([0-9]{3})(?: .*)?", lines[0])
    if status_match is None:
        raise DiscoveryError("range_response_status_line_invalid")
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if not line:
            continue
        if line[0].isspace() or ":" not in line:
            raise DiscoveryError("range_response_header_line_invalid")
        name, value = line.split(":", 1)
        normalized_name = name.casefold()
        if normalized_name in fields:
            if normalized_name in {"cache-control", "vary"}:
                fields[normalized_name] = f"{fields[normalized_name]}, {value.strip()}"
                continue
            raise DiscoveryError(f"range_response_duplicate_header:{normalized_name}")
        fields[normalized_name] = value.strip()
    return int(status_match.group(1)), fields


def validate_range_outcome(
    source: SiyavulaSource,
    *,
    start: int,
    end: int,
    outcome: RangeOutcome,
) -> dict[str, Any]:
    expected = end - start + 1
    if outcome.exit_code != 0:
        raise DiscoveryError(f"curl_range_exit_nonzero:{outcome.exit_code}")
    if len(outcome.body) != expected:
        raise DiscoveryError("range_body_size_mismatch")
    status, fields = parse_single_response_headers(outcome.headers)
    expected_content_range = f"bytes {start}-{end}/{source.expected_bytes}"
    content_type = fields.get("content-type", "").split(";", 1)[0].casefold()
    encoding = fields.get("content-encoding")
    if (
        status != 206
        or fields.get("content-length") != str(expected)
        or fields.get("content-range") != expected_content_range
        or fields.get("etag") != source.expected_etag
        or fields.get("last-modified") != source.expected_last_modified
        or content_type != "application/epub+zip"
        or (encoding is not None and encoding.casefold() != "identity")
    ):
        raise DiscoveryError("range_response_identity_mismatch")
    match = CONTENT_RANGE_RE.fullmatch(fields["content-range"])
    if match is None or tuple(map(int, match.groups())) != (
        start,
        end,
        source.expected_bytes,
    ):
        raise DiscoveryError("range_content_range_invalid")
    return {
        "content_encoding": encoding,
        "content_length": expected,
        "content_range": expected_content_range,
        "content_type": fields["content-type"],
        "etag": fields["etag"],
        "last_modified": fields["last-modified"],
        "status_code": status,
    }


def chunk_bounds(source: SiyavulaSource, chunk_index: int) -> tuple[int, int]:
    chunk_count = (source.expected_bytes + CHUNK_BYTES - 1) // CHUNK_BYTES
    if type(chunk_index) is not int or not 0 <= chunk_index < chunk_count:
        raise DiscoveryError("chunk_index_out_of_range")
    start = chunk_index * CHUNK_BYTES
    end = min(source.expected_bytes, start + CHUNK_BYTES) - 1
    return start, end


def source_state_directory(epoch: Path, source: SiyavulaSource) -> Path:
    directory = epoch / "sources" / source.source_id
    for child in (directory, directory / "attempts", directory / "selected"):
        ensure_private_directory(child)
    return directory


def selection_path(epoch: Path, source: SiyavulaSource, chunk_index: int) -> Path:
    return source_state_directory(epoch, source) / "selected" / f"{chunk_index:08d}.json"


def publish_cas_blob(root: Path, payload: bytes) -> tuple[Path, str]:
    digest = sha256_bytes(payload)
    cas_directory = root / "cas" / "sha256" / digest[:2]
    ensure_private_directory(cas_directory)
    destination = cas_directory / digest
    if destination.exists():
        require_sealed_regular_path(destination, role="CAS")
        observed_digest, observed_bytes = hash_file(destination)
        if observed_digest != digest or observed_bytes != len(payload):
            raise DiscoveryError("CAS_existing_blob_identity_mismatch")
        return destination, digest
    try:
        publish_immutable_bytes(destination, payload)
    except DiscoveryError as error:
        if not str(error).startswith("immutable_artifact_race:"):
            raise
        observed_digest, observed_bytes = hash_file(destination)
        if observed_digest != digest or observed_bytes != len(payload):
            raise DiscoveryError("CAS_publication_race_mismatch") from None
    observed_digest, observed_bytes = hash_file(destination)
    require_sealed_regular_path(destination, role="CAS")
    if observed_digest != digest or observed_bytes != len(payload):
        raise DiscoveryError("CAS_postpublication_identity_mismatch")
    return destination, digest


def require_sealed_regular_stat(value: os.stat_result, *, role: str) -> None:
    if (
        not stat.S_ISREG(value.st_mode)
        or stat.S_IMODE(value.st_mode) != 0o400
        or value.st_nlink != 1
        or value.st_uid != os.geteuid()
        or value.st_gid != os.getegid()
    ):
        raise DiscoveryError(f"{role}_sealed_identity_invalid")


def require_sealed_regular_path(path: Path, *, role: str) -> os.stat_result:
    value = os.stat(path, follow_symlinks=False)
    require_sealed_regular_stat(value, role=role)
    return value


def open_validated_CAS_fd(
    root: Path,
    record: Mapping[str, Any],
) -> tuple[int, Path, os.stat_result]:
    cas_path = resolve_relative_artifact(root, record.get("cas_artifact"))
    expected_digest = record.get("body_sha256")
    expected_bytes = record.get("expected_chunk_bytes")
    if (
        not isinstance(expected_digest, str)
        or SHA256_RE.fullmatch(expected_digest) is None
        or type(expected_bytes) is not int
        or expected_bytes <= 0
        or cas_path.name != expected_digest
    ):
        raise DiscoveryError("CAS_selection_identity_invalid")
    fd = os.open(cas_path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        path_before = os.stat(cas_path, follow_symlinks=False)
        require_sealed_regular_stat(before, role="CAS")
        if (
            stat_identity(before) != stat_identity(path_before)
            or before.st_size != expected_bytes
        ):
            raise DiscoveryError("CAS_held_preidentity_invalid")
        digest = hashlib.sha256()
        consumed = 0
        while True:
            payload = os.read(fd, HASH_READ_BYTES)
            if not payload:
                break
            digest.update(payload)
            consumed += len(payload)
        if digest.hexdigest() != expected_digest or consumed != expected_bytes:
            raise DiscoveryError("CAS_held_digest_invalid")
        os.lseek(fd, 0, os.SEEK_SET)
        return fd, cas_path, before
    except BaseException:
        os.close(fd)
        raise


def revalidate_held_CAS_fd(
    fd: int,
    cas_path: Path,
    before: os.stat_result,
    *,
    expected_digest: str,
    expected_bytes: int,
    copied_digest: str,
    copied_bytes: int,
) -> None:
    after = os.fstat(fd)
    try:
        path_after = os.stat(cas_path, follow_symlinks=False)
    except OSError as error:
        raise DiscoveryError("CAS_path_changed_during_copy") from error
    if (
        stat_identity(before) != stat_identity(after)
        or stat_identity(after) != stat_identity(path_after)
        or expected_digest != copied_digest
        or expected_bytes != copied_bytes
    ):
        raise DiscoveryError("CAS_changed_or_wrong_stream_copied")


def relative_inside(base: Path, target: Path) -> str:
    try:
        relative = target.resolve(strict=True).relative_to(base.resolve(strict=True))
    except (FileNotFoundError, ValueError):
        raise DiscoveryError("artifact_path_escapes_evidence_root") from None
    if any(part in {"", ".", ".."} for part in relative.parts):
        raise DiscoveryError("artifact_relative_path_invalid")
    return relative.as_posix()


def resolve_relative_artifact(base: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value or value.startswith("/"):
        raise DiscoveryError("artifact_relative_path_invalid")
    relative = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in relative.parts):
        raise DiscoveryError("artifact_relative_path_invalid")
    candidate = base.joinpath(*relative.parts)
    try:
        candidate.resolve(strict=True).relative_to(base.resolve(strict=True))
    except (FileNotFoundError, ValueError):
        raise DiscoveryError("artifact_path_escapes_evidence_root") from None
    return candidate


def attempt_record_path(
    epoch: Path,
    source: SiyavulaSource,
    chunk_index: int,
    *,
    now: datetime,
) -> Path:
    attempts = source_state_directory(epoch, source) / "attempts" / f"{chunk_index:08d}"
    ensure_private_directory(attempts)
    stamp = format_utc(now).replace("-", "").replace(":", "")
    return attempts / f"{stamp}-{uuid.uuid4().hex}.json"


def file_payload_sha256(path: Path) -> str:
    digest, _size = hash_file(path)
    return "sha256:" + digest


def validate_selected_chunk(
    root: Path,
    epoch: Path,
    source: SiyavulaSource,
    chunk_index: int,
) -> dict[str, Any]:
    start, end = chunk_bounds(source, chunk_index)
    selected_path = selection_path(epoch, source, chunk_index)
    selected = read_canonical_json(selected_path, schema=CHUNK_SELECTION_SCHEMA)
    require_exact_keys(
        selected,
        {
            "attempt_artifact",
            "attempt_sha256",
            "body_sha256",
            "cas_artifact",
            "chunk_end",
            "chunk_index",
            "chunk_start",
            "eligible_for_assembly",
            "expected_chunk_bytes",
            "schema_version",
            "source_id",
        },
        role="chunk_selection",
    )
    manifest = read_canonical_json(epoch / "epoch.json", schema=EPOCH_SCHEMA)
    attempt_path = resolve_relative_artifact(epoch, selected.get("attempt_artifact"))
    attempt = read_canonical_json(attempt_path, schema=CHUNK_ATTEMPT_SCHEMA)
    require_exact_keys(
        attempt,
        {
            "attempted_at_utc",
            "body_sha256",
            "chunk_end",
            "chunk_index",
            "chunk_start",
            "curl_exit_code",
            "curl_held_execution_identity_sha256",
            "curl_retry_count",
            "downloaded_bytes",
            "eligible_for_assembly",
            "expected_chunk_bytes",
            "expected_source_bytes",
            "failure_reason",
            "headers_sha256",
            "one_request_attempt_only",
            "request_count",
            "resource_observation_artifact",
            "resource_observation_sha256",
            "response",
            "runtime_identity_sha256",
            "schema_version",
            "source_id",
            "stderr_bytes",
            "stderr_sha256",
        },
        role="chunk_attempt",
    )
    require_exact_keys(
        attempt["response"],
        {
            "content_encoding",
            "content_length",
            "content_range",
            "content_type",
            "etag",
            "last_modified",
            "status_code",
        },
        role="chunk_response",
    )
    resource_path = resolve_relative_artifact(
        epoch, attempt.get("resource_observation_artifact")
    )
    validate_resource_observation_binding(
        epoch,
        (
            relative_inside(epoch, resource_path),
            attempt.get("resource_observation_sha256"),
        ),
    )
    cas_path = resolve_relative_artifact(root, selected.get("cas_artifact"))
    require_sealed_regular_path(cas_path, role="CAS")
    cas_digest, cas_bytes = hash_file(cas_path)
    required = {
        "body_sha256": selected.get("body_sha256"),
        "chunk_end": end,
        "chunk_index": chunk_index,
        "chunk_start": start,
        "expected_chunk_bytes": end - start + 1,
        "source_id": source.source_id,
    }
    if (
        any(attempt.get(key) != value for key, value in required.items())
        or any(selected.get(key) != value for key, value in required.items())
        or selected.get("attempt_sha256") != file_payload_sha256(attempt_path)
        or selected.get("eligible_for_assembly") is not True
        or attempt.get("eligible_for_assembly") is not True
        or attempt.get("one_request_attempt_only") is not True
        or attempt.get("request_count") != 1
        or attempt.get("curl_retry_count") != 0
        or attempt.get("expected_source_bytes") != source.expected_bytes
        or attempt.get("downloaded_bytes") != end - start + 1
        or attempt.get("curl_exit_code") != 0
        or attempt.get("failure_reason") is not None
        or attempt["response"]
        != {
            "content_encoding": None,
            "content_length": end - start + 1,
            "content_range": f"bytes {start}-{end}/{source.expected_bytes}",
            "content_type": "application/epub+zip",
            "etag": source.expected_etag,
            "last_modified": source.expected_last_modified,
            "status_code": 206,
        }
        or attempt.get("curl_held_execution_identity_sha256")
        != expected_curl_execution_identity(manifest["runtime_identity"])
        or attempt.get("runtime_identity_sha256")
        != manifest.get("runtime_identity_sha256")
        or attempt.get("resource_observation_sha256")
        != file_payload_sha256(resource_path)
        or cas_digest != selected.get("body_sha256")
        or cas_bytes != end - start + 1
        or cas_path.name != cas_digest
    ):
        raise DiscoveryError(f"selected_chunk_evidence_invalid:{source.source_id}")
    return {**selected, "cas_path": cas_path}


def _acquire_chunk_locked(
    root: Path,
    epoch: Path,
    source: SiyavulaSource,
    chunk_index: int,
    *,
    executor: RangeExecutor,
    resource_observer: Callable[[], tuple[str, str]],
    now: datetime | None = None,
) -> dict[str, Any]:
    manifest = read_canonical_json(epoch / "epoch.json", schema=EPOCH_SCHEMA)
    validate_selection_ready_binding(root, epoch, manifest)
    selected_path = selection_path(epoch, source, chunk_index)
    if selected_path.exists():
        return validate_selected_chunk(root, epoch, source, chunk_index)
    resource_observation = validate_resource_observation_binding(
        epoch,
        resource_observer(),
    )
    instant = now or utc_now()
    ensure_circuit_allows(root, now=instant)
    start, end = chunk_bounds(source, chunk_index)
    request_reservation = record_request_intent(
        root,
        source_id=source.source_id,
        chunk_index=chunk_index,
        resource_observation_sha256=resource_observation[1],
        now=instant,
    )
    execution_error: str | None = None
    try:
        outcome = executor(source, start, end)
    except Exception as error:  # The immutable record must survive launch failures.
        outcome = RangeOutcome(-1, b"", b"", type(error).__name__.encode("ascii"))
        execution_error = f"range_executor_exception:{type(error).__name__}"
    validation_error = execution_error
    response: dict[str, Any] | None = None
    expected_tool_identity_sha256 = expected_curl_execution_identity(
        manifest["runtime_identity"]
    )
    if (
        validation_error is None
        and outcome.tool_identity_sha256 != expected_tool_identity_sha256
    ):
        validation_error = "curl_held_execution_identity_mismatch"
    if validation_error is None:
        try:
            response = validate_range_outcome(
                source,
                start=start,
                end=end,
                outcome=outcome,
            )
        except DiscoveryError as error:
            validation_error = str(error)
    body_sha256 = sha256_bytes(outcome.body)
    cas_path: Path | None = None
    eligible = validation_error is None
    if eligible:
        cas_path, body_sha256 = publish_cas_blob(root, outcome.body)
    attempt = {
        "attempted_at_utc": format_utc(instant),
        "body_sha256": body_sha256,
        "chunk_end": end,
        "chunk_index": chunk_index,
        "chunk_start": start,
        "curl_exit_code": outcome.exit_code,
        "curl_held_execution_identity_sha256": outcome.tool_identity_sha256,
        "curl_retry_count": 0,
        "downloaded_bytes": len(outcome.body),
        "eligible_for_assembly": eligible,
        "expected_chunk_bytes": end - start + 1,
        "expected_source_bytes": source.expected_bytes,
        "failure_reason": validation_error,
        "headers_sha256": sha256_bytes(outcome.headers),
        "one_request_attempt_only": True,
        "request_count": 1,
        "resource_observation_artifact": resource_observation[0],
        "resource_observation_sha256": resource_observation[1],
        "response": response,
        "runtime_identity_sha256": manifest["runtime_identity_sha256"],
        "schema_version": CHUNK_ATTEMPT_SCHEMA,
        "source_id": source.source_id,
        "stderr_bytes": len(outcome.stderr),
        "stderr_sha256": sha256_bytes(outcome.stderr),
    }
    attempt_path = attempt_record_path(epoch, source, chunk_index, now=instant)
    attempt_sha256 = publish_immutable_json(attempt_path, attempt)
    if not eligible or cas_path is None:
        raise CircuitOpen(
            "range_attempt_failed_open_until:"
            f"{request_reservation['open_until_utc']}"
        )
    selection = {
        "attempt_artifact": relative_inside(epoch, attempt_path),
        "attempt_sha256": attempt_sha256,
        "body_sha256": body_sha256,
        "cas_artifact": relative_inside(root, cas_path),
        "chunk_end": end,
        "chunk_index": chunk_index,
        "chunk_start": start,
        "eligible_for_assembly": True,
        "expected_chunk_bytes": end - start + 1,
        "schema_version": CHUNK_SELECTION_SCHEMA,
        "source_id": source.source_id,
    }
    publish_immutable_json(selected_path, selection)
    record_circuit_success(
        root,
        source_id=source.source_id,
        chunk_index=chunk_index,
        attempt_sha256=attempt_sha256,
        now=instant,
    )
    return validate_selected_chunk(root, epoch, source, chunk_index)


def acquire_chunk(
    root: Path,
    epoch: Path,
    source: SiyavulaSource,
    chunk_index: int,
    *,
    executor: RangeExecutor,
    resource_observer: Callable[[], tuple[str, str]],
    now: datetime | None = None,
) -> dict[str, Any]:
    if not callable(resource_observer):
        raise DiscoveryError("range_resource_observer_invalid")
    with origin_lock(root):
        return _acquire_chunk_locked(
            root,
            epoch,
            source,
            chunk_index,
            executor=executor,
            resource_observer=resource_observer,
            now=now,
        )


def next_pending_chunk(epoch: Path) -> tuple[SiyavulaSource, int] | None:
    for source in SIYAVULA_SOURCES:
        chunk_count = (source.expected_bytes + CHUNK_BYTES - 1) // CHUNK_BYTES
        for chunk_index in range(chunk_count):
            if not selection_path(epoch, source, chunk_index).exists():
                return source, chunk_index
    return None


def acquire_epoch(
    epoch: Path,
    *,
    executor: RangeExecutor,
    runtime_identity: Mapping[str, Any],
    lease: DiscoveryLease,
    max_successful_chunks: int = 0,
) -> dict[str, Any]:
    if type(max_successful_chunks) is not int or max_successful_chunks < 0:
        raise DiscoveryError("max_successful_chunks_invalid")
    root, epoch, manifest = validate_epoch(epoch)
    require_epoch_runtime(manifest, runtime_identity)
    require_lease_epoch(lease, epoch)
    validate_selection_ready_binding(root, epoch, manifest)
    completed = 0
    with epoch_lock(epoch):
        while max_successful_chunks == 0 or completed < max_successful_chunks:
            pending = next_pending_chunk(epoch)
            if pending is None:
                break
            source, chunk_index = pending
            acquire_chunk(
                root,
                epoch,
                source,
                chunk_index,
                executor=executor,
                resource_observer=lambda source_id=source.source_id, index=chunk_index: lease.observe(
                    phase=f"before_range:{source_id}:{index}"
                ),
            )
            lease.observe(phase=f"after_range:{source.source_id}:{chunk_index}")
            completed += 1
    return {
        "all_chunks_selected": next_pending_chunk(epoch) is None,
        "successful_chunks_this_invocation": completed,
    }


def write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise DiscoveryError("assembly_zero_length_write")
        view = view[written:]


def assemble_source(root: Path, epoch: Path, source: SiyavulaSource) -> dict[str, Any]:
    chunk_count = (source.expected_bytes + CHUNK_BYTES - 1) // CHUNK_BYTES
    selected = [
        validate_selected_chunk(root, epoch, source, chunk_index)
        for chunk_index in range(chunk_count)
    ]
    selected_roster = [
        {
            "attempt_sha256": record["attempt_sha256"],
            "body_sha256": record["body_sha256"],
            "chunk_end": record["chunk_end"],
            "chunk_index": record["chunk_index"],
            "chunk_start": record["chunk_start"],
        }
        for record in selected
    ]
    selected_root = canonical_sha256(selected_roster)
    source_output = epoch / "assembled" / source.source_id
    ensure_private_directory(source_output)
    assembly_path = source_output / "assembly.json"
    if assembly_path.exists():
        assembly = read_canonical_json(assembly_path, schema=ASSEMBLY_SCHEMA)
        artifact = resolve_relative_artifact(epoch, assembly.get("assembled_artifact"))
        require_sealed_regular_path(artifact, role="assembly")
        first_hash, size = hash_file(artifact)
        second_hash, second_size = hash_file(artifact)
        if (
            assembly.get("source_id") != source.source_id
            or assembly.get("assembled_bytes") != source.expected_bytes
            or assembly.get("chunk_bytes") != CHUNK_BYTES
            or assembly.get("chunk_count") != chunk_count
            or assembly.get("selected_chunk_evidence_root_sha256") != selected_root
            or assembly.get("old_unreceipted_prefixes_or_chunks_adopted") is not False
            or assembly.get("double_hash_verified") is not True
            or first_hash != assembly.get("whole_file_sha256_pass_1")
            or second_hash != assembly.get("whole_file_sha256_pass_2")
            or size != source.expected_bytes
            or second_size != source.expected_bytes
            or artifact.name != f"{first_hash}.epub"
            or (
                source.known_sha256 is not None
                and first_hash != source.known_sha256
            )
        ):
            raise DiscoveryError(f"existing_assembly_identity_invalid:{source.source_id}")
        return assembly
    temporary = source_output / f".assembling-{uuid.uuid4().hex}"
    fd = os.open(
        temporary,
        os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
        0o600,
    )
    digest = hashlib.sha256()
    written = 0
    try:
        for record in selected:
            cas_fd, cas_path, cas_before = open_validated_CAS_fd(root, record)
            chunk_digest = hashlib.sha256()
            chunk_copied = 0
            try:
                remaining = record["expected_chunk_bytes"]
                while remaining:
                    payload = os.read(cas_fd, min(HASH_READ_BYTES, remaining))
                    if not payload:
                        raise DiscoveryError("CAS_chunk_short_read_during_assembly")
                    write_all(fd, payload)
                    digest.update(payload)
                    chunk_digest.update(payload)
                    remaining -= len(payload)
                    written += len(payload)
                    chunk_copied += len(payload)
                if os.read(cas_fd, 1):
                    raise DiscoveryError("CAS_chunk_long_read_during_assembly")
                revalidate_held_CAS_fd(
                    cas_fd,
                    cas_path,
                    cas_before,
                    expected_digest=record["body_sha256"],
                    expected_bytes=record["expected_chunk_bytes"],
                    copied_digest=chunk_digest.hexdigest(),
                    copied_bytes=chunk_copied,
                )
            finally:
                os.close(cas_fd)
        if written != source.expected_bytes:
            raise DiscoveryError("assembled_source_size_mismatch")
        os.fsync(fd)
        pass_1 = digest.hexdigest()
        os.lseek(fd, 0, os.SEEK_SET)
        with os.fdopen(os.dup(fd), "rb", closefd=True) as stream:
            pass_2, pass_2_bytes = hash_stream(stream)
        if pass_1 != pass_2 or pass_2_bytes != source.expected_bytes:
            raise DiscoveryError("assembled_source_double_hash_mismatch")
        if source.known_sha256 is not None and pass_1 != source.known_sha256:
            raise DiscoveryError(f"known_source_sha256_mismatch:{source.source_id}")
        os.fchmod(fd, 0o400)
        os.fsync(fd)
    except BaseException:
        os.close(fd)
        temporary.unlink(missing_ok=True)
        raise
    os.close(fd)
    destination = source_output / f"{pass_1}.epub"
    if destination.exists():
        observed_hash, observed_bytes = hash_file(destination)
        if observed_hash != pass_1 or observed_bytes != source.expected_bytes:
            temporary.unlink(missing_ok=True)
            raise DiscoveryError("assembly_publication_collision") from None
    else:
        source_fd = os.open(temporary, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        destination_fd = -1
        try:
            source_info = os.fstat(source_fd)
            if (
                not stat.S_ISREG(source_info.st_mode)
                or stat.S_IMODE(source_info.st_mode) != 0o400
                or source_info.st_nlink != 1
                or source_info.st_size != source.expected_bytes
            ):
                raise DiscoveryError("assembly_temporary_identity_invalid")
            destination_fd = os.open(
                destination,
                os.O_RDWR
                | os.O_CREAT
                | os.O_EXCL
                | os.O_CLOEXEC
                | os.O_NOFOLLOW,
                0o400,
            )
            copied = 0
            copied_digest = hashlib.sha256()
            while copied < source.expected_bytes:
                payload = os.pread(
                    source_fd,
                    min(HASH_READ_BYTES, source.expected_bytes - copied),
                    copied,
                )
                if not payload:
                    raise DiscoveryError("assembly_publication_short_read")
                view = memoryview(payload)
                while view:
                    written_now = os.write(destination_fd, view)
                    if written_now <= 0:
                        raise DiscoveryError("assembly_publication_short_write")
                    view = view[written_now:]
                copied += len(payload)
                copied_digest.update(payload)
            os.fsync(destination_fd)
            os.fchmod(destination_fd, 0o400)
            os.fsync(destination_fd)
            destination_info = os.fstat(destination_fd)
            destination_entry = os.stat(destination, follow_symlinks=False)
            if (
                copied != source.expected_bytes
                or copied_digest.hexdigest() != pass_1
                or stat_identity(destination_info) != stat_identity(destination_entry)
            ):
                raise DiscoveryError("assembly_publication_readback_invalid")
            fsync_directory(source_output)
        finally:
            if destination_fd >= 0:
                os.close(destination_fd)
            os.close(source_fd)
    temporary.unlink(missing_ok=True)
    require_sealed_regular_path(destination, role="assembly")
    assembly = {
        "assembled_artifact": relative_inside(epoch, destination),
        "assembled_bytes": source.expected_bytes,
        "chunk_bytes": CHUNK_BYTES,
        "chunk_count": chunk_count,
        "double_hash_verified": True,
        "known_sha256_cross_check": (
            "matched" if source.known_sha256 is not None else "not_preregistered"
        ),
        "old_unreceipted_prefixes_or_chunks_adopted": False,
        "schema_version": ASSEMBLY_SCHEMA,
        "selected_chunk_evidence_root_sha256": selected_root,
        "source_id": source.source_id,
        "whole_file_sha256_pass_1": pass_1,
        "whole_file_sha256_pass_2": pass_2,
    }
    publish_immutable_json(assembly_path, assembly)
    return assembly


def qualified(namespace: str, local_name: str) -> str:
    return f"{{{namespace}}}{local_name}"


def local_name(tag: Any) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def reject_forbidden_xml(payload: bytes, *, allow_single_html5_doctype: bool = False) -> None:
    try:
        text = payload.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        raise DiscoveryError("EPUB_XML_encoding_invalid") from None
    if allow_single_html5_doctype:
        if text.count("<!DOCTYPE html>") != 1:
            raise DiscoveryError("EPUB_rights_HTML5_doctype_invalid")
        text = text.replace("<!DOCTYPE html>", "", 1)
    if XML_FORBIDDEN_RE.search(text):
        raise DiscoveryError("EPUB_forbidden_XML_markup")


def parse_xml(
    payload: bytes,
    *,
    role: str,
    allow_html5_doctype: bool = False,
    checkpoint: Callable[[str], None] | None = None,
) -> ElementTree.Element:
    reject_forbidden_xml(payload, allow_single_html5_doctype=allow_html5_doctype)
    parser = ElementTree.XMLPullParser(events=("start", "end"))
    root: ElementTree.Element | None = None
    depth = 0
    element_count = 0
    text_characters = 0

    def consume_events() -> None:
        nonlocal depth, element_count, root, text_characters
        for event, element in parser.read_events():
            if event == "start":
                if root is None:
                    root = element
                depth += 1
                element_count += 1
                attribute_characters = sum(
                    len(name) + len(value) for name, value in element.attrib.items()
                )
                if (
                    depth > MAX_XML_DEPTH
                    or element_count > MAX_XML_ELEMENTS
                    or len(element.attrib) > MAX_XML_ATTRIBUTES_PER_ELEMENT
                    or attribute_characters > MAX_XML_ATTRIBUTE_CHARACTERS
                ):
                    raise DiscoveryError(f"EPUB_{role}_XML_allocation_limit")
                continue
            text_characters += len(element.text or "") + len(element.tail or "")
            if text_characters > MAX_XML_TEXT_CHARACTERS:
                raise DiscoveryError(f"EPUB_{role}_XML_text_limit")
            depth -= 1
            if depth < 0:
                raise DiscoveryError(f"EPUB_{role}_XML_depth_invalid")

    try:
        for offset in range(0, len(payload), 64 * 1024):
            parser.feed(payload[offset : offset + 64 * 1024])
            consume_events()
            if checkpoint is not None:
                checkpoint(f"XML_parse:{role}")
        parser.close()
        consume_events()
        if checkpoint is not None:
            checkpoint(f"XML_parse_final:{role}")
    except ElementTree.ParseError:
        raise DiscoveryError(f"EPUB_{role}_XML_invalid") from None
    if root is None or depth != 0 or element_count <= 0:
        raise DiscoveryError(f"EPUB_{role}_XML_structure_invalid")
    return root


def validate_archive_member_name(name: str, seen: set[str]) -> None:
    if (
        not name
        or "\x00" in name
        or "\\" in name
        or name.startswith("/")
        or name in seen
    ):
        raise DiscoveryError("EPUB_archive_member_name_invalid")
    path = PurePosixPath(name)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise DiscoveryError("EPUB_archive_member_path_invalid")
    seen.add(name)


def validate_zip_mode(info: zipfile.ZipInfo) -> None:
    mode = info.external_attr >> 16
    file_type = stat.S_IFMT(mode)
    if stat.S_ISLNK(mode) or file_type not in {0, stat.S_IFREG, stat.S_IFDIR}:
        raise DiscoveryError("EPUB_archive_special_member_forbidden")
    if info.flag_bits & 0x1:
        raise DiscoveryError("EPUB_encrypted_member_forbidden")


def manifest_properties(value: str) -> tuple[str, ...]:
    tokens = tuple(value.split())
    if len(tokens) != len(set(tokens)) or any(
        re.fullmatch(r"[A-Za-z][A-Za-z0-9._:-]*", token) is None for token in tokens
    ):
        raise DiscoveryError("EPUB_manifest_properties_invalid")
    return tokens


def resolve_epub_member(base_member: str, href: str) -> str:
    if not href or "\x00" in href or "\\" in href:
        raise DiscoveryError("EPUB_href_invalid")
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc:
        raise DiscoveryError("EPUB_remote_manifest_URI_forbidden")
    href_path = unquote(parsed.path)
    if not href_path:
        if parsed.fragment:
            return base_member
        raise DiscoveryError("EPUB_href_path_missing")
    if href_path.startswith("/"):
        raise DiscoveryError("EPUB_href_escapes_root")
    parts: list[str] = []
    for part in (PurePosixPath(base_member).parent / href_path).parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                raise DiscoveryError("EPUB_href_escapes_root")
            parts.pop()
            continue
        parts.append(part)
    if not parts:
        raise DiscoveryError("EPUB_href_invalid")
    result = "/".join(parts)
    validate_archive_member_name(result, set())
    return result


def dc_values(package: ElementTree.Element, field: str) -> list[str]:
    return [
        (element.text or "").strip()
        for element in package.iter()
        if element.tag == qualified(DC_NS, field)
    ]


def package_prefix_mappings(package: ElementTree.Element) -> dict[str, str]:
    value = package.attrib.get("prefix", "")
    mappings = {"dcterms": "http://purl.org/dc/terms/"}
    cursor = 0
    pattern = re.compile(r"\s*([a-z][a-z0-9._-]*):\s+([^\s]+)")
    while cursor < len(value):
        match = pattern.match(value, cursor)
        if match is None:
            raise DiscoveryError("EPUB_package_prefix_declaration_invalid")
        prefix, namespace = match.groups()
        if prefix in mappings and mappings[prefix] != namespace:
            raise DiscoveryError("EPUB_package_prefix_redefinition_invalid")
        mappings[prefix] = namespace
        cursor = match.end()
    return mappings


def recognized_grade_metadata(package: ElementTree.Element) -> list[dict[str, str]]:
    mappings = package_prefix_mappings(package)
    approved = {
        ("dcterms", "educationlevel", "http://purl.org/dc/terms/"),
        ("dcterms", "educationallevel", "http://purl.org/dc/terms/"),
        ("lrmi", "educationallevel", "http://purl.org/dcx/lrmi-terms/"),
        ("schema", "educationallevel", "http://schema.org/"),
        ("schema", "educationallevel", "https://schema.org/"),
    }
    values: list[dict[str, str]] = []
    grade_like = {"educationlevel", "educationallevel", "grade"}
    for element in package.iter(qualified(OPF_NS, "meta")):
        property_name = element.attrib.get("property", "")
        if ":" in property_name:
            prefix, local = property_name.split(":", 1)
        else:
            prefix, local = "", property_name
        normalized_local = re.sub(r"[-_.]", "", local).casefold()
        if normalized_local not in grade_like:
            continue
        namespace = mappings.get(prefix)
        if (prefix, normalized_local, namespace) not in approved:
            raise DiscoveryError("EPUB_unapproved_grade_like_metadata_property")
        text = (element.text or "").strip()
        if not text:
            raise DiscoveryError("EPUB_recognized_grade_metadata_empty")
        values.append(
            {
                "namespace": namespace,
                "property": property_name,
                "value": text,
            }
        )
    return values


def observation_state(values: Sequence[Any]) -> str:
    return "observed_values" if values else "observed_empty"


def package_metadata(package: ElementTree.Element) -> dict[str, Any]:
    version = package.attrib.get("version")
    unique_identifier_id = package.attrib.get("unique-identifier")
    identifiers = dc_values(package, "identifier")
    modified = [
        (element.text or "").strip()
        for element in package.iter(qualified(OPF_NS, "meta"))
        if element.attrib.get("property") == "dcterms:modified"
    ]
    if (
        version is None
        or re.fullmatch(r"3\.[0-9]+", version) is None
        or unique_identifier_id is None
        or re.fullmatch(r"[A-Za-z_][A-Za-z0-9._:-]{0,127}", unique_identifier_id)
        is None
        or len(identifiers) != 1
    ):
        raise DiscoveryError("EPUB_package_identity_invalid")
    linked = [
        element
        for element in package.iter(qualified(DC_NS, "identifier"))
        if element.attrib.get("id") == unique_identifier_id
    ]
    if len(linked) != 1 or (linked[0].text or "").strip() != identifiers[0]:
        raise DiscoveryError("EPUB_unique_identifier_link_invalid")
    creator = dc_values(package, "creator")
    publisher = dc_values(package, "publisher")
    rights = dc_values(package, "rights")
    subject = dc_values(package, "subject")
    grade = recognized_grade_metadata(package)
    values = {
        "dc_creator_values": dc_values(package, "creator"),
        "dc_creator_observation_state": observation_state(creator),
        "dc_identifier_values": identifiers,
        "dc_language_values": dc_values(package, "language"),
        "dc_publisher_values": publisher,
        "dc_publisher_observation_state": observation_state(publisher),
        "dc_rights_values": rights,
        "dc_rights_observation_state": observation_state(rights),
        "dc_subject_values": subject,
        "dc_subject_observation_state": observation_state(subject),
        "dc_title_values": dc_values(package, "title"),
        "dcterms_modified_values": modified,
        "recognized_grade_metadata": grade,
        "recognized_grade_observation_state": observation_state(grade),
        "package_unique_identifier_id": unique_identifier_id,
        "package_unique_identifier_linked": True,
        "package_version": version,
    }
    bounded_metadata_lists = [
        value for value in values.values() if isinstance(value, list)
    ]
    if any(
        len(items) > 64
        or sum(len(canonical_json_bytes(item)) for item in items) > 64 * 1024
        for items in bounded_metadata_lists
    ):
        raise DiscoveryError("EPUB_OPF_metadata_allocation_limit")
    if (
        len(values["dc_title_values"]) != 1
        or values["dc_language_values"] != ["en"]
        or len(modified) != 1
        or any(not value for field in values.values() if isinstance(field, list) for value in field)
    ):
        raise DiscoveryError("EPUB_required_metadata_invalid")
    return values


def inspect_navigation(
    payload: bytes,
    *,
    member_path: str,
    archive_names: set[str],
    xhtml_payloads: Mapping[str, bytes],
    checkpoint: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    root = parse_xml(payload, role="navigation", checkpoint=checkpoint)
    if root.tag != qualified(XHTML_NS, "html"):
        raise DiscoveryError("EPUB_navigation_namespace_invalid")
    toc_nodes = [
        element
        for element in root.iter(qualified(XHTML_NS, "nav"))
        if "toc" in element.attrib.get(qualified(EPUB_OPS_NS, "type"), "").split()
    ]
    if len(toc_nodes) != 1:
        raise DiscoveryError("EPUB_navigation_TOC_cardinality_invalid")
    links = [
        element.attrib.get("href", "")
        for element in toc_nodes[0].iter(qualified(XHTML_NS, "a"))
    ]
    if (
        not links
        or len(links) > 100_000
        or any(not link or len(link) > 4096 for link in links)
    ):
        raise DiscoveryError("EPUB_navigation_TOC_link_invalid")
    targets = [resolve_epub_member(member_path, link) for link in links]
    if any(target not in archive_names for target in targets):
        raise DiscoveryError("EPUB_navigation_TOC_target_missing")
    fragment_count = 0
    parsed_target_ids: dict[str, set[str]] = {}
    for href, target in zip(links, targets, strict=True):
        fragment = unquote(urlsplit(href).fragment)
        if not fragment:
            continue
        fragment_count += 1
        payload = xhtml_payloads.get(target)
        if payload is None:
            raise DiscoveryError("EPUB_navigation_fragment_target_not_XHTML")
        if target not in parsed_target_ids:
            target_root = parse_xhtml_for_media(payload, checkpoint=checkpoint)
            ids = [
                element.attrib["id"]
                for element in target_root.iter()
                if "id" in element.attrib
            ]
            if len(ids) != len(set(ids)):
                raise DiscoveryError("EPUB_XHTML_duplicate_fragment_id")
            parsed_target_ids[target] = set(ids)
        if fragment not in parsed_target_ids[target]:
            raise DiscoveryError("EPUB_navigation_fragment_id_missing")
    return {
        "fragment_link_count": fragment_count,
        "fragment_targets_verified": True,
        "toc_link_count": len(links),
        "toc_nav_count": 1,
        "toc_target_set_sha256": canonical_sha256(sorted(set(targets))),
    }


def rights_subject_grade_claims(text: str) -> list[dict[str, Any]]:
    pattern = re.compile(
        r"(?i)(?:grade\s*([0-9]{1,2}).{0,80}"
        r"(natural\s+sciences|physical\s+sciences|mathematics)|"
        r"(natural\s+sciences|physical\s+sciences|mathematics).{0,80}"
        r"grade\s*([0-9]{1,2}))"
    )
    claims: set[tuple[int, str]] = set()
    for match in pattern.finditer(text):
        grade_text = match.group(1) or match.group(4)
        subject_text = match.group(2) or match.group(3)
        if grade_text and subject_text:
            subject = " ".join(word.capitalize() for word in subject_text.split())
            claims.add((int(grade_text), subject))
    return [
        {"grade": grade, "subject": subject}
        for grade, subject in sorted(claims)
    ]


def inspect_rights(
    payload: bytes,
    source: SiyavulaSource,
    *,
    checkpoint: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    root = parse_xml(
        payload,
        role="rights",
        allow_html5_doctype=True,
        checkpoint=checkpoint,
    )
    if root.tag != qualified(XHTML_NS, "html"):
        raise DiscoveryError("EPUB_rights_namespace_invalid")
    notice_url = "http://creativecommons.org/licenses/by/4.0/"
    links = [
        element
        for element in root.iter(qualified(XHTML_NS, "a"))
        if element.attrib.get("href") == notice_url
    ]
    text = " ".join(part.strip() for part in root.itertext() if part.strip())
    if not links or "siyavula" not in text.casefold():
        raise DiscoveryError("EPUB_structured_rights_evidence_missing")
    claims = rights_subject_grade_claims(text)
    expected_claim = {
        "grade": source.catalogue_grade,
        "subject": source.catalogue_subject,
    }
    mismatch: bool | None = None
    if claims:
        mismatch = expected_claim not in claims
    return {
        "artifact_notice_license_id": "CC-BY-4.0",
        "artifact_notice_url": notice_url,
        "catalogue_license_id": "CC-BY-3.0",
        "resolved_license_id": "LicenseRef-Siyavula-Unbranded-CCBY-Version-Conflict",
        "rights_subject_grade_claims": claims,
        "rights_subject_template_mismatch": mismatch,
        "structured_license_link_count": len(links),
        "siyavula_marker_present": True,
    }


def inspect_package_structure(
    package: ElementTree.Element,
    *,
    opf_path: str,
    archive_names: set[str],
) -> dict[str, Any]:
    if package.tag != qualified(OPF_NS, "package"):
        raise DiscoveryError("EPUB_OPF_package_namespace_invalid")
    namespace_by_local = {
        "creator": DC_NS,
        "identifier": DC_NS,
        "item": OPF_NS,
        "itemref": OPF_NS,
        "language": DC_NS,
        "manifest": OPF_NS,
        "meta": OPF_NS,
        "metadata": OPF_NS,
        "publisher": DC_NS,
        "rights": DC_NS,
        "spine": OPF_NS,
        "subject": DC_NS,
        "title": DC_NS,
    }
    for element in package.iter():
        name = local_name(element.tag)
        namespace = namespace_by_local.get(name)
        if namespace is not None and element.tag != qualified(namespace, name):
            raise DiscoveryError(f"EPUB_OPF_element_namespace_invalid:{name}")
    structural_counts = {
        name: sum(1 for _ in package.iter(qualified(OPF_NS, name)))
        for name in ("metadata", "manifest", "spine")
    }
    if any(count != 1 for count in structural_counts.values()):
        raise DiscoveryError("EPUB_OPF_structure_cardinality_invalid")
    items: dict[str, dict[str, Any]] = {}
    targets: set[str] = set()
    for element in package.iter(qualified(OPF_NS, "item")):
        item_id = element.attrib.get("id")
        href = element.attrib.get("href")
        media_type = element.attrib.get("media-type")
        properties = manifest_properties(element.attrib.get("properties", ""))
        if (
            not item_id
            or not href
            or not media_type
            or len(item_id) > 256
            or len(href) > 4096
            or len(media_type) > 256
        ):
            raise DiscoveryError("EPUB_manifest_item_invalid")
        target = resolve_epub_member(opf_path, href)
        if target not in archive_names:
            raise DiscoveryError("EPUB_manifest_target_missing")
        if item_id in items or target in targets:
            raise DiscoveryError("EPUB_manifest_duplicate_id_or_target")
        items[item_id] = {
            "href": href,
            "media_type": media_type,
            "properties": list(properties),
            "target": target,
        }
        targets.add(target)
    navigation = [
        (item_id, item)
        for item_id, item in items.items()
        if "nav" in item["properties"]
    ]
    if (
        len(navigation) != 1
        or navigation[0][1]["media_type"] != "application/xhtml+xml"
    ):
        raise DiscoveryError("EPUB_navigation_manifest_binding_invalid")
    rights = [
        (item_id, item)
        for item_id, item in items.items()
        if (
            PurePosixPath(item["target"]).name
            == "copyright_acknowledgements_ccby.html"
            or PurePosixPath(item["target"]).name.casefold().endswith(
                ("frontmatter.xhtml", "frontmatter.html")
            )
        )
    ]
    if (
        len(rights) != 1
        or rights[0][1]["media_type"] != "application/xhtml+xml"
        or "nav" in rights[0][1]["properties"]
    ):
        raise DiscoveryError("EPUB_rights_manifest_binding_invalid")
    xhtml_ids = {
        item_id
        for item_id, item in items.items()
        if item["media_type"] == "application/xhtml+xml"
    }
    spine = [
        element.attrib.get("idref")
        for element in package.iter(qualified(OPF_NS, "itemref"))
    ]
    if (
        not items
        or not xhtml_ids
        or not spine
        or len(spine) != len(set(spine))
        or any(item_id not in xhtml_ids for item_id in spine)
    ):
        raise DiscoveryError("EPUB_spine_binding_invalid")
    return {
        "items": items,
        "manifest_item_count": len(items),
        "manifest_target_count": len(targets),
        "navigation_item_id": navigation[0][0],
        "navigation_path": navigation[0][1]["target"],
        "rights_item_id": rights[0][0],
        "rights_path": rights[0][1]["target"],
        "spine_item_count": len(spine),
        "spine_item_ids_root_sha256": canonical_sha256(spine),
        "structural_counts": structural_counts,
        "xhtml_manifest_item_count": len(xhtml_ids),
    }


MEDIA_ELEMENT_ATTRIBUTES = {
    "audio": "src",
    "image": "href",
    "img": "src",
    "object": "data",
    "script": "src",
    "source": "src",
    "video": "src",
}
VISUAL_OR_CONTEXT_TAGS = frozenset(
    {
        "audio",
        "canvas",
        "figure",
        "image",
        "img",
        "math",
        "object",
        "picture",
        "script",
        "style",
        "svg",
        "table",
        "video",
    }
)


def parse_xhtml_for_media(
    payload: bytes,
    *,
    checkpoint: Callable[[str], None] | None = None,
) -> ElementTree.Element:
    try:
        text = payload.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        raise DiscoveryError("EPUB_XHTML_encoding_invalid") from None
    doctype_count = text.count("<!DOCTYPE html>")
    if doctype_count > 1:
        raise DiscoveryError("EPUB_XHTML_doctype_cardinality_invalid")
    if doctype_count == 1:
        text = text.replace("<!DOCTYPE html>", "", 1)
    if XML_FORBIDDEN_RE.search(text):
        raise DiscoveryError("EPUB_XHTML_forbidden_markup")
    root = parse_xml(
        text.encode("utf-8"),
        role="XHTML",
        checkpoint=checkpoint,
    )
    if root.tag != qualified(XHTML_NS, "html"):
        raise DiscoveryError("EPUB_XHTML_root_namespace_invalid")
    return root


def inspect_media_context(
    *,
    items: Mapping[str, Mapping[str, Any]],
    archive_names: set[str],
    xhtml_payloads: Mapping[str, bytes],
    css_payloads: Mapping[str, bytes],
    checkpoint: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    media_types = Counter(item["media_type"] for item in items.values())
    properties = Counter(
        property_name
        for item in items.values()
        for property_name in item["properties"]
    )
    element_counts: Counter[str] = Counter()
    internal_references: set[str] = set()
    remote_reference_count = 0
    embedded_data_reference_count = 0
    inline_style_attribute_count = 0
    inline_style_content_declaration_count = 0
    inline_style_url_count = 0
    for member_path, payload in xhtml_payloads.items():
        if checkpoint is not None:
            checkpoint("XHTML_media_context_member")
        root = parse_xhtml_for_media(payload, checkpoint=checkpoint)
        for element in root.iter():
            name = local_name(element.tag)
            if name in VISUAL_OR_CONTEXT_TAGS:
                element_counts[name] += 1
            inline_style = element.attrib.get("style")
            if inline_style is not None:
                inline_style_attribute_count += 1
                inline_style_url_count += len(
                    re.findall(r"(?i)\burl\s*\(", inline_style)
                )
                inline_style_content_declaration_count += len(
                    re.findall(r"(?i)(?:^|;)\s*content\s*:", inline_style)
                )
            attribute = MEDIA_ELEMENT_ATTRIBUTES.get(name)
            if attribute is None:
                continue
            value = element.attrib.get(attribute)
            if name == "image" and value is None:
                value = element.attrib.get("{http://www.w3.org/1999/xlink}href")
            if not value:
                continue
            parsed = urlsplit(value)
            if parsed.scheme in {"http", "https"} or parsed.netloc:
                remote_reference_count += 1
                continue
            if parsed.scheme == "data":
                embedded_data_reference_count += 1
                continue
            if parsed.scheme:
                raise DiscoveryError("EPUB_media_reference_scheme_invalid")
            target = resolve_epub_member(member_path, value)
            if target not in archive_names:
                raise DiscoveryError("EPUB_media_reference_target_missing")
            internal_references.add(target)
    image_items = sum(
        count for media_type, count in media_types.items() if media_type.startswith("image/")
    )
    css_items = media_types.get("text/css", 0)
    scripted_items = properties.get("scripted", 0) + media_types.get(
        "application/javascript", 0
    )
    css_url_count = 0
    css_content_declaration_count = 0
    css_bytes = 0
    for payload in css_payloads.values():
        if checkpoint is not None:
            checkpoint("CSS_media_context_member")
        css_bytes += len(payload)
        css_url_count += len(re.findall(rb"(?i)\burl\s*\(", payload))
        css_content_declaration_count += len(
            re.findall(rb"(?i)(?:^|[;{}])\s*content\s*:", payload)
        )
    visual_present = bool(
        image_items
        or css_items
        or any(element_counts[name] for name in VISUAL_OR_CONTEXT_TAGS)
        or scripted_items
        or inline_style_attribute_count
        or remote_reference_count
        or embedded_data_reference_count
    )
    return {
        "CSS_content_declaration_count": css_content_declaration_count,
        "CSS_payload_bytes": css_bytes,
        "CSS_payloads_not_semantically_interpreted": css_items > 0,
        "CSS_url_token_count": css_url_count,
        "embedded_data_reference_count": embedded_data_reference_count,
        "internal_media_reference_count": len(internal_references),
        "internal_media_reference_set_sha256": canonical_sha256(
            sorted(internal_references)
        ),
        "inline_style_attribute_count": inline_style_attribute_count,
        "inline_style_content_declaration_count": (
            inline_style_content_declaration_count
        ),
        "inline_style_url_token_count": inline_style_url_count,
        "manifest_image_item_count": image_items,
        "manifest_media_type_counts": dict(sorted(media_types.items())),
        "manifest_property_counts": dict(sorted(properties.items())),
        "media_context_element_counts": dict(sorted(element_counts.items())),
        "remote_media_reference_count": remote_reference_count,
        "scripted_manifest_item_count": scripted_items,
        "text_only_materialization_without_context_quarantine_forbidden": (
            visual_present
        ),
        "visual_or_table_context_present": visual_present,
        "visual_or_table_context_quarantine_required": visual_present,
    }


def read_small_zip_member(
    archive: zipfile.ZipFile,
    name: str,
    *,
    limit: int = MAX_COLLECTED_XML_BYTES,
    checkpoint: Callable[[str], None] | None = None,
) -> bytes:
    matches = [info for info in archive.infolist() if info.filename == name]
    if len(matches) != 1 or matches[0].is_dir() or matches[0].file_size > limit:
        raise DiscoveryError(f"EPUB_bound_member_invalid:{PurePosixPath(name).name}")
    collected = bytearray()
    with archive.open(matches[0], mode="r") as stream:
        while len(collected) <= limit:
            chunk = stream.read(min(HASH_READ_BYTES, limit + 1 - len(collected)))
            if not chunk:
                break
            collected.extend(chunk)
            if checkpoint is not None:
                checkpoint(f"ZIP_member:{PurePosixPath(name).name}")
    payload = bytes(collected)
    if len(payload) != matches[0].file_size:
        raise DiscoveryError("EPUB_bound_member_size_mismatch")
    return payload


def inspect_epub_fd(
    data_fd: int,
    source: SiyavulaSource,
    *,
    checkpoint: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    before = os.fstat(data_fd)
    if not stat.S_ISREG(before.st_mode) or before.st_size != source.expected_bytes:
        raise DiscoveryError("EPUB_held_assembly_identity_invalid")
    os.lseek(data_fd, 0, os.SEEK_SET)
    try:
        with os.fdopen(os.dup(data_fd), "rb", closefd=True) as handle:
            with zipfile.ZipFile(handle, mode="r") as archive:
                infos = archive.infolist()
                if not infos or len(infos) > MAX_ARCHIVE_ENTRIES:
                    raise DiscoveryError("EPUB_archive_entry_count_invalid")
                seen: set[str] = set()
                regular_names: set[str] = set()
                total_uncompressed = 0
                roster: list[dict[str, Any]] = []
                for info in infos:
                    if checkpoint is not None:
                        checkpoint("ZIP_central_directory_scan")
                    validate_archive_member_name(info.filename, seen)
                    validate_zip_mode(info)
                    if info.is_dir():
                        continue
                    if (
                        info.file_size < 0
                        or info.file_size > MAX_MEMBER_BYTES
                        or info.compress_type not in ADMITTED_ZIP_COMPRESSION_METHODS
                        or (info.compress_size == 0 and info.file_size > 0)
                        or (
                            info.compress_size > 0
                            and info.file_size / info.compress_size > 10_000
                        )
                    ):
                        raise DiscoveryError("EPUB_archive_member_envelope_invalid")
                    total_uncompressed += info.file_size
                    if total_uncompressed > min(source.expected_bytes * 32, 4 * 1024**3):
                        raise DiscoveryError("EPUB_archive_expansion_limit_reached")
                    regular_names.add(info.filename)
                    roster.append(
                        {
                            "CRC32": f"{info.CRC:08x}",
                            "compressed_bytes": info.compress_size,
                            "compression_method": info.compress_type,
                            "member": info.filename,
                            "uncompressed_bytes": info.file_size,
                        }
                    )
                first = infos[0]
                if (
                    first.filename != "mimetype"
                    or first.compress_type != zipfile.ZIP_STORED
                    or read_small_zip_member(archive, "mimetype", limit=256)
                    != b"application/epub+zip"
                ):
                    raise DiscoveryError("EPUB_mimetype_identity_invalid")
                container_payload = read_small_zip_member(
                    archive,
                    "META-INF/container.xml",
                    checkpoint=checkpoint,
                )
                container = parse_xml(
                    container_payload,
                    role="container",
                    checkpoint=checkpoint,
                )
                if container.tag != qualified(EPUB_CONTAINER_NS, "container"):
                    raise DiscoveryError("EPUB_container_namespace_invalid")
                rootfiles = [
                    (
                        element.attrib.get("full-path"),
                        element.attrib.get("media-type"),
                    )
                    for element in container.iter(
                        qualified(EPUB_CONTAINER_NS, "rootfile")
                    )
                ]
                if (
                    len(rootfiles) != 1
                    or not rootfiles[0][0]
                    or rootfiles[0][1] != "application/oebps-package+xml"
                ):
                    raise DiscoveryError("EPUB_container_rootfile_invalid")
                opf_path = rootfiles[0][0]
                if opf_path is None:
                    raise DiscoveryError("EPUB_container_rootfile_path_missing")
                validate_archive_member_name(opf_path, set())
                opf_payload = read_small_zip_member(
                    archive, opf_path, checkpoint=checkpoint
                )
                package = parse_xml(opf_payload, role="OPF", checkpoint=checkpoint)
                structure = inspect_package_structure(
                    package,
                    opf_path=opf_path,
                    archive_names=regular_names,
                )
                metadata = package_metadata(package)
                navigation_path = structure["navigation_path"]
                rights_path = structure["rights_path"]
                navigation_payload = read_small_zip_member(
                    archive, navigation_path, checkpoint=checkpoint
                )
                rights_payload = read_small_zip_member(
                    archive, rights_path, checkpoint=checkpoint
                )
                rights = inspect_rights(
                    rights_payload,
                    source,
                    checkpoint=checkpoint,
                )
                xhtml_payloads: dict[str, bytes] = {}
                css_payloads: dict[str, bytes] = {}
                xhtml_bytes = 0
                xhtml_count = 0
                css_bytes = 0
                for item in structure["items"].values():
                    if item["media_type"] == "application/xhtml+xml":
                        matches = [
                            info
                            for info in infos
                            if info.filename == item["target"] and not info.is_dir()
                        ]
                        if len(matches) != 1:
                            raise DiscoveryError("EPUB_XHTML_member_cardinality_invalid")
                        xhtml_bytes += matches[0].file_size
                        xhtml_count += 1
                        if (
                            xhtml_bytes > MAX_AGGREGATE_XHTML_BYTES
                            or xhtml_count > MAX_XHTML_MEMBERS
                        ):
                            raise DiscoveryError("EPUB_aggregate_XHTML_memory_bound")
                        xhtml_payloads[item["target"]] = read_small_zip_member(
                            archive,
                            item["target"],
                            checkpoint=checkpoint,
                        )
                    elif item["media_type"] == "text/css":
                        matches = [
                            info
                            for info in infos
                            if info.filename == item["target"] and not info.is_dir()
                        ]
                        if len(matches) != 1:
                            raise DiscoveryError("EPUB_CSS_member_cardinality_invalid")
                        css_bytes += matches[0].file_size
                        if css_bytes > MAX_AGGREGATE_CSS_BYTES:
                            raise DiscoveryError("EPUB_aggregate_CSS_memory_bound")
                        css_payloads[item["target"]] = read_small_zip_member(
                            archive,
                            item["target"],
                            limit=MAX_AGGREGATE_CSS_BYTES,
                            checkpoint=checkpoint,
                        )
                navigation = inspect_navigation(
                    navigation_payload,
                    member_path=navigation_path,
                    archive_names=regular_names,
                    xhtml_payloads=xhtml_payloads,
                    checkpoint=checkpoint,
                )
                media = inspect_media_context(
                    items=structure["items"],
                    archive_names=regular_names,
                    xhtml_payloads=xhtml_payloads,
                    css_payloads=css_payloads,
                    checkpoint=checkpoint,
                )
                # A complete streaming read forces zipfile to validate every CRC,
                # including binary members not collected for XML inspection.
                for info in infos:
                    if info.is_dir():
                        continue
                    consumed = 0
                    with archive.open(info, mode="r") as stream:
                        while True:
                            chunk = stream.read(HASH_READ_BYTES)
                            if not chunk:
                                break
                            consumed += len(chunk)
                            if checkpoint is not None:
                                checkpoint("ZIP_CRC_full_stream")
                    if consumed != info.file_size:
                        raise DiscoveryError("EPUB_member_stream_size_mismatch")
    except (OSError, RuntimeError, zipfile.BadZipFile) as error:
        if isinstance(error, DiscoveryError):
            raise
        raise DiscoveryError("EPUB_archive_inspection_failed") from error
    after = os.fstat(data_fd)
    if stat_identity(before) != stat_identity(after):
        raise DiscoveryError("EPUB_held_assembly_changed_during_inspection")
    manifest_targets = {
        item["target"] for item in structure["items"].values()
    }
    unmanifested = sorted(
        name
        for name in regular_names
        if name not in manifest_targets
        and name not in {"mimetype", "META-INF/container.xml", opf_path}
        and not name.startswith("META-INF/")
    )
    catalogue_record = {
        "catalogue_grade": source.catalogue_grade,
        "catalogue_subject": source.catalogue_subject,
        "download_filename": source.filename,
        "download_filename_grade_token": source.filename_grade_token,
        "download_filename_subject_token": source.filename_subject_token,
        "download_url": source.url,
        "license_id": "CC-BY-3.0",
        "source_id": source.source_id,
    }
    identity_core = {
        "archive": {
            "all_member_CRCs_verified": True,
            "archive_member_count": len(infos),
            "archive_member_roster_sha256": canonical_sha256(roster),
            "mimetype_first_and_stored": True,
            "total_uncompressed_bytes": total_uncompressed,
            "unmanifested_payload_count": len(unmanifested),
            "unmanifested_payload_name_root_sha256": canonical_sha256(unmanifested),
        },
        "catalogue_record": catalogue_record,
        "catalogue_record_sha256": canonical_sha256(catalogue_record),
        "container": {
            "media_type": rootfiles[0][1],
            "opf_path": opf_path,
            "path": "META-INF/container.xml",
            "sha256": "sha256:" + sha256_bytes(container_payload),
        },
        "internal_members": {
            "navigation": {
                "path": navigation_path,
                "sha256": "sha256:" + sha256_bytes(navigation_payload),
            },
            "opf": {
                "path": opf_path,
                "sha256": "sha256:" + sha256_bytes(opf_payload),
            },
            "rights": {
                "path": rights_path,
                "sha256": "sha256:" + sha256_bytes(rights_payload),
            },
        },
        "manifest_bindings": {
            "aggregate_xhtml_bytes": xhtml_bytes,
            "manifest_item_count": structure["manifest_item_count"],
            "manifest_target_count": structure["manifest_target_count"],
            "navigation_item_id": structure["navigation_item_id"],
            "navigation_path": navigation_path,
            "rights_item_id": structure["rights_item_id"],
            "rights_path": rights_path,
            "spine_item_count": structure["spine_item_count"],
            "spine_item_ids_root_sha256": structure["spine_item_ids_root_sha256"],
            "xhtml_manifest_item_count": structure["xhtml_manifest_item_count"],
        },
        "media_context": media,
        "metadata": metadata,
        "navigation": navigation,
        "rights": rights,
        "source_id": source.source_id,
    }
    return {
        **identity_core,
        "observation_root_sha256": canonical_sha256(identity_core),
        "schema_version": IDENTITY_SCHEMA,
    }


PageExecutor = Callable[[str], RangeOutcome]


def curl_page_executor(
    url: str,
    *,
    curl_path: Path = DEFAULT_CURL,
    private_temp_dir: Path,
) -> RangeOutcome:
    if url not in {CATALOGUE_URL, TERMS_URL}:
        raise DiscoveryError("external_evidence_URL_not_admitted")
    validate_transport_temp_directory(private_temp_dir)
    with tempfile.TemporaryFile(
        dir=private_temp_dir
    ) as headers, tempfile.TemporaryFile(dir=private_temp_dir) as body:
        guard = open_loader_closure(
            curl_path,
            role="curl",
            expected=CURL_LOADER_EXPECTED,
        )
        try:
            CA_fd, CA_before, CA_identity = open_CA_bundle()
            try:
                argv = [
                    str(guard.linker_path),
                    f"/proc/self/fd/{guard.target_fd}",
                    "--disable",
                    "--silent",
                    "--show-error",
                    "--http1.1",
                    "--proto",
                    "=https",
                    "--proto-redir",
                    "=https",
                    "--max-redirs",
                    "0",
                    "--noproxy",
                    "*",
                    "--retry",
                    "0",
                    "--tlsv1.2",
                    "--tls-max",
                    "1.3",
                    "--connect-timeout",
                    "30",
                    "--speed-limit",
                    "1",
                    "--speed-time",
                    "180",
                    "--max-time",
                    str(CURL_MAX_TIME_SECONDS),
                    "--max-filesize",
                    str(16 * 1024 * 1024),
                    "--cacert",
                    f"/proc/self/fd/{CA_fd}",
                    "--header",
                    "Accept-Encoding: identity",
                    "--dump-header",
                    f"/proc/self/fd/{headers.fileno()}",
                    "--output",
                    f"/proc/self/fd/{body.fileno()}",
                    url,
                ]
                completed = subprocess.run(
                    argv,
                    check=False,
                    close_fds=True,
                    env=exact_curl_environment(private_temp_dir),
                    pass_fds=(
                        headers.fileno(),
                        body.fileno(),
                        guard.target_fd,
                        CA_fd,
                    ),
                    stderr=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    timeout=CURL_SUBPROCESS_TIMEOUT_SECONDS,
                )
                guard.revalidate()
                revalidate_held_executable(CA_fd, CA_before, CA_BUNDLE_PATH)
                headers.seek(0)
                body.seek(0)
                return RangeOutcome(
                    exit_code=completed.returncode,
                    headers=headers.read(256 * 1024 + 1),
                    body=body.read(16 * 1024 * 1024 + 1),
                    stderr=completed.stderr[:256 * 1024],
                    tool_identity_sha256=canonical_sha256(
                        {
                            "CA_bundle": CA_identity,
                            "loader_closure": guard.closure,
                        }
                    ),
                )
            finally:
                os.close(CA_fd)
        finally:
            guard.close()


def validate_page_outcome(url: str, outcome: RangeOutcome) -> dict[str, Any]:
    if outcome.exit_code != 0 or not outcome.body or len(outcome.body) > 16 * 1024 * 1024:
        raise DiscoveryError("external_evidence_page_transfer_invalid")
    status, fields = parse_single_response_headers(outcome.headers)
    media_type = fields.get("content-type", "").split(";", 1)[0].casefold()
    encoding = fields.get("content-encoding")
    content_length = fields.get("content-length")
    if (
        status != 200
        or media_type not in {"text/html", "application/xhtml+xml"}
        or (encoding is not None and encoding.casefold() != "identity")
        or (content_length is not None and content_length != str(len(outcome.body)))
    ):
        raise DiscoveryError("external_evidence_page_response_identity_invalid")
    return {
        "body_bytes": len(outcome.body),
        "body_sha256": "sha256:" + sha256_bytes(outcome.body),
        "content_encoding": encoding,
        "content_length_header": content_length,
        "content_type": fields["content-type"],
        "etag": fields.get("etag"),
        "headers_sha256": "sha256:" + sha256_bytes(outcome.headers),
        "last_modified": fields.get("last-modified"),
        "request_count": 1,
        "retry_count": 0,
        "status_code": status,
        "url": url,
    }


CARD_TAGS = frozenset(
    {"article", "aside", "div", "li", "main", "p", "section"}
)
HIDDEN_CONTENT_TAGS = frozenset({"script", "style", "template", "noscript"})
VOID_HTML_TAGS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)


def contextual_assertion_pairs(text: str) -> set[tuple[int, str]]:
    subjects = (
        (
            "Natural Sciences and Technology",
            r"Natural\s+Sciences\s+and\s+Technology",
        ),
        ("Natural Sciences", r"Natural\s+Sciences(?!\s+and\s+Technology)"),
        ("Physical Sciences", r"Physical\s+Sciences"),
        ("Mathematics", r"Mathematics"),
    )
    pairs: set[tuple[int, str]] = set()
    for subject, subject_pattern in subjects:
        for grade in range(1, 13):
            grade_pattern = rf"(?:grade|gr)\s*{grade}(?![0-9])"
            if re.search(
                rf"(?is)(?:{subject_pattern}.{{0,240}}{grade_pattern}|"
                rf"{grade_pattern}.{{0,240}}{subject_pattern})",
                text,
            ):
                pairs.add((grade, subject))
    return pairs


class EvidenceHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[dict[str, Any]] = []
        self.cards: dict[int, dict[str, Any]] = {}
        self.images: list[dict[str, Any]] = []
        self.text_parts: list[str] = []
        self._stack: list[dict[str, Any]] = []
        self._active_anchor: dict[str, Any] | None = None
        self._element_count = 0
        self._visible_text_characters = 0
        self._structural_text_characters = 0
        self._next_card_id = 0

    def _normalize_attributes(
        self, attrs: list[tuple[str, str | None]]
    ) -> dict[str, str]:
        if len(attrs) > MAX_HTML_ATTRIBUTES_PER_ELEMENT:
            raise DiscoveryError("external_evidence_HTML_attribute_count_limit")
        normalized: dict[str, str] = {}
        characters = 0
        for name, value in attrs:
            key = name.casefold()
            if key in normalized:
                raise DiscoveryError("external_evidence_duplicate_HTML_attribute")
            normalized_value = value or ""
            characters += len(key) + len(normalized_value)
            if characters > MAX_HTML_ATTRIBUTE_CHARACTERS:
                raise DiscoveryError("external_evidence_HTML_attribute_size_limit")
            normalized[key] = normalized_value
        return normalized

    def _is_hidden(self, tag: str, attrs: Mapping[str, str]) -> bool:
        inherited = bool(self._stack and self._stack[-1]["hidden"])
        style = attrs.get("style", "")
        class_tokens = {token.casefold() for token in attrs.get("class", "").split()}
        return bool(
            inherited
            or tag in HIDDEN_CONTENT_TAGS
            or "hidden" in attrs
            or "inert" in attrs
            or class_tokens.intersection({"d-none", "display-none", "hidden"})
            or attrs.get("aria-hidden", "").casefold() == "true"
            or re.search(r"(?i)(?:display\s*:\s*none|visibility\s*:\s*hidden)", style)
        )

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        normalized_tag = tag.casefold()
        normalized_attrs = self._normalize_attributes(attrs)
        self._element_count += 1
        if self._element_count > MAX_HTML_ELEMENTS or len(self._stack) >= MAX_HTML_DEPTH:
            raise DiscoveryError("external_evidence_HTML_structure_limit")
        hidden = self._is_hidden(normalized_tag, normalized_attrs)
        active_cards = list(self._stack[-1]["active_cards"]) if self._stack else []
        if normalized_tag in CARD_TAGS and not hidden:
            card_id = self._next_card_id
            self._next_card_id += 1
            self.cards[card_id] = {
                "anchor_ordinals": [],
                "depth": len(self._stack),
                "structural_attributes": {
                    key: normalized_attrs[key]
                    for key in ("class", "id", "role")
                    if key in normalized_attrs and len(normalized_attrs[key]) <= 512
                },
                "tag": normalized_tag,
                "text_characters": 0,
                "text_parts": [],
            }
            active_cards.append(card_id)
        frame = {
            "active_cards": active_cards,
            "hidden": hidden,
            "tag": normalized_tag,
        }
        if normalized_tag == "img" and not hidden:
            alt = normalized_attrs.get("alt")
            if alt:
                if len(alt) > 4096:
                    raise DiscoveryError("external_evidence_image_alt_limit")
                self.images.append(
                    {
                        "alt": " ".join(alt.split()),
                        "element_ordinal": self._element_count,
                    }
                )
        if normalized_tag == "a" and not hidden:
            if self._active_anchor is not None or len(self.anchors) >= MAX_ANCHORS:
                raise DiscoveryError("external_evidence_anchor_limit_or_nesting")
            href = normalized_attrs.get("href")
            if href is None or len(href) > 4096:
                raise DiscoveryError("external_evidence_anchor_href_invalid")
            self._active_anchor = {
                "card_ids": list(active_cards),
                "href": href,
                "element_ordinal": self._element_count,
                "ordinal": len(self.anchors),
                "text_characters": 0,
                "text_parts": [],
            }
            for card_id in active_cards:
                self.cards[card_id]["anchor_ordinals"].append(len(self.anchors))
        if normalized_tag not in VOID_HTML_TAGS:
            self._stack.append(frame)

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.handle_starttag(tag, attrs)
        if tag.casefold() not in VOID_HTML_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.casefold()
        if normalized_tag == "a" and self._active_anchor is not None:
            text = " ".join(
                " ".join(self._active_anchor.pop("text_parts")).split()
            )
            self._active_anchor.pop("text_characters")
            self._active_anchor["text"] = text
            self.anchors.append(self._active_anchor)
            self._active_anchor = None
        matching = next(
            (
                index
                for index in range(len(self._stack) - 1, -1, -1)
                if self._stack[index]["tag"] == normalized_tag
            ),
            None,
        )
        if matching is not None:
            del self._stack[matching:]

    def handle_data(self, data: str) -> None:
        if not data.strip() or (self._stack and self._stack[-1]["hidden"]):
            return
        self._visible_text_characters += len(data)
        if self._visible_text_characters > MAX_HTML_VISIBLE_TEXT_CHARACTERS:
            raise DiscoveryError("external_evidence_HTML_visible_text_limit")
        self.text_parts.append(data)
        active_cards = self._stack[-1]["active_cards"] if self._stack else []
        for card_id in active_cards:
            card = self.cards[card_id]
            card["text_characters"] += len(data)
            self._structural_text_characters += len(data)
            if (
                card["text_characters"] > MAX_HTML_SCOPE_TEXT_CHARACTERS
                or self._structural_text_characters
                > MAX_HTML_AGGREGATE_SCOPE_TEXT_CHARACTERS
            ):
                raise DiscoveryError("external_evidence_HTML_card_text_limit")
            card["text_parts"].append(data)
        if self._active_anchor is not None:
            self._active_anchor["text_characters"] += len(data)
            if self._active_anchor["text_characters"] > 4096:
                raise DiscoveryError("external_evidence_anchor_text_limit")
            self._active_anchor["text_parts"].append(data)


def parse_evidence_html(
    payload: bytes,
    *,
    checkpoint: Callable[[str], None] | None = None,
) -> EvidenceHTMLParser:
    try:
        text = payload.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        raise DiscoveryError("external_evidence_HTML_encoding_invalid") from None
    parser = EvidenceHTMLParser()
    try:
        for offset in range(0, len(text), 64 * 1024):
            parser.feed(text[offset : offset + 64 * 1024])
            if checkpoint is not None:
                checkpoint("external_evidence_HTML_parse")
        parser.close()
    except Exception as error:
        if isinstance(error, DiscoveryError):
            raise
        raise DiscoveryError("external_evidence_HTML_parse_invalid") from error
    if parser._active_anchor is not None:
        raise DiscoveryError("external_evidence_unclosed_anchor")
    for card in parser.cards.values():
        text_value = " ".join(" ".join(card.pop("text_parts")).split())
        card.pop("text_characters")
        card["visible_text"] = text_value
    return parser


def canonical_anchor(anchor: Mapping[str, Any], *, page_url: str) -> dict[str, Any]:
    href = anchor.get("href")
    if not isinstance(href, str):
        raise DiscoveryError("external_evidence_anchor_invalid")
    return {
        "card_ids": list(anchor.get("card_ids", ())),
        "element_ordinal": anchor.get("element_ordinal"),
        "href": href,
        "ordinal": anchor.get("ordinal"),
        "resolved_url": urljoin(page_url, href),
        "text": anchor.get("text", ""),
    }


def exact_CC_BY_anchor(value: Mapping[str, Any], version: str) -> bool:
    if version not in {"3.0", "4.0"}:
        raise DiscoveryError("CC_BY_anchor_version_invalid")
    parsed = urlsplit(str(value.get("resolved_url", "")))
    return bool(
        parsed.scheme in {"http", "https"}
        and parsed.hostname == "creativecommons.org"
        and parsed.netloc == "creativecommons.org"
        and parsed.path == f"/licenses/by/{version}/"
        and not parsed.query
        and not parsed.fragment
    )


def egress_anchor(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "href": value["href"],
        "ordinal": value["ordinal"],
        "resolved_url": value["resolved_url"],
        "text": value["text"],
    }


def catalogue_card_selection(
    parser: EvidenceHTMLParser,
    anchor: Mapping[str, Any],
    source: SiyavulaSource,
) -> tuple[int, dict[str, Any]]:
    expected = {(source.catalogue_grade, source.catalogue_subject)}
    candidates = [
        (card_id, parser.cards[card_id])
        for card_id in reversed(anchor.get("card_ids", ()))
        if card_id in parser.cards
        and contextual_assertion_pairs(parser.cards[card_id]["visible_text"])
        == expected
    ]
    association_mode = "exact_subject_grade_in_target_ancestor_card"
    image: Mapping[str, Any] | None = None
    if candidates:
        nearest_depth = max(card["depth"] for _card_id, card in candidates)
        nearest = [
            (card_id, card)
            for card_id, card in candidates
            if card["depth"] == nearest_depth
        ]
        if len(nearest) != 1:
            raise DiscoveryError(
                f"catalogue_card_association_ambiguous:{source.source_id}"
            )
        card_id, card = nearest[0]
    else:
        target_element_ordinal = anchor.get("element_ordinal")
        if type(target_element_ordinal) is not int:
            raise DiscoveryError("catalogue_target_element_ordinal_invalid")
        preceding_images = [
            record
            for record in parser.images
            if record["element_ordinal"] < target_element_ordinal
        ]
        if not preceding_images:
            raise DiscoveryError(
                f"catalogue_card_subject_grade_not_unique:{source.source_id}"
            )
        image = preceding_images[-1]
        if contextual_assertion_pairs(image["alt"]) != expected:
            raise DiscoveryError(
                f"catalogue_nearest_image_subject_grade_mismatch:{source.source_id}"
            )
        active_cards = [
            (card_id, parser.cards[card_id])
            for card_id in anchor.get("card_ids", ())
            if card_id in parser.cards
        ]
        if not active_cards:
            raise DiscoveryError(f"catalogue_target_card_missing:{source.source_id}")
        card_id, card = max(active_cards, key=lambda item: item[1]["depth"])
        association_mode = "nearest_preceding_nonhidden_image_alt"
    context = card["visible_text"]
    return card_id, {
        "association_mode": association_mode,
        "card_anchor_count": len(card["anchor_ordinals"]),
        "card_depth": card["depth"],
        "card_structural_attributes": card["structural_attributes"],
        "card_tag": card["tag"],
        "card_visible_text": context,
        "card_visible_text_sha256": "sha256:"
        + sha256_bytes(context.encode("utf-8")),
        "catalogue_assertion_pairs": [
            {"grade": source.catalogue_grade, "subject": source.catalogue_subject}
        ],
        "expected_catalogue_subject_and_grade_uniquely_asserted": True,
        "hidden_or_noncontent_subtrees_excluded": True,
        "nearest_preceding_image_alt": image["alt"] if image is not None else None,
        "nearest_preceding_image_alt_sha256": (
            "sha256:" + sha256_bytes(image["alt"].encode("utf-8"))
            if image is not None
            else None
        ),
        "nearest_preceding_image_element_ordinal": (
            image["element_ordinal"] if image is not None else None
        ),
        "target_anchor_element_ordinal": anchor["element_ordinal"],
    }


def explicit_collection_license_statement(text: str) -> bool:
    normalized = " ".join(text.casefold().split())
    license_marker = re.search(
        r"\b(?:cc[ -]?by|creative commons attribution)\s*3(?:\.0)?\b",
        normalized,
    )
    collection_marker = re.search(
        r"\b(?:all|our|these|the)\s+(?:open\s+)?"
        r"(?:books?|textbooks?|resources|materials)\b",
        normalized,
    )
    applicability_marker = re.search(
        r"\b(?:are|is)\s+(?:made\s+available\s+under|licensed\s+under|"
        r"licensed|published\s+under|released\s+under|provided\s+under)\b",
        normalized,
    )
    return bool(license_marker and collection_marker and applicability_marker)


def explicit_unbranded_adaptation_statement(text: str) -> bool:
    normalized = " ".join(text.casefold().split())
    return all(
        marker in normalized
        for marker in (
            "unbranded versions",
            "share, adapt, transform, modify or build upon",
            "give appropriate credit to siyavula",
            "creative commons attribution 3.0",
        )
    )


def explicit_target_CC_BY_label(text: str) -> bool:
    return re.fullmatch(r"(?i)epub\s*\(cc-by\)", " ".join(text.split())) is not None


def structural_scope_evidence(
    card: Mapping[str, Any],
    *,
    target_anchor_ordinals: Sequence[int],
    license_anchor_ordinal: int,
    contains_all_target_anchors: bool,
    include_visible_statement: bool,
) -> dict[str, Any]:
    value = {
        "contains_all_target_anchors": contains_all_target_anchors,
        "contains_exact_CC_BY_3_0_anchor": True,
        "license_anchor_ordinal": license_anchor_ordinal,
        "scope_depth": card["depth"],
        "scope_structural_attributes": card["structural_attributes"],
        "scope_tag": card["tag"],
        "scope_visible_text_sha256": "sha256:"
        + sha256_bytes(card["visible_text"].encode("utf-8")),
        "target_anchor_ordinals": list(target_anchor_ordinals),
    }
    if include_visible_statement:
        value["visible_collection_license_statement"] = card["visible_text"]
    return value


def catalogue_license_applicability_preimage(
    parser: EvidenceHTMLParser,
    target_states: Sequence[Mapping[str, Any]],
    catalogue_license_anchors: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    per_target: dict[str, dict[str, Any]] = {}
    unresolved: list[Mapping[str, Any]] = []
    for state in target_states:
        anchors = [
            egress_anchor(anchor)
            for anchor in catalogue_license_anchors
            if state["card_id"] in anchor["card_ids"]
        ]
        if not anchors:
            unresolved.append(state)
            continue
        record = {
            "applicable_license_anchors": anchors,
            "application_mode": "exact_CC_BY_3_0_anchor_within_selected_target_card",
            "selected_target_card_context_sha256": canonical_sha256(
                state["context"]
            ),
            "source_id": state["source"].source_id,
        }
        per_target[state["source"].source_id] = record

    if unresolved:
        statement_candidates: list[tuple[int, Mapping[str, Any], Mapping[str, Any]]] = []
        for license_anchor in catalogue_license_anchors:
            for statement_id in license_anchor["card_ids"]:
                statement = parser.cards[statement_id]
                if explicit_unbranded_adaptation_statement(statement["visible_text"]):
                    statement_candidates.append(
                        (statement["depth"], statement, license_anchor)
                    )
        if statement_candidates and all(
            explicit_target_CC_BY_label(state["anchor"]["text"])
            for state in unresolved
        ):
            _depth, statement, license_anchor = max(
                statement_candidates,
                key=lambda candidate: (candidate[0], -candidate[2]["ordinal"]),
            )
            statement_scope = structural_scope_evidence(
                statement,
                target_anchor_ordinals=(),
                license_anchor_ordinal=license_anchor["ordinal"],
                contains_all_target_anchors=False,
                include_visible_statement=True,
            )
            for state in unresolved:
                label = state["anchor"]["text"]
                per_target[state["source"].source_id] = {
                    "applicable_license_anchors": [egress_anchor(license_anchor)],
                    "application_mode": (
                        "explicit_target_CC_BY_label_plus_scoped_unbranded_"
                        "adaptation_statement"
                    ),
                    "license_statement_scope_evidence": statement_scope,
                    "source_id": state["source"].source_id,
                    "target_anchor_label_evidence": {
                        "text": label,
                        "text_sha256": "sha256:"
                        + sha256_bytes(label.encode("utf-8")),
                    },
                }
            unresolved = []
    if unresolved:
        common_scope_ids = set(target_states[0]["anchor"]["card_ids"])
        for state in target_states[1:]:
            common_scope_ids.intersection_update(state["anchor"]["card_ids"])
        candidates: list[tuple[int, int, int, Mapping[str, Any]]] = []
        for license_anchor in catalogue_license_anchors:
            license_scope_ids = set(license_anchor["card_ids"])
            for collection_id in common_scope_ids & license_scope_ids:
                collection = parser.cards[collection_id]
                for statement_id in license_anchor["card_ids"]:
                    statement = parser.cards[statement_id]
                    if (
                        statement["depth"] >= collection["depth"]
                        and explicit_collection_license_statement(
                            statement["visible_text"]
                        )
                    ):
                        candidates.append(
                            (
                                collection_id,
                                statement_id,
                                license_anchor["ordinal"],
                                license_anchor,
                            )
                        )
        if not candidates:
            raise DiscoveryError(
                "catalogue_CC_BY_3_0_license_not_structurally_applicable_to_targets"
            )
        collection_id, statement_id, _ordinal, license_anchor = max(
            candidates,
            key=lambda candidate: (
                parser.cards[candidate[0]]["depth"],
                parser.cards[candidate[1]]["depth"],
                -candidate[2],
            ),
        )
        target_ordinals = [state["anchor"]["ordinal"] for state in target_states]
        collection_scope = structural_scope_evidence(
            parser.cards[collection_id],
            target_anchor_ordinals=target_ordinals,
            license_anchor_ordinal=license_anchor["ordinal"],
            contains_all_target_anchors=True,
            include_visible_statement=False,
        )
        statement_scope = structural_scope_evidence(
            parser.cards[statement_id],
            target_anchor_ordinals=(),
            license_anchor_ordinal=license_anchor["ordinal"],
            contains_all_target_anchors=False,
            include_visible_statement=True,
        )
        for state in unresolved:
            record = {
                "applicable_license_anchors": [egress_anchor(license_anchor)],
                "application_mode": "visible_collection_scope_statement",
                "collection_scope_evidence": collection_scope,
                "license_statement_scope_evidence": statement_scope,
                "source_id": state["source"].source_id,
            }
            per_target[state["source"].source_id] = record
    records = [per_target[state["source"].source_id] for state in target_states]
    return {
        "applicability_policy": (
            "each_target_requires_exact_CC_BY_3_0_in_selected_card_or_explicit_"
            "visible_collection_statement_in_common_structural_scope"
        ),
        "target_applicability_records": records,
    }


def build_external_evidence_preimage(
    catalogue_payload: bytes,
    catalogue_transport: Mapping[str, Any],
    terms_payload: bytes,
    terms_transport: Mapping[str, Any],
    successful_attempt_bindings: Mapping[str, Mapping[str, Any]],
    checkpoint: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    catalogue = parse_evidence_html(catalogue_payload, checkpoint=checkpoint)
    terms = parse_evidence_html(terms_payload, checkpoint=checkpoint)
    catalogue_anchors = [
        canonical_anchor(anchor, page_url=CATALOGUE_URL)
        for anchor in catalogue.anchors
    ]
    terms_anchors = [
        canonical_anchor(anchor, page_url=TERMS_URL) for anchor in terms.anchors
    ]
    catalogue_license_anchor_candidates = [
        value for value in catalogue_anchors if exact_CC_BY_anchor(value, "3.0")
    ]
    catalogue_license_anchors = [
        egress_anchor(value) for value in catalogue_license_anchor_candidates
    ]
    terms_license_anchors = [
        egress_anchor(value)
        for value in terms_anchors
        if exact_CC_BY_anchor(value, "4.0")
    ]
    if not catalogue_license_anchors or not terms_license_anchors:
        raise DiscoveryError("catalogue_CC_BY_3_or_terms_CC_BY_4_evidence_missing")
    license_preimage = {
        "catalogue_CC_BY_3_0_anchors": catalogue_license_anchors,
        "license_id": "CC-BY-3.0",
    }
    license_root = canonical_sha256(license_preimage)
    terms_visible_text = " ".join(" ".join(terms.text_parts).split())
    normalized_terms_text = terms_visible_text.casefold()
    terms_marked_material_notice_present = all(
        marker in normalized_terms_text
        for marker in (
            "only material that is clearly marked",
            "creative commons license",
            "re-used without permission",
        )
    )
    if not terms_marked_material_notice_present:
        raise DiscoveryError("terms_marked_material_CC_BY_notice_missing")
    terms_license_preimage = {
        "license_id_observed_from_anchor": "CC-BY-4.0",
        "marked_material_only_scope_assertion_present": True,
        "terms_CC_BY_4_0_anchors": terms_license_anchors,
        "terms_visible_text_sha256": "sha256:"
        + sha256_bytes(terms_visible_text.encode("utf-8")),
    }
    terms_license_root = canonical_sha256(terms_license_preimage)
    target_states: list[dict[str, Any]] = []
    for source in SIYAVULA_SOURCES:
        matches = [
            anchor
            for anchor in catalogue_anchors
            if urlsplit(anchor["resolved_url"])._replace(fragment="").geturl()
            == source.url
        ]
        if len(matches) != 1:
            raise DiscoveryError(
                f"catalogue_target_anchor_cardinality:{source.source_id}"
            )
        card_id, context = catalogue_card_selection(
            catalogue,
            matches[0],
            source,
        )
        target_states.append(
            {
                "anchor": matches[0],
                "card_id": card_id,
                "context": context,
                "source": source,
            }
        )
    applicability_preimage = catalogue_license_applicability_preimage(
        catalogue,
        target_states,
        catalogue_license_anchor_candidates,
    )
    applicability_root = canonical_sha256(applicability_preimage)
    target_records: list[dict[str, Any]] = []
    for state, applicability in zip(
        target_states,
        applicability_preimage["target_applicability_records"],
        strict=True,
    ):
        source = state["source"]
        target_records.append(
            {
                "catalogue_grade": source.catalogue_grade,
                "catalogue_license_applicability_root_sha256": applicability_root,
                "catalogue_subject": source.catalogue_subject,
                "download_filename_grade_token": source.filename_grade_token,
                "download_filename_subject_token": source.filename_subject_token,
                "catalogue_CC_BY_3_0_evidence_root_sha256": license_root,
                "license_id": "CC-BY-3.0",
                "source_id": source.source_id,
                "target_anchor": egress_anchor(state["anchor"]),
                "target_context_evidence": state["context"],
                "target_license_applicability_sha256": canonical_sha256(
                    applicability
                ),
            }
        )
    combined_text = " ".join(
        " ".join((*catalogue.text_parts, *terms.text_parts)).split()
    )
    if (
        not catalogue_license_anchors
        or not terms_license_anchors
        or "siyavula" not in combined_text.casefold()
    ):
        raise DiscoveryError("catalogue_or_terms_license_preimage_incomplete")
    return {
        "catalogue": {
            "exact_CC_BY_3_0_evidence_root_sha256": license_root,
            "license_applicability_preimage": applicability_preimage,
            "license_applicability_root_sha256": applicability_root,
            "license_anchor_records": catalogue_license_anchors,
            "page_transport_identity": dict(catalogue_transport),
            "successful_attempt_binding": dict(
                successful_attempt_bindings["catalogue"]
            ),
            "target_anchor_records": target_records,
        },
        "catalogue_and_terms_payloads_observed_phone_side": True,
        "exact_CC_BY_3_0_evidence_preimage": license_preimage,
        "exact_CC_BY_3_0_evidence_root_sha256": license_root,
        "terms_marked_material_CC_BY_4_0_evidence_preimage": (
            terms_license_preimage
        ),
        "terms_marked_material_CC_BY_4_0_evidence_root_sha256": (
            terms_license_root
        ),
        "external_evidence_observation_state": "observed_values",
        "terms": {
            "marked_material_CC_BY_4_0_evidence_root_sha256": terms_license_root,
            "license_anchor_records": terms_license_anchors,
            "page_transport_identity": dict(terms_transport),
            "successful_attempt_binding": dict(successful_attempt_bindings["terms"]),
        },
    }


def external_page_selection_path(epoch: Path, role: str) -> Path:
    if role not in {"catalogue", "terms"}:
        raise DiscoveryError("external_page_role_invalid")
    directory = epoch / "external_page_selections"
    ensure_private_directory(directory)
    return directory / f"{role}.json"


def read_sealed_payload(path: Path, *, max_bytes: int) -> bytes:
    require_sealed_regular_path(path, role="sealed_payload")
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        if before.st_size <= 0 or before.st_size > max_bytes:
            raise DiscoveryError("sealed_payload_size_invalid")
        payload = bytearray()
        while len(payload) < before.st_size:
            chunk = os.read(fd, min(HASH_READ_BYTES, before.st_size - len(payload)))
            if not chunk:
                raise DiscoveryError("sealed_payload_short_read")
            payload.extend(chunk)
        after = os.fstat(fd)
        path_after = os.stat(path, follow_symlinks=False)
        if (
            stat_identity(before) != stat_identity(after)
            or stat_identity(after) != stat_identity(path_after)
        ):
            raise DiscoveryError("sealed_payload_changed")
        return bytes(payload)
    finally:
        os.close(fd)


def validate_external_page_selection(
    root: Path,
    epoch: Path,
    manifest: Mapping[str, Any],
    role: str,
) -> dict[str, Any]:
    selection = read_canonical_json(
        external_page_selection_path(epoch, role),
        schema=PAGE_SELECTION_SCHEMA,
    )
    require_exact_keys(
        selection,
        {
            "attempt_artifact",
            "attempt_sha256",
            "body_bytes",
            "body_sha256",
            "CAS_artifact",
            "resource_observation_artifact",
            "resource_observation_sha256",
            "role",
            "runtime_identity_sha256",
            "schema_version",
            "transport",
        },
        role="external_page_selection",
    )
    attempt_path = resolve_relative_artifact(epoch, selection.get("attempt_artifact"))
    attempt = read_canonical_json(attempt_path, schema=PAGE_ATTEMPT_SCHEMA)
    require_exact_keys(
        attempt,
        {
            "body_bytes",
            "body_sha256",
            "curl_exit_code",
            "curl_held_execution_identity_sha256",
            "eligible_for_external_evidence",
            "failure_reason",
            "one_request_attempt_only",
            "request_count",
            "resource_observation_artifact",
            "resource_observation_sha256",
            "retry_count",
            "role",
            "runtime_identity_sha256",
            "schema_version",
            "stderr_sha256",
            "transport",
            "url",
        },
        role="external_page_attempt",
    )
    resource_path = resolve_relative_artifact(
        epoch, selection.get("resource_observation_artifact")
    )
    validate_resource_observation_binding(
        epoch,
        (
            relative_inside(epoch, resource_path),
            selection.get("resource_observation_sha256"),
        ),
    )
    cas_path = resolve_relative_artifact(root, selection.get("CAS_artifact"))
    payload = read_sealed_payload(cas_path, max_bytes=16 * 1024 * 1024)
    expected_tool = expected_curl_execution_identity(manifest["runtime_identity"])
    if (
        selection.get("role") != role
        or selection.get("attempt_sha256") != file_payload_sha256(attempt_path)
        or selection.get("resource_observation_sha256")
        != file_payload_sha256(resource_path)
        or selection.get("runtime_identity_sha256")
        != manifest["runtime_identity_sha256"]
        or selection.get("body_sha256")
        != "sha256:" + sha256_bytes(payload)
        or selection.get("body_bytes") != len(payload)
        or attempt.get("eligible_for_external_evidence") is not True
        or attempt.get("curl_held_execution_identity_sha256") != expected_tool
        or attempt.get("transport") != selection.get("transport")
    ):
        raise DiscoveryError("external_page_selection_invalid")
    return {**selection, "body": payload}


def capture_one_external_page_locked(
    root: Path,
    epoch: Path,
    manifest: Mapping[str, Any],
    *,
    role: str,
    url: str,
    executor: PageExecutor,
    resource_observer: Callable[[], tuple[str, str]],
) -> dict[str, Any]:
    selection_path = external_page_selection_path(epoch, role)
    if selection_path.exists():
        return validate_external_page_selection(root, epoch, manifest, role)
    resource_observation = validate_resource_observation_binding(
        epoch,
        resource_observer(),
    )
    instant = utc_now()
    ensure_circuit_allows(root, now=instant)
    reservation = record_request_intent(
        root,
        source_id=f"external_{role}",
        chunk_index=-1,
        resource_observation_sha256=resource_observation[1],
        now=instant,
    )
    try:
        outcome = executor(url)
    except Exception as error:
        outcome = RangeOutcome(-1, b"", b"", type(error).__name__.encode("ascii"))
    failure: str | None = None
    transport: dict[str, Any] | None = None
    expected_tool = expected_curl_execution_identity(manifest["runtime_identity"])
    if outcome.tool_identity_sha256 != expected_tool:
        failure = "curl_held_execution_identity_mismatch"
    if failure is None:
        try:
            transport = validate_page_outcome(url, outcome)
        except DiscoveryError as error:
            failure = str(error)
    cas_path: Path | None = None
    if failure is None:
        cas_path, _digest = publish_cas_blob(root, outcome.body)
    attempt = {
        "body_bytes": len(outcome.body),
        "body_sha256": "sha256:" + sha256_bytes(outcome.body),
        "curl_exit_code": outcome.exit_code,
        "curl_held_execution_identity_sha256": outcome.tool_identity_sha256,
        "eligible_for_external_evidence": failure is None,
        "failure_reason": failure,
        "one_request_attempt_only": True,
        "request_count": 1,
        "resource_observation_artifact": resource_observation[0],
        "resource_observation_sha256": resource_observation[1],
        "retry_count": 0,
        "role": role,
        "runtime_identity_sha256": manifest["runtime_identity_sha256"],
        "schema_version": PAGE_ATTEMPT_SCHEMA,
        "stderr_sha256": "sha256:" + sha256_bytes(outcome.stderr),
        "transport": transport,
        "url": url,
    }
    attempts = epoch / "external_page_attempts"
    ensure_private_directory(attempts)
    attempt_path = attempts / f"{role}-{uuid.uuid4().hex}.json"
    attempt_sha = publish_immutable_json(attempt_path, attempt)
    if failure is not None or cas_path is None or transport is None:
        raise CircuitOpen(
            f"external_evidence_failed_open_until:{reservation['open_until_utc']}"
        )
    selection = {
        "attempt_artifact": relative_inside(epoch, attempt_path),
        "attempt_sha256": attempt_sha,
        "body_bytes": len(outcome.body),
        "body_sha256": "sha256:" + sha256_bytes(outcome.body),
        "CAS_artifact": relative_inside(root, cas_path),
        "resource_observation_artifact": resource_observation[0],
        "resource_observation_sha256": resource_observation[1],
        "role": role,
        "runtime_identity_sha256": manifest["runtime_identity_sha256"],
        "schema_version": PAGE_SELECTION_SCHEMA,
        "transport": transport,
    }
    publish_immutable_json(selection_path, selection)
    record_circuit_success(
        root,
        source_id=f"external_{role}",
        chunk_index=-1,
        attempt_sha256=attempt_sha,
    )
    return validate_external_page_selection(root, epoch, manifest, role)


def capture_external_evidence(
    epoch: Path,
    *,
    executor: PageExecutor,
    runtime_identity: Mapping[str, Any],
    lease: DiscoveryLease,
) -> dict[str, Any]:
    root, epoch, manifest = validate_epoch(epoch)
    require_epoch_runtime(manifest, runtime_identity)
    require_lease_epoch(lease, epoch)
    evidence_path = epoch / "external_evidence.json"
    if evidence_path.exists():
        existing = validate_external_evidence(
            root,
            epoch,
            checkpoint=lambda phase: lease.checkpoint(phase=phase),
        )
        publish_selection_ready_binding(root, epoch, manifest, existing)
        return existing
    observations: dict[str, dict[str, Any]] = {}
    with epoch_lock(epoch):
        for role, url in (("catalogue", CATALOGUE_URL), ("terms", TERMS_URL)):
            with origin_lock(root):
                observations[role] = capture_one_external_page_locked(
                    root,
                    epoch,
                    manifest,
                    role=role,
                    url=url,
                    executor=executor,
                    resource_observer=lambda current_role=role: lease.observe(
                        phase=f"before_external_evidence:{current_role}"
                    ),
                )
            lease.observe(phase=f"after_external_evidence:{role}")
        bindings = {
            role: {
                "attempt_sha256": observations[role]["attempt_sha256"],
                "resource_observation_sha256": observations[role][
                    "resource_observation_sha256"
                ],
                "runtime_identity_sha256": observations[role][
                    "runtime_identity_sha256"
                ],
            }
            for role in ("catalogue", "terms")
        }
        preimage = build_external_evidence_preimage(
            observations["catalogue"]["body"],
            observations["catalogue"]["transport"],
            observations["terms"]["body"],
            observations["terms"]["transport"],
            bindings,
            checkpoint=lambda phase: lease.checkpoint(phase=phase),
        )
        evidence = {
            "egress_preimage": preimage,
            "egress_preimage_sha256": canonical_sha256(preimage),
            "raw_page_egress_forbidden": True,
            "schema_version": EXTERNAL_EVIDENCE_SCHEMA,
            "successful_page_attempts": {
                role: {
                    key: value
                    for key, value in observations[role].items()
                    if key not in {"body", "transport"}
                }
                for role in ("catalogue", "terms")
            },
        }
        publish_immutable_json(evidence_path, evidence)
    validated = validate_external_evidence(
        root,
        epoch,
        checkpoint=lambda phase: lease.checkpoint(phase=phase),
    )
    publish_selection_ready_binding(root, epoch, manifest, validated)
    return validated


def validate_page_transport_closed(value: Any, *, expected_url: str) -> None:
    transport = require_exact_keys(
        value,
        {
            "body_bytes",
            "body_sha256",
            "content_encoding",
            "content_length_header",
            "content_type",
            "etag",
            "headers_sha256",
            "last_modified",
            "request_count",
            "retry_count",
            "status_code",
            "url",
        },
        role="external_page_transport",
    )
    if (
        type(transport["body_bytes"]) is not int
        or not 1 <= transport["body_bytes"] <= 16 * 1024 * 1024
        or transport["request_count"] != 1
        or transport["retry_count"] != 0
        or transport["status_code"] != 200
        or transport["url"] != expected_url
    ):
        raise DiscoveryError("external_page_transport_value_invalid")
    require_sha256(transport["body_sha256"], role="external_page_body")
    require_sha256(transport["headers_sha256"], role="external_page_headers")
    for field in (
        "content_encoding",
        "content_length_header",
        "etag",
        "last_modified",
    ):
        if transport[field] is not None:
            require_bounded_string(
                transport[field], role=f"external_{field}", maximum=4096
            )
    require_bounded_string(
        transport["content_type"], role="external_content_type", maximum=512
    )


def validate_egress_anchor(value: Any, *, role: str) -> None:
    anchor = require_exact_keys(
        value,
        {"href", "ordinal", "resolved_url", "text"},
        role=role,
    )
    if type(anchor["ordinal"]) is not int or not 0 <= anchor["ordinal"] < MAX_ANCHORS:
        raise DiscoveryError(f"{role}_ordinal_invalid")
    require_bounded_string(anchor["href"], role=role, maximum=4096)
    require_bounded_string(anchor["resolved_url"], role=role, maximum=4096)
    require_bounded_string(anchor["text"], role=role, maximum=4096, allow_empty=True)


def validate_structural_attributes(value: Any, *, role: str) -> None:
    if type(value) is not dict or not set(value).issubset({"class", "id", "role"}):
        raise DiscoveryError(f"{role}_invalid")
    for attribute in value.values():
        require_bounded_string(
            attribute,
            role=role,
            maximum=512,
            allow_empty=True,
        )


def validate_license_scope_evidence(
    value: Any,
    *,
    role: str,
    statement: bool,
) -> None:
    keys = {
        "contains_all_target_anchors",
        "contains_exact_CC_BY_3_0_anchor",
        "license_anchor_ordinal",
        "scope_depth",
        "scope_structural_attributes",
        "scope_tag",
        "scope_visible_text_sha256",
        "target_anchor_ordinals",
    }
    if statement:
        keys.add("visible_collection_license_statement")
    scope = require_exact_keys(value, keys, role=role)
    if (
        scope["contains_all_target_anchors"] is not (not statement)
        or scope["contains_exact_CC_BY_3_0_anchor"] is not True
        or type(scope["license_anchor_ordinal"]) is not int
        or not 0 <= scope["license_anchor_ordinal"] < MAX_ANCHORS
        or type(scope["scope_depth"]) is not int
        or not 0 <= scope["scope_depth"] < MAX_HTML_DEPTH
        or scope["scope_tag"] not in CARD_TAGS
    ):
        raise DiscoveryError(f"{role}_value_invalid")
    validate_structural_attributes(
        scope["scope_structural_attributes"],
        role=f"{role}_attributes",
    )
    require_sha256(scope["scope_visible_text_sha256"], role=f"{role}_text")
    ordinals = scope["target_anchor_ordinals"]
    if (
        type(ordinals) is not list
        or len(ordinals) > len(SIYAVULA_SOURCES)
        or len(ordinals) != len(set(ordinals))
        or any(type(ordinal) is not int or not 0 <= ordinal < MAX_ANCHORS for ordinal in ordinals)
        or (statement and ordinals)
        or (not statement and len(ordinals) != len(SIYAVULA_SOURCES))
    ):
        raise DiscoveryError(f"{role}_target_ordinals_invalid")
    if statement:
        visible = require_bounded_string(
            scope["visible_collection_license_statement"],
            role=f"{role}_statement",
            maximum=MAX_HTML_CARD_TEXT_CHARACTERS,
        )
        if (
            not (
                explicit_collection_license_statement(visible)
                or explicit_unbranded_adaptation_statement(visible)
            )
            or scope["scope_visible_text_sha256"]
            != "sha256:" + sha256_bytes(visible.encode("utf-8"))
        ):
            raise DiscoveryError(f"{role}_statement_invalid")


def validate_catalogue_license_applicability(
    value: Any,
    *,
    catalogue_license_anchors: Sequence[Mapping[str, Any]],
    target_anchors: Sequence[Mapping[str, Any]],
    target_contexts: Sequence[Mapping[str, Any]],
    target_anchor_ordinals: Sequence[int],
) -> None:
    preimage = require_exact_keys(
        value,
        {"applicability_policy", "target_applicability_records"},
        role="catalogue_license_applicability",
    )
    if preimage["applicability_policy"] != (
        "each_target_requires_exact_CC_BY_3_0_in_selected_card_or_explicit_"
        "visible_collection_statement_in_common_structural_scope"
    ):
        raise DiscoveryError("catalogue_license_applicability_policy_invalid")
    records = preimage["target_applicability_records"]
    if type(records) is not list or len(records) != len(SIYAVULA_SOURCES):
        raise DiscoveryError("catalogue_license_applicability_roster_invalid")
    allowed_anchors = [dict(anchor) for anchor in catalogue_license_anchors]
    for source, target_anchor, context, record in zip(
        SIYAVULA_SOURCES,
        target_anchors,
        target_contexts,
        records,
        strict=True,
    ):
        if type(record) is not dict:
            raise DiscoveryError("catalogue_target_applicability_invalid")
        mode = record.get("application_mode")
        keys = {
            "applicable_license_anchors",
            "application_mode",
            "source_id",
        }
        if mode == "exact_CC_BY_3_0_anchor_within_selected_target_card":
            keys.add("selected_target_card_context_sha256")
        elif mode == (
            "explicit_target_CC_BY_label_plus_scoped_unbranded_"
            "adaptation_statement"
        ):
            keys.update(
                {
                    "license_statement_scope_evidence",
                    "target_anchor_label_evidence",
                }
            )
        elif mode == "visible_collection_scope_statement":
            keys.update(
                {
                    "collection_scope_evidence",
                    "license_statement_scope_evidence",
                }
            )
        else:
            raise DiscoveryError("catalogue_target_applicability_mode_invalid")
        closed = require_exact_keys(record, keys, role="catalogue_target_applicability")
        anchors = closed["applicable_license_anchors"]
        if (
            closed["source_id"] != source.source_id
            or type(anchors) is not list
            or not 1 <= len(anchors) <= 64
        ):
            raise DiscoveryError("catalogue_target_applicability_value_invalid")
        for anchor in anchors:
            validate_egress_anchor(anchor, role="catalogue_applicable_license_anchor")
            if dict(anchor) not in allowed_anchors:
                raise DiscoveryError("catalogue_applicable_license_anchor_unbound")
        if mode == "exact_CC_BY_3_0_anchor_within_selected_target_card":
            if closed["selected_target_card_context_sha256"] != canonical_sha256(
                context
            ):
                raise DiscoveryError("catalogue_per_card_license_scope_invalid")
            continue
        if mode == (
            "explicit_target_CC_BY_label_plus_scoped_unbranded_"
            "adaptation_statement"
        ):
            label = require_exact_keys(
                closed["target_anchor_label_evidence"],
                {"text", "text_sha256"},
                role="catalogue_target_CC_BY_label",
            )
            label_text = require_bounded_string(
                label["text"], role="catalogue_target_CC_BY_label", maximum=4096
            )
            if (
                label_text != target_anchor["text"]
                or not explicit_target_CC_BY_label(label_text)
                or label["text_sha256"]
                != "sha256:" + sha256_bytes(label_text.encode("utf-8"))
            ):
                raise DiscoveryError("catalogue_target_CC_BY_label_invalid")
            validate_license_scope_evidence(
                closed["license_statement_scope_evidence"],
                role="catalogue_unbranded_license_statement_scope",
                statement=True,
            )
            if not explicit_unbranded_adaptation_statement(
                closed["license_statement_scope_evidence"][
                    "visible_collection_license_statement"
                ]
            ):
                raise DiscoveryError("catalogue_unbranded_statement_invalid")
            continue
        validate_license_scope_evidence(
            closed["collection_scope_evidence"],
            role="catalogue_collection_scope",
            statement=False,
        )
        validate_license_scope_evidence(
            closed["license_statement_scope_evidence"],
            role="catalogue_license_statement_scope",
            statement=True,
        )
        collection_scope = closed["collection_scope_evidence"]
        statement_scope = closed["license_statement_scope_evidence"]
        if (
            collection_scope["target_anchor_ordinals"]
            != list(target_anchor_ordinals)
            or collection_scope["license_anchor_ordinal"]
            != anchors[0]["ordinal"]
            or statement_scope["license_anchor_ordinal"]
            != anchors[0]["ordinal"]
            or statement_scope["scope_depth"] < collection_scope["scope_depth"]
        ):
            raise DiscoveryError("catalogue_collection_license_scope_invalid")


def validate_external_preimage_closed(value: Any) -> None:
    preimage = require_exact_keys(
        value,
        {
            "catalogue",
            "catalogue_and_terms_payloads_observed_phone_side",
            "exact_CC_BY_3_0_evidence_preimage",
            "exact_CC_BY_3_0_evidence_root_sha256",
            "external_evidence_observation_state",
            "terms",
            "terms_marked_material_CC_BY_4_0_evidence_preimage",
            "terms_marked_material_CC_BY_4_0_evidence_root_sha256",
        },
        role="external_evidence_preimage",
    )
    if (
        preimage["catalogue_and_terms_payloads_observed_phone_side"] is not True
        or preimage["external_evidence_observation_state"] != "observed_values"
    ):
        raise DiscoveryError("external_evidence_preimage_state_invalid")
    license_preimage = require_exact_keys(
        preimage["exact_CC_BY_3_0_evidence_preimage"],
        {
            "catalogue_CC_BY_3_0_anchors",
            "license_id",
        },
        role="CC_BY_3_evidence_preimage",
    )
    if (
        license_preimage["license_id"] != "CC-BY-3.0"
        or preimage["exact_CC_BY_3_0_evidence_root_sha256"]
        != canonical_sha256(license_preimage)
    ):
        raise DiscoveryError("CC_BY_3_evidence_root_invalid")
    catalogue_license_anchors = license_preimage["catalogue_CC_BY_3_0_anchors"]
    if (
        type(catalogue_license_anchors) is not list
        or not 1 <= len(catalogue_license_anchors) <= 64
    ):
        raise DiscoveryError("CC_BY_3_anchor_roster_invalid")
    for anchor in catalogue_license_anchors:
        validate_egress_anchor(anchor, role="CC_BY_3_anchor")
        if not exact_CC_BY_anchor(anchor, "3.0"):
            raise DiscoveryError("CC_BY_3_anchor_URL_invalid")
    terms_license_preimage = require_exact_keys(
        preimage["terms_marked_material_CC_BY_4_0_evidence_preimage"],
        {
            "license_id_observed_from_anchor",
            "marked_material_only_scope_assertion_present",
            "terms_CC_BY_4_0_anchors",
            "terms_visible_text_sha256",
        },
        role="terms_marked_material_CC_BY_4_evidence_preimage",
    )
    if (
        terms_license_preimage["license_id_observed_from_anchor"] != "CC-BY-4.0"
        or terms_license_preimage["marked_material_only_scope_assertion_present"]
        is not True
        or preimage["terms_marked_material_CC_BY_4_0_evidence_root_sha256"]
        != canonical_sha256(terms_license_preimage)
    ):
        raise DiscoveryError("terms_marked_material_CC_BY_4_evidence_root_invalid")
    require_sha256(
        terms_license_preimage["terms_visible_text_sha256"],
        role="terms_visible_text",
    )
    terms_license_anchors = terms_license_preimage["terms_CC_BY_4_0_anchors"]
    if type(terms_license_anchors) is not list or not 1 <= len(terms_license_anchors) <= 64:
        raise DiscoveryError("CC_BY_4_anchor_roster_invalid")
    for anchor in terms_license_anchors:
        validate_egress_anchor(anchor, role="CC_BY_4_anchor")
        if not exact_CC_BY_anchor(anchor, "4.0"):
            raise DiscoveryError("CC_BY_4_anchor_URL_invalid")
    for role, expected_url in (("catalogue", CATALOGUE_URL), ("terms", TERMS_URL)):
        evidence_root_field = (
            "exact_CC_BY_3_0_evidence_root_sha256"
            if role == "catalogue"
            else "marked_material_CC_BY_4_0_evidence_root_sha256"
        )
        expected_keys = {
            evidence_root_field,
            "license_anchor_records",
            "page_transport_identity",
            "successful_attempt_binding",
        }
        if role == "catalogue":
            expected_keys.update(
                {
                    "license_applicability_preimage",
                    "license_applicability_root_sha256",
                    "target_anchor_records",
                }
            )
        section = require_exact_keys(
            preimage[role], expected_keys, role=f"external_{role}"
        )
        if (
            section[evidence_root_field]
            != (
                preimage["exact_CC_BY_3_0_evidence_root_sha256"]
                if role == "catalogue"
                else preimage[
                    "terms_marked_material_CC_BY_4_0_evidence_root_sha256"
                ]
            )
            or section["license_anchor_records"]
            != (
                catalogue_license_anchors
                if role == "catalogue"
                else terms_license_anchors
            )
        ):
            raise DiscoveryError(f"external_{role}_license_binding_invalid")
        validate_page_transport_closed(
            section["page_transport_identity"], expected_url=expected_url
        )
        binding = require_exact_keys(
            section["successful_attempt_binding"],
            {
                "attempt_sha256",
                "resource_observation_sha256",
                "runtime_identity_sha256",
            },
            role=f"external_{role}_attempt_binding",
        )
        for field in binding:
            require_sha256(binding[field], role=f"external_{role}_{field}")
    targets = preimage["catalogue"]["target_anchor_records"]
    if type(targets) is not list or len(targets) != len(SIYAVULA_SOURCES):
        raise DiscoveryError("external_target_roster_invalid")
    applicability_preimage = preimage["catalogue"][
        "license_applicability_preimage"
    ]
    applicability_root = preimage["catalogue"][
        "license_applicability_root_sha256"
    ]
    if applicability_root != canonical_sha256(applicability_preimage):
        raise DiscoveryError("catalogue_license_applicability_root_invalid")
    applicability_records = applicability_preimage.get(
        "target_applicability_records", []
    )
    if (
        type(applicability_records) is not list
        or len(applicability_records) != len(SIYAVULA_SOURCES)
    ):
        raise DiscoveryError("catalogue_license_applicability_roster_invalid")
    contexts: list[Mapping[str, Any]] = []
    target_ordinals: list[int] = []
    for source, target, applicability in zip(
        SIYAVULA_SOURCES,
        targets,
        applicability_records,
        strict=True,
    ):
        record = require_exact_keys(
            target,
            {
                "catalogue_grade",
                "catalogue_license_applicability_root_sha256",
                "catalogue_subject",
                "catalogue_CC_BY_3_0_evidence_root_sha256",
                "download_filename_grade_token",
                "download_filename_subject_token",
                "license_id",
                "source_id",
                "target_anchor",
                "target_context_evidence",
                "target_license_applicability_sha256",
            },
            role="catalogue_target_record",
        )
        context = require_exact_keys(
            record["target_context_evidence"],
            {
                "association_mode",
                "card_anchor_count",
                "card_depth",
                "card_structural_attributes",
                "card_tag",
                "card_visible_text",
                "card_visible_text_sha256",
                "catalogue_assertion_pairs",
                "expected_catalogue_subject_and_grade_uniquely_asserted",
                "hidden_or_noncontent_subtrees_excluded",
                "nearest_preceding_image_alt",
                "nearest_preceding_image_alt_sha256",
                "nearest_preceding_image_element_ordinal",
                "target_anchor_element_ordinal",
            },
            role="catalogue_target_context",
        )
        validate_structural_attributes(
            context["card_structural_attributes"],
            role="catalogue_card_attributes",
        )
        visible_text = require_bounded_string(
            context["card_visible_text"],
            role="catalogue_card_visible_text",
            maximum=MAX_HTML_CARD_TEXT_CHARACTERS,
        )
        association_mode = context["association_mode"]
        target_element_ordinal = context["target_anchor_element_ordinal"]
        if type(target_element_ordinal) is not int or target_element_ordinal <= 0:
            raise DiscoveryError("catalogue_target_element_ordinal_invalid")
        if association_mode == "exact_subject_grade_in_target_ancestor_card":
            if any(
                context[field] is not None
                for field in (
                    "nearest_preceding_image_alt",
                    "nearest_preceding_image_alt_sha256",
                    "nearest_preceding_image_element_ordinal",
                )
            ):
                raise DiscoveryError("catalogue_card_association_evidence_invalid")
            if contextual_assertion_pairs(visible_text) != {
                (source.catalogue_grade, source.catalogue_subject)
            }:
                raise DiscoveryError("catalogue_card_assertion_invalid")
        elif association_mode == "nearest_preceding_nonhidden_image_alt":
            image_alt = require_bounded_string(
                context["nearest_preceding_image_alt"],
                role="catalogue_image_alt",
                maximum=4096,
            )
            image_ordinal = context["nearest_preceding_image_element_ordinal"]
            if (
                type(image_ordinal) is not int
                or not 0 < image_ordinal < target_element_ordinal
                or context["nearest_preceding_image_alt_sha256"]
                != "sha256:" + sha256_bytes(image_alt.encode("utf-8"))
                or contextual_assertion_pairs(image_alt)
                != {(source.catalogue_grade, source.catalogue_subject)}
            ):
                raise DiscoveryError("catalogue_image_association_evidence_invalid")
        else:
            raise DiscoveryError("catalogue_association_mode_invalid")
        if (
            record["source_id"] != source.source_id
            or record["catalogue_grade"] != source.catalogue_grade
            or record["catalogue_subject"] != source.catalogue_subject
            or record["download_filename_grade_token"]
            != source.filename_grade_token
            or record["download_filename_subject_token"]
            != source.filename_subject_token
            or record["license_id"] != "CC-BY-3.0"
            or record["catalogue_CC_BY_3_0_evidence_root_sha256"]
            != preimage["exact_CC_BY_3_0_evidence_root_sha256"]
            or record["catalogue_license_applicability_root_sha256"]
            != applicability_root
            or record["target_license_applicability_sha256"]
            != canonical_sha256(applicability)
            or context["expected_catalogue_subject_and_grade_uniquely_asserted"]
            is not True
            or context["hidden_or_noncontent_subtrees_excluded"] is not True
            or type(context["card_anchor_count"]) is not int
            or context["card_anchor_count"] <= 0
            or type(context["card_depth"]) is not int
            or not 0 <= context["card_depth"] < MAX_HTML_DEPTH
            or context["card_tag"] not in CARD_TAGS
            or context["card_visible_text_sha256"]
            != "sha256:" + sha256_bytes(visible_text.encode("utf-8"))
            or context["catalogue_assertion_pairs"]
            != [{"grade": source.catalogue_grade, "subject": source.catalogue_subject}]
        ):
            raise DiscoveryError("catalogue_target_context_value_invalid")
        validate_egress_anchor(record["target_anchor"], role="catalogue_target_anchor")
        if (
            urlsplit(record["target_anchor"]["resolved_url"])
            ._replace(fragment="")
            .geturl()
            != source.url
        ):
            raise DiscoveryError("catalogue_target_anchor_URL_invalid")
        contexts.append(context)
        target_ordinals.append(record["target_anchor"]["ordinal"])
    validate_catalogue_license_applicability(
        applicability_preimage,
        catalogue_license_anchors=preimage["catalogue"]["license_anchor_records"],
        target_anchors=[target["target_anchor"] for target in targets],
        target_contexts=contexts,
        target_anchor_ordinals=target_ordinals,
    )


def validate_external_evidence(
    root: Path,
    epoch: Path,
    *,
    checkpoint: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    evidence = read_canonical_json(
        epoch / "external_evidence.json",
        schema=EXTERNAL_EVIDENCE_SCHEMA,
    )
    require_exact_keys(
        evidence,
        {
            "egress_preimage",
            "egress_preimage_sha256",
            "raw_page_egress_forbidden",
            "schema_version",
            "successful_page_attempts",
        },
        role="external_evidence_artifact",
    )
    preimage = evidence.get("egress_preimage")
    validate_external_preimage_closed(preimage)
    if (
        not isinstance(preimage, dict)
        or preimage.get("external_evidence_observation_state") != "observed_values"
        or evidence.get("egress_preimage_sha256") != canonical_sha256(preimage)
        or evidence.get("raw_page_egress_forbidden") is not True
    ):
        raise DiscoveryError("external_evidence_preimage_invalid")
    attempts = evidence.get("successful_page_attempts")
    require_exact_keys(
        attempts,
        {"catalogue", "terms"},
        role="external_successful_page_attempts",
    )
    if not isinstance(attempts, dict):
        raise DiscoveryError("external_evidence_attempt_bindings_missing")
    manifest = read_canonical_json(epoch / "epoch.json", schema=EPOCH_SCHEMA)
    live_pages: dict[str, dict[str, Any]] = {}
    live_bindings: dict[str, dict[str, Any]] = {}
    for role in ("catalogue", "terms"):
        binding = attempts[role]
        require_exact_keys(
            binding,
            {
                "attempt_artifact",
                "attempt_sha256",
                "body_bytes",
                "body_sha256",
                "CAS_artifact",
                "resource_observation_artifact",
                "resource_observation_sha256",
                "role",
                "runtime_identity_sha256",
                "schema_version",
            },
            role="external_page_attempt_projection",
        )
        live_selection = validate_external_page_selection(
            root,
            epoch,
            manifest,
            role,
        )
        live_pages[role] = live_selection
        attempt_path = resolve_relative_artifact(epoch, binding.get("attempt_artifact"))
        attempt = read_canonical_json(attempt_path, schema=PAGE_ATTEMPT_SCHEMA)
        resource_path = resolve_relative_artifact(
            epoch, binding.get("resource_observation_artifact")
        )
        read_canonical_json(resource_path, schema=RESOURCE_OBSERVATION_SCHEMA)
        cas_path = resolve_relative_artifact(root, binding.get("CAS_artifact"))
        payload = read_sealed_payload(cas_path, max_bytes=16 * 1024 * 1024)
        digest = sha256_bytes(payload)
        size = len(payload)
        transport = preimage[role]["page_transport_identity"]
        egress_binding = preimage[role]["successful_attempt_binding"]
        if (
            "sha256:" + digest != transport["body_sha256"]
            or size != transport["body_bytes"]
            or binding.get("attempt_sha256") != file_payload_sha256(attempt_path)
            or binding.get("resource_observation_sha256")
            != file_payload_sha256(resource_path)
            or binding.get("runtime_identity_sha256")
            != manifest["runtime_identity_sha256"]
            or {
                key: live_selection[key]
                for key in (
                    "attempt_artifact",
                    "attempt_sha256",
                    "body_bytes",
                    "body_sha256",
                    "CAS_artifact",
                    "resource_observation_artifact",
                    "resource_observation_sha256",
                    "role",
                    "runtime_identity_sha256",
                    "schema_version",
                )
            }
            != dict(binding)
            or attempt.get("eligible_for_external_evidence") is not True
            or attempt.get("one_request_attempt_only") is not True
            or attempt.get("request_count") != 1
            or attempt.get("retry_count") != 0
            or attempt.get("body_sha256") != transport["body_sha256"]
            or attempt.get("body_bytes") != transport["body_bytes"]
            or attempt.get("runtime_identity_sha256")
            != binding.get("runtime_identity_sha256")
            or attempt.get("resource_observation_sha256")
            != binding.get("resource_observation_sha256")
            or attempt.get("transport") != transport
            or egress_binding
            != {
                "attempt_sha256": binding["attempt_sha256"],
                "resource_observation_sha256": binding[
                    "resource_observation_sha256"
                ],
                "runtime_identity_sha256": binding["runtime_identity_sha256"],
            }
        ):
            raise DiscoveryError("external_evidence_CAS_identity_invalid")
        live_bindings[role] = {
            "attempt_sha256": binding["attempt_sha256"],
            "resource_observation_sha256": binding[
                "resource_observation_sha256"
            ],
            "runtime_identity_sha256": binding["runtime_identity_sha256"],
        }
    targets = preimage["catalogue"].get("target_anchor_records")
    if (
        not isinstance(targets, list)
        or len(targets) != len(SIYAVULA_SOURCES)
        or [record.get("source_id") for record in targets]
        != [source.source_id for source in SIYAVULA_SOURCES]
    ):
        raise DiscoveryError("external_evidence_target_roster_invalid")
    rebuilt_preimage = build_external_evidence_preimage(
        live_pages["catalogue"]["body"],
        live_pages["catalogue"]["transport"],
        live_pages["terms"]["body"],
        live_pages["terms"]["transport"],
        live_bindings,
        checkpoint=checkpoint,
    )
    if rebuilt_preimage != preimage:
        raise DiscoveryError("external_evidence_live_DOM_revalidation_mismatch")
    return evidence


def selection_ready_path(epoch: Path) -> Path:
    return epoch / "SELECTION_READY.json"


def publish_selection_ready_binding(
    root: Path,
    epoch: Path,
    manifest: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    del root
    preimage = evidence["egress_preimage"]
    targets = preimage["catalogue"]["target_anchor_records"]
    target_bindings = [
        {
            "catalogue_grade": target["catalogue_grade"],
            "catalogue_license_applicability_root_sha256": target[
                "catalogue_license_applicability_root_sha256"
            ],
            "catalogue_subject": target["catalogue_subject"],
            "catalogue_CC_BY_3_0_evidence_root_sha256": target[
                "catalogue_CC_BY_3_0_evidence_root_sha256"
            ],
            "source_id": target["source_id"],
            "target_context_observation_sha256": canonical_sha256(
                target["target_context_evidence"]
            ),
            "target_license_applicability_sha256": target[
                "target_license_applicability_sha256"
            ],
        }
        for target in targets
    ]
    value = {
        "epoch_id": manifest["epoch_id"],
        "external_evidence_artifact_sha256": file_payload_sha256(
            epoch / "external_evidence.json"
        ),
        "external_evidence_preimage_sha256": evidence["egress_preimage_sha256"],
        "exact_CC_BY_3_0_evidence_root_sha256": preimage[
            "exact_CC_BY_3_0_evidence_root_sha256"
        ],
        "terms_marked_material_CC_BY_4_0_evidence_root_sha256": preimage[
            "terms_marked_material_CC_BY_4_0_evidence_root_sha256"
        ],
        "runtime_identity_sha256": manifest["runtime_identity_sha256"],
        "schema_version": SELECTION_BINDING_SCHEMA,
        "selection_ready": True,
        "source_roster_sha256": manifest["source_roster_sha256"],
        "target_binding_root_sha256": canonical_sha256(target_bindings),
        "target_bindings": target_bindings,
    }
    path = selection_ready_path(epoch)
    if path.exists():
        existing = read_canonical_json(path, schema=SELECTION_BINDING_SCHEMA)
        if existing != value:
            raise DiscoveryError("selection_ready_binding_changed")
        return existing
    publish_immutable_json(path, value)
    return value


def validate_selection_ready_binding(
    root: Path,
    epoch: Path,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    evidence = validate_external_evidence(root, epoch)
    binding = read_canonical_json(
        selection_ready_path(epoch),
        schema=SELECTION_BINDING_SCHEMA,
    )
    expected = publish_selection_ready_binding(root, epoch, manifest, evidence)
    if binding != expected or binding.get("selection_ready") is not True:
        raise DiscoveryError("selection_ready_binding_invalid")
    return binding


def hash_held_fd(fd: int) -> tuple[str, int, tuple[int, ...]]:
    before = os.fstat(fd)
    os.lseek(fd, 0, os.SEEK_SET)
    with os.fdopen(os.dup(fd), "rb", closefd=True) as stream:
        digest, size = hash_stream(stream)
    after = os.fstat(fd)
    before_identity = stat_identity(before)
    after_identity = stat_identity(after)
    if before_identity != after_identity or size != before.st_size:
        raise DiscoveryError("held_file_changed_while_hashing")
    return digest, size, after_identity


def inspect_source_identity(
    root: Path,
    epoch: Path,
    source: SiyavulaSource,
    *,
    before_resource_observation: tuple[str, str],
    after_resource_observer: Callable[[], tuple[str, str]],
    checkpoint: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    before_resource_observation = validate_resource_observation_binding(
        epoch,
        before_resource_observation,
    )
    assembly = assemble_source(root, epoch, source)
    chunk_count = (source.expected_bytes + CHUNK_BYTES - 1) // CHUNK_BYTES
    # Revalidate every selected CAS immediately before opening the assembled
    # inode.  No assembly receipt can substitute for the live chunk evidence.
    for chunk_index in range(chunk_count):
        validate_selected_chunk(root, epoch, source, chunk_index)
    assembled_path = resolve_relative_artifact(epoch, assembly["assembled_artifact"])
    fd = os.open(assembled_path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        before_hash, before_bytes, held_identity = hash_held_fd(fd)
        if (
            before_hash != assembly["whole_file_sha256_pass_1"]
            or before_bytes != source.expected_bytes
        ):
            raise DiscoveryError("assembly_changed_before_identity_inspection")
        observed = inspect_epub_fd(fd, source, checkpoint=checkpoint)
        after_hash, after_bytes, after_identity = hash_held_fd(fd)
        if (
            after_hash != before_hash
            or after_bytes != before_bytes
            or after_identity != held_identity
        ):
            raise DiscoveryError("assembly_changed_after_identity_inspection")
    finally:
        os.close(fd)
    after_resource_observation = validate_resource_observation_binding(
        epoch,
        after_resource_observer(),
    )
    epub_core = {
        key: value
        for key, value in observed.items()
        if key not in {"observation_root_sha256", "schema_version"}
    }
    identity_core = {
        **epub_core,
        "assembly_binding": {
            "assembled_bytes": source.expected_bytes,
            "chunk_bytes": CHUNK_BYTES,
            "chunk_count": chunk_count,
            "held_inode_revalidated_before_and_after": True,
            "selected_chunk_evidence_root_sha256": assembly[
                "selected_chunk_evidence_root_sha256"
            ],
            "whole_file_sha256": "sha256:" + before_hash,
        },
        "resource_observation_sha256": {
            "after": after_resource_observation[1],
            "before": before_resource_observation[1],
        },
    }
    identity = {
        **identity_core,
        "local_resource_artifacts": {
            "after": after_resource_observation[0],
            "before": before_resource_observation[0],
        },
        "observation_root_sha256": canonical_sha256(identity_core),
        "schema_version": IDENTITY_SCHEMA,
    }
    identity_path = epoch / "identities" / f"{source.source_id}.json"
    if identity_path.exists():
        existing = read_canonical_json(identity_path, schema=IDENTITY_SCHEMA)
        validate_phone_identity_artifact(epoch, existing)
        existing_core = identity_observation_core(existing)
        comparison_fields = {
            key: value
            for key, value in identity_core.items()
            if key != "resource_observation_sha256"
        }
        existing_comparison = {
            key: value
            for key, value in existing_core.items()
            if key != "resource_observation_sha256"
        }
        if existing_comparison != comparison_fields:
            raise DiscoveryError(f"identity_reinspection_mismatch:{source.source_id}")
        revalidations = epoch / "identity_revalidations" / source.source_id
        ensure_private_directory(revalidations)
        revalidation = {
            "assembly_whole_file_sha256": "sha256:" + before_hash,
            "identity_observation_root_sha256": existing[
                "observation_root_sha256"
            ],
            "live_reinspection_matched": True,
            "resource_observation_sha256": identity_core[
                "resource_observation_sha256"
            ],
            "schema_version": "cur0s_siyavula_identity_live_revalidation_v2",
            "source_id": source.source_id,
        }
        publish_immutable_json(
            revalidations / f"{uuid.uuid4().hex}.json",
            revalidation,
        )
        return existing
    else:
        publish_immutable_json(identity_path, identity)
    return identity


def identity_observation_core(identity: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in identity.items()
        if key
        not in {
            "local_resource_artifacts",
            "observation_root_sha256",
            "schema_version",
        }
    }


EGRESS_IDENTITY_KEYS = {
    "archive",
    "assembly_binding",
    "catalogue_record",
    "catalogue_record_sha256",
    "container",
    "internal_members",
    "manifest_bindings",
    "media_context",
    "metadata",
    "navigation",
    "observation_root_sha256",
    "resource_observation_sha256",
    "rights",
    "schema_version",
    "source_id",
}


def require_nonnegative_integer_map(
    value: Any,
    *,
    role: str,
    key_pattern: re.Pattern[str],
    allowed_keys: set[str] | None = None,
) -> None:
    if type(value) is not dict or len(value) > 512:
        raise DiscoveryError(f"{role}_map_invalid")
    for key, item in value.items():
        if (
            type(key) is not str
            or key_pattern.fullmatch(key) is None
            or (allowed_keys is not None and key not in allowed_keys)
            or type(item) is not int
            or item < 0
        ):
            raise DiscoveryError(f"{role}_entry_invalid")


def validate_egress_identity(value: Any, source: SiyavulaSource) -> None:
    identity = require_exact_keys(value, EGRESS_IDENTITY_KEYS, role="egress_identity")
    core = {
        key: item
        for key, item in identity.items()
        if key not in {"observation_root_sha256", "schema_version"}
    }
    if (
        identity["schema_version"] != IDENTITY_SCHEMA
        or identity["source_id"] != source.source_id
        or identity["observation_root_sha256"] != canonical_sha256(core)
    ):
        raise DiscoveryError("egress_identity_root_invalid")
    archive = require_exact_keys(
        identity["archive"],
        {
            "all_member_CRCs_verified",
            "archive_member_count",
            "archive_member_roster_sha256",
            "mimetype_first_and_stored",
            "total_uncompressed_bytes",
            "unmanifested_payload_count",
            "unmanifested_payload_name_root_sha256",
        },
        role="identity_archive",
    )
    if (
        archive["all_member_CRCs_verified"] is not True
        or archive["mimetype_first_and_stored"] is not True
        or any(
            type(archive[field]) is not int or archive[field] < 0
            for field in (
                "archive_member_count",
                "total_uncompressed_bytes",
                "unmanifested_payload_count",
            )
        )
        or archive["archive_member_count"] <= 0
        or archive["total_uncompressed_bytes"] <= 0
        or archive["unmanifested_payload_count"]
        > archive["archive_member_count"]
    ):
        raise DiscoveryError("identity_archive_value_invalid")
    require_sha256(archive["archive_member_roster_sha256"], role="archive_roster")
    require_sha256(
        archive["unmanifested_payload_name_root_sha256"], role="unmanifested_roster"
    )
    catalogue = require_exact_keys(
        identity["catalogue_record"],
        {
            "catalogue_grade",
            "catalogue_subject",
            "download_filename",
            "download_filename_grade_token",
            "download_filename_subject_token",
            "download_url",
            "license_id",
            "source_id",
        },
        role="identity_catalogue_record",
    )
    if catalogue != {
        "catalogue_grade": source.catalogue_grade,
        "catalogue_subject": source.catalogue_subject,
        "download_filename": source.filename,
        "download_filename_grade_token": source.filename_grade_token,
        "download_filename_subject_token": source.filename_subject_token,
        "download_url": source.url,
        "license_id": "CC-BY-3.0",
        "source_id": source.source_id,
    } or identity["catalogue_record_sha256"] != canonical_sha256(catalogue):
        raise DiscoveryError("identity_catalogue_record_invalid")
    container = require_exact_keys(
        identity["container"],
        {"media_type", "opf_path", "path", "sha256"},
        role="identity_container",
    )
    if (
        container["media_type"] != "application/oebps-package+xml"
        or container["path"] != "META-INF/container.xml"
    ):
        raise DiscoveryError("identity_container_value_invalid")
    require_bounded_string(container["opf_path"], role="identity_OPF_path")
    validate_archive_member_name(container["opf_path"], set())
    require_sha256(container["sha256"], role="identity_container")
    internal = require_exact_keys(
        identity["internal_members"],
        {"navigation", "opf", "rights"},
        role="identity_internal_members",
    )
    for role in ("navigation", "opf", "rights"):
        member = require_exact_keys(
            internal[role], {"path", "sha256"}, role=f"identity_{role}_member"
        )
        require_bounded_string(member["path"], role=f"identity_{role}_path")
        require_sha256(member["sha256"], role=f"identity_{role}")
        validate_archive_member_name(member["path"], set())
    if internal["opf"]["path"] != container["opf_path"]:
        raise DiscoveryError("identity_OPF_container_binding_invalid")
    manifest = require_exact_keys(
        identity["manifest_bindings"],
        {
            "aggregate_xhtml_bytes",
            "manifest_item_count",
            "manifest_target_count",
            "navigation_item_id",
            "navigation_path",
            "rights_item_id",
            "rights_path",
            "spine_item_count",
            "spine_item_ids_root_sha256",
            "xhtml_manifest_item_count",
        },
        role="identity_manifest_bindings",
    )
    for field in (
        "aggregate_xhtml_bytes",
        "manifest_item_count",
        "manifest_target_count",
        "spine_item_count",
        "xhtml_manifest_item_count",
    ):
        if type(manifest[field]) is not int or manifest[field] <= 0:
            raise DiscoveryError("identity_manifest_count_invalid")
    for field in ("navigation_item_id", "navigation_path", "rights_item_id", "rights_path"):
        require_bounded_string(manifest[field], role=f"identity_manifest_{field}")
    require_sha256(manifest["spine_item_ids_root_sha256"], role="identity_spine")
    if (
        manifest["manifest_target_count"] != manifest["manifest_item_count"]
        or manifest["xhtml_manifest_item_count"] > manifest["manifest_item_count"]
        or manifest["spine_item_count"] > manifest["xhtml_manifest_item_count"]
        or manifest["navigation_path"] != internal["navigation"]["path"]
        or manifest["rights_path"] != internal["rights"]["path"]
    ):
        raise DiscoveryError("identity_manifest_binding_invalid")
    validate_identity_metadata(identity["metadata"])
    validate_identity_media(identity["media_context"])
    navigation = require_exact_keys(
        identity["navigation"],
        {
            "fragment_link_count",
            "fragment_targets_verified",
            "toc_link_count",
            "toc_nav_count",
            "toc_target_set_sha256",
        },
        role="identity_navigation",
    )
    if (
        navigation["fragment_targets_verified"] is not True
        or navigation["toc_nav_count"] != 1
        or type(navigation["toc_link_count"]) is not int
        or navigation["toc_link_count"] <= 0
        or type(navigation["fragment_link_count"]) is not int
        or not 0
        <= navigation["fragment_link_count"]
        <= navigation["toc_link_count"]
    ):
        raise DiscoveryError("identity_navigation_value_invalid")
    require_sha256(navigation["toc_target_set_sha256"], role="identity_TOC")
    rights = require_exact_keys(
        identity["rights"],
        {
            "artifact_notice_license_id",
            "artifact_notice_url",
            "catalogue_license_id",
            "resolved_license_id",
            "rights_subject_grade_claims",
            "rights_subject_template_mismatch",
            "structured_license_link_count",
            "siyavula_marker_present",
        },
        role="identity_rights",
    )
    if (
        rights["artifact_notice_license_id"] != "CC-BY-4.0"
        or rights["artifact_notice_url"]
        != "http://creativecommons.org/licenses/by/4.0/"
        or rights["catalogue_license_id"] != "CC-BY-3.0"
        or rights["resolved_license_id"]
        != "LicenseRef-Siyavula-Unbranded-CCBY-Version-Conflict"
        or rights["siyavula_marker_present"] is not True
        or type(rights["structured_license_link_count"]) is not int
        or rights["structured_license_link_count"] <= 0
        or rights["rights_subject_template_mismatch"] not in {True, False, None}
        or type(rights["rights_subject_grade_claims"]) is not list
        or len(rights["rights_subject_grade_claims"]) > 64
    ):
        raise DiscoveryError("identity_rights_value_invalid")
    for claim in rights["rights_subject_grade_claims"]:
        closed_claim = require_exact_keys(
            claim, {"grade", "subject"}, role="rights_claim"
        )
        if (
            type(closed_claim["grade"]) is not int
            or not 1 <= closed_claim["grade"] <= 12
            or closed_claim["subject"]
            not in {
                "Mathematics",
                "Natural Sciences",
                "Natural Sciences and Technology",
                "Physical Sciences",
            }
        ):
            raise DiscoveryError("identity_rights_claim_invalid")
    expected_claim = {
        "grade": source.catalogue_grade,
        "subject": source.catalogue_subject,
    }
    expected_mismatch = (
        expected_claim not in rights["rights_subject_grade_claims"]
        if rights["rights_subject_grade_claims"]
        else None
    )
    if rights["rights_subject_template_mismatch"] is not expected_mismatch:
        raise DiscoveryError("identity_rights_template_mismatch_invalid")
    assembly = require_exact_keys(
        identity["assembly_binding"],
        {
            "assembled_bytes",
            "chunk_bytes",
            "chunk_count",
            "held_inode_revalidated_before_and_after",
            "selected_chunk_evidence_root_sha256",
            "whole_file_sha256",
        },
        role="identity_assembly_binding",
    )
    if (
        assembly["assembled_bytes"] != source.expected_bytes
        or assembly["chunk_bytes"] != CHUNK_BYTES
        or assembly["chunk_count"]
        != (source.expected_bytes + CHUNK_BYTES - 1) // CHUNK_BYTES
        or assembly["held_inode_revalidated_before_and_after"] is not True
    ):
        raise DiscoveryError("identity_assembly_value_invalid")
    require_sha256(assembly["selected_chunk_evidence_root_sha256"], role="selected_root")
    require_sha256(assembly["whole_file_sha256"], role="whole_EPUB")
    if (
        source.known_sha256 is not None
        and assembly["whole_file_sha256"] != f"sha256:{source.known_sha256}"
    ):
        raise DiscoveryError("identity_known_EPUB_hash_invalid")
    resources = require_exact_keys(
        identity["resource_observation_sha256"],
        {"after", "before"},
        role="identity_resource_observations",
    )
    require_sha256(resources["before"], role="identity_resource_before")
    require_sha256(resources["after"], role="identity_resource_after")


def validate_identity_metadata(value: Any) -> None:
    metadata = require_exact_keys(
        value,
        {
            "dc_creator_observation_state",
            "dc_creator_values",
            "dc_identifier_values",
            "dc_language_values",
            "dc_publisher_observation_state",
            "dc_publisher_values",
            "dc_rights_observation_state",
            "dc_rights_values",
            "dc_subject_observation_state",
            "dc_subject_values",
            "dc_title_values",
            "dcterms_modified_values",
            "package_unique_identifier_id",
            "package_unique_identifier_linked",
            "package_version",
            "recognized_grade_metadata",
            "recognized_grade_observation_state",
        },
        role="identity_metadata",
    )
    list_fields = (
        "dc_creator_values",
        "dc_identifier_values",
        "dc_language_values",
        "dc_publisher_values",
        "dc_rights_values",
        "dc_subject_values",
        "dc_title_values",
        "dcterms_modified_values",
    )
    for field in list_fields:
        values = metadata[field]
        if type(values) is not list or len(values) > 64 or any(
            type(item) is not str or not item or len(item) > 4096 for item in values
        ):
            raise DiscoveryError(f"identity_metadata_{field}_invalid")
    for prefix in ("dc_creator", "dc_publisher", "dc_rights", "dc_subject"):
        expected_state = observation_state(metadata[f"{prefix}_values"])
        if metadata[f"{prefix}_observation_state"] != expected_state:
            raise DiscoveryError(f"identity_metadata_{prefix}_state_invalid")
    grades = metadata["recognized_grade_metadata"]
    if type(grades) is not list or len(grades) > 64:
        raise DiscoveryError("identity_grade_metadata_invalid")
    for grade in grades:
        closed_grade = require_exact_keys(
            grade, {"namespace", "property", "value"}, role="recognized_grade"
        )
        namespace = require_bounded_string(
            closed_grade["namespace"], role="recognized_grade_namespace"
        )
        property_name = require_bounded_string(
            closed_grade["property"], role="recognized_grade_property"
        )
        require_bounded_string(
            closed_grade["value"], role="recognized_grade_value"
        )
        normalized_local = re.sub(
            r"[-_.]", "", property_name.split(":", 1)[-1]
        ).casefold()
        if (
            namespace
            not in {
                "http://purl.org/dc/terms/",
                "http://purl.org/dcx/lrmi-terms/",
                "http://schema.org/",
                "https://schema.org/",
            }
            or normalized_local not in {"educationlevel", "educationallevel"}
        ):
            raise DiscoveryError("identity_recognized_grade_value_invalid")
    if (
        metadata["recognized_grade_observation_state"] != observation_state(grades)
        or metadata["package_unique_identifier_linked"] is not True
        or type(metadata["package_version"]) is not str
        or re.fullmatch(r"3\.[0-9]+", metadata["package_version"]) is None
        or type(metadata["package_unique_identifier_id"]) is not str
        or re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9._:-]{0,127}",
            metadata["package_unique_identifier_id"],
        )
        is None
        or len(metadata["dc_identifier_values"]) != 1
        or len(metadata["dc_title_values"]) != 1
        or metadata["dc_language_values"] != ["en"]
        or len(metadata["dcterms_modified_values"]) != 1
    ):
        raise DiscoveryError("identity_metadata_value_invalid")


def validate_identity_media(value: Any) -> None:
    media = require_exact_keys(
        value,
        {
            "CSS_content_declaration_count",
            "CSS_payload_bytes",
            "CSS_payloads_not_semantically_interpreted",
            "CSS_url_token_count",
            "embedded_data_reference_count",
            "inline_style_attribute_count",
            "inline_style_content_declaration_count",
            "inline_style_url_token_count",
            "internal_media_reference_count",
            "internal_media_reference_set_sha256",
            "manifest_image_item_count",
            "manifest_media_type_counts",
            "manifest_property_counts",
            "media_context_element_counts",
            "remote_media_reference_count",
            "scripted_manifest_item_count",
            "text_only_materialization_without_context_quarantine_forbidden",
            "visual_or_table_context_present",
            "visual_or_table_context_quarantine_required",
        },
        role="identity_media_context",
    )
    integer_fields = {
        key
        for key in media
        if key.endswith("_count") or key.endswith("_bytes")
    } - {"manifest_media_type_counts", "manifest_property_counts", "media_context_element_counts"}
    if any(type(media[field]) is not int or media[field] < 0 for field in integer_fields):
        raise DiscoveryError("identity_media_count_invalid")
    require_nonnegative_integer_map(
        media["manifest_media_type_counts"],
        role="manifest_media_types",
        key_pattern=re.compile(r"[a-z0-9.+-]+/[a-z0-9.+-]+"),
    )
    require_nonnegative_integer_map(
        media["manifest_property_counts"],
        role="manifest_properties",
        key_pattern=re.compile(r"[A-Za-z][A-Za-z0-9._:-]*"),
    )
    require_nonnegative_integer_map(
        media["media_context_element_counts"],
        role="media_elements",
        key_pattern=re.compile(r"[a-z]+"),
        allowed_keys=set(VISUAL_OR_CONTEXT_TAGS),
    )
    require_sha256(
        media["internal_media_reference_set_sha256"], role="media_reference_set"
    )
    for field in (
        "CSS_payloads_not_semantically_interpreted",
        "text_only_materialization_without_context_quarantine_forbidden",
        "visual_or_table_context_present",
        "visual_or_table_context_quarantine_required",
    ):
        if type(media[field]) is not bool:
            raise DiscoveryError("identity_media_boolean_invalid")
    visual_present = media["visual_or_table_context_present"]
    if (
        media["CSS_payloads_not_semantically_interpreted"] is not True
        or media["text_only_materialization_without_context_quarantine_forbidden"]
        is not visual_present
        or media["visual_or_table_context_quarantine_required"]
        is not visual_present
        or media["manifest_image_item_count"]
        != sum(
            count
            for media_type, count in media["manifest_media_type_counts"].items()
            if media_type.startswith("image/")
        )
    ):
        raise DiscoveryError("identity_media_semantic_binding_invalid")


def validate_phone_identity_artifact(
    epoch: Path, identity: Mapping[str, Any]
) -> None:
    artifact = require_exact_keys(
        identity,
        EGRESS_IDENTITY_KEYS | {"local_resource_artifacts"},
        role="phone_identity_artifact",
    )
    local_resources = require_exact_keys(
        artifact["local_resource_artifacts"],
        {"after", "before"},
        role="phone_identity_local_resources",
    )
    resource_hashes = require_exact_keys(
        artifact["resource_observation_sha256"],
        {"after", "before"},
        role="phone_identity_resource_hashes",
    )
    if (
        artifact["schema_version"] != IDENTITY_SCHEMA
        or artifact["observation_root_sha256"]
        != canonical_sha256(identity_observation_core(artifact))
    ):
        raise DiscoveryError("phone_identity_artifact_invalid")
    for phase in ("before", "after"):
        path = resolve_relative_artifact(epoch, local_resources.get(phase))
        validate_resource_observation_binding(
            epoch,
            (
                relative_inside(epoch, path),
                resource_hashes.get(phase),
            ),
        )


def deep_closed_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(canonical_json_bytes(dict(value)))


def project_runtime_identity(value: Mapping[str, Any]) -> dict[str, Any]:
    validate_runtime_identity(value)
    projected = {key: value[key] for key in sorted(RUNTIME_IDENTITY_KEYS)}
    return deep_closed_projection(projected)


def project_external_preimage(value: Mapping[str, Any]) -> dict[str, Any]:
    validate_external_preimage_closed(value)
    return deep_closed_projection(value)


def egress_identity(
    identity: Mapping[str, Any], source: SiyavulaSource
) -> dict[str, Any]:
    require_exact_keys(
        identity,
        EGRESS_IDENTITY_KEYS | {"local_resource_artifacts"},
        role="phone_identity_artifact",
    )
    projected = {key: identity[key] for key in sorted(EGRESS_IDENTITY_KEYS)}
    value = deep_closed_projection(projected)
    validate_egress_identity(value, source)
    return value


AGGREGATE_RECEIPT_KEYS = {
    "aggregate_egress_only",
    "candidate_admission_claim",
    "commercial_preregistration_claim",
    "discovery_complete",
    "epoch_id",
    "external_evidence_observation_state",
    "external_evidence_preimage",
    "external_evidence_preimage_sha256",
    "generated_at_utc",
    "immutable_origin_circuit_chain_tip",
    "old_unreceipted_prefixes_or_chunks_adopted",
    "raw_source_egress_occurred",
    "receipt_observation_root_sha256",
    "runtime_identity",
    "runtime_identity_sha256",
    "schema_version",
    "source_identity_observations",
    "source_roster_sha256",
    "thermal_policy",
    "transport_policy",
}


def aggregate_transport_policy(
    runtime_identity: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "CA_bundle_path": str(CA_BUNDLE_PATH),
        "CA_bundle_sha256": f"sha256:{CA_BUNDLE_EXPECTED_SHA256}",
        "chunk_bytes": CHUNK_BYTES,
        "curl_disable_config_files": True,
        "curl_execution_identity_sha256": expected_curl_execution_identity(
            runtime_identity
        ),
        "curl_max_time_seconds": CURL_MAX_TIME_SECONDS,
        "curl_subprocess_timeout_seconds": CURL_SUBPROCESS_TIMEOUT_SECONDS,
        "exact_one_request_per_attempt": True,
        "expected_total_chunk_requests": EXPECTED_TOTAL_CHUNK_REQUESTS,
        "origin_wide_backoff_seconds": list(BACKOFF_SECONDS),
        "per_request_retry_count": 0,
        "private_transport_temp_directory_required": True,
        "request_and_terminal_reserve_seconds": (
            REQUEST_AND_TERMINAL_RESERVE_SECONDS
        ),
        "system_linker64_held_curl_FD_launch_required": True,
    }


def validate_aggregate_receipt(receipt: Mapping[str, Any]) -> None:
    aggregate = require_exact_keys(
        receipt,
        AGGREGATE_RECEIPT_KEYS,
        role="aggregate_receipt",
    )
    if len(canonical_json_bytes(aggregate)) + 1 > 32 * 1024 * 1024:
        raise DiscoveryError("aggregate_receipt_size_limit")
    core = {
        key: value
        for key, value in aggregate.items()
        if key not in {"receipt_observation_root_sha256", "schema_version"}
    }
    runtime_identity = aggregate["runtime_identity"]
    validate_runtime_identity(runtime_identity)
    external_preimage = aggregate["external_evidence_preimage"]
    validate_external_preimage_closed(external_preimage)
    records = aggregate["source_identity_observations"]
    circuit_tip = require_exact_keys(
        aggregate["immutable_origin_circuit_chain_tip"],
        {"event_sequence", "last_event_sha256"},
        role="aggregate_circuit_tip",
    )
    if (
        aggregate["schema_version"] != AGGREGATE_RECEIPT_SCHEMA
        or aggregate["receipt_observation_root_sha256"] != canonical_sha256(core)
        or aggregate["aggregate_egress_only"] is not True
        or aggregate["candidate_admission_claim"] is not False
        or aggregate["commercial_preregistration_claim"] is not False
        or aggregate["discovery_complete"] is not True
        or aggregate["old_unreceipted_prefixes_or_chunks_adopted"] is not False
        or aggregate["raw_source_egress_occurred"] is not False
        or aggregate["external_evidence_observation_state"] != "observed_values"
        or aggregate["external_evidence_preimage_sha256"]
        != canonical_sha256(external_preimage)
        or aggregate["runtime_identity_sha256"]
        != canonical_sha256(runtime_identity)
        or aggregate["source_roster_sha256"] != source_roster_root()
        or aggregate["transport_policy"]
        != aggregate_transport_policy(runtime_identity)
        or aggregate["thermal_policy"] != THERMAL_POLICY
        or type(records) is not list
        or len(records) != len(SIYAVULA_SOURCES)
        or type(circuit_tip["event_sequence"]) is not int
        or circuit_tip["event_sequence"] < 0
        or (
            circuit_tip["event_sequence"] == 0
            and circuit_tip["last_event_sha256"] is not None
        )
        or (
            circuit_tip["event_sequence"] > 0
            and (
                type(circuit_tip["last_event_sha256"]) is not str
                or not circuit_tip["last_event_sha256"].startswith("sha256:")
                or SHA256_RE.fullmatch(
                    circuit_tip["last_event_sha256"].removeprefix("sha256:")
                )
                is None
            )
        )
    ):
        raise DiscoveryError("aggregate_receipt_invalid")
    require_bounded_string(aggregate["epoch_id"], role="aggregate_epoch_id", maximum=256)
    parse_utc(
        require_bounded_string(
            aggregate["generated_at_utc"],
            role="aggregate_generated_at",
            maximum=64,
        )
    )
    for source, identity in zip(SIYAVULA_SOURCES, records, strict=True):
        validate_egress_identity(identity, source)
    for role in ("catalogue", "terms"):
        binding = external_preimage[role]["successful_attempt_binding"]
        if binding["runtime_identity_sha256"] != aggregate[
            "runtime_identity_sha256"
        ]:
            raise DiscoveryError("aggregate_external_attempt_binding_invalid")


def collect_live_egress_identities(
    root: Path,
    epoch: Path,
    lease: DiscoveryLease,
) -> list[dict[str, Any]]:
    identities: list[dict[str, Any]] = []
    for source in SIYAVULA_SOURCES:
        lease.checkpoint(phase=f"before_identity_revalidation:{source.source_id}")
        before = lease.observe(phase=f"before_identity_inspection:{source.source_id}")
        identity = inspect_source_identity(
            root,
            epoch,
            source,
            before_resource_observation=before,
            after_resource_observer=lambda source_id=source.source_id: lease.observe(
                phase=f"after_identity_inspection:{source_id}"
            ),
            checkpoint=lambda phase: lease.checkpoint(phase=phase),
        )
        validate_phone_identity_artifact(epoch, identity)
        identities.append(egress_identity(identity, source))
        lease.checkpoint(phase=f"after_identity_revalidation:{source.source_id}")
    return identities


def finalize_epoch(
    epoch: Path,
    *,
    runtime_identity: Mapping[str, Any],
    lease: DiscoveryLease,
) -> dict[str, Any]:
    root, epoch, manifest = validate_epoch(epoch)
    require_epoch_runtime(manifest, runtime_identity)
    require_lease_epoch(lease, epoch)
    receipt_path = epoch / "aggregate_receipt.json"
    with epoch_lock(epoch):
        if next_pending_chunk(epoch) is not None:
            raise DiscoveryError("identity_discovery_chunks_incomplete")
        evidence = validate_external_evidence(
            root,
            epoch,
            checkpoint=lambda phase: lease.checkpoint(phase=phase),
        )
        identities = collect_live_egress_identities(root, epoch, lease)
        external_preimage = project_external_preimage(evidence["egress_preimage"])
        projected_runtime = project_runtime_identity(manifest["runtime_identity"])
        current_circuit = read_circuit(root)
        current_circuit_tip = {
            "event_sequence": current_circuit["event_sequence"],
            "last_event_sha256": current_circuit["last_event_sha256"],
        }
        if receipt_path.exists():
            existing = read_canonical_json(
                receipt_path,
                schema=AGGREGATE_RECEIPT_SCHEMA,
                max_bytes=32 * 1024 * 1024,
            )
            validate_aggregate_receipt(existing)
            if (
                existing["epoch_id"] != manifest["epoch_id"]
                or existing["runtime_identity"] != projected_runtime
                or existing["runtime_identity_sha256"]
                != manifest["runtime_identity_sha256"]
                or existing["external_evidence_preimage"] != external_preimage
                or existing["external_evidence_preimage_sha256"]
                != evidence["egress_preimage_sha256"]
                or existing["source_identity_observations"] != identities
                or existing["source_roster_sha256"] != source_roster_root()
                or existing["immutable_origin_circuit_chain_tip"]
                != current_circuit_tip
            ):
                raise DiscoveryError(
                    "existing_aggregate_receipt_live_revalidation_invalid"
                )
            return existing
        core = {
            "aggregate_egress_only": True,
            "candidate_admission_claim": False,
            "commercial_preregistration_claim": False,
            "discovery_complete": True,
            "epoch_id": manifest["epoch_id"],
            "external_evidence_observation_state": "observed_values",
            "external_evidence_preimage": external_preimage,
            "external_evidence_preimage_sha256": evidence[
                "egress_preimage_sha256"
            ],
            "generated_at_utc": format_utc(utc_now()),
            "immutable_origin_circuit_chain_tip": current_circuit_tip,
            "old_unreceipted_prefixes_or_chunks_adopted": False,
            "raw_source_egress_occurred": False,
            "runtime_identity": projected_runtime,
            "runtime_identity_sha256": manifest["runtime_identity_sha256"],
            "source_identity_observations": identities,
            "source_roster_sha256": source_roster_root(),
            "thermal_policy": THERMAL_POLICY,
            "transport_policy": aggregate_transport_policy(projected_runtime),
        }
        receipt = {
            **core,
            "receipt_observation_root_sha256": canonical_sha256(core),
            "schema_version": AGGREGATE_RECEIPT_SCHEMA,
        }
        validate_aggregate_receipt(receipt)
        publish_immutable_json(receipt_path, receipt)
    result = read_canonical_json(
        receipt_path,
        schema=AGGREGATE_RECEIPT_SCHEMA,
        max_bytes=32 * 1024 * 1024,
    )
    validate_aggregate_receipt(result)
    return result


def read_phone_identity() -> dict[str, Any]:
    property_names = {
        "ABI": "ro.product.cpu.abi",
        "android_release": "ro.build.version.release",
        "android_SDK": "ro.build.version.sdk",
        "board_platform": "ro.board.platform",
        "boot_verified_state": "ro.boot.verifiedbootstate",
        "device": "ro.product.device",
        "fingerprint": "ro.build.fingerprint",
        "flash_locked": "ro.boot.flash.locked",
        "model": "ro.product.model",
        "phone_process_boot_serial": "ro.boot.serialno",
        "phone_process_serial": "ro.serialno",
        "product_name": "ro.product.name",
        "SoC_manufacturer": "ro.soc.manufacturer",
        "SoC_model": "ro.soc.model",
        "thermal_battery_control": "ro.vendor.feature.zte_feature_ccc_bat_temp_cntrl",
        "thermal_policy_thresholds": "ro.vendor.feature.zte_feature_ccc_temp_threshold",
        "thermal_service_state": "init.svc.thermal-engine",
        "vendor_device": "ro.product.vendor.device",
    }
    getprop_path = Path("/system/bin/getprop")
    symlink_before = getprop_path.lstat()
    if not stat.S_ISLNK(symlink_before.st_mode):
        raise DiscoveryError("getprop_system_symlink_identity_invalid")
    symlink_target = os.readlink(getprop_path)
    toolbox_path = getprop_path.resolve(strict=True)
    toolbox_fd, toolbox_before, toolbox_identity = open_held_executable(
        getprop_path
    )
    linker_path = Path("/system/bin/linker64")
    linker_fd, linker_before, linker_identity = open_held_executable(linker_path)
    observed: dict[str, str] = {}
    try:
        for role, property_name in property_names.items():
            completed = subprocess.run(
                [str(getprop_path), property_name],
                check=False,
                close_fds=True,
                env={
                    "ANDROID_ROOT": "/system",
                    "LC_ALL": "C",
                    "PATH": "/system/bin",
                },
                stderr=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
            )
            try:
                value = completed.stdout.decode("utf-8", errors="strict").strip()
            except UnicodeDecodeError:
                raise DiscoveryError(f"phone_property_encoding_invalid:{role}") from None
            empty_serial_role = role in {
                "phone_process_boot_serial",
                "phone_process_serial",
            }
            if (
                completed.returncode != 0
                or (not value and not empty_serial_role)
                or len(value) > 1024
            ):
                raise DiscoveryError(f"phone_property_unavailable:{role}")
            observed[role] = value
        revalidate_held_executable(toolbox_fd, toolbox_before, toolbox_path)
        revalidate_held_executable(linker_fd, linker_before, linker_path)
        symlink_after = getprop_path.lstat()
        if (
            stat_identity(symlink_before) != stat_identity(symlink_after)
            or os.readlink(getprop_path) != symlink_target
        ):
            raise DiscoveryError("getprop_system_symlink_changed")
    finally:
        os.close(toolbox_fd)
        os.close(linker_fd)
    expected = {
        "ABI": EXPECTED_PHONE_ABI,
        "android_release": EXPECTED_ANDROID_RELEASE,
        "android_SDK": EXPECTED_ANDROID_SDK,
        "board_platform": EXPECTED_PHONE_BOARD_PLATFORM,
        "boot_verified_state": "green",
        "device": EXPECTED_PHONE_DEVICE,
        "fingerprint": EXPECTED_BUILD_FINGERPRINT,
        "flash_locked": "1",
        "model": EXPECTED_PHONE_MODEL,
        "phone_process_boot_serial": "",
        "phone_process_serial": "",
        "product_name": EXPECTED_PHONE_PRODUCT_NAME,
        "SoC_manufacturer": EXPECTED_PHONE_SOC_MANUFACTURER,
        "SoC_model": EXPECTED_PHONE_SOC,
        "thermal_battery_control": "true",
        "thermal_policy_thresholds": "skin,54,battery,45",
        "thermal_service_state": "running",
        "vendor_device": EXPECTED_PHONE_VENDOR_DEVICE,
    }
    if observed != expected:
        raise DiscoveryError("sovereign_phone_identity_mismatch")
    process = {
        "environment": dict(os.environ),
        "gid": os.getegid(),
        "HOME": str(Path.home()),
        "kernel_release": os.uname().release,
        "machine": platform.machine(),
        "platform_release": platform.release(),
        "PREFIX": os.environ.get("PREFIX"),
        "python_version": platform.python_version(),
        "uid": os.geteuid(),
    }
    if process != {
        "environment": EXPECTED_PYTHON_ENVIRONMENT,
        "gid": EXPECTED_TERMUX_UID_GID,
        "HOME": str(PHONE_HOME),
        "kernel_release": EXPECTED_KERNEL_RELEASE,
        "machine": EXPECTED_PHONE_MACHINE,
        "platform_release": "15",
        "PREFIX": EXPECTED_PYTHON_PREFIX,
        "python_version": EXPECTED_PYTHON_VERSION,
        "uid": EXPECTED_TERMUX_UID_GID,
    }:
        raise DiscoveryError("sovereign_phone_process_identity_mismatch")
    core = {
        "ADB_serial_claimed_by_phone_process": False,
        "external_ADB_serial_is_launcher_evidence_only": True,
        "getprop": {
            "execution_shape": (
                "canonical_root_owned_system_getprop_symlink_to_toolbox_"
                "held_toolbox_and_linker_pre_post"
            ),
            "linker64": linker_identity,
            "linker64_invocation_path": str(linker_path),
            "symlink": {
                "gid": symlink_after.st_gid,
                "mode": f"{stat.S_IMODE(symlink_after.st_mode):04o}",
                "path": str(getprop_path),
                "target": symlink_target,
                "uid": symlink_after.st_uid,
            },
            "toolbox": toolbox_identity,
        },
        "process": process,
        "properties": observed,
        "schema_version": "cur0s_siyavula_sovereign_phone_identity_v2",
    }
    return {**core, "observation_root_sha256": canonical_sha256(core)}


def current_phone_runtime_identity() -> dict[str, Any]:
    require_phone_runtime(DEFAULT_CURL)
    startup_identity = require_python_startup_contract()
    phone_identity = read_phone_identity()
    harness_identity = held_harness_identity()
    return observe_runtime_identity(
        curl_path=DEFAULT_CURL,
        build_fingerprint=EXPECTED_BUILD_FINGERPRINT,
        harness_identity=harness_identity,
        phone_identity=phone_identity,
        startup_identity=startup_identity,
    )


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    initialize = subparsers.add_parser("init")
    initialize.add_argument("--root", type=Path, default=DEFAULT_DISCOVERY_ROOT)
    for command in ("acquire", "evidence", "finalize"):
        child = subparsers.add_parser(command)
        child.add_argument("epoch", type=Path)
        child.add_argument("--lease-seconds", type=int, default=MAX_DISCOVERY_LEASE_SECONDS)
    subparsers.choices["acquire"].add_argument(
        "--max-successful-chunks",
        type=int,
        default=0,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_argument_parser().parse_args(argv)
    runtime_identity = current_phone_runtime_identity()
    if arguments.command == "init":
        epoch = initialize_epoch(
            arguments.root,
            runtime_identity=runtime_identity,
        )
        # This is a phone-local control locator, not evidence or a claim.
        print(str(epoch), file=sys.stderr)
        return 0
    root, epoch, _manifest = validate_epoch(arguments.epoch)
    private_temp_dir = root / "transport_tmp"
    validate_transport_temp_directory(private_temp_dir)
    lease = DiscoveryLease(epoch=epoch, lease_seconds=arguments.lease_seconds)
    if arguments.command == "acquire":
        acquire_epoch(
            epoch,
            executor=lambda source, start, end: curl_range_executor(
                source,
                start,
                end,
                curl_path=DEFAULT_CURL,
                private_temp_dir=private_temp_dir,
            ),
            runtime_identity=runtime_identity,
            lease=lease,
            max_successful_chunks=arguments.max_successful_chunks,
        )
        return 0
    if arguments.command == "evidence":
        capture_external_evidence(
            epoch,
            executor=lambda url: curl_page_executor(
                url,
                curl_path=DEFAULT_CURL,
                private_temp_dir=private_temp_dir,
            ),
            runtime_identity=runtime_identity,
            lease=lease,
        )
        return 0
    if arguments.command == "finalize":
        receipt = finalize_epoch(
            epoch,
            runtime_identity=runtime_identity,
            lease=lease,
        )
        print(canonical_json_bytes(receipt).decode("ascii"))
        return 0
    raise DiscoveryError("command_unreachable")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (DiscoveryError, CircuitOpen) as error:
        print(f"identity_discovery_blocked:{error}", file=sys.stderr)
        raise SystemExit(2) from None
