// SPDX-License-Identifier: MIT
// One output-stationary microtile. Each input word packs four signed bytes,
// lane 0 in bits 7:0. The loader accepts A[k], B[k] alternately.
module projection_tile #(
    parameter bit BANKED = 1'b0
) (
    input  logic clk, rst_n,
    input  logic cmd_valid,
    output logic cmd_ready,
    input  logic [1:0] cmd_last_row, cmd_last_col,
    input  logic [4:0] cmd_last_k, // inclusive, 0..31
    input  logic in_valid,
    output logic in_ready,
    input  logic [31:0] in_data,
    output logic out_valid,
    input  logic out_ready,
    output logic [1:0] out_row, out_col,
    output logic signed [31:0] out_data,
    output logic read_a, read_b, mac_fire // observation points for cycle accounting
);
    typedef enum logic [2:0] {IDLE, LOAD, ISSUE, FINISH, DRAIN} state_t;
    state_t state;
    logic [1:0] last_row, last_col;
    logic [4:0] last_k, index_k;
    logic rhs, pair_pending;
    logic [31:0] a_word, b_word;
    wire accept = cmd_valid && cmd_ready;
    wire store = in_valid && in_ready;
    assign cmd_ready = rst_n && state == IDLE;
    assign in_ready  = rst_n && state == LOAD;
    assign out_valid = rst_n && state == DRAIN;
    assign read_a = rst_n && state == ISSUE && (BANKED || !rhs);
    assign read_b = rst_n && state == ISSUE && (BANKED || rhs);
    assign mac_fire = rst_n && pair_pending;

    // Same 256-byte capacity and 32-bit load interface in both configurations.
    if (BANKED) begin : banks
        logic [31:0] a_mem [0:31], b_mem [0:31];
        always_ff @(posedge clk) begin
            if (store && !rhs) a_mem[index_k] <= in_data;
            if (store && rhs)  b_mem[index_k] <= in_data;
            if (read_a) a_word <= a_mem[index_k];
            if (read_b) b_word <= b_mem[index_k];
        end
    end else begin : shared
        logic [31:0] mem [0:63];
        logic [31:0] word_q, saved_a;
        always_ff @(posedge clk) begin
            if (store) mem[{index_k, rhs}] <= in_data;
            if (read_a || read_b) word_q <= mem[{index_k, rhs}];
            if (read_b) saved_a <= word_q; // A arrived on the previous clock
        end
        assign a_word = saved_a;
        assign b_word = word_q;
    end

    wire signed [31:0] acc [0:3][0:3];
    wire [3:0] active_rows = 4'b1111 >> (2'd3 - last_row);
    wire [3:0] active_cols = 4'b1111 >> (2'd3 - last_col);
    for (genvar i = 0; i < 4; i++) begin : rows
        for (genvar j = 0; j < 4; j++) begin : cols
            mac_int8 pe (
                .clk, .rst_n, .clear(accept),
                .enable(mac_fire && active_rows[i] && active_cols[j]),
                .a(a_word[i*8 +: 8]), .b(b_word[j*8 +: 8]), .acc(acc[i][j])
            );
        end
    end
    assign out_data = acc[out_row][out_col];

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            last_row <= 0;
            last_col <= 0;
            last_k <= 0;
            index_k <= 0;
            rhs <= 0;
            pair_pending <= 0;
            out_row <= 0;
            out_col <= 0;
        end else begin
            // Synchronous RAM output is consumed one edge after the B read.
            pair_pending <= read_b;
            case (state)
                IDLE: if (accept) begin
                    last_row <= cmd_last_row;
                    last_col <= cmd_last_col;
                    last_k <= cmd_last_k;
                    index_k <= 0;
                    rhs <= 0;
                    out_row <= 0;
                    out_col <= 0;
                    state <= LOAD;
                end
                LOAD: if (store) begin
                    rhs <= !rhs;
                    if (rhs) begin
                        if (index_k == last_k) begin
                            index_k <= 0;
                            state <= ISSUE;
                        end else index_k <= index_k + 1'b1;
                    end
                end
                ISSUE: begin
                    if (!BANKED) rhs <= !rhs;
                    if (read_b) begin
                        if (index_k == last_k) state <= FINISH;
                        else index_k <= index_k + 1'b1;
                    end
                end
                FINISH: state <= DRAIN;
                DRAIN: if (out_ready) begin
                    if (out_col != last_col) out_col <= out_col + 1'b1;
                    else if (out_row != last_row) begin
                        out_col <= 0;
                        out_row <= out_row + 1'b1;
                    end else state <= IDLE;
                end
                default: state <= IDLE;
            endcase
        end
    end
endmodule
