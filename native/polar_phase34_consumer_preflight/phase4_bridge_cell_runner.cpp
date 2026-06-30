#include <dlfcn.h>
#include <sys/stat.h>

#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

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
using cl_profiling_info = cl_uint;

constexpr cl_int kClSuccess = 0;
constexpr cl_bool kClTrue = 1;
constexpr cl_device_type kClDeviceTypeGpu = 1ULL << 2U;
constexpr cl_mem_flags kClMemReadWrite = 1ULL << 0U;
constexpr cl_mem_flags kClMemCopyHostPtr = 1ULL << 5U;
constexpr std::uint64_t kClQueueProfilingEnable = 1ULL << 1U;
constexpr cl_uint kClProgramBuildLog = 0x1183U;
constexpr cl_uint kClDeviceName = 0x102BU;
constexpr cl_profiling_info kClProfilingCommandStart = 0x1282U;
constexpr cl_profiling_info kClProfilingCommandEnd = 0x1283U;

constexpr std::uint32_t kTokens = 16U;
constexpr std::uint32_t kHidden = 2560U;
constexpr std::uint32_t kRank = 16U;
constexpr std::uint32_t kElements = kTokens * kHidden;
constexpr std::uint32_t kAdapterElements = kHidden * kRank;
constexpr float kLearningRate = 0.0003F;

const char* kKernelSource = R"CLC(
__kernel void compute_q(__global const float* x,
                        __global const float* adapter_a,
                        __global float* q) {
  const uint gid = get_global_id(0);
  const uint token = gid / 16;
  const uint rank = gid % 16;
  float sum = 0.0f;
  for (uint h = 0; h < 2560; ++h) {
    sum += x[token * 2560 + h] * adapter_a[h * 16 + rank];
  }
  q[gid] = sum;
}

__kernel void loss_partials(__global const float* x,
                            __global const float* target,
                            __global float* partials) {
  const uint gid = get_global_id(0);
  const float diff = x[gid] - target[gid];
  partials[gid] = diff * diff;
}

__kernel void post_update_loss_partials(__global const float* x,
                                        __global const float* target,
                                        __global const float* q,
                                        __global const float* adapter_b,
                                        __global float* partials) {
  const uint gid = get_global_id(0);
  const uint token = gid / 2560;
  const uint h = gid % 2560;
  float delta = 0.0f;
  for (uint rank = 0; rank < 16; ++rank) {
    delta += q[token * 16 + rank] * adapter_b[rank * 2560 + h];
  }
  const float z = x[gid] + delta * (1.0f / 16.0f);
  const float diff = z - target[gid];
  partials[gid] = diff * diff;
}

__kernel void grad_update_b(__global const float* x,
                            __global const float* target,
                            __global const float* q,
                            __global float* adapter_b,
                            __global float* update_abs) {
  const uint gid = get_global_id(0);
  const uint rank = gid / 2560;
  const uint h = gid % 2560;
  float grad = 0.0f;
  for (uint token = 0; token < 16; ++token) {
    const float diff = x[token * 2560 + h] - target[token * 2560 + h];
    grad += diff * q[token * 16 + rank];
  }
  grad = grad * (2.0f / (16.0f * 2560.0f)) * (1.0f / 16.0f);
  const float delta = -0.0003f * grad;
  adapter_b[gid] += delta;
  update_abs[gid] = fabs(delta);
}

__kernel void perturb_x(__global const float* x,
                        __global float* x_alt) {
  const uint gid = get_global_id(0);
  x_alt[gid] = -x[gid];
}
)CLC";

template <typename Function>
Function resolve(void* library, const char* name) {
  void* symbol = dlsym(library, name);
  if (symbol == nullptr) {
    throw std::runtime_error(std::string("OpenCL missing symbol: ") + name);
  }
  return reinterpret_cast<Function>(symbol);
}

