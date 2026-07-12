"""Adversarial tests for CUR-0S commercial-source phone acquisition.

Every fixture is local and synthetic.  These tests must never contact an
upstream service or write into the real Termux campaign root.
"""

from __future__ import annotations

from argparse import Namespace
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import io
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import ssl
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
from types import SimpleNamespace
from typing import Any, Mapping
import zipfile

import pytest

from polymath_ai.corpus import cur0s_commercial_sources as commercial


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts/termux/run_cur0s_commercial_sources.py"
BUILDER_PATH = ROOT / "scripts/host/build_cur0s_commercial_sources_preregistration.py"
RUN_ID = "20260712T120000Z_cur0s_commercial_sources_v1"
FAKE_COMMIT = "1" * 40
SHA256 = "sha256:" + "2" * 64
PARENT_CAPSULE_SHA256 = (
    "sha256:e6905f36fa526e15a0a1d8ac4eadbf670061a2837fea9a7ac51a1df6bb608f15"
)
PARENT_FRONTIER_ROOT_SHA256 = (
    "sha256:d118000d8fd457962f2332f2597bb25f6c6e33ee61010f5cd1459ab9768235fc"
)


@pytest.fixture
def runner():
    name = "cur0s_commercial_sources_runner_test"
    spec = importlib.util.spec_from_file_location(name, RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def builder():
    name = "cur0s_commercial_sources_builder_test"
    spec = importlib.util.spec_from_file_location(name, BUILDER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _git_blob(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload, usedforsecurity=False).hexdigest()


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _exact_startup_identity(runner) -> dict[str, Any]:
    action_root = runner.PHONE_RUN_ROOT / RUN_ID
    pycache_prefix = action_root / runner.RUN_SCOPED_PYCACHE_DIRECTORY_NAME
    return {
        "sys_executable": f"{runner.EXPECTED_PYTHON_PREFIX}/bin/python",
        "base_executable": f"{runner.EXPECTED_PYTHON_PREFIX}/bin/python",
        "real_executable": f"{runner.EXPECTED_PYTHON_PREFIX}/bin/python3.13",
        "prefix": runner.EXPECTED_PYTHON_PREFIX,
        "base_prefix": runner.EXPECTED_PYTHON_PREFIX,
        "exec_prefix": runner.EXPECTED_PYTHON_PREFIX,
        "base_exec_prefix": runner.EXPECTED_PYTHON_PREFIX,
        "initial_sys_path": list(runner.EXPECTED_PYTHON_INITIAL_SYS_PATH),
        "sys_flags": {
            "isolated": 1,
            "no_site": 1,
            "no_user_site": 1,
            "ignore_environment": 1,
            "safe_path": True,
            "dont_write_bytecode": 1,
            "optimize": 0,
        },
        "xoptions": {"pycache_prefix": str(pycache_prefix)},
        "pycache_prefix": str(pycache_prefix),
        "orig_argv": [
            f"{runner.EXPECTED_PYTHON_PREFIX}/bin/python",
            "-IBS",
            "-X",
            f"pycache_prefix={pycache_prefix}",
            runner.RUNNER_EXECUTION_PATH,
            "--preregistration",
            str(action_root / "preregistration.json"),
            "--expected-preregistration-sha256",
            SHA256,
            "--output-dir",
            str(action_root / "candidate_runs/candidate-001"),
        ],
        "environment": runner.EXPECTED_PYTHON_LAUNCH_ENVIRONMENT,
    }


def _fake_git_output(builder, *args: str) -> str:
    if args == ("for-each-ref", "--format=%(refname)", "refs/replace"):
        return ""
    if args == ("rev-parse", "HEAD"):
        return FAKE_COMMIT
    if args[:2] == ("status", "--short"):
        return ""
    if args[:1] == ("rev-parse",) and args[1].startswith("HEAD:"):
        relative = args[1][5:]
        return _git_blob((builder.ROOT / relative).read_bytes())
    raise AssertionError(args)


def _dynamic_build_python_runtime() -> dict[str, Any]:
    base = commercial.native_preflight_build_python_runtime_identity()
    layout = commercial.native_preflight_execution_layout(RUN_ID, FAKE_COMMIT)
    driver_path = (
        layout["checkout_root"] + "/scripts/termux/build_cur0s_native_preflight.py"
    )
    pycache = layout["action_root"] + "/native_preflight_build_pycache_forbidden"
    origins = [
        {
            "cached": None,
            "loader": "explicit_held_source",
            "name": "__main__",
            "origin": driver_path,
            "origin_kind": "held_source",
        },
        {
            "cached": None,
            "loader": "explicit_held_source",
            "name": "_cur0s_build_driver_contract",
            "origin": layout["commercial_sources_path"],
            "origin_kind": "held_source",
        },
    ]
    orig_argv = [
        "/data/data/com.termux/files/usr/bin/python",
        "-IBS",
        "-X",
        f"pycache_prefix={pycache}",
        driver_path,
        "--run-id",
        RUN_ID,
        "--source-commit",
        FAKE_COMMIT,
    ]
    body = {
        **base,
        "driver_path": driver_path,
        "file_backed_executable_mapping_paths": sorted(
            artifact["path"] for artifact in base["artifact_inputs"].values()
        ),
        "loaded_module_origin_count": len(origins),
        "loaded_module_origins": origins,
        "loaded_module_origins_sha256": commercial.canonical_sha256(origins),
        "loaded_stdlib_extension_module_paths": [],
        "orig_argv": orig_argv,
        "pycache_prefix": pycache,
        "pycache_prefix_absent": True,
        "run_id": RUN_ID,
        "source_commit": FAKE_COMMIT,
        "sys_argv": orig_argv[4:],
        "sys_xoptions": {"pycache_prefix": pycache},
    }
    return {
        **body,
        "python_runtime_root_sha256": commercial.canonical_sha256(body),
    }


def _dynamic_build_tool_runtime(
    compiler_identity: Mapping[str, Any],
    linker_identity: Mapping[str, Any],
) -> dict[str, Any]:
    empty_sha = _sha(b"")
    inputs = commercial.NATIVE_PREFLIGHT_BUILD_TOOL_RUNTIME_INPUTS

    def held(role: str, identity: Mapping[str, Any], inode: int) -> dict[str, Any]:
        return {
            "bytes": identity["bytes"],
            "device_major": 1,
            "device_minor": 2,
            "inode": inode,
            "literal_path": identity["literal_path"],
            "resolved_path": identity["resolved_path"],
            "runtime_role": role,
            "sha256": identity["sha256"],
        }

    tools: dict[str, Any] = {}
    identities = {"compiler": compiler_identity, "linker": linker_identity}
    for tool_index, (tool_role, identity) in enumerate(identities.items(), start=1):
        entries: list[dict[str, Any]] = []
        for entry_index, (soname, runtime_role) in enumerate(
            commercial.NATIVE_PREFLIGHT_ACTUAL_LOADER_EXPECTED_RESOLUTION[tool_role],
            start=1,
        ):
            if runtime_role == "kernel_vdso":
                path = "[vdso]"
                file_identity = {
                    "bytes": None,
                    "device_major": None,
                    "device_minor": None,
                    "inode": None,
                    "sha256": None,
                }
            else:
                artifact = inputs[runtime_role]
                path = artifact["resolved_path"]
                file_identity = {
                    "bytes": artifact["bytes"],
                    "device_major": 1,
                    "device_minor": 2,
                    "inode": 100 + entry_index,
                    "sha256": artifact["sha256"],
                }
            entries.append(
                {
                    **file_identity,
                    "normalized_line": f"\t{soname} => {path}",
                    "resolved_path": path,
                    "runtime_role": runtime_role,
                    "soname": soname,
                }
            )
        resolution_body = {
            "argv": [
                "/system/bin/linker64",
                "--list",
                f"/proc/self/fd/{70 + tool_index}",
            ],
            "entries": entries,
            "entry_count": len(entries),
            "normalized_stdout_sha256": commercial.canonical_sha256(
                [entry["normalized_line"] for entry in entries]
            ),
            "returncode": 0,
            "stderr_bytes": 0,
            "stderr_sha256": empty_sha,
            "target": held(tool_role, identity, 10 + tool_index),
        }
        tools[tool_role] = {
            **resolution_body,
            "resolution_root_sha256": commercial.canonical_sha256(resolution_body),
        }
    actual_body = {
        "address_normalization": (
            "remove_only_exact_terminal_lowercase_hex_ASLR_address_suffix"
        ),
        "environment": {
            "ANDROID_ROOT": "/system",
            "HOME": "/data/data/com.termux/files/home",
            "LC_ALL": "C",
            "PATH": "/data/data/com.termux/files/usr/bin:/system/bin",
        },
        "loader": held("android_linker64", inputs["android_linker64"], 9),
        "schema_version": (commercial.NATIVE_PREFLIGHT_ACTUAL_LOADER_RESOLUTION_SCHEMA),
        "scope": (
            "static_PT_INTERP_and_DT_NEEDED_resolution_only_no_arbitrary_dlopen_claim"
        ),
        "tools": tools,
    }
    return {
        **commercial.NATIVE_PREFLIGHT_BUILD_TOOL_RUNTIME_IDENTITY,
        "actual_loader_resolution": {
            **actual_body,
            "actual_loader_resolution_root_sha256": (
                commercial.canonical_sha256(actual_body)
            ),
        },
    }


def _native_maps_attestation(native: Mapping[str, Any]) -> dict[str, Any]:
    files = {
        record.get("toolchain_role"): record
        for record in native["static_manifest_records"]
        if record["record_type"] == "FILE" and "toolchain_role" in record
    }
    native_self = next(
        record
        for record in native["static_manifest_records"]
        if record.get("runtime_role") == "native_self"
    )
    shapes = {
        "android_linker64": (0x4C000, 0x116000),
        "android_bionic_libc": (0x48000, 0x8F000),
        "android_bionic_libdl": (0x4000, 0x1000),
        "android_bionic_libm": (0x14000, 0x24000),
        "system_libcxx": (0x84000, 0x7B000),
        "system_libnetd_client": (0x4000, 0x4000),
    }
    records: list[dict[str, Any]] = []
    for index, (role, (offset, mapped_bytes)) in enumerate(shapes.items(), start=1):
        artifact = files[role]
        records.append(
            {
                "bytes": artifact["bytes"],
                "device_major": 1,
                "device_minor": 2,
                "inode": 100 + index,
                "mapped_bytes": mapped_bytes,
                "offset": offset,
                "path": artifact["path"],
                "permissions": "r-xp",
                "runtime_role": role,
                "sha256": artifact["sha256"],
            }
        )
    records.extend(
        (
            {
                "bytes": native_self["bytes"],
                "device_major": 1,
                "device_minor": 2,
                "inode": 99,
                "mapped_bytes": 4096,
                "offset": 0,
                "path": native_self["path"],
                "permissions": "r-xp",
                "runtime_role": "native-self",
                "sha256": native_self["sha256"],
            },
            {
                "bytes": None,
                "device_major": 0,
                "device_minor": 0,
                "inode": 0,
                "mapped_bytes": 4096,
                "offset": 0,
                "path": "[vdso]",
                "permissions": "r-xp",
                "runtime_role": "kernel_vdso",
                "sha256": None,
            },
            {
                "bytes": None,
                "device_major": 0,
                "device_minor": 0,
                "inode": 0,
                "mapped_bytes": 8192,
                "offset": 0,
                "path": "[vvar]",
                "permissions": "r--p",
                "runtime_role": "kernel_vvar",
                "sha256": None,
            },
        )
    )
    records.sort(
        key=lambda record: (
            record["path"],
            record["offset"],
            record["permissions"],
            record["inode"],
        )
    )
    maps = {
        "capture_timing": "first_action_in_main_before_argument_parsing",
        "executable_mapping_policy": (
            "exact_nine_record_phone_native_runtime_closure_only"
        ),
        "production_policy_enforced": True,
        "records": records,
        "schema_version": "cur0s_native_earliest_main_maps_v1",
        "unexpected_executable_mappings_absent": True,
        "vvar": {"nonexecutable": True, "present": True},
    }
    return {
        "native_maps": maps,
        "native_maps_root_sha256": commercial.canonical_sha256(maps),
    }


def _native_build_receipt(builder) -> dict[str, Any]:
    source_bindings = {
        path: builder.build_source_binding(path) for path in builder.NATIVE_SOURCE_FILES
    }
    empty_sha = _sha(b"")
    common_tool_identity = {
        "literal_entry_type": "symbolic_link",
        "literal_mode": "0777",
        "literal_uid": 10536,
        "literal_gid": 10536,
        "literal_nlink": 1,
        "resolved_entry_type": "regular_file",
        "resolved_mode": "0700",
        "resolved_uid": 10536,
        "resolved_gid": 10536,
        "resolved_nlink": 1,
        "version_returncode": 0,
        "version_stderr_bytes": 0,
        "version_stderr_sha256": empty_sha,
    }
    compiler_identity = {
        **common_tool_identity,
        "literal_path": "/data/data/com.termux/files/usr/bin/clang",
        "literal_symlink_target": "clang-21",
        "resolved_path": "/data/data/com.termux/files/usr/bin/clang-21",
        "sha256": "sha256:34da8e3a9b71793eb70c25670e1fe2bce4d37f1e2837ba8dc0c516c2ca0ffc83",
        "bytes": 120_848,
        "version_argv_suffix": ["--version"],
        "version_stdout_bytes": 109,
        "version_stdout_sha256": "sha256:fe40f61ef08c80c802452d327052739a0a57b31366d8eabdc694a15b8df98f94",
    }
    linker_identity = {
        **common_tool_identity,
        "literal_path": "/data/data/com.termux/files/usr/bin/ld.lld",
        "literal_symlink_target": "lld",
        "resolved_path": "/data/data/com.termux/files/usr/bin/lld",
        "sha256": "sha256:5214b9511221a87e02c4a9603f470dd83804a54f4cf62475f168d47d707d964d",
        "bytes": 5_615_720,
        "version_argv_suffix": ["-flavor", "gnu", "--version"],
        "version_stdout_bytes": 41,
        "version_stdout_sha256": "sha256:418d72df86baf70c88b9a96a9118e3cdc66be0537a58f66a6879df0479f9a78f",
    }
    binary_digest = {"bytes": 4096, "sha256": _sha(b"native-binary")}
    binary_identity = {
        **binary_digest,
        "mode": "0700",
        "uid": 10536,
        "gid": 10536,
        "nlink": 1,
    }
    closure = {
        "schema_version": commercial.NATIVE_PREFLIGHT_TOOLCHAIN_CLOSURE_SCHEMA,
        "compiled_source_execution": "held_source_fds",
        "compiler_execution": "held_compiler_fd",
        "default_clang_configuration": {
            "disabled": True,
            "flag": "--no-default-config",
        },
        "header_resolution": "private_symlink_to_held_header_fd",
        "include_trees": deepcopy(commercial.NATIVE_PREFLIGHT_BUILD_INCLUDE_TREES),
        "input_closure_scope": (
            "all_file_backed_build_inputs_and_current_process_executable_mappings"
        ),
        "kernel_and_process_boundary": {
            "kernel_vdso": "observed_executable_mapping_without_file_backing",
            "pre_exec_process_provenance": "outside_file_input_closure_claim",
        },
        "link_inputs": deepcopy(commercial.NATIVE_PREFLIGHT_BUILD_LINK_INPUTS),
        "linker_execution": "direct_held_linker_fd",
        "python_runtime": _dynamic_build_python_runtime(),
        "tool_execution_runtime": _dynamic_build_tool_runtime(
            compiler_identity,
            linker_identity,
        ),
        "unmeasured_inputs_allowed": False,
        "unmeasured_inputs_allowed_scope": "within_input_closure_scope",
    }
    closure["closure_root_sha256"] = builder.canonical_sha256(closure)
    object_digests = {
        "cur0s_native_preflight": {
            "bytes": 2048,
            "sha256": _sha(b"native-preflight-object"),
        },
        "cur0s_sha256": {
            "bytes": 1024,
            "sha256": _sha(b"sha256-object"),
        },
    }
    receipt = {
        "schema_version": commercial.NATIVE_PREFLIGHT_BUILD_SCHEMA,
        "run_id": RUN_ID,
        "source_commit": FAKE_COMMIT,
        "source_commit_binding_status": (
            commercial.NATIVE_PREFLIGHT_SOURCE_COMMIT_BINDING_STATUS
        ),
        "source_file_bindings": source_bindings,
        "intended_target": {
            "architecture": "aarch64",
            "compiler_target": "aarch64-linux-android30",
            "runtime_device_and_soc_gate": "not_claimed_by_build_receipt",
        },
        "build_principal": {"gid": 10536, "uid": 10536},
        "compiler_identity": compiler_identity,
        "linker_identity": linker_identity,
        "toolchain_input_closure": closure,
        "build_environment": {
            "ANDROID_ROOT": "/system",
            "HOME": "/data/data/com.termux/files/home",
            "LC_ALL": "C",
            "PATH": "/data/data/com.termux/files/usr/bin:/system/bin",
        },
        "build_argv_template": {
            "compile": list(commercial.NATIVE_PREFLIGHT_COMPILE_ARGV_TEMPLATE),
            "link": list(commercial.NATIVE_PREFLIGHT_LINK_ARGV_TEMPLATE),
        },
        "build_one": dict(binary_digest),
        "build_two": dict(binary_digest),
        "intermediate_objects": {
            "build_one": deepcopy(object_digests),
            "build_two": deepcopy(object_digests),
            "deterministic_match": True,
        },
        "binary_identity": binary_identity,
        "elf_identity": {
            "android_ident": {
                "api_level": 30,
                "ndk_build_number": "14206865",
                "ndk_version": "r29",
            },
            "bind_now": True,
            "build_id": None,
            "class_bits": 64,
            "data_encoding": "little_endian",
            "executable_pt_load": {
                "alignment": 4096,
                "file_offset": 0,
                "file_size": binary_digest["bytes"],
                "memory_size": binary_digest["bytes"],
                "proc_maps_mapped_bytes": 4096,
                "proc_maps_offset": 0,
                "proc_maps_page_size": 4096,
                "virtual_address": 0,
            },
            "interpreter": "/system/bin/linker64",
            "machine": "AArch64",
            "needed": ["libc.so"],
            "pie": True,
            "relro": True,
            "rpath": None,
            "runpath": None,
            "sha256": binary_digest["sha256"],
            "text_relocations": False,
        },
        "deterministic_binary_match": True,
        "testing_macro_absent": True,
        "testing_hook_strings_absent": True,
        "network_requested": False,
        "network_syscalls_instrumented": False,
        "security_ceiling": (
            "observational_only_no_guarantee_against_a_concurrent_malicious_"
            "same_uid_between_checks"
        ),
    }
    receipt["build_receipt_root_sha256"] = builder.canonical_sha256(receipt)
    return receipt


def _build_prereg(builder, monkeypatch) -> dict[str, Any]:
    monkeypatch.setattr(
        builder,
        "git_output",
        lambda *args: _fake_git_output(builder, *args),
    )
    monkeypatch.setattr(
        builder,
        "load_native_preflight_build_receipt",
        lambda _args: _native_build_receipt(builder),
    )
    return builder.build_preregistration(
        Namespace(
            run_id=RUN_ID,
            parent_capsule_sha256=PARENT_CAPSULE_SHA256,
            parent_frontier_root_sha256=PARENT_FRONTIER_ROOT_SHA256,
            output="unused",
        )
    )


def _reroot(prereg: dict[str, Any], canonical_sha256) -> dict[str, Any]:
    prereg.pop("preregistration_root_sha256", None)
    prereg["preregistration_root_sha256"] = canonical_sha256(prereg)
    return prereg


def _bootstrap_checkout(tmp_path: Path, runner) -> tuple[Path, dict[str, bytes]]:
    payloads: dict[str, bytes] = {}
    for relative in runner.BOUND_SOURCE_FILES:
        payload = (ROOT / relative).read_bytes()
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        payloads[relative] = payload
    return tmp_path, payloads


def _install_bootstrap_mocks(
    runner,
    monkeypatch,
    checkout: Path,
    prereg_bytes: bytes,
) -> None:
    monkeypatch.setattr(
        runner,
        "bootstrap_read_private_preregistration",
        lambda _path: prereg_bytes,
    )

    def open_checkout() -> int:
        return os.open(checkout, os.O_RDONLY | os.O_DIRECTORY)

    monkeypatch.setattr(runner, "bootstrap_open_checkout_root", open_checkout)

    runner_payload = (checkout / runner.BOUND_SOURCE_FILES[1]).read_bytes()
    monkeypatch.setattr(
        runner,
        "_EXECUTED_RUNNER_IDENTITY",
        {
            "sha256": _sha(runner_payload),
            "bytes": len(runner_payload),
        },
    )


class _Checks:
    def __init__(self) -> None:
        self.values: list[str] = []

    def check(self, checkpoint: str, **_kwargs: Any) -> None:
        self.values.append(checkpoint)


def _fd_for(tmp_path: Path, payload: bytes) -> int:
    path = tmp_path / f"payload-{len(list(tmp_path.iterdir()))}"
    path.write_bytes(payload)
    return os.open(path, os.O_RDWR)


def _tar_bytes(entries: list[tuple[str, bytes, str]]) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, payload, kind in entries:
            info = tarfile.TarInfo(name)
            if kind == "file":
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))
            elif kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = "target"
                archive.addfile(info)
            else:
                raise AssertionError(kind)
    return output.getvalue()


def _wordnet_tar(marker: str) -> bytes:
    entries = [("WordNet-3.0/LICENSE", marker.encode(), "file")]
    for name in (
        "data.noun",
        "data.verb",
        "data.adj",
        "data.adv",
        "index.noun",
        "index.verb",
        "index.adj",
        "index.adv",
    ):
        entries.append((f"WordNet-3.0/dict/{name}", b"fixture\n", "file"))
    return _tar_bytes(entries)


def _zip_bytes(
    entries: list[tuple[str, bytes, int, int | None]],
) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, payload, compression, mode in entries:
            info = zipfile.ZipInfo(name)
            info.compress_type = compression
            if mode is not None:
                info.create_system = 3
                info.external_attr = mode << 16
            archive.writestr(info, payload)
    return output.getvalue()


def _epub_bytes(
    *,
    title: str = "maths10",
    identifier: str = "www.siyavula.com.epubmaker.maths10",
    modified: str = "2015-09-15T13:22:49Z",
) -> tuple[bytes, dict[str, bytes]]:
    stem = "maths10"
    opf_path = f"OPS/{stem}-package.opf"
    navigation_path = f"OPS/xhtml/{stem}/{stem}.nav.xhtml"
    rights_path = (
        f"OPS/xhtml/{stem}/front-matter-epubs/copyright_acknowledgements_ccby.html"
    )
    mimetype = b"application/epub+zip"
    container = f"""<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="{opf_path}"
    media-type="application/oebps-package+xml"/></rootfiles>
</container>""".encode()
    opf = f"""<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0"
 unique-identifier="pub-id"
 xmlns:dc="http://purl.org/dc/elements/1.1/">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="pub-id">{identifier}</dc:identifier><dc:title>{title}</dc:title>
    <dc:language>en</dc:language><meta property="dcterms:modified">{modified}</meta>
  </metadata>
  <manifest>
    <item id="chapter" href="xhtml/{stem}/chapter.xhtml" media-type="application/xhtml+xml"/>
    <item id="nav" href="xhtml/{stem}/{stem}.nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <item id="rights" href="xhtml/{stem}/front-matter-epubs/copyright_acknowledgements_ccby.html" media-type="application/xhtml+xml"/>
  </manifest>
  <spine><itemref idref="chapter"/></spine>
</package>""".encode()
    chapter = b'<html xmlns="http://www.w3.org/1999/xhtml"><body>chapter</body></html>'
    navigation = (
        b'<html xmlns="http://www.w3.org/1999/xhtml" '
        b'xmlns:epub="http://www.idpf.org/2007/ops"><body>'
        b'<nav epub:type="toc"><a href="chapter.xhtml">chapter</a></nav>'
        b"</body></html>"
    )
    rights = (
        b'<!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml"><body>Siyavula '
        b'<a href="http://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>'
        b"</body></html>"
    )
    members = {
        "mimetype": mimetype,
        "META-INF/container.xml": container,
        opf_path: opf,
        f"OPS/xhtml/{stem}/chapter.xhtml": chapter,
        navigation_path: navigation,
        rights_path: rights,
    }
    payload = _zip_bytes(
        [
            ("mimetype", mimetype, zipfile.ZIP_STORED, stat.S_IFREG | 0o644),
            (
                "META-INF/container.xml",
                container,
                zipfile.ZIP_DEFLATED,
                stat.S_IFREG | 0o644,
            ),
            (
                opf_path,
                opf,
                zipfile.ZIP_DEFLATED,
                stat.S_IFREG | 0o644,
            ),
            (
                f"OPS/xhtml/{stem}/chapter.xhtml",
                chapter,
                zipfile.ZIP_DEFLATED,
                stat.S_IFREG | 0o644,
            ),
            (
                navigation_path,
                navigation,
                zipfile.ZIP_DEFLATED,
                stat.S_IFREG | 0o644,
            ),
            (
                rights_path,
                rights,
                zipfile.ZIP_DEFLATED,
                stat.S_IFREG | 0o644,
            ),
        ]
    )
    return payload, members


def _bind_epub_fixture_source(base, payload: bytes, members: dict[str, bytes]):
    identity = base.epub_identity
    assert identity is not None
    return replace(
        base,
        expected_bytes=len(payload),
        expected_sha256=hashlib.sha256(payload).hexdigest(),
        epub_identity=replace(
            identity,
            opf_sha256=hashlib.sha256(members[identity.opf_path]).hexdigest(),
            navigation_sha256=hashlib.sha256(
                members[identity.navigation_path]
            ).hexdigest(),
            rights_member_sha256=hashlib.sha256(
                members[identity.rights_member_path]
            ).hexdigest(),
        ),
    )


def _obo_bytes(markers: tuple[str, ...]) -> bytes:
    lines = [*(marker.encode() + b"\n" for marker in markers)]
    for index in range(100):
        lines.extend(
            (
                b"[Term]\n",
                f"id: TEST:{index:07d}\n".encode(),
                f"name: term {index}\n".encode(),
                b'def: "fixture definition" []\n',
            )
        )
    return b"".join(lines)


def _rdf_bytes(markers: tuple[str, ...]) -> bytes:
    assert markers == (
        '<dc:rights xml:lang="en">Public domain</dc:rights>',
        "<dc:date rdf:datatype=",
        ">2023-11-02</dc:date>",
    )
    marker_text = (
        '<dc:rights xml:lang="en">Public domain</dc:rights>'
        '<dc:date rdf:datatype="http://www.w3.org/2001/XMLSchema#date"'
        ">2023-11-02</dc:date>"
    )
    descriptions = "".join(
        f'<rdf:Description rdf:about="urn:test:{index}"/>' for index in range(100)
    )
    return (
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f"{marker_text}{descriptions}</rdf:RDF>"
    ).encode()


def _make_candidate_path(tmp_path: Path, runner, monkeypatch) -> Path:
    package_root = tmp_path / "com.termux"
    home = package_root / "files/home"
    campaign = home / runner.PHONE_RUN_ROOT_RELATIVE
    parent = campaign / RUN_ID / "candidate_runs"
    parent.mkdir(parents=True, mode=0o700)
    package_root.chmod(0o700)
    (package_root / "files").chmod(0o771)
    for path in (home, campaign, campaign / RUN_ID, parent):
        path.chmod(0o700)
    monkeypatch.setattr(runner, "PHONE_PACKAGE_ROOT", package_root)
    monkeypatch.setattr(runner, "PHONE_HOME", home)
    monkeypatch.setattr(runner, "PHONE_RUN_ROOT", campaign)
    return parent / "candidate-001"


def _lease(runner, now: datetime, **overrides: Any):
    values = {
        "lease_id": "fixture",
        "action_id": RUN_ID,
        "issued_at": now,
        "expires_at": now + timedelta(hours=4),
        "max_wall_seconds": 7200,
        "terminalization_reserve_seconds": 30,
        "max_private_output_bytes": 16 * 1024 * 1024,
        "min_free_storage_bytes": 10_737_418_240,
        "thermal_safety_contract": runner.phone_thermal_safety_contract(),
        "thermal_sample_interval_seconds": 5,
    }
    values.update(overrides)
    return runner.CampaignLease(**values)


def _thermal_sample(
    runner,
    *,
    group_values: Mapping[str, int] | None = None,
    unavailable_groups: frozenset[str] = frozenset(),
):
    contract = runner.phone_thermal_safety_contract()
    group_values = dict(group_values or {})
    type_to_group = {
        sensor_type: group
        for group, sensor_types in contract["sensor_types_by_group"].items()
        for sensor_type in sensor_types
    }
    excluded = set(contract["excluded_non_temperature_sensor_types"])
    observations = []
    for zone_name, sensor_type in contract["zone_type_roster"].items():
        if sensor_type in excluded:
            observations.append((zone_name, sensor_type, None, False))
            continue
        group = type_to_group[sensor_type]
        value = None if group in unavailable_groups else group_values.get(group, 40_000)
        observations.append((zone_name, sensor_type, value, True))
    return runner.assemble_thermal_sample(observations, contract)


