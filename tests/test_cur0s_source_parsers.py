"""Focused safety and normalization tests for CUR-0S source parsers."""

from __future__ import annotations

import hashlib
from io import BytesIO
import inspect
import json
import os
from pathlib import Path
import shutil
import stat
import tarfile
from dataclasses import replace
from types import SimpleNamespace
from typing import Any
import zipfile

import pytest

from polymath_ai.corpus import cur0s_commercial_sources as commercial
from polymath_ai.corpus import cur0s_source_parsers as parsers


def _context(source_id: str = "fixture") -> parsers.ParseContext:
    return parsers.ParseContext(
        source_id=source_id,
        release_identity="fixture_release_v1",
        source_sha256="sha256:" + "1" * 64,
        source_locator="phone_private/cur0s/fixture",
        license_id="CC-BY-4.0",
        license_class="B",
        rights_proof="fixture_embedded_license",
    )


def _file_context(path: Path, source_id: str) -> parsers.ParseContext:
    return parsers.ParseContext(
        **{
            **_context(source_id).__dict__,
            "source_sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
            "source_locator": path.name,
        }
    )


def _tree_context(root: Path, source_id: str = "openstax") -> parsers.ParseContext:
    files = []
    for path in sorted(
        candidate for candidate in root.rglob("*") if candidate.is_file()
    ):
        relative = path.relative_to(root).as_posix()
        payload = path.read_bytes()
        files.append(
            {
                "relative_path": relative,
                "bytes": len(payload),
                "sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
            }
        )
    manifest = {
        "schema_version": "cur0s_git_sparse_content_manifest_v1",
        "commit_sha": "a" * 40,
        "tree_sha": "b" * 40,
        "files": files,
    }
    manifest_json = json.dumps(
        manifest,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return parsers.ParseContext(
        **{
            **_context(source_id).__dict__,
            "source_sha256": "sha256:"
            + hashlib.sha256(manifest_json.encode("utf-8")).hexdigest(),
            "source_locator": root.name,
            "source_manifest_json": manifest_json,
        }
    )


def _write_zip(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in members.items():
            if name == "mimetype":
                info = zipfile.ZipInfo(name)
                info.compress_type = zipfile.ZIP_STORED
                archive.writestr(info, value)
            else:
                archive.writestr(name, value)


def _add_tar_bytes(archive: tarfile.TarFile, name: str, value: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(value)
    archive.addfile(info, BytesIO(value))


def _wordnet_members() -> dict[str, bytes]:
    return {
        "WordNet-3.0/dict/data.noun": (
            b"00001740 03 n 01 entity 0 000 | that which is perceived\n"
            b"00001930 03 n 01 physical_entity 0 001 @ 00001740 n 0000 | "
            b"an entity with 2 dimensions\n"
        ),
        "WordNet-3.0/dict/index.noun": (
            b"entity n 1 0 1 1 00001740\nphysical_entity n 1 1 @ 1 1 00001930\n"
        ),
        "WordNet-3.0/dict/data.verb": (
            b"00003000 00 v 01 act 0 000 00 | perform 1 action\n"
        ),
        "WordNet-3.0/dict/index.verb": b"act v 1 0 1 1 00003000\n",
        "WordNet-3.0/dict/data.adj": b"00004000 00 a 01 good 0 000 | having merit\n",
        "WordNet-3.0/dict/index.adj": b"good a 1 0 1 1 00004000\n",
        "WordNet-3.0/dict/data.adv": b"00005000 00 r 01 well 0 000 | in a good way\n",
        "WordNet-3.0/dict/index.adv": b"well r 1 0 1 1 00005000\n",
    }


def _write_wordnet(path: Path, extra: Any = None) -> None:
    with tarfile.open(path, "w:gz") as archive:
        for name, value in _wordnet_members().items():
            _add_tar_bytes(archive, name, value)
        if extra is not None:
            archive.addfile(extra)


def _write_canonical_read_only(path: Path, value: dict[str, Any]) -> bytes:
    payload = (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )
    path.write_bytes(payload)
    path.chmod(0o400)
    return payload


def _write_canonical_private(
    path: Path,
    value: dict[str, Any],
    *,
    trailing_newline: bool = True,
) -> bytes:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if trailing_newline:
        payload += b"\n"
    path.write_bytes(payload)
    path.chmod(0o600)
    return payload


def _git_binding(payload: bytes) -> dict[str, Any]:
    header = f"blob {len(payload)}\0".encode("ascii")
    return {
        "bytes": len(payload),
        "sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
        "git_blob_oid": hashlib.sha1(
            header + payload,
            usedforsecurity=False,
        ).hexdigest(),
    }


def _dynamic_build_python_fixture(
    commercial: Any,
    run_id: str,
    source_commit: str,
) -> dict[str, Any]:
    base = commercial.native_preflight_build_python_runtime_identity()
    layout = commercial.native_preflight_execution_layout(run_id, source_commit)
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
        run_id,
        "--source-commit",
        source_commit,
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
        "run_id": run_id,
        "source_commit": source_commit,
        "sys_argv": orig_argv[4:],
        "sys_xoptions": {"pycache_prefix": pycache},
    }
    return {
        **body,
        "python_runtime_root_sha256": commercial.canonical_sha256(body),
    }


def _dynamic_build_tool_fixture(
    commercial: Any,
    compiler: dict[str, Any],
    linker: dict[str, Any],
) -> dict[str, Any]:
    inputs = commercial.NATIVE_PREFLIGHT_BUILD_TOOL_RUNTIME_INPUTS

    def held(role: str, identity: dict[str, Any], inode: int) -> dict[str, Any]:
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
    for tool_index, (tool_role, identity) in enumerate(
        (("compiler", compiler), ("linker", linker)),
        start=1,
    ):
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
        resolution = {
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
            "stderr_sha256": (
                "sha256:e3b0c44298fc1c149afbf4c8996fb924"
                "27ae41e4649b934ca495991b7852b855"
            ),
            "target": held(tool_role, identity, 10 + tool_index),
        }
        tools[tool_role] = {
            **resolution,
            "resolution_root_sha256": commercial.canonical_sha256(resolution),
        }
    actual = {
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
            **actual,
            "actual_loader_resolution_root_sha256": (
                commercial.canonical_sha256(actual)
            ),
        },
    }


def _native_build_receipt_fixture(
    commercial: Any,
    run_id: str,
    source_commit: str,
    native_source_bindings: dict[str, dict[str, Any]],
    binary_payload: bytes,
    owner_uid: int,
    owner_gid: int,
) -> dict[str, Any]:
    empty_sha = "sha256:" + hashlib.sha256(b"").hexdigest()
    common_tool = {
        "literal_entry_type": "symbolic_link",
        "literal_mode": "0777",
        "literal_uid": owner_uid,
        "literal_gid": owner_gid,
        "literal_nlink": 1,
        "resolved_entry_type": "regular_file",
        "resolved_mode": "0700",
        "resolved_uid": owner_uid,
        "resolved_gid": owner_gid,
        "resolved_nlink": 1,
        "version_returncode": 0,
        "version_stderr_bytes": 0,
        "version_stderr_sha256": empty_sha,
    }
    compiler = {
        **common_tool,
        "literal_path": "/data/data/com.termux/files/usr/bin/clang",
        "literal_symlink_target": "clang-21",
        "resolved_path": "/data/data/com.termux/files/usr/bin/clang-21",
        "sha256": "sha256:34da8e3a9b71793eb70c25670e1fe2bce4d37f1e2837ba8dc0c516c2ca0ffc83",
        "bytes": 120_848,
        "version_argv_suffix": ["--version"],
        "version_stdout_bytes": 109,
        "version_stdout_sha256": "sha256:fe40f61ef08c80c802452d327052739a0a57b31366d8eabdc694a15b8df98f94",
    }
    linker = {
        **common_tool,
        "literal_path": "/data/data/com.termux/files/usr/bin/ld.lld",
        "literal_symlink_target": "lld",
        "resolved_path": "/data/data/com.termux/files/usr/bin/lld",
        "sha256": "sha256:5214b9511221a87e02c4a9603f470dd83804a54f4cf62475f168d47d707d964d",
        "bytes": 5_615_720,
        "version_argv_suffix": ["-flavor", "gnu", "--version"],
        "version_stdout_bytes": 41,
        "version_stdout_sha256": "sha256:418d72df86baf70c88b9a96a9118e3cdc66be0537a58f66a6879df0479f9a78f",
    }
    binary_digest = {
        "bytes": len(binary_payload),
        "sha256": "sha256:" + hashlib.sha256(binary_payload).hexdigest(),
    }
    closure_body = {
        "schema_version": commercial.NATIVE_PREFLIGHT_TOOLCHAIN_CLOSURE_SCHEMA,
        "compiled_source_execution": "held_source_fds",
        "compiler_execution": "held_compiler_fd",
        "default_clang_configuration": {
            "disabled": True,
            "flag": "--no-default-config",
        },
        "header_resolution": "private_symlink_to_held_header_fd",
        "include_trees": commercial.NATIVE_PREFLIGHT_BUILD_INCLUDE_TREES,
        "input_closure_scope": (
            "all_file_backed_build_inputs_and_current_process_executable_mappings"
        ),
        "kernel_and_process_boundary": {
            "kernel_vdso": "observed_executable_mapping_without_file_backing",
            "pre_exec_process_provenance": "outside_file_input_closure_claim",
        },
        "link_inputs": commercial.NATIVE_PREFLIGHT_BUILD_LINK_INPUTS,
        "linker_execution": "direct_held_linker_fd",
        "python_runtime": _dynamic_build_python_fixture(
            commercial,
            run_id,
            source_commit,
        ),
        "tool_execution_runtime": _dynamic_build_tool_fixture(
            commercial,
            compiler,
            linker,
        ),
        "unmeasured_inputs_allowed": False,
        "unmeasured_inputs_allowed_scope": "within_input_closure_scope",
    }
    closure = {
        **closure_body,
        "closure_root_sha256": commercial.canonical_sha256(closure_body),
    }
    object_digests = {
        "cur0s_native_preflight": {
            "bytes": 2048,
            "sha256": "sha256:" + hashlib.sha256(b"native-object").hexdigest(),
        },
        "cur0s_sha256": {
            "bytes": 1024,
            "sha256": "sha256:" + hashlib.sha256(b"sha-object").hexdigest(),
        },
    }
    body = {
        "schema_version": commercial.NATIVE_PREFLIGHT_BUILD_SCHEMA,
        "run_id": run_id,
        "source_commit": source_commit,
        "source_commit_binding_status": (
            commercial.NATIVE_PREFLIGHT_SOURCE_COMMIT_BINDING_STATUS
        ),
        "source_file_bindings": native_source_bindings,
        "intended_target": {
            "architecture": "aarch64",
            "compiler_target": "aarch64-linux-android30",
            "runtime_device_and_soc_gate": "not_claimed_by_build_receipt",
        },
        "build_principal": {"gid": owner_gid, "uid": owner_uid},
        "compiler_identity": compiler,
        "linker_identity": linker,
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
            "build_one": object_digests,
            "build_two": {role: dict(value) for role, value in object_digests.items()},
            "deterministic_match": True,
        },
        "binary_identity": {
            **binary_digest,
            "mode": "0700",
            "uid": owner_uid,
            "gid": owner_gid,
            "nlink": 1,
        },
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
        "security_ceiling": commercial.NATIVE_PREFLIGHT_SECURITY_CEILING,
    }
    return {**body, "build_receipt_root_sha256": commercial.canonical_sha256(body)}


def _rewrite_candidate_receipt(
    candidate: Path,
    field: str,
    replacement: Any,
) -> None:
    from polymath_ai.corpus import cur0s_commercial_sources as commercial

    receipt_path = candidate / "receipt.json"
    complete_path = candidate / "COMPLETE.json"
    receipt_path.chmod(0o600)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt[field] = replacement
    receipt.pop("receipt_root_sha256")
    receipt["receipt_root_sha256"] = commercial.canonical_sha256(receipt)
    receipt_payload = _write_canonical_read_only(receipt_path, receipt)
    complete_path.chmod(0o600)
    complete = json.loads(complete_path.read_text(encoding="utf-8"))
    complete["receipt_sha256"] = "sha256:" + hashlib.sha256(receipt_payload).hexdigest()
    complete["receipt_root_sha256"] = receipt["receipt_root_sha256"]
    complete["receipt_bytes"] = len(receipt_payload)
    _write_canonical_read_only(complete_path, complete)


def _expect_current_receipt(
    candidate: Path,
    expected: parsers.ProductionAuthorityExpectation,
) -> parsers.ProductionAuthorityExpectation:
    return parsers.ProductionAuthorityExpectation(
        preregistration_sha256=expected.preregistration_sha256,
        acquisition_receipt_sha256="sha256:"
        + hashlib.sha256((candidate / "receipt.json").read_bytes()).hexdigest(),
    )


