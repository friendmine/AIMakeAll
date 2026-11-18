"""Execute an exported model on the actual RV32 cores, with identical request bytes."""

import hashlib
import json
import struct
import sys
from pathlib import Path
import torch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [
    str(ROOT / "labs/15-execution-plan"),
    str(ROOT / "labs/03-rv32-generation"),
]
from compiler import Executable, plan_dir, load
from guest import build_firmware, inspect


def firmware(out, folder, extra_cflags=()):
    plan = Executable(folder).plan
    return build_firmware(out, plan, (folder / "model.bin").read_bytes(), extra_cflags)


def scores_bits(fields):
    return torch.frombuffer(
        bytearray(struct.pack(f"<{len(fields['L'])}I", *fields["L"])),
        dtype=torch.float32,
    ).view(-1, 256)


def suite(width=48, prompt=b"Th", steps=3, folder=None):
    folder = folder or plan_dir(width)
    out = ROOT / f"build/language-soc/{width}-{prompt.hex()}"
    elf, image = firmware(out, folder)
    m = load(width)
    ex = Executable(folder)
    ids = torch.tensor([list(prompt)])
    kv = None
    ref = []
    for _ in range(steps):
        y, kv = m(ids, kv, ex, last_only=True)
        ref.append(y[0, 0])
        ids = y.argmax(-1)
    ref = torch.stack(ref)
    runs = {}
    gold = None
    for backend in ("qemu", "rtl"):
        for device in (False, True):
            label = backend + ("-npu" if device else "-cpu")
            fields = inspect(out / label, elf, image, prompt, steps, device, backend)
            outputs = (fields["L"], fields["H"], fields["J"])
            if gold is None:
                gold = outputs
            assert outputs == gold and fields["J"] == ref.argmax(-1).tolist()
            err = float((scores_bits(fields) - ref).abs().max())
            assert err < 1e-4, err
            row = dict(
                tokens=fields["J"],
                integer_hashes=fields["H"],
                commands=fields["N"],
                max_error=err,
            )
            if backend == "rtl":
                row["cycles"] = [b - a for a, b in zip(fields["U"], fields["E"])]
            runs[label] = row
    report = dict(
        width=width,
        prompt=list(prompt),
        model_sha256=ex.plan["sha256"],
        elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),
        runs=runs,
    )
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(report)
    return report


if __name__ == "__main__":
    torch.set_num_threads(1)
    torch.set_grad_enabled(False)
    suite()
