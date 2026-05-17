#include <exception>
#include <cstdlib>
#include <cstdint>
#include <iostream>
#include <string>

#include "polymath/gemma4/adapter_training.h"
#include "polymath/gemma4/data_pipeline.h"
#include "polymath/gemma4/device_backend.h"
#include "polymath/gemma4/json_writer.h"
#include "polymath/gemma4/layer_pack_reader.h"
#include "polymath/gemma4/opencl_layer_runner.h"

namespace {

void print_help() {
  std::cout
      << "Usage: gemma4_layer_runner [--help] [--probe] [--validate-pack DIR]\n"
      << "                           [--run-opencl PACK_DIR OUT_DIR]\n"
      << "                           [--run-opencl-stack PACK0 PACK1 OUT_DIR]\n"
      << "                           [--run-adapter-grad FIXTURE CHECKPOINT OUT_DIR]\n"
      << "                           [--run-adapter-sgd FIXTURE CHECKPOINT OUT_DIR LR]\n"
      << "                           [--run-g8-distill TOKEN_CACHE ASSETS PACK0 PACK1 CHECKPOINT OUT_DIR LR]\n"
      << "                           [--tokenize-pack TOKENIZER_DIR RAW_TEXT OUT_DIR SEQ N URL]\n"
      << "\n"
      << "Current authority gates: Gemma 4 E4B layer forward-only and stack\n"
      << "forward-only plus rank-4 adapter backward/update on REDMAGIC SM8750\n"
      << "Adreno via OpenCL, compared against RunPod PyTorch.\n"
      << "\n"
      << "This runner does not claim gate success unless a full real-weight layer\n"
      << "output is produced on a GPU backend and audited externally.\n";
}

void write_pack_validation_json(const std::string& pack_dir,
                                const polymath::gemma4::LayerPackValidation& validation) {
  std::cout << "{\"schema_version\":\"gemma4_layer_pack_validation_v1\",";
  std::cout << "\"pack_dir\":";
  polymath::gemma4::write_json_string(std::cout, pack_dir);
  std::cout << ",\"status\":\"" << (validation.status.is_ok() ? "pass" : "fail") << "\"";
  if (!validation.status.is_ok()) {
    std::cout << ",\"reason\":";
    polymath::gemma4::write_json_string(std::cout, validation.status.message());
  }
  std::cout << ",\"checked_paths\":[";
  for (std::size_t index = 0; index < validation.checked_paths.size(); ++index) {
    if (index != 0U) {
      std::cout << ',';
    }
    polymath::gemma4::write_json_string(std::cout, validation.checked_paths[index]);
  }
  std::cout << "]}\n";
}

int run_validate_pack(int argc, char** argv, int index) {
  if ((index + 1) >= argc) {
    throw std::invalid_argument("--validate-pack requires a directory");
  }
  const std::string pack_dir = argv[index + 1];
  const polymath::gemma4::LayerPackReader reader;
  const polymath::gemma4::LayerPackValidation validation = reader.validate(pack_dir);
  write_pack_validation_json(pack_dir, validation);
  return validation.status.is_ok() ? 0 : 3;
}

int run_opencl(int argc, char** argv, int index) {
  if ((index + 2) >= argc) {
    throw std::invalid_argument("--run-opencl requires PACK_DIR and OUT_DIR");
  }
  const polymath::gemma4::Status status =
      polymath::gemma4::run_opencl_layer_forward(argv[index + 1], argv[index + 2]);
  if (!status.is_ok()) {
    std::cerr << status.message() << '\n';
    return 4;
  }
  return 0;
}

int run_opencl_stack(int argc, char** argv, int index) {
  if ((index + 3) >= argc) {
    throw std::invalid_argument("--run-opencl-stack requires PACK0 PACK1 and OUT_DIR");
  }
  const polymath::gemma4::Status status =
      polymath::gemma4::run_opencl_two_layer_stack(argv[index + 1], argv[index + 2],
                                                   argv[index + 3]);
  if (!status.is_ok()) {
    std::cerr << status.message() << '\n';
    return 5;
  }
  return 0;
}

int run_adapter_grad(int argc, char** argv, int index) {
  if ((index + 3) >= argc) {
    throw std::invalid_argument(
        "--run-adapter-grad requires FIXTURE, CHECKPOINT, and OUT_DIR");
  }
  const polymath::gemma4::Status status =
      polymath::gemma4::run_opencl_adapter_gradient_step(argv[index + 1],
                                                         argv[index + 2],
                                                         argv[index + 3]);
  if (!status.is_ok()) {
    std::cerr << status.message() << '\n';
    return 6;
  }
  return 0;
}

int run_adapter_sgd(int argc, char** argv, int index) {
  if ((index + 4) >= argc) {
    throw std::invalid_argument(
        "--run-adapter-sgd requires FIXTURE, CHECKPOINT, OUT_DIR, and LR");
  }
  char* end = nullptr;
  const float learning_rate = std::strtof(argv[index + 4], &end);
  if (end == argv[index + 4] || *end != '\0') {
    throw std::invalid_argument("--run-adapter-sgd LR must be a float");
  }
  const polymath::gemma4::Status status =
      polymath::gemma4::run_opencl_adapter_sgd_update(argv[index + 1],
                                                      argv[index + 2],
                                                      argv[index + 3],
                                                      learning_rate);
  if (!status.is_ok()) {
    std::cerr << status.message() << '\n';
    return 7;
  }
  return 0;
}

int run_tokenize_pack(int argc, char** argv, int index) {
  if ((index + 6) >= argc) {
    throw std::invalid_argument(
        "--tokenize-pack requires TOKENIZER_DIR, RAW_TEXT, OUT_DIR, SEQ, N, and URL");
  }
  const auto sequence_length =
      static_cast<std::uint32_t>(std::stoul(argv[index + 4]));
  const auto max_sequences =
      static_cast<std::uint32_t>(std::stoul(argv[index + 5]));
  const polymath::gemma4::Status status =
      polymath::gemma4::run_tokenize_pack(argv[index + 1], argv[index + 2],
                                          argv[index + 3], sequence_length,
                                          max_sequences, argv[index + 6]);
  if (!status.is_ok()) {
    std::cerr << status.message() << '\n';
    return 8;
  }
  return 0;
}

int run_g8_distill(int argc, char** argv, int index) {
  if ((index + 7) >= argc) {
    throw std::invalid_argument(
        "--run-g8-distill requires TOKEN_CACHE, ASSETS, PACK0, PACK1, CHECKPOINT, OUT_DIR, and LR");
  }
  char* end = nullptr;
  const float learning_rate = std::strtof(argv[index + 7], &end);
  if (end == argv[index + 7] || *end != '\0') {
    throw std::invalid_argument("--run-g8-distill LR must be a float");
  }
  const polymath::gemma4::Status status =
      polymath::gemma4::run_opencl_streamed_distill_update(
          argv[index + 1], argv[index + 2], argv[index + 3], argv[index + 4],
          argv[index + 5], argv[index + 6], learning_rate);
  if (!status.is_ok()) {
    std::cerr << status.message() << '\n';
    return 9;
  }
  return 0;
}

}  // namespace

