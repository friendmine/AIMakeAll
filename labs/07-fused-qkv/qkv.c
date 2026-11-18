/* SPDX-License-Identifier: MIT. A single copy-model firmware for three QKV backends. */
#include "../../runtime/rv32_console.h"
#include "../../runtime/rv32_cycle.h"

enum { STEPS = 4, CHANNELS = 48, QKV_BYTES = 768, QKV_SCALES = 49 };
enum backend { FP32 = 3, CPU_INT8, NPU_INT8 };
static uint32_t logits[STEPS][11], step_index;
static inline void record_logit(unsigned index, uint32_t value) { logits[step_index][index] = value; }
#define COPY_BATCHED_QKV
#define MODEL_PHASE(name) ((void)0)
#include "../03-rv32-generation/copy_forward.h"

struct qkv_parameters {
    const float *scales;
    const int8_t *weights;
};

struct fused_model {
    struct model_view base;
    struct qkv_parameters qkv;
};

static struct qkv_parameters resident;
static unsigned generation;
static struct {
    int8_t qkv[QKV_BYTES], ffn[N*D];
} packed __attribute__((aligned(4)));

static enum load_status inspect_fused(const uint8_t *data, unsigned bytes, struct fused_model *next)
{
    const unsigned tail_size = 4*QKV_SCALES + QKV_BYTES;
    enum load_status status = inspect_format(data, bytes, &next->base, 2, tail_size);
    if (status != LOAD_OK) return status;
    const float *scales = (const float *)(data + bytes - tail_size);
    for (unsigned i = 0; i < QKV_SCALES; ++i) {
        uint32_t bits = float_bits(scales[i]);
        if (!bits || bits >= 0x7f800000u) return BAD_SCALE;
    }
    next->qkv.scales = scales;
    next->qkv.weights = (const int8_t *)(scales + QKV_SCALES);
    return LOAD_OK;
}

static void pack(int8_t *dest, const int8_t *src, unsigned width)
{
    for (unsigned j = 0; j < width; j += 4)
        for (unsigned k = 0; k < D; ++k)
            for (unsigned n = 0; n < 4; ++n)
                dest[j*D + 4*k+n] = src[(j+n)*D+k];
}

static unsigned select_model(const struct fused_model *next, enum backend mode)
{
    const struct model_view *v = &next->base;
    unsigned hit = active.bytes == v->bytes &&
        (active.package == v->package || memcmp(active.package, v->package, v->bytes) == 0);
    if (!hit) {
        pack(packed.ffn, v->weights, v->width);
        if (mode == NPU_INT8) pack(packed.qkv, next->qkv.weights, CHANNELS);
        ++generation;
    }
    resident = next->qkv;
    active = *v;
    return hit;
}

static int8_t qkv_input[5][D] __attribute__((aligned(4)));
static volatile uint32_t tile_c[16];
static int32_t qkv_sums[CTX][CHANNELS], ffn_sums[CTX][N];
static float fused[CTX][CHANNELS];
static uint32_t tokens[STEPS], step_start[STEPS], step_end[STEPS];

static void tiled(const int8_t *x, const int8_t *weights, unsigned rows,
                  unsigned width, int32_t *dest, unsigned stride)
{
    for (unsigned r = 0; r < rows; r += 4) {
        unsigned m = rows-r < 4 ? rows-r : 4;
        for (unsigned j = 0; j < width; j += 4) {
            unsigned error = npu_gemm(x+r*D, weights+j*D, tile_c, m, 4, D);
            if (error) stop(error);
            for (unsigned i = 0; i < m; ++i)
                for (unsigned n = 0; n < 4; ++n)
                    dest[(r+i)*stride+j+n] = (int32_t)tile_c[i*4+n];
        }
    }
}

static void project_qkv(enum backend mode, const uint8_t *prompt, unsigned pos, unsigned rows, unsigned token)
{
    for (unsigned r = 0; r < rows; ++r) {
        float h[D];
        input_norm(pos == 0 ? prompt[r] : token, pos+r, r, h);
        if (mode == FP32) linear(h, qkv_weight, qkv_bias, fused[pos+r], D, CHANNELS);
        else for (unsigned k = 0; k < D; ++k) qkv_input[r][k] = quantize_scaled(h[k], resident.scales[0]);
    }
    if (mode == FP32) return;
    if (mode == NPU_INT8) {
        tiled(&qkv_input[0][0], packed.qkv, rows, CHANNELS, &qkv_sums[pos][0], CHANNELS);
    } else {
        for (unsigned r = 0; r < rows; ++r)
            for (unsigned j = 0; j < CHANNELS; ++j) {
                int32_t sum = 0;
                for (unsigned k = 0; k < D; ++k) sum += qkv_input[r][k]*resident.weights[j*D+k];
                qkv_sums[pos+r][j] = sum;
            }
    }
    for (unsigned r = 0; r < rows; ++r)
        for (unsigned j = 0; j < CHANNELS; ++j)
            fused[pos+r][j] = qkv_sums[pos+r][j]*resident.scales[0]*resident.scales[1+j] + qkv_bias[j];
}

