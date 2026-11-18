"""Regression controls for the fused projection, observed DMA and cached K/V."""

from collections import deque
from pathlib import Path
import sys
import tempfile
import unittest

LABS = Path(__file__).resolve().parents[1] / "labs"
sys.path[:0] = [str(LABS/"07-fused-qkv"), str(LABS/"06-model-switch")]
from qkv_checks import Trace, check_device, check_numbers, verify


class FusedQKVTests(unittest.TestCase):
    def test_qkv_and_ffn_must_use_their_own_blocks(self):
        symbols = dict(qkv_input=0x1000, activation=0x2000, packed=0x3000, tile_c=0x4000)
        tiles, writes = [], []
        for x, w, cols in [(0x1000, 0x3000, 48), (0x2000, 0x3300, 24)]:
            for row, m in [(0, 4), (4, 1)]:
                for col in range(0, cols, 4):
                    t = 10+200*len(tiles)
                    end = t+170
                    tiles.append((t+7, end-1, (m+4)*16, m*4, 2))
                    values = [x+16*row, w+16*col, 0x4000, m, 4, 16, 1, 2]
                    for i, (off, v) in enumerate(zip((16, 20, 24, 28, 32, 36, 4, 4), values)):
                        writes.append((t+i if i != 7 else end, 0x10010000+off, v))
        args = ("qkv-npu", 24, symbols, [(1, 8000)])
        commands, _ = check_device(*args, deque(tiles), deque(writes))
        self.assertEqual(commands, [36])
        t, reg, _ = writes[1]
        writes[1] = (t, reg, 0x3300)  # correct shape, but the FFN cache instead of QKV
        with self.assertRaisesRegex(ValueError, "descriptor"):
            check_device(*args, deque(tiles), deque(writes))

    def test_kv_cache_must_store_projected_bits(self):
        tensor = [[0]*48 for _ in range(8)]
        ref = dict(F=tensor, K=[[0]*16]*8, Y=[[0]*16]*8, P=[[0]*24]*8,
                   tokens=[2, 5, 6, 10], logits=[[0]*11]*4)
        model = dict(qkv_scales=[1]*49, ffn_scales=[1]*25, fp32=ref)
        words = [("X", 1)]*49+[("W", 1)]*25
        for token in ref["tokens"]:
            words += [("U", 10), ("E", 12), ("J", token)]+[("L", 0)]*11
        for _ in range(8):
            words += [("F", 0)]*48+[("K", 0)]*16+[("Y", 0)]*16+[("P", 0)]*24
        data = "".join(f"{tag}{bits:08x}\n" for tag, bits in words).encode()
        _, numbers = check_numbers(Trace(data, "test"), "qkv-fp32", model, 24)
        self.assertEqual(numbers["checked_kv_floats"], 256)
        # This difference is smaller than the floating-point oracle tolerance.
        with self.assertRaisesRegex(ValueError, "KV differs"):
            check_numbers(Trace(data.replace(b"K00000000", b"K00000001", 1), "test"), "qkv-fp32", model, 24)

    def test_rejected_qkv_scale_requires_a_quiet_window(self):
        raw = b"M00000005\nR00000000\nZ00000000\nV00000004\nG00000000\nA0000000b\nB00000010\nC00000012\n"
        cases = [("qkv-nan-last-channel", None, 4, None)]
        with tempfile.TemporaryDirectory() as tmp:
            counts, mmio, stores = [Path(tmp)/p for p in ("counts", "mmio", "stores")]
            counts.write_text("R 10 0\nZ 25 0\nfinish 50 0\n")
            mmio.write_text("")
            stores.write_text("")
            args = ("qkv-npu", cases, {}, {}, raw, counts, mmio, stores)
            self.assertEqual(verify(*args)[0]["commands"], 0)
            mmio.write_text("10010004 1 15\n")
            with self.assertRaisesRegex(ValueError, "device activity"):
                verify(*args)
            mmio.write_text("")
            counts.write_text("R 10 0\nZ 25 1\nfinish 50 1\n")
            with self.assertRaisesRegex(ValueError, "DMA"):
                verify(*args)
