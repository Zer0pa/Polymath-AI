#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

import generate_golden


class CommandFailure(RuntimeError):
    def __init__(self, command: list[str], returncode: int, output: str) -> None:
        super().__init__(f"command failed with exit code {returncode}: {' '.join(command)}")
        self.command = command
        self.returncode = returncode
        self.output = output


def run_command(command: list[str], cwd: Path | None = None) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    result = {
        "command": command,
        "returncode": completed.returncode,
        "output": completed.stdout,
    }
    if completed.returncode != 0:
        raise CommandFailure(command, completed.returncode, completed.stdout)
    return result


def executable_name() -> str:
    if sys.platform.startswith("win"):
        return "native_kernel_tests.exe"
    return "native_kernel_tests"


def find_test_executable(build_dir: Path, config: str) -> Path:
    candidates = [
        build_dir / executable_name(),
        build_dir / config / executable_name(),
        build_dir / "tests" / executable_name(),
        build_dir / "tests" / config / executable_name(),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    joined = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(f"native_kernel_tests executable not found; tried {joined}")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def case_map(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cases = document.get("cases", [])
    if not isinstance(cases, list):
        raise ValueError("document cases must be a list")
    mapped: dict[str, dict[str, Any]] = {}
    for test_case in cases:
        name = test_case.get("name")
        if not isinstance(name, str):
            raise ValueError("case name must be a string")
        if name in mapped:
            raise ValueError(f"duplicate case name: {name}")
        mapped[name] = test_case
    return mapped


def require_float_list(values: Any, label: str) -> list[float]:
    if not isinstance(values, list):
        raise ValueError(f"{label} must be a list")

    converted: list[float] = []
    for index, value in enumerate(values):
        if not isinstance(value, (int, float)):
            raise ValueError(f"{label}[{index}] must be numeric")
        converted.append(float(value))
    return converted


def compare_arrays(
    expected: list[float],
    actual: list[float],
    abs_tolerance: float,
    rel_tolerance: float,
) -> dict[str, Any]:
    if len(expected) != len(actual):
        return {
            "status": "fail",
            "reason": "length_mismatch",
            "expected_length": len(expected),
            "actual_length": len(actual),
        }

    max_abs_error = 0.0
    max_rel_error = 0.0
    first_mismatch: dict[str, Any] | None = None

    for index, (expected_value, actual_value) in enumerate(zip(expected, actual)):
        if not math.isfinite(actual_value):
            first_mismatch = {
                "index": index,
                "expected": expected_value,
                "actual": actual_value,
                "reason": "non_finite_actual",
            }
            break

        abs_error = abs(actual_value - expected_value)
        rel_error = abs_error / max(abs(expected_value), 1.0e-30)
        max_abs_error = max(max_abs_error, abs_error)
        max_rel_error = max(max_rel_error, rel_error)
        allowed = abs_tolerance + (rel_tolerance * abs(expected_value))
        if abs_error > allowed and first_mismatch is None:
            first_mismatch = {
                "index": index,
                "expected": expected_value,
                "actual": actual_value,
                "abs_error": abs_error,
                "rel_error": rel_error,
                "allowed": allowed,
            }

    return {
        "status": "pass" if first_mismatch is None else "fail",
        "count": len(expected),
        "max_abs_error": max_abs_error,
        "max_rel_error": max_rel_error,
        "first_mismatch": first_mismatch,
    }


def compare_outputs(
    expected_outputs: dict[str, Any],
    actual_outputs: dict[str, Any],
    abs_tolerance: float,
    rel_tolerance: float,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for name, expected_values_any in expected_outputs.items():
        if name not in actual_outputs:
            results.append({"name": name, "status": "fail", "reason": "missing_output"})
            continue

        expected_values = require_float_list(expected_values_any, f"expected {name}")
        actual_values = require_float_list(actual_outputs[name], f"actual {name}")
        output_result = compare_arrays(expected_values, actual_values, abs_tolerance, rel_tolerance)
        output_result["name"] = name
        results.append(output_result)

    for name in sorted(set(actual_outputs) - set(expected_outputs)):
        results.append({"name": name, "status": "fail", "reason": "extra_output"})

    return results


def compare_case(expected_case: dict[str, Any], actual_case: dict[str, Any]) -> dict[str, Any]:
    tolerances = expected_case.get("tolerances", {})
    abs_tolerance = float(tolerances.get("abs", generate_golden.DEFAULT_ABS_TOLERANCE))
    rel_tolerance = float(tolerances.get("rel", generate_golden.DEFAULT_REL_TOLERANCE))
    expected_outputs = expected_case.get("outputs", {})
    actual_outputs = actual_case.get("outputs", {})

    if not isinstance(expected_outputs, dict) or not isinstance(actual_outputs, dict):
        raise ValueError(f"case outputs must be objects: {expected_case.get('name')}")

    output_results = compare_outputs(
        expected_outputs, actual_outputs, abs_tolerance, rel_tolerance
    )
    status = "pass" if all(result["status"] == "pass" for result in output_results) else "fail"
    compared_values = sum(int(result.get("count", 0)) for result in output_results)

    return {
        "name": expected_case["name"],
        "status": status,
        "abs_tolerance": abs_tolerance,
        "rel_tolerance": rel_tolerance,
        "compared_values": compared_values,
        "outputs": output_results,
    }


def compare_documents(golden: dict[str, Any], actual: dict[str, Any]) -> list[dict[str, Any]]:
    expected_cases = case_map(golden)
    actual_cases = case_map(actual)
    results: list[dict[str, Any]] = []

    for name, expected_case in expected_cases.items():
        actual_case = actual_cases.get(name)
        if actual_case is None:
            results.append({"name": name, "status": "fail", "reason": "missing_case"})
            continue
        results.append(compare_case(expected_case, actual_case))

    for name in sorted(set(actual_cases) - set(expected_cases)):
        results.append({"name": name, "status": "fail", "reason": "extra_case"})

    return results


def summarize(cases: list[dict[str, Any]]) -> dict[str, int]:
    passed = sum(1 for test_case in cases if test_case["status"] == "pass")
    compared_values = sum(int(test_case.get("compared_values", 0)) for test_case in cases)
    return {
        "total_cases": len(cases),
        "passed_cases": passed,
        "failed_cases": len(cases) - passed,
        "compared_values": compared_values,
    }


def build_and_run(args: argparse.Namespace) -> dict[str, Any]:
    source_dir = args.source_dir.resolve()
    build_dir = args.build_dir.resolve()
    golden_path = args.golden.resolve()
    actual_path = args.actual.resolve()
    output_path = args.output.resolve()
    commands: list[dict[str, Any]] = []

    generate_golden.write_golden(golden_path)

    if not args.skip_build:
        commands.append(
            run_command(
                [
                    args.cmake,
                    "-S",
                    str(source_dir),
                    "-B",
                    str(build_dir),
                    f"-DCMAKE_BUILD_TYPE={args.config}",
                ]
            )
        )
        commands.append(
            run_command(
                [
                    args.cmake,
                    "--build",
                    str(build_dir),
                    "--target",
                    "native_kernel_tests",
                    "--config",
                    args.config,
                ]
            )
        )

    test_executable = find_test_executable(build_dir, args.config)
    actual_path.parent.mkdir(parents=True, exist_ok=True)
    commands.append(run_command([str(test_executable), "--output", str(actual_path)]))

    cases = compare_documents(load_json(golden_path), load_json(actual_path))
    summary = summarize(cases)
    status = "pass" if summary["failed_cases"] == 0 else "fail"

    result = {
        "schema_version": 1,
        "suite": "polymath_native_kernel_gate",
        "status": status,
        "paths": {
            "source_dir": str(source_dir),
            "build_dir": str(build_dir),
            "golden": str(golden_path),
            "actual": str(actual_path),
            "output": str(output_path),
        },
        "commands": [
            {"command": item["command"], "returncode": item["returncode"]} for item in commands
        ],
        "cases": cases,
        "summary": summary,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def default_source_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def default_build_dir() -> Path:
    return default_source_dir() / "build" / "native_kernel_lab"


def parse_args() -> argparse.Namespace:
    build_dir = default_build_dir()
    parser = argparse.ArgumentParser(description="Build and run native kernel correctness gates.")
    parser.add_argument("--source-dir", type=Path, default=default_source_dir())
    parser.add_argument("--build-dir", type=Path, default=build_dir)
    parser.add_argument("--golden", type=Path, default=build_dir / "golden_vectors.json")
    parser.add_argument("--actual", type=Path, default=build_dir / "actual_vectors.json")
    parser.add_argument("--output", type=Path, default=build_dir / "test_results.json")
    parser.add_argument("--config", default="Release")
    parser.add_argument("--cmake", default="cmake")
    parser.add_argument("--skip-build", action="store_true")
    return parser.parse_args()


def failure_document(error: Exception) -> dict[str, Any]:
    document: dict[str, Any] = {
        "schema_version": 1,
        "suite": "polymath_native_kernel_gate",
        "status": "error",
        "error": str(error),
    }
    if isinstance(error, CommandFailure):
        document["command"] = error.command
        document["returncode"] = error.returncode
        document["command_output"] = error.output
    return document


def main() -> int:
    try:
        result = build_and_run(parse_args())
    except Exception as error:
        result = failure_document(error)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
