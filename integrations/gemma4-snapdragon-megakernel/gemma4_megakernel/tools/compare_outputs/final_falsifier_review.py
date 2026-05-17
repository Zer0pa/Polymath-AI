#!/usr/bin/env python3
"""Final promotion falsifier for the Gemma4 Snapdragon gate ladder."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


MODEL_ID = "google/gemma-4-E4B"
REVISION = "7aa32e6889efd6300124851b164f8b364314c3d8"
DEVICE_IDENTITY = "nubia NX789J SM8750 FY25013101C8"
TRAINABLE_SCOPE = "post_layer0_rank4_residual_adapter"
MIN_COSINE = 0.99

GATE_REPORTS = {
    "g1_layer0_opencl": "runtime/reports/gemma4_megakernel/parity/20260516_e4b_layer0_opencl_gate/gate_result.json",
    "g2_import_regression": "runtime/reports/gemma4_megakernel/import_and_regression/20260517T030510Z_g2_import_regression/gate_result.json",
    "g3_two_layer_opencl": "runtime/reports/gemma4_megakernel/forward_stack/20260517T032829Z_g3_two_layer_opencl/gate_result.json",
    "g4_minimal_executor": "runtime/reports/gemma4_megakernel/executor_architecture/20260517T040000Z_g4_minimal_executor/gate_result.json",
    "g5_rank4_adapter_backward": "runtime/reports/gemma4_megakernel/backward_path/20260517T040000Z_g5_rank4_adapter_opencl/gate_result.json",
    "g6_rank4_adapter_sgd": "runtime/reports/gemma4_megakernel/optimizer_update/20260517T040000Z_g6_rank4_adapter_sgd/gate_result.json",
    "g7_hf_native_token_pack": "runtime/reports/gemma4_megakernel/phone_data_pipeline/20260517T040000Z_g7_hf_native_token_pack/gate_result.json",
    "g8_streamed_corpus_repaired": "runtime/reports/gemma4_megakernel/integrated_training/20260517T071405Z_g8_streamed_corpus_repaired/gate_result.json",
    "g9_three_batch_chain": "runtime/reports/gemma4_megakernel/sustained_authority/20260517T071405Z_g9_three_batch_chain/gate_result.json",
}

FALSIFIER_REPORTS = {
    "g2_import_regression": "runtime/reports/gemma4_megakernel/falsifiers/20260517T030510Z_g2_import_regression/falsifier_report.json",
    "g3_two_layer_opencl": "runtime/reports/gemma4_megakernel/falsifiers/20260517T032829Z_g3_two_layer_opencl/falsifier_report.json",
    "g4_minimal_executor": "runtime/reports/gemma4_megakernel/falsifiers/20260517T040000Z_g4_minimal_executor/falsifier_report.json",
    "g5_rank4_adapter_backward": "runtime/reports/gemma4_megakernel/falsifiers/20260517T040000Z_g5_rank4_adapter_opencl/falsifier_report.json",
    "g6_rank4_adapter_sgd": "runtime/reports/gemma4_megakernel/falsifiers/20260517T040000Z_g6_rank4_adapter_sgd/falsifier_report.json",
    "g7_hf_native_token_pack": "runtime/reports/gemma4_megakernel/falsifiers/20260517T040000Z_g7_hf_native_token_pack/falsifier_report.json",
    "g8_streamed_corpus_repaired": "runtime/reports/gemma4_megakernel/falsifiers/20260517T071405Z_g8_streamed_corpus_repaired/falsifier_report.json",
    "g9_three_batch_chain": "runtime/reports/gemma4_megakernel/falsifiers/20260517T071405Z_g9_three_batch_chain/falsifier_report.json",
}

HISTORICAL_FAILED_G8 = Path(
    "runtime/reports/gemma4_megakernel/integrated_training/"
    "20260517T040000Z_g8_streamed_corpus_falsified/gate_result.json"
)

G8_DIR = Path(
    "runtime/reports/gemma4_megakernel/integrated_training/"
    "20260517T071405Z_g8_streamed_corpus_repaired"
)
G9_DIR = Path(
    "runtime/reports/gemma4_megakernel/sustained_authority/"
    "20260517T071405Z_g9_three_batch_chain"
)


@dataclass
class Check:
    name: str
    status: str
    details: dict[str, Any]

    def to_json(self) -> dict[str, Any]:
        return {"name": self.name, "status": self.status, "details": self.details}


def load_json(repo_root: Path, path: Path | str) -> dict[str, Any]:
    full_path = repo_root / path
    with full_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def status_is_pass(value: dict[str, Any]) -> bool:
    return value.get("status") == "pass"


def check_all_reports_pass(repo_root: Path) -> Check:
    statuses = {}
    failures = []
    for name, path in GATE_REPORTS.items():
        report = load_json(repo_root, path)
        status = report.get("status")
        statuses[name] = {"path": path, "status": status}
        if status != "pass":
            failures.append(name)
    return Check("gate_chain_status", "pass" if not failures else "fail", {"reports": statuses})


def check_falsifiers_pass(repo_root: Path) -> Check:
    statuses = {}
    failures = []
    for name, path in FALSIFIER_REPORTS.items():
        report = load_json(repo_root, path)
        checks = report.get("checks", [])
        failed_checks = [
            item.get("name")
            for item in checks
            if not str(item.get("status", "")).startswith(("pass", "not_applicable"))
        ]
        unresolved = report.get("critical_unresolved") or []
        if unresolved:
            failed_checks.append("critical_unresolved")
        status = "pass" if not failed_checks else "fail"
        statuses[name] = {
            "path": path,
            "status": status,
            "failed_checks": failed_checks,
            "critical_unresolved": unresolved,
        }
        if failed_checks:
            failures.append(name)
    return Check("prior_falsifier_chain_status", "pass" if not failures else "fail", {"reports": statuses})


def check_historical_g8_rejected(repo_root: Path) -> Check:
    report = load_json(repo_root, HISTORICAL_FAILED_G8)
    status = report.get("status")
    return Check(
        "historical_failed_g8_not_promoted",
        "pass" if status == "fail_under_falsification" else "fail",
        {"path": str(HISTORICAL_FAILED_G8), "status": status},
    )


def find_check(report: dict[str, Any], name: str) -> dict[str, Any] | None:
    for item in report.get("checks", []):
        if item.get("name") == name:
            return item
    return None


def check_g8_authority_path(repo_root: Path) -> Check:
    gate = load_json(repo_root, GATE_REPORTS["g8_streamed_corpus_repaired"])
    telemetry = load_json(repo_root, G8_DIR / "phone_output/telemetry.json")
    token_to_hidden = load_json(repo_root, G8_DIR / "token_to_hidden_compare.json")
    hidden_inputs = gate.get("hidden_state_fixtures_consumed")
    statuses = {
        "runtime_input_path": gate.get("runtime_input_path"),
        "hidden_state_fixtures_consumed": hidden_inputs,
        "token_to_hidden_status": token_to_hidden.get("status"),
        "token_to_hidden_backend": telemetry.get("token_to_hidden_backend"),
        "layer_backend": telemetry.get("layer_backend"),
        "adapter_backend": telemetry.get("adapter_backend"),
        "backend": telemetry.get("backend"),
    }
    passed = (
        hidden_inputs == []
        and gate.get("runtime_input_path") == "token_cache_to_phone_generated_hidden_to_opencl_layers_to_adapter_update"
        and token_to_hidden.get("hidden_state_fixtures_consumed") == []
        and token_to_hidden.get("status") == "pass"
        and telemetry.get("token_to_hidden_backend") == "phone_cpu"
        and telemetry.get("layer_backend") == "opencl"
        and telemetry.get("adapter_backend") == "opencl"
    )
    return Check("g8_no_hidden_host_data_path", "pass" if passed else "fail", statuses)


def check_model_revision(repo_root: Path) -> Check:
    files = [
        G8_DIR / "token_compare.json",
        G8_DIR / "layer0_compare.json",
        G8_DIR / "layer1_compare.json",
        G9_DIR / "layer0_compare_000.json",
        G9_DIR / "layer1_compare_000.json",
        G9_DIR / "layer0_compare_001.json",
        G9_DIR / "layer1_compare_001.json",
        G9_DIR / "layer0_compare_002.json",
        G9_DIR / "layer1_compare_002.json",
    ]
    records: list[dict[str, Any]] = []
    failures: list[str] = []
    for path in files:
        data = load_json(repo_root, path)
        provenance = data.get("provenance", data)
        model_id = provenance.get("model_id") or data.get("model_id")
        revision = provenance.get("revision") or data.get("revision")
        expected_model = provenance.get("expected_model_id", MODEL_ID)
        expected_revision = provenance.get("expected_revision", REVISION)
        record = {
            "path": str(path),
            "model_id": model_id,
            "revision": revision,
            "expected_model_id": expected_model,
            "expected_revision": expected_revision,
        }
        records.append(record)
        if model_id != MODEL_ID or revision != REVISION or expected_model != MODEL_ID or expected_revision != REVISION:
            failures.append(str(path))
    return Check("model_revision_consistency", "pass" if not failures else "fail", {"records": records})


def check_token_parity(repo_root: Path) -> Check:
    token_reports = [G8_DIR / "token_compare.json"] + [
        G9_DIR / f"token_compare_{batch:03d}.json" for batch in range(3)
    ]
    mismatch_keys = [
        "input_id_mismatch_count",
        "attention_mask_mismatch_count",
        "label_mismatch_count",
        "loss_mask_mismatch_count",
        "position_id_mismatch_count",
    ]
    records = []
    failures = []
    for path in token_reports:
        report = load_json(repo_root, path)
        mismatches = {key: report.get(key) for key in mismatch_keys}
        record = {"path": str(path), "status": report.get("status"), **mismatches}
        records.append(record)
        if report.get("status") != "pass" or any(report.get(key) != 0 for key in mismatch_keys):
            failures.append(str(path))
    return Check("token_mask_label_position_parity", "pass" if not failures else "fail", {"reports": records})


def compare_report_passes(repo_root: Path, path: Path) -> tuple[bool, dict[str, Any]]:
    report = load_json(repo_root, path)
    comparison = report.get("comparison", {})
    record = {
        "path": str(path),
        "status": report.get("status"),
        "method": comparison.get("method"),
        "token_count": comparison.get("token_count"),
        "pad_token_count": comparison.get("pad_token_count"),
        "failed_token_count": comparison.get("failed_token_count"),
        "p50": comparison.get("percentiles", {}).get("p50"),
        "non_finite_count": comparison.get("non_finite_count"),
    }
    passed = (
        report.get("status") == "pass"
        and comparison.get("method") == "fp64_cosine_per_non_pad_token"
        and comparison.get("token_count", 0) > 0
        and comparison.get("failed_token_count") == 0
        and comparison.get("percentiles", {}).get("p50", 0.0) >= MIN_COSINE
        and comparison.get("non_finite_count") == 0
    )
    return passed, record


def check_pad_inflation(repo_root: Path) -> Check:
    paths = [G8_DIR / "layer0_compare.json", G8_DIR / "layer1_compare.json"]
    paths += [G9_DIR / f"layer{layer}_compare_{batch:03d}.json" for batch in range(3) for layer in (0, 1)]
    records = []
    failures = []
    for path in paths:
        passed, record = compare_report_passes(repo_root, path)
        records.append(record)
        if not passed:
            failures.append(str(path))
    return Check("pad_inflation_guard", "pass" if not failures else "fail", {"reports": records})


def check_checkpoint_and_hashes(repo_root: Path) -> Check:
    g8 = load_json(repo_root, GATE_REPORTS["g8_streamed_corpus_repaired"])
    g9_falsifier = load_json(repo_root, FALSIFIER_REPORTS["g9_three_batch_chain"])
    required_g8 = [
        "frozen_layer_hashes_stable",
        "trainable_checkpoint_changed",
        "checkpoint_manifest_present",
    ]
    g8_records = {name: (find_check(g8, name) or {}).get("status") for name in required_g8}
    g9_required_prefixes = [
        "batch_000_frozen_hashes_stable",
        "batch_001_frozen_hashes_stable",
        "batch_002_frozen_hashes_stable",
        "batch_000_trainable_hashes_changed",
        "batch_001_trainable_hashes_changed",
        "batch_002_trainable_hashes_changed",
        "checkpoint_chain_000_to_001",
        "checkpoint_chain_001_to_002",
    ]
    g9_records = {name: (find_check(g9_falsifier, name) or {}).get("status") for name in g9_required_prefixes}
    passed = all(status == "pass" for status in g8_records.values()) and all(
        status == "pass" for status in g9_records.values()
    )
    return Check(
        "checkpoint_chain_and_hash_contract",
        "pass" if passed else "fail",
        {"g8": g8_records, "g9": g9_records},
    )


def check_regressions(repo_root: Path) -> Check:
    g8 = load_json(repo_root, GATE_REPORTS["g8_streamed_corpus_repaired"])
    g9 = load_json(repo_root, GATE_REPORTS["g9_three_batch_chain"])
    g8_metrics = g8.get("metrics", {})
    g9_post = g9.get("post_regressions", {})
    passed = (
        g8_metrics.get("g1_regression_p50", 0.0) >= MIN_COSINE
        and g8_metrics.get("g3_regression_p50", 0.0) >= MIN_COSINE
        and g9_post.get("g1_p50", 0.0) >= MIN_COSINE
        and g9_post.get("g3_p50", 0.0) >= MIN_COSINE
    )
    return Check("g1_g3_regression_floor", "pass" if passed else "fail", {"g8": g8_metrics, "g9": g9_post})


def git_ls_files(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=repo_root,
        text=True,
        check=True,
        capture_output=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def check_committed_artifact_hygiene(repo_root: Path) -> Check:
    forbidden_ext = (".bin", ".safetensors", ".pt", ".pth", ".gguf", ".tflite", ".so", ".a", ".o", ".pyc")
    tracked = git_ls_files(repo_root)
    offenders = [
        path
        for path in tracked
        if path.endswith(forbidden_ext)
        or path.endswith("/selected_text.txt")
        or re.search(r"(^|/)\.env($|\.)", path)
    ]
    return Check(
        "committed_artifact_hygiene",
        "pass" if not offenders else "fail",
        {"forbidden_tracked_files": offenders},
    )


def check_secret_hygiene(repo_root: Path) -> Check:
    secret_re = re.compile(r"hf_[A-Za-z0-9]{20,}|(?:Authorization|Bearer)[:= ]+hf_[A-Za-z0-9]+")
    skipped_ext = {".bin", ".safetensors", ".pt", ".pth", ".gguf", ".tflite", ".so", ".a", ".o", ".pyc"}
    offenders: list[str] = []
    for tracked_path in git_ls_files(repo_root):
        path = repo_root / tracked_path
        if path.suffix in skipped_ext:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if secret_re.search(text):
            offenders.append(tracked_path)
    return Check("hf_token_secret_hygiene", "pass" if not offenders else "fail", {"files_with_secret_patterns": offenders})


def check_claim_scope(repo_root: Path) -> Check:
    g8 = load_json(repo_root, GATE_REPORTS["g8_streamed_corpus_repaired"])
    g9 = load_json(repo_root, GATE_REPORTS["g9_three_batch_chain"])
    scope = {
        "g8_trainable_scope": g8.get("trainable_scope"),
        "g9_objective": g9.get("objective"),
        "g9_batch_count": g9.get("batch_count"),
        "non_claims": [
            "not full Gemma 4 training",
            "not six-hour endurance",
            "not Hexagon NPU training",
            "not public benchmark",
        ],
    }
    passed = (
        g8.get("trainable_scope") == TRAINABLE_SCOPE
        and g9.get("objective") == "three chained phone-native streamed-corpus batches"
        and g9.get("batch_count") == 3
    )
    return Check("overclaim_scope_guard", "pass" if passed else "fail", scope)


def build_report(repo_root: Path, run_id: str) -> dict[str, Any]:
    checks = [
        check_all_reports_pass(repo_root),
        check_falsifiers_pass(repo_root),
        check_historical_g8_rejected(repo_root),
        check_model_revision(repo_root),
        check_g8_authority_path(repo_root),
        check_token_parity(repo_root),
        check_pad_inflation(repo_root),
        check_checkpoint_and_hashes(repo_root),
        check_regressions(repo_root),
        check_committed_artifact_hygiene(repo_root),
        check_secret_hygiene(repo_root),
        check_claim_scope(repo_root),
    ]
    failures = [check for check in checks if check.status != "pass"]
    status = "pass" if not failures else "fail"
    return {
        "schema_version": "gemma4_g10_final_falsifier_review_v1",
        "run_id": run_id,
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "status": status,
        "authority_verdict": (
            "promote_narrow_rank4_two_layer_distillation_adapter_claim"
            if status == "pass"
            else "do_not_promote"
        ),
        "promotion_scope": {
            "allowed": (
                "REDMAGIC phone-native streamed-token Gemma4 E4B two-layer distillation run "
                "with rank-4 post-layer0 adapter SGD checkpoint chain"
            ),
            "forbidden": [
                "full Gemma4 training",
                "six-hour endurance",
                "Hexagon NPU training",
                "generic Snapdragon maximum claim",
                "public benchmark or release claim",
            ],
        },
        "checks": [check.to_json() for check in checks],
        "failed_checks": [check.name for check in failures],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the final G10 falsifier review.")
    parser.add_argument("--repo-root", default=".", type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    run_id = args.run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ_g10_final_review")
    out_dir = args.out_dir
    if not out_dir.is_absolute():
        out_dir = repo_root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    report = build_report(repo_root, run_id)
    report_path = out_dir / "falsifier_report.json"
    gate_path = out_dir / "gate_result.json"
    commands_path = out_dir / "commands.log"
    blockers_path = out_dir / "blockers.md"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    gate = {
        "schema_version": "gemma4_g10_final_gate_result_v1",
        "gate": "Phase 9 final falsifier review",
        "run_id": run_id,
        "status": report["status"],
        "authority_verdict": report["authority_verdict"],
        "final_falsifier_report": str(report_path.relative_to(repo_root)),
        "summary": (
            "All G1-G9 authority evidence survived final falsifier review under the narrow rank-4 adapter claim."
            if report["status"] == "pass"
            else "Final falsifier review found unresolved blockers; promotion is denied."
        ),
    }
    gate_path.write_text(json.dumps(gate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    command = (
        "final_falsifier_review.py --repo-root "
        f"{repo_root} --out-dir {out_dir.relative_to(repo_root)} --run-id {run_id}"
    )
    commands_path.write_text(command + "\n", encoding="utf-8")
    blockers = ["# Final Falsifier Review Blockers", ""]
    if report["failed_checks"]:
        blockers.extend(f"- {name}" for name in report["failed_checks"])
    else:
        blockers.append("None.")
    blockers_path.write_text("\n".join(blockers) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "report": str(report_path), "gate": str(gate_path)}, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
