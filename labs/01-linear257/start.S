/* SPDX-License-Identifier: MIT */
.section .text.start,"ax"
.globl _start
_start:
    la sp, stack_top
    call guest_main
1:  wfi
    j 1b
