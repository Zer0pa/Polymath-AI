#ifndef POLYMATH_GEMMA4_GEMMA_BPE_TOKENIZER_H_
#define POLYMATH_GEMMA4_GEMMA_BPE_TOKENIZER_H_

#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>

namespace polymath::gemma4 {

class GemmaBpeTokenizer {
 public:
  void load(const std::string& tokenizer_dir);
  std::vector<std::uint32_t> encode(const std::string& text) const;
  std::string decode_token_piece(std::uint32_t token_id) const;

 private:
  void load_vocab(const std::string& path);
  void load_merges(const std::string& path);
  void append_symbol_ids(const std::string& symbol,
                         std::vector<std::uint32_t>& ids) const;

  std::unordered_map<std::string, std::uint32_t> vocab_;
  std::unordered_map<std::uint32_t, std::string> id_to_piece_;
  std::unordered_map<std::string, std::uint32_t> merge_ranks_;
};

}  // namespace polymath::gemma4

#endif  // POLYMATH_GEMMA4_GEMMA_BPE_TOKENIZER_H_
