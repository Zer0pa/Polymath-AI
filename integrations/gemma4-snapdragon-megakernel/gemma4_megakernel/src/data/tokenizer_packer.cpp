#include "polymath/gemma4/data_pipeline.h"

#include <sys/stat.h>

#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include "polymath/gemma4/json_writer.h"
#include "polymath/gemma4/sha256.h"

namespace polymath::gemma4 {
namespace {

constexpr std::uint32_t kPadTokenId = 0U;
constexpr std::uint32_t kBosTokenId = 2U;
constexpr std::uint32_t kUnkTokenId = 3U;

std::string join_path(const std::string& base, const std::string& leaf) {
  if (base.empty() || base.back() == '/') {
    return base + leaf;
  }
  return base + "/" + leaf;
}

void ensure_directory(const std::string& path) {
  std::string partial;
  for (char character : path) {
    partial.push_back(character);
    if (character == '/' && partial.size() > 1U) {
      mkdir(partial.c_str(), 0755);
    }
  }
  if (!path.empty()) {
    mkdir(path.c_str(), 0755);
  }
}

std::string read_text_file(const std::string& path) {
  std::ifstream file(path, std::ios::binary);
  if (!file) {
    throw std::runtime_error("unable to open " + path);
  }
  std::ostringstream buffer;
  buffer << file.rdbuf();
  return buffer.str();
}

template <typename T>
void write_binary_vector(const std::string& path, const std::vector<T>& values) {
  std::ofstream file(path, std::ios::binary);
  if (!file) {
    throw std::runtime_error("unable to create " + path);
  }
  file.write(reinterpret_cast<const char*>(values.data()),
             static_cast<std::streamsize>(values.size() * sizeof(T)));
  if (!file) {
    throw std::runtime_error("unable to write " + path);
  }
}

std::uint8_t hex_value(char character) {
  if (character >= '0' && character <= '9') {
    return static_cast<std::uint8_t>(character - '0');
  }
  if (character >= 'a' && character <= 'f') {
    return static_cast<std::uint8_t>(10 + character - 'a');
  }
  if (character >= 'A' && character <= 'F') {
    return static_cast<std::uint8_t>(10 + character - 'A');
  }
  throw std::runtime_error("invalid hex character in tokenizer table");
}

std::string decode_hex(const std::string& hex) {
  if ((hex.size() % 2U) != 0U) {
    throw std::runtime_error("odd-length hex token in tokenizer table");
  }
  std::string output;
  output.reserve(hex.size() / 2U);
  for (std::size_t index = 0U; index < hex.size(); index += 2U) {
    const std::uint8_t byte =
        static_cast<std::uint8_t>((hex_value(hex[index]) << 4U) |
                                  hex_value(hex[index + 1U]));
    output.push_back(static_cast<char>(byte));
  }
  return output;
}

std::string pair_key(const std::string& left, const std::string& right) {
  return std::to_string(left.size()) + ":" + left + right;
}

std::vector<std::string> split_tab_line(const std::string& line) {
  std::vector<std::string> fields;
  std::size_t start = 0U;
  while (start <= line.size()) {
    const std::size_t tab = line.find('\t', start);
    if (tab == std::string::npos) {
      fields.push_back(line.substr(start));
      break;
    }
    fields.push_back(line.substr(start, tab - start));
    start = tab + 1U;
  }
  return fields;
}

class GemmaBpeTokenizer {
 public:
  void load(const std::string& tokenizer_dir) {
    load_vocab(join_path(tokenizer_dir, "vocab.hex.tsv"));
    load_merges(join_path(tokenizer_dir, "merges.hex.tsv"));
  }

  std::vector<std::uint32_t> encode(const std::string& text) const {
    std::vector<std::string> symbols = initial_symbols(normalize(text));
    while (symbols.size() > 1U) {
      std::uint32_t best_rank = std::numeric_limits<std::uint32_t>::max();
      std::size_t best_index = symbols.size();
      for (std::size_t index = 0U; index + 1U < symbols.size(); ++index) {
        const auto found = merge_ranks_.find(pair_key(symbols[index], symbols[index + 1U]));
        if (found != merge_ranks_.end() && found->second < best_rank) {
          best_rank = found->second;
          best_index = index;
        }
      }
      if (best_index == symbols.size()) {
        break;
      }
      symbols[best_index] += symbols[best_index + 1U];
      symbols.erase(symbols.begin() + static_cast<std::ptrdiff_t>(best_index + 1U));
    }

    std::vector<std::uint32_t> ids;
    ids.reserve(symbols.size() + 1U);
    ids.push_back(kBosTokenId);
    for (const std::string& symbol : symbols) {
      append_symbol_ids(symbol, ids);
    }
    return ids;
  }

