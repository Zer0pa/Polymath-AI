#!/usr/bin/env python3
"""Matched exact Phase 1 APK A/B runs for Android game modes.

This harness reuses the canonical exact-closure material and the existing APK
JNI path. It stages one trial once, runs repeated standard/custom arms against
the same APK/material, and writes safe JSON evidence only.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
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
    PROMOTED_TRIALS,
    ensure_external_table,
    ensure_internal_table,
    stage_trial_external,
    stage_trial_internal,
    summarize_trial_material,
    utc_stamp,
    validate_export,
)


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


def shell_sample(serial: str, label: str) -> dict[str, Any]:
    commands = {
        "game_modes": ("shell", "cmd", "game", "list-modes", PACKAGE_NAME),
        "game_configs": ("shell", "cmd", "game", "list-configs", PACKAGE_NAME),
        "dumpsys_game": ("shell", "dumpsys", "game"),
        "thermal_headroom_0": ("shell", "cmd", "thermalservice", "headroom", "0"),
        "thermal_headroom_30": ("shell", "cmd", "thermalservice", "headroom", "30"),
        "battery": ("shell", "dumpsys", "battery"),
        "cpu_policy": (
            "shell",
            "for p in /sys/devices/system/cpu/cpufreq/policy*; do "
            "echo POLICY=$p; "
            "for f in related_cpus scaling_cur_freq scaling_min_freq scaling_max_freq cpuinfo_max_freq scaling_governor; do "
            "[ -r \"$p/$f\" ] && printf \"%s=\" \"$f\" && cat \"$p/$f\"; "
            "done; "
            "done",
        ),
        "redmagic_settings": (
            "shell",
            "printf 'performance_mode_value='; settings get global performance_mode_value; "
            "printf 'performance_mode_package='; settings get global performance_mode_package; "
            "printf 'nubia_game_scene_package_name='; settings get system nubia_game_scene_package_name; "
            "printf 'game_app_foreground='; settings get global game_app_foreground; "
            "printf 'game_fan_off_on='; settings get global game_fan_off_on; "
            "printf 'fan_state_of_manual='; settings get global fan_state_of_manual; "
            "printf 'charge_separation_switch='; settings get global charge_separation_switch; "
            "printf 'sys_charge_separation_open='; getprop sys.charge.separation.open; "
            "printf 'vendor_thermal_mode_cur='; getprop vendor.thermal.mode_cur; "
            "printf 'nubia_perf_cpu_cpufreq_ctrl='; getprop nubia.perf.cpu.cpufreq.ctrl",
        ),
    }
    return {
        "label": label,
        "captured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "commands": {name: adb_text(serial, *command) for name, command in commands.items()},
    }


def set_game_mode(serial: str, mode: str) -> dict[str, Any]:
    if mode == "leave":
        return {"requested_mode": mode, "set_command": None}
    before = adb_text(serial, "shell", "cmd", "game", "list-modes", PACKAGE_NAME)
    set_result = adb_text(serial, "shell", "cmd", "game", "mode", mode, PACKAGE_NAME)
    after = adb_text(serial, "shell", "cmd", "game", "list-modes", PACKAGE_NAME)
    return {
        "requested_mode": mode,
        "before": before,
        "set_result": set_result,
        "after": after,
    }


def report_run_ids(serial: str) -> list[str]:
    listing = adb(serial, "shell", "find", ADB_REPORT_ROOT, "-maxdepth", "1", "-type", "d", timeout=20, check=False)
    run_ids = []
    for line in listing.stdout.splitlines():
        leaf = line.rstrip("/").split("/")[-1]
        if leaf and leaf != "phase1":
            run_ids.append(leaf)
    return run_ids


def launch_and_wait_warm(
    serial: str,
    tokenizer_dir: str,
    gbt1_path: str,
    batch_list_path: str,
    workers: int,
    bpe_algorithm: str,
    timeout_sec: int,
) -> str:
    adb(serial, "logcat", "-c", timeout=10, check=False)
    before_dirs = set(report_run_ids(serial))
    adb(
        serial,
        "shell",
        "am",
        "start",
        "-W",
        "-n",
        f"{PACKAGE_NAME}/.MainActivity",
        "-a",
        f"{PACKAGE_NAME}.WRITE_PROBE_REPORT",
        "--es",
        "tokenizer_dir",
        tokenizer_dir,
        "--es",
        "gbt1_path",
        gbt1_path,
        "--es",
        "batch_list_path",
        batch_list_path,
        "--es",
        "bpe_algorithm",
        bpe_algorithm,
        "--ei",
        "worker_count",
        str(workers),
        timeout=60,
    )
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        logs = adb(serial, "logcat", "-d", "-s", "PolymathLabActivity", timeout=10, check=False).stdout
        for line in reversed(logs.splitlines()):
            marker = "adb_probe_report_written run_id="
            if marker in line:
                return line.split(marker, 1)[1].split()[0]
        for run_id in sorted([run_id for run_id in report_run_ids(serial) if run_id not in before_dirs], reverse=True):
            probe = adb(serial, "shell", "test", "-f", f"{ADB_REPORT_ROOT}/{run_id}/gate_result.json", timeout=10, check=False)
            if probe.returncode == 0:
                return run_id
        time.sleep(2.0)
    raise TimeoutError("Timed out waiting for warm app benchmark report marker.")


def warm_foreground(serial: str, warmup_sec: float, game_state_active: bool) -> dict[str, Any]:
    start = adb_text(serial, "shell", "am", "start", "-W", "-n", f"{PACKAGE_NAME}/.MainActivity", timeout=60)
    state = None
    if game_state_active:
        state = adb_text(
            serial,
            "shell",
            "am",
            "start",
            "-W",
            "-n",
            f"{PACKAGE_NAME}/.MainActivity",
            "-a",
            f"{PACKAGE_NAME}.SET_BENCHMARK_STATE",
            "--ez",
            "active",
            "true",
            timeout=60,
        )
    time.sleep(max(0.0, warmup_sec))
    return {
        "start_activity": start,
        "set_benchmark_state": state,
        "post_warm_sample": shell_sample(serial, "warm_foreground_post"),
    }


def find_pulled_file(pulled_root: Path, name: str) -> Path | None:
    for path in pulled_root.rglob(name):
        if path.is_file():
            return path
    return None


def load_json_file(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def summarize_run(
    *,
    arm_index: int,
    mode: str,
    report_dir: Path,
    pulled: Path,
    expected: dict[str, Any],
    baseline: dict[str, Any],
    pre_sample: dict[str, Any],
    post_sample: dict[str, Any],
    mode_evidence: dict[str, Any],
) -> dict[str, Any]:
    app_result = load_json_file(find_pulled_file(pulled, "phase1_app_run_result.json"))
    native_metrics = load_json_file(find_pulled_file(pulled, "native_phase1_metrics.json"))
    batch_metrics = load_json_file(find_pulled_file(pulled, "native_batch_metrics.json"))
    game_authority = load_json_file(find_pulled_file(pulled, "phase1_android_game_authority.json"))
    apk_identity = load_json_file(find_pulled_file(pulled, "apk_identity.json"))

    wrapper_rate = float(app_result.get("token_ids_per_sec", 0.0))
    worker_elapsed_sec = float(batch_metrics.get("elapsed_ns", 0)) / 1_000_000_000.0
    worker_rate = float(expected["token_ids"]) / worker_elapsed_sec if worker_elapsed_sec > 0 else 0.0
    wrapper_wall = float(app_result.get("wall_sec", 0.0))
    worker_decimal_mb_per_sec = (float(expected["input_bytes"]) / 1_000_000.0) / worker_elapsed_sec if worker_elapsed_sec > 0 else 0.0
    wrapper_decimal_mb_per_sec = (float(expected["input_bytes"]) / 1_000_000.0) / wrapper_wall if wrapper_wall > 0 else 0.0
    material_hash = app_result.get("material_hash_hex")
    parity = (
        material_hash == expected["material_hash_hex"]
        and int(app_result.get("records", -1)) == int(expected["records"])
        and int(app_result.get("token_ids", -1)) == int(expected["token_ids"])
    )
    summary = {
        "schema_version": "phase1_exact_game_mode_ab_run_v1",
        "arm_index": arm_index,
        "mode": mode,
        "status": "probe",
        "report_dir": str(report_dir),
        "pulled_report_root": str(pulled),
        "run_id": app_result.get("run_id"),
        "exact_material_parity": "pass" if parity else "fail",
        "records": app_result.get("records"),
        "token_ids": app_result.get("token_ids"),
        "input_bytes": expected["input_bytes"],
        "wrapper_wall_sec": wrapper_wall,
        "wrapper_token_ids_per_sec": wrapper_rate,
        "wrapper_records_per_sec": app_result.get("records_per_sec"),
        "wrapper_input_decimal_mb_per_sec": wrapper_decimal_mb_per_sec,
        "wrapper_latency_ms_per_record": app_result.get("latency_ms_per_record"),
        "worker_window_sec": worker_elapsed_sec,
        "worker_window_token_ids_per_sec": worker_rate,
        "worker_window_input_decimal_mb_per_sec": worker_decimal_mb_per_sec,
        "worker_window_records_per_sec": float(expected["records"]) / worker_elapsed_sec if worker_elapsed_sec > 0 else 0.0,
        "worker_window_latency_ms_per_record": (worker_elapsed_sec * 1000.0) / float(expected["records"]) if worker_elapsed_sec > 0 else 0.0,
        "ratio_vs_termux_wrapper_token_ids_per_sec": wrapper_rate / float(baseline["token_ids_per_sec"]) if baseline["token_ids_per_sec"] else 0.0,
        "ratio_vs_termux_worker_window_token_ids_per_sec": worker_rate / float(baseline["token_ids_per_sec"]) if baseline["token_ids_per_sec"] else 0.0,
        "pss_kb": app_result.get("pss_kb"),
        "rss_kb": app_result.get("rss_kb"),
        "peak_rss_kb": app_result.get("peak_rss_kb"),
        "thread_count": app_result.get("thread_count"),
        "job_count": app_result.get("job_count"),
        "hot_loop_allocations": app_result.get("hot_loop_allocations"),
        "span_errors": app_result.get("span_errors"),
        "parity_mismatches": app_result.get("parity_mismatches"),
        "cpuset_before": app_result.get("cpuset_before"),
        "cpuset_after": app_result.get("cpuset_after"),
        "cpus_allowed_list_before": app_result.get("cpus_allowed_list_before"),
        "cpus_allowed_list_after": app_result.get("cpus_allowed_list_after"),
        "apk_identity": apk_identity,
        "app_side_game_authority": game_authority,
        "native_phase1_metrics": native_metrics,
        "native_batch_metrics": batch_metrics,
        "game_mode_evidence": mode_evidence,
        "pre_sample": pre_sample,
        "post_sample": post_sample,
        "nonclaims": [
            "no_redmagic_rise_claim_without_operator_attestation",
            "no_redmagic_diablo_claim_without_operator_attestation",
            "no_adpf_claim",
            "no_prd_floor_pass_unless_ratio_reaches_minimum",
        ],
    }
    write_json(report_dir / f"arm_{arm_index:02d}_{mode}_summary.json", summary)
    return summary


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return statistics.fmean(values)


def stdev(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    return statistics.stdev(values)


def aggregate(results: list[dict[str, Any]], min_ratio: float, baseline: dict[str, Any]) -> dict[str, Any]:
    by_mode: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        by_mode.setdefault(str(result["mode"]), []).append(result)

    mode_summaries = {}
    for mode, rows in by_mode.items():
        wrapper_rates = [float(row["wrapper_token_ids_per_sec"]) for row in rows]
        worker_rates = [float(row["worker_window_token_ids_per_sec"]) for row in rows]
        mode_summaries[mode] = {
            "count": len(rows),
            "all_exact_parity_pass": all(row["exact_material_parity"] == "pass" for row in rows),
            "wrapper_token_ids_per_sec_mean": mean(wrapper_rates),
            "wrapper_token_ids_per_sec_stdev": stdev(wrapper_rates),
            "wrapper_ratio_vs_termux_mean": (mean(wrapper_rates) or 0.0) / float(baseline["token_ids_per_sec"]),
            "worker_window_token_ids_per_sec_mean": mean(worker_rates),
            "worker_window_token_ids_per_sec_stdev": stdev(worker_rates),
            "worker_window_ratio_vs_termux_mean": (mean(worker_rates) or 0.0) / float(baseline["token_ids_per_sec"]),
            "best_wrapper_token_ids_per_sec": max(wrapper_rates) if wrapper_rates else None,
            "best_worker_window_token_ids_per_sec": max(worker_rates) if worker_rates else None,
        }

    best = max(results, key=lambda row: float(row["wrapper_token_ids_per_sec"])) if results else None
    custom = mode_summaries.get("custom", {})
    standard = mode_summaries.get("standard", {})
    uplift = None
    if custom.get("wrapper_token_ids_per_sec_mean") and standard.get("wrapper_token_ids_per_sec_mean"):
        uplift = float(custom["wrapper_token_ids_per_sec_mean"]) / float(standard["wrapper_token_ids_per_sec_mean"]) - 1.0

    return {
        "schema_version": "phase1_exact_game_mode_ab_aggregate_v1",
        "status": "fail" if not best or float(best["ratio_vs_termux_wrapper_token_ids_per_sec"]) < min_ratio else "pass",
        "promotion_gate": "pass" if best and float(best["ratio_vs_termux_wrapper_token_ids_per_sec"]) >= min_ratio else "fail",
        "min_ratio": min_ratio,
        "termux_baseline": baseline,
        "mode_summaries": mode_summaries,
        "custom_vs_standard_wrapper_mean_uplift": uplift,
        "best_run": best,
        "nonclaims": [
            "custom_mode_uplift_is_not_redmagic_rise_or_diablo",
            "rise_diablo_need_operator_visible_state",
            "adpf_not_tested",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-root", type=Path, default=DEFAULT_EXPORT_ROOT)
    parser.add_argument("--trial", choices=["10k", "100k", "1m"], default="1m")
    parser.add_argument("--staging", choices=["internal", "external"], default="external")
    parser.add_argument("--modes", nargs="+", choices=["standard", "custom", "leave"], default=["standard", "custom", "standard", "custom"])
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--sleep-sec", type=float, default=8.0)
    parser.add_argument("--warm-foreground", action="store_true")
    parser.add_argument("--warm-game-state", action="store_true")
    parser.add_argument("--warmup-sec", type=float, default=10.0)
    parser.add_argument("--timeout-sec", type=int, default=1800)
    parser.add_argument("--min-ratio", type=float, default=0.85)
    parser.add_argument("--out-dir", type=Path, default=Path("runtime/reports/polar_phase1_android_game_authority"))
    args = parser.parse_args()

    export_root = args.export_root.resolve()
    export_identity = validate_export(export_root)
    serial = select_serial()
    trial_dir = export_root / "benchmarks" / PROMOTED_TRIALS[args.trial]
    expected = summarize_trial_material(trial_dir)
    baseline = TERMUX_BASELINES[args.trial]
    stamp = utc_stamp()
    report_root = args.out_dir / f"{stamp}_exact_game_mode_ab_{args.trial}_{args.staging}"
    report_root.mkdir(parents=True, exist_ok=True)
    local_work_dir = Path("/tmp") / f"polymath_phase1_exact_game_mode_ab_{stamp}_{trial_dir.name}"
    local_work_dir.mkdir(parents=True, exist_ok=True)
    remote_dir = (
        f"{INTERNAL_FILES_ROOT}/staged/phase1/exact_ab_{stamp}_{trial_dir.name}"
        if args.staging == "internal"
        else f"{STAGED_ROOT}/exact_ab_{stamp}_{trial_dir.name}"
    )

    batch_path = (
        stage_trial_internal(serial, trial_dir, local_work_dir, remote_dir)
        if args.staging == "internal"
        else stage_trial_external(serial, trial_dir, local_work_dir, remote_dir)
    )
    tokenizer_dir = f"{remote_dir}/tokenizer"
    gbt1_path = (
        ensure_internal_table(serial, export_root / "tokenizer/packed/gemma4_bpe.gbt1", remote_dir)
        if args.staging == "internal"
        else ensure_external_table(serial, export_root / "tokenizer/packed/gemma4_bpe.gbt1", remote_dir)
    )

    write_json(
        report_root / "ab_input_manifest.json",
        {
            "schema_version": "phase1_exact_game_mode_ab_input_manifest_v1",
            "serial": serial,
            "package": PACKAGE_NAME,
            "trial_key": args.trial,
            "trial": trial_dir.name,
            "staging": args.staging,
            "remote_dir": remote_dir,
            "batch_path": batch_path,
            "tokenizer_dir": tokenizer_dir,
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
            "raw_payload_policy": "raw QAI1/PQA1 stayed in /tmp and device staging; report output is JSON only",
        },
    )

    results = []
    before_report_ids = set(adb(serial, "shell", "find", ADB_REPORT_ROOT, "-maxdepth", "1", "-type", "d", timeout=20, check=False).stdout.splitlines())
    for arm_index, mode in enumerate(args.modes):
        arm_dir = report_root / f"arm_{arm_index:02d}_{mode}"
        arm_dir.mkdir(parents=True, exist_ok=True)
        mode_evidence = set_game_mode(serial, mode)
        time.sleep(max(0.0, args.sleep_sec))
        warm_evidence = warm_foreground(serial, args.warmup_sec, args.warm_game_state) if args.warm_foreground else None
        pre_sample = shell_sample(serial, f"arm_{arm_index:02d}_{mode}_pre")
        run_id = (
            launch_and_wait_warm(serial, tokenizer_dir, gbt1_path, batch_path, args.workers, "heap", args.timeout_sec)
            if args.warm_foreground
            else launch_and_wait(serial, tokenizer_dir, gbt1_path, batch_path, args.workers, "heap", args.timeout_sec)
        )
        pulled = pull_run_report(serial, run_id, arm_dir)
        post_sample = shell_sample(serial, f"arm_{arm_index:02d}_{mode}_post")
        findings = scan_forbidden(arm_dir)
        write_json(arm_dir / "forbidden_payload_scan.json", {"status": "pass" if not findings else "fail", "findings": findings})
        if findings:
            raise SystemExit(f"forbidden payload pulled for arm {arm_index}: {findings[:3]}")
        summary = summarize_run(
            arm_index=arm_index,
            mode=mode,
            report_dir=arm_dir,
            pulled=pulled,
            expected=expected,
            baseline=baseline,
            pre_sample=pre_sample,
            post_sample=post_sample,
            mode_evidence=mode_evidence,
        )
        summary["warm_foreground"] = warm_evidence
        write_json(arm_dir / f"arm_{arm_index:02d}_{mode}_summary.json", summary)
        results.append(summary)
        print(
            json.dumps(
                {
                    "arm": arm_index,
                    "mode": mode,
                    "run_id": run_id,
                    "parity": summary["exact_material_parity"],
                    "wrapper_token_ids_per_sec": summary["wrapper_token_ids_per_sec"],
                    "ratio": summary["ratio_vs_termux_wrapper_token_ids_per_sec"],
                },
                sort_keys=True,
            ),
            flush=True,
        )

    aggregate_payload = aggregate(results, args.min_ratio, baseline)
    aggregate_payload["report_root"] = str(report_root)
    aggregate_payload["report_ids_before"] = sorted(before_report_ids)[-20:]
    write_json(report_root / "phase1_exact_game_mode_ab_summary.json", aggregate_payload)
    print(json.dumps({"report_root": str(report_root), "promotion_gate": aggregate_payload["promotion_gate"], "status": aggregate_payload["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
