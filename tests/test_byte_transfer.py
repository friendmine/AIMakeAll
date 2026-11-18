"""Protect the paired holdout, prompt layout and constrained decision without PyTorch."""

import json
from pathlib import Path
import struct
import sys
import unittest

LABS = Path(__file__).resolve().parents[1] / "labs"
sys.path[:0] = [str(LABS/"08-byte-transfer"), str(LABS/"06-model-switch")]
from corpus import documents
from decision import QUALITY_PATH, rank_candidates
from packages import encode_requests


class ByteTransferTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads((LABS/"08-byte-transfer"/"contract.json").read_text())

    def test_device_ids_and_flags_stay_together(self):
        splits = documents(self.spec)
        self.assertEqual([len(s) for s in splits.values()], [384, 64, 64])
        all_ids = set()
        for rows in splits.values():
            for negative, positive in zip(rows[::2], rows[1::2]):
                tag = negative[:4]
                self.assertNotIn(tag, all_ids)
                self.assertEqual(negative, tag + b"=0>no\n")
                self.assertEqual(positive, tag + b"=1>ok\n")
                all_ids.add(tag)
        self.assertEqual(all_ids, {f"R{i:03}".encode() for i in range(256)})

    def test_request_table_after_different_prompt_lengths(self):
        for prompt in (bytes(range(5)), b"R123=1>", bytes(range(8))):
            with self.subTest(prompt=prompt):
                blob = encode_requests(prompt, [("b",), ("a",), ("b",)], {"a": b"A", "b": b"bbb"})
                self.assertEqual(blob[:len(prompt)+1], prompt + bytes([3]))
                index = (len(prompt)+4)//4*4
                for i, expected in enumerate((b"bbb", b"A", b"bbb")):
                    offset, size = struct.unpack_from("<II", blob, index + 8*i)
                    self.assertEqual(offset % 4, 0)
                    self.assertGreaterEqual(offset, index + 24)
                    self.assertEqual(blob[offset:offset+size], expected)

    def test_fastest_must_pass_quality_and_fit_all_budgets(self):
        gates = self.spec["quality"]
        budget = self.spec["budget"]
        def candidate(exact):
            row = dict(exact=exact, conditional_ppl=1.01)
            return dict(fp32=row, ffn_int8=row, dual_int8=row, bigram=dict(conditional_ppl=1.3))
        quality = {"24": candidate(32), "32": candidate(64)}
        models = {"24": dict(package_bytes=42284), "32": dict(package_bytes=42988)}
        ram = dict(linked_writable_bytes=20000, array_local_bytes=256)
        samples = [dict(modes={m: dict(valid=[dict(width=32, request_cycles=500-i),
                                                 dict(width=24, request_cycles=100-i)])
                               for i, m in enumerate(QUALITY_PATH)})]
        rows = rank_candidates(samples, quality, models, ram, gates, budget)
        self.assertEqual((rows[0]["width"], rows[0]["mode"], rows[0]["eligible"]), (32, "qkv-npu", True))
        for field, limit in [("one_model_package_bytes", 42496), ("linked_writable_bytes_including_stack", 19999),
                             ("array_local_bytes", 255)]:
            with self.subTest(field=field):
                reduced = dict(budget, **{field: limit})
                self.assertFalse(any(r["eligible"] for r in rank_candidates(samples, quality, models, ram, gates, reduced)))
