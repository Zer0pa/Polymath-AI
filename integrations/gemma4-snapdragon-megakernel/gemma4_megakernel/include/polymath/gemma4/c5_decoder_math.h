#ifndef POLYMATH_GEMMA4_C5_DECODER_MATH_H_
#define POLYMATH_GEMMA4_C5_DECODER_MATH_H_

#include <cstdint>
#include <vector>

#include "polymath/gemma4/safetensors_reader.h"
#include "polymath/gemma4/status.h"

namespace polymath::gemma4 {

struct ChunkedNllResult {
  std::uint32_t argmax_token = 0;
  float argmax_logit = 0.0F;
  float target_logit = 0.0F;
  bool has_observed_logits = false;
  bool target_seen = false;
  double nll = 0.0;
  double confidence = 0.0;
};

float bf16_to_float(std::uint16_t value);
float f16_to_float(std::uint16_t value);

Status decode_tensor_f32(const SafetensorsTensorInfo& tensor,
                         const std::vector<std::uint8_t>& bytes,
                         std::vector<float>& output);
Status decode_f32_le_bytes(const std::vector<std::uint8_t>& bytes,
                           std::vector<float>& output);
Status rms_norm_weighted(const std::vector<float>& input,
                         const std::vector<float>& weight,
                         std::uint64_t rows,
                         std::uint64_t width,
                         float epsilon,
                         std::vector<float>& output);
Status linear_row_major(const std::vector<float>& input,
                        const std::vector<float>& weight,
                        std::uint64_t rows,
                        std::uint64_t input_width,
                        std::uint64_t output_width,
                        std::vector<float>& output);
Status gelu_tanh_mul(const std::vector<float>& lhs,
                     const std::vector<float>& rhs,
                     std::vector<float>& output);
Status adapter_rank16_residual(const std::vector<float>& input,
                               const std::vector<float>& adapter_a,
                               const std::vector<float>& adapter_b,
                               std::uint64_t rows,
                               std::uint64_t hidden,
                               std::vector<float>& output);
Status chunked_nll_from_logits(const std::vector<float>& logits,
                               std::uint32_t vocab_offset,
                               std::uint32_t target_token,
                               ChunkedNllResult& accumulator,
                               bool final_chunk);

}  // namespace polymath::gemma4

#endif  // POLYMATH_GEMMA4_C5_DECODER_MATH_H_
