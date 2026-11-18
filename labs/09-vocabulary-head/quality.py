from contextlib import nullcontext
from pathlib import Path
import json
import sys
import torch

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "build/vocabulary-head"
HERE.mkdir(parents=True, exist_ok=True)
L8 = ROOT / "labs/08-byte-transfer"
sys.path.insert(0, str(L8))
import run_byte
from byte_model import tensor, tensor_hash, load_candidate, model_package
from experiment import loss
from oracle import packed
from packages import floats, package, HEADER
from replay import project
from corpus import documents

torch.set_num_threads(1)
torch.set_grad_enabled(False)
c = json.loads((L8 / "contract.json").read_text())
data = documents(c)
m, f, q, _ = load_candidate(ROOT / "build/byte-transfer/models/byte-32.pt", 32, c, data)
archived = json.loads((L8 / "verified-run.json").read_text())
assert tensor_hash(m) == archived["models"]["32"]["tensor_sha256"]
cal = tensor(data["train"][:32])[:, :-1]
with m.qkv.register_forward_hook(lambda layer, a, _: q.compute(a[0], layer.bias)[1]):
    with m.head.register_forward_pre_hook(
        lambda _, a: captures.append(a[0].detach().clone())
    ):
        captures = []
        m(cal, projection=f.apply)
sx = captures[0].abs().amax().clamp_min(1e-12) / 127
sw = m.head.weight.abs().amax(1).clamp_min(1e-12) / 127
w = (m.head.weight / sw[:, None]).round().clamp(-127, 127).int()


def quant_head(x, tile=False):
    xq = (x / sx).round().clamp(-127, 127).int().reshape(-1, 16)
    sums = xq @ w.T
    if tile:
        matrix, _ = project(
            ROOT / "build/projection/banked/Vprojection_tile", xq.tolist(), w.tolist()
        )
        assert torch.equal(sums, torch.tensor(matrix, dtype=torch.int32))
    return (sums.float() * sx * sw + m.head.bias).reshape(*x.shape[:-1], 256)


def run(d, rtl=False, int_head=True):
    with m.qkv.register_forward_hook(lambda l, a, _: q.compute(a[0], l.bias)[1]):
        with (
            m.head.register_forward_hook(lambda l, a, _: quant_head(a[0], rtl))
            if int_head
            else nullcontext()
        ):
            teacher, _ = m(d[:, :-1], projection=f.apply)
            prefix = d[:, :7]
            kv = None
            seq = []
            logits = []
            for _ in range(3):
                v, kv = m(prefix, kv, projection=f.apply)
                logits.append(v[:, -1])
                prefix = v[:, -1].argmax(1, keepdim=True)
                seq.append(prefix)
    ret = torch.cat(seq, dim=1)
    return (
        dict(
            exact=int((ret == d[:, 7:]).all(1).sum()),
            ppl=loss(teacher[:, 6:], d[:, 7:]).exp().item(),
        ),
        torch.stack(logits, dim=1),
        ret,
    )


if __name__ == "__main__":
    report = {}
    for split in ("validation", "test"):
        d = tensor(data[split])
        base, oldlog, _ = run(d, int_head=False)
        host, newlog, seq = run(d)
        tile, rlog, rseq = run(d, rtl=True)
        assert torch.equal(newlog, rlog) and torch.equal(seq, rseq) and host == tile
        report[split] = dict(
            baseline=base,
            quantized=host,
            array_replay=tile,
            min_top_two_margin=(newlog.topk(2).values.diff(dim=-1).abs().min().item()),
            max_quant_vs_float_head_abs_error=(newlog - oldlog).abs().max().item(),
        )
        if split == "test":
            torch.save({"quant": newlog, "float": oldlog}, HERE / "references.pt")
    orig = model_package(m, f, q, c["architecture"])
    assert run_byte.sha(orig) == archived["models"]["32"]["package_sha256"]
    (HERE / "float.amp").write_bytes(orig)
    from packages import COMMON

    # Serialize tensors by name; identical weight bytes in another tensor must be preserved.
    tensors = m.state_dict()
    prefix = (
        floats(f.sx)
        + floats(f.sw)
        + b"".join(floats(tensors[n]) for n in COMMON if n != "head.weight")
    )
    prefix += (
        floats(f.bias)
        + floats(tensors["down.weight"])
        + bytes(v & 255 for v in f.wq.flatten().tolist())
    )
    prefix += (
        floats(q.sx)
        + floats(q.sw)
        + bytes(v & 255 for v in q.weights.flatten().tolist())
    )
    payload = orig[HEADER.size :]
    v4 = package(32, prefix + floats(sx) + floats(sw) + packed(w) + payload[-16:], 4)
    assert len(v4) == 31728
    (HERE / "compact.amp").write_bytes(v4)
    (HERE / "quality.json").write_text(json.dumps(report, indent=2))
    print(report)
