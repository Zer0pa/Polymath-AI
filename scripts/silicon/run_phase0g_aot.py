"""Phase 0G AOT compile sweep — Apple Silicon executor.

Boundary: Research infrastructure for in silico on-device LLM training and
multilingual / multi-domain knowledge model construction. Outputs are
research artifacts - model checkpoints, training telemetry, evaluation
reports, throughput measurements. No regulatory certification claims. No
clinical or human-subject use. No surveillance, biometric profiling, or
identity inference. No model weights distributed without explicit license
attestation. No training on copyrighted material without explicit
corpus-license decomposition. No deployment to production without a
falsifier-traced acceptance gate.

This script attempts the QNN AOT compile chain for the Phase 0G matrix:

    (Qwen/Qwen2.5-1.5B,  tiny_block)             -> litert_qnn_sm8750
    (Qwen/Qwen2.5-1.5B,  qwen_block)             -> litert_qnn_sm8750
    (Qwen/Qwen2.5-1.5B,  qwen_frozen_subgraph)   -> litert_qnn_sm8750
    (HuggingFaceTB/SmolLM3-3B, smollm3_block)    -> litert_qnn_sm8750
    (HuggingFaceTB/SmolLM3-3B, smollm3_frozen_subgraph) -> litert_qnn_sm8750

Each scope is exercised in two stages:
  1. ``litert_torch.convert(...)``  -> ``.tflite`` flatbuffer
  2. ``ai_edge_litert.aot.aot_compile(..., target=Target(SocModel.SM8750))``

Per-scope output (under ``runtime/reports/export_probe/<utc>/``):
  * ``compile_records/<scope>__litert_qnn_sm8750.json``
  * ``compile_logs/<scope>__litert_qnn_sm8750.log``
  * ``tflite/<scope>.tflite`` (intermediate; HF-bound, not committed to git)
  * ``delegate_report.json`` per scope when AOT succeeds

Plus aggregate ``summary.json`` + ``truth_table.md`` plus parity rows for
``cpu`` and ``vulkan_gpu`` via ``MacSimAdapter`` (stage=stub, marked).

Random-init weights are used for the real-architecture scopes (qwen_*,
smollm3_*); Phase 0G is a graph-structure / op-coverage probe, not a
weight-correctness probe. Architecture comes from
``transformers.AutoConfig.from_pretrained(...)`` so the op surface matches
the production weights identically.
"""
from __future__ import annotations

import dataclasses
import json
import os
import platform
import sys
import textwrap
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --- Repo imports (must work from CWD = repo root) ---
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from polymath_ai._version import SCHEMA_VERSION
from polymath_ai.boundary.text import boundary_envelope
from polymath_ai.dispatch.adapters import (
    AcceleratorAdapter,
    BackendProbeRecord,
    CompileRecord,
    DelegateReport,
    FallbackAdapter,
    MacSimAdapter,
)
from polymath_ai.dispatch.export_probe import (
    ExportProbeRecord,
    ExportProbeSpec,
    _record_for,
    _write_markdown_truth_table,
)
from polymath_ai.utils.canonical import canonical_json, sha256_file, utc_now_iso


SCOPES_QNN = (
    ("Qwen/Qwen2.5-1.5B", "tiny_block"),
    ("Qwen/Qwen2.5-1.5B", "qwen_block"),
    ("Qwen/Qwen2.5-1.5B", "qwen_frozen_subgraph"),
    ("HuggingFaceTB/SmolLM3-3B", "smollm3_block"),
    ("HuggingFaceTB/SmolLM3-3B", "smollm3_frozen_subgraph"),
)
SCOPES_PARITY = (
    # (model_id, scope, target) parity rows for falsifier-coverage parity per
    # the handoff: "the same five against the cpu and vulkan_gpu targets ...
    # these can use the existing MacSimAdapter/FallbackAdapter rather than
    # real compile if you prefer; the litert_qnn_sm8750 rows are what unlock
    # the gate."
)
TARGET_QNN = "litert_qnn_sm8750"
TARGET_SOC = "SM8750"