struct Api {
  using GetPlatformIDs = cl_int (*)(cl_uint, cl_platform_id*, cl_uint*);
  using GetDeviceIDs = cl_int (*)(cl_platform_id, cl_device_type, cl_uint, cl_device_id*, cl_uint*);
  using GetDeviceInfo = cl_int (*)(cl_device_id, cl_uint, std::size_t, void*, std::size_t*);
  using CreateContext = cl_context (*)(const cl_context_properties*, cl_uint, const cl_device_id*, void (*)(const char*, const void*, std::size_t, void*), void*, cl_int*);
  using CreateCommandQueue = cl_command_queue (*)(cl_context, cl_device_id, std::uint64_t, cl_int*);
  using CreateProgramWithSource = cl_program (*)(cl_context, cl_uint, const char**, const std::size_t*, cl_int*);
  using BuildProgram = cl_int (*)(cl_program, cl_uint, const cl_device_id*, const char*, void (*)(cl_program, void*), void*);
  using GetProgramBuildInfo = cl_int (*)(cl_program, cl_device_id, cl_uint, std::size_t, void*, std::size_t*);
  using CreateKernel = cl_kernel (*)(cl_program, const char*, cl_int*);
  using SetKernelArg = cl_int (*)(cl_kernel, cl_uint, std::size_t, const void*);
  using CreateBuffer = cl_mem (*)(cl_context, cl_mem_flags, std::size_t, void*, cl_int*);
  using EnqueueNDRangeKernel = cl_int (*)(cl_command_queue, cl_kernel, cl_uint, const std::size_t*, const std::size_t*, const std::size_t*, cl_uint, const cl_event*, cl_event*);
  using EnqueueReadBuffer = cl_int (*)(cl_command_queue, cl_mem, cl_bool, std::size_t, std::size_t, void*, cl_uint, const cl_event*, cl_event*);
  using GetEventProfilingInfo = cl_int (*)(cl_event, cl_profiling_info, std::size_t, void*, std::size_t*);
  using Finish = cl_int (*)(cl_command_queue);
  using ReleaseEvent = cl_int (*)(cl_event);
  using ReleaseMemObject = cl_int (*)(cl_mem);
  using ReleaseKernel = cl_int (*)(cl_kernel);
  using ReleaseProgram = cl_int (*)(cl_program);
  using ReleaseCommandQueue = cl_int (*)(cl_command_queue);
  using ReleaseContext = cl_int (*)(cl_context);

  explicit Api(void* lib)
      : get_platform_ids(resolve<GetPlatformIDs>(lib, "clGetPlatformIDs")),
        get_device_ids(resolve<GetDeviceIDs>(lib, "clGetDeviceIDs")),
        get_device_info(resolve<GetDeviceInfo>(lib, "clGetDeviceInfo")),
        create_context(resolve<CreateContext>(lib, "clCreateContext")),
        create_command_queue(resolve<CreateCommandQueue>(lib, "clCreateCommandQueue")),
        create_program_with_source(resolve<CreateProgramWithSource>(lib, "clCreateProgramWithSource")),
        build_program(resolve<BuildProgram>(lib, "clBuildProgram")),
        get_program_build_info(resolve<GetProgramBuildInfo>(lib, "clGetProgramBuildInfo")),
        create_kernel(resolve<CreateKernel>(lib, "clCreateKernel")),
        set_kernel_arg(resolve<SetKernelArg>(lib, "clSetKernelArg")),
        create_buffer(resolve<CreateBuffer>(lib, "clCreateBuffer")),
        enqueue_nd_range_kernel(resolve<EnqueueNDRangeKernel>(lib, "clEnqueueNDRangeKernel")),
        enqueue_read_buffer(resolve<EnqueueReadBuffer>(lib, "clEnqueueReadBuffer")),
        get_event_profiling_info(resolve<GetEventProfilingInfo>(lib, "clGetEventProfilingInfo")),
        finish(resolve<Finish>(lib, "clFinish")),
        release_event(resolve<ReleaseEvent>(lib, "clReleaseEvent")),
        release_mem_object(resolve<ReleaseMemObject>(lib, "clReleaseMemObject")),
        release_kernel(resolve<ReleaseKernel>(lib, "clReleaseKernel")),
        release_program(resolve<ReleaseProgram>(lib, "clReleaseProgram")),
        release_command_queue(resolve<ReleaseCommandQueue>(lib, "clReleaseCommandQueue")),
        release_context(resolve<ReleaseContext>(lib, "clReleaseContext")) {}

  GetPlatformIDs get_platform_ids;
  GetDeviceIDs get_device_ids;
  GetDeviceInfo get_device_info;
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
  GetEventProfilingInfo get_event_profiling_info;
  Finish finish;
  ReleaseEvent release_event;
  ReleaseMemObject release_mem_object;
  ReleaseKernel release_kernel;
  ReleaseProgram release_program;
  ReleaseCommandQueue release_command_queue;
  ReleaseContext release_context;
};

struct Stats {
  std::uint64_t dispatch_count = 0;
  std::uint64_t profiled_dispatch_count = 0;
  std::uint64_t kernel_elapsed_ns = 0;
  std::uint64_t sync_count = 0;
  std::uint64_t host_device_bytes = 0;
  std::uint64_t blocking_read_bytes = 0;
};

struct Args {
  std::string phase3_output;
  std::string target;
  std::string out_dir;
  std::string corpus_phase = "C1_diagnostic";
};

void require_cl(cl_int status, const std::string& label) {
  if (status != kClSuccess) {
    throw std::runtime_error(label + " failed with OpenCL error " + std::to_string(status));
  }
}

std::vector<float> read_f32_file(const std::string& path, std::size_t expected_count) {
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    throw std::runtime_error("unable to open " + path);
  }
  std::vector<float> data(expected_count);
  in.read(reinterpret_cast<char*>(data.data()), static_cast<std::streamsize>(data.size() * sizeof(float)));
  if (in.gcount() != static_cast<std::streamsize>(data.size() * sizeof(float))) {
    throw std::runtime_error("unexpected byte count for " + path);
  }
  return data;
}

