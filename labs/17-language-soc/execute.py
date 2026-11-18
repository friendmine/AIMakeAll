"""Execute an exported model on the actual RV32 cores, with identical request bytes."""

import hashlib
import json
import os
import struct
import sys
from pathlib import Path
import torch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [
    str(ROOT / "labs/15-execution-plan"),
    str(ROOT / "labs/03-rv32-generation"),
]
from compiler import Executable, plan_dir, load
from run import build, run_backend


def firmware(out, folder):
    plan = Executable(folder).plan
    if plan["width"] > 64 or any(
        op["k"] > op["max_k"] and op["max_k"] % 4 for op in plan["ops"]
    ):
        raise ValueError(
            "RV32 target needs <=64 activation lanes and aligned multi-tile slices"
        )
    p = plan["floats"]
    content = (folder / "model.bin").read_bytes()
    constants = dict(
        D=plan["dim"],
        CTX=plan["context"],
        LAYERS=plan["blocks"],
        HEADS=plan["heads"],
        WIDTH=plan["width"],
        TOK=p["tokens.weight"],
        POS=p["positions.weight"],
        FINAL_GAIN=p["norm.weight"],
        FINAL_BIAS=p["norm.bias"],
    )
    fields = ["k", "n", "w", "scale", "bias", "max_k"]
    expected = [
        f"blocks.{i}.{op}"
        for i in range(plan["blocks"])
        for op in ("qkv", "out", "up", "down")
    ] + ["head"]
    if [op["name"] for op in plan["ops"]] != expected:
        raise ValueError("unsupported graph order")
    header = "enum {" + ",".join(f"{k}={v}" for k, v in constants.items()) + "};\n"
    header += (
        "static const unsigned char blob[] __attribute__((aligned(4)))={"
        + ",".join(map(str, content))
        + "};\n"
    )
    header += (
        "static const struct op {unsigned k,n,w,sc,bias,limit;} ops[]={"
        + ",".join(
            "{" + ",".join(str(op[k]) for k in fields) + "}" for op in plan["ops"]
        )
        + "};\n"
    )
    header += (
        "static const unsigned norms[][4]={"
        + ",".join(
            "{"
            + ",".join(
                str(p[f"blocks.{i}.{n}.{v}"])
                for n in ("norm1", "norm2")
                for v in ("weight", "bias")
            )
            + "}"
            for i in range(plan["blocks"])
        )
        + "};\n"
    )
    out.mkdir(parents=True, exist_ok=True)
    (out / "compiled.h").write_text(header)
    return build(out, HERE / "generate.c")


def inspect(out, elf, image, prompt, steps, device, backend, rtl=None):
    out.mkdir(parents=True, exist_ok=True)
    request = bytes([int(device), len(prompt), steps]) + prompt
    counts, bus = out / "counters", out / "mmio"
    if backend == "qemu":
        asset = out / "input"
        asset.write_bytes(struct.pack("<I", len(request)) + request)
        cmd = [
            os.environ.get(
                "LINEAR_QEMU", ROOT / "build/qemu-course/out/qemu-system-riscv32"
            ),
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
            "-device",
            f"loader,file={asset},addr=0x80100000,force-raw=on",
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
        ]
    else:
        asset = out / "input"
        asset.write_bytes(request)
        cmd = [
            rtl or ROOT / "build/generation/soc/Vgeneration_soc",
            image,
            counts,
            bus,
            "prepacked" if device else "cpu",
            "0x80000000",
            out / "stores",
            asset,
            "4",
        ]
    raw = run_backend(cmd, out / "uart")
    fields = {}
    for line in raw.decode().splitlines():
        fields.setdefault(line[0], []).append(int(line[1:], 16))
    if backend == "rtl":
        tiles = [l for l in counts.read_text().splitlines() if l.startswith("tile ")]
        assert len(tiles) == sum(fields["N"]) and len(
            bus.read_text().splitlines()
        ) == 8 * len(tiles)
    assert len(fields["J"]) == steps and len(fields["L"]) == steps * 256
    return fields


def scores_bits(fields):
    return torch.frombuffer(
        bytearray(struct.pack(f"<{len(fields['L'])}I", *fields["L"])),
        dtype=torch.float32,
    ).view(-1, 256)


def suite(width=48, prompt=b"Th", steps=3, folder=None):
    folder = folder or plan_dir(width)
    out = ROOT / f"build/language-soc/{width}-{prompt.hex()}"
    elf, image = firmware(out, folder)
    m = load(width)
    ex = Executable(folder)
    ids = torch.tensor([list(prompt)])
    kv = None
    ref = []
    for _ in range(steps):
        y, kv = m(ids, kv, ex, last_only=True)
        ref.append(y[0, 0])
        ids = y.argmax(-1)
    ref = torch.stack(ref)
    runs = {}
    gold = None
    for backend in ("qemu", "rtl"):
        for device in (False, True):
            label = backend + ("-npu" if device else "-cpu")
            fields = inspect(out / label, elf, image, prompt, steps, device, backend)
            outputs = (fields["L"], fields["H"], fields["J"])
            if gold is None:
                gold = outputs
            assert outputs == gold and fields["J"] == ref.argmax(-1).tolist()
            err = float((scores_bits(fields) - ref).abs().max())
            assert err < 1e-4, err
            row = dict(
                tokens=fields["J"],
                integer_hashes=fields["H"],
                commands=fields["N"],
                max_error=err,
            )
            if backend == "rtl":
                row["cycles"] = [b - a for a, b in zip(fields["U"], fields["E"])]
            runs[label] = row
    report = dict(
        width=width,
        prompt=list(prompt),
        model_sha256=ex.plan["sha256"],
        elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),
        runs=runs,
    )
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report)
    return report


if __name__ == "__main__":
    torch.set_num_threads(1)
    torch.set_grad_enabled(False)
    suite()
