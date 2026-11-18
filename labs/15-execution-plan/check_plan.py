"""Make sure the loader rejects malformed plans before it dispatches a projection."""

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from compiler import Executable, plan_dir


def check():
    source = plan_dir(48)
    plan = json.loads((source / "plan.json").read_text())
    raw = (source / "model.bin").read_bytes()
    faults = {}
    for case in (
        "digest",
        "truncated",
        "missing layer",
        "wrong shape",
        "overlap",
        "bad offset",
        "missing norm",
    ):
        manifest = deepcopy(plan)
        payload = raw
        if case == "digest":
            payload = bytes([raw[0] ^ 1]) + raw[1:]
        elif case == "truncated":
            payload = raw[:-1]
        elif case == "missing layer":
            manifest["ops"].pop()
        elif case == "wrong shape":
            manifest["ops"][-1]["n"] = 252
        elif case == "overlap":
            manifest["floats"]["norm.bias"] = manifest["floats"]["norm.weight"]
        elif case == "bad offset":
            manifest["ops"][-1]["w"] = len(raw)
        else:
            del manifest["floats"]["norm.weight"]
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "plan.json").write_text(json.dumps(manifest))
            (folder / "model.bin").write_bytes(payload)
            try:
                Executable(folder)
            except ValueError as exc:
                faults[case] = str(exc)
            else:
                raise AssertionError(case)
    (source / "rejections.json").write_text(json.dumps(faults, indent=2) + "\n")


if __name__ == "__main__":
    check()
