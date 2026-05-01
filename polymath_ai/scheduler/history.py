"""Per-(op_shape, backend) latency / energy / thermal history.

The history table powers UCB and epsilon-greedy decisions. Append-only
JSONL on disk so the scheduler is replayable from the audit log.
"""
from __future__ import annotations

import dataclasses
import json
import math
import os
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

from polymath_ai._version import SCHEMA_VERSION
from polymath_ai.boundary.text import boundary_envelope
from polymath_ai.utils.canonical import canonical_json, utc_now_iso


@dataclasses.dataclass(frozen=True)
class DispatchObservation:
    """One observation: backend B ran op O of shape S in T ms at E mJ.

    ``op_key`` is the canonical key constructed from op class + shape
    descriptor (e.g. ``"matmul_512x1536x1536"``). The scheduler indexes
    its history by ``(op_key, backend_id)`` so different shapes have
    independent histories.
    """

    recorded_at: str
    op_key: str
    backend_id: str
    latency_ms: float
    energy_mj: Optional[float] = None
    success: bool = True
    notes: str = ""


class DispatchHistory:
    """In-memory per-(op_key, backend_id) summary plus optional JSONL
    persistence.

    Summary fields per arm:
      n           = visit count
      mean_lat    = running mean latency (ms)
      m2_lat      = sum of squared deviations (Welford)
      success_n   = number of successful runs
      last_seen   = last recorded_at
    """

    def __init__(self, jsonl_path: Optional[Path] = None) -> None:
        self.jsonl_path = jsonl_path
        # arms[op_key][backend_id] -> dict of stats
        self.arms: Dict[str, Dict[str, dict]] = {}

    def record(self, obs: DispatchObservation) -> None:
        arm = self.arms.setdefault(obs.op_key, {}).setdefault(
            obs.backend_id,
            {"n": 0, "mean_lat": 0.0, "m2_lat": 0.0, "success_n": 0, "last_seen": ""},
        )
        n = arm["n"] + 1
        delta = obs.latency_ms - arm["mean_lat"]
        arm["mean_lat"] += delta / n
        delta2 = obs.latency_ms - arm["mean_lat"]
        arm["m2_lat"] += delta * delta2
        arm["n"] = n
        if obs.success:
            arm["success_n"] += 1
        arm["last_seen"] = obs.recorded_at

        if self.jsonl_path:
            self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.jsonl_path, "a", encoding="utf-8") as f:
                row = {
                    "schema_version": SCHEMA_VERSION,
                    "boundary": boundary_envelope(),
                    **dataclasses.asdict(obs),
                }
                f.write(canonical_json(row) + "\n")

    def std_lat(self, op_key: str, backend_id: str) -> float:
        arm = self.arms.get(op_key, {}).get(backend_id)
        if arm is None or arm["n"] < 2:
            return float("inf")
        return math.sqrt(arm["m2_lat"] / (arm["n"] - 1))

    def visit_count(self, op_key: str, backend_id: str) -> int:
        return self.arms.get(op_key, {}).get(backend_id, {}).get("n", 0)

    def total_visits(self, op_key: str) -> int:
        return sum(a["n"] for a in self.arms.get(op_key, {}).values())

    def mean_latency(self, op_key: str, backend_id: str) -> Optional[float]:
        arm = self.arms.get(op_key, {}).get(backend_id)
        return arm["mean_lat"] if arm else None

    def success_rate(self, op_key: str, backend_id: str) -> Optional[float]:
        arm = self.arms.get(op_key, {}).get(backend_id)
        if not arm or arm["n"] == 0:
            return None
        return arm["success_n"] / arm["n"]

    @classmethod
    def load(cls, jsonl_path: str | os.PathLike[str]) -> "DispatchHistory":
        history = cls(Path(jsonl_path))
        p = Path(jsonl_path)
        if not p.exists():
            return history
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                obs = DispatchObservation(
                    recorded_at=row["recorded_at"],
                    op_key=row["op_key"],
                    backend_id=row["backend_id"],
                    latency_ms=row["latency_ms"],
                    energy_mj=row.get("energy_mj"),
                    success=row.get("success", True),
                    notes=row.get("notes", ""),
                )
                # record but skip the persistence pass (would double-write)
                arm = history.arms.setdefault(obs.op_key, {}).setdefault(
                    obs.backend_id,
                    {"n": 0, "mean_lat": 0.0, "m2_lat": 0.0, "success_n": 0, "last_seen": ""},
                )
                n = arm["n"] + 1
                delta = obs.latency_ms - arm["mean_lat"]
                arm["mean_lat"] += delta / n
                delta2 = obs.latency_ms - arm["mean_lat"]
                arm["m2_lat"] += delta * delta2
                arm["n"] = n
                if obs.success:
                    arm["success_n"] += 1
                arm["last_seen"] = obs.recorded_at
        return history
