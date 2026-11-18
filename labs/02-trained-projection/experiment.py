"""Train two small causal models and replace their trained FFN projection with RTL."""

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import random

import torch
from torch.nn import functional as F

from replay import project, run_cases
from models.tiny_copy import CopyTransformer, DIM, VOCAB

SEED = 2701
STEPS = 400
WIDTHS = (32, 24)


def dataset():
    triples = list(itertools.product(range(8), repeat=3))
    random.Random(SEED).shuffle(triples)
    documents = torch.tensor([[8, *t, 9, *t, 10] for t in triples])
    return documents[:384], documents[384:448], documents[448:]


def bigram_ppl(train, evaluation):
    counts = torch.ones(VOCAB, VOCAB, dtype=torch.float64)
    for row in train.tolist():
        for a, b in zip(row, row[1:]):
            counts[a, b] += 1
    probabilities = counts / counts.sum(1, keepdim=True)
    return float(
        (-probabilities[evaluation[:, :-1], evaluation[:, 1:]].log().mean()).exp()
    )


def loss(logits, labels):
    return F.cross_entropy(logits.reshape(-1, VOCAB), labels.reshape(-1))


def train_model(width, train, validation, steps, resume, output):
    torch.manual_seed(SEED)
    model = CopyTransformer(width)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.006)
    checkpoint = output / f"copy-{width}.pt"
    begin = 0
    history = []
    if resume:
        state = torch.load(checkpoint, map_location="cpu", weights_only=True)
        if (
            state["task"] != "copy-three-v1"
            or state["seed"] != SEED
            or state["width"] != width
            or state["step"] > steps
        ):
            raise ValueError("incompatible checkpoint or requested step")
        model.load_state_dict(state["model"])
        optimizer.load_state_dict(state["optimizer"])
        begin, history = state["step"], state["history"]
    for step in range(begin, steps):
        # Per-step seed makes the document order identical across widths and resume.
        generator = torch.Generator().manual_seed(SEED + step)
        batch = train[torch.randint(len(train), (32,), generator=generator)]
        logits, _ = model(batch[:, :-1])
        batch_loss = loss(logits, batch[:, 1:])
        optimizer.zero_grad()
        batch_loss.backward()
        optimizer.step()
        if (step + 1) % 50 == 0:
            with torch.no_grad():
                logits, _ = model(validation[:, :-1])
                history.append(
                    [
                        step + 1,
                        batch_loss.item(),
                        loss(logits, validation[:, 1:]).item(),
                    ]
                )
    temp = checkpoint.with_suffix(".tmp")
    torch.save(
        dict(
            task="copy-three-v1",
            width=width,
            seed=SEED,
            step=steps,
            model=model.state_dict(),
            optimizer=optimizer.state_dict(),
            history=history,
        ),
        temp,
    )
    temp.replace(checkpoint)
    return model.eval(), history


class QuantizedProjection:
    def __init__(self, model, calibration):
        _, features, _ = model.features(calibration[:, :-1])
        self.sx = features.abs().max().clamp_min(1.0e-12) / 127
        weight = model.up.weight
        self.sw = weight.abs().amax(1).clamp_min(1.0e-12) / 127
        self.wq = (weight / self.sw[:, None]).round().clamp(-127, 127).int()
        self.bias = model.up.bias

    def activation(self, x):
        return (x / self.sx).round().clamp(-127, 127).int()

    def apply(self, x, binary=None):
        xq = self.activation(x).reshape(-1, DIM)
        if binary is None:
            acc = xq @ self.wq.T
        else:
            values, _ = project(binary, xq.tolist(), self.wq.tolist())
            acc = torch.tensor(values, dtype=torch.int32)
        y = acc.float() * self.sx * self.sw + self.bias
        return y.reshape(*x.shape[:-1], -1)


def greedy(model, prefix, projection=None):
    logits, cache = model(prefix, projection=projection)
    suffix = []
    for index in range(4):
        token = logits[:, -1].argmax(-1, keepdim=True)
        suffix.append(token)
        if index < 3:
            logits, cache = model(token, cache, projection)
    return torch.cat(suffix, dim=1)


