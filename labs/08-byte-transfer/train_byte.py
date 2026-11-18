"""Train both fixed candidates with equal budgets and isolate held-out IDs by document."""

import argparse
import json
from pathlib import Path
import sys
import tempfile

import torch
from torch.nn import functional as F

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from models.tiny_copy import CopyTransformer
from corpus import corpus_hash, documents


def tensor(records):
    return torch.tensor([list(row) for row in records], dtype=torch.long)


def train(width, contract, records):
    cfg = contract["training"]
    torch.manual_seed(cfg["seed"])
    shape = contract["architecture"]
    model = CopyTransformer(width, vocab=shape["vocab"], context=shape["context"])
    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg["learning_rate"])
    train_set, val = (tensor(records[s]) for s in ("train", "validation"))
    generator = torch.Generator().manual_seed(cfg["seed"]+1)
    first_target = shape["prompt_bytes"] if cfg.get("objective") == "completion_bytes" else 1
    def objective(scores, batch):
        targets = batch[:, first_target:]
        predictions = scores[:, first_target-1:]
        return F.cross_entropy(predictions.reshape(-1, shape["vocab"]), targets.reshape(-1))

    history = []
    for step in range(1, cfg["steps"]+1):
        batch = train_set[torch.randint(len(train_set), (cfg["batch"],), generator=generator)]
        scores, _ = model(batch[:, :-1])
        loss = objective(scores, batch)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        if step % 100 == 0:
            with torch.no_grad():
                v, _ = model(val[:, :-1])
                history.append([step, loss.item(), objective(v, val).item()])
    return dict(task=contract["task"], width=width, recipe=cfg, model=model.state_dict(),
                train_sha256=corpus_hash(records["train"]), validation_sha256=corpus_hash(records["validation"]),
                history=history)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--width", type=int, choices=(24, 32), required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--contract", type=Path, default=HERE/"contract.json")
    args = p.parse_args()
    contract = json.loads(args.contract.read_text())
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    checkpoint = train(args.width, contract, documents(contract))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Unique temporary directory also keeps the torch archive member name deterministic.
    with tempfile.TemporaryDirectory(dir=args.output.parent) as tmp:
        scratch = Path(tmp)/args.output.name
        torch.save(checkpoint, scratch)
        scratch.replace(args.output)
    print(f"width={args.width} final train/validation losses {checkpoint['history'][-1][1:]}")
