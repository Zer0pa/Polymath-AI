#include "opencl_dynamic_runtime.h"

#include <fcntl.h>
#include <sys/stat.h>
#if defined(__ANDROID__)
#include <sys/sysmacros.h>
#endif
#include <unistd.h>

#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <iterator>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace polymath::e4b_adreno {
namespace {

constexpr std::size_t kOutputFeatures = 262'144U;
constexpr std::size_t kPackedWeightBytes = 167'772'160U;
constexpr std::size_t kScaleBytes = 524'288U;
constexpr std::size_t kInputBytes = 5'120U;
constexpr std::size_t kOutputBytes = 524'288U;
constexpr std::size_t kLocalSize = 64U;
constexpr std::size_t kRowsPerWorkgroup = 8U;
constexpr std::size_t kGlobalSize =
    (kOutputFeatures / kRowsPerWorkgroup) * kLocalSize;
constexpr const char* kBuildOptions = "-cl-std=CL3.0";
constexpr cl_uint kClKernelWorkGroupSize = 0x11B0U;

#ifndef POLYMATH_SOURCE_CLOSURE_SHA256
#error "POLYMATH_SOURCE_CLOSURE_SHA256 must bind the executable source closure"
#endif
constexpr const char* kSourceClosureSha256 = POLYMATH_SOURCE_CLOSURE_SHA256;

void require_runtime_loader_isolation() {
  if (std::getenv("LD_PRELOAD") != nullptr || std::getenv("LD_LIBRARY_PATH") != nullptr) {
    throw std::runtime_error("runtime loader environment is not isolated");
  }
  std::ifstream maps("/proc/self/maps");
  if (!maps) {
    throw std::runtime_error("cannot inspect runtime mappings");
  }
  const std::string mappings((std::istreambuf_iterator<char>(maps)),
                             std::istreambuf_iterator<char>());
  if (mappings.find("libtermux-exec.so") != std::string::npos) {
    throw std::runtime_error("Termux exec interposer is mapped in candidate runtime");
  }
}

constexpr std::array<const char*, 12> kRequiredRuntimeMappings = {
    "/vendor/lib64/libOpenCL.so",
    "/vendor/lib64/libOpenCL_adreno.so",
    "/vendor/lib64/libadreno_compiler_cl.so",
    "/vendor/lib64/libadreno_utils.so",
    "/system/lib64/libvndksupport.so",
    "/apex/com.android.runtime/lib64/bionic/libdl_android.so",
    "/system/lib64/liblog.so",
    "/system/lib64/libc++.so",
    "/apex/com.android.runtime/lib64/bionic/libc.so",
    "/apex/com.android.runtime/lib64/bionic/libdl.so",
    "/apex/com.android.runtime/lib64/bionic/libm.so",
    "/data/data/com.termux/files/usr/lib/libc++_shared.so",
};

bool has_exact_runtime_mapping(const std::string& expected_path) {
  struct stat expected_metadata {};
  if (stat(expected_path.c_str(), &expected_metadata) != 0 ||
      !S_ISREG(expected_metadata.st_mode) || expected_metadata.st_nlink != 1) {
    throw std::runtime_error("required runtime file identity is unsafe: " +
                             expected_path);
  }
  std::ifstream maps("/proc/self/maps");
  if (!maps) {
    throw std::runtime_error("cannot inspect runtime library mappings");
  }
  std::string line;
  bool observed = false;
  while (std::getline(maps, line)) {
    std::istringstream fields(line);
    std::string address_range;
    std::string permissions;
    std::string offset;
    std::string device;
    std::string inode;
    if (!(fields >> address_range >> permissions >> offset >> device >> inode)) {
      continue;
    }
    std::string mapped_path;
    std::getline(fields, mapped_path);
    const std::size_t first = mapped_path.find_first_not_of(' ');
    if (first == std::string::npos || mapped_path.substr(first) != expected_path) {
      continue;
    }
#if defined(__ANDROID__)
    const std::size_t separator = device.find(':');
    if (separator == std::string::npos) {
      throw std::runtime_error("required runtime mapping device is invalid: " +
                               expected_path);
    }
    const std::string major_component = device.substr(0U, separator);
    const std::string minor_component = device.substr(separator + 1U);
    std::size_t major_consumed = 0U;
    std::size_t minor_consumed = 0U;
    const unsigned long observed_major =
        std::stoul(major_component, &major_consumed, 16);
    const unsigned long observed_minor =
        std::stoul(minor_component, &minor_consumed, 16);
    if (major_consumed != major_component.size() ||
        minor_consumed != minor_component.size() ||
        observed_major != static_cast<unsigned long>(major(expected_metadata.st_dev)) ||
        observed_minor != static_cast<unsigned long>(minor(expected_metadata.st_dev)) ||
        inode != std::to_string(static_cast<std::uint64_t>(expected_metadata.st_ino))) {
      throw std::runtime_error("required runtime mapping inode drifted: " +
                               expected_path);
    }
#else
    (void)device;
    (void)inode;
#endif
    observed = true;
  }
  return observed;
}

void require_runtime_library_mappings() {
  for (const char* path : kRequiredRuntimeMappings) {
    if (!has_exact_runtime_mapping(path)) {
      throw std::runtime_error(std::string("required runtime mapping absent: ") + path);
    }
  }
}

bool is_lower_sha256(const std::string& value) {
  if (value.size() != 64U) {
    return false;
  }
  for (const char character : value) {
    if (!((character >= '0' && character <= '9') ||
          (character >= 'a' && character <= 'f'))) {
      return false;
    }
  }
  return true;
}

constexpr const char* kKernelSource = R"CLC(
#pragma OPENCL EXTENSION cl_qcom_bfloat16_product : enable
#pragma OPENCL FP_CONTRACT OFF

#define INPUT_FEATURES 2560u
#define PACKED_BYTES_PER_ROW 640u
#define ROWS_PER_WORKGROUP 8u
#define LOCAL_SIZE 64u

inline float bf16_to_f32(const ushort bits) {
  return as_float(((uint)bits) << 16);
}

inline ushort f32_to_bf16_rne(const float value) {
  uint bits = as_uint(value);
  uint exponent = bits & 0x7f800000u;
  uint mantissa = bits & 0x007fffffu;
  if (exponent == 0x7f800000u && mantissa != 0u) {
    return (ushort)((bits >> 16) | 0x0040u);
  }
  uint rounded = bits + 0x00007fffu + ((bits >> 16) & 1u);
  return (ushort)(rounded >> 16);
}

inline ushort dequantized_weight_bf16(const ushort scale_bits,
                                      const uint unsigned_code) {
  float scale = bf16_to_f32(scale_bits);
  float signed_code = (float)((int)unsigned_code - 2);
  return f32_to_bf16_rne(signed_code * scale);
}

__kernel void e4b_intrinsic_contract_probe(__global uint* restrict observed) {
  if (get_global_id(0) != 0u) {
    return;
  }
  observed[0] = as_uint(qcom_mad32_bf16((ushort)0x3f80u, (ushort)0x4000u, 3.0f));
  observed[1] = as_uint(qcom_mad32_bf16((ushort)0xbf80u, (ushort)0x4000u, 0.5f));
  observed[2] = as_uint(qcom_mad32_bf16((ushort)0x3fc0u, (ushort)0x4020u, 0.25f));
  observed[3] = as_uint(qcom_mad32_bf16((ushort)0x3f81u, (ushort)0x3f81u, 0.0f));
  observed[4] = (uint)f32_to_bf16_rne(as_float(0x3f808000u));
  observed[5] = (uint)f32_to_bf16_rne(as_float(0x3f818000u));
}

__attribute__((reqd_work_group_size(64, 1, 1)))
__kernel void e4b_direct_packed_int2_lm_head(
    __global const uchar* restrict packed_weight,
    __global const ushort* restrict row_scale_bf16,
    __global const ushort* restrict input_bf16,
    __global ushort* restrict output_bf16) {
  const uint lane = get_local_id(0);
  const uint row_base = get_group_id(0) * ROWS_PER_WORKGROUP;
  __local ushort input_tile[INPUT_FEATURES];
  __local ushort weight_lut[4u];
  __local float reduction[LOCAL_SIZE];

  for (uint column = lane; column < INPUT_FEATURES; column += LOCAL_SIZE) {
    input_tile[column] = input_bf16[column];
  }
  barrier(CLK_LOCAL_MEM_FENCE);

  for (uint row_in_group = 0u; row_in_group < ROWS_PER_WORKGROUP; ++row_in_group) {
    const uint row = row_base + row_in_group;
    if (lane == 0u) {
      const ushort scale = row_scale_bf16[row];
      weight_lut[0u] = dequantized_weight_bf16(scale, 0u);
      weight_lut[1u] = dequantized_weight_bf16(scale, 1u);
      weight_lut[2u] = dequantized_weight_bf16(scale, 2u);
      weight_lut[3u] = dequantized_weight_bf16(scale, 3u);
    }
    barrier(CLK_LOCAL_MEM_FENCE);

    float acc0 = 0.0f;
    float acc1 = 0.0f;
    float acc2 = 0.0f;
    float acc3 = 0.0f;
    for (uint packed_column = lane; packed_column < PACKED_BYTES_PER_ROW;
         packed_column += LOCAL_SIZE) {
      const uchar packed =
          packed_weight[row * PACKED_BYTES_PER_ROW + packed_column];
      const uint input_base = packed_column << 2;
      acc0 = qcom_mad32_bf16(input_tile[input_base + 0u],
                             weight_lut[(uint)(packed & (uchar)3u)], acc0);
      acc1 = qcom_mad32_bf16(input_tile[input_base + 1u],
                             weight_lut[(uint)((packed >> 2) & (uchar)3u)], acc1);
      acc2 = qcom_mad32_bf16(input_tile[input_base + 2u],
                             weight_lut[(uint)((packed >> 4) & (uchar)3u)], acc2);
      acc3 = qcom_mad32_bf16(input_tile[input_base + 3u],
                             weight_lut[(uint)((packed >> 6) & (uchar)3u)], acc3);
    }
    reduction[lane] = (acc0 + acc1) + (acc2 + acc3);
    barrier(CLK_LOCAL_MEM_FENCE);

    for (uint stride = LOCAL_SIZE >> 1; stride != 0u; stride >>= 1) {
      if (lane < stride) {
        reduction[lane] += reduction[lane + stride];
      }
      barrier(CLK_LOCAL_MEM_FENCE);
    }
    if (lane == 0u) {
      output_bf16[row] = f32_to_bf16_rne(reduction[0u]);
    }
    barrier(CLK_LOCAL_MEM_FENCE);
  }
}
)CLC";

