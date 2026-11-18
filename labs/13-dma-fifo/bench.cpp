#include "Vdma_arbiter.h"
#include "verilated_vcd_c.h"
#include <array>
#include <cstdint>
#include <deque>
#include <iostream>
#include <random>
#include <stdexcept>
#include <utility>

int main(int argc, char **argv)
{
    if (argc != 2)
        return 2;
    Verilated::traceEverOn(true);
    Vdma_arbiter dut;
    VerilatedVcdC wave;
    dut.trace(&wave, 6);
    wave.open(argv[1]);
    std::mt19937 random(1313);
    std::deque<std::pair<unsigned, uint32_t>> pending;
    std::array<unsigned, 2> serial{}, completed{};
    unsigned canceled = 0, stalls = 0, simultaneous = 0, errors = 0, max_depth = 0, preferred = 0;
    std::array<unsigned, 64> memory{};
    unsigned offered = 0;
    for (unsigned cycle = 0; cycle < 2048; ++cycle) {
        dut.clk = 0;
        dut.rst_n = cycle != 0 && cycle != 43 && cycle != 765;
        // Each producer holds valid and payload until its own handshake.
        if (!dut.rst_n)
            offered = 0;
        else if (cycle < 2038)
            offered |= cycle < 75 ? 3 : random() % 4;
        dut.in_valid = offered;
        dut.mem_ready = cycle >= 2038 || (cycle > 50 && random() % 4 != 0);
        auto request = [](unsigned owner, unsigned seq) {
            // bit 31 selects a write; bits 30:24 encode the word address.
            return ((seq % 3 != 0 ? 1u : 0u) << 31) | (((seq * 11 + owner) % 68) << 24) |
                   (seq * 2 + owner);
        };
        dut.req0 = request(0, serial[0]);
        dut.req1 = request(1, serial[1]);
        dut.eval();
        if (!dut.rst_n) {
            canceled += pending.size();
            pending.clear();
            preferred = 0;
        } else {
            if (bool(dut.mem_valid) != !pending.empty())
                throw std::runtime_error("valid");
            bool pop = dut.mem_valid && dut.mem_ready;
            if (dut.mem_valid) {
                auto [owner, word] = pending.front();
                if (dut.mem_req != word || dut.mem_owner != owner)
                    throw std::runtime_error("order or stalled payload");
                if (pop) {
                    unsigned addr = (word >> 24) & 127;
                    if (addr >= memory.size())
                        ++errors;
                    else if (word >> 31)
                        memory[addr] = word & 0xffffff;
                    ++completed[owner];
                    pending.pop_front();
                } else
                    ++stalls;
            }
            auto mask = dut.in_valid & dut.in_ready;
            if (mask) {
                offered &= ~mask;
                unsigned owner = mask >> 1;
                if (mask == 3 || (dut.in_valid == 3 && owner != preferred))
                    throw std::runtime_error("arbitration");
                preferred = 1 - owner;
                pending.emplace_back(owner, owner ? dut.req1 : dut.req0);
                ++serial[owner];
                simultaneous += pop;
            }
            if (pending.size() > 4)
                throw std::runtime_error("overflow");
            max_depth = std::max(max_depth, (unsigned)pending.size());
        }
        wave.dump(2 * cycle);
        dut.clk = 1;
        dut.eval();
        wave.dump(2 * cycle + 1);
    }
    if (offered || !pending.empty() || !errors || !stalls || max_depth != 4 || !canceled ||
        !simultaneous || serial[0] + serial[1] != completed[0] + completed[1] + canceled)
        return 1;
    wave.close();
    std::cout << "{\"accepted\":[" << serial[0] << "," << serial[1] << "],\"completed\":["
              << completed[0] << "," << completed[1] << "],\"reset_canceled\":" << canceled
              << ",\"out_of_range_at_target\":" << errors << ",\"stalled\":" << stalls
              << ",\"simultaneous\":" << simultaneous << ",\"max_depth\":" << max_depth << "}\n";
}
