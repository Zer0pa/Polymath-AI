#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

namespace {

constexpr uint16_t kSchemaVersion = 1;
constexpr uint16_t kEndianMarker = 1;
constexpr uint32_t kHeaderBytes = 4096;
constexpr uint32_t kPacketLen = 128;
constexpr uint32_t kJlDim = 256;
constexpr uint32_t kEmbedDim = 2560;
constexpr uint64_t kSectionTableOffset = 768;
constexpr uint64_t kSectionEntryBytes = 40;
constexpr uint64_t kSectionCount = 6;
constexpr uint64_t kPolarStride = kPacketLen * (kJlDim / 8);
constexpr uint64_t kI8SignsPerPacket = kPacketLen * kJlDim;

struct SectionSpec {
  std::string_view name;
  uint64_t stride;
};

constexpr std::array<SectionSpec, kSectionCount> kExpectedSections{{
    {"metadata", 192},
    {"token_ids", 512},
    {"roles", 128},
    {"input_polar", 4096},
    {"target_polar", 4096},
    {"pooled_answer", 32},
}};

struct Options {
  std::string pjp1_path;
  std::string output_path;
  uint64_t batch_packets = 16;
  uint64_t max_batches = 64;
};

struct Header {
  std::string magic;
  uint16_t schema = 0;
  uint16_t endian = 0;
  uint32_t header_len = 0;
  uint32_t packet_len = 0;
  uint32_t jl_dim = 0;
  uint32_t embedding_dim = 0;
  uint64_t packet_count = 0;
  uint64_t source_record_count = 0;
  uint64_t source_token_count = 0;
  uint64_t slot_count = 0;
  uint32_t section_count = 0;
};

struct Section {
  std::string name;
  uint64_t offset = 0;
  uint64_t length = 0;
  uint64_t stride = 0;
};

[[noreturn]] void fail(const std::string& message) {
  throw std::runtime_error(message);
}

uint16_t load_u16(const std::array<uint8_t, kHeaderBytes>& bytes, size_t offset) {
  return static_cast<uint16_t>(bytes[offset]) | static_cast<uint16_t>(bytes[offset + 1] << 8);
}

uint32_t load_u32(const std::array<uint8_t, kHeaderBytes>& bytes, size_t offset) {
  return static_cast<uint32_t>(bytes[offset]) | (static_cast<uint32_t>(bytes[offset + 1]) << 8) |
         (static_cast<uint32_t>(bytes[offset + 2]) << 16) | (static_cast<uint32_t>(bytes[offset + 3]) << 24);
}

uint64_t load_u64(const std::array<uint8_t, kHeaderBytes>& bytes, size_t offset) {
  uint64_t out = 0;
  for (int i = 7; i >= 0; --i) {
    out = (out << 8) | bytes[offset + static_cast<size_t>(i)];
  }
  return out;
}

std::string decode_padded_ascii(const std::array<uint8_t, kHeaderBytes>& bytes, size_t offset, size_t width) {
  std::string out;
  out.reserve(width);
  for (size_t i = 0; i < width; ++i) {
    const uint8_t value = bytes[offset + i];
    if (value == 0) {
      break;
    }
    out.push_back(value >= 0x20 && value <= 0x7e ? static_cast<char>(value) : '?');
  }
  return out;
}

std::string json_escape(std::string_view text) {
  std::string out;
  out.reserve(text.size() + 8);
  for (const char c : text) {
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
        out.push_back(static_cast<unsigned char>(c) < 0x20 ? '?' : c);
        break;
    }
  }
  return out;
}

std::string utc_now() {
  const std::time_t now = std::time(nullptr);
  std::tm tm{};
#if defined(_WIN32)
  gmtime_s(&tm, &now);
#else
  gmtime_r(&now, &tm);
#endif
  char buf[32];
  std::strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &tm);
  return std::string(buf);
}

uint64_t parse_u64_arg(const std::string& value, const char* name) {
  size_t consumed = 0;
  unsigned long long parsed = 0;
  try {
    parsed = std::stoull(value, &consumed, 10);
  } catch (const std::exception&) {
    fail(std::string("invalid integer for ") + name + ": " + value);
  }
  if (consumed != value.size()) {
    fail(std::string("invalid integer for ") + name + ": " + value);
  }
  return static_cast<uint64_t>(parsed);
}

bool checked_mul(uint64_t lhs, uint64_t rhs, uint64_t& out) {
  if (lhs != 0 && rhs > std::numeric_limits<uint64_t>::max() / lhs) {
    return false;
  }
  out = lhs * rhs;
  return true;
}

