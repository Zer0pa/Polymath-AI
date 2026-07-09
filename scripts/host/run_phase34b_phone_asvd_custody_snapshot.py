#!/usr/bin/env python3
"""Build Phase34B ASVD custody/rank reports on the phone; pull JSON only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    args = parse_args()
    args.local_report_root.mkdir(parents=True, exist_ok=True)
    config = {
        "run_id": args.run_id,
        "phone_root": args.phone_root,
        "phone_repo_root": args.phone_repo_root,
        "phone_report_root": args.phone_report_root,
        "expected_chunk_count": args.expected_chunk_count,
        "rank_threshold": args.rank_threshold,
        "require_complete": args.require_complete,
        "log_comet": args.log_comet,
    }
    remote = run_remote(args, remote_script(config))
    if remote.returncode != 0:
        sys.stderr.write(remote.stderr)
        sys.stdout.write(remote.stdout)
        return 2
    payload = json.loads(remote.stdout)
    local_paths = pull_json_reports(args, payload)
    if args.git_commit and local_paths:
        commit_reports(local_paths, f"phase34b: record phone asvd custody {payload['label']}")
    print(json.dumps({"remote": payload, "local_paths": [str(path) for path in local_paths]}, indent=2, sort_keys=True))
    return 0 if payload["metadata_status"] == "pass" else 2


def pull_json_reports(args: argparse.Namespace, payload: dict[str, Any]) -> list[Path]:
    label = str(payload["label"])
    path_map = {
        "metadata_report_path": args.local_report_root / f"phase34b_asvd_phone_metadata_{label}.json",
        "rank_report_path": args.local_report_root / f"phase34b_asvd_rank_trend_{label}_report.json",
        "rank_comet_result_path": args.local_report_root / f"phase34b_asvd_rank_trend_{label}_comet_result.json",
    }
    pulled: list[Path] = []
    for key, local in path_map.items():
        remote_path = str(payload.get(key) or "")
        if not remote_path:
            continue
        result = scp_one(args, remote_path, local)
        if result.returncode != 0:
            sys.stderr.write(result.stderr)
            continue
        pulled.append(local)
    return pulled


def run_remote(args: argparse.Namespace, script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        base_ssh(args) + [args.ssh_target, "python3 -"],
        input=script,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def scp_one(args: argparse.Namespace, remote: str, local: Path) -> subprocess.CompletedProcess[str]:
    local.parent.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [
            "scp",
            "-i",
            str(args.ssh_identity.expanduser()),
            "-o",
            "IdentitiesOnly=yes",
            "-P",
            str(args.ssh_port),
            "-o",
            "ConnectTimeout=20",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            f"{args.ssh_target}:{remote}",
            str(local),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def base_ssh(args: argparse.Namespace) -> list[str]:
    return [
        "ssh",
        "-i",
        str(args.ssh_identity.expanduser()),
        "-o",
        "IdentitiesOnly=yes",
        "-p",
        str(args.ssh_port),
        "-o",
        "ConnectTimeout=20",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
    ]


def commit_reports(paths: list[Path], message: str) -> None:
    subprocess.run(["git", "add", "--", *[str(path) for path in paths]], cwd=ROOT, check=False)
    diff = subprocess.run(["git", "diff", "--cached", "--quiet", "--", *[str(path) for path in paths]], cwd=ROOT, check=False)
    if diff.returncode != 0:
        subprocess.run(["git", "commit", "-m", message], cwd=ROOT, check=False)


def remote_script(config: dict[str, Any]) -> str:
    config_json = json.dumps(config, sort_keys=True)
    return f"""
import datetime as dt
import glob
import hashlib
import json
import os
import shlex
import subprocess
import sys

CONFIG = json.loads({config_json!r})
RUN_ID = CONFIG["run_id"]
PHONE_ROOT = CONFIG["phone_root"]
PHONE_REPO_ROOT = CONFIG["phone_repo_root"]
PHONE_REPORT_ROOT = CONFIG["phone_report_root"]
EXPECTED_CHUNK_COUNT = int(CONFIG["expected_chunk_count"])
RANK_THRESHOLD = int(CONFIG["rank_threshold"])
REQUIRE_COMPLETE = bool(CONFIG["require_complete"])
LOG_COMET = bool(CONFIG["log_comet"])
HIDDEN_DIM = 2560
FLOAT32_BYTES = 4
ROW_BYTES = HIDDEN_DIM * FLOAT32_BYTES

def utc_stamp():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\\n")

