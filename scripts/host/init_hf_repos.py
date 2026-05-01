#!/usr/bin/env python3
"""Initialise the private HF repos with READMEs that carry the boundary
block, license attestation, and a pointer to PRD.md.

Idempotent. Safe to re-run.

Repo plan (Decision D-008, PRD §Required GitHub/HF Review Surface):
* `Architect-Prime/polymath-corpus-seed-v0`        - dataset, private
* `Architect-Prime/polymath-models-qwen2-5-1p5b-elo` - model, private
* `Architect-Prime/polymath-models-smollm3-3b-elo`   - model, private
* `Architect-Prime/polymath-telemetry`             - dataset, private (logs / traces)
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from polymath_ai.boundary.text import BOUNDARY_TEXT


REPOS = [
    {
        "repo_id": "Architect-Prime/polymath-corpus-seed-v0",
        "repo_type": "dataset",
        "title": "Polymath Seed Corpus v0",
        "purpose": (
            "Multilingual / multi-domain corpus shards for Polymath ELO Stage 1 "
            "training. License-clean (class A and B per docs/CORPUS-SPEC.md). "
            "Sources are decomposed into per-source license attestations in "
            "`manifests/`."
        ),
    },
    {
        "repo_id": "Architect-Prime/polymath-models-qwen2-5-1p5b-elo",
        "repo_type": "model",
        "title": "Polymath ELO Stage 1 / Stage 2 — Qwen2.5-1.5B base",
        "purpose": (
            "Boundary-layer ELO Stage 1 checkpoints, Stage 2 alignment "
            "checkpoints, and Phase 1A merged artifacts derived from "
            "Qwen/Qwen2.5-1.5B (Apache 2.0). Base model attestation: "
            "`license:apache-2.0:qwen2.5-1.5b`."
        ),
    },
    {
        "repo_id": "Architect-Prime/polymath-models-smollm3-3b-elo",
        "repo_type": "model",
        "title": "Polymath ELO Candidate B — SmolLM3-3B base",
        "purpose": (
            "Boundary-layer ELO Stage 1 checkpoints derived from "
            "HuggingFaceTB/SmolLM3-3B (Apache 2.0). Acceleration path "
            "is contingent on Phase 0G / Experiment 2 verdict. Base "
            "model attestation: `license:apache-2.0:smollm3-3b`."
        ),
    },
    {
        "repo_id": "Architect-Prime/polymath-telemetry",
        "repo_type": "dataset",
        "title": "Polymath telemetry, profiler traces, eval reports",
        "purpose": (
            "Bulk run artifacts: per-step train logs, profiler traces, eval "
            "tuples, teacher-panel judgments. Mirrors of GitHub-tracked "
            "small JSONL where size demands HF storage."
        ),
    },
]


README_TEMPLATE = """\
# {title}

Boundary: {boundary}

## Purpose

{purpose}

## Provenance

* Workstream: [Zer0pa/Polymath-AI](https://github.com/Zer0pa/Polymath-AI)
* PRD: see `PRD.md` in the repo above.
* Modus operandi: see `MODUS-OPERANDI.md`.
* Decision log: see `docs/DECISIONS.md`.

## License

This artifact set is generated under the boundary above. Base-model and
base-corpus license attestations are recorded per artifact in their
manifests; this repo never carries derivative weights without explicit
attestation. No public release of weights or corpus shards is permitted
without operator review and a falsifier-traced acceptance gate.

## Visibility

Private. Audience: Architect-Prime + reviewers explicitly granted access
by the operator.
"""


def main():
    from huggingface_hub import HfApi, upload_file

    api = HfApi()
    for r in REPOS:
        body = README_TEMPLATE.format(
            title=r["title"],
            boundary=BOUNDARY_TEXT,
            purpose=r["purpose"],
        )
        out = ROOT / "runtime" / "hf_readmes" / r["repo_id"].replace("/", "_")
        out.mkdir(parents=True, exist_ok=True)
        readme_local = out / "README.md"
        readme_local.write_text(body)
        try:
            upload_file(
                path_or_fileobj=str(readme_local),
                path_in_repo="README.md",
                repo_id=r["repo_id"],
                repo_type=r["repo_type"],
                commit_message="polymath bootstrap: boundary-bearing README",
            )
            print(f"OK   {r['repo_type']:7s} {r['repo_id']}")
        except Exception as e:
            print(f"FAIL {r['repo_type']:7s} {r['repo_id']} -> {e!r}")


if __name__ == "__main__":
    main()
