#include "polymath/gemma4/opencl_layer_runner.h"

#include <dlfcn.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/types.h>

#include <chrono>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "polymath/gemma4/adapter_training.h"
#include "polymath/gemma4/json_writer.h"
#include "polymath/gemma4/sha256.h"

namespace polymath::gemma4 {
namespace {

using cl_bool = std::uint32_t;
using cl_command_queue = void*;
using cl_context = void*;
using cl_context_properties = intptr_t;
using cl_device_id = void*;
using cl_device_type = std::uint64_t;
using cl_event = void*;
using cl_int = int;
using cl_kernel = void*;
using cl_mem = void*;
using cl_mem_flags = std::uint64_t;
using cl_platform_id = void*;
using cl_program = void*;
using cl_uint = std::uint32_t;

constexpr cl_int kClSuccess = 0;
constexpr cl_bool kClTrue = 1;
constexpr cl_device_type kClDeviceTypeGpu = 1ULL << 2U;
constexpr cl_mem_flags kClMemReadWrite = 1ULL << 0U;
constexpr cl_mem_flags kClMemCopyHostPtr = 1ULL << 5U;
constexpr cl_uint kClProgramBuildLog = 0x1183U;

constexpr std::uint32_t kCases = 8U;
constexpr std::uint32_t kSequence = 128U;
constexpr std::uint32_t kTokens = kCases * kSequence;
constexpr std::uint32_t kHidden = 2560U;
constexpr std::uint32_t kSmallInput = 256U;
constexpr std::uint32_t kIntermediate = 10240U;
constexpr std::uint32_t kQueryHeads = 8U;
constexpr std::uint32_t kKeyValueHeads = 2U;
constexpr std::uint32_t kHeadDim = 256U;
constexpr std::uint32_t kAdapterRank = 4U;
constexpr float kRmsEpsilon = 1.0e-6F;
constexpr float kAdapterScale = 1.0F / static_cast<float>(kAdapterRank);

template <typename Function>
Function resolve_symbol(void* library, const char* name) {
  void* symbol = dlsym(library, name);
  if (symbol == nullptr) {
    throw std::runtime_error(std::string("OpenCL missing symbol: ") + name);
  }
  return reinterpret_cast<Function>(symbol);
}

struct OpenClApi {
  using Notify = void (*)(const char*, const void*, std::size_t, void*);
  using GetPlatformIDs = cl_int (*)(cl_uint, cl_platform_id*, cl_uint*);
  using GetDeviceIDs = cl_int (*)(cl_platform_id, cl_device_type, cl_uint,
                                  cl_device_id*, cl_uint*);
  using CreateContext = cl_context (*)(const cl_context_properties*, cl_uint,
                                       const cl_device_id*, Notify, void*, cl_int*);
  using CreateCommandQueue = cl_command_queue (*)(cl_context, cl_device_id,
                                                  std::uint64_t, cl_int*);
  using CreateProgramWithSource = cl_program (*)(cl_context, cl_uint, const char**,
                                                 const std::size_t*, cl_int*);
  using BuildProgram = cl_int (*)(cl_program, cl_uint, const cl_device_id*,
                                  const char*, void (*)(cl_program, void*), void*);
  using GetProgramBuildInfo = cl_int (*)(cl_program, cl_device_id, cl_uint,
                                         std::size_t, void*, std::size_t*);
  using CreateKernel = cl_kernel (*)(cl_program, const char*, cl_int*);
  using SetKernelArg = cl_int (*)(cl_kernel, cl_uint, std::size_t, const void*);
  using CreateBuffer = cl_mem (*)(cl_context, cl_mem_flags, std::size_t, void*, cl_int*);
  using EnqueueNDRangeKernel = cl_int (*)(cl_command_queue, cl_kernel, cl_uint,
                                          const std::size_t*, const std::size_t*,
                                          const std::size_t*, cl_uint,
                                          const cl_event*, cl_event*);
  using EnqueueReadBuffer = cl_int (*)(cl_command_queue, cl_mem, cl_bool,
                                       std::size_t, std::size_t, void*, cl_uint,
                                       const cl_event*, cl_event*);
  using Finish = cl_int (*)(cl_command_queue);
  using ReleaseMemObject = cl_int (*)(cl_mem);
  using ReleaseKernel = cl_int (*)(cl_kernel);
  using ReleaseProgram = cl_int (*)(cl_program);
  using ReleaseCommandQueue = cl_int (*)(cl_command_queue);
  using ReleaseContext = cl_int (*)(cl_context);

  explicit OpenClApi(void* library)
      : get_platform_ids(resolve_symbol<GetPlatformIDs>(library, "clGetPlatformIDs")),
        get_device_ids(resolve_symbol<GetDeviceIDs>(library, "clGetDeviceIDs")),
        create_context(resolve_symbol<CreateContext>(library, "clCreateContext")),
        create_command_queue(
            resolve_symbol<CreateCommandQueue>(library, "clCreateCommandQueue")),
        create_program_with_source(resolve_symbol<CreateProgramWithSource>(
            library, "clCreateProgramWithSource")),
        build_program(resolve_symbol<BuildProgram>(library, "clBuildProgram")),
        get_program_build_info(
            resolve_symbol<GetProgramBuildInfo>(library, "clGetProgramBuildInfo")),
        create_kernel(resolve_symbol<CreateKernel>(library, "clCreateKernel")),
        set_kernel_arg(resolve_symbol<SetKernelArg>(library, "clSetKernelArg")),
        create_buffer(resolve_symbol<CreateBuffer>(library, "clCreateBuffer")),
        enqueue_nd_range_kernel(
            resolve_symbol<EnqueueNDRangeKernel>(library, "clEnqueueNDRangeKernel")),
        enqueue_read_buffer(
            resolve_symbol<EnqueueReadBuffer>(library, "clEnqueueReadBuffer")),
        finish(resolve_symbol<Finish>(library, "clFinish")),
        release_mem_object(
            resolve_symbol<ReleaseMemObject>(library, "clReleaseMemObject")),
        release_kernel(resolve_symbol<ReleaseKernel>(library, "clReleaseKernel")),
        release_program(resolve_symbol<ReleaseProgram>(library, "clReleaseProgram")),
        release_command_queue(
            resolve_symbol<ReleaseCommandQueue>(library, "clReleaseCommandQueue")),
        release_context(resolve_symbol<ReleaseContext>(library, "clReleaseContext")) {}

  GetPlatformIDs get_platform_ids;
  GetDeviceIDs get_device_ids;
  CreateContext create_context;
  CreateCommandQueue create_command_queue;
  CreateProgramWithSource create_program_with_source;
  BuildProgram build_program;
  GetProgramBuildInfo get_program_build_info;
  CreateKernel create_kernel;
  SetKernelArg set_kernel_arg;
  CreateBuffer create_buffer;
  EnqueueNDRangeKernel enqueue_nd_range_kernel;
  EnqueueReadBuffer enqueue_read_buffer;
  Finish finish;
  ReleaseMemObject release_mem_object;
  ReleaseKernel release_kernel;
  ReleaseProgram release_program;
  ReleaseCommandQueue release_command_queue;
  ReleaseContext release_context;
};

class DynamicLibrary {
 public:
  DynamicLibrary() {
    const char* candidates[] = {"libOpenCL.so", "/vendor/lib64/libOpenCL.so"};
    for (const char* candidate : candidates) {
      handle_ = dlopen(candidate, RTLD_NOW | RTLD_LOCAL);
      if (handle_ != nullptr) {
        loaded_path_ = candidate;
        return;
      }
    }
    throw std::runtime_error("unable to load libOpenCL.so");
  }

  ~DynamicLibrary() {
    if (handle_ != nullptr) {
      dlclose(handle_);
    }
  }

  DynamicLibrary(const DynamicLibrary&) = delete;
  DynamicLibrary& operator=(const DynamicLibrary&) = delete;

  void* handle() const { return handle_; }
  const std::string& loaded_path() const { return loaded_path_; }

 private:
  void* handle_ = nullptr;
  std::string loaded_path_;
};

class ClRuntime {
 public:
  explicit ClRuntime(const OpenClApi& api) : api_(api) {
    platform_ = select_platform();
    device_ = select_gpu_device(platform_);

    cl_int error = kClSuccess;
    context_ = api_.create_context(nullptr, 1U, &device_, nullptr, nullptr, &error);
    require(error, "clCreateContext");
    if (context_ == nullptr) {
      throw std::runtime_error("clCreateContext returned null context");
    }

    queue_ = api_.create_command_queue(context_, device_, 0U, &error);
    require(error, "clCreateCommandQueue");
    if (queue_ == nullptr) {
      throw std::runtime_error("clCreateCommandQueue returned null queue");
    }
  }

  ~ClRuntime() {
    for (cl_kernel kernel : kernels_) {
      api_.release_kernel(kernel);
    }
    if (program_ != nullptr) {
      api_.release_program(program_);
    }
    for (cl_mem buffer : buffers_) {
      api_.release_mem_object(buffer);
    }
    if (queue_ != nullptr) {
      api_.release_command_queue(queue_);
    }
    if (context_ != nullptr) {
      api_.release_context(context_);
    }
  }

  ClRuntime(const ClRuntime&) = delete;
  ClRuntime& operator=(const ClRuntime&) = delete;

