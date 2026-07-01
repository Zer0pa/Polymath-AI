#include "polymath/gemma4/c5_full_decoder_runtime.h"

#include <cmath>
#include <algorithm>
#include <cctype>
#include <cstdint>
#include <fstream>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "polymath/gemma4/c5_decoder_math.h"
#include "polymath/gemma4/gemma_bpe_tokenizer.h"
#include "polymath/gemma4/opencl_layer_runner.h"
#include "polymath/gemma4/safetensors_reader.h"
#include "polymath/gemma4/sha256.h"

namespace polymath::gemma4 {
namespace {

constexpr const char* kEmbedTokensKey =
    "model.language_model.embed_tokens.weight";
constexpr const char* kPleTokenKey =
    "model.language_model.embed_tokens_per_layer.weight";
constexpr const char* kPleProjectionNormKey =
    "model.language_model.per_layer_projection_norm.weight";
constexpr const char* kPleProjectionKey =
    "model.language_model.per_layer_model_projection.weight";
constexpr std::uint32_t kLayerCount = 42;
constexpr std::uint32_t kHiddenSize = 2560;
constexpr std::uint32_t kVocabSize = 262144;
constexpr std::uint32_t kIntermediateSize = 10240;
constexpr std::uint32_t kAttentionHeads = 8;
constexpr std::uint32_t kKeyValueHeads = 2;
constexpr std::uint32_t kHeadDim = 256;
constexpr std::uint32_t kSmallInputSize = 256;
constexpr std::uint32_t kAdapterRank = 16;
constexpr std::uint64_t kAdapterPayloadBytes =
    static_cast<std::uint64_t>(kHiddenSize) * kAdapterRank * 2U * sizeof(float);

struct RoleSpec {
  const char* role;
  const char* suffix;
  std::vector<std::uint64_t> shape;
};

struct SourceModelIdentity {
  std::string path;
  std::string sha256;
  std::uint64_t size_bytes = 0;
};

struct QaTokenization {
  std::vector<std::uint32_t> question_tokens;
  std::vector<std::uint32_t> answer_tokens;
};

struct SingleLayerBody {
  std::vector<float> layer_input_row;
  std::vector<float> ple_input_row;
  std::vector<float> output_row;
};

std::vector<RoleSpec> role_specs() {
  return {
      {"input_layernorm", "input_layernorm.weight", {kHiddenSize}},
      {"self_attn_q_proj", "self_attn.q_proj.weight",
       {kAttentionHeads * kHeadDim, kHiddenSize}},
      {"self_attn_k_proj", "self_attn.k_proj.weight",
       {kKeyValueHeads * kHeadDim, kHiddenSize}},
      {"self_attn_v_proj", "self_attn.v_proj.weight",
       {kKeyValueHeads * kHeadDim, kHiddenSize}},
      {"self_attn_o_proj", "self_attn.o_proj.weight",
       {kHiddenSize, kAttentionHeads * kHeadDim}},
      {"self_attn_q_norm", "self_attn.q_norm.weight",
       {kKeyValueHeads * kHeadDim}},
      {"self_attn_k_norm", "self_attn.k_norm.weight",
       {kKeyValueHeads * kHeadDim}},
      {"post_attention_layernorm", "post_attention_layernorm.weight",
       {kHiddenSize}},
      {"pre_feedforward_layernorm", "pre_feedforward_layernorm.weight",
       {kHiddenSize}},
      {"mlp_gate_proj", "mlp.gate_proj.weight",
       {kIntermediateSize, kHiddenSize}},
      {"mlp_up_proj", "mlp.up_proj.weight", {kIntermediateSize, kHiddenSize}},
      {"mlp_down_proj", "mlp.down_proj.weight",
       {kHiddenSize, kIntermediateSize}},
      {"post_feedforward_layernorm", "post_feedforward_layernorm.weight",
       {kHiddenSize}},
      {"per_layer_input_gate", "per_layer_input_gate.weight",
       {kSmallInputSize, kHiddenSize}},
      {"per_layer_projection", "per_layer_projection.weight",
       {kHiddenSize, kSmallInputSize}},
      {"post_per_layer_input_norm", "post_per_layer_input_norm.weight",
       {kHiddenSize}},
      {"layer_scalar", "layer_scalar", {1}},
  };
}

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

std::uint64_t file_size_bytes(const std::string& path) {
  std::ifstream file(path, std::ios::binary | std::ios::ate);
  if (!file) {
    throw std::runtime_error("file_size_open_failed");
  }
  return static_cast<std::uint64_t>(file.tellg());
}

std::string read_text_file(const std::string& path) {
  std::ifstream file(path);
  if (!file) {
    throw std::runtime_error("text_file_read_failed");
  }
  std::string text;
  std::string line;
  while (std::getline(file, line)) {
    text += line;
    text.push_back('\n');
  }
  return text;
}

std::vector<std::uint8_t> read_binary_file_limited(const std::string& path,
                                                   std::uint64_t max_bytes) {
  std::ifstream file(path, std::ios::binary | std::ios::ate);
  if (!file) {
    throw std::runtime_error("binary_file_read_failed");
  }
  const std::uint64_t size = static_cast<std::uint64_t>(file.tellg());
  if (size == 0U || size > max_bytes) {
    throw std::runtime_error("binary_file_size_invalid");
  }
  file.seekg(0, std::ios::beg);
  std::vector<std::uint8_t> bytes(static_cast<std::size_t>(size));
  file.read(reinterpret_cast<char*>(bytes.data()),
            static_cast<std::streamsize>(bytes.size()));
  if (file.gcount() != static_cast<std::streamsize>(bytes.size())) {
    throw std::runtime_error("binary_file_read_truncated");
  }
  return bytes;
}

std::string compact_json_text(const std::string& text) {
  std::string compact;
  compact.reserve(text.size());
  for (const char character : text) {
    if (std::isspace(static_cast<unsigned char>(character)) == 0) {
      compact.push_back(character);
    }
  }
  return compact;
}

bool contains(const std::string& text, const std::string& needle) {
  return text.find(needle) != std::string::npos;
}

bool contains_string(const std::vector<std::string>& values,
                     const std::string& value) {
  for (const std::string& candidate : values) {
    if (candidate == value) {
      return true;
    }
  }
  return false;
}

std::uint64_t tensor_element_bytes(const SafetensorsTensorInfo& tensor) {
  if (tensor.dtype == "bf16" || tensor.dtype == "f16") {
    return 2U;
  }
  if (tensor.dtype == "f32") {
    return 4U;
  }
  return 0U;
}

Status decode_tensor_slice_f32(const SafetensorsReader& reader,
                               const std::string& key,
                               std::uint64_t element_offset,
                               std::uint64_t element_count,
                               std::uint64_t max_bytes,
                               std::vector<float>& output) {
  output.clear();
  const SafetensorsTensorInfo* tensor = reader.find_tensor(key);
  if (tensor == nullptr) {
    return Status::invalid("safetensors_tensor_missing:" + key);
  }
  const std::uint64_t element_bytes = tensor_element_bytes(*tensor);
  if (element_bytes == 0U) {
    return Status::invalid("safetensors_tensor_dtype_unsupported:" + key);
  }
  if (element_count == 0U ||
      element_count > (std::numeric_limits<std::uint64_t>::max() / element_bytes) ||
      element_offset > (std::numeric_limits<std::uint64_t>::max() / element_bytes)) {
    return Status::invalid("safetensors_tensor_slice_element_range_invalid:" + key);
  }
  std::vector<std::uint8_t> bytes;
  const Status read_status = reader.read_tensor_slice_bytes(
      key, element_offset * element_bytes, element_count * element_bytes,
      max_bytes, bytes);
  if (!read_status.is_ok()) {
    return read_status;
  }
  SafetensorsTensorInfo slice = *tensor;
  slice.shape = {element_count};
  return decode_tensor_f32(slice, bytes, output);
}

Status decode_tensor_slice_f32_from_stream(const SafetensorsReader& reader,
                                           std::ifstream& file,
                                           const std::string& key,
                                           std::uint64_t element_offset,
                                           std::uint64_t element_count,
                                           std::uint64_t max_bytes,
                                           std::vector<float>& output) {
  output.clear();
  const SafetensorsTensorInfo* tensor = reader.find_tensor(key);
  if (tensor == nullptr) {
    return Status::invalid("safetensors_tensor_missing:" + key);
  }
  const std::uint64_t element_bytes = tensor_element_bytes(*tensor);
  if (element_bytes == 0U) {
    return Status::invalid("safetensors_tensor_dtype_unsupported:" + key);
  }
  if (element_count == 0U ||
      element_count > (std::numeric_limits<std::uint64_t>::max() / element_bytes) ||
      element_offset > (std::numeric_limits<std::uint64_t>::max() / element_bytes)) {
    return Status::invalid("safetensors_tensor_slice_element_range_invalid:" + key);
  }
  const std::uint64_t relative_offset = element_offset * element_bytes;
  const std::uint64_t byte_count = element_count * element_bytes;
  if (tensor->byte_length == 0U) {
    return Status::invalid("safetensors_tensor_empty:" + key);
  }
  if (max_bytes == 0U || byte_count > max_bytes) {
    return Status::invalid("safetensors_tensor_read_exceeds_limit:" + key);
  }
  if (relative_offset > tensor->byte_length ||
      byte_count > (tensor->byte_length - relative_offset)) {
    return Status::invalid("safetensors_tensor_slice_range_invalid:" + key);
  }
  const std::uint64_t absolute_begin =
      tensor->absolute_data_offset_begin + relative_offset;
  const std::uint64_t absolute_end = absolute_begin + byte_count;
  if (absolute_end > reader.metadata().file_size_bytes ||
      absolute_end < absolute_begin ||
      absolute_begin < tensor->absolute_data_offset_begin ||
      absolute_end > tensor->absolute_data_offset_end) {
    return Status::invalid("safetensors_tensor_range_invalid:" + key);
  }
  file.clear();
  file.seekg(static_cast<std::streamoff>(absolute_begin), std::ios::beg);
  std::vector<std::uint8_t> bytes(static_cast<std::size_t>(byte_count));
  file.read(reinterpret_cast<char*>(bytes.data()),
            static_cast<std::streamsize>(bytes.size()));
  if (file.gcount() != static_cast<std::streamsize>(bytes.size())) {
    return Status::invalid("safetensors_tensor_read_truncated:" + key);
  }
  SafetensorsTensorInfo slice = *tensor;
  slice.shape = {element_count};
  return decode_tensor_f32(slice, bytes, output);
}

Status decode_full_tensor_f32_limited(const SafetensorsReader& reader,
                                      const std::string& key,
                                      std::uint64_t expected_elements,
                                      std::uint64_t max_bytes,
                                      std::vector<float>& output) {
  output.clear();
  const SafetensorsTensorInfo* tensor = reader.find_tensor(key);
  if (tensor == nullptr) {
    return Status::invalid("safetensors_tensor_missing:" + key);
  }
  std::vector<std::uint8_t> bytes;
  const Status read_status = reader.read_tensor_bytes(key, max_bytes, bytes);
  if (!read_status.is_ok()) {
    return read_status;
  }
  const Status decode_status = decode_tensor_f32(*tensor, bytes, output);
  if (!decode_status.is_ok()) {
    return decode_status;
  }
  if (output.size() != expected_elements) {
    return Status::invalid("c5_full_decoder_tensor_element_count_mismatch:" + key);
  }
  return Status::ok();
}

std::string layer_key(std::uint32_t layer_index, const std::string& suffix) {
  return "model.language_model.layers." + std::to_string(layer_index) + "." +
         suffix;
}

Status decode_layer_vector(const SafetensorsReader& reader,
                           std::uint32_t layer_index,
                           const std::string& suffix,
                           std::uint64_t expected_elements,
                           std::vector<float>& output) {
  const std::string key = layer_key(layer_index, suffix);
  return decode_full_tensor_f32_limited(
      reader, key, expected_elements, expected_elements * sizeof(float), output);
}

std::uint64_t tensor_shape_element_count(const SafetensorsTensorInfo& tensor) {
  if (tensor.shape.empty()) {
    return 0U;
  }
  std::uint64_t count = 1U;
  for (const std::uint64_t value : tensor.shape) {
    if (value == 0U ||
        count > (std::numeric_limits<std::uint64_t>::max() / value)) {
      return 0U;
    }
    count *= value;
  }
  return count;
}

Status decode_layer_tensor_all(const SafetensorsReader& reader,
                               std::uint32_t layer_index,
                               const std::string& suffix,
                               std::vector<float>& output) {
  output.clear();
  const std::string key = layer_key(layer_index, suffix);
  const SafetensorsTensorInfo* tensor = reader.find_tensor(key);
  if (tensor == nullptr) {
    return Status::invalid("safetensors_tensor_missing:" + key);
  }
  const std::uint64_t elements = tensor_shape_element_count(*tensor);
  if (elements == 0U) {
    return Status::invalid("safetensors_tensor_shape_invalid:" + key);
  }
  return decode_full_tensor_f32_limited(reader, key, elements,
                                        elements * sizeof(float), output);
}

Status load_opencl_single_token_weights(const SafetensorsReader& reader,
                                        std::uint32_t layer_index,
                                        OpenClSingleTokenLayerWeights& weights) {
  weights = OpenClSingleTokenLayerWeights{};
  Status status = decode_layer_vector(reader, layer_index,
                                      "input_layernorm.weight", kHiddenSize,
                                      weights.input_layernorm_weight);
  if (!status.is_ok()) {
    return status;
  }
  status = decode_layer_vector(reader, layer_index, "layer_scalar", 1U,
                               weights.layer_scalar);
  if (!status.is_ok()) {
    return status;
  }
  status = decode_layer_tensor_all(reader, layer_index, "mlp.down_proj.weight",
                                   weights.mlp_down_proj_weight);
  if (!status.is_ok()) {
    return status;
  }
  status = decode_layer_tensor_all(reader, layer_index, "mlp.gate_proj.weight",
                                   weights.mlp_gate_proj_weight);
  if (!status.is_ok()) {
    return status;
  }
  status = decode_layer_tensor_all(reader, layer_index, "mlp.up_proj.weight",
                                   weights.mlp_up_proj_weight);
  if (!status.is_ok()) {
    return status;
  }
  status = decode_layer_tensor_all(reader, layer_index,
                                   "per_layer_input_gate.weight",
                                   weights.per_layer_input_gate_weight);
  if (!status.is_ok()) {
    return status;
  }
  status = decode_layer_tensor_all(reader, layer_index,
                                   "per_layer_projection.weight",
                                   weights.per_layer_projection_weight);
  if (!status.is_ok()) {
    return status;
  }
  status = decode_layer_vector(reader, layer_index,
                               "post_attention_layernorm.weight", kHiddenSize,
                               weights.post_attention_layernorm_weight);
  if (!status.is_ok()) {
    return status;
  }
  status = decode_layer_vector(reader, layer_index,
                               "post_feedforward_layernorm.weight", kHiddenSize,
                               weights.post_feedforward_layernorm_weight);
  if (!status.is_ok()) {
    return status;
  }
  status = decode_layer_vector(reader, layer_index,
                               "post_per_layer_input_norm.weight", kHiddenSize,
                               weights.post_per_layer_input_norm_weight);
  if (!status.is_ok()) {
    return status;
  }
  status = decode_layer_vector(reader, layer_index,
                               "pre_feedforward_layernorm.weight", kHiddenSize,
                               weights.pre_feedforward_layernorm_weight);
  if (!status.is_ok()) {
    return status;
  }
  status = decode_layer_tensor_all(reader, layer_index, "self_attn.k_norm.weight",
                                   weights.self_attn_k_norm_weight);
  if (!status.is_ok()) {
    return status;
  }
  status = decode_layer_tensor_all(reader, layer_index, "self_attn.k_proj.weight",
                                   weights.self_attn_k_proj_weight);
  if (!status.is_ok()) {
    return status;
  }
  status = decode_layer_tensor_all(reader, layer_index, "self_attn.o_proj.weight",
                                   weights.self_attn_o_proj_weight);
  if (!status.is_ok()) {
    return status;
  }
  status = decode_layer_tensor_all(reader, layer_index, "self_attn.q_norm.weight",
                                   weights.self_attn_q_norm_weight);
  if (!status.is_ok()) {
    return status;
  }
  status = decode_layer_tensor_all(reader, layer_index, "self_attn.q_proj.weight",
                                   weights.self_attn_q_proj_weight);
  if (!status.is_ok()) {
    return status;
  }
  return decode_layer_tensor_all(reader, layer_index, "self_attn.v_proj.weight",
                                 weights.self_attn_v_proj_weight);
}

Status linear_row_major_streamed(const SafetensorsReader& reader,
                                 std::ifstream& file,
                                 const std::string& key,
                                 const std::vector<float>& input,
                                 std::vector<float>& output) {
  output.clear();
  const SafetensorsTensorInfo* tensor = reader.find_tensor(key);
  if (tensor == nullptr) {
    return Status::invalid("safetensors_tensor_missing:" + key);
  }
  if (tensor->shape.size() != 2U || tensor->shape[0] == 0U ||
      tensor->shape[1] != input.size()) {
    return Status::invalid("c5_full_decoder_streamed_linear_shape_mismatch:" +
                           key);
  }
  const std::uint64_t output_width = tensor->shape[0];
  const std::uint64_t input_width = tensor->shape[1];
  if (output_width >
      static_cast<std::uint64_t>(std::numeric_limits<std::size_t>::max())) {
    return Status::invalid("c5_full_decoder_streamed_linear_output_too_large:" +
                           key);
  }
  output.assign(static_cast<std::size_t>(output_width), 0.0F);
  std::vector<float> row;
  for (std::uint64_t out = 0U; out < output_width; ++out) {
    Status status = decode_tensor_slice_f32_from_stream(
        reader, file, key, out * input_width, input_width,
        input_width * sizeof(float), row);
    if (!status.is_ok()) {
      return status;
    }
    double sum = 0.0;
    for (std::uint64_t col = 0U; col < input_width; ++col) {
      sum += static_cast<double>(input[static_cast<std::size_t>(col)]) *
             static_cast<double>(row[static_cast<std::size_t>(col)]);
    }
    const float value = static_cast<float>(sum);
    if (!std::isfinite(value)) {
      return Status::invalid("c5_full_decoder_streamed_linear_nonfinite:" +
                             key);
    }
    output[static_cast<std::size_t>(out)] = value;
  }
  return Status::ok();
}

Status rms_norm_weighted_repeating(const std::vector<float>& input,
                                   const std::vector<float>& weight,
                                   std::vector<float>& output) {
  output.clear();
  if (input.empty() || weight.empty() || (input.size() % weight.size()) != 0U) {
    return Status::invalid("c5_full_decoder_repeating_rms_shape_mismatch");
  }
  return rms_norm_weighted(input, weight,
                           input.size() / weight.size(), weight.size(),
                           1.0e-6F, output);
}

Status rms_norm_unweighted_repeating(const std::vector<float>& input,
                                     std::uint64_t width,
                                     std::vector<float>& output) {
  output.clear();
  if (input.empty() || width == 0U || (input.size() % width) != 0U) {
    return Status::invalid("c5_full_decoder_unweighted_rms_shape_mismatch");
  }
  output.resize(input.size());
  const std::uint64_t rows = input.size() / width;
  for (std::uint64_t row = 0U; row < rows; ++row) {
    const std::uint64_t base = row * width;
    double sum_sq = 0.0;
    for (std::uint64_t col = 0U; col < width; ++col) {
      const float value = input[static_cast<std::size_t>(base + col)];
      sum_sq += static_cast<double>(value) * static_cast<double>(value);
    }
    const float scale =
        1.0F / std::sqrt(static_cast<float>(sum_sq / width) + 1.0e-6F);
    for (std::uint64_t col = 0U; col < width; ++col) {
      output[static_cast<std::size_t>(base + col)] =
          input[static_cast<std::size_t>(base + col)] * scale;
    }
  }
  return Status::ok();
}

Status add_rows(const std::vector<float>& lhs,
                const std::vector<float>& rhs,
                std::vector<float>& output) {
  output.clear();
  if (lhs.empty() || lhs.size() != rhs.size()) {
    return Status::invalid("c5_full_decoder_add_shape_mismatch");
  }
  output.resize(lhs.size());
  for (std::size_t index = 0U; index < lhs.size(); ++index) {
    const float value = lhs[index] + rhs[index];
    if (!std::isfinite(value)) {
      return Status::invalid("c5_full_decoder_add_nonfinite");
    }
    output[index] = value;
  }
  return Status::ok();
}

Status single_token_attention_context(const std::vector<float>& query,
                                      const std::vector<float>& key,
                                      const std::vector<float>& value,
                                      std::vector<float>& context) {
  context.clear();
  if (query.empty() || key.empty() || value.empty() ||
      (query.size() % kHeadDim) != 0U || (key.size() % kHeadDim) != 0U ||
      key.size() != value.size()) {
    return Status::invalid("c5_full_decoder_single_token_attention_shape_mismatch");
  }
  const std::uint64_t query_heads = query.size() / kHeadDim;
  const std::uint64_t key_value_heads = key.size() / kHeadDim;
  if (query_heads == 0U || key_value_heads == 0U ||
      (query_heads % key_value_heads) != 0U) {
    return Status::invalid("c5_full_decoder_single_token_attention_head_mismatch");
  }
  context.resize(query.size());
  const std::uint64_t group_size = query_heads / key_value_heads;
  for (std::uint64_t query_head = 0U; query_head < query_heads; ++query_head) {
    const std::uint64_t key_head = query_head / group_size;
    double score = 0.0;
    for (std::uint64_t dim = 0U; dim < kHeadDim; ++dim) {
      score += static_cast<double>(
                   query[static_cast<std::size_t>(query_head * kHeadDim + dim)]) *
               static_cast<double>(
                   key[static_cast<std::size_t>(key_head * kHeadDim + dim)]);
      context[static_cast<std::size_t>(query_head * kHeadDim + dim)] =
          value[static_cast<std::size_t>(key_head * kHeadDim + dim)];
    }
    if (!std::isfinite(score)) {
      return Status::invalid("c5_full_decoder_single_token_attention_score_nonfinite");
    }
  }
  return Status::ok();
}

Status ensure_finite_row(const std::vector<float>& row,
                         const std::string& label) {
  if (row.empty()) {
    return Status::invalid(label + "_empty");
  }
  for (const float value : row) {
    if (!std::isfinite(value)) {
      return Status::invalid(label + "_nonfinite");
    }
  }
  return Status::ok();
}

bool contains_json_unsigned_pair(const std::string& text,
                                 const std::string& key,
                                 std::uint32_t value) {
  return contains(compact_json_text(text),
                  "\"" + key + "\":" + std::to_string(value));
}

bool contains_json_bool_pair(const std::string& text,
                             const std::string& key,
                             bool value) {
  return contains(compact_json_text(text),
                  "\"" + key + "\":" + (value ? "true" : "false"));
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
    throw std::runtime_error("json_string_expected");
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
        throw std::runtime_error("json_escape_truncated");
      }
      value.push_back(text[cursor++]);
      continue;
    }
    value.push_back(character);
  }
  throw std::runtime_error("json_string_unterminated");
}

