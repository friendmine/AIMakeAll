"""Paired three-seed ablation on Chinese course prose, then a real RV32 deployment."""

import collections
import gzip
import hashlib
import json
import math
import random
import statistics
import sys
from pathlib import Path

import torch
from torch.nn import functional as F

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "labs/17-language-soc"))
from execute import firmware, inspect, scores_bits
from compiler import Executable, compile_model
from models.byte_lm import ByteLM
from train import batch

OUT = ROOT / "build/model-study"
CFG = json.loads((HERE / "contract.json").read_text())


@torch.no_grad()
def evaluate(model, docs, plan=None):
    sums = collections.Counter()
    counts = collections.Counter()
    examples = []
    size = CFG["window"]
    for name, ids in docs.items():
        candidate = None
        for start in range(0, len(ids) - 1, size):
            x = ids[start : start + size + 1]
            logits, _ = model(
                x[None, :-1], **({"project": plan} if plan is not None else {})
            )
            y = x[1:]
            loss = F.cross_entropy(logits[0], y, reduction="none")
            for group, mask in (
                ("all", y >= 0),
                ("ascii", y < 128),
                ("continuation", (y >= 128) & (y < 192)),
                ("lead", y >= 192),
            ):
                sums[group] += loss[mask].double().sum().item()
                counts[group] += int(mask.sum())
            # First incorrectly predicted visible ASCII byte per held-out document.
            where = torch.nonzero(
                (y >= 33) & (y < 127) & (logits[0].argmax(-1) != y)
            ).flatten()
            if candidate is None and len(where):
                i = int(where[0])
                candidate = dict(
                    document=name,
                    offset=start + i + 1,
                    context=bytes(x[: i + 1].tolist()).decode(errors="replace"),
                    expected=int(y[i]),
                    predicted=int(logits[0, i].argmax()),
                )
        if candidate:
            examples.append(candidate)
    nll = {k: sums[k] / counts[k] for k in counts}
    return dict(
        bytes=dict(counts), nll=nll, ppl=math.exp(nll["all"]), examples=examples
    )


@torch.no_grad()
def paired_errors(models, docs):
    """Compare top-1 predictions at identical test offsets for the deployment seed."""
    counts = collections.Counter()
    examples = {}
    size = CFG["window"]
    for name, ids in docs.items():
        for start in range(0, len(ids) - 1, size):
            x = ids[start : start + size + 1]
            y = x[1:]
            preds = [m(x[None, :-1])[0][0].argmax(-1) for m in models]
            for group, mask in (
                ("gain", (preds[0] != y) & (preds[1] == y)),
                ("loss", (preds[0] == y) & (preds[1] != y)),
            ):
                counts[group] += int(mask.sum())
                visible = torch.nonzero(mask & (y >= 33) & (y < 127)).flatten()
                if group not in examples and len(visible):
                    i = visible[0].item()
                    examples[group] = dict(
                        document=name,
                        offset=start + i + 1,
                        context_hex=bytes(x[: i + 1].tolist()).hex(),
                        target=y[i].item(),
                        baseline=preds[0][i].item(),
                        weighted=preds[1][i].item(),
                    )
    return dict(top1_changes=dict(counts), first_printable_examples=examples)