def _envelope(
    runner,
    tmp_path: Path,
    *,
    now: datetime,
    free_bytes: int = 10_737_418_240,
    temperatures: list[int] | None = None,
    max_private_output_bytes: int = 16 * 1024 * 1024,
    monotonic: list[float] | None = None,
    wall_clock: list[datetime] | None = None,
):
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    monotonic = monotonic or [0.0]
    wall_clock = wall_clock or [now]
    candidate = SimpleNamespace(
        path=tmp_path,
        bound_path=tmp_path,
        directory_fd=directory_fd,
        revalidate_path_binding=lambda: None,
    )
    envelope = runner.ResourceEnvelope(
        _lease(
            runner,
            now,
            max_private_output_bytes=max_private_output_bytes,
        ),
        candidate,
        0.0,
        now_fn=lambda: wall_clock[0],
        monotonic_fn=lambda: monotonic[0],
        thermal_reader=lambda: (
            _thermal_sample(
                runner,
                group_values={
                    "compute_cpu_soc": (
                        40_000 if temperatures is None else temperatures[0]
                    )
                },
            )
            if temperatures is None or temperatures
            else None
        ),
        statvfs_fn=lambda _fd: SimpleNamespace(f_bavail=free_bytes, f_frsize=1),
    )
    return envelope, directory_fd


def _receipt_prereg(runner) -> dict[str, Any]:
    contract = runner.source_contract()
    return {
        "candidate_id": "cur0s_commercial_authority_sources_phone_native_v1",
        "run_id": RUN_ID,
        "parent_capsule_sha256": SHA256,
        "parent_frontier_root_sha256": SHA256,
        "maximal_selector_sha256": SHA256,
        "commercial_source_contract": contract,
        "commercial_source_contract_sha256": runner.canonical_sha256(contract),
        "campaign_lease": {"action_id": RUN_ID},
        "resource_slice": {"phone": "fixture"},
        "network_policy": {"https_only": True},
        "preregistration_root_sha256": SHA256,
        "ACCESS_receipt_sha256": SHA256,
    }


def _resolved_epub_grade_sources(sources):
    return tuple(
        replace(
            source,
            epub_identity=(
                None
                if source.epub_identity is None
                else replace(source.epub_identity, opf_grade_values=())
            ),
        )
        for source in sources
    )


def _resolve_fixture_epub_grade_metadata(monkeypatch, runner) -> None:
    monkeypatch.setattr(
        commercial,
        "DIRECT_SOURCES",
        _resolved_epub_grade_sources(commercial.DIRECT_SOURCES),
    )
    monkeypatch.setitem(
        runner.source_contract.__globals__,
        "DIRECT_SOURCES",
        _resolved_epub_grade_sources(runner.DIRECT_SOURCES),
    )


def _terminal_receipt(runner, candidate, state: str = "blocked_fail_closed"):
    receipt = {
        "schema_version": runner.RECEIPT_SCHEMA,
        "run_id": RUN_ID,
        "state": state,
        "execution_claim": candidate.execution_claim_receipt(),
    }
    receipt["receipt_root_sha256"] = runner.canonical_sha256(receipt)
    return receipt


def _claimed_candidate(runner, output: Path):
    """Test-only shortcut; production claim ownership lives exclusively in main()."""

    candidate = runner.PrivateCandidate.prepare(output, RUN_ID, SHA256, SHA256)
    try:
        candidate.publish_execution_claim()
        return candidate
    except BaseException:
        candidate.close()
        raise


def _claim_path(runner) -> Path:
    return runner.PHONE_PACKAGE_ROOT / runner.execution_claim_name(RUN_ID)


def _abort_path(runner) -> Path:
    return runner.PHONE_PACKAGE_ROOT / runner.execution_abort_name(RUN_ID)


def _terminal_complete(runner, receipt, *, completed_at="2026-07-12T12:00:00Z"):
    receipt_payload = runner.canonical_json_bytes(receipt) + b"\n"
    protocol = (
        "raw_sources_fsync_read_only_then_receipt_O_EXCL_fsync_read_only_then_"
        "COMPLETE_O_EXCL_fsync_last"
        if receipt["state"] == "passed_scope"
        else "partial_raw_preserved_then_blocker_receipt_O_EXCL_fsync_read_only_"
        "then_COMPLETE_O_EXCL_fsync_last"
    )
    return {
        "schema_version": runner.COMPLETE_SCHEMA,
        "run_id": RUN_ID,
        "state": receipt["state"],
        "receipt_sha256": _sha(receipt_payload),
        "receipt_root_sha256": receipt["receipt_root_sha256"],
        "receipt_bytes": len(receipt_payload),
        "completion_marker_prepared_at_utc": completed_at,
        "completion_protocol": protocol,
        "raw_sources_preserved_on_phone": True,
        "output_directory_mode": "owner_only_0700",
    }


def _install_main_transaction_mocks(runner, monkeypatch, output: Path):
    now = datetime.now(timezone.utc)
    lease = _lease(runner, now)
    prereg = {
        "run_id": RUN_ID,
        "output_directory_name": "candidate-001",
        "preregistration_root_sha256": SHA256,
        "network_policy": {"allowed_https_hosts": []},
    }

    class FakeEnvelope:
        def __init__(self, lease_arg, candidate, _started):
            self.lease = lease_arg
            self.candidate = candidate
            self.checkpoints = []

        def arm(self):
            return None

        def begin_terminalization(self, checkpoint):
            self.checkpoints.append(checkpoint)

        def check(self, checkpoint, **_kwargs):
            self.checkpoints.append(checkpoint)

        def disarm(self):
            return None

        def receipt_metrics(self):
            return {"action_id": RUN_ID, "phone_execution_ordinal": 1}

    monkeypatch.setattr(runner, "guard_phone_environment", lambda: {})
    monkeypatch.setattr(
        runner,
        "validate_native_preflight_execution_binding",
        lambda *_args: {"native_preflight": "fixture"},
    )
    monkeypatch.setattr(runner, "validate_preregistration", lambda _value: {})
    monkeypatch.setattr(runner, "validate_phone_toolchain", lambda _value: {})
    monkeypatch.setattr(
        runner,
        "validate_phone_runtime",
        lambda *_args, **_kwargs: {"phone_toolchain": {}},
    )
    monkeypatch.setattr(
        runner,
        "revalidate_full_phone_toolchain",
        lambda: {"final_revalidation_passed": True},
    )
    monkeypatch.setattr(runner, "validate_campaign_lease", lambda _value: lease)
    monkeypatch.setattr(runner, "validate_private_output_path", lambda *_args: output)
    monkeypatch.setattr(runner, "preclaim_resource_check", lambda *_args: None)
    monkeypatch.setattr(
        runner,
        "source_contract",
        lambda: {"contract_root_sha256": SHA256, "source_count": 1},
    )
    monkeypatch.setattr(runner, "ResourceEnvelope", FakeEnvelope)
    monkeypatch.setattr(
        runner,
        "build_failure_receipt",
        lambda **kwargs: _terminal_receipt(runner, kwargs["candidate"]),
    )
    monkeypatch.setattr(runner, "emit_committed_receipt", lambda _receipt: None)
    return prereg, runner.canonical_json_bytes(prereg) + b"\n"


def _install_signal_harness(runner, monkeypatch):
    managed = [signal.SIGINT, signal.SIGTERM]
    if hasattr(signal, "SIGHUP"):
        managed.append(signal.SIGHUP)
    handlers = {signum: signal.SIG_DFL for signum in managed}
    mask_calls = []

    def getsignal(signum):
        return handlers.get(signum, signal.SIG_DFL)

    def install(signum, handler):
        previous = handlers.get(signum, signal.SIG_DFL)
        handlers[signum] = handler
        return previous

    def pthread_sigmask(operation, values):
        mask_calls.append((operation, tuple(values)))
        return set()

    monkeypatch.setattr(runner.signal, "getsignal", getsignal)
    monkeypatch.setattr(runner.signal, "signal", install)
    monkeypatch.setattr(runner.signal, "pthread_sigmask", pthread_sigmask)
    return handlers, mask_calls


def _install_empty_success_path(runner, monkeypatch):
    monkeypatch.setattr(
        runner,
        "source_contract",
        lambda: {"contract_root_sha256": SHA256, "source_count": 0},
    )
    monkeypatch.setattr(runner, "DIRECT_SOURCES", ())
    monkeypatch.setattr(runner, "GIT_SOURCES", ())
    monkeypatch.setattr(
        runner,
        "build_source_root",
        lambda _artifacts: {
            "source_root_state": "passed_scope",
            "source_root_sha256": SHA256,
        },
    )
    monkeypatch.setattr(
        runner,
        "build_success_receipt",
        lambda **kwargs: _terminal_receipt(
            runner, kwargs["candidate"], state="passed_scope"
        ),
    )


def test_builder_schema_and_lease_round_trip_runner(
    builder, runner, monkeypatch
) -> None:
    _resolve_fixture_epub_grade_metadata(monkeypatch, runner)
    prereg = _build_prereg(builder, monkeypatch)
    monkeypatch.setattr(
        runner,
        "_PREIMPORT_SOURCE_ATTESTATION",
        {
            "source_commit": prereg["source_commit"],
            "source_file_sha256": prereg["source_file_sha256"],
            "source_file_bindings": prereg["source_file_bindings"],
        },
    )

    def admitted_git(*args: str) -> str:
        if args == ("for-each-ref", "--format=%(refname)", "refs/replace"):
            return ""
        if args == ("rev-parse", "HEAD"):
            return prereg["source_commit"]
        if args[:1] == ("rev-parse",) and args[1].startswith("HEAD:"):
            relative = args[1][5:]
            bindings = prereg["source_file_bindings"]
            if relative not in bindings:
                bindings = prereg["native_preflight"]["native_source_file_bindings"]
            return bindings[relative]["git_blob_oid"]
        if args[:2] == ("status", "--porcelain"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(runner, "git_output", admitted_git)

    identity = runner.validate_preregistration(prereg)
    lease = runner.validate_campaign_lease(
        prereg,
        now=datetime.now(timezone.utc),
    )

    assert prereg["schema_version"] == runner.PREREG_SCHEMA
    assert set(prereg["native_preflight"]["native_source_file_bindings"]) == set(
        commercial.NATIVE_PREFLIGHT_SOURCE_FILES
    )
    assert identity["source_commit"] == FAKE_COMMIT
    assert (
        identity["commercial_source_contract_root_sha256"]
        == prereg["commercial_source_contract"]["contract_root_sha256"]
    )
    assert lease.action_id == RUN_ID
    assert lease.expires_at - lease.issued_at == timedelta(hours=4)
    assert lease.max_wall_seconds == 7200
    assert lease.max_private_output_bytes == 2_147_483_648


def test_builder_rejects_ineligible_contract_before_any_output(
    builder,
    monkeypatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "preregistration.json"
    manifest = tmp_path / "native.manifest"
    envelope = tmp_path / "native-launch-envelope.json"
    monkeypatch.setattr(
        builder,
        "parse_args",
        lambda: Namespace(
            output=str(output),
            native_manifest_output=str(manifest),
            native_launch_envelope_output=str(envelope),
        ),
    )
    monkeypatch.setattr(
        builder,
        "source_contract",
        lambda: {"preregistration_eligibility": {"eligible": False}},
    )
    monkeypatch.setattr(
        builder,
        "build_preregistration",
        lambda _args: pytest.fail("ineligible contract reached preregistration build"),
    )

    with pytest.raises(
        ValueError,
        match="commercial_source_contract_preregistration_ineligible",
    ):
        builder.main()

    assert list(tmp_path.iterdir()) == []


def test_runner_rejects_unresolved_payload_grade_metadata_before_acquisition(
    builder, runner, monkeypatch
) -> None:
    prereg = _build_prereg(builder, monkeypatch)

    with pytest.raises(
        runner.AcquisitionError,
        match="payload_grade_metadata_identity_unresolved",
    ):
        runner.validate_preregistration(prereg)


def test_builder_native_manifest_closes_roles_symlinks_and_execution_plan(
    builder, monkeypatch
) -> None:
    prereg = _build_prereg(builder, monkeypatch)
    payload = builder.build_native_preflight_manifest_bytes(prereg)
    lines = payload.decode("utf-8").splitlines()

    assert lines[0] == "CUR0S_NATIVE_PREFLIGHT_MANIFEST_V3"
    assert lines[-1].startswith(f"EXEC_PLAN\t{RUN_ID}\t")
    assert lines[-1].endswith("\t3\t4\t5\t6")
    exec_fields = lines[-1].split("\t")
    assert len(exec_fields) == 14
    assert exec_fields[5:7] == ["-IBS", "-X"]
    assert exec_fields[7].endswith("/python_pycache_forbidden")
    assert exec_fields[9] == commercial.NATIVE_OUTER_ENVIRONMENT_SHA256
    assert sum("\tnative-self\t" in line for line in lines) == 1
    assert sum(line.endswith("\tpython") for line in lines) == 1
    assert sum(line.endswith("\trunner") for line in lines) == 1
    assert sum(line.endswith("\tpreregistration") for line in lines) == 1
    assert sum(line.startswith("SYMLINK\t") for line in lines) == 10
    assert any(
        line.startswith("SYMLINK\t/system/bin/env\t") and line.endswith("\ttoybox")
        for line in lines
    )
    assert any(
        line.startswith("FILE\t/system/bin/toybox\t")
        and commercial.phone_toolchain_contract()["artifacts"]["system_launcher_env"][
            "sha256"
        ]
        in line
        for line in lines
    )
    assert not any(
        "libonnxruntime.so" in line for line in lines if line.startswith("FILE")
    )


def test_builder_emits_exact_prereg_bound_shell_free_native_launch_envelope(
    builder, monkeypatch
) -> None:
    prereg = _build_prereg(builder, monkeypatch)
    manifest = builder.build_native_preflight_manifest_bytes(prereg)
    envelope = builder.build_native_launch_envelope(prereg, manifest)
    native = prereg["native_preflight"]
    layout = native["execution_layout"]
    prereg_payload = builder.canonical_json_bytes(prereg) + b"\n"

    assert envelope["schema_version"] == "cur0s_native_launch_envelope_v1"
    assert envelope["outer_environment"] == {}
    assert envelope["outer_environment_sha256"] == builder.canonical_sha256({})
    assert envelope["fixed_fd_map"] == commercial.NATIVE_PREFLIGHT_FIXED_FD_MAP
    assert envelope["launcher_path"] == "/system/bin/env"
    assert envelope["launcher_resolved_path"] == "/system/bin/toybox"
    assert envelope["launcher_toolchain_artifact_role"] == "system_launcher_env"
    assert envelope["native_attestation_required"] == {
        "outer_env_observed": True,
        "outer_environment_sha256": builder.canonical_sha256({}),
    }
    assert envelope["launcher_argv"] == [
        "/system/bin/env",
        "-i",
        layout["native_binary_path"],
        "--launch",
        "--manifest",
        layout["manifest_path"],
        "--manifest-sha256",
        _sha(manifest),
        "--expected-preregistration-sha256",
        _sha(prereg_payload),
    ]
    assert envelope["shell_interpolation_allowed"] is False
    assert envelope["malicious_same_UID_tamper_resistance_claimed"] is False
    assert envelope["outer_launch_contract_sha256"] == native["outer_launch_sha256"]
    body = dict(envelope)
    assert body.pop("envelope_root_sha256") == builder.canonical_sha256(body)


def test_manifest_and_launch_envelope_reject_self_consistent_dirty_outer_env(
    builder, monkeypatch
) -> None:
    prereg = deepcopy(_build_prereg(builder, monkeypatch))
    native = prereg["native_preflight"]
    outer = native["outer_launch"]
    outer["outer_environment"] = {"LD_PRELOAD": "/evil/lib.so"}
    outer["outer_environment_sha256"] = builder.canonical_sha256(
        outer["outer_environment"]
    )
    outer["native_attestation_required"]["outer_environment_sha256"] = outer[
        "outer_environment_sha256"
    ]
    native["outer_launch_sha256"] = builder.canonical_sha256(outer)
    native_body = dict(native)
    native_body.pop("contract_root_sha256")
    native["contract_root_sha256"] = builder.canonical_sha256(native_body)
    prereg["native_preflight_sha256"] = builder.canonical_sha256(native)
    _reroot(prereg, builder.canonical_sha256)

    with pytest.raises(
        commercial.CommercialSourceError, match="launch_contract_mismatch"
    ):
        builder.build_native_preflight_manifest_bytes(prereg)


def test_builder_reads_exact_hash_bound_native_build_receipt_without_newline(
    builder, monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(
        builder,
        "git_output",
        lambda *args: _fake_git_output(builder, *args),
    )
    receipt = _native_build_receipt(builder)
    payload = builder.canonical_json_bytes(receipt)
    path = tmp_path / "native-build-receipt.json"
    path.write_bytes(payload)
    path.chmod(0o600)
    monkeypatch.setattr(builder, "require_output_parent", lambda parent: None)
    args = Namespace(
        native_preflight_build_receipt=str(path),
        expected_native_preflight_build_receipt_sha256=_sha(payload),
    )

    assert builder.load_native_preflight_build_receipt(args) == receipt
    path.write_bytes(payload + b"\n")
    args.expected_native_preflight_build_receipt_sha256 = _sha(payload + b"\n")
    with pytest.raises(ValueError, match="not_canonical"):
        builder.load_native_preflight_build_receipt(args)


def test_native_build_v3_validator_rejects_self_consistent_weakened_closure(
    builder,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        builder,
        "git_output",
        lambda *args: _fake_git_output(builder, *args),
    )
    receipt = _native_build_receipt(builder)
    bindings = receipt["source_file_bindings"]
    assert (
        commercial.validate_native_preflight_build_receipt(
            receipt,
            source_commit=FAKE_COMMIT,
            source_file_bindings=bindings,
        )
        == receipt
    )

    def reroot(value: dict[str, Any], *, closure_changed: bool = False) -> None:
        if closure_changed:
            closure = value["toolchain_input_closure"]
            closure.pop("closure_root_sha256", None)
            closure["closure_root_sha256"] = builder.canonical_sha256(closure)
        value.pop("build_receipt_root_sha256", None)
        value["build_receipt_root_sha256"] = builder.canonical_sha256(value)

    weakened = deepcopy(receipt)
    weakened["toolchain_input_closure"]["unmeasured_inputs_allowed"] = True
    reroot(weakened, closure_changed=True)
    with pytest.raises(
        commercial.CommercialSourceError,
        match="toolchain_closure_identity_mismatch",
    ):
        commercial.validate_native_preflight_build_receipt(
            weakened,
            source_commit=FAKE_COMMIT,
            source_file_bindings=bindings,
        )

    injected_header = deepcopy(receipt)
    injected_header["toolchain_input_closure"]["include_trees"][
        "termux_system_headers"
    ]["sha256"] = _sha(b"injected header tree")
    reroot(injected_header, closure_changed=True)
    with pytest.raises(
        commercial.CommercialSourceError,
        match="toolchain_closure_identity_mismatch",
    ):
        commercial.validate_native_preflight_build_receipt(
            injected_header,
            source_commit=FAKE_COMMIT,
            source_file_bindings=bindings,
        )

    mutated_crt = deepcopy(receipt)
    mutated_crt["toolchain_input_closure"]["link_inputs"]["crtbegin_dynamic"][
        "sha256"
    ] = _sha(b"mutated CRT")
    reroot(mutated_crt, closure_changed=True)
    with pytest.raises(
        commercial.CommercialSourceError,
        match="toolchain_closure_identity_mismatch",
    ):
        commercial.validate_native_preflight_build_receipt(
            mutated_crt,
            source_commit=FAKE_COMMIT,
            source_file_bindings=bindings,
        )

    mutated_loader_dependency = deepcopy(receipt)
    mutated_loader_dependency["toolchain_input_closure"]["tool_execution_runtime"][
        "runtime_inputs"
    ]["libllvm"]["sha256"] = _sha(b"mutated LLVM")
    reroot(mutated_loader_dependency, closure_changed=True)
    with pytest.raises(
        commercial.CommercialSourceError,
        match="tool_runtime_schema_invalid",
    ):
        commercial.validate_native_preflight_build_receipt(
            mutated_loader_dependency,
            source_commit=FAKE_COMMIT,
            source_file_bindings=bindings,
        )

    missing_python_mapping = deepcopy(receipt)
    mutated_python_runtime = missing_python_mapping["toolchain_input_closure"][
        "python_runtime"
    ]
    mutated_python_runtime["file_backed_executable_mapping_paths"].pop()
    mutated_python_runtime.pop("python_runtime_root_sha256")
    mutated_python_runtime["python_runtime_root_sha256"] = commercial.canonical_sha256(
        mutated_python_runtime
    )
    reroot(missing_python_mapping, closure_changed=True)
    with pytest.raises(
        commercial.CommercialSourceError,
        match="python_runtime_identity_invalid",
    ):
        commercial.validate_native_preflight_build_receipt(
            missing_python_mapping,
            source_commit=FAKE_COMMIT,
            source_file_bindings=bindings,
        )

    overstated_local_git_binding = deepcopy(receipt)
    overstated_local_git_binding["source_commit_binding_status"] = (
        "phone_locally_verified_git_tree_binding"
    )
    reroot(overstated_local_git_binding)
    with pytest.raises(
        commercial.CommercialSourceError,
        match="source_binding_mismatch",
    ):
        commercial.validate_native_preflight_build_receipt(
            overstated_local_git_binding,
            source_commit=FAKE_COMMIT,
            source_file_bindings=bindings,
        )

    nondeterministic_object = deepcopy(receipt)
    nondeterministic_object["intermediate_objects"]["build_two"]["cur0s_sha256"][
        "sha256"
    ] = _sha(b"different object")
    reroot(nondeterministic_object)
    with pytest.raises(
        commercial.CommercialSourceError,
        match="intermediate_objects_mismatch",
    ):
        commercial.validate_native_preflight_build_receipt(
            nondeterministic_object,
            source_commit=FAKE_COMMIT,
            source_file_bindings=bindings,
        )

    overstated_network = deepcopy(receipt)
    overstated_network["network_syscalls_instrumented"] = True
    reroot(overstated_network)
    with pytest.raises(commercial.CommercialSourceError, match="build_claim_mismatch"):
        commercial.validate_native_preflight_build_receipt(
            overstated_network,
            source_commit=FAKE_COMMIT,
            source_file_bindings=bindings,
        )

    wrong_api = deepcopy(receipt)
    wrong_api["elf_identity"]["android_ident"]["api_level"] = 29
    reroot(wrong_api)
    with pytest.raises(commercial.CommercialSourceError, match="ELF_identity_mismatch"):
        commercial.validate_native_preflight_build_receipt(
            wrong_api,
            source_commit=FAKE_COMMIT,
            source_file_bindings=bindings,
        )

    missing_governing_source = deepcopy(receipt)
    missing_governing_source["source_file_bindings"].pop(
        "scripts/termux/build_cur0s_native_preflight.py"
    )
    reroot(missing_governing_source)
    with pytest.raises(
        commercial.CommercialSourceError,
        match="source_binding_mismatch",
    ):
        commercial.validate_native_preflight_build_receipt(
            missing_governing_source,
            source_commit=FAKE_COMMIT,
            source_file_bindings=bindings,
        )


def test_runner_reconstructs_native_manifest_and_role_closure(
    builder, runner, monkeypatch
) -> None:
    prereg = _build_prereg(builder, monkeypatch)
    prereg_bytes = runner.bootstrap_canonical_json_bytes(prereg) + b"\n"
    manifest = builder.build_native_preflight_manifest_bytes(prereg)
    native = prereg["native_preflight"]
    layout = native["execution_layout"]
    binary = native["build_receipt"]["binary_identity"]
    python = prereg["phone_toolchain_identity"]["artifacts"]["python"]
    runner_binding = prereg["source_file_bindings"][
        "scripts/termux/run_cur0s_commercial_sources.py"
    ]
    attestation = {
        "entries_verified": len(native["static_manifest_records"]) + 1,
        "fixed_fds": {
            "manifest": 5,
            "native_attestation": 4,
            "preregistration": 6,
            "python_exec_cloexec": 7,
            "runner": 3,
        },
        "helper_dependency_swap_safety_claimed": False,
        "manifest_sha256": _sha(manifest),
        "mode": "launch",
        **_native_maps_attestation(native),
        "outer_env_observed": True,
        "outer_environment_sha256": (runner.EXPECTED_NATIVE_OUTER_ENVIRONMENT_SHA256),
        "passes_completed": 2,
        "persistent_writes": False,
        "pid": os.getpid(),
        "python_pycache_prefix": native["python_pycache_prefix"],
        "python_pycache_prefix_absent": True,
        "roles": {
            "native-self": {
                "bytes": binary["bytes"],
                "path": layout["native_binary_path"],
                "sha256": binary["sha256"],
            },
            "preregistration": {
                "bytes": len(prereg_bytes),
                "path": layout["preregistration_path"],
                "sha256": _sha(prereg_bytes),
            },
            "python": {
                "bytes": python["bytes"],
                "path": python["resolved_path"],
                "sha256": python["sha256"],
            },
            "runner": {
                "bytes": runner_binding["bytes"],
                "path": layout["runner_path"],
                "sha256": runner_binding["sha256"],
            },
        },
        "run_id": RUN_ID,
        "schema_version": "cur0s_native_launch_attestation_v2",
        "security_ceiling": (
            "observational_only_no_guarantee_against_a_concurrent_malicious_"
            "same_uid_between_checks"
        ),
        "status": "verified",
    }
    monkeypatch.setattr(runner, "_NATIVE_PREFLIGHT_EXEC_ATTESTATION", attestation)
    monkeypatch.setattr(runner, "_NATIVE_PREFLIGHT_MANIFEST_BYTES", manifest)
    monkeypatch.setattr(
        runner,
        "_NATIVE_PREFLIGHT_PREREGISTRATION_BYTES",
        prereg_bytes,
    )
    monkeypatch.setattr(runner, "_NATIVE_PREFLIGHT_MANIFEST_IDENTITY", (5,))
    monkeypatch.setattr(
        runner,
        "_NATIVE_PREFLIGHT_PREREGISTRATION_IDENTITY",
        (6,),
    )
    monkeypatch.setattr(
        runner, "revalidate_inherited_path_binding", lambda *_args: None
    )

    identity = runner.validate_native_preflight_execution_binding(
        prereg,
        prereg_bytes,
    )
    assert identity["same_pid_execveat_verified"] is True
    assert identity["sealed_memfd_attestation_verified"] is True

    monkeypatch.setattr(
        runner,
        "_NATIVE_PREFLIGHT_MANIFEST_BYTES",
        manifest + b"FILE\t/extra\n",
    )
    with pytest.raises(runner.AcquisitionError, match="manifest_closure_mismatch"):
        runner.validate_native_preflight_execution_binding(prereg, prereg_bytes)


def test_builder_rejects_invalid_run_hash_and_uncommitted_bound_source(
    builder, monkeypatch
) -> None:
    with pytest.raises(ValueError, match="invalid_run_id"):
        builder.build_campaign_lease("moving-latest", datetime.now(timezone.utc))
    with pytest.raises(ValueError, match="invalid_sha256"):
        builder.normalize_sha("not-a-sha")

    def dirty_git(*args: str) -> str:
        if args == ("for-each-ref", "--format=%(refname)", "refs/replace"):
            return ""
        if args == ("rev-parse", "HEAD"):
            return FAKE_COMMIT
        if args[:2] == ("status", "--short"):
            return " M bound-source.py"
        raise AssertionError(args)

    monkeypatch.setattr(builder, "git_output", dirty_git)
    with pytest.raises(ValueError, match="source_file_not_committed"):
        builder.build_preregistration(
            Namespace(
                run_id=RUN_ID,
                parent_capsule_sha256=PARENT_CAPSULE_SHA256,
                parent_frontier_root_sha256=PARENT_FRONTIER_ROOT_SHA256,
                output="unused",
            )
        )


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("parent_capsule_sha256", "parent_capsule_sha256_mismatch"),
        ("parent_frontier_root_sha256", "parent_frontier_root_sha256_mismatch"),
    ],
)
def test_builder_rejects_well_formed_but_wrong_sovereign_parent(
    builder, field: str, message: str
) -> None:
    values = {
        "run_id": RUN_ID,
        "parent_capsule_sha256": PARENT_CAPSULE_SHA256,
        "parent_frontier_root_sha256": PARENT_FRONTIER_ROOT_SHA256,
        "output": "unused",
    }
    values[field] = "sha256:" + "9" * 64
    with pytest.raises(ValueError, match=message):
        builder.build_preregistration(Namespace(**values))


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda lease: lease.pop("max_wall_seconds"), "field_set"),
        (lambda lease: lease.__setitem__("max_wall_seconds", True), "max_wall"),
        (lambda lease: lease.__setitem__("action_id", "wrong"), "action"),
        (
            lambda lease: lease["thermal_safety_contract"][
                "group_ceilings_millidegrees_c"
            ].__setitem__("skin", 85_000),
            "thermal_contract",
        ),
        (lambda lease: lease.__setitem__("additional_paid_capacity", True), "state"),
    ],
)
def test_campaign_lease_rejects_schema_and_authority_mutation(
    builder, runner, mutation, message: str
) -> None:
    issued = datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc)
    prereg = {
        "run_id": RUN_ID,
        "campaign_lease": builder.build_campaign_lease(RUN_ID, issued),
    }
    mutation(prereg["campaign_lease"])
    with pytest.raises(runner.AcquisitionError, match=message):
        runner.validate_campaign_lease(prereg, now=issued + timedelta(hours=1))


