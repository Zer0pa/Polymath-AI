#!/usr/bin/env python3
"""Run Phase 13 P13-F Gemma-compatible HTP context gate."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
PHASE13_ROOT = REPO_ROOT / "runtime/reports/gemma4_megakernel/phase13_gemma4_only_heterogeneous"
ACTIVE_RUN = PHASE13_ROOT / "active_phase13_run.json"

DEFAULT_SERIAL = "FY25013101C8"
DEFAULT_PHONE_ROOT = "/data/local/tmp/polymath_gemma4_gate"
DEFAULT_RUNPOD_HOST = "38.80.152.147"
DEFAULT_RUNPOD_PORT = "31002"
DEFAULT_RUNPOD_KEY = "~/.ssh/id_ed25519"
DEFAULT_RUNPOD_WORKSPACE = "/workspace/Polymath-AI"
RUNPOD_QAIRT_ROOT = "/workspace/qairt-2.44/qairt/2.44.0.260225"
RUNPOD_NDK_ROOT = "/workspace/android-ndk-r28b"
PHONE_QAIRT_ROOT = "/data/local/tmp/qairt-2.44"

MODEL_ID = "google/gemma-4-E4B"
MODEL_REVISION = "7aa32e6889efd6300124851b164f8b364314c3d8"
HIDDEN = 2560
SEQ = 16
INPUT_BYTES = HIDDEN * SEQ * 4
GEMMA_LAYER0_REFERENCE = "layer_pack/gemma4_e4b_layer0_seq128_v0/reference/layer_output.f32.bin"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def q(value: str) -> str:
    return shlex.quote(value)


def rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def active_run_root() -> Path:
    return REPO_ROOT / load_json(ACTIVE_RUN)["run_root"]


def run_command(
    command: list[str],
    *,
    check: bool = False,
    input_text: str | None = None,
    timeout: int = 600,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        input=input_text,
        capture_output=True,
        timeout=timeout,
    )
    if check and completed.returncode != 0:
        joined = " ".join(q(part) for part in command)
        raise RuntimeError(
            f"command failed ({completed.returncode}): {joined}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def command_log_entry(name: str, result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return {
        "name": name,
        "returncode": result.returncode,
        "stdout_first_4096": result.stdout[:4096],
        "stderr_first_4096": result.stderr[:4096],
    }


def adb(serial: str, args: list[str], *, check: bool = False, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return run_command(["adb", "-s", serial, *args], check=check, timeout=timeout)


def adb_shell(serial: str, command: str, *, check: bool = False, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return adb(serial, ["shell", command], check=check, timeout=timeout)


def adb_push(serial: str, local: Path, remote: str) -> None:
    adb(serial, ["push", str(local), remote], check=True)


def adb_pull(serial: str, remote: str, local: Path, *, check: bool = False) -> bool:
    local.parent.mkdir(parents=True, exist_ok=True)
    completed = adb(serial, ["pull", remote, str(local)], check=False)
    if check and completed.returncode != 0:
        raise RuntimeError(f"adb pull failed: {remote}\n{completed.stderr}")
    return completed.returncode == 0


def ssh_base(args: argparse.Namespace) -> list[str]:
    return [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=30",
        f"root@{args.runpod_host}",
        "-p",
        args.runpod_port,
        "-i",
        os.path.expanduser(args.runpod_key),
    ]


def ssh_script(args: argparse.Namespace, script: str, *, check: bool = False, timeout: int = 900) -> subprocess.CompletedProcess[str]:
    return run_command([*ssh_base(args), "bash", "-s"], input_text=script, check=check, timeout=timeout)


def scp_from_runpod(args: argparse.Namespace, remote: str, local: Path) -> None:
    local.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            "scp",
            "-P",
            args.runpod_port,
            "-i",
            os.path.expanduser(args.runpod_key),
            f"root@{args.runpod_host}:{remote}",
            str(local),
        ],
        check=True,
        timeout=300,
    )


MODEL_CPP_IDENTITY = r'''
#include "QnnModel.hpp"
#include "QnnOpDef.h"

#define DO_GRAPH_NODE_VALIDATIONS 1

using namespace qnn_wrapper_api;

extern "C" {
QNN_API
ModelError_t QnnModel_composeGraphs(Qnn_BackendHandle_t backendHandle,
                                    QNN_INTERFACE_VER_TYPE interface,
                                    Qnn_ContextHandle_t contextHandle,
                                    const GraphConfigInfo_t** graphsConfigInfo,
                                    const uint32_t numGraphsConfigInfo,
                                    GraphInfoPtr_t** graphsInfo,
                                    uint32_t* numGraphsInfo,
                                    bool debug,
                                    QnnLog_Callback_t logCallback,
                                    QnnLog_Level_t maxLogLevel) {
  (void)logCallback;
  (void)maxLogLevel;
  ModelError_t err = MODEL_NO_ERROR;
  QnnModel model;
  const QnnGraph_Config_t** graphConfigs = nullptr;
  VALIDATE(getQnnGraphConfigFromInfo("gemma_hidden2560_identity_add",
                                     graphsConfigInfo,
                                     numGraphsConfigInfo,
                                     graphConfigs),
           err);
  VALIDATE(model.initialize(backendHandle,
                            interface,
                            contextHandle,
                            "gemma_hidden2560_identity_add",
                            debug,
                            DO_GRAPH_NODE_VALIDATIONS,
                            graphConfigs),
           err);

  uint32_t dims_hidden[] = {1, 16, 2560};
  VALIDATE(model.addTensor(
               "gemma_hidden_input",
               (Qnn_Tensor_t){
                   .version = QNN_TENSOR_VERSION_1,
                   .v1      = {.id             = 0,
                          .name           = "gemma_hidden_input",
                          .type           = QNN_TENSOR_TYPE_APP_WRITE,
                          .dataFormat     = QNN_TENSOR_DATA_FORMAT_FLAT_BUFFER,
                          .dataType       = QNN_DATATYPE_FLOAT_32,
                          .quantizeParams = {QNN_DEFINITION_UNDEFINED,
                                             QNN_QUANTIZATION_ENCODING_UNDEFINED,
                                             {.scaleOffsetEncoding = {.scale = 0.0f, .offset = 0}}},
                          .rank           = 3,
                          .dimensions     = dims_hidden,
                          .memType        = QNN_TENSORMEMTYPE_RAW,
                          .clientBuf      = {.data = nullptr, .dataSize = 0}}}),
           err);
  VALIDATE(model.addTensor(
               "gemma_hidden_zero",
               (Qnn_Tensor_t){
                   .version = QNN_TENSOR_VERSION_1,
                   .v1      = {.id             = 0,
                          .name           = "gemma_hidden_zero",
                          .type           = QNN_TENSOR_TYPE_STATIC,
                          .dataFormat     = QNN_TENSOR_DATA_FORMAT_FLAT_BUFFER,
                          .dataType       = QNN_DATATYPE_FLOAT_32,
                          .quantizeParams = {QNN_DEFINITION_UNDEFINED,
                                             QNN_QUANTIZATION_ENCODING_UNDEFINED,
                                             {.scaleOffsetEncoding = {.scale = 0.0f, .offset = 0}}},
                          .rank           = 3,
                          .dimensions     = dims_hidden,
                          .memType        = QNN_TENSORMEMTYPE_RAW,
                          .clientBuf      = {.data = BINVARSTART(gemma_hidden_zero),
                                             .dataSize = BINLEN(gemma_hidden_zero)}}}),
           err);

  const char* inputs[] = {"gemma_hidden_input", "gemma_hidden_zero"};
  Qnn_Tensor_t outputs[] = {(Qnn_Tensor_t){
      .version = QNN_TENSOR_VERSION_1,
      .v1      = {.id             = 0,
             .name           = "gemma_hidden_identity_out",
             .type           = QNN_TENSOR_TYPE_APP_READ,
             .dataFormat     = QNN_TENSOR_DATA_FORMAT_FLAT_BUFFER,
             .dataType       = QNN_DATATYPE_FLOAT_32,
             .quantizeParams = {QNN_DEFINITION_UNDEFINED,
                                QNN_QUANTIZATION_ENCODING_UNDEFINED,
                                {.scaleOffsetEncoding = {.scale = 0.0f, .offset = 0}}},
             .rank           = 3,
             .dimensions     = dims_hidden,
             .memType        = QNN_TENSORMEMTYPE_RAW,
             .clientBuf      = {.data = nullptr, .dataSize = 0}}}};
  VALIDATE(model.addNode(QNN_OPCONFIG_VERSION_1,
                         "gemma_hidden2560_identity_add_node",
                         QNN_OP_PACKAGE_NAME_QTI_AISW,
                         QNN_OP_ELEMENT_WISE_ADD,
                         nullptr,
                         0,
                         inputs,
                         2,
                         outputs,
                         1),
           err);
  QnnModel* models[] = {&model};
  uint32_t numModels = 1;
  VALIDATE(getGraphInfoFromModels(*models, numModels, graphsInfo), err);
  *numGraphsInfo = numModels;
  return err;
}

QNN_API
ModelError_t QnnModel_freeGraphsInfo(GraphInfoPtr_t** graphs, uint32_t numGraphsInfo) {
  return qnn_wrapper_api::freeGraphsInfo(graphs, numGraphsInfo);
}
}
'''


MODEL_CPP_RELU = r'''
#include "QnnModel.hpp"
#include "QnnOpDef.h"

#define DO_GRAPH_NODE_VALIDATIONS 1

using namespace qnn_wrapper_api;

extern "C" {
QNN_API
ModelError_t QnnModel_composeGraphs(Qnn_BackendHandle_t backendHandle,
                                    QNN_INTERFACE_VER_TYPE interface,
                                    Qnn_ContextHandle_t contextHandle,
                                    const GraphConfigInfo_t** graphsConfigInfo,
                                    const uint32_t numGraphsConfigInfo,
                                    GraphInfoPtr_t** graphsInfo,
                                    uint32_t* numGraphsInfo,
                                    bool debug,
                                    QnnLog_Callback_t logCallback,
                                    QnnLog_Level_t maxLogLevel) {
  (void)logCallback;
  (void)maxLogLevel;
  ModelError_t err = MODEL_NO_ERROR;
  QnnModel model;
  const QnnGraph_Config_t** graphConfigs = nullptr;
  VALIDATE(getQnnGraphConfigFromInfo("gemma_hidden2560_relu",
                                     graphsConfigInfo,
                                     numGraphsConfigInfo,
                                     graphConfigs),
           err);
  VALIDATE(model.initialize(backendHandle,
                            interface,
                            contextHandle,
                            "gemma_hidden2560_relu",
                            debug,
                            DO_GRAPH_NODE_VALIDATIONS,
                            graphConfigs),
           err);
  uint32_t dims_hidden[] = {1, 16, 2560};
  VALIDATE(model.addTensor(
               "gemma_hidden_input",
               (Qnn_Tensor_t){
                   .version = QNN_TENSOR_VERSION_1,
                   .v1      = {.id             = 0,
                          .name           = "gemma_hidden_input",
                          .type           = QNN_TENSOR_TYPE_APP_WRITE,
                          .dataFormat     = QNN_TENSOR_DATA_FORMAT_FLAT_BUFFER,
                          .dataType       = QNN_DATATYPE_FLOAT_32,
                          .quantizeParams = {QNN_DEFINITION_UNDEFINED,
                                             QNN_QUANTIZATION_ENCODING_UNDEFINED,
                                             {.scaleOffsetEncoding = {.scale = 0.0f, .offset = 0}}},
                          .rank           = 3,
                          .dimensions     = dims_hidden,
                          .memType        = QNN_TENSORMEMTYPE_RAW,
                          .clientBuf      = {.data = nullptr, .dataSize = 0}}}),
           err);
  const char* inputs[] = {"gemma_hidden_input"};
  Qnn_Tensor_t outputs[] = {(Qnn_Tensor_t){
      .version = QNN_TENSOR_VERSION_1,
      .v1      = {.id             = 0,
             .name           = "gemma_hidden_relu_out",
             .type           = QNN_TENSOR_TYPE_APP_READ,
             .dataFormat     = QNN_TENSOR_DATA_FORMAT_FLAT_BUFFER,
             .dataType       = QNN_DATATYPE_FLOAT_32,
             .quantizeParams = {QNN_DEFINITION_UNDEFINED,
                                QNN_QUANTIZATION_ENCODING_UNDEFINED,
                                {.scaleOffsetEncoding = {.scale = 0.0f, .offset = 0}}},
             .rank           = 3,
             .dimensions     = dims_hidden,
             .memType        = QNN_TENSORMEMTYPE_RAW,
             .clientBuf      = {.data = nullptr, .dataSize = 0}}}};
  VALIDATE(model.addNode(QNN_OPCONFIG_VERSION_1,
                         "gemma_hidden2560_relu_node",
                         QNN_OP_PACKAGE_NAME_QTI_AISW,
                         QNN_OP_RELU,
                         nullptr,
                         0,
                         inputs,
                         1,
                         outputs,
                         1),
           err);
  QnnModel* models[] = {&model};
  uint32_t numModels = 1;
  VALIDATE(getGraphInfoFromModels(*models, numModels, graphsInfo), err);
  *numGraphsInfo = numModels;
  return err;
}

QNN_API
ModelError_t QnnModel_freeGraphsInfo(GraphInfoPtr_t** graphs, uint32_t numGraphsInfo) {
  return qnn_wrapper_api::freeGraphsInfo(graphs, numGraphsInfo);
}
}
'''


def build_remote_models(args: argparse.Namespace, run_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    remote_root = f"/workspace/artifacts/polymath_gemma4/phase13/{run_id}/p13f_gemma_hidden2560_htp"
    script = f"""