size_t checked_size(uint64_t value, std::string_view label) {
  if (value > static_cast<uint64_t>(std::numeric_limits<size_t>::max())) {
    fail(std::string(label) + " exceeds size_t");
  }
  return static_cast<size_t>(value);
}

Options parse_args(int argc, char** argv) {
  Options options;
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    auto take = [&](const char* name) -> std::string {
      if (i + 1 >= argc) {
        fail(std::string("missing value for ") + name);
      }
      return argv[++i];
    };
    if (arg == "--pjp1") {
      options.pjp1_path = take("--pjp1");
    } else if (arg == "--output") {
      options.output_path = take("--output");
    } else if (arg == "--batch-packets") {
      options.batch_packets = parse_u64_arg(take("--batch-packets"), "--batch-packets");
    } else if (arg == "--max-batches") {
      options.max_batches = parse_u64_arg(take("--max-batches"), "--max-batches");
    } else if (arg == "--help" || arg == "-h") {
      std::cout << "usage: phase34_pjp1_i8_staging_bench --pjp1 PATH [--output JSON] "
                   "[--batch-packets N] [--max-batches N]\n";
      std::exit(0);
    } else {
      fail("unknown argument: " + arg);
    }
  }
  if (options.pjp1_path.empty()) {
    fail("missing required --pjp1 PATH");
  }
  if (options.batch_packets == 0) {
    fail("--batch-packets must be positive");
  }
  if (options.max_batches == 0) {
    fail("--max-batches must be positive");
  }
  return options;
}

Header parse_header(const std::array<uint8_t, kHeaderBytes>& bytes) {
  Header header;
  header.magic = decode_padded_ascii(bytes, 0, 4);
  header.schema = load_u16(bytes, 4);
  header.endian = load_u16(bytes, 6);
  header.header_len = load_u32(bytes, 8);
  header.packet_len = load_u32(bytes, 12);
  header.jl_dim = load_u32(bytes, 16);
  header.embedding_dim = load_u32(bytes, 20);
  header.packet_count = load_u64(bytes, 24);
  header.source_record_count = load_u64(bytes, 32);
  header.source_token_count = load_u64(bytes, 40);
  header.slot_count = load_u64(bytes, 48);
  header.section_count = load_u32(bytes, 64);
  return header;
}

std::vector<Section> parse_sections(const std::array<uint8_t, kHeaderBytes>& bytes, uint64_t packet_count) {
  std::vector<Section> sections;
  sections.reserve(kSectionCount);
  for (uint64_t index = 0; index < kSectionCount; ++index) {
    const uint64_t cursor = kSectionTableOffset + index * kSectionEntryBytes;
    Section section;
    section.name = decode_padded_ascii(bytes, static_cast<size_t>(cursor), 24);
    section.offset = load_u64(bytes, static_cast<size_t>(cursor + 24));
    section.length = load_u64(bytes, static_cast<size_t>(cursor + 32));
    section.stride = packet_count == 0 ? 0 : section.length / packet_count;
    sections.push_back(section);
  }
  return sections;
}

std::vector<std::string> validate_contract(uint64_t file_bytes, const Header& header, const std::vector<Section>& sections) {
  std::vector<std::string> blockers;
  auto expect = [&](bool condition, const std::string& message) {
    if (!condition) {
      blockers.push_back(message);
    }
  };
  expect(header.magic == "PJP1", "bad magic");
  expect(header.schema == kSchemaVersion, "schema version mismatch");
  expect(header.endian == kEndianMarker, "endian marker mismatch");
  expect(header.header_len == kHeaderBytes, "header length mismatch");
  expect(header.packet_len == kPacketLen, "packet length mismatch");
  expect(header.jl_dim == kJlDim, "JL dimension mismatch");
  expect(header.embedding_dim == kEmbedDim, "embedding dimension mismatch");
  expect(header.packet_count > 0, "packet count must be positive");
  expect(header.slot_count == header.packet_count * kPacketLen, "slot count mismatch");
  expect(header.section_count == kSectionCount, "section count mismatch");

  std::map<std::string, Section> section_by_name;
  for (const auto& section : sections) {
    section_by_name[section.name] = section;
  }
  for (const auto& spec : kExpectedSections) {
    const auto found = section_by_name.find(std::string(spec.name));
    if (found == section_by_name.end()) {
      blockers.push_back("missing section " + std::string(spec.name));
      continue;
    }
    const Section& section = found->second;
    expect(section.stride == spec.stride, std::string(spec.name) + " stride mismatch");
    expect(section.length == header.packet_count * spec.stride, std::string(spec.name) + " length mismatch");
    expect(section.offset >= kHeaderBytes, std::string(spec.name) + " overlaps header");
    expect(section.offset + section.length <= file_bytes, std::string(spec.name) + " exceeds file size");
  }

  std::vector<std::pair<uint64_t, uint64_t>> ranges;
  ranges.reserve(sections.size());
  uint64_t max_end = kHeaderBytes;
  for (const auto& section : sections) {
    ranges.push_back({section.offset, section.offset + section.length});
    max_end = std::max(max_end, section.offset + section.length);
  }
  std::sort(ranges.begin(), ranges.end());
  for (size_t index = 1; index < ranges.size(); ++index) {
    expect(ranges[index - 1].second <= ranges[index].first, "sections overlap");
  }
  expect(file_bytes == max_end, "file size does not match section table end");
  return blockers;
}

