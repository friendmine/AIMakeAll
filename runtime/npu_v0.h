/* SPDX-License-Identifier: MIT. Single-hart RV32 teaching virt platform. */
#ifndef AIM_NPU_V0_H
#define AIM_NPU_V0_H
#include <stdint.h>

enum { VERSION, COMMAND, STATUS, ERROR, A_ADDR, B_ADDR, C_ADDR, ROWS, COLS, DEPTH };
static volatile uint32_t *const npu = (volatile uint32_t *)0x10010000u;
static inline void io_fence(void) { __asm__ volatile("fence iorw, iorw" ::: "memory"); }

/* Returns the device error (1..4), or a driver failure (>4).
 * A timed-out BUSY device still owns its buffers; the caller must stop. */
static inline unsigned npu_gemm(const int8_t *a, const int8_t *b, volatile uint32_t *c,
                                unsigned m, unsigned n, unsigned k)
{
    if (npu[VERSION] != 1 || npu[STATUS] != 0) return 5;
    npu[A_ADDR] = (uintptr_t)a;
    npu[B_ADDR] = (uintptr_t)b;
    npu[C_ADDR] = (uintptr_t)c;
    npu[ROWS] = m;
    npu[COLS] = n;
    npu[DEPTH] = k;
    io_fence();
    npu[COMMAND] = 1;
    unsigned status, remaining = 1000000;
    do { status = npu[STATUS]; } while (status == 1 && --remaining);
    if (status != 2 && status != 4) return 6;
    unsigned error = npu[ERROR];
    if ((status == 2) != (error == 0)) return 7;
    io_fence();
    npu[COMMAND] = 2;
    return npu[STATUS] == 0 ? error : 8;
}
#endif
