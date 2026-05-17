#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


RMS_ROWS = 2
RMS_WIDTH = 4
RMS_EPSILON = 1.0e-5
RMS_INPUT = [0.5, -1.25, 2.0, -0.75, -1.5, 0.25, 0.75, 1.5]
RMS_WEIGHT = [1.0, 0.75, -0.5, 1.25]
RMS_GRAD_OUTPUT = [0.1, -0.2, 0.3, -0.4, 0.25, -0.15, 0.05, 0.35]

MATMUL_ROWS = 2
MATMUL_SHARED = 3
MATMUL_COLS = 4
MATMUL_LHS = [1.0, -2.0, 0.5, 0.25, 1.5, -1.0]
MATMUL_RHS = [
    0.5,
    -1.0,
    2.0,
    0.0,
    -0.75,
    1.25,
    -0.5,
    1.0,
    1.5,
    0.25,
    -1.25,
    0.75,
]
MATMUL_GRAD_OUTPUT = [0.2, -0.1, 0.4, -0.3, -0.25, 0.5, -0.15, 0.35]

DEFAULT_ABS_TOLERANCE = 1.0e-5
DEFAULT_REL_TOLERANCE = 1.0e-5


def inverse_rms(row_values: list[float], epsilon: float) -> float:
    square_mean = sum(value * value for value in row_values) / len(row_values)
    return 1.0 / math.sqrt(square_mean + epsilon)


def rms_norm_forward(
    input_values: list[float],
    weight: list[float],
    rows: int,
    width: int,
    epsilon: float,
) -> list[float]:
    output: list[float] = []
    for row in range(rows):
        row_values = input_values[row * width : (row + 1) * width]
        scale = inverse_rms(row_values, epsilon)
        output.extend(row_values[col] * scale * weight[col] for col in range(width))
    return output


def rms_norm_backward(
    input_values: list[float],
    weight: list[float],
    grad_output: list[float],
    rows: int,
    width: int,
    epsilon: float,
) -> tuple[list[float], list[float]]:
    grad_input = [0.0 for _ in input_values]
    grad_weight = [0.0 for _ in weight]

    for row in range(rows):
        offset = row * width
        row_values = input_values[offset : offset + width]
        grad_row = grad_output[offset : offset + width]
        scale = inverse_rms(row_values, epsilon)
        weighted_dot = sum(grad_row[col] * weight[col] * row_values[col] for col in range(width))
        row_scale = (scale**3) * weighted_dot / width

        for col in range(width):
            grad_weight[col] += grad_row[col] * row_values[col] * scale
            direct = grad_row[col] * weight[col] * scale
            grad_input[offset + col] = direct - (row_values[col] * row_scale)

    return grad_input, grad_weight


def matmul_forward(
    lhs: list[float],
    rhs: list[float],
    rows: int,
    shared: int,
    cols: int,
) -> list[float]:
    output = [0.0 for _ in range(rows * cols)]
    for row in range(rows):
        for col in range(cols):
            total = 0.0
            for inner in range(shared):
                total += lhs[(row * shared) + inner] * rhs[(inner * cols) + col]
            output[(row * cols) + col] = total
    return output


def matmul_backward(
    lhs: list[float],
    rhs: list[float],
    grad_output: list[float],
    rows: int,
    shared: int,
    cols: int,
) -> tuple[list[float], list[float]]:
    grad_lhs = [0.0 for _ in range(rows * shared)]
    grad_rhs = [0.0 for _ in range(shared * cols)]

    for row in range(rows):
        for inner in range(shared):
            total = 0.0
            for col in range(cols):
                total += grad_output[(row * cols) + col] * rhs[(inner * cols) + col]
            grad_lhs[(row * shared) + inner] = total

    for inner in range(shared):
        for col in range(cols):
            total = 0.0
            for row in range(rows):
                total += lhs[(row * shared) + inner] * grad_output[(row * cols) + col]
            grad_rhs[(inner * cols) + col] = total

    return grad_lhs, grad_rhs


def tolerances() -> dict[str, float]:
    return {"abs": DEFAULT_ABS_TOLERANCE, "rel": DEFAULT_REL_TOLERANCE}


def case(name: str, outputs: dict[str, list[float]]) -> dict[str, Any]:
    return {"name": name, "outputs": outputs, "tolerances": tolerances()}


def fixture_document() -> dict[str, Any]:
    rms_grad_input, rms_grad_weight = rms_norm_backward(
        RMS_INPUT, RMS_WEIGHT, RMS_GRAD_OUTPUT, RMS_ROWS, RMS_WIDTH, RMS_EPSILON
    )
    matmul_grad_lhs, matmul_grad_rhs = matmul_backward(
        MATMUL_LHS,
        MATMUL_RHS,
        MATMUL_GRAD_OUTPUT,
        MATMUL_ROWS,
        MATMUL_SHARED,
        MATMUL_COLS,
    )

    return {
        "schema_version": 1,
        "suite": "polymath_native_goldens",
        "metadata": {
            "fixture_set": "native_kernel_lab_v1",
            "generator": "polymath_native/tools/generate_golden.py",
            "precision": "python_float64",
        },
        "fixtures": {
            "rmsnorm": {
                "shape": {"rows": RMS_ROWS, "width": RMS_WIDTH},
                "epsilon": RMS_EPSILON,
                "input": RMS_INPUT,
                "weight": RMS_WEIGHT,
                "grad_output": RMS_GRAD_OUTPUT,
            },
            "matmul": {
                "shape": {
                    "rows": MATMUL_ROWS,
                    "shared": MATMUL_SHARED,
                    "cols": MATMUL_COLS,
                },
                "lhs": MATMUL_LHS,
                "rhs": MATMUL_RHS,
                "grad_output": MATMUL_GRAD_OUTPUT,
            },
        },
        "cases": [
            case(
                "rmsnorm_forward",
                {
                    "output": rms_norm_forward(
                        RMS_INPUT, RMS_WEIGHT, RMS_ROWS, RMS_WIDTH, RMS_EPSILON
                    )
                },
            ),
            case(
                "rmsnorm_backward",
                {"grad_input": rms_grad_input, "grad_weight": rms_grad_weight},
            ),
            case(
                "matmul_forward",
                {
                    "output": matmul_forward(
                        MATMUL_LHS, MATMUL_RHS, MATMUL_ROWS, MATMUL_SHARED, MATMUL_COLS
                    )
                },
            ),
            case(
                "matmul_backward",
                {"grad_lhs": matmul_grad_lhs, "grad_rhs": matmul_grad_rhs},
            ),
        ],
    }


def write_golden(output_path: Path) -> dict[str, Any]:
    document = fixture_document()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return document


def default_output_path() -> Path:
    return Path(__file__).resolve().parents[1] / "build" / "native_kernel_lab" / "golden_vectors.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate native kernel golden vectors.")
    parser.add_argument(
        "--output",
        type=Path,
        default=default_output_path(),
        help="Destination JSON path. Use '-' to write to stdout.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    document = fixture_document()

    if str(args.output) == "-":
        print(json.dumps(document, indent=2, sort_keys=True))
        return 0

    write_golden(args.output)
    print(json.dumps({"status": "pass", "output": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