@torch.no_grad()
def evaluate(model, train, validation, evaluation, shared, banked):
    q = QuantizedProjection(model, train[:32])
    val_logits, _ = model(validation[:, :-1], projection=q.apply)
    ids, labels = evaluation[:, :-1], evaluation[:, 1:]
    floats, _ = model(ids)
    integers, _ = model(ids, projection=q.apply)
    if not torch.isfinite(integers).all():
        raise ValueError("invalid logits")
    # Full teacher-forced held-out evaluation: the selected projection is replaced
    # on every position of every document. All other operators still execute on CPU.
    for binary in [shared, banked]:
        hybrid, _ = model(ids, projection=lambda x: q.apply(x, binary))
        torch.testing.assert_close(hybrid, integers, atol=0, rtol=0)

    prefix = evaluation[:1, :5]
    _, h_prefill, cache = model.features(prefix)
    _, h_decode, _ = model.features(evaluation[:1, 5:6], cache)
    # KV incremental and full-prefix computation need not use identical FP kernels.
    _, h_full, _ = model.features(evaluation[:1, :6])
    torch.testing.assert_close(h_decode, h_full[:, -1:], atol=1.0e-5, rtol=1.0e-5)
    torch.testing.assert_close(
        floats[:1, :5], model(prefix)[0], atol=1.0e-5, rtol=1.0e-5
    )
    suffix = greedy(model, evaluation[:, :5], q.apply)
    sample = greedy(model, prefix, lambda x: q.apply(x, banked))
    if not torch.equal(sample, suffix[:1]):
        raise ValueError("hybrid greedy generation differs from INT8 CPU")
    metrics = dict(
        parameters=sum(p.numel() for p in model.parameters()),
        validation_quant_ppl=loss(val_logits, validation[:, 1:]).exp().item(),
        float_ppl=loss(floats, labels).exp().item(),
        quant_ppl=loss(integers, labels).exp().item(),
        max_abs_logit_error=(integers - floats).abs().max().item(),
        matched_hybrid_logits=integers.numel(),
        test_documents=len(evaluation),
        quant_exact_sequences=int((suffix == evaluation[:, 5:]).all(1).sum()),
        sample_prompt=prefix[0].tolist(),
        hybrid_generation=sample[0].tolist(),
    )
    asset = dict(
        width=len(q.sw),
        activation_scale=q.sx.item(),
        weight_scales=q.sw.tolist(),
        bias=q.bias.tolist(),
        weight_i8=q.wq.tolist(),
        inputs=dict(
            prefill=q.activation(h_prefill[0]).tolist(),
            decode=q.activation(h_decode[0]).tolist(),
        ),
    )
    return metrics, asset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shared", type=Path)
    parser.add_argument("--banked", type=Path)
    parser.add_argument(
        "--train-only",
        action="store_true",
        help="save checkpoints without accessing the test set or RTL",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--steps", default=STEPS, type=int)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.steps < 1:
        parser.error("steps must be positive")
    if not args.train_only and (args.shared is None or args.banked is None):
        parser.error("full evaluation requires --shared and --banked")
    args.output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    train, validation, test = dataset()
    models = []
    metrics = []
    for width in WIDTHS:
        model, history = train_model(
            width, train, validation, args.steps, args.resume, args.output
        )
        if args.train_only:
            print(f"saved width={width} at step {args.steps}", flush=True)
            continue
        scores, asset = evaluate(model, train, validation, test, args.shared, args.banked)
        metrics.append(dict(width=width, loss_history=history, **scores))
        models.append(asset)
        print(
            f"width={width}, FP32 PPL={scores['float_ppl']:.4f}, INT8 PPL={scores['quant_ppl']:.4f}, "
            f"greedy copy={scores['quant_exact_sequences']}/{len(test)}",
            flush=True,
        )
    if args.train_only:
        return
    baseline = bigram_ppl(train, test)
    fixture = dict(task="copy-three-v1", seed=SEED, steps=args.steps, models=models)
    payload = json.dumps(fixture, separators=(",", ":")) + "\n"
    (args.output / "projection-fixture.json").write_text(payload)
    records = run_cases(fixture, args.shared, args.banked, args.output)
    split_hashes = {
        name: hashlib.sha256(bytes(data.flatten().tolist())).hexdigest()
        for name, data in [("train", train), ("validation", validation), ("test", test)]
    }
    report = dict(
        torch_version=str(torch.__version__),
        steps=args.steps,
        split_sha256=split_hashes,
        baseline_bigram_ppl=baseline,
        fixture_sha256=hashlib.sha256(payload.encode()).hexdigest(),
        model_scores=metrics,
        hardware=records,
    )
    (args.output / "experiment.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
