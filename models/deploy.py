"""Weight-only package construction and the shared symmetric INT8 dot-product contract."""

from collections import Counter
from pathlib import Path
import sys
import torch
from torch import nn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "labs/02-trained-projection"))
from replay import project


def quantize_rows(x):
    scales = x.abs().amax(-1, keepdim=True).clamp_min(1e-9) / 127
    return (x / scales).round().clamp(-127, 127).to(torch.int8), scales


def dot(x, w, tile=None, limit=32):
    if not 1 <= limit <= 32 or x.shape[1] != w.shape[1]:
        raise ValueError("unsupported reduction")
    sums = torch.zeros(len(x), len(w), dtype=torch.int32)
    stats = Counter()
    for start in range(0, x.shape[1], limit):
        a = x[:, start : start + limit].int()
        b = w[:, start : start + limit].int()
        if tile is None:
            part = a @ b.T
        else:
            matrix, counters = project(tile, a.tolist(), b.tolist())
            part = torch.tensor(matrix, dtype=torch.int32)
            stats.update({k: v for k, v in counters.items() if isinstance(v, int)})
        sums += part
    return sums, dict(stats)


class QuantPlan:
    def __init__(self, model, tile=None, limit=32):
        self.weights = {
            n: quantize_rows(layer.weight.detach())
            for n, layer in model.named_modules()
            if isinstance(layer, nn.Linear)
        }
        self.tile, self.limit = tile, limit
        self.calls = []

    def __call__(self, name, layer, x):
        a, sx = quantize_rows(x.reshape(-1, x.shape[-1]))
        w, sw = self.weights[name]
        sums, stats = dot(a, w, self.tile, self.limit)
        self.calls.append(
            dict(name=name, rows=len(a), inputs=w.shape[1], outputs=w.shape[0], **stats)
        )
        return (sums.float() * sx * sw.T + layer.bias).reshape(*x.shape[:-1], len(w))
