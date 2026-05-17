#ifndef POLYMATH_GEMMA4_EXECUTOR_INTERFACES_H_
#define POLYMATH_GEMMA4_EXECUTOR_INTERFACES_H_

#include <cstdint>
#include <string>
#include <vector>

#include "polymath/gemma4/status.h"

namespace polymath::gemma4 {

struct TensorSpec {
  std::string name;
  std::vector<std::uint32_t> shape;
  std::string dtype;
};

class TensorStore {
 public:
  virtual ~TensorStore() = default;

  virtual std::vector<float> read_f32(const std::string& path,
                                      std::size_t expected_count) const = 0;
  virtual void write_f32(const std::string& path,
                         const std::vector<float>& values) const = 0;
  virtual std::vector<std::uint8_t> read_bytes(const std::string& path) const = 0;
  virtual std::string sha256_hex(const std::string& path) const = 0;
};

class BackendExecutor {
 public:
  virtual ~BackendExecutor() = default;

  virtual Status run_layer_forward(const std::string& layer_pack_dir,
                                   const std::string& output_dir) = 0;
  virtual Status run_two_layer_forward(const std::string& first_layer_pack_dir,
                                       const std::string& second_layer_pack_dir,
                                       const std::string& output_dir) = 0;
};

struct ReferenceComparison {
  Status status;
  double cosine_p50 = 0.0;
  double cosine_min = 0.0;
  std::uint32_t failed_items = 0;
};

class ReferenceComparator {
 public:
  virtual ~ReferenceComparator() = default;

  virtual ReferenceComparison compare(const std::string& candidate_path,
                                      const std::string& reference_path,
                                      const std::string& mask_path,
                                      const TensorSpec& tensor) const = 0;
};

class TelemetrySink {
 public:
  virtual ~TelemetrySink() = default;

  virtual Status write_json(const std::string& output_dir,
                            const std::string& file_name,
                            const std::string& json_payload) const = 0;
};

class Tokenizer {
 public:
  virtual ~Tokenizer() = default;

  virtual Status tokenize(const std::string& text,
                          std::vector<std::uint32_t>& token_ids) const = 0;
};

class SequencePacker {
 public:
  virtual ~SequencePacker() = default;

  virtual Status pack(const std::vector<std::uint32_t>& token_ids,
                      const std::string& output_cache_dir) const = 0;
};

class CheckpointStore {
 public:
  virtual ~CheckpointStore() = default;

  virtual std::vector<float> read_trainable(const std::string& name,
                                            std::size_t expected_count) const = 0;
  virtual void write_trainable(const std::string& name,
                               const std::vector<float>& values) const = 0;
  virtual std::string trainable_sha256(const std::string& name) const = 0;
};

struct TrainingStepRequest {
  std::string fixture_dir;
  std::string checkpoint_dir;
  std::string output_dir;
  float learning_rate = 0.0F;
  bool apply_update = false;
};

class TrainingStepExecutor {
 public:
  virtual ~TrainingStepExecutor() = default;

  virtual Status run_training_step(const TrainingStepRequest& request) = 0;
};

}  // namespace polymath::gemma4

#endif  // POLYMATH_GEMMA4_EXECUTOR_INTERFACES_H_