  void build_program(const char* source) {
    cl_int error = kClSuccess;
    const char* sources[] = {source};
    program_ = api_.create_program_with_source(context_, 1U, sources, nullptr, &error);
    require(error, "clCreateProgramWithSource");
    const cl_int build_error =
        api_.build_program(program_, 1U, &device_, nullptr, nullptr, nullptr);
    if (build_error != kClSuccess) {
      throw std::runtime_error("clBuildProgram failed: " + program_build_log());
    }
  }

  cl_kernel kernel(const char* name) {
    cl_int error = kClSuccess;
    cl_kernel created = api_.create_kernel(program_, name, &error);
    require(error, std::string("clCreateKernel ") + name);
    kernels_.push_back(created);
    return created;
  }

  cl_mem buffer(std::size_t bytes) {
    cl_int error = kClSuccess;
    cl_mem created = api_.create_buffer(context_, kClMemReadWrite, bytes, nullptr, &error);
    require(error, "clCreateBuffer");
    buffers_.push_back(created);
    return created;
  }

  template <typename T>
  cl_mem buffer_from_vector(std::vector<T>& values) {
    cl_int error = kClSuccess;
    cl_mem created = api_.create_buffer(context_, kClMemReadWrite | kClMemCopyHostPtr,
                                        values.size() * sizeof(T), values.data(), &error);
    require(error, "clCreateBuffer host vector");
    buffers_.push_back(created);
    return created;
  }

  template <typename T>
  void set_arg(cl_kernel kernel, cl_uint index, const T& value) {
    require(api_.set_kernel_arg(kernel, index, sizeof(T), &value), "clSetKernelArg");
  }

  void run_1d(cl_kernel kernel, std::size_t count) {
    const std::size_t global[] = {round_up(count, 256U)};
    const std::size_t local[] = {256U};
    require(api_.enqueue_nd_range_kernel(queue_, kernel, 1U, nullptr, global, local, 0U,
                                         nullptr, nullptr),
            "clEnqueueNDRangeKernel 1D");
  }

  void run_1d_exact(cl_kernel kernel, std::size_t count) {
    const std::size_t global[] = {count};
    require(api_.enqueue_nd_range_kernel(queue_, kernel, 1U, nullptr, global, nullptr, 0U,
                                         nullptr, nullptr),
            "clEnqueueNDRangeKernel exact 1D");
  }

  void run_linear(cl_kernel kernel, std::size_t rows, std::size_t cols) {
    const std::size_t local[] = {16U, 16U};
    const std::size_t global[] = {round_up(cols, local[0]), round_up(rows, local[1])};
    require(api_.enqueue_nd_range_kernel(queue_, kernel, 2U, nullptr, global, local, 0U,
                                         nullptr, nullptr),
            "clEnqueueNDRangeKernel linear");
  }

  void finish() { require(api_.finish(queue_), "clFinish"); }

  template <typename T>
  void read_buffer(cl_mem buffer, std::vector<T>& values) {
    require(api_.enqueue_read_buffer(queue_, buffer, kClTrue, 0U,
                                     values.size() * sizeof(T), values.data(), 0U,
                                     nullptr, nullptr),
            "clEnqueueReadBuffer");
  }

 private:
  cl_platform_id select_platform() const {
    cl_uint platform_count = 0U;
    require(api_.get_platform_ids(0U, nullptr, &platform_count), "clGetPlatformIDs count");
    if (platform_count == 0U) {
      throw std::runtime_error("OpenCL reports zero platforms");
    }
    std::vector<cl_platform_id> platforms(platform_count);
    require(api_.get_platform_ids(platform_count, platforms.data(), nullptr),
            "clGetPlatformIDs list");
    return platforms.front();
  }

  cl_device_id select_gpu_device(cl_platform_id platform) const {
    cl_uint device_count = 0U;
    require(api_.get_device_ids(platform, kClDeviceTypeGpu, 0U, nullptr, &device_count),
            "clGetDeviceIDs count");
    if (device_count == 0U) {
      throw std::runtime_error("OpenCL reports zero GPU devices");
    }
    std::vector<cl_device_id> devices(device_count);
    require(api_.get_device_ids(platform, kClDeviceTypeGpu, device_count, devices.data(),
                                nullptr),
            "clGetDeviceIDs list");
    return devices.front();
  }

  std::string program_build_log() const {
    std::size_t log_size = 0U;
    api_.get_program_build_info(program_, device_, kClProgramBuildLog, 0U, nullptr,
                                &log_size);
    std::string log(log_size, '\0');
    if (log_size > 0U) {
      api_.get_program_build_info(program_, device_, kClProgramBuildLog, log_size,
                                  log.data(), nullptr);
    }
    return log;
  }

  static void require(cl_int error, const std::string& label) {
    if (error != kClSuccess) {
      throw std::runtime_error(label + " failed with OpenCL error " +
                               std::to_string(error));
    }
  }

  static std::size_t round_up(std::size_t value, std::size_t multiple) {
    return ((value + multiple - 1U) / multiple) * multiple;
  }

