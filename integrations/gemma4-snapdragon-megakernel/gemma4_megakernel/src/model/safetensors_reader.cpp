#include "polymath/gemma4/safetensors_reader.h"

#include <algorithm>
#include <cctype>
#include <cstdint>
#include <fstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace polymath::gemma4 {
namespace {

constexpr std::uint64_t kSafetensorsPrefixBytes = 8U;
constexpr std::uint64_t kMaxHeaderBytes = 256ULL * 1024ULL * 1024ULL;

std::uint64_t file_size_bytes(const std::string& path) {
  std::ifstream file(path, std::ios::binary | std::ios::ate);
  if (!file) {
    throw std::runtime_error("safetensors_file_open_failed");
  }
  return static_cast<std::uint64_t>(file.tellg());
}

std::uint64_t load_le64(const char* data) {
  std::uint64_t value = 0U;
  for (std::uint32_t index = 0U; index < 8U; ++index) {
    value |= (static_cast<std::uint64_t>(
                  static_cast<unsigned char>(data[index]))
              << (index * 8U));
  }
  return value;
}

std::string normalize_dtype(std::string value) {
  std::string upper;
  upper.reserve(value.size());
  for (const char character : value) {
    upper.push_back(static_cast<char>(
        std::toupper(static_cast<unsigned char>(character))));
  }
  if (upper == "BF16" || upper == "BFLOAT16") {
    return "bf16";
  }
  if (upper == "F16" || upper == "FLOAT16" || upper == "HALF") {
    return "f16";
  }
  if (upper == "F32" || upper == "FLOAT32" || upper == "FLOAT") {
    return "f32";
  }
  return value;
}

void skip_ws(const std::string& text, std::size_t& cursor) {
  while (cursor < text.size() &&
         std::isspace(static_cast<unsigned char>(text[cursor])) != 0) {
    ++cursor;
  }
}

std::string parse_json_string(const std::string& text, std::size_t& cursor) {
  skip_ws(text, cursor);
  if (cursor >= text.size() || text[cursor] != '"') {
    throw std::runtime_error("safetensors_json_string_expected");
  }
  ++cursor;
  std::string value;
  while (cursor < text.size()) {
    const char character = text[cursor++];
    if (character == '"') {
      return value;
    }
    if (character == '\\') {
      if (cursor >= text.size()) {
        throw std::runtime_error("safetensors_json_escape_truncated");
      }
      value.push_back(text[cursor++]);
      continue;
    }
    value.push_back(character);
  }
  throw std::runtime_error("safetensors_json_string_unterminated");
}

std::uint64_t parse_json_unsigned(const std::string& text,
                                  std::size_t& cursor) {
  skip_ws(text, cursor);
  if (cursor >= text.size() || text[cursor] < '0' || text[cursor] > '9') {
    throw std::runtime_error("safetensors_json_unsigned_expected");
  }
  std::uint64_t value = 0U;
  while (cursor < text.size() && text[cursor] >= '0' && text[cursor] <= '9') {
    value = (value * 10U) +
            static_cast<std::uint64_t>(text[cursor] - '0');
    ++cursor;
  }
  return value;
}

void expect_char(const std::string& text, std::size_t& cursor, char expected) {
  skip_ws(text, cursor);
  if (cursor >= text.size() || text[cursor] != expected) {
    throw std::runtime_error("safetensors_json_expected_token");
  }
  ++cursor;
}

void skip_json_value(const std::string& text, std::size_t& cursor) {
  skip_ws(text, cursor);
  if (cursor >= text.size()) {
    throw std::runtime_error("safetensors_json_value_expected");
  }
  if (text[cursor] == '"') {
    (void)parse_json_string(text, cursor);
    return;
  }
  if (text[cursor] == '{') {
    ++cursor;
    skip_ws(text, cursor);
    if (cursor < text.size() && text[cursor] == '}') {
      ++cursor;
      return;
    }
    while (cursor < text.size()) {
      (void)parse_json_string(text, cursor);
      expect_char(text, cursor, ':');
      skip_json_value(text, cursor);
      skip_ws(text, cursor);
      if (cursor < text.size() && text[cursor] == ',') {
        ++cursor;
        continue;
      }
      expect_char(text, cursor, '}');
      return;
    }
  }
  if (text[cursor] == '[') {
    ++cursor;
    skip_ws(text, cursor);
    if (cursor < text.size() && text[cursor] == ']') {
      ++cursor;
      return;
    }
    while (cursor < text.size()) {
      skip_json_value(text, cursor);
      skip_ws(text, cursor);
      if (cursor < text.size() && text[cursor] == ',') {
        ++cursor;
        continue;
      }
      expect_char(text, cursor, ']');
      return;
    }
  }
  while (cursor < text.size()) {
    const char character = text[cursor];
    if (character == ',' || character == '}' || character == ']') {
      return;
    }
    ++cursor;
  }
}

std::string object_value_text(const std::string& text, std::size_t& cursor) {
  skip_ws(text, cursor);
  const std::size_t start = cursor;
  skip_json_value(text, cursor);
  return text.substr(start, cursor - start);
}

std::string string_field(const std::string& object_text,
                         const std::string& field) {
  std::size_t cursor = object_text.find("\"" + field + "\"");
  if (cursor == std::string::npos) {
    throw std::runtime_error("safetensors_tensor_" + field + "_missing");
  }
  cursor = object_text.find(':', cursor);
  if (cursor == std::string::npos) {
    throw std::runtime_error("safetensors_tensor_" + field + "_invalid");
  }
  ++cursor;
  return parse_json_string(object_text, cursor);
}

std::vector<std::uint64_t> unsigned_array_field(const std::string& object_text,
                                                const std::string& field) {
  std::size_t cursor = object_text.find("\"" + field + "\"");
  if (cursor == std::string::npos) {
    throw std::runtime_error("safetensors_tensor_" + field + "_missing");
  }
  cursor = object_text.find(':', cursor);
  if (cursor == std::string::npos) {
    throw std::runtime_error("safetensors_tensor_" + field + "_invalid");
  }
  ++cursor;
  expect_char(object_text, cursor, '[');
  std::vector<std::uint64_t> values;
  skip_ws(object_text, cursor);
  if (cursor < object_text.size() && object_text[cursor] == ']') {
    ++cursor;
    return values;
  }
  while (cursor < object_text.size()) {
    values.push_back(parse_json_unsigned(object_text, cursor));
    skip_ws(object_text, cursor);
    if (cursor < object_text.size() && object_text[cursor] == ',') {
      ++cursor;
      continue;
    }
    expect_char(object_text, cursor, ']');
    return values;
  }
  throw std::runtime_error("safetensors_tensor_" + field + "_unterminated");
}

SafetensorsTensorInfo parse_tensor_info(const std::string& key,
                                        const std::string& object_text,
                                        std::uint64_t tensor_data_start,
                                        std::uint64_t file_size) {
  SafetensorsTensorInfo info;
  info.key = key;
  info.dtype = normalize_dtype(string_field(object_text, "dtype"));
  info.shape = unsigned_array_field(object_text, "shape");
  const std::vector<std::uint64_t> offsets =
      unsigned_array_field(object_text, "data_offsets");
  if (offsets.size() != 2U || offsets[1] < offsets[0]) {
    throw std::runtime_error("safetensors_tensor_data_offsets_invalid");
  }
  if (tensor_data_start + offsets[1] > file_size ||
      tensor_data_start + offsets[1] < tensor_data_start) {
    throw std::runtime_error("safetensors_tensor_range_exceeds_file_size");
  }
  info.data_offset_begin = offsets[0];
  info.data_offset_end = offsets[1];
  info.absolute_data_offset_begin = tensor_data_start + offsets[0];
  info.absolute_data_offset_end = tensor_data_start + offsets[1];
  info.byte_length = offsets[1] - offsets[0];
  return info;
}

std::vector<SafetensorsTensorInfo> parse_safetensors_header(
    const std::string& header_text,
    std::uint64_t tensor_data_start,
    std::uint64_t file_size) {
  std::vector<SafetensorsTensorInfo> tensors;
  std::size_t cursor = 0U;
  expect_char(header_text, cursor, '{');
  skip_ws(header_text, cursor);
  if (cursor < header_text.size() && header_text[cursor] == '}') {
    return tensors;
  }
  while (cursor < header_text.size()) {
    const std::string key = parse_json_string(header_text, cursor);
    expect_char(header_text, cursor, ':');
    const std::string value_text = object_value_text(header_text, cursor);
    if (key != "__metadata__") {
      tensors.push_back(
          parse_tensor_info(key, value_text, tensor_data_start, file_size));
    }
    skip_ws(header_text, cursor);
    if (cursor < header_text.size() && header_text[cursor] == ',') {
      ++cursor;
      continue;
    }
    expect_char(header_text, cursor, '}');
    break;
  }
  return tensors;
}

bool contains_string(const std::vector<std::string>& values,
                     const std::string& value) {
  return std::find(values.begin(), values.end(), value) != values.end();
}

}  // namespace

