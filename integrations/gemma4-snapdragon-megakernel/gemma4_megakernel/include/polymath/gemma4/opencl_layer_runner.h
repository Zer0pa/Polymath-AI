#ifndef POLYMATH_GEMMA4_OPENCL_LAYER_RUNNER_H_
#define POLYMATH_GEMMA4_OPENCL_LAYER_RUNNER_H_

#include <cstdint>
#include <string>
#include <vector>

#include "polymath/gemma4/status.h"

namespace polymath::gemma4 {

struct OpenClSingleTokenLayerWeights {
  std::vector<float> input_layernorm_weight;
  std::vector<float> layer_scalar;
  std::vector<float> mlp_down_proj_weight;
  std::vector<float> mlp_gate_proj_weight;
  std::vector<float> mlp_up_proj_weight;
  std::vector<float> per_layer_input_gate_weight;
  std::vector<float> per_layer_projection_weight;
  std::vector<float> post_attention_layernorm_weight;
  std::vector<float> post_feedforward_layernorm_weight;
  std::vector<float> post_per_layer_input_norm_weight;
  std::vector<float> pre_feedforward_layernorm_weight;
  std::vector<float> self_attn_k_norm_weight;
  std::vector<float> self_attn_k_proj_weight;
  std::vector<float> self_attn_o_proj_weight;
  std::vector<float> self_attn_q_norm_weight;
  std::vector<float> self_attn_q_proj_weight;
  std::vector<float> self_attn_v_proj_weight;
};

struct OpenClSingleTokenLayerInput {
  std::uint32_t layer_index = 0;
  std::vector<float> layer_input_row;
  std::vector<float> per_layer_input_row;
  std::uint32_t position_id = 0;
};

struct OpenClSingleTokenLayerResult {
  std::vector<float> output_row;
  std::string opencl_library;
  double elapsed_seconds = 0.0;
  std::uint64_t max_resident_set_kb = 0;
};

struct OpenClPromptLayerInput {
  std::uint32_t layer_index = 0;
  std::uint32_t active_tokens = 0;
  std::vector<float> layer_input_rows;
  std::vector<float> per_layer_input_rows;
  std::vector<std::uint8_t> attention_mask;
  std::vector<std::uint32_t> position_ids;
};

struct OpenClPromptLayerResult {
  std::vector<float> output_rows;
  std::string opencl_library;
  double elapsed_seconds = 0.0;
  std::uint64_t max_resident_set_kb = 0;
};

struct OpenClRuntimeDiscoveryConfig {
  std::string opencl_library;
  std::vector<std::string> opencl_library_candidates;
};

Status run_opencl_layer0(const std::string& pack_dir, const std::string& output_dir);
Status run_opencl_layer_forward(const std::string& pack_dir, const std::string& output_dir);
Status run_opencl_two_layer_stack(const std::string& first_pack_dir,
                                  const std::string& second_pack_dir,
                                  const std::string& output_dir);
Status probe_opencl_layer_runtime_available(
    const OpenClRuntimeDiscoveryConfig& config = OpenClRuntimeDiscoveryConfig{});
Status run_opencl_single_token_layer_forward(
    const OpenClSingleTokenLayerWeights& weights,
    const OpenClSingleTokenLayerInput& input,
    OpenClSingleTokenLayerResult& result,
    const OpenClRuntimeDiscoveryConfig& config = OpenClRuntimeDiscoveryConfig{});
Status run_opencl_prompt_layer_forward(
    const OpenClSingleTokenLayerWeights& weights,
    const OpenClPromptLayerInput& input,
    OpenClPromptLayerResult& result,
    const OpenClRuntimeDiscoveryConfig& config = OpenClRuntimeDiscoveryConfig{});

}  // namespace polymath::gemma4

#endif  // POLYMATH_GEMMA4_OPENCL_LAYER_RUNNER_H_
