#!/usr/bin/env python3
"""Run Phase 11 H11-E trainable residual-adapter scope sweep."""
from __future__ import annotations

import argparse
import array
import datetime as dt
import hashlib
import json
import math
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


DEFAULT_SERIAL = "FY25013101C8"
DEFAULT_PHONE_ROOT = "/data/local/tmp/polymath_gemma4_gate"
DEFAULT_TOKEN_CACHES = (
    "hf_stream/20260517T083219Z_phase10_hf_auth_token_bridge_baseline_cache",
    "sustained_g9_20260517T071405Z/cache_000",
)
DEFAULT_ASSET_DIR = "streamed_assets/g8_layer01_20260517T071405Z"
DEFAULT_LAYER0_PACK = "layer_pack/gemma4_e4b_layer0_seq128_v0"
DEFAULT_LAYER1_PACK = "layer_pack/gemma4_e4b_layer1_seq128_v0"
DEFAULT_BASE_CHECKPOINT = "adapter_training/g5g6_rank4_20260517T040000Z/checkpoint"
DEFAULT_PHASE11_RUNNER = Path(
    "integrations/gemma4-snapdragon-megakernel/build/"
    "gemma4_megakernel_android/phase11_runner"
)
HIDDEN = 2560
BASE_RANK = 4


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


def adb_pull(serial: str, remote_path: str, local_path: Path, *, check: bool = False) -> bool:
    local_path.parent.mkdir(parents=True, exist_ok=True)
    completed = adb(serial, ["pull", remote_path, str(local_path)], check=False)
    if completed.returncode == 0:
        return True
    if check:
        raise RuntimeError(f"adb pull failed for {remote_path}:\n{completed.stderr}")
    return False


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def phone_path(phone_root: str, relative_or_absolute: str) -> str:
    if relative_or_absolute.startswith("/"):
        return relative_or_absolute
    return f"{phone_root.rstrip('/')}/{relative_or_absolute.strip('/')}"


def deploy_runner(*, serial: str, phone_phase11_root: str, runner: Path) -> str:
    if not runner.exists():
        raise FileNotFoundError(f"phase11_runner not found: {runner}")
    adb_shell(serial, f"mkdir -p {q(phone_phase11_root)}")
    remote = f"{phone_phase11_root}/phase11_runner"
    adb(serial, ["push", str(runner), remote])
    adb_shell(serial, f"chmod 755 {q(remote)}")
    return remote


def read_float32(path: Path, expected: int) -> array.array:
    values = array.array("f")
    with path.open("rb") as handle:
        values.fromfile(handle, expected)
    if len(values) != expected:
        raise ValueError(f"{path} expected {expected} float32 values, found {len(values)}")
    if values.itemsize != 4:
        raise RuntimeError("Python float array itemsize is not 4 bytes")
    return values


def deterministic_extra_a(hidden_index: int, rank_index: int) -> float:
    mixed = ((hidden_index + 1) * 1103515245 + (rank_index + 17) * 12345) & 0xFFFF
    centered = (float(mixed) / 65535.0) - 0.5
    return centered * 1.0e-4


def write_float32(path: Path, values: array.array) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        values.tofile(handle)


def expand_checkpoint(base_dir: Path, out_dir: Path, rank: int) -> dict[str, Any]:
    base_a = read_float32(base_dir / "adapter_a.f32.bin", HIDDEN * BASE_RANK)
    base_b = read_float32(base_dir / "adapter_b.f32.bin", BASE_RANK * HIDDEN)
    out_a = array.array("f", [0.0]) * (HIDDEN * rank)
    out_b = array.array("f", [0.0]) * (rank * HIDDEN)
    for hidden in range(HIDDEN):
        for r in range(rank):
            if r < BASE_RANK:
                out_a[(hidden * rank) + r] = base_a[(hidden * BASE_RANK) + r]
            else:
                out_a[(hidden * rank) + r] = deterministic_extra_a(hidden, r)
    for r in range(rank):
        for hidden in range(HIDDEN):
            if r < BASE_RANK:
                out_b[(r * HIDDEN) + hidden] = base_b[(r * HIDDEN) + hidden]
    write_float32(out_dir / "adapter_a.f32.bin", out_a)
    write_float32(out_dir / "adapter_b.f32.bin", out_b)
    manifest = {
        "schema_version": "phase11_h11e_initial_checkpoint_v1",
        "rank": rank,
        "base_rank": BASE_RANK,
        "scope": f"post_layer0_rank{rank}_residual_adapter",
        "initialization": (
            "rank4 rows copied from baseline; additional A columns deterministic small "
            "values; additional B rows zero so first forward delta preserves baseline"
        ),
        "adapter_a_sha256": sha256_file(out_dir / "adapter_a.f32.bin"),
        "adapter_b_sha256": sha256_file(out_dir / "adapter_b.f32.bin"),
        "adapter_a_bytes": (out_dir / "adapter_a.f32.bin").stat().st_size,
        "adapter_b_bytes": (out_dir / "adapter_b.f32.bin").stat().st_size,
    }
    write_json(out_dir / "manifest.json", manifest)
    return manifest


