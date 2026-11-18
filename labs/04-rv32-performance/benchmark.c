/* SPDX-License-Identifier: MIT. One RV32IM image per instrumentation level, two backends. */
#include "../../runtime/rv32_console.h"

enum phase { INPUT_NORM, QKV, ATTENTION, ATTN_OUT, FFN_NORM, CPU_DOT, PACK,
             DRIVER, GATHER, RESCALE, GELU, DOWN, FINAL_NORM_HEAD, PHASE_COUNT };

static inline uint32_t cycle_after(unsigned dependency)
{
    uint32_t cycle;
    // Order memory accesses and the greedy decision before the boundary.
    __asm__ volatile("rdcycle %0" : "=r"(cycle) : "r"(dependency) : "memory");
    return cycle;
}

#ifdef PROFILE_PHASES
static uint32_t phase_cycles[4][PHASE_COUNT], last_cycle;
static unsigned active_step;
static enum phase active_phase;

static void change_phase(enum phase next)
{
    uint32_t now = cycle_after(0);
    phase_cycles[active_step][active_phase] += now - last_cycle;
    last_cycle = now;
    active_phase = next;
}
#define MODEL_PHASE(name) change_phase(name)
#else
#define MODEL_PHASE(name) ((void)0)
#endif

static uint32_t *step_logits;
static inline void record_logit(unsigned index, uint32_t bits) { step_logits[index] = bits; }
#include "../03-rv32-generation/copy_forward.h"

static int32_t sums[CTX][N];  // Natural row/column layout for both projection backends.
static int8_t tile_a[4*D], tile_b[D*4];
static volatile uint32_t tile_c[16];
static uint32_t logits[4][V], elapsed[4], generated[4];

static void project_cpu(unsigned rows, int32_t result[][N])
{
    MODEL_PHASE(CPU_DOT);
    for (unsigned r = 0; r < rows; ++r)
        for (unsigned j = 0; j < N; ++j) {
            int32_t acc = 0;
            for (unsigned k = 0; k < D; ++k)
                acc += (int32_t)activation[r][k] * weight_i8[j*D+k];
            result[r][j] = acc;
        }
}

static void project_npu(unsigned rows, int32_t result[][N])
{
    for (unsigned r = 0; r < rows; r += 4) {
        unsigned m = rows-r < 4 ? rows-r : 4;
        for (unsigned j = 0; j < N; j += 4) {
            MODEL_PHASE(PACK);
            for (unsigned i = 0; i < m; ++i)
                for (unsigned k = 0; k < D; ++k) tile_a[i*D+k] = activation[r+i][k];
            for (unsigned k = 0; k < D; ++k)
                for (unsigned n = 0; n < 4; ++n) tile_b[k*4+n] = weight_i8[(j+n)*D+k];

            MODEL_PHASE(DRIVER);
            unsigned error = npu_gemm(tile_a, tile_b, tile_c, m, 4, D);
            if (error) stop(error);

            MODEL_PHASE(GATHER);
            for (unsigned i = 0; i < m; ++i)
                for (unsigned n = 0; n < 4; ++n)
                    result[r+i][j+n] = (int32_t)tile_c[4*i+n];
        }
    }
}

void guest_main(void)
{
    const unsigned use_npu = *(volatile const uint32_t *)0x10001000u;
    unsigned used = 0, token = 0, steps = 0;
    while (used < CTX) {
        const unsigned step = steps++, rows = step == 0 ? 5 : 1;
        int32_t (*result)[N] = &sums[used];
        step_logits = logits[step];
        uint32_t start = cycle_after(token);
#ifdef PROFILE_PHASES
        last_cycle = start;
        active_step = step;
        active_phase = INPUT_NORM;
#endif
        for (unsigned r = 0; r < rows; ++r)
            features(step == 0 ? prompt[r] : token, used++, r);
        if (use_npu) project_npu(rows, result);
        else project_cpu(rows, result);

        MODEL_PHASE(RESCALE);
        for (unsigned r = 0; r < rows; ++r)
            for (unsigned j = 0; j < N; ++j)
                up[r][j] = (float)result[r][j] * activation_scale * weight_scales[j] + up_bias[j];
        MODEL_PHASE(GELU);
        token = next_token(rows-1);
        uint32_t end = cycle_after(token);
#ifdef PROFILE_PHASES
        phase_cycles[step][active_phase] += end - last_cycle;
#endif
        elapsed[step] = end - start;
        generated[step] = token;
        if (token == 10) break;
    }
    if (token != 10) stop(10);

    // Only now print the actual accumulators and scores used by the timed computation.
    used = 0;
    for (unsigned step = 0; step < steps; ++step) {
        word('S', step);
        word('C', elapsed[step]);
#ifdef PROFILE_PHASES
        for (unsigned p = 0; p < PHASE_COUNT; ++p) word('F', phase_cycles[step][p]);
#endif
        unsigned rows = step == 0 ? 5 : 1;
        for (unsigned r = 0; r < rows; ++r)
            for (unsigned j = 0; j < N; ++j) word('P', sums[used+r][j]);
        used += rows;
        for (unsigned j = 0; j < V; ++j) word('L', logits[step][j]);
        word('T', generated[step]);
    }
    stop(0);
}
