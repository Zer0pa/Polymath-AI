#include "polymath/gemma4/c5_full_decoder_runtime.h"

#include <cctype>
#include <cstdint>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "polymath/gemma4/safetensors_reader.h"
#include "polymath/gemma4/sha256.h"

namespace polymath::gemma4 {
namespace {

constexpr const char* kEmbedTokensKey =
    "model.language_model.embed_tokens.weight";
constexpr std::uint32_t kLayerCount = 42;
constexpr std::uint32_t kHiddenSize = 2560;
constexpr std::uint32_t kVocabSize = 262144;
constexpr std::uint32_t kIntermediateSize = 10240;
constexpr std::uint32_t kAttentionHeads = 8;
constexpr std::uint32_t kKeyValueHeads = 2;
constexpr std::uint32_t kHeadDim = 256;
constexpr std::uint32_t kSmallInputSize = 256;

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

void append_full_decoder_compute_kernel_blockers(
    C5FullDecoderRuntimeResult& result) {
  result.blockers.push_back("c5_full_decoder_streamed_compute_kernel_missing");
  result.blockers.push_back("c5_full_decoder_tensor_value_loader_missing");
  result.blockers.push_back("c5_full_decoder_qa_prompt_token_runtime_missing");
  result.blockers.push_back("c5_full_decoder_attention_mlp_kernel_missing");
  result.blockers.push_back("c5_full_decoder_rank16_adapter_injection_missing");
  result.blockers.push_back("c5_full_decoder_chunked_lm_head_nll_writer_missing");
}

}  // namespace

C5FullDecoderRuntimeResult run_c5_full_decoder_runtime(
    const C5QaInferenceRequest& request) {
  C5FullDecoderRuntimeResult result;
  try {
    const std::string manifest = read_text_file(request.decoder_manifest_path);
    append_architecture_blockers(manifest, result.blockers);
    append_tokenizer_identity_blockers(manifest, request, result.blockers);
    append_adapter_runtime_blockers(request, result.blockers);
    const SourceModelIdentity identity =
        parse_source_model_identity(manifest, result.blockers);
    append_source_model_blockers(identity, result, result.blockers);
    append_tensor_role_blockers(manifest, identity, result, result.blockers);
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
