#include <arm_neon.h>
#include <fcntl.h>
#include <openssl/sha.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#include <zlib.h>

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>
#include <vector>
#include <utility>

namespace {

constexpr uint32_t kVocabSize = 262144;
constexpr uint32_t kEmbedDim = 2560;
constexpr uint32_t kJlDim = 256;
constexpr uint32_t kPacketLen = 128;
constexpr uint32_t kPjp1HeaderBytes = 4096;
constexpr uint32_t kPjp1MetaBytes = 192;
constexpr uint32_t kTokenBytes = kPacketLen * 4;
constexpr uint32_t kRoleBytes = kPacketLen;
constexpr uint32_t kPolarBytes = kPacketLen * (kJlDim / 8);
constexpr uint32_t kPooledBytes = kJlDim / 8;
constexpr uint32_t kMaxRecordTokens = 8192;
constexpr uint32_t kMaxSegments = 16;
constexpr uint32_t kTokenProjectionTile = 16;

using Clock = std::chrono::steady_clock;

struct Timer {
  Clock::time_point started = Clock::now();

  double elapsed() const {
    return std::chrono::duration<double>(Clock::now() - started).count();
  }
};

[[noreturn]] void fail(const std::string& message) {
  throw std::runtime_error(message);
}

uint16_t load_u16(const uint8_t* p) {
  return static_cast<uint16_t>(static_cast<uint16_t>(p[0]) | static_cast<uint16_t>(static_cast<uint16_t>(p[1]) << 8));
}

uint32_t load_u32(const uint8_t* p) {
  return static_cast<uint32_t>(p[0]) | (static_cast<uint32_t>(p[1]) << 8) |
         (static_cast<uint32_t>(p[2]) << 16) | (static_cast<uint32_t>(p[3]) << 24);
}

uint64_t load_u64(const uint8_t* p) {
  uint64_t out = 0;
  for (int i = 7; i >= 0; --i) {
    out = (out << 8) | p[i];
  }
  return out;
}

void store_u16(uint8_t* p, uint16_t value) {
  p[0] = static_cast<uint8_t>(value & 0xffu);
  p[1] = static_cast<uint8_t>((value >> 8) & 0xffu);
}

void store_u32(uint8_t* p, uint32_t value) {
  for (int i = 0; i < 4; ++i) {
    p[i] = static_cast<uint8_t>((value >> (8 * i)) & 0xffu);
  }
}

void store_u64(uint8_t* p, uint64_t value) {
  for (int i = 0; i < 8; ++i) {
    p[i] = static_cast<uint8_t>((value >> (8 * i)) & 0xffu);
  }
}

std::string hex_digest(const uint8_t* bytes, size_t n) {
  std::ostringstream out;
  out << std::hex << std::setfill('0');
  for (size_t i = 0; i < n; ++i) {
    out << std::setw(2) << static_cast<unsigned>(bytes[i]);
  }
  return out.str();
}

std::string sha256_bytes(const uint8_t* bytes, size_t n) {
  uint8_t digest[SHA256_DIGEST_LENGTH];
  SHA256(bytes, n, digest);
  return hex_digest(digest, sizeof(digest));
}

std::string sha256_stream_paths(const std::vector<std::string>& paths) {
  SHA256_CTX ctx;
  SHA256_Init(&ctx);
  std::array<uint8_t, 1 << 20> buf{};
  for (const std::string& path : paths) {
    std::ifstream in(path, std::ios::binary);
    if (!in) {
      fail("unable to open for sha256: " + path);
    }
    while (in) {
      in.read(reinterpret_cast<char*>(buf.data()), static_cast<std::streamsize>(buf.size()));
      const std::streamsize got = in.gcount();
      if (got > 0) {
        SHA256_Update(&ctx, buf.data(), static_cast<size_t>(got));
      }
    }
  }
  uint8_t digest[SHA256_DIGEST_LENGTH];
  SHA256_Final(digest, &ctx);
  return hex_digest(digest, sizeof(digest));
}

std::string utc_iso() {
  std::time_t now = std::time(nullptr);
  std::tm tm{};
  gmtime_r(&now, &tm);
  char buf[64];
  std::strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &tm);
  return std::string(buf);
}

std::string json_escape(std::string_view s) {
  std::string out;
  out.reserve(s.size() + 8);
  for (char c : s) {
    switch (c) {
      case '\\':
        out += "\\\\";
        break;
      case '"':
        out += "\\\"";
        break;
      case '\n':
        out += "\\n";
        break;
      case '\r':
        out += "\\r";
        break;
      case '\t':
        out += "\\t";
        break;
      default:
        out += c;
        break;
    }
  }
  return out;
}

struct Options {
  std::string label;
  std::string output;
  std::string embedding;
  std::string jl;
  std::string result_json;
  std::string embed_sha;
  std::string embed_manifest_sha;
  std::string jl_sha;
  int64_t max_records = -1;
  int threads = 1;
  std::vector<std::string> pqa1_paths;
};

std::vector<std::string> read_list_file(const std::string& path) {
  std::ifstream in(path);
  if (!in) {
    fail("unable to open pqa1 list: " + path);
  }
  std::vector<std::string> paths;
  std::string line;
  while (std::getline(in, line)) {
    if (!line.empty()) {
      paths.push_back(line);
    }
  }
  return paths;
}