def prepare_checkpoints(
    *, serial: str, phone_root: str, phone_phase11_root: str, ranks: list[int], tmp: Path
) -> dict[int, str]:
    base_remote = phone_path(phone_root, DEFAULT_BASE_CHECKPOINT)
    base_local = tmp / "base_rank4"
    adb_pull(serial, f"{base_remote}/adapter_a.f32.bin", base_local / "adapter_a.f32.bin", check=True)
    adb_pull(serial, f"{base_remote}/adapter_b.f32.bin", base_local / "adapter_b.f32.bin", check=True)
    remote_dirs: dict[int, str] = {}
    for rank in ranks:
        local_dir = tmp / f"rank{rank}_init"
        manifest = expand_checkpoint(base_local, local_dir, rank)
        remote = f"{phone_phase11_root}/h11e_checkpoints/rank{rank}_init"
        adb_shell(serial, f"rm -rf {q(remote)} && mkdir -p {q(remote)}")
        adb(serial, ["push", str(local_dir / "adapter_a.f32.bin"), f"{remote}/adapter_a.f32.bin"])
        adb(serial, ["push", str(local_dir / "adapter_b.f32.bin"), f"{remote}/adapter_b.f32.bin"])
        adb(serial, ["push", str(local_dir / "manifest.json"), f"{remote}/manifest.json"])
        remote_dirs[rank] = remote
        manifest["phone_path"] = remote
        write_json(local_dir / "manifest.json", manifest)
    return remote_dirs


