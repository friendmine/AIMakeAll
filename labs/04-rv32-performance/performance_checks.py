"""Validate the measured path against the copy-model oracle and independent RTL bus traces."""

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "03-rv32-generation"))
from trace_checks import LOGIT_TOLERANCE, Trace

PHASES = ("input_norm", "qkv", "attention", "attention_out", "ffn_norm_quant",
          "cpu_dot", "pack", "driver", "gather", "rescale", "gelu", "down", "final_norm_head")


def expected_matrix(tiles):
    cells = {}
    for tile in tiles:
        for i, value in enumerate(tile["sums"]):
            pos = (tile["row"] + i // tile["n"], tile["col"] + i % tile["n"])
            if pos in cells:
                raise ValueError(f"overlapping reference tiles at {pos}")
            cells[pos] = value
    return sorted(cells.items())


def verify_run(uart, counters, mmio, backend, profile, expected):
    trace = Trace(uart, backend)
    # All UART output happens after EOS. No tile may appear in the serial dump.
    events = [line.split() for line in counters.read_text().splitlines() if line.strip()]
    total_tiles = sum(len(step["tiles"]) for step in expected) if backend == "npu" else 0
    expected_events = ["tile"] * total_tiles + ["S", "T"] * len(expected) + ["finish"]
    if [row[0] for row in events] != expected_events:
        raise ValueError("unexpected device activity or incomplete serial dump")
    first_uart_cycle = int(events[total_tiles][1])
    previous_tile_end = -1
    tiles = iter(row[1:] for row in events[:total_tiles])
    bus = iter(tuple(int(v, 16) for v in row.split()) for row in mmio.read_text().splitlines())
    steps, all_logits = [], []
    for i, ref in enumerate(expected):
        trace.word("S", "step", i)
        cycles = trace.word("C", f"step {i} cycles")
        if cycles == 0:
            raise ValueError("empty timing interval")
        phase = {p: trace.word("F", p) for p in PHASES} if profile else {}
        if profile:
            inactive = ("pack", "driver", "gather") if backend == "cpu" else ("cpu_dot",)
            if sum(phase.values()) != cycles or any(phase[p] for p in inactive):
                raise ValueError(f"step {i}: invalid phase accounting")
            if any(phase[p] == 0 for p in phase if p not in inactive):
                raise ValueError(f"step {i}: missing active phase")
        matrix = expected_matrix(ref["tiles"])
        for pos, value in matrix:
            trace.word("P", f"step {i} accumulator {pos}", value)
        bits = [trace.word("L", f"step {i} logit {j}") for j in range(len(ref["logits"]))]
        scores = struct.unpack(f"<{len(bits)}f", struct.pack(f"<{len(bits)}I", *bits))
        errors = [abs(a - b) for a, b in zip(scores, ref["logits"])]
        if not all(e <= LOGIT_TOLERANCE for e in errors):
            raise ValueError(f"step {i}: logits diverged from the model")
        trace.word("T", "greedy token", ref["token"])
        all_logits.extend(bits)
        device_cycles = reads = write_bytes = waits = 0
        npu_tiles = ref["tiles"] if backend == "npu" else []
        for t in npu_tiles:
            addresses = [next(bus, ()) for _ in range(8)]
            offsets = [0x10010000 + offset for offset in (16, 20, 24, 28, 32, 36, 4, 4)]
            register_order = [a[0] for a in addresses if len(a) == 2]
            if register_order != offsets:
                raise ValueError(f"step {i}: incomplete MMIO register writes")
            if [a[1] for a in addresses[3:]] != [t["m"], t["n"], t["k"], 1, 2]:
                raise ValueError(f"step {i}: device descriptor differs from tile")
            event = next(tiles, [])
            if len(event) != 5:
                raise ValueError("missing tile counters")
            start, end, nr, nw, stalled = map(int, event)
            if not previous_tile_end < start <= end < first_uart_cycle:
                raise ValueError(f"step {i}: overlapping or late device activity")
            previous_tile_end = end
            duration = end - start + 1
            if (
                nr != (t["m"] + t["n"]) * t["k"]
                or nw != t["m"] * t["n"]
                or not 0 <= stalled <= duration - nr - nw
            ):
                raise ValueError(f"step {i}: invalid DMA counters")
            device_cycles += duration
            reads += nr
            write_bytes += 4 * nw
            waits += stalled
        if device_cycles > (phase["driver"] if profile else cycles):
            raise ValueError("device time exceeds its enclosing interval")
        step = dict(step=i, token=ref["token"], cycles=cycles, integers=len(matrix),
                    logits=len(bits), max_logit_error=max(errors), commands=len(npu_tiles),
                    device_cycles=device_cycles, dma_read_bytes=reads, dma_write_bytes=write_bytes,
                    dma_stall_cycles=waits)
        if profile:
            step["phase_cycles"] = phase
        steps.append(step)
    if sum(step["cycles"] for step in steps) > first_uart_cycle:
        raise ValueError("reported work exceeds RTL cycles before the serial dump")
    if any(next(stream, None) is not None for stream in (trace.lines, tiles, bus)):
        raise ValueError("unexpected output or device activity after expected work")
    return steps, all_logits