int main(int argc, char** argv) {
  try {
    if (argc == 1) {
      print_help();
      return 0;
    }

    for (int index = 1; index < argc; ++index) {
      const std::string argument = argv[index];
      if (argument == "--help") {
        print_help();
        return 0;
      }
      if (argument == "--probe") {
        const polymath::gemma4::CpuDebugBackend backend;
        polymath::gemma4::write_device_probe_json(
            backend.probe(), std::cout);
        return 0;
      }
      if (argument == "--validate-pack") {
        return run_validate_pack(argc, argv, index);
      }
      if (argument == "--run-opencl") {
        return run_opencl(argc, argv, index);
      }
      if (argument == "--run-opencl-stack") {
        return run_opencl_stack(argc, argv, index);
      }
      if (argument == "--run-adapter-grad") {
        return run_adapter_grad(argc, argv, index);
      }
      if (argument == "--run-adapter-sgd") {
        return run_adapter_sgd(argc, argv, index);
      }
      if (argument == "--run-g8-distill") {
        return run_g8_distill(argc, argv, index);
      }
      if (argument == "--tokenize-pack") {
        return run_tokenize_pack(argc, argv, index);
      }
      throw std::invalid_argument("unknown argument: " + argument);
    }
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "gemma4_layer_runner failed: " << error.what() << '\n';
    return 2;
  }
}
