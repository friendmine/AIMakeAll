"""Boot an isolated Linux guest and collect the guest driver's self-checks."""

import argparse
import gzip
import hashlib
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "labs/15-execution-plan"))
from compiler import Executable, load, plan_dir, quantize_rows, torch

KERNEL_SHA = "8ce908a8cb28d55adcacacf8a16609fa400e07a8826f0084ae5b13b8cb91b9ab"
KERNEL_URL = "https://dl-cdn.alpinelinux.org/alpine/v3.22/releases/x86_64/netboot-3.22.8/vmlinuz-virt"
BASE = ROOT / "build/linux-qemu"
BUILD = ROOT / "build/linux-systems"


def pinned_image(path, url, digest):
    def verify(candidate):
        if hashlib.sha256(candidate.read_bytes()).hexdigest() != digest:
            raise ValueError(f"{candidate}: expected SHA-256 {digest}")

    if path.is_file():
        verify(path)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=path.parent) as scratch:
        candidate = Path(scratch) / "download"
        subprocess.run(
            [
                "curl",
                "-fL",
                "--retry",
                "2",
                "--connect-timeout",
                "15",
                "--max-time",
                "180",
                url,
                "-o",
                candidate,
            ],
            check=True,
        )
        verify(candidate)
        candidate.replace(path)


def fixture():
    model = load(48)
    plan = Executable(plan_dir(48))
    captured = []

    def project(name, layer, x):
        if name == "head":
            a, _ = quantize_rows(x[0, -1])
            w = plan.ops[name][0]
            packed = w.reshape(64, 4, 32).transpose(1, 2).contiguous()
            expected = w.int() @ a.int()
            captured.append(
                a.numpy().tobytes()
                + packed.numpy().tobytes()
                + expected.numpy().astype("<i4").tobytes()
            )
        return plan(name, layer, x)

    with torch.no_grad():
        model(torch.tensor([[84, 104]]), project=project, last_only=True)
    return captured[0]


def archive(entries):
    buf = bytearray()

    def pad():
        buf.extend(bytes(-len(buf) % 4))

    for ino, (name, mode, data, major, minor) in enumerate(
        entries + [("TRAILER!!!", 0, b"", 0, 0)], 1
    ):
        fields = (
            ino,
            mode,
            0,
            0,
            1,
            0,
            len(data),
            0,
            0,
            major,
            minor,
            len(name) + 1,
            0,
        )
        buf.extend(
            b"070701"
            + "".join(f"{x:08x}" for x in fields).encode()
            + name.encode()
            + b"\0"
        )
        pad()
        buf.extend(data)
        pad()
    return gzip.compress(buf, mtime=0)


def boot(course):
    out = BUILD / str(course)
    out.mkdir(parents=True, exist_ok=True)
    kernel = Path(
        os.environ.get("AIM_LINUX_KERNEL", ROOT / "build/system-images/vmlinuz-virt")
    )
    pinned_image(kernel, KERNEL_URL, KERNEL_SHA)
    subprocess.run(
        [
            "go",
            "build",
            "-trimpath",
            "-o",
            str(out / "init"),
            str(HERE / "driver.go"),
            str(HERE / "peer.go"),
        ],
        check=True,
        env={
            **os.environ,
            "CGO_ENABLED": "0",
            "GOOS": "linux",
            "GOARCH": "amd64",
            "GOTOOLCHAIN": "local",
            "GOCACHE": str(BUILD / "go-cache"),
        },
    )
    entries = [(name, 0o40755, b"", 0, 0) for name in ("dev", "proc", "sys", "tmp")]
    entries += [
        ("dev/console", 0o20600, b"", 5, 1),
        ("dev/null", 0o20666, b"", 1, 3),
        ("init", 0o100755, (out / "init").read_bytes(), 0, 0),
        ("fixture", 0o100444, fixture(), 0, 0),
    ]
    initrd = out / "initrd.gz"
    initrd.write_bytes(archive(entries))
    command = [
        str(BASE / "out/qemu-system-x86_64"),
        "-L",
        str(BASE / "source/pc-bios"),
        "-machine",
        "q35,accel=tcg",
        "-cpu",
        "max",
        "-m",
        "384M",
        "-smp",
        "1",
        "-kernel",
        str(kernel),
        "-initrd",
        str(initrd),
        "-append",
        f"console=ttyS0 quiet panic=-1 rdinit=/init course={course}",
        "-nographic",
        "-monitor",
        "none",
        "-no-reboot",
        "-nic",
        "none",
        "-device",
        "pcie-root-port,id=p0,bus=pcie.0,slot=1",
        "-device",
        "aim-pcie,bus=p0",
    ]
    with (out / "serial.log").open("w") as log:
        subprocess.run(
            command, check=True, stdout=log, stderr=subprocess.STDOUT, timeout=90
        )
    lines = (out / "serial.log").read_text(errors="replace").splitlines()
    report = json.loads(
        next(
            (x.split("AIM_RESULT ", 1)[1] for x in lines if "AIM_RESULT " in x), "null"
        )
    )
    if not report:
        raise RuntimeError("\n".join(lines[-20:]))
    report["kernel_sha256"] = KERNEL_SHA
    report["kernel"] = "Alpine Linux 6.12.115-0-virt x86_64"
    report["timing"] = (
        "TCG guest monotonic nanoseconds; median excludes first request of each path"
    )
    for path, rows in report["rows"].items():
        assert len(rows) == 12 and all(
            r["Digest"] == report["expected_sha256"] and r["Commands"] == 64
            for r in rows
        )
        report[path + "_median_ns"] = {
            key: int(statistics.median(x[key] for x in rows[1:]))
            for key in ("QueueNS", "CopyNS", "DeviceNS", "ServiceNS", "ClientNS")
        }
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(course, report["bdf"], {p: report[p + "_median_ns"] for p in report["rows"]})


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("course", type=int, choices=(21, 22))
    boot(p.parse_args().course)
