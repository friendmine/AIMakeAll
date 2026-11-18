/* Batch independent layer-zero QKV projections in prompt order.
 * All later attention uses the same sequential causal KV updates as the baseline.
 * This particular operation has K=D=32 (one reduction tile). */
static float grouped_qkv[4][3 * D];
static int8_t grouped_input[4][D] __attribute__((aligned(4)));
static volatile uint32_t grouped_sums[4][4];
static void project_prompt_qkv(const uint8_t *ids, unsigned pos, unsigned rows)
{
    const struct op *op = &ops[0];
    const float *embedding = (const float *)(blob + TOK);
    const float *position = (const float *)(blob + POS);
    const float *sw = (const float *)(blob + op->sc);
    const float *bias = (const float *)(blob + op->bias);
    const int8_t *weights = (const int8_t *)(blob + op->w);
    float scales[4], h[4][D];
    for (unsigned r = 0; r < rows; r++) {
        float x[D];
        for (unsigned k = 0; k < D; k++)
            x[k] = embedding[ids[r] * D + k] + position[(pos + r) * D + k];
        norm(x, norms[0][0], norms[0][1], h[r]);
    }
    PROFILE_START(linear_begin);
    for (unsigned r = 0; r < rows; r++)
        scales[r] = quantize_activation(h[r], grouped_input[r], D);
    for (unsigned j = 0; j < 3 * D; j += 4) {
        PROFILE_START(driver_begin);
        unsigned error = npu_gemm(grouped_input[0], weights + j * D, grouped_sums[0], rows, 4, D);
        if (error)
            stop(error);
        PROFILE_END(driver_begin, P_DRIVER);
        commands++;
        for (unsigned r = 0; r < rows; r++) {
            for (unsigned n = 0; n < 4; n++) {
                int32_t acc = (int32_t)grouped_sums[r][n];
                integer_hash = (integer_hash ^ (uint32_t)acc) * 16777619u;
                grouped_qkv[r][j + n] = acc * scales[r] * sw[j + n] + bias[j + n];
            }
        }
    }
    PROFILE_END(linear_begin, P_LINEAR);
}
