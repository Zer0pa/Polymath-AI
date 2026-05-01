"""Single entry point for Polymath experiment runs.

Usage:
    python -m polymath_ai.experiments.runner \
        --phase phase0e_experiment0 \
        --config configs/experiments/E0/E0.1.yaml \
        --run-id run:... \
        --run-dir runtime/runs/...

Dispatches to phase-specific submodules. Each submodule:

  1. Validates the config against the phase's expected schema.
  2. Constructs an ``AuditWriter`` rooted at ``run-dir/audit.jsonl``.
  3. Emits a ``genesis`` event then runs.
  4. On every event the runner emits a typed audit row.
  5. On success emits a ``phase_gate`` event with the falsifier outcomes.
  6. On failure emits a ``falsifier`` event with the blocking failure and
     exits non-zero so the watchdog can decide whether to retry.

The runner is *boundary-bearing*: every emitted envelope contains the
boundary block. The runner refuses to start if the freshly-loaded boundary
text drifts from the manifest sha (catches accidental boundary edits).
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Optional

from polymath_ai._version import SCHEMA_VERSION
from polymath_ai.audit.chain import AuditWriter
from polymath_ai.boundary.text import BOUNDARY_SHA256, BOUNDARY_TEXT, boundary_envelope
from polymath_ai.utils.canonical import canonical_json, sha256_text, utc_now_iso


PHASE_DISPATCH = {
    "phase0a_substrate": "polymath_ai.experiments.phase0a",
    "phase0b_elo_correctness": "polymath_ai.experiments.phase0b",
    "phase0c_export_truth_table": "polymath_ai.experiments.phase0c",
    "phase0d_device_attach": "polymath_ai.experiments.phase0d",
    "phase0e_experiment0": "polymath_ai.experiments.phase0e",
    "phase0f_experiment1_fertility": "polymath_ai.experiments.phase0f",
    "phase0g_experiment2_smollm3_export": "polymath_ai.experiments.phase0g",
    "phase0h_cutover_review": "polymath_ai.experiments.phase0h",
    "phase1a_qwen_elo_100m": "polymath_ai.experiments.phase1a",
}


def _load_config(path: Optional[str]) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    if p.suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError:
            raise ImportError("pyyaml required to load YAML configs")
        return yaml.safe_load(p.read_text()) or {}
    if p.suffix == ".json":
        return json.loads(p.read_text())
    raise ValueError(f"unsupported config format: {p.suffix}")


def _verify_boundary_integrity() -> None:
    if sha256_text(BOUNDARY_TEXT) != BOUNDARY_SHA256:
        raise RuntimeError(
            "boundary text drift detected at runner startup - aborting "
            "before any audit row is written"
        )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True, choices=list(PHASE_DISPATCH.keys()))
    parser.add_argument("--config", help="path to YAML/JSON config")
    parser.add_argument("--run-id", default=None, help="defaults to a fresh timestamped id")
    parser.add_argument("--run-dir", default=None, help="defaults to runtime/runs/<run_id>")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    _verify_boundary_integrity()

    cfg = _load_config(args.config)
    run_id = args.run_id or f"run:{utc_now_iso()}:{args.phase}"
    run_dir = Path(args.run_dir or f"runtime/runs/{run_id.replace(':', '_')}")
    run_dir.mkdir(parents=True, exist_ok=True)

    audit = AuditWriter(run_dir / "audit.jsonl", run_id=run_id)
    audit.append(
        event_type="genesis",
        payload={
            "phase": args.phase,
            "config_sha256": sha256_text(canonical_json(cfg)),
            "config": cfg,
            "args": vars(args),
            "boundary_envelope": boundary_envelope(),
        },
    )

    if args.dry_run:
        audit.append(event_type="phase_gate", payload={"gate": "dry_run", "result": "skipped"})
        print(json.dumps({"run_id": run_id, "run_dir": str(run_dir), "result": "dry_run"}))
        return 0

    module_name = PHASE_DISPATCH[args.phase]
    try:
        mod = importlib.import_module(module_name)
    except ImportError as e:
        audit.append(
            event_type="falsifier",
            payload={
                "falsifier_id": "phase_module_missing",
                "result": "blocked",
                "detail": f"could not import {module_name}: {e!r}",
                "blocking": True,
            },
        )
        print(f"phase module {module_name!r} not importable: {e!r}", file=sys.stderr)
        return 2

    if not hasattr(mod, "run"):
        audit.append(
            event_type="falsifier",
            payload={
                "falsifier_id": "phase_module_missing_run",
                "result": "blocked",
                "detail": f"{module_name} has no .run(...) entry point",
                "blocking": True,
            },
        )
        return 3

    rc = mod.run(config=cfg, run_id=run_id, run_dir=run_dir, audit=audit)
    audit.append(
        event_type="phase_gate",
        payload={"gate": "phase_complete", "phase": args.phase, "rc": rc},
    )
    return rc


if __name__ == "__main__":
    sys.exit(main())
