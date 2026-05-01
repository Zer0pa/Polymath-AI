"""Tests for the export probe runner."""
from __future__ import annotations

from polymath_ai.dispatch import (
    ExportProbeSpec,
    PROBE_SCOPES,
    PROBE_TARGETS,
    run_export_probe,
)
from polymath_ai.dispatch.adapters import FallbackAdapter, MacSimAdapter


def test_run_export_probe_emits_expected_rows(tmp_path):
    specs = [
        ExportProbeSpec(model_id="tiny.qwen.shape", graph_scope="tiny_block", target="cpu"),
        ExportProbeSpec(model_id="tiny.qwen.shape", graph_scope="tiny_block", target="litert_qnn_sm8650"),
    ]
    summary = run_export_probe(specs, adapters=(MacSimAdapter(), FallbackAdapter()), out_dir=tmp_path)
    assert summary["specs_count"] == 2
    rows = summary["rows"]
    backends = {r["backend"] for r in rows}
    assert backends == {"mac_sim"}, "all rows go through MacSim when no real adapter is available"
    for r in rows:
        assert r["result"] == "ok"
        assert r["delegate_pct"] == 1.0


def test_truth_table_distinguishes_stub_from_measured(tmp_path):
    specs = [ExportProbeSpec(model_id="m1", graph_scope="tiny_block", target="cpu")]
    run_export_probe(specs, adapters=(MacSimAdapter(),), out_dir=tmp_path)
    truth = next(tmp_path.rglob("truth_table.md")).read_text()
    assert "Stage column distinguishes" in truth
    assert "stub" in truth


def test_fallback_adapter_records_downgrade_reason():
    adapter = FallbackAdapter(downgrade_reason="qnn_unavailable")
    probe = adapter.probe()
    assert probe.available is True
    assert "qnn_unavailable" in probe.notes
    assert adapter.fallback_reason() == "qnn_unavailable"


def test_probe_scopes_and_targets_match_prd():
    expected_scopes = {
        "tiny_block",
        "qwen_block",
        "qwen_frozen_subgraph",
        "smollm3_block",
        "smollm3_frozen_subgraph",
    }
    assert expected_scopes.issubset(set(PROBE_SCOPES))
    expected_targets_subset = {
        "cpu",
        "vulkan_gpu",
        "litert_qnn_sm8650",
        "litert_qnn_sm8750",
        "litert_qnn_sm8850",
    }
    assert expected_targets_subset.issubset(set(PROBE_TARGETS))
