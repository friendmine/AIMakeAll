"""QEMU q35 + one CXL Type-3. Read and write actual guest physical addresses via qtest."""

import json
import re
import socket
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QEMU = ROOT / "build/linux-qemu"


class Machine:
    def __enter__(self):
        parent, child = socket.socketpair()
        self.socket = parent
        parent.settimeout(12)
        self.monitor = parent.makefile("rwb", buffering=0)
        cmd = [
            str(QEMU / "out/qemu-system-x86_64"),
            "-L",
            str(QEMU / "source/pc-bios"),
            "-machine",
            "q35,cxl=on,cxl-fmw.0.targets.0=cxl.0,cxl-fmw.0.size=256M",
            "-m",
            "128M",
            "-nic",
            "none",
            "-nodefaults",
            "-display",
            "none",
            "-serial",
            "none",
            "-accel",
            "tcg",
            "-chardev",
            f"socket,id=mon,fd={child.fileno()}",
            "-mon",
            "chardev=mon,mode=control",
            "-qtest",
            "stdio",
            "-qtest-log",
            "/dev/null",
            "-device",
            "pxb-cxl,id=cxl.0,bus=pcie.0,bus_nr=52",
            "-device",
            "cxl-rp,id=rp,bus=cxl.0,chassis=0,slot=0",
            "-object",
            "memory-backend-ram,id=ram,size=256M",
            "-device",
            "cxl-type3,bus=rp,volatile-memdev=ram,id=course-memory",
        ]
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            pass_fds=(child.fileno(),),
        )
        child.close()
        try:
            assert "QMP" in json.loads(self.monitor.readline())
            self.qmp("qmp_capabilities")
            for _ in range(100):
                tree = self.qmp("human-monitor-command", {"command-line": "info mtree"})
                match = re.search(
                    r"([\da-f]{16})-[\da-f]{16}[^\n]*: cxl-type3\s*$",
                    tree,
                    re.MULTILINE,
                )
                if match:
                    break
                time.sleep(0.03)
            else:
                raise RuntimeError(
                    "component BAR unavailable:\n"
                    + "\n".join(x for x in tree.splitlines() if "cxl" in x.lower())
                )
            self.qmp("stop")
            self.window = int(
                re.search(
                    r"([\da-f]{16})-[\da-f]{16}[^\n]*: cxl-fixed-memory-region", tree
                ).group(1),
                16,
            )
            component = int(match.group(1), 16)
            self.configure(component)
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def qmp(self, name, params=None):
        self.monitor.write(
            json.dumps({"execute": name, "arguments": params or {}}).encode() + b"\n"
        )
        while True:
            msg = json.loads(self.monitor.readline())
            if "return" in msg:
                return msg["return"]
            if "error" in msg:
                raise RuntimeError(msg["error"])

    def command(self, cmd):
        self.proc.stdin.write(cmd.encode() + b"\n")
        self.proc.stdin.flush()
        reply = self.proc.stdout.readline().decode().strip()
        if reply == "OK" or reply.startswith("OK "):
            return reply[2:].strip()
        raise RuntimeError(reply)

    def read(self, addr, size):
        return bytes.fromhex(self.command(f"read {addr:#x} {size}")[2:])

    def write(self, addr, data):
        self.command(f"write {addr:#x} {len(data)} 0x{data.hex()}")

    def configure(self, component):
        # QEMU 9.2 exposes the cache/mem block at BAR0+0x1000. Follow the HDM header.
        block = component + 0x1000
        hdr = int(self.command(f"readl {block + 12:#x}"), 16)
        assert (hdr & 0xFFFF) == 5, hex(hdr)
        cap = block + (hdr >> 20)

        def wr(off, value):
            self.command(f"writel {cap + off:#x} {value:#x}")

        wr(0x10, self.window & 0xFFFFFFFF)
        wr(0x14, self.window >> 32)
        wr(0x18, 0x10000000)
        wr(0x1C, 0)
        signature = b"AIM-CXL-Type3"
        addr = self.window + 0x80
        wr(0x20, 0)
        self.write(addr, signature)
        self.uncommitted_hidden = self.read(addr, len(signature)) != signature
        assert self.uncommitted_hidden
        wr(0x20, 1 << 9)
        self.control = int(self.command(f"readl {cap + 0x20:#x}"), 16)
        assert self.control & (1 << 10), (hex(component), hex(self.control))
        assert self.read(addr, len(signature)) == bytes(len(signature))
        self.write(addr, signature)
        assert self.read(self.window + 0x80, len(signature)) == signature

    def __exit__(self, *exc):
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        self.monitor.close()
        self.socket.close()
        self.proc.stdin.close()
        self.proc.stdout.close()
