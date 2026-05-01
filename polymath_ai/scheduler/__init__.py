"""Reflex Scheduler.

PRD §Reflex Scheduler:
  Phase 0 implementation includes:
    * static placement policy
    * UCB or epsilon-greedy policy over op-shape and backend choices
    * latency / energy / thermal history table
    * config flag to force static
    * deterministic replay from audit

Phase 1A use:
  * static burn-in first
  * Reflex becomes default ONLY if micro-calibration shows
    tokens/hour or tokens/J improves >=5 % without thermal/quality
    regressions

Forked-and-owned from Energy Pipeline `l6/router.py + registry.py +
production_falsifiers.py + enforcement.py` per MODUS-OPERANDI fork-and-
own. No runtime co-dependency.
"""
from polymath_ai.scheduler.registry import (
    BackendCapability,
    BackendRecord,
    BackendRegistry,
    default_registry,
)
from polymath_ai.scheduler.history import (
    DispatchHistory,
    DispatchObservation,
)
from polymath_ai.scheduler.policy import (
    PolicyDecision,
    ReflexScheduler,
    SchedulerPolicy,
    static_policy,
    epsilon_greedy_policy,
    ucb_policy,
)

__all__ = [
    "BackendCapability",
    "BackendRecord",
    "BackendRegistry",
    "default_registry",
    "DispatchHistory",
    "DispatchObservation",
    "PolicyDecision",
    "ReflexScheduler",
    "SchedulerPolicy",
    "static_policy",
    "epsilon_greedy_policy",
    "ucb_policy",
]
