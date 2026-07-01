#include "polymath/gemma4/c5_qa_inference.h"

#include <cctype>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#include "polymath/gemma4/json_writer.h"
#include "polymath/gemma4/sha256.h"

namespace polymath::gemma4 {
namespace {

constexpr const char* kSchema = "polymath_c5_qa_inference_native_report_v1";
constexpr const char* kDecoderManifestSchema =
    "polymath_c5_full_decoder_manifest_v1";
constexpr const char* kAdapterSitePolicySchema =
    "polymath_c5_adapter_site_policy_v1";
constexpr const char* kGemma4E4bModelId = "google/gemma-4-E4B";
constexpr const char* kGemma4E4bRevision =
    "7aa32e6889efd6300124851b164f8b364314c3d8";
constexpr std::uint32_t kGemma4E4bLayerCount = 42;
constexpr std::uint32_t kGemma4E4bHiddenSize = 2560;
constexpr std::uint32_t kGemma4E4bVocabSize = 262144;
constexpr std::uint32_t kMaxAcceptedVocabChunkSize = 16384;
constexpr std::uint32_t kMaxAcceptedGenerationTokens = 512;

bool is_sha256(const std::string& value) {
  if (value.size() != 64U) {
    return false;
  }
  for (const char character : value) {
    if (std::isxdigit(static_cast<unsigned char>(character)) == 0) {
      return false;
    }
  }
  return true;
}

bool file_exists(const std::string& path) {
  std::ifstream file(path, std::ios::binary);
  return static_cast<bool>(file);
}

std::string join_path(const std::string& base, const std::string& leaf) {
  if (base.empty() || base.back() == '/') {
    return base + leaf;
  }
  return base + "/" + leaf;
}

std::uint64_t file_size_bytes(const std::string& path) {
  std::ifstream file(path, std::ios::binary | std::ios::ate);
  if (!file) {
    throw std::runtime_error("failed to open for size: " + path);
  }
  return static_cast<std::uint64_t>(file.tellg());
}

std::uint64_t count_jsonl_records(const std::string& path) {
  std::ifstream file(path);
  if (!file) {
    throw std::runtime_error("failed to open heldout QA JSONL: " + path);
  }
  std::uint64_t count = 0;
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
      ++count;
    }
  }
  return count;
}

std::string read_text_file(const std::string& path) {
  std::ifstream file(path);
  if (!file) {
    throw std::runtime_error("failed to read text file: " + path);
  }
  std::string text;
  std::string line;
  while (std::getline(file, line)) {
    text += line;
    text.push_back('\n');
  }
  return text;
}

