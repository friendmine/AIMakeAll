import json
import sys
from pathlib import Path
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "labs/10-language-model"))
from train import load
from models.deploy import dot, quantize_rows

torch.set_num_threads(1)
torch.set_grad_enabled(False)
model = load(48)
features = {}


def capture(name, layer, x):
    features[name] = x[0].clone()
    return layer(x)


model(torch.tensor([list(b"The v")]), project=capture)
tile = ROOT / "build/projection/banked/Vprojection_tile"
rows = []
for name in ("blocks.0.qkv", "blocks.0.down", "head"):
    a, _ = quantize_rows(features[name])
    w, _ = quantize_rows(model.get_submodule(name).weight)
    for matrix, weights in [(a, w), (a[:1], w[:7])]:
        for k in (13, 32):
            actual, stats = dot(matrix, weights, tile, k)
            assert torch.equal(actual, matrix.int() @ weights.int().T)
            rows.append(
                dict(
                    layer=name,
                    shape=[len(matrix), weights.shape[1], len(weights)],
                    max_k=k,
                    **stats,
                )
            )
out = ROOT / "build/matrix-tiles"
out.mkdir(exist_ok=True)
(out / "report.json").write_text(json.dumps(rows, indent=2) + "\n")
print(len(rows), "RTL cases; total checked cells", sum(r["cells"] for r in rows))