Options parse_args(int argc, char** argv) {
  Options opt;
  for (int i = 1; i < argc; ++i) {
    std::string arg = argv[i];
    auto take = [&](const char* name) -> std::string {
      if (i + 1 >= argc) {
        fail(std::string("missing value for ") + name);
      }
      return argv[++i];
    };
    if (arg == "--label") {
      opt.label = take("--label");
    } else if (arg == "--output") {
      opt.output = take("--output");
    } else if (arg == "--embedding") {
      opt.embedding = take("--embedding");
    } else if (arg == "--jl") {
      opt.jl = take("--jl");
    } else if (arg == "--result-json") {
      opt.result_json = take("--result-json");
    } else if (arg == "--embed-sha") {
      opt.embed_sha = take("--embed-sha");
    } else if (arg == "--embed-manifest-sha") {
      opt.embed_manifest_sha = take("--embed-manifest-sha");
    } else if (arg == "--jl-sha") {
      opt.jl_sha = take("--jl-sha");
    } else if (arg == "--max-records") {
      opt.max_records = std::stoll(take("--max-records"));
    } else if (arg == "--threads") {
      opt.threads = std::stoi(take("--threads"));
    } else if (arg == "--pqa1-list") {
      opt.pqa1_paths = read_list_file(take("--pqa1-list"));
    } else if (arg == "--pqa1") {
      opt.pqa1_paths.push_back(take("--pqa1"));
    } else {
      fail("unknown argument: " + arg);
    }
  }
  if (opt.label.empty() || opt.output.empty() || opt.embedding.empty() || opt.jl.empty() || opt.result_json.empty()) {
    fail("missing required arguments");
  }
  if (opt.embed_sha.empty() || opt.embed_manifest_sha.empty() || opt.jl_sha.empty()) {
    fail("missing artifact hash arguments");
  }
  if (opt.pqa1_paths.empty()) {
    fail("no pqa1 paths supplied");
  }
  opt.threads = std::max(1, opt.threads);
  return opt;
}

struct MappedFile {
  std::string path;
  int fd = -1;
  uint8_t* data = nullptr;
  size_t size = 0;

  MappedFile() = default;
  MappedFile(const MappedFile&) = delete;
  MappedFile& operator=(const MappedFile&) = delete;

  MappedFile(MappedFile&& other) noexcept {
    *this = std::move(other);
  }

  MappedFile& operator=(MappedFile&& other) noexcept {
    if (this == &other) {
      return *this;
    }
    close_map();
    path = std::move(other.path);
    fd = other.fd;
    data = other.data;
    size = other.size;
    other.fd = -1;
    other.data = nullptr;
    other.size = 0;
    return *this;
  }

  ~MappedFile() {
    close_map();
  }

  void close_map() {
    if (data != nullptr) {
      munmap(data, size);
      data = nullptr;
    }
    if (fd >= 0) {
      close(fd);
      fd = -1;
    }
  }

  static MappedFile map_read(const std::string& p) {
    MappedFile f;
    f.path = p;
    f.fd = open(p.c_str(), O_RDONLY);
    if (f.fd < 0) {
      fail("open failed: " + p);
    }
    struct stat st {};
    if (fstat(f.fd, &st) != 0) {
      fail("fstat failed: " + p);
    }
    if (st.st_size <= 0) {
      fail("empty file: " + p);
    }
    f.size = static_cast<size_t>(st.st_size);
    void* mapped = mmap(nullptr, f.size, PROT_READ, MAP_SHARED, f.fd, 0);
    if (mapped == MAP_FAILED) {
      fail("mmap read failed: " + p);
    }
    f.data = static_cast<uint8_t*>(mapped);
    return f;
  }
};

struct OutputMap {
  int fd = -1;
  uint8_t* data = nullptr;
  uint64_t size = 0;

  OutputMap() = default;
  OutputMap(const OutputMap&) = delete;
  OutputMap& operator=(const OutputMap&) = delete;

  OutputMap(OutputMap&& other) noexcept {
    *this = std::move(other);
  }

  OutputMap& operator=(OutputMap&& other) noexcept {
    if (this == &other) {
      return *this;
    }
    if (data != nullptr) {
      msync(data, static_cast<size_t>(size), MS_SYNC);
      munmap(data, static_cast<size_t>(size));
    }
    if (fd >= 0) {
      close(fd);
    }
    fd = other.fd;
    data = other.data;
    size = other.size;
    other.fd = -1;
    other.data = nullptr;
    other.size = 0;
    return *this;
  }

  ~OutputMap() {
    if (data != nullptr) {
      msync(data, static_cast<size_t>(size), MS_SYNC);
      munmap(data, static_cast<size_t>(size));
    }
    if (fd >= 0) {
      close(fd);
    }
  }

  static OutputMap create(const std::string& path, uint64_t bytes) {
    OutputMap out;
    out.fd = open(path.c_str(), O_RDWR | O_CREAT | O_TRUNC, 0644);
    if (out.fd < 0) {
      fail("open output failed: " + path);
    }
    if (ftruncate(out.fd, static_cast<off_t>(bytes)) != 0) {
      fail("ftruncate output failed: " + path);
    }
    void* mapped = mmap(nullptr, static_cast<size_t>(bytes), PROT_READ | PROT_WRITE, MAP_SHARED, out.fd, 0);
    if (mapped == MAP_FAILED) {
      fail("mmap output failed: " + path);
    }
    out.data = static_cast<uint8_t*>(mapped);
    out.size = bytes;
    return out;
  }
};

struct SegmentRef {
  uint8_t role = 0;
  uint32_t token_start = 0;
  uint32_t token_end = 0;
  uint8_t loss_mask = 0;
};

struct RecordRef {
  uint32_t file_index = 0;
  uint64_t offset = 0;
  uint64_t first_packet_id = 0;
  uint64_t record_hash = 0;
  uint32_t token_count = 0;
  uint16_t segment_count = 0;
  uint16_t continuation_count = 0;
  uint8_t source_kind = 0;
};

