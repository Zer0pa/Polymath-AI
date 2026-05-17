#include "polymath/gemma4/layer_pack_reader.h"

#include <fstream>
#include <sstream>
#include <string>
#include <utility>

namespace polymath::gemma4 {
namespace {

std::string join_path(const std::string& base, const std::string& leaf) {
  if (base.empty() || base.back() == '/') {
    return base + leaf;
  }
  return base + "/" + leaf;
}

bool file_exists(const std::string& path) {
  std::ifstream file(path, std::ios::binary);
  return static_cast<bool>(file);
}

std::string read_text_file(const std::string& path) {
  std::ifstream file(path);
  if (!file) {
    return {};
  }
  std::ostringstream buffer;
  buffer << file.rdbuf();
  return buffer.str();
}

bool contains(const std::string& haystack, const std::string& needle) {
  return haystack.find(needle) != std::string::npos;
}

std::uint32_t parse_unsigned_field(const std::string& text,
                                   const std::string& field_name,
                                   std::uint32_t fallback) {
  const std::size_t field = text.find("\"" + field_name + "\"");
  if (field == std::string::npos) {
    return fallback;
  }
  const std::size_t colon = text.find(':', field);
  if (colon == std::string::npos) {
    return fallback;
  }
  std::size_t cursor = colon + 1U;
  while (cursor < text.size() && (text[cursor] < '0' || text[cursor] > '9')) {
    ++cursor;
  }
  std::uint32_t value = 0U;
  bool found_digit = false;
  while (cursor < text.size() && text[cursor] >= '0' && text[cursor] <= '9') {
    found_digit = true;
    value = (value * 10U) + static_cast<std::uint32_t>(text[cursor] - '0');
    ++cursor;
  }
  return found_digit ? value : fallback;
}

Status validate_contract_text(const std::string& contract) {
  const std::pair<const char*, const char*> required[] = {
      {"model id", "google/gemma-4-E4B"},
      {"revision", "7aa32e6889efd6300124851b164f8b364314c3d8"},
      {"layer index", "\"layer_index\""},
      {"sequence length", "\"seq\""},
      {"hidden size", "\"hidden_size\""},
      {"activation", "gelu_pytorch_tanh"},
      {"comparison method", "cosine"}};

  for (const auto& item : required) {
    if (!contains(contract, item.second)) {
      return Status::invalid(std::string("contract missing ") + item.first);
    }
  }
  return Status::ok();
}

}  // namespace

Status::Status(std::string message) : message_(std::move(message)) {}

Status Status::ok() {
  return Status("");
}

Status Status::invalid(std::string message) {
  return Status(std::move(message));
}

bool Status::is_ok() const {
  return message_.empty();
}

const std::string& Status::message() const {
  return message_;
}

LayerPackValidation LayerPackReader::validate(const std::string& pack_dir) const {
  LayerPackValidation validation{Status::ok(), {}, {}};
  const std::string contract_path = join_path(pack_dir, "contract.json");
  const std::string manifest_path = join_path(pack_dir, "manifest.json");
  const std::string checksums_path = join_path(pack_dir, "checksums/sha256.txt");

  const std::string required_paths[] = {contract_path, manifest_path, checksums_path};
  for (const std::string& path : required_paths) {
    validation.checked_paths.push_back(path);
    if (!file_exists(path)) {
      validation.status = Status::invalid("missing required layer pack file: " + path);
      return validation;
    }
  }

  const std::string contract_text = read_text_file(contract_path);
  validation.status = validate_contract_text(contract_text);
  if (!validation.status.is_ok()) {
    return validation;
  }

  validation.contract.model_id = "google/gemma-4-E4B";
  validation.contract.revision = "7aa32e6889efd6300124851b164f8b364314c3d8";
  validation.contract.layer_index = parse_unsigned_field(contract_text, "layer_index", 0U);
  validation.contract.batch = 1U;
  validation.contract.sequence_length = 128U;
  validation.contract.hidden_size = 2560U;
  validation.contract.attention_heads = 8U;
  validation.contract.key_value_heads = 2U;
  validation.contract.head_dim = 256U;
  validation.contract.intermediate_size = 10240U;
  validation.contract.activation = "gelu_pytorch_tanh";
  validation.contract.rms_norm_epsilon = 1.0e-6F;
  return validation;
}

}  // namespace polymath::gemma4
