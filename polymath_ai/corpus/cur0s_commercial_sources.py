"""Exact commercial-source contract for the phone-native CUR-0S rebuild.

This module freezes acquisition identity and rights evidence only.  It does
not claim semantic compilation, connected splitting, CUR-0S admission, target
learning, or authority.  Raw source bytes remain on the phone and may later be
mirrored only to a private, revision-pinned C4-COM repository.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SOURCE_ROOT_SCHEMA = "cur0s_commercial_source_root_v1"
CONTRACT_SCHEMA = "cur0s_commercial_source_contract_v1"
PHONE_TOOLCHAIN_SCHEMA = "cur0s_phone_toolchain_identity_v2"
NATIVE_PREFLIGHT_BUILD_SCHEMA = "cur0s_native_preflight_android_build_receipt_v3"
NATIVE_PREFLIGHT_TOOLCHAIN_CLOSURE_SCHEMA = "cur0s_native_toolchain_input_closure_v2"
NATIVE_PREFLIGHT_CONTRACT_SCHEMA = "cur0s_native_preflight_execution_contract_v2"
NATIVE_LAUNCH_CONTRACT_SCHEMA = "cur0s_native_outer_launch_contract_v1"
NATIVE_LAUNCH_ENVELOPE_SCHEMA = "cur0s_native_launch_envelope_v1"
NATIVE_PREFLIGHT_MANIFEST_HEADER = "CUR0S_NATIVE_PREFLIGHT_MANIFEST_V3"
NATIVE_PREFLIGHT_TREE_CANONICALIZATION = (
    "sorted_relative_POSIX_paths_canonical_JSON_type_mode_"
    "regular_bytes_sha256_source_only_excluding_root_site_packages_"
    "all_pycache_and_pyc_reject_external_symlinks_root_excluded"
)
NATIVE_PREFLIGHT_SECURITY_CEILING = (
    "observational_only_no_guarantee_against_a_concurrent_malicious_"
    "same_uid_between_checks"
)
NATIVE_PREFLIGHT_SOURCE_FILES = (
    "scripts/termux/native/cur0s_sha256.h",
    "scripts/termux/native/cur0s_sha256.c",
    "scripts/termux/native/cur0s_native_preflight.c",
    "scripts/termux/build_cur0s_native_preflight.py",
    "polymath_ai/corpus/cur0s_commercial_sources.py",
)
NATIVE_PREFLIGHT_BUILD_TREE_CANONICALIZATION = (
    "sorted_relative_POSIX_paths_canonical_JSON_type_mode_uid_gid_nlink_"
    "regular_bytes_sha256_or_literal_internal_symlink_target_root_excluded"
)
NATIVE_PREFLIGHT_BUILD_INCLUDE_TREES = {
    "clang_resource_tree": {
        "canonicalization": NATIVE_PREFLIGHT_BUILD_TREE_CANONICALIZATION,
        "entry_count": 330,
        "entry_type": "directory_tree",
        "gid": 10536,
        "mode": "0755",
        "nlink": 6,
        "path": "/data/data/com.termux/files/usr/lib/clang/21",
        "regular_bytes": 49_574_163,
        "regular_file_count": 318,
        "sha256": (
            "sha256:d97053fa2e97adeb5812e1f79b6946e53e75096f6cdea652361b089e97c3f48a"
        ),
        "symlink_count": 0,
        "uid": 10536,
    },
    "termux_arch_headers": {
        "canonicalization": NATIVE_PREFLIGHT_BUILD_TREE_CANONICALIZATION,
        "entry_count": 39,
        "entry_type": "directory_tree",
        "gid": 10536,
        "mode": "0700",
        "nlink": 3,
        "path": ("/data/data/com.termux/files/usr/include/aarch64-linux-android"),
        "regular_bytes": 42_645,
        "regular_file_count": 38,
        "sha256": (
            "sha256:6f5a4c1ce9ad3151bd9c1237b7be7698695edc9b63bd5893fdca0cd7ad62b43d"
        ),
        "symlink_count": 0,
        "uid": 10536,
    },
    "termux_system_headers": {
        "canonicalization": NATIVE_PREFLIGHT_BUILD_TREE_CANONICALIZATION,
        "entry_count": 10_906,
        "entry_type": "directory_tree",
        "gid": 10536,
        "mode": "0700",
        "nlink": 136,
        "path": "/data/data/com.termux/files/usr/include",
        "regular_bytes": 134_436_489,
        "regular_file_count": 10_284,
        "sha256": (
            "sha256:3390524567ef958bd79c7460816eec8f90591fb6277aa96588683850ca55c316"
        ),
        "symlink_count": 26,
        "uid": 10536,
    },
}
NATIVE_PREFLIGHT_BUILD_LINK_INPUTS = {
    "android_libc": {
        "bytes": 1_143_072,
        "entry_type": "regular_file",
        "gid": 1000,
        "mode": "0644",
        "nlink": 1,
        "path": "/apex/com.android.runtime/lib64/bionic/libc.so",
        "sha256": (
            "sha256:b4d95dc39a379dbe5049ce033f019b01a2f10dcf507562e83c72eef901d6ebcf"
        ),
        "uid": 1000,
    },
    "android_libdl": {
        "bytes": 50_760,
        "entry_type": "regular_file",
        "gid": 1000,
        "mode": "0644",
        "nlink": 1,
        "path": "/apex/com.android.runtime/lib64/bionic/libdl.so",
        "sha256": (
            "sha256:7abc47c96a4f49d52647e7f1d2045d3eb9ba4d9766c1d7f225e6aa229fa9f479"
        ),
        "uid": 1000,
    },
    "clang_rt_builtins": {
        "bytes": 409_982,
        "entry_type": "regular_file",
        "gid": 10536,
        "mode": "0600",
        "nlink": 1,
        "path": (
            "/data/data/com.termux/files/usr/lib/clang/21/lib/linux/"
            "libclang_rt.builtins-aarch64-android.a"
        ),
        "sha256": (
            "sha256:9aeed0613b933c2c79a7c366371b5910681b740b78093d33237fd31c67345cb2"
        ),
        "uid": 10536,
    },
    "crtbegin_dynamic": {
        "bytes": 3_896,
        "entry_type": "regular_file",
        "gid": 10536,
        "mode": "0600",
        "nlink": 1,
        "path": "/data/data/com.termux/files/usr/lib/crtbegin_dynamic.o",
        "sha256": (
            "sha256:612cf67a324667367e78f99c4f42116d9f0ae94dd1bed72303c0b989d87facac"
        ),
        "uid": 10536,
    },
    "crtend_android": {
        "bytes": 832,
        "entry_type": "regular_file",
        "gid": 10536,
        "mode": "0600",
        "nlink": 1,
        "path": "/data/data/com.termux/files/usr/lib/crtend_android.o",
        "sha256": (
            "sha256:4a73856c6b87bfaa7b6fc5963796f21941f85f9bb3de36f688f70b5c5ceca44b"
        ),
        "uid": 10536,
    },
    "libunwind": {
        "bytes": 92_452,
        "entry_type": "regular_file",
        "gid": 10536,
        "mode": "0600",
        "nlink": 1,
        "path": "/data/data/com.termux/files/usr/lib/libunwind.a",
        "sha256": (
            "sha256:c52c8462134a1610e93d873e9d992f4804027d0c73115b2ea4c21b0aed5cbe65"
        ),
        "uid": 10536,
    },
}
NATIVE_PREFLIGHT_COMPILE_ARGV_TEMPLATE = (
    "/data/data/com.termux/files/usr/bin/clang",
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
NATIVE_PREFLIGHT_LINK_ARGV_TEMPLATE = (
    "/data/data/com.termux/files/usr/bin/ld.lld",
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
NATIVE_PREFLIGHT_FIXED_FD_MAP = {
    "manifest": 5,
    "native_attestation": 4,
    "preregistration": 6,
    "python_exec_cloexec": 7,
    "runner": 3,
}
NATIVE_OUTER_ENVIRONMENT: dict[str, str] = {}
NATIVE_OUTER_ENVIRONMENT_SHA256 = (
    "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
)
PHONE_APP_UID = 10536
PHONE_APP_GID = 10536
_RUN_ID_RE = re.compile(r"^[0-9]{8}T[0-9]{6}Z_cur0s_commercial_sources_v1$")
LANE = "C4-COM"

NATIVE_PREFLIGHT_RUNTIME_DEPENDENCY_CLOSURE_SCHEMA = (
    "cur0s_native_aarch64_recursive_runtime_dependency_closure_v2"
)
NATIVE_PREFLIGHT_ACTUAL_LOADER_RESOLUTION_SCHEMA = (
    "cur0s_native_aarch64_actual_loader_resolution_v1"
)
NATIVE_PREFLIGHT_SOURCE_COMMIT_BINDING_STATUS = (
    "pending_host_preregistration_git_tree_binding"
)
NATIVE_PREFLIGHT_BUILD_DRIVER_LAUNCH_ENVIRONMENT = {
    "ANDROID_ROOT": "/system",
    "HOME": "/data/data/com.termux/files/home",
    "LC_ALL": "C",
    "LD_PRELOAD": "/data/data/com.termux/files/usr/lib/libtermux-exec.so",
    "PATH": "/data/data/com.termux/files/usr/bin:/system/bin",
    "TERMUX_EXEC__PROC_SELF_EXE": "/data/data/com.termux/files/usr/bin/python",
}


def _native_runtime_file_identity(
    literal_path: str,
    resolved_path: str,
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


_TERMUX_PREFIX = "/data/data/com.termux/files/usr"
_TERMUX_LIBRARY_RUNPATH = f"{_TERMUX_PREFIX}/lib"

_PHONE_THERMAL_ZONE_ROSTER = (
    ("thermal_zone0", "aoss-0", "compute_cpu_soc"),
    ("thermal_zone1", "pm8550-bcl-lvl0", "excluded_non_temperature"),
    ("thermal_zone2", "cpu-0-0-0", "compute_cpu_soc"),
    ("thermal_zone3", "pm8550-bcl-lvl1", "excluded_non_temperature"),
    ("thermal_zone4", "cpu-0-0-1", "compute_cpu_soc"),
    ("thermal_zone5", "pm8550-bcl-lvl2", "excluded_non_temperature"),
    ("thermal_zone6", "vbat", "excluded_non_temperature"),
    ("thermal_zone7", "pmih010x-ibat-lvl0", "excluded_non_temperature"),
    ("thermal_zone8", "pmih010x-ibat-lvl1", "excluded_non_temperature"),
    ("thermal_zone9", "cpu-0-1-0", "compute_cpu_soc"),
    ("thermal_zone10", "pmih010x-bcl-lvl0", "excluded_non_temperature"),
    ("thermal_zone11", "cpu-0-1-1", "compute_cpu_soc"),
    ("thermal_zone12", "pmih010x-bcl-lvl1", "excluded_non_temperature"),
    ("thermal_zone13", "cpu-0-2-0", "compute_cpu_soc"),
    ("thermal_zone14", "pmih010x-bcl-lvl2", "excluded_non_temperature"),
    ("thermal_zone15", "cpu-0-2-1", "compute_cpu_soc"),
    ("thermal_zone16", "cpu-0-3-0", "compute_cpu_soc"),
    ("thermal_zone17", "cpu-0-3-1", "compute_cpu_soc"),
    ("thermal_zone18", "cpu-0-4-0", "compute_cpu_soc"),
    ("thermal_zone19", "cpu-0-4-1", "compute_cpu_soc"),
    ("thermal_zone20", "cpu-0-5-0", "compute_cpu_soc"),
    ("thermal_zone21", "cpu-0-5-1", "compute_cpu_soc"),
    ("thermal_zone22", "cpuss-0-0", "compute_cpu_soc"),
    ("thermal_zone23", "cpuss-0-1", "compute_cpu_soc"),
    ("thermal_zone24", "aoss-1", "compute_cpu_soc"),
    ("thermal_zone25", "cpu-1-0-0", "compute_cpu_soc"),
    ("thermal_zone26", "cpu-1-0-1", "compute_cpu_soc"),
    ("thermal_zone27", "cpu-1-1-0", "compute_cpu_soc"),
    ("thermal_zone28", "cpu-1-1-1", "compute_cpu_soc"),
    ("thermal_zone29", "cpuss-1-0", "compute_cpu_soc"),
    ("thermal_zone30", "cpuss-1-1", "compute_cpu_soc"),
    ("thermal_zone31", "aoss-2", "compute_cpu_soc"),
    ("thermal_zone32", "gpuss-0", "gpu"),
    ("thermal_zone33", "gpuss-1", "gpu"),
    ("thermal_zone34", "gpuss-2", "gpu"),
    ("thermal_zone35", "gpuss-3", "gpu"),
    ("thermal_zone36", "gpuss-4", "gpu"),
    ("thermal_zone37", "gpuss-5", "gpu"),
    ("thermal_zone38", "gpuss-6", "gpu"),
    ("thermal_zone39", "gpuss-7", "gpu"),
    ("thermal_zone40", "mdmss-0", "compute_cpu_soc"),
    ("thermal_zone41", "mdmss-1", "compute_cpu_soc"),
    ("thermal_zone42", "mdmss-2", "compute_cpu_soc"),
    ("thermal_zone43", "mdmss-3", "compute_cpu_soc"),
    ("thermal_zone44", "camera-0", "compute_cpu_soc"),
    ("thermal_zone45", "camera-1", "compute_cpu_soc"),
    ("thermal_zone46", "video", "compute_cpu_soc"),
    ("thermal_zone47", "aoss-3", "compute_cpu_soc"),
    ("thermal_zone48", "nsphvx-0", "npu"),
    ("thermal_zone49", "nsphvx-1", "npu"),
    ("thermal_zone50", "nsphvx-2", "npu"),
    ("thermal_zone51", "nsphmx-0", "npu"),
    ("thermal_zone52", "nsphmx-1", "npu"),
    ("thermal_zone53", "nsphmx-2", "npu"),
    ("thermal_zone54", "nsphmx-3", "npu"),
    ("thermal_zone55", "ddr", "ddr"),
    ("thermal_zone56", "skin-msm-therm", "skin"),
    ("thermal_zone57", "cam-flash-therm", "skin"),
    ("thermal_zone58", "pm8010m_tz", "pmic"),
    ("thermal_zone59", "wlan-therm", "skin"),
    ("thermal_zone60", "socd", "excluded_non_temperature"),
    ("thermal_zone61", "pmr735d_tz", "pmic"),
    ("thermal_zone62", "pa-therm1", "skin"),
    ("thermal_zone63", "pa-therm2", "skin"),
    ("thermal_zone64", "sidekey-therm", "skin"),
    ("thermal_zone65", "rear-tof-therm", "skin"),
    ("thermal_zone66", "xo-therm", "skin"),
    ("thermal_zone67", "usb-therm", "battery_usb"),
    ("thermal_zone68", "wls-therm", "battery_usb"),
    ("thermal_zone69", "alps-therm", "skin"),
    ("thermal_zone70", "pm8550ve_g_tz", "pmic"),
    ("thermal_zone71", "pm8550ve_i_tz", "pmic"),
    ("thermal_zone72", "pm8550vs_j_tz", "pmic"),
    ("thermal_zone73", "pmih010x_tz", "pmic"),
    ("thermal_zone74", "pmih010x_lite_tz", "pmic"),
    ("thermal_zone75", "pm8550_tz", "pmic"),
    ("thermal_zone76", "pm8550ve_d_tz", "pmic"),
    ("thermal_zone77", "pm8550ve_f_tz", "pmic"),
    ("thermal_zone78", "usb", "excluded_non_temperature"),
    ("thermal_zone79", "wireless", "excluded_non_temperature"),
    ("thermal_zone80", "battery", "battery_usb"),
    ("thermal_zone81", "sdr0_pa", "skin"),
    ("thermal_zone82", "sdr0", "compute_cpu_soc"),
    ("thermal_zone83", "mmw_ific0", "compute_cpu_soc"),
)
_PHONE_THERMAL_GROUP_CEILINGS_MILLIDEGREES_C = {
    "battery_usb": 45_000,
    "compute_cpu_soc": 85_000,
    "ddr": 85_000,
    "gpu": 85_000,
    "npu": 85_000,
    "pmic": 85_000,
    "skin": 54_000,
}


def phone_thermal_safety_contract() -> dict[str, Any]:
    """Return the exact NX789J thermal type roster and fail-closed ceilings."""

    zone_type_roster = {
        zone_name: sensor_type
        for zone_name, sensor_type, _classification in _PHONE_THERMAL_ZONE_ROSTER
    }
    sensor_types_by_group = {
        group: sorted(
            sensor_type
            for _zone_name, sensor_type, classification in _PHONE_THERMAL_ZONE_ROSTER
            if classification == group
        )
        for group in sorted(_PHONE_THERMAL_GROUP_CEILINGS_MILLIDEGREES_C)
    }
    excluded_types = sorted(
        sensor_type
        for _zone_name, sensor_type, classification in _PHONE_THERMAL_ZONE_ROSTER
        if classification == "excluded_non_temperature"
    )
    if (
        list(zone_type_roster)
        != [f"thermal_zone{index}" for index in range(len(_PHONE_THERMAL_ZONE_ROSTER))]
        or len(set(zone_type_roster.values())) != len(zone_type_roster)
        or any(not sensor_types for sensor_types in sensor_types_by_group.values())
    ):
        raise CommercialSourceError("phone_thermal_contract_internal_invalid")
    body = {
        "schema_version": "cur0s_phone_thermal_safety_contract_v1",
        "sysfs_root": "/sys/class/thermal",
        "expected_zone_count": len(zone_type_roster),
        "zone_type_roster": zone_type_roster,
        "sensor_types_by_group": sensor_types_by_group,
        "excluded_non_temperature_sensor_types": excluded_types,
        "group_ceilings_millidegrees_c": dict(
            sorted(_PHONE_THERMAL_GROUP_CEILINGS_MILLIDEGREES_C.items())
        ),
        "temperature_unit": "millidegrees_c",
        "plausible_temperature_range_millidegrees_c": [5_000, 150_000],
        "unavailable_sentinels_millidegrees_c": [-273_000, -40_960],
        "zone_binding": (
            "exact_zone_name_roster_held_zone_directory_fd_type_read_before_and_"
            "after_held_temp_fd"
        ),
        "unknown_missing_duplicate_or_type_swap_policy": "stop_before_claim_or_continue",
        "missing_readable_group_policy": "stop_before_claim_or_continue",
        "non_temperature_values_are_not_read_or_compared": True,
        "oem_thermal_property_inputs": {
            "ro.vendor.feature.zte_feature_ccc_bat_temp_cntrl": "true",
            "ro.vendor.feature.zte_feature_ccc_temp_threshold": ("skin,54,battery,45"),
        },
        "group_ceiling_basis": {
            "battery_usb": ("battery_45_token_in_exact_ccc_temp_threshold_property"),
            "skin": "skin_54_token_in_exact_ccc_temp_threshold_property",
            "compute_gpu_npu_ddr_pmic": (
                "existing_preregistered_85C_ceiling_not_claimed_as_OEM_property"
            ),
        },
        "oem_property_attestation": (
            "exact_value_via_hash_bound_root_owned_system_getprop_before_claim"
        ),
    }
    return {**body, "contract_root_sha256": canonical_sha256(body)}


NATIVE_PREFLIGHT_BUILD_TOOL_RUNTIME_INPUTS = {
    "android_bionic_libc": _native_runtime_file_identity(
        "/apex/com.android.runtime/lib64/bionic/libc.so",
        "/apex/com.android.runtime/lib64/bionic/libc.so",
        "sha256:b4d95dc39a379dbe5049ce033f019b01a2f10dcf507562e83c72eef901d6ebcf",
        1_143_072,
        "0644",
        1000,
        1000,
    ),
    "android_bionic_libdl": _native_runtime_file_identity(
        "/system/lib64/libdl.so",
        "/apex/com.android.runtime/lib64/bionic/libdl.so",
        "sha256:7abc47c96a4f49d52647e7f1d2045d3eb9ba4d9766c1d7f225e6aa229fa9f479",
        50_760,
        "0644",
        1000,
        1000,
        "/apex/com.android.runtime/lib64/bionic/libdl.so",
        "0644",
        0,
        0,
    ),
    "android_bionic_libm": _native_runtime_file_identity(
        "/system/lib64/libm.so",
        "/apex/com.android.runtime/lib64/bionic/libm.so",
        "sha256:2a99c9ac7a12461663ec31b8d4ee3404ee99a1dca53f7c30b248bcccb155eefc",
        249_192,
        "0644",
        1000,
        1000,
        "/apex/com.android.runtime/lib64/bionic/libm.so",
        "0644",
        0,
        0,
    ),
    "android_ld": _native_runtime_file_identity(
        "/system/lib64/ld-android.so",
        "/system/lib64/ld-android.so",
        "sha256:599ae148e0abc4a93d0d20915338c494a2cbb5df5ba28257f0ac84e6f0e3447a",
        34_144,
        "0644",
        0,
        0,
    ),
    "android_linker64": _native_runtime_file_identity(
        "/system/bin/linker64",
        "/apex/com.android.runtime/bin/linker64",
        "sha256:6aa1b8bcf1da7e8b48f67f78eebaa2d9356c76ad3c9809bd5576b579907d7f9e",
        2_160_952,
        "0755",
        0,
        2000,
        "/apex/com.android.runtime/bin/linker64",
        "0755",
        0,
        2000,
    ),
    "libclang_cpp": _native_runtime_file_identity(
        f"{_TERMUX_PREFIX}/lib/libclang-cpp.so",
        f"{_TERMUX_PREFIX}/lib/libclang-cpp.so",
        "sha256:279758cd28398a44d0f036474ccd4839e1ba0c44bcbfc44cdb05a28527b0227d",
        59_130_224,
        "0600",
        PHONE_APP_UID,
        PHONE_APP_GID,
    ),
    "libffi": _native_runtime_file_identity(
        f"{_TERMUX_PREFIX}/lib/libffi.so",
        f"{_TERMUX_PREFIX}/lib/libffi.so",
        "sha256:11cfbf6e8a9d18ebc7dd4f5a1acb08404b1dea9503e5ca13066d1b0fa01435e1",
        86_144,
        "0700",
        PHONE_APP_UID,
        PHONE_APP_GID,
    ),
    "libiconv": _native_runtime_file_identity(
        f"{_TERMUX_PREFIX}/lib/libiconv.so",
        f"{_TERMUX_PREFIX}/lib/libiconv.so",
        "sha256:763c461c53d47e4f10b585b33ed6589949ce7765aa560f4b2aedfc7e4885cae2",
        1_082_512,
        "0600",
        PHONE_APP_UID,
        PHONE_APP_GID,
    ),
    "libicudata": _native_runtime_file_identity(
        f"{_TERMUX_PREFIX}/lib/libicudata.so.78",
        f"{_TERMUX_PREFIX}/lib/libicudata.so.78.3",
        "sha256:82b40055d3f2eada13b5816069c5bc2d82a4fa5b919fad4f69b1e83f5382ec7a",
        33_108_952,
        "0700",
        PHONE_APP_UID,
        PHONE_APP_GID,
        "libicudata.so.78.3",
        "0777",
    ),
    "libicuuc": _native_runtime_file_identity(
        f"{_TERMUX_PREFIX}/lib/libicuuc.so.78",
        f"{_TERMUX_PREFIX}/lib/libicuuc.so.78.3",
        "sha256:104dc1ed87acd79b200cac3998bbfcdcc02cc01d139f5c58a8c8d363b4f6d49d",
        1_867_696,
        "0700",
        PHONE_APP_UID,
        PHONE_APP_GID,
        "libicuuc.so.78.3",
        "0777",
    ),
    "libllvm": _native_runtime_file_identity(
        f"{_TERMUX_PREFIX}/lib/libLLVM.so",
        f"{_TERMUX_PREFIX}/lib/libLLVM.so",
        "sha256:d8157ef272769f24142408f819e9eb27139e9c3b0fecbd468fe5416e77c402ce",
        129_366_048,
        "0600",
        PHONE_APP_UID,
        PHONE_APP_GID,
    ),
    "libxml2": _native_runtime_file_identity(
        f"{_TERMUX_PREFIX}/lib/libxml2.so.16",
        f"{_TERMUX_PREFIX}/lib/libxml2.so.16.1.3",
        "sha256:541f9a23a573322ffd6f31f2f28af0c4f614bfb547441006c15ddc0192f35366",
        1_048_952,
        "0700",
        PHONE_APP_UID,
        PHONE_APP_GID,
        "libxml2.so.16.1.3",
        "0777",
    ),
    "libz": _native_runtime_file_identity(
        f"{_TERMUX_PREFIX}/lib/libz.so.1",
        f"{_TERMUX_PREFIX}/lib/libz.so.1.3.2",
        "sha256:6d1a271adb9864fd66d696c746eac7a43faaa158b1370d32774ef73f1fe799ef",
        72_232,
        "0700",
        PHONE_APP_UID,
        PHONE_APP_GID,
        "libz.so.1.3.2",
        "0777",
    ),
    "libzstd": _native_runtime_file_identity(
        f"{_TERMUX_PREFIX}/lib/libzstd.so.1",
        f"{_TERMUX_PREFIX}/lib/libzstd.so.1.5.7",
        "sha256:5baa1d62cdd945afb01ae0a8d4ee8cdd3bcb8ec4d21e90b30ef017655a86bebf",
        820_840,
        "0600",
        PHONE_APP_UID,
        PHONE_APP_GID,
        "libzstd.so.1.5.7",
        "0777",
    ),
    "termux_libcxx": _native_runtime_file_identity(
        f"{_TERMUX_PREFIX}/lib/libc++_shared.so",
        f"{_TERMUX_PREFIX}/lib/libc++_shared.so",
        "sha256:e09c2f45cf4cf8ae574f94b6c2650d99ead0d332d5396f6613f062a2d2d73540",
        1_374_336,
        "0700",
        PHONE_APP_UID,
        PHONE_APP_GID,
    ),
}
NATIVE_PREFLIGHT_BUILD_TOOL_RUNTIME_SONAME_ROLES = {
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
NATIVE_PREFLIGHT_BUILD_TOOL_RUNTIME_GRAPH = {
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
        "runpath": _TERMUX_LIBRARY_RUNPATH,
        "soname": None,
    },
    "libclang_cpp": {
        "interpreter": None,
        "needed": ["libc.so", "libLLVM.so", "libc++_shared.so", "libm.so"],
        "rpath": None,
        "runpath": _TERMUX_LIBRARY_RUNPATH,
        "soname": "libclang-cpp.so",
    },
    "libffi": {
        "interpreter": None,
        "needed": ["libc.so"],
        "rpath": None,
        "runpath": f"{_TERMUX_LIBRARY_RUNPATH}:{_TERMUX_LIBRARY_RUNPATH}",
        "soname": "libffi.so",
    },
    "libiconv": {
        "interpreter": None,
        "needed": ["libc.so"],
        "rpath": None,
        "runpath": _TERMUX_LIBRARY_RUNPATH,
        "soname": "libiconv.so",
    },
    "libicudata": {
        "interpreter": None,
        "needed": [],
        "rpath": None,
        "runpath": _TERMUX_LIBRARY_RUNPATH,
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
        "runpath": _TERMUX_LIBRARY_RUNPATH,
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
        "runpath": _TERMUX_LIBRARY_RUNPATH,
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
        "runpath": _TERMUX_LIBRARY_RUNPATH,
        "soname": "libxml2.so.16",
    },
    "libz": {
        "interpreter": None,
        "needed": ["libc.so"],
        "rpath": None,
        "runpath": _TERMUX_LIBRARY_RUNPATH,
        "soname": "libz.so.1",
    },
    "libzstd": {
        "interpreter": None,
        "needed": ["libc.so"],
        "rpath": None,
        "runpath": _TERMUX_LIBRARY_RUNPATH,
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
        "runpath": _TERMUX_LIBRARY_RUNPATH,
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
NATIVE_PREFLIGHT_BUILD_TOOL_RUNTIME_IDENTITY = {
    "dependency_graph": NATIVE_PREFLIGHT_BUILD_TOOL_RUNTIME_GRAPH,
    "interpreter_role": "android_linker64",
    "recursive_resolution_complete": True,
    "runtime_inputs": NATIVE_PREFLIGHT_BUILD_TOOL_RUNTIME_INPUTS,
    "schema_version": NATIVE_PREFLIGHT_RUNTIME_DEPENDENCY_CLOSURE_SCHEMA,
    "soname_roles": NATIVE_PREFLIGHT_BUILD_TOOL_RUNTIME_SONAME_ROLES,
    "tool_roots": {
        "compiler": f"{_TERMUX_PREFIX}/bin/clang-21",
        "linker": f"{_TERMUX_PREFIX}/bin/lld",
    },
}
NATIVE_PREFLIGHT_ACTUAL_LOADER_EXPECTED_RESOLUTION = {
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


class CommercialSourceError(RuntimeError):
    """A fail-closed source-contract violation."""


@dataclass(frozen=True)
class EpubIdentitySpec:
    opf_path: str
    opf_sha256: str
    navigation_path: str
    navigation_sha256: str
    rights_member_path: str
    rights_member_sha256: str
    identifier: str
    title: str
    language: str
    modified: str
    package_version: str | None
    catalogue_subject: str
    catalogue_grade: int
    filename_subject_token: str
    filename_grade_token: str
    artifact_notice_url: str
    catalogue_license_id: str
    artifact_notice_license_id: str
    resolved_license_id: str
    catalogue_evidence_root_sha256: str
    terms_evidence_root_sha256: str
    rights_subject_template_mismatch: bool
    container_sha256: str | None = None
    opf_publisher_values: tuple[str, ...] = ()
    opf_creator_values: tuple[str, ...] = ()
    opf_rights_values: tuple[str, ...] = ()
    opf_subject_values: tuple[str, ...] = ()
    opf_grade_values: tuple[str, ...] | None = None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        for field in (
            "opf_publisher_values",
            "opf_creator_values",
            "opf_rights_values",
            "opf_subject_values",
        ):
            value[field] = list(value[field])
        value["opf_grade_values"] = (
            None if self.opf_grade_values is None else list(self.opf_grade_values)
        )
        return value


@dataclass(frozen=True)
class PayloadRightsEvidenceSpec:
    locator_kind: str
    locator: str
    byte_offset: int | None
    byte_length: int | None
    sha256: str
    license_id: str
    required_markers: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["required_markers"] = list(self.required_markers)
        return value

    def observed_record(self) -> dict[str, Any]:
        return {
            **self.to_dict(),
            "sha256": "sha256:" + self.sha256,
            "verification_method": f"exact_{self.locator_kind}",
        }


@dataclass(frozen=True)
class ExternalRightsEvidenceSpec:
    evidence_id: str
    locator: str
    sha256: str
    byte_count: int | None
    canonicalization: str
    observed_license_id: str | None
    role: str = "supplementary_conflict_context"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DirectSourceSpec:
    source_id: str
    stages: tuple[str, ...]
    url: str
    filename: str
    media_type: str
    expected_bytes: int
    expected_etag: str
    expected_last_modified: str | None
    release_identity: str
    license_id: str
    license_class: str
    rights_proof: str
    required_markers: tuple[str, ...]
    selection_filter: str
    expected_sha256: str | None = None
    conditional_lock_mode: str = "if_match_enforced_observed_412_on_mismatch"
    payload_rights_evidence: tuple[PayloadRightsEvidenceSpec, ...] = ()
    external_rights_evidence: tuple[ExternalRightsEvidenceSpec, ...] = ()
    rights_admission_basis: str = "exact_acquired_payload_evidence_only"
    epub_identity: EpubIdentitySpec | None = None
    transfer_mode: str = "single_response_v1"
    fixed_chunk_bytes: int | None = None

    @property
    def acquisition_mode(self) -> str:
        return "https_file"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["stages"] = list(self.stages)
        value["required_markers"] = list(self.required_markers)
        value["payload_rights_evidence"] = [
            evidence.to_dict() for evidence in self.payload_rights_specs()
        ]
        value["external_rights_evidence"] = [
            evidence.to_dict() for evidence in self.external_rights_specs()
        ]
        value["transfer_mode"] = self.transfer_mode
        value["fixed_chunk_bytes"] = self.fixed_chunk_bytes
        value["epub_identity"] = (
            None if self.epub_identity is None else self.epub_identity.to_dict()
        )
        value["acquisition_mode"] = self.acquisition_mode
        return value

    def payload_rights_specs(self) -> tuple[PayloadRightsEvidenceSpec, ...]:
        if self.payload_rights_evidence:
            return self.payload_rights_evidence
        if self.epub_identity is None:
            return ()
        return (
            PayloadRightsEvidenceSpec(
                locator_kind="zip_member",
                locator=self.epub_identity.rights_member_path,
                byte_offset=None,
                byte_length=None,
                sha256=self.epub_identity.rights_member_sha256,
                license_id="CC-BY-4.0",
                required_markers=self.required_markers,
            ),
        )

    def external_rights_specs(self) -> tuple[ExternalRightsEvidenceSpec, ...]:
        if self.epub_identity is None:
            return self.external_rights_evidence
        identity = self.epub_identity
        generated = (
            ExternalRightsEvidenceSpec(
                evidence_id="siyavula_catalogue_license_section",
                locator="https://www.siyavula.com/read",
                sha256=identity.catalogue_evidence_root_sha256,
                byte_count=None,
                canonicalization="siyavula_catalogue_target_anchors_canonical_json_v1",
                observed_license_id=identity.catalogue_license_id,
            ),
            ExternalRightsEvidenceSpec(
                evidence_id="siyavula_terms_license_section",
                locator="https://www.siyavula.com/info/terms-and-conditions",
                sha256=identity.terms_evidence_root_sha256,
                byte_count=None,
                canonicalization="siyavula_terms_license_sections_canonical_json_v1",
                observed_license_id=identity.catalogue_license_id,
            ),
        )
        return (*self.external_rights_evidence, *generated)

    def expected_payload_rights_records(self) -> list[dict[str, Any]]:
        explicit = self.payload_rights_specs()
        if explicit:
            return [evidence.observed_record() for evidence in explicit]
        if self.expected_sha256 is None:
            raise CommercialSourceError("source_spec_expected_sha256_missing")
        return [
            {
                "locator_kind": "whole_payload_marker_scan",
                "locator": self.filename,
                "byte_offset": 0,
                "byte_length": self.expected_bytes,
                "sha256": "sha256:" + self.expected_sha256,
                "license_id": self.license_id,
                "required_markers": list(self.required_markers),
                "verification_method": (
                    "exact_whole_payload_plus_structural_marker_scan"
                ),
            }
        ]


@dataclass(frozen=True)
class GitSourceSpec:
    source_id: str
    stages: tuple[str, ...]
    repository: str
    commit_sha: str
    tree_sha: str
    selected_paths: tuple[str, ...]
    selected_file_count: int
    selected_bytes: int
    license_id: str
    license_class: str
    license_sha256: str
    rights_proof: str
    selection_filter: str

    @property
    def acquisition_mode(self) -> str:
        return "git_sparse_commit"

    @property
    def clone_url(self) -> str:
        return f"https://github.com/{self.repository}.git"

    @property
    def release_identity(self) -> str:
        return f"{self.repository}@{self.commit_sha}_tree_{self.tree_sha}"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["stages"] = list(self.stages)
        value["selected_paths"] = list(self.selected_paths)
        value["clone_url"] = self.clone_url
        value["release_identity"] = self.release_identity
        value["acquisition_mode"] = self.acquisition_mode
        return value


def _siyavula_epub_identity(
    *,
    stem: str,
    opf_sha256: str,
    navigation_sha256: str,
    rights_sha256: str,
    identifier: str,
    modified: str,
    catalogue_subject: str,
    catalogue_grade: int,
    filename_subject_token: str,
    filename_grade_token: str,
    rights_subject_template_mismatch: bool = False,
) -> EpubIdentitySpec:
    return EpubIdentitySpec(
        opf_path=f"OPS/{stem}-package.opf",
        opf_sha256=opf_sha256,
        navigation_path=f"OPS/xhtml/{stem}/{stem}.nav.xhtml",
        navigation_sha256=navigation_sha256,
        rights_member_path=(
            f"OPS/xhtml/{stem}/front-matter-epubs/copyright_acknowledgements_ccby.html"
        ),
        rights_member_sha256=rights_sha256,
        identifier=identifier,
        title=stem,
        language="en",
        modified=modified,
        package_version=None,
        catalogue_subject=catalogue_subject,
        catalogue_grade=catalogue_grade,
        filename_subject_token=filename_subject_token,
        filename_grade_token=filename_grade_token,
        artifact_notice_url="http://creativecommons.org/licenses/by/4.0/",
        catalogue_license_id="CC-BY-3.0",
        artifact_notice_license_id="CC-BY-4.0",
        resolved_license_id="LicenseRef-Siyavula-Unbranded-CCBY-Version-Conflict",
        catalogue_evidence_root_sha256=(
            "e8e18ccd3f7804aa6a430c939f3258235c976ef3687b1d4340106b27355664d2"
        ),
        terms_evidence_root_sha256=(
            "2677fd2952488fb873549efc3feade18212fd066e6173124de3a2a3a5a40277f"
        ),
        rights_subject_template_mismatch=rights_subject_template_mismatch,
    )


DIRECT_SOURCES = (
    DirectSourceSpec(
        source_id="wordnet_3_0",
        stages=("C1", "C2", "B23"),
        url="https://wordnetcode.princeton.edu/3.0/WordNet-3.0.tar.gz",
        filename="WordNet-3.0.tar.gz",
        media_type="application/x-gzip",
        expected_bytes=11_537_239,
        expected_etag='"b00b57-4384e6ed68640"',
        expected_last_modified="Wed, 22 Aug 2007 19:03:45 GMT",
        transfer_mode="fixed_range_chunks_v1",
        fixed_chunk_bytes=8_388_608,
        release_identity="Princeton_WordNet_3.0_2007-08-22",
        license_id="LicenseRef-WordNet-3.0",
        license_class="B",
        rights_proof="archive_LICENSE_plus_wordnet.princeton.edu/license-and-commercial-use",
        required_markers=(
            "Permission to use, copy, modify and distribute this software and database",
        ),
        selection_filter="English_database_dict_and_index_files_with_synset_gloss_relation_lineage",
        expected_sha256=(
            "640db279c949a88f61f851dd54ebbb22d003f8b90b85267042ef85a3781d3a52"
        ),
    ),
    DirectSourceSpec(
        source_id="usda_nalt_core_2024",
        stages=("C2", "B23", "C3"),
        url="https://lod.nal.usda.gov/downloads/nalt-core_dwn.ttl.zip",
        filename="nalt-core_dwn.ttl.zip",
        media_type="application/zip",
        expected_bytes=1_687_502,
        expected_etag='"19bfce-61e01c565bbf5"',
        expected_last_modified="Wed, 24 Jul 2024 17:40:15 GMT",
        transfer_mode="fixed_range_chunks_v1",
        fixed_chunk_bytes=8_388_608,
        release_identity=(
            "NALT_Core_2024_modified_2024-07-16_"
            "14196_concepts_14196_en_pref_19075_en_alt_0_hidden_labels_"
            "exact_archive_sha256_"
            "32e33ef2397088e7a076e2864bb0de594be6f958ef8702bf4d72f01be8a1c66a"
        ),
        license_id="CC-BY-4.0",
        license_class="B",
        rights_proof="lod.nal.usda.gov/nalt-core/en_metadata_and_embedded_RDF_license",
        required_markers=(
            "creativecommons.org/licenses/by/4.0",
            "nalt-core",
        ),
        selection_filter=(
            "English_NALT_Core_concepts_only_with_2024_authority_counts_"
            "excluding_taxon_only_and_geography_only_rows"
        ),
        expected_sha256=(
            "32e33ef2397088e7a076e2864bb0de594be6f958ef8702bf4d72f01be8a1c66a"
        ),
    ),
    DirectSourceSpec(
        source_id="gene_ontology_go_basic_2026_06_19",
        stages=("C3",),
        url="https://release.geneontology.org/2026-06-19/ontology/go-basic.obo",
        filename="go-basic.obo",
        media_type="text/obo",
        expected_bytes=32_215_811,
        expected_etag='"e08da9e04e0f8e26822b8e0212207a64-4"',
        expected_last_modified="Fri, 26 Jun 2026 23:12:03 GMT",
        transfer_mode="fixed_range_chunks_v1",
        fixed_chunk_bytes=8_388_608,
        release_identity=(
            "GO_official_release_2026-06-19_DOI_10.5281/zenodo.20943148_"
            "ontology_data_version_2026-06-15"
        ),
        license_id="CC-BY-4.0",
        license_class="B",
        rights_proof="release_metadata_DOI_and_ontology_terms_license",
        required_markers=(
            "data-version: releases/2026-06-15",
            "terms:license http://creativecommons.org/licenses/by/4.0/",
        ),
        selection_filter="non_obsolete_GO_terms_with_definition_and_acyclic_go_basic_prerequisites",
        expected_sha256=(
            "c72fc198a86983d55e43aac585d1ffdbeb6e3601475b3f18b6045acdc0a0734c"
        ),
        conditional_lock_mode=(
            "dated_release_pre_get_post_identity_server_ignores_conditionals"
        ),
    ),
    DirectSourceSpec(
        source_id="chebi_release_252_three_star",
        stages=("C3",),
        url="https://ftp.ebi.ac.uk/pub/databases/chebi/archive/rel252/ontology/chebi.obo",
        filename="chebi-252.obo",
        media_type="text/obo",
        expected_bytes=259_560_362,
        expected_etag='"f7893aa-650c397c9a420"',
        expected_last_modified="Fri, 01 May 2026 15:54:15 GMT",
        transfer_mode="fixed_range_chunks_v1",
        fixed_chunk_bytes=8_388_608,
        release_identity=(
            "ChEBI_ontology_release_252_data_version_252_2026-05-01T16:42_three_STAR"
        ),
        license_id="CC-BY-4.0",
        license_class="B",
        rights_proof=(
            "embedded_CC_BY_4_ontology_terms_license_plus_official_rights_"
            "with_README_CC_BY_SA_wording_discrepancy_recorded"
        ),
        required_markers=(
            "data-version: 252",
            "terms:license https://creativecommons.org/licenses/by/4.0/",
        ),
        selection_filter="subset_3_STAR_with_definition_non_obsolete_and_resolved_parent_chain",
        expected_sha256=(
            "f7072fac790ad20332991c622a4dadd5a6c4f18d5b470481991966b4f78dde83"
        ),
        payload_rights_evidence=(
            PayloadRightsEvidenceSpec(
                locator_kind="direct_prefix",
                locator="chebi-252.obo",
                byte_offset=0,
                byte_length=1_392,
                sha256="e36272c2e15176c950125936ba19ce7fcc96d4ba53a10b4af67cb497bfcdadd7",
                license_id="CC-BY-4.0",
                required_markers=(
                    "data-version: 252",
                    "terms:license https://creativecommons.org/licenses/by/4.0/",
                ),
            ),
        ),
        external_rights_evidence=(
            ExternalRightsEvidenceSpec(
                evidence_id="chebi_rel252_archived_README",
                locator=(
                    "https://ftp.ebi.ac.uk/pub/databases/chebi/archive/"
                    "rel252/ontology/README"
                ),
                sha256="c507a71af255020b633c5fac3e7ff74c2a0441709a390b77cfba864ed81d7356",
                byte_count=4_329,
                canonicalization="raw_bytes",
                observed_license_id="LicenseRef-ChEBI-README-CC-BY-SA-4.0-wording",
            ),
            ExternalRightsEvidenceSpec(
                evidence_id="chebi_rel252_archived_LICENSE",
                locator=(
                    "https://ftp.ebi.ac.uk/pub/databases/chebi/archive/"
                    "rel252/ontology/LICENSE"
                ),
                sha256="fe7b4ce83b8381cc5b216bbb4af73c570688d1b819c73bbaed8ca401f4677cd6",
                byte_count=18_655,
                canonicalization="raw_bytes",
                observed_license_id="CC-BY-4.0",
            ),
            ExternalRightsEvidenceSpec(
                evidence_id="chebi_rel252_rights_evidence_envelope",
                locator="urn:cur0s:rights-evidence:chebi-rel252-v1",
                sha256="d0e8ce9aafc3ccde332d53956c2e6eee08d9914638872b588a3b20322a7bef64",
                byte_count=None,
                canonicalization="cur0s_chebi_rights_evidence_envelope_canonical_json_v1",
                observed_license_id="CC-BY-4.0",
            ),
        ),
    ),
    DirectSourceSpec(
        source_id="envo_v2026_06_26",
        stages=("C3",),
        url=(
            "https://raw.githubusercontent.com/EnvironmentOntology/envo/"
            "a2455d1a77e46bb8a664d65a157166b539269042/envo.obo"
        ),
        filename="envo-a2455d1.obo",
        media_type="text/plain; charset=utf-8",
        expected_bytes=2_922_713,
        expected_etag='"6e8ab0e84affbb67c0cc24505588efca9f00e4ee7118569f1c104239e9c617ad"',
        expected_last_modified=None,
        transfer_mode="fixed_range_chunks_v1",
        fixed_chunk_bytes=8_388_608,
        release_identity="ENVO_v2026-06-26_commit_a2455d1a77e46bb8a664d65a157166b539269042",
        license_id="CC0-1.0",
        license_class="A",
        rights_proof="commit_bound_ontology_terms_license_and_repository_LICENSE",
        required_markers=(
            "data-version: releases/2026-06-26",
            "terms:license https://creativecommons.org/publicdomain/zero/1.0/",
        ),
        selection_filter="ENVO_namespace_terms_with_definition_non_obsolete_and_resolved_parent_chain",
        expected_sha256=(
            "7f5a6580d1b59166da07a54f9aa907a76f86079b7082e089192f04df91fd7d5b"
        ),
    ),
    DirectSourceSpec(
        source_id="usgs_thesaurus_2023_11_02",
        stages=("C2", "B23", "C3"),
        url="https://apps.usgs.gov/thesaurus/download/USGSThesaurus.rdf",
        filename="USGSThesaurus.rdf",
        media_type="application/rdf+xml",
        expected_bytes=1_062_937,
        expected_etag='"103819-60944d2017180"',
        expected_last_modified="Fri, 03 Nov 2023 19:50:46 GMT",
        transfer_mode="fixed_range_chunks_v1",
        fixed_chunk_bytes=8_388_608,
        release_identity="USGS_Thesaurus_dc_date_2023-11-02",
        license_id="LicenseRef-US-PD-USGS",
        license_class="A",
        rights_proof="embedded_dc_rights_Public_domain_USGS_government_source",
        required_markers=(
            '<dc:rights xml:lang="en">Public domain</dc:rights>',
            "<dc:date rdf:datatype=",
            ">2023-11-02</dc:date>",
        ),
        selection_filter="scientific_sciences_topics_methods_concepts_with_scope_notes",
        expected_sha256=(
            "2261c48206395f20b62f7cbad8ceaa659d1a41c83b0d13f7dbb11b4c39f5fa0e"
        ),
    ),
    DirectSourceSpec(
        source_id="siyavula_mathematics_grade_10_cc_by",
        stages=("C4",),
        url=(
            "https://www.siyavula.com/downloads/books/maths/"
            "Gr10_Mathematics_Learner_Eng_CC-BY.epub"
        ),
        filename="Gr10_Mathematics_Learner_Eng_CC-BY.epub",
        media_type="application/epub+zip",
        expected_bytes=49_009_925,
        expected_etag='"8bc76385d940a36dd75b9f9acd6a970c-3"',
        expected_last_modified="Fri, 26 Jun 2026 16:57:48 GMT",
        transfer_mode="fixed_range_chunks_v1",
        fixed_chunk_bytes=8_388_608,
        release_identity=(
            "Siyavula_Grade10_Mathematics_unbranded_CC_BY_version_conflict_"
            "exact_EPUB_2026-06-26"
        ),
        license_id="LicenseRef-Siyavula-Unbranded-CCBY-Version-Conflict",
        license_class="B",
        rights_proof=(
            "catalogue_CC_BY_3_plus_exact_artifact_notice_CC_BY_4_"
            "commercial_derivative_permission_invariant"
        ),
        required_markers=(
            "http://creativecommons.org/licenses/by/4.0/",
            "Siyavula",
        ),
        selection_filter=(
            "English_unbranded_quantitative_prerequisites_with_"
            "required_visual_context_quarantined"
        ),
        expected_sha256=(
            "881f0968936e797a6f0fa4df305b92641c52add3812871ae39a791c2ee1e4a99"
        ),
        epub_identity=_siyavula_epub_identity(
            stem="maths10",
            opf_sha256="76037874841fa5bc9d2ebebec6a1d211480a73ae1361766dba895112f48a2946",
            navigation_sha256="247a1747aad98905c48f05ed9e958e8334e4df991ae55754542cfec186a009e6",
            rights_sha256="727e17c81eb0eaa2a5020a1bda4ba8a66d2a1f9cf54ffb57e0e0da21429c4736",
            identifier="www.siyavula.com.epubmaker.maths10",
            modified="2015-09-15T13:22:49Z",
            catalogue_subject="Mathematics",
            catalogue_grade=10,
            filename_subject_token="Mathematics",
            filename_grade_token="Gr10",
            rights_subject_template_mismatch=True,
        ),
    ),
    DirectSourceSpec(
        source_id="siyavula_mathematics_grade_11_cc_by",
        stages=("C4",),
        url=(
            "https://www.siyavula.com/downloads/books/maths/"
            "Gr11_Mathematics_Learner_Eng_CC-BY.epub"
        ),
        filename="Gr11_Mathematics_Learner_Eng_CC-BY.epub",
        media_type="application/epub+zip",
        expected_bytes=34_751_539,
        expected_etag='"9f8bcfbe8eec4cedafbbfe5a13be79ef-3"',
        expected_last_modified="Fri, 26 Jun 2026 16:57:17 GMT",
        transfer_mode="fixed_range_chunks_v1",
        fixed_chunk_bytes=8_388_608,
        release_identity=(
            "Siyavula_Grade11_Mathematics_unbranded_CC_BY_version_conflict_"
            "exact_EPUB_2026-06-26"
        ),
        license_id="LicenseRef-Siyavula-Unbranded-CCBY-Version-Conflict",
        license_class="B",
        rights_proof=(
            "catalogue_CC_BY_3_plus_exact_artifact_notice_CC_BY_4_"
            "commercial_derivative_permission_invariant"
        ),
        required_markers=(
            "http://creativecommons.org/licenses/by/4.0/",
            "Siyavula",
        ),
        selection_filter=(
            "English_unbranded_quantitative_prerequisites_with_"
            "required_visual_context_quarantined"
        ),
        expected_sha256=(
            "45be47abfdb209bad368522c49643dc431d285d6b0a8261da55d0b597c7db807"
        ),
        epub_identity=_siyavula_epub_identity(
            stem="maths11",
            opf_sha256="a363428af32adb061cfa901c273e103e0c174397253fbf62ac6ac2fe9eabf61c",
            navigation_sha256="401ec25a8a42c8a2811ead263badf6a663360bcef67c322b7c66c209aa93f3ba",
            rights_sha256="83a58874939c94e42051258f624dd51663505eb407e504c24a482a2cb12b9740",
            identifier="www.siyavula.com.epubmaker.maths11",
            modified="2015-09-10T08:33:22Z",
            catalogue_subject="Mathematics",
            catalogue_grade=11,
            filename_subject_token="Mathematics",
            filename_grade_token="Gr11",
        ),
    ),
    DirectSourceSpec(
        source_id="siyavula_mathematics_grade_12_cc_by",
        stages=("C4",),
        url=(
            "https://www.siyavula.com/downloads/books/maths/"
            "Gr12_Mathematics_Learner_Eng_CC-BY.epub"
        ),
        filename="Gr12_Mathematics_Learner_Eng_CC-BY.epub",
        media_type="application/epub+zip",
        expected_bytes=40_361_251,
        expected_etag='"604c42c5c20042a278360f033499fea2-3"',
        expected_last_modified="Fri, 26 Jun 2026 16:57:26 GMT",
        transfer_mode="fixed_range_chunks_v1",
        fixed_chunk_bytes=8_388_608,
        release_identity=(
            "Siyavula_Grade12_Mathematics_unbranded_CC_BY_version_conflict_"
            "exact_EPUB_2026-06-26"
        ),
        license_id="LicenseRef-Siyavula-Unbranded-CCBY-Version-Conflict",
        license_class="B",
        rights_proof=(
            "catalogue_CC_BY_3_plus_exact_artifact_notice_CC_BY_4_"
            "commercial_derivative_permission_invariant"
        ),
        required_markers=(
            "http://creativecommons.org/licenses/by/4.0/",
            "Siyavula",
        ),
        selection_filter=(
            "English_unbranded_quantitative_prerequisites_with_"
            "required_visual_context_quarantined"
        ),
        expected_sha256=(
            "0d7554f2d0df805133f3be38a3a5ffe20e5963fd5318e40e77c63490a413adc8"
        ),
        epub_identity=_siyavula_epub_identity(
            stem="maths12",
            opf_sha256="f1d27a2cc1bed2d78c6dcb4ce8b932221636f18856c9e72b8e4743904d0ade79",
            navigation_sha256="6bad30d26289adc95f3547738700dc1eb372d7948b70989d48fccf3e90a8c3b0",
            rights_sha256="fb64024763ec78129e91cc6f9abc752b655e6a1be4f08e0fb2cd969dfb978ebe",
            identifier="www.siyavula.com.epubmaker.maths12",
            modified="2015-09-10T13:29:12Z",
            catalogue_subject="Mathematics",
            catalogue_grade=12,
            filename_subject_token="Mathematics",
            filename_grade_token="Gr12",
        ),
    ),
    DirectSourceSpec(
        source_id="siyavula_physical_sciences_grade_10_cc_by",
        stages=("C4",),
        url=(
            "https://www.siyavula.com/downloads/books/science/"
            "Gr10_PhysicalSciences_Learner_Eng_CC-BY.epub"
        ),
        filename="Gr10_PhysicalSciences_Learner_Eng_CC-BY.epub",
        media_type="application/epub+zip",
        expected_bytes=31_675_351,
        expected_etag='"11e81361d79ff4a7370bb90d4c2704bd-2"',
        expected_last_modified="Fri, 26 Jun 2026 16:57:29 GMT",
        transfer_mode="fixed_range_chunks_v1",
        fixed_chunk_bytes=8_388_608,
        release_identity=(
            "Siyavula_Grade10_Physical_Sciences_unbranded_CC_BY_version_"
            "conflict_exact_EPUB_2026-06-26"
        ),
        license_id="LicenseRef-Siyavula-Unbranded-CCBY-Version-Conflict",
        license_class="B",
        rights_proof=(
            "catalogue_CC_BY_3_plus_exact_artifact_notice_CC_BY_4_"
            "commercial_derivative_permission_invariant"
        ),
        required_markers=(
            "http://creativecommons.org/licenses/by/4.0/",
            "Siyavula",
        ),
        selection_filter="English_unbranded_text_sections_with_required_visual_context_quarantined",
        expected_sha256=(
            "366c2f0beb5d3c4cf0789e0dc49cd12dd07c20d47cd5c9e3e4dc5d1ca49ce3db"
        ),
        epub_identity=_siyavula_epub_identity(
            stem="science10",
            opf_sha256="5731fc2c134970256f34ffcd0c554190308cef91aaa5facd0d17608a109e9e3e",
            navigation_sha256="c7ac4d5c3d697451522ccd82d33c290913d4e187c532cb1805a488ccf9f0aace",
            rights_sha256="727e17c81eb0eaa2a5020a1bda4ba8a66d2a1f9cf54ffb57e0e0da21429c4736",
            identifier="www.siyavula.com.epubmaker.science10",
            modified="2015-09-10T19:50:07Z",
            catalogue_subject="Physical Sciences",
            catalogue_grade=10,
            filename_subject_token="PhysicalSciences",
            filename_grade_token="Gr10",
        ),
    ),
    DirectSourceSpec(
        source_id="siyavula_physical_sciences_grade_11_cc_by",
        stages=("C4",),
        url=(
            "https://www.siyavula.com/downloads/books/science/"
            "Gr11_PhysicalSciences_Learner_Eng_CC-BY.epub"
        ),
        filename="Gr11_PhysicalSciences_Learner_Eng_CC-BY.epub",
        media_type="application/epub+zip",
        expected_bytes=47_417_044,
        expected_etag='"dc57cdc3110e200afcb325a3070de995-3"',
        expected_last_modified="Fri, 26 Jun 2026 16:57:49 GMT",
        transfer_mode="fixed_range_chunks_v1",
        fixed_chunk_bytes=8_388_608,
        release_identity=(
            "Siyavula_Grade11_Physical_Sciences_unbranded_CC_BY_version_"
            "conflict_exact_EPUB_2026-06-26"
        ),
        license_id="LicenseRef-Siyavula-Unbranded-CCBY-Version-Conflict",
        license_class="B",
        rights_proof=(
            "catalogue_CC_BY_3_plus_exact_artifact_notice_CC_BY_4_"
            "commercial_derivative_permission_invariant"
        ),
        required_markers=(
            "http://creativecommons.org/licenses/by/4.0/",
            "Siyavula",
        ),
        selection_filter="English_unbranded_text_sections_with_required_visual_context_quarantined",
        expected_sha256=(
            "3d893a4364f52efe1991360302cfccb06030e03ad67d725867fb48f0f177a0f9"
        ),
        epub_identity=_siyavula_epub_identity(
            stem="science11",
            opf_sha256="64e49889777b68346c6a1ac227fa80d372a48a4a803f8a10e294a0f6af44e00a",
            navigation_sha256="a545b65cd1838badb7af2fe409481efe7581ab8416e271d91302d13278a2676b",
            rights_sha256="b0ee91d23afb156b3ab3a0b3e98c122fd5d0b37537231d2be1a24d4257ccb936",
            identifier="www.siyavula.com.epubmaker.science11",
            modified="2015-09-10T17:40:11Z",
            catalogue_subject="Physical Sciences",
            catalogue_grade=11,
            filename_subject_token="PhysicalSciences",
            filename_grade_token="Gr11",
        ),
    ),
)


_OPENSTAX_PATHS = ("LICENSE", "README.md", "META-INF", "collections", "modules")


GIT_SOURCES = (
    GitSourceSpec(
        source_id="openstax_biology_bundle_pre_transition",
        stages=("C4",),
        repository="openstax/osbooks-biology-bundle",
        commit_sha="4460012626ee747bdb9db8c4418317798fbc67ce",
        tree_sha="f09b4ae56f850e5c287d6971ffb11d99da61856c",
        selected_paths=_OPENSTAX_PATHS,
        selected_file_count=580,
        selected_bytes=15_495_336,
        license_id="CC-BY-4.0",
        license_class="B",
        license_sha256="0ff174546cbe3dd1287da231f9796618ac2f6e6595b2d11f567b2c9790f64868",
        rights_proof="commit_bound_LICENSE_before_2026_OpenStax_license_transition",
        selection_filter="CNXML_modules_collections_metadata_without_media_binary_admission",
    ),
    GitSourceSpec(
        source_id="openstax_chemistry_bundle_pre_transition",
        stages=("C4",),
        repository="openstax/osbooks-chemistry-bundle",
        commit_sha="9928441ef0badc3ff024c6a1fe2842c0048ea858",
        tree_sha="937b9e2e8a8479d7f60c32db4ebecbbd4c010e91",
        selected_paths=_OPENSTAX_PATHS,
        selected_file_count=181,
        selected_bytes=9_065_951,
        license_id="CC-BY-4.0",
        license_class="B",
        license_sha256="0ff174546cbe3dd1287da231f9796618ac2f6e6595b2d11f567b2c9790f64868",
        rights_proof="commit_bound_LICENSE_before_2026_OpenStax_license_transition",
        selection_filter="CNXML_modules_collections_metadata_without_media_binary_admission",
    ),
    GitSourceSpec(
        source_id="openstax_university_physics_bundle_pre_transition",
        stages=("C4",),
        repository="openstax/osbooks-university-physics-bundle",
        commit_sha="9364cbc32511afea3d4695e70a88687ffc1a3696",
        tree_sha="9cd4a12b01ebcb58c891e43e7a30f70ffb200c63",
        selected_paths=_OPENSTAX_PATHS,
        selected_file_count=328,
        selected_bytes=15_385_592,
        license_id="CC-BY-4.0",
        license_class="B",
        license_sha256="38a27c0f017da132e9a04ec8be91ead41cf8a55d85018c2de50c2b831dcfac38",
        rights_proof="commit_bound_LICENSE_before_2026_OpenStax_license_transition",
        selection_filter="CNXML_modules_collections_metadata_without_media_binary_admission",
    ),
    GitSourceSpec(
        source_id="openstax_astronomy_pre_transition",
        stages=("C4",),
        repository="openstax/osbooks-astronomy",
        commit_sha="9d7e69a2e0c9a651ad42254b9a93b701a6b08c10",
        tree_sha="aadd140722b936185ebbb633e83d0b22681788a2",
        selected_paths=_OPENSTAX_PATHS,
        selected_file_count=203,
        selected_bytes=4_674_481,
        license_id="CC-BY-4.0",
        license_class="B",
        license_sha256="0ff174546cbe3dd1287da231f9796618ac2f6e6595b2d11f567b2c9790f64868",
        rights_proof="commit_bound_LICENSE_before_2026_OpenStax_license_transition",
        selection_filter="CNXML_modules_collections_metadata_without_media_binary_admission",
    ),
    GitSourceSpec(
        source_id="openstax_anatomy_physiology_pre_transition",
        stages=("C4",),
        repository="openstax/osbooks-anatomy-physiology",
        commit_sha="3f855aef2941c1da9c01db904d45b129e26106f2",
        tree_sha="2c5a9dc2b84bf2aadb5fb0f0c43dfb0d052f3063",
        selected_paths=_OPENSTAX_PATHS,
        selected_file_count=202,
        selected_bytes=5_351_241,
        license_id="CC-BY-4.0",
        license_class="B",
        license_sha256="0ff174546cbe3dd1287da231f9796618ac2f6e6595b2d11f567b2c9790f64868",
        rights_proof="commit_bound_LICENSE_before_2026_OpenStax_license_transition",
        selection_filter="CNXML_modules_collections_metadata_without_media_binary_admission",
    ),
)


HARD_REJECTS = (
    {
        "source_id": "siyavula_physical_sciences_grade_12_cc_by",
        "disposition": "quarantine_transport_incomplete_internal_identity_unverified",
        "reason": (
            "bounded_exact_object_fetch_ended_at_69598652_of_78477236_bytes_"
            "without_full_SHA_OPF_navigation_or_rights_identity"
        ),
    },
    {
        "source_id": "qasc_as_C4_COM",
        "disposition": "rejected_for_C4_COM",
        "reason": "question_set_not_prerequisite_ordered_syllabus",
    },
    {
        "source_id": "openbookqa",
        "disposition": "rejected",
        "reason": "upstream_training_and_redistribution_rights_not_admitted",
    },
    {
        "source_id": "openstax_current_main",
        "disposition": "rejected",
        "reason": "post_transition_NC_SA_and_LLM_ingestion_restriction_not_commercial_eligible",
    },
    {
        "source_id": "nasa_gcmd_definitions",
        "disposition": "rejected",
        "reason": "definition_reuse_rights_not_admitted_for_commercial_training",
    },
    {
        "source_id": "sciinstruct_and_OpenScienceReasoning2",
        "disposition": "rejected",
        "reason": "card_level_license_does_not_close_upstream_provenance_or_target_semantics",
    },
    {
        "source_id": "MegaScience_TextbookReasoning_and_MegaScience",
        "disposition": "C4_RX_only",
        "reason": "CC_BY_NC_SA_research_comparator_never_C4_COM_ingredient",
    },
    {
        "source_id": "chebi_lite",
        "disposition": "rejected_for_C3_dictionary",
        "reason": "lite_export_omits_authoritative_definitions",
    },
    {
        "source_id": "siyavula_branded_or_non_derivative_editions",
        "disposition": "rejected",
        "reason": "CC_BY_ND_not_admissible_for_training_derivatives",
    },
    {
        "source_id": "siyavula_corrupt_134_byte_catalog_endpoints",
        "disposition": "rejected",
        "reason": "not_valid_EPUB_content",
    },
    {
        "source_id": "unpinned_OpenStax_refs_or_generated_archives",
        "disposition": "rejected",
        "reason": "commit_tree_and_historical_license_identity_required",
    },
)


_COMMON_VERIFICATION_FIELDS = {
    "content_manifest_sha256",
    "identity_verified",
    "phone_private",
    "raw_fsynced",
    "rights_verified",
    "stage_binding_verified",
}
_DIRECT_VERIFICATION_FIELDS = _COMMON_VERIFICATION_FIELDS | {
    "conditional_lock_mode",
    "cryptographic_payload_identity_verified",
    "https_only",
    "license_markers_verified",
    "metadata_match",
    "observed_etag",
    "observed_final_url",
    "observed_last_modified",
    "observed_content_type",
    "observed_payload_rights_evidence",
    "path_safety_verified",
    "payload_rights_evidence_root_sha256",
    "pre_post_metadata_match",
    "rights_admission_basis",
    "structure_verified",
    "server_conditional_lock_enforced",
    "transport_conditionals_identity_role",
    "external_rights_evidence_used_for_admission",
}
_GIT_VERIFICATION_FIELDS = _COMMON_VERIFICATION_FIELDS | {
    "commit_verified",
    "cryptographic_payload_identity_verified",
    "license_verified",
    "observed_commit_sha",
    "observed_file_count",
    "observed_license_sha256",
    "observed_selected_bytes",
    "observed_tree_sha",
    "path_safety_verified",
    "symlink_policy_verified",
    "tree_verified",
    "worktree_clean",
}
_TRUE_VERIFICATION_FIELDS = {
    "commit_verified",
    "cryptographic_payload_identity_verified",
    "https_only",
    "identity_verified",
    "license_markers_verified",
    "license_verified",
    "metadata_match",
    "path_safety_verified",
    "phone_private",
    "pre_post_metadata_match",
    "raw_fsynced",
    "rights_verified",
    "stage_binding_verified",
    "structure_verified",
    "symlink_policy_verified",
    "tree_verified",
    "worktree_clean",
}


def canonical_json_bytes(value: Any) -> bytes:
    _validate_json_tree(value)
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _toolchain_artifact(
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
    literal_nlink: int = 1,
    elf_aarch64: bool = True,
) -> dict[str, Any]:
    """Build one closed, path-aware phone toolchain identity record."""

    literal_is_symlink = symlink_target is not None
    return {
        "literal_path": literal_path,
        "literal_entry_type": (
            "symbolic_link" if literal_is_symlink else "regular_file"
        ),
        "literal_mode": literal_mode or ("0777" if literal_is_symlink else mode),
        "literal_uid": uid if literal_uid is None else literal_uid,
        "literal_gid": gid if literal_gid is None else literal_gid,
        "literal_nlink": literal_nlink,
        "literal_symlink_target": symlink_target,
        "resolved_path": resolved_path,
        "resolved_entry_type": "regular_file",
        "resolved_mode": mode,
        "resolved_uid": uid,
        "resolved_gid": gid,
        "resolved_nlink": 1,
        "bytes": size,
        "sha256": "sha256:" + sha256,
        "elf_identity": (
            {
                "class_bits": 64,
                "data_encoding": "little_endian",
                "machine": "AArch64",
            }
            if elf_aarch64
            else None
        ),
    }


def phone_toolchain_contract() -> dict[str, Any]:
    """Return the exact pre-claim Termux/runtime identity admitted for this action."""

    prefix = "/data/data/com.termux/files/usr"
    empty_sha = "sha256:" + hashlib.sha256(b"").hexdigest()
    artifacts = {
        "android_bionic_libc": _toolchain_artifact(
            "/apex/com.android.runtime/lib64/bionic/libc.so",
            "/apex/com.android.runtime/lib64/bionic/libc.so",
            sha256="b4d95dc39a379dbe5049ce033f019b01a2f10dcf507562e83c72eef901d6ebcf",
            size=1_143_072,
            mode="0644",
            uid=1000,
            gid=1000,
        ),
        "android_bionic_libdl": _toolchain_artifact(
            "/system/lib64/libdl.so",
            "/apex/com.android.runtime/lib64/bionic/libdl.so",
            sha256="7abc47c96a4f49d52647e7f1d2045d3eb9ba4d9766c1d7f225e6aa229fa9f479",
            size=50_760,
            mode="0644",
            uid=1000,
            gid=1000,
            symlink_target="/apex/com.android.runtime/lib64/bionic/libdl.so",
            literal_mode="0644",
            literal_uid=0,
            literal_gid=0,
        ),
        "android_bionic_libm": _toolchain_artifact(
            "/system/lib64/libm.so",
            "/apex/com.android.runtime/lib64/bionic/libm.so",
            sha256="2a99c9ac7a12461663ec31b8d4ee3404ee99a1dca53f7c30b248bcccb155eefc",
            size=249_192,
            mode="0644",
            uid=1000,
            gid=1000,
            symlink_target="/apex/com.android.runtime/lib64/bionic/libm.so",
            literal_mode="0644",
            literal_uid=0,
            literal_gid=0,
        ),
        "android_linker64": _toolchain_artifact(
            "/system/bin/linker64",
            "/apex/com.android.runtime/bin/linker64",
            sha256="6aa1b8bcf1da7e8b48f67f78eebaa2d9356c76ad3c9809bd5576b579907d7f9e",
            size=2_160_952,
            mode="0755",
            uid=0,
            gid=2000,
            symlink_target="/apex/com.android.runtime/bin/linker64",
            literal_mode="0755",
        ),
        "android_getprop": _toolchain_artifact(
            "/system/bin/getprop",
            "/system/bin/toolbox",
            sha256="e336522f057ca8c094a24ecb467469313906d5eac62873b5e355e400fbe51600",
            size=153_016,
            mode="0755",
            uid=0,
            gid=2000,
            symlink_target="toolbox",
            literal_mode="0755",
        ),
        "system_launcher_env": _toolchain_artifact(
            "/system/bin/env",
            "/system/bin/toybox",
            sha256="a581d694b3d74f550d3bc896cf75ddda84a33f56f4e3ab47e06945ad3383c82d",
            size=577_184,
            mode="0755",
            uid=0,
            gid=2000,
            symlink_target="toybox",
            literal_mode="0755",
        ),
        "ca_certificate_bundle": _toolchain_artifact(
            f"{prefix}/etc/tls/cert.pem",
            f"{prefix}/etc/tls/cert.pem",
            sha256="86a1f3366afac7c6f8ae9f3c779ac221129328c43f0ab2b8817eb2f362a5025c",
            size=189_462,
            mode="0600",
            uid=10536,
            gid=10536,
            elf_aarch64=False,
        ),
        "curl": _toolchain_artifact(
            f"{prefix}/bin/curl",
            f"{prefix}/bin/curl",
            sha256="ae614749dea3653ec219919d852b1072030a0961de766610da21449f64a91624",
            size=274_936,
            mode="0700",
            uid=10536,
            gid=10536,
        ),
        "git": _toolchain_artifact(
            f"{prefix}/bin/git",
            f"{prefix}/libexec/git-core/git",
            sha256="2dde942b18b437eaeef9ca0db07f0d82494a38e8e5a67b52a38f87d7545c9a2a",
            size=3_358_136,
            mode="0700",
            uid=10536,
            gid=10536,
            symlink_target="../libexec/git-core/git",
        ),
        "git_https_helper": _toolchain_artifact(
            f"{prefix}/libexec/git-core/git-remote-https",
            f"{prefix}/libexec/git-core/git-remote-http",
            sha256="320acb049a76cc9758c185bc80cba339da25755d141ca0158eb83a8f1f67e021",
            size=1_940_504,
            mode="0700",
            uid=10536,
            gid=10536,
            symlink_target="git-remote-http",
        ),
        "launcher_env": _toolchain_artifact(
            f"{prefix}/bin/env",
            f"{prefix}/bin/coreutils",
            sha256="4dff3fb0faf37930e396439093989815113605a91bf80471e37399d2f9ffab01",
            size=1_245_744,
            mode="0700",
            uid=10536,
            gid=10536,
            symlink_target="coreutils",
        ),
        "libbz2": _toolchain_artifact(
            f"{prefix}/lib/libbz2.so.1.0.8",
            f"{prefix}/lib/libbz2.so.1.0.8",
            sha256="5129a738fec8c6733954fa6a98f1fad9538e818f38db89d5391f12e5657746dc",
            size=50_328,
            mode="0600",
            uid=10536,
            gid=10536,
        ),
        "libcrypto": _toolchain_artifact(
            f"{prefix}/lib/libcrypto.so.3",
            f"{prefix}/lib/libcrypto.so.3",
            sha256="28534a11feb019f149032374c88d1c52f87baa241bc9ee7ab0bb1f3d24d21118",
            size=4_611_704,
            mode="0700",
            uid=10536,
            gid=10536,
        ),
        "libexpat": _toolchain_artifact(
            f"{prefix}/lib/libexpat.so.1.12.1",
            f"{prefix}/lib/libexpat.so.1.12.1",
            sha256="12af88ae36095de371d20c278a4438f253194d94eee83780e9f815ed4866e12f",
            size=134_800,
            mode="0700",
            uid=10536,
            gid=10536,
        ),
        "liblzma": _toolchain_artifact(
            f"{prefix}/lib/liblzma.so.5.8.3",
            f"{prefix}/lib/liblzma.so.5.8.3",
            sha256="f8ab7f7548a57222c1115274bd6ff10d08917ba0701c1b3892be5a12a8d506cf",
            size=157_112,
            mode="0700",
            uid=10536,
            gid=10536,
        ),
        "libandroid_posix_semaphore": _toolchain_artifact(
            f"{prefix}/lib/libandroid-posix-semaphore.so",
            f"{prefix}/lib/libandroid-posix-semaphore.so",
            sha256="adc7a3aa24f7e3baadc6149dea370bceeb11f058f19e22d8ca46e19f19e9e803",
            size=7_136,
            mode="0600",
            uid=10536,
            gid=10536,
        ),
        "libcurl": _toolchain_artifact(
            f"{prefix}/lib/libcurl.so",
            f"{prefix}/lib/libcurl.so",
            sha256="d654a8face01e897871d99a636d89e3c25dfcc0e2500f4ffe22e455984eb443c",
            size=884_688,
            mode="0700",
            uid=10536,
            gid=10536,
        ),
        "libpcre2": _toolchain_artifact(
            f"{prefix}/lib/libpcre2-8.so",
            f"{prefix}/lib/libpcre2-8.so",
            sha256="7a72db73181e80c311fcc0302833690044c958502a14dea50f5788038e661ced",
            size=489_384,
            mode="0700",
            uid=10536,
            gid=10536,
        ),
        "libnghttp2": _toolchain_artifact(
            f"{prefix}/lib/libnghttp2.so",
            f"{prefix}/lib/libnghttp2.so",
            sha256="75f4514179c2f4e57ba1f1ff01dfc1ee49f83828bf83259ad84ed840c1d41d67",
            size=154_080,
            mode="0700",
            uid=10536,
            gid=10536,
        ),
        "libnghttp3": _toolchain_artifact(
            f"{prefix}/lib/libnghttp3.so",
            f"{prefix}/lib/libnghttp3.so",
            sha256="d8a05e811b2fbf23fb48400a0f21e79ec5b3eec1126e67e1833f8bace3ff038e",
            size=149_504,
            mode="0700",
            uid=10536,
            gid=10536,
        ),
        "libngtcp2": _toolchain_artifact(
            f"{prefix}/lib/libngtcp2.so",
            f"{prefix}/lib/libngtcp2.so",
            sha256="a12fc16d01ea00f0e94c59b8271df75dbd4b0a174ed5af1f7b9f7ae95a8c1158",
            size=342_128,
            mode="0600",
            uid=10536,
            gid=10536,
        ),
        "libngtcp2_crypto_ossl": _toolchain_artifact(
            f"{prefix}/lib/libngtcp2_crypto_ossl.so",
            f"{prefix}/lib/libngtcp2_crypto_ossl.so",
            sha256="7dbe51f07d80a4385171ea44a96e2a46f80c827da897cda23dbe8978100082c8",
            size=43_616,
            mode="0600",
            uid=10536,
            gid=10536,
        ),
        "libpython": _toolchain_artifact(
            f"{prefix}/lib/libpython3.13.so",
            f"{prefix}/lib/libpython3.13.so",
            sha256="7ca4f4f00ae2e1afde50bb3ce01926ec6edb582719c7731a416235833d4d2319",
            size=5_153_728,
            mode="0700",
            uid=10536,
            gid=10536,
        ),
        "libssl": _toolchain_artifact(
            f"{prefix}/lib/libssl.so.3",
            f"{prefix}/lib/libssl.so.3",
            sha256="9197a4a8bfb4239ee0c0fc475c2704cdb655caed2593863ef125808a3f3e75e8",
            size=816_264,
            mode="0700",
            uid=10536,
            gid=10536,
        ),
        "libssh2": _toolchain_artifact(
            f"{prefix}/lib/libssh2.so",
            f"{prefix}/lib/libssh2.so",
            sha256="3e72aa886e7a273bb3081bddda195144b5ce3c112e52d10417acd8315728e840",
            size=247_520,
            mode="0600",
            uid=10536,
            gid=10536,
        ),
        "libtermux_exec": _toolchain_artifact(
            f"{prefix}/lib/libtermux-exec.so",
            f"{prefix}/lib/libtermux-exec.so",
            sha256="45ad0183d4fdb399ce5df0823b1d67b53a01bbb2596c7e4db79b7c255214c9c8",
            size=13_808,
            mode="0700",
            uid=10536,
            gid=10536,
        ),
        "libz": _toolchain_artifact(
            f"{prefix}/lib/libz.so.1",
            f"{prefix}/lib/libz.so.1.3.2",
            sha256="6d1a271adb9864fd66d696c746eac7a43faaa158b1370d32774ef73f1fe799ef",
            size=72_232,
            mode="0700",
            uid=10536,
            gid=10536,
            symlink_target="libz.so.1.3.2",
        ),
        "python": _toolchain_artifact(
            f"{prefix}/bin/python",
            f"{prefix}/bin/python3.13",
            sha256="1d3987c39c03b764d629a8c8c6fdc5979d8f8e28beb7193f312fc39d63b70404",
            size=4_728,
            mode="0700",
            uid=10536,
            gid=10536,
            symlink_target="python3.13",
        ),
        "system_libcxx": _toolchain_artifact(
            "/system/lib64/libc++.so",
            "/system/lib64/libc++.so",
            sha256="794eb8fafd7be35da3725e9ec0b15189c6f4f2544f5b78afd8a647dde5b69195",
            size=1_083_168,
            mode="0644",
            uid=0,
            gid=0,
        ),
        "system_libbase": _toolchain_artifact(
            "/system/lib64/libbase.so",
            "/system/lib64/libbase.so",
            sha256="7e5fc96fcb4ec246b125609771fc458981eeafc8274079491dd0d25b15bb4d98",
            size=218_928,
            mode="0644",
            uid=0,
            gid=0,
        ),
        "system_liblog": _toolchain_artifact(
            "/system/lib64/liblog.so",
            "/system/lib64/liblog.so",
            sha256="b9d6a5f515686068e0a66d3d56c248701745f59273b20051a62bec4d44bedd9e",
            size=101_848,
            mode="0644",
            uid=0,
            gid=0,
        ),
        "system_libnetd_client": _toolchain_artifact(
            "/system/lib64/libnetd_client.so",
            "/system/lib64/libnetd_client.so",
            sha256="d4aedc713a2d6f06214faa6c27ea333909a685a717d12b5a750d134ec4733c89",
            size=52_368,
            mode="0644",
            uid=0,
            gid=0,
        ),
    }
    base_environment = {
        "ANDROID_ROOT": "/system",
        "HOME": "/data/data/com.termux/files/home",
        "LC_ALL": "C",
        "PATH": f"{prefix}/bin:/system/bin",
    }
    git_environment = {
        **base_environment,
        "GIT_ASKPASS": "/system/bin/false",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_EXEC_PATH": f"{prefix}/libexec/git-core",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
        "LD_PRELOAD": f"{prefix}/lib/libtermux-exec.so",
    }
    probes = {
        "android_getprop_build_fingerprint": {
            "argv": ["/system/bin/getprop", "ro.build.fingerprint"],
            "environment": "base",
            "returncode": 0,
            "stdout_bytes": 77,
            "stdout_sha256": "sha256:fce358a6cdd6535afbecf6f72088412abaccf9b9902c05800ee8852512f9882f",
            "stderr_bytes": 0,
            "stderr_sha256": empty_sha,
        },
        "android_getprop_device": {
            "argv": ["/system/bin/getprop", "ro.product.device"],
            "environment": "base",
            "returncode": 0,
            "stdout_bytes": 7,
            "stdout_sha256": "sha256:507a644a157efb845902e2b6d57c67329f0c6d5fadfb0a66c258cb0742a13844",
            "stderr_bytes": 0,
            "stderr_sha256": empty_sha,
        },
        "android_getprop_model": {
            "argv": ["/system/bin/getprop", "ro.product.model"],
            "environment": "base",
            "returncode": 0,
            "stdout_bytes": 7,
            "stdout_sha256": "sha256:507a644a157efb845902e2b6d57c67329f0c6d5fadfb0a66c258cb0742a13844",
            "stderr_bytes": 0,
            "stderr_sha256": empty_sha,
        },
        "android_getprop_soc": {
            "argv": ["/system/bin/getprop", "ro.soc.model"],
            "environment": "base",
            "returncode": 0,
            "stdout_bytes": 7,
            "stdout_sha256": "sha256:7a52eeeb3376893cd5274bee778140e99f00191a5af661a975d2e263196b1316",
            "stderr_bytes": 0,
            "stderr_sha256": empty_sha,
        },
        "android_env_i_empty_environment": {
            "argv": ["/system/bin/env", "-i", "/system/bin/env"],
            "environment": "base",
            "returncode": 0,
            "stdout_bytes": 0,
            "stdout_sha256": empty_sha,
            "stderr_bytes": 0,
            "stderr_sha256": empty_sha,
        },
        "curl_help_all": {
            "argv": [f"{prefix}/bin/curl", "--help", "all"],
            "environment": "base",
            "returncode": 0,
            "stdout_bytes": 18_068,
            "stdout_sha256": "sha256:8db162781e5adfcd1c0deba21942b86af41d1a51c3d4406ccfaddeb3f53261e9",
            "stderr_bytes": 0,
            "stderr_sha256": empty_sha,
        },
        "curl_version": {
            "argv": [f"{prefix}/bin/curl", "--version"],
            "environment": "base",
            "returncode": 0,
            "stdout_bytes": 415,
            "stdout_sha256": "sha256:b14c9742cebe03ba50b1d11719bf4e1dd4086289c94d12ae29721a3baa881f8e",
            "stderr_bytes": 0,
            "stderr_sha256": empty_sha,
        },
        "git_build_options": {
            "argv": [f"{prefix}/bin/git", "version", "--build-options"],
            "environment": "git",
            "returncode": 0,
            "stdout_bytes": 308,
            "stdout_sha256": "sha256:f0c8732bd8459bb2b1073683b03b74ef6af58ef821989bd51fdcc2ea90b9676b",
            "stderr_bytes": 0,
            "stderr_sha256": empty_sha,
        },
        "git_https_helper_exec": {
            "argv": [f"{prefix}/libexec/git-core/git-remote-https"],
            "environment": "git",
            "returncode": 1,
            "stdout_bytes": 0,
            "stdout_sha256": empty_sha,
            "stderr_bytes": 60,
            "stderr_sha256": "sha256:0fa693d5b131874cf65284c8ac91b47bbf0454b9774a430f29c50fe3f7beed9b",
        },
        "python_version": {
            "argv": [
                f"{prefix}/bin/python",
                "-IBS",
                "-X",
                "pycache_prefix=$RUN_SCOPED_PYCACHE_PREFIX",
                "--version",
            ],
            "environment": "base",
            "returncode": 0,
            "stdout_bytes": 15,
            "stdout_sha256": "sha256:6b64edf0fc8f22e798fb64873acba6b4106df290f0bf458b507e8cb409b63e49",
            "stderr_bytes": 0,
            "stderr_sha256": empty_sha,
        },
    }
    runner_mapping_artifact_roles = sorted(
        (
            "android_bionic_libc",
            "android_bionic_libdl",
            "android_bionic_libm",
            "android_linker64",
            "libandroid_posix_semaphore",
            "libbz2",
            "libcrypto",
            "libexpat",
            "liblzma",
            "libpython",
            "libtermux_exec",
            "libz",
            "python",
            "system_libcxx",
            "system_liblog",
            "system_libnetd_client",
        )
    )
    runner_extension_names = (
        "_bisect.cpython-313-aarch64-linux-android.so",
        "_blake2.cpython-313-aarch64-linux-android.so",
        "_bz2.cpython-313-aarch64-linux-android.so",
        "_datetime.cpython-313-aarch64-linux-android.so",
        "_elementtree.cpython-313-aarch64-linux-android.so",
        "_hashlib.cpython-313-aarch64-linux-android.so",
        "_json.cpython-313-aarch64-linux-android.so",
        "_lzma.cpython-313-aarch64-linux-android.so",
        "_opcode.cpython-313-aarch64-linux-android.so",
        "_posixsubprocess.cpython-313-aarch64-linux-android.so",
        "_random.cpython-313-aarch64-linux-android.so",
        "_struct.cpython-313-aarch64-linux-android.so",
        "binascii.cpython-313-aarch64-linux-android.so",
        "fcntl.cpython-313-aarch64-linux-android.so",
        "grp.cpython-313-aarch64-linux-android.so",
        "math.cpython-313-aarch64-linux-android.so",
        "pyexpat.cpython-313-aarch64-linux-android.so",
        "resource.cpython-313-aarch64-linux-android.so",
        "select.cpython-313-aarch64-linux-android.so",
        "zlib.cpython-313-aarch64-linux-android.so",
    )
    runner_extension_paths = sorted(
        f"{prefix}/lib/python3.13/lib-dynload/{name}"
        for name in runner_extension_names
    )
    runner_mapping_paths = sorted(
        [artifacts[role]["resolved_path"] for role in runner_mapping_artifact_roles]
        + runner_extension_paths
        + ["[vdso]"]
    )
    body = {
        "schema_version": PHONE_TOOLCHAIN_SCHEMA,
        "artifacts": artifacts,
        "environments": {"base": base_environment, "git": git_environment},
        "command_probes": probes,
        "python_stdlib_tree": {
            "root_path": f"{prefix}/lib/python3.13",
            "root_mode": "0700",
            "root_uid": 10536,
            "root_gid": 10536,
            "root_nlink": 38,
            "entry_count": 691,
            "regular_bytes": 16_922_387,
            "root_sha256": (
                "sha256:303f8e4b3a9a521cd88d5a2ed2c2312c5bdad135365a60dfb8110d441c1fa700"
            ),
            "canonicalization": (
                "sorted_relative_POSIX_paths_canonical_JSON_type_mode_"
                "regular_bytes_sha256_source_only_excluding_root_site_packages_"
                "all_pycache_and_pyc_reject_external_symlinks_root_excluded"
            ),
        },
        "python_runtime": {
            "sys_executable": f"{prefix}/bin/python",
            "base_executable": f"{prefix}/bin/python",
            "proc_self_exe": f"{prefix}/bin/python3.13",
            "prefix": prefix,
            "base_prefix": prefix,
            "exec_prefix": prefix,
            "base_exec_prefix": prefix,
            "initial_sys_path": [
                f"{prefix}/lib/python313.zip",
                f"{prefix}/lib/python3.13",
                f"{prefix}/lib/python3.13/lib-dynload",
            ],
            "absent_sys_path_entries": [f"{prefix}/lib/python313.zip"],
            "sanitized_sys_path": [
                f"{prefix}/lib/python3.13",
                f"{prefix}/lib/python3.13/lib-dynload",
            ],
            "sys_flags": {
                "isolated": 1,
                "no_site": 1,
                "no_user_site": 1,
                "ignore_environment": 1,
                "safe_path": True,
                "dont_write_bytecode": 1,
                "optimize": 0,
            },
            "launch_environment": {
                **base_environment,
                "CUR0S_NATIVE_ATTESTATION_FD": "4",
                "CUR0S_NATIVE_MANIFEST_FD": "5",
                "CUR0S_PREREGISTRATION_FD": "6",
                "LD_PRELOAD": f"{prefix}/lib/libtermux-exec.so",
                "TERMUX_EXEC__PROC_SELF_EXE": f"{prefix}/bin/python",
            },
            "executable_mapping_artifact_roles": runner_mapping_artifact_roles,
            "executable_mapping_stdlib_extension_paths": runner_extension_paths,
            "executable_mapping_expected_paths": runner_mapping_paths,
            "executable_mapping_expected_count": len(runner_mapping_paths),
            "unexpected_executable_file_mappings_forbidden": True,
            "loaded_module_origin_policy": {
                "admitted_extension_root": f"{prefix}/lib/python3.13/lib-dynload",
                "admitted_source_root": f"{prefix}/lib/python3.13",
                "sourceless_file_loader_forbidden": True,
                "stdlib_cached_bytecode_must_be_under_absent_pycache_prefix": True,
            },
            "pycache_prefix_policy": "run_scoped_verified_absent",
        },
        "curl_required_options": [
            "--max-filesize",
            "--max-redirs",
            "--proto",
            "--retry-all-errors",
        ],
        "git_https_child_exec_probe_network_access": False,
        "runner_python_flags": [
            "-IBS",
            "-X",
            "pycache_prefix=$RUN_SCOPED_PYCACHE_PREFIX",
        ],
        "attestation_timing": "before_candidate_preparation_and_execution_claim",
    }
    return {**body, "toolchain_root_sha256": canonical_sha256(body)}


def native_preflight_build_python_runtime_identity() -> dict[str, Any]:
    """Return the exact already-running Python file closure for the build driver."""

    toolchain = phone_toolchain_contract()
    artifact_roles = (
        "android_bionic_libc",
        "android_bionic_libdl",
        "android_bionic_libm",
        "android_linker64",
        "libandroid_posix_semaphore",
        "libbz2",
        "libcrypto",
        "liblzma",
        "libpython",
        "libtermux_exec",
        "libz",
        "python",
        "system_libcxx",
        "system_liblog",
        "system_libnetd_client",
    )
    artifacts = {
        role: {
            "bytes": toolchain["artifacts"][role]["bytes"],
            "gid": toolchain["artifacts"][role]["resolved_gid"],
            "mode": toolchain["artifacts"][role]["resolved_mode"],
            "nlink": toolchain["artifacts"][role]["resolved_nlink"],
            "path": toolchain["artifacts"][role]["resolved_path"],
            "sha256": toolchain["artifacts"][role]["sha256"],
            "uid": toolchain["artifacts"][role]["resolved_uid"],
        }
        for role in artifact_roles
    }
    return {
        "artifact_inputs": artifacts,
        "base_executable": f"{_TERMUX_PREFIX}/bin/python",
        "base_exec_prefix": _TERMUX_PREFIX,
        "base_prefix": _TERMUX_PREFIX,
        "exec_prefix": _TERMUX_PREFIX,
        "executable_mapping_artifact_roles": sorted(artifact_roles),
        "kernel_executable_mapping_boundary": ["[vdso]"],
        "launch_environment": dict(NATIVE_PREFLIGHT_BUILD_DRIVER_LAUNCH_ENVIRONMENT),
        "loaded_module_origin_policy": {
            "admitted_extension_root": (f"{_TERMUX_PREFIX}/lib/python3.13/lib-dynload"),
            "admitted_source_root": f"{_TERMUX_PREFIX}/lib/python3.13",
            "sourceless_file_loader_forbidden": True,
            "stdlib_cached_bytecode_must_be_under_absent_pycache_prefix": True,
        },
        "stdlib_executable_mapping_policy": (
            "exact_loaded_ExtensionFileLoader_origins_plus_manifest_bound_dependencies"
        ),
        "proc_self_exe": f"{_TERMUX_PREFIX}/bin/python3.13",
        "python_prefix": _TERMUX_PREFIX,
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
            f"{_TERMUX_PREFIX}/lib/python313.zip",
            f"{_TERMUX_PREFIX}/lib/python3.13",
            f"{_TERMUX_PREFIX}/lib/python3.13/lib-dynload",
        ],
        "stdlib_tree": dict(toolchain["python_stdlib_tree"]),
        "sys_executable": f"{_TERMUX_PREFIX}/bin/python",
        "unexpected_executable_file_mappings_forbidden": True,
    }


def native_preflight_execution_layout(
    run_id: str, source_commit: str
) -> dict[str, str]:
    """Return the only phone-private layout admitted for this one-shot action."""

    if _RUN_ID_RE.fullmatch(run_id) is None:
        raise CommercialSourceError("native_preflight_run_id_invalid")
    if SHA1_RE.fullmatch(source_commit) is None:
        raise CommercialSourceError("native_preflight_source_commit_invalid")
    action_root = (
        "/data/data/com.termux/files/home/polymath_gemma4_e4b_frontier/" + run_id
    )
    checkout_root = f"{action_root}/source/Polymath-AI-{source_commit}"
    return {
        "action_root": action_root,
        "candidate_output": f"{action_root}/candidate_runs/candidate-001",
        "checkout_root": checkout_root,
        "commercial_sources_path": (
            f"{checkout_root}/polymath_ai/corpus/cur0s_commercial_sources.py"
        ),
        "launch_envelope_path": f"{action_root}/native_launch_envelope.json",
        "manifest_path": f"{action_root}/native_preflight.manifest",
        "native_binary_path": f"{action_root}/cur0s_native_preflight",
        "preregistration_path": f"{action_root}/preregistration.json",
        "runner_path": (
            f"{checkout_root}/scripts/termux/run_cur0s_commercial_sources.py"
        ),
    }


def native_outer_launch_contract(layout: Mapping[str, str]) -> dict[str, Any]:
    """Freeze the exact shell-free plan that starts the native verifier.

    The two digest positions cannot contain their eventual literal values in the
    preregistration that they hash.  They are therefore typed derivations, not
    shell placeholders.  ``build_native_launch_envelope`` resolves them to one
    exact argv after both canonical payloads exist.
    """

    required_layout = {
        "launch_envelope_path",
        "manifest_path",
        "native_binary_path",
        "preregistration_path",
    }
    if not isinstance(layout, Mapping) or not required_layout <= set(layout):
        raise CommercialSourceError("native_outer_launch_layout_invalid")
    for field in required_layout:
        value = layout[field]
        if (
            not isinstance(value, str)
            or not value.startswith("/")
            or any(character in value for character in "\x00\r\n\t")
        ):
            raise CommercialSourceError("native_outer_launch_layout_invalid")
    if canonical_sha256(NATIVE_OUTER_ENVIRONMENT) != NATIVE_OUTER_ENVIRONMENT_SHA256:
        raise CommercialSourceError("native_outer_environment_constant_invalid")
    launcher_identity = phone_toolchain_contract()["artifacts"].get(
        "system_launcher_env"
    )
    if (
        not isinstance(launcher_identity, Mapping)
        or launcher_identity.get("literal_path") != "/system/bin/env"
        or launcher_identity.get("resolved_path") != "/system/bin/toybox"
        or launcher_identity.get("sha256")
        != "sha256:a581d694b3d74f550d3bc896cf75ddda84a33f56f4e3ab47e06945ad3383c82d"
    ):
        raise CommercialSourceError("native_outer_launcher_identity_invalid")
    argv_plan = [
        {"kind": "literal", "value": "/system/bin/env"},
        {"kind": "literal", "value": "-i"},
        {"kind": "literal", "value": layout["native_binary_path"]},
        {"kind": "literal", "value": "--launch"},
        {"kind": "literal", "value": "--manifest"},
        {"kind": "literal", "value": layout["manifest_path"]},
        {"kind": "literal", "value": "--manifest-sha256"},
        {"kind": "derived", "source": "native_manifest_bytes_sha256"},
        {
            "kind": "literal",
            "value": "--expected-preregistration-sha256",
        },
        {"kind": "derived", "source": "preregistration_bytes_sha256"},
    ]
    return {
        "schema_version": NATIVE_LAUNCH_CONTRACT_SCHEMA,
        "launcher_path": "/system/bin/env",
        "launcher_toolchain_artifact_role": "system_launcher_env",
        "launcher_toolchain_artifact_identity_sha256": canonical_sha256(
            launcher_identity
        ),
        "launcher_resolved_path": "/system/bin/toybox",
        "launcher_clear_environment_argument": "-i",
        "launcher_argv_plan": argv_plan,
        "launcher_argv_resolution": (
            "typed_literal_or_canonical_payload_sha256_no_shell_interpolation"
        ),
        "outer_environment": dict(NATIVE_OUTER_ENVIRONMENT),
        "outer_environment_sha256": NATIVE_OUTER_ENVIRONMENT_SHA256,
        "outer_environment_must_be_empty": True,
        "forbidden_outer_environment_name_prefixes": ["LD_"],
        "native_attestation_required": {
            "outer_env_observed": True,
            "outer_environment_sha256": NATIVE_OUTER_ENVIRONMENT_SHA256,
        },
        "shell_interpolation_allowed": False,
        "malicious_same_UID_tamper_resistance_claimed": False,
        "security_ceiling": NATIVE_PREFLIGHT_SECURITY_CEILING,
    }


def validate_native_preflight_build_receipt(
    receipt: Mapping[str, Any],
    *,
    source_commit: str,
    source_file_bindings: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate the deterministic Android build evidence bound by preregistration."""

    expected_fields = {
        "schema_version",
        "run_id",
        "source_commit",
        "source_commit_binding_status",
        "source_file_bindings",
        "intended_target",
        "build_principal",
        "compiler_identity",
        "linker_identity",
        "toolchain_input_closure",
        "build_environment",
        "build_argv_template",
        "build_one",
        "build_two",
        "intermediate_objects",
        "binary_identity",
        "elf_identity",
        "deterministic_binary_match",
        "testing_macro_absent",
        "testing_hook_strings_absent",
        "network_requested",
        "network_syscalls_instrumented",
        "security_ceiling",
        "build_receipt_root_sha256",
    }
    if not isinstance(receipt, Mapping) or set(receipt) != expected_fields:
        raise CommercialSourceError("native_preflight_build_receipt_schema_invalid")
    value = dict(receipt)
    claimed_root = value.pop("build_receipt_root_sha256")
    _validate_prefixed_sha256(
        claimed_root,
        "native_preflight_build_receipt_root_invalid",
    )
    if canonical_sha256(value) != claimed_root:
        raise CommercialSourceError("native_preflight_build_receipt_root_mismatch")
    if (
        receipt["schema_version"] != NATIVE_PREFLIGHT_BUILD_SCHEMA
        or not isinstance(receipt["run_id"], str)
        or _RUN_ID_RE.fullmatch(receipt["run_id"]) is None
        or receipt["source_commit"] != source_commit
        or receipt["source_commit_binding_status"]
        != NATIVE_PREFLIGHT_SOURCE_COMMIT_BINDING_STATUS
        or receipt["source_file_bindings"] != dict(source_file_bindings)
        or set(source_file_bindings) != set(NATIVE_PREFLIGHT_SOURCE_FILES)
    ):
        raise CommercialSourceError("native_preflight_build_source_binding_mismatch")
    if receipt["intended_target"] != {
        "architecture": "aarch64",
        "compiler_target": "aarch64-linux-android30",
        "runtime_device_and_soc_gate": "not_claimed_by_build_receipt",
    } or receipt["build_principal"] != {
        "gid": PHONE_APP_GID,
        "uid": PHONE_APP_UID,
    }:
        raise CommercialSourceError("native_preflight_build_target_mismatch")
    if receipt["build_environment"] != {
        "ANDROID_ROOT": "/system",
        "HOME": "/data/data/com.termux/files/home",
        "LC_ALL": "C",
        "PATH": "/data/data/com.termux/files/usr/bin:/system/bin",
    }:
        raise CommercialSourceError("native_preflight_build_environment_mismatch")
    expected_build_argv = {
        "compile": list(NATIVE_PREFLIGHT_COMPILE_ARGV_TEMPLATE),
        "link": list(NATIVE_PREFLIGHT_LINK_ARGV_TEMPLATE),
    }
    if receipt["build_argv_template"] != expected_build_argv:
        raise CommercialSourceError("native_preflight_build_argv_mismatch")
    _validate_build_tool_identity(receipt["compiler_identity"], "compiler")
    _validate_build_tool_identity(receipt["linker_identity"], "linker")
    _validate_native_toolchain_input_closure(
        receipt["toolchain_input_closure"],
        run_id=receipt["run_id"],
        source_commit=source_commit,
        compiler_identity=receipt["compiler_identity"],
        linker_identity=receipt["linker_identity"],
    )
    _validate_native_intermediate_objects(receipt["intermediate_objects"])
    build_one = _validate_native_binary_digest(receipt["build_one"], "build_one")
    build_two = _validate_native_binary_digest(receipt["build_two"], "build_two")
    binary = _validate_native_binary_identity(receipt["binary_identity"])
    if (
        build_one != build_two
        or build_one != {"bytes": binary["bytes"], "sha256": binary["sha256"]}
        or receipt["deterministic_binary_match"] is not True
        or receipt["testing_macro_absent"] is not True
        or receipt["testing_hook_strings_absent"] is not True
        or receipt["network_requested"] is not False
        or receipt["network_syscalls_instrumented"] is not False
        or receipt["security_ceiling"] != NATIVE_PREFLIGHT_SECURITY_CEILING
    ):
        raise CommercialSourceError("native_preflight_build_claim_mismatch")
    _validate_native_elf_identity(receipt["elf_identity"], binary)
    return dict(receipt)


