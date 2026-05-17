#ifndef POLYMATH_GEMMA4_OPENCL_LAYER_RUNNER_H_
#define POLYMATH_GEMMA4_OPENCL_LAYER_RUNNER_H_

#include <string>

#include "polymath/gemma4/status.h"

namespace polymath::gemma4 {

Status run_opencl_layer0(const std::string& pack_dir, const std::string& output_dir);
Status run_opencl_layer_forward(const std::string& pack_dir, const std::string& output_dir);
Status run_opencl_two_layer_stack(const std::string& first_pack_dir,
                                  const std::string& second_pack_dir,
                                  const std::string& output_dir);

}  // namespace polymath::gemma4

#endif  // POLYMATH_GEMMA4_OPENCL_LAYER_RUNNER_H_
