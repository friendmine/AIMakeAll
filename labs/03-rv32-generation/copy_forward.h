/* SPDX-License-Identifier: MIT. Shared RV32 forward pass for the copy task. */
#ifndef AIM_COPY_FORWARD_H
#define AIM_COPY_FORWARD_H
#include <math.h>
#include "model.h"
#include "../../runtime/copy_shape.h"

enum { D = 16, N = 32, V = COPY_VOCAB, CTX = COPY_CONTEXT };
#ifndef COPY_FFN_WIDTH
#define COPY_FFN_WIDTH N
#endif
static float keys[CTX][D], values[CTX][D], residual[COPY_PROMPT][D];
static int8_t activation[COPY_PROMPT][D];
static float up[COPY_PROMPT][N];

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

#ifdef COPY_BATCHED_QKV
#define quantize(v) quantize_scaled((v), activation_scale)
static int8_t quantize_scaled(float v, float scale)
{
    float x = v / scale;
#else
static int8_t quantize(float v)
{
    float x = v / activation_scale;
#endif
    if (x >= 127) return 127;
    if (x <= -127) return -127;
    int z = (int)x;
    float fraction = fabsf(x-z);
    if (fraction > 0.5f || (fraction == 0.5f && (z % 2))) z += x < 0 ? -1 : 1;
    return (int8_t)z;
}

/* The batched caller projects the normalized prompt before running causal
 * attention row by row. Keep the original scalar schedule for the timed labs. */
#ifdef COPY_BATCHED_QKV
static void input_norm(unsigned token, unsigned pos, unsigned row, float h[D])
{
#else
static void features(unsigned token, unsigned pos, unsigned row)
{
    float h[D], qkv[3*D], scores[CTX], context[D] = {0}, attn[D];
#endif
    MODEL_PHASE(INPUT_NORM);
    for (unsigned i = 0; i < D; ++i)
        residual[row][i] = tokens_weight[token*D+i] + positions_weight[pos*D+i];
    norm(residual[row], attn_norm_weight, attn_norm_bias, h);
#ifdef COPY_BATCHED_QKV
}

static void attend(const float qkv[3*D], unsigned pos, unsigned row)
{
    float h[D], scores[CTX], context[D] = {0}, attn[D];
#else
    MODEL_PHASE(QKV);
    linear(h, qkv_weight, qkv_bias, qkv, D, 3*D);
#endif
    MODEL_PHASE(ATTENTION);
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
    MODEL_PHASE(ATTN_OUT);
    linear(context, attn_out_weight, attn_out_bias, attn, D, D);
    MODEL_PHASE(FFN_NORM);
    for (unsigned i = 0; i < D; ++i) residual[row][i] += attn[i];
    norm(residual[row], ffn_norm_weight, ffn_norm_bias, h);
    for (unsigned i = 0; i < D; ++i) activation[row][i] = quantize(h[i]);
}

static unsigned next_token(unsigned row)
{
    float hidden[D], h[D], logits[V];
    for (unsigned j = 0; j < COPY_FFN_WIDTH; ++j) {
        float x = up[row][j];
        up[row][j] = 0.5f*x*(1 + erff(x*0.7071067811865475f));
    }
    MODEL_PHASE(DOWN);
    linear(up[row], down_weight, down_bias, hidden, COPY_FFN_WIDTH, D);
    MODEL_PHASE(FINAL_NORM_HEAD);
    for (unsigned i = 0; i < D; ++i) hidden[i] += residual[row][i];
    norm(hidden, final_norm_weight, final_norm_bias, h);
#ifdef MEASURE_BYTE_STAGES
    uint32_t head_begin = cycle_after(0);
#endif
    linear(h, head_weight, head_bias, logits, D, V);
#ifdef MEASURE_BYTE_STAGES
    head_cycles[step_index] = cycle_after(float_bits(logits[0])) - head_begin;
#endif
    unsigned best = 0;
    for (unsigned j = 0; j < V; ++j) {
        union {float value; uint32_t bits;} score = { .value = logits[j] };
        record_logit(j, score.bits);
        if (logits[j] > logits[best]) best = j;
    }
    return best;
}

#endif
