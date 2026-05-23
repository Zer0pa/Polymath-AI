#ifndef POLYMATH_GEMMA4_ADAPTER_TRAINING_H_
#define POLYMATH_GEMMA4_ADAPTER_TRAINING_H_

#include <cstdint>
#include <string>

#include "polymath/gemma4/executor_interfaces.h"
#include "polymath/gemma4/status.h"

namespace polymath::gemma4 {

Status run_opencl_adapter_gradient_step(const std::string& fixture_dir,
                                        const std::string& checkpoint_dir,
                                        const std::string& output_dir);

Status run_opencl_adapter_sgd_update(const std::string& fixture_dir,
                                     const std::string& checkpoint_dir,
                                     const std::string& output_dir,
                                     float learning_rate);

Status run_opencl_streamed_distill_update(const std::string& token_cache_dir,
                                          const std::string& asset_dir,
                                          const std::string& layer0_pack_dir,
                                          const std::string& layer1_pack_dir,
                                          const std::string& checkpoint_dir,
                                          const std::string& output_dir,
                                          float learning_rate,
                                          bool write_raw_outputs = true,
                                          bool hash_static_artifacts = true);

Status run_opencl_streamed_distill_update_rank(const std::string& token_cache_dir,
                                               const std::string& asset_dir,
                                               const std::string& layer0_pack_dir,
                                               const std::string& layer1_pack_dir,
                                               const std::string& checkpoint_dir,
                                               const std::string& output_dir,
                                               float learning_rate,
                                               std::uint32_t adapter_rank,
                                               bool write_raw_outputs = true,
                                               bool hash_static_artifacts = true);

Status run_opencl_streamed_topk_kl_update_rank(const std::string& token_cache_dir,
                                               const std::string& asset_dir,
                                               const std::string& layer0_pack_dir,
                                               const std::string& layer1_pack_dir,
                                               const std::string& checkpoint_dir,
                                               const std::string& teacher_shard_dir,
                                               const std::string& output_dir,
                                               float learning_rate,
                                               std::uint32_t adapter_rank,
                                               bool apply_update,
                                               bool write_raw_outputs = true,
                                               bool hash_static_artifacts = true);

class OpenClAdapterTrainingStepExecutor final : public TrainingStepExecutor {
 public:
  Status run_training_step(const TrainingStepRequest& request) override;
};

}  // namespace polymath::gemma4

#endif  // POLYMATH_GEMMA4_ADAPTER_TRAINING_H_
