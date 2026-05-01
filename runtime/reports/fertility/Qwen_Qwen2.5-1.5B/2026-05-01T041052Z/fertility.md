# Tokenizer fertility audit — Qwen/Qwen2.5-1.5B

Fixture dir: `/Users/zer0palab/Polymath-AI/data/fixtures/fertility`
Threshold (PRD): 2.5x English
Recorded at: 2026-05-01T04:10:52Z

| Language | Tokens | Words | Tokens/Word | Tokens/Char | Ratio vs en |
|---|---:|---:|---:|---:|---:|
| ar | 290 | 148 | 1.959 | 0.420 | 1.70x |
| de | 346 | 180 | 1.922 | 0.323 | 1.67x |
| en | 314 | 273 | 1.150 | 0.224 | 1.00x |
| es | 331 | 219 | 1.511 | 0.300 | 1.31x |
| fr | 363 | 245 | 1.482 | 0.324 | 1.29x |
| hi | 698 | 274 | 2.547 | 1.124 | 2.21x |
| ja | 301 | 450 | 0.669 | 0.669 | 0.58x |
| ko | 313 | 351 | 0.892 | 0.848 | 0.78x |
| ru | 327 | 148 | 2.209 | 0.363 | 1.92x |
| sw | 335 | 139 | 2.410 | 0.465 | 2.10x |
| zh | 193 | 283 | 0.682 | 0.656 | 0.59x |

Falsifier `tokenizer_fertility_high`: **pass** — 11 languages all at or below 2.5x