def _validate_native_toolchain_input_closure(
    value: Any,
    *,
    run_id: str,
    source_commit: str,
    compiler_identity: Mapping[str, Any],
    linker_identity: Mapping[str, Any],
) -> None:
    expected_fields = {
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
    if not isinstance(value, Mapping) or set(value) != expected_fields:
        raise CommercialSourceError("native_preflight_toolchain_closure_invalid")
    body = dict(value)
    claimed_root = body.pop("closure_root_sha256")
    _validate_prefixed_sha256(
        claimed_root,
        "native_preflight_toolchain_closure_root_invalid",
    )
    if claimed_root != canonical_sha256(body):
        raise CommercialSourceError("native_preflight_toolchain_closure_root_mismatch")
    if (
        value["schema_version"] != NATIVE_PREFLIGHT_TOOLCHAIN_CLOSURE_SCHEMA
        or value["compiled_source_execution"] != "held_source_fds"
        or value["compiler_execution"] != "held_compiler_fd"
        or value["header_resolution"] != "private_symlink_to_held_header_fd"
        or value["linker_execution"] != "direct_held_linker_fd"
        or value["input_closure_scope"]
        != "all_file_backed_build_inputs_and_current_process_executable_mappings"
        or value["kernel_and_process_boundary"]
        != {
            "kernel_vdso": "observed_executable_mapping_without_file_backing",
            "pre_exec_process_provenance": "outside_file_input_closure_claim",
        }
        or value["default_clang_configuration"]
        != {"disabled": True, "flag": "--no-default-config"}
        or value["unmeasured_inputs_allowed"] is not False
        or value["unmeasured_inputs_allowed_scope"] != "within_input_closure_scope"
        or value["include_trees"] != NATIVE_PREFLIGHT_BUILD_INCLUDE_TREES
        or value["link_inputs"] != NATIVE_PREFLIGHT_BUILD_LINK_INPUTS
    ):
        raise CommercialSourceError(
            "native_preflight_toolchain_closure_identity_mismatch"
        )
    _validate_native_build_python_runtime(
        value["python_runtime"],
        run_id=run_id,
        source_commit=source_commit,
    )
    _validate_native_build_tool_runtime(
        value["tool_execution_runtime"],
        compiler_identity=compiler_identity,
        linker_identity=linker_identity,
    )


def _is_canonical_absolute_runtime_path(value: Any) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("/")
        and "\x00" not in value
        and "//" not in value
        and all(component not in {"", ".", ".."} for component in value.split("/")[1:])
    )


