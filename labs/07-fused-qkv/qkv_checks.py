"""Compare RV32 results to the host model and account for every independent bus event."""

from collections import deque
import hashlib
import struct

from check_switch import LOGIT_TOLERANCE, Trace, check_cache, require, within

MODES = {"qkv-fp32": 3, "qkv-int8": 4, "qkv-npu": 5}


def scalar(bits):
    return struct.unpack("<f", struct.pack("<I", bits))[0]


def check_numbers(trace, mode, model, width):
    ref = model["fp32" if mode == "qkv-fp32" else "int8"]
    for tag, key in (("X", "qkv_scales"), ("W", "ffn_scales")):
        for i, word in enumerate(model[key]):
            trace.word(tag, f"{key}[{i}]", word)
    digest = hashlib.sha256()
    errors = dict.fromkeys(("L", "F", "K", "Y"), 0.0)

    def read_floats(tag, expected, position):
        words = []
        for j, value in enumerate(expected):
            where = f"{tag}[{position},{j}]"
            bits = trace.word(tag, where)
            error = abs(scalar(bits)-value)
            require(error <= LOGIT_TOLERANCE, f"{where} absolute error {error}")
            errors[tag] = max(errors[tag], error)
            words.append(bits)
        digest.update(struct.pack(f"<{len(words)}I", *words))
        return words

    def read_ints(tag, expected, r):
        words = [trace.word(tag, f"{tag}[{r},{j}]", value) for j, value in enumerate(expected)]
        digest.update(struct.pack(f"<{len(words)}I", *words))

    intervals, tokens = [], []
    for s in range(4):
        intervals.append((trace.word("U", "step start"), trace.word("E", "token cycle")))
        tokens.append(trace.word("J", "selected token", ref["tokens"][s]))
        read_floats("L", ref["logits"][s], s)
    for r in range(8):
        if mode != "qkv-fp32":
            read_ints("I", ref["I"][r], r)
        fused = read_floats("F", ref["F"][r], r)
        k = read_floats("K", ref["K"][r], r)
        v = read_floats("Y", ref["Y"][r], r)
        require(k == fused[16:32] and v == fused[32:48], "KV differs from the actual projected K/V")
        read_ints("P", ref["P"][r], r)
    return intervals, dict(tokens=tokens, output_sha256=digest.hexdigest(), max_abs_error=errors,
                           checked_qkv_int32=384 if mode != "qkv-fp32" else 0,
                           checked_qkv_floats=384, checked_kv_floats=256, checked_ffn_int32=8*width,
                           checked_logits=44, checked_scales=49+1+width)


def check_device(mode, width, symbols, intervals, tiles, mmio):
    """The QKV and FFN descriptor order, buffers and tile geometry come from the model shapes."""
    commands = []
    dma_beats = 0
    for s, (begin, end) in enumerate(intervals):
        rows = 5 if s == 0 else 1
        layers = [("activation", width, 768)]
        if mode == "qkv-npu":
            layers.insert(0, ("qkv_input", 48, 0))
        step_count = 0
        previous = begin
        for activation, channels, cache_offset in layers:
            for row in range(0, rows, 4):
                m = min(4, rows-row)
                for col in range(0, channels, 4):
                    require(bool(tiles) and len(mmio) >= 8, "missing tile or NPU writes")
                    start, finish, reads, writes, stalls = tiles.popleft()
                    group = [mmio.popleft() for _ in range(8)]
                    values = [symbols[activation]+16*row, symbols["packed"]+cache_offset+16*col,
                              symbols["tile_c"], m, 4, 16, 1, 2]
                    offsets = (16, 20, 24, 28, 32, 36, 4, 4)
                    require([(a, v) for _, a, v in group] ==
                            [(0x10010000+o, v) for o, v in zip(offsets, values)],
                            f"wrong descriptor step {s} {activation} row {row} col {col}")
                    times = [t for t, _, _ in group]
                    require(times == sorted(set(times)) and previous < times[0]
                            and times[6] <= start <= finish < times[7] < end, "tile outside compute window")
                    require(reads == (m+4)*16 and writes == m*4
                            and 0 <= stalls <= finish-start+1-reads-writes, "wrong DMA traffic")
                    previous = times[7]
                    dma_beats += reads+writes
                    step_count += 1
        commands.append(step_count)
    require(not tiles and not mmio, "unexpected device activity in request")
    return commands, dma_beats


