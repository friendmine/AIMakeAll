/* SPDX-License-Identifier: MIT. One activation row, four output channels per tile. */
static void quantized_head(const float h[D], float logits[V])
{
    static int8_t hx[D] __attribute__((aligned(4)));
    static volatile uint32_t head_c[4] __attribute__((aligned(4)));
    for (unsigned k = 0; k < D; ++k)
        hx[k] = quantize_scaled(h[k], head_scales[0]);
    for (unsigned j = 0; j < V; j += 4) {
        const int8_t *weights = head_packed + j * D;
        if (head_mode == NPU_INT8) {
            unsigned e = npu_gemm(hx, weights, head_c, 1, 4, D);
            if (e)
                stop(e);
        }
        for (unsigned n = 0; n < 4; ++n) {
            int32_t sum = 0;
            if (head_mode == NPU_INT8)
                sum = (int32_t)head_c[n];
            else
                for (unsigned k = 0; k < D; ++k)
                    sum += hx[k] * weights[4 * k + n];
            logits[j + n] = sum * head_scales[0] * head_scales[1 + j + n] + head_bias[j + n];
        }
    }
}