bool contains(const std::string& text, const std::string& needle) {
  return text.find(needle) != std::string::npos;
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

bool contains_json_string_pair(const std::string& text,
                               const std::string& key,
                               const std::string& value) {
  const std::string compact = compact_json_text(text);
  return contains(compact, "\"" + key + "\":\"" + value + "\"");
}

bool contains_json_unsigned_pair(const std::string& text,
                                 const std::string& key,
                                 std::uint32_t value) {
  const std::string compact = compact_json_text(text);
  return contains(compact, "\"" + key + "\":" + std::to_string(value));
}

bool contains_json_bool_pair(const std::string& text,
                             const std::string& key,
                             bool value) {
  const std::string compact = compact_json_text(text);
  return contains(compact, "\"" + key + "\":" + (value ? "true" : "false"));
}

bool contains_json_key(const std::string& text, const std::string& key) {
  return contains(compact_json_text(text), "\"" + key + "\":");
}

bool contains_json_array_pair(const std::string& text,
                              const std::string& key,
                              const std::string& compact_array) {
  const std::string compact = compact_json_text(text);
  return contains(compact, "\"" + key + "\":" + compact_array);
}

void append_missing_if_empty(std::vector<std::string>& blockers,
                             const std::string& value,
                             const std::string& blocker) {
  if (value.empty()) {
    blockers.push_back(blocker);
  }
}

void append_file_missing_if_present(std::vector<std::string>& blockers,
                                    const std::string& path,
                                    const std::string& blocker) {
  if (!path.empty() && !file_exists(path)) {
    blockers.push_back(blocker);
  }
}

bool decoder_manifest_embeds_lm_head(const std::string& path) {
  try {
    const std::string text = read_text_file(path);
    return contains(text, "\"lm_head\"") &&
           contains_json_bool_pair(text, "embedded_in_decoder", true);
  } catch (const std::exception&) {
    return false;
  }
}

std::string first_existing_lm_head_path(const std::string& component_pack_dir) {
  const std::vector<std::string> names = {
      "lm_head_or_unembedding.bf16",
      "lm_head_or_unembedding.f16",
      "lm_head_or_unembedding.f32",
      "lm_head.bf16",
      "lm_head.f16",
      "lm_head.f32",
      "unembedding.bf16",
      "unembedding.f16",
      "unembedding.f32",
  };
  for (const std::string& name : names) {
    const std::string candidate = join_path(component_pack_dir, name);
    if (file_exists(candidate)) {
      return candidate;
    }
  }
  return std::string();
}

C5QaInferenceRequest resolve_component_pack_paths(
    const C5QaInferenceRequest& request) {
  C5QaInferenceRequest resolved = request;
  if (resolved.decoder_component_pack_dir.empty()) {
    return resolved;
  }
  if (resolved.decoder_manifest_path.empty()) {
    resolved.decoder_manifest_path =
        join_path(resolved.decoder_component_pack_dir, "decoder_manifest.json");
  }
  if (resolved.adapter_site_policy_path.empty()) {
    resolved.adapter_site_policy_path =
        join_path(resolved.decoder_component_pack_dir, "adapter_site_policy.json");
  }
  if (resolved.lm_head_path.empty()) {
    resolved.lm_head_path =
        first_existing_lm_head_path(resolved.decoder_component_pack_dir);
  }
  return resolved;
}

void append_tokenizer_table_blockers(std::vector<std::string>& blockers,
                                     const std::string& tokenizer_dir) {
  if (tokenizer_dir.empty()) {
    return;
  }
  if (!file_exists(join_path(tokenizer_dir, "vocab.hex.tsv"))) {
    blockers.push_back("tokenizer_vocab_hex_missing");
  }
  if (!file_exists(join_path(tokenizer_dir, "merges.hex.tsv"))) {
    blockers.push_back("tokenizer_merges_hex_missing");
  }
}

void append_decoder_manifest_blockers(std::vector<std::string>& blockers,
                                      const std::string& path) {
  if (path.empty() || !file_exists(path)) {
    return;
  }
  try {
    const std::string text = read_text_file(path);
    if (!contains_json_string_pair(text, "schema_version", kDecoderManifestSchema)) {
      blockers.push_back("decoder_manifest_schema_version_mismatch");
    }
    if (!contains_json_string_pair(text, "model_id", kGemma4E4bModelId)) {
      blockers.push_back("decoder_manifest_model_id_mismatch");
    }
    if (!contains_json_string_pair(text, "hf_revision", kGemma4E4bRevision)) {
      blockers.push_back("decoder_manifest_hf_revision_mismatch");
    }
    if (!contains_json_string_pair(text, "kind", "full_gemma4_text_decoder_logits")) {
      blockers.push_back("decoder_manifest_decoder_kind_mismatch");
    }
    if (!contains_json_unsigned_pair(text, "num_hidden_layers", kGemma4E4bLayerCount)) {
      blockers.push_back("decoder_manifest_decoder_num_hidden_layers_mismatch");
    }
    if (!contains_json_unsigned_pair(text, "hidden_size", kGemma4E4bHiddenSize)) {
      blockers.push_back("decoder_manifest_decoder_hidden_size_mismatch");
    }
    if (!contains_json_unsigned_pair(text, "vocab_size", kGemma4E4bVocabSize)) {
      blockers.push_back("decoder_manifest_decoder_vocab_size_mismatch");
    }
    if (!contains_json_unsigned_pair(text, "logits_vocabulary_size", kGemma4E4bVocabSize)) {
      blockers.push_back("decoder_manifest_decoder_logits_vocabulary_size_mismatch");
    }
    if (contains_json_bool_pair(text, "materializes_full_bsv_logits", true)) {
      blockers.push_back("decoder_manifest_full_bsv_logits_materialization_forbidden");
    }
  } catch (const std::exception& error) {
    blockers.push_back(std::string("decoder_manifest_read_error:") + error.what());
  }
}

void append_adapter_site_policy_blockers(std::vector<std::string>& blockers,
                                         const std::string& path,
                                         const std::string& checkpoint_role,
                                         const std::string& checkpoint_sha256) {
  if (path.empty() || !file_exists(path)) {
    return;
  }
  try {
    const std::string text = read_text_file(path);
    if (!contains_json_string_pair(text, "schema_version", kAdapterSitePolicySchema)) {
      blockers.push_back("adapter_site_policy_schema_version_mismatch");
    }
    if (!contains_json_string_pair(text, "model_id", kGemma4E4bModelId)) {
      blockers.push_back("adapter_site_policy_model_id_mismatch");
    }
    if (!contains_json_unsigned_pair(text, "adapter_rank", 16U)) {
      blockers.push_back("adapter_site_policy_rank_mismatch");
    }
    if (!contains_json_key(text, "decoder_layer_index")) {
      blockers.push_back("adapter_site_policy_decoder_layer_index_missing");
    }
    if (!contains_json_key(text, "adapter_site")) {
      blockers.push_back("adapter_site_policy_site_missing");
    }
    if (!contains_json_array_pair(text, "input_shape", "[1,16,2560]")) {
      blockers.push_back("adapter_site_policy_input_shape_mismatch");
    }
    if (!contains_json_array_pair(text, "output_shape", "[1,16,2560]")) {
      blockers.push_back("adapter_site_policy_output_shape_mismatch");
    }
    if (!contains_json_key(text, "candidate_adapter_sha256")) {
      blockers.push_back("adapter_site_policy_candidate_sha256_missing");
    }
    if (!contains_json_key(text, "stable_baseline_adapter_sha256")) {
      blockers.push_back("adapter_site_policy_stable_sha256_missing");
    }
    if (checkpoint_role == "candidate" &&
        is_sha256(checkpoint_sha256) &&
        !contains_json_string_pair(text, "candidate_adapter_sha256",
                                   checkpoint_sha256)) {
      blockers.push_back("adapter_site_policy_candidate_sha256_mismatch");
    }
    if (checkpoint_role == "stable_baseline" &&
        is_sha256(checkpoint_sha256) &&
        !contains_json_string_pair(text, "stable_baseline_adapter_sha256",
                                   checkpoint_sha256)) {
      blockers.push_back("adapter_site_policy_stable_sha256_mismatch");
    }
    if (!contains_json_bool_pair(text, "bridge_mse_is_c5_loss", false)) {
      blockers.push_back("adapter_site_policy_bridge_mse_loss_forbidden");
    }
  } catch (const std::exception& error) {
    blockers.push_back(std::string("adapter_site_policy_read_error:") +
                       error.what());
  }
}

void append_runtime_plan_blockers(std::vector<std::string>& blockers,
                                  const C5QaInferenceRequest& request) {
  if (request.vocab_chunk_size == 0U) {
    blockers.push_back("vocab_chunk_size_zero");
  }
  if (request.vocab_chunk_size > kMaxAcceptedVocabChunkSize ||
      request.vocab_chunk_size > kGemma4E4bVocabSize) {
    blockers.push_back("vocab_chunk_size_exceeds_streaming_limit");
  }
  if (request.max_generation_tokens == 0U) {
    blockers.push_back("max_generation_tokens_zero");
  }
  if (request.max_generation_tokens > kMaxAcceptedGenerationTokens) {
    blockers.push_back("max_generation_tokens_exceeds_c5_limit");
  }
}

void write_string_array(std::ostream& stream, const std::vector<std::string>& values) {
  stream << '[';
  for (std::size_t index = 0; index < values.size(); ++index) {
    if (index != 0U) {
      stream << ',';
    }
    write_json_string(stream, values[index]);
  }
  stream << ']';
}

void write_optional_string_field(std::ostream& stream,
                                 const char* key,
                                 const std::string& value,
                                 bool prepend_comma) {
  if (value.empty()) {
    return;
  }
  if (prepend_comma) {
    stream << ',';
  }
  write_json_string(stream, key);
  stream << ':';
  write_json_string(stream, value);
}

void write_path_identity(std::ostream& stream, const std::string& path) {
  stream << "{\"present\":" << (path.empty() ? "false" : "true");
  stream << ",\"path_string_sha256\":";
  write_json_string(stream, path.empty() ? std::string() : sha256_text_hex(path));
  stream << ",\"path_redacted\":true}";
}

void write_report(const C5QaInferenceRequest& request,
                  const std::vector<std::string>& blockers,
                  const std::string& checkpoint_actual_sha256,
                  std::uint64_t checkpoint_size_bytes,
                  const std::string& heldout_qa_sha256,
                  std::uint64_t heldout_record_count) {
  const std::string first_missing =
      blockers.empty() ? std::string() : blockers.front();
  std::cout << "{\"schema_version\":";
  write_json_string(std::cout, kSchema);
  std::cout << ",\"status\":";
  write_json_string(std::cout, blockers.empty() ? "pass" : "blocked");
  std::cout << ",\"first_missing_green_field\":";
  if (first_missing.empty()) {
    std::cout << "null";
  } else {
    write_json_string(std::cout, first_missing);
  }
  std::cout << ",\"blockers\":";
  write_string_array(std::cout, blockers);
  std::cout << ",\"run_label\":";
  write_json_string(std::cout, request.run_label);
  std::cout << ",\"eval_point\":";
  write_json_string(std::cout, request.eval_point);
  std::cout << ",\"checkpoint_role\":";
  write_json_string(std::cout, request.checkpoint_role);
  std::cout << ",\"checkpoint_payload_identity\":{";
  std::cout << "\"expected_sha256\":";
  write_json_string(std::cout, request.checkpoint_sha256);
  write_optional_string_field(std::cout, "actual_sha256", checkpoint_actual_sha256, true);
  std::cout << ",\"size_bytes\":" << checkpoint_size_bytes;
  std::cout << ",\"path_string_sha256\":";
  write_json_string(std::cout, request.checkpoint_payload_path.empty()
                                   ? std::string()
                                   : sha256_text_hex(request.checkpoint_payload_path));
  std::cout << ",\"path_redacted\":true}";
  std::cout << ",\"heldout_qa_identity\":{";
  write_optional_string_field(std::cout, "sha256", heldout_qa_sha256, false);
  if (heldout_qa_sha256.empty()) {
    std::cout << "\"sha256\":null";
  }
  std::cout << ",\"record_count\":" << heldout_record_count;
  std::cout << ",\"path_string_sha256\":";
  write_json_string(std::cout, request.heldout_qa_jsonl_path.empty()
                                   ? std::string()
                                   : sha256_text_hex(request.heldout_qa_jsonl_path));
  std::cout << ",\"path_redacted\":true}";
  std::cout << ",\"output_jsonl_contract\":{\"path_string_sha256\":";
  write_json_string(std::cout, request.output_jsonl_path.empty()
                                   ? std::string()
                                   : sha256_text_hex(request.output_jsonl_path));
  std::cout << ",\"path_redacted\":true,\"raw_prediction_payload_outside_git_required\":true}";
  std::cout << ",\"decoder_component_pack_identity\":";
  write_path_identity(std::cout, request.decoder_component_pack_dir);
  std::cout << ",\"resolved_runtime_component_paths\":{";
  std::cout << "\"decoder_manifest\":";
  write_path_identity(std::cout, request.decoder_manifest_path);
  std::cout << ",\"lm_head_or_unembedding\":";
  write_path_identity(std::cout, request.lm_head_path);
  std::cout << ",\"adapter_site_policy\":";
  write_path_identity(std::cout, request.adapter_site_policy_path);
  std::cout << '}';
  std::cout << ",\"memory_strategy_contract\":{";
  std::cout << "\"vocab_chunk_size\":" << request.vocab_chunk_size;
  std::cout << ",\"max_generation_tokens\":" << request.max_generation_tokens;
  std::cout << ",\"max_accepted_vocab_chunk_size\":"
            << kMaxAcceptedVocabChunkSize;
  std::cout << ",\"full_bsv_logits_materialization_allowed\":false";
  std::cout << ",\"streamed_or_chunked_logits_required\":true}";
  std::cout << ",\"required_runtime_components\":{";
  std::cout << "\"tokenizer_dir_present\":" << (request.tokenizer_dir.empty() ? "false" : "true");
  std::cout << ",\"decoder_manifest_present\":"
            << (request.decoder_manifest_path.empty() ? "false" : "true");
  std::cout << ",\"lm_head_or_unembedding_present\":"
            << (request.lm_head_path.empty() ? "false" : "true");
  std::cout << ",\"adapter_site_policy_present\":"
            << (request.adapter_site_policy_path.empty() ? "false" : "true");
  std::cout << "},\"raw_boundary_proof\":{";
  std::cout << "\"raw_payload_bytes_in_report\":false,";
  std::cout << "\"prediction_jsonl_written\":false,";
  std::cout << "\"checkpoint_payload_copied_to_repo\":false}";
  std::cout << ",\"nonclaims\":[";
  write_json_string(std::cout, "no C5 pass");
  std::cout << ',';
  write_json_string(std::cout, "no prediction JSONL emitted without full decoder logits generation");
  std::cout << ',';
  write_json_string(std::cout, "no learning or model-quality claim");
  std::cout << "]}\n";
}

}  // namespace

