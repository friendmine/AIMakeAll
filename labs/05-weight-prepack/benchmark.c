/* SPDX-License-Identifier: MIT. Three independent requests per reset, one resident model. */
#include "../../runtime/rv32_console.h"
#include "../../runtime/rv32_cycle.h"

#define MODEL_PHASE(name) ((void)0)
static uint32_t *step_logits;
static inline void record_logit(unsigned index, uint32_t bits) { step_logits[index] = bits; }
#include "../03-rv32-generation/copy_forward.h"

enum { REQUESTS = 3, STEPS = 4, CPU = 0, ONSITE = 1, PREPACKED = 2 };
static int8_t tile_a[4*D];
static union {
    int8_t scratch[4*D];
    int8_t blocks[N/4][4*D];
} weight_workspace;
// The unchanged Lab 04 kernel uses the scratch view of the same RAM.
#define tile_b weight_workspace.scratch
static volatile uint32_t tile_c[16];
#include "../04-rv32-performance/projection_kernels.h"
#undef tile_b

struct request {
    uint32_t setup, first_token, total, elapsed[STEPS], token[STEPS], logits[STEPS][V];
    int32_t sums[CTX][N];
};
static struct request requests[REQUESTS];

static void prepare_weights(void)
{
    for (unsigned j = 0; j < N; j += 4)
        for (unsigned k = 0; k < D; ++k)
            for (unsigned n = 0; n < 4; ++n)
                weight_workspace.blocks[j/4][4*k+n] = weight_i8[(j+n)*D+k];
}

// Same row tiling, activation copy, driver and result gathering as the onsite control.
// Only the B operand comes directly from the resident block.
static void project_prepacked(unsigned rows, int32_t result[][N])
{
    for (unsigned r = 0; r < rows; r += 4) {
        unsigned m = rows-r < 4 ? rows-r : 4;
        for (unsigned j = 0; j < N; j += 4) {
            for (unsigned i = 0; i < m; ++i)
                for (unsigned k = 0; k < D; ++k) tile_a[i*D+k] = activation[r+i][k];
            unsigned error = npu_gemm(tile_a, weight_workspace.blocks[j/4], tile_c, m, 4, D);
            if (error) stop(error);
            for (unsigned i = 0; i < m; ++i)
                for (unsigned n = 0; n < 4; ++n)
                    result[r+i][j+n] = (int32_t)tile_c[4*i+n];
        }
    }
}

static void run_request(unsigned mode, unsigned index)
{
    struct request *out = &requests[index];
    unsigned used = 0, token = 0; // Fresh logical KV length; every visible position is overwritten.
    const uint32_t begin = cycle_after(0);
    if (mode == PREPACKED && index == 0) {
        const uint32_t start = cycle_after(0);
        prepare_weights();
        out->setup = cycle_after(0) - start;
    }

    for (unsigned step = 0; step < STEPS; ++step) {
        const unsigned rows = step == 0 ? 5 : 1;
        int32_t (*result)[N] = &out->sums[used];
        step_logits = out->logits[step];
        const uint32_t start = cycle_after(token);
        for (unsigned r = 0; r < rows; ++r)
            features(step == 0 ? prompt[r] : token, used++, r);
        if (mode == CPU) project_cpu(rows, result);
        else if (mode == PREPACKED) project_prepacked(rows, result);
        else project_npu(rows, result);
        for (unsigned r = 0; r < rows; ++r)
            for (unsigned j = 0; j < N; ++j)
                up[r][j] = (float)result[r][j] * activation_scale * weight_scales[j] + up_bias[j];
        token = next_token(rows-1);
        const uint32_t end = cycle_after(token);
        out->elapsed[step] = end - start;
        out->token[step] = token;
        if (step == 0) out->first_token = end - begin;
        if (token == 10) {
            if (step != STEPS-1) stop(10);
            out->total = end - begin;
            return;
        }
    }
    stop(10);
}

void guest_main(void)
{
    const unsigned mode = *(volatile const uint32_t *)0x10001000u;
    if (mode > PREPACKED) stop(11);
    for (unsigned i = 0; i < REQUESTS; ++i) run_request(mode, i);

    // Diagnostics are emitted only after all three requests have selected EOS.
    word('M', mode);
    word('W', (uintptr_t)&weight_workspace);
    for (unsigned i = 0; i < REQUESTS; ++i) {
        word('R', i);
        word('U', requests[i].setup);
        word('F', requests[i].first_token);
        word('E', requests[i].total);
    }
    if (mode == PREPACKED)
        for (unsigned i = 0; i < sizeof(weight_workspace); ++i)
            word('B', ((const uint8_t *)&weight_workspace)[i]);

    for (unsigned i = 0; i < REQUESTS; ++i) {
        const struct request *out = &requests[i];
        unsigned used = 0;
        for (unsigned s = 0; s < STEPS; ++s) {
            word('S', i*STEPS+s);
            word('C', out->elapsed[s]);
            const unsigned rows = s == 0 ? 5 : 1;
            for (unsigned r = 0; r < rows; ++r)
                for (unsigned j = 0; j < N; ++j) word('P', out->sums[used+r][j]);
            used += rows;
            for (unsigned j = 0; j < V; ++j) word('L', out->logits[s][j]);
            word('T', out->token[s]);
        }
    }
    stop(0);
}
