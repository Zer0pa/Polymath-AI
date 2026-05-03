"""Phase 1A.A.0 — replace synthetic FP32 zeros with real Qwen-tokenized inputs.

This is the smallest scientifically meaningful step beyond Phase 1A.B's
sustained-load-on-zeros characterization. It:

  1. Loads Qwen/Qwen2.5-1.5B and its tokenizer.
  2. Tokenizes N short English sentences and runs them through the model's
     embedding layer to produce real (1, 16, 1536) FP32 hidden-state tensors.
  3. Runs the host-side REFERENCE forward pass through the FROZEN MIDDLE
     (layers 1..26 — exactly the subgraph that was AOT-compiled to the
     2.3 GB Qualcomm SM8750 binary in Phase 0G) and saves the reference
     output for each sentence.
  4. Saves everything to a directory ready for ADB push:
        out_dir/inputs/<id>.bin             real-token hidden-state input
        out_dir/refs/<id>.ref.bin           host CPU reference output
        out_dir/sentences.json              the source text for traceability
        out_dir/manifest.json               id <-> sentence mapping
        out_dir/input_list.txt              relative paths for qnn-net-run

After running, the phone-side step is:
    adb push out_dir/inputs/* /data/local/tmp/phase1a/inputs/
    adb push out_dir/input_list.txt /data/local/tmp/phase1a/inputs/
    adb shell sh /data/local/tmp/phase1a/run_real_data_inference.sh

Then this script is re-invoked with --compare-mode pointing at the pulled
phone outputs, and computes cosine similarity per sentence. The Phase 1A.A.0
falsifier (D-033) is: cosine_per_token p50 >= 0.99 and p5 >= 0.95 across all
test sentences.

Usage:
    # Step 1 — generate real inputs + host references
    python scripts/host/phase1aa0_real_data.py \
        --mode generate --n 20 --out-dir runtime/reports/phase1aa0/<ts>/

    # Step 2 — (after adb push + on-device run + adb pull)
    python scripts/host/phase1aa0_real_data.py \
        --mode compare --out-dir runtime/reports/phase1aa0/<ts>/
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import torch


# --- Sentence corpus -------------------------------------------------------
# 20 English sentences sampled to avoid any restricted-license content. These
# are tokenizer-fertility and length neutral, deliberately mundane subject
# matter; project-internal content (no FLORES dependency required for this
# first-cut test).
SENTENCES = [
    "The quick brown fox jumps over the lazy dog at sunset.",
    "She placed the warm cup of tea on the wooden table.",
    "Snow fell quietly all morning across the empty fields.",
    "The library closes at six on weekdays and at four on Sundays.",
    "He read the entire book in a single afternoon by the window.",
    "Three children laughed as the puppy chased the falling leaves.",
    "Computers compile programs from human-readable text into machine code.",
    "Salt water freezes at a lower temperature than fresh water does.",
    "The musician tuned the violin before the rehearsal began.",
    "Bicycles outnumbered cars on the narrow road through the village.",
    "Mountains in this region rise nearly four kilometres above sea level.",
    "The recipe calls for two cups of flour and one cup of sugar.",
    "After the rain, the streets shone in the headlights of passing cars.",
    "Birds gather in the park each evening before flying south.",
    "She had been studying mathematics for nearly a decade by then.",
    "The robot vacuum bumps into furniture but eventually finds the charger.",
    "Coffee grows best in the highlands of certain tropical countries.",
    "He whistled a familiar tune as he walked down the long corridor.",
    "Astronomers detected a new comet passing close to the inner planets.",
    "The cat watched the goldfish for hours without moving an inch.",
]


def utc_ts() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def generate(n: int, out_dir: Path) -> int:
    """Generate N real-token inputs + host CPU reference outputs."""
    n = min(n, len(SENTENCES))
    sentences = SENTENCES[:n]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "inputs").mkdir(exist_ok=True)
    (out_dir / "refs").mkdir(exist_ok=True)

    print(f"[generate] loading Qwen2.5-1.5B (CPU)...", flush=True)
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-1.5B")
    model = AutoModelForCausalLM.from_pretrained(
        "Qwen/Qwen2.5-1.5B",
        torch_dtype=torch.float32,
        device_map="cpu",
    )
    model.eval()
    print(f"[generate] model loaded; layers={len(model.model.layers)} hidden={model.model.embed_tokens.weight.shape[1]}", flush=True)

    SEQ_LEN = 16
    HIDDEN = model.model.embed_tokens.weight.shape[1]

    # The frozen middle = layers 1..26 (Qwen2.5-1.5B has 28 layers; we hold
    # layers[0] as trainable and layers[27] as trainable, freezing 1..27 in
    # the canonical ELO Stage-1 layout — but for THIS test we match Phase 0G's
    # qwen_frozen_subgraph which compiled layers[1:27]).
    frozen_layers = model.model.layers[1:27]
    n_frozen = len(frozen_layers)
    assert n_frozen == 26, f"expected 26 frozen layers, got {n_frozen}"
    print(f"[generate] frozen middle: layers[1:27] = {n_frozen} layers", flush=True)

    manifest = {
        "schema_version": "1.0.0",
        "kind": "phase1aa0_real_data_input_manifest",
        "ts_utc": utc_ts(),
        "model_id": "Qwen/Qwen2.5-1.5B",
        "model_dtype": "float32",
        "frozen_middle": "layers[1:27] (26 layers; matches Phase 0G qwen_frozen_subgraph)",
        "seq_len": SEQ_LEN,
        "hidden_size": HIDDEN,
        "n_sequences": n,
        "sentences": [],
    }

    t0 = time.time()
    with torch.no_grad():
        for i, sentence in enumerate(sentences):
            t_a = time.time()
            # Tokenize + truncate/pad to SEQ_LEN
            ids = tok.encode(sentence, add_special_tokens=False)
            ids = ids[:SEQ_LEN]
            while len(ids) < SEQ_LEN:
                ids.append(tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id)
            ids_t = torch.tensor([ids], dtype=torch.long)
            # Embed (host)
            embeds = model.model.embed_tokens(ids_t)  # (1, 16, 1536)
            assert embeds.shape == (1, SEQ_LEN, HIDDEN), embeds.shape
            input_path = out_dir / "inputs" / f"input_{i:03d}.bin"
            embeds.contiguous().cpu().numpy().astype("float32").tofile(input_path)

            # Reference forward through frozen middle (host CPU).
            # We MIRROR EXACTLY the trace-wrap that the Phase 0G AOT runner used
            # at compile time (scripts/silicon/run_phase0g_aot.py
            # `_make_subgraph_tracewrap`):
            #   - hand-rolled RoPE cos/sin tables from rope_theta + head_dim
            #     in the model config (NOT the default transformers
            #     RotaryEmbedding implementation).
            #   - causal attention mask (zero where allowed, -inf where masked)
            #     of shape (1, 1, T, T).
            #   - position_ids = arange(seq_len).unsqueeze(0).
            #   - position_embeddings = (cos, sin) passed alongside.
            # If we use a different RoPE / mask layout, the on-device output
            # will be numerically uncorrelated with the host reference even
            # though both are individually "correct" — so this is the bit
            # that has to match byte-for-byte.
            cfg = model.config
            head_dim = getattr(cfg, "head_dim", cfg.hidden_size // cfg.num_attention_heads)
            rope_theta = float(getattr(cfg, "rope_theta", 10000.0))
            inv_freq = 1.0 / (rope_theta ** (torch.arange(0, head_dim, 2).float() / head_dim))
            pos = torch.arange(SEQ_LEN, dtype=torch.float32)
            freqs = torch.einsum("i,j->ij", pos, inv_freq)
            emb = torch.cat([freqs, freqs], dim=-1)
            cos = emb.cos()[None, :, :]
            sin = emb.sin()[None, :, :]
            mask_causal = torch.zeros(1, 1, SEQ_LEN, SEQ_LEN, dtype=torch.float32)
            mask_causal = mask_causal.masked_fill(
                torch.triu(torch.ones(SEQ_LEN, SEQ_LEN, dtype=torch.bool), diagonal=1),
                float("-inf"),
            )
            position_ids = torch.arange(SEQ_LEN, dtype=torch.long).unsqueeze(0)
            position_embeddings = (cos, sin)

            hidden = embeds
            for layer in frozen_layers:
                out = layer(
                    hidden_states=hidden,
                    attention_mask=mask_causal,
                    position_ids=position_ids,
                    position_embeddings=position_embeddings,
                    past_key_value=None,
                    output_attentions=False,
                    use_cache=False,
                )
                hidden = out[0] if isinstance(out, tuple) else out
            ref_path = out_dir / "refs" / f"input_{i:03d}.ref.bin"
            hidden.contiguous().cpu().numpy().astype("float32").tofile(ref_path)

            manifest["sentences"].append({
                "id": f"input_{i:03d}",
                "sentence": sentence,
                "token_ids": ids,
                "n_tokens_real": min(len(tok.encode(sentence, add_special_tokens=False)), SEQ_LEN),
                "host_ref_min": float(hidden.min()),
                "host_ref_max": float(hidden.max()),
                "host_ref_mean": float(hidden.mean()),
                "host_ref_std": float(hidden.std()),
            })
            t_b = time.time()
            print(f"[generate]   {i+1:3d}/{n}: ({t_b-t_a:.1f}s)  '{sentence[:60]}{'...' if len(sentence)>60 else ''}'", flush=True)

    # input_list.txt for qnn-net-run --input_list (relative paths)
    with open(out_dir / "input_list.txt", "w") as f:
        for i in range(n):
            f.write(f"inputs/input_{i:03d}.bin\n")

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    (out_dir / "sentences.json").write_text(json.dumps(sentences, indent=2))
    print(f"[generate] done in {time.time()-t0:.1f}s; out_dir={out_dir}")
    return 0


def compare(out_dir: Path, phone_outputs_dir: Path) -> int:
    """Compute cosine similarity per sequence between host CPU reference and
    on-device NPU output."""
    import numpy as np
    manifest = json.loads((out_dir / "manifest.json").read_text())
    n = manifest["n_sequences"]
    seq_len = manifest["seq_len"]
    hidden = manifest["hidden_size"]
    elements = seq_len * hidden  # 16 * 1536 = 24576
    bytes_expected = elements * 4  # FP32

    print(f"[compare] manifest n={n} seq_len={seq_len} hidden={hidden}")
    print(f"[compare] phone_outputs_dir={phone_outputs_dir}")

    results = []
    for i in range(n):
        ref_path = out_dir / "refs" / f"input_{i:03d}.ref.bin"
        ref = np.fromfile(ref_path, dtype=np.float32).reshape(1, seq_len, hidden)
        # Phone outputs land in a per-result subdir; qnn-net-run produces
        # output/Result_<i>/serving_default_output_0_output.raw
        npu_path = phone_outputs_dir / f"Result_{i}" / "serving_default_output_0_output.raw"
        if not npu_path.exists():
            print(f"[compare]   {i:03d}: SKIP — phone output missing at {npu_path}")
            continue
        if npu_path.stat().st_size != bytes_expected:
            print(f"[compare]   {i:03d}: SIZE MISMATCH — got {npu_path.stat().st_size} expected {bytes_expected}")
            continue
        npu = np.fromfile(npu_path, dtype=np.float32).reshape(1, seq_len, hidden)

        # Per-token cosine similarity (16 values), then aggregate
        cos_per_tok = []
        for t in range(seq_len):
            a = ref[0, t, :]
            b = npu[0, t, :]
            denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-12
            cos_per_tok.append(float(np.dot(a, b) / denom))
        # Whole-tensor cosine
        a_flat = ref.reshape(-1)
        b_flat = npu.reshape(-1)
        cos_total = float(np.dot(a_flat, b_flat) / ((np.linalg.norm(a_flat) * np.linalg.norm(b_flat)) + 1e-12))
        # MSE / max abs error
        diff = ref - npu
        mse = float((diff ** 2).mean())
        max_abs_err = float(np.abs(diff).max())

        results.append({
            "id": f"input_{i:03d}",
            "cos_total": cos_total,
            "cos_per_tok_min": min(cos_per_tok),
            "cos_per_tok_p5": float(np.percentile(cos_per_tok, 5)),
            "cos_per_tok_p50": float(np.percentile(cos_per_tok, 50)),
            "cos_per_tok_p95": float(np.percentile(cos_per_tok, 95)),
            "cos_per_tok_max": max(cos_per_tok),
            "mse": mse,
            "max_abs_err": max_abs_err,
            "ref_min": float(ref.min()), "ref_max": float(ref.max()), "ref_std": float(ref.std()),
            "npu_min": float(npu.min()), "npu_max": float(npu.max()), "npu_std": float(npu.std()),
        })
        print(f"[compare]   {i:03d}: cos_total={cos_total:.4f} cos_p50_per_tok={results[-1]['cos_per_tok_p50']:.4f} cos_p5={results[-1]['cos_per_tok_p5']:.4f} max_abs_err={max_abs_err:.4f}")

    # Aggregate — D-033 falsifier
    if not results:
        print("[compare] FATAL: no results computed")
        return 5
    cos_totals = [r["cos_total"] for r in results]
    cos_p5s = [r["cos_per_tok_p5"] for r in results]
    cos_min_per_tok = [r["cos_per_tok_min"] for r in results]
    p50_cos_total = float(__import__("statistics").median(cos_totals))
    min_cos_total = min(cos_totals)
    min_cos_per_tok = min(cos_min_per_tok)
    falsifier_passes = (p50_cos_total >= 0.99) and (min(cos_p5s) >= 0.95)

    summary = {
        "schema_version": "1.0.0",
        "kind": "phase1aa0_real_data_compare_summary",
        "ts_utc": utc_ts(),
        "n_compared": len(results),
        "n_total": n,
        "p50_cos_total": p50_cos_total,
        "min_cos_total": min_cos_total,
        "min_cos_per_tok": min_cos_per_tok,
        "min_cos_p5_per_tok": min(cos_p5s),
        "max_mse": max(r["mse"] for r in results),
        "max_max_abs_err": max(r["max_abs_err"] for r in results),
        "falsifier_d033_pass": falsifier_passes,
        "falsifier_d033_threshold": "cos_per_token p50 >= 0.99 AND min(cos_p5) >= 0.95",
        "per_sequence": results,
    }
    summary_path = out_dir / "compare_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True))

    print()
    print(f"[compare] === D-033 falsifier verdict ===")
    print(f"  n_compared:                   {len(results)} / {n}")
    print(f"  p50_cos_total:                {p50_cos_total:.6f}  (threshold >= 0.99)")
    print(f"  min_cos_total:                {min_cos_total:.6f}")
    print(f"  min(cos_p5_per_tok):          {min(cos_p5s):.6f}  (threshold >= 0.95)")
    print(f"  min_cos_per_tok (worst tok):  {min_cos_per_tok:.6f}")
    print(f"  max_mse:                      {summary['max_mse']:.6f}")
    print(f"  max_abs_err (any tensor):     {summary['max_max_abs_err']:.6f}")
    print(f"  PASS:                         {falsifier_passes}")
    print(f"  summary_path:                 {summary_path}")
    return 0 if falsifier_passes else 5


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["generate", "compare"], required=True)
    p.add_argument("--n", type=int, default=20, help="number of sentences (max 20 for the built-in corpus)")
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--phone-outputs", type=Path, default=None,
                   help="for compare mode: directory containing Result_NNN/ subdirs pulled from phone")
    args = p.parse_args()

    if args.mode == "generate":
        return generate(args.n, args.out_dir)
    elif args.mode == "compare":
        phone_outputs = args.phone_outputs or (args.out_dir / "phone_outputs")
        if not phone_outputs.exists():
            print(f"[compare] ERROR: --phone-outputs not found at {phone_outputs}", file=sys.stderr)
            return 4
        return compare(args.out_dir, phone_outputs)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
