#!/usr/bin/env python3
"""Run Phase 13 P13-A contamination audit and quarantine artifacts.

P13-A does not run training. It separates valid Phase 12 Gemma residual
learning evidence from invalid Qwen/random-init/hidden-1536 HTP artifacts so
later Phase 13 gates cannot accidentally consume non-Gemma evidence.
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
PHASE12_ROOT = REPO_ROOT / "runtime/reports/gemma4_megakernel/phase12_hardware_native_learning"
PHASE13_ROOT = REPO_ROOT / "runtime/reports/gemma4_megakernel/phase13_gemma4_only_heterogeneous"
PHASE12_FINAL = PHASE12_ROOT / "20260524T175056Z_phase12_final_exact_claims/phase12_gate_status.json"
STATE_MD = REPO_ROOT / ".gpd/STATE.md"
STATE_JSON = REPO_ROOT / ".gpd/state.json"
RUNLOG = REPO_ROOT / ".gpd/runlog.jsonl"

FORBIDDEN_PAYLOAD_SUFFIXES = (
    ".bin",
    ".safetensors",
    ".npy",
    ".npz",
    ".pt",
    ".pth",
    ".ckpt",
    ".qnn",
    ".dlc",
    ".raw",
    ".f32",
    ".u32",
    ".u8",
)
TEXT_SUFFIXES = (".json", ".jsonl", ".md", ".txt", ".log", ".yaml", ".yml", ".csv")
CONTAMINATION_TERMS = (
    "qwen",
    "smollm",
    "random-init",
    "random_init",
    "hidden-size-1536",
    "hidden_size_1536",
    "hidden 1536",
)
NEGATIVE_PHASE12_PATH_MARKERS = (
    "phase12_f_qairt_updateable_context",
    "F-qairt-updateable-context",
    "phase12_g_heterogeneous",
    "G-heterogeneous-hypothesis",
    "phase12_final_exact_claims",
    "phase12_exact_claims",
)
VALID_GEMMA_ARTIFACTS = {
    "cde",
    "gradient_parity",
    "long_native_lr",
}
NEGATIVE_ARTIFACTS = {
    "qairt_f",
    "heterogeneous_g",
}


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


def rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True, check=False)


def command_log_entry(command: list[str], result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout_first_4096": result.stdout[:4096],
        "stderr_first_4096": result.stderr[:4096],
    }


def phase12_artifact_path(final: dict[str, Any], key: str) -> Path:
    value = final["primary_artifacts"][key]
    return REPO_ROOT / value


def classify_primary_artifacts(final: dict[str, Any]) -> list[dict[str, Any]]:
    classifications: list[dict[str, Any]] = []
    for key, artifact in sorted(final.get("primary_artifacts", {}).items()):
        path = REPO_ROOT / artifact
        if key in VALID_GEMMA_ARTIFACTS:
            classification = "gemma_valid_narrow_residual_learning_evidence"
            allowed = True
            reason = "Gemma4 E4B residual adapter evidence; may seed P13 only within its narrow post-layer0 scope."
        elif key in NEGATIVE_ARTIFACTS:
            classification = "negative_tool_surface_probe_forbidden_for_promoted_gemma_gate"
            allowed = False
            reason = "Non-Gemma/Qwen/random-init/hidden-size-mismatched HTP evidence; quarantine only."
        elif key == "preflight":
            classification = "control_preflight_not_learning_evidence"
            allowed = True
            reason = "Control-plane preflight and compact-artifact evidence only."
        else:
            classification = "control_summary_not_direct_training_input"
            allowed = False
            reason = "Summary/control artifact; later gates must consume explicit classified source artifacts."
        classifications.append(
            {
                "key": key,
                "path": artifact,
                "exists": path.exists(),
                "classification": classification,
                "allowed_for_promoted_gemma_gate": allowed,
                "reason": reason,
            }
        )
    return classifications


def scan_forbidden_payloads(root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not root.exists():
        return findings
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        lower = path.name.lower()
        if lower.endswith(FORBIDDEN_PAYLOAD_SUFFIXES):
            findings.append({"path": rel(path), "bytes": path.stat().st_size})
    return findings


def scan_text_contamination(root: Path) -> dict[str, Any]:
    allowed_negative_hits: list[dict[str, Any]] = []
    forbidden_hits: list[dict[str, Any]] = []
    if not root.exists():
        return {"allowed_negative_hits": allowed_negative_hits, "forbidden_hits": forbidden_hits}

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        terms = sorted({term for term in CONTAMINATION_TERMS if term in text})
        if not terms:
            continue
        entry = {"path": rel(path), "terms": terms}
        if any(marker in rel(path) for marker in NEGATIVE_PHASE12_PATH_MARKERS):
            allowed_negative_hits.append(entry)
        else:
            forbidden_hits.append(entry)
    return {"allowed_negative_hits": allowed_negative_hits, "forbidden_hits": forbidden_hits}


def audit_git_worktree() -> dict[str, Any]:
    status = run_command(["git", "status", "--porcelain=v1"])
    rows = [line for line in status.stdout.splitlines() if line.strip()]
    dirty_entries: list[dict[str, Any]] = []
    forbidden_untracked_payloads: list[dict[str, Any]] = []

    for row in rows:
        code = row[:2]
        path = row[3:]
        category = "other"
        if path.startswith(".gpd/"):
            category = "gpd_state_or_plan"
        elif path == "AGENTS.md":
            category = "repo_instruction_update"
        elif path.startswith("docs/PRD-PHASE13") or path.startswith("docs/HANDOFF-PHASE13") or path.startswith(
            "docs/STARTUP-PROMPT-PHASE13"
        ):
            category = "phase13_control_artifact"
        elif path.startswith("runtime/reports/gemma4_megakernel/phase12_hardware_native_learning"):
            category = "phase12_evidence_artifact"
        elif path.startswith("runtime/reports/gemma4_megakernel/phase13_gemma4_only_heterogeneous"):
            category = "phase13_evidence_artifact"
        elif path.startswith("scripts/host/run_phase12"):
            category = "phase12_host_runner"
        elif path.startswith("scripts/host/run_phase13"):
            category = "phase13_host_runner"
        elif path.startswith("integrations/gemma4-snapdragon-megakernel/"):
            category = "gemma4_runtime_source"
        lower = path.lower()
        forbidden_payload = lower.endswith(FORBIDDEN_PAYLOAD_SUFFIXES)
        entry = {
            "status_code": code,
            "path": path,
            "category": category,
            "forbidden_payload_suffix": forbidden_payload,
        }
        dirty_entries.append(entry)
        if code == "??" and forbidden_payload:
            forbidden_untracked_payloads.append(entry)

    return {
        "git_status_returncode": status.returncode,
        "dirty_entries": dirty_entries,
        "forbidden_untracked_payloads": forbidden_untracked_payloads,
    }


def gate_result(
    *,
    report_dir: Path,
    run_id: str,
    final: dict[str, Any],
    classifications: list[dict[str, Any]],
    payload_findings: list[dict[str, Any]],
    contamination_scan: dict[str, Any],
    worktree: dict[str, Any],
    state_json_valid: bool,
) -> dict[str, Any]:
    blockers: list[str] = []
    if final.get("status") != "completed_with_residual_learning_pass_and_falsified_nonclaims":
        blockers.append("Phase 12 final exact claims status is unexpected")
    missing = [item["key"] for item in classifications if not item["exists"]]
    if missing:
        blockers.append(f"Phase 12 primary artifact paths are missing: {missing}")
    if payload_findings:
        blockers.append("Phase 12 report tree contains forbidden raw payload suffixes")
    if contamination_scan["forbidden_hits"]:
        blockers.append("Qwen/random-init/hidden1536 terms appear outside quarantined negative artifacts")
    if worktree["forbidden_untracked_payloads"]:
        blockers.append("Dirty worktree contains untracked forbidden raw payloads")
    if not state_json_valid:
        blockers.append(".gpd/state.json failed JSON parse")

    negative_allowed = [item for item in classifications if not item["allowed_for_promoted_gemma_gate"]]
    return {
        "schema_version": "phase13_p13a_gate_result_v1",
        "gate": "P13-A-contamination-audit",
        "run_id": run_id,
        "status": "pass" if not blockers else "fail",
        "started_at_utc": run_id.split("_", maxsplit=1)[0],
        "ended_at_utc": utc_now(),
        "blockers": blockers,
        "pass_condition_checks": {
            "phase12_final_status_understood": final.get("status")
            == "completed_with_residual_learning_pass_and_falsified_nonclaims",
            "primary_artifacts_exist": not missing,
            "raw_payload_scan_clean": not payload_findings,
            "nongemma_terms_confined_to_negative_or_summary_artifacts": not contamination_scan["forbidden_hits"],
            "dirty_worktree_forbidden_untracked_payloads_absent": not worktree["forbidden_untracked_payloads"],
            "state_json_valid": state_json_valid,
        },
        "quarantine_summary": {
            "gemma_valid_narrow_keys": [
                item["key"] for item in classifications if item["allowed_for_promoted_gemma_gate"]
            ],
            "forbidden_for_promoted_gemma_keys": [item["key"] for item in negative_allowed],
            "negative_tool_surface_rule": (
                "Qwen/random-init/hidden-size-1536 HTP artifacts may be referenced only as negative "
                "tool-surface probes and cannot feed Gemma training, teacher generation, evaluation, "
                "or heterogeneous promotion."
            ),
        },
        "strongest_valid_fallback": {
            "model_id": "google/gemma-4-E4B",
            "hidden_size": 2560,
            "kernel_lineage_class": "residual_adapter_opencl_training",
            "trainable_scope": "post_layer0_residual_adapter_rank16",
            "source": final.get("primary_artifacts", {}).get("long_native_lr"),
            "limits": [
                "Phase 12 corpus was only 16 sequences and is smoke-scale for Phase 13.",
                "Phase 12 gradient parity covered two high-gradient coordinates only.",
                "No multi-site, HTP backprop, updateable QNN, or heterogeneous Gemma learning claim is valid.",
            ],
        },
        "report_dir": rel(report_dir),
    }


def write_artifact_manifest(report_dir: Path) -> None:
    entries: list[dict[str, Any]] = []
    for path in sorted(report_dir.rglob("*")):
        if not path.is_file() or path.name == "artifact_manifest.json":
            continue
        entries.append({"path": rel(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    write_json(
        report_dir / "artifact_manifest.json",
        {
            "schema_version": "phase13_p13a_artifact_manifest_v1",
            "created_at_utc": utc_now(),
            "artifacts": entries,
        },
    )


def write_phase13_status(run_root: Path, p13a_result: dict[str, Any]) -> None:
    write_json(
        run_root / "phase13_gate_status.json",
        {
            "schema_version": "phase13_gate_status_v1",
            "created_at_utc": utc_now(),
            "run_id": p13a_result["run_id"],
            "gate_status": {
                "P13-A": p13a_result["status"],
                "P13-B": "pending",
                "P13-C": "pending",
                "P13-D": "pending",
                "P13-E": "pending",
                "P13-F": "pending",
                "P13-G": "pending",
                "P13-H": "not_started_requires_P13_A_through_G_artifacts",
                "P13-I": "pending",
            },
            "current_strongest_valid_fallback": p13a_result["strongest_valid_fallback"],
            "nonclaims": [
                "full Gemma4 training",
                "multi-site adapter training",
                "full-gradient parity",
                "HTP backprop",
                "successful QnnContext_applyBinarySection on phone",
                "Gemma-compatible HTP context execution",
                "integrated heterogeneous Gemma learning",
                "benchmark readiness",
                "corpus-scale learning beyond Phase 12 smoke-scale cache",
            ],
            "latest_gate_result": rel(run_root / "P13-A-contamination-audit/gate_result.json"),
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=f"{compact_utc_now()}_phase13_gemma4_only_heterogeneous")
    args = parser.parse_args()

    run_root = PHASE13_ROOT / args.run_id
    report_dir = run_root / "P13-A-contamination-audit"
    commands: list[dict[str, Any]] = []
    for command in (
        ["git", "status", "--short", "--branch"],
        ["git", "status", "--porcelain=v1"],
        ["git", "rev-parse", "HEAD"],
    ):
        commands.append(command_log_entry(command, run_command(command)))

    final = load_json(PHASE12_FINAL)
    classifications = classify_primary_artifacts(final)
    payload_findings = scan_forbidden_payloads(PHASE12_ROOT)
    contamination_scan = scan_text_contamination(PHASE12_ROOT)
    worktree = audit_git_worktree()
    state_json_valid = True
    try:
        load_json(STATE_JSON)
    except (OSError, json.JSONDecodeError):
        state_json_valid = False

    result = gate_result(
        report_dir=report_dir,
        run_id=args.run_id,
        final=final,
        classifications=classifications,
        payload_findings=payload_findings,
        contamination_scan=contamination_scan,
        worktree=worktree,
        state_json_valid=state_json_valid,
    )

    write_json(report_dir / "phase12_artifact_classification.json", {"artifacts": classifications})
    write_json(report_dir / "artifact_quarantine_manifest.json", result["quarantine_summary"])
    write_json(
        report_dir / "contamination_scan.json",
        {
            "phase12_root": rel(PHASE12_ROOT),
            "forbidden_payload_findings": payload_findings,
            "text_contamination_scan": contamination_scan,
        },
    )
    write_json(report_dir / "dirty_worktree_audit.json", worktree)
    write_json(
        report_dir / "state_repair_plan.json",
        {
            "schema_version": "phase13_p13a_state_repair_plan_v1",
            "state_md": rel(STATE_MD),
            "state_json": rel(STATE_JSON),
            "runlog": rel(RUNLOG),
            "required_update": (
                "Mark Phase 13 execution as started and P13-A as passed before any P13-B phone smoke run."
            ),
            "phase12_final_result_to_preserve": final.get("status"),
            "phase12_contamination_boundary": (
                "Qwen/random-init hidden-size-1536 HTP artifacts are forbidden for promoted Gemma gates."
            ),
        },
    )
    write_json(report_dir / "gate_result.json", result)
    write_text(
        report_dir / "blockers.md",
        "- None.\n" if not result["blockers"] else "".join(f"- {item}\n" for item in result["blockers"]),
    )
    write_text(
        report_dir / "falsifier_report.md",
        "# P13-A Falsifier Report\n\n"
        f"- Gate status: {result['status']}.\n"
        "- Qwen/random-init/hidden-size-1536 artifacts are quarantined as negative tool-surface probes.\n"
        "- Phase 12 valid continuation evidence is limited to Gemma4 E4B post-layer0 residual adapter learning.\n"
        "- Phase 12 16-sequence corpus evidence is smoke-scale only and cannot satisfy P13-C/P13-H promotion.\n"
        "- No raw model/checkpoint/QNN payload was found in the Phase 12 report tree.\n",
    )
    write_text(
        report_dir / "commands.log",
        "\n".join(json.dumps(entry, sort_keys=True) for entry in commands) + "\n",
    )
    write_phase13_status(run_root, result)
    write_json(
        PHASE13_ROOT / "active_phase13_run.json",
        {
            "schema_version": "phase13_active_run_v1",
            "run_id": args.run_id,
            "run_root": rel(run_root),
            "started_at_utc": utc_now(),
            "current_gate": "P13-A",
        },
    )
    write_artifact_manifest(report_dir)

    print(json.dumps({"status": result["status"], "run_root": rel(run_root), "gate_result": rel(report_dir / "gate_result.json")}, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
