#!/usr/bin/env python3
"""Run Phase 13 P13-D expanded residual-adapter gradient parity gate."""
from __future__ import annotations

import argparse
import array
import datetime as dt
import hashlib
import json
import math
import random
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
PHASE13_ROOT = REPO_ROOT / "runtime/reports/gemma4_megakernel/phase13_gemma4_only_heterogeneous"
ACTIVE_RUN = PHASE13_ROOT / "active_phase13_run.json"

DEFAULT_SERIAL = "FY25013101C8"
DEFAULT_PHONE_ROOT = "/data/local/tmp/polymath_gemma4_gate"
DEFAULT_LAYER_RUNNER = Path("/tmp/gemma4_phase13_android/gemma4_layer_runner")

MODEL_ID = "google/gemma-4-E4B"
MODEL_REVISION = "7aa32e6889efd6300124851b164f8b364314c3d8"
HIDDEN = 2560
BASE_LR = 0.1
EPSILON = 0.01
SEED = 13004
COORDS_PER_SOURCE = 16
COORDS_PER_TENSOR_PER_SOURCE = 8
REL_TOL = 0.25
ABS_TOL = 5.0e-5
SIGN_THRESHOLD = 1.0e-5
MIN_PASS_COUNT = 64

ASSET_DIR = "streamed_assets/g8_layer01_20260517T071405Z"
LAYER0_PACK = "layer_pack/gemma4_e4b_layer0_seq128_v0"
LAYER1_PACK = "layer_pack/gemma4_e4b_layer1_seq128_v0"
TOKEN_CACHE = "phase12/token_caches/20260524T164412Z_phase12_cde_authority_train_shard00"
TEACHER_SHARD = "phase12/teacher_shards/20260524T164412Z_phase12_cde_authority_train_shard00"

