"""Concrete falsifier checks.

Every entry maps a falsifier ID (from PRD §Falsifier Registry) to:
  * ``description`` - human-readable purpose
  * ``blocking_default`` - whether a fail blocks phase advancement by default
  * ``check`` - callable ``(evidence: dict) -> (result: str, detail: str)``

Evidence shapes are documented inline. Callers are expected to provide the
required keys. Missing keys produce ``skipped`` so the registry is safe to
sweep across partially-populated evidence dicts.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Callable, Dict, List, Mapping, Sequence, Tuple


CheckFn = Callable[[Mapping[str, Any]], Tuple[str, str]]


def _skipped(reason: str) -> Tuple[str, str]:
    return "skipped", reason


def _ok(detail: str = "") -> Tuple[str, str]:
    return "pass", detail


def _fail(detail: str) -> Tuple[str, str]:
    return "fail", detail


def _warn(detail: str) -> Tuple[str, str]:
    return "warn", detail


def _blocked(detail: str) -> Tuple[str, str]:
    return "blocked", detail


# ---------- individual checks ----------


def _check_boundary_violation(ev: Mapping[str, Any]) -> Tuple[str, str]:
    """Evidence: ``{"scan_failures": [BoundaryScanResult-like dict, ...]}``."""
    if "scan_failures" not in ev:
        return _skipped("no scan_failures key")
    failures = ev["scan_failures"]
    if not failures:
        return _ok("scanner reports clean")
    return _fail(f"{len(failures)} scan failures: {failures[:3]}")


def _check_device_soc_mismatch(ev: Mapping[str, Any]) -> Tuple[str, str]:
    """Evidence: ``{"soc_reported": str, "soc_target": str}``."""
    reported = ev.get("soc_reported")
    target = ev.get("soc_target")
    if not reported or not target:
        return _skipped("soc_reported or soc_target missing")
    if reported.lower() == target.lower():
        return _ok(f"soc_reported {reported} == target {target}")
    return _fail(f"soc_reported {reported!r} != target {target!r}")


def _check_qnn_exact_path_unproven(ev: Mapping[str, Any]) -> Tuple[str, str]:
    """Evidence: ``{"qnn_compile_records": [{"graph_scope": ..., "result": "ok"|...}]}``."""
    if "qnn_compile_records" not in ev:
        return _skipped("no qnn_compile_records")
    records = ev["qnn_compile_records"]
    if not records:
        return _blocked("no QNN compile attempts recorded - QNN claims must be measured")
    successes = [r for r in records if r.get("result") == "ok"]
    if not successes:
        return _blocked("no successful QNN compile - QNN cannot be enabled")
    return _ok(f"{len(successes)}/{len(records)} QNN compiles succeeded")


def _check_qnn_unsupported_op(ev: Mapping[str, Any]) -> Tuple[str, str]:
    """Evidence: ``{"delegate_pct": float, "delegate_threshold": float, "unsupported_ops": [...]}``."""
    if "delegate_pct" not in ev:
        return _skipped("no delegate_pct")
    pct = float(ev["delegate_pct"])
    threshold = float(ev.get("delegate_threshold", 0.5))
    if pct < threshold:
        return _fail(
            f"delegate_pct={pct:.2f} below threshold {threshold:.2f}; "
            f"unsupported_ops={ev.get('unsupported_ops', [])}"
        )
    return _ok(f"delegate_pct={pct:.2f}")


def _check_smollm3_export_unproven(ev: Mapping[str, Any]) -> Tuple[str, str]:
    """Evidence: ``{"experiment_2_status": "pass"|"fail"|"deferred"}``."""
    status = ev.get("experiment_2_status")
    if status is None:
        return _skipped("experiment_2_status missing")
    if status == "pass":
        return _ok("Experiment 2 passed")
    return _blocked(f"Experiment 2 status={status!r}; SmolLM3 acceleration not allowed")


def _check_checkpoint_hash_mismatch(ev: Mapping[str, Any]) -> Tuple[str, str]:
    expected = ev.get("expected_sha256")
    actual = ev.get("actual_sha256")
    if expected is None or actual is None:
        return _skipped("expected_sha256 / actual_sha256 missing")
    if expected != actual:
        return _fail(f"checkpoint hash {actual} != manifest {expected}")
    return _ok("hashes match")


def _check_tokenizer_fertility_high(ev: Mapping[str, Any]) -> Tuple[str, str]:
    """Evidence: ``{"per_language": {"<lang>": {"ratio_vs_english": float}, ...}, "threshold": 2.5}``."""
    per_lang = ev.get("per_language")
    if not per_lang:
        return _skipped("per_language missing")
    threshold = float(ev.get("threshold", 2.5))
    high = {l: r["ratio_vs_english"] for l, r in per_lang.items() if r.get("ratio_vs_english", 0) > threshold}
    if high:
        return _fail(f"languages above {threshold}x English fertility: {high}")
    return _ok(f"{len(per_lang)} languages all at or below {threshold}x")


def _check_oom_or_memory_pressure(ev: Mapping[str, Any]) -> Tuple[str, str]:
    if ev.get("oom"):
        return _fail("OOM observed")
    peak = ev.get("peak_ram_gb")
    if peak is None:
        return _skipped("peak_ram_gb missing")
    if peak >= 22.0:
        return _fail(f"peak RAM {peak:.2f} GB exceeds 22 GB hard ceiling")
    if peak >= 20.0:
        return _warn(f"peak RAM {peak:.2f} GB above 20 GB preferred ceiling")
    return _ok(f"peak RAM {peak:.2f} GB")


def _check_thermal_throttle(ev: Mapping[str, Any]) -> Tuple[str, str]:
    """Evidence: ``{"gpu_clock_below_600_pct": float}`` (fraction of 1h window)."""
    pct = ev.get("gpu_clock_below_600_pct")
    if pct is None:
        return _skipped("gpu_clock_below_600_pct missing")
    if pct > 0.10:
        return _fail(f"GPU clock <600 MHz for {pct*100:.1f}% of window (>10% threshold)")
    return _ok(f"GPU clock <600 MHz only {pct*100:.1f}% of window")


def _check_battery_heat_risk(ev: Mapping[str, Any]) -> Tuple[str, str]:
    samples = ev.get("battery_temp_samples_c")
    if not samples:
        return _skipped("battery_temp_samples_c missing")
    over_42_secs = sum(1 for s in samples if s.get("temp_c", 0) >= 42)
    over_40_5min = sum(1 for s in samples if 40 <= s.get("temp_c", 0) < 42)
    if over_42_secs >= 60:
        return _fail(">=42C for 60s")
    if over_40_5min >= 300:
        return _fail(">=40C for 5 minutes")
    return _ok("battery temp within thresholds")


def _check_charge_bypass_unproven(ev: Mapping[str, Any]) -> Tuple[str, str]:
    pct_drift = ev.get("battery_pct_drift_per_hour")
    if pct_drift is None:
        return _skipped("battery_pct_drift_per_hour missing")
    if pct_drift > 2.0:
        return _fail(f"battery SoC drift {pct_drift:.2f} pp/hr > 2pp/hr under bypass test")
    return _ok(f"battery SoC drift {pct_drift:.2f} pp/hr")


def _check_throughput_floor_fail(ev: Mapping[str, Any]) -> Tuple[str, str]:
    tph = ev.get("tokens_per_hour")
    if tph is None:
        return _skipped("tokens_per_hour missing")
    if tph < 100_000:
        return _fail(f"throughput {tph:,.0f} tokens/hour < 100K hard fail")
    if tph < 500_000:
        return _warn(f"throughput {tph:,.0f} tokens/hour < 500K preferred floor")
    return _ok(f"throughput {tph:,.0f} tokens/hour")


def _check_energy_budget_exceeded(ev: Mapping[str, Any]) -> Tuple[str, str]:
    j_per_token = ev.get("joules_per_token")
    baseline = ev.get("joules_per_token_baseline")
    quality_gain = ev.get("quality_gain_pct", 0.0)
    if j_per_token is None or baseline is None:
        return _skipped("joules_per_token or baseline missing")
    if baseline == 0:
        return _skipped("baseline=0 - cannot compute ratio")
    over = (j_per_token - baseline) / baseline
    if over > 0.20 and quality_gain <= 0:
        return _fail(f"joules/token {j_per_token:.4f} is {over*100:.1f}% over baseline with no quality gain")
    return _ok(f"joules/token {j_per_token:.4f} (delta {over*100:+.1f}% vs baseline)")


def _check_catastrophic_forgetting(ev: Mapping[str, Any]) -> Tuple[str, str]:
    en_drop_pp = ev.get("english_anchor_drop_pp")
    if en_drop_pp is None:
        return _skipped("english_anchor_drop_pp missing")
    if en_drop_pp > 1.0:
        return _fail(f"English anchor drop {en_drop_pp:.2f}pp > 1pp threshold")
    return _ok(f"English anchor drop {en_drop_pp:.2f}pp")


def _check_cross_model_disagreement_high(ev: Mapping[str, Any]) -> Tuple[str, str]:
    metric = ev.get("disagreement_metric")
    threshold = ev.get("disagreement_threshold", 0.30)
    if metric is None:
        return _skipped("disagreement_metric missing")
    if metric > threshold:
        return _warn(f"cross-model disagreement {metric:.3f} above threshold {threshold:.3f}")
    return _ok(f"cross-model disagreement {metric:.3f}")


def _check_method_disagreement_high(ev: Mapping[str, Any]) -> Tuple[str, str]:
    rho = ev.get("elo_qlora_spearman_rho")
    if rho is None:
        return _skipped("elo_qlora_spearman_rho missing")
    if rho < 0.6:
        return _warn(f"ELO vs QLoRA Spearman rho {rho:.3f} below 0.6")
    return _ok(f"ELO vs QLoRA Spearman rho {rho:.3f}")


def _check_license_drift(ev: Mapping[str, Any]) -> Tuple[str, str]:
    sources = ev.get("corpus_sources")
    if sources is None:
        return _skipped("corpus_sources missing")
    bad = [s for s in sources if not s.get("license_class") or s.get("license_class") in ("D", "E")]
    if bad:
        return _fail(f"{len(bad)} sources lack permissive license class: {[s.get('source_id') for s in bad[:5]]}")
    return _ok(f"{len(sources)} sources, all license-attested")


def _check_ocr_damage_high(ev: Mapping[str, Any]) -> Tuple[str, str]:
    score = ev.get("ocr_damage_score")
    threshold = ev.get("ocr_damage_threshold", 0.30)
    if score is None:
        return _skipped("ocr_damage_score missing")
    if score > threshold:
        return _fail(f"OCR damage {score:.3f} > {threshold:.3f}")
    return _ok(f"OCR damage {score:.3f}")


def _check_overclaim(ev: Mapping[str, Any]) -> Tuple[str, str]:
    unsupported = ev.get("unsupported_claims")
    if unsupported is None:
        return _skipped("unsupported_claims missing")
    if unsupported:
        return _fail(f"unsupported claims: {unsupported}")
    return _ok("no unsupported claims")


# ---------- fridge-mode falsifiers ----------


def _check_condensation_risk(ev: Mapping[str, Any]) -> Tuple[str, str]:
    """Trigger when the device is at risk of condensation - typically when
    the surface temperature is close to the dewpoint and the recent
    temperature trajectory is rising fast (fridge door opened, run ending).

    Evidence: ``{"surface_temp_c": float, "ambient_dewpoint_c": float,
              "rate_of_change_c_per_min": float}``.
    """
    surface = ev.get("surface_temp_c")
    dew = ev.get("ambient_dewpoint_c")
    rate = ev.get("rate_of_change_c_per_min")
    if surface is None or dew is None:
        return _skipped("surface_temp_c / ambient_dewpoint_c missing")
    margin = surface - dew
    if margin <= 0:
        return _fail(f"surface_temp_c {surface} <= dewpoint {dew} - condensation forming")
    if margin <= 2 and (rate is None or rate > 0.5):
        return _warn(f"margin {margin:.1f}C above dewpoint and rising at {rate} C/min")
    return _ok(f"margin {margin:.1f}C above dewpoint")


def _check_wifi_silent(ev: Mapping[str, Any]) -> Tuple[str, str]:
    """No successful HF / GitHub push in the last N minutes.

    Evidence: ``{"minutes_since_last_push": float, "threshold_minutes": float}``.
    """
    mins = ev.get("minutes_since_last_push")
    threshold = ev.get("threshold_minutes", 30)
    if mins is None:
        return _skipped("minutes_since_last_push missing")
    if mins > threshold:
        return _warn(f"no successful push in {mins:.1f} min (threshold {threshold} min)")
    return _ok(f"last push {mins:.1f} min ago")


def _check_fan_silent(ev: Mapping[str, Any]) -> Tuple[str, str]:
    """Active fan should be running for sustained training. Game Space mode
    keeps it on; if the user accidentally exited Game Space, the fan goes
    silent and thermal margin collapses.

    Evidence: ``{"fan_rpm": int|null, "fan_state": "running"|"silent"|"unknown"}``.
    """
    state = ev.get("fan_state")
    rpm = ev.get("fan_rpm")
    if state == "running":
        return _ok(f"fan running (rpm={rpm})")
    if state == "silent" or (rpm is not None and rpm == 0):
        return _fail("fan silent during sustained training - Game Space may have exited")
    return _skipped("fan_state / fan_rpm not reported")


def _check_screen_off_violation(ev: Mapping[str, Any]) -> Tuple[str, str]:
    """The wakelock should keep the runner alive even when the screen is
    off, but a screen-on transition mid-run usually means the operator
    interacted with the phone (door opened, etc.). Worth flagging as a
    warn so we know the run was disturbed.

    Evidence: ``{"screen_on_count": int, "since_minutes": float}``.
    """
    count = ev.get("screen_on_count")
    if count is None:
        return _skipped("screen_on_count missing")
    if count > 0:
        return _warn(f"screen_on observed {count} time(s) during run window")
    return _ok("screen stayed off for the run window")


# ---------- registry ----------


@dataclasses.dataclass(frozen=True)
class FalsifierEvaluator:
    falsifier_id: str
    description: str
    blocking_default: bool
    trigger_summary: str
    blocks: Tuple[str, ...]
    required_response: str
    check: CheckFn


FALSIFIERS: Dict[str, FalsifierEvaluator] = {}


def _register(*, falsifier_id, description, blocking_default, trigger_summary, blocks, required_response, check):
    FALSIFIERS[falsifier_id] = FalsifierEvaluator(
        falsifier_id=falsifier_id,
        description=description,
        blocking_default=blocking_default,
        trigger_summary=trigger_summary,
        blocks=tuple(blocks),
        required_response=required_response,
        check=check,
    )


_register(
    falsifier_id="boundary_violation",
    description="Artifact frames an out-of-scope use case or omits the boundary block.",
    blocking_default=True,
    trigger_summary="Boundary scanner reports MISSING / DRIFT / FORBIDDEN_FRAMING.",
    blocks=("publication", "upload", "phase_advancement"),
    required_response="Stop, quarantine artifact, emit retraction record, fix source.",
    check=_check_boundary_violation,
)

_register(
    falsifier_id="device_soc_mismatch",
    description="Probed SoC contradicts configured QNN target.",
    blocking_default=True,
    trigger_summary="soc_reported != soc_target",
    blocks=("qnn_compile", "acceleration_claim"),
    required_response="Re-probe, select correct target, or use fallback.",
    check=_check_device_soc_mismatch,
)

_register(
    falsifier_id="qnn_exact_path_unproven",
    description="No stored compile/delegate report for exact model graph scope.",
    blocking_default=True,
    trigger_summary="qnn_compile_records absent or all failed",
    blocks=("npu_claim", "phase1a_qnn_use"),
    required_response="Run export truth table or disable QNN.",
    check=_check_qnn_exact_path_unproven,
)

_register(
    falsifier_id="qnn_unsupported_op",
    description="LiteRT/QNN compile fails or delegate percentage below threshold.",
    blocking_default=True,
    trigger_summary="delegate_pct < threshold",
    blocks=("qnn_use_for_scope",),
    required_response="Store failing op, fallback, open issue.",
    check=_check_qnn_unsupported_op,
)

_register(
    falsifier_id="smollm3_export_unproven",
    description="SmolLM3 has no successful Experiment 2 record.",
    blocking_default=True,
    trigger_summary="experiment_2_status not pass",
    blocks=("smollm3_accelerated_training",),
    required_response="Mark eval-only or GPU/CPU-only.",
    check=_check_smollm3_export_unproven,
)

_register(
    falsifier_id="checkpoint_hash_mismatch",
    description="Checkpoint SHA does not match manifest.",
    blocking_default=True,
    trigger_summary="checkpoint_sha256 != manifest",
    blocks=("resume", "eval", "upload"),
    required_response="Quarantine checkpoint, roll back to previous hash-chain head.",
    check=_check_checkpoint_hash_mismatch,
)

_register(
    falsifier_id="tokenizer_fertility_high",
    description="Any core target language exceeds 2.5x English token-per-word ratio.",
    blocking_default=True,
    trigger_summary="ratio_vs_english > 2.5",
    blocks=("phase1a_corpus_lock",),
    required_response="Vocabulary extension, sampling adjustment, model swap, or operator-decision record.",
    check=_check_tokenizer_fertility_high,
)

_register(
    falsifier_id="oom_or_memory_pressure",
    description="Android process killed, OOM, or peak RAM above 22 GB.",
    blocking_default=True,
    trigger_summary="oom or peak_ram_gb >= 22",
    blocks=("device_run_scaleup",),
    required_response="Reduce batch/sequence, enable checkpointing, retry smoke.",
    check=_check_oom_or_memory_pressure,
)

_register(
    falsifier_id="thermal_throttle",
    description="GPU clock below 600 MHz for >10% of any 1-hour window.",
    blocking_default=True,
    trigger_summary="gpu_clock_below_600_pct > 0.10",
    blocks=("phase1a_multi_hour_run",),
    required_response="Enable fan/charge separation, reduce load, schedule rest, rerun calibration.",
    check=_check_thermal_throttle,
)

_register(
    falsifier_id="battery_heat_risk",
    description=">=42C for 60s or >=40C for 5 minutes.",
    blocking_default=True,
    trigger_summary="battery_temp_samples_c thresholds",
    blocks=("plugged_in_run_continuation",),
    required_response="Stop run, cool device, change charging regime.",
    check=_check_battery_heat_risk,
)

_register(
    falsifier_id="charge_bypass_unproven",
    description="Charge Separation not visible or SoC drifts more than 2pp/hour during bypass test.",
    blocking_default=True,
    trigger_summary="battery_pct_drift_per_hour > 2",
    blocks=("multi_day_run",),
    required_response="Use rest periods and stricter thermal gate, or postpone.",
    check=_check_charge_bypass_unproven,
)

_register(
    falsifier_id="throughput_floor_fail",
    description="2-hour micro-run under 500K tokens/hour equivalent, or under 100K hard fail.",
    blocking_default=True,
    trigger_summary="tokens_per_hour < 100K",
    blocks=("phase1a_timing_claim",),
    required_response="Debug data pipeline / backend overhead before corpus investment.",
    check=_check_throughput_floor_fail,
)

_register(
    falsifier_id="energy_budget_exceeded",
    description="Joules/token exceeds static baseline by >20% without quality gain.",
    blocking_default=True,
    trigger_summary="joules_per_token > 1.2 * baseline with no quality gain",
    blocks=("reflex_default", "multi_day_plan"),
    required_response="Revert scheduler or reduce load.",
    check=_check_energy_budget_exceeded,
)

_register(
    falsifier_id="catastrophic_forgetting",
    description="English held-out / MMLU-style drop > 1pp vs base.",
    blocking_default=True,
    trigger_summary="english_anchor_drop_pp > 1",
    blocks=("phase1b_advancement",),
    required_response="Increase replay, reduce LR, revise curriculum.",
    check=_check_catastrophic_forgetting,
)

_register(
    falsifier_id="cross_model_disagreement_high",
    description="Qwen vs SmolLM3 disagreement above threshold on matched eval.",
    blocking_default=False,
    trigger_summary="disagreement_metric > threshold",
    blocks=("quality_claim",),
    required_response="Flag for teacher-panel adjudication; do not claim stable improvement.",
    check=_check_cross_model_disagreement_high,
)

_register(
    falsifier_id="method_disagreement_high",
    description="ELO vs QLoRA improvement ranking Spearman rho < 0.6 on pilot slice.",
    blocking_default=False,
    trigger_summary="elo_qlora_spearman_rho < 0.6",
    blocks=("elo_superiority_claim",),
    required_response="Investigate corpus signal and method behavior.",
    check=_check_method_disagreement_high,
)

_register(
    falsifier_id="license_drift",
    description="Corpus chunk lacks explicit license class or source provenance.",
    blocking_default=True,
    trigger_summary="license_class missing or D/E",
    blocks=("training_on_chunk",),
    required_response="Remove chunk until attested.",
    check=_check_license_drift,
)

_register(
    falsifier_id="ocr_damage_high",
    description="Perplexity or OCR heuristic damage score above threshold.",
    blocking_default=True,
    trigger_summary="ocr_damage_score > threshold",
    blocks=("training_on_chunk",),
    required_response="Re-OCR, repair, or exclude.",
    check=_check_ocr_damage_high,
)

_register(
    falsifier_id="overclaim",
    description="Report makes a claim unsupported by run/eval artifacts.",
    blocking_default=True,
    trigger_summary="unsupported_claims non-empty",
    blocks=("report_publication",),
    required_response="Rewrite claim or produce evidence.",
    check=_check_overclaim,
)


def list_ids() -> List[str]:
    return list(FALSIFIERS.keys())


@dataclasses.dataclass(frozen=True)
class FalsifierResult:
    falsifier_id: str
    result: str  # pass | warn | fail | blocked | skipped
    detail: str
    blocking: bool


def evaluate(falsifier_id: str, evidence: Mapping[str, Any]) -> FalsifierResult:
    if falsifier_id not in FALSIFIERS:
        raise KeyError(f"unknown falsifier {falsifier_id!r}")
    f = FALSIFIERS[falsifier_id]
    result, detail = f.check(evidence)
    blocking = f.blocking_default and result in ("fail", "blocked")
    return FalsifierResult(falsifier_id=falsifier_id, result=result, detail=detail, blocking=blocking)


def summary_report(results: Sequence[FalsifierResult]) -> dict:
    counts = {"pass": 0, "warn": 0, "fail": 0, "blocked": 0, "skipped": 0}
    blocking_failures: List[str] = []
    for r in results:
        counts[r.result] = counts.get(r.result, 0) + 1
        if r.blocking and r.result in ("fail", "blocked"):
            blocking_failures.append(r.falsifier_id)
    overall = "pass"
    if blocking_failures:
        overall = "blocked"
    elif counts.get("fail", 0):
        overall = "fail"
    elif counts.get("warn", 0):
        overall = "warn"
    return {
        "counts": counts,
        "overall": overall,
        "blocking_failures": blocking_failures,
        "results": [
            {
                "falsifier_id": r.falsifier_id,
                "result": r.result,
                "detail": r.detail,
                "blocking": r.blocking,
            }
            for r in results
        ],
    }