struct CasePaths {
  std::string case_id;
  std::string input_path;
  std::array<std::string, 2> output_paths;
};

struct Arguments {
  std::string packed_weight_path;
  std::string scale_bf16_path;
  std::string summary_path;
  std::string custody_challenge;
  std::vector<CasePaths> cases;
  bool probe_contract = false;
};

struct CaseTiming {
  std::string case_id;
  std::array<std::uint64_t, 2> kernel_elapsed_ns{};
  bool replay_byte_identical = false;
};

Arguments parse_arguments(int argc, char** argv) {
  Arguments result;
  for (int index = 1; index < argc;) {
    const std::string option = argv[index++];
    auto require_value = [&]() -> std::string {
      if (index >= argc) {
        throw std::runtime_error("missing value for " + option);
      }
      return argv[index++];
    };
    if (option == "--probe-contract") {
      result.probe_contract = true;
      result.summary_path = require_value();
    } else if (option == "--custody-challenge") {
      result.custody_challenge = require_value();
    } else if (option == "--packed-weight") {
      result.packed_weight_path = require_value();
    } else if (option == "--scale-bf16") {
      result.scale_bf16_path = require_value();
    } else if (option == "--summary") {
      result.summary_path = require_value();
    } else if (option == "--case") {
      CasePaths value;
      value.case_id = require_value();
      value.input_path = require_value();
      value.output_paths[0] = require_value();
      value.output_paths[1] = require_value();
      result.cases.push_back(std::move(value));
    } else {
      throw std::runtime_error("unknown argument: " + option);
    }
  }
  if (result.probe_contract) {
    if (result.summary_path.empty() ||
        !is_lower_sha256(result.custody_challenge) ||
        !result.packed_weight_path.empty() || !result.scale_bf16_path.empty() ||
        !result.cases.empty()) {
      throw std::runtime_error(
          "probe-contract requires only its output path and custody challenge");
    }
    return result;
  }
  if (!result.custody_challenge.empty() || result.packed_weight_path.empty() ||
      result.scale_bf16_path.empty() ||
      result.summary_path.empty() || result.cases.size() != 4U) {
    throw std::runtime_error("model, scale, summary, and exactly four cases are required");
  }
  return result;
}