SOURCE_STATES = [
    {
        "name": "rank16_init_iter0",
        "rank": 16,
        "checkpoint": "phase12/checkpoints/20260524T164412Z_phase12_cde_authority_rank16_init",
        "phase12_iteration": "init_before_iter_000000",
    },
    {
        "name": "rank16_final_iter7",
        "rank": 16,
        "checkpoint": (
            "phase12/runs/20260524T164412Z_phase12_cde_authority_rank16_train/"
            "Phase12-CDE-learning/iterations/iter_000007/checkpoint"
        ),
        "phase12_iteration": "iter_000007",
    },
    {
        "name": "rank32_init_iter0",
        "rank": 32,
        "checkpoint": "phase12/checkpoints/20260524T164412Z_phase12_cde_authority_rank32_init",
        "phase12_iteration": "init_before_iter_000000",
    },
    {
        "name": "rank32_final_iter7",
        "rank": 32,
        "checkpoint": (
            "phase12/runs/20260524T164412Z_phase12_cde_authority_rank32_train/"
            "Phase12-CDE-learning/iterations/iter_000007/checkpoint"
        ),
        "phase12_iteration": "iter_000007",
    },
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def q(value: str) -> str:
    return shlex.quote(value)


def phone_path(root: str, child: str) -> str:
    if child.startswith("/"):
        return child
    return root.rstrip("/") + "/" + child.lstrip("/")


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


def run_command(command: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True)
    if check and completed.returncode != 0:
        joined = " ".join(q(part) for part in command)
        raise RuntimeError(
            f"command failed ({completed.returncode}): {joined}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def adb(serial: str, args: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return run_command(["adb", "-s", serial, *args], check=check)


def adb_shell(serial: str, command: str, *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return adb(serial, ["shell", command], check=check)


def adb_pull(serial: str, remote: str, local: Path, *, check: bool = False) -> bool:
    local.parent.mkdir(parents=True, exist_ok=True)
    completed = adb(serial, ["pull", remote, str(local)], check=False)
    if check and completed.returncode != 0:
        raise RuntimeError(f"adb pull failed: {remote}\n{completed.stderr}")
    return completed.returncode == 0


def adb_push(serial: str, local: Path, remote: str) -> None:
    adb(serial, ["push", str(local), remote], check=True)


def active_run_root() -> Path:
    return REPO_ROOT / load_json(ACTIVE_RUN)["run_root"]


def source_commit() -> str:
    return run_command(["git", "rev-parse", "HEAD"], check=True).stdout.strip()


def source_dirty() -> bool:
    return bool(run_command(["git", "status", "--porcelain=v1"], check=True).stdout.strip())


def command_log_entry(name: str, result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return {
        "name": name,
        "returncode": result.returncode,
        "stdout_first_2048": result.stdout[:2048],
        "stderr_first_2048": result.stderr[:2048],
    }


def deploy_layer_runner(serial: str, phone_gate_root: str, layer_runner: Path) -> dict[str, Any]:
    if not layer_runner.exists():
        raise FileNotFoundError(f"missing Android gemma4_layer_runner binary: {layer_runner}")
    remote_bin = f"{phone_gate_root}/bin"
    adb_shell(serial, f"rm -rf {q(remote_bin)} && mkdir -p {q(remote_bin)}", check=True)
    adb_push(serial, layer_runner, f"{remote_bin}/gemma4_layer_runner")
    adb_shell(serial, f"chmod 755 {q(remote_bin + '/gemma4_layer_runner')}", check=True)
    phone_sha = adb_shell(serial, f"sha256sum {q(remote_bin + '/gemma4_layer_runner')}", check=False)
    return {
        "phone_bin": remote_bin,
        "local_gemma4_layer_runner": str(layer_runner),
        "local_gemma4_layer_runner_sha256": sha256_file(layer_runner),
        "phone_sha256sum_stdout": phone_sha.stdout.strip(),
        "phone_sha256sum_returncode": phone_sha.returncode,
    }


def read_f32(path: Path, expected: int) -> array.array:
    values = array.array("f")
    with path.open("rb") as handle:
        values.frombytes(handle.read())
    if len(values) != expected:
        raise ValueError(f"{path} expected {expected} float32 values, found {len(values)}")
    return values


def write_f32(path: Path, values: array.array) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(values.tobytes())


def l2(values: array.array | list[float]) -> float:
    return math.sqrt(sum(float(value) * float(value) for value in values))


def l2_delta(left: array.array, right: array.array) -> float:
    return math.sqrt(
        sum((float(right[index]) - float(left[index])) ** 2 for index in range(len(left)))
    )


def pull_checkpoint(serial: str, checkpoint: str, local: Path, rank: int) -> dict[str, Any]:
    adb_pull(serial, f"{checkpoint}/adapter_a.f32.bin", local / "adapter_a.f32.bin", check=True)
    adb_pull(serial, f"{checkpoint}/adapter_b.f32.bin", local / "adapter_b.f32.bin", check=True)
    a = read_f32(local / "adapter_a.f32.bin", HIDDEN * rank)
    b = read_f32(local / "adapter_b.f32.bin", rank * HIDDEN)
    return {
        "adapter_a": a,
        "adapter_b": b,
        "adapter_a_sha256": sha256_file(local / "adapter_a.f32.bin"),
        "adapter_b_sha256": sha256_file(local / "adapter_b.f32.bin"),
    }


def run_topk_eval(
    *,
    serial: str,
    runner: str,
    phone_root: str,
    checkpoint: str,
    output_dir: str,
    rank: int,
    learning_rate: float,
    apply_update: bool,
) -> subprocess.CompletedProcess[str]:
    command = (
        f"{q(runner)} --run-h11f-topk-kl-compact "
        f"{q(phone_path(phone_root, TOKEN_CACHE))} "
        f"{q(phone_path(phone_root, ASSET_DIR))} "
        f"{q(phone_path(phone_root, LAYER0_PACK))} "
        f"{q(phone_path(phone_root, LAYER1_PACK))} "
        f"{q(checkpoint)} "
        f"{q(phone_path(phone_root, TEACHER_SHARD))} "
        f"{q(output_dir)} {learning_rate:.10f} {rank} "
        f"{'true' if apply_update else 'false'}"
    )
    return adb_shell(serial, f"rm -rf {q(output_dir)} && {command}", check=False)


def choose_coordinates(source_name: str, rank: int) -> list[dict[str, Any]]:
    rng = random.Random(f"{SEED}:{source_name}:{rank}")
    probes: list[dict[str, Any]] = []
    for tensor, count, size in (
        ("adapter_a", COORDS_PER_TENSOR_PER_SOURCE, HIDDEN * rank),
        ("adapter_b", COORDS_PER_TENSOR_PER_SOURCE, HIDDEN * rank),
    ):
        selected: set[int] = set()
        while len(selected) < count:
            selected.add(rng.randrange(size))
        for index in sorted(selected):
            probes.append(
                {
                    "source": source_name,
                    "rank": rank,
                    "tensor": tensor,
                    "index": index,
                    "epsilon": EPSILON,
                    "selection_policy": "seeded_uniform_without_replacement_over_flat_tensor",
                }
            )
    return probes


def make_perturbed_checkpoint(
    *,
    base_a: array.array,
    base_b: array.array,
    probe: dict[str, Any],
    sign: int,
    local_dir: Path,
) -> None:
    a = array.array("f", base_a)
    b = array.array("f", base_b)
    target = a if probe["tensor"] == "adapter_a" else b
    target[probe["index"]] = float(target[probe["index"]]) + (sign * EPSILON)
    write_f32(local_dir / "adapter_a.f32.bin", a)
    write_f32(local_dir / "adapter_b.f32.bin", b)


def push_checkpoint(serial: str, local_dir: Path, remote_dir: str) -> None:
    adb_shell(serial, f"rm -rf {q(remote_dir)} && mkdir -p {q(remote_dir)}", check=True)
    adb_push(serial, local_dir / "adapter_a.f32.bin", f"{remote_dir}/adapter_a.f32.bin")
    adb_push(serial, local_dir / "adapter_b.f32.bin", f"{remote_dir}/adapter_b.f32.bin")


def result_passes(analytic: float, finite_diff: float) -> tuple[bool, dict[str, Any]]:
    abs_error = abs(finite_diff - analytic)
    denom = max(abs(analytic), 1.0e-12)
    rel_error = abs_error / denom
    sign_required = abs(analytic) >= SIGN_THRESHOLD
    sign_match = (finite_diff == 0.0 and analytic == 0.0) or (finite_diff * analytic > 0.0)
    passed = abs_error <= ABS_TOL or (rel_error <= REL_TOL and (not sign_required or sign_match))
    return passed, {
        "absolute_error": abs_error,
        "relative_error": rel_error,
        "sign_required": sign_required,
        "sign_match": sign_match,
    }


def write_artifact_manifest(report_dir: Path) -> None:
    entries: list[dict[str, Any]] = []
    for path in sorted(report_dir.rglob("*")):
        if path.is_file() and path.name != "artifact_manifest.json":
            entries.append({"path": rel(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    write_json(
        report_dir / "artifact_manifest.json",
        {
            "schema_version": "phase13_p13d_artifact_manifest_v1",
            "created_at_utc": utc_now(),
            "artifacts": entries,
        },
    )


def update_phase13_status(run_root: Path, status: str, gate_result_path: Path) -> None:
    status_path = run_root / "phase13_gate_status.json"
    phase_status = load_json(status_path)
    phase_status["gate_status"]["P13-D"] = status
    phase_status["current_gate"] = "P13-E" if status == "pass" else "P13-D"
    phase_status["latest_gate_result"] = rel(gate_result_path)
    phase_status["updated_at_utc"] = utc_now()
    write_json(status_path, phase_status)

    active = load_json(ACTIVE_RUN)
    active["current_gate"] = phase_status["current_gate"]
    active["updated_at_utc"] = utc_now()
    write_json(ACTIVE_RUN, active)


def update_gpd_state(status: str, gate_result_path: Path, pass_count: int, max_rel: float, max_abs: float) -> None:
    if status != "pass":
        return
    gate_rel = rel(gate_result_path)
    state_path = REPO_ROOT / ".gpd/state.json"
    state = load_json(state_path)
    desc = (
        f"P13-D expanded gradient parity passed at {gate_rel}. Seeded phone finite-difference "
        f"checks covered {pass_count} residual-adapter coordinates across rank16/rank32, "
        f"adapter A/B, and init/final Phase 12 checkpoint states; max relative error {max_rel:.6g}, "
        f"max absolute error {max_abs:.6g}."
    )
    state["position"]["last_activity"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    state["position"]["last_activity_desc"] = desc
    state["position"]["last_activity_description"] = desc
    state["position"]["status"] = "Phase 13 execution in progress; P13-A through P13-D passed; next gate is P13-E multi-site Gemma adapter"
    state["session"]["stopped_at"] = (
        "P13-D expanded gradient parity passed; continue with P13-E multi-site Gemma adapter or exact falsification. "
        "Do not run P13-H until P13-E through P13-G also have exact pass/fail/fallback artifacts."
    )
    todos = [
        item for item in state.get("pending_todos", [])
        if "P13-D" not in item and "expanded gradient parity" not in item
    ]
    next_todo = (
        "Execute P13-E next: implement or exactly falsify the smallest real second Gemma-compatible trainable site."
    )
    if next_todo not in todos:
        todos.insert(0, next_todo)
    state["pending_todos"] = todos
    result = (
        f"P13-D expanded gradient parity passed: {gate_rel}. Seeded phone finite differences "
        f"validated {pass_count} sampled rank16/rank32 residual-adapter coordinates with max_rel={max_rel:.6g} "
        f"and max_abs={max_abs:.6g}; no HTP or multi-site claim is promoted."
    )
    if result not in state.setdefault("intermediate_results", []):
        state["intermediate_results"].append(result)
    state["_synced_at"] = utc_now()
    write_json(state_path, state)

    state_md = REPO_ROOT / ".gpd/STATE.md"
    text = state_md.read_text(encoding="utf-8")
    text = text.replace(
        "**Status:** Phase 13 execution in progress; P13-A through P13-C passed; next gate is P13-D expanded gradient parity",
        "**Status:** Phase 13 execution in progress; P13-A through P13-D passed; next gate is P13-E multi-site Gemma adapter",
    )
    marker = "\n## Session Continuity\n"
    entry = (
        f"- P13-D expanded gradient parity passed: `{gate_rel}`. Seeded phone finite-difference "
        f"checks covered `{pass_count}` residual-adapter coordinates across rank16/rank32, "
        f"adapter A/B, and init/final checkpoint states; max relative error `{max_rel:.6g}`, "
        f"max absolute error `{max_abs:.6g}`.\n"
    )
    if entry not in text and marker in text:
        text = text.replace(marker, entry + marker)
    text = text.replace(
        "- Execute P13-D next: run seeded expanded gradient parity over at least `64`\n"
        "  adapter A/B coordinates and multiple iterations, or record an exact blocker.\n",
        "- Execute P13-E next: implement or exactly falsify the smallest real second\n"
        "  Gemma-compatible trainable site.\n",
    )
    text = text.replace(
        "**Stopped at:** P13-C scaled phone-native HF corpus passed; continue with P13-D\n"
        "expanded gradient parity. Do not run P13-H until P13-D through P13-G have exact\n"
        "pass/fail/fallback artifacts.",
        "**Stopped at:** P13-D expanded gradient parity passed; continue with P13-E\n"
        "multi-site Gemma adapter or exact falsification. Do not run P13-H until P13-E\n"
        "through P13-G have exact pass/fail/fallback artifacts.",
    )
    state_md.write_text(text, encoding="utf-8")

    runlog = REPO_ROOT / ".gpd/runlog.jsonl"
    event = {
        "ts": utc_now(),
        "event": "phase13_p13d_expanded_gradient_parity_passed",
        "project": "polymath-gemma4-snapdragon-megakernel",
        "status": "pass",
        "branch": "gemma4-megakernel-native-training",
        "evidence": gate_rel,
        "note": (
            f"P13-D validated {pass_count} seeded phone finite-difference residual-adapter coordinates "
            f"across rank16/rank32 and init/final checkpoints; max_rel={max_rel:.6g}, max_abs={max_abs:.6g}."
        ),
    }
    with runlog.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serial", default=DEFAULT_SERIAL)
    parser.add_argument("--phone-root", default=DEFAULT_PHONE_ROOT)
    parser.add_argument("--layer-runner", type=Path, default=DEFAULT_LAYER_RUNNER)
    args = parser.parse_args()

    run_root = active_run_root()
    run_id = load_json(ACTIVE_RUN)["run_id"]
    report_dir = run_root / "P13-D-expanded-gradient-parity"
    report_dir.mkdir(parents=True, exist_ok=True)
    phone_gate_root = f"{args.phone_root}/phase13/{run_id}/p13d"
    commands: list[dict[str, Any]] = []
    blockers: list[str] = []
    base_records: list[dict[str, Any]] = []
    probe_results: list[dict[str, Any]] = []

    required_paths = [
        phone_path(args.phone_root, TOKEN_CACHE),
        phone_path(args.phone_root, TEACHER_SHARD),
        phone_path(args.phone_root, ASSET_DIR),
        phone_path(args.phone_root, LAYER0_PACK),
        phone_path(args.phone_root, LAYER1_PACK),
    ]
    for source in SOURCE_STATES:
        required_paths.append(phone_path(args.phone_root, source["checkpoint"]))
    for path in required_paths:
        if adb_shell(args.serial, f"test -e {q(path)}", check=False).returncode != 0:
            blockers.append(f"missing phone path: {path}")

    deploy: dict[str, Any] = {}
    if not blockers:
        deploy = deploy_layer_runner(args.serial, phone_gate_root, args.layer_runner)
        write_json(report_dir / "binary_deploy_manifest.json", deploy)

    with tempfile.TemporaryDirectory(prefix="phase13_p13d_") as tmp_name:
        tmp = Path(tmp_name)
        source_contexts: dict[str, dict[str, Any]] = {}
        if not blockers:
            for source in SOURCE_STATES:
                source_name = source["name"]
                rank = int(source["rank"])
                checkpoint = phone_path(args.phone_root, source["checkpoint"])
                local_base = tmp / source_name / "base"
                local_post = tmp / source_name / "post"
                checkpoint_payload = pull_checkpoint(args.serial, checkpoint, local_base, rank)
                base_out = f"{phone_gate_root}/base_grad/{source_name}"
                run_result = run_topk_eval(
                    serial=args.serial,
                    runner=f"{phone_gate_root}/bin/gemma4_layer_runner",
                    phone_root=args.phone_root,
                    checkpoint=checkpoint,
                    output_dir=base_out,
                    rank=rank,
                    learning_rate=BASE_LR,
                    apply_update=True,
                )
                commands.append(command_log_entry(f"base phone gradient via SGD delta {source_name}", run_result))
                if run_result.returncode != 0:
                    blockers.append(f"base gradient run failed for {source_name}")
                    continue
                adb_pull(args.serial, f"{base_out}/telemetry.json", report_dir / "base_runs" / source_name / "telemetry.json", check=True)
                adb_pull(args.serial, f"{base_out}/checkpoint/manifest.json", report_dir / "base_runs" / source_name / "checkpoint_manifest.json", check=True)
                pull_checkpoint(args.serial, f"{base_out}/checkpoint", local_post, rank)
                pre_a = checkpoint_payload["adapter_a"]
                pre_b = checkpoint_payload["adapter_b"]
                post_a = read_f32(local_post / "adapter_a.f32.bin", HIDDEN * rank)
                post_b = read_f32(local_post / "adapter_b.f32.bin", HIDDEN * rank)
                grad_a = array.array("f", ((float(pre_a[i]) - float(post_a[i])) / BASE_LR for i in range(len(pre_a))))
                grad_b = array.array("f", ((float(pre_b[i]) - float(post_b[i])) / BASE_LR for i in range(len(pre_b))))
                telemetry = load_json(report_dir / "base_runs" / source_name / "telemetry.json")
                inferred_a_l2 = l2(grad_a)
                inferred_b_l2 = l2(grad_b)
                tel_a_l2 = float(telemetry["gradient_l2"]["adapter_a"])
                tel_b_l2 = float(telemetry["gradient_l2"]["adapter_b"])
                source_contexts[source_name] = {
                    "source": source,
                    "checkpoint": checkpoint,
                    "rank": rank,
                    "base_a": pre_a,
                    "base_b": pre_b,
                    "grad_a": grad_a,
                    "grad_b": grad_b,
                    "base_loss": float(telemetry["loss_topk_kl"]),
                    "base_out": base_out,
                }
                base_records.append(
                    {
                        "source": source_name,
                        "rank": rank,
                        "checkpoint": checkpoint,
                        "phase12_iteration": source["phase12_iteration"],
                        "base_phone_output_dir": base_out,
                        "base_loss_topk_kl": float(telemetry["loss_topk_kl"]),
                        "telemetry_gradient_l2": {"adapter_a": tel_a_l2, "adapter_b": tel_b_l2},
                        "inferred_from_sgd_delta_gradient_l2": {
                            "adapter_a": inferred_a_l2,
                            "adapter_b": inferred_b_l2,
                        },
                        "gradient_l2_abs_delta": {
                            "adapter_a": abs(inferred_a_l2 - tel_a_l2),
                            "adapter_b": abs(inferred_b_l2 - tel_b_l2),
                        },
                        "base_checkpoint_sha256": {
                            "adapter_a": checkpoint_payload["adapter_a_sha256"],
                            "adapter_b": checkpoint_payload["adapter_b_sha256"],
                        },
                    }
                )

            probes: list[dict[str, Any]] = []
            for source in SOURCE_STATES:
                probes.extend(choose_coordinates(source["name"], int(source["rank"])))
            predeclare = {
                "schema_version": "phase13_p13d_predeclared_gradient_probe_plan_v1",
                "declared_at_utc": utc_now(),
                "seed": SEED,
                "epsilon": EPSILON,
                "base_learning_rate_for_phone_sgd_gradient_inference": BASE_LR,
                "coordinate_count": len(probes),
                "source_states": SOURCE_STATES,
                "selection_policy": "For each source state, select 8 adapter_a and 8 adapter_b flat indices with seeded uniform sampling independent of gradient magnitude.",
                "pass_rule": {
                    "minimum_pass_count": MIN_PASS_COUNT,
                    "relative_error_max": REL_TOL,
                    "absolute_error_max": ABS_TOL,
                    "sign_required_when_abs_analytic_gradient_gte": SIGN_THRESHOLD,
                },
                "probes": probes,
                "nonclaims": [
                    "This is sampled residual-adapter parity, not full-gradient proof.",
                    "This does not validate a second trainable site.",
                    "This does not validate HTP backprop.",
                ],
            }
            write_json(report_dir / "predeclared_gradient_probe_plan.json", predeclare)

            for ordinal, probe in enumerate(probes):
                source_name = probe["source"]
                if source_name not in source_contexts:
                    continue
                context = source_contexts[source_name]
                tensor = probe["tensor"]
                index = int(probe["index"])
                gradient_array = context["grad_a"] if tensor == "adapter_a" else context["grad_b"]
                analytic = float(gradient_array[index])
                losses: dict[str, float] = {}
                eval_records: dict[str, Any] = {}
                for sign_name, sign in (("minus", -1), ("plus", 1)):
                    local_ckpt = tmp / "fd" / f"{ordinal:03d}_{sign_name}" / "checkpoint"
                    make_perturbed_checkpoint(
                        base_a=context["base_a"],
                        base_b=context["base_b"],
                        probe=probe,
                        sign=sign,
                        local_dir=local_ckpt,
                    )
                    remote_ckpt = f"{phone_gate_root}/fd_checkpoints/probe_{ordinal:03d}_{sign_name}"
                    remote_out = f"{phone_gate_root}/fd_evals/probe_{ordinal:03d}_{sign_name}"
                    push_checkpoint(args.serial, local_ckpt, remote_ckpt)
                    run_result = run_topk_eval(
                        serial=args.serial,
                        runner=f"{phone_gate_root}/bin/gemma4_layer_runner",
                        phone_root=args.phone_root,
                        checkpoint=remote_ckpt,
                        output_dir=remote_out,
                        rank=int(context["rank"]),
                        learning_rate=0.0,
                        apply_update=False,
                    )
                    commands.append(command_log_entry(f"finite difference {ordinal:03d} {sign_name}", run_result))
                    local_eval = report_dir / "evals" / f"probe_{ordinal:03d}_{sign_name}" / "telemetry.json"
                    if run_result.returncode != 0:
                        blockers.append(f"finite-difference eval failed for probe {ordinal:03d} {sign_name}")
                        continue
                    adb_pull(args.serial, f"{remote_out}/telemetry.json", local_eval, check=True)
                    telemetry = load_json(local_eval)
                    losses[sign_name] = float(telemetry["loss_topk_kl"])
                    eval_records[sign_name] = {
                        "phone_output_dir": remote_out,
                        "local_telemetry": rel(local_eval),
                        "loss_topk_kl": losses[sign_name],
                        "returncode": run_result.returncode,
                    }
                if "plus" not in losses or "minus" not in losses:
                    continue
                finite_diff = (losses["plus"] - losses["minus"]) / (2.0 * EPSILON)
                passed, error_payload = result_passes(analytic, finite_diff)
                probe_results.append(
                    {
                        "ordinal": ordinal,
                        **probe,
                        "analytic_gradient_from_phone_sgd_delta": analytic,
                        "finite_difference_gradient": finite_diff,
                        "passed": passed,
                        **error_payload,
                        "evals": eval_records,
                    }
                )

    pass_count = sum(1 for item in probe_results if item["passed"])
    fail_count = len(probe_results) - pass_count
    max_abs = max((float(item["absolute_error"]) for item in probe_results), default=float("inf"))
    max_rel = max((float(item["relative_error"]) for item in probe_results), default=float("inf"))

    if len(probe_results) != MIN_PASS_COUNT:
        blockers.append(f"expected {MIN_PASS_COUNT} completed probes, found {len(probe_results)}")
    if pass_count < MIN_PASS_COUNT:
        blockers.append(f"only {pass_count}/{MIN_PASS_COUNT} gradient probes passed")
    for record in base_records:
        if record["gradient_l2_abs_delta"]["adapter_a"] > 1.0e-6:
            blockers.append(f"{record['source']} adapter_a SGD-inferred gradient L2 does not match telemetry")
        if record["gradient_l2_abs_delta"]["adapter_b"] > 1.0e-6:
            blockers.append(f"{record['source']} adapter_b SGD-inferred gradient L2 does not match telemetry")

    summary = {
        "schema_version": "phase13_p13d_gradient_parity_summary_v1",
        "created_at_utc": utc_now(),
        "run_id": run_id,
        "phone_gate_root": phone_gate_root,
        "model_id": MODEL_ID,
        "revision": MODEL_REVISION,
        "method": "phone_finite_difference_vs_phone_sgd_checkpoint_delta_gradient",
        "rank_coverage": sorted({item["rank"] for item in probe_results}),
        "source_state_count": len(SOURCE_STATES),
        "probe_count": len(probe_results),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "max_absolute_error": max_abs,
        "max_relative_error": max_rel,
        "base_records": base_records,
        "probe_results": probe_results,
        "source_commit": source_commit(),
        "source_tree_dirty": source_dirty(),
    }
    write_json(report_dir / "gradient_parity_summary.json", summary)

    status = "pass" if not blockers else "fail"
    gate = {
        "schema_version": "phase13_p13d_gate_result_v1",
        "gate": "P13-D-expanded-gradient-parity",
        "run_id": run_id,
        "status": status,
        "started_at_utc": utc_now(),
        "ended_at_utc": utc_now(),
        "blockers": blockers,
        "phone_gate_root": phone_gate_root,
        "model_id": MODEL_ID,
        "revision": MODEL_REVISION,
        "method": summary["method"],
        "probe_count": len(probe_results),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "max_absolute_error": max_abs,
        "max_relative_error": max_rel,
        "rank_coverage": summary["rank_coverage"],
        "tensor_coverage": sorted({item["tensor"] for item in probe_results}),
        "source_state_coverage": sorted({item["source"] for item in probe_results}),
        "promoted_claims": [
            f"Seeded sampled phone finite-difference parity passed for {pass_count} residual-adapter coordinates.",
            "Coverage includes rank16/rank32, adapter_a/adapter_b, and init/final checkpoint states.",
        ]
        if status == "pass"
        else [],
        "nonclaims": [
            "P13-D is sampled residual-adapter gradient parity, not full-gradient proof.",
            "P13-D does not validate multi-site adapters.",
            "P13-D does not validate HTP backprop or heterogeneous training.",
        ],
    }
    write_json(report_dir / "gate_result.json", gate)
    write_text(report_dir / "blockers.md", "- None.\n" if not blockers else "".join(f"- {item}\n" for item in blockers))
    write_text(
        report_dir / "falsifier_report.md",
        "# P13-D Falsifier Report\n\n"
        f"- Gate status: {status}.\n"
        f"- Completed probes: {len(probe_results)}; passed: {pass_count}; failed: {fail_count}.\n"
        f"- Rank coverage: {summary['rank_coverage']}.\n"
        f"- Max absolute error: {max_abs:.10g}; max relative error: {max_rel:.10g}.\n"
        "- Host gradient substitution: false; finite-difference losses and SGD-gradient source both come from phone runner outputs.\n"
        "- Full-gradient claim: false; this is sampled parity only.\n",
    )
    write_text(report_dir / "commands.log", "\n".join(json.dumps(item, sort_keys=True) for item in commands) + "\n")
    write_artifact_manifest(report_dir)
    update_phase13_status(run_root, status, report_dir / "gate_result.json")
    update_gpd_state(status, report_dir / "gate_result.json", pass_count, max_rel, max_abs)

    print(json.dumps({"status": status, "gate_result": rel(report_dir / "gate_result.json")}, indent=2))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
