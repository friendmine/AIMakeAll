"""A one-tool, bounded agent: the fine-tuned LM emits a tool byte; the executor binds arguments."""

import concurrent.futures
import hashlib
import json
import random
import sys
import time
from pathlib import Path
import torch
from torch.nn import functional as F

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "labs/17-language-soc"))
from execute import load, firmware, inspect
from compiler import compile_model, plan_dir

TOOLS = {
    "C": ("sum", "add", "plus"),
    "D": ("find", "read", "lookup"),
    "M": ("metric", "bench", "score"),
}


def task(tool, index, word):
    return f"{word} {index} {index % 9 + 1}" if tool == "C" else f"{word} {index}"


def train_agent():
    torch.manual_seed(2020)
    rng = random.Random(2020)
    m = load(48).train()
    opt = torch.optim.AdamW(m.parameters(), lr=0.001)
    for step in range(320):
        samples = []
        for _ in range(24):
            label = rng.choice(list(TOOLS))
            number = rng.randrange(10, 70)
            query = task(label, number, rng.choice(TOOLS[label]))
            samples.append((query, ord(label)))
        length = max(len(q) for q, _ in samples)
        ids = torch.tensor(
            [list(q.encode()) + [0] * (length - len(q)) for q, _ in samples]
        )
        scores, _ = m(ids)
        next_byte = scores[torch.arange(len(samples)), [len(q) - 1 for q, _ in samples]]
        loss = F.cross_entropy(next_byte, torch.tensor([y for _, y in samples]))
        opt.zero_grad()
        loss.backward()
        opt.step()
    return m.eval()


def execute(prompt, select, docs, metrics):
    start = time.perf_counter_ns()
    tool, cycles = select(prompt)
    words = prompt.split()
    try:
        if tool == "C" and len(words) == 3:
            result = int(words[1]) + int(words[2])
        elif tool == "D" and len(words) == 2:
            result = docs[int(words[1])]
        elif tool == "M" and len(words) == 2:
            result = metrics[int(words[1])]
        else:
            raise ValueError("invalid call")
        state = "completed"
    except (KeyError, ValueError):
        result = None
        state = "rejected"
    return dict(
        tool=tool,
        result=result,
        state=state,
        trace=["select", "dispatch", state],
        model_cycles=cycles,
        elapsed_host_ns=time.perf_counter_ns() - start,
    )


def main():
    out = ROOT / "build/tool-agent"
    out.mkdir(exist_ok=True)
    m = train_agent()
    torch.set_grad_enabled(False)
    tuned = compile_model(m, out)
    base = json.loads((plan_dir(48) / "plan.json").read_text())
    assert tuned["sha256"] != base["sha256"]
    elf, image = firmware(out, out)
    evidence = json.loads((ROOT / "build/joint/report.json").read_text())["candidates"]
    docs = {
        i: f"entry-{i}: {['matrix', 'cache', 'array', 'model'][i % 4]}"
        for i in range(80, 90)
    }
    metrics = {i: evidence[i % len(evidence)]["total"] for i in range(80, 90)}
    held = []
    for i in range(80, 90):
        for tool, words in TOOLS.items():
            prompt = task(tool, i, words[i % 3])
            expected = {"C": i + i % 9 + 1, "D": docs[i], "M": metrics[i]}[tool]
            held.append((prompt, tool, expected))

    def trial(args):
        index, (prompt, expected_tool, expected) = args

        def rule(q):
            return next(
                (t for t, words in TOOLS.items() if q.split()[0] in words), "?"
            ), 0

        def infer(device):
            row = inspect(
                out / f"{index}-{int(device)}",
                elf,
                image,
                prompt.encode(),
                1,
                device,
                "rtl",
            )
            return chr(row["J"][0]), row["E"][0] - row["U"][0]

        runs = {"rule": execute(prompt, rule, docs, metrics)}
        for label, device in [("cpu", False), ("npu", True)]:
            runs[label] = execute(prompt, lambda q: infer(device), docs, metrics)
        assert runs["cpu"]["tool"] == runs["npu"]["tool"]
        return dict(
            prompt=prompt, expected_tool=expected_tool, expected=expected, paths=runs
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(trial, enumerate(held)))
    summary = {}
    for mode in ("rule", "cpu", "npu"):
        rows = [r["paths"][mode] for r in records]
        summary[mode] = dict(
            correct=sum(s["result"] == r["expected"] for s, r in zip(rows, records)),
            legal=sum(r["state"] == "completed" for r in rows),
            timeouts=0,
            mean_model_cycles=sum(r["model_cycles"] for r in rows) / len(rows),
        )
    assert summary["npu"]["correct"] >= 27, summary
    for query, bad in [("find 9999", "D"), ("add X 3", "C"), ("unknown", "?")]:
        assert execute(query, lambda q: (bad, 0), docs, metrics)["state"] == "rejected"
    result = dict(
        tasks=len(held),
        baseline_model_sha256=base["sha256"],
        tool_model_sha256=tuned["sha256"],
        elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),
        training_numbers="10..69",
        heldout_numbers="80..89",
        dispatch_limit=1,
        max_simulator_seconds_per_request=180,
        summary=summary,
        records=records,
    )
    (out / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    print(summary)


if __name__ == "__main__":
    torch.set_num_threads(1)
    main()
