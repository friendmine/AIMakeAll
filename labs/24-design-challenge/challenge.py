"""Compare two independent design changes on the same frozen workload and PicoRV32."""

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import torch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [
    str(ROOT / "labs/18-joint-selection"),
    str(ROOT / "labs/17-language-soc"),
]
from select_model import quality
from execute import Executable, firmware, inspect, load, plan_dir, scores_bits

OUT = ROOT / "build/design-challenge"


def ram_bytes(elf):
    cc = os.environ.get("RISCV_CC", "riscv64-unknown-elf-gcc")
    nm = subprocess.check_output([cc, "-print-prog-name=nm"], text=True).strip()
    objdump = subprocess.check_output(
        [cc, "-print-prog-name=objdump"], text=True
    ).strip()
    listing = subprocess.check_output([nm, "-n", elf], text=True).splitlines()
    stack = next(int(l.split()[0], 16) for l in listing if l.endswith(" stack_top"))
    sections = subprocess.check_output([objdump, "-h", elf], text=True).splitlines()
    starts = [
        int(line.split()[3], 16)
        for line, flags in zip(sections, sections[1:])
        if line.split()
        and line.split()[0].isdigit()
        and "ALLOC" in flags
        and "READONLY" not in flags
    ]
    return stack - min(starts), stack


def reference(prompt, model, plan, steps):
    ids = torch.tensor([list(prompt.encode())])
    past = None
    out = []
    with torch.no_grad():
        for _ in range(steps):
            scores, past = model(ids, past, plan, last_only=True)
            out.append(scores[0, 0])
            ids = scores.argmax(-1)
    return torch.stack(out)


def simulate(
    image_info, variant, prompt, diagnostic, ref, cfg, out_root, kv_per_position
):
    elf, image, (mem, stack_top) = image_info
    word = variant in ("word_dma", "combined")
    sim = ROOT / (
        "build/design-challenge/soc/Vgeneration_soc"
        if word
        else "build/array-design/soc/Vgeneration_soc"
    )
    out = (
        out_root
        / ("profile" if diagnostic else "score")
        / variant
        / prompt.encode().hex()
    )
    f = inspect(
        out,
        elf,
        image,
        prompt.encode(),
        cfg["steps"],
        True,
        "rtl",
        sim,
        stack_top=stack_top,
    )
    scores = scores_bits(f)
    error = (scores - ref).abs().max().item()
    assert error <= cfg["max_reference_abs_error"] and f["J"] == ref.argmax(-1).tolist()
    tiles = [
        list(map(int, line.split()[1:]))
        for line in (out / "counters").read_text().splitlines()
        if line.startswith("tile ")
    ]
    writes = [
        (int(addr, 16), int(value, 16), int(t))
        for addr, value, t in (
            line.split() for line in (out / "mmio").read_text().splitlines()
        )
    ]
    (stack_used,) = [
        int(line.split()[1])
        for line in (out / "counters").read_text().splitlines()
        if line.startswith("stack_used ")
    ]
    assert 0 < stack_used <= 4096
    stages = []
    cursor = 0
    for i, (start, end, n) in enumerate(zip(f["U"], f["E"], f["N"])):
        group = tiles[cursor : cursor + n]
        busy = reads = stores = configure = finish = 0
        shapes = {}
        for j, (t0, t1, r, w, stalls) in enumerate(group, cursor):
            regs = writes[j * 8 : (j + 1) * 8]
            assert [a - 0x10010000 for a, _, _ in regs] == [
                16,
                20,
                24,
                28,
                32,
                36,
                4,
                4,
            ]
            m, cols, k = [reg[1] for reg in regs[3:6]]
            assert start <= regs[0][2] <= regs[6][2] <= t0 < t1 <= regs[7][2] < end
            lanes = 1 if word and cols == 4 and regs[1][1] % 4 == 0 else cols
            assert r == k * (m + lanes) and w == m * cols
            busy += t1 - t0
            configure += t0 - regs[0][2]
            finish += regs[7][2] - t1
            reads += r
            stores += w
            shapes[str(m)] = shapes.get(str(m), 0) + 1
        cursor += n
        row = dict(
            cycles=end - start,
            commands=n,
            device_busy_cycles=busy,
            configuration_cycles=configure,
            finish_to_clear_cycles=finish,
            read_beats=reads,
            write_beats=stores,
            rows_per_command=shapes,
        )
        if diagnostic:
            linear, driver, norm, attn, gelu = f["P"][5 * i : 5 * i + 5]
            partition = dict(
                device_busy=busy,
                driver_config=configure,
                driver_finish=finish,
                driver_other=driver - configure - busy - finish,
                linear_cpu=linear - driver,
                norm=norm,
                attention_kv=attn,
                gelu=gelu,
                other=end - start - linear - norm - attn - gelu,
            )
            assert (
                min(partition.values()) >= 0 and sum(partition.values()) == end - start
            )
            row["exclusive_cycles"] = partition
        stages.append(row)
    assert cursor == len(tiles)
    return dict(
        prompt=prompt,
        tokens=f["J"],
        logits_sha256=hashlib.sha256(scores.numpy().tobytes()).hexdigest(),
        max_abs_error=error,
        request_cycles=f["E"][-1] - f["U"][0],
        steps=stages,
        valid_kv_peak_bytes=kv_per_position * (len(prompt.encode()) + cfg["steps"] - 1),
        linked_writable_bytes=mem,
        peak_stack_bytes=stack_used,
        static_plus_peak_stack_bytes=mem - 4096 + stack_used,
    )


