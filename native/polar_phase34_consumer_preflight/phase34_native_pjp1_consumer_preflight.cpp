#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdlib>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
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
constexpr uint64_t kExpectedSectionCount = 6;

struct SectionSpec {
  std::string_view name;
  uint64_t stride;
};

constexpr std::array<SectionSpec, kExpectedSectionCount> kExpectedSections{{
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
};

struct Header {
  bool available = false;
  std::string magic;
  uint16_t schema_version = 0;
  uint16_t endian_marker = 0;
  uint32_t header_bytes = 0;
  uint32_t packet_len = 0;
  uint32_t jl_dim = 0;
  uint32_t embedding_dim = 0;
  uint64_t packet_count = 0;
  uint64_t source_record_count = 0;
  uint64_t source_real_token_count = 0;
  uint64_t slot_count = 0;
  uint32_t section_count = 0;
};

struct Section {
  std::string name;
  uint64_t offset = 0;
  uint64_t length = 0;
  uint64_t expected_stride = 0;
  uint64_t actual_stride = 0;
  bool expected = false;
  bool length_matches_stride = false;
  bool offset_align_64 = false;
  bool offset_align_128 = false;
};

struct Report {
  std::string path;
  uint64_t file_bytes = 0;
  Header header;
  std::vector<Section> sections;
  std::vector<std::string> blockers;
  bool file_size_matches_section_table = false;
  bool no_section_overlaps = false;
  bool all_section_offsets_align_64 = false;
  bool all_section_offsets_align_128 = false;
  uint64_t section_table_end = kHeaderBytes;
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
    if (value >= 0x20 && value <= 0x7e) {
      out.push_back(static_cast<char>(value));
    } else {
      out.push_back('?');
    }
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
        if (static_cast<unsigned char>(c) < 0x20) {
          out += "?";
        } else {
          out.push_back(c);
        }
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

bool checked_mul(uint64_t lhs, uint64_t rhs, uint64_t& out) {
  if (lhs != 0 && rhs > std::numeric_limits<uint64_t>::max() / lhs) {
    return false;
  }
  out = lhs * rhs;
  return true;
}

bool checked_add(uint64_t lhs, uint64_t rhs, uint64_t& out) {
  if (rhs > std::numeric_limits<uint64_t>::max() - lhs) {
    return false;
  }
  out = lhs + rhs;
  return true;
}

const SectionSpec* expected_spec(std::string_view name) {
  for (const SectionSpec& spec : kExpectedSections) {
    if (spec.name == name) {
      return &spec;
    }
  }
  return nullptr;
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
    } else if (arg == "--help" || arg == "-h") {
      std::cout << "usage: phase34_native_pjp1_consumer_preflight --pjp1 PATH [--output JSON]\n";
      std::exit(0);
    } else {
      fail("unknown argument: " + arg);
    }
  }
  if (options.pjp1_path.empty()) {
    fail("missing required --pjp1 PATH");
  }
  return options;
}

std::array<uint8_t, kHeaderBytes> read_header(const std::string& path, uint64_t file_bytes, Report& report) {
  std::array<uint8_t, kHeaderBytes> header{};
  if (file_bytes < kHeaderBytes) {
    report.blockers.push_back("truncated PJP1 header");
    return header;
  }

  std::ifstream in(path, std::ios::binary);
  if (!in) {
    fail("unable to open PJP1 file: " + path);
  }
  in.read(reinterpret_cast<char*>(header.data()), static_cast<std::streamsize>(header.size()));
  if (in.gcount() != static_cast<std::streamsize>(header.size())) {
    report.blockers.push_back("short read while loading PJP1 header");
    return header;
  }
  report.header.available = true;
  return header;
}

Header parse_header(const std::array<uint8_t, kHeaderBytes>& bytes) {
  Header header;
  header.available = true;
  header.magic = decode_padded_ascii(bytes, 0, 4);
  header.schema_version = load_u16(bytes, 4);
  header.endian_marker = load_u16(bytes, 6);
  header.header_bytes = load_u32(bytes, 8);
  header.packet_len = load_u32(bytes, 12);
  header.jl_dim = load_u32(bytes, 16);
  header.embedding_dim = load_u32(bytes, 20);
  header.packet_count = load_u64(bytes, 24);
  header.source_record_count = load_u64(bytes, 32);
  header.source_real_token_count = load_u64(bytes, 40);
  header.slot_count = load_u64(bytes, 48);
  header.section_count = load_u32(bytes, 64);
  return header;
}

