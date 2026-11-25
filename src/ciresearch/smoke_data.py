"""Read only authorized smoke records from the pinned benchmark archives."""

import gzip
import hashlib
import json
import re

ARCHIVES = {
    "humaneval": ("HumanEvalPlus.jsonl.gz", "272720b90ac375502c8ed23cd791c2a93dfb22a911641a494da74a426c09f101"),
    "mbpp": ("MbppPlus.jsonl.gz", "af43697e8791c4c149bdfd6b489d8b5412507551ac20e28a439f650b8225db63"),
}
# Commit to the audited P0 metadata without publishing the private membership.
SPLIT_AUDIT = "3fb2beb50987373b434c14896426d872278c3c5b58ec1448aa508fd8ba1f383d"


def smoke_records(directory):
    audit = (directory / "split-audit.json").read_bytes()
    if hashlib.sha256(audit).hexdigest() != SPLIT_AUDIT:
        raise ValueError("unverified smoke authorization audit")
    groups = json.loads(audit)["benchmarks"]
    for dataset, (name, digest) in ARCHIVES.items():
        path = directory / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("unverified benchmark archive")
        order = groups[dataset]["smoke_ids"]
        if len(order) != 4 or len(set(order)) != 4:
            raise ValueError("invalid smoke membership")
        pattern = re.compile(rb'"task_id"\s*:\s*"(' +
                             b"|".join(re.escape(key.encode()) for key in order) + rb')"')
        records = {}
        with gzip.open(path, "rb") as lines:
            for line in lines:
                if not pattern.search(line):
                    continue
                record = json.loads(line)
                if record["task_id"] not in order or record["task_id"] in records:
                    raise ValueError("unexpected task record")
                records[record["task_id"]] = record
        if set(records) != set(order):
            raise ValueError("missing registered smoke record")
        for key in order:
            yield dataset, records[key]