def _production_obo_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[
    Path,
    Any,
    parsers.ParseContext,
    parsers.ProductionAuthorityExpectation,
]:
    from polymath_ai.corpus import cur0s_commercial_sources as commercial

    source_id = "fixture_obo"
    run_id = "20260712T120000Z_cur0s_commercial_sources_v1"
    payload = b'[Term]\nid: X:1\nname: exact\ndef: "bound definition" []\n'
    package_root = tmp_path / "data" / "data" / "com.termux"
    phone_home = package_root / "files" / "home"
    phone_run_root = phone_home / "polymath_gemma4_e4b_frontier"
    candidate = phone_run_root / run_id / "candidate_runs" / "candidate-001"
    candidate.mkdir(parents=True)
    package_root.chmod(0o700)
    (package_root / "files").chmod(0o771)
    phone_home.chmod(0o700)
    phone_run_root.chmod(0o700)
    (phone_run_root / run_id).chmod(0o700)
    candidate.parent.chmod(0o700)
    candidate.chmod(0o700)
    prepared = candidate.stat()
    monkeypatch.setattr(parsers, "PHONE_PACKAGE_ROOT", package_root)
    monkeypatch.setattr(parsers, "PHONE_HOME", phone_home)
    monkeypatch.setattr(parsers, "PHONE_RUN_ROOT", phone_run_root)
    monkeypatch.setattr(commercial, "PHONE_APP_UID", os.getuid())
    monkeypatch.setattr(commercial, "PHONE_APP_GID", os.getgid())
    source_dir = candidate / f"sources/direct/{source_id}"
    source_dir.mkdir(parents=True)
    source_path = source_dir / "fixture.obo"
    source_path.write_bytes(payload)
    digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    spec = commercial.DirectSourceSpec(
        source_id=source_id,
        stages=("C3",),
        url="https://example.test/fixture.obo",
        filename="fixture.obo",
        media_type="text/obo",
        expected_bytes=len(payload),
        expected_etag='"fixture"',
        expected_last_modified=None,
        release_identity="fixture_release_v1",
        license_id="CC-BY-4.0",
        license_class="B",
        rights_proof="exact_fixture_rights",
        required_markers=("bound definition",),
        selection_filter="all_terms",
        expected_sha256=digest.removeprefix("sha256:"),
        transfer_mode="fixed_range_chunks_v1",
        fixed_chunk_bytes=8_388_608,
    )
    locator = f"sources/direct/{source_id}/fixture.obo"
    artifact = {
        "source_id": source_id,
        "acquisition_mode": "https_file",
        "release_identity": spec.release_identity,
        "stages": ["C3"],
        "license_id": spec.license_id,
        "license_class": spec.license_class,
        "rights_proof": spec.rights_proof,
        "bytes": len(payload),
        "sha256": digest,
        "local_locator": locator,
        "content_manifest": {
            "schema_version": "cur0s_direct_content_manifest_v1",
            "files": [
                {
                    "relative_path": locator,
                    "bytes": len(payload),
                    "sha256": digest,
                }
            ],
        },
        "verification": {},
    }
    contract_body = {
        "schema_version": "cur0s_commercial_source_contract_v1",
        "source_count": 1,
        "preregistration_eligibility": {
            "eligible": True,
            "selection_critical_identity_blockers": [],
        },
    }
    contract = {
        **contract_body,
        "contract_root_sha256": commercial.canonical_sha256(contract_body),
    }
    source_root_body = {
        "schema_version": "cur0s_commercial_source_root_v1",
        "lane": "C4-COM",
        "contract_root_sha256": contract["contract_root_sha256"],
        "artifacts": [artifact],
        "source_artifact_count": 1,
        "hard_rejects": [],
        "stage_source_ids": {
            "C1": [],
            "C2": [],
            "B23": [],
            "C3": [source_id],
            "C4": [],
        },
        "rights_classes": ["B"],
        "raw_source_custody": "phone_private",
        "source_root_state": "passed_scope",
        "all_source_identity_and_rights_gates_passed": True,
        "private_HF_mirror_completed": False,
        "c4_rx_content_present": False,
        "first_next_blocker": "private_C4_COM_mirror",
        "semantic_rows_compiled": False,
        "near_semantic_arm_C_executed": False,
        "connected_split_assigned": False,
        "cur0s_static_pass_claimed": False,
        "target_data_learning_claimed": False,
        "authority_claimed": False,
    }
    source_root = {
        **source_root_body,
        "source_root_sha256": commercial.canonical_sha256(source_root_body),
    }
    monkeypatch.setattr(commercial, "DIRECT_SOURCES", (spec,))
    monkeypatch.setattr(commercial, "GIT_SOURCES", ())
    monkeypatch.setattr(commercial, "source_contract", lambda: contract)
    monkeypatch.setattr(
        commercial,
        "build_source_root",
        lambda artifacts: source_root if artifacts == [artifact] else None,
    )
    toolchain_contract = commercial.phone_toolchain_contract()
    action_root = phone_run_root / run_id
    source_commit = "2" * 40
    checkout = action_root / "source" / f"Polymath-AI-{source_commit}"
    checkout.mkdir(parents=True)
    (action_root / "source").chmod(0o700)
    checkout.chmod(0o700)
    git_directory = checkout / ".git"
    git_directory.mkdir(mode=0o700)
    head_path = git_directory / "HEAD"
    head_path.write_text(source_commit + "\n", encoding="ascii")
    head_path.chmod(0o600)

    source_file_bindings: dict[str, dict[str, Any]] = {}
    source_file_sha256: dict[str, str] = {}
    for index, relative in enumerate(parsers.BOUND_SOURCE_FILES, start=1):
        code_payload = f"bound production source {index}\n".encode()
        code_path = checkout / relative
        code_path.parent.mkdir(parents=True, exist_ok=True)
        for parent in code_path.parents:
            if parent == checkout:
                break
            parent.chmod(0o700)
        code_path.write_bytes(code_payload)
        code_path.chmod(0o600)
        binding = _git_binding(code_payload)
        source_file_bindings[relative] = binding
        hash_name = "commercial_sources_sha256" if index == 1 else "runner_sha256"
        source_file_sha256[hash_name] = binding["sha256"]

    native_source_bindings: dict[str, dict[str, Any]] = {}
    for index, relative in enumerate(commercial.NATIVE_PREFLIGHT_SOURCE_FILES, start=1):
        if relative in source_file_bindings:
            native_source_bindings[relative] = dict(source_file_bindings[relative])
            continue
        native_payload = f"native source {index}\n".encode()
        native_path = checkout / relative
        native_path.parent.mkdir(parents=True, exist_ok=True)
        for parent in native_path.parents:
            if parent == checkout:
                break
            parent.chmod(0o700)
        native_path.write_bytes(native_payload)
        native_path.chmod(0o600)
        native_source_bindings[relative] = _git_binding(native_payload)

    layout = {
        "action_root": str(action_root),
        "candidate_output": str(candidate),
        "checkout_root": str(checkout),
        "commercial_sources_path": str(checkout / parsers.BOUND_SOURCE_FILES[0]),
        "launch_envelope_path": str(action_root / "native_launch_envelope.json"),
        "manifest_path": str(action_root / "native_preflight.manifest"),
        "native_binary_path": str(action_root / "cur0s_native_preflight"),
        "preregistration_path": str(action_root / "preregistration.json"),
        "runner_path": str(checkout / parsers.BOUND_SOURCE_FILES[1]),
    }

    def fixture_layout(observed_run_id: str, observed_commit: str) -> dict[str, str]:
        assert observed_run_id == run_id
        assert observed_commit == source_commit
        return dict(layout)

    monkeypatch.setattr(commercial, "native_preflight_execution_layout", fixture_layout)
    binary_payload = b"synthetic-android-native-binary"
    binary_path = action_root / "cur0s_native_preflight"
    binary_path.write_bytes(binary_payload)
    binary_path.chmod(0o700)
    native_build_receipt = _native_build_receipt_fixture(
        commercial,
        run_id,
        source_commit,
        native_source_bindings,
        binary_payload,
        os.getuid(),
        os.getgid(),
    )
    _write_canonical_private(
        action_root / "native_preflight_build_receipt.json",
        native_build_receipt,
        trailing_newline=False,
    )
    native_preflight = commercial.build_native_preflight_execution_contract(
        run_id=run_id,
        source_commit=source_commit,
        source_file_bindings=source_file_bindings,
        native_source_file_bindings=native_source_bindings,
        native_build_receipt=native_build_receipt,
    )
    thermal_contract = commercial.phone_thermal_safety_contract()
    campaign_lease = {
        "lease_id": "current_user_sovereign_frontier_campaign_20260712",
        "action_id": run_id,
        "state": "active",
        "issued_at_utc": "2026-07-12T12:00:00Z",
        "expires_at_utc": "2026-07-12T13:00:00Z",
        "additional_paid_capacity": False,
        "max_phone_execution_count": 1,
        "phone_execution_count_before": 0,
        "max_wall_seconds": 1000,
        "terminalization_reserve_seconds": 30,
        "max_private_output_bytes": 10_000,
        "min_free_storage_bytes": 100,
        "thermal_safety_contract": thermal_contract,
        "thermal_sample_interval_seconds": 5,
    }
    resource_slice = {
        "phone_adb_serial_sha256": parsers.EXPECTED_ADB_SERIAL_SHA256,
        "phone_model": "NX789J",
        "phone_soc": "SM8750",
        "runpod": "not_used_for_this_action",
        "github_repository": "Zer0pa/Polymath-AI",
        "huggingface_visibility": "private_revision_pinned_C4_COM_only",
        "comet_payload": "hash_bound_metadata_only",
        "public_release": False,
    }
    network_policy = {
        "allowed_https_hosts": [
            "apps.usgs.gov",
            "ftp.ebi.ac.uk",
            "github-cloud.s3.amazonaws.com",
            "github.com",
            "lod.nal.usda.gov",
            "objects.githubusercontent.com",
            "raw.githubusercontent.com",
            "release.geneontology.org",
            "wordnetcode.princeton.edu",
            "www.siyavula.com",
        ],
        "cleartext_transport_allowed": False,
        "curl_resume_allowed": False,
        "direct_source_pre_and_post_metadata_required": True,
        "git_protocol": "https_only_exact_commit_sparse_fetch",
        "redirect_hops_must_remain_allowlisted_https": True,
    }
    preregistration_body = {
        "schema_version": "cur0s_commercial_sources_preregistration_v1",
        "candidate_id": "cur0s_commercial_authority_sources_phone_native_v1",
        "parent_experiment_id": "EXP-CUR0S-SOVEREIGN-COMPOSITE-V1",
        "run_id": run_id,
        "state": "frozen_unobserved",
        "candidate_output_observed": False,
        "candidate_output_files_present": False,
        "phone_execution_started": False,
        "promotion_allowed": False,
        "source_commit": source_commit,
        "source_file_sha256": source_file_sha256,
        "source_file_bindings": source_file_bindings,
        "commercial_source_contract": contract,
        "commercial_source_contract_sha256": commercial.canonical_sha256(contract),
        "phone_toolchain_identity": toolchain_contract,
        "phone_toolchain_identity_sha256": commercial.canonical_sha256(
            toolchain_contract
        ),
        "native_preflight": native_preflight,
        "native_preflight_sha256": commercial.canonical_sha256(native_preflight),
        "parent_capsule_sha256": parsers.EXPECTED_PARENT_CAPSULE_SHA256,
        "parent_frontier_root_sha256": parsers.EXPECTED_PARENT_FRONTIER_ROOT_SHA256,
        "maximal_selector_sha256": parsers.EXPECTED_PARENT_FRONTIER_ROOT_SHA256,
        "ACCESS_receipt_sha256": parsers.EXPECTED_ACCESS_RECEIPT_SHA256,
        "campaign_lease": campaign_lease,
        "resource_slice": resource_slice,
        "target_device": {
            "adb_serial_sha256": parsers.EXPECTED_ADB_SERIAL_SHA256,
            "architecture": "aarch64",
            "build_fingerprint_sha256": parsers.EXPECTED_BUILD_FINGERPRINT_SHA256,
            "device": "NX789J",
            "model": "NX789J",
            "private_home": str(phone_home),
            "python_platform_system": "Android",
            "soc": "SM8750",
        },
        "network_policy": network_policy,
        "source_checkout_policy": (
            "git_HEAD_equals_source_commit_and_bound_files_match_blob_oid_bytes_sha256"
        ),
        "governing_inputs": {
            "PRD_sha256": "sha256:725d0ad6ac77fdcfc06a2635c7552cc414e0ed48f30fbd0f7f7ec38720493a3c",
            "living_concept_sha256": "sha256:b2f617766b660237ddfd329c6b7fa2370f9a2641983e71915b4cd71c6d31bacc",
            "corpus_audit_sha256": "sha256:c3a5d5eacf424f6e50ae0a170873d1c80e566581e22031a8f64bc899f8eec0fa",
        },
        "claim_scope": (
            "commercial_source_acquisition_identity_rights_and_phone_custody"
        ),
        "claim_ceiling": "source_root_passed_scope_only_not_integrated_CUR_0S",
        "output_directory_name": "candidate-001",
        "expected_disposition": (
            "retain_phone_private_source_root_and_continue_near_semantic_Arm_C"
        ),
        "transaction_policy": {
            "execution_claim_publication": (
                "canonical_empty_candidate_fsync_then_stable_package_anchor_"
                "run_keyed_O_EXCL_claim_last"
            ),
            "execution_claim_replay_allowed": False,
            "claim_only_disposition": "blocked_incomplete_nonreplayable",
            "terminal_success": "canonical_receipt_bound_COMPLETE_O_EXCL_fsync_last",
            "terminal_abort": (
                "stable_package_anchor_run_keyed_ABORT_O_EXCL_without_source_root_pass"
            ),
            "partial_claim_blocks_replay": True,
            "preclaim_orphan_reconciliation": (
                "exact_empty_owner_only_adopt_else_stable_ABORT"
            ),
            "control_anchor": str(package_root),
            "exclusive_Termux_UID_operational_assumption": True,
            "concurrent_same_UID_writer_allowed": False,
            "malicious_same_UID_tamper_resistance_claimed": False,
            "package_reset_or_uninstall_invalidates_local_control_anchor": True,
        },
        "custody": {
            "C4_COM_and_C4_RX_roots_separate": True,
            "aggregate_hash_bound_receipt_egress": True,
            "execution_plane": "phone_private",
            "Mac_raw_cache": False,
            "private_HF_mirror": (
                "deferred_until_source_root_passes_then_revision_pinned"
            ),
            "raw_payload_egress": False,
        },
        "nonclaims": [
            "not_semantic_material_compilation",
            "not_near_semantic_Arm_C",
            "not_connected_split_or_exposure_ledger",
            "not_C3_dictionary_or_C4_syllabus_admission",
            "not_CUR_0S_or_CUR_0P_or_composite_CUR_0",
            "not_target_data_learning_or_authority",
        ],
    }
    preregistration = {
        **preregistration_body,
        "preregistration_root_sha256": commercial.canonical_sha256(
            preregistration_body
        ),
    }
    preregistration_payload = _write_canonical_private(
        action_root / "preregistration.json",
        preregistration,
    )
    manifest_payload = commercial.build_native_preflight_manifest_bytes(preregistration)
    manifest_path = action_root / "native_preflight.manifest"
    manifest_path.write_bytes(manifest_payload)
    manifest_path.chmod(0o600)
    launch_envelope = commercial.build_native_launch_envelope(
        preregistration,
        manifest_payload,
    )
    _write_canonical_private(
        action_root / "native_launch_envelope.json",
        launch_envelope,
    )
    process_identity_sha256 = "sha256:" + "9" * 64
    phone_toolchain = {
        "toolchain_root_sha256": toolchain_contract["toolchain_root_sha256"],
        "artifact_count": len(toolchain_contract["artifacts"]),
        "artifact_manifest_sha256": commercial.canonical_sha256(
            toolchain_contract["artifacts"]
        ),
        "command_probe_count": len(toolchain_contract["command_probes"]),
        "command_probe_manifest_sha256": commercial.canonical_sha256(
            toolchain_contract["command_probes"]
        ),
        "python_stdlib_tree_root_sha256": toolchain_contract["python_stdlib_tree"][
            "root_sha256"
        ],
        "python_stdlib_tree_entry_count": toolchain_contract["python_stdlib_tree"][
            "entry_count"
        ],
        "python_stdlib_tree_volatile_identity": [1] * 9,
        "current_process_identity_sha256": process_identity_sha256,
        "current_process_executable_mapping_count": 1,
        "validated_before_candidate_preparation_and_execution_claim": True,
        "final_revalidation": {
            "toolchain_root_sha256": toolchain_contract["toolchain_root_sha256"],
            "artifact_count": len(toolchain_contract["artifacts"]),
            "python_stdlib_tree_root_sha256": toolchain_contract["python_stdlib_tree"][
                "root_sha256"
            ],
            "current_process_identity_sha256": process_identity_sha256,
            "final_revalidation_passed": True,
        },
    }
    final_custody_body = {
        "schema_version": "cur0s_final_source_custody_reattestation_v1",
        "artifact_count": 1,
        "artifacts": [
            {
                "source_id": source_id,
                "acquisition_mode": spec.acquisition_mode,
                "bytes": len(payload),
                "sha256": digest,
                "content_manifest_sha256": commercial.canonical_sha256(
                    artifact["content_manifest"]
                ),
            }
        ],
        "candidate_entry_set": ["sources"],
        "C4_COM_and_C4_RX_roots_separate": True,
        "fd_root_O_NOFOLLOW_readback": True,
        "raw_payload_egressed": False,
    }
    final_custody = {
        **final_custody_body,
        "reattestation_root_sha256": commercial.canonical_sha256(final_custody_body),
    }
    preregistration_root_sha256 = preregistration["preregistration_root_sha256"]
    authority_bindings = {
        "parent_capsule_sha256": parsers.EXPECTED_PARENT_CAPSULE_SHA256,
        "parent_frontier_root_sha256": parsers.EXPECTED_PARENT_FRONTIER_ROOT_SHA256,
        "maximal_selector_sha256": parsers.EXPECTED_PARENT_FRONTIER_ROOT_SHA256,
        "campaign_lease_root_sha256": commercial.canonical_sha256(campaign_lease),
        "resource_slice_root_sha256": commercial.canonical_sha256(resource_slice),
        "network_policy_root_sha256": commercial.canonical_sha256(network_policy),
        "preregistration_sha256": "sha256:"
        + hashlib.sha256(preregistration_payload).hexdigest(),
        "preregistration_root_sha256": preregistration_root_sha256,
        "ACCESS_receipt_sha256": parsers.EXPECTED_ACCESS_RECEIPT_SHA256,
    }
    claim_name = f".{run_id}.cur0s_execution_claim.json"
    claim = {
        "schema_version": "cur0s_commercial_sources_execution_claim_v1",
        "state": "claimed_terminal_pending",
        "run_id": run_id,
        "output_directory_name": "candidate-001",
        "stable_control_anchor": str(package_root),
        "execution_claim_filename": claim_name,
        "phone_execution_ordinal": 1,
        "preregistration_root_sha256": preregistration_root_sha256,
        "contract_root_sha256": contract["contract_root_sha256"],
        "candidate_directory_prepared_identity": {
            "device": prepared.st_dev,
            "inode": prepared.st_ino,
            "file_type": "directory",
            "link_count": prepared.st_nlink,
            "bytes": prepared.st_size,
            "uid": prepared.st_uid,
            "gid": prepared.st_gid,
            "mode": "0700",
        },
        "replay_allowed": False,
        "claim_only_disposition": "blocked_incomplete_nonreplayable",
        "valid_terminal_resolutions": [
            "canonical_receipt_bound_COMPLETE_in_candidate",
            "stable_control_anchor_ABORT_without_source_root_pass",
        ],
    }
    claim_payload = _write_canonical_read_only(package_root / claim_name, claim)
    claim_sha256 = "sha256:" + hashlib.sha256(claim_payload).hexdigest()
    native_execution_identity = {
        "schema_version": "cur0s_native_launch_attestation_v1",
        "manifest_sha256": "sha256:" + hashlib.sha256(manifest_payload).hexdigest(),
        "manifest_bytes": len(manifest_payload),
        "entries_verified": len(native_preflight["static_manifest_records"]) + 1,
        "passes_completed": 2,
        "same_pid_execveat_verified": True,
        "sealed_memfd_attestation_verified": True,
        "fixed_fd_map": dict(native_preflight["fixed_fd_map"]),
        "fixed_fd_map_matches_preregistration": True,
        "outer_env_observed": True,
        "outer_environment_sha256": native_preflight["outer_launch"][
            "outer_environment_sha256"
        ],
        "outer_launch_contract_sha256": native_preflight["outer_launch_sha256"],
        "outer_launcher_argv_preregistered": True,
        "helper_dependency_swap_safety_claimed": False,
        "security_ceiling": native_preflight["security_ceiling"],
        "validated_before_candidate_preparation_and_execution_claim": True,
    }
    receipt_body = {
        "schema_version": "cur0s_commercial_sources_receipt_v1",
        "candidate_id": "cur0s_commercial_authority_sources_phone_native_v1",
        "run_id": run_id,
        "state": "passed_scope",
        "candidate_output_observed": True,
        "source_root_state": "passed_scope",
        "all_source_identity_and_rights_gates_passed": True,
        "commercial_source_contract_sha256": commercial.canonical_sha256(contract),
        "commercial_source_contract_root_sha256": contract["contract_root_sha256"],
        "source_execution_identity": {
            "source_commit": source_commit,
            "source_file_sha256": source_file_sha256,
            "source_file_bindings": source_file_bindings,
            "git_HEAD_verified": True,
            "bound_source_files_clean": True,
            "preimport_source_bytes_verified": True,
            "commercial_source_contract_sha256": commercial.canonical_sha256(contract),
            "commercial_source_contract_root_sha256": contract["contract_root_sha256"],
            "phone_toolchain_identity_sha256": commercial.canonical_sha256(
                toolchain_contract
            ),
            "phone_toolchain_root_sha256": toolchain_contract["toolchain_root_sha256"],
            "native_preflight_contract_sha256": commercial.canonical_sha256(
                native_preflight
            ),
            "native_preflight_contract_root_sha256": native_preflight[
                "contract_root_sha256"
            ],
            "native_preflight_execution": dict(native_execution_identity),
            "native_preflight_final_revalidation": dict(native_execution_identity),
            "final_source_custody_reattestation": final_custody,
        },
        "runtime_identity": {
            "model": "NX789J",
            "device": "NX789J",
            "soc": "SM8750",
            "architecture": "aarch64",
            "python_platform_system": "Android",
            "private_home_sha256": "sha256:"
            + hashlib.sha256(str(phone_home).encode("utf-8")).hexdigest(),
            "build_fingerprint_sha256": parsers.EXPECTED_BUILD_FINGERPRINT_SHA256,
            "adb_serial_sha256": parsers.EXPECTED_ADB_SERIAL_SHA256,
            "adb_serial_runtime_visibility": "external_ADB_custody_only",
            "phone_private_runtime_guard_passed": True,
            "phone_toolchain": phone_toolchain,
        },
        "authority_bindings": authority_bindings,
        "source_root": source_root,
        "source_inspection_summaries": [
            {
                "source_id": source_id,
                "acquisition_mode": spec.acquisition_mode,
                "archive_or_document_type": "validated_OBO_document",
                "member_count": 1,
                "uncompressed_or_document_bytes": len(payload),
                "required_marker_count": 1,
                "required_markers_verified": True,
                "payload_rights_evidence_root_sha256": "sha256:" + "7" * 64,
                "external_rights_evidence_runtime_verified": False,
                "transport_response_attempts": {
                    "preflight": 1,
                    "download": 1,
                    "postflight": 1,
                },
                "transfer_evidence": {
                    "schema_version": "cur0s_direct_transfer_evidence_v1",
                    "mode": spec.transfer_mode,
                    "fixed_chunk_bytes": spec.fixed_chunk_bytes,
                    "chunk_count": 1,
                    "per_chunk_attempts": [1],
                    "total_attempts": 1,
                    "every_response_206": True,
                    "every_content_range_exact": True,
                    "no_overlap": True,
                    "no_gap": True,
                    "held_destination_single_inode": True,
                    "full_length_and_sha256_verified": True,
                },
                "structure_checks": {
                    "OBO_term_stanzas": 1,
                    "definition_line_count": 1,
                    "id_line_count": 1,
                    "name_line_count": 1,
                    "release_and_license_headers_verified": True,
                },
                "raw_payload_egressed": False,
            }
        ],
        "first_next_blocker": "private_C4_COM_mirror",
        "mandatory_next_disposition": (
            "retain_phone_private_source_root_mirror_to_private_revision_pinned_"
            "C4_COM_then_compile_semantic_materials_before_near_semantic_Arm_C"
        ),
        "claim_ceiling": "commercial_source_identity_rights_and_phone_custody_only",
        "semantic_rows_compiled": False,
        "near_semantic_arm_C_executed": False,
        "connected_split_assigned": False,
        "cur0s_static_pass_claimed": False,
        "cur0s_pass_claimed": False,
        "composite_cur0_pass_claimed": False,
        "target_data_learning_claimed": False,
        "authority_claimed": False,
        "private_HF_mirror_completed": False,
        "c4_rx_content_present": False,
        "custody": {
            "raw_source_owner": "phone",
            "raw_source_path_egressed": False,
            "raw_payload_egressed": False,
            "Mac_raw_cache": False,
            "receipt_contains_hash_bound_aggregates_only": True,
            "C4_COM_and_C4_RX_roots_separate": True,
        },
        "execution_claim": {
            "state": "claimed_terminal_pending_once_O_EXCL",
            "claim_sha256": claim_sha256,
            "claim_bytes": len(claim_payload),
            "stable_control_anchor": str(package_root),
            "execution_claim_filename": claim_name,
            "claim_egressed": False,
            "claim_is_crash_anchor": True,
            "claim_only_state_is_blocked_and_never_replayable": True,
            "exclusive_Termux_UID_operational_assumption": True,
            "malicious_same_UID_tamper_resistance_claimed": False,
            "replay_allowed": False,
            "terminal_resolution_required": (
                "exact_receipt_bound_COMPLETE_or_stable_control_ABORT"
            ),
        },
        "preterminal_resource_envelope_snapshot": {
            "action_id": run_id,
            "phone_execution_ordinal": 1,
            "max_wall_seconds": 1000,
            "terminalization_reserve_seconds": 30,
            "maximum_observed_elapsed_seconds": 10.0,
            "min_free_storage_bytes": 100,
            "minimum_observed_free_storage_bytes": 200,
            "thermal_safety_contract_root_sha256": thermal_contract[
                "contract_root_sha256"
            ],
            "thermal_group_ceilings_millidegrees_c": thermal_contract[
                "group_ceilings_millidegrees_c"
            ],
            "maximum_observed_thermal_group_millidegrees_c": {
                group: 35_000 for group in thermal_contract["sensor_types_by_group"]
            },
            "observed_thermal_sensor_types_by_group": thermal_contract[
                "sensor_types_by_group"
            ],
            "thermal_unavailable_sentinels_millidegrees_c": [-273_000, -40_960],
            "thermal_sample_interval_seconds": 5,
            "thermal_sample_count": 1,
            "maximum_readable_thermal_sensor_count": 1,
            "max_private_output_bytes": 10_000,
            "private_output_bytes_before_receipt": 500,
            "private_output_allocated_bytes_before_receipt": 600,
            "maximum_observed_private_output_bytes": 500,
            "maximum_observed_private_allocated_bytes": 600,
            "maximum_ephemeral_control_bytes": 100,
            "maximum_ephemeral_control_allocated_bytes": 100,
            "ephemeral_control_files_open_at_receipt": 0,
            "lease_expires_at_utc": "2026-07-12T13:00:00Z",
            "snapshot_scope": "through_receipt_construction_before_publication",
        },
        "preterminal_execution_snapshot": {
            "started_at_utc": "2026-07-12T12:00:00Z",
            "snapshot_at_utc": "2026-07-12T12:01:00Z",
            "elapsed_seconds_at_snapshot": 60.0,
            "peak_rss_kib_at_snapshot": 1024,
            "python": "3.13.9",
        },
        "pending_transaction_links": [
            "post_run_evidence_commit",
            "origin_push_readback",
            "capsule_CAS_transition",
            "private_revision_pinned_HF_C4_COM_mirror",
        ],
        "nonclaims": [
            "not_semantic_material_compilation",
            "not_near_semantic_Arm_C",
            "not_connected_split_or_exposure_ledger",
            "not_C3_dictionary_or_C4_syllabus_admission",
            "not_CUR_0S_or_CUR_0P_or_composite_CUR_0",
            "not_target_data_learning_or_authority",
            "not_Section_0_5_success",
        ],
    }
    receipt = {
        **receipt_body,
        "receipt_root_sha256": commercial.canonical_sha256(receipt_body),
    }
    receipt_payload = _write_canonical_read_only(candidate / "receipt.json", receipt)
    complete = {
        "schema_version": "cur0s_commercial_sources_completion_v1",
        "run_id": receipt["run_id"],
        "state": "passed_scope",
        "receipt_sha256": "sha256:" + hashlib.sha256(receipt_payload).hexdigest(),
        "receipt_root_sha256": receipt["receipt_root_sha256"],
        "receipt_bytes": len(receipt_payload),
        "completion_marker_prepared_at_utc": "2026-07-12T12:00:00Z",
        "completion_protocol": (
            "raw_sources_fsync_read_only_then_receipt_O_EXCL_fsync_read_only_"
            "then_COMPLETE_O_EXCL_fsync_last"
        ),
        "raw_sources_preserved_on_phone": True,
        "output_directory_mode": "owner_only_0700",
    }
    _write_canonical_read_only(candidate / "COMPLETE.json", complete)
    source_path.chmod(0o400)
    source_dir.chmod(0o500)
    source_dir.parent.chmod(0o500)
    source_dir.parent.parent.chmod(0o500)
    candidate.chmod(0o700)
    context = parsers.ParseContext(
        source_id=source_id,
        release_identity=spec.release_identity,
        source_sha256=digest,
        source_locator=locator,
        license_id=spec.license_id,
        license_class=spec.license_class,
        rights_proof=spec.rights_proof,
    )
    expected_authority = parsers.ProductionAuthorityExpectation(
        preregistration_sha256="sha256:"
        + hashlib.sha256(preregistration_payload).hexdigest(),
        acquisition_receipt_sha256="sha256:"
        + hashlib.sha256(receipt_payload).hexdigest(),
    )
    return candidate, spec, context, expected_authority


