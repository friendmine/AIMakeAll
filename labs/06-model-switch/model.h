/* SPDX-License-Identifier: MIT. Read-only, little-endian copy-model package v1. */
#ifndef AIM_SWITCH_MODEL_H
#define AIM_SWITCH_MODEL_H
#include <stdint.h>
#include <string.h>

struct package_header {
    uint32_t magic, version, width, payload_bytes, crc32;
};

/* Ordered FP32 tensors whose shapes are common to both checkpoints. */
struct shared_tensors {
    float tokens[11*16], positions[8*16], attn_gain[16], attn_bias[16];
    float qkv[48*16], qkv_b[48], out[16*16], out_b[16];
    float ffn_gain[16], ffn_bias[16], down_b[16], final_gain[16], final_bias[16];
    float head[11*16], head_b[11];
};

struct model_view {
    const void *package;
    uint32_t bytes, width;
    float sx;
    const float *sw, *up_b, *down;
    const struct shared_tensors *common;
    const int8_t *weights;
};

enum load_status { LOAD_OK, BAD_LENGTH, BAD_HEADER, BAD_CRC, BAD_SCALE, BAD_FLOAT };

static inline uint32_t float_bits(float value)
{
    uint32_t bits;
    memcpy(&bits, &value, sizeof bits);
    return bits;
}

static uint32_t payload_crc(const uint8_t *p, uint32_t bytes)
{
    uint32_t crc = ~0u;
    for (uint32_t i = 0; i < bytes; ++i) {
        crc ^= p[i];
        for (unsigned bit = 0; bit < 8; ++bit)
            crc = (crc >> 1) ^ ((0u - (crc & 1)) & 0xedb88320u);
    }
    return ~crc;
}

static inline enum load_status inspect_format(const uint8_t *data, uint32_t bytes, struct model_view *view,
                                             uint32_t version, uint32_t extension_bytes)
{
    struct package_header h;
    if (bytes < sizeof h || ((uintptr_t)data & 3)) return BAD_LENGTH;
    memcpy(&h, data, sizeof h);
    if (h.magic != 0x31504d41 || h.version != version || (h.width != 32 && h.width != 24))
        return BAD_HEADER;
    const uint32_t w = h.width, weight_bytes = w*16;
    const uint32_t float_bytes = sizeof(struct shared_tensors) + (1 + w + w + 16*w)*4;
    if (h.payload_bytes != float_bytes + weight_bytes + extension_bytes || bytes - sizeof h != h.payload_bytes)
        return BAD_LENGTH;
    const uint8_t *payload = data + sizeof h;
    if (payload_crc(payload, h.payload_bytes) != h.crc32) return BAD_CRC;
    for (unsigned i = 0; i < float_bytes/4; ++i) {
        uint32_t bits;
        memcpy(&bits, payload + 4*i, 4);
        if (i <= w && (bits == 0 || bits >= 0x7f800000u)) return BAD_SCALE;
        if ((bits & 0x7f800000u) == 0x7f800000u) return BAD_FLOAT;
    }
    const float *f = (const float *)payload;
    const struct shared_tensors *common = (const struct shared_tensors *)(payload + (1+w)*4);
    const float *up_b = (const float *)(payload + (1+w)*4 + sizeof *common);
    *view = (struct model_view){
        .package = data, .bytes = bytes, .width = w, .sx = f[0], .sw = f+1,
        .common = common, .up_b = up_b, .down = up_b+w,
        .weights = (const int8_t *)(payload + float_bytes)
    };
    return LOAD_OK;
}

static inline enum load_status inspect_package(const uint8_t *data, uint32_t bytes, struct model_view *view)
{
    return inspect_format(data, bytes, view, 1, 0);
}

/* Names consumed by the shared experiment 03 forward pass. */
static struct model_view active;
#define COPY_FFN_WIDTH   active.width
#define activation_scale active.sx
#define weight_scales    active.sw
#define up_bias          active.up_b
#define down_weight      active.down
#define tokens_weight    active.common->tokens
#define positions_weight active.common->positions
#define attn_norm_weight active.common->attn_gain
#define attn_norm_bias   active.common->attn_bias
#define qkv_weight       active.common->qkv
#define qkv_bias         active.common->qkv_b
#define attn_out_weight  active.common->out
#define attn_out_bias    active.common->out_b
#define ffn_norm_weight  active.common->ffn_gain
#define ffn_norm_bias    active.common->ffn_bias
#define down_bias        active.common->down_b
#define final_norm_weight active.common->final_gain
#define final_norm_bias  active.common->final_bias
#define head_weight      active.common->head
#define head_bias        active.common->head_b
#endif
