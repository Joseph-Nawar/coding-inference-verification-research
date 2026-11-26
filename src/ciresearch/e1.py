"""Run only the authorized 40-task E1 candidate bank, with separate evidence streams."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
import shutil
import subprocess
import time

from ciresearch.e1_data import chunk_indices, development_records, typed_cases, unique_panels
from ciresearch.evaluate import EvaluationUnavailable, evaluate_panel
from ciresearch.extract import extract
from ciresearch.model_host import OfflineModel
from ciresearch.p1 import MODEL_REVISION, append, evidence_json, sha, verify_model
from ciresearch.e1_continuation import (
    ContinuationError,
    _hash_tree,
    create_continuation_segment,
    parent_validation_pins,
    validate_parent,
    write_segment_manifest,
)

CALL_CAP = 320
TOKEN_CAP = 245760
WALL_CAP = 3600
DISK_FLOOR = 15 * 2**30
N = 8


class StopRun(RuntimeError):
    pass


def environment(path):
    vm = subprocess.check_output(
        ["sysctl", "kern.memorystatus_vm_pressure_level", "vm.swapusage"], text=True)
    pressure = re.search(r"pressure_level:\s*(\d+)", vm)
    swap = re.search(r"used\s*=\s*([\d.]+)([KMGT]?)", vm)
    if not pressure or not swap:
        raise StopRun("could not verify system pressure and swap")
    scale = {"": 2**-20, "K": 2**-10, "M": 1, "G": 1024, "T": 1024**2}
    processes = subprocess.check_output(["ps", "-axo", "pid=,command="], text=True, timeout=15)
    active_models = [line.split()[0] for line in processes.splitlines()
                     if " -m ciresearch.inference " in line and " -c " not in line]
    return {
        "unix": time.time(),
        "active_models": active_models,
        "pressure": int(pressure[1]),
        "swap_mib": float(swap[1]) * scale[swap[2]],
        "free_bytes": shutil.disk_usage(path).free,
        "container_ids": subprocess.check_output(
            ["docker", "--context", "desktop-linux", "ps", "-aq", "--filter",
             "name=ciresearch-panel-"], text=True, timeout=15).split(),
    }


def play(image, directory, dataset, task, program, cases, ref, deadline):
    if ref is None:
        return {"pass": None, "v_count": None, "signature": None, "reason": "reference_unavailable"}
    values, timings = ref
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise StopRun("authorized E1 wall budget exhausted")
    official_guard = min(60, sum(max(1.0, 4*t) for t in timings)) + 3
    try:
        verdict = evaluate_panel(image, directory, dataset, program, task["entry_point"],
                                 task["atol"], cases, values, timings,
                                 halt=lambda: time.monotonic() >= deadline,
                                 hard_seconds=min(remaining, official_guard))
    except EvaluationUnavailable as error:
        # Resource-limited or unsupported output is distinct from ordinary incorrectness.
        return {"pass": None, "v_count": None, "signature": None, "reason": str(error)}
    signature = None
    if verdict["initialization"] == "complete":
        frames = (directory / "responses.jsonl").open("rb")
        with frames:
            next(frames)
            digest = hashlib.sha256()
            for frame in frames:
                reply = json.loads(frame)
                observation = [reply["status"], reply.get("value")]
                digest.update(json.dumps(observation, separators=(",", ":")).encode() + b"\n")
            signature = digest.hexdigest()
    return {"pass": verdict["status"] == "pass", "v_count": sum(verdict["details"]),
            "signature": signature, "execution": verdict["execution"],
            "initialization": verdict["initialization"], "details": verdict["details"]}


def classify(result):
    text = result["text"]
    parsed, code = extract(text, result["entry"])
    if result["finish_reason"] == "length":
        parsed = "truncated"
    failure = {"pass": False, "v_count": 0, "signature": None, "reason": parsed}
    if parsed == "ok":
        failure = None
    return parsed, code, failure


def load_context(args):
    lock = json.loads(args.lock.read_bytes())
    if lock["stage"] != "E1" or lock["model_revision"] != MODEL_REVISION:
        raise StopRun("E1 is not authorized for this model")
    if lock["limits"] != {"calls": CALL_CAP, "output_tokens": TOKEN_CAP, "seconds": WALL_CAP}:
        raise StopRun("E1 cap mismatch")
    if lock["parameters"] != {"temperature": 0.7, "top_p": 0.95, "max_tokens": 768}:
        raise StopRun("generation settings mismatch")
    if not args.protected_path or not all(any(root.resolve() == path.resolve() or root.resolve() in path.resolve().parents
                                             for root in args.protected_path)
                                          for path in (args.lock, args.audit, args.data, args.run)):
        raise StopRun("protected data must be denied in generator and selector sandboxes")
    if any(len(seeds) != N or len(set(seeds)) != N for seeds in lock["seeds"]):
        raise StopRun("incomplete or duplicate registered sampling seeds")
    audit = args.audit.read_bytes()
    if sha(audit) != lock["audit_sha256"]:
        raise StopRun("integrity qualification artifact changed")
    audit = json.loads(audit)
    tasks = development_records(args.data, lock["split_sha256"])
    verify_model(args.model, lock["model_files"])
    if len(audit) != 40 or len(lock["prompt_sha256"]) != 40 or len(lock["seeds"]) != 40:
        raise StopRun("incomplete development registration")
    result = []
    for index, ((dataset, task), item) in enumerate(zip(tasks, audit)):
        if sha(task["prompt"].encode()) != lock["prompt_sha256"][index]:
            raise StopRun("registered prompt changed")
        base, plus = [typed_cases(task[f"{name}_input"], item["conversion"])
                      for name in ("base", "plus")]
        d, h = unique_panels(base, plus)
        if item["panel_sizes"] != dict(base=len(base), plus=len(plus), D=len(d), H=len(h)):
            raise StopRun("registered evidence partition changed")
        refs = {}
        for name in ("base", "plus", "D", "H"):
            entry = item["references"].get(name)
            if entry is not None:
                from ciresearch.wire import unpack
                refs[name] = ([unpack(v) for v in entry["values"]], entry["seconds"])
        result.append((dataset, task, item["integrity"], {"base": base, "plus": plus, "D": d, "H": h}, refs))
    return lock, result


def select_visible(args, rows, deadline):
    profile = OfflineModel(args.python, args.model, args.run, args.protected_path).profile
    environment = {"PATH": "/usr/bin:/bin", "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    selected = subprocess.run(
        ["/usr/bin/sandbox-exec", "-p", profile, sys._base_executable, "-B", "-m", "ciresearch.e1_select"],
        input=json.dumps([{"v_count": r["v_count"], "signature": r["signature"]} for r in rows]),
        env=environment, capture_output=True, text=True, check=True,
        timeout=max(0.01, min(10, deadline-time.monotonic())),
    )
    return json.loads(selected.stdout)


def forecast_continuation_total(elapsed_seconds, task_costs, future_groups, tasks, future_model_load_seconds):
    """Project total segment time from elapsed work plus unrun tasks and model starts."""
    counts = Counter(tasks[index][0] for group in future_groups for index in group)
    projected = float(elapsed_seconds)
    for benchmark, count in counts.items():
        samples = task_costs.get(benchmark, ())
        if count and not samples:
            raise StopRun(f"insufficient measured costs to forecast {benchmark} continuation tasks")
        if samples:
            projected += count * (sum(samples) / len(samples))
    projected += len(future_groups) * max(0.0, float(future_model_load_seconds))
    return projected


def run(args):
    continuation = getattr(args, "continue_from", None) is not None
    if not continuation and getattr(args, "expected_parent_ledger_sha256", None):
        raise StopRun("an expected parent hash requires --continue-from")
    parent = None
    if continuation:
        if args.run.exists():
            raise StopRun("continuation segment path already exists")
        expected = getattr(args, "expected_parent_ledger_sha256", None)
        try:
            pins = parent_validation_pins()
        except ContinuationError as error:
            raise StopRun(f"continuation integrity pins unavailable: {error}") from error
        if expected != pins["ledger_sha256"]:
            raise StopRun("continuation requires the approved stopped-parent ledger hash")
        try:
            parent = validate_parent(
                args.continue_from, expected,
                expected_manifest_sha256=pins["manifest_sha256"],
                expected_registration_sha256=pins["registration_sha256"],
                expected_checker_sha256=pins["checker_sha256"],
                expected_reference_build_sha256=pins["reference_build_sha256"],
            )
        except ContinuationError as error:
            raise StopRun(f"continuation parent validation failed: {error}") from error
        # Every process that can observe a generation prompt is denied the full parent tree.
        args.protected_path = [*args.protected_path, parent.root]
    lock, tasks = load_context(args)

    if continuation:
        baseline_path = args.run.parent
        if not baseline_path.is_dir():
            raise StopRun("continuation segment parent directory is unavailable")
        baseline = environment(baseline_path)
        diagnostic_log = baseline_path / "diagnostics" / "resource-observations-20261126.jsonl"
        diagnostic_log.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        append(diagnostic_log, {"event": "continuation_preflight", "segment": str(args.run),
                                "parent_ledger_sha256": parent.ledger_sha256,
                                "environment": baseline})
        try:
            registration = create_continuation_segment(
                args.run, parent, baseline, args.protected_path,
                chunk_ids=parent.remaining_chunks,
                task_ids=tuple(task for group in list(chunk_indices())[4:] for task in group),
                calls=parent.remaining_calls,
                tokens=parent.remaining_output_tokens,
                seconds=parent.remaining_seconds,
            )
        except ContinuationError as error:
            raise StopRun(f"continuation registration failed: {error}") from error
        call_cap = parent.remaining_calls
        token_cap = parent.remaining_output_tokens
        wall_cap = parent.remaining_seconds
        chunk_specs = list(enumerate(chunk_indices()))[4:]
        initial_calls = parent.completed_calls
        initial_tokens = parent.output_tokens
        initial_input_tokens = parent.input_tokens
        initial_tasks = len(parent.completed_tasks)
        initial_seconds = parent.elapsed_seconds
    else:
        args.run.mkdir(mode=0o700)
        baseline = environment(args.run)
        call_cap, token_cap, wall_cap = CALL_CAP, TOKEN_CAP, WALL_CAP
        chunk_specs = list(enumerate(chunk_indices()))
        initial_calls = initial_tokens = initial_input_tokens = initial_tasks = initial_seconds = 0

    start = time.monotonic()
    deadline = start + wall_cap
    ledger = args.run / "ledger.jsonl"
    visible = args.run / "visible.jsonl"
    decisions = args.run / "decisions.jsonl"
    sealed = args.run / "sealed-labels.jsonl"
    if continuation:
        registration_bytes = (args.run / "continuation-registration.json").read_bytes()
        append(ledger, {"event": "continuation_start", "environment": baseline,
                        "parent_ledger_sha256": parent.ledger_sha256,
                        "registration_sha256": sha(registration_bytes),
                        "starting_calls": initial_calls, "starting_tokens": initial_tokens,
                        "starting_input_tokens": initial_input_tokens,
                        "starting_tasks": initial_tasks, "starting_elapsed_seconds": initial_seconds})
    else:
        append(ledger, {"event": "start", "environment": baseline})
    calls = tokens = input_tokens = completed = 0
    swap_high = False
    costs = defaultdict(list)
    if (not continuation and (baseline["pressure"] >= 4 or baseline["free_bytes"] < DISK_FLOOR
                              or baseline["container_ids"] or baseline["active_models"])):
        raise StopRun("initial runtime gate failed")
    try:
        if (continuation and (baseline["pressure"] >= 4 or baseline["free_bytes"] < DISK_FLOOR
                or baseline["container_ids"] or baseline["active_models"])):
            raise StopRun("initial runtime gate failed")
        for ordinal, group in chunk_specs:
            snapshot = environment(args.run)
            append(ledger, {"event": "chunk_start", "chunk": ordinal, "environment": snapshot})
            high = snapshot["swap_mib"] - baseline["swap_mib"] >= 256
            if (snapshot["pressure"] >= 4 or snapshot["free_bytes"] < DISK_FLOOR
                    or snapshot["container_ids"] or snapshot["active_models"] or (high and swap_high)):
                raise StopRun("resource or containment gate failed at chunk boundary")
            swap_high = high
            if time.monotonic() >= deadline:
                raise StopRun("authorized E1 wall budget exhausted")
            chunk_dir = args.run / f"chunk-{ordinal:02d}"
            chunk_dir.mkdir(mode=0o700)
            programs = {}
            runtime = defaultdict(float)
            with OfflineModel(args.python, args.model, chunk_dir, args.protected_path) as inference:
                meta = inference.read(deadline)
                if meta.get("status") != "ready":
                    raise StopRun("offline model protocol failed")
                evidence_json(chunk_dir / "model-runtime.json", meta)
                for index in group:
                    _, task, _, _, _ = tasks[index]
                    started = time.monotonic()
                    items = []
                    for sample, seed in enumerate(lock["seeds"][index]):
                        if calls >= call_cap or tokens + 768 > token_cap or time.monotonic() >= deadline:
                            raise StopRun("authorized E1 generation cap reached")
                        cid = sha(f'{lock["run_id"]}|{index}|{sample}|{seed}'.encode())
                        append(ledger, {"event": "call_started", "task": index, "sample": sample, "id": cid})
                        calls += 1
                        result = inference.generate(task["prompt"], seed, deadline)
                        evidence_json(chunk_dir / f"{cid}.json", result)
                        if result.get("status") != "ok" or not 1 <= result["output_tokens"] <= 768:
                            raise StopRun("generation infrastructure failure")
                        tokens += result["output_tokens"]
                        input_tokens += result["input_tokens"]
                        parsed, code, failure = classify({**result, "entry": task["entry_point"]})
                        append(ledger, {"event": "call_complete", "id": cid, "task": index, "sample": sample,
                                        "parse": parsed, "code_hash": sha(code.encode()),
                                        "tokens": result["output_tokens"], "input_tokens": result["input_tokens"]})
                        evidence_json(chunk_dir / f"{cid}-code.json", {"parse": parsed, "code": code})
                        items.append((cid, code, failure))
                    programs[index] = items
                    runtime[index] += time.monotonic() - started
            append(ledger, {"event": "chunk_bank_frozen", "chunk": ordinal})
            known_visible = {}
            for index in group:
                dataset, task, _, panels, refs = tasks[index]
                image = lock["candidate_image"]
                began = time.monotonic()
                rows = []
                for sample, (cid, code, failure) in enumerate(programs[index]):
                    outputs = {}
                    for panel in ("base", "D"):
                        if panels[panel]:
                            outputs[panel] = failure or play(image, chunk_dir / f"{cid}-{panel}", dataset, task,
                                                             code, panels[panel], refs.get(panel), deadline)
                    v = outputs["base"]
                    rows.append({"v": v["pass"], "v_count": v["v_count"], "signature": v["signature"]})
                    append(visible, {"task": index, "sample": sample, "id": cid, "evidence": outputs})
                known_visible[index] = rows
                append(decisions, {"task": index, "decisions": select_visible(args, rows, deadline)})
                runtime[index] += time.monotonic() - began
            append(ledger, {"event": "chunk_decisions_frozen", "chunk": ordinal})
            for index in group:
                dataset, task, integrity, panels, refs = tasks[index]
                began = time.monotonic()
                for sample, (cid, code, failure) in enumerate(programs[index]):
                    outputs = {}
                    for panel in ("plus", "H"):
                        if panels[panel]:
                            outputs[panel] = (failure or play(image, chunk_dir / f"{cid}-{panel}",
                                                             dataset, task, code, panels[panel],
                                                             refs.get(panel), deadline))
                    plus = outputs["plus"]["pass"]
                    v = known_visible[index][sample]["v"]
                    y = None if "plus" not in refs or plus is None or v is None else bool(v and plus)
                    h = outputs.get("H", {}).get("pass") if "H" in refs else None
                    append(sealed, {"task": index, "sample": sample, "id": cid, "y": y, "h": h,
                                    "qualified_y": y if integrity else None, "outcomes": outputs})
                costs[dataset].append(runtime[index] + time.monotonic() - began)
            if continuation:
                append(ledger, {"event": "chunk_labels_joined", "chunk": ordinal})
            completed += len(group)
            checkpoint = environment(args.run)
            if continuation:
                future_groups = [future_group for future_ordinal, future_group in chunk_specs
                                 if future_ordinal > ordinal]
                forecast = forecast_continuation_total(
                    time.monotonic() - start, costs, future_groups, tasks,
                    meta.get("load_seconds", 0.0))
            else:
                forecast = sum(20 * (sum(costs[name])/len(costs[name])) for name in costs)
            checkpoint_record = {"event": "chunk_checkpoint", "chunk": ordinal,
                                 "completed_tasks": initial_tasks + completed,
                                 "environment": checkpoint, "wall": time.monotonic() - start,
                                 "forecast_seconds": forecast,
                                 "reference_audit_seconds": lock["reference_audit_seconds"]}
            if continuation:
                checkpoint_record["chunk_artifact_sha256"] = _hash_tree(chunk_dir)
            append(ledger, checkpoint_record)
            if ordinal == chunk_specs[0][0] and forecast >= wall_cap:
                raise StopRun("measured first-chunk workload does not fit the authorized window")
        elapsed = time.monotonic() - start
        append(ledger, {"event": "global_freeze", "calls": initial_calls + calls,
                        "tokens": initial_tokens + tokens,
                        "input_tokens": initial_input_tokens + input_tokens,
                        "tasks": initial_tasks + completed,
                        "elapsed_seconds": initial_seconds + elapsed,
                        "segment_calls": calls, "segment_tokens": tokens,
                        "segment_input_tokens": input_tokens,
                        "segment_tasks": completed, "segment_elapsed_seconds": elapsed})
    except BaseException as error:
        elapsed = time.monotonic() - start
        append(ledger, {"event": "stopped", "calls": initial_calls + calls,
                        "tokens": initial_tokens + tokens,
                        "input_tokens": initial_input_tokens + input_tokens,
                        "tasks": initial_tasks + completed,
                        "elapsed_seconds": initial_seconds + elapsed,
                        "segment_calls": calls, "segment_tokens": tokens,
                        "segment_input_tokens": input_tokens,
                        "segment_tasks": completed, "segment_elapsed_seconds": elapsed,
                        "reason": str(error)})
        if continuation:
            write_segment_manifest(args.run)
        raise
    if continuation:
        write_segment_manifest(args.run)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("lock", "audit", "data", "model", "python", "run"):
        parser.add_argument("--" + field, required=True, type=Path)
    parser.add_argument("--continue-from", type=Path)
    parser.add_argument("--expected-parent-ledger-sha256")
    parser.add_argument("--protected-path", required=True, action="append", type=Path)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
