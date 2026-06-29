# Phase 2-C NPU-Readiness Preflight Contract

Status: pass for byte-tensor preflight, not an NPU execution claim and not a Phase 3 handoff.

PJP1 exposes fixed sections: metadata, token_ids, roles, input_polar, target_polar, and pooled_answer. The Phase 3 consumer shape would be:

- token_ids: `[batch_packets, 128] uint32`
- roles: `[batch_packets, 128] uint8`
- input_polar: `[batch_packets, 128, 32] uint8 bitpack`
- target_polar: `[batch_packets, 128, 32] uint8 bitpack`
- pooled_answer: `[batch_packets, 32] uint8 bitpack`

PJP1 is sufficient as-is for byte-level staging without CPU unpacking. If a future QNN graph requires float or int8 unpacked vectors, that unpack kernel remains future Phase 3 work. Expected QNN staging copy count is one accelerator-buffer copy unless file-backed memory import is proven.

Measured CPU staging throughput: 6980.54 MB/sec over 405798912 bytes.