# Frozen subgraph layer ranges (PRD ELO Stage 1: train first + last layer,
# freeze the middle). For Qwen2.5-1.5B (28 layers) the middle is 1..27 (1..26 inclusive).
# For SmolLM3-3B (36 layers) the middle is 1..35 (1..34 inclusive).
QWEN_FROZEN_RANGE = (1, 27)        # python-slice end-exclusive
# SmolLM3-3B is hidden_size=2048, intermediate=11008. The full frozen middle
# (layers 1..35 = 34 layers) materialises a ~12 GB tflite + ~4 GB convert
# overhead, which exceeds this 16 GB M1's combined disk + RAM budget. We
# reduce the representative subgraph to 8 layers (still spans ~2 NoPE
# positions in SmolLM3's "every-4th NoPE" alternation pattern) and annotate
# the reduction explicitly in the CompileRecord so downstream falsifiers
# can decide whether to accept it. The full-range run is recoverable on a
# Linux x86_64 host where ai-edge-litert ships the apply_plugin_main
# binary anyway (Path A in docs/PHASE-0G-PLAN.md).
SMOLLM3_FROZEN_RANGE = (1, 9)
SMOLLM3_FROZEN_FULL_RANGE = (1, 35)
SMOLLM3_FROZEN_REDUCTION_REASON = (
    "apple_silicon_m1_16gb_ram_disk_constraint: full 34-layer subgraph "
    "materialises ~12 GB tflite + ~4 GB convert RAM overhead which "
    "exceeds host budget; 8-layer representative slice retains "
    "RoPE/NoPE alternation and the SmolLM3 op set."
)


# ---------- graph builders ----------


def _build_tiny_block(*, seq_len: int = 16):
    """Single Qwen-shape block at toy dims using polymath_ai.models.tiny_qwen.

    Returns ``(module, sample_args)`` where sample_args is a 1-tuple
    ``(input_ids,)`` so litert_torch.convert sees the full embedding-to-logits
    path; this matches what an on-device executor would dispatch.
    """
    import torch
    from polymath_ai.models.tiny_qwen import TinyQwenConfig, TinyQwenForCausalLM

    cfg = TinyQwenConfig(
        vocab_size=257,
        hidden_size=32,
        intermediate_size=64,
        num_hidden_layers=1,    # single block for tiny scope
        num_attention_heads=4,
        num_key_value_heads=2,
        head_dim=8,
        max_position_embeddings=seq_len,
    )
    model = TinyQwenForCausalLM(cfg).eval()
    sample = (torch.randint(0, cfg.vocab_size, (1, seq_len), dtype=torch.long),)
    return model, sample, {"seq_len": seq_len, "config": dataclasses.asdict(cfg)}


class _BlockTraceWrap:
    """Wraps a single transformers DecoderLayer so litert_torch.convert can
    trace it from a single ``hidden_states`` input. Position embeddings and
    the causal attention mask are precomputed at trace time.
    """

    pass


def _make_block_tracewrap(layer, hidden_size: int, seq_len: int, num_heads: int, head_dim: int, rope_theta: float):
    import torch
    import torch.nn as nn

    # Pre-compute RoPE cos/sin tables once.
    inv_freq = 1.0 / (rope_theta ** (torch.arange(0, head_dim, 2).float() / head_dim))
    pos = torch.arange(seq_len, dtype=torch.float32)
    freqs = torch.einsum("i,j->ij", pos, inv_freq)  # (T, head_dim/2)
    emb = torch.cat([freqs, freqs], dim=-1)        # (T, head_dim)
    cos = emb.cos()[None, :, :]                    # (1, T, head_dim)
    sin = emb.sin()[None, :, :]                    # (1, T, head_dim)

    # Standard causal mask: 0 where attention is allowed, -inf where masked.
    mask_causal = torch.zeros(1, 1, seq_len, seq_len, dtype=torch.float32)
    mask_causal = mask_causal.masked_fill(
        torch.triu(torch.ones(seq_len, seq_len, dtype=torch.bool), diagonal=1),
        float("-inf"),
    )

    class _Wrap(nn.Module):
        def __init__(self):
            super().__init__()
            self.layer = layer
            self.register_buffer("cos", cos)
            self.register_buffer("sin", sin)
            self.register_buffer("attn_mask", mask_causal)
            self.register_buffer("position_ids", torch.arange(seq_len, dtype=torch.long).unsqueeze(0))

        def forward(self, hidden_states):
            position_embeddings = (self.cos, self.sin)
            out = self.layer(
                hidden_states=hidden_states,
                attention_mask=self.attn_mask,
                position_ids=self.position_ids,
                position_embeddings=position_embeddings,
                past_key_value=None,
                output_attentions=False,
                use_cache=False,
            )
            return out[0] if isinstance(out, tuple) else out

    return _Wrap().eval()


