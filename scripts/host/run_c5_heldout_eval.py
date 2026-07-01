#!/usr/bin/env python3
"""Produce executed C5 metrics JSON from heldout QA and prediction JSONL.

This runner is the canonical metadata-only producer for the
``polymath_c5_executed_metrics_v1`` artifact consumed by ``run_c5_eval.py``.
It scores already-produced candidate and stable-baseline predictions. It does
not run model inference, call Comet, source secrets, or copy raw payloads into
repo reports.
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
from polymath_ai.polar.c5_heldout_eval import (  # noqa: E402
    build_blocker_report,
    build_executed_metrics_payload,
    extract_grad_norm_max_observed,
    load_json,
    load_validated_identity_inputs,
    safe_label,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-label")
    parser.add_argument("--eval-point", choices=EVAL_POINTS)
    parser.add_argument("--eval-split-identity", type=Path)
    parser.add_argument("--checkpoint-identity", type=Path)
    parser.add_argument("--stable-baseline-identity", type=Path)
    parser.add_argument("--heldout-qa-jsonl", type=Path)
    parser.add_argument("--candidate-predictions-jsonl", type=Path)
    parser.add_argument("--stable-baseline-predictions-jsonl", type=Path)
    parser.add_argument(
        "--candidate-train-loss",
        type=float,
        help="Candidate training loss aligned to the evaluated checkpoint, used for overfit-gap reporting.",
    )
    parser.add_argument(
        "--grad-norm-max-observed",
        type=float,
        help="Observed maximum gradient norm. Required unless --phase34-report contains a finite Phase4 grad norm.",
    )
    parser.add_argument(
        "--phase34-report",
        type=Path,
        help="Optional Phase3/4 metadata report used only to recover observed grad norm.",
    )
    parser.add_argument("--ece-bins", type=int, default=10)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--print-prediction-schema",
        action="store_true",
        help="Print the required prediction JSONL row schema and exit.",
    )
    return parser.parse_args()


def missing_required_run_args(args: argparse.Namespace) -> list[str]:
    required = (
        "run_label",
        "eval_point",
        "eval_split_identity",
        "checkpoint_identity",
        "stable_baseline_identity",
        "heldout_qa_jsonl",
        "candidate_predictions_jsonl",
        "stable_baseline_predictions_jsonl",
        "candidate_train_loss",
        "output_dir",
    )
    return [name for name in required if getattr(args, name) in (None, "")]


def prediction_schema() -> dict[str, object]:
    return {
        "schema": "polymath_c5_prediction_jsonl_row_v1",
        "required_fields": {
            "record_id": "Must match the accepted heldout QA split record_id.",
            "prediction": "Predicted answer text. Aliases accepted: predicted_answer, answer.",
            "loss": "Finite per-record negative log likelihood or equivalent answer-token loss.",
            "confidence": "Finite probability in [0, 1] for the predicted answer being correct.",
        },
        "optional_fields": {
            "loss_weight": "Positive weight, usually answer token count. Aliases accepted: token_count, answer_token_count.",
        },
        "raw_boundary": "Prediction JSONL must stay outside the git worktree; this runner emits JSON metadata only.",
    }


def resolve_grad_norm(args: argparse.Namespace) -> float | None:
    if args.grad_norm_max_observed is not None:
        return args.grad_norm_max_observed
    if args.phase34_report is None:
        return None
    payload = load_json(args.phase34_report)
    return extract_grad_norm_max_observed(payload, args.eval_point)


def main() -> int:
    args = parse_args()
    if args.print_prediction_schema:
        print(json.dumps(prediction_schema(), indent=2, sort_keys=True))
        return 0

    missing_args = missing_required_run_args(args)
    if missing_args:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "blockers": [f"argument_missing_{name}" for name in missing_args],
                    "prediction_schema": prediction_schema(),
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / (
        f"c5_executed_metrics_{safe_label(args.eval_point)}_{safe_label(args.run_label)}.json"
    )

    input_paths = [
        args.eval_split_identity,
        args.checkpoint_identity,
        args.stable_baseline_identity,
        args.heldout_qa_jsonl,
        args.candidate_predictions_jsonl,
        args.stable_baseline_predictions_jsonl,
    ]
    if args.phase34_report is not None:
        input_paths.append(args.phase34_report)

    try:
        eval_split_identity, checkpoint_identity, stable_baseline_identity = load_validated_identity_inputs(
            eval_split_identity_path=args.eval_split_identity,
            checkpoint_identity_path=args.checkpoint_identity,
            stable_baseline_identity_path=args.stable_baseline_identity,
        )
        grad_norm = resolve_grad_norm(args)
        if grad_norm is None:
            raise ValueError("grad_norm_max_observed_missing")

        payload = build_executed_metrics_payload(
            run_label=args.run_label,
            eval_point=args.eval_point,
            eval_split_identity=eval_split_identity,
            checkpoint_identity=checkpoint_identity,
            stable_baseline_identity=stable_baseline_identity,
            heldout_qa_path=args.heldout_qa_jsonl,
            candidate_predictions_path=args.candidate_predictions_jsonl,
            baseline_predictions_path=args.stable_baseline_predictions_jsonl,
            candidate_train_loss=args.candidate_train_loss,
            grad_norm_max_observed=grad_norm,
            ece_bins=args.ece_bins,
            repo_root=REPO_ROOT,
        )
        write_json(output_path, payload)
        status = "executed_metrics_ready"
        exit_code = 0
    except Exception as exc:  # noqa: BLE001 - CLI must fail closed with a compact blocker report.
        output_path = args.output_dir / (
            f"c5_heldout_eval_blocker_{safe_label(args.eval_point)}_{safe_label(args.run_label)}.json"
        )
        payload = build_blocker_report(
            run_label=args.run_label,
            eval_point=args.eval_point,
            blockers=[f"{type(exc).__name__}:{exc}"],
            output_path=output_path,
            input_paths=input_paths,
        )
        write_json(output_path, payload)
        status = "blocked"
        exit_code = 2

    print(
        json.dumps(
            {
                "status": status,
                "output_path": str(output_path),
                "output_sha256": sha256_file(output_path),
            },
            sort_keys=True,
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
