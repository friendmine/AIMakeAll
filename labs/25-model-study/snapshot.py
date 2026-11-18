"""Recreate the MIT course-prose corpus from the immutable Git revision (optional)."""

import gzip
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def snapshot():
    revision = json.loads((HERE / "contract.json").read_text())["source_commit"]

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT).decode()

    names = sorted(git("ls-tree", "--name-only", f"{revision}:docs").splitlines())
    seen, docs = set(), {}
    for name in (n for n in names if n.endswith(".md")):
        raw = git("show", f"{revision}:docs/{name}")
        raw = re.sub(r"(?ms)^`{3}[^\n]*\n.*?^`{3}[^\n]*", "", raw)
        lines = []
        for line in raw.splitlines():
            line = line.strip()
            if (
                line.startswith(("#", "|", ">", "!", "["))
                or len(re.findall("[\u3400-\u9fff]", line)) < 12
            ):
                continue
            line = (
                re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)
                .replace("`", "")
                .replace("**", "")
            )
            if line not in seen:
                seen.add(line)
                lines.append(line)
        if lines:
            docs[Path(name).stem] = "\n".join(lines)
    return json.dumps(docs, sort_keys=True, ensure_ascii=False).encode()


if __name__ == "__main__":
    path = HERE / "course-prose.json.gz"
    raw = snapshot()
    if path.exists():
        assert gzip.decompress(path.read_bytes()) == raw
    else:
        path.write_bytes(gzip.compress(raw, mtime=0))
    print("source documents", len(json.loads(raw)))
