#include "opencl_dynamic_runtime.h"

#include <dlfcn.h>

#include <cstdlib>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace polymath::e4b_adreno {
namespace {

constexpr const char* kOpenClLibraryPath = "/vendor/lib64/libOpenCL.so";
#ifdef __ANDROID__
constexpr const char* kSphalSupportLibrary = "libvndksupport.so";
#endif

constexpr cl_platform_info kClPlatformVersion = 0x0901U;
constexpr cl_platform_info kClPlatformName = 0x0902U;
constexpr cl_platform_info kClPlatformVendor = 0x0903U;
constexpr cl_device_info kClDeviceMaxWorkGroupSize = 0x1004U;
constexpr cl_device_info kClDeviceMaxMemAllocSize = 0x1010U;
constexpr cl_device_info kClDeviceAddressBits = 0x100DU;
constexpr cl_device_info kClDeviceLocalMemSize = 0x1023U;
constexpr cl_device_info kClDeviceEndianLittle = 0x1026U;
constexpr cl_device_info kClDeviceName = 0x102BU;
constexpr cl_device_info kClDeviceVendor = 0x102CU;
constexpr cl_device_info kClDriverVersion = 0x102DU;
constexpr cl_device_info kClDeviceVersion = 0x102FU;
constexpr cl_device_info kClDeviceExtensions = 0x1030U;
constexpr cl_device_info kClDeviceOpenClCVersion = 0x103DU;

#if !defined(__ANDROID__)
int close_regular(void* handle) { return dlclose(handle); }
#endif

template <typename Function>
Function resolve_required(void* library, const char* name) {
  dlerror();
  void* symbol = dlsym(library, name);
  const char* error = dlerror();
  if (symbol == nullptr || error != nullptr) {
    throw std::runtime_error(std::string("OpenCL symbol missing: ") + name);
  }
  return reinterpret_cast<Function>(symbol);
}

std::string required_environment(const char* name) {
  const char* value = std::getenv(name);
  if (value == nullptr || value[0] == '\0') {
    throw std::runtime_error(std::string("required runtime binding absent: ") + name);
  }
  return value;
}

void require_equal(const std::string& observed, const char* environment_name,
                   const char* field_name) {
  if (observed != required_environment(environment_name)) {
    throw std::runtime_error(std::string("OpenCL runtime identity drift: ") + field_name);
  }
}

std::string platform_string(const OpenClApi& api, cl_platform_id platform,
                            cl_platform_info field) {
  std::size_t size = 0U;
  require_cl(api.get_platform_info(platform, field, 0U, nullptr, &size),
             "clGetPlatformInfo size");
  if (size == 0U) {
    throw std::runtime_error("OpenCL platform string is empty");
  }
  std::vector<char> bytes(size);
  require_cl(api.get_platform_info(platform, field, bytes.size(), bytes.data(), nullptr),
             "clGetPlatformInfo value");
  if (bytes.back() != '\0') {
    throw std::runtime_error("OpenCL platform string is not terminated");
  }
  return std::string(bytes.data());
}

std::string device_string(const OpenClApi& api, cl_device_id device,
                          cl_device_info field) {
  std::size_t size = 0U;
  require_cl(api.get_device_info(device, field, 0U, nullptr, &size),
             "clGetDeviceInfo size");
  if (size == 0U) {
    throw std::runtime_error("OpenCL device string is empty");
  }
  std::vector<char> bytes(size);
  require_cl(api.get_device_info(device, field, bytes.size(), bytes.data(), nullptr),
             "clGetDeviceInfo value");
  if (bytes.back() != '\0') {
    throw std::runtime_error("OpenCL device string is not terminated");
  }
  return std::string(bytes.data());
}

template <typename Value>
Value device_scalar(const OpenClApi& api, cl_device_id device, cl_device_info field) {
  Value value{};
  require_cl(api.get_device_info(device, field, sizeof(value), &value, nullptr),
             "clGetDeviceInfo scalar");
  return value;
}

cl_platform_id select_single_platform(const OpenClApi& api) {
  cl_uint count = 0U;
  require_cl(api.get_platform_ids(0U, nullptr, &count), "clGetPlatformIDs count");
  if (count != 1U) {
    throw std::runtime_error("OpenCL platform cardinality drift");
  }
  cl_platform_id platform = nullptr;
  require_cl(api.get_platform_ids(1U, &platform, nullptr), "clGetPlatformIDs value");
  return platform;
}

cl_device_id select_single_gpu(const OpenClApi& api, cl_platform_id platform) {
  cl_uint count = 0U;
  require_cl(api.get_device_ids(platform, kClDeviceTypeGpu, 0U, nullptr, &count),
             "clGetDeviceIDs count");
  if (count != 1U) {
    throw std::runtime_error("OpenCL GPU device cardinality drift");
  }
  cl_device_id device = nullptr;
  require_cl(api.get_device_ids(platform, kClDeviceTypeGpu, 1U, &device, nullptr),
             "clGetDeviceIDs value");
  return device;
}

}  // namespace

