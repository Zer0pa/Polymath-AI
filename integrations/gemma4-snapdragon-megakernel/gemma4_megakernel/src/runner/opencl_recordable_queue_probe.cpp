#include <dlfcn.h>
#include <sys/stat.h>
#include <unistd.h>

#include <cerrno>
#include <chrono>
#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "polymath/gemma4/json_writer.h"

namespace {

using cl_bool = std::uint32_t;
using cl_command_queue = void*;
using cl_command_queue_properties = std::uint64_t;
using cl_context = void*;
using cl_context_properties = intptr_t;
using cl_device_id = void*;
using cl_device_info = std::uint32_t;
using cl_device_type = std::uint64_t;
using cl_event = void*;
using cl_int = int;
using cl_kernel = void*;
using cl_mem = void*;
using cl_mem_flags = std::uint64_t;
using cl_platform_id = void*;
using cl_platform_info = std::uint32_t;
using cl_program = void*;
using cl_queue_info = std::uint32_t;
using cl_recording_qcom = void*;
using cl_uint = std::uint32_t;

constexpr cl_int kClSuccess = 0;
constexpr cl_bool kClTrue = 1;
constexpr cl_device_type kClDeviceTypeGpu = 1ULL << 2U;
constexpr cl_mem_flags kClMemReadWrite = 1ULL << 0U;
constexpr cl_mem_flags kClMemCopyHostPtr = 1ULL << 5U;
constexpr cl_platform_info kClPlatformProfile = 0x0900U;
constexpr cl_platform_info kClPlatformVersion = 0x0901U;
constexpr cl_platform_info kClPlatformName = 0x0902U;
constexpr cl_platform_info kClPlatformVendor = 0x0903U;
constexpr cl_platform_info kClPlatformExtensions = 0x0904U;
constexpr cl_device_info kClDeviceType = 0x1000U;
constexpr cl_device_info kClDeviceVendorId = 0x1001U;
constexpr cl_device_info kClDeviceMaxComputeUnits = 0x1002U;
constexpr cl_device_info kClDeviceName = 0x102BU;
constexpr cl_device_info kClDeviceVendor = 0x102CU;
constexpr cl_device_info kClDriverVersion = 0x102DU;
constexpr cl_device_info kClDeviceProfile = 0x102EU;
constexpr cl_device_info kClDeviceVersion = 0x102FU;
constexpr cl_device_info kClDeviceExtensions = 0x1030U;
constexpr cl_uint kClProgramBuildLog = 0x1183U;
constexpr cl_queue_info kClQueueProperties = 0x1093U;

struct ProbeArgs {
  std::string output_dir;
  int iterations = 200;
};

struct SymbolProbe {
  std::string name;
  bool dlsym_present = false;
  bool extension_address_present = false;
};

struct QueuePropertyTrial {
  std::uint64_t property = 0U;
  int create_error = 0;
  bool created = false;
  bool returned_property_contains_candidate = false;
  std::uint64_t returned_properties = 0U;
};

struct ClArrayArgQcom {
  cl_uint dispatch_index = 0U;
  cl_uint arg_index = 0U;
  std::size_t arg_size = 0U;
  const void* arg_value = nullptr;
};

struct ClWorkgroupQcom {
  cl_uint dispatch_index = 0U;
  const std::size_t* workgroup_size = nullptr;
};

struct ClOffsetQcom {
  cl_uint dispatch_index = 0U;
  std::size_t offsets[3] = {0U, 0U, 0U};
};

struct BenchmarkResult {
  std::string name;
  std::string status = "skipped";
  std::string reason;
  double ordinary_wall_seconds = 0.0;
  double recorded_wall_seconds = 0.0;
  double ordinary_dispatch_seconds = 0.0;
  double recorded_dispatch_seconds = 0.0;
  double speedup_ratio = 0.0;
  int iterations = 0;
  int ordinary_value = 0;
  int recorded_value = 0;
  bool ordinary_correct = false;
  bool recorded_correct = false;
};

template <typename Function>
Function resolve_required(void* library, const char* name) {
  void* symbol = dlsym(library, name);
  if (symbol == nullptr) {
    throw std::runtime_error(std::string("OpenCL missing symbol: ") + name);
  }
  return reinterpret_cast<Function>(symbol);
}

std::string qjson(const std::string& value) {
  std::ostringstream out;
  polymath::gemma4::write_json_string(out, value);
  return out.str();
}

std::string hex_u64(std::uint64_t value) {
  std::ostringstream out;
  out << "0x" << std::hex << std::nouppercase << value;
  return out.str();
}

std::string dirname_of(const std::string& path) {
  const std::size_t slash = path.find_last_of('/');
  if (slash == std::string::npos) {
    return ".";
  }
  if (slash == 0U) {
    return "/";
  }
  return path.substr(0, slash);
}

std::string join_path(const std::string& left, const std::string& right) {
  if (left.empty() || right.empty()) {
    return left.empty() ? right : left;
  }
  if (right.front() == '/') {
    return right;
  }
  if (left.back() == '/') {
    return left + right;
  }
  return left + "/" + right;
}

void ensure_directory(const std::string& path) {
  if (path.empty()) {
    return;
  }
  std::string current;
  for (const char character : path) {
    current.push_back(character);
    if (character != '/' || current.size() <= 1U) {
      continue;
    }
    if (::mkdir(current.c_str(), 0755) != 0 && errno != EEXIST) {
      throw std::runtime_error("mkdir failed for: " + current);
    }
  }
  if (::mkdir(path.c_str(), 0755) != 0 && errno != EEXIST) {
    throw std::runtime_error("mkdir failed for: " + path);
  }
}

void write_text_file(const std::string& path, const std::string& text) {
  ensure_directory(dirname_of(path));
  std::ofstream file(path);
  if (!file) {
    throw std::runtime_error("unable to write: " + path);
  }
  file << text;
}

bool extension_list_has(const std::string& extensions, const std::string& needle) {
  std::istringstream in(extensions);
  std::string token;
  while (in >> token) {
    if (token == needle) {
      return true;
    }
  }
  return false;
}

double seconds_since(std::chrono::steady_clock::time_point started_at) {
  const auto elapsed = std::chrono::steady_clock::now() - started_at;
  return std::chrono::duration<double>(elapsed).count();
}

void require_cl(cl_int error, const std::string& label) {
  if (error != kClSuccess) {
    throw std::runtime_error(label + " failed with OpenCL error " +
                             std::to_string(error));
  }
}

class DynamicLibrary {
 public:
  DynamicLibrary() {
    const char* candidates[] = {"libOpenCL.so", "/vendor/lib64/libOpenCL.so",
                                "/system/vendor/lib64/libOpenCL.so"};
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

struct OpenClApi {
  using Notify = void (*)(const char*, const void*, std::size_t, void*);
  using GetPlatformIDs = cl_int (*)(cl_uint, cl_platform_id*, cl_uint*);
  using GetPlatformInfo = cl_int (*)(cl_platform_id, cl_platform_info, std::size_t,
                                     void*, std::size_t*);
  using GetDeviceIDs = cl_int (*)(cl_platform_id, cl_device_type, cl_uint,
                                  cl_device_id*, cl_uint*);
  using GetDeviceInfo = cl_int (*)(cl_device_id, cl_device_info, std::size_t, void*,
                                   std::size_t*);
  using CreateContext = cl_context (*)(const cl_context_properties*, cl_uint,
                                       const cl_device_id*, Notify, void*, cl_int*);
  using CreateCommandQueue = cl_command_queue (*)(cl_context, cl_device_id,
                                                  cl_command_queue_properties,
                                                  cl_int*);
  using GetCommandQueueInfo = cl_int (*)(cl_command_queue, cl_queue_info,
                                         std::size_t, void*, std::size_t*);
  using CreateProgramWithSource = cl_program (*)(cl_context, cl_uint, const char**,
                                                 const std::size_t*, cl_int*);
  using BuildProgram = cl_int (*)(cl_program, cl_uint, const cl_device_id*,
                                  const char*, void (*)(cl_program, void*), void*);
  using GetProgramBuildInfo = cl_int (*)(cl_program, cl_device_id, cl_uint,
                                         std::size_t, void*, std::size_t*);
  using CreateKernel = cl_kernel (*)(cl_program, const char*, cl_int*);
  using SetKernelArg = cl_int (*)(cl_kernel, cl_uint, std::size_t, const void*);
  using CreateBuffer = cl_mem (*)(cl_context, cl_mem_flags, std::size_t, void*,
                                  cl_int*);
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
  using GetExtensionFunctionAddressForPlatform = void* (*)(cl_platform_id,
                                                           const char*);

  explicit OpenClApi(void* library)
      : get_platform_ids(resolve_required<GetPlatformIDs>(library, "clGetPlatformIDs")),
        get_platform_info(
            resolve_required<GetPlatformInfo>(library, "clGetPlatformInfo")),
        get_device_ids(resolve_required<GetDeviceIDs>(library, "clGetDeviceIDs")),
        get_device_info(resolve_required<GetDeviceInfo>(library, "clGetDeviceInfo")),
        create_context(resolve_required<CreateContext>(library, "clCreateContext")),
        create_command_queue(
            resolve_required<CreateCommandQueue>(library, "clCreateCommandQueue")),
        get_command_queue_info(resolve_required<GetCommandQueueInfo>(
            library, "clGetCommandQueueInfo")),
        create_program_with_source(resolve_required<CreateProgramWithSource>(
            library, "clCreateProgramWithSource")),
        build_program(resolve_required<BuildProgram>(library, "clBuildProgram")),
        get_program_build_info(resolve_required<GetProgramBuildInfo>(
            library, "clGetProgramBuildInfo")),
        create_kernel(resolve_required<CreateKernel>(library, "clCreateKernel")),
        set_kernel_arg(resolve_required<SetKernelArg>(library, "clSetKernelArg")),
        create_buffer(resolve_required<CreateBuffer>(library, "clCreateBuffer")),
        enqueue_nd_range_kernel(resolve_required<EnqueueNDRangeKernel>(
            library, "clEnqueueNDRangeKernel")),
        enqueue_read_buffer(resolve_required<EnqueueReadBuffer>(
            library, "clEnqueueReadBuffer")),
        finish(resolve_required<Finish>(library, "clFinish")),
        release_mem_object(
            resolve_required<ReleaseMemObject>(library, "clReleaseMemObject")),
        release_kernel(resolve_required<ReleaseKernel>(library, "clReleaseKernel")),
        release_program(
            resolve_required<ReleaseProgram>(library, "clReleaseProgram")),
        release_command_queue(resolve_required<ReleaseCommandQueue>(
            library, "clReleaseCommandQueue")),
        release_context(resolve_required<ReleaseContext>(library, "clReleaseContext")) {
    auto* function = dlsym(library, "clGetExtensionFunctionAddressForPlatform");
    get_extension_function_address_for_platform =
        reinterpret_cast<GetExtensionFunctionAddressForPlatform>(function);
  }

  GetPlatformIDs get_platform_ids;
  GetPlatformInfo get_platform_info;
  GetDeviceIDs get_device_ids;
  GetDeviceInfo get_device_info;
  CreateContext create_context;
  CreateCommandQueue create_command_queue;
  GetCommandQueueInfo get_command_queue_info;
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
  GetExtensionFunctionAddressForPlatform get_extension_function_address_for_platform =
      nullptr;
};

class OpenClObjects {
 public:
  explicit OpenClObjects(const OpenClApi& api) : api_(api) {}

  ~OpenClObjects() {
    for (cl_kernel kernel : kernels_) {
      api_.release_kernel(kernel);
    }
    if (program_ != nullptr) {
      api_.release_program(program_);
    }
    for (cl_mem buffer : buffers_) {
      api_.release_mem_object(buffer);
    }
    for (cl_command_queue queue : queues_) {
      api_.release_command_queue(queue);
    }
    if (context_ != nullptr) {
      api_.release_context(context_);
    }
  }

  OpenClObjects(const OpenClObjects&) = delete;
  OpenClObjects& operator=(const OpenClObjects&) = delete;

  cl_platform_id select_platform() const {
    cl_uint count = 0U;
    require_cl(api_.get_platform_ids(0U, nullptr, &count), "clGetPlatformIDs count");
    if (count == 0U) {
      throw std::runtime_error("OpenCL reports zero platforms");
    }
    std::vector<cl_platform_id> platforms(count);
    require_cl(api_.get_platform_ids(count, platforms.data(), nullptr),
               "clGetPlatformIDs list");
    return platforms.front();
  }

  cl_device_id select_gpu_device(cl_platform_id platform) const {
    cl_uint count = 0U;
    require_cl(api_.get_device_ids(platform, kClDeviceTypeGpu, 0U, nullptr, &count),
               "clGetDeviceIDs count");
    if (count == 0U) {
      throw std::runtime_error("OpenCL reports zero GPU devices");
    }
    std::vector<cl_device_id> devices(count);
    require_cl(api_.get_device_ids(platform, kClDeviceTypeGpu, count, devices.data(),
                                   nullptr),
               "clGetDeviceIDs list");
    return devices.front();
  }

  void create_context_and_queue(cl_device_id device) {
    cl_int error = kClSuccess;
    context_ = api_.create_context(nullptr, 1U, &device, nullptr, nullptr, &error);
    require_cl(error, "clCreateContext");
    live_queue_ = create_queue(device, 0U, true);
  }

  cl_command_queue create_queue(cl_device_id device,
                                cl_command_queue_properties properties,
                                bool retain) {
    cl_int error = kClSuccess;
    cl_command_queue queue = api_.create_command_queue(context_, device, properties, &error);
    require_cl(error, "clCreateCommandQueue");
    if (retain) {
      queues_.push_back(queue);
    }
    return queue;
  }

  cl_mem create_int_buffer(int initial_value) {
    int value = initial_value;
    cl_int error = kClSuccess;
    cl_mem buffer = api_.create_buffer(context_, kClMemReadWrite | kClMemCopyHostPtr,
                                       sizeof(value), &value, &error);
    require_cl(error, "clCreateBuffer");
    buffers_.push_back(buffer);
    return buffer;
  }

  void build_program(cl_device_id device, const char* source) {
    cl_int error = kClSuccess;
    const char* sources[] = {source};
    program_ = api_.create_program_with_source(context_, 1U, sources, nullptr, &error);
    require_cl(error, "clCreateProgramWithSource");
    const cl_int build_error =
        api_.build_program(program_, 1U, &device, nullptr, nullptr, nullptr);
    if (build_error != kClSuccess) {
      throw std::runtime_error("clBuildProgram failed: " + program_build_log(device));
    }
  }

  cl_kernel create_kernel(const char* name) {
    cl_int error = kClSuccess;
    cl_kernel kernel = api_.create_kernel(program_, name, &error);
    require_cl(error, std::string("clCreateKernel ") + name);
    kernels_.push_back(kernel);
    return kernel;
  }

  int read_int(cl_mem buffer) const {
    int value = 0;
    require_cl(api_.enqueue_read_buffer(live_queue_, buffer, kClTrue, 0U, sizeof(value),
                                        &value, 0U, nullptr, nullptr),
               "clEnqueueReadBuffer");
    return value;
  }

  cl_command_queue live_queue() const { return live_queue_; }
  cl_context context() const { return context_; }

 private:
  std::string program_build_log(cl_device_id device) const {
    std::size_t size = 0U;
    api_.get_program_build_info(program_, device, kClProgramBuildLog, 0U, nullptr,
                                &size);
    std::string log(size, '\0');
    if (size > 0U) {
      api_.get_program_build_info(program_, device, kClProgramBuildLog, size,
                                  log.data(), nullptr);
    }
    return log;
  }

  const OpenClApi& api_;
  cl_context context_ = nullptr;
  cl_command_queue live_queue_ = nullptr;
  cl_program program_ = nullptr;
  std::vector<cl_command_queue> queues_;
  std::vector<cl_mem> buffers_;
  std::vector<cl_kernel> kernels_;
};

std::string platform_string(const OpenClApi& api, cl_platform_id platform,
                            cl_platform_info param) {
  std::size_t size = 0U;
  require_cl(api.get_platform_info(platform, param, 0U, nullptr, &size),
             "clGetPlatformInfo size");
  std::string value(size, '\0');
  if (size > 0U) {
    require_cl(api.get_platform_info(platform, param, size, value.data(), nullptr),
               "clGetPlatformInfo value");
  }
  while (!value.empty() && value.back() == '\0') {
    value.pop_back();
  }
  return value;
}

std::string device_string(const OpenClApi& api, cl_device_id device,
                          cl_device_info param) {
  std::size_t size = 0U;
  require_cl(api.get_device_info(device, param, 0U, nullptr, &size),
             "clGetDeviceInfo size");
  std::string value(size, '\0');
  if (size > 0U) {
    require_cl(api.get_device_info(device, param, size, value.data(), nullptr),
               "clGetDeviceInfo value");
  }
  while (!value.empty() && value.back() == '\0') {
    value.pop_back();
  }
  return value;
}

template <typename T>
T device_scalar(const OpenClApi& api, cl_device_id device, cl_device_info param) {
  T value {};
  require_cl(api.get_device_info(device, param, sizeof(value), &value, nullptr),
             "clGetDeviceInfo scalar");
  return value;
}

std::vector<SymbolProbe> probe_symbols(void* library, const OpenClApi& api,
                                       cl_platform_id platform) {
  const char* names[] = {"clNewRecordingQCOM", "clEndRecordingQCOM",
                         "clReleaseRecordingQCOM", "clRetainRecordingQCOM",
                         "clEnqueueRecordingQCOM", "clEnqueueRecordingSVMQCOM"};
  std::vector<SymbolProbe> probes;
  for (const char* name : names) {
    SymbolProbe probe;
    probe.name = name;
    probe.dlsym_present = dlsym(library, name) != nullptr;
    if (api.get_extension_function_address_for_platform != nullptr) {
      probe.extension_address_present =
          api.get_extension_function_address_for_platform(platform, name) != nullptr;
    }
    probes.push_back(probe);
  }
  return probes;
}

std::vector<QueuePropertyTrial> scan_queue_properties(const OpenClApi& api,
                                                      OpenClObjects& objects,
                                                      cl_device_id device) {
  std::vector<QueuePropertyTrial> trials;
  for (int bit = 2; bit < 64; ++bit) {
    const std::uint64_t property = 1ULL << static_cast<unsigned>(bit);
    QueuePropertyTrial trial;
    trial.property = property;
    cl_int error = kClSuccess;
    cl_command_queue queue =
        api.create_command_queue(objects.context(), device, property, &error);
    trial.create_error = error;
    trial.created = queue != nullptr && error == kClSuccess;
    if (trial.created) {
      cl_command_queue_properties returned = 0U;
      const cl_int info_error = api.get_command_queue_info(
          queue, kClQueueProperties, sizeof(returned), &returned, nullptr);
      if (info_error == kClSuccess) {
        trial.returned_properties = returned;
        trial.returned_property_contains_candidate = (returned & property) == property;
      }
      api.release_command_queue(queue);
    }
    trials.push_back(trial);
  }
  return trials;
}

std::uint64_t selected_queue_property(const std::vector<QueuePropertyTrial>& trials) {
  for (const QueuePropertyTrial& trial : trials) {
    if (trial.created && trial.returned_property_contains_candidate) {
      return trial.property;
    }
  }
  return 0U;
}

std::string benchmark_status_json(const BenchmarkResult& result) {
  std::ostringstream out;
  out << "{\n";
  out << "  \"name\": " << qjson(result.name) << ",\n";
  out << "  \"status\": " << qjson(result.status) << ",\n";
  out << "  \"reason\": " << qjson(result.reason) << ",\n";
  out << "  \"iterations\": " << result.iterations << ",\n";
  out << "  \"ordinary_wall_seconds\": " << std::setprecision(10)
      << result.ordinary_wall_seconds << ",\n";
  out << "  \"recorded_wall_seconds\": " << std::setprecision(10)
      << result.recorded_wall_seconds << ",\n";
  out << "  \"ordinary_dispatch_seconds\": " << std::setprecision(10)
      << result.ordinary_dispatch_seconds << ",\n";
  out << "  \"recorded_dispatch_seconds\": " << std::setprecision(10)
      << result.recorded_dispatch_seconds << ",\n";
  out << "  \"speedup_ratio\": " << std::setprecision(10) << result.speedup_ratio
      << ",\n";
  out << "  \"ordinary_value\": " << result.ordinary_value << ",\n";
  out << "  \"recorded_value\": " << result.recorded_value << ",\n";
  out << "  \"ordinary_correct\": " << (result.ordinary_correct ? "true" : "false")
      << ",\n";
  out << "  \"recorded_correct\": " << (result.recorded_correct ? "true" : "false")
      << "\n";
  out << "}";
  return out.str();
}

using NewRecordingQCOM = cl_recording_qcom (*)(cl_command_queue, cl_int*);
using EndRecordingQCOM = cl_int (*)(cl_recording_qcom);
using ReleaseRecordingQCOM = cl_int (*)(cl_recording_qcom);
using EnqueueRecordingQCOM =
    cl_int (*)(cl_command_queue, cl_recording_qcom, std::size_t,
               const ClArrayArgQcom*, std::size_t, const ClOffsetQcom*,
               std::size_t, const ClWorkgroupQcom*, std::size_t,
               const ClWorkgroupQcom*, cl_uint, const cl_event*, cl_event*);

void run_ordinary_kernel(const OpenClApi& api, cl_command_queue queue,
                         cl_kernel kernel, int iterations) {
  const std::size_t global[] = {1U};
  for (int index = 0; index < iterations; ++index) {
    require_cl(api.enqueue_nd_range_kernel(queue, kernel, 1U, nullptr, global, nullptr,
                                           0U, nullptr, nullptr),
               "ordinary clEnqueueNDRangeKernel");
    require_cl(api.finish(queue), "ordinary clFinish");
  }
}

void run_ordinary_kernel_with_arg_update(const OpenClApi& api, cl_command_queue queue,
                                         cl_kernel kernel, int update_value,
                                         int iterations) {
  const std::size_t global[] = {1U};
  for (int index = 0; index < iterations; ++index) {
    require_cl(api.set_kernel_arg(kernel, 1U, sizeof(update_value), &update_value),
               "ordinary mutable clSetKernelArg");
    require_cl(api.enqueue_nd_range_kernel(queue, kernel, 1U, nullptr, global, nullptr,
                                           0U, nullptr, nullptr),
               "ordinary mutable clEnqueueNDRangeKernel");
    require_cl(api.finish(queue), "ordinary mutable clFinish");
  }
}

void run_recorded_kernel(const OpenClApi& api, cl_command_queue live_queue,
                         cl_recording_qcom recording,
                         EnqueueRecordingQCOM enqueue_recording,
                         int iterations) {
  for (int index = 0; index < iterations; ++index) {
    const cl_int error =
        enqueue_recording(live_queue, recording, 0U, nullptr, 0U, nullptr, 0U, nullptr,
                          0U, nullptr, 0U, nullptr, nullptr);
    require_cl(error, "clEnqueueRecordingQCOM");
    require_cl(api.finish(live_queue), "recorded clFinish");
  }
}

void run_recorded_kernel_with_arg_update(const OpenClApi& api,
                                         cl_command_queue live_queue,
                                         cl_recording_qcom recording,
                                         EnqueueRecordingQCOM enqueue_recording,
                                         int update_value, int iterations) {
  ClArrayArgQcom update;
  update.dispatch_index = 0U;
  update.arg_index = 1U;
  update.arg_size = sizeof(update_value);
  update.arg_value = &update_value;
  for (int index = 0; index < iterations; ++index) {
    const cl_int error =
        enqueue_recording(live_queue, recording, 1U, &update, 0U, nullptr, 0U, nullptr,
                          0U, nullptr, 0U, nullptr, nullptr);
    require_cl(error, "mutable clEnqueueRecordingQCOM");
    require_cl(api.finish(live_queue), "mutable recorded clFinish");
  }
}

BenchmarkResult benchmark_recording(void* library_handle, const OpenClApi& api,
                                    OpenClObjects& objects,
                                    cl_device_id device, std::uint64_t property,
                                    const std::string& name, cl_kernel ordinary_kernel,
                                    cl_kernel recorded_kernel, cl_mem ordinary_buffer,
                                    cl_mem recorded_buffer, int iterations,
                                    bool expect_increment) {
  BenchmarkResult result;
  result.name = name;
  result.iterations = iterations;

  auto* new_recording =
      reinterpret_cast<NewRecordingQCOM>(dlsym(library_handle, "clNewRecordingQCOM"));
  auto* end_recording =
      reinterpret_cast<EndRecordingQCOM>(dlsym(library_handle, "clEndRecordingQCOM"));
  auto* release_recording = reinterpret_cast<ReleaseRecordingQCOM>(
      dlsym(library_handle, "clReleaseRecordingQCOM"));
  auto* enqueue_recording = reinterpret_cast<EnqueueRecordingQCOM>(
      dlsym(library_handle, "clEnqueueRecordingQCOM"));
  if (new_recording == nullptr || end_recording == nullptr ||
      enqueue_recording == nullptr) {
    result.status = "skipped";
    result.reason = "recordable queue functions are not visible through dlsym";
    return result;
  }

  try {
    const auto ordinary_start = std::chrono::steady_clock::now();
    run_ordinary_kernel(api, objects.live_queue(), ordinary_kernel, iterations);
    result.ordinary_wall_seconds = seconds_since(ordinary_start);
    result.ordinary_dispatch_seconds =
        result.ordinary_wall_seconds / static_cast<double>(iterations);
    result.ordinary_value = objects.read_int(ordinary_buffer);

    cl_int error = kClSuccess;
    cl_command_queue recordable_queue =
        api.create_command_queue(objects.context(), device, property, &error);
    require_cl(error, "clCreateCommandQueue recordable");
    cl_recording_qcom recording = new_recording(recordable_queue, &error);
    require_cl(error, "clNewRecordingQCOM");
    if (recording == nullptr) {
      throw std::runtime_error("clNewRecordingQCOM returned null recording");
    }
    const std::size_t global[] = {1U};
    require_cl(api.enqueue_nd_range_kernel(recordable_queue, recorded_kernel, 1U,
                                           nullptr, global, nullptr, 0U, nullptr,
                                           nullptr),
               "recording clEnqueueNDRangeKernel");
    require_cl(end_recording(recording), "clEndRecordingQCOM");

    const auto recorded_start = std::chrono::steady_clock::now();
    run_recorded_kernel(api, objects.live_queue(), recording, enqueue_recording,
                        iterations);
    result.recorded_wall_seconds = seconds_since(recorded_start);
    result.recorded_dispatch_seconds =
        result.recorded_wall_seconds / static_cast<double>(iterations);
    result.recorded_value = objects.read_int(recorded_buffer);
    if (release_recording != nullptr) {
      release_recording(recording);
    }
    api.release_command_queue(recordable_queue);

    const int expected = expect_increment ? iterations : 0;
    result.ordinary_correct = result.ordinary_value == expected;
    result.recorded_correct = result.recorded_value == expected;
    result.speedup_ratio = result.recorded_wall_seconds > 0.0
                               ? result.ordinary_wall_seconds / result.recorded_wall_seconds
                               : 0.0;
    result.status =
        (result.ordinary_correct && result.recorded_correct) ? "completed" : "failed";
    result.reason = result.status == "completed" ? "" : "ordinary or recorded output drift";
  } catch (const std::exception& error) {
    result.status = "failed";
    result.reason = error.what();
  }
  return result;
}

BenchmarkResult benchmark_mutable_recording(void* library_handle, const OpenClApi& api,
                                            OpenClObjects& objects,
                                            cl_device_id device,
                                            std::uint64_t property,
                                            cl_kernel ordinary_kernel,
                                            cl_kernel recorded_kernel,
                                            cl_mem ordinary_buffer,
                                            cl_mem recorded_buffer,
                                            int iterations) {
  BenchmarkResult result;
  result.name = "mutable_arg_recorded_add";
  result.iterations = iterations;
  constexpr int kRecordedValue = 1;
  constexpr int kUpdatedValue = 3;

  auto* new_recording =
      reinterpret_cast<NewRecordingQCOM>(dlsym(library_handle, "clNewRecordingQCOM"));
  auto* end_recording =
      reinterpret_cast<EndRecordingQCOM>(dlsym(library_handle, "clEndRecordingQCOM"));
  auto* release_recording = reinterpret_cast<ReleaseRecordingQCOM>(
      dlsym(library_handle, "clReleaseRecordingQCOM"));
  auto* enqueue_recording = reinterpret_cast<EnqueueRecordingQCOM>(
      dlsym(library_handle, "clEnqueueRecordingQCOM"));
  if (new_recording == nullptr || end_recording == nullptr ||
      enqueue_recording == nullptr) {
    result.status = "skipped";
    result.reason = "recordable queue functions are not visible through dlsym";
    return result;
  }

  try {
    const auto ordinary_start = std::chrono::steady_clock::now();
    run_ordinary_kernel_with_arg_update(api, objects.live_queue(), ordinary_kernel,
                                        kUpdatedValue, iterations);
    result.ordinary_wall_seconds = seconds_since(ordinary_start);
    result.ordinary_dispatch_seconds =
        result.ordinary_wall_seconds / static_cast<double>(iterations);
    result.ordinary_value = objects.read_int(ordinary_buffer);

    cl_int error = kClSuccess;
    cl_command_queue recordable_queue =
        api.create_command_queue(objects.context(), device, property, &error);
    require_cl(error, "clCreateCommandQueue mutable recordable");
    cl_recording_qcom recording = new_recording(recordable_queue, &error);
    require_cl(error, "mutable clNewRecordingQCOM");
    if (recording == nullptr) {
      throw std::runtime_error("mutable clNewRecordingQCOM returned null recording");
    }
    require_cl(api.set_kernel_arg(recorded_kernel, 1U, sizeof(kRecordedValue),
                                  &kRecordedValue),
               "mutable recorded initial clSetKernelArg");
    const std::size_t global[] = {1U};
    require_cl(api.enqueue_nd_range_kernel(recordable_queue, recorded_kernel, 1U,
                                           nullptr, global, nullptr, 0U, nullptr,
                                           nullptr),
               "mutable recording clEnqueueNDRangeKernel");
    require_cl(end_recording(recording), "mutable clEndRecordingQCOM");

    const auto recorded_start = std::chrono::steady_clock::now();
    run_recorded_kernel_with_arg_update(api, objects.live_queue(), recording,
                                        enqueue_recording, kUpdatedValue, iterations);
    result.recorded_wall_seconds = seconds_since(recorded_start);
    result.recorded_dispatch_seconds =
        result.recorded_wall_seconds / static_cast<double>(iterations);
    result.recorded_value = objects.read_int(recorded_buffer);
    if (release_recording != nullptr) {
      release_recording(recording);
    }
    api.release_command_queue(recordable_queue);

    const int expected = iterations * kUpdatedValue;
    result.ordinary_correct = result.ordinary_value == expected;
    result.recorded_correct = result.recorded_value == expected;
    result.speedup_ratio = result.recorded_wall_seconds > 0.0
                               ? result.ordinary_wall_seconds / result.recorded_wall_seconds
                               : 0.0;
    result.status =
        (result.ordinary_correct && result.recorded_correct) ? "completed" : "failed";
    result.reason =
        result.status == "completed" ? "" : "mutable recorded output did not match update";
  } catch (const std::exception& error) {
    result.status = "failed";
    result.reason = error.what();
  }
  return result;
}

std::string extension_dump_json(const std::string& library_path,
                                const std::string& platform_profile,
                                const std::string& platform_version,
                                const std::string& platform_name,
                                const std::string& platform_vendor,
                                const std::string& platform_extensions,
                                const std::string& device_name,
                                const std::string& device_vendor,
                                const std::string& device_version,
                                const std::string& driver_version,
                                const std::string& device_profile,
                                const std::string& device_extensions,
                                cl_device_type device_type, cl_uint vendor_id,
                                cl_uint compute_units, bool supported) {
  std::ostringstream out;
  out << "{\n";
  out << "  \"schema_version\": \"phase11_h11d_extension_dump_v1\",\n";
  out << "  \"library_path\": " << qjson(library_path) << ",\n";
  out << "  \"target_extension\": \"cl_qcom_recordable_queues\",\n";
  out << "  \"recordable_queues_supported\": "
      << (supported ? "true" : "false") << ",\n";
  out << "  \"platform\": {\n";
  out << "    \"profile\": " << qjson(platform_profile) << ",\n";
  out << "    \"version\": " << qjson(platform_version) << ",\n";
  out << "    \"name\": " << qjson(platform_name) << ",\n";
  out << "    \"vendor\": " << qjson(platform_vendor) << ",\n";
  out << "    \"extensions\": " << qjson(platform_extensions) << "\n";
  out << "  },\n";
  out << "  \"device\": {\n";
  out << "    \"name\": " << qjson(device_name) << ",\n";
  out << "    \"vendor\": " << qjson(device_vendor) << ",\n";
  out << "    \"version\": " << qjson(device_version) << ",\n";
  out << "    \"driver_version\": " << qjson(driver_version) << ",\n";
  out << "    \"profile\": " << qjson(device_profile) << ",\n";
  out << "    \"type\": " << device_type << ",\n";
  out << "    \"vendor_id\": " << vendor_id << ",\n";
  out << "    \"max_compute_units\": " << compute_units << ",\n";
  out << "    \"extensions\": " << qjson(device_extensions) << "\n";
  out << "  }\n";
  out << "}\n";
  return out.str();
}

std::string symbol_probe_json(const std::vector<SymbolProbe>& probes) {
  std::ostringstream out;
  out << "{\n";
  out << "  \"schema_version\": \"phase11_h11d_symbol_probe_v1\",\n";
  out << "  \"symbols\": [\n";
  for (std::size_t index = 0; index < probes.size(); ++index) {
    const SymbolProbe& probe = probes[index];
    out << "    {\"name\": " << qjson(probe.name)
        << ", \"dlsym_present\": " << (probe.dlsym_present ? "true" : "false")
        << ", \"extension_address_present\": "
        << (probe.extension_address_present ? "true" : "false") << "}";
    out << (index + 1U == probes.size() ? "\n" : ",\n");
  }
  out << "  ]\n";
  out << "}\n";
  return out.str();
}

std::string queue_scan_json(const std::vector<QueuePropertyTrial>& trials,
                            std::uint64_t selected) {
  std::ostringstream out;
  out << "{\n";
  out << "  \"schema_version\": \"phase11_h11d_queue_property_scan_v1\",\n";
  out << "  \"selected_recordable_property\": " << qjson(hex_u64(selected)) << ",\n";
  out << "  \"trials\": [\n";
  for (std::size_t index = 0; index < trials.size(); ++index) {
    const QueuePropertyTrial& trial = trials[index];
    out << "    {\"property\": " << qjson(hex_u64(trial.property))
        << ", \"create_error\": " << trial.create_error
        << ", \"created\": " << (trial.created ? "true" : "false")
        << ", \"returned_properties\": " << qjson(hex_u64(trial.returned_properties))
        << ", \"returned_property_contains_candidate\": "
        << (trial.returned_property_contains_candidate ? "true" : "false") << "}";
    out << (index + 1U == trials.size() ? "\n" : ",\n");
  }
  out << "  ]\n";
  out << "}\n";
  return out.str();
}

std::string microbenchmark_json(const BenchmarkResult& noop,
                                const BenchmarkResult& fixed,
                                const BenchmarkResult& mutable_result) {
  std::ostringstream out;
  out << "{\n";
  out << "  \"schema_version\": \"phase11_h11d_microbenchmark_v1\",\n";
  out << "  \"ordinary_queue_mode\": \"clCreateCommandQueue properties=0\",\n";
  out << "  \"recorded_queue_mode\": \"cl_qcom_recordable_queues recording replay\",\n";
  out << "  \"benchmarks\": [\n";
  out << benchmark_status_json(noop) << ",\n";
  out << benchmark_status_json(fixed) << ",\n";
  out << benchmark_status_json(mutable_result) << "\n";
  out << "  ],\n";
  out << "  \"mutable_arg_benchmark_skipped\": "
      << (mutable_result.status == "skipped" ? "true" : "false") << "\n";
  out << "}\n";
  return out.str();
}

std::string output_comparison_json(const BenchmarkResult& noop,
                                   const BenchmarkResult& fixed,
                                   const BenchmarkResult& mutable_result) {
  std::ostringstream out;
  out << "{\n";
  out << "  \"schema_version\": \"phase11_h11d_output_comparison_v1\",\n";
  out << "  \"noop_outputs_match\": "
      << (noop.ordinary_correct && noop.recorded_correct ? "true" : "false")
      << ",\n";
  out << "  \"fixed_arg_outputs_match\": "
      << (fixed.ordinary_correct && fixed.recorded_correct ? "true" : "false")
      << ",\n";
  out << "  \"mutable_arg_outputs_match\": "
      << (mutable_result.ordinary_correct && mutable_result.recorded_correct ? "true" : "false")
      << ",\n";
  out << "  \"ordinary_fixed_value\": " << fixed.ordinary_value << ",\n";
  out << "  \"recorded_fixed_value\": " << fixed.recorded_value << ",\n";
  out << "  \"ordinary_mutable_value\": " << mutable_result.ordinary_value << ",\n";
  out << "  \"recorded_mutable_value\": " << mutable_result.recorded_value << ",\n";
  out << "  \"ordinary_noop_value\": " << noop.ordinary_value << ",\n";
  out << "  \"recorded_noop_value\": " << noop.recorded_value << "\n";
  out << "}\n";
  return out.str();
}

void run_probe(const ProbeArgs& args) {
  ensure_directory(args.output_dir);
  DynamicLibrary library;
  const OpenClApi api(library.handle());
  OpenClObjects objects(api);
  const cl_platform_id platform = objects.select_platform();
  const cl_device_id device = objects.select_gpu_device(platform);

  const std::string platform_profile =
      platform_string(api, platform, kClPlatformProfile);
  const std::string platform_version =
      platform_string(api, platform, kClPlatformVersion);
  const std::string platform_name = platform_string(api, platform, kClPlatformName);
  const std::string platform_vendor =
      platform_string(api, platform, kClPlatformVendor);
  const std::string platform_extensions =
      platform_string(api, platform, kClPlatformExtensions);
  const std::string device_name = device_string(api, device, kClDeviceName);
  const std::string device_vendor = device_string(api, device, kClDeviceVendor);
  const std::string device_version = device_string(api, device, kClDeviceVersion);
  const std::string driver_version = device_string(api, device, kClDriverVersion);
  const std::string device_profile = device_string(api, device, kClDeviceProfile);
  const std::string device_extensions = device_string(api, device, kClDeviceExtensions);
  const cl_device_type device_type =
      device_scalar<cl_device_type>(api, device, kClDeviceType);
  const cl_uint vendor_id = device_scalar<cl_uint>(api, device, kClDeviceVendorId);
  const cl_uint compute_units =
      device_scalar<cl_uint>(api, device, kClDeviceMaxComputeUnits);
  const bool supported =
      extension_list_has(platform_extensions, "cl_qcom_recordable_queues") ||
      extension_list_has(device_extensions, "cl_qcom_recordable_queues");

  write_text_file(join_path(args.output_dir, "extension_dump.json"),
                  extension_dump_json(library.loaded_path(), platform_profile,
                                      platform_version, platform_name,
                                      platform_vendor, platform_extensions,
                                      device_name, device_vendor, device_version,
                                      driver_version, device_profile,
                                      device_extensions, device_type, vendor_id,
                                      compute_units, supported));
  const std::vector<SymbolProbe> symbols =
      probe_symbols(library.handle(), api, platform);
  write_text_file(join_path(args.output_dir, "symbol_probe.json"),
                  symbol_probe_json(symbols));

  if (!supported) {
    const BenchmarkResult skipped_noop{
        "noop_recorded_sequence", "skipped",
        "cl_qcom_recordable_queues is not advertised by platform or device"};
    const BenchmarkResult skipped_fixed{
        "fixed_arg_recorded_add", "skipped",
        "cl_qcom_recordable_queues is not advertised by platform or device"};
    const BenchmarkResult skipped_mutable{
        "mutable_arg_recorded_add", "skipped",
        "cl_qcom_recordable_queues is not advertised by platform or device"};
    write_text_file(join_path(args.output_dir, "queue_property_scan.json"),
                    queue_scan_json({}, 0U));
    write_text_file(join_path(args.output_dir, "microbenchmark.json"),
                    microbenchmark_json(skipped_noop, skipped_fixed, skipped_mutable));
    write_text_file(join_path(args.output_dir, "output_comparison.json"),
                    output_comparison_json(skipped_noop, skipped_fixed, skipped_mutable));
    return;
  }

  objects.create_context_and_queue(device);
  const std::vector<QueuePropertyTrial> trials =
      scan_queue_properties(api, objects, device);
  const std::uint64_t recordable_property = selected_queue_property(trials);
  write_text_file(join_path(args.output_dir, "queue_property_scan.json"),
                  queue_scan_json(trials, recordable_property));
  if (recordable_property == 0U) {
    const BenchmarkResult skipped_noop{
        "noop_recorded_sequence", "skipped",
        "no non-standard queue property bit was accepted and echoed by CL_QUEUE_PROPERTIES"};
    const BenchmarkResult skipped_fixed{
        "fixed_arg_recorded_add", "skipped",
        "no non-standard queue property bit was accepted and echoed by CL_QUEUE_PROPERTIES"};
    const BenchmarkResult skipped_mutable{
        "mutable_arg_recorded_add", "skipped",
        "no non-standard queue property bit was accepted and echoed by CL_QUEUE_PROPERTIES"};
    write_text_file(join_path(args.output_dir, "microbenchmark.json"),
                    microbenchmark_json(skipped_noop, skipped_fixed, skipped_mutable));
    write_text_file(join_path(args.output_dir, "output_comparison.json"),
                    output_comparison_json(skipped_noop, skipped_fixed, skipped_mutable));
    return;
  }

  const char* source = R"CLC(
__kernel void add_value(__global int* data, int value) {
  data[get_global_id(0)] += value;
}
__kernel void noop_value(__global int* data) {
  if (get_global_id(0) == 0) {
    data[0] += 0;
  }
}
)CLC";
  objects.build_program(device, source);

  cl_kernel ordinary_add = objects.create_kernel("add_value");
  cl_kernel recorded_add = objects.create_kernel("add_value");
  cl_kernel ordinary_mutable_add = objects.create_kernel("add_value");
  cl_kernel recorded_mutable_add = objects.create_kernel("add_value");
  cl_kernel ordinary_noop = objects.create_kernel("noop_value");
  cl_kernel recorded_noop = objects.create_kernel("noop_value");
  cl_mem ordinary_add_buffer = objects.create_int_buffer(0);
  cl_mem recorded_add_buffer = objects.create_int_buffer(0);
  cl_mem ordinary_mutable_buffer = objects.create_int_buffer(0);
  cl_mem recorded_mutable_buffer = objects.create_int_buffer(0);
  cl_mem ordinary_noop_buffer = objects.create_int_buffer(0);
  cl_mem recorded_noop_buffer = objects.create_int_buffer(0);
  int one = 1;
  require_cl(api.set_kernel_arg(ordinary_add, 0U, sizeof(ordinary_add_buffer),
                                &ordinary_add_buffer),
             "clSetKernelArg ordinary add buffer");
  require_cl(api.set_kernel_arg(ordinary_add, 1U, sizeof(one), &one),
             "clSetKernelArg ordinary add value");
  require_cl(api.set_kernel_arg(recorded_add, 0U, sizeof(recorded_add_buffer),
                                &recorded_add_buffer),
             "clSetKernelArg recorded add buffer");
  require_cl(api.set_kernel_arg(recorded_add, 1U, sizeof(one), &one),
             "clSetKernelArg recorded add value");
  require_cl(api.set_kernel_arg(ordinary_mutable_add, 0U,
                                sizeof(ordinary_mutable_buffer),
                                &ordinary_mutable_buffer),
             "clSetKernelArg ordinary mutable buffer");
  require_cl(api.set_kernel_arg(ordinary_mutable_add, 1U, sizeof(one), &one),
             "clSetKernelArg ordinary mutable initial value");
  require_cl(api.set_kernel_arg(recorded_mutable_add, 0U,
                                sizeof(recorded_mutable_buffer),
                                &recorded_mutable_buffer),
             "clSetKernelArg recorded mutable buffer");
  require_cl(api.set_kernel_arg(recorded_mutable_add, 1U, sizeof(one), &one),
             "clSetKernelArg recorded mutable initial value");
  require_cl(api.set_kernel_arg(ordinary_noop, 0U, sizeof(ordinary_noop_buffer),
                                &ordinary_noop_buffer),
             "clSetKernelArg ordinary noop buffer");
  require_cl(api.set_kernel_arg(recorded_noop, 0U, sizeof(recorded_noop_buffer),
                                &recorded_noop_buffer),
             "clSetKernelArg recorded noop buffer");

  const BenchmarkResult noop =
      benchmark_recording(library.handle(), api, objects, device, recordable_property,
                          "noop_recorded_sequence", ordinary_noop, recorded_noop,
                          ordinary_noop_buffer, recorded_noop_buffer, args.iterations,
                          false);
  const BenchmarkResult fixed =
      benchmark_recording(library.handle(), api, objects, device, recordable_property,
                          "fixed_arg_recorded_add", ordinary_add, recorded_add,
                          ordinary_add_buffer, recorded_add_buffer, args.iterations,
                          true);
  const BenchmarkResult mutable_result =
      benchmark_mutable_recording(library.handle(), api, objects, device,
                                  recordable_property, ordinary_mutable_add,
                                  recorded_mutable_add, ordinary_mutable_buffer,
                                  recorded_mutable_buffer, args.iterations);
  write_text_file(join_path(args.output_dir, "microbenchmark.json"),
                  microbenchmark_json(noop, fixed, mutable_result));
  write_text_file(join_path(args.output_dir, "output_comparison.json"),
                  output_comparison_json(noop, fixed, mutable_result));
}

void print_help() {
  std::cout << "Usage: opencl_recordable_queue_probe --output DIR [--iterations N]\n"
            << "Probes cl_qcom_recordable_queues on the local OpenCL device and writes\n"
            << "H11-D JSON artifacts. This is a probe only; it does not enable training\n"
            << "recordable queues.\n";
}

ProbeArgs parse_args(int argc, char** argv) {
  ProbeArgs args;
  for (int index = 1; index < argc; ++index) {
    const std::string arg = argv[index];
    if (arg == "--help") {
      print_help();
      std::exit(0);
    }
    if (arg == "--output") {
      if ((index + 1) >= argc) {
        throw std::invalid_argument("--output requires DIR");
      }
      args.output_dir = argv[++index];
      continue;
    }
    if (arg == "--iterations") {
      if ((index + 1) >= argc) {
        throw std::invalid_argument("--iterations requires N");
      }
      args.iterations = std::stoi(argv[++index]);
      if (args.iterations <= 0) {
        throw std::invalid_argument("--iterations must be positive");
      }
      continue;
    }
    throw std::invalid_argument("unknown argument: " + arg);
  }
  if (args.output_dir.empty()) {
    throw std::invalid_argument("--output DIR is required");
  }
  return args;
}

}  // namespace

int main(int argc, char** argv) {
  try {
    const ProbeArgs args = parse_args(argc, argv);
    run_probe(args);
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "opencl_recordable_queue_probe failed: " << error.what() << '\n';
    return 2;
  }
}
