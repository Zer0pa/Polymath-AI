#!/usr/bin/env python3
"""Run Phase 11 H11-G HTP mutable-adapter / zero-order classification gate."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any


PHONE_SERIAL = "FY25013101C8"
PHONE_ROOT = "/data/local/tmp/polymath_gemma4_gate"
PHONE_QAIRT_ROOT = "/data/local/tmp/qairt-2.44"
PHONE_CONTEXT = "/data/local/tmp/phase1a/qwen_block.qnn.bin"
PHONE_INPUT_LIST = "/data/local/tmp/phase1a/input_list.txt"
RUNPOD_SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=30", "root@38.80.152.147", "-p", "31002", "-i", os.path.expanduser("~/.ssh/id_ed25519")]
RUNPOD_QAIRT_ROOT = "/workspace/qairt-2.44/qairt/2.44.0.260225"
RUNPOD_PYTHON = "/workspace/Polymath-AI/.venv/bin/python"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(command: list[str], *, check: bool = True, input_text: str | None = None, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if check and completed.returncode != 0:
        joined = " ".join(shlex.quote(part) for part in command)
        raise RuntimeError(
            f"command failed ({completed.returncode}): {joined}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def adb(args: list[str], *, check: bool = True, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return run(["adb", "-s", PHONE_SERIAL, *args], check=check, timeout=timeout)


def adb_shell_script(script: str, *, check: bool = True, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return run(
        ["adb", "-s", PHONE_SERIAL, "shell", "sh", "-s"],
        check=check,
        input_text=script,
        timeout=timeout,
    )


def ssh_script(script: str, *, check: bool = True, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return run([*RUNPOD_SSH, "bash", "-s"], check=check, input_text=script, timeout=timeout)


def q(value: str) -> str:
    return shlex.quote(value)


def truncate(text: str, limit: int = 12000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def capture_step(name: str, completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return {
        "name": name,
        "returncode": completed.returncode,
        "stdout_tail": truncate(completed.stdout),
        "stderr_tail": truncate(completed.stderr),
        "status": "pass" if completed.returncode == 0 else "fail",
    }


def run_runpod_env_probe() -> dict[str, Any]:
    script = f"""
set +e
Q={q(RUNPOD_QAIRT_ROOT)}
PY={q(RUNPOD_PYTHON)}
echo "qairt_root=$Q"
echo "python=$PY"
test -d "$Q"; echo "qairt_root_exists=$?"
test -x "$PY"; echo "python_exists=$?"
echo "=== expected host tools ==="
for tool in qairt-converter qairt-lora-importer qairt-lora-adapter-bin-updater qnn-context-binary-generator qnn-context-binary-utility qnn-net-run; do
  path="$Q/bin/x86_64-linux-clang/$tool"
  if [ -x "$path" ]; then echo "$tool present"; else echo "$tool missing"; fi
done
echo "=== expected phone tools in SDK payload ==="
for tool in qairt-lora-adapter-bin-updater qnn-context-binary-generator qnn-context-binary-utility qnn-net-run qnn-platform-validator; do
  path="$Q/bin/aarch64-android/$tool"
  if [ -x "$path" ]; then echo "$tool present"; else echo "$tool missing"; fi
done
echo "=== apply binary section headers ==="
grep -n "QnnContext_applyBinarySection\\|QNN_CONTEXT_SECTION_UPDATABLE\\|QnnContext_GetBinarySection\\|contextApplyBinarySection" "$Q/include/QNN/QnnContext.h" "$Q/include/QNN/QnnInterface.h" "$Q/include/QNN/QnnProperty.h" 2>/dev/null | head -120
echo "=== python imports with QAIRT PYTHONPATH ==="
PYTHONPATH="$Q/lib/python" "$PY" - <<'PY'
mods = ["numpy", "yaml", "pydantic", "onnx", "qti", "qti.aisw", "qti.aisw.lora"]
for mod in mods:
    try:
        imported = __import__(mod)
        print(f"{{mod}}: ok {{getattr(imported, '__version__', '')}}")
    except Exception as exc:
        print(f"{{mod}}: ERR {{type(exc).__name__}}: {{exc}}")
