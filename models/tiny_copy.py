"""One-block, one-head causal Transformer for the chip/model projection lab."""

import math

from torch import Tensor, arange, cat, softmax
from torch import nn
from torch.nn import functional as F

DIM = 16
VOCAB = 11  # eight symbols, then BOS, separator, EOS
CONTEXT = 8


class CopyTransformer(nn.Module):
    def __init__(self, width, *, vocab=VOCAB, context=CONTEXT):
        super().__init__()
        self.tokens = nn.Embedding(vocab, DIM)
        self.positions = nn.Embedding(context, DIM)
        self.attn_norm = nn.LayerNorm(DIM)
        self.qkv = nn.Linear(DIM, 3 * DIM)
        self.attn_out = nn.Linear(DIM, DIM)
        self.ffn_norm = nn.LayerNorm(DIM)
        self.up = nn.Linear(DIM, width)
        self.down = nn.Linear(width, DIM)
        self.final_norm = nn.LayerNorm(DIM)
        self.head = nn.Linear(DIM, vocab)

    def features(self, ids, cache=None):
        """Return the residual, the real input to the FFN up projection, and KV."""
        start = 0 if cache is None else cache[0].size(1)
        positions = arange(start, start + ids.size(1), device=ids.device)
        residual = self.tokens(ids) + self.positions(positions)
        q, k, v = self.qkv(self.attn_norm(residual)).chunk(3, dim=-1)
        if cache is not None:
            k = cat([cache[0], k], dim=1)
            v = cat([cache[1], v], dim=1)
        scores = q @ k.transpose(1, 2) / math.sqrt(DIM)
        future = arange(k.size(1), device=ids.device) > positions[:, None]
        attention = softmax(scores.masked_fill(future, -math.inf), dim=-1) @ v
        residual = residual + self.attn_out(attention)
        return residual, self.ffn_norm(residual), (k, v)

    def forward(self, ids: Tensor, cache=None, projection=None):
        residual, features, cache = self.features(ids, cache)
        expanded = self.up(features) if projection is None else projection(features)
        hidden = residual + self.down(F.gelu(expanded))
        return self.head(self.final_norm(hidden)), cache
