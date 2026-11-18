import json
from pathlib import Path

base = Path(__file__).resolve().parents[2] / "build/language"
runs = [json.loads((base / f"metrics-{w}.json").read_text()) for w in (48, 40)]
for field in ("topics", "seed", "train_bytes", "steps", "corpus_sha256"):
    assert runs[0][field] == runs[1][field], field
choice = min(runs, key=lambda r: r["metrics"]["validation"]["ppl"])
result = dict(
    train_bytes_per_candidate=choice["train_bytes"],
    validation_choice=choice["width"],
    candidates=[
        {k: r[k] for k in ("width", "parameters", "metrics", "sample")} for r in runs
    ],
)
(base / "comparison.json").write_text(json.dumps(result, indent=2) + "\n")
print(result)
