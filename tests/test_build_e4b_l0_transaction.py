from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "host" / "build_gemma4_e4b_l0_manifest.py"
SPEC = importlib.util.spec_from_file_location(
    "e4b_l0_transaction_test_target", SCRIPT_PATH
)
assert SPEC is not None and SPEC.loader is not None
transaction = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = transaction
SPEC.loader.exec_module(transaction)


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def fake_manifest_payload() -> dict[str, Any]:
    manifest = {
        "state": "passed_scope",
        "blockers": [],
        "high_precision_task_oracle": {
            "edge_A_decode_template_stop_length_seed_and_evaluator_protocol_sha256": (
                "a" * 64
            )
        },
        "effects": ["authorizes_f5_probe"],
        "nonclaims": ["not_phone_runtime_evidence"],
    }
    return {
        "manifest": manifest,
        "manifest_sha256": transaction.canonical_sha256(manifest),
    }


def build_args(tmp_path: Path) -> tuple[argparse.Namespace, Path]:
    evidence_parent = tmp_path / "evidence"
    evidence_parent.mkdir()
    parent_capsule = tmp_path / "capsule.yaml"
    parent_capsule.write_bytes(b"state: frozen\n")
    input_paths: dict[str, Path] = {}
    for name in (
        "reference_stacks",
        "weight_verification_receipts",
        "edge_a_protocol",
        "converter_lineage",
    ):
        path = tmp_path / f"{name}.json"
        write_json(path, {"kind": name})
        input_paths[name] = path
    args = argparse.Namespace(
        output_dir=str(evidence_parent / "l0-run"),
        provisional_build_source="qat_mobile_transformers",
        reference_stacks=str(input_paths["reference_stacks"]),
        weight_verification_receipts=str(input_paths["weight_verification_receipts"]),
        edge_a_protocol=str(input_paths["edge_a_protocol"]),
        converter_lineage=str(input_paths["converter_lineage"]),
        source_revision="1" * 40,
        parent_capsule=str(parent_capsule),
        parent_capsule_sha256=hashlib.sha256(parent_capsule.read_bytes()).hexdigest(),
    )
    return args, evidence_parent