void skip_json_value(const std::string& text, std::size_t& cursor);

void expect_char(const std::string& text, std::size_t& cursor, char expected) {
  skip_ws(text, cursor);
  if (cursor >= text.size() || text[cursor] != expected) {
    throw std::runtime_error("json_expected_token");
  }
  ++cursor;
}

void skip_json_array(const std::string& text, std::size_t& cursor) {
  expect_char(text, cursor, '[');
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

void skip_json_object(const std::string& text, std::size_t& cursor) {
  expect_char(text, cursor, '{');
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

void skip_json_value(const std::string& text, std::size_t& cursor) {
  skip_ws(text, cursor);
  if (cursor >= text.size()) {
    throw std::runtime_error("json_value_expected");
  }
  if (text[cursor] == '"') {
    (void)parse_json_string(text, cursor);
    return;
  }
  if (text[cursor] == '{') {
    skip_json_object(text, cursor);
    return;
  }
  if (text[cursor] == '[') {
    skip_json_array(text, cursor);
    return;
  }
  while (cursor < text.size()) {
    const char character = text[cursor];
    if (character == ',' || character == '}' || character == ']') {
      return;
    }
    ++cursor;
  }
}

std::string object_after_key(const std::string& text, const std::string& key) {
  std::size_t cursor = text.find("\"" + key + "\"");
  if (cursor == std::string::npos) {
    return {};
  }
  cursor = text.find(':', cursor);
  if (cursor == std::string::npos) {
    return {};
  }
  ++cursor;
  skip_ws(text, cursor);
  const std::size_t start = cursor;
  try {
    skip_json_object(text, cursor);
  } catch (const std::exception&) {
    return {};
  }
  return text.substr(start, cursor - start);
}

std::string string_field(const std::string& text, const std::string& key) {
  std::size_t cursor = text.find("\"" + key + "\"");
  if (cursor == std::string::npos) {
    return {};
  }
  cursor = text.find(':', cursor);
  if (cursor == std::string::npos) {
    return {};
  }
  ++cursor;
  try {
    return parse_json_string(text, cursor);
  } catch (const std::exception&) {
    return {};
  }
}

std::uint64_t unsigned_field(const std::string& text, const std::string& key) {
  std::size_t cursor = text.find("\"" + key + "\"");
  if (cursor == std::string::npos) {
    return 0U;
  }
  cursor = text.find(':', cursor);
  if (cursor == std::string::npos) {
    return 0U;
  }
  ++cursor;
  skip_ws(text, cursor);
  std::uint64_t value = 0U;
  bool found_digit = false;
  while (cursor < text.size() && text[cursor] >= '0' && text[cursor] <= '9') {
    found_digit = true;
    value = (value * 10U) + static_cast<std::uint64_t>(text[cursor] - '0');
    ++cursor;
  }
  return found_digit ? value : 0U;
}

SourceModelIdentity parse_source_model_identity(const std::string& manifest,
                                                std::vector<std::string>& blockers) {
  SourceModelIdentity identity;
  const std::string section = object_after_key(manifest, "source_model_safetensors");
  if (section.empty()) {
    blockers.push_back("decoder_manifest_source_model_safetensors_missing");
    return identity;
  }
  identity.path = string_field(section, "path");
  identity.sha256 = string_field(section, "sha256");
  identity.size_bytes = unsigned_field(section, "size_bytes");
  if (identity.path.empty()) {
    blockers.push_back("decoder_manifest_source_model_safetensors_path_missing");
  }
  if (identity.sha256.size() != 64U) {
    blockers.push_back("decoder_manifest_source_model_safetensors_sha256_invalid");
  }
  if (identity.size_bytes == 0U) {
    blockers.push_back("decoder_manifest_source_model_safetensors_size_invalid");
  }
  return identity;
}

void append_architecture_blockers(const std::string& manifest,
                                  std::vector<std::string>& blockers) {
  if (object_after_key(manifest, "architecture_config").empty()) {
    blockers.push_back("decoder_manifest_architecture_config_missing");
    return;
  }
  const std::pair<const char*, std::uint32_t> required[] = {
      {"num_hidden_layers", kLayerCount},
      {"hidden_size", kHiddenSize},
      {"vocab_size", kVocabSize},
      {"logits_vocabulary_size", kVocabSize},
      {"intermediate_size", kIntermediateSize},
      {"num_attention_heads", kAttentionHeads},
      {"num_key_value_heads", kKeyValueHeads},
      {"head_dim", kHeadDim},
  };
  for (const auto& item : required) {
    if (!contains_json_unsigned_pair(manifest, item.first, item.second)) {
      blockers.push_back(std::string("decoder_manifest_architecture_") +
                         item.first + "_mismatch");
    }
  }
  if (contains_json_bool_pair(manifest, "materializes_full_bsv_logits", true)) {
    blockers.push_back("decoder_manifest_full_bsv_logits_materialization_forbidden");
  }
}

void append_tokenizer_identity_blockers(const std::string& manifest,
                                        const C5QaInferenceRequest& request,
                                        std::vector<std::string>& blockers) {
  const std::string section = object_after_key(manifest, "tokenizer_identity");
  if (section.empty()) {
    blockers.push_back("decoder_manifest_tokenizer_identity_missing");
    return;
  }
  const std::string expected_vocab = string_field(section, "vocab_hex_tsv_sha256");
  const std::string expected_merges =
      string_field(section, "merges_hex_tsv_sha256");
  if (expected_vocab.empty() || expected_merges.empty()) {
    blockers.push_back("decoder_manifest_tokenizer_identity_sha_missing");
    return;
  }
  try {
    const std::string vocab_path = join_path(request.tokenizer_dir, "vocab.hex.tsv");
    const std::string merges_path = join_path(request.tokenizer_dir, "merges.hex.tsv");
    if (file_exists(vocab_path) && sha256_file_hex(vocab_path) != expected_vocab) {
      blockers.push_back("tokenizer_vocab_hex_sha256_mismatch");
    }
    if (file_exists(merges_path) && sha256_file_hex(merges_path) != expected_merges) {
      blockers.push_back("tokenizer_merges_hex_sha256_mismatch");
    }
  } catch (const std::exception& error) {
    blockers.push_back(std::string("tokenizer_identity_hash_error:") + error.what());
  }
}

void append_adapter_runtime_blockers(const C5QaInferenceRequest& request,
                                     std::vector<std::string>& blockers) {
  try {
    const std::string policy = read_text_file(request.adapter_site_policy_path);
    const std::string site = string_field(policy, "adapter_site");
    const std::uint64_t layer = unsigned_field(policy, "decoder_layer_index");
    if (site != "post_layer0_residual" && site != "post_layer1_residual") {
      blockers.push_back("adapter_site_policy_site_unsupported");
      return;
    }
    const std::uint64_t expected_layer = site == "post_layer1_residual" ? 1U : 0U;
    if (layer != expected_layer) {
      blockers.push_back("adapter_site_policy_decoder_layer_index_site_mismatch");
    }
  } catch (const std::exception& error) {
    blockers.push_back(std::string("adapter_site_policy_runtime_read_error:") +
                       error.what());
  }
}

void append_source_model_blockers(const SourceModelIdentity& identity,
                                  C5FullDecoderRuntimeResult& result,
                                  std::vector<std::string>& blockers) {
  if (identity.path.empty()) {
    return;
  }
  if (!file_exists(identity.path)) {
    blockers.push_back("source_model_safetensors_path_not_found");
    return;
  }
  try {
    const std::uint64_t actual_size = file_size_bytes(identity.path);
    result.source_model_size_bytes = actual_size;
    if (identity.size_bytes != 0U && actual_size != identity.size_bytes) {
      blockers.push_back("source_model_safetensors_size_mismatch");
      return;
    }
    if (identity.sha256.size() == 64U) {
      result.source_model_sha256 = sha256_file_hex(identity.path);
      if (result.source_model_sha256 != identity.sha256) {
        blockers.push_back("source_model_safetensors_sha256_mismatch");
      }
    }
  } catch (const std::exception& error) {
    blockers.push_back(std::string("source_model_safetensors_identity_error:") +
                       error.what());
  }
}

Status validate_role_tensor(const SafetensorsReader& reader,
                            const std::string& key,
                            const RoleSpec& role,
                            const std::vector<std::string>& allowed_dtypes) {
  const SafetensorsTensorInfo* tensor = reader.find_tensor(key);
  if (tensor == nullptr) {
    return Status::invalid("safetensors_tensor_missing:" + key);
  }
  if (!contains_string(allowed_dtypes, tensor->dtype)) {
    return Status::invalid("safetensors_tensor_dtype_unsupported:" + key);
  }
  const std::vector<std::uint64_t>& shape = tensor->shape;
  const std::string role_name = role.role;
  if (role_name == "self_attn_q_proj" || role_name == "self_attn_k_proj" ||
      role_name == "self_attn_v_proj") {
    if (shape.size() != 2U || shape[1] != kHiddenSize || shape[0] == 0U ||
        (shape[0] % kHeadDim) != 0U) {
      return Status::invalid("safetensors_tensor_shape_mismatch:" + key);
    }
    return Status::ok();
  }
  if (role_name == "self_attn_o_proj") {
    if (shape.size() != 2U || shape[0] != kHiddenSize || shape[1] == 0U ||
        (shape[1] % kHeadDim) != 0U) {
      return Status::invalid("safetensors_tensor_shape_mismatch:" + key);
    }
    return Status::ok();
  }
  if (role_name == "self_attn_q_norm" || role_name == "self_attn_k_norm") {
    if (shape.size() != 1U || shape[0] == 0U || (shape[0] % kHeadDim) != 0U) {
      return Status::invalid("safetensors_tensor_shape_mismatch:" + key);
    }
    return Status::ok();
  }
  if (shape != role.shape) {
    return Status::invalid("safetensors_tensor_shape_mismatch:" + key);
  }
  return Status::ok();
}

bool norm_width_compatible_with_projection(std::uint64_t norm_width,
                                           std::uint64_t q_proj_rows,
                                           std::uint64_t projected_rows) {
  if (norm_width == 0U || q_proj_rows == 0U || projected_rows == 0U) {
    return false;
  }
  if ((norm_width % kHeadDim) != 0U || norm_width > q_proj_rows ||
      (q_proj_rows % norm_width) != 0U) {
    return false;
  }
  return (projected_rows % norm_width) == 0U ||
         (norm_width % projected_rows) == 0U;
}

void append_attention_layout_blockers(const SafetensorsReader& reader,
                                      std::uint32_t layer,
                                      std::vector<std::string>& blockers) {
  const std::string prefix =
      "model.language_model.layers." + std::to_string(layer) + ".";
  const SafetensorsTensorInfo* q =
      reader.find_tensor(prefix + "self_attn.q_proj.weight");
  const SafetensorsTensorInfo* k =
      reader.find_tensor(prefix + "self_attn.k_proj.weight");
  const SafetensorsTensorInfo* v =
      reader.find_tensor(prefix + "self_attn.v_proj.weight");
  const SafetensorsTensorInfo* o =
      reader.find_tensor(prefix + "self_attn.o_proj.weight");
  const SafetensorsTensorInfo* q_norm =
      reader.find_tensor(prefix + "self_attn.q_norm.weight");
  const SafetensorsTensorInfo* k_norm =
      reader.find_tensor(prefix + "self_attn.k_norm.weight");
  if (q == nullptr || k == nullptr || v == nullptr || o == nullptr ||
      q_norm == nullptr || k_norm == nullptr ||
      q->shape.size() != 2U || k->shape.size() != 2U ||
      v->shape.size() != 2U || o->shape.size() != 2U ||
      q_norm->shape.size() != 1U || k_norm->shape.size() != 1U) {
    return;
  }
  const std::uint64_t query_heads = q->shape[0] / kHeadDim;
  const std::uint64_t key_heads = k->shape[0] / kHeadDim;
  const std::uint64_t value_heads = v->shape[0] / kHeadDim;
  const std::uint64_t output_heads = o->shape[1] / kHeadDim;
  if (key_heads != value_heads) {
    blockers.push_back("safetensors_attention_kv_head_shape_mismatch:" +
                       std::to_string(layer));
  }
  if (query_heads != output_heads) {
    blockers.push_back("safetensors_attention_q_o_head_shape_mismatch:" +
                       std::to_string(layer));
  }
  if (key_heads == 0U || query_heads == 0U ||
      (query_heads % key_heads) != 0U) {
    blockers.push_back("safetensors_attention_head_grouping_invalid:" +
                       std::to_string(layer));
  }
  if (!norm_width_compatible_with_projection(q_norm->shape[0], q->shape[0],
                                             q->shape[0])) {
    blockers.push_back("safetensors_attention_q_norm_shape_mismatch:" +
                       std::to_string(layer));
  }
  if (!norm_width_compatible_with_projection(k_norm->shape[0], q->shape[0],
                                             k->shape[0])) {
    blockers.push_back("safetensors_attention_k_norm_shape_mismatch:" +
                       std::to_string(layer));
  }
}

void append_tensor_role_blockers(const std::string& manifest,
                                 const SourceModelIdentity& identity,
                                 C5FullDecoderRuntimeResult& result,
                                 std::vector<std::string>& blockers) {
  if (object_after_key(manifest, "tensor_role_inventory").empty()) {
    blockers.push_back("decoder_manifest_tensor_role_inventory_missing");
    return;
  }
  if (identity.path.empty() || !file_exists(identity.path)) {
    return;
  }

  SafetensorsReader reader;
  const Status open_status = reader.open(identity.path);
  if (!open_status.is_ok()) {
    blockers.push_back(open_status.message());
    return;
  }
  const std::vector<std::string> allowed_dtypes = {"bf16", "f16", "f32"};
  const Status embed_status = reader.validate_tensor(
      kEmbedTokensKey, {kVocabSize, kHiddenSize}, allowed_dtypes);
  if (!embed_status.is_ok()) {
    blockers.push_back(embed_status.message());
  }
  if (!contains(manifest, kEmbedTokensKey)) {
    blockers.push_back("decoder_manifest_token_embedding_key_missing");
  }

  for (std::uint32_t layer = 0U; layer < kLayerCount; ++layer) {
    const std::string prefix =
        "model.language_model.layers." + std::to_string(layer) + ".";
    for (const RoleSpec& role : role_specs()) {
      const std::string key = prefix + role.suffix;
      if (!contains(manifest, key)) {
        blockers.push_back(std::string("decoder_manifest_tensor_role_key_missing:") +
                           std::to_string(layer) + ":" + role.role);
        continue;
      }
      const Status status = validate_role_tensor(reader, key, role, allowed_dtypes);
      if (!status.is_ok()) {
        blockers.push_back(status.message());
      }
      ++result.validated_tensor_count;
    }
    append_attention_layout_blockers(reader, layer, blockers);
  }
}

void append_per_layer_input_runtime_blockers(
    const std::string& manifest,
    const SourceModelIdentity& identity,
    std::vector<std::string>& blockers) {
  const std::string section = object_after_key(manifest, "per_layer_input_runtime");
  if (section.empty() || object_after_key(section, "roles").empty()) {
    blockers.push_back("decoder_manifest_per_layer_input_runtime_missing");
    return;
  }
  if (!contains(section, kPleTokenKey)) {
    blockers.push_back("decoder_manifest_per_layer_token_embedding_key_missing");
  }
  if (!contains(section, kPleProjectionNormKey)) {
    blockers.push_back("decoder_manifest_per_layer_projection_norm_key_missing");
  }
  if (!contains(section, kPleProjectionKey)) {
    blockers.push_back("decoder_manifest_per_layer_projection_key_missing");
  }
  if (identity.path.empty() || !file_exists(identity.path)) {
    return;
  }

  SafetensorsReader reader;
  const Status open_status = reader.open(identity.path);
  if (!open_status.is_ok()) {
    blockers.push_back(open_status.message());
    return;
  }
  const std::vector<std::string> allowed_dtypes = {"bf16", "f16", "f32"};
  const Status token_status = reader.validate_tensor(
      kPleTokenKey, {kVocabSize, kLayerCount * kSmallInputSize},
      allowed_dtypes);
  if (!token_status.is_ok()) {
    blockers.push_back(token_status.message());
  }
  const Status norm_status = reader.validate_tensor(
      kPleProjectionNormKey, {kSmallInputSize}, allowed_dtypes);
  if (!norm_status.is_ok()) {
    blockers.push_back(norm_status.message());
  }
  const Status projection_status = reader.validate_tensor(
      kPleProjectionKey, {kLayerCount * kSmallInputSize, kHiddenSize},
      allowed_dtypes);
  if (!projection_status.is_ok()) {
    blockers.push_back(projection_status.message());
  }
}

void append_tensor_value_loader_blockers(
    const SourceModelIdentity& identity,
    std::vector<std::string>& blockers) {
  if (identity.path.empty() || !file_exists(identity.path)) {
    return;
  }
  SafetensorsReader reader;
  const Status open_status = reader.open(identity.path);
  if (!open_status.is_ok()) {
    blockers.push_back(open_status.message());
    return;
  }
  std::vector<std::uint8_t> layer_scalar;
  const Status read_status = reader.read_tensor_bytes(
      "model.language_model.layers.0.layer_scalar", 4096U, layer_scalar);
  if (!read_status.is_ok()) {
    blockers.push_back(read_status.message());
    return;
  }
  const SafetensorsTensorInfo* scalar_info =
      reader.find_tensor("model.language_model.layers.0.layer_scalar");
  if (scalar_info == nullptr) {
    blockers.push_back("safetensors_tensor_missing:model.language_model.layers.0.layer_scalar");
    return;
  }
  std::vector<float> scalar;
  const Status decode_status =
      decode_tensor_f32(*scalar_info, layer_scalar, scalar);
  if (!decode_status.is_ok()) {
    blockers.push_back(decode_status.message());
    return;
  }
  if (scalar.size() != 1U || !std::isfinite(scalar[0])) {
    blockers.push_back("c5_full_decoder_tensor_value_loader_nonfinite");
  }
}

void append_adapter_payload_blockers(const C5QaInferenceRequest& request,
                                     std::vector<std::string>& blockers) {
  try {
    const std::vector<std::uint8_t> bytes =
        read_binary_file_limited(request.checkpoint_payload_path,
                                 kAdapterPayloadBytes);
    if (bytes.size() != kAdapterPayloadBytes) {
      blockers.push_back("c5_full_decoder_rank16_adapter_payload_size_mismatch");
      return;
    }
    std::vector<float> adapter;
    const Status decode_status = decode_f32_le_bytes(bytes, adapter);
    if (!decode_status.is_ok()) {
      blockers.push_back(decode_status.message());
      return;
    }
    if (adapter.size() !=
        static_cast<std::size_t>(kHiddenSize * kAdapterRank * 2U)) {
      blockers.push_back("c5_full_decoder_rank16_adapter_element_count_mismatch");
      return;
    }
    for (const float value : adapter) {
      if (!std::isfinite(value)) {
        blockers.push_back("c5_full_decoder_rank16_adapter_nonfinite");
        return;
      }
    }
  } catch (const std::exception& error) {
    blockers.push_back(std::string("c5_full_decoder_rank16_adapter_read_error:") +
                       error.what());
  }
}

Status derive_layer_input_row(const SafetensorsReader& reader,
                              std::uint32_t token_id,
                              std::vector<float>& layer_input_row) {
  if (token_id >= kVocabSize) {
    return Status::invalid("c5_full_decoder_token_id_out_of_vocab");
  }
  const std::uint64_t row_offset =
      static_cast<std::uint64_t>(token_id) * kHiddenSize;
  const Status read_status = decode_tensor_slice_f32(
      reader, kEmbedTokensKey, row_offset, kHiddenSize,
      static_cast<std::uint64_t>(kHiddenSize) * sizeof(float),
      layer_input_row);
  if (!read_status.is_ok()) {
    return read_status;
  }
  const float embedding_scale =
      bf16_round(std::sqrt(static_cast<float>(kHiddenSize)));
  for (float& value : layer_input_row) {
    value *= embedding_scale;
    if (!std::isfinite(value)) {
      return Status::invalid("c5_full_decoder_layer_input_nonfinite");
    }
  }
  return Status::ok();
}

Status derive_ple_input_row(const SafetensorsReader& reader,
                            const std::vector<float>& layer_input_row,
                            std::uint32_t token_id,
                            std::uint32_t layer_index,
                            std::vector<float>& ple_input_row) {
  ple_input_row.clear();
  if (layer_input_row.size() != kHiddenSize) {
    return Status::invalid("c5_full_decoder_ple_layer_input_shape_mismatch");
  }
  if (token_id >= kVocabSize || layer_index >= kLayerCount) {
    return Status::invalid("c5_full_decoder_ple_index_out_of_range");
  }

  const std::uint64_t ple_row_width =
      static_cast<std::uint64_t>(kLayerCount) * kSmallInputSize;
  const std::uint64_t layer_offset =
      static_cast<std::uint64_t>(layer_index) * kSmallInputSize;
  const std::uint64_t identity_offset =
      (static_cast<std::uint64_t>(token_id) * ple_row_width) + layer_offset;
  std::vector<float> identity;
  Status status = decode_tensor_slice_f32(
      reader, kPleTokenKey, identity_offset, kSmallInputSize,
      static_cast<std::uint64_t>(kSmallInputSize) * sizeof(float),
      identity);
  if (!status.is_ok()) {
    return status;
  }
  for (float& value : identity) {
    value *= 16.0F;
  }

  const std::uint64_t projection_offset =
      layer_offset * static_cast<std::uint64_t>(kHiddenSize);
  std::vector<float> projection;
  status = decode_tensor_slice_f32(
      reader, kPleProjectionKey, projection_offset,
      static_cast<std::uint64_t>(kSmallInputSize) * kHiddenSize,
      static_cast<std::uint64_t>(kSmallInputSize) * kHiddenSize * sizeof(float),
      projection);
  if (!status.is_ok()) {
    return status;
  }

  std::vector<float> norm_weight;
  status = decode_full_tensor_f32_limited(
      reader, kPleProjectionNormKey, kSmallInputSize,
      static_cast<std::uint64_t>(kSmallInputSize) * sizeof(float),
      norm_weight);
  if (!status.is_ok()) {
    return status;
  }

  std::vector<float> projected;
  status = linear_row_major(layer_input_row, projection, 1U, kHiddenSize,
                            kSmallInputSize, projected);
  if (!status.is_ok()) {
    return status;
  }
  const float projection_scale =
      1.0F / std::sqrt(static_cast<float>(kHiddenSize));
  for (float& value : projected) {
    value *= projection_scale;
  }

  std::vector<float> normalized_projection;
  status = rms_norm_weighted(projected, norm_weight, 1U, kSmallInputSize,
                             1.0e-6F, normalized_projection);
  if (!status.is_ok()) {
    return status;
  }

  const float combine_scale = 1.0F / std::sqrt(2.0F);
  ple_input_row.resize(kSmallInputSize);
  for (std::uint32_t index = 0U; index < kSmallInputSize; ++index) {
    const float value =
        (normalized_projection[index] + identity[index]) * combine_scale;
    if (!std::isfinite(value)) {
      return Status::invalid("c5_full_decoder_ple_row_nonfinite");
    }
    ple_input_row[index] = value;
  }
  return Status::ok();
}

Status prepare_single_layer_input_norm_slice(const SafetensorsReader& reader,
                                             const std::vector<float>& layer_input_row,
                                             std::uint32_t layer_index,
                                             std::vector<float>& normalized_row) {
  normalized_row.clear();
  if (layer_input_row.size() != kHiddenSize || layer_index >= kLayerCount) {
    return Status::invalid("c5_full_decoder_single_layer_input_shape_mismatch");
  }
  const std::string key = "model.language_model.layers." +
                          std::to_string(layer_index) +
                          ".input_layernorm.weight";
  std::vector<float> norm_weight;
  Status status = decode_full_tensor_f32_limited(
      reader, key, kHiddenSize,
      static_cast<std::uint64_t>(kHiddenSize) * sizeof(float),
      norm_weight);
  if (!status.is_ok()) {
    return status;
  }
  status = rms_norm_weighted(layer_input_row, norm_weight, 1U, kHiddenSize,
                             1.0e-6F, normalized_row);
  if (!status.is_ok()) {
    return status;
  }
  for (const float value : normalized_row) {
    if (!std::isfinite(value)) {
      return Status::invalid("c5_full_decoder_single_layer_norm_nonfinite");
    }
  }
  return Status::ok();
}

void append_ple_single_layer_slice_blockers(
    const SourceModelIdentity& identity,
    const QaTokenization& tokenization,
    std::vector<std::string>& blockers) {
  if (identity.path.empty() || !file_exists(identity.path)) {
    return;
  }
  if (tokenization.question_tokens.empty()) {
    blockers.push_back("c5_full_decoder_ple_prompt_tokens_missing");
    return;
  }
  SafetensorsReader reader;
  const Status open_status = reader.open(identity.path);
  if (!open_status.is_ok()) {
    blockers.push_back(open_status.message());
    return;
  }

  const std::uint32_t token_id = tokenization.question_tokens.front();
  std::vector<float> layer_input_row;
  Status status = derive_layer_input_row(reader, token_id, layer_input_row);
  if (!status.is_ok()) {
    blockers.push_back(status.message());
    return;
  }
  std::vector<float> ple_input_row;
  status = derive_ple_input_row(reader, layer_input_row, token_id, 0U,
                                ple_input_row);
  if (!status.is_ok()) {
    blockers.push_back(status.message());
    return;
  }
  if (ple_input_row.size() != kSmallInputSize) {
    blockers.push_back("c5_full_decoder_ple_row_shape_mismatch");
    return;
  }

  std::vector<float> normalized_row;
  status = prepare_single_layer_input_norm_slice(reader, layer_input_row, 0U,
                                                 normalized_row);
  if (!status.is_ok()) {
    blockers.push_back(status.message());
  }
}

Status run_cpu_single_layer_body_slice(const SafetensorsReader& reader,
                                       std::ifstream& file,
                                       std::uint32_t layer_index,
                                       const std::vector<float>& layer_input_row,
                                       const std::vector<float>& ple_input_row,
                                       SingleLayerBody& body) {
  body = SingleLayerBody{};
  if (layer_input_row.size() != kHiddenSize ||
      ple_input_row.size() != kSmallInputSize ||
      layer_index >= kLayerCount) {
    return Status::invalid("c5_full_decoder_cpu_single_layer_input_shape_mismatch");
  }

  std::vector<float> attn_input;
  Status status = prepare_single_layer_input_norm_slice(
      reader, layer_input_row, layer_index, attn_input);
  if (!status.is_ok()) {
    return status;
  }

  std::vector<float> query;
  std::vector<float> key;
  std::vector<float> value;
  status = linear_row_major_streamed(
      reader, file, layer_key(layer_index, "self_attn.q_proj.weight"),
      attn_input, query);
  if (!status.is_ok()) {
    return status;
  }
  status = linear_row_major_streamed(
      reader, file, layer_key(layer_index, "self_attn.k_proj.weight"),
      attn_input, key);
  if (!status.is_ok()) {
    return status;
  }
  status = linear_row_major_streamed(
      reader, file, layer_key(layer_index, "self_attn.v_proj.weight"),
      attn_input, value);
  if (!status.is_ok()) {
    return status;
  }

  std::vector<float> q_norm_weight;
  std::vector<float> k_norm_weight;
  status = decode_layer_vector(reader, layer_index, "self_attn.q_norm.weight",
                               reader.find_tensor(layer_key(layer_index, "self_attn.q_norm.weight"))
                                   ->shape[0],
                               q_norm_weight);
  if (!status.is_ok()) {
    return status;
  }
  status = decode_layer_vector(reader, layer_index, "self_attn.k_norm.weight",
                               reader.find_tensor(layer_key(layer_index, "self_attn.k_norm.weight"))
                                   ->shape[0],
                               k_norm_weight);
  if (!status.is_ok()) {
    return status;
  }

  std::vector<float> query_norm;
  std::vector<float> key_norm;
  std::vector<float> value_norm;
  status = rms_norm_weighted_repeating(query, q_norm_weight, query_norm);
  if (!status.is_ok()) {
    return status;
  }
  status = rms_norm_weighted_repeating(key, k_norm_weight, key_norm);
  if (!status.is_ok()) {
    return status;
  }
  status = rms_norm_unweighted_repeating(value, kHeadDim, value_norm);
  if (!status.is_ok()) {
    return status;
  }

  std::vector<float> context;
  status = single_token_attention_context(query_norm, key_norm, value_norm,
                                          context);
  if (!status.is_ok()) {
    return status;
  }

  std::vector<float> attn_projection;
  status = linear_row_major_streamed(
      reader, file, layer_key(layer_index, "self_attn.o_proj.weight"),
      context, attn_projection);
  if (!status.is_ok()) {
    return status;
  }
  std::vector<float> post_attention_weight;
  status = decode_layer_vector(reader, layer_index,
                               "post_attention_layernorm.weight", kHiddenSize,
                               post_attention_weight);
  if (!status.is_ok()) {
    return status;
  }
  std::vector<float> attn_norm;
  status = rms_norm_weighted(attn_projection, post_attention_weight, 1U,
                             kHiddenSize, 1.0e-6F, attn_norm);
  if (!status.is_ok()) {
    return status;
  }
  std::vector<float> hidden_state;
  status = add_rows(layer_input_row, attn_norm, hidden_state);
  if (!status.is_ok()) {
    return status;
  }

  std::vector<float> pre_ff_weight;
  status = decode_layer_vector(reader, layer_index,
                               "pre_feedforward_layernorm.weight", kHiddenSize,
                               pre_ff_weight);
  if (!status.is_ok()) {
    return status;
  }
  std::vector<float> ff_input;
  status = rms_norm_weighted(hidden_state, pre_ff_weight, 1U, kHiddenSize,
                             1.0e-6F, ff_input);
  if (!status.is_ok()) {
    return status;
  }

  std::vector<float> gate;
  std::vector<float> up;
  status = linear_row_major_streamed(
      reader, file, layer_key(layer_index, "mlp.gate_proj.weight"), ff_input,
      gate);
  if (!status.is_ok()) {
    return status;
  }
  status = linear_row_major_streamed(
      reader, file, layer_key(layer_index, "mlp.up_proj.weight"), ff_input, up);
  if (!status.is_ok()) {
    return status;
  }
  std::vector<float> activation;
  status = gelu_tanh_mul(gate, up, activation);
  if (!status.is_ok()) {
    return status;
  }
  std::vector<float> down;
  status = linear_row_major_streamed(
      reader, file, layer_key(layer_index, "mlp.down_proj.weight"), activation,
      down);
  if (!status.is_ok()) {
    return status;
  }
  std::vector<float> post_ff_weight;
  status = decode_layer_vector(reader, layer_index,
                               "post_feedforward_layernorm.weight", kHiddenSize,
                               post_ff_weight);
  if (!status.is_ok()) {
    return status;
  }
  std::vector<float> down_norm;
  status = rms_norm_weighted(down, post_ff_weight, 1U, kHiddenSize, 1.0e-6F,
                             down_norm);
  if (!status.is_ok()) {
    return status;
  }
  std::vector<float> hidden2;
  status = add_rows(hidden_state, down_norm, hidden2);
  if (!status.is_ok()) {
    return status;
  }

  std::vector<float> per_gate;
  status = linear_row_major_streamed(
      reader, file, layer_key(layer_index, "per_layer_input_gate.weight"),
      hidden2, per_gate);
  if (!status.is_ok()) {
    return status;
  }
  std::vector<float> per_activation;
  status = gelu_tanh_mul(per_gate, ple_input_row, per_activation);
  if (!status.is_ok()) {
    return status;
  }
  std::vector<float> per_projection;
  status = linear_row_major_streamed(
      reader, file, layer_key(layer_index, "per_layer_projection.weight"),
      per_activation, per_projection);
  if (!status.is_ok()) {
    return status;
  }
  std::vector<float> post_per_weight;
  status = decode_layer_vector(reader, layer_index,
                               "post_per_layer_input_norm.weight", kHiddenSize,
                               post_per_weight);
  if (!status.is_ok()) {
    return status;
  }
  std::vector<float> per_norm;
  status = rms_norm_weighted(per_projection, post_per_weight, 1U, kHiddenSize,
                             1.0e-6F, per_norm);
  if (!status.is_ok()) {
    return status;
  }
  std::vector<float> output;
  status = add_rows(hidden2, per_norm, output);
  if (!status.is_ok()) {
    return status;
  }

  std::vector<float> layer_scalar;
  status = decode_layer_vector(reader, layer_index, "layer_scalar", 1U,
                               layer_scalar);
  if (!status.is_ok()) {
    return status;
  }
  for (float& value : output) {
    value *= layer_scalar[0];
  }
  status = ensure_finite_row(output, "c5_full_decoder_cpu_single_layer_output");
  if (!status.is_ok()) {
    return status;
  }
  body.output_row = std::move(output);
  return Status::ok();
}

void append_cpu_single_layer_body_blockers(
    const SourceModelIdentity& identity,
    const QaTokenization& tokenization,
    SingleLayerBody& body,
    std::vector<std::string>& blockers) {
  body = SingleLayerBody{};
  if (identity.path.empty() || !file_exists(identity.path)) {
    return;
  }
  if (tokenization.question_tokens.empty()) {
    blockers.push_back("c5_full_decoder_single_layer_prompt_tokens_missing");
    return;
  }

  SafetensorsReader reader;
  Status status = reader.open(identity.path);
  if (!status.is_ok()) {
    blockers.push_back(status.message());
    return;
  }
  std::ifstream file(identity.path, std::ios::binary);
  if (!file) {
    blockers.push_back("safetensors_file_open_failed");
    return;
  }

  const std::uint32_t token_id = tokenization.question_tokens.front();
  std::vector<float> layer_input_row;
  status = derive_layer_input_row(reader, token_id, layer_input_row);
  if (!status.is_ok()) {
    blockers.push_back(status.message());
    return;
  }
  std::vector<float> ple_input_row;
  status = derive_ple_input_row(reader, layer_input_row, token_id, 0U,
                                ple_input_row);
  if (!status.is_ok()) {
    blockers.push_back(status.message());
    return;
  }

  status = run_cpu_single_layer_body_slice(reader, file, 0U, layer_input_row,
                                           ple_input_row, body);
  if (!status.is_ok()) {
    blockers.push_back(status.message());
    return;
  }
  body.layer_input_row = std::move(layer_input_row);
  body.ple_input_row = std::move(ple_input_row);
  if (body.output_row.size() != kHiddenSize) {
    blockers.push_back("c5_full_decoder_cpu_single_layer_output_shape_mismatch");
  }
}

void append_opencl_single_layer_parity_blockers(
    const C5QaInferenceRequest& request,
    const SourceModelIdentity& identity,
    const SingleLayerBody& cpu_body,
    std::vector<std::string>& blockers) {
  if (identity.path.empty() || !file_exists(identity.path)) {
    return;
  }
  if (cpu_body.layer_input_row.size() != kHiddenSize ||
      cpu_body.ple_input_row.size() != kSmallInputSize ||
      cpu_body.output_row.size() != kHiddenSize) {
    blockers.push_back("c5_full_decoder_opencl_parity_cpu_slice_missing");
    return;
  }

  OpenClRuntimeDiscoveryConfig opencl_config;
  opencl_config.opencl_library = request.opencl_library;
  const Status runtime_status = probe_opencl_layer_runtime_available(opencl_config);
  if (!runtime_status.is_ok()) {
    blockers.push_back("c5_full_decoder_opencl_parity_runtime_unavailable:" +
                       runtime_status.message());
    return;
  }

  SafetensorsReader reader;
  Status status = reader.open(identity.path);
  if (!status.is_ok()) {
    blockers.push_back(status.message());
    return;
  }
  OpenClSingleTokenLayerWeights weights;
  status = load_opencl_single_token_weights(reader, 0U, weights);
  if (!status.is_ok()) {
    blockers.push_back(status.message());
    return;
  }

  OpenClSingleTokenLayerInput input;
  input.layer_index = 0U;
  input.layer_input_row = cpu_body.layer_input_row;
  input.per_layer_input_row = cpu_body.ple_input_row;
  input.position_id = 0U;
  OpenClSingleTokenLayerResult result;
  status = run_opencl_single_token_layer_forward(weights, input, result,
                                                 opencl_config);
  if (!status.is_ok()) {
    blockers.push_back("c5_full_decoder_opencl_parity_dispatch_failed:" +
                       status.message());
    return;
  }
  if (result.output_row.size() != cpu_body.output_row.size()) {
    blockers.push_back("c5_full_decoder_opencl_parity_output_shape_mismatch");
    return;
  }

  double max_abs = 0.0;
  double max_rel = 0.0;
  for (std::size_t index = 0U; index < cpu_body.output_row.size(); ++index) {
    const double cpu = static_cast<double>(cpu_body.output_row[index]);
    const double gpu = static_cast<double>(result.output_row[index]);
    if (!std::isfinite(cpu) || !std::isfinite(gpu)) {
      blockers.push_back("c5_full_decoder_opencl_parity_output_nonfinite");
      return;
    }
    const double abs_diff = std::fabs(cpu - gpu);
    const double denom = std::max(1.0, std::fabs(cpu));
    max_abs = std::max(max_abs, abs_diff);
    max_rel = std::max(max_rel, abs_diff / denom);
  }
  if (max_abs > 5.0e-2 && max_rel > 5.0e-2) {
    blockers.push_back("c5_full_decoder_opencl_parity_output_mismatch");
  }
}

std::string first_nonempty_jsonl_line(const std::string& path) {
  std::ifstream file(path);
  if (!file) {
    throw std::runtime_error("heldout_qa_jsonl_read_failed");
  }
  std::string line;
  while (std::getline(file, line)) {
    bool has_content = false;
    for (const char character : line) {
      if (std::isspace(static_cast<unsigned char>(character)) == 0) {
        has_content = true;
        break;
      }
    }
    if (has_content) {
      return line;
    }
  }
  return {};
}

void append_qa_prompt_token_runtime_blockers(
    const C5QaInferenceRequest& request,
    QaTokenization& tokenization,
    std::vector<std::string>& blockers) {
  try {
    GemmaBpeTokenizer tokenizer;
    tokenizer.load(request.tokenizer_dir);
    const std::string record = first_nonempty_jsonl_line(request.heldout_qa_jsonl_path);
    if (record.empty()) {
      blockers.push_back("c5_qa_prompt_token_runtime_heldout_empty");
      return;
    }
    const std::string question = string_field(record, "question");
    const std::string answer = string_field(record, "answer");
    if (question.empty()) {
      blockers.push_back("c5_qa_prompt_token_runtime_question_missing");
    }
    if (answer.empty()) {
      blockers.push_back("c5_qa_prompt_token_runtime_answer_missing");
    }
    if (!question.empty() && tokenizer.encode(question).empty()) {
      blockers.push_back("c5_qa_prompt_token_runtime_question_tokens_empty");
    }
    if (!question.empty()) {
      tokenization.question_tokens = tokenizer.encode(question);
    }
    if (!answer.empty()) {
      tokenization.answer_tokens = tokenizer.encode(answer);
    }
    if (!answer.empty() && tokenization.answer_tokens.size() <= 1U) {
      blockers.push_back("c5_qa_prompt_token_runtime_answer_tokens_empty");
    }
  } catch (const std::exception& error) {
    blockers.push_back(std::string("c5_qa_prompt_token_runtime_error:") +
                       error.what());
  }
}

void append_numeric_decoder_primitive_blockers(
    std::vector<std::string>& blockers) {
  std::vector<float> output;
  const Status rms_status =
      rms_norm_weighted({1.0F, 2.0F, 3.0F, 4.0F}, {1.0F, 0.5F}, 2U, 2U,
                        1.0e-6F, output);
  if (!rms_status.is_ok()) {
    blockers.push_back(rms_status.message());
    return;
  }
  const Status linear_status =
      linear_row_major({1.0F, 2.0F}, {3.0F, 4.0F, 5.0F, 6.0F}, 1U, 2U, 2U,
                       output);
  if (!linear_status.is_ok()) {
    blockers.push_back(linear_status.message());
    return;
  }
  const Status gelu_status = gelu_tanh_mul({1.0F, -1.0F}, {2.0F, 3.0F}, output);
  if (!gelu_status.is_ok()) {
    blockers.push_back(gelu_status.message());
    return;
  }
  std::vector<float> adapter_a(32U, 0.0F);
  std::vector<float> adapter_b(32U, 0.0F);
  adapter_a[0] = 1.0F;
  adapter_b[0] = 1.0F;
  const Status adapter_status =
      adapter_rank16_residual({1.0F, 0.0F}, adapter_a, adapter_b, 1U, 2U,
                              output);
  if (!adapter_status.is_ok()) {
    blockers.push_back(adapter_status.message());
    return;
  }
  ChunkedNllResult nll;
  const Status nll_first =
      chunked_nll_from_logits({0.0F, 1.0F}, 0U, 1U, nll, false);
  if (!nll_first.is_ok()) {
    blockers.push_back(nll_first.message());
    return;
  }
  const Status nll_final =
      chunked_nll_from_logits({2.0F}, 2U, 1U, nll, true);
  if (!nll_final.is_ok() || !std::isfinite(nll.nll) ||
      nll.confidence < 0.0 || nll.confidence > 1.0) {
    blockers.push_back(nll_final.is_ok()
                           ? "c5_decoder_math_chunked_nll_invalid"
                           : nll_final.message());
  }
}

void append_full_decoder_compute_kernel_blockers(
    C5FullDecoderRuntimeResult& result) {
  result.blockers.push_back(
      "c5_full_decoder_multi_token_qa_prompt_sequence_orchestration_missing");
  result.blockers.push_back("c5_full_decoder_rank16_adapter_stream_injection_missing");
  result.blockers.push_back("c5_full_decoder_42_layer_orchestration_missing");
  result.blockers.push_back("c5_full_decoder_chunked_lm_head_nll_writer_missing");
}

}  // namespace

C5FullDecoderRuntimeResult run_c5_full_decoder_runtime(
    const C5QaInferenceRequest& request) {
  C5FullDecoderRuntimeResult result;
  try {
    QaTokenization tokenization;
    SingleLayerBody layer0_body;
    const std::string manifest = read_text_file(request.decoder_manifest_path);
    append_architecture_blockers(manifest, result.blockers);
    append_tokenizer_identity_blockers(manifest, request, result.blockers);
    append_adapter_runtime_blockers(request, result.blockers);
    const SourceModelIdentity identity =
        parse_source_model_identity(manifest, result.blockers);
    append_source_model_blockers(identity, result, result.blockers);
    append_tensor_role_blockers(manifest, identity, result, result.blockers);
    append_per_layer_input_runtime_blockers(manifest, identity, result.blockers);
    if (result.blockers.empty()) {
      append_tensor_value_loader_blockers(identity, result.blockers);
    }
    if (result.blockers.empty()) {
      append_qa_prompt_token_runtime_blockers(request, tokenization,
                                             result.blockers);
    }
    if (result.blockers.empty()) {
      append_adapter_payload_blockers(request, result.blockers);
    }
    if (result.blockers.empty()) {
      append_numeric_decoder_primitive_blockers(result.blockers);
    }
    if (result.blockers.empty()) {
      append_ple_single_layer_slice_blockers(identity, tokenization,
                                             result.blockers);
    }
    if (result.blockers.empty()) {
      append_cpu_single_layer_body_blockers(identity, tokenization,
                                            layer0_body,
                                            result.blockers);
    }
    if (result.blockers.empty()) {
      append_opencl_single_layer_parity_blockers(request, identity, layer0_body,
                                                 result.blockers);
    }
  } catch (const std::exception& error) {
    result.blockers.push_back(std::string("c5_full_decoder_runtime_error:") +
                              error.what());
  }

  if (result.blockers.empty()) {
    append_full_decoder_compute_kernel_blockers(result);
  }
  return result;
}

}  // namespace polymath::gemma4
