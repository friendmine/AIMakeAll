"""Recreate the installed CPython 3.11.7 pydoc snapshot and compare it to the course copy."""

import gzip
import json
from pathlib import Path
from pydoc_data.topics import topics
import re
import sys

if sys.version_info[:3] != (3, 11, 7):
    raise SystemExit("Regenerate the source snapshot with CPython 3.11.7.")
seen = set()
docs = {}
for name, topic in sorted(topics.items()):
    paragraphs = []
    for paragraph in re.split(r"\n\s*\n", topic):
        text = " ".join(paragraph.split())
        if len(text) >= 45 and re.search(r"[a-zA-Z]{3}", text) and text not in seen:
            seen.add(text)
            paragraphs.append(text)
    if paragraphs:
        docs[name] = "\n".join(paragraphs) + "\n"
saved = json.loads(
    gzip.decompress(Path(__file__).with_name("python-help.json.gz").read_bytes())
)
assert docs == saved, [key for key in docs if docs[key] != saved.get(key)]
print("Verified", len(docs), "source topics")
