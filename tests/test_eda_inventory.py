import json
from pathlib import Path
import tempfile
import unittest

from tools.eda.inspect_environment import locate, probe, read_record


class EnvironmentInventoryTests(unittest.TestCase):
    def test_missing_lab_is_reported_without_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            lab = Path(directory) / "missing"
            result = probe("test", "test", "{lab}/bin/tool", ["--version"], lab)
            self.assertEqual(result["status"], "not_found_in_checked_locations")
            self.assertFalse(lab.exists())

    def test_ambiguous_executables_are_not_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("tool-a", "tool-b"):
                path = root / name
                path.write_text("not an executable program")
                path.chmod(0o700)
            result = probe("test", "test", "{lab}/tool-*", ["--version"], root)
            self.assertEqual(result["status"], "ambiguous_requires_selection")
            self.assertEqual(len(result["candidates"]), 2)

    def test_report_preserves_incomplete_status_and_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = json.dumps({"status": "INCOMPLETE", "characterization_ready": False,
                              "gates": [{"name": "PVT", "status": "PENDING", "detail": "large"}]})
            (root / "report.json").write_text(raw)
            item = read_record(root, "report.json", summary=True)
            self.assertEqual(item["summary"]["status"], "INCOMPLETE")
            self.assertFalse(item["summary"]["characterization_ready"])
            self.assertEqual((root / "report.json").read_text(), raw)
            self.assertEqual(len(item["sha256"]), 64)

    def test_paths_with_spaces_and_malformed_report(self):
        with tempfile.TemporaryDirectory(prefix="eda test ") as directory:
            root = Path(directory)
            path = root / "tool"
            path.write_text("placeholder")
            path.chmod(0o700)
            self.assertEqual(locate("{lab}/tool", root), [str(path)])
            (root / "report.json").write_text("in progress {")
            self.assertEqual(read_record(root, "report.json", True)["status"],
                             "unreadable_json_snapshot")


if __name__ == "__main__":
    unittest.main()
