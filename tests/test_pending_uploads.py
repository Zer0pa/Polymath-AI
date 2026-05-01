"""Pending upload manifest tests."""
from __future__ import annotations

from polymath_ai.sync.pending import PendingUploadStore, queue_pending_upload, list_pending_uploads


def test_queue_emits_row(tmp_path):
    store_path = tmp_path / "pending.jsonl"
    artifact = tmp_path / "smoke.safetensors"
    artifact.write_bytes(b"\x00" * 16)
    queue_pending_upload(
        store_path,
        pending_id="pending:smoke:001",
        local_path=str(artifact),
        intended_target={"target_kind": "hf_model", "repo_id": "Architect-Prime/polymath-smoke"},
        blocked_by="hf_token_absent",
    )
    rows = list_pending_uploads(store_path)
    assert len(rows) == 1
    assert rows[0]["pending_id"] == "pending:smoke:001"
    assert rows[0]["size_bytes"] == 16
    assert rows[0]["sha256"].startswith("sha256:")


def test_appends_preserve_history(tmp_path):
    store = PendingUploadStore(tmp_path / "p.jsonl")
    artifact = tmp_path / "x.bin"
    artifact.write_bytes(b"AB")
    store.append(
        pending_id="p1",
        local_path=str(artifact),
        size_bytes=2,
        intended_target={"target_kind": "hf_dataset", "repo_id": "Architect-Prime/polymath-corpora"},
    )
    store.append(
        pending_id="p2",
        local_path=str(artifact),
        size_bytes=2,
        intended_target={"target_kind": "hf_model", "repo_id": "Architect-Prime/polymath-models"},
    )
    rows = store.list()
    assert [r["pending_id"] for r in rows] == ["p1", "p2"]
