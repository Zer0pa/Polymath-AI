#!/usr/bin/env python3
"""Generate or fail-closed on C5 prediction payloads.

This is the canonical host-side contract wrapper for producing the two raw
prediction JSONL files required by ``run_c5_heldout_eval.py``. It only runs a
real producer command supplied by Execution; it never fabricates predictions,
loss, confidence, or train loss from metadata.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from polymath_ai.polar.c5_eval import EVAL_POINTS, sha256_file  # noqa: E402
from polymath_ai.polar.c5_prediction_payloads import (  # noqa: E402
    execute_prediction_payload_contract,
    producer_contract,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-label")
    parser.add_argument("--eval-point", choices=EVAL_POINTS)
    parser.add_argument("--eval-split-identity", type=Path)
    parser.add_argument("--checkpoint-identity", type=Path)
    parser.add_argument("--stable-baseline-identity", type=Path)
    parser.add_argument("--heldout-qa-jsonl", type=Path)
    parser.add_argument("--candidate-checkpoint-payload", type=Path)
    parser.add_argument("--stable-baseline-checkpoint-payload", type=Path)
    parser.add_argument("--prediction-output-root", type=Path)
    parser.add_argument("--metadata-output-dir", type=Path)
    parser.add_argument(
        "--producer-command",
        help=(
            "Shell-style command prefix for the real inference producer. The wrapper appends "
            "--run-label/--eval-point/--checkpoint-role/--checkpoint-payload/--checkpoint-sha256/"
            "--heldout-qa-jsonl/--output-jsonl."
        ),
    )
    parser.add_argument("--candidate-train-loss", type=float)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument(
        "--contract-only",
        action="store_true",
        help="Write a fail-closed metadata contract without running a producer.",
    )
    parser.add_argument(
        "--print-contract",
        action="store_true",
        help="Print the producer command and prediction row contract without writing a report.",
    )
    return parser.parse_args()


def missing_required_args(args: argparse.Namespace) -> list[str]:
    required = ("run_label", "eval_point", "metadata_output_dir")
    if not args.contract_only:
        required = (
            *required,
            "eval_split_identity",
            "checkpoint_identity",
            "stable_baseline_identity",
            "heldout_qa_jsonl",
            "candidate_checkpoint_payload",
            "stable_baseline_checkpoint_payload",
            "prediction_output_root",
            "producer_command",
            "candidate_train_loss",
        )
    return [name for name in required if getattr(args, name) in (None, "")]


def main() -> int:
    args = parse_args()
    if args.print_contract:
        print(json.dumps(producer_contract(), indent=2, sort_keys=True))
        return 0

    missing_args = missing_required_args(args)
    if missing_args:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "blockers": [f"argument_missing_{name}" for name in missing_args],
                    "producer_contract": producer_contract(),
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2

    report_path, report = execute_prediction_payload_contract(
        run_label=args.run_label,
        eval_point=args.eval_point,
        eval_split_identity_path=args.eval_split_identity,
        checkpoint_identity_path=args.checkpoint_identity,
        stable_baseline_identity_path=args.stable_baseline_identity,
        heldout_qa_jsonl=args.heldout_qa_jsonl,
        candidate_checkpoint_payload=args.candidate_checkpoint_payload,
        stable_baseline_checkpoint_payload=args.stable_baseline_checkpoint_payload,
        prediction_output_root=args.prediction_output_root,
        metadata_output_dir=args.metadata_output_dir,
        producer_command_text=args.producer_command,
        candidate_train_loss_value=args.candidate_train_loss,
        timeout_seconds=args.timeout_seconds,
        repo_root=REPO_ROOT,
        contract_only=args.contract_only,
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "first_missing_green_field": report["first_missing_green_field"],
                "report_path": str(report_path),
                "report_sha256": sha256_file(report_path),
            },
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
