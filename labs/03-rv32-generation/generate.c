/* SPDX-License-Identifier: MIT. Same RV32IM firmware on the QEMU and RTL systems. */
#include "../../runtime/rv32_console.h"

#define MODEL_PHASE(name) ((void)0)
static inline void record_logit(unsigned index, uint32_t bits) { (void)index; word('L', bits); }
#include "copy_forward.h"

static int8_t tile_a[4*D], tile_b[D*4];
static volatile uint32_t tile_c[16];

static uint32_t digest(const int8_t *bytes, unsigned len)
{
    uint32_t hash = 2166136261u;
    for (unsigned i = 0; i < len; ++i) hash = (hash ^ (uint8_t)bytes[i]) * 16777619u;
    return hash;
}

static void project(unsigned rows)
{
    for (unsigned r = 0; r < rows; r += 4) {
        unsigned m = rows-r < 4 ? rows-r : 4;
        for (unsigned j = 0; j < N; j += 4) {
            for (unsigned i = 0; i < m; ++i)
                for (unsigned k = 0; k < D; ++k) tile_a[i*D+k] = activation[r+i][k];
            for (unsigned k = 0; k < D; ++k)
                for (unsigned n = 0; n < 4; ++n) tile_b[k*4+n] = weight_i8[(j+n)*D+k];
            word('I', (r << 16) | j);
            word('H', (m << 16) | (4 << 8) | D);
            word('X', digest(tile_a, m*D));
            word('W', digest(tile_b, D*4));
            unsigned error = npu_gemm(tile_a, tile_b, tile_c, m, 4, D);
            if (error) stop(error);
            for (unsigned i = 0; i < m; ++i)
                for (unsigned n = 0; n < 4; ++n) {
                    union {uint32_t bits; int32_t value;} acc = { .bits = tile_c[i*4+n] };
                    word('P', acc.bits);
                    up[r+i][j+n] = (float)acc.value * activation_scale * weight_scales[j+n] + up_bias[j+n];
                }
        }
    }
}

void guest_main(void)
{
    // Rejected commands must not write a result or prevent the next submission.
    tile_c[0] = 0x13579bdf;
    if (npu_gemm(tile_a, tile_b, tile_c, 0, 4, D) != 2 ||
        npu_gemm((const int8_t *)tile_c, tile_b, tile_c, 1, 4, D) != 4 ||
        tile_c[0] != 0x13579bdf) stop(9);
    word('A', (uintptr_t)tile_a);
    word('B', (uintptr_t)tile_b);
    word('C', (uintptr_t)tile_c);
    unsigned used = 0, token = 0;
    for (unsigned step = 0; used < CTX; ++step) {
        word('S', step);
        unsigned rows = step == 0 ? 5 : 1;
        for (unsigned r = 0; r < rows; ++r) features(step == 0 ? prompt[r] : token, used++, r);
        project(rows);
        token = next_token(rows-1);
        word('T', token);
        if (token == 10) stop(0);
    }
    stop(10); // expected EOS within the trained context.
}
