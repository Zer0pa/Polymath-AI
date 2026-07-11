#ifndef POLYMATH_E4B_ADRENO_INT2_OPENCL_DYNAMIC_RUNTIME_H_
#define POLYMATH_E4B_ADRENO_INT2_OPENCL_DYNAMIC_RUNTIME_H_

#include <cstddef>
#include <cstdint>
#include <string>

namespace polymath::e4b_adreno {

using cl_bool = std::uint32_t;
using cl_command_queue = void*;
using cl_context = void*;
using cl_context_properties = std::intptr_t;
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
using cl_uint = std::uint32_t;

constexpr cl_int kClSuccess = 0;
constexpr cl_bool kClFalse = 0;
constexpr cl_bool kClTrue = 1;
constexpr cl_device_type kClDeviceTypeGpu = 1ULL << 2U;
constexpr cl_mem_flags kClMemReadWrite = 1ULL << 0U;
constexpr cl_mem_flags kClMemWriteOnly = 1ULL << 1U;
constexpr cl_mem_flags kClMemReadOnly = 1ULL << 2U;
constexpr std::uint64_t kClQueueProfilingEnable = 1ULL << 1U;
constexpr cl_uint kClProgramBuildLog = 0x1183U;
constexpr cl_uint kClProfilingCommandStart = 0x1282U;
constexpr cl_uint kClProfilingCommandEnd = 0x1283U;

struct OpenClIdentity {
  std::string loaded_path;
  std::string load_route;
  std::string platform_name;
  std::string platform_vendor;
  std::string platform_version;
  std::string device_name;
  std::string device_vendor;
  std::string driver_version;
  std::string device_version;
  std::string opencl_c_version;
  std::string device_extensions;
  std::size_t max_work_group_size = 0U;
  std::uint64_t local_mem_bytes = 0U;
  std::uint64_t max_mem_alloc_bytes = 0U;
  std::uint32_t address_bits = 0U;
  bool endian_little = false;
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
                                                   std::uint64_t, cl_int*);
  using CreateBuffer = cl_mem (*)(cl_context, cl_mem_flags, std::size_t, void*, cl_int*);
  using CreateProgramWithSource = cl_program (*)(cl_context, cl_uint, const char**,
                                                 const std::size_t*, cl_int*);
  using BuildProgram = cl_int (*)(cl_program, cl_uint, const cl_device_id*, const char*,
                                  void (*)(cl_program, void*), void*);
  using GetProgramBuildInfo = cl_int (*)(cl_program, cl_device_id, cl_uint,
                                         std::size_t, void*, std::size_t*);
  using CreateKernel = cl_kernel (*)(cl_program, const char*, cl_int*);
  using GetKernelWorkGroupInfo = cl_int (*)(cl_kernel, cl_device_id, cl_uint,
                                            std::size_t, void*, std::size_t*);
  using SetKernelArg = cl_int (*)(cl_kernel, cl_uint, std::size_t, const void*);
  using EnqueueWriteBuffer = cl_int (*)(cl_command_queue, cl_mem, cl_bool,
                                        std::size_t, std::size_t, const void*, cl_uint,
                                        const cl_event*, cl_event*);
  using EnqueueNDRangeKernel = cl_int (*)(cl_command_queue, cl_kernel, cl_uint,
                                          const std::size_t*, const std::size_t*,
                                          const std::size_t*, cl_uint, const cl_event*,
                                          cl_event*);
  using EnqueueReadBuffer = cl_int (*)(cl_command_queue, cl_mem, cl_bool,
                                       std::size_t, std::size_t, void*, cl_uint,
                                       const cl_event*, cl_event*);
  using GetEventProfilingInfo = cl_int (*)(cl_event, cl_uint, std::size_t, void*,
                                           std::size_t*);
  using Finish = cl_int (*)(cl_command_queue);
  using ReleaseEvent = cl_int (*)(cl_event);
  using ReleaseMemObject = cl_int (*)(cl_mem);
  using ReleaseKernel = cl_int (*)(cl_kernel);
  using ReleaseProgram = cl_int (*)(cl_program);
  using ReleaseCommandQueue = cl_int (*)(cl_command_queue);
  using ReleaseContext = cl_int (*)(cl_context);

  explicit OpenClApi(void* library);

  GetPlatformIDs get_platform_ids;
  GetPlatformInfo get_platform_info;
  GetDeviceIDs get_device_ids;
  GetDeviceInfo get_device_info;
  CreateContext create_context;
  CreateCommandQueue create_command_queue;
  CreateBuffer create_buffer;
  CreateProgramWithSource create_program_with_source;
  BuildProgram build_program;
  GetProgramBuildInfo get_program_build_info;
  CreateKernel create_kernel;
  GetKernelWorkGroupInfo get_kernel_work_group_info;
  SetKernelArg set_kernel_arg;
  EnqueueWriteBuffer enqueue_write_buffer;
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

class DynamicOpenClLibrary {
 public:
  DynamicOpenClLibrary();
  ~DynamicOpenClLibrary();

  DynamicOpenClLibrary(const DynamicOpenClLibrary&) = delete;
  DynamicOpenClLibrary& operator=(const DynamicOpenClLibrary&) = delete;

  void* handle() const;
  const std::string& loaded_path() const;
  const std::string& load_route() const;

 private:
  using CloseFunction = int (*)(void*);

  void* handle_ = nullptr;
  void* support_handle_ = nullptr;
  CloseFunction close_function_ = nullptr;
  std::string loaded_path_;
  std::string load_route_;
};

struct BoundOpenClDevice {
  cl_platform_id platform = nullptr;
  cl_device_id device = nullptr;
  OpenClIdentity identity;
};

BoundOpenClDevice select_and_validate_device(const OpenClApi& api,
                                             const DynamicOpenClLibrary& library,
                                             bool enforce_environment = true);
bool extension_list_has(const std::string& extensions, const std::string& extension);
void require_cl(cl_int error, const std::string& operation);

}  // namespace polymath::e4b_adreno

#endif  // POLYMATH_E4B_ADRENO_INT2_OPENCL_DYNAMIC_RUNTIME_H_
