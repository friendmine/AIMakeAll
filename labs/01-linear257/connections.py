"""Four short, offline exercises connected to the fixed Linear lesson."""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

from walkthrough import M, K, N, ROOT, FULL, direct, sample, plan, quantize


def training():
    x, w, b = sample()
    # Synthetic regression: one target per row and output channel.
    target = [((i % 9) - 4) / 4 for i in range(M * N)]

    def loss_and_errors():
        errors = [v + b[i % N] - target[i] for i, v in enumerate(direct(x, w))]
        return sum(e * e for e in errors) / (2 * M * N), errors

    before, errors = loss_and_errors()
    dy = [e / (M * N) for e in errors]
    dw = [
        [sum(dy[i * N + j] * x[i][p] for i in range(M)) for p in range(K)]
        for j in range(N)
    ]
    dx = [
        [sum(dy[i * N + j] * w[j][p] for j in range(N)) for p in range(K)]
        for i in range(M)
    ]
    db = [sum(dy[j::N]) for j in range(N)]
    for row, col, grad in [(w[0], 0, dw[0][0]), (x[1], 7, dx[1][7]), (b, 2, db[2])]:
        orig, step = row[col], 2**-12
        row[col] = orig + step
        hi, _ = loss_and_errors()
        row[col] = orig - step
        lo, _ = loss_and_errors()
        row[col] = orig
        assert math.isclose((hi - lo) / (2 * step), grad, abs_tol=1e-8)
    for j in range(N):
        b[j] -= 0.001 * db[j]
        for p in range(K):
            w[j][p] -= 0.001 * dw[j][p]
    after, _ = loss_and_errors()
    assert after < before
    # Explicit storage model: forward X,W,b,Y; backward reuses Y for dY.
    forward = 4 * (M * K + N * K + N + M * N)
    backward = forward + 4 * (M * K + N * K + N)  # store dX, dW and db
    print(f"training loss {before:.8f} -> {after:.8f}; gradient checks dW,dX,db PASS")
    print(
        f"FP32 modeled live bytes: forward {forward}, backward {backward}, "
        f"optional momentum buffer {4 * (N * K + N)}; forward MACs {M * N * K}, forward+backward {3 * M * N * K}"
    )