def test_canonical_source_unit_is_stable_and_hash_bound() -> None:
    context = _context()
    first = parsers.stable_unit_id("fixture", "fixture_release_v1", "term:1")
    second = parsers.stable_unit_id("fixture", "fixture_release_v1", "term:1")

    assert first == second
    assert first.startswith("urn:cur0s:source-unit:")
    assert first != parsers.stable_unit_id("fixture", "fixture_release_v1", "term:2")
    context.validate()
    assert set(parsers.UNVERIFIED_PARSER_FORMATS) == {
        "wordnet_tar",
        "nalt_turtle_zip",
        "obo",
        "usgs_skos_rdf",
        "siyavula_epub",
        "openstax_tree",
    }

    invalid = parsers.ParseContext(**{**context.__dict__, "license_class": "C"})
    with pytest.raises(parsers.SourceParseError, match="inadmissible_license_class"):
        invalid.validate()


def test_wordnet_tar_normalizes_synsets_index_and_hypernym(tmp_path: Path) -> None:
    path = tmp_path / "wordnet.tar.gz"
    _write_wordnet(path)

    units = list(parsers.parse_wordnet_tar(path, _file_context(path, "wordnet")))
    by_key = {unit.source_key: unit for unit in units}

    assert len(units) == 5
    child = by_key["wn:n:00001930"]
    assert child.title == "physical entity"
    assert child.flags.has_numeric_content is True
    assert [edge.edge_type for edge in child.edges] == ["hierarchy"]
    assert child.edges[0].predicate == "hypernym"
    assert child.edges[0].target_source_key == "wn:n:00001740"
    assert child.rights.license_id == "CC-BY-4.0"
    assert child.provenance.record_sha256.startswith("sha256:")
    assert child.canonical_sha256.startswith("sha256:")
    assert parsers.validate_source_unit(child) is child
    assert child.facets == (parsers.SourceFacet("part_of_speech", ("n",)),)


