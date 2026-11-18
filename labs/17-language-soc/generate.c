/* SPDX-License-Identifier: MIT. Ordered two-block byte-LM plan, RV32 CPU fallback + tiled MMIO. */
#include <math.h>
#include <stdint.h>
#include <string.h>
#include "../../runtime/rv32_console.h"
#include "../../runtime/rv32_cycle.h"
#include "compiled.h"
#include "../24-design-challenge/profile.h"

static float keys[LAYERS][CTX][D], values[LAYERS][CTX][D];
static unsigned device, commands, integer_hash;
static int8_t activation[64] __attribute__((aligned(4)));
static volatile uint32_t partial[4];

static inline __attribute__((always_inline)) float quantize_activation(const float *x, int8_t *out,
                                                                       unsigned width)
{
    float peak = 1.e-9f;
    for (unsigned k = 0; k < width; k++)
        if (fabsf(x[k]) > peak)
            peak = fabsf(x[k]);
    float sx = peak / 127.f;
    for (unsigned k = 0; k < width; k++) {
        float v = x[k] / sx;
        int z = (int)v;
        float f = fabsf(v - z);
        if (f > 0.5f || (f == 0.5f && z % 2))
            z += v < 0 ? -1 : 1;
        out[k] = z > 127 ? 127 : (z < -127 ? -127 : z);
    }
    return sx;
}

static void linear_plan(unsigned opid, const float *x, float *out)
{
    const struct op *p = &ops[opid];
    const int8_t *w = (const int8_t *)blob + p->w;
    const float *sc = (const float *)(blob + p->sc);
    const float *bias = (const float *)(blob + p->bias);
    PROFILE_START(linear_begin);
    float sx = quantize_activation(x, activation, p->k);
    for (unsigned j = 0; j < p->n; j += 4) {
        int32_t acc[4] = {0};
        for (unsigned first = 0; first < p->k; first += p->limit) {
            unsigned len = p->k - first < p->limit ? p->k - first : p->limit;
            const int8_t *tile = w + j * p->k + 4 * first;
            if (device) {
                PROFILE_START(driver_begin);
                unsigned err = npu_gemm(activation + first, tile, partial, 1, 4, len);
                if (err)
                    stop(err);
                PROFILE_END(driver_begin, P_DRIVER);
                for (unsigned l = 0; l < 4; l++)
                    acc[l] += (int32_t)partial[l];
                commands++;
            } else {
                for (unsigned k = 0; k < len; k++)
                    for (unsigned l = 0; l < 4; l++)
                        acc[l] += activation[first + k] * tile[k * 4 + l];
            }
        }
        for (unsigned l = 0; l < 4; l++) {
            integer_hash = (integer_hash ^ (uint32_t)acc[l]) * 16777619u;
            out[j + l] = acc[l] * sx * sc[j + l] + bias[j + l];
        }
    }
    PROFILE_END(linear_begin, P_LINEAR);
}

static void norm(const float *x, unsigned gain, unsigned offset, float *y)
{
    PROFILE_START(norm_begin);
    const float *w = (const float *)(blob + gain), *b = (const float *)(blob + offset);
    float mean = 0, var = 0;
    for (unsigned j = 0; j < D; j++)
        mean += x[j];
    mean /= D;
    for (unsigned j = 0; j < D; j++) {
        float d = x[j] - mean;
        var += d * d;
    }
    float inv = 1.f / sqrtf(var / D + 1.e-5f);
    for (unsigned j = 0; j < D; j++)
        y[j] = (x[j] - mean) * inv * w[j] + b[j];
    PROFILE_END(norm_begin, P_NORM);
}

#ifdef AIM_QKV4
#include "../24-design-challenge/grouped.h"
#endif

