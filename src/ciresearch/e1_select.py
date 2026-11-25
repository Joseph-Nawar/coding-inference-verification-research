"""Prompt-free selector process. The only accepted inputs are visible summaries."""
import json
import re
import sys

from ciresearch.e1_metrics import PREFIXES, choose


def main():
    rows = json.loads(sys.stdin.read(4096))
    if type(rows) is not list or len(rows) != 8:
        raise ValueError("expected exactly eight visible summaries")
    for row in rows:
        if type(row) is not dict or set(row) != {"v_count", "signature"}:
            raise ValueError("unauthorized evidence field")
        count, signature = row["v_count"], row["signature"]
        if count is not None and (type(count) is not int or count < 0):
            raise ValueError("invalid visible pass count")
        if signature is not None and (type(signature) is not str or
                                      not re.fullmatch(r"[0-9a-f]{64}", signature)):
            raise ValueError("invalid behavioral signature")
    print(json.dumps({str(k): choose(rows[:k]) for k in PREFIXES}))


if __name__ == "__main__":
    main()