template <typename Value>
std::vector<Value> read_exact_file(const std::string& path, std::size_t byte_count) {
  if (byte_count % sizeof(Value) != 0U) {
    throw std::runtime_error("typed read byte count is misaligned");
  }
  struct stat metadata {};
  if (lstat(path.c_str(), &metadata) != 0 || !S_ISREG(metadata.st_mode) ||
      metadata.st_nlink != 1 || static_cast<std::uint64_t>(metadata.st_size) != byte_count) {
    throw std::runtime_error("unsafe file or byte-count mismatch: " + path);
  }
  std::ifstream input(path, std::ios::binary);
  if (!input) {
    throw std::runtime_error("cannot open: " + path);
  }
  std::vector<Value> result(byte_count / sizeof(Value));
  input.read(reinterpret_cast<char*>(result.data()),
             static_cast<std::streamsize>(byte_count));
  if (!input || input.peek() != std::char_traits<char>::eof()) {
    throw std::runtime_error("short or oversized read: " + path);
  }
  return result;
}

void write_exclusive(const std::string& path, const void* payload, std::size_t size) {
  const int descriptor =
      open(path.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC | O_NOFOLLOW, 0600);
  if (descriptor < 0) {
    throw std::runtime_error("exclusive output open failed");
  }
  const auto* bytes = static_cast<const std::uint8_t*>(payload);
  std::size_t offset = 0U;
  try {
    while (offset < size) {
      const ssize_t written = write(descriptor, bytes + offset, size - offset);
      if (written <= 0) {
        throw std::runtime_error("short output write");
      }
      offset += static_cast<std::size_t>(written);
    }
    if (fsync(descriptor) != 0) {
      throw std::runtime_error("output fsync failed");
    }
  } catch (...) {
    close(descriptor);
    throw;
  }
  if (close(descriptor) != 0) {
    throw std::runtime_error("output close failed");
  }
}

