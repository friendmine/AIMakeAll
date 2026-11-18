// SPDX-License-Identifier: MIT
#include "Vmac_int8.h"
#include <cstdint>
#include <cstdio>
#include <vector>

static void tick(Vmac_int8 &dut) {
    dut.clk = 0;
    dut.eval();
    dut.clk = 1;
    dut.eval();
}

// One byte stream per command: A then B, row major. Return hex words in C order.
int main() {
    unsigned m, n, k;
    if (std::scanf("%u %u %u", &m, &n, &k) != 3 || !m || !n || !k ||
        m > 256 || n > 256 || k > 256 || std::getchar() != '\n') return 2;
    std::vector<uint8_t> a(m*k), b(k*n);
    if (std::fread(a.data(), 1, a.size(), stdin) != a.size() ||
        std::fread(b.data(), 1, b.size(), stdin) != b.size() || std::getchar() != EOF) return 2;
    Vmac_int8 dut;
    dut.rst_n = 0;
    dut.enable = 0;
    dut.clear = 0;
    tick(dut);
    dut.rst_n = 1;
    for (unsigned i = 0; i < m; ++i) {
        for (unsigned j = 0; j < n; ++j) {
            dut.clear = 1;
            tick(dut);
            dut.clear = 0;
            dut.enable = 1;
            for (unsigned p = 0; p < k; ++p) {
                dut.a = a[i*k+p];
                dut.b = b[p*n+j];
                tick(dut);
            }
            std::printf("%08x\n", static_cast<unsigned>(dut.acc));
        }
    }
    dut.final();
}