def _validate_native_build_module_origins(
    records: Any,
    *,
    driver_path: str,
    contract_path: str,
    pycache_prefix: str,
) -> None:
    if not isinstance(records, list) or not records:
        raise CommercialSourceError("native_build_python_module_origins_invalid")
    expected_fields = {"cached", "loader", "name", "origin", "origin_kind"}
    names: list[str] = []
    stdlib_root = f"{_TERMUX_PREFIX}/lib/python3.13"
    extension_root = f"{stdlib_root}/lib-dynload"
    held_sources = {
        "__main__": driver_path,
        "_cur0s_build_driver_contract": contract_path,
    }
    for record in records:
        if not isinstance(record, Mapping) or set(record) != expected_fields:
            raise CommercialSourceError("native_build_python_module_origin_invalid")
        name = record["name"]
        loader = record["loader"]
        origin = record["origin"]
        cached = record["cached"]
        kind = record["origin_kind"]
        if (
            not isinstance(name, str)
            or re.fullmatch(r"[A-Za-z0-9_.]+", name) is None
            or (loader is not None and not isinstance(loader, str))
            or (isinstance(loader, str) and loader.endswith(".SourcelessFileLoader"))
        ):
            raise CommercialSourceError("native_build_python_module_origin_invalid")
        if kind in {"built_in", "frozen"}:
            expected_origin = "built-in" if kind == "built_in" else "frozen"
            if origin != expected_origin or cached is not None or loader is None:
                raise CommercialSourceError(
                    "native_build_python_builtin_origin_invalid"
                )
        elif kind == "held_source":
            if (
                held_sources.get(name) != origin
                or cached is not None
                or loader != "explicit_held_source"
            ):
                raise CommercialSourceError("native_build_python_held_origin_invalid")
        elif kind == "namespace":
            if (
                not isinstance(origin, str)
                or not origin.startswith("namespace:")
                or cached is not None
                or loader is not None
            ):
                raise CommercialSourceError(
                    "native_build_python_namespace_origin_invalid"
                )
            locations = origin.removeprefix("namespace:").split(":")
            if not locations or any(
                not _is_canonical_absolute_runtime_path(location)
                or not location.startswith(stdlib_root + "/")
                for location in locations
            ):
                raise CommercialSourceError(
                    "native_build_python_namespace_origin_invalid"
                )
        elif kind == "stdlib_source":
            if (
                not _is_canonical_absolute_runtime_path(origin)
                or not origin.startswith(stdlib_root + "/")
                or origin.startswith(stdlib_root + "/site-packages/")
                or "/__pycache__/" in origin
                or not origin.endswith(".py")
                or not isinstance(loader, str)
                or not loader.endswith(".SourceFileLoader")
                or not _is_canonical_absolute_runtime_path(cached)
                or not cached.startswith(pycache_prefix + "/")
            ):
                raise CommercialSourceError("native_build_python_source_origin_invalid")
        elif kind == "stdlib_extension":
            if (
                not _is_canonical_absolute_runtime_path(origin)
                or not origin.startswith(extension_root + "/")
                or not origin.endswith(".so")
                or not isinstance(loader, str)
                or not loader.endswith(".ExtensionFileLoader")
                or cached is not None
            ):
                raise CommercialSourceError(
                    "native_build_python_extension_origin_invalid"
                )
        else:
            raise CommercialSourceError("native_build_python_origin_kind_invalid")
        names.append(name)
    if names != sorted(names) or len(set(names)) != len(names):
        raise CommercialSourceError("native_build_python_module_order_invalid")
    if set(held_sources) - set(names):
        raise CommercialSourceError("native_build_python_held_origin_missing")