struct ScanResult {
  std::vector<MappedFile> files;
  std::vector<std::string> consumed_paths;
  std::vector<RecordRef> records;
  std::string vocab_sha;
  std::string merges_sha;
  std::string source_hash;
  uint64_t source_token_count = 0;
  uint64_t packet_count = 0;
};

void validate_segment(const std::string& path, uint64_t index, uint8_t role, uint32_t start, uint32_t end,
                      uint32_t byte_start, uint32_t byte_end, uint8_t loss, uint32_t token_count) {
  if (role != 1 && role != 2) {
    fail(path + ": unknown role at record " + std::to_string(index));
  }
  if (loss != 0 && loss != 1) {
    fail(path + ": malformed loss mask at record " + std::to_string(index));
  }
  if (start > end || end > token_count) {
    fail(path + ": segment token span out of range at record " + std::to_string(index));
  }
  if (byte_start > byte_end) {
    fail(path + ": segment byte span reversed at record " + std::to_string(index));
  }
}

ScanResult scan_pqa1(const Options& opt) {
  Timer timer;
  ScanResult result;
  uint64_t loaded_records = 0;
  uint64_t next_packet = 0;
  bool have_hashes = false;

  for (const std::string& path : opt.pqa1_paths) {
    if (opt.max_records >= 0 && loaded_records >= static_cast<uint64_t>(opt.max_records)) {
      break;
    }
    MappedFile file = MappedFile::map_read(path);
    const uint32_t file_index = static_cast<uint32_t>(result.files.size());
    if (file.size < 144) {
      fail(path + ": truncated PQA1 header");
    }
    const uint8_t* data = file.data;
    if (std::memcmp(data, "PQA1", 4) != 0) {
      fail(path + ": bad PQA1 magic");
    }
    if (load_u16(data + 4) != 1 || load_u16(data + 6) != 1) {
      fail(path + ": unsupported PQA1 schema/endian");
    }
    const uint64_t record_count = load_u64(data + 8);
    std::string vocab(reinterpret_cast<const char*>(data + 16), 64);
    std::string merges(reinterpret_cast<const char*>(data + 80), 64);
    if (!have_hashes) {
      result.vocab_sha = vocab;
      result.merges_sha = merges;
      have_hashes = true;
    } else if (result.vocab_sha != vocab || result.merges_sha != merges) {
      fail(path + ": mixed tokenizer hashes");
    }

    uint64_t offset = 144;
    for (uint64_t index = 0; index < record_count; ++index) {
      if (offset + 15 > file.size) {
        fail(path + ": truncated record header");
      }
      const uint64_t record_offset = offset;
      const uint64_t record_hash = load_u64(data + offset);
      offset += 8;
      const uint8_t source_kind = data[offset++];
      const uint32_t token_count = load_u32(data + offset);
      offset += 4;
      const uint16_t segment_count = load_u16(data + offset);
      offset += 2;
      if (source_kind < 1 || source_kind > 4) {
        fail(path + ": bad source_kind at record " + std::to_string(index));
      }
      if (token_count == 0 || token_count > kMaxRecordTokens) {
        fail(path + ": bad token_count at record " + std::to_string(index));
      }
      if (segment_count == 0 || segment_count > kMaxSegments) {
        fail(path + ": bad segment_count at record " + std::to_string(index));
      }
      const uint64_t need = static_cast<uint64_t>(token_count) * 4u + static_cast<uint64_t>(segment_count) * 18u;
      if (offset + need > file.size) {
        fail(path + ": truncated record payload");
      }
      offset += static_cast<uint64_t>(token_count) * 4u;
      for (uint16_t s = 0; s < segment_count; ++s) {
        const uint8_t role = data[offset];
        const uint32_t token_start = load_u32(data + offset + 1);
        const uint32_t token_end = load_u32(data + offset + 5);
        const uint32_t byte_start = load_u32(data + offset + 9);
        const uint32_t byte_end = load_u32(data + offset + 13);
        const uint8_t loss = data[offset + 17];
        validate_segment(path, index, role, token_start, token_end, byte_start, byte_end, loss, token_count);
        offset += 18;
      }

      const bool keep = opt.max_records < 0 || loaded_records < static_cast<uint64_t>(opt.max_records);
      if (keep) {
        const uint16_t continuation_count = static_cast<uint16_t>((token_count + kPacketLen - 1) / kPacketLen);
        result.records.push_back(RecordRef{
            file_index,
            record_offset,
            next_packet,
            record_hash,
            token_count,
            segment_count,
            continuation_count,
            source_kind,
        });
        result.source_token_count += token_count;
        result.packet_count += continuation_count;
        next_packet += continuation_count;
        ++loaded_records;
      }
    }
    if (offset != file.size) {
      fail(path + ": trailing bytes after PQA1 records");
    }
    result.consumed_paths.push_back(path);
    result.files.push_back(std::move(file));
  }

  if (result.records.empty()) {
    fail("no records loaded");
  }
  result.source_hash = sha256_stream_paths(result.consumed_paths);
  (void)timer;
  return result;
}

struct Layout {
  uint64_t metadata_offset = 0;
  uint64_t metadata_len = 0;
  uint64_t token_ids_offset = 0;
  uint64_t token_ids_len = 0;
  uint64_t roles_offset = 0;
  uint64_t roles_len = 0;
  uint64_t input_polar_offset = 0;
  uint64_t input_polar_len = 0;
  uint64_t target_polar_offset = 0;
  uint64_t target_polar_len = 0;
  uint64_t pooled_answer_offset = 0;
  uint64_t pooled_answer_len = 0;
  uint64_t file_len = 0;
};

