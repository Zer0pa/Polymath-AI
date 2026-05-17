#ifndef POLYMATH_NATIVE_CPU_KERNELS_H_
#define POLYMATH_NATIVE_CPU_KERNELS_H_

#include <cstddef>
#include <vector>

namespace polymath_native {

struct RmsNormConfig {
  std::size_t rows;
  std::size_t width;
  float epsilon;
};

struct MatmulConfig {
  std::size_t rows;
  std::size_t shared;
  std::size_t cols;
};

struct RmsNormBackwardResult {
  std::vector<float> grad_input;
  std::vector<float> grad_weight;
};

struct MatmulBackwardResult {
  std::vector<float> grad_lhs;
  std::vector<float> grad_rhs;
};

void rms_norm_forward(const float* input,
                      const float* weight,
                      float* output,
                      RmsNormConfig config);

void rms_norm_backward(const float* input,
                       const float* weight,
                       const float* grad_output,
                       float* grad_input,
                       float* grad_weight,
                       RmsNormConfig config);

void matmul_forward(const float* lhs,
                    const float* rhs,
                    float* output,
                    MatmulConfig config);

void matmul_backward(const float* lhs,
                     const float* rhs,
                     const float* grad_output,
                     float* grad_lhs,
                     float* grad_rhs,
                     MatmulConfig config);

std::vector<float> rms_norm_forward_reference(const std::vector<float>& input,
                                              const std::vector<float>& weight,
                                              RmsNormConfig config);

RmsNormBackwardResult rms_norm_backward_reference(
    const std::vector<float>& input,
    const std::vector<float>& weight,
    const std::vector<float>& grad_output,
    RmsNormConfig config);

std::vector<float> matmul_forward_reference(const std::vector<float>& lhs,
                                            const std::vector<float>& rhs,
                                            MatmulConfig config);

MatmulBackwardResult matmul_backward_reference(
    const std::vector<float>& lhs,
    const std::vector<float>& rhs,
    const std::vector<float>& grad_output,
    MatmulConfig config);

}  // namespace polymath_native

#endif  // POLYMATH_NATIVE_CPU_KERNELS_H_