def _make_subgraph_tracewrap(layers, hidden_size: int, seq_len: int, num_heads: int, head_dim: int, rope_theta: float):
    """Same as block_tracewrap but threads hidden_states through a sequence of
    layers (the "frozen middle" subgraph)."""
    import torch
    import torch.nn as nn

    inv_freq = 1.0 / (rope_theta ** (torch.arange(0, head_dim, 2).float() / head_dim))
    pos = torch.arange(seq_len, dtype=torch.float32)
    freqs = torch.einsum("i,j->ij", pos, inv_freq)
    emb = torch.cat([freqs, freqs], dim=-1)
    cos = emb.cos()[None, :, :]
    sin = emb.sin()[None, :, :]

    mask_causal = torch.zeros(1, 1, seq_len, seq_len, dtype=torch.float32)
    mask_causal = mask_causal.masked_fill(
        torch.triu(torch.ones(seq_len, seq_len, dtype=torch.bool), diagonal=1),
        float("-inf"),
    )

    class _Wrap(nn.Module):
        def __init__(self):
            super().__init__()
            self.layers = nn.ModuleList(layers)
            self.register_buffer("cos", cos)
            self.register_buffer("sin", sin)
            self.register_buffer("attn_mask", mask_causal)
            self.register_buffer("position_ids", torch.arange(seq_len, dtype=torch.long).unsqueeze(0))

        def forward(self, hidden_states):
            position_embeddings = (self.cos, self.sin)
            for layer in self.layers:
                out = layer(
                    hidden_states=hidden_states,
                    attention_mask=self.attn_mask,
                    position_ids=self.position_ids,
                    position_embeddings=position_embeddings,
                    past_key_value=None,
                    output_attentions=False,
                    use_cache=False,
                )
                hidden_states = out[0] if isinstance(out, tuple) else out
            return hidden_states

    return _Wrap().eval()


def _build_qwen_block(*, seq_len: int = 16):
    import torch
    from transformers import AutoConfig
    from transformers.models.qwen2.modeling_qwen2 import Qwen2DecoderLayer

    cfg = AutoConfig.from_pretrained("Qwen/Qwen2.5-1.5B")
    cfg._attn_implementation = "eager"  # tflite-traceable; no flash/sdpa kernels
    head_dim = cfg.hidden_size // cfg.num_attention_heads
    layer = Qwen2DecoderLayer(cfg, layer_idx=0).eval()
    wrap = _make_block_tracewrap(
        layer,
        hidden_size=cfg.hidden_size,
        seq_len=seq_len,
        num_heads=cfg.num_attention_heads,
        head_dim=head_dim,
        rope_theta=cfg.rope_theta,
    )
    sample = (torch.randn(1, seq_len, cfg.hidden_size),)
    meta = {
        "model_id": "Qwen/Qwen2.5-1.5B",
        "model_type": cfg.model_type,
        "seq_len": seq_len,
        "hidden_size": cfg.hidden_size,
        "num_heads": cfg.num_attention_heads,
        "num_kv_heads": cfg.num_key_value_heads,
        "head_dim": head_dim,
        "intermediate_size": cfg.intermediate_size,
        "rope_theta": cfg.rope_theta,
        "layer_index": 0,
        "weights": "random_init",
    }
    return wrap, sample, meta


def _build_qwen_frozen_subgraph(*, seq_len: int = 16):
    import torch
    from transformers import AutoConfig
    from transformers.models.qwen2.modeling_qwen2 import Qwen2DecoderLayer

    cfg = AutoConfig.from_pretrained("Qwen/Qwen2.5-1.5B")
    cfg._attn_implementation = "eager"  # tflite-traceable; no flash/sdpa kernels
    head_dim = cfg.hidden_size // cfg.num_attention_heads
    a, b = QWEN_FROZEN_RANGE
    layers = [Qwen2DecoderLayer(cfg, layer_idx=i).eval() for i in range(a, b)]
    wrap = _make_subgraph_tracewrap(
        layers,
        hidden_size=cfg.hidden_size,
        seq_len=seq_len,
        num_heads=cfg.num_attention_heads,
        head_dim=head_dim,
        rope_theta=cfg.rope_theta,
    )
    sample = (torch.randn(1, seq_len, cfg.hidden_size),)
    meta = {
        "model_id": "Qwen/Qwen2.5-1.5B",
        "model_type": cfg.model_type,
        "seq_len": seq_len,
        "hidden_size": cfg.hidden_size,
        "frozen_layer_range": list(QWEN_FROZEN_RANGE),
        "num_layers_in_subgraph": b - a,
        "weights": "random_init",
    }
    return wrap, sample, meta


