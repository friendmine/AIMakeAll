// SPDX-License-Identifier: MIT
// Consume each A/B pair as it arrives. Each weight word is used exactly once per tile.
module projection_stream (
    input logic clk, rst_n, cmd_valid, output logic cmd_ready,
    input logic [1:0] cmd_last_row, cmd_last_col, input logic [4:0] cmd_last_k,
    input logic in_valid, output logic in_ready, input logic [31:0] in_data,
    output logic out_valid, input logic out_ready, output logic [1:0] out_row, out_col,
    output logic signed [31:0] out_data, output logic read_a, read_b, mac_fire
);
    typedef enum logic [1:0] {IDLE, FIRST, SECOND, DRAIN} phase_t;
    phase_t phase;
    logic [31:0] activation;
    logic [1:0] last_row,last_col;
    logic [4:0] remaining;
    wire accept = cmd_valid && cmd_ready;
    assign cmd_ready = rst_n && phase == IDLE;
    assign in_ready = rst_n && (phase==FIRST || phase==SECOND);
    assign mac_fire = rst_n && phase==SECOND && in_valid;
    assign out_valid = rst_n && phase==DRAIN;
    assign read_a=0;
    assign read_b=0;
    wire signed [31:0] acc[0:3][0:3];
    wire [3:0] active_rows=4'b1111 >> (2'd3-last_row), active_cols=4'b1111 >> (2'd3-last_col);
    for(genvar i=0;i<4;i++) begin: rows
        for(genvar j=0;j<4;j++) begin: cols
            mac_int8 pe(.clk,.rst_n,.clear(accept),.enable(mac_fire && active_rows[i] && active_cols[j]),
                        .a(activation[8*i+:8]),.b(in_data[8*j+:8]),.acc(acc[i][j]));
        end
    end
    assign out_data=acc[out_row][out_col];
    always_ff @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            phase<=IDLE; out_row<=0; out_col<=0; remaining<=0; last_row<=0; last_col<=0; activation<=0;
        end else case(phase)
            IDLE: if(accept) begin
                phase<=FIRST; last_row<=cmd_last_row;last_col<=cmd_last_col;remaining<=cmd_last_k;
                out_row<=0;out_col<=0;
            end
            FIRST: if(in_valid) begin activation<=in_data;phase<=SECOND;end
            SECOND: if(in_valid) begin
                if(remaining==0) phase<=DRAIN;
                else begin remaining<=remaining-1'b1;phase<=FIRST;end
            end
            DRAIN: if(out_ready) begin
                if(out_col!=last_col) out_col<=out_col+1'b1;
                else if(out_row!=last_row) begin out_row<=out_row+1'b1;out_col<=0;end
                else phase<=IDLE;
            end
        endcase
    end
endmodule
