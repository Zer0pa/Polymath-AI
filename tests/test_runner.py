"""Tests for the experiments runner entry point."""
from __future__ import annotations

import json
import sys
import importlib

import pytest

from polymath_ai.experiments.runner import _verify_boundary_integrity, main, _load_config


def test_boundary_integrity_passes():
    _verify_boundary_integrity()  # must not raise


def test_load_config_yaml_and_json(tmp_path):
    yml = tmp_path / "c.yaml"
    yml.write_text("a: 1\nb: 2\n")
    cfg = _load_config(str(yml))
    assert cfg == {"a": 1, "b": 2}

    js = tmp_path / "c.json"
    js.write_text(json.dumps({"x": "y"}))
    cfg2 = _load_config(str(js))
    assert cfg2 == {"x": "y"}


def test_runner_dry_run(tmp_path):
    rc = main(
        [
            "--phase", "phase0a_substrate",
            "--config", str(_make_yaml(tmp_path, {"k": "v"})),
            "--run-dir", str(tmp_path / "run"),
            "--dry-run",
        ]
    )
    assert rc == 0
    audit_lines = (tmp_path / "run" / "audit.jsonl").read_text().splitlines()
    events = [json.loads(line) for line in audit_lines if line.strip()]
    assert events[0]["event_type"] == "genesis"
    assert events[-1]["event_type"] == "phase_gate"


def _make_yaml(tmp_path, body):
    p = tmp_path / "c.yaml"
    import yaml
    p.write_text(yaml.safe_dump(body))
    return p


def test_runner_phase0c_dry_run(tmp_path):
    """Phase 0C runs the host MacSim path successfully without a phone."""
    rc = main(
        [
            "--phase", "phase0c_export_truth_table",
            "--run-dir", str(tmp_path / "p0c"),
        ]
    )
    assert rc == 0
    summary_path = tmp_path / "p0c" / "summary.json"
    assert summary_path.exists()
    summary = json.loads(summary_path.read_text())
    assert summary["specs_count"] > 0


def test_runner_phase0e_blocks_without_phone(tmp_path):
    """Phase 0E refuses to start without phone_attached=true."""
    rc = main(
        [
            "--phase", "phase0e_experiment0",
            "--config", str(_make_yaml(tmp_path, {"phone_attached": False})),
            "--run-dir", str(tmp_path / "p0e"),
        ]
    )
    assert rc == 10
