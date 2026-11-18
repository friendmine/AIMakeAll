"""Guard the phase accounting and isolation of the CPU performance baseline."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "labs/04-rv32-performance"))
from performance_checks import PHASES, verify_run


class PerformanceTraceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.counters = Path(tmp.name) / "counters"
        self.mmio = Path(tmp.name) / "mmio"
        self.counters.write_text("S 40\nT 50\nfinish 80\n")
        self.mmio.write_text("")
        tile = dict(row=0, col=0, m=1, n=1, k=1, sums=[-3])
        self.oracle = [dict(tiles=[tile], logits=[0.0], token=0)]
        cpu_phases = [int(p not in ("pack", "driver", "gather")) for p in PHASES]
        words = [("S", 0), ("C", sum(cpu_phases))]
        words += [("F", value) for value in cpu_phases]
        words += [("P", 0xfffffffd), ("L", 0), ("T", 0)]
        self.uart = "".join(f"{k}{v:08x}\n" for k, v in words).encode()

    def check_cpu(self, uart):
        return verify_run(uart, self.counters, self.mmio, "cpu", True, self.oracle)

    def test_exclusive_phases_and_oracle(self):
        steps, _ = self.check_cpu(self.uart)
        self.assertEqual(sum(steps[0]["phase_cycles"].values()), steps[0]["cycles"])
        with self.assertRaisesRegex(ValueError, "phase accounting"):
            self.check_cpu(self.uart.replace(b"F00000001", b"F00000002", 1))
        with self.assertRaisesRegex(ValueError, "accumulator"):
            self.check_cpu(self.uart.replace(b"Pfffffffd", b"P00000000"))
        with self.assertRaisesRegex(ValueError, "logits"):
            self.check_cpu(self.uart.replace(b"L00000000", b"L7fc00000"))

    def test_cpu_must_never_submit_device_work(self):
        self.mmio.write_text("10010004 1\n")
        with self.assertRaisesRegex(ValueError, "device activity"):
            self.check_cpu(self.uart)
        self.mmio.write_text("")
        self.counters.write_text("tile 1 8 2 1 0\nS 40\nT 50\nfinish 80\n")
        with self.assertRaisesRegex(ValueError, "device activity"):
            self.check_cpu(self.uart)
