"""Selection and statistics for the registered nested, fixed candidate pools."""
from collections import Counter, defaultdict
from math import comb

PREFIXES = (1, 2, 4, 8)


def choose(rows):
    counts = [row["v_count"] for row in rows]
    signatures = [row["signature"] for row in rows]
    size = Counter(value for value in signatures if value is not None)
    eligible = [index for index, value in enumerate(signatures) if value is not None]
    return {
        "pass_count": max(range(len(counts)), key=counts.__getitem__) if None not in counts else None,
        "consensus": max(eligible, key=lambda i: size[signatures[i]]) if eligible else None,
    }


def pass_at_k(n, correct, k):
    if not 0 <= correct <= n or not 1 <= k <= n:
        raise ValueError("invalid pass@k dimensions")
    return 1 - (comb(n-correct, k)/comb(n, k) if n-correct >= k else 0)


def metric_row(y, decisions, k):
    p = y[:k]
    if len(p) != k or None in p:
        return {}
    first, oracle = p[0], max(p)
    result = {"first": first, "uniform": sum(p)/k, "oracle": oracle}
    for name, index in decisions.items():
        selected = 0 if index is None else p[index]
        result[name] = selected
        result[f"headroom_{name}"] = oracle - selected
        result[f"delta_{name}"] = selected - first
    if len(y) == 8 and None not in y:
        result["pass_at_k"] = pass_at_k(8, sum(y), k)
    return result


def composition(y):
    if None in y:
        return "incomplete"
    if all(y):
        return "all_correct"
    if any(y):
        return "mixed"
    return "all_incorrect"


def verification(rows):
    counts = Counter()
    for row in rows:
        y, v, h = row["y"], row["v"], row["h"]
        if y is not None and v is not None:
            counts[f"y{int(y)}v{int(v)}"] += 1
        else:
            counts["yv_missing"] += 1
        if v is True:
            counts["visible_pass"] += 1
            if h is not None:
                counts["visible_pass_h_available"] += 1
                counts["visible_pass_h_fail"] += not h
    return dict(counts)


def clusters(rows):
    grouped = defaultdict(list)
    for row in rows:
        if row["signature"] is not None:
            grouped[row["signature"]].append(row["y"])
    mixed = [group for group in grouped.values() if True in group and False in group]
    return {
        "signatures": sum(map(len, grouped.values())),
        "clusters": len(grouped),
        "mixed_clusters": len(mixed),
        "mixed_cluster_sizes": [len(group) for group in mixed],
        "signature_missing": sum(row["signature"] is None for row in rows),
        "label_missing_in_clusters": sum(group.count(None) for group in grouped.values()),
    }