set -euo pipefail
Q={q(RUNPOD_QAIRT_ROOT)}
NDK={q(RUNPOD_NDK_ROOT)}
BUILD={q(remote_root)}
rm -rf "$BUILD"
mkdir -p "$BUILD/obj/binary" "$BUILD/out"
python3 - <<'PY'
from pathlib import Path
Path({remote_root!r}, "obj/binary/gemma_hidden_zero.raw").write_bytes(b"\\0" * {INPUT_BYTES})
PY
cat > "$BUILD/gemma_hidden2560_identity.cpp" <<'CPP'
{MODEL_CPP_IDENTITY}
CPP
cat > "$BUILD/gemma_hidden2560_relu.cpp" <<'CPP'
{MODEL_CPP_RELU}
CPP
"$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-objcopy" -I binary -O elf64-littleaarch64 -B aarch64 \
  "$BUILD/obj/binary/gemma_hidden_zero.raw" "$BUILD/obj/gemma_hidden_zero.o"
COMMON=(
  -std=c++20 -O2 -fPIC -fvisibility=hidden -shared
  "-DQNN_API=__attribute__((visibility(\\"default\\")))"
  -I"$Q/include/QNN"
  -I"$Q/share/QNN/converter/jni"
  -I"$Q/share/QNN/converter/jni/linux"
  "$Q/share/QNN/converter/jni/QnnModel.cpp"
  "$Q/share/QNN/converter/jni/QnnWrapperUtils.cpp"
  "$Q/share/QNN/converter/jni/linux/QnnModelPal.cpp"
  -ldl
)
"$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android35-clang++" "${{COMMON[@]}}" \
  "$BUILD/gemma_hidden2560_identity.cpp" "$BUILD/obj/gemma_hidden_zero.o" \
  -o "$BUILD/out/libgemma_hidden2560_identity_add.so"
