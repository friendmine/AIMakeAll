"""Run two Lab 02 checkpoints on a single boot of the same PicoRV32 firmware."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import platform
import struct
import subprocess
import sys

import torch

from check_switch import LOGIT_TOLERANCE, verify
from packages import export_package, floats, make_inputs

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "03-rv32-generation"))
from run import build, load_model, reference, run_backend, sha


def buffer_symbols(elf, cc):
    nm = subprocess.check_output([cc, "-print-prog-name=nm"], text=True).strip()
    sizes = {"packed_weights": 512, "tile_a": 64, "tile_c": 64}
    symbols = {}
    stack = None
    for line in subprocess.check_output([nm, "-S", elf], text=True).splitlines():
        fields = line.split()
        if fields[-1:] == ["stack_top"]:
            stack = int(fields[0], 16)
        if len(fields) == 4 and fields[3] in sizes:
            address, size, section, name = fields
            if int(size, 16) != sizes[name] or section.lower() != "b":
                raise ValueError(f"unexpected ELF buffer {name}")
            symbols[name] = int(address, 16)
    if symbols.keys() != sizes.keys() or stack is None or stack > 0x80100000:
        raise ValueError("missing buffers or ELF overlaps read-only inputs")
    return symbols


@torch.no_grad()
def execute(args):
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    out = args.output
    models, manifest, packages = {}, {}, {}
    for label, width, path in [("A", 32, args.model_a), ("B", 24, args.model_b)]:
        model, q, test = load_model(path, width)
        prompt = test[args.sample, :5].tolist()
        steps = reference(model, q, prompt)
        if [s["token"] for s in steps] != test[args.sample, 5:].tolist():
            raise ValueError(f"width {width} failed the held-out copy task")
        tensor_hash = sha(b"".join(name.encode() + b"\0" + floats(t)
                                   for name, t in sorted(model.state_dict().items())))
        if width == 32:
            lab03 = json.loads((HERE.parent / "03-rv32-generation/verified-run.json").read_text())
            if tensor_hash != lab03["model_tensor_sha256"]:
                raise ValueError("A differs from the Lab 03 model")
        blob = export_package(model, q)
        (out / f"{label}.amp").write_bytes(blob)
        packages[label] = blob
        packed = bytes(x & 255 for tile in q.wq.split(4) for x in tile.T.flatten().tolist())
        sx = struct.unpack("<I", floats(q.sx))[0]
        sw = struct.unpack(f"<{width}I", floats(q.sw))
        models[width] = dict(steps=steps, packed=packed, sx_bits=sx, sw_bits=sw)
        manifest[label] = dict(width=width, checkpoint_sha256=sha(path.read_bytes()),
                               model_tensor_sha256=tensor_hash, package_bytes=len(blob),
                               package_sha256=sha(blob), packed_sha256=sha(packed),
                               activation_scale=q.sx.item(), activation_scale_bits=f"{sx:08x}",
                               weight_scale_bits=[f"{bits:08x}" for bits in sw])

    inputs, cases = make_inputs(prompt, packages["A"], packages["B"])
    input_path = out / "requests.bin"
    input_path.write_bytes(inputs)
    elf, image = build(out, HERE / "switch.c", ("-I", HERE, "-Wall", "-Wextra", "-Werror"))
    cc = os.environ.get("RISCV_CC", "riscv64-unknown-elf-gcc")
    symbols = buffer_symbols(elf, cc)
    counters, mmio, stores = [out / name for name in ("rtl-counters.txt", "rtl-mmio.txt", "cache-stores.txt")]
    uart = out / "rtl.uart"
    raw = run_backend([args.rtl, image, counters, mmio, "prepacked", hex(symbols["packed_weights"]),
                       stores, input_path], uart)
    requests = verify(raw, counters, mmio, stores, cases, models, symbols)
    report = dict(task="copy-three-v1", sample=args.sample, prompt=prompt, models=manifest,
                  elf_sha256=sha(elf.read_bytes()), image_sha256=sha(image.read_bytes()),
                  rtl_simulator_sha256=sha(args.rtl.read_bytes()), input_sha256=sha(inputs),
                  tools=dict(python=platform.python_version(), torch=str(torch.__version__),
                             gcc=subprocess.check_output([cc, "--version"], text=True).splitlines()[0],
                             verilator=subprocess.check_output([os.environ.get("VERILATOR", "verilator"),
                                                                "--version"], text=True).strip()),
                  logit_absolute_tolerance=LOGIT_TOLERANCE, requests=requests[:4],
                  rejected=requests[4:-1], recovery=requests[-1],
                  trace_sha256={p.name: sha(p.read_bytes()) for p in (uart, counters, mmio, stores)})
    tmp = out / "report.tmp"
    tmp.write_text(json.dumps(report, indent=2) + "\n")
    tmp.replace(out / "report.json")
    print(f"PASS sample {args.sample}: {len(requests)} requests on one boot; {out / 'report.json'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("model-a", "model-b", "rtl", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--sample", type=int, default=0, choices=range(64))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        (args.output / "report.json").unlink(missing_ok=True)
        execute(args)