std::string json_string(const std::string& value) {
  std::ostringstream output;
  output << '"';
  for (const char raw_byte : value) {
    const auto byte = static_cast<unsigned char>(raw_byte);
    switch (byte) {
      case '"':
        output << "\\\"";
        break;
      case '\\':
        output << "\\\\";
        break;
      case '\b':
        output << "\\b";
        break;
      case '\f':
        output << "\\f";
        break;
      case '\n':
        output << "\\n";
        break;
      case '\r':
        output << "\\r";
        break;
      case '\t':
        output << "\\t";
        break;
      default:
        if (byte < 0x20U) {
          constexpr char kHex[] = "0123456789abcdef";
          output << "\\u00" << kHex[byte >> 4U] << kHex[byte & 0x0FU];
        } else {
          output << static_cast<char>(byte);
        }
    }
  }
  output << '"';
  return output.str();
}

std::string program_build_log(const OpenClApi& api, cl_program program,
                              cl_device_id device) {
  std::size_t size = 0U;
  api.get_program_build_info(program, device, kClProgramBuildLog, 0U, nullptr, &size);
  std::vector<char> bytes(size == 0U ? 1U : size, '\0');
  if (size != 0U) {
    api.get_program_build_info(program, device, kClProgramBuildLog, size, bytes.data(),
                               nullptr);
  }
  return bytes.data();
}

std::string build_probe_contract_json(const OpenClIdentity& identity,
                                      std::size_t kernel_maximum,
                                      const std::string& custody_challenge) {
  std::ostringstream output;
  output << "{\"schema_version\":\"gemma4_e4b_adreno_opencl_execution_contract_v1\"";
  output << ",\"state\":\"passed_scope\",\"candidate_output_observed\":false";
  output << ",\"candidate_output_observation_scope\":\"this_custody_run_only\"";
  output << ",\"model_or_tensor_path_supplied\":false";
  output << ",\"model_or_tensor_access_count_measured\":false";
  output << ",\"model_or_tensor_access_observation\":";
  output << "\"not_observed_no_paths_supplied\"";
  output << ",\"model_or_tensor_access_observation_basis\":";
  output << "\"exclusive_probe_argv_and_source_bound_control_flow_no_syscall_trace\"";
  output << ",\"source_closure_sha256\":" << json_string(kSourceClosureSha256);
  output << ",\"custody_challenge\":" << json_string(custody_challenge);
  output << ",\"runtime_isolation\":{";
  output << "\"ld_preload_absent\":true,\"ld_library_path_absent\":true";
  output << ",\"termux_exec_mapping_absent\":true}";
  output << ",\"runtime_mappings_observed\":[";
  for (std::size_t index = 0; index < kRequiredRuntimeMappings.size(); ++index) {
    if (index != 0U) {
      output << ',';
    }
    output << json_string(kRequiredRuntimeMappings[index]);
  }
  output << ']';
  output << ",\"runtime_mapping_identity\":";
  output << "\"exact_path_device_inode_against_prevalidated_regular_file\"";
  output << ",\"loader\":{";
  output << "\"loaded_path\":" << json_string(identity.loaded_path);
  output << ",\"route\":" << json_string(identity.load_route) << '}';
  output << ",\"identity\":{";
  output << "\"platform_name\":" << json_string(identity.platform_name);
  output << ",\"platform_vendor\":" << json_string(identity.platform_vendor);
  output << ",\"platform_version\":" << json_string(identity.platform_version);
  output << ",\"device_name\":" << json_string(identity.device_name);
  output << ",\"device_vendor\":" << json_string(identity.device_vendor);
  output << ",\"driver_version\":" << json_string(identity.driver_version);
  output << ",\"device_version\":" << json_string(identity.device_version);
  output << ",\"opencl_c_version\":" << json_string(identity.opencl_c_version);
  output << ",\"device_extensions\":" << json_string(identity.device_extensions);
  output << ",\"address_bits\":" << identity.address_bits;
  output << ",\"endian_little\":" << (identity.endian_little ? "true" : "false") << '}';
  output << ",\"limits\":{";
  output << "\"max_work_group_size\":" << identity.max_work_group_size;
  output << ",\"production_kernel_max_work_group_size\":" << kernel_maximum;
  output << ",\"local_mem_bytes\":" << identity.local_mem_bytes;
  output << ",\"max_mem_alloc_bytes\":" << identity.max_mem_alloc_bytes << '}';
  output << ",\"compiler_probe\":{";
  output << "\"build_options\":\"-cl-std=CL3.0\",\"build_succeeded\":true";
  output << ",\"production_kernel_compiled\":true,\"local_size_64_admitted\":true";
  output << ",\"bf16_product_succeeded\":true,\"bf16_intrinsic_signature\":";
  output << "\"float_qcom_mad32_bf16_ushort_ushort_float\"";
  output << ",\"intrinsic_and_rne_runtime_conformance\":true";
  output << ",\"production_buffer_allocation_succeeded\":true";
  output << ",\"production_buffer_bytes\":[167772160,524288,5120,524288]";
  output << ",\"production_kernel_arguments_bound\":true";
  output << ",\"fast_math_enabled\":false,\"subgroup_reduce_used\":false}";
  output << ",\"arithmetic_observed_bits\":[\"0x40a00000\",\"0xbfc00000\",";
  output << "\"0x40800000\",\"0x3f820200\",\"0x00003f80\",\"0x00003f82\"]";
  output << '}';
  return output.str();
}