"$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android35-clang++" "${{COMMON[@]}}" \
  "$BUILD/gemma_hidden2560_relu.cpp" \
  -o "$BUILD/out/libgemma_hidden2560_relu.so"
LIBCPP="$NDK/toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/lib/aarch64-linux-android/libc++_shared.so"
cp "$LIBCPP" "$BUILD/out/libc++_shared.so"
sha256sum "$BUILD/out/"*.so "$BUILD/gemma_hidden2560_identity.cpp" "$BUILD/gemma_hidden2560_relu.cpp" "$BUILD/obj/binary/gemma_hidden_zero.raw" > "$BUILD/out/sha256sums.txt"
wc -c "$BUILD/out/"*.so "$BUILD/obj/binary/gemma_hidden_zero.raw" > "$BUILD/out/sizes.txt"
file "$BUILD/out/"*.so > "$BUILD/out/file.txt"
"$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf" -d "$BUILD/out/libgemma_hidden2560_identity_add.so" "$BUILD/out/libgemma_hidden2560_relu.so" > "$BUILD/out/dynamic.txt"
cat "$BUILD/out/sha256sums.txt"
cat "$BUILD/out/file.txt"
"""
    completed = ssh_script(args, script, check=False, timeout=900)
    record = command_log_entry("runpod_build_android_qnn_gemma_hidden2560_models", completed)
    manifest = {
        "schema_version": "phase13_p13f_remote_model_build_v1",
        "remote_root": remote_root,
        "status": "pass" if completed.returncode == 0 else "fail",
        "qairt_root": RUNPOD_QAIRT_ROOT,
        "ndk_root": RUNPOD_NDK_ROOT,
        "source": "generated QNN Android model libraries for Gemma hidden-size-2560 tensor islands",
        "model_outputs": [
            f"{remote_root}/out/libgemma_hidden2560_identity_add.so",
            f"{remote_root}/out/libgemma_hidden2560_relu.so",
        ],
        "runtime_dependencies": [
            f"{remote_root}/out/libc++_shared.so",
        ],
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    if completed.returncode != 0:
        return manifest, [record]
    return manifest, [record]


def deploy_models_to_phone(
    args: argparse.Namespace,
    serial: str,
    run_id: str,
    phone_gate_root: str,
    report_dir: Path,
    remote_root: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    commands: list[dict[str, Any]] = []
    phone_root = f"{phone_gate_root}/models"
    completed = adb_shell(serial, f"rm -rf {q(phone_root)} && mkdir -p {q(phone_root)}", check=False)
    commands.append(command_log_entry("phone_prepare_p13f_model_dir", completed))
    if completed.returncode != 0:
        return {"status": "fail", "phone_model_root": phone_root}, commands

    deployed: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="p13f_gemma_htp_") as tmp:
        tmp_path = Path(tmp)
        for name in ("libgemma_hidden2560_identity_add.so", "libgemma_hidden2560_relu.so", "libc++_shared.so"):
            local = tmp_path / name
            scp_from_runpod(args, f"{remote_root}/out/{name}", local)
            adb_push(serial, local, f"{phone_root}/{name}")
            deployed.append(
                {
                    "name": name,
                    "phone_path": f"{phone_root}/{name}",
                    "size_bytes": local.stat().st_size,
                    "sha256": sha256_file(local),
                }
            )
    chmod = adb_shell(serial, f"chmod 755 {q(phone_root)}/*.so && sha256sum {q(phone_root)}/*.so", check=False)
    commands.append(command_log_entry("phone_chmod_and_hash_p13f_models", chmod))
    return {
        "schema_version": "phase13_p13f_phone_model_deploy_v1",
        "status": "pass" if chmod.returncode == 0 else "fail",
        "phone_model_root": phone_root,
        "deployed": deployed,
        "phone_sha256_stdout": chmod.stdout,
    }, commands


def run_phone_htp_attempts(serial: str, phone_gate_root: str, report_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    commands: list[dict[str, Any]] = []
    htp_root = f"{phone_gate_root}/htp"
    source_tensor = f"{DEFAULT_PHONE_ROOT}/{GEMMA_LAYER0_REFERENCE}"
    prep_script = f"""
