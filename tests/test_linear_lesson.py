"""Cross-layer contract regressions for the public lesson entry point."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RUN = Path(__file__).resolve().parents[1] / "labs" / "01-linear257" / "walkthrough.py"


class LinearLessonTests(unittest.TestCase):
    def test_halving_budget_preserves_all_outputs_and_changes_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            records = []
            for budget in (3212, 1606):
                subprocess.run(
                    [
                        sys.executable,
                        RUN,
                        "--native",
                        "--budget",
                        str(budget),
                        "--report",
                        path,
                    ],
                    check=True,
                    capture_output=True,
                )
                records.append(json.loads(path.read_text()))
        baseline, half = records
        self.assertEqual(baseline["widths"], [256, 1])
        self.assertEqual(half["widths"], [122, 122, 13])
        self.assertEqual(baseline["y_times_128"][0], -70)
        self.assertEqual(baseline["y_times_128"], half["y_times_128"])
        self.assertEqual(half["live_packed_tile_bytes"], 1604)

    def test_earliest_failure(self):
        for args, error in [
            (["--fault", "layout"], "layout B[0,1]"),
            (["--budget", "151"], "budget too small"),
        ]:
            result = subprocess.run(
                [sys.executable, RUN, *args], capture_output=True, text=True
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(error, result.stderr)

    def test_handoff_needs_current_evidence_and_rejects_changed_output(self):
        evidence = RUN.parent / "evidence"
        baseline = evidence / "all-3212.json"
        half = evidence / "all-1606.json"
        cmd = [
            sys.executable,
            RUN.with_name("connections.py"),
            "handoff",
            "--interactive",
            "--reports",
            baseline,
        ]
        run = subprocess.run(
            [*cmd, half],
            input="accept\ncorrect 1\naccept\n",
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertIn("预算与任务不符", run.stdout)
        self.assertIn("已确认 13 项", run.stdout)
        with tempfile.TemporaryDirectory() as tmp:
            changed = Path(tmp) / "changed.json"
            record = json.loads(half.read_text())
            record["partials"]["rv32-mmio"][0][0] += 1
            changed.write_text(json.dumps(record))
            run = subprocess.run(
                [*cmd, changed], input="stop\n", text=True, capture_output=True
            )
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("四条路径", run.stderr)
