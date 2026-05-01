# Tokenizer fertility audit — HuggingFaceTB/SmolLM3-3B

Fixture dir: `/Users/zer0palab/Polymath-AI/data/fixtures/fertility`
Threshold (PRD): 2.5x English
Recorded at: 2026-05-01T04:11:10Z

| Language | Tokens | Words | Tokens/Word | Tokens/Char | Ratio vs en |
|---|---:|---:|---:|---:|---:|
| ar | 301 | 148 | 2.034 | 0.436 | 1.77x |
| de | 348 | 180 | 1.933 | 0.325 | 1.68x |
| en | 314 | 273 | 1.150 | 0.224 | 1.00x |
| es | 335 | 219 | 1.530 | 0.303 | 1.33x |
| fr | 367 | 245 | 1.498 | 0.327 | 1.30x |
| hi | 385 | 274 | 1.405 | 0.620 | 1.22x |
| ja | 332 | 450 | 0.738 | 0.738 | 0.64x |
| ko | 300 | 351 | 0.855 | 0.813 | 0.74x |
| ru | 303 | 148 | 2.047 | 0.337 | 1.78x |
| sw | 334 | 139 | 2.403 | 0.463 | 2.09x |
| zh | 265 | 283 | 0.936 | 0.901 | 0.81x |

Falsifier `tokenizer_fertility_high`: **pass** — 11 languages all at or below 2.5x