// SPDX-License-Identifier: MIT
#include "Vgeneration_soc.h"
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

static constexpr uint32_t base = 0x80000000, size = 32u << 20;
struct Ram {
    std::vector<uint8_t> data = std::vector<uint8_t>(size);
    bool contains(uint32_t addr) const { return addr >= base && addr-base < size; }
    uint32_t read(uint32_t addr) const {
        if (!contains(addr)) throw std::runtime_error("RAM read outside guest memory");
        uint32_t at = (addr-base) & ~3u, value = 0;
        for (unsigned i = 0; i < 4; ++i) value |= uint32_t(data[at+i]) << (8*i);
        return value;
    }
    void write(uint32_t addr, uint32_t value, unsigned mask) {
        if (!contains(addr)) throw std::runtime_error("RAM write outside guest memory");
        uint32_t at = (addr-base) & ~3u;
        for (unsigned i = 0; i < 4; ++i)
            if ((mask >> i) & 1) data[at+i] = value >> (8*i);
    }
};

int main(int argc, char **argv) {
    try {
        if (argc != 4 && argc != 5 && argc != 7 && argc != 8 && argc != 9)
            throw std::runtime_error("usage: Vgeneration_soc guest.bin counters.txt mmio.txt [backend [weight_base stores.txt [models.bin [watch_bytes]]]]");
        const bool benchmark = argc >= 5;
        unsigned backend = 0;
        if (benchmark) {
            const std::string name(argv[4]);
            if (name == "npu") backend = 1;
            else if (name == "prepacked") backend = 2;
            else if (name == "qkv-fp32") backend = 3;
            else if (name == "qkv-int8") backend = 4;
            else if (name == "qkv-npu") backend = 5;
            else if (name != "cpu") throw std::runtime_error("unknown projection backend");
        }
        constexpr uint32_t backend_port = 0x10001000;
        Ram ram;
        std::ifstream image(argv[1], std::ios::binary | std::ios::ate);
        auto bytes = image.tellg();
        if (!image || bytes < 1 || bytes >= size) throw std::runtime_error("bad guest image");
        image.seekg(0);
        if (!image.read(reinterpret_cast<char *>(ram.data.data()), bytes))
            throw std::runtime_error("incomplete guest image");
        std::ofstream counts(argv[2]);
        std::ofstream mmio(argv[3]);
        if (!counts || !mmio) throw std::runtime_error("cannot open trace files");
        // An optional read-only RAM region holds request data independently of the ELF.
        const bool package_run = argc >= 8;
        constexpr uint32_t input_offset = 1u << 20;
        if (package_run) {
            std::ifstream inputs(argv[7], std::ios::binary | std::ios::ate);
            auto length = inputs.tellg();
            if (!inputs || length < 1 || length > size - input_offset - 4 || bytes > input_offset)
                throw std::runtime_error("bad model input region");
            ram.write(base + input_offset, uint32_t(length), 15);
            inputs.seekg(0);
            if (!inputs.read(reinterpret_cast<char *>(ram.data.data() + input_offset + 4), length))
                throw std::runtime_error("incomplete model inputs");
        }
        const bool watch_weights = argc >= 7;
        const auto watch_bytes = argc == 9 ? std::stoull(argv[8], nullptr, 0) : 512u;
        uint32_t weight_base = 0;
        std::ofstream stores;
        if (watch_weights) {
            auto addr = std::stoull(argv[5], nullptr, 0);
            if (addr < base || !watch_bytes || watch_bytes > size || addr > base + size - watch_bytes || (addr & 3))
                throw std::runtime_error("weight buffer outside aligned guest RAM");
            weight_base = uint32_t(addr);
            stores.open(argv[6]);
            if (!stores) throw std::runtime_error("cannot open weight store trace");
        }
        Vgeneration_soc dut;
        uint64_t dma_beats = 0, began = 0, reads = 0, writes = 0, stalls = 0;
        for (uint64_t cycle = 0; cycle < 150000000; ++cycle) {
            dut.rst_n = cycle >= 4;
            dut.clk = 0;
            // A periodic wait exercises the actual ready/valid DMA interface.
            dut.dma_ready = cycle % 7 != 0;
            dut.eval();
            dut.mem_rdata = 0;
            dut.dma_rdata = 0;
            if (dut.dma_valid && !dut.dma_write) dut.dma_rdata = ram.read(dut.dma_addr);
            if (dut.mem_valid && ram.contains(dut.mem_addr))
                dut.mem_rdata = ram.read(dut.mem_addr);
            else if (dut.mem_addr == 0x10000004)
                dut.mem_rdata = 0x2000;  // UART LSR[5] in byte lane 1.
            else if (benchmark && dut.mem_addr == backend_port)
                dut.mem_rdata = backend;
            dut.eval();
            if (dut.trap || dut.bus_error) throw std::runtime_error("CPU trap or unsupported MMIO");
            if (benchmark && backend == 0 && dut.dma_valid)
                throw std::runtime_error("unexpected DMA on the CPU-only path");
            if (dut.mmio_write) {
                mmio << std::hex << dut.mem_addr << ' ' << dut.mem_wdata;
                if (package_run) mmio << ' ' << std::dec << cycle;
                mmio << '\n';
            }
            if (dut.tile_start) { began = cycle; reads = writes = stalls = 0; }
            if (dut.dma_valid) {
                if (dut.dma_ready) ++dma_beats;
                if (package_run && dut.dma_write && dut.dma_addr >= base + input_offset)
                    throw std::runtime_error("DMA write to read-only model inputs");
                if (!dut.dma_ready) ++stalls;
                else if (dut.dma_write) { ram.write(dut.dma_addr, dut.dma_wdata, 15); ++writes; }
                else ++reads;
            }
            if (dut.tile_finish)
                counts << "tile " << began << ' ' << cycle << ' ' << reads << ' ' << writes
                       << ' ' << stalls << '\n';
            if (dut.mem_valid) {
                auto addr = dut.mem_addr, value = dut.mem_wdata;
                if (ram.contains(addr)) {
                    if (dut.mem_wstrb) {
                        if (package_run && addr >= base + input_offset)
                            throw std::runtime_error("CPU write to read-only model inputs");
                        ram.write(addr, value, dut.mem_wstrb);
                        uint32_t offset = (addr & ~3u) - weight_base;
                        if (watch_weights && offset < watch_bytes)
                            stores << cycle << ' ' << offset << ' ' << unsigned(dut.mem_wstrb)
                                   << ' ' << value << '\n';
                    }
                } else if (addr == 0x10000000 && dut.mem_wstrb == 1) {
                    char ch = char(value & 255);
                    if (package_run && (ch == 'R' || ch == 'Z'))
                        counts << ch << ' ' << cycle << ' ' << dma_beats << '\n';
                    if (ch == 'S' || ch == 'T') counts << ch << ' ' << cycle << '\n';
                    std::cout.put(ch);
                } else if (addr == 0x00100000 && dut.mem_wstrb == 15) {
                    counts << "finish " << cycle;
                    if (package_run) counts << ' ' << dma_beats;
                    counts << '\n';
                    dut.final();
                    if (value != 0x5555) throw std::runtime_error("guest failure " + std::to_string(value >> 16));
                    return 0;
                } else if (dut.mem_wstrb || (addr != 0x10000004 && !(benchmark && addr == backend_port))) {
                    throw std::runtime_error("unmapped CPU transaction " + std::to_string(addr));
                }
            }
            dut.clk = 1;
            dut.eval();
        }
        throw std::runtime_error("RTL generation timed out");
    } catch (const std::exception &e) { std::cerr << e.what() << '\n'; return 1; }
}
