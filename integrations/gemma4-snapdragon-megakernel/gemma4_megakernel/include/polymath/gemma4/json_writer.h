#ifndef POLYMATH_GEMMA4_JSON_WRITER_H_
#define POLYMATH_GEMMA4_JSON_WRITER_H_

#include <ostream>
#include <string>

namespace polymath::gemma4 {

void write_json_string(std::ostream& stream, const std::string& value);

}  // namespace polymath::gemma4

#endif  // POLYMATH_GEMMA4_JSON_WRITER_H_
