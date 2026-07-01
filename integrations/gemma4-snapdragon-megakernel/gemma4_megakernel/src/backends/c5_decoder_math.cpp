#include "polymath/gemma4/c5_decoder_math.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <string>
#include <vector>

namespace polymath::gemma4 {
namespace {

std::uint16_t read_le16(const std::uint8_t* bytes) {
  return static_cast<std::uint16_t>(bytes[0]) |
         static_cast<std::uint16_t>(static_cast<std::uint16_t>(bytes[1]) << 8U);
}

std::uint32_t read_le32(const std::uint8_t* bytes) {
  return static_cast<std::uint32_t>(bytes[0]) |
         (static_cast<std::uint32_t>(bytes[1]) << 8U) |
         (static_cast<std::uint32_t>(bytes[2]) << 16U) |
         (static_cast<std::uint32_t>(bytes[3]) << 24U);
}

std::uint64_t element_count(const std::vector<std::uint64_t>& shape) {
  if (shape.empty()) {
    return 0U;
  }
  std::uint64_t count = 1U;
  for (const std::uint64_t value : shape) {
    if (value == 0U ||
        count > (std::numeric_limits<std::uint64_t>::max() / value)) {
      return 0U;
    }
    count *= value;
  }
  return count;
}

Status require_size(const std::vector<std::uint8_t>& bytes,
                    std::uint64_t expected_bytes,
                    const std::string& dtype) {
  if (expected_bytes == 0U || bytes.size() != expected_bytes) {
    return Status::invalid("c5_decoder_math_" + dtype + "_byte_count_mismatch");
  }
  return Status::ok();
}

}  // namespace

float bf16_to_float(std::uint16_t value) {
  const std::uint32_t expanded = static_cast<std::uint32_t>(value) << 16U;
  float result = 0.0F;
  std::memcpy(&result, &expanded, sizeof(float));
  return result;
}

std::uint16_t float_to_bf16_bits(float value) {
  std::uint32_t bits = 0U;
  std::memcpy(&bits, &value, sizeof(float));
  const std::uint32_t round_bias = 0x7FFFU + ((bits >> 16U) & 1U);
  return static_cast<std::uint16_t>((bits + round_bias) >> 16U);
}

float bf16_round(float value) {
  return bf16_to_float(float_to_bf16_bits(value));
}

float f16_to_float(std::uint16_t value) {
  const std::uint32_t sign = static_cast<std::uint32_t>(value & 0x8000U) << 16U;
  const std::uint32_t exponent = static_cast<std::uint32_t>((value >> 10U) & 0x1FU);
  std::uint32_t mantissa = static_cast<std::uint32_t>(value & 0x03FFU);
  std::uint32_t bits = 0U;
  if (exponent == 0U) {
    if (mantissa == 0U) {
      bits = sign;
    } else {
      int normalized_exponent = -14;
      while ((mantissa & 0x0400U) == 0U) {
        mantissa <<= 1U;
        --normalized_exponent;
      }
      mantissa &= 0x03FFU;
      bits = sign |
             (static_cast<std::uint32_t>(normalized_exponent + 127) << 23U) |
             (mantissa << 13U);
    }
  } else if (exponent == 0x1FU) {
    bits = sign | 0x7F800000U | (mantissa << 13U);
  } else {
    bits = sign | ((exponent + 112U) << 23U) | (mantissa << 13U);
  }
  float result = 0.0F;
  std::memcpy(&result, &bits, sizeof(float));
  return result;
}

Status decode_tensor_f32(const SafetensorsTensorInfo& tensor,
                         const std::vector<std::uint8_t>& bytes,
                         std::vector<float>& output) {
  output.clear();
  const std::uint64_t count = element_count(tensor.shape);
  if (count == 0U) {
    return Status::invalid("c5_decoder_math_tensor_shape_invalid:" + tensor.key);
  }
  if (count > static_cast<std::uint64_t>(std::numeric_limits<std::size_t>::max())) {
    return Status::invalid("c5_decoder_math_tensor_too_large:" + tensor.key);
  }

  if (tensor.dtype == "bf16" || tensor.dtype == "f16") {
    const Status size_status = require_size(bytes, count * 2U, tensor.dtype);
    if (!size_status.is_ok()) {
      return size_status;
    }
    output.resize(static_cast<std::size_t>(count));
    for (std::uint64_t index = 0U; index < count; ++index) {
      const std::uint16_t packed =
          read_le16(bytes.data() + static_cast<std::size_t>(index * 2U));
      output[static_cast<std::size_t>(index)] =
          tensor.dtype == "bf16" ? bf16_to_float(packed) : f16_to_float(packed);
    }
    return Status::ok();
  }

  if (tensor.dtype == "f32") {
    const Status size_status = require_size(bytes, count * 4U, tensor.dtype);
    if (!size_status.is_ok()) {
      return size_status;
    }
    output.resize(static_cast<std::size_t>(count));
    for (std::uint64_t index = 0U; index < count; ++index) {
      const std::uint32_t packed =
          read_le32(bytes.data() + static_cast<std::size_t>(index * 4U));
      float value = 0.0F;
      std::memcpy(&value, &packed, sizeof(float));
      output[static_cast<std::size_t>(index)] = value;
    }
    return Status::ok();
  }

  return Status::invalid("c5_decoder_math_tensor_dtype_unsupported:" + tensor.key);
}

Status decode_f32_le_bytes(const std::vector<std::uint8_t>& bytes,
                           std::vector<float>& output) {
  output.clear();
  if (bytes.empty() || (bytes.size() % sizeof(float)) != 0U) {
    return Status::invalid("c5_decoder_math_f32_byte_count_mismatch");
  }
  output.resize(bytes.size() / sizeof(float));
  for (std::size_t index = 0U; index < output.size(); ++index) {
    const std::uint32_t packed = read_le32(bytes.data() + (index * sizeof(float)));
    std::memcpy(&output[index], &packed, sizeof(float));
  }
  return Status::ok();
}

Status rms_norm_weighted(const std::vector<float>& input,
                         const std::vector<float>& weight,
                         std::uint64_t rows,
                         std::uint64_t width,
                         float epsilon,
                         std::vector<float>& output) {
  output.clear();
  if (rows == 0U || width == 0U || weight.size() != width ||
      input.size() != (rows * width)) {
    return Status::invalid("c5_decoder_math_rms_shape_mismatch");
  }
  output.resize(input.size());
  for (std::uint64_t row = 0U; row < rows; ++row) {
    const std::uint64_t base = row * width;
    double sum_sq = 0.0;
    for (std::uint64_t col = 0U; col < width; ++col) {
      const float value = input[static_cast<std::size_t>(base + col)];
      sum_sq += static_cast<double>(value) * static_cast<double>(value);
    }
    const float scale =
        1.0F / std::sqrt(static_cast<float>(sum_sq / width) + epsilon);
    for (std::uint64_t col = 0U; col < width; ++col) {
      const std::size_t index = static_cast<std::size_t>(base + col);
      output[index] = input[index] * scale * weight[static_cast<std::size_t>(col)];
    }
  }
  return Status::ok();
}

Status linear_row_major(const std::vector<float>& input,
                        const std::vector<float>& weight,
                        std::uint64_t rows,
                        std::uint64_t input_width,
                        std::uint64_t output_width,
                        std::vector<float>& output) {
  output.clear();
  if (rows == 0U || input_width == 0U || output_width == 0U ||
      input.size() != (rows * input_width) ||
      weight.size() != (output_width * input_width)) {
    return Status::invalid("c5_decoder_math_linear_shape_mismatch");
  }
  output.assign(static_cast<std::size_t>(rows * output_width), 0.0F);
  for (std::uint64_t row = 0U; row < rows; ++row) {
    for (std::uint64_t out = 0U; out < output_width; ++out) {
      double sum = 0.0;
      for (std::uint64_t col = 0U; col < input_width; ++col) {
        sum += static_cast<double>(
                   input[static_cast<std::size_t>(row * input_width + col)]) *
               static_cast<double>(
                   weight[static_cast<std::size_t>(out * input_width + col)]);
      }
      output[static_cast<std::size_t>(row * output_width + out)] =
          static_cast<float>(sum);
    }
  }
  return Status::ok();
}

Status gelu_tanh_mul(const std::vector<float>& lhs,
                     const std::vector<float>& rhs,
                     std::vector<float>& output) {
  output.clear();
  if (lhs.empty() || lhs.size() != rhs.size()) {
    return Status::invalid("c5_decoder_math_gelu_shape_mismatch");
  }
  output.resize(lhs.size());
  for (std::size_t index = 0U; index < lhs.size(); ++index) {
    const float x = lhs[index];
    const float inner = 0.7978845608028654F * (x + (0.044715F * x * x * x));
    const float gelu = 0.5F * x * (1.0F + std::tanh(inner));
    output[index] = gelu * rhs[index];
  }
  return Status::ok();
}

Status adapter_rank16_residual(const std::vector<float>& input,
                               const std::vector<float>& adapter_a,
                               const std::vector<float>& adapter_b,
                               std::uint64_t rows,
                               std::uint64_t hidden,
                               std::vector<float>& output) {
  constexpr std::uint64_t kRank = 16U;
  output.clear();
  if (rows == 0U || hidden == 0U || input.size() != (rows * hidden) ||
      adapter_a.size() != (hidden * kRank) ||
      adapter_b.size() != (kRank * hidden)) {
    return Status::invalid("c5_decoder_math_adapter_shape_mismatch");
  }
  output = input;
  std::vector<float> z(static_cast<std::size_t>(rows * kRank), 0.0F);
  for (std::uint64_t row = 0U; row < rows; ++row) {
    for (std::uint64_t rank = 0U; rank < kRank; ++rank) {
      double sum = 0.0;
      for (std::uint64_t col = 0U; col < hidden; ++col) {
        sum += static_cast<double>(input[static_cast<std::size_t>(row * hidden + col)]) *
               static_cast<double>(adapter_a[static_cast<std::size_t>(col * kRank + rank)]);
      }
      z[static_cast<std::size_t>(row * kRank + rank)] = static_cast<float>(sum);
    }
  }
  const float scale = 1.0F / static_cast<float>(kRank);
  for (std::uint64_t row = 0U; row < rows; ++row) {
    for (std::uint64_t col = 0U; col < hidden; ++col) {
      double delta = 0.0;
      for (std::uint64_t rank = 0U; rank < kRank; ++rank) {
        delta += static_cast<double>(z[static_cast<std::size_t>(row * kRank + rank)]) *
                 static_cast<double>(adapter_b[static_cast<std::size_t>(rank * hidden + col)]);
      }
      output[static_cast<std::size_t>(row * hidden + col)] +=
          scale * static_cast<float>(delta);
    }
  }
  return Status::ok();
}

Status chunked_nll_from_logits(const std::vector<float>& logits,
                               std::uint32_t vocab_offset,
                               std::uint32_t target_token,
                               ChunkedNllResult& accumulator,
                               bool final_chunk) {
  if (logits.empty()) {
    return Status::invalid("c5_decoder_math_logits_chunk_empty");
  }
  if (!final_chunk && accumulator.confidence != 0.0) {
    return Status::invalid("c5_decoder_math_logits_accumulator_already_final");
  }
  if (!accumulator.has_observed_logits) {
    accumulator.target_logit = -std::numeric_limits<float>::infinity();
    accumulator.argmax_logit = -std::numeric_limits<float>::infinity();
    accumulator.nll = -std::numeric_limits<double>::infinity();
    accumulator.has_observed_logits = true;
  }

  double max_logit = accumulator.nll;
  for (std::size_t index = 0U; index < logits.size(); ++index) {
    const float value = logits[index];
    if (!std::isfinite(value)) {
      return Status::invalid("c5_decoder_math_logits_nonfinite");
    }
    const std::uint32_t token = vocab_offset + static_cast<std::uint32_t>(index);
    if (value > accumulator.argmax_logit) {
      accumulator.argmax_logit = value;
      accumulator.argmax_token = token;
    }
    if (token == target_token) {
      accumulator.target_logit = value;
      accumulator.target_seen = true;
    }
    max_logit = std::max(max_logit, static_cast<double>(value));
  }

  double exp_sum = !std::isfinite(accumulator.nll)
                       ? 0.0
                       : std::exp(accumulator.nll - max_logit);
  for (const float value : logits) {
    exp_sum += std::exp(static_cast<double>(value) - max_logit);
  }
  accumulator.nll = max_logit + std::log(exp_sum);
  if (final_chunk) {
    if (!accumulator.target_seen || !std::isfinite(accumulator.target_logit)) {
      return Status::invalid("c5_decoder_math_target_token_not_observed");
    }
    accumulator.nll -= static_cast<double>(accumulator.target_logit);
    accumulator.confidence = std::exp(-accumulator.nll);
  }
  return Status::ok();
}

}  // namespace polymath::gemma4
