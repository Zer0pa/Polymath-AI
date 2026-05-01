# Tokenizer fertility audit — Qwen/Qwen2.5-1.5B

Fixture dir: `/Users/zer0palab/Polymath-AI/data/fixtures/fertility`
Threshold (PRD): 2.5x English
Recorded at: 2026-05-01T12:58:35Z

| Language | Tokens | Words | Tokens/Word | Tokens/Char | Ratio vs en |
|---|---:|---:|---:|---:|---:|
| af | 4841 | 2446 | 1.979 | 0.395 | 1.55x |
| ar | 4693 | 2099 | 2.236 | 0.468 | 1.75x |
| de | 4409 | 2313 | 1.906 | 0.328 | 1.49x |
| el | 13788 | 2469 | 5.584 | 1.001 | 4.38x |
| en | 2906 | 2279 | 1.275 | 0.260 | 1.00x |
| es | 4449 | 2749 | 1.618 | 0.326 | 1.27x |
| fr | 4537 | 2797 | 1.622 | 0.338 | 1.27x |
| hi | 12562 | 4965 | 2.530 | 1.148 | 1.98x |
| it | 4683 | 2638 | 1.775 | 0.341 | 1.39x |
| ja | 4408 | 5796 | 0.761 | 0.719 | 0.60x |
| ko | 4855 | 4606 | 1.054 | 0.896 | 0.83x |
| pt | 4126 | 2447 | 1.686 | 0.335 | 1.32x |
| ru | 5237 | 2132 | 2.456 | 0.403 | 1.93x |
| sw | 5440 | 2226 | 2.444 | 0.440 | 1.92x |
| zh | 3448 | 3853 | 0.895 | 0.720 | 0.70x |
| zu | 6128 | 1792 | 3.420 | 0.447 | 2.68x |

Falsifier `tokenizer_fertility_high`: **fail** — languages above 2.5x English fertility: {'zu': 2.681819019762069, 'el': 4.379544061434046}

## Languages above threshold
- **zu**: 2.68x — mitigation required before Phase 1A
- **el**: 4.38x — mitigation required before Phase 1A