def raw_boundary():
    return {{
        "metadata_only_report": True,
        "raw_rows_embedded": False,
        "raw_tensors_embedded": False,
        "theta_binaries_embedded": False,
        "tokens_embedded": False,
        "logits_embedded": False,
        "secrets_embedded": False,
    }}

def read_int(path):
    if not os.path.exists(path):
        return None
    try:
        return int(open(path, encoding="utf-8").read().strip())
    except Exception:
        return "invalid"

def count_lines(path):
    if not os.path.exists(path):
        return 0
    with open(path, "rb") as handle:
        return sum(1 for _ in handle)

os.makedirs(PHONE_REPORT_ROOT, exist_ok=True)
blockers = []
chunk_reports = []
rank_chunks = []
for run in sorted(glob.glob(PHONE_ROOT + "/runs/chunk*")):
    label = os.path.basename(run)
    rc = read_int(f"{{run}}/reports/{{label}}_native_rc.txt")
    capture_path = f"{{run}}/raw/layer24_{{label}}_capture.f32"
    native_report_path = f"{{run}}/reports/{{label}}_native_report.json"
    comet_path = f"{{run}}/reports/{{label}}_comet_result.json"
    progress_path = f"{{run}}/predictions/{{label}}_predictions.jsonl.progress.jsonl"
    chunk_path = f"{{PHONE_ROOT}}/chunks/phase34b_asvd_{{label}}.qa.jsonl"
    capture_present = os.path.exists(capture_path)
    capture_bytes = os.path.getsize(capture_path) if capture_present else 0
    capture_sha = sha256_file(capture_path) if capture_present else ""
    record_count = count_lines(chunk_path)
    row_count = capture_bytes // ROW_BYTES
    chunk_blockers = []
    if rc not in (None, 0):
        chunk_blockers.append("chunk_native_rc_nonzero")
    if rc == 0 and not capture_present:
        chunk_blockers.append("completed_chunk_capture_absent")
    if capture_present and capture_bytes % ROW_BYTES:
        chunk_blockers.append("capture_byte_count_not_row_aligned")
    if rc == 0 and capture_present:
        rank_chunks.append({{"activation_capture_f32": capture_path, "record_count": record_count, "sha256": capture_sha}})
    chunk_reports.append({{
        "label": label,
        "rc": rc,
        "record_count": record_count,
        "row_count": row_count,
        "capture_present_on_phone": capture_present,
        "capture_bytes": capture_bytes,
        "capture_sha256": capture_sha,
        "capture_path_sha256": sha256_text(capture_path) if capture_present else "",
        "native_report_present": os.path.exists(native_report_path),
        "native_report_sha256": sha256_file(native_report_path) if os.path.exists(native_report_path) else "",
        "comet_result_present": os.path.exists(comet_path),
        "comet_result_sha256": sha256_file(comet_path) if os.path.exists(comet_path) else "",
        "progress_bytes": os.path.getsize(progress_path) if os.path.exists(progress_path) else 0,
        "raw_rows_embedded": False,
        "blockers": chunk_blockers,
    }})
    blockers.extend(chunk_blockers)

completed = [chunk for chunk in chunk_reports if chunk["rc"] == 0]
if REQUIRE_COMPLETE and len(completed) != EXPECTED_CHUNK_COUNT:
    blockers.append("capture_chain_incomplete")
label = f"chunk{{max(0, len(completed) - 1):02d}}" if completed else "chunk_none"
metadata_report_path = os.path.join(PHONE_REPORT_ROOT, f"phase34b_asvd_phone_metadata_{{label}}.json")
rank_report_path = os.path.join(PHONE_REPORT_ROOT, f"phase34b_asvd_rank_trend_{{label}}_report.json")
rank_comet_result_path = os.path.join(PHONE_REPORT_ROOT, f"phase34b_asvd_rank_trend_{{label}}_comet_result.json")
metadata_report = {{
    "schema_version": "phase34b_phone_asvd_custody_snapshot_v1",
    "status": "pass" if not blockers else "blocked_fail_closed",
    "first_missing_green_field": "none" if not blockers else blockers[0],
    "blockers": list(dict.fromkeys(blockers)),
    "created_utc": utc_stamp(),
    "run_id": RUN_ID,
    "phone_root_path_sha256": sha256_text(PHONE_ROOT),
    "chunk_count_observed": len(chunk_reports),
    "chunk_count_complete": len(completed),
    "expected_chunk_count": EXPECTED_CHUNK_COUNT,
    "rank_report_phone_path_sha256": sha256_text(rank_report_path),
    "chunk_reports": chunk_reports,
    "raw_boundary": raw_boundary(),
    "nonclaims": [
        "phone custody snapshot embeds metadata and hashes only",
        "raw activation captures remain on Termux storage",
        "rank pass, if present, is not correlation evidence",
        "no Gate E pass is implied",
    ],
}}
write_json(metadata_report_path, metadata_report)

