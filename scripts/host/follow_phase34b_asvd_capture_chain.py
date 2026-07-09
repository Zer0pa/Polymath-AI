#!/usr/bin/env python3
"""Follow a detached Phase34B ASVD capture chain and checkpoint metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import time


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    args = parse_args()
    args.report_root.mkdir(parents=True, exist_ok=True)
    last_complete = args.initial_complete
    final_rc = 0
    for poll_index in range(args.max_polls):
        latest_pull = args.report_root / "phase34b_asvd_capture_metadata_pull_follow_latest.json"
        pull = run(
            [
                "python3",
                "scripts/host/pull_phase34b_asvd_capture_metadata.py",
                "--run-id",
                args.run_id,
                "--phone-root",
                args.phone_root,
                "--host-scratch-root",
                str(args.host_scratch_root),
                "--pull-raw-captures",
                "--expected-chunk-count",
                str(args.expected_chunk_count),
                "--output",
                str(latest_pull),
            ]
        )
        if pull.returncode != 0:
            print(f"poll={poll_index} pull_rc={pull.returncode} waiting")
            time.sleep(args.poll_seconds)
            continue
        pull_payload = load_json(latest_pull)
        complete = int(pull_payload.get("chunk_count_complete") or 0)
        observed = int(pull_payload.get("chunk_count_observed") or 0)
        status = str(pull_payload.get("status"))
        print(f"poll={poll_index} status={status} observed={observed} complete={complete}")
        if complete > last_complete:
            label_index = complete - 1
            pull_report = args.report_root / f"phase34b_asvd_capture_metadata_pull_chunk{label_index:02d}.json"
            shutil.copyfile(latest_pull, pull_report)
            rank_report = args.report_root / f"phase34b_asvd_rank_trend_chunk{label_index:02d}_report.json"
            rank = run(
                [
                    "python3",
                    "scripts/host/build_phase34_activation_rank_trend_report.py",
                    "--input",
                    str(args.host_scratch_root / "pulled_metadata" / "phase34b_rank_trend_input.json"),
                    "--output",
                    str(rank_report),
                ]
            )
            print(f"complete={complete} rank_rc={rank.returncode} rank_report={rank_report}")
            if args.git_commit:
                commit_reports([pull_report, rank_report], f"phase34b: record asvd capture chunk {label_index:02d}")
            last_complete = complete
        if status == "blocked_fail_closed":
            final_rc = 2
            break
        if complete >= args.expected_chunk_count:
            final_rc = 0
            break
        time.sleep(args.poll_seconds)
    else:
        final_rc = 3
    return final_rc


def commit_reports(paths: list[Path], message: str) -> None:
    add = run(["git", "add", "--", *[str(path) for path in paths]])
    if add.returncode != 0:
        print(f"git_add_failed rc={add.returncode}")
        return
    diff = run(["git", "diff", "--cached", "--quiet", "--", *[str(path) for path in paths]])
    if diff.returncode == 0:
        print("git_commit_skipped=no_cached_diff")
        return
    commit = run(["git", "commit", "-m", message])
    print(f"git_commit_rc={commit.returncode} message={message!r}")


def run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--phone-root", required=True)
    parser.add_argument("--host-scratch-root", required=True, type=Path)
    parser.add_argument("--report-root", required=True, type=Path)
    parser.add_argument("--expected-chunk-count", type=int, default=16)
    parser.add_argument("--initial-complete", type=int, default=0)
    parser.add_argument("--poll-seconds", type=int, default=300)
    parser.add_argument("--max-polls", type=int, default=200)
    parser.add_argument("--git-commit", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
