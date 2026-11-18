"""Run one RV32 ELF on QEMU and PicoRV32 and check its causal generation."""

import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

import torch

from build_guest import build
from trace_checks import LOGIT_TOLERANCE, check_counters, check_mmio, check_uart

HERE = Path(__file__).resolve().parent
LAB02 = HERE.parent / "02-trained-projection"
sys.path.insert(0, str(LAB02))
from experiment import CopyTransformer, QuantizedProjection, SEED, STEPS, dataset  # noqa: E402


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(values):
    value = 2166136261
    for byte in values:
        value = ((value ^ (byte & 255)) * 16777619) & 0xFFFFFFFF
    return value


def load_model(checkpoint, width=32):
    if width not in (24, 32):
        raise ValueError(f"unsupported Lab 02 width {width}")
    state = torch.load(checkpoint, map_location="cpu", weights_only=True)
    if (state["task"], state["width"], state["step"], state["seed"]) != (
        "copy-three-v1",
        width,
        STEPS,
        SEED,
    ):
        raise ValueError(f"expected the completed Lab 02 width-{width} checkpoint")
    model = CopyTransformer(width).eval()
    model.load_state_dict(state["model"])
    train, _, test = dataset()
    q = QuantizedProjection(model, train[:32])
    payload = (LAB02 / "projection-fixture.json").read_bytes()
    archived = json.loads((LAB02 / "verified-run.json").read_text())
    if sha(payload) != archived["fixture_sha256"]:
        raise ValueError("Lab 02 fixture digest differs from its published report")
    fixture = next(m for m in json.loads(payload)["models"] if m["width"] == width)
    if (q.wq.tolist(), q.sx.item(), q.sw.tolist(), q.bias.tolist()) != (
        fixture["weight_i8"],
        fixture["activation_scale"],
        fixture["weight_scales"],
        fixture["bias"],
    ):
        raise ValueError(
            "checkpoint projection differs from the published Lab 02 weights/scales/bias"
        )
    return model, q, test


def export(model, q, prompt, folder):
    lines = []
    tensor_bytes = bytearray()
    for name, tensor in sorted(model.state_dict().items()):
        values = tensor.flatten().tolist()
        tensor_bytes.extend(
            name.encode() + b"\0" + struct.pack(f"<{len(values)}f", *values)
        )
        if name != "up.weight":  # its quantized representation is exported below
            lines.append(
                f"static const float {name.replace('.', '_')}[] = {{"
                + ",".join(v.hex() + "f" for v in values)
                + "};"
            )
    lines.append(f"static const float activation_scale = {q.sx.item().hex()}f;")
    lines.append(
        "static const float weight_scales[] = {"
        + ",".join(v.hex() + "f" for v in q.sw.tolist())
        + "};"
    )
    lines.append(
        "static const int8_t weight_i8[] = {"
        + ",".join(map(str, q.wq.flatten().tolist()))
        + "};"
    )
    lines.append(
        "static const uint8_t prompt[] = {" + ",".join(map(str, prompt)) + "};"
    )
    (folder / "model.h").write_text("\n".join(lines) + "\n")
    return sha(tensor_bytes)


def reference(model, q, prompt):
    steps = []
    ids = torch.tensor([prompt])
    cache = None
    for step in range(4):
        tiles = []

        def projection(features):
            x = q.activation(features[0])
            acc = x @ q.wq.T
            for i in range(0, len(x), 4):
                for j in range(0, len(q.wq), 4):
                    a = x[i : i + 4]
                    w = q.wq[j : j + 4]
                    tiles.append(
                        dict(
                            row=i,
                            col=j,
                            m=len(a),
                            n=len(w),
                            k=x.size(1),
                            a_hash=digest(a.flatten().tolist()),
                            b_hash=digest(w.T.flatten().tolist()),
                            sums=acc[i : i + 4, j : j + 4].flatten().tolist(),
                        )
                    )
            return (acc.float() * q.sx * q.sw + q.bias).unsqueeze(0)

        logits, cache = model(ids, cache, projection)
        scores = logits[0, -1]
        token = int(scores.argmax())
        steps.append(dict(tiles=tiles, logits=scores.tolist(), token=token))
        if token == 10:
            break
        ids = torch.tensor([[token]])
    return steps


