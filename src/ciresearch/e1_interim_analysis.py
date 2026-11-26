"""Registered task-level analyses for a validated incomplete E1 checkpoint view."""
from collections import Counter, defaultdict
import random
import statistics

from ciresearch.e1_analysis import failure_counts, interval, quantile, ratio
from ciresearch.e1_interim import InterimView
from ciresearch.e1_metrics import PREFIXES, clusters, composition, metric_row, verification

REPLICATES = 2000
BOOTSTRAP_SEED = 11252026
REGISTERED_TASKS = 40
BENCHMARK_TASKS = 20


def _strata(task_ids):
    tasks = tuple(task_ids)
    return {
        "overall": tasks,
        "humaneval": tuple(task for task in tasks if task < 20),
        "mbpp": tuple(task for task in tasks if task >= 20),
    }


def _bootstrap(task_ids, *, replicates=REPLICATES, seed=BOOTSTRAP_SEED):
    rng = random.Random(seed)
    output = {name: [] for name in ("overall", "humaneval", "mbpp")}
    for _ in range(replicates):
        sampled = {
            name: tuple(rng.choices(group, k=BENCHMARK_TASKS))
            for name, group in (("humaneval", tuple(range(20))),
                                ("mbpp", tuple(range(20, 40))))
        }
        output["humaneval"].append(sampled["humaneval"])
        output["mbpp"].append(sampled["mbpp"])
        output["overall"].append(sampled["humaneval"] + sampled["mbpp"])
    return output


def _population_bounds(values, registered_n, metric):
    observed = len(values)
    missing = registered_n - observed
    total = sum(values.values())
    if metric.startswith("delta_"):
        return [(total - missing) / registered_n, (total + missing) / registered_n]
    return [total / registered_n, (total + missing) / registered_n]


def _score_metrics(rows, schedules, task_ids, draws, registered_n):
    result = {}
    for k in PREFIXES:
        name = str(k)
        by_task = {
            task: metric_row([record["y"] for record in rows[task]], schedules[task].get(name, {}), k)
            for task in task_ids
        }
        metric_names = (
            "first", "uniform", "oracle", "pass_count", "consensus", "pass_at_k",
            "headroom_pass_count", "headroom_consensus", "delta_pass_count", "delta_consensus",
        )
        merged = {}
        for metric in metric_names:
            values = {task: record[metric] for task, record in by_task.items() if metric in record}
            estimates = []
            for draw in draws:
                available = [values[task] for task in draw if task in values]
                estimates.append(statistics.mean(available) if available else None)
            total = sum(values.values())
            missing = len(task_ids) - len(values)
            if metric.startswith("delta_"):
                checkpoint_bounds = [(total - missing) / len(task_ids), (total + missing) / len(task_ids)]
            else:
                checkpoint_bounds = [total / len(task_ids), (total + missing) / len(task_ids)]
            merged[metric] = {
                "point": ratio(total, len(values)),
                "denominator_tasks": len(values),
                "missing_tasks_in_checkpoint_population": missing,
                "sum_task_values": total,
                "checkpoint_population_bounds": checkpoint_bounds,
                "registered_population_bounds": _population_bounds(values, registered_n, metric),
                **interval(estimates),
            }
        for selector in ("pass_count", "consensus"):
            pairs = Counter()
            for record in by_task.values():
                if selector in record:
                    pairs[f"first{int(record['first'])}_selected{int(record[selector])}"] += 1
                    pairs[f"oracle{int(record['oracle'])}_selected{int(record[selector])}"] += 1
            merged[f"{selector}_paired_task_counts"] = dict(pairs)
        result[name] = merged
    return result


def _verification_rates(counts):
    return {
        "false_accept": ratio(counts["y0v1"], counts["y0v0"] + counts["y0v1"]),
        "false_reject": ratio(counts["y1v0"], counts["y1v0"] + counts["y1v1"]),
        "incorrect_given_visible_pass": ratio(counts["y0v1"], counts["y0v1"] + counts["y1v1"]),
        "heldout_fail_given_visible_pass": ratio(
            counts["visible_pass_h_fail"], counts["visible_pass_h_available"]),
    }


