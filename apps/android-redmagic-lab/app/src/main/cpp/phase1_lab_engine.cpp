#include "phase1_lab_engine.h"

#include <algorithm>
#include <atomic>
#include <cerrno>
#include <chrono>
#include <cstring>
#include <dirent.h>
#include <fcntl.h>
#include <fstream>
#include <limits>
#include <pthread.h>
#include <sched.h>
#include <sstream>
#include <string>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <thread>
#include <unordered_set>
#include <unistd.h>
#include <vector>

struct phase1_engine {
    std::string app_files_dir;
};

extern "C" int phase1_qa_stream_main(int argc, char** argv);

namespace {
constexpr int kOk = 0;
constexpr int kInvalidArgument = 1;
constexpr int kNotConnected = 2;
constexpr int kThreadLaunchFailed = 125;
constexpr int kChildExecFailed = 126;
constexpr std::size_t kPhase1EntryStackBytes = 64U * 1024U * 1024U;
constexpr std::uint32_t kTokenizerVocabSize = 262144U;

void copy_message(char* destination, size_t destination_size, const char* message) {
    if (destination == nullptr || destination_size == 0) {
        return;
    }
    std::strncpy(destination, message, destination_size - 1);
    destination[destination_size - 1] = '\0';
}

bool present(const char* value) {
    return value != nullptr && value[0] != '\0';
}

std::string trim_copy(std::string value) {
    while (!value.empty() && (value.back() == '\n' || value.back() == '\r' || value.back() == '\t' || value.back() == ' ')) {
        value.pop_back();
    }
    std::size_t start = 0;
    while (start < value.size() && (value[start] == '\n' || value[start] == '\r' || value[start] == '\t' || value[start] == ' ')) {
        ++start;
    }
    return value.substr(start);
}

std::string read_text_file(const char* path) {
    std::ifstream stream(path);
    if (!stream) {
        return {};
    }
    std::ostringstream buffer;
    buffer << stream.rdbuf();
    return trim_copy(buffer.str());
}

std::uint64_t read_u64_text_file(const std::string& path) {
    std::ifstream stream(path);
    std::uint64_t value = 0;
    stream >> value;
    return stream ? value : 0;
}

std::string json_escape(const std::string& value) {
    std::ostringstream escaped;
    for (char character : value) {
        switch (character) {
            case '\\':
                escaped << "\\\\";
                break;
            case '"':
                escaped << "\\\"";
                break;
            case '\n':
                escaped << "\\n";
                break;
            case '\r':
                escaped << "\\r";
                break;
            case '\t':
                escaped << "\\t";
                break;
            default:
                escaped << character;
                break;
        }
    }
    return escaped.str();
}

std::string join_path(const std::string& base, const std::string& leaf) {
    if (base.empty() || base.back() == '/') {
        return base + leaf;
    }
    return base + "/" + leaf;
}

bool copy_file_contents(const std::string& source, const std::string& destination) {
    std::ifstream input(source, std::ios::binary);
    if (!input) {
        return false;
    }
    std::ofstream output(destination, std::ios::binary);
    if (!output) {
        return false;
    }
    output << input.rdbuf();
    return static_cast<bool>(output);
}

std::uint64_t file_size(const char* path) {
    struct stat status {};
    if (!present(path) || stat(path, &status) != 0 || status.st_size < 0) {
        return 0;
    }
    return static_cast<std::uint64_t>(status.st_size);
}

std::uint64_t peak_rss_kb() {
    struct rusage usage {};
    if (getrusage(RUSAGE_SELF, &usage) != 0 || usage.ru_maxrss < 0) {
        return 0;
    }
    return static_cast<std::uint64_t>(usage.ru_maxrss);
}

bool read_exact(std::ifstream& stream, char* buffer, std::size_t count) {
    stream.read(buffer, static_cast<std::streamsize>(count));
    return stream.good();
}

std::uint16_t read_u16_le(std::ifstream& stream, bool& ok) {
    char bytes[2] {};
    ok = ok && read_exact(stream, bytes, sizeof(bytes));
    return static_cast<std::uint16_t>(
        (static_cast<unsigned char>(bytes[0])) |
        (static_cast<unsigned char>(bytes[1]) << 8U)
    );
}

std::uint32_t read_u32_le(std::ifstream& stream, bool& ok) {
    char bytes[4] {};
    ok = ok && read_exact(stream, bytes, sizeof(bytes));
    return static_cast<std::uint32_t>(
        (static_cast<unsigned char>(bytes[0])) |
        (static_cast<unsigned char>(bytes[1]) << 8U) |
        (static_cast<unsigned char>(bytes[2]) << 16U) |
        (static_cast<unsigned char>(bytes[3]) << 24U)
    );
}

std::uint64_t read_u64_le(std::ifstream& stream, bool& ok) {
    char bytes[8] {};
    ok = ok && read_exact(stream, bytes, sizeof(bytes));
    std::uint64_t value = 0;
    for (int index = 0; index < 8; ++index) {
        value |= static_cast<std::uint64_t>(static_cast<unsigned char>(bytes[index])) << (index * 8);
    }
    return value;
}

struct Pqa1Summary {
    bool ok = false;
    std::uint64_t records = 0;
    std::uint64_t token_ids = 0;
    std::uint64_t distinct_token_ids = 0;
    std::uint32_t vocab_size = kTokenizerVocabSize;
    std::uint64_t bytes = 0;
    std::uint32_t max_token_id = 0;
    double vocab_coverage_ratio = 0.0;
    double tokens_per_record_mean = 0.0;
    double tokens_per_record_p50 = 0.0;
    double tokens_per_record_p95 = 0.0;
    double tokens_per_record_p99 = 0.0;
    std::vector<std::uint32_t> tokens_per_record;
    std::unordered_set<std::uint32_t> distinct_tokens;
    std::string error;
};

double percentile_u32(std::vector<std::uint32_t> values, double fraction) {
    if (values.empty()) {
        return 0.0;
    }
    std::sort(values.begin(), values.end());
    const double scaled = static_cast<double>(values.size() - 1U) * fraction;
    const std::size_t index = static_cast<std::size_t>(std::max(0.0, std::min(static_cast<double>(values.size() - 1U), scaled + 0.5)));
    return static_cast<double>(values[index]);
}

void finalize_pqa1_summary(Pqa1Summary& summary) {
    summary.distinct_token_ids = static_cast<std::uint64_t>(summary.distinct_tokens.size());
    summary.vocab_size = kTokenizerVocabSize;
    summary.vocab_coverage_ratio = summary.vocab_size > 0
        ? static_cast<double>(summary.distinct_token_ids) / static_cast<double>(summary.vocab_size)
        : 0.0;
    if (summary.tokens_per_record.empty()) {
        return;
    }
    summary.tokens_per_record_mean = static_cast<double>(summary.token_ids) / static_cast<double>(summary.tokens_per_record.size());
    summary.tokens_per_record_p50 = percentile_u32(summary.tokens_per_record, 0.50);
    summary.tokens_per_record_p95 = percentile_u32(summary.tokens_per_record, 0.95);
    summary.tokens_per_record_p99 = percentile_u32(summary.tokens_per_record, 0.99);
}

Pqa1Summary parse_pqa1(const char* path) {
    Pqa1Summary summary {};
    std::ifstream stream(path, std::ios::binary);
    if (!stream) {
        summary.error = "unable to open PQA1 output";
        return summary;
    }
    bool ok = true;
    char magic[4] {};
    ok = read_exact(stream, magic, sizeof(magic));
    if (!ok || std::memcmp(magic, "PQA1", 4) != 0) {
        summary.error = "PQA1 magic mismatch";
        return summary;
    }
    const std::uint16_t version = read_u16_le(stream, ok);
    const std::uint16_t endian = read_u16_le(stream, ok);
    const std::uint64_t records = read_u64_le(stream, ok);
    char hashes[128] {};
    ok = ok && read_exact(stream, hashes, sizeof(hashes));
    if (!ok || version != 1 || endian != 1) {
        summary.error = "PQA1 header mismatch";
        return summary;
    }

    std::uint64_t token_ids = 0;
    summary.tokens_per_record.reserve(static_cast<std::size_t>(std::min<std::uint64_t>(records, 1'000'000ULL)));
    for (std::uint64_t record = 0; record < records; ++record) {
        (void)read_u64_le(stream, ok);
        char kind = 0;
        ok = ok && read_exact(stream, &kind, 1);
        const std::uint32_t token_count = read_u32_le(stream, ok);
        const std::uint16_t segment_count = read_u16_le(stream, ok);
        if (!ok) {
            summary.error = "truncated PQA1 record header";
            return summary;
        }
        summary.tokens_per_record.push_back(token_count);
        for (std::uint32_t index = 0; index < token_count; ++index) {
            const std::uint32_t token_id = read_u32_le(stream, ok);
            if (!ok) {
                summary.error = "truncated PQA1 token ids";
                return summary;
            }
            summary.distinct_tokens.insert(token_id);
            summary.max_token_id = std::max(summary.max_token_id, token_id);
        }
        stream.seekg(static_cast<std::streamoff>(static_cast<std::uint64_t>(segment_count) * 18U), std::ios::cur);
        if (!stream.good()) {
            summary.error = "truncated PQA1 record body";
            return summary;
        }
        token_ids += token_count;
    }

    summary.ok = true;
    summary.records = records;
    summary.token_ids = token_ids;
    summary.bytes = file_size(path);
    finalize_pqa1_summary(summary);
    return summary;
}

struct BatchJobPaths {
    std::string input_path;
    std::string pqa1_output_path;
    std::string writer_metrics_path;
    std::string bpe_metrics_path;
};

struct MemorySnapshot {
    std::uint64_t pss_kb = 0;
    std::uint64_t rss_kb = 0;
};

struct SchedulerSnapshot {
    std::string cpuset;
    std::string cpus_allowed_list;
    std::string mems_allowed_list;
    std::string cgroup;
    std::string sched_excerpt;
    int scheduler_policy = -1;
    int nice_value = 0;
};

struct CpuFrequencyStat {
    int cpu = 0;
    std::uint64_t samples = 0;
    std::uint64_t min_khz = std::numeric_limits<std::uint64_t>::max();
    std::uint64_t max_khz = 0;
    std::uint64_t sum_khz = 0;
    std::uint64_t first_khz = 0;
    std::uint64_t last_khz = 0;
};

struct RuntimeSamplerSnapshot {
    bool enabled = false;
    std::uint64_t sample_count = 0;
    std::uint64_t duration_ns = 0;
    int sample_interval_ms = 5;
    int min_thread_count = 0;
    int max_thread_count = 0;
    std::vector<CpuFrequencyStat> cpu_frequency_stats;
};

struct WarmSequenceRun {
    std::string label;
    int return_code = 0;
    double wall_sec = 0.0;
    std::string batch_metrics_copy_path;
};

struct Phase1Invocation {
    int argc = 0;
    char** argv = nullptr;
    int return_code = kThreadLaunchFailed;
};

struct ChildExecResult {
    int return_code = kChildExecFailed;
    int exec_errno = 0;
};

int count_process_threads() {
    DIR* directory = opendir("/proc/self/task");
    if (directory == nullptr) {
        return 0;
    }
    int count = 0;
    while (const dirent* entry = readdir(directory)) {
        if (entry->d_name[0] >= '0' && entry->d_name[0] <= '9') {
            ++count;
        }
    }
    closedir(directory);
    return count;
}

std::vector<int> discover_online_cpu_ids() {
    std::vector<int> cpu_ids;
    for (int cpu = 0; cpu < 32; ++cpu) {
        const std::string path = "/sys/devices/system/cpu/cpu" + std::to_string(cpu) + "/cpufreq/scaling_cur_freq";
        std::ifstream stream(path);
        if (stream) {
            cpu_ids.push_back(cpu);
        }
    }
    return cpu_ids;
}

void record_cpu_frequency(CpuFrequencyStat& stat, std::uint64_t khz) {
    if (khz == 0) {
        return;
    }
    if (stat.samples == 0) {
        stat.first_khz = khz;
    }
    stat.last_khz = khz;
    stat.min_khz = std::min(stat.min_khz, khz);
    stat.max_khz = std::max(stat.max_khz, khz);
    stat.sum_khz += khz;
    ++stat.samples;
}

RuntimeSamplerSnapshot sample_runtime_until_stopped(std::atomic<bool>& stop) {
    constexpr int kSampleIntervalMs = 5;
    RuntimeSamplerSnapshot snapshot {};
    snapshot.enabled = true;
    snapshot.sample_interval_ms = kSampleIntervalMs;
    const std::vector<int> cpu_ids = discover_online_cpu_ids();
    snapshot.cpu_frequency_stats.reserve(cpu_ids.size());
    for (int cpu : cpu_ids) {
        CpuFrequencyStat stat {};
        stat.cpu = cpu;
        snapshot.cpu_frequency_stats.push_back(stat);
    }

    const auto started = std::chrono::steady_clock::now();
    while (!stop.load(std::memory_order_acquire)) {
        const int thread_count = count_process_threads();
        if (thread_count > 0) {
            if (snapshot.min_thread_count == 0 || thread_count < snapshot.min_thread_count) {
                snapshot.min_thread_count = thread_count;
            }
            snapshot.max_thread_count = std::max(snapshot.max_thread_count, thread_count);
        }
        for (CpuFrequencyStat& stat : snapshot.cpu_frequency_stats) {
            const std::string path = "/sys/devices/system/cpu/cpu" + std::to_string(stat.cpu) + "/cpufreq/scaling_cur_freq";
            record_cpu_frequency(stat, read_u64_text_file(path));
        }
        ++snapshot.sample_count;
        std::this_thread::sleep_for(std::chrono::milliseconds(kSampleIntervalMs));
    }
    const auto finished = std::chrono::steady_clock::now();
    snapshot.duration_ns = static_cast<std::uint64_t>(
        std::chrono::duration_cast<std::chrono::nanoseconds>(finished - started).count()
    );
    return snapshot;
}

void* phase1_entry_thread(void* opaque) {
    auto* invocation = static_cast<Phase1Invocation*>(opaque);
    invocation->return_code = phase1_qa_stream_main(invocation->argc, invocation->argv);
    return nullptr;
}

int run_phase1_entry_on_large_stack(int argc, char** argv) {
    pthread_attr_t attributes {};
    if (pthread_attr_init(&attributes) != 0) {
        return kThreadLaunchFailed;
    }
    (void)pthread_attr_setstacksize(&attributes, kPhase1EntryStackBytes);

    Phase1Invocation invocation {};
    invocation.argc = argc;
    invocation.argv = argv;

    pthread_t thread {};
    const int create_result = pthread_create(&thread, &attributes, phase1_entry_thread, &invocation);
    pthread_attr_destroy(&attributes);
    if (create_result != 0) {
        return kThreadLaunchFailed;
    }
    if (pthread_join(thread, nullptr) != 0) {
        return kThreadLaunchFailed;
    }
    return invocation.return_code;
}

int prepare_child_exec_binary(
    const phase1_engine_t* engine,
    const phase1_run_config_t* config,
    std::string& executable_path,
    std::string& error_message
) {
    (void)engine;
    if (!present(config->phase1_exec_path)) {
        error_message = "CHILD_EXEC flag requires phase1_exec_path.";
        return kInvalidArgument;
    }
    executable_path = config->phase1_exec_path;
    if (access(executable_path.c_str(), X_OK) != 0) {
        error_message = "phase1_exec_path is not executable by the APK process.";
        return kChildExecFailed;
    }
    return kOk;
}

ChildExecResult run_phase1_child_process(const std::string& executable_path, const std::vector<char*>& argv) {
    ChildExecResult result {};
    if (executable_path.empty() || argv.empty()) {
        result.return_code = kInvalidArgument;
        return result;
    }
    std::vector<char*> child_argv;
    child_argv.reserve(argv.size() + 1);
    child_argv.push_back(const_cast<char*>(executable_path.c_str()));
    for (std::size_t index = 1; index < argv.size(); ++index) {
        child_argv.push_back(argv[index]);
    }
    child_argv.push_back(nullptr);

    int exec_errno_pipe[2] = {-1, -1};
    if (pipe(exec_errno_pipe) != 0) {
        result.return_code = kChildExecFailed;
        result.exec_errno = errno;
        return result;
    }
    (void)fcntl(exec_errno_pipe[1], F_SETFD, FD_CLOEXEC);

    const pid_t pid = fork();
    if (pid < 0) {
        result.return_code = kChildExecFailed;
        result.exec_errno = errno;
        close(exec_errno_pipe[0]);
        close(exec_errno_pipe[1]);
        return result;
    }
    if (pid == 0) {
        close(exec_errno_pipe[0]);
        execv(executable_path.c_str(), child_argv.data());
        const int exec_error = errno;
        (void)write(exec_errno_pipe[1], &exec_error, sizeof(exec_error));
        _exit(127);
    }

    close(exec_errno_pipe[1]);
    int exec_error = 0;
    const ssize_t bytes_read = read(exec_errno_pipe[0], &exec_error, sizeof(exec_error));
    close(exec_errno_pipe[0]);
    if (bytes_read == sizeof(exec_error)) {
        result.exec_errno = exec_error;
    }

    int status = 0;
    pid_t waited = -1;
    do {
        waited = waitpid(pid, &status, 0);
    } while (waited < 0 && errno == EINTR);

    if (waited < 0) {
        result.return_code = kChildExecFailed;
        result.exec_errno = errno;
        return result;
    }
    if (WIFEXITED(status)) {
        result.return_code = WEXITSTATUS(status);
        return result;
    }
    if (WIFSIGNALED(status)) {
        result.return_code = 128 + WTERMSIG(status);
        return result;
    }
    result.return_code = kChildExecFailed;
    return result;
}

void normalize_report_file_permissions(const std::string& path) {
    if (!path.empty()) {
        (void)chmod(path.c_str(), S_IRUSR | S_IWUSR | S_IRGRP | S_IWGRP);
    }
}

void normalize_batch_report_permissions(const std::vector<BatchJobPaths>& jobs) {
    for (const BatchJobPaths& job : jobs) {
        normalize_report_file_permissions(job.writer_metrics_path);
        normalize_report_file_permissions(job.bpe_metrics_path);
    }
}

std::vector<std::string> split_tab_line(const std::string& line) {
    std::vector<std::string> fields;
    std::size_t start = 0;
    while (start <= line.size()) {
        const std::size_t end = line.find('\t', start);
        if (end == std::string::npos) {
            fields.push_back(line.substr(start));
            break;
        }
        fields.push_back(line.substr(start, end - start));
        start = end + 1;
    }
    return fields;
}

std::vector<BatchJobPaths> read_batch_list(const char* path) {
    std::vector<BatchJobPaths> jobs;
    if (!present(path)) {
        return jobs;
    }
    std::ifstream stream(path);
    std::string line;
    while (std::getline(stream, line)) {
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }
        if (line.empty()) {
            continue;
        }
        const std::vector<std::string> fields = split_tab_line(line);
        if (fields.size() < 2) {
            continue;
        }
        jobs.push_back(BatchJobPaths{
            fields[0],
            fields[1],
            fields.size() > 2 ? fields[2] : std::string(),
            fields.size() > 3 ? fields[3] : std::string()
        });
    }
    return jobs;
}

