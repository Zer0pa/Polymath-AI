"""Fail-closed planning for real Gemma 4 E4B packed projection probes.

This module does not export or convert a model.  It binds the smallest useful
Frontier-A probes to the exact, pinned mobile-QAT tensors and emits the memory
and lowering contracts that an exporter/converter experiment must satisfy.

The two probes deliberately retain the full architectural dimensions.  Only
batch and sequence are reduced to one, so an implementation cannot obtain a
pass by substituting a toy projection.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
from typing import Any, BinaryIO, Iterable, Mapping


QAT_REPOSITORY = "google/gemma-4-E4B-it-qat-mobile-transformers"
QAT_REVISION = "9a78a5adac7bca7a9e421634e4b58f41ca7cbca3"
QAT_MODEL_BYTES = 3_525_094_516
QAT_MODEL_SHA256 = "391946da2e0bec22288e9fe50a4d31d2401c9570ba3baaf0ba43d644dadeb1d4"

TRANSFORMERS_VERSION = "5.13.0"
TRANSFORMERS_COMMIT = "6af945f436d85f2b0c5dff9b14feccd27b1d470b"
TRANSFORMERS_SOURCE_SHA256 = {
    "src/transformers/quantizers/quantizer_gemma.py": (
        "9284963540a16cb2373125ef93556d030820fa0fd914d185322d198393cdebef"
    ),
    "src/transformers/integrations/gemma_quant.py": (
        "9bf6d109dfc3540a46953f5b183af766edcf6a044529c12d7751db47ee71cc17"
    ),
    "src/transformers/models/gemma4/modeling_gemma4.py": (
        "6dd0585a12a45f40ec5ad2a8205b7d5e8e895d03361a50ecfcab2b8dd26cd5c6"
    ),
}

QAIRT_VERSION = "2.44.0.260225143659"
QAIRT_SUPPORTED_ONNX_OPS_SHA256 = (
    "3acf59ca9f6ccd01637e314880362a685e39c5ddec354ecd1630fe8946a20c18"
)
QAIRT_ONNX_MATH_TRANSLATIONS_SHA256 = (
    "b765c6b72c53639aebd9c9122092e87d41a74ddecd04e93bdd30e0a12959d349"
)
QAIRT_QNN_TYPES_SHA256 = (
    "c81b11d04ddd9cb995442add4d404eacd604d97325c7190e3cbd831d254f1889"
)
QAIRT_HTP_OPDEF_SUPPLEMENT_SHA256 = (
    "f3f447b4f2f871236d1187db7d216828232f9b16a8561e878f3b40434fab4f37"
)

LITERAL_PACKED_CRITICAL_OPS = frozenset({"BitwiseAnd", "BitShift"})
LITERAL_COMMON_OPS = (
    "Cast",
    "BitwiseAnd",
    "BitShift",
    "Sub",
    "Unsqueeze",
    "Concat",
    "Reshape",
    "Slice",
    "Mul",
    "Where",
    "Div",
    "Round",
    "Clip",
    "MatMul_or_Gemm",
)


class ProbeContractError(ValueError):
    """Raised when metadata cannot identify the exact pinned probe."""


@dataclass(frozen=True)
class TensorContract:
    name: str
    dtype: str
    shape: tuple[int, ...]
    offsets: tuple[int, int]
    data_sha256: str

    @property
    def nbytes(self) -> int:
        return self.offsets[1] - self.offsets[0]


@dataclass(frozen=True)
class ProjectionContract:
    probe_id: str
    prefix: str
    input_features: int
    output_features: int
    num_bits: int
    signed_shift: int
    weight: TensorContract
    weight_scale: TensorContract
    input_activation_scale: TensorContract
    output_activation_scale: TensorContract

    @property
    def logical_weight_values(self) -> int:
        return self.input_features * self.output_features

    @property
    def expected_packed_bytes(self) -> int:
        return (self.logical_weight_values * self.num_bits + 7) // 8

    @property
    def checkpoint_bytes(self) -> int:
        return (
            self.weight.nbytes
            + self.weight_scale.nbytes
            + self.input_activation_scale.nbytes
            + self.output_activation_scale.nbytes
        )


Q_PROJ = ProjectionContract(
    probe_id="w4_layer0_q_proj",
    prefix="model.language_model.layers.0.self_attn.q_proj",
    input_features=2_560,
    output_features=2_048,
    num_bits=4,
    signed_shift=-8,
    input_activation_scale=TensorContract(
        name="model.language_model.layers.0.self_attn.q_proj.input_activation_scale",
        dtype="F32",
        shape=(),
        offsets=(132_353_156, 132_353_160),
        data_sha256="7bb99ff5665e3f7337be1fe1e415f78d7d264490f34ef488925519439ae4603a",
    ),
    output_activation_scale=TensorContract(
        name="model.language_model.layers.0.self_attn.q_proj.output_activation_scale",
        dtype="F32",
        shape=(),
        offsets=(132_353_160, 132_353_164),
        data_sha256="ab7ba497aba98eb8fe7505b6d94d7dcd7a929ea1a251c2f3b99cb7652b9ffa15",
    ),
    weight=TensorContract(
        name="model.language_model.layers.0.self_attn.q_proj.weight",
        dtype="U8",
        shape=(2_048, 1_280),
        offsets=(1_594_640_700, 1_597_262_140),
        data_sha256="bdf9b5c1de7ea89581981c7a9e6b284796bca27e3af818c41d7971abb018ac2d",
    ),
    weight_scale=TensorContract(
        name="model.language_model.layers.0.self_attn.q_proj.weight_scale",
        dtype="F32",
        shape=(2_048, 1),
        offsets=(132_353_164, 132_361_356),
        data_sha256="59ec6c37c568d8317047bb534de354203c74b44153aea3371a95fdd01290d484",
    ),
)

LM_HEAD = ProjectionContract(
    probe_id="w2_untied_lm_head",
    prefix="lm_head",
    input_features=2_560,
    output_features=262_144,
    num_bits=2,
    signed_shift=-2,
    input_activation_scale=TensorContract(
        name="lm_head.input_activation_scale",
        dtype="F32",
        shape=(),
        offsets=(0, 4),
        data_sha256="df3f619804a92fdb4057192dc43dd748ea778adc52bc498ce80524c014b81119",
    ),
    output_activation_scale=TensorContract(
        name="lm_head.output_activation_scale",
        dtype="F32",
        shape=(),
        offsets=(4, 8),
        data_sha256="df3f619804a92fdb4057192dc43dd748ea778adc52bc498ce80524c014b81119",
    ),
    weight=TensorContract(
        name="lm_head.weight",
        dtype="U8",
        shape=(262_144, 640),
        offsets=(433_211_708, 600_983_868),
        data_sha256="4733d4ef634f781c7b4094e0df6c432b53e3390e161d546951ea6806de9e0d07",
    ),
    weight_scale=TensorContract(
        name="lm_head.weight_scale",
        dtype="F32",
        shape=(262_144, 1),
        offsets=(8, 1_048_584),
        data_sha256="870e405117e2b9b91a86a4210dc66de2d46af52c9274ea46c3193dd69b437eb6",
    ),
)

PROJECTIONS = (Q_PROJ, LM_HEAD)


def _strict_json_loads(raw: bytes) -> Any:
    def reject_constant(value: str) -> None:
        raise ProbeContractError(f"non-finite JSON constant is forbidden: {value}")

    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ProbeContractError(f"duplicate JSON key is forbidden: {key}")
            result[key] = value
        return result

    try:
        return json.loads(
            raw,
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProbeContractError(f"invalid SafeTensors header JSON: {exc}") from exc


def read_safetensors_header(handle: BinaryIO) -> tuple[Mapping[str, Any], int]:
    """Read a SafeTensors header and return ``(header, data_start)``.

    Reading only the header intentionally supports a partial carrier used for
    diagnostic planning.  Promotion still requires the full provider SHA-256.
    """

    length_raw = handle.read(8)
    if len(length_raw) != 8:
        raise ProbeContractError("truncated SafeTensors length prefix")
    header_length = struct.unpack("<Q", length_raw)[0]
    if header_length == 0 or header_length > 64 * 1024 * 1024:
        raise ProbeContractError(f"implausible SafeTensors header length: {header_length}")
    raw_header = handle.read(header_length)
    if len(raw_header) != header_length:
        raise ProbeContractError("truncated SafeTensors header")
    header = _strict_json_loads(raw_header)
    if not isinstance(header, dict):
        raise ProbeContractError("SafeTensors header must be an object")
    return header, 8 + header_length


def _tensor_metadata(header: Mapping[str, Any], contract: TensorContract) -> Mapping[str, Any]:
    metadata = header.get(contract.name)
    if not isinstance(metadata, dict):
        raise ProbeContractError(f"missing tensor metadata: {contract.name}")
    if metadata.get("dtype") != contract.dtype:
        raise ProbeContractError(f"dtype mismatch for {contract.name}")
    shape = metadata.get("shape")
    if not isinstance(shape, list) or tuple(shape) != contract.shape:
        raise ProbeContractError(f"shape mismatch for {contract.name}")
    offsets = metadata.get("data_offsets")
    if not isinstance(offsets, list) or tuple(offsets) != contract.offsets:
        raise ProbeContractError(f"offset mismatch for {contract.name}")
    return metadata


def validate_pinned_header(header: Mapping[str, Any]) -> None:
    for projection in PROJECTIONS:
        for contract in (
            projection.weight,
            projection.weight_scale,
            projection.input_activation_scale,
            projection.output_activation_scale,
        ):
            _tensor_metadata(header, contract)
        if projection.weight.nbytes != projection.expected_packed_bytes:
            raise ProbeContractError(f"packed width mismatch for {projection.probe_id}")


def _hash_range(handle: BinaryIO, start: int, length: int) -> str:
    handle.seek(start)
    remaining = length
    digest = hashlib.sha256()
    while remaining:
        chunk = handle.read(min(remaining, 8 * 1024 * 1024))
        if not chunk:
            raise ProbeContractError("carrier ends before a probe tensor is complete")
        digest.update(chunk)
        remaining -= len(chunk)
    return digest.hexdigest()


def verify_probe_payloads(handle: BinaryIO, header: Mapping[str, Any], data_start: int) -> dict[str, str]:
    """Hash only the eight exact tensors used by the two probes."""

    validate_pinned_header(header)
    result: dict[str, str] = {}
    for projection in PROJECTIONS:
        for contract in (
            projection.weight,
            projection.weight_scale,
            projection.input_activation_scale,
            projection.output_activation_scale,
        ):
            observed = _hash_range(handle, data_start + contract.offsets[0], contract.nbytes)
            if observed != contract.data_sha256:
                raise ProbeContractError(f"payload digest mismatch for {contract.name}")
            result[contract.name] = observed
    return result


def _memory_contract(projection: ProjectionContract, sequence_length: int) -> dict[str, Any]:
    values = projection.logical_weight_values
    checkpoint = projection.checkpoint_bytes
    return {
        "logical_weight_values": values,
        "packed_weight_bytes": projection.weight.nbytes,
        "scale_bytes": projection.weight_scale.nbytes,
        "checkpoint_probe_bytes_including_srq_scales": checkpoint,
        "dense_bfloat16_weight_bytes": values * 2,
        "dense_float32_weight_bytes": values * 4,
        "dense_bfloat16_expansion_ratio": (values * 2) / checkpoint,
        "dense_float32_expansion_ratio": (values * 4) / checkpoint,
        "input_bfloat16_bytes": sequence_length * projection.input_features * 2,
        "output_bfloat16_bytes": sequence_length * projection.output_features * 2,
        "output_float32_bytes": sequence_length * projection.output_features * 4,
    }


def _direct_qnn_contract(projection: ProjectionContract) -> dict[str, Any]:
    if projection is Q_PROJ:
        input_abi = {
            "shape": [1, 1, projection.input_features],
            "data_type": "QNN_DATATYPE_SFIXED_POINT_8",
            "encoding": "QNN_QUANTIZATION_ENCODING_SCALE_OFFSET",
            "scale_tensor": projection.input_activation_scale.name,
            "offset": 0,
        }
        output_abi = {
            "shape": [1, 1, projection.output_features],
            "data_type": "QNN_DATATYPE_SFIXED_POINT_8",
            "encoding": "QNN_QUANTIZATION_ENCODING_SCALE_OFFSET",
            "scale_tensor": projection.output_activation_scale.name,
            "offset": 0,
        }
    else:
        input_abi = {
            "shape": [1, 1, projection.input_features],
            "data_type": "QNN_DATATYPE_FLOAT_16",
            "reason": "HTP MatMul documents FP16 activation plus SFixedPoint8 static weight; QAT BF16 drift remains an L2 measurement",
        }
        output_abi = {
            "shape": [1, 1, projection.output_features],
            "data_type": "QNN_DATATYPE_FLOAT_16",
            "surface": "full_pre_softcap_vocabulary",
        }
    return {
        "op": "QNN_OP_MAT_MUL",
        "source_packed_weight": {
            "shape_bytes": list(projection.weight.shape),
            "data_sha256": projection.weight.data_sha256,
            "packing": f"{8 // projection.num_bits}_values_per_byte_lsb_lane_first",
        },
        "deterministic_host_lowering": {
            "operation": "unpack_each_lane_then_add_signed_shift",
            "signed_shift": projection.signed_shift,
            "logical_int8_values": projection.logical_weight_values,
            "transient_bytes": projection.logical_weight_values,
        },
        "weight_logical_shape": [projection.output_features, projection.input_features],
        "transpose_in1": True,
        "weight_data_type": "QNN_DATATYPE_SFIXED_POINT_8",
        "weight_quantization": {
            "encoding": "QNN_QUANTIZATION_ENCODING_BW_AXIS_SCALE_OFFSET",
            "bitwidth": projection.num_bits,
            "axis_before_transpose": 0,
            "num_scales": projection.output_features,
            "offsets": None,
            "symmetry": "signed_symmetric",
            "scale_tensor": projection.weight_scale.name,
        },
        "input_abi": input_abi,
        "output_abi": output_abi,
        "htp_2_44_documented_constraint": (
            "MatMul low-bit weights are supplied as static SFixedPoint8 with "
            "BW_AXIS_SCALE_OFFSET; raw UFixedPoint2/4 is not a documented MatMul ABI"
        ),
        "backend_acceptance": "unproven_until_soc69_dsp79_context_generation_and_phone_execution",
    }


def _matmul_nbits_contract(projection: ProjectionContract) -> dict[str, Any]:
    if projection.num_bits != 4:
        return {
            "status": "hard_reject_by_qairt_2_44_importer",
            "reason": "OnnxMatMulnBitsTranslation asserts bits == 4",
        }
    block_size = projection.input_features
    return {
        "status": "admissible_probe_not_yet_executed",
        "domain": "com.microsoft",
        "op_type": "MatMulNBits",
        "attributes": {
            "K": projection.input_features,
            "N": projection.output_features,
            "bits": 4,
            "block_size": block_size,
        },
        "B_shape": [projection.output_features, 1, block_size // 2],
        "scale_shape": [projection.output_features, 1],
        "zero_point_shape": [projection.output_features, 1],
        "zero_point_byte": "0x88",
        "zero_point_value_per_nibble": 8,
        "qairt_converter_float32_dequantization_transient_bytes": (
            projection.logical_weight_values * 4
        ),
        "warning": (
            "QAIRT reconstructs a float32 constant during conversion before attaching "
            "PER_BLOCK encoding; single-probe success does not prove full-model peak memory"
        ),
    }


def build_probe_plan(
    *,
    supported_onnx_ops: Iterable[str],
    carrier_bytes: int | None,
    full_artifact_sha256: str | None,
    sequence_length: int = 1,
) -> dict[str, Any]:
    """Build a deterministic falsification plan from already-validated metadata."""

    if sequence_length <= 0:
        raise ProbeContractError("sequence_length must be positive")
    supported = frozenset(supported_onnx_ops)
    unsupported_critical = sorted(LITERAL_PACKED_CRITICAL_OPS - supported)
    full_identity = (
        carrier_bytes == QAT_MODEL_BYTES and full_artifact_sha256 == QAT_MODEL_SHA256
    )
    probes = []
    for projection in PROJECTIONS:
        probes.append(
            {
                "probe_id": projection.probe_id,
                "architectural_dimensions": {
                    "batch": 1,
                    "sequence": sequence_length,
                    "input_features": projection.input_features,
                    "output_features": projection.output_features,
                    "num_bits": projection.num_bits,
                },
                "real_tensors": [
                    projection.weight.name,
                    projection.weight_scale.name,
                    projection.input_activation_scale.name,
                    projection.output_activation_scale.name,
                ],
                "memory": _memory_contract(projection, sequence_length),
                "literal_transformers_export": {
                    "expected_nodes_if_not_constant_folded": list(LITERAL_COMMON_OPS),
                    "unsupported_critical_nodes_in_qairt_2_44": unsupported_critical,
                    "kill_if": [
                        "BitwiseAnd or BitShift survives into ONNX",
                        "packed initializer is replaced by a dense logical weight initializer",
                        "output differs from the pinned Transformers reference",
                    ],
                },
                "onnx_matmul_nbits": _matmul_nbits_contract(projection),
                "direct_qnn_low_bit": _direct_qnn_contract(projection),
            }
        )
    return {
        "schema_version": "gemma4_e4b_f5_real_projection_probe_plan_v1",
        "claim_class": "diagnostic_plan_only",
        "artifact": {
            "repository": QAT_REPOSITORY,
            "revision": QAT_REVISION,
            "expected_bytes": QAT_MODEL_BYTES,
            "expected_sha256": QAT_MODEL_SHA256,
            "carrier_bytes": carrier_bytes,
            "observed_full_sha256": full_artifact_sha256,
            "full_provider_identity_green": full_identity,
        },
        "source_identity": {
            "transformers_version": TRANSFORMERS_VERSION,
            "transformers_commit": TRANSFORMERS_COMMIT,
            "transformers_source_sha256": TRANSFORMERS_SOURCE_SHA256,
            "qairt_version": QAIRT_VERSION,
            "qairt_supported_onnx_ops_sha256": QAIRT_SUPPORTED_ONNX_OPS_SHA256,
            "qairt_onnx_math_translations_sha256": QAIRT_ONNX_MATH_TRANSLATIONS_SHA256,
            "qairt_qnn_types_sha256": QAIRT_QNN_TYPES_SHA256,
            "qairt_htp_opdef_supplement_sha256": QAIRT_HTP_OPDEF_SUPPLEMENT_SHA256,
        },
        "preconditions": {
            "reference_stack_passed": False,
            "full_provider_artifact_identity_required_before_conversion": True,
            "phone_private_state_allowed_on_provider": False,
        },
        "probes": probes,
        "decision_order": [
            "Run the W4 literal export once; kill literal export on unsupported bitwise nodes or densification.",
            "Run W4 MatMulNBits and direct-QNN packed probes against the same real tensor and oracle.",
            "Run the direct-QNN UFixedPoint2 head because QAIRT MatMulNBits cannot represent W2.",
            "Use unpacked U8 plus QDQ only as a semantic diagnostic if packed UFixedPoint2 is rejected; it is not a memory-authority pass.",
        ],
        "promotion": {
            "capsule_advance_allowed": False,
            "reason": "metadata planning and slice identity do not establish converter or phone execution",
        },
    }


def inspect_carrier(path: Path, *, supported_onnx_ops: Iterable[str]) -> dict[str, Any]:
    """Validate probe slices in a full or partial carrier and return a plan."""

    carrier_bytes = path.stat().st_size
    full_sha256 = None
    with path.open("rb") as handle:
        header, data_start = read_safetensors_header(handle)
        tensor_digests = verify_probe_payloads(handle, header, data_start)
    if carrier_bytes == QAT_MODEL_BYTES:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(8 * 1024 * 1024):
                digest.update(chunk)
        full_sha256 = digest.hexdigest()
        if full_sha256 != QAT_MODEL_SHA256:
            raise ProbeContractError("full carrier SHA-256 does not match the pinned artifact")
    plan = build_probe_plan(
        supported_onnx_ops=supported_onnx_ops,
        carrier_bytes=carrier_bytes,
        full_artifact_sha256=full_sha256,
    )
    plan["artifact"]["verified_probe_tensor_sha256"] = tensor_digests
    return plan
