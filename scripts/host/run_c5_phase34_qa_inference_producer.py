#!/usr/bin/env python3
"""Phase3/4 C5 QA prediction producer boundary.

This command is designed to be passed as ``--producer-command`` to
``run_c5_prediction_payloads.py``. The wrapper appends the checkpoint role,
payload, expected hash, heldout QA JSONL, and output JSONL path. This producer
delegates to ``gemma4_layer_runner --run-c5-qa-predict`` and fails closed until
the native runtime has tokenizer, full decoder, LM-head/unembedding, and
adapter-site policy inputs capable of producing real logits.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from polymath_ai.polar.c5_eval import EVAL_POINTS, is_sha256, sha256_file  # noqa: E402


REPORT_SCHEMA = "polymath_c5_phase34_qa_inference_producer_report_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gemma4-runner", default=os.environ.get("GEMMA4_LAYER_RUNNER"))
    parser.add_argument("--tokenizer-dir")
    parser.add_argument("--decoder-manifest")
    parser.add_argument("--lm-head")
    parser.add_argument("--adapter-site-policy")
    parser.add_argument("--native-timeout-seconds", type=int, default=3600)
    parser.add_argument("--print-contract", action="store_true")

    parser.add_argument("--run-label")
    parser.add_argument("--eval-point", choices=EVAL_POINTS)
    parser.add_argument("--checkpoint-role", choices=("candidate", "stable_baseline"))
    parser.add_argument("--checkpoint-payload", type=Path)
    parser.add_argument("--checkpoint-sha256")
    parser.add_argument("--heldout-qa-jsonl", type=Path)
    parser.add_argument("--output-jsonl", type=Path)
    return parser.parse_args()


def producer_contract() -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA,
        "compatible_wrapper": "scripts/host/run_c5_prediction_payloads.py",
        "producer_command_prefix": (
            "python3.11 scripts/host/run_c5_phase34_qa_inference_producer.py "
            "--gemma4-runner <outside_git_or_build_gemma4_layer_runner> "
            "--tokenizer-dir <outside_git_tokenizer_dir> "
            "--decoder-manifest <outside_git_decoder_manifest> "
            "--lm-head <outside_git_lm_head_or_unembedding> "
            "--adapter-site-policy <outside_git_adapter_site_policy>"
        ),
        "wrapper_appended_args": [
            "--run-label",
            "--eval-point",
            "--checkpoint-role",
            "--checkpoint-payload",
            "--checkpoint-sha256",
            "--heldout-qa-jsonl",
            "--output-jsonl",
        ],
        "fail_closed_missing_runtime_fields": [
            "gemma4_runner_missing",
            "tokenizer_dir_missing",
            "decoder_manifest_missing",
            "lm_head_or_unembedding_missing",
            "adapter_site_policy_missing",
        ],
        "raw_boundary": {
            "prediction_jsonl_output_must_be_outside_git": True,
            "checkpoint_payload_must_remain_outside_git": True,
            "reports_redact_raw_paths": True,
        },
    }


def path_digest(path: Path | None) -> str | None:
    if path is None:
        return None
    return sha256_file(path) if path.is_file() else None


def path_string_digest(path: Path | None) -> str | None:
    if path is None:
        return None
    import hashlib

    return hashlib.sha256(str(path).encode("utf-8")).hexdigest()


def is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def report_path_for(output_jsonl: Path | None) -> Path | None:
    if output_jsonl is None:
        return None
    return output_jsonl.with_name(f"{output_jsonl.name}.phase34_qa_producer_report.json")


def first_blocker(blockers: list[str]) -> str | None:
    return blockers[0] if blockers else None


def write_report(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_blocked_report(
    *,
    args: argparse.Namespace,
    blockers: list[str],
    native_result: subprocess.CompletedProcess[str] | None,
) -> dict[str, Any]:
    native_stdout_json = None
    if native_result is not None and native_result.stdout.strip():
        try:
            native_stdout_json = json.loads(native_result.stdout)
        except json.JSONDecodeError:
            native_stdout_json = None

    first_missing = first_blocker(blockers)
    if native_stdout_json and native_stdout_json.get("first_missing_green_field"):
        first_missing = native_stdout_json["first_missing_green_field"]

    return {
        "schema_version": REPORT_SCHEMA,
        "status": "blocked",
        "first_missing_green_field": first_missing,
        "blockers": blockers,
        "native_report": native_stdout_json,
        "native_returncode": None if native_result is None else native_result.returncode,
        "native_stderr_excerpt": None
        if native_result is None
        else native_result.stderr[-1200:],
        "checkpoint_role": args.checkpoint_role,
        "checkpoint_sha256": args.checkpoint_sha256,
        "checkpoint_payload_identity": {
            "actual_sha256": path_digest(args.checkpoint_payload),
            "path_string_sha256": path_string_digest(args.checkpoint_payload),
            "path_redacted": True,
        },
        "heldout_qa_identity": {
            "sha256": path_digest(args.heldout_qa_jsonl),
            "path_string_sha256": path_string_digest(args.heldout_qa_jsonl),
            "path_redacted": True,
        },
        "output_jsonl_contract": {
            "path_string_sha256": path_string_digest(args.output_jsonl),
            "path_redacted": True,
            "prediction_jsonl_written": bool(args.output_jsonl and args.output_jsonl.exists()),
        },
        "raw_boundary_proof": {
            "raw_payload_bytes_in_report": False,
            "checkpoint_payload_copied_to_git": False,
            "prediction_jsonl_copied_to_git": False,
        },
        "nonclaims": [
            "no C5 pass",
            "no prediction payload emitted unless native runner returns real predictions",
            "no learning or model-quality claim",
        ],
    }


def validate_args(args: argparse.Namespace) -> list[str]:
    blockers: list[str] = []
    if not args.gemma4_runner:
        blockers.append("gemma4_runner_missing")
    elif not Path(args.gemma4_runner).exists():
        blockers.append("gemma4_runner_path_not_found")
    for name in ("run_label", "eval_point", "checkpoint_role", "checkpoint_sha256"):
        if getattr(args, name) in (None, ""):
            blockers.append(f"{name}_missing")
    if not is_sha256(args.checkpoint_sha256 or ""):
        blockers.append("checkpoint_sha256_invalid")
    for name in ("checkpoint_payload", "heldout_qa_jsonl", "output_jsonl"):
        if getattr(args, name) is None:
            blockers.append(f"{name}_missing")
    if args.checkpoint_payload is not None and not args.checkpoint_payload.exists():
        blockers.append("checkpoint_payload_path_not_found")
    if args.heldout_qa_jsonl is not None and not args.heldout_qa_jsonl.exists():
        blockers.append("heldout_qa_jsonl_path_not_found")
    if args.checkpoint_payload is not None and is_under(args.checkpoint_payload, REPO_ROOT):
        blockers.append("checkpoint_payload_inside_git_worktree")
    if args.heldout_qa_jsonl is not None and is_under(args.heldout_qa_jsonl, REPO_ROOT):
        blockers.append("heldout_qa_jsonl_inside_git_worktree")
    if args.output_jsonl is not None and is_under(args.output_jsonl, REPO_ROOT):
        blockers.append("output_jsonl_inside_git_worktree")
    return blockers


def native_argv(args: argparse.Namespace) -> list[str]:
    assert args.gemma4_runner
    argv = [
        args.gemma4_runner,
        "--run-c5-qa-predict",
        "--run-label",
        args.run_label,
        "--eval-point",
        args.eval_point,
        "--checkpoint-role",
        args.checkpoint_role,
        "--checkpoint-payload",
        str(args.checkpoint_payload),
        "--checkpoint-sha256",
        args.checkpoint_sha256,
        "--heldout-qa-jsonl",
        str(args.heldout_qa_jsonl),
        "--output-jsonl",
        str(args.output_jsonl),
    ]
    optional = (
        ("--tokenizer-dir", args.tokenizer_dir),
        ("--decoder-manifest", args.decoder_manifest),
        ("--lm-head", args.lm_head),
        ("--adapter-site-policy", args.adapter_site_policy),
    )
    for flag, value in optional:
        if value:
            argv.extend([flag, value])
    return argv


def main() -> int:
    args = parse_args()
    if args.print_contract:
        print(json.dumps(producer_contract(), indent=2, sort_keys=True))
        return 0

    blockers = validate_args(args)
    if blockers:
        report = build_blocked_report(args=args, blockers=blockers, native_result=None)
        write_report(report_path_for(args.output_jsonl), report)
        print(json.dumps({"status": "blocked", "first_missing_green_field": report["first_missing_green_field"]}))
        return 2

    try:
        completed = subprocess.run(
            native_argv(args),
            text=True,
            capture_output=True,
            timeout=args.native_timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        report = build_blocked_report(
            args=args,
            blockers=[f"native_runner_timeout:{exc.timeout}"],
            native_result=None,
        )
        write_report(report_path_for(args.output_jsonl), report)
        print(json.dumps({"status": "blocked", "first_missing_green_field": report["first_missing_green_field"]}))
        return 2

    if completed.returncode != 0:
        report = build_blocked_report(
            args=args,
            blockers=["native_c5_qa_inference_failed"],
            native_result=completed,
        )
        write_report(report_path_for(args.output_jsonl), report)
        print(json.dumps({"status": "blocked", "first_missing_green_field": report["first_missing_green_field"]}))
        return completed.returncode

    if args.output_jsonl is None or not args.output_jsonl.exists():
        report = build_blocked_report(
            args=args,
            blockers=["native_runner_returned_success_without_output_jsonl"],
            native_result=completed,
        )
        write_report(report_path_for(args.output_jsonl), report)
        print(json.dumps({"status": "blocked", "first_missing_green_field": report["first_missing_green_field"]}))
        return 2

    print(json.dumps({"status": "pass", "output_jsonl": str(args.output_jsonl)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
