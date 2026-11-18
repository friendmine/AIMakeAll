"""Compare guest diagnostics, bus writes and the RTL timing trace with the model reference."""

import re
import struct

LOGIT_TOLERANCE = 1e-4


class Trace:
    def __init__(self, data, backend):
        self.lines = iter(data.decode("ascii").splitlines())
        self.backend = backend

    def word(self, tag, where, expected=None):
        line = next(self.lines, "")
        if not re.fullmatch(tag + r"[0-9a-f]{8}", line):
            raise ValueError(f"{self.backend} {where}: expected {tag}, got {line!r}")
        v = int(line[1:], 16)
        if expected is not None and v != (expected & 0xFFFFFFFF):
            raise ValueError(
                f"{self.backend} {where}: got {v:08x}, expected {expected & 0xFFFFFFFF:08x}"
            )
        return v


def check_uart(data, backend, steps):
    trace = Trace(data, backend)
    addresses = {name: trace.word(name, "descriptor") for name in "ABC"}
    reports = []
    for index, step in enumerate(steps):
        trace.word("S", "generation step", index)
        count = 0
        for t in step["tiles"]:
            i, j = t["row"], t["col"]
            where = f"step {index} tile ({i},{j})"
            trace.word("I", where, i << 16 | j)
            trace.word("H", where + " shape", t["m"] << 16 | t["n"] << 8 | t["k"])
            trace.word("X", where + " activation bytes", t["a_hash"])
            trace.word("W", where + " packed weight bytes", t["b_hash"])
            for cell, expected in enumerate(t["sums"]):
                trace.word(
                    "P",
                    f"{where} output[{i + cell // t['n']},{j + cell % t['n']}]",
                    expected,
                )
                count += 1
        words = [
            trace.word("L", f"step {index} logit {j}")
            for j in range(len(step["logits"]))
        ]
        scores = struct.unpack("<11f", struct.pack("<11I", *words))
        errors = [abs(a - b) for a, b in zip(scores, step["logits"])]
        if not all(e <= LOGIT_TOLERANCE for e in errors):
            raise ValueError(f"{backend} step {index}: logit absolute errors {errors}")
        token = trace.word("T", f"step {index} greedy token", step["token"])
        reports.append(
            dict(
                step=index,
                token=token,
                commands=len(step["tiles"]),
                integers=count,
                logits=list(scores),
                max_logit_error=max(errors),
            )
        )
    if next(trace.lines, None) is not None:
        raise ValueError(f"{backend}: excess records after EOS")
    return addresses, reports


def check_counters(path, steps):
    lines = iter(path.read_text().splitlines())

    def fields(tag, n):
        values = next(lines, "").split()
        if len(values) != n + 1 or values[0] != tag:
            raise ValueError(f"RTL counters: expected {tag}, got {values}")
        return [int(v) for v in values[1:]]

    stages = []
    for step in steps:
        (start,) = fields("S", 1)
        if stages and start <= stages[-1]["token_cycle"]:
            raise ValueError("generation step precedes the previous token")
        commands = []
        previous = start
        for t in step["tiles"]:
            first, last, reads, writes, waits = fields("tile", 5)
            if (
                not previous < first <= last
                or not 0 <= waits <= last - first + 1 - reads - writes
                or reads != (t["m"] + t["n"]) * t["k"]
                or writes != t["m"] * t["n"]
            ):
                raise ValueError(
                    f"RTL transaction mismatch at row {t['row']}, col {t['col']}"
                )
            commands.append(
                dict(
                    start=first,
                    end=last,
                    cycles=last - first + 1,
                    dma_byte_reads=reads,
                    dma_word_writes=writes,
                    dma_wait_cycles=waits,
                )
            )
            previous = last
        (token,) = fields("T", 1)
        if token <= previous:
            raise ValueError("token emitted before device completion")
        stages.append(
            dict(
                start=start,
                token_cycle=token,
                elapsed_cycles=token - start,
                tiles=commands,
            )
        )
    (finish,) = fields("finish", 1)
    if finish <= stages[-1]["token_cycle"] or next(lines, None) is not None:
        raise ValueError("incomplete RTL finish")
    return stages


def check_mmio(qemu_log, rtl_log, addresses, steps):
    # Observe both buses independently of the UART diagnostics in the guest.
    regex = re.compile(
        r" addr 0x([0-9a-f]+) value 0x([0-9a-f]+) size 4 name 'aimakeall-npu'$"
    )
    qemu = []
    for line in qemu_log.read_text().splitlines():
        if not line.endswith("name 'aimakeall-npu'"):
            continue
        match = regex.search(line)
        if not match:
            raise ValueError("unexpected QEMU NPU access width or trace format")
        qemu.append(tuple(int(v, 16) for v in match.groups()))
    rtl = [
        tuple(int(v, 16) for v in line.split())
        for line in rtl_log.read_text().splitlines()
    ]
    a, b, c = (addresses[name] for name in "ABC")
    commands = [(a, b, c, 0, 4, 16), (c, b, c, 1, 4, 16)]  # two negative controls
    commands.extend(
        (a, b, c, t["m"], t["n"], t["k"]) for step in steps for t in step["tiles"]
    )
    base = 0x10010000
    for name, observed in [("QEMU", qemu), ("RTL", rtl)]:
        if len(observed) != 8 * len(commands):
            raise ValueError(
                f"{name}: incomplete MMIO write history ({len(observed)} writes)"
            )
        for index, descriptor in enumerate(commands):
            want = [(base + 16 + 4 * i, v) for i, v in enumerate(descriptor)] + [
                (base + 4, 1),
                (base + 4, 2),
            ]
            if observed[8 * index : 8 * index + 8] != want:
                raise ValueError(
                    f"{name}: MMIO descriptor/START/CLEAR mismatch at command {index}"
                )
    return len(qemu)
