#ifndef POLYMATH_GEMMA4_STATUS_H_
#define POLYMATH_GEMMA4_STATUS_H_

#include <string>

namespace polymath::gemma4 {

class Status {
 public:
  static Status ok();
  static Status invalid(std::string message);

  bool is_ok() const;
  const std::string& message() const;

 private:
  explicit Status(std::string message);

  std::string message_;
};

}  // namespace polymath::gemma4

#endif  // POLYMATH_GEMMA4_STATUS_H_