Status SafetensorsReader::open(const std::string& path) {
  metadata_ = SafetensorsMetadata{};
  metadata_.path = path;
  try {
    const std::uint64_t file_size = file_size_bytes(path);
    if (file_size < kSafetensorsPrefixBytes) {
      return Status::invalid("safetensors_header_length_missing");
    }
    std::ifstream file(path, std::ios::binary);
    if (!file) {
      return Status::invalid("safetensors_file_open_failed");
    }
    char header_len_bytes[8] = {};
    file.read(header_len_bytes, sizeof(header_len_bytes));
    if (file.gcount() != static_cast<std::streamsize>(sizeof(header_len_bytes))) {
      return Status::invalid("safetensors_header_length_missing");
    }
    const std::uint64_t header_length = load_le64(header_len_bytes);
    if (header_length == 0U) {
      return Status::invalid("safetensors_header_length_invalid");
    }
    if (header_length > kMaxHeaderBytes) {
      return Status::invalid("safetensors_header_length_unbounded");
    }
    const std::uint64_t tensor_data_start =
        kSafetensorsPrefixBytes + header_length;
    if (tensor_data_start > file_size || tensor_data_start < header_length) {
      return Status::invalid("safetensors_header_truncated");
    }
    std::string header_text;
    header_text.resize(static_cast<std::size_t>(header_length));
    file.read(&header_text[0], static_cast<std::streamsize>(header_text.size()));
    if (file.gcount() != static_cast<std::streamsize>(header_text.size())) {
      return Status::invalid("safetensors_header_truncated");
    }

    metadata_.file_size_bytes = file_size;
    metadata_.header_length_bytes = header_length;
    metadata_.tensor_data_start = tensor_data_start;
    metadata_.tensors =
        parse_safetensors_header(header_text, tensor_data_start, file_size);
    if (metadata_.tensors.empty()) {
      return Status::invalid("safetensors_no_tensors");
    }
    return Status::ok();
  } catch (const std::exception& error) {
    return Status::invalid(error.what());
  }
}

