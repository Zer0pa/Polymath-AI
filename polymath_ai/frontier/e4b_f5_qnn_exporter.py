"""Executable direct-QNN probe package generator for Gemma 4 E4B F5.

The generated package embeds the exact packed W4 q-projection and W2 untied
LM-head bytes.  At graph composition time it deterministically unpacks those
bytes into the SFixedPoint8 + BW_AXIS_SCALE_OFFSET ABI documented for HTP
MatMul in QAIRT 2.44.  Backend acceptance remains a measured result: the
package never turns source generation into a context or phone-execution pass.
"""

from __future__ import annotations

import ctypes
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import sys
from typing import Any, BinaryIO

from .e4b_f5_probe import (
    LM_HEAD,
    PROJECTIONS,
    QAT_MODEL_BYTES,
    QAT_MODEL_SHA256,
    QAT_REPOSITORY,
    QAT_REVISION,
    Q_PROJ,
    QAIRT_HTP_OPDEF_SUPPLEMENT_SHA256,
    QAIRT_QNN_TYPES_SHA256,
    QAIRT_VERSION,
    TRANSFORMERS_COMMIT,
    TRANSFORMERS_SOURCE_SHA256,
    ProbeContractError,
    ProjectionContract,
    TensorContract,
    read_safetensors_header,
    validate_pinned_header,
    verify_probe_payloads,
)


QAIRT_BUILD_SOURCE_SHA256 = {
    "share/QNN/converter/jni/QnnModel.cpp": (
        "9b61ae746cf38769ba3929976c1ce6bf5b9d55a07b1620bb710ffb5f3496ff0b"
    ),
    "share/QNN/converter/jni/QnnWrapperUtils.cpp": (
        "ba4e6ef9faedcd538f3c7ead91495744a7976d4f71504e8a984a772eebf2bdb8"
    ),
    "share/QNN/converter/jni/linux/QnnModelPal.cpp": (
        "cd175508b73513119462bf9a6f2c326e28175923b03e25044f931e6242c556e9"
    ),
    "share/QNN/converter/jni/QnnModel.hpp": (
        "26736ad0740558c59bdc8a99311c0c798639b7d296e19b4ab2edd0130bd76c93"
    ),
    "share/QNN/converter/jni/QnnWrapperUtils.hpp": (
        "aa910fb8f631f7d8794610028328a15deb8e936cda16f15f6ad0f0b311504173"
    ),
    "include/QNN/QnnTypes.h": QAIRT_QNN_TYPES_SHA256,
    "include/QNN/QnnOpDef.h": (
        "272baf1a8dd32be2771e552303e820e76201affa8106792b96c2e289cf7a79e9"
    ),
    "docs/QAIRT-Docs/QNN/general/htp/htp_backend.html": (
        "391b905c4f92d2309e5dc91e00e7497f06ff55a54b134b8f4afa9a8466362dff"
    ),
    "lib/python/qti/aisw/core/model_level_api/utils/subprocess_executor.py": (
        "32f0be62acd57b8f0f4d6ce6ecc52da7cef3671dd076ef5aa94e754e1f7b6031"
    ),
}

TENSOR_FILENAMES = {
    Q_PROJ.weight.name: "w4_q_proj_weight.u4.packed.bin",
    Q_PROJ.weight_scale.name: "w4_q_proj_weight_scale.f32.bin",
    Q_PROJ.input_activation_scale.name: "w4_q_proj_input_scale.f32.bin",
    Q_PROJ.output_activation_scale.name: "w4_q_proj_output_scale.f32.bin",
    LM_HEAD.weight.name: "w2_lm_head_weight.u2.packed.bin",
    LM_HEAD.weight_scale.name: "w2_lm_head_weight_scale.f32.bin",
    LM_HEAD.input_activation_scale.name: "w2_lm_head_input_scale.f32.bin",
    LM_HEAD.output_activation_scale.name: "w2_lm_head_output_scale.f32.bin",
}

TENSOR_SYMBOLS = {
    Q_PROJ.weight.name: "f5_w4_weight",
    Q_PROJ.weight_scale.name: "f5_w4_weight_scale",
    Q_PROJ.input_activation_scale.name: "f5_w4_input_scale",
    Q_PROJ.output_activation_scale.name: "f5_w4_output_scale",
    LM_HEAD.weight.name: "f5_w2_weight",
    LM_HEAD.weight_scale.name: "f5_w2_weight_scale",
    LM_HEAD.input_activation_scale.name: "f5_w2_input_scale",
    LM_HEAD.output_activation_scale.name: "f5_w2_output_scale",
}

Q_PROJ_GRAPH = "gemma4_e4b_f5_w4_q_proj"
LM_HEAD_GRAPH = "gemma4_e4b_f5_w2_lm_head"

BACKEND_CONFIG = {
    "graphs": [
        {"graph_names": [Q_PROJ_GRAPH], "vtcm_mb": 2},
        {"graph_names": [LM_HEAD_GRAPH], "vtcm_mb": 2},
    ],
    "devices": [{"soc_model": 69, "dsp_arch": "v79"}],
}

EXTENSIONS_CONFIG = {
    "backend_extensions": {
        "shared_library_path": "/opt/qairt/lib/libQnnHtpNetRunExtensions.so",
        "config_file_path": "config/backend.json",
    }
}


def validate_qairt_configs(backend: Any, extensions: Any) -> None:
    """Apply a narrow schema for the exact QAIRT 2.44 provider configuration."""

    if backend != BACKEND_CONFIG:
        raise ProbeContractError("backend config does not match the exact soc69/v79 two-graph schema")
    if extensions != EXTENSIONS_CONFIG:
        raise ProbeContractError("extensions config does not match the exact QAIRT 2.44 outer schema")


def _open_regular_nofollow(path: Path) -> BinaryIO:
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ProbeContractError(f"cannot open carrier without following links: {path}: {exc}") from exc
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode):
        os.close(descriptor)
        raise ProbeContractError("carrier must be a regular file")
    try:
        fcntl.flock(descriptor, fcntl.LOCK_SH)
    except OSError:
        os.close(descriptor)
        raise
    return os.fdopen(descriptor, "rb", closefd=True)


