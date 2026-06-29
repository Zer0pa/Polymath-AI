#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACKETIZER_BIN = ROOT / "native/polar_phase2_packetizer/bin/phase2b_native_packetizer"
PACKETIZER_SOURCE = ROOT / "native/polar_phase2_packetizer/phase2b_native_packetizer.cpp"
PACKETIZER_BUILD_SCRIPT = ROOT / "native/polar_phase2_packetizer/build_phase2b_native_packetizer.sh"
RAW_SUFFIXES = {".pqa1", ".qai1", ".pjp1", ".safetensors", ".bin", ".pt", ".pth", ".onnx", ".tflite"}
HEX64_RE = re.compile(r"^[0-9a-fA-F]{64}$")

NONCLAIMS = [
    "c1_smoke_only",
    "no_100k_or_1m_phase2_authority_claim",
    "no_phase3_ready_claim",
    "no_npu_htp_claim",
    "no_learning_claim",
    "no_model_quality_claim",
]


class Phase2C1Error(RuntimeError):
    pass


def utc_iso() -> str:
    return dt.datetime.now(tz=dt.timezone.utc).isoformat().replace("+00:00", "Z")


def path_for_report(path: Path) -> str:
    return str(path.expanduser())


def resolve_loose(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def is_under(path: Path, parent: Path) -> bool:
    try:
        resolve_loose(path).relative_to(resolve_loose(parent))
        return True
    except ValueError:
        return False


def jwrite(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def file_identity(path: Path, *, hash_if_exists: bool = True) -> dict[str, Any]:
    expanded = path.expanduser()
    out: dict[str, Any] = {
        "path": path_for_report(expanded),
        "exists": expanded.exists(),
        "inside_git_worktree": is_under(expanded, ROOT),
    }
    if expanded.exists():
        stat = expanded.stat()
        out["bytes"] = stat.st_size
        out["is_file"] = expanded.is_file()
        out["is_executable"] = os.access(expanded, os.X_OK)
        if expanded.is_file() and hash_if_exists:
            out["sha256"] = sha256_file(expanded)
    return out


def require_hex64(name: str, value: str) -> str:
    if not HEX64_RE.fullmatch(value):
        raise Phase2C1Error(f"{name} must be a 64-character hex sha256")
    return value.lower()


def raw_suffix_paths_under_repo(paths: list[Path]) -> list[str]:
    bad: list[str] = []
    for path in paths:
        if path.suffix.lower() in RAW_SUFFIXES and is_under(path, ROOT):
            bad.append(path_for_report(path))
    return bad


def read_pqa1_list(path: Path, *, require_exists: bool) -> dict[str, Any]:
    expanded = path.expanduser()
    identity = file_identity(expanded)
    report: dict[str, Any] = {
        "list_file": identity,
        "line_count": None,
        "nonempty_line_count": None,
        "sample_paths": [],
        "listed_raw_paths_inside_git_worktree": [],
    }
    if not expanded.exists():
        if require_exists:
            raise Phase2C1Error(f"PQA1 list does not exist: {expanded}")
        return report
    if not expanded.is_file():
        raise Phase2C1Error(f"PQA1 list is not a file: {expanded}")

    text = expanded.read_text(encoding="utf-8")
    lines = text.splitlines()
    paths = [Path(line.strip()) for line in lines if line.strip()]
    report["line_count"] = len(lines)
    report["nonempty_line_count"] = len(paths)
    report["sample_paths"] = [path_for_report(path) for path in paths[:8]]
    report["listed_raw_paths_inside_git_worktree"] = raw_suffix_paths_under_repo(paths)
    if not paths and require_exists:
        raise Phase2C1Error(f"PQA1 list has no non-empty entries: {expanded}")
    if report["listed_raw_paths_inside_git_worktree"]:
        raise Phase2C1Error("PQA1 list points at raw payloads inside the git worktree")
    return report


def summarize_native_report(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    keys = [
        "schema_version",
        "status",
        "writer",
        "label",
        "thread_count",
        "job_count",
        "pqa1_files_consumed",
        "source_record_count",
        "source_real_token_count",
        "packet_count",
        "slot_count",
        "pqa1_source_sha256_stream",
        "pjp1_path",
        "pjp1_bytes",
        "timing_sec",
        "throughput",
        "worker_rollup",
    ]
    return {key: report[key] for key in keys if key in report}


def run_cmd(cmd: list[str], *, cwd: Path, timeout: int | None) -> dict[str, Any]:
    started = time.perf_counter()
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False)
    return {
        "cmd": cmd,
        "cwd": path_for_report(cwd),
        "returncode": proc.returncode,
        "elapsed_sec": time.perf_counter() - started,
        "stdout_tail": proc.stdout[-8000:],
        "stderr_tail": proc.stderr[-8000:],
    }


def validate_real_output_policy(output_dir: Path, pjp1_path: Path) -> None:
    if is_under(output_dir, ROOT) or is_under(pjp1_path, ROOT):
        raise Phase2C1Error(
            "real mode refuses to write raw PJP1 under the git worktree; "
            "use a Termux/private or /tmp output directory and copy metadata only"
        )


def artifact_hash_check(name: str, path: Path, expected_sha: str, *, required: bool) -> dict[str, Any]:
    expected = require_hex64(name, expected_sha)
    identity = file_identity(path, hash_if_exists=path.expanduser().exists())
    identity["expected_sha256"] = expected
    if not path.expanduser().exists():
        if required:
            raise Phase2C1Error(f"{name} artifact path does not exist: {path.expanduser()}")
        identity["sha256_match"] = None
        return identity
    actual = identity.get("sha256")
    identity["sha256_match"] = actual == expected
    if required and actual != expected:
        raise Phase2C1Error(f"{name} sha256 mismatch: expected {expected}, got {actual}")
    return identity


def make_command(args: argparse.Namespace, pjp1_path: Path, native_result_json: Path) -> list[str]:
    cmd = [
        path_for_report(args.packetizer_bin),
        "--label",
        args.run_label,
        "--pqa1-list",
        path_for_report(args.pqa1_list),
        "--output",
        path_for_report(pjp1_path),
        "--embedding",
        path_for_report(args.embedding),
        "--jl",
        path_for_report(args.jl),
        "--embed-sha",
        args.embedding_sha.lower(),
        "--embed-manifest-sha",
        args.embedding_manifest_sha.lower(),
        "--jl-sha",
        args.jl_sha.lower(),
        "--threads",
        str(args.threads),
        "--result-json",
        path_for_report(native_result_json),
    ]
    if args.max_records is not None:
        cmd.extend(["--max-records", str(args.max_records)])
    return cmd


def initial_report(args: argparse.Namespace, output_dir: Path, pjp1_path: Path, native_result_json: Path) -> dict[str, Any]:
    require_real = not args.dry_run
    packetizer_bin = args.packetizer_bin.expanduser()
    return {
        "schema_version": "polar_phase2_c1_smoke_wrapper_v1",
        "status": "dry_run_pending" if args.dry_run else "pending",
        "created_at_utc": utc_iso(),
        "run_label": args.run_label,
        "mode": "dry_run" if args.dry_run else "real",
        "nonclaims": NONCLAIMS,
        "raw_payload_policy": {
            "raw_payload_suffixes": sorted(RAW_SUFFIXES),
            "raw_payloads_allowed_in_git_worktree": False,
            "real_output_dir_inside_git_worktree": is_under(output_dir, ROOT),
            "dry_run_does_not_invoke_native_packetizer": args.dry_run,
        },
        "paths": {
            "repo_root": path_for_report(ROOT),
            "output_dir": path_for_report(output_dir),
            "pjp1_output": path_for_report(pjp1_path),
            "native_result_json": path_for_report(native_result_json),
            "wrapper_report": path_for_report(args.wrapper_report),
        },
        "input_identity": {
            "pqa1_list": read_pqa1_list(args.pqa1_list, require_exists=require_real),
            "embedding": artifact_hash_check(
                "embedding_sha", args.embedding, args.embedding_sha, required=require_real
            ),
            "embedding_manifest_sha256": require_hex64(
                "embedding_manifest_sha", args.embedding_manifest_sha
            ),
            "jl": artifact_hash_check("jl_sha", args.jl, args.jl_sha, required=require_real),
        },
        "packetizer_identity": {
            "binary": file_identity(packetizer_bin, hash_if_exists=packetizer_bin.exists()),
            "source": file_identity(PACKETIZER_SOURCE, hash_if_exists=PACKETIZER_SOURCE.exists()),
            "build_script": file_identity(PACKETIZER_BUILD_SCRIPT, hash_if_exists=PACKETIZER_BUILD_SCRIPT.exists()),
        },
        "execution_contract": {
            "threads": args.threads,
            "max_records": args.max_records,
            "c1_smoke_only": True,
        },
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run or dry-run the Phase 2 C1 PQA1-to-PJP1 native packetizer smoke contract."
    )
    parser.add_argument("--pqa1-list", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--run-label", required=True)
    parser.add_argument("--packetizer-bin", type=Path, default=DEFAULT_PACKETIZER_BIN)
    parser.add_argument("--embedding", type=Path, required=True)
    parser.add_argument("--embedding-sha", required=True)
    parser.add_argument("--embedding-manifest-sha", required=True)
    parser.add_argument("--jl", type=Path, required=True)
    parser.add_argument("--jl-sha", required=True)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--max-records", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout-sec", type=int, default=0, help="0 means no timeout in real mode.")
    parser.add_argument(
        "--wrapper-report",
        type=Path,
        help="Optional metadata report path. May be inside the repo because it is JSON-only.",
    )
    args = parser.parse_args(argv)

    if args.threads < 1:
        parser.error("--threads must be >= 1")
    if args.max_records is not None and args.max_records < 1:
        parser.error("--max-records must be >= 1 when supplied")
    if not re.fullmatch(r"[A-Za-z0-9_.=-]+", args.run_label):
        parser.error("--run-label may contain only letters, numbers, underscore, dash, dot, and equals")

    args.pqa1_list = resolve_loose(args.pqa1_list)
    args.output_dir = resolve_loose(args.output_dir)
    args.packetizer_bin = resolve_loose(args.packetizer_bin)
    args.embedding = resolve_loose(args.embedding)
    args.jl = resolve_loose(args.jl)
    if args.wrapper_report is None:
        args.wrapper_report = args.output_dir / f"{args.run_label}_phase2_c1_smoke_wrapper_report.json"
    else:
        args.wrapper_report = resolve_loose(args.wrapper_report)
        if args.wrapper_report.suffix.lower() != ".json":
            parser.error("--wrapper-report must point to a .json metadata file")
    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    output_dir = args.output_dir
    pjp1_path = output_dir / f"raw_{args.run_label}.pjp1"
    native_result_json = output_dir / f"{args.run_label}_native_packetizer_report.json"
    cmd = make_command(args, pjp1_path, native_result_json)

    try:
        if not args.dry_run:
            validate_real_output_policy(output_dir, pjp1_path)
        report = initial_report(args, output_dir, pjp1_path, native_result_json)
        report["native_command_argv"] = cmd

        if args.dry_run:
            report["status"] = "dry_run_pass"
            report["native_invoked"] = False
            jwrite(args.wrapper_report, report)
            print(json.dumps({"status": report["status"], "wrapper_report": path_for_report(args.wrapper_report)}))
            return 0

        packetizer_bin = args.packetizer_bin.expanduser()
        if not packetizer_bin.exists():
            raise Phase2C1Error(f"packetizer binary does not exist: {packetizer_bin}")
        if not os.access(packetizer_bin, os.X_OK):
            raise Phase2C1Error(f"packetizer binary is not executable: {packetizer_bin}")

        output_dir.mkdir(parents=True, exist_ok=True)
        timeout = None if args.timeout_sec == 0 else args.timeout_sec
        native = run_cmd(cmd, cwd=ROOT, timeout=timeout)
        report["native_invoked"] = True
        report["native_command"] = native
        if native["returncode"] != 0:
            report["status"] = "fail"
            jwrite(args.wrapper_report, report)
            print(json.dumps({"status": "fail", "wrapper_report": path_for_report(args.wrapper_report)}))
            return native["returncode"] or 1

        if not native_result_json.exists():
            raise Phase2C1Error(f"native result JSON missing after run: {native_result_json}")
        if not pjp1_path.exists():
            raise Phase2C1Error(f"PJP1 output missing after run: {pjp1_path}")

        report["native_result_json"] = {
            "path": path_for_report(native_result_json),
            "sha256": sha256_file(native_result_json),
            "summary": summarize_native_report(native_result_json),
        }
        report["pjp1_output"] = {
            "path": path_for_report(pjp1_path),
            "bytes": pjp1_path.stat().st_size,
            "sha256": sha256_file(pjp1_path),
            "inside_git_worktree": is_under(pjp1_path, ROOT),
        }
        report["status"] = "pass"
        jwrite(args.wrapper_report, report)
        print(json.dumps({"status": "pass", "wrapper_report": path_for_report(args.wrapper_report)}))
        return 0
    except Exception as exc:
        failure = {
            "schema_version": "polar_phase2_c1_smoke_wrapper_v1",
            "status": "blocked" if isinstance(exc, Phase2C1Error) else "error",
            "created_at_utc": utc_iso(),
            "run_label": args.run_label,
            "mode": "dry_run" if args.dry_run else "real",
            "nonclaims": NONCLAIMS,
            "error": str(exc),
            "native_command_argv": cmd,
        }
        jwrite(args.wrapper_report, failure)
        print(json.dumps({"status": failure["status"], "wrapper_report": path_for_report(args.wrapper_report), "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
