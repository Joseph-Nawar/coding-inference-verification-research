"""Bounded engineering smoke. This module accepts only the registered smoke split."""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import uuid

from ciresearch.evaluate import evaluate_panel
from ciresearch.extract import extract
from ciresearch.fixture_client import reference_panel
from ciresearch.model_host import OfflineModel
from ciresearch.smoke_data import smoke_records
from ciresearch.wire import pack, write_frame

MODEL_REVISION = "3dd939c621c08e5753d5b89f35a2642cd83b98ca"
WEIGHT_SHA256 = "d448aef7ea541ec604ec05f6aef13b80a0017c6cc7acb9261a005e0358995db9"
GATES = {"patched", "lock", "model", "offline", "containment", "synthetic_parity", "smoke_parity"}
CALL_LIMIT = 24
TOKEN_LIMIT = 18432


def sha(data):
    return hashlib.sha256(data).hexdigest()


def evidence_json(path, value):
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.partial")
    with temporary.open("x") as handle:
        json.dump(value, handle, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.link(temporary, path)
    temporary.unlink()


def append(path, value):
    with path.open("a") as handle:
        json.dump(value, handle, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def panels(task):
    visible = {write_frame(pack(case)) for case in task["base_input"]}
    first = {}
    for index, item in enumerate(task["plus_input"]):
        value = write_frame(pack(item))
        if value not in visible:
            first.setdefault(value, index)
    ordered = sorted(first, key=lambda value: hashlib.sha256(value).digest())
    if len(ordered) < 16:
        return [], []
    return [first[key] for key in ordered[:8]], [first[key] for key in ordered[8:]]


def verify_model(directory, expected_files):
    for name, expected in expected_files.items():
        if Path(name).name != name:
            raise ValueError("invalid model filename")
        digester = hashlib.sha256()
        with (directory / name).open("rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digester.update(block)
        if digester.hexdigest() != expected:
            raise ValueError(f"model file hash mismatch: {name}")
    if expected_files.get("model.safetensors") != WEIGHT_SHA256:
        raise ValueError("unverified model weights")
    for core in ("config.json", "tokenizer_config.json", "tokenizer.json", "model.safetensors.index.json"):
        if core not in expected_files:
            raise ValueError(f"missing registered model input: {core}")
    allowed = set(expected_files) | {".cache"}
    if not {item.name for item in directory.iterdir()} <= allowed:
        raise ValueError("unexpected file in model directory")


def run(args):
    authorization = args.authorization.read_bytes()
    auth = json.loads(authorization)
    if (auth.get("stage") != "P1" or auth.get("model_revision") != MODEL_REVISION
            or auth.get("gates") != dict.fromkeys(GATES, True)
            or auth.get("images") != {"candidate": args.candidate_image, "official": args.official_image}):
        raise ValueError("P1 technical gates have not all passed")
    tasks = list(smoke_records(args.data))
    if len(tasks) != 8 or shutil.disk_usage(args.run.parent).free < 15 * 2**30:
        raise ValueError("smoke population or resource floor mismatch")
    verify_model(args.model, auth["model_files"])
    if args.dry_run:
        print(json.dumps({"stage": "P1", "smoke_tasks": 8, "planned_calls": 17, "technical_gates": "verified"}))
        return
    ledger = args.run / "ledger.jsonl"
    runtime_path = args.run / "run-metadata.json"
    source = Path(__file__).resolve().parent
    version = sha(b"".join(path.read_bytes() for path in sorted(source.glob("*.py"))))
    identity = {"authorization_sha256": sha(authorization), "implementation_sha256": version}
    if args.resume:
        saved = json.loads(runtime_path.read_text())
        if saved["identity"] != identity:
            raise ValueError("resume identity differs from the original run")
        previous = [json.loads(line) for line in ledger.read_text().splitlines()]
        if any(row["event"] == "p1_complete" for row in previous):
            raise ValueError("P1 already completed")
        start = saved["started_unix"]
    else:
        args.run.mkdir(mode=0o700)
        start = time.time()
        evidence_json(runtime_path, {"started_unix": start, "identity": identity})
        previous = []
    deadline = time.monotonic() + (90 * 60 - (time.time() - start))
    started = {row["call_id"] for row in previous if row["event"] == "call_started"}
    completed = {row["call_id"]: row for row in previous if row["event"] == "call_completed"}
    scored = {row["candidate"] for row in previous if row["event"] == "scored"}
    count = len(started)
    tokens = sum(row["output_tokens"] for row in completed.values())
    generated = []

    def call(inference, task, ordinal, replay=False):
        nonlocal count, tokens
        seed_text = f'{auth["seed_namespace"]}|P1|{task["task_id"]}|{ordinal}|{MODEL_REVISION}'
        seed_hash = sha(seed_text.encode())
        seed = int(seed_hash[:8], 16)
        call_id = sha((seed_hash + ("|live_replay" if replay else "|generation")).encode())
        raw_path = args.run / f"{call_id}-raw.json"
        if call_id in started:
            if not raw_path.is_file():
                raise RuntimeError("a prior call started without a durable response; retry denied")
            response = json.loads(raw_path.read_text())
            if call_id in completed:
                return call_id, *extract(response["text"], task["entry_point"]), response
        else:
            if count >= CALL_LIMIT or tokens + 768 > TOKEN_LIMIT or time.monotonic() >= deadline:
                raise RuntimeError("generation cap reached")
            append(ledger, {"event": "call_started", "call_id": call_id, "seed": seed, "replay": replay,
                            "task": task["task_id"], "prompt_hash": sha(task["prompt"].encode())})
            count += 1
            response = inference.generate(task["prompt"], seed, deadline)
            evidence_json(raw_path, response)
        if response.get("status") != "ok" or not 1 <= response.get("output_tokens", 0) <= 768:
            raise RuntimeError("invalid inference accounting")
        tokens += response["output_tokens"]
        parsed, code = extract(response["text"], task["entry_point"])
        append(ledger, {"event": "call_completed", "call_id": call_id, "parse": parsed,
                        "input_tokens": response["input_tokens"], "output_tokens": response["output_tokens"],
                        "code_hash": sha(code.encode())})
        return call_id, parsed, code, response

    # All candidate text is frozen before accessing per-candidate evaluation.
    with OfflineModel(args.python, args.model, args.run,
                      [args.data, args.authorization.parent, args.run, *args.protected_path]) as inference:
        meta = inference.read(min(deadline, time.monotonic() + 120))
        if meta.get("status") != "ready":
            raise RuntimeError("model preflight failed")
        if not (args.run / "model-runtime.json").exists():
            evidence_json(args.run / "model-runtime.json", meta)
        for dataset, task in tasks:
            for ordinal in (0, 1):
                generated.append((dataset, task, call(inference, task, ordinal)))
        first_task, first = generated[0][1:]
        cached = json.loads((args.run / f"{first[0]}-raw.json").read_text())
        replay = call(inference, first_task, 0, replay=True)
        if not (args.run / "reproducibility.json").exists():
            evidence_json(args.run / "reproducibility.json", {
                "cached_extraction_equal": extract(cached["text"], first_task["entry_point"]) == first[1:3],
                "live_text_equal": replay[3]["text"] == first[3]["text"],
                "live_tokens_equal": replay[3]["token_ids"] == first[3]["token_ids"],
            })
    append(ledger, {"event": "generation_frozen", "calls": count, "output_tokens": tokens})
    references = {}
    for dataset, task, (cid, parsed, code, _) in generated:
        if cid in scored:
            continue
        if args.resume and any(args.run.glob(f"{cid}-*-candidate")):
            raise RuntimeError("a prior candidate assessment is incomplete; retry denied")
        if time.monotonic() >= deadline or shutil.disk_usage(args.run).free < 15 * 2**30:
            raise RuntimeError("P1 resource cap reached")
        comparison = {"task": task["task_id"], "candidate": cid, "parse": parsed}
        if parsed == "ok":
            measured = time.monotonic()
            for panel in ("base", "plus"):
                cases = task[f"{panel}_input"]
                key = (task["task_id"], panel)
                if key not in references:
                    values, timing, _ = reference_panel(
                        args.official_image, args.run / f"{cid}-{panel}-reference", dataset,
                        task["entry_point"], task["atol"], 1.0, cases,
                        reference=task["prompt"] + task["canonical_solution"], deadline=deadline,
                    )
                    references[key] = values, timing
                comparison[panel] = evaluate_panel(
                    args.candidate_image, args.run / f"{cid}-{panel}-candidate", dataset,
                    code, task["entry_point"], task["atol"], cases, *references[key],
                    halt=lambda: time.monotonic() >= deadline,
                )
            comparison["evaluator_wall_seconds"] = time.monotonic() - measured
            comparison["full_pass"] = all(comparison[p]["status"] == "pass" for p in ("base", "plus"))
            d, h = panels(task)
            if d:
                details = comparison["plus"]["details"]
                comparison["diagnostic"] = [details[i] for i in d]
                comparison["withheld"] = [details[i] for i in h]
        else:
            comparison["full_pass"] = False
        append(ledger, {"event": "scored", **comparison})
    append(ledger, {"event": "p1_complete", "wall_seconds": time.time() - start})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("authorization", "data", "model", "python", "run"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--stage", choices=("P1",), default="P1")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--resume", action="store_true")
    parser.add_argument("--protected-path", action="append", required=True, type=Path)
    parser.add_argument("--candidate-image", required=True)
    parser.add_argument("--official-image", required=True)
    args = parser.parse_args()
    lock = args.run.parent / f".{args.run.name}.lock"
    descriptor = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run(args)
    finally:
        os.close(descriptor)


if __name__ == "__main__":
    main()