def _sha256_handle(handle: BinaryIO) -> str:
    handle.seek(0)
    digest = hashlib.sha256()
    while chunk := handle.read(8 * 1024 * 1024):
        digest.update(chunk)
    return digest.hexdigest()


def publish_directory_noreplace(source: Path, destination: Path) -> None:
    """Atomically publish a directory without replacing any destination."""

    libc = ctypes.CDLL(None, use_errno=True)
    source_bytes = os.fsencode(source)
    destination_bytes = os.fsencode(destination)
    if sys.platform.startswith("linux") or sys.platform == "android":
        renameat2 = getattr(libc, "renameat2", None)
        if renameat2 is None:
            raise ProbeContractError("renameat2 is unavailable; refusing non-atomic publication")
        renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        renameat2.restype = ctypes.c_int
        result = renameat2(-100, source_bytes, -100, destination_bytes, 1)
    elif sys.platform == "darwin":
        renamex_np = getattr(libc, "renamex_np", None)
        if renamex_np is None:
            raise ProbeContractError("renamex_np is unavailable; refusing non-atomic publication")
        renamex_np.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        renamex_np.restype = ctypes.c_int
        result = renamex_np(source_bytes, destination_bytes, 0x00000004)
    else:
        raise ProbeContractError(f"no proven no-replace directory publication primitive on {sys.platform}")
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number in (errno.EEXIST, errno.ENOTEMPTY):
        raise ProbeContractError(f"publication destination already exists: {destination}")
    raise OSError(error_number, os.strerror(error_number), str(destination))


