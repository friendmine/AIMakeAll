"""Verify guest values and assign independently observed RTL events to request windows."""

from collections import deque
import hashlib
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "03-rv32-generation"))
from trace_checks import LOGIT_TOLERANCE, Trace


def require(condition, message):
    if not condition:
        raise ValueError(message)


def within(events, start, end):
    """Consume every event up to this window end, rejecting anything in the gap."""
    rows = []
    while events and events[0][0] <= end:
        row = events.popleft()
        require(row[0] > start, f"bus event outside request at cycle {row[0]}")
        rows.append(row)
    return rows


def check_cache(stores, expected, first_start):
    seen = {}
    for cycle, offset, mask, data in stores:
        require(cycle < first_start and offset % 4 == 0 and 0 < mask < 16,
                f"late or malformed cache store at {cycle}")
        for lane in range(4):
            if mask & (1 << lane):
                pos = offset + lane
                require(pos not in seen, f"duplicate store at {pos}")
                seen[pos] = (data >> (8*lane)) & 255
    require(seen == dict(enumerate(expected)), "packed cache writes differ in content or extent")
    return len(seen)


def verify(raw, counters, mmio, stores, cases, models, symbols):
    trace = Trace(raw, "RTL")
    events = deque(line.split() for line in counters.read_text().splitlines())
    bus = deque((int(c), int(a, 16), int(v, 16))
                for a, v, c in (line.split() for line in mmio.read_text().splitlines()))
    cache = deque(tuple(map(int, row.split())) for row in stores.read_text().splitlines())
    all_scores, requests = {}, []
    generation = dma_total = 0

    def event(tag, count):
        row = events.popleft() if events else []
        require(len(row) == count+1 and row[0] == tag, f"expected RTL {tag}, got {row}")
        return tuple(map(int, row[1:]))

    for index, (name, width, status, hit) in enumerate(cases):
        start, before = event("R", 2)
        trace.word("R", "request", index)
        trace.word("V", name + " loader status", status)
        require(before == dma_total, "DMA activity outside a request")
        result = dict(input=name, width=width, status=status, cache_hit=hit)
        model = models.get(width)
        steps = model["steps"] if model else []
        if model:
            trace.word("H", "prepack hit", hit)
            generation += int(not hit)
            trace.word("N", "active width", width)
            trace.word("X", "activation scale", model["sx_bits"])
            for j, bits in enumerate(model["sw_bits"]):
                trace.word("W", f"weight scale {j}", bits)
        tiles, scores, tokens = [], [], []
        sums = bytearray()
        reads = writes = 0
        previous = start
        max_error = 0.
        for s, step in enumerate(steps):
            (step_start,) = event("S", 1)
            require(previous < step_start, "step boundary out of order")
            previous = step_start
            trace.word("S", "step", s)
            for tile in step["tiles"]:
                first, last, nr, nw, stalls = event("tile", 5)
                m, n, k = (tile[key] for key in ("m", "n", "k"))
                require(previous < first <= last and nr == (m+n)*k and nw == m*n
                        and 0 <= stalls <= last-first+1-nr-nw, "RTL tile or DMA mismatch")
                tiles.append((first, last, tile))
                previous = last
                reads += nr
                writes += nw
                for cell, value in enumerate(tile["sums"]):
                    bits = trace.word("P", f"{name} step {s} tile ({tile['row']},{tile['col']}) cell {cell}", value)
                    sums.extend(struct.pack("<I", bits))
            bits = [trace.word("L", f"{name} step {s} logit {j}") for j in range(11)]
            scores.extend(bits)
            decoded = struct.unpack("<11f", struct.pack("<11I", *bits))
            errors = [abs(x-y) for x, y in zip(decoded, step["logits"])]
            require(all(e <= LOGIT_TOLERANCE for e in errors), f"{name} step {s} logit error {errors}")
            max_error = max(max_error, *errors)
            tokens.append(trace.word("T", "greedy token", step["token"]))
            (previous_token,) = event("T", 1)
            require(previous < previous_token, "token before tile completion")
            previous = previous_token
        trace.word("G", "committed cache generation", generation)
        trace.word("Z", "request end", index)
        end, dma_total = event("Z", 2)
        require(previous < end and dma_total-before == reads+writes, "unaccounted DMA activity")
        registers = within(bus, start, end)
        require(len(registers) == 8*len(tiles), f"{name}: unexpected number of NPU writes")
        for i, (first, last, tile) in enumerate(tiles):
            group = registers[8*i:8*i+8]
            values = [symbols["tile_a"], symbols["packed_weights"] + tile["col"]*16,
                      symbols["tile_c"], tile["m"], tile["n"], tile["k"], 1, 2]
            offsets = [16, 20, 24, 28, 32, 36, 4, 4]
            require([(a, v) for _, a, v in group] == [(0x10010000+off, v) for off, v in zip(offsets, values)]
                    and group[6][0] <= first <= last <= group[7][0], "MMIO descriptor or timing mismatch")
        cold_bytes = model["packed"] if model and not hit else b""
        count = check_cache(within(cache, start, end), cold_bytes, registers[0][0] if registers else end)
        result.update(cache_generation=generation, cache_written_bytes=count, commands=len(tiles),
                      mmio_writes=len(registers), dma_read_bytes=reads, dma_write_bytes=4*writes,
                      checked_scale_words=len(model["sw_bits"])+1 if model else 0,
                      checked_integers=len(sums)//4, checked_logits=len(scores), tokens=tokens,
                      rtl_window=dict(start_cycle=start, end_cycle=end,
                                      dma_beats_before=before, dma_beats_after=dma_total))
        if model:
            score_bytes = struct.pack(f"<{len(scores)}I", *scores)
            require(all_scores.setdefault(width, score_bytes) == score_bytes, "repeat changed RV32 logit bits")
            result.update(first_int32=struct.unpack_from("<i", sums)[0], projection_sha256=hashlib.sha256(sums).hexdigest(),
                          max_logit_error=max_error, logits_sha256=hashlib.sha256(score_bytes).hexdigest())
        requests.append(result)

    finish, final_dma = event("finish", 2)
    require(finish > end and final_dma == dma_total and not events and not cache and not bus,
            "extra RTL activity after final request")
    require(next(trace.lines, None) is None, "extra UART records")
    require(all_scores.keys() == models.keys(), "missing expected model outputs")
    require(len(set(all_scores.values())) == len(models), "different models produced identical scores")
    return requests
