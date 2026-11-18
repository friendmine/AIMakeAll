// SPDX-License-Identifier: MIT
#include "Vprojection_mmio.h"
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>

constexpr uint32_t base = 0x80000000;
struct Bench {
    Vprojection_mmio dut;
    std::array<uint8_t, 1024> memory{};
    unsigned cycles = 0, reads = 0, writes = 0, stalls = 0;
    bool waiting = false;
    uint32_t held_addr = 0, held_value = 0;
    bool held_write = false;

    uint32_t word(unsigned offset) const
    {
        uint32_t value = 0;
        for (unsigned i = 0; i < 4; ++i)
            value |= uint32_t(memory.at(offset + i)) << (8 * i);
        return value;
    }
    void tick()
    {
        dut.clk = 0;
        dut.dma_ready = cycles % 5 >= 2;
        dut.eval();
        if (dut.bus_error)
            throw std::runtime_error("unexpected MMIO error");
        if (waiting && dut.rst_n &&
            (!dut.dma_valid || dut.dma_write != held_write || dut.dma_addr != held_addr ||
             (held_write && dut.dma_wdata != held_value)))
            throw std::runtime_error("DMA request changed under backpressure");
        waiting = dut.rst_n && dut.dma_valid && !dut.dma_ready;
        if (dut.rst_n && dut.dma_valid) {
            held_addr = dut.dma_addr;
            held_value = dut.dma_wdata;
            held_write = dut.dma_write;
            unsigned at = (dut.dma_addr - base) & ~3u;
            if (!dut.dma_write)
                dut.dma_rdata = word(at);
            if (waiting)
                ++stalls;
            else if (dut.dma_write) {
                for (unsigned i = 0; i < 4; ++i)
                    memory.at(at + i) = dut.dma_wdata >> (8 * i);
                ++writes;
            } else
                ++reads;
        }
        dut.clk = 1;
        dut.eval();
        ++cycles;
    }
    void reg(unsigned offset, uint32_t value)
    {
        dut.offset = offset;
        dut.wdata = value;
        dut.access = dut.write_en = 1;
        tick();
        dut.access = dut.write_en = 0;
    }
    void reset()
    {
        dut.access = dut.write_en = dut.rst_n = 0;
        tick();
        dut.rst_n = 1;
        tick();
    }
    void job(unsigned m, unsigned n, unsigned k, unsigned misalign, bool interrupt = false)
    {
        constexpr unsigned a = 1, c = 640;
        unsigned b = 256 + misalign;
        memory.fill(0xa5);
        for (unsigned i = 0; i < m * k; ++i)
            memory[a + i] = (17 * i + 113) % 256;
        for (unsigned i = 0; i < n * k; ++i)
            memory[b + i] = (31 * i + 137) % 256;
        const auto original = memory;
        reads = writes = stalls = 0;
        reg(16, base + a);
        reg(20, base + b);
        reg(24, base + c);
        reg(28, m);
        reg(32, n);
        reg(36, k);
        reg(4, 1);
        bool done = false;
        for (unsigned i = 0; i < 4000 && !done; ++i) {
            if (interrupt && reads == 3) {
                reset();
                if (memory != original || dut.dma_valid)
                    throw std::runtime_error("reset did not cancel read");
                return;
            }
            tick();
            dut.clk = 0;
            dut.offset = 8;
            dut.eval();
            done = dut.rdata == 2;
        }
        const unsigned expected = k * (m + ((n == 4 && misalign == 0) ? 1 : n));
        if (!done || reads != expected || writes != m * n || stalls == 0)
            throw std::runtime_error("incorrect tile completion or transfer counts");
        for (unsigned r = 0; r < m; ++r)
            for (unsigned col = 0; col < n; ++col) {
                int32_t sum = 0;
                for (unsigned t = 0; t < k; ++t)
                    sum += int8_t(original[a + r * k + t]) * int8_t(original[b + t * n + col]);
                if (word(c + 4 * (r * n + col)) != uint32_t(sum))
                    throw std::runtime_error("dot product mismatch");
            }
        for (unsigned i = 0; i < memory.size(); ++i)
            if ((i < c || i >= c + 4 * m * n) && original[i] != memory[i])
                throw std::runtime_error("stray write");
        reg(4, 2);
    }
};

int main()
{
    Bench bench;
    bench.reset();
    bench.job(4, 4, 32, 0, true);
    unsigned cases = 0;
    for (unsigned m : {1, 2, 3, 4})
        for (unsigned n : {1, 2, 3, 4})
            for (unsigned k : {1, 13, 32})
                for (unsigned align : {0, 1, 2, 3}) {
                    bench.job(m, n, k, align);
                    ++cases;
                }
    std::cout << "{\"completed_tiles\":" << cases << ",\"mid_read_reset\":true}\n";
}
