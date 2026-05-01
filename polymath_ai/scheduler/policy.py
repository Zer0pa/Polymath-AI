"""Reflex Scheduler policies + the scheduler itself.

Static policy:
  Pick a backend per op_key from a hard-coded preference list. PRD §Reflex
  Scheduler default for Phase 1A burn-in.

Epsilon-greedy:
  With probability ``epsilon`` pick a random *eligible* backend; otherwise
  pick the one with the lowest mean latency. Deterministic given the seed.

UCB-1:
  Lower-confidence-bound on latency (we minimise) per the standard
  bandit form: choose argmin over eligible backends of
    mean_lat - C * sqrt(2 ln total_n / arm_n)
  Visiting an arm few times pulls its bound down, encouraging exploration.

Eligibility:
  A backend is eligible for an op only if its ``capabilities`` cover the
  op's required capability AND, when it's a phone-side backend, the
  current device SoC is in its confirmed_for_socs list at confidence 1.0.
  This keeps the QNN gate in scheduler hands as well as falsifier hands.
"""
from __future__ import annotations

import dataclasses
import math
import random
from typing import Callable, Iterable, List, Mapping, Optional, Sequence, Tuple

from polymath_ai.scheduler.history import DispatchHistory
from polymath_ai.scheduler.registry import (
    BackendCapability,
    BackendRecord,
    BackendRegistry,
)


@dataclasses.dataclass(frozen=True)
class PolicyDecision:
    op_key: str
    backend_id: str
    rationale: str
    eligible_backends: Tuple[str, ...]
    arm_n: int
    arm_mean_lat: Optional[float]
    fallback_used: bool = False


SchedulerPolicy = Callable[
    ["ReflexScheduler", str, BackendCapability, Sequence[BackendRecord]],
    PolicyDecision,
]


def _eligible(
    registry: BackendRegistry,
    capability: BackendCapability,
    *,
    soc: Optional[str],
    require_phone: Optional[bool],
) -> List[BackendRecord]:
    out = []
    for r in registry.all():
        if not r.supports(capability):
            continue
        if require_phone is not None and r.requires_phone != require_phone:
            continue
        if r.requires_phone and soc is not None:
            # SoC-confirmation gate: NPU AOT and any other backend that
            # produces SoC-specific binaries needs explicit (soc, 1.0).
            if not r.is_routable_on(soc, 1.0):
                continue
        out.append(r)
    return out


def static_policy(
    preference: Tuple[str, ...] = (
        "android_cpu",
        "vulkan_gpu",
        "litert_qnn_sm8750",
        "fallback_cpu",
        "mac_sim",
    ),
) -> SchedulerPolicy:
    """Pick the first record from ``preference`` whose backend_id is in
    the eligible set. Used during Phase 1A static burn-in.
    """

    def decide(scheduler, op_key, capability, eligible):
        eligible_ids = {b.backend_id for b in eligible}
        for bid in preference:
            if bid in eligible_ids:
                arm_n = scheduler.history.visit_count(op_key, bid)
                arm_mean = scheduler.history.mean_latency(op_key, bid)
                return PolicyDecision(
                    op_key=op_key,
                    backend_id=bid,
                    rationale=f"static preference order picked {bid}",
                    eligible_backends=tuple(eligible_ids),
                    arm_n=arm_n,
                    arm_mean_lat=arm_mean,
                )
        # No eligible backend in the preference list.
        if eligible:
            chosen = eligible[0].backend_id
            return PolicyDecision(
                op_key=op_key,
                backend_id=chosen,
                rationale=f"static preference exhausted, fell back to first eligible {chosen}",
                eligible_backends=tuple(eligible_ids),
                arm_n=scheduler.history.visit_count(op_key, chosen),
                arm_mean_lat=scheduler.history.mean_latency(op_key, chosen),
                fallback_used=True,
            )
        raise ValueError(f"no eligible backend for {op_key} / {capability.value}")

    return decide


