#include "polymath/gemma4/gemma_bpe_tokenizer.h"

#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace polymath::gemma4 {
namespace {

constexpr std::uint32_t kBosTokenId = 2U;
constexpr std::uint32_t kUnkTokenId = 3U;

std::string join_path(const std::string& base, const std::string& leaf) {
  if (base.empty() || base.back() == '/') {
    return base + leaf;
  }
  return base + "/" + leaf;
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

std::string normalize_text(const std::string& text) {
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

std::size_t utf8_codepoint_bytes(const std::string& text, std::size_t index) {
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

std::vector<std::string> initial_symbols(const std::string& text) {
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

}  // namespace

void GemmaBpeTokenizer::load(const std::string& tokenizer_dir) {
  load_vocab(join_path(tokenizer_dir, "vocab.hex.tsv"));
  load_merges(join_path(tokenizer_dir, "merges.hex.tsv"));
}

std::vector<std::uint32_t> GemmaBpeTokenizer::encode(
    const std::string& text) const {
  std::vector<std::string> symbols = initial_symbols(normalize_text(text));
  while (symbols.size() > 1U) {
    std::uint32_t best_rank = std::numeric_limits<std::uint32_t>::max();
    std::size_t best_index = symbols.size();
    for (std::size_t index = 0U; index + 1U < symbols.size(); ++index) {
      const auto found =
          merge_ranks_.find(pair_key(symbols[index], symbols[index + 1U]));
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

void GemmaBpeTokenizer::load_vocab(const std::string& path) {
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
    vocab_[decode_hex(fields[0])] =
        static_cast<std::uint32_t>(std::stoul(fields[1]));
  }
}

void GemmaBpeTokenizer::load_merges(const std::string& path) {
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

void GemmaBpeTokenizer::append_symbol_ids(
    const std::string& symbol,
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

}  // namespace polymath::gemma4
