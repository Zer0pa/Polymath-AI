#ifndef POLYMATH_GEMMA4_DEVICE_BACKEND_H_
#define POLYMATH_GEMMA4_DEVICE_BACKEND_H_

#include <ostream>
#include <string>
#include <vector>

namespace polymath::gemma4 {

struct Capability {
  std::string name;
  bool available;
  std::string detail;
};

struct DeviceProbe {
  std::string platform;
  std::string architecture;
  std::vector<Capability> capabilities;
};

class DeviceBackend {
 public:
  virtual ~DeviceBackend() = default;

  virtual std::string name() const = 0;
  virtual DeviceProbe probe() const = 0;
};

class CpuDebugBackend final : public DeviceBackend {
 public:
  std::string name() const override;
  DeviceProbe probe() const override;
};

DeviceProbe probe_device_libraries();
void write_device_probe_json(const DeviceProbe& probe, std::ostream& stream);

}  // namespace polymath::gemma4

#endif  // POLYMATH_GEMMA4_DEVICE_BACKEND_H_
