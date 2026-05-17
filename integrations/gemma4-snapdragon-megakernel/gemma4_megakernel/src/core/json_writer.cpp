#include "polymath/gemma4/json_writer.h"

namespace polymath::gemma4 {

void write_json_string(std::ostream& stream, const std::string& value) {
  stream << '"';
  for (const char character : value) {
    if (character == '"' || character == '\\') {
      stream << '\\' << character;
      continue;
    }
    if (character == '\n') {
      stream << "\\n";
      continue;
    }
    if (character == '\r') {
      stream << "\\r";
      continue;
    }
    if (character == '\t') {
      stream << "\\t";
      continue;
    }
    stream << character;
  }
  stream << '"';
}

}  // namespace polymath::gemma4
