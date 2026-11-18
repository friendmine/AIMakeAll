// SPDX-License-Identifier: MIT
// Single-hart teaching system. RAM, UART and the test finisher are simulation ports.
module generation_soc (
    input logic clk, rst_n,
    output logic mem_valid, output logic [31:0] mem_addr, mem_wdata,
    output logic [3:0] mem_wstrb, input logic [31:0] mem_rdata,
    output logic trap, bus_error, tile_start, tile_finish, mmio_write,
    output logic dma_valid, dma_write, output logic [31:0] dma_addr, dma_wdata,
    input logic dma_ready, input logic [31:0] dma_rdata
);
    wire valid;
    wire io_select = mem_addr[31:12] == 20'h10010;
    wire [31:0] io_rdata;
    wire invalid_mmio;
    assign mem_valid = valid && !io_select;
    assign mmio_write = valid && io_select && mem_wstrb == 4'hf && !bus_error;
    assign bus_error = invalid_mmio || (io_select && valid && |mem_wstrb && mem_wstrb != 4'hf);
    picorv32 #(.PROGADDR_RESET(32'h80000000), .ENABLE_FAST_MUL(1), .ENABLE_DIV(1),
               .BARREL_SHIFTER(1)) cpu (
        .mem_instr(), .mem_la_read(), .mem_la_write(), .mem_la_addr(), .mem_la_wdata(), .mem_la_wstrb(),
        .pcpi_valid(), .pcpi_insn(), .pcpi_rs1(), .pcpi_rs2(), .eoi(), .trace_valid(), .trace_data(),
        .clk, .resetn(rst_n), .trap, .mem_valid(valid), .mem_ready(valid),
        .mem_addr, .mem_wdata, .mem_wstrb, .mem_rdata(io_select ? io_rdata : mem_rdata),
        .irq(32'b0), .pcpi_wr(1'b0), .pcpi_rd(32'b0), .pcpi_wait(1'b0), .pcpi_ready(1'b0)
    );
    projection_mmio device (
        .clk, .rst_n, .access(valid && io_select && (mem_wstrb == 0 || mem_wstrb == 4'hf)),
        .write_en(|mem_wstrb), .offset(mem_addr[11:0]), .wdata(mem_wdata), .rdata(io_rdata),
        .bus_error(invalid_mmio), .dma_valid, .dma_write, .dma_addr, .dma_wdata, .dma_ready,
        .dma_rdata, .tile_start, .tile_finish
    );
endmodule
