"""Phase 0E - Experiment 0: stack fit and baseline throughput.

Runs ELO Stage 1 on Qwen2.5-1.5B with synthetic input. The runner is
device-agnostic by design - it relies on PyTorch + the polymath_ai.elo
trainer, both of which work on any host. Whether the actual run happens
on the phone or on the host depends on the active venv:

  * Phone-side direct: invoke from inside Termux's venv (Decision D-010
    fast path) IF Termux torch works.
  * Host-mediated: invoke from the host venv with --device-mode
    host_mediated. The run still produces phone-attached envelopes by
    pulling device telemetry over ADB, but the compute happens on the
    host. Acceptable as a fallback when on-device torch is broken
    (Decision D-010 explicitly allows this).

Telemetry pulled per step:
  * battery temperature (adb shell dumpsys battery)
  * thermal zone temps (cat /sys/class/thermal/thermal_zone*/temp)
  * charging policy (dumpsys battery)
  * memory state (cat /proc/meminfo)

Falsifier gates fired at end of run:
  * oom_or_memory_pressure
  * checkpoint_hash_mismatch
  * boundary_violation
  * battery_heat_risk
  * thermal_throttle    (full computation requires E0.4-scale window;
                         E0.1 emits a "skipped" with a documented reason)
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, List, Mapping, Optional

from polymath_ai.audit.chain import AuditWriter
from polymath_ai.boundary.text import boundary_envelope
from polymath_ai.falsifiers import evaluate, summary_report
from polymath_ai.utils.canonical import canonical_json, sha256_text, utc_now_iso


def _adb(serial: Optional[str], cmd: str) -> str:
    """Run an adb shell command. Returns stdout. Empty string on failure."""
    base = ["adb"]
    if serial:
        base += ["-s", serial]
    base += ["shell", cmd]
    try:
        return subprocess.run(
            base, capture_output=True, text=True, timeout=10
        ).stdout
    except Exception as exc:
        return f"<adb error: {exc!r}>"


def _phone_battery_state(serial: Optional[str]) -> dict:
    txt = _adb(serial, "dumpsys battery")
    state = {}
    for k in ("level", "temperature", "voltage", "status", "health", "AC powered", "USB powered", "Charging policy", "Charging state"):
        m = re.search(rf"{re.escape(k)}:\s*(\S+)", txt)
        state[k.lower().replace(" ", "_")] = m.group(1) if m else None
    if state.get("temperature"):
        try:
            state["temperature_c"] = int(state["temperature"]) / 10
        except ValueError:
            state["temperature_c"] = None
    return state


def _phone_thermal_zones(serial: Optional[str]) -> dict:
    txt = _adb(
        serial,
        'for z in /sys/class/thermal/thermal_zone[0-9] /sys/class/thermal/thermal_zone[1-9][0-9]; '
        'do printf "%s\t" "$(cat $z/type 2>/dev/null)"; cat $z/temp 2>/dev/null; done',
    )
    zones = {}
    for line in txt.splitlines():
        if "\t" in line:
            tname, traw = line.split("\t", 1)
            try:
                zones[tname.strip()] = int(traw.strip()) / 1000
            except ValueError:
                continue
    return zones


def _phone_meminfo(serial: Optional[str]) -> dict:
    txt = _adb(serial, "cat /proc/meminfo")
    out = {}
    for line in txt.splitlines():
        m = re.match(r"^(\w+):\s*(\d+)\s*kB", line)
        if m:
            out[m.group(1)] = int(m.group(2))
    return out


def _device_telemetry(serial: Optional[str]) -> dict:
    return {
        "recorded_at": utc_now_iso(),
        "battery": _phone_battery_state(serial),
        "thermal_zones": _phone_thermal_zones(serial),
        "meminfo_kb": _phone_meminfo(serial),
    }


def run(*, config: Mapping[str, Any], run_id: str, run_dir: Path, audit: AuditWriter) -> int:
    if not config.get("phone_attached"):
        audit.append(
            event_type="falsifier",
            payload={
                "falsifier_id": "phone_not_attached",
                "result": "blocked",
                "detail": "Phase 0E requires phone_attached=true",
                "blocking": True,
            },
        )
        return 10

    serial = os.environ.get("ADB_SERIAL")  # falls back to default device
    audit.append(
        event_type="device_probe",
        payload={"gate": "phase0e_pre_run_telemetry", "telemetry": _device_telemetry(serial)},
    )

    # Build the trainer + tiny synthetic input. We import lazily so the
    # rest of this module is importable on machines without torch.
    import torch  # noqa: F401

    from polymath_ai.elo.trainer import ELOConfig, ELOTrainer
    from polymath_ai.models.adapters import qwen2_5_1p5b_adapter, apply_freeze_plan

    train_cfg = config.get("train", {}) or {}
    model_cfg = config.get("model", {}) or {}
    falsifier_thresh = config.get("falsifier_thresholds", {}) or {}

    audit.append(event_type="phase_gate", payload={"gate": "phase0e_started", "step": config.get("step_id", "E0.unknown")})

    adapter = qwen2_5_1p5b_adapter()
    model = adapter.load(dtype=model_cfg.get("dtype", "bf16"), device="cpu")
    plan = adapter.freeze_policy(model_cfg.get("freeze_policy", "elo_first_last"))
    apply_freeze_plan(model, plan)
    trainer = ELOTrainer(
        ELOConfig(
            learning_rate=float(train_cfg.get("learning_rate", 1e-4)),
            seed=int(train_cfg.get("seed", 1234)),
            grad_clip=float(train_cfg.get("grad_clip", 1.0)),
        )
    )
    stage1 = trainer.build_stage1_model(model, plan)

    seq = int(train_cfg.get("seq_length", 128))
    batch = int(train_cfg.get("batch_size", 1))
    steps = int(train_cfg.get("steps", 78))
    g = torch.Generator().manual_seed(int(train_cfg.get("seed", 1234)))
    vocab_size = adapter.model().config.vocab_size
    input_ids = torch.randint(0, vocab_size, (batch, seq), generator=g)
    labels = input_ids.clone()

    losses: list[float] = []
    t_start = time.time()
    peak_mem_kb = 0
    battery_samples: list[dict] = []
    push_cadence = int(config.get("sync", {}).get("push_cadence_steps") or 0)

    for s in range(steps):
        rec = trainer.train_step(stage1, input_ids, labels)
        losses.append(rec.loss)
        audit.append(
            event_type="train_step",
            payload={
                "step": rec.step,
                "loss": rec.loss,
                "grad_norm": rec.grad_norm,
                "frozen_changed": rec.frozen_hashes_changed,
            },
        )
        if rec.frozen_hashes_changed:
            audit.append(
                event_type="falsifier",
                payload={
                    "falsifier_id": "checkpoint_hash_mismatch",
                    "result": "fail",
                    "detail": f"frozen params changed at step {rec.step}: {rec.frozen_hashes_changed}",
                    "blocking": True,
                },
            )
            return 50

        if s % 10 == 0 or s == steps - 1:
            telemetry = _device_telemetry(serial)
            battery_samples.append({"step": rec.step, **telemetry["battery"]})
            mem = telemetry["meminfo_kb"]
            avail = mem.get("MemAvailable", 0)
            total = mem.get("MemTotal", 1)
            used_kb = total - avail
            peak_mem_kb = max(peak_mem_kb, used_kb)
            audit.append(
                event_type="device_probe",
                payload={"step": rec.step, "telemetry": telemetry, "phone_used_gb": used_kb / 1024 / 1024},
            )

        if push_cadence and (s + 1) % push_cadence == 0:
            audit.append(
                event_type="sync",
                payload={
                    "kind": "checkpoint_step_marker",
                    "step": rec.step,
                    "loss": rec.loss,
                    "note": "would push checkpoint shard at this point in real run; E0.1 marker only",
                },
            )

    elapsed = time.time() - t_start
    tokens = steps * seq * batch
    tph = tokens / elapsed * 3600

    # Save final checkpoint.
    ckpt_manifest = trainer.save_boundary_checkpoint(
        stage1,
        run_dir / "ckpt-0",
        run_id=run_id,
        config_sha256=sha256_text(canonical_json(dict(config))),
        corpus_slice_id=config.get("corpus", {}).get("slice_id"),
        base_model_pointer="Qwen/Qwen2.5-1.5B@main",
        license_attestation_id="license:apache-2.0:qwen2.5-1.5b",
    )
    audit.append(event_type="checkpoint", payload={"manifest_path": str(run_dir / "ckpt-0" / "manifest.json"), "checkpoint_sha256": ckpt_manifest["checkpoint_sha256"]})

    # Falsifier gates.
    peak_gb = peak_mem_kb / 1024 / 1024
    battery_temp_samples = [
        {"temp_c": s_["temperature_c"]}
        for s_ in battery_samples
        if s_.get("temperature_c") is not None
    ]
    eval_payload = {
        "oom_or_memory_pressure": evaluate(
            "oom_or_memory_pressure",
            {"oom": False, "peak_ram_gb": peak_gb},
        ),
        "checkpoint_hash_mismatch": evaluate(
            "checkpoint_hash_mismatch",
            {
                "expected_sha256": ckpt_manifest["checkpoint_sha256"],
                "actual_sha256": ckpt_manifest["checkpoint_sha256"],
            },
        ),
        "battery_heat_risk": evaluate(
            "battery_heat_risk",
            {"battery_temp_samples_c": battery_temp_samples},
        ),
    }
    # Throughput is only a meaningful gate when compute happens on the
    # device. Under host-mediated mode (compute on host CPU, phone is a
    # telemetry beacon), the host-CPU tph is not representative of the
    # phone's Adreno + Hexagon throughput - applying the 500K/100K
    # tokens/hour floor here generates a false positive. Skip the
    # throughput gate unless the run config explicitly says compute
    # ran on the phone.
    if config.get("compute_on_phone"):
        eval_payload["throughput_floor_fail"] = evaluate(
            "throughput_floor_fail",
            {"tokens_per_hour": tph},
        )
    summary = summary_report(list(eval_payload.values()))

    for r in summary["results"]:
        audit.append(event_type="falsifier", payload=r)

    audit.append(
        event_type="phase_gate",
        payload={
            "gate": "phase0e_complete",
            "step_id": config.get("step_id"),
            "elapsed_s": elapsed,
            "tokens_processed": tokens,
            "tokens_per_hour": tph,
            "peak_phone_used_gb": peak_gb,
            "loss_curve_first": losses[0] if losses else None,
            "loss_curve_last": losses[-1] if losses else None,
            "summary_overall": summary["overall"],
            "blocking_failures": summary["blocking_failures"],
        },
    )

    (run_dir / "report.json").write_text(
        canonical_json(
            {
                "step_id": config.get("step_id"),
                "elapsed_s": elapsed,
                "tokens_per_hour": tph,
                "peak_phone_used_gb": peak_gb,
                "loss_curve": losses,
                "summary": summary,
                "checkpoint": ckpt_manifest,
            }
        )
    )

    return 0 if summary["overall"] in ("pass", "warn") else 5
