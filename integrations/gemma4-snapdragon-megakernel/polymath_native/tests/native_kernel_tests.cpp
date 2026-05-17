#include "polymath_native/cpu_kernels.h"

#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {

using polymath_native::MatmulBackwardResult;
using polymath_native::MatmulConfig;
using polymath_native::RmsNormBackwardResult;
using polymath_native::RmsNormConfig;

struct OutputArray {
  std::string name;
  std::vector<float> values;
};

struct TestCaseResult {
  std::string name;
  std::vector<OutputArray> outputs;
};

RmsNormConfig rms_config() {
  return RmsNormConfig{2U, 4U, 1.0e-5F};
}

MatmulConfig matmul_config() {
  return MatmulConfig{2U, 3U, 4U};
}

std::vector<float> rms_input() {
  return {0.5F, -1.25F, 2.0F, -0.75F, -1.5F, 0.25F, 0.75F, 1.5F};
}

std::vector<float> rms_weight() {
  return {1.0F, 0.75F, -0.5F, 1.25F};
}

std::vector<float> rms_grad_output() {
  return {0.1F, -0.2F, 0.3F, -0.4F, 0.25F, -0.15F, 0.05F, 0.35F};
}

std::vector<float> matmul_lhs() {
  return {1.0F, -2.0F, 0.5F, 0.25F, 1.5F, -1.0F};
}

std::vector<float> matmul_rhs() {
  return {0.5F, -1.0F, 2.0F, 0.0F, -0.75F, 1.25F,
          -0.5F, 1.0F, 1.5F, 0.25F, -1.25F, 0.75F};
}

std::vector<float> matmul_grad_output() {
  return {0.2F, -0.1F, 0.4F, -0.3F, -0.25F, 0.5F, -0.15F, 0.35F};
}

TestCaseResult run_rmsnorm_forward() {
  return TestCaseResult{
      "rmsnorm_forward",
      {OutputArray{"output",
                   polymath_native::rms_norm_forward_reference(
                       rms_input(), rms_weight(), rms_config())}}};
}

TestCaseResult run_rmsnorm_backward() {
  const RmsNormBackwardResult result = polymath_native::rms_norm_backward_reference(
      rms_input(), rms_weight(), rms_grad_output(), rms_config());

  return TestCaseResult{
      "rmsnorm_backward",
      {OutputArray{"grad_input", result.grad_input},
       OutputArray{"grad_weight", result.grad_weight}}};
}

TestCaseResult run_matmul_forward() {
  return TestCaseResult{
      "matmul_forward",
      {OutputArray{"output",
                   polymath_native::matmul_forward_reference(
                       matmul_lhs(), matmul_rhs(), matmul_config())}}};
}

TestCaseResult run_matmul_backward() {
  const MatmulBackwardResult result = polymath_native::matmul_backward_reference(
      matmul_lhs(), matmul_rhs(), matmul_grad_output(), matmul_config());

  return TestCaseResult{
      "matmul_backward",
      {OutputArray{"grad_lhs", result.grad_lhs},
       OutputArray{"grad_rhs", result.grad_rhs}}};
}

std::vector<TestCaseResult> run_all_cases() {
  return {run_rmsnorm_forward(),
          run_rmsnorm_backward(),
          run_matmul_forward(),
          run_matmul_backward()};
}

void write_json_string(std::ostream& stream, const std::string& value) {
  stream << '"';
  for (const char character : value) {
    if (character == '"' || character == '\\') {
      stream << '\\' << character;
      continue;
    }
    if (character == '\n') {
      stream << "\\n";
      continue;
    }
    stream << character;
  }
  stream << '"';
}

void write_float_array(std::ostream& stream, const std::vector<float>& values) {
  stream << '[';
  for (std::size_t index = 0; index < values.size(); ++index) {
    if (index != 0U) {
      stream << ',';
    }
    stream << std::setprecision(10) << values[index];
  }
  stream << ']';
}

void write_outputs(std::ostream& stream, const std::vector<OutputArray>& outputs) {
  stream << '{';
  for (std::size_t index = 0; index < outputs.size(); ++index) {
    if (index != 0U) {
      stream << ',';
    }
    write_json_string(stream, outputs[index].name);
    stream << ':';
    write_float_array(stream, outputs[index].values);
  }
  stream << '}';
}

void write_case(std::ostream& stream, const TestCaseResult& test_case) {
  stream << "{\"name\":";
  write_json_string(stream, test_case.name);
  stream << ",\"backend\":\"cpu_reference\",\"outputs\":";
  write_outputs(stream, test_case.outputs);
  stream << '}';
}

void write_document(std::ostream& stream, const std::vector<TestCaseResult>& cases) {
  stream << "{\"schema_version\":1,\"suite\":\"polymath_native_cpu_reference\",";
  stream << "\"cases\":[";
  for (std::size_t index = 0; index < cases.size(); ++index) {
    if (index != 0U) {
      stream << ',';
    }
    write_case(stream, cases[index]);
  }
  stream << "],\"summary\":{\"total_cases\":" << cases.size() << "}}\n";
}

std::string parse_output_path(int argc, char** argv) {
  std::string output_path;
  for (int index = 1; index < argc; ++index) {
    const std::string argument = argv[index];
    if (argument == "--output") {
      if ((index + 1) >= argc) {
        throw std::invalid_argument("--output requires a path");
      }
      output_path = argv[index + 1];
      ++index;
      continue;
    }
    if (argument == "--help") {
      std::cout << "Usage: native_kernel_tests [--output path]\n";
      std::exit(0);
    }
    throw std::invalid_argument("unknown argument: " + argument);
  }
  return output_path;
}

}  // namespace

int main(int argc, char** argv) {
  try {
    const std::string output_path = parse_output_path(argc, argv);
    const std::vector<TestCaseResult> cases = run_all_cases();

    if (output_path.empty()) {
      write_document(std::cout, cases);
      return 0;
    }

    std::ofstream output_file(output_path);
    if (!output_file) {
      throw std::runtime_error("failed to open output path: " + output_path);
    }
    write_document(output_file, cases);
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "native_kernel_tests failed: " << error.what() << '\n';
    return 2;
  }
}
