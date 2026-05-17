#include <exception>
#include <iostream>
#include <string>

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
      << "\n"
      << "Current authority gates: Gemma 4 E4B layer forward-only and stack\n"
      << "forward-only on REDMAGIC SM8750 Adreno via OpenCL, p50 cosine >= 0.99\n"
      << "vs RunPod PyTorch.\n"
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
      throw std::invalid_argument("unknown argument: " + argument);
    }
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "gemma4_layer_runner failed: " << error.what() << '\n';
    return 2;
  }
}
