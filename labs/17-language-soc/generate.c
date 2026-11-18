/* SPDX-License-Identifier: MIT. Ordered two-block byte-LM plan, RV32 CPU fallback + tiled MMIO. */
#include <math.h>
#include <stdint.h>
#include <string.h>
#include "../../runtime/rv32_console.h"
#include "../../runtime/rv32_cycle.h"
#include "compiled.h"

static float keys[LAYERS][CTX][D], values[LAYERS][CTX][D];
static unsigned device, commands, integer_hash;
static int8_t activation[64] __attribute__((aligned(4)));
static volatile uint32_t partial[4];

static void linear_plan(unsigned opid, const float *x, float *out)
{
    const struct op *p = &ops[opid];
    const int8_t *w = (const int8_t *)blob + p->w;
    const float *sc = (const float *)(blob + p->sc);
    const float *bias = (const float *)(blob + p->bias);
    float peak = 1.e-9f;
    for (unsigned k = 0; k < p->k; k++)
        if (fabsf(x[k]) > peak)
            peak = fabsf(x[k]);
    float sx = peak / 127.f;
    for (unsigned k = 0; k < p->k; k++) {
        float v = x[k] / sx;
        int z = (int)v;
        float f = fabsf(v - z);
        if (f > 0.5f || (f == 0.5f && z % 2))
            z += v < 0 ? -1 : 1;
        activation[k] = z > 127 ? 127 : (z < -127 ? -127 : z);
    }
    for (unsigned j = 0; j < p->n; j += 4) {
        int32_t acc[4] = {0};
        for (unsigned first = 0; first < p->k; first += p->limit) {
            unsigned len = p->k - first < p->limit ? p->k - first : p->limit;
            const int8_t *tile = w + j * p->k + 4 * first;
            if (device) {
                unsigned err = npu_gemm(activation + first, tile, partial, 1, 4, len);
                if (err)
                    stop(err);
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
}

static void norm(const float *x, unsigned gain, unsigned offset, float *y)
{
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
}

static void forward(unsigned id, unsigned pos, float *logits)
{
    float x[D], h[D], qkv[3 * D], attn[D], up[WIDTH], probs[CTX];
    const float *tok = (const float *)(blob + TOK), *positions = (const float *)(blob + POS);
    for (unsigned d = 0; d < D; d++)
        x[d] = tok[id * D + d] + positions[pos * D + d];
    for (unsigned l = 0; l < LAYERS; l++) {
        norm(x, norms[l][0], norms[l][1], h);
        linear_plan(4 * l, h, qkv);
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
        linear_plan(4 * l + 1, attn, h);
        for (unsigned d = 0; d < D; d++)
            x[d] += h[d];
        norm(x, norms[l][2], norms[l][3], h);
        linear_plan(4 * l + 2, h, up);
        for (unsigned i = 0; i < WIDTH; i++) {
            float v = up[i];
            up[i] = 0.5f * v * (1 + erff(v * 0.7071067811865475f));
        }
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
        starts[s] = cycle_after(token);
        unsigned rows = s ? 1 : req[1];
        for (unsigned r = 0; r < rows; r++, pos++)
            forward(s ? token : req[3 + r], pos, r + 1 == rows ? scores[s] : 0);
        token = 0;
        for (unsigned j = 1; j < 256; j++)
            if (scores[s][j] > scores[s][token])
                token = j;
        ends[s] = cycle_after(token);
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
        for (unsigned j = 0; j < 256; j++) {
            uint32_t bits;
            memcpy(&bits, &scores[s][j], 4);
            word('L', bits);
        }
    }
    stop(0);
}
