"""Connect two isolated QEMU guests by a private socketpair acting as an Ethernet wire."""

from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import socket
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "labs/21-linux-driver"))
from boot import BASE, BUILD, KERNEL_SHA, KERNEL_URL, pinned_image

INITRD_SHA = "6dde230b0e49d80c54337e2854d7cff6e8c9aa8cfa37588eaf9df4dd325a87a9"


def stop(process):
    if process.poll() is None:
        process.kill()
        process.wait()


def collect(out, role):
    lines = (out / f"{role}.log").read_text(errors="replace").splitlines()
    for line in lines:
        if "AIM_RESULT " in line:
            return json.loads(line.split("AIM_RESULT ", 1)[1])
    raise RuntimeError(f"{role}: " + "\n".join(lines[-12:]))


def main():
    out = BUILD / "22"
    image = Path(
        os.environ.get(
            "AIM_LINUX_INITRAMFS", ROOT / "build/system-images/alpine-net-initramfs"
        )
    )
    pinned_image(
        image, KERNEL_URL.replace("vmlinuz-virt", "initramfs-virt"), INITRD_SHA
    )
    # Linux unpacks both archives; the course /init replaces the distribution entry point.
    merged = out / "peer.initrd"
    merged.write_bytes(image.read_bytes() + (out / "initrd.gz").read_bytes())
    kernel = Path(
        os.environ.get("AIM_LINUX_KERNEL", ROOT / "build/system-images/vmlinuz-virt")
    )
    assert hashlib.sha256(kernel.read_bytes()).hexdigest() == KERNEL_SHA
    with ExitStack() as cleanup:
        endpoints = socket.socketpair()
        procs = []
        for index, (role, endpoint) in enumerate(
            zip(("server", "client"), endpoints), 1
        ):
            cleanup.callback(endpoint.close)
            cmd = [
                str(BASE / "out/qemu-system-x86_64"),
                "-L",
                str(BASE / "source/pc-bios"),
                "-machine",
                "q35,accel=tcg",
                "-m",
                "384M",
                "-cpu",
                "max",
                "-smp",
                "1",
                "-nographic",
                "-monitor",
                "none",
                "-no-reboot",
                "-kernel",
                str(kernel),
                "-initrd",
                str(merged),
                "-append",
                f"console=ttyS0 quiet panic=-1 rdinit=/init peer={role}",
                "-netdev",
                f"socket,id=w,fd={endpoint.fileno()}",
                "-device",
                f"e1000,netdev=w,mac=52:54:00:00:00:0{index}",
            ]
            if role == "server":
                cmd += [
                    "-device",
                    "pcie-root-port,id=p0,bus=pcie.0,slot=1",
                    "-device",
                    "aim-pcie,bus=p0",
                ]
            log = cleanup.enter_context((out / f"{role}.log").open("w"))
            process = subprocess.Popen(
                cmd, stdout=log, stderr=subprocess.STDOUT, pass_fds=(endpoint.fileno(),)
            )
            procs.append(process)
            cleanup.callback(stop, process)
        for p in procs:
            if p.wait(timeout=60) != 0:
                raise RuntimeError("guest exited; see console logs")
    server = collect(out, "server")
    client = collect(out, "client")
    assert server["served"] == 12 and server["commands"] == 768
    report = json.loads((out / "report.json").read_text())
    assert (
        server["expected_sha256"]
        == client["expected_sha256"]
        == report["expected_sha256"]
    )
    rows = client["rows"]
    assert len(rows) == 12 and all(
        r["ID"] == i and r["Commands"] == 64 for i, r in enumerate(rows)
    )
    report["rows"]["peer_tcp"] = rows
    report["peer_tcp_median_ns"] = {
        k: int(statistics.median(r[k] for r in rows[1:]))
        for k in ("QueueNS", "CopyNS", "DeviceNS", "ServiceNS", "ClientNS")
    }
    report["peer_link"] = {
        "transport": "two Linux guests, isolated QEMU e1000 Ethernet pair, persistent TCP",
        "server": server,
        "initramfs_sha256": INITRD_SHA,
    }
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        "Two Linux guests", server["served"], "requests", report["peer_tcp_median_ns"]
    )


if __name__ == "__main__":
    main()