Pqa1Summary summarize_batch_outputs(const std::vector<BatchJobPaths>& jobs) {
    Pqa1Summary total {};
    if (jobs.empty()) {
        total.error = "empty or unreadable batch list";
        return total;
    }
    for (const BatchJobPaths& job : jobs) {
        const Pqa1Summary part = parse_pqa1(job.pqa1_output_path.c_str());
        if (!part.ok) {
            total.error = "batch PQA1 parse failed: " + job.pqa1_output_path + ": " + part.error;
            return total;
        }
        total.records += part.records;
        total.token_ids += part.token_ids;
        total.bytes += part.bytes;
        total.max_token_id = std::max(total.max_token_id, part.max_token_id);
        total.tokens_per_record.insert(total.tokens_per_record.end(), part.tokens_per_record.begin(), part.tokens_per_record.end());
        total.distinct_tokens.insert(part.distinct_tokens.begin(), part.distinct_tokens.end());
    }
    total.ok = true;
    finalize_pqa1_summary(total);
    return total;
}

std::uint64_t batch_input_bytes(const std::vector<BatchJobPaths>& jobs) {
    std::uint64_t total = 0;
    for (const BatchJobPaths& job : jobs) {
        total += file_size(job.input_path.c_str());
    }
    return total;
}

std::uint64_t parse_kb_line(const std::string& line, const char* prefix) {
    if (line.rfind(prefix, 0) != 0) {
        return 0;
    }
    std::istringstream values(line.substr(std::strlen(prefix)));
    std::uint64_t kb = 0;
    values >> kb;
    return kb;
}

