/* SPDX-License-Identifier: MIT. Teaching virt UART and test finisher. */
#ifndef AIM_RV32_CONSOLE_H
#define AIM_RV32_CONSOLE_H
#include "npu_v0.h"

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
    io_fence();
    *(volatile uint32_t *)0x100000u = failure ? (failure << 16) | 0x3333 : 0x5555;
    for (;;) __asm__ volatile("wfi");
}

#endif