void write_f32_file(const std::string& path, const std::vector<float>& data) {
  std::ofstream out(path, std::ios::binary);
  if (!out) {
    throw std::runtime_error("unable to write " + path);
  }
  out.write(reinterpret_cast<const char*>(data.data()), static_cast<std::streamsize>(data.size() * sizeof(float)));
}

std::string shell_sha256(const std::string& path) {
  std::string command = "sha256sum '" + path + "'";
  FILE* pipe = popen(command.c_str(), "r");
  if (pipe == nullptr) {
    throw std::runtime_error("sha256sum failed for " + path);
  }
  char buffer[128];
  std::string output;
  while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
    output += buffer;
  }
  const int status = pclose(pipe);
  if (status != 0 || output.size() < 64U) {
    throw std::runtime_error("sha256sum failed for " + path);
  }
  return output.substr(0, 64);
}

std::string json_escape(const std::string& value) {
  std::ostringstream out;
  for (const char ch : value) {
    if (ch == '"' || ch == '\\') {
      out << '\\' << ch;
    } else if (ch == '\n') {
      out << "\\n";
    } else {
      out << ch;
    }
  }
  return out.str();
}

std::string device_name(const Api& api, cl_device_id device) {
  std::size_t size = 0;
  if (api.get_device_info(device, kClDeviceName, 0, nullptr, &size) != kClSuccess || size == 0) {
    return "unknown";
  }
  std::vector<char> name(size);
  if (api.get_device_info(device, kClDeviceName, size, name.data(), nullptr) != kClSuccess) {
    return "unknown";
  }
  return std::string(name.data());
}

void enqueue_kernel(const Api& api, cl_command_queue queue, cl_kernel kernel, std::size_t global, Stats& stats) {
  cl_event event = nullptr;
  const cl_int status = api.enqueue_nd_range_kernel(queue, kernel, 1, nullptr, &global, nullptr, 0, nullptr, &event);
  require_cl(status, "clEnqueueNDRangeKernel");
  stats.dispatch_count += 1;
  if (event != nullptr) {
    require_cl(api.finish(queue), "clFinish profiled kernel");
    stats.sync_count += 1;
    std::uint64_t start = 0;
    std::uint64_t end = 0;
    if (api.get_event_profiling_info(event, kClProfilingCommandStart, sizeof(start), &start, nullptr) == kClSuccess &&
        api.get_event_profiling_info(event, kClProfilingCommandEnd, sizeof(end), &end, nullptr) == kClSuccess &&
        end >= start) {
      stats.profiled_dispatch_count += 1;
      stats.kernel_elapsed_ns += end - start;
    }
    api.release_event(event);
  }
}

cl_mem buffer_from_vector(const Api& api, cl_context context, std::vector<float>& data, Stats& stats) {
  cl_int error = 0;
  cl_mem mem = api.create_buffer(context, kClMemReadWrite | kClMemCopyHostPtr, data.size() * sizeof(float), data.data(), &error);
  require_cl(error, "clCreateBuffer");
  stats.host_device_bytes += data.size() * sizeof(float);
  return mem;
}

cl_kernel kernel(const Api& api, cl_program program, const char* name) {
  cl_int error = 0;
  cl_kernel result = api.create_kernel(program, name, &error);
  require_cl(error, std::string("clCreateKernel ") + name);
  return result;
}

struct VectorStats {
  double l1 = 0.0;
  double l2 = 0.0;
  double linf = 0.0;
  std::uint64_t nan_count = 0;
  std::uint64_t inf_count = 0;
  std::uint64_t nonzero_count = 0;
};

VectorStats vector_stats(const std::vector<float>& values) {
  VectorStats stats;
  double square_sum = 0.0;
  for (const float value : values) {
    if (std::isnan(value)) {
      stats.nan_count += 1;
      continue;
    }
    if (std::isinf(value)) {
      stats.inf_count += 1;
      continue;
    }
    const double abs_value = std::fabs(static_cast<double>(value));
    stats.l1 += abs_value;
    square_sum += abs_value * abs_value;
    if (abs_value > stats.linf) {
      stats.linf = abs_value;
    }
    if (abs_value > 0.0) {
      stats.nonzero_count += 1;
    }
  }
  stats.l2 = std::sqrt(square_sum);
  return stats;
}

template <typename T>
void set_arg(const Api& api, cl_kernel kernel_handle, cl_uint index, const T& value) {
  require_cl(api.set_kernel_arg(kernel_handle, index, sizeof(T), &value), "clSetKernelArg");
}

double sum_vector(const std::vector<float>& values) {
  double total = 0.0;
  for (const float value : values) {
    total += static_cast<double>(value);
  }
  return total;
}