PY
echo "=== qairt converter lora help ==="
PYTHONPATH="$Q/lib/python" LD_LIBRARY_PATH="$Q/lib/x86_64-linux-clang:$LD_LIBRARY_PATH" "$PY" "$Q/bin/x86_64-linux-clang/qairt-converter" --help 2>&1 | grep -A8 -B8 "lora_weight_list"
echo "converter_help_rc=${{PIPESTATUS[0]}}"
echo "=== qairt lora importer help ==="
PYTHONPATH="$Q/lib/python" LD_LIBRARY_PATH="$Q/lib/x86_64-linux-clang:$LD_LIBRARY_PATH" "$PY" "$Q/bin/x86_64-linux-clang/qairt-lora-importer" --help 2>&1 | head -120
echo "lora_importer_rc=${{PIPESTATUS[0]}}"
echo "=== x86 lora updater help ==="
LD_LIBRARY_PATH="$Q/lib/x86_64-linux-clang:$LD_LIBRARY_PATH" "$Q/bin/x86_64-linux-clang/qairt-lora-adapter-bin-updater" --help 2>&1 | head -120
echo "lora_updater_rc=${{PIPESTATUS[0]}}"
"""
    completed = ssh_script(script, check=False, timeout=180)
    return capture_step("runpod_qairt_env_probe", completed)


def run_runpod_api_compile_probe() -> dict[str, Any]:
    script = f"""
set -e
Q={q(RUNPOD_QAIRT_ROOT)}
TMP=$(mktemp -d /tmp/h11g_qnn_api_probe.XXXXXX)
cat > "$TMP/qnn_apply_probe.cpp" <<'CPP'
#include <QNN/QnnContext.h>
#include <QNN/QnnInterface.h>
#include <QNN/QnnProperty.h>
#include <cstdint>
#include <iostream>

int main() {{
  QnnContext_SectionType_t section = QNN_CONTEXT_SECTION_UPDATABLE;
  QnnContext_Buffer_t buffer{{}};
  buffer.version = QNN_CONTEXT_BUFFER_VERSION_1;
  buffer.v1.memType = QNN_CONTEXTMEMTYPE_RAW;
  QnnContext_ApplyBinarySectionFn_t apply_fn = nullptr;
  QnnContext_GetBinarySectionFn_t get_fn = nullptr;
  QnnContext_GetBinarySectionSizeFn_t size_fn = nullptr;
  std::cout << "section=" << static_cast<int>(section)
            << " buffer_version=" << static_cast<int>(buffer.version)
            << " mem_type=" << static_cast<int>(buffer.v1.memType)
            << " apply_ptr_null=" << (apply_fn == nullptr)
            << " get_ptr_null=" << (get_fn == nullptr)
            << " size_ptr_null=" << (size_fn == nullptr)
            << "\\n";
  return section == QNN_CONTEXT_SECTION_UPDATABLE ? 0 : 2;
}}
CPP
g++ -std=c++17 -I"$Q/include" "$TMP/qnn_apply_probe.cpp" -o "$TMP/qnn_apply_probe"
"$TMP/qnn_apply_probe"
rm -rf "$TMP"
"""
    completed = ssh_script(script, check=False, timeout=120)
    return capture_step("runpod_qnn_apply_api_compile_probe", completed)


def run_phone_context_utility(run_id: str, local_report_dir: Path) -> dict[str, Any]:
    phone_out = f"{PHONE_ROOT}/phase11/{run_id}/h11g_context_utility"
    script = f"""
