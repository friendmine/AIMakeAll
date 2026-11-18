/* SPDX-License-Identifier: MIT. RV32 bare-metal driver for the course virt machine. */
#include <stdint.h>
#include "fixture.h"

static volatile uint32_t *const reg = (volatile uint32_t *)0x10010000u;
enum { VERSION, COMMAND, STATUS, ERROR, A_ADDR, B_ADDR, C_ADDR, ROWS, COLS, DEPTH };
static inline void fence(void) { __asm__ volatile("fence iorw, iorw" ::: "memory"); }

static void putch(char ch)
{
    volatile uint8_t *uart = (volatile uint8_t *)0x10000000u;
    while (!(uart[5] & 0x20)) {}
    uart[0] = ch;
}

static void word(char tag, uint32_t value)
{
    putch(tag);
    for (int shift = 28; shift >= 0; shift -= 4) {
        putch("0123456789abcdef"[(value >> shift) & 15]);
    }
    putch('\n');
}

static void stop(uint32_t failure)
{
    fence();
    *(volatile uint32_t *)0x100000u = failure ? (failure << 16) | 0x3333 : 0x5555;
    for (;;) __asm__ volatile("wfi");
}

void guest_main(void)
{
    static volatile uint32_t out[ROWS_M * COLS_N];
    static uint32_t total[ROWS_M * COLS_N]; /* Zeroed by the ELF loader. */
    if (reg[VERSION] != 1) stop(1);
    reg[ROWS] = ROWS_M;
    reg[COLS] = COLS_N;
    reg[C_ADDR] = (uintptr_t)out;
    for (unsigned t = 0; t < TILE_COUNT; ++t) {
        reg[A_ADDR] = (uintptr_t)tiles[t].a;
        reg[B_ADDR] = (uintptr_t)tiles[t].b;
        reg[DEPTH] = tiles[t].k;
        fence();
        reg[COMMAND] = 1;
        unsigned poll = 0;
        while (reg[STATUS] == 1 && ++poll < 1000000) {}
        if (reg[STATUS] != 2 || reg[ERROR]) stop(2);
        fence();
        for (unsigned i = 0; i < ROWS_M * COLS_N; ++i) {
            total[i] += out[i];
            word('P', out[i]);
        }
        reg[COMMAND] = 2;
        if (reg[STATUS]) stop(3);
    }
    for (unsigned i = 0; i < ROWS_M * COLS_N; ++i) {
        unsigned j = i % COLS_N;
        /* Fixed fixture uses s_x=1/8, s_w=(j+1)/16, bias=(j-3)/8.
         * Send the exact numerator of 128*Y; unsigned arithmetic preserves bits. */
        word('Y', total[i] * (j+1) + 16u * (j-3u));
    }
    stop(0);
}