set -e
Q={q(PHONE_QAIRT_ROOT)}
OUT={q(htp_root)}
SRC={q(source_tensor)}
rm -rf "$OUT"
mkdir -p "$OUT"
dd if="$SRC" of="$OUT/gemma_layer0_first16_hidden.f32.bin" bs={INPUT_BYTES} count=1 2>"$OUT/dd.log"
printf 'gemma_layer0_first16_hidden.f32.bin\\n' > "$OUT/input_list.txt"
sha256sum "$SRC" "$OUT/gemma_layer0_first16_hidden.f32.bin" > "$OUT/input_sha256sums.txt"
wc -c "$SRC" "$OUT/gemma_layer0_first16_hidden.f32.bin" > "$OUT/input_sizes.txt"
"""
    prep = adb_shell(serial, prep_script, check=False)
    commands.append(command_log_entry("phone_prepare_gemma_hidden2560_input", prep))
    attempts = []
    if prep.returncode != 0:
        return {
            "schema_version": "phase13_p13f_phone_htp_attempts_v1",
            "status": "fail",
            "phone_htp_root": htp_root,
            "source_tensor": source_tensor,
            "attempts": attempts,
            "blocker": "failed to slice Gemma layer0 reference tensor on phone",
        }, commands

    model_root = f"{phone_gate_root}/models"
    variants = [
        {
            "name": "identity_add",
            "model": f"{model_root}/libgemma_hidden2560_identity_add.so",
            "context_stem": "gemma_hidden2560_identity_add.qnn",
        },
        {
            "name": "relu",
            "model": f"{model_root}/libgemma_hidden2560_relu.so",
            "context_stem": "gemma_hidden2560_relu.qnn",
        },
    ]
    for variant in variants:
        variant_root = f"{htp_root}/{variant['name']}"
        context = f"{variant_root}/context/{variant['context_stem']}.bin"
        script = f"""