def epsilon_greedy_policy(epsilon: float = 0.1, seed: int = 0) -> SchedulerPolicy:
    rng = random.Random(seed)

    def decide(scheduler, op_key, capability, eligible):
        eligible_ids = tuple(b.backend_id for b in eligible)
        if not eligible_ids:
            raise ValueError(f"no eligible backend for {op_key}")
        if rng.random() < epsilon:
            chosen = rng.choice(eligible_ids)
            return PolicyDecision(
                op_key=op_key,
                backend_id=chosen,
                rationale=f"epsilon-greedy explored {chosen} (epsilon={epsilon})",
                eligible_backends=eligible_ids,
                arm_n=scheduler.history.visit_count(op_key, chosen),
                arm_mean_lat=scheduler.history.mean_latency(op_key, chosen),
            )
        # Exploit: argmin mean latency. Untouched arms have None -> treat as
        # +inf so they get visited at least once via the explore branch.
        ranked = []
        for bid in eligible_ids:
            mean = scheduler.history.mean_latency(op_key, bid)
            ranked.append((mean if mean is not None else float("inf"), bid))
        ranked.sort()
        chosen = ranked[0][1]
        return PolicyDecision(
            op_key=op_key,
            backend_id=chosen,
            rationale=f"epsilon-greedy exploited {chosen} (mean={ranked[0][0]})",
            eligible_backends=eligible_ids,
            arm_n=scheduler.history.visit_count(op_key, chosen),
            arm_mean_lat=ranked[0][0] if ranked[0][0] != float("inf") else None,
        )

    return decide


def ucb_policy(c: float = 1.4) -> SchedulerPolicy:
    """UCB-1 minimising latency.

    Score = mean_lat - c * sqrt(2 ln total / n_arm) — lowest score wins.
    Untouched arms receive priority.
    """

    def decide(scheduler, op_key, capability, eligible):
        eligible_ids = tuple(b.backend_id for b in eligible)
        if not eligible_ids:
            raise ValueError(f"no eligible backend for {op_key}")
        # Force-visit untouched arms first.
        for bid in eligible_ids:
            if scheduler.history.visit_count(op_key, bid) == 0:
                return PolicyDecision(
                    op_key=op_key,
                    backend_id=bid,
                    rationale=f"UCB force-visit untouched arm {bid}",
                    eligible_backends=eligible_ids,
                    arm_n=0,
                    arm_mean_lat=None,
                )
        total = scheduler.history.total_visits(op_key)
        ranked = []
        for bid in eligible_ids:
            n_arm = scheduler.history.visit_count(op_key, bid)
            mean = scheduler.history.mean_latency(op_key, bid) or 0.0
            bonus = c * math.sqrt(2 * math.log(max(total, 2)) / n_arm)
            score = mean - bonus
            ranked.append((score, bid, mean, n_arm))
        ranked.sort()
        score, chosen, mean, n_arm = ranked[0]
        return PolicyDecision(
            op_key=op_key,
            backend_id=chosen,
            rationale=f"UCB {chosen} score={score:.3f} (mean={mean:.3f}, n={n_arm})",
            eligible_backends=eligible_ids,
            arm_n=n_arm,
            arm_mean_lat=mean,
        )

    return decide


@dataclasses.dataclass
class ReflexScheduler:
    """Reflex Scheduler.

    Initialise with a registry, a history (in-memory or backed by JSONL),
    a policy, and the current device SoC (used for eligibility on
    phone-side backends).

    ``decide(op_key, capability)`` returns a ``PolicyDecision``. After the
    op runs, the caller emits a ``DispatchObservation`` and the scheduler
    updates its history.
    """

    registry: BackendRegistry
    history: DispatchHistory
    policy: SchedulerPolicy
    soc: Optional[str] = None
    require_phone: Optional[bool] = None

    def decide(self, op_key: str, capability: BackendCapability) -> PolicyDecision:
        eligible = _eligible(
            self.registry,
            capability,
            soc=self.soc,
            require_phone=self.require_phone,
        )
        return self.policy(self, op_key, capability, eligible)