std::vector<Section> parse_sections(const std::array<uint8_t, kHeaderBytes>& bytes, const Header& header) {
  std::vector<Section> sections;
  const uint64_t max_entries = (kHeaderBytes - kSectionTableOffset) / kSectionEntryBytes;
  const uint64_t parse_count = std::min<uint64_t>(header.section_count, max_entries);
  sections.reserve(static_cast<size_t>(parse_count));

  for (uint64_t index = 0; index < parse_count; ++index) {
    const size_t cursor = static_cast<size_t>(kSectionTableOffset + index * kSectionEntryBytes);
    Section section;
    section.name = decode_padded_ascii(bytes, cursor, 24);
    section.offset = load_u64(bytes, cursor + 24);
    section.length = load_u64(bytes, cursor + 32);
    section.offset_align_64 = (section.offset % 64) == 0;
    section.offset_align_128 = (section.offset % 128) == 0;

    if (const SectionSpec* spec = expected_spec(section.name)) {
      section.expected = true;
      section.expected_stride = spec->stride;
    }
    if (header.packet_count > 0 && section.length % header.packet_count == 0) {
      section.actual_stride = section.length / header.packet_count;
    }
    section.length_matches_stride = section.expected && section.actual_stride == section.expected_stride;
    sections.push_back(section);
  }
  return sections;
}

void validate_header(Report& report) {
  const Header& header = report.header;
  if (!header.available) {
    return;
  }

  if (header.magic != "PJP1") {
    report.blockers.push_back("bad PJP1 magic");
  }
  if (header.schema_version != kSchemaVersion) {
    report.blockers.push_back("schema_version=" + std::to_string(header.schema_version) + " expected 1");
  }
  if (header.endian_marker != kEndianMarker) {
    report.blockers.push_back("endian_marker=" + std::to_string(header.endian_marker) + " expected 1");
  }
  if (header.header_bytes != kHeaderBytes) {
    report.blockers.push_back("header_bytes=" + std::to_string(header.header_bytes) + " expected 4096");
  }
  if (header.packet_len != kPacketLen) {
    report.blockers.push_back("packet_len=" + std::to_string(header.packet_len) + " expected 128");
  }
  if (header.jl_dim != kJlDim) {
    report.blockers.push_back("jl_dim=" + std::to_string(header.jl_dim) + " expected 256");
  }
  if (header.embedding_dim != kEmbedDim) {
    report.blockers.push_back("embedding_dim=" + std::to_string(header.embedding_dim) + " expected 2560");
  }
  if (header.packet_count == 0) {
    report.blockers.push_back("packet_count must be positive");
  }

  uint64_t expected_slot_count = 0;
  if (!checked_mul(header.packet_count, kPacketLen, expected_slot_count)) {
    report.blockers.push_back("packet_count * packet_len overflows uint64");
  } else if (header.slot_count != expected_slot_count) {
    report.blockers.push_back("slot_count=" + std::to_string(header.slot_count) + " expected " +
                              std::to_string(expected_slot_count));
  }

  if (header.section_count != kExpectedSectionCount) {
    report.blockers.push_back("section_count=" + std::to_string(header.section_count) + " expected 6");
  }
  const uint64_t section_table_end = kSectionTableOffset + static_cast<uint64_t>(header.section_count) * kSectionEntryBytes;
  if (section_table_end > kHeaderBytes) {
    report.blockers.push_back("section table exceeds fixed 4096-byte header");
  }
}