def test_bootstrap_accepts_canonical_prereg_and_exact_bound_bytes(
    builder, runner, monkeypatch, tmp_path
) -> None:
    prereg = _build_prereg(builder, monkeypatch)
    checkout, payloads = _bootstrap_checkout(tmp_path, runner)
    prereg_bytes = runner.bootstrap_canonical_json_bytes(prereg) + b"\n"
    _install_bootstrap_mocks(runner, monkeypatch, checkout, prereg_bytes)

    observed_bytes, observed, source_bytes, attestation = runner.bootstrap_authority(
        Namespace(
            preregistration="fixture",
            expected_preregistration_sha256=_sha(prereg_bytes),
        )
    )

    assert observed_bytes == prereg_bytes
    assert observed == prereg
    assert source_bytes == payloads
    assert attestation["bound_contract_bytes_verified_before_contract_import"] is True
    assert attestation["external_preregistration_sha256_verified"] is True


def test_bootstrap_rejects_wrong_external_preregistration_digest_before_trust(
    builder, runner, monkeypatch, tmp_path
) -> None:
    prereg = _build_prereg(builder, monkeypatch)
    checkout, _payloads = _bootstrap_checkout(tmp_path, runner)
    prereg_bytes = runner.bootstrap_canonical_json_bytes(prereg) + b"\n"
    _install_bootstrap_mocks(runner, monkeypatch, checkout, prereg_bytes)

    with pytest.raises(runner.BootstrapError, match="external_preregistration"):
        runner.bootstrap_authority(
            Namespace(
                preregistration="fixture",
                expected_preregistration_sha256="sha256:" + "0" * 64,
            )
        )


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("noncanonical", "not_canonical"),
        ("root", "root_mismatch"),
        ("contract_hash", "contract_sha256_mismatch"),
        ("source_hash", "source_file_hash_binding_mismatch"),
    ],
)
def test_bootstrap_rejects_authority_tamper(
    builder, runner, monkeypatch, tmp_path, case: str, message: str
) -> None:
    prereg = _build_prereg(builder, monkeypatch)
    checkout, _payloads = _bootstrap_checkout(tmp_path, runner)
    if case == "root":
        prereg["preregistration_root_sha256"] = "sha256:" + "0" * 64
    elif case == "contract_hash":
        prereg["commercial_source_contract_sha256"] = "sha256:" + "0" * 64
        _reroot(prereg, runner.bootstrap_canonical_sha256)
    elif case == "source_hash":
        prereg["source_file_sha256"]["runner_sha256"] = "sha256:" + "0" * 64
        _reroot(prereg, runner.bootstrap_canonical_sha256)
    prereg_bytes = runner.bootstrap_canonical_json_bytes(prereg) + b"\n"
    if case == "noncanonical":
        prereg_bytes = b" " + prereg_bytes
    _install_bootstrap_mocks(
        runner,
        monkeypatch,
        checkout,
        prereg_bytes,
    )

    with pytest.raises(runner.BootstrapError, match=message):
        runner.bootstrap_authority(
            Namespace(
                preregistration="fixture",
                expected_preregistration_sha256=_sha(prereg_bytes),
            )
        )


def test_bootstrap_rejects_bound_source_byte_replacement(
    builder, runner, monkeypatch, tmp_path
) -> None:
    prereg = _build_prereg(builder, monkeypatch)
    checkout, _payloads = _bootstrap_checkout(tmp_path, runner)
    runner_path = checkout / runner.BOUND_SOURCE_FILES[1]
    runner_path.write_bytes(runner_path.read_bytes() + b"\n# injected\n")
    prereg_bytes = runner.bootstrap_canonical_json_bytes(prereg) + b"\n"
    _install_bootstrap_mocks(runner, monkeypatch, checkout, prereg_bytes)

    with pytest.raises(runner.BootstrapError, match="source_file_binding_mismatch"):
        runner.bootstrap_authority(
            Namespace(
                preregistration="fixture",
                expected_preregistration_sha256=_sha(prereg_bytes),
            )
        )


def test_preimport_device_guard_is_exact_and_uses_minimal_environment(
    runner, monkeypatch
) -> None:
    monkeypatch.setattr(runner.platform, "machine", lambda: "aarch64")
    monkeypatch.setattr(runner.platform, "system", lambda: "Android")
    monkeypatch.setattr(
        runner.Path, "home", classmethod(lambda _cls: runner.PHONE_HOME)
    )
    startup = _exact_startup_identity(runner)
    monkeypatch.setattr(runner, "observe_python_startup_identity", lambda: startup)
    monkeypatch.setattr(runner, "attest_executed_runner_fd", lambda: {})
    monkeypatch.setattr(runner, "bootstrap_native_preflight_guard", lambda: {})
    monkeypatch.setattr(runner.os.path, "lexists", lambda _path: False)
    monkeypatch.setattr(
        runner.sys,
        "path",
        list(runner.EXPECTED_PYTHON_INITIAL_SYS_PATH),
    )
    calls: list[tuple[list[str], dict[str, str]]] = []
    fingerprint = b"fixture-fingerprint\n"
    monkeypatch.setattr(
        runner,
        "EXPECTED_BUILD_FINGERPRINT_SHA256",
        _sha(fingerprint),
    )
    revalidations: list[frozenset[str]] = []
    monkeypatch.setattr(
        runner,
        "revalidate_attested_toolchain_roles",
        lambda roles: revalidations.append(roles),
    )
    monkeypatch.setattr(
        runner,
        "open_attested_executable_fd",
        lambda _executable: os.open(os.devnull, os.O_RDONLY),
    )

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs["env"]))
        prop = argv[-1]
        values = {
            "ro.product.model": b"NX789J\n",
            "ro.product.device": b"NX789J\n",
            "ro.soc.model": b"SM8750\n",
            "ro.build.fingerprint": fingerprint,
            "ro.vendor.feature.zte_feature_ccc_bat_temp_cntrl": b"true\n",
            "ro.vendor.feature.zte_feature_ccc_temp_threshold": (
                b"skin,54,battery,45\n"
            ),
        }
        return SimpleNamespace(stdout=values[prop], stderr=b"")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    runner.preimport_phone_guard()

    assert len(calls) == 6
    assert len(revalidations) == 12
    assert all("android_getprop" in roles for roles in revalidations)
    for argv, environment in calls:
        assert argv[0] == "/system/bin/getprop"
        assert environment == {
            "ANDROID_ROOT": "/system",
            "HOME": str(runner.PHONE_HOME),
            "PATH": "/system/bin:/data/data/com.termux/files/usr/bin",
            "LC_ALL": "C",
        }
    monkeypatch.setattr(runner.platform, "system", lambda: "Linux")
    with pytest.raises(runner.BootstrapError, match="android_aarch64"):
        runner.preimport_phone_guard()


@pytest.mark.parametrize(
    ("stdout", "stderr"),
    [
        (b"value", b""),
        (b"value\n\n", b""),
        (b"prefix\nsuffix\n", b""),
        (b" value\n", b""),
        (b"value \n", b""),
        (b"value\t\n", b""),
        (b"value\r\n", b""),
        (b"\n", b""),
        (b"value\n", b"spoofed diagnostic"),
    ],
)
def test_getprop_rejects_noncanonical_or_spoofable_response_shapes(
    runner,
    monkeypatch,
    stdout: bytes,
    stderr: bytes,
) -> None:
    monkeypatch.setattr(
        runner,
        "revalidate_attested_toolchain_roles",
        lambda _roles: None,
    )
    monkeypatch.setattr(
        runner,
        "open_attested_executable_fd",
        lambda _executable: os.open(os.devnull, os.O_RDONLY),
    )
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout=stdout, stderr=stderr),
    )

    with pytest.raises(runner.AcquisitionError, match="getprop_response_shape_invalid"):
        runner.getprop("ro.product.model")


def test_native_preflight_bootstrap_requires_exact_sealed_same_pid_handoff(
    runner, monkeypatch
) -> None:
    manifest = b"native manifest\n"
    layout = {
        "launch_envelope_path": "/phone/native_launch_envelope.json",
        "manifest_path": "/phone/native.manifest",
        "native_binary_path": "/phone/native",
        "preregistration_path": "/phone/prereg.json",
    }
    outer_launch = runner.bootstrap_expected_native_outer_launch_contract(layout)
    prereg = (
        runner.bootstrap_canonical_json_bytes(
            {
                "phone_toolchain_identity": commercial.phone_toolchain_contract(),
                "native_preflight": {
                    "execution_layout": layout,
                    "fixed_fd_map": dict(runner.EXPECTED_NATIVE_PREFLIGHT_FIXED_FD_MAP),
                    "python_pycache_prefix": "/phone/pycache",
                    "python_pycache_prefix_must_be_absent": True,
                    "outer_launch": outer_launch,
                    "outer_launch_sha256": runner.bootstrap_canonical_sha256(
                        outer_launch
                    ),
                },
            }
        )
        + b"\n"
    )
    runner._EXECUTED_RUNNER_IDENTITY = {
        "bytes": 13,
        "path": "/phone/runner.py",
        "sha256": _sha(b"exact-runner"),
    }
    receipt = {
        "entries_verified": 45,
        "fixed_fds": {
            "manifest": 5,
            "native_attestation": 4,
            "preregistration": 6,
            "python_exec_cloexec": 7,
            "runner": 3,
        },
        "helper_dependency_swap_safety_claimed": False,
        "manifest_sha256": _sha(manifest),
        "mode": "launch",
        "native_maps": {},
        "native_maps_root_sha256": runner.bootstrap_canonical_sha256({}),
        "outer_env_observed": True,
        "outer_environment_sha256": (runner.EXPECTED_NATIVE_OUTER_ENVIRONMENT_SHA256),
        "passes_completed": 2,
        "persistent_writes": False,
        "pid": os.getpid(),
        "python_pycache_prefix": "/phone/pycache",
        "python_pycache_prefix_absent": True,
        "roles": {
            "native-self": {
                "bytes": 1,
                "path": "/phone/native",
                "sha256": SHA256,
            },
            "preregistration": {
                "bytes": len(prereg),
                "path": "/phone/prereg.json",
                "sha256": _sha(prereg),
            },
            "python": {
                "bytes": 1,
                "path": "/phone/python",
                "sha256": SHA256,
            },
            "runner": dict(runner._EXECUTED_RUNNER_IDENTITY),
        },
        "run_id": RUN_ID,
        "schema_version": "cur0s_native_launch_attestation_v2",
        "security_ceiling": (
            "observational_only_no_guarantee_against_a_concurrent_malicious_"
            "same_uid_between_checks"
        ),
        "status": "verified",
    }
    receipt_payload = runner.bootstrap_canonical_json_bytes(receipt)
    payloads = {
        runner.NATIVE_PREFLIGHT_ATTESTATION_FD: receipt_payload,
        runner.NATIVE_PREFLIGHT_MANIFEST_FD: manifest,
        runner.NATIVE_PREFLIGHT_PREREGISTRATION_FD: prereg,
    }
    monkeypatch.setattr(
        runner,
        "bootstrap_read_inherited_fd",
        lambda fd, **_kwargs: (payloads[fd], (fd,)),
    )
    monkeypatch.setattr(
        runner.fcntl,
        "fcntl",
        lambda *_args: 0x0001 | 0x0002 | 0x0004 | 0x0008,
    )
    monkeypatch.setattr(runner.os, "close", lambda _fd: None)
    monkeypatch.setattr(runner, "bootstrap_validate_native_maps", lambda *_args: None)
    original_fstat = runner.os.fstat

    def fstat(fd):
        if fd == 7:
            raise OSError("closed-on-exec")
        return original_fstat(fd)

    monkeypatch.setattr(runner.os, "fstat", fstat)

    observed = runner.bootstrap_native_preflight_guard()
    assert observed == receipt
    assert runner._NATIVE_PREFLIGHT_MANIFEST_BYTES == manifest
    assert runner._NATIVE_PREFLIGHT_PREREGISTRATION_BYTES == prereg

    receipt["pid"] += 1
    payloads[runner.NATIVE_PREFLIGHT_ATTESTATION_FD] = (
        runner.bootstrap_canonical_json_bytes(receipt)
    )
    with pytest.raises(runner.BootstrapError, match="claim_mismatch"):
        runner.bootstrap_native_preflight_guard()


def test_native_maps_bootstrap_accepts_build_receipt_bound_self_mapping(runner) -> None:
    runtime_shapes = {
        "android_linker64": (0x4C000, 0x116000),
        "android_bionic_libc": (0x48000, 0x8F000),
        "android_bionic_libdl": (0x4000, 0x1000),
        "android_bionic_libm": (0x14000, 0x24000),
        "system_libcxx": (0x84000, 0x7B000),
        "system_libnetd_client": (0x4000, 0x4000),
    }
    static_records = [
        {
            "bytes": 1000 + index,
            "path": f"/system/{role}.so",
            "record_type": "FILE",
            "sha256": SHA256,
            "toolchain_role": role,
        }
        for index, role in enumerate(runtime_shapes)
    ]
    native_self = {
        "bytes": 4096,
        "path": "/phone/cur0s_native_preflight",
        "record_type": "FILE",
        "runtime_role": "native_self",
        "sha256": SHA256,
    }
    static_records.append(native_self)
    native_self_shape = {
        "mapped_bytes": 0x3000,
        "offset": 0x1000,
        "source": "deterministic_build_receipt_executable_PT_LOAD",
    }
    maps_contract = {
        "capture_timing": "first_action_in_main_before_argument_parsing",
        "executable_mapping_policy": (
            "exact_nine_record_phone_native_runtime_closure_only"
        ),
        "normalized_fields": [
            "bytes",
            "device_major",
            "device_minor",
            "inode",
            "mapped_bytes",
            "offset",
            "path",
            "permissions",
            "runtime_role",
            "sha256",
        ],
        "record_count": 9,
        "native_self_executable_map": native_self_shape,
        "schema_version": "cur0s_native_earliest_main_maps_v1",
        "start_and_end_addresses_excluded_as_ASLR_only": True,
        "unexpected_executable_mappings_forbidden": True,
        "vvar_required_nonexecutable": True,
    }

    records = []
    for index, (role, (offset, mapped_bytes)) in enumerate(runtime_shapes.items()):
        source = static_records[index]
        records.append(
            {
                "bytes": source["bytes"],
                "device_major": 1,
                "device_minor": 2,
                "inode": 100 + index,
                "mapped_bytes": mapped_bytes,
                "offset": offset,
                "path": source["path"],
                "permissions": "r-xp",
                "runtime_role": role,
                "sha256": source["sha256"],
            }
        )
    records.extend(
        [
            {
                "bytes": native_self["bytes"],
                "device_major": 1,
                "device_minor": 2,
                "inode": 999,
                "mapped_bytes": native_self_shape["mapped_bytes"],
                "offset": native_self_shape["offset"],
                "path": native_self["path"],
                "permissions": "r-xp",
                "runtime_role": "native-self",
                "sha256": native_self["sha256"],
            },
            {
                "bytes": None,
                "device_major": 0,
                "device_minor": 0,
                "inode": 0,
                "mapped_bytes": 0x1000,
                "offset": 0,
                "path": "[vdso]",
                "permissions": "r-xp",
                "runtime_role": "kernel_vdso",
                "sha256": None,
            },
            {
                "bytes": None,
                "device_major": 0,
                "device_minor": 0,
                "inode": 0,
                "mapped_bytes": 0x2000,
                "offset": 0,
                "path": "[vvar]",
                "permissions": "r--p",
                "runtime_role": "kernel_vvar",
                "sha256": None,
            },
        ]
    )
    records.sort(
        key=lambda record: (
            record["path"],
            record["offset"],
            record["permissions"],
            record["inode"],
        )
    )
    maps = {
        "capture_timing": maps_contract["capture_timing"],
        "executable_mapping_policy": maps_contract["executable_mapping_policy"],
        "production_policy_enforced": True,
        "records": records,
        "schema_version": maps_contract["schema_version"],
        "unexpected_executable_mappings_absent": True,
        "vvar": {"nonexecutable": True, "present": True},
    }
    attestation = {
        "native_maps": maps,
        "native_maps_root_sha256": runner.bootstrap_canonical_sha256(maps),
    }
    contract = {
        "native_maps_contract": maps_contract,
        "static_manifest_records": static_records,
    }

    runner.bootstrap_validate_native_maps(attestation, contract)

    contract["native_maps_contract"] = {
        key: value
        for key, value in maps_contract.items()
        if key != "native_self_executable_map"
    }
    with pytest.raises(
        runner.BootstrapError, match="native_attestation_self_map_contract_invalid"
    ):
        runner.bootstrap_validate_native_maps(attestation, contract)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda native: native["fixed_fd_map"].__setitem__("native_attestation", 8),
            "fixed_fd_map_mismatch",
        ),
        (
            lambda native: native["fixed_fd_map"].__setitem__(
                "sealed_native_receipt", 4
            ),
            "fixed_fd_map_mismatch",
        ),
        (
            lambda native: native["outer_launch"]["outer_environment"].__setitem__(
                "LD_PRELOAD", "/evil/lib.so"
            ),
            "outer_launch_contract_mismatch",
        ),
    ],
)
def test_bootstrap_rejects_prereg_fd_map_and_dirty_outer_launch_declarations(
    runner, mutation, message: str
) -> None:
    layout = {
        "launch_envelope_path": "/phone/native_launch_envelope.json",
        "manifest_path": "/phone/native.manifest",
        "native_binary_path": "/phone/native",
        "preregistration_path": "/phone/prereg.json",
    }
    outer_launch = runner.bootstrap_expected_native_outer_launch_contract(layout)
    native = {
        "execution_layout": layout,
        "fixed_fd_map": dict(runner.EXPECTED_NATIVE_PREFLIGHT_FIXED_FD_MAP),
        "outer_launch": outer_launch,
        "outer_launch_sha256": runner.bootstrap_canonical_sha256(outer_launch),
    }
    mutation(native)
    if "LD_PRELOAD" in native["outer_launch"]["outer_environment"]:
        native["outer_launch"]["outer_environment_sha256"] = (
            runner.bootstrap_canonical_sha256(
                native["outer_launch"]["outer_environment"]
            )
        )
        native["outer_launch_sha256"] = runner.bootstrap_canonical_sha256(
            native["outer_launch"]
        )
    payload = (
        runner.bootstrap_canonical_json_bytes(
            {
                "native_preflight": native,
                "phone_toolchain_identity": commercial.phone_toolchain_contract(),
            }
        )
        + b"\n"
    )

    with pytest.raises(runner.BootstrapError, match=message):
        runner.bootstrap_native_contract_from_preregistration(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("outer_env_observed", False),
        ("outer_environment_sha256", "sha256:" + "0" * 64),
        (
            "fixed_fds",
            {
                "manifest": 5,
                "preregistration": 6,
                "runner": 3,
                "sealed_native_receipt": 4,
            },
        ),
    ],
)
def test_runtime_binding_rejects_native_outer_environment_attestation_mismatch(
    builder, runner, monkeypatch, field: str, value: Any
) -> None:
    prereg = _build_prereg(builder, monkeypatch)
    prereg_bytes = runner.bootstrap_canonical_json_bytes(prereg) + b"\n"
    manifest = builder.build_native_preflight_manifest_bytes(prereg)
    native = prereg["native_preflight"]
    layout = native["execution_layout"]
    binary = native["build_receipt"]["binary_identity"]
    python = prereg["phone_toolchain_identity"]["artifacts"]["python"]
    runner_binding = prereg["source_file_bindings"][runner.BOUND_SOURCE_FILES[1]]
    attestation = {
        "entries_verified": len(native["static_manifest_records"]) + 1,
        "fixed_fds": dict(runner.EXPECTED_NATIVE_PREFLIGHT_FIXED_FD_MAP),
        "helper_dependency_swap_safety_claimed": False,
        "manifest_sha256": _sha(manifest),
        "mode": "launch",
        **_native_maps_attestation(native),
        "outer_env_observed": True,
        "outer_environment_sha256": (runner.EXPECTED_NATIVE_OUTER_ENVIRONMENT_SHA256),
        "passes_completed": 2,
        "persistent_writes": False,
        "pid": os.getpid(),
        "python_pycache_prefix": native["python_pycache_prefix"],
        "python_pycache_prefix_absent": True,
        "roles": {
            "native-self": {
                "bytes": binary["bytes"],
                "path": layout["native_binary_path"],
                "sha256": binary["sha256"],
            },
            "preregistration": {
                "bytes": len(prereg_bytes),
                "path": layout["preregistration_path"],
                "sha256": _sha(prereg_bytes),
            },
            "python": {
                "bytes": python["bytes"],
                "path": python["resolved_path"],
                "sha256": python["sha256"],
            },
            "runner": {
                "bytes": runner_binding["bytes"],
                "path": layout["runner_path"],
                "sha256": runner_binding["sha256"],
            },
        },
        "run_id": RUN_ID,
        "schema_version": "cur0s_native_launch_attestation_v2",
        "security_ceiling": (
            "observational_only_no_guarantee_against_a_concurrent_malicious_"
            "same_uid_between_checks"
        ),
        "status": "verified",
    }
    attestation[field] = value
    monkeypatch.setattr(runner, "_NATIVE_PREFLIGHT_EXEC_ATTESTATION", attestation)
    monkeypatch.setattr(runner, "_NATIVE_PREFLIGHT_MANIFEST_BYTES", manifest)
    monkeypatch.setattr(runner, "_NATIVE_PREFLIGHT_PREREGISTRATION_BYTES", prereg_bytes)
    monkeypatch.setattr(runner, "_NATIVE_PREFLIGHT_MANIFEST_IDENTITY", (5,))
    monkeypatch.setattr(runner, "_NATIVE_PREFLIGHT_PREREGISTRATION_IDENTITY", (6,))

    with pytest.raises(runner.AcquisitionError, match="attestation_binding_mismatch"):
        runner.validate_native_preflight_execution_binding(prereg, prereg_bytes)


@pytest.mark.parametrize(
    ("field", "mutate"),
    [
        (
            "sys_executable",
            lambda value: value.__setitem__("sys_executable", "/evil/python"),
        ),
        ("prefix", lambda value: value.__setitem__("prefix", "/evil/prefix")),
        (
            "initial_sys_path",
            lambda value: value["initial_sys_path"].insert(0, "/evil/site"),
        ),
        (
            "sys_flags",
            lambda value: value["sys_flags"].__setitem__("isolated", 0),
        ),
        ("xoptions", lambda value: value["xoptions"].__setitem__("dev", True)),
        (
            "environment",
            lambda value: value["environment"].__setitem__("PYTHONPATH", "/evil/site"),
        ),
        ("orig_argv", lambda value: value["orig_argv"].insert(1, "-O")),
    ],
)
def test_python_startup_identity_rejects_every_authority_surface(
    runner, field: str, mutate
) -> None:
    observed = deepcopy(_exact_startup_identity(runner))
    mutate(observed)
    with pytest.raises(runner.BootstrapError, match=f"python_startup_{field}"):
        runner.require_exact_python_startup(observed)


def test_executed_runner_fd_is_inode_and_hash_bound_to_checkout_entry(
    runner, monkeypatch, tmp_path
) -> None:
    relative = runner.BOUND_SOURCE_FILES[1]
    runner_path = tmp_path / relative
    runner_path.parent.mkdir(parents=True)
    runner_path.write_bytes(b"exact runner bytes")
    fd = os.open(runner_path, os.O_RDONLY)
    try:
        fd_path = f"/dev/fd/{fd}"
        monkeypatch.setattr(runner, "ROOT", tmp_path)
        monkeypatch.setattr(runner, "RUNNER_EXECUTION_FD", fd)
        monkeypatch.setattr(runner, "RUNNER_EXECUTION_PATH", fd_path)
        monkeypatch.setattr(runner.os, "readlink", lambda _path: str(runner_path))
        identity = runner.attest_executed_runner_fd()
        assert identity["sha256"] == _sha(b"exact runner bytes")

        replacement = tmp_path / "replacement"
        replacement.write_bytes(b"different runner")
        os.replace(replacement, runner_path)
        with pytest.raises(runner.BootstrapError, match="path_mismatch|inode_mismatch"):
            runner.attest_executed_runner_fd()
    finally:
        os.close(fd)


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/openstax/repo.git",
        "https://user@github.com/openstax/repo.git",
        "https://github.com:444/openstax/repo.git",
        "https://evil.example/openstax/repo.git",
        "https://github.com/openstax/repo.git#fragment",
    ],
)
def test_https_network_policy_rejects_cleartext_credentials_ports_and_hosts(
    runner, url: str
) -> None:
    with pytest.raises(runner.AcquisitionError, match="https_url"):
        runner.validate_https_url(url, frozenset({"github.com"}))


def test_transport_subprocess_policies_disable_redirects_credentials_and_resume(
    runner,
) -> None:
    git_options = runner.git_safety_options()
    assert "http.followRedirects=false" in git_options
    assert "credential.helper=" in git_options
    assert "protocol.allow=never" in git_options
    assert "protocol.https.allow=always" in git_options
    assert "protocol.file.allow=never" in git_options
    assert runner.git_environment()["GIT_TERMINAL_PROMPT"] == "0"
    assert runner.git_environment()["LD_PRELOAD"] == runner.TERMUX_EXEC_INTERPOSER
    assert runner.git_environment()["GIT_EXEC_PATH"] == runner.GIT_EXEC_PATH
    assert runner.git_environment()["GIT_OPTIONAL_LOCKS"] == "0"
    assert runner.git_environment()["GIT_NO_REPLACE_OBJECTS"] == "1"
    assert runner.curl_environment()["PATH"].startswith(
        "/data/data/com.termux/files/usr/bin"
    )


def test_real_git_replace_ref_is_rejected_and_never_changes_canonical_blob(
    builder, monkeypatch, tmp_path
) -> None:
    repository = tmp_path / "replace-repo"
    repository.mkdir()

    def git(*args: str) -> str:
        return subprocess.run(
            ["/usr/bin/git", *args],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
            env={
                "GIT_CONFIG_GLOBAL": "/dev/null",
                "GIT_CONFIG_NOSYSTEM": "1",
                "HOME": str(tmp_path),
                "LC_ALL": "C",
                "PATH": "/usr/bin:/bin",
            },
        ).stdout.strip()

    git("init", "--quiet")
    (repository / "bound.py").write_text("A\n", encoding="utf-8")
    git("add", "bound.py")
    git(
        "-c",
        "user.name=fixture",
        "-c",
        "user.email=f@x",
        "commit",
        "--quiet",
        "-m",
        "A",
    )
    original = git("rev-parse", "HEAD")
    (repository / "bound.py").write_text("B\n", encoding="utf-8")
    git("add", "bound.py")
    git(
        "-c",
        "user.name=fixture",
        "-c",
        "user.email=f@x",
        "commit",
        "--quiet",
        "-m",
        "B",
    )
    replacement = git("rev-parse", "HEAD")
    git("replace", original, replacement)
    git("checkout", "--quiet", "--detach", original)
    assert (repository / "bound.py").read_text(encoding="utf-8") == "B\n"

    monkeypatch.setattr(builder, "ROOT", repository)
    assert builder.git_output("show", f"{original}:bound.py") == "A"
    with pytest.raises(ValueError, match="replace_refs_forbidden"):
        builder.build_preregistration(
            Namespace(
                run_id=RUN_ID,
                parent_capsule_sha256=PARENT_CAPSULE_SHA256,
                parent_frontier_root_sha256=PARENT_FRONTIER_ROOT_SHA256,
                output="unused",
            )
        )