@pytest.mark.parametrize(
    ("mutation", "match"),
    (
        ("edge", "source_unit_edge_target_binding_invalid"),
        ("rights", "source_unit_rights_structure_invalid"),
        ("record_scope", "source_unit_record_scope_invalid"),
    ),
)
def test_source_unit_validation_recomputes_structural_bindings(
    tmp_path: Path,
    mutation: str,
    match: str,
) -> None:
    path = tmp_path / "wordnet.tar.gz"
    _write_wordnet(path)
    unit = next(
        item
        for item in parsers.parse_wordnet_tar(path, _file_context(path, "wordnet"))
        if item.edges
    )
    forged = unit.to_dict()
    for facet in forged["facets"]:
        facet["values"] = list(facet["values"])
    if mutation == "edge":
        forged["edges"][0]["target_unit_id"] = "urn:cur0s:source-unit:" + "0" * 64
    elif mutation == "rights":
        forged["rights"]["license_class"] = "C"
    else:
        forged["provenance"]["record_digest_scope"] = "caller_supplied"
    body = dict(forged)
    body.pop("canonical_sha256")
    forged["canonical_sha256"] = parsers.canonical_sha256(body)
    with pytest.raises(parsers.SourceParseError, match=match):
        parsers.validate_source_unit(parsers._source_unit_from_dict(forged))


def test_wordnet_tar_rejects_links_and_missing_index_target(tmp_path: Path) -> None:
    link_path = tmp_path / "linked.tar.gz"
    link = tarfile.TarInfo("WordNet-3.0/dict/linked")
    link.type = tarfile.SYMTYPE
    link.linkname = "../../outside"
    _write_wordnet(link_path, link)
    with pytest.raises(
        parsers.SourceParseError,
        match="archive_link_or_special_member_rejected",
    ):
        list(
            parsers.parse_wordnet_tar(
                link_path,
                _file_context(link_path, "wordnet"),
            )
        )

    bad_path = tmp_path / "bad-index.tar.gz"
    members = _wordnet_members()
    members["WordNet-3.0/dict/index.noun"] = b"entity n 1 0 1 1 99999999\n"
    with tarfile.open(bad_path, "w:gz") as archive:
        for name, value in members.items():
            _add_tar_bytes(archive, name, value)
    with pytest.raises(
        parsers.SourceParseError,
        match="wordnet_index_references_missing_synset",
    ):
        list(
            parsers.parse_wordnet_tar(
                bad_path,
                _file_context(bad_path, "wordnet"),
            )
        )


@pytest.mark.parametrize("archive_format", (tarfile.PAX_FORMAT, tarfile.GNU_FORMAT))
def test_wordnet_tar_bounds_extension_metadata_before_tarfile_trust(
    tmp_path: Path,
    archive_format: int,
) -> None:
    path = tmp_path / f"metadata-{archive_format}.tar.gz"
    with tarfile.open(path, "w:gz", format=archive_format) as archive:
        for index, (name, value) in enumerate(_wordnet_members().items()):
            info = tarfile.TarInfo(name)
            if index == 0 and archive_format == tarfile.PAX_FORMAT:
                info.pax_headers = {"comment": "x" * 512}
            info.size = len(value)
            archive.addfile(info, BytesIO(value))
        if archive_format == tarfile.GNU_FORMAT:
            _add_tar_bytes(archive, "long/" + "x" * 256, b"metadata")
    limits = replace(parsers.DEFAULT_LIMITS, max_field_chars=64)
    with pytest.raises(
        parsers.SourceParseError,
        match="tar_extension_metadata_limit_exceeded",
    ):
        list(
            parsers.parse_wordnet_tar(
                path,
                _file_context(path, "wordnet"),
                limits,
            )
        )