Status run_c5_qa_predict(const C5QaInferenceRequest& request) {
  const C5QaInferenceRequest resolved_request = resolve_component_pack_paths(request);
  std::vector<std::string> blockers;
  append_missing_if_empty(blockers, resolved_request.run_label, "run_label_missing");
  append_missing_if_empty(blockers, resolved_request.eval_point, "eval_point_missing");
  append_missing_if_empty(blockers, resolved_request.checkpoint_role, "checkpoint_role_missing");
  append_missing_if_empty(blockers, resolved_request.checkpoint_payload_path,
                          "checkpoint_payload_path_missing");
  append_missing_if_empty(blockers, resolved_request.checkpoint_sha256, "checkpoint_sha256_missing");
  append_missing_if_empty(blockers, resolved_request.heldout_qa_jsonl_path, "heldout_qa_jsonl_missing");
  append_missing_if_empty(blockers, resolved_request.output_jsonl_path, "output_jsonl_missing");

  if (!resolved_request.checkpoint_role.empty() &&
      resolved_request.checkpoint_role != "candidate" &&
      resolved_request.checkpoint_role != "stable_baseline") {
    blockers.push_back("checkpoint_role_invalid");
  }
  if (!resolved_request.checkpoint_sha256.empty() &&
      !is_sha256(resolved_request.checkpoint_sha256)) {
    blockers.push_back("checkpoint_sha256_invalid");
  }
  append_runtime_plan_blockers(blockers, resolved_request);

  std::string checkpoint_actual_sha256;
  std::uint64_t checkpoint_size = 0;
  std::string heldout_qa_sha256;
  std::uint64_t heldout_record_count = 0;
  try {
    if (!resolved_request.checkpoint_payload_path.empty()) {
      if (!file_exists(resolved_request.checkpoint_payload_path)) {
        blockers.push_back("checkpoint_payload_path_not_found");
      } else {
        checkpoint_actual_sha256 =
            sha256_file_hex(resolved_request.checkpoint_payload_path);
        checkpoint_size = file_size_bytes(resolved_request.checkpoint_payload_path);
        if (is_sha256(resolved_request.checkpoint_sha256) &&
            checkpoint_actual_sha256 != resolved_request.checkpoint_sha256) {
          blockers.push_back("checkpoint_payload_sha256_mismatch");
        }
      }
    }
    if (!resolved_request.heldout_qa_jsonl_path.empty()) {
      if (!file_exists(resolved_request.heldout_qa_jsonl_path)) {
        blockers.push_back("heldout_qa_jsonl_path_not_found");
      } else {
        heldout_qa_sha256 = sha256_file_hex(resolved_request.heldout_qa_jsonl_path);
        heldout_record_count =
            count_jsonl_records(resolved_request.heldout_qa_jsonl_path);
        if (heldout_record_count == 0U) {
          blockers.push_back("heldout_qa_jsonl_empty");
        }
      }
    }
  } catch (const std::exception& error) {
    blockers.push_back(std::string("io_error:") + error.what());
  }

  append_missing_if_empty(blockers, resolved_request.tokenizer_dir,
                          "tokenizer_dir_missing");
  append_missing_if_empty(blockers, resolved_request.decoder_manifest_path,
                          "decoder_manifest_missing");
  if (resolved_request.lm_head_path.empty() &&
      (resolved_request.decoder_manifest_path.empty() ||
       !decoder_manifest_embeds_lm_head(resolved_request.decoder_manifest_path))) {
    blockers.push_back("lm_head_or_unembedding_missing");
  }
  append_missing_if_empty(blockers, resolved_request.adapter_site_policy_path,
                          "adapter_site_policy_missing");
  append_tokenizer_table_blockers(blockers, resolved_request.tokenizer_dir);
  append_file_missing_if_present(blockers, resolved_request.decoder_manifest_path,
                                 "decoder_manifest_path_not_found");
  append_file_missing_if_present(blockers, resolved_request.lm_head_path,
                                 "lm_head_or_unembedding_path_not_found");
  append_file_missing_if_present(blockers, resolved_request.adapter_site_policy_path,
                                 "adapter_site_policy_path_not_found");
  append_decoder_manifest_blockers(blockers, resolved_request.decoder_manifest_path);
  append_adapter_site_policy_blockers(blockers,
                                      resolved_request.adapter_site_policy_path,
                                      resolved_request.checkpoint_role,
                                      resolved_request.checkpoint_sha256);

  if (blockers.empty()) {
    blockers.push_back("full_decoder_logits_generation_not_implemented");
  }

  write_report(resolved_request, blockers, checkpoint_actual_sha256, checkpoint_size,
               heldout_qa_sha256, heldout_record_count);
  return Status::invalid(blockers.front());
}

}  // namespace polymath::gemma4