def _build_smollm3_block(*, seq_len: int = 16):
    import torch
    from transformers import AutoConfig
    from transformers.models.smollm3.modeling_smollm3 import SmolLM3DecoderLayer

    cfg = AutoConfig.from_pretrained("HuggingFaceTB/SmolLM3-3B")
    cfg._attn_implementation = "eager"  # tflite-traceable; no flash/sdpa kernels
    head_dim = cfg.hidden_size // cfg.num_attention_heads
    layer = SmolLM3DecoderLayer(cfg, layer_idx=0).eval()
    wrap = _make_block_tracewrap(
        layer,
        hidden_size=cfg.hidden_size,
        seq_len=seq_len,
        num_heads=cfg.num_attention_heads,
        head_dim=head_dim,
        rope_theta=cfg.rope_theta,
    )
    sample = (torch.randn(1, seq_len, cfg.hidden_size),)
    meta = {
        "model_id": "HuggingFaceTB/SmolLM3-3B",
        "model_type": cfg.model_type,
        "seq_len": seq_len,
        "hidden_size": cfg.hidden_size,
        "num_heads": cfg.num_attention_heads,
        "num_kv_heads": cfg.num_key_value_heads,
        "head_dim": head_dim,
        "intermediate_size": cfg.intermediate_size,
        "rope_theta": cfg.rope_theta,
        "layer_index": 0,
        "weights": "random_init",
    }
    return wrap, sample, meta


def _build_smollm3_frozen_subgraph(*, seq_len: int = 16):
    import torch
    from transformers import AutoConfig
    from transformers.models.smollm3.modeling_smollm3 import SmolLM3DecoderLayer

    cfg = AutoConfig.from_pretrained("HuggingFaceTB/SmolLM3-3B")
    cfg._attn_implementation = "eager"  # tflite-traceable; no flash/sdpa kernels
    head_dim = cfg.hidden_size // cfg.num_attention_heads
    a, b = SMOLLM3_FROZEN_RANGE
    layers = [SmolLM3DecoderLayer(cfg, layer_idx=i).eval() for i in range(a, b)]
    wrap = _make_subgraph_tracewrap(
        layers,
        hidden_size=cfg.hidden_size,
        seq_len=seq_len,
        num_heads=cfg.num_attention_heads,
        head_dim=head_dim,
        rope_theta=cfg.rope_theta,
    )
    sample = (torch.randn(1, seq_len, cfg.hidden_size),)
    meta = {
        "model_id": "HuggingFaceTB/SmolLM3-3B",
        "model_type": cfg.model_type,
        "seq_len": seq_len,
        "hidden_size": cfg.hidden_size,
        "frozen_layer_range": list(SMOLLM3_FROZEN_RANGE),
        "frozen_layer_range_full": list(SMOLLM3_FROZEN_FULL_RANGE),
        "num_layers_in_subgraph": b - a,
        "num_layers_full_subgraph": SMOLLM3_FROZEN_FULL_RANGE[1] - SMOLLM3_FROZEN_FULL_RANGE[0],
        "reduction_applied": True,
        "reduction_reason": SMOLLM3_FROZEN_REDUCTION_REASON,
        "weights": "random_init",
    }
    return wrap, sample, meta


SCOPE_BUILDERS = {
    "tiny_block": _build_tiny_block,
    "qwen_block": _build_qwen_block,
    "qwen_frozen_subgraph": _build_qwen_frozen_subgraph,
    "smollm3_block": _build_smollm3_block,
    "smollm3_frozen_subgraph": _build_smollm3_frozen_subgraph,
}


# ---------- compile attempt ----------