def _validate_native_build_python_runtime(
    value: Any,
    *,
    run_id: str,
    source_commit: str,
) -> None:
    base = native_preflight_build_python_runtime_identity()
    dynamic_fields = {
        "driver_path",
        "file_backed_executable_mapping_paths",
        "loaded_module_origin_count",
        "loaded_module_origins",
        "loaded_module_origins_sha256",
        "loaded_stdlib_extension_module_paths",
        "orig_argv",
        "pycache_prefix",
        "pycache_prefix_absent",
        "python_runtime_root_sha256",
        "run_id",
        "source_commit",
        "sys_argv",
        "sys_xoptions",
    }
    if (
        not isinstance(value, Mapping)
        or set(value) != set(base) | dynamic_fields
        or {field: value[field] for field in base} != base
    ):
        raise CommercialSourceError("native_build_python_runtime_schema_invalid")
    body = dict(value)
    claimed_root = body.pop("python_runtime_root_sha256")
    _validate_prefixed_sha256(
        claimed_root,
        "native_build_python_runtime_root_invalid",
    )
    if claimed_root != canonical_sha256(body):
        raise CommercialSourceError("native_build_python_runtime_root_mismatch")
    layout = native_preflight_execution_layout(run_id, source_commit)
    driver_path = (
        layout["checkout_root"] + "/scripts/termux/build_cur0s_native_preflight.py"
    )
    pycache_prefix = layout["action_root"] + "/native_preflight_build_pycache_forbidden"
    expected_orig_argv = [
        f"{_TERMUX_PREFIX}/bin/python",
        "-IBS",
        "-X",
        f"pycache_prefix={pycache_prefix}",
        driver_path,
        "--run-id",
        run_id,
        "--source-commit",
        source_commit,
    ]
    expected_sys_argv = expected_orig_argv[4:]
    records = value["loaded_module_origins"]
    extension_paths = (
        sorted(
            record["origin"]
            for record in records
            if isinstance(record, Mapping)
            and record.get("origin_kind") == "stdlib_extension"
        )
        if isinstance(records, list)
        else []
    )
    expected_mapping_paths = sorted(
        [artifact["path"] for artifact in base["artifact_inputs"].values()]
        + extension_paths
    )
    if (
        value["run_id"] != run_id
        or value["source_commit"] != source_commit
        or value["driver_path"] != driver_path
        or value["pycache_prefix"] != pycache_prefix
        or value["pycache_prefix_absent"] is not True
        or value["sys_xoptions"] != {"pycache_prefix": pycache_prefix}
        or value["orig_argv"] != expected_orig_argv
        or value["sys_argv"] != expected_sys_argv
        or not isinstance(records, list)
        or value["loaded_module_origin_count"] != len(records)
        or value["loaded_module_origins_sha256"] != canonical_sha256(records)
        or value["loaded_stdlib_extension_module_paths"] != extension_paths
        or value["file_backed_executable_mapping_paths"] != expected_mapping_paths
    ):
        raise CommercialSourceError("native_build_python_runtime_identity_invalid")
    _validate_native_build_module_origins(
        records,
        driver_path=driver_path,
        contract_path=layout["commercial_sources_path"],
        pycache_prefix=pycache_prefix,
    )