@pytest.fixture(scope="module")
def local_tls_material(tmp_path_factory):
    directory = tmp_path_factory.mktemp("cur0s-range-tls")
    certificate = directory / "certificate.pem"
    private_key = directory / "private-key.pem"
    openssl = shutil.which("openssl")
    assert openssl is not None
    subprocess.run(
        [
            openssl,
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost",
            "-keyout",
            str(private_key),
            "-out",
            str(certificate),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    return certificate, private_key


def _start_adversarial_range_server(
    local_tls_material,
    payload: bytes,
    *,
    mode: str,
    chunk_bytes: int,
):
    certificate, private_key = local_tls_material
    etag = '"range-fixture"'
    last_modified = "Sun, 12 Jul 2026 10:00:00 GMT"
    state = SimpleNamespace(
        full_requests=0,
        ranges=[],
        attempts={},
    )

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, _format, *_args):
            return

        def do_GET(self):
            range_value = self.headers.get("Range")
            if range_value is None:
                state.full_requests += 1
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("ETag", etag)
                self.send_header("Last-Modified", last_modified)
                self.send_header("Content-Type", "application/octet-stream")
                self.end_headers()
                self._write_then_reset(payload[:chunk_bytes])
                return
            match = __import__("re").fullmatch(r"bytes=([0-9]+)-([0-9]+)", range_value)
            if match is None:
                self.send_error(400)
                return
            start, end = (int(value) for value in match.groups())
            state.ranges.append((start, end))
            key = (start, end)
            state.attempts[key] = state.attempts.get(key, 0) + 1
            if mode == "ignored":
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("ETag", etag)
                self.send_header("Last-Modified", last_modified)
                self.send_header("Content-Type", "application/octet-stream")
                self.end_headers()
                return
            body = payload[start : end + 1]
            response_etag = '"raced"' if mode == "race" and start > 0 else etag
            total = len(payload) + 1 if mode == "malformed" else len(payload)
            self.send_response(206)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("ETag", response_etag)
            self.send_header("Last-Modified", last_modified)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Range", f"bytes {start}-{end}/{total}")
            self.end_headers()
            should_reset = (
                mode == "reset_once"
                and start == chunk_bytes
                and state.attempts[key] == 1
            )
            if should_reset:
                self._write_then_reset(body[: max(1, len(body) // 2)])
                return
            try:
                self.wfile.write(body)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _write_then_reset(self, body):
            try:
                self.wfile.write(body)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.connection.close()
            self.close_connection = True

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certificate, private_key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, state, etag, last_modified, certificate


def _local_curl_monitored(runner, certificate: Path):
    def invoke(argv, **kwargs):
        portable_argv = [
            value.replace("/proc/self/fd/", str(runner.FD_PATH_ROOT) + "/")
            for value in argv
        ]
        environment = {
            **os.environ,
            **kwargs["env"],
            "CURL_CA_BUNDLE": str(certificate),
            "SSL_CERT_FILE": str(certificate),
        }
        completed = subprocess.run(
            portable_argv,
            cwd=kwargs["cwd"],
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            pass_fds=kwargs["pass_fds"],
            timeout=30,
        )
        if completed.returncode != 0:
            raise runner.AcquisitionError(
                f"subprocess_exit_{completed.returncode}_local_range_fixture"
            )
        return completed.stdout

    return invoke


def _local_range_source(
    *,
    url: str,
    payload: bytes,
    etag: str,
    last_modified: str,
    mode: str,
    chunk_bytes: int | None,
):
    return SimpleNamespace(
        source_id="local_range_fixture",
        url=url,
        media_type="application/octet-stream",
        expected_bytes=len(payload),
        expected_etag=etag,
        expected_last_modified=last_modified,
        expected_sha256=hashlib.sha256(payload).hexdigest(),
        transfer_mode=mode,
        fixed_chunk_bytes=chunk_bytes,
    )


def _patch_local_range_runtime(runner, monkeypatch, certificate: Path):
    curl = shutil.which("curl")
    assert curl is not None
    monkeypatch.setattr(runner, "CURL", curl)
    monkeypatch.setattr(runner, "validate_https_url", lambda url, _hosts: url)
    monkeypatch.setattr(
        runner,
        "run_monitored",
        _local_curl_monitored(runner, certificate),
    )
    monkeypatch.setattr(runner.time, "sleep", lambda _seconds: None)


def _range_test_envelope():
    return SimpleNamespace(
        lease=SimpleNamespace(
            max_wall_seconds=7200,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ),
        elapsed_seconds=lambda: 0.0,
        check=lambda *_args, **_kwargs: None,
        register_ephemeral_control=lambda *_args, **_kwargs: None,
        unregister_ephemeral_control=lambda *_args, **_kwargs: None,
    )


def test_curl_invocations_are_https_nonredirecting_ranged_and_conditional(
    runner, monkeypatch, tmp_path
) -> None:
    base = next(
        source
        for source in runner.DIRECT_SOURCES
        if source.source_id == "envo_v2026_06_26"
    )
    source = replace(base, expected_bytes=3, expected_etag='"fixture"')
    calls: list[list[str]] = []

    def fake_monitored(argv, **kwargs):
        calls.append(list(argv))
        header_fd = kwargs["pass_fds"][0]
        is_head = "--head" in argv
        if is_head:
            header = (
                b'HTTP/1.1 200 OK\r\nContent-Length: 3\r\nETag: "fixture"\r\n'
                b"Content-Type: text/plain\r\n\r\n"
            )
            code = 200
        else:
            header = (
                b"HTTP/1.1 206 Partial Content\r\nContent-Length: 3\r\n"
                b'ETag: "fixture"\r\nContent-Type: text/plain\r\n'
                b"Content-Range: bytes 0-2/3\r\n\r\n"
            )
            code = 206
            os.write(kwargs["pass_fds"][1], b"abc")
        os.write(header_fd, header)
        size = 0 if is_head else 3
        return (
            f"CUR0S_URL:{source.url}\nCUR0S_CODE:{code}\nCUR0S_SIZE:{size}\n"
            "CUR0S_REDIRECTS:0\nCUR0S_TYPE:text/plain\n"
        ).encode()

    monkeypatch.setattr(runner, "run_monitored", fake_monitored)
    envelope = SimpleNamespace(
        lease=SimpleNamespace(
            max_wall_seconds=7200,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ),
        elapsed_seconds=lambda: 0.0,
        check=lambda *_args, **_kwargs: None,
        register_ephemeral_control=lambda *_args, **_kwargs: None,
        unregister_ephemeral_control=lambda *_args, **_kwargs: None,
    )
    observed_head = runner.observe_direct_metadata(
        source,
        tmp_path,
        envelope,
        frozenset({"raw.githubusercontent.com"}),
        checkpoint="fixture",
    )
    data_fd = _fd_for(tmp_path, b"")
    try:
        observed_get = runner.download_direct_file(
            source,
            tmp_path,
            data_fd,
            envelope,
            frozenset({"raw.githubusercontent.com"}),
        )
    finally:
        os.close(data_fd)

    assert observed_head.downloaded_bytes == 0
    assert observed_get.downloaded_bytes == 3
    assert len(calls) == 2
    for argv in calls:
        assert argv[0] == runner.CURL
        assert argv[argv.index("--proto") + 1] == "=https"
        assert argv[argv.index("--max-redirs") + 1] == "0"
        assert "--location" not in argv
        assert "--continue-at" not in argv
    get_argv = calls[1]
    assert f"If-Match: {source.expected_etag}" in get_argv
    assert f"If-Range: {source.expected_etag}" in get_argv
    assert "Range: bytes=0-2" in get_argv
    assert get_argv[get_argv.index("--max-filesize") + 1] == "3"


def test_fixed_ranges_survive_long_stream_resets_and_retry_only_failed_chunk(
    runner,
    monkeypatch,
    tmp_path,
    local_tls_material,
) -> None:
    chunk_bytes = 64 * 1024
    payload = bytes(range(251)) * 800
    server, thread, state, etag, last_modified, certificate = (
        _start_adversarial_range_server(
            local_tls_material,
            payload,
            mode="reset_once",
            chunk_bytes=chunk_bytes,
        )
    )
    url = f"https://localhost:{server.server_port}/payload"
    _patch_local_range_runtime(runner, monkeypatch, certificate)
    envelope = _range_test_envelope()
    single_source = _local_range_source(
        url=url,
        payload=payload,
        etag=etag,
        last_modified=last_modified,
        mode="single_response_v1",
        chunk_bytes=None,
    )
    single_fd = _fd_for(tmp_path, b"")
    ranged_fd = -1
    try:
        with pytest.raises(runner.AcquisitionError, match="subprocess_exit_"):
            runner.download_direct_file(
                single_source,
                tmp_path,
                single_fd,
                envelope,
                frozenset({"localhost"}),
            )
        assert state.full_requests == runner.DIRECT_TRANSFER_MAX_ATTEMPTS

        ranged_source = _local_range_source(
            url=url,
            payload=payload,
            etag=etag,
            last_modified=last_modified,
            mode="fixed_range_chunks_v1",
            chunk_bytes=chunk_bytes,
        )
        ranged_fd = _fd_for(tmp_path, b"")
        result = runner.download_direct_file(
            ranged_source,
            tmp_path,
            ranged_fd,
            envelope,
            frozenset({"localhost"}),
        )
        digest, byte_count = runner.hash_fd(ranged_fd)
        evidence = runner.build_direct_transfer_evidence_after_hash(
            result,
            ranged_source,
            verified_digest=digest,
            verified_bytes=byte_count,
        )
        assert digest == "sha256:" + hashlib.sha256(payload).hexdigest()
        assert byte_count == len(payload)
        assert result.per_chunk_attempts == (1, 2, 1, 1)
        assert evidence["chunk_count"] == 4
        assert evidence["total_attempts"] == 5
        assert evidence["every_response_206"] is True
        expected_ranges = [
            (0, chunk_bytes - 1),
            (chunk_bytes, 2 * chunk_bytes - 1),
            (chunk_bytes, 2 * chunk_bytes - 1),
            (2 * chunk_bytes, 3 * chunk_bytes - 1),
            (3 * chunk_bytes, len(payload) - 1),
        ]
        assert state.ranges == expected_ranges
    finally:
        os.close(single_fd)
        if ranged_fd >= 0:
            os.close(ranged_fd)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize(
    ("server_mode", "message", "expected_partial_chunks"),
    [
        ("ignored", "status_not_206", 0),
        ("malformed", "content_range_mismatch", 0),
        ("race", "etag_mismatch", 1),
    ],
)
def test_fixed_ranges_reject_ignored_malformed_and_raced_responses(
    runner,
    monkeypatch,
    tmp_path,
    local_tls_material,
    server_mode: str,
    message: str,
    expected_partial_chunks: int,
) -> None:
    chunk_bytes = 32 * 1024
    payload = bytes(range(239)) * 400
    server, thread, state, etag, last_modified, certificate = (
        _start_adversarial_range_server(
            local_tls_material,
            payload,
            mode=server_mode,
            chunk_bytes=chunk_bytes,
        )
    )
    url = f"https://localhost:{server.server_port}/payload"
    source = _local_range_source(
        url=url,
        payload=payload,
        etag=etag,
        last_modified=last_modified,
        mode="fixed_range_chunks_v1",
        chunk_bytes=chunk_bytes,
    )
    _patch_local_range_runtime(runner, monkeypatch, certificate)
    data_fd = _fd_for(tmp_path, b"")
    try:
        with pytest.raises(runner.AcquisitionError, match=message):
            runner.download_direct_file(
                source,
                tmp_path,
                data_fd,
                _range_test_envelope(),
                frozenset({"localhost"}),
            )
        assert os.fstat(data_fd).st_size == expected_partial_chunks * chunk_bytes
        assert state.full_requests == 0
    finally:
        os.close(data_fd)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_fixed_range_rejects_multiple_http_responses_in_one_chunk(runner) -> None:
    payload = b"abc"
    source = _local_range_source(
        url="https://fixture.invalid/payload",
        payload=payload,
        etag='"range-fixture"',
        last_modified="Sun, 12 Jul 2026 10:00:00 GMT",
        mode="fixed_range_chunks_v1",
        chunk_bytes=3,
    )
    response = (
        b"HTTP/1.1 206 Partial Content\r\nContent-Length: 3\r\n"
        b'ETag: "range-fixture"\r\n'
        b"Last-Modified: Sun, 12 Jul 2026 10:00:00 GMT\r\n"
        b"Content-Type: application/octet-stream\r\n"
        b"Content-Range: bytes 0-2/3\r\n\r\n"
    )
    with pytest.raises(runner.AcquisitionError, match="multi_response_ambiguity"):
        runner.validate_failed_range_response_headers(
            response + response,
            source,
            start=0,
            end=2,
        )


def test_toolchain_artifact_attestation_is_path_type_hash_and_inode_bound(
    runner, tmp_path
) -> None:
    target = tmp_path / "tool"
    payload = b"exact-toolchain-fixture"
    target.write_bytes(payload)
    target.chmod(0o600)
    info = target.stat()

    def record(literal: Path, *, symlink_target: str | None = None):
        literal_info = literal.lstat()
        return {
            "literal_path": str(literal),
            "literal_entry_type": (
                "symbolic_link" if symlink_target is not None else "regular_file"
            ),
            "literal_mode": f"{stat.S_IMODE(literal_info.st_mode):04o}",
            "literal_uid": literal_info.st_uid,
            "literal_gid": literal_info.st_gid,
            "literal_nlink": literal_info.st_nlink,
            "literal_symlink_target": symlink_target,
            "resolved_path": str(target),
            "resolved_entry_type": "regular_file",
            "resolved_mode": "0600",
            "resolved_uid": info.st_uid,
            "resolved_gid": info.st_gid,
            "resolved_nlink": info.st_nlink,
            "bytes": len(payload),
            "sha256": _sha(payload),
            "elf_identity": None,
        }

    regular_record = record(target)
    assert runner.attest_toolchain_artifact("fixture", regular_record)

    link = tmp_path / "tool-link"
    link.symlink_to(target.name)
    assert runner.attest_toolchain_artifact(
        "fixture-link", record(link, symlink_target=target.name)
    )

    target.write_bytes(b"X" * len(payload))
    with pytest.raises(runner.AcquisitionError, match="toolchain_hash_mismatch"):
        runner.attest_toolchain_artifact("fixture", regular_record)


def test_toolchain_probe_binds_returncode_stream_lengths_and_hashes(
    runner, monkeypatch
) -> None:
    literal = Path("/usr/bin/printf")
    resolved = literal.resolve(strict=True)
    literal_info = literal.lstat()
    resolved_info = resolved.stat()
    payload = resolved.read_bytes()
    symlink_target = os.readlink(literal) if literal.is_symlink() else None
    artifact = {
        "literal_path": str(literal),
        "literal_entry_type": "symbolic_link" if symlink_target else "regular_file",
        "literal_mode": f"{stat.S_IMODE(literal_info.st_mode):04o}",
        "literal_uid": literal_info.st_uid,
        "literal_gid": literal_info.st_gid,
        "literal_nlink": literal_info.st_nlink,
        "literal_symlink_target": symlink_target,
        "resolved_path": str(resolved),
        "resolved_entry_type": "regular_file",
        "resolved_mode": f"{stat.S_IMODE(resolved_info.st_mode):04o}",
        "resolved_uid": resolved_info.st_uid,
        "resolved_gid": resolved_info.st_gid,
        "resolved_nlink": resolved_info.st_nlink,
        "bytes": len(payload),
        "sha256": _sha(payload),
        "elf_identity": None,
    }
    artifacts = {"fixture": artifact}
    volatile = {"fixture": runner.attest_toolchain_artifact("fixture", artifact)}
    stdout = b"probe-ok"
    empty = _sha(b"")
    probe = {
        "argv": ["/usr/bin/printf", "probe-ok"],
        "environment": "base",
        "returncode": 0,
        "stdout_bytes": len(stdout),
        "stdout_sha256": _sha(stdout),
        "stderr_bytes": 0,
        "stderr_sha256": empty,
    }

    def fake_run(argv, **kwargs):
        assert argv == probe["argv"]
        assert kwargs["executable"].startswith(str(runner.FD_PATH_ROOT) + "/")
        assert len(kwargs["pass_fds"]) == 1
        return SimpleNamespace(returncode=0, stdout=stdout, stderr=b"")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    runner.run_toolchain_probe(
        "fixture", probe, {"base": {"LC_ALL": "C"}}, artifacts, volatile
    )
    probe["stdout_sha256"] = SHA256
    with pytest.raises(runner.AcquisitionError, match="probe_identity_mismatch"):
        runner.run_toolchain_probe(
            "fixture", probe, {"base": {"LC_ALL": "C"}}, artifacts, volatile
        )


def test_phone_toolchain_validation_attests_all_artifacts_before_use(
    runner, monkeypatch
) -> None:
    expected = runner.phone_toolchain_contract()
    calls: list[str] = []

    def attest(role, _artifact):
        calls.append(role)
        return (len(role),)

    monkeypatch.setattr(runner, "attest_toolchain_artifact", attest)
    monkeypatch.setattr(runner, "attest_python_stdlib_tree", lambda _value: (1,))
    monkeypatch.setattr(runner, "run_toolchain_probe", lambda *_args: None)
    process_identity = {
        "executable_mapping_count": 2,
        "isolated_startup_verified": True,
    }
    process_calls: list[int] = []

    def attest_process(*_args):
        process_calls.append(1)
        return process_identity

    monkeypatch.setattr(runner, "attest_current_python_process", attest_process)
    result = runner.validate_phone_toolchain(expected)

    assert result["artifact_count"] == len(expected["artifacts"])
    assert result["command_probe_count"] == len(expected["command_probes"])
    assert sorted(set(calls)) == sorted(expected["artifacts"])
    assert len(process_calls) == 2
    runner.revalidate_attested_toolchain_roles(frozenset({"curl"}))


def test_device_properties_require_prevalidated_getprop_toolchain(runner) -> None:
    with pytest.raises(
        runner.AcquisitionError,
        match="toolchain_must_precede_device_property_use",
    ):
        runner.validate_phone_runtime({}, {}, prevalidated_toolchain=None)
    roles = runner.command_toolchain_roles(runner.GETPROP)
    assert {
        "android_getprop",
        "system_libbase",
        "system_libcxx",
        "system_liblog",
    }.issubset(roles)


def test_main_attests_toolchain_before_git_prereg_and_device_properties(
    runner, monkeypatch, tmp_path
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    prereg, prereg_bytes = _install_main_transaction_mocks(runner, monkeypatch, output)
    events: list[str] = []
    monkeypatch.setattr(
        runner,
        "validate_native_preflight_execution_binding",
        lambda *_args: events.append("native_preflight") or {},
    )
    monkeypatch.setattr(
        runner,
        "validate_phone_toolchain",
        lambda _value: events.append("toolchain") or {},
    )
    monkeypatch.setattr(
        runner,
        "validate_preregistration",
        lambda _value: events.append("git_prereg") or {},
    )
    monkeypatch.setattr(
        runner,
        "guard_phone_environment",
        lambda: events.append("device_properties") or {},
    )

    def stop_after_order(*_args, **_kwargs):
        events.append("runtime_binding")
        raise RuntimeError("ordered_stop")

    monkeypatch.setattr(runner, "validate_phone_runtime", stop_after_order)
    with pytest.raises(RuntimeError, match="ordered_stop"):
        runner.main(
            args=Namespace(preregistration="unused", output_dir=str(output)),
            prereg_bytes=prereg_bytes,
            prereg=prereg,
        )
    assert events == [
        "native_preflight",
        "toolchain",
        "git_prereg",
        "device_properties",
        "runtime_binding",
    ]


def _maps_line(path: Path, *, inode: int | None = None) -> bytes:
    info = path.stat()
    device = f"{os.major(info.st_dev):x}:{os.minor(info.st_dev):x}"
    return (
        f"1000-2000 r-xp 00000000 {device} "
        f"{info.st_ino if inode is None else inode} {path}\n"
    ).encode()


def _vdso_maps_line() -> bytes:
    return b"7000-8000 r-xp 00000000 00:00 0 [vdso]\n"


def _synthetic_process_contract(runner, tmp_path: Path):
    python = tmp_path / "python"
    libpython = tmp_path / "libpython.so"
    python.write_bytes(b"exact-python")
    libpython.write_bytes(b"exact-libpython")
    artifacts = {
        "python": {
            "resolved_path": str(python),
            "sha256": _sha(python.read_bytes()),
            "bytes": python.stat().st_size,
            "elf_identity": None,
        },
        "libpython": {
            "resolved_path": str(libpython),
            "sha256": _sha(libpython.read_bytes()),
            "bytes": libpython.stat().st_size,
            "elf_identity": None,
        },
    }
    volatile = {
        role: runner.stat_identity(path.stat())
        for role, path in (("python", python), ("libpython", libpython))
    }
    runtime = {
        "proc_self_exe": str(python),
        "sanitized_sys_path": [str(tmp_path / "stdlib"), str(tmp_path / "dynload")],
        "executable_mapping_artifact_roles": ["libpython", "python"],
        "executable_mapping_stdlib_extension_paths": [],
        "executable_mapping_expected_paths": sorted(
            [str(python), str(libpython), "[vdso]"]
        ),
        "executable_mapping_expected_count": 3,
    }
    return python, libpython, artifacts, volatile, runtime


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing_libpython", "required_python_executable_mapping_missing"),
        ("wrong_libpython_inode", "executable_mapping_inode_mismatch"),
        ("alternate_libpython", "unapproved_executable_mapping"),
        ("deleted", "unapproved_executable_mapping"),
        ("evil_preload", "unapproved_executable_mapping"),
        ("extra_manifest_artifact", "unapproved_executable_mapping"),
        ("extra_stdlib_extension", "unapproved_executable_mapping"),
    ],
)
def test_current_process_maps_reject_missing_alternate_deleted_and_injected_code(
    runner, monkeypatch, tmp_path, mutation: str, message: str
) -> None:
    python, libpython, artifacts, volatile, runtime = _synthetic_process_contract(
        runner, tmp_path
    )
    original_open = os.open
    monkeypatch.setattr(
        runner, "validate_sanitized_python_runtime", lambda _value: None
    )
    monkeypatch.setattr(
        runner,
        "runner_pycache_prefix_from_orig_argv",
        lambda _argv: tmp_path / "absent-pycache",
    )
    monkeypatch.setattr(
        runner, "loaded_python_module_origin_records", lambda _prefix: []
    )
    monkeypatch.setattr(runner.os, "readlink", lambda _path: str(python))
    monkeypatch.setattr(
        runner.os,
        "open",
        lambda path, flags, *args, **kwargs: (
            original_open(python, flags)
            if path == "/proc/self/exe"
            else original_open(path, flags, *args, **kwargs)
        ),
    )
    lines = [_maps_line(python), _maps_line(libpython), _vdso_maps_line()]
    if mutation == "missing_libpython":
        lines = [lines[0], lines[2]]
    elif mutation == "wrong_libpython_inode":
        lines[1] = _maps_line(libpython, inode=libpython.stat().st_ino + 1)
    elif mutation == "alternate_libpython":
        alternate = tmp_path / "alternate-libpython.so"
        alternate.write_bytes(b"alternate")
        lines[1] = _maps_line(alternate)
    elif mutation == "deleted":
        lines[1] = lines[1].rstrip(b"\n") + b" (deleted)\n"
    elif mutation == "evil_preload":
        evil = tmp_path / "evil.so"
        evil.write_bytes(b"evil")
        lines.append(_maps_line(evil))
    elif mutation == "extra_manifest_artifact":
        ambient = tmp_path / "manifest-listed-but-not-runtime-admitted.so"
        ambient.write_bytes(b"ambient")
        artifacts["ambient_manifest_artifact"] = {
            "resolved_path": str(ambient),
            "sha256": _sha(ambient.read_bytes()),
            "bytes": ambient.stat().st_size,
            "elf_identity": None,
        }
        volatile["ambient_manifest_artifact"] = runner.stat_identity(ambient.stat())
        lines.append(_maps_line(ambient))
    elif mutation == "extra_stdlib_extension":
        lines.append(
            b"9000-a000 r-xp 00000000 00:01 12345 "
            b"/data/data/com.termux/files/usr/lib/python3.13/lib-dynload/"
            b"_ambient.cpython-313.so\n"
        )
    monkeypatch.setattr(runner, "read_proc_self_maps", lambda: b"".join(lines))

    with pytest.raises(runner.AcquisitionError, match=message):
        runner.attest_current_python_process(runtime, artifacts, volatile)


def test_current_process_rejects_same_hash_executable_on_different_inode(
    runner, monkeypatch, tmp_path
) -> None:
    python, libpython, artifacts, volatile, runtime = _synthetic_process_contract(
        runner, tmp_path
    )
    clone = tmp_path / "python-clone"
    clone.write_bytes(python.read_bytes())
    original_open = os.open
    monkeypatch.setattr(
        runner, "validate_sanitized_python_runtime", lambda _value: None
    )
    monkeypatch.setattr(
        runner,
        "runner_pycache_prefix_from_orig_argv",
        lambda _argv: tmp_path / "absent-pycache",
    )
    monkeypatch.setattr(
        runner, "loaded_python_module_origin_records", lambda _prefix: []
    )
    monkeypatch.setattr(runner.os, "readlink", lambda _path: str(python))
    monkeypatch.setattr(
        runner.os,
        "open",
        lambda path, flags, *args, **kwargs: (
            original_open(clone, flags)
            if path == "/proc/self/exe"
            else original_open(path, flags, *args, **kwargs)
        ),
    )
    monkeypatch.setattr(
        runner,
        "read_proc_self_maps",
        lambda: _maps_line(python) + _maps_line(libpython) + _vdso_maps_line(),
    )
    with pytest.raises(runner.AcquisitionError, match="proc_exe_identity_mismatch"):
        runner.attest_current_python_process(runtime, artifacts, volatile)


def test_python_owned_range_retry_truncates_only_ephemeral_chunk_and_headers(
    runner, monkeypatch, tmp_path
) -> None:
    base = next(
        source
        for source in runner.DIRECT_SOURCES
        if source.source_id == "envo_v2026_06_26"
    )
    source = replace(base, expected_bytes=3, expected_etag='"fixture"')
    header = (
        b"HTTP/1.1 206 Partial Content\r\nContent-Length: 3\r\n"
        b'ETag: "fixture"\r\nContent-Type: text/plain\r\n'
        b"Content-Range: bytes 0-2/3\r\n\r\n"
    )
    attempts = 0

    def fake_monitored(_argv, **kwargs):
        nonlocal attempts
        attempts += 1
        os.write(kwargs["pass_fds"][0], header)
        if attempts == 1:
            os.write(kwargs["pass_fds"][1], b"bad-prefix")
            raise runner.AcquisitionError("subprocess_exit_18_fixture")
        os.write(kwargs["pass_fds"][1], b"abc")
        return (
            f"CUR0S_URL:{source.url}\nCUR0S_CODE:206\nCUR0S_SIZE:3\n"
            "CUR0S_REDIRECTS:0\nCUR0S_TYPE:text/plain\n"
        ).encode()

    monkeypatch.setattr(runner, "run_monitored", fake_monitored)
    monkeypatch.setattr(runner.time, "sleep", lambda _seconds: None)
    envelope = SimpleNamespace(
        lease=SimpleNamespace(
            max_wall_seconds=7200,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ),
        elapsed_seconds=lambda: 0.0,
        check=lambda *_args, **_kwargs: None,
        register_ephemeral_control=lambda *_args, **_kwargs: None,
        unregister_ephemeral_control=lambda *_args, **_kwargs: None,
    )
    data_fd = _fd_for(tmp_path, b"")
    try:
        observed = runner.download_direct_file(
            source,
            tmp_path,
            data_fd,
            envelope,
            frozenset({"raw.githubusercontent.com"}),
        )
        os.lseek(data_fd, 0, os.SEEK_SET)
        assert os.read(data_fd, 32) == b"abc"
    finally:
        os.close(data_fd)
    assert attempts == 2
    assert observed.response_attempt_count == 2
    assert observed.per_chunk_attempts == (2,)


def _observation(runner, source, **overrides: Any):
    values = {
        "url": source.url,
        "status_code": 200,
        "content_length": source.expected_bytes,
        "etag": source.expected_etag,
        "last_modified": source.expected_last_modified,
        "content_type": source.media_type,
        "content_encoding": None,
        "content_range": None,
        "redirect_count": 0,
        "downloaded_bytes": source.expected_bytes,
        "response_attempt_count": 1,
    }
    values.update(overrides)
    return runner.HttpObservation(**values)


def _download_result(runner, source, observation=None, *, attempts=(1,)):
    observation = observation or _observation(runner, source)
    mode, fixed_chunk_bytes = runner.validate_direct_transfer_policy(source)
    ranged = mode == "fixed_range_chunks_v1"
    return runner.DirectDownloadResult(
        observation=replace(
            observation,
            response_attempt_count=sum(attempts),
        ),
        transfer_mode=mode,
        fixed_chunk_bytes=fixed_chunk_bytes,
        per_chunk_attempts=attempts,
        every_response_206=ranged,
        every_content_range_exact=ranged,
        no_overlap=True,
        no_gap=True,
        held_destination_single_inode=True,
    )


def test_direct_transfer_result_cannot_mint_pre_hash_sha_claim(runner) -> None:
    source = runner.DIRECT_SOURCES[0]
    _mode, fixed_chunk_bytes = runner.validate_direct_transfer_policy(source)
    chunk_count = (
        (source.expected_bytes + fixed_chunk_bytes - 1) // fixed_chunk_bytes
        if fixed_chunk_bytes is not None
        else 1
    )
    result = _download_result(
        runner,
        source,
        attempts=(1,) * chunk_count,
    )
    assert not hasattr(result, "receipt_evidence")
    with pytest.raises(runner.AcquisitionError, match="post_hash_proof_invalid"):
        runner.build_direct_transfer_evidence_after_hash(
            result,
            source,
            verified_digest="sha256:" + "0" * 64,
            verified_bytes=source.expected_bytes,
        )
    evidence = runner.build_direct_transfer_evidence_after_hash(
        result,
        source,
        verified_digest="sha256:" + source.expected_sha256,
        verified_bytes=source.expected_bytes,
    )
    assert evidence["full_length_and_sha256_verified"] is True


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"url": "https://wordnetcode.princeton.edu/other"}, "final_url"),
        ({"status_code": 206}, "status_or_redirect"),
        ({"redirect_count": 1}, "status_or_redirect"),
        ({"content_length": 1}, "content_length"),
        ({"etag": '"changed"'}, "etag"),
        ({"last_modified": "changed"}, "last_modified"),
        ({"content_type": "application/octet-stream"}, "content_type"),
        ({"content_encoding": "gzip"}, "content_encoding"),
        ({"content_range": "bytes 0-1/2"}, "partial_content"),
        ({"downloaded_bytes": 1}, "downloaded_bytes"),
    ],
)
def test_direct_metadata_final_url_and_size_are_exact(
    runner, overrides: dict[str, Any], message: str
) -> None:
    source = runner.DIRECT_SOURCES[0]
    observation = _observation(runner, source, **overrides)
    with pytest.raises(runner.AcquisitionError, match=message):
        runner.validate_http_observation(
            observation,
            source,
            expected_downloaded_bytes=source.expected_bytes,
        )


