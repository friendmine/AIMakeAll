"""Replay exported FFN inputs on two Verilated tiles. Python standard library only."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

LAB = Path(__file__).resolve().parent
sys.path.insert(0, str(LAB.parents[1]))
from reference.int8 import matmul_int8  # noqa: E402 (standalone lab uses the repository reference)


def lane_word(values):
    return sum((v & 255) << (8 * lane) for lane, v in enumerate(values))


def project(binary, x, weight, *, bubbles=False, trace=None):
    """W is [output,input]; the independent oracle never reads a packed word."""
    if not weight or not x:
        raise ValueError("empty projection")
    m, n, k = len(x), len(weight), len(x[0])
    if not 1 <= k <= 32 or any(len(row) != k for row in weight):
        raise ValueError("requires a rectangular W and K in [1,32]")
    reference = matmul_int8(x, [list(col) for col in zip(*weight)])
    commands = []
    tiles = []
    for i in range(0, m, 4):
        for j in range(0, n, 4):
            rows, cols = min(4, m - i), min(4, n - j)
            tiles.append((i, j, rows, cols))
            commands.append(f"{rows} {cols} {k}")
            for p in range(k):
                a = lane_word(x[r][p] for r in range(i, i + rows))
                b = lane_word(weight[c][p] for c in range(j, j + cols))
                commands.append(f"{a:x} {b:x}")
    args = [binary]
    if bubbles:
        args.append("--bubbles")
    if trace is not None:
        args.extend(["--trace", trace])
    run = subprocess.run(
        args,
        input="\n".join(commands) + "\n",
        text=True,
        stdout=subprocess.PIPE,
        check=True,
        timeout=60,
    )
    lines = run.stdout.splitlines()
    if len(lines) != len(tiles):
        raise ValueError("missing or extra tile in simulator output")
    matrix = [[0] * n for _ in range(m)]
    cycles = reads = mac_edges = waits = 0
    for (i, j, rows, cols), line in zip(tiles, lines):
        data = [int(value) for value in line.split()]
        if len(data) != rows * cols + 4:
            raise ValueError("incomplete tile response")
        for offset, value in enumerate(data[:-4]):
            r, c = i + offset // cols, j + offset % cols
            if value != reference[r][c]:
                raise ValueError(
                    f"{binary}: output[{r},{c}]={value}, expected {reference[r][c]}"
                )
            matrix[r][c] = value
        cyc, rd, me, stall = data[-4:]
        cycles += cyc
        reads += rd
        mac_edges += me
        waits += stall
    stats = dict(
        shape_mkn=[m, k, n],
        commands=len(tiles),
        cells=m * n,
        cycles=cycles,
        useful_macs=m * n * k,
        mac_edges=mac_edges,
        local_read_bytes=4 * reads,
        input_bytes=8 * k * len(tiles),
        output_bytes=4 * m * n,
        handshake_wait_cycles=waits,
    )
    return matrix, stats


def run_cases(asset, shared, banked, output, prefill_rows=None):
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for model in asset["models"]:
        for name, x in model["inputs"].items():
            if name == "prefill" and prefill_rows is not None:
                if not 1 <= prefill_rows <= len(x):
                    raise ValueError(f"prefill rows must be in [1,{len(x)}]")
                x = x[:prefill_rows]
            stats = {}
            for label, binary in [("shared", shared), ("banked", banked)]:
                trace = output / f"{label}.vcd" if not records else None
                _, stats[label] = project(binary, x, model["weight_i8"], trace=trace)
            records.append(dict(width=model["width"], workload=name, results=stats))
            print(
                f"FFN {model['width']} {name}: {stats['shared']['cells']} cells, "
                f"{stats['shared']['cycles']} -> {stats['banked']['cycles']} cycles, "
                f"{stats['shared']['local_read_bytes']} local read bytes"
            )
    return records


def check_protocol(shared, banked):
    for binary, banked_reads in [(shared, False), (banked, True)]:
        for m, k, n in [(1, 1, 1), (5, 7, 3), (4, 32, 4)]:
            x = [[[-128, 127, 0, 1][(i + p) % 4] for p in range(k)] for i in range(m)]
            w = [[[127, -128, 1, 0][(j + p) % 4] for p in range(k)] for j in range(n)]
            for bubbles in [False, True]:
                _, s = project(binary, x, w, bubbles=bubbles)
                # cmd + 2K writes + K or 2K reads + final MAC + valid outputs
                expected = s["commands"] * (2 + (3 if banked_reads else 4) * k) + m * n
                if s["cycles"] != expected + s["handshake_wait_cycles"]:
                    raise ValueError("cycle accounting failed")
                if s["local_read_bytes"] != 8 * k * s["commands"]:
                    raise ValueError("read traffic mismatch")
    print(
        "PASS integer extremes, K=1/32, row/column tails, input gaps, output stalls and reset"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shared", type=Path, required=True)
    parser.add_argument("--banked", type=Path, required=True)
    parser.add_argument("--asset", type=Path, default=LAB / "projection-fixture.json")
    parser.add_argument(
        "--prefill-rows", type=int, help="replay only the first N prefill rows"
    )
    parser.add_argument(
        "--expected", type=Path, help="verify archived asset and default cycle counts"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    check_protocol(args.shared, args.banked)
    if args.expected and args.prefill_rows is not None:
        parser.error("verify the full fixture without --prefill-rows")
    payload = args.asset.read_bytes()
    asset = json.loads(payload)
    records = run_cases(asset, args.shared, args.banked, args.output, args.prefill_rows)
    if args.expected:
        expected = json.loads(args.expected.read_text())
        if (
            expected["fixture_sha256"] != hashlib.sha256(payload).hexdigest()
            or records != expected["hardware"]
        ):
            raise ValueError(
                "asset digest or RTL counters differ from the archived run"
            )
    (args.output / "replay.json").write_text(json.dumps(records, indent=2) + "\n")