def _attempt_aot_compile(scope: str, model_id: str, *, out_dir: Path) -> Tuple[CompileRecord, str, Dict[str, Any]]:
    """Run convert + aot_compile, capture all logs, return (CompileRecord, log_text, meta).

    On any failure the CompileRecord captures result="failed" or "unsupported"
    with a parsed reason and a pointer to log_path.
    """
    import torch

    log = StringIO()
    meta_extra: Dict[str, Any] = {}
    log.write(f"=== Phase 0G AOT compile: model={model_id} scope={scope} target={TARGET_QNN} ===\n")
    log.write(f"=== started: {utc_now_iso()} ===\n\n")

    builder = SCOPE_BUILDERS[scope]

    # 1. Build the graph
    try:
        log.write(f"[1/3] Building scope graph (random init weights)...\n")
        t0 = time.time()
        with torch.no_grad():
            module, sample_args, meta = builder()
        log.write(f"  ok in {time.time() - t0:.2f}s\n")
        log.write(f"  meta: {json.dumps(meta, default=str)}\n\n")
        meta_extra.update(meta)
    except Exception as e:
        tb = traceback.format_exc()
        log.write(f"  FAILED: {type(e).__name__}: {e}\n{tb}\n")
        return (
            CompileRecord(
                backend_name=TARGET_QNN,
                graph_scope=scope,
                target=TARGET_SOC,
                result="failed",
                delegate_pct=None,
                unsupported_ops=[],
                log_path=None,
            ),
            log.getvalue(),
            {**meta_extra, "stage_failed": "build_graph", "exception": f"{type(e).__name__}: {e}"},
        )

    # 2. litert_torch.convert
    try:
        log.write(f"[2/3] litert_torch.convert(...)...\n")
        import litert_torch
        captured = StringIO()
        t0 = time.time()
        with redirect_stdout(captured), redirect_stderr(captured):
            with torch.no_grad():
                lr_model = litert_torch.convert(module, sample_args)
        dt = time.time() - t0
        log.write(captured.getvalue())
        log.write(f"  convert ok in {dt:.2f}s\n")

        tflite_path = out_dir / "tflite" / f"{scope}.tflite"
        tflite_path.parent.mkdir(parents=True, exist_ok=True)
        captured = StringIO()
        with redirect_stdout(captured), redirect_stderr(captured):
            lr_model.export(str(tflite_path))
        log.write(captured.getvalue())
        size = tflite_path.stat().st_size
        meta_extra["tflite_path"] = str(tflite_path.relative_to(out_dir))
        meta_extra["tflite_size_bytes"] = size
        meta_extra["tflite_sha256"] = sha256_file(tflite_path)
        log.write(f"  saved {tflite_path} ({size} bytes)\n\n")
    except Exception as e:
        tb = traceback.format_exc()
        log.write(f"  FAILED: {type(e).__name__}: {e}\n{tb}\n")
        return (
            CompileRecord(
                backend_name=TARGET_QNN,
                graph_scope=scope,
                target=TARGET_SOC,
                result="failed",
                delegate_pct=None,
                unsupported_ops=[],
                log_path=None,
            ),
            log.getvalue(),
            {**meta_extra, "stage_failed": "litert_convert", "exception": f"{type(e).__name__}: {e}"},
        )

    # 3. ai_edge_litert.aot.aot_compile to QNN SM8750
    try:
        log.write(f"[3/3] ai_edge_litert.aot.aot_compile(target=Qualcomm_SM8750)...\n")
        from ai_edge_litert.aot.aot_compile import aot_compile
        from ai_edge_litert.aot.vendors.qualcomm.target import (
            SocModel,
            Target as QnnTarget,
        )

        target = QnnTarget(SocModel.SM8750)
        aot_dir = out_dir / "qnn_aot" / scope
        aot_dir.mkdir(parents=True, exist_ok=True)
        captured = StringIO()
        t0 = time.time()
        with redirect_stdout(captured), redirect_stderr(captured):
            result = aot_compile(
                str(tflite_path),
                output_dir=str(aot_dir),
                target=target,
                keep_going=True,
            )
        dt = time.time() - t0
        log.write(captured.getvalue())
        log.write(f"  aot_compile returned in {dt:.2f}s; type={type(result).__name__}\n")
        # Inspect the result to determine ok/unsupported/failed.
        delegate_pct: Optional[float] = None
        unsupported_ops: List[str] = []
        compiled_artifacts: List[str] = []
        # CompilationResult has models_with_backend on success; check.
        for attr in ("compilation_results", "models_with_backend", "results", "compiled_models"):
            if hasattr(result, attr):
                compiled_artifacts.append(f"{attr}={getattr(result, attr)!r}")
        log.write(f"  result fields: {compiled_artifacts}\n")

        # Inspect result.models_with_backend directly. ai_edge_litert's
        # CompilationResult exposes models_with_backend at the top level;
        # an empty list means the plugin (apply_plugin) was invoked but
        # produced zero compiled models. The most common cause is the
        # Qualcomm runtime libraries being absent: libQnnSystem.so from
        # the QAIRT SDK is not shipped with ai-edge-litert and must be
        # installed separately (Decision D-013, D-023).
        models_with_backend = getattr(result, "models_with_backend", None)
        n_with_backend = len(models_with_backend) if models_with_backend is not None else -1
        log.write(f"  models_with_backend len: {n_with_backend}\n")

        # 0-byte output binary on disk is the corroborating signal.
        empty_binary = False
        for f in aot_dir.rglob("*"):
            if f.is_file() and f.stat().st_size == 0:
                empty_binary = True
                log.write(f"    0-byte output binary: {f.relative_to(out_dir)}\n")

        if (n_with_backend == 0) or empty_binary:
            log.write("  AOT VERDICT: unsupported - models_with_backend=[] AND/OR 0-byte output\n")
            log.write("    Named root cause: libQnnSystem.so from QAIRT SDK absent (D-013, D-023)\n")
            return (
                CompileRecord(
                    backend_name=TARGET_QNN,
                    graph_scope=scope,
                    target=TARGET_SOC,
                    result="unsupported",
                    delegate_pct=0.0,
                    unsupported_ops=[],
                    log_path=None,
                ),
                log.getvalue(),
                {
                    **meta_extra,
                    "aot_dir": str(aot_dir.relative_to(out_dir)),
                    "aot_seconds": dt,
                    "stage_failed": "aot_compile_qnn_runtime_libs_missing",
                    "blocker": "libQnnSystem.so from QAIRT SDK absent; aot_compile returned CompilationResult with models_with_backend=[]; no QNN binary produced. Manual QAIRT SDK download from Qualcomm Developer Network required (D-013, D-023).",
                    
                },
            )

        # Otherwise compile actually produced models with backend
        return (
            CompileRecord(
                backend_name=TARGET_QNN,
                graph_scope=scope,
                target=TARGET_SOC,
                result="ok",
                delegate_pct=delegate_pct,
                unsupported_ops=unsupported_ops,
                log_path=None,  # filled in by caller
            ),
            log.getvalue(),
            {
                **meta_extra,
                "aot_dir": str(aot_dir.relative_to(out_dir)),
                "aot_seconds": dt,
                "stage_failed": None,
            },
        )
    except FileNotFoundError as e:
        # The diagnostic SDK-level failure: apply_plugin_main missing on
        # this platform's wheel.
        tb = traceback.format_exc()
        log.write(f"  AOT FAILED (SDK-level): {type(e).__name__}: {e}\n{tb}\n")
        msg = str(e)
        result = "unsupported" if "apply_plugin" in msg or "AOT might not be available" in msg else "failed"
        return (
            CompileRecord(
                backend_name=TARGET_QNN,
                graph_scope=scope,
                target=TARGET_SOC,
                result=result,
                delegate_pct=None,
                unsupported_ops=[],
                log_path=None,
            ),
            log.getvalue(),
            {
                **meta_extra,
                "stage_failed": "aot_compile_sdk_binary_missing",
                "exception": f"{type(e).__name__}: {msg}",
                "blocker": "apply_plugin_main native binary absent on macOS arm64 ai-edge-litert wheel",
            },
        )
    except Exception as e:
        tb = traceback.format_exc()
        log.write(f"  AOT FAILED: {type(e).__name__}: {e}\n{tb}\n")
        return (
            CompileRecord(
                backend_name=TARGET_QNN,
                graph_scope=scope,
                target=TARGET_SOC,
                result="failed",
                delegate_pct=None,
                unsupported_ops=[],
                log_path=None,
            ),
            log.getvalue(),
            {
                **meta_extra,
                "stage_failed": "aot_compile",
                "exception": f"{type(e).__name__}: {e}",
            },
        )


