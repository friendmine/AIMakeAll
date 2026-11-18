import json
import sys
import time
import statistics
from pathlib import Path
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "labs/15-execution-plan"))
from compiler import Executable, plan_dir, load
from train import corpus
from models.byte_lm import DIM, LAYERS

torch.set_num_threads(1)
torch.set_grad_enabled(False)
m = load(48)
data, _, _ = corpus()
report = []
for size in (4, 16, 48, 88):
    prompt = data["test"][0][:size][None]

    def run(cached):
        plan = Executable(plan_dir(48))
        seq = prompt
        kv = None
        trace = []
        dur = []
        bytes_kv = 0
        for step in range(5):
            t = time.perf_counter_ns()
            scores, kv = m(
                seq[:, -1:] if cached and step else seq,
                kv if cached else None,
                plan,
                last_only=True,
            )
            token = scores.argmax(-1)
            dur.append(time.perf_counter_ns() - t)
            seq = torch.cat([seq, token], dim=1)
            trace.append(scores)
            bytes_kv = sum(v.numel() * v.element_size() for pair in kv for v in pair)
        return torch.cat(trace, 1), dur, bytes_kv, sum(c["rows"] for c in plan.calls)

    outputs = {}
    for cached in (False, True):
        trials = [run(cached) for _ in range(5)]
        scores, times, storage, rows = trials[-1]
        outputs[cached] = scores
        report.append(
            dict(
                prefix=size,
                cached=cached,
                peak_valid_kv_bytes=storage if cached else 0,
                processed_linear_rows=rows,
                generated=scores.argmax(-1).flatten().tolist(),
                median_host_ns=[
                    statistics.median(t[1][j] for t in trials) for j in range(5)
                ],
            )
        )
    assert torch.equal(outputs[0].argmax(-1), outputs[1].argmax(-1))
    err = (outputs[0] - outputs[1]).abs().max().item()
    assert err < 0.005, (size, err)
    report[-1]["max_logit_delta"] = err
    assert storage == 2 * LAYERS * (size + 4) * DIM * 4
out = ROOT / "build/kv"
out.mkdir(exist_ok=True)
(out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
print("cache versus recomputation", len(report), "runs")
