"""Original, deterministic byte records. Each device ID belongs to exactly one split."""

import hashlib
import random


def documents(contract):
    ids = list(range(256))
    random.Random(contract["split_seed"]).shuffle(ids)
    result = {}
    for split, size in zip(("train", "validation", "test"), contract["id_counts_train_validation_test"]):
        result[split] = [
            f"R{device:03d}={flag}>".encode("ascii") + (b"ok\n" if flag else b"no\n")
            for device in ids[:size] for flag in (0, 1)
        ]
        ids = ids[size:]
    return result


def corpus_hash(records):
    return hashlib.sha256(b"".join(records)).hexdigest()