OpenClApi::OpenClApi(void* library)
    : get_platform_ids(resolve_required<GetPlatformIDs>(library, "clGetPlatformIDs")),
      get_platform_info(resolve_required<GetPlatformInfo>(library, "clGetPlatformInfo")),
      get_device_ids(resolve_required<GetDeviceIDs>(library, "clGetDeviceIDs")),
      get_device_info(resolve_required<GetDeviceInfo>(library, "clGetDeviceInfo")),
      create_context(resolve_required<CreateContext>(library, "clCreateContext")),
      create_command_queue(
          resolve_required<CreateCommandQueue>(library, "clCreateCommandQueue")),
      create_buffer(resolve_required<CreateBuffer>(library, "clCreateBuffer")),
      create_program_with_source(resolve_required<CreateProgramWithSource>(
          library, "clCreateProgramWithSource")),
      build_program(resolve_required<BuildProgram>(library, "clBuildProgram")),
      get_program_build_info(
          resolve_required<GetProgramBuildInfo>(library, "clGetProgramBuildInfo")),
      create_kernel(resolve_required<CreateKernel>(library, "clCreateKernel")),
      get_kernel_work_group_info(resolve_required<GetKernelWorkGroupInfo>(
          library, "clGetKernelWorkGroupInfo")),
      set_kernel_arg(resolve_required<SetKernelArg>(library, "clSetKernelArg")),
      enqueue_write_buffer(
          resolve_required<EnqueueWriteBuffer>(library, "clEnqueueWriteBuffer")),
      enqueue_nd_range_kernel(resolve_required<EnqueueNDRangeKernel>(
          library, "clEnqueueNDRangeKernel")),
      enqueue_read_buffer(
          resolve_required<EnqueueReadBuffer>(library, "clEnqueueReadBuffer")),
      get_event_profiling_info(resolve_required<GetEventProfilingInfo>(
          library, "clGetEventProfilingInfo")),
      finish(resolve_required<Finish>(library, "clFinish")),
      release_event(resolve_required<ReleaseEvent>(library, "clReleaseEvent")),
      release_mem_object(
          resolve_required<ReleaseMemObject>(library, "clReleaseMemObject")),
      release_kernel(resolve_required<ReleaseKernel>(library, "clReleaseKernel")),
      release_program(resolve_required<ReleaseProgram>(library, "clReleaseProgram")),
      release_command_queue(resolve_required<ReleaseCommandQueue>(
          library, "clReleaseCommandQueue")),
      release_context(resolve_required<ReleaseContext>(library, "clReleaseContext")) {}

DynamicOpenClLibrary::DynamicOpenClLibrary() {
#ifdef __ANDROID__
  using AndroidLoadSphalLibrary = void* (*)(const char*, int);
  using AndroidUnloadSphalLibrary = int (*)(void*);
  support_handle_ = dlopen(kSphalSupportLibrary, RTLD_NOW | RTLD_LOCAL);
  if (support_handle_ == nullptr) {
    throw std::runtime_error("Android SPHAL support library unavailable");
  }
  auto load = resolve_required<AndroidLoadSphalLibrary>(support_handle_,
                                                        "android_load_sphal_library");
  auto unload = resolve_required<AndroidUnloadSphalLibrary>(
      support_handle_, "android_unload_sphal_library");
  handle_ = load(kOpenClLibraryPath, RTLD_NOW | RTLD_LOCAL);
  if (handle_ == nullptr) {
    throw std::runtime_error("Android SPHAL OpenCL load failed");
  }
  close_function_ = unload;
  loaded_path_ = kOpenClLibraryPath;
  load_route_ = "android_sphal";
#else
  handle_ = dlopen(kOpenClLibraryPath, RTLD_NOW | RTLD_LOCAL);
  if (handle_ == nullptr) {
    throw std::runtime_error("OpenCL direct load failed on non-Android diagnostic build");
  }
  close_function_ = close_regular;
  loaded_path_ = kOpenClLibraryPath;
  load_route_ = "direct_dlopen";
#endif
}

DynamicOpenClLibrary::~DynamicOpenClLibrary() {
  if (handle_ != nullptr && close_function_ != nullptr) {
    close_function_(handle_);
  }
  if (support_handle_ != nullptr) {
    dlclose(support_handle_);
  }
}

