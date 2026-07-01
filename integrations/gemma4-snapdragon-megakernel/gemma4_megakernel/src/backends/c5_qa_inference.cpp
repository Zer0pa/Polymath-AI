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
  std::vector<std::string> blockers;
  append_missing_if_empty(blockers, request.run_label, "run_label_missing");
  append_missing_if_empty(blockers, request.eval_point, "eval_point_missing");
  append_missing_if_empty(blockers, request.checkpoint_role, "checkpoint_role_missing");
  append_missing_if_empty(blockers, request.checkpoint_payload_path,
                          "checkpoint_payload_path_missing");
  append_missing_if_empty(blockers, request.checkpoint_sha256, "checkpoint_sha256_missing");
  append_missing_if_empty(blockers, request.heldout_qa_jsonl_path, "heldout_qa_jsonl_missing");
  append_missing_if_empty(blockers, request.output_jsonl_path, "output_jsonl_missing");

  if (!request.checkpoint_role.empty() && request.checkpoint_role != "candidate" &&
      request.checkpoint_role != "stable_baseline") {
    blockers.push_back("checkpoint_role_invalid");
  }
  if (!request.checkpoint_sha256.empty() && !is_sha256(request.checkpoint_sha256)) {
    blockers.push_back("checkpoint_sha256_invalid");
  }

  std::string checkpoint_actual_sha256;
  std::uint64_t checkpoint_size = 0;
  std::string heldout_qa_sha256;
  std::uint64_t heldout_record_count = 0;
  try {
    if (!request.checkpoint_payload_path.empty()) {
      if (!file_exists(request.checkpoint_payload_path)) {
        blockers.push_back("checkpoint_payload_path_not_found");
      } else {
        checkpoint_actual_sha256 = sha256_file_hex(request.checkpoint_payload_path);
        checkpoint_size = file_size_bytes(request.checkpoint_payload_path);
        if (is_sha256(request.checkpoint_sha256) &&
            checkpoint_actual_sha256 != request.checkpoint_sha256) {
          blockers.push_back("checkpoint_payload_sha256_mismatch");
        }
      }
    }
    if (!request.heldout_qa_jsonl_path.empty()) {
      if (!file_exists(request.heldout_qa_jsonl_path)) {
        blockers.push_back("heldout_qa_jsonl_path_not_found");
      } else {
        heldout_qa_sha256 = sha256_file_hex(request.heldout_qa_jsonl_path);
        heldout_record_count = count_jsonl_records(request.heldout_qa_jsonl_path);
        if (heldout_record_count == 0U) {
          blockers.push_back("heldout_qa_jsonl_empty");
        }
      }
    }
  } catch (const std::exception& error) {
    blockers.push_back(std::string("io_error:") + error.what());
  }

  append_missing_if_empty(blockers, request.tokenizer_dir, "tokenizer_dir_missing");
  append_missing_if_empty(blockers, request.decoder_manifest_path, "decoder_manifest_missing");
  append_missing_if_empty(blockers, request.lm_head_path, "lm_head_or_unembedding_missing");
  append_missing_if_empty(blockers, request.adapter_site_policy_path,
                          "adapter_site_policy_missing");
  append_tokenizer_table_blockers(blockers, request.tokenizer_dir);
  append_file_missing_if_present(blockers, request.decoder_manifest_path,
                                 "decoder_manifest_path_not_found");
  append_file_missing_if_present(blockers, request.lm_head_path,
                                 "lm_head_or_unembedding_path_not_found");
  append_file_missing_if_present(blockers, request.adapter_site_policy_path,
                                 "adapter_site_policy_path_not_found");

  if (blockers.empty()) {
    blockers.push_back("full_decoder_logits_generation_not_implemented");
  }

  write_report(request, blockers, checkpoint_actual_sha256, checkpoint_size,
               heldout_qa_sha256, heldout_record_count);
  return Status::invalid(blockers.front());
}

}  // namespace polymath::gemma4
