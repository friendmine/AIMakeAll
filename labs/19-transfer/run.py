import json
import sys
from pathlib import Path
import torch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "labs/18-joint-selection"))
from select_model import rank, measure, load, Executable, plan_dir
from models.byte_lm import generate

torch.set_num_threads(1)
torch.set_grad_enabled(False)
cfg = json.loads((HERE / "contract.json").read_text())
rows = json.loads((ROOT / "build/joint/report.json").read_text())["candidates"]
chosen = rank(rows, cfg)
assert chosen and chosen["width"] == 40
out = ROOT / "build/transfer"
out.mkdir(exist_ok=True)
m = load(40)
plan = Executable(plan_dir(40))
prompt = cfg["prompt"].encode()
reference = generate(m, prompt, cfg["steps"], plan)
runs = {h: measure(out, 40, h, prompt, cfg["steps"]) for h in ("banked", "stream")}
assert (
    runs["banked"][1] == runs["stream"][1]
    and bytes(runs["stream"][0]["tokens"]) == reference
)
assert runs[chosen["hardware"]][0]["total"] == min(
    row[0]["total"] for row in runs.values()
)

# Simulate a packer using the opposite output-lane order and localize by layer.
bad = Executable(plan_dir(40))
w, sw, bias, k = bad.ops["blocks.0.qkv"]
bad.ops["blocks.0.qkv"] = (w.reshape(-1, 4, 32).flip(1).reshape_as(w), sw, bias, k)
x = torch.tensor([list(prompt)])


def trace(backend):
    layers = {}

    def observe(name, layer, a):
        y = backend(name, layer, a)
        layers[name] = y.detach().clone()
        return y

    m(x, project=observe)
    return layers


good, broken = trace(plan), trace(bad)
first = next(n for n in good if not torch.equal(good[n], broken[n]))
index = torch.nonzero(good[first] != broken[first])[0].tolist()
assert first == "blocks.0.qkv"
report = dict(
    contract=cfg,
    selection=dict(width=40, hardware=chosen["hardware"]),
    validation_ppl=chosen["validation_ppl"],
    payload_bytes=chosen["payload_bytes"],
    rejected_wide_bytes=rows[0]["payload_bytes"],
    runs={h: r[0] for h, r in runs.items()},
    first_divergence=dict(
        layer=first,
        index=index,
        expected=good[first][tuple(index)].item(),
        found=broken[first][tuple(index)].item(),
    ),
    reference=list(reference),
    independent_reader="pending",
)
(out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
print(report["selection"], reference)
