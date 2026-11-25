"""Compute aggregate E1 results only after a terminal freeze or stop record."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import random
import statistics

from ciresearch.e1_data import chunk_indices
from ciresearch.e1_metrics import PREFIXES, clusters, composition, metric_row, verification

REPLICATES = 2000
BOOTSTRAP_SEED = 11252026
BENCHMARKS = ("humaneval", "mbpp")


def jsonl(path):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()]


def quantile(values, probability):
    i = (len(values) - 1) * probability
    low = int(i)
    high = min(len(values) - 1, low + 1)
    return values[low] + (values[high] - values[low]) * (i - low)


def interval(values):
    values = sorted(value for value in values if value is not None)
    return {
        "valid_replicates": len(values),
        "ci95": [quantile(values, 0.025), quantile(values, 0.975)] if values else None,
    }


def ratio(a, b):
    return a / b if b else None


def bootstrap_groups():
    rng = random.Random(BOOTSTRAP_SEED)
    return [
        (rng.choices(range(20), k=20), rng.choices(range(20, 40), k=20))
        for _ in range(REPLICATES)
    ]


def verification_rates(counts):
    return {
        "false_accept": ratio(counts["y0v1"], counts["y0v0"] + counts["y0v1"]),
        "false_reject": ratio(counts["y1v0"], counts["y1v0"] + counts["y1v1"]),
        "incorrect_given_visible_pass": ratio(counts["y0v1"], counts["y0v1"] + counts["y1v1"]),
        "heldout_fail_given_visible_pass": ratio(
            counts["visible_pass_h_fail"], counts["visible_pass_h_available"]),
    }


def population_scopes(draws):
    return {
        "overall": (list(range(40)), [a + b for a, b in draws]),
        **{name: (list(range(i * 20, (i + 1) * 20)), [draw[i] for draw in draws])
           for i, name in enumerate(BENCHMARKS)},
    }


def score_metrics(rows, suites, indices, replicates):
    result = {}
    for k in PREFIXES:
        name = str(k)
        task_metrics = {i: metric_row([r["y"] for r in rows[i]], suites[i].get(name, {}), k)
                        for i in indices}
        merged = {}
        metric_names = ("first", "uniform", "oracle", "pass_count", "consensus", "pass_at_k",
                        "headroom_pass_count", "headroom_consensus", "delta_pass_count", "delta_consensus")
        for metric in metric_names:
            vals = {i: r[metric] for i, r in task_metrics.items() if metric in r}
            simulations = [statistics.mean(present) if
                           (present := [vals[i] for i in draw if i in vals]) else None
                           for draw in replicates]
            total = sum(vals.values())
            missing = len(indices) - len(vals)
            bounds = (((total - missing) / len(indices), (total + missing) / len(indices))
                      if metric.startswith("delta_") else
                      (total / len(indices), (total + missing) / len(indices)))
            merged[metric] = {
                "point": ratio(total, len(vals)),
                "denominator_tasks": len(vals),
                "missing_tasks": missing,
                "sum_task_values": total,
                "population_bounds": bounds,
                **interval(simulations),
            }
        for selector in ("pass_count", "consensus"):
            pairs = Counter()
            for i, values in task_metrics.items():
                if selector in values:
                    pairs[f"first{int(values['first'])}_selected{int(values[selector])}"] += 1
                    pairs[f"oracle{int(values['oracle'])}_selected{int(values[selector])}"] += 1
            merged[f"{selector}_paired_counts"] = dict(pairs)
        result[name] = merged
    return result


def evidence_summary(rows, indices, replicates):
    task_checks = {i: Counter(verification(rows[i])) for i in indices}
    counts = sum(task_checks.values(), Counter())
    simulated_checks = [verification_rates(sum((task_checks[i] for i in draw), Counter()))
                        for draw in replicates]
    rates = {name: {"point": value, **interval([d[name] for d in simulated_checks])}
             for name, value in verification_rates(counts).items()}
    pools = {}
    for k in (4, 8):
        parts = [clusters(rows[i][:k]) for i in indices]
        pools[str(k)] = {
            "tasks": len(indices),
            "candidate_pool": dict(Counter(composition([r["y"] for r in rows[i][:k]]) for i in indices)),
            "tasks_with_visible_signatures": sum(p["signatures"] > 0 for p in parts),
            "tasks_with_mixed_visible_clusters": sum(p["mixed_clusters"] > 0 for p in parts),
            "visible_clusters": sum(p["clusters"] for p in parts),
            "mixed_visible_clusters": sum(p["mixed_clusters"] for p in parts),
            "mixed_cluster_size_histogram": dict(Counter(n for p in parts for n in p["mixed_cluster_sizes"])),
            "candidates_missing_signature": sum(p["signature_missing"] for p in parts),
            "signed_candidates_missing_label": sum(p["label_missing_in_clusters"] for p in parts),
        }
    return {"composition_and_behavior": pools, "verification_counts": dict(counts), "verification_rates": rates}


def failure_counts(label, v, full):
    result = Counter()
    if label["y"] is None:
        result["official_y_unavailable"] += 1
    reasons = set()
    for name, panel in (("base", v), ("plus", full)):
        outcomes = panel.get("execution", [])
        details = panel.get("details", [])
        initial = panel.get("initialization")
        reason = panel.get("reason")
        result[f"cases_run_{name}"] += len(outcomes)
        for status, correct in zip(outcomes, details):
            if status in ("exception", "timeout"):
                result[f"case_{status}_{name}"] += 1
                reasons.add(f"candidate_{status}")
            if status == "ok" and not correct:
                result[f"case_incorrect_output_{name}"] += 1
                reasons.add("candidate_incorrect_output")
        if initial in ("invalid_program", "exception"):
            reasons.add(f"initialization_{initial}")
        if panel["pass"] is None:
            reasons.add("evaluation_unavailable")
            if reason:
                reasons.add(f"unavailable_{reason.split(':')[-1].strip()}")
    for reason in reasons:
        result[reason] += 1
    if v["pass"] is True and label["h"] is False:
        result["visible_pass_heldout_fail"] += 1
    return result


def analyze(run):
    ledger = jsonl(run / "ledger.jsonl")
    if not ledger or ledger[-1]["event"] not in ("global_freeze", "stopped"):
        raise ValueError("analysis requires a terminal freeze or stopped-run record")
    final = ledger[-1]
    checkpoints = [row for row in ledger if row["event"] == "chunk_checkpoint"]
    chunks = list(chunk_indices())
    usable = {i for row in checkpoints for i in chunks[row["chunk"]]}
    calls = [row for row in ledger if row["event"] == "call_complete"]
    started = [row for row in ledger if row["event"] == "call_started"]
    vis = {(r["task"], r["sample"]): r["evidence"] for r in jsonl(run/"visible.jsonl") if r["task"] in usable}
    signed = {(r["task"], r["sample"]): r for r in jsonl(run/"sealed-labels.jsonl") if r["task"] in usable}
    decisions = {r["task"]: r["decisions"] for r in jsonl(run/"decisions.jsonl") if r["task"] in usable}
    failures = sum((failure_counts(r, vis[key]["base"], r["outcomes"]["plus"]) for key, r in signed.items()), Counter())
    labels = {"official_compatible": {}, "integrity_qualified": {}}
    schedules = {}
    for i in range(40):
        schedules[i] = decisions.get(i, {})
        for endpoint in labels:
            rows = []
            for j in range(8):
                key = i, j
                if key not in signed:
                    rows.append(dict(y=None, v=None, h=None, signature=None))
                    continue
                score, visible = signed[key], vis[key]["base"]
                y = score["y"] if endpoint == "official_compatible" else score["qualified_y"]
                h = score["h"] if endpoint == "official_compatible" or y is not None else None
                rows.append(dict(y=y, v=visible["pass"], h=h, signature=visible["signature"]))
            labels[endpoint][i] = rows
    scopes = population_scopes(bootstrap_groups())
    breakdown = {}
    for endpoint, rows in labels.items():
        breakdown[endpoint] = {
            scope: {"metrics": score_metrics(rows, schedules, inds, resamples),
                    **evidence_summary(rows, inds, resamples)}
            for scope, (inds, resamples) in scopes.items()
        }
    raw_files = {p.stem: p for p in run.glob("chunk-*/*.json") if len(p.stem) == 64}
    generations = [json.loads(raw_files[r["id"]].read_text()) for r in calls]
    code_groups = defaultdict(Counter)
    for r in calls:
        code_groups[r["task"]][r["code_hash"]] += 1
    return {
        "stage_status": final["event"],
        "stop_reason": final.get("reason"),
        "complete_checkpoint_tasks": len(usable),
        "generated_calls": len(calls),
        "started_calls": len(started),
        "output_tokens": sum(r["tokens"] for r in calls),
        "input_tokens": sum(r["input_tokens"] for r in calls),
        "wall_seconds": final["elapsed_seconds"],
        "first_chunk_forecast_seconds": checkpoints[0]["forecast_seconds"] if checkpoints else None,
        "reference_precompute_seconds": checkpoints[0]["reference_audit_seconds"] if checkpoints else None,
        "memory_and_disk_samples": [row["environment"] for row in ledger
                                    if row["event"] in ("start", "chunk_start", "chunk_checkpoint")],
        "generation_outcomes": dict(Counter(r["parse"] for r in calls)),
        "within_task_duplicate_extractions": sum(n-1 for group in code_groups.values() for n in group.values()),
        "med_prefill_tps": statistics.median(x["prefill_tokens_per_second"] for x in generations) if generations else None,
        "med_decode_tps": statistics.median(x["decode_tokens_per_second"] for x in generations) if generations else None,
        "peak_mlx_bytes": max((x["peak_mlx_bytes"] for x in generations), default=None),
        "peak_rss_bytes": max((x["host_peak_rss_bytes"] for x in generations), default=None),
        "generation_seconds": sum(x["wall_seconds"] for x in generations),
        "failure_counts": dict(failures),
        "analyses": breakdown,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    result = analyze(args.run)
    # The input is private. Public publication uses reviewed aggregates only.
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