set -e
Q={q(PHONE_QAIRT_ROOT)}
OUT={q(phone_out)}
rm -rf "$OUT"
mkdir -p "$OUT"
export LD_LIBRARY_PATH="$Q/lib/aarch64-android:$LD_LIBRARY_PATH"
"$Q/bin/aarch64-android/qnn-context-binary-utility" --context_binary={q(PHONE_CONTEXT)} --json_file="$OUT/context_info.json"
grep -n "graphName\\|numUpdateableTensors\\|updateableTensors\\|contextBlobSize" "$OUT/context_info.json" | head -80
"""
    completed = adb_shell_script(script, check=False, timeout=180)
    pulled = False
    local_context = local_report_dir / "phone_context_info.json"
    if completed.returncode == 0:
        pulled = adb(["pull", f"{phone_out}/context_info.json", str(local_context)], check=False, timeout=120).returncode == 0
    result = capture_step("phone_context_binary_utility", completed)
    result["phone_output_dir"] = phone_out
    result["context_info_pulled"] = pulled
    result["local_context_info"] = str(local_context) if pulled else None
    if pulled:
        info = json.loads(local_context.read_text(encoding="utf-8"))
        graphs = info.get("info", {}).get("graphs", [])
        result["graphs"] = [
            {
                "graph_name": graph.get("info", {}).get("graphName"),
                "num_updateable_tensors": graph.get("info", {}).get("numUpdateableTensors"),
                "updateable_tensors": graph.get("info", {}).get("updateableTensors", []),
                "num_graph_inputs": graph.get("info", {}).get("numGraphInputs"),
                "num_graph_outputs": graph.get("info", {}).get("numGraphOutputs"),
            }
            for graph in graphs
        ]
        result["context_blob_size"] = info.get("info", {}).get("contextBlobSize")
    return result


def run_phone_htp_inference(run_id: str, local_report_dir: Path) -> dict[str, Any]:
    phone_out = f"{PHONE_ROOT}/phase11/{run_id}/h11g_htp_inference"
    script = f"""
set -e
Q={q(PHONE_QAIRT_ROOT)}
OUT={q(phone_out)}
rm -rf "$OUT"
mkdir -p "$OUT"
export LD_LIBRARY_PATH="$Q/lib/aarch64-android:/vendor/dsp/cdsp:/vendor/lib64:$LD_LIBRARY_PATH"
export ADSP_LIBRARY_PATH="$Q/lib/hexagon-v79/unsigned;/vendor/dsp/cdsp;/vendor/lib/rfsa/adsp;/system/lib/rfsa/adsp;/dsp"
cd /data/local/tmp/phase1a
"$Q/bin/aarch64-android/qnn-net-run" --retrieve_context {q(PHONE_CONTEXT)} --backend "$Q/lib/aarch64-android/libQnnHtp.so" --input_list {q(PHONE_INPUT_LIST)} --output_dir "$OUT" --num_inferences 1 --profiling_level basic --log_level info
sed -n '1,220p' "$OUT/execution_metadata.yaml"
"""
    completed = adb_shell_script(script, check=False, timeout=240)
    pulled = False
    local_meta = local_report_dir / "phone_htp_inference_execution_metadata.yaml"
    if completed.returncode == 0:
        pulled = adb(["pull", f"{phone_out}/execution_metadata.yaml", str(local_meta)], check=False, timeout=120).returncode == 0
    result = capture_step("phone_htp_frozen_forward_inference", completed)
    result["phone_output_dir"] = phone_out
    result["execution_metadata_pulled"] = pulled
    result["local_execution_metadata"] = str(local_meta) if pulled else None
    result["inference_completed"] = "inferences_completed: 1" in completed.stdout
    result["qnn_partition_seen"] = "qnn_partition_0" in completed.stdout
    return result


def run_phone_tool_surface() -> dict[str, Any]:
    script = f"""
set +e
Q={q(PHONE_QAIRT_ROOT)}
export LD_LIBRARY_PATH="$Q/lib/aarch64-android:$LD_LIBRARY_PATH"
echo "=== tool presence ==="
for tool in qairt-lora-adapter-bin-updater qnn-context-binary-generator qnn-context-binary-utility qnn-net-run qnn-platform-validator; do
  path="$Q/bin/aarch64-android/$tool"
  if [ -x "$path" ]; then echo "$tool present"; else echo "$tool missing"; fi
