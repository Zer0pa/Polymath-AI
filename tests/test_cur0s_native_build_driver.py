"""Synthetic host tests for the phone-only CUR-0S native build driver."""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import struct
import subprocess
import sys
import time
from types import ModuleType

import pytest

from polymath_ai.corpus import cur0s_commercial_sources as commercial


ROOT = Path(__file__).resolve().parents[1]
DRIVER_PATH = ROOT / "scripts/termux/build_cur0s_native_preflight.py"


def _load_driver() -> ModuleType:
    name = "_test_cur0s_native_build_driver"
    spec = importlib.util.spec_from_file_location(name, DRIVER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


driver = _load_driver()
NATIVE_PREFLIGHT_SOURCE_FILES = driver.NATIVE_SOURCE_FILES
RUN_ID = "20260712T120000Z_cur0s_commercial_sources_v1"


def _valid_aarch64_elf() -> bytes:
    payload = bytearray(0x500)
    program_offset = 64
    program_count = 6
    interpreter = b"/system/bin/linker64\0"
    interpreter_offset = 0x200
    dynamic_offset = 0x240
    string_offset = 0x300
    string_table = b"\0libc.so\0"
    note_offset = 0x380
    note_name = b"Android\0"
    note_description = (
        struct.pack("<I", 30)
        + b"r29\0".ljust(64, b"\0")
        + b"14206865\0".ljust(64, b"\0")
    )
    note = (
        struct.pack("<III", len(note_name), len(note_description), 1)
        + note_name
        + note_description
    )
    base = 0x400000

    header = struct.pack(
        "<16sHHIQQQIHHHHHH",
        b"\x7fELF\x02\x01\x01" + (b"\0" * 9),
        3,
        183,
        1,
        base,
        program_offset,
        0,
        0,
        64,
        56,
        program_count,
        0,
        0,
        0,
    )
    payload[:64] = header
    dynamic_entries = (
        (1, 1),
        (3, base + dynamic_offset + 0x20),
        (5, base + string_offset),
        (10, len(string_table)),
        (30, 0x8),
        (0x6FFFFFFB, 0x08000001),
        (0, 0),
    )
    dynamic_bytes = b"".join(struct.pack("<QQ", *entry) for entry in dynamic_entries)
    programs = (
        (1, 5, 0, base, base, len(payload), len(payload), 0x1000),
        (
            3,
            4,
            interpreter_offset,
            base + interpreter_offset,
            0,
            len(interpreter),
            len(interpreter),
            1,
        ),
        (
            2,
            6,
            dynamic_offset,
            base + dynamic_offset,
            0,
            len(dynamic_bytes),
            len(dynamic_bytes),
            8,
        ),
        (
            0x6474E552,
            4,
            dynamic_offset,
            base + dynamic_offset,
            0,
            len(dynamic_bytes),
            len(dynamic_bytes),
            1,
        ),
        (0x6474E551, 6, 0, 0, 0, 0, 0, 16),
        (
            4,
            4,
            note_offset,
            base + note_offset,
            0,
            len(note),
            len(note),
            4,
        ),
    )
    for index, program in enumerate(programs):
        offset = program_offset + index * 56
        payload[offset : offset + 56] = struct.pack("<IIQQQQQQ", *program)
    payload[interpreter_offset : interpreter_offset + len(interpreter)] = interpreter
    payload[dynamic_offset : dynamic_offset + len(dynamic_bytes)] = dynamic_bytes
    payload[string_offset : string_offset + len(string_table)] = string_table
    payload[note_offset : note_offset + len(note)] = note
    return bytes(payload)


def _snapshot(payload: bytes, *, uid: int = 0, gid: int = 0) -> object:
    return driver.FileSnapshot(
        payload=payload,
        identity=(1, 2, stat.S_IFREG | 0o700, 1, len(payload), uid, gid, 3, 4),
        mode="0700",
        uid=uid,
        gid=gid,
        nlink=1,
    )


def _expected_tool_identity(role: str) -> dict[str, object]:
    empty_sha = "sha256:" + hashlib.sha256(b"").hexdigest()
    if role == "compiler":
        return {
            "literal_path": "/data/data/com.termux/files/usr/bin/clang",
            "literal_entry_type": "symbolic_link",
            "literal_mode": "0777",
            "literal_uid": 10536,
            "literal_gid": 10536,
            "literal_nlink": 1,
            "literal_symlink_target": "clang-21",
            "resolved_path": "/data/data/com.termux/files/usr/bin/clang-21",
            "resolved_entry_type": "regular_file",
            "sha256": (
                "sha256:34da8e3a9b71793eb70c25670e1fe2bce4d37f1e2837ba8dc0c516c2ca0ffc83"
            ),
            "bytes": 120848,
            "resolved_mode": "0700",
            "resolved_uid": 10536,
            "resolved_gid": 10536,
            "resolved_nlink": 1,
            "version_argv_suffix": ["--version"],
            "version_returncode": 0,
            "version_stdout_bytes": 109,
            "version_stdout_sha256": (
                "sha256:fe40f61ef08c80c802452d327052739a0a57b31366d8eabdc694a15b8df98f94"
            ),
            "version_stderr_bytes": 0,
            "version_stderr_sha256": empty_sha,
        }
    return {
        "literal_path": "/data/data/com.termux/files/usr/bin/ld.lld",
        "literal_entry_type": "symbolic_link",
        "literal_mode": "0777",
        "literal_uid": 10536,
        "literal_gid": 10536,
        "literal_nlink": 1,
        "literal_symlink_target": "lld",
        "resolved_path": "/data/data/com.termux/files/usr/bin/lld",
        "resolved_entry_type": "regular_file",
        "sha256": (
            "sha256:5214b9511221a87e02c4a9603f470dd83804a54f4cf62475f168d47d707d964d"
        ),
        "bytes": 5615720,
        "resolved_mode": "0700",
        "resolved_uid": 10536,
        "resolved_gid": 10536,
        "resolved_nlink": 1,
        "version_argv_suffix": ["-flavor", "gnu", "--version"],
        "version_returncode": 0,
        "version_stdout_bytes": 41,
        "version_stdout_sha256": (
            "sha256:418d72df86baf70c88b9a96a9118e3cdc66be0537a58f66a6879df0479f9a78f"
        ),
        "version_stderr_bytes": 0,
        "version_stderr_sha256": empty_sha,
    }


def _production_python_runtime(source_commit: str) -> dict[str, object]:
    base = commercial.native_preflight_build_python_runtime_identity()
    layout = commercial.native_preflight_execution_layout(RUN_ID, source_commit)
    driver_path = (
        layout["checkout_root"] + "/scripts/termux/build_cur0s_native_preflight.py"
    )
    pycache_prefix = layout["action_root"] + "/native_preflight_build_pycache_forbidden"
    records = [
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
        f"pycache_prefix={pycache_prefix}",
        driver_path,
        "--run-id",
        RUN_ID,
        "--source-commit",
        source_commit,
    ]
    body = {
        **base,
        "driver_path": driver_path,
        "file_backed_executable_mapping_paths": sorted(
            artifact["path"] for artifact in base["artifact_inputs"].values()
        ),
        "loaded_module_origin_count": len(records),
        "loaded_module_origins": records,
        "loaded_module_origins_sha256": driver.canonical_sha256(records),
        "loaded_stdlib_extension_module_paths": [],
        "orig_argv": orig_argv,
        "pycache_prefix": pycache_prefix,
        "pycache_prefix_absent": True,
        "run_id": RUN_ID,
        "source_commit": source_commit,
        "sys_argv": orig_argv[4:],
        "sys_xoptions": {"pycache_prefix": pycache_prefix},
    }
    return {**body, "python_runtime_root_sha256": driver.canonical_sha256(body)}


def _held_actual_identity(
    role: str,
    identity: dict[str, object],
    *,
    inode: int,
) -> dict[str, object]:
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


def _production_tool_runtime() -> dict[str, object]:
    runtime_inputs = commercial.NATIVE_PREFLIGHT_BUILD_TOOL_RUNTIME_INPUTS
    tools: dict[str, object] = {}
    for tool_index, tool_role in enumerate(("compiler", "linker"), start=1):
        entries: list[dict[str, object]] = []
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
                artifact = runtime_inputs[runtime_role]
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
        arguments = [
            "/system/bin/linker64",
            "--list",
            f"/proc/self/fd/{70 + tool_index}",
        ]
        body = {
            "argv": arguments,
            "entries": entries,
            "entry_count": len(entries),
            "normalized_stdout_sha256": driver.canonical_sha256(
                [entry["normalized_line"] for entry in entries]
            ),
            "returncode": 0,
            "stderr_bytes": 0,
            "stderr_sha256": (
                "sha256:e3b0c44298fc1c149afbf4c8996fb924"
                "27ae41e4649b934ca495991b7852b855"
            ),
            "target": _held_actual_identity(
                tool_role,
                _expected_tool_identity(tool_role),
                inode=10 + tool_index,
            ),
        }
        tools[tool_role] = {
            **body,
            "resolution_root_sha256": driver.canonical_sha256(body),
        }
    body = {
        "address_normalization": (
            "remove_only_exact_terminal_lowercase_hex_ASLR_address_suffix"
        ),
        "environment": {
            "ANDROID_ROOT": "/system",
            "HOME": "/data/data/com.termux/files/home",
            "LC_ALL": "C",
            "PATH": "/data/data/com.termux/files/usr/bin:/system/bin",
        },
        "loader": _held_actual_identity(
            "android_linker64",
            runtime_inputs["android_linker64"],
            inode=9,
        ),
        "scope": (
            "static_PT_INTERP_and_DT_NEEDED_resolution_only_no_arbitrary_dlopen_claim"
        ),
        "schema_version": (commercial.NATIVE_PREFLIGHT_ACTUAL_LOADER_RESOLUTION_SCHEMA),
        "tools": tools,
    }
    actual = {
        **body,
        "actual_loader_resolution_root_sha256": driver.canonical_sha256(body),
    }
    return {
        **commercial.NATIVE_PREFLIGHT_BUILD_TOOL_RUNTIME_IDENTITY,
        "actual_loader_resolution": actual,
    }


def _git(repo: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ("/usr/bin/git", "-C", str(repo), *arguments),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "HOME": str(repo.parent),
            "LC_ALL": "C",
            "PATH": "/usr/bin:/bin",
        },
    )


