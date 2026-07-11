from __future__ import annotations

import importlib.util
import hashlib
from pathlib import Path
import struct
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/termux/run_e4b_l2_int16_phone_gate.py"
SPEC = importlib.util.spec_from_file_location("e4b_l2_int16_phone_gate", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
phone_gate = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = phone_gate
SPEC.loader.exec_module(phone_gate)


def test_s16_decode_uses_frozen_exact_power_of_two_scale():
    payload = struct.pack("<hhhh", -32768, -1, 0, 32767)
    assert phone_gate.decode_s16(payload, 1.0 / 256.0) == [
        -128.0,
        -1.0 / 256.0,
        0.0,
        32767.0 / 256.0,
    ]


def test_qnn_command_skips_q_proj_and_requests_native_s16_io(tmp_path: Path):
    command = phone_gate.build_qnn_command(
        qnn_net_run=tmp_path / "qnn-net-run",
        qairt_root=tmp_path / "qairt",
        context_path=tmp_path / "context.bin",
        input_list=tmp_path / "input.txt",
        output_dir=tmp_path / "output",
    )
    assert f"--input_list=__,{tmp_path / 'input.txt'}" in command
    assert "--use_native_input_files" in command
    assert "--use_native_output_files" in command
    assert command.count("1") == 2


def test_identical_full_width_vectors_pass_frozen_combined_limits(tmp_path: Path):
    values = [float(index - 32) / 16.0 for index in range(64)]
    reference = tmp_path / "reference.bf16.raw"
    candidate = tmp_path / "candidate.s16.raw"
    bf16 = bytearray()
    s16 = bytearray()
    for value in values:
        bits = struct.unpack("<I", struct.pack("<f", value))[0] >> 16
        bf16.extend(struct.pack("<H", bits))
        s16.extend(struct.pack("<h", round(value * 256.0)))
    reference.write_bytes(bytes(bf16))
    candidate.write_bytes(bytes(s16))
    case = phone_gate.CaseContract(
        case_id="test",
        input_path=tmp_path / "unused",
        input_sha256="0" * 64,
        reference_path=reference,
        reference_sha256=phone_gate.sha256_path(reference),
        output_bytes=len(s16),
    )
    limits = {
        "max_abs": 0.1875,
        "rms": 0.03,
        "relative_l2": 0.0075,
        "cosine_min": 0.99998,
        "softmax_js_divergence_max": 2.0e-6,
        "top_k_set_overlap_min": 0.9375,
        "top_1_equal": True,
    }
    result = phone_gate.adjudicate_case(
        case=case,
        output_path=candidate,
        output_scale=1.0 / 256.0,
        limits=limits,
    )
    assert result["passed"] is True
    assert result["failures"] == []


def test_relative_path_rejects_escape(tmp_path: Path):
    try:
        phone_gate.resolve_relative(tmp_path, "../escape")
    except phone_gate.PhoneGateError:
        pass
    else:
        raise AssertionError("path escape was accepted")


def test_execution_code_bundle_requires_every_hash(monkeypatch, tmp_path: Path):
    source = tmp_path / "module.py"
    source.write_text("value = 1\n", encoding="utf-8")
    monkeypatch.setattr(phone_gate, "ROOT", tmp_path)
    prereg = {
        "execution_code": {
            "files": [
                {
                    "relative_path": "module.py",
                    "bytes": source.stat().st_size,
                    "sha256": phone_gate.sha256_path(source),
                }
            ]
        }
    }
    phone_gate.validate_execution_code(prereg)
    source.write_text("value = 2\n", encoding="utf-8")
    try:
        phone_gate.validate_execution_code(prereg)
    except phone_gate.PhoneGateError:
        pass
    else:
        raise AssertionError("execution-code drift was accepted")


def test_qnn_environment_includes_proven_android_fastrpc_resolution(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LD_LIBRARY_PATH", "/existing/lib")
    environment = phone_gate.qnn_environment(
        tmp_path / "qairt",
        phone_gate.SYSTEM_LD_LIBRARY_DIRS,
    )
    assert environment["LD_LIBRARY_PATH"].split(":") == [
        str(tmp_path / "qairt/lib/aarch64-android"),
        "/vendor/lib64",
        "/system/lib64",
        "/existing/lib",
    ]


def test_runtime_resolution_requires_exact_fastrpc_set(monkeypatch, tmp_path: Path):
    vendor = tmp_path / "vendor/lib64"
    system = tmp_path / "system/lib64"
    vendor.mkdir(parents=True)
    system.mkdir(parents=True)
    libraries = []
    required = set()
    for name, payload in (("libadsprpc.so", b"adsp"), ("libcdsprpc.so", b"cdsp")):
        path = vendor / name
        path.write_bytes(payload)
        required.add(path)
        libraries.append(
            {
                "absolute_path": str(path),
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    monkeypatch.setattr(phone_gate, "SYSTEM_LD_LIBRARY_DIRS", (vendor, system))
    monkeypatch.setattr(phone_gate, "REQUIRED_FASTRPC_LIBRARIES", required)
    prereg = {
        "runtime_resolution_topology": {
            "system_ld_library_dirs": [str(vendor), str(system)],
            "fastrpc_libraries": libraries,
        }
    }
    assert phone_gate.validate_runtime_resolution(prereg) == (vendor, system)
    prereg["runtime_resolution_topology"]["fastrpc_libraries"].pop()
    try:
        phone_gate.validate_runtime_resolution(prereg)
    except phone_gate.PhoneGateError:
        pass
    else:
        raise AssertionError("incomplete FastRPC dependency set was accepted")