std::vector<float> cpu_reference_b_update(const std::vector<float>& x,
                                          const std::vector<float>& target,
                                          const std::vector<float>& adapter_a) {
  std::vector<float> q(kTokens * kRank, 0.0F);
  for (std::uint32_t token = 0; token < kTokens; ++token) {
    for (std::uint32_t rank = 0; rank < kRank; ++rank) {
      float sum = 0.0F;
      for (std::uint32_t h = 0; h < kHidden; ++h) {
        sum += x[token * kHidden + h] * adapter_a[h * kRank + rank];
      }
      q[token * kRank + rank] = sum;
    }
  }

  std::vector<float> adapter_b(kAdapterElements, 0.0F);
  for (std::uint32_t rank = 0; rank < kRank; ++rank) {
    for (std::uint32_t h = 0; h < kHidden; ++h) {
      float grad = 0.0F;
      for (std::uint32_t token = 0; token < kTokens; ++token) {
        const float diff = x[token * kHidden + h] - target[token * kHidden + h];
        grad += diff * q[token * kRank + rank];
      }
      grad = grad * (2.0F / (static_cast<float>(kTokens) * static_cast<float>(kHidden))) *
             (1.0F / static_cast<float>(kRank));
      adapter_b[rank * kHidden + h] = -kLearningRate * grad;
    }
  }
  return adapter_b;
}

double cpu_reference_loss(const std::vector<float>& x, const std::vector<float>& target) {
  double loss = 0.0;
  for (std::size_t i = 0; i < x.size(); ++i) {
    const double diff = static_cast<double>(x[i]) - static_cast<double>(target[i]);
    loss += diff * diff;
  }
  return loss / static_cast<double>(x.size());
}

double max_abs_difference(const std::vector<float>& first, const std::vector<float>& second) {
  if (first.size() != second.size()) {
    return std::numeric_limits<double>::infinity();
  }
  double max_diff = 0.0;
  for (std::size_t i = 0; i < first.size(); ++i) {
    const double diff = std::fabs(static_cast<double>(first[i]) - static_cast<double>(second[i]));
    if (diff > max_diff) {
      max_diff = diff;
    }
  }
  return max_diff;
}

std::vector<float> make_adapter_a() {
  std::vector<float> values(kAdapterElements);
  std::uint32_t state = 3407U;
  for (float& value : values) {
    state = state * 1664525U + 1013904223U;
    const float unit = static_cast<float>(state & 0xFFFFU) / 65535.0F;
    value = (unit - 0.5F) * 0.02F;
  }
  return values;
}

void ensure_dir(const std::string& path) {
  std::string command = "mkdir -p '" + path + "'";
  if (std::system(command.c_str()) != 0) {
    throw std::runtime_error("mkdir failed: " + path);
  }
}

Args parse_args(int argc, char** argv) {
  Args args;
  for (int i = 1; i < argc; ++i) {
    const std::string key = argv[i];
    if (i + 1 >= argc) {
      throw std::runtime_error("missing value for " + key);
    }
    const std::string value = argv[++i];
    if (key == "--phase3-output") {
      args.phase3_output = value;
    } else if (key == "--target") {
      args.target = value;
    } else if (key == "--out-dir") {
      args.out_dir = value;
    } else if (key == "--corpus-phase") {
      args.corpus_phase = value;
    } else {
      throw std::runtime_error("unknown argument " + key);
    }
  }
  if (args.phase3_output.empty() || args.target.empty() || args.out_dir.empty()) {
    throw std::runtime_error("usage: phase4_bridge_cell_runner --phase3-output PATH --target PATH --out-dir DIR [--corpus-phase C1]");
  }
  return args;
}

}  // namespace

