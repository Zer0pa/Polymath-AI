#!/usr/bin/env python3
"""Launch and audit the Phase 11 H11-A phone-resident queue runner.

The host starts the phone daemon, creates one disconnect marker, optionally
stops the local ADB server for the required hold window, and then pulls only
git-allowed audit artifacts. It does not drive training iterations.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shlex
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any


DEFAULT_SERIAL = "FY25013101C8"
DEFAULT_PHONE_ROOT = "/data/local/tmp/polymath_gemma4_gate"
DEFAULT_TOKEN_CACHES = (
    "hf_stream/20260517T083219Z_phase10_hf_auth_token_bridge_baseline_cache",
    "sustained_g9_20260517T071405Z/cache_000",
    "sustained_g9_20260517T071405Z/cache_001",
    "sustained_g9_20260517T071405Z/cache_002",
)
DEFAULT_ASSET_DIR = "streamed_assets/g8_layer01_20260517T071405Z"
DEFAULT_LAYER0_PACK = "layer_pack/gemma4_e4b_layer0_seq128_v0"
DEFAULT_LAYER1_PACK = "layer_pack/gemma4_e4b_layer1_seq128_v0"
DEFAULT_INITIAL_CHECKPOINT = "adapter_training/g5g6_rank4_20260517T040000Z/checkpoint"
GIT_ALLOWED_GATE_FILES = (
    "daemon_design_note.md",
    "queue_schema.json",
    "commands.log",
    "daemon_static_artifact_manifest.json",
    "cold_start_probe.json",
    "one_shot_baseline.json",
    "telemetry.jsonl",
    "timing_breakdown.json",
    "blockers.md",
    "falsifier_report.md",
    "gate_result.json",
    "artifact_manifest.json",
    "disconnect_log.md",
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compact_utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def q(value: str) -> str:
    return shlex.quote(value)


def run_command(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, text=True, capture_output=True)
    if check and completed.returncode != 0:
        joined = " ".join(shlex.quote(part) for part in command)
        raise RuntimeError(
            f"command failed ({completed.returncode}): {joined}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def adb(serial: str, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run_command(["adb", "-s", serial, *args], check=check)


def adb_shell(serial: str, command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return adb(serial, ["shell", command], check=check)


def adb_push(serial: str, local_path: Path, remote_path: str) -> None:
    adb(serial, ["push", str(local_path), remote_path])


def adb_pull(serial: str, remote_path: str, local_path: Path, *, check: bool = False) -> bool:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    completed = adb(serial, ["pull", remote_path, str(local_path)], check=False)
    if completed.returncode == 0:
        return True
    if check:
        raise RuntimeError(
            f"adb pull failed for {remote_path}:\n{completed.stdout}\n{completed.stderr}"
        )
    return False


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def active_training_seconds(telemetry: dict[str, Any]) -> float:
    return (
        float(telemetry.get("token_to_hidden_elapsed_seconds", 0.0))
        + sum(float(value) for value in telemetry.get("layer_elapsed_seconds", []))
        + float(telemetry.get("adapter_elapsed_seconds", 0.0))
    )


def phone_path(phone_root: str, relative_or_absolute: str) -> str:
    if relative_or_absolute.startswith("/"):
        return relative_or_absolute
    return f"{phone_root.rstrip('/')}/{relative_or_absolute.strip('/')}"


def wait_for_device(serial: str, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        completed = adb(serial, ["get-state"], check=False)
        if completed.returncode == 0 and completed.stdout.strip() == "device":
            return
        time.sleep(2)
    raise TimeoutError(f"ADB device {serial} did not return within {timeout_seconds}s")


def wait_for_remote_file(serial: str, remote_path: str, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        completed = adb_shell(serial, f"test -f {q(remote_path)}", check=False)
        if completed.returncode == 0:
            return
        time.sleep(5)
    raise TimeoutError(f"remote file did not appear: {remote_path}")


def remote_json(serial: str, remote_path: str) -> dict[str, Any]:
    completed = adb_shell(serial, f"cat {q(remote_path)}")
    return json.loads(completed.stdout)


def write_temp_json(directory: Path, name: str, payload: dict[str, Any]) -> Path:
    path = directory / name
    write_json(path, payload)
    return path


def run_cold_start_probe(
    *,
    serial: str,
    phone_one_shot_runner: str,
    local_dir: Path,
    gate_dir: str,
) -> None:
    started_at = utc_now()
    start = time.monotonic()
    completed = adb_shell(serial, f"{q(phone_one_shot_runner)} --probe", check=False)
    wall_seconds = time.monotonic() - start
    payload = {
        "schema_version": "phase11_h11a_cold_start_probe_v1",
        "started_at_utc": started_at,
        "ended_at_utc": utc_now(),
        "phone_runner": phone_one_shot_runner,
        "host_observed_wall_seconds": wall_seconds,
        "returncode": completed.returncode,
        "stdout_first_4096": completed.stdout[:4096],
        "stderr_first_4096": completed.stderr[:4096],
        "claim_scope": "cold start probe only; not a training iteration",
    }
    local_path = local_dir / "cold_start_probe.json"
    write_json(local_path, payload)
    adb_push(serial, local_path, f"{gate_dir}/cold_start_probe.json")


def run_one_shot_baseline(
    *,
    serial: str,
    phone_one_shot_runner: str,
    token_cache: str,
    asset_dir: str,
    layer0_pack: str,
    layer1_pack: str,
    initial_checkpoint: str,
    learning_rate: float,
    local_dir: Path,
    gate_dir: str,
) -> None:
    output_dir = f"{gate_dir}/one_shot_baseline_output"
    adb_shell(serial, f"rm -rf {q(output_dir)}")
    command = (
        f"{q(phone_one_shot_runner)} --run-g8-distill-compact {q(token_cache)} "
        f"{q(asset_dir)} {q(layer0_pack)} {q(layer1_pack)} {q(initial_checkpoint)} "
        f"{q(output_dir)} {q(str(learning_rate))}"
    )
    started_at = utc_now()
    start = time.monotonic()
    completed = adb_shell(serial, command, check=False)
    wall_seconds = time.monotonic() - start
    telemetry: dict[str, Any] | None = None
    active_seconds = 0.0
    if completed.returncode == 0:
        telemetry = remote_json(serial, f"{output_dir}/telemetry.json")
        active_seconds = active_training_seconds(telemetry)
    payload = {
        "schema_version": "phase11_h11a_one_shot_baseline_v1",
        "started_at_utc": started_at,
        "ended_at_utc": utc_now(),
        "phone_runner": phone_one_shot_runner,
        "phone_output_dir": output_dir,
        "command_shape": (
            "gemma4_layer_runner --run-g8-distill-compact TOKEN_CACHE ASSETS "
            "PACK0 PACK1 CHECKPOINT OUT_DIR LR"
        ),
        "returncode": completed.returncode,
        "wall_seconds": wall_seconds,
        "active_training_seconds": active_seconds,
        "active_wall_ratio": active_seconds / wall_seconds if wall_seconds > 0.0 else 0.0,
        "stdout_first_4096": completed.stdout[:4096],
        "stderr_first_4096": completed.stderr[:4096],
        "telemetry": telemetry,
    }
    local_path = local_dir / "one_shot_baseline.json"
    write_json(local_path, payload)
    adb_push(serial, local_path, f"{gate_dir}/one_shot_baseline.json")


def start_phase11_runner(serial: str, phase11_root: str) -> None:
    command = (
        f"cd {q(phase11_root)}; "
        "nohup ./phase11_runner --queue queue/phase11_queue.jsonl --run-root runs "
        "--heartbeat heartbeat.json --state runner_state.json --stop-file STOP "
        "> runner.log 2>&1 & echo $! > runner.pid"
    )
    adb_shell(serial, command)


def pull_h11a_artifacts(
    *,
    serial: str,
    phase11_root: str,
    run_id: str,
    host_report_dir: Path,
) -> None:
    run_dir = f"{phase11_root}/runs/{run_id}"
    gate_dir = f"{run_dir}/H11-A-daemon"
    for name in GIT_ALLOWED_GATE_FILES:
        adb_pull(serial, f"{gate_dir}/{name}", host_report_dir / name)
    for remote, local in (
        (f"{run_dir}/campaign_manifest.json", host_report_dir / "campaign_manifest.json"),
        (f"{run_dir}/checksum_chain.jsonl", host_report_dir / "checksum_chain.jsonl"),
        (f"{phase11_root}/heartbeat.json", host_report_dir / "heartbeat.json"),
        (f"{phase11_root}/runner_state.json", host_report_dir / "runner_state.json"),
        (f"{phase11_root}/runner.log", host_report_dir / "runner.log"),
        (f"{phase11_root}/runner.pid", host_report_dir / "runner.pid"),
        (f"{phase11_root}/queue/phase11_queue.jsonl", host_report_dir / "phase11_queue.jsonl"),
        (f"{phase11_root}/configs/H11-A.json", host_report_dir / "H11-A.json"),
        (f"{phase11_root}/disconnect_evidence.json", host_report_dir / "disconnect_evidence.json"),
    ):
        adb_pull(serial, remote, local)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", default=DEFAULT_SERIAL)
    parser.add_argument("--phone-root", default=DEFAULT_PHONE_ROOT)
    parser.add_argument("--run-id", default=f"{compact_utc_now()}_h11a_daemon")
    parser.add_argument(
        "--phase11-runner",
        type=Path,
        default=Path(
            "integrations/gemma4-snapdragon-megakernel/build/"
            "gemma4_megakernel_android/phase11_runner"
        ),
    )
    parser.add_argument(
        "--phone-one-shot-runner",
        default=f"{DEFAULT_PHONE_ROOT}/gemma4_layer_runner_phase10_compact",
    )
    parser.add_argument("--iteration-count", type=int, default=50)
    parser.add_argument("--sample-every", type=int, default=25)
    parser.add_argument("--disconnect-seconds", type=int, default=600)
    parser.add_argument("--marker-wait-seconds", type=int, default=1800)
    parser.add_argument("--skip-disconnect-test", action="store_true")
    parser.add_argument("--learning-rate", type=float, default=0.01)
    parser.add_argument("--host-report-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.phase11_runner.exists():
        raise FileNotFoundError(
            f"phase11_runner binary not found: {args.phase11_runner}. "
            "Build the Android target before launching H11-A."
        )

    phase11_root = f"{args.phone_root.rstrip('/')}/phase11"
    run_dir = f"{phase11_root}/runs/{args.run_id}"
    gate_dir = f"{run_dir}/H11-A-daemon"
    host_report_dir = args.host_report_dir or Path(
        f"runtime/reports/gemma4_megakernel/hardware_native_povc/{args.run_id}/H11-A-daemon"
    )
    host_report_dir.mkdir(parents=True, exist_ok=True)

    token_caches = [phone_path(args.phone_root, item) for item in DEFAULT_TOKEN_CACHES]
    asset_dir = phone_path(args.phone_root, DEFAULT_ASSET_DIR)
    layer0_pack = phone_path(args.phone_root, DEFAULT_LAYER0_PACK)
    layer1_pack = phone_path(args.phone_root, DEFAULT_LAYER1_PACK)
    initial_checkpoint = phone_path(args.phone_root, DEFAULT_INITIAL_CHECKPOINT)

    config = {
        "schema_version": "phase11_h11a_config_v1",
        "run_id": args.run_id,
        "iteration_count": args.iteration_count,
        "sample_every": args.sample_every,
        "token_caches": token_caches,
        "asset_dir": asset_dir,
        "layer0_pack": layer0_pack,
        "layer1_pack": layer1_pack,
        "initial_checkpoint": initial_checkpoint,
        "learning_rate": args.learning_rate,
        "disconnect_marker_path": f"{phase11_root}/disconnect_evidence.json",
        "require_disconnect_marker": not args.skip_disconnect_test,
        "disconnect_hold_seconds": args.disconnect_seconds,
        "marker_wait_seconds": args.marker_wait_seconds,
    }
    queue_record = {
        "id": "H11-A-001",
        "gate": "H11-A",
        "config": "configs/H11-A.json",
        "depends_on": [],
        "resume": "auto",
    }

    wait_for_device(args.serial, 30)
    adb_shell(
        args.serial,
        f"mkdir -p {q(phase11_root + '/queue')} {q(phase11_root + '/configs')} "
        f"{q(gate_dir)} && rm -f {q(phase11_root + '/STOP')}",
    )
    adb_push(args.serial, args.phase11_runner, f"{phase11_root}/phase11_runner")
    adb_shell(args.serial, f"chmod 755 {q(phase11_root + '/phase11_runner')}")

    with tempfile.TemporaryDirectory(prefix="phase11_h11a_") as temp_name:
        temp_dir = Path(temp_name)
        config_path = write_temp_json(temp_dir, "H11-A.json", config)
        queue_path = temp_dir / "phase11_queue.jsonl"
        queue_path.write_text(json.dumps(queue_record, sort_keys=True) + "\n", encoding="utf-8")
        adb_push(args.serial, config_path, f"{phase11_root}/configs/H11-A.json")
        adb_push(args.serial, queue_path, f"{phase11_root}/queue/phase11_queue.jsonl")
        (host_report_dir / "H11-A.json").write_text(config_path.read_text(encoding="utf-8"), encoding="utf-8")
        (host_report_dir / "phase11_queue.jsonl").write_text(queue_path.read_text(encoding="utf-8"), encoding="utf-8")

        run_cold_start_probe(
            serial=args.serial,
            phone_one_shot_runner=args.phone_one_shot_runner,
            local_dir=temp_dir,
            gate_dir=gate_dir,
        )
        run_one_shot_baseline(
            serial=args.serial,
            phone_one_shot_runner=args.phone_one_shot_runner,
            token_cache=token_caches[0],
            asset_dir=asset_dir,
            layer0_pack=layer0_pack,
            layer1_pack=layer1_pack,
            initial_checkpoint=initial_checkpoint,
            learning_rate=args.learning_rate,
            local_dir=temp_dir,
            gate_dir=gate_dir,
        )

    start_phase11_runner(args.serial, phase11_root)
    wait_for_remote_file(args.serial, f"{phase11_root}/heartbeat.json", 120)

    disconnect_started_at = utc_now()
    disconnect_payload = {
        "schema_version": "phase11_h11a_disconnect_evidence_v1",
        "host_marker_utc": disconnect_started_at,
        "method": "adb kill-server hold" if not args.skip_disconnect_test else "skipped by operator flag",
        "disconnect_hold_seconds": args.disconnect_seconds,
        "note": (
            "The phone runner must continue from its local queue while the Mac has no "
            "active ADB server. This is ADB-session disconnect evidence, not physical "
            "USB cable removal."
        ),
    }
    with tempfile.TemporaryDirectory(prefix="phase11_disconnect_") as temp_name:
        marker_path = write_temp_json(Path(temp_name), "disconnect_evidence.json", disconnect_payload)
        adb_push(args.serial, marker_path, f"{phase11_root}/disconnect_evidence.json")

    if not args.skip_disconnect_test:
        run_command(["adb", "kill-server"], check=False)
        time.sleep(args.disconnect_seconds)
        run_command(["adb", "start-server"], check=False)
        wait_for_device(args.serial, 120)

    gate_result_remote = f"{gate_dir}/gate_result.json"
    wait_for_remote_file(args.serial, gate_result_remote, args.marker_wait_seconds + 120)
    disconnect_log = (
        "# H11-A Disconnect Log\n\n"
        f"- disconnect marker pushed at: {disconnect_started_at}\n"
        f"- host reconnected at: {utc_now()}\n"
        f"- method: {'adb kill-server hold' if not args.skip_disconnect_test else 'skipped'}\n"
        f"- requested hold seconds: {args.disconnect_seconds}\n"
        "- physical USB cable removal: not performed by this script\n"
    )
    local_disconnect_log = host_report_dir / "disconnect_log.md"
    local_disconnect_log.write_text(disconnect_log, encoding="utf-8")
    adb_push(args.serial, local_disconnect_log, f"{gate_dir}/disconnect_log.md")

    pull_h11a_artifacts(
        serial=args.serial,
        phase11_root=phase11_root,
        run_id=args.run_id,
        host_report_dir=host_report_dir,
    )
    gate_result = json.loads((host_report_dir / "gate_result.json").read_text(encoding="utf-8"))
    print(json.dumps({"status": gate_result.get("status"), "host_report_dir": str(host_report_dir)}, sort_keys=True))
    return 0 if gate_result.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