void validate_sections(Report& report) {
  if (!report.header.available) {
    return;
  }

  std::vector<std::string> names;
  names.reserve(report.sections.size());
  for (const Section& section : report.sections) {
    names.push_back(section.name);
  }

  for (size_t index = 0; index < kExpectedSections.size(); ++index) {
    const std::string expected_name(kExpectedSections[index].name);
    const auto count = static_cast<size_t>(std::count(names.begin(), names.end(), expected_name));
    if (count == 0) {
      report.blockers.push_back("missing section: " + expected_name);
      continue;
    }
    if (count > 1) {
      report.blockers.push_back("duplicate section: " + expected_name);
    }
    if (index < report.sections.size() && report.sections[index].name != expected_name) {
      report.blockers.push_back("section[" + std::to_string(index) + "]=" + report.sections[index].name +
                                " expected " + expected_name);
    }
  }

  for (const Section& section : report.sections) {
    if (!section.expected) {
      report.blockers.push_back("unexpected section: " + section.name);
      continue;
    }
    if (section.offset < kHeaderBytes) {
      report.blockers.push_back(section.name + ".offset overlaps fixed header");
    }

    uint64_t expected_length = 0;
    if (!checked_mul(report.header.packet_count, section.expected_stride, expected_length)) {
      report.blockers.push_back(section.name + ".length expectation overflows uint64");
    } else if (section.length != expected_length) {
      report.blockers.push_back(section.name + ".length=" + std::to_string(section.length) + " expected " +
                                std::to_string(expected_length));
    }
    if (!section.length_matches_stride) {
      report.blockers.push_back(section.name + ".stride=" + std::to_string(section.actual_stride) + " expected " +
                                std::to_string(section.expected_stride));
    }

    uint64_t section_end = 0;
    if (!checked_add(section.offset, section.length, section_end)) {
      report.blockers.push_back(section.name + ".range overflows uint64");
      continue;
    }
    if (section_end > report.file_bytes) {
      report.blockers.push_back(section.name + ".range exceeds file size");
    }
  }

  report.no_section_overlaps = true;
  std::vector<std::pair<uint64_t, std::pair<uint64_t, std::string>>> ranges;
  ranges.reserve(report.sections.size());
  for (const Section& section : report.sections) {
    uint64_t section_end = 0;
    if (checked_add(section.offset, section.length, section_end)) {
      ranges.push_back({section.offset, {section_end, section.name}});
    }
  }
  std::sort(ranges.begin(), ranges.end());
  for (size_t index = 1; index < ranges.size(); ++index) {
    const uint64_t previous_end = ranges[index - 1].second.first;
    const uint64_t current_start = ranges[index].first;
    if (previous_end > current_start) {
      report.no_section_overlaps = false;
      report.blockers.push_back("sections overlap: " + ranges[index - 1].second.second + " and " +
                                ranges[index].second.second);
    }
  }

  uint64_t max_end = kHeaderBytes;
  for (const auto& range : ranges) {
    max_end = std::max(max_end, range.second.first);
  }
  report.section_table_end = max_end;
  report.file_size_matches_section_table = report.file_bytes == max_end;
  if (!report.file_size_matches_section_table) {
    report.blockers.push_back("file size " + std::to_string(report.file_bytes) + " does not equal section end " +
                              std::to_string(max_end));
  }

  report.all_section_offsets_align_64 = std::all_of(report.sections.begin(), report.sections.end(), [](const Section& section) {
    return section.offset_align_64;
  });
  report.all_section_offsets_align_128 =
      std::all_of(report.sections.begin(), report.sections.end(), [](const Section& section) {
        return section.offset_align_128;
      });
}

Report inspect_pjp1(const std::string& path) {
  Report report;
  report.path = path;

  std::error_code error;
  const auto size = std::filesystem::file_size(path, error);
  if (error) {
    report.blockers.push_back("unable to stat PJP1 file: " + error.message());
    return report;
  }
  if (size > std::numeric_limits<uint64_t>::max()) {
    report.blockers.push_back("file size exceeds uint64");
    return report;
  }
  report.file_bytes = static_cast<uint64_t>(size);

  const std::array<uint8_t, kHeaderBytes> bytes = read_header(path, report.file_bytes, report);
  if (!report.header.available) {
    return report;
  }

  report.header = parse_header(bytes);
  validate_header(report);
  report.sections = parse_sections(bytes, report.header);
  validate_sections(report);
  return report;
}

void append_string_array(std::ostream& out, const std::vector<std::string>& values) {
  out << '[';
  for (size_t index = 0; index < values.size(); ++index) {
    if (index != 0) {
      out << ',';
    }
    out << '"' << json_escape(values[index]) << '"';
  }
  out << ']';
}

void append_consumer_shape(std::ostream& out) {
  out << "\"consumer_shape\":{";
  out << "\"token_ids\":[\"batch_packets\",128,\"uint32\"],";
  out << "\"roles\":[\"batch_packets\",128,\"uint8\"],";
  out << "\"input_polar\":[\"batch_packets\",128,32,\"uint8 bitpack\"],";
  out << "\"target_polar\":[\"batch_packets\",128,32,\"uint8 bitpack\"],";
  out << "\"pooled_answer\":[\"batch_packets\",32,\"uint8 bitpack\"]";
  out << '}';
}