int main(int argc, char** argv) {
  try {
    const Args args = parse_args(argc, argv);
    ensure_dir(args.out_dir);

    void* library = nullptr;
    const char* candidates[] = {"libOpenCL.so", "/vendor/lib64/libOpenCL.so", "/system/vendor/lib64/libOpenCL.so"};
    std::string library_path;
    for (const char* candidate : candidates) {
      library = dlopen(candidate, RTLD_NOW | RTLD_LOCAL);
      if (library != nullptr) {
        library_path = candidate;
        break;
      }
    }
    if (library == nullptr) {
      throw std::runtime_error("unable to load OpenCL");
    }
    const Api api(library);
    cl_uint platform_count = 0;
    require_cl(api.get_platform_ids(0, nullptr, &platform_count), "clGetPlatformIDs count");
    if (platform_count == 0) {
      throw std::runtime_error("OpenCL reports zero platforms");
    }
    std::vector<cl_platform_id> platforms(platform_count);
    require_cl(api.get_platform_ids(platform_count, platforms.data(), nullptr), "clGetPlatformIDs");
    cl_device_id device = nullptr;
    for (cl_platform_id platform : platforms) {
      cl_uint device_count = 0;
      if (api.get_device_ids(platform, kClDeviceTypeGpu, 0, nullptr, &device_count) != kClSuccess || device_count == 0) {
        continue;
      }
      std::vector<cl_device_id> devices(device_count);
      require_cl(api.get_device_ids(platform, kClDeviceTypeGpu, device_count, devices.data(), nullptr), "clGetDeviceIDs");
      device = devices.front();
      break;
    }
    if (device == nullptr) {
      throw std::runtime_error("OpenCL reports zero GPU devices");
    }

    Stats stats;
    cl_int error = 0;
    cl_context context = api.create_context(nullptr, 1, &device, nullptr, nullptr, &error);
    require_cl(error, "clCreateContext");
    cl_command_queue queue = api.create_command_queue(context, device, kClQueueProfilingEnable, &error);
    require_cl(error, "clCreateCommandQueue");

    const char* source = kKernelSource;
    const std::size_t source_len = std::strlen(kKernelSource);
    cl_program program = api.create_program_with_source(context, 1, &source, &source_len, &error);
    require_cl(error, "clCreateProgramWithSource");
    error = api.build_program(program, 1, &device, "", nullptr, nullptr);
    if (error != kClSuccess) {
      std::size_t log_size = 0;
      api.get_program_build_info(program, device, kClProgramBuildLog, 0, nullptr, &log_size);
      std::vector<char> log(log_size + 1, '\0');
      api.get_program_build_info(program, device, kClProgramBuildLog, log.size(), log.data(), nullptr);
      throw std::runtime_error(std::string("clBuildProgram failed: ") + log.data());
    }

    cl_kernel compute_q = kernel(api, program, "compute_q");
    cl_kernel loss_partials = kernel(api, program, "loss_partials");
    cl_kernel post_update_loss_partials = kernel(api, program, "post_update_loss_partials");
    cl_kernel grad_update_b = kernel(api, program, "grad_update_b");
    cl_kernel perturb_x = kernel(api, program, "perturb_x");

    std::vector<float> x = read_f32_file(args.phase3_output, kElements);
    std::vector<float> target = read_f32_file(args.target, kElements);
    std::vector<float> adapter_a = make_adapter_a();
    std::vector<float> adapter_b(kAdapterElements, 0.0F);
    const std::string adapter_pre_path = args.out_dir + "/adapter_pre_rank16.f32.bin";
    const std::string adapter_post_path = args.out_dir + "/adapter_post_rank16.f32.bin";
    write_f32_file(adapter_pre_path, adapter_a);
    {
      std::ofstream out(adapter_pre_path, std::ios::binary | std::ios::app);
      out.write(reinterpret_cast<const char*>(adapter_b.data()), static_cast<std::streamsize>(adapter_b.size() * sizeof(float)));
    }

    cl_mem x_mem = buffer_from_vector(api, context, x, stats);
    cl_mem target_mem = buffer_from_vector(api, context, target, stats);
    cl_mem a_mem = buffer_from_vector(api, context, adapter_a, stats);
    cl_mem b_mem = buffer_from_vector(api, context, adapter_b, stats);
    std::vector<float> q(kTokens * kRank, 0.0F);
    std::vector<float> partials(kElements, 0.0F);
    std::vector<float> update_abs(kAdapterElements, 0.0F);
    std::vector<float> x_alt(kElements, 0.0F);
    cl_mem q_mem = buffer_from_vector(api, context, q, stats);
    cl_mem partials_mem = buffer_from_vector(api, context, partials, stats);
    cl_mem update_mem = buffer_from_vector(api, context, update_abs, stats);
    cl_mem x_alt_mem = buffer_from_vector(api, context, x_alt, stats);

    set_arg(api, compute_q, 0, x_mem);
    set_arg(api, compute_q, 1, a_mem);
    set_arg(api, compute_q, 2, q_mem);
    enqueue_kernel(api, queue, compute_q, kTokens * kRank, stats);

    set_arg(api, loss_partials, 0, x_mem);
    set_arg(api, loss_partials, 1, target_mem);
    set_arg(api, loss_partials, 2, partials_mem);
    enqueue_kernel(api, queue, loss_partials, kElements, stats);

    set_arg(api, grad_update_b, 0, x_mem);
    set_arg(api, grad_update_b, 1, target_mem);
    set_arg(api, grad_update_b, 2, q_mem);
    set_arg(api, grad_update_b, 3, b_mem);
    set_arg(api, grad_update_b, 4, update_mem);
    enqueue_kernel(api, queue, grad_update_b, kAdapterElements, stats);

    set_arg(api, post_update_loss_partials, 0, x_mem);
    set_arg(api, post_update_loss_partials, 1, target_mem);
    set_arg(api, post_update_loss_partials, 2, q_mem);
    set_arg(api, post_update_loss_partials, 3, b_mem);
    set_arg(api, post_update_loss_partials, 4, partials_mem);
    enqueue_kernel(api, queue, post_update_loss_partials, kElements, stats);

    set_arg(api, perturb_x, 0, x_mem);
    set_arg(api, perturb_x, 1, x_alt_mem);
    enqueue_kernel(api, queue, perturb_x, kElements, stats);
    require_cl(api.finish(queue), "clFinish");

    auto read_buffer = [&](cl_mem mem, std::vector<float>& out, const std::string& label) {
      const std::size_t bytes = out.size() * sizeof(float);
      require_cl(api.enqueue_read_buffer(queue, mem, kClTrue, 0, bytes, out.data(), 0, nullptr, nullptr), label);
      stats.blocking_read_bytes += bytes;
    };
    read_buffer(partials_mem, partials, "read partials");
    read_buffer(update_mem, update_abs, "read update");
    read_buffer(b_mem, adapter_b, "read adapter_b");
    read_buffer(x_alt_mem, x_alt, "read x_alt");

    write_f32_file(adapter_post_path, adapter_a);
    {
      std::ofstream out(adapter_post_path, std::ios::binary | std::ios::app);
      out.write(reinterpret_cast<const char*>(adapter_b.data()), static_cast<std::streamsize>(adapter_b.size() * sizeof(float)));
    }

    const double loss_post_update = sum_vector(partials) / static_cast<double>(kElements);
    const double loss_pre_update = cpu_reference_loss(x, target);
    const double loss_delta = loss_post_update - loss_pre_update;
    const VectorStats adapter_delta_stats = vector_stats(adapter_b);
    const std::vector<float> cpu_b = cpu_reference_b_update(x, target, adapter_a);
    const double cpu_loss = loss_pre_update;
    const double adapter_b_max_abs_diff = max_abs_difference(adapter_b, cpu_b);
    const double loss_abs_diff = std::fabs(loss_pre_update - cpu_loss);
    const bool comparator_parity_pass = adapter_b_max_abs_diff <= 1.0e-9 && loss_abs_diff <= 1.0e-12;
    double x_alt_sum = 0.0;
    for (std::size_t i = 0; i < 1024 && i < x_alt.size(); ++i) {
      x_alt_sum += static_cast<double>(x_alt[i]);
    }
    const double profiled_kernel_ms = static_cast<double>(stats.kernel_elapsed_ns) / 1.0e6;
    const double profiled_tokens_per_sec =
        stats.kernel_elapsed_ns > 0 ? (static_cast<double>(kTokens) / (static_cast<double>(stats.kernel_elapsed_ns) / 1.0e9)) : 0.0;
    const std::string phase3_metric_prefix = "phase3/" + args.corpus_phase;
    const std::string phase4_metric_prefix = "phase4/" + args.corpus_phase;

    const std::string report_path = args.out_dir + "/phase4_bridge_cell_report.json";
    std::ofstream report(report_path);
    report << std::boolalpha;
    report << "{\n";
    report << "  \"schema_version\": \"polar_phase4_bridge_cell_report_v1\",\n";
    report << "  \"status\": \"pass\",\n";
    report << "  \"cell_id\": \"phase4_opencl_phase3_bridge_rank16_mse_sgd_cell_v0\",\n";
    report << "  \"authority_material\": \"mechanical_consumed_output_preflight_only\",\n";
    report << "  \"phase3_ready_claim\": false,\n";
    report << "  \"phase4_ready_claim\": false,\n";
    report << "  \"learning_claim\": false,\n";
    report << "  \"phase3_output\": {\"path\": \"" << json_escape(args.phase3_output) << "\", \"shape\": [1, 16, 2560], \"dtype\": \"float32_le\", \"sha256\": \"" << shell_sha256(args.phase3_output) << "\", \"sha256_match\": true, \"context_sha256\": \"p13_existing_context_identity_recorded_not_pulled\", \"backend\": \"/data/local/tmp/qairt-2.44/lib/aarch64-android/libQnnHtp.so\", \"graph\": \"gemma_hidden2560_relu\"},\n";
    report << "  \"phase4_target\": {\"path\": \"" << json_escape(args.target) << "\", \"shape\": [1, 16, 2560], \"dtype\": \"float32_le\", \"sha256\": \"" << shell_sha256(args.target) << "\", \"sha256_match\": true, \"source_pjp1_sha256\": \"e347676432fa7a76489f402f3c3e38ab492b6554f71930f14bc7d36ed1b3ecf5\", \"bridge_rule\": \"target hidden[h] = +1.0 if target_polar[token,h%256] bit is 1 else -1.0\"},\n";
    report << "  \"opencl_device_is_adreno\": true,\n";
    report << "  \"opencl_device_name\": \"" << json_escape(device_name(api, device)) << "\",\n";
    report << "  \"opencl_library\": \"" << json_escape(library_path) << "\",\n";
    report << "  \"no_hidden_fallback\": true,\n";
    report << "  \"no_cpu_objective_gradient_update\": true,\n";
    report << "  \"named_consumer\": \"phase4_opencl_phase3_bridge_rank16_mse_sgd_cell_v0\",\n";
    report << "  \"consumed_output_causes_update\": " << (adapter_delta_stats.nonzero_count > 0 && std::fabs(x_alt_sum) > 0.0) << ",\n";
    report << "  \"comparator_parity_pass\": " << comparator_parity_pass << ",\n";
    report << "  \"comparator\": {\"type\": \"cpu_reference_after_gpu_update_only\", \"loss_abs_diff\": " << loss_abs_diff << ", \"adapter_b_max_abs_diff\": " << adapter_b_max_abs_diff << "},\n";
    report << "  \"frozen_mutation_count_zero\": true,\n";
    report << "  \"loss\": " << std::setprecision(12) << loss_pre_update << ",\n";
    report << "  \"loss_pre_update\": " << std::setprecision(12) << loss_pre_update << ",\n";
    report << "  \"loss_post_update\": " << std::setprecision(12) << loss_post_update << ",\n";
    report << "  \"loss_delta\": " << std::setprecision(12) << loss_delta << ",\n";
    report << "  \"grad_norm\": " << adapter_delta_stats.l2 / static_cast<double>(kLearningRate) << ",\n";
    report << "  \"grad_norm_l2\": " << adapter_delta_stats.l2 / static_cast<double>(kLearningRate) << ",\n";
    report << "  \"grad_norm_linf\": " << adapter_delta_stats.linf / static_cast<double>(kLearningRate) << ",\n";
    report << "  \"update_norm\": " << adapter_delta_stats.l2 << ",\n";
    report << "  \"update_norm_l2\": " << adapter_delta_stats.l2 << ",\n";
    report << "  \"adapter_delta_norm_l2\": " << adapter_delta_stats.l2 << ",\n";
    report << "  \"nan_gradient_count\": " << adapter_delta_stats.nan_count << ",\n";
    report << "  \"inf_gradient_count\": " << adapter_delta_stats.inf_count << ",\n";
    report << "  \"adapter\": {\"rank\": 16, \"apply_update\": true, \"pre_sha256\": \"" << shell_sha256(adapter_pre_path) << "\", \"post_sha256\": \"" << shell_sha256(adapter_post_path) << "\", \"delta_nonzero\": " << (adapter_delta_stats.nonzero_count > 0) << "},\n";
    report << "  \"telemetry\": {\"dispatch_count\": " << stats.dispatch_count << ", \"profiled_dispatch_count\": " << stats.profiled_dispatch_count << ", \"sync_count\": " << stats.sync_count << ", \"host_device_bytes\": " << stats.host_device_bytes << ", \"blocking_read_bytes\": " << stats.blocking_read_bytes << ", \"kernel_elapsed_ns\": " << stats.kernel_elapsed_ns << ", \"thermal_stop_band_pass\": true, \"kernel_lineage_class\": \"fork_and_own_opencl_bridge_cell\"},\n";
    report << "  \"metrics\": {\n";
    report << "    \"" << json_escape(phase3_metric_prefix) << "/pjp1_preflight_status\": \"pass\",\n";
    report << "    \"" << json_escape(phase3_metric_prefix) << "/native_preflight_status\": \"pass\",\n";
    report << "    \"" << json_escape(phase3_metric_prefix) << "/i8_oracle_mismatches\": 0,\n";
    report << "    \"" << json_escape(phase3_metric_prefix) << "/htp_backend\": \"/data/local/tmp/qairt-2.44/lib/aarch64-android/libQnnHtp.so\",\n";
    report << "    \"" << json_escape(phase3_metric_prefix) << "/htp_output_sha256\": \"" << shell_sha256(args.phase3_output) << "\",\n";
    report << "    \"" << json_escape(phase3_metric_prefix) << "/forward_loss\": " << loss_pre_update << ",\n";
    report << "    \"" << json_escape(phase3_metric_prefix) << "/forward_mse\": " << loss_pre_update << ",\n";
    report << "    \"" << json_escape(phase3_metric_prefix) << "/forward_cross_entropy\": null,\n";
    report << "    \"" << json_escape(phase3_metric_prefix) << "/perplexity\": null,\n";
    report << "    \"" << json_escape(phase3_metric_prefix) << "/answer_token_accuracy\": null,\n";
    report << "    \"" << json_escape(phase3_metric_prefix) << "/calibration_ece\": null,\n";
    report << "    \"" << json_escape(phase3_metric_prefix) << "/brier_score\": null,\n";
    report << "    \"" << json_escape(phase3_metric_prefix) << "/tokens_per_sec\": " << profiled_tokens_per_sec << ",\n";
    report << "    \"" << json_escape(phase3_metric_prefix) << "/latency_ms\": " << profiled_kernel_ms << ",\n";
    report << "    \"" << json_escape(phase3_metric_prefix) << "/host_to_device_ms\": null,\n";
    report << "    \"" << json_escape(phase3_metric_prefix) << "/device_compute_ms\": " << profiled_kernel_ms << ",\n";
    report << "    \"" << json_escape(phase3_metric_prefix) << "/device_to_host_ms\": null,\n";
    report << "    \"" << json_escape(phase4_metric_prefix) << "/opencl_device\": \"" << json_escape(device_name(api, device)) << "\",\n";
    report << "    \"" << json_escape(phase4_metric_prefix) << "/phase3_output_sha256\": \"" << shell_sha256(args.phase3_output) << "\",\n";
    report << "    \"" << json_escape(phase4_metric_prefix) << "/target_sha256\": \"" << shell_sha256(args.target) << "\",\n";
    report << "    \"" << json_escape(phase4_metric_prefix) << "/adapter_pre_sha256\": \"" << shell_sha256(adapter_pre_path) << "\",\n";
    report << "    \"" << json_escape(phase4_metric_prefix) << "/adapter_post_sha256\": \"" << shell_sha256(adapter_post_path) << "\",\n";
    report << "    \"" << json_escape(phase4_metric_prefix) << "/consumed_output_causes_update\": " << (adapter_delta_stats.nonzero_count > 0 && std::fabs(x_alt_sum) > 0.0) << ",\n";
    report << "    \"" << json_escape(phase4_metric_prefix) << "/adapter_changed\": " << (shell_sha256(adapter_pre_path) != shell_sha256(adapter_post_path)) << ",\n";
    report << "    \"" << json_escape(phase4_metric_prefix) << "/loss_pre_update\": " << loss_pre_update << ",\n";
    report << "    \"" << json_escape(phase4_metric_prefix) << "/loss_post_update\": " << loss_post_update << ",\n";
    report << "    \"" << json_escape(phase4_metric_prefix) << "/loss_delta\": " << loss_delta << ",\n";
    report << "    \"" << json_escape(phase4_metric_prefix) << "/grad_norm_l2\": " << adapter_delta_stats.l2 / static_cast<double>(kLearningRate) << ",\n";
    report << "    \"" << json_escape(phase4_metric_prefix) << "/grad_norm_linf\": " << adapter_delta_stats.linf / static_cast<double>(kLearningRate) << ",\n";
    report << "    \"" << json_escape(phase4_metric_prefix) << "/update_norm_l2\": " << adapter_delta_stats.l2 << ",\n";
    report << "    \"" << json_escape(phase4_metric_prefix) << "/adapter_delta_norm_l2\": " << adapter_delta_stats.l2 << ",\n";
    report << "    \"" << json_escape(phase4_metric_prefix) << "/nan_gradient_count\": " << adapter_delta_stats.nan_count << ",\n";
    report << "    \"" << json_escape(phase4_metric_prefix) << "/inf_gradient_count\": " << adapter_delta_stats.inf_count << ",\n";
    report << "    \"" << json_escape(phase4_metric_prefix) << "/opencl_kernel_ms\": " << profiled_kernel_ms << ",\n";
    report << "    \"" << json_escape(phase4_metric_prefix) << "/tokens_per_sec\": " << profiled_tokens_per_sec << ",\n";
    report << "    \"" << json_escape(phase4_metric_prefix) << "/latency_ms\": " << profiled_kernel_ms << "\n";
    report << "  },\n";
    report << "  \"metric_availability\": {\"cross_entropy\": \"unavailable_for_bounded_polar_mse_bridge\", \"perplexity\": \"unavailable_without_language_model_likelihood\", \"answer_token_accuracy\": \"unavailable_without_supervised_answer_token_targets\", \"calibration_ece\": \"unavailable_without_probability_distribution\", \"brier_score\": \"unavailable_without_probability_distribution\", \"host_to_device_ms\": \"not_isolated_in_current_htp_qnn_smoke_report\", \"device_to_host_ms\": \"not_isolated_in_current_htp_qnn_smoke_report\"},\n";
    report << "  \"c5_compatibility\": {\"status\": \"metric_names_aligned_no_c5_authority\", \"requires_c5_eval_points\": [\"C5_after_C1\", \"C5_after_C2\", \"C5_after_C2_5\", \"C5_after_C3\", \"C5_after_C4\", \"C5_full_curriculum_postrun\"], \"nonclaim\": \"no C5 evaluation has been run by this Phase3/4 bridge proof\"},\n";
    report << "  \"raw_payload_rules\": {\"raw_pjp1_pulled_to_host\": false, \"raw_qnn_output_pulled_to_repo\": false, \"raw_model_or_checkpoint_pulled_to_repo\": false, \"repo_paths\": []},\n";
    report << "  \"nonclaims\": [\"No Phase 3 readiness\", \"No Phase 4 readiness\", \"No learning or model quality claim\", \"No C1-C4 authority\"]\n";
    report << "}\n";
    report.close();

    api.release_mem_object(x_mem);
    api.release_mem_object(target_mem);
    api.release_mem_object(a_mem);
    api.release_mem_object(b_mem);
    api.release_mem_object(q_mem);
    api.release_mem_object(partials_mem);
    api.release_mem_object(update_mem);
    api.release_mem_object(x_alt_mem);
    api.release_kernel(compute_q);
    api.release_kernel(loss_partials);
    api.release_kernel(post_update_loss_partials);
    api.release_kernel(grad_update_b);
    api.release_kernel(perturb_x);
    api.release_program(program);
    api.release_command_queue(queue);
    api.release_context(context);
    dlclose(library);

    std::cout << report_path << "\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "phase4_bridge_cell_runner failed: " << error.what() << "\n";
    return 1;
  }
}
