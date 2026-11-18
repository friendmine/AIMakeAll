import json
import math
import sys
from pathlib import Path
import torch
from torch.nn import functional as F

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "labs/17-language-soc"))
from execute import firmware, inspect, Executable, plan_dir, load
from train import corpus, WINDOW


def quality(width, split):
    model = load(width)
    plan = Executable(plan_dir(width))
    data, _, _ = corpus()
    nll = total = 0
    for doc in data[split]:
        for start in range(0, len(doc) - 1, WINDOW):
            seq = doc[start : start + WINDOW + 1]
            logits, _ = model(seq[None, :-1], project=plan)
            nll += F.cross_entropy(logits[0], seq[1:], reduction="sum").item()
            total += len(seq) - 1
    return math.exp(nll / total)


def measure(out, width, hardware, prompt, steps):
    folder = out / f"{width}-{hardware}-{prompt.hex()}"
    elf, image = firmware(folder, plan_dir(width))
    sim = ROOT / (
        "build/generation/soc/Vgeneration_soc"
        if hardware == "banked"
        else "build/array-design/soc/Vgeneration_soc"
    )
    row = inspect(folder, elf, image, prompt, steps, True, "rtl", sim)
    cycles = [e - s for s, e in zip(row["U"], row["E"])]
    return dict(
        cycles=cycles,
        total=row["E"][-1] - row["U"][0],
        commands=row["N"],
        tokens=row["J"],
        sums=row["H"],
    ), row["L"]


def rank(rows, contract):
    feasible = [
        r
        for r in rows
        if r["validation_ppl"] <= contract["max_validation_ppl"]
        and r["payload_bytes"] <= contract["max_weight_payload_bytes"]
    ]
    return min(feasible, key=lambda r: r["total"]) if feasible else None


def main():
    cfg = json.loads((HERE / "contract.json").read_text())
    out = ROOT / "build/joint"
    out.mkdir(exist_ok=True)
    rows = []
    for width in cfg["widths"]:
        ppl = quality(width, "validation")
        gold = None
        for hw in cfg["hardware"]:
            r, logits = measure(out, width, hw, cfg["prompt"].encode(), cfg["steps"])
            if gold is not None:
                assert logits == gold
            gold = logits
            rows.append(
                dict(
                    width=width,
                    hardware=hw,
                    validation_ppl=ppl,
                    payload_bytes=(plan_dir(width) / "model.bin").stat().st_size,
                    **r,
                )
            )
    chosen = rank(rows, cfg)
    assert chosen
    heldout, _ = measure(
        out,
        chosen["width"],
        chosen["hardware"],
        cfg["test_prompt"].encode(),
        cfg["steps"],
    )
    result = dict(
        candidates=rows,
        chosen=chosen,
        confirmation=heldout,
        test_ppl=quality(chosen["width"], "test"),
    )
    (out / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    print(chosen)


if __name__ == "__main__":
    torch.set_num_threads(1)
    torch.set_grad_enabled(False)
    main()