MemorySnapshot read_process_memory_snapshot() {
    MemorySnapshot snapshot {};
    std::ifstream rollup("/proc/self/smaps_rollup");
    std::string line;
    while (std::getline(rollup, line)) {
        if (snapshot.pss_kb == 0) {
            snapshot.pss_kb = parse_kb_line(line, "Pss:");
        }
        if (snapshot.rss_kb == 0) {
            snapshot.rss_kb = parse_kb_line(line, "Rss:");
        }
    }
    if (snapshot.rss_kb != 0) {
        return snapshot;
    }
    std::ifstream status("/proc/self/status");
    while (std::getline(status, line)) {
        snapshot.rss_kb = parse_kb_line(line, "VmRSS:");
        if (snapshot.rss_kb != 0) {
            break;
        }
    }
    return snapshot;
}

std::string status_value(const std::string& line, const char* key) {
    const std::string prefix = std::string(key) + ":";
    if (line.rfind(prefix, 0) != 0) {
        return {};
    }
    return trim_copy(line.substr(prefix.size()));
}

SchedulerSnapshot read_scheduler_snapshot() {
    SchedulerSnapshot snapshot {};
    snapshot.cpuset = read_text_file("/proc/self/cpuset");
    snapshot.cgroup = read_text_file("/proc/self/cgroup");
    snapshot.scheduler_policy = sched_getscheduler(0);
    snapshot.nice_value = getpriority(PRIO_PROCESS, 0);
    std::ifstream status("/proc/self/status");
    std::string line;
    while (std::getline(status, line)) {
        if (snapshot.cpus_allowed_list.empty()) {
            snapshot.cpus_allowed_list = status_value(line, "Cpus_allowed_list");
        }
        if (snapshot.mems_allowed_list.empty()) {
            snapshot.mems_allowed_list = status_value(line, "Mems_allowed_list");
        }
    }
    std::ifstream sched("/proc/self/sched");
    std::ostringstream sched_excerpt;
    while (std::getline(sched, line)) {
        if (
            line.find("uclamp") != std::string::npos ||
            line.find("policy") != std::string::npos ||
            line.find("prio") != std::string::npos
        ) {
            sched_excerpt << trim_copy(line) << '\n';
        }
    }
    snapshot.sched_excerpt = trim_copy(sched_excerpt.str());
    return snapshot;
}