def install_execution_fakes(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    source_calls: list[str] = []

    def verify_source_tree(revision: str) -> dict[str, dict[str, Any]]:
        source_calls.append(revision)
        return {
            "polymath_ai/frontier/e4b_l0.py": {
                "sha256": "b" * 64,
                "bytes": 123,
                "git_blob_oid": "c" * 40,
            },
            "scripts/host/build_gemma4_e4b_l0_manifest.py": {
                "sha256": "d" * 64,
                "bytes": 456,
                "git_blob_oid": "e" * 40,
            },
        }

    monkeypatch.setattr(transaction, "verify_source_tree", verify_source_tree)
    monkeypatch.setattr(transaction, "HuggingFaceHubClient", lambda token: object())
    monkeypatch.setattr(
        transaction,
        "build_default_l0_manifest",
        lambda *_args, **_kwargs: fake_manifest_payload(),
    )
    return source_calls


@pytest.mark.parametrize(
    ("payload", "error_code"),
    [
        (b'{"outer":{"x":1,"x":2}}', "fixture_duplicate_json_key"),
        (b'{"value":NaN}', "fixture_nonfinite_json"),
        (b'{"value":1e999}', "fixture_nonfinite_json"),
    ],
)
def test_strict_json_rejects_duplicate_and_nonfinite_values(
    tmp_path: Path,
    payload: bytes,
    error_code: str,
) -> None:
    path = tmp_path / "input.json"
    path.write_bytes(payload)
    with pytest.raises(transaction.TransactionError) as raised:
        transaction.read_strict_json(path, error_prefix="fixture")
    assert raised.value.code == error_code


def test_json_hash_is_over_the_exact_bytes_that_were_parsed(tmp_path: Path) -> None:
    path = tmp_path / "input.json"
    payload = b'{\n  "z": 2,\n  "a": 1\n}\n'
    path.write_bytes(payload)
    value, observed = transaction.read_strict_json(path, error_prefix="fixture")
    record = transaction.file_record(path, observed)
    assert value == {"a": 1, "z": 2}
    assert observed == payload
    assert record["sha256"] == hashlib.sha256(payload).hexdigest()
    assert record["bytes"] == len(payload)


def test_bounded_reader_rejects_a_final_component_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(transaction.TransactionError) as raised:
        transaction.read_strict_json(link, error_prefix="fixture")
    assert raised.value.code == "fixture_read_failed"


def test_bounded_reader_rejects_an_oversize_input(tmp_path: Path) -> None:
    path = tmp_path / "input.json"
    path.write_bytes(b"{}\n")
    with pytest.raises(transaction.TransactionError) as raised:
        transaction.read_bounded_regular_file(
            path,
            max_bytes=2,
            error_prefix="fixture",
        )
    assert raised.value.code == "fixture_size_out_of_bounds"


def test_source_verification_ignores_report_dirt_but_rejects_source_dirt(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    source = repository / "polymath_ai" / "frontier" / "unit.py"
    command = repository / "scripts" / "host" / "command.py"
    report = repository / "runtime" / "reports" / "unrelated.json"
    source.parent.mkdir(parents=True)
    command.parent.mkdir(parents=True)
    report.parent.mkdir(parents=True)
    source.write_text("VALUE = 1\n", encoding="utf-8")
    command.write_text("COMMAND = True\n", encoding="utf-8")
    report.write_text('{"dirty":false}\n', encoding="utf-8")
    subprocess.run(["git", "init", "-q", repository], check=True)
    subprocess.run(["git", "-C", repository, "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            repository,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-q",
            "-m",
            "source",
        ],
        check=True,
    )
    revision = subprocess.check_output(
        ["git", "-C", repository, "rev-parse", "HEAD"],
        text=True,
    ).strip()

    records = transaction.verify_source_tree(
        revision,
        root=repository,
        source_paths=[source, command],
    )
    assert (
        records["polymath_ai/frontier/unit.py"]["sha256"]
        == hashlib.sha256(source.read_bytes()).hexdigest()
    )

    report.write_text('{"dirty":true}\n', encoding="utf-8")
    transaction.verify_source_tree(
        revision,
        root=repository,
        source_paths=[source, command],
    )

    with pytest.raises(transaction.TransactionError) as raised:
        transaction.verify_source_tree(
            "0" * 40,
            root=repository,
            source_paths=[source, command],
        )
    assert raised.value.code == "source_revision_not_current_head"

    source.write_text("VALUE = 2\n", encoding="utf-8")
    with pytest.raises(transaction.TransactionError) as raised:
        transaction.verify_source_tree(
            revision,
            root=repository,
            source_paths=[source, command],
        )
    assert raised.value.code == "loaded_source_differs_from_commit"


def test_transaction_publishes_both_files_with_final_locators(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    args, evidence_parent = build_args(tmp_path)
    source_calls = install_execution_fakes(monkeypatch)

    assert transaction.execute(args) == 0
    emitted = json.loads(capsys.readouterr().out)
    output_dir = Path(args.output_dir).resolve()
    manifest_path = Path(emitted["manifest"])
    receipt_path = Path(emitted["receipt"])
    assert manifest_path.parent == output_dir
    assert receipt_path.parent == output_dir
    assert manifest_path.name == (
        f"e4b_l0_parent_{hashlib.sha256(manifest_path.read_bytes()).hexdigest()}.json"
    )
    assert receipt_path.name == (
        f"l0_execution_receipt_{hashlib.sha256(receipt_path.read_bytes()).hexdigest()}.json"
    )
    receipt = json.loads(receipt_path.read_bytes())
    assert receipt["claim"]["evidence"][
        "report_path_or_content_addressed_locator"
    ] == str(manifest_path)
    assert receipt["transaction"]["manifest_locator"] == str(manifest_path)
    assert (
        receipt["transaction"]["source_files"][
            "scripts/host/build_gemma4_e4b_l0_manifest.py"
        ]["sha256"]
        == "d" * 64
    )
    assert len(source_calls) == 3
    assert not list(evidence_parent.glob(".l0-run.staging-*"))
    assert sorted(path.name for path in output_dir.iterdir()) == sorted(
        [manifest_path.name, receipt_path.name]
    )


def test_publish_failure_cleans_only_owned_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args, evidence_parent = build_args(tmp_path)
    install_execution_fakes(monkeypatch)
    unrelated = evidence_parent / "keep.txt"
    unrelated.write_text("keep", encoding="utf-8")

    def reject_publish(_source: Path, _destination: Path) -> None:
        raise transaction.TransactionError("atomic_noreplace_rename_failed")

    monkeypatch.setattr(
        transaction,
        "atomic_rename_directory_noreplace",
        reject_publish,
    )
    with pytest.raises(transaction.TransactionError) as raised:
        transaction.execute(args)
    assert raised.value.code == "atomic_noreplace_rename_failed"
    assert unrelated.read_text(encoding="utf-8") == "keep"
    assert not Path(args.output_dir).exists()
    assert not list(evidence_parent.glob(".l0-run.staging-*"))


def test_atomic_publish_never_replaces_an_existing_directory(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    marker = destination / "marker"
    marker.write_text("authority", encoding="utf-8")
    with pytest.raises(transaction.TransactionError) as raised:
        transaction.atomic_rename_directory_noreplace(source, destination)
    assert raised.value.code == "output_dir_already_exists"
    assert source.is_dir()
    assert marker.read_text(encoding="utf-8") == "authority"


def test_parent_capsule_hash_must_match_exact_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args, _evidence_parent = build_args(tmp_path)
    install_execution_fakes(monkeypatch)
    args.parent_capsule_sha256 = "0" * 64
    with pytest.raises(transaction.TransactionError) as raised:
        transaction.execute(args)
    assert raised.value.code == "parent_capsule_sha256_mismatch"


def test_main_sanitizes_unexpected_errors(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def explode(_args: argparse.Namespace) -> int:
        raise RuntimeError("secret=https://provider.invalid/private?token=credential")

    monkeypatch.setattr(transaction, "execute", explode)
    result = transaction.main(
        [
            "--output-dir",
            "unused",
            "--provisional-build-source",
            "qat_mobile_transformers",
            "--reference-stacks",
            "unused",
            "--weight-verification-receipts",
            "unused",
            "--edge-a-protocol",
            "unused",
            "--converter-lineage",
            "unused",
            "--source-revision",
            "1" * 40,
            "--parent-capsule",
            "unused",
            "--parent-capsule-sha256",
            "2" * 64,
        ]
    )
    assert result == 1
    stderr = capsys.readouterr().err
    assert json.loads(stderr) == {"error": "l0_manifest_transaction_failed"}
    assert "credential" not in stderr