int probe_contract(const std::string& output_path,
                   const std::string& custody_challenge) {
  DynamicOpenClLibrary library;
  OpenClApi api(library.handle());
  BoundOpenClDevice bound = select_and_validate_device(api, library, false);
  cl_context context = nullptr;
  cl_command_queue queue = nullptr;
  cl_program program = nullptr;
  cl_kernel production_kernel = nullptr;
  cl_kernel probe_kernel = nullptr;
  cl_mem observed_buffer = nullptr;
  std::array<cl_mem, 4> production_buffers{};
  auto release = [&]() {
    if (observed_buffer != nullptr) {
      api.release_mem_object(observed_buffer);
      observed_buffer = nullptr;
    }
    for (cl_mem& buffer : production_buffers) {
      if (buffer != nullptr) {
        api.release_mem_object(buffer);
        buffer = nullptr;
      }
    }
    if (probe_kernel != nullptr) {
      api.release_kernel(probe_kernel);
      probe_kernel = nullptr;
    }
    if (production_kernel != nullptr) {
      api.release_kernel(production_kernel);
      production_kernel = nullptr;
    }
    if (program != nullptr) {
      api.release_program(program);
      program = nullptr;
    }
    if (queue != nullptr) {
      api.release_command_queue(queue);
      queue = nullptr;
    }
    if (context != nullptr) {
      api.release_context(context);
      context = nullptr;
    }
  };
  try {
    cl_int error = kClSuccess;
    context = api.create_context(nullptr, 1U, &bound.device, nullptr, nullptr, &error);
    require_cl(error, "probe clCreateContext");
    if (context == nullptr) throw std::runtime_error("probe clCreateContext returned null");
    queue = api.create_command_queue(context, bound.device, 0U, &error);
    require_cl(error, "probe clCreateCommandQueue");
    if (queue == nullptr) {
      throw std::runtime_error("probe clCreateCommandQueue returned null");
    }
    const std::size_t source_size = std::strlen(kKernelSource);
    const char* source = kKernelSource;
    program = api.create_program_with_source(context, 1U, &source, &source_size,
                                             &error);
    require_cl(error, "probe clCreateProgramWithSource");
    if (program == nullptr) {
      throw std::runtime_error("probe clCreateProgramWithSource returned null");
    }
    error = api.build_program(program, 1U, &bound.device, kBuildOptions, nullptr, nullptr);
    if (error != kClSuccess) {
      throw std::runtime_error("probe clBuildProgram failed: " +
                               program_build_log(api, program, bound.device));
    }
    production_kernel =
        api.create_kernel(program, "e4b_direct_packed_int2_lm_head", &error);
    require_cl(error, "probe clCreateKernel production");
    if (production_kernel == nullptr) {
      throw std::runtime_error("probe production kernel returned null");
    }
    std::size_t kernel_maximum = 0U;
    require_cl(api.get_kernel_work_group_info(production_kernel, bound.device,
                                              kClKernelWorkGroupSize,
                                              sizeof(kernel_maximum), &kernel_maximum,
                                              nullptr),
               "probe clGetKernelWorkGroupInfo");
    if (kernel_maximum < kLocalSize) {
      throw std::runtime_error("probe production kernel rejected local size 64");
    }
    constexpr std::array<std::size_t, 4> kProductionBufferBytes = {
        kPackedWeightBytes,
        kScaleBytes,
        kInputBytes,
        kOutputBytes,
    };
    constexpr std::array<cl_mem_flags, 4> kProductionBufferFlags = {
        kClMemReadOnly,
        kClMemReadOnly,
        kClMemReadOnly,
        kClMemWriteOnly,
    };
    for (std::size_t index = 0U; index < production_buffers.size(); ++index) {
      production_buffers[index] = api.create_buffer(
          context, kProductionBufferFlags[index], kProductionBufferBytes[index],
          nullptr, &error);
      require_cl(error, "probe clCreateBuffer production geometry");
      if (production_buffers[index] == nullptr) {
        throw std::runtime_error("probe production buffer returned null");
      }
      require_cl(api.set_kernel_arg(production_kernel, static_cast<cl_uint>(index),
                                    sizeof(production_buffers[index]),
                                    &production_buffers[index]),
                 "probe clSetKernelArg production geometry");
    }
    probe_kernel = api.create_kernel(program, "e4b_intrinsic_contract_probe", &error);
    require_cl(error, "probe clCreateKernel arithmetic");
    if (probe_kernel == nullptr) {
      throw std::runtime_error("probe arithmetic kernel returned null");
    }
    observed_buffer =
        api.create_buffer(context, kClMemReadWrite, 6U * sizeof(std::uint32_t), nullptr,
                          &error);
    require_cl(error, "probe clCreateBuffer arithmetic");
    if (observed_buffer == nullptr) {
      throw std::runtime_error("probe arithmetic buffer returned null");
    }
    require_cl(api.set_kernel_arg(probe_kernel, 0U, sizeof(observed_buffer),
                                  &observed_buffer),
               "probe clSetKernelArg arithmetic");
    const std::size_t one = 1U;
    require_cl(api.enqueue_nd_range_kernel(queue, probe_kernel, 1U, nullptr, &one, &one,
                                           0U, nullptr, nullptr),
               "probe clEnqueueNDRangeKernel arithmetic");
    std::array<std::uint32_t, 6> observed{};
    require_cl(api.enqueue_read_buffer(queue, observed_buffer, kClTrue, 0U,
                                       sizeof(observed), observed.data(), 0U, nullptr,
                                       nullptr),
               "probe clEnqueueReadBuffer arithmetic");
    constexpr std::array<std::uint32_t, 6> kExpected = {
        0x40A00000U, 0xBFC00000U, 0x40800000U,
        0x3F820200U, 0x00003F80U, 0x00003F82U,
    };
    if (observed != kExpected) {
      throw std::runtime_error("BF16 intrinsic or RNE arithmetic conformance drift");
    }
    require_runtime_library_mappings();
    const std::string contract =
        build_probe_contract_json(bound.identity, kernel_maximum, custody_challenge);
    write_exclusive(output_path, contract.data(), contract.size());
    release();
    return 0;
  } catch (...) {
    release();
    throw;
  }
}