def test_wordnet_tar_counts_hidden_pax_headers_against_member_bound(
    tmp_path: Path,
) -> None:
    path = tmp_path / "hidden-pax-member.tar.gz"
    with tarfile.open(path, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        info = tarfile.TarInfo("WordNet-3.0/dict/data.noun")
        info.pax_headers = {"comment": "bounded"}
        payload = _wordnet_members()["WordNet-3.0/dict/data.noun"]
        info.size = len(payload)
        archive.addfile(info, BytesIO(payload))
    limits = replace(parsers.DEFAULT_LIMITS, max_archive_members=1)
    with pytest.raises(parsers.SourceParseError, match="archive_member_limit_exceeded"):
        list(
            parsers.parse_wordnet_tar(
                path,
                _file_context(path, "wordnet"),
                limits,
            )
        )


def _nalt_turtle() -> bytes:
    return b"""@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix nalt: <https://lod.nal.usda.gov/nalt/100> .
<https://lod.nal.usda.gov/nalt/1_def> rdf:value "systematic knowledge"@en .
<https://lod.nal.usda.gov/nalt/1> a skos:Concept ;
  skos:prefLabel "science"@en ;
  skos:altLabel "scientific knowledge"@en ;
  skos:definition <https://lod.nal.usda.gov/nalt/1_def> .
<https://lod.nal.usda.gov/nalt/2> rdf:type skos:Concept ;
  skos:prefLabel "soil 2"@en ;
  skos:scopeNote "earth material"@en ;
  skos:broader <https://lod.nal.usda.gov/nalt/1> .
"""


def test_nalt_restricted_turtle_normalizes_labels_and_broader(tmp_path: Path) -> None:
    path = tmp_path / "nalt.zip"
    _write_zip(path, {"nalt-core.ttl": _nalt_turtle()})

    units = list(parsers.parse_nalt_turtle_zip(path, _file_context(path, "nalt")))

    assert [unit.title for unit in units] == ["science", "soil 2"]
    assert units[0].synonyms == ("scientific knowledge",)
    assert units[0].definition == "systematic knowledge"
    assert units[0].facets == (
        parsers.SourceFacet(
            "rdf_type", ("http://www.w3.org/2004/02/skos/core#Concept",)
        ),
    )
    assert units[1].flags.has_numeric_content is False
    assert units[1].edges[0].predicate == "skos_broader"
    assert units[1].edges[0].target_source_key.endswith("/1")


@pytest.mark.parametrize(
    "bad_turtle,match",
    [
        (
            b"@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n"
            b"[] a skos:Concept .\n",
            "unsupported_turtle_collection_or_blank_node",
        ),
        (
            b"@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n"
            b'<urn:x> a skos:Concept ; skos:prefLabel "one"@en ; '
            b'skos:prefLabel "two"@en ; skos:definition "d"@en .\n',
            "nalt_ambiguous_or_missing_english_pref_label",
        ),
    ],
)
def test_nalt_turtle_fails_closed_on_unsupported_or_ambiguous_grammar(
    tmp_path: Path,
    bad_turtle: bytes,
    match: str,
) -> None:
    path = tmp_path / "bad.zip"
    _write_zip(path, {"nalt.ttl": bad_turtle})
    with pytest.raises(parsers.SourceParseError, match=match):
        list(parsers.parse_nalt_turtle_zip(path, _file_context(path, "nalt")))


def test_nalt_per_concept_assertions_are_bounded_while_parsing(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bounded-nalt.zip"
    turtle = b"""@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
<urn:x> a skos:Concept ;
  skos:prefLabel "one"@en ;
  skos:altLabel "alternate one"@en ;
  skos:altLabel "alternate two"@en ;
  skos:altLabel "alternate three"@en .
"""
    _write_zip(path, {"nalt.ttl": turtle})

    with pytest.raises(
        parsers.SourceParseError,
        match="nalt_alt_assertion_limit_exceeded",
    ):
        list(
            parsers.parse_nalt_turtle_zip(
                path,
                _file_context(path, "nalt"),
                parsers.ParserLimits(max_synonyms_per_unit=2),
            )
        )


def test_zip_rejects_path_traversal_before_parsing(tmp_path: Path) -> None:
    path = tmp_path / "unsafe.zip"
    _write_zip(path, {"../nalt.ttl": _nalt_turtle()})
    with pytest.raises(parsers.SourceParseError, match="unsafe_archive_path"):
        list(parsers.parse_nalt_turtle_zip(path, _file_context(path, "nalt")))


def test_obo_normalizes_definition_synonyms_and_edges(tmp_path: Path) -> None:
    path = tmp_path / "ontology.obo"
    path.write_text(
        """format-version: 1.2

[Term]
id: TEST:0001
name: parent
def: "parent definition" [src:1]

[Term]
id: TEST:0002
name: child 2
def: "child definition" [src:2]
subset: 3_STAR
synonym: "offspring" EXACT []
is_a: TEST:0001 ! parent
relationship: occurs_in TEST:0001

[Term]
id: TEST:0003
name: old
def: "obsolete" []
is_obsolete: true
""",
        encoding="utf-8",
    )

    units = list(parsers.parse_obo(path, _file_context(path, "obo")))

    assert [unit.source_key for unit in units] == ["TEST:0001", "TEST:0002"]
    child = units[1]
    assert child.synonyms == ("offspring",)
    assert [(edge.edge_type, edge.predicate) for edge in child.edges] == [
        ("hierarchy", "is_a"),
    ]
    assert child.flags.has_numeric_content is False
    assert child.facets == (
        parsers.SourceFacet("subset", ("3_STAR",)),
        parsers.SourceFacet(
            "unadjudicated_ontology_relation",
            ("occurs_in TEST:0001",),
        ),
    )


def test_obo_rejects_duplicate_identity_and_bounded_lines(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.obo"
    stanza = '[Term]\nid: X:1\nname: x\ndef: "d" []\n'
    path.write_text(stanza + "\n" + stanza, encoding="utf-8")
    with pytest.raises(parsers.SourceParseError, match="obo_duplicate_identity"):
        list(parsers.parse_obo(path, _file_context(path, "obo")))

    limits = parsers.ParserLimits(max_line_bytes=8)
    with pytest.raises(parsers.SourceParseError, match="line_limit_exceeded"):
        list(parsers.parse_obo(path, _file_context(path, "obo"), limits))


def test_obo_late_duplicate_releases_no_partial_unit(tmp_path: Path) -> None:
    path = tmp_path / "late-duplicate.obo"
    stanza = '[Term]\nid: X:1\nname: x\ndef: "d" []\n'
    path.write_text(stanza + "\n" + stanza, encoding="utf-8")

    iterator = parsers.parse_obo(path, _file_context(path, "obo"))

    with pytest.raises(parsers.SourceParseError, match="obo_duplicate_identity"):
        next(iterator)


def test_all_or_nothing_spool_has_an_enforced_disk_bound(tmp_path: Path) -> None:
    path = tmp_path / "bounded.obo"
    path.write_text(
        '[Term]\nid: X:1\nname: x\ndef: "definition beyond tiny spool" []\n',
        encoding="utf-8",
    )
    limits = parsers.ParserLimits(max_spool_bytes=64)
    iterator = parsers.parse_obo(path, _file_context(path, "obo"), limits)

    with pytest.raises(
        parsers.SourceParseError,
        match="source_unit_spool_limit_exceeded",
    ):
        next(iterator)


def test_direct_parser_holds_one_fd_and_rejects_path_swap_before_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "held.obo"
    path.write_text(
        '[Term]\nid: X:1\nname: original\ndef: "original definition" []\n',
        encoding="utf-8",
    )
    context = _file_context(path, "obo")
    original_parser = parsers._parse_obo_handle
    swapped = False

    def swap_then_parse(*args: Any, **kwargs: Any) -> Any:
        nonlocal swapped
        if not swapped:
            swapped = True
            path.rename(tmp_path / "held-original.obo")
            path.write_text(
                '[Term]\nid: EVIL:1\nname: attacker\ndef: "attacker" []\n',
                encoding="utf-8",
            )
        yield from original_parser(*args, **kwargs)

    monkeypatch.setattr(parsers, "_parse_obo_handle", swap_then_parse)
    iterator = parsers.parse_obo(path, context)

    with pytest.raises(
        parsers.SourceParseError,
        match="source_(?:path_)?changed_during_parse",
    ):
        next(iterator)


def _rdf_xml() -> str:
    return f"""<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="{parsers.RDF_NS}" xmlns:skos="{parsers.SKOS_NS}">
  <rdf:Description rdf:about="https://example.test/concept/1">
    <rdf:type rdf:resource="{parsers.SKOS_NS}Concept"/>
    <skos:prefLabel xml:lang="en">Earth science</skos:prefLabel>
    <skos:definition xml:lang="en">Study of Earth 3</skos:definition>
  </rdf:Description>
  <skos:Concept rdf:about="https://example.test/concept/2">
    <skos:prefLabel xml:lang="en">Geology</skos:prefLabel>
    <skos:altLabel xml:lang="en">Earth geology</skos:altLabel>
    <skos:scopeNote xml:lang="en">Study of rocks</skos:scopeNote>
    <skos:broader rdf:resource="https://example.test/concept/1"/>
  </skos:Concept>
</rdf:RDF>
"""


def test_usgs_rdf_streams_description_and_skos_concept(tmp_path: Path) -> None:
    path = tmp_path / "usgs.rdf"
    path.write_text(_rdf_xml(), encoding="utf-8")

    units = list(parsers.parse_usgs_skos_rdf(path, _file_context(path, "usgs")))

    assert [unit.title for unit in units] == ["Earth science", "Geology"]
    assert units[0].flags.has_numeric_content is True
    assert units[1].synonyms == ("Earth geology",)
    assert units[1].edges[0].target_source_key.endswith("/1")


def test_xml_dtd_and_entities_are_rejected_before_elementtree(tmp_path: Path) -> None:
    path = tmp_path / "entity.rdf"
    path.write_text(
        '<!DOCTYPE rdf:RDF [<!ENTITY leak SYSTEM "file:///etc/passwd">]>'
        f'<rdf:RDF xmlns:rdf="{parsers.RDF_NS}"/>',
        encoding="utf-8",
    )
    with pytest.raises(parsers.SourceParseError, match="xml_dtd_or_entity_rejected"):
        list(parsers.parse_usgs_skos_rdf(path, _file_context(path, "usgs")))


@pytest.mark.parametrize(
    "encoding",
    ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "utf-32", "utf-32-be"),
)
def test_encoded_xml_declarations_are_rejected_before_tree_allocation(
    monkeypatch: pytest.MonkeyPatch,
    encoding: str,
) -> None:
    value = (
        '<!DOCTYPE root [<!ENTITY leak SYSTEM "file:///etc/passwd">]>'
        "<root>&leak;</root>"
    ).encode(encoding)

    def parser_must_not_run(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(
            "ElementTree parser allocated before declaration rejection"
        )

    monkeypatch.setattr(parsers.ET, "fromstring", parser_must_not_run)
    with pytest.raises(parsers.SourceParseError, match="xml_dtd_or_entity_rejected"):
        parsers._secure_xml_from_bytes(value, parsers.DEFAULT_LIMITS)


@pytest.mark.parametrize(
    ("payload", "limits", "match"),
    (
        (
            b"<a><b><c><d/></c></b></a>",
            replace(parsers.DEFAULT_LIMITS, max_xml_depth=3),
            "xml_depth_limit_exceeded",
        ),
        (
            b"<a>0123456789</a>",
            replace(parsers.DEFAULT_LIMITS, max_field_chars=8),
            "xml_text_limit_exceeded",
        ),
        (
            b"<a><b/><c/><d/></a>",
            replace(parsers.DEFAULT_LIMITS, max_xml_elements=3),
            "xml_element_count_limit_exceeded",
        ),
        (
            b"<a><b>123456</b><c>123456</c></a>",
            replace(
                parsers.DEFAULT_LIMITS,
                max_field_chars=100,
                max_unit_text_chars=10,
            ),
            "xml_total_text_limit_exceeded",
        ),
    ),
)
def test_xml_allocation_guard_rejects_bombs_before_elementtree_tree_build(
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
    limits: parsers.ParserLimits,
    match: str,
) -> None:
    def parser_must_not_run(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("ElementTree allocated before XML guard")

    monkeypatch.setattr(parsers.ET, "fromstring", parser_must_not_run)
    with pytest.raises(parsers.SourceParseError, match=match):
        parsers._secure_xml_from_bytes(payload, limits)


def test_rdf_bounds_concept_children_and_accumulated_text(tmp_path: Path) -> None:
    many_children = "".join(f"<unknown:item{i}/>" for i in range(67))
    child_bomb = tmp_path / "rdf-child-bomb.rdf"
    child_bomb.write_text(
        f'<rdf:RDF xmlns:rdf="{parsers.RDF_NS}" '
        f'xmlns:skos="{parsers.SKOS_NS}" xmlns:unknown="urn:unknown">'
        f'<skos:Concept rdf:about="https://example.test/c">{many_children}'
        '<skos:prefLabel xml:lang="en">label</skos:prefLabel>'
        "</skos:Concept></rdf:RDF>",
        encoding="utf-8",
    )
    child_limits = replace(
        parsers.DEFAULT_LIMITS,
        max_synonyms_per_unit=1,
        max_edges_per_unit=1,
        max_files=100,
    )
    with pytest.raises(
        parsers.SourceParseError,
        match="rdf_concept_child_limit_exceeded",
    ):
        list(
            parsers.parse_usgs_skos_rdf(
                child_bomb,
                _file_context(child_bomb, "usgs"),
                child_limits,
            )
        )

    text_bomb = tmp_path / "rdf-text-bomb.rdf"
    text_bomb.write_text(
        f'<rdf:RDF xmlns:rdf="{parsers.RDF_NS}" xmlns:skos="{parsers.SKOS_NS}">'
        '<skos:Concept rdf:about="https://example.test/c">'
        '<skos:prefLabel xml:lang="en">label</skos:prefLabel>'
        '<skos:definition xml:lang="en">abcdefghij</skos:definition>'
        '<skos:note xml:lang="en">abcdefghij</skos:note>'
        '<skos:scopeNote xml:lang="en">abcdefghij</skos:scopeNote>'
        "</skos:Concept></rdf:RDF>",
        encoding="utf-8",
    )
    text_limits = replace(
        parsers.DEFAULT_LIMITS,
        max_field_chars=100,
        max_unit_text_chars=25,
    )
    with pytest.raises(
        parsers.SourceParseError,
        match="rdf_accumulated_text_limit_exceeded",
    ):
        list(
            parsers.parse_usgs_skos_rdf(
                text_bomb,
                _file_context(text_bomb, "usgs"),
                text_limits,
            )
        )


def test_utf16_rdf_declaration_is_rejected_before_iterparse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "entity-utf16.rdf"
    path.write_bytes(
        (
            '<!DOCTYPE rdf:RDF [<!ENTITY leak SYSTEM "file:///etc/passwd">]>'
            f'<rdf:RDF xmlns:rdf="{parsers.RDF_NS}"/>'
        ).encode("utf-16")
    )

    def parser_must_not_run(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("iterparse allocated before declaration rejection")

    monkeypatch.setattr(parsers.ET, "iterparse", parser_must_not_run)
    with pytest.raises(parsers.SourceParseError, match="xml_dtd_or_entity_rejected"):
        list(parsers.parse_usgs_skos_rdf(path, _file_context(path, "usgs")))


def test_rdf_scan_and_iterparse_share_held_fd_across_path_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "held.rdf"
    path.write_text(_rdf_xml(), encoding="utf-8")
    context = _file_context(path, "usgs")
    original_scan = parsers._scan_xml_handle
    original_iterparse = parsers.ET.iterparse
    observed_handles: list[Any] = []

    def swap_during_scan(handle: Any, limits: Any) -> None:
        path.rename(tmp_path / "held-original.rdf")
        path.write_text(
            '<!DOCTYPE rdf:RDF [<!ENTITY leak SYSTEM "file:///etc/passwd">]>'
            f'<rdf:RDF xmlns:rdf="{parsers.RDF_NS}">&leak;</rdf:RDF>',
            encoding="utf-8",
        )
        original_scan(handle, limits)

    def record_iterparse(source: Any, *args: Any, **kwargs: Any) -> Any:
        observed_handles.append(source)
        assert hasattr(source, "read")
        return original_iterparse(source, *args, **kwargs)

    monkeypatch.setattr(parsers, "_scan_xml_handle", swap_during_scan)
    monkeypatch.setattr(parsers.ET, "iterparse", record_iterparse)
    iterator = parsers.parse_usgs_skos_rdf(path, context)

    with pytest.raises(
        parsers.SourceParseError,
        match="source_(?:path_)?changed_during_parse",
    ):
        next(iterator)
    assert len(observed_handles) == 1


def test_rdf_rejects_semantic_local_names_from_evil_namespace(tmp_path: Path) -> None:
    path = tmp_path / "evil-namespace.rdf"
    path.write_text(
        f"""<rdf:RDF xmlns:rdf="{parsers.RDF_NS}"
xmlns:skos="{parsers.SKOS_NS}" xmlns:evil="https://evil.invalid/">
<skos:Concept rdf:about="https://example.test/concept/1">
<evil:prefLabel xml:lang="en">Injected label</evil:prefLabel>
</skos:Concept></rdf:RDF>""",
        encoding="utf-8",
    )
    with pytest.raises(
        parsers.SourceParseError, match="rdf_namespace_mismatch:prefLabel"
    ):
        list(parsers.parse_usgs_skos_rdf(path, _file_context(path, "usgs")))


def _epub_members() -> dict[str, bytes]:
    return {
        "mimetype": b"application/epub+zip",
        "META-INF/container.xml": b"""<?xml version="1.0"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OPS/package.opf"
    media-type="application/oebps-package+xml"/></rootfiles>
</container>""",
        "OPS/package.opf": b"""<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0"
  unique-identifier="pub-id" xmlns:dc="http://purl.org/dc/elements/1.1/">
  <metadata><dc:identifier id="pub-id">fixture-book</dc:identifier></metadata>
  <manifest>
    <item id="chapter-1" href="c1.xhtml" media-type="application/xhtml+xml"/>
    <item id="chapter-2" href="c2.xhtml" media-type="application/xhtml+xml"/>
    <item id="navigation" href="nav.xhtml" media-type="application/xhtml+xml"
      properties="nav"/>
    <item id="rights" href="copyright_acknowledgements_ccby.html"
      media-type="application/xhtml+xml"/>
  </manifest>
  <spine><itemref idref="chapter-1"/><itemref idref="chapter-2"/></spine>
</package>""",
        "OPS/nav.xhtml": b"""<html xmlns="http://www.w3.org/1999/xhtml"
xmlns:epub="http://www.idpf.org/2007/ops"><body><nav epub:type="toc">
<a href="c1.xhtml">Foundations</a><a href="c2.xhtml">Measurements</a>
</nav></body></html>""",
        "OPS/copyright_acknowledgements_ccby.html": b"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml"><body>Siyavula
<a href="http://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>
</body></html>""",
        "OPS/c1.xhtml": b"""<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Foundations</title></head><body><p>Start here.</p></body></html>""",
        "OPS/c2.xhtml": b"""<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Measurements</title></head><body>
<p>Measure 12 units.</p><table><tr><td>12</td></tr></table>
<img src="missing.png" alt="required diagram"/>
</body></html>""",
    }


def test_siyavula_epub_resolves_spine_and_context_flags(tmp_path: Path) -> None:
    path = tmp_path / "book.epub"
    _write_zip(path, _epub_members())

    units = list(parsers.parse_siyavula_epub(path, _file_context(path, "siyavula")))

    assert [unit.title for unit in units] == ["Foundations", "Measurements"]
    assert units[0].edges == ()
    assert units[1].edges == ()
    assert (
        parsers.SourceFacet(
            "structural_sequence_evidence",
            ("epub_spine_position:2",),
        )
        in units[1].facets
    )
    assert units[1].flags == parsers.SourceFlags(
        missing_media=True,
        has_table=True,
        has_numeric_content=True,
        present_visual_media=False,
        uninterpreted_nontext_media=True,
        visual_context_quarantined=True,
    )


def test_epub_rejects_ambiguous_package_and_unsafe_reference(tmp_path: Path) -> None:
    members = _epub_members()
    members[
        "META-INF/container.xml"
    ] = b"""<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
<rootfile full-path="OPS/package.opf"/><rootfile full-path="OPS/other.opf"/>
</container>"""
    members["OPS/other.opf"] = members["OPS/package.opf"]
    path = tmp_path / "ambiguous.epub"
    _write_zip(path, members)
    with pytest.raises(
        parsers.SourceParseError,
        match="epub_ambiguous_or_missing_package",
    ):
        list(parsers.parse_siyavula_epub(path, _file_context(path, "siyavula")))

    members = _epub_members()
    members["OPS/package.opf"] = members["OPS/package.opf"].replace(
        b'href="c1.xhtml"', b'href="../../c1.xhtml"'
    )
    unsafe = tmp_path / "unsafe.epub"
    _write_zip(unsafe, members)
    with pytest.raises(parsers.SourceParseError, match="unsafe_archive_reference"):
        list(
            parsers.parse_siyavula_epub(
                unsafe,
                _file_context(unsafe, "siyavula"),
            )
        )


@pytest.mark.parametrize(
    ("case", "match"),
    (
        ("container", "epub_container_namespace_mismatch:rootfile"),
        ("opf", "epub_opf_namespace_mismatch:item"),
        ("xhtml", "epub_xhtml_namespace_mismatch:body"),
    ),
)
def test_epub_rejects_semantic_local_names_from_evil_namespaces(
    tmp_path: Path,
    case: str,
    match: str,
) -> None:
    members = _epub_members()
    if case == "container":
        members["META-INF/container.xml"] = (
            members["META-INF/container.xml"]
            .replace(
                b"<rootfile ",
                b'<evil:rootfile xmlns:evil="https://evil.invalid/" ',
            )
            .replace(b"</rootfiles>", b"</rootfiles>")
        )
    elif case == "opf":
        members["OPS/package.opf"] = members["OPS/package.opf"].replace(
            b'<item id="chapter-1"',
            b'<evil:item xmlns:evil="https://evil.invalid/" id="chapter-1"',
        )
    else:
        members["OPS/c1.xhtml"] = (
            members["OPS/c1.xhtml"]
            .replace(
                b"<body>",
                b'<evil:body xmlns:evil="https://evil.invalid/">',
            )
            .replace(b"</body>", b"</evil:body>")
        )
    path = tmp_path / f"evil-{case}.epub"
    _write_zip(path, members)
    with pytest.raises(parsers.SourceParseError, match=match):
        list(parsers.parse_siyavula_epub(path, _file_context(path, "siyavula")))


@pytest.mark.parametrize(
    ("mutation", "match"),
    (
        (b'id="chapter-2"', "epub_duplicate_manifest_id"),
        (b'href="c2.xhtml"', "epub_duplicate_manifest_target"),
    ),
)
def test_epub_rejects_duplicate_manifest_ids_and_resolved_targets(
    tmp_path: Path,
    mutation: bytes,
    match: str,
) -> None:
    members = _epub_members()
    replacement = (
        b'id="chapter-1"' if mutation.startswith(b"id=") else b'href="c1.xhtml"'
    )
    members["OPS/package.opf"] = members["OPS/package.opf"].replace(
        mutation,
        replacement,
    )
    path = tmp_path / f"duplicate-{match}.epub"
    _write_zip(path, members)
    with pytest.raises(parsers.SourceParseError, match=match):
        list(parsers.parse_siyavula_epub(path, _file_context(path, "siyavula")))


@pytest.mark.parametrize(
    ("mutation", "match"),
    (
        (
            lambda value: value.replace(b'version="3.0"', b'version="2.0"'),
            "epub_package_version_invalid",
        ),
        (
            lambda value: value.replace(b'id="pub-id"', b'id="other"'),
            "epub_package_unique_identifier_link_invalid",
        ),
        (
            lambda value: value.replace(
                b"</metadata>", b"<creator>wrong namespace</creator></metadata>"
            ),
            "epub_opf_namespace_mismatch:creator",
        ),
        (
            lambda value: value.replace(b' properties="nav"', b""),
            "epub_unique_navigation_manifest_item_required",
        ),
        (
            lambda value: value.replace(
                b'<itemref idref="chapter-2"/>',
                b'<itemref idref="chapter-1"/>',
            ),
            "epub_duplicate_spine_identity",
        ),
        (
            lambda value: value.replace(
                b'href="c1.xhtml"', b'href="https://example.invalid/c1.xhtml"'
            ),
            "epub_remote_manifest_item_rejected",
        ),
        (
            lambda value: value.replace(
                b'id="rights" href="copyright_acknowledgements_ccby.html"\n      media-type="application/xhtml+xml"',
                b'id="rights" href="copyright_acknowledgements_ccby.html"\n      media-type="text/plain"',
            ),
            "epub_rights_manifest_binding_invalid",
        ),
    ),
)
def test_epub_package_authority_links_fail_closed(
    tmp_path: Path,
    mutation,
    match: str,
) -> None:
    members = _epub_members()
    members["OPS/package.opf"] = mutation(members["OPS/package.opf"])
    path = tmp_path / f"authority-{match}.epub"
    _write_zip(path, members)

    with pytest.raises(parsers.SourceParseError, match=match):
        list(parsers.parse_siyavula_epub(path, _file_context(path, "siyavula")))


@pytest.mark.parametrize(
    ("member", "mutation", "match"),
    (
        (
            "OPS/nav.xhtml",
            lambda value: value.replace(b'epub:type="toc"', b'epub:type="page-list"'),
            "epub_navigation_unique_toc_role_required",
        ),
        (
            "OPS/nav.xhtml",
            lambda value: value.replace(
                b'href="c1.xhtml"', b'href="https://example.invalid/c1.xhtml"'
            ),
            "epub_remote_navigation_target_rejected",
        ),
        (
            "OPS/copyright_acknowledgements_ccby.html",
            lambda _value: (
                b'<!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml">'
                b"<body>Siyavula http://creativecommons.org/licenses/by/4.0/"
                b"</body></html>"
            ),
            "epub_rights_structured_license_link_missing",
        ),
    ),
)
def test_epub_navigation_and_rights_structure_fail_closed(
    tmp_path: Path,
    member: str,
    mutation,
    match: str,
) -> None:
    members = _epub_members()
    members[member] = mutation(members[member])
    path = tmp_path / f"structure-{match}.epub"
    _write_zip(path, members)

    with pytest.raises(parsers.SourceParseError, match=match):
        list(parsers.parse_siyavula_epub(path, _file_context(path, "siyavula")))


def test_epub_present_visual_media_is_distinct_and_dependency_is_retained(
    tmp_path: Path,
) -> None:
    members = _epub_members()
    members["OPS/c2.xhtml"] = members["OPS/c2.xhtml"].replace(
        b"missing.png", b"diagram.png"
    )
    members["OPS/diagram.png"] = b"synthetic image bytes"
    path = tmp_path / "present-visual.epub"
    _write_zip(path, members)

    units = list(parsers.parse_siyavula_epub(path, _file_context(path, "siyavula")))
    visual = units[1]

    assert visual.flags == parsers.SourceFlags(
        missing_media=False,
        has_table=True,
        has_numeric_content=True,
        present_visual_media=True,
        uninterpreted_nontext_media=True,
        visual_context_quarantined=True,
    )
    assert (
        parsers.SourceFacet("media_dependency_member", ("OPS/diagram.png",))
        in visual.facets
    )


@pytest.mark.parametrize(
    ("markup", "member", "present_visual"),
    (
        (b"<figure><p>caption only</p></figure>", None, False),
        (b'<object data="object.bin"/>', "OPS/object.bin", True),
        (b'<audio src="sound.bin"/>', "OPS/sound.bin", False),
    ),
)
def test_epub_uninterpreted_nontext_always_requires_visual_context_quarantine(
    tmp_path: Path,
    markup: bytes,
    member: str | None,
    present_visual: bool,
) -> None:
    members = _epub_members()
    members["OPS/c1.xhtml"] = members["OPS/c1.xhtml"].replace(
        b"</body>", markup + b"</body>"
    )
    if member is not None:
        members[member] = b"synthetic dependency"
    path = tmp_path / f"quarantine-{present_visual}-{member is not None}.epub"
    _write_zip(path, members)

    unit = next(
        iter(parsers.parse_siyavula_epub(path, _file_context(path, "siyavula")))
    )

    assert unit.flags.present_visual_media is present_visual
    assert unit.flags.uninterpreted_nontext_media is True
    assert unit.flags.visual_context_quarantined is True


@pytest.mark.parametrize(
    "flags",
    (
        parsers.SourceFlags(False, False, False, True, False, True),
        parsers.SourceFlags(False, False, False, False, True, False),
        parsers.SourceFlags(True, False, False, False, True, False),
    ),
)
def test_source_flags_cannot_bypass_nontext_quarantine(
    flags: parsers.SourceFlags,
) -> None:
    with pytest.raises(
        parsers.SourceParseError,
        match="source_flags_media_quarantine_invariant_invalid",
    ):
        parsers._validate_source_flags(flags)


def _production_epub_structure_checks(spec: Any) -> dict[str, Any]:
    identity = spec.epub_identity
    assert identity is not None
    metadata = {
        "dc_creator_values": list(identity.opf_creator_values),
        "dc_identifier_values": [identity.identifier],
        "dc_language_values": [identity.language],
        "dc_publisher_values": list(identity.opf_publisher_values),
        "dc_rights_values": list(identity.opf_rights_values),
        "dc_subject_values": list(identity.opf_subject_values),
        "dc_title_values": [identity.title],
        "dcterms_modified_values": [identity.modified],
        "grade_metadata_values": [],
    }
    return {
        "all_member_CRCs_verified": True,
        "container_and_declared_OPF_verified": True,
        "internal_member_sha256": {
            "container": "sha256:" + "0" * 64,
            "navigation": "sha256:" + identity.navigation_sha256,
            "opf": "sha256:" + identity.opf_sha256,
            "rights": "sha256:" + identity.rights_member_sha256,
        },
        "manifest_and_spine_verified": True,
        "metadata_observation": metadata,
        "mimetype_first_and_stored": True,
        "navigation_toc_structure": {
            "manifest_media_type": "application/xhtml+xml",
            "manifest_properties": ["nav"],
            "toc_link_count": 12,
            "toc_nav_count": 1,
        },
        "package_identity": {
            "unique_identifier_id": "pub-id",
            "unique_identifier_linked": True,
            "version": "3.0",
        },
        "preregistered_catalogue_conflict_context_bound": True,
        "rights_context": {
            "artifact_notice_license_id": identity.artifact_notice_license_id,
            "artifact_notice_url": identity.artifact_notice_url,
            "catalogue_license_id": identity.catalogue_license_id,
            "catalogue_or_terms_evidence_runtime_verified": False,
            "preregistered_rights_subject_template_mismatch": (
                identity.rights_subject_template_mismatch
            ),
            "resolved_license_id": identity.resolved_license_id,
        },
        "rights_link_structure": {
            "artifact_notice_url": identity.artifact_notice_url,
            "manifest_media_type": "application/xhtml+xml",
            "structured_license_link_count": 1,
        },
        "subject_grade_evidence": {
            "catalogue": {
                "evidence_root_sha256": "sha256:"
                + identity.catalogue_evidence_root_sha256,
                "grade": identity.catalogue_grade,
                "subject": identity.catalogue_subject,
            },
            "download_filename": {
                "filename": spec.filename,
                "grade_token": identity.filename_grade_token,
                "subject_token": identity.filename_subject_token,
            },
            "opf_observation": {
                "dc_subject_values": list(identity.opf_subject_values),
                "grade_metadata_values": [],
                "grade_assertion_present": False,
                "subject_assertion_present": bool(identity.opf_subject_values),
            },
        },
        "xhtml_manifest_item_count": 20,
        "spine_item_count": 18,
    }


def test_production_epub_receipt_validation_is_contract_exact() -> None:
    spec = next(
        source
        for source in commercial.DIRECT_SOURCES
        if source.source_id == "siyavula_mathematics_grade_10_cc_by"
    )
    checks = _production_epub_structure_checks(spec)

    parsers._validate_structure_checks("safe_crc_verified_epub", checks, spec)
    checks["internal_member_sha256"]["container"] = "sha256:" + "9" * 64
    parsers._validate_structure_checks("safe_crc_verified_epub", checks, spec)


@pytest.mark.parametrize(
    ("mutate", "match"),
    (
        (
            lambda checks: checks.pop("subject_grade_evidence"),
            "structure_schema_invalid",
        ),
        (
            lambda checks: checks["subject_grade_evidence"]["catalogue"].update(
                {"subject": "Physical Sciences"}
            ),
            "subject_grade_evidence_invalid",
        ),
        (
            lambda checks: checks["rights_context"].update(
                {"preregistered_rights_subject_template_mismatch": 1}
            ),
            "rights_context_invalid",
        ),
        (
            lambda checks: checks["internal_member_sha256"].update(
                {"opf": "sha256:" + "8" * 64}
            ),
            "internal_hash_mismatch",
        ),
        (
            lambda checks: checks["navigation_toc_structure"].update(
                {"manifest_properties": ["nav", "nav"]}
            ),
            "navigation_invalid",
        ),
        (
            lambda checks: checks["metadata_observation"].update(
                {"dc_subject_values": ["Mathematics"]}
            ),
            "metadata_observation_invalid",
        ),
    ),
)
def test_production_epub_receipt_rejects_self_consistent_authority_lies(
    mutate,
    match: str,
) -> None:
    spec = next(
        source
        for source in commercial.DIRECT_SOURCES
        if source.source_id == "siyavula_mathematics_grade_10_cc_by"
    )
    checks = _production_epub_structure_checks(spec)
    mutate(checks)

    with pytest.raises(parsers.SourceParseError, match=match):
        parsers._validate_structure_checks("safe_crc_verified_epub", checks, spec)


def test_zip_rejects_fifo_member_before_archive_read(tmp_path: Path) -> None:
    path = tmp_path / "fifo.zip"
    info = zipfile.ZipInfo("nalt-core.ttl")
    info.create_system = 3
    info.external_attr = (stat.S_IFIFO | 0o600) << 16
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(info, _nalt_turtle())

    with pytest.raises(
        parsers.SourceParseError,
        match="archive_non_regular_member_rejected",
    ):
        list(parsers.parse_nalt_turtle_zip(path, _file_context(path, "nalt")))


def _write_openstax_tree(root: Path) -> None:
    (root / "modules/m1").mkdir(parents=True)
    (root / "modules/m2").mkdir(parents=True)
    (root / "collections").mkdir()
    (root / "modules/m1/index.cnxml").write_text(
        """<document xmlns="http://cnx.rice.edu/cnxml" id="m1">
<title>First module</title><metadata><content-id>m1</content-id></metadata>
<content><para>Concept foundation.</para></content></document>""",
        encoding="utf-8",
    )
    (root / "modules/m2/index.cnxml").write_text(
        """<document xmlns="http://cnx.rice.edu/cnxml" id="m2">
<title>Second module</title><metadata><content-id>m2</content-id></metadata>
<content><para>Value 42.</para><table><tgroup/></table>
<figure><image src="diagram.svg"/></figure></content></document>""",
        encoding="utf-8",
    )
    (root / "collections/book.collection.xml").write_text(
        """<collection xmlns="http://cnx.rice.edu/collxml">
<metadata><title>Fixture book</title></metadata><content>
<module document="m1"/><module document="m2"/></content></collection>""",
        encoding="utf-8",
    )


def test_openstax_cnxml_keeps_membership_and_unadjudicated_order(
    tmp_path: Path,
) -> None:
    root = tmp_path / "openstax"
    _write_openstax_tree(root)

    units = list(parsers.parse_openstax_tree(root, _tree_context(root)))
    by_key = {unit.source_key: unit for unit in units}

    assert set(by_key) == {
        "collection:collections/book.collection.xml",
        "module:m1",
        "module:m2",
    }
    assert by_key["module:m1"].edges[0].predicate == "collection_membership"
    assert {(edge.edge_type, edge.predicate) for edge in by_key["module:m2"].edges} == {
        ("hierarchy", "collection_membership"),
    }
    assert by_key["module:m2"].facets == (
        parsers.SourceFacet(
            "structural_sequence_evidence",
            ("collection:collections/book.collection.xml:position:2",),
        ),
    )
    assert by_key["module:m2"].flags == parsers.SourceFlags(
        missing_media=True,
        has_table=True,
        has_numeric_content=True,
        present_visual_media=False,
        uninterpreted_nontext_media=True,
        visual_context_quarantined=True,
    )


def test_openstax_rejects_symlinks_and_missing_module_reference(tmp_path: Path) -> None:
    root = tmp_path / "linked"
    _write_openstax_tree(root)
    context = _tree_context(root)
    os.symlink(root / "modules/m1/index.cnxml", root / "modules/m1/alias.cnxml")
    with pytest.raises(parsers.SourceParseError, match="openstax_symlink_rejected"):
        list(parsers.parse_openstax_tree(root, context))

    clean = tmp_path / "missing"
    _write_openstax_tree(clean)
    collection = clean / "collections/book.collection.xml"
    collection.write_text(
        collection.read_text(encoding="utf-8").replace("m2", "missing"),
        encoding="utf-8",
    )
    with pytest.raises(
        parsers.SourceParseError,
        match="openstax_collection_reference_missing_module",
    ):
        list(parsers.parse_openstax_tree(clean, _tree_context(clean)))


def test_openstax_rejects_extra_file_and_git_metadata_against_manifest(
    tmp_path: Path,
) -> None:
    extra_root = tmp_path / "extra"
    _write_openstax_tree(extra_root)
    extra_context = _tree_context(extra_root)
    (extra_root / "rogue.txt").write_text("unreceipted", encoding="utf-8")
    with pytest.raises(
        parsers.SourceParseError,
        match="openstax_file_manifest_mismatch",
    ):
        list(parsers.parse_openstax_tree(extra_root, extra_context))

    git_root = tmp_path / "git"
    _write_openstax_tree(git_root)
    git_context = _tree_context(git_root)
    (git_root / ".git").mkdir()
    (git_root / ".git/config").write_text("[core]", encoding="utf-8")
    with pytest.raises(
        parsers.SourceParseError,
        match="openstax_git_metadata_rejected",
    ):
        list(parsers.parse_openstax_tree(git_root, git_context))


def test_openstax_inventory_streams_wide_directories_without_eager_listdir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "streamed-inventory"
    _write_openstax_tree(root)
    context = _tree_context(root)

    def eager_listdir_forbidden(*_args: Any, **_kwargs: Any) -> list[str]:
        raise AssertionError("OpenStax inventory used eager listdir")

    monkeypatch.setattr(parsers.os, "listdir", eager_listdir_forbidden)
    units = list(parsers.parse_openstax_tree(root, context))
    assert len(units) == 3


def test_openstax_inventory_bounds_unmanifested_wide_directory_bomb(
    tmp_path: Path,
) -> None:
    root = tmp_path / "wide-inventory"
    _write_openstax_tree(root)
    context = _tree_context(root)
    for index in range(8):
        (root / f"rogue-{index}").mkdir()
    limits = replace(parsers.DEFAULT_LIMITS, max_files=5)
    with pytest.raises(
        parsers.SourceParseError,
        match="openstax_(?:entry|directory_count)_limit_exceeded",
    ):
        list(parsers.parse_openstax_tree(root, context, limits))


def test_openstax_root_swap_releases_no_partial_unit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "openstax-swap"
    _write_openstax_tree(root)
    context = _tree_context(root)
    original_reader = parsers._read_openstax_manifest_file
    swapped = False

    def swap_root_then_read(*args: Any, **kwargs: Any) -> bytes:
        nonlocal swapped
        if not swapped:
            swapped = True
            held_root = tmp_path / "openstax-held"
            root.rename(held_root)
            shutil.copytree(held_root, root)
        return original_reader(*args, **kwargs)

    monkeypatch.setattr(
        parsers,
        "_read_openstax_manifest_file",
        swap_root_then_read,
    )
    iterator = parsers.parse_openstax_tree(root, context)

    with pytest.raises(
        parsers.SourceParseError,
        match="openstax_root_(?:path_changed|changed_during_parse)",
    ):
        next(iterator)


@pytest.mark.parametrize(
    ("case", "match"),
    (
        ("cnxml", "openstax_cnxml_namespace_mismatch"),
        ("collxml", "openstax_collxml_namespace_mismatch"),
    ),
)
def test_openstax_rejects_evil_cnxml_and_collxml_namespaces(
    tmp_path: Path,
    case: str,
    match: str,
) -> None:
    root = tmp_path / case
    _write_openstax_tree(root)
    target = (
        root / "modules/m1/index.cnxml"
        if case == "cnxml"
        else root / "collections/book.collection.xml"
    )
    target.write_text(
        target.read_text(encoding="utf-8").replace(
            "http://cnx.rice.edu/cnxml"
            if case == "cnxml"
            else "http://cnx.rice.edu/collxml",
            "https://evil.invalid/",
        ),
        encoding="utf-8",
    )
    with pytest.raises(parsers.SourceParseError, match=match):
        list(parsers.parse_openstax_tree(root, _tree_context(root)))


def test_dispatch_rejects_unknown_format(tmp_path: Path) -> None:
    with pytest.raises(parsers.SourceParseError, match="unsupported_source_format"):
        list(
            parsers.iter_unverified_source_units(
                "unknown", tmp_path / "unused", _context()
            )
        )


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("chunk_count", True),
        ("total_attempts", True),
        ("every_response_206", 1),
        ("every_content_range_exact", 1),
        ("per_chunk_attempts", [True]),
    ),
)
def test_direct_transfer_evidence_rejects_json_scalar_type_confusion(
    field: str,
    replacement: Any,
) -> None:
    spec = SimpleNamespace(
        expected_bytes=1,
        transfer_mode="fixed_range_chunks_v1",
        fixed_chunk_bytes=8_388_608,
    )
    evidence = {
        "schema_version": "cur0s_direct_transfer_evidence_v1",
        "mode": "fixed_range_chunks_v1",
        "fixed_chunk_bytes": 8_388_608,
        "chunk_count": 1,
        "per_chunk_attempts": [1],
        "total_attempts": 1,
        "every_response_206": True,
        "every_content_range_exact": True,
        "no_overlap": True,
        "no_gap": True,
        "held_destination_single_inode": True,
        "full_length_and_sha256_verified": True,
    }
    evidence[field] = replacement

    with pytest.raises(
        parsers.SourceParseError,
        match="acquisition_transfer_evidence_invalid",
    ):
        parsers._validate_direct_transfer_evidence(evidence, spec, 1)


def test_production_dispatch_derives_identity_rights_and_format_from_transaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate, spec, context, expected = _production_obo_candidate(
        tmp_path, monkeypatch
    )

    signature = inspect.signature(parsers.iter_verified_normalized_source_units)
    assert "context" not in signature.parameters
    assert "source_format" not in signature.parameters
    envelopes = list(
        parsers.iter_verified_normalized_source_units(
            candidate,
            spec.source_id,
            expected,
        )
    )
    units = [envelope.unit for envelope in envelopes]

    assert [unit.source_key for unit in units] == ["X:1"]
    assert units[0].rights == parsers.RightsRecord(
        context.license_id,
        context.license_class,
        context.rights_proof,
    )
    assert units[0].provenance.source_sha256 == context.source_sha256
    verification = envelopes[0].production_verification
    assert verification.production_transaction_verified is True
    assert verification.run_id == "20260712T120000Z_cur0s_commercial_sources_v1"
    assert verification.source_id == spec.source_id
    assert verification.source_artifact_sha256 == context.source_sha256
    verification_body = verification.to_dict()
    verification_root = verification_body.pop("verification_root_sha256")
    assert verification_root == parsers.canonical_sha256(verification_body)


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("mode", "single_response_v1"),
        ("fixed_chunk_bytes", None),
        ("chunk_count", True),
        ("per_chunk_attempts", [True]),
        ("total_attempts", True),
        ("every_response_206", 1),
        ("every_content_range_exact", 1),
        ("no_gap", False),
        ("held_destination_single_inode", False),
        ("full_length_and_sha256_verified", False),
    ),
)
def test_production_dispatch_rejects_forged_direct_transfer_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    replacement: Any,
) -> None:
    candidate, spec, _context_value, expected = _production_obo_candidate(
        tmp_path,
        monkeypatch,
    )
    receipt = json.loads((candidate / "receipt.json").read_text(encoding="utf-8"))
    summaries = receipt["source_inspection_summaries"]
    summaries[0]["transfer_evidence"][field] = replacement
    _rewrite_candidate_receipt(candidate, "source_inspection_summaries", summaries)
    expected = _expect_current_receipt(candidate, expected)

    with pytest.raises(
        parsers.SourceParseError,
        match="acquisition_transfer_evidence_invalid",
    ):
        list(
            parsers.iter_verified_normalized_source_units(
                candidate,
                spec.source_id,
                expected,
            )
        )


def test_production_dispatch_rejects_boolean_required_marker_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate, spec, _context_value, expected = _production_obo_candidate(
        tmp_path,
        monkeypatch,
    )
    receipt = json.loads((candidate / "receipt.json").read_text(encoding="utf-8"))
    summaries = receipt["source_inspection_summaries"]
    summaries[0]["required_marker_count"] = True
    _rewrite_candidate_receipt(candidate, "source_inspection_summaries", summaries)
    expected = _expect_current_receipt(candidate, expected)

    with pytest.raises(
        parsers.SourceParseError,
        match="acquisition_inspection_marker_count_invalid",
    ):
        list(
            parsers.iter_verified_normalized_source_units(
                candidate,
                spec.source_id,
                expected,
            )
        )


@pytest.mark.parametrize(
    ("receipt_field", "nested_field", "replacement", "match"),
    (
        (
            "runtime_identity",
            "phone_private_runtime_guard_passed",
            1,
            "acquisition_runtime_identity_invalid",
        ),
        (
            "custody",
            "raw_payload_egressed",
            0,
            "acquisition_custody_claim_invalid",
        ),
        (
            "execution_claim",
            "claim_egressed",
            0,
            "acquisition_execution_claim_receipt_invalid",
        ),
        (
            "preterminal_resource_envelope_snapshot",
            "phone_execution_ordinal",
            True,
            "acquisition_resource_snapshot_claim_invalid",
        ),
        (
            "preterminal_resource_envelope_snapshot",
            "ephemeral_control_files_open_at_receipt",
            False,
            "acquisition_resource_snapshot_claim_invalid",
        ),
    ),
)
def test_production_dispatch_rejects_authority_json_scalar_type_confusion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    receipt_field: str,
    nested_field: str,
    replacement: Any,
    match: str,
) -> None:
    candidate, spec, _context_value, expected = _production_obo_candidate(
        tmp_path,
        monkeypatch,
    )
    receipt = json.loads((candidate / "receipt.json").read_text(encoding="utf-8"))
    nested = receipt[receipt_field]
    nested[nested_field] = replacement
    _rewrite_candidate_receipt(candidate, receipt_field, nested)
    expected = _expect_current_receipt(candidate, expected)

    with pytest.raises(parsers.SourceParseError, match=match):
        list(
            parsers.iter_verified_normalized_source_units(
                candidate,
                spec.source_id,
                expected,
            )
        )


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("same_pid_execveat_verified", 1),
        ("helper_dependency_swap_safety_claimed", 0),
    ),
)
def test_production_dispatch_rejects_native_attestation_scalar_type_confusion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    replacement: Any,
) -> None:
    candidate, spec, _context_value, expected = _production_obo_candidate(
        tmp_path,
        monkeypatch,
    )
    receipt = json.loads((candidate / "receipt.json").read_text(encoding="utf-8"))
    identity = receipt["source_execution_identity"]
    native_execution = identity["native_preflight_execution"]
    native_execution[field] = replacement
    _rewrite_candidate_receipt(candidate, "source_execution_identity", identity)
    expected = _expect_current_receipt(candidate, expected)

    with pytest.raises(
        parsers.SourceParseError,
        match="acquisition_native_preflight_execution_invalid",
    ):
        list(
            parsers.iter_verified_normalized_source_units(
                candidate,
                spec.source_id,
                expected,
            )
        )


def test_production_dispatch_rejects_boolean_source_root_artifact_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polymath_ai.corpus import cur0s_commercial_sources as commercial

    candidate, spec, _context_value, expected = _production_obo_candidate(
        tmp_path,
        monkeypatch,
    )
    receipt = json.loads((candidate / "receipt.json").read_text(encoding="utf-8"))
    source_root = receipt["source_root"]
    source_root["source_artifact_count"] = True
    source_root.pop("source_root_sha256")
    source_root["source_root_sha256"] = commercial.canonical_sha256(source_root)
    _rewrite_candidate_receipt(candidate, "source_root", source_root)
    expected = _expect_current_receipt(candidate, expected)

    with pytest.raises(
        parsers.SourceParseError,
        match="acquisition_source_root_claim_invalid",
    ):
        list(
            parsers.iter_verified_normalized_source_units(
                candidate,
                spec.source_id,
                expected,
            )
        )


def test_strict_binding_rejects_self_consistent_forged_rights(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate, spec, context, expected = _production_obo_candidate(
        tmp_path, monkeypatch
    )
    unit = next(
        parsers.iter_verified_normalized_source_units(
            candidate,
            spec.source_id,
            expected,
        )
    ).unit
    forged_value = unit.to_dict()
    forged_value["rights"] = {
        "license_id": "CC0-1.0",
        "license_class": "A",
        "rights_proof": "caller_assertion",
    }
    body = dict(forged_value)
    body.pop("canonical_sha256")
    forged_value["canonical_sha256"] = parsers.canonical_sha256(body)
    forged = parsers._source_unit_from_dict(forged_value)

    assert parsers.validate_source_unit(forged) is forged
    with pytest.raises(
        parsers.SourceParseError,
        match="source_unit_rights_binding_mismatch",
    ):
        parsers.validate_source_unit(forged, context)


def test_production_dispatch_rejects_receipt_complete_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate, spec, _context_value, expected = _production_obo_candidate(
        tmp_path,
        monkeypatch,
    )
    complete_path = candidate / "COMPLETE.json"
    complete_path.chmod(0o600)
    complete = json.loads(complete_path.read_text(encoding="utf-8"))
    complete["receipt_sha256"] = "sha256:" + "0" * 64
    _write_canonical_read_only(complete_path, complete)

    with pytest.raises(
        parsers.SourceParseError,
        match="acquisition_completion_binding_invalid",
    ):
        list(
            parsers.iter_verified_normalized_source_units(
                candidate,
                spec.source_id,
                expected,
            )
        )


def test_production_dispatch_rejects_self_consistent_forged_source_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polymath_ai.corpus import cur0s_commercial_sources as commercial

    candidate, spec, _context_value, expected = _production_obo_candidate(
        tmp_path,
        monkeypatch,
    )
    receipt_path = candidate / "receipt.json"
    complete_path = candidate / "COMPLETE.json"
    receipt_path.chmod(0o600)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["source_root"]["unreceipted_claim"] = True
    receipt.pop("receipt_root_sha256")
    receipt["receipt_root_sha256"] = commercial.canonical_sha256(receipt)
    receipt_payload = _write_canonical_read_only(receipt_path, receipt)
    complete_path.chmod(0o600)
    complete = json.loads(complete_path.read_text(encoding="utf-8"))
    complete["receipt_sha256"] = "sha256:" + hashlib.sha256(receipt_payload).hexdigest()
    complete["receipt_root_sha256"] = receipt["receipt_root_sha256"]
    complete["receipt_bytes"] = len(receipt_payload)
    _write_canonical_read_only(complete_path, complete)
    expected = _expect_current_receipt(candidate, expected)

    with pytest.raises(
        parsers.SourceParseError,
        match="acquisition_source_root_(?:schema|binding)_invalid",
    ):
        list(
            parsers.iter_verified_normalized_source_units(
                candidate,
                spec.source_id,
                expected,
            )
        )


@pytest.mark.parametrize(
    "field,replacement,match",
    [
        (
            "source_execution_identity",
            {},
            "acquisition_source_execution_identity_schema_invalid",
        ),
        ("runtime_identity", {}, "acquisition_runtime_identity_schema_invalid"),
        (
            "authority_bindings",
            {},
            "acquisition_authority_bindings_schema_invalid",
        ),
        ("custody", {}, "acquisition_custody_claim_invalid"),
        (
            "execution_claim",
            {},
            "acquisition_execution_claim_receipt_schema_invalid",
        ),
        (
            "source_inspection_summaries",
            [],
            "acquisition_inspection_summary_count_invalid",
        ),
        ("pending_transaction_links", [], "acquisition_receipt_binding_invalid"),
        ("nonclaims", [], "acquisition_receipt_binding_invalid"),
    ],
)
def test_production_dispatch_rejects_prior_empty_nested_authority_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    replacement: Any,
    match: str,
) -> None:
    candidate, spec, _context_value, expected = _production_obo_candidate(
        tmp_path,
        monkeypatch,
    )
    _rewrite_candidate_receipt(candidate, field, replacement)
    expected = _expect_current_receipt(candidate, expected)

    with pytest.raises(parsers.SourceParseError, match=match):
        list(
            parsers.iter_verified_normalized_source_units(
                candidate,
                spec.source_id,
                expected,
            )
        )


def test_production_dispatch_requires_stable_run_keyed_claim_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate, spec, _context_value, expected = _production_obo_candidate(
        tmp_path,
        monkeypatch,
    )
    claim_path = (
        parsers.PHONE_PACKAGE_ROOT / ".20260712T120000Z_cur0s_commercial_sources_v1."
        "cur0s_execution_claim.json"
    )
    claim_path.unlink()

    with pytest.raises(
        parsers.SourceParseError,
        match="terminal_artifact_open_failed",
    ):
        list(
            parsers.iter_verified_normalized_source_units(
                candidate,
                spec.source_id,
                expected,
            )
        )


def test_production_dispatch_requires_out_of_band_dual_authority_anchor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate, spec, _context_value, expected = _production_obo_candidate(
        tmp_path,
        monkeypatch,
    )
    with pytest.raises(
        parsers.SourceParseError,
        match="production_authority_expectation_required",
    ):
        list(
            parsers.iter_verified_normalized_source_units(
                candidate,
                spec.source_id,
                {},  # type: ignore[arg-type]
            )
        )
    wrong_preregistration = parsers.ProductionAuthorityExpectation(
        preregistration_sha256="sha256:" + "0" * 64,
        acquisition_receipt_sha256=expected.acquisition_receipt_sha256,
    )
    with pytest.raises(
        parsers.SourceParseError,
        match="acquisition_preregistration_out_of_band_mismatch",
    ):
        list(
            parsers.iter_verified_normalized_source_units(
                candidate,
                spec.source_id,
                wrong_preregistration,
            )
        )
    wrong_receipt = parsers.ProductionAuthorityExpectation(
        preregistration_sha256=expected.preregistration_sha256,
        acquisition_receipt_sha256="sha256:" + "0" * 64,
    )
    with pytest.raises(
        parsers.SourceParseError,
        match="acquisition_receipt_out_of_band_mismatch",
    ):
        list(
            parsers.iter_verified_normalized_source_units(
                candidate,
                spec.source_id,
                wrong_receipt,
            )
        )


def test_production_dispatch_rejects_self_consistent_narrative_without_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate, spec, _context_value, expected = _production_obo_candidate(
        tmp_path,
        monkeypatch,
    )
    action_root = candidate.parent.parent
    for name in (
        "preregistration.json",
        "native_preflight.manifest",
        "native_launch_envelope.json",
        "native_preflight_build_receipt.json",
        "cur0s_native_preflight",
    ):
        (action_root / name).unlink()
    with pytest.raises(
        parsers.SourceParseError,
        match="acquisition_preregistration_open_failed",
    ):
        list(
            parsers.iter_verified_normalized_source_units(
                candidate,
                spec.source_id,
                expected,
            )
        )


@pytest.mark.parametrize(
    "artifact_name,mode,match",
    [
        (
            "cur0s_native_preflight",
            0o700,
            "acquisition_native_binary_artifact_mismatch",
        ),
        (
            "native_launch_envelope.json",
            0o600,
            "acquisition_native_launch_envelope_mismatch",
        ),
        (
            "native_preflight_build_receipt.json",
            0o600,
            "acquisition_native_build_receipt_artifact_mismatch",
        ),
    ],
)
def test_production_dispatch_rejects_forged_retained_native_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    artifact_name: str,
    mode: int,
    match: str,
) -> None:
    candidate, spec, _context_value, expected = _production_obo_candidate(
        tmp_path,
        monkeypatch,
    )
    artifact = candidate.parent.parent / artifact_name
    artifact.chmod(0o600)
    if artifact_name == "native_launch_envelope.json":
        _write_canonical_private(artifact, {"forged": True})
    elif artifact_name == "native_preflight_build_receipt.json":
        _write_canonical_private(
            artifact,
            {"forged": True},
            trailing_newline=False,
        )
    else:
        artifact.write_bytes(b"forged-retained-artifact")
    artifact.chmod(mode)
    with pytest.raises(parsers.SourceParseError, match=match):
        list(
            parsers.iter_verified_normalized_source_units(
                candidate,
                spec.source_id,
                expected,
            )
        )


def test_production_dispatch_rejects_checkout_blob_forgery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate, spec, _context_value, expected = _production_obo_candidate(
        tmp_path,
        monkeypatch,
    )
    preregistration = json.loads(
        (candidate.parent.parent / "preregistration.json").read_text(encoding="utf-8")
    )
    checkout = Path(
        preregistration["native_preflight"]["execution_layout"]["checkout_root"]
    )
    source_file = checkout / parsers.BOUND_SOURCE_FILES[0]
    source_file.write_bytes(b"forged checkout blob\n")
    source_file.chmod(0o600)
    with pytest.raises(
        parsers.SourceParseError,
        match="acquisition_checkout_source_binding_mismatch",
    ):
        list(
            parsers.iter_verified_normalized_source_units(
                candidate,
                spec.source_id,
                expected,
            )
        )


def test_production_dispatch_rejects_checkout_head_forgery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate, spec, _context_value, expected = _production_obo_candidate(
        tmp_path,
        monkeypatch,
    )
    preregistration = json.loads(
        (candidate.parent.parent / "preregistration.json").read_text(encoding="utf-8")
    )
    checkout = Path(
        preregistration["native_preflight"]["execution_layout"]["checkout_root"]
    )
    head = checkout / ".git/HEAD"
    head.write_text("3" * 40 + "\n", encoding="ascii")
    head.chmod(0o600)
    with pytest.raises(
        parsers.SourceParseError,
        match="acquisition_checkout_HEAD_mismatch",
    ):
        list(
            parsers.iter_verified_normalized_source_units(
                candidate,
                spec.source_id,
                expected,
            )
        )


def test_production_dispatch_rejects_claim_abort_complete_coexistence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate, spec, _context_value, expected = _production_obo_candidate(
        tmp_path,
        monkeypatch,
    )
    abort_path = (
        parsers.PHONE_PACKAGE_ROOT
        / ".20260712T120000Z_cur0s_commercial_sources_v1.cur0s_ABORT.json"
    )
    _write_canonical_read_only(
        abort_path,
        {
            "schema_version": "cur0s_commercial_sources_abort_v1",
            "state": "failed_scope_terminal",
        },
    )
    with pytest.raises(
        parsers.SourceParseError,
        match="acquisition_conflicting_terminal_resolutions",
    ):
        list(
            parsers.iter_verified_normalized_source_units(
                candidate,
                spec.source_id,
                expected,
            )
        )


def test_production_dispatch_rejects_multiple_candidate_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate, spec, _context_value, expected = _production_obo_candidate(
        tmp_path,
        monkeypatch,
    )
    second = candidate.parent / "candidate-002"
    second.mkdir(mode=0o700)
    with pytest.raises(
        parsers.SourceParseError,
        match="acquisition_multiple_candidate_resolution",
    ):
        list(
            parsers.iter_verified_normalized_source_units(
                candidate,
                spec.source_id,
                expected,
            )
        )


def test_production_dispatch_rejects_stale_native_execution_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate, spec, _context_value, expected = _production_obo_candidate(
        tmp_path,
        monkeypatch,
    )
    receipt = json.loads((candidate / "receipt.json").read_text(encoding="utf-8"))
    identity = receipt["source_execution_identity"]
    stale_execution = dict(identity["native_preflight_execution"])
    stale_execution.pop("outer_launch_contract_sha256")
    identity = {**identity, "native_preflight_execution": stale_execution}
    _rewrite_candidate_receipt(candidate, "source_execution_identity", identity)
    expected = _expect_current_receipt(candidate, expected)
    with pytest.raises(
        parsers.SourceParseError,
        match="acquisition_native_preflight_execution_schema_invalid",
    ):
        list(
            parsers.iter_verified_normalized_source_units(
                candidate,
                spec.source_id,
                expected,
            )
        )
