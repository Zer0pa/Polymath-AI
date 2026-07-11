#!/usr/bin/env python3
"""Freeze and execute the exact QAT-T full-width projection reference gate."""

from __future__ import annotations

import argparse
import gc
import hashlib
import os
from pathlib import Path
import resource
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from polymath_ai.frontier.e4b_f5_probe import (  # noqa: E402
    LM_HEAD,
    QAT_MODEL_BYTES,
    QAT_MODEL_SHA256,
    Q_PROJ,
    TRANSFORMERS_COMMIT,
    TRANSFORMERS_SOURCE_SHA256,
)
from polymath_ai.frontier.e4b_f5_qnn_exporter import LM_HEAD_GRAPH, Q_PROJ_GRAPH  # noqa: E402
from polymath_ai.frontier.e4b_l2_projection_gate import (  # noqa: E402
    REFERENCE_GATE_SCHEMA_VERSION,
    ProjectionGateError,
    adjudicate_metrics,
    bf16_payload_to_fp16,
    build_preregistration,
    canonical_json,
    input_cases,
    sha256_bytes,
    sha256_path,
    softmax_js_divergence,
    threshold_policy,
    validate_preregistration,
    vector_metrics,
    write_hashed_json,
)


EXPECTED_VERSIONS = {
    "torch": "2.13.0+cpu",
    "transformers": "5.13.0",
    "safetensors": "0.8.0",
    "numpy": "1.26.4",
}


def _tensor_sha256(tensor: Any) -> str:
    import torch

    if not isinstance(tensor, torch.Tensor):
        raise TypeError("expected torch tensor")
    contiguous = tensor.detach().cpu().contiguous().view(torch.uint8).numpy()
    return hashlib.sha256(memoryview(contiguous)).hexdigest()


def _tensor_bytes(tensor: Any) -> bytes:
    import torch

    if not isinstance(tensor, torch.Tensor):
        raise TypeError("expected torch tensor")
    contiguous = tensor.detach().cpu().contiguous().view(torch.uint8).numpy()
    return memoryview(contiguous).tobytes()


