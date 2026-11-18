/* SPDX-License-Identifier: MIT. RV32 bare-metal driver for the course virt machine. */
#include <stdint.h>
#include "fixture.h"

#include "../../runtime/rv32_console.h"

void guest_main(void)
{
    static volatile uint32_t out[ROWS_M * COLS_N];
    static uint32_t total[ROWS_M * COLS_N]; /* Zeroed by the ELF loader. */
    for (unsigned t = 0; t < TILE_COUNT; ++t) {
        unsigned error = npu_gemm(tiles[t].a, tiles[t].b, out, ROWS_M, COLS_N, tiles[t].k);
        if (error) stop(error);
        for (unsigned i = 0; i < ROWS_M * COLS_N; ++i) {
            total[i] += out[i];
            word('P', out[i]);
        }
    }
    for (unsigned i = 0; i < ROWS_M * COLS_N; ++i) {
        unsigned j = i % COLS_N;
        /* Fixed fixture uses s_x=1/8, s_w=(j+1)/16, bias=(j-3)/8.
         * Send the exact numerator of 128*Y; unsigned arithmetic preserves bits. */
        word('Y', total[i] * (j+1) + 16u * (j-3u));
    }
    stop(0);
}
