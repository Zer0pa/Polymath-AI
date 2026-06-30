#!/usr/bin/env python3
"""Stage a bounded PJP1-derived HTP ReLU input tensor on the phone."""

from __future__ import annotations

import argparse
from array import array
import hashlib
import json
from pathlib import Path
from typing import Any

from polymath_ai.polar.metrics_contract import metric_report
from polymath_ai.polar.pjp1 import (
    PJP1_EMBED_DIM,
    PJP1_JL_DIM,
    PJP1_POLAR_BYTES,
    PJP1_PACKET_LEN,
    inspect_pjp1,
)


DEFAULT_OUTPUT_ROOT = "/data/local/tmp/polymath_phase34/active_wave/pjp1_htp_relu_input"
DEFAULT_REPORT_NAME = "phase34_pjp1_htp_relu_input_stage.json"
DEFAULT_TOKENS = 16


def main() -> int:
    args = parse_args()
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    contract = inspect_pjp1(args.pjp1, metadata_samples=2)
    if contract.validation["status"] != "pass":
        write_report(
            output_root / args.report_name,
            {
                "schema_version": "polar_phase34_pjp1_htp_relu_input_stage_v1",
                "status": "fail",
                "phase3_ready_claim": False,
                "blockers": contract.validation["blockers"],
                "pjp1": contract.to_dict(),
            },
        )
        return 1

    token_count = validate_token_count(args.tokens)
    packet_index = validate_packet_index(args.packet_index, contract.packet_count)
    contract_dict = contract.to_dict()
    input_polar = read_polar_packet(Path(args.pjp1), contract_dict, packet_index, "input_polar")
    target_polar = read_polar_packet(Path(args.pjp1), contract_dict, packet_index, "target_polar")
    tensor = polar_packet_to_hidden_tensor(input_polar, token_count=token_count)
    target_tensor = polar_packet_to_hidden_tensor(target_polar, token_count=token_count)
    expected_relu = relu_tensor(tensor)

    input_path = output_root / f"pjp1_packet{packet_index}_tokens{token_count}_gemma_hidden.f32.bin"
    input_path.write_bytes(tensor.tobytes())
    target_path = output_root / f"pjp1_packet{packet_index}_tokens{token_count}_phase4_target.f32.bin"
    target_path.write_bytes(target_tensor.tobytes())
    input_list_path = output_root / "input_list.txt"
    input_list_path.write_text(input_path.name + "\n", encoding="utf-8")

    report = {
        "schema_version": "polar_phase34_pjp1_htp_relu_input_stage_v1",
        "status": "pass",
        "phase3_ready_claim": False,
        "phase4_ready_claim": False,
        "learning_claim": False,
        "authority_material": args.authority_material,
        "nonclaims": [
            "This stages a bounded derived HTP input only.",
            "This does not execute QNN/HTP.",
            "This does not consume HTP output.",
            "This is not Phase 3 readiness.",
            "This is not a real-corpus authority gate.",
            "This does not authorize C1-C4 execution.",
        ],
        "pjp1": {
            "path": contract.path,
            "bytes": contract.bytes,
            "sha256": contract.sha256,
            "packet_count": contract.packet_count,
            "packet_len": contract.packet_len,
            "jl_dim": contract.jl_dim,
            "embedding_dim": contract.embedding_dim,
            "source_record_count": contract.source_record_count,
            "source_real_token_count": contract.source_real_token_count,
            "projection_label": contract.projection_label,
        },
        "source_packet": {
            "packet_index": packet_index,
            "tokens_used": token_count,
            "source_section": "input_polar",
            "source_bytes_read": token_count * (PJP1_JL_DIM // 8),
            "target_section": "target_polar",
            "target_bytes_read": token_count * (PJP1_JL_DIM // 8),
            "bit_order": "lsb_first",
        },
        "bridge": {
            "name": "phase34_pjp1_polar_to_gemma_hidden_relu_bridge_v1",
            "rule": "hidden[h] = +1.0 if input_polar[token,h%256] bit is 1 else -1.0",
            "shape": [1, token_count, PJP1_EMBED_DIM],
            "dtype": "float32_le",
            "hidden_dim": PJP1_EMBED_DIM,
            "polar_dim": PJP1_JL_DIM,
            "repeat_factor": PJP1_EMBED_DIM // PJP1_JL_DIM,
        },
        "outputs": {
            "remote_input_path": str(input_path),
            "remote_input_list": str(input_list_path),
            "remote_phase4_target_path": str(target_path),
            "input_bytes": input_path.stat().st_size,
            "input_sha256": sha256_bytes(tensor.tobytes()),
            "phase4_target_bytes": target_path.stat().st_size,
            "phase4_target_sha256": sha256_bytes(target_tensor.tobytes()),
            "expected_relu_output_bytes": len(expected_relu.tobytes()),
            "expected_relu_output_sha256": sha256_bytes(expected_relu.tobytes()),
            "expected_positive_count": count_positive(expected_relu),
            "expected_zero_count": len(expected_relu) - count_positive(expected_relu),
        },
        "phase3_metrics": build_phase3_staging_metrics(
            args=args,
            contract=contract,
            token_count=token_count,
            expected_relu=expected_relu,
        ),
        "phase4_accepted_input_surface": {
            "cell_id": "phase4_opencl_phase3_bridge_rank16_mse_sgd_cell_v0",
            "phase3_output_expected_shape": [1, token_count, PJP1_EMBED_DIM],
            "phase3_output_expected_dtype": "float32_le",
            "target_shape": [1, token_count, PJP1_EMBED_DIM],
            "target_dtype": "float32_le",
            "adapter_rank": 16,
            "optimizer": "sgd",
            "objective": "bounded MSE between Phase 3 HTP output and PJP1 target-derived tensor",
            "authority": "mechanical_consumed_output_and_gpu_update_surface_only",
        },
        "raw_payload_rules": {
            "raw_pjp1_copied": False,
            "raw_pjp1_pulled_to_host": False,
            "derived_tensor_storage": classify_storage_root(output_root),
            "derived_tensor_staging_root": str(output_root),
            "repo_may_record_hashes_only": True,
        },
        "next_required_for_phase3": [
            "Run qnn-net-run on the derived tensor with the declared context/backend.",
            "Verify HTP output hash against expected_relu_output_sha256 without pulling raw output to repo.",
            "Consume the HTP output through a named route/objective/teacher/state transition.",
        ],
    }
    write_report(output_root / args.report_name, report)
    print(output_root / args.report_name)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pjp1", required=True)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report-name", default=DEFAULT_REPORT_NAME)
    parser.add_argument("--packet-index", type=int, default=0)
    parser.add_argument("--tokens", type=int, default=DEFAULT_TOKENS)
    parser.add_argument("--authority-material", default="diagnostic_or_preflight_only")
    parser.add_argument("--corpus-phase", default="C1", help="Metric namespace corpus phase, e.g. C1, C2, C2.5, C3, C4.")
    return parser.parse_args()


def validate_token_count(tokens: int) -> int:
    if tokens <= 0 or tokens > PJP1_PACKET_LEN:
        raise ValueError(f"tokens must be in [1,{PJP1_PACKET_LEN}], got {tokens}")
    return tokens


def validate_packet_index(packet_index: int, packet_count: int) -> int:
    if packet_index < 0 or packet_index >= packet_count:
        raise ValueError(f"packet_index must be in [0,{packet_count}), got {packet_index}")
    return packet_index


def read_polar_packet(
    pjp1_path: Path, contract: dict[str, Any], packet_index: int, section_name: str
) -> bytes:
    section = next(section for section in contract["sections"] if section["name"] == section_name)
    offset = section["offset"] + packet_index * PJP1_POLAR_BYTES
    with pjp1_path.open("rb") as handle:
        handle.seek(offset)
        packet = handle.read(PJP1_POLAR_BYTES)
    if len(packet) != PJP1_POLAR_BYTES:
        raise ValueError(f"truncated {section_name} packet")
    return packet


def polar_packet_to_hidden_tensor(input_polar: bytes, *, token_count: int) -> array:
    values = array("f")
    bytes_per_token = PJP1_JL_DIM // 8
    for token_index in range(token_count):
        row = input_polar[token_index * bytes_per_token : (token_index + 1) * bytes_per_token]
        for hidden_index in range(PJP1_EMBED_DIM):
            bit_index = hidden_index % PJP1_JL_DIM
            bit = (row[bit_index // 8] >> (bit_index % 8)) & 1
            values.append(1.0 if bit else -1.0)
    return values


def relu_tensor(tensor: array) -> array:
    values = array("f")
    for value in tensor:
        values.append(value if value > 0.0 else 0.0)
    return values


def count_positive(tensor: array) -> int:
    return sum(1 for value in tensor if value > 0.0)


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_phase3_staging_metrics(
    *,
    args: argparse.Namespace,
    contract: Any,
    token_count: int,
    expected_relu: array,
) -> dict[str, Any]:
    metrics = {
        "pjp1_preflight_status": contract.validation["status"],
        "native_preflight_status": None,
        "i8_oracle_mismatches": None,
        "htp_backend": None,
        "htp_output_sha256": None,
        "forward_loss": None,
        "forward_mse": None,
        "forward_cross_entropy": None,
        "perplexity": None,
        "answer_token_accuracy": None,
        "calibration_ece": None,
        "brier_score": None,
        "tokens_per_sec": None,
        "latency_ms": None,
        "host_to_device_ms": None,
        "device_compute_ms": None,
        "device_to_host_ms": None,
        "staged_token_count": token_count,
        "source_record_count": contract.source_record_count,
        "source_real_token_count": contract.source_real_token_count,
        "packet_count": contract.packet_count,
        "expected_positive_count": count_positive(expected_relu),
        "expected_zero_count": len(expected_relu) - count_positive(expected_relu),
    }
    return metric_report(
        schema_version="phase3_staging_metric_contract_v1",
        phase_family="phase3",
        corpus_phase=args.corpus_phase,
        metrics=metrics,
        blockers=[
            "htp_not_executed_by_staging_script",
            "forward_loss_requires_supervised_eval_objective",
            "native_preflight_status_not_in_stage_report",
            "i8_oracle_mismatches_not_in_stage_report",
        ],
        nonclaims=[
            "stage_metrics_do_not_claim_phase3_readiness",
            "stage_metrics_do_not_claim_learning",
        ],
    )


def classify_storage_root(path: Path) -> str:
    text = str(path)
    if text.startswith("/data/local/tmp/"):
        return "adb_shared_tmp"
    if text.startswith("/sdcard/") or text.startswith("/storage/emulated/0/"):
        return "shared_external_storage"
    if text.startswith("/data/data/com.termux/files/home/"):
        return "termux_private_storage"
    return "other_phone_storage"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