done
echo "=== qnn-net-run binary_updates help ==="
"$Q/bin/aarch64-android/qnn-net-run" --help 2>&1 | grep -A18 -B8 "binary_updates"
echo "=== lora updater help ==="
"$Q/bin/aarch64-android/qairt-lora-adapter-bin-updater" --help 2>&1 | head -140
"""
    completed = adb_shell_script(script, check=False, timeout=120)
    return capture_step("phone_qairt_tool_surface", completed)


def build_classification(checks: dict[str, Any]) -> dict[str, Any]:
    context_graphs = checks["phone_context_utility"].get("graphs", [])
    updateable_tensor_count = sum(int(graph.get("num_updateable_tensors") or 0) for graph in context_graphs)
    frozen_forward_ok = (
        checks["phone_htp_inference"].get("status") == "pass"
        and checks["phone_htp_inference"].get("inference_completed")
        and checks["phone_htp_inference"].get("qnn_partition_seen")
    )
    api_compile_ok = checks["runpod_api_compile_probe"].get("status") == "pass"
    phone_tools_ok = checks["phone_tool_surface"].get("status") == "pass"
    host_env_ok = (
        checks["runpod_qairt_env_probe"].get("status") == "pass"
        and "ERR" not in checks["runpod_qairt_env_probe"].get("stdout_tail", "")
    )

    blockers: list[str] = []
    if not api_compile_ok:
        blockers.append("RunPod QNN apply-binary-section API compile probe failed")
    if not phone_tools_ok:
        blockers.append("Phone QAIRT tool surface probe failed")
    if not frozen_forward_ok:
        blockers.append("Phone HTP frozen-forward inference did not complete")
    if updateable_tensor_count <= 0:
        blockers.append("Current phone QNN context has zero updateable tensors, so QnnContext_applyBinarySection has no valid Gemma/Qwen section to apply")
    if not host_env_ok:
        blockers.append("RunPod QAIRT Python/x86 LoRA tooling is not fully runnable in the current shell environment")

    mutable_section_promoted = updateable_tensor_count > 0 and api_compile_ok and phone_tools_ok
    zero_order_promoted = False
    classification = "blocked"
    if frozen_forward_ok and not mutable_section_promoted:
        classification = "frozen_forward_only_mutable_blocked"
    if mutable_section_promoted:
        classification = "updateable_section_available_zero_order_not_attempted"

    return {
        "classification": classification,
        "frozen_forward_promoted": frozen_forward_ok,
        "teacher_role_allowed": frozen_forward_ok,
        "mutable_section_promoted": mutable_section_promoted,
        "zero_order_promoted": zero_order_promoted,
        "normal_htp_backprop_promoted": False,
        "updateable_tensor_count": updateable_tensor_count,
        "blockers": blockers,
        "next_for_h11h": "Use HTP only as a frozen-forward/teacher candidate if useful; run H11-H training/update path through the H11-F OpenCL daemon lane unless an updateable context is produced later.",
    }


def write_artifact_manifest(report_dir: Path) -> None:
    files: list[dict[str, Any]] = []
    for path in sorted(report_dir.rglob("*")):
        if path.is_file():
            files.append(
                {
                    "path": str(path.relative_to(report_dir)),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    write_json(
        report_dir / "artifact_manifest.json",
        {
            "schema_version": "gemma4_phase11_artifact_manifest_v1",
            "generated_at_utc": utc_now(),
            "file_count": len(files),
            "files": files,
            "forbidden_artifacts_policy": "no raw model weights, raw tensors, SDK binaries, secrets, env files, token files, or build caches",
        },
    )


def main() -> int:
    run_id = utc_now().replace("-", "").replace(":", "").replace("T", "T").replace("Z", "Z") + "_h11g_htp_mutable_adapter"
    report_dir = Path("runtime/reports/gemma4_megakernel/hardware_native_povc") / run_id / "H11-G-htp-mutable-adapter"
    report_dir.mkdir(parents=True, exist_ok=True)

    started_at = utc_now()
    checks: dict[str, Any] = {}
    checks["runpod_qairt_env_probe"] = run_runpod_env_probe()
    write_json(report_dir / "qairt_env_report.json", checks["runpod_qairt_env_probe"])
    checks["runpod_api_compile_probe"] = run_runpod_api_compile_probe()
    write_json(report_dir / "host_api_compile_report.json", checks["runpod_api_compile_probe"])
    checks["phone_tool_surface"] = run_phone_tool_surface()
    write_json(report_dir / "phone_tool_surface_report.json", checks["phone_tool_surface"])
    checks["phone_context_utility"] = run_phone_context_utility(run_id, report_dir)
    write_json(report_dir / "context_utility_report.json", checks["phone_context_utility"])
    checks["phone_htp_inference"] = run_phone_htp_inference(run_id, report_dir)
    write_json(report_dir / "phone_htp_inference_report.json", checks["phone_htp_inference"])

    classification = build_classification(checks)
    write_json(report_dir / "htp_classification.json", classification)

    status = "pass_classified_frozen_forward_only" if classification["classification"] == "frozen_forward_only_mutable_blocked" else "fail"
    if classification["classification"] == "blocked":
        status = "blocked"

    gate = {
        "schema_version": "gemma4_phase11_h11g_htp_mutable_adapter_v1",
        "gate": "H11-G HTP mutable-adapter / zero-order arm",
        "run_id": run_id,
        "started_at_utc": started_at,
        "ended_at_utc": utc_now(),
        "status": status,
        "authority_device": PHONE_SERIAL,
        "phone_context": PHONE_CONTEXT,
        "runpod_qairt_root": RUNPOD_QAIRT_ROOT,
        "phone_qairt_root": PHONE_QAIRT_ROOT,
        "checks": checks,
        "classification": classification,
        "promoted_claims": {
            "htp_frozen_forward_or_teacher": classification["frozen_forward_promoted"],
            "htp_mutable_updateable_section": classification["mutable_section_promoted"],
            "htp_zero_order_forward_only": classification["zero_order_promoted"],
            "normal_htp_backprop": False,
        },
        "non_claims": [
            "No normal HTP backprop, gradient, or optimizer API was executed.",
            "No QnnContext_applyBinarySection update was applied because the current context has zero updateable tensors.",
            "No SPSA/MeZO zero-order step was attempted because there was no valid updateable section to perturb.",
        ],
        "blockers": classification["blockers"],
    }
    write_json(report_dir / "gate_result.json", gate)

    (report_dir / "blockers.md").write_text(
        "\n".join(f"- {item}" for item in classification["blockers"]) + "\n",
        encoding="utf-8",
    )
    (report_dir / "falsifier_report.md").write_text(
        "# H11-G Falsifier Report\n\n"
        "- HTP frozen-forward inference is accepted only if `qnn-net-run` completes on the phone with `qnn_partition_0` and one inference.\n"
        "- Mutable-section promotion is rejected unless the active context reports updateable tensors and an update binary is applied on phone.\n"
        "- Zero-order promotion is rejected unless two or more forward-only perturbation/evaluation/apply steps improve the declared objective without host gradients or optimizer substitution.\n"
        "- Normal HTP backprop remains false: no backward, gradient, or optimizer QNN/HTP API was found or executed.\n",
        encoding="utf-8",
    )
    (report_dir / "commands.log").write_text(
        "Sanitized commands: RunPod QAIRT header/tool/env probe; RunPod QNN apply-binary-section API compile probe; "
        "phone qnn-context-binary-utility --context_binary qwen_block.qnn.bin; "
        "phone qnn-net-run --retrieve_context qwen_block.qnn.bin --backend libQnnHtp.so; "
        "phone qnn-net-run --help binary_updates; phone qairt-lora-adapter-bin-updater --help.\n",
        encoding="utf-8",
    )
    write_artifact_manifest(report_dir)
    print(json.dumps({"host_report_dir": str(report_dir), "status": status}, sort_keys=True))
    return 0 if status.startswith("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
