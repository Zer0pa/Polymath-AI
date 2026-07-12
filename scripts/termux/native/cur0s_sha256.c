#include "cur0s_sha256.h"

#include <string.h>

static const uint32_t ROUND_CONSTANTS[64] = {
    0x428a2f98U, 0x71374491U, 0xb5c0fbcfU, 0xe9b5dba5U,
    0x3956c25bU, 0x59f111f1U, 0x923f82a4U, 0xab1c5ed5U,
    0xd807aa98U, 0x12835b01U, 0x243185beU, 0x550c7dc3U,
    0x72be5d74U, 0x80deb1feU, 0x9bdc06a7U, 0xc19bf174U,
    0xe49b69c1U, 0xefbe4786U, 0x0fc19dc6U, 0x240ca1ccU,
    0x2de92c6fU, 0x4a7484aaU, 0x5cb0a9dcU, 0x76f988daU,
    0x983e5152U, 0xa831c66dU, 0xb00327c8U, 0xbf597fc7U,
    0xc6e00bf3U, 0xd5a79147U, 0x06ca6351U, 0x14292967U,
    0x27b70a85U, 0x2e1b2138U, 0x4d2c6dfcU, 0x53380d13U,
    0x650a7354U, 0x766a0abbU, 0x81c2c92eU, 0x92722c85U,
    0xa2bfe8a1U, 0xa81a664bU, 0xc24b8b70U, 0xc76c51a3U,
    0xd192e819U, 0xd6990624U, 0xf40e3585U, 0x106aa070U,
    0x19a4c116U, 0x1e376c08U, 0x2748774cU, 0x34b0bcb5U,
    0x391c0cb3U, 0x4ed8aa4aU, 0x5b9cca4fU, 0x682e6ff3U,
    0x748f82eeU, 0x78a5636fU, 0x84c87814U, 0x8cc70208U,
    0x90befffaU, 0xa4506cebU, 0xbef9a3f7U, 0xc67178f2U,
};

static uint32_t rotate_right(uint32_t value, unsigned int shift) {
    return (value >> shift) | (value << (32U - shift));
}

static uint32_t load_big_endian_u32(const uint8_t *input) {
    return ((uint32_t)input[0] << 24U)
        | ((uint32_t)input[1] << 16U)
        | ((uint32_t)input[2] << 8U)
        | (uint32_t)input[3];
}

static void store_big_endian_u32(uint8_t *output, uint32_t value) {
    output[0] = (uint8_t)(value >> 24U);
    output[1] = (uint8_t)(value >> 16U);
    output[2] = (uint8_t)(value >> 8U);
    output[3] = (uint8_t)value;
}

static void transform(cur0s_sha256_context *context, const uint8_t block[64]) {
    uint32_t schedule[64];
    uint32_t a;
    uint32_t b;
    uint32_t c;
    uint32_t d;
    uint32_t e;
    uint32_t f;
    uint32_t g;
    uint32_t h;

    for (size_t index = 0; index < 16U; ++index) {
        schedule[index] = load_big_endian_u32(block + (index * 4U));
    }
    for (size_t index = 16U; index < 64U; ++index) {
        uint32_t previous_15 = schedule[index - 15U];
        uint32_t previous_2 = schedule[index - 2U];
        uint32_t sigma0 = rotate_right(previous_15, 7U)
            ^ rotate_right(previous_15, 18U)
            ^ (previous_15 >> 3U);
        uint32_t sigma1 = rotate_right(previous_2, 17U)
            ^ rotate_right(previous_2, 19U)
            ^ (previous_2 >> 10U);
        schedule[index] = schedule[index - 16U] + sigma0
            + schedule[index - 7U] + sigma1;
    }

    a = context->state[0];
    b = context->state[1];
    c = context->state[2];
    d = context->state[3];
    e = context->state[4];
    f = context->state[5];
    g = context->state[6];
    h = context->state[7];

    for (size_t index = 0; index < 64U; ++index) {
        uint32_t uppercase_sigma1 = rotate_right(e, 6U)
            ^ rotate_right(e, 11U)
            ^ rotate_right(e, 25U);
        uint32_t choice = (e & f) ^ ((~e) & g);
        uint32_t temporary1 = h + uppercase_sigma1 + choice
            + ROUND_CONSTANTS[index] + schedule[index];
        uint32_t uppercase_sigma0 = rotate_right(a, 2U)
            ^ rotate_right(a, 13U)
            ^ rotate_right(a, 22U);
        uint32_t majority = (a & b) ^ (a & c) ^ (b & c);
        uint32_t temporary2 = uppercase_sigma0 + majority;

        h = g;
        g = f;
        f = e;
        e = d + temporary1;
        d = c;
        c = b;
        b = a;
        a = temporary1 + temporary2;
    }

    context->state[0] += a;
    context->state[1] += b;
    context->state[2] += c;
    context->state[3] += d;
    context->state[4] += e;
    context->state[5] += f;
    context->state[6] += g;
    context->state[7] += h;
}

