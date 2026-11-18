/* SPDX-License-Identifier: MIT. One RV32IM image per instrumentation level, two backends. */
#include "../../runtime/rv32_console.h"

enum phase { INPUT_NORM, QKV, ATTENTION, ATTN_OUT, FFN_NORM, CPU_DOT, PACK,
             DRIVER, GATHER, RESCALE, GELU, DOWN, FINAL_NORM_HEAD, PHASE_COUNT };

#include "../../runtime/rv32_cycle.h"

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

#include "projection_kernels.h"

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