static void infer(enum backend mode, const uint8_t *prompt)
{
    unsigned pos = 0, token = 0;
    for (unsigned s = 0; s < STEPS; ++s) {
        unsigned rows = s == 0 ? 5 : 1;
        step_index = s;
        step_start[s] = cycle_after(token);
        project_qkv(mode, prompt, pos, rows, token);
        for (unsigned r = 0; r < rows; ++r) attend(fused[pos+r], pos+r, r);
        tiled(&activation[0][0], packed.ffn, rows, active.width, &ffn_sums[pos][0], N);
        for (unsigned r = 0; r < rows; ++r)
            for (unsigned j = 0; j < active.width; ++j)
                up[r][j] = ffn_sums[pos+r][j]*activation_scale*weight_scales[j] + up_bias[j];
        token = next_token(rows-1);
        step_end[s] = cycle_after(token);
        tokens[s] = token;
        pos += rows;
        if (token == 10 && s+1 != STEPS) stop(21);
    }
    if (token != 10) stop(21);
}

// Transfer the values actually consumed by the generation path, after the measured request.
static void dump(enum backend mode)
{
    for (unsigned i = 0; i < QKV_SCALES; ++i) word('X', float_bits(resident.scales[i]));
    word('W', float_bits(activation_scale));
    for (unsigned j = 0; j < active.width; ++j) word('W', float_bits(weight_scales[j]));
    for (unsigned s = 0; s < STEPS; ++s) {
        word('U', step_start[s]);
        word('E', step_end[s]);
        word('J', tokens[s]);
        for (unsigned j = 0; j < V; ++j) word('L', logits[s][j]);
    }
    for (unsigned r = 0; r < CTX; ++r) {
        if (mode != FP32)
            for (unsigned j = 0; j < CHANNELS; ++j) word('I', qkv_sums[r][j]);
        for (unsigned j = 0; j < CHANNELS; ++j) word('F', float_bits(fused[r][j]));
        for (unsigned j = 0; j < D; ++j) word('K', float_bits(keys[r][j]));
        for (unsigned j = 0; j < D; ++j) word('Y', float_bits(values[r][j]));
        for (unsigned j = 0; j < active.width; ++j) word('P', ffn_sums[r][j]);
    }
}

void guest_main(void)
{
    enum backend mode = *(const volatile unsigned *)0x10001000u;
    if (mode < FP32 || mode > NPU_INT8) stop(20);
    word('M', mode);
    const uint32_t *region = (const uint32_t *)0x80100000u;
    uint32_t length = *region;
    const uint8_t *input = (const uint8_t *)(region+1);
    if (length < 8) stop(20);
    unsigned count = input[5], table_end = 8+8*count;
    if (!count || table_end > length) stop(20);
    for (unsigned i = 0; i < 5; ++i) if (input[i] >= V) stop(20);
    for (unsigned i = 0; i < count; ++i) {
        word('R', i);
        uint32_t start = cycle_after(i);
        uint32_t span[2];
        memcpy(span, input+8+8*i, sizeof span);
        struct fused_model next;
        enum load_status status = BAD_LENGTH;
        if (span[0] >= table_end && span[0] <= length && span[1] <= length-span[0])
            status = inspect_fused(input+span[0], span[1], &next);
        uint32_t validated = cycle_after(status);
        unsigned hit = 0;
        if (status == LOAD_OK) hit = select_model(&next, mode);
        uint32_t ready = cycle_after(hit);
        if (status == LOAD_OK) infer(mode, input);
        word('Z', i);
        word('V', status);
        word('G', generation);
        word('A', start);
        word('B', validated);
        word('C', ready);
        if (status == LOAD_OK) {
            word('H', hit);
            word('N', active.width);
            dump(mode);
        }
    }
    stop(0);
}
