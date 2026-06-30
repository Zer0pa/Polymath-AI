from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import Sequence


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts/termux/run_phase34_phone_accel_prereqs.py"
)
SPEC = importlib.util.spec_from_file_location("phase34_phone_accel_prereqs", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
probe = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = probe
SPEC.loader.exec_module(probe)


class FakeRunner:
    def __init__(self, responses: dict[tuple[str, ...], object] | None = None) -> None:
        self.responses = responses or {}
        self.commands: list[tuple[tuple[str, ...], float]] = []

    def run(self, command: Sequence[str], timeout_sec: float) -> object:
        key = tuple(command)
        self.commands.append((key, timeout_sec))
        return self.responses.get(
            key,
            probe.CommandResult(returncode=127, stderr="not found"),
        )


def test_build_payload_collects_phone_accel_prereqs_without_claims(monkeypatch) -> None:
    monkeypatch.setenv("SECRET_TOKEN", "do-not-emit")
    runner = FakeRunner(
        {
            ("uname", "-s"): probe.CommandResult(0, "Linux\n"),
            ("uname", "-r"): probe.CommandResult(0, "5.15.148-android13\n"),
            ("uname", "-m"): probe.CommandResult(0, "aarch64\n"),
            ("uname", "-a"): probe.CommandResult(0, "Linux localhost 5.15 aarch64 Android\n"),
            ("getprop", "ro.product.cpu.abi"): probe.CommandResult(0, "arm64-v8a\n"),
            ("getprop", "ro.product.cpu.abilist"): probe.CommandResult(
                0,
                "arm64-v8a,armeabi-v7a,armeabi\n",
            ),
            ("getprop", "ro.build.version.sdk"): probe.CommandResult(0, "35\n"),
            ("getprop", "ro.product.manufacturer"): probe.CommandResult(0, "nubia\n"),
            ("getprop", "ro.product.model"): probe.CommandResult(0, "NX769J\n"),
            ("getprop", "ro.board.platform"): probe.CommandResult(0, "kalama\n"),
            ("getprop", "ro.soc.model"): probe.CommandResult(0, "SM8550\n"),
            ("/data/data/com.termux/files/usr/bin/qnn-net-run", "--help"): probe.CommandResult(
                0,
                "Usage: qnn-net-run [options]\n",
            ),
            ("/data/data/com.termux/files/usr/bin/clinfo", "-l"): probe.CommandResult(
                0,
                "Platform #0: QUALCOMM Adreno\n",
            ),
        }
    )
    existing_paths = {
        "/data/data/com.termux/files/home",
        "/data/data/com.termux/files/usr",
        "/vendor/lib64/libQnnHtp.so",
        "/vendor/lib64/libOpenCL.so",
        "/data/data/com.termux/files/usr/bin/qnn-net-run",
        "/data/data/com.termux/files/usr/bin/clinfo",
    }
    glob_matches = {
        "/vendor/lib64/libQnn*.so": ["/vendor/lib64/libQnnHtp.so"],
        "/vendor/lib64/hw/vulkan.*.so": ["/vendor/lib64/hw/vulkan.adreno.so"],
        "/vendor/lib64/egl/lib*_adreno.so": ["/vendor/lib64/egl/libGLESv2_adreno.so"],
    }

    monkeypatch.setattr(
        probe,
        "read_text_prefix",
        lambda path, max_bytes: probe.TextReadResult(
            True,
            "MemTotal:       12000000 kB\n"
            "MemAvailable:    8000000 kB\n"
            "SwapTotal:       2000000 kB\n"
            "SwapFree:        1500000 kB\n",
        ),
    )
    monkeypatch.setattr(probe, "file_exists", lambda path: path in existing_paths)
    monkeypatch.setattr(
        probe,
        "path_presence",
        lambda path: {
            "path": path,
            "present": path in existing_paths,
            "inaccessible": False,
            "error": None,
        },
    )
    monkeypatch.setattr(probe, "is_executable", lambda path: path in existing_paths)
    monkeypatch.setattr(probe, "glob_paths", lambda pattern: glob_matches.get(pattern, []))
    monkeypatch.setattr(
        probe,
        "which_tool",
        lambda name: {
            "qnn-net-run": "/data/data/com.termux/files/usr/bin/qnn-net-run",
            "clinfo": "/data/data/com.termux/files/usr/bin/clinfo",
        }.get(name),
    )
    monkeypatch.setattr(
        probe,
        "disk_usage_bytes",
        lambda path: {
            "total_bytes": 1000,
            "used_bytes": 400,
            "free_bytes": 600,
        },
    )

    payload = probe.build_payload(
        label="fake_phone",
        runner=runner,
        probe_timeout_sec=1.5,
        cwd=Path("/repo"),
    )

    assert payload["schema_version"] == probe.SCHEMA_VERSION
    assert payload["status"] == "observed"
    assert payload["gate"]["enabled"] is False
    assert payload["phase3_ready_claim"] is False
    assert "no_gate_pass_claim" in payload["nonclaims"]
    assert payload["safety"]["environment_variables_included"] is False
    assert payload["device"]["uname"]["machine"]["value"] == "aarch64"
    assert payload["device"]["getprop"]["android_summary"]["primary_abi"] == "arm64-v8a"
    assert payload["device"]["getprop"]["android_summary"]["api_level"] == "35"
    assert payload["device"]["getprop"]["android_summary"]["model"] == "NX769J"
    assert payload["device"]["getprop"]["android_summary"]["platform"] == "kalama"
    assert payload["resources"]["meminfo"]["summary"]["MemTotal"]["kb"] == 12000000
    assert payload["accelerator_presence"]["summary"]["qnn_qairt_htp_present"] is True
    assert payload["accelerator_presence"]["summary"]["opencl_present"] is True
    assert payload["accelerator_presence"]["summary"]["vulkan_present"] is True
    assert any(
        item["label"] == "termux_home" and item["usage"]["free_bytes"] == 600
        for item in payload["resources"]["df_summary"]
    )
    assert any(
        item["name"] == "clinfo_list" and item["status"] == "ok"
        for item in payload["command_probes"]["probes"]
    )

    emitted = json.dumps(payload)
    assert "do-not-emit" not in emitted
    for command, timeout in runner.commands:
        assert timeout == 1.5
        assert command[0] not in {"env", "printenv", "sh", "bash", "zsh", "dash"}
        assert "source" not in command


def test_command_probes_can_be_skipped(monkeypatch) -> None:
    runner = FakeRunner(
        {
            ("uname", "-s"): probe.CommandResult(0, "Linux\n"),
            ("uname", "-r"): probe.CommandResult(0, "5.15\n"),
            ("uname", "-m"): probe.CommandResult(0, "aarch64\n"),
            ("uname", "-a"): probe.CommandResult(0, "Linux aarch64\n"),
        }
    )
    monkeypatch.setattr(probe, "read_text_prefix", lambda path, max_bytes: probe.TextReadResult(False))
    monkeypatch.setattr(probe, "file_exists", lambda path: False)
    monkeypatch.setattr(
        probe,
        "path_presence",
        lambda path: {
            "path": path,
            "present": False,
            "inaccessible": False,
            "error": None,
        },
    )
    monkeypatch.setattr(probe, "glob_paths", lambda pattern: [])
    monkeypatch.setattr(probe, "which_tool", lambda name: None)

    payload = probe.build_payload(runner=runner, include_command_probes=False)

    assert payload["command_probes"] == {
        "enabled": False,
        "timeout_sec": probe.DEFAULT_PROBE_TIMEOUT_SEC,
        "probes": [],
    }
    assert all(command[0] in {"uname", "getprop"} for command, _timeout in runner.commands)


def test_main_writes_full_json_payload(monkeypatch, tmp_path: Path, capsys) -> None:
    payload = {
        "schema_version": probe.SCHEMA_VERSION,
        "status": "observed",
        "phase3_ready_claim": False,
        "nonclaims": ["no_phase3_ready_claim"],
    }
    monkeypatch.setattr(probe, "build_payload", lambda **kwargs: payload)
    output = tmp_path / "phase34_phone_accel_prereqs.json"

    rc = probe.main(["--output", str(output), "--skip-command-probes"])

    assert rc == 0
    assert json.loads(output.read_text(encoding="utf-8")) == payload
    assert json.loads(capsys.readouterr().out) == payload


def test_permission_denied_path_probe_is_structured_evidence(monkeypatch) -> None:
    class DeniedPath:
        def __init__(self, path: str) -> None:
            self.path = path

        def exists(self) -> bool:
            raise PermissionError(13, "Permission denied", self.path)

    monkeypatch.setattr(probe, "Path", DeniedPath)

    result = probe.path_presence("/vendor/lib64/libQnnSystem.so")

    assert result["path"] == "/vendor/lib64/libQnnSystem.so"
    assert result["present"] is True
    assert result["inaccessible"] is True
    assert "PermissionError" in result["error"]
