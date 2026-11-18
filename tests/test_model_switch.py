"""Detect false passes for rejected requests using bus observations independent of guest status."""

import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

LAB = Path(__file__).resolve().parents[1] / "labs/06-model-switch"
sys.path.insert(0, str(LAB))
from check_switch import check_cache, verify
from packages import HEADER, make_inputs, package


class ModelSwitchTests(unittest.TestCase):
    def test_request_bytes_and_negative_controls(self):
        # Placeholder payloads exercise the transport independently of PyTorch.
        a = package(32, bytes(256))
        b = package(24, bytes(192))
        data, cases = make_inputs([8, 2, 5, 6, 9], a, b)
        spans = [struct.unpack_from("<II", data, 8+8*i) for i in range(len(cases))]
        blobs = [data[start:start+length] for start, length in spans]
        self.assertEqual(blobs[:4], [a, a, b, a])
        self.assertNotEqual(spans[0], spans[1])
        self.assertEqual(spans[0], spans[3])
        self.assertEqual(bytes(blobs[4][:-1]), a[:-1])
        self.assertNotEqual(zlib.crc32(blobs[4][HEADER.size:]), HEADER.unpack_from(blobs[4])[-1])
        self.assertEqual(blobs[5], b[:-1])
        self.assertEqual(HEADER.unpack_from(blobs[6])[2], 28)
        self.assertEqual(struct.unpack_from("<I", blobs[7], HEADER.size+4*24)[0], 0x7fc00000)
        self.assertEqual(zlib.crc32(blobs[7][HEADER.size:]), HEADER.unpack_from(blobs[7])[-1])
        self.assertEqual(blobs[8], a)

    def test_rejection_requires_quiet_device_and_cache(self):
        uart = b"R00000000\nV00000003\nG00000000\nZ00000000\n"
        cases = [("flipped", None, 3, None)]
        with tempfile.TemporaryDirectory() as temp:
            counts, mmio, stores = [Path(temp) / n for n in ("counts", "mmio", "stores")]
            counts.write_text("R 10 0\nZ 20 0\nfinish 30 0\n")
            mmio.write_text("")
            stores.write_text("")
            verified = verify(uart, counts, mmio, stores, cases, {}, {})
            self.assertEqual(verified[0]["commands"], 0)
            for name, writes, cache, beats, message in [
                ("start", "10010004 1 17\n", "", 0, "NPU writes"),
                ("descriptor", "10010014 0 12\n", "", 0, "NPU writes"),
                ("DMA", "", "", 1, "DMA activity"),
                ("cache", "", "13 0 1 0\n", 0, "cache writes"),
                ("before request", "10010004 1 7\n", "", 0, "outside request"),
                ("after request", "10010004 1 21\n", "", 0, "after final request"),
            ]:
                with self.subTest(name=name):
                    counts.write_text(f"R 10 0\nZ 20 {beats}\nfinish 30 {beats}\n")
                    mmio.write_text(writes)
                    stores.write_text(cache)
                    with self.assertRaisesRegex(ValueError, message):
                        verify(uart, counts, mmio, stores, cases, {}, {})

    def test_cache_extent_content_and_deadline(self):
        wanted = bytes([17, 34, 51, 68])
        good = (12, 0, 15, 0x44332211)
        self.assertEqual(check_cache([good], wanted, 15), 4)
        for stores in [[good, good], [(15, *good[1:])], [(12, 0, 7, good[3])],
                       [(12, 0, 15, good[3]+1)]]:
            with self.assertRaises(ValueError):
                check_cache(stores, wanted, 15)
