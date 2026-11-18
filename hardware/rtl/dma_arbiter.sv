// SPDX-License-Identifier: MIT
// Two producers share a four-entry FIFO and one external memory transaction port.
// A request commits only on mem_valid && mem_ready. Reset cancels queued work.
module dma_arbiter (
    input logic clk, rst_n,
    input logic [1:0] in_valid, output logic [1:0] in_ready,
    input logic [31:0] req0, req1,
    output logic mem_valid, input logic mem_ready,
    output logic [31:0] mem_req, output logic mem_owner
);
    logic [32:0] queue [0:3];
    logic [1:0] rd, wr;
    logic [2:0] used;
    logic preferred, grant;
    assign mem_valid = rst_n && used != 0;
    assign {mem_owner, mem_req} = queue[rd];
    wire pop = mem_valid && mem_ready;
    always_comb begin
        grant = in_valid[preferred] ? preferred : !preferred;
        in_ready = 0;
        if (rst_n && (used < 4 || pop)) in_ready[grant] = 1;
    end
    wire push = |(in_valid & in_ready);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            used <= 0;
            rd <= 0;
            wr <= 0;
            preferred <= 0;
        end else begin
            if (push) begin
                queue[wr] <= {grant, grant ? req1 : req0};
                wr <= wr + 1'b1;
                preferred <= !grant;
            end
            if (pop) rd <= rd + 1'b1;
            if (push && !pop) used <= used + 1'b1;
            if (!push && pop) used <= used - 1'b1;
        end
    end
    assert property (@(posedge clk) disable iff (!rst_n)
        mem_valid && !mem_ready |=> mem_valid && $stable({mem_req,mem_owner}));
    assert property (@(posedge clk) used <= 4);
endmodule
