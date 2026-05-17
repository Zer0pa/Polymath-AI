#ifndef POLYMATH_GEMMA4_LAYER_PACK_READER_H_
#define POLYMATH_GEMMA4_LAYER_PACK_READER_H_

#include <cstdint>
#include <string>
#include <vector>

#include "polymath/gemma4/status.h"

namespace polymath::gemma4 {

struct LayerPackContract {
  std::string model_id;
  std::string revision;
  std::uint32_t layer_index;
  std::uint32_t batch;
  std::uint32_t sequence_length;
  std::uint32_t hidden_size;
  std::uint32_t attention_heads;
  std::uint32_t key_value_heads;
  std::uint32_t head_dim;
  std::uint32_t intermediate_size;
  std::string activation;
  float rms_norm_epsilon;
};

struct LayerPackValidation {
  Status status;
  LayerPackContract contract;
  std::vector<std::string> checked_paths;
};

class LayerPackReader {
 public:
  LayerPackValidation validate(const std::string& pack_dir) const;
};

}  // namespace polymath::gemma4

#endif  // POLYMATH_GEMMA4_LAYER_PACK_READER_H_
