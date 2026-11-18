"""Measure three fused QKV paths with the same boot image, model packages and RTL."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

import torch

HERE = Path(__file__).resolve().parent
LAB06 = HERE.parent / "06-model-switch"
sys.path.insert(0, str(LAB06))
from run_switch import buffer_symbols
from run import build, load_model, run_backend, sha
from oracle import prepare_model, request_inputs
from qkv_checks import verify, compare_modes, MODES


@torch.no_grad()
def execute(args):
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    models, golden, blobs = {}, {}, {}
    baseline = json.loads((LAB06 / "verified-sample-0.json").read_text())["models"]
    out = args.output
    for label, width, path in (("A", 32, args.model_a), ("B", 24, args.model_b)):
        model, ffn, test = load_model(path, width)
        blob, golden[width], manifest, prompt = prepare_model(model, ffn, test, args.sample, args.tile)
        if (manifest["model_tensor_sha256"] != baseline[label]["model_tensor_sha256"]
                or manifest["v1_sha256"] != baseline[label]["package_sha256"]):
            raise ValueError(f"{label} differs from Lab 06")
        models[label] = dict(**manifest, checkpoint_sha256=sha(path.read_bytes()))
        blobs[label] = blob
        (out / f"{label}.amp").write_bytes(blob)
    inputs, cases = request_inputs(prompt, blobs["A"], blobs["B"])
    asset = out / "requests.bin"
    asset.write_bytes(inputs)
    elf, image = build(out, HERE / "qkv.c", ("-I", LAB06, "-Wall", "-Wextra", "-Werror"))
    cc = os.environ.get("RISCV_CC", "riscv64-unknown-elf-gcc")
    sizes = {"packed": 1280, "activation": 80, "qkv_input": 80, "tile_c": 64}
    symbols = buffer_symbols(elf, cc, sizes)
    modes = {}
    for mode in MODES:
        directory = out / mode
        directory.mkdir(exist_ok=True)
        counters, bus, stores, uart = [directory / f for f in ("counters.txt", "mmio.txt", "stores.txt", "rtl.uart")]
        raw = run_backend([args.rtl, image, counters, bus, mode, hex(symbols["packed"]), stores, asset,
                           str(sizes["packed"])], uart)
        rows = verify(mode, cases, golden, symbols, raw, counters, bus, stores)
        modes[mode] = dict(requests=rows[:4], rejected=rows[4:-1], recovery=rows[-1],
                           trace_sha256={f.name: sha(f.read_bytes()) for f in (counters, bus, stores, uart)})
        print(f"{mode} passed {len(rows)} requests", flush=True)
    comparison = compare_modes(modes)
    report = dict(task="copy-three-v1", sample=args.sample, prompt=prompt, models=models,
                  firmware_sha256=sha(image.read_bytes()), elf_sha256=sha(elf.read_bytes()),
                  rtl_sha256=sha(args.rtl.read_bytes()), tile_sha256=sha(args.tile.read_bytes()), requests_sha256=sha(inputs), modes=modes,
                  comparison=comparison, tolerance=dict(float_absolute=1e-4, ppl_vs_ffn=1.01, ppl_vs_fp32=1.10),
                  tools=dict(python=platform.python_version(), torch=str(torch.__version__),
                             gcc=subprocess.check_output([cc, "--version"], text=True).splitlines()[0],
                             verilator=subprocess.check_output([os.environ.get("VERILATOR", "verilator"),
                                                                "--version"], text=True).strip()))
    tmp = out / "report.tmp"
    tmp.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    tmp.replace(out / "report.json")
    print("PASS", out / "report.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("model-a", "model-b", "rtl", "tile", "output"):
        parser.add_argument("--"+name, required=True, type=Path)
    parser.add_argument("--sample", type=int, choices=range(64), default=0)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        (args.output / "report.json").unlink(missing_ok=True)
        execute(args)
