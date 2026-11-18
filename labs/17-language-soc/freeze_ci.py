"""Refresh CI assets from the verified Lab 10/15 export and independent host reference."""

import gzip
import json
from pathlib import Path
import struct

import torch
from execute import Executable, load, plan_dir

HERE = Path(__file__).resolve().parent


@torch.no_grad()
def main():
    torch.set_num_threads(1)
    record = json.loads((HERE / "verified-run.json").read_text())
    folder = plan_dir(record["width"])
    model, plan = load(record["width"]), Executable(folder)
    assert plan.plan["sha256"] == record["model_sha256"]
    ids = torch.tensor([record["prompt"]])
    cache, scores = None, []
    for token in record["runs"]["rtl-cpu"]["tokens"]:
        y, cache = model(ids, cache, plan, last_only=True)
        scores.extend(y[0, 0].tolist())
        ids = y.argmax(-1)
        assert ids.item() == token
    (HERE / "ci-logits.f32").write_bytes(struct.pack("<768f", *scores))
    (HERE / "ci-model.bin.gz").write_bytes(
        gzip.compress((folder / "model.bin").read_bytes(), mtime=0)
    )


if __name__ == "__main__":
    main()
