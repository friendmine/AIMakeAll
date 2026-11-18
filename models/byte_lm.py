"""Two-block byte language model; a projection callback supports the deployment labs."""

import math
import torch
from torch import nn
from torch.nn import functional as F

DIM, HEADS, LAYERS, CONTEXT = 32, 4, 2, 96


class Block(nn.Module):
    def __init__(self, width):
        super().__init__()
        self.norm1 = nn.LayerNorm(DIM)
        self.qkv = nn.Linear(DIM, 3 * DIM)
        self.out = nn.Linear(DIM, DIM)
        self.norm2 = nn.LayerNorm(DIM)
        self.up = nn.Linear(DIM, width)
        self.down = nn.Linear(width, DIM)

    def forward(self, x, cache, project, prefix):
        batch, rows, _ = x.shape
        q, k, v = (
            project(prefix + "qkv", self.qkv, self.norm1(x))
            .reshape(batch, rows, 3, HEADS, DIM // HEADS)
            .permute(2, 0, 3, 1, 4)
        )
        pos = 0 if cache is None else cache[0].shape[2]
        if cache is not None:
            k = torch.cat((cache[0], k), dim=2)
            v = torch.cat((cache[1], v), dim=2)
        scores = q @ k.transpose(-1, -2) / math.sqrt(DIM // HEADS)
        future = (
            torch.arange(pos + rows, device=x.device)
            > torch.arange(pos, pos + rows, device=x.device)[:, None]
        )
        attended = (
            (scores.masked_fill(future, -torch.inf).softmax(-1) @ v)
            .transpose(1, 2)
            .reshape(batch, rows, DIM)
        )
        x = x + project(prefix + "out", self.out, attended)
        hidden = F.gelu(project(prefix + "up", self.up, self.norm2(x)))
        return x + project(prefix + "down", self.down, hidden), (k, v)


def floating(name, layer, x):
    return layer(x)


class ByteLM(nn.Module):
    def __init__(self, width):
        super().__init__()
        self.width = width
        self.tokens = nn.Embedding(256, DIM)
        self.positions = nn.Embedding(CONTEXT, DIM)
        self.blocks = nn.ModuleList([Block(width) for _ in range(LAYERS)])
        self.norm = nn.LayerNorm(DIM)
        self.head = nn.Linear(DIM, 256)

    def forward(self, ids, cache=None, project=floating, last_only=False):
        pos = 0 if cache is None else cache[0][0].shape[2]
        length = ids.shape[1]
        if length < 1 or pos + length > CONTEXT:
            raise ValueError("position outside learned context")
        x = self.tokens(ids) + self.positions(
            torch.arange(pos, pos + length, device=ids.device)
        )
        updated = []
        for i, block in enumerate(self.blocks):
            x, kv = block(
                x, None if cache is None else cache[i], project, f"blocks.{i}."
            )
            updated.append(kv)
        x = x[:, -1:] if last_only else x
        return project("head", self.head, self.norm(x)), updated


def generate(model, prompt, steps, project=floating):
    ids = torch.tensor([list(prompt)])
    result, cache = bytearray(), None
    for _ in range(steps):
        logits, cache = model(ids, cache, project, last_only=True)
        ids = logits.argmax(-1)
        result.append(int(ids.item()))
    return bytes(result)
