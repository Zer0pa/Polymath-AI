#include "polymath_native/cpu_kernels.h"

#include <cmath>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace polymath_native {
namespace {

void require_dimension(std::size_t value, std::string_view name) {
  if (value == 0U) {
    throw std::invalid_argument(std::string(name) + " must be greater than zero");
  }
}

void require_epsilon(float epsilon) {
  if (!(epsilon > 0.0F)) {
    throw std::invalid_argument("epsilon must be greater than zero");
  }
}

void require_pointer(const float* pointer, std::string_view name) {
  if (pointer == nullptr) {
    throw std::invalid_argument(std::string(name) + " must not be null");
  }
}

void require_vector_size(const std::vector<float>& values,
                         std::size_t expected_size,
                         std::string_view name) {
  if (values.size() != expected_size) {
    throw std::invalid_argument(std::string(name) + " has an unexpected size");
  }
}

std::size_t rms_element_count(RmsNormConfig config) {
  return config.rows * config.width;
}

std::size_t matmul_lhs_count(MatmulConfig config) {
  return config.rows * config.shared;
}

std::size_t matmul_rhs_count(MatmulConfig config) {
  return config.shared * config.cols;
}

std::size_t matmul_output_count(MatmulConfig config) {
  return config.rows * config.cols;
}

void validate_rms_config(RmsNormConfig config) {
  require_dimension(config.rows, "rows");
  require_dimension(config.width, "width");
  require_epsilon(config.epsilon);
}

void validate_matmul_config(MatmulConfig config) {
  require_dimension(config.rows, "rows");
  require_dimension(config.shared, "shared");
  require_dimension(config.cols, "cols");
}

float inverse_rms_for_row(const float* row, RmsNormConfig config) {
  double square_sum = 0.0;
  for (std::size_t col = 0; col < config.width; ++col) {
    const double value = row[col];
    square_sum += value * value;
  }

  const double mean_square = square_sum / static_cast<double>(config.width);
  return static_cast<float>(1.0 / std::sqrt(mean_square + config.epsilon));
}

}  // namespace

void rms_norm_forward(const float* input,
                      const float* weight,
                      float* output,
                      RmsNormConfig config) {
  validate_rms_config(config);
  require_pointer(input, "input");
  require_pointer(weight, "weight");
  require_pointer(output, "output");

  for (std::size_t row = 0; row < config.rows; ++row) {
    const float* input_row = input + (row * config.width);
    float* output_row = output + (row * config.width);
    const float inverse_rms = inverse_rms_for_row(input_row, config);

    for (std::size_t col = 0; col < config.width; ++col) {
      output_row[col] = input_row[col] * inverse_rms * weight[col];
    }
  }
}

void rms_norm_backward(const float* input,
                       const float* weight,
                       const float* grad_output,
                       float* grad_input,
                       float* grad_weight,
                       RmsNormConfig config) {
  validate_rms_config(config);
  require_pointer(input, "input");
  require_pointer(weight, "weight");
  require_pointer(grad_output, "grad_output");
  require_pointer(grad_input, "grad_input");
  require_pointer(grad_weight, "grad_weight");

  std::vector<double> grad_weight_total(config.width, 0.0);

  for (std::size_t row = 0; row < config.rows; ++row) {
    const float* input_row = input + (row * config.width);
    const float* grad_output_row = grad_output + (row * config.width);
    float* grad_input_row = grad_input + (row * config.width);
    const float inverse_rms = inverse_rms_for_row(input_row, config);
    const double inverse_rms_cubed =
        static_cast<double>(inverse_rms) * inverse_rms * inverse_rms;

    double weighted_dot = 0.0;
    for (std::size_t col = 0; col < config.width; ++col) {
      weighted_dot += static_cast<double>(grad_output_row[col]) * weight[col] *
                      input_row[col];
      grad_weight_total[col] +=
          static_cast<double>(grad_output_row[col]) * input_row[col] * inverse_rms;
    }

    const double row_scale =
        inverse_rms_cubed * weighted_dot / static_cast<double>(config.width);
    for (std::size_t col = 0; col < config.width; ++col) {
      const double direct =
          static_cast<double>(grad_output_row[col]) * weight[col] * inverse_rms;
      grad_input_row[col] =
          static_cast<float>(direct - (static_cast<double>(input_row[col]) * row_scale));
    }
  }

  for (std::size_t col = 0; col < config.width; ++col) {
    grad_weight[col] = static_cast<float>(grad_weight_total[col]);
  }
}

