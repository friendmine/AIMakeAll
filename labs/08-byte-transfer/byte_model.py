"""Quality and independent references for the second workload. Predictions use raw byte IDs."""

from contextlib import nullcontext
import struct

import torch

from experiment import CopyTransformer, QuantizedProjection, greedy, loss
from oracle import QuantizedQKV, bits, generation_trace, packed
from packages import HEADER, export_package, floats, package
from run import sha
from train_byte import tensor
from corpus import corpus_hash


def bigram(train, docs, prompt):
    counts = torch.full((256, 256), 0.01, dtype=torch.float64)
    for doc in train:
        for a, b in zip(doc, doc[1:]):
            counts[a, b] += 1
    probabilities = counts / counts.sum(1, keepdim=True)
    scores = probabilities[docs[:, :-1], docs[:, 1:]].log()
    exact = torch.ones(len(docs), dtype=torch.bool)
    token = docs[:, prompt-1]
    for expected in docs[:, prompt:].T:
        token = counts[token].argmax(1)
        exact &= token == expected
    return dict(conditional_ppl=float((-scores[:, prompt-1:].mean()).exp()),
                full_ppl=float((-scores.mean()).exp()), exact=int(exact.sum()))


def load_candidate(path, width, cfg, records):
    ckpt = torch.load(path, map_location="cpu", weights_only=True)
    if (ckpt["width"] != width or ckpt["task"] != cfg["task"] or ckpt["recipe"] != cfg["training"]
            or ckpt["train_sha256"] != corpus_hash(records["train"])
            or ckpt["validation_sha256"] != corpus_hash(records["validation"])):
        raise ValueError("checkpoint does not match the frozen training recipe and splits")
    shape = cfg["architecture"]
    model = CopyTransformer(width, vocab=shape["vocab"], context=shape["context"]).eval()
    model.load_state_dict(ckpt["model"])
    calibration = tensor(records["train"][:cfg["training"]["calibration_documents"]])
    return model, QuantizedProjection(model, calibration), QuantizedQKV(model, calibration), ckpt["history"]


def model_package(model, ffn, qkv, shape):
    layout = struct.pack("<4I", *(shape[name] for name in ("vocab", "context", "prompt_bytes", "generated_bytes")))
    tail = floats(qkv.sx) + floats(qkv.sw) + bytes(v & 255 for v in qkv.weights.flatten().tolist())
    return package(len(ffn.sw), export_package(model, ffn)[HEADER.size:] + tail + layout, version=3)


def assess(candidate, training, evaluation, cfg, tile):
    model, ffn, qkv = candidate
    docs = tensor(evaluation)
    shape = cfg["architecture"]
    prompt, steps = shape["prompt_bytes"], shape["generated_bytes"]
    baseline = bigram(training, docs, prompt)
    result = dict(documents=len(docs), conditional_targets=len(docs)*steps, bigram=baseline)
    for label in ("fp32", "ffn_int8", "dual_int8", "dual_int8_array"):
        device = tile if label == "dual_int8_array" else None
        project = None if label == "fp32" else lambda x: ffn.apply(x, device)
        hook = nullcontext()
        if label.startswith("dual_int8"):
            hook = model.qkv.register_forward_hook(lambda layer, args, _: qkv.compute(args[0], layer.bias, device)[1])
        with hook:
            scores, _ = model(docs[:, :-1], projection=project)
            predicted = greedy(model, docs[:, :prompt], project, steps=steps)
        if not torch.isfinite(scores).all():
            raise ValueError(f"non-finite scores for {label}")
        if label == "dual_int8":
            reference_logits, reference_bytes = scores, predicted
        if device and (not torch.equal(reference_logits, scores) or not torch.equal(reference_bytes, predicted)):
            raise ValueError("array replay diverged on logits or free generation")
        result[label] = dict(
            conditional_ppl=loss(scores[:, prompt-1:], docs[:, prompt:]).exp().item(),
            full_ppl=loss(scores, docs[:, 1:]).exp().item(),
            exact=int((predicted == docs[:, prompt:]).all(1).sum()),
        )
    result["array_checked_logits"] = scores.numel()
    return result


def initial_validation(directory, cfg, records):
    """Document the first training attempt using validation only."""
    shape = cfg["architecture"]
    prompt, steps = shape["prompt_bytes"], shape["generated_bytes"]
    data = tensor(records["validation"])
    result = {}
    for width in shape["ffn_widths"]:
        model, _, _, _ = load_candidate(directory/f"byte-{width}.pt", width, cfg, records)
        scores, _ = model(data[:, :-1])
        tokens = greedy(model, data[:, :prompt], steps=steps)
        result[str(width)] = dict(tensor_sha256=tensor_hash(model),
                                  exact=int((tokens == data[:, prompt:]).all(1).sum()),
                                  conditional_ppl=loss(scores[:, prompt-1:], data[:, prompt:]).exp().item(),
                                  first_pair=tokens[:2].tolist())
    return result


def reference(candidate, prompt, steps):
    model, ffn, qkv = candidate
    return dict(fp32=generation_trace(model, ffn, qkv, prompt, steps, False),
                int8=generation_trace(model, ffn, qkv, prompt, steps, True),
                ffn_scales=bits(ffn.sx)+bits(ffn.sw), qkv_scales=bits(qkv.sx)+bits(qkv.sw),
                packed_ffn=packed(ffn.wq), packed_qkv=packed(qkv.weights))


def tensor_hash(model):
    return sha(b"".join(name.encode()+b"\0"+floats(t) for name, t in sorted(model.state_dict().items())))