def _synthetic_checkout(tmp_path: Path) -> tuple[object, str, bytes]:
    repo = (tmp_path / "checkout").resolve()
    repo.mkdir(mode=0o700)
    for relative_path in NATIVE_PREFLIGHT_SOURCE_FILES:
        path = repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"synthetic committed source: {relative_path}\n", encoding="utf-8"
        )
        path.chmod(0o644)
    _git(repo, "init", "-q")
    _git(repo, "add", "--", *NATIVE_PREFLIGHT_SOURCE_FILES)
    _git(
        repo,
        "-c",
        "user.name=CUR0S Test",
        "-c",
        "user.email=cur0s@example.invalid",
        "commit",
        "-q",
        "-m",
        "synthetic native closure",
    )
    commit = _git(repo, "rev-parse", "HEAD").stdout.decode().strip()

    action_root = (tmp_path / RUN_ID).resolve()
    action_root.mkdir(mode=0o700)
    action_root.chmod(0o700)
    tools = (tmp_path / "tools").resolve()
    tools.mkdir(mode=0o700)
    compiler = tools / "clang-21"
    linker = tools / "lld"
    compiler.write_bytes(b"synthetic compiler")
    linker.write_bytes(b"synthetic linker")
    compiler.chmod(0o700)
    linker.chmod(0o700)
    (tools / "clang").symlink_to("clang-21")
    (tools / "ld.lld").symlink_to("lld")
    resource_directory = (tmp_path / "resource").resolve()
    resource_include_root = resource_directory / "include"
    resource_include_root.mkdir(parents=True, mode=0o700)
    (resource_include_root / "stddef.h").write_bytes(b"synthetic stddef\n")
    system_include_root = (tmp_path / "include").resolve()
    system_include_root.mkdir(mode=0o700)
    (system_include_root / "stdint.h").write_bytes(b"synthetic stdint\n")
    arch_include_root = system_include_root / "aarch64-linux-android"
    arch_include_root.mkdir(mode=0o700)
    (arch_include_root / "types.h").write_bytes(b"synthetic arch types\n")
    link_root = (tmp_path / "link-inputs").resolve()
    link_root.mkdir(mode=0o700)
    link_input_paths: dict[str, Path] = {}
    for role in driver.LINK_INPUT_ROLES:
        path = link_root / role
        path.write_bytes(f"synthetic held link input: {role}\n".encode())
        path.chmod(0o600)
        link_input_paths[role] = path
    config = driver.BuildConfig(
        source_root=repo,
        action_root=action_root,
        compiler_path=tools / "clang",
        linker_path=tools / "ld.lld",
        resource_directory=resource_directory,
        resource_include_root=resource_include_root,
        system_include_root=system_include_root,
        arch_include_root=arch_include_root,
        link_input_paths=link_input_paths,
        expected_uid=os.getuid(),
        expected_gid=os.getgid(),
    )
    return config, commit, _valid_aarch64_elf()


