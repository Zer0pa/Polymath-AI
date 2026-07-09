#!/usr/bin/env python3
"""Deprecated Mac-side Phase34B ASVD follower.

This script used to pull raw activation captures to Mac scratch storage. The
post-offload workflow keeps raw captures and rank computation on Termux; use
``run_phase34b_phone_asvd_custody_snapshot.py`` instead.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parse_args()
    print(
        "deprecated_fail_closed: use scripts/host/run_phase34b_phone_asvd_custody_snapshot.py "
        "for phone-only ASVD custody; Mac raw activation pulls are disabled."
    )
    return 2


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