void matmul_forward(const float* lhs,
                    const float* rhs,
                    float* output,
                    MatmulConfig config) {
  validate_matmul_config(config);
  require_pointer(lhs, "lhs");
  require_pointer(rhs, "rhs");
  require_pointer(output, "output");

  for (std::size_t row = 0; row < config.rows; ++row) {
    for (std::size_t col = 0; col < config.cols; ++col) {
      double total = 0.0;
      for (std::size_t inner = 0; inner < config.shared; ++inner) {
        total += static_cast<double>(lhs[(row * config.shared) + inner]) *
                 rhs[(inner * config.cols) + col];
      }
      output[(row * config.cols) + col] = static_cast<float>(total);
    }
  }
}

void matmul_backward(const float* lhs,
                     const float* rhs,
                     const float* grad_output,
                     float* grad_lhs,
                     float* grad_rhs,
                     MatmulConfig config) {
  validate_matmul_config(config);
  require_pointer(lhs, "lhs");
  require_pointer(rhs, "rhs");
  require_pointer(grad_output, "grad_output");
  require_pointer(grad_lhs, "grad_lhs");
  require_pointer(grad_rhs, "grad_rhs");

  for (std::size_t row = 0; row < config.rows; ++row) {
    for (std::size_t inner = 0; inner < config.shared; ++inner) {
      double total = 0.0;
      for (std::size_t col = 0; col < config.cols; ++col) {
        total += static_cast<double>(grad_output[(row * config.cols) + col]) *
                 rhs[(inner * config.cols) + col];
      }
      grad_lhs[(row * config.shared) + inner] = static_cast<float>(total);
    }
  }

  for (std::size_t inner = 0; inner < config.shared; ++inner) {
    for (std::size_t col = 0; col < config.cols; ++col) {
      double total = 0.0;
      for (std::size_t row = 0; row < config.rows; ++row) {
        total += static_cast<double>(lhs[(row * config.shared) + inner]) *
                 grad_output[(row * config.cols) + col];
      }
      grad_rhs[(inner * config.cols) + col] = static_cast<float>(total);
    }
  }
}

std::vector<float> rms_norm_forward_reference(const std::vector<float>& input,
                                              const std::vector<float>& weight,
                                              RmsNormConfig config) {
  validate_rms_config(config);
  require_vector_size(input, rms_element_count(config), "input");
  require_vector_size(weight, config.width, "weight");

  std::vector<float> output(rms_element_count(config), 0.0F);
  rms_norm_forward(input.data(), weight.data(), output.data(), config);
  return output;
}

RmsNormBackwardResult rms_norm_backward_reference(
    const std::vector<float>& input,
    const std::vector<float>& weight,
    const std::vector<float>& grad_output,
    RmsNormConfig config) {
  validate_rms_config(config);
  require_vector_size(input, rms_element_count(config), "input");
  require_vector_size(weight, config.width, "weight");
  require_vector_size(grad_output, rms_element_count(config), "grad_output");

  RmsNormBackwardResult result;
  result.grad_input.assign(rms_element_count(config), 0.0F);
  result.grad_weight.assign(config.width, 0.0F);
  rms_norm_backward(input.data(),
                    weight.data(),
                    grad_output.data(),
                    result.grad_input.data(),
                    result.grad_weight.data(),
                    config);
  return result;
}

std::vector<float> matmul_forward_reference(const std::vector<float>& lhs,
                                            const std::vector<float>& rhs,
                                            MatmulConfig config) {
  validate_matmul_config(config);
  require_vector_size(lhs, matmul_lhs_count(config), "lhs");
  require_vector_size(rhs, matmul_rhs_count(config), "rhs");

  std::vector<float> output(matmul_output_count(config), 0.0F);
  matmul_forward(lhs.data(), rhs.data(), output.data(), config);
  return output;
}

MatmulBackwardResult matmul_backward_reference(
    const std::vector<float>& lhs,
    const std::vector<float>& rhs,
    const std::vector<float>& grad_output,
    MatmulConfig config) {
  validate_matmul_config(config);
  require_vector_size(lhs, matmul_lhs_count(config), "lhs");
  require_vector_size(rhs, matmul_rhs_count(config), "rhs");
  require_vector_size(grad_output, matmul_output_count(config), "grad_output");

  MatmulBackwardResult result;
  result.grad_lhs.assign(matmul_lhs_count(config), 0.0F);
  result.grad_rhs.assign(matmul_rhs_count(config), 0.0F);
  matmul_backward(lhs.data(),
                  rhs.data(),
                  grad_output.data(),
                  result.grad_lhs.data(),
                  result.grad_rhs.data(),
                  config);
  return result;
}

}  // namespace polymath_native