def run_backend(command, path):
    result = subprocess.run(command, stdout=subprocess.PIPE, timeout=180)
    path.write_bytes(result.stdout)
    result.check_returncode()
    return result.stdout


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ["checkpoint", "qemu", "rtl", "output"]:
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--sample", type=int, default=0, choices=range(64))
    args = p.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    # One writer owns the UART, bus traces and success report for this sample.
    with (out / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        (out / "report.json").unlink(missing_ok=True)
        execute(args, out)


@torch.no_grad()
def execute(args, out):
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    model, q, test = load_model(args.checkpoint)
    prompt = test[args.sample, :5].tolist()
    model_hash = export(model, q, prompt, out)
    steps = reference(model, q, prompt)
    tokens = [s["token"] for s in steps]
    if tokens != test[args.sample, 5:].tolist():
        raise ValueError("CPU reference failed the held-out copy task")
    elf, image = build(out)
    qlog = out / "qemu-mmio.log"
    q_uart = run_backend(
        [
            args.qemu,
            "-trace",
            "enable=memory_region_ops_write",
            "-D",
            qlog,
            "-M",
            "virt",
            "-m",
            "32M",
            "-smp",
            "1",
            "-bios",
            "none",
            "-kernel",
            elf,
            "-display",
            "none",
            "-serial",
            "stdio",
            "-monitor",
            "none",
            "-nic",
            "none",
            "-icount",
            "shift=0",
        ],
        out / "qemu.uart",
    )
    addresses, reports = check_uart(q_uart, "QEMU", steps)
    print(
        "QEMU matched the quantized model at every tile, logit and generated token",
        flush=True,
    )
    counters = out / "rtl-counters.txt"
    rtl_mmio = out / "rtl-mmio.txt"
    rtl_uart = run_backend([args.rtl, image, counters, rtl_mmio], out / "rtl.uart")
    check_uart(rtl_uart, "RTL", steps)
    if rtl_uart != q_uart:
        raise ValueError(
            "same firmware produced different raw QEMU and RTL UART records"
        )
    mmio_writes = check_mmio(qlog, rtl_mmio, addresses, steps)
    stages = check_counters(counters, steps)
    for s, stage in zip(reports, stages):
        s["rtl_cycles"] = stage["elapsed_cycles"]
        s["rtl_tile_cycles"] = sum(t["cycles"] for t in stage["tiles"])
        s["rtl_dma_input_bytes"] = sum(t["dma_byte_reads"] for t in stage["tiles"])
        s["rtl_dma_output_bytes"] = 4 * sum(
            t["dma_word_writes"] for t in stage["tiles"]
        )
    report = dict(
        task="copy-three-v1",
        sample=args.sample,
        width=32,
        prompt=prompt,
        tokens=tokens,
        model_tensor_sha256=model_hash,
        elf_sha256=sha(elf.read_bytes()),
        image_sha256=sha(image.read_bytes()),
        uart_sha256=sha(q_uart),
        addresses=addresses,
        checked_mmio_writes=mmio_writes,
        max_logit_tolerance=LOGIT_TOLERANCE,
        first_tile=steps[0]["tiles"][0],
        steps=reports,
    )
    temp = out / "report.tmp"
    temp.write_text(json.dumps(report, indent=2) + "\n")
    temp.replace(out / "report.json")
    print(
        f"PASS {prompt} -> {tokens}, {sum(s['commands'] for s in reports)} commands, "
        f"{sum(s['integers'] for s in reports)} integers; report {out / 'report.json'}"
    )


if __name__ == "__main__":
    main()