rank_status = "blocked_fail_closed"
rank_import_error = ""
rank_backend = "phone_repo"

def local_rank_stats(matrix):
    import numpy as np
    centered = matrix - matrix.mean(axis=0, keepdims=True)
    _, singular_values, _ = np.linalg.svd(centered, full_matrices=False)
    tolerance = float(np.finfo(np.float64).eps * max(centered.shape) * singular_values[0])
    rank = int(np.sum(singular_values > tolerance))
    energy = np.square(singular_values)
    probabilities = energy / energy.sum() if float(energy.sum()) > 0.0 else energy
    nonzero = probabilities[probabilities > 0.0]
    effective_rank = float(np.exp(-np.sum(nonzero * np.log(nonzero)))) if len(nonzero) else 0.0
    return {{
        "centered_rank_estimate": rank,
        "effective_rank": effective_rank,
        "top256_energy_ratio": float(energy[:256].sum() / energy.sum()) if float(energy.sum()) > 0.0 else None,
        "singular_value_1": float(singular_values[0]),
        "singular_value_256": float(singular_values[255]) if len(singular_values) >= 256 else None,
        "singular_value_last": float(singular_values[-1]),
    }}

def build_local_rank_report(chunks, import_error):
    blockers = []
    matrices = []
    chunk_summaries = []
    total_records = 0
    total_rows = 0
    try:
        import numpy as np
    except Exception as exc:
        np = None
        blockers.append("numpy_unavailable_for_rank_trend")
        import_error = import_error or repr(exc)
    for index, chunk in enumerate(chunks):
        path = str(chunk.get("activation_capture_f32") or "")
        record_count = int(chunk.get("record_count") or 0)
        expected_sha = str(chunk.get("sha256") or "")
        chunk_blockers = []
        byte_count = 0
        row_count = 0
        actual_sha = ""
        if not os.path.isfile(path):
            chunk_blockers.append("activation_chunk_file_absent")
        else:
            byte_count = os.path.getsize(path)
            row_count = byte_count // ROW_BYTES
            actual_sha = sha256_file(path)
            if byte_count % ROW_BYTES:
                chunk_blockers.append("activation_chunk_byte_count_not_row_aligned")
            if expected_sha and actual_sha != expected_sha:
                chunk_blockers.append("activation_chunk_sha256_mismatch")
            if os.path.abspath(path).startswith(os.path.abspath(PHONE_REPO_ROOT) + os.sep):
                chunk_blockers.append("raw_activation_chunk_inside_repo")
            if np is not None and not chunk_blockers:
                values = np.memmap(path, dtype="<f4", mode="r", shape=(row_count, HIDDEN_DIM))
                arr = np.asarray(values, dtype=np.float64)
                if not bool(np.isfinite(arr).all()):
                    chunk_blockers.append("activation_chunk_nonfinite_values")
                matrices.append(arr)
        total_records += record_count
        total_rows += row_count
        chunk_summaries.append({{
            "chunk_index": index,
            "record_count": record_count,
            "row_count": row_count,
            "capture_sha256": actual_sha,
            "capture_path_sha256": sha256_text(path),
            "bytes": byte_count,
            "blockers": chunk_blockers,
        }})
        blockers.extend(chunk_blockers)
    trend = []
    final_stats = {{}}
    if np is not None and matrices and not blockers:
        cumulative = []
        for index, matrix in enumerate(matrices):
            cumulative.append(matrix)
            stacked = np.vstack(cumulative)
            stats = local_rank_stats(stacked)
            trend.append({{"chunk_index": index, "cumulative_rows": int(stacked.shape[0]), **stats}})
        final_stats = trend[-1]
        if int(final_stats["centered_rank_estimate"]) < RANK_THRESHOLD:
            blockers.append("activation_capture_rank_below_projection_dim")
        if int(final_stats["effective_rank"]) < 128:
            blockers.append("activation_effective_rank_below_min")
    elif not matrices and "numpy_unavailable_for_rank_trend" not in blockers:
        blockers.append("activation_chunks_absent")
    report = {{
        "schema_version": "phase34b_activation_rank_trend_v1",
        "status": "pass" if not blockers else "blocked_fail_closed",
        "first_missing_green_field": "none" if not blockers else blockers[0],
        "blockers": list(dict.fromkeys(blockers)),
        "created_utc": utc_stamp(),
        "run_id": RUN_ID,
        "chunk_count": len(chunks),
        "calibration_record_count": total_records,
        "calibration_row_count": total_rows,
        "rank_threshold": RANK_THRESHOLD,
        "rank_backend": "phone_self_contained_numpy",
        "phone_repo_import_error_sha256": sha256_text(import_error) if import_error else "",
        "chunk_reports": chunk_summaries,
        "rank_trend": trend,
        "final_stats": final_stats,
        "raw_boundary": raw_boundary(),
        "nonclaims": [
            "rank trend report is a Stage 0 surface gate",
            "rank trend pass is not correlation or Gate E evidence",
            "raw activation rows remain on Termux storage",
        ],
    }}
    return report

