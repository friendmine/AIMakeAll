"""Run the fixed Linear lesson; all optional backends consume identical packed tiles."""

import argparse
import ctypes
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from reference.int8 import matmul_int8, wrap_int32

M, K, N = 5, 257, 7
FULL = 4 * M * N + (M + N) * 256


def sample():
    # Off-grid dyadic inputs make quantization error reproducible, including ties.
    x = [
        [(((13 * i + 7 * p) % 29) - 14 + 0.25) / 8 for p in range(K)] for i in range(M)
    ]
    w = [
        [(((11 * j + 3 * p) % 23) - 11 + 0.5) * (j + 1) / 16 for p in range(K)]
        for j in range(N)
    ]
    bias = [(j - 3) / 8 for j in range(N)]
    return x, w, bias


def quantize(row, scale):
    return [max(-127, min(127, round(v / scale))) for v in row]


@dataclass
class Tile:
    start: int
    k: int
    a: list
    b: list

    def packed(self):
        return bytes(
            v & 255 for matrix in (self.a, self.b) for row in matrix for v in row
        )


def plan(x, w, budget, bad_layout=False):
    width = min(256, (budget - 4 * M * N) // (M + N))
    if width < 1:
        raise ValueError("budget too small for even one K element")
    packed_w = list(zip(*w))
    if bad_layout:
        flat = sum(w, [])
        packed_w = [flat[p : p + N] for p in range(0, len(flat), N)]
    return [
        Tile(
            p,
            min(width, K - p),
            [r[p : p + width] for r in x],
            [list(r) for r in packed_w[p : p + width]],
        )
        for p in range(0, K, width)
    ]


def direct(x, w, lo=0, hi=K):
    # Independent oracle reads the original W[N,K], never the packed B.
    return [
        sum(a * b for a, b in zip(row[lo:hi], col[lo:hi])) for row in x for col in w
    ]


def agree(stage, actual, expected):
    if len(actual) != len(expected):
        raise ValueError(f"{stage}: expected {len(expected)} cells, got {len(actual)}")
    for i, (got, want) in enumerate(zip(actual, expected)):
        if got != want:
            raise ValueError(
                f"{stage} cell[{i // N},{i % N}]: got {got}, expected {want}"
            )


def run_native(tiles, folder):
    library = folder / "kernel.so"
    subprocess.run(
        [
            os.environ.get("CC", "cc"),
            "-std=c11",
            "-O2",
            "-fPIC",
            "-shared",
            HERE / "kernel.c",
            "-o",
            library,
        ],
        check=True,
    )
    fn = ctypes.CDLL(str(library)).linear_tile
    i8, u32 = ctypes.c_int8, ctypes.c_uint32
    fn.argtypes = [ctypes.c_uint] * 3 + [ctypes.POINTER(i8)] * 2 + [ctypes.POINTER(u32)]
    fn.restype = None
    result = []
    for t in tiles:
        raw = t.packed()
        a = (i8 * (M * t.k)).from_buffer_copy(raw)
        b = (i8 * (N * t.k)).from_buffer_copy(raw, len(a))
        c = (u32 * (M * N))()
        fn(M, N, t.k, a, b, c)
        result.append([wrap_int32(v) for v in c])
    return result


def run_mac(tiles, binary):
    rows = []
    for t in tiles:
        data = f"{M} {N} {t.k}\n".encode() + t.packed()
        out = subprocess.run(
            [binary], input=data, stdout=subprocess.PIPE, check=True, timeout=30
        )
        rows.append([wrap_int32(int(v, 16)) for v in out.stdout.splitlines()])
    return rows


def fixture_header(tiles):
    lines = [
        f"#define ROWS_M {M}",
        f"#define COLS_N {N}",
        f"#define TILE_COUNT {len(tiles)}",
    ]
    entries = []
    for idx, t in enumerate(tiles):
        for name, matrix in [("a", t.a), ("b", t.b)]:
            values = ",".join(str(v) for row in matrix for v in row)
            lines.append(f"static const int8_t {name}{idx}[] = {{{values}}};")
        entries.append(f"{{{t.k},a{idx},b{idx}}}")
    lines.append(
        "static const struct { unsigned k; const int8_t *a,*b; } tiles[] = {"
        + ",".join(entries)
        + "};"
    )
    return "\n".join(lines) + "\n"


def run_guest(tiles, binary, folder):
    (folder / "fixture.h").write_text(fixture_header(tiles))
    elf = folder / "linear.elf"
    subprocess.run(
        [
            os.environ.get("RISCV_CC", "riscv64-unknown-elf-gcc"),
            "-march=rv32im",
            "-mabi=ilp32",
            "-mcmodel=medany",
            "-msmall-data-limit=0",
            "-mno-relax",
            "-ffreestanding",
            "-nostdlib",
            "-O1",
            "-I",
            folder,
            "-T",
            HERE / "guest.ld",
            HERE / "start.S",
            HERE / "guest.c",
            "-o",
            elf,
        ],
        check=True,
    )
    result = subprocess.run(
        [
            binary,
            "-M",
            "virt",
            "-m",
            "32M",
            "-smp",
            "1",
            "-bios",
            "none",
            "-kernel",
            elf,
            "-display",
            "none",
            "-serial",
            "stdio",
            "-monitor",
            "none",
            "-nic",
            "none",
            "-icount",
            "shift=0",
        ],
        capture_output=True,
        timeout=30,
    )
    if result.returncode:
        raise RuntimeError(
            f"guest exit {result.returncode}: {result.stderr.decode(errors='replace')}"
        )
    records = result.stdout.decode().splitlines()
    if any(not re.fullmatch("[PY][0-9a-f]{8}", v) for v in records):
        raise ValueError("bad UART trace")
    tags = "".join(v[0] for v in records)
    if tags != "P" * (M * N * len(tiles)) + "Y" * (M * N):
        raise ValueError("incomplete UART trace")
    vals = [wrap_int32(int(v[1:], 16)) for v in records]
    return [vals[i : i + M * N] for i in range(0, len(vals) - M * N, M * N)], vals[
        -M * N :
    ]


def execute(args, folder):
    x, w, bias = sample()
    xq = [quantize(row, 1 / 8) for row in x]
    wq = [quantize(row, (j + 1) / 16) for j, row in enumerate(w)]
    tiles = plan(xq, wq, args.budget, args.fault == "layout")
    digests = []
    refs = []
    for t in tiles:
        # Check input packing BEFORE running a backend so a shared exporter bug is visible.
        for p in range(t.k):
            for j in range(N):
                if t.b[p][j] != wq[j][t.start + p]:
                    raise ValueError(
                        f"layout B[{t.start + p},{j}]={t.b[p][j]}, W[{j},{t.start + p}]={wq[j][t.start + p]}"
                    )
        refs.append(direct(xq, wq, t.start, t.start + t.k))
        digests.append(hashlib.sha256(t.packed()).hexdigest())
    backends = {"python": [sum(matmul_int8(t.a, t.b), []) for t in tiles]}
    if args.native:
        backends["host-c"] = run_native(tiles, folder)
    if args.rtl:
        backends["verilated-mac"] = run_mac(tiles, args.rtl)
    if args.qemu:
        backends["rv32-mmio"], guest_y = run_guest(tiles, args.qemu, folder)
    integer = direct(xq, wq)
    y128 = [v * (i % N + 1) + round(128 * bias[i % N]) for i, v in enumerate(integer)]
    for name, partials in backends.items():
        if len(partials) != len(tiles):
            raise ValueError(
                f"{name}: expected {len(tiles)} tile results, got {len(partials)}"
            )
        for t, got, want in zip(tiles, partials, refs):
            agree(f"{name} K={t.start}+{t.k}", got, want)
        merged = [wrap_int32(sum(v)) for v in zip(*partials)]
        agree(name + " merge", merged, integer)
    if args.qemu:
        agree("guest final x128", guest_y, y128)
    fp = [v + bias[i % N] for i, v in enumerate(direct(x, w))]
    # Inputs and operations are dyadic and exact here within FP32's significand.
    report = dict(
        asset="linear257-v1",
        abi_version=1,
        shape=[M, K, N],
        budget=args.budget,
        live_packed_tile_bytes=max(len(t.packed()) + 4 * M * N for t in tiles),
        widths=[t.k for t in tiles],
        input_sha256=digests,
        backends=list(backends),
        partials=backends,
        y_times_128=y128,
        max_abs_quant_error=max(abs(v / 128 - f) for v, f in zip(y128, fp)),
    )
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(
        f"K tiles {report['widths']}, live tile bytes {report['live_packed_tile_bytes']}"
    )
    print(
        f"cell[0,0] partials {[p[0] for p in refs]}, Y={y128[0] / 128}, float={fp[0]}"
    )
    print(
        f"max quantization error {report['max_abs_quant_error']}; {M * N} cells agree: {', '.join(backends)}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--budget", type=int, default=FULL, help="packed A+B+C bytes per command"
    )
    parser.add_argument("--fault", choices=["layout"])
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--rtl", type=Path)
    parser.add_argument("--qemu", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as work:
        try:
            execute(args, Path(work))
        except (ValueError, RuntimeError, subprocess.SubprocessError, OSError) as exc:
            sys.exit(f"FAIL: {exc}")
