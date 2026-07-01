#!/usr/bin/env python3
"""Phase3/4 C5 QA prediction producer boundary.

This command is designed to be passed as ``--producer-command`` to
``run_c5_prediction_payloads.py``. The wrapper appends the checkpoint role,
payload, expected hash, heldout QA JSONL, and output JSONL path. This producer
delegates to ``gemma4_layer_runner --run-c5-qa-predict`` and fails closed until
the native runtime has tokenizer, full decoder, LM-head/unembedding, and
adapter-site policy inputs capable of producing real logits.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from polymath_ai.polar.c5_eval import EVAL_POINTS, is_sha256, sha256_file  # noqa: E402


REPORT_SCHEMA = "polymath_c5_phase34_qa_inference_producer_report_v1"
DECODER_MANIFEST_SCHEMA = "polymath_c5_full_decoder_manifest_v1"
ADAPTER_SITE_POLICY_SCHEMA = "polymath_c5_adapter_site_policy_v1"
GEMMA4_E4B_MODEL_ID = "google/gemma-4-E4B"
GEMMA4_E4B_REVISION = "7aa32e6889efd6300124851b164f8b364314c3d8"
GEMMA4_E4B_LAYERS = 42
GEMMA4_E4B_HIDDEN_SIZE = 2560
GEMMA4_E4B_VOCAB_SIZE = 262144
DEFAULT_VOCAB_CHUNK_SIZE = 4096
MAX_ACCEPTED_VOCAB_CHUNK_SIZE = 16384
DEFAULT_MAX_GENERATION_TOKENS = 128
MAX_ACCEPTED_GENERATION_TOKENS = 512
LM_HEAD_CANDIDATE_FILENAMES = (
    "lm_head_or_unembedding.bf16",
    "lm_head_or_unembedding.f16",
    "lm_head_or_unembedding.f32",
    "lm_head.bf16",
    "lm_head.f16",
    "lm_head.f32",
    "unembedding.bf16",
    "unembedding.f16",
    "unembedding.f32",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gemma4-runner", default=os.environ.get("GEMMA4_LAYER_RUNNER"))
    parser.add_argument("--tokenizer-dir")
    parser.add_argument("--decoder-component-pack")
    parser.add_argument("--decoder-manifest")
    parser.add_argument("--lm-head")
    parser.add_argument("--adapter-site-policy")
    parser.add_argument("--vocab-chunk-size", type=int, default=DEFAULT_VOCAB_CHUNK_SIZE)
    parser.add_argument(
        "--max-generation-tokens",
        type=int,
        default=DEFAULT_MAX_GENERATION_TOKENS,
    )
    parser.add_argument("--native-timeout-seconds", type=int, default=3600)
    parser.add_argument("--print-contract", action="store_true")

    parser.add_argument("--run-label")
    parser.add_argument("--eval-point", choices=EVAL_POINTS)
    parser.add_argument("--checkpoint-role", choices=("candidate", "stable_baseline"))
    parser.add_argument("--checkpoint-payload", type=Path)
    parser.add_argument("--checkpoint-sha256")
    parser.add_argument("--heldout-qa-jsonl", type=Path)
    parser.add_argument("--output-jsonl", type=Path)
    return parser.parse_args()


def producer_contract() -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA,
        "compatible_wrapper": "scripts/host/run_c5_prediction_payloads.py",
        "producer_command_prefix": (
            "python3.11 scripts/host/run_c5_phase34_qa_inference_producer.py "
            "--gemma4-runner <outside_git_or_build_gemma4_layer_runner> "
            "--tokenizer-dir <outside_git_tokenizer_dir> "
            "--decoder-component-pack <outside_git_c5_decoder_component_pack> "
            "[--decoder-manifest <outside_git_decoder_manifest>] "
            "[--lm-head <outside_git_lm_head_or_unembedding>] "
            "[--adapter-site-policy <outside_git_adapter_site_policy>] "
            "--vocab-chunk-size 4096 --max-generation-tokens 128"
        ),
        "wrapper_appended_args": [
            "--run-label",
            "--eval-point",
            "--checkpoint-role",
            "--checkpoint-payload",
            "--checkpoint-sha256",
            "--heldout-qa-jsonl",
            "--output-jsonl",
        ],
        "fail_closed_missing_runtime_fields": [
            "gemma4_runner_missing",
            "tokenizer_dir_missing",
            "decoder_component_pack_missing_or_decoder_manifest_missing",
            "decoder_manifest_missing",
            "lm_head_or_unembedding_missing",
            "adapter_site_policy_missing",
        ],
        "raw_boundary": {
            "prediction_jsonl_output_must_be_outside_git": True,
            "checkpoint_payload_must_remain_outside_git": True,
            "reports_redact_raw_paths": True,
        },
        "decoder_manifest_schema": {
            "schema_version": DECODER_MANIFEST_SCHEMA,
            "model_id": GEMMA4_E4B_MODEL_ID,
            "hf_revision": GEMMA4_E4B_REVISION,
            "decoder": {
                "kind": "full_gemma4_text_decoder_logits",
                "num_hidden_layers": GEMMA4_E4B_LAYERS,
                "hidden_size": GEMMA4_E4B_HIDDEN_SIZE,
                "vocab_size": GEMMA4_E4B_VOCAB_SIZE,
                "logits_vocabulary_size": GEMMA4_E4B_VOCAB_SIZE,
                "layer_inventory": "required 42-layer inventory",
            },
            "architecture_config": {
                "required": True,
                "purpose": "Native full-decoder runtime dimensions and attention/MLP/norm/RoPE parameters.",
            },
            "tensor_role_inventory": {
                "required": True,
                "purpose": "Map every decoder tensor role to safetensors key, dtype, shape, and byte range.",
            },
            "per_layer_input_runtime": {
                "required": True,
                "purpose": "Map token IDs to Gemma 4 per-layer 256-wide inputs from PLE source tensors.",
                "required_roles": [
                    "embed_tokens_per_layer",
                    "per_layer_projection_norm",
                    "per_layer_model_projection",
                ],
            },
            "source_model_safetensors": {
                "required_fields": ["path", "sha256", "size_bytes"],
            },
            "lm_head": {
                "embedded_in_decoder": "true if --lm-head is intentionally omitted",
                "required_fields": ["dtype", "shape", "sha256", "vocab_size"],
            },
        },
        "adapter_site_policy_schema": {
            "schema_version": ADAPTER_SITE_POLICY_SCHEMA,
            "model_id": GEMMA4_E4B_MODEL_ID,
            "adapter_rank": 16,
            "required_fields": [
                "decoder_layer_index",
                "adapter_site",
                "input_shape",
                "output_shape",
                "candidate_adapter_sha256",
                "stable_baseline_adapter_sha256",
                "bridge_mse_is_c5_loss",
            ],
        },
        "component_pack_layout": {
            "decoder_manifest": "decoder_manifest.json",
            "adapter_site_policy": "adapter_site_policy.json",
            "lm_head_or_unembedding_candidates": list(LM_HEAD_CANDIDATE_FILENAMES),
        },
        "memory_strategy_contract": {
            "default_vocab_chunk_size": DEFAULT_VOCAB_CHUNK_SIZE,
            "max_accepted_vocab_chunk_size": MAX_ACCEPTED_VOCAB_CHUNK_SIZE,
            "default_max_generation_tokens": DEFAULT_MAX_GENERATION_TOKENS,
            "max_accepted_generation_tokens": MAX_ACCEPTED_GENERATION_TOKENS,
            "full_bsv_logits_materialization_allowed": False,
            "streamed_or_chunked_logits_required": True,
        },
    }


def path_digest(path: Path | None) -> str | None:
    if path is None:
        return None
    return sha256_file(path) if path.is_file() else None


def path_string_digest(path: Path | None) -> str | None:
    if path is None:
        return None
    import hashlib

    return hashlib.sha256(str(path).encode("utf-8")).hexdigest()


def is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def load_json_file(path: Path, blocker_prefix: str, blockers: list[str]) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        blockers.append(f"{blocker_prefix}_json_invalid")
    except OSError:
        blockers.append(f"{blocker_prefix}_json_unreadable")
    return None


def nested_get(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def validate_decoder_manifest(path: Path, blockers: list[str]) -> bool:
    payload = load_json_file(path, "decoder_manifest", blockers)
    if not isinstance(payload, dict):
        blockers.append("decoder_manifest_not_object")
        return False

    checks: tuple[tuple[str, Any], ...] = (
        ("schema_version", DECODER_MANIFEST_SCHEMA),
        ("model_id", GEMMA4_E4B_MODEL_ID),
        ("hf_revision", GEMMA4_E4B_REVISION),
    )
    for field, expected in checks:
        if payload.get(field) != expected:
            blockers.append(f"decoder_manifest_{field}_mismatch")

    decoder = payload.get("decoder")
    if not isinstance(decoder, dict):
        blockers.append("decoder_manifest_decoder_missing")
    else:
        decoder_checks: tuple[tuple[str, Any], ...] = (
            ("kind", "full_gemma4_text_decoder_logits"),
            ("num_hidden_layers", GEMMA4_E4B_LAYERS),
            ("hidden_size", GEMMA4_E4B_HIDDEN_SIZE),
            ("vocab_size", GEMMA4_E4B_VOCAB_SIZE),
            ("logits_vocabulary_size", GEMMA4_E4B_VOCAB_SIZE),
        )
        for field, expected in decoder_checks:
            if decoder.get(field) != expected:
                blockers.append(f"decoder_manifest_decoder_{field}_mismatch")
        layer_inventory = decoder.get("layer_inventory")
        if not isinstance(layer_inventory, list) or len(layer_inventory) != GEMMA4_E4B_LAYERS:
            blockers.append("decoder_manifest_layer_inventory_missing_or_incomplete")
    source_model = payload.get("source_model_safetensors")
    if not isinstance(source_model, dict):
        blockers.append("decoder_manifest_source_model_safetensors_missing")
    else:
        if not source_model.get("path"):
            blockers.append("decoder_manifest_source_model_safetensors_path_missing")
        if not is_sha256(str(source_model.get("sha256", ""))):
            blockers.append("decoder_manifest_source_model_safetensors_sha256_invalid")
        if not isinstance(source_model.get("size_bytes"), int) or source_model.get("size_bytes", 0) <= 0:
            blockers.append("decoder_manifest_source_model_safetensors_size_invalid")
    if not isinstance(payload.get("architecture_config"), dict):
        blockers.append("decoder_manifest_architecture_config_missing")
    if not isinstance(payload.get("tensor_role_inventory"), dict):
        blockers.append("decoder_manifest_tensor_role_inventory_missing")
    ple_runtime = payload.get("per_layer_input_runtime")
    if not isinstance(ple_runtime, dict):
        blockers.append("decoder_manifest_per_layer_input_runtime_missing")
    else:
        roles = ple_runtime.get("roles")
        if not isinstance(roles, dict):
            blockers.append("decoder_manifest_per_layer_input_runtime_roles_missing")
        else:
            for role in (
                "embed_tokens_per_layer",
                "per_layer_projection_norm",
                "per_layer_model_projection",
            ):
                if role not in roles:
                    blockers.append(f"decoder_manifest_per_layer_input_runtime_{role}_missing")

    lm_head = payload.get("lm_head")
    if lm_head is not None:
        validate_lm_head_identity(lm_head, "decoder_manifest_lm_head", blockers)
    runtime = payload.get("runtime")
    if isinstance(runtime, dict) and runtime.get("materializes_full_bsv_logits") is True:
        blockers.append("decoder_manifest_full_bsv_logits_materialization_forbidden")
    return "decoder_manifest_not_object" not in blockers


def validate_lm_head_identity(payload: Any, prefix: str, blockers: list[str]) -> None:
    if not isinstance(payload, dict):
        blockers.append(f"{prefix}_not_object")
        return
    if payload.get("dtype") not in {"bf16", "f16", "f32"}:
        blockers.append(f"{prefix}_dtype_invalid")
    shape = payload.get("shape")
    if shape != [GEMMA4_E4B_VOCAB_SIZE, GEMMA4_E4B_HIDDEN_SIZE]:
        blockers.append(f"{prefix}_shape_mismatch")
    if not is_sha256(str(payload.get("sha256", ""))):
        blockers.append(f"{prefix}_sha256_invalid")
    if payload.get("vocab_size") != GEMMA4_E4B_VOCAB_SIZE:
        blockers.append(f"{prefix}_vocab_size_mismatch")


def decoder_manifest_embeds_lm_head(path: Path) -> bool:
    blockers: list[str] = []
    payload = load_json_file(path, "decoder_manifest", blockers)
    if not isinstance(payload, dict):
        return False
    return nested_get(payload, "lm_head", "embedded_in_decoder") is True


def validate_adapter_site_policy(
    path: Path,
    blockers: list[str],
    checkpoint_role: str | None,
    checkpoint_sha256: str | None,
) -> None:
    payload = load_json_file(path, "adapter_site_policy", blockers)
    if not isinstance(payload, dict):
        blockers.append("adapter_site_policy_not_object")
        return
    if payload.get("schema_version") != ADAPTER_SITE_POLICY_SCHEMA:
        blockers.append("adapter_site_policy_schema_version_mismatch")
    if payload.get("model_id") != GEMMA4_E4B_MODEL_ID:
        blockers.append("adapter_site_policy_model_id_mismatch")
    if payload.get("adapter_rank") != 16:
        blockers.append("adapter_site_policy_rank_mismatch")
    layer_index = payload.get("decoder_layer_index")
    if not isinstance(layer_index, int) or not 0 <= layer_index < GEMMA4_E4B_LAYERS:
        blockers.append("adapter_site_policy_decoder_layer_index_invalid")
    if not isinstance(payload.get("adapter_site"), str) or not payload.get("adapter_site"):
        blockers.append("adapter_site_policy_site_missing")
    if payload.get("input_shape") != [1, 16, GEMMA4_E4B_HIDDEN_SIZE]:
        blockers.append("adapter_site_policy_input_shape_mismatch")
    if payload.get("output_shape") != [1, 16, GEMMA4_E4B_HIDDEN_SIZE]:
        blockers.append("adapter_site_policy_output_shape_mismatch")
    candidate_sha = str(payload.get("candidate_adapter_sha256", ""))
    stable_sha = str(payload.get("stable_baseline_adapter_sha256", ""))
    if not is_sha256(candidate_sha):
        blockers.append("adapter_site_policy_candidate_sha256_invalid")
    if not is_sha256(stable_sha):
        blockers.append("adapter_site_policy_stable_sha256_invalid")
    if checkpoint_role == "candidate" and checkpoint_sha256 and candidate_sha != checkpoint_sha256:
        blockers.append("adapter_site_policy_candidate_sha256_mismatch")
    if (
        checkpoint_role == "stable_baseline"
        and checkpoint_sha256
        and stable_sha != checkpoint_sha256
    ):
        blockers.append("adapter_site_policy_stable_sha256_mismatch")
    if payload.get("bridge_mse_is_c5_loss") is not False:
        blockers.append("adapter_site_policy_bridge_mse_loss_forbidden")


def resolve_component_pack_args(args: argparse.Namespace) -> list[str]:
    blockers: list[str] = []
    if not args.decoder_component_pack:
        return blockers
    component_pack = Path(args.decoder_component_pack)
    if not component_pack.is_dir():
        blockers.append("decoder_component_pack_path_not_found")
        return blockers
    if not args.decoder_manifest:
        args.decoder_manifest = str(component_pack / "decoder_manifest.json")
    if not args.adapter_site_policy:
        args.adapter_site_policy = str(component_pack / "adapter_site_policy.json")
    if not args.lm_head:
        for filename in LM_HEAD_CANDIDATE_FILENAMES:
            candidate = component_pack / filename
            if candidate.is_file():
                args.lm_head = str(candidate)
                break
    return blockers


def validate_memory_strategy_args(args: argparse.Namespace) -> list[str]:
    blockers: list[str] = []
    if args.vocab_chunk_size <= 0:
        blockers.append("vocab_chunk_size_zero")
    if args.vocab_chunk_size > MAX_ACCEPTED_VOCAB_CHUNK_SIZE:
        blockers.append("vocab_chunk_size_exceeds_streaming_limit")
    if args.max_generation_tokens <= 0:
        blockers.append("max_generation_tokens_zero")
    if args.max_generation_tokens > MAX_ACCEPTED_GENERATION_TOKENS:
        blockers.append("max_generation_tokens_exceeds_c5_limit")
    return blockers


def validate_optional_runtime_paths(args: argparse.Namespace) -> list[str]:
    blockers: list[str] = []
    if args.tokenizer_dir:
        tokenizer_dir = Path(args.tokenizer_dir)
        if not tokenizer_dir.is_dir():
            blockers.append("tokenizer_dir_path_not_found")
        else:
            if not (tokenizer_dir / "vocab.hex.tsv").is_file():
                blockers.append("tokenizer_vocab_hex_missing")
            if not (tokenizer_dir / "merges.hex.tsv").is_file():
                blockers.append("tokenizer_merges_hex_missing")
    if args.decoder_manifest:
        decoder_manifest = Path(args.decoder_manifest)
        if not decoder_manifest.is_file():
            blockers.append("decoder_manifest_path_not_found")
        else:
            validate_decoder_manifest(decoder_manifest, blockers)
    if args.lm_head:
        lm_head = Path(args.lm_head)
        if not lm_head.is_file():
            blockers.append("lm_head_or_unembedding_path_not_found")
    elif args.decoder_manifest:
        decoder_manifest = Path(args.decoder_manifest)
        if decoder_manifest.is_file() and not decoder_manifest_embeds_lm_head(decoder_manifest):
            blockers.append("lm_head_or_unembedding_missing")
    if args.adapter_site_policy:
        adapter_site_policy = Path(args.adapter_site_policy)
        if not adapter_site_policy.is_file():
            blockers.append("adapter_site_policy_path_not_found")
        else:
            validate_adapter_site_policy(
                adapter_site_policy,
                blockers,
                args.checkpoint_role,
                args.checkpoint_sha256,
            )
    return blockers


def report_path_for(output_jsonl: Path | None) -> Path | None:
    if output_jsonl is None:
        return None
    return output_jsonl.with_name(f"{output_jsonl.name}.phase34_qa_producer_report.json")


def first_blocker(blockers: list[str]) -> str | None:
    return blockers[0] if blockers else None


def write_report(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_blocked_report(
    *,
    args: argparse.Namespace,
    blockers: list[str],
    native_result: subprocess.CompletedProcess[str] | None,
) -> dict[str, Any]:
    native_stdout_json = None
    if native_result is not None and native_result.stdout.strip():
        try:
            native_stdout_json = json.loads(native_result.stdout)
        except json.JSONDecodeError:
            native_stdout_json = None

    first_missing = first_blocker(blockers)
    if native_stdout_json and native_stdout_json.get("first_missing_green_field"):
        first_missing = native_stdout_json["first_missing_green_field"]

    return {
        "schema_version": REPORT_SCHEMA,
        "status": "blocked",
        "first_missing_green_field": first_missing,
        "blockers": blockers,
        "native_report": native_stdout_json,
        "native_returncode": None if native_result is None else native_result.returncode,
        "native_stderr_excerpt": None
        if native_result is None
        else native_result.stderr[-1200:],
        "checkpoint_role": args.checkpoint_role,
        "checkpoint_sha256": args.checkpoint_sha256,
        "checkpoint_payload_identity": {
            "actual_sha256": path_digest(args.checkpoint_payload),
            "path_string_sha256": path_string_digest(args.checkpoint_payload),
            "path_redacted": True,
        },
        "heldout_qa_identity": {
            "sha256": path_digest(args.heldout_qa_jsonl),
            "path_string_sha256": path_string_digest(args.heldout_qa_jsonl),
            "path_redacted": True,
        },
        "output_jsonl_contract": {
            "path_string_sha256": path_string_digest(args.output_jsonl),
            "path_redacted": True,
            "prediction_jsonl_written": bool(args.output_jsonl and args.output_jsonl.exists()),
        },
        "decoder_component_pack_identity": {
            "path_string_sha256": path_string_digest(
                Path(args.decoder_component_pack) if args.decoder_component_pack else None
            ),
            "path_redacted": True,
        },
        "memory_strategy_contract": {
            "vocab_chunk_size": args.vocab_chunk_size,
            "max_generation_tokens": args.max_generation_tokens,
            "full_bsv_logits_materialization_allowed": False,
            "streamed_or_chunked_logits_required": True,
        },
        "raw_boundary_proof": {
            "raw_payload_bytes_in_report": False,
            "checkpoint_payload_copied_to_git": False,
            "prediction_jsonl_copied_to_git": False,
        },
        "nonclaims": [
            "no C5 pass",
            "no prediction payload emitted unless native runner returns real predictions",
            "no learning or model-quality claim",
        ],
    }


def validate_args(args: argparse.Namespace) -> list[str]:
    blockers = resolve_component_pack_args(args)
    if not args.gemma4_runner:
        blockers.append("gemma4_runner_missing")
    elif not Path(args.gemma4_runner).exists():
        blockers.append("gemma4_runner_path_not_found")
    for name in ("run_label", "eval_point", "checkpoint_role", "checkpoint_sha256"):
        if getattr(args, name) in (None, ""):
            blockers.append(f"{name}_missing")
    if not is_sha256(args.checkpoint_sha256 or ""):
        blockers.append("checkpoint_sha256_invalid")
    for name in ("checkpoint_payload", "heldout_qa_jsonl", "output_jsonl"):
        if getattr(args, name) is None:
            blockers.append(f"{name}_missing")
    if args.checkpoint_payload is not None and not args.checkpoint_payload.exists():
        blockers.append("checkpoint_payload_path_not_found")
    if args.heldout_qa_jsonl is not None and not args.heldout_qa_jsonl.exists():
        blockers.append("heldout_qa_jsonl_path_not_found")
    if args.checkpoint_payload is not None and is_under(args.checkpoint_payload, REPO_ROOT):
        blockers.append("checkpoint_payload_inside_git_worktree")
    if args.heldout_qa_jsonl is not None and is_under(args.heldout_qa_jsonl, REPO_ROOT):
        blockers.append("heldout_qa_jsonl_inside_git_worktree")
    if args.output_jsonl is not None and is_under(args.output_jsonl, REPO_ROOT):
        blockers.append("output_jsonl_inside_git_worktree")
    blockers.extend(validate_memory_strategy_args(args))
    blockers.extend(validate_optional_runtime_paths(args))
    return blockers


def native_argv(args: argparse.Namespace) -> list[str]:
    assert args.gemma4_runner
    argv = [
        args.gemma4_runner,
        "--run-c5-qa-predict",
        "--run-label",
        args.run_label,
        "--eval-point",
        args.eval_point,
        "--checkpoint-role",
        args.checkpoint_role,
        "--checkpoint-payload",
        str(args.checkpoint_payload),
        "--checkpoint-sha256",
        args.checkpoint_sha256,
        "--heldout-qa-jsonl",
        str(args.heldout_qa_jsonl),
        "--output-jsonl",
        str(args.output_jsonl),
        "--vocab-chunk-size",
        str(args.vocab_chunk_size),
        "--max-generation-tokens",
        str(args.max_generation_tokens),
    ]
    optional = (
        ("--tokenizer-dir", args.tokenizer_dir),
        ("--decoder-component-pack", args.decoder_component_pack),
        ("--decoder-manifest", args.decoder_manifest),
        ("--lm-head", args.lm_head),
        ("--adapter-site-policy", args.adapter_site_policy),
    )
    for flag, value in optional:
        if value:
            argv.extend([flag, value])
    return argv


def main() -> int:
    args = parse_args()
    if args.print_contract:
        print(json.dumps(producer_contract(), indent=2, sort_keys=True))
        return 0

    blockers = validate_args(args)
    if blockers:
        report = build_blocked_report(args=args, blockers=blockers, native_result=None)
        write_report(report_path_for(args.output_jsonl), report)
        print(json.dumps({"status": "blocked", "first_missing_green_field": report["first_missing_green_field"]}))
        return 2

    try:
        completed = subprocess.run(
            native_argv(args),
            text=True,
            capture_output=True,
            timeout=args.native_timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        report = build_blocked_report(
            args=args,
            blockers=[f"native_runner_timeout:{exc.timeout}"],
            native_result=None,
        )
        write_report(report_path_for(args.output_jsonl), report)
        print(json.dumps({"status": "blocked", "first_missing_green_field": report["first_missing_green_field"]}))
        return 2

    if completed.returncode != 0:
        report = build_blocked_report(
            args=args,
            blockers=["native_c5_qa_inference_failed"],
            native_result=completed,
        )
        write_report(report_path_for(args.output_jsonl), report)
        print(json.dumps({"status": "blocked", "first_missing_green_field": report["first_missing_green_field"]}))
        return completed.returncode

    if args.output_jsonl is None or not args.output_jsonl.exists():
        report = build_blocked_report(
            args=args,
            blockers=["native_runner_returned_success_without_output_jsonl"],
            native_result=completed,
        )
        write_report(report_path_for(args.output_jsonl), report)
        print(json.dumps({"status": "blocked", "first_missing_green_field": report["first_missing_green_field"]}))
        return 2

    print(json.dumps({"status": "pass", "output_jsonl": str(args.output_jsonl)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