class OpenClLmHead {
 public:
  OpenClLmHead(const std::vector<std::uint8_t>& packed_weight,
               const std::vector<std::uint16_t>& scales)
      : library_(), api_(library_.handle()), bound_(select_and_validate_device(api_, library_)) {
    create_runtime();
    build_kernel();
    create_buffers();
    upload_static_tensors(packed_weight, scales);
  }

  ~OpenClLmHead() {
    if (output_ != nullptr) api_.release_mem_object(output_);
    if (input_ != nullptr) api_.release_mem_object(input_);
    if (scales_ != nullptr) api_.release_mem_object(scales_);
    if (packed_weight_ != nullptr) api_.release_mem_object(packed_weight_);
    if (kernel_ != nullptr) api_.release_kernel(kernel_);
    if (program_ != nullptr) api_.release_program(program_);
    if (queue_ != nullptr) api_.release_command_queue(queue_);
    if (context_ != nullptr) api_.release_context(context_);
  }

  OpenClLmHead(const OpenClLmHead&) = delete;
  OpenClLmHead& operator=(const OpenClLmHead&) = delete;

  const OpenClIdentity& identity() const { return bound_.identity; }

  std::pair<std::vector<std::uint16_t>, std::uint64_t> dispatch(
      const std::vector<std::uint16_t>& input, std::uint16_t poison) {
    if (input.size() * sizeof(std::uint16_t) != kInputBytes) {
      throw std::runtime_error("input tensor byte count drift");
    }
    require_cl(api_.enqueue_write_buffer(queue_, input_, kClTrue, 0U, kInputBytes,
                                         input.data(), 0U, nullptr, nullptr),
               "clEnqueueWriteBuffer input");
    std::vector<std::uint16_t> output(kOutputFeatures, poison);
    require_cl(api_.enqueue_write_buffer(queue_, output_, kClTrue, 0U, kOutputBytes,
                                         output.data(), 0U, nullptr, nullptr),
               "clEnqueueWriteBuffer output poison");
    cl_event event = nullptr;
    require_cl(api_.enqueue_nd_range_kernel(queue_, kernel_, 1U, nullptr, &kGlobalSize,
                                            &kLocalSize, 0U, nullptr, &event),
               "clEnqueueNDRangeKernel");
    require_cl(api_.enqueue_read_buffer(queue_, output_, kClTrue, 0U, kOutputBytes,
                                        output.data(), 0U, nullptr, nullptr),
               "clEnqueueReadBuffer output");
    std::uint64_t started = 0U;
    std::uint64_t ended = 0U;
    require_cl(api_.get_event_profiling_info(event, kClProfilingCommandStart,
                                             sizeof(started), &started, nullptr),
               "clGetEventProfilingInfo start");
    require_cl(api_.get_event_profiling_info(event, kClProfilingCommandEnd, sizeof(ended),
                                             &ended, nullptr),
               "clGetEventProfilingInfo end");
    api_.release_event(event);
    if (ended < started) {
      throw std::runtime_error("OpenCL event clock regressed");
    }
    return {std::move(output), ended - started};
  }

