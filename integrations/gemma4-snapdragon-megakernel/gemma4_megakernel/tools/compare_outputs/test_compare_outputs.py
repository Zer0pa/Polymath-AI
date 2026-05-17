from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path

import compare_outputs


def write_f32(path: Path, values: list[float]) -> None:
    path.write_bytes(struct.pack(f"<{len(values)}f", *values))


def write_u8(path: Path, values: list[int]) -> None:
    path.write_bytes(bytes(values))


def write_json(path: Path, values: dict[str, object]) -> None:
    path.write_text(json.dumps(values), encoding="utf-8")


class CompareOutputsTests(unittest.TestCase):
    def test_passes_with_non_pad_fp64_cosines(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            reference = directory / "reference.f32.bin"
            phone = directory / "phone.f32.bin"
            mask = directory / "attention_mask.u8.bin"
            manifest = directory / "manifest.json"
            contract = directory / "contract.json"

            write_f32(reference, [1.0, 0.0, 0.0, 1.0, 3.0, 9.0, 9.0, 9.0])
            write_f32(phone, [1.0, 0.0, 0.0, 1.0, 0.0, -4.0, -9.0, -9.0])
            write_u8(mask, [1, 1, 0, 0])
            write_json(
                manifest,
                {
                    "model_id": compare_outputs.EXPECTED_MODEL_ID,
                    "revision": compare_outputs.EXPECTED_REVISION,
                    "layer_index": 0,
                    "expected_output_shape": [1, 4, 2],
                },
            )
            write_json(contract, {"model_id": compare_outputs.EXPECTED_MODEL_ID})

            report_path = directory / "report.json"
            exit_code = compare_outputs.main(
                [
                    "--reference-output",
                    str(reference),
                    "--phone-output",
                    str(phone),
                    "--attention-mask",
                    str(mask),
                    "--shape",
                    "1,4,2",
                    "--manifest",
                    str(manifest),
                    "--contract",
                    str(contract),
                    "--backend",
                    "vulkan",
                    "--device-identity",
                    "nubia NX789J SM8750 FY25013101C8",
                    "--input-dtype",
                    "f32",
                    "--weight-dtype",
                    "f32",
                    "--accumulation-dtype",
                    "f32",
                    "--phone-command",
                    "adb shell run_gemma4_layer0",
                    "--reference-command",
                    "python reference.py",
                    "--report-json",
                    str(report_path),
                ]
            )

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["comparison"]["token_count"], 2)
            self.assertEqual(report["comparison"]["pad_token_count"], 2)
            self.assertEqual(report["comparison"]["percentiles"]["p50"], 1.0)

    def test_fails_when_p50_is_below_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            reference = directory / "reference.f32.bin"
            phone = directory / "phone.f32.bin"
            mask = directory / "attention_mask.u8.bin"
            manifest = directory / "manifest.json"

            write_f32(reference, [1.0, 0.0, 0.0, 1.0])
            write_f32(phone, [0.0, 1.0, 1.0, 0.0])
            write_u8(mask, [1, 1])
            write_json(
                manifest,
                {
                    "model_id": compare_outputs.EXPECTED_MODEL_ID,
                    "revision": compare_outputs.EXPECTED_REVISION,
                    "layer_index": 0,
                    "expected_output_shape": [1, 2, 2],
                },
            )

            report_path = directory / "report.json"
            exit_code = compare_outputs.main(
                [
                    "--reference-output",
                    str(reference),
                    "--phone-output",
                    str(phone),
                    "--attention-mask",
                    str(mask),
                    "--shape",
                    "1,2,2",
                    "--manifest",
                    str(manifest),
                    "--backend",
                    "opencl",
                    "--device-identity",
                    "NX789J SM8750",
                    "--input-dtype",
                    "f32",
                    "--weight-dtype",
                    "f16",
                    "--accumulation-dtype",
                    "f32",
                    "--phone-command",
                    "adb shell run",
                    "--reference-command",
                    "python reference.py",
                    "--report-json",
                    str(report_path),
                ]
            )

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 1)
            self.assertEqual(report["status"], "fail")
            self.assertEqual(report["comparison"]["percentiles"]["p50"], 0.0)
            self.assertEqual(report["comparison"]["failed_token_count"], 2)

    def test_wrong_revision_fails_provenance_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            reference = directory / "reference.f32.bin"
            phone = directory / "phone.f32.bin"
            mask = directory / "attention_mask.u8.bin"
            manifest = directory / "manifest.json"

            write_f32(reference, [1.0, 0.0])
            write_f32(phone, [1.0, 0.0])
            write_u8(mask, [1])
            write_json(
                manifest,
                {
                    "model_id": compare_outputs.EXPECTED_MODEL_ID,
                    "revision": "wrong",
                    "layer_index": 0,
                    "expected_output_shape": [1, 1, 2],
                },
            )

            report_path = directory / "report.json"
            exit_code = compare_outputs.main(
                [
                    "--reference-output",
                    str(reference),
                    "--phone-output",
                    str(phone),
                    "--attention-mask",
                    str(mask),
                    "--shape",
                    "1,1,2",
                    "--manifest",
                    str(manifest),
                    "--backend",
                    "vulkan",
                    "--device-identity",
                    "NX789J SM8750",
                    "--input-dtype",
                    "f32",
                    "--weight-dtype",
                    "f32",
                    "--accumulation-dtype",
                    "f32",
                    "--phone-command",
                    "adb shell run",
                    "--reference-command",
                    "python reference.py",
                    "--report-json",
                    str(report_path),
                ]
            )

            report = json.loads(report_path.read_text(encoding="utf-8"))
            revision_check = next(check for check in report["checks"] if check["name"] == "revision")
            self.assertEqual(exit_code, 1)
            self.assertEqual(revision_check["status"], "fail")

    def test_expected_layer_index_can_be_overridden(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            reference = directory / "reference.f32.bin"
            phone = directory / "phone.f32.bin"
            mask = directory / "attention_mask.u8.bin"
            manifest = directory / "manifest.json"

            write_f32(reference, [1.0, 0.0])
            write_f32(phone, [1.0, 0.0])
            write_u8(mask, [1])
            write_json(
                manifest,
                {
                    "model_id": compare_outputs.EXPECTED_MODEL_ID,
                    "revision": compare_outputs.EXPECTED_REVISION,
                    "layer_index": 1,
                    "expected_output_shape": [1, 1, 2],
                },
            )

            report_path = directory / "report.json"
            exit_code = compare_outputs.main(
                [
                    "--reference-output",
                    str(reference),
                    "--phone-output",
                    str(phone),
                    "--attention-mask",
                    str(mask),
                    "--shape",
                    "1,1,2",
                    "--manifest",
                    str(manifest),
                    "--backend",
                    "opencl",
                    "--device-identity",
                    "NX789J SM8750",
                    "--input-dtype",
                    "f32",
                    "--weight-dtype",
                    "f32",
                    "--accumulation-dtype",
                    "f32",
                    "--phone-command",
                    "adb shell run",
                    "--reference-command",
                    "python reference.py",
                    "--expected-layer-index",
                    "1",
                    "--report-json",
                    str(report_path),
                ]
            )

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["provenance"]["expected_layer_index"], 1)


if __name__ == "__main__":
    unittest.main()
