#!/usr/bin/env python3
"""Run a chained REDMAGIC Gemma4 training endurance gate.

The host script is intentionally narrow: it invokes the existing phone-native
`--run-g8-distill` path repeatedly, chains each adapter checkpoint into the
next iteration, and stores only small audit artifacts in the repository report
directory. Raw tensors are kept under the temporary raw directory and/or on the
phone only for selected sample iterations.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any


DEFAULT_PHONE_ROOT = "/data/local/tmp/polymath_gemma4_gate"
DEFAULT_TOKEN_CACHES = (
    "hf_stream/20260517T083219Z_phase10_hf_auth_token_bridge_baseline_cache",
    "sustained_g9_20260517T071405Z/cache_000",
    "sustained_g9_20260517T071405Z/cache_001",
    "sustained_g9_20260517T071405Z/cache_002",
)
SMALL_OUTPUT_FILES = (
    "telemetry.json",
    "artifact_manifest.json",
    "replay_manifest.json",
    "checkpoint/manifest.json",
)
SAMPLE_OUTPUT_PATHS = (
    "generated/layer_input.f32.bin",
    "generated/per_layer_input_layer0.f32.bin",
    "generated/per_layer_input_layer1.f32.bin",
    "layer0_output.f32.bin",
    "layer1_output.f32.bin",
    "adapter_grad_a.f32.bin",
    "adapter_grad_b.f32.bin",
    "checkpoint/adapter_a.f32.bin",
    "checkpoint/adapter_b.f32.bin",
    "input_checkpoint/adapter_a.f32.bin",
    "input_checkpoint/adapter_b.f32.bin",
)
TOKEN_CACHE_FILES = (
    "input_ids.u32.bin",
    "attention_mask.u8.bin",
    "labels.u32.bin",
    "loss_mask.u8.bin",
    "position_ids.u32.bin",
    "manifest.json",
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_command(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, text=True, capture_output=True)
    if check and completed.returncode != 0:
        joined = " ".join(shlex.quote(part) for part in command)
        raise RuntimeError(
            f"command failed ({completed.returncode}): {joined}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def adb(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run_command(["adb", *args], check=check)


def adb_shell(command: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return adb(["shell", command], check=check)


def q(path: str) -> str:
    return shlex.quote(path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def parse_json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_remote_json(remote_path: str) -> dict[str, Any]:
    completed = adb_shell(f"cat {q(remote_path)}")
    return json.loads(completed.stdout)


def parse_thermal_status(text: str) -> int | None:
    match = re.search(r"Thermal Status:\s*(\d+)", text)
    return int(match.group(1)) if match else None


def parse_headroom(text: str) -> float | None:
    match = re.search(r"(-?\d+(?:\.\d+)?)", text.strip())
    return float(match.group(1)) if match else None


def pull_file(remote_path: str, local_path: Path, *, check: bool = True) -> bool:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    completed = adb(["pull", remote_path, str(local_path)], check=False)
    if completed.returncode == 0:
        return True
    if check:
        raise RuntimeError(
            f"adb pull failed for {remote_path}: {completed.stdout}\n{completed.stderr}"
        )
    return False


def capture_device_sample() -> dict[str, Any]:
    battery = adb_shell("dumpsys battery", check=False).stdout
    thermal = adb_shell("dumpsys thermalservice | sed -n '1,150p'", check=False).stdout
    headroom_0 = adb_shell("cmd thermalservice headroom 0", check=False).stdout
    headroom_60 = adb_shell("cmd thermalservice headroom 60", check=False).stdout
    meminfo = adb_shell("cat /proc/meminfo | sed -n '1,20p'", check=False).stdout
    storage = adb_shell(f"df -h {q(DEFAULT_PHONE_ROOT)} /data/local/tmp 2>/dev/null", check=False).stdout
    return {
        "recorded_at_utc": utc_now(),
        "battery": battery,
        "thermal": thermal,
        "thermal_status": parse_thermal_status(thermal),
        "thermal_headroom_0s": parse_headroom(headroom_0),
        "thermal_headroom_60s": parse_headroom(headroom_60),
        "meminfo_head": meminfo,
        "storage": storage,
    }


def token_cache_paths(phone_root: str, relatives: list[str]) -> list[str]:
    return [f"{phone_root.rstrip('/')}/{relative.strip('/')}" for relative in relatives]


def training_seconds_from_telemetry(telemetry: dict[str, Any]) -> float:
    layer_seconds = telemetry.get("layer_elapsed_seconds") or []
    layer_total = sum(float(value) for value in layer_seconds)
    return (
        float(telemetry.get("token_to_hidden_elapsed_seconds", 0.0))
        + layer_total
        + float(telemetry.get("adapter_elapsed_seconds", 0.0))
    )


def verify_checkpoint_chain(manifests: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    previous_post: dict[str, str] | None = None
    for index, manifest in enumerate(manifests):
        pre = {
            "adapter_a": manifest["pre_update"]["adapter_a"]["sha256"],
            "adapter_b": manifest["pre_update"]["adapter_b"]["sha256"],
        }
        post = {
            "adapter_a": manifest["post_update"]["adapter_a"]["sha256"],
            "adapter_b": manifest["post_update"]["adapter_b"]["sha256"],
        }
        if previous_post is not None and pre != previous_post:
            failures.append(f"checkpoint chain break before iteration {index}")
        if pre == post:
            failures.append(f"checkpoint unchanged in iteration {index}")
        previous_post = post
    return failures


def pull_small_outputs(phone_output_dir: str, local_dir: Path) -> dict[str, str]:
    pulled: dict[str, str] = {}
    for relative in SMALL_OUTPUT_FILES:
        local_path = local_dir / relative
        if pull_file(f"{phone_output_dir}/{relative}", local_path, check=False):
            pulled[relative] = str(local_path)
    return pulled


def write_inline_iteration_artifacts(
    local_dir: Path, telemetry: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, str]:
    telemetry_path = local_dir / "telemetry.json"
    manifest_path = local_dir / "checkpoint/manifest.json"
    write_json(telemetry_path, telemetry)
    write_json(manifest_path, manifest)
    return {
        "telemetry.json": str(telemetry_path),
        "checkpoint/manifest.json": str(manifest_path),
    }


def pull_sample_outputs(phone_output_dir: str, sample_dir: Path) -> dict[str, str]:
    pulled: dict[str, str] = {}
    for relative in SAMPLE_OUTPUT_PATHS:
        local_path = sample_dir / "phone_output" / relative
        if pull_file(f"{phone_output_dir}/{relative}", local_path, check=False):
            pulled[relative] = str(local_path)
    return pulled


def pull_sample_token_cache(token_cache: str, sample_dir: Path) -> dict[str, str]:
    pulled: dict[str, str] = {}
    for relative in TOKEN_CACHE_FILES:
        local_path = sample_dir / "token_cache" / relative
        if pull_file(f"{token_cache}/{relative}", local_path, check=False):
            pulled[relative] = str(local_path)
    return pulled


def prepare_sample_input_checkpoint(checkpoint_dir: str, output_dir: str) -> None:
    command = (
        f"mkdir -p {q(output_dir + '/input_checkpoint')} && "
        f"cp {q(checkpoint_dir + '/adapter_a.f32.bin')} "
        f"{q(output_dir + '/input_checkpoint/adapter_a.f32.bin')} && "
        f"cp {q(checkpoint_dir + '/adapter_b.f32.bin')} "
        f"{q(output_dir + '/input_checkpoint/adapter_b.f32.bin')}"
    )
    adb_shell(command)


def remove_non_sample_raw(output_dir: str) -> None:
    command = (
        f"rm -f {q(output_dir + '/generated/layer_input.f32.bin')} "
        f"{q(output_dir + '/generated/per_layer_input_layer0.f32.bin')} "
        f"{q(output_dir + '/generated/per_layer_input_layer1.f32.bin')} "
        f"{q(output_dir + '/layer0_output.f32.bin')} "
        f"{q(output_dir + '/layer1_output.f32.bin')} "
        f"{q(output_dir + '/adapter_grad_a.f32.bin')} "
        f"{q(output_dir + '/adapter_grad_b.f32.bin')}"
    )
    adb_shell(command, check=False)


def should_sample_iteration(index: int, sample_every: int) -> bool:
    return index == 0 or (sample_every > 0 and index % sample_every == 0)


def run_iteration(
    *,
    index: int,
    args: argparse.Namespace,
    token_cache: str,
    checkpoint_dir: str,
    output_dir: str,
    local_iteration_dir: Path,
    raw_sample_dir: Path,
    sample: bool,
) -> dict[str, Any]:
    if sample:
        prepare_sample_input_checkpoint(checkpoint_dir, output_dir)
    distill_flag = "--run-g8-distill" if sample else "--run-g8-distill-compact"
    command = (
        f"{q(args.runner)} {distill_flag} {q(token_cache)} {q(args.asset_dir)} "
        f"{q(args.layer0_pack)} {q(args.layer1_pack)} {q(checkpoint_dir)} "
        f"{q(output_dir)} {q(str(args.learning_rate))}"
    )
    start = time.monotonic()
    completed = adb_shell(command, check=False)
    wall_seconds = time.monotonic() - start
    if completed.returncode != 0:
        return {
            "iteration": index,
            "status": "fail",
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "wall_seconds": wall_seconds,
            "phone_output_dir": output_dir,
        }

    telemetry = read_remote_json(f"{output_dir}/telemetry.json")
    manifest = read_remote_json(f"{output_dir}/checkpoint/manifest.json")
    pulled = pull_small_outputs(output_dir, local_iteration_dir)
    pulled.update(write_inline_iteration_artifacts(local_iteration_dir, telemetry, manifest))
    training_seconds = training_seconds_from_telemetry(telemetry)
    sample_files: dict[str, str] = {}
    sample_cache: dict[str, str] = {}
    if sample:
        sample_files = pull_sample_outputs(output_dir, raw_sample_dir)
        sample_cache = pull_sample_token_cache(token_cache, raw_sample_dir)
    else:
        remove_non_sample_raw(output_dir)

    return {
        "iteration": index,
        "status": "pass",
        "token_cache": token_cache,
        "input_checkpoint": checkpoint_dir,
        "output_checkpoint": f"{output_dir}/checkpoint",
        "phone_output_dir": output_dir,
        "local_iteration_dir": str(local_iteration_dir),
        "raw_sample_dir": str(raw_sample_dir) if sample else None,
        "sample": sample,
        "pulled_small_outputs": pulled,
        "sample_files": sample_files,
        "sample_token_cache": sample_cache,
        "wall_seconds": wall_seconds,
        "training_seconds": training_seconds,
        "raw_outputs_written": sample,
        "telemetry": telemetry,
        "checkpoint_manifest": manifest,
    }


def build_gate_result(
    *,
    args: argparse.Namespace,
    run_id: str,
    started_at: str,
    ended_at: str,
    wall_seconds: float,
    training_seconds: float,
    records: list[dict[str, Any]],
    device_samples: list[dict[str, Any]],
    chain_failures: list[str],
    failed_record: dict[str, Any] | None,
) -> dict[str, Any]:
    thermal_statuses = [
        sample["thermal_status"]
        for sample in device_samples
        if isinstance(sample.get("thermal_status"), int)
    ]
    max_thermal_status = max(thermal_statuses) if thermal_statuses else None
    status = "pass"
    blockers: list[str] = []
    if failed_record is not None:
        status = "fail"
        blockers.append(f"iteration {failed_record['iteration']} returned nonzero")
    if wall_seconds < args.min_wall_seconds:
        status = "fail"
        blockers.append("wall-clock endurance seconds below gate")
    if training_seconds < args.min_training_seconds:
        status = "fail"
        blockers.append("active phone training seconds below configured floor")
    if args.min_wall_seconds < 21600.0 and not args.allow_short_smoke:
        status = "fail"
        blockers.append("configured duration is below the six-hour wall-clock gate")
    if chain_failures:
        status = "fail"
        blockers.extend(chain_failures)
    if max_thermal_status is not None and max_thermal_status >= args.max_allowed_thermal_status:
        status = "fail"
        blockers.append("thermal status reached disallowed level")

    return {
        "schema_version": "gemma4_phase10_six_hour_endurance_gate_v1",
        "run_id": run_id,
        "gate": "Phase 10 phone-native chained training endurance",
        "status": status,
        "blockers": blockers,
        "started_at_utc": started_at,
        "ended_at_utc": ended_at,
        "wall_seconds": wall_seconds,
        "min_required_wall_seconds": args.min_wall_seconds,
        "active_training_seconds": training_seconds,
        "min_required_active_training_seconds": args.min_training_seconds,
        "iteration_count": len(records),
        "sample_iterations": [record["iteration"] for record in records if record["sample"]],
        "token_caches": args.token_cache,
        "runner": args.runner,
        "asset_dir": args.asset_dir,
        "layer0_pack": args.layer0_pack,
        "layer1_pack": args.layer1_pack,
        "initial_checkpoint": args.initial_checkpoint,
        "learning_rate": args.learning_rate,
        "max_thermal_status": max_thermal_status,
        "max_allowed_thermal_status": args.max_allowed_thermal_status,
        "authority_verdict": (
            "six_hour_endurance_passed_for_current_rank4_two_layer_phone_training"
            if status == "pass" and args.min_wall_seconds >= 21600.0
            else "six_hour_endurance_not_promoted"
        ),
        "non_claims_remaining": [
            "not full Gemma4 training",
            "not Hexagon NPU training",
            "not public benchmark readiness",
            "not theoretical maximum reached",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--phone-root", default=DEFAULT_PHONE_ROOT)
    parser.add_argument(
        "--runner",
        default=f"{DEFAULT_PHONE_ROOT}/gemma4_layer_runner_phase10_compact",
    )
    parser.add_argument(
        "--token-cache",
        action="append",
        default=[],
        help="Phone token cache path. May be repeated. Defaults to Phase 10 + G9 caches.",
    )
    parser.add_argument(
        "--asset-dir",
        default=f"{DEFAULT_PHONE_ROOT}/streamed_assets/g8_layer01_20260517T071405Z",
    )
    parser.add_argument(
        "--layer0-pack",
        default=f"{DEFAULT_PHONE_ROOT}/layer_pack/gemma4_e4b_layer0_seq128_v0",
    )
    parser.add_argument(
        "--layer1-pack",
        default=f"{DEFAULT_PHONE_ROOT}/layer_pack/gemma4_e4b_layer1_seq128_v0",
    )
    parser.add_argument(
        "--initial-checkpoint",
        default=f"{DEFAULT_PHONE_ROOT}/adapter_training/g5g6_rank4_20260517T040000Z/checkpoint",
    )
    parser.add_argument("--learning-rate", type=float, default=0.01)
    parser.add_argument("--min-wall-seconds", type=float, default=21600.0)
    parser.add_argument("--min-training-seconds", type=float, default=0.0)
    parser.add_argument("--allow-short-smoke", action="store_true")
    parser.add_argument("--sample-every", type=int, default=300)
    parser.add_argument("--device-sample-every", type=int, default=20)
    parser.add_argument("--max-iterations", type=int, default=0)
    parser.add_argument("--max-allowed-thermal-status", type=int, default=4)
    parser.add_argument(
        "--host-report-dir",
        type=Path,
        default=None,
        help="Repository report directory for JSON/markdown audit artifacts.",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=None,
        help="Temporary directory for raw sampled tensors.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.token_cache:
        args.token_cache = token_cache_paths(args.phone_root, list(DEFAULT_TOKEN_CACHES))
    host_report_dir = args.host_report_dir or Path(
        f"runtime/reports/gemma4_megakernel/hardware_max/{args.run_id}"
    )
    raw_dir = args.raw_dir or Path(f"/tmp/polymath_{args.run_id}")
    phone_run_dir = f"{args.phone_root.rstrip('/')}/hardware_max/{args.run_id}"
    host_report_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    adb_shell(f"rm -rf {q(phone_run_dir)} && mkdir -p {q(phone_run_dir + '/iterations')}")

    started_at = utc_now()
    start = time.monotonic()
    records: list[dict[str, Any]] = []
    manifests: list[dict[str, Any]] = []
    device_samples: list[dict[str, Any]] = [capture_device_sample()]
    failed_record: dict[str, Any] | None = None
    checkpoint_dir = args.initial_checkpoint
    training_seconds = 0.0
    index = 0

    while (
        (time.monotonic() - start) < args.min_wall_seconds
        or training_seconds < args.min_training_seconds
    ):
        if args.max_iterations and index >= args.max_iterations:
            break
        token_cache = args.token_cache[index % len(args.token_cache)]
        output_dir = f"{phone_run_dir}/iterations/iter_{index:06d}"
        sample = should_sample_iteration(index, args.sample_every)
        record = run_iteration(
            index=index,
            args=args,
            token_cache=token_cache,
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            local_iteration_dir=host_report_dir / "iterations" / f"iter_{index:06d}",
            raw_sample_dir=raw_dir / "samples" / f"iter_{index:06d}",
            sample=sample,
        )
        append_jsonl(host_report_dir / "iteration_metrics.jsonl", record)
        if record["status"] != "pass":
            failed_record = record
            break
        records.append(record)
        manifests.append(record["checkpoint_manifest"])
        training_seconds += float(record["training_seconds"])
        checkpoint_dir = record["output_checkpoint"]
        if index % args.device_sample_every == 0:
            sample_record = capture_device_sample()
            device_samples.append(sample_record)
            append_jsonl(host_report_dir / "device_samples.jsonl", sample_record)
        index += 1

    if failed_record is None and records and not records[-1]["sample"]:
        index = records[-1]["iteration"] + 1
        token_cache = args.token_cache[index % len(args.token_cache)]
        output_dir = f"{phone_run_dir}/iterations/iter_{index:06d}"
        final_record = run_iteration(
            index=index,
            args=args,
            token_cache=token_cache,
            checkpoint_dir=checkpoint_dir,
            output_dir=output_dir,
            local_iteration_dir=host_report_dir / "iterations" / f"iter_{index:06d}",
            raw_sample_dir=raw_dir / "samples" / f"iter_{index:06d}",
            sample=True,
        )
        append_jsonl(host_report_dir / "iteration_metrics.jsonl", final_record)
        if final_record["status"] != "pass":
            failed_record = final_record
        else:
            records.append(final_record)
            manifests.append(final_record["checkpoint_manifest"])
            training_seconds += float(final_record["training_seconds"])

    device_samples.append(capture_device_sample())
    chain_failures = verify_checkpoint_chain(manifests)
    ended_at = utc_now()
    wall_seconds = time.monotonic() - start
    summary = {
        "schema_version": "gemma4_phase10_endurance_summary_v1",
        "run_id": args.run_id,
        "started_at_utc": started_at,
        "ended_at_utc": ended_at,
        "wall_seconds": wall_seconds,
        "active_training_seconds": training_seconds,
        "iteration_count": len(records),
        "phone_run_dir": phone_run_dir,
        "host_report_dir": str(host_report_dir),
        "raw_dir": str(raw_dir),
        "checkpoint_chain_failures": chain_failures,
        "failed_record": failed_record,
    }
    gate_result = build_gate_result(
        args=args,
        run_id=args.run_id,
        started_at=started_at,
        ended_at=ended_at,
        wall_seconds=wall_seconds,
        training_seconds=training_seconds,
        records=records,
        device_samples=device_samples,
        chain_failures=chain_failures,
        failed_record=failed_record,
    )
    write_json(host_report_dir / "endurance_summary.json", summary)
    write_json(host_report_dir / "gate_result.json", gate_result)
    blockers = "\n".join(f"- {item}" for item in gate_result["blockers"])
    (host_report_dir / "blockers.md").write_text(
        (blockers or "- None for the six-hour endurance gate.\n"), encoding="utf-8"
    )
    (host_report_dir / "commands.log").write_text(
        "Sanitized command pattern:\n"
        "adb shell gemma4_layer_runner_phase10_compact --run-g8-distill "
        "TOKEN_CACHE ASSETS PACK0 PACK1 CHECKPOINT OUT_DIR LR\n"
        "Non-sample iterations use --run-g8-distill-compact and write only "
        "checkpoint, telemetry, artifact manifest, and replay manifest.\n"
        "No Hugging Face token or selected text is stored in this report.\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": gate_result["status"], "gate_result": str(host_report_dir / "gate_result.json")}, sort_keys=True))
    return 0 if gate_result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
