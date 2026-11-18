"""Train on an immutable, document-disjoint snapshot of Python's English reference manual."""

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import torch
from torch.nn import functional as F

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from models.byte_lm import ByteLM, generate

BUILD = ROOT / "build/language"
SEED, STEPS, BATCH, WINDOW = 1011, 1600, 16, 48


def corpus():
    raw = (HERE / "python-help.json.gz").read_bytes()
    docs = json.loads(gzip.decompress(raw))
    names = sorted(n for n in docs if len(docs[n].encode()) > WINDOW)
    random.Random(SEED).shuffle(names)
    groups = dict(train=names[16:], validation=names[:8], test=names[8:16])
    return (
        {
            k: [torch.tensor(list(docs[n].encode()), dtype=torch.long) for n in v]
            for k, v in groups.items()
        },
        groups,
        hashlib.sha256(raw).hexdigest(),
    )


def batch(documents, rng, count=BATCH):
    spans = [rng.choice(documents) for _ in range(count)]
    rows = []
    for doc in spans:
        start = rng.randrange(len(doc) - WINDOW)
        rows.append(doc[start : start + WINDOW + 1])
    values = torch.stack(rows)
    return values[:, :-1], values[:, 1:]


def checkpoint(width):
    return BUILD / f"width-{width}.pt"


def load(width):
    model = ByteLM(width)
    model.load_state_dict(torch.load(checkpoint(width), weights_only=True)["model"])
    return model.eval()


@torch.no_grad()
def evaluate(model, documents, counts):
    nll = total = 0
    markov = 0.0
    for doc in documents:
        for start in range(0, len(doc) - 1, WINDOW):
            seq = doc[start : start + WINDOW + 1]
            pred, _ = model(seq[None, :-1])
            nll += F.cross_entropy(pred[0], seq[1:], reduction="sum").item()
            markov -= counts[seq[:-1], seq[1:]].log().sum().item()
            total += len(seq) - 1
    return dict(
        target_bytes=total,
        ppl=math.exp(nll / total),
        bigram_ppl=math.exp(markov / total),
    )


def run(width):
    BUILD.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(SEED)
    data, groups, digest = corpus()
    model = ByteLM(width)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.003)
    history = []
    for step in range(STEPS):
        x, y = batch(data["train"], random.Random(SEED + step))
        scores, _ = model(x)
        loss = F.cross_entropy(scores.reshape(-1, 256), y.reshape(-1))
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        if (step + 1) % 200 == 0:
            history.append([step + 1, loss.item()])
        if step + 1 == STEPS // 2:
            saved = BUILD / f"resume-{width}.pt"
            torch.save(
                dict(
                    model=model.state_dict(),
                    optimizer=optimizer.state_dict(),
                    step=step + 1,
                ),
                saved,
            )
            other = ByteLM(width)
            other_opt = torch.optim.AdamW(other.parameters(), lr=0.003)
            state = torch.load(saved, weights_only=True)
            other.load_state_dict(state["model"])
            other_opt.load_state_dict(state["optimizer"])
            # Compare the first subsequent update, including restored Adam moments.
            a, b = batch(data["train"], random.Random(SEED + step + 1))
            score, _ = other(a)
            F.cross_entropy(score.reshape(-1, 256), b.reshape(-1)).backward()
            torch.nn.utils.clip_grad_norm_(other.parameters(), 1.0)
            other_opt.step()
        if step + 1 == STEPS // 2 + 1:
            assert all(
                torch.equal(p, q)
                for p, q in zip(model.parameters(), other.parameters())
            )
            model, optimizer = other, other_opt
    counts = torch.full((256, 256), 0.1, dtype=torch.float64)
    for doc in data["train"]:
        counts += torch.bincount(doc[:-1] * 256 + doc[1:], minlength=65536).reshape(
            256, 256
        )
    counts /= counts.sum(1, keepdim=True)
    model.eval()
    metrics = {s: evaluate(model, data[s], counts) for s in ("validation", "test")}
    with torch.no_grad():
        x = data["test"][0][:40][None]
        changed = x.clone()
        changed[:, 20:] = (changed[:, 20:] + 91) % 256
        assert torch.equal(model(x)[0][:, :20], model(changed)[0][:, :20])
        text = generate(model, b"The ", 24).decode(errors="backslashreplace")
    assert all(v["ppl"] < v["bigram_ppl"] for v in metrics.values()), metrics
    torch.save(
        dict(model=model.state_dict(), width=width, corpus=digest), checkpoint(width)
    )
    report = dict(
        width=width,
        parameters=sum(p.numel() for p in model.parameters()),
        seed=SEED,
        steps=STEPS,
        batch=BATCH,
        window=WINDOW,
        train_bytes=STEPS * BATCH * WINDOW,
        corpus_sha256=digest,
        topics=groups,
        metrics=metrics,
        history=history,
        sample="The " + text,
        resume_identical=True,
    )
    (BUILD / f"metrics-{width}.json").write_text(json.dumps(report, indent=2) + "\n")
    print(width, metrics, repr(text))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", choices=(48, 40), type=int, default=48)
    run(parser.parse_args().width)
