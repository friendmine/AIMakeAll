/* SPDX-License-Identifier: MIT. Scalar and on-demand kernels as measured in Lab 04. */
#ifndef AIM_PROJECTION_KERNELS_H
#define AIM_PROJECTION_KERNELS_H

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

#endif
