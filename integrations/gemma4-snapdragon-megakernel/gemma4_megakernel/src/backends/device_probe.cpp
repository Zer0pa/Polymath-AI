#include "polymath/gemma4/device_backend.h"

#include <ostream>
#include <string>
#include <vector>

#include "polymath/gemma4/json_writer.h"

#if defined(__ANDROID__) || defined(__linux__) || defined(__APPLE__)
#include <dlfcn.h>
#endif

namespace polymath::gemma4 {
namespace {

bool can_load_library(const char* name) {
#if defined(__ANDROID__) || defined(__linux__) || defined(__APPLE__)
  void* handle = dlopen(name, RTLD_LAZY | RTLD_LOCAL);
  if (handle == nullptr) {
    return false;
  }
  dlclose(handle);
  return true;
#else
  (void)name;
  return false;
#endif
}

std::string join_attempted_libraries(const std::vector<std::string>& libraries) {
  std::string joined;
  for (std::size_t index = 0; index < libraries.size(); ++index) {
    if (index != 0U) {
      joined += ", ";
    }
    joined += libraries[index];
  }
  return joined;
}

std::string platform_name() {
#if defined(__ANDROID__)
  return "android";
#elif defined(__APPLE__)
  return "apple";
#elif defined(__linux__)
  return "linux";
#else
  return "unknown";
#endif
}

std::string architecture_name() {
#if defined(__aarch64__)
  return "aarch64";
#elif defined(__x86_64__)
  return "x86_64";
#elif defined(__arm__)
  return "arm";
#else
  return "unknown";
#endif
}

std::vector<std::string> vulkan_libraries() {
#if defined(__ANDROID__)
  return {"libvulkan.so", "/system/lib64/libvulkan.so",
          "/vendor/lib64/libvulkan.so"};
#elif defined(__APPLE__)
  return {"libvulkan.1.dylib", "libvulkan.dylib", "libMoltenVK.dylib"};
#elif defined(__linux__)
  return {"libvulkan.so.1", "libvulkan.so"};
#else
  return {"libvulkan.so"};
#endif
}

std::vector<std::string> opencl_libraries() {
#if defined(__ANDROID__)
  return {"libOpenCL.so", "/vendor/lib64/libOpenCL.so",
          "/system/vendor/lib64/libOpenCL.so", "/system/lib64/libOpenCL.so"};
#elif defined(__APPLE__)
  return {"/System/Library/Frameworks/OpenCL.framework/OpenCL",
          "libOpenCL.dylib"};
#elif defined(__linux__)
  return {"libOpenCL.so.1", "libOpenCL.so"};
#else
  return {"libOpenCL.so"};
#endif
}

Capability library_capability(const std::string& name,
                              const std::vector<std::string>& libraries) {
  for (const std::string& library : libraries) {
    if (can_load_library(library.c_str())) {
      return Capability{name, true, library};
    }
  }
  return Capability{name, false,
                    "not loadable; attempted " +
                        join_attempted_libraries(libraries)};
}

}  // namespace

DeviceProbe probe_device_libraries() {
  DeviceProbe probe;
  probe.platform = platform_name();
  probe.architecture = architecture_name();
  probe.capabilities.push_back(library_capability("vulkan", vulkan_libraries()));
  probe.capabilities.push_back(library_capability("opencl", opencl_libraries()));
  return probe;
}

void write_device_probe_json(const DeviceProbe& probe, std::ostream& stream) {
  stream << "{\"schema_version\":\"gemma4_device_probe_v1\",";
  stream << "\"platform\":";
  write_json_string(stream, probe.platform);
  stream << ",\"architecture\":";
  write_json_string(stream, probe.architecture);
  stream << ",\"capabilities\":[";
  for (std::size_t index = 0; index < probe.capabilities.size(); ++index) {
    if (index != 0U) {
      stream << ',';
    }
    const Capability& capability = probe.capabilities[index];
    stream << "{\"name\":";
    write_json_string(stream, capability.name);
    stream << ",\"available\":" << (capability.available ? "true" : "false");
    stream << ",\"detail\":";
    write_json_string(stream, capability.detail);
    stream << '}';
  }
  stream << "]}\n";
}

}  // namespace polymath::gemma4