def _validate_actual_loader_held_identity(
    value: Any,
    *,
    runtime_role: str,
    expected: Mapping[str, Any],
) -> None:
    fields = {
        "bytes",
        "device_major",
        "device_minor",
        "inode",
        "literal_path",
        "resolved_path",
        "runtime_role",
        "sha256",
    }
    if (
        not isinstance(value, Mapping)
        or set(value) != fields
        or value["runtime_role"] != runtime_role
        or value["literal_path"] != expected["literal_path"]
        or value["resolved_path"] != expected["resolved_path"]
        or value["bytes"] != expected["bytes"]
        or value["sha256"] != expected["sha256"]
        or not isinstance(value["device_major"], int)
        or value["device_major"] < 0
        or not isinstance(value["device_minor"], int)
        or value["device_minor"] < 0
        or not isinstance(value["inode"], int)
        or value["inode"] <= 0
    ):
        raise CommercialSourceError("native_build_actual_loader_held_identity_invalid")


def _validate_actual_loader_entries(tool_role: str, entries: Any) -> None:
    expected_sequence = NATIVE_PREFLIGHT_ACTUAL_LOADER_EXPECTED_RESOLUTION[tool_role]
    fields = {
        "bytes",
        "device_major",
        "device_minor",
        "inode",
        "normalized_line",
        "resolved_path",
        "runtime_role",
        "sha256",
        "soname",
    }
    if not isinstance(entries, list) or len(entries) != len(expected_sequence):
        raise CommercialSourceError("native_build_actual_loader_entries_invalid")
    for entry, (soname, runtime_role) in zip(
        entries,
        expected_sequence,
        strict=True,
    ):
        if not isinstance(entry, Mapping) or set(entry) != fields:
            raise CommercialSourceError("native_build_actual_loader_entry_invalid")
        if runtime_role == "kernel_vdso":
            expected_path = "[vdso]"
            file_identity = {
                "bytes": None,
                "device_major": None,
                "device_minor": None,
                "inode": None,
                "sha256": None,
            }
        else:
            expected = NATIVE_PREFLIGHT_BUILD_TOOL_RUNTIME_INPUTS[runtime_role]
            expected_path = expected["resolved_path"]
            file_identity = {
                "bytes": expected["bytes"],
                "sha256": expected["sha256"],
            }
            if (
                not isinstance(entry["device_major"], int)
                or entry["device_major"] < 0
                or not isinstance(entry["device_minor"], int)
                or entry["device_minor"] < 0
                or not isinstance(entry["inode"], int)
                or entry["inode"] <= 0
            ):
                raise CommercialSourceError(
                    "native_build_actual_loader_entry_inode_invalid"
                )
        if (
            entry["soname"] != soname
            or entry["runtime_role"] != runtime_role
            or entry["resolved_path"] != expected_path
            or entry["normalized_line"] != f"\t{soname} => {expected_path}"
            or any(
                entry[field] != expected for field, expected in file_identity.items()
            )
        ):
            raise CommercialSourceError("native_build_actual_loader_entry_mismatch")