void cur0s_sha256_init(cur0s_sha256_context *context) {
    static const uint32_t initial_state[8] = {
        0x6a09e667U,
        0xbb67ae85U,
        0x3c6ef372U,
        0xa54ff53aU,
        0x510e527fU,
        0x9b05688cU,
        0x1f83d9abU,
        0x5be0cd19U,
    };

    memcpy(context->state, initial_state, sizeof(initial_state));
    context->total_bytes = 0U;
    context->block_bytes = 0U;
    memset(context->block, 0, sizeof(context->block));
}

void cur0s_sha256_update(
    cur0s_sha256_context *context,
    const void *payload,
    size_t payload_bytes
) {
    const uint8_t *cursor = (const uint8_t *)payload;

    context->total_bytes += (uint64_t)payload_bytes;
    while (payload_bytes > 0U) {
        size_t available = sizeof(context->block) - context->block_bytes;
        size_t copied = payload_bytes < available ? payload_bytes : available;

        memcpy(context->block + context->block_bytes, cursor, copied);
        context->block_bytes += copied;
        cursor += copied;
        payload_bytes -= copied;
        if (context->block_bytes == sizeof(context->block)) {
            transform(context, context->block);
            context->block_bytes = 0U;
        }
    }
}

void cur0s_sha256_final(
    cur0s_sha256_context *context,
    uint8_t digest[CUR0S_SHA256_DIGEST_BYTES]
) {
    uint64_t total_bits = context->total_bytes * 8U;

    context->block[context->block_bytes++] = 0x80U;
    if (context->block_bytes > 56U) {
        memset(
            context->block + context->block_bytes,
            0,
            sizeof(context->block) - context->block_bytes
        );
        transform(context, context->block);
        context->block_bytes = 0U;
    }
    memset(context->block + context->block_bytes, 0, 56U - context->block_bytes);
    for (size_t index = 0; index < 8U; ++index) {
        context->block[63U - index] = (uint8_t)(total_bits >> (index * 8U));
    }
    transform(context, context->block);

    for (size_t index = 0; index < 8U; ++index) {
        store_big_endian_u32(digest + (index * 4U), context->state[index]);
    }
    memset(context, 0, sizeof(*context));
}

void cur0s_sha256_hex(
    const uint8_t digest[CUR0S_SHA256_DIGEST_BYTES],
    char output[CUR0S_SHA256_HEX_BYTES + 1U]
) {
    static const char hex_digits[] = "0123456789abcdef";

    for (size_t index = 0; index < CUR0S_SHA256_DIGEST_BYTES; ++index) {
        output[index * 2U] = hex_digits[digest[index] >> 4U];
        output[(index * 2U) + 1U] = hex_digits[digest[index] & 0x0fU];
    }
    output[CUR0S_SHA256_HEX_BYTES] = '\0';
}
