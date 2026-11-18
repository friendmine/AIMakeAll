"""Guard cost recovery and prevent a late weight rewrite from passing as reuse."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "labs/05-weight-prepack"))
from packing_checks import amortization, check_weight_addresses, check_weight_stores


class WeightPrepackTests(unittest.TestCase):
    def test_payback_including_first_request(self):
        report = amortization([100, 100, 100], [112, 91, 91], 21)
        self.assertEqual(report["cumulative_saved_cycles"], [-12, -3, 6])
        self.assertEqual(report["observed_first_nonloss_request"], 3)
        self.assertEqual(report["cold_adjusted_payback_requests"], 3)
        self.assertEqual(report["setup_payback_requests"], 3)
        tie = amortization([100, 100], [107, 93], 14)
        self.assertEqual(tie["observed_first_nonloss_request"], 2)
        no_gain = amortization([100, 100], [105, 101], 4)
        self.assertIsNone(no_gain["setup_payback_requests"])
        self.assertIsNone(no_gain["cold_adjusted_payback_requests"])

    def test_resident_bytes_and_warm_rewrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stores, counters = root / "stores", root / "counters"
            counters.write_text("tile 11 14 0 0 0\ntile 21 24 0 0 0\n")
            steps = [{"tiles": [{"col": 0, "n": 4, "k": 1}]}]
            data = bytes(range(4))
            store = "5 0 15 50462976\n"
            stores.write_text(store)
            self.assertEqual(check_weight_stores(stores, counters, "prepacked", steps, data, 2), [4, 0])
            stores.write_text(store + "16 0 15 50462976\n")
            with self.assertRaisesRegex(ValueError, "after preparation"):
                check_weight_stores(stores, counters, "prepacked", steps, data, 2)
            self.assertEqual(check_weight_stores(stores, counters, "onsite", steps, data, 2), [4, 4])
            stores.write_text("5 0 15 0\n")
            with self.assertRaisesRegex(ValueError, "wrong or repeated"):
                check_weight_stores(stores, counters, "prepacked", steps, data, 2)

    def test_b_addresses_follow_output_columns(self):
        steps = [{"tiles": [{"col": c, "k": 16} for c in (0, 4, 0)]}]
        with tempfile.TemporaryDirectory() as temp:
            bus = Path(temp) / "mmio"
            bus.write_text("10010014 1000\n10010014 1040\n10010014 1000\n")
            self.assertEqual(check_weight_addresses(bus, 0x1000, steps, True), 2)
            with self.assertRaisesRegex(ValueError, "B addresses"):
                check_weight_addresses(bus, 0x1000, steps, False)