def _synthetic_process_runner(
    config: object,
    elf_payload: bytes,
    *,
    after_compile: object | None = None,
    before_link: object | None = None,
) -> object:
    compile_count = 0
    link_count = 0

    def synthetic_runner(
        arguments: object,
        cwd: Path,
        environment: object,
        executable_fd: int | None,
        inherited_fds: object,
    ) -> subprocess.CompletedProcess[bytes]:
        nonlocal compile_count, link_count
        argv = tuple(arguments)
        if argv[1:] in {
            ("--version",),
            ("-flavor", "gnu", "--version"),
        }:
            output = b"synthetic tool version\n"
            return subprocess.CompletedProcess(argv, 0, output, b"")
        if "--no-default-config" in argv:
            assert "-nostdinc" in argv
            assert str(config.source_root) not in "\0".join(argv)
            output_path = Path(argv[-1])
            assert argv[-2] == "-o"
            source_path = Path(argv[-3])
            assert source_path.parts[-3:-1] == ("self", "fd")
            assert int(source_path.name) in set(inherited_fds)
            assert len(set(inherited_fds)) == 2
            output_path.write_bytes(b"object:" + source_path.name.encode())
            output_path.chmod(0o600)
            compile_count += 1
            if after_compile is not None:
                after_compile(compile_count)
            return subprocess.CompletedProcess(argv, 0, b"", b"")
        assert argv[1:3] == ("-flavor", "gnu")
        link_count += 1
        if before_link is not None:
            before_link(link_count)
        output_index = argv.index("-o") + 1
        output_path = Path(argv[output_index])
        inherited = set(inherited_fds)
        held_paths = [item for item in argv if item.startswith("/proc/self/fd/")]
        assert held_paths
        assert all(int(item.rsplit("/", 1)[1]) in inherited for item in held_paths)
        assert executable_fd not in inherited
        output_path.write_bytes(elf_payload)
        output_path.chmod(0o700)
        return subprocess.CompletedProcess(argv, 0, b"", b"")

    return synthetic_runner