void write_cpu_frequency_sampler_json(std::ofstream& report, const RuntimeSamplerSnapshot& sampler) {
    report << "  \"cpu_frequency_sampler\": {\n";
    report << "    \"schema_version\": \"cpu_frequency_sampler_v1\",\n";
    report << "    \"enabled\": " << (sampler.enabled ? "true" : "false") << ",\n";
    report << "    \"sample_interval_ms\": " << sampler.sample_interval_ms << ",\n";
    report << "    \"sample_count\": " << sampler.sample_count << ",\n";
    report << "    \"duration_sec\": " << (static_cast<double>(sampler.duration_ns) / 1000000000.0) << ",\n";
    report << "    \"min_thread_count\": " << sampler.min_thread_count << ",\n";
    report << "    \"max_thread_count\": " << sampler.max_thread_count << ",\n";
    report << "    \"cpus\": [\n";
    for (std::size_t index = 0; index < sampler.cpu_frequency_stats.size(); ++index) {
        const CpuFrequencyStat& stat = sampler.cpu_frequency_stats[index];
        const std::uint64_t min_khz = stat.samples > 0 ? stat.min_khz : 0;
        const double avg_khz = stat.samples > 0
            ? static_cast<double>(stat.sum_khz) / static_cast<double>(stat.samples)
            : 0.0;
        report << "      {"
               << "\"cpu\": " << stat.cpu
               << ", \"samples\": " << stat.samples
               << ", \"min_khz\": " << min_khz
               << ", \"max_khz\": " << stat.max_khz
               << ", \"avg_khz\": " << avg_khz
               << ", \"first_khz\": " << stat.first_khz
               << ", \"last_khz\": " << stat.last_khz
               << "}";
        if (index + 1 != sampler.cpu_frequency_stats.size()) {
            report << ",";
        }
        report << "\n";
    }
    report << "    ]\n";
    report << "  },\n";
}