Layout make_layout(uint64_t packet_count) {
  Layout layout;
  uint64_t offset = kPjp1HeaderBytes;
  layout.metadata_offset = offset;
  layout.metadata_len = packet_count * kPjp1MetaBytes;
  offset += layout.metadata_len;
  layout.token_ids_offset = offset;
  layout.token_ids_len = packet_count * kTokenBytes;
  offset += layout.token_ids_len;
  layout.roles_offset = offset;
  layout.roles_len = packet_count * kRoleBytes;
  offset += layout.roles_len;
  layout.input_polar_offset = offset;
  layout.input_polar_len = packet_count * kPolarBytes;
  offset += layout.input_polar_len;
  layout.target_polar_offset = offset;
  layout.target_polar_len = packet_count * kPolarBytes;
  offset += layout.target_polar_len;
  layout.pooled_answer_offset = offset;
  layout.pooled_answer_len = packet_count * kPooledBytes;
  offset += layout.pooled_answer_len;
  layout.file_len = offset;
  return layout;
}

void put_padded(uint8_t* dst, size_t width, const std::string& text) {
  std::memset(dst, 0, width);
  const size_t n = std::min(width, text.size());
  std::memcpy(dst, text.data(), n);
}

void write_header(uint8_t* out, const ScanResult& scan, const Options& opt, const Layout& layout) {
  std::memset(out, 0, kPjp1HeaderBytes);
  std::memcpy(out, "PJP1", 4);
  store_u16(out + 4, 1);
  store_u16(out + 6, 1);
  store_u32(out + 8, kPjp1HeaderBytes);
  store_u32(out + 12, kPacketLen);
  store_u32(out + 16, kJlDim);
  store_u32(out + 20, kEmbedDim);
  store_u64(out + 24, scan.packet_count);
  store_u64(out + 32, static_cast<uint64_t>(scan.records.size()));
  store_u64(out + 40, scan.source_token_count);
  store_u64(out + 48, scan.packet_count * kPacketLen);
  store_u32(out + 64, 6);

  uint64_t cursor = 80;
  const std::array<std::pair<std::string, size_t>, 9> strings{{
      {scan.source_hash, 64},
      {scan.vocab_sha, 64},
      {scan.merges_sha, 64},
      {opt.embed_sha, 64},
      {opt.embed_manifest_sha, 64},
      {opt.jl_sha, 64},
      {utc_iso(), 40},
      {"phase2b_native_cpp_neon_writer_v1", 32},
      {"dense_rademacher_k256_lsb_bitpack", 48},
  }};
  for (const auto& item : strings) {
    put_padded(out + cursor, item.second, item.first);
    cursor += item.second;
  }

  struct Section {
    const char* name;
    uint64_t off;
    uint64_t len;
  };
  const std::array<Section, 6> sections{{
      {"metadata", layout.metadata_offset, layout.metadata_len},
      {"token_ids", layout.token_ids_offset, layout.token_ids_len},
      {"roles", layout.roles_offset, layout.roles_len},
      {"input_polar", layout.input_polar_offset, layout.input_polar_len},
      {"target_polar", layout.target_polar_offset, layout.target_polar_len},
      {"pooled_answer", layout.pooled_answer_offset, layout.pooled_answer_len},
  }};
  cursor = 768;
  for (const Section& section : sections) {
    put_padded(out + cursor, 24, section.name);
    store_u64(out + cursor + 24, section.off);
    store_u64(out + cursor + 32, section.len);
    cursor += 40;
  }
}

struct EmbeddingMap {
  MappedFile map;
  const __fp16* rows = nullptr;

  static EmbeddingMap load(const std::string& path) {
    EmbeddingMap out;
    out.map = MappedFile::map_read(path);
    const uint64_t expected = static_cast<uint64_t>(kVocabSize) * kEmbedDim * 2u;
    if (out.map.size != expected) {
      fail("embedding size mismatch");
    }
    out.rows = reinterpret_cast<const __fp16*>(out.map.data);
    return out;
  }
};

struct MatrixMap {
  MappedFile map;
  const int8_t* signs = nullptr;

  static MatrixMap load(const std::string& path) {
    MatrixMap out;
    out.map = MappedFile::map_read(path);
    const uint64_t expected = static_cast<uint64_t>(kEmbedDim) * kJlDim;
    if (out.map.size != expected) {
      fail("JL matrix size mismatch");
    }
    out.signs = reinterpret_cast<const int8_t*>(out.map.data);
    return out;
  }
};

struct PacketLocal {
  alignas(16) uint32_t token_ids[kPacketLen];
  alignas(16) uint8_t roles[kPacketLen];
  alignas(16) uint8_t input[kPolarBytes];
  alignas(16) uint8_t target[kPolarBytes];
  alignas(16) uint8_t pooled[kPooledBytes];
  unsigned __int128 loss_mask = 0;
  unsigned __int128 pad_mask = 0;
  uint16_t real = 0;
  uint16_t pad = 0;
  uint16_t answer_active_count = 0;

  void reset() {
    std::memset(token_ids, 0, sizeof(token_ids));
    std::memset(roles, 0, sizeof(roles));
    std::memset(input, 0, sizeof(input));
    std::memset(target, 0, sizeof(target));
    std::memset(pooled, 0, sizeof(pooled));
    loss_mask = 0;
    pad_mask = 0;
    real = 0;
    pad = 0;
    answer_active_count = 0;
  }
};

void set_mask128(uint8_t* dst, unsigned __int128 value) {
  store_u64(dst, static_cast<uint64_t>(value));
  store_u64(dst + 8, static_cast<uint64_t>(value >> 64));
}