const Section& require_section(const std::vector<Section>& sections, std::string_view name) {
  for (const auto& section : sections) {
    if (section.name == name) {
      return section;
    }
  }
  fail("validated section missing: " + std::string(name));
}

void read_exact(std::ifstream& in, uint64_t offset, uint8_t* dst, size_t bytes) {
  in.seekg(static_cast<std::streamoff>(offset), std::ios::beg);
  if (!in) {
    fail("seek failed while reading PJP1");
  }
  in.read(reinterpret_cast<char*>(dst), static_cast<std::streamsize>(bytes));
  if (in.gcount() != static_cast<std::streamsize>(bytes)) {
    fail("short read while reading PJP1 polar section");
  }
}

int popcount8(uint8_t value) {
#if defined(__GNUC__) || defined(__clang__)
  return __builtin_popcount(static_cast<unsigned int>(value));
#else
  int count = 0;
  while (value != 0) {
    count += value & 1U;
    value >>= 1U;
  }
  return count;
#endif
}

void unpack_lsb_i8(const uint8_t* packed, size_t packed_bytes, int8_t* unpacked) {
  size_t out = 0;
  for (size_t byte_index = 0; byte_index < packed_bytes; ++byte_index) {
    const uint8_t byte = packed[byte_index];
    for (int bit = 0; bit < 8; ++bit) {
      unpacked[out++] = ((byte >> bit) & 1U) ? int8_t{1} : int8_t{-1};
    }
  }
}

int32_t dot_i8(const int8_t* lhs, const int8_t* rhs, size_t slot) {
  const size_t start = slot * kJlDim;
  int32_t acc = 0;
  for (size_t k = 0; k < kJlDim; ++k) {
    acc += static_cast<int32_t>(lhs[start + k]) * static_cast<int32_t>(rhs[start + k]);
  }
  return acc;
}

int32_t dot_oracle(const uint8_t* lhs, const uint8_t* rhs, size_t slot) {
  const size_t start = slot * (kJlDim / 8);
  int hamming = 0;
  for (size_t byte = 0; byte < (kJlDim / 8); ++byte) {
    hamming += popcount8(static_cast<uint8_t>(lhs[start + byte] ^ rhs[start + byte]));
  }
  return static_cast<int32_t>(kJlDim) - 2 * hamming;
}

