"""Phase 0G parallel path: PyTorch -> ONNX -> ONNX Runtime QNN EP AOT compile.

This is the alternate route to a SM8750 .bin context binary that does NOT go
through ai-edge-litert / TFLite. It uses Microsoft's onnxruntime-qnn build (from
the ORT-Nightly Visual Studio feed) to AOT-compile an ONNX graph for QNN HTP.

Why this exists
---------------
Yesterday's Phase 0G QAIRT 2.41 attempt failed at three independent SDK-level
blockers (D-024, D-025, D-026, D-027). Two of those (D-025/D-027) are inherent
to the TFLite frontend's EMBEDDING_LOOKUP op which fails for tied-embedding
models. ONNX uses Gather, not EMBEDDING_LOOKUP, so this path may bypass the
model-architecture blockers entirely.

Matrix (mirrors run_phase0g_aot.py):
  * Qwen/Qwen2.5-1.5B / tiny_block          -> litert_qnn_sm8750
  * Qwen/Qwen2.5-1.5B / qwen_block          -> litert_qnn_sm8750
  * Qwen/Qwen2.5-1.5B / qwen_frozen_subgraph-> litert_qnn_sm8750
  * HuggingFaceTB/SmolLM3-3B / smollm3_block -> litert_qnn_sm8750
  * HuggingFaceTB/SmolLM3-3B / smollm3_frozen_subgraph -> litert_qnn_sm8750

Environment expected:
  QAIRT_SDK_ROOT or QNN_SDK_ROOT pointing at /workspace/qairt-2.43/qairt/2.43.0.260128
  LD_LIBRARY_PATH including $QAIRT_SDK_ROOT/lib/x86_64-linux-clang
  .venv-onnxqnn active (has torch + onnxruntime-qnn 1.23.2 + QNNExecutionProvider)

Output (per scope):
  out_dir/onnx_qnn/<scope>/model.onnx        (ONNX intermediate)
  out_dir/onnx_qnn/<scope>/model_qnn.bin     (QNN context binary if AOT ok)
  out_dir/onnx_qnn/<scope>/aot_log.txt       (full ORT compile log)
  out_dir/compile_records/<scope>__litert_qnn_sm8750.json  (CompileRecord)

The output dir layout matches run_phase0g_aot.py so summaries can be merged.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any

TARGET_QNN = "litert_qnn_sm8750"

SCOPES = (
    ("Qwen/Qwen2.5-1.5B", "tiny_block"),
    ("Qwen/Qwen2.5-1.5B", "qwen_block"),
    ("Qwen/Qwen2.5-1.5B", "qwen_frozen_subgraph"),
    ("HuggingFaceTB/SmolLM3-3B", "smollm3_block"),
    ("HuggingFaceTB/SmolLM3-3B", "smollm3_frozen_subgraph"),
)


def utc_now_iso() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")


def _resolve_qnn_sdk_root() -> Path:
    for var in ("QAIRT_SDK_ROOT", "QNN_SDK_ROOT"):
        v = os.environ.get(var)
        if v and Path(v).exists():
            return Path(v)
    fallback = Path("/workspace/qairt-2.43/qairt/2.43.0.260128")
    if fallback.exists():
        return fallback
    raise RuntimeError("QAIRT SDK not found; set QAIRT_SDK_ROOT")


def _build_module(scope: str):
    import torch
    if scope == "tiny_block":
        return _tiny_block(), (1, 16, 64), (1, 16)
    if scope.startswith("qwen"):
        return _qwen_block_module(scope), (1, 16, 1536), (1, 16)
    if scope.startswith("smollm3"):
        return _smollm3_block_module(scope), (1, 16, 2048), (1, 16)
    raise ValueError(f"unknown scope: {scope}")


def _tiny_block():
    import torch.nn as nn
    class Block(nn.Module):
        def __init__(self):
            super().__init__()
            self.q = nn.Linear(64, 64, bias=False)
            self.k = nn.Linear(64, 64, bias=False)
            self.v = nn.Linear(64, 64, bias=False)
            self.o = nn.Linear(64, 64, bias=False)
            self.norm = nn.LayerNorm(64)

        def forward(self, x, _attn_mask):
            import torch
            x = self.norm(x)
            q, k, v = self.q(x), self.k(x), self.v(x)
            attn = torch.softmax(q @ k.transpose(-1, -2) / (64**0.5), dim=-1)
            return self.o(attn @ v)

    return Block().eval()


def _qwen_block_module(scope: str):
    from transformers import AutoModelForCausalLM
    import torch.nn as nn
    base = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-1.5B", torch_dtype="float32")
    layers = base.model.layers
    if scope == "qwen_block":
        sel = [layers[0]]
    else:  # qwen_frozen_subgraph: layers 1..26 (the ELO frozen middle)
        sel = list(layers[1:27])

    class Wrap(nn.Module):
        def __init__(self, sel):
            super().__init__()
            self.layers = nn.ModuleList(sel)

        def forward(self, hidden, attn_mask):
            for layer in self.layers:
                out = layer(hidden, attention_mask=attn_mask)
                hidden = out[0] if isinstance(out, tuple) else out
            return hidden

    return Wrap(sel).eval()


def _smollm3_block_module(scope: str):
    from transformers import AutoModelForCausalLM
    import torch.nn as nn
    base = AutoModelForCausalLM.from_pretrained(
        "HuggingFaceTB/SmolLM3-3B",
        torch_dtype="float32",
        trust_remote_code=True,
    )
    layers = base.model.layers
    if scope == "smollm3_block":
        sel = [layers[0]]
    else:
        sel = list(layers[1:31])  # frozen middle

    class Wrap(nn.Module):
        def __init__(self, sel):
            super().__init__()
            self.layers = nn.ModuleList(sel)

        def forward(self, hidden, attn_mask):
            for layer in self.layers:
                out = layer(hidden, attention_mask=attn_mask)
                hidden = out[0] if isinstance(out, tuple) else out
            return hidden

    return Wrap(sel).eval()


def _export_onnx(module, hidden_shape, mask_shape, out_path: Path) -> dict:
    import torch
    out_path.parent.mkdir(parents=True, exist_ok=True)
    hidden = torch.zeros(*hidden_shape, dtype=torch.float32)
    mask = torch.zeros(*mask_shape, dtype=torch.long)
    t0 = time.time()
    torch.onnx.export(
        module,
        (hidden, mask),
        str(out_path),
        input_names=["hidden", "attn_mask"],
        output_names=["out"],
        opset_version=17,
        dynamic_axes={"hidden": {0: "B", 1: "T"}, "attn_mask": {0: "B", 1: "T"}, "out": {0: "B", 1: "T"}},
    )
    return {"export_seconds": round(time.time() - t0, 2), "onnx_size_bytes": out_path.stat().st_size}


def _qnn_aot_compile(onnx_path: Path, qnn_sdk: Path, ctx_bin: Path, log_path: Path) -> dict:
    """Use onnxruntime-qnn to AOT compile to QNN HTP context binary.

    Returns: {"result": "ok|failed|unsupported", "delegate_pct": ..., "unsupported_ops": [...]}.
    """
    log = open(log_path, "w")
    log.write(f"[onnxruntime-qnn AOT] onnx={onnx_path} ctx_out={ctx_bin}\n")
    log.write(f"[onnxruntime-qnn AOT] qnn_sdk={qnn_sdk}\n")
    libqnnhtp = qnn_sdk / "lib" / "x86_64-linux-clang" / "libQnnHtp.so"
    log.write(f"[onnxruntime-qnn AOT] backend_path={libqnnhtp} exists={libqnnhtp.exists()}\n")
    if not libqnnhtp.exists():
        log.write("FAIL: libQnnHtp.so not found at expected path\n")
        return {
            "result": "failed",
            "stage_failed": "qnn_runtime_libs_missing",
            "blocker": f"libQnnHtp.so missing at {libqnnhtp}",
        }

    try:
        import onnxruntime as ort
    except Exception as exc:
        log.write(f"FAIL: cannot import onnxruntime: {exc}\n")
        return {"result": "failed", "stage_failed": "ort_import", "blocker": repr(exc)}

    log.write(f"[onnxruntime-qnn AOT] ort.__version__={ort.__version__}\n")
    providers = ort.get_available_providers()
    log.write(f"[onnxruntime-qnn AOT] available_providers={providers}\n")
    if "QNNExecutionProvider" not in providers:
        log.write("FAIL: QNNExecutionProvider not in available providers\n")
        return {
            "result": "failed",
            "stage_failed": "qnn_ep_not_available",
            "blocker": "QNNExecutionProvider not in onnxruntime available providers",
        }

    so = ort.SessionOptions()
    so.add_session_config_entry("ep.context_enable", "1")
    so.add_session_config_entry("ep.context_embed_mode", "0")
    so.add_session_config_entry("ep.context_file_path", str(ctx_bin))
    so.log_severity_level = 0

    provider_options = {
        "backend_path": str(libqnnhtp),
        "htp_arch": "75",  # SM8750
        "soc_model": "75",
        "htp_performance_mode": "burst",
    }

    t0 = time.time()
    try:
        log.write(f"[onnxruntime-qnn AOT] creating InferenceSession with QNN EP...\n")
        sess = ort.InferenceSession(
            str(onnx_path),
            sess_options=so,
            providers=[("QNNExecutionProvider", provider_options), "CPUExecutionProvider"],
        )
    except Exception as exc:
        tb = traceback.format_exc()
        log.write(f"FAIL: session creation: {exc}\n{tb}\n")
        return {
            "result": "failed",
            "stage_failed": "qnn_session_create",
            "blocker": repr(exc),
        }

    log.write(f"[onnxruntime-qnn AOT] session ready in {time.time()-t0:.1f}s\n")

    if not ctx_bin.exists() or ctx_bin.stat().st_size == 0:
        log.write(f"FAIL: ctx_bin {ctx_bin} not produced (size={ctx_bin.stat().st_size if ctx_bin.exists() else 0})\n")
        return {
            "result": "failed",
            "stage_failed": "qnn_ctx_bin_not_produced",
            "blocker": "QNN context binary not written despite session creation",
        }

    log.write(f"[onnxruntime-qnn AOT] OK ctx_bin_size={ctx_bin.stat().st_size}\n")

    used = [p for p in sess.get_providers() if p == "QNNExecutionProvider"]
    delegate_pct = 1.0 if used else 0.0
    log.write(f"[onnxruntime-qnn AOT] active_providers={sess.get_providers()} delegate_pct={delegate_pct}\n")

    return {
        "result": "ok" if delegate_pct > 0 else "unsupported",
        "delegate_pct": delegate_pct,
        "ctx_bin_size_bytes": ctx_bin.stat().st_size,
    }


def _run_one_scope(model_id: str, scope: str, out_dir: Path, qnn_sdk: Path) -> dict:
    out_dir = Path(out_dir)
    scope_dir = out_dir / "onnx_qnn" / scope
    scope_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = scope_dir / "model.onnx"
    ctx_bin = scope_dir / "model_qnn.bin"
    log_path = scope_dir / "aot_log.txt"

    record = {
        "schema_version": "1.0.0",
        "kind": "compile_record",
        "scope": scope,
        "model_id": model_id,
        "backend_name": TARGET_QNN,
        "target": "SM8750",
        "frontend": "onnxruntime-qnn",
        "started_at": utc_now_iso(),
    }
    print(f">>> [onnxqnn] {model_id} / {scope} -> {TARGET_QNN}", flush=True)

    try:
        module, hidden_shape, mask_shape = _build_module(scope)
    except Exception as exc:
        record["result"] = "failed"
        record["stage_failed"] = "build_module"
        record["blocker"] = repr(exc)
        record["finished_at"] = utc_now_iso()
        return record

    try:
        export_meta = _export_onnx(module, hidden_shape, mask_shape, onnx_path)
        record["onnx_export"] = export_meta
    except Exception as exc:
        tb = traceback.format_exc()
        log_path.write_text(f"ONNX export FAILED:\n{tb}\n")
        record["result"] = "failed"
        record["stage_failed"] = "onnx_export"
        record["blocker"] = repr(exc)
        record["finished_at"] = utc_now_iso()
        return record

    aot_meta = _qnn_aot_compile(onnx_path, qnn_sdk, ctx_bin, log_path)
    record.update(aot_meta)
    record["finished_at"] = utc_now_iso()
    return record


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--scope", choices=[s for (_m, s) in SCOPES], help="run a single scope")
    p.add_argument("--out-dir", required=True)
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    (out_dir / "compile_logs").mkdir(parents=True, exist_ok=True)
    (out_dir / "compile_records").mkdir(parents=True, exist_ok=True)

    qnn_sdk = _resolve_qnn_sdk_root()
    print(f"[onnxqnn] qnn_sdk={qnn_sdk}", flush=True)

    scopes_to_run = [(m, s) for (m, s) in SCOPES if (args.scope is None or s == args.scope)]
    rc = 0
    for model_id, scope in scopes_to_run:
        rec = _run_one_scope(model_id, scope, out_dir, qnn_sdk)
        rec_path = out_dir / "compile_records" / f"{scope}__{TARGET_QNN}__onnxqnn.json"
        rec_path.write_text(json.dumps(rec, indent=2, sort_keys=True))
        print(f"<<< [onnxqnn] {scope}: result={rec.get('result')} delegate_pct={rec.get('delegate_pct')}", flush=True)
        if rec.get("result") not in ("ok", "unsupported"):
            rc = 5

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
