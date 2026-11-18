"""Fetch live weights and KV via guest physical addresses for each real model step."""

import hashlib
import json
import sys
from collections import Counter

from machine import Machine, ROOT

sys.path.insert(0, str(ROOT / "labs/15-execution-plan"))
from compiler import Executable, load, plan_dir, torch
from models.byte_lm import ByteLM, DIM, HEADS, LAYERS

PROMPT = b"The argument is "
STEPS = 4
WEIGHT_BYTES = plan_dir(48) / "model.bin"
KV_STEP = LAYERS * 2 * DIM * 4
LOW_BUDGET = 80 * 1024


class Region:
    def __init__(self, machine, base, size, counters, tier):
        self.machine, self.base, self.size = machine, base, size
        self.counts, self.tier = counters, tier

    def access(self, offset, length, data=None):
        if (
            offset < 0
            or length < 0
            or offset + length > self.size
            or (data is not None and len(data) != length)
        ):
            raise ValueError("allocation boundary")
        out = bytearray()
        op = "read" if data is None else "write"
        self.counts[f"{self.tier}_{op}"] += length
        for i in range(0, length, 1024):
            addr = self.base + offset + i
            n = min(1024, length - i)
            if data is None:
                out.extend(self.machine.read(addr, n))
            else:
                self.machine.write(addr, data[i : i + n])
        return bytes(out)


def move_model(raw):
    # Every inference parameter comes from the selected emulated memory tier.
    execution = Executable(plan_dir(48), payload=raw)
    model = ByteLM(48).eval()
    for name, tensor in model.named_parameters():
        if name in execution.plan["floats"]:
            offset = execution.plan["floats"][name]
            values = torch.frombuffer(
                bytearray(raw[offset : offset + tensor.numel() * 4]),
                dtype=torch.float32,
            )
            tensor.copy_(values.reshape_as(tensor))
    return model, execution


def encode(cache, begin):
    # Layout per token: layer, K/V, head, channel; append only newly generated rows.
    pairs = torch.stack([torch.stack(pair) for pair in cache])
    return (
        pairs[:, :, :, :, begin:, :]
        .permute(4, 0, 1, 2, 3, 5)
        .contiguous()
        .numpy()
        .tobytes()
    )


def decode(raw):
    t = torch.frombuffer(bytearray(raw), dtype=torch.float32).reshape(
        -1, LAYERS, 2, 1, HEADS, DIM // HEADS
    )
    t = t.permute(1, 2, 3, 4, 0, 5).contiguous()
    return [(k, v) for k, v in t]


def capacity(wtier, ktier):
    sizes = Counter()
    sizes[wtier] += WEIGHT_BYTES.stat().st_size
    sizes[ktier] += KV_STEP * (len(PROMPT) + STEPS - 1)
    return sizes


def run(machine, wtier, ktier, gold):
    size = capacity(wtier, ktier)
    bases = {"local": 32 << 20, "cxl": machine.window + 0x10000}
    counts = Counter()
    weights = Region(machine, bases[wtier], WEIGHT_BYTES.stat().st_size, counts, wtier)
    kv = Region(
        machine,
        bases[ktier] + (1 << 20),
        KV_STEP * (len(PROMPT) + STEPS - 1),
        counts,
        ktier,
    )
    raw = WEIGHT_BYTES.read_bytes()
    weights.access(0, len(raw), raw)
    initial_writes = dict(counts)
    counts.clear()
    length = 0
    inputs = torch.tensor([list(PROMPT)])
    tokens = []
    all_scores = hashlib.sha256()
    for expected in gold:
        model, execution = move_model(weights.access(0, len(raw)))
        past = decode(kv.access(0, length * KV_STEP)) if length else None
        logits, cache = model(inputs, past, execution, last_only=True)
        assert torch.equal(logits, expected)
        append = encode(cache, length)
        kv.access(length * KV_STEP, len(append), append)
        length += inputs.numel()
        all_scores.update(logits.numpy().tobytes())
        inputs = logits.argmax(-1)
        tokens.append(int(inputs.item()))
    blocked = False
    try:
        kv.access(kv.size, 1)
    except ValueError:
        blocked = True
    assert blocked
    remote = counts["cxl_read"] + counts["cxl_write"]
    return dict(
        weights=wtier,
        kv=ktier,
        capacity=dict(size),
        fits_80_KiB=size["local"] <= LOW_BUDGET,
        setup_bytes=initial_writes,
        request_bytes=dict(counts),
        generated=tokens,
        logits_sha256=all_scores.hexdigest(),
        scores_checked=STEPS * 256,
        bounds_rejected=blocked,
        remote_transfer_lower_bound_ns={
            str(gbps): remote / gbps for gbps in (8, 16, 32)
        },
    )


def main():
    torch.set_num_threads(1)
    torch.set_grad_enabled(False)
    gold = []
    model = load(48)
    plan = Executable(plan_dir(48))
    inputs = torch.tensor([list(PROMPT)])
    cache = None
    for _ in range(STEPS):
        logits, cache = model(inputs, cache, plan, last_only=True)
        gold.append(logits)
        inputs = logits.argmax(-1)
    with Machine() as vm:
        runs = [
            run(vm, w, k, gold)
            for w, k in (
                ("local", "local"),
                ("local", "cxl"),
                ("cxl", "local"),
                ("cxl", "cxl"),
            )
        ]
        report = dict(
            model_width=48,
            prompt=PROMPT.decode(),
            steps=STEPS,
            window_hpa=hex(vm.window),
            hdm_decoder_control=hex(vm.control),
            uncommitted_write_blocked=vm.uncommitted_hidden,
            type3_capacity_bytes=256 << 20,
            local_budget_bytes=LOW_BUDGET,
            runs=runs,
            accounting="Per-step full weight fetch, incremental KV append; bandwidth-only estimate for decimal GB/s.",
        )
    assert not runs[0]["fits_80_KiB"] and all(r["fits_80_KiB"] for r in runs[1:])
    assert len({r["logits_sha256"] for r in runs}) == 1
    out = ROOT / "build/cxl-placement"
    out.mkdir(exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print([(r["weights"], r["kv"], r["fits_80_KiB"], r["request_bytes"]) for r in runs])


if __name__ == "__main__":
    main()