def _synthetic_runtime_kwargs() -> dict[str, object]:
    python_guard = driver.RuntimeGuard(
        dict(driver.PYTHON_RUNTIME_BASE_IDENTITY),
        lambda: None,
        lambda: None,
    )

    def tool_attestor(
        compiler: object,
        linker: object,
        source_root: Path,
        process_runner: object,
    ) -> object:
        del source_root, process_runner

        def revalidate() -> None:
            driver.revalidate_build_tool_file(compiler)
            driver.revalidate_build_tool_file(linker)

        identity = {
            **driver.TOOL_RUNTIME_IDENTITY,
            "tool_roots": {
                "compiler": compiler.identity["resolved_path"],
                "linker": linker.identity["resolved_path"],
            },
        }
        return driver.RuntimeGuard(identity, revalidate, lambda: None)

    return {
        "python_runtime_guard": python_guard,
        "tool_runtime_attestor": tool_attestor,
    }


def test_build_arguments_disable_configs_and_use_only_explicit_closure(
    tmp_path: Path,
) -> None:
    config, _commit, _payload = _synthetic_checkout(tmp_path)
    object_path = config.action_root / "cur0s_sha256.o"

    observed = driver.compile_arguments(config, 37, object_path)

    assert observed[0] == driver.COMPILER_PATH
    assert "--no-default-config" in observed
    assert "--target=aarch64-linux-android30" in observed
    assert "-nostdinc" in observed
    assert observed[-5:] == (
        "-x",
        "c",
        "/proc/self/fd/37",
        "-o",
        str(object_path),
    )
    assert "CUR0S_NATIVE_PREFLIGHT_TESTING" not in "\0".join(observed)
    assert driver.LINK_ARGV_TEMPLATE[0:3] == (
        driver.LINKER_PATH,
        "-flavor",
        "gnu",
    )
    assert all(not argument.startswith("-l") for argument in driver.LINK_ARGV_TEMPLATE)
    assert "$HELD_FD:crtbegin_dynamic" in driver.LINK_ARGV_TEMPLATE
    assert "$HELD_FD:crtend_android" in driver.LINK_ARGV_TEMPLATE


def test_elf_parser_requires_full_android_hardening_identity() -> None:
    payload = _valid_aarch64_elf()

    identity = driver.parse_aarch64_elf(payload)

    assert identity == {
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
            "file_size": 1280,
            "memory_size": 1280,
            "proc_maps_mapped_bytes": 4096,
            "proc_maps_offset": 0,
            "proc_maps_page_size": 4096,
            "virtual_address": 0x400000,
        },
        "interpreter": "/system/bin/linker64",
        "machine": "AArch64",
        "needed": ["libc.so"],
        "pie": True,
        "relro": True,
        "rpath": None,
        "runpath": None,
        "sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
        "text_relocations": False,
    }

    executable_stack = bytearray(payload)
    stack_flags_offset = 64 + (4 * 56) + 4
    executable_stack[stack_flags_offset : stack_flags_offset + 4] = struct.pack("<I", 7)
    with pytest.raises(driver.BuildError, match="ELF_hardening_identity_mismatch"):
        driver.parse_aarch64_elf(bytes(executable_stack))

    wrong_needed = payload.replace(b"libc.so", b"libm.so")
    with pytest.raises(driver.BuildError, match="ELF_needed_mismatch"):
        driver.parse_aarch64_elf(wrong_needed)

    writable_executable = bytearray(payload)
    load_flags_offset = 64 + 4
    writable_executable[load_flags_offset : load_flags_offset + 4] = struct.pack(
        "<I", 7
    )
    with pytest.raises(driver.BuildError, match="ELF_WX_load_segment_present"):
        driver.parse_aarch64_elf(bytes(writable_executable))

    entry_outside_executable = bytearray(payload)
    entry_outside_executable[24:32] = struct.pack("<Q", 0xDEADBEEF)
    with pytest.raises(
        driver.BuildError,
        match="ELF_entrypoint_not_in_executable_segment",
    ):
        driver.parse_aarch64_elf(bytes(entry_outside_executable))

    relro_too_short = bytearray(payload)
    relro_virtual_offset = 64 + (3 * 56) + 16
    relro_too_short[relro_virtual_offset : relro_virtual_offset + 8] = struct.pack(
        "<Q", 0x400000 + 0x250
    )
    with pytest.raises(
        driver.BuildError,
        match="ELF_dynamic_segment_not_covered_by_RELRO",
    ):
        driver.parse_aarch64_elf(bytes(relro_too_short))

    got_outside_relro = bytearray(payload)
    got_value_offset = 0x240 + 16 + 8
    got_outside_relro[got_value_offset : got_value_offset + 8] = struct.pack(
        "<Q", 0xDEADBEEF
    )
    with pytest.raises(driver.BuildError, match="ELF_PLTGOT_not_covered_by_RELRO"):
        driver.parse_aarch64_elf(bytes(got_outside_relro))

    wrong_api = bytearray(payload)
    wrong_api[0x394:0x398] = struct.pack("<I", 29)
    with pytest.raises(driver.BuildError, match="ELF_Android_API_level_mismatch"):
        driver.parse_aarch64_elf(bytes(wrong_api))