def _evidence_summary(rows, task_ids, draws):
    task_counts = {task: Counter(verification(rows[task])) for task in task_ids}
    counts = sum(task_counts.values(), Counter())
    boot_rates = []
    for draw in draws:
        sample_counts = sum((task_counts[task] for task in draw if task in task_counts), Counter())
        boot_rates.append(_verification_rates(sample_counts))
    rates = {
        name: {"point": value, **interval([sample[name] for sample in boot_rates])}
        for name, value in _verification_rates(counts).items()
    }
    pool_summary = {}
    for k in (1, 2, 4, 8):
        compositions = Counter(composition([row["y"] for row in rows[task][:k]]) for task in task_ids)
        parts = [clusters(rows[task][:k]) for task in task_ids]
        pool_summary[str(k)] = {
            "tasks": len(task_ids),
            "complete_label_tasks": sum(compositions[name] for name in
                                         ("all_correct", "mixed", "all_incorrect")),
            "candidate_pool_composition": dict(compositions),
            "tasks_with_any_visible_signatures": sum(part["signatures"] > 0 for part in parts),
            "tasks_with_mixed_correctness_visible_clusters": sum(part["mixed_clusters"] > 0 for part in parts),
            "visible_clusters": sum(part["clusters"] for part in parts),
            "mixed_visible_clusters": sum(part["mixed_clusters"] for part in parts),
            "mixed_cluster_size_histogram": dict(Counter(
                size for part in parts for size in part["mixed_cluster_sizes"])),
            "candidates_missing_visible_signature": sum(part["signature_missing"] for part in parts),
            "signed_candidates_missing_correctness_label": sum(
                part["label_missing_in_clusters"] for part in parts),
        }
    return {
        "candidate_level_confusion_counts": dict(counts),
        "task_bootstrap_verification_rates": rates,
        "candidate_pool_and_cluster_summary": pool_summary,
    }


def _endpoint_rows(view, endpoint):
    visible = {(row["task"], row["sample"]): row["evidence"]["base"]
               for row in view.visible_records}
    labels = {(row["task"], row["sample"]): row for row in view.label_records}
    decisions = {row["task"]: row["decisions"] for row in view.decision_records}
    task_rows = {}
    for task in view.completed_tasks:
        entries = []
        for sample in range(8):
            key = task, sample
            label = labels[key]
            truth = label["y"] if endpoint == "official_compatible" else label["qualified_y"]
            heldout = label["h"] if endpoint == "official_compatible" or truth is not None else None
            entries.append({"y": truth, "v": visible[key]["pass"], "h": heldout,
                            "signature": visible[key]["signature"]})
        task_rows[task] = entries
    return task_rows, decisions, labels, visible


def _failure_summary(task_ids, rows, labels, visible):
    failures = Counter()
    for task in task_ids:
        for sample in range(8):
            key = task, sample
            full = labels[key]["outcomes"]["plus"]
            failures.update(failure_counts(labels[key], visible[key], full))
    return dict(failures)


def _duplicate_summary(view, task_ids):
    by_task = defaultdict(Counter)
    selected_tasks = set(task_ids)
    for row in view.call_records:
        if row.get("task") in selected_tasks and row.get("code_hash"):
            by_task[row["task"]][row["code_hash"]] += 1
    duplicate_extractions = sum(max(0, count - 1) for counts in by_task.values()
                                for count in counts.values())
    return {
        "candidate_code_hash_duplicates_beyond_first_copy": duplicate_extractions,
        "tasks_with_any_duplicate_extracted_code": sum(
            any(count > 1 for count in counts.values()) for counts in by_task.values()),
    }