const SafetensorsMetadata& SafetensorsReader::metadata() const {
  return metadata_;
}

const SafetensorsTensorInfo* SafetensorsReader::find_tensor(
    const std::string& key) const {
  for (const SafetensorsTensorInfo& tensor : metadata_.tensors) {
    if (tensor.key == key) {
      return &tensor;
    }
  }
  return nullptr;
}

Status SafetensorsReader::validate_tensor(
    const std::string& key,
    const std::vector<std::uint64_t>& expected_shape,
    const std::vector<std::string>& allowed_dtypes) const {
  const SafetensorsTensorInfo* tensor = find_tensor(key);
  if (tensor == nullptr) {
    return Status::invalid("safetensors_tensor_missing:" + key);
  }
  if (!contains_string(allowed_dtypes, tensor->dtype)) {
    return Status::invalid("safetensors_tensor_dtype_unsupported:" + key);
  }
  if (tensor->shape != expected_shape) {
    return Status::invalid("safetensors_tensor_shape_mismatch:" + key);
  }
  if (tensor->absolute_data_offset_end > metadata_.file_size_bytes ||
      tensor->absolute_data_offset_end < tensor->absolute_data_offset_begin) {
    return Status::invalid("safetensors_tensor_range_invalid:" + key);
  }
  return Status::ok();
}

Status SafetensorsReader::read_tensor_bytes(
    const std::string& key,
    std::uint64_t max_bytes,
    std::vector<std::uint8_t>& output) const {
  const SafetensorsTensorInfo* tensor = find_tensor(key);
  if (tensor == nullptr) {
    output.clear();
    return Status::invalid("safetensors_tensor_missing:" + key);
  }
  return read_tensor_slice_bytes(key, 0U, tensor->byte_length, max_bytes, output);
}

Status SafetensorsReader::read_tensor_slice_bytes(
    const std::string& key,
    std::uint64_t tensor_relative_offset,
    std::uint64_t byte_count,
    std::uint64_t max_bytes,
    std::vector<std::uint8_t>& output) const {
  output.clear();
  const SafetensorsTensorInfo* tensor = find_tensor(key);
  if (tensor == nullptr) {
    return Status::invalid("safetensors_tensor_missing:" + key);
  }
  if (tensor->byte_length == 0U) {
    return Status::invalid("safetensors_tensor_empty:" + key);
  }
  if (byte_count == 0U) {
    return Status::invalid("safetensors_tensor_slice_empty:" + key);
  }
  if (max_bytes == 0U || byte_count > max_bytes) {
    return Status::invalid("safetensors_tensor_read_exceeds_limit:" + key);
  }
  if (tensor_relative_offset > tensor->byte_length ||
      byte_count > (tensor->byte_length - tensor_relative_offset)) {
    return Status::invalid("safetensors_tensor_slice_range_invalid:" + key);
  }
  const std::uint64_t absolute_begin =
      tensor->absolute_data_offset_begin + tensor_relative_offset;
  const std::uint64_t absolute_end = absolute_begin + byte_count;
  if (absolute_end > metadata_.file_size_bytes ||
      absolute_end < absolute_begin ||
      absolute_begin < tensor->absolute_data_offset_begin ||
      absolute_end > tensor->absolute_data_offset_end) {
    return Status::invalid("safetensors_tensor_range_invalid:" + key);
  }
  std::ifstream file(metadata_.path, std::ios::binary);
  if (!file) {
    return Status::invalid("safetensors_file_open_failed");
  }
  file.seekg(static_cast<std::streamoff>(absolute_begin), std::ios::beg);
  output.resize(static_cast<std::size_t>(byte_count));
  file.read(reinterpret_cast<char*>(output.data()),
            static_cast<std::streamsize>(output.size()));
  if (file.gcount() != static_cast<std::streamsize>(output.size())) {
    output.clear();
    return Status::invalid("safetensors_tensor_read_truncated:" + key);
  }
  return Status::ok();
}

}  // namespace polymath::gemma4