 private:
  void create_runtime() {
    cl_int error = kClSuccess;
    context_ = api_.create_context(nullptr, 1U, &bound_.device, nullptr, nullptr, &error);
    require_cl(error, "clCreateContext");
    if (context_ == nullptr) throw std::runtime_error("clCreateContext returned null");
    queue_ = api_.create_command_queue(context_, bound_.device, kClQueueProfilingEnable,
                                       &error);
    require_cl(error, "clCreateCommandQueue");
    if (queue_ == nullptr) throw std::runtime_error("clCreateCommandQueue returned null");
  }

  void build_kernel() {
    cl_int error = kClSuccess;
    const std::size_t source_size = std::strlen(kKernelSource);
    const char* source = kKernelSource;
    program_ = api_.create_program_with_source(context_, 1U, &source, &source_size,
                                               &error);
    require_cl(error, "clCreateProgramWithSource");
    error = api_.build_program(program_, 1U, &bound_.device, kBuildOptions, nullptr, nullptr);
    if (error != kClSuccess) {
      throw std::runtime_error("clBuildProgram failed: " +
                               program_build_log(api_, program_, bound_.device));
    }
    require_runtime_library_mappings();
    kernel_ = api_.create_kernel(program_, "e4b_direct_packed_int2_lm_head", &error);
    require_cl(error, "clCreateKernel");
    std::size_t maximum = 0U;
    require_cl(api_.get_kernel_work_group_info(kernel_, bound_.device,
                                               kClKernelWorkGroupSize, sizeof(maximum),
                                               &maximum, nullptr),
               "clGetKernelWorkGroupInfo");
    if (maximum < kLocalSize) {
      throw std::runtime_error("compiled kernel rejected local size 64");
    }
  }

  cl_mem create_buffer(cl_mem_flags flags, std::size_t bytes, const char* label) {
    cl_int error = kClSuccess;
    cl_mem result = api_.create_buffer(context_, flags, bytes, nullptr, &error);
    require_cl(error, label);
    if (result == nullptr) throw std::runtime_error(std::string(label) + " returned null");
    return result;
  }

  void create_buffers() {
    packed_weight_ = create_buffer(kClMemReadOnly, kPackedWeightBytes,
                                   "clCreateBuffer packed weight");
    scales_ = create_buffer(kClMemReadOnly, kScaleBytes, "clCreateBuffer scales");
    input_ = create_buffer(kClMemReadOnly, kInputBytes, "clCreateBuffer input");
    output_ = create_buffer(kClMemWriteOnly, kOutputBytes, "clCreateBuffer output");
    require_cl(api_.set_kernel_arg(kernel_, 0U, sizeof(packed_weight_), &packed_weight_),
               "clSetKernelArg packed weight");
    require_cl(api_.set_kernel_arg(kernel_, 1U, sizeof(scales_), &scales_),
               "clSetKernelArg scales");
    require_cl(api_.set_kernel_arg(kernel_, 2U, sizeof(input_), &input_),
               "clSetKernelArg input");
    require_cl(api_.set_kernel_arg(kernel_, 3U, sizeof(output_), &output_),
               "clSetKernelArg output");
  }

  void upload_static_tensors(const std::vector<std::uint8_t>& packed_weight,
                             const std::vector<std::uint16_t>& scales) {
    if (packed_weight.size() != kPackedWeightBytes ||
        scales.size() * sizeof(std::uint16_t) != kScaleBytes) {
      throw std::runtime_error("static tensor byte count drift");
    }
    require_cl(api_.enqueue_write_buffer(queue_, packed_weight_, kClTrue, 0U,
                                         kPackedWeightBytes, packed_weight.data(), 0U,
                                         nullptr, nullptr),
               "clEnqueueWriteBuffer packed weight");
    require_cl(api_.enqueue_write_buffer(queue_, scales_, kClTrue, 0U, kScaleBytes,
                                         scales.data(), 0U, nullptr, nullptr),
               "clEnqueueWriteBuffer scales");
    require_cl(api_.finish(queue_), "clFinish static residency");
  }

  DynamicOpenClLibrary library_;
  OpenClApi api_;
  BoundOpenClDevice bound_;
  cl_context context_ = nullptr;
  cl_command_queue queue_ = nullptr;
  cl_program program_ = nullptr;
  cl_kernel kernel_ = nullptr;
  cl_mem packed_weight_ = nullptr;
  cl_mem scales_ = nullptr;
  cl_mem input_ = nullptr;
  cl_mem output_ = nullptr;
};

