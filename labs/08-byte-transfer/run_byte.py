"""Reproduce the frozen transfer decision on validation and confirm it on unseen record IDs."""

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

HERE = Path(__file__).resolve().parent
LAB06, LAB07 = HERE.parent/"06-model-switch", HERE.parent/"07-fused-qkv"
sys.path[:0] = [str(LAB06), str(LAB07)]
from run_switch import buffer_symbols
from run import build, run_backend, sha
from packages import HEADER, encode_requests, package
from qkv_checks import MODES, verify
from check_switch import LOGIT_TOLERANCE
from byte_model import assess, initial_validation, load_candidate, model_package, reference, tensor_hash
from corpus import corpus_hash, documents
from decision import compare_stages, rank_candidates


def writable_reservation(elf, cc):
    def listing(tool, flag):
        program = subprocess.check_output([cc, "-print-prog-name="+tool], text=True).strip()
        return subprocess.check_output([program, flag, elf], text=True).splitlines()
    stack = next(int(line.split()[0], 16) for line in listing("nm", "-n") if line.endswith(" stack_top"))
    sections = {}
    lines = listing("objdump", "-h")
    for row, flags in zip(lines, lines[1:]):
        fields = row.split()
        if len(fields) >= 6 and fields[0].isdigit() and "ALLOC" in flags and "READONLY" not in flags:
            sections[fields[1]] = dict(start=int(fields[3], 16), bytes=int(fields[2], 16))
    start = min(section["start"] for section in sections.values())
    end = max(s["start"]+s["bytes"] for s in sections.values())
    if not end+4096 <= stack < 0x80100000:
        raise ValueError("unexpected ELF stack or input region")
    return dict(sections=sections, stack_top=stack, stack_reservation_bytes=4096,
                linked_writable_bytes=stack-start)


def inputs_for(doc, prompt_length, packages):
    # A and B both miss. The last request is a CRC-correct package with the wrong ABI shape.
    b = packages[24]
    payload = bytearray(b[HEADER.size:])
    struct.pack_into("<I", payload, len(payload)-16, 11)
    blobs = {"A": packages[32], "B": b, "wrong-vocab": package(24, payload, version=3)}
    cases = [("A", 32, 0, False), ("B", 24, 0, False), ("wrong-vocab", None, 2, None)]
    return encode_requests(doc[:prompt_length], cases, blobs), cases


def run_prompt(directory, doc, cfg, candidates, packages, symbols, image, rtl):
    directory.mkdir(parents=True, exist_ok=True)
    p = cfg["architecture"]["prompt_bytes"]
    prompt, suffix = list(doc[:p]), list(doc[p:])
    gold = {w: reference(c, prompt, len(suffix)) for w, c in candidates.items()}
    inputs, cases = inputs_for(doc, p, packages)
    asset = directory/"requests.bin"
    asset.write_bytes(inputs)
    runs = {}
    for mode in MODES:
        out = directory/mode
        out.mkdir(exist_ok=True)
        counts, bus, stores, uart = [out/name for name in ("counters.txt", "mmio.txt", "stores.txt", "rtl.uart")]
        raw = run_backend([rtl, image, counts, bus, mode, hex(symbols["packed"]), stores,
                           asset, "1280"], uart)
        rows = verify(mode, cases, gold, symbols, raw, counts, bus, stores, prompt_length=p, profile=True)
        runs[mode] = dict(valid=rows[:2], rejected=rows[2],
                          traces={f.name: sha(f.read_bytes()) for f in (uart, counts, bus, stores)})
    for cpu, npu in zip(runs["qkv-int8"]["valid"], runs["qkv-npu"]["valid"]):
        if cpu["output_sha256"] != npu["output_sha256"]:
            raise ValueError("integer implementations differ bit-for-bit")
    return dict(prompt=bytes(prompt).decode(), expected=bytes(suffix).decode(), input_sha256=sha(inputs), modes=runs)