try:
    sys.path.insert(0, PHONE_REPO_ROOT)
    from polymath_ai.polar.asvd_calibration import build_activation_rank_trend_report
    from polymath_ai.polar.task_aligned_projection import write_json as repo_write_json
    rank_report = build_activation_rank_trend_report(
        chunks=rank_chunks,
        repo_root=PHONE_REPO_ROOT,
        run_id=RUN_ID,
        rank_threshold=RANK_THRESHOLD,
    )
    repo_write_json(rank_report_path, rank_report)
    rank_status = str(rank_report.get("status"))
except Exception as exc:
    rank_import_error = repr(exc)
    rank_backend = "phone_self_contained_numpy"
    try:
        rank_report = build_local_rank_report(rank_chunks, rank_import_error)
    except Exception as fallback_exc:
        rank_backend = "phone_rank_exception"
        rank_report = {{
            "schema_version": "phase34b_activation_rank_trend_v1",
            "status": "blocked_fail_closed",
            "first_missing_green_field": "phone_rank_trend_exception",
            "blockers": ["phone_rank_trend_exception"],
            "created_utc": utc_stamp(),
            "run_id": RUN_ID,
            "exception_type": type(fallback_exc).__name__,
            "exception_sha256": sha256_text(repr(fallback_exc)),
            "phone_repo_import_error_sha256": sha256_text(rank_import_error),
            "raw_boundary": raw_boundary(),
        }}
    write_json(rank_report_path, rank_report)
    rank_status = str(rank_report.get("status"))

if LOG_COMET and os.path.exists(rank_report_path):
    cmd = (
        '. "$HOME/.termux_agent_env" 2>/dev/null || true; '
        'export COMET_WORKSPACE=zer0pa-imc COMET_PROJECT_NAME=mobile-polymath-ai-training; '
        f'cd {{shlex.quote(PHONE_REPO_ROOT)}} && '
        'python3 scripts/host/log_apex_metadata_report_to_comet.py '
        f'--gate PHASE34 --report {{shlex.quote(rank_report_path)}} '
        f'--run-name phase34b-asvd-rank-{{shlex.quote(label)}} '
        f'--output {{shlex.quote(rank_comet_result_path)}}'
    )
    subprocess.run(["bash", "-lc", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

print(json.dumps({{
    "label": label,
    "metadata_status": metadata_report["status"],
    "rank_status": rank_status,
    "rank_backend": rank_backend,
    "rank_import_error_sha256": sha256_text(rank_import_error) if rank_import_error else "",
    "chunk_count_complete": len(completed),
    "chunk_count_observed": len(chunk_reports),
    "expected_chunk_count": EXPECTED_CHUNK_COUNT,
    "metadata_report_path": metadata_report_path,
    "rank_report_path": rank_report_path,
    "rank_comet_result_path": rank_comet_result_path if os.path.exists(rank_comet_result_path) else "",
}}, sort_keys=True))
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--phone-root", required=True)
    parser.add_argument("--local-report-root", required=True, type=Path)
    parser.add_argument("--phone-report-root", required=True)
    parser.add_argument("--phone-repo-root", default="/data/data/com.termux/files/home/Polymath-AI")
    parser.add_argument("--expected-chunk-count", type=int, default=16)
    parser.add_argument("--rank-threshold", type=int, default=256)
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--log-comet", action="store_true")
    parser.add_argument("--git-commit", action="store_true")
    parser.add_argument("--ssh-target", default="u0_a536@127.0.0.1")
    parser.add_argument("--ssh-port", type=int, default=18022)
    parser.add_argument("--ssh-identity", type=Path, default=Path("~/.ssh/polymath_host"))
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
