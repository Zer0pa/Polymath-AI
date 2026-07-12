#ifndef CUR0S_SHA256_H
#define CUR0S_SHA256_H

#include <stddef.h>
#include <stdint.h>

#define CUR0S_SHA256_DIGEST_BYTES 32U
#define CUR0S_SHA256_HEX_BYTES 64U

typedef struct {
    uint32_t state[8];
    uint64_t total_bytes;
    uint8_t block[64];
    size_t block_bytes;
} cur0s_sha256_context;

void cur0s_sha256_init(cur0s_sha256_context *context);
void cur0s_sha256_update(
    cur0s_sha256_context *context,
    const void *payload,
    size_t payload_bytes
);
void cur0s_sha256_final(
    cur0s_sha256_context *context,
    uint8_t digest[CUR0S_SHA256_DIGEST_BYTES]
);
void cur0s_sha256_hex(
    const uint8_t digest[CUR0S_SHA256_DIGEST_BYTES],
    char output[CUR0S_SHA256_HEX_BYTES + 1U]
);

#endif