def verify(mode, cases, golden, symbols, raw, counters, bus, stores):
    trace = Trace(raw, mode)
    trace.word("M", "backend", MODES[mode])
    events = deque(row.split() for row in counters.read_text().splitlines())
    registers = deque((int(t), int(a, 16), int(v, 16))
                      for a, v, t in (line.split() for line in bus.read_text().splitlines()))
    cache = deque(tuple(map(int, row.split())) for row in stores.read_text().splitlines())

    def event(tag, count):
        row = events.popleft() if events else []
        require(len(row) == count+1 and row[0] == tag, f"expected {tag}, got {row}")
        return tuple(map(int, row[1:]))

    generation = last_end = dma_total = 0
    repeated, rows = {}, []
    for index, (name, width, status, hit) in enumerate(cases):
        begin, before = event("R", 2)
        tiles = deque()
        while events and events[0][0] == "tile":
            tiles.append(event("tile", 5))
        end, after = event("Z", 2)
        require(last_end < begin < end and before == dma_total, "device activity between requests")
        trace.word("R", "request start", index)
        trace.word("Z", "request end", index)
        trace.word("V", "loader status", status)
        generation += int(hit is False)
        trace.word("G", "cache generation", generation)
        start, validated, ready = [trace.word(t, "loader cycle") for t in "ABC"]
        require(begin < start < validated <= ready < end, "loader timing outside request")
        req = dict(input=name, width=width, status=status, cache_hit=hit, cache_generation=generation,
                   validation_cycles=validated-start, selection_cycles=ready-validated)
        want_qkv = want_ffn = b""
        intervals = []
        if width:
            model = golden[width]
            trace.word("H", "cache hit", hit)
            trace.word("N", "active width", width)
            intervals, numbers = check_numbers(trace, mode, model, width)
            previous = ready
            for left, right in intervals:
                require(previous < left < right < end, "generation timing outside request")
                previous = right
            req.update(**numbers, first_token_cycles=intervals[0][1]-start,
                       step_cycles=[b-a for a, b in intervals], request_cycles=intervals[-1][1]-start)
            require(repeated.setdefault(width, numbers["output_sha256"]) == numbers["output_sha256"],
                    "repeat or recovery changed numeric output")
            if not hit:
                want_ffn = model["packed_ffn"]
                if mode == "qkv-npu":
                    want_qkv = model["packed_qkv"]

        writes = within(cache, begin, end)
        qkv, ffn = [], []
        for t, offset, mask, data in writes:
            require(validated < t < ready, "cache write outside select/pack interval")
            if offset < 768:
                qkv.append((t, offset, mask, data))
            else:
                ffn.append((t, offset-768, mask, data))
        req["qkv_cache_written_bytes"] = check_cache(qkv, want_qkv, ready)
        req["ffn_cache_written_bytes"] = check_cache(ffn, want_ffn, ready)
        mmio = deque(within(registers, begin, end))
        req["mmio_writes"] = len(mmio)
        commands, beats = check_device(mode, width, symbols, intervals, tiles, mmio)
        require(after-before == beats, "unaccounted DMA handshakes")
        req.update(commands=sum(commands), step_commands=commands, dma_beats=beats,
                   rtl_window=[begin, end, before, after])
        last_end, dma_total = end, after
        rows.append(req)
    finish, final_beats = event("finish", 2)
    require(finish > last_end and final_beats == dma_total and not events and not cache and not registers
            and next(trace.lines, None) is None, "unaccounted events after final request")
    return rows


def compare_modes(modes):
    comparisons = []
    for group in ("requests", "recovery"):
        paths = {m: run[group] if group == "requests" else [run[group]] for m, run in modes.items()}
        for fp, cpu, npu in zip(*(paths[m] for m in MODES)):
            require(cpu["output_sha256"] == npu["output_sha256"], "integer paths differ bit for bit")
            row = dict(input=fp["input"], width=fp["width"], cache_hit=fp["cache_hit"])
            for key in ("first_token_cycles", "decode_cycles", "request_cycles"):
                a, b, c = [sum(r["step_cycles"][1:]) if key == "decode_cycles" else r[key]
                           for r in (fp, cpu, npu)]
                row[key] = dict(fp32=a, cpu_int8=b, npu_int8=c, saved_vs_fp32=a-c, saved_vs_cpu_int8=b-c)
            comparisons.append(row)
    return comparisons