def test_http_stable_identity_normalizes_absent_identity_encoding_and_ignores_type(
    runner,
) -> None:
    source = runner.DIRECT_SOURCES[0]
    absent = _observation(
        runner,
        source,
        content_type=None,
        content_encoding=None,
    )
    present = _observation(
        runner,
        source,
        content_type=source.media_type + "; charset=binary",
        content_encoding="Identity",
    )
    runner.validate_http_observation(
        absent, source, expected_downloaded_bytes=source.expected_bytes
    )
    runner.validate_http_observation(
        present, source, expected_downloaded_bytes=source.expected_bytes
    )
    assert absent.stable_identity() == present.stable_identity()


@pytest.mark.parametrize(
    ("phase", "message"),
    [
        ("success", ""),
        ("pre_get", "direct_content_type_mismatch"),
        ("pre_post", "direct_content_type_mismatch"),
    ],
)
def test_direct_acquisition_binds_pre_get_post_and_publishes_atomically(
    runner, monkeypatch, tmp_path, phase: str, message: str
) -> None:
    base = next(
        source for source in runner.DIRECT_SOURCES if source.media_type == "text/obo"
    )
    payload = _obo_bytes(base.required_markers)
    source = replace(
        base,
        expected_bytes=len(payload),
        expected_sha256=hashlib.sha256(payload).hexdigest(),
        filename="fixture.obo",
    )
    direct_root = tmp_path / "direct"
    direct_root.mkdir()
    observations = [
        _observation(runner, source, downloaded_bytes=0),
        _observation(
            runner,
            source,
            downloaded_bytes=0,
            content_type=(
                "application/changed" if phase == "pre_post" else source.media_type
            ),
        ),
    ]

    def observe(*_args, **_kwargs):
        return observations.pop(0)

    def download(_source, _cwd, data_fd, _envelope, _allowed_hosts):
        os.write(data_fd, payload)
        return _download_result(
            runner,
            source,
            _observation(
                runner,
                source,
                content_type=(
                    "application/changed" if phase == "pre_get" else source.media_type
                ),
            ),
        )

    monkeypatch.setattr(runner, "observe_direct_metadata", observe)
    monkeypatch.setattr(runner, "download_direct_file", download)
    source_dir = direct_root / source.source_id
    try:
        if phase == "success":
            artifact, inspection = runner.acquire_direct_source(
                source,
                direct_root,
                SimpleNamespace(),
                _Checks(),
                frozenset({"release.geneontology.org"}),
            )
            final = source_dir / source.filename
            assert final.read_bytes() == payload
            assert stat.S_IMODE(final.stat().st_mode) == 0o400
            assert not (source_dir / ".download.partial").exists()
            assert {entry.name for entry in source_dir.iterdir()} == {source.filename}
            assert stat.S_IMODE(source_dir.stat().st_mode) == 0o500
            assert artifact["verification"]["pre_post_metadata_match"] is True
            assert inspection["structure_checks"]["OBO_term_stanzas"] == 100
        else:
            with pytest.raises(runner.AcquisitionError, match=message):
                runner.acquire_direct_source(
                    source,
                    direct_root,
                    SimpleNamespace(),
                    _Checks(),
                    frozenset({"release.geneontology.org"}),
                )
            assert not (source_dir / source.filename).exists()
    finally:
        if source_dir.exists():
            source_dir.chmod(0o700)
            for child in source_dir.iterdir():
                if child.is_file():
                    child.chmod(0o600)


def test_direct_acquisition_rejects_same_size_rewrite_before_inspection(
    runner, monkeypatch, tmp_path
) -> None:
    base = next(
        source for source in runner.DIRECT_SOURCES if source.media_type == "text/obo"
    )
    original_payload = _obo_bytes(base.required_markers)
    rewritten_payload = original_payload.replace(b"name: term 0", b"name: germ 0", 1)
    assert len(rewritten_payload) == len(original_payload)
    source = replace(
        base,
        filename="rewrite.obo",
        expected_bytes=len(original_payload),
        expected_sha256=hashlib.sha256(original_payload).hexdigest(),
    )
    direct_root = tmp_path / "direct"
    direct_root.mkdir()
    observations = [
        _observation(runner, source, downloaded_bytes=0),
        _observation(runner, source, downloaded_bytes=0),
    ]
    monkeypatch.setattr(
        runner,
        "observe_direct_metadata",
        lambda *_args, **_kwargs: observations.pop(0),
    )

    def download(_source, _cwd, data_fd, _envelope, _allowed_hosts):
        os.write(data_fd, original_payload)
        return _download_result(runner, source)

    real_inspection = runner.inspect_direct_source

    def rewrite_then_inspect(_source, data_fd, envelope):
        os.lseek(data_fd, 0, os.SEEK_SET)
        os.write(data_fd, rewritten_payload)
        os.fsync(data_fd)
        return real_inspection(_source, data_fd, envelope)

    monkeypatch.setattr(runner, "download_direct_file", download)
    monkeypatch.setattr(runner, "inspect_direct_source", rewrite_then_inspect)
    source_dir = direct_root / source.source_id
    try:
        with pytest.raises(
            runner.AcquisitionError,
            match="changed_during_inspection|direct_sha256_mismatch",
        ):
            runner.acquire_direct_source(
                source,
                direct_root,
                SimpleNamespace(),
                _Checks(),
                frozenset({"release.geneontology.org"}),
            )
    finally:
        if source_dir.exists():
            source_dir.chmod(0o700)
            for child in source_dir.iterdir():
                if child.is_file():
                    child.chmod(0o600)


def test_direct_hash_mismatch_never_reaches_archive_or_xml_inspector(
    runner, monkeypatch, tmp_path
) -> None:
    base = next(
        source for source in runner.DIRECT_SOURCES if source.media_type == "text/obo"
    )
    admitted = _obo_bytes(base.required_markers)
    wrong = admitted.replace(b"name: term 0", b"name: germ 0", 1)
    source = replace(
        base,
        filename="wrong.obo",
        expected_bytes=len(admitted),
        expected_sha256=hashlib.sha256(admitted).hexdigest(),
    )
    direct_root = tmp_path / "direct"
    direct_root.mkdir()
    observations = [
        _observation(runner, source, downloaded_bytes=0),
        _observation(runner, source, downloaded_bytes=0),
    ]
    monkeypatch.setattr(
        runner,
        "observe_direct_metadata",
        lambda *_args, **_kwargs: observations.pop(0),
    )

    def download(_source, _cwd, data_fd, _envelope, _allowed_hosts):
        os.write(data_fd, wrong)
        return _download_result(runner, source)

    monkeypatch.setattr(runner, "download_direct_file", download)
    monkeypatch.setattr(
        runner,
        "inspect_direct_source",
        lambda *_args, **_kwargs: pytest.fail("inspector_called_before_hash_admission"),
    )
    source_dir = direct_root / source.source_id
    try:
        with pytest.raises(runner.AcquisitionError, match="preinspection_sha256"):
            runner.acquire_direct_source(
                source,
                direct_root,
                SimpleNamespace(),
                _Checks(),
                frozenset({"release.geneontology.org"}),
            )
    finally:
        if source_dir.exists():
            source_dir.chmod(0o700)
            for child in source_dir.iterdir():
                if child.is_file():
                    child.chmod(0o600)


@pytest.mark.parametrize("mutate_before_final_readback", [False, True])
def test_final_fd_root_source_reattestation_rejects_prior_artifact_mutation(
    runner, monkeypatch, tmp_path, mutate_before_final_readback: bool
) -> None:
    payload = b"authority-payload"
    source = replace(
        runner.DIRECT_SOURCES[0],
        source_id="fixture_direct",
        filename="fixture.bin",
        expected_bytes=len(payload),
        expected_sha256=hashlib.sha256(payload).hexdigest(),
    )
    monkeypatch.setattr(runner, "DIRECT_SOURCES", (source,))
    monkeypatch.setattr(runner, "GIT_SOURCES", ())

    candidate_path = tmp_path / "candidate"
    source_path = candidate_path / "sources/direct" / source.source_id
    git_root = candidate_path / "sources/git"
    source_path.mkdir(parents=True, mode=0o700)
    git_root.mkdir(parents=True, mode=0o700)
    for path in (
        candidate_path,
        candidate_path / "sources",
        candidate_path / "sources/direct",
        git_root,
    ):
        path.chmod(0o700)
    final_file = source_path / source.filename
    final_file.write_bytes(payload)
    final_file.chmod(0o400)
    source_path.chmod(0o500)
    digest = _sha(payload)
    locator = f"sources/direct/{source.source_id}/{source.filename}"
    manifest = {
        "schema_version": "cur0s_direct_content_manifest_v1",
        "files": [{"relative_path": locator, "bytes": len(payload), "sha256": digest}],
    }
    artifact = {
        "source_id": source.source_id,
        "acquisition_mode": source.acquisition_mode,
        "bytes": len(payload),
        "sha256": digest,
        "local_locator": locator,
        "content_manifest": manifest,
        "verification": {"content_manifest_sha256": runner.canonical_sha256(manifest)},
    }
    if mutate_before_final_readback:
        final_file.chmod(0o600)
        final_file.write_bytes(b"X" * len(payload))
        final_file.chmod(0o400)
    directory_fd = os.open(candidate_path, os.O_RDONLY | os.O_DIRECTORY)
    candidate = SimpleNamespace(
        directory_fd=directory_fd,
        revalidate_path_binding=lambda: None,
    )
    try:
        if mutate_before_final_readback:
            with pytest.raises(runner.AcquisitionError, match="final_direct_manifest"):
                runner.reattest_candidate_source_tree(candidate, [artifact], _Checks())
        else:
            result = runner.reattest_candidate_source_tree(
                candidate, [artifact], _Checks()
            )
            assert result["artifact_count"] == 1
            assert result["fd_root_O_NOFOLLOW_readback"] is True
            assert stat.S_IMODE((candidate_path / "sources").stat().st_mode) == 0o500
    finally:
        os.close(directory_fd)


@pytest.mark.parametrize("injection", ["none", "extra_file", "git_metadata"])
def test_final_fd_root_git_reattestation_rederives_exact_manifest(
    runner, monkeypatch, tmp_path, injection: str
) -> None:
    files = {
        "LICENSE": b"license",
        "modules/m1/index.cnxml": b"module",
    }
    selected_bytes = sum(len(payload) for payload in files.values())
    source = replace(
        runner.GIT_SOURCES[0],
        source_id="fixture_git",
        selected_file_count=len(files),
        selected_bytes=selected_bytes,
        selected_paths=("LICENSE", "modules"),
    )
    monkeypatch.setattr(runner, "DIRECT_SOURCES", ())
    monkeypatch.setattr(runner, "GIT_SOURCES", (source,))

    candidate_path = tmp_path / "candidate"
    direct_root = candidate_path / "sources/direct"
    checkout = candidate_path / "sources/git" / source.source_id / "checkout"
    checkout.mkdir(parents=True, mode=0o700)
    direct_root.mkdir(parents=True, mode=0o700)
    for relative, payload in files.items():
        path = checkout / relative
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_bytes(payload)
    if injection == "extra_file":
        (checkout / "extra.txt").write_bytes(b"extra")
    elif injection == "git_metadata":
        (checkout / ".git").mkdir(mode=0o700)
        (checkout / ".git/rogue-C4-RX-payload").write_bytes(b"rogue")
    for root_text, directory_names, file_names in os.walk(checkout):
        root = Path(root_text)
        for name in file_names:
            (root / name).chmod(0o400)
        for name in directory_names:
            (root / name).chmod(0o500)
        root.chmod(0o500)
    source_dir = checkout.parent
    source_dir.chmod(0o500)
    for path in (
        candidate_path,
        candidate_path / "sources",
        direct_root,
        candidate_path / "sources/git",
    ):
        path.chmod(0o700)
    manifest_files = [
        {
            "relative_path": relative,
            "bytes": len(payload),
            "sha256": _sha(payload),
        }
        for relative, payload in sorted(files.items())
    ]
    manifest = {
        "schema_version": "cur0s_git_sparse_content_manifest_v1",
        "commit_sha": source.commit_sha,
        "tree_sha": source.tree_sha,
        "files": manifest_files,
    }
    manifest_sha = runner.canonical_sha256(manifest)
    artifact = {
        "source_id": source.source_id,
        "acquisition_mode": source.acquisition_mode,
        "bytes": selected_bytes,
        "sha256": manifest_sha,
        "local_locator": f"sources/git/{source.source_id}/checkout",
        "content_manifest": manifest,
        "verification": {"content_manifest_sha256": manifest_sha},
    }
    directory_fd = os.open(candidate_path, os.O_RDONLY | os.O_DIRECTORY)
    candidate = SimpleNamespace(
        directory_fd=directory_fd,
        revalidate_path_binding=lambda: None,
    )
    try:
        if injection != "none":
            message = (
                "final_git_metadata"
                if injection == "git_metadata"
                else "final_git_manifest"
            )
            with pytest.raises(runner.AcquisitionError, match=message):
                runner.reattest_candidate_source_tree(candidate, [artifact], _Checks())
        else:
            result = runner.reattest_candidate_source_tree(
                candidate, [artifact], _Checks()
            )
            assert result["artifact_count"] == 1
            assert result["artifacts"][0]["sha256"] == manifest_sha
    finally:
        os.close(directory_fd)


def test_http_parser_rejects_redirect_duplicate_metadata_and_size_lies(runner) -> None:
    output = (
        b"CUR0S_URL:https://wordnetcode.princeton.edu/3.0/WordNet-3.0.tar.gz\n"
        b"CUR0S_CODE:200\nCUR0S_SIZE:0\nCUR0S_REDIRECTS:0\n"
        b"CUR0S_TYPE:application/x-gzip\n"
    )
    good = (
        b"HTTP/1.1 200 OK\r\nContent-Length: 11537239\r\n"
        b'ETag: "b00b57-4384e6ed68640"\r\n\r\n'
    )
    assert (
        runner.parse_http_observation(output, good, downloaded_bytes=0).status_code
        == 200
    )

    redirect = b"HTTP/1.1 302 Found\r\nLocation: https://evil.example/x\r\n\r\n" + good
    with pytest.raises(runner.AcquisitionError, match="redirect_or_nonretryable"):
        runner.parse_http_observation(output, redirect, downloaded_bytes=0)

    duplicate = good.replace(b"\r\n\r\n", b'\r\nETag: "duplicate"\r\n\r\n')
    with pytest.raises(runner.AcquisitionError, match="etag_header_invalid"):
        runner.parse_http_observation(output, duplicate, downloaded_bytes=0)

    with pytest.raises(runner.AcquisitionError, match="reported_download_size"):
        runner.parse_http_observation(
            output.replace(b"CUR0S_SIZE:0", b"CUR0S_SIZE:1"),
            good,
            downloaded_bytes=0,
        )


def test_marker_tracker_handles_chunk_boundaries_and_missing_marker(runner) -> None:
    tracker = runner.MarkerTracker(("commercial-rights-marker",))
    tracker.feed(b"commercial-rights-")
    tracker.feed(b"marker")
    tracker.require_all("fixture")

    missing = runner.MarkerTracker(("required",))
    missing.feed(b"not present")
    with pytest.raises(runner.AcquisitionError, match="license_marker_missing"):
        missing.require_all("fixture")


def test_wordnet_tar_requires_license_dictionary_and_safe_members(
    runner, tmp_path
) -> None:
    base = runner.DIRECT_SOURCES[0]
    payload = _wordnet_tar(base.required_markers[0])
    source = replace(base, expected_bytes=len(payload))
    fd = _fd_for(tmp_path, payload)
    try:
        result = runner.inspect_safe_tar(source, fd, _Checks())
    finally:
        os.close(fd)
    assert result["structure_checks"]["bundled_license_present"] is True
    assert (
        result["structure_checks"]["required_dictionary_and_index_members_present"]
        is True
    )

    unsafe = _tar_bytes(
        [
            ("../escape", b"x", "file"),
            ("LICENSE", base.required_markers[0].encode(), "file"),
        ]
    )
    fd = _fd_for(tmp_path, unsafe)
    try:
        with pytest.raises(runner.AcquisitionError, match="traversal"):
            runner.inspect_safe_tar(
                replace(base, expected_bytes=len(unsafe)), fd, _Checks()
            )
    finally:
        os.close(fd)

    linked = _tar_bytes([("LICENSE", b"", "symlink")])
    fd = _fd_for(tmp_path, linked)
    try:
        with pytest.raises(runner.AcquisitionError, match="nonregular"):
            runner.inspect_safe_tar(
                replace(base, expected_bytes=len(linked)), fd, _Checks()
            )
    finally:
        os.close(fd)


def test_nalt_zip_routes_only_exact_authoritative_counts(
    runner, monkeypatch, tmp_path
) -> None:
    base = next(
        source
        for source in runner.DIRECT_SOURCES
        if source.source_id == "usda_nalt_core_2024"
    )
    turtle = (
        b"https://creativecommons.org/licenses/by/4.0 nalt-core\n"
        b'<urn:test> a skos:Concept ; skos:prefLabel "one"@en .\n'
    )
    payload = _zip_bytes(
        [("nalt-core.ttl", turtle, zipfile.ZIP_DEFLATED, stat.S_IFREG | 0o644)]
    )
    source = replace(base, expected_bytes=len(payload))
    expected = {
        "concepts": 14_196,
        "english_pref_labels": 14_196,
        "alt_labels": 19_075,
        "hidden_labels": 0,
    }
    monkeypatch.setattr(runner, "count_nalt_turtle_constructs", lambda _text: expected)
    fd = _fd_for(tmp_path, payload)
    try:
        result = runner.inspect_safe_zip(source, fd, _Checks(), epub=False)
    finally:
        os.close(fd)
    assert result["structure_checks"]["authoritative_counts"] == expected

    monkeypatch.setattr(
        runner,
        "count_nalt_turtle_constructs",
        lambda _text: {**expected, "concepts": 14_195},
    )
    with pytest.raises(runner.AcquisitionError, match="authoritative_count"):
        runner.validate_nalt_core_turtle(turtle)


def test_nalt_counter_is_prefix_bound_unique_and_exactly_english(runner) -> None:
    turtle = """@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
<urn:c1> a skos:Concept ;
  skos:prefLabel "one"@en, "one"@en ;
  skos:altLabel "alternate"@en, "francais"@fr, "not english"@eng ;
  skos:hiddenLabel "hidden"@en, "hidden"@en .
"""
    assert runner.count_nalt_turtle_constructs(turtle) == {
        "concepts": 1,
        "english_pref_labels": 1,
        "alt_labels": 1,
        "hidden_labels": 1,
    }

    two_preferred = turtle.replace('"one"@en, "one"@en', '"one"@en, "different"@en')
    with pytest.raises(runner.AcquisitionError, match="exactly_one_english"):
        runner.count_nalt_turtle_constructs(two_preferred)

    rebound = turtle.replace(
        "http://www.w3.org/2004/02/skos/core#", "https://evil.example/skos#"
    )
    with pytest.raises(runner.AcquisitionError, match="prefix_binding"):
        runner.count_nalt_turtle_constructs(rebound)

    dangling = turtle + '<urn:missing> skos:altLabel "dangling"@en .\n'
    with pytest.raises(runner.AcquisitionError, match="not_concept"):
        runner.count_nalt_turtle_constructs(dangling)


def test_nalt_archive_requires_exactly_one_turtle_member(runner, tmp_path) -> None:
    base = next(
        source
        for source in runner.DIRECT_SOURCES
        if source.source_id == "usda_nalt_core_2024"
    )
    marker = b"https://creativecommons.org/licenses/by/4.0 nalt-core\n"
    payload = _zip_bytes(
        [
            ("first.ttl", marker, zipfile.ZIP_DEFLATED, stat.S_IFREG | 0o644),
            ("second.ttl", marker, zipfile.ZIP_DEFLATED, stat.S_IFREG | 0o644),
        ]
    )
    fd = _fd_for(tmp_path, payload)
    try:
        with pytest.raises(runner.AcquisitionError, match="multiple_turtle"):
            runner.inspect_safe_zip(
                replace(base, expected_bytes=len(payload)), fd, _Checks(), epub=False
            )
    finally:
        os.close(fd)


def test_zip_rejects_traversal_symlink_and_duplicate_members(runner, tmp_path) -> None:
    base = runner.DIRECT_SOURCES[1]
    cases = [
        (
            [("../escape.ttl", b"x", zipfile.ZIP_STORED, stat.S_IFREG | 0o644)],
            "traversal",
        ),
        (
            [("link.ttl", b"x", zipfile.ZIP_STORED, stat.S_IFLNK | 0o777)],
            "link_or_special",
        ),
        (
            [
                ("same.ttl", b"x", zipfile.ZIP_STORED, stat.S_IFREG | 0o644),
                ("same.ttl", b"y", zipfile.ZIP_STORED, stat.S_IFREG | 0o644),
            ],
            "duplicate",
        ),
    ]
    for entries, message in cases:
        if message == "duplicate":
            with pytest.warns(UserWarning, match="Duplicate name"):
                payload = _zip_bytes(entries)
        else:
            payload = _zip_bytes(entries)
        fd = _fd_for(tmp_path, payload)
        try:
            with pytest.raises(runner.AcquisitionError, match=message):
                runner.inspect_safe_zip(
                    replace(base, expected_bytes=len(payload), required_markers=()),
                    fd,
                    _Checks(),
                    epub=False,
                )
        finally:
            os.close(fd)


def test_epub_requires_first_stored_mimetype_and_distinct_subject_grade_evidence(
    runner, tmp_path
) -> None:
    base = next(
        source
        for source in runner.DIRECT_SOURCES
        if source.source_id == "siyavula_mathematics_grade_10_cc_by"
    )
    payload, members = _epub_bytes()
    source = _bind_epub_fixture_source(base, payload, members)
    fd = _fd_for(tmp_path, payload)
    try:
        result = runner.inspect_safe_zip(source, fd, _Checks(), epub=True)
    finally:
        os.close(fd)
    evidence = result["structure_checks"]["subject_grade_evidence"]
    assert evidence == {
        "catalogue": {
            "evidence_root_sha256": "sha256:"
            + source.epub_identity.catalogue_evidence_root_sha256,
            "grade": 10,
            "subject": "Mathematics",
        },
        "download_filename": {
            "filename": "Gr10_Mathematics_Learner_Eng_CC-BY.epub",
            "grade_token": "Gr10",
            "subject_token": "Mathematics",
        },
        "opf_observation": {
            "dc_subject_values": [],
            "grade_metadata_values": [],
            "grade_assertion_present": False,
            "subject_assertion_present": False,
        },
    }

    wrong, wrong_members = _epub_bytes(title="science11")
    wrong_source = _bind_epub_fixture_source(base, wrong, wrong_members)
    fd = _fd_for(tmp_path, wrong)
    try:
        with pytest.raises(runner.AcquisitionError, match="title_metadata_mismatch"):
            runner.inspect_safe_zip(wrong_source, fd, _Checks(), epub=True)
    finally:
        os.close(fd)

    with pytest.raises(runner.AcquisitionError, match="escapes_root"):
        runner.resolve_epub_member("content.opf", "../escape.xhtml")


def _rebuild_epub(members: dict[str, bytes]) -> bytes:
    ordered = list(members)
    return _zip_bytes(
        [
            (
                name,
                members[name],
                zipfile.ZIP_STORED if name == "mimetype" else zipfile.ZIP_DEFLATED,
                stat.S_IFREG | 0o644,
            )
            for name in ordered
        ]
    )


def _validate_epub_fixture(runner, base, members: dict[str, bytes]):
    payload = _rebuild_epub(members)
    source = _bind_epub_fixture_source(base, payload, members)
    return runner.validate_epub_identity(source, members, set(members))


def test_epub_receipt_separates_catalogue_filename_and_opf_observation(
    runner,
) -> None:
    base = next(
        source
        for source in runner.DIRECT_SOURCES
        if source.source_id == "siyavula_mathematics_grade_10_cc_by"
    )
    _payload, members = _epub_bytes()
    result = _validate_epub_fixture(runner, base, members)
    misleading_source_id_result = _validate_epub_fixture(
        runner,
        replace(base, source_id="siyavula_deliberately_misleading_grade_99"),
        members,
    )

    assert set(result["internal_member_sha256"]) == {
        "container",
        "navigation",
        "opf",
        "rights",
    }
    assert all(
        re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
        for digest in result["internal_member_sha256"].values()
    )
    assert result["package_identity"]["unique_identifier_linked"] is True
    assert (
        misleading_source_id_result["subject_grade_evidence"]
        == result["subject_grade_evidence"]
    )
    assert result["navigation_toc_structure"]["manifest_properties"] == ["nav"]
    assert result["rights_link_structure"] == {
        "artifact_notice_url": "http://creativecommons.org/licenses/by/4.0/",
        "manifest_media_type": "application/xhtml+xml",
        "structured_license_link_count": 1,
    }
    assert result["rights_context"] == {
        "artifact_notice_license_id": "CC-BY-4.0",
        "artifact_notice_url": "http://creativecommons.org/licenses/by/4.0/",
        "catalogue_license_id": "CC-BY-3.0",
        "catalogue_or_terms_evidence_runtime_verified": False,
        "preregistered_rights_subject_template_mismatch": True,
        "resolved_license_id": ("LicenseRef-Siyavula-Unbranded-CCBY-Version-Conflict"),
    }
    assert base.epub_identity is not None
    mismatched_filename_contract = replace(
        base,
        epub_identity=replace(
            base.epub_identity,
            filename_subject_token="PhysicalSciences",
        ),
    )
    with pytest.raises(
        runner.AcquisitionError,
        match="filename_subject_grade_contract_mismatch",
    ):
        _validate_epub_fixture(runner, mismatched_filename_contract, members)


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (
            lambda opf: opf.replace(b'version="3.0"', b'version="2.0"'),
            "package_version_invalid",
        ),
        (
            lambda opf: opf.replace(b'id="pub-id"', b'id="other"'),
            "unique_identifier_link_mismatch",
        ),
        (
            lambda opf: opf.replace(
                b"</metadata>", b"<creator>wrong namespace</creator></metadata>"
            ),
            "OPF_namespace_invalid:creator",
        ),
        (
            lambda opf: opf.replace(
                b"</metadata>",
                b"<dc:subject>Mathematics Grade 10</dc:subject></metadata>",
            ),
            "metadata_observation_mismatch",
        ),
        (
            lambda opf: opf.replace(
                b'<itemref idref="chapter"/>',
                b'<itemref idref="chapter"/><itemref idref="chapter"/>',
            ),
            "manifest_or_spine_invalid",
        ),
        (
            lambda opf: opf.replace(
                b'href="xhtml/maths10/chapter.xhtml"',
                b'href="https://example.invalid/chapter.xhtml"',
            ),
            "remote_manifest_URI_rejected",
        ),
        (
            lambda opf: opf.replace(b' properties="nav"', b""),
            "unique_navigation_manifest_item_required",
        ),
    ],
)
def test_epub_package_manifest_and_spine_claims_fail_closed(
    runner,
    mutation,
    match: str,
) -> None:
    base = next(
        source
        for source in runner.DIRECT_SOURCES
        if source.source_id == "siyavula_mathematics_grade_10_cc_by"
    )
    _payload, members = _epub_bytes()
    assert base.epub_identity is not None
    mutated = dict(members)
    mutated[base.epub_identity.opf_path] = mutation(
        mutated[base.epub_identity.opf_path]
    )

    with pytest.raises(runner.AcquisitionError, match=match):
        _validate_epub_fixture(runner, base, mutated)


