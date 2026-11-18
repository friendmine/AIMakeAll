"""A compact package with a bad checksum or zero head scale must not reach the device."""

import json
import struct
import subprocess

from quality import HERE, ROOT, data
from packages import HEADER, encode_requests, package
from run_switch import buffer_symbols

compact = (HERE / "compact.amp").read_bytes()
crc_fault = bytearray(compact)
crc_fault[-1] ^= 1
payload = bytearray(compact[HEADER.size :])
# The tail holds 257 float scales, the packed 256 x 16 head and four shape words.
struct.pack_into("<f", payload, len(payload) - 16 - 4096 - 257 * 4, 0.0)
models = {"crc": crc_fault, "scale": package(32, payload, 4), "valid": compact}
out = HERE / "recovery"
out.mkdir(exist_ok=True)
doc = data["test"][0]
asset = out / "requests.bin"
asset.write_bytes(encode_requests(doc[:7], [(n,) for n in models], models))
packed = buffer_symbols(
    HERE / "generation.elf", "riscv64-unknown-elf-gcc", {"packed": 1280}
)["packed"]
uart = subprocess.check_output(
    [
        ROOT / "build/generation/soc/Vgeneration_soc",
        HERE / "generation.bin",
        out / "counts",
        out / "mmio",
        "qkv-npu",
        hex(packed),
        out / "stores",
        asset,
        "1280",
    ],
    timeout=180,
)
(out / "uart").write_bytes(uart)
fields = {}
for line in uart.decode().splitlines():
    fields.setdefault(line[0], []).append(int(line[1:], 16))
assert (
    fields["V"] == [3, 4, 0]
    and fields["G"] == [0, 0, 1]
    and fields["J"] == list(doc[7:])
)
lines = [line.split() for line in (out / "counts").read_text().splitlines()]
begins, ends = (
    [list(map(int, row[1:])) for row in lines if row[0] == tag] for tag in ("R", "Z")
)
tiles = [int(row[1]) for row in lines if row[0] == "tile"]
stores = [int(row.split()[0]) for row in (out / "stores").read_text().splitlines()]
mmio = [int(row.split()[-1]) for row in (out / "mmio").read_text().splitlines()]
assert len(begins) == len(ends) == len(models)
checks = {}
for i, name in enumerate(models):
    (start, rx), (end, tx) = begins[i], ends[i]
    activity = {
        kind: sum(start < t < end for t in values)
        for kind, values in (
            ("tiles", tiles),
            ("prepack_stores", stores),
            ("mmio_writes", mmio),
        )
    }
    activity["dma_beats"] = tx - rx
    assert not any(activity.values()) if name != "valid" else all(activity.values())
    checks[name] = dict(status=fields["V"][i], **activity)
(out / "report.json").write_text(json.dumps(checks, indent=2) + "\n")
print(checks)
