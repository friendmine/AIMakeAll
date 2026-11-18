"""Measure on-demand versus resident weight layout over consecutive RV32 requests."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

import torch

from packing_checks import amortization, check_weight_addresses, check_weight_stores

HERE = Path(__file__).resolve().parent
LAB04 = HERE.parent / "04-rv32-performance"
LAB03 = HERE.parent / "03-rv32-generation"
sys.path[:0] = [str(LAB03), str(LAB04)]
from run import build, export, load_model, reference, run_backend, sha
from performance_checks import LOGIT_TOLERANCE, Trace, verify_run

MODES = {"cpu": 0, "onsite": 1, "prepacked": 2}
REQUESTS = 3


def weight_storage(elf, gcc):
    nm = subprocess.check_output([gcc, "-print-prog-name=nm"], text=True).strip()
    symbols = {}
    for line in subprocess.check_output([nm, "-S", str(elf)], text=True).splitlines():
        fields = line.split()
        if len(fields) == 4 and fields[3] in ("weight_i8", "weight_workspace"):
            symbols[fields[3]] = dict(address=int(fields[0], 16), bytes=int(fields[1], 16),
                                      section_type=fields[2])
    weights, workspace = symbols["weight_i8"], symbols["weight_workspace"]
    if not (weights["bytes"] == workspace["bytes"] == 32 * 16
            and weights["section_type"].lower() == "r" and workspace["section_type"].lower() == "b"):
        raise ValueError("unexpected source weight or writable workspace in the firmware")
    block_bytes = 4 * 16
    return dict(elf_symbols=symbols, source_bytes=weights["bytes"], onsite_scratch_bytes=block_bytes,
                prepacked_cache_bytes=workspace["bytes"], extra_live_ram_bytes=workspace["bytes"]-block_bytes)


def verify_mode(mode, raw, counters, mmio, steps, packed_bytes, workspace):
    trace = Trace(raw, mode)
    trace.word("M", "backend", MODES[mode])
    trace.word("W", "weight workspace address", workspace)
    requests = []
    for i in range(REQUESTS):
        trace.word("R", "request", i)
        setup = trace.word("U", "preparation")
        if (setup > 0) != (mode == "prepacked" and i == 0):
            raise ValueError("preparation must run exactly once in the prepacked cold request")
        requests.append(dict(index=i, setup_cycles=setup, first_token_cycles=trace.word("F", "first token"),
                             request_cycles=trace.word("E", "request to EOS")))
    if mode == "prepacked":
        for i, expected in enumerate(packed_bytes):
            trace.word("B", f"cached byte {i}", expected)

    all_steps = steps * REQUESTS
    rest = ("\n".join(trace.lines) + "\n").encode("ascii")
    backend = "cpu" if mode == "cpu" else "npu"
    verified, logits = verify_run(rest, counters, mmio, backend, False, all_steps)
    logits_per_request = sum(len(step["logits"]) for step in steps)
    if logits != logits[:logits_per_request] * REQUESTS:
        raise ValueError("repeated request changed the RV32 logit bits")
    distinct = 0
    if mode != "cpu":
        distinct = check_weight_addresses(mmio, workspace, all_steps, mode == "prepacked")
    for i, req in enumerate(requests):
        results = verified[i*len(steps):(i+1)*len(steps)]
        req["step_cycles"] = [s["cycles"] for s in results]
        req["commands"] = [s["commands"] for s in results]
        req["dma_read_bytes"] = [s["dma_read_bytes"] for s in results]
        req["dma_write_bytes"] = [s["dma_write_bytes"] for s in results]
        req["checked_integers"] = sum(s["integers"] for s in results)
        req["checked_logits"] = sum(s["logits"] for s in results)
        req["max_logit_error"] = max(s["max_logit_error"] for s in results)
        req["tokens"] = [s["token"] for s in results]
        if req["first_token_cycles"] < req["setup_cycles"] + req["step_cycles"][0]:
            raise ValueError("cold first-token latency omits setup or prefill")
        if req["request_cycles"] < req["first_token_cycles"] + sum(req["step_cycles"][1:]):
            raise ValueError("request interval omits a generation step")
    return dict(requests=requests, distinct_b_addresses=distinct), logits


@torch.no_grad()
def measure(args):
    out = args.output
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    model, q, test = load_model(args.checkpoint)
    prompt = test[args.sample, :5].tolist()
    steps = reference(model, q, prompt)
    if [s["token"] for s in steps] != test[args.sample, 5:].tolist():
        raise ValueError("reference failed the held-out task")
    model_hash = export(model, q, prompt, out)
    lab04 = json.loads((LAB04 / "verified-sample-0.json").read_text())
    if model_hash != lab04["model_tensor_sha256"]:
        raise ValueError("model differs from the published Lab 04 tensor hash")
    # Oracle builds each [depth,4] tile independently from the original [out,depth] tensor.
    packed_bytes = bytes(v & 255 for j in range(0, len(q.wq), 4)
                         for v in q.wq[j:j+4].T.flatten().tolist())
    elf, image = build(out, HERE / "benchmark.c")
    gcc = os.environ.get("RISCV_CC", "riscv64-unknown-elf-gcc")
    storage = weight_storage(elf, gcc)
    tools = {"python": platform.python_version(), "torch": str(torch.__version__)}
    for name, exe in (("gcc", gcc), ("verilator", os.environ.get("VERILATOR", "verilator"))):
        tools[name] = subprocess.check_output([exe, "--version"], text=True).splitlines()[0]
    report = dict(task="copy-three-v1", sample=args.sample, prompt=prompt, tools=tools,
                  model_tensor_sha256=model_hash, checkpoint_sha256=sha(args.checkpoint.read_bytes()),
                  elf_sha256=sha(elf.read_bytes()), image_sha256=sha(image.read_bytes()),
                  rtl_simulator_sha256=sha(args.rtl.read_bytes()), packed_bytes_sha256=sha(packed_bytes),
                  configuration=lab04["configuration"], logit_absolute_tolerance=LOGIT_TOLERANCE,
                  storage=storage, modes={})
    baseline_logits = None
    workspace = storage["elf_symbols"]["weight_workspace"]["address"]
    for mode in MODES:
        counters, mmio = out / f"{mode}-counters.txt", out / f"{mode}-mmio.txt"
        selector = "npu" if mode == "onsite" else mode
        stores = out / f"{mode}-weight-stores.txt"
        raw = run_backend([args.rtl, image, counters, mmio, selector, hex(workspace), stores],
                          out / f"{mode}.uart")
        run, logits = verify_mode(mode, raw, counters, mmio, steps, packed_bytes, workspace)
        if baseline_logits is not None and logits != baseline_logits:
            raise ValueError("projection backend changed RV32 output bits")
        baseline_logits = logits
        written = check_weight_stores(stores, counters, mode, steps, packed_bytes, REQUESTS)
        for req, count in zip(run["requests"], written):
            req["cpu_weight_store_bytes"] = count
        run["trace_sha256"] = dict(uart=sha(raw), mmio=sha(mmio.read_bytes()),
                                   counters=sha(counters.read_bytes()), weight_stores=sha(stores.read_bytes()))
        report["modes"][mode] = run
        print(mode, [r["request_cycles"] for r in run["requests"]], flush=True)

    # B is the only MMIO descriptor field allowed to differ between NPU policies.
    def other_registers(mode):
        return [line for line in (out / f"{mode}-mmio.txt").read_text().splitlines()
                if int(line.split()[0], 16) != 0x10010014]
    if other_registers("onsite") != other_registers("prepacked"):
        raise ValueError("non-weight device descriptors differ between NPU paths")

    runs = {mode: item["requests"] for mode, item in report["modes"].items()}
    report["amortization"] = amortization(
        [r["request_cycles"] for r in runs["onsite"]], [r["request_cycles"] for r in runs["prepacked"]],
        runs["prepacked"][0]["setup_cycles"])
    report["decode_vs_cpu"] = [
        {name: [a-b for a, b in zip(runs[name][i]["step_cycles"][1:], runs["cpu"][i]["step_cycles"][1:])]
         for name in ("onsite", "prepacked")} for i in range(REQUESTS)]
    tmp = out / "report.tmp"
    tmp.write_text(json.dumps(report, indent=2) + "\n")
    tmp.replace(out / "report.json")
    print("PASS", report["amortization"], out / "report.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("checkpoint", "rtl", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--sample", type=int, default=0, choices=range(64))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        (args.output / "report.json").unlink(missing_ok=True)
        measure(args)