uint64_t token_hash64(const uint32_t* ids, uint16_t real) {
  uint8_t digest[SHA256_DIGEST_LENGTH];
  SHA256(reinterpret_cast<const uint8_t*>(ids), static_cast<size_t>(real) * 4u, digest);
  return load_u64(digest);
}

void project_group4(const __fp16* embedding, const int8_t* signs, const uint32_t* token_ids, int lanes, uint8_t* out32_by_lane) {
  for (uint32_t k0 = 0; k0 < kJlDim; k0 += kTokenProjectionTile) {
    float32x4_t acc[kTokenProjectionTile];
    for (auto& item : acc) {
      item = vdupq_n_f32(0.0f);
    }

    for (uint32_t d = 0; d < kEmbedDim; ++d) {
      float vals[4] = {0.0f, 0.0f, 0.0f, 0.0f};
      for (int lane = 0; lane < lanes; ++lane) {
        vals[lane] = static_cast<float>(embedding[static_cast<uint64_t>(token_ids[lane]) * kEmbedDim + d]);
      }
      const float32x4_t v = vld1q_f32(vals);
      const int8_t* row = signs + static_cast<uint64_t>(d) * kJlDim + k0;
      for (uint32_t j = 0; j < kTokenProjectionTile; ++j) {
        const float s = row[j] > 0 ? 1.0f : -1.0f;
        acc[j] = vmlaq_n_f32(acc[j], v, s);
      }
    }

    for (uint32_t j = 0; j < kTokenProjectionTile; ++j) {
      float sums[4];
      vst1q_f32(sums, acc[j]);
      const uint32_t bit = k0 + j;
      const uint8_t mask = static_cast<uint8_t>(1u << (bit & 7u));
      const uint32_t byte_index = bit >> 3u;
      for (int lane = 0; lane < lanes; ++lane) {
        if (sums[lane] >= 0.0f) {
          out32_by_lane[static_cast<size_t>(lane) * 32u + byte_index] |= mask;
        }
      }
    }
  }
}

void project_f32_row(const float* row_f32, const int8_t* signs, uint8_t out32[kPooledBytes]) {
  std::memset(out32, 0, kPooledBytes);
  for (uint32_t k0 = 0; k0 < kJlDim; k0 += 4) {
    float32x4_t acc = vdupq_n_f32(0.0f);
    for (uint32_t d = 0; d < kEmbedDim; ++d) {
      const float32x4_t v = vdupq_n_f32(row_f32[d]);
      const int8_t* src = signs + static_cast<uint64_t>(d) * kJlDim + k0;
      float sign_values[4] = {
          src[0] > 0 ? 1.0f : -1.0f,
          src[1] > 0 ? 1.0f : -1.0f,
          src[2] > 0 ? 1.0f : -1.0f,
          src[3] > 0 ? 1.0f : -1.0f,
      };
      acc = vmlaq_f32(acc, v, vld1q_f32(sign_values));
    }
    float sums[4];
    vst1q_f32(sums, acc);
    for (uint32_t j = 0; j < 4; ++j) {
      const uint32_t bit = k0 + j;
      if (sums[j] >= 0.0f) {
        out32[bit >> 3u] |= static_cast<uint8_t>(1u << (bit & 7u));
      }
    }
  }
}

void write_packet_meta(uint8_t* meta, uint64_t packet_id, uint64_t record_hash, uint8_t source_kind,
                       uint16_t continuation_index, uint16_t continuation_count, uint32_t source_token_start,
                       const PacketLocal& packet, uint64_t token_hash, const Layout& layout, uint32_t crc) {
  std::memset(meta, 0, kPjp1MetaBytes);
  store_u64(meta + 0, packet_id);
  store_u64(meta + 8, record_hash);
  meta[16] = source_kind;
  store_u16(meta + 17, continuation_index);
  store_u16(meta + 19, continuation_count);
  store_u32(meta + 21, source_token_start);
  store_u16(meta + 25, packet.real);
  store_u16(meta + 27, packet.pad);
  store_u64(meta + 29, token_hash);
  set_mask128(meta + 40, packet.loss_mask);
  set_mask128(meta + 56, packet.pad_mask);

  const uint64_t in_off = layout.input_polar_offset + packet_id * kPolarBytes;
  const uint64_t tgt_off = layout.target_polar_offset + packet_id * kPolarBytes;
  const uint64_t pool_off = layout.pooled_answer_offset + packet_id * kPooledBytes;
  const uint64_t tok_off = layout.token_ids_offset + packet_id * kTokenBytes;
  const uint64_t role_off = layout.roles_offset + packet_id * kRoleBytes;

  uint64_t cursor = 72;
  const std::array<std::pair<uint64_t, uint32_t>, 5> pairs{{
      {in_off, kPolarBytes},
      {tgt_off, kPolarBytes},
      {pool_off, kPooledBytes},
      {tok_off, kTokenBytes},
      {role_off, kRoleBytes},
  }};
  for (const auto& item : pairs) {
    store_u64(meta + cursor, item.first);
    store_u32(meta + cursor + 8, item.second);
    cursor += 12;
  }
  store_u32(meta + cursor, crc);
}

struct WorkerStats {
  uint64_t records = 0;
  uint64_t packets = 0;
  uint64_t real_tokens = 0;
};

struct Context {
  const ScanResult* scan = nullptr;
  const EmbeddingMap* embedding = nullptr;
  const MatrixMap* matrix = nullptr;
  const Layout* layout = nullptr;
  uint8_t* output = nullptr;
  std::vector<WorkerStats> worker_stats;
  std::vector<std::pair<uint64_t, uint64_t>> record_ranges;
};

