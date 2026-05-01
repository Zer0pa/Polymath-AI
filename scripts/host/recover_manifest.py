#!/usr/bin/env python3
"""Reconstruct a missing checkpoint manifest.json from the saved
``trainable.pt`` + ``optimizer.pt`` files.

Used after a kill or crash that left the .pt files on disk but never
wrote manifest.json. The manifest is the canonical metadata record; the
.pt files are usable for resume only with a manifest beside them.

Usage:
    .venv/bin/python scripts/host/recover_manifest.py \
        --ckpt-dir runtime/reports/qwen_elo_smoke/<ts>/ckpt-0 \
        --run-id "run:<ts>:qwen-elo-smoke" \
        --base-model-pointer "Qwen/Qwen2.5-1.5B@main" \
        --license-attestation-id "license:apache-2.0:qwen2.5-1.5b" \
        --step <step_count> \
        --tokens-seen <tokens>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from polymath_ai._version import SCHEMA_VERSION
from polymath_ai.boundary.text import boundary_envelope
from polymath_ai.elo.trainer import _hash_tensor_into
from polymath_ai.utils.canonical import canonical_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ckpt-dir", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--checkpoint-kind", default="stage1_boundary")
    parser.add_argument("--model-id", default="Qwen/Qwen2.5-1.5B")
    parser.add_argument("--config-sha256", default="sha256:recovered")
    parser.add_argument("--corpus-slice-id", default=None)
    parser.add_argument("--base-model-pointer", required=True)
    parser.add_argument("--license-attestation-id", default=None)
    parser.add_argument("--step", type=int, required=True)
    parser.add_argument("--tokens-seen", type=int, required=True)
    parser.add_argument("--policy", default="elo_first_last")
    args = parser.parse_args()

    import torch

    ckpt = Path(args.ckpt_dir)
    trainable_path = ckpt / "trainable.pt"
    optimizer_path = ckpt / "optimizer.pt"
    if not (trainable_path.exists() and optimizer_path.exists()):
        print(f"FATAL: trainable.pt + optimizer.pt must both exist in {ckpt}")
        sys.exit(2)

    trainable_state = torch.load(trainable_path, map_location="cpu")
    print(f"loaded trainable.pt: {len(trainable_state)} tensors")

    h = hashlib.sha256()
    for n in sorted(trainable_state.keys()):
        h.update(n.encode("utf-8"))
        h.update(b":")
        _hash_tensor_into(h, trainable_state[n])
        h.update(b"\n")
    ckpt_sha = "sha256:" + h.hexdigest()
    print(f"checkpoint_sha256 = {ckpt_sha}")

    optimizer_state = torch.load(optimizer_path, map_location="cpu")
    optimizer_state_keys = sorted(optimizer_state.keys()) if isinstance(optimizer_state, dict) else []

    # Frozen-hash sample is unavailable (we don't have the model in memory);
    # reconstructed manifest records this with an explicit placeholder so
    # downstream readers can tell this manifest was recovered, not built
    # from a live training context.
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "boundary": boundary_envelope(),
        "run_id": args.run_id,
        "checkpoint_kind": args.checkpoint_kind,
        "model_id": args.model_id,
        "checkpoint_sha256": ckpt_sha,
        "trainable_param_names": sorted(trainable_state.keys()),
        "frozen_param_hash_sample": {"_recovered_offline": "frozen-hash-sample-unavailable"},
        "optimizer_state_keys": optimizer_state_keys,
        "step": args.step,
        "tokens_seen": args.tokens_seen,
        "config_sha256": args.config_sha256,
        "corpus_slice_id": args.corpus_slice_id,
        "base_model_pointer": args.base_model_pointer,
        "license_attestation_id": args.license_attestation_id,
        "hf_repo_id": None,
        "hf_path": None,
        "local_path": str(ckpt),
        "freeze_plan": {
            "policy_name": args.policy,
            "trainable_layer_indices": [0, 27],  # Qwen2.5-1.5B default
            "freeze_embeddings": True,
            "train_lm_head": True,
        },
        "_recovered_offline": True,
    }
    (ckpt / "manifest.json").write_text(canonical_json(manifest))
    print(f"wrote {ckpt / 'manifest.json'}")
    print(f"  step={args.step} tokens_seen={args.tokens_seen}")
    print(f"  checkpoint_sha256={ckpt_sha}")


if __name__ == "__main__":
    main()