void write_warm_sequence_report(
    const phase1_run_config_t* config,
    const std::vector<WarmSequenceRun>& runs
) {
    if (!present(config->report_output_path) || runs.empty()) {
        return;
    }
    const std::string path = join_path(config->report_output_path, "native_warm_sequence_metrics.json");
    std::ofstream report(path);
    if (!report) {
        return;
    }
    report << "{\n";
    report << "  \"schema_version\": \"phase1_native_warm_sequence_metrics_v1\",\n";
    report << "  \"sequence\": \"warmup_then_back_to_back_trials\",\n";
    report << "  \"run_count\": " << runs.size() << ",\n";
    report << "  \"runs\": [\n";
    for (std::size_t index = 0; index < runs.size(); ++index) {
        const WarmSequenceRun& run = runs[index];
        report << "    {"
               << "\"label\": \"" << json_escape(run.label) << "\""
               << ", \"return_code\": " << run.return_code
               << ", \"wall_sec\": " << run.wall_sec
               << ", \"batch_metrics_copy_path\": \"" << json_escape(run.batch_metrics_copy_path) << "\""
               << "}";
        if (index + 1 != runs.size()) {
            report << ",";
        }
        report << "\n";
    }
    report << "  ],\n";
    report << "  \"nonclaims\": [\"diagnostic_sequence_not_promotion\", \"canonical_phase1_main_called_without_tokenizer_substitution\"]\n";
    report << "}\n";
}