# ---------- main sweep ----------


def _host_versions() -> Dict[str, Any]:
    import torch
    versions: Dict[str, Any] = {}
    try:
        import litert_torch
        versions["litert_torch"] = getattr(litert_torch, "__version__", "unknown")
    except Exception:
        pass
    try:
        import ai_edge_torch
        from importlib.metadata import version as _pkg_version
        versions["ai_edge_torch"] = _pkg_version("ai-edge-torch")
    except Exception:
        pass
    for mod_name in ("torch", "ai_edge_litert", "transformers", "tokenizers", "numpy"):
        try:
            mod = __import__(mod_name)
            versions[mod_name] = getattr(mod, "__version__", "unknown")
        except Exception as e:
            versions[mod_name] = f"import_failed: {e}"
    return versions


def _run_single_scope(scope: str, out_dir: Path) -> int:
    """Run one scope and write its CompileRecord + log; return 0 on success.

    Used by the per-scope subprocess so each scope gets a fresh Python
    interpreter and unencumbered RAM. The "ok" exit just means the row was
    recorded; the row's `result` field captures the AOT verdict.
    """
    (out_dir / "compile_logs").mkdir(parents=True, exist_ok=True)
    (out_dir / "compile_records").mkdir(parents=True, exist_ok=True)

    model_id = next((m for (m, s) in SCOPES_QNN if s == scope), None)
    if model_id is None:
        print(f"unknown scope: {scope}", file=sys.stderr)
        return 2

    print(f">>> {model_id} / {scope} -> {TARGET_QNN}", flush=True)
    cr, log_text, meta_extra = _attempt_aot_compile(scope, model_id, out_dir=out_dir)
    log_path = out_dir / "compile_logs" / f"{scope}__{TARGET_QNN}.log"
    log_path.write_text(log_text)
    cr_dict = dataclasses.asdict(cr)
    cr_dict["log_path"] = str(log_path.relative_to(out_dir))
    cr_dict["meta"] = meta_extra
    cr_dict["model_id"] = model_id
    cr_record_path = out_dir / "compile_records" / f"{scope}__{TARGET_QNN}.json"
    cr_record_path.write_text(canonical_json(cr_dict))
    print(f"    => {cr.result} (stage_failed={meta_extra.get('stage_failed')})", flush=True)
    return 0