void parse_record_payload(const MappedFile& file, const RecordRef& rec, uint32_t* tokens, SegmentRef* segments) {
  const uint8_t* p = file.data + rec.offset + 15;
  for (uint32_t i = 0; i < rec.token_count; ++i) {
    tokens[i] = load_u32(p + static_cast<uint64_t>(i) * 4u);
  }
  p += static_cast<uint64_t>(rec.token_count) * 4u;
  for (uint16_t i = 0; i < rec.segment_count; ++i) {
    segments[i].role = p[0];
    segments[i].token_start = load_u32(p + 1);
    segments[i].token_end = load_u32(p + 5);
    segments[i].loss_mask = p[17];
    p += 18;
  }
}

void process_record(Context& ctx, const RecordRef& rec, PacketLocal& packet, uint32_t* tokens, uint8_t* role_codes,
                    uint8_t* loss_flags, float* pooled_row, SegmentRef* segments) {
  const MappedFile& file = ctx.scan->files[rec.file_index];
  parse_record_payload(file, rec, tokens, segments);
  std::memset(role_codes, 0, rec.token_count);
  std::memset(loss_flags, 0, rec.token_count);
  for (uint16_t s = 0; s < rec.segment_count; ++s) {
    for (uint32_t i = segments[s].token_start; i < segments[s].token_end; ++i) {
      role_codes[i] = segments[s].role;
      if (segments[s].loss_mask != 0) {
        loss_flags[i] = 1;
      }
    }
  }

  for (uint16_t cont = 0; cont < rec.continuation_count; ++cont) {
    packet.reset();
    const uint32_t start = static_cast<uint32_t>(cont) * kPacketLen;
    const uint32_t end = std::min(start + kPacketLen, rec.token_count);
    packet.real = static_cast<uint16_t>(end - start);
    packet.pad = static_cast<uint16_t>(kPacketLen - packet.real);
    for (uint32_t slot = 0; slot < kPacketLen; ++slot) {
      if (slot < packet.real) {
        const uint32_t source_index = start + slot;
        const uint32_t token_id = tokens[source_index];
        if (token_id >= kVocabSize) {
          fail("token id out of embedding range");
        }
        packet.token_ids[slot] = token_id;
        packet.roles[slot] = role_codes[source_index];
        if (loss_flags[source_index] != 0) {
          packet.loss_mask |= (static_cast<unsigned __int128>(1) << slot);
          ++packet.answer_active_count;
        }
      } else {
        packet.pad_mask |= (static_cast<unsigned __int128>(1) << slot);
      }
    }

    for (uint32_t slot = 0; slot < packet.real; slot += 4) {
      const int lanes = static_cast<int>(std::min<uint32_t>(4, packet.real - slot));
      project_group4(ctx.embedding->rows, ctx.matrix->signs, packet.token_ids + slot, lanes, packet.input + static_cast<uint64_t>(slot) * 32u);
    }
    for (uint32_t slot = 0; slot < packet.real; ++slot) {
      if (((packet.loss_mask >> slot) & 1u) != 0) {
        std::memcpy(packet.target + static_cast<uint64_t>(slot) * 32u, packet.input + static_cast<uint64_t>(slot) * 32u, 32);
      }
    }

    if (packet.answer_active_count > 0) {
      std::fill(pooled_row, pooled_row + kEmbedDim, 0.0f);
      for (uint32_t slot = 0; slot < packet.real; ++slot) {
        if (((packet.loss_mask >> slot) & 1u) == 0) {
          continue;
        }
        const __fp16* row = ctx.embedding->rows + static_cast<uint64_t>(packet.token_ids[slot]) * kEmbedDim;
        for (uint32_t d = 0; d < kEmbedDim; ++d) {
          pooled_row[d] += static_cast<float>(row[d]);
        }
      }
      const float inv = 1.0f / static_cast<float>(packet.answer_active_count);
      for (uint32_t d = 0; d < kEmbedDim; ++d) {
        pooled_row[d] *= inv;
      }
      project_f32_row(pooled_row, ctx.matrix->signs, packet.pooled);
    }

    const uint64_t packet_id = rec.first_packet_id + cont;
    const uint64_t tok_off = ctx.layout->token_ids_offset + packet_id * kTokenBytes;
    const uint64_t role_off = ctx.layout->roles_offset + packet_id * kRoleBytes;
    const uint64_t in_off = ctx.layout->input_polar_offset + packet_id * kPolarBytes;
    const uint64_t tgt_off = ctx.layout->target_polar_offset + packet_id * kPolarBytes;
    const uint64_t pool_off = ctx.layout->pooled_answer_offset + packet_id * kPooledBytes;
    std::memcpy(ctx.output + tok_off, packet.token_ids, kTokenBytes);
    std::memcpy(ctx.output + role_off, packet.roles, kRoleBytes);
    std::memcpy(ctx.output + in_off, packet.input, kPolarBytes);
    std::memcpy(ctx.output + tgt_off, packet.target, kPolarBytes);
    std::memcpy(ctx.output + pool_off, packet.pooled, kPooledBytes);

    uLong crc = crc32(0L, Z_NULL, 0);
    crc = crc32(crc, reinterpret_cast<const Bytef*>(packet.token_ids), kTokenBytes);
    crc = crc32(crc, reinterpret_cast<const Bytef*>(packet.roles), kRoleBytes);
    crc = crc32(crc, reinterpret_cast<const Bytef*>(packet.input), kPolarBytes);
    crc = crc32(crc, reinterpret_cast<const Bytef*>(packet.target), kPolarBytes);
    crc = crc32(crc, reinterpret_cast<const Bytef*>(packet.pooled), kPooledBytes);
    const uint64_t tok_hash = token_hash64(packet.token_ids, packet.real);
    uint8_t meta[kPjp1MetaBytes];
    write_packet_meta(meta, packet_id, rec.record_hash, rec.source_kind, cont, rec.continuation_count, start, packet, tok_hash,
                      *ctx.layout, static_cast<uint32_t>(crc));
    std::memcpy(ctx.output + ctx.layout->metadata_offset + packet_id * kPjp1MetaBytes, meta, kPjp1MetaBytes);
  }
}