@torch.no_grad()
def execute(args, out):
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    spec = HERE/"contract.json"
    cfg = json.loads(spec.read_text())
    if cfg["quality"]["max_rtl_float_abs_error"] != LOGIT_TOLERANCE:
        raise ValueError("float tolerance differs from the RTL checker")
    data = documents(cfg)
    shape = cfg["architecture"]
    widths = shape["ffn_widths"]
    manifests, candidates, blobs = {}, {}, {}
    for w in widths:
        path = args.models/f"byte-{w}.pt"
        model, ffn, qkv, history = load_candidate(path, w, cfg, data)
        candidates[w] = model, ffn, qkv
        blobs[w] = model_package(model, ffn, qkv, shape)
        (out/f"byte-{w}.amp").write_bytes(blobs[w])
        manifests[str(w)] = dict(package_bytes=len(blobs[w]), package_sha256=sha(blobs[w]),
                                 checkpoint_sha256=sha(path.read_bytes()), tensor_sha256=tensor_hash(model),
                                 training_history=history)
    flags = ("-include", HERE/"byte_shape.h", "-I", LAB06, "-Wall", "-Wextra", "-Werror")
    elf, image = build(out, LAB07/"qkv.c", flags)
    cc = os.environ.get("RISCV_CC", "riscv64-unknown-elf-gcc")
    symbols = buffer_symbols(elf, cc, dict(packed=1280, activation=16*shape["prompt_bytes"],
                                          qkv_input=16*shape["prompt_bytes"], tile_c=64))
    ram = writable_reservation(elf, cc)
    # H1 has two 32-word banks of 32 bits each, fixed in projection_tile.sv.
    ram.update(array_local_bytes=2*32*4, packed_buffer_bytes=1280, kv_cache_bytes=2*shape["context"]*16*4)
    initial_spec = HERE/"initial-contract.json"
    baseline = initial_validation(args.models/"baseline", json.loads(initial_spec.read_text()), data)
    report = dict(initial_contract_sha256=sha(initial_spec.read_bytes()), initial_validation=baseline,
                  task=cfg["task"], contract_sha256=sha(spec.read_bytes()), pair=args.pair, models=manifests,
                  memory=ram, elf_sha256=sha(elf.read_bytes()), firmware_sha256=sha(image.read_bytes()),
                  rtl_sha256=sha(args.rtl.read_bytes()), tile_sha256=sha(args.tile.read_bytes()),
                  splits={k: dict(documents=len(v), sha256=corpus_hash(v)) for k,v in data.items()},
                  tools=dict(python=platform.python_version(), torch=str(torch.__version__),
                             gcc=subprocess.check_output([cc, "--version"], text=True).splitlines()[0],
                             verilator=subprocess.check_output([os.environ.get("VERILATOR","verilator"), "--version"],
                                                               text=True).strip()))
    for split, pair in (("validation", 0), ("test", args.pair)):
        quality = {str(w): assess(candidates[w], data["train"], data[split], cfg, args.tile) for w in widths}
        measured = []
        for flag, doc in enumerate(data[split][2*pair:2*pair+2]):
            print(f"{split} {doc!r}: comparing three RTL paths", flush=True)
            measured.append(run_prompt(out/f"{split}-{flag}", doc, cfg, candidates, blobs, symbols, image, args.rtl))
        ranking = rank_candidates(measured, quality, manifests, ram, cfg["quality"], cfg["budget"])
        if not ranking[0]["eligible"]:
            raise ValueError(f"no eligible candidate on {split}: {ranking}")
        report[split] = dict(quality=quality, prompts=measured, ranking=ranking, stage_comparisons=compare_stages(measured))
        if split == "validation":
            chosen = ranking[0]
            report["decision"] = dict(width=chosen["width"], mode=chosen["mode"])
            report["predicted_choice_confirmed"] = (chosen["width"], chosen["mode"]) == (24, "qkv-npu")
            tighter_budget = dict(cfg["budget"], one_model_package_bytes=42496)
            tighter = rank_candidates(measured, quality, manifests, ram, cfg["quality"], tighter_budget)
            report["tighter_budget"] = dict(single_package_bytes=42496, eligible=[r for r in tighter if r["eligible"]])
        else:
            decision = report["decision"]
            selected = next(row for row in ranking if all(row[k] == v for k,v in decision.items()))
            if not selected["eligible"]:
                raise ValueError("frozen validation choice failed the test gates")
            report["test_confirmation"] = dict(**selected, fastest_on_test=selected == ranking[0])
    temp = out/"report.tmp"
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n")
    temp.replace(out/"report.json")
    print("PASS", report["decision"], out/"report.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("models","rtl","tile","output"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--pair", type=int, choices=range(32), default=0)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output/".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        (args.output/"report.json").unlink(missing_ok=True)
        execute(args, args.output)