void write_native_metrics_report(
    const phase1_run_config_t* config,
    const Pqa1Summary& summary,
    int return_code,
    double wall_sec,
    std::uint64_t input_bytes,
    std::uint64_t output_bytes,
    const MemorySnapshot& memory,
    const SchedulerSnapshot& scheduler_before,
    const SchedulerSnapshot& scheduler_after,
    const RuntimeSamplerSnapshot& runtime_sampler,
    bool native_warm_sequence_enabled,
    bool native_extended_warm_sequence_enabled,
    bool direct_entry_enabled,
    bool child_exec_enabled,
    int child_exec_errno,
    std::uint64_t job_count,
    const char* bpe_algorithm,
    bool batch_mode
) {
    if (!present(config->report_output_path)) {
        return;
    }
    const std::string path = join_path(config->report_output_path, "native_phase1_metrics.json");
    std::ofstream report(path);
    if (!report) {
        return;
    }
    const double input_mb = static_cast<double>(input_bytes) / (1024.0 * 1024.0);
    const double mb_per_sec = wall_sec > 0.0 ? input_mb / wall_sec : 0.0;
    const double token_ids_per_sec = wall_sec > 0.0 ? static_cast<double>(summary.token_ids) / wall_sec : 0.0;
    const double records_per_sec = wall_sec > 0.0 ? static_cast<double>(summary.records) / wall_sec : 0.0;
    const double latency_ms_per_record = summary.records > 0
        ? (wall_sec * 1000.0) / static_cast<double>(summary.records)
        : 0.0;
    const std::uint64_t rss_kb = peak_rss_kb();
    report << "{\n";
    report << "  \"schema_version\": \"phase1_android_native_metrics_v1\",\n";
    report << "  \"engine_name\": \"phase1_qa_stream_zig_shared_object\",\n";
    report << "  \"connection_state\": \"CONNECTED\",\n";
    report << "  \"return_code\": " << return_code << ",\n";
    report << "  \"status\": \"" << (return_code == 0 && summary.ok ? "probe" : "fail") << "\",\n";
    report << "  \"records\": " << summary.records << ",\n";
    report << "  \"token_ids\": " << summary.token_ids << ",\n";
    report << "  \"distinct_token_ids\": " << summary.distinct_token_ids << ",\n";
    report << "  \"vocab_size\": " << summary.vocab_size << ",\n";
    report << "  \"vocab_coverage_ratio\": " << summary.vocab_coverage_ratio << ",\n";
    report << "  \"tokens_per_record_mean\": " << summary.tokens_per_record_mean << ",\n";
    report << "  \"tokens_per_record_p50\": " << summary.tokens_per_record_p50 << ",\n";
    report << "  \"tokens_per_record_p95\": " << summary.tokens_per_record_p95 << ",\n";
    report << "  \"tokens_per_record_p99\": " << summary.tokens_per_record_p99 << ",\n";
    report << "  \"tokens_per_record_distribution_source\": \"pqa1_record_headers\",\n";
    report << "  \"max_token_id\": " << summary.max_token_id << ",\n";
    report << "  \"wall_sec\": " << wall_sec << ",\n";
    report << "  \"input_bytes\": " << input_bytes << ",\n";
    report << "  \"output_bytes\": " << output_bytes << ",\n";
    report << "  \"input_mb_per_sec\": " << mb_per_sec << ",\n";
    report << "  \"token_ids_per_sec\": " << token_ids_per_sec << ",\n";
    report << "  \"records_per_sec\": " << records_per_sec << ",\n";
    report << "  \"latency_ms_per_record\": " << latency_ms_per_record << ",\n";
    report << "  \"latency_ms_per_prompt\": " << latency_ms_per_record << ",\n";
    report << "  \"pss_kb\": " << memory.pss_kb << ",\n";
    report << "  \"rss_kb\": " << memory.rss_kb << ",\n";
    report << "  \"peak_rss_kb\": " << rss_kb << ",\n";
    report << "  \"cpuset_before\": \"" << json_escape(scheduler_before.cpuset) << "\",\n";
    report << "  \"cpuset_after\": \"" << json_escape(scheduler_after.cpuset) << "\",\n";
    report << "  \"cpus_allowed_list_before\": \"" << json_escape(scheduler_before.cpus_allowed_list) << "\",\n";
    report << "  \"cpus_allowed_list_after\": \"" << json_escape(scheduler_after.cpus_allowed_list) << "\",\n";
    report << "  \"mems_allowed_list_before\": \"" << json_escape(scheduler_before.mems_allowed_list) << "\",\n";
    report << "  \"mems_allowed_list_after\": \"" << json_escape(scheduler_after.mems_allowed_list) << "\",\n";
    report << "  \"cgroup_before\": \"" << json_escape(scheduler_before.cgroup) << "\",\n";
    report << "  \"cgroup_after\": \"" << json_escape(scheduler_after.cgroup) << "\",\n";
    report << "  \"sched_policy_before\": " << scheduler_before.scheduler_policy << ",\n";
    report << "  \"sched_policy_after\": " << scheduler_after.scheduler_policy << ",\n";
    report << "  \"nice_before\": " << scheduler_before.nice_value << ",\n";
    report << "  \"nice_after\": " << scheduler_after.nice_value << ",\n";
    report << "  \"sched_excerpt_before\": \"" << json_escape(scheduler_before.sched_excerpt) << "\",\n";
    report << "  \"sched_excerpt_after\": \"" << json_escape(scheduler_after.sched_excerpt) << "\",\n";
    report << "  \"native_warm_sequence_enabled\": " << (native_warm_sequence_enabled ? "true" : "false") << ",\n";
    report << "  \"native_extended_warm_sequence_enabled\": " << (native_extended_warm_sequence_enabled ? "true" : "false") << ",\n";
    report << "  \"direct_entry_enabled\": " << (direct_entry_enabled ? "true" : "false") << ",\n";
    report << "  \"child_exec_enabled\": " << (child_exec_enabled ? "true" : "false") << ",\n";
    report << "  \"child_exec_errno\": " << child_exec_errno << ",\n";
    report << "  \"child_exec_errno_message\": \"" << json_escape(child_exec_errno == 0 ? "" : std::strerror(child_exec_errno)) << "\",\n";
    write_cpu_frequency_sampler_json(report, runtime_sampler);
    report << "  \"job_count\": " << job_count << ",\n";
    report << "  \"thread_count\": " << config->worker_count << ",\n";
    report << "  \"parity_state\": \"not_checked_in_apk_run\",\n";
    report << "  \"bpe_algorithm\": \"" << (present(bpe_algorithm) ? bpe_algorithm : "heap") << "\",\n";
    report << "  \"run_interface\": \"" << (batch_mode ? "batch-list" : "single-input") << "\",\n";
    report << "  \"table_format\": \"" << (present(config->gbt1_path) ? "packed_or_requested" : "tsv") << "\",\n";
    report << "  \"nonclaims\": [\"no_promoted_phase1_pass\", \"no_game_mode_benefit\", \"no_redmagic_benefit\"]\n";
    report << "}\n";
}
}  // namespace

extern "C" int phase1_engine_create(const char* app_files_dir, phase1_engine_t** out) {
    if (app_files_dir == nullptr || out == nullptr) {
        return kInvalidArgument;
    }
    *out = new phase1_engine{std::string(app_files_dir)};
    return kOk;
}

extern "C" int phase1_engine_info(phase1_engine_t* engine, phase1_engine_info_t* out) {
    if (engine == nullptr || out == nullptr) {
        return kInvalidArgument;
    }
    out->abi_version = POLYMATH_PHASE1_ENGINE_ABI_VERSION;
    out->build_id = "android-redmagic-lab-phase1-canonical-export-2026-06-27";
    out->git_sha = "not_embedded";
    out->engine_name = "phase1_qa_stream_zig_shared_object";
    out->connection_state = "PROBE";
    return kOk;
}