@pytest.mark.parametrize(
    ("role", "mutation", "match"),
    [
        (
            "navigation",
            lambda value: value.replace(b'epub:type="toc"', b'epub:type="page-list"'),
            "unique_TOC_role_required",
        ),
        (
            "navigation",
            lambda value: value.replace(
                b'href="chapter.xhtml"', b'href="https://example.invalid/chapter"'
            ),
            "remote_manifest_URI_rejected",
        ),
        (
            "rights",
            lambda _value: (
                b'<!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml">'
                b"<body>Siyavula http://creativecommons.org/licenses/by/4.0/"
                b"</body></html>"
            ),
            "structured_license_link_missing",
        ),
    ],
)
def test_epub_navigation_and_rights_structure_fail_closed(
    runner,
    role: str,
    mutation,
    match: str,
) -> None:
    base = next(
        source
        for source in runner.DIRECT_SOURCES
        if source.source_id == "siyavula_mathematics_grade_10_cc_by"
    )
    _payload, members = _epub_bytes()
    assert base.epub_identity is not None
    member = (
        base.epub_identity.navigation_path
        if role == "navigation"
        else base.epub_identity.rights_member_path
    )
    mutated = dict(members)
    mutated[member] = mutation(mutated[member])

    with pytest.raises(runner.AcquisitionError, match=match):
        _validate_epub_fixture(runner, base, mutated)


def test_siyavula_payload_rights_evidence_is_exact_member_bound(
    runner, tmp_path
) -> None:
    base = next(
        source
        for source in runner.DIRECT_SOURCES
        if source.source_id == "siyavula_mathematics_grade_10_cc_by"
    )
    payload, members = _epub_bytes()
    source = _bind_epub_fixture_source(base, payload, members)
    rights_path = source.epub_identity.rights_member_path
    fd = _fd_for(tmp_path, payload)
    try:
        records = runner.verify_payload_rights_evidence(source, fd)
    finally:
        os.close(fd)
    assert records == source.expected_payload_rights_records()

    mutated_members = dict(members)
    mutated_members[rights_path] = mutated_members[rights_path].replace(
        b"Siyavula", b"SiyavulX"
    )
    mutated_payload = _rebuild_epub(mutated_members)
    fd = _fd_for(tmp_path, mutated_payload)
    try:
        with pytest.raises(runner.AcquisitionError, match="evidence_sha256_mismatch"):
            runner.verify_payload_rights_evidence(source, fd)
    finally:
        os.close(fd)

    relocated_members = dict(members)
    markers = b"Siyavula http://creativecommons.org/licenses/by/4.0/"
    relocated_members[rights_path] = (
        b'<!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml">'
        b"<body>rights omitted</body></html>"
    )
    chapter_path = "OPS/xhtml/maths10/chapter.xhtml"
    relocated_members[chapter_path] += markers
    relocated_payload = _rebuild_epub(relocated_members)
    relocated_source = _bind_epub_fixture_source(
        base, relocated_payload, relocated_members
    )
    fd = _fd_for(tmp_path, relocated_payload)
    try:
        with pytest.raises(runner.AcquisitionError, match="required_marker_missing"):
            runner.verify_payload_rights_evidence(relocated_source, fd)
    finally:
        os.close(fd)


def test_epub_rejects_confusable_namespaces_duplicate_targets_and_non_xhtml_spine(
    runner,
) -> None:
    source = next(
        source
        for source in runner.DIRECT_SOURCES
        if source.source_id == "siyavula_mathematics_grade_10_cc_by"
    )
    identity = source.epub_identity
    assert identity is not None
    valid_container = f"""<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfiles><rootfile full-path="{identity.opf_path}"
media-type="application/oebps-package+xml"/></rootfiles></container>""".encode()
    evil_container = valid_container.replace(
        b"urn:oasis:names:tc:opendocument:xmlns:container", b"urn:evil"
    )
    with pytest.raises(runner.AcquisitionError, match="container_namespace"):
        runner.validate_epub_identity(
            source,
            {
                "mimetype": b"application/epub+zip",
                "META-INF/container.xml": evil_container,
            },
            {"mimetype", "META-INF/container.xml"},
        )

    navigation = (
        b'<html xmlns="http://www.w3.org/1999/xhtml" '
        b'xmlns:epub="http://www.idpf.org/2007/ops"><body>'
        b'<nav epub:type="toc"><a href="chapter.xhtml">chapter</a></nav>'
        b"</body></html>"
    )
    rights = (
        b'<!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml"><body>Siyavula '
        b'<a href="http://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>'
        b"</body></html>"
    )
    opf_template = f"""<package xmlns="http://www.idpf.org/2007/opf" version="3.0"
unique-identifier="pub-id"
xmlns:dc="http://purl.org/dc/elements/1.1/">
<metadata><dc:identifier id="pub-id">{identity.identifier}</dc:identifier>
<dc:title>{identity.title}</dc:title><dc:language>{identity.language}</dc:language>
<meta property="dcterms:modified">{identity.modified}</meta></metadata>
<manifest>{{manifest}}</manifest><spine><itemref idref="chapter"/></spine></package>"""
    bound_items = (
        '<item id="nav" href="xhtml/maths10/maths10.nav.xhtml" '
        'media-type="application/xhtml+xml" properties="nav"/>'
        '<item id="rights" href="xhtml/maths10/front-matter-epubs/'
        'copyright_acknowledgements_ccby.html" media-type="application/xhtml+xml"/>'
    )
    duplicate_target = opf_template.format(
        manifest=(
            '<item id="chapter" href="xhtml/maths10/chapter.xhtml" '
            'media-type="application/xhtml+xml"/>'
            '<item id="duplicate" href="xhtml/maths10/chapter.xhtml" '
            'media-type="application/xhtml+xml"/>' + bound_items
        )
    ).encode()
    payloads = {
        "mimetype": b"application/epub+zip",
        "META-INF/container.xml": valid_container,
        identity.opf_path: duplicate_target,
        identity.navigation_path: navigation,
        identity.rights_member_path: rights,
    }
    duplicate_source = replace(
        source,
        epub_identity=replace(
            identity,
            opf_sha256=hashlib.sha256(duplicate_target).hexdigest(),
            navigation_sha256=hashlib.sha256(navigation).hexdigest(),
            rights_member_sha256=hashlib.sha256(rights).hexdigest(),
        ),
    )
    names = {*payloads, "OPS/xhtml/maths10/chapter.xhtml"}
    with pytest.raises(runner.AcquisitionError, match="duplicate_manifest_target"):
        runner.validate_epub_identity(duplicate_source, payloads, names)

    non_xhtml = opf_template.format(
        manifest=(
            '<item id="chapter" href="xhtml/maths10/chapter.txt" '
            'media-type="text/plain"/>' + bound_items
        )
    ).encode()
    payloads[identity.opf_path] = non_xhtml
    non_xhtml_source = replace(
        source,
        epub_identity=replace(
            identity,
            opf_sha256=hashlib.sha256(non_xhtml).hexdigest(),
            navigation_sha256=hashlib.sha256(navigation).hexdigest(),
            rights_member_sha256=hashlib.sha256(rights).hexdigest(),
        ),
    )
    names = {*payloads, "OPS/xhtml/maths10/chapter.txt"}
    with pytest.raises(runner.AcquisitionError, match="manifest_or_spine"):
        runner.validate_epub_identity(non_xhtml_source, payloads, names)


def test_obo_and_plain_ontology_require_markers_size_and_structure(
    runner, tmp_path
) -> None:
    base = next(
        source for source in runner.DIRECT_SOURCES if source.media_type == "text/obo"
    )
    payload = _obo_bytes(base.required_markers)
    source = replace(base, expected_bytes=len(payload))
    fd = _fd_for(tmp_path, payload)
    try:
        result = runner.inspect_obo_or_text(source, fd, _Checks())
    finally:
        os.close(fd)
    assert result["structure_checks"]["OBO_term_stanzas"] == 100

    without_marker = payload.replace(base.required_markers[0].encode(), b"wrong")
    fd = _fd_for(tmp_path, without_marker)
    try:
        with pytest.raises(runner.AcquisitionError, match="license_marker_missing"):
            runner.inspect_obo_or_text(source, fd, _Checks())
    finally:
        os.close(fd)


def test_chebi_rights_admission_is_bound_to_exact_1392_byte_header(
    runner, tmp_path
) -> None:
    base = next(
        source
        for source in runner.DIRECT_SOURCES
        if source.source_id == "chebi_release_252_three_star"
    )
    evidence = base.payload_rights_specs()[0]
    header = ("\n".join(evidence.required_markers) + "\n").encode().ljust(1_392, b" ")
    body = b"[Term]\nid: TEST:1\nname: fixture\n"
    payload = header + body
    bound_evidence = replace(
        evidence,
        sha256=hashlib.sha256(header).hexdigest(),
    )
    source = replace(
        base,
        expected_bytes=len(payload),
        expected_sha256=hashlib.sha256(payload).hexdigest(),
        payload_rights_evidence=(bound_evidence,),
    )
    fd = _fd_for(tmp_path, payload)
    try:
        records = runner.verify_payload_rights_evidence(source, fd)
    finally:
        os.close(fd)
    assert records == source.expected_payload_rights_records()
    assert runner.canonical_sha256(records).startswith("sha256:")

    mutated = b"X" + payload[1:]
    mutated_source = replace(
        source,
        expected_sha256=hashlib.sha256(mutated).hexdigest(),
    )
    fd = _fd_for(tmp_path, mutated)
    try:
        with pytest.raises(runner.AcquisitionError, match="evidence_sha256_mismatch"):
            runner.verify_payload_rights_evidence(mutated_source, fd)
    finally:
        os.close(fd)

    prefix_without_license = (b"data-version: 252\n").ljust(1_392, b" ")
    relocated = prefix_without_license + body + evidence.required_markers[1].encode()
    relocated_evidence = replace(
        evidence,
        sha256=hashlib.sha256(prefix_without_license).hexdigest(),
    )
    relocated_source = replace(
        base,
        expected_bytes=len(relocated),
        expected_sha256=hashlib.sha256(relocated).hexdigest(),
        payload_rights_evidence=(relocated_evidence,),
    )
    fd = _fd_for(tmp_path, relocated)
    try:
        with pytest.raises(runner.AcquisitionError, match="required_marker_missing"):
            runner.verify_payload_rights_evidence(relocated_source, fd)
    finally:
        os.close(fd)


def test_rdf_requires_well_formed_document_markers_and_plausible_size(
    runner, tmp_path
) -> None:
    base = next(
        source
        for source in runner.DIRECT_SOURCES
        if source.media_type == "application/rdf+xml"
    )
    payload = _rdf_bytes(base.required_markers)
    source = replace(base, expected_bytes=len(payload))
    fd = _fd_for(tmp_path, payload)
    try:
        result = runner.inspect_rdf_xml(source, fd, _Checks())
    finally:
        os.close(fd)

    with pytest.raises(runner.AcquisitionError, match="forbidden_XML_markup"):
        runner.reject_forbidden_xml_markup(
            b'<!DOCTYPE rdf:RDF [<!ENTITY x "expansion">]>',
            base.source_id,
        )
    assert result["structure_checks"]["RDF_description_count"] == 100

    malformed = payload[:-10]
    fd = _fd_for(tmp_path, malformed)
    try:
        with pytest.raises(runner.AcquisitionError, match="not_well_formed"):
            runner.inspect_rdf_xml(
                replace(base, expected_bytes=len(malformed)), fd, _Checks()
            )
    finally:
        os.close(fd)


@pytest.mark.parametrize("encoding", ["utf-16", "utf-32"])
def test_xml_guard_rejects_encoded_dtd_before_parser_or_marker_gates(
    runner, encoding
) -> None:
    payload = (
        '<?xml version="1.0"?><!DOCTYPE root [<!ENTITY x "expanded">]><root>&x;</root>'
    ).encode(encoding)
    with pytest.raises(runner.AcquisitionError, match="forbidden_XML_markup"):
        runner.reject_forbidden_xml_markup(payload, "encoded_fixture")


def test_rdf_rejects_description_in_confusable_namespace(runner, tmp_path) -> None:
    base = next(
        source
        for source in runner.DIRECT_SOURCES
        if source.media_type == "application/rdf+xml"
    )
    marker_text = (
        '<dc:rights xml:lang="en">Public domain</dc:rights>'
        '<dc:date rdf:datatype="http://www.w3.org/2001/XMLSchema#date">'
        "2023-11-02</dc:date>"
    )
    descriptions = "".join(
        f'<evil:Description rdf:about="urn:test:{index}"/>' for index in range(100)
    )
    payload = (
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:evil="urn:evil">'
        f"{marker_text}{descriptions}</rdf:RDF>"
    ).encode()
    fd = _fd_for(tmp_path, payload)
    try:
        with pytest.raises(runner.AcquisitionError, match="description_namespace"):
            runner.inspect_rdf_xml(
                replace(base, expected_bytes=len(payload)), fd, _Checks()
            )
    finally:
        os.close(fd)


@pytest.mark.parametrize(
    "value",
    ["../escape", "/absolute", "a\\b", "-option", "a/*", "a//b", "a/../b"],
)
def test_git_selected_paths_reject_escape_options_and_patterns(
    runner, value: str
) -> None:
    with pytest.raises(runner.AcquisitionError, match="git_relative_path_invalid"):
        runner.validate_git_relative_path(value)


def _tree_record(path: str, payload: bytes, *, mode: str = "100644") -> bytes:
    return f"{mode} blob {_git_blob(payload)}\t{path}".encode() + b"\0"


def test_git_tree_parser_binds_count_paths_blobs_and_rejects_special_entries(
    runner,
) -> None:
    source = replace(
        runner.GIT_SOURCES[0],
        selected_paths=("LICENSE", "modules"),
        selected_file_count=2,
        selected_bytes=2,
    )
    payload = _tree_record("LICENSE", b"L") + _tree_record("modules/a.cnxml", b"A")
    records = runner.parse_git_tree_records(payload, source)
    assert records["LICENSE"][1] == _git_blob(b"L")

    for mode in ("120000", "160000", "040000"):
        with pytest.raises(runner.AcquisitionError, match="special_entry"):
            runner.parse_git_tree_records(
                _tree_record("LICENSE", b"L", mode=mode)
                + _tree_record("modules/a.cnxml", b"A"),
                source,
            )

    with pytest.raises(runner.AcquisitionError, match="file_count"):
        runner.parse_git_tree_records(_tree_record("LICENSE", b"L"), source)


def test_git_tree_inventory_recurses_real_selected_subtrees_and_nonrecursive_fails(
    runner, tmp_path
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(
        ["git", "init", "--quiet", "--object-format=sha1", str(repository)],
        check=True,
        capture_output=True,
    )
    (repository / "modules/nested").mkdir(parents=True)
    files = {
        "LICENSE": b"fixture license\n",
        "modules/a.cnxml": b"fixture module a\n",
        "modules/nested/b.cnxml": b"fixture module b\n",
    }
    for relative_path, payload in files.items():
        (repository / relative_path).write_bytes(payload)
    subprocess.run(
        ["git", "-C", str(repository), "add", "--", *files],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "-c",
            "user.name=CUR0S Fixture",
            "-c",
            "user.email=cur0s-fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.hooksPath=/dev/null",
            "commit",
            "--quiet",
            "-m",
            "nested selected tree fixture",
        ],
        check=True,
        capture_output=True,
    )
    commit_sha = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    source = replace(
        runner.GIT_SOURCES[0],
        commit_sha=commit_sha,
        selected_paths=("LICENSE", "modules"),
        selected_file_count=len(files),
        selected_bytes=sum(len(payload) for payload in files.values()),
    )

    recursive = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "ls-tree",
            "-r",
            "-z",
            "--full-tree",
            commit_sha,
            "--",
            *source.selected_paths,
        ],
        check=True,
        capture_output=True,
    ).stdout
    records = runner.parse_git_tree_records(recursive, source)
    assert set(records) == set(files)
    assert all(mode == "100644" for mode, _oid in records.values())

    nonrecursive = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "ls-tree",
            "-z",
            "--full-tree",
            commit_sha,
            "--",
            *source.selected_paths,
        ],
        check=True,
        capture_output=True,
    ).stdout
    assert b"040000 tree " in nonrecursive
    with pytest.raises(runner.AcquisitionError, match="special_entry"):
        runner.parse_git_tree_records(nonrecursive, source)


def test_git_worktree_manifest_binds_blob_count_bytes_and_rejects_symlink(
    runner, tmp_path
) -> None:
    checkout = tmp_path / "checkout"
    (checkout / "modules").mkdir(parents=True)
    (checkout / "LICENSE").write_bytes(b"license")
    (checkout / "modules/a.cnxml").write_bytes(b"module")
    records = {
        "LICENSE": ("100644", _git_blob(b"license")),
        "modules/a.cnxml": ("100644", _git_blob(b"module")),
    }
    source = replace(
        runner.GIT_SOURCES[0],
        selected_paths=("LICENSE", "modules"),
        selected_file_count=2,
        selected_bytes=len(b"licensemodule"),
    )
    manifest, size = runner.build_worktree_manifest(
        checkout, source, records, _Checks()
    )
    assert len(manifest) == 2
    assert size == source.selected_bytes

    wrong_size = replace(source, selected_bytes=source.selected_bytes + 1)
    with pytest.raises(runner.AcquisitionError, match="selected_bytes"):
        runner.build_worktree_manifest(checkout, wrong_size, records, _Checks())

    (checkout / "modules/a.cnxml").unlink()
    (checkout / "modules/a.cnxml").symlink_to(checkout / "LICENSE")
    with pytest.raises(runner.AcquisitionError, match="nonregular"):
        runner.build_worktree_manifest(checkout, source, records, _Checks())


@pytest.mark.parametrize(
    ("fault", "message"),
    [
        ("commit", "fetched_commit_mismatch"),
        ("tree", "tree_mismatch"),
        ("license", "license_sha256_mismatch"),
        ("bytes", "selected_bytes_mismatch"),
        ("symlink", "nonregular"),
    ],
)
def test_git_acquisition_fails_closed_on_exact_identity_and_worktree_faults(
    runner, monkeypatch, tmp_path, fault: str, message: str
) -> None:
    git_root = tmp_path / "git"
    git_root.mkdir()
    license_payload = b"fixture commercial license"
    wrong_license_payload = b"fixture commercial licensf"
    module_payload = b"fixture module"
    records = {
        "LICENSE": ("100644", _git_blob(license_payload)),
        "modules/a.cnxml": ("100644", _git_blob(module_payload)),
    }
    selected_bytes = len(license_payload) + len(module_payload)
    source = replace(
        runner.GIT_SOURCES[0],
        commit_sha="a" * 40,
        tree_sha="b" * 40,
        selected_paths=("LICENSE", "modules"),
        selected_file_count=2,
        selected_bytes=selected_bytes + (1 if fault == "bytes" else 0),
        license_sha256=hashlib.sha256(license_payload).hexdigest(),
    )
    monkeypatch.setattr(runner, "run_git_with_retries", lambda *_args, **_kwargs: 1)

    def run_git(args, cwd, _envelope, _checkpoint):
        if args[0] != "checkout":
            return
        (cwd / "modules").mkdir(exist_ok=True)
        (cwd / "LICENSE").write_bytes(
            wrong_license_payload if fault == "license" else license_payload
        )
        module = cwd / "modules/a.cnxml"
        if fault == "symlink":
            module.symlink_to(cwd / "LICENSE")
        else:
            module.write_bytes(module_payload)

    monkeypatch.setattr(runner, "run_git", run_git)

    def run_git_text(args, _cwd, _envelope, _checkpoint):
        joined = " ".join(args)
        if "FETCH_HEAD" in joined:
            return "c" * 40 if fault == "commit" else source.commit_sha
        if args == ["rev-parse", f"{source.commit_sha}^{{tree}}"]:
            return "d" * 40 if fault == "tree" else source.tree_sha
        if args == ["rev-parse", "HEAD"]:
            return source.commit_sha
        if args == ["rev-parse", "HEAD^{tree}"]:
            return source.tree_sha
        if args[:2] == ["remote", "get-url"]:
            return source.clone_url
        raise AssertionError(args)

    monkeypatch.setattr(runner, "run_git_text", run_git_text)
    tree_payload = b"".join(
        _tree_record(
            path,
            (
                wrong_license_payload
                if path == "LICENSE" and fault == "license"
                else license_payload
                if path == "LICENSE"
                else module_payload
            ),
        )
        for path in records
    )

    def run_git_capture(args, *_rest, **_kwargs):
        if args[0] != "ls-tree":
            return b""
        assert args == [
            "ls-tree",
            "-r",
            "-z",
            "--full-tree",
            source.commit_sha,
            "--",
            *source.selected_paths,
        ]
        return tree_payload

    monkeypatch.setattr(runner, "run_git_capture", run_git_capture)

    with pytest.raises(runner.AcquisitionError, match=message):
        runner.acquire_git_source(
            source,
            git_root,
            SimpleNamespace(),
            _Checks(),
            frozenset({"github.com"}),
        )


def test_git_acquisition_accepts_exact_commit_tree_license_count_and_bytes(
    runner, monkeypatch, tmp_path
) -> None:
    git_root = tmp_path / "git"
    git_root.mkdir()
    license_payload = b"fixture commercial license"
    module_payload = b"fixture module"
    source = replace(
        runner.GIT_SOURCES[0],
        commit_sha="a" * 40,
        tree_sha="b" * 40,
        selected_paths=("LICENSE", "modules"),
        selected_file_count=2,
        selected_bytes=len(license_payload) + len(module_payload),
        license_sha256=hashlib.sha256(license_payload).hexdigest(),
    )
    monkeypatch.setattr(runner, "run_git_with_retries", lambda *_args, **_kwargs: 1)

    def run_git(args, cwd, _envelope, _checkpoint):
        if args[0] == "init":
            (cwd / ".git").mkdir(exist_ok=True)
            (cwd / ".git/config").write_bytes(b"fixture")
        elif args[0] == "checkout":
            (cwd / "modules").mkdir(exist_ok=True)
            (cwd / "LICENSE").write_bytes(license_payload)
            (cwd / "modules/a.cnxml").write_bytes(module_payload)

    monkeypatch.setattr(runner, "run_git", run_git)

    def run_git_text(args, _cwd, _envelope, _checkpoint):
        joined = " ".join(args)
        if "FETCH_HEAD" in joined or args == ["rev-parse", "HEAD"]:
            return source.commit_sha
        if args[0] == "rev-parse":
            return source.tree_sha
        if args[:2] == ["remote", "get-url"]:
            return source.clone_url
        raise AssertionError(args)

    monkeypatch.setattr(runner, "run_git_text", run_git_text)
    tree_payload = _tree_record("LICENSE", license_payload) + _tree_record(
        "modules/a.cnxml", module_payload
    )
    monkeypatch.setattr(
        runner,
        "run_git_capture",
        lambda args, *_rest, **_kwargs: tree_payload if args[0] == "ls-tree" else b"",
    )

    artifact, inspection = runner.acquire_git_source(
        source,
        git_root,
        SimpleNamespace(),
        _Checks(),
        frozenset({"github.com"}),
    )
    assert artifact["verification"]["commit_verified"] is True
    assert artifact["verification"]["tree_verified"] is True
    assert artifact["verification"]["license_verified"] is True
    assert inspection["member_count"] == 2


def test_builder_and_runner_publication_are_exclusive_no_overwrite(
    builder, runner, tmp_path
) -> None:
    builder_target = tmp_path / "prereg.json"
    builder.exclusive_publish(builder_target, b"first\n")
    with pytest.raises(FileExistsError):
        builder.exclusive_publish(builder_target, b"second\n")
    assert builder_target.read_bytes() == b"first\n"

    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        runner.write_exclusive_bytes_at(
            directory_fd, "receipt.json", b"first\n", mode=0o400
        )
        provenance = runner.ExclusiveCreateProvenance()
        with pytest.raises(FileExistsError):
            runner.write_exclusive_bytes_at(
                directory_fd,
                "receipt.json",
                b"second\n",
                mode=0o400,
                provenance=provenance,
            )
        assert provenance.create_attempted is True
        assert provenance.created_by_this_call is False
        assert provenance.creation_binding is None
    finally:
        os.close(directory_fd)
    assert (tmp_path / "receipt.json").read_bytes() == b"first\n"


