"""AOT compiler for ByteLM's two-block graph, with an executable packed INT8 plan."""

import hashlib
import json
import sys
from pathlib import Path
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "labs/10-language-model"))
from train import load
from models.byte_lm import DIM, HEADS, LAYERS, CONTEXT
from models.deploy import QuantPlan, quantize_rows, dot


def compile_model(model, out, max_k=32):
    if not 1 <= max_k <= 32:
        raise ValueError("array reduction exceeds v0 microtile")
    out.mkdir(parents=True, exist_ok=True)
    payload = bytearray()

    def store(t):
        while len(payload) % 4:
            payload.append(0)
        start = len(payload)
        payload.extend(t.detach().contiguous().numpy().tobytes())
        return start

    floats = {
        name: store(t)
        for name, t in model.named_parameters()
        if name.startswith(("tokens.", "positions.")) or "norm" in name
    }
    ops = []

    def trace(name, layer, x):
        w, sw = quantize_rows(layer.weight)
        n, k = w.shape
        if n % 4:
            raise ValueError(
                "output channels must be divisible by four for this AOT target"
            )
        ops.append(
            dict(
                name=name,
                k=k,
                n=n,
                w=store(w.reshape(n // 4, 4, k).transpose(1, 2)),
                scale=store(sw.flatten()),
                bias=store(layer.bias),
                max_k=max_k,
            )
        )
        return layer(x)

    model(torch.tensor([[84, 104]]), project=trace)
    manifest = dict(
        format=1,
        width=model.width,
        dim=DIM,
        heads=HEADS,
        blocks=LAYERS,
        context=CONTEXT,
        vocab=256,
        floats=floats,
        ops=ops,
        cpu_ops=[
            "embedding",
            "layer_norm",
            "causal_attention",
            "softmax",
            "GELU",
            "residual",
            "rescale",
            "argmax",
        ],
        payload_bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
    )
    (out / "model.bin").write_bytes(payload)
    (out / "plan.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


class Executable:
    def __init__(self, out, tile=None, *, payload=None):
        self.plan = json.loads((out / "plan.json").read_text())
        data = (out / "model.bin").read_bytes() if payload is None else payload
        if (
            self.plan["format"] != 1
            or hashlib.sha256(data).hexdigest() != self.plan["sha256"]
            or len(data) != self.plan["payload_bytes"]
        ):
            raise ValueError("invalid plan payload")
        width = self.plan["width"]
        if (
            not isinstance(width, int)
            or width <= 0
            or width % 4
            or any(
                self.plan[key] != value
                for key, value in dict(
                    dim=DIM, heads=HEADS, blocks=LAYERS, context=CONTEXT, vocab=256
                ).items()
            )
        ):
            raise ValueError("unsupported architecture")
        required = {"tokens.weight", "positions.weight", "norm.weight", "norm.bias"}
        expected = {}
        for i in range(LAYERS):
            for norm in ("norm1", "norm2"):
                required.update(
                    f"blocks.{i}.{norm}.{key}" for key in ("weight", "bias")
                )
            for name, shape in [
                ("qkv", (DIM, 3 * DIM)),
                ("out", (DIM, DIM)),
                ("up", (DIM, width)),
                ("down", (width, DIM)),
            ]:
                expected[f"blocks.{i}.{name}"] = shape
        expected["head"] = (DIM, 256)
        if set(self.plan["floats"]) != required or [
            op["name"] for op in self.plan["ops"]
        ] != list(expected):
            raise ValueError("incomplete or reordered execution plan")
        self.ops = {}
        used = []

        def span(offset, size, dtype):
            if offset % 4 or offset < 0 or size <= 0 or offset + size > len(data):
                raise ValueError("invalid tensor span")
            used.append((offset, offset + size))
            return torch.frombuffer(
                bytearray(data[offset : offset + size]), dtype=dtype
            )

        for name, offset in self.plan["floats"].items():
            count = {"tokens.weight": 256 * DIM, "positions.weight": CONTEXT * DIM}.get(
                name, DIM
            )
            span(offset, 4 * count, torch.float32)
        for op in self.plan["ops"]:
            k, n = op["k"], op["n"]
            if (
                (k, n) != expected[op["name"]]
                or n % 4
                or not 1 <= op["max_k"] <= 32
                or op["name"] in self.ops
            ):
                raise ValueError("invalid projection")
            w = (
                span(op["w"], n * k, torch.int8)
                .reshape(n // 4, k, 4)
                .transpose(1, 2)
                .reshape(n, k)
            )
            sw = span(op["scale"], n * 4, torch.float32)
            bias = span(op["bias"], n * 4, torch.float32)
            if (
                not torch.isfinite(sw).all()
                or not (sw > 0).all()
                or not torch.isfinite(bias).all()
            ):
                raise ValueError("invalid scale/bias")
            self.ops[op["name"]] = (w, sw, bias, op["max_k"])
        used.sort()
        if any(b > c for (_, b), (c, _) in zip(used, used[1:])):
            raise ValueError("overlapping tensor span")
        self.tile = tile
        self.calls = []

    def __call__(self, name, layer, x):
        w, sw, bias, kmax = self.ops[name]
        a, sx = quantize_rows(x.reshape(-1, x.shape[-1]))
        sums, stats = dot(a, w, self.tile, kmax)
        self.calls.append(dict(name=name, rows=len(a), **stats))
        return (sums.float() * sx * sw + bias).reshape(*x.shape[:-1], len(w))


def plan_dir(width):
    return ROOT / f"build/plans/{width}"


if __name__ == "__main__":
    torch.set_num_threads(1)
    torch.set_grad_enabled(False)
    for width in (48, 40):
        model = load(width)
        out = plan_dir(width)
        compile_model(model, out)
        cpu = Executable(out)
        rtl = Executable(out, ROOT / "build/projection/banked/Vprojection_tile")
        x = torch.tensor([list(b"The")])
        scores = model(x, project=QuantPlan(model))[0]
        for backend in (cpu, rtl):
            got = model(x, project=backend)[0]
            assert torch.equal(scores, got)
        report = dict(
            width=width,
            payload_bytes=cpu.plan["payload_bytes"],
            ops=rtl.calls,
            verified_scores=scores.numel(),
            cpu_fallback=cpu.plan["cpu_ops"],
        )
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(width, report["payload_bytes"])