std::string build_json(const Report& report) {
  const bool pass = report.blockers.empty();
  std::ostringstream out;
  out << '{';
  out << "\"schema_version\":\"polar_phase34_native_pjp1_consumer_preflight_v1\",";
  out << "\"created_at_utc\":\"" << utc_now() << "\",";
  out << "\"status\":\"" << (pass ? "pass" : "fail") << "\",";
  out << "\"phase3_ready_claim\":false,";
  out << "\"nonclaims\":[\"no_npu_execution\",\"no_gpu_execution\",\"no_learning_claim\",\"no_phase3_readiness_claim\"],";
  out << "\"source_pjp1_path\":\"" << json_escape(report.path) << "\",";
  out << "\"bytes\":" << report.file_bytes << ',';
  out << "\"header_available\":" << (report.header.available ? "true" : "false") << ',';
  if (report.header.available) {
    const Header& header = report.header;
    out << "\"header\":{";
    out << "\"magic\":\"" << json_escape(header.magic) << "\",";
    out << "\"schema\":" << header.schema_version << ',';
    out << "\"endian\":" << header.endian_marker << ',';
    out << "\"header_len\":" << header.header_bytes << ',';
    out << "\"packet_len\":" << header.packet_len << ',';
    out << "\"jl_dim\":" << header.jl_dim << ',';
    out << "\"embedding_dim\":" << header.embedding_dim << ',';
    out << "\"packet_count\":" << header.packet_count << ',';
    out << "\"source_record_count\":" << header.source_record_count << ',';
    out << "\"source_token_count\":" << header.source_real_token_count << ',';
    out << "\"slot_count\":" << header.slot_count << ',';
    out << "\"section_count\":" << header.section_count;
    out << "},";
  }

  out << "\"section_table\":{\"offset\":" << kSectionTableOffset << ",\"entry_bytes\":" << kSectionEntryBytes
      << ",\"expected_entries\":" << kExpectedSectionCount << "},";
  out << "\"sections\":[";
  for (size_t index = 0; index < report.sections.size(); ++index) {
    if (index != 0) {
      out << ',';
    }
    const Section& section = report.sections[index];
    out << '{';
    out << "\"name\":\"" << json_escape(section.name) << "\",";
    out << "\"offset\":" << section.offset << ',';
    out << "\"bytes\":" << section.length << ',';
    out << "\"stride_bytes\":" << section.expected_stride << ',';
    out << "\"actual_stride_bytes\":" << section.actual_stride << ',';
    out << "\"length_matches_stride\":" << (section.length_matches_stride ? "true" : "false") << ',';
    out << "\"offset_align_64\":" << (section.offset_align_64 ? "true" : "false") << ',';
    out << "\"offset_align_128\":" << (section.offset_align_128 ? "true" : "false");
    out << '}';
  }
  out << "],";

  out << "\"preflight\":{";
  out << "\"file_size_matches_section_table\":" << (report.file_size_matches_section_table ? "true" : "false")
      << ',';
  out << "\"no_section_overlaps\":" << (report.no_section_overlaps ? "true" : "false") << ',';
  out << "\"all_section_offsets_align_64\":" << (report.all_section_offsets_align_64 ? "true" : "false")
      << ',';
  out << "\"all_section_offsets_align_128\":" << (report.all_section_offsets_align_128 ? "true" : "false")
      << ',';
  out << "\"direct_bitpacked_contract\":\"" << (pass ? "pass" : "blocked") << "\"";
  out << "},";
  append_consumer_shape(out);
  out << ',';
  out << "\"blockers\":";
  append_string_array(out, report.blockers);
  out << '}';
  return out.str();
}

void write_output(const std::string& output_path, const std::string& payload) {
  if (output_path.empty()) {
    return;
  }
  const std::filesystem::path path(output_path);
  const std::filesystem::path parent = path.parent_path();
  if (!parent.empty()) {
    std::filesystem::create_directories(parent);
  }
  std::ofstream out(path, std::ios::binary);
  if (!out) {
    fail("unable to open output JSON: " + output_path);
  }
  out << payload << '\n';
  if (!out) {
    fail("unable to write output JSON: " + output_path);
  }
}

int run(int argc, char** argv) {
  const Options options = parse_args(argc, argv);
  const Report report = inspect_pjp1(options.pjp1_path);
  const std::string payload = build_json(report);
  write_output(options.output_path, payload);
  std::cout << payload << '\n';
  return report.blockers.empty() ? 0 : 1;
}

}  // namespace

int main(int argc, char** argv) {
  try {
    return run(argc, argv);
  } catch (const std::exception& exc) {
    std::cerr << "phase34_native_pjp1_consumer_preflight: " << exc.what() << '\n';
    return 2;
  }
}