def test_output_path_is_exact_and_defers_existing_orphan_to_secure_reconciliation(
    runner, monkeypatch, tmp_path
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    assert (
        runner.validate_private_output_path(output, RUN_ID, "candidate-001") == output
    )

    with pytest.raises(runner.AcquisitionError, match="output_directory_name"):
        runner.validate_private_output_path(
            output.with_name("candidate-002"), RUN_ID, "candidate-001"
        )
    (tmp_path / "outside").mkdir()
    with pytest.raises(runner.AcquisitionError, match="output_parent"):
        runner.validate_private_output_path(
            tmp_path / "outside/candidate-001", RUN_ID, "candidate-001"
        )

    output.mkdir()
    output.chmod(0o700)
    assert (
        runner.validate_private_output_path(output, RUN_ID, "candidate-001") == output
    )


def test_one_shot_claim_blocks_replay_and_completion_is_last(
    runner, monkeypatch, tmp_path
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    candidate = _claimed_candidate(runner, output)
    try:
        receipt = _terminal_receipt(runner, candidate)
        envelope = SimpleNamespace(
            lease=SimpleNamespace(max_private_output_bytes=16 * 1024 * 1024),
            check=lambda *_args, **_kwargs: None,
            disarm=lambda: None,
        )
        runner.finalize_candidate(candidate, envelope, RUN_ID, receipt)
        assert (output / "receipt.json").is_file()
        assert (output / "COMPLETE.json").is_file()
        assert stat.S_IMODE((output / "receipt.json").stat().st_mode) == 0o400
        assert stat.S_IMODE((output / "COMPLETE.json").stat().st_mode) == 0o400
        with pytest.raises(runner.AcquisitionError, match="already_completed"):
            candidate.write_receipt(receipt)
    finally:
        candidate.close()

    with pytest.raises(runner.AcquisitionError, match="forbids_replay"):
        runner.PrivateCandidate.prepare(output, RUN_ID, SHA256, SHA256)
    assert not (_abort_path(runner)).exists()


@pytest.mark.parametrize(
    "fault",
    ["mkdir", "parent_fsync", "candidate_open", "ownership", "candidate_fsync"],
)
def test_candidate_preparation_faults_never_publish_claim_and_clean_exact_empty_dir(
    runner, monkeypatch, tmp_path, fault
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    original_open = runner.os.open
    original_fsync = runner.os.fsync
    original_require_owned = runner.require_owned_fd

    if fault == "mkdir":
        monkeypatch.setattr(
            runner.os,
            "mkdir",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("mkdir_fault")),
        )
    elif fault == "parent_fsync":
        calls = 0

        def fail_parent_fsync_once(fd):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("parent_fsync_fault")
            return original_fsync(fd)

        monkeypatch.setattr(runner.os, "fsync", fail_parent_fsync_once)
    elif fault == "candidate_open":
        failed = False

        def fail_candidate_open_once(path, flags, mode=0o777, *, dir_fd=None):
            nonlocal failed
            if path == "candidate-001" and dir_fd is not None and not failed:
                failed = True
                raise OSError("candidate_open_fault")
            return original_open(path, flags, mode, dir_fd=dir_fd)

        monkeypatch.setattr(runner.os, "open", fail_candidate_open_once)
    elif fault == "ownership":

        def fail_candidate_ownership(fd, *, owner_only, role):
            if role == "candidate_output":
                raise runner.AcquisitionError("candidate_ownership_fault")
            return original_require_owned(fd, owner_only=owner_only, role=role)

        monkeypatch.setattr(runner, "require_owned_fd", fail_candidate_ownership)
    elif fault == "candidate_fsync":
        calls = 0

        def fail_second_fsync(fd):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("candidate_fsync_fault")
            return original_fsync(fd)

        monkeypatch.setattr(runner.os, "fsync", fail_second_fsync)
    else:
        raise AssertionError(fault)

    with pytest.raises((OSError, runner.AcquisitionError)):
        runner.PrivateCandidate.prepare(output, RUN_ID, SHA256, SHA256)

    assert not output.exists()
    assert not (_claim_path(runner)).exists()
    assert not (_abort_path(runner)).exists()


def test_mkdir_success_then_interrupt_emits_parent_initialization_abort(
    runner, monkeypatch, tmp_path
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    original_mkdir = runner.os.mkdir

    def create_then_interrupt(*args, **kwargs):
        original_mkdir(*args, **kwargs)
        raise KeyboardInterrupt()

    monkeypatch.setattr(runner.os, "mkdir", create_then_interrupt)
    with pytest.raises(KeyboardInterrupt):
        runner.PrivateCandidate.prepare(output, RUN_ID, SHA256, SHA256)

    assert output.is_dir()
    assert not (_claim_path(runner)).exists()
    abort = runner.strict_json_loads((_abort_path(runner)).read_bytes())
    assert abort["state"] == "blocked_incomplete_initialization"
    assert abort["claim_state"] == "not_published"
    assert abort["replay_allowed"] is False


def test_preexisting_parent_abort_forbids_new_candidate_and_claim(
    runner, monkeypatch, tmp_path
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    abort_path = _abort_path(runner)
    abort_path.write_bytes(b"{}\n")
    abort_path.chmod(0o400)

    with pytest.raises(runner.AcquisitionError, match="prior_abort"):
        runner.PrivateCandidate.prepare(output, RUN_ID, SHA256, SHA256)

    assert not output.exists()
    assert not (_claim_path(runner)).exists()
    assert abort_path.read_bytes() == b"{}\n"


def test_claim_failure_before_create_rolls_back_only_unclaimed_empty_candidate(
    runner, monkeypatch, tmp_path
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    candidate = runner.PrivateCandidate.prepare(output, RUN_ID, SHA256, SHA256)
    monkeypatch.setattr(
        runner,
        "write_exclusive_bytes_at",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("claim_open_fault")),
    )
    try:
        with pytest.raises(runner.ClaimPublicationError):
            candidate.publish_execution_claim()
        assert candidate.claim_consumed is False
        assert not output.exists()
        assert not (_claim_path(runner)).exists()
    finally:
        candidate.close()


def test_partial_claim_is_never_replayed_and_gets_typed_parent_abort(
    runner, monkeypatch, tmp_path
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    candidate = runner.PrivateCandidate.prepare(output, RUN_ID, SHA256, SHA256)
    original_writer = runner.write_exclusive_bytes_at

    def partial_claim(directory_fd, name, payload, *, mode, provenance=None):
        if name != candidate._claim_name:
            return original_writer(
                directory_fd,
                name,
                payload,
                mode=mode,
                provenance=provenance,
            )
        if provenance is not None:
            provenance.create_attempted = True
        fd = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            mode,
            dir_fd=directory_fd,
        )
        if provenance is not None:
            created = os.fstat(fd)
            provenance.created_by_this_call = True
            provenance.creation_binding = (
                created.st_dev,
                created.st_ino,
                created.st_uid,
                created.st_gid,
            )
        try:
            os.write(fd, b"{")
            os.fsync(fd)
            os.fchmod(fd, mode)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(directory_fd)
        raise OSError("claim_partial_write_fault")

    monkeypatch.setattr(runner, "write_exclusive_bytes_at", partial_claim)
    try:
        with pytest.raises(runner.ClaimPublicationError):
            candidate.publish_execution_claim()
        assert candidate.claimed is False
        assert candidate.claim_consumed is True
        assert output.is_dir()
        assert (_claim_path(runner)).read_bytes() == b"{"
        candidate.write_parent_abort(
            blocker="claim_partial_write_fault",
            checkpoint="claim_publication",
        )
        abort = runner.strict_json_loads((_abort_path(runner)).read_bytes())
        assert abort["state"] == "blocked_incomplete_terminalization"
        assert abort["claim_state"] == "present_unverified"
        assert abort["replay_allowed"] is False
    finally:
        candidate.close()


def test_exact_preexisting_claim_is_not_adopted_by_new_publication(
    runner, monkeypatch, tmp_path
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    candidate = runner.PrivateCandidate.prepare(output, RUN_ID, SHA256, SHA256)
    claim_value = {
        "schema_version": runner.EXECUTION_CLAIM_SCHEMA,
        "state": "claimed_terminal_pending",
        "run_id": RUN_ID,
        "output_directory_name": "candidate-001",
        "phone_execution_ordinal": 1,
        "preregistration_root_sha256": SHA256,
        "contract_root_sha256": SHA256,
    }
    claim_payload = runner.canonical_json_bytes(claim_value) + b"\n"
    runner.write_exclusive_bytes_at(
        candidate._control_fd,
        candidate._claim_name,
        claim_payload,
        mode=0o400,
    )

    try:
        with pytest.raises(runner.ClaimPublicationError):
            candidate.publish_execution_claim()
        assert candidate.claimed is False
        assert candidate.claim_consumed is False
        assert candidate.foreign_claim_observed is True
        assert (_claim_path(runner)).read_bytes() == claim_payload
        assert not (_abort_path(runner)).exists()
    finally:
        candidate.close()


def test_main_claim_race_loser_neither_rolls_back_nor_terminalizes_winner(
    runner,
    monkeypatch,
    tmp_path,
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    prereg, prereg_bytes = _install_main_transaction_mocks(
        runner,
        monkeypatch,
        output,
    )
    winner = runner.PrivateCandidate.prepare(output, RUN_ID, SHA256, SHA256)
    loser = runner.PrivateCandidate.prepare(output, RUN_ID, SHA256, SHA256)
    prepared_identity = runner.stat_identity(output.stat())
    original_writer = runner.write_exclusive_bytes_at
    race_injected = False
    loser_provenance = None

    def interleaving_writer(
        directory_fd,
        name,
        payload,
        *,
        mode,
        provenance=None,
    ):
        nonlocal race_injected, loser_provenance
        if name == loser._claim_name and not race_injected:
            race_injected = True
            loser_provenance = provenance
            winner.publish_execution_claim()
        return original_writer(
            directory_fd,
            name,
            payload,
            mode=mode,
            provenance=provenance,
        )

    monkeypatch.setattr(runner, "write_exclusive_bytes_at", interleaving_writer)
    monkeypatch.setattr(
        runner.PrivateCandidate,
        "prepare",
        classmethod(lambda _cls, *_args, **_kwargs: loser),
    )
    try:
        exit_code = runner.main(
            args=Namespace(preregistration="unused", output_dir=str(output)),
            prereg_bytes=prereg_bytes,
            prereg=prereg,
        )

        assert exit_code == 5
        assert race_injected is True
        assert loser_provenance is not None
        assert loser_provenance.create_attempted is True
        assert loser_provenance.created_by_this_call is False
        assert loser_provenance.creation_binding is None
        assert winner.claimed is True
        assert loser.claimed is False
        assert loser.claim_consumed is False
        assert loser.foreign_claim_observed is True
        assert runner.stat_identity(output.stat()) == prepared_identity
        assert list(output.iterdir()) == []
        assert (_claim_path(runner)).is_file()
        assert not (_abort_path(runner)).exists()
        assert not (output / "receipt.json").exists()
        assert not (output / "COMPLETE.json").exists()
    finally:
        winner.close()
        loser.close()


def test_exclusive_writer_recovers_only_same_inode_after_directory_fsync_retry(
    runner, monkeypatch, tmp_path
) -> None:
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    original_fsync = runner.os.fsync
    directory_failures = 0

    def fail_first_directory_fsync(fd):
        nonlocal directory_failures
        if fd == directory_fd and directory_failures == 0:
            directory_failures += 1
            raise OSError("directory_fsync_ambiguous")
        return original_fsync(fd)

    monkeypatch.setattr(runner.os, "fsync", fail_first_directory_fsync)
    try:
        artifact = runner.write_exclusive_bytes_at(
            directory_fd, "artifact.json", b"payload\n", mode=0o400
        )
    finally:
        os.close(directory_fd)
    assert directory_failures == 1
    assert artifact.sha256 == _sha(b"payload\n")
    assert (tmp_path / "artifact.json").read_bytes() == b"payload\n"


def test_file_fsync_failure_and_same_content_inode_swap_are_never_adopted(
    runner, monkeypatch, tmp_path
) -> None:
    first_dir = tmp_path / "file-fsync"
    first_dir.mkdir()
    directory_fd = os.open(first_dir, os.O_RDONLY | os.O_DIRECTORY)
    original_fsync = runner.os.fsync
    failed = False

    def fail_first_file_fsync(fd):
        nonlocal failed
        if fd != directory_fd and not failed:
            failed = True
            raise OSError("file_fsync_fault")
        return original_fsync(fd)

    monkeypatch.setattr(runner.os, "fsync", fail_first_file_fsync)
    try:
        with pytest.raises(OSError, match="file_fsync_fault"):
            runner.write_exclusive_bytes_at(
                directory_fd, "artifact.json", b"payload\n", mode=0o400
            )
        with pytest.raises(FileExistsError):
            runner.write_exclusive_bytes_at(
                directory_fd, "artifact.json", b"payload\n", mode=0o400
            )
    finally:
        os.close(directory_fd)

    monkeypatch.setattr(runner.os, "fsync", original_fsync)
    second_dir = tmp_path / "inode-swap"
    second_dir.mkdir()
    directory_fd = os.open(second_dir, os.O_RDONLY | os.O_DIRECTORY)

    def replace_with_same_content(directory_fd_arg, name, _initial, _final):
        os.unlink(name, dir_fd=directory_fd_arg)
        replacement = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o400,
            dir_fd=directory_fd_arg,
        )
        try:
            os.write(replacement, b"payload\n")
            os.fsync(replacement)
            os.fchmod(replacement, 0o400)
            os.fsync(replacement)
        finally:
            os.close(replacement)
        raise OSError("same_content_inode_swap")

    monkeypatch.setattr(runner, "validate_same_entry", replace_with_same_content)
    try:
        with pytest.raises(OSError, match="same_content_inode_swap"):
            runner.write_exclusive_bytes_at(
                directory_fd, "artifact.json", b"payload\n", mode=0o400
            )
    finally:
        os.close(directory_fd)


@pytest.mark.parametrize("target_name", ["receipt.json", "COMPLETE.json"])
def test_partial_terminal_artifact_preserves_claim_and_emits_parent_abort(
    runner, monkeypatch, tmp_path, target_name
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    candidate = _claimed_candidate(runner, output)
    original_writer = runner.write_exclusive_bytes_at
    receipt = _terminal_receipt(runner, candidate)

    def partial_terminal(directory_fd, name, payload, *, mode, provenance=None):
        if name != target_name:
            return original_writer(
                directory_fd,
                name,
                payload,
                mode=mode,
                provenance=provenance,
            )
        fd = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            mode,
            dir_fd=directory_fd,
        )
        try:
            os.write(fd, b"{")
            os.fsync(fd)
            os.fchmod(fd, mode)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(directory_fd)
        raise OSError(f"partial_{name}")

    monkeypatch.setattr(runner, "write_exclusive_bytes_at", partial_terminal)
    envelope = SimpleNamespace(
        lease=SimpleNamespace(max_private_output_bytes=16 * 1024 * 1024),
        check=lambda *_args, **_kwargs: None,
        disarm=lambda: None,
    )
    try:
        with pytest.raises(OSError, match="partial_"):
            runner.finalize_candidate(candidate, envelope, RUN_ID, receipt)
        candidate.write_parent_abort(
            blocker=f"partial_{target_name}",
            checkpoint="terminal_evidence_publication",
        )
        assert (_abort_path(runner)).is_file()
        assert not candidate.completed
        if target_name == "receipt.json":
            assert not (output / "COMPLETE.json").exists()
        else:
            assert (output / "receipt.json").is_file()
            assert (output / "COMPLETE.json").read_bytes() == b"{"
    finally:
        candidate.close()


def test_valid_complete_is_adopted_after_interrupted_return_and_never_aborted(
    runner, monkeypatch, tmp_path
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    candidate = _claimed_candidate(runner, output)
    receipt = _terminal_receipt(runner, candidate)
    envelope = SimpleNamespace(
        lease=SimpleNamespace(max_private_output_bytes=16 * 1024 * 1024),
        check=lambda *_args, **_kwargs: None,
        disarm=lambda: None,
    )
    original_write_completion = candidate.write_completion_last

    def commit_then_interrupt(value):
        original_write_completion(value)
        candidate._completed = False
        candidate._completion = None
        raise KeyboardInterrupt()

    monkeypatch.setattr(candidate, "write_completion_last", commit_then_interrupt)
    try:
        with pytest.raises(KeyboardInterrupt):
            runner.finalize_candidate(candidate, envelope, RUN_ID, receipt)
        assert candidate.reconcile_exact_completion_if_present() is True
        with pytest.raises(runner.AcquisitionError, match="abort_forbidden"):
            candidate.write_parent_abort(
                blocker="interrupt_after_complete",
                checkpoint="terminal_evidence_publication",
            )
        assert not (_abort_path(runner)).exists()
    finally:
        candidate.close()


@pytest.mark.parametrize("swap", ["claim", "candidate_path"])
def test_complete_publication_boundary_swap_cannot_commit_or_use_cached_success(
    runner, monkeypatch, tmp_path, swap: str
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    candidate = _claimed_candidate(runner, output)
    receipt = _terminal_receipt(runner, candidate)
    envelope = SimpleNamespace(
        lease=SimpleNamespace(max_private_output_bytes=16 * 1024 * 1024),
        check=lambda *_args, **_kwargs: None,
        disarm=lambda: None,
    )
    original_publish = runner.publish_exact_bytes_at

    def publish_then_swap(directory_fd, name, payload, *, mode):
        artifact = original_publish(directory_fd, name, payload, mode=mode)
        if name != "COMPLETE.json":
            return artifact
        if swap == "claim":
            os.unlink(candidate._claim_name, dir_fd=candidate._control_fd)
            original_publish(
                candidate._control_fd,
                candidate._claim_name,
                b'{"forged":true}\n',
                mode=0o400,
            )
        else:
            os.rename(
                output.name,
                "displaced-candidate",
                src_dir_fd=candidate._parent_fd,
                dst_dir_fd=candidate._parent_fd,
            )
            os.mkdir(output.name, mode=0o700, dir_fd=candidate._parent_fd)
        return artifact

    monkeypatch.setattr(runner, "publish_exact_bytes_at", publish_then_swap)
    try:
        with pytest.raises(
            runner.AcquisitionError,
            match="postpublication_revalidation_failed",
        ):
            runner.finalize_candidate(candidate, envelope, RUN_ID, receipt)
        candidate._completed = True
        assert candidate.reconcile_exact_completion_if_present() is False
        assert candidate.completed is False
    finally:
        candidate.close()


def test_source_mutation_at_complete_boundary_blocks_passed_scope_terminal(
    runner, monkeypatch, tmp_path
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    candidate = _claimed_candidate(runner, output)
    sources = output / "sources"
    sources.mkdir(mode=0o700)
    source_file = sources / "bound-source.bin"
    source_file.write_bytes(b"admitted")
    source_file.chmod(0o400)
    expected_sha = _sha(b"admitted")

    def revalidate_source(_expected_control_entries: frozenset[str]) -> None:
        if _sha(source_file.read_bytes()) != expected_sha:
            raise runner.AcquisitionError("terminal_source_custody_changed")

    candidate.bind_terminal_custody_revalidator(revalidate_source)
    receipt = _terminal_receipt(runner, candidate, state="passed_scope")
    envelope = SimpleNamespace(
        lease=SimpleNamespace(max_private_output_bytes=16 * 1024 * 1024),
        check=lambda *_args, **_kwargs: None,
        disarm=lambda: None,
    )
    original_publish = runner.publish_exact_bytes_at

    def publish_then_mutate(directory_fd, name, payload, *, mode):
        artifact = original_publish(directory_fd, name, payload, mode=mode)
        if name == "COMPLETE.json":
            source_file.chmod(0o600)
            source_file.write_bytes(b"mutated")
            source_file.chmod(0o400)
        return artifact

    monkeypatch.setattr(runner, "publish_exact_bytes_at", publish_then_mutate)
    try:
        with pytest.raises(
            runner.AcquisitionError,
            match="postpublication_revalidation_failed",
        ):
            runner.finalize_candidate(candidate, envelope, RUN_ID, receipt)
        assert candidate.reconcile_exact_completion_if_present() is False
        assert candidate.completed is False
    finally:
        candidate.close()


@pytest.mark.parametrize(
    "signum",
    [signal.SIGINT, signal.SIGTERM]
    + ([signal.SIGHUP] if hasattr(signal, "SIGHUP") else []),
)
def test_stop_signals_are_typed_and_terminalization_defers_reentry(
    runner, monkeypatch, signum
) -> None:
    handlers, mask_calls = _install_signal_harness(runner, monkeypatch)
    guard = runner.TerminationSignalGuard()
    guard.block_during_initialization()
    guard.arm()
    guard.restore_initialization_mask()
    with pytest.raises(runner.OperationalStop, match=signal.Signals(signum).name):
        handlers[signum](signum, None)
    guard.defer_during_terminalization()
    handlers[signum](signum, None)
    assert guard.deferred_signals == (signal.Signals(signum).name,)
    guard.disarm()
    assert handlers[signum] == signal.SIG_DFL
    assert [operation for operation, _values in mask_calls] == [
        signal.SIG_BLOCK,
        signal.SIG_SETMASK,
    ]


def test_broken_stdout_cannot_downgrade_committed_receipt(runner, monkeypatch) -> None:
    monkeypatch.setattr(
        "builtins.print",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(BrokenPipeError()),
    )
    runner.emit_committed_receipt({"state": "passed_scope"})


def test_main_terminalizes_interrupt_across_prepare_return_without_claim(
    runner, monkeypatch, tmp_path
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    prereg, prereg_bytes = _install_main_transaction_mocks(runner, monkeypatch, output)
    original_prepare = runner.PrivateCandidate.prepare
    prepared = []

    def prepare_then_interrupt(_cls, *args, **kwargs):
        candidate = original_prepare(*args, **kwargs)
        prepared.append(candidate)
        raise KeyboardInterrupt()

    monkeypatch.setattr(
        runner.PrivateCandidate,
        "prepare",
        classmethod(prepare_then_interrupt),
    )
    try:
        exit_code = runner.main(
            args=Namespace(preregistration="unused", output_dir=str(output)),
            prereg_bytes=prereg_bytes,
            prereg=prereg,
        )
        assert exit_code == 2
        assert output.is_dir()
        assert not (_claim_path(runner)).exists()
        abort = runner.strict_json_loads((_abort_path(runner)).read_bytes())
        assert abort["state"] == "blocked_incomplete_initialization"
        assert abort["replay_allowed"] is False
    finally:
        for candidate in prepared:
            candidate.close()


def test_main_keyboard_interrupt_after_claim_seals_failure_complete(
    runner, monkeypatch, tmp_path
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    prereg, prereg_bytes = _install_main_transaction_mocks(runner, monkeypatch, output)

    def interrupt_after_claim(_candidate):
        raise KeyboardInterrupt()

    monkeypatch.setattr(
        runner.PrivateCandidate, "create_source_roots", interrupt_after_claim
    )
    exit_code = runner.main(
        args=Namespace(preregistration="unused", output_dir=str(output)),
        prereg_bytes=prereg_bytes,
        prereg=prereg,
    )

    assert exit_code == 2
    assert (_claim_path(runner)).is_file()
    assert (output / "receipt.json").is_file()
    assert (output / "COMPLETE.json").is_file()
    assert not (_abort_path(runner)).exists()


@pytest.mark.parametrize("mutation_call", [2, 4, 8, 10])
def test_terminal_toolchain_change_at_every_publication_boundary_blocks_pass_egress(
    runner, monkeypatch, tmp_path, mutation_call: int
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    prereg, prereg_bytes = _install_main_transaction_mocks(runner, monkeypatch, output)
    _install_empty_success_path(runner, monkeypatch)
    calls = 0
    baseline = {"final_revalidation_passed": True, "identity": "baseline"}

    def mutable_toolchain():
        nonlocal calls
        calls += 1
        if calls >= mutation_call:
            return {"final_revalidation_passed": True, "identity": "changed"}
        return baseline

    emitted = []
    monkeypatch.setattr(runner, "revalidate_full_phone_toolchain", mutable_toolchain)
    monkeypatch.setattr(
        runner, "emit_committed_receipt", lambda receipt: emitted.append(receipt)
    )
    exit_code = runner.main(
        args=Namespace(preregistration="unused", output_dir=str(output)),
        prereg_bytes=prereg_bytes,
        prereg=prereg,
    )

    assert exit_code != 0
    assert not any(receipt["state"] == "passed_scope" for receipt in emitted)


def test_mutation_during_envelope_disarm_is_caught_before_success_egress(
    runner, monkeypatch, tmp_path
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    prereg, prereg_bytes = _install_main_transaction_mocks(runner, monkeypatch, output)
    _install_empty_success_path(runner, monkeypatch)
    base_envelope = runner.ResourceEnvelope

    class MutatingEnvelope(base_envelope):
        def disarm(self):
            result = super().disarm()
            claim = _claim_path(runner)
            claim.chmod(0o600)
            claim.write_bytes(b'{"forged":true}\n')
            claim.chmod(0o400)
            return result

    emitted = []
    monkeypatch.setattr(runner, "ResourceEnvelope", MutatingEnvelope)
    monkeypatch.setattr(
        runner, "emit_committed_receipt", lambda receipt: emitted.append(receipt)
    )
    exit_code = runner.main(
        args=Namespace(preregistration="unused", output_dir=str(output)),
        prereg_bytes=prereg_bytes,
        prereg=prereg,
    )

    assert exit_code == 4
    assert emitted == []


@pytest.mark.parametrize(
    "signum",
    [signal.SIGINT, signal.SIGTERM]
    + ([signal.SIGHUP] if hasattr(signal, "SIGHUP") else []),
)
@pytest.mark.parametrize("phase", ["before_claim", "after_claim", "terminal"])
def test_main_stop_signal_lifecycle_at_each_transaction_phase(
    runner, monkeypatch, tmp_path, signum, phase
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    prereg, prereg_bytes = _install_main_transaction_mocks(runner, monkeypatch, output)
    handlers, _mask_calls = _install_signal_harness(runner, monkeypatch)

    if phase == "before_claim":

        def stop_before_claim(_candidate):
            handlers[signum](signum, None)

        monkeypatch.setattr(
            runner.PrivateCandidate,
            "publish_execution_claim",
            stop_before_claim,
        )
    elif phase == "after_claim":

        def stop_after_claim(_candidate):
            handlers[signum](signum, None)

        monkeypatch.setattr(
            runner.PrivateCandidate,
            "create_source_roots",
            stop_after_claim,
        )
    elif phase == "terminal":
        monkeypatch.setattr(
            runner,
            "source_contract",
            lambda: {"contract_root_sha256": SHA256, "source_count": 0},
        )
        monkeypatch.setattr(runner, "DIRECT_SOURCES", ())
        monkeypatch.setattr(runner, "GIT_SOURCES", ())
        monkeypatch.setattr(
            runner,
            "build_source_root",
            lambda _artifacts: {
                "source_root_state": "passed_scope",
                "source_root_sha256": SHA256,
            },
        )
        monkeypatch.setattr(
            runner,
            "build_success_receipt",
            lambda **kwargs: _terminal_receipt(
                runner, kwargs["candidate"], state="passed_scope"
            ),
        )
        original_write_receipt = runner.PrivateCandidate.write_receipt

        def stop_during_receipt(candidate, value):
            handlers[signum](signum, None)
            return original_write_receipt(candidate, value)

        monkeypatch.setattr(
            runner.PrivateCandidate,
            "write_receipt",
            stop_during_receipt,
        )
    else:
        raise AssertionError(phase)

    exit_code = runner.main(
        args=Namespace(preregistration="unused", output_dir=str(output)),
        prereg_bytes=prereg_bytes,
        prereg=prereg,
    )

    assert exit_code == 3
    assert handlers[signum] == signal.SIG_DFL
    if phase == "before_claim":
        assert not output.exists()
        assert not (_claim_path(runner)).exists()
        assert not (_abort_path(runner)).exists()
    else:
        assert (_claim_path(runner)).is_file()
        complete = runner.strict_json_loads((output / "COMPLETE.json").read_bytes())
        expected_state = (
            "passed_scope" if phase == "terminal" else "blocked_fail_closed"
        )
        assert complete["state"] == expected_state
        assert not (_abort_path(runner)).exists()


@pytest.mark.parametrize(
    "alarm_phase", ["receipt", "complete_partial", "complete_exact"]
)
def test_hard_alarm_during_terminal_publication_never_creates_false_pass(
    runner, monkeypatch, tmp_path, alarm_phase
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    prereg, prereg_bytes = _install_main_transaction_mocks(runner, monkeypatch, output)
    _install_empty_success_path(runner, monkeypatch)
    events = []
    emitted = []
    base_envelope = runner.ResourceEnvelope

    class TrackingEnvelope(base_envelope):
        def disarm(self):
            events.append("envelope_disarm")
            return super().disarm()

    monkeypatch.setattr(runner, "ResourceEnvelope", TrackingEnvelope)
    monkeypatch.setattr(
        runner, "emit_committed_receipt", lambda receipt: emitted.append(receipt)
    )
    original_abort = runner.PrivateCandidate.write_parent_abort

    def tracked_abort(candidate, **kwargs):
        events.append("parent_abort")
        return original_abort(candidate, **kwargs)

    monkeypatch.setattr(runner.PrivateCandidate, "write_parent_abort", tracked_abort)

    def alarm():
        return runner.OperationalStop(
            "wall_or_lease_alarm_reached", "terminal_evidence_publication"
        )

    if alarm_phase == "receipt":

        def alarm_before_receipt(_candidate, _value):
            events.append("receipt_alarm")
            raise alarm()

        monkeypatch.setattr(
            runner.PrivateCandidate, "write_receipt", alarm_before_receipt
        )
    elif alarm_phase == "complete_partial":

        def alarm_after_partial_complete(candidate, _value):
            events.append("complete_partial_alarm")
            fd = os.open(
                "COMPLETE.json",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o400,
                dir_fd=candidate.directory_fd,
            )
            try:
                os.write(fd, b"{")
                os.fsync(fd)
                os.fchmod(fd, 0o400)
                os.fsync(fd)
            finally:
                os.close(fd)
            os.fsync(candidate.directory_fd)
            raise alarm()

        monkeypatch.setattr(
            runner.PrivateCandidate,
            "write_completion_last",
            alarm_after_partial_complete,
        )
    elif alarm_phase == "complete_exact":
        original_completion = runner.PrivateCandidate.write_completion_last

        def alarm_after_exact_complete(candidate, value):
            original_completion(candidate, value)
            events.append("complete_exact_alarm")
            raise alarm()

        monkeypatch.setattr(
            runner.PrivateCandidate,
            "write_completion_last",
            alarm_after_exact_complete,
        )
    else:
        raise AssertionError(alarm_phase)

    exit_code = runner.main(
        args=Namespace(preregistration="unused", output_dir=str(output)),
        prereg_bytes=prereg_bytes,
        prereg=prereg,
    )

    assert "envelope_disarm" in events
    if alarm_phase == "complete_exact":
        assert exit_code == 0
        assert len(emitted) == 1
        assert emitted[0]["state"] == "passed_scope"
        assert not (_abort_path(runner)).exists()
        complete = runner.strict_json_loads((output / "COMPLETE.json").read_bytes())
        assert complete["state"] == "passed_scope"
        assert events.index("complete_exact_alarm") < events.index("envelope_disarm")
    else:
        assert exit_code == 4
        assert emitted == []
        assert (_abort_path(runner)).is_file()
        assert events.index("parent_abort") < events.index("envelope_disarm")
        if alarm_phase == "receipt":
            assert not (output / "receipt.json").exists()
            assert not (output / "COMPLETE.json").exists()
        else:
            assert (output / "receipt.json").is_file()
            assert (output / "COMPLETE.json").read_bytes() == b"{"


def test_candidate_path_replacement_before_claim_is_detected_and_never_executes(
    runner, monkeypatch, tmp_path
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    candidate = runner.PrivateCandidate.prepare(output, RUN_ID, SHA256, SHA256)
    displaced = output.with_name("candidate-displaced")
    output.rename(displaced)
    output.mkdir(mode=0o700)
    try:
        with pytest.raises(runner.AcquisitionError, match="path_binding_changed"):
            candidate.publish_execution_claim()
        assert candidate.claim_consumed is False
        assert not (_claim_path(runner)).exists()
        with pytest.raises(
            runner.AcquisitionError,
            match="parent_abort_requires_owned_execution_claim",
        ):
            candidate.write_parent_abort(
                blocker="candidate_path_binding_changed",
                checkpoint="before_execution_claim",
                claim_state="not_published",
            )
        assert not (_abort_path(runner)).exists()
    finally:
        candidate.close()


@pytest.mark.parametrize("ancestor", ["candidate_runs", "run_id", "campaign"])
def test_stable_claim_survives_canonical_ancestor_replacement_and_blocks_replay(
    runner, monkeypatch, tmp_path, ancestor: str
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    candidate = _claimed_candidate(runner, output)
    targets = {
        "candidate_runs": output.parent,
        "run_id": output.parent.parent,
        "campaign": output.parent.parent.parent,
    }
    target = targets[ancestor]
    displaced = target.with_name(target.name + "-displaced")
    target.rename(displaced)
    canonical_parent = runner.PHONE_RUN_ROOT / RUN_ID / "candidate_runs"
    canonical_parent.mkdir(parents=True, mode=0o700)
    for path in (
        runner.PHONE_RUN_ROOT,
        runner.PHONE_RUN_ROOT / RUN_ID,
        canonical_parent,
    ):
        path.chmod(0o700)
    try:
        with pytest.raises(
            runner.AcquisitionError,
            match="canonical_directory_chain_changed|path_binding_changed",
        ):
            candidate.revalidate_path_binding()
        with pytest.raises(
            runner.AcquisitionError,
            match="prior_execution_claim_forbids_replay",
        ):
            runner.PrivateCandidate.prepare(output, RUN_ID, SHA256, SHA256)
        assert _claim_path(runner).is_file()
        assert not (canonical_parent / "candidate-001").exists()
    finally:
        candidate.close()


def test_completed_candidate_rejects_later_canonical_parent_replacement(
    runner, monkeypatch, tmp_path
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    candidate = _claimed_candidate(runner, output)
    receipt = _terminal_receipt(runner, candidate)
    envelope = SimpleNamespace(
        lease=SimpleNamespace(max_private_output_bytes=16 * 1024 * 1024),
        check=lambda *_args, **_kwargs: None,
    )
    runner.finalize_candidate(candidate, envelope, RUN_ID, receipt, recheck=False)
    displaced = output.parent.with_name("candidate_runs-displaced")
    output.parent.rename(displaced)
    output.parent.mkdir(mode=0o700)
    try:
        assert candidate.reconcile_exact_completion_if_present() is False
        with pytest.raises(
            runner.AcquisitionError,
            match="prior_execution_claim_forbids_replay",
        ):
            runner.PrivateCandidate.prepare(output, RUN_ID, SHA256, SHA256)
    finally:
        candidate.close()


def test_exact_empty_preclaim_crash_orphan_is_reconciled_without_second_claim(
    runner, monkeypatch, tmp_path
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    output.mkdir(mode=0o700)
    orphan_identity = (output.stat().st_dev, output.stat().st_ino)
    candidate = runner.PrivateCandidate.prepare(output, RUN_ID, SHA256, SHA256)
    try:
        assert (output.stat().st_dev, output.stat().st_ino) == orphan_identity
        candidate.publish_execution_claim()
        assert _claim_path(runner).is_file()
        with pytest.raises(
            runner.AcquisitionError,
            match="prior_execution_claim_forbids_replay",
        ):
            runner.PrivateCandidate.prepare(output, RUN_ID, SHA256, SHA256)
    finally:
        candidate.close()


def test_process_death_after_prepare_is_reconciled_on_restart(
    runner, monkeypatch, tmp_path
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    child = """
import importlib.util
import os
from pathlib import Path
import sys

runner_path, package_root, phone_home, run_root, output, run_id, digest = sys.argv[1:]
spec = importlib.util.spec_from_file_location("cur0s_crash_child", runner_path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
module.PHONE_PACKAGE_ROOT = Path(package_root)
module.PHONE_HOME = Path(phone_home)
module.PHONE_RUN_ROOT = Path(run_root)
module.PrivateCandidate.prepare(Path(output), run_id, digest, digest)
os._exit(0)
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            child,
            str(RUNNER_PATH),
            str(runner.PHONE_PACKAGE_ROOT),
            str(runner.PHONE_HOME),
            str(runner.PHONE_RUN_ROOT),
            str(output),
            RUN_ID,
            SHA256,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert output.is_dir()
    assert not _claim_path(runner).exists()

    candidate = runner.PrivateCandidate.prepare(output, RUN_ID, SHA256, SHA256)
    try:
        candidate.publish_execution_claim()
        assert _claim_path(runner).is_file()
    finally:
        candidate.close()


@pytest.mark.parametrize("orphan", ["nonempty", "symlink", "wrong_mode"])
def test_untrusted_preclaim_orphan_publishes_stable_abort_and_never_replays(
    runner, monkeypatch, tmp_path, orphan: str
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    if orphan == "nonempty":
        output.mkdir(mode=0o700)
        (output / "unexpected").write_bytes(b"x")
    elif orphan == "symlink":
        target = output.with_name("orphan-target")
        target.mkdir(mode=0o700)
        output.symlink_to(target, target_is_directory=True)
    else:
        output.mkdir(mode=0o700)
        output.chmod(0o755)

    with pytest.raises((OSError, runner.AcquisitionError)):
        runner.PrivateCandidate.prepare(output, RUN_ID, SHA256, SHA256)
    abort = runner.strict_json_loads(_abort_path(runner).read_bytes())
    assert abort["state"] == "blocked_incomplete_initialization"
    assert abort["replay_allowed"] is False
    with pytest.raises(
        runner.AcquisitionError,
        match="prior_abort_forbids_execution_claim",
    ):
        runner.PrivateCandidate.prepare(output, RUN_ID, SHA256, SHA256)


def test_postclaim_swap_between_validation_and_use_stays_fd_rooted_and_aborts(
    runner, monkeypatch, tmp_path
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    candidate = _claimed_candidate(runner, output)
    displaced = output.with_name("candidate-held-inode")
    original_revalidate = candidate.revalidate_path_binding
    swapped = False

    def validate_then_swap(*, require_prepared_identity=False):
        nonlocal swapped
        original_revalidate(require_prepared_identity=require_prepared_identity)
        if not swapped:
            output.rename(displaced)
            output.mkdir(mode=0o700)
            swapped = True

    monkeypatch.setattr(candidate, "revalidate_path_binding", validate_then_swap)
    try:
        with pytest.raises(runner.AcquisitionError, match="path_binding_changed"):
            candidate.create_source_roots()
        assert (displaced / "sources/direct").is_dir()
        assert (displaced / "sources/git").is_dir()
        assert list(output.iterdir()) == []
        candidate.write_parent_abort(
            blocker="candidate_path_binding_changed",
            checkpoint="postclaim_fd_root_validation",
        )
        assert (_abort_path(runner)).is_file()
        assert not (displaced / "receipt.json").exists()
        assert not (displaced / "COMPLETE.json").exists()
    finally:
        candidate.close()


def test_immutable_claim_itself_binds_nonreplayable_crash_semantics_and_inode(
    runner, monkeypatch, tmp_path
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    candidate = _claimed_candidate(runner, output)
    try:
        claim = runner.strict_json_loads((_claim_path(runner)).read_bytes())
        assert claim["stable_control_anchor"] == str(runner.PHONE_PACKAGE_ROOT)
        assert claim["execution_claim_filename"] == runner.execution_claim_name(RUN_ID)
        assert claim["replay_allowed"] is False
        assert claim["claim_only_disposition"] == "blocked_incomplete_nonreplayable"
        assert claim["valid_terminal_resolutions"] == [
            "canonical_receipt_bound_COMPLETE_in_candidate",
            "stable_control_anchor_ABORT_without_source_root_pass",
        ]
        identity = claim["candidate_directory_prepared_identity"]
        assert identity["inode"] == output.stat().st_ino
        assert identity["device"] == output.stat().st_dev
        assert identity["mode"] == "0700"
        claim_receipt = candidate.execution_claim_receipt()
        assert claim_receipt["stable_control_anchor"] == str(runner.PHONE_PACKAGE_ROOT)
        assert claim_receipt["malicious_same_UID_tamper_resistance_claimed"] is False
    finally:
        candidate.close()


@pytest.mark.parametrize(
    "fault",
    [
        "open_before",
        "open_after",
        "partial_write",
        "first_file_fsync",
        "hash",
        "chmod",
        "second_file_fsync",
        "entry_validation",
    ],
)
def test_exclusive_writer_rejects_every_preseal_or_identity_fault(
    runner, monkeypatch, tmp_path, fault
) -> None:
    directory_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    original_open = runner.os.open
    original_close = runner.os.close
    original_fsync = runner.os.fsync

    if fault == "open_before":

        def fail_open_before(path, flags, mode=0o777, *, dir_fd=None):
            if path == "artifact.json":
                raise OSError("open_before")
            return original_open(path, flags, mode, dir_fd=dir_fd)

        monkeypatch.setattr(runner.os, "open", fail_open_before)
    elif fault == "open_after":

        def fail_open_after(path, flags, mode=0o777, *, dir_fd=None):
            fd = original_open(path, flags, mode, dir_fd=dir_fd)
            if path == "artifact.json":
                original_close(fd)
                raise OSError("open_after")
            return fd

        monkeypatch.setattr(runner.os, "open", fail_open_after)
    elif fault == "partial_write":

        def partial_write(fd, payload):
            os.write(fd, payload[:1])
            raise OSError("partial_write")

        monkeypatch.setattr(runner, "write_all", partial_write)
    elif fault in {"first_file_fsync", "second_file_fsync"}:
        file_calls = 0

        def fail_selected_file_fsync(fd):
            nonlocal file_calls
            if fd != directory_fd:
                file_calls += 1
                target = 1 if fault == "first_file_fsync" else 2
                if file_calls == target:
                    raise OSError(fault)
            return original_fsync(fd)

        monkeypatch.setattr(runner.os, "fsync", fail_selected_file_fsync)
    elif fault == "hash":
        monkeypatch.setattr(
            runner,
            "hash_fd",
            lambda _fd: (_ for _ in ()).throw(runner.AcquisitionError("hash_fault")),
        )
    elif fault == "chmod":
        monkeypatch.setattr(
            runner.os,
            "fchmod",
            lambda *_args: (_ for _ in ()).throw(OSError("chmod_fault")),
        )
    elif fault == "entry_validation":
        monkeypatch.setattr(
            runner,
            "validate_same_entry",
            lambda *_args: (_ for _ in ()).throw(
                runner.AcquisitionError("entry_validation_fault")
            ),
        )
    else:
        raise AssertionError(fault)

    try:
        with pytest.raises(
            (OSError, runner.AcquisitionError), match="fault|open|write|fsync"
        ):
            runner.write_exclusive_bytes_at(
                directory_fd, "artifact.json", b"payload\n", mode=0o400
            )
    finally:
        original_close(directory_fd)
    if fault == "open_before":
        assert not (tmp_path / "artifact.json").exists()


def test_writer_recovers_close_ambiguity_but_not_persistent_directory_fsync(
    runner, monkeypatch, tmp_path
) -> None:
    close_dir = tmp_path / "close"
    close_dir.mkdir()
    directory_fd = os.open(close_dir, os.O_RDONLY | os.O_DIRECTORY)
    original_close = runner.os.close
    close_failed = False

    def close_then_raise(fd):
        nonlocal close_failed
        if fd != directory_fd and not close_failed:
            close_failed = True
            original_close(fd)
            raise OSError("close_ambiguous")
        return original_close(fd)

    monkeypatch.setattr(runner.os, "close", close_then_raise)
    artifact = runner.write_exclusive_bytes_at(
        directory_fd, "artifact.json", b"payload\n", mode=0o400
    )
    original_close(directory_fd)
    assert close_failed is True
    assert artifact.sha256 == _sha(b"payload\n")

    monkeypatch.setattr(runner.os, "close", original_close)
    fsync_dir = tmp_path / "fsync"
    fsync_dir.mkdir()
    directory_fd = os.open(fsync_dir, os.O_RDONLY | os.O_DIRECTORY)
    original_fsync = runner.os.fsync

    def always_fail_directory_fsync(fd):
        if fd == directory_fd:
            raise OSError("persistent_directory_fsync")
        return original_fsync(fd)

    monkeypatch.setattr(runner.os, "fsync", always_fail_directory_fsync)
    try:
        with pytest.raises(OSError, match="persistent_directory_fsync"):
            runner.write_exclusive_bytes_at(
                directory_fd, "artifact.json", b"payload\n", mode=0o400
            )
        with pytest.raises(FileExistsError):
            runner.write_exclusive_bytes_at(
                directory_fd, "artifact.json", b"payload\n", mode=0o400
            )
    finally:
        original_close(directory_fd)


@pytest.mark.parametrize("budget_delta", [0, -1])
def test_terminal_budget_exact_boundary_and_one_byte_over_fail_closed(
    runner, monkeypatch, tmp_path, budget_delta
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    candidate = _claimed_candidate(runner, output)
    receipt = _terminal_receipt(runner, candidate)
    complete = _terminal_complete(runner, receipt)
    base_usage = 100
    exact_budget = (
        base_usage
        + len(runner.canonical_json_bytes(receipt) + b"\n")
        + len(runner.canonical_json_bytes(complete) + b"\n")
    )
    monkeypatch.setattr(runner, "utc_now", lambda: "2026-07-12T12:00:00Z")
    monkeypatch.setattr(
        runner, "private_tree_usage", lambda _path: (base_usage, base_usage)
    )
    envelope = SimpleNamespace(
        lease=SimpleNamespace(max_private_output_bytes=exact_budget + budget_delta),
        check=lambda *_args, **_kwargs: None,
        disarm=lambda: None,
    )
    try:
        if budget_delta == 0:
            runner.finalize_candidate(candidate, envelope, RUN_ID, receipt)
            assert candidate.completed is True
        else:
            with pytest.raises(
                runner.AcquisitionError, match="terminal_evidence_reserve"
            ):
                runner.finalize_candidate(candidate, envelope, RUN_ID, receipt)
            candidate.write_parent_abort(
                blocker="terminal_evidence_reserve_unavailable",
                checkpoint="terminal_evidence_publication",
            )
            assert not (output / "receipt.json").exists()
            assert (_abort_path(runner)).is_file()
    finally:
        candidate.close()


def test_malformed_canonical_terminal_pair_is_not_adopted_and_allows_abort(
    runner, monkeypatch, tmp_path
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    candidate = _claimed_candidate(runner, output)
    expected_receipt = _terminal_receipt(runner, candidate)
    expected_complete = _terminal_complete(runner, expected_receipt)
    candidate.bind_expected_terminal(expected_receipt, expected_complete)
    wrong_receipt = dict(expected_receipt)
    wrong_receipt["unexpected"] = True
    wrong_receipt.pop("receipt_root_sha256")
    wrong_receipt["receipt_root_sha256"] = runner.canonical_sha256(wrong_receipt)
    wrong_complete = _terminal_complete(runner, wrong_receipt)
    runner.write_exclusive_bytes_at(
        candidate.directory_fd,
        "receipt.json",
        runner.canonical_json_bytes(wrong_receipt) + b"\n",
        mode=0o400,
    )
    runner.write_exclusive_bytes_at(
        candidate.directory_fd,
        "COMPLETE.json",
        runner.canonical_json_bytes(wrong_complete) + b"\n",
        mode=0o400,
    )
    try:
        assert candidate.reconcile_exact_completion_if_present() is False
        candidate.write_parent_abort(
            blocker="malformed_terminal_pair",
            checkpoint="terminal_evidence_publication",
        )
        assert (_abort_path(runner)).is_file()
    finally:
        candidate.close()


def test_resource_alarm_reserves_terminalization_and_hard_deadline_remains_active(
    runner, monkeypatch, tmp_path
) -> None:
    now = datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc)
    monotonic = [0.0]
    wall_clock = [now]
    candidate_fd = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
    candidate = SimpleNamespace(
        path=tmp_path,
        bound_path=tmp_path,
        directory_fd=candidate_fd,
        revalidate_path_binding=lambda: None,
    )
    envelope = runner.ResourceEnvelope(
        _lease(runner, now),
        candidate,
        0.0,
        now_fn=lambda: wall_clock[0],
        monotonic_fn=lambda: monotonic[0],
        thermal_reader=lambda: _thermal_sample(runner),
        statvfs_fn=lambda _fd: SimpleNamespace(f_bavail=10_737_418_240, f_frsize=1),
    )
    timers = []
    monkeypatch.setattr(runner.signal, "getsignal", lambda _signum: signal.SIG_DFL)
    monkeypatch.setattr(runner.signal, "signal", lambda *_args: None)
    monkeypatch.setattr(
        runner.signal,
        "setitimer",
        lambda _which, duration: timers.append(duration),
    )
    try:
        envelope.arm()
        assert timers[-1] == 7170
        monotonic[0] = 7169
        wall_clock[0] = now + timedelta(seconds=7169)
        envelope.check("before_reserve", force_thermal=True)
        envelope.begin_terminalization("terminal")
        assert timers[-1] == 31
        monotonic[0] = 7199
        wall_clock[0] = now + timedelta(seconds=7199)
        envelope.check("hard_boundary", force_thermal=True)
        with pytest.raises(runner.OperationalStop, match="wall_time"):
            monotonic[0] = 7200
            wall_clock[0] = now + timedelta(seconds=7200)
            envelope.check("expired", force_thermal=True)
    finally:
        envelope.disarm()
        os.close(candidate_fd)


def test_real_candidate_fd_root_supports_envelope_scan_and_finalization(
    runner, monkeypatch, tmp_path
) -> None:
    output = _make_candidate_path(tmp_path, runner, monkeypatch)
    candidate = _claimed_candidate(runner, output)
    now = datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc)
    envelope = runner.ResourceEnvelope(
        _lease(runner, now),
        candidate,
        0.0,
        now_fn=lambda: now,
        monotonic_fn=lambda: 0.0,
        thermal_reader=lambda: _thermal_sample(runner),
        statvfs_fn=lambda _fd: SimpleNamespace(f_bavail=20_000_000_000, f_frsize=1),
    )
    receipt = _terminal_receipt(runner, candidate)
    try:
        assert candidate.bound_path != output
        assert (
            candidate.bound_path.stat().st_ino
            == os.fstat(candidate.directory_fd).st_ino
        )
        envelope.check("real_fd_root", force_thermal=True)
        runner.finalize_candidate(candidate, envelope, RUN_ID, receipt)
        assert candidate.completed is True
        assert (output / "receipt.json").is_file()
        assert (output / "COMPLETE.json").is_file()
    finally:
        envelope.disarm()
        candidate.close()


def test_resource_envelope_enforces_exact_thermal_free_space_output_and_time(
    runner, tmp_path
) -> None:
    now = datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc)
    cases = [
        ({"temperatures": [85_000]}, "thermal_ceiling"),
        ({"free_bytes": 10_737_418_239}, "free_storage_floor"),
        (
            {"max_private_output_bytes": runner.CONTROL_RESERVE_BYTES - 1},
            "private_output_budget",
        ),
    ]
    for kwargs, message in cases:
        envelope, fd = _envelope(runner, tmp_path, now=now, **kwargs)
        try:
            with pytest.raises(runner.OperationalStop, match=message):
                envelope.check("boundary", force_thermal=True)
        finally:
            os.close(fd)

    monotonic = [7200.0]
    envelope, fd = _envelope(runner, tmp_path, now=now, monotonic=monotonic)
    try:
        with pytest.raises(runner.OperationalStop, match="wall_time"):
            envelope.check("boundary")
    finally:
        os.close(fd)


def test_terminal_timestamps_are_explicit_snapshots_not_false_finish_claims(
    runner, monkeypatch
) -> None:
    monotonic = iter((112.5,))
    monkeypatch.setattr(runner.time, "monotonic", lambda: next(monotonic))
    snapshot = runner.execution_snapshot("2026-07-12T12:00:00Z", 100.0)
    assert snapshot["elapsed_seconds_at_snapshot"] == 12.5
    assert "finished_at_utc" not in snapshot
    assert "elapsed_seconds" not in snapshot
    complete = _terminal_complete(
        runner,
        {
            "state": "blocked_fail_closed",
            "receipt_root_sha256": SHA256,
        },
    )
    assert "completion_marker_prepared_at_utc" in complete
    assert "completed_at_utc" not in complete


def test_unlinked_control_files_are_hard_capped_and_counted_in_output_budget(
    runner, tmp_path
) -> None:
    now = datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc)
    envelope, directory_fd = _envelope(
        runner,
        tmp_path,
        now=now,
        max_private_output_bytes=runner.CONTROL_RESERVE_BYTES + 4,
    )
    with tempfile.TemporaryFile(dir=tmp_path) as control:
        envelope.register_ephemeral_control(
            control.fileno(), limit=16, role="fixture_control"
        )
        try:
            control.write(b"12345")
            control.flush()
            with pytest.raises(runner.OperationalStop, match="private_output_budget"):
                envelope.check("ephemeral_budget", force_thermal=True)
        finally:
            envelope.unregister_ephemeral_control(control.fileno())
    os.close(directory_fd)

    envelope, directory_fd = _envelope(runner, tmp_path, now=now)
    with tempfile.TemporaryFile(dir=tmp_path) as control:
        envelope.register_ephemeral_control(
            control.fileno(), limit=4, role="fixture_control"
        )
        try:
            control.write(b"12345")
            control.flush()
            with pytest.raises(
                runner.AcquisitionError, match="ephemeral_control_size_limit"
            ):
                envelope.check("ephemeral_limit", force_thermal=True)
        finally:
            envelope.unregister_ephemeral_control(control.fileno())
    os.close(directory_fd)


def test_preclaim_reserves_full_payload_and_requires_live_thermal_sensor(
    runner, monkeypatch, tmp_path
) -> None:
    now = datetime.now(timezone.utc)
    lease = _lease(runner, now, max_private_output_bytes=2_147_483_648)
    required_payload = sum(
        source.expected_bytes for source in runner.DIRECT_SOURCES
    ) + sum(source.selected_bytes for source in runner.GIT_SOURCES)
    required = (
        lease.min_free_storage_bytes
        + required_payload
        + 512 * 1024 * 1024
        + runner.CONTROL_RESERVE_BYTES
    )
    monkeypatch.setattr(
        runner.os,
        "statvfs",
        lambda _path: SimpleNamespace(f_bavail=required - 1, f_frsize=1),
    )
    monkeypatch.setattr(runner, "read_thermal_zones", lambda: _thermal_sample(runner))
    with pytest.raises(runner.OperationalStop, match="insufficient_free_storage"):
        runner.preclaim_resource_check(tmp_path, lease, runner.time.monotonic())

    monkeypatch.setattr(
        runner.os,
        "statvfs",
        lambda _path: SimpleNamespace(f_bavail=required, f_frsize=1),
    )
    monkeypatch.setattr(runner, "read_thermal_zones", lambda: None)
    with pytest.raises(runner.OperationalStop, match="thermal_sample_shape_invalid"):
        runner.preclaim_resource_check(tmp_path, lease, runner.time.monotonic())


def test_thermal_reader_treats_both_preregistered_sentinels_as_unavailable(
    runner, monkeypatch
) -> None:
    monkeypatch.setattr(runner.os, "read", lambda _fd, _size: b"-273000\n")
    assert runner.read_thermal_value(1) is None
    monkeypatch.setattr(runner.os, "read", lambda _fd, _size: b"-40960\n")
    assert runner.read_thermal_value(1) is None
    monkeypatch.setattr(runner.os, "read", lambda _fd, _size: b"85000\n")
    assert runner.read_thermal_value(1) == 85_000
    monkeypatch.setattr(runner.os, "read", lambda _fd, _size: b"24\n")
    with pytest.raises(runner.OperationalStop, match="unit_or_value_shape"):
        runner.read_thermal_value(1)
    monkeypatch.setattr(runner.os, "read", lambda _fd, _size: b"malformed\n")
    with pytest.raises(runner.OperationalStop, match="malformed"):
        runner.read_thermal_value(1)

    def unreadable(_fd, _size):
        raise OSError("volatile sysfs read")

    monkeypatch.setattr(runner.os, "read", unreadable)
    with pytest.raises(runner.OperationalStop, match="value_unreadable"):
        runner.read_thermal_value(1)


def _thermal_observations(runner):
    contract = runner.phone_thermal_safety_contract()
    excluded = set(contract["excluded_non_temperature_sensor_types"])
    return contract, [
        (
            zone_name,
            sensor_type,
            None if sensor_type in excluded else 40_000,
            sensor_type not in excluded,
        )
        for zone_name, sensor_type in contract["zone_type_roster"].items()
    ]


def test_thermal_contract_excludes_false_low_nonthermal_values(runner) -> None:
    contract, observations = _thermal_observations(runner)
    socd_index = next(
        index
        for index, observation in enumerate(observations)
        if observation[1] == "socd"
    )
    zone_name, sensor_type, _value, _read = observations[socd_index]
    observations[socd_index] = (zone_name, sensor_type, 24, True)
    with pytest.raises(runner.OperationalStop, match="non_temperature"):
        runner.assemble_thermal_sample(observations, contract)


def test_thermal_contract_rejects_missing_group_type_swap_and_duplicate(runner) -> None:
    with pytest.raises(runner.OperationalStop, match="group_sensor_unavailable:gpu"):
        _thermal_sample(runner, unavailable_groups=frozenset({"gpu"}))

    contract, observations = _thermal_observations(runner)
    first = observations[0]
    second = observations[2]
    observations[0] = (first[0], second[1], first[2], first[3])
    observations[2] = (second[0], first[1], second[2], second[3])
    with pytest.raises(runner.OperationalStop, match="type_swap"):
        runner.assemble_thermal_sample(observations, contract)

    contract, observations = _thermal_observations(runner)
    first = observations[0]
    second = observations[2]
    observations[2] = (second[0], first[1], second[2], second[3])
    with pytest.raises(runner.OperationalStop, match="type_duplicate"):
        runner.assemble_thermal_sample(observations, contract)


def test_thermal_contract_enforces_each_group_ceiling_and_reports_types(
    runner, tmp_path
) -> None:
    now = datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc)
    envelope, fd = _envelope(runner, tmp_path, now=now)
    envelope._thermal_reader = lambda: _thermal_sample(
        runner,
        group_values={"battery_usb": 45_000},
    )
    try:
        with pytest.raises(
            runner.OperationalStop,
            match="thermal_ceiling_reached:battery_usb",
        ):
            envelope.check("battery_boundary", force_thermal=True)
        stopped_metrics = envelope.receipt_metrics()
        assert stopped_metrics["thermal_sample_count"] == 1
        assert (
            stopped_metrics["maximum_observed_thermal_group_millidegrees_c"][
                "battery_usb"
            ]
            == 45_000
        )
    finally:
        os.close(fd)

    envelope, fd = _envelope(runner, tmp_path, now=now)
    try:
        envelope.check("report", force_thermal=True)
        metrics = envelope.receipt_metrics()
        assert metrics["maximum_observed_thermal_group_millidegrees_c"] == {
            group: 40_000
            for group in runner.phone_thermal_safety_contract()["sensor_types_by_group"]
        }
        assert (
            metrics["observed_thermal_sensor_types_by_group"]
            == (runner.phone_thermal_safety_contract()["sensor_types_by_group"])
        )
    finally:
        os.close(fd)


class _ReceiptCandidate:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.bound_path = path
        self.directory_fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)

    def __del__(self):
        if getattr(self, "directory_fd", -1) >= 0:
            os.close(self.directory_fd)
            self.directory_fd = -1

    def execution_claim_receipt(self) -> dict[str, Any]:
        return {
            "state": "claimed_terminal_pending_once_O_EXCL",
            "claim_sha256": SHA256,
            "claim_bytes": 1,
            "claim_egressed": False,
            "claim_is_crash_anchor": True,
            "claim_only_state_is_blocked_and_never_replayable": True,
        }

    def revalidate_path_binding(self) -> None:
        return None


class _ReceiptEnvelope:
    def receipt_metrics(self) -> dict[str, Any]:
        return {
            "action_id": RUN_ID,
            "phone_execution_ordinal": 1,
            "maximum_observed_temperature_millidegrees_c": 40_000,
        }


def test_success_and_failure_receipts_are_hash_bound_and_never_overclaim(
    runner, tmp_path
) -> None:
    prereg = _receipt_prereg(runner)
    prereg_bytes = runner.canonical_json_bytes(prereg) + b"\n"
    candidate = _ReceiptCandidate(tmp_path)
    envelope = _ReceiptEnvelope()
    success = runner.build_success_receipt(
        prereg=prereg,
        prereg_bytes=prereg_bytes,
        source_execution_identity={"preimport_source_bytes_verified": True},
        runtime_identity={"phone_private_runtime_guard_passed": True},
        source_root={"source_root_state": "passed_scope", "source_root_sha256": SHA256},
        inspection_summaries=[],
        candidate=candidate,
        envelope=envelope,
        started_at="2026-07-12T12:00:00Z",
        started_monotonic=runner.time.monotonic(),
    )
    failure = runner.build_failure_receipt(
        prereg=prereg,
        prereg_bytes=prereg_bytes,
        source_execution_identity={"preimport_source_bytes_verified": True},
        runtime_identity={"phone_private_runtime_guard_passed": True},
        acquired_artifacts=[],
        inspection_summaries=[],
        active_source_id="wordnet_3_0",
        blocker="direct_etag_mismatch:wordnet_3_0",
        blocker_class="source_gate_failure",
        checkpoint="source_acquisition",
        candidate=candidate,
        envelope=envelope,
        started_at="2026-07-12T12:00:00Z",
        started_monotonic=runner.time.monotonic(),
    )

    assert success["state"] == "passed_scope"
    assert success["first_next_blocker"] == "private_C4_COM_mirror"
    assert failure["state"] == "blocked_fail_closed"
    assert failure["source_root_state"] == "not_claimed"
    assert failure["all_source_identity_and_rights_gates_passed"] is False
    for receipt in (success, failure):
        root = receipt.pop("receipt_root_sha256")
        assert root == runner.canonical_sha256(receipt)
        for field in (
            "semantic_rows_compiled",
            "near_semantic_arm_C_executed",
            "connected_split_assigned",
            "cur0s_static_pass_claimed",
            "cur0s_pass_claimed",
            "composite_cur0_pass_claimed",
            "target_data_learning_claimed",
            "authority_claimed",
            "private_HF_mirror_completed",
            "c4_rx_content_present",
        ):
            assert receipt[field] is False