def _write_raw(path: Path, payload: bytes) -> dict[str, Any]:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        view = memoryview(payload)
        while view:
            count = os.write(descriptor, view)
            if count <= 0:
                raise OSError(f"short write to {path}")
            view = view[count:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return {"relative_path": str(path.name), "bytes": len(payload), "sha256": sha256_bytes(payload)}


def _source_hashes(transformers_root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for relative, expected in TRANSFORMERS_SOURCE_SHA256.items():
        path = transformers_root / relative.removeprefix("src/transformers/")
        observed = sha256_path(path)
        if observed != expected:
            raise ProjectionGateError(f"Transformers source drift: {relative}")
        result[relative] = observed
    return result


def _advise_drop_cache(path: Path) -> dict[str, Any]:
    if not hasattr(os, "posix_fadvise") or not hasattr(os, "POSIX_FADV_DONTNEED"):
        return {"supported": False, "applied": False}
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_CLOEXEC", 0))
    try:
        os.posix_fadvise(descriptor, 0, 0, os.POSIX_FADV_DONTNEED)
    finally:
        os.close(descriptor)
    return {"supported": True, "applied": True, "global_drop_caches_used": False}


def _load_module(handle: Any, contract: Any, quantized_linear: Any) -> Any:
    import torch

    module = quantized_linear(
        contract.input_features,
        contract.output_features,
        bias=False,
        num_bits=contract.num_bits,
    )
    tensors = {
        "weight": handle.get_tensor(contract.weight.name),
        "weight_scale": handle.get_tensor(contract.weight_scale.name),
        "input_activation_scale": handle.get_tensor(contract.input_activation_scale.name),
        "output_activation_scale": handle.get_tensor(contract.output_activation_scale.name),
    }
    contracts = {
        "weight": contract.weight,
        "weight_scale": contract.weight_scale,
        "input_activation_scale": contract.input_activation_scale,
        "output_activation_scale": contract.output_activation_scale,
    }
    for name, tensor in tensors.items():
        if _tensor_sha256(tensor) != contracts[name].data_sha256:
            raise ProjectionGateError(f"exact tensor digest mismatch: {contracts[name].name}")
        setattr(module, name, torch.nn.Parameter(tensor, requires_grad=False))
    module.eval()
    return module


def _stack_w4_inputs(prereg_root: Path) -> tuple[Any, list[Any]]:
    import torch

    cases = [case for case in input_cases() if case.graph_name == Q_PROJ_GRAPH]
    tensors = []
    for case in cases:
        payload = (prereg_root / "inputs" / case.filename).read_bytes()
        tensor = torch.frombuffer(bytearray(payload), dtype=torch.int8).clone()
        tensors.append(tensor)
    return torch.stack(tensors).reshape(len(tensors), 1, Q_PROJ.input_features), cases


def _stack_w2_inputs(prereg_root: Path) -> tuple[Any, Any, list[Any]]:
    import torch

    cases = [case for case in input_cases() if case.graph_name == LM_HEAD_GRAPH]
    bf16_tensors = []
    fp16_tensors = []
    for case in cases:
        bf16_payload = (prereg_root / "inputs" / case.filename).read_bytes()
        fp16_payload = (
            prereg_root / "inputs" / case.filename.replace(".bf16.raw", ".f16.raw")
        ).read_bytes()
        if fp16_payload != bf16_payload_to_fp16(bf16_payload):
            raise ProjectionGateError(f"FP16 input is not the frozen BF16 cast: {case.case_id}")
        bf16 = torch.frombuffer(bytearray(bf16_payload), dtype=torch.uint16).view(torch.bfloat16).clone()
        fp16 = torch.frombuffer(bytearray(fp16_payload), dtype=torch.float16).clone()
        if _tensor_bytes(fp16.to(torch.bfloat16).view(torch.uint16)) != bf16_payload:
            raise ProjectionGateError(f"BF16-to-FP16 round trip drift: {case.case_id}")
        bf16_tensors.append(bf16)
        fp16_tensors.append(fp16)
    shape = (len(cases), 1, LM_HEAD.input_features)
    return torch.stack(bf16_tensors).reshape(shape), torch.stack(fp16_tensors).reshape(shape), cases


def _run_twice(module: Any, inputs: Any) -> tuple[Any, list[str]]:
    import torch

    outputs = []
    digests = []
    with torch.inference_mode():
        for _ in range(2):
            output = module(inputs)
            if not torch.isfinite(output).all():
                raise FloatingPointError("non-finite projection output")
            digests.append(_tensor_sha256(output))
            outputs.append(output.detach().cpu().clone())
    if digests[0] != digests[1] or not torch.equal(outputs[0], outputs[1]):
        raise ProjectionGateError("framework projection replay is not deterministic")
    return outputs[0], digests


def _metrics(reference: Any, candidate: Any) -> dict[str, Any]:
    left = reference.detach().float().reshape(-1).tolist()
    right = candidate.detach().float().reshape(-1).tolist()
    result = vector_metrics(left, right)
    result["softmax_js_divergence"] = softmax_js_divergence(left, right)
    return result


def _observe(args: argparse.Namespace) -> None:
    prereg = validate_preregistration(args.prereg_dir)
    prereg_sha256 = sha256_path(args.prereg_dir / "preregistration.json")
    policy = threshold_policy()
    policy_sha256 = sha256_path(args.prereg_dir / "threshold_policy.json")
    if args.output_dir.exists():
        raise ProjectionGateError(f"output already exists: {args.output_dir}")
    args.output_dir.mkdir(mode=0o700, parents=True)
    references = args.output_dir / "references"
    references.mkdir(mode=0o700)

    if args.model.stat().st_size != QAT_MODEL_BYTES or sha256_path(args.model) != QAT_MODEL_SHA256:
        raise ProjectionGateError("QAT-T model carrier identity mismatch")
    model_cache_advice = _advise_drop_cache(args.model)

    import numpy
    import safetensors
    import torch
    import transformers
    from safetensors import safe_open
    from transformers.integrations.gemma_quant import QuantizedLinear, apply_srq

    observed_versions = {
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "safetensors": safetensors.__version__,
        "numpy": numpy.__version__,
    }
    if observed_versions != EXPECTED_VERSIONS:
        raise ProjectionGateError(f"reference package version drift: {observed_versions}")
    transformers_root = Path(transformers.__file__).resolve().parent
    source_hashes = _source_hashes(transformers_root)

    torch.manual_seed(0)
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    started = time.monotonic()

    case_records: list[dict[str, Any]] = []
    all_cast_edges_passed = True
    with safe_open(args.model, framework="pt", device="cpu") as handle:
        q_module = _load_module(handle, Q_PROJ, QuantizedLinear)
        q_raw, q_cases = _stack_w4_inputs(args.prereg_dir)
        q_scale = q_module.input_activation_scale.to(torch.bfloat16)
        q_inputs = q_raw.to(torch.bfloat16) * q_scale
        q_outputs, q_replays = _run_twice(q_module, q_inputs)
        q_output_scale = q_module.output_activation_scale.to(torch.bfloat16)
        q_output_bins = torch.clamp(
            torch.round(q_outputs / q_output_scale),
            -128,
            127,
        ).to(torch.int8)
        if not torch.equal(apply_srq(q_outputs, q_module.output_activation_scale), q_outputs):
            raise ProjectionGateError("W4 output is not stable under its frozen SRQ")
        for index, case in enumerate(q_cases):
            output_payload = _tensor_bytes(q_output_bins[index])
            output_file = references / f"{case.case_id}.w4_reference.s8.raw"
            output_record = _write_raw(output_file, output_payload)
            case_records.append(
                {
                    "graph_name": Q_PROJ_GRAPH,
                    "case_id": case.case_id,
                    "input": {
                        "relative_path": f"inputs/{case.filename}",
                        "bytes": len(case.payload),
                        "sha256": sha256_bytes(case.payload),
                        "dtype": "int8",
                    },
                    "reference_output": {
                        **output_record,
                        "relative_path": f"references/{output_record['relative_path']}",
                        "dtype": "int8",
                        "shape": [1, 1, Q_PROJ.output_features],
                    },
                    "framework_replay_sha256": q_replays,
                    "state": "reference_generated_phone_unobserved",
                }
            )
        del q_module, q_raw, q_inputs, q_outputs, q_output_bins
        gc.collect()

        head_module = _load_module(handle, LM_HEAD, QuantizedLinear)
        bf16_inputs, fp16_inputs, head_cases = _stack_w2_inputs(args.prereg_dir)
        bf16_outputs, bf16_replays = _run_twice(head_module, bf16_inputs)
        fp16_outputs, fp16_replays = _run_twice(head_module, fp16_inputs)
        limits = policy["edges"]["w2_bf16_to_fp16_framework"]
        for index, case in enumerate(head_cases):
            bf16_payload = _tensor_bytes(bf16_outputs[index])
            fp16_payload = _tensor_bytes(fp16_outputs[index])
            bf16_file = references / f"{case.case_id}.w2_qat_authority.bf16.raw"
            fp16_file = references / f"{case.case_id}.w2_fp16_surrogate.f16.raw"
            bf16_record = _write_raw(bf16_file, bf16_payload)
            fp16_record = _write_raw(fp16_file, fp16_payload)
            metrics = _metrics(bf16_outputs[index], fp16_outputs[index])
            metrics["input_cast_max_abs"] = float(
                torch.max(torch.abs(bf16_inputs[index].float() - fp16_inputs[index].float()))
            )
            passed, failures = adjudicate_metrics(metrics, limits)
            if metrics["input_cast_max_abs"] > float(limits["input_cast_max_abs"]):
                passed = False
                failures.append("input_cast_max_abs_above_zero")
            all_cast_edges_passed = all_cast_edges_passed and passed
            case_records.append(
                {
                    "graph_name": LM_HEAD_GRAPH,
                    "case_id": case.case_id,
                    "input": {
                        "bf16_relative_path": f"inputs/{case.filename}",
                        "bf16_bytes": len(case.payload),
                        "bf16_sha256": sha256_bytes(case.payload),
                        "fp16_relative_path": f"inputs/{case.filename.replace('.bf16.raw', '.f16.raw')}",
                        "fp16_bytes": len(case.payload),
                        "fp16_sha256": sha256_bytes(bf16_payload_to_fp16(case.payload)),
                    },
                    "qat_bf16_output": {
                        **bf16_record,
                        "relative_path": f"references/{bf16_record['relative_path']}",
                        "dtype": "bfloat16",
                        "shape": [1, 1, LM_HEAD.output_features],
                    },
                    "qat_fp16_surrogate_output": {
                        **fp16_record,
                        "relative_path": f"references/{fp16_record['relative_path']}",
                        "dtype": "float16",
                        "shape": [1, 1, LM_HEAD.output_features],
                    },
                    "framework_replay_sha256": {
                        "bfloat16": bf16_replays,
                        "float16": fp16_replays,
                    },
                    "bf16_to_fp16_metrics": metrics,
                    "bf16_to_fp16_failures": failures,
                    "state": "passed_scope" if passed else "falsified_scope",
                }
            )

    primary_q = next(record for record in case_records if record["graph_name"] == Q_PROJ_GRAPH)
    primary_head = next(record for record in case_records if record["graph_name"] == LM_HEAD_GRAPH)
    status = "passed_scope" if all_cast_edges_passed else "falsified_scope"
    gate = {
        "schema_version": REFERENCE_GATE_SCHEMA_VERSION,
        "status": status,
        "scope": "full_width_W4_W2_framework_reference_and_W2_BF16_to_FP16_admission",
        "run_id": args.run_id,
        "recorded_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "qat_model_sha256": QAT_MODEL_SHA256,
        "transformers_commit": TRANSFORMERS_COMMIT,
        "preregistration_sha256": prereg_sha256,
        "l2_threshold_policy_sha256": policy_sha256,
        "probes": [
            {
                "graph_name": Q_PROJ_GRAPH,
                "input_sha256": primary_q["input"]["sha256"],
                "reference_output_sha256": primary_q["reference_output"]["sha256"],
                "primary_case_id": primary_q["case_id"],
            },
            {
                "graph_name": LM_HEAD_GRAPH,
                "input_sha256": primary_head["input"]["fp16_sha256"],
                "reference_output_sha256": primary_head["qat_fp16_surrogate_output"]["sha256"],
                "primary_case_id": primary_head["case_id"],
            },
        ],
        "case_records": case_records,
        "phone_execution_count": 0,
        "qnn_output_observed": False,
        "full_L2_passed": False,
        "claim_boundary": "reference_and_cast_edge_only; phone_QNN_projection_execution_still_required",
        "nonclaims": prereg["nonclaims"],
    }
    gate_sha256 = write_hashed_json(args.output_dir / "reference_gate.json", gate)
    receipt = {
        "schema_version": "gemma4_e4b_l2_projection_reference_receipt_v1",
        "state": status,
        "run_id": args.run_id,
        "reference_gate_sha256": gate_sha256,
        "preregistration_sha256": prereg_sha256,
        "threshold_policy_sha256": policy_sha256,
        "model_sha256": QAT_MODEL_SHA256,
        "versions": observed_versions,
        "transformers_source_sha256": source_hashes,
        "model_cache_advice_after_full_hash": model_cache_advice,
        "case_count": len(case_records),
        "w2_cast_cases_passed": sum(
            record["state"] == "passed_scope"
            for record in case_records
            if record["graph_name"] == LM_HEAD_GRAPH
        ),
        "w2_cast_cases_total": len([record for record in case_records if record["graph_name"] == LM_HEAD_GRAPH]),
        "wall_time_seconds": time.monotonic() - started,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "phone_execution_count": 0,
        "full_L2_passed": False,
    }
    receipt_sha256 = write_hashed_json(args.output_dir / "reference_receipt.json", receipt)
    print(
        canonical_json(
            {
                "state": status,
                "reference_gate_sha256": gate_sha256,
                "reference_receipt_sha256": receipt_sha256,
            }
        ).decode("utf-8")
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    freeze = subparsers.add_parser("freeze")
    freeze.add_argument("--output-dir", type=Path, required=True)
    freeze.add_argument("--created-at-utc", required=True)

    observe = subparsers.add_parser("observe")
    observe.add_argument("--prereg-dir", type=Path, required=True)
    observe.add_argument("--model", type=Path, required=True)
    observe.add_argument("--output-dir", type=Path, required=True)
    observe.add_argument("--run-id", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "freeze":
        print(canonical_json(build_preregistration(args.output_dir, created_at_utc=args.created_at_utc)).decode("utf-8"))
        return 0
    _observe(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