def _aggregate(out_dir: Path) -> int:
    """Read existing per-scope CompileRecords, emit summary.json + truth_table.md."""
    rows: List[Dict[str, Any]] = []
    qnn_failure_signatures: List[Dict[str, Any]] = []
    qnn_results = []

    for model_id, scope in SCOPES_QNN:
        cr_path = out_dir / "compile_records" / f"{scope}__{TARGET_QNN}.json"
        if not cr_path.exists():
            print(f"WARNING: missing {cr_path}", file=sys.stderr)
            qnn_results.append({"scope": scope, "model_id": model_id, "result": "missing", "stage_failed": "no_record_emitted"})
            qnn_failure_signatures.append({"scope": scope, "model_id": model_id, "stage_failed": "no_record_emitted", "exception": "scope did not produce a CompileRecord"})
            continue
        cr = json.loads(cr_path.read_text())
        log_path_rel = cr.get("log_path") or f"compile_logs/{scope}__{TARGET_QNN}.log"
        row = {
            "schema_version": SCHEMA_VERSION,
            "boundary": boundary_envelope(),
            "recorded_at": utc_now_iso(),
            "spec": {"model_id": model_id, "graph_scope": scope, "target": TARGET_QNN, "notes": None},
            "backend": TARGET_QNN,
            "result": cr["result"],
            "delegate_pct": cr.get("delegate_pct"),
            "unsupported_ops": cr.get("unsupported_ops") or [],
            "log_path": log_path_rel,
            "fallback_used": None,
            "meta": cr.get("meta", {}),
            "stage": "measured",
        }
        rows.append(row)
        qnn_results.append({"scope": scope, "model_id": model_id, "result": cr["result"], "stage_failed": cr.get("meta", {}).get("stage_failed")})
        if cr["result"] != "ok":
            qnn_failure_signatures.append(
                {"scope": scope, "model_id": model_id, "stage_failed": cr.get("meta", {}).get("stage_failed"), "exception": cr.get("meta", {}).get("exception")}
            )

    # Parity rows for cpu and vulkan_gpu via existing MacSimAdapter (stub).
    parity_targets = ("cpu", "vulkan_gpu")
    parity_adapter = MacSimAdapter()
    for model_id, scope in SCOPES_QNN:
        for parity_target in parity_targets:
            spec = ExportProbeSpec(model_id=model_id, graph_scope=scope, target=parity_target)
            r = _record_for(spec, parity_adapter)
            rd = dataclasses.asdict(r)
            rd["meta"] = {"note": "MacSim stub for falsifier-coverage parity; not a device claim."}
            rd["stage"] = "stub"
            rows.append(rd)

    summary = {
        "schema_version": SCHEMA_VERSION,
        "boundary": boundary_envelope(),
        "recorded_at": utc_now_iso(),
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "mac_version": platform.mac_ver()[0],
            "python": platform.python_version(),
            "node": platform.node(),
        },
        "package_versions": _host_versions(),
        "specs_count": len(rows),
        "qnn_specs_count": len(SCOPES_QNN),
        "qnn_results": qnn_results,
        "qnn_failure_signatures": qnn_failure_signatures,
        "rows": rows,
    }
    (out_dir / "summary.json").write_text(canonical_json(summary))
    _write_markdown_truth_table(rows, out_dir / "truth_table.md")

    extra = (
        "\n## Host\n\n"
        f"* platform: `{summary['host']['platform']}`\n"
        f"* machine: `{summary['host']['machine']}`\n"
        f"* python: `{summary['host']['python']}`\n"
        "\n## Versions\n\n"
        + "\n".join(f"* `{k}` = `{v}`" for k, v in summary["package_versions"].items())
        + "\n\n## QNN failure signatures\n\n"
    )
    if qnn_failure_signatures:
        for sig in qnn_failure_signatures:
            extra += f"* `{sig['scope']}` ({sig['model_id']}) — stage `{sig['stage_failed']}` — {sig['exception']}\n"
    else:
        extra += "* none — all QNN scopes returned `ok`.\n"
    with open(out_dir / "truth_table.md", "a") as fh:
        fh.write(extra)

    print(f"\n=== Phase 0G aggregate done. Output: {out_dir} ===")
    print(f"  qnn rows: {len(SCOPES_QNN)}")
    print(f"  parity rows: {len(SCOPES_QNN) * len(parity_targets)}")
    print(f"  qnn_failures: {len(qnn_failure_signatures)}")
    print(f"  summary.json + truth_table.md written.")
    return 0


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--scope", choices=[s for (_m, s) in SCOPES_QNN], help="run a single scope only")
    p.add_argument("--out-dir", help="reuse an existing output dir")
    p.add_argument("--aggregate", action="store_true", help="aggregate existing records into summary.json + truth_table.md")
    p.add_argument("--per-scope-subprocess", action="store_true", help="default: run each scope in its own python subprocess")
    args = p.parse_args()

    out_root = Path("runtime/reports/export_probe")
    if args.out_dir:
        out_dir = Path(args.out_dir)
    else:
        stamp = utc_now_iso().replace(":", "")
        out_dir = out_root / stamp
    (out_dir / "compile_logs").mkdir(parents=True, exist_ok=True)
    (out_dir / "compile_records").mkdir(parents=True, exist_ok=True)

    if args.scope:
        return _run_single_scope(args.scope, out_dir)
    if args.aggregate:
        return _aggregate(out_dir)

    # Default: run each scope in its own subprocess for memory isolation, then aggregate.
    import subprocess
    me = Path(__file__).resolve()
    rc_total = 0
    for _model_id, scope in SCOPES_QNN:
        print(f"\n=== Subprocess: {scope} ===", flush=True)
        rc = subprocess.call(
            [sys.executable, str(me), "--scope", scope, "--out-dir", str(out_dir)],
            cwd=str(Path(__file__).resolve().parents[2]),
        )
        if rc != 0:
            print(f"  scope {scope} subprocess exited rc={rc}", file=sys.stderr)
            rc_total = rc
    rc_aggregate = _aggregate(out_dir)
    return rc_aggregate or rc_total


if __name__ == "__main__":
    raise SystemExit(main())