def write_candidate_queue(
    *,
    local_dir: Path,
    phone_phase11_root: str,
    candidate_run_id: str,
    rank: int,
    checkpoint: str,
    iterations: int,
    learning_rate: float,
    phone_root: str,
) -> tuple[Path, Path]:
    queue = local_dir / f"h11e_rank{rank}_queue.jsonl"
    config = local_dir / f"h11e_rank{rank}_config.json"
    token_caches = [phone_path(phone_root, item) for item in DEFAULT_TOKEN_CACHES]
    config_payload = {
        "schema_version": "phase11_h11e_candidate_config_v1",
        "run_id": candidate_run_id,
        "token_caches": token_caches,
        "asset_dir": phone_path(phone_root, DEFAULT_ASSET_DIR),
        "layer0_pack": phone_path(phone_root, DEFAULT_LAYER0_PACK),
        "layer1_pack": phone_path(phone_root, DEFAULT_LAYER1_PACK),
        "initial_checkpoint": checkpoint,
        "iteration_count": iterations,
        "sample_every": 1,
        "learning_rate": learning_rate,
        "adapter_rank": rank,
        "require_disconnect_marker": False,
        "marker_wait_seconds": 0,
        "disconnect_hold_seconds": 0,
    }
    write_json(config, config_payload)
    queue.write_text(
        json.dumps(
            {
                "id": f"h11e_rank{rank}",
                "gate": "H11-A",
                "config": f"{phone_phase11_root}/queue/{config.name}",
                "depends_on": [],
                "resume": "fresh",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return queue, config


def run_candidate(
    *,
    serial: str,
    phone_phase11_root: str,
    remote_runner: str,
    run_id: str,
    rank: int,
    checkpoint: str,
    iterations: int,
    learning_rate: float,
    phone_root: str,
    report_dir: Path,
    tmp: Path,
) -> dict[str, Any]:
    local_candidate = tmp / f"rank{rank}_candidate"
    local_candidate.mkdir(parents=True, exist_ok=True)
    candidate_run_id = f"{run_id}_rank{rank}"
    queue, config = write_candidate_queue(
        local_dir=local_candidate,
        phone_phase11_root=phone_phase11_root,
        candidate_run_id=candidate_run_id,
        rank=rank,
        checkpoint=checkpoint,
        iterations=iterations,
        learning_rate=learning_rate,
        phone_root=phone_root,
    )
    remote_queue_dir = f"{phone_phase11_root}/queue"
    adb_shell(serial, f"mkdir -p {q(remote_queue_dir)}")
    adb(serial, ["push", str(queue), f"{remote_queue_dir}/{queue.name}"])
    adb(serial, ["push", str(config), f"{remote_queue_dir}/{config.name}"])
    state_path = f"{phone_phase11_root}/h11e_rank{rank}_state.json"
    heartbeat_path = f"{phone_phase11_root}/h11e_rank{rank}_heartbeat.json"
    stop_path = f"{phone_phase11_root}/STOP_h11e_rank{rank}"
    adb_shell(serial, f"rm -f {q(state_path)} {q(heartbeat_path)} {q(stop_path)}")
    command = (
        f"cd {q(phone_phase11_root)}; "
        f"{q(remote_runner)} --queue {q(f'queue/{queue.name}')} --run-root runs "
        f"--heartbeat {q(heartbeat_path)} --state {q(state_path)} --stop-file {q(stop_path)}"
    )
    started_at = utc_now()
    completed = adb_shell(serial, command, check=False)

    local_report = report_dir / "candidates" / f"rank{rank}"
    gate_dir = f"{phone_phase11_root}/runs/{candidate_run_id}/H11-A-daemon"
    for name in (
        "gate_result.json",
        "telemetry.jsonl",
        "timing_breakdown.json",
        "blockers.md",
        "falsifier_report.md",
        "artifact_manifest.json",
    ):
        adb_pull(serial, f"{gate_dir}/{name}", local_report / name)
    for index in range(iterations):
        remote_iter = f"{gate_dir}/iterations/iter_{index:06d}"
        local_iter = local_report / "iterations" / f"iter_{index:06d}"
        adb_pull(serial, f"{remote_iter}/telemetry.json", local_iter / "telemetry.json")
        adb_pull(
            serial,
            f"{remote_iter}/checkpoint/manifest.json",
            local_iter / "checkpoint_manifest.json",
        )
    return {
        "schema_version": "phase11_h11e_candidate_run_v1",
        "rank": rank,
        "candidate_run_id": candidate_run_id,
        "started_at_utc": started_at,
        "ended_at_utc": utc_now(),
        "returncode": completed.returncode,
        "stdout_first_4096": completed.stdout[:4096],
        "stderr_first_4096": completed.stderr[:4096],
        "phone_gate_dir": gate_dir,
        "local_report_dir": str(local_report),
    }


def candidate_summary(candidate: dict[str, Any], iterations: int) -> dict[str, Any]:
    local = Path(candidate["local_report_dir"])
    gate = load_json(local / "gate_result.json") if (local / "gate_result.json").exists() else {}
    losses = []
    active_seconds = []
    walls = []
    max_rss = 0
    grad_norms = []
    delta_norms = []
    for index in range(iterations):
        telemetry_path = local / "iterations" / f"iter_{index:06d}" / "telemetry.json"
        if not telemetry_path.exists():
            continue
        telemetry = load_json(telemetry_path)
        losses.append(float(telemetry.get("loss_half_mse", float("nan"))))
        active = (
            float(telemetry.get("token_to_hidden_elapsed_seconds", 0.0))
            + sum(float(value) for value in telemetry.get("layer_elapsed_seconds", []))
            + float(telemetry.get("adapter_elapsed_seconds", 0.0))
        )
        active_seconds.append(active)
        max_rss = max(max_rss, int(telemetry.get("max_rss_kb", 0) or 0))
        grad = telemetry.get("gradient_l2", {})
        delta = telemetry.get("checkpoint_delta_l2", {})
        grad_norms.append(float(grad.get("adapter_a", 0.0)) + float(grad.get("adapter_b", 0.0)))
        delta_norms.append(float(delta.get("adapter_a", 0.0)) + float(delta.get("adapter_b", 0.0)))
    timing = load_json(local / "timing_breakdown.json") if (local / "timing_breakdown.json").exists() else {}
    for item in timing.get("iterations", []):
        walls.append(float(item.get("wall_seconds", 0.0)))
    loss_delta = losses[0] - losses[-1] if len(losses) >= 2 else 0.0
    total_active = sum(active_seconds)
    total_wall = sum(walls)
    return {
        "schema_version": "phase11_h11e_candidate_summary_v1",
        "rank": candidate["rank"],
        "status": "pass" if gate.get("status") == "pass" and candidate["returncode"] == 0 else "fail",
        "gate_status": gate.get("status", "missing"),
        "losses": losses,
        "loss_delta": loss_delta,
        "loss_delta_per_active_second": loss_delta / total_active if total_active > 0 else 0.0,
        "loss_delta_per_wall_second": loss_delta / total_wall if total_wall > 0 else 0.0,
        "active_seconds": total_active,
        "wall_seconds": total_wall,
        "max_rss_kb": max_rss,
        "gradient_l2_sum_first": grad_norms[0] if grad_norms else 0.0,
        "checkpoint_delta_l2_sum_first": delta_norms[0] if delta_norms else 0.0,
        "finite_losses": all(math.isfinite(value) for value in losses),
        "checkpoint_changed": any(value > 0.0 for value in delta_norms),
        "candidate_run": candidate,
    }


def choose_scope(summaries: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, list[str]]:
    blockers = []
    baseline = next((item for item in summaries if item["rank"] == BASE_RANK), None)
    if baseline is None or baseline["status"] != "pass":
        blockers.append("rank-4 baseline candidate did not pass")
        return None, blockers
    viable = []
    for item in summaries:
        if item["status"] != "pass":
            blockers.append(f"rank-{item['rank']} candidate did not pass")
            continue
        if not item["finite_losses"]:
            blockers.append(f"rank-{item['rank']} candidate has non-finite loss")
            continue
        if not item["checkpoint_changed"]:
            blockers.append(f"rank-{item['rank']} checkpoint did not change")
            continue
        if item["loss_delta"] <= 0.0:
            blockers.append(f"rank-{item['rank']} did not reduce loss over two iterations")
            continue
        viable.append(item)
    expanded = [item for item in viable if item["rank"] > BASE_RANK]
    if not expanded:
        blockers.append("no expanded rank candidate was viable")
        return baseline, blockers
    baseline_score = baseline["loss_delta_per_active_second"]
    better = [
        item
        for item in expanded
        if item["loss_delta_per_active_second"] > baseline_score
    ]
    if not better:
        blockers.append("no expanded candidate beat rank-4 loss movement per active second")
        return baseline, blockers
    return max(better, key=lambda item: item["loss_delta_per_active_second"]), blockers


def artifact_manifest(report_dir: Path) -> dict[str, Any]:
    entries = []
    for path in sorted(report_dir.rglob("*")):
        if not path.is_file() or path.name == "artifact_manifest.json":
            continue
        entries.append({"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return {
        "schema_version": "phase11_h11e_artifact_manifest_v1",
        "gate": "H11-E",
        "report_dir": str(report_dir),
        "git_allowed_artifacts": entries,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", default=DEFAULT_SERIAL)
    parser.add_argument("--phone-root", default=DEFAULT_PHONE_ROOT)
    parser.add_argument("--run-id", default=f"{compact_utc_now()}_h11e_scope_sweep")
    parser.add_argument("--phase11-runner", type=Path, default=DEFAULT_PHASE11_RUNNER)
    parser.add_argument("--ranks", default="4,16,32")
    parser.add_argument("--iterations", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=0.01)
    parser.add_argument("--host-report-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ranks = [int(item.strip()) for item in args.ranks.split(",") if item.strip()]
    if BASE_RANK not in ranks or len([rank for rank in ranks if rank > BASE_RANK]) < 2:
        raise ValueError("--ranks must include 4 and at least two expanded ranks")
    report_dir = args.host_report_dir or Path(
        f"runtime/reports/gemma4_megakernel/hardware_native_povc/"
        f"{args.run_id}/H11-E-scope-sweep"
    )
    report_dir.mkdir(parents=True, exist_ok=True)
    phone_phase11_root = f"{args.phone_root.rstrip('/')}/phase11"
    with tempfile.TemporaryDirectory(prefix="h11e_scope_") as tmp_name:
        tmp = Path(tmp_name)
        remote_runner = deploy_runner(
            serial=args.serial,
            phone_phase11_root=phone_phase11_root,
            runner=args.phase11_runner,
        )
        checkpoint_dirs = prepare_checkpoints(
            serial=args.serial,
            phone_root=args.phone_root,
            phone_phase11_root=phone_phase11_root,
            ranks=ranks,
            tmp=tmp,
        )
        scope_configs = []
        candidate_runs = []
        for rank in ranks:
            manifest_src = tmp / f"rank{rank}_init" / "manifest.json"
            scope_configs.append(load_json(manifest_src))
            candidate_runs.append(
                run_candidate(
                    serial=args.serial,
                    phone_phase11_root=phone_phase11_root,
                    remote_runner=remote_runner,
                    run_id=args.run_id,
                    rank=rank,
                    checkpoint=checkpoint_dirs[rank],
                    iterations=args.iterations,
                    learning_rate=args.learning_rate,
                    phone_root=args.phone_root,
                    report_dir=report_dir,
                    tmp=tmp,
                )
            )
    write_json(report_dir / "scope_configs.json", {"schema_version": "phase11_h11e_scope_configs_v1", "scopes": scope_configs})
    write_json(
        report_dir / "projection_lora_feasibility.json",
        {
            "schema_version": "phase11_h11e_projection_lora_feasibility_v1",
            "q_proj_o_proj_gate_proj_up_proj_status": "blocked_for_this_gate",
            "reason": (
                "Current authority backward/update implementation is a post-layer0 residual adapter. "
                "Projection LoRA/DoRA across q_proj, o_proj, gate_proj, and up_proj would require "
                "layer-internal backward kernels and optimizer/checkpoint layout not present in this code path."
            ),
            "non_promotion": "No projection-LoRA capability claim is made by H11-E.",
        },
    )
    write_json(report_dir / "candidate_runs.json", {"schema_version": "phase11_h11e_candidate_runs_v1", "runs": candidate_runs})
    summaries = [candidate_summary(item, args.iterations) for item in candidate_runs]
    selected, blockers = choose_scope(summaries)
    write_json(report_dir / "candidate_summary.json", {"schema_version": "phase11_h11e_candidate_summary_set_v1", "candidates": summaries})
    write_json(
        report_dir / "memory_budget.json",
        {
            "schema_version": "phase11_h11e_memory_budget_v1",
            "candidates": [
                {
                    "rank": item["rank"],
                    "adapter_parameter_count": 2 * HIDDEN * item["rank"],
                    "adapter_checkpoint_bytes": 2 * HIDDEN * item["rank"] * 4,
                    "max_rss_kb": item["max_rss_kb"],
                }
                for item in summaries
            ],
        },
    )
    selected_rank = selected["rank"] if selected is not None else None
    status = "pass" if selected is not None and not blockers and selected_rank != BASE_RANK else "fail"
    gate_result = {
        "schema_version": "phase11_h11e_gate_result_v1",
        "gate": "H11-E",
        "status": status,
        "blockers": blockers,
        "selected_scope": selected,
        "selected_rank": selected_rank,
        "baseline_rank": BASE_RANK,
        "expanded_ranks_tested": [rank for rank in ranks if rank > BASE_RANK],
        "projection_lora_status": "blocked_not_promoted",
        "host_report_dir": str(report_dir),
        "started_at_utc": candidate_runs[0]["started_at_utc"] if candidate_runs else utc_now(),
        "ended_at_utc": utc_now(),
    }
    write_json(report_dir / "gate_result.json", gate_result)
    write_text(
        report_dir / "blockers.md",
        "- None for H11-E.\n" if not blockers and status == "pass" else "".join(f"- {item}\n" for item in blockers),
    )
    write_text(
        report_dir / "falsifier_report.md",
        "# H11-E Falsifier Report\n\n"
        "- phone-local candidate daemon trials used `phase11_runner`; host did not drive individual training iterations.\n"
        "- rank-4 baseline and two expanded residual ranks were run with identical token-cache cadence and learning rate.\n"
        "- projection LoRA/DoRA across q/o/gate/up was not promoted because the current authority backward path does not implement those layer-internal gradients.\n"
        f"- selected rank: {selected_rank}.\n"
        f"- gate status: {status}.\n",
    )
    write_text(
        report_dir / "commands.log",
        "adb push phase11_runner PHONE_PHASE11_ROOT/phase11_runner\n"
        "adb push rankN initial adapter checkpoint PHONE_PHASE11_ROOT/h11e_checkpoints/rankN_init\n"
        "adb shell phase11_runner --queue queue/h11e_rankN_queue.jsonl --run-root runs --heartbeat ... --state ...\n",
    )
    write_json(report_dir / "artifact_manifest.json", artifact_manifest(report_dir))
    print(json.dumps({"status": status, "host_report_dir": str(report_dir), "selected_rank": selected_rank}, sort_keys=True))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