std::string build_summary(const OpenClIdentity& identity,
                          const std::vector<CaseTiming>& cases) {
  bool all_equal = true;
  std::ostringstream output;
  output << "{\"schema_version\":\"gemma4_e4b_adreno_int2_native_summary_v1\"";
  output << ",\"status\":\"completed_scope\"";
  output << ",\"candidate_id\":\"adreno_opencl_direct_packed_w2_scalar_bf16_product_fp32_tree_bf16_rne_v1\"";
  output << ",\"source_closure_sha256\":" << json_string(kSourceClosureSha256);
  output << ",\"build_options\":" << json_string(kBuildOptions);
  output << ",\"runtime\":{";
  output << "\"loaded_path\":" << json_string(identity.loaded_path);
  output << ",\"load_route\":" << json_string(identity.load_route);
  output << ",\"platform_name\":" << json_string(identity.platform_name);
  output << ",\"platform_vendor\":" << json_string(identity.platform_vendor);
  output << ",\"platform_version\":" << json_string(identity.platform_version);
  output << ",\"device_name\":" << json_string(identity.device_name);
  output << ",\"device_vendor\":" << json_string(identity.device_vendor);
  output << ",\"driver_version\":" << json_string(identity.driver_version);
  output << ",\"device_version\":" << json_string(identity.device_version);
  output << ",\"opencl_c_version\":" << json_string(identity.opencl_c_version);
  output << "}";
  output << ",\"lifecycle\":{";
  output << "\"process_count\":1,\"context_count\":1,\"program_build_count\":1";
  output << ",\"packed_weight_upload_count\":1,\"scale_upload_count\":1";
  output << ",\"authority_case_count\":3,\"sentinel_case_count\":1";
  output << ",\"replays_per_case\":2,\"dispatch_count\":8}";
  output << ",\"kernel\":{";
  output << "\"local_size\":64,\"rows_per_workgroup\":8,\"global_size\":"
         << kGlobalSize;
  output << ",\"qcom_mad32_bf16_scalar_calls_per_output\":2560";
  output << ",\"dense_weight_expansion\":false,\"explicit_bf16_rne_output\":true}";
  output << ",\"cases\":[";
  for (std::size_t index = 0U; index < cases.size(); ++index) {
    if (index != 0U) output << ',';
    const CaseTiming& item = cases[index];
    all_equal = all_equal && item.replay_byte_identical;
    output << "{\"case_id\":" << json_string(item.case_id);
    output << ",\"kernel_elapsed_ns\":[" << item.kernel_elapsed_ns[0] << ','
           << item.kernel_elapsed_ns[1] << ']';
    output << ",\"replay_byte_identical\":"
           << (item.replay_byte_identical ? "true" : "false") << '}';
  }
  output << ']';
  output << ",\"all_replays_byte_identical\":" << (all_equal ? "true" : "false");
  output << '}';
  return output.str();
}

int run(const Arguments& arguments) {
  const std::vector<std::uint8_t> packed_weight =
      read_exact_file<std::uint8_t>(arguments.packed_weight_path, kPackedWeightBytes);
  const std::vector<std::uint16_t> scales =
      read_exact_file<std::uint16_t>(arguments.scale_bf16_path, kScaleBytes);
  OpenClLmHead runner(packed_weight, scales);
  std::vector<CaseTiming> timings;
  timings.reserve(arguments.cases.size());
  bool all_equal = true;
  for (const CasePaths& item : arguments.cases) {
    const std::vector<std::uint16_t> input =
        read_exact_file<std::uint16_t>(item.input_path, kInputBytes);
    std::array<std::vector<std::uint16_t>, 2> outputs;
    CaseTiming timing;
    timing.case_id = item.case_id;
    for (std::size_t replay = 0U; replay < outputs.size(); ++replay) {
      auto result = runner.dispatch(input, replay == 0U ? 0x7FC1U : 0xFFC1U);
      outputs[replay] = std::move(result.first);
      timing.kernel_elapsed_ns[replay] = result.second;
      write_exclusive(item.output_paths[replay], outputs[replay].data(), kOutputBytes);
    }
    timing.replay_byte_identical = outputs[0] == outputs[1];
    all_equal = all_equal && timing.replay_byte_identical;
    timings.push_back(std::move(timing));
  }
  const std::string summary = build_summary(runner.identity(), timings);
  write_exclusive(arguments.summary_path, summary.data(), summary.size());
  return all_equal ? 0 : 2;
}

}  // namespace
}  // namespace polymath::e4b_adreno

int main(int argc, char** argv) {
  try {
    polymath::e4b_adreno::require_runtime_loader_isolation();
    const polymath::e4b_adreno::Arguments arguments =
        polymath::e4b_adreno::parse_arguments(argc, argv);
    if (arguments.probe_contract) {
      return polymath::e4b_adreno::probe_contract(arguments.summary_path,
                                                  arguments.custody_challenge);
    }
    return polymath::e4b_adreno::run(arguments);
  } catch (const std::exception& error) {
    std::cerr << "e4b_adreno_int2_lm_head: " << error.what() << '\n';
    return 3;
  }
}