 private:
  void load_vocab(const std::string& path) {
    std::ifstream file(path);
    if (!file) {
      throw std::runtime_error("unable to open " + path);
    }
    std::string line;
    while (std::getline(file, line)) {
      if (line.empty()) {
        continue;
      }
      const std::vector<std::string> fields = split_tab_line(line);
      if (fields.size() != 2U) {
        throw std::runtime_error("malformed vocab line in " + path);
      }
      vocab_[decode_hex(fields[0])] = static_cast<std::uint32_t>(std::stoul(fields[1]));
    }
  }

  void load_merges(const std::string& path) {
    std::ifstream file(path);
    if (!file) {
      throw std::runtime_error("unable to open " + path);
    }
    std::string line;
    while (std::getline(file, line)) {
      if (line.empty()) {
        continue;
      }
      const std::vector<std::string> fields = split_tab_line(line);
      if (fields.size() != 3U) {
        throw std::runtime_error("malformed merge line in " + path);
      }
      const std::string left = decode_hex(fields[0]);
      const std::string right = decode_hex(fields[1]);
      merge_ranks_[pair_key(left, right)] =
          static_cast<std::uint32_t>(std::stoul(fields[2]));
    }
  }

  static std::string normalize(const std::string& text) {
    std::string output;
    output.reserve(text.size());
    for (const char character : text) {
      if (character == ' ') {
        output += "\xE2\x96\x81";
      } else {
        output.push_back(character);
      }
    }
    return output;
  }

  static std::size_t utf8_codepoint_bytes(const std::string& text, std::size_t index) {
    const auto byte = static_cast<unsigned char>(text[index]);
    if ((byte & 0x80U) == 0U) {
      return 1U;
    }
    if ((byte & 0xE0U) == 0xC0U) {
      return 2U;
    }
    if ((byte & 0xF0U) == 0xE0U) {
      return 3U;
    }
    if ((byte & 0xF8U) == 0xF0U) {
      return 4U;
    }
    return 1U;
  }

  static std::vector<std::string> initial_symbols(const std::string& text) {
    std::vector<std::string> symbols;
    std::size_t index = 0U;
    while (index < text.size()) {
      const std::size_t width = std::min(utf8_codepoint_bytes(text, index),
                                         text.size() - index);
      symbols.push_back(text.substr(index, width));
      index += width;
    }
    return symbols;
  }

  void append_symbol_ids(const std::string& symbol,
                         std::vector<std::uint32_t>& ids) const {
    const auto found = vocab_.find(symbol);
    if (found != vocab_.end()) {
      ids.push_back(found->second);
      return;
    }
    for (const unsigned char byte : symbol) {
      std::ostringstream byte_token;
      byte_token << "<0x" << std::uppercase << std::hex << std::setw(2)
                 << std::setfill('0') << static_cast<int>(byte) << ">";
      const auto fallback = vocab_.find(byte_token.str());
      ids.push_back(fallback == vocab_.end() ? kUnkTokenId : fallback->second);
    }
  }

