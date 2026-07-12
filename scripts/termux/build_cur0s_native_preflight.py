#!/data/data/com.termux/files/usr/bin/python -IBS
"""Deterministically build the CUR-0S Android native preflight on the phone.

This is a build-only action.  It requests no source acquisition or network
operation and has no candidate or preregistration surface.  Network syscalls
are not instrumented, which the receipt states explicitly.  Production paths
and compiler arguments are fixed; the caller supplies the frozen run id and a
commit label that the later host preregistration must bind to these exact held
source bytes.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import posixpath
import re
import selectors
import signal
import stat
import struct
import subprocess
import sys
import time
from types import ModuleType
from typing import Any, Callable, Mapping, Sequence


sys.dont_write_bytecode = True


NATIVE_PREFLIGHT_BUILD_SCHEMA = "cur0s_native_preflight_android_build_receipt_v3"
TOOLCHAIN_INPUT_CLOSURE_SCHEMA = "cur0s_native_toolchain_input_closure_v2"
RUNTIME_DEPENDENCY_CLOSURE_SCHEMA = (
    "cur0s_native_aarch64_recursive_runtime_dependency_closure_v2"
)
ACTUAL_LOADER_RESOLUTION_SCHEMA = "cur0s_native_aarch64_actual_loader_resolution_v1"
SOURCE_COMMIT_BINDING_STATUS = "pending_host_preregistration_git_tree_binding"
NATIVE_PREFLIGHT_SECURITY_CEILING = (
    "observational_only_no_guarantee_against_a_concurrent_malicious_"
    "same_uid_between_checks"
)
NATIVE_SOURCE_FILES = (
    "scripts/termux/native/cur0s_sha256.h",
    "scripts/termux/native/cur0s_sha256.c",
    "scripts/termux/native/cur0s_native_preflight.c",
    "scripts/termux/build_cur0s_native_preflight.py",
    "polymath_ai/corpus/cur0s_commercial_sources.py",
)
COMPILED_SOURCE_FILES = {
    "cur0s_native_preflight": "scripts/termux/native/cur0s_native_preflight.c",
    "cur0s_sha256": "scripts/termux/native/cur0s_sha256.c",
}
NATIVE_HEADER_FILE = "scripts/termux/native/cur0s_sha256.h"
COMMERCIAL_CONTRACT_FILE = "polymath_ai/corpus/cur0s_commercial_sources.py"
RUN_ID_RE = re.compile(r"[0-9]{8}T[0-9]{6}Z_cur0s_commercial_sources_v1\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
PROC_MAP_PAGE_SIZE = 4096

PHONE_HOME = "/data/data/com.termux/files/home"
PHONE_PREFIX = "/data/data/com.termux/files/usr"
PHONE_UID = 10536
PHONE_GID = 10536
COMPILER_PATH = f"{PHONE_PREFIX}/bin/clang"
LINKER_PATH = f"{PHONE_PREFIX}/bin/ld.lld"
RECEIPT_NAME = "native_preflight_build_receipt.json"
BUILD_ROOT_NAME = "native_preflight_build"

RESOURCE_DIRECTORY = f"{PHONE_PREFIX}/lib/clang/21"
RESOURCE_INCLUDE_ROOT = f"{RESOURCE_DIRECTORY}/include"
SYSTEM_INCLUDE_ROOT = f"{PHONE_PREFIX}/include"
ARCH_INCLUDE_ROOT = f"{SYSTEM_INCLUDE_ROOT}/aarch64-linux-android"
LINK_INPUT_PATHS = {
    "android_libc": "/apex/com.android.runtime/lib64/bionic/libc.so",
    "android_libdl": "/apex/com.android.runtime/lib64/bionic/libdl.so",
    "clang_rt_builtins": (
        f"{RESOURCE_DIRECTORY}/lib/linux/libclang_rt.builtins-aarch64-android.a"
    ),
    "crtbegin_dynamic": f"{PHONE_PREFIX}/lib/crtbegin_dynamic.o",
    "crtend_android": f"{PHONE_PREFIX}/lib/crtend_android.o",
    "libunwind": f"{PHONE_PREFIX}/lib/libunwind.a",
}
LINK_INPUT_ROLES = tuple(sorted(LINK_INPUT_PATHS))
INCLUDE_TREE_ROLES = (
    "clang_resource_tree",
    "termux_arch_headers",
    "termux_system_headers",
)

BUILD_DRIVER_LAUNCH_ENVIRONMENT = {
    "ANDROID_ROOT": "/system",
    "HOME": PHONE_HOME,
    "LC_ALL": "C",
    "LD_PRELOAD": f"{PHONE_PREFIX}/lib/libtermux-exec.so",
    "PATH": f"{PHONE_PREFIX}/bin:/system/bin",
    "TERMUX_EXEC__PROC_SELF_EXE": f"{PHONE_PREFIX}/bin/python",
}
PYTHON_RUNTIME_STDLIB_TREE = {
    "canonicalization": (
        "sorted_relative_POSIX_paths_canonical_JSON_type_mode_"
        "regular_bytes_sha256_source_only_excluding_root_site_packages_"
        "all_pycache_and_pyc_reject_external_symlinks_root_excluded"
    ),
    "entry_count": 691,
    "regular_bytes": 16_922_387,
    "root_gid": PHONE_GID,
    "root_mode": "0700",
    "root_nlink": 38,
    "root_path": f"{PHONE_PREFIX}/lib/python3.13",
    "root_sha256": (
        "sha256:303f8e4b3a9a521cd88d5a2ed2c2312c5bdad135365a60dfb8110d441c1fa700"
    ),
    "root_uid": PHONE_UID,
}
PYTHON_RUNTIME_ARTIFACTS = {
    "android_bionic_libc": {
        "bytes": 1_143_072,
        "gid": 1000,
        "mode": "0644",
        "nlink": 1,
        "path": "/apex/com.android.runtime/lib64/bionic/libc.so",
        "sha256": (
            "sha256:b4d95dc39a379dbe5049ce033f019b01a2f10dcf507562e83c72eef901d6ebcf"
        ),
        "uid": 1000,
    },
    "android_bionic_libdl": {
        "bytes": 50_760,
        "gid": 1000,
        "mode": "0644",
        "nlink": 1,
        "path": "/apex/com.android.runtime/lib64/bionic/libdl.so",
        "sha256": (
            "sha256:7abc47c96a4f49d52647e7f1d2045d3eb9ba4d9766c1d7f225e6aa229fa9f479"
        ),
        "uid": 1000,
    },
    "android_bionic_libm": {
        "bytes": 249_192,
        "gid": 1000,
        "mode": "0644",
        "nlink": 1,
        "path": "/apex/com.android.runtime/lib64/bionic/libm.so",
        "sha256": (
            "sha256:2a99c9ac7a12461663ec31b8d4ee3404ee99a1dca53f7c30b248bcccb155eefc"
        ),
        "uid": 1000,
    },
    "android_linker64": {
        "bytes": 2_160_952,
        "gid": 2000,
        "mode": "0755",
        "nlink": 1,
        "path": "/apex/com.android.runtime/bin/linker64",
        "sha256": (
            "sha256:6aa1b8bcf1da7e8b48f67f78eebaa2d9356c76ad3c9809bd5576b579907d7f9e"
        ),
        "uid": 0,
    },
    "libandroid_posix_semaphore": {
        "bytes": 7_136,
        "gid": PHONE_GID,
        "mode": "0600",
        "nlink": 1,
        "path": f"{PHONE_PREFIX}/lib/libandroid-posix-semaphore.so",
        "sha256": (
            "sha256:adc7a3aa24f7e3baadc6149dea370bceeb11f058f19e22d8ca46e19f19e9e803"
        ),
        "uid": PHONE_UID,
    },
    "libbz2": {
        "bytes": 50_328,
        "gid": PHONE_GID,
        "mode": "0600",
        "nlink": 1,
        "path": f"{PHONE_PREFIX}/lib/libbz2.so.1.0.8",
        "sha256": (
            "sha256:5129a738fec8c6733954fa6a98f1fad9538e818f38db89d5391f12e5657746dc"
        ),
        "uid": PHONE_UID,
    },
    "libcrypto": {
        "bytes": 4_611_704,
        "gid": PHONE_GID,
        "mode": "0700",
        "nlink": 1,
        "path": f"{PHONE_PREFIX}/lib/libcrypto.so.3",
        "sha256": (
            "sha256:28534a11feb019f149032374c88d1c52f87baa241bc9ee7ab0bb1f3d24d21118"
        ),
        "uid": PHONE_UID,
    },
    "libpython": {
        "bytes": 5_153_728,
        "gid": PHONE_GID,
        "mode": "0700",
        "nlink": 1,
        "path": f"{PHONE_PREFIX}/lib/libpython3.13.so",
        "sha256": (
            "sha256:7ca4f4f00ae2e1afde50bb3ce01926ec6edb582719c7731a416235833d4d2319"
        ),
        "uid": PHONE_UID,
    },
    "libtermux_exec": {
        "bytes": 13_808,
        "gid": PHONE_GID,
        "mode": "0700",
        "nlink": 1,
        "path": f"{PHONE_PREFIX}/lib/libtermux-exec.so",
        "sha256": (
            "sha256:45ad0183d4fdb399ce5df0823b1d67b53a01bbb2596c7e4db79b7c255214c9c8"
        ),
        "uid": PHONE_UID,
    },
    "liblzma": {
        "bytes": 157_112,
        "gid": PHONE_GID,
        "mode": "0700",
        "nlink": 1,
        "path": f"{PHONE_PREFIX}/lib/liblzma.so.5.8.3",
        "sha256": (
            "sha256:f8ab7f7548a57222c1115274bd6ff10d08917ba0701c1b3892be5a12a8d506cf"
        ),
        "uid": PHONE_UID,
    },
    "libz": {
        "bytes": 72_232,
        "gid": PHONE_GID,
        "mode": "0700",
        "nlink": 1,
        "path": f"{PHONE_PREFIX}/lib/libz.so.1.3.2",
        "sha256": (
            "sha256:6d1a271adb9864fd66d696c746eac7a43faaa158b1370d32774ef73f1fe799ef"
        ),
        "uid": PHONE_UID,
    },
    "python": {
        "bytes": 4_728,
        "gid": PHONE_GID,
        "mode": "0700",
        "nlink": 1,
        "path": f"{PHONE_PREFIX}/bin/python3.13",
        "sha256": (
            "sha256:1d3987c39c03b764d629a8c8c6fdc5979d8f8e28beb7193f312fc39d63b70404"
        ),
        "uid": PHONE_UID,
    },
    "system_libcxx": {
        "bytes": 1_083_168,
        "gid": 0,
        "mode": "0644",
        "nlink": 1,
        "path": "/system/lib64/libc++.so",
        "sha256": (
            "sha256:794eb8fafd7be35da3725e9ec0b15189c6f4f2544f5b78afd8a647dde5b69195"
        ),
        "uid": 0,
    },
    "system_liblog": {
        "bytes": 101_848,
        "gid": 0,
        "mode": "0644",
        "nlink": 1,
        "path": "/system/lib64/liblog.so",
        "sha256": (
            "sha256:b9d6a5f515686068e0a66d3d56c248701745f59273b20051a62bec4d44bedd9e"
        ),
        "uid": 0,
    },
    "system_libnetd_client": {
        "bytes": 52_368,
        "gid": 0,
        "mode": "0644",
        "nlink": 1,
        "path": "/system/lib64/libnetd_client.so",
        "sha256": (
            "sha256:d4aedc713a2d6f06214faa6c27ea333909a685a717d12b5a750d134ec4733c89"
        ),
        "uid": 0,
    },
}
PYTHON_RUNTIME_BASE_IDENTITY = {
    "artifact_inputs": PYTHON_RUNTIME_ARTIFACTS,
    "base_executable": f"{PHONE_PREFIX}/bin/python",
    "base_prefix": PHONE_PREFIX,
    "exec_prefix": PHONE_PREFIX,
    "executable_mapping_artifact_roles": list(sorted(PYTHON_RUNTIME_ARTIFACTS)),
    "kernel_executable_mapping_boundary": ["[vdso]"],
    "launch_environment": BUILD_DRIVER_LAUNCH_ENVIRONMENT,
    "proc_self_exe": f"{PHONE_PREFIX}/bin/python3.13",
    "base_exec_prefix": PHONE_PREFIX,
    "python_prefix": PHONE_PREFIX,
    "sys_executable": f"{PHONE_PREFIX}/bin/python",
    "startup_flags": {
        "dont_write_bytecode": 1,
        "ignore_environment": 1,
        "isolated": 1,
        "no_site": 1,
        "no_user_site": 1,
        "optimize": 0,
        "safe_path": True,
    },
    "startup_sys_path": [
        f"{PHONE_PREFIX}/lib/python313.zip",
        f"{PHONE_PREFIX}/lib/python3.13",
        f"{PHONE_PREFIX}/lib/python3.13/lib-dynload",
    ],
    "stdlib_tree": PYTHON_RUNTIME_STDLIB_TREE,
    "loaded_module_origin_policy": {
        "admitted_extension_root": f"{PHONE_PREFIX}/lib/python3.13/lib-dynload",
        "admitted_source_root": f"{PHONE_PREFIX}/lib/python3.13",
        "sourceless_file_loader_forbidden": True,
        "stdlib_cached_bytecode_must_be_under_absent_pycache_prefix": True,
    },
    "stdlib_executable_mapping_policy": (
        "exact_loaded_ExtensionFileLoader_origins_plus_manifest_bound_dependencies"
    ),
    "unexpected_executable_file_mappings_forbidden": True,
}


def _runtime_file_identity(
    literal_path: str,
    resolved_path: str,
    *,
    sha256: str,
    size: int,
    mode: str,
    uid: int,
    gid: int,
    symlink_target: str | None = None,
    literal_mode: str | None = None,
    literal_uid: int | None = None,
    literal_gid: int | None = None,
) -> dict[str, Any]:
    return {
        "bytes": size,
        "literal_entry_type": (
            "symbolic_link" if symlink_target is not None else "regular_file"
        ),
        "literal_gid": gid if literal_gid is None else literal_gid,
        "literal_mode": mode if literal_mode is None else literal_mode,
        "literal_nlink": 1,
        "literal_path": literal_path,
        "literal_symlink_target": symlink_target,
        "literal_uid": uid if literal_uid is None else literal_uid,
        "resolved_entry_type": "regular_file",
        "resolved_gid": gid,
        "resolved_mode": mode,
        "resolved_nlink": 1,
        "resolved_path": resolved_path,
        "resolved_uid": uid,
        "sha256": sha256,
    }


TOOL_RUNTIME_INPUTS = {
    "android_bionic_libc": _runtime_file_identity(
        "/apex/com.android.runtime/lib64/bionic/libc.so",
        "/apex/com.android.runtime/lib64/bionic/libc.so",
        sha256="sha256:b4d95dc39a379dbe5049ce033f019b01a2f10dcf507562e83c72eef901d6ebcf",
        size=1_143_072,
        mode="0644",
        uid=1000,
        gid=1000,
    ),
    "android_bionic_libdl": _runtime_file_identity(
        "/system/lib64/libdl.so",
        "/apex/com.android.runtime/lib64/bionic/libdl.so",
        sha256="sha256:7abc47c96a4f49d52647e7f1d2045d3eb9ba4d9766c1d7f225e6aa229fa9f479",
        size=50_760,
        mode="0644",
        uid=1000,
        gid=1000,
        symlink_target="/apex/com.android.runtime/lib64/bionic/libdl.so",
        literal_mode="0644",
        literal_uid=0,
        literal_gid=0,
    ),
    "android_bionic_libm": _runtime_file_identity(
        "/system/lib64/libm.so",
        "/apex/com.android.runtime/lib64/bionic/libm.so",
        sha256="sha256:2a99c9ac7a12461663ec31b8d4ee3404ee99a1dca53f7c30b248bcccb155eefc",
        size=249_192,
        mode="0644",
        uid=1000,
        gid=1000,
        symlink_target="/apex/com.android.runtime/lib64/bionic/libm.so",
        literal_mode="0644",
        literal_uid=0,
        literal_gid=0,
    ),
    "android_ld": _runtime_file_identity(
        "/system/lib64/ld-android.so",
        "/system/lib64/ld-android.so",
        sha256="sha256:599ae148e0abc4a93d0d20915338c494a2cbb5df5ba28257f0ac84e6f0e3447a",
        size=34_144,
        mode="0644",
        uid=0,
        gid=0,
    ),
    "android_linker64": _runtime_file_identity(
        "/system/bin/linker64",
        "/apex/com.android.runtime/bin/linker64",
        sha256="sha256:6aa1b8bcf1da7e8b48f67f78eebaa2d9356c76ad3c9809bd5576b579907d7f9e",
        size=2_160_952,
        mode="0755",
        uid=0,
        gid=2000,
        symlink_target="/apex/com.android.runtime/bin/linker64",
        literal_mode="0755",
        literal_uid=0,
        literal_gid=2000,
    ),
    "libclang_cpp": _runtime_file_identity(
        f"{PHONE_PREFIX}/lib/libclang-cpp.so",
        f"{PHONE_PREFIX}/lib/libclang-cpp.so",
        sha256="sha256:279758cd28398a44d0f036474ccd4839e1ba0c44bcbfc44cdb05a28527b0227d",
        size=59_130_224,
        mode="0600",
        uid=PHONE_UID,
        gid=PHONE_GID,
    ),
    "libffi": _runtime_file_identity(
        f"{PHONE_PREFIX}/lib/libffi.so",
        f"{PHONE_PREFIX}/lib/libffi.so",
        sha256="sha256:11cfbf6e8a9d18ebc7dd4f5a1acb08404b1dea9503e5ca13066d1b0fa01435e1",
        size=86_144,
        mode="0700",
        uid=PHONE_UID,
        gid=PHONE_GID,
    ),
    "libiconv": _runtime_file_identity(
        f"{PHONE_PREFIX}/lib/libiconv.so",
        f"{PHONE_PREFIX}/lib/libiconv.so",
        sha256="sha256:763c461c53d47e4f10b585b33ed6589949ce7765aa560f4b2aedfc7e4885cae2",
        size=1_082_512,
        mode="0600",
        uid=PHONE_UID,
        gid=PHONE_GID,
    ),
    "libicudata": _runtime_file_identity(
        f"{PHONE_PREFIX}/lib/libicudata.so.78",
        f"{PHONE_PREFIX}/lib/libicudata.so.78.3",
        sha256="sha256:82b40055d3f2eada13b5816069c5bc2d82a4fa5b919fad4f69b1e83f5382ec7a",
        size=33_108_952,
        mode="0700",
        uid=PHONE_UID,
        gid=PHONE_GID,
        symlink_target="libicudata.so.78.3",
        literal_mode="0777",
    ),
    "libicuuc": _runtime_file_identity(
        f"{PHONE_PREFIX}/lib/libicuuc.so.78",
        f"{PHONE_PREFIX}/lib/libicuuc.so.78.3",
        sha256="sha256:104dc1ed87acd79b200cac3998bbfcdcc02cc01d139f5c58a8c8d363b4f6d49d",
        size=1_867_696,
        mode="0700",
        uid=PHONE_UID,
        gid=PHONE_GID,
        symlink_target="libicuuc.so.78.3",
        literal_mode="0777",
    ),
    "libllvm": _runtime_file_identity(
        f"{PHONE_PREFIX}/lib/libLLVM.so",
        f"{PHONE_PREFIX}/lib/libLLVM.so",
        sha256="sha256:d8157ef272769f24142408f819e9eb27139e9c3b0fecbd468fe5416e77c402ce",
        size=129_366_048,
        mode="0600",
        uid=PHONE_UID,
        gid=PHONE_GID,
    ),
    "libxml2": _runtime_file_identity(
        f"{PHONE_PREFIX}/lib/libxml2.so.16",
        f"{PHONE_PREFIX}/lib/libxml2.so.16.1.3",
        sha256="sha256:541f9a23a573322ffd6f31f2f28af0c4f614bfb547441006c15ddc0192f35366",
        size=1_048_952,
        mode="0700",
        uid=PHONE_UID,
        gid=PHONE_GID,
        symlink_target="libxml2.so.16.1.3",
        literal_mode="0777",
    ),
    "libz": _runtime_file_identity(
        f"{PHONE_PREFIX}/lib/libz.so.1",
        f"{PHONE_PREFIX}/lib/libz.so.1.3.2",
        sha256="sha256:6d1a271adb9864fd66d696c746eac7a43faaa158b1370d32774ef73f1fe799ef",
        size=72_232,
        mode="0700",
        uid=PHONE_UID,
        gid=PHONE_GID,
        symlink_target="libz.so.1.3.2",
        literal_mode="0777",
    ),
    "libzstd": _runtime_file_identity(
        f"{PHONE_PREFIX}/lib/libzstd.so.1",
        f"{PHONE_PREFIX}/lib/libzstd.so.1.5.7",
        sha256="sha256:5baa1d62cdd945afb01ae0a8d4ee8cdd3bcb8ec4d21e90b30ef017655a86bebf",
        size=820_840,
        mode="0600",
        uid=PHONE_UID,
        gid=PHONE_GID,
        symlink_target="libzstd.so.1.5.7",
        literal_mode="0777",
    ),
    "termux_libcxx": _runtime_file_identity(
        f"{PHONE_PREFIX}/lib/libc++_shared.so",
        f"{PHONE_PREFIX}/lib/libc++_shared.so",
        sha256="sha256:e09c2f45cf4cf8ae574f94b6c2650d99ead0d332d5396f6613f062a2d2d73540",
        size=1_374_336,
        mode="0700",
        uid=PHONE_UID,
        gid=PHONE_GID,
    ),
}
TOOL_RUNTIME_INPUT_ROLES = tuple(sorted(TOOL_RUNTIME_INPUTS))
TERMUX_LIBRARY_RUNPATH = f"{PHONE_PREFIX}/lib"
TOOL_RUNTIME_DEPENDENCY_GRAPH = {
    "android_bionic_libc": {
        "interpreter": None,
        "needed": ["ld-android.so", "libdl.so"],
        "rpath": None,
        "runpath": None,
        "soname": "libc.so",
    },
    "android_bionic_libdl": {
        "interpreter": None,
        "needed": ["ld-android.so"],
        "rpath": None,
        "runpath": None,
        "soname": "libdl.so",
    },
    "android_bionic_libm": {
        "interpreter": None,
        "needed": ["libc.so"],
        "rpath": None,
        "runpath": None,
        "soname": "libm.so",
    },
    "android_ld": {
        "interpreter": None,
        "needed": [],
        "rpath": None,
        "runpath": None,
        "soname": "ld-android.so",
    },
    "android_linker64": {
        "interpreter": None,
        "needed": [],
        "rpath": None,
        "runpath": None,
        "soname": "ld-android.so",
    },
    "compiler": {
        "interpreter": "/system/bin/linker64",
        "needed": ["libc.so", "libclang-cpp.so", "libLLVM.so", "libc++_shared.so"],
        "rpath": None,
        "runpath": TERMUX_LIBRARY_RUNPATH,
        "soname": None,
    },
    "libclang_cpp": {
        "interpreter": None,
        "needed": ["libc.so", "libLLVM.so", "libc++_shared.so", "libm.so"],
        "rpath": None,
        "runpath": TERMUX_LIBRARY_RUNPATH,
        "soname": "libclang-cpp.so",
    },
    "libffi": {
        "interpreter": None,
        "needed": ["libc.so"],
        "rpath": None,
        "runpath": f"{TERMUX_LIBRARY_RUNPATH}:{TERMUX_LIBRARY_RUNPATH}",
        "soname": "libffi.so",
    },
    "libiconv": {
        "interpreter": None,
        "needed": ["libc.so"],
        "rpath": None,
        "runpath": TERMUX_LIBRARY_RUNPATH,
        "soname": "libiconv.so",
    },
    "libicudata": {
        "interpreter": None,
        "needed": [],
        "rpath": None,
        "runpath": TERMUX_LIBRARY_RUNPATH,
        "soname": "libicudata.so.78",
    },
    "libicuuc": {
        "interpreter": None,
        "needed": [
            "libicudata.so.78",
            "libc.so",
            "libm.so",
            "libc++_shared.so",
            "libdl.so",
        ],
        "rpath": None,
        "runpath": TERMUX_LIBRARY_RUNPATH,
        "soname": "libicuuc.so.78",
    },
    "libllvm": {
        "interpreter": None,
        "needed": [
            "libffi.so",
            "libdl.so",
            "libc.so",
            "libm.so",
            "libz.so.1",
            "libzstd.so.1",
            "libxml2.so.16",
            "libc++_shared.so",
        ],
        "rpath": None,
        "runpath": TERMUX_LIBRARY_RUNPATH,
        "soname": "libLLVM.so",
    },
    "libxml2": {
        "interpreter": None,
        "needed": [
            "libm.so",
            "libz.so.1",
            "libicuuc.so.78",
            "libc.so",
            "libiconv.so",
            "libdl.so",
        ],
        "rpath": None,
        "runpath": TERMUX_LIBRARY_RUNPATH,
        "soname": "libxml2.so.16",
    },
    "libz": {
        "interpreter": None,
        "needed": ["libc.so"],
        "rpath": None,
        "runpath": TERMUX_LIBRARY_RUNPATH,
        "soname": "libz.so.1",
    },
    "libzstd": {
        "interpreter": None,
        "needed": ["libc.so"],
        "rpath": None,
        "runpath": TERMUX_LIBRARY_RUNPATH,
        "soname": "libzstd.so.1",
    },
    "linker": {
        "interpreter": "/system/bin/linker64",
        "needed": [
            "libc.so",
            "libz.so.1",
            "libzstd.so.1",
            "libLLVM.so",
            "libc++_shared.so",
        ],
        "rpath": None,
        "runpath": TERMUX_LIBRARY_RUNPATH,
        "soname": None,
    },
    "termux_libcxx": {
        "interpreter": None,
        "needed": ["libc.so", "libm.so", "libdl.so"],
        "rpath": None,
        "runpath": None,
        "soname": "libc++_shared.so",
    },
}
TOOL_RUNTIME_SONAME_ROLES = {
    "ld-android.so": "android_ld",
    "libLLVM.so": "libllvm",
    "libc++_shared.so": "termux_libcxx",
    "libc.so": "android_bionic_libc",
    "libclang-cpp.so": "libclang_cpp",
    "libdl.so": "android_bionic_libdl",
    "libffi.so": "libffi",
    "libiconv.so": "libiconv",
    "libicudata.so.78": "libicudata",
    "libicuuc.so.78": "libicuuc",
    "libm.so": "android_bionic_libm",
    "libxml2.so.16": "libxml2",
    "libz.so.1": "libz",
    "libzstd.so.1": "libzstd",
}
TOOL_RUNTIME_IDENTITY = {
    "dependency_graph": TOOL_RUNTIME_DEPENDENCY_GRAPH,
    "interpreter_role": "android_linker64",
    "recursive_resolution_complete": True,
    "runtime_inputs": TOOL_RUNTIME_INPUTS,
    "schema_version": RUNTIME_DEPENDENCY_CLOSURE_SCHEMA,
    "soname_roles": TOOL_RUNTIME_SONAME_ROLES,
    "tool_roots": {
        "compiler": f"{PHONE_PREFIX}/bin/clang-21",
        "linker": f"{PHONE_PREFIX}/bin/lld",
    },
}

ACTUAL_LOADER_EXPECTED_RESOLUTION = {
    "compiler": (
        ("linux-vdso.so.1", "kernel_vdso"),
        ("libc.so", "android_bionic_libc"),
        ("libclang-cpp.so", "libclang_cpp"),
        ("libLLVM.so", "libllvm"),
        ("libc++_shared.so", "termux_libcxx"),
        ("libdl.so", "android_bionic_libdl"),
        ("libm.so", "android_bionic_libm"),
        ("libffi.so", "libffi"),
        ("libz.so.1", "libz"),
        ("libzstd.so.1", "libzstd"),
        ("libxml2.so.16", "libxml2"),
        ("libicuuc.so.78", "libicuuc"),
        ("libiconv.so", "libiconv"),
        ("libicudata.so.78", "libicudata"),
    ),
    "linker": (
        ("linux-vdso.so.1", "kernel_vdso"),
        ("libc.so", "android_bionic_libc"),
        ("libz.so.1", "libz"),
        ("libzstd.so.1", "libzstd"),
        ("libLLVM.so", "libllvm"),
        ("libc++_shared.so", "termux_libcxx"),
        ("libdl.so", "android_bionic_libdl"),
        ("libffi.so", "libffi"),
        ("libm.so", "android_bionic_libm"),
        ("libxml2.so.16", "libxml2"),
        ("libicuuc.so.78", "libicuuc"),
        ("libiconv.so", "libiconv"),
        ("libicudata.so.78", "libicudata"),
    ),
}
LOADER_LIST_LINE_RE = re.compile(
    rb"\t(?P<soname>[A-Za-z0-9_+.-]+) => "
    rb"(?P<path>\[vdso\]|/[^\x00\x09\x0a\x0d ]+) "
    rb"\(0x(?P<address>[0-9a-f]+)\)\Z"
)

BUILD_ENVIRONMENT = {
    "ANDROID_ROOT": "/system",
    "HOME": PHONE_HOME,
    "LC_ALL": "C",
    "PATH": f"{PHONE_PREFIX}/bin:/system/bin",
}
COMPILE_ARGV_TEMPLATE = (
    COMPILER_PATH,
    "--no-default-config",
    "--target=aarch64-linux-android30",
    "-std=c17",
    "-O2",
    "-Wall",
    "-Wextra",
    "-Werror",
    "-pedantic",
    "-Wshadow",
    "-Wconversion",
    "-Wsign-conversion",
    "-Wstrict-prototypes",
    "-fPIE",
    "-fstack-protector-strong",
    "-D_FORTIFY_SOURCE=2",
    "-fno-ident",
    "-nostdinc",
    "-resource-dir",
    "$RESOURCE_DIRECTORY",
    "-isystem",
    "$RESOURCE_INCLUDE_ROOT",
    "-isystem",
    "$ARCH_INCLUDE_ROOT",
    "-isystem",
    "$SYSTEM_INCLUDE_ROOT",
    "-iquote",
    "$HEADER_SHIM_DIRECTORY",
    "-c",
    "-x",
    "c",
    "$HELD_SOURCE",
    "-o",
    "$OBJECT",
)
LINK_ARGV_TEMPLATE = (
    LINKER_PATH,
    "-flavor",
    "gnu",
    "-EL",
    "--fix-cortex-a53-843419",
    "-z",
    "now",
    "-z",
    "relro",
    "-z",
    "max-page-size=16384",
    "--use-android-relr-tags",
    "--pack-dyn-relocs=relr",
    "--hash-style=gnu",
    "--eh-frame-hdr",
    "-m",
    "aarch64linux",
    "-pie",
    "-dynamic-linker",
    "/system/bin/linker64",
    "--build-id=none",
    "--no-undefined",
    "-z",
    "noexecstack",
    "-o",
    "$OUTPUT",
    "$HELD_FD:crtbegin_dynamic",
    "$HELD_OBJECT:cur0s_sha256",
    "$HELD_OBJECT:cur0s_native_preflight",
    "$HELD_FD:clang_rt_builtins",
    "$HELD_FD:libunwind",
    "--as-needed",
    "$HELD_FD:android_libdl",
    "--no-as-needed",
    "$HELD_FD:android_libc",
    "$HELD_FD:clang_rt_builtins",
    "$HELD_FD:libunwind",
    "--as-needed",
    "$HELD_FD:android_libdl",
    "--no-as-needed",
    "$HELD_FD:crtend_android",
)
TEST_HOOK_MARKERS = (
    b"CUR0S_PREFLIGHT_TEST_SIGNAL_FD",
    b"CUR0S_PREFLIGHT_TEST_RESUME_FD",
)

MAX_SOURCE_BYTES = 4 * 1024 * 1024
MAX_BINARY_BYTES = 16 * 1024 * 1024
MAX_RUNTIME_FILE_BYTES = 256 * 1024 * 1024
MAX_PROCESS_OUTPUT_BYTES = 1024 * 1024
MAX_TOOLCHAIN_TREE_ENTRIES = 200_000
MAX_TOOLCHAIN_TREE_BYTES = 1024 * 1024 * 1024
MAX_TOOLCHAIN_TREE_DEPTH = 128
PROCESS_TIMEOUT_SECONDS = 600
TREE_CANONICALIZATION = (
    "sorted_relative_POSIX_paths_canonical_JSON_type_mode_uid_gid_nlink_"
    "regular_bytes_sha256_or_literal_internal_symlink_target_root_excluded"
)


class BuildError(RuntimeError):
    """The deterministic build failed closed."""


@dataclass(frozen=True)
class BuildConfig:
    source_root: Path
    action_root: Path
    compiler_path: Path
    linker_path: Path
    resource_directory: Path
    resource_include_root: Path
    system_include_root: Path
    arch_include_root: Path
    link_input_paths: Mapping[str, Path]
    expected_uid: int
    expected_gid: int

    @property
    def checkout_root(self) -> Path:
        return self.source_root

    @property
    def build_root(self) -> Path:
        return self.action_root / BUILD_ROOT_NAME

    @property
    def build_one_directory(self) -> Path:
        return self.build_root / "build-one"

    @property
    def build_two_directory(self) -> Path:
        return self.build_root / "build-two"

    @property
    def build_one_output(self) -> Path:
        return self.build_one_directory / "cur0s_native_preflight"

    @property
    def build_two_output(self) -> Path:
        return self.build_two_directory / "cur0s_native_preflight"

    @property
    def final_binary(self) -> Path:
        return self.action_root / "cur0s_native_preflight"

    @property
    def receipt_path(self) -> Path:
        return self.action_root / RECEIPT_NAME

    @property
    def header_shim_directory(self) -> Path:
        return self.build_root / "held-header"

    @property
    def pycache_prefix(self) -> Path:
        return self.action_root / "native_preflight_build_pycache_forbidden"

    def object_paths(self, directory: Path) -> dict[str, Path]:
        return {
            "cur0s_native_preflight": directory / "cur0s_native_preflight.o",
            "cur0s_sha256": directory / "cur0s_sha256.o",
        }


@dataclass(frozen=True)
class FileSnapshot:
    payload: bytes
    identity: tuple[int, ...]
    mode: str
    uid: int
    gid: int
    nlink: int

    @property
    def digest(self) -> dict[str, Any]:
        return {
            "bytes": len(self.payload),
            "sha256": prefixed_sha256(self.payload),
        }


@dataclass
class AttestedTool:
    identity: dict[str, Any]
    resolved_fd: int
    volatile_identity: tuple[int, ...]

    def close(self) -> None:
        if self.resolved_fd >= 0:
            os.close(self.resolved_fd)
            self.resolved_fd = -1


@dataclass
class HeldFileInput:
    role: str
    path: Path
    identity: dict[str, Any]
    resolved_fd: int
    volatile_identity: tuple[int, ...]

    def close(self) -> None:
        if self.resolved_fd >= 0:
            os.close(self.resolved_fd)
            self.resolved_fd = -1


@dataclass
class RuntimeFileInput:
    role: str
    identity: dict[str, Any]
    literal_volatile_identity: tuple[int, ...]
    resolved_fd: int
    resolved_volatile_identity: tuple[int, ...]

    def close(self) -> None:
        if self.resolved_fd >= 0:
            os.close(self.resolved_fd)
            self.resolved_fd = -1


@dataclass
class RuntimeGuard:
    identity: dict[str, Any]
    revalidate_action: Callable[[], None]
    close_action: Callable[[], None]

    def revalidate(self) -> None:
        self.revalidate_action()

    def close(self) -> None:
        self.close_action()


@dataclass(frozen=True)
class TreeSnapshot:
    identity: dict[str, Any]
    volatile_identity: tuple[int, ...]


@dataclass(frozen=True)
class BuildResult:
    binary: FileSnapshot
    objects: Mapping[str, FileSnapshot]


ProcessRunner = Callable[
    [Sequence[str], Path, Mapping[str, str], int | None, Sequence[int]],
    subprocess.CompletedProcess[bytes],
]
ReceiptValidator = Callable[
    [Mapping[str, Any], str, Mapping[str, Mapping[str, Any]]],
    Mapping[str, Any],
]
PythonRuntimeAttestor = Callable[[BuildConfig, str], RuntimeGuard]
ToolRuntimeAttestor = Callable[
    [AttestedTool, AttestedTool, Path, ProcessRunner],
    RuntimeGuard,
]


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def prefixed_sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def canonical_sha256(value: Any) -> str:
    return prefixed_sha256(canonical_json_bytes(value))


def mode_text(mode: int) -> str:
    return f"{stat.S_IMODE(mode):04o}"


def stat_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_uid,
        value.st_gid,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def canonical_absolute_path(path: Path) -> Path:
    text = os.fspath(path)
    if (
        not text.startswith("/")
        or "\x00" in text
        or text != os.path.normpath(text)
        or text == "/"
    ):
        raise BuildError("path_not_canonical_absolute")
    return Path(text)


def open_absolute_nofollow(
    path: Path,
    *,
    directory: bool = False,
    path_only_directory: bool = False,
) -> int:
    if path_only_directory and not directory:
        raise BuildError("path_only_requires_directory")
    canonical = canonical_absolute_path(path)
    path_only = getattr(os, "O_PATH", 0)
    ancestor_access = path_only if path_only else os.O_RDONLY
    ancestor_flags = ancestor_access | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    current_fd = os.open("/", ancestor_flags)
    try:
        components = canonical.parts[1:]
        for index, component in enumerate(components):
            is_final = index == len(components) - 1
            flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
            if not is_final:
                flags = ancestor_flags
            elif path_only_directory:
                flags = ancestor_flags
            elif directory:
                flags |= os.O_DIRECTORY
            next_fd = os.open(component, flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        result = current_fd
        current_fd = -1
        return result
    except OSError as error:
        raise BuildError("secure_path_open_failed") from error
    finally:
        if current_fd >= 0:
            os.close(current_fd)


def read_regular_file(
    path: Path,
    *,
    byte_limit: int,
    expected_uid: int | None = None,
    expected_gid: int | None = None,
    expected_mode: str | None = None,
) -> FileSnapshot:
    fd = open_absolute_nofollow(path)
    try:
        initial = os.fstat(fd)
        if (
            not stat.S_ISREG(initial.st_mode)
            or initial.st_nlink != 1
            or initial.st_size <= 0
            or initial.st_size > byte_limit
        ):
            raise BuildError("regular_file_identity_invalid")
        if expected_uid is not None and initial.st_uid != expected_uid:
            raise BuildError("regular_file_uid_mismatch")
        if expected_gid is not None and initial.st_gid != expected_gid:
            raise BuildError("regular_file_gid_mismatch")
        if expected_mode is not None and mode_text(initial.st_mode) != expected_mode:
            raise BuildError("regular_file_mode_mismatch")
        payload = bytearray()
        while len(payload) < initial.st_size:
            chunk = os.read(fd, min(1024 * 1024, initial.st_size - len(payload)))
            if not chunk:
                raise BuildError("regular_file_read_truncated")
            payload.extend(chunk)
        if os.read(fd, 1):
            raise BuildError("regular_file_grew_during_read")
        final = os.fstat(fd)
        entry = os.stat(path, follow_symlinks=False)
        if not (stat_identity(initial) == stat_identity(final) == stat_identity(entry)):
            raise BuildError("regular_file_changed_during_read")
        return FileSnapshot(
            payload=bytes(payload),
            identity=stat_identity(final),
            mode=mode_text(final.st_mode),
            uid=final.st_uid,
            gid=final.st_gid,
            nlink=final.st_nlink,
        )
    finally:
        os.close(fd)


def _parent_fd_and_name(
    path: Path,
    *,
    path_only: bool = False,
) -> tuple[int, str]:
    canonical = canonical_absolute_path(path)
    return (
        open_absolute_nofollow(
            canonical.parent,
            directory=True,
            path_only_directory=path_only,
        ),
        canonical.name,
    )


def require_private_directory(path: Path, uid: int, gid: int) -> None:
    fd = open_absolute_nofollow(path, directory=True)
    try:
        information = os.fstat(fd)
        if (
            not stat.S_ISDIR(information.st_mode)
            or mode_text(information.st_mode) != "0700"
            or information.st_uid != uid
            or information.st_gid != gid
        ):
            raise BuildError("private_directory_identity_mismatch")
    finally:
        os.close(fd)


def create_private_directory(path: Path, uid: int, gid: int) -> None:
    parent_fd, name = _parent_fd_and_name(path)
    child_fd = -1
    try:
        os.mkdir(name, 0o700, dir_fd=parent_fd)
        child_fd = os.open(
            name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
        os.fchmod(child_fd, 0o700)
        information = os.fstat(child_fd)
        if (
            not stat.S_ISDIR(information.st_mode)
            or mode_text(information.st_mode) != "0700"
            or information.st_uid != uid
            or information.st_gid != gid
        ):
            raise BuildError("created_private_directory_identity_mismatch")
        os.fsync(child_fd)
        os.fsync(parent_fd)
    except FileExistsError as error:
        raise BuildError("private_build_directory_already_exists") from error
    finally:
        if child_fd >= 0:
            os.close(child_fd)
        os.close(parent_fd)


def run_process(
    arguments: Sequence[str],
    cwd: Path,
    environment: Mapping[str, str],
    executable_fd: int | None = None,
    inherited_fds: Sequence[int] = (),
) -> subprocess.CompletedProcess[bytes]:
    keyword_arguments: dict[str, Any] = {}
    pass_fds = set(inherited_fds)
    if executable_fd is not None:
        pass_fds.add(executable_fd)
        keyword_arguments["executable"] = f"/proc/self/fd/{executable_fd}"
    if pass_fds:
        if any(fd < 0 for fd in pass_fds):
            raise BuildError("process_inherited_descriptor_invalid")
        keyword_arguments["pass_fds"] = tuple(sorted(pass_fds))
    process: subprocess.Popen[bytes] | None = None
    selector = selectors.DefaultSelector()
    streams = {"stdout": bytearray(), "stderr": bytearray()}

    def kill_process_group() -> None:
        if process is None:
            return
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        finally:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired as error:
                raise BuildError("process_group_reap_failed") from error

    try:
        process = subprocess.Popen(
            list(arguments),
            cwd=cwd,
            env=dict(environment),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            **keyword_arguments,
        )
        if process.stdout is None or process.stderr is None:
            raise BuildError("process_pipe_creation_failed")
        for name, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        deadline = time.monotonic() + PROCESS_TIMEOUT_SECONDS
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                kill_process_group()
                raise BuildError("process_timeout")
            for key, _events in selector.select(timeout=min(remaining, 0.25)):
                captured = sum(len(payload) for payload in streams.values())
                read_limit = min(65536, MAX_PROCESS_OUTPUT_BYTES - captured + 1)
                try:
                    chunk = os.read(key.fileobj.fileno(), read_limit)
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                    continue
                streams[key.data].extend(chunk)
                if sum(len(payload) for payload in streams.values()) > (
                    MAX_PROCESS_OUTPUT_BYTES
                ):
                    kill_process_group()
                    raise BuildError("process_output_limit_exceeded")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            kill_process_group()
            raise BuildError("process_timeout")
        try:
            returncode = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired as error:
            kill_process_group()
            raise BuildError("process_timeout") from error
        return subprocess.CompletedProcess(
            list(arguments),
            returncode,
            bytes(streams["stdout"]),
            bytes(streams["stderr"]),
        )
    except BuildError:
        if process is not None and process.poll() is None:
            kill_process_group()
        raise
    except (OSError, subprocess.SubprocessError) as error:
        if process is not None and process.poll() is None:
            kill_process_group()
        raise BuildError("process_execution_failed") from error
    finally:
        selector.close()
        if process is not None:
            for stream in (process.stdout, process.stderr):
                if stream is not None and not stream.closed:
                    stream.close()


def build_source_binding(
    config: BuildConfig,
    relative_path: str,
) -> dict[str, Any]:
    if relative_path not in NATIVE_SOURCE_FILES:
        raise BuildError("native_source_path_not_admitted")
    snapshot = read_regular_file(
        config.source_root / relative_path,
        byte_limit=MAX_SOURCE_BYTES,
    )
    blob_header = f"blob {len(snapshot.payload)}\0".encode("ascii")
    observed_blob = hashlib.sha1(
        blob_header + snapshot.payload,
        usedforsecurity=False,
    ).hexdigest()
    return {
        "bytes": len(snapshot.payload),
        "git_blob_oid": observed_blob,
        "sha256": prefixed_sha256(snapshot.payload),
    }


def snapshot_source_bindings(config: BuildConfig) -> dict[str, dict[str, Any]]:
    """Bind only held worktree bytes; the host later binds them to the Git tree."""

    return {
        relative_path: build_source_binding(config, relative_path)
        for relative_path in NATIVE_SOURCE_FILES
    }


def _symlink_snapshot(path: Path) -> tuple[os.stat_result, str]:
    parent_fd, name = _parent_fd_and_name(path, path_only=True)
    try:
        initial = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISLNK(initial.st_mode) or initial.st_nlink != 1:
            raise BuildError("build_tool_literal_not_single_symlink")
        target = os.readlink(name, dir_fd=parent_fd)
        final = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if stat_identity(initial) != stat_identity(final):
            raise BuildError("build_tool_symlink_changed")
        return final, target
    finally:
        os.close(parent_fd)


def _resolved_symlink_path(literal_path: Path, target: str) -> Path:
    if not target or "\x00" in target:
        raise BuildError("build_tool_symlink_target_invalid")
    combined = Path(target) if target.startswith("/") else literal_path.parent / target
    return canonical_absolute_path(Path(os.path.normpath(os.fspath(combined))))


def attest_build_tool_file(
    role: str,
    literal_path: Path,
) -> AttestedTool:
    if role not in {"compiler", "linker"}:
        raise BuildError("build_tool_role_invalid")
    literal_information, target = _symlink_snapshot(literal_path)
    resolved_path = _resolved_symlink_path(literal_path, target)
    resolved_fd = open_absolute_nofollow(resolved_path)
    try:
        initial = os.fstat(resolved_fd)
        if (
            not stat.S_ISREG(initial.st_mode)
            or initial.st_nlink != 1
            or initial.st_size <= 0
            or initial.st_size > MAX_BINARY_BYTES
        ):
            raise BuildError("build_tool_resolved_identity_invalid")
        digest, byte_count = hash_open_descriptor(resolved_fd)
        final = os.fstat(resolved_fd)
        entry = os.stat(resolved_path, follow_symlinks=False)
        if not (stat_identity(initial) == stat_identity(final) == stat_identity(entry)):
            raise BuildError("build_tool_resolved_changed")
        identity = {
            "literal_path": os.fspath(literal_path),
            "literal_entry_type": "symbolic_link",
            "literal_mode": mode_text(literal_information.st_mode),
            "literal_uid": literal_information.st_uid,
            "literal_gid": literal_information.st_gid,
            "literal_nlink": literal_information.st_nlink,
            "literal_symlink_target": target,
            "resolved_path": os.fspath(resolved_path),
            "resolved_entry_type": "regular_file",
            "sha256": digest,
            "bytes": byte_count,
            "resolved_mode": mode_text(final.st_mode),
            "resolved_uid": final.st_uid,
            "resolved_gid": final.st_gid,
            "resolved_nlink": final.st_nlink,
        }
        volatile_identity = stat_identity(literal_information) + stat_identity(final)
        return AttestedTool(identity, resolved_fd, volatile_identity)
    except Exception:
        os.close(resolved_fd)
        raise


def probe_build_tool_identity(
    role: str,
    tool: AttestedTool,
    source_root: Path,
    process_runner: ProcessRunner = run_process,
) -> dict[str, Any]:
    suffixes = {
        "compiler": ("--version",),
        "linker": ("-flavor", "gnu", "--version"),
    }
    if role not in suffixes or tool.resolved_fd < 0:
        raise BuildError("build_tool_probe_role_or_descriptor_invalid")
    suffix = suffixes[role]
    version = process_runner(
        (tool.identity["literal_path"], *suffix),
        source_root,
        BUILD_ENVIRONMENT,
        tool.resolved_fd,
        (),
    )
    if version.returncode != 0:
        raise BuildError("build_tool_version_failed")
    return {
        **tool.identity,
        "version_argv_suffix": list(suffix),
        "version_returncode": version.returncode,
        "version_stdout_bytes": len(version.stdout),
        "version_stdout_sha256": prefixed_sha256(version.stdout),
        "version_stderr_bytes": len(version.stderr),
        "version_stderr_sha256": prefixed_sha256(version.stderr),
    }


def revalidate_build_tool_file(tool: AttestedTool) -> None:
    literal_path = Path(tool.identity["literal_path"])
    literal_information, target = _symlink_snapshot(literal_path)
    resolved_path = Path(tool.identity["resolved_path"])
    information = os.fstat(tool.resolved_fd)
    entry = os.stat(resolved_path, follow_symlinks=False)
    digest, byte_count = hash_open_descriptor(tool.resolved_fd)
    volatile = stat_identity(literal_information) + stat_identity(information)
    if (
        volatile != tool.volatile_identity
        or target != tool.identity["literal_symlink_target"]
        or stat_identity(information) != stat_identity(entry)
        or digest != tool.identity["sha256"]
        or byte_count != tool.identity["bytes"]
    ):
        raise BuildError("build_tool_changed")


def hash_open_descriptor(
    fd: int,
    *,
    byte_limit: int = MAX_BINARY_BYTES,
) -> tuple[str, int]:
    try:
        os.lseek(fd, 0, os.SEEK_SET)
    except OSError as error:
        raise BuildError("descriptor_not_seekable") from error
    digest = hashlib.sha256()
    byte_count = 0
    while True:
        chunk = os.read(fd, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
        byte_count += len(chunk)
        if byte_count > byte_limit:
            raise BuildError("descriptor_oversize")
    os.lseek(fd, 0, os.SEEK_SET)
    return "sha256:" + digest.hexdigest(), byte_count


def _parse_runtime_elf(
    total_bytes: int,
    read_at: Callable[[int, int], bytes],
) -> dict[str, Any]:
    def require(offset: int, size: int, code: str) -> bytes:
        if (
            offset < 0
            or size < 0
            or offset > total_bytes
            or size > total_bytes - offset
        ):
            raise BuildError(code)
        payload = read_at(offset, size)
        if len(payload) != size:
            raise BuildError(code)
        return payload

    raw_header = require(0, 64, "runtime_ELF_header_truncated")
    if raw_header[:7] != b"\x7fELF\x02\x01\x01":
        raise BuildError("runtime_ELF_header_invalid")
    header = struct.unpack("<16sHHIQQQIHHHHHH", raw_header)
    (
        _identity,
        elf_type,
        machine,
        version,
        _entry,
        program_offset,
        _section_offset,
        _flags,
        header_size,
        program_entry_size,
        program_count,
        _section_entry_size,
        _section_count,
        _section_name_index,
    ) = header
    if (
        elf_type not in {2, 3}
        or machine != 183
        or version != 1
        or header_size != 64
        or program_entry_size != 56
        or program_count == 0
    ):
        raise BuildError("runtime_ELF_AArch64_header_mismatch")

    loads: list[tuple[int, int, int]] = []
    dynamic_segment: tuple[int, int] | None = None
    interpreter: str | None = None
    for index in range(program_count):
        raw = require(
            program_offset + index * program_entry_size,
            program_entry_size,
            "runtime_ELF_program_header_invalid",
        )
        (
            program_type,
            _program_flags,
            offset,
            virtual,
            _physical,
            file_size,
            memory_size,
            _alignment,
        ) = struct.unpack("<IIQQQQQQ", raw)
        require(offset, file_size, "runtime_ELF_segment_bounds_invalid")
        if file_size > memory_size:
            raise BuildError("runtime_ELF_segment_size_invalid")
        if program_type == 1:
            loads.append((virtual, offset, file_size))
        elif program_type == 2:
            if dynamic_segment is not None:
                raise BuildError("runtime_ELF_multiple_dynamic_segments")
            dynamic_segment = (offset, file_size)
        elif program_type == 3:
            if interpreter is not None:
                raise BuildError("runtime_ELF_multiple_interpreters")
            raw_interpreter = require(
                offset,
                file_size,
                "runtime_ELF_interpreter_bounds_invalid",
            )
            if not raw_interpreter.endswith(b"\0") or b"\0" in raw_interpreter[:-1]:
                raise BuildError("runtime_ELF_interpreter_invalid")
            try:
                interpreter = raw_interpreter[:-1].decode("ascii")
            except UnicodeDecodeError as error:
                raise BuildError("runtime_ELF_interpreter_invalid") from error

    empty = {
        "interpreter": interpreter,
        "needed": [],
        "rpath": None,
        "runpath": None,
        "soname": None,
    }
    if dynamic_segment is None:
        return empty
    dynamic_offset, dynamic_size = dynamic_segment
    if dynamic_size == 0 or dynamic_size % 16:
        raise BuildError("runtime_ELF_dynamic_segment_invalid")
    values: dict[int, list[int]] = {}
    terminated = False
    for cursor in range(dynamic_offset, dynamic_offset + dynamic_size, 16):
        tag, value = struct.unpack(
            "<QQ",
            require(cursor, 16, "runtime_ELF_dynamic_entry_invalid"),
        )
        if tag == 0:
            terminated = True
            break
        values.setdefault(tag, []).append(value)
    if not terminated:
        raise BuildError("runtime_ELF_dynamic_segment_unterminated")
    string_tags = (1, 14, 15, 29)
    if not any(values.get(tag) for tag in string_tags):
        return empty
    if len(values.get(5, [])) != 1 or len(values.get(10, [])) != 1:
        raise BuildError("runtime_ELF_string_table_missing")
    string_address = values[5][0]
    string_size = values[10][0]
    string_offset: int | None = None
    for virtual, offset, file_size in loads:
        if string_address < virtual:
            continue
        relative = string_address - virtual
        if relative <= file_size and string_size <= file_size - relative:
            string_offset = offset + relative
            break
    if string_offset is None:
        raise BuildError("runtime_ELF_string_table_unmapped")
    string_table = require(
        string_offset,
        string_size,
        "runtime_ELF_string_table_bounds_invalid",
    )

    def dynamic_string(offset: int) -> str:
        if offset >= len(string_table):
            raise BuildError("runtime_ELF_dynamic_string_offset_invalid")
        end = string_table.find(b"\0", offset)
        if end < 0:
            raise BuildError("runtime_ELF_dynamic_string_unterminated")
        try:
            result = string_table[offset:end].decode("ascii")
        except UnicodeDecodeError as error:
            raise BuildError("runtime_ELF_dynamic_string_invalid") from error
        if not result or "\x00" in result:
            raise BuildError("runtime_ELF_dynamic_string_invalid")
        return result

    for singleton_tag in (14, 15, 29):
        if len(values.get(singleton_tag, [])) > 1:
            raise BuildError("runtime_ELF_duplicate_dynamic_string")
    return {
        "interpreter": interpreter,
        "needed": [dynamic_string(offset) for offset in values.get(1, [])],
        "rpath": (dynamic_string(values[15][0]) if values.get(15) else None),
        "runpath": (dynamic_string(values[29][0]) if values.get(29) else None),
        "soname": (dynamic_string(values[14][0]) if values.get(14) else None),
    }


def parse_runtime_elf_bytes(payload: bytes) -> dict[str, Any]:
    return _parse_runtime_elf(
        len(payload),
        lambda offset, size: payload[offset : offset + size],
    )


def parse_runtime_elf_descriptor(fd: int) -> dict[str, Any]:
    information = os.fstat(fd)
    if (
        not stat.S_ISREG(information.st_mode)
        or information.st_size <= 0
        or information.st_size > MAX_RUNTIME_FILE_BYTES
    ):
        raise BuildError("runtime_ELF_descriptor_identity_invalid")
    try:
        return _parse_runtime_elf(
            information.st_size,
            lambda offset, size: os.pread(fd, size, offset),
        )
    except OSError as error:
        raise BuildError("runtime_ELF_descriptor_read_failed") from error


def _tree_symlink_is_internal(relative_path: str, target: str) -> bool:
    if not target or "\x00" in target or target.startswith("/"):
        return False
    normalized = posixpath.normpath(
        posixpath.join(posixpath.dirname(relative_path), target)
    )
    return normalized not in {".", ".."} and not normalized.startswith("../")


def snapshot_toolchain_tree(
    path: Path,
    *,
    expected_uid: int,
    expected_gid: int,
) -> TreeSnapshot:
    root_fd = open_absolute_nofollow(path, directory=True)
    records: list[dict[str, Any]] = []
    regular_bytes = 0
    regular_files = 0
    symlinks = 0

    def append_record(record: dict[str, Any]) -> None:
        if len(records) >= MAX_TOOLCHAIN_TREE_ENTRIES:
            raise BuildError("toolchain_tree_entry_limit_exceeded")
        records.append(record)

    def walk(directory_fd: int, prefix: str, depth: int) -> None:
        nonlocal regular_bytes, regular_files, symlinks
        if depth > MAX_TOOLCHAIN_TREE_DEPTH:
            raise BuildError("toolchain_tree_depth_limit_exceeded")
        try:
            with os.scandir(directory_fd) as iterator:
                entries = sorted(iterator, key=lambda entry: entry.name)
        except OSError as error:
            raise BuildError("toolchain_tree_enumeration_failed") from error
        for entry in entries:
            if entry.name in {".", ".."} or "/" in entry.name or "\x00" in entry.name:
                raise BuildError("toolchain_tree_entry_name_invalid")
            relative = f"{prefix}/{entry.name}" if prefix else entry.name
            try:
                initial = entry.stat(follow_symlinks=False)
            except OSError as error:
                raise BuildError("toolchain_tree_entry_stat_failed") from error
            common = {
                "gid": initial.st_gid,
                "mode": mode_text(initial.st_mode),
                "nlink": initial.st_nlink,
                "relative_path": relative,
                "uid": initial.st_uid,
            }
            if stat.S_ISDIR(initial.st_mode):
                child_fd = -1
                try:
                    child_fd = os.open(
                        entry.name,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                        dir_fd=directory_fd,
                    )
                    opened = os.fstat(child_fd)
                    if stat_identity(initial) != stat_identity(opened):
                        raise BuildError("toolchain_tree_directory_replaced")
                    append_record({**common, "type": "directory"})
                    walk(child_fd, relative, depth + 1)
                    final = os.stat(
                        entry.name,
                        dir_fd=directory_fd,
                        follow_symlinks=False,
                    )
                    if stat_identity(initial) != stat_identity(final):
                        raise BuildError("toolchain_tree_directory_changed")
                except OSError as error:
                    raise BuildError("toolchain_tree_directory_open_failed") from error
                finally:
                    if child_fd >= 0:
                        os.close(child_fd)
                continue
            if stat.S_ISREG(initial.st_mode):
                if initial.st_nlink != 1 or initial.st_size < 0:
                    raise BuildError("toolchain_tree_regular_identity_invalid")
                file_fd = -1
                try:
                    file_fd = os.open(
                        entry.name,
                        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                        dir_fd=directory_fd,
                    )
                    opened = os.fstat(file_fd)
                    if stat_identity(initial) != stat_identity(opened):
                        raise BuildError("toolchain_tree_regular_replaced")
                    digest = hashlib.sha256()
                    observed_bytes = 0
                    while True:
                        chunk = os.read(file_fd, 1024 * 1024)
                        if not chunk:
                            break
                        digest.update(chunk)
                        observed_bytes += len(chunk)
                        if regular_bytes + observed_bytes > MAX_TOOLCHAIN_TREE_BYTES:
                            raise BuildError("toolchain_tree_byte_limit_exceeded")
                    final_fd = os.fstat(file_fd)
                    final_entry = os.stat(
                        entry.name,
                        dir_fd=directory_fd,
                        follow_symlinks=False,
                    )
                    if (
                        not (
                            stat_identity(initial)
                            == stat_identity(opened)
                            == stat_identity(final_fd)
                            == stat_identity(final_entry)
                        )
                        or observed_bytes != initial.st_size
                    ):
                        raise BuildError("toolchain_tree_regular_changed")
                    append_record(
                        {
                            **common,
                            "bytes": observed_bytes,
                            "sha256": "sha256:" + digest.hexdigest(),
                            "type": "regular",
                        }
                    )
                    regular_bytes += observed_bytes
                    regular_files += 1
                except OSError as error:
                    raise BuildError("toolchain_tree_regular_open_failed") from error
                finally:
                    if file_fd >= 0:
                        os.close(file_fd)
                continue
            if stat.S_ISLNK(initial.st_mode):
                try:
                    target = os.readlink(entry.name, dir_fd=directory_fd)
                    final = os.stat(
                        entry.name,
                        dir_fd=directory_fd,
                        follow_symlinks=False,
                    )
                except OSError as error:
                    raise BuildError("toolchain_tree_symlink_read_failed") from error
                if (
                    initial.st_nlink != 1
                    or stat_identity(initial) != stat_identity(final)
                    or not _tree_symlink_is_internal(relative, target)
                ):
                    raise BuildError("toolchain_tree_symlink_identity_invalid")
                append_record({**common, "target": target, "type": "symlink"})
                symlinks += 1
                continue
            raise BuildError("toolchain_tree_unsupported_entry")

    try:
        initial_root = os.fstat(root_fd)
        if (
            not stat.S_ISDIR(initial_root.st_mode)
            or initial_root.st_uid != expected_uid
            or initial_root.st_gid != expected_gid
        ):
            raise BuildError("toolchain_tree_root_identity_invalid")
        walk(root_fd, "", 0)
        final_root = os.fstat(root_fd)
        entry_root = os.stat(path, follow_symlinks=False)
        if not (
            stat_identity(initial_root)
            == stat_identity(final_root)
            == stat_identity(entry_root)
        ):
            raise BuildError("toolchain_tree_root_changed")
    finally:
        os.close(root_fd)
    records.sort(key=lambda record: record["relative_path"])
    identity = {
        "canonicalization": TREE_CANONICALIZATION,
        "entry_count": len(records),
        "entry_type": "directory_tree",
        "gid": final_root.st_gid,
        "mode": mode_text(final_root.st_mode),
        "nlink": final_root.st_nlink,
        "path": os.fspath(path),
        "regular_bytes": regular_bytes,
        "regular_file_count": regular_files,
        "sha256": prefixed_sha256(canonical_json_bytes(records)),
        "symlink_count": symlinks,
        "uid": final_root.st_uid,
    }
    return TreeSnapshot(identity, stat_identity(final_root))


def snapshot_python_stdlib_tree() -> TreeSnapshot:
    expected = PYTHON_RUNTIME_STDLIB_TREE
    root_path = Path(expected["root_path"])
    root_fd = open_absolute_nofollow(root_path, directory=True)
    records: list[dict[str, Any]] = []
    regular_bytes = 0
    try:
        initial_root = os.fstat(root_fd)
        if (
            not stat.S_ISDIR(initial_root.st_mode)
            or mode_text(initial_root.st_mode) != expected["root_mode"]
            or initial_root.st_uid != expected["root_uid"]
            or initial_root.st_gid != expected["root_gid"]
            or initial_root.st_nlink != expected["root_nlink"]
        ):
            raise BuildError("python_stdlib_root_identity_mismatch")
        try:
            walk = os.fwalk(
                ".",
                topdown=True,
                follow_symlinks=False,
                dir_fd=root_fd,
            )
            for current, directory_names, file_names, directory_fd in walk:
                directory_names[:] = sorted(
                    name
                    for name in directory_names
                    if name != "__pycache__"
                    and not (current == "." and name == "site-packages")
                )
                file_names.sort()
                for name in (*directory_names, *file_names):
                    relative = posixpath.normpath(posixpath.join(current, name))
                    if relative.startswith("./"):
                        relative = relative[2:]
                    if (
                        not relative
                        or relative.startswith("../")
                        or relative == ".."
                        or "\x00" in relative
                    ):
                        raise BuildError("python_stdlib_relative_path_invalid")
                    information = os.stat(
                        name,
                        dir_fd=directory_fd,
                        follow_symlinks=False,
                    )
                    common = {
                        "mode": mode_text(information.st_mode),
                        "relative_path": relative,
                    }
                    if name.endswith(".pyc"):
                        if not stat.S_ISREG(information.st_mode):
                            raise BuildError("python_stdlib_excluded_pyc_not_regular")
                        continue
                    if stat.S_ISDIR(information.st_mode):
                        records.append({**common, "type": "directory"})
                        continue
                    if stat.S_ISLNK(information.st_mode):
                        target = os.readlink(name, dir_fd=directory_fd)
                        if not _tree_symlink_is_internal(relative, target):
                            raise BuildError("python_stdlib_external_symlink_forbidden")
                        records.append(
                            {
                                **common,
                                "target": target,
                                "type": "symlink",
                            }
                        )
                        continue
                    if (
                        not stat.S_ISREG(information.st_mode)
                        or information.st_nlink != 1
                    ):
                        raise BuildError("python_stdlib_unsafe_entry")
                    descriptor = os.open(
                        name,
                        os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                        dir_fd=directory_fd,
                    )
                    try:
                        opened = os.fstat(descriptor)
                        if stat_identity(information) != stat_identity(opened):
                            raise BuildError("python_stdlib_entry_replaced")
                        digest, size = hash_open_descriptor(
                            descriptor,
                            byte_limit=MAX_RUNTIME_FILE_BYTES,
                        )
                        final = os.fstat(descriptor)
                        if stat_identity(opened) != stat_identity(final):
                            raise BuildError("python_stdlib_entry_changed")
                    finally:
                        os.close(descriptor)
                    regular_bytes += size
                    if regular_bytes > MAX_TOOLCHAIN_TREE_BYTES:
                        raise BuildError("python_stdlib_tree_byte_limit_exceeded")
                    records.append(
                        {
                            **common,
                            "bytes": size,
                            "sha256": digest.removeprefix("sha256:"),
                            "type": "regular",
                        }
                    )
                    if len(records) > MAX_TOOLCHAIN_TREE_ENTRIES:
                        raise BuildError("python_stdlib_tree_entry_limit_exceeded")
        except OSError as error:
            raise BuildError("python_stdlib_tree_walk_failed") from error
        records.sort(key=lambda record: record["relative_path"])
        final_root = os.fstat(root_fd)
        entry_root = os.stat(root_path, follow_symlinks=False)
        if not (
            stat_identity(initial_root)
            == stat_identity(final_root)
            == stat_identity(entry_root)
        ):
            raise BuildError("python_stdlib_root_changed")
        observed = {
            **expected,
            "entry_count": len(records),
            "regular_bytes": regular_bytes,
            "root_sha256": prefixed_sha256(canonical_json_bytes(records)),
        }
        if observed != expected:
            raise BuildError("python_stdlib_tree_frozen_identity_mismatch")
        return TreeSnapshot(dict(expected), stat_identity(final_root))
    finally:
        os.close(root_fd)


def _read_proc_self_maps(limit: int = 2 * 1024 * 1024) -> bytes:
    try:
        descriptor = os.open(
            "/proc/self/maps",
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
    except OSError as error:
        raise BuildError("proc_self_maps_open_failed") from error
    try:
        payload = bytearray()
        while True:
            chunk = os.read(descriptor, min(64 * 1024, limit + 1 - len(payload)))
            if not chunk:
                return bytes(payload)
            payload.extend(chunk)
            if len(payload) > limit:
                raise BuildError("proc_self_maps_oversize")
    finally:
        os.close(descriptor)


def _parse_proc_self_maps(payload: bytes) -> list[dict[str, Any]]:
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise BuildError("proc_self_maps_encoding_invalid") from error
    result: list[dict[str, Any]] = []
    for line in text.splitlines():
        fields = line.split(None, 5)
        if len(fields) < 5:
            raise BuildError("proc_self_maps_record_invalid")
        try:
            start_text, end_text = fields[0].split("-", 1)
            major_text, minor_text = fields[3].split(":", 1)
            record = {
                "device_major": int(major_text, 16),
                "device_minor": int(minor_text, 16),
                "end": int(end_text, 16),
                "inode": int(fields[4]),
                "offset": int(fields[2], 16),
                "path": fields[5] if len(fields) == 6 else "",
                "permissions": fields[1],
                "start": int(start_text, 16),
            }
        except (TypeError, ValueError) as error:
            raise BuildError("proc_self_maps_record_invalid") from error
        permissions = record["permissions"]
        if (
            record["start"] >= record["end"]
            or len(permissions) != 4
            or any(
                permissions[index] not in admitted
                for index, admitted in enumerate(("r-", "w-", "x-", "ps"))
            )
        ):
            raise BuildError("proc_self_maps_record_invalid")
        result.append(record)
    if not result:
        raise BuildError("proc_self_maps_empty")
    return result


def _loaded_module_origin_records(config: BuildConfig) -> list[dict[str, Any]]:
    stdlib_root = os.fspath(Path(PYTHON_RUNTIME_STDLIB_TREE["root_path"]))
    extension_root = f"{stdlib_root}/lib-dynload"
    admitted_held_sources = {
        "__main__": os.fspath(
            config.source_root / "scripts/termux/build_cur0s_native_preflight.py"
        ),
        "_cur0s_build_driver_contract": os.fspath(
            config.source_root / COMMERCIAL_CONTRACT_FILE
        ),
    }
    records: list[dict[str, Any]] = []
    for name, module in sorted(sys.modules.items()):
        if module is None:
            continue
        specification = getattr(module, "__spec__", None)
        if specification is None:
            origin = getattr(module, "__file__", None)
            expected_origin = admitted_held_sources.get(name)
            if expected_origin is None or origin != expected_origin:
                raise BuildError("python_module_without_spec_not_admitted")
            records.append(
                {
                    "cached": None,
                    "loader": "explicit_held_source",
                    "name": name,
                    "origin": origin,
                    "origin_kind": "held_source",
                }
            )
            continue
        loader = specification.loader
        if isinstance(loader, type):
            loader_name = f"{loader.__module__}.{loader.__qualname__}"
        elif loader is None:
            loader_name = None
        else:
            loader_type = type(loader)
            loader_name = f"{loader_type.__module__}.{loader_type.__qualname__}"
        if loader_name is not None and loader_name.endswith(".SourcelessFileLoader"):
            raise BuildError("python_sourceless_file_loader_forbidden")
        origin = specification.origin
        cached = specification.cached
        if origin in {"built-in", "frozen"}:
            if cached is not None:
                raise BuildError("python_builtin_or_frozen_module_cached")
            origin_kind = origin.replace("-", "_")
        elif origin is None:
            if specification.submodule_search_locations is None or cached is not None:
                raise BuildError("python_namespace_module_identity_invalid")
            locations = list(specification.submodule_search_locations)
            if any(
                not location.startswith(stdlib_root + "/") for location in locations
            ):
                raise BuildError("python_namespace_module_outside_stdlib")
            origin_kind = "namespace"
            origin = "namespace:" + ":".join(locations)
        else:
            if (
                not isinstance(origin, str)
                or not origin.startswith("/")
                or origin != os.path.normpath(origin)
                or origin.endswith(".pyc")
                or "/__pycache__/" in origin
                or origin.startswith(f"{stdlib_root}/site-packages/")
            ):
                raise BuildError("python_module_origin_not_source_only")
            information = os.stat(origin, follow_symlinks=False)
            if not stat.S_ISREG(information.st_mode) or information.st_nlink != 1:
                raise BuildError("python_module_origin_file_identity_invalid")
            if origin.startswith(extension_root + "/") and origin.endswith(".so"):
                if loader_name is None or not loader_name.endswith(
                    ".ExtensionFileLoader"
                ):
                    raise BuildError("python_extension_loader_identity_invalid")
                if cached is not None:
                    raise BuildError("python_extension_module_cached")
                origin_kind = "stdlib_extension"
            elif origin.startswith(stdlib_root + "/") and origin.endswith(".py"):
                if loader_name is None or not loader_name.endswith(".SourceFileLoader"):
                    raise BuildError("python_source_loader_identity_invalid")
                if not isinstance(cached, str) or not cached.startswith(
                    os.fspath(config.pycache_prefix) + "/"
                ):
                    raise BuildError("python_source_cached_path_not_quarantined")
                origin_kind = "stdlib_source"
            else:
                raise BuildError("python_module_origin_outside_admitted_roots")
        records.append(
            {
                "cached": cached,
                "loader": loader_name,
                "name": name,
                "origin": origin,
                "origin_kind": origin_kind,
            }
        )
    return records


def python_runtime_identity(
    config: BuildConfig,
    source_commit: str,
    module_origins: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    run_id = config.action_root.name
    if (
        RUN_ID_RE.fullmatch(run_id) is None
        or COMMIT_RE.fullmatch(source_commit) is None
    ):
        raise BuildError("python_runtime_action_identity_invalid")
    pycache_prefix = os.fspath(canonical_absolute_path(config.pycache_prefix))
    driver_path = os.fspath(
        config.source_root / "scripts/termux/build_cur0s_native_preflight.py"
    )
    records = [dict(record) for record in module_origins]
    extension_paths = sorted(
        record["origin"]
        for record in records
        if record.get("origin_kind") == "stdlib_extension"
    )
    file_backed_mapping_paths = sorted(
        [value["path"] for value in PYTHON_RUNTIME_ARTIFACTS.values()] + extension_paths
    )
    body = {
        **PYTHON_RUNTIME_BASE_IDENTITY,
        "driver_path": driver_path,
        "loaded_module_origin_count": len(records),
        "loaded_module_origins": records,
        "loaded_module_origins_sha256": canonical_sha256(records),
        "loaded_stdlib_extension_module_paths": extension_paths,
        "file_backed_executable_mapping_paths": file_backed_mapping_paths,
        "orig_argv": [
            f"{PHONE_PREFIX}/bin/python",
            "-IBS",
            "-X",
            f"pycache_prefix={pycache_prefix}",
            driver_path,
            "--run-id",
            run_id,
            "--source-commit",
            source_commit,
        ],
        "pycache_prefix": pycache_prefix,
        "pycache_prefix_absent": True,
        "run_id": run_id,
        "source_commit": source_commit,
        "sys_argv": [
            driver_path,
            "--run-id",
            run_id,
            "--source-commit",
            source_commit,
        ],
        "sys_xoptions": {"pycache_prefix": pycache_prefix},
    }
    return {**body, "python_runtime_root_sha256": canonical_sha256(body)}


def _validate_python_startup_identity(expected: Mapping[str, Any]) -> None:
    flags = {
        "dont_write_bytecode": sys.flags.dont_write_bytecode,
        "ignore_environment": sys.flags.ignore_environment,
        "isolated": sys.flags.isolated,
        "no_site": sys.flags.no_site,
        "no_user_site": sys.flags.no_user_site,
        "optimize": sys.flags.optimize,
        "safe_path": sys.flags.safe_path,
    }
    if (
        dict(os.environ) != BUILD_DRIVER_LAUNCH_ENVIRONMENT
        or flags != expected["startup_flags"]
        or list(sys.path) != expected["startup_sys_path"]
        or sys.executable != expected["sys_executable"]
        or getattr(sys, "_base_executable", None) != expected["base_executable"]
        or sys.prefix != expected["python_prefix"]
        or sys.base_prefix != expected["base_prefix"]
        or sys.exec_prefix != expected["exec_prefix"]
        or sys.base_exec_prefix != expected["base_exec_prefix"]
        or os.path.lexists(expected["startup_sys_path"][0])
        or dict(sys._xoptions) != expected["sys_xoptions"]
        or sys.pycache_prefix != expected["pycache_prefix"]
        or list(sys.orig_argv) != expected["orig_argv"]
        or list(sys.argv) != expected["sys_argv"]
        or os.path.lexists(expected["pycache_prefix"])
    ):
        raise BuildError("python_isolated_startup_identity_mismatch")


def _attest_python_runtime_artifacts() -> dict[str, tuple[int, ...]]:
    volatile: dict[str, tuple[int, ...]] = {}
    for role, expected in sorted(PYTHON_RUNTIME_ARTIFACTS.items()):
        snapshot = read_regular_file(
            Path(expected["path"]),
            byte_limit=MAX_RUNTIME_FILE_BYTES,
            expected_uid=expected["uid"],
            expected_gid=expected["gid"],
            expected_mode=expected["mode"],
        )
        observed = {
            "bytes": len(snapshot.payload),
            "gid": snapshot.gid,
            "mode": snapshot.mode,
            "nlink": snapshot.nlink,
            "path": expected["path"],
            "sha256": prefixed_sha256(snapshot.payload),
            "uid": snapshot.uid,
        }
        if observed != expected:
            raise BuildError("python_runtime_artifact_identity_mismatch")
        volatile[role] = snapshot.identity
    return volatile


def _attest_python_executable_mappings(
    artifact_volatile: Mapping[str, tuple[int, ...]],
    expected_runtime: Mapping[str, Any],
) -> None:
    expected_path_roles = {
        identity["path"]: role for role, identity in PYTHON_RUNTIME_ARTIFACTS.items()
    }
    stdlib_paths = set(expected_runtime["loaded_stdlib_extension_module_paths"])
    observed_paths: list[str] = []
    for record in _parse_proc_self_maps(_read_proc_self_maps()):
        if "x" not in record["permissions"]:
            continue
        path = record["path"]
        observed_paths.append(path)
        if path == "[vdso]":
            continue
        if not path.startswith("/") or path.endswith(" (deleted)"):
            raise BuildError("python_runtime_unapproved_executable_mapping")
        role = expected_path_roles.get(path)
        if role is not None:
            identity = artifact_volatile[role]
            if (
                os.makedev(record["device_major"], record["device_minor"])
                != identity[0]
                or record["inode"] != identity[1]
            ):
                raise BuildError("python_runtime_mapping_inode_mismatch")
            continue
        if path not in stdlib_paths:
            raise BuildError(f"python_runtime_unapproved_executable_mapping:{path}")
        information = os.stat(path, follow_symlinks=False)
        if (
            not stat.S_ISREG(information.st_mode)
            or information.st_nlink != 1
            or information.st_dev
            != os.makedev(record["device_major"], record["device_minor"])
            or information.st_ino != record["inode"]
        ):
            raise BuildError("python_stdlib_mapping_inode_mismatch")
    expected_paths = sorted(
        [*expected_runtime["file_backed_executable_mapping_paths"], "[vdso]"]
    )
    if sorted(observed_paths) != expected_paths:
        raise BuildError("python_runtime_executable_mapping_set_mismatch")


def _observe_current_python_runtime(
    config: BuildConfig,
    source_commit: str,
) -> tuple[
    dict[str, tuple[int, ...]],
    tuple[int, ...],
    dict[str, Any],
]:
    module_origins = _loaded_module_origin_records(config)
    expected_runtime = python_runtime_identity(config, source_commit, module_origins)
    _validate_python_startup_identity(expected_runtime)
    artifact_volatile = _attest_python_runtime_artifacts()
    stdlib = snapshot_python_stdlib_tree()
    try:
        proc_exe_target = os.readlink("/proc/self/exe")
    except OSError as error:
        raise BuildError("proc_self_exe_attestation_failed") from error
    if proc_exe_target != expected_runtime["proc_self_exe"]:
        raise BuildError("proc_self_exe_identity_mismatch")
    _attest_python_executable_mappings(artifact_volatile, expected_runtime)
    return artifact_volatile, stdlib.volatile_identity, expected_runtime


def attest_current_python_runtime(
    config: BuildConfig,
    source_commit: str,
) -> RuntimeGuard:
    initial_artifacts, initial_stdlib, initial_runtime = (
        _observe_current_python_runtime(config, source_commit)
    )

    def revalidate() -> None:
        final_artifacts, final_stdlib, final_runtime = _observe_current_python_runtime(
            config, source_commit
        )
        if (
            final_artifacts != initial_artifacts
            or final_stdlib != initial_stdlib
            or final_runtime != initial_runtime
        ):
            raise BuildError("python_runtime_changed")

    return RuntimeGuard(initial_runtime, revalidate, lambda: None)


def attest_held_build_input(role: str, path: Path) -> HeldFileInput:
    if role not in LINK_INPUT_ROLES:
        raise BuildError("link_input_role_not_admitted")
    fd = open_absolute_nofollow(path)
    try:
        initial = os.fstat(fd)
        if (
            not stat.S_ISREG(initial.st_mode)
            or initial.st_nlink != 1
            or initial.st_size <= 0
            or initial.st_size > MAX_BINARY_BYTES
        ):
            raise BuildError("link_input_identity_invalid")
        digest, byte_count = hash_open_descriptor(fd)
        final = os.fstat(fd)
        entry = os.stat(path, follow_symlinks=False)
        if not (stat_identity(initial) == stat_identity(final) == stat_identity(entry)):
            raise BuildError("link_input_changed_during_attestation")
        identity = {
            "bytes": byte_count,
            "entry_type": "regular_file",
            "gid": final.st_gid,
            "mode": mode_text(final.st_mode),
            "nlink": final.st_nlink,
            "path": os.fspath(path),
            "sha256": digest,
            "uid": final.st_uid,
        }
        return HeldFileInput(role, path, identity, fd, stat_identity(final))
    except Exception:
        os.close(fd)
        raise


def revalidate_held_build_input(value: HeldFileInput) -> None:
    information = os.fstat(value.resolved_fd)
    digest, byte_count = hash_open_descriptor(value.resolved_fd)
    entry = os.stat(value.path, follow_symlinks=False)
    if (
        stat_identity(information) != value.volatile_identity
        or stat_identity(entry) != value.volatile_identity
        or digest != value.identity["sha256"]
        or byte_count != value.identity["bytes"]
    ):
        raise BuildError("held_link_input_changed")


def attest_runtime_file_input(role: str) -> RuntimeFileInput:
    expected = TOOL_RUNTIME_INPUTS.get(role)
    if expected is None:
        raise BuildError("runtime_input_role_not_admitted")
    literal_path = Path(expected["literal_path"])
    resolved_path = Path(expected["resolved_path"])
    if expected["literal_entry_type"] == "symbolic_link":
        literal_information, target = _symlink_snapshot(literal_path)
        observed_resolved = _resolved_symlink_path(literal_path, target)
        if observed_resolved != resolved_path:
            raise BuildError("runtime_input_symlink_resolution_mismatch")
    elif expected["literal_entry_type"] == "regular_file":
        literal_information = os.stat(literal_path, follow_symlinks=False)
        target = None
        if literal_path != resolved_path:
            raise BuildError("runtime_regular_literal_resolution_mismatch")
    else:
        raise BuildError("runtime_input_literal_type_invalid")
    resolved_fd = open_absolute_nofollow(resolved_path)
    try:
        initial = os.fstat(resolved_fd)
        if (
            not stat.S_ISREG(initial.st_mode)
            or initial.st_nlink != 1
            or initial.st_size <= 0
            or initial.st_size > MAX_RUNTIME_FILE_BYTES
        ):
            raise BuildError("runtime_input_resolved_identity_invalid")
        digest, byte_count = hash_open_descriptor(
            resolved_fd,
            byte_limit=MAX_RUNTIME_FILE_BYTES,
        )
        final = os.fstat(resolved_fd)
        entry = os.stat(resolved_path, follow_symlinks=False)
        if not (stat_identity(initial) == stat_identity(final) == stat_identity(entry)):
            raise BuildError("runtime_input_changed_during_attestation")
        observed = _runtime_file_identity(
            os.fspath(literal_path),
            os.fspath(resolved_path),
            sha256=digest,
            size=byte_count,
            mode=mode_text(final.st_mode),
            uid=final.st_uid,
            gid=final.st_gid,
            symlink_target=target,
            literal_mode=mode_text(literal_information.st_mode),
            literal_uid=literal_information.st_uid,
            literal_gid=literal_information.st_gid,
        )
        if observed != expected:
            raise BuildError("runtime_input_frozen_identity_mismatch")
        return RuntimeFileInput(
            role,
            observed,
            stat_identity(literal_information),
            resolved_fd,
            stat_identity(final),
        )
    except Exception:
        os.close(resolved_fd)
        raise


def revalidate_runtime_file_input(value: RuntimeFileInput) -> None:
    expected = value.identity
    literal_path = Path(expected["literal_path"])
    resolved_path = Path(expected["resolved_path"])
    if expected["literal_entry_type"] == "symbolic_link":
        literal_information, target = _symlink_snapshot(literal_path)
        if (
            target != expected["literal_symlink_target"]
            or _resolved_symlink_path(literal_path, target) != resolved_path
        ):
            raise BuildError("runtime_input_literal_changed")
    else:
        literal_information = os.stat(literal_path, follow_symlinks=False)
    information = os.fstat(value.resolved_fd)
    entry = os.stat(resolved_path, follow_symlinks=False)
    digest, byte_count = hash_open_descriptor(
        value.resolved_fd,
        byte_limit=MAX_RUNTIME_FILE_BYTES,
    )
    if (
        stat_identity(literal_information) != value.literal_volatile_identity
        or stat_identity(information) != value.resolved_volatile_identity
        or stat_identity(entry) != value.resolved_volatile_identity
        or digest != expected["sha256"]
        or byte_count != expected["bytes"]
    ):
        raise BuildError("runtime_input_changed")


def _runtime_graph_from_inputs(
    compiler: AttestedTool,
    linker: AttestedTool,
    runtime_inputs: Mapping[str, RuntimeFileInput],
) -> dict[str, dict[str, Any]]:
    if set(runtime_inputs) != set(TOOL_RUNTIME_INPUT_ROLES):
        raise BuildError("runtime_input_role_set_mismatch")
    graph = {
        "compiler": parse_runtime_elf_descriptor(compiler.resolved_fd),
        "linker": parse_runtime_elf_descriptor(linker.resolved_fd),
    }
    graph.update(
        {
            role: parse_runtime_elf_descriptor(runtime_inputs[role].resolved_fd)
            for role in TOOL_RUNTIME_INPUT_ROLES
        }
    )
    return graph


def _validate_recursive_runtime_graph(
    graph: Mapping[str, Mapping[str, Any]],
) -> None:
    expected_roles = {"compiler", "linker", *TOOL_RUNTIME_INPUT_ROLES}
    if set(graph) != expected_roles:
        raise BuildError("runtime_dependency_graph_role_set_mismatch")
    reachable = {"compiler", "linker"}
    frontier = ["compiler", "linker"]
    while frontier:
        role = frontier.pop()
        node = graph[role]
        interpreter = node.get("interpreter")
        if interpreter is not None:
            if interpreter != "/system/bin/linker64":
                raise BuildError("runtime_dependency_interpreter_mismatch")
            dependency_role = "android_linker64"
            if dependency_role not in reachable:
                reachable.add(dependency_role)
                frontier.append(dependency_role)
        needed = node.get("needed")
        if not isinstance(needed, list):
            raise BuildError("runtime_dependency_needed_invalid")
        for soname in needed:
            dependency_role = TOOL_RUNTIME_SONAME_ROLES.get(soname)
            if dependency_role is None:
                raise BuildError("runtime_dependency_soname_unresolved")
            if dependency_role not in reachable:
                reachable.add(dependency_role)
                frontier.append(dependency_role)
    if reachable != expected_roles:
        raise BuildError("runtime_dependency_graph_not_recursive_complete")
    for soname, role in TOOL_RUNTIME_SONAME_ROLES.items():
        if graph[role].get("soname") != soname:
            raise BuildError("runtime_dependency_soname_role_mismatch")


def parse_actual_loader_list(payload: bytes) -> list[dict[str, str]]:
    """Remove only the terminal ASLR address from strict linker64 output."""

    if not payload or not payload.endswith(b"\n") or b"\r" in payload:
        raise BuildError("actual_loader_list_framing_invalid")
    lines = payload.split(b"\n")
    if lines[-1] != b"" or any(not line for line in lines[:-1]):
        raise BuildError("actual_loader_list_framing_invalid")
    records: list[dict[str, str]] = []
    for line in lines[:-1]:
        match = LOADER_LIST_LINE_RE.fullmatch(line)
        if match is None or int(match.group("address"), 16) == 0:
            raise BuildError("actual_loader_list_record_invalid")
        try:
            soname = match.group("soname").decode("ascii")
            resolved_path = match.group("path").decode("ascii")
        except UnicodeDecodeError as error:
            raise BuildError("actual_loader_list_record_invalid") from error
        records.append(
            {
                "normalized_line": f"\t{soname} => {resolved_path}",
                "resolved_path": resolved_path,
                "soname": soname,
            }
        )
    if not records:
        raise BuildError("actual_loader_list_empty")
    return records


def require_actual_loader_process_result(
    result: subprocess.CompletedProcess[bytes],
) -> list[dict[str, str]]:
    if (
        result.returncode != 0
        or not isinstance(result.stdout, bytes)
        or result.stderr != b""
    ):
        raise BuildError("actual_loader_list_execution_failed")
    return parse_actual_loader_list(result.stdout)


def _held_resolution_identity(
    runtime_role: str,
    identity: Mapping[str, Any],
    descriptor: int,
) -> dict[str, Any]:
    information = os.fstat(descriptor)
    if (
        not stat.S_ISREG(information.st_mode)
        or information.st_nlink != identity["resolved_nlink"]
        or information.st_size != identity["bytes"]
    ):
        raise BuildError("actual_loader_held_identity_invalid")
    return {
        "bytes": identity["bytes"],
        "device_major": os.major(information.st_dev),
        "device_minor": os.minor(information.st_dev),
        "inode": information.st_ino,
        "literal_path": identity["literal_path"],
        "resolved_path": identity["resolved_path"],
        "runtime_role": runtime_role,
        "sha256": identity["sha256"],
    }


def _bind_actual_loader_entries(
    tool_role: str,
    parsed: Sequence[Mapping[str, str]],
    runtime_inputs: Mapping[str, RuntimeFileInput],
) -> list[dict[str, Any]]:
    expected = ACTUAL_LOADER_EXPECTED_RESOLUTION.get(tool_role)
    if expected is None or len(parsed) != len(expected):
        raise BuildError("actual_loader_resolution_set_mismatch")
    entries: list[dict[str, Any]] = []
    observed_pairs: list[tuple[str, str]] = []
    for record, (expected_soname, expected_role) in zip(parsed, expected, strict=True):
        soname = record.get("soname")
        resolved_path = record.get("resolved_path")
        if soname != expected_soname:
            raise BuildError("actual_loader_resolution_order_or_soname_mismatch")
        if expected_role == "kernel_vdso":
            if resolved_path != "[vdso]":
                raise BuildError("actual_loader_vdso_path_mismatch")
            entry: dict[str, Any] = {
                **record,
                "bytes": None,
                "device_major": None,
                "device_minor": None,
                "inode": None,
                "runtime_role": expected_role,
                "sha256": None,
            }
        else:
            runtime_input = runtime_inputs.get(expected_role)
            if runtime_input is None:
                raise BuildError("actual_loader_runtime_role_missing")
            identity = runtime_input.identity
            if resolved_path != identity["resolved_path"]:
                raise BuildError("actual_loader_resolved_path_mismatch")
            held = _held_resolution_identity(
                expected_role,
                identity,
                runtime_input.resolved_fd,
            )
            entry = {
                **record,
                "bytes": held["bytes"],
                "device_major": held["device_major"],
                "device_minor": held["device_minor"],
                "inode": held["inode"],
                "runtime_role": expected_role,
                "sha256": held["sha256"],
            }
        pair = (soname, expected_role)
        if pair in observed_pairs:
            raise BuildError("actual_loader_resolution_duplicate")
        observed_pairs.append(pair)
        entries.append(entry)
    if tuple(observed_pairs) != expected:
        raise BuildError("actual_loader_resolution_set_mismatch")
    return entries


def _observe_actual_loader_resolution(
    compiler: AttestedTool,
    linker: AttestedTool,
    runtime_inputs: Mapping[str, RuntimeFileInput],
    source_root: Path,
    process_runner: ProcessRunner,
) -> dict[str, Any]:
    loader = runtime_inputs.get("android_linker64")
    if loader is None:
        raise BuildError("actual_loader_held_input_missing")
    loader_identity = _held_resolution_identity(
        "android_linker64",
        loader.identity,
        loader.resolved_fd,
    )
    tools = {"compiler": compiler, "linker": linker}
    resolutions: dict[str, Any] = {}
    for tool_role, tool in tools.items():
        target = f"/proc/self/fd/{tool.resolved_fd}"
        arguments = ("/system/bin/linker64", "--list", target)
        result = process_runner(
            arguments,
            source_root,
            BUILD_ENVIRONMENT,
            loader.resolved_fd,
            (tool.resolved_fd,),
        )
        parsed = require_actual_loader_process_result(result)
        entries = _bind_actual_loader_entries(tool_role, parsed, runtime_inputs)
        target_identity = _held_resolution_identity(
            tool_role,
            tool.identity,
            tool.resolved_fd,
        )
        body = {
            "argv": list(arguments),
            "entries": entries,
            "entry_count": len(entries),
            "normalized_stdout_sha256": canonical_sha256(
                [entry["normalized_line"] for entry in entries]
            ),
            "returncode": result.returncode,
            "stderr_bytes": 0,
            "stderr_sha256": prefixed_sha256(b""),
            "target": target_identity,
        }
        resolutions[tool_role] = {
            **body,
            "resolution_root_sha256": canonical_sha256(body),
        }
    body = {
        "address_normalization": (
            "remove_only_exact_terminal_lowercase_hex_ASLR_address_suffix"
        ),
        "environment": dict(BUILD_ENVIRONMENT),
        "loader": loader_identity,
        "scope": (
            "static_PT_INTERP_and_DT_NEEDED_resolution_only_no_arbitrary_dlopen_claim"
        ),
        "schema_version": ACTUAL_LOADER_RESOLUTION_SCHEMA,
        "tools": resolutions,
    }
    return {**body, "actual_loader_resolution_root_sha256": canonical_sha256(body)}


def attest_tool_runtime_closure(
    compiler: AttestedTool,
    linker: AttestedTool,
    source_root: Path,
    process_runner: ProcessRunner = run_process,
) -> RuntimeGuard:
    runtime_inputs: dict[str, RuntimeFileInput] = {}
    try:
        for role in TOOL_RUNTIME_INPUT_ROLES:
            runtime_inputs[role] = attest_runtime_file_input(role)
        graph = _runtime_graph_from_inputs(compiler, linker, runtime_inputs)
        _validate_recursive_runtime_graph(graph)
        observed = {
            "dependency_graph": graph,
            "interpreter_role": "android_linker64",
            "recursive_resolution_complete": True,
            "runtime_inputs": {
                role: runtime_inputs[role].identity for role in TOOL_RUNTIME_INPUT_ROLES
            },
            "schema_version": RUNTIME_DEPENDENCY_CLOSURE_SCHEMA,
            "soname_roles": dict(TOOL_RUNTIME_SONAME_ROLES),
            "tool_roots": {
                "compiler": compiler.identity["resolved_path"],
                "linker": linker.identity["resolved_path"],
            },
        }
        if observed != TOOL_RUNTIME_IDENTITY:
            raise BuildError("runtime_dependency_frozen_closure_mismatch")
        actual_resolution = _observe_actual_loader_resolution(
            compiler,
            linker,
            runtime_inputs,
            source_root,
            process_runner,
        )
        closure_identity = {
            **observed,
            "actual_loader_resolution": actual_resolution,
        }

        def revalidate() -> None:
            revalidate_build_tool_file(compiler)
            revalidate_build_tool_file(linker)
            for runtime_role in TOOL_RUNTIME_INPUT_ROLES:
                revalidate_runtime_file_input(runtime_inputs[runtime_role])
            final_graph = _runtime_graph_from_inputs(
                compiler,
                linker,
                runtime_inputs,
            )
            _validate_recursive_runtime_graph(final_graph)
            if final_graph != graph:
                raise BuildError("runtime_dependency_graph_changed")
            final_resolution = _observe_actual_loader_resolution(
                compiler,
                linker,
                runtime_inputs,
                source_root,
                process_runner,
            )
            if final_resolution != actual_resolution:
                raise BuildError("actual_loader_resolution_changed")

        def close() -> None:
            for runtime_input in runtime_inputs.values():
                runtime_input.close()

        return RuntimeGuard(closure_identity, revalidate, close)
    except Exception:
        for runtime_input in runtime_inputs.values():
            runtime_input.close()
        raise


def attest_held_source_inputs(
    config: BuildConfig,
    source_bindings: Mapping[str, Mapping[str, Any]],
) -> dict[str, HeldFileInput]:
    role_paths = {
        **{
            role: config.source_root / relative
            for role, relative in COMPILED_SOURCE_FILES.items()
        },
        "cur0s_header": config.source_root / NATIVE_HEADER_FILE,
    }
    held: dict[str, HeldFileInput] = {}
    try:
        for role in sorted(role_paths):
            path = role_paths[role]
            relative = (
                NATIVE_HEADER_FILE
                if role == "cur0s_header"
                else COMPILED_SOURCE_FILES[role]
            )
            binding = source_bindings.get(relative)
            if binding is None:
                raise BuildError("held_source_binding_missing")
            fd = open_absolute_nofollow(path)
            try:
                initial = os.fstat(fd)
                digest, byte_count = hash_open_descriptor(fd)
                final = os.fstat(fd)
                entry = os.stat(path, follow_symlinks=False)
                if (
                    not stat.S_ISREG(initial.st_mode)
                    or initial.st_nlink != 1
                    or not (
                        stat_identity(initial)
                        == stat_identity(final)
                        == stat_identity(entry)
                    )
                    or binding.get("bytes") != byte_count
                    or binding.get("sha256") != digest
                ):
                    raise BuildError("held_source_identity_or_binding_mismatch")
                identity = {
                    "bytes": byte_count,
                    "entry_type": "regular_file",
                    "path": os.fspath(path),
                    "sha256": digest,
                }
                held[role] = HeldFileInput(
                    role,
                    path,
                    identity,
                    fd,
                    stat_identity(final),
                )
            except Exception:
                os.close(fd)
                raise
    except Exception:
        for value in held.values():
            value.close()
        raise
    return held


def revalidate_held_source_inputs(
    source_inputs: Mapping[str, HeldFileInput],
) -> None:
    expected_roles = {"cur0s_header", *COMPILED_SOURCE_FILES}
    if set(source_inputs) != expected_roles:
        raise BuildError("held_source_role_set_mismatch")
    for role in sorted(source_inputs):
        value = source_inputs[role]
        information = os.fstat(value.resolved_fd)
        digest, byte_count = hash_open_descriptor(value.resolved_fd)
        entry = os.stat(value.path, follow_symlinks=False)
        if (
            stat_identity(information) != value.volatile_identity
            or stat_identity(entry) != value.volatile_identity
            or digest != value.identity["sha256"]
            or byte_count != value.identity["bytes"]
        ):
            raise BuildError("held_source_changed")


def create_held_header_shim(
    config: BuildConfig,
    header: HeldFileInput,
) -> None:
    create_private_directory(
        config.header_shim_directory,
        config.expected_uid,
        config.expected_gid,
    )
    directory_fd = open_absolute_nofollow(
        config.header_shim_directory,
        directory=True,
    )
    try:
        target = f"/proc/self/fd/{header.resolved_fd}"
        try:
            os.symlink(target, "cur0s_sha256.h", dir_fd=directory_fd)
        except FileExistsError as error:
            raise BuildError("held_header_shim_preexists") from error
        information = os.stat(
            "cur0s_sha256.h",
            dir_fd=directory_fd,
            follow_symlinks=False,
        )
        observed_target = os.readlink("cur0s_sha256.h", dir_fd=directory_fd)
        if (
            not stat.S_ISLNK(information.st_mode)
            or information.st_nlink != 1
            or information.st_uid != config.expected_uid
            or information.st_gid != config.expected_gid
            or observed_target != target
        ):
            raise BuildError("held_header_shim_identity_invalid")
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def attest_toolchain_input_closure(
    config: BuildConfig,
) -> tuple[dict[str, TreeSnapshot], dict[str, HeldFileInput]]:
    if set(config.link_input_paths) != set(LINK_INPUT_ROLES):
        raise BuildError("link_input_role_set_mismatch")
    if config.resource_include_root != config.resource_directory / "include":
        raise BuildError("resource_include_root_not_canonical")
    include_trees = {
        "clang_resource_tree": snapshot_toolchain_tree(
            config.resource_directory,
            expected_uid=config.expected_uid,
            expected_gid=config.expected_gid,
        ),
        "termux_system_headers": snapshot_toolchain_tree(
            config.system_include_root,
            expected_uid=config.expected_uid,
            expected_gid=config.expected_gid,
        ),
        "termux_arch_headers": snapshot_toolchain_tree(
            config.arch_include_root,
            expected_uid=config.expected_uid,
            expected_gid=config.expected_gid,
        ),
    }
    link_inputs: dict[str, HeldFileInput] = {}
    try:
        for role in LINK_INPUT_ROLES:
            link_inputs[role] = attest_held_build_input(
                role,
                canonical_absolute_path(config.link_input_paths[role]),
            )
    except Exception:
        for value in link_inputs.values():
            value.close()
        raise
    return include_trees, link_inputs


def compile_arguments(
    config: BuildConfig,
    source_descriptor: int,
    object_path: Path,
) -> tuple[str, ...]:
    if source_descriptor < 0:
        raise BuildError("compile_source_descriptor_invalid")
    replacements = {
        "$ARCH_INCLUDE_ROOT": os.fspath(
            canonical_absolute_path(config.arch_include_root)
        ),
        "$HEADER_SHIM_DIRECTORY": os.fspath(
            canonical_absolute_path(config.header_shim_directory)
        ),
        "$HELD_SOURCE": f"/proc/self/fd/{source_descriptor}",
        "$OBJECT": os.fspath(canonical_absolute_path(object_path)),
        "$RESOURCE_DIRECTORY": os.fspath(
            canonical_absolute_path(config.resource_directory)
        ),
        "$RESOURCE_INCLUDE_ROOT": os.fspath(
            canonical_absolute_path(config.resource_include_root)
        ),
        "$SYSTEM_INCLUDE_ROOT": os.fspath(
            canonical_absolute_path(config.system_include_root)
        ),
    }
    result: list[str] = []
    for argument in COMPILE_ARGV_TEMPLATE:
        expanded = argument
        for marker in sorted(replacements, key=len, reverse=True):
            value = replacements[marker]
            expanded = expanded.replace(marker, value)
        if "$" in expanded:
            raise BuildError("compile_argument_placeholder_unresolved")
        result.append(expanded)
    return tuple(result)


def link_arguments(
    output: Path,
    link_inputs: Mapping[str, HeldFileInput],
    object_descriptors: Mapping[str, int],
) -> tuple[str, ...]:
    if set(link_inputs) != set(LINK_INPUT_ROLES):
        raise BuildError("link_argument_input_role_set_mismatch")
    if set(object_descriptors) != {"cur0s_native_preflight", "cur0s_sha256"}:
        raise BuildError("link_argument_object_role_set_mismatch")
    result: list[str] = []
    for argument in LINK_ARGV_TEMPLATE:
        if argument == "$OUTPUT":
            result.append(os.fspath(canonical_absolute_path(output)))
            continue
        if argument.startswith("$HELD_FD:"):
            role = argument.removeprefix("$HELD_FD:")
            if role not in link_inputs or link_inputs[role].resolved_fd < 0:
                raise BuildError("link_argument_held_input_missing")
            result.append(f"/proc/self/fd/{link_inputs[role].resolved_fd}")
            continue
        if argument.startswith("$HELD_OBJECT:"):
            role = argument.removeprefix("$HELD_OBJECT:")
            if role not in object_descriptors or object_descriptors[role] < 0:
                raise BuildError("link_argument_held_object_missing")
            result.append(f"/proc/self/fd/{object_descriptors[role]}")
            continue
        if "$" in argument:
            raise BuildError("link_argument_placeholder_unresolved")
        result.append(argument)
    return tuple(result)


def open_verified_snapshot(path: Path, snapshot: FileSnapshot) -> int:
    fd = open_absolute_nofollow(path)
    try:
        information = os.fstat(fd)
        digest, byte_count = hash_open_descriptor(fd)
        if (
            stat_identity(information) != snapshot.identity
            or byte_count != len(snapshot.payload)
            or digest != prefixed_sha256(snapshot.payload)
        ):
            raise BuildError("generated_object_snapshot_changed")
        return fd
    except Exception:
        os.close(fd)
        raise


def run_one_build(
    config: BuildConfig,
    output: Path,
    directory: Path,
    compiler_fd: int,
    linker_fd: int,
    link_inputs: Mapping[str, HeldFileInput],
    source_inputs: Mapping[str, HeldFileInput],
    process_runner: ProcessRunner = run_process,
) -> BuildResult:
    if output.exists() or output.is_symlink():
        raise BuildError("build_output_preexists")
    if set(source_inputs) != {"cur0s_header", *COMPILED_SOURCE_FILES}:
        raise BuildError("held_source_role_set_mismatch")
    object_paths = config.object_paths(directory)
    object_snapshots: dict[str, FileSnapshot] = {}
    for role in sorted(COMPILED_SOURCE_FILES):
        object_path = object_paths[role]
        if object_path.exists() or object_path.is_symlink():
            raise BuildError("build_object_preexists")
        completed = process_runner(
            compile_arguments(
                config,
                source_inputs[role].resolved_fd,
                object_path,
            ),
            directory,
            BUILD_ENVIRONMENT,
            compiler_fd,
            (
                source_inputs[role].resolved_fd,
                source_inputs["cur0s_header"].resolved_fd,
            ),
        )
        if completed.returncode != 0 or completed.stdout or completed.stderr:
            raise BuildError("native_compile_failed_or_noisy")
        object_snapshots[role] = read_regular_file(
            object_path,
            byte_limit=MAX_BINARY_BYTES,
            expected_uid=config.expected_uid,
            expected_gid=config.expected_gid,
            expected_mode="0600",
        )

    object_descriptors: dict[str, int] = {}
    try:
        for role in sorted(object_snapshots):
            object_descriptors[role] = open_verified_snapshot(
                object_paths[role], object_snapshots[role]
            )
        inherited_fds = tuple(
            value.resolved_fd for value in link_inputs.values()
        ) + tuple(object_descriptors.values())
        linked = process_runner(
            link_arguments(output, link_inputs, object_descriptors),
            directory,
            BUILD_ENVIRONMENT,
            linker_fd,
            inherited_fds,
        )
        if linked.returncode != 0 or linked.stdout or linked.stderr:
            raise BuildError("native_link_failed_or_noisy")
    finally:
        for descriptor in object_descriptors.values():
            os.close(descriptor)
    binary = read_regular_file(
        output,
        byte_limit=MAX_BINARY_BYTES,
        expected_uid=config.expected_uid,
        expected_gid=config.expected_gid,
        expected_mode="0700",
    )
    return BuildResult(binary, object_snapshots)


def _require_range(payload: bytes, offset: int, size: int, code: str) -> bytes:
    if offset < 0 or size < 0 or offset > len(payload) or size > len(payload) - offset:
        raise BuildError(code)
    return payload[offset : offset + size]


def _fixed_note_text(payload: bytes, code: str) -> str:
    terminator = payload.find(b"\0")
    if terminator < 0 or any(payload[terminator + 1 :]):
        raise BuildError(code)
    try:
        value = payload[:terminator].decode("ascii")
    except UnicodeDecodeError as error:
        raise BuildError(code) from error
    if not value:
        raise BuildError(code)
    return value


def _parse_notes(
    payload: bytes,
    offset: int,
    size: int,
    android_identities: list[tuple[int, str, str]],
) -> None:
    cursor = offset
    end = offset + size
    _require_range(payload, offset, size, "ELF_note_bounds_invalid")
    while cursor < end:
        header = _require_range(payload, cursor, 12, "ELF_note_header_truncated")
        name_size, description_size, note_type = struct.unpack("<III", header)
        cursor += 12
        name = _require_range(payload, cursor, name_size, "ELF_note_name_truncated")
        cursor += (name_size + 3) & ~3
        description = _require_range(
            payload, cursor, description_size, "ELF_note_description_truncated"
        )
        cursor += (description_size + 3) & ~3
        if cursor > end:
            raise BuildError("ELF_note_alignment_invalid")
        if note_type == 3 and name.rstrip(b"\0") == b"GNU":
            raise BuildError("ELF_build_id_present")
        if note_type == 1 and name == b"Android\0":
            if description_size != 132:
                raise BuildError("ELF_Android_ident_note_size_invalid")
            api_level = struct.unpack("<I", description[:4])[0]
            ndk_version = _fixed_note_text(
                description[4:68],
                "ELF_Android_ident_NDK_version_invalid",
            )
            ndk_build = _fixed_note_text(
                description[68:132],
                "ELF_Android_ident_NDK_build_invalid",
            )
            android_identities.append((api_level, ndk_version, ndk_build))


def _virtual_to_file_offset(
    address: int,
    size: int,
    load_segments: Sequence[tuple[int, int, int]],
) -> int:
    for virtual_address, file_offset, file_size in load_segments:
        if address < virtual_address:
            continue
        relative = address - virtual_address
        if relative <= file_size and size <= file_size - relative:
            return file_offset + relative
    raise BuildError("ELF_virtual_address_unmapped")


def _dynamic_string(
    payload: bytes,
    table_offset: int,
    table_size: int,
    string_offset: int,
) -> bytes:
    if string_offset >= table_size:
        raise BuildError("ELF_dynamic_string_offset_invalid")
    table = _require_range(
        payload,
        table_offset,
        table_size,
        "ELF_dynamic_string_table_invalid",
    )
    end = table.find(b"\0", string_offset)
    if end < 0:
        raise BuildError("ELF_dynamic_string_unterminated")
    return table[string_offset:end]


def parse_aarch64_elf(payload: bytes) -> dict[str, Any]:
    if len(payload) < 64 or payload[:4] != b"\x7fELF":
        raise BuildError("ELF_header_invalid")
    if payload[4:7] != b"\x02\x01\x01":
        raise BuildError("ELF_class_or_encoding_invalid")
    header = struct.unpack("<16sHHIQQQIHHHHHH", payload[:64])
    (
        _ident,
        elf_type,
        machine,
        version,
        entry_point,
        program_offset,
        section_offset,
        _flags,
        header_size,
        program_entry_size,
        program_count,
        section_entry_size,
        section_count,
        _section_name_index,
    ) = header
    if (
        elf_type != 3
        or machine != 183
        or version != 1
        or header_size != 64
        or program_entry_size != 56
        or program_count == 0
    ):
        raise BuildError("ELF_AArch64_PIE_header_mismatch")

    program_headers: list[tuple[int, int, int, int, int, int, int, int]] = []
    for index in range(program_count):
        raw = _require_range(
            payload,
            program_offset + index * program_entry_size,
            program_entry_size,
            "ELF_program_header_bounds_invalid",
        )
        program_headers.append(struct.unpack("<IIQQQQQQ", raw))

    interpreter: str | None = None
    dynamic_segment: tuple[int, int, int, int] | None = None
    load_segments: list[tuple[int, int, int]] = []
    executable_ranges: list[tuple[int, int]] = []
    executable_load_segments: list[dict[str, int]] = []
    relro_range: tuple[int, int] | None = None
    android_identities: list[tuple[int, str, str]] = []
    relro_segments = 0
    stack_segments = 0
    non_executable_stack = False
    for (
        program_type,
        flags,
        offset,
        virtual,
        _physical,
        file_size,
        memory_size,
        _align,
    ) in program_headers:
        if flags & ~0x7:
            raise BuildError("ELF_program_header_flags_invalid")
        _require_range(payload, offset, file_size, "ELF_segment_bounds_invalid")
        if file_size > memory_size:
            raise BuildError("ELF_segment_file_size_exceeds_memory_size")
        if program_type == 1:
            if flags & 0x1 and flags & 0x2:
                raise BuildError("ELF_WX_load_segment_present")
            load_segments.append((virtual, offset, file_size))
            if flags & 0x1:
                if (
                    memory_size == 0
                    or _align < PROC_MAP_PAGE_SIZE
                    or _align & (_align - 1)
                    or offset % _align != virtual % _align
                ):
                    raise BuildError("ELF_executable_PT_LOAD_alignment_invalid")
                executable_ranges.append((virtual, memory_size))
                map_offset = offset - (offset % PROC_MAP_PAGE_SIZE)
                page_delta = virtual % PROC_MAP_PAGE_SIZE
                mapped_bytes = (
                    page_delta + memory_size + PROC_MAP_PAGE_SIZE - 1
                ) // PROC_MAP_PAGE_SIZE * PROC_MAP_PAGE_SIZE
                executable_load_segments.append(
                    {
                        "alignment": _align,
                        "file_offset": offset,
                        "file_size": file_size,
                        "memory_size": memory_size,
                        "proc_maps_mapped_bytes": mapped_bytes,
                        "proc_maps_offset": map_offset,
                        "proc_maps_page_size": PROC_MAP_PAGE_SIZE,
                        "virtual_address": virtual,
                    }
                )
        elif program_type == 2:
            if dynamic_segment is not None:
                raise BuildError("ELF_multiple_dynamic_segments")
            dynamic_segment = (offset, file_size, virtual, memory_size)
        elif program_type == 3:
            if interpreter is not None:
                raise BuildError("ELF_multiple_interpreters")
            raw_interpreter = payload[offset : offset + file_size]
            if not raw_interpreter.endswith(b"\0") or b"\0" in raw_interpreter[:-1]:
                raise BuildError("ELF_interpreter_invalid")
            try:
                interpreter = raw_interpreter[:-1].decode("ascii")
            except UnicodeDecodeError as error:
                raise BuildError("ELF_interpreter_not_ascii") from error
        elif program_type == 4:
            _parse_notes(payload, offset, file_size, android_identities)
        elif program_type == 0x6474E551:
            stack_segments += 1
            non_executable_stack = flags & 1 == 0
        elif program_type == 0x6474E552:
            if file_size == 0 or memory_size == 0:
                raise BuildError("ELF_RELRO_segment_empty")
            if relro_range is not None:
                raise BuildError("ELF_multiple_RELRO_segments")
            relro_range = (virtual, memory_size)
            relro_segments += 1

    if dynamic_segment is None:
        raise BuildError("ELF_dynamic_segment_missing")
    if len(executable_load_segments) != 1:
        raise BuildError("ELF_executable_PT_LOAD_cardinality_invalid")
    if not any(
        start <= entry_point < start + size for start, size in executable_ranges
    ):
        raise BuildError("ELF_entrypoint_not_in_executable_segment")
    dynamic_offset, dynamic_size, dynamic_virtual, dynamic_memory_size = dynamic_segment
    if relro_range is None:
        raise BuildError("ELF_RELRO_segment_missing")
    relro_virtual, relro_memory_size = relro_range
    if not (
        relro_virtual <= dynamic_virtual
        and dynamic_memory_size <= (relro_virtual + relro_memory_size - dynamic_virtual)
    ):
        raise BuildError("ELF_dynamic_segment_not_covered_by_RELRO")
    if dynamic_size == 0 or dynamic_size % 16 != 0:
        raise BuildError("ELF_dynamic_segment_size_invalid")
    dynamic: list[tuple[int, int]] = []
    terminated = False
    for cursor in range(dynamic_offset, dynamic_offset + dynamic_size, 16):
        tag, value = struct.unpack("<QQ", payload[cursor : cursor + 16])
        if tag == 0:
            terminated = True
            break
        dynamic.append((tag, value))
    if not terminated:
        raise BuildError("ELF_dynamic_segment_unterminated")

    values: dict[int, list[int]] = {}
    for tag, value in dynamic:
        values.setdefault(tag, []).append(value)
    if len(values.get(5, [])) != 1 or len(values.get(10, [])) != 1:
        raise BuildError("ELF_dynamic_string_table_missing")
    if len(values.get(3, [])) != 1 or not (
        relro_virtual <= values[3][0] < relro_virtual + relro_memory_size
    ):
        raise BuildError("ELF_PLTGOT_not_covered_by_RELRO")
    string_size = values[10][0]
    string_table_offset = _virtual_to_file_offset(
        values[5][0],
        string_size,
        load_segments,
    )
    needed_bytes = [
        _dynamic_string(payload, string_table_offset, string_size, offset)
        for offset in values.get(1, [])
    ]
    if needed_bytes != [b"libc.so"]:
        raise BuildError("ELF_needed_mismatch")
    if values.get(15) or values.get(29):
        raise BuildError("ELF_RPATH_or_RUNPATH_present")
    flags = 0
    for value in values.get(30, []):
        flags |= value
    flags_one = 0
    for value in values.get(0x6FFFFFFB, []):
        flags_one |= value
    bind_now = bool(values.get(24) or flags & 0x8 or flags_one & 0x1)
    pie = elf_type == 3 and bool(flags_one & 0x08000000)
    text_relocations = bool(values.get(22) or flags & 0x4)

    if section_count:
        if section_entry_size != 64:
            raise BuildError("ELF_section_header_size_invalid")
        for index in range(section_count):
            raw = _require_range(
                payload,
                section_offset + index * section_entry_size,
                section_entry_size,
                "ELF_section_header_bounds_invalid",
            )
            section = struct.unpack("<IIQQQQIIQQ", raw)
            if section[1] == 7:
                _parse_notes(
                    payload,
                    section[4],
                    section[5],
                    android_identities,
                )

    unique_android_identities = set(android_identities)
    if len(unique_android_identities) != 1:
        raise BuildError("ELF_Android_ident_note_missing_or_inconsistent")
    android_api, android_ndk, android_ndk_build = unique_android_identities.pop()
    if android_api != 30:
        raise BuildError("ELF_Android_API_level_mismatch")

    if (
        interpreter != "/system/bin/linker64"
        or not pie
        or relro_segments != 1
        or not bind_now
        or stack_segments != 1
        or not non_executable_stack
        or text_relocations
    ):
        raise BuildError("ELF_hardening_identity_mismatch")
    return {
        "bind_now": True,
        "build_id": None,
        "class_bits": 64,
        "data_encoding": "little_endian",
        "executable_pt_load": executable_load_segments[0],
        "interpreter": interpreter,
        "machine": "AArch64",
        "android_ident": {
            "api_level": android_api,
            "ndk_build_number": android_ndk_build,
            "ndk_version": android_ndk,
        },
        "needed": ["libc.so"],
        "pie": True,
        "relro": True,
        "rpath": None,
        "runpath": None,
        "sha256": prefixed_sha256(payload),
        "text_relocations": False,
    }


def publish_exclusive(
    path: Path,
    payload: bytes,
    *,
    mode: int,
    uid: int,
    gid: int,
) -> FileSnapshot:
    parent_fd, name = _parent_fd_and_name(path)
    fd = -1
    try:
        fd = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            mode,
            dir_fd=parent_fd,
        )
        offset = 0
        while offset < len(payload):
            written = os.write(fd, payload[offset:])
            if written <= 0:
                raise BuildError("exclusive_publication_write_failed")
            offset += written
        os.fchmod(fd, mode)
        os.fsync(fd)
        information = os.fstat(fd)
        if (
            not stat.S_ISREG(information.st_mode)
            or information.st_nlink != 1
            or information.st_size != len(payload)
            or mode_text(information.st_mode) != f"{mode:04o}"
            or information.st_uid != uid
            or information.st_gid != gid
        ):
            raise BuildError("exclusive_publication_identity_mismatch")
        os.fsync(parent_fd)
    except FileExistsError as error:
        raise BuildError("exclusive_publication_target_exists") from error
    finally:
        if fd >= 0:
            os.close(fd)
        os.close(parent_fd)
    snapshot = read_regular_file(
        path,
        byte_limit=max(len(payload), 1),
        expected_uid=uid,
        expected_gid=gid,
        expected_mode=f"{mode:04o}",
    )
    if snapshot.payload != payload:
        raise BuildError("exclusive_publication_payload_mismatch")
    return snapshot


def revalidate_toolchain_input_closure(
    config: BuildConfig,
    include_trees: Mapping[str, TreeSnapshot],
    link_inputs: Mapping[str, HeldFileInput],
) -> None:
    if set(include_trees) != set(INCLUDE_TREE_ROLES):
        raise BuildError("include_tree_role_set_mismatch")
    observed = {
        "clang_resource_tree": snapshot_toolchain_tree(
            config.resource_directory,
            expected_uid=config.expected_uid,
            expected_gid=config.expected_gid,
        ),
        "termux_system_headers": snapshot_toolchain_tree(
            config.system_include_root,
            expected_uid=config.expected_uid,
            expected_gid=config.expected_gid,
        ),
        "termux_arch_headers": snapshot_toolchain_tree(
            config.arch_include_root,
            expected_uid=config.expected_uid,
            expected_gid=config.expected_gid,
        ),
    }
    if observed != dict(include_trees):
        raise BuildError("toolchain_include_tree_changed")
    if set(link_inputs) != set(LINK_INPUT_ROLES):
        raise BuildError("link_input_role_set_mismatch")
    for role in LINK_INPUT_ROLES:
        revalidate_held_build_input(link_inputs[role])


def toolchain_input_closure_receipt(
    include_trees: Mapping[str, TreeSnapshot],
    link_inputs: Mapping[str, HeldFileInput],
    python_runtime: Mapping[str, Any],
    tool_runtime: Mapping[str, Any],
) -> dict[str, Any]:
    if set(include_trees) != set(INCLUDE_TREE_ROLES):
        raise BuildError("include_tree_role_set_mismatch")
    if set(link_inputs) != set(LINK_INPUT_ROLES):
        raise BuildError("link_input_role_set_mismatch")
    body = {
        "compiled_source_execution": "held_source_fds",
        "compiler_execution": "held_compiler_fd",
        "default_clang_configuration": {
            "disabled": True,
            "flag": "--no-default-config",
        },
        "include_trees": {
            role: include_trees[role].identity for role in INCLUDE_TREE_ROLES
        },
        "input_closure_scope": (
            "all_file_backed_build_inputs_and_current_process_executable_mappings"
        ),
        "header_resolution": "private_symlink_to_held_header_fd",
        "kernel_and_process_boundary": {
            "kernel_vdso": "observed_executable_mapping_without_file_backing",
            "pre_exec_process_provenance": "outside_file_input_closure_claim",
        },
        "link_inputs": {role: link_inputs[role].identity for role in LINK_INPUT_ROLES},
        "linker_execution": "direct_held_linker_fd",
        "python_runtime": dict(python_runtime),
        "schema_version": TOOLCHAIN_INPUT_CLOSURE_SCHEMA,
        "tool_execution_runtime": dict(tool_runtime),
        "unmeasured_inputs_allowed": False,
        "unmeasured_inputs_allowed_scope": "within_input_closure_scope",
    }
    return {**body, "closure_root_sha256": canonical_sha256(body)}


def build_receipt(
    *,
    run_id: str,
    source_commit: str,
    source_bindings: Mapping[str, Mapping[str, Any]],
    compiler_identity: Mapping[str, Any],
    linker_identity: Mapping[str, Any],
    toolchain_input_closure: Mapping[str, Any],
    build_one: BuildResult,
    build_two: BuildResult,
    elf_identity: Mapping[str, Any],
    uid: int,
    gid: int,
) -> dict[str, Any]:
    if (
        RUN_ID_RE.fullmatch(run_id) is None
        or COMMIT_RE.fullmatch(source_commit) is None
    ):
        raise BuildError("native_build_action_identity_invalid")
    closure = dict(toolchain_input_closure)
    claimed_closure_root = closure.pop("closure_root_sha256", None)
    if (
        set(toolchain_input_closure)
        != {
            "closure_root_sha256",
            "compiled_source_execution",
            "compiler_execution",
            "default_clang_configuration",
            "header_resolution",
            "include_trees",
            "input_closure_scope",
            "kernel_and_process_boundary",
            "link_inputs",
            "linker_execution",
            "python_runtime",
            "schema_version",
            "tool_execution_runtime",
            "unmeasured_inputs_allowed",
            "unmeasured_inputs_allowed_scope",
        }
        or claimed_closure_root != canonical_sha256(closure)
        or closure.get("schema_version") != TOOLCHAIN_INPUT_CLOSURE_SCHEMA
        or closure.get("compiled_source_execution") != "held_source_fds"
        or closure.get("compiler_execution") != "held_compiler_fd"
        or closure.get("header_resolution") != "private_symlink_to_held_header_fd"
        or closure.get("linker_execution") != "direct_held_linker_fd"
        or closure.get("unmeasured_inputs_allowed") is not False
        or closure.get("unmeasured_inputs_allowed_scope")
        != "within_input_closure_scope"
        or closure.get("input_closure_scope")
        != "all_file_backed_build_inputs_and_current_process_executable_mappings"
        or closure.get("kernel_and_process_boundary")
        != {
            "kernel_vdso": "observed_executable_mapping_without_file_backing",
            "pre_exec_process_provenance": "outside_file_input_closure_claim",
        }
        or closure.get("default_clang_configuration")
        != {"disabled": True, "flag": "--no-default-config"}
        or not isinstance(closure.get("include_trees"), Mapping)
        or set(closure["include_trees"]) != set(INCLUDE_TREE_ROLES)
        or not isinstance(closure.get("link_inputs"), Mapping)
        or set(closure["link_inputs"]) != set(LINK_INPUT_ROLES)
        or not isinstance(closure.get("python_runtime"), Mapping)
        or not isinstance(closure.get("tool_execution_runtime"), Mapping)
    ):
        raise BuildError("toolchain_input_closure_receipt_invalid")
    expected_object_roles = set(COMPILED_SOURCE_FILES)
    if (
        set(source_bindings) != set(NATIVE_SOURCE_FILES)
        or set(build_one.objects) != expected_object_roles
        or set(build_two.objects) != expected_object_roles
    ):
        raise BuildError("native_build_receipt_input_role_set_invalid")
    if build_one.binary.payload != build_two.binary.payload:
        raise BuildError("native_builds_not_byte_identical")
    if set(build_one.objects) != set(build_two.objects) or any(
        build_one.objects[role].payload != build_two.objects[role].payload
        for role in build_one.objects
    ):
        raise BuildError("native_intermediate_objects_not_byte_identical")
    if any(marker in build_one.binary.payload for marker in TEST_HOOK_MARKERS):
        raise BuildError("native_testing_hook_string_present")
    if any(
        "CUR0S_NATIVE_PREFLIGHT_TESTING" in item
        for item in (*COMPILE_ARGV_TEMPLATE, *LINK_ARGV_TEMPLATE)
    ):
        raise BuildError("native_testing_macro_present")
    digest = build_one.binary.digest
    intermediate_objects = {
        "build_one": {
            role: build_one.objects[role].digest for role in sorted(build_one.objects)
        },
        "build_two": {
            role: build_two.objects[role].digest for role in sorted(build_two.objects)
        },
        "deterministic_match": True,
    }
    body: dict[str, Any] = {
        "schema_version": NATIVE_PREFLIGHT_BUILD_SCHEMA,
        "run_id": run_id,
        "source_commit": source_commit,
        "source_commit_binding_status": SOURCE_COMMIT_BINDING_STATUS,
        "source_file_bindings": dict(source_bindings),
        "intended_target": {
            "architecture": "aarch64",
            "compiler_target": "aarch64-linux-android30",
            "runtime_device_and_soc_gate": "not_claimed_by_build_receipt",
        },
        "build_principal": {"gid": gid, "uid": uid},
        "compiler_identity": dict(compiler_identity),
        "linker_identity": dict(linker_identity),
        "toolchain_input_closure": dict(toolchain_input_closure),
        "build_environment": dict(BUILD_ENVIRONMENT),
        "build_argv_template": {
            "compile": list(COMPILE_ARGV_TEMPLATE),
            "link": list(LINK_ARGV_TEMPLATE),
        },
        "build_one": digest,
        "build_two": build_two.binary.digest,
        "intermediate_objects": intermediate_objects,
        "binary_identity": {
            **digest,
            "gid": gid,
            "mode": "0700",
            "nlink": 1,
            "uid": uid,
        },
        "elf_identity": dict(elf_identity),
        "deterministic_binary_match": True,
        "testing_macro_absent": True,
        "testing_hook_strings_absent": True,
        "network_requested": False,
        "network_syscalls_instrumented": False,
        "security_ceiling": NATIVE_PREFLIGHT_SECURITY_CEILING,
    }
    return {**body, "build_receipt_root_sha256": canonical_sha256(body)}


def _load_contract_module(
    source_root: Path,
    binding: Mapping[str, Any],
) -> ModuleType:
    path = source_root / COMMERCIAL_CONTRACT_FILE
    module_name = "_cur0s_build_driver_contract"
    snapshot = read_regular_file(path, byte_limit=MAX_SOURCE_BYTES)
    if binding.get("bytes") != len(snapshot.payload) or binding.get(
        "sha256"
    ) != prefixed_sha256(snapshot.payload):
        raise BuildError("commercial_contract_snapshot_binding_mismatch")
    module = ModuleType(module_name)
    module.__file__ = os.fspath(path)
    module.__package__ = ""
    sys.modules[module_name] = module
    try:
        code = compile(snapshot.payload, os.fspath(path), "exec", dont_inherit=True)
        exec(code, module.__dict__)
    except Exception as error:
        sys.modules.pop(module_name, None)
        raise BuildError("commercial_contract_import_failed") from error
    return module


def production_receipt_validator(module: ModuleType) -> ReceiptValidator:
    def validate(
        receipt: Mapping[str, Any],
        source_commit: str,
        bindings: Mapping[str, Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        if (
            module.NATIVE_PREFLIGHT_BUILD_SCHEMA != NATIVE_PREFLIGHT_BUILD_SCHEMA
            or tuple(module.NATIVE_PREFLIGHT_SOURCE_FILES) != NATIVE_SOURCE_FILES
            or module.NATIVE_PREFLIGHT_SECURITY_CEILING
            != NATIVE_PREFLIGHT_SECURITY_CEILING
            or module.NATIVE_PREFLIGHT_SOURCE_COMMIT_BINDING_STATUS
            != SOURCE_COMMIT_BINDING_STATUS
            or module.NATIVE_PREFLIGHT_RUNTIME_DEPENDENCY_CLOSURE_SCHEMA
            != RUNTIME_DEPENDENCY_CLOSURE_SCHEMA
            or module.native_preflight_build_python_runtime_identity()
            != PYTHON_RUNTIME_BASE_IDENTITY
            or module.NATIVE_PREFLIGHT_BUILD_TOOL_RUNTIME_IDENTITY
            != TOOL_RUNTIME_IDENTITY
        ):
            raise BuildError("commercial_contract_constant_mismatch")
        try:
            return module.validate_native_preflight_build_receipt(
                receipt,
                source_commit=source_commit,
                source_file_bindings=bindings,
            )
        except Exception as error:
            raise BuildError("native_build_receipt_validation_failed") from error

    return validate


def final_prepublication_authority_revalidation(
    config: BuildConfig,
    initial_bindings: Mapping[str, Mapping[str, Any]],
    include_trees: Mapping[str, TreeSnapshot],
    link_inputs: Mapping[str, HeldFileInput],
    source_inputs: Mapping[str, HeldFileInput],
    runtime_guard: RuntimeGuard,
    tool_runtime_guard: RuntimeGuard,
) -> None:
    """Perform every final fallible authority check before any public artifact."""

    tool_runtime_guard.revalidate()
    runtime_guard.revalidate()
    revalidate_toolchain_input_closure(config, include_trees, link_inputs)
    revalidate_held_source_inputs(source_inputs)
    if snapshot_source_bindings(config) != dict(initial_bindings):
        raise BuildError("native_sources_changed_before_publication")


def execute_build(
    config: BuildConfig,
    source_commit: str,
    *,
    receipt_validator: ReceiptValidator,
    process_runner: ProcessRunner = run_process,
    source_bindings: Mapping[str, Mapping[str, Any]] | None = None,
    python_runtime_attestor: PythonRuntimeAttestor = attest_current_python_runtime,
    python_runtime_guard: RuntimeGuard | None = None,
    tool_runtime_attestor: ToolRuntimeAttestor = attest_tool_runtime_closure,
) -> dict[str, Any]:
    if COMMIT_RE.fullmatch(source_commit) is None:
        raise BuildError("source_commit_invalid")
    runtime_guard = (
        python_runtime_attestor(config, source_commit)
        if python_runtime_guard is None
        else python_runtime_guard
    )
    compiler: AttestedTool | None = None
    linker: AttestedTool | None = None
    tool_runtime_guard: RuntimeGuard | None = None
    link_inputs: dict[str, HeldFileInput] = {}
    source_inputs: dict[str, HeldFileInput] = {}
    include_trees: dict[str, TreeSnapshot] = {}
    try:
        runtime_guard.revalidate()
        require_private_directory(
            config.action_root, config.expected_uid, config.expected_gid
        )
        observed_bindings = snapshot_source_bindings(config)
        if source_bindings is not None and dict(source_bindings) != observed_bindings:
            raise BuildError("provided_source_bindings_mismatch")
        initial_bindings = observed_bindings
        if config.final_binary.exists() or config.receipt_path.exists():
            raise BuildError("native_build_publication_preexists")
        create_private_directory(
            config.build_root,
            config.expected_uid,
            config.expected_gid,
        )
        create_private_directory(
            config.build_one_directory,
            config.expected_uid,
            config.expected_gid,
        )
        create_private_directory(
            config.build_two_directory,
            config.expected_uid,
            config.expected_gid,
        )

        compiler = attest_build_tool_file("compiler", config.compiler_path)
        linker = attest_build_tool_file("linker", config.linker_path)
        tool_runtime_guard = tool_runtime_attestor(
            compiler,
            linker,
            config.source_root,
            process_runner,
        )
        tool_runtime_guard.revalidate()
        runtime_guard.revalidate()
        compiler.identity = probe_build_tool_identity(
            "compiler",
            compiler,
            config.source_root,
            process_runner,
        )
        tool_runtime_guard.revalidate()
        linker.identity = probe_build_tool_identity(
            "linker",
            linker,
            config.source_root,
            process_runner,
        )
        tool_runtime_guard.revalidate()
        runtime_guard.revalidate()
        initial_compiler_identity = dict(compiler.identity)
        initial_linker_identity = dict(linker.identity)
        include_trees, link_inputs = attest_toolchain_input_closure(config)
        source_inputs = attest_held_source_inputs(config, initial_bindings)
        create_held_header_shim(
            config,
            source_inputs["cur0s_header"],
        )
        build_one = run_one_build(
            config,
            config.build_one_output,
            config.build_one_directory,
            compiler.resolved_fd,
            linker.resolved_fd,
            link_inputs,
            source_inputs,
            process_runner,
        )
        tool_runtime_guard.revalidate()
        runtime_guard.revalidate()
        revalidate_toolchain_input_closure(config, include_trees, link_inputs)
        revalidate_held_source_inputs(source_inputs)
        build_two = run_one_build(
            config,
            config.build_two_output,
            config.build_two_directory,
            compiler.resolved_fd,
            linker.resolved_fd,
            link_inputs,
            source_inputs,
            process_runner,
        )
        tool_runtime_guard.revalidate()
        runtime_guard.revalidate()
        revalidate_toolchain_input_closure(config, include_trees, link_inputs)
        revalidate_held_source_inputs(source_inputs)
        final_compiler_identity = probe_build_tool_identity(
            "compiler",
            compiler,
            config.source_root,
            process_runner,
        )
        tool_runtime_guard.revalidate()
        final_linker_identity = probe_build_tool_identity(
            "linker",
            linker,
            config.source_root,
            process_runner,
        )
        tool_runtime_guard.revalidate()
        runtime_guard.revalidate()
        if (
            final_compiler_identity != initial_compiler_identity
            or final_linker_identity != initial_linker_identity
        ):
            raise BuildError("build_tool_changed_across_builds")

        if build_one.binary.payload != build_two.binary.payload:
            raise BuildError("native_builds_not_byte_identical")
        elf_identity = parse_aarch64_elf(build_one.binary.payload)
        final_bindings = snapshot_source_bindings(config)
        if final_bindings != initial_bindings:
            raise BuildError("native_sources_changed_across_build")
        receipt = build_receipt(
            run_id=config.action_root.name,
            source_commit=source_commit,
            source_bindings=initial_bindings,
            compiler_identity=initial_compiler_identity,
            linker_identity=initial_linker_identity,
            toolchain_input_closure=toolchain_input_closure_receipt(
                include_trees,
                link_inputs,
                runtime_guard.identity,
                tool_runtime_guard.identity,
            ),
            build_one=build_one,
            build_two=build_two,
            elf_identity=elf_identity,
            uid=config.expected_uid,
            gid=config.expected_gid,
        )
        validated = dict(receipt_validator(receipt, source_commit, initial_bindings))
        if validated != receipt:
            raise BuildError("native_build_receipt_validator_changed_value")
        final_prepublication_authority_revalidation(
            config,
            initial_bindings,
            include_trees,
            link_inputs,
            source_inputs,
            runtime_guard,
            tool_runtime_guard,
        )
        published = publish_exclusive(
            config.final_binary,
            build_one.binary.payload,
            mode=0o700,
            uid=config.expected_uid,
            gid=config.expected_gid,
        )
        if published.digest != build_one.binary.digest:
            raise BuildError("published_native_binary_identity_mismatch")
        receipt_payload = canonical_json_bytes(receipt)
        publish_exclusive(
            config.receipt_path,
            receipt_payload,
            mode=0o600,
            uid=config.expected_uid,
            gid=config.expected_gid,
        )
        return receipt
    finally:
        for value in link_inputs.values():
            value.close()
        for value in source_inputs.values():
            value.close()
        if tool_runtime_guard is not None:
            tool_runtime_guard.close()
        if compiler is not None:
            compiler.close()
        if linker is not None:
            linker.close()
        runtime_guard.close()


def production_config(run_id: str, source_commit: str) -> BuildConfig:
    if RUN_ID_RE.fullmatch(run_id) is None:
        raise BuildError("run_id_invalid")
    if COMMIT_RE.fullmatch(source_commit) is None:
        raise BuildError("source_commit_invalid")
    source_root = Path(os.path.abspath(__file__)).parents[2]
    expected_action = Path(f"{PHONE_HOME}/polymath_gemma4_e4b_frontier/{run_id}")
    expected_checkout = expected_action / f"source/Polymath-AI-{source_commit}"
    expected_driver = (
        expected_checkout / "scripts/termux/build_cur0s_native_preflight.py"
    )
    if (
        source_root != expected_checkout
        or Path(os.path.abspath(__file__)) != expected_driver
        or Path.cwd() != source_root
    ):
        raise BuildError("exact_checkout_or_working_directory_mismatch")
    return BuildConfig(
        source_root=source_root,
        action_root=expected_action,
        compiler_path=Path(COMPILER_PATH),
        linker_path=Path(LINKER_PATH),
        resource_directory=Path(RESOURCE_DIRECTORY),
        resource_include_root=Path(RESOURCE_INCLUDE_ROOT),
        system_include_root=Path(SYSTEM_INCLUDE_ROOT),
        arch_include_root=Path(ARCH_INCLUDE_ROOT),
        link_input_paths={role: Path(path) for role, path in LINK_INPUT_PATHS.items()},
        expected_uid=PHONE_UID,
        expected_gid=PHONE_GID,
    )


def parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-commit", required=True)
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    try:
        options = parse_arguments(arguments)
        previous_umask = os.umask(0o077)
        try:
            config = production_config(options.run_id, options.source_commit)
            _validate_python_startup_identity(
                python_runtime_identity(config, options.source_commit, ())
            )
            bindings = snapshot_source_bindings(config)
            if set(bindings) != set(NATIVE_SOURCE_FILES):
                raise BuildError("native_source_binding_set_mismatch")
            contract = _load_contract_module(
                config.source_root,
                bindings[COMMERCIAL_CONTRACT_FILE],
            )
            runtime_guard = attest_current_python_runtime(
                config,
                options.source_commit,
            )
            try:
                layout = contract.native_preflight_execution_layout(
                    options.run_id,
                    options.source_commit,
                )
            except Exception as error:
                raise BuildError("commercial_contract_layout_failed") from error
            if (
                Path(layout["action_root"]) != config.action_root
                or Path(layout["checkout_root"]) != config.source_root
                or Path(layout["native_binary_path"]) != config.final_binary
            ):
                raise BuildError("commercial_contract_layout_mismatch")
            try:
                receipt = execute_build(
                    config,
                    options.source_commit,
                    receipt_validator=production_receipt_validator(contract),
                    source_bindings=bindings,
                    python_runtime_guard=runtime_guard,
                )
            except Exception:
                runtime_guard.close()
                raise
        finally:
            os.umask(previous_umask)
        summary = {
            "binary_path": os.fspath(config.final_binary),
            "binary_sha256": receipt["binary_identity"]["sha256"],
            "receipt_path": os.fspath(config.receipt_path),
            "receipt_sha256": prefixed_sha256(canonical_json_bytes(receipt)),
            "status": "built",
        }
        sys.stdout.buffer.write(canonical_json_bytes(summary) + b"\n")
        sys.stdout.buffer.flush()
        return 0
    except (BuildError, OSError, ValueError) as error:
        rejection = {
            "error": str(error) or type(error).__name__,
            "status": "rejected",
        }
        sys.stderr.buffer.write(canonical_json_bytes(rejection) + b"\n")
        sys.stderr.buffer.flush()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
