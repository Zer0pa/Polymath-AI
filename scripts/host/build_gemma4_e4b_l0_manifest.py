#!/usr/bin/env python3
"""Build the immutable Gemma 4 E4B L0 parent manifest without weight egress."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from polymath_ai.frontier.e4b_l0 import (  # noqa: E402
    HuggingFaceHubClient,
    build_default_l0_manifest,
)


DEFAULT_EDGE_A_PROTOCOL = {
    "template": "exact_repository_chat_template",
    "teacher_forced_objective": "full_answer_plus_turn_termination_masked_NLL",
    "decode": {
        "do_sample": False,
        "max_new_tokens": 64,
        "stop_token": "<turn|>",
        "seed": 0,
    },
    "length_buckets": [16, 64, 128],
    "evaluator": "token_weighted_nll_plus_deterministic_generation_behavior",
    "target_shift": "causal_next_token",
}


DEFAULT_REFERENCE_STACKS = {
    "qat_mobile_transformers": {
        "python": "3.11",
        "torch": "2.13.0",
        "transformers": "5.13.0",
        "accelerate": "1.14.0",
        "safetensors": "0.8.0",
        "artifact_revision_is_runtime_code_revision": True,
        "state": "identity_frozen_execution_unverified",
    },
    "qat_mobile_compressed_tensors": {
        "python": "3.11",
        "torch": "2.13.0",
        "transformers": "5.13.0",
        "accelerate": "1.14.0",
        "safetensors": "0.8.0",
        "compressed_tensors_artifact_declared_version": "0.16.1.dev7+g7087506.d20260602",
        "state": "identity_frozen_execution_unverified",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--provisional-build-source",
        choices=("none", "qat_mobile_transformers", "qat_mobile_compressed_tensors"),
        default="none",
    )
    parser.add_argument("--exporter-revision", required=True)
    parser.add_argument("--qairt-build", default="2.44.0.260225")
    parser.add_argument("--qnn-api-version", default="2.34.0")
    parser.add_argument("--target-soc-model", type=int, default=69)
    parser.add_argument("--target-dsp-arch", type=int, default=79)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    provisional = None if args.provisional_build_source == "none" else args.provisional_build_source
    converter_lineage = {
        "exporter_revision": args.exporter_revision,
        "converter_and_QAIRT_build": args.qairt_build,
        "QNN_API_version": args.qnn_api_version,
        "target_socModel": args.target_soc_model,
        "target_dspArch": args.target_dsp_arch,
    }
    payload = build_default_l0_manifest(
        HuggingFaceHubClient(),
        provisional_build_source=provisional,
        reference_stacks=DEFAULT_REFERENCE_STACKS,
        converter_lineage=converter_lineage,
        edge_a_protocol=DEFAULT_EDGE_A_PROTOCOL,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "manifest_sha256": payload["manifest_sha256"], "state": payload["manifest"]["state"]}, sort_keys=True))
    return 0 if payload["manifest"]["state"] == "passed_scope" else 2


if __name__ == "__main__":
    raise SystemExit(main())
