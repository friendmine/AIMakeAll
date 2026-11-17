// SPDX-License-Identifier: MIT
#include "Vmac_int8.h"
#include "verilated.h"
#include <cstdint>
#include <cstdlib>
#include <iostream>

static void tick(Vmac_int8 &dut) {
    dut.clk = 0;
    dut.eval();
    dut.clk = 1;
    dut.eval();
}

static void expect(Vmac_int8 &dut, uint32_t expected, const char *label) {
    if (dut.acc != expected) {
        std::cerr << "FAIL " << label << ": got " << dut.acc
                  << ", expected " << expected << '\n';
        std::exit(1);
    }
}

int main(int argc, char **argv) {
    Verilated::commandArgs(argc, argv);
    Vmac_int8 dut;
    dut.rst_n = 1;
    dut.clear = 0;
    dut.enable = 0;
    dut.a = 0;
    dut.b = 0;
    dut.eval();
    dut.rst_n = 0;
    dut.eval();
    expect(dut, 0, "asynchronous reset");
    dut.rst_n = 1;
    dut.enable = 1;
    uint32_t expected = 0;
    // Exhaustive signed operand pairs, checking each accumulation.
    for (int a = -128; a <= 127; ++a) {
        for (int b = -128; b <= 127; ++b) {
            dut.a = static_cast<uint8_t>(a);
            dut.b = static_cast<uint8_t>(b);
            expected += static_cast<uint32_t>(a * b);
            tick(dut);
            expect(dut, expected, "signed accumulation");
        }
    }
    dut.enable = 0;
    tick(dut);
    expect(dut, expected, "disabled hold");
    dut.clear = 1;
    dut.enable = 1;
    tick(dut);
    expect(dut, 0, "clear beats enable");
    dut.clear = 0;
    dut.a = 128; // INT8 -128 bit pattern
    dut.b = 128;
    expected = 0;
    for (int i = 0; i < 131073; ++i) {
        expected += 16384u;
        tick(dut);
        expect(dut, expected, "INT32 overflow");
    }
    dut.rst_n = 0;
    dut.eval();
    expect(dut, 0, "reset nonzero accumulator");
    dut.final();
    std::cout << "PASS: all INT8 pairs, hold, clear, reset, INT32 overflow\n";
}
