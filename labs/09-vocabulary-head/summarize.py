from pathlib import Path
from statistics import mean
import hashlib
import json
import platform
import subprocess
import torch

here = Path(__file__).resolve().parents[2] / "build/vocabulary-head"
r = json.loads((here / "timing-all.json").read_text())
quality = json.loads((here / "quality.json").read_text())
old = json.loads(
    (here.parents[1] / "labs/08-byte-transfer/verified-run.json").read_text()
)
assert len(r["results"]) == 64
assert all(
    q["quantized"]["exact"] == 64
    and q["quantized"]["ppl"] <= 1.01 * q["baseline"]["ppl"]
    for q in quality.values()
)


def metrics(row, warm=False):
    return dict(
        prefill=row["steps"][0],
        decode1=row["steps"][1],
        decode2=row["steps"][2],
        decode=sum(row["steps"][1:]),
        ttft=row["ttft"],
        full=row["full"],
        validation=row["crc_and_validation"],
        head=sum(row["head"]),
    )


def aggregate(samples):
    cols = list(samples[0])
    return {k: mean(s[k] for s in samples) for k in cols}


report = dict(
    scope="Experiment 09. Lab 08 checkpoint, FFN and QKV INT8 on H1 throughout. Each prompt starts from reset and then repeats at the same address.",
    corpus=old["splits"],
    checkpoint_tensor_sha256=old["models"]["32"]["tensor_sha256"],
    elf_sha256=r["elf_sha256"],
    tools=dict(
        python=platform.python_version(),
        torch=str(torch.__version__),
        gcc=subprocess.check_output(
            ["riscv64-unknown-elf-gcc", "--version"], text=True
        ).splitlines()[0],
        verilator=subprocess.check_output(
            ["verilator", "--version"], text=True
        ).strip(),
    ),
    n_unique_requests=len(r["results"]),
    deployment_package_bytes={
        "fp32": 42988,
        "int8": (here / "compact.amp").stat().st_size,
    },
    compact_package_sha256=hashlib.sha256(
        (here / "compact.amp").read_bytes()
    ).hexdigest(),
    ram=r["ram"],
    quality=quality,
)
for i, cache in enumerate(("cold", "warm")):
    report[cache] = {
        mode: aggregate([metrics(d[mode][i]) for d in r["results"].values()])
        for mode in ("fp32", "int8", "npu")
    }
    print(cache, report[cache])
for mode in ("fp32", "int8"):
    for key in (
        "decode",
        "ttft",
        "full",
        "head",
        "decode1",
        "decode2",
        "prefill",
        "validation",
    ):
        a, b = [report["cold"][m][key] for m in (mode, "npu")]
        print(
            mode, key, "cycles saved", a - b, "pct", 100 * (1 - b / a), "speedup", a / b
        )
report["bus_verified_head_commands"] = json.loads((here / "bus.json").read_text())[
    "head_commands"
]
report["package_faults_and_recovery"] = json.loads(
    (here / "recovery/report.json").read_text()
)
report["actual_tokens_correct"] = {
    m: sum(
        bytes(s[m][0]["tokens"]) == (b"no\n" if p[5] == "0" else b"ok\n")
        for p, s in r["results"].items()
    )
    for m in ["fp32", "int8", "npu"]
}
print("correct", report["actual_tokens_correct"])
(here / "summary.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + "\n"
)