def test_elf_parser_rejects_executable_pt_load_geometry_mutations() -> None:
    payload = _valid_aarch64_elf()

    zero_memory = bytearray(payload)
    zero_memory[64 + 32 : 64 + 40] = struct.pack("<Q", 0)
    zero_memory[64 + 40 : 64 + 48] = struct.pack("<Q", 0)
    with pytest.raises(
        driver.BuildError,
        match="ELF_executable_PT_LOAD_alignment_invalid",
    ):
        driver.parse_aarch64_elf(bytes(zero_memory))

    subpage_alignment = bytearray(payload)
    subpage_alignment[64 + 48 : 64 + 56] = struct.pack("<Q", 2048)
    with pytest.raises(
        driver.BuildError,
        match="ELF_executable_PT_LOAD_alignment_invalid",
    ):
        driver.parse_aarch64_elf(bytes(subpage_alignment))

    incongruent_offset = bytearray(payload)
    incongruent_offset[64 + 8 : 64 + 16] = struct.pack("<Q", 1)
    incongruent_offset[64 + 32 : 64 + 40] = struct.pack("<Q", len(payload) - 1)
    with pytest.raises(
        driver.BuildError,
        match="ELF_executable_PT_LOAD_alignment_invalid",
    ):
        driver.parse_aarch64_elf(bytes(incongruent_offset))

    second_executable_load = bytearray(payload)
    note_header = 64 + 5 * 56
    second_executable_load[note_header : note_header + 4] = struct.pack("<I", 1)
    second_executable_load[note_header + 4 : note_header + 8] = struct.pack("<I", 5)
    second_executable_load[note_header + 48 : note_header + 56] = struct.pack(
        "<Q", 4096
    )
    with pytest.raises(
        driver.BuildError,
        match="ELF_executable_PT_LOAD_cardinality_invalid",
    ):
        driver.parse_aarch64_elf(bytes(second_executable_load))


def test_recursive_runtime_graph_is_exact_and_rejects_unknown_soname() -> None:
    identity = driver.parse_runtime_elf_bytes(_valid_aarch64_elf())

    assert identity == {
        "interpreter": "/system/bin/linker64",
        "needed": ["libc.so"],
        "rpath": None,
        "runpath": None,
        "soname": None,
    }
    assert driver.PYTHON_RUNTIME_BASE_IDENTITY == (
        commercial.native_preflight_build_python_runtime_identity()
    )
    assert driver.TOOL_RUNTIME_IDENTITY == (
        commercial.NATIVE_PREFLIGHT_BUILD_TOOL_RUNTIME_IDENTITY
    )
    driver._validate_recursive_runtime_graph(driver.TOOL_RUNTIME_DEPENDENCY_GRAPH)

    weakened = {
        role: {**node, "needed": list(node["needed"])}
        for role, node in driver.TOOL_RUNTIME_DEPENDENCY_GRAPH.items()
    }
    weakened["compiler"]["needed"].append("libambient-injection.so")
    with pytest.raises(driver.BuildError, match="runtime_dependency_soname_unresolved"):
        driver._validate_recursive_runtime_graph(weakened)


def test_actual_loader_list_is_strict_and_rejects_resolution_drift(
    tmp_path: Path,
) -> None:
    runtime_inputs: dict[str, object] = {}
    descriptors: list[int] = []
    try:
        for index, role in enumerate(driver.TOOL_RUNTIME_INPUT_ROLES):
            path = tmp_path / f"runtime-{index}"
            path.write_bytes(b"x")
            descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC)
            descriptors.append(descriptor)
            expected = driver.TOOL_RUNTIME_INPUTS[role]
            identity = {
                **expected,
                "bytes": 1,
                "resolved_nlink": 1,
                "sha256": "sha256:" + ("a" * 64),
            }
            information = os.fstat(descriptor)
            runtime_inputs[role] = driver.RuntimeFileInput(
                role,
                identity,
                driver.stat_identity(information),
                descriptor,
                driver.stat_identity(information),
            )
        lines = []
        for index, (soname, role) in enumerate(
            driver.ACTUAL_LOADER_EXPECTED_RESOLUTION["compiler"],
            start=1,
        ):
            path = (
                "[vdso]"
                if role == "kernel_vdso"
                else runtime_inputs[role].identity["resolved_path"]
            )
            lines.append(f"\t{soname} => {path} (0x{0x700000 + index:x})\n")
        payload = "".join(lines).encode("ascii")
        parsed = driver.parse_actual_loader_list(payload)

        bound = driver._bind_actual_loader_entries(
            "compiler",
            parsed,
            runtime_inputs,
        )

        assert len(bound) == len(lines)
        assert all("0x" not in entry["normalized_line"] for entry in bound)
        with pytest.raises(driver.BuildError, match="actual_loader_resolution_set"):
            driver._bind_actual_loader_entries(
                "compiler",
                parsed[:-1],
                runtime_inputs,
            )
        with pytest.raises(driver.BuildError, match="actual_loader_resolution_set"):
            driver._bind_actual_loader_entries(
                "compiler",
                [*parsed, parsed[-1]],
                runtime_inputs,
            )
        changed_path = [dict(record) for record in parsed]
        changed_path[1]["resolved_path"] = "/unexpected/libc.so"
        with pytest.raises(driver.BuildError, match="resolved_path_mismatch"):
            driver._bind_actual_loader_entries(
                "compiler",
                changed_path,
                runtime_inputs,
            )
        duplicate = [dict(record) for record in parsed]
        duplicate[1] = dict(duplicate[0])
        with pytest.raises(driver.BuildError, match="order_or_soname_mismatch"):
            driver._bind_actual_loader_entries(
                "compiler",
                duplicate,
                runtime_inputs,
            )
        for malformed in (
            payload + b"\n",
            payload.replace(b"(0x", b"(0X", 1),
            payload.replace(b"\t", b" ", 1),
            payload.replace(b")\n", b") \n", 1),
            payload.replace(b"0x700001", b"0x0", 1),
        ):
            with pytest.raises(driver.BuildError):
                driver.parse_actual_loader_list(malformed)
        completed = subprocess.CompletedProcess(
            ("/system/bin/linker64", "--list", "/proc/self/fd/1"),
            0,
            payload,
            b"injected warning",
        )
        with pytest.raises(driver.BuildError, match="actual_loader_list_execution"):
            driver.require_actual_loader_process_result(completed)
    finally:
        for value in runtime_inputs.values():
            value.close()


