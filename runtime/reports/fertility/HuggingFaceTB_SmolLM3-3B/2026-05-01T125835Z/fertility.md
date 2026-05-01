# Tokenizer fertility audit — HuggingFaceTB/SmolLM3-3B

Fixture dir: `/Users/zer0palab/Polymath-AI/data/fixtures/fertility`
Threshold (PRD): 2.5x English
Recorded at: 2026-05-01T12:58:35Z

| Language | Tokens | Words | Tokens/Word | Tokens/Char | Ratio vs en |
|---|---:|---:|---:|---:|---:|
| af | 4744 | 2446 | 1.939 | 0.387 | 1.57x |
| ar | 4659 | 2099 | 2.220 | 0.465 | 1.79x |
| de | 4348 | 2313 | 1.880 | 0.323 | 1.52x |
| el | 6306 | 2469 | 2.554 | 0.458 | 2.06x |
| en | 2824 | 2279 | 1.239 | 0.253 | 1.00x |
| es | 4399 | 2749 | 1.600 | 0.323 | 1.29x |
| fr | 4482 | 2797 | 1.602 | 0.334 | 1.29x |
| hi | 7117 | 4965 | 1.433 | 0.650 | 1.16x |
| it | 4606 | 2638 | 1.746 | 0.336 | 1.41x |
| ja | 4446 | 5796 | 0.767 | 0.726 | 0.62x |
| ko | 4279 | 4606 | 0.929 | 0.790 | 0.75x |
| pt | 4096 | 2447 | 1.674 | 0.332 | 1.35x |
| ru | 4758 | 2132 | 2.232 | 0.366 | 1.80x |
| sw | 5317 | 2226 | 2.389 | 0.430 | 1.93x |
| zh | 4015 | 3853 | 1.042 | 0.838 | 0.84x |
| zu | 6023 | 1792 | 3.361 | 0.440 | 2.71x |

Falsifier `tokenizer_fertility_high`: **fail** — languages above 2.5x English fertility: {'zu': 2.7124047150065764}

## Languages above threshold
- **zu**: 2.71x — mitigation required before Phase 1A