void worker_main(Context& ctx, int worker_index) {
  PacketLocal packet;
  alignas(16) uint32_t tokens[kMaxRecordTokens];
  alignas(16) uint8_t role_codes[kMaxRecordTokens];
  alignas(16) uint8_t loss_flags[kMaxRecordTokens];
  alignas(16) float pooled_row[kEmbedDim];
  SegmentRef segments[kMaxSegments];
  WorkerStats stats;
  const auto [begin, end] = ctx.record_ranges[static_cast<size_t>(worker_index)];

  for (uint64_t index = begin; index < end; ++index) {
    const RecordRef& rec = ctx.scan->records[index];
    process_record(ctx, rec, packet, tokens, role_codes, loss_flags, pooled_row, segments);
    ++stats.records;
    stats.packets += rec.continuation_count;
    stats.real_tokens += rec.token_count;
  }
  ctx.worker_stats[static_cast<size_t>(worker_index)] = stats;
}

std::vector<std::pair<uint64_t, uint64_t>> make_record_ranges(const ScanResult& scan, int threads) {
  std::vector<std::pair<uint64_t, uint64_t>> ranges(static_cast<size_t>(threads), {0, 0});
  const uint64_t total = scan.source_token_count;
  uint64_t begin = 0;
  uint64_t token_cursor = 0;
  for (int worker = 0; worker < threads; ++worker) {
    const uint64_t target = (total * static_cast<uint64_t>(worker + 1)) / static_cast<uint64_t>(threads);
    uint64_t end = begin;
    while (end < scan.records.size() && (token_cursor < target || end == begin)) {
      token_cursor += scan.records[end].token_count;
      ++end;
    }
    ranges[static_cast<size_t>(worker)] = {begin, end};
    begin = end;
  }
  if (!ranges.empty()) {
    ranges.back().second = scan.records.size();
  }
  return ranges;
}

struct Sample {
  uint64_t packet_id = 0;
  uint64_t record_hash = 0;
  uint16_t real = 0;
  uint16_t pad = 0;
  uint16_t answer_active_count = 0;
  std::string input_sha;
  std::string target_sha;
  std::string pooled_sha;
  uint32_t crc32_value = 0;
};

uint16_t popcount128(unsigned __int128 value) {
  const uint64_t low = static_cast<uint64_t>(value);
  const uint64_t high = static_cast<uint64_t>(value >> 64);
  return static_cast<uint16_t>(__builtin_popcountll(low) + __builtin_popcountll(high));
}

std::vector<Sample> collect_samples(const uint8_t* output, const Layout& layout, uint64_t packet_count) {
  std::vector<Sample> samples;
  const uint64_t limit = std::min<uint64_t>(5, packet_count);
  for (uint64_t pid = 0; pid < limit; ++pid) {
    const uint8_t* meta = output + layout.metadata_offset + pid * kPjp1MetaBytes;
    const uint64_t in_off = load_u64(meta + 72);
    const uint64_t tgt_off = load_u64(meta + 84);
    const uint64_t pool_off = load_u64(meta + 96);
    const unsigned __int128 loss =
        static_cast<unsigned __int128>(load_u64(meta + 40)) | (static_cast<unsigned __int128>(load_u64(meta + 48)) << 64);
    Sample sample;
    sample.packet_id = load_u64(meta);
    sample.record_hash = load_u64(meta + 8);
    sample.real = load_u16(meta + 25);
    sample.pad = load_u16(meta + 27);
    sample.answer_active_count = popcount128(loss);
    sample.input_sha = sha256_bytes(output + in_off, kPolarBytes);
    sample.target_sha = sha256_bytes(output + tgt_off, kPolarBytes);
    sample.pooled_sha = sha256_bytes(output + pool_off, kPooledBytes);
    sample.crc32_value = load_u32(meta + 132);
    samples.push_back(sample);
  }
  return samples;
}

std::string read_status_value(const char* key) {
  std::ifstream in("/proc/self/status");
  std::string line;
  const std::string prefix = std::string(key) + ":";
  while (std::getline(in, line)) {
    if (line.rfind(prefix, 0) == 0) {
      return line.substr(prefix.size());
    }
  }
  return "";
}

