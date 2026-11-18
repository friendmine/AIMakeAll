/* SPDX-License-Identifier: MIT. Same RV32IM firmware on the QEMU and RTL systems. */
#include <math.h>
#include <stdint.h>
#include "../../runtime/rv32_console.h"
#include "model.h"

enum { D = 16, N = 32, V = 11, CTX = 8 };
static float keys[CTX][D], values[CTX][D], residual[5][D];
static int8_t activation[5][D], tile_a[4*D], tile_b[D*4];
static volatile uint32_t tile_c[16];
static float up[5][N];

static void linear(const float *x, const float *w, const float *b, float *y,
                   unsigned in, unsigned out)
{
    for (unsigned j = 0; j < out; ++j) {
        float sum = 0;
        for (unsigned i = 0; i < in; ++i) sum += x[i] * w[j*in+i];
        y[j] = sum + b[j];
    }
}

static void norm(const float *x, const float *w, const float *b, float *y)
{
    float mean = 0, var = 0;
    for (unsigned i = 0; i < D; ++i) mean += x[i];
    mean /= D;
    for (unsigned i = 0; i < D; ++i) {
        float d = x[i] - mean;
        var += d*d;
    }
    float inv = 1.0f / sqrtf(var/D + 1e-5f);
    for (unsigned i = 0; i < D; ++i) y[i] = (x[i]-mean)*inv*w[i]+b[i];
}

static int8_t quantize(float v)
{
    float x = v / activation_scale;
    if (x >= 127) return 127;
    if (x <= -127) return -127;
    int z = (int)x;
    float fraction = fabsf(x-z);
    if (fraction > 0.5f || (fraction == 0.5f && (z % 2))) z += x < 0 ? -1 : 1;
    return (int8_t)z;
}

static void features(unsigned token, unsigned pos, unsigned row)
{
    float h[D], qkv[3*D], scores[CTX], context[D] = {0}, attn[D];
    for (unsigned i = 0; i < D; ++i)
        residual[row][i] = tokens_weight[token*D+i] + positions_weight[pos*D+i];
    norm(residual[row], attn_norm_weight, attn_norm_bias, h);
    linear(h, qkv_weight, qkv_bias, qkv, D, 3*D);
    for (unsigned i = 0; i < D; ++i) {
        keys[pos][i] = qkv[D+i];
        values[pos][i] = qkv[2*D+i];
    }
    float maximum = -INFINITY, denominator = 0;
    for (unsigned t = 0; t <= pos; ++t) {
        float dot = 0;
        for (unsigned i = 0; i < D; ++i) dot += qkv[i]*keys[t][i];
        scores[t] = dot * 0.25f;
        if (scores[t] > maximum) maximum = scores[t];
    }
    for (unsigned t = 0; t <= pos; ++t) {
        scores[t] = expf(scores[t]-maximum);
        denominator += scores[t];
    }
    for (unsigned t = 0; t <= pos; ++t)
        for (unsigned i = 0; i < D; ++i)
            context[i] += (scores[t]/denominator)*values[t][i];
    linear(context, attn_out_weight, attn_out_bias, attn, D, D);
    for (unsigned i = 0; i < D; ++i) residual[row][i] += attn[i];
    norm(residual[row], ffn_norm_weight, ffn_norm_bias, h);
    for (unsigned i = 0; i < D; ++i) activation[row][i] = quantize(h[i]);
}

static uint32_t digest(const int8_t *bytes, unsigned len)
{
    uint32_t hash = 2166136261u;
    for (unsigned i = 0; i < len; ++i) hash = (hash ^ (uint8_t)bytes[i]) * 16777619u;
    return hash;
}

static void project(unsigned rows)
{
    for (unsigned r = 0; r < rows; r += 4) {
        unsigned m = rows-r < 4 ? rows-r : 4;
        for (unsigned j = 0; j < N; j += 4) {
            for (unsigned i = 0; i < m; ++i)
                for (unsigned k = 0; k < D; ++k) tile_a[i*D+k] = activation[r+i][k];
            for (unsigned k = 0; k < D; ++k)
                for (unsigned n = 0; n < 4; ++n) tile_b[k*4+n] = weight_i8[(j+n)*D+k];
            word('I', (r << 16) | j);
            word('H', (m << 16) | (4 << 8) | D);
            word('X', digest(tile_a, m*D));
            word('W', digest(tile_b, D*4));
            unsigned error = npu_gemm(tile_a, tile_b, tile_c, m, 4, D);
            if (error) stop(error);
            for (unsigned i = 0; i < m; ++i)
                for (unsigned n = 0; n < 4; ++n) {
                    union {uint32_t bits; int32_t value;} acc = { .bits = tile_c[i*4+n] };
                    word('P', acc.bits);
                    up[r+i][j+n] = (float)acc.value * activation_scale * weight_scales[j+n] + up_bias[j+n];
                }
        }
    }
}

static unsigned next_token(unsigned row)
{
    float hidden[D], h[D], logits[V];
    for (unsigned j = 0; j < N; ++j) {
        float x = up[row][j];
        up[row][j] = 0.5f*x*(1 + erff(x*0.7071067811865475f));
    }
    linear(up[row], down_weight, down_bias, hidden, N, D);
    for (unsigned i = 0; i < D; ++i) hidden[i] += residual[row][i];
    norm(hidden, final_norm_weight, final_norm_bias, h);
    linear(h, head_weight, head_bias, logits, D, V);
    unsigned best = 0;
    for (unsigned j = 0; j < V; ++j) {
        union {float value; uint32_t bits;} score = { .value = logits[j] };
        word('L', score.bits);
        if (logits[j] > logits[best]) best = j;
    }
    return best;
}

void guest_main(void)
{
    // Rejected commands must not write a result or prevent the next submission.
    tile_c[0] = 0x13579bdf;
    if (npu_gemm(tile_a, tile_b, tile_c, 0, 4, D) != 2 ||
        npu_gemm((const int8_t *)tile_c, tile_b, tile_c, 1, 4, D) != 4 ||
        tile_c[0] != 0x13579bdf) stop(9);
    word('A', (uintptr_t)tile_a);
    word('B', (uintptr_t)tile_b);
    word('C', (uintptr_t)tile_c);
    unsigned used = 0, token = 0;
    for (unsigned step = 0; used < CTX; ++step) {
        word('S', step);
        unsigned rows = step == 0 ? 5 : 1;
        for (unsigned r = 0; r < rows; ++r) features(step == 0 ? prompt[r] : token, used++, r);
        project(rows);
        token = next_token(rows-1);
        word('T', token);
        if (token == 10) stop(0);
    }
    stop(10); // expected EOS within the trained context.
}
