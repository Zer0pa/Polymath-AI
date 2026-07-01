#ifndef POLYMATH_GEMMA4_C5_QA_INFERENCE_H_
#define POLYMATH_GEMMA4_C5_QA_INFERENCE_H_

#include <cstdint>
#include <string>

#include "polymath/gemma4/status.h"

namespace polymath::gemma4 {

struct C5QaInferenceRequest {
  std::string run_label;
  std::string eval_point;
  std::string checkpoint_role;
  std::string checkpoint_payload_path;
  std::string checkpoint_sha256;
  std::string heldout_qa_jsonl_path;
  std::string output_jsonl_path;
  std::string tokenizer_dir;
  std::string decoder_component_pack_dir;
  std::string decoder_manifest_path;
  std::string lm_head_path;
  std::string adapter_site_policy_path;
  std::string opencl_library;
  std::uint32_t vocab_chunk_size = 4096;
  std::uint32_t max_generation_tokens = 128;
};

Status run_c5_qa_predict(const C5QaInferenceRequest& request);

}  // namespace polymath::gemma4

#endif  // POLYMATH_GEMMA4_C5_QA_INFERENCE_H_