void write_result_json(const Options& opt, const ScanResult& scan, const Layout& layout, const std::vector<Sample>& samples,
                       const std::vector<WorkerStats>& worker_stats, double scan_sec, double output_prepare_sec,
                       double process_sec, double total_sec) {
  std::ofstream out(opt.result_json);
  if (!out) {
    fail("unable to write result json: " + opt.result_json);
  }
  uint64_t worker_records = 0;
  uint64_t worker_packets = 0;
  uint64_t worker_tokens = 0;
  for (const WorkerStats& stats : worker_stats) {
    worker_records += stats.records;
    worker_packets += stats.packets;
    worker_tokens += stats.real_tokens;
  }
  const double tokens_per_sec = static_cast<double>(scan.source_token_count) / total_sec;
  const double records_per_sec = static_cast<double>(scan.records.size()) / total_sec;
  const double packets_per_sec = static_cast<double>(scan.packet_count) / total_sec;
  const double mb_per_sec = (static_cast<double>(layout.file_len) / 1000000.0) / total_sec;

  out << "{\n";
  out << "  \"schema_version\": \"polar_phase2b_native_packetizer_run_v1\",\n";
  out << "  \"status\": \"pass\",\n";
  out << "  \"writer\": \"phase2b_native_cpp_neon_writer_v1\",\n";
  out << "  \"label\": \"" << json_escape(opt.label) << "\",\n";
  out << "  \"thread_count\": " << opt.threads << ",\n";
  out << "  \"job_count\": " << scan.records.size() << ",\n";
  out << "  \"pqa1_files_consumed\": " << scan.consumed_paths.size() << ",\n";
  out << "  \"source_record_count\": " << scan.records.size() << ",\n";
  out << "  \"source_real_token_count\": " << scan.source_token_count << ",\n";
  out << "  \"packet_count\": " << scan.packet_count << ",\n";
  out << "  \"slot_count\": " << (scan.packet_count * kPacketLen) << ",\n";
  out << "  \"pqa1_source_sha256_stream\": \"" << scan.source_hash << "\",\n";
  out << "  \"pjp1_path\": \"" << json_escape(opt.output) << "\",\n";
  out << "  \"pjp1_bytes\": " << layout.file_len << ",\n";
  out << "  \"timing_sec\": {\n";
  out << "    \"scan_validate\": " << scan_sec << ",\n";
  out << "    \"output_prepare\": " << output_prepare_sec << ",\n";
  out << "    \"native_process\": " << process_sec << ",\n";
  out << "    \"total\": " << total_sec << "\n";
  out << "  },\n";
  out << "  \"throughput\": {\n";
  out << "    \"records_per_sec\": " << records_per_sec << ",\n";
  out << "    \"real_tokens_per_sec\": " << tokens_per_sec << ",\n";
  out << "    \"packets_per_sec\": " << packets_per_sec << ",\n";
  out << "    \"packet_slots_per_sec\": " << (static_cast<double>(scan.packet_count * kPacketLen) / total_sec) << ",\n";
  out << "    \"output_MB_per_sec\": " << mb_per_sec << "\n";
  out << "  },\n";
  out << "  \"worker_rollup\": {\n";
  out << "    \"records\": " << worker_records << ",\n";
  out << "    \"packets\": " << worker_packets << ",\n";
  out << "    \"real_tokens\": " << worker_tokens << "\n";
  out << "  },\n";
  out << "  \"memory_after\": {\n";
  out << "    \"VmRSS\": \"" << json_escape(read_status_value("VmRSS")) << "\",\n";
  out << "    \"VmHWM\": \"" << json_escape(read_status_value("VmHWM")) << "\",\n";
  out << "    \"VmSize\": \"" << json_escape(read_status_value("VmSize")) << "\"\n";
  out << "  },\n";
  out << "  \"sampled_packets\": [\n";
  for (size_t i = 0; i < samples.size(); ++i) {
    const Sample& s = samples[i];
    out << "    {\"packet_id\": " << s.packet_id << ", \"record_hash\": " << s.record_hash
        << ", \"real_token_count\": " << s.real << ", \"pad_count\": " << s.pad
        << ", \"answer_active_count\": " << s.answer_active_count << ", \"input_sha256\": \"" << s.input_sha
        << "\", \"target_sha256\": \"" << s.target_sha << "\", \"pooled_sha256\": \"" << s.pooled_sha
        << "\", \"crc32\": " << s.crc32_value << "}";
    if (i + 1 != samples.size()) {
      out << ",";
    }
    out << "\n";
  }
  out << "  ]\n";
  out << "}\n";
}

int run(int argc, char** argv) {
  const Timer total_timer;
  Options opt = parse_args(argc, argv);
  const Timer scan_timer;
  ScanResult scan = scan_pqa1(opt);
  const double scan_sec = scan_timer.elapsed();

  EmbeddingMap embedding = EmbeddingMap::load(opt.embedding);
  MatrixMap matrix = MatrixMap::load(opt.jl);
  Layout layout = make_layout(scan.packet_count);

  const Timer prepare_timer;
  OutputMap output = OutputMap::create(opt.output, layout.file_len);
  write_header(output.data, scan, opt, layout);
  const double prepare_sec = prepare_timer.elapsed();

  Context ctx;
  ctx.scan = &scan;
  ctx.embedding = &embedding;
  ctx.matrix = &matrix;
  ctx.layout = &layout;
  ctx.output = output.data;
  ctx.worker_stats.resize(static_cast<size_t>(opt.threads));
  ctx.record_ranges = make_record_ranges(scan, opt.threads);

  const Timer process_timer;
  std::vector<std::thread> threads;
  for (int i = 0; i < opt.threads; ++i) {
    threads.emplace_back(worker_main, std::ref(ctx), i);
  }
  for (auto& thread : threads) {
    thread.join();
  }
  const double process_sec = process_timer.elapsed();

  if (msync(output.data, static_cast<size_t>(layout.file_len), MS_SYNC) != 0) {
    fail("msync output failed");
  }
  const std::vector<Sample> samples = collect_samples(output.data, layout, scan.packet_count);
  const double total_sec = total_timer.elapsed();
  write_result_json(opt, scan, layout, samples, ctx.worker_stats, scan_sec, prepare_sec, process_sec, total_sec);

  std::cout << "{\"status\":\"pass\",\"result_json\":\"" << json_escape(opt.result_json) << "\",\"real_tokens_per_sec\":"
            << (static_cast<double>(scan.source_token_count) / total_sec) << "}" << std::endl;
  return 0;
}

}  // namespace

int main(int argc, char** argv) {
  try {
    return run(argc, argv);
  } catch (const std::exception& exc) {
    std::cerr << "phase2b_native_packetizer_error: " << exc.what() << std::endl;
    return 2;
  }
}