def bits_to_bytes(bits):
    return int(bits.ljust((len(bits) + 7) // 8 * 8, "0"), 2).to_bytes(
        (len(bits) + 7) // 8, "big"
    )


def encoding():
    symbols = [0, 1, 0, 2, 0, 1, 0, 3] * 4
    codes = ["0", "10", "110", "111"]
    encoded = "".join(codes[i] for i in symbols)
    payload = bits_to_bytes(encoded)
    stream = "".join(f"{byte:08b}" for byte in payload)[: len(encoded)]
    pending = ""
    decoded = []
    for bit in stream:
        pending += bit
        if pending in codes:
            decoded.append(codes.index(pending))
            pending = ""
    assert not pending and decoded == symbols
    q = [v // 2 for v in symbols]
    mse = sum((v - 2 * c) ** 2 for v, c in zip(symbols, q)) / len(q)

    def entropy(seq):
        probs = [n / len(seq) for n in Counter(seq).values()]
        return -sum(p * math.log2(p) for p in probs)

    triples = [v * 3 for v in encoded]

    def corrupt(word, n):
        return "".join(
            ("1" if bit == "0" else "0") if i < n else bit for i, bit in enumerate(word)
        )

    def vote(words):
        return "".join("1" if w.count("1") >= 2 else "0" for w in words)

    assert vote([corrupt(w, 1) for w in triples]) == encoded
    assert vote([corrupt(triples[0], 2), *triples[1:]]) != encoded
    print(
        f"coding {len(symbols) * 2} fixed bits -> {len(encoded)} lossless bits ({len(payload)} bytes); "
        f"{len(q)} quantized bits, MSE={mse}, I(X;Q)={entropy(q):.6f} bits/symbol"
    )
    print(
        f"repetition code {len(triples) * 3} bits; majority corrects one flip per triplet; two flips exposed"
    )


def link(zload, out, sample_phase, gain):
    if not math.isfinite(zload) or not 1 <= zload <= 1000:
        raise ValueError("load must be in [1,1000] ohms")
    if not math.isfinite(gain) or not 0 < gain <= 1:
        raise ValueError("one-way gain must be in (0,1]")
    # Far-end voltage for a line with finite-rise source and round-trip echoes.
    z0, zs, ui, delay = 50, 25, 16, 6
    gs, gl = (zs - z0) / (zs + z0), (zload - z0) / (zload + z0)
    seq = [0, 0, 0, 1, 0, 1, 1, 1, 1, 0, 0, 1, 1, 0, 1, 0] * 4
    launch = []
    level = 0
    for bit in seq:
        for _ in range(ui):
            level += 0.35 * (bit - level)
            launch.append(level * z0 / (zs + z0))
    v = [0.0] * len(launch)
    for i in range(len(v)):
        # t measured from the first possible arrival; initial line voltage is zero.
        v[i] = (1 + gl) * gain * launch[i]
        if i >= 2 * delay:
            v[i] += gs * gl * gain**2 * v[i - 2 * delay]
    eyes = [v[i * ui : (i + 1) * ui] for i in range(16, len(seq))]
    labels = seq[16:]
    heights = [
        min(t[p] for t, b in zip(eyes, labels) if b)
        - max(t[p] for t, b in zip(eyes, labels) if not b)
        for p in range(ui)
    ]
    if gl == 0:
        assert max(abs(gain * a - b) for a, b in zip(launch, v)) < 1e-12
    paths = []
    for trace in eyes:
        points = " ".join(
            f"{40 + p * 28},{180 - y * 130:.2f}" for p, y in enumerate(trace)
        )
        paths.append(
            f'<polyline points="{points}" fill="none" stroke="#167a96" opacity=".28"/>'
        )
    line_x = 40 + sample_phase * 28
    out.parent.mkdir(exist_ok=True, parents=True)
    out.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 220">'
        '<rect width="520" height="220" fill="white"/>'
        f'<text x="18" y="22">Load {zload:g} ohm / receiver voltage (V)</text>'
        f'<path d="M{line_x} 34v146" stroke="#ba540a" stroke-dasharray="4 3"/>'
        + "".join(paths)
        + '<text x="40" y="208">phase 0</text>'
        '<text x="395" y="208">15/16 UI</text></svg>\n'
    )
    print(
        f"line Zload={zload:g} ohm, reflection={gl:.3f}, gain={gain:g}, phase={sample_phase}/16 UI, "
        f"eye height={heights[sample_phase]:.6f} V; {out.name}"
    )


def handoff(interactive, reports):
    budgets = [FULL, FULL // 2]
    x, w, _ = sample()
    xq = [quantize(row, 1 / 8) for row in x]
    wq = [quantize(row, (j + 1) / 16) for j, row in enumerate(w)]
    sources = []
    for index, budget in enumerate(budgets):
        tiles = plan(xq, wq, budget)
        widths = [tile.k for tile in tiles]
        if reports:
            source = json.loads(reports[index].read_text())
            hashes = [hashlib.sha256(tile.packed()).hexdigest() for tile in tiles]
            if (
                source.get("asset") != "linear257-v1"
                or source.get("abi_version") != 1
                or source.get("shape") != [M, K, N]
                or source.get("budget") != budget
                or source.get("widths") != widths
                or source.get("input_sha256") != hashes
            ):
                raise ValueError(f"报告 {index} 的资产、预算或分块输入不匹配")
            partials = [
                direct(xq, wq, tile.start, tile.start + tile.k) for tile in tiles
            ]
            merged = [sum(column) for column in zip(*partials)]
            expected_y = [
                value * (i % N + 1) + 16 * (i % N - 3) for i, value in enumerate(merged)
            ]
            expected_backends = {"python", "host-c", "verilated-mac", "rv32-mmio"}
            observed = source.get("partials", {})
            if (
                set(source.get("backends", [])) != expected_backends
                or set(observed) != expected_backends
                or any(rows != partials for rows in observed.values())
                or source.get("y_times_128") != expected_y
            ):
                raise ValueError(f"报告 {index} 缺少一致的四条路径或最终输出")
            print(
                f"证据预算 {budget}，各命令首元素 {[row[0] for row in partials]}，"
                f"最终 Y[0,0]={expected_y[0] / 128}，后端 {source['backends']}"
            )
        sources.append(dict(budget=budget, widths=widths))
    proposal = 0
    print("任务：预算减半后，最后一次设备提交处理几项？")
    for i, source in enumerate(sources):
        print(f"资料 {i}：预算 {source['budget']} 字节，分块 {source['widths']}")
    print(f"助手先引用资料 0，提出 {sources[0]['widths'][-1]} 项。")
    commands = iter(["correct 1", "accept"])
    steps = 0
    while steps < 8:
        choice = (
            input("correct 1 / accept / stop > ") if interactive else next(commands)
        )
        steps += 1
        if choice == "stop":
            print(f"已接管并终止；未发布答案，操作数 {steps}")
            return
        if choice in ("correct 0", "correct 1"):
            proposal = int(choice[8:])
            print(f"已替换依据为 {proposal}，待确认")
        elif choice == "accept" and sources[proposal]["budget"] == budgets[1]:
            print(
                f"已确认 {sources[proposal]['widths'][-1]} 项（依据 {proposal}），操作数 {steps}"
            )
            return
        else:
            print("预算与任务不符或输入无效，请更正或终止")
    print("达到操作上限，保留未确认状态")


if __name__ == "__main__":
    if not __debug__:
        raise SystemExit("Run without -O so all lesson checks are active")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "lesson",
        nargs="?",
        choices=["training", "coding", "link", "handoff", "all"],
        default="all",
    )
    parser.add_argument("--reports", nargs=2, type=Path, metavar=("BASELINE", "HALF"))
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--load", type=float, default=100)
    parser.add_argument("--gain", type=float, default=1, help="one-way voltage gain")
    parser.add_argument("--phase", type=int, choices=range(16), default=8)
    args = parser.parse_args()
    if args.lesson in ("training", "all"):
        training()
    if args.lesson in ("coding", "all"):
        encoding()
    if args.lesson in ("link", "all"):
        for name, z in [("matched", 50), ("selected", args.load)]:
            link(
                z, ROOT / "build" / "linear" / f"eye-{name}.svg", args.phase, args.gain
            )
    if args.lesson in ("handoff", "all"):
        handoff(args.interactive, args.reports)