def _validate_native_build_tool_runtime(
    value: Any,
    *,
    compiler_identity: Mapping[str, Any],
    linker_identity: Mapping[str, Any],
) -> None:
    base = NATIVE_PREFLIGHT_BUILD_TOOL_RUNTIME_IDENTITY
    if (
        not isinstance(value, Mapping)
        or set(value) != set(base) | {"actual_loader_resolution"}
        or {field: value[field] for field in base} != base
    ):
        raise CommercialSourceError("native_build_tool_runtime_schema_invalid")
    actual = value["actual_loader_resolution"]
    expected_actual_fields = {
        "actual_loader_resolution_root_sha256",
        "address_normalization",
        "environment",
        "loader",
        "schema_version",
        "scope",
        "tools",
    }
    if not isinstance(actual, Mapping) or set(actual) != expected_actual_fields:
        raise CommercialSourceError("native_build_actual_loader_schema_invalid")
    actual_body = dict(actual)
    claimed_root = actual_body.pop("actual_loader_resolution_root_sha256")
    _validate_prefixed_sha256(claimed_root, "native_build_actual_loader_root_invalid")
    if claimed_root != canonical_sha256(actual_body):
        raise CommercialSourceError("native_build_actual_loader_root_mismatch")
    if (
        actual["schema_version"] != NATIVE_PREFLIGHT_ACTUAL_LOADER_RESOLUTION_SCHEMA
        or actual["address_normalization"]
        != "remove_only_exact_terminal_lowercase_hex_ASLR_address_suffix"
        or actual["scope"]
        != "static_PT_INTERP_and_DT_NEEDED_resolution_only_no_arbitrary_dlopen_claim"
        or actual["environment"]
        != {
            "ANDROID_ROOT": "/system",
            "HOME": "/data/data/com.termux/files/home",
            "LC_ALL": "C",
            "PATH": "/data/data/com.termux/files/usr/bin:/system/bin",
        }
        or not isinstance(actual["tools"], Mapping)
        or set(actual["tools"]) != {"compiler", "linker"}
    ):
        raise CommercialSourceError("native_build_actual_loader_identity_invalid")
    _validate_actual_loader_held_identity(
        actual["loader"],
        runtime_role="android_linker64",
        expected=NATIVE_PREFLIGHT_BUILD_TOOL_RUNTIME_INPUTS["android_linker64"],
    )
    tool_identities = {"compiler": compiler_identity, "linker": linker_identity}
    for tool_role, tool_identity in tool_identities.items():
        resolution = actual["tools"][tool_role]
        resolution_fields = {
            "argv",
            "entries",
            "entry_count",
            "normalized_stdout_sha256",
            "resolution_root_sha256",
            "returncode",
            "stderr_bytes",
            "stderr_sha256",
            "target",
        }
        if not isinstance(resolution, Mapping) or set(resolution) != resolution_fields:
            raise CommercialSourceError(
                "native_build_actual_loader_resolution_schema_invalid"
            )
        body = dict(resolution)
        resolution_root = body.pop("resolution_root_sha256")
        _validate_prefixed_sha256(
            resolution_root,
            "native_build_actual_loader_resolution_root_invalid",
        )
        if resolution_root != canonical_sha256(body):
            raise CommercialSourceError(
                "native_build_actual_loader_resolution_root_mismatch"
            )
        entries = resolution["entries"]
        argv = resolution["argv"]
        target_expected = {
            **tool_identity,
            "literal_path": tool_identity["literal_path"],
            "resolved_path": tool_identity["resolved_path"],
        }
        _validate_actual_loader_held_identity(
            resolution["target"],
            runtime_role=tool_role,
            expected=target_expected,
        )
        if (
            not isinstance(argv, list)
            or len(argv) != 3
            or argv[:2] != ["/system/bin/linker64", "--list"]
            or not isinstance(argv[2], str)
            or re.fullmatch(r"/proc/self/fd/[0-9]+", argv[2]) is None
            or resolution["entry_count"] != len(entries)
            or resolution["normalized_stdout_sha256"]
            != canonical_sha256([entry["normalized_line"] for entry in entries])
            or resolution["returncode"] != 0
            or resolution["stderr_bytes"] != 0
            or resolution["stderr_sha256"]
            != "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        ):
            raise CommercialSourceError(
                "native_build_actual_loader_resolution_identity_invalid"
            )
        _validate_actual_loader_entries(tool_role, entries)


def _validate_native_intermediate_objects(value: Any) -> None:
    if not isinstance(value, Mapping) or set(value) != {
        "build_one",
        "build_two",
        "deterministic_match",
    }:
        raise CommercialSourceError("native_preflight_intermediate_objects_invalid")
    roles = {"cur0s_native_preflight", "cur0s_sha256"}
    if (
        not isinstance(value["build_one"], Mapping)
        or not isinstance(value["build_two"], Mapping)
        or set(value["build_one"]) != roles
        or set(value["build_two"]) != roles
        or value["deterministic_match"] is not True
    ):
        raise CommercialSourceError("native_preflight_intermediate_objects_invalid")
    first = {
        role: _validate_native_binary_digest(value["build_one"][role], role)
        for role in roles
    }
    second = {
        role: _validate_native_binary_digest(value["build_two"][role], role)
        for role in roles
    }
    if first != second:
        raise CommercialSourceError("native_preflight_intermediate_objects_mismatch")


def _validate_build_tool_identity(value: Any, role: str) -> None:
    fields = {
        "literal_path",
        "literal_entry_type",
        "literal_mode",
        "literal_uid",
        "literal_gid",
        "literal_nlink",
        "literal_symlink_target",
        "resolved_path",
        "resolved_entry_type",
        "sha256",
        "bytes",
        "resolved_mode",
        "resolved_uid",
        "resolved_gid",
        "resolved_nlink",
        "version_argv_suffix",
        "version_returncode",
        "version_stdout_bytes",
        "version_stdout_sha256",
        "version_stderr_bytes",
        "version_stderr_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        raise CommercialSourceError(f"native_preflight_{role}_identity_invalid")
    for field in ("sha256", "version_stdout_sha256", "version_stderr_sha256"):
        _validate_prefixed_sha256(
            value[field],
            f"native_preflight_{role}_{field}_invalid",
        )
    if (
        not all(
            isinstance(value[field], str)
            and value[field].startswith("/")
            and "\x00" not in value[field]
            for field in ("literal_path", "resolved_path")
        )
        or value["literal_entry_type"] != "symbolic_link"
        or not re.fullmatch(r"0[0-7]{3}", value["literal_mode"])
        or value["literal_nlink"] != 1
        or not isinstance(value["literal_symlink_target"], str)
        or not value["literal_symlink_target"]
        or value["resolved_entry_type"] != "regular_file"
        or not re.fullmatch(r"0[0-7]{3}", value["resolved_mode"])
        or any(
            type(value[field]) is not int or value[field] < 0
            for field in (
                "bytes",
                "literal_uid",
                "literal_gid",
                "literal_nlink",
                "resolved_uid",
                "resolved_gid",
                "resolved_nlink",
                "version_returncode",
                "version_stdout_bytes",
                "version_stderr_bytes",
            )
        )
        or value["bytes"] <= 0
        or value["resolved_nlink"] != 1
        or not isinstance(value["version_argv_suffix"], list)
        or any(
            not isinstance(argument, str) or "\x00" in argument
            for argument in value["version_argv_suffix"]
        )
        or value["version_returncode"] != 0
    ):
        raise CommercialSourceError(f"native_preflight_{role}_identity_invalid")
    empty_sha = "sha256:" + hashlib.sha256(b"").hexdigest()
    expected_by_role = {
        "compiler": {
            "literal_path": "/data/data/com.termux/files/usr/bin/clang",
            "literal_entry_type": "symbolic_link",
            "literal_mode": "0777",
            "literal_uid": PHONE_APP_UID,
            "literal_gid": PHONE_APP_GID,
            "literal_nlink": 1,
            "literal_symlink_target": "clang-21",
            "resolved_path": "/data/data/com.termux/files/usr/bin/clang-21",
            "resolved_entry_type": "regular_file",
            "sha256": (
                "sha256:34da8e3a9b71793eb70c25670e1fe2bce4d37f1e2837ba8d"
                "c0c516c2ca0ffc83"
            ),
            "bytes": 120_848,
            "resolved_mode": "0700",
            "resolved_uid": PHONE_APP_UID,
            "resolved_gid": PHONE_APP_GID,
            "resolved_nlink": 1,
            "version_argv_suffix": ["--version"],
            "version_returncode": 0,
            "version_stdout_bytes": 109,
            "version_stdout_sha256": (
                "sha256:fe40f61ef08c80c802452d327052739a0a57b31366d8eabdc"
                "694a15b8df98f94"
            ),
            "version_stderr_bytes": 0,
            "version_stderr_sha256": empty_sha,
        },
        "linker": {
            "literal_path": "/data/data/com.termux/files/usr/bin/ld.lld",
            "literal_entry_type": "symbolic_link",
            "literal_mode": "0777",
            "literal_uid": PHONE_APP_UID,
            "literal_gid": PHONE_APP_GID,
            "literal_nlink": 1,
            "literal_symlink_target": "lld",
            "resolved_path": "/data/data/com.termux/files/usr/bin/lld",
            "resolved_entry_type": "regular_file",
            "sha256": (
                "sha256:5214b9511221a87e02c4a9603f470dd83804a54f4cf62475"
                "f168d47d707d964d"
            ),
            "bytes": 5_615_720,
            "resolved_mode": "0700",
            "resolved_uid": PHONE_APP_UID,
            "resolved_gid": PHONE_APP_GID,
            "resolved_nlink": 1,
            "version_argv_suffix": ["-flavor", "gnu", "--version"],
            "version_returncode": 0,
            "version_stdout_bytes": 41,
            "version_stdout_sha256": (
                "sha256:418d72df86baf70c88b9a96a9118e3cdc66be0537a58f66"
                "a6879df0479f9a78f"
            ),
            "version_stderr_bytes": 0,
            "version_stderr_sha256": empty_sha,
        },
    }
    if role not in expected_by_role or value != expected_by_role[role]:
        raise CommercialSourceError(f"native_preflight_{role}_identity_mismatch")


def _validate_native_binary_digest(value: Any, role: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {"bytes", "sha256"}:
        raise CommercialSourceError(f"native_preflight_{role}_invalid")
    _validate_prefixed_sha256(value["sha256"], f"native_preflight_{role}_invalid")
    if type(value["bytes"]) is not int or value["bytes"] <= 0:
        raise CommercialSourceError(f"native_preflight_{role}_invalid")
    return dict(value)


def _validate_native_binary_identity(value: Any) -> dict[str, Any]:
    fields = {"bytes", "gid", "mode", "nlink", "sha256", "uid"}
    if not isinstance(value, Mapping) or set(value) != fields:
        raise CommercialSourceError("native_preflight_binary_identity_invalid")
    _validate_prefixed_sha256(
        value["sha256"],
        "native_preflight_binary_identity_invalid",
    )
    if (
        type(value["bytes"]) is not int
        or value["bytes"] <= 0
        or value["mode"] != "0700"
        or value["uid"] != PHONE_APP_UID
        or value["gid"] != PHONE_APP_GID
        or value["nlink"] != 1
    ):
        raise CommercialSourceError("native_preflight_binary_identity_invalid")
    return dict(value)


def _validate_native_elf_identity(value: Any, binary: Mapping[str, Any]) -> None:
    executable_fields = {
        "alignment",
        "file_offset",
        "file_size",
        "memory_size",
        "proc_maps_mapped_bytes",
        "proc_maps_offset",
        "proc_maps_page_size",
        "virtual_address",
    }
    if not isinstance(value, Mapping):
        raise CommercialSourceError("native_preflight_ELF_identity_mismatch")
    executable = value.get("executable_pt_load")
    if not isinstance(executable, Mapping) or set(executable) != executable_fields:
        raise CommercialSourceError("native_preflight_ELF_identity_mismatch")
    if any(type(executable[field]) is not int for field in executable_fields):
        raise CommercialSourceError("native_preflight_ELF_identity_mismatch")
    page_size = executable["proc_maps_page_size"]
    alignment = executable["alignment"]
    file_offset = executable["file_offset"]
    virtual_address = executable["virtual_address"]
    file_size = executable["file_size"]
    memory_size = executable["memory_size"]
    if page_size != 4096 or alignment < page_size or alignment & (alignment - 1):
        raise CommercialSourceError("native_preflight_ELF_identity_mismatch")
    expected_map_offset = file_offset - (file_offset % page_size)
    expected_mapped_bytes = (
        virtual_address % page_size + memory_size + page_size - 1
    ) // page_size * page_size
    if (
        file_offset < 0
        or virtual_address < 0
        or file_size <= 0
        or memory_size < file_size
        or file_offset > binary["bytes"]
        or file_size > binary["bytes"] - file_offset
        or file_offset % alignment != virtual_address % alignment
        or executable["proc_maps_offset"] != expected_map_offset
        or executable["proc_maps_mapped_bytes"] != expected_mapped_bytes
    ):
        raise CommercialSourceError("native_preflight_ELF_identity_mismatch")
    expected = {
        "android_ident": {
            "api_level": 30,
            "ndk_build_number": "14206865",
            "ndk_version": "r29",
        },
        "bind_now": True,
        "build_id": None,
        "class_bits": 64,
        "data_encoding": "little_endian",
        "executable_pt_load": dict(executable),
        "interpreter": "/system/bin/linker64",
        "machine": "AArch64",
        "needed": ["libc.so"],
        "pie": True,
        "relro": True,
        "rpath": None,
        "runpath": None,
        "sha256": binary["sha256"],
        "text_relocations": False,
    }
    if value != expected:
        raise CommercialSourceError("native_preflight_ELF_identity_mismatch")


def build_native_preflight_static_manifest_records(
    *,
    run_id: str,
    source_commit: str,
    source_file_bindings: Mapping[str, Mapping[str, Any]],
    native_binary_identity: Mapping[str, Any],
    native_elf_identity: Mapping[str, Any],
    toolchain: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build the exact runtime closure that must be measured before CPython."""

    layout = native_preflight_execution_layout(run_id, source_commit)
    toolchain_value = phone_toolchain_contract() if toolchain is None else toolchain
    if toolchain_value != phone_toolchain_contract():
        raise CommercialSourceError("native_preflight_toolchain_contract_mismatch")
    artifacts = toolchain_value["artifacts"]
    records: list[dict[str, Any]] = []
    for role, artifact in sorted(artifacts.items()):
        if artifact["literal_entry_type"] == "symbolic_link":
            records.append(
                {
                    "record_type": "SYMLINK",
                    "path": artifact["literal_path"],
                    "mode": artifact["literal_mode"],
                    "uid": artifact["literal_uid"],
                    "gid": artifact["literal_gid"],
                    "nlink": artifact["literal_nlink"],
                    "target": artifact["literal_symlink_target"],
                    "toolchain_role": role,
                }
            )
        records.append(
            {
                "record_type": "FILE",
                "path": artifact["resolved_path"],
                "mode": artifact["resolved_mode"],
                "uid": artifact["resolved_uid"],
                "gid": artifact["resolved_gid"],
                "nlink": artifact["resolved_nlink"],
                "bytes": artifact["bytes"],
                "sha256": artifact["sha256"],
                "toolchain_role": role,
            }
        )
    expected_source_paths = {
        "polymath_ai/corpus/cur0s_commercial_sources.py": layout[
            "commercial_sources_path"
        ],
        "scripts/termux/run_cur0s_commercial_sources.py": layout["runner_path"],
    }
    if set(source_file_bindings) != set(expected_source_paths):
        raise CommercialSourceError("native_preflight_runtime_source_binding_invalid")
    for relative_path, phone_path in sorted(expected_source_paths.items()):
        binding = source_file_bindings[relative_path]
        records.append(
            {
                "record_type": "FILE",
                "path": phone_path,
                "mode": "0600",
                "uid": PHONE_APP_UID,
                "gid": PHONE_APP_GID,
                "nlink": 1,
                "bytes": binding["bytes"],
                "sha256": binding["sha256"],
                "runtime_role": (
                    "runner"
                    if relative_path.endswith("run_cur0s_commercial_sources.py")
                    else "commercial_sources"
                ),
            }
        )
    binary = _validate_native_binary_identity(native_binary_identity)
    _validate_native_elf_identity(native_elf_identity, binary)
    executable_geometry = native_elf_identity["executable_pt_load"]
    records.append(
        {
            "record_type": "FILE",
            "path": layout["native_binary_path"],
            **binary,
            "runtime_role": "native_self",
            "executable_map_offset": executable_geometry["proc_maps_offset"],
            "executable_map_mapped_bytes": executable_geometry[
                "proc_maps_mapped_bytes"
            ],
        }
    )
    stdlib = toolchain_value["python_stdlib_tree"]
    records.append(
        {
            "record_type": "STDLIB_TREE",
            "path": stdlib["root_path"],
            "mode": stdlib["root_mode"],
            "uid": stdlib["root_uid"],
            "gid": stdlib["root_gid"],
            "nlink": stdlib["root_nlink"],
            "entry_count": stdlib["entry_count"],
            "regular_bytes": stdlib["regular_bytes"],
            "sha256": stdlib["root_sha256"],
            "canonicalization": stdlib["canonicalization"],
            "runtime_role": "python_stdlib",
        }
    )
    paths = [record["path"] for record in records]
    if len(paths) != len(set(paths)):
        raise CommercialSourceError("native_preflight_manifest_duplicate_path")
    return sorted(records, key=lambda record: (record["path"], record["record_type"]))


def build_native_preflight_execution_contract(
    *,
    run_id: str,
    source_commit: str,
    source_file_bindings: Mapping[str, Mapping[str, Any]],
    native_source_file_bindings: Mapping[str, Mapping[str, Any]],
    native_build_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Freeze the native-to-Python execution continuity contract."""

    validated_receipt = validate_native_preflight_build_receipt(
        native_build_receipt,
        source_commit=source_commit,
        source_file_bindings=native_source_file_bindings,
    )
    if validated_receipt["run_id"] != run_id:
        raise CommercialSourceError("native_preflight_build_run_id_mismatch")
    layout = native_preflight_execution_layout(run_id, source_commit)
    records = build_native_preflight_static_manifest_records(
        run_id=run_id,
        source_commit=source_commit,
        source_file_bindings=source_file_bindings,
        native_binary_identity=validated_receipt["binary_identity"],
        native_elf_identity=validated_receipt["elf_identity"],
    )
    launch_environment = {
        **phone_toolchain_contract()["python_runtime"]["launch_environment"],
        "CUR0S_NATIVE_ATTESTATION_FD": "4",
        "CUR0S_NATIVE_MANIFEST_FD": "5",
        "CUR0S_PREREGISTRATION_FD": "6",
    }
    outer_launch = native_outer_launch_contract(layout)
    pycache_prefix = layout["action_root"] + "/python_pycache_forbidden"
    native_maps_contract = {
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
        "native_self_executable_map": {
            "mapped_bytes": validated_receipt["elf_identity"][
                "executable_pt_load"
            ]["proc_maps_mapped_bytes"],
            "offset": validated_receipt["elf_identity"]["executable_pt_load"][
                "proc_maps_offset"
            ],
            "source": "deterministic_build_receipt_executable_PT_LOAD",
        },
        "schema_version": "cur0s_native_earliest_main_maps_v1",
        "start_and_end_addresses_excluded_as_ASLR_only": True,
        "unexpected_executable_mappings_forbidden": True,
        "vvar_required_nonexecutable": True,
    }
    body = {
        "schema_version": NATIVE_PREFLIGHT_CONTRACT_SCHEMA,
        "build_receipt": validated_receipt,
        "build_receipt_sha256": canonical_sha256(validated_receipt),
        "native_source_file_bindings": dict(native_source_file_bindings),
        "manifest_header": NATIVE_PREFLIGHT_MANIFEST_HEADER,
        "manifest_tree_canonicalization": NATIVE_PREFLIGHT_TREE_CANONICALIZATION,
        "static_manifest_records": records,
        "static_manifest_records_sha256": canonical_sha256(records),
        "execution_layout": layout,
        "fixed_fd_map": dict(NATIVE_PREFLIGHT_FIXED_FD_MAP),
        "python_flags": ["-IBS", "-X"],
        "python_argv0": "/data/data/com.termux/files/usr/bin/python",
        "python_pycache_prefix": pycache_prefix,
        "python_pycache_prefix_must_be_absent": True,
        "python_executable_record_path": (
            "/data/data/com.termux/files/usr/bin/python3.13"
        ),
        "runner_execution_path": "/proc/self/fd/3",
        "launch_environment": launch_environment,
        "launch_environment_sha256": canonical_sha256(launch_environment),
        "outer_launch": outer_launch,
        "outer_launch_sha256": canonical_sha256(outer_launch),
        "native_receipt_schema": "cur0s_native_launch_attestation_v2",
        "native_maps_contract": native_maps_contract,
        "native_receipt_transport": (
            "anonymous_memfd_exact_seals_WRITE_GROW_SHRINK_SEAL_offset_zero"
        ),
        "manifest_required_record_types": [
            "FILE",
            "SYMLINK",
            "STDLIB_TREE",
            "EXEC_PLAN",
        ],
        "verification_passes": 2,
        "same_process_execveat_required": True,
        "direct_python_launch_allowed": False,
        "persistent_preflight_writes": False,
        "security_ceiling": NATIVE_PREFLIGHT_SECURITY_CEILING,
        "malicious_same_UID_tamper_resistance_claimed": False,
        "git_helper_and_dynamic_dependency_atomic_FD_custody_claimed": False,
        "claim_ceiling": (
            "exact_owner_writable_phone_runtime_snapshot_verified_before_"
            "CPython_under_no_concurrent_same_UID_writer"
        ),
    }
    return {**body, "contract_root_sha256": canonical_sha256(body)}


def build_native_preflight_manifest_bytes(
    preregistration: Mapping[str, Any],
) -> bytes:
    """Serialize the exact native closure plus the self-referential prereg entry."""

    if not isinstance(preregistration, Mapping):
        raise CommercialSourceError("native_preflight_preregistration_invalid")
    native = preregistration.get("native_preflight")
    if not isinstance(native, Mapping):
        raise CommercialSourceError("native_preflight_contract_missing")
    body = dict(native)
    claimed_root = body.pop("contract_root_sha256", None)
    if claimed_root != canonical_sha256(body):
        raise CommercialSourceError("native_preflight_contract_root_mismatch")
    if preregistration.get("native_preflight_sha256") != canonical_sha256(native):
        raise CommercialSourceError("native_preflight_contract_hash_mismatch")
    prereg_body = dict(preregistration)
    prereg_root = prereg_body.pop("preregistration_root_sha256", None)
    if prereg_root != canonical_sha256(prereg_body):
        raise CommercialSourceError("native_preflight_preregistration_root_mismatch")
    prereg_payload = canonical_json_bytes(preregistration) + b"\n"
    layout = native["execution_layout"]
    expected_outer_launch = native_outer_launch_contract(layout)
    if (
        native.get("fixed_fd_map") != NATIVE_PREFLIGHT_FIXED_FD_MAP
        or native.get("outer_launch") != expected_outer_launch
        or native.get("outer_launch_sha256") != canonical_sha256(expected_outer_launch)
    ):
        raise CommercialSourceError("native_preflight_launch_contract_mismatch")
    records = list(native["static_manifest_records"])
    records.append(
        {
            "record_type": "FILE",
            "path": layout["preregistration_path"],
            "mode": "0600",
            "uid": PHONE_APP_UID,
            "gid": PHONE_APP_GID,
            "nlink": 1,
            "bytes": len(prereg_payload),
            "sha256": "sha256:" + hashlib.sha256(prereg_payload).hexdigest(),
            "runtime_role": "preregistration",
        }
    )
    role_counts = {
        role: sum(_native_manifest_record_role(record) == role for record in records)
        for role in ("native-self", "python", "runner", "preregistration")
    }
    if set(role_counts.values()) != {1}:
        raise CommercialSourceError("native_preflight_manifest_role_closure_invalid")
    lines = [NATIVE_PREFLIGHT_MANIFEST_HEADER]
    lines.extend(_native_manifest_record_line(record) for record in records)
    fixed_fds = native["fixed_fd_map"]
    exec_fields = (
        "EXEC_PLAN",
        preregistration["run_id"],
        layout["action_root"],
        layout["candidate_output"],
        native["python_argv0"],
        *native["python_flags"],
        native["python_pycache_prefix"],
        native["launch_environment_sha256"],
        native["outer_launch"]["outer_environment_sha256"],
        str(fixed_fds["runner"]),
        str(fixed_fds["native_attestation"]),
        str(fixed_fds["manifest"]),
        str(fixed_fds["preregistration"]),
    )
    lines.append("\t".join(exec_fields))
    payload = ("\n".join(lines) + "\n").encode("utf-8")
    if len(payload) > 4 * 1024 * 1024:
        raise CommercialSourceError("native_preflight_manifest_oversize")
    return payload


def build_native_launch_envelope(
    preregistration: Mapping[str, Any],
    manifest_payload: bytes,
) -> dict[str, Any]:
    """Resolve the preregistered outer-launch plan without a shell."""

    if not isinstance(manifest_payload, bytes):
        raise CommercialSourceError("native_launch_manifest_payload_invalid")
    expected_manifest = build_native_preflight_manifest_bytes(preregistration)
    if manifest_payload != expected_manifest:
        raise CommercialSourceError("native_launch_manifest_payload_mismatch")
    native = preregistration["native_preflight"]
    layout = native["execution_layout"]
    expected_contract = native_outer_launch_contract(layout)
    if (
        native.get("outer_launch") != expected_contract
        or native.get("outer_launch_sha256") != canonical_sha256(expected_contract)
        or native.get("fixed_fd_map") != NATIVE_PREFLIGHT_FIXED_FD_MAP
    ):
        raise CommercialSourceError("native_launch_contract_mismatch")
    preregistration_payload = canonical_json_bytes(preregistration) + b"\n"
    digest_values = {
        "native_manifest_bytes_sha256": (
            "sha256:" + hashlib.sha256(manifest_payload).hexdigest()
        ),
        "preregistration_bytes_sha256": (
            "sha256:" + hashlib.sha256(preregistration_payload).hexdigest()
        ),
    }
    launcher_argv: list[str] = []
    for item in expected_contract["launcher_argv_plan"]:
        if item["kind"] == "literal":
            launcher_argv.append(item["value"])
            continue
        if item["kind"] != "derived" or item.get("source") not in digest_values:
            raise CommercialSourceError("native_launch_argv_plan_invalid")
        launcher_argv.append(digest_values[item["source"]])
    if (
        launcher_argv[:2] != ["/system/bin/env", "-i"]
        or any("=" in argument for argument in launcher_argv[2:3])
        or any(
            name.startswith("LD_") for name in expected_contract["outer_environment"]
        )
    ):
        raise CommercialSourceError("native_launch_outer_environment_dirty")
    body = {
        "schema_version": NATIVE_LAUNCH_ENVELOPE_SCHEMA,
        "state": "frozen_unexecuted",
        "execution_performed": False,
        "run_id": preregistration["run_id"],
        "native_preflight_contract_root_sha256": native["contract_root_sha256"],
        "outer_launch_contract_sha256": native["outer_launch_sha256"],
        "launcher_toolchain_artifact_role": expected_contract[
            "launcher_toolchain_artifact_role"
        ],
        "launcher_toolchain_artifact_identity_sha256": expected_contract[
            "launcher_toolchain_artifact_identity_sha256"
        ],
        "launcher_path": expected_contract["launcher_path"],
        "launcher_resolved_path": expected_contract["launcher_resolved_path"],
        "launch_envelope_path": layout["launch_envelope_path"],
        "preregistration_path": layout["preregistration_path"],
        "preregistration_bytes": len(preregistration_payload),
        "preregistration_sha256": digest_values["preregistration_bytes_sha256"],
        "manifest_path": layout["manifest_path"],
        "manifest_bytes": len(manifest_payload),
        "manifest_sha256": digest_values["native_manifest_bytes_sha256"],
        "outer_environment": dict(NATIVE_OUTER_ENVIRONMENT),
        "outer_environment_sha256": NATIVE_OUTER_ENVIRONMENT_SHA256,
        "fixed_fd_map": dict(NATIVE_PREFLIGHT_FIXED_FD_MAP),
        "native_attestation_required": dict(
            expected_contract["native_attestation_required"]
        ),
        "launcher_argv": launcher_argv,
        "launcher_argv_sha256": canonical_sha256(launcher_argv),
        "shell_interpolation_allowed": False,
        "malicious_same_UID_tamper_resistance_claimed": False,
        "security_ceiling": NATIVE_PREFLIGHT_SECURITY_CEILING,
    }
    return {**body, "envelope_root_sha256": canonical_sha256(body)}


def _native_manifest_record_role(record: Mapping[str, Any]) -> str | None:
    if record.get("record_type") != "FILE":
        return None
    runtime_role = record.get("runtime_role")
    if runtime_role == "native_self":
        return "native-self"
    if runtime_role == "runner":
        return "runner"
    if runtime_role == "preregistration":
        return "preregistration"
    if record.get("toolchain_role") == "python":
        return "python"
    return None


def _native_manifest_record_line(record: Mapping[str, Any]) -> str:
    record_type = record.get("record_type")
    common = (
        str(record.get("path")),
        str(record.get("mode")),
        str(record.get("uid")),
        str(record.get("gid")),
        str(record.get("nlink")),
    )
    if record_type == "FILE":
        fields = (
            "FILE",
            *common,
            str(record.get("bytes")),
            str(record.get("sha256")),
        )
        role = _native_manifest_record_role(record)
        if role is not None:
            fields = (*fields, role)
        if role == "native-self":
            map_offset = record.get("executable_map_offset")
            mapped_bytes = record.get("executable_map_mapped_bytes")
            if (
                type(map_offset) is not int
                or map_offset < 0
                or type(mapped_bytes) is not int
                or mapped_bytes <= 0
            ):
                raise CommercialSourceError(
                    "native_preflight_manifest_self_geometry_invalid"
                )
            fields = (*fields, str(map_offset), str(mapped_bytes))
    elif record_type == "SYMLINK":
        fields = ("SYMLINK", *common, str(record.get("target")))
    elif record_type == "STDLIB_TREE":
        fields = (
            "STDLIB_TREE",
            *common,
            str(record.get("entry_count")),
            str(record.get("regular_bytes")),
            str(record.get("sha256")),
            str(record.get("canonicalization")),
        )
    else:
        raise CommercialSourceError("native_preflight_manifest_record_type_invalid")
    if any(
        not value or "\x00" in value or "\t" in value or "\r" in value or "\n" in value
        for value in fields
    ):
        raise CommercialSourceError("native_preflight_manifest_record_text_invalid")
    return "\t".join(fields)


def source_contract() -> dict[str, Any]:
    _validate_frozen_specs()
    preregistration_blockers = [
        {
            "field": "opf_grade_values",
            "reason": "payload_grade_metadata_identity_unresolved",
            "source_id": source.source_id,
        }
        for source in DIRECT_SOURCES
        if source.epub_identity is not None
        and source.epub_identity.opf_grade_values is None
    ]
    body = {
        "schema_version": CONTRACT_SCHEMA,
        "lane": LANE,
        "source_count": len(DIRECT_SOURCES) + len(GIT_SOURCES),
        "target_semantics": {
            "C1": "lexical_self_expansion",
            "C2": "known_vocabulary_lexical_frontier",
            "B23": "general_to_science_bridge_diagnostic_weight_zero",
            "C3": "science_dictionary",
            "C4": "prerequisite_ordered_science_syllabus",
        },
        "direct_sources": [source.to_dict() for source in DIRECT_SOURCES],
        "git_sources": [source.to_dict() for source in GIT_SOURCES],
        "hard_rejects": [dict(item) for item in HARD_REJECTS],
        "preregistration_eligibility": {
            "eligible": not preregistration_blockers,
            "selection_critical_identity_blockers": preregistration_blockers,
        },
        "artifact_receipt_contract": {
            "common_verification_fields": sorted(_COMMON_VERIFICATION_FIELDS),
            "direct_verification_fields": sorted(_DIRECT_VERIFICATION_FIELDS),
            "git_verification_fields": sorted(_GIT_VERIFICATION_FIELDS),
            "verification_booleans_required_true": sorted(_TRUE_VERIFICATION_FIELDS),
            "direct_size_etag_last_modified_and_final_url_must_match": True,
            "git_commit_tree_license_count_and_selected_bytes_must_match": True,
            "transport_metadata_is_not_upstream_cryptographic_identity": True,
        },
        "downstream_admission_requirements": {
            "raw_source_pass_is_not_row_admission": True,
            "third_party_attribution_and_embedded_asset_quarantine_required": True,
            "OpenStax_media_binary_admission": False,
            "Siyavula_missing_visual_or_table_context_quarantined": True,
            "numeric_and_unit_views_require_recomputation": True,
            "C4_mathematics_role": "quantitative_prerequisite_only",
            "C4_science_syllabus_role": "sovereign_target",
        },
        "custody": {
            "raw_source_owner": "phone",
            "Mac_raw_cache": False,
            "private_HF_mirror_required_before_CUR0S_admission": True,
            "C4_COM_and_C4_RX_roots_separate": True,
        },
        "claim_ceiling": (
            "commercial_source_acquisition_and_rights_identity_only_not_semantic_"
            "compilation_near_semantic_split_CUR0S_learning_or_authority"
        ),
    }
    return {**body, "contract_root_sha256": canonical_sha256(body)}


def _validate_frozen_specs() -> None:
    sources = (*DIRECT_SOURCES, *GIT_SOURCES)
    source_ids = [source.source_id for source in sources]
    if len(source_ids) != len(set(source_ids)):
        raise CommercialSourceError("duplicate_source_id")
    allowed_stages = {"C1", "C2", "B23", "C3", "C4"}
    for source in sources:
        if not source.source_id or not source.stages:
            raise CommercialSourceError("source_spec_identity_or_stages_missing")
        if len(source.stages) != len(set(source.stages)):
            raise CommercialSourceError("source_spec_duplicate_stage")
        if any(stage not in allowed_stages for stage in source.stages):
            raise CommercialSourceError("source_spec_unknown_stage")
        if source.license_class not in {"A", "B"}:
            raise CommercialSourceError("source_spec_license_not_commercial_default")
        if isinstance(source, DirectSourceSpec):
            if not source.url.startswith("https://"):
                raise CommercialSourceError("source_spec_non_https_url")
            if (
                type(source.expected_bytes) is not int
                or source.expected_bytes <= 0
                or not isinstance(source.expected_etag, str)
                or not source.expected_etag
            ):
                raise CommercialSourceError("source_spec_transport_identity_missing")
            if (
                source.expected_sha256 is None
                or SHA256_RE.fullmatch(source.expected_sha256) is None
            ):
                raise CommercialSourceError("source_spec_expected_sha256_invalid")
            allowed_conditional_modes = {
                "if_match_enforced_observed_412_on_mismatch",
                "dated_release_pre_get_post_identity_server_ignores_conditionals",
            }
            if source.conditional_lock_mode not in allowed_conditional_modes:
                raise CommercialSourceError("source_spec_conditional_lock_mode_invalid")
            if source.transfer_mode == "fixed_range_chunks_v1":
                if (
                    type(source.fixed_chunk_bytes) is not int
                    or not 1 <= source.fixed_chunk_bytes <= 16 * 1024 * 1024
                    or source.expected_etag.startswith("W/")
                ):
                    raise CommercialSourceError(
                        "source_spec_fixed_range_transfer_policy_invalid"
                    )
            elif source.transfer_mode == "single_response_v1":
                if source.fixed_chunk_bytes is not None:
                    raise CommercialSourceError(
                        "source_spec_single_response_transfer_policy_invalid"
                    )
            else:
                raise CommercialSourceError("source_spec_transfer_mode_invalid")
            if not source.required_markers:
                raise CommercialSourceError("source_spec_rights_marker_missing")
            if source.rights_admission_basis != "exact_acquired_payload_evidence_only":
                raise CommercialSourceError(
                    "source_spec_rights_admission_basis_invalid"
                )
            payload_evidence = source.payload_rights_specs()
            for evidence in payload_evidence:
                if (
                    evidence.locator_kind not in {"direct_prefix", "zip_member"}
                    or not evidence.locator
                    or evidence.locator.startswith(("/", "\\"))
                    or ".." in evidence.locator.split("/")
                    or SHA256_RE.fullmatch(evidence.sha256) is None
                    or evidence.license_id == ""
                    or not evidence.required_markers
                ):
                    raise CommercialSourceError(
                        "source_spec_payload_rights_evidence_invalid"
                    )
                if evidence.locator_kind == "direct_prefix":
                    if (
                        evidence.locator != source.filename
                        or type(evidence.byte_offset) is not int
                        or evidence.byte_offset < 0
                        or type(evidence.byte_length) is not int
                        or evidence.byte_length <= 0
                        or evidence.byte_offset + evidence.byte_length
                        > source.expected_bytes
                    ):
                        raise CommercialSourceError(
                            "source_spec_payload_rights_range_invalid"
                        )
                elif (
                    evidence.byte_offset is not None or evidence.byte_length is not None
                ):
                    raise CommercialSourceError(
                        "source_spec_payload_rights_zip_range_invalid"
                    )
            allowed_external_canonicalizations = {
                "raw_bytes",
                "cur0s_chebi_rights_evidence_envelope_canonical_json_v1",
                "siyavula_catalogue_target_anchors_canonical_json_v1",
                "siyavula_terms_license_sections_canonical_json_v1",
            }
            for evidence in source.external_rights_specs():
                if (
                    not evidence.evidence_id
                    or not evidence.locator
                    or SHA256_RE.fullmatch(evidence.sha256) is None
                    or (
                        evidence.byte_count is not None
                        and (
                            type(evidence.byte_count) is not int
                            or evidence.byte_count <= 0
                        )
                    )
                    or evidence.canonicalization
                    not in allowed_external_canonicalizations
                    or evidence.role != "supplementary_conflict_context"
                ):
                    raise CommercialSourceError(
                        "source_spec_external_rights_evidence_invalid"
                    )
            media_type = source.media_type.split(";", 1)[0].strip().lower()
            if media_type == "application/epub+zip":
                identity = source.epub_identity
                if identity is None:
                    raise CommercialSourceError("source_spec_EPUB_identity_missing")
                for digest in (
                    identity.opf_sha256,
                    identity.navigation_sha256,
                    identity.rights_member_sha256,
                    identity.catalogue_evidence_root_sha256,
                    identity.terms_evidence_root_sha256,
                ):
                    if SHA256_RE.fullmatch(digest) is None:
                        raise CommercialSourceError("source_spec_EPUB_hash_invalid")
                for path in (
                    identity.opf_path,
                    identity.navigation_path,
                    identity.rights_member_path,
                ):
                    if (
                        not path
                        or path.startswith(("/", "\\"))
                        or ".." in path.split("/")
                    ):
                        raise CommercialSourceError("source_spec_EPUB_path_invalid")
                metadata_value_sets = (
                    identity.opf_publisher_values,
                    identity.opf_creator_values,
                    identity.opf_rights_values,
                    identity.opf_subject_values,
                )
                if (
                    (
                        identity.package_version is not None
                        and re.fullmatch(r"3\.[0-9]+", identity.package_version) is None
                    )
                    or not isinstance(identity.catalogue_subject, str)
                    or not identity.catalogue_subject.strip()
                    or identity.catalogue_subject != identity.catalogue_subject.strip()
                    or len(identity.catalogue_subject) > 128
                    or type(identity.catalogue_grade) is not int
                    or not 1 <= identity.catalogue_grade <= 12
                    or identity.filename_grade_token != f"Gr{identity.catalogue_grade}"
                    or re.fullmatch(r"Gr[1-9][0-9]?", identity.filename_grade_token)
                    is None
                    or re.fullmatch(
                        r"[A-Za-z][A-Za-z0-9]*", identity.filename_subject_token
                    )
                    is None
                    or source.url.rsplit("/", 1)[-1] != source.filename
                    or not source.filename.startswith(
                        f"{identity.filename_grade_token}_"
                        f"{identity.filename_subject_token}_"
                    )
                    or identity.artifact_notice_url
                    != "http://creativecommons.org/licenses/by/4.0/"
                    or any(
                        not isinstance(values, tuple)
                        or any(
                            not isinstance(value, str)
                            or not value.strip()
                            or value != value.strip()
                            for value in values
                        )
                        for values in metadata_value_sets
                    )
                    or (
                        identity.opf_grade_values is not None
                        and (
                            not isinstance(identity.opf_grade_values, tuple)
                            or any(
                                not isinstance(value, str)
                                or not value.strip()
                                or value != value.strip()
                                for value in identity.opf_grade_values
                            )
                        )
                    )
                    or (
                        identity.container_sha256 is not None
                        and SHA256_RE.fullmatch(identity.container_sha256) is None
                    )
                ):
                    raise CommercialSourceError(
                        "source_spec_EPUB_subject_grade_or_metadata_identity_invalid"
                    )
                if (
                    source.license_id != identity.resolved_license_id
                    or identity.catalogue_license_id != "CC-BY-3.0"
                    or identity.artifact_notice_license_id != "CC-BY-4.0"
                ):
                    raise CommercialSourceError(
                        "source_spec_EPUB_rights_conflict_invalid"
                    )
                if (
                    len(payload_evidence) != 1
                    or payload_evidence[0].locator_kind != "zip_member"
                    or payload_evidence[0].locator != identity.rights_member_path
                    or payload_evidence[0].sha256 != identity.rights_member_sha256
                    or payload_evidence[0].license_id != "CC-BY-4.0"
                ):
                    raise CommercialSourceError(
                        "source_spec_EPUB_payload_rights_binding_invalid"
                    )
            elif source.epub_identity is not None:
                raise CommercialSourceError("source_spec_unexpected_EPUB_identity")
            continue
        if SHA1_RE.fullmatch(source.commit_sha) is None:
            raise CommercialSourceError("source_spec_commit_sha_invalid")
        if SHA1_RE.fullmatch(source.tree_sha) is None:
            raise CommercialSourceError("source_spec_tree_sha_invalid")
        if SHA256_RE.fullmatch(source.license_sha256) is None:
            raise CommercialSourceError("source_spec_license_sha256_invalid")
        if source.selected_file_count <= 0 or source.selected_bytes <= 0:
            raise CommercialSourceError("source_spec_selected_identity_invalid")
        if any(
            not path or path.startswith(("/", "\\")) or ".." in path.split("/")
            for path in source.selected_paths
        ):
            raise CommercialSourceError("source_spec_selected_path_invalid")
    covered = {stage for source in sources for stage in source.stages}
    if covered != allowed_stages:
        raise CommercialSourceError("source_spec_stage_coverage_incomplete")


def validate_source_contract(value: Any) -> dict[str, Any]:
    if value != source_contract():
        raise CommercialSourceError("commercial_source_contract_mismatch")
    return json.loads(canonical_json_bytes(value))


def build_source_root(artifacts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    sources = (*DIRECT_SOURCES, *GIT_SOURCES)
    expected_ids = [source.source_id for source in sources]
    if any(not isinstance(artifact, Mapping) for artifact in artifacts):
        raise CommercialSourceError("source_artifact_not_mapping")
    observed_ids = [artifact.get("source_id") for artifact in artifacts]
    if observed_ids != expected_ids:
        raise CommercialSourceError("source_artifact_order_or_identity_mismatch")
    normalized = [
        _validate_artifact(artifact, expected)
        for artifact, expected in zip(artifacts, sources, strict=True)
    ]
    body = {
        "schema_version": SOURCE_ROOT_SCHEMA,
        "lane": LANE,
        "contract_root_sha256": source_contract()["contract_root_sha256"],
        "artifacts": normalized,
        "source_artifact_count": len(normalized),
        "hard_rejects": [dict(item) for item in HARD_REJECTS],
        "stage_source_ids": _stage_source_ids(normalized),
        "rights_classes": sorted(
            {artifact["license_class"] for artifact in normalized}
        ),
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
    return {**body, "source_root_sha256": canonical_sha256(body)}


def _stage_source_ids(artifacts: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    result = {stage: [] for stage in ("C1", "C2", "B23", "C3", "C4")}
    for artifact in artifacts:
        for stage in artifact["stages"]:
            result[stage].append(artifact["source_id"])
    if any(not sources for sources in result.values()):
        raise CommercialSourceError("stage_source_coverage_incomplete")
    return result


def _validate_artifact(
    value: Mapping[str, Any], expected: DirectSourceSpec | GitSourceSpec
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise CommercialSourceError("source_artifact_not_mapping")
    required = {
        "source_id",
        "acquisition_mode",
        "release_identity",
        "stages",
        "license_id",
        "license_class",
        "rights_proof",
        "bytes",
        "sha256",
        "local_locator",
        "content_manifest",
        "verification",
    }
    if set(value) != required:
        raise CommercialSourceError("source_artifact_field_set_mismatch")
    expected_fields = {
        "source_id": expected.source_id,
        "acquisition_mode": expected.acquisition_mode,
        "release_identity": expected.release_identity,
        "stages": list(expected.stages),
        "license_id": expected.license_id,
        "license_class": expected.license_class,
        "rights_proof": expected.rights_proof,
    }
    for field, expected_value in expected_fields.items():
        if value[field] != expected_value:
            raise CommercialSourceError(f"source_artifact_{field}_mismatch")
    if value["license_class"] not in {"A", "B"}:
        raise CommercialSourceError("source_artifact_license_not_commercial_default")
    byte_count = value["bytes"]
    if type(byte_count) is not int or byte_count <= 0:
        raise CommercialSourceError("source_artifact_bytes_invalid")
    expected_bytes = (
        expected.expected_bytes
        if isinstance(expected, DirectSourceSpec)
        else expected.selected_bytes
    )
    if byte_count != expected_bytes:
        raise CommercialSourceError("source_artifact_bytes_mismatch")
    digest = value["sha256"]
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        raise CommercialSourceError("source_artifact_sha256_invalid")
    if SHA256_RE.fullmatch(digest.removeprefix("sha256:")) is None:
        raise CommercialSourceError("source_artifact_sha256_invalid")
    if (
        isinstance(expected, DirectSourceSpec)
        and expected.expected_sha256 is not None
        and digest != "sha256:" + expected.expected_sha256
    ):
        raise CommercialSourceError("source_artifact_expected_sha256_mismatch")
    stages = value["stages"]
    if not isinstance(stages, list) or not stages:
        raise CommercialSourceError("source_artifact_stages_invalid")
    if any(stage not in {"C1", "C2", "B23", "C3", "C4"} for stage in stages):
        raise CommercialSourceError("source_artifact_stage_unknown")
    _validate_local_locator(value["local_locator"])
    if type(value["verification"]) is not dict:
        raise CommercialSourceError("source_artifact_verification_invalid")
    _validate_verification(value["verification"], expected)
    _validate_content_manifest(value, expected)
    return json.loads(canonical_json_bytes(dict(value)))


def _validate_content_manifest(
    artifact: Mapping[str, Any], expected: DirectSourceSpec | GitSourceSpec
) -> None:
    manifest = artifact["content_manifest"]
    if not isinstance(manifest, Mapping):
        raise CommercialSourceError("source_artifact_content_manifest_invalid")
    manifest_digest = canonical_sha256(manifest)
    if artifact["verification"].get("content_manifest_sha256") != manifest_digest:
        raise CommercialSourceError("source_artifact_content_manifest_hash_mismatch")
    if isinstance(expected, DirectSourceSpec):
        expected_manifest = {
            "schema_version": "cur0s_direct_content_manifest_v1",
            "files": [
                {
                    "relative_path": artifact["local_locator"],
                    "bytes": artifact["bytes"],
                    "sha256": artifact["sha256"],
                }
            ],
        }
        if manifest != expected_manifest:
            raise CommercialSourceError("source_artifact_direct_manifest_mismatch")
        return
    if set(manifest) != {"schema_version", "commit_sha", "tree_sha", "files"}:
        raise CommercialSourceError("source_artifact_git_manifest_field_set_mismatch")
    if (
        manifest["schema_version"] != "cur0s_git_sparse_content_manifest_v1"
        or manifest["commit_sha"] != expected.commit_sha
        or manifest["tree_sha"] != expected.tree_sha
        or artifact["sha256"] != manifest_digest
    ):
        raise CommercialSourceError("source_artifact_git_manifest_identity_mismatch")
    files = manifest["files"]
    if not isinstance(files, list) or len(files) != expected.selected_file_count:
        raise CommercialSourceError("source_artifact_git_manifest_count_mismatch")
    paths: list[str] = []
    selected_bytes = 0
    for entry in files:
        if not isinstance(entry, Mapping) or set(entry) != {
            "relative_path",
            "bytes",
            "sha256",
        }:
            raise CommercialSourceError("source_artifact_git_manifest_entry_invalid")
        _validate_local_locator(entry["relative_path"])
        byte_count = entry["bytes"]
        if type(byte_count) is not int or byte_count < 0:
            raise CommercialSourceError("source_artifact_git_manifest_bytes_invalid")
        _validate_prefixed_sha256(
            entry["sha256"], "source_artifact_git_manifest_sha256_invalid"
        )
        paths.append(entry["relative_path"])
        selected_bytes += byte_count
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise CommercialSourceError("source_artifact_git_manifest_paths_invalid")
    if selected_bytes != expected.selected_bytes:
        raise CommercialSourceError("source_artifact_git_manifest_bytes_mismatch")


def _validate_local_locator(value: Any) -> None:
    if not isinstance(value, str) or not value or value.startswith(("/", "\\")):
        raise CommercialSourceError("source_artifact_local_locator_invalid")
    if "\\" in value or "\x00" in value:
        raise CommercialSourceError("source_artifact_local_locator_invalid")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise CommercialSourceError("source_artifact_local_locator_invalid")


def _validate_verification(
    value: Mapping[str, Any], expected: DirectSourceSpec | GitSourceSpec
) -> None:
    required = (
        _DIRECT_VERIFICATION_FIELDS
        if isinstance(expected, DirectSourceSpec)
        else _GIT_VERIFICATION_FIELDS
    )
    if set(value) != required:
        raise CommercialSourceError("source_artifact_verification_field_set_mismatch")
    for field in required & _TRUE_VERIFICATION_FIELDS:
        if value[field] is not True:
            raise CommercialSourceError(f"source_artifact_{field}_not_verified")
    _validate_prefixed_sha256(
        value["content_manifest_sha256"],
        "source_artifact_content_manifest_sha256_invalid",
    )
    if isinstance(expected, DirectSourceSpec):
        if value["conditional_lock_mode"] != expected.conditional_lock_mode:
            raise CommercialSourceError(
                "source_artifact_conditional_lock_mode_mismatch"
            )
        if value["observed_etag"] != expected.expected_etag:
            raise CommercialSourceError("source_artifact_observed_etag_mismatch")
        if value["observed_last_modified"] != expected.expected_last_modified:
            raise CommercialSourceError(
                "source_artifact_observed_last_modified_mismatch"
            )
        if value["observed_final_url"] != expected.url:
            raise CommercialSourceError("source_artifact_observed_final_url_mismatch")
        server_lock_expected = expected.conditional_lock_mode == (
            "if_match_enforced_observed_412_on_mismatch"
        )
        if value["server_conditional_lock_enforced"] is not server_lock_expected:
            raise CommercialSourceError(
                "source_artifact_server_conditional_lock_mismatch"
            )
        if value["transport_conditionals_identity_role"] != "defense_in_depth_only":
            raise CommercialSourceError(
                "source_artifact_transport_conditionals_role_mismatch"
            )
        if value["rights_admission_basis"] != expected.rights_admission_basis:
            raise CommercialSourceError(
                "source_artifact_rights_admission_basis_mismatch"
            )
        if value["external_rights_evidence_used_for_admission"] is not False:
            raise CommercialSourceError(
                "source_artifact_external_rights_evidence_used_for_admission"
            )
        observed_rights = value["observed_payload_rights_evidence"]
        expected_rights = expected.expected_payload_rights_records()
        if observed_rights != expected_rights:
            raise CommercialSourceError(
                "source_artifact_payload_rights_evidence_mismatch"
            )
        expected_rights_root = canonical_sha256(expected_rights)
        if value["payload_rights_evidence_root_sha256"] != expected_rights_root:
            raise CommercialSourceError(
                "source_artifact_payload_rights_evidence_root_mismatch"
            )
        content_type = value["observed_content_type"]
        if content_type is not None:
            if not isinstance(content_type, str) or (
                content_type.split(";", 1)[0].strip().lower()
                != expected.media_type.split(";", 1)[0].strip().lower()
            ):
                raise CommercialSourceError(
                    "source_artifact_observed_content_type_mismatch"
                )
        return
    observed = {
        "observed_commit_sha": expected.commit_sha,
        "observed_tree_sha": expected.tree_sha,
        "observed_license_sha256": "sha256:" + expected.license_sha256,
        "observed_file_count": expected.selected_file_count,
        "observed_selected_bytes": expected.selected_bytes,
    }
    for field, expected_value in observed.items():
        if value[field] != expected_value:
            raise CommercialSourceError(f"source_artifact_{field}_mismatch")


def _validate_prefixed_sha256(value: Any, error: str) -> None:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise CommercialSourceError(error)
    if SHA256_RE.fullmatch(value.removeprefix("sha256:")) is None:
        raise CommercialSourceError(error)


def _validate_json_tree(value: Any, seen: set[int] | None = None) -> None:
    if seen is None:
        seen = set()
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CommercialSourceError("nonfinite_json_number")
        return
    if isinstance(value, (list, tuple, dict)):
        identity = id(value)
        if identity in seen:
            raise CommercialSourceError("cyclic_json_value")
        seen.add(identity)
        try:
            children = value.items() if isinstance(value, dict) else enumerate(value)
            for key, child in children:
                if isinstance(value, dict) and not isinstance(key, str):
                    raise CommercialSourceError("json_key_not_string")
                _validate_json_tree(child, seen)
        finally:
            seen.remove(identity)
        return
    raise CommercialSourceError("unsupported_json_value")


__all__ = [
    "CONTRACT_SCHEMA",
    "DIRECT_SOURCES",
    "GIT_SOURCES",
    "HARD_REJECTS",
    "LANE",
    "NATIVE_LAUNCH_CONTRACT_SCHEMA",
    "NATIVE_LAUNCH_ENVELOPE_SCHEMA",
    "NATIVE_OUTER_ENVIRONMENT",
    "NATIVE_OUTER_ENVIRONMENT_SHA256",
    "NATIVE_PREFLIGHT_BUILD_INCLUDE_TREES",
    "NATIVE_PREFLIGHT_BUILD_LINK_INPUTS",
    "NATIVE_PREFLIGHT_BUILD_DRIVER_LAUNCH_ENVIRONMENT",
    "NATIVE_PREFLIGHT_BUILD_SCHEMA",
    "NATIVE_PREFLIGHT_BUILD_TOOL_RUNTIME_GRAPH",
    "NATIVE_PREFLIGHT_BUILD_TOOL_RUNTIME_IDENTITY",
    "NATIVE_PREFLIGHT_BUILD_TOOL_RUNTIME_INPUTS",
    "NATIVE_PREFLIGHT_BUILD_TOOL_RUNTIME_SONAME_ROLES",
    "NATIVE_PREFLIGHT_BUILD_TREE_CANONICALIZATION",
    "NATIVE_PREFLIGHT_COMPILE_ARGV_TEMPLATE",
    "NATIVE_PREFLIGHT_CONTRACT_SCHEMA",
    "NATIVE_PREFLIGHT_FIXED_FD_MAP",
    "NATIVE_PREFLIGHT_MANIFEST_HEADER",
    "NATIVE_PREFLIGHT_SECURITY_CEILING",
    "NATIVE_PREFLIGHT_SOURCE_COMMIT_BINDING_STATUS",
    "NATIVE_PREFLIGHT_SOURCE_FILES",
    "NATIVE_PREFLIGHT_RUNTIME_DEPENDENCY_CLOSURE_SCHEMA",
    "NATIVE_PREFLIGHT_LINK_ARGV_TEMPLATE",
    "NATIVE_PREFLIGHT_TOOLCHAIN_CLOSURE_SCHEMA",
    "NATIVE_PREFLIGHT_TREE_CANONICALIZATION",
    "SOURCE_ROOT_SCHEMA",
    "CommercialSourceError",
    "DirectSourceSpec",
    "GitSourceSpec",
    "build_native_preflight_execution_contract",
    "build_native_launch_envelope",
    "build_native_preflight_manifest_bytes",
    "build_native_preflight_static_manifest_records",
    "build_source_root",
    "canonical_json_bytes",
    "canonical_sha256",
    "native_preflight_execution_layout",
    "native_preflight_build_python_runtime_identity",
    "native_outer_launch_contract",
    "phone_thermal_safety_contract",
    "phone_toolchain_contract",
    "source_contract",
    "validate_native_preflight_build_receipt",
    "validate_source_contract",
]
