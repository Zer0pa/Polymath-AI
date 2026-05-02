"""Extract the embedded QNN context binary from a LiteRT apply_plugin .tflite.

Background
----------
ai-edge-litert's AOT compile produces a wrapped .tflite where the TFLite
flatbuffer holds a single ``DISPATCH_OP`` whose ``custom_options`` is a
flexbuffer mapping::

    bytecode_offset -> int (offset into the .tflite file where the QNN
                            context binary lives, immediately after the
                            flatbuffer's tail)
    bytecode_size   -> int (length of the QNN context binary)
    name            -> str ("qnn_partition_0", etc.)

The QNN context binary is appended verbatim to the tflite file. Extracting it
gives you a raw ``.qnn.bin`` that ``qnn-net-run --retrieve_context`` can load
on a Snapdragon device. This bypasses the LiteRT-on-Android runtime
requirement (which has no aarch64-android pip wheel — see D-019).

Usage
-----
    python scripts/host/extract_qnn_context.py \
        --tflite runtime/reports/export_probe/<ts>/qnn_aot/<scope>/<scope>_Qualcomm_SM8750_apply_plugin.tflite \
        --out runtime/reports/phase1a/<ts>/<scope>.qnn.bin

The host venv must have ``ai-edge-litert`` and ``flatbuffers`` installed
(both come with ai-edge-litert >= 2.1).
"""
from __future__ import annotations

import argparse
from pathlib import Path

from ai_edge_litert.schema_py_generated import Model as TFLModel
from flatbuffers import flexbuffers


def extract(tflite_path: Path) -> tuple[bytes, dict]:
    buf = tflite_path.read_bytes()
    m = TFLModel.GetRootAs(buf, 0)
    n_subgraphs = m.SubgraphsLength()
    if n_subgraphs != 1:
        raise ValueError(
            f"expected exactly 1 subgraph in apply_plugin tflite, got {n_subgraphs}"
        )
    sg = m.Subgraphs(0)
    n_ops = sg.OperatorsLength()
    if n_ops != 1:
        raise ValueError(
            f"expected exactly 1 DISPATCH_OP in apply_plugin tflite, got {n_ops}"
        )
    op = sg.Operators(0)
    co_bytes = bytes(op.CustomOptionsAsNumpy())
    fbm = flexbuffers.Loads(co_bytes)
    if not isinstance(fbm, dict):
        raise ValueError(f"DISPATCH_OP custom_options not a dict; got {type(fbm)}")
    for k in ("bytecode_offset", "bytecode_size", "name"):
        if k not in fbm:
            raise ValueError(f"DISPATCH_OP custom_options missing key {k!r}")
    offset = int(fbm["bytecode_offset"])
    size = int(fbm["bytecode_size"])
    name = str(fbm["name"])
    if offset + size > len(buf):
        raise ValueError(
            f"bytecode_offset({offset}) + bytecode_size({size}) > file size({len(buf)})"
        )
    return buf[offset : offset + size], {
        "name": name,
        "offset": offset,
        "size": size,
        "tflite_size": len(buf),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--tflite", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()

    qnn_bin, meta = extract(args.tflite)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(qnn_bin)
    print(
        f"extracted name={meta['name']!r} offset={meta['offset']} size={meta['size']} "
        f"-> {args.out} ({len(qnn_bin)} bytes)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
