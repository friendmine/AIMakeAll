// SPDX-License-Identifier: MIT
#ifdef STREAM_TILE
#include "Vprojection_stream.h"
using Tile = Vprojection_stream;
static constexpr bool streaming = true;
#else
#include "Vprojection_tile.h"
using Tile = Vprojection_tile;
static constexpr bool streaming = false;
#endif
#include "verilated_vcd_c.h"
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string>

static void require(bool condition, const char *message) {
    if (!condition) throw std::runtime_error(message);
}

struct Bench {
    Tile dut;
    VerilatedVcdC trace;
    uint64_t time = 0;

    void tick() {
        for (int clk : {0, 1}) {
            dut.clk = clk;
            dut.eval();
            if (trace.isOpen()) trace.dump(time);
            ++time;
        }
        dut.clk = 0;
        dut.eval();
    }

    void reset() {
        dut.cmd_valid = 0;
        dut.in_valid = 0;
        dut.out_ready = 0;
        dut.rst_n = 0;
        tick();
        dut.rst_n = 1;
        dut.eval();
        require(dut.cmd_ready && !dut.out_valid, "reset did not clear pending command");
    }

    void command(unsigned m, unsigned n, unsigned k) {
        require(dut.cmd_ready, "command not ready");
        dut.cmd_last_row = m - 1;
        dut.cmd_last_col = n - 1;
        dut.cmd_last_k = k - 1;
        dut.cmd_valid = 1;
        tick();
        dut.cmd_valid = 0;
    }

    void abort_cases() {
        // Reset during load, while reads are pending, and on a stalled output.
        for (int phase = 0; phase < 3; ++phase) {
            command(2, 2, 3);
            dut.in_valid = 1;
            dut.in_data = 0x7f8081ff;
            for (int i = 0; i < (phase == 0 ? 3 : (streaming && phase == 1 ? 5 : 6)); ++i) tick();
            dut.in_valid = 0;
            if (phase == 1 && !streaming) {
                for (int i = 0; i < 3 && !dut.mac_fire; ++i) tick();
                require(dut.mac_fire, "read pipeline has no pending MAC");
            }
            if (phase == 2) {
                for (int i = 0; i < 12 && !dut.out_valid; ++i) tick();
                require(dut.out_valid, "stalled output never appeared");
            }
            reset();
            for (int i = 0; i < 8; ++i) {
                tick();
                require(!dut.out_valid && !dut.mac_fire && dut.cmd_ready, "late response after reset");
            }
        }
    }

    void tile(unsigned m, unsigned n, unsigned k, bool bubbles) {
        command(m, n, k);
        unsigned cycles = 1, words = 0, cells = 0, reads = 0, macs = 0, waits = 0;
        uint32_t value = 0, held_data = 0;
        unsigned held_index = 0;
        bool stalled = false;
        while (cells < m*n) {
            require(cycles < 512, "tile timed out");
            dut.in_valid = words < 2*k && (!bubbles || cycles % 4 != 0);
            dut.out_ready = !bubbles || cycles % 3 == 0;
            if (dut.in_valid && dut.in_ready) {
                require(bool(std::cin >> std::hex >> value >> std::dec), "truncated tile");
                dut.in_data = value;
                ++words;
            }
            dut.eval();
            reads += dut.read_a + dut.read_b;
            macs += dut.mac_fire;
            unsigned index = dut.out_row * n + dut.out_col;
            if (stalled) require(dut.out_valid && index == held_index && dut.out_data == held_data,
                                 "result changed under backpressure");
            stalled = dut.out_valid && !dut.out_ready;
            held_data = dut.out_data;
            held_index = index;
            waits += (dut.in_ready && !dut.in_valid) || stalled;
            if (dut.out_valid && dut.out_ready) {
                require(index == cells, "lost or out-of-order result");
                // Explicit sign extension for portable decimal output.
                int64_t word = dut.out_data;
                if (word >= (1LL << 31)) word -= 1LL << 32;
                std::cout << word << ' ';
                ++cells;
            }
            tick();
            ++cycles;
        }
        require(dut.cmd_ready && words == 2*k && reads == (streaming ? 0 : 2*k) && macs == k, "transaction count mismatch");
        std::cout << cycles << ' ' << reads << ' ' << macs << ' ' << waits << '\n';
    }
};

int main(int argc, char **argv) {
    try {
        bool bubbles = false;
        const char *trace_path = nullptr;
        for (int i = 1; i < argc; ++i) {
            std::string arg(argv[i]);
            if (arg == "--bubbles") bubbles = true;
            else if (arg == "--trace" && i+1 < argc) trace_path = argv[++i];
            else throw std::runtime_error("unexpected option");
        }
        if (trace_path) Verilated::traceEverOn(true);
        Bench bench;
        bench.reset();
        bench.abort_cases();
        if (trace_path) {
            bench.dut.trace(&bench.trace, 8);
            bench.trace.open(trace_path);
        }
        unsigned m, n, k;
        while (std::cin >> m) {
            require(bool(std::cin >> n >> k) && m && m <= 4 && n && n <= 4 && k && k <= 32,
                    "invalid tile shape");
            bench.tile(m, n, k, bubbles);
            if (bench.trace.isOpen()) bench.trace.close(); // only the first command
        }
        require(std::cin.eof(), "unexpected input");
        bench.dut.final();
    } catch (const std::exception &e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
