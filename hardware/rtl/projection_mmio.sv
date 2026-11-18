// SPDX-License-Identifier: MIT
// v0 microtile subset. One byte-addressed DMA read per active lane, one full word per output.
module projection_mmio (
    input logic clk, rst_n, access, write_en,
    input logic [11:0] offset,
    input logic [31:0] wdata,
    output logic [31:0] rdata,
    output logic bus_error,
    output logic dma_valid, dma_write,
    output logic [31:0] dma_addr, dma_wdata,
    input logic dma_ready,
    input logic [31:0] dma_rdata, // aligned little-endian word containing dma_addr
    output logic tile_start, tile_finish
);
    localparam logic [31:0] RAM_BASE = 32'h80000000, RAM_END = 32'h82000000;
    typedef enum logic [2:0] {IDLE, START_TILE, FETCH, FEED, DRAIN, DONE, FAILED} state_t;
    state_t state;
    logic [31:0] a, b, c, m, n, k, error_code;
    logic [31:0] packed_word, acc;
    logic [1:0] lane, row_idx, col_idx;
    logic [4:0] depth_idx;
    logic rhs, tile_ready, in_ready, out_valid;
    wire busy = state != IDLE && state != DONE && state != FAILED;
    wire config_reg = offset >= 'h10 && offset <= 'h24 && offset[1:0] == 0;
    wire clear_cmd = offset == 4 && wdata == 2 && !busy;

    always_comb begin
        bus_error = 0;
        rdata = 0;
        case (offset)
            0: rdata = 1;
            8: rdata = busy ? 1 : state == DONE ? 2 : state == FAILED ? 4 : 0;
            12: rdata = error_code;
            16: rdata = a;
            20: rdata = b;
            24: rdata = c;
            28: rdata = m;
            32: rdata = n;
            36: rdata = k;
            default: bus_error = access;
        endcase
        if (access && write_en)
            bus_error = !(clear_cmd || (state == IDLE && (offset == 4 || config_reg)));
    end

    // Lengths below are only used after checking the small positive shape.
    wire [31:0] rows = {29'b0,m[2:0]}, cols = {29'b0,n[2:0]}, depth_len = {26'b0,k[5:0]};
    wire [31:0] length_a = rows*depth_len, length_b = depth_len*cols, length_c = (rows*cols)<<2;
    function automatic logic in_ram(input logic [31:0] address, length);
        in_ram = address >= RAM_BASE && address < RAM_END && length <= RAM_END-address;
    endfunction
    logic [2:0] invalid;
    always_comb begin
        invalid = 0;
        if (m == 0 || m > 4 || n == 0 || n > 4 || k == 0 || k > 32) invalid = 2;
        else if (!in_ram(a,length_a) || !in_ram(b,length_b) || !in_ram(c,length_c) || |c[1:0]) invalid = 3;
        else if ((c < a+length_a && a < c+length_c) || (c < b+length_b && b < c+length_c)) invalid = 4;
    end

    wire [31:0] depth = {27'b0,depth_idx}, idx = {30'b0,lane};
    always_comb begin
        dma_write = state == DRAIN && out_valid;
        dma_valid = state == FETCH || dma_write;
        if (state == DRAIN) dma_addr = c + (({30'b0,row_idx}*cols + {30'b0,col_idx}) << 2);
        else if (rhs) dma_addr = b + depth*cols + idx;
        else dma_addr = a + idx*depth_len + depth;
        dma_wdata = acc;
    end

    assign tile_start = state == START_TILE && tile_ready;
    assign tile_finish = dma_write && dma_ready && row_idx == m[1:0]-2'd1 && col_idx == n[1:0]-2'd1;
`ifdef AIM_STREAM_SOC
    projection_stream array4 (
`else
    projection_tile #(.BANKED(1'b1)) array4 (
`endif
        .clk, .rst_n, .cmd_valid(state == START_TILE), .cmd_ready(tile_ready),
        .cmd_last_row(m[1:0]-2'd1), .cmd_last_col(n[1:0]-2'd1), .cmd_last_k(k[4:0]-5'd1),
        .in_valid(state == FEED), .in_ready, .in_data(packed_word),
        .out_valid, .out_ready(state == DRAIN && dma_ready), .out_row(row_idx), .out_col(col_idx),
        .out_data(acc), .read_a(), .read_b(), .mac_fire()
    );

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            a <= 0; b <= 0; c <= 0; m <= 0; n <= 0; k <= 0; error_code <= 0;
            depth_idx <= 0; lane <= 0; rhs <= 0; packed_word <= 0;
        end else begin
            if (access && write_en && !bus_error) begin
                case (offset)
                    4: if (clear_cmd) begin
                        state <= IDLE;
                        error_code <= 0;
                    end else if (wdata != 1 || invalid != 0) begin
                        state <= FAILED;
                        error_code <= wdata != 1 ? 1 : {29'b0,invalid};
                    end else state <= START_TILE;
                    16: a <= wdata;
                    20: b <= wdata;
                    24: c <= wdata;
                    28: m <= wdata;
                    32: n <= wdata;
                    36: k <= wdata;
                    default: ;
                endcase
            end
            case (state)
                START_TILE: if (tile_ready) begin
                    state <= FETCH;
                    lane <= 0; depth_idx <= 0; rhs <= 0; packed_word <= 0;
                end
                FETCH: if (dma_ready) begin
                    packed_word[lane*8 +: 8] <= dma_rdata[dma_addr[1:0]*8 +: 8];
                    if (idx+1 == (rhs ? n : m)) state <= FEED;
                    else lane <= lane + 1'b1;
                end
                FEED: if (in_ready) begin
                    rhs <= !rhs;
                    lane <= 0;
                    packed_word <= 0;
                    state <= FETCH;
                    if (rhs) begin
                        if (depth+1 == k) state <= DRAIN;
                        else depth_idx <= depth_idx+1'b1;
                    end
                end
                DRAIN: if (tile_finish) state <= DONE;
                default: ;
            endcase
        end
    end
endmodule
