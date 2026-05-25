#!/usr/bin/env python3
"""Run Phase 13 P13-B Gemma identity/kernel-lineage smoke gate."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
PHASE13_ROOT = REPO_ROOT / "runtime/reports/gemma4_megakernel/phase13_gemma4_only_heterogeneous"
ACTIVE_RUN = PHASE13_ROOT / "active_phase13_run.json"
PHASE12_CDE = REPO_ROOT / (
    "runtime/reports/gemma4_megakernel/phase12_hardware_native_learning/"
    "20260524T164412Z_phase12_cde_authority/CDE-expanded-learning/phase12_cde_gate_result.json"
)
PHASE12_SHARDS = REPO_ROOT / (
    "runtime/reports/gemma4_megakernel/phase12_hardware_native_learning/"
    "20260524T164412Z_phase12_cde_authority/CDE-expanded-learning/"
    "D-phone-native-corpus/runner_shards_manifest.json"
)

DEFAULT_SERIAL = "FY25013101C8"
DEFAULT_PHONE_ROOT = "/data/local/tmp/polymath_gemma4_gate"
DEFAULT_RUNNER = Path("/tmp/gemma4_phase13_android/phase11_runner")
DEFAULT_LAYER_RUNNER = Path("/tmp/gemma4_phase13_android/gemma4_layer_runner")
MODEL_ID = "google/gemma-4-E4B"
MODEL_REVISION = "7aa32e6889efd6300124851b164f8b364314c3d8"
HIDDEN_SIZE = 2560
KERNEL_LINEAGE = "residual_adapter_opencl_training"
RUNTIME_BACKEND = "phone_cpu_token_to_hidden_plus_opencl_layers_and_adapter"
TEACHER_PROVENANCE = "runpod_precomputed_full_gemma4_topk_before_phone_runtime"
ASSET_DIR = "streamed_assets/g8_layer01_20260517T071405Z"
LAYER0_PACK = "layer_pack/gemma4_e4b_layer0_seq128_v0"
LAYER1_PACK = "layer_pack/gemma4_e4b_layer1_seq128_v0"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def q(text: str) -> str:
    return "'" + text.replace("'", "'\"'\"'") + "'"


def run_command(command: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True)
    if check and completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def adb(serial: str, args: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return run_command(["adb", "-s", serial, *args], check=check)


def adb_shell(serial: str, command: str, *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return adb(serial, ["shell", command], check=check)


def adb_push(serial: str, local: Path, remote: str) -> None:
    adb(serial, ["push", str(local), remote], check=True)


def adb_pull(serial: str, remote: str, local: Path, *, check: bool = False) -> bool:
    local.parent.mkdir(parents=True, exist_ok=True)
    completed = adb(serial, ["pull", remote, str(local)], check=False)
    if check and completed.returncode != 0:
        raise RuntimeError(f"adb pull failed: {remote}\n{completed.stderr}")
    return completed.returncode == 0


def phone_path(root: str, child: str) -> str:
    return root.rstrip("/") + "/" + child.lstrip("/")


def command_log_entry(command: str, result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout_first_4096": result.stdout[:4096],
        "stderr_first_4096": result.stderr[:4096],
    }


def require_phone_path(serial: str, path: str) -> bool:
    return adb_shell(serial, f"test -e {q(path)}").returncode == 0


def active_run_root() -> Path:
    active = load_json(ACTIVE_RUN)
    return REPO_ROOT / active["run_root"]


def source_commit() -> str:
    completed = run_command(["git", "rev-parse", "HEAD"], check=True)
    return completed.stdout.strip()


def source_dirty() -> bool:
    completed = run_command(["git", "status", "--porcelain=v1"], check=True)
    return bool(completed.stdout.strip())


def deploy_binaries(serial: str, phone_gate_root: str, runner: Path, layer_runner: Path) -> dict[str, Any]:
    if not runner.exists():
        raise FileNotFoundError(f"missing phase11_runner binary: {runner}")
    if not layer_runner.exists():
        raise FileNotFoundError(f"missing gemma4_layer_runner binary: {layer_runner}")
    remote_bin = f"{phone_gate_root}/bin"
    adb_shell(serial, f"rm -rf {q(remote_bin)} && mkdir -p {q(remote_bin)}", check=True)
    adb_push(serial, runner, f"{remote_bin}/phase11_runner")
    adb_push(serial, layer_runner, f"{remote_bin}/gemma4_layer_runner")
    adb_shell(serial, f"chmod 755 {q(remote_bin + '/phase11_runner')} {q(remote_bin + '/gemma4_layer_runner')}", check=True)
    phone_sha = adb_shell(
        serial,
        f"sha256sum {q(remote_bin + '/phase11_runner')} {q(remote_bin + '/gemma4_layer_runner')}",
        check=False,
    )
    return {
        "phone_bin": remote_bin,
        "local_phase11_runner": str(runner),
        "local_phase11_runner_sha256": sha256_file(runner),
        "local_gemma4_layer_runner": str(layer_runner),
        "local_gemma4_layer_runner_sha256": sha256_file(layer_runner),
        "phone_sha256sum_stdout": phone_sha.stdout,
        "phone_sha256sum_returncode": phone_sha.returncode,
    }


def make_config(
    *,
    run_id: str,
    phone_root: str,
    phone_gate_root: str,
    token_cache: str,
    teacher_shard: str,
    checkpoint: str,
    bad_identity: bool,
) -> dict[str, Any]:
    return {
        "schema_version": "phase13_p13b_identity_smoke_config_v1",
        "run_id": run_id,
        "gate_name": "P13-B",
        "gate_dir_name": "P13-B-identity-smoke",
        "objective": "topk_embedding_kl",
        "token_caches": [token_cache],
        "teacher_shards": [teacher_shard],
        "asset_dir": phone_path(phone_root, ASSET_DIR),
        "layer0_pack": phone_path(phone_root, LAYER0_PACK),
        "layer1_pack": phone_path(phone_root, LAYER1_PACK),
        "initial_checkpoint": checkpoint,
        "iteration_count": 1,
        "sample_every": 99,
        "learning_rate": 0.0,
        "optimizer": "adamw",
        "weight_decay": 0.01,
        "grad_clip_l2": 1.0,
        "adapter_rank": 16,
        "apply_update": False,
        "require_disconnect_marker": False,
        "marker_wait_seconds": 0,
        "disconnect_hold_seconds": 0,
        "model_id": "Qwen/Qwen2.5-1.5B" if bad_identity else MODEL_ID,
        "model_revision": MODEL_REVISION,
        "hidden_size": 1536 if bad_identity else HIDDEN_SIZE,
        "source_commit": source_commit(),
        "source_tree_dirty": source_dirty(),
        "kernel_lineage_class": KERNEL_LINEAGE,
        "runtime_backend": RUNTIME_BACKEND,
        "teacher_provenance": (
            "qwen random-init hidden-size-1536 negative probe"
            if bad_identity
            else TEACHER_PROVENANCE
        ),
        "hidden_state_fixtures_consumed": False,
        "phone_gate_root": phone_gate_root,
    }


def queue_record(record_id: str, config_name: str) -> str:
    return json.dumps(
        {
            "id": record_id,
            "gate": "H11-F",
            "config": f"queue/{config_name}",
            "depends_on": [],
            "resume": "fresh",
        },
        sort_keys=True,
    ) + "\n"


def write_and_push_queue(
    *,
    serial: str,
    tmp: Path,
    phone_gate_root: str,
    config: dict[str, Any],
    config_name: str,
    queue_name: str,
    record_id: str,
) -> None:
    local_config = tmp / config_name
    local_queue = tmp / queue_name
    write_json(local_config, config)
    local_queue.write_text(queue_record(record_id, config_name), encoding="utf-8")
    adb_shell(serial, f"mkdir -p {q(phone_gate_root + '/queue')}", check=True)
    adb_push(serial, local_config, f"{phone_gate_root}/queue/{config_name}")
    adb_push(serial, local_queue, f"{phone_gate_root}/queue/{queue_name}")


def run_phone_queue(
    *,
    serial: str,
    phone_gate_root: str,
    queue_name: str,
    state_name: str,
    heartbeat_name: str,
) -> subprocess.CompletedProcess[str]:
    command = (
        f"cd {q(phone_gate_root)} && "
        f"./bin/phase11_runner --queue {q('queue/' + queue_name)} "
        f"--run-root runs --heartbeat {q(heartbeat_name)} "
        f"--state {q(state_name)} --stop-file STOP"
    )
    return adb_shell(serial, command, check=False)


def pull_good_artifacts(serial: str, phone_gate_root: str, good_run_id: str, report_dir: Path) -> None:
    phone_gate_dir = f"{phone_gate_root}/runs/{good_run_id}/P13-B-identity-smoke"
    pulls = {
        "gate_result.json": f"{phone_gate_dir}/gate_result.json",
        "telemetry.jsonl": f"{phone_gate_dir}/telemetry.jsonl",
        "timing_breakdown.json": f"{phone_gate_dir}/timing_breakdown.json",
        "blockers.md": f"{phone_gate_dir}/blockers.md",
        "falsifier_report.md": f"{phone_gate_dir}/falsifier_report.md",
        "artifact_manifest.json": f"{phone_gate_dir}/artifact_manifest.json",
        "queue_schema.json": f"{phone_gate_dir}/queue_schema.json",
        "daemon_static_artifact_manifest.json": f"{phone_gate_dir}/daemon_static_artifact_manifest.json",
        "iterations/iter_000000/telemetry.json": f"{phone_gate_dir}/iterations/iter_000000/telemetry.json",
        "iterations/iter_000000/replay_manifest.json": f"{phone_gate_dir}/iterations/iter_000000/replay_manifest.json",
        "iterations/iter_000000/artifact_manifest.json": f"{phone_gate_dir}/iterations/iter_000000/artifact_manifest.json",
        "iterations/iter_000000/checkpoint_manifest.json": f"{phone_gate_dir}/iterations/iter_000000/checkpoint/manifest.json",
        "runner_state.json": f"{phone_gate_root}/state_good.json",
        "heartbeat.json": f"{phone_gate_root}/heartbeat_good.json",
    }
    for local_name, remote in pulls.items():
        adb_pull(serial, remote, report_dir / "phone_good" / local_name, check=False)


def validate_good(report_dir: Path, deploy: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    blockers: list[str] = []
    gate = load_json(report_dir / "phone_good/gate_result.json")
    telemetry = load_json(report_dir / "phone_good/iterations/iter_000000/telemetry.json")
    required_gate = {
        "status": "pass",
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "hidden_size": HIDDEN_SIZE,
        "kernel_lineage_class": KERNEL_LINEAGE,
        "runtime_backend": RUNTIME_BACKEND,
        "teacher_provenance": TEACHER_PROVENANCE,
        "hidden_state_fixtures_consumed": False,
        "trainable_scope": "post_layer0_rank16_residual_adapter",
    }
    for key, expected in required_gate.items():
        if gate.get(key) != expected:
            blockers.append(f"gate_result {key} mismatch: {gate.get(key)!r} != {expected!r}")
    if not gate.get("runner_binary_sha256"):
        blockers.append("gate_result missing runner_binary_sha256")
    if gate.get("runner_binary_sha256") != deploy["local_phase11_runner_sha256"]:
        blockers.append("phone runner self-hash does not match deployed local runner hash")
    if gate.get("source_commit") != source_commit():
        blockers.append("gate_result source_commit mismatch")

    required_telemetry = {
        "model_id": MODEL_ID,
        "revision": MODEL_REVISION,
        "hidden_size": HIDDEN_SIZE,
        "kernel_lineage_class": KERNEL_LINEAGE,
        "runtime_backend": RUNTIME_BACKEND,
        "teacher_provenance": TEACHER_PROVENANCE,
        "fixture_usage": "none",
        "megakernel_claim": False,
        "trainable_scope": "post_layer0_rank16_residual_adapter",
    }
    for key, expected in required_telemetry.items():
        if telemetry.get(key) != expected:
            blockers.append(f"telemetry {key} mismatch: {telemetry.get(key)!r} != {expected!r}")
    if telemetry.get("hidden_state_fixtures_consumed") != []:
        blockers.append("telemetry hidden_state_fixtures_consumed must be []")
    return blockers, {"gate_result": gate, "iteration_telemetry": telemetry}


def write_artifact_manifest(report_dir: Path) -> None:
    entries: list[dict[str, Any]] = []
    for path in sorted(report_dir.rglob("*")):
        if path.is_file() and path.name != "artifact_manifest.json":
            entries.append({"path": rel(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    write_json(
        report_dir / "artifact_manifest.json",
        {
            "schema_version": "phase13_p13b_artifact_manifest_v1",
            "created_at_utc": utc_now(),
            "artifacts": entries,
        },
    )


def update_phase13_status(run_root: Path, status: str, gate_result_path: Path) -> None:
    status_path = run_root / "phase13_gate_status.json"
    phase_status = load_json(status_path)
    phase_status["gate_status"]["P13-B"] = status
    phase_status["current_gate"] = "P13-C" if status == "pass" else "P13-B"
    phase_status["latest_gate_result"] = rel(gate_result_path)
    phase_status["updated_at_utc"] = utc_now()
    write_json(status_path, phase_status)
    active = load_json(ACTIVE_RUN)
    active["current_gate"] = phase_status["current_gate"]
    active["updated_at_utc"] = utc_now()
    write_json(ACTIVE_RUN, active)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serial", default=DEFAULT_SERIAL)
    parser.add_argument("--phone-root", default=DEFAULT_PHONE_ROOT)
    parser.add_argument("--runner", type=Path, default=DEFAULT_RUNNER)
    parser.add_argument("--layer-runner", type=Path, default=DEFAULT_LAYER_RUNNER)
    args = parser.parse_args()

    run_root = active_run_root()
    report_dir = run_root / "P13-B-identity-kernel-lineage"
    report_dir.mkdir(parents=True, exist_ok=True)
    run_id = load_json(ACTIVE_RUN)["run_id"]
    phone_gate_root = f"{args.phone_root}/phase13/{run_id}/p13b"
    commands: list[dict[str, Any]] = []

    cde = load_json(PHASE12_CDE)
    shards = load_json(PHASE12_SHARDS)
    shard0 = shards["shards"][0]
    checkpoint = cde["gate_c"]["rank_results"][0]["train"]["run"]["final_checkpoint"]
    required_paths = [
        phone_path(args.phone_root, ASSET_DIR),
        phone_path(args.phone_root, LAYER0_PACK),
        phone_path(args.phone_root, LAYER1_PACK),
        shard0["phone_cache"],
        shard0["phone_teacher"],
        checkpoint,
    ]

    blockers = [f"missing phone path: {path}" for path in required_paths if not require_phone_path(args.serial, path)]
    deploy: dict[str, Any] = {}
    good_result: subprocess.CompletedProcess[str] | None = None
    bad_result: subprocess.CompletedProcess[str] | None = None
    validation_payload: dict[str, Any] = {}

    if not blockers:
        deploy = deploy_binaries(args.serial, phone_gate_root, args.runner, args.layer_runner)
        write_json(report_dir / "binary_deploy_manifest.json", deploy)
        with tempfile.TemporaryDirectory(prefix="phase13_p13b_") as tmp_name:
            tmp = Path(tmp_name)
            good_run_id = f"{run_id}_p13b_good"
            bad_run_id = f"{run_id}_p13b_bad"
            good_config = make_config(
                run_id=good_run_id,
                phone_root=args.phone_root,
                phone_gate_root=phone_gate_root,
                token_cache=shard0["phone_cache"],
                teacher_shard=shard0["phone_teacher"],
                checkpoint=checkpoint,
                bad_identity=False,
            )
            bad_config = make_config(
                run_id=bad_run_id,
                phone_root=args.phone_root,
                phone_gate_root=phone_gate_root,
                token_cache=shard0["phone_cache"],
                teacher_shard=shard0["phone_teacher"],
                checkpoint=checkpoint,
                bad_identity=True,
            )
            write_json(report_dir / "good_config.json", good_config)
            write_json(report_dir / "bad_config.json", bad_config)
            write_and_push_queue(
                serial=args.serial,
                tmp=tmp,
                phone_gate_root=phone_gate_root,
                config=good_config,
                config_name="p13b_good_config.json",
                queue_name="p13b_good_queue.jsonl",
                record_id="p13b_good_identity_smoke",
            )
            write_and_push_queue(
                serial=args.serial,
                tmp=tmp,
                phone_gate_root=phone_gate_root,
                config=bad_config,
                config_name="p13b_bad_config.json",
                queue_name="p13b_bad_queue.jsonl",
                record_id="p13b_bad_identity_rejection",
            )
        good_result = run_phone_queue(
            serial=args.serial,
            phone_gate_root=phone_gate_root,
            queue_name="p13b_good_queue.jsonl",
            state_name="state_good.json",
            heartbeat_name="heartbeat_good.json",
        )
        commands.append(command_log_entry("adb shell phase11_runner good identity smoke", good_result))
        pull_good_artifacts(args.serial, phone_gate_root, f"{run_id}_p13b_good", report_dir)
        if good_result.returncode != 0:
            blockers.append("valid Gemma identity smoke run failed")
        else:
            validation_blockers, validation_payload = validate_good(report_dir, deploy)
            blockers.extend(validation_blockers)

        bad_result = run_phone_queue(
            serial=args.serial,
            phone_gate_root=phone_gate_root,
            queue_name="p13b_bad_queue.jsonl",
            state_name="state_bad.json",
            heartbeat_name="heartbeat_bad.json",
        )
        commands.append(command_log_entry("adb shell phase11_runner bad identity rejection", bad_result))
        rejection_text = bad_result.stdout + "\n" + bad_result.stderr
        rejection_ok = bad_result.returncode != 0 and "Gemma identity mismatch" in rejection_text
        if not rejection_ok:
            blockers.append("deliberate non-Gemma hidden-size mismatch was not rejected")

    if bad_result is not None:
        write_json(
            report_dir / "bad_rejection_result.json",
            {
                "returncode": bad_result.returncode,
                "stdout_first_4096": bad_result.stdout[:4096],
                "stderr_first_4096": bad_result.stderr[:4096],
                "expected_rejection": "Gemma identity mismatch",
            },
        )
    if validation_payload:
        write_json(report_dir / "identity_validation_record.json", validation_payload)

    status = "pass" if not blockers else "fail"
    gate = {
        "schema_version": "phase13_p13b_gate_result_v1",
        "gate": "P13-B-identity-kernel-lineage",
        "run_id": run_id,
        "status": status,
        "started_at_utc": utc_now(),
        "ended_at_utc": utc_now(),
        "blockers": blockers,
        "phone_gate_root": phone_gate_root,
        "valid_smoke_returncode": None if good_result is None else good_result.returncode,
        "bad_rejection_returncode": None if bad_result is None else bad_result.returncode,
        "identity_fields_required": [
            "model_id",
            "model_revision",
            "hidden_size",
            "runner_binary_sha256",
            "source_commit",
            "kernel_lineage_class",
            "runtime_backend",
            "trainable_scope",
            "teacher_provenance",
            "hidden_state_fixtures_consumed",
        ],
        "kernel_lineage_class": KERNEL_LINEAGE,
        "promoted_claims": [
            "Phase 13 runner rejects non-Gemma/hidden-size-mismatched config before phone training.",
            "Valid phone smoke emits Gemma identity and residual_adapter_opencl_training lineage telemetry.",
        ]
        if status == "pass"
        else [],
        "nonclaims": [
            "P13-B smoke does not promote corpus-scale learning.",
            "P13-B smoke does not promote heterogeneous HTP training.",
            "P13-B smoke does not promote a long-run learning result.",
        ],
    }
    write_json(report_dir / "gate_result.json", gate)
    write_text(report_dir / "blockers.md", "- None.\n" if not blockers else "".join(f"- {item}\n" for item in blockers))
    write_text(
        report_dir / "falsifier_report.md",
        "# P13-B Falsifier Report\n\n"
        f"- Gate status: {status}.\n"
        "- Valid smoke config used `google/gemma-4-E4B`, hidden size 2560, and residual adapter OpenCL lineage.\n"
        "- Deliberate bad config used Qwen model id and hidden size 1536 and had to fail before training.\n"
        "- The smoke uses Phase 12 smoke-scale cache only for identity instrumentation, not learning promotion.\n",
    )
    write_text(report_dir / "commands.log", "\n".join(json.dumps(item, sort_keys=True) for item in commands) + "\n")
    write_artifact_manifest(report_dir)
    update_phase13_status(run_root, status, report_dir / "gate_result.json")
    print(json.dumps({"status": status, "gate_result": rel(report_dir / "gate_result.json")}, indent=2))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
