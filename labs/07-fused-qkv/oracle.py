"""Frozen Lab 02 checkpoints, training-only calibration and independent host references."""

import struct

import torch

from experiment import dataset, greedy, loss
from packages import HEADER, export_package, floats, make_inputs, package
from replay import project
from run import sha

QKV_CHANNELS = 48
QKV_TAIL_BYTES = 49*4 + 48*16


def packed(weight):
    return bytes(x & 255 for block in weight.split(4) for x in block.T.flatten().tolist())


def bits(values):
    return list(struct.unpack(f"<{values.numel()}I", floats(values)))


class QuantizedQKV:
    def __init__(self, model, calibration):
        ids = calibration[:, :-1]
        positions = torch.arange(ids.shape[1])
        h = model.attn_norm(model.tokens(ids) + model.positions(positions))
        self.sx = h.abs().max().clamp_min(1e-12) / 127
        self.sw = model.qkv.weight.abs().amax(1).clamp_min(1e-12) / 127
        self.weights = (model.qkv.weight / self.sw[:, None]).round().clamp(-127, 127).int()

    def compute(self, x, bias, tile=None):
        xq = (x / self.sx).round().clamp(-127, 127).int()
        flat = xq.reshape(-1, 16)
        if tile is None:
            sums = flat @ self.weights.T
        else:
            matrix, _ = project(tile, flat.tolist(), self.weights.tolist())
            sums = torch.tensor(matrix, dtype=torch.int32)
        value = (sums.float()*self.sx*self.sw + bias).reshape(*x.shape[:-1], QKV_CHANNELS)
        return sums, value


def evaluate(model, ffn, qkv, test, tile):
    ids, target = test[:, :-1], test[:, 1:]
    metrics = {}
    for mode in ("fp32", "ffn_int8", "ffn_qkv_int8", "rtl_ffn_qkv_int8"):
        projection = None if mode == "fp32" else ffn.apply
        hook = None
        device = tile if mode == "rtl_ffn_qkv_int8" else None
        if device:
            projection = lambda x: ffn.apply(x, device)
        if mode in ("ffn_qkv_int8", "rtl_ffn_qkv_int8"):
            hook = model.qkv.register_forward_hook(lambda layer, args, _: qkv.compute(args[0], layer.bias, device)[1])
        try:
            logits, _ = model(ids, projection=projection)
            suffix = greedy(model, test[:, :5], projection)
        finally:
            if hook is not None:
                hook.remove()
        if mode == "ffn_qkv_int8":
            reference_logits, reference_tokens = logits, suffix
        if device and (not torch.equal(logits, reference_logits) or not torch.equal(suffix, reference_tokens)):
            raise ValueError("held-out RTL logits or free-running tokens differ from the integer reference")
        if not torch.isfinite(logits).all():
            raise ValueError(f"non-finite {mode} reference")
        metrics[mode] = dict(ppl=loss(logits, target).exp().item(),
                             exact_sequences=int((suffix == test[:, 5:]).all(1).sum()))
    candidate = metrics["ffn_qkv_int8"]["ppl"]
    if (any(m["exact_sequences"] != len(test) for m in metrics.values())
            or candidate > 1.01*metrics["ffn_int8"]["ppl"] or candidate > 1.10*metrics["fp32"]["ppl"]):
        raise ValueError(f"quality gate failed: {metrics}")
    return dict(documents=len(test), predicted_positions=target.numel(), checked_rtl_logits=logits.numel(), **metrics)


def generation(model, ffn, qkv, prompt, target, quantized):
    out = {key: [] for key in ("I", "F", "P", "K", "Y", "tokens", "logits")}

    def project_qkv(layer, args, y):
        if quantized:
            sums, y = qkv.compute(args[0], layer.bias)
            out["I"].extend(sums.tolist())
        out["F"].extend(y[0].tolist())
        return y

    def project_ffn(x):
        acc = ffn.activation(x[0]) @ ffn.wq.T
        out["P"].extend(acc.tolist())
        return (acc.float()*ffn.sx*ffn.sw + ffn.bias).unsqueeze(0)

    ids, kv = torch.tensor([prompt]), None
    with model.qkv.register_forward_hook(project_qkv):
        for _ in range(4):
            logits, kv = model(ids, kv, projection=project_ffn)
            scores = logits[0, -1]
            token = int(scores.argmax())
            out["logits"].append(scores.tolist())
            out["tokens"].append(token)
            ids = torch.tensor([[token]])
    out["K"], out["Y"] = (tensor[0].tolist() for tensor in kv)
    if out["tokens"] != target:
        raise ValueError("reference failed held-out generation")
    return out


def prepare_model(model, ffn, test, sample, tile):
    train, _, _ = dataset()
    qkv = QuantizedQKV(model, train[:32])
    width = len(ffn.sw)
    v1 = export_package(model, ffn)
    tail = floats(qkv.sx) + floats(qkv.sw) + bytes(x & 255 for x in qkv.weights.flatten().tolist())
    blob = package(width, v1[HEADER.size:] + tail, version=2)
    prompt, target = test[sample, :5].tolist(), test[sample, 5:].tolist()
    golden = dict(fp32=generation(model, ffn, qkv, prompt, target, False),
                  int8=generation(model, ffn, qkv, prompt, target, True),
                  ffn_scales=bits(ffn.sx)+bits(ffn.sw), qkv_scales=bits(qkv.sx)+bits(qkv.sw),
                  packed_ffn=packed(ffn.wq), packed_qkv=packed(qkv.weights))
    tensor_hash = sha(b"".join(name.encode()+b"\0"+floats(t) for name, t in sorted(model.state_dict().items())))
    manifest = dict(width=width, model_tensor_sha256=tensor_hash, v1_sha256=sha(v1), v2_sha256=sha(blob),
                    package_bytes=len(blob), quality=evaluate(model, ffn, qkv, test, tile),
                    qkv_activation_scale=qkv.sx.item(), qkv_scale_words=golden["qkv_scales"],
                    ffn_scale_words=golden["ffn_scales"])
    return blob, golden, manifest, prompt


def request_inputs(prompt, a, b):
    extra = []
    for name, channel, word in (("qkv-zero-input", 0, 0), ("qkv-nan-last-channel", 48, 0x7fc00000)):
        payload = bytearray(b[HEADER.size:])
        struct.pack_into("<I", payload, len(payload)-QKV_TAIL_BYTES+4*channel, word)
        extra.append((name, package(24, payload, version=2), 4))
    return make_inputs(prompt, a, b, version=2, extra_invalid=extra)
