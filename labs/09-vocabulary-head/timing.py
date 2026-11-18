from quality import ROOT, HERE, L8, data
import json
import struct
import torch
from concurrent.futures import ThreadPoolExecutor
import subprocess
from packages import encode_requests
from run import build, sha
from run_switch import buffer_symbols
from run_byte import writable_reservation

guest = ROOT / "labs/07-fused-qkv/qkv.c"
mheader = ROOT / "labs/06-model-switch/model.h"
elf, image = build(
    HERE,
    guest,
    (
        "-DVOCAB_HEAD_BACKENDS",
        "-include",
        L8 / "byte_shape.h",
        "-I",
        mheader.parent,
        "-Wall",
        "-Wextra",
        "-Werror",
    ),
)
cc = "riscv64-unknown-elf-gcc"
symbols = buffer_symbols(elf, cc, dict(packed=1280))
ram = writable_reservation(elf, cc)
soc = ROOT / "build/generation/soc/Vgeneration_soc"
base = (HERE / "float.amp").read_bytes()
compact = (HERE / "compact.amp").read_bytes()
refs = torch.load(HERE / "references.pt", weights_only=True)


def measure(case):
    i, mode = case
    doc = data["test"][i]
    target = list(doc[7:])
    blob = base if mode == "fp32" else compact
    out = HERE / (doc[:7].decode()[:4] + "-" + chr(doc[5]) + "-" + mode)
    out.mkdir(exist_ok=True)
    asset = out / "requests.bin"
    asset.write_bytes(encode_requests(doc[:7], [("A",), ("A",)], {"A": blob}))
    raw = subprocess.check_output(
        [
            soc,
            image,
            out / "counts",
            out / "mmio",
            {"fp32": "qkv-fp32", "int8": "qkv-int8", "npu": "qkv-npu"}[mode],
            hex(symbols["packed"]),
            out / "stores",
            asset,
            "1280",
        ],
        timeout=180,
    )
    (out / "uart").write_bytes(raw)
    parsed = {}
    for line in raw.decode().splitlines():
        parsed.setdefault(line[0], []).append(int(line[1:], 16))
    assert (
        parsed["V"] == [0, 0] and parsed["H"] == [0, 1] and parsed["J"] == target * 2
    ), parsed["J"]
    scores = torch.tensor(
        [struct.unpack("<f", struct.pack("<I", x))[0] for x in parsed["L"]]
    ).reshape(2, 3, 256)
    ref = refs["float" if mode == "fp32" else "quant"][i]
    err = float((scores - ref).abs().max())
    assert err <= 1e-4 and torch.equal(scores[0], scores[1]), err
    result = []
    tiles = [
        int(l.split()[1])
        for l in (out / "counts").read_text().splitlines()
        if l.startswith("tile ")
    ]
    for rep in range(2):
        start, end = (
            parsed["U"][3 * rep : 3 * rep + 3],
            parsed["E"][3 * rep : 3 * rep + 3],
        )
        commands = [sum(l < t < r for t in tiles) for l, r in zip(start, end)]
        assert commands == ([104, 84, 84] if mode == "npu" else [40, 20, 20]), commands
        result.append(
            dict(
                steps=[e - s for e, s in zip(end, start)],
                ttft=end[0] - parsed["A"][rep],
                full=end[-1] - parsed["A"][rep],
                crc_and_validation=parsed["B"][rep] - parsed["A"][rep],
                head=parsed["D"][3 * rep : 3 * rep + 3],
                commands=commands,
                max_error=err,
                tokens=parsed["J"][rep * 3 : rep * 3 + 3],
            )
        )
    return (doc[:7].decode(), mode, result, parsed["L"])


counts = {}
digests = {}
with ThreadPoolExecutor(max_workers=4) as pool:
    for prompt, mode, r, logs in pool.map(
        measure,
        [
            (i, mode)
            for i in range(len(data["test"]))
            for mode in ["fp32", "int8", "npu"]
        ],
    ):
        counts.setdefault(prompt, {})[mode] = r
        if mode != "fp32":
            assert digests.setdefault(prompt, logs) == logs
        print(prompt, mode, r, flush=True)
(HERE / "timing-all.json").write_text(
    json.dumps(
        dict(ram=ram, elf_sha256=sha(elf.read_bytes()), results=counts), indent=2
    )
)
