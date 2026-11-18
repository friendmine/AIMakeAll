from pathlib import Path
import struct
import subprocess
import json
import sys

here = Path(__file__).resolve().parents[2] / "build/vocabulary-head"
sym = {
    p.split()[3].split(".")[0]: int(p.split()[0], 16)
    for p in subprocess.check_output(
        ["riscv64-unknown-elf-nm", "-S", here / "generation.elf"], text=True
    ).splitlines()
    if len(p.split()) == 4
}
runs = json.loads(
    (here / (sys.argv[1] if len(sys.argv) > 1 else "timing-all.json")).read_text()
)["results"]
seen = 0
for prompt in runs:
    directory = here / (prompt[:4] + "-" + prompt[5] + "-npu")
    raw = (directory / "requests.bin").read_bytes()
    offset, length = struct.unpack_from("<II", raw, 8)
    assert length == 31728
    head_addr = 0x80100004 + offset + length - 16 - 4096
    writes = [
        (int(a, 16), int(v, 16), int(t))
        for a, v, t in (
            line.split() for line in (directory / "mmio").read_text().splitlines()
        )
    ]
    tiles = [
        tuple(map(int, line.split()[1:]))
        for line in (directory / "counts").read_text().splitlines()
        if line.startswith("tile ")
    ]
    assert len(writes) == 8 * len(tiles)
    n = 0
    for i, (start, end, reads, outputs, stalls) in enumerate(tiles):
        regs, values, times = zip(*writes[i * 8 : i * 8 + 8])
        if values[2] != sym["head_c"]:
            continue
        assert tuple(x - 0x10010000 for x in regs) == (16, 20, 24, 28, 32, 36, 4, 4)
        assert values == (
            sym["hx"],
            head_addr + 64 * (n % 64),
            sym["head_c"],
            1,
            4,
            16,
            1,
            2,
        )
        assert times[6] <= start <= end < times[7] and reads == 80 and outputs == 4
        n += 1
    assert n == 64 * 3 * 2
    seen += n
print(
    "Verified",
    seen,
    "vocabulary head device commands across",
    len(runs),
    "prompts, cold and warm.",
)

(here / "bus.json").write_text(
    json.dumps(dict(head_commands=seen, requests=len(runs)), indent=2) + "\n"
)
