#include "polymath/gemma4/device_backend.h"

namespace polymath::gemma4 {

std::string CpuDebugBackend::name() const {
  return "cpu_debug";
}

DeviceProbe CpuDebugBackend::probe() const {
  DeviceProbe probe = probe_device_libraries();
  probe.capabilities.push_back({"cpu_debug_backend", true, "diagnostic only; not a gate backend"});
  return probe;
}

}  // namespace polymath::gemma4