def main(contract, out_root, select_only=False, confirm_from=None):
    cfg = json.loads(contract.read_text())
    width = cfg["model_width"]
    prompts = cfg["development"] + cfg["confirmation"]
    assert set(cfg["candidates"]) == {"baseline", "word_dma", "qkv4", "combined"}
    assert (
        cfg["development"]
        and (select_only or cfg["confirmation"])
        and 1 <= cfg["steps"] <= 8
    )
    assert len(set(prompts)) == len(prompts) and all(
        0 < len(s.encode()) <= 96 - cfg["steps"] + 1 for s in prompts
    )
    os.environ.setdefault("AIM_RTL_CYCLE_LIMIT", "500000000")
    torch.set_num_threads(1)
    torch.set_grad_enabled(False)
    plan = Executable(plan_dir(width))
    model = load(width)
    p = plan.plan
    assert p["ops"][0]["k"] == p["dim"] == p["ops"][0]["max_k"] == 32
    kv_per_position = 2 * p["blocks"] * p["dim"] * 4
    allocated = kv_per_position * p["context"]
    ppl = quality(width, "validation")
    assert (
        ppl <= cfg["max_validation_byte_ppl"]
        and allocated <= cfg["max_allocated_kv_bytes"]
        and p["payload_bytes"] <= cfg["max_payload_bytes"]
    )
    images = {}
    for grouped in (False, True):
        for diagnostic in (False, True):
            flags = (["-DAIM_QKV4"] if grouped else []) + (
                ["-DAIM_PROFILE"] if diagnostic else []
            )
            elf, rom = firmware(
                out_root / f"firmware-{int(grouped)}-{int(diagnostic)}",
                plan_dir(width),
                flags,
            )
            images[grouped, diagnostic] = (elf, rom, ram_bytes(elf))

    def batch(variants, prompts, diagnostic=False):
        refs = {s: reference(s, model, plan, cfg["steps"]) for s in prompts}

        def run(task):
            v, s = task
            img = images[v in ("qkv4", "combined"), diagnostic]
            return simulate(
                img, v, s, diagnostic, refs[s], cfg, out_root, kv_per_position
            )

        tasks = [(v, s) for v in variants for s in prompts]
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            rows = list(pool.map(run, tasks))
        data = {
            v: [row for (variant, _), row in zip(tasks, rows) if variant == v]
            for v in variants
        }
        for i in range(len(prompts)):
            assert len({group[i]["logits_sha256"] for group in data.values()}) == 1
        return data

    sources = {
        f"qkv4={int(g)},profile={int(d)}": hashlib.sha256(elf.read_bytes()).hexdigest()
        for (g, d), (elf, _, _) in images.items()
    }
    selection_contract = {k: v for k, v in cfg.items() if k != "confirmation"}
    frozen_inputs = dict(
        development_contract_sha256=hashlib.sha256(
            json.dumps(selection_contract, sort_keys=True).encode()
        ).hexdigest(),
        model_sha256=p["sha256"],
        firmware_sha256=sources,
        rtl_sim_sha256={
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                ROOT / "build/array-design/soc/Vgeneration_soc",
                ROOT / "build/design-challenge/soc/Vgeneration_soc",
            )
        },
    )
    if confirm_from is not None:
        decision = json.loads(confirm_from.read_text())
        if decision["inputs"] != frozen_inputs:
            raise ValueError(
                "Development contract, model or executable changed after selection"
            )
        selected = decision["selection"]
        assert selected in cfg["candidates"]
        confirm = batch(
            list(dict.fromkeys(["baseline", selected])), cfg["confirmation"]
        )
        evidence = dict(
            selection_sha256=hashlib.sha256(confirm_from.read_bytes()).hexdigest(),
            selection=selected,
            confirmation=confirm,
        )
        (out_root / "confirmation.json").write_text(
            json.dumps(evidence, indent=2) + "\n"
        )
        print("Confirmed", selected, "on", len(cfg["confirmation"]), "new requests")
        return
    dev = batch(cfg["candidates"], cfg["development"])
    totals = {k: sum(r["request_cycles"] for r in rows) for k, rows in dev.items()}
    eligible = [
        v
        for v in totals
        if dev[v][0]["linked_writable_bytes"]
        <= cfg["max_firmware_writable_bytes_including_stack"]
    ]
    if not eligible:
        raise ValueError(
            f"No design fits the writable-memory budget: {[(v, dev[v][0]['linked_writable_bytes']) for v in totals]}"
        )
    selected = min(eligible, key=totals.get)
    decision = dict(
        inputs=frozen_inputs,
        contract_sha256=hashlib.sha256(contract.read_bytes()).hexdigest(),
        development_total_cycles=totals,
        selection=selected,
    )
    (out_root / "selection.json").write_text(json.dumps(decision, indent=2) + "\n")
    if select_only:
        (out_root / "development.json").write_text(json.dumps(dev, indent=2) + "\n")
        print("Selection frozen:", selected)
        return
    confirm = batch(list(dict.fromkeys(["baseline", selected])), cfg["confirmation"])
    diagnostics = batch(
        list(dict.fromkeys(["baseline", selected])), cfg["development"], True
    )
    for v, rows in diagnostics.items():
        assert [r["logits_sha256"] for r in rows] == [
            r["logits_sha256"] for r in dev[v]
        ]
    tails = batch(["baseline", "combined"], ["Shape"])
    report = dict(
        contract_sha256=hashlib.sha256(contract.read_bytes()).hexdigest(),
        firmware_sha256=sources,
        compiler=subprocess.check_output(
            [os.environ.get("RISCV_CC", "riscv64-unknown-elf-gcc"), "-dumpfullversion"],
            text=True,
        ).strip(),
        tail_check=tails,
        model_sha256=p["sha256"],
        validation_byte_ppl=ppl,
        payload_bytes=p["payload_bytes"],
        allocated_kv_bytes=allocated,
        development=dev,
        development_total_cycles=totals,
        selection=selected,
        confirmation=confirm,
        profile=diagnostics,
    )
    (out_root / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(selected, totals)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=HERE / "contract.json")
    parser.add_argument("--output", type=Path, default=OUT)
    phases = parser.add_mutually_exclusive_group()
    phases.add_argument(
        "--select-only",
        action="store_true",
        help="freeze a choice without confirmation inputs",
    )
    phases.add_argument(
        "--confirm-from",
        type=Path,
        help="verify a frozen choice on newly released requests",
    )
    args = parser.parse_args()
    main(args.contract, args.output.resolve(), args.select_only, args.confirm_from)