std::string render_json(const Options& options,
                        const Header& header,
                        const std::vector<std::string>& blockers,
                        uint64_t file_bytes,
                        uint64_t batches_processed,
                        uint64_t active_packets,
                        uint64_t oracle_mismatches,
                        double contract_parse_sec,
                        double staging_sec,
                        double total_sec) {
  const uint64_t bitpacked_bytes = active_packets * 2 * kPolarStride;
  const uint64_t i8_bytes = active_packets * 2 * kI8SignsPerPacket;
  const uint64_t slots_checked = active_packets * kPacketLen;
  const bool pass = blockers.empty() && oracle_mismatches == 0;
  const double packets_per_sec = staging_sec > 0.0 ? static_cast<double>(active_packets) / staging_sec : 0.0;
  const double slots_per_sec = staging_sec > 0.0 ? static_cast<double>(slots_checked) / staging_sec : 0.0;
  const double bitpacked_bytes_per_sec = staging_sec > 0.0 ? static_cast<double>(bitpacked_bytes) / staging_sec : 0.0;
  const double i8_bytes_per_sec = staging_sec > 0.0 ? static_cast<double>(i8_bytes) / staging_sec : 0.0;

  std::ostringstream out;
  out << "{";
  out << "\"schema_version\":\"polar_phase34_pjp1_i8_staging_bench_v1\",";
  out << "\"created_at_utc\":\"" << utc_now() << "\",";
  out << "\"status\":\"" << (pass ? "pass" : "fail") << "\",";
  out << "\"phase3_ready_claim\":false,";
  out << "\"nonclaims\":[\"no_npu_execution\",\"no_gpu_execution\",\"no_learning_claim\",\"no_phase3_readiness_claim\",\"no_raw_tensor_output\"],";
  out << "\"source_pjp1_path\":\"" << json_escape(options.pjp1_path) << "\",";
  out << "\"bytes\":" << file_bytes << ",";
  out << "\"pjp1\":{\"bytes\":" << file_bytes << ",\"packet_count\":" << header.packet_count << "},";
  out << "\"header\":{\"packet_count\":" << header.packet_count << ",\"source_record_count\":" << header.source_record_count
      << ",\"source_token_count\":" << header.source_token_count << ",\"slot_count\":" << header.slot_count << "},";
  out << "\"config\":{\"batch_packets\":" << options.batch_packets << ",\"max_batches\":" << options.max_batches
      << ",\"packet_len\":" << kPacketLen << ",\"jl_dim\":" << kJlDim << "},";
  out << "\"batch_count\":" << batches_processed << ",";
  out << "\"processed_packets\":" << active_packets << ",";
  out << "\"slots_checked\":" << slots_checked << ",";
  out << "\"bytes_read_bitpacked\":" << bitpacked_bytes << ",";
  out << "\"bytes_written_i8\":" << i8_bytes << ",";
  out << "\"expansion_ratio\":8,";
  out << "\"qnn_input_shape\":[" << options.batch_packets << "," << kPacketLen << "," << kJlDim << "],";
  out << "\"oracle_mismatches\":" << oracle_mismatches << ",";
  out << "\"elapsed_timings\":{\"contract_parse_sec\":" << contract_parse_sec << ",\"staging_and_oracle_sec\":"
      << staging_sec << ",\"total_sec\":" << total_sec << "},";
  out << "\"throughput\":{\"packets_per_sec\":" << packets_per_sec << ",\"slots_per_sec\":" << slots_per_sec
      << ",\"bitpacked_bytes_per_sec\":" << bitpacked_bytes_per_sec << ",\"i8_bytes_per_sec\":" << i8_bytes_per_sec
      << "},";
  out << "\"staging\":{\"batches_processed\":" << batches_processed << ",\"active_packets\":" << active_packets
      << ",\"bytes_read_bitpacked\":" << bitpacked_bytes << ",\"bytes_written_i8_model\":" << i8_bytes
      << ",\"i8_vs_bitpacked_ratio\":8,\"oracle_mismatches\":" << oracle_mismatches << "},";
  out << "\"timing\":{\"elapsed_sec\":" << staging_sec << ",\"packets_per_sec\":" << packets_per_sec
      << ",\"bitpacked_bytes_per_sec\":" << bitpacked_bytes_per_sec << ",\"i8_model_bytes_per_sec\":"
      << i8_bytes_per_sec << "},";
  out << "\"blockers\":[";
  for (size_t i = 0; i < blockers.size(); ++i) {
    if (i != 0) {
      out << ",";
    }
    out << "\"" << json_escape(blockers[i]) << "\"";
  }
  out << "]}";
  return out.str();
}