  const OpenClApi& api_;
  cl_platform_id platform_ = nullptr;
  cl_device_id device_ = nullptr;
  cl_context context_ = nullptr;
  cl_command_queue queue_ = nullptr;
  cl_program program_ = nullptr;
  std::vector<cl_kernel> kernels_;
  std::vector<cl_mem> buffers_;
};

struct TensorData {
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

std::string join_path(const std::string& base, const std::string& leaf) {
  if (base.empty() || base.back() == '/') {
    return base + leaf;
  }
  return base + "/" + leaf;
}

void ensure_directory(const std::string& path) {
  std::string partial;
  for (char character : path) {
    partial.push_back(character);
    if (character == '/' && partial.size() > 1U) {
      mkdir(partial.c_str(), 0755);
    }
  }
  if (!path.empty()) {
    mkdir(path.c_str(), 0755);
  }
}

std::vector<std::uint8_t> read_bytes(const std::string& path) {
  std::ifstream file(path, std::ios::binary);
  if (!file) {
    throw std::runtime_error("unable to open " + path);
  }
  file.seekg(0, std::ios::end);
  const std::streamoff size = file.tellg();
  if (size < 0) {
    throw std::runtime_error("unable to size " + path);
  }
  file.seekg(0, std::ios::beg);
  std::vector<std::uint8_t> bytes(static_cast<std::size_t>(size));
  if (!bytes.empty()) {
    file.read(reinterpret_cast<char*>(bytes.data()), size);
  }
  if (!file) {
    throw std::runtime_error("unable to read all bytes from " + path);
  }
  return bytes;
}

std::string read_text_file(const std::string& path) {
  std::ifstream file(path);
  if (!file) {
    throw std::runtime_error("unable to open " + path);
  }
  std::ostringstream buffer;
  buffer << file.rdbuf();
  return buffer.str();
}

template <typename T>
std::vector<T> read_binary_vector(const std::string& path, std::size_t expected_count) {
  const std::vector<std::uint8_t> bytes = read_bytes(path);
  const std::size_t expected_bytes = expected_count * sizeof(T);
  if (bytes.size() != expected_bytes) {
    throw std::runtime_error(path + " has " + std::to_string(bytes.size()) +
                             " bytes; expected " + std::to_string(expected_bytes));
  }
  std::vector<T> values(expected_count);
  if (!values.empty()) {
    std::memcpy(values.data(), bytes.data(), bytes.size());
  }
  return values;
}

template <typename T>
void write_binary_vector(const std::string& path, const std::vector<T>& values) {
  std::ofstream file(path, std::ios::binary);
  if (!file) {
    throw std::runtime_error("unable to create " + path);
  }
  file.write(reinterpret_cast<const char*>(values.data()),
             static_cast<std::streamsize>(values.size() * sizeof(T)));
  if (!file) {
    throw std::runtime_error("unable to write " + path);
  }
}

std::uint64_t read_little_u64(const std::uint8_t* data) {
  std::uint64_t value = 0U;
  for (std::uint32_t index = 0U; index < 8U; ++index) {
    value |= static_cast<std::uint64_t>(data[index]) << (8U * index);
  }
  return value;
}

std::uint16_t read_little_u16(const std::uint8_t* data) {
  return static_cast<std::uint16_t>(data[0]) |
         static_cast<std::uint16_t>(static_cast<std::uint16_t>(data[1]) << 8U);
}

float bf16_to_float(std::uint16_t value) {
  const std::uint32_t expanded = static_cast<std::uint32_t>(value) << 16U;
  float result = 0.0F;
  std::memcpy(&result, &expanded, sizeof(float));
  return result;
}

std::size_t parse_unsigned_after(const std::string& text, std::size_t offset) {
  while (offset < text.size() && (text[offset] < '0' || text[offset] > '9')) {
    ++offset;
  }
  if (offset == text.size()) {
    throw std::runtime_error("safetensors header missing unsigned integer");
  }
  std::size_t value = 0U;
  while (offset < text.size() && text[offset] >= '0' && text[offset] <= '9') {
    value = (value * 10U) + static_cast<std::size_t>(text[offset] - '0');
    ++offset;
  }
  return value;
}

std::pair<std::size_t, std::size_t> tensor_offsets(const std::string& header,
                                                   const std::string& name) {
  const std::size_t tensor_pos = header.find("\"" + name + "\"");
  if (tensor_pos == std::string::npos) {
    throw std::runtime_error("safetensors missing tensor " + name);
  }
  const std::size_t offsets_pos = header.find("\"data_offsets\"", tensor_pos);
  if (offsets_pos == std::string::npos) {
    throw std::runtime_error("safetensors missing offsets for " + name);
  }
  const std::size_t first = parse_unsigned_after(header, offsets_pos);
  const std::size_t comma = header.find(',', offsets_pos);
  if (comma == std::string::npos) {
    throw std::runtime_error("safetensors malformed offsets for " + name);
  }
  const std::size_t second = parse_unsigned_after(header, comma);
  if (second < first) {
    throw std::runtime_error("safetensors invalid offsets for " + name);
  }
  return {first, second};
}

std::vector<float> load_bf16_tensor(const std::vector<std::uint8_t>& file,
                                    const std::string& header,
                                    std::size_t data_base,
                                    const std::string& name,
                                    std::size_t expected_count) {
  const auto offsets = tensor_offsets(header, name);
  const std::size_t byte_count = offsets.second - offsets.first;
  const std::size_t expected_bytes = expected_count * sizeof(std::uint16_t);
  if (byte_count != expected_bytes) {
    throw std::runtime_error(name + " has " + std::to_string(byte_count) +
                             " bytes; expected " + std::to_string(expected_bytes));
  }
  if ((data_base + offsets.second) > file.size()) {
    throw std::runtime_error(name + " extends beyond safetensors file");
  }

  const std::uint8_t* tensor_data = file.data() + data_base + offsets.first;
  std::vector<float> values(expected_count);
  for (std::size_t index = 0U; index < expected_count; ++index) {
    values[index] = bf16_to_float(read_little_u16(tensor_data + (index * 2U)));
  }
  return values;
}

TensorData load_weights(const std::string& pack_dir, std::uint32_t layer_index) {
  const std::string path =
      join_path(pack_dir, "weights/layer" + std::to_string(layer_index) + ".safetensors");
  const std::vector<std::uint8_t> file = read_bytes(path);
  if (file.size() < 8U) {
    throw std::runtime_error("safetensors file too small");
  }
  const std::uint64_t header_size = read_little_u64(file.data());
  const std::size_t data_base = 8U + static_cast<std::size_t>(header_size);
  if (data_base > file.size()) {
    throw std::runtime_error("safetensors header exceeds file size");
  }
  const std::string header(reinterpret_cast<const char*>(file.data() + 8U),
                           static_cast<std::size_t>(header_size));

  TensorData weights;
  weights.input_layernorm_weight =
      load_bf16_tensor(file, header, data_base, "input_layernorm.weight", kHidden);
  weights.layer_scalar = load_bf16_tensor(file, header, data_base, "layer_scalar", 1U);
  weights.mlp_down_proj_weight = load_bf16_tensor(
      file, header, data_base, "mlp.down_proj.weight", kHidden * kIntermediate);
  weights.mlp_gate_proj_weight = load_bf16_tensor(
      file, header, data_base, "mlp.gate_proj.weight", kIntermediate * kHidden);
  weights.mlp_up_proj_weight = load_bf16_tensor(
      file, header, data_base, "mlp.up_proj.weight", kIntermediate * kHidden);
  weights.per_layer_input_gate_weight = load_bf16_tensor(
      file, header, data_base, "per_layer_input_gate.weight", kSmallInput * kHidden);
  weights.per_layer_projection_weight = load_bf16_tensor(
      file, header, data_base, "per_layer_projection.weight", kHidden * kSmallInput);
  weights.post_attention_layernorm_weight = load_bf16_tensor(
      file, header, data_base, "post_attention_layernorm.weight", kHidden);
  weights.post_feedforward_layernorm_weight = load_bf16_tensor(
      file, header, data_base, "post_feedforward_layernorm.weight", kHidden);
  weights.post_per_layer_input_norm_weight = load_bf16_tensor(
      file, header, data_base, "post_per_layer_input_norm.weight", kHidden);
  weights.pre_feedforward_layernorm_weight = load_bf16_tensor(
      file, header, data_base, "pre_feedforward_layernorm.weight", kHidden);
  weights.self_attn_k_norm_weight =
      load_bf16_tensor(file, header, data_base, "self_attn.k_norm.weight", kHeadDim);
  weights.self_attn_k_proj_weight = load_bf16_tensor(
      file, header, data_base, "self_attn.k_proj.weight", kKeyValueHeads * kHeadDim * kHidden);
  weights.self_attn_o_proj_weight = load_bf16_tensor(
      file, header, data_base, "self_attn.o_proj.weight", kHidden * kQueryHeads * kHeadDim);
  weights.self_attn_q_norm_weight =
      load_bf16_tensor(file, header, data_base, "self_attn.q_norm.weight", kHeadDim);
  weights.self_attn_q_proj_weight = load_bf16_tensor(
      file, header, data_base, "self_attn.q_proj.weight", kQueryHeads * kHeadDim * kHidden);
  weights.self_attn_v_proj_weight = load_bf16_tensor(
      file, header, data_base, "self_attn.v_proj.weight", kKeyValueHeads * kHeadDim * kHidden);
  return weights;
}

std::uint32_t parse_layer_index(const std::string& pack_dir) {
  const std::string contract = read_text_file(join_path(pack_dir, "contract.json"));
  const std::size_t field = contract.find("\"layer_index\"");
  if (field == std::string::npos) {
    return 0U;
  }
  const std::size_t colon = contract.find(':', field);
  if (colon == std::string::npos) {
    return 0U;
  }
  std::size_t cursor = colon + 1U;
  while (cursor < contract.size() && (contract[cursor] < '0' || contract[cursor] > '9')) {
    ++cursor;
  }
  std::uint32_t value = 0U;
  bool found_digit = false;
  while (cursor < contract.size() && contract[cursor] >= '0' && contract[cursor] <= '9') {
    found_digit = true;
    value = (value * 10U) + static_cast<std::uint32_t>(contract[cursor] - '0');
    ++cursor;
  }
  return found_digit ? value : 0U;
}

const char* opencl_source() {
  return R"CLC(
__kernel void rms_weighted(__global const float* input,
                           __global const float* weight,
                           __global float* output,
                           int rows,
                           int width,
                           float epsilon) {
  const int row = get_global_id(0);
  if (row >= rows) {
    return;
  }
  float sum_sq = 0.0f;
  const int base = row * width;
  for (int index = 0; index < width; ++index) {
    const float value = input[base + index];
    sum_sq += value * value;
  }
  const float scale = rsqrt((sum_sq / (float)width) + epsilon);
  for (int index = 0; index < width; ++index) {
    output[base + index] = input[base + index] * scale * weight[index];
  }
}

__kernel void rms_unweighted(__global const float* input,
                             __global float* output,
                             int rows,
                             int width,
                             float epsilon) {
  const int row = get_global_id(0);
  if (row >= rows) {
    return;
  }
  float sum_sq = 0.0f;
  const int base = row * width;
  for (int index = 0; index < width; ++index) {
    const float value = input[base + index];
    sum_sq += value * value;
  }
  const float scale = rsqrt((sum_sq / (float)width) + epsilon);
  for (int index = 0; index < width; ++index) {
    output[base + index] = input[base + index] * scale;
  }
}

__kernel void linear_tiled(__global const float* input,
                           __global const float* weight,
                           __global float* output,
                           int rows,
                           int input_width,
                           int output_width) {
  __local float tile_a[16][16];
  __local float tile_b[16][16];
  const int col = get_global_id(0);
  const int row = get_global_id(1);
  const int local_col = get_local_id(0);
  const int local_row = get_local_id(1);
  float sum = 0.0f;
  for (int tile = 0; tile < input_width; tile += 16) {
    const int input_index = tile + local_col;
    const int weight_index = tile + local_row;
    tile_a[local_row][local_col] =
        (row < rows && input_index < input_width) ? input[row * input_width + input_index] : 0.0f;
    tile_b[local_row][local_col] =
        (col < output_width && weight_index < input_width) ? weight[col * input_width + weight_index] : 0.0f;
    barrier(CLK_LOCAL_MEM_FENCE);
    for (int k = 0; k < 16; ++k) {
      sum += tile_a[local_row][k] * tile_b[k][local_col];
    }
    barrier(CLK_LOCAL_MEM_FENCE);
  }
  if (row < rows && col < output_width) {
    output[row * output_width + col] = sum;
  }
}

__kernel void add_vectors(__global const float* lhs,
                          __global const float* rhs,
                          __global float* output,
                          int count) {
  const int index = get_global_id(0);
  if (index < count) {
    output[index] = lhs[index] + rhs[index];
  }
}

__kernel void gelu_tanh_mul(__global const float* lhs,
                            __global const float* rhs,
                            __global float* output,
                            int count) {
  const int index = get_global_id(0);
  if (index >= count) {
    return;
  }
  const float x = lhs[index];
  const float inner = 0.7978845608028654f * (x + (0.044715f * x * x * x));
  const float gelu = 0.5f * x * (1.0f + tanh(inner));
  output[index] = gelu * rhs[index];
}

__kernel void rope(__global const float* input,
                   __global float* output,
                   __global const uint* position_ids,
                   int tokens,
                   int heads,
                   int head_dim) {
  const int index = get_global_id(0);
  const int total = tokens * heads * head_dim;
  if (index >= total) {
    return;
  }
  const int dim = index % head_dim;
  const int head = (index / head_dim) % heads;
  const int token = index / (head_dim * heads);
  const int half_dim = head_dim / 2;
  const int pair_dim = dim < half_dim ? dim : dim - half_dim;
  const float exponent = (2.0f * (float)pair_dim) / (float)head_dim;
  const float inv_freq = 1.0f / pow(10000.0f, exponent);
  const float angle = (float)position_ids[token] * inv_freq;
  const float c = cos(angle);
  const float s = sin(angle);
  const int base = (token * heads + head) * head_dim;
  const float x = input[base + dim];
  if (dim < half_dim) {
    output[base + dim] = (x * c) - (input[base + dim + half_dim] * s);
  } else {
    output[base + dim] = (x * c) + (input[base + dim - half_dim] * s);
  }
}

__kernel void attention_scores(__global const float* query,
                               __global const float* key,
                               __global const uchar* attention_mask,
                               __global float* scores,
                               int cases,
                               int sequence,
                               int query_heads,
                               int key_value_heads,
                               int head_dim) {
  const int index = get_global_id(0);
  const int total = cases * query_heads * sequence * sequence;
  if (index >= total) {
    return;
  }
  const int key_position = index % sequence;
  const int query_position = (index / sequence) % sequence;
  const int query_head = (index / (sequence * sequence)) % query_heads;
  const int batch = index / (sequence * sequence * query_heads);
  if (key_position > query_position || attention_mask[(batch * sequence) + key_position] == 0) {
    scores[index] = -3.4028234663852886e+38f;
    return;
  }
  const int group_size = query_heads / key_value_heads;
  const int key_head = query_head / group_size;
  const int query_token = (batch * sequence) + query_position;
  const int key_token = (batch * sequence) + key_position;
  const int query_base = (query_token * query_heads + query_head) * head_dim;
  const int key_base = (key_token * key_value_heads + key_head) * head_dim;
  float sum = 0.0f;
  for (int dim = 0; dim < head_dim; ++dim) {
    sum += query[query_base + dim] * key[key_base + dim];
  }
  scores[index] = sum;
}

__kernel void attention_values(__global const float* scores,
                               __global const float* value,
                               __global float* output,
                               int cases,
                               int sequence,
                               int query_heads,
                               int key_value_heads,
                               int head_dim) {
  const int index = get_global_id(0);
  const int total = cases * query_heads * sequence * head_dim;
  if (index >= total) {
    return;
  }
  const int dim = index % head_dim;
  const int query_head = (index / head_dim) % query_heads;
  const int query_position = (index / (head_dim * query_heads)) % sequence;
  const int batch = index / (head_dim * query_heads * sequence);
  const int score_base = ((batch * query_heads + query_head) * sequence + query_position) * sequence;
  float max_score = -3.4028234663852886e+38f;
  for (int key_position = 0; key_position < sequence; ++key_position) {
    const float score = scores[score_base + key_position];
    max_score = score > max_score ? score : max_score;
  }
  if (max_score < -3.0e38f) {
    output[index] = 0.0f;
    return;
  }
  const int group_size = query_heads / key_value_heads;
  const int value_head = query_head / group_size;
  float denominator = 0.0f;
  float numerator = 0.0f;
  for (int key_position = 0; key_position < sequence; ++key_position) {
    const float score = scores[score_base + key_position];
    const float probability = exp(score - max_score);
    const int value_token = (batch * sequence) + key_position;
    const int value_index = (value_token * key_value_heads + value_head) * head_dim + dim;
    numerator += probability * value[value_index];
    denominator += probability;
  }
  output[index] = denominator > 0.0f ? numerator / denominator : 0.0f;
}

__kernel void scale_inplace(__global float* values, float scale, int count) {
  const int index = get_global_id(0);
  if (index < count) {
    values[index] *= scale;
  }
}

__kernel void adapter_forward_z(__global const float* input,
                                __global const float* adapter_a,
                                __global float* z,
                                int tokens,
                                int hidden,
                                int rank) {
  const int index = get_global_id(0);
  const int count = tokens * rank;
  if (index >= count) {
    return;
  }
  const int r = index % rank;
  const int token = index / rank;
  float sum = 0.0f;
  for (int h = 0; h < hidden; ++h) {
    sum += input[token * hidden + h] * adapter_a[h * rank + r];
  }
  z[index] = sum;
}

__kernel void adapter_output_diff(__global const float* input,
                                  __global const float* target,
                                  __global const uchar* mask,
                                  __global const float* z,
                                  __global const float* adapter_b,
                                  __global float* diff,
                                  int tokens,
                                  int hidden,
                                  int rank,
                                  float adapter_scale) {
  const int index = get_global_id(0);
  const int count = tokens * hidden;
  if (index >= count) {
    return;
  }
  const int h = index % hidden;
  const int token = index / hidden;
  if (mask[token] == 0) {
    diff[index] = 0.0f;
    return;
  }
  float delta = 0.0f;
  for (int r = 0; r < rank; ++r) {
    delta += z[token * rank + r] * adapter_b[r * hidden + h];
  }
  const float output = input[index] + (adapter_scale * delta);
  diff[index] = output - target[index];
}

__kernel void adapter_grad_b(__global const float* z,
                             __global const float* diff,
                             __global float* grad_b,
                             int tokens,
                             int hidden,
                             int rank,
                             float adapter_scale,
                             float inv_norm) {
  const int index = get_global_id(0);
  const int count = rank * hidden;
  if (index >= count) {
    return;
  }
  const int h = index % hidden;
  const int r = index / hidden;
  float sum = 0.0f;
  for (int token = 0; token < tokens; ++token) {
    sum += z[token * rank + r] * diff[token * hidden + h];
  }
  grad_b[index] = adapter_scale * inv_norm * sum;
}

__kernel void adapter_hidden_rank_grad(__global const float* diff,
                                       __global const float* adapter_b,
                                       __global float* hidden_rank_grad,
                                       int tokens,
                                       int hidden,
                                       int rank,
                                       float adapter_scale,
                                       float inv_norm) {
  const int index = get_global_id(0);
  const int count = tokens * rank;
  if (index >= count) {
    return;
  }
  const int r = index % rank;
  const int token = index / rank;
  float sum = 0.0f;
  for (int h = 0; h < hidden; ++h) {
    sum += diff[token * hidden + h] * adapter_b[r * hidden + h];
  }
  hidden_rank_grad[index] = adapter_scale * inv_norm * sum;
}

__kernel void adapter_grad_a(__global const float* input,
                             __global const float* hidden_rank_grad,
                             __global float* grad_a,
                             int tokens,
                             int hidden,
                             int rank) {
  const int index = get_global_id(0);
  const int count = hidden * rank;
  if (index >= count) {
    return;
  }
  const int r = index % rank;
  const int h = index / rank;
  float sum = 0.0f;
  for (int token = 0; token < tokens; ++token) {
    sum += input[token * hidden + h] * hidden_rank_grad[token * rank + r];
  }
  grad_a[index] = sum;
}

__kernel void sgd_update(__global float* values,
                         __global const float* gradient,
                         float learning_rate,
                         int count) {
  const int index = get_global_id(0);
  if (index < count) {
    values[index] -= learning_rate * gradient[index];
  }
}
)CLC";
}

struct KernelSet {
  cl_kernel rms_weighted;
  cl_kernel rms_unweighted;
  cl_kernel linear_tiled;
  cl_kernel add_vectors;
  cl_kernel gelu_tanh_mul;
  cl_kernel rope;
  cl_kernel attention_scores;
  cl_kernel attention_values;
  cl_kernel scale_inplace;
  cl_kernel adapter_forward_z;
  cl_kernel adapter_output_diff;
  cl_kernel adapter_grad_b;
  cl_kernel adapter_hidden_rank_grad;
  cl_kernel adapter_grad_a;
  cl_kernel sgd_update;
};

KernelSet create_kernels(ClRuntime& runtime) {
  return {runtime.kernel("rms_weighted"),
          runtime.kernel("rms_unweighted"),
          runtime.kernel("linear_tiled"),
          runtime.kernel("add_vectors"),
          runtime.kernel("gelu_tanh_mul"),
          runtime.kernel("rope"),
          runtime.kernel("attention_scores"),
          runtime.kernel("attention_values"),
          runtime.kernel("scale_inplace"),
          runtime.kernel("adapter_forward_z"),
          runtime.kernel("adapter_output_diff"),
          runtime.kernel("adapter_grad_b"),
          runtime.kernel("adapter_hidden_rank_grad"),
          runtime.kernel("adapter_grad_a"),
          runtime.kernel("sgd_update")};
}

void dispatch_rms_weighted(ClRuntime& runtime, cl_kernel kernel, cl_mem input,
                           cl_mem weight, cl_mem output, std::int32_t rows,
                           std::int32_t width) {
  runtime.set_arg(kernel, 0U, input);
  runtime.set_arg(kernel, 1U, weight);
  runtime.set_arg(kernel, 2U, output);
  runtime.set_arg(kernel, 3U, rows);
  runtime.set_arg(kernel, 4U, width);
  runtime.set_arg(kernel, 5U, kRmsEpsilon);
  runtime.run_1d_exact(kernel, static_cast<std::size_t>(rows));
}

void dispatch_rms_unweighted(ClRuntime& runtime, cl_kernel kernel, cl_mem input,
                             cl_mem output, std::int32_t rows, std::int32_t width) {
  runtime.set_arg(kernel, 0U, input);
  runtime.set_arg(kernel, 1U, output);
  runtime.set_arg(kernel, 2U, rows);
  runtime.set_arg(kernel, 3U, width);
  runtime.set_arg(kernel, 4U, kRmsEpsilon);
  runtime.run_1d_exact(kernel, static_cast<std::size_t>(rows));
}

void dispatch_linear(ClRuntime& runtime, cl_kernel kernel, cl_mem input,
                     cl_mem weight, cl_mem output, std::int32_t rows,
                     std::int32_t input_width, std::int32_t output_width) {
  runtime.set_arg(kernel, 0U, input);
  runtime.set_arg(kernel, 1U, weight);
  runtime.set_arg(kernel, 2U, output);
  runtime.set_arg(kernel, 3U, rows);
  runtime.set_arg(kernel, 4U, input_width);
  runtime.set_arg(kernel, 5U, output_width);
  runtime.run_linear(kernel, static_cast<std::size_t>(rows),
                     static_cast<std::size_t>(output_width));
}

void dispatch_add(ClRuntime& runtime, cl_kernel kernel, cl_mem lhs, cl_mem rhs,
                  cl_mem output, std::int32_t count) {
  runtime.set_arg(kernel, 0U, lhs);
  runtime.set_arg(kernel, 1U, rhs);
  runtime.set_arg(kernel, 2U, output);
  runtime.set_arg(kernel, 3U, count);
  runtime.run_1d(kernel, static_cast<std::size_t>(count));
}

void dispatch_gelu_mul(ClRuntime& runtime, cl_kernel kernel, cl_mem lhs, cl_mem rhs,
                       cl_mem output, std::int32_t count) {
  runtime.set_arg(kernel, 0U, lhs);
  runtime.set_arg(kernel, 1U, rhs);
  runtime.set_arg(kernel, 2U, output);
  runtime.set_arg(kernel, 3U, count);
  runtime.run_1d(kernel, static_cast<std::size_t>(count));
}

void dispatch_rope(ClRuntime& runtime, cl_kernel kernel, cl_mem input, cl_mem output,
                   cl_mem position_ids, std::int32_t tokens, std::int32_t heads,
                   std::int32_t head_dim) {
  runtime.set_arg(kernel, 0U, input);
  runtime.set_arg(kernel, 1U, output);
  runtime.set_arg(kernel, 2U, position_ids);
  runtime.set_arg(kernel, 3U, tokens);
  runtime.set_arg(kernel, 4U, heads);
  runtime.set_arg(kernel, 5U, head_dim);
  runtime.run_1d(kernel, static_cast<std::size_t>(tokens * heads * head_dim));
}

void dispatch_attention_scores(ClRuntime& runtime, cl_kernel kernel, cl_mem query,
                               cl_mem key, cl_mem attention_mask, cl_mem scores) {
  const std::int32_t cases = static_cast<std::int32_t>(kCases);
  const std::int32_t sequence = static_cast<std::int32_t>(kSequence);
  const std::int32_t query_heads = static_cast<std::int32_t>(kQueryHeads);
  const std::int32_t key_value_heads = static_cast<std::int32_t>(kKeyValueHeads);
  const std::int32_t head_dim = static_cast<std::int32_t>(kHeadDim);
  runtime.set_arg(kernel, 0U, query);
  runtime.set_arg(kernel, 1U, key);
  runtime.set_arg(kernel, 2U, attention_mask);
  runtime.set_arg(kernel, 3U, scores);
  runtime.set_arg(kernel, 4U, cases);
  runtime.set_arg(kernel, 5U, sequence);
  runtime.set_arg(kernel, 6U, query_heads);
  runtime.set_arg(kernel, 7U, key_value_heads);
  runtime.set_arg(kernel, 8U, head_dim);
  runtime.run_1d(kernel, kCases * kQueryHeads * kSequence * kSequence);
}

void dispatch_attention_values(ClRuntime& runtime, cl_kernel kernel, cl_mem scores,
                               cl_mem value, cl_mem output) {
  const std::int32_t cases = static_cast<std::int32_t>(kCases);
  const std::int32_t sequence = static_cast<std::int32_t>(kSequence);
  const std::int32_t query_heads = static_cast<std::int32_t>(kQueryHeads);
  const std::int32_t key_value_heads = static_cast<std::int32_t>(kKeyValueHeads);
  const std::int32_t head_dim = static_cast<std::int32_t>(kHeadDim);
  runtime.set_arg(kernel, 0U, scores);
  runtime.set_arg(kernel, 1U, value);
  runtime.set_arg(kernel, 2U, output);
  runtime.set_arg(kernel, 3U, cases);
  runtime.set_arg(kernel, 4U, sequence);
  runtime.set_arg(kernel, 5U, query_heads);
  runtime.set_arg(kernel, 6U, key_value_heads);
  runtime.set_arg(kernel, 7U, head_dim);
  runtime.run_1d(kernel, kCases * kQueryHeads * kSequence * kHeadDim);
}

void dispatch_scale(ClRuntime& runtime, cl_kernel kernel, cl_mem values, float scale,
                    std::int32_t count) {
  runtime.set_arg(kernel, 0U, values);
  runtime.set_arg(kernel, 1U, scale);
  runtime.set_arg(kernel, 2U, count);
  runtime.run_1d(kernel, static_cast<std::size_t>(count));
}

void dispatch_adapter_forward_z(ClRuntime& runtime, cl_kernel kernel, cl_mem input,
                                cl_mem adapter_a, cl_mem z) {
  const std::int32_t tokens = static_cast<std::int32_t>(kTokens);
  const std::int32_t hidden = static_cast<std::int32_t>(kHidden);
  const std::int32_t rank = static_cast<std::int32_t>(kAdapterRank);
  runtime.set_arg(kernel, 0U, input);
  runtime.set_arg(kernel, 1U, adapter_a);
  runtime.set_arg(kernel, 2U, z);
  runtime.set_arg(kernel, 3U, tokens);
  runtime.set_arg(kernel, 4U, hidden);
  runtime.set_arg(kernel, 5U, rank);
  runtime.run_1d(kernel, kTokens * kAdapterRank);
}

void dispatch_adapter_output_diff(ClRuntime& runtime, cl_kernel kernel, cl_mem input,
                                  cl_mem target, cl_mem mask, cl_mem z,
                                  cl_mem adapter_b, cl_mem diff) {
  const std::int32_t tokens = static_cast<std::int32_t>(kTokens);
  const std::int32_t hidden = static_cast<std::int32_t>(kHidden);
  const std::int32_t rank = static_cast<std::int32_t>(kAdapterRank);
  runtime.set_arg(kernel, 0U, input);
  runtime.set_arg(kernel, 1U, target);
  runtime.set_arg(kernel, 2U, mask);
  runtime.set_arg(kernel, 3U, z);
  runtime.set_arg(kernel, 4U, adapter_b);
  runtime.set_arg(kernel, 5U, diff);
  runtime.set_arg(kernel, 6U, tokens);
  runtime.set_arg(kernel, 7U, hidden);
  runtime.set_arg(kernel, 8U, rank);
  runtime.set_arg(kernel, 9U, kAdapterScale);
  runtime.run_1d(kernel, kTokens * kHidden);
}

void dispatch_adapter_grad_b(ClRuntime& runtime, cl_kernel kernel, cl_mem z,
                             cl_mem diff, cl_mem grad_b, float inv_norm) {
  const std::int32_t tokens = static_cast<std::int32_t>(kTokens);
  const std::int32_t hidden = static_cast<std::int32_t>(kHidden);
  const std::int32_t rank = static_cast<std::int32_t>(kAdapterRank);
  runtime.set_arg(kernel, 0U, z);
  runtime.set_arg(kernel, 1U, diff);
  runtime.set_arg(kernel, 2U, grad_b);
  runtime.set_arg(kernel, 3U, tokens);
  runtime.set_arg(kernel, 4U, hidden);
  runtime.set_arg(kernel, 5U, rank);
  runtime.set_arg(kernel, 6U, kAdapterScale);
  runtime.set_arg(kernel, 7U, inv_norm);
  runtime.run_1d(kernel, kAdapterRank * kHidden);
}

void dispatch_adapter_hidden_rank_grad(ClRuntime& runtime, cl_kernel kernel, cl_mem diff,
                                       cl_mem adapter_b, cl_mem hidden_rank_grad,
                                       float inv_norm) {
  const std::int32_t tokens = static_cast<std::int32_t>(kTokens);
  const std::int32_t hidden = static_cast<std::int32_t>(kHidden);
  const std::int32_t rank = static_cast<std::int32_t>(kAdapterRank);
  runtime.set_arg(kernel, 0U, diff);
  runtime.set_arg(kernel, 1U, adapter_b);
  runtime.set_arg(kernel, 2U, hidden_rank_grad);
  runtime.set_arg(kernel, 3U, tokens);
  runtime.set_arg(kernel, 4U, hidden);
  runtime.set_arg(kernel, 5U, rank);
  runtime.set_arg(kernel, 6U, kAdapterScale);
  runtime.set_arg(kernel, 7U, inv_norm);
  runtime.run_1d(kernel, kTokens * kAdapterRank);
}

void dispatch_adapter_grad_a(ClRuntime& runtime, cl_kernel kernel, cl_mem input,
                             cl_mem hidden_rank_grad, cl_mem grad_a) {
  const std::int32_t tokens = static_cast<std::int32_t>(kTokens);
  const std::int32_t hidden = static_cast<std::int32_t>(kHidden);
  const std::int32_t rank = static_cast<std::int32_t>(kAdapterRank);
  runtime.set_arg(kernel, 0U, input);
  runtime.set_arg(kernel, 1U, hidden_rank_grad);
  runtime.set_arg(kernel, 2U, grad_a);
  runtime.set_arg(kernel, 3U, tokens);
  runtime.set_arg(kernel, 4U, hidden);
  runtime.set_arg(kernel, 5U, rank);
  runtime.run_1d(kernel, kHidden * kAdapterRank);
}

void dispatch_sgd_update(ClRuntime& runtime, cl_kernel kernel, cl_mem values,
                         cl_mem gradient, float learning_rate, std::int32_t count) {
  runtime.set_arg(kernel, 0U, values);
  runtime.set_arg(kernel, 1U, gradient);
  runtime.set_arg(kernel, 2U, learning_rate);
  runtime.set_arg(kernel, 3U, count);
  runtime.run_1d(kernel, static_cast<std::size_t>(count));
}

struct LayerForwardResult {
  std::vector<float> output_values;
  std::string opencl_library;
  double elapsed_seconds;
  std::uint32_t layer_index;
  long max_rss_kb;
};

struct AdapterStepResult {
  std::vector<float> grad_a;
  std::vector<float> grad_b;
  std::vector<float> updated_a;
  std::vector<float> updated_b;
  std::string opencl_library;
  double elapsed_seconds;
  double loss;
  std::uint32_t active_tokens;
  bool applied_update;
  long max_rss_kb;
};

long max_resident_set_kb() {
  rusage usage{};
  if (getrusage(RUSAGE_SELF, &usage) != 0) {
    return -1L;
  }
  return usage.ru_maxrss;
}

void write_layer_telemetry(const std::string& output_dir, const std::string& opencl_library,
                           double elapsed_seconds, std::uint32_t layer_index) {
  std::ofstream file(join_path(output_dir, "telemetry.json"));
  if (!file) {
    throw std::runtime_error("unable to create telemetry.json");
  }
  file << "{\n";
  file << "  \"schema_version\": \"gemma4_opencl_layer_forward_telemetry_v1\",\n";
  file << "  \"backend\": \"opencl\",\n";
  file << "  \"model_id\": \"google/gemma-4-E4B\",\n";
  file << "  \"revision\": \"7aa32e6889efd6300124851b164f8b364314c3d8\",\n";
  file << "  \"layer_index\": " << layer_index << ",\n";
  file << "  \"case_count\": " << kCases << ",\n";
  file << "  \"seq\": " << kSequence << ",\n";
  file << "  \"hidden_size\": " << kHidden << ",\n";
  file << "  \"kernel_contract\": \"full_layer_forward_real_weights_no_cpu_fallback\",\n";
  file << "  \"opencl_library\": ";
  write_json_string(file, opencl_library);
  file << ",\n";
  file << "  \"elapsed_seconds\": " << std::fixed << std::setprecision(6)
       << elapsed_seconds << ",\n";
  file << "  \"max_rss_kb\": " << max_resident_set_kb() << "\n";
  file << "}\n";
}

void write_stack_telemetry(const std::string& output_dir,
                           const LayerForwardResult& first,
                           const LayerForwardResult& second) {
  std::ofstream file(join_path(output_dir, "telemetry.json"));
  if (!file) {
    throw std::runtime_error("unable to create telemetry.json");
  }
  file << "{\n";
  file << "  \"schema_version\": \"gemma4_opencl_two_layer_stack_telemetry_v1\",\n";
  file << "  \"backend\": \"opencl\",\n";
  file << "  \"model_id\": \"google/gemma-4-E4B\",\n";
  file << "  \"revision\": \"7aa32e6889efd6300124851b164f8b364314c3d8\",\n";
  file << "  \"layer_indices\": [" << first.layer_index << ", " << second.layer_index << "],\n";
  file << "  \"case_count\": " << kCases << ",\n";
  file << "  \"seq\": " << kSequence << ",\n";
  file << "  \"hidden_size\": " << kHidden << ",\n";
  file << "  \"kernel_contract\": \"two_sequential_layer_forward_real_weights_no_cpu_fallback\",\n";
  file << "  \"opencl_libraries\": [";
  write_json_string(file, first.opencl_library);
  file << ", ";
  write_json_string(file, second.opencl_library);
  file << "],\n";
  file << "  \"layer_elapsed_seconds\": [" << std::fixed << std::setprecision(6)
       << first.elapsed_seconds << ", " << second.elapsed_seconds << "],\n";
  file << "  \"layer_max_rss_kb\": [" << first.max_rss_kb << ", " << second.max_rss_kb
       << "],\n";
  file << "  \"elapsed_seconds\": " << std::fixed << std::setprecision(6)
       << (first.elapsed_seconds + second.elapsed_seconds) << ",\n";
  file << "  \"max_rss_kb\": " << max_resident_set_kb() << "\n";
  file << "}\n";
}

std::uint32_t count_active_tokens(const std::vector<std::uint8_t>& mask) {
  std::uint32_t active = 0U;
  for (const std::uint8_t value : mask) {
    if (value != 0U) {
      ++active;
    }
  }
  if (active == 0U) {
    throw std::runtime_error("adapter fixture attention mask has zero active tokens");
  }
  return active;
}

double masked_mse_half_loss(const std::vector<float>& diff,
                            const std::vector<std::uint8_t>& mask,
                            std::uint32_t active_tokens) {
  double sum_sq = 0.0;
  for (std::size_t token = 0U; token < kTokens; ++token) {
    if (mask[token] == 0U) {
      continue;
    }
    const std::size_t base = token * kHidden;
    for (std::size_t hidden = 0U; hidden < kHidden; ++hidden) {
      const double value = static_cast<double>(diff[base + hidden]);
      if (!std::isfinite(value)) {
        throw std::runtime_error("adapter diff contains a non-finite value");
      }
      sum_sq += value * value;
    }
  }
  const double norm = static_cast<double>(active_tokens) * static_cast<double>(kHidden);
  return 0.5 * sum_sq / norm;
}

void write_adapter_telemetry(const std::string& output_dir,
                             const std::string& checkpoint_dir,
                             const AdapterStepResult& result,
                             float learning_rate) {
  std::ofstream file(join_path(output_dir, "telemetry.json"));
  if (!file) {
    throw std::runtime_error("unable to create adapter telemetry.json");
  }

  const std::string grad_a_path = join_path(output_dir, "adapter_grad_a.f32.bin");
  const std::string grad_b_path = join_path(output_dir, "adapter_grad_b.f32.bin");
  const std::string input_a_path = join_path(checkpoint_dir, "adapter_a.f32.bin");
  const std::string input_b_path = join_path(checkpoint_dir, "adapter_b.f32.bin");

  file << "{\n";
  file << "  \"schema_version\": \"gemma4_opencl_adapter_training_step_telemetry_v1\",\n";
  file << "  \"backend\": \"opencl\",\n";
  file << "  \"model_id\": \"google/gemma-4-E4B\",\n";
  file << "  \"revision\": \"7aa32e6889efd6300124851b164f8b364314c3d8\",\n";
  file << "  \"trainable_scope\": \"post_layer0_rank4_residual_adapter\",\n";
  file << "  \"kernel_contract\": \"adapter_backward_real_hidden_state_no_host_gradient\",\n";
  file << "  \"case_count\": " << kCases << ",\n";
  file << "  \"seq\": " << kSequence << ",\n";
  file << "  \"hidden_size\": " << kHidden << ",\n";
  file << "  \"rank\": " << kAdapterRank << ",\n";
  file << "  \"adapter_scale\": " << std::fixed << std::setprecision(8)
       << kAdapterScale << ",\n";
  file << "  \"active_tokens\": " << result.active_tokens << ",\n";
  file << "  \"loss_half_mse\": " << std::fixed << std::setprecision(10)
       << result.loss << ",\n";
  file << "  \"applied_update\": " << (result.applied_update ? "true" : "false") << ",\n";
  file << "  \"learning_rate\": " << std::fixed << std::setprecision(10)
       << learning_rate << ",\n";
  file << "  \"opencl_library\": ";
  write_json_string(file, result.opencl_library);
  file << ",\n";
  file << "  \"elapsed_seconds\": " << std::fixed << std::setprecision(6)
       << result.elapsed_seconds << ",\n";
  file << "  \"max_rss_kb\": " << result.max_rss_kb << ",\n";
  file << "  \"input_checkpoint_sha256\": {\n";
  file << "    \"adapter_a\": ";
  write_json_string(file, sha256_file_hex(input_a_path));
  file << ",\n";
  file << "    \"adapter_b\": ";
  write_json_string(file, sha256_file_hex(input_b_path));
  file << "\n  },\n";
  file << "  \"gradient_sha256\": {\n";
  file << "    \"adapter_a\": ";
  write_json_string(file, sha256_file_hex(grad_a_path));
  file << ",\n";
  file << "    \"adapter_b\": ";
  write_json_string(file, sha256_file_hex(grad_b_path));
  file << "\n  }";
  if (result.applied_update) {
    file << ",\n  \"updated_checkpoint_sha256\": {\n";
    file << "    \"adapter_a\": ";
    write_json_string(file,
                      sha256_file_hex(join_path(output_dir, "checkpoint/adapter_a.f32.bin")));
    file << ",\n";
    file << "    \"adapter_b\": ";
    write_json_string(file,
                      sha256_file_hex(join_path(output_dir, "checkpoint/adapter_b.f32.bin")));
    file << "\n  }";
  }
  file << "\n}\n";
}

AdapterStepResult run_adapter_step_values(const std::string& fixture_dir,
                                          const std::string& checkpoint_dir,
                                          bool apply_update,
                                          float learning_rate) {
  const auto start_time = std::chrono::steady_clock::now();
  std::vector<float> input =
      read_binary_vector<float>(join_path(fixture_dir, "input/layer0_output.f32.bin"),
                                kTokens * kHidden);
  std::vector<float> target =
      read_binary_vector<float>(join_path(fixture_dir, "target/layer1_output.f32.bin"),
                                kTokens * kHidden);
  std::vector<std::uint8_t> mask =
      read_binary_vector<std::uint8_t>(join_path(fixture_dir, "input/attention_mask.u8.bin"),
                                       kTokens);
  std::vector<float> adapter_a =
      read_binary_vector<float>(join_path(checkpoint_dir, "adapter_a.f32.bin"),
                                kHidden * kAdapterRank);
  std::vector<float> adapter_b =
      read_binary_vector<float>(join_path(checkpoint_dir, "adapter_b.f32.bin"),
                                kAdapterRank * kHidden);

  const std::uint32_t active_tokens = count_active_tokens(mask);
  const float inv_norm =
      1.0F / (static_cast<float>(active_tokens) * static_cast<float>(kHidden));

  DynamicLibrary library;
  OpenClApi api(library.handle());
  ClRuntime runtime(api);
  runtime.build_program(opencl_source());
  const KernelSet kernels = create_kernels(runtime);

  cl_mem input_buffer = runtime.buffer_from_vector(input);
  cl_mem target_buffer = runtime.buffer_from_vector(target);
  cl_mem mask_buffer = runtime.buffer_from_vector(mask);
  cl_mem adapter_a_buffer = runtime.buffer_from_vector(adapter_a);
  cl_mem adapter_b_buffer = runtime.buffer_from_vector(adapter_b);
  cl_mem z = runtime.buffer(kTokens * kAdapterRank * sizeof(float));
  cl_mem diff = runtime.buffer(kTokens * kHidden * sizeof(float));
  cl_mem hidden_rank_grad = runtime.buffer(kTokens * kAdapterRank * sizeof(float));
  cl_mem grad_a = runtime.buffer(kHidden * kAdapterRank * sizeof(float));
  cl_mem grad_b = runtime.buffer(kAdapterRank * kHidden * sizeof(float));

  dispatch_adapter_forward_z(runtime, kernels.adapter_forward_z, input_buffer,
                             adapter_a_buffer, z);
  dispatch_adapter_output_diff(runtime, kernels.adapter_output_diff, input_buffer,
                               target_buffer, mask_buffer, z, adapter_b_buffer, diff);
  dispatch_adapter_grad_b(runtime, kernels.adapter_grad_b, z, diff, grad_b, inv_norm);
  dispatch_adapter_hidden_rank_grad(runtime, kernels.adapter_hidden_rank_grad, diff,
                                    adapter_b_buffer, hidden_rank_grad, inv_norm);
  dispatch_adapter_grad_a(runtime, kernels.adapter_grad_a, input_buffer,
                          hidden_rank_grad, grad_a);
  if (apply_update) {
    dispatch_sgd_update(runtime, kernels.sgd_update, adapter_a_buffer, grad_a,
                        learning_rate, static_cast<std::int32_t>(kHidden * kAdapterRank));
    dispatch_sgd_update(runtime, kernels.sgd_update, adapter_b_buffer, grad_b,
                        learning_rate, static_cast<std::int32_t>(kAdapterRank * kHidden));
  }
  runtime.finish();

  std::vector<float> diff_values(kTokens * kHidden);
  std::vector<float> grad_a_values(kHidden * kAdapterRank);
  std::vector<float> grad_b_values(kAdapterRank * kHidden);
  std::vector<float> updated_a_values(kHidden * kAdapterRank);
  std::vector<float> updated_b_values(kAdapterRank * kHidden);
  runtime.read_buffer(diff, diff_values);
  runtime.read_buffer(grad_a, grad_a_values);
  runtime.read_buffer(grad_b, grad_b_values);
  runtime.read_buffer(adapter_a_buffer, updated_a_values);
  runtime.read_buffer(adapter_b_buffer, updated_b_values);

  const auto end_time = std::chrono::steady_clock::now();
  const double elapsed_seconds =
      std::chrono::duration<double>(end_time - start_time).count();
  const double loss = masked_mse_half_loss(diff_values, mask, active_tokens);
  return AdapterStepResult{std::move(grad_a_values),
                           std::move(grad_b_values),
                           std::move(updated_a_values),
                           std::move(updated_b_values),
                           library.loaded_path(),
                           elapsed_seconds,
                           loss,
                           active_tokens,
                           apply_update,
                           max_resident_set_kb()};
}

LayerForwardResult run_opencl_layer_values(const std::string& pack_dir,
                                           const std::vector<float>* input_override) {
  const auto start_time = std::chrono::steady_clock::now();
  const std::uint32_t layer_index = parse_layer_index(pack_dir);
  TensorData weights = load_weights(pack_dir, layer_index);
  std::vector<float> layer_input =
      input_override == nullptr
          ? read_binary_vector<float>(join_path(pack_dir, "input/layer_input.f32.bin"),
                                      kTokens * kHidden)
          : *input_override;
  if (layer_input.size() != (kTokens * kHidden)) {
    throw std::runtime_error("layer input override has invalid element count");
  }
    std::vector<float> per_layer_input = read_binary_vector<float>(
        join_path(pack_dir, "input/per_layer_input.f32.bin"), kTokens * kSmallInput);
    std::vector<std::uint8_t> attention_mask = read_binary_vector<std::uint8_t>(
        join_path(pack_dir, "input/attention_mask.u8.bin"), kTokens);
    std::vector<std::uint32_t> position_ids = read_binary_vector<std::uint32_t>(
        join_path(pack_dir, "input/position_ids.u32.bin"), kTokens);

    DynamicLibrary library;
    OpenClApi api(library.handle());
    ClRuntime runtime(api);
    runtime.build_program(opencl_source());
    const KernelSet kernels = create_kernels(runtime);

    cl_mem input = runtime.buffer_from_vector(layer_input);
    cl_mem per_input = runtime.buffer_from_vector(per_layer_input);
    cl_mem mask = runtime.buffer_from_vector(attention_mask);
    cl_mem positions = runtime.buffer_from_vector(position_ids);
    cl_mem input_ln_w = runtime.buffer_from_vector(weights.input_layernorm_weight);
    cl_mem down_w = runtime.buffer_from_vector(weights.mlp_down_proj_weight);
    cl_mem gate_w = runtime.buffer_from_vector(weights.mlp_gate_proj_weight);
    cl_mem up_w = runtime.buffer_from_vector(weights.mlp_up_proj_weight);
    cl_mem per_gate_w = runtime.buffer_from_vector(weights.per_layer_input_gate_weight);
    cl_mem per_proj_w = runtime.buffer_from_vector(weights.per_layer_projection_weight);
    cl_mem post_attn_ln_w = runtime.buffer_from_vector(weights.post_attention_layernorm_weight);
    cl_mem post_ff_ln_w = runtime.buffer_from_vector(weights.post_feedforward_layernorm_weight);
    cl_mem post_per_ln_w = runtime.buffer_from_vector(weights.post_per_layer_input_norm_weight);
    cl_mem pre_ff_ln_w = runtime.buffer_from_vector(weights.pre_feedforward_layernorm_weight);
    cl_mem k_norm_w = runtime.buffer_from_vector(weights.self_attn_k_norm_weight);
    cl_mem k_proj_w = runtime.buffer_from_vector(weights.self_attn_k_proj_weight);
    cl_mem o_proj_w = runtime.buffer_from_vector(weights.self_attn_o_proj_weight);
    cl_mem q_norm_w = runtime.buffer_from_vector(weights.self_attn_q_norm_weight);
    cl_mem q_proj_w = runtime.buffer_from_vector(weights.self_attn_q_proj_weight);
    cl_mem v_proj_w = runtime.buffer_from_vector(weights.self_attn_v_proj_weight);

    const std::size_t hidden_bytes = kTokens * kHidden * sizeof(float);
    const std::size_t query_bytes = kTokens * kQueryHeads * kHeadDim * sizeof(float);
    const std::size_t key_value_bytes = kTokens * kKeyValueHeads * kHeadDim * sizeof(float);
    const std::size_t intermediate_bytes = kTokens * kIntermediate * sizeof(float);
    const std::size_t small_bytes = kTokens * kSmallInput * sizeof(float);
    const std::size_t scores_bytes = kCases * kQueryHeads * kSequence * kSequence * sizeof(float);

    cl_mem attn_in = runtime.buffer(hidden_bytes);
    cl_mem q = runtime.buffer(query_bytes);
    cl_mem k = runtime.buffer(key_value_bytes);
    cl_mem v = runtime.buffer(key_value_bytes);
    cl_mem qn = runtime.buffer(query_bytes);
    cl_mem kn = runtime.buffer(key_value_bytes);
    cl_mem vn = runtime.buffer(key_value_bytes);
    cl_mem q_rope = runtime.buffer(query_bytes);
    cl_mem k_rope = runtime.buffer(key_value_bytes);
    cl_mem scores = runtime.buffer(scores_bytes);
    cl_mem context = runtime.buffer(query_bytes);
    cl_mem attn_proj = runtime.buffer(hidden_bytes);
    cl_mem attn_norm = runtime.buffer(hidden_bytes);
    cl_mem hidden_state = runtime.buffer(hidden_bytes);
    cl_mem ff_in = runtime.buffer(hidden_bytes);
    cl_mem gate = runtime.buffer(intermediate_bytes);
    cl_mem up = runtime.buffer(intermediate_bytes);
    cl_mem activation = runtime.buffer(intermediate_bytes);
    cl_mem down = runtime.buffer(hidden_bytes);
    cl_mem down_norm = runtime.buffer(hidden_bytes);
    cl_mem hidden2 = runtime.buffer(hidden_bytes);
    cl_mem per_gate = runtime.buffer(small_bytes);
    cl_mem per_activation = runtime.buffer(small_bytes);
    cl_mem per_proj = runtime.buffer(hidden_bytes);
    cl_mem per_norm = runtime.buffer(hidden_bytes);
    cl_mem output = runtime.buffer(hidden_bytes);

    const std::int32_t tokens = static_cast<std::int32_t>(kTokens);
    const std::int32_t hidden_size = static_cast<std::int32_t>(kHidden);
    const std::int32_t q_width = static_cast<std::int32_t>(kQueryHeads * kHeadDim);
    const std::int32_t kv_width = static_cast<std::int32_t>(kKeyValueHeads * kHeadDim);
    const std::int32_t head_dim = static_cast<std::int32_t>(kHeadDim);
    const std::int32_t intermediate = static_cast<std::int32_t>(kIntermediate);
    const std::int32_t small_input = static_cast<std::int32_t>(kSmallInput);

    dispatch_rms_weighted(runtime, kernels.rms_weighted, input, input_ln_w, attn_in, tokens,
                          hidden_size);
    dispatch_linear(runtime, kernels.linear_tiled, attn_in, q_proj_w, q, tokens, hidden_size,
                    q_width);
    dispatch_linear(runtime, kernels.linear_tiled, attn_in, k_proj_w, k, tokens, hidden_size,
                    kv_width);
    dispatch_linear(runtime, kernels.linear_tiled, attn_in, v_proj_w, v, tokens, hidden_size,
                    kv_width);
    dispatch_rms_weighted(runtime, kernels.rms_weighted, q, q_norm_w, qn,
                          tokens * static_cast<std::int32_t>(kQueryHeads), head_dim);
    dispatch_rms_weighted(runtime, kernels.rms_weighted, k, k_norm_w, kn,
                          tokens * static_cast<std::int32_t>(kKeyValueHeads), head_dim);
    dispatch_rms_unweighted(runtime, kernels.rms_unweighted, v, vn,
                            tokens * static_cast<std::int32_t>(kKeyValueHeads), head_dim);
    dispatch_rope(runtime, kernels.rope, qn, q_rope, positions, tokens,
                  static_cast<std::int32_t>(kQueryHeads), head_dim);
    dispatch_rope(runtime, kernels.rope, kn, k_rope, positions, tokens,
                  static_cast<std::int32_t>(kKeyValueHeads), head_dim);
    dispatch_attention_scores(runtime, kernels.attention_scores, q_rope, k_rope, mask,
                              scores);
    dispatch_attention_values(runtime, kernels.attention_values, scores, vn, context);
    dispatch_linear(runtime, kernels.linear_tiled, context, o_proj_w, attn_proj, tokens,
                    q_width, hidden_size);
    dispatch_rms_weighted(runtime, kernels.rms_weighted, attn_proj, post_attn_ln_w,
                          attn_norm, tokens, hidden_size);
    dispatch_add(runtime, kernels.add_vectors, input, attn_norm, hidden_state,
                 tokens * hidden_size);

    dispatch_rms_weighted(runtime, kernels.rms_weighted, hidden_state, pre_ff_ln_w, ff_in, tokens,
                          hidden_size);
    dispatch_linear(runtime, kernels.linear_tiled, ff_in, gate_w, gate, tokens, hidden_size,
                    intermediate);
    dispatch_linear(runtime, kernels.linear_tiled, ff_in, up_w, up, tokens, hidden_size,
                    intermediate);
    dispatch_gelu_mul(runtime, kernels.gelu_tanh_mul, gate, up, activation,
                      tokens * intermediate);
    dispatch_linear(runtime, kernels.linear_tiled, activation, down_w, down, tokens,
                    intermediate, hidden_size);
    dispatch_rms_weighted(runtime, kernels.rms_weighted, down, post_ff_ln_w, down_norm,
                          tokens, hidden_size);
    dispatch_add(runtime, kernels.add_vectors, hidden_state, down_norm, hidden2,
                 tokens * hidden_size);

    dispatch_linear(runtime, kernels.linear_tiled, hidden2, per_gate_w, per_gate, tokens,
                    hidden_size, small_input);
    dispatch_gelu_mul(runtime, kernels.gelu_tanh_mul, per_gate, per_input, per_activation,
                      tokens * small_input);
    dispatch_linear(runtime, kernels.linear_tiled, per_activation, per_proj_w, per_proj,
                    tokens, small_input, hidden_size);
    dispatch_rms_weighted(runtime, kernels.rms_weighted, per_proj, post_per_ln_w, per_norm,
                          tokens, hidden_size);
    dispatch_add(runtime, kernels.add_vectors, hidden2, per_norm, output,
                 tokens * hidden_size);
    dispatch_scale(runtime, kernels.scale_inplace, output, weights.layer_scalar[0],
                   tokens * hidden_size);
    runtime.finish();

    std::vector<float> output_values(kTokens * kHidden);
    runtime.read_buffer(output, output_values);
    const auto end_time = std::chrono::steady_clock::now();
    const double elapsed_seconds =
        std::chrono::duration<double>(end_time - start_time).count();
  return LayerForwardResult{std::move(output_values), library.loaded_path(), elapsed_seconds,
                            layer_index, max_resident_set_kb()};
}

}  // namespace

Status run_opencl_layer_forward(const std::string& pack_dir, const std::string& output_dir) {
  try {
    ensure_directory(output_dir);
    const LayerForwardResult result = run_opencl_layer_values(pack_dir, nullptr);
    write_binary_vector(join_path(output_dir, "layer_output.f32.bin"), result.output_values);
    write_layer_telemetry(output_dir, result.opencl_library, result.elapsed_seconds,
                          result.layer_index);
    return Status::ok();
  } catch (const std::exception& error) {
    return Status::invalid(error.what());
  }
}

Status run_opencl_layer0(const std::string& pack_dir, const std::string& output_dir) {
  return run_opencl_layer_forward(pack_dir, output_dir);
}

Status run_opencl_two_layer_stack(const std::string& first_pack_dir,
                                  const std::string& second_pack_dir,
                                  const std::string& output_dir) {
  try {
    ensure_directory(output_dir);
    const LayerForwardResult first = run_opencl_layer_values(first_pack_dir, nullptr);
    write_binary_vector(join_path(output_dir, "layer0_output.f32.bin"), first.output_values);
    const LayerForwardResult second =
        run_opencl_layer_values(second_pack_dir, &first.output_values);
    write_binary_vector(join_path(output_dir, "layer_output.f32.bin"), second.output_values);
    write_stack_telemetry(output_dir, first, second);
    return Status::ok();
  } catch (const std::exception& error) {
    return Status::invalid(error.what());
  }
}

Status run_opencl_adapter_gradient_step(const std::string& fixture_dir,
                                        const std::string& checkpoint_dir,
                                        const std::string& output_dir) {
  try {
    ensure_directory(output_dir);
    const AdapterStepResult result =
        run_adapter_step_values(fixture_dir, checkpoint_dir, false, 0.0F);
    write_binary_vector(join_path(output_dir, "adapter_grad_a.f32.bin"), result.grad_a);
    write_binary_vector(join_path(output_dir, "adapter_grad_b.f32.bin"), result.grad_b);
    write_adapter_telemetry(output_dir, checkpoint_dir, result, 0.0F);
    return Status::ok();
  } catch (const std::exception& error) {
    return Status::invalid(error.what());
  }
}

Status run_opencl_adapter_sgd_update(const std::string& fixture_dir,
                                     const std::string& checkpoint_dir,
                                     const std::string& output_dir,
                                     float learning_rate) {
  try {
    if (!(learning_rate > 0.0F) || !std::isfinite(learning_rate)) {
      return Status::invalid("learning rate must be finite and positive");
    }
    ensure_directory(output_dir);
    ensure_directory(join_path(output_dir, "checkpoint"));
    const AdapterStepResult result =
        run_adapter_step_values(fixture_dir, checkpoint_dir, true, learning_rate);
    write_binary_vector(join_path(output_dir, "adapter_grad_a.f32.bin"), result.grad_a);
    write_binary_vector(join_path(output_dir, "adapter_grad_b.f32.bin"), result.grad_b);
    write_binary_vector(join_path(output_dir, "checkpoint/adapter_a.f32.bin"),
                        result.updated_a);
    write_binary_vector(join_path(output_dir, "checkpoint/adapter_b.f32.bin"),
                        result.updated_b);
    write_adapter_telemetry(output_dir, checkpoint_dir, result, learning_rate);
    return Status::ok();
  } catch (const std::exception& error) {
    return Status::invalid(error.what());
  }
}

Status OpenClAdapterTrainingStepExecutor::run_training_step(
    const TrainingStepRequest& request) {
  if (request.apply_update) {
    return run_opencl_adapter_sgd_update(request.fixture_dir, request.checkpoint_dir,
                                         request.output_dir, request.learning_rate);
  }
  return run_opencl_adapter_gradient_step(request.fixture_dir, request.checkpoint_dir,
                                          request.output_dir);
}

}  // namespace polymath::gemma4
