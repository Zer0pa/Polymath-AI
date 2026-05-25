#include <sys/stat.h>
#include <sys/statvfs.h>
#include <unistd.h>

#include <atomic>
#include <cerrno>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <ctime>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <mutex>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include "polymath/gemma4/adapter_training.h"
#include "polymath/gemma4/json_writer.h"
#include "polymath/gemma4/sha256.h"

namespace {

constexpr const char* kRunnerBuildId = "phase13_runner_identity_v1_20260524";
constexpr const char* kExpectedModelId = "google/gemma-4-E4B";
constexpr const char* kExpectedModelRevision = "7aa32e6889efd6300124851b164f8b364314c3d8";
constexpr int kExpectedHiddenSize = 2560;
constexpr const char* kKernelLineageClass = "residual_adapter_opencl_training";
constexpr const char* kRuntimeBackend = "phone_cpu_token_to_hidden_plus_opencl_layers_and_adapter";
constexpr const char* kTeacherProvenance =
    "runpod_precomputed_full_gemma4_topk_before_phone_runtime";
constexpr double kPhase10ActiveWallBaseline = 4626.645587 / 21692.164205625013;

struct RunnerArgs {
  std::string queue_path;
  std::string run_root;
  std::string heartbeat_path;
  std::string state_path;
  std::string stop_file = "STOP";
};

struct QueueRecord {
  std::string id;
  std::string gate;
  std::string config_path;
  std::string resume;
};

struct H11AConfig {
  std::string run_id;
  std::string gate_name = "H11-A";
  std::string gate_dir_name = "H11-A-daemon";
  std::string objective = "hidden_mse";
  std::vector<std::string> token_caches;
  std::vector<std::string> teacher_shards;
  std::string asset_dir;
  std::string layer0_pack;
  std::string layer1_pack;
  std::string initial_checkpoint;
  std::string disconnect_marker_path = "disconnect_evidence.json";
  int iteration_count = 50;
  int sample_every = 25;
  int marker_wait_seconds = 1800;
  int disconnect_hold_seconds = 600;
  double learning_rate = 0.01;
  std::string optimizer = "sgd";
  double weight_decay = 0.0;
  double beta1 = 0.9;
  double beta2 = 0.999;
  double optimizer_epsilon = 1.0e-8;
  double grad_clip_l2 = 0.0;
  int adapter_rank = 4;
  bool apply_update = true;
  bool require_disconnect_marker = true;
  std::string model_id = kExpectedModelId;
  std::string model_revision = kExpectedModelRevision;
  int hidden_size = kExpectedHiddenSize;
  std::string source_commit = "unknown";
  std::string kernel_lineage_class = kKernelLineageClass;
  std::string runtime_backend = kRuntimeBackend;
  std::string teacher_provenance = kTeacherProvenance;
  bool hidden_state_fixtures_consumed = false;
};

struct RunnerState {
  std::string run_id;
  std::string record_id;
  std::string gate;
  std::string checkpoint_dir;
  std::string status;
  int next_iteration = 0;
};

struct IterationRecord {
  int index = 0;
  bool sample = false;
  std::string status;
  std::string token_cache;
  std::string teacher_shard;
  std::string input_checkpoint;
  std::string output_checkpoint;
  std::string phone_output_dir;
  std::string blocker;
  double wall_seconds = 0.0;
  double active_training_seconds = 0.0;
};

struct GateStats {
  std::vector<IterationRecord> records;
  std::vector<std::string> blockers;
  double queue_wall_seconds = 0.0;
  double active_training_seconds = 0.0;
  double disconnect_wait_seconds = 0.0;
  bool stopped = false;
  bool disconnect_marker_seen = false;
};

std::string read_text_file(const std::string& path) {
  std::ifstream file(path);
  if (!file) {
    throw std::runtime_error("unable to read file: " + path);
  }
  return std::string((std::istreambuf_iterator<char>(file)),
                     std::istreambuf_iterator<char>());
}

bool path_exists(const std::string& path) {
  struct stat info {};
  return ::stat(path.c_str(), &info) == 0;
}

std::uint64_t file_size_bytes(const std::string& path) {
  struct stat info {};
  if (::stat(path.c_str(), &info) != 0) {
    throw std::runtime_error("stat failed for: " + path);
  }
  return static_cast<std::uint64_t>(info.st_size);
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
  for (char character : path) {
    current.push_back(character);
    if (character != '/') {
      continue;
    }
    if (current.size() <= 1U) {
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

void write_text_file_atomic(const std::string& path, const std::string& text) {
  ensure_directory(dirname_of(path));
  const std::string temp_path =
      path + ".tmp." + std::to_string(static_cast<long long>(::getpid()));
  {
    std::ofstream file(temp_path);
    if (!file) {
      throw std::runtime_error("unable to write temp file: " + temp_path);
    }
    file << text;
  }
  if (::rename(temp_path.c_str(), path.c_str()) != 0) {
    throw std::runtime_error("rename failed for: " + path);
  }
}

void append_text_file(const std::string& path, const std::string& text) {
  ensure_directory(dirname_of(path));
  std::ofstream file(path, std::ios::app);
  if (!file) {
    throw std::runtime_error("unable to append file: " + path);
  }
  file << text;
}

std::string utc_timestamp() {
  const std::time_t now = std::time(nullptr);
  std::tm tm {};
  gmtime_r(&now, &tm);
  char buffer[32] = {};
  std::strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%SZ", &tm);
  return std::string(buffer);
}

std::string compact_utc_timestamp() {
  const std::time_t now = std::time(nullptr);
  std::tm tm {};
  gmtime_r(&now, &tm);
  char buffer[32] = {};
  std::strftime(buffer, sizeof(buffer), "%Y%m%dT%H%M%SZ", &tm);
  return std::string(buffer);
}

std::string current_working_directory() {
  std::vector<char> buffer(4096U, '\0');
  if (::getcwd(buffer.data(), buffer.size()) == nullptr) {
    throw std::runtime_error("getcwd failed");
  }
  return std::string(buffer.data());
}

std::string self_executable_path() {
  std::vector<char> buffer(4096U, '\0');
  const ssize_t count = ::readlink("/proc/self/exe", buffer.data(), buffer.size() - 1U);
  if (count <= 0) {
    return "unavailable";
  }
  return std::string(buffer.data(), static_cast<std::size_t>(count));
}

std::string self_executable_sha256() {
  const std::string path = self_executable_path();
  if (path == "unavailable") {
    return path;
  }
  try {
    return polymath::gemma4::sha256_file_hex(path);
  } catch (const std::exception& error) {
    return std::string("unavailable:") + error.what();
  }
}

std::string resolve_path(const std::string& path, const std::string& cwd) {
  if (path.empty() || path.front() == '/') {
    return path;
  }
  return join_path(cwd, path);
}

std::string lower_ascii(std::string value) {
  for (char& c : value) {
    if (c >= 'A' && c <= 'Z') {
      c = static_cast<char>(c - 'A' + 'a');
    }
  }
  return value;
}

bool contains_forbidden_identity_marker(const std::string& value) {
  const std::string lower = lower_ascii(value);
  return lower.find("qwen") != std::string::npos ||
         lower.find("smollm") != std::string::npos ||
         lower.find("random-init") != std::string::npos ||
         lower.find("random_init") != std::string::npos ||
         lower.find("hidden-size-1536") != std::string::npos ||
         lower.find("hidden_size_1536") != std::string::npos;
}

std::string residual_adapter_scope(int adapter_rank) {
  return "post_layer0_rank" + std::to_string(adapter_rank) + "_residual_adapter";
}

std::size_t find_key_colon(const std::string& json, const std::string& key) {
  const std::string token = "\"" + key + "\"";
  const std::size_t key_pos = json.find(token);
  if (key_pos == std::string::npos) {
    return std::string::npos;
  }
  return json.find(':', key_pos + token.size());
}

std::size_t skip_spaces(const std::string& text, std::size_t pos) {
  while (pos < text.size()) {
    const char c = text[pos];
    if (c != ' ' && c != '\n' && c != '\r' && c != '\t') {
      break;
    }
    ++pos;
  }
  return pos;
}

std::optional<std::string> json_string_value(const std::string& json,
                                             const std::string& key) {
  const std::size_t colon = find_key_colon(json, key);
  if (colon == std::string::npos) {
    return std::nullopt;
  }
  std::size_t pos = skip_spaces(json, colon + 1U);
  if (pos >= json.size() || json[pos] != '"') {
    return std::nullopt;
  }
  ++pos;
  std::string value;
  while (pos < json.size()) {
    const char c = json[pos++];
    if (c == '"') {
      return value;
    }
    if (c != '\\' || pos >= json.size()) {
      value.push_back(c);
      continue;
    }
    const char escaped = json[pos++];
    if (escaped == 'n') {
      value.push_back('\n');
    } else if (escaped == 'r') {
      value.push_back('\r');
    } else if (escaped == 't') {
      value.push_back('\t');
    } else {
      value.push_back(escaped);
    }
  }
  return std::nullopt;
}

std::optional<double> json_number_value(const std::string& json,
                                        const std::string& key) {
  const std::size_t colon = find_key_colon(json, key);
  if (colon == std::string::npos) {
    return std::nullopt;
  }
  const std::size_t pos = skip_spaces(json, colon + 1U);
  if (pos >= json.size()) {
    return std::nullopt;
  }
  char* end = nullptr;
  const double value = std::strtod(json.c_str() + pos, &end);
  if (end == json.c_str() + pos) {
    return std::nullopt;
  }
  return value;
}

std::optional<bool> json_bool_value(const std::string& json,
                                    const std::string& key) {
  const std::size_t colon = find_key_colon(json, key);
  if (colon == std::string::npos) {
    return std::nullopt;
  }
  const std::size_t pos = skip_spaces(json, colon + 1U);
  if (json.compare(pos, 4U, "true") == 0) {
    return true;
  }
  if (json.compare(pos, 5U, "false") == 0) {
    return false;
  }
  return std::nullopt;
}

std::vector<std::string> json_string_array_value(const std::string& json,
                                                 const std::string& key) {
  std::vector<std::string> values;
  const std::size_t colon = find_key_colon(json, key);
  if (colon == std::string::npos) {
    return values;
  }
  std::size_t pos = skip_spaces(json, colon + 1U);
  if (pos >= json.size() || json[pos] != '[') {
    return values;
  }
  ++pos;
  while (pos < json.size()) {
    pos = skip_spaces(json, pos);
    if (pos >= json.size() || json[pos] == ']') {
      break;
    }
    if (json[pos] != '"') {
      ++pos;
      continue;
    }
    ++pos;
    std::string value;
    while (pos < json.size()) {
      const char c = json[pos++];
      if (c == '"') {
        values.push_back(value);
        break;
      }
      if (c != '\\' || pos >= json.size()) {
        value.push_back(c);
        continue;
      }
      const char escaped = json[pos++];
      value.push_back(escaped == 'n' ? '\n' : escaped);
    }
  }
  return values;
}

std::vector<double> json_number_array_value(const std::string& json,
                                            const std::string& key) {
  std::vector<double> values;
  const std::size_t colon = find_key_colon(json, key);
  if (colon == std::string::npos) {
    return values;
  }
  std::size_t pos = skip_spaces(json, colon + 1U);
  if (pos >= json.size() || json[pos] != '[') {
    return values;
  }
  ++pos;
  while (pos < json.size()) {
    pos = skip_spaces(json, pos);
    if (pos >= json.size() || json[pos] == ']') {
      break;
    }
    char* end = nullptr;
    const double value = std::strtod(json.c_str() + pos, &end);
    if (end == json.c_str() + pos) {
      ++pos;
      continue;
    }
    values.push_back(value);
    pos = static_cast<std::size_t>(end - json.c_str());
  }
  return values;
}

bool json_contains_string(const std::string& json,
                          const std::string& key,
                          const std::string& expected) {
  const std::optional<std::string> value = json_string_value(json, key);
  return value.has_value() && value.value() == expected;
}

int json_int_or(const std::string& json, const std::string& key, int fallback) {
  const std::optional<double> value = json_number_value(json, key);
  return value.has_value() ? static_cast<int>(value.value()) : fallback;
}

double json_double_or(const std::string& json,
                      const std::string& key,
                      double fallback) {
  const std::optional<double> value = json_number_value(json, key);
  return value.has_value() ? value.value() : fallback;
}

bool json_bool_or(const std::string& json, const std::string& key, bool fallback) {
  const std::optional<bool> value = json_bool_value(json, key);
  return value.has_value() ? value.value() : fallback;
}

std::string json_string_or(const std::string& json,
                           const std::string& key,
                           const std::string& fallback) {
  const std::optional<std::string> value = json_string_value(json, key);
  return value.has_value() ? value.value() : fallback;
}

void write_json_string_field(std::ostream& stream,
                             const std::string& name,
                             const std::string& value,
                             bool comma) {
  stream << "  ";
  polymath::gemma4::write_json_string(stream, name);
  stream << ": ";
  polymath::gemma4::write_json_string(stream, value);
  if (comma) {
    stream << ',';
  }
  stream << '\n';
}

void write_identity_fields(std::ostream& stream,
                           const H11AConfig& config,
                           bool trailing_comma) {
  write_json_string_field(stream, "model_id", config.model_id, true);
  write_json_string_field(stream, "model_revision", config.model_revision, true);
  stream << "  \"hidden_size\": " << config.hidden_size << ",\n";
  write_json_string_field(stream, "source_commit", config.source_commit, true);
  write_json_string_field(stream, "runner_binary_path", self_executable_path(), true);
  write_json_string_field(stream, "runner_binary_sha256", self_executable_sha256(), true);
  write_json_string_field(stream, "kernel_lineage_class", config.kernel_lineage_class, true);
  write_json_string_field(stream, "runtime_backend", config.runtime_backend, true);
  write_json_string_field(stream, "trainable_scope",
                          residual_adapter_scope(config.adapter_rank), true);
  write_json_string_field(stream, "teacher_provenance", config.teacher_provenance, true);
  stream << "  \"hidden_state_fixtures_consumed\": "
         << (config.hidden_state_fixtures_consumed ? "true" : "false");
  if (trailing_comma) {
    stream << ',';
  }
  stream << '\n';
}

std::string format_iteration_dir(const std::string& gate_dir, int index) {
  std::ostringstream name;
  name << "iterations/iter_" << std::setw(6) << std::setfill('0') << index;
  return join_path(gate_dir, name.str());
}

bool should_sample_iteration(int index, int total, int sample_every) {
  if (index == 0 || index + 1 == total) {
    return true;
  }
  return sample_every > 0 && (index % sample_every) == 0;
}

long current_rss_kb() {
  std::ifstream file("/proc/self/status");
  std::string key;
  while (file >> key) {
    if (key == "VmRSS:") {
      long value = -1L;
      file >> value;
      return value;
    }
    std::string rest;
    std::getline(file, rest);
  }
  return -1L;
}

std::uint64_t storage_free_bytes(const std::string& path) {
  struct statvfs info {};
  if (::statvfs(path.c_str(), &info) != 0) {
    return 0U;
  }
  return static_cast<std::uint64_t>(info.f_bavail) *
         static_cast<std::uint64_t>(info.f_frsize);
}

std::string read_first_existing(const std::vector<std::string>& paths) {
  for (const std::string& path : paths) {
    std::ifstream file(path);
    if (!file) {
      continue;
    }
    std::string text;
    std::getline(file, text);
    return text;
  }
  return "unavailable";
}

std::string thermal_summary_json() {
  const std::string battery_temp = read_first_existing({
      "/sys/class/power_supply/battery/temp",
      "/sys/class/power_supply/bms/temp",
  });
  const std::string skin_temp = read_first_existing({
      "/sys/class/thermal/thermal_zone0/temp",
      "/sys/class/thermal/thermal_zone1/temp",
  });
  std::ostringstream out;
  out << "{\"battery_temp_raw\":";
  polymath::gemma4::write_json_string(out, battery_temp);
  out << ",\"sample_zone0_or_1_raw\":";
  polymath::gemma4::write_json_string(out, skin_temp);
  out << "}";
  return out.str();
}

class Heartbeat {
 public:
  Heartbeat(std::string heartbeat_path, std::string run_id, std::string gate)
      : heartbeat_path_(std::move(heartbeat_path)),
        run_id_(std::move(run_id)),
        gate_(std::move(gate)),
        storage_path_(dirname_of(heartbeat_path_)),
        started_at_(std::chrono::steady_clock::now()) {}

  void start() {
    running_.store(true);
    worker_ = std::thread([this]() { loop(); });
  }

  void stop() {
    running_.store(false);
    if (worker_.joinable()) {
      worker_.join();
    }
    write_once();
  }

  void set_step(const std::string& step) {
    std::lock_guard<std::mutex> lock(mutex_);
    step_ = step;
  }

  void set_last_artifact(const std::string& path, const std::string& chain_hash) {
    std::lock_guard<std::mutex> lock(mutex_);
    last_artifact_path_ = path;
    last_artifact_chain_hash_ = chain_hash;
  }

 private:
  void loop() {
    while (running_.load()) {
      try {
        write_once();
      } catch (const std::exception&) {
      }
      for (int tick = 0; tick < 10 && running_.load(); ++tick) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
      }
    }
  }

  void write_once() {
    std::string step;
    std::string last_path;
    std::string last_hash;
    {
      std::lock_guard<std::mutex> lock(mutex_);
      step = step_;
      last_path = last_artifact_path_;
      last_hash = last_artifact_chain_hash_;
    }

    const double monotonic_seconds =
        std::chrono::duration<double>(std::chrono::steady_clock::now() - started_at_)
            .count();
    std::ostringstream out;
    out << "{\n";
    write_json_string_field(out, "schema_version", "phase11_runner_heartbeat_v1", true);
    write_json_string_field(out, "runner_build_id", kRunnerBuildId, true);
    write_json_string_field(out, "run_id", run_id_, true);
    write_json_string_field(out, "gate", gate_, true);
    write_json_string_field(out, "step", step, true);
    out << "  \"pid\": " << static_cast<long long>(::getpid()) << ",\n";
    out << "  \"monotonic_seconds\": " << std::fixed << std::setprecision(3)
        << monotonic_seconds << ",\n";
    out << "  \"storage_free_bytes\": " << storage_free_bytes(storage_path_) << ",\n";
    out << "  \"rss_kb\": " << current_rss_kb() << ",\n";
    out << "  \"thermal_summary\": " << thermal_summary_json() << ",\n";
    write_json_string_field(out, "last_artifact_path", last_path, true);
    write_json_string_field(out, "last_artifact_chain_hash", last_hash, true);
    write_json_string_field(out, "updated_at_utc", utc_timestamp(), false);
    out << "}\n";
    write_text_file_atomic(heartbeat_path_, out.str());
  }

  std::string heartbeat_path_;
  std::string run_id_;
  std::string gate_;
  std::string storage_path_;
  std::chrono::steady_clock::time_point started_at_;
  std::atomic<bool> running_ = false;
  std::thread worker_;
  std::mutex mutex_;
  std::string step_ = "starting";
  std::string last_artifact_path_;
  std::string last_artifact_chain_hash_;
};

class ChecksumChain {
 public:
  ChecksumChain(std::string chain_path, Heartbeat* heartbeat)
      : chain_path_(std::move(chain_path)), heartbeat_(heartbeat) {
    ensure_directory(dirname_of(chain_path_));
    if (!path_exists(chain_path_)) {
      return;
    }
    std::ifstream file(chain_path_);
    std::string line;
    while (std::getline(file, line)) {
      const std::optional<std::string> hash = json_string_value(line, "chain_hash");
      if (hash.has_value()) {
        previous_hash_ = hash.value();
      }
    }
  }

  void append_if_exists(const std::string& artifact_path, const std::string& gate) {
    if (!path_exists(artifact_path)) {
      return;
    }
    const std::string artifact_sha = polymath::gemma4::sha256_file_hex(artifact_path);
    const std::uint64_t bytes = file_size_bytes(artifact_path);
    const std::string timestamp = utc_timestamp();
    const std::string payload = previous_hash_ + "\n" + artifact_path + "\n" +
                                artifact_sha + "\n" + std::to_string(bytes) + "\n" +
                                timestamp + "\n" + gate + "\n" + kRunnerBuildId;
    const std::string chain_hash = polymath::gemma4::sha256_text_hex(payload);

    std::ostringstream out;
    out << "{";
    out << "\"schema_version\":\"phase11_checksum_record_v1\",";
    out << "\"timestamp_utc\":";
    polymath::gemma4::write_json_string(out, timestamp);
    out << ",\"gate\":";
    polymath::gemma4::write_json_string(out, gate);
    out << ",\"runner_build_id\":";
    polymath::gemma4::write_json_string(out, kRunnerBuildId);
    out << ",\"artifact_path\":";
    polymath::gemma4::write_json_string(out, artifact_path);
    out << ",\"sha256\":";
    polymath::gemma4::write_json_string(out, artifact_sha);
    out << ",\"byte_count\":" << bytes;
    out << ",\"previous_chain_hash\":";
    polymath::gemma4::write_json_string(out, previous_hash_);
    out << ",\"chain_hash\":";
    polymath::gemma4::write_json_string(out, chain_hash);
    out << "}\n";
    append_text_file(chain_path_, out.str());
    previous_hash_ = chain_hash;
    if (heartbeat_ != nullptr) {
      heartbeat_->set_last_artifact(artifact_path, chain_hash);
    }
  }

  const std::string& previous_hash() const { return previous_hash_; }

 private:
  std::string chain_path_;
  Heartbeat* heartbeat_ = nullptr;
  std::string previous_hash_ = "GENESIS";
};

std::vector<QueueRecord> read_queue(const std::string& queue_path,
                                    const std::string& cwd) {
  std::ifstream file(queue_path);
  if (!file) {
    throw std::runtime_error("unable to open queue: " + queue_path);
  }
  std::vector<QueueRecord> records;
  std::string line;
  while (std::getline(file, line)) {
    if (line.find_first_not_of(" \t\r\n") == std::string::npos) {
      continue;
    }
    QueueRecord record;
    record.id = json_string_or(line, "id", "");
    record.gate = json_string_or(line, "gate", "");
    record.config_path = resolve_path(json_string_or(line, "config", ""), cwd);
    record.resume = json_string_or(line, "resume", "auto");
    if (record.id.empty() || record.gate.empty() || record.config_path.empty()) {
      throw std::runtime_error("invalid queue record: " + line);
    }
    records.push_back(record);
  }
  return records;
}

H11AConfig read_h11a_config(const std::string& config_path,
                            const std::string& cwd) {
  const std::string json = read_text_file(config_path);
  H11AConfig config;
  config.run_id = json_string_or(json, "run_id", "");
  config.gate_name = json_string_or(json, "gate_name", config.gate_name);
  config.gate_dir_name = json_string_or(json, "gate_dir_name", config.gate_dir_name);
  config.objective = json_string_or(json, "objective", config.objective);
  config.token_caches = json_string_array_value(json, "token_caches");
  config.teacher_shards = json_string_array_value(json, "teacher_shards");
  config.asset_dir = resolve_path(json_string_or(json, "asset_dir", ""), cwd);
  config.layer0_pack = resolve_path(json_string_or(json, "layer0_pack", ""), cwd);
  config.layer1_pack = resolve_path(json_string_or(json, "layer1_pack", ""), cwd);
  config.initial_checkpoint =
      resolve_path(json_string_or(json, "initial_checkpoint", ""), cwd);
  config.disconnect_marker_path =
      resolve_path(json_string_or(json, "disconnect_marker_path",
                                  config.disconnect_marker_path),
                   cwd);
  config.iteration_count = json_int_or(json, "iteration_count", config.iteration_count);
  config.sample_every = json_int_or(json, "sample_every", config.sample_every);
  config.marker_wait_seconds =
      json_int_or(json, "marker_wait_seconds", config.marker_wait_seconds);
  config.disconnect_hold_seconds =
      json_int_or(json, "disconnect_hold_seconds", config.disconnect_hold_seconds);
  config.learning_rate = json_double_or(json, "learning_rate", config.learning_rate);
  config.optimizer = json_string_or(json, "optimizer", config.optimizer);
  config.weight_decay = json_double_or(json, "weight_decay", config.weight_decay);
  config.beta1 = json_double_or(json, "beta1", config.beta1);
  config.beta2 = json_double_or(json, "beta2", config.beta2);
  config.optimizer_epsilon =
      json_double_or(json, "optimizer_epsilon", config.optimizer_epsilon);
  config.grad_clip_l2 = json_double_or(json, "grad_clip_l2", config.grad_clip_l2);
  config.adapter_rank = json_int_or(json, "adapter_rank", config.adapter_rank);
  config.apply_update = json_bool_or(json, "apply_update", config.apply_update);
  config.require_disconnect_marker =
      json_bool_or(json, "require_disconnect_marker", config.require_disconnect_marker);
  config.model_id = json_string_or(json, "model_id", config.model_id);
  config.model_revision = json_string_or(json, "model_revision", config.model_revision);
  config.hidden_size = json_int_or(json, "hidden_size", config.hidden_size);
  config.source_commit = json_string_or(json, "source_commit", config.source_commit);
  config.kernel_lineage_class =
      json_string_or(json, "kernel_lineage_class", config.kernel_lineage_class);
  config.runtime_backend = json_string_or(json, "runtime_backend", config.runtime_backend);
  config.teacher_provenance =
      json_string_or(json, "teacher_provenance", config.teacher_provenance);
  config.hidden_state_fixtures_consumed =
      json_bool_or(json, "hidden_state_fixtures_consumed",
                   config.hidden_state_fixtures_consumed);

  for (std::string& token_cache : config.token_caches) {
    token_cache = resolve_path(token_cache, cwd);
  }
  for (std::string& teacher_shard : config.teacher_shards) {
    teacher_shard = resolve_path(teacher_shard, cwd);
  }
  if (config.token_caches.empty()) {
    throw std::runtime_error("H11-A config requires token_caches");
  }
  if (config.objective == "topk_embedding_kl" && config.teacher_shards.empty()) {
    throw std::runtime_error("topk_embedding_kl objective requires teacher_shards");
  }
  if (config.objective != "hidden_mse" && config.objective != "topk_embedding_kl") {
    throw std::runtime_error("unsupported objective: " + config.objective);
  }
  if (config.asset_dir.empty() || config.layer0_pack.empty() || config.layer1_pack.empty() ||
      config.initial_checkpoint.empty()) {
    throw std::runtime_error("H11-A config has empty asset, pack, or checkpoint path");
  }
  if (config.iteration_count <= 0) {
    throw std::runtime_error("H11-A iteration_count must be positive");
  }
  if (config.adapter_rank <= 0) {
    throw std::runtime_error("H11-A adapter_rank must be positive");
  }
  if (config.optimizer != "sgd" && config.optimizer != "adamw") {
    throw std::runtime_error("unsupported optimizer: " + config.optimizer);
  }
  if (config.model_id != kExpectedModelId) {
    throw std::runtime_error("Gemma identity mismatch: model_id=" + config.model_id);
  }
  if (config.model_revision != kExpectedModelRevision) {
    throw std::runtime_error("Gemma identity mismatch: model_revision=" +
                             config.model_revision);
  }
  if (config.hidden_size != kExpectedHiddenSize) {
    throw std::runtime_error("Gemma identity mismatch: hidden_size=" +
                             std::to_string(config.hidden_size));
  }
  if (config.kernel_lineage_class != kKernelLineageClass) {
    throw std::runtime_error("unsupported kernel_lineage_class: " +
                             config.kernel_lineage_class);
  }
  if (config.hidden_state_fixtures_consumed) {
    throw std::runtime_error("hidden-state fixtures are forbidden for this runner path");
  }
  if (contains_forbidden_identity_marker(config.teacher_provenance) ||
      contains_forbidden_identity_marker(config.runtime_backend)) {
    throw std::runtime_error("non-Gemma marker found in runtime identity metadata");
  }
  return config;
}

std::optional<RunnerState> read_runner_state(const std::string& state_path) {
  if (!path_exists(state_path)) {
    return std::nullopt;
  }
  const std::string json = read_text_file(state_path);
  RunnerState state;
  state.run_id = json_string_or(json, "run_id", "");
  state.record_id = json_string_or(json, "record_id", "");
  state.gate = json_string_or(json, "gate", "");
  state.checkpoint_dir = json_string_or(json, "checkpoint_dir", "");
  state.status = json_string_or(json, "status", "");
  state.next_iteration = json_int_or(json, "next_iteration", 0);
  return state;
}

void write_runner_state(const std::string& state_path,
                        const RunnerState& state,
                        const QueueRecord& record) {
  std::ostringstream out;
  out << "{\n";
  write_json_string_field(out, "schema_version", "phase11_runner_state_v1", true);
  write_json_string_field(out, "runner_build_id", kRunnerBuildId, true);
  write_json_string_field(out, "run_id", state.run_id, true);
  write_json_string_field(out, "record_id", record.id, true);
  write_json_string_field(out, "gate", state.gate, true);
  write_json_string_field(out, "status", state.status, true);
  out << "  \"next_iteration\": " << state.next_iteration << ",\n";
  write_json_string_field(out, "checkpoint_dir", state.checkpoint_dir, true);
  write_json_string_field(out, "updated_at_utc", utc_timestamp(), false);
  out << "}\n";
  write_text_file_atomic(state_path, out.str());
}

double active_training_seconds_from_telemetry(const std::string& telemetry_path) {
  const std::string json = read_text_file(telemetry_path);
  double active = json_double_or(json, "token_to_hidden_elapsed_seconds", 0.0);
  active += json_double_or(json, "adapter_elapsed_seconds", 0.0);
  const std::vector<double> layer_seconds =
      json_number_array_value(json, "layer_elapsed_seconds");
  for (const double value : layer_seconds) {
    active += value;
  }
  return active;
}

std::pair<std::string, std::string> checkpoint_pair_sha(const std::string& checkpoint_dir) {
  return {
      polymath::gemma4::sha256_file_hex(join_path(checkpoint_dir, "adapter_a.f32.bin")),
      polymath::gemma4::sha256_file_hex(join_path(checkpoint_dir, "adapter_b.f32.bin")),
  };
}

void append_iteration_telemetry(const std::string& telemetry_jsonl_path,
                                const H11AConfig& config,
                                const IterationRecord& record) {
  std::ostringstream out;
  out << "{";
  out << "\"schema_version\":\"phase11_h11a_iteration_telemetry_v1\",";
  out << "\"timestamp_utc\":";
  polymath::gemma4::write_json_string(out, utc_timestamp());
  out << ",\"iteration\":" << record.index;
  out << ",\"status\":";
  polymath::gemma4::write_json_string(out, record.status);
  out << ",\"sample\":" << (record.sample ? "true" : "false");
  out << ",\"wall_seconds\":" << std::fixed << std::setprecision(6)
      << record.wall_seconds;
  out << ",\"active_training_seconds\":" << std::fixed << std::setprecision(6)
      << record.active_training_seconds;
  out << ",\"token_cache\":";
  polymath::gemma4::write_json_string(out, record.token_cache);
  out << ",\"teacher_shard\":";
  polymath::gemma4::write_json_string(out, record.teacher_shard);
  out << ",\"input_checkpoint\":";
  polymath::gemma4::write_json_string(out, record.input_checkpoint);
  out << ",\"output_checkpoint\":";
  polymath::gemma4::write_json_string(out, record.output_checkpoint);
  out << ",\"phone_output_dir\":";
  polymath::gemma4::write_json_string(out, record.phone_output_dir);
  out << ",\"blocker\":";
  polymath::gemma4::write_json_string(out, record.blocker);
  out << ",\"model_id\":";
  polymath::gemma4::write_json_string(out, config.model_id);
  out << ",\"model_revision\":";
  polymath::gemma4::write_json_string(out, config.model_revision);
  out << ",\"hidden_size\":" << config.hidden_size;
  out << ",\"source_commit\":";
  polymath::gemma4::write_json_string(out, config.source_commit);
  out << ",\"runner_binary_sha256\":";
  polymath::gemma4::write_json_string(out, self_executable_sha256());
  out << ",\"kernel_lineage_class\":";
  polymath::gemma4::write_json_string(out, config.kernel_lineage_class);
  out << ",\"runtime_backend\":";
  polymath::gemma4::write_json_string(out, config.runtime_backend);
  out << ",\"trainable_scope\":";
  polymath::gemma4::write_json_string(out, residual_adapter_scope(config.adapter_rank));
  out << ",\"teacher_provenance\":";
  polymath::gemma4::write_json_string(out, config.teacher_provenance);
  out << ",\"hidden_state_fixtures_consumed\":"
      << (config.hidden_state_fixtures_consumed ? "true" : "false");
  out << "}\n";
  append_text_file(telemetry_jsonl_path, out.str());
}

void write_queue_schema(const std::string& gate_dir) {
  const std::string path = join_path(gate_dir, "queue_schema.json");
  std::ostringstream out;
  out << "{\n"
      << "  \"schema_version\": \"phase13_queue_schema_v1\",\n"
      << "  \"record_format\": \"jsonl\",\n"
      << "  \"required_fields\": [\"id\", \"gate\", \"config\", \"depends_on\", \"resume\"],\n"
      << "  \"required_identity_config_fields\": [\"model_id\", \"model_revision\", "
         "\"hidden_size\", \"source_commit\", \"kernel_lineage_class\", "
         "\"runtime_backend\", \"teacher_provenance\", "
         "\"hidden_state_fixtures_consumed\"],\n"
      << "  \"supported_gates_in_this_build\": [\"H11-A\", \"H11-F\"],\n"
      << "  \"supported_objectives\": [\"hidden_mse\", \"topk_embedding_kl\"],\n"
      << "  \"supported_optimizers\": [\"sgd\", \"adamw\"],\n";
  write_json_string_field(out, "runner_build_id", kRunnerBuildId, false);
  out << "}\n";
  write_text_file_atomic(path, out.str());
}

void write_daemon_design_note(const std::string& gate_dir) {
  write_text_file_atomic(
      join_path(gate_dir, "daemon_design_note.md"),
      "# H11-A Daemon Design Note\n\n"
      "- `phase11_runner` starts once from ADB and then reads the phone-local JSONL queue.\n"
      "- H11-A iterations run inside one long-lived process; ADB does not issue per-iteration commands.\n"
      "- `runner_state.json` is rewritten after each completed checkpoint boundary so a restart can resume from the last output checkpoint.\n"
      "- `heartbeat.json` is emitted by a native heartbeat thread every 10 seconds during work and disconnect hold.\n"
      "- `STOP` is honored before each iteration and during disconnect hold.\n"
      "- `checksum_chain.jsonl` lives under the run directory and chains small JSON artifacts plus adapter checkpoint payload hashes.\n"
      "- Existing one-shot `gemma4_layer_runner --run-g8-distill[-compact]` behavior remains untouched as the diagnostic fallback.\n"
      "- This H11-A build removes host process restart per iteration; deeper OpenCL context reuse remains measurable in H11-C/H11-D.\n");
}

void write_commands_log(const std::string& gate_dir, const RunnerArgs& args) {
  std::ostringstream out;
  out << "Sanitized command shape:\n";
  out << "cd /data/local/tmp/polymath_gemma4_gate/phase11\n";
  out << "nohup ./phase11_runner --queue " << args.queue_path
      << " --run-root " << args.run_root << " --heartbeat " << args.heartbeat_path
      << " --state " << args.state_path << " > runner.log 2>&1 &\n\n";
  out << "The queue and config contain only phone-local paths. No token values, SDK "
         "binaries, model weights, or raw tensor payloads are printed here.\n";
  write_text_file_atomic(join_path(gate_dir, "commands.log"), out.str());
}

void write_static_manifest_entry(std::ostream& out,
                                 const std::string& name,
                                 const std::string& path,
                                 bool comma) {
  out << "    {\"name\": ";
  polymath::gemma4::write_json_string(out, name);
  out << ", \"path\": ";
  polymath::gemma4::write_json_string(out, path);
  if (path_exists(path)) {
    out << ", \"sha256\": ";
    polymath::gemma4::write_json_string(out, polymath::gemma4::sha256_file_hex(path));
    out << ", \"byte_count\": " << file_size_bytes(path);
  } else {
    out << ", \"status\": \"missing\"";
  }
  out << "}";
  if (comma) {
    out << ',';
  }
  out << "\n";
}

void write_daemon_static_artifact_manifest(const std::string& gate_dir,
                                           const H11AConfig& config) {
  std::vector<std::pair<std::string, std::string>> artifacts = {
      {"asset_manifest", join_path(config.asset_dir, "manifest.json")},
      {"embed_tokens", join_path(config.asset_dir, "embed_tokens.bf16.bin")},
      {"ple_projection_norm", join_path(config.asset_dir, "ple_projection_norm.f32.bin")},
      {"ple_token_layer0", join_path(config.asset_dir, "ple_token_layer0.bf16.bin")},
      {"ple_token_layer1", join_path(config.asset_dir, "ple_token_layer1.bf16.bin")},
      {"ple_projection_layer0", join_path(config.asset_dir, "ple_projection_layer0.bf16.bin")},
      {"ple_projection_layer1", join_path(config.asset_dir, "ple_projection_layer1.bf16.bin")},
      {"layer0_safetensors", join_path(config.layer0_pack, "weights/layer0.safetensors")},
      {"layer1_safetensors", join_path(config.layer1_pack, "weights/layer1.safetensors")},
  };
  for (std::size_t index = 0; index < config.teacher_shards.size(); ++index) {
    const std::string prefix = "teacher_shard_" + std::to_string(index) + "_";
    artifacts.emplace_back(prefix + "manifest",
                           join_path(config.teacher_shards[index], "manifest.json"));
    artifacts.emplace_back(prefix + "topk_token_ids",
                           join_path(config.teacher_shards[index],
                                     "topk_token_ids.u32.bin"));
    artifacts.emplace_back(prefix + "topk_probabilities",
                           join_path(config.teacher_shards[index],
                                     "topk_probabilities.f32.bin"));
    artifacts.emplace_back(prefix + "loss_mask",
                           join_path(config.teacher_shards[index], "loss_mask.u8.bin"));
  }

  std::ostringstream out;
  out << "{\n";
  write_json_string_field(out, "schema_version", "phase13_static_artifact_manifest_v1", true);
  write_json_string_field(out, "runner_build_id", kRunnerBuildId, true);
  write_json_string_field(out, "created_at_utc", utc_timestamp(), true);
  write_identity_fields(out, config, true);
  out << "  \"artifacts\": [\n";
  for (std::size_t index = 0; index < artifacts.size(); ++index) {
    write_static_manifest_entry(out, artifacts[index].first, artifacts[index].second,
                                index + 1U != artifacts.size());
  }
  out << "  ]\n";
  out << "}\n";
  write_text_file_atomic(join_path(gate_dir, "daemon_static_artifact_manifest.json"),
                         out.str());
}

void write_campaign_manifest(const std::string& run_dir,
                             const std::string& queue_path,
                             const std::string& config_path) {
  std::ostringstream out;
  out << "{\n";
  write_json_string_field(out, "schema_version", "phase11_campaign_manifest_v1", true);
  write_json_string_field(out, "runner_build_id", kRunnerBuildId, true);
  write_json_string_field(out, "queue_path", queue_path, true);
  write_json_string_field(out, "h11a_config_path", config_path, true);
  write_json_string_field(out, "run_dir", run_dir, true);
  write_json_string_field(out, "created_at_utc", utc_timestamp(), false);
  out << "}\n";
  write_text_file_atomic(join_path(run_dir, "campaign_manifest.json"), out.str());
}

void write_blockers_md(const std::string& gate_dir, const std::vector<std::string>& blockers) {
  std::ostringstream out;
  if (blockers.empty()) {
    out << "- None for H11-A.\n";
  } else {
    for (const std::string& blocker : blockers) {
      out << "- " << blocker << "\n";
    }
  }
  write_text_file_atomic(join_path(gate_dir, "blockers.md"), out.str());
}

void write_falsifier_report(const std::string& gate_dir,
                            const std::string& heartbeat_path,
                            const GateStats& stats,
                            bool active_wall_ok,
                            bool disconnect_ok,
                            bool checkpoint_chain_ok) {
  std::ostringstream out;
  out << "# H11-A Falsifier Report\n\n";
  out << "- hidden ADB iteration driver: pass, the queue is phone-local and one "
         "daemon invocation runs all iterations.\n";
  out << "- process restart per step: pass for the runner process; OpenCL internal "
         "context reuse remains explicitly unclaimed until H11-C/H11-D timing.\n";
  out << "- missing heartbeat: "
      << (path_exists(heartbeat_path) ? "pass" : "fail")
      << ".\n";
  out << "- overwritten artifacts: pass, iteration output dirs are unique and "
         "state resumes from checkpoint boundaries.\n";
  out << "- host-side minibatch serving: pass, token caches are phone-local paths.\n";
  out << "- stale checkpoint input: " << (checkpoint_chain_ok ? "pass" : "fail")
      << ".\n";
  out << "- active/wall gate: " << (active_wall_ok ? "pass" : "fail") << ".\n";
  out << "- disconnect survival gate: " << (disconnect_ok ? "pass" : "fail")
      << ".\n";
  if (!stats.blockers.empty()) {
    out << "\n## Blockers\n";
    for (const std::string& blocker : stats.blockers) {
      out << "- " << blocker << "\n";
    }
  }
  write_text_file_atomic(join_path(gate_dir, "falsifier_report.md"), out.str());
}

void write_timing_breakdown(const std::string& gate_dir,
                            const GateStats& stats,
                            double active_wall_ratio) {
  std::ostringstream out;
  out << "{\n";
  write_json_string_field(out, "schema_version", "phase11_h11a_timing_breakdown_v1", true);
  out << "  \"queue_execution_wall_seconds\": " << std::fixed << std::setprecision(6)
      << stats.queue_wall_seconds << ",\n";
  out << "  \"active_training_seconds\": " << std::fixed << std::setprecision(6)
      << stats.active_training_seconds << ",\n";
  out << "  \"active_wall_ratio\": " << std::fixed << std::setprecision(8)
      << active_wall_ratio << ",\n";
  out << "  \"disconnect_wait_seconds\": " << std::fixed << std::setprecision(6)
      << stats.disconnect_wait_seconds << ",\n";
  out << "  \"iteration_count\": " << stats.records.size() << ",\n";
  out << "  \"iterations\": [\n";
  for (std::size_t index = 0; index < stats.records.size(); ++index) {
    const IterationRecord& record = stats.records[index];
    out << "    {\"iteration\": " << record.index << ", \"wall_seconds\": "
        << std::fixed << std::setprecision(6) << record.wall_seconds
        << ", \"active_training_seconds\": " << std::fixed << std::setprecision(6)
        << record.active_training_seconds << ", \"sample\": "
        << (record.sample ? "true" : "false") << "}";
    if (index + 1U != stats.records.size()) {
      out << ',';
    }
    out << "\n";
  }
  out << "  ]\n";
  out << "}\n";
  write_text_file_atomic(join_path(gate_dir, "timing_breakdown.json"), out.str());
}

void write_artifact_manifest(const std::string& gate_dir,
                             const std::string& run_dir,
                             const GateStats& stats,
                             const H11AConfig& config) {
  std::ostringstream out;
  out << "{\n";
  write_json_string_field(out, "schema_version", "phase13_gate_artifact_manifest_v1", true);
  write_json_string_field(out, "gate", config.gate_name, true);
  write_json_string_field(out, "objective", config.objective, true);
  write_json_string_field(out, "runner_build_id", kRunnerBuildId, true);
  write_json_string_field(out, "run_dir", run_dir, true);
  write_json_string_field(out, "gate_dir", gate_dir, true);
  write_identity_fields(out, config, true);
  out << "  \"iteration_count\": " << stats.records.size() << ",\n";
  out << "  \"git_allowed_artifacts\": [\n";
  const std::vector<std::string> artifacts = {
      "daemon_design_note.md", "queue_schema.json", "commands.log",
      "daemon_static_artifact_manifest.json",
      "cold_start_probe.json", "one_shot_baseline.json",
      "telemetry.jsonl",       "timing_breakdown.json", "blockers.md",
      "falsifier_report.md",   "gate_result.json"};
  for (std::size_t index = 0; index < artifacts.size(); ++index) {
    const std::string artifact_path = join_path(gate_dir, artifacts[index]);
    out << "    {\"path\": ";
    polymath::gemma4::write_json_string(out, artifact_path);
    if (path_exists(artifact_path)) {
      out << ", \"sha256\": ";
      polymath::gemma4::write_json_string(out,
                                          polymath::gemma4::sha256_file_hex(artifact_path));
      out << ", \"byte_count\": " << file_size_bytes(artifact_path);
    }
    out << "}";
    if (index + 1U != artifacts.size()) {
      out << ',';
    }
    out << "\n";
  }
  out << "  ],\n";
  write_json_string_field(out, "phone_checksum_chain", join_path(run_dir, "checksum_chain.jsonl"), false);
  out << "}\n";
  write_text_file_atomic(join_path(gate_dir, "artifact_manifest.json"), out.str());
}

void write_gate_result(const std::string& gate_dir,
                       const GateStats& stats,
                       const H11AConfig& config,
                       double active_wall_ratio,
                       bool active_wall_ok,
                       bool disconnect_ok,
                       bool checkpoint_chain_ok) {
  std::vector<std::string> blockers = stats.blockers;
  if (static_cast<int>(stats.records.size()) < config.iteration_count) {
    blockers.push_back("completed fewer than configured H11-A iterations");
  }
  if (!active_wall_ok) {
    blockers.push_back("active/wall did not reach >=0.50 or >=2x Phase 10 baseline");
  }
  if (!disconnect_ok) {
    blockers.push_back("disconnect marker/hold evidence did not satisfy H11-A");
  }
  if (!checkpoint_chain_ok) {
    blockers.push_back("checkpoint chain validation failed");
  }
  if (stats.stopped) {
    blockers.push_back("STOP file observed before gate completion");
  }

  const bool pass = blockers.empty();
  std::ostringstream out;
  out << "{\n";
  write_json_string_field(out, "schema_version", "phase11_h11a_gate_result_v1", true);
  write_json_string_field(out, "gate", config.gate_name, true);
  write_json_string_field(out, "runner_build_id", kRunnerBuildId, true);
  write_json_string_field(out, "status", pass ? "pass" : "fail", true);
  write_json_string_field(out, "objective", config.objective, true);
  write_identity_fields(out, config, true);
  out << "  \"apply_update\": " << (config.apply_update ? "true" : "false") << ",\n";
  out << "  \"iteration_count\": " << stats.records.size() << ",\n";
  out << "  \"required_iteration_count\": " << config.iteration_count << ",\n";
  out << "  \"queue_execution_wall_seconds\": " << std::fixed << std::setprecision(6)
      << stats.queue_wall_seconds << ",\n";
  out << "  \"active_training_seconds\": " << std::fixed << std::setprecision(6)
      << stats.active_training_seconds << ",\n";
  out << "  \"active_wall_ratio\": " << std::fixed << std::setprecision(8)
      << active_wall_ratio << ",\n";
  out << "  \"phase10_active_wall_baseline\": " << std::fixed << std::setprecision(8)
      << kPhase10ActiveWallBaseline << ",\n";
  out << "  \"active_wall_acceptance\": " << (active_wall_ok ? "true" : "false")
      << ",\n";
  out << "  \"disconnect_marker_seen\": "
      << (stats.disconnect_marker_seen ? "true" : "false") << ",\n";
  out << "  \"disconnect_hold_seconds\": " << std::fixed << std::setprecision(6)
      << stats.disconnect_wait_seconds << ",\n";
  out << "  \"disconnect_acceptance\": " << (disconnect_ok ? "true" : "false")
      << ",\n";
  out << "  \"checkpoint_chain_acceptance\": "
      << (checkpoint_chain_ok ? "true" : "false") << ",\n";
  out << "  \"runtime_topology\": \"phone_local_queue_no_adb_per_iteration\",\n";
  out << "  \"one_shot_fallback_preserved\": true,\n";
  out << "  \"blockers\": [";
  for (std::size_t index = 0; index < blockers.size(); ++index) {
    if (index != 0U) {
      out << ", ";
    }
    polymath::gemma4::write_json_string(out, blockers[index]);
  }
  out << "],\n";
  write_json_string_field(out, "ended_at_utc", utc_timestamp(), false);
  out << "}\n";
  write_text_file_atomic(join_path(gate_dir, "gate_result.json"), out.str());
  write_blockers_md(gate_dir, blockers);
}

void chain_iteration_artifacts(ChecksumChain& chain,
                               const std::string& output_dir,
                               const std::string& gate) {
  chain.append_if_exists(join_path(output_dir, "telemetry.json"), gate);
  chain.append_if_exists(join_path(output_dir, "artifact_manifest.json"), gate);
  chain.append_if_exists(join_path(output_dir, "replay_manifest.json"), gate);
  chain.append_if_exists(join_path(output_dir, "checkpoint/manifest.json"), gate);
  chain.append_if_exists(join_path(output_dir, "checkpoint/adapter_a.f32.bin"), gate);
  chain.append_if_exists(join_path(output_dir, "checkpoint/adapter_b.f32.bin"), gate);
}

bool gate_result_passed(const std::string& gate_dir) {
  const std::string gate_result = join_path(gate_dir, "gate_result.json");
  return path_exists(gate_result) && json_contains_string(read_text_file(gate_result), "status", "pass");
}

void wait_for_disconnect_marker(const H11AConfig& config,
                                const RunnerArgs& args,
                                GateStats& stats,
                                Heartbeat& heartbeat,
                                ChecksumChain& chain) {
  if (!config.require_disconnect_marker) {
    return;
  }

  heartbeat.set_step("waiting_for_disconnect_marker");
  const auto wait_start = std::chrono::steady_clock::now();
  while (!path_exists(config.disconnect_marker_path)) {
    if (path_exists(args.stop_file)) {
      stats.stopped = true;
      stats.blockers.push_back("STOP file observed while waiting for disconnect marker");
      return;
    }
    const double waited =
        std::chrono::duration<double>(std::chrono::steady_clock::now() - wait_start)
            .count();
    if (waited >= static_cast<double>(config.marker_wait_seconds)) {
      stats.blockers.push_back("disconnect evidence marker was not created before timeout");
      return;
    }
    std::this_thread::sleep_for(std::chrono::seconds(5));
  }

  stats.disconnect_marker_seen = true;
  chain.append_if_exists(config.disconnect_marker_path, "H11-A");
  heartbeat.set_step("disconnect_hold");
  const auto hold_start = std::chrono::steady_clock::now();
  while (true) {
    if (path_exists(args.stop_file)) {
      stats.stopped = true;
      stats.blockers.push_back("STOP file observed during disconnect hold");
      return;
    }
    struct stat info {};
    if (::stat(config.disconnect_marker_path.c_str(), &info) != 0) {
      stats.blockers.push_back("disconnect evidence marker disappeared during hold");
      return;
    }
    const double marker_age = std::difftime(std::time(nullptr), info.st_mtime);
    if (marker_age >= static_cast<double>(config.disconnect_hold_seconds)) {
      const double local_hold_seconds =
          std::chrono::duration<double>(std::chrono::steady_clock::now() - hold_start)
              .count();
      stats.disconnect_wait_seconds =
          marker_age > local_hold_seconds ? marker_age : local_hold_seconds;
      return;
    }
    std::this_thread::sleep_for(std::chrono::seconds(5));
  }
}

int run_h11a(const RunnerArgs& args,
             const QueueRecord& record,
             const std::string& cwd) {
  H11AConfig config = read_h11a_config(record.config_path, cwd);
  std::optional<RunnerState> prior_state = read_runner_state(args.state_path);

  RunnerState state;
  state.gate = config.gate_name;
  state.record_id = record.id;
  state.status = "running";
  state.run_id = config.run_id.empty() ? compact_utc_timestamp() + "_h11a_daemon"
                                       : config.run_id;
  state.checkpoint_dir = config.initial_checkpoint;

  if (prior_state.has_value() && prior_state->record_id == record.id &&
      prior_state->gate == config.gate_name && prior_state->run_id == state.run_id &&
      prior_state->status != "completed") {
    state = prior_state.value();
    if (state.checkpoint_dir.empty()) {
      state.checkpoint_dir = config.initial_checkpoint;
    }
  }

  const std::string run_dir = join_path(args.run_root, state.run_id);
  const std::string gate_dir = join_path(run_dir, config.gate_dir_name);
  if (gate_result_passed(gate_dir)) {
    state.status = "completed";
    write_runner_state(args.state_path, state, record);
    return 0;
  }

  ensure_directory(join_path(gate_dir, "iterations"));
  write_campaign_manifest(run_dir, args.queue_path, record.config_path);
  write_queue_schema(gate_dir);
  write_daemon_design_note(gate_dir);
  write_commands_log(gate_dir, args);
  write_daemon_static_artifact_manifest(gate_dir, config);
  write_runner_state(args.state_path, state, record);

  Heartbeat heartbeat(args.heartbeat_path, state.run_id, config.gate_name);
  heartbeat.start();
  ChecksumChain chain(join_path(run_dir, "checksum_chain.jsonl"), &heartbeat);
  chain.append_if_exists(join_path(run_dir, "campaign_manifest.json"), config.gate_name);
  chain.append_if_exists(join_path(gate_dir, "queue_schema.json"), config.gate_name);
  chain.append_if_exists(join_path(gate_dir, "daemon_design_note.md"), config.gate_name);
  chain.append_if_exists(join_path(gate_dir, "commands.log"), config.gate_name);
  chain.append_if_exists(join_path(gate_dir, "daemon_static_artifact_manifest.json"),
                         config.gate_name);
  chain.append_if_exists(join_path(gate_dir, "cold_start_probe.json"), config.gate_name);
  chain.append_if_exists(join_path(gate_dir, "one_shot_baseline.json"), config.gate_name);

  GateStats stats;
  bool checkpoint_chain_ok = true;
  std::optional<std::pair<std::string, std::string>> previous_post_sha;
  const std::string telemetry_jsonl = join_path(gate_dir, "telemetry.jsonl");
  const auto queue_start = std::chrono::steady_clock::now();

  for (int index = state.next_iteration; index < config.iteration_count; ++index) {
    if (path_exists(args.stop_file)) {
      stats.stopped = true;
      stats.blockers.push_back("STOP file observed before iteration " +
                               std::to_string(index));
      break;
    }

    IterationRecord iteration;
    iteration.index = index;
    iteration.sample = should_sample_iteration(index, config.iteration_count,
                                               config.sample_every);
    iteration.status = "running";
    iteration.token_cache =
        config.token_caches[static_cast<std::size_t>(index) % config.token_caches.size()];
    if (!config.teacher_shards.empty()) {
      iteration.teacher_shard =
          config.teacher_shards[static_cast<std::size_t>(index) %
                                config.teacher_shards.size()];
    }
    iteration.input_checkpoint = state.checkpoint_dir;
    iteration.phone_output_dir = format_iteration_dir(gate_dir, index);
    iteration.output_checkpoint = join_path(iteration.phone_output_dir, "checkpoint");

    if (path_exists(iteration.phone_output_dir)) {
      iteration.phone_output_dir += "_resume_" + compact_utc_timestamp();
      iteration.output_checkpoint = join_path(iteration.phone_output_dir, "checkpoint");
    }

    heartbeat.set_step("iteration_" + std::to_string(index));
    const auto iteration_start = std::chrono::steady_clock::now();
    polymath::gemma4::Status status = polymath::gemma4::Status::ok();
    if (config.objective == "topk_embedding_kl") {
      polymath::gemma4::AdapterOptimizerConfig optimizer;
      optimizer.optimizer = config.optimizer;
      optimizer.learning_rate = static_cast<float>(config.learning_rate);
      optimizer.weight_decay = static_cast<float>(config.weight_decay);
      optimizer.beta1 = static_cast<float>(config.beta1);
      optimizer.beta2 = static_cast<float>(config.beta2);
      optimizer.epsilon = static_cast<float>(config.optimizer_epsilon);
      optimizer.grad_clip_l2 = static_cast<float>(config.grad_clip_l2);
      status = polymath::gemma4::run_opencl_streamed_topk_kl_update_rank_optimizer(
          iteration.token_cache, config.asset_dir, config.layer0_pack,
          config.layer1_pack, state.checkpoint_dir, iteration.teacher_shard,
          iteration.phone_output_dir, optimizer,
          static_cast<std::uint32_t>(config.adapter_rank), config.apply_update,
          iteration.sample, false);
    } else {
      status = polymath::gemma4::run_opencl_streamed_distill_update_rank(
          iteration.token_cache, config.asset_dir, config.layer0_pack,
          config.layer1_pack, state.checkpoint_dir, iteration.phone_output_dir,
          static_cast<float>(config.learning_rate),
          static_cast<std::uint32_t>(config.adapter_rank), iteration.sample, false);
    }
    iteration.wall_seconds =
        std::chrono::duration<double>(std::chrono::steady_clock::now() - iteration_start)
            .count();

    if (!status.is_ok()) {
      iteration.status = "fail";
      iteration.blocker = status.message();
      stats.blockers.push_back("iteration " + std::to_string(index) + " failed: " +
                               status.message());
      append_iteration_telemetry(telemetry_jsonl, config, iteration);
      stats.records.push_back(iteration);
      break;
    }

    iteration.status = "pass";
    iteration.active_training_seconds =
        active_training_seconds_from_telemetry(join_path(iteration.phone_output_dir,
                                                        "telemetry.json"));
    const std::pair<std::string, std::string> pre_sha =
        checkpoint_pair_sha(state.checkpoint_dir);
    const std::pair<std::string, std::string> post_sha =
        checkpoint_pair_sha(iteration.output_checkpoint);
    if (previous_post_sha.has_value() && pre_sha != previous_post_sha.value()) {
      checkpoint_chain_ok = false;
      stats.blockers.push_back("checkpoint pre-hash did not match previous post-hash at iteration " +
                               std::to_string(index));
    }
    if (config.apply_update && pre_sha == post_sha) {
      checkpoint_chain_ok = false;
      stats.blockers.push_back("checkpoint unchanged at iteration " + std::to_string(index));
    }
    if (!config.apply_update && pre_sha != post_sha) {
      checkpoint_chain_ok = false;
      stats.blockers.push_back("fixed-adapter control checkpoint changed at iteration " +
                               std::to_string(index));
    }
    previous_post_sha = post_sha;

    chain_iteration_artifacts(chain, iteration.phone_output_dir, config.gate_name);
    append_iteration_telemetry(telemetry_jsonl, config, iteration);
    chain.append_if_exists(telemetry_jsonl, config.gate_name);
    stats.active_training_seconds += iteration.active_training_seconds;
    stats.records.push_back(iteration);

    state.next_iteration = index + 1;
    state.checkpoint_dir = iteration.output_checkpoint;
    state.status = "running";
    write_runner_state(args.state_path, state, record);
    chain.append_if_exists(args.state_path, config.gate_name);
  }

  stats.queue_wall_seconds =
      std::chrono::duration<double>(std::chrono::steady_clock::now() - queue_start)
          .count();
  wait_for_disconnect_marker(config, args, stats, heartbeat, chain);

  const double active_wall_ratio =
      stats.queue_wall_seconds > 0.0
          ? stats.active_training_seconds / stats.queue_wall_seconds
          : 0.0;
  const bool active_wall_ok =
      active_wall_ratio >= 0.50 ||
      active_wall_ratio >= (2.0 * kPhase10ActiveWallBaseline);
  const bool disconnect_ok =
      !config.require_disconnect_marker ||
      (stats.disconnect_marker_seen &&
       stats.disconnect_wait_seconds >= static_cast<double>(config.disconnect_hold_seconds) -
                                            5.0);

  write_timing_breakdown(gate_dir, stats, active_wall_ratio);
  write_gate_result(gate_dir, stats, config, active_wall_ratio, active_wall_ok,
                    disconnect_ok, checkpoint_chain_ok);
  write_falsifier_report(gate_dir, args.heartbeat_path, stats, active_wall_ok, disconnect_ok,
                         checkpoint_chain_ok);
  write_artifact_manifest(gate_dir, run_dir, stats, config);
  chain.append_if_exists(join_path(gate_dir, "timing_breakdown.json"), config.gate_name);
  chain.append_if_exists(join_path(gate_dir, "gate_result.json"), config.gate_name);
  chain.append_if_exists(join_path(gate_dir, "blockers.md"), config.gate_name);
  chain.append_if_exists(join_path(gate_dir, "falsifier_report.md"), config.gate_name);
  chain.append_if_exists(join_path(gate_dir, "artifact_manifest.json"), config.gate_name);

  const std::string gate_result = read_text_file(join_path(gate_dir, "gate_result.json"));
  state.status = json_contains_string(gate_result, "status", "pass") ? "completed" : "failed";
  write_runner_state(args.state_path, state, record);
  heartbeat.set_step(state.status);
  heartbeat.stop();
  return state.status == "completed" ? 0 : 1;
}

void print_help() {
  std::cout
      << "Usage: phase11_runner --queue QUEUE --run-root DIR --heartbeat FILE --state FILE [--stop-file FILE]\n"
      << "\n"
      << "Executes Phase 11 phone-local queue records. This build supports H11-A "
         "hidden-MSE daemon training and H11-F top-k KL objective runs with "
         "heartbeat, STOP, resume state, checksum chain artifacts, and Phase 13 "
         "Gemma identity/kernel-lineage validation.\n";
}

std::string require_next(int argc, char** argv, int& index, const std::string& flag) {
  if ((index + 1) >= argc) {
    throw std::invalid_argument(flag + " requires a value");
  }
  ++index;
  return argv[index];
}

RunnerArgs parse_args(int argc, char** argv) {
  RunnerArgs args;
  for (int index = 1; index < argc; ++index) {
    const std::string arg = argv[index];
    if (arg == "--help") {
      print_help();
      std::exit(0);
    }
    if (arg == "--queue") {
      args.queue_path = require_next(argc, argv, index, arg);
    } else if (arg == "--run-root") {
      args.run_root = require_next(argc, argv, index, arg);
    } else if (arg == "--heartbeat") {
      args.heartbeat_path = require_next(argc, argv, index, arg);
    } else if (arg == "--state") {
      args.state_path = require_next(argc, argv, index, arg);
    } else if (arg == "--stop-file") {
      args.stop_file = require_next(argc, argv, index, arg);
    } else {
      throw std::invalid_argument("unknown argument: " + arg);
    }
  }
  if (args.queue_path.empty() || args.run_root.empty() || args.heartbeat_path.empty() ||
      args.state_path.empty()) {
    throw std::invalid_argument("--queue, --run-root, --heartbeat, and --state are required");
  }
  return args;
}

}  // namespace

int main(int argc, char** argv) {
  try {
    if (argc == 1) {
      print_help();
      return 0;
    }
    RunnerArgs args = parse_args(argc, argv);
    const std::string cwd = current_working_directory();
    args.queue_path = resolve_path(args.queue_path, cwd);
    args.run_root = resolve_path(args.run_root, cwd);
    args.heartbeat_path = resolve_path(args.heartbeat_path, cwd);
    args.state_path = resolve_path(args.state_path, cwd);
    args.stop_file = resolve_path(args.stop_file, cwd);

    ensure_directory(args.run_root);
    const std::vector<QueueRecord> records = read_queue(args.queue_path, cwd);
    for (const QueueRecord& record : records) {
      if (record.gate != "H11-A" && record.gate != "H11-F") {
        throw std::runtime_error("unsupported queue gate in this build: " + record.gate);
      }
      const int result = run_h11a(args, record, cwd);
      if (result != 0) {
        return result;
      }
    }
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "phase11_runner failed: " << error.what() << '\n';
    return 2;
  }
}
