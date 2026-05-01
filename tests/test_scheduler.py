"""Reflex Scheduler tests."""
from __future__ import annotations

import pytest

from polymath_ai.scheduler import (
    BackendCapability,
    BackendRecord,
    BackendRegistry,
    DispatchHistory,
    DispatchObservation,
    PolicyDecision,
    ReflexScheduler,
    default_registry,
    epsilon_greedy_policy,
    static_policy,
    ucb_policy,
)


def _registry_with_three():
    reg = BackendRegistry()
    reg.register(
        BackendRecord(
            backend_id="cpu_a",
            family="cpu",
            capabilities=(BackendCapability.training_forward,),
            requires_phone=True,
        )
    )
    reg.register(
        BackendRecord(
            backend_id="gpu_a",
            family="gpu",
            capabilities=(BackendCapability.training_forward,),
            requires_phone=True,
        )
    )
    reg.register(
        BackendRecord(
            backend_id="npu_a",
            family="npu",
            capabilities=(BackendCapability.frozen_subgraph_inference,),
            requires_phone=True,
            confirmed_for_socs=(("SM8750", 1.0),),
        )
    )
    return reg


def test_default_registry_includes_required_backends():
    reg = default_registry()
    ids = {b.backend_id for b in reg.all()}
    assert {"mac_sim", "android_cpu", "vulkan_gpu", "litert_qnn_sm8750", "fallback_cpu"}.issubset(ids)


def test_qnn_backend_is_locked_until_proof():
    """litert_qnn_sm8750 starts with empty confirmed_for_socs - the
    scheduler refuses to route to it until Phase 0G adds (SM8750, 1.0).
    """
    reg = default_registry()
    qnn = reg.get("litert_qnn_sm8750")
    assert qnn.confirmed_for_socs == ()
    # Find with soc=SM8750 must NOT include qnn yet.
    matches = reg.find(soc="SM8750", capability=BackendCapability.frozen_subgraph_inference)
    assert "litert_qnn_sm8750" not in {m.backend_id for m in matches}


def test_history_running_mean_and_visit_count():
    h = DispatchHistory()
    h.record(DispatchObservation(recorded_at="t1", op_key="matmul_512", backend_id="cpu_a", latency_ms=20.0))
    h.record(DispatchObservation(recorded_at="t2", op_key="matmul_512", backend_id="cpu_a", latency_ms=22.0))
    h.record(DispatchObservation(recorded_at="t3", op_key="matmul_512", backend_id="gpu_a", latency_ms=8.0))
    assert h.visit_count("matmul_512", "cpu_a") == 2
    assert h.visit_count("matmul_512", "gpu_a") == 1
    assert h.total_visits("matmul_512") == 3
    assert abs(h.mean_latency("matmul_512", "cpu_a") - 21.0) < 1e-6
    assert h.mean_latency("matmul_512", "gpu_a") == 8.0


def test_history_persists_to_jsonl(tmp_path):
    p = tmp_path / "hist.jsonl"
    h = DispatchHistory(p)
    h.record(DispatchObservation(recorded_at="t1", op_key="op", backend_id="b1", latency_ms=10.0))
    h.record(DispatchObservation(recorded_at="t2", op_key="op", backend_id="b1", latency_ms=14.0))
    h2 = DispatchHistory.load(p)
    assert h2.visit_count("op", "b1") == 2
    assert abs(h2.mean_latency("op", "b1") - 12.0) < 1e-6


def test_static_policy_picks_first_eligible():
    reg = _registry_with_three()
    sched = ReflexScheduler(
        registry=reg,
        history=DispatchHistory(),
        policy=static_policy(preference=("gpu_a", "cpu_a", "npu_a")),
        soc="SM8750",
    )
    decision = sched.decide("matmul_512", BackendCapability.training_forward)
    # gpu_a is in preference and supports training_forward
    assert decision.backend_id == "gpu_a"


def test_static_policy_falls_back_when_preference_misses():
    reg = _registry_with_three()
    sched = ReflexScheduler(
        registry=reg,
        history=DispatchHistory(),
        policy=static_policy(preference=("nonexistent", "cpu_a")),
        soc="SM8750",
    )
    decision = sched.decide("matmul_512", BackendCapability.training_forward)
    assert decision.backend_id == "cpu_a"  # second in preference, eligible


def test_static_policy_qnn_blocked_by_soc_lock():
    """Even if QNN is in the preference list, the scheduler must NOT pick
    it for an op that would require it when the registry lock is set
    (litert_qnn_sm8750.confirmed_for_socs is empty by default).
    """
    reg = default_registry()
    sched = ReflexScheduler(
        registry=reg,
        history=DispatchHistory(),
        policy=static_policy(preference=("litert_qnn_sm8750", "vulkan_gpu", "android_cpu")),
        soc="SM8750",
    )
    decision = sched.decide("frozen_subgraph", BackendCapability.frozen_subgraph_inference)
    assert decision.backend_id != "litert_qnn_sm8750"
    # Will fall through to vulkan_gpu (which supports frozen_subgraph_inference).
    assert decision.backend_id == "vulkan_gpu"


def test_epsilon_greedy_explores_then_exploits():
    reg = _registry_with_three()
    h = DispatchHistory()
    h.record(DispatchObservation(recorded_at="t1", op_key="op", backend_id="cpu_a", latency_ms=20.0))
    h.record(DispatchObservation(recorded_at="t2", op_key="op", backend_id="gpu_a", latency_ms=5.0))

    sched = ReflexScheduler(
        registry=reg,
        history=h,
        policy=epsilon_greedy_policy(epsilon=0.0, seed=0),  # pure exploit
        soc="SM8750",
    )
    decision = sched.decide("op", BackendCapability.training_forward)
    assert decision.backend_id == "gpu_a"  # lower mean latency

    # With epsilon=1.0 always explore - over many calls visits both arms.
    sched2 = ReflexScheduler(
        registry=reg,
        history=h,
        policy=epsilon_greedy_policy(epsilon=1.0, seed=42),
        soc="SM8750",
    )
    seen = set()
    for _ in range(50):
        seen.add(sched2.decide("op", BackendCapability.training_forward).backend_id)
    assert seen == {"cpu_a", "gpu_a"}  # only the two with capability


def test_ucb_policy_force_visits_untouched_arms_first():
    reg = _registry_with_three()
    h = DispatchHistory()
    sched = ReflexScheduler(
        registry=reg,
        history=h,
        policy=ucb_policy(c=1.4),
        soc="SM8750",
    )
    decision = sched.decide("op", BackendCapability.training_forward)
    assert decision.arm_n == 0
    assert "force-visit" in decision.rationale


def test_ucb_then_records_observation_and_revisits():
    reg = _registry_with_three()
    h = DispatchHistory()
    sched = ReflexScheduler(
        registry=reg,
        history=h,
        policy=ucb_policy(c=1.4),
        soc="SM8750",
    )
    # First three calls force-visit each arm.
    chosen_ids = []
    for _ in range(3):
        d = sched.decide("op", BackendCapability.training_forward)
        h.record(
            DispatchObservation(
                recorded_at=f"t{len(chosen_ids)}",
                op_key="op",
                backend_id=d.backend_id,
                latency_ms={"cpu_a": 50.0, "gpu_a": 10.0}.get(d.backend_id, 100.0),
            )
        )
        chosen_ids.append(d.backend_id)
    assert set(chosen_ids) == {"cpu_a", "gpu_a"}  # only two have the capability
    # After visiting both, exploit gpu_a (lower mean).
    d = sched.decide("op", BackendCapability.training_forward)
    assert d.backend_id == "gpu_a"