def unpack_low_bits(packed: bytes, *, num_bits: int, signed_shift: int, logical_values: int) -> bytes:
    """Unpack the exact Transformers lane order into signed int8 values."""

    if num_bits not in (2, 4):
        raise ProbeContractError(f"unsupported packed bit width: {num_bits}")
    lanes_per_byte = 8 // num_bits
    expected_bytes = (logical_values + lanes_per_byte - 1) // lanes_per_byte
    if len(packed) != expected_bytes:
        raise ProbeContractError(
            f"packed byte count mismatch: expected {expected_bytes}, got {len(packed)}"
        )
    mask = (1 << num_bits) - 1
    result = bytearray(logical_values)
    for index in range(logical_values):
        packed_byte = packed[index // lanes_per_byte]
        lane = index % lanes_per_byte
        unsigned_value = (packed_byte >> (lane * num_bits)) & mask
        signed_value = unsigned_value + signed_shift
        result[index] = signed_value & 0xFF
    return bytes(result)


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _write_exclusive(path: Path, payload: bytes, *, executable: bool = False) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    mode = 0o750 if executable else 0o640
    descriptor = os.open(path, flags, mode)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError(f"short write to {path}")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _copy_tensor(
    source: BinaryIO,
    *,
    data_start: int,
    contract: TensorContract,
    destination: Path,
) -> dict[str, Any]:
    source.seek(data_start + contract.offsets[0])
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(destination, flags, 0o640)
    remaining = contract.nbytes
    digest = hashlib.sha256()
    try:
        while remaining:
            chunk = source.read(min(remaining, 8 * 1024 * 1024))
            if not chunk:
                raise ProbeContractError(f"truncated tensor payload: {contract.name}")
            digest.update(chunk)
            view = memoryview(chunk)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise OSError(f"short write to {destination}")
                view = view[written:]
            remaining -= len(chunk)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    observed = digest.hexdigest()
    if observed != contract.data_sha256:
        raise ProbeContractError(f"copied tensor digest mismatch: {contract.name}")
    return {
        "source_tensor": contract.name,
        "relative_path": f"tensors/{destination.name}",
        "bytes": contract.nbytes,
        "sha256": observed,
        "dtype": contract.dtype,
        "shape": list(contract.shape),
    }


def _projection_tensors(projection: ProjectionContract) -> tuple[TensorContract, ...]:
    return (
        projection.weight,
        projection.weight_scale,
        projection.input_activation_scale,
        projection.output_activation_scale,
    )


def render_packed_tensor_assembly() -> str:
    sections = [
        '.section .rodata.f5_packed_tensors,"a",@progbits',
    ]
    for projection in PROJECTIONS:
        for tensor in _projection_tensors(projection):
            symbol = TENSOR_SYMBOLS[tensor.name]
            filename = TENSOR_FILENAMES[tensor.name]
            sections.extend(
                [
                    ".balign 64",
                    f".global {symbol}_start",
                    f".hidden {symbol}_start",
                    f"{symbol}_start:",
                    f'.incbin "tensors/{filename}"',
                    f".global {symbol}_end",
                    f".hidden {symbol}_end",
                    f"{symbol}_end:",
                ]
            )
    sections.append('.section .note.GNU-stack,"",@progbits')
    return "\n".join(sections) + "\n"


def render_direct_qnn_cpp() -> str:
    """Render the complete two-graph QNN model-library source."""

    return r'''#include "QnnModel.hpp"
#include "QnnOpDef.h"

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <vector>

#define DO_GRAPH_NODE_VALIDATIONS 1

using namespace qnn_wrapper_api;

extern "C" {
extern const uint8_t f5_w4_weight_start[];
extern const uint8_t f5_w4_weight_end[];
extern const uint8_t f5_w4_weight_scale_start[];
extern const uint8_t f5_w4_weight_scale_end[];
extern const uint8_t f5_w4_input_scale_start[];
extern const uint8_t f5_w4_input_scale_end[];
extern const uint8_t f5_w4_output_scale_start[];
extern const uint8_t f5_w4_output_scale_end[];
extern const uint8_t f5_w2_weight_start[];
extern const uint8_t f5_w2_weight_end[];
extern const uint8_t f5_w2_weight_scale_start[];
extern const uint8_t f5_w2_weight_scale_end[];
extern const uint8_t f5_w2_input_scale_start[];
extern const uint8_t f5_w2_input_scale_end[];
extern const uint8_t f5_w2_output_scale_start[];
extern const uint8_t f5_w2_output_scale_end[];
}

namespace {

struct Blob {
  const uint8_t* begin;
  const uint8_t* end;

  size_t size() const {
    return static_cast<size_t>(reinterpret_cast<uintptr_t>(end) -
                               reinterpret_cast<uintptr_t>(begin));
  }
};

bool unpackLowBits(const Blob packed,
                   const uint32_t numBits,
                   const int32_t signedShift,
                   const size_t logicalValues,
                   std::vector<int8_t>& output) {
  if (numBits != 2 && numBits != 4) {
    return false;
  }
  const size_t lanesPerByte = 8u / numBits;
  const size_t expectedBytes = (logicalValues + lanesPerByte - 1u) / lanesPerByte;
  if (packed.size() != expectedBytes) {
    return false;
  }
  const uint8_t mask = static_cast<uint8_t>((1u << numBits) - 1u);
  output.resize(logicalValues);
  for (size_t index = 0; index < logicalValues; ++index) {
    const uint8_t byte = packed.begin[index / lanesPerByte];
    const uint32_t lane = static_cast<uint32_t>(index % lanesPerByte);
    const uint8_t value = static_cast<uint8_t>((byte >> (lane * numBits)) & mask);
    output[index] = static_cast<int8_t>(static_cast<int32_t>(value) + signedShift);
  }
  return true;
}

bool loadScales(const Blob source, const size_t count, std::vector<float>& output) {
  if (source.size() != count * sizeof(float)) {
    return false;
  }
  output.resize(count);
  std::memcpy(output.data(), source.begin, source.size());
  for (const float scale : output) {
    if (!std::isfinite(scale) || scale <= 0.0f) {
      return false;
    }
  }
  return true;
}

bool loadScalar(const Blob source, float& output) {
  if (source.size() != sizeof(float)) {
    return false;
  }
  std::memcpy(&output, source.begin, sizeof(float));
  return std::isfinite(output);
}

Qnn_QuantizeParams_t undefinedQuantization() {
  Qnn_QuantizeParams_t result = QNN_QUANTIZE_PARAMS_INIT;
  return result;
}

Qnn_QuantizeParams_t scaleOffsetQuantization(const float scale) {
  Qnn_QuantizeParams_t result = QNN_QUANTIZE_PARAMS_INIT;
  result.encodingDefinition = QNN_DEFINITION_DEFINED;
  result.quantizationEncoding = QNN_QUANTIZATION_ENCODING_SCALE_OFFSET;
  result.scaleOffsetEncoding.scale = scale;
  result.scaleOffsetEncoding.offset = 0;
  return result;
}

Qnn_QuantizeParams_t weightQuantization(const uint32_t bits,
                                        const uint32_t outputChannels,
                                        float* scales) {
  Qnn_QuantizeParams_t result = QNN_QUANTIZE_PARAMS_INIT;
  result.encodingDefinition = QNN_DEFINITION_DEFINED;
  result.quantizationEncoding = QNN_QUANTIZATION_ENCODING_BW_AXIS_SCALE_OFFSET;
  result.bwAxisScaleOffsetEncoding.bitwidth = bits;
  result.bwAxisScaleOffsetEncoding.axis = 0;
  result.bwAxisScaleOffsetEncoding.numElements = outputChannels;
  result.bwAxisScaleOffsetEncoding.scales = scales;
  result.bwAxisScaleOffsetEncoding.offsets = nullptr;
  return result;
}

Qnn_Tensor_t tensor(const char* name,
                    uint32_t* dimensions,
                    const uint32_t rank,
                    const Qnn_TensorType_t type,
                    const Qnn_DataType_t dataType,
                    const Qnn_QuantizeParams_t quantization,
                    void* data,
                    const uint32_t dataSize) {
  Qnn_Tensor_t result = QNN_TENSOR_INIT;
  result.version = QNN_TENSOR_VERSION_1;
  result.v1.id = 0;
  result.v1.name = name;
  result.v1.type = type;
  result.v1.dataFormat = QNN_TENSOR_DATA_FORMAT_FLAT_BUFFER;
  result.v1.dataType = dataType;
  result.v1.quantizeParams = quantization;
  result.v1.rank = rank;
  result.v1.dimensions = dimensions;
  result.v1.memType = QNN_TENSORMEMTYPE_RAW;
  result.v1.clientBuf.data = data;
  result.v1.clientBuf.dataSize = dataSize;
  return result;
}

struct GraphSpec {
  const char* graphName;
  const char* inputName;
  const char* weightName;
  const char* outputName;
  const char* nodeName;
  uint32_t inputFeatures;
  uint32_t outputFeatures;
  uint32_t weightBits;
  Qnn_DataType_t ioDataType;
  Qnn_QuantizeParams_t inputQuantization;
  Qnn_QuantizeParams_t outputQuantization;
};

ModelError_t addProjectionGraph(QnnModel& model,
                                const Qnn_BackendHandle_t backendHandle,
                                const QNN_INTERFACE_VER_TYPE interface,
                                const Qnn_ContextHandle_t contextHandle,
                                const GraphConfigInfo_t** graphsConfigInfo,
                                const uint32_t numGraphsConfigInfo,
                                const bool debug,
                                const GraphSpec& spec,
                                std::vector<int8_t>& weights,
                                std::vector<float>& scales) {
  ModelError_t error = MODEL_NO_ERROR;
  const QnnGraph_Config_t** graphConfigs = nullptr;
  VALIDATE(getQnnGraphConfigFromInfo(spec.graphName,
                                     graphsConfigInfo,
                                     numGraphsConfigInfo,
                                     graphConfigs),
           error);
  VALIDATE(model.initialize(backendHandle,
                            interface,
                            contextHandle,
                            spec.graphName,
                            debug,
                            DO_GRAPH_NODE_VALIDATIONS,
                            graphConfigs),
           error);

  uint32_t inputDimensions[] = {1, 1, spec.inputFeatures};
  uint32_t weightDimensions[] = {spec.outputFeatures, spec.inputFeatures};
  uint32_t outputDimensions[] = {1, 1, spec.outputFeatures};

  Qnn_Tensor_t input = tensor(spec.inputName,
                              inputDimensions,
                              3,
                              QNN_TENSOR_TYPE_APP_WRITE,
                              spec.ioDataType,
                              spec.inputQuantization,
                              nullptr,
                              0);
  VALIDATE(model.addTensor(spec.nodeName, input), error);

  if (weights.size() > std::numeric_limits<uint32_t>::max()) {
    return MODEL_INVALID_ARGUMENT_ERROR;
  }
  Qnn_Tensor_t weight = tensor(spec.weightName,
                               weightDimensions,
                               2,
                               QNN_TENSOR_TYPE_STATIC,
                               QNN_DATATYPE_SFIXED_POINT_8,
                               weightQuantization(spec.weightBits,
                                                  spec.outputFeatures,
                                                  scales.data()),
                               weights.data(),
                               static_cast<uint32_t>(weights.size()));
  VALIDATE(model.addTensor(spec.nodeName, weight), error);

  Qnn_Param_t parameters[2] = {QNN_PARAM_INIT, QNN_PARAM_INIT};
  parameters[0].paramType = QNN_PARAMTYPE_SCALAR;
  parameters[0].name = QNN_OP_MAT_MUL_PARAM_TRANSPOSE_IN0;
  parameters[0].scalarParam.dataType = QNN_DATATYPE_BOOL_8;
  parameters[0].scalarParam.bool8Value = 0;
  parameters[1].paramType = QNN_PARAMTYPE_SCALAR;
  parameters[1].name = QNN_OP_MAT_MUL_PARAM_TRANSPOSE_IN1;
  parameters[1].scalarParam.dataType = QNN_DATATYPE_BOOL_8;
  parameters[1].scalarParam.bool8Value = 1;

  const char* inputs[] = {spec.inputName, spec.weightName};
  Qnn_Tensor_t outputs[] = {tensor(spec.outputName,
                                   outputDimensions,
                                   3,
                                   QNN_TENSOR_TYPE_APP_READ,
                                   spec.ioDataType,
                                   spec.outputQuantization,
                                   nullptr,
                                   0)};
  VALIDATE(model.addNode(QNN_OPCONFIG_VERSION_1,
                         spec.nodeName,
                         QNN_OP_PACKAGE_NAME_QTI_AISW,
                         QNN_OP_MAT_MUL,
                         parameters,
                         2,
                         inputs,
                         2,
                         outputs,
                         1),
           error);
  return MODEL_NO_ERROR;
}

}  // namespace

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
  if (graphsInfo == nullptr || numGraphsInfo == nullptr) {
    return MODEL_INVALID_ARGUMENT_ERROR;
  }

  try {
    const Blob qWeight{f5_w4_weight_start, f5_w4_weight_end};
    const Blob qWeightScale{f5_w4_weight_scale_start, f5_w4_weight_scale_end};
    const Blob qInputScale{f5_w4_input_scale_start, f5_w4_input_scale_end};
    const Blob qOutputScale{f5_w4_output_scale_start, f5_w4_output_scale_end};
    const Blob headWeight{f5_w2_weight_start, f5_w2_weight_end};
    const Blob headWeightScale{f5_w2_weight_scale_start, f5_w2_weight_scale_end};
    const Blob headInputScale{f5_w2_input_scale_start, f5_w2_input_scale_end};
    const Blob headOutputScale{f5_w2_output_scale_start, f5_w2_output_scale_end};

    std::vector<int8_t> qWeights;
    std::vector<int8_t> headWeights;
    std::vector<float> qScales;
    std::vector<float> headScales;
    float qInputScaleValue = 0.0f;
    float qOutputScaleValue = 0.0f;
    float headInputScaleValue = 1.0f;
    float headOutputScaleValue = 1.0f;

    if (!unpackLowBits(qWeight, 4, -8, 2048ull * 2560ull, qWeights) ||
        !unpackLowBits(headWeight, 2, -2, 262144ull * 2560ull, headWeights) ||
        !loadScales(qWeightScale, 2048, qScales) ||
        !loadScales(headWeightScale, 262144, headScales) ||
        !loadScalar(qInputScale, qInputScaleValue) ||
        !loadScalar(qOutputScale, qOutputScaleValue) ||
        !loadScalar(headInputScale, headInputScaleValue) ||
        !loadScalar(headOutputScale, headOutputScaleValue) ||
        qInputScaleValue <= 0.0f || qOutputScaleValue <= 0.0f ||
        headInputScaleValue != 0.0f || headOutputScaleValue != 0.0f) {
      return MODEL_INVALID_ARGUMENT_ERROR;
    }

    GraphSpec qSpec{
        "gemma4_e4b_f5_w4_q_proj",
        "q_proj_input_s8",
        "q_proj_weight_s8_bw4",
        "q_proj_output_s8",
        "q_proj_matmul",
        2560,
        2048,
        4,
        QNN_DATATYPE_SFIXED_POINT_8,
        scaleOffsetQuantization(qInputScaleValue),
        scaleOffsetQuantization(qOutputScaleValue),
    };
    GraphSpec headSpec{
        "gemma4_e4b_f5_w2_lm_head",
        "lm_head_input_f16",
        "lm_head_weight_s8_bw2",
        "lm_head_output_f16_pre_softcap",
        "lm_head_matmul",
        2560,
        262144,
        2,
        QNN_DATATYPE_FLOAT_16,
        undefinedQuantization(),
        undefinedQuantization(),
    };

    QnnModel models[2];
    ModelError_t error = MODEL_NO_ERROR;
    VALIDATE(addProjectionGraph(models[0],
                                backendHandle,
                                interface,
                                contextHandle,
                                graphsConfigInfo,
                                numGraphsConfigInfo,
                                debug,
                                qSpec,
                                qWeights,
                                qScales),
             error);
    VALIDATE(addProjectionGraph(models[1],
                                backendHandle,
                                interface,
                                contextHandle,
                                graphsConfigInfo,
                                numGraphsConfigInfo,
                                debug,
                                headSpec,
                                headWeights,
                                headScales),
             error);
    VALIDATE(getGraphInfoFromModels(models, 2, graphsInfo), error);
    *numGraphsInfo = 2;
    return MODEL_NO_ERROR;
  } catch (...) {
    return MODEL_MEMORY_ALLOCATE_ERROR;
  }
}

QNN_API
ModelError_t QnnModel_freeGraphsInfo(GraphInfoPtr_t** graphs, uint32_t numGraphsInfo) {
  return qnn_wrapper_api::freeGraphsInfo(graphs, numGraphsInfo);
}
}
'''


def render_build_script() -> str:
    checks = "\n".join(
        f"check_sha {digest} \"$QAIRT_ROOT/{relative}\""
        for relative, digest in QAIRT_BUILD_SOURCE_SHA256.items()
    )
    return f'''#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
QAIRT_ROOT="${{QAIRT_ROOT:?QAIRT_ROOT must point to QAIRT 2.44.0.260225}}"
CXX="${{CXX:-clang++-14}}"
BUILD="$ROOT/build"
CXX_STANDARD="-std=c++20"

check_sha() {{
  local expected="$1"
  local file="$2"
  test -f "$file"
  local observed
  observed="$(sha256sum "$file" | awk '{{print $1}}')"
  test "$observed" = "$expected"
}}

{checks}
mkdir -m 0750 "$BUILD"
export SOURCE_DATE_EPOCH=0
cd "$ROOT"

if ! printf 'int main(){{return 0;}}\n' | "$CXX" "$CXX_STANDARD" -x c++ -fsyntax-only - >/dev/null 2>&1; then
  CXX_STANDARD="-std=c++2a"
  printf 'int main(){{return 0;}}\n' | "$CXX" "$CXX_STANDARD" -x c++ -fsyntax-only - >/dev/null
fi

"$CXX" -c -fPIC -x assembler-with-cpp source/packed_tensors.S -o "$BUILD/packed_tensors.o"
"$CXX" \
  "$CXX_STANDARD" -O2 -fPIC -fvisibility=hidden -shared \
  '-DQNN_API=__attribute__((visibility("default")))' \
  -I"$QAIRT_ROOT/include/QNN" \
  -I"$QAIRT_ROOT/share/QNN/converter/jni" \
  -I"$QAIRT_ROOT/share/QNN/converter/jni/linux" \
  "$QAIRT_ROOT/share/QNN/converter/jni/QnnModel.cpp" \
  "$QAIRT_ROOT/share/QNN/converter/jni/QnnWrapperUtils.cpp" \
  "$QAIRT_ROOT/share/QNN/converter/jni/linux/QnnModelPal.cpp" \
  source/direct_qnn_probes.cpp \
  "$BUILD/packed_tensors.o" \
  -ldl \
  -Wl,--build-id=sha1 \
  -o "$BUILD/libgemma4_e4b_f5_lowbit_probes.so"

test -s "$BUILD/libgemma4_e4b_f5_lowbit_probes.so"
nm -D "$BUILD/libgemma4_e4b_f5_lowbit_probes.so" | grep -q 'QnnModel_composeGraphs'
python3 - \
  "$BUILD/libgemma4_e4b_f5_lowbit_probes.so" \
  "$BUILD/build_receipt.json" \
  "$ROOT/package_manifest.json" \
  "$ROOT/package_manifest.sha256" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

def reject_constant(value):
    raise SystemExit(f"non-finite JSON constant: {{value}}")

def reject_duplicates(pairs):
    result = {{}}
    for key, value in pairs:
        if key in result:
            raise SystemExit(f"duplicate JSON key: {{key}}")
        result[key] = value
    return result

def read_regular(path):
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise SystemExit(f"not a regular file: {{path}}")
        chunks = []
        while chunk := os.read(descriptor, 8 * 1024 * 1024):
            chunks.append(chunk)
        return metadata, b"".join(chunks)
    finally:
        os.close(descriptor)

def digest(path):
    metadata, data = read_regular(path)
    return {{"bytes": metadata.st_size, "sha256": hashlib.sha256(data).hexdigest()}}

def strict_load(path):
    _, data = read_regular(path)
    return json.loads(data, parse_constant=reject_constant, object_pairs_hook=reject_duplicates)

def write_exclusive(path, data):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        view = memoryview(data)
        while view:
            count = os.write(descriptor, view)
            if count <= 0:
                raise SystemExit("short receipt write")
            view = view[count:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    parent = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
    try:
        os.fsync(parent)
    finally:
        os.close(parent)

library = Path(sys.argv[1])
receipt = Path(sys.argv[2])
manifest_path = Path(sys.argv[3])
manifest_sha_path = Path(sys.argv[4])
manifest = strict_load(manifest_path)
manifest_digest = digest(manifest_path)
_, manifest_sha_bytes = read_regular(manifest_sha_path)
expected_sha_line = (manifest_digest["sha256"] + "  package_manifest.json").encode("ascii") + bytes([10])
if manifest_sha_bytes != expected_sha_line:
    raise SystemExit("package manifest sidecar mismatch")
if manifest.get("status") != "proposed_executable_backend_unvalidated":
    raise SystemExit("package manifest status mismatch")
payload = {{
    "schema_version": "gemma4_e4b_f5_qnn_model_build_receipt_v1",
    "status": "source_compile_passed_backend_unvalidated",
    "library": digest(library),
    "package_manifest": manifest_digest,
    "qairt_version": "{QAIRT_VERSION}",
    "graph_names": ["{Q_PROJ_GRAPH}", "{LM_HEAD_GRAPH}"],
    "backend_context_generated": False,
    "phone_execution_count": 0,
}}
encoded = (json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\\n").encode("utf-8")
write_exclusive(receipt, encoded)
PY
'''


def render_context_script() -> str:
    return f'''#!/usr/bin/env bash
set -euo pipefail

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
QAIRT_ROOT="${{QAIRT_ROOT:?QAIRT_ROOT must point to the chroot-visible QAIRT 2.44 root}}"
REFERENCE_GATE="${{REFERENCE_GATE:?REFERENCE_GATE must be the dedicated passed reference gate}}"
BUILD_RECEIPT="$ROOT/build/build_receipt.json"
OUT="$ROOT/context"

python3 - "$REFERENCE_GATE" "$BUILD_RECEIPT" "$ROOT" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

def reject_constant(value):
    raise SystemExit(f"non-finite JSON constant: {{value}}")

def reject_duplicates(pairs):
    result = {{}}
    for key, value in pairs:
        if key in result:
            raise SystemExit(f"duplicate JSON key: {{key}}")
        result[key] = value
    return result

def read_regular(path):
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise SystemExit(f"not a regular file: {{path}}")
        chunks = []
        while chunk := os.read(descriptor, 8 * 1024 * 1024):
            chunks.append(chunk)
    finally:
        os.close(descriptor)
    return metadata, b"".join(chunks)

def strict_load(path):
    _, data = read_regular(path)
    return json.loads(data, parse_constant=reject_constant, object_pairs_hook=reject_duplicates)

def digest(path):
    metadata, data = read_regular(path)
    return {{"bytes": metadata.st_size, "sha256": hashlib.sha256(data).hexdigest()}}

reference = strict_load(Path(sys.argv[1]))
build = strict_load(Path(sys.argv[2]))
root = Path(sys.argv[3])
backend = strict_load(root / "config/backend.json")
extensions = strict_load(root / "config/extensions.json")
expected_backend = {{
    "graphs": [
        {{"graph_names": ["{Q_PROJ_GRAPH}"], "vtcm_mb": 2}},
        {{"graph_names": ["{LM_HEAD_GRAPH}"], "vtcm_mb": 2}},
    ],
    "devices": [{{"soc_model": 69, "dsp_arch": "v79"}}],
}}
expected_extensions = {{
    "backend_extensions": {{
        "shared_library_path": "/opt/qairt/lib/libQnnHtpNetRunExtensions.so",
        "config_file_path": "config/backend.json",
    }}
}}
if backend != expected_backend or extensions != expected_extensions:
    raise SystemExit("QAIRT backend/extension config schema mismatch")
expected_reference = {{
    "schema_version": "gemma4_e4b_f5_reference_gate_v1",
    "status": "passed_scope",
    "qat_model_sha256": "{QAT_MODEL_SHA256}",
    "transformers_commit": "{TRANSFORMERS_COMMIT}",
}}
for key, value in expected_reference.items():
    if reference.get(key) != value:
        raise SystemExit(f"reference gate mismatch: {{key}}")
sha256 = re.compile(r"^[0-9a-f]{{64}}$")
if not sha256.fullmatch(str(reference.get("l2_threshold_policy_sha256", ""))):
    raise SystemExit("reference gate lacks a frozen L2 threshold-policy digest")
probes = reference.get("probes")
if not isinstance(probes, dict):
    raise SystemExit("reference gate lacks probe oracle records")
for graph_name in ("{Q_PROJ_GRAPH}", "{LM_HEAD_GRAPH}"):
    probe = probes.get(graph_name)
    if not isinstance(probe, dict):
        raise SystemExit(f"reference gate lacks oracle for {{graph_name}}")
    for digest_name in ("input_sha256", "reference_output_sha256"):
        if not sha256.fullmatch(str(probe.get(digest_name, ""))):
            raise SystemExit(f"invalid {{graph_name}} {{digest_name}}")
if build.get("status") != "source_compile_passed_backend_unvalidated":
    raise SystemExit("build receipt is not green")
if build.get("qairt_version") != "{QAIRT_VERSION}":
    raise SystemExit("build receipt QAIRT version mismatch")
if build.get("graph_names") != ["{Q_PROJ_GRAPH}", "{LM_HEAD_GRAPH}"]:
    raise SystemExit("build receipt graph set mismatch")
observed_library = digest(root / "build/libgemma4_e4b_f5_lowbit_probes.so")
if observed_library != build.get("library"):
    raise SystemExit("current model library does not match the build receipt")
manifest_path = root / "package_manifest.json"
manifest = strict_load(manifest_path)
observed_manifest = digest(manifest_path)
if observed_manifest != build.get("package_manifest"):
    raise SystemExit("current package manifest does not match the build receipt")
_, sidecar = read_regular(root / "package_manifest.sha256")
expected_sidecar = (observed_manifest["sha256"] + "  package_manifest.json").encode("ascii") + bytes([10])
if sidecar != expected_sidecar:
    raise SystemExit("package manifest sidecar mismatch")
if manifest.get("status") != "proposed_executable_backend_unvalidated":
    raise SystemExit("package manifest status mismatch")
if manifest.get("artifact", {{}}).get("carrier_sha256") != "{QAT_MODEL_SHA256}":
    raise SystemExit("package manifest artifact mismatch")
PY

mkdir -m 0750 "$OUT"
cd "$ROOT"
timeout 1800 "$QAIRT_ROOT/bin/qnn-context-binary-generator" \
  --backend="$QAIRT_ROOT/lib/libQnnHtp.so" \
  --model="$ROOT/build/libgemma4_e4b_f5_lowbit_probes.so" \
  --binary_file=gemma4_e4b_f5_lowbit_probes_v79 \
  --output_dir="$OUT" \
  --config_file="$ROOT/config/extensions.json" \
  --log_level=info >"$OUT/context_generator.log" 2>&1
test -s "$OUT/gemma4_e4b_f5_lowbit_probes_v79.bin"
"$QAIRT_ROOT/bin/qnn-context-binary-utility" \
  --context_binary="$OUT/gemma4_e4b_f5_lowbit_probes_v79.bin" \
  --json_file="$OUT/context_info.json" >"$OUT/context_utility.log" 2>&1
test -s "$OUT/context_info.json"
python3 - "$OUT" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

def reject_constant(value):
    raise SystemExit(f"non-finite JSON constant: {{value}}")

def reject_duplicates(pairs):
    result = {{}}
    for key, value in pairs:
        if key in result:
            raise SystemExit(f"duplicate JSON key: {{key}}")
        result[key] = value
    return result

def strict_load(path):
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise SystemExit(f"not a regular JSON file: {{path}}")
        chunks = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
    finally:
        os.close(descriptor)
    return json.loads(b"".join(chunks), parse_constant=reject_constant, object_pairs_hook=reject_duplicates)

def digest(path):
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise SystemExit(f"not a regular file: {{path}}")
        value = hashlib.sha256()
        while chunk := os.read(descriptor, 8 * 1024 * 1024):
            value.update(chunk)
        return {{"bytes": metadata.st_size, "sha256": value.hexdigest()}}
    finally:
        os.close(descriptor)

def write_exclusive(path, data):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        view = memoryview(data)
        while view:
            count = os.write(descriptor, view)
            if count <= 0:
                raise SystemExit("short receipt write")
            view = view[count:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    parent = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
    try:
        os.fsync(parent)
    finally:
        os.close(parent)

root = Path(sys.argv[1])
context = root / "gemma4_e4b_f5_lowbit_probes_v79.bin"
info = root / "context_info.json"
context_info = strict_load(info)
graphs = context_info.get("info", {{}}).get("graphs", [])
graph_names = [entry.get("info", {{}}).get("graphName") for entry in graphs]
if graph_names != ["{Q_PROJ_GRAPH}", "{LM_HEAD_GRAPH}"]:
    raise SystemExit(f"context graph set mismatch: {{graph_names}}")
payload = {{
    "schema_version": "gemma4_e4b_f5_provider_context_receipt_v1",
    "status": "provider_context_generated_phone_unvalidated",
    "context": digest(context),
    "context_info": digest(info),
    "soc_model": 69,
    "dsp_arch": 79,
    "phone_execution_count": 0,
}}
encoded = (json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\\n").encode("utf-8")
write_exclusive(root / "context_receipt.json", encoded)
PY
'''


def _output_contract(projection: ProjectionContract) -> dict[str, Any]:
    if projection is Q_PROJ:
        return {
            "input": {"dtype": "int8", "shape": [1, 1, 2560], "bytes": 2560},
            "output": {"dtype": "int8", "shape": [1, 1, 2048], "bytes": 2048},
            "lowering_oracle": {
                "digest_algorithm": "sha256",
                "digest_scope": "entire_raw_tensor_file",
                "byte_order": "little_endian",
                "required_input_sha256": None,
                "required_reference_output_sha256": None,
                "required_qnn_output_sha256": None,
                "pass_rule": "qnn_output_sha256_equals_reference_output_sha256",
            },
            "qat_edge_b": "dequantize output with exact output SRQ scale and compare under frozen L2 thresholds",
        }
    return {
        "input": {"dtype": "float16", "shape": [1, 1, 2560], "bytes": 5120},
        "output": {
            "dtype": "float16",
            "shape": [1, 1, 262144],
            "bytes": 524288,
            "surface": "full_pre_softcap_logits",
        },
        "lowering_oracle": {
            "digest_algorithm": "sha256",
            "digest_scope": "entire_raw_tensor_file",
            "byte_order": "little_endian_ieee754_binary16",
            "required_input_sha256": None,
            "required_reference_output_sha256": None,
            "required_qnn_output_sha256": None,
            "raw_digests_recorded": True,
            "pass_rule": "frozen_before_observation_L2_numeric_thresholds_required",
        },
        "qat_edge_b": (
            "measure QAT BF16 to candidate FP16 projection drift separately; "
            "provider context success cannot admit this edge"
        ),
    }


def _manifest(
    *,
    carrier_bytes: int,
    carrier_sha256: str | None,
    tensor_files: list[dict[str, Any]],
    generated_files: list[dict[str, Any]],
) -> dict[str, Any]:
    if carrier_bytes != QAT_MODEL_BYTES or carrier_sha256 != QAT_MODEL_SHA256:
        raise ProbeContractError("manifest construction requires the complete pinned provider artifact")
    return {
        "schema_version": "gemma4_e4b_f5_direct_qnn_probe_package_v1",
        "status": "proposed_executable_backend_unvalidated",
        "claim_class": "source_generation_only",
        "artifact": {
            "repository": QAT_REPOSITORY,
            "revision": QAT_REVISION,
            "expected_bytes": QAT_MODEL_BYTES,
            "expected_sha256": QAT_MODEL_SHA256,
            "carrier_bytes": carrier_bytes,
            "carrier_sha256": carrier_sha256,
            "full_provider_identity_green": True,
        },
        "source_evidence": {
            "transformers_commit": TRANSFORMERS_COMMIT,
            "transformers_gemma_quant_sha256": TRANSFORMERS_SOURCE_SHA256[
                "src/transformers/integrations/gemma_quant.py"
            ],
            "qairt_version": QAIRT_VERSION,
            "qairt_qnn_types_sha256": QAIRT_QNN_TYPES_SHA256,
            "qairt_htp_opdef_supplement_sha256": QAIRT_HTP_OPDEF_SUPPLEMENT_SHA256,
            "qairt_build_source_sha256": QAIRT_BUILD_SOURCE_SHA256,
            "config_schema_evidence": {
                "outer_wrapper_source": "lib/python/qti/aisw/core/model_level_api/utils/subprocess_executor.py",
                "htp_backend_schema_document": "docs/QAIRT-Docs/QNN/general/htp/htp_backend.html",
                "validation": "exact_narrow_schema_in_generator_and_context_runner",
            },
        },
        "lowering": {
            "source_packing": "Transformers low lane first: W4 two values/byte; W2 four values/byte",
            "unpack": "lane=(byte >> (lane_index*num_bits)) & mask; signed=lane+signed_shift",
            "q_proj": {
                "packed_sha256": Q_PROJ.weight.data_sha256,
                "logical_weight_shape": [2048, 2560],
                "signed_shift": -8,
                "qnn_weight_dtype": "QNN_DATATYPE_SFIXED_POINT_8",
                "qnn_encoding": "QNN_QUANTIZATION_ENCODING_BW_AXIS_SCALE_OFFSET",
                "bitwidth": 4,
                "axis": 0,
                "transpose_in1": True,
            },
            "lm_head": {
                "packed_sha256": LM_HEAD.weight.data_sha256,
                "logical_weight_shape": [262144, 2560],
                "signed_shift": -2,
                "qnn_weight_dtype": "QNN_DATATYPE_SFIXED_POINT_8",
                "qnn_encoding": "QNN_QUANTIZATION_ENCODING_BW_AXIS_SCALE_OFFSET",
                "bitwidth": 2,
                "axis": 0,
                "transpose_in1": True,
            },
            "raw_u2_u4_direct_matmul_disposition": (
                "rejected_before_build: HTP 2.44 MatMul documents SFixedPoint8 low-bit weights, "
                "not UFixedPoint2/UFixedPoint4 MatMul inputs"
            ),
        },
        "graphs": [
            {
                "name": Q_PROJ_GRAPH,
                "weight_role": Q_PROJ.probe_id,
                "tensor_abi": _output_contract(Q_PROJ),
            },
            {
                "name": LM_HEAD_GRAPH,
                "weight_role": LM_HEAD.probe_id,
                "tensor_abi": _output_contract(LM_HEAD),
            },
        ],
        "tensor_files": tensor_files,
        "generated_files": generated_files,
        "execution_preconditions": {
            "model_library_compile": "QAIRT source hashes must match exactly",
            "context_generation": "dedicated passed reference gate required",
            "phone_execution": "not performed by this package generator",
        },
        "command_matrix": [
            {"stage": "package", "command": "build_gemma4_e4b_f5_qnn_probes.py --safetensors MODEL --output-dir OUT"},
            {"stage": "compile", "command": "QAIRT_ROOT=/opt/qairt OUT/build_model_library.sh"},
            {"stage": "context", "command": "QAIRT_ROOT=/opt/qairt REFERENCE_GATE=gate.json OUT/run_context_generation.sh"},
        ],
        "nonclaims": [
            "no HTP backend acceptance",
            "no phone execution",
            "no QAT-to-QNN numerical fidelity",
            "no full F5 forward-child",
            "no capsule advancement",
        ],
    }


def _file_receipt(path: Path, root: Path) -> dict[str, Any]:
    return {
        "relative_path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": _sha256_path(path),
    }


def _carrier_identity(metadata: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def build_probe_package(
    *,
    safetensors_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Generate an atomic executable probe package from the pinned checkpoint."""

    if output_dir.name in ("", ".", ".."):
        raise ProbeContractError("output directory must have a normal basename")
    try:
        os.lstat(output_dir)
    except FileNotFoundError:
        pass
    else:
        raise ProbeContractError(f"output directory already exists: {output_dir}")

    parent_flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        parent_flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        parent_flags |= os.O_NOFOLLOW
    parent_descriptor = os.open(output_dir.parent, parent_flags)
    temporary = output_dir.with_name(f".{output_dir.name}.tmp.{secrets.token_hex(16)}")
    try:
        os.mkdir(temporary.name, mode=0o750, dir_fd=parent_descriptor)
    except Exception:
        os.close(parent_descriptor)
        raise
    try:
        tensors_dir = temporary / "tensors"
        source_dir = temporary / "source"
        config_dir = temporary / "config"
        tensors_dir.mkdir(mode=0o750)
        source_dir.mkdir(mode=0o750)
        config_dir.mkdir(mode=0o750)

        tensor_files: list[dict[str, Any]] = []
        with _open_regular_nofollow(safetensors_path) as source:
            initial_metadata = os.fstat(source.fileno())
            carrier_bytes = initial_metadata.st_size
            if carrier_bytes != QAT_MODEL_BYTES:
                raise ProbeContractError(
                    f"carrier byte count mismatch: expected {QAT_MODEL_BYTES}, got {carrier_bytes}"
                )
            carrier_sha256 = _sha256_handle(source)
            if carrier_sha256 != QAT_MODEL_SHA256:
                raise ProbeContractError("full carrier SHA-256 mismatch")
            source.seek(0)
            header, data_start = read_safetensors_header(source)
            validate_pinned_header(header)
            verify_probe_payloads(source, header, data_start)
            for projection in PROJECTIONS:
                for tensor_contract in _projection_tensors(projection):
                    tensor_files.append(
                        _copy_tensor(
                            source,
                            data_start=data_start,
                            contract=tensor_contract,
                            destination=tensors_dir / TENSOR_FILENAMES[tensor_contract.name],
                        )
                    )
            stable_sha256 = _sha256_handle(source)
            final_metadata = os.fstat(source.fileno())
            if stable_sha256 != carrier_sha256:
                raise ProbeContractError("carrier content changed during package generation")
            if _carrier_identity(final_metadata) != _carrier_identity(initial_metadata):
                raise ProbeContractError("carrier inode metadata changed during package generation")

        validate_qairt_configs(BACKEND_CONFIG, EXTENSIONS_CONFIG)
        source_files = {
            source_dir / "direct_qnn_probes.cpp": render_direct_qnn_cpp().encode("utf-8"),
            source_dir / "packed_tensors.S": render_packed_tensor_assembly().encode("utf-8"),
            temporary / "build_model_library.sh": render_build_script().encode("utf-8"),
            temporary / "run_context_generation.sh": render_context_script().encode("utf-8"),
            config_dir / "backend.json": (
                json.dumps(BACKEND_CONFIG, indent=2, sort_keys=True, allow_nan=False)
                + "\n"
            ).encode("utf-8"),
            config_dir / "extensions.json": (
                json.dumps(EXTENSIONS_CONFIG, indent=2, sort_keys=True, allow_nan=False)
                + "\n"
            ).encode("utf-8"),
        }
        for path, payload in source_files.items():
            _write_exclusive(path, payload, executable=path.suffix == ".sh")
        generated_files = [_file_receipt(path, temporary) for path in source_files]

        manifest = _manifest(
            carrier_bytes=carrier_bytes,
            carrier_sha256=carrier_sha256,
            tensor_files=tensor_files,
            generated_files=generated_files,
        )
        manifest_path = temporary / "package_manifest.json"
        manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n").encode(
            "utf-8"
        )
        _write_exclusive(manifest_path, manifest_bytes)
        manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
        _write_exclusive(
            temporary / "package_manifest.sha256",
            f"{manifest_sha256}  package_manifest.json\n".encode("ascii"),
        )
        directory_descriptor = os.open(temporary, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
        publish_directory_noreplace(temporary, output_dir)
        os.fsync(parent_descriptor)
        return {
            "output_dir": str(output_dir),
            "manifest_sha256": manifest_sha256,
            "status": manifest["status"],
        }
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    finally:
        os.close(parent_descriptor)
