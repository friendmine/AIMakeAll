/* SPDX-License-Identifier: MIT. All requests and model bytes arrive independently of this ELF. */
#include "../../runtime/rv32_console.h"

#define MODEL_PHASE(name) ((void)0)
static inline void record_logit(unsigned index, uint32_t bits)
{
    (void)index;
    word('L', bits);
}
#include "../03-rv32-generation/copy_forward.h"

static int8_t packed_weights[N/4][D*4] __attribute__((aligned(4)));
static int8_t tile_a[4*D] __attribute__((aligned(4)));
static volatile uint32_t tile_c[16];
static unsigned cache_generation;

static unsigned select_model(const struct model_view *next)
{
    // Both packages live in immutable storage. Compare contents even for different copies.
    unsigned hit = active.bytes == next->bytes &&
        (active.package == next->package || memcmp(active.package, next->package, next->bytes) == 0);
    if (!hit) {
        for (unsigned col = 0; col < next->width; col += 4)
            for (unsigned k = 0; k < D; ++k)
                for (unsigned lane = 0; lane < 4; ++lane)
                    packed_weights[col/4][4*k+lane] = next->weights[(col+lane)*D+k];
        ++cache_generation;
    }
    active = *next;
    return hit;
}

static void infer(const uint8_t *prompt)
{
    unsigned used = 0, token = 0;
    for (unsigned step = 0; step < 4; ++step) {
        word('S', step);
        const unsigned rows = step == 0 ? 5 : 1;
        for (unsigned i = 0; i < rows; ++i)
            features(step == 0 ? prompt[i] : token, used++, i);

        for (unsigned r = 0; r < rows; r += 4) {
            const unsigned m = rows-r < 4 ? rows-r : 4;
            memcpy(tile_a, activation[r], m*D);
            for (unsigned col = 0; col < active.width; col += 4) {
                unsigned error = npu_gemm(tile_a, packed_weights[col/4], tile_c, m, 4, D);
                if (error) stop(error);
                for (unsigned i = 0; i < m; ++i)
                    for (unsigned lane = 0; lane < 4; ++lane) {
                        int32_t sum = (int32_t)tile_c[4*i+lane];
                        word('P', (uint32_t)sum);
                        unsigned j = col+lane;
                        up[r+i][j] = (float)sum * activation_scale * weight_scales[j] + up_bias[j];
                    }
            }
        }
        token = next_token(rows-1);
        word('T', token);
        if (token == 10) return;
    }
}

struct request_span { uint32_t offset, length; };

void guest_main(void)
{
    const uint32_t *region = (const uint32_t *)0x80100000u;
    const uint32_t bytes = *region;
    const uint8_t *input = (const uint8_t *)(region+1);
    if (bytes < 8) stop(20);
    const unsigned requests = input[5];
    const uint32_t table_end = 8 + requests*sizeof(struct request_span);
    if (!requests || bytes < table_end) stop(20);
    for (unsigned i = 0; i < 5; ++i)
        if (input[i] >= V) stop(20);
    for (unsigned index = 0; index < requests; ++index) {
        word('R', index);
        struct request_span span;
        memcpy(&span, input + 8 + index*sizeof span, sizeof span);
        struct model_view next;
        enum load_status status = BAD_LENGTH;
        if (span.offset >= table_end && span.offset <= bytes && span.length <= bytes-span.offset)
            status = inspect_package(input + span.offset, span.length, &next);
        word('V', status);
        if (status == LOAD_OK) {
            word('H', select_model(&next));
            word('N', active.width);
            word('X', float_bits(activation_scale));
            for (unsigned j = 0; j < active.width; ++j) word('W', float_bits(weight_scales[j]));
            infer(input);
        }
        word('G', cache_generation);
        word('Z', index);
    }
    stop(0);
}
