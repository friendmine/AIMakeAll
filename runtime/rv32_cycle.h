/* SPDX-License-Identifier: MIT. Read the in-order PicoRV32 cycle counter. */
#ifndef AIM_RV32_CYCLE_H
#define AIM_RV32_CYCLE_H
#include <stdint.h>

static inline uint32_t cycle_after(unsigned dependency)
{
    uint32_t cycle;
    // Order memory accesses and the greedy decision before the boundary.
    __asm__ volatile("rdcycle %0" : "=r"(cycle) : "r"(dependency) : "memory");
    return cycle;
}

#endif