set +e
Q={q(PHONE_QAIRT_ROOT)}
ROOT={q(htp_root)}
VARIANT_ROOT={q(variant_root)}
MODEL_ROOT={q(model_root)}
MODEL={q(variant['model'])}
CONTEXT={q(context)}
BINARY_STEM={q(variant['context_stem'])}
rm -rf "$VARIANT_ROOT"
mkdir -p "$VARIANT_ROOT/context" "$VARIANT_ROOT/run"
export LD_LIBRARY_PATH="$MODEL_ROOT:$Q/lib/aarch64-android:/vendor/lib64:$LD_LIBRARY_PATH"
export ADSP_LIBRARY_PATH="$Q/lib/hexagon-v81/unsigned;$Q/lib/hexagon-v79/unsigned;$Q/lib/hexagon-v75/unsigned;/vendor/dsp/cdsp;/vendor/lib/rfsa/adsp;/system/lib/rfsa/adsp;/dsp"
ls -l "$MODEL_ROOT/libc++_shared.so" "$MODEL" > "$VARIANT_ROOT/loader_inputs.log" 2>&1
"$Q/bin/aarch64-android/qnn-context-binary-generator" \
  --model="$MODEL" \
  --backend="$Q/lib/aarch64-android/libQnnHtp.so" \
  --binary_file="$BINARY_STEM" \
  --output_dir="$VARIANT_ROOT/context" \
  --log_level info > "$VARIANT_ROOT/context/stdout.log" 2> "$VARIANT_ROOT/context/stderr.log"
CONTEXT_RC=$?
if [ "$CONTEXT_RC" -eq 0 ]; then
  "$Q/bin/aarch64-android/qnn-context-binary-utility" \
    --context_binary="$CONTEXT" \
    --json_file="$VARIANT_ROOT/context/context_info.json" \
    > "$VARIANT_ROOT/context/utility_stdout.log" 2> "$VARIANT_ROOT/context/utility_stderr.log"
  UTILITY_RC=$?
else
  UTILITY_RC=99
fi
if [ "$CONTEXT_RC" -eq 0 ]; then
  cd "$ROOT"
  "$Q/bin/aarch64-android/qnn-net-run" \
    --retrieve_context="$CONTEXT" \
    --backend "$Q/lib/aarch64-android/libQnnHtp.so" \
    --input_list input_list.txt \
    --output_dir "$VARIANT_ROOT/run" \
    --num_inferences 1 \
    --profiling_level basic \
    --log_level info > "$VARIANT_ROOT/run/stdout.log" 2> "$VARIANT_ROOT/run/stderr.log"
  RUN_RC=$?
else
  RUN_RC=99
fi
OUTPUT_RAW="$(find "$VARIANT_ROOT/run" -type f ! -name 'execution_metadata.yaml' ! -name 'stdout.log' ! -name 'stderr.log' ! -name 'qnn-profiling*' 2>/dev/null | head -n 1)"
if [ -n "$OUTPUT_RAW" ]; then
  sha256sum "$ROOT/gemma_layer0_first16_hidden.f32.bin" "$OUTPUT_RAW" > "$VARIANT_ROOT/output_sha256sums.txt"
  wc -c "$ROOT/gemma_layer0_first16_hidden.f32.bin" "$OUTPUT_RAW" > "$VARIANT_ROOT/output_sizes.txt"
  cmp -s "$ROOT/gemma_layer0_first16_hidden.f32.bin" "$OUTPUT_RAW"
  BYTE_EXACT_RC=$?
