"""Run only the authorized 40-task E1 candidate bank, with separate evidence streams."""
import argparse
from collections import defaultdict
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


def run(args):
    lock, tasks = load_context(args)
    args.run.mkdir(mode=0o700)
    start = time.monotonic()
    deadline = start + WALL_CAP
    ledger = args.run / "ledger.jsonl"
    visible = args.run / "visible.jsonl"
    decisions = args.run / "decisions.jsonl"
    sealed = args.run / "sealed-labels.jsonl"
    baseline = environment(args.run)
    append(ledger, {"event": "start", "environment": baseline})
    if baseline["pressure"] >= 4 or baseline["free_bytes"] < DISK_FLOOR or baseline["container_ids"] or baseline["active_models"]:
        raise StopRun("initial runtime gate failed")
    calls = tokens = completed = 0
    swap_high = False
    costs = defaultdict(list)
    try:
        for ordinal, group in enumerate(chunk_indices()):
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
                        if calls >= CALL_CAP or tokens + 768 > TOKEN_CAP or time.monotonic() >= deadline:
                            raise StopRun("authorized E1 generation cap reached")
                        cid = sha(f'{lock["run_id"]}|{index}|{sample}|{seed}'.encode())
                        append(ledger, {"event": "call_started", "task": index, "sample": sample, "id": cid})
                        calls += 1
                        result = inference.generate(task["prompt"], seed, deadline)
                        evidence_json(chunk_dir / f"{cid}.json", result)
                        if result.get("status") != "ok" or not 1 <= result["output_tokens"] <= 768:
                            raise StopRun("generation infrastructure failure")
                        tokens += result["output_tokens"]
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
            completed += len(group)
            checkpoint = environment(args.run)
            forecast = sum(20 * (sum(costs[name])/len(costs[name])) for name in costs)
            append(ledger, {"event": "chunk_checkpoint", "chunk": ordinal, "completed_tasks": completed,
                            "environment": checkpoint, "wall": time.monotonic() - start,
                            "forecast_seconds": forecast, "reference_audit_seconds": lock["reference_audit_seconds"]})
            if ordinal == 0 and forecast >= WALL_CAP:
                raise StopRun("measured first-chunk workload does not fit the authorized window")
        append(ledger, {"event": "global_freeze", "calls": calls, "tokens": tokens, "tasks": completed,
                        "elapsed_seconds": time.monotonic() - start})
    except BaseException as error:
        append(ledger, {"event": "stopped", "calls": calls, "tokens": tokens, "tasks": completed,
                        "elapsed_seconds": time.monotonic() - start, "reason": str(error)})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("lock", "audit", "data", "model", "python", "run"):
        parser.add_argument("--" + field, required=True, type=Path)
    parser.add_argument("--protected-path", required=True, action="append", type=Path)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
