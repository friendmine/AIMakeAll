"""Catch false passes when a projection or its device transaction changes."""

import sys
import tempfile
import unittest
from pathlib import Path

LAB = Path(__file__).resolve().parents[1] / "labs/03-rv32-generation"
sys.path.insert(0, str(LAB))
from trace_checks import check_counters, check_mmio, check_uart  # noqa: E402


class GenerationTraceTests(unittest.TestCase):
    def setUp(self):
        self.tile = dict(row=0, col=0, m=1, n=1, k=1, a_hash=17, b_hash=18, sums=[-6])
        self.steps = [dict(tiles=[self.tile], logits=[0.0] * 11, token=0)]
        words = (
            [
                ("A", 1),
                ("B", 2),
                ("C", 4),
                ("S", 0),
                ("I", 0),
                ("H", 0x10101),
                ("X", 17),
                ("W", 18),
                ("P", 0xFFFFFFFA),
            ]
            + [("L", 0)] * 11
            + [("T", 0)]
        )
        self.uart = "".join(f"{tag}{v:08x}\n" for tag, v in words).encode()

    def test_first_wrong_integer_or_nonfinite_logit(self):
        addresses, result = check_uart(self.uart, "test", self.steps)
        self.assertEqual((addresses["C"], result[0]["integers"]), (4, 1))
        with self.assertRaisesRegex(ValueError, r"step 0 tile \(0,0\) output\[0,0\]"):
            check_uart(
                self.uart.replace(b"Pfffffffa", b"Pfffffffb"), "test", self.steps
            )
        with self.assertRaisesRegex(ValueError, "logit"):
            check_uart(
                self.uart.replace(b"L00000000", b"L7fc00000", 1), "test", self.steps
            )

    def test_dma_accounting_and_completion_order(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / "counters"
            good = "S 3\ntile 10 19 2 1 1\nT 27\nfinish 31\n"
            p.write_text(good)
            self.assertEqual(check_counters(p, self.steps)[0]["elapsed_cycles"], 24)
            for bad in [good.replace("19 2", "19 1"), good.replace("T 27", "T 18")]:
                p.write_text(bad)
                with self.assertRaises(ValueError):
                    check_counters(p, self.steps)

    def test_mmio_wrong_on_both_backends(self):
        with tempfile.TemporaryDirectory() as folder:
            qemu, rtl = (Path(folder) / name for name in ("qemu", "rtl"))
            writes = []
            for descriptor in [
                (1, 2, 4, 0, 4, 16),
                (4, 2, 4, 1, 4, 16),
                (1, 2, 4, 1, 1, 1),
            ]:
                writes += [
                    (0x10010010 + 4 * i, value) for i, value in enumerate(descriptor)
                ]
                writes += [(0x10010004, 1), (0x10010004, 2)]
            for corrupt in [False, True]:
                if corrupt:
                    writes[-1] = (0x10010004, 1)
                qemu.write_text(
                    "".join(
                        f"memory_region_ops_write cpu 0 mr 0x1 addr 0x{a:x} value 0x{v:x} size 4 name 'aimakeall-npu'\n"
                        for a, v in writes
                    )
                )
                rtl.write_text("".join(f"{a:x} {v:x}\n" for a, v in writes))
                if corrupt:
                    with self.assertRaisesRegex(ValueError, "command 2"):
                        check_mmio(qemu, rtl, dict(A=1, B=2, C=4), self.steps)
                else:
                    self.assertEqual(
                        check_mmio(qemu, rtl, dict(A=1, B=2, C=4), self.steps), 24
                    )
