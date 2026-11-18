/* SPDX-License-Identifier: MIT */
#include <stdint.h>

/* One packed A[M,K], B[K,N] command. The caller validates the buffers. */
void linear_tile(unsigned m, unsigned n, unsigned k,
                 const int8_t *a, const int8_t *b, uint32_t *c)
{
    for (unsigned i = 0; i < m; ++i) {
        for (unsigned j = 0; j < n; ++j) {
            uint32_t sum = 0;
            for (unsigned p = 0; p < k; ++p) {
                sum += (uint32_t)((int)a[i*k+p] * (int)b[p*n+j]);
            }
            c[i*n+j] = sum;
        }
    }
}