static void forward(unsigned id, unsigned pos, float *logits, const float *first_qkv)
{
    float x[D], h[D], qkv[3 * D], attn[D], up[WIDTH], probs[CTX];
    const float *tok = (const float *)(blob + TOK), *positions = (const float *)(blob + POS);
    for (unsigned d = 0; d < D; d++)
        x[d] = tok[id * D + d] + positions[pos * D + d];
    for (unsigned l = 0; l < LAYERS; l++) {
        if (l == 0 && first_qkv)
            memcpy(qkv, first_qkv, sizeof qkv);
        else {
            norm(x, norms[l][0], norms[l][1], h);
            linear_plan(4 * l, h, qkv);
        }
        PROFILE_START(attention_begin);
        memcpy(keys[l][pos], qkv + D, sizeof h);
        memcpy(values[l][pos], qkv + 2 * D, sizeof h);
        for (unsigned head = 0; head < HEADS; head++) {
            unsigned begin = head * (D / HEADS), end = begin + D / HEADS;
            float mx = -INFINITY, total = 0;
            for (unsigned t = 0; t <= pos; t++) {
                float score = 0;
                for (unsigned d = begin; d < end; d++)
                    score += qkv[d] * keys[l][t][d];
                probs[t] = score * (1.f / sqrtf(D / HEADS));
                if (probs[t] > mx)
                    mx = probs[t];
            }
            for (unsigned t = 0; t <= pos; t++) {
                probs[t] = expf(probs[t] - mx);
                total += probs[t];
            }
            for (unsigned d = begin; d < end; d++) {
                attn[d] = 0;
                for (unsigned t = 0; t <= pos; t++)
                    attn[d] += (probs[t] / total) * values[l][t][d];
            }
        }
        PROFILE_END(attention_begin, P_ATTN);
        linear_plan(4 * l + 1, attn, h);
        for (unsigned d = 0; d < D; d++)
            x[d] += h[d];
        norm(x, norms[l][2], norms[l][3], h);
        linear_plan(4 * l + 2, h, up);
        PROFILE_START(gelu_begin);
        for (unsigned i = 0; i < WIDTH; i++) {
            float v = up[i];
            up[i] = 0.5f * v * (1 + erff(v * 0.7071067811865475f));
        }
        PROFILE_END(gelu_begin, P_GELU);
        linear_plan(4 * l + 3, up, h);
        for (unsigned d = 0; d < D; d++)
            x[d] += h[d];
    }
    if (logits) {
        norm(x, FINAL_GAIN, FINAL_BIAS, h);
        linear_plan(4 * LAYERS, h, logits);
    }
}

void guest_main(void)
{
    const uint32_t *region = (const uint32_t *)0x80100000u;
    const uint8_t *req = (const uint8_t *)(region + 1);
    if (*region < 4 || req[0] > 1 || !req[1] || !req[2] || req[2] > 8 || *region != 3u + req[1] ||
        req[1] + req[2] - 1 > CTX)
        stop(20);
    device = req[0];
    static float scores[8][256];
    unsigned starts[8], ends[8], tokens[8], hashes[8], counts[8];
    unsigned pos = 0, token = 0;
    for (unsigned s = 0; s < req[2]; s++) {
        integer_hash = 2166136261u;
        commands = 0;
#ifdef AIM_PROFILE
        memset(profile, 0, sizeof profile);
#endif
        starts[s] = cycle_after(token);
        unsigned rows = s ? 1 : req[1];
        for (unsigned r = 0; r < rows; r++, pos++) {
            const float *precomputed = 0;
#ifdef AIM_QKV4
            if (device && !s && rows > 1) {
                if (r % 4 == 0) {
                    unsigned count = rows - r < 4 ? rows - r : 4;
                    project_prompt_qkv(req + 3 + r, pos, count);
                }
                precomputed = grouped_qkv[r % 4];
            }
#endif
            forward(s ? token : req[3 + r], pos, r + 1 == rows ? scores[s] : 0, precomputed);
        }
        token = 0;
        for (unsigned j = 1; j < 256; j++)
            if (scores[s][j] > scores[s][token])
                token = j;
        ends[s] = cycle_after(token);
#ifdef AIM_PROFILE
        memcpy(profile_steps[s], profile, sizeof profile);
#endif
        tokens[s] = token;
        hashes[s] = integer_hash;
        counts[s] = commands;
    }
    for (unsigned s = 0; s < req[2]; s++) {
        word('U', starts[s]);
        word('E', ends[s]);
        word('J', tokens[s]);
        word('H', hashes[s]);
        word('N', counts[s]);
#ifdef AIM_PROFILE
        for (unsigned i = 0; i < P_COUNT; i++)
            word('P', profile_steps[s][i]);
#endif
        for (unsigned j = 0; j < 256; j++) {
            uint32_t bits;
            memcpy(&bits, &scores[s][j], 4);
            word('L', bits);
        }
    }
    stop(0);
}
