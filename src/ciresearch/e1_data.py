"""Load the immutable development allowlist and derive typed evidence panels."""
import gzip
import hashlib
import json
import re

from ciresearch.smoke_data import ARCHIVES
from ciresearch.wire import pack, write_frame


def development_records(directory, split_digest):
    split = (directory / "private-split.json").read_bytes()
    if hashlib.sha256(split).hexdigest() != split_digest:
        raise ValueError("development split commitment mismatch")
    manifest = json.loads(split)
    records = []
    for benchmark, (name, digest) in ARCHIVES.items():
        path = directory / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("dataset archive digest mismatch")
        order = manifest[benchmark]["development"]
        if len(order) != 20 or len(set(order)) != 20:
            raise ValueError("invalid registered development membership")
        pattern = re.compile(rb'"task_id"\s*:\s*"(' +
                             b"|".join(re.escape(x.encode()) for x in order) + rb')"')
        matches = {}
        with gzip.open(path, "rb") as source:
            for line in source:
                if pattern.search(line):
                    record = json.loads(line)
                    key = record["task_id"]
                    if key not in order or key in matches:
                        raise ValueError("unexpected development record")
                    matches[key] = record
        if set(matches) != set(order):
            raise ValueError("development archive missing records")
        records.extend((benchmark, matches[key]) for key in order)
    return records


def typed_cases(cases, conversion):
    """Pinned MBPP loader shapes needed by this development population."""
    if conversion == "tuple_wrapped_items":
        return [[tuple(tuple(item) if type(item) is list else item for item in row[0])]
                for row in cases]
    if conversion == "tuple_items_then_index":
        return [[[tuple(item) for item in row[0]], row[1]] for row in cases]
    if conversion == "identity":
        return cases
    raise ValueError("unregistered input conversion")


def unique_panels(base, plus):
    visible = {write_frame(pack(case)) for case in base}
    first = {}
    for index, case in enumerate(plus):
        key = write_frame(pack(case))
        if key not in visible:
            first.setdefault(key, index)
    take = min(8, len(first) - 8)
    if take <= 0:
        return [], []
    rank = sorted(first, key=lambda key: hashlib.sha256(key).digest())
    diagnostic = {first[key] for key in rank[:take]}
    heldout = set(first.values()) - diagnostic
    return [plus[i] for i in sorted(diagnostic)], [plus[i] for i in sorted(heldout)]


def chunk_indices():
    human = iter(range(20))
    mbpp = iter(range(20, 40))
    for chunk in range(8):
        human_count = 3 - chunk % 2
        yield [next(human) for _ in range(human_count)] + [next(mbpp) for _ in range(5-human_count)]
