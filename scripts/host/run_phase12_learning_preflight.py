#!/usr/bin/env python3
"""Run Phase 12 host-verifiable learning-gate preflight artifacts.

This script intentionally stops before claiming authority phone execution when
ADB cannot see the REDMAGIC device. It covers the sequential gates that can be
earned without a live phone transport:

* Gate A: exact H11-H claim and artifact hygiene audit.
* Gate B: compact artifact strategy and index for future long runs.
* Gate C preflight: expanded-scope optimizer repair/build readiness, with the
  actual authority run blocked unless the phone is reachable.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
H11H_DIR = REPO_ROOT / (
    "runtime/reports/gemma4_megakernel/hardware_native_povc/"
    "20260523T225149Z_h11h_combined_povc/H11-H-combined-povc"
)
H11H_GATE = H11H_DIR / "gate_result.json"
PHASE12_ROOT = REPO_ROOT / "runtime/reports/gemma4_megakernel/phase12_hardware_native_learning"
FORBIDDEN_SUFFIXES = (
    ".f32.bin",
    ".bf16.bin",
    ".safetensors",
)
EXPECTED_H11H_VERDICT = "promote_exact_h11h_phone_native_rank4_topk_kl_povc_claim"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compact_utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_command(command: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=check,
    )


def relative(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def artifact_entries(root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        entries.append(
            {
                "path": relative(path),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "forbidden_payload_suffix": path.name.endswith(FORBIDDEN_SUFFIXES),
            }
        )
    return entries


def write_gate_common(report_dir: Path, gate: str, status: str, blockers: list[str]) -> None:
    write_text(
        report_dir / "blockers.md",
        "- None.\n" if not blockers else "".join(f"- {item}\n" for item in blockers),
    )
    write_text(
        report_dir / "falsifier_report.md",
        f"# Phase 12 {gate} Falsifier Report\n\n"
        f"- gate status: {status}.\n"
        "- broad Gemma4 training, HTP backprop, benchmark readiness, and broad capability remain nonclaims.\n"
        + ("" if not blockers else "\n## Blockers\n" + "".join(f"- {item}\n" for item in blockers)),
    )


def gate_a(report_root: Path) -> dict[str, Any]:
    report_dir = report_root / "A-h11h-audit"
    gate = load_json(H11H_GATE)
    predeclared = load_json(H11H_DIR / "predeclared_objective.json")
    combined = load_json(H11H_DIR / "combined_choices.json")
    checkpoint_manifest = load_json(H11H_DIR / "checkpoint_adapter_manifest.json")
    entries = artifact_entries(H11H_DIR)
    forbidden_local = [item for item in entries if item["forbidden_payload_suffix"]]

    checks = {
        "h11h_status_pass": gate.get("status") == "pass",
        "exact_authority_verdict": gate.get("authority_verdict") == EXPECTED_H11H_VERDICT,
        "selected_scope_rank4_only": gate.get("selected_scope") == "post_layer0_rank4_residual_adapter",
        "objective_topk_kl_only": gate.get("objective") == "topk_embedding_kl_distillation_v1",
        "phone_queue_topology": gate.get("runtime_topology") == "phone_local_queue_no_adb_per_iteration",
        "no_runtime_teacher_service": gate.get("runtime_teacher_service_used") is False,
        "predeclared_before_run": predeclared.get("declared_before_phone_training_run") is True,
        "ordinary_opencl_not_recordable_claim": combined.get("queue_backend", "").startswith("ordinary OpenCL"),
        "htp_not_training_claim": "no mutable-section training" in combined.get("htp_role", ""),
        "phone_checkpoint_payloads_not_pulled": not forbidden_local,
        "checkpoint_manifest_points_to_phone": str(checkpoint_manifest.get("train_final_checkpoint_phone", "")).startswith(
            "/data/local/tmp/"
        ),
    }
    blockers = [name for name, ok in checks.items() if not ok]
    status = "pass" if not blockers else "fail"
    audit = {
        "schema_version": "phase12_gate_a_h11h_audit_v1",
        "gate": "A",
        "status": status,
        "checks": checks,
        "promoted_claim": {
            "authority_verdict": gate.get("authority_verdict"),
            "selected_scope": gate.get("selected_scope"),
            "objective": gate.get("objective"),
            "runtime_topology": gate.get("runtime_topology"),
        },
        "nonclaims_preserved": [
            "full Gemma4 training",
            "HTP backprop",
            "public benchmark readiness",
            "broad capability",
        ],
        "artifact_hygiene": {
            "file_count": len(entries),
            "total_bytes": sum(int(item["bytes"]) for item in entries),
            "forbidden_local_payloads": forbidden_local,
        },
        "h11h_gate": relative(H11H_GATE),
    }
    write_json(report_dir / "audit.json", audit)
    write_json(
        report_dir / "gate_result.json",
        {
            "schema_version": "phase12_gate_result_v1",
            "gate": "A",
            "status": status,
            "blockers": blockers,
            "host_report_dir": relative(report_dir),
            "ended_at_utc": utc_now(),
        },
    )
    write_gate_common(report_dir, "Gate A", status, blockers)
    return {"gate": "A", "status": status, "blockers": blockers, "report_dir": relative(report_dir)}


def gate_b(report_root: Path) -> dict[str, Any]:
    report_dir = report_root / "B-compact-artifacts"
    entries = artifact_entries(H11H_DIR)
    total_bytes = sum(int(item["bytes"]) for item in entries)
    largest = sorted(entries, key=lambda item: int(item["bytes"]), reverse=True)[:20]
    forbidden_local = [item for item in entries if item["forbidden_payload_suffix"]]
    iteration_json_count = sum(1 for item in entries if "/iterations/" in item["path"])

    strategy = {
        "schema_version": "phase12_compact_artifact_strategy_v1",
        "goal": "Keep future long-run git artifacts bounded while preserving replayability and authority auditability.",
        "policies": [
            "Hash static model/token assets once per run in a static manifest; later iterations reference that manifest.",
            "Write raw tensors only for predeclared sample/parity iterations; compact iterations emit telemetry, replay manifests, checkpoint manifests, and checksum records only.",
            "Keep trainable adapter payloads and optimizer-state payloads on the phone; pull only manifests and hashes into git.",
            "Represent long traces as JSONL metric rows plus rolled summaries; do not duplicate full loss arrays in multiple artifacts.",
            "Every compact gate must include artifact_manifest.json, blockers.md, falsifier_report.md, gate_result.json, and checksum_chain.jsonl.",
        ],
        "h11h_empirical_index": {
            "file_count": len(entries),
            "total_bytes": total_bytes,
            "iteration_json_file_count": iteration_json_count,
            "largest_files": largest,
            "forbidden_local_payloads": forbidden_local,
        },
        "new_phase12_code_support": {
            "optimizer_state_policy": "AdamW state is checkpoint-local phone payload; manifests record state hashes only.",
            "runner_config_fields": [
                "optimizer",
                "weight_decay",
                "beta1",
                "beta2",
                "optimizer_epsilon",
                "grad_clip_l2",
            ],
        },
    }
    blockers = []
    if forbidden_local:
        blockers.append("H11-H local report contains forbidden raw payload files")
    if not entries:
        blockers.append("H11-H artifact index is empty")
    status = "pass" if not blockers else "fail"
    write_json(report_dir / "compact_artifact_strategy.json", strategy)
    write_json(report_dir / "compact_artifact_index.json", {"schema_version": "phase12_compact_artifact_index_v1", "entries": entries})
    write_json(
        report_dir / "gate_result.json",
        {
            "schema_version": "phase12_gate_result_v1",
            "gate": "B",
            "status": status,
            "blockers": blockers,
            "host_report_dir": relative(report_dir),
            "ended_at_utc": utc_now(),
        },
    )
    write_gate_common(report_dir, "Gate B", status, blockers)
    return {"gate": "B", "status": status, "blockers": blockers, "report_dir": relative(report_dir)}


def adb_devices() -> dict[str, Any]:
    completed = run_command(["adb", "devices", "-l"])
    phone_visible = any(
        line.split()[:2] == ["FY25013101C8", "device"]
        for line in completed.stdout.splitlines()
    )
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "phone_visible": phone_visible,
    }


def source_contains(path: Path, needles: list[str]) -> dict[str, bool]:
    text = path.read_text(encoding="utf-8")
    return {needle: needle in text for needle in needles}


def gate_c_preflight(report_root: Path) -> dict[str, Any]:
    report_dir = report_root / "C-expanded-scope-repair"
    backend = REPO_ROOT / "integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/src/backends/opencl_layer_runner.cpp"
    runner = REPO_ROOT / "integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/src/runner/phase11_runner.cpp"
    header = REPO_ROOT / "integrations/gemma4-snapdragon-megakernel/gemma4_megakernel/include/polymath/gemma4/adapter_training.h"
    host_binary = REPO_ROOT / "build/gemma4_megakernel_host/phase11_runner"
    code_checks = {
        "header_optimizer_config": source_contains(header, ["AdapterOptimizerConfig"]),
        "backend_adamw_clip_state": source_contains(
            backend,
            ["adamw", "grad_clip_l2", "optimizer_state", "combined_gradient_l2"],
        ),
        "runner_config_parse": source_contains(
            runner,
            ["optimizer", "weight_decay", "grad_clip_l2", "run_opencl_streamed_topk_kl_update_rank_optimizer"],
        ),
        "host_phase11_runner_exists": host_binary.exists(),
    }
    adb = adb_devices()
    missing_code = [
        f"{group}:{name}"
        for group, checks in code_checks.items()
        if isinstance(checks, dict)
        for name, ok in checks.items()
        if not ok
    ]
    if not code_checks["host_phase11_runner_exists"]:
        missing_code.append("host_phase11_runner_exists")

    blockers = list(missing_code)
    status = "pass_preflight"
    if blockers:
        status = "fail"
    elif not adb["phone_visible"]:
        status = "blocked_phone_transport_after_repair_build_passed"
        blockers.append("ADB does not list authority phone FY25013101C8; expanded-scope authority run cannot start")

    write_json(
        report_dir / "repair_preflight.json",
        {
            "schema_version": "phase12_gate_c_repair_preflight_v1",
            "code_checks": code_checks,
            "adb": adb,
            "host_build_binary": relative(host_binary) if host_binary.exists() else None,
            "authority_run_plan": {
                "first_trial": "rank16 top-k KL, AdamW, grad_clip_l2=1.0, 8-20 phone-local queued updates",
                "second_trial": "rank32 top-k KL, AdamW, grad_clip_l2=1.0, identical cache/order",
                "promotion_rule": "finite gradients/checkpoints, no authority regression, heldout mini metric beats fixed control",
            },
        },
    )
    write_json(
        report_dir / "gate_result.json",
        {
            "schema_version": "phase12_gate_result_v1",
            "gate": "C",
            "status": status,
            "blockers": blockers,
            "host_report_dir": relative(report_dir),
            "ended_at_utc": utc_now(),
        },
    )
    write_gate_common(report_dir, "Gate C", status, blockers)
    return {"gate": "C", "status": status, "blockers": blockers, "report_dir": relative(report_dir)}


def write_top_level(report_root: Path, gates: list[dict[str, Any]], started_at: str) -> None:
    first_blocked = next((gate for gate in gates if str(gate["status"]).startswith("blocked")), None)
    status = "blocked" if first_blocked else ("pass" if all(gate["status"].startswith("pass") for gate in gates) else "fail")
    write_json(
        report_root / "phase12_gate_status.json",
        {
            "schema_version": "phase12_learning_preflight_status_v1",
            "status": status,
            "started_at_utc": started_at,
            "ended_at_utc": utc_now(),
            "gates": gates,
            "stop_reason": first_blocked["blockers"][0] if first_blocked else None,
            "nonclaims": [
                "full Gemma4 training",
                "HTP backprop",
                "public benchmark readiness",
                "broad capability",
            ],
        },
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default=f"{compact_utc_now()}_phase12_learning_preflight")
    parser.add_argument("--report-root", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started_at = utc_now()
    report_root = args.report_root or PHASE12_ROOT / args.run_id
    gates = [gate_a(report_root), gate_b(report_root), gate_c_preflight(report_root)]
    write_top_level(report_root, gates, started_at)
    print(json.dumps({"status": load_json(report_root / "phase12_gate_status.json")["status"], "report_root": relative(report_root)}, sort_keys=True))
    return 0 if gates[-1]["status"] == "pass_preflight" else 1


if __name__ == "__main__":
    raise SystemExit(main())