def test_receipt_is_canonical_and_enumerates_full_input_closure(
    tmp_path: Path,
) -> None:
    payload = _valid_aarch64_elf()
    snapshot = _snapshot(payload, uid=10536, gid=10536)
    objects = {
        "cur0s_native_preflight": _snapshot(b"preflight object"),
        "cur0s_sha256": _snapshot(b"sha256 object"),
    }
    build_result = driver.BuildResult(snapshot, objects)
    source_bindings = {
        path: {
            "bytes": 1,
            "git_blob_oid": "0" * 40,
            "sha256": "sha256:" + ("1" * 64),
        }
        for path in NATIVE_PREFLIGHT_SOURCE_FILES
    }
    config, _commit, _elf = _synthetic_checkout(tmp_path)
    include_trees, link_inputs = driver.attest_toolchain_input_closure(config)
    try:
        closure = driver.toolchain_input_closure_receipt(
            include_trees,
            link_inputs,
            driver.PYTHON_RUNTIME_BASE_IDENTITY,
            driver.TOOL_RUNTIME_IDENTITY,
        )
        receipt = driver.build_receipt(
            run_id=RUN_ID,
            source_commit="a" * 40,
            source_bindings=source_bindings,
            compiler_identity=_expected_tool_identity("compiler"),
            linker_identity=_expected_tool_identity("linker"),
            toolchain_input_closure=closure,
            build_one=build_result,
            build_two=build_result,
            elf_identity=driver.parse_aarch64_elf(payload),
            uid=10536,
            gid=10536,
        )

    finally:
        for value in link_inputs.values():
            value.close()

    production_closure_body = {
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
        "python_runtime": _production_python_runtime("a" * 40),
        "unmeasured_inputs_allowed": False,
        "unmeasured_inputs_allowed_scope": "within_input_closure_scope",
        "tool_execution_runtime": _production_tool_runtime(),
    }
    production_closure = {
        **production_closure_body,
        "closure_root_sha256": driver.canonical_sha256(production_closure_body),
    }
    production_receipt = driver.build_receipt(
        run_id=RUN_ID,
        source_commit="a" * 40,
        source_bindings=source_bindings,
        compiler_identity=_expected_tool_identity("compiler"),
        linker_identity=_expected_tool_identity("linker"),
        toolchain_input_closure=production_closure,
        build_one=build_result,
        build_two=build_result,
        elf_identity=driver.parse_aarch64_elf(payload),
        uid=10536,
        gid=10536,
    )
    assert (
        commercial.validate_native_preflight_build_receipt(
            production_receipt,
            source_commit="a" * 40,
            source_file_bindings=source_bindings,
        )
        == production_receipt
    )

    assert receipt["schema_version"].endswith("_v3")
    assert set(receipt["source_file_bindings"]) == set(driver.NATIVE_SOURCE_FILES)
    assert (
        "scripts/termux/build_cur0s_native_preflight.py"
        in receipt["source_file_bindings"]
    )
    assert driver.COMMERCIAL_CONTRACT_FILE in receipt["source_file_bindings"]
    assert set(receipt["toolchain_input_closure"]["include_trees"]) == set(
        driver.INCLUDE_TREE_ROLES
    )
    assert set(receipt["toolchain_input_closure"]["link_inputs"]) == set(
        driver.LINK_INPUT_ROLES
    )
    assert receipt["toolchain_input_closure"]["linker_execution"] == (
        "direct_held_linker_fd"
    )
    assert receipt["toolchain_input_closure"]["unmeasured_inputs_allowed"] is False
    assert receipt["source_commit_binding_status"] == (
        "pending_host_preregistration_git_tree_binding"
    )
    assert receipt["toolchain_input_closure"]["python_runtime"] == (
        driver.PYTHON_RUNTIME_BASE_IDENTITY
    )
    assert receipt["toolchain_input_closure"]["tool_execution_runtime"] == (
        driver.TOOL_RUNTIME_IDENTITY
    )
    assert receipt["intermediate_objects"]["deterministic_match"] is True
    assert receipt["network_requested"] is False
    assert receipt["network_syscalls_instrumented"] is False
    assert receipt["intended_target"] == {
        "architecture": "aarch64",
        "compiler_target": "aarch64-linux-android30",
        "runtime_device_and_soc_gate": "not_claimed_by_build_receipt",
    }
    body = dict(receipt)
    claimed_root = body.pop("build_receipt_root_sha256")
    assert claimed_root == driver.canonical_sha256(body)

    tampered_closure = dict(closure)
    tampered_closure["unmeasured_inputs_allowed"] = True
    closure_body = dict(tampered_closure)
    closure_body.pop("closure_root_sha256")
    tampered_closure["closure_root_sha256"] = driver.canonical_sha256(closure_body)
    with pytest.raises(
        driver.BuildError,
        match="toolchain_input_closure_receipt_invalid",
    ):
        driver.build_receipt(
            run_id=RUN_ID,
            source_commit="a" * 40,
            source_bindings=source_bindings,
            compiler_identity=_expected_tool_identity("compiler"),
            linker_identity=_expected_tool_identity("linker"),
            toolchain_input_closure=tampered_closure,
            build_one=build_result,
            build_two=build_result,
            elf_identity=driver.parse_aarch64_elf(payload),
            uid=10536,
            gid=10536,
        )


