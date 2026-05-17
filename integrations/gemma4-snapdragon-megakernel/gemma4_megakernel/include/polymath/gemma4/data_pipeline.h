#ifndef POLYMATH_GEMMA4_DATA_PIPELINE_H_
#define POLYMATH_GEMMA4_DATA_PIPELINE_H_

#include <cstdint>
#include <string>

#include "polymath/gemma4/status.h"

namespace polymath::gemma4 {

Status run_tokenize_pack(const std::string& tokenizer_dir,
                         const std::string& raw_text_path,
                         const std::string& output_cache_dir,
                         std::uint32_t sequence_length,
                         std::uint32_t max_sequences,
                         const std::string& source_url);

}  // namespace polymath::gemma4

#endif  // POLYMATH_GEMMA4_DATA_PIPELINE_H_
