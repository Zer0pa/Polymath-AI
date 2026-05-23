#ifndef POLYMATH_GEMMA4_SHA256_H_
#define POLYMATH_GEMMA4_SHA256_H_

#include <cstdint>
#include <string>
#include <vector>

namespace polymath::gemma4 {

std::string sha256_bytes_hex(const std::vector<std::uint8_t>& bytes);
std::string sha256_text_hex(const std::string& text);
std::string sha256_file_hex(const std::string& path);

}  // namespace polymath::gemma4

#endif  // POLYMATH_GEMMA4_SHA256_H_