def test_source_binding_is_local_and_defers_git_tree_authority(tmp_path: Path) -> None:
    config, _commit, _payload = _synthetic_checkout(tmp_path)

    clean = driver.snapshot_source_bindings(config)

    assert set(clean) == set(NATIVE_PREFLIGHT_SOURCE_FILES)
    assert all(len(binding["git_blob_oid"]) == 40 for binding in clean.values())
    changed_path = config.source_root / NATIVE_PREFLIGHT_SOURCE_FILES[0]
    changed_path.write_text("dirty\n", encoding="utf-8")
    changed = driver.snapshot_source_bindings(config)

    assert changed != clean
    assert driver.SOURCE_COMMIT_BINDING_STATUS == (
        "pending_host_preregistration_git_tree_binding"
    )
    assert not hasattr(driver, "GIT_ENVIRONMENT")


def test_commercial_validator_loads_only_hash_bound_snapshot() -> None:
    path = ROOT / driver.COMMERCIAL_CONTRACT_FILE
    payload = path.read_bytes()
    binding = {"bytes": len(payload), "sha256": driver.prefixed_sha256(payload)}

    module = driver._load_contract_module(ROOT, binding)

    assert hasattr(module, "validate_native_preflight_build_receipt")
    with pytest.raises(
        driver.BuildError,
        match="commercial_contract_snapshot_binding_mismatch",
    ):
        driver._load_contract_module(
            ROOT,
            {"bytes": len(payload), "sha256": "sha256:" + ("0" * 64)},
        )


def test_run_process_caps_output_before_buffer_growth(tmp_path: Path) -> None:
    command = (
        sys.executable,
        "-I",
        "-B",
        "-S",
        "-c",
        "import os; os.write(1, b'x' * 2000000)",
    )

    with pytest.raises(driver.BuildError, match="process_output_limit_exceeded"):
        driver.run_process(command, tmp_path, {}, None, ())