void* DynamicOpenClLibrary::handle() const { return handle_; }

const std::string& DynamicOpenClLibrary::loaded_path() const { return loaded_path_; }

const std::string& DynamicOpenClLibrary::load_route() const { return load_route_; }

BoundOpenClDevice select_and_validate_device(const OpenClApi& api,
                                             const DynamicOpenClLibrary& library,
                                             bool enforce_environment) {
  BoundOpenClDevice result;
  result.platform = select_single_platform(api);
  result.device = select_single_gpu(api, result.platform);
  OpenClIdentity& identity = result.identity;
  identity.loaded_path = library.loaded_path();
  identity.load_route = library.load_route();
  identity.platform_name = platform_string(api, result.platform, kClPlatformName);
  identity.platform_vendor = platform_string(api, result.platform, kClPlatformVendor);
  identity.platform_version = platform_string(api, result.platform, kClPlatformVersion);
  identity.device_name = device_string(api, result.device, kClDeviceName);
  identity.device_vendor = device_string(api, result.device, kClDeviceVendor);
  identity.driver_version = device_string(api, result.device, kClDriverVersion);
  identity.device_version = device_string(api, result.device, kClDeviceVersion);
  identity.opencl_c_version = device_string(api, result.device, kClDeviceOpenClCVersion);
  identity.device_extensions = device_string(api, result.device, kClDeviceExtensions);
  identity.max_work_group_size =
      device_scalar<std::size_t>(api, result.device, kClDeviceMaxWorkGroupSize);
  identity.local_mem_bytes =
      device_scalar<std::uint64_t>(api, result.device, kClDeviceLocalMemSize);
  identity.max_mem_alloc_bytes =
      device_scalar<std::uint64_t>(api, result.device, kClDeviceMaxMemAllocSize);
  identity.address_bits =
      device_scalar<std::uint32_t>(api, result.device, kClDeviceAddressBits);
  identity.endian_little =
      device_scalar<cl_bool>(api, result.device, kClDeviceEndianLittle) == kClTrue;

  if (enforce_environment) {
    require_equal(identity.loaded_path, "POLYMATH_EXPECT_OPENCL_LOADED_PATH", "loaded_path");
    require_equal(identity.load_route, "POLYMATH_EXPECT_OPENCL_LOAD_ROUTE", "load_route");
    require_equal(identity.platform_name, "POLYMATH_EXPECT_OPENCL_PLATFORM_NAME",
                  "platform_name");
    require_equal(identity.platform_vendor, "POLYMATH_EXPECT_OPENCL_PLATFORM_VENDOR",
                  "platform_vendor");
    require_equal(identity.platform_version, "POLYMATH_EXPECT_OPENCL_PLATFORM_VERSION",
                  "platform_version");
    require_equal(identity.device_name, "POLYMATH_EXPECT_OPENCL_DEVICE_NAME",
                  "device_name");
    require_equal(identity.device_vendor, "POLYMATH_EXPECT_OPENCL_DEVICE_VENDOR",
                  "device_vendor");
    require_equal(identity.driver_version, "POLYMATH_EXPECT_OPENCL_DRIVER_VERSION",
                  "driver_version");
    require_equal(identity.device_version, "POLYMATH_EXPECT_OPENCL_DEVICE_VERSION",
                  "device_version");
    require_equal(identity.opencl_c_version, "POLYMATH_EXPECT_OPENCL_C_VERSION",
                  "opencl_c_version");
    require_equal(identity.device_extensions, "POLYMATH_EXPECT_OPENCL_DEVICE_EXTENSIONS",
                  "device_extensions");
  }

  if (identity.max_work_group_size < 64U || identity.local_mem_bytes < 5'384U ||
      identity.max_mem_alloc_bytes < 167'772'160U || identity.address_bits != 64U ||
      !identity.endian_little) {
    throw std::runtime_error("OpenCL device limit or ABI drift");
  }
  if (!extension_list_has(identity.device_extensions, "cl_khr_subgroups") ||
      !extension_list_has(identity.device_extensions, "cl_qcom_bfloat16_product")) {
    throw std::runtime_error("required OpenCL extension drift");
  }
  return result;
}

bool extension_list_has(const std::string& extensions, const std::string& extension) {
  std::istringstream input(extensions);
  std::string token;
  while (input >> token) {
    if (token == extension) {
      return true;
    }
  }
  return false;
}

void require_cl(cl_int error, const std::string& operation) {
  if (error != kClSuccess) {
    throw std::runtime_error(operation + " failed with OpenCL error " +
                             std::to_string(error));
  }
}

}  // namespace polymath::e4b_adreno
