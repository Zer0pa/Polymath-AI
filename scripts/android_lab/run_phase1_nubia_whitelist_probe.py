#!/usr/bin/env python3
"""REDMAGIC/Nubia high-performance profile run for Phase 1 APK child exec.

This stages exact Phase 1 closure material on device, applies the Nubia
performance whitelist as the authority default for this lane, runs the APK
child-exec path, re-applies the high-performance target after the run, and
writes only safe report metadata.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import statistics
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from run_phase1_apk_benchmark import (  # noqa: E402
    ADB_REPORT_ROOT,
    INTERNAL_FILES_ROOT,
    PACKAGE_NAME,
    STAGED_ROOT,
    TERMUX_BASELINES,
    adb,
    launch_and_wait,
    pull_run_report,
    scan_forbidden,
    select_serial,
    sha256_file,
    write_json,
)
from run_phase1_exact_closure_benchmark import (  # noqa: E402
    DEFAULT_EXPORT_ROOT,
    EXPECTED_MATERIAL_HASHES,
    PROMOTED_TRIALS,
    ensure_external_table,
    ensure_internal_table,
    stage_trial_external,
    stage_trial_internal,
    summarize_trial_material,
    utc_stamp,
    validate_export,
)

SETTING_KEYS = [
    "NubiaperformanceMode",
    "db_game_strengthen_mode_list",
    "db_game_strengthen_packagename",
    "performance_mode_package",
    "performance_mode_value",
    "game_strengthen_mode_value",
]

CHILD_EXEC_WARM_FLAGS = 16 | 2 | 4
RUNTIME_SAMPLER_FLAG = 1


def adb_text(serial: str, *args: str, timeout: int = 30) -> dict[str, Any]:
    started = time.perf_counter()
    proc = adb(serial, *args, timeout=timeout, check=False)
    return {
        "cmd": ["adb", "-s", serial, *args],
        "returncode": proc.returncode,
        "elapsed_sec": time.perf_counter() - started,
        "stdout_tail": proc.stdout[-12000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def get_setting(serial: str, key: str) -> str:
    return adb(serial, "shell", "settings", "get", "global", key, timeout=20, check=False).stdout.strip()


def put_setting(serial: str, key: str, value: str) -> None:
    adb(serial, "shell", "settings", "put", "global", key, value, timeout=20)


def snapshot_settings(serial: str) -> dict[str, str]:
    return {key: get_setting(serial, key) for key in SETTING_KEYS}


def target_settings() -> dict[str, str]:
    return {
        "NubiaperformanceMode": f"{PACKAGE_NAME}+300,com.primatelabs.geekbench6+300,",
        "db_game_strengthen_mode_list": f"null,{PACKAGE_NAME}+6,com.primatelabs.geekbench6+6",
        "db_game_strengthen_packagename": PACKAGE_NAME,
        "performance_mode_package": PACKAGE_NAME,
        "performance_mode_value": "2",
        "game_strengthen_mode_value": "6",
    }


def apply_settings(serial: str, settings: dict[str, str]) -> None:
    for key, value in settings.items():
        put_setting(serial, key, value)


def current_game_mode(serial: str) -> str | None:
    text = adb(serial, "shell", "cmd", "game", "list-modes", PACKAGE_NAME, timeout=20, check=False).stdout.strip()
    match = re.search(r"current mode: ([A-Za-z0-9_-]+)", text)
    return match.group(1) if match else None


def set_game_mode(serial: str, mode: str | None) -> dict[str, Any]:
    if not mode:
        return {"requested_mode": None, "set_result": None}
    before = adb_text(serial, "shell", "cmd", "game", "list-modes", PACKAGE_NAME)
    set_result = adb_text(serial, "shell", "cmd", "game", "mode", mode, PACKAGE_NAME)
    after = adb_text(serial, "shell", "cmd", "game", "list-modes", PACKAGE_NAME)
    return {
        "requested_mode": mode,
        "before": before,
        "set_result": set_result,
        "after": after,
    }


def frequency_snapshot(serial: str) -> dict[str, Any]:
    command = (
        "for c in 0 1 2 3 4 5 6 7; do "
        "b=/sys/devices/system/cpu/cpu${c}/cpufreq; "
        "printf 'cpu%s cur=' \"$c\"; cat $b/scaling_cur_freq; "
        "printf 'cpu%s min=' \"$c\"; cat $b/scaling_min_freq; "
        "printf 'cpu%s max=' \"$c\"; cat $b/scaling_max_freq; "
        "printf 'cpu%s hwmax=' \"$c\"; cat $b/cpuinfo_max_freq; "
        "done"
    )
    return adb_text(serial, "shell", command, timeout=20)


def stage_exact_trial(args: argparse.Namespace, serial: str, report_root: Path) -> dict[str, Any]:
    export_root = args.export_root.resolve()
    export_identity = validate_export(export_root)
    trial_dir = export_root / "benchmarks" / PROMOTED_TRIALS[args.trial]
    expected = summarize_trial_material(trial_dir)
    expected_hash = EXPECTED_MATERIAL_HASHES[args.trial]
    if expected["material_hash_hex"] != expected_hash:
        raise SystemExit(f"{trial_dir.name} material hash mismatch: {expected['material_hash_hex']} != {expected_hash}")

    stamp = utc_stamp()
    local_work_dir = Path("/tmp") / f"polymath_phase1_high_profile_{stamp}_{trial_dir.name}"
    local_work_dir.mkdir(parents=True, exist_ok=True)
    remote_dir = (
        f"{INTERNAL_FILES_ROOT}/staged/phase1/high_profile_{stamp}_{trial_dir.name}"
        if args.staging == "internal"
        else f"{STAGED_ROOT}/high_profile_{stamp}_{trial_dir.name}"
    )
    if args.staging == "internal":
        batch_path = stage_trial_internal(serial, trial_dir, local_work_dir, remote_dir)
        gbt1_path = ensure_internal_table(serial, export_root / "tokenizer/packed/gemma4_bpe.gbt1", remote_dir)
    else:
        batch_path = stage_trial_external(serial, trial_dir, local_work_dir, remote_dir)
        gbt1_path = ensure_external_table(serial, export_root / "tokenizer/packed/gemma4_bpe.gbt1", remote_dir)

    manifest = {
        "schema_version": "phase1_high_profile_input_manifest_v1",
        "serial": serial,
        "package": PACKAGE_NAME,
        "trial_key": args.trial,
        "trial": trial_dir.name,
        "staging": args.staging,
        "remote_dir": remote_dir,
        "batch_path": batch_path,
        "tokenizer_dir": f"{remote_dir}/tokenizer",
        "gbt1_path": gbt1_path,
        "expected": {key: value for key, value in expected.items() if key != "output_sha256s"},
        "export_identity": {
            "manifest_sha256": export_identity["manifest_sha256"],
            "sha256sums_sha256": export_identity["sha256sums_sha256"],
            "sha256sums_status": export_identity["manifest"].get("sha256sums_status"),
            "file_count": export_identity["manifest"].get("file_count"),
            "total_bytes": export_identity["manifest"].get("total_bytes"),
        },
        "artifact_hashes": {
            "export_manifest_sha256": sha256_file(export_root / "EXPORT_MANIFEST.json"),
            "gbt1_sha256": sha256_file(export_root / "tokenizer/packed/gemma4_bpe.gbt1"),
            "phase1_source_sha256": sha256_file(export_root / "source/native/polar_phase1_zig/phase1_qa_stream.zig"),
        },
        "raw_payload_policy": "raw QAI1/PQA1 stayed in /tmp and device staging; report output is JSON/Markdown only",
    }
    write_json(report_root / "input_manifest.json", manifest)
    return {"expected": expected, "manifest": manifest}


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def trial_rates(pulled: Path, expected_token_ids: int) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(pulled.glob("native_batch_metrics_trial*.json")):
        payload = load_json(path)
        elapsed_ns = int(payload.get("elapsed_ns", 0) or 0)
        elapsed_sec = elapsed_ns / 1_000_000_000.0 if elapsed_ns > 0 else None
        rate = float(expected_token_ids) / elapsed_sec if elapsed_sec else None
        rows.append(
            {
                "file": path.name,
                "elapsed_ns": elapsed_ns or None,
                "elapsed_sec": elapsed_sec,
                "token_ids_per_sec_derived": rate,
            }
        )
    return rows


def summarize_probe(
    *,
    report_root: Path,
    pulled: Path,
    run_id: str,
    flags: int,
    expected: dict[str, Any],
    original_settings: dict[str, str],
    applied_settings: dict[str, str],
    after_run_settings: dict[str, str],
    final_settings: dict[str, str],
    settings_target: dict[str, str],
    game_mode_before: str | None,
    game_mode_target: dict[str, Any],
    frequency_before: dict[str, Any],
    frequency_after_apply: dict[str, Any],
    frequency_after_final_apply: dict[str, Any],
    launch_stdout: str,
    forbidden_findings: list[str],
) -> dict[str, Any]:
    app = load_json(pulled / "phase1_app_run_result.json")
    native = load_json(pulled / "native_probe_result.json")
    phase_metrics = load_json(pulled / "native_phase1_metrics.json")
    rates = trial_rates(pulled, int(expected["token_ids"]))
    rate_values = [float(row["token_ids_per_sec_derived"]) for row in rates if row.get("token_ids_per_sec_derived")]
    material_pass = app.get("material_hash_hex") == expected["material_hash_hex"]
    records_pass = int(app.get("records", -1)) == int(expected["records"])
    tokens_pass = int(app.get("token_ids", -1)) == int(expected["token_ids"])
    baseline = TERMUX_BASELINES["1m"]
    best_rate = max(rate_values) if rate_values else None
    mean_rate = statistics.fmean(rate_values) if rate_values else None
    summary = {
        "schema_version": "phase1_apk_nubia_high_profile_probe_v1",
        "status": "probe",
        "run_id": run_id,
        "flags": flags,
        "settings_previous": original_settings,
        "settings_target": settings_target,
        "settings_applied": applied_settings,
        "settings_after_run_before_reapply": after_run_settings,
        "settings_final": final_settings,
        "settings_final_match_target": final_settings == settings_target,
        "settings_policy": "high_performance_profile_is_authority_default_no_restore",
        "game_mode_before": game_mode_before,
        "game_mode_target": game_mode_target,
        "frequency_before": frequency_before,
        "frequency_after_apply": frequency_after_apply,
        "frequency_after_final_apply": frequency_after_final_apply,
        "launch_stdout": launch_stdout,
        "exact_material_parity": "pass" if material_pass and records_pass and tokens_pass else "fail",
        "record_count_parity": records_pass,
        "token_count_parity": tokens_pass,
        "material_hash_parity": material_pass,
        "app_token_ids_per_sec": app.get("token_ids_per_sec"),
        "native_token_ids_per_sec": native.get("token_ids_per_sec"),
        "native_phase1_token_ids_per_sec": phase_metrics.get("token_ids_per_sec"),
        "native_wall_sec": native.get("wall_sec"),
        "best_trial_token_ids_per_sec_derived": best_rate,
        "mean_trial_token_ids_per_sec_derived": mean_rate,
        "ratio_vs_termux_promoted_best_trial": (best_rate / float(baseline["token_ids_per_sec"])) if best_rate else None,
        "termux_promoted_baseline": baseline,
        "native_phase1_exec_path": native.get("phase1_exec_path"),
        "child_exec_enabled": phase_metrics.get("child_exec_enabled"),
        "child_exec_errno": phase_metrics.get("child_exec_errno"),
        "native_cpuset_before": native.get("cpuset_before"),
        "native_cpus_allowed_before": native.get("cpus_allowed_list_before"),
        "native_sched_excerpt_before": phase_metrics.get("sched_excerpt_before"),
        "cpu_frequency_sampler": phase_metrics.get("cpu_frequency_sampler"),
        "trials_derived_from_elapsed_ns": rates,
        "forbidden_payload_scan": {
            "status": "pass" if not forbidden_findings else "fail",
            "findings": forbidden_findings,
        },
        "nonclaims": [
            "no_standard_profile_fallback_in_authority_path",
            "high_profile_is_device_policy_not_tokenizer_code",
            "no_phase1_promotion_claim",
            "no_game_mode_or_rise_diablo_claim",
        ],
    }
    write_json(report_root / "phase1_nubia_high_profile_probe_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--trial", choices=["1m"], default="1m")
    parser.add_argument("--staging", choices=["internal", "external"], default="external")
    parser.add_argument("--timeout-sec", type=int, default=1800)
    parser.add_argument("--out-dir", type=Path, default=Path("runtime/reports/polar_phase1_android_game_authority"))
    parser.add_argument("--runtime-sampler", action="store_true")
    args = parser.parse_args()

    serial = select_serial()
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    report_root = args.out_dir / f"{stamp}_phase1_apk_high_profile_no_sampler_authority"
    if args.runtime_sampler:
        report_root = args.out_dir / f"{stamp}_phase1_apk_high_profile_sampler_authority"
    report_root.mkdir(parents=True, exist_ok=True)

    staged = stage_exact_trial(args, serial, report_root)
    manifest = staged["manifest"]
    expected = staged["expected"]
    settings_original = snapshot_settings(serial)
    settings_target = target_settings()
    game_mode_before = current_game_mode(serial)
    frequency_before = frequency_snapshot(serial)
    flags = CHILD_EXEC_WARM_FLAGS | (RUNTIME_SAMPLER_FLAG if args.runtime_sampler else 0)
    run_id = ""
    launch_stdout = ""
    settings_applied: dict[str, str] = {}
    settings_after_run: dict[str, str] = {}
    game_mode_target: dict[str, Any] = {}
    frequency_after_apply: dict[str, Any] = {}
    frequency_after_final_apply: dict[str, Any] = {}
    settings_final: dict[str, str] = {}

    try:
        apply_settings(serial, settings_target)
        settings_applied = snapshot_settings(serial)
        game_mode_target = set_game_mode(serial, "standard")
        frequency_after_apply = frequency_snapshot(serial)
        adb(serial, "logcat", "-c", timeout=10, check=False)
        run_id = launch_and_wait(
            serial,
            str(manifest["tokenizer_dir"]),
            str(manifest["gbt1_path"]),
            str(manifest["batch_path"]),
            8,
            "heap",
            args.timeout_sec,
            run_flags=flags,
        )
        launch_stdout = "see adb logcat marker; launch completed through existing app runner"
        settings_after_run = snapshot_settings(serial)
    finally:
        apply_settings(serial, settings_target)
        frequency_after_final_apply = frequency_snapshot(serial)
        settings_final = snapshot_settings(serial)
        write_json(
            report_root / "settings_profile_evidence.json",
            {
                "previous": settings_original,
                "target": settings_target,
                "applied": settings_applied,
                "after_run_before_reapply": settings_after_run,
                "final": settings_final,
                "final_match_target": settings_final == settings_target,
                "policy": "high_performance_profile_is_authority_default_no_restore",
                "game_mode_before": game_mode_before,
            },
        )

    if not run_id:
        raise SystemExit("No APK report run_id was produced.")

    pulled = pull_run_report(serial, run_id, report_root)
    findings = scan_forbidden(report_root)
    write_json(
        report_root / "forbidden_payload_scan.json",
        {"schema_version": "phase1_high_profile_forbidden_payload_scan_v1", "status": "pass" if not findings else "fail", "findings": findings},
    )
    if findings:
        raise SystemExit(f"Forbidden payloads were pulled into report tree: {findings[:3]}")

    summary = summarize_probe(
        report_root=report_root,
        pulled=pulled,
        run_id=run_id,
        flags=flags,
        expected=expected,
        original_settings=settings_original,
        applied_settings=settings_applied,
        after_run_settings=settings_after_run,
        final_settings=settings_final,
        settings_target=settings_target,
        game_mode_before=game_mode_before,
        game_mode_target=game_mode_target,
        frequency_before=frequency_before,
        frequency_after_apply=frequency_after_apply,
        frequency_after_final_apply=frequency_after_final_apply,
        launch_stdout=launch_stdout,
        forbidden_findings=findings,
    )
    print(
        json.dumps(
            {
                "status": summary["status"],
                "report_root": str(report_root),
                "run_id": run_id,
                "exact_material_parity": summary["exact_material_parity"],
                "settings_final_match_target": summary["settings_final_match_target"],
                "best_trial_token_ids_per_sec_derived": summary["best_trial_token_ids_per_sec_derived"],
                "forbidden_payload_scan": summary["forbidden_payload_scan"]["status"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
