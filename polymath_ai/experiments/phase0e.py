"""Phase 0E - Experiment 0: stack fit + baseline throughput.

Runs only on the actual REDMAGIC. Host-side path produces a *plan* envelope
that the on-device runner consumes. Plan shape (PRD §Phase 0E):

    E0.1: 10K  tokens, seq 128, batch 1
    E0.2: 100K tokens, seq 256, batch 1-2
    E0.3: 1M   tokens, seq 512, batch 2-4
    E0.4: 2h sustained, seq 512, batch max stable

Each step writes:
  * train_step events to the audit log
  * a checkpoint at end-of-step
  * a falsifier evaluation against `oom_or_memory_pressure`,
    `thermal_throttle`, `throughput_floor_fail`, `battery_heat_risk`,
    `charge_bypass_unproven`

Acceptance: every falsifier passes (or is `skipped` with a documented
reason that does not block).
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Mapping

from polymath_ai.audit.chain import AuditWriter
from polymath_ai.falsifiers import evaluate, summary_report


def run(*, config: Mapping[str, Any], run_id: str, run_dir: Path, audit: AuditWriter) -> int:
    audit.append(event_type="phase_gate", payload={"gate": "phase0e_started", "config": dict(config)})

    if not config.get("phone_attached"):
        audit.append(
            event_type="falsifier",
            payload={
                "falsifier_id": "phone_not_attached",
                "result": "blocked",
                "detail": "Phase 0E requires phone_attached=true; skip on host.",
                "blocking": True,
            },
        )
        return 10

    # On-device runner path. The host stub does not implement real training;
    # the device-side runner overrides this module via the Termux deploy step
    # OR the host-mediated training harness (see Decision D-010) is invoked.
    audit.append(
        event_type="phase_gate",
        payload={
            "gate": "phase0e_pending_device_runner",
            "detail": "device-side runner not deployed in this checkout",
        },
    )
    return 11
