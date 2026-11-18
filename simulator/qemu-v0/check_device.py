"""Deterministic MMIO and reset regression using QEMU's qtest virtual clock."""

import json
import socket
import subprocess
import sys

BASE = 0x10010000
RAM = 0x80000000


def check(binary):
    parent, child = socket.socketpair()
    parent.settimeout(10)
    with (
        parent,
        child,
        subprocess.Popen(
            [
                binary,
                "-M",
                "virt",
                "-accel",
                "qtest",
                "-m",
                "32M",
                "-bios",
                "none",
                "-display",
                "none",
                "-serial",
                "none",
                "-monitor",
                "none",
                "-nic",
                "none",
                "-qtest",
                "stdio",
                "-qtest-log",
                "/dev/null",
                "-chardev",
                f"socket,id=ctrl,fd={child.fileno()}",
                "-mon",
                "ctrl,mode=control",
            ],
            pass_fds=(child.fileno(),),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        ) as proc,
    ):
        try:

            def cmd(line):
                proc.stdin.write(line + "\n")
                proc.stdin.flush()
                ans = proc.stdout.readline().split()
                if not ans or ans[0] != "OK":
                    raise RuntimeError(f"{line}: {ans}")
                return int(ans[1], 0) if len(ans) > 1 else None

            def write(off, val):
                cmd(f"writel {BASE + off:#x} {val:#x}")

            def read(off):
                return cmd(f"readl {BASE + off:#x}")

            def output():
                return cmd(f"readl {RAM + 8:#x}")

            with parent.makefile("rwb", buffering=0) as qmp:
                assert "QMP" in json.loads(qmp.readline())

                def control(name):
                    qmp.write((json.dumps({"execute": name}) + "\n").encode())
                    while True:
                        reply = json.loads(qmp.readline())
                        if "return" in reply:
                            return
                        if "error" in reply:
                            raise RuntimeError(reply)

                control("qmp_capabilities")
                assert read(0) == 1
                cmd(f"writeb {RAM:#x} 0xfe")
                cmd(f"writeb {RAM + 4:#x} 3")
                cmd(f"writel {RAM + 8:#x} 0x12345678")
                for reg, val in enumerate([RAM, RAM + 4, RAM + 8, 1, 1, 1]):
                    write(0x10 + 4 * reg, val)
                # Invalid widths, unaligned writes and writes to read-only registers.
                cmd(f"writeb {BASE + 0x24:#x} 0xff")
                cmd(f"writew {BASE + 0x1D:#x} 0xffff")
                write(8, 4)
                assert read(0x24) == read(0x1C) == 1 and read(8) == 0
                for offset, val, code in [
                    (4, 3, 1),
                    (0x24, 257, 2),
                    (0x18, RAM + 9, 3),
                    (0x10, 0xFFFFFFFF, 3),
                    (0x18, RAM, 4),
                ]:
                    original = read(offset) if offset != 4 else 0
                    write(offset, val)
                    if offset != 4:
                        write(4, 1)
                    assert (read(8), read(12), output()) == (4, code, 0x12345678)
                    write(4, 2)
                    if offset != 4:
                        write(offset, original)
                write(4, 1)
                assert read(8) == 1
                write(4, 2)
                write(0x24, 0)
                assert read(8) == 1 and read(0x24) == 1
                cmd("clock_step 1000")
                assert read(8) == 2 and output() == 0xFFFFFFFA
                write(4, 1)
                assert read(8) == 2
                write(4, 2)
                write(4, 1)
                assert read(8) == 1
                control("system_reset")
                cmd(f"writel {RAM + 8:#x} 0xdeadbeef")
                cmd("clock_step 10000")
                assert read(8) == read(12) == 0 and output() == 0xDEADBEEF
                assert all(read(off) == 0 for off in range(0x10, 0x28, 4))
                print(
                    "PASS qtest: errors 1-4, unchanged output, BUSY/DONE/CLEAR, reset cancels"
                )
        finally:
            proc.terminate()


if __name__ == "__main__":
    if not __debug__:
        sys.exit("Run without -O so all device checks are active")
    check(sys.argv[1])
