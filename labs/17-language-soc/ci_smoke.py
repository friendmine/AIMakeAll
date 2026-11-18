"""Replay the checked-in model on live RV32 firmware and both RTL paths."""

import gzip
import hashlib
import json
from pathlib import Path
import struct
from guest import build_firmware, inspect

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    out = ROOT / "build/language-ci"
    report = json.loads((HERE / "verified-run.json").read_text())
    plan = json.loads(
        (ROOT / "labs/15-execution-plan/verified-plan-48.json").read_text()
    )
    payload = gzip.decompress((HERE / "ci-model.bin.gz").read_bytes())
    assert len(payload) == plan["payload_bytes"]
    assert (
        hashlib.sha256(payload).hexdigest() == plan["sha256"] == report["model_sha256"]
    )
    reference = struct.unpack("<768f", (HERE / "ci-logits.f32").read_bytes())
    elf, image = build_firmware(out, plan, payload)
    outputs = []
    for label in ("rtl-cpu", "rtl-npu"):
        expected = report["runs"][label]
        fields = inspect(
            out / label,
            elf,
            image,
            bytes(report["prompt"]),
            3,
            label == "rtl-npu",
            "rtl",
        )
        for key, field in (("tokens", "J"), ("integer_hashes", "H"), ("commands", "N")):
            assert expected[key] == fields[field], (label, key)
        scores = struct.unpack("<768f", struct.pack("<768I", *fields["L"]))
        assert all(abs(a - b) <= 1e-4 for a, b in zip(scores, reference))
        outputs.append(fields["L"])
    assert outputs[0] == outputs[1]
    print(
        "CPU and NPU matched 768 logits, 3 integer hashes, 3 output bytes and all command counts."
    )


if __name__ == "__main__":
    main()
