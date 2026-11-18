"""Build and run a ByteLM execution plan on the course RV32 platforms."""

import os
from pathlib import Path
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "labs/03-rv32-generation"))
from build_guest import build


def build_firmware(out, plan, content, extra_cflags=()):
    if plan["width"] > 64 or any(
        op["k"] > op["max_k"] and op["max_k"] % 4 for op in plan["ops"]
    ):
        raise ValueError(
            "RV32 target needs <=64 activation lanes and aligned multi-tile slices"
        )
    p = plan["floats"]
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
    return build(out, HERE / "generate.c", extra_cflags)


def inspect(out, elf, image, prompt, steps, device, backend, rtl=None, stack_top=None):
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
    env = os.environ.copy()
    if stack_top is not None:
        env["AIM_RTL_STACK_TOP"] = hex(stack_top)
    result = subprocess.run(cmd, stdout=subprocess.PIPE, timeout=600, env=env)
    raw = result.stdout
    (out / "uart").write_bytes(raw)
    result.check_returncode()
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