def test_run_process_timeout_kills_descendant_process_group(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "descendant-survived"
    child = (
        "import pathlib,sys,time; time.sleep(0.8); "
        "pathlib.Path(sys.argv[1]).write_text('survived')"
    )
    parent = (
        "import subprocess,sys,time; "
        f"subprocess.Popen([sys.executable, '-c', {child!r}, sys.argv[1]]); "
        "time.sleep(30)"
    )
    monkeypatch.setattr(driver, "PROCESS_TIMEOUT_SECONDS", 0.2)

    with pytest.raises(driver.BuildError, match="process_timeout"):
        driver.run_process(
            (sys.executable, "-I", "-B", "-S", "-c", parent, str(marker)),
            tmp_path,
            {},
            None,
            (),
        )
    time.sleep(1.0)
    assert not marker.exists()


def test_linker_path_swap_cannot_replace_held_linker(tmp_path: Path) -> None:
    config, commit, elf_payload = _synthetic_checkout(tmp_path)

    def swap_linker(link_count: int) -> None:
        if link_count != 1:
            return
        resolved = config.linker_path.parent / "lld"
        resolved.rename(resolved.with_name("lld-attested"))
        resolved.write_bytes(b"injected replacement linker")
        resolved.chmod(0o700)

    with pytest.raises(driver.BuildError, match="build_tool_changed"):
        driver.execute_build(
            config,
            commit,
            receipt_validator=lambda receipt, _commit, _bindings: receipt,
            process_runner=_synthetic_process_runner(
                config,
                elf_payload,
                before_link=swap_linker,
            ),
            **_synthetic_runtime_kwargs(),
        )


def test_default_clang_config_injection_is_disabled(tmp_path: Path) -> None:
    config, commit, elf_payload = _synthetic_checkout(tmp_path)
    injected = config.compiler_path.parent / "clang.cfg"
    injected.write_text("-DCUR0S_INJECTED_DEFAULT_CONFIG=1\n", encoding="utf-8")

    receipt = driver.execute_build(
        config,
        commit,
        receipt_validator=lambda value, _commit, _bindings: value,
        process_runner=_synthetic_process_runner(config, elf_payload),
        **_synthetic_runtime_kwargs(),
    )

    assert receipt["toolchain_input_closure"]["default_clang_configuration"] == {
        "disabled": True,
        "flag": "--no-default-config",
    }
    assert all(
        "CUR0S_INJECTED_DEFAULT_CONFIG" not in argument
        for argument in receipt["build_argv_template"]["compile"]
    )


def test_final_authority_revalidation_fault_publishes_no_consumable_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, commit, elf_payload = _synthetic_checkout(tmp_path)
    calls = 0

    def fail_final_revalidation(*_args: object, **_kwargs: object) -> None:
        nonlocal calls
        calls += 1
        raise driver.BuildError("injected_final_authority_revalidation_failure")

    monkeypatch.setattr(
        driver,
        "final_prepublication_authority_revalidation",
        fail_final_revalidation,
    )

    with pytest.raises(
        driver.BuildError,
        match="injected_final_authority_revalidation_failure",
    ):
        driver.execute_build(
            config,
            commit,
            receipt_validator=lambda value, _commit, _bindings: value,
            process_runner=_synthetic_process_runner(config, elf_payload),
            **_synthetic_runtime_kwargs(),
        )

    assert calls == 1
    assert not config.final_binary.exists()
    assert not config.receipt_path.exists()


def test_header_mutation_aborts_before_second_build(tmp_path: Path) -> None:
    config, commit, elf_payload = _synthetic_checkout(tmp_path)

    def mutate_header(compile_count: int) -> None:
        if compile_count == 1:
            (config.system_include_root / "stdint.h").write_bytes(
                b"reproducibly injected header\n"
            )

    with pytest.raises(driver.BuildError, match="toolchain_include_tree_changed"):
        driver.execute_build(
            config,
            commit,
            receipt_validator=lambda receipt, _commit, _bindings: receipt,
            process_runner=_synthetic_process_runner(
                config,
                elf_payload,
                after_compile=mutate_header,
            ),
            **_synthetic_runtime_kwargs(),
        )


def test_compiled_source_mutation_cannot_change_held_compile_input(
    tmp_path: Path,
) -> None:
    config, commit, elf_payload = _synthetic_checkout(tmp_path)

    def mutate_source(compile_count: int) -> None:
        if compile_count == 1:
            path = config.source_root / driver.COMPILED_SOURCE_FILES["cur0s_sha256"]
            path.write_bytes(b"replaced checkout source\n")

    with pytest.raises(driver.BuildError, match="held_source_changed"):
        driver.execute_build(
            config,
            commit,
            receipt_validator=lambda receipt, _commit, _bindings: receipt,
            process_runner=_synthetic_process_runner(
                config,
                elf_payload,
                after_compile=mutate_source,
            ),
            **_synthetic_runtime_kwargs(),
        )


def test_crt_mutation_is_detected_on_held_descriptor(tmp_path: Path) -> None:
    config, commit, elf_payload = _synthetic_checkout(tmp_path)

    def mutate_crt(link_count: int) -> None:
        if link_count == 1:
            config.link_input_paths["crtbegin_dynamic"].write_bytes(
                b"mutated CRT payload\n"
            )

    with pytest.raises(driver.BuildError, match="held_link_input_changed"):
        driver.execute_build(
            config,
            commit,
            receipt_validator=lambda receipt, _commit, _bindings: receipt,
            process_runner=_synthetic_process_runner(
                config,
                elf_payload,
                before_link=mutate_crt,
            ),
            **_synthetic_runtime_kwargs(),
        )


def test_unmeasured_link_input_role_is_rejected(tmp_path: Path) -> None:
    config, _commit, _elf_payload = _synthetic_checkout(tmp_path)
    ambient = tmp_path / "ambient-link-input"
    ambient.write_bytes(b"unmeasured input")
    config.link_input_paths["ambient_injection"] = ambient

    with pytest.raises(driver.BuildError, match="link_input_role_set_mismatch"):
        driver.attest_toolchain_input_closure(config)


def test_synthetic_double_build_is_one_shot_and_fsynced(tmp_path: Path) -> None:
    config, commit, elf_payload = _synthetic_checkout(tmp_path)
    synthetic_runner = _synthetic_process_runner(config, elf_payload)

    def accept_receipt(
        receipt: object,
        source_commit: str,
        bindings: object,
    ) -> object:
        assert source_commit == commit
        assert set(bindings) == set(NATIVE_PREFLIGHT_SOURCE_FILES)
        body = dict(receipt)
        root = body.pop("build_receipt_root_sha256")
        assert root == driver.canonical_sha256(body)
        return receipt

    previous_umask = os.umask(0o077)
    try:
        receipt = driver.execute_build(
            config,
            commit,
            receipt_validator=accept_receipt,
            process_runner=synthetic_runner,
            **_synthetic_runtime_kwargs(),
        )
    finally:
        os.umask(previous_umask)

    assert config.final_binary.read_bytes() == elf_payload
    assert config.receipt_path.read_bytes() == driver.canonical_json_bytes(receipt)
    assert stat.S_IMODE(config.final_binary.stat().st_mode) == 0o700
    assert stat.S_IMODE(config.receipt_path.stat().st_mode) == 0o600
    assert config.build_one_output.read_bytes() == config.build_two_output.read_bytes()
    with pytest.raises(driver.BuildError):
        driver.execute_build(
            config,
            commit,
            receipt_validator=accept_receipt,
            process_runner=synthetic_runner,
            **_synthetic_runtime_kwargs(),
        )