else
  BYTE_EXACT_RC=99
fi
cat > "$VARIANT_ROOT/attempt_summary.json" <<EOF
{{"variant":"{variant['name']}","context_rc":$CONTEXT_RC,"utility_rc":$UTILITY_RC,"run_rc":$RUN_RC,"byte_exact_rc":$BYTE_EXACT_RC,"context":"$CONTEXT","output_raw":"$OUTPUT_RAW"}}
EOF
cat "$VARIANT_ROOT/attempt_summary.json"
exit 0
"""
        completed = adb_shell(serial, script, check=False, timeout=900)
        commands.append(command_log_entry(f"phone_p13f_htp_attempt_{variant['name']}", completed))
        local_variant = report_dir / "phone_attempts" / variant["name"]
        pulled = {
            "attempt_summary": adb_pull(serial, f"{variant_root}/attempt_summary.json", local_variant / "attempt_summary.json"),
            "context_info": adb_pull(serial, f"{variant_root}/context/context_info.json", local_variant / "context_info.json"),
            "execution_metadata": adb_pull(serial, f"{variant_root}/run/execution_metadata.yaml", local_variant / "execution_metadata.yaml"),
            "context_stdout": adb_pull(serial, f"{variant_root}/context/stdout.log", local_variant / "context_stdout.log"),
            "context_stderr": adb_pull(serial, f"{variant_root}/context/stderr.log", local_variant / "context_stderr.log"),
            "run_stdout": adb_pull(serial, f"{variant_root}/run/stdout.log", local_variant / "run_stdout.log"),
            "run_stderr": adb_pull(serial, f"{variant_root}/run/stderr.log", local_variant / "run_stderr.log"),
            "loader_inputs": adb_pull(serial, f"{variant_root}/loader_inputs.log", local_variant / "loader_inputs.log"),
            "utility_stdout": adb_pull(serial, f"{variant_root}/context/utility_stdout.log", local_variant / "utility_stdout.log"),
            "utility_stderr": adb_pull(serial, f"{variant_root}/context/utility_stderr.log", local_variant / "utility_stderr.log"),
            "output_sha256sums": adb_pull(serial, f"{variant_root}/output_sha256sums.txt", local_variant / "output_sha256sums.txt"),
            "output_sizes": adb_pull(serial, f"{variant_root}/output_sizes.txt", local_variant / "output_sizes.txt"),
        }
        summary_path = local_variant / "attempt_summary.json"
        summary = load_json(summary_path) if summary_path.exists() else {}
        context_info = load_json(local_variant / "context_info.json") if (local_variant / "context_info.json").exists() else {}
        output_hashes = (local_variant / "output_sha256sums.txt").read_text(encoding="utf-8") if (local_variant / "output_sha256sums.txt").exists() else ""
        output_sizes = (local_variant / "output_sizes.txt").read_text(encoding="utf-8") if (local_variant / "output_sizes.txt").exists() else ""
        attempts.append(
            {
                "variant": variant["name"],
                "phone_variant_root": variant_root,
                "phone_model": variant["model"],
                "phone_context": context,
                "completed": completed.returncode == 0,
                "context_rc": summary.get("context_rc"),
                "utility_rc": summary.get("utility_rc"),
                "run_rc": summary.get("run_rc"),
                "byte_exact_rc": summary.get("byte_exact_rc"),
                "context_generated": summary.get("context_rc") == 0,
                "phone_htp_run_completed": summary.get("run_rc") == 0,
                "byte_exact_identity": summary.get("byte_exact_rc") == 0,
                "output_raw_phone_path": summary.get("output_raw"),
                "pulled": pulled,
                "context_graphs": context_info.get("info", {}).get("graphs", []),
                "output_sha256sums": output_hashes,
                "output_sizes": output_sizes,
            }
        )

    input_manifest_local = report_dir / "phone_attempts" / "input_manifest"
    input_manifest_pulled = {
        "input_sha256sums": adb_pull(serial, f"{htp_root}/input_sha256sums.txt", input_manifest_local / "input_sha256sums.txt"),
        "input_sizes": adb_pull(serial, f"{htp_root}/input_sizes.txt", input_manifest_local / "input_sizes.txt"),
        "dd_log": adb_pull(serial, f"{htp_root}/dd.log", input_manifest_local / "dd.log"),
    }
    passed = [item for item in attempts if item.get("context_generated") and item.get("phone_htp_run_completed")]
    return {
        "schema_version": "phase13_p13f_phone_htp_attempts_v1",
        "status": "pass" if passed else "fail",
        "phone_htp_root": htp_root,
        "source_tensor": source_tensor,
        "input_shape": [1, SEQ, HIDDEN],
        "input_bytes": INPUT_BYTES,
        "input_manifest_pulled": input_manifest_pulled,
        "attempts": attempts,
        "selected_valid_attempt": passed[0]["variant"] if passed else None,
    }, commands


def write_artifact_manifest(report_dir: Path) -> None:
    entries: list[dict[str, Any]] = []
    for path in sorted(report_dir.rglob("*")):
        if path.is_file() and path.name != "artifact_manifest.json":
            entries.append({"path": rel(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    write_json(
        report_dir / "artifact_manifest.json",
        {
            "schema_version": "phase13_p13f_artifact_manifest_v1",
            "created_at_utc": utc_now(),
            "artifacts": entries,
        },
    )


def update_phase13_status(run_root: Path, status: str, gate_result_path: Path) -> None:
    status_path = run_root / "phase13_gate_status.json"
    phase_status = load_json(status_path)
    phase_status["gate_status"]["P13-F"] = status
    phase_status["current_gate"] = "P13-G"
    phase_status["latest_gate_result"] = rel(gate_result_path)
    phase_status["updated_at_utc"] = utc_now()
    write_json(status_path, phase_status)
    active = load_json(ACTIVE_RUN)
    active["current_gate"] = "P13-G"
    active["updated_at_utc"] = utc_now()
    write_json(ACTIVE_RUN, active)


def update_gpd_state(status: str, gate_result_path: Path, selected: str | None) -> None:
    gate_rel = rel(gate_result_path)
    state_path = REPO_ROOT / ".gpd/state.json"
    state = load_json(state_path)
    if status == "pass":
        desc = (
            f"P13-F passed at {gate_rel}: phone QAIRT generated and executed a Gemma hidden-size-2560 "
            f"HTP context from a megakernel layer0 hidden tensor; selected HTP island={selected}. "
            "This proves only Gemma-compatible HTP execution, not HTP backprop or heterogeneous learning."
        )
        next_status = "Phase 13 execution in progress; P13-A through P13-F passed; next gate is P13-G heterogeneous comparison"
    else:
        desc = (
            f"P13-F falsified at {gate_rel}: no Gemma hidden-size-2560 HTP context executed on phone; "
            "continue to P13-G with Adreno/OpenCL fallback and exact HTP blocker."
        )
        next_status = "Phase 13 execution in progress; P13-A through P13-E passed; P13-F falsified; next gate is P13-G heterogeneous comparison"
    state["position"]["last_activity"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    state["position"]["last_activity_desc"] = desc
    state["position"]["last_activity_description"] = desc
    state["position"]["status"] = next_status
    state["session"]["stopped_at"] = (
        "P13-F artifact written; continue with P13-G heterogeneous candidate versus Adreno baseline. "
        "Do not run P13-H until P13-G has an exact pass/fail/fallback artifact."
    )
    todos = [
        item for item in state.get("pending_todos", [])
        if "P13-F" not in item and "Gemma-compatible HTP" not in item
    ]
    next_todo = "Execute P13-G next: compare any valid Gemma-compatible HTP/CPU/Adreno candidate against the Adreno-only baseline."
    if next_todo not in todos:
        todos.insert(0, next_todo)
    state["pending_todos"] = todos
    result = desc.replace(" at ", ": ", 1)
    if result not in state.setdefault("intermediate_results", []):
        state["intermediate_results"].append(result)
    state["_synced_at"] = utc_now()
    write_json(state_path, state)

    state_md = REPO_ROOT / ".gpd/STATE.md"
    if state_md.exists():
        text = state_md.read_text(encoding="utf-8")
        text = text.replace(
            "**Status:** Phase 13 execution in progress; P13-A through P13-E passed; next gate is P13-F Gemma-compatible HTP or hard falsification",
            f"**Status:** {next_status}",
        )
        marker = "\n## Session Continuity\n"
        entry = f"- {desc}\n"
        if entry not in text:
            if marker in text:
                text = text.replace(marker, entry + marker)
            else:
                text += "\n" + entry
        state_md.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serial", default=DEFAULT_SERIAL)
    parser.add_argument("--phone-root", default=DEFAULT_PHONE_ROOT)
    parser.add_argument("--runpod-host", default=DEFAULT_RUNPOD_HOST)
    parser.add_argument("--runpod-port", default=DEFAULT_RUNPOD_PORT)
    parser.add_argument("--runpod-key", default=DEFAULT_RUNPOD_KEY)
    parser.add_argument("--runpod-workspace", default=DEFAULT_RUNPOD_WORKSPACE)
    args = parser.parse_args()

    run_root = active_run_root()
    run_id = run_root.name
    report_dir = run_root / "P13-F-gemma-compatible-htp-context"
    report_dir.mkdir(parents=True, exist_ok=True)
    phone_gate_root = f"{args.phone_root.rstrip('/')}/phase13/{run_id}/p13f"
    started_at = utc_now()

    commands: list[dict[str, Any]] = []
    qairt_help = adb_shell(
        args.serial,
        f"Q={q(PHONE_QAIRT_ROOT)}; export LD_LIBRARY_PATH=$Q/lib/aarch64-android:$LD_LIBRARY_PATH; "
        f"$Q/bin/aarch64-android/qnn-context-binary-generator --help | head -n 40",
        check=False,
    )
    commands.append(command_log_entry("phone_qnn_context_binary_generator_help", qairt_help))

    build_manifest, build_commands = build_remote_models(args, run_id)
    commands.extend(build_commands)
    write_json(report_dir / "remote_model_build_manifest.json", build_manifest)

    deploy_manifest: dict[str, Any] = {"status": "skipped"}
    attempts_summary: dict[str, Any] = {"status": "skipped", "attempts": []}
    if build_manifest["status"] == "pass":
        deploy_manifest, deploy_commands = deploy_models_to_phone(
            args,
            args.serial,
            run_id,
            phone_gate_root,
            report_dir,
            build_manifest["remote_root"],
        )
        commands.extend(deploy_commands)
        write_json(report_dir / "phone_model_deploy_manifest.json", deploy_manifest)
    else:
        write_json(report_dir / "phone_model_deploy_manifest.json", deploy_manifest)

    if deploy_manifest.get("status") == "pass":
        attempts_summary, attempt_commands = run_phone_htp_attempts(args.serial, phone_gate_root, report_dir)
        commands.extend(attempt_commands)
    write_json(report_dir / "phone_htp_attempts_summary.json", attempts_summary)

    valid_attempt = attempts_summary.get("selected_valid_attempt")
    status = "pass" if attempts_summary.get("status") == "pass" and valid_attempt else "falsified"
    blockers: list[str] = []
    if qairt_help.returncode != 0:
        blockers.append("phone qnn-context-binary-generator help failed")
    if build_manifest.get("status") != "pass":
        blockers.append("RunPod Android QNN model-library build failed")
    if deploy_manifest.get("status") != "pass":
        blockers.append("phone QNN model-library deployment failed")
    if attempts_summary.get("status") != "pass":
        blockers.append("no Gemma hidden-size-2560 phone HTP context both generated and executed")

    gate_result_path = report_dir / "gate_result.json"
    gate = {
        "schema_version": "phase13_p13f_gemma_compatible_htp_context_v1",
        "gate": "P13-F Gemma-compatible HTP artifact or hard falsification",
        "status": status,
        "started_at_utc": started_at,
        "ended_at_utc": utc_now(),
        "model_id": MODEL_ID,
        "revision": MODEL_REVISION,
        "hidden_size": HIDDEN,
        "sequence_length": SEQ,
        "authority_device": args.serial,
        "phone_qairt_root": PHONE_QAIRT_ROOT,
        "runpod_qairt_root": RUNPOD_QAIRT_ROOT,
        "runpod_ndk_root": RUNPOD_NDK_ROOT,
        "gemma_source_tensor": f"{args.phone_root.rstrip('/')}/{GEMMA_LAYER0_REFERENCE}",
        "context_role": "gemma_hidden2560_htp_tensor_island",
        "selected_valid_attempt": valid_attempt,
        "promoted_claims": {
            "gemma_hidden2560_htp_context_executed_on_phone": status == "pass",
            "htp_output_consumed_by_training_loop": False,
            "htp_backprop": False,
            "qnn_context_apply_binary_section_executed": False,
            "heterogeneous_learning": False,
        },
        "nonclaims": [
            "The HTP context is a Gemma-compatible hidden tensor island only; it is not full Gemma4 training.",
            "No HTP backward, optimizer, updateable section, or QnnContext_applyBinarySection path is promoted.",
            "No Qwen, random-init, or hidden-size-1536 artifact is used in this promoted P13-F gate.",
            "P13-G must still decide whether any heterogeneous path beats the Adreno/OpenCL training baseline.",
        ],
        "remote_model_build_manifest": rel(report_dir / "remote_model_build_manifest.json"),
        "phone_model_deploy_manifest": rel(report_dir / "phone_model_deploy_manifest.json"),
        "phone_htp_attempts_summary": rel(report_dir / "phone_htp_attempts_summary.json"),
        "blockers": blockers,
    }
    write_json(gate_result_path, gate)
    write_text(report_dir / "blockers.md", "\n".join(f"- {item}" for item in blockers) + ("\n" if blockers else "- none\n"))
    write_text(
        report_dir / "falsifier_report.md",
        "# P13-F Falsifier Report\n\n"
        "- Gemma compatibility requires `google/gemma-4-E4B`, hidden size `2560`, and an input tensor sliced from the Gemma4 megakernel layer0 reference output.\n"
        "- Qwen/random-init hidden-size-1536 artifacts are not used for context generation, input, execution, or promotion.\n"
        "- HTP promotion requires phone `qnn-context-binary-generator` plus phone `qnn-net-run` success. Tool help alone is not accepted.\n"
        "- The selected HTP island is not treated as HTP backprop, updateable QNN training, or integrated heterogeneous learning.\n",
    )
    write_text(
        report_dir / "commands.log",
        json.dumps({"commands": commands}, indent=2, sort_keys=True) + "\n",
    )
    write_artifact_manifest(report_dir)
    update_phase13_status(run_root, status, gate_result_path)
    update_gpd_state(status, gate_result_path, valid_attempt)
    print(json.dumps({"status": status, "gate_result": rel(gate_result_path)}, sort_keys=True))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