int run(const Options& options) {
  const auto total_start = std::chrono::steady_clock::now();
  const auto contract_start = std::chrono::steady_clock::now();
  const auto raw_file_bytes = std::filesystem::file_size(options.pjp1_path);
  if (raw_file_bytes > std::numeric_limits<uint64_t>::max()) {
    fail("PJP1 file size exceeds uint64");
  }
  const uint64_t file_bytes = static_cast<uint64_t>(raw_file_bytes);
  std::ifstream in(options.pjp1_path, std::ios::binary);
  if (!in) {
    fail("unable to open PJP1 file: " + options.pjp1_path);
  }
  std::array<uint8_t, kHeaderBytes> header_bytes{};
  in.read(reinterpret_cast<char*>(header_bytes.data()), static_cast<std::streamsize>(header_bytes.size()));
  if (in.gcount() != static_cast<std::streamsize>(header_bytes.size())) {
    fail("truncated PJP1 header");
  }
  const Header header = parse_header(header_bytes);
  const auto sections = parse_sections(header_bytes, header.packet_count);
  auto blockers = validate_contract(file_bytes, header, sections);
  const auto contract_end = std::chrono::steady_clock::now();

  uint64_t batches_processed = 0;
  uint64_t active_packets = 0;
  uint64_t oracle_mismatches = 0;
  double staging_sec = 0.0;
  if (blockers.empty()) {
    const Section& input = require_section(sections, "input_polar");
    const Section& target = require_section(sections, "target_polar");
    uint64_t requested_packets = 0;
    uint64_t batch_packed_capacity = 0;
    uint64_t batch_i8_capacity = 0;
    if (!checked_mul(options.batch_packets, options.max_batches, requested_packets)) {
      fail("--batch-packets * --max-batches overflows uint64");
    }
    if (!checked_mul(options.batch_packets, kPolarStride, batch_packed_capacity)) {
      fail("batch bitpacked staging buffer size overflows uint64");
    }
    if (!checked_mul(options.batch_packets, kI8SignsPerPacket, batch_i8_capacity)) {
      fail("batch i8 staging buffer size overflows uint64");
    }
    const uint64_t packets_to_process = std::min(header.packet_count, requested_packets);
    std::vector<uint8_t> input_packed(checked_size(batch_packed_capacity, "input bitpacked staging buffer"));
    std::vector<uint8_t> target_packed(checked_size(batch_packed_capacity, "target bitpacked staging buffer"));
    std::vector<int8_t> input_i8(checked_size(batch_i8_capacity, "input i8 staging buffer"));
    std::vector<int8_t> target_i8(checked_size(batch_i8_capacity, "target i8 staging buffer"));

    const auto start = std::chrono::steady_clock::now();
    while (active_packets < packets_to_process) {
      const uint64_t packet_cursor = active_packets;
      const uint64_t batch_packets = std::min(options.batch_packets, packets_to_process - packet_cursor);
      const uint64_t batch_packed_bytes = batch_packets * kPolarStride;
      const size_t batch_packed_size = checked_size(batch_packed_bytes, "active bitpacked batch");
      read_exact(in, input.offset + packet_cursor * input.stride, input_packed.data(), batch_packed_size);
      read_exact(in, target.offset + packet_cursor * target.stride, target_packed.data(), batch_packed_size);
      unpack_lsb_i8(input_packed.data(), batch_packed_size, input_i8.data());
      unpack_lsb_i8(target_packed.data(), batch_packed_size, target_i8.data());

      for (uint64_t packet = 0; packet < batch_packets; ++packet) {
        for (uint64_t slot = 0; slot < kPacketLen; ++slot) {
          const uint64_t logical_slot = packet * kPacketLen + slot;
          const size_t slot_index = checked_size(logical_slot, "logical slot");
          if (dot_i8(input_i8.data(), target_i8.data(), slot_index) !=
              dot_oracle(input_packed.data(), target_packed.data(), slot_index)) {
            ++oracle_mismatches;
          }
        }
      }
      active_packets += batch_packets;
      ++batches_processed;
    }
    const auto end = std::chrono::steady_clock::now();
    staging_sec = std::chrono::duration<double>(end - start).count();
  }

  if (oracle_mismatches != 0) {
    blockers.push_back("i8 dot mismatched bitpacked popcount oracle");
  }
  const auto total_end = std::chrono::steady_clock::now();
  const double contract_sec = std::chrono::duration<double>(contract_end - contract_start).count();
  const double total_sec = std::chrono::duration<double>(total_end - total_start).count();
  const std::string payload = render_json(
      options,
      header,
      blockers,
      file_bytes,
      batches_processed,
      active_packets,
      oracle_mismatches,
      contract_sec,
      staging_sec,
      total_sec);
  if (!options.output_path.empty()) {
    const std::filesystem::path output(options.output_path);
    if (!output.parent_path().empty()) {
      std::filesystem::create_directories(output.parent_path());
    }
    std::ofstream out(output);
    out << payload << "\n";
  }
  std::cout << payload << "\n";
  return blockers.empty() ? 0 : 1;
}

}  // namespace

int main(int argc, char** argv) {
  try {
    return run(parse_args(argc, argv));
  } catch (const std::exception& exc) {
    std::cerr << "phase34_pjp1_i8_staging_bench: " << exc.what() << "\n";
    return 2;
  }
}
