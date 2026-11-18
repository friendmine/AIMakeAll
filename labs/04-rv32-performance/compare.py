"""Measure two projection backends on the same PicoRV32, using Lab 03's model and oracle."""

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
LAB03 = HERE.parent / "03-rv32-generation"
sys.path.insert(0, str(LAB03))
from run import build, export, load_model, reference, run_backend, sha
from performance_checks import LOGIT_TOLERANCE, verify_run


@torch.no_grad()
def measure(args, out):
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    model, q, test = load_model(args.checkpoint)
    prompt = test[args.sample, :5].tolist()
    oracle = reference(model, q, prompt)
    tokens = [s["token"] for s in oracle]
    if tokens != test[args.sample, 5:].tolist():
        raise ValueError("model failed the held-out task")
    model_hash = json.loads((LAB03 / "verified-run.json").read_text())["model_tensor_sha256"]
    tools = {"python": platform.python_version(), "torch": str(torch.__version__)}
    commands = {
        "gcc": os.environ.get("RISCV_CC", "riscv64-unknown-elf-gcc"),
        "verilator": os.environ.get("VERILATOR", "verilator"),
    }
    for name, command in commands.items():
        tools[name] = subprocess.check_output([command, "--version"], text=True).splitlines()[0]
    report = dict(
        task="copy-three-v1", sample=args.sample, prompt=prompt, tokens=tokens,
        model_tensor_sha256=model_hash, rtl_simulator_sha256=sha(args.rtl.read_bytes()),
        checkpoint_sha256=sha(args.checkpoint.read_bytes()),
        configuration=dict(isa="RV32IM", npu="H1-4x4", ram_mib=32,
                           dma_wait_period_cycles=7, width=32, hidden=16),
        tools=tools, logit_absolute_tolerance=LOGIT_TOLERANCE, runs={},
    )
    baseline_logits = None
    for kind in ("timing", "profile"):
        folder = out / kind
        folder.mkdir(exist_ok=True)
        if export(model, q, prompt, folder) != model_hash:
            raise ValueError("full model hash differs from Lab 03")
        extra = ["-DPROFILE_PHASES"] if kind == "profile" else []
        elf, image = build(folder, HERE / "benchmark.c", extra)
        run = dict(elf_sha256=sha(elf.read_bytes()), image_sha256=sha(image.read_bytes()),
                   trace_sha256={})
        for backend in ("cpu", "npu"):
            counts = folder / f"{backend}-counters.txt"
            mmio = folder / f"{backend}-mmio.txt"
            uart = run_backend([args.rtl, image, counts, mmio, backend], folder / f"{backend}.uart")
            steps, bits = verify_run(uart, counts, mmio, backend, kind == "profile", oracle)
            if baseline_logits is not None and baseline_logits != bits:
                raise ValueError("RV32 paths or instrumentation changed logit bits")
            baseline_logits = bits
            run["trace_sha256"][backend] = dict(uart=sha(uart), counters=sha(counts.read_bytes()),
                                                mmio=sha(mmio.read_bytes()))
            run[backend] = steps
            print(kind, backend, [s["cycles"] for s in steps], flush=True)
        report["runs"][kind] = run
    timing = report["runs"]["timing"]
    report["comparison"] = [
        dict(step=c["step"], token=c["token"], cpu_minus_npu_cycles=c["cycles"] - n["cycles"],
             speedup_cpu_over_npu=c["cycles"] / n["cycles"])
        for c, n in zip(timing["cpu"], timing["npu"])
    ]
    tmp = out / "report.tmp"
    tmp.write_text(json.dumps(report, indent=2) + "\n")
    tmp.replace(out / "report.json")
    print(f"PASS {prompt} -> {tokens}; {out / 'report.json'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("checkpoint", "rtl", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--sample", default=0, type=int, choices=range(64))
    args = parser.parse_args()
    args.output.mkdir(exist_ok=True, parents=True)
    with (args.output / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        (args.output / "report.json").unlink(missing_ok=True)
        measure(args, args.output)
