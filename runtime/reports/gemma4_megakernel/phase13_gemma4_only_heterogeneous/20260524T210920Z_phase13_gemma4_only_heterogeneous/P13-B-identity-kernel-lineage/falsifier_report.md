# P13-B Falsifier Report

- Gate status: pass.
- Valid smoke config used `google/gemma-4-E4B`, hidden size 2560, and residual adapter OpenCL lineage.
- Deliberate bad config used Qwen model id and hidden size 1536 and had to fail before training.
- The smoke uses Phase 12 smoke-scale cache only for identity instrumentation, not learning promotion.
