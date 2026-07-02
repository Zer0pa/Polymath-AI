#ifndef POLYMATH_GEMMA4_C5_FULL_DECODER_RUNTIME_H_
#define POLYMATH_GEMMA4_C5_FULL_DECODER_RUNTIME_H_

#include <cstdint>
#include <string>
#include <vector>

#include "polymath/gemma4/c5_qa_inference.h"

namespace polymath::gemma4 {

struct C5FullDecoderRuntimeResult {
  std::vector<std::string> blockers;
  bool prediction_jsonl_written = false;
  std::uint64_t heldout_record_count = 0;
  std::uint64_t prediction_record_count = 0;
  std::uint64_t validated_tensor_count = 0;
  std::string source_model_sha256;
  std::uint64_t source_model_size_bytes = 0;
};

C5FullDecoderRuntimeResult run_c5_full_decoder_runtime(
    const C5QaInferenceRequest& request);

}  // namespace polymath::gemma4

#endif  // POLYMATH_GEMMA4_C5_FULL_DECODER_RUNTIME_H_
