// SPDX-License-Identifier: MIT
module mac_int8 (
    input  logic clk,
    input  logic rst_n,
    input  logic clear,
    input  logic enable,
    input  logic signed [7:0] a,
    input  logic signed [7:0] b,
    output logic signed [31:0] acc
);
    logic signed [15:0] product;
    assign product = a * b;

    // Priority: reset > clear > accumulate > hold. Addition wraps at 32 bits.
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            acc <= '0;
        else if (clear)
            acc <= '0;
        else if (enable)
            acc <= acc + {{16{product[15]}}, product};
    end
endmodule
