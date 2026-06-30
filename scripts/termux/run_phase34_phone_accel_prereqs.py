#!/usr/bin/env python3
"""Collect non-gating Phase 3/4 phone acceleration prerequisites in Termux."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import datetime as dt
import glob
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Protocol, Sequence


SCHEMA_VERSION = "polar_phase34_phone_accel_prereqs_v1"
DEFAULT_LABEL = "phase34_phone_accel_prereqs"
DEFAULT_PROBE_TIMEOUT_SEC = 2.0
MAX_STDIO_CHARS = 2048
MAX_MEMINFO_BYTES = 64 * 1024

GETPROP_FIELDS: tuple[tuple[str, str], ...] = (
    ("ro.product.cpu.abi", "primary_abi"),
    ("ro.product.cpu.abi2", "secondary_abi"),
    ("ro.product.cpu.abilist", "abi_list"),
    ("ro.build.version.sdk", "api_level"),
    ("ro.build.version.release", "android_release"),
    ("ro.product.manufacturer", "manufacturer"),
    ("ro.product.brand", "brand"),
    ("ro.product.model", "model"),
    ("ro.product.device", "device"),
    ("ro.product.board", "product_board"),
    ("ro.board.platform", "board_platform"),
    ("ro.hardware", "hardware"),
    ("ro.soc.manufacturer", "soc_manufacturer"),
    ("ro.soc.model", "soc_model"),
    ("ro.vendor.qti.soc_name", "qti_soc_name"),
    ("ro.vendor.qti.hardware.sku", "qti_hardware_sku"),
)

MEMINFO_KEYS = (
    "MemTotal",
    "MemFree",
    "MemAvailable",
    "Buffers",
    "Cached",
    "SwapTotal",
    "SwapFree",
)

TERMUX_STORAGE_PATHS: tuple[tuple[str, str], ...] = (
    ("termux_home", "/data/data/com.termux/files/home"),
    ("termux_prefix", "/data/data/com.termux/files/usr"),
    ("shared_storage_sdcard", "/sdcard"),
    ("shared_storage_emulated0", "/storage/emulated/0"),
    ("shared_storage_primary", "/storage/self/primary"),
)

QNN_LIBRARY_EXACT_PATHS = (
    "/vendor/lib64/libQnnSystem.so",
    "/vendor/lib64/libQnnCpu.so",
    "/vendor/lib64/libQnnGpu.so",
    "/vendor/lib64/libQnnHtp.so",
    "/vendor/lib64/libQnnHtpPrepare.so",
    "/vendor/lib64/libQnnHtpNetRunExtensions.so",
    "/vendor/lib64/libQnnHtpV68Stub.so",
    "/vendor/lib64/libQnnHtpV69Stub.so",
    "/vendor/lib64/libQnnHtpV73Stub.so",
    "/vendor/lib64/libQnnHtpV75Stub.so",
    "/vendor/lib64/libQnnHtpV79Stub.so",
    "/vendor/lib64/libcdsprpc.so",
    "/vendor/lib64/libadsprpc.so",
    "/system/vendor/lib64/libQnnHtp.so",
    "/system/vendor/lib64/libcdsprpc.so",
    "/data/data/com.termux/files/usr/lib/libQnnSystem.so",
    "/data/data/com.termux/files/usr/lib/libQnnHtp.so",
    "/data/local/tmp/qnn/lib/aarch64-android/libQnnSystem.so",
    "/data/local/tmp/qnn/lib/aarch64-android/libQnnHtp.so",
    "/data/local/tmp/qairt/lib/aarch64-android/libQnnSystem.so",
    "/data/local/tmp/qairt/lib/aarch64-android/libQnnHtp.so",
)

QNN_LIBRARY_GLOBS = (
    "/vendor/lib64/libQnn*.so",
    "/vendor/lib/libQnn*.so",
    "/odm/lib64/libQnn*.so",
    "/system/vendor/lib64/libQnn*.so",
    "/vendor/dsp/cdsp/libQnnHtp*.so",
    "/vendor/lib/rfsa/adsp/libQnnHtp*.so",
    "/system/lib/rfsa/adsp/libQnnHtp*.so",
    "/data/data/com.termux/files/usr/lib/libQnn*.so",
    "/data/local/tmp/qnn/lib/aarch64-android/libQnn*.so",
    "/data/local/tmp/qairt/lib/aarch64-android/libQnn*.so",
    "/sdcard/qnn/lib/aarch64-android/libQnn*.so",
    "/sdcard/Download/qnn/lib/aarch64-android/libQnn*.so",
    "/sdcard/qairt/lib/aarch64-android/libQnn*.so",
    "/sdcard/Download/qairt/lib/aarch64-android/libQnn*.so",
)

QNN_TOOL_NAMES = (
    "qnn-net-run",
    "qnn-throughput-net-run",
    "qnn-platform-validator",
    "qnn-profile-viewer",
)

QNN_TOOL_EXACT_PATHS = (
    "/data/data/com.termux/files/usr/bin/qnn-net-run",
    "/data/data/com.termux/files/usr/bin/qnn-throughput-net-run",
    "/data/data/com.termux/files/usr/bin/qnn-platform-validator",
    "/data/local/tmp/qnn/bin/aarch64-android/qnn-net-run",
    "/data/local/tmp/qnn/bin/aarch64-android/qnn-throughput-net-run",
    "/data/local/tmp/qnn/bin/aarch64-android/qnn-platform-validator",
    "/data/local/tmp/qairt/bin/aarch64-android/qnn-net-run",
    "/data/local/tmp/qairt/bin/aarch64-android/qnn-throughput-net-run",
    "/data/local/tmp/qairt/bin/aarch64-android/qnn-platform-validator",
    "/sdcard/qnn/bin/aarch64-android/qnn-net-run",
    "/sdcard/Download/qnn/bin/aarch64-android/qnn-net-run",
    "/sdcard/qairt/bin/aarch64-android/qnn-net-run",
    "/sdcard/Download/qairt/bin/aarch64-android/qnn-net-run",
)

OPENCL_LIBRARY_EXACT_PATHS = (
    "/vendor/lib64/libOpenCL.so",
    "/vendor/lib/libOpenCL.so",
    "/system/vendor/lib64/libOpenCL.so",
    "/system/vendor/lib/libOpenCL.so",
    "/system/lib64/libOpenCL.so",
    "/system/lib/libOpenCL.so",
    "/data/data/com.termux/files/usr/lib/libOpenCL.so",
)

OPENCL_LIBRARY_GLOBS = (
    "/vendor/etc/OpenCL/vendors/*.icd",
    "/system/vendor/etc/OpenCL/vendors/*.icd",
    "/data/data/com.termux/files/usr/etc/OpenCL/vendors/*.icd",
)

OPENCL_TOOL_NAMES = ("clinfo",)
OPENCL_TOOL_EXACT_PATHS = ("/data/data/com.termux/files/usr/bin/clinfo",)

VULKAN_LIBRARY_EXACT_PATHS = (
    "/vendor/lib64/libvulkan.so",
    "/vendor/lib/libvulkan.so",
    "/system/lib64/libvulkan.so",
    "/system/lib/libvulkan.so",
    "/data/data/com.termux/files/usr/lib/libvulkan.so",
)

VULKAN_LIBRARY_GLOBS = (
    "/vendor/lib64/hw/vulkan.*.so",
    "/vendor/lib/hw/vulkan.*.so",
    "/system/lib64/hw/vulkan.*.so",
    "/system/lib/hw/vulkan.*.so",
)

VULKAN_TOOL_NAMES = ("vulkaninfo", "vkvia")
VULKAN_TOOL_EXACT_PATHS = (
    "/data/data/com.termux/files/usr/bin/vulkaninfo",
    "/data/data/com.termux/files/usr/bin/vkvia",
)

GPU_LIBRARY_EXACT_PATHS = (
    "/vendor/lib64/libadreno_utils.so",
    "/vendor/lib64/libgsl.so",
    "/vendor/lib64/egl/libEGL_adreno.so",
    "/vendor/lib64/egl/libGLESv2_adreno.so",
    "/vendor/lib64/egl/libGLESv1_CM_adreno.so",
)

GPU_LIBRARY_GLOBS = (
    "/vendor/lib64/egl/lib*_adreno.so",
    "/vendor/lib/egl/lib*_adreno.so",
    "/vendor/lib64/libadreno*.so",
    "/vendor/lib/libadreno*.so",
    "/vendor/lib64/libGLES*.so",
    "/vendor/lib/libGLES*.so",
)

COMMAND_PROBE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "name": "qnn_net_run_help",
        "tool": "qnn-net-run",
        "args": ["--help"],
        "exact_paths": QNN_TOOL_EXACT_PATHS,
    },
    {
        "name": "qnn_platform_validator_help",
        "tool": "qnn-platform-validator",
        "args": ["--help"],
        "exact_paths": QNN_TOOL_EXACT_PATHS,
    },
    {
        "name": "clinfo_list",
        "tool": "clinfo",
        "args": ["-l"],
        "exact_paths": OPENCL_TOOL_EXACT_PATHS,
    },
    {
        "name": "vulkaninfo_summary",
        "tool": "vulkaninfo",
        "args": ["--summary"],
        "exact_paths": VULKAN_TOOL_EXACT_PATHS,
    },
)

FORBIDDEN_COMMAND_BASENAMES = {"env", "printenv", "sh", "bash", "zsh", "dash"}
CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


@dataclass(frozen=True)
class CommandResult:
    returncode: int | None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    error: str | None = None


@dataclass(frozen=True)
class TextReadResult:
    present: bool
    text: str = ""
    error: str | None = None


class CommandRunner(Protocol):
    def run(self, command: Sequence[str], timeout_sec: float) -> CommandResult:
        """Run one allowlisted command without a shell."""


class SubprocessRunner:
    def run(self, command: Sequence[str], timeout_sec: float) -> CommandResult:
        validate_command(command)
        try:
            completed = subprocess.run(
                list(command),
                text=True,
                capture_output=True,
                timeout=timeout_sec,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                returncode=None,
                stdout=sanitize_text(exc.stdout),
                stderr=sanitize_text(exc.stderr),
                timed_out=True,
                error=f"timeout_after_{timeout_sec:g}_sec",
            )
        except OSError as exc:
            return CommandResult(
                returncode=None,
                stdout="",
                stderr="",
                timed_out=False,
                error=f"{type(exc).__name__}: {exc}",
            )
        return CommandResult(
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            timed_out=False,
            error=None,
        )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional JSON report path; full JSON is also printed")
    parser.add_argument("--label", default=DEFAULT_LABEL)
    parser.add_argument("--probe-timeout-sec", type=float, default=DEFAULT_PROBE_TIMEOUT_SEC)
    parser.add_argument("--skip-command-probes", action="store_true")
    return parser.parse_args(argv)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_command(command: Sequence[str]) -> None:
    if not command:
        raise ValueError("empty command is not allowed")
    basename = Path(command[0]).name
    if basename in FORBIDDEN_COMMAND_BASENAMES:
        raise ValueError(f"forbidden probe command: {basename}")


def sanitize_text(value: str | bytes | None, limit: int = MAX_STDIO_CHARS) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = value
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = CONTROL_CHARS_RE.sub("?", text)
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    return f"{text[:limit]}...[truncated {omitted} chars]"


def command_result_payload(command: Sequence[str], result: CommandResult) -> dict[str, Any]:
    status = "timeout" if result.timed_out else "ok"
    if result.error and not result.timed_out:
        status = "error"
    return {
        "command": list(command),
        "status": status,
        "returncode": result.returncode,
        "timed_out": result.timed_out,
        "stdout_first_2048": sanitize_text(result.stdout),
        "stderr_first_2048": sanitize_text(result.stderr),
        "error": result.error,
    }


def run_scalar_command(
    runner: CommandRunner,
    command: Sequence[str],
    timeout_sec: float,
    *,
    max_chars: int = 512,
) -> dict[str, Any]:
    result = runner.run(command, timeout_sec)
    value = sanitize_text(result.stdout, limit=max_chars).strip()
    if result.returncode != 0 or result.timed_out or result.error:
        value = None
    return {
        "command": list(command),
        "value": value,
        "returncode": result.returncode,
        "timed_out": result.timed_out,
        "error": result.error,
    }


def collect_uname(runner: CommandRunner, timeout_sec: float) -> dict[str, Any]:
    return {
        "system": run_scalar_command(runner, ["uname", "-s"], timeout_sec),
        "kernel_release": run_scalar_command(runner, ["uname", "-r"], timeout_sec),
        "machine": run_scalar_command(runner, ["uname", "-m"], timeout_sec),
        "all": run_scalar_command(runner, ["uname", "-a"], timeout_sec, max_chars=1024),
    }


def collect_getprop(runner: CommandRunner, timeout_sec: float) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    aliases: dict[str, str | None] = {}
    for prop_name, alias in GETPROP_FIELDS:
        result = run_scalar_command(runner, ["getprop", prop_name], timeout_sec, max_chars=256)
        fields[prop_name] = result
        aliases[alias] = result["value"]
    return {
        "selected_fields": fields,
        "android_summary": {
            "primary_abi": aliases["primary_abi"],
            "secondary_abi": aliases["secondary_abi"],
            "abi_list": aliases["abi_list"],
            "api_level": aliases["api_level"],
            "android_release": aliases["android_release"],
            "manufacturer": aliases["manufacturer"],
            "brand": aliases["brand"],
            "model": aliases["model"],
            "device": aliases["device"],
            "platform": first_present(
                aliases["board_platform"],
                aliases["hardware"],
                aliases["soc_model"],
                aliases["product_board"],
            ),
            "soc_manufacturer": aliases["soc_manufacturer"],
            "soc_model": aliases["soc_model"],
            "qti_soc_name": aliases["qti_soc_name"],
            "qti_hardware_sku": aliases["qti_hardware_sku"],
        },
        "privacy_note": "Only an explicit low-sensitivity getprop allowlist is queried.",
    }


def first_present(*values: str | None) -> str | None:
    for value in values:
        if value:
            return value
    return None


def read_text_prefix(path: str, max_bytes: int) -> TextReadResult:
    try:
        with Path(path).open("rb") as handle:
            data = handle.read(max_bytes + 1)
    except OSError as exc:
        return TextReadResult(present=False, error=f"{type(exc).__name__}: {exc}")
    text = data[:max_bytes].decode("utf-8", errors="replace")
    if len(data) > max_bytes:
        text = f"{text}\n...[truncated after {max_bytes} bytes]"
    return TextReadResult(present=True, text=text)


def parse_meminfo(text: str) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for line in text.splitlines():
        name, separator, remainder = line.partition(":")
        if not separator or name not in MEMINFO_KEYS:
            continue
        parts = remainder.strip().split()
        if not parts:
            continue
        try:
            value_kb = int(parts[0])
        except ValueError:
            continue
        unit = parts[1] if len(parts) > 1 else "kB"
        summary[name] = {
            "kb": value_kb,
            "bytes": value_kb * 1024 if unit == "kB" else None,
            "unit": unit,
        }
    return summary


def collect_meminfo() -> dict[str, Any]:
    path = "/proc/meminfo"
    result = read_text_prefix(path, MAX_MEMINFO_BYTES)
    return {
        "path": path,
        "present": result.present,
        "error": result.error,
        "summary": parse_meminfo(result.text) if result.present else {},
    }


def path_presence(path: str) -> dict[str, Any]:
    candidate = Path(path)
    try:
        return {
            "path": path,
            "present": candidate.exists(),
            "inaccessible": False,
            "error": None,
        }
    except PermissionError as exc:
        return {
            "path": path,
            "present": True,
            "inaccessible": True,
            "error": f"{type(exc).__name__}: {exc}",
        }
    except OSError as exc:
        return {
            "path": path,
            "present": False,
            "inaccessible": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def file_exists(path: str) -> bool:
    return bool(path_presence(path)["present"])


def is_executable(path: str) -> bool:
    candidate = Path(path)
    try:
        return candidate.is_file() and os.access(candidate, os.X_OK)
    except OSError:
        return False


def glob_paths(pattern: str) -> list[str]:
    return sorted(glob.glob(pattern))


def which_tool(name: str) -> str | None:
    return shutil.which(name)


def disk_usage_bytes(path: str) -> dict[str, int]:
    usage = shutil.disk_usage(path)
    return {
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
    }


def collect_df_summary(cwd: Path | None = None) -> list[dict[str, Any]]:
    candidates = [("cwd", str(cwd or Path.cwd())), *TERMUX_STORAGE_PATHS]
    seen: set[str] = set()
    summaries: list[dict[str, Any]] = []
    for label, path in candidates:
        if path in seen:
            continue
        seen.add(path)
        present = file_exists(path)
        summary: dict[str, Any] = {
            "label": label,
            "path": path,
            "present": present,
            "usage": None,
            "error": None,
        }
        if present:
            try:
                summary["usage"] = disk_usage_bytes(path)
            except OSError as exc:
                summary["error"] = f"{type(exc).__name__}: {exc}"
        summaries.append(summary)
    return summaries


def scan_exact_paths(paths: Sequence[str]) -> list[dict[str, Any]]:
    return [path_presence(path) for path in paths]


def scan_glob_patterns(patterns: Sequence[str]) -> list[dict[str, Any]]:
    scans = []
    for pattern in patterns:
        scans.append({"pattern": pattern, "matches": glob_paths(pattern)})
    return scans


def scan_tools(names: Sequence[str], exact_paths: Sequence[str]) -> dict[str, Any]:
    exact = []
    for path in exact_paths:
        presence = path_presence(path)
        presence["executable"] = is_executable(path) if presence["present"] else False
        exact.append(presence)
    path_lookup = [{"name": name, "path": which_tool(name)} for name in names]
    return {"path_lookup": path_lookup, "exact_paths": exact}


def any_exact_present(scans: Sequence[dict[str, Any]]) -> bool:
    return any(bool(item.get("present")) for item in scans)


def any_glob_present(scans: Sequence[dict[str, Any]]) -> bool:
    return any(bool(item.get("matches")) for item in scans)


def any_tool_present(scan: dict[str, Any]) -> bool:
    return any(bool(item.get("path")) for item in scan["path_lookup"]) or any(
        bool(item.get("present")) for item in scan["exact_paths"]
    )


def collect_accelerator_presence() -> dict[str, Any]:
    qnn_libraries = scan_exact_paths(QNN_LIBRARY_EXACT_PATHS)
    qnn_library_globs = scan_glob_patterns(QNN_LIBRARY_GLOBS)
    qnn_tools = scan_tools(QNN_TOOL_NAMES, QNN_TOOL_EXACT_PATHS)

    opencl_libraries = scan_exact_paths(OPENCL_LIBRARY_EXACT_PATHS)
    opencl_library_globs = scan_glob_patterns(OPENCL_LIBRARY_GLOBS)
    opencl_tools = scan_tools(OPENCL_TOOL_NAMES, OPENCL_TOOL_EXACT_PATHS)

    vulkan_libraries = scan_exact_paths(VULKAN_LIBRARY_EXACT_PATHS)
    vulkan_library_globs = scan_glob_patterns(VULKAN_LIBRARY_GLOBS)
    vulkan_tools = scan_tools(VULKAN_TOOL_NAMES, VULKAN_TOOL_EXACT_PATHS)

    gpu_libraries = scan_exact_paths(GPU_LIBRARY_EXACT_PATHS)
    gpu_library_globs = scan_glob_patterns(GPU_LIBRARY_GLOBS)

    qnn_present = (
        any_exact_present(qnn_libraries)
        or any_glob_present(qnn_library_globs)
        or any_tool_present(qnn_tools)
    )
    opencl_present = (
        any_exact_present(opencl_libraries)
        or any_glob_present(opencl_library_globs)
        or any_tool_present(opencl_tools)
    )
    vulkan_present = (
        any_exact_present(vulkan_libraries)
        or any_glob_present(vulkan_library_globs)
        or any_tool_present(vulkan_tools)
    )
    gpu_present = any_exact_present(gpu_libraries) or any_glob_present(gpu_library_globs)

    return {
        "qnn_qairt_htp": {
            "any_present": qnn_present,
            "libraries": qnn_libraries,
            "library_globs": qnn_library_globs,
            "tools": qnn_tools,
        },
        "opencl": {
            "any_present": opencl_present,
            "libraries": opencl_libraries,
            "library_globs": opencl_library_globs,
            "tools": opencl_tools,
        },
        "vulkan": {
            "any_present": vulkan_present,
            "libraries": vulkan_libraries,
            "library_globs": vulkan_library_globs,
            "tools": vulkan_tools,
        },
        "gpu_driver": {
            "any_present": gpu_present,
            "libraries": gpu_libraries,
            "library_globs": gpu_library_globs,
        },
        "summary": {
            "qnn_qairt_htp_present": qnn_present,
            "opencl_present": opencl_present,
            "vulkan_present": vulkan_present,
            "gpu_driver_present": gpu_present,
            "presence_is_not_functionality": True,
        },
    }


def resolve_tool_command(tool_name: str, exact_paths: Sequence[str]) -> str | None:
    found = which_tool(tool_name)
    if found:
        return found
    for path in exact_paths:
        if Path(path).name == tool_name and is_executable(path):
            return path
    return None


def collect_command_probes(
    runner: CommandRunner,
    timeout_sec: float,
    *,
    enabled: bool,
) -> dict[str, Any]:
    if not enabled:
        return {"enabled": False, "timeout_sec": timeout_sec, "probes": []}

    probes = []
    for spec in COMMAND_PROBE_SPECS:
        command_path = resolve_tool_command(spec["tool"], spec["exact_paths"])
        if not command_path:
            probes.append(
                {
                    "name": spec["name"],
                    "tool": spec["tool"],
                    "status": "skipped_missing_tool",
                    "command": None,
                }
            )
            continue
        command = [command_path, *spec["args"]]
        result = runner.run(command, timeout_sec)
        payload = command_result_payload(command, result)
        payload["name"] = spec["name"]
        payload["tool"] = spec["tool"]
        probes.append(payload)

    return {
        "enabled": True,
        "timeout_sec": timeout_sec,
        "probes": probes,
        "note": "Probe commands are lightweight --help, summary, or list forms only.",
    }


def build_payload(
    *,
    label: str = DEFAULT_LABEL,
    runner: CommandRunner | None = None,
    probe_timeout_sec: float = DEFAULT_PROBE_TIMEOUT_SEC,
    include_command_probes: bool = True,
    cwd: Path | None = None,
) -> dict[str, Any]:
    active_runner = runner or SubprocessRunner()
    device = {
        "uname": collect_uname(active_runner, probe_timeout_sec),
        "getprop": collect_getprop(active_runner, probe_timeout_sec),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "label": label,
        "created_at_utc": utc_now(),
        "status": "observed",
        "gate": {
            "enabled": False,
            "status": "not_applicable",
            "reason": "This probe records prerequisites only and cannot unlock Phase 3.",
        },
        "phase3_ready_claim": False,
        "nonclaims": [
            "no_phase3_ready_claim",
            "no_gate_pass_claim",
            "no_accelerator_execution_claim",
            "no_qnn_htp_functionality_claim",
            "no_opencl_vulkan_functionality_claim",
            "no_learning_claim",
            "no_model_quality_claim",
            "presence_only_prerequisite_inventory",
        ],
        "safety": {
            "shell_used_for_probes": False,
            "environment_variables_included": False,
            "env_files_read": False,
            "full_getprop_dump_used": False,
            "selected_getprop_allowlist": [name for name, _alias in GETPROP_FIELDS],
            "command_stdout_stderr_truncated_to_chars": MAX_STDIO_CHARS,
        },
        "device": device,
        "resources": {
            "meminfo": collect_meminfo(),
            "df_summary": collect_df_summary(cwd=cwd),
        },
        "accelerator_presence": collect_accelerator_presence(),
        "command_probes": collect_command_probes(
            active_runner,
            probe_timeout_sec,
            enabled=include_command_probes,
        ),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    payload = build_payload(
        label=args.label,
        probe_timeout_sec=args.probe_timeout_sec,
        include_command_probes=not args.skip_command_probes,
    )
    if args.output:
        write_json(args.output, payload)
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