def analyze_interim(view: InterimView, *, replicates=REPLICATES, seed=BOOTSTRAP_SEED):
    """Analyze the original, continuation, and combined checkpoint populations."""
    scopes = {
        "original_20": tuple(view.original_tasks),
        "continuation_10": tuple(view.continuation_tasks),
        "combined_30": tuple(view.completed_tasks),
    }
    result = {
        "analysis_status": "retrospective exploratory interim analysis; incomplete versus registered 40 tasks",
        "registered_population_tasks": REGISTERED_TASKS,
        "checkpoint_candidate_count": len(view.call_records),
        "unavailable_or_uncheckpointed": {
            "generation_only_outputs_excluded_from_correctness": view.generation_only_outputs,
            "interrupted_generation_without_output": view.interrupted_started_calls,
            "unstarted_registered_calls": view.unstarted_registered_calls,
            "uncheckpointed_registered_tasks": REGISTERED_TASKS - len(view.completed_tasks),
        },
        "resource_counters": {
            "parent_output_tokens": view.parent_output_tokens,
            "continuation_output_tokens_including_generation_only": view.continuation_output_tokens,
            "cumulative_output_tokens": view.cumulative_output_tokens,
            "parent_elapsed_seconds": view.parent_elapsed_seconds,
            "continuation_elapsed_seconds": view.continuation_elapsed_seconds,
            "cumulative_elapsed_seconds": view.cumulative_elapsed_seconds,
        },
        "endpoints": {},
    }
    for endpoint in ("official_compatible", "integrity_qualified"):
        task_rows, schedules, labels, visible = _endpoint_rows(view, endpoint)
        endpoint_result = {}
        for scope, task_ids in scopes.items():
            bootstrap = _bootstrap(task_ids, replicates=replicates, seed=seed)
            strata = _strata(task_ids)
            per_stratum = {}
            for stratum in ("overall", "humaneval", "mbpp"):
                ids = strata[stratum]
                if not ids:
                    per_stratum[stratum] = {"task_count": 0, "status": "no tasks in this stratum"}
                    continue
                registered_n = REGISTERED_TASKS if stratum == "overall" else BENCHMARK_TASKS
                per_stratum[stratum] = {
                    "task_count": len(ids),
                    "metrics": _score_metrics(task_rows, schedules, ids, bootstrap[stratum], registered_n),
                    **_evidence_summary(task_rows, ids, bootstrap[stratum]),
                    "extracted_code_duplicates": _duplicate_summary(view, ids),
                    "failure_counts": _failure_summary(ids, task_rows, labels, visible),
                }
            endpoint_result[scope] = {
                "tasks": len(task_ids),
                "humaneval_tasks": len(strata["humaneval"]),
                "mbpp_tasks": len(strata["mbpp"]),
                "tasks_with_complete_official_labels": sum(
                    all(task_rows[task][sample]["y"] is not None for sample in range(8))
                    for task in task_ids),
                "tasks_with_complete_integrity_qualified_labels": sum(
                    all(labels[(task, sample)]["qualified_y"] is not None for sample in range(8))
                    for task in task_ids),
                "strata": per_stratum,
            }
        result["endpoints"][endpoint] = endpoint_result

    # Candidate-call outcomes and evaluator measurements are descriptive and remain
    # separate from scientific correctness labels.
    parse_counts = Counter(row.get("parse", "missing") for row in view.call_records)
    result["generation_parse_outcomes"] = dict(parse_counts)
    result["generation_performance"] = {
        "median_prefill_tokens_per_second": statistics.median(
            row["prefill_tokens_per_second"] for row in view.generation_records),
        "median_decode_tokens_per_second": statistics.median(
            row["decode_tokens_per_second"] for row in view.generation_records),
        "peak_mlx_bytes": max(row["peak_mlx_bytes"] for row in view.generation_records),
        "peak_host_rss_bytes": max(row["host_peak_rss_bytes"] for row in view.generation_records),
        "generation_wall_seconds_sum": sum(row["wall_seconds"] for row in view.generation_records),
    }
    result["bootstrap"] = {"replicates": replicates, "seed": seed,
                            "unit": "task; stratified by benchmark; candidate and panel records nested"}
    result["interpretation_notes"] = {
        "first_candidate": "observed sample-0 correctness; not the unbiased pass@1 estimator",
        "pass_at_k": "available only when all eight labels are present and registered sampling assumptions apply",
        "false_rejection": "structurally constrained because full-suite correctness contains visible base tests",
        "interruption": "segment contrasts are descriptive and do not identify session or interruption effects",
        "missingness": "unavailable labels and uncheckpointed tasks are not assumed missing at random",
    }
    return result
