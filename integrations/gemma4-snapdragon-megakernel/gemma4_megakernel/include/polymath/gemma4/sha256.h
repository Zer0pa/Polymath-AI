#ifndef POLYMATH_GEMMA4_SHA256_H_
#define POLYMATH_GEMMA4_SHA256_H_

#include <string>

namespace polymath::gemma4 {

std::string sha256_file_hex(const std::string& path);

}  // namespace polymath::gemma4

#endif  // POLYMATH_GEMMA4_SHA256_H_