  std::unordered_map<std::string, std::uint32_t> vocab_;
  std::unordered_map<std::string, std::uint32_t> merge_ranks_;
};

std::vector<std::string> select_texts(const std::string& raw_text,
                                      std::uint32_t max_sequences) {
  std::vector<std::string> texts;
  std::istringstream stream(raw_text);
  std::string line;
  bool first_line = true;
  while (std::getline(stream, line) && texts.size() < max_sequences) {
    if (!line.empty() && line.back() == '\r') {
      line.pop_back();
    }
    if (first_line && line.rfind("act,prompt", 0U) == 0U) {
      first_line = false;
      continue;
    }
    first_line = false;
    if (!line.empty()) {
      texts.push_back(line);
    }
  }
  if (texts.empty()) {
    throw std::runtime_error("no non-empty texts selected from raw stream");
  }
  return texts;
}

void write_texts(const std::string& path, const std::vector<std::string>& texts) {
  std::ofstream file(path);
  if (!file) {
    throw std::runtime_error("unable to create " + path);
  }
  for (const std::string& text : texts) {
    file << text << '\n';
  }
}

void write_manifest(const std::string& output_cache_dir,
                    const std::string& tokenizer_dir,
                    const std::string& raw_text_path,
                    const std::string& source_url,
                    std::uint32_t sequence_length,
                    std::uint32_t sequence_count,
                    std::uint64_t non_pad_tokens) {
  std::ofstream file(join_path(output_cache_dir, "manifest.json"));
  if (!file) {
    throw std::runtime_error("unable to create token cache manifest");
  }
  file << "{\n";
  file << "  \"schema_version\": \"gemma4_phone_token_pack_v1\",\n";
  file << "  \"model_id\": \"google/gemma-4-E4B\",\n";
  file << "  \"revision\": \"7aa32e6889efd6300124851b164f8b364314c3d8\",\n";
  file << "  \"tokenizer\": \"native_cpp_bpe_from_tokenizer_json_tables\",\n";
  file << "  \"source_url\": ";
  write_json_string(file, source_url);
  file << ",\n";
  file << "  \"raw_text_sha256\": ";
  write_json_string(file, sha256_file_hex(raw_text_path));
  file << ",\n";
  file << "  \"vocab_sha256\": ";
  write_json_string(file, sha256_file_hex(join_path(tokenizer_dir, "vocab.hex.tsv")));
  file << ",\n";
  file << "  \"merges_sha256\": ";
  write_json_string(file, sha256_file_hex(join_path(tokenizer_dir, "merges.hex.tsv")));
  file << ",\n";
  file << "  \"sequence_length\": " << sequence_length << ",\n";
  file << "  \"sequence_count\": " << sequence_count << ",\n";
  file << "  \"non_pad_tokens\": " << non_pad_tokens << ",\n";
  file << "  \"input_ids_sha256\": ";
  write_json_string(file, sha256_file_hex(join_path(output_cache_dir, "input_ids.u32.bin")));
  file << ",\n";
  file << "  \"attention_mask_sha256\": ";
  write_json_string(file, sha256_file_hex(join_path(output_cache_dir, "attention_mask.u8.bin")));
  file << ",\n";
  file << "  \"selected_text_sha256\": ";
  write_json_string(file, sha256_file_hex(join_path(output_cache_dir, "selected_text.txt")));
  file << "\n}\n";
}

}  // namespace

Status run_tokenize_pack(const std::string& tokenizer_dir,
                         const std::string& raw_text_path,
                         const std::string& output_cache_dir,
                         std::uint32_t sequence_length,
                         std::uint32_t max_sequences,
                         const std::string& source_url) {
  try {
    if (sequence_length == 0U || max_sequences == 0U) {
      return Status::invalid("sequence length and max sequences must be positive");
    }
    ensure_directory(output_cache_dir);
    GemmaBpeTokenizer tokenizer;
    tokenizer.load(tokenizer_dir);
    const std::vector<std::string> texts =
        select_texts(read_text_file(raw_text_path), max_sequences);
    write_texts(join_path(output_cache_dir, "selected_text.txt"), texts);

    std::vector<std::uint32_t> input_ids(texts.size() * sequence_length, kPadTokenId);
    std::vector<std::uint8_t> attention_mask(texts.size() * sequence_length, 0U);
    std::uint64_t non_pad_tokens = 0U;
    for (std::size_t row = 0U; row < texts.size(); ++row) {
      std::vector<std::uint32_t> ids = tokenizer.encode(texts[row]);
      if (ids.size() > sequence_length) {
        ids.resize(sequence_length);
      }
      non_pad_tokens += ids.size();
      const std::size_t start = sequence_length - ids.size();
      for (std::size_t col = 0U; col < ids.size(); ++col) {
        input_ids[(row * sequence_length) + start + col] = ids[col];
        attention_mask[(row * sequence_length) + start + col] = 1U;
      }
    }

    write_binary_vector(join_path(output_cache_dir, "input_ids.u32.bin"), input_ids);
    write_binary_vector(join_path(output_cache_dir, "attention_mask.u8.bin"), attention_mask);
    write_manifest(output_cache_dir, tokenizer_dir, raw_text_path, source_url,
                   sequence_length, static_cast<std::uint32_t>(texts.size()),
                   non_pad_tokens);
    return Status::ok();
  } catch (const std::exception& error) {
    return Status::invalid(error.what());
  }
}

}  // namespace polymath::gemma4