def train(docs, seed, weight):
    torch.manual_seed(seed)
    model = ByteLM(CFG["width"])
    opt = torch.optim.AdamW(model.parameters(), lr=CFG["lr"])
    curve = []
    for step in range(CFG["steps"]):
        x, y = batch(docs, random.Random(seed * 10000 + step), CFG["batch"])
        assert x.shape[1] == CFG["window"]
        scores, _ = model(x)
        loss = F.cross_entropy(scores.flatten(0, 1), y.flatten(), reduction="none")
        w = torch.where(y.flatten() < 128, weight, 1.0)
        opt.zero_grad()
        objective = (loss * w).sum().div(w.sum())
        if (step + 1) % 100 == 0:
            curve.append(
                dict(
                    step=step + 1,
                    objective=objective.item(),
                    unweighted_nll=loss.mean().item(),
                )
            )
        objective.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
    return model.eval(), curve


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    raw = gzip.decompress((HERE / "course-prose.json.gz").read_bytes())
    docs = {
        k: torch.tensor(list(v.encode()), dtype=torch.long)
        for k, v in json.loads(raw).items()
        if len(v.encode()) > CFG["window"]
    }
    assert hashlib.sha256(raw).hexdigest() == CFG["source_sha256"]
    val, test = ({n: docs[n] for n in CFG[key]} for key in ("validation", "test"))
    train_docs = {k: v for k, v in docs.items() if k not in val and k not in test}
    assert not val.keys() & test.keys()
    records = []
    for seed in CFG["seeds"]:
        for method, weight in CFG["weights"].items():
            model, curve = train(list(train_docs.values()), seed, weight)
            torch.save(model.state_dict(), OUT / f"{seed}-{method}.pt")
            records.append(
                dict(
                    seed=seed,
                    method=method,
                    training_curve=curve,
                    validation=evaluate(model, val),
                )
            )
    means = {}
    for method in CFG["weights"]:
        rows = [r["validation"] for r in records if r["method"] == method]
        means[method] = dict(
            ascii_nll=statistics.mean(r["nll"]["ascii"] for r in rows),
            ppl=statistics.mean(r["ppl"] for r in rows),
        )
    chosen = min(
        (m for m in means if means[m]["ppl"] <= 1.05 * means["uniform"]["ppl"]),
        key=lambda m: means[m]["ascii_nll"],
    )
    for row in records:
        model.load_state_dict(
            torch.load(OUT / f"{row['seed']}-{row['method']}.pt", weights_only=True)
        )
        row["test"] = evaluate(model, test)
    paired = []
    for method in ("uniform", "ascii_x2"):
        candidate = ByteLM(CFG["width"]).eval()
        candidate.load_state_dict(
            torch.load(OUT / f"{CFG['deployment_seed']}-{method}.pt", weights_only=True)
        )
        paired.append(candidate)
    errors = paired_errors(paired, test)
    model.load_state_dict(
        torch.load(OUT / f"{CFG['deployment_seed']}-{chosen}.pt", weights_only=True)
    )
    with torch.no_grad():
        manifest = compile_model(model, OUT)
        plan = Executable(OUT)
        metrics = evaluate(model, test, plan)
        prompt = "时序".encode()
        ids = torch.tensor([list(prompt)])
        cache = None
        refs = []
        for _ in range(3):
            y, cache = model(ids, cache, project=plan, last_only=True)
            refs.append(y[0, 0])
            ids = y.argmax(-1)
        elf, image = firmware(OUT, OUT)
        outputs = {}
        command_counts = {}
        for npu in (False, True):
            fields = inspect(
                OUT / ("npu" if npu else "cpu"), elf, image, prompt, 3, npu, "rtl"
            )
            err = (scores_bits(fields) - torch.stack(refs)).abs().max().item()
            assert err < 1e-4 and fields["J"] == torch.stack(refs).argmax(-1).tolist()
            assert all(n > 0 if npu else n == 0 for n in fields["N"])
            outputs[npu] = fields["L"]
            command_counts["npu" if npu else "cpu"] = fields["N"]
        assert outputs[True] == outputs[False]
    report = dict(
        torch_version=str(torch.__version__),
        contract_sha256=hashlib.sha256(
            (HERE / "contract.json").read_bytes()
        ).hexdigest(),
        source_sha256=hashlib.sha256(raw).hexdigest(),
        splits=dict(train=list(train_docs), validation=list(val), test=list(test)),
        target_bytes_per_run=CFG["steps"] * CFG["batch"] * CFG["window"],
        records=records,
        validation_means=means,
        selected=chosen,
        paired_test=errors,
        deployment=dict(
            seed=CFG["deployment_seed"],
            sha256=manifest["sha256"],
            test_ppl=metrics["ppl"],
            prompt_hex=prompt.hex(),
            tokens=fields["J"],
            scores_checked=768,
            commands=command_counts,
            max_abs_error=err,
        ),
    )
    (OUT / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(chosen, means, report["deployment"])


if __name__ == "__main__":
    main()
