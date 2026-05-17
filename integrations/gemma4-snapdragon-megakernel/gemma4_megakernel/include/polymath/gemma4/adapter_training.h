#ifndef POLYMATH_GEMMA4_ADAPTER_TRAINING_H_
#define POLYMATH_GEMMA4_ADAPTER_TRAINING_H_

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

class OpenClAdapterTrainingStepExecutor final : public TrainingStepExecutor {
 public:
  Status run_training_step(const TrainingStepRequest& request) override;
};

}  // namespace polymath::gemma4

#endif  // POLYMATH_GEMMA4_ADAPTER_TRAINING_H_
