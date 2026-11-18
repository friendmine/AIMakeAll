/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef HW_RISCV_AIM_NPU_H
#define HW_RISCV_AIM_NPU_H
#include "exec/hwaddr.h"
void aim_npu_map(hwaddr base, uint64_t ram_base, uint64_t ram_size);
#endif
