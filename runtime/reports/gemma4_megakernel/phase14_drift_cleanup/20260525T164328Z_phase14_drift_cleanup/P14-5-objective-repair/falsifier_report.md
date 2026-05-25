# P14-5 Falsifier Report

P14-5 would fail if the Phase 13 label-contrastive teacher path remained the
promoted objective for the next proof. It did not: the generator now emits
`full_gemma_teacher_topk_kl_v1` with full Gemma logits, explicit teacher
provenance, and a no-runtime-teacher contract.

P14-5 would fail if the result claimed full scaled objective repair. It does
not. The pass is limited to a complete 8-sequence shard smoke; the 1024/128
scaled shard campaign is deferred.

P14-5 would fail if RunPod replaced the phone runtime data path. It did not:
RunPod was used only as an offline teacher oracle over phone-defined token
caches, and no phone training was launched.

P14-5 would fail if forbidden payloads were copied into the repository. They
were not: only JSON/text metadata is present under this report.
