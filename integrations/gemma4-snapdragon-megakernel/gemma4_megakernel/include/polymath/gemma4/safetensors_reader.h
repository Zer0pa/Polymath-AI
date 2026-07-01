#ifndef POLYMATH_GEMMA4_SAFETENSORS_READER_H_
#define POLYMATH_GEMMA4_SAFETENSORS_READER_H_

#include <cstdint>
#include <string>
#include <vector>

#include "polymath/gemma4/status.h"

namespace polymath::gemma4 {

struct SafetensorsTensorInfo {
  std::string key;
  std::string dtype;
  std::vector<std::uint64_t> shape;
  std::uint64_t data_offset_begin = 0;
  std::uint64_t data_offset_end = 0;
  std::uint64_t absolute_data_offset_begin = 0;
  std::uint64_t absolute_data_offset_end = 0;
  std::uint64_t byte_length = 0;
};

struct SafetensorsMetadata {
  std::string path;
  std::uint64_t file_size_bytes = 0;
  std::uint64_t header_length_bytes = 0;
  std::uint64_t tensor_data_start = 0;
  std::vector<SafetensorsTensorInfo> tensors;
};

class SafetensorsReader {
 public:
  Status open(const std::string& path);

  const SafetensorsMetadata& metadata() const;
  const SafetensorsTensorInfo* find_tensor(const std::string& key) const;
  Status validate_tensor(const std::string& key,
                         const std::vector<std::uint64_t>& expected_shape,
                         const std::vector<std::string>& allowed_dtypes) const;
  Status read_tensor_bytes(const std::string& key,
                           std::uint64_t max_bytes,
                           std::vector<std::uint8_t>& output) const;

 private:
  SafetensorsMetadata metadata_;
};

}  // namespace polymath::gemma4

#endif  // POLYMATH_GEMMA4_SAFETENSORS_READER_H_