extern "C" int phase1_engine_run(
    phase1_engine_t* engine,
    const phase1_run_config_t* config,
    phase1_run_result_t* out
) {
    if (engine == nullptr || out == nullptr) {
        return kInvalidArgument;
    }
    std::memset(out, 0, sizeof(*out));
    if (config == nullptr) {
        copy_message(out->error_message, sizeof(out->error_message), "Missing Phase 1 run config.");
        return kInvalidArgument;
    }
    const bool batch_mode = present(config->batch_list_path);
    if (!batch_mode && (!present(config->qai1_path) || !present(config->pqa1_output_path))) {
        copy_message(out->error_message, sizeof(out->error_message), "Missing QAI1 input or PQA1 output path.");
        return kInvalidArgument;
    }
    if (batch_mode && !present(config->batch_list_path)) {
        copy_message(out->error_message, sizeof(out->error_message), "Missing Phase 1 batch list path.");
        return kInvalidArgument;
    }

    const bool use_packed = present(config->gbt1_path);
    const char* tokenizer_dir = present(config->tokenizer_dir) ? config->tokenizer_dir : engine->app_files_dir.c_str();
    const char* bpe_algorithm = present(config->bpe_algorithm) ? config->bpe_algorithm : "heap";
    const std::string writer_metrics = present(config->report_output_path)
        ? join_path(config->report_output_path, "native_writer_metrics.json")
        : std::string();
    const std::string single_bpe_metrics = present(config->bpe_metrics_output_path)
        ? config->bpe_metrics_output_path
        : (present(config->report_output_path) ? join_path(config->report_output_path, "native_bpe_metrics.json") : std::string());
    const std::string batch_metrics = present(config->batch_metrics_output_path)
        ? config->batch_metrics_output_path
        : (present(config->report_output_path) ? join_path(config->report_output_path, "native_batch_metrics.json") : std::string());
    const std::string worker_count = std::to_string(config->worker_count == 0 ? 1U : config->worker_count);

    std::vector<std::string> args = {
        "phase1_qa_stream",
        "--tokenizer-dir", tokenizer_dir,
        "--vocab-sha256", "0e43bafc96037bed92fabea31282eb10ad094ec921748a58f6be10dbf9796f74",
        "--merges-sha256", "6c99efe1bfe6b70092d531cad0a57278182652a2380aa5fb33e99d4e4eeb905f",
        "--bpe-algorithm", bpe_algorithm
    };
    if (batch_mode) {
        args.emplace_back("--batch-list");
        args.emplace_back(config->batch_list_path);
        args.emplace_back("--batch-workers");
        args.emplace_back(worker_count);
        if (!batch_metrics.empty()) {
            args.emplace_back("--batch-metrics");
            args.emplace_back(batch_metrics);
        }
    } else {
        args.emplace_back("--input");
        args.emplace_back(config->qai1_path);
        args.emplace_back("--input-format");
        args.emplace_back("binary");
        args.emplace_back("--out-bin");
        args.emplace_back(config->pqa1_output_path);
        args.emplace_back("--out-jsonl");
        args.emplace_back("-");
        if (!writer_metrics.empty()) {
            args.emplace_back("--writer-metrics");
            args.emplace_back(writer_metrics);
        }
        if (!single_bpe_metrics.empty()) {
            args.emplace_back("--bpe-metrics");
            args.emplace_back(single_bpe_metrics);
        }
    }
    if (use_packed) {
        args.emplace_back("--table-format");
        args.emplace_back("packed-mmap");
        args.emplace_back("--tokenizer-table");
        args.emplace_back(config->gbt1_path);
    } else {
        args.emplace_back("--table-format");
        args.emplace_back("tsv");
    }

    std::vector<char*> argv;
    argv.reserve(args.size());
    for (std::string& arg : args) {
        argv.push_back(arg.data());
    }

    const SchedulerSnapshot scheduler_before = read_scheduler_snapshot();
    RuntimeSamplerSnapshot runtime_sampler {};
    std::vector<WarmSequenceRun> warm_sequence_runs;
    std::atomic<bool> sampler_stop {false};
    std::thread sampler_thread;
    const bool runtime_sampler_enabled = (config->flags & POLYMATH_PHASE1_RUN_FLAG_RUNTIME_SAMPLER) != 0U;
    const bool native_warm_sequence_enabled = batch_mode && (config->flags & POLYMATH_PHASE1_RUN_FLAG_NATIVE_WARM_SEQUENCE) != 0U;
    const bool native_extended_warm_sequence_enabled = native_warm_sequence_enabled
        && (config->flags & POLYMATH_PHASE1_RUN_FLAG_NATIVE_EXTENDED_WARM_SEQUENCE) != 0U;
    const bool child_exec_enabled = (config->flags & POLYMATH_PHASE1_RUN_FLAG_CHILD_EXEC) != 0U;
    const bool direct_entry_enabled = !child_exec_enabled && (config->flags & POLYMATH_PHASE1_RUN_FLAG_DIRECT_ENTRY) != 0U;
    std::string child_exec_path;
    std::string setup_error_message;
    int setup_rc = kOk;
    if (child_exec_enabled) {
        setup_rc = prepare_child_exec_binary(engine, config, child_exec_path, setup_error_message);
    }
    if (runtime_sampler_enabled) {
        sampler_thread = std::thread([&]() {
            runtime_sampler = sample_runtime_until_stopped(sampler_stop);
        });
    }
    int rc = kOk;
    int child_exec_errno = 0;
    double wall_sec = 0.0;
    const auto run_once = [&](const std::string& label) -> int {
        const auto started = std::chrono::steady_clock::now();
        int run_rc = kOk;
        if (child_exec_enabled) {
            const ChildExecResult child_result = run_phase1_child_process(child_exec_path, argv);
            run_rc = child_result.return_code;
            child_exec_errno = child_result.exec_errno;
        } else if (direct_entry_enabled) {
            run_rc = phase1_qa_stream_main(static_cast<int>(argv.size()), argv.data());
        } else {
            run_rc = run_phase1_entry_on_large_stack(static_cast<int>(argv.size()), argv.data());
        }
        const auto finished = std::chrono::steady_clock::now();
        wall_sec = std::chrono::duration<double>(finished - started).count();
        if (native_warm_sequence_enabled) {
            WarmSequenceRun run {};
            run.label = label;
            run.return_code = run_rc;
            run.wall_sec = wall_sec;
            if (present(config->report_output_path) && !batch_metrics.empty()) {
                run.batch_metrics_copy_path = join_path(config->report_output_path, "native_batch_metrics_" + label + ".json");
                if (copy_file_contents(batch_metrics, run.batch_metrics_copy_path)) {
                    normalize_report_file_permissions(run.batch_metrics_copy_path);
                } else {
                    run.batch_metrics_copy_path.clear();
                }
            }
            warm_sequence_runs.push_back(run);
        }
        return run_rc;
    };
    if (setup_rc != kOk) {
        rc = setup_rc;
    } else if (native_warm_sequence_enabled) {
        const std::vector<std::string> labels = native_extended_warm_sequence_enabled
            ? std::vector<std::string>{
                "warmup1", "warmup2", "warmup3", "warmup4", "warmup5", "warmup6",
                "trial1", "trial2", "trial3", "trial4", "trial5", "trial6", "trial7", "trial8"
            }
            : std::vector<std::string>{"warmup", "trial1", "trial2", "trial3", "trial4", "trial5"};
        for (const std::string& label : labels) {
            rc = run_once(label);
            if (rc != 0) {
                break;
            }
        }
    } else {
        rc = run_once("single");
    }
    if (runtime_sampler_enabled) {
        sampler_stop.store(true, std::memory_order_release);
    }
    if (sampler_thread.joinable()) {
        sampler_thread.join();
    }
    const SchedulerSnapshot scheduler_after = read_scheduler_snapshot();

    const std::vector<BatchJobPaths> batch_jobs = batch_mode ? read_batch_list(config->batch_list_path) : std::vector<BatchJobPaths>{};
    normalize_report_file_permissions(batch_metrics);
    normalize_report_file_permissions(writer_metrics);
    normalize_report_file_permissions(single_bpe_metrics);
    normalize_batch_report_permissions(batch_jobs);
    const Pqa1Summary summary = rc == 0
        ? (batch_mode ? summarize_batch_outputs(batch_jobs) : parse_pqa1(config->pqa1_output_path))
        : Pqa1Summary{};
    const std::uint64_t input_bytes = batch_mode ? batch_input_bytes(batch_jobs) : file_size(config->qai1_path);
    const std::uint64_t output_bytes = batch_mode ? summary.bytes : file_size(config->pqa1_output_path);
    const double input_mb = static_cast<double>(input_bytes) / (1024.0 * 1024.0);
    const double input_mb_per_sec = wall_sec > 0.0 ? input_mb / wall_sec : 0.0;
    const double token_ids_per_sec = wall_sec > 0.0 ? static_cast<double>(summary.token_ids) / wall_sec : 0.0;
    const double records_per_sec = wall_sec > 0.0 ? static_cast<double>(summary.records) / wall_sec : 0.0;
    const double latency_ms_per_record = summary.records > 0
        ? (wall_sec * 1000.0) / static_cast<double>(summary.records)
        : 0.0;
    const MemorySnapshot memory = read_process_memory_snapshot();
    write_warm_sequence_report(config, warm_sequence_runs);
    write_native_metrics_report(
        config,
        summary,
        rc,
        wall_sec,
        input_bytes,
        output_bytes,
        memory,
        scheduler_before,
        scheduler_after,
        runtime_sampler,
        native_warm_sequence_enabled,
        native_extended_warm_sequence_enabled,
        direct_entry_enabled,
        child_exec_enabled,
        child_exec_errno,
        batch_mode ? batch_jobs.size() : 1,
        bpe_algorithm,
        batch_mode
    );

    out->records = summary.records;
    out->token_ids = summary.token_ids;
    out->distinct_token_ids = summary.distinct_token_ids;
    out->vocab_size = summary.vocab_size;
    out->wall_sec = wall_sec;
    out->vocab_coverage_ratio = summary.vocab_coverage_ratio;
    out->tokens_per_record_mean = summary.tokens_per_record_mean;
    out->tokens_per_record_p50 = summary.tokens_per_record_p50;
    out->tokens_per_record_p95 = summary.tokens_per_record_p95;
    out->tokens_per_record_p99 = summary.tokens_per_record_p99;
    out->input_bytes = input_bytes;
    out->output_bytes = output_bytes;
    out->input_mb_per_sec = input_mb_per_sec;
    out->token_ids_per_sec = token_ids_per_sec;
    out->records_per_sec = records_per_sec;
    out->latency_ms_per_record = latency_ms_per_record;
    out->pss_kb = memory.pss_kb;
    out->rss_kb = memory.rss_kb;
    out->peak_rss_kb = peak_rss_kb();
    out->job_count = static_cast<std::uint32_t>(batch_mode ? batch_jobs.size() : 1);
    out->thread_count = config->worker_count == 0 ? 1U : config->worker_count;
    copy_message(out->cpuset_before, sizeof(out->cpuset_before), scheduler_before.cpuset.c_str());
    copy_message(out->cpuset_after, sizeof(out->cpuset_after), scheduler_after.cpuset.c_str());
    copy_message(out->cpus_allowed_list_before, sizeof(out->cpus_allowed_list_before), scheduler_before.cpus_allowed_list.c_str());
    copy_message(out->cpus_allowed_list_after, sizeof(out->cpus_allowed_list_after), scheduler_after.cpus_allowed_list.c_str());

    if (rc != 0 || !summary.ok) {
        const std::string message = rc != 0
            ? (setup_error_message.empty() ? "phase1_qa_stream returned nonzero" : setup_error_message)
            : summary.error;
        copy_message(out->error_message, sizeof(out->error_message), message.c_str());
        return rc != 0 ? rc : kNotConnected;
    }

    out->hot_loop_allocations = 0;
    out->span_errors = 0;
    out->parity_mismatches = 0;
    copy_message(out->material_hash_hex, sizeof(out->material_hash_hex), "");
    copy_message(out->error_message, sizeof(out->error_message), "probe run completed; parity must be checked externally before promotion.");
    return kOk;
}

extern "C" void phase1_engine_destroy(phase1_engine_t* engine) {
    delete engine;
}
