"""Resource-gated E2 selector execution; never executes candidate code."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Callable

from ciresearch.e2 import E2Error, make_call_seed, parse_selector_response
from ciresearch.e2_model_host import E2ModelError, E2OfflineModel
from ciresearch.e2_prompts import E2_USER_PREFIX

CALL_CAP = 96
OUTPUT_TOKEN_CAP = 12_288
OUTPUT_PER_CALL = 128
WALL_SECONDS_CAP = 1800
DISK_FLOOR_BYTES = 15 * 2**30
SWAP_GROWTH_MIB = 256
ALLOWED_FRONTMOST_APPS = {"Finder", "Terminal", "Codex", "Activity Monitor"}
WORKER_NAMES = ("ciresearch.inference", "ciresearch.e2_inference", "ciresearch.worker")


class E2RunError(RuntimeError):
    """E2 plan or runtime gate failed closed."""


class E2ResourceStop(E2RunError):
    """The registered E2 resource stop condition was reached."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise E2RunError("duplicate key in frozen E2 plan")
        result[key] = value
    return result


def load_plan(path: Path):
    try:
        plan = json.loads(Path(path).read_text(), object_pairs_hook=_json_no_duplicates)
    except (OSError, json.JSONDecodeError) as error:
        raise E2RunError("private E2 registration is unavailable or malformed") from error
    validate_frozen_plan(plan)
    return plan, _sha(Path(path).read_bytes())


def validate_frozen_plan(plan: dict):
    if (type(plan) is not dict or plan.get("schema") != "ciresearch-e2-private-registration.v3"
            or plan.get("status") != "technical_preflight_complete"
            or plan.get("labels_read") is not False or plan.get("confirmation_accessed") is not False):
        raise E2RunError("E2 registration is not frozen, eligible, and label-blind")
    for field in ("protocol_sha256", "config_sha256", "runtime_dependency_lock_sha256"):
        if type(plan.get(field)) is not str or re.fullmatch(r"[0-9a-f]{64}", plan[field]) is None:
            raise E2RunError(f"frozen E2 {field} is missing or malformed")
    protected = plan.get("worker_protected_roots")
    protected_roles = {"e1_parent", "e1_continuation", "dataset", "e2_private"}
    if (type(protected) is not dict or set(protected) != protected_roles
            or any(type(value) is not str or not Path(value).is_absolute()
                   for value in protected.values())
            or len(set(protected.values())) != len(protected_roles)):
        raise E2RunError("frozen E2 worker protected roots are missing or malformed")
    schedule, sample = plan.get("call_schedule"), plan.get("sample")
    if type(schedule) is not list or type(sample) is not list or len(sample) != 24 or len(schedule) != CALL_CAP:
        raise E2RunError("frozen E2 schedule does not contain exactly 24 tasks and 96 calls")
    if sum(row.get("benchmark") == "humaneval" for row in sample) != 12 or sum(
            row.get("benchmark") == "mbpp" for row in sample) != 12:
        raise E2RunError("frozen E2 sample is not balanced 12/12")
    if plan.get("model_sampling") != {"temperature": 0.7, "top_p": 0.95,
                                      "max_new_tokens": 128, "context_limit": 8192,
                                      "input_limit": 8064}:
        raise E2RunError("frozen E2 inference parameters differ from authorization")
    if plan.get("caps") != {"tasks": 24, "model_call_starts": 96, "output_tokens": 12288,
                            "empirical_seconds": 1800, "inference_streams": 1,
                            "minimum_free_disk_gib": 15, "batch_tasks": 4}:
        raise E2RunError("frozen E2 caps differ from authorization")
    if (plan.get("resource_gate", {}).get("fresh_boot_required") is not True
            or plan["resource_gate"].get("repeat_rebaseline_to_bypass_stop") is not False):
        raise E2RunError("fresh-boot or no-rebaseline resource protection is absent")
    tasks = {row["task_id"]: row for row in sample}
    if len(tasks) != 24:
        raise E2RunError("sample task identities are duplicated")
    batch_rows = {}
    for row in sample:
        batch_rows.setdefault(row.get("batch"), []).append(row)
    if set(batch_rows) != set(range(6)) or any(len(rows) != 4 for rows in batch_rows.values()):
        raise E2RunError("frozen E2 sample does not contain six four-task batches")
    for rows in batch_rows.values():
        if sum(row.get("benchmark") == "humaneval" for row in rows) != 2 or sum(
                row.get("benchmark") == "mbpp" for row in rows) != 2:
            raise E2RunError("E2 batch is not balanced by benchmark")
        for position in range(4):
            if {row["arm_order"][position] for row in rows} != {"A", "B", "C", "D"}:
                raise E2RunError("E2 arm order is not balanced within its batch")
    call_ids, counts_by_task, choices_by_task = set(), {}, {}
    for index, call in enumerate(schedule):
        if type(call) is not dict or call.get("sequence") != index:
            raise E2RunError("E2 call sequence is malformed")
        task_id, arm = call.get("task_id"), call.get("arm")
        if task_id not in tasks or arm not in {"A", "B", "C", "D"}:
            raise E2RunError("scheduled call is outside the frozen task/arm set")
        if call.get("batch") != tasks[task_id].get("batch"):
            raise E2RunError("scheduled call batch differs from the frozen sample")
        if call.get("benchmark") != tasks[task_id].get("benchmark"):
            raise E2RunError("scheduled call benchmark differs from the frozen sample")
        if type(call.get("prompt")) is not str or type(call.get("input_tokens")) is not int:
            raise E2RunError("frozen prompt or token count is missing")
        if not 1 <= call["input_tokens"] <= 8064 or call.get("max_new_tokens") != OUTPUT_PER_CALL:
            raise E2RunError("frozen call exceeds the input or output token allowance")
        if _sha(call["prompt"].encode("utf-8")) != call.get("prompt_sha256"):
            raise E2RunError("frozen selector prompt hash mismatch")
        if call.get("call_id") in call_ids:
            raise E2RunError("duplicate immutable E2 call identity")
        call_ids.add(call["call_id"])
        expected_seed = make_call_seed(task_id, arm, plan["model_revision"], plan["namespace"])
        if call.get("seed") != expected_seed:
            raise E2RunError("call seed differs from the registered derivation")
        expected_call_id = _sha(
            f"{plan['namespace']}\0call-v1\0{task_id}\0{arm}\0{expected_seed}\0{call['prompt_sha256']}".encode())
        if call.get("call_id") != expected_call_id:
            raise E2RunError("immutable call identity differs from its frozen prompt and seed")
        call_map = call.get("candidate_map")
        if (type(call_map) is not list or len(call_map) != 4
                or [row.get("display_index") for row in call_map] != [1, 2, 3, 4]
                or len({row.get("candidate_id") for row in call_map}) != 4
                or len({row.get("original_sample") for row in call_map}) != 4):
            raise E2RunError("frozen displayed-to-original candidate map is invalid")
        prior = choices_by_task.setdefault(task_id, tuple(
            (row["candidate_id"], row["original_sample"]) for row in call_map))
        if prior != tuple((row["candidate_id"], row["original_sample"]) for row in call_map):
            raise E2RunError("candidate permutation differs between E2 conditions")
        counts_by_task.setdefault(task_id, []).append(arm)
        payload = _validate_prompt_payload(call["prompt"], arm)
        candidate_codes = [row["code"] for row in payload["candidates"]]
        if len(candidate_codes) != 4 or any(type(code) is not str for code in candidate_codes):
            raise E2RunError("candidate prompt does not contain four bounded source strings")
    for task_id, row in tasks.items():
        if counts_by_task.get(task_id) != list(row["arm_order"]):
            raise E2RunError("call schedule does not preserve each frozen task arm order")
    if len(counts_by_task) != 24 or sum(map(len, counts_by_task.values())) != CALL_CAP:
        raise E2RunError("scheduled call coverage is incomplete")


def _validate_prompt_payload(prompt: str, arm: str):
    if not prompt.startswith(E2_USER_PREFIX):
        raise E2RunError("frozen selector prompt has an unexpected registered prefix")
    try:
        encoded = prompt[len(E2_USER_PREFIX):]
        payload = json.loads(encoded, object_pairs_hook=_json_no_duplicates,
                             parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()))
    except (ValueError, json.JSONDecodeError) as error:
        raise E2RunError("frozen E2 prompt does not match the registered bounded JSON format") from error
    expected_keys = {
        "A": {"task", "candidates"},
        "B": {"task", "candidates", "visible_results"},
        "C": {"task", "candidates", "visible_results", "diagnostic"},
        "D": {"task", "candidates", "visible_results", "diagnostic",
              "expected_outputs", "comparison_results"},
    }[arm]
    if type(payload) is not dict or set(payload) != expected_keys:
        raise E2RunError("frozen prompt contains unregistered or missing evidence fields")
    if type(payload.get("task")) is not str or type(payload.get("candidates")) is not list:
        raise E2RunError("frozen prompt lacks task text or candidate records")
    if len(payload["candidates"]) != 4 or any(
            type(row) is not dict or set(row) != {"index", "status", "code"}
            or row["index"] not in (1, 2, 3, 4) or type(row["status"]) is not str
            or type(row["code"]) is not str for row in payload["candidates"]):
        raise E2RunError("candidate prompt records have an invalid bounded shape")
    if arm in {"B", "C", "D"}:
        visible = payload["visible_results"]
        if type(visible) is not list or len(visible) != 4 or any(
                type(row) is not dict or set(row) !=
                {"index", "pass_count", "case_count", "passed", "status"}
                for row in visible):
            raise E2RunError("visible evidence prompt schema is invalid")
    if arm in {"C", "D"}:
        diagnostic = payload["diagnostic"]
        if (type(diagnostic) is not dict or set(diagnostic) != {"inputs", "candidate_results"}
                or type(diagnostic["inputs"]) is not list
                or type(diagnostic["candidate_results"]) is not list
                or len(diagnostic["candidate_results"]) != 4):
            raise E2RunError("cached diagnostic evidence prompt schema is invalid")
        if any(type(row) is not dict or set(row) != {"args"} for row in diagnostic["inputs"]):
            raise E2RunError("diagnostic input prompt schema is invalid")
        for candidate in diagnostic["candidate_results"]:
            if (type(candidate) is not dict or set(candidate) != {"index", "initialization", "cases"}
                    or type(candidate["cases"]) is not list):
                raise E2RunError("diagnostic output prompt schema is invalid")
            for case in candidate["cases"]:
                if (type(case) is not dict or "args_after" in case
                        or set(case) not in ({"execution_status"},
                                             {"execution_status", "value"})):
                    raise E2RunError("candidate-reported state or unsupported output entered the prompt")
    if arm == "D":
        if type(payload["expected_outputs"]) is not list or type(payload["comparison_results"]) is not list:
            raise E2RunError("oracle-assisted D evidence is malformed")
        if any(type(row) is not dict or set(row) != {"index", "cases"}
               or type(row["cases"]) is not list for row in payload["comparison_results"]):
            raise E2RunError("D comparator evidence is malformed")
        if any(type(case) is not dict or set(case) != {"execution_status", "comparison"}
               for row in payload["comparison_results"] for case in row["cases"]):
            raise E2RunError("D comparator prompt contains unsupported fields")
    return payload


def _command(argv, timeout=10):
    return subprocess.run(argv, text=True, capture_output=True, timeout=timeout, check=True).stdout.strip()


def _sysctl_integer(name):
    return int(_command(["sysctl", "-n", name]))


def _boot_unix():
    raw = _command(["sysctl", "kern.boottime"])
    match = re.search(r"sec\s*=\s*(\d+)", raw)
    if not match:
        raise E2RunError("macOS boot timestamp could not be verified")
    return int(match.group(1))


def _frontmost_apps():
    script = ('tell application "System Events" to get name of every application process '
              'whose background only is false')
    value = _command(["osascript", "-e", script], timeout=8)
    return sorted({name.strip() for name in value.split(",") if name.strip()})


def resource_snapshot(directory: Path) -> dict:
    try:
        pressure = _sysctl_integer("kern.memorystatus_vm_pressure_level")
        swap_raw = _command(["sysctl", "vm.swapusage"])
        swap_match = re.search(r"used\s*=\s*([\d.]+)([KMGT]?)", swap_raw)
        if not swap_match:
            raise E2RunError("macOS swap usage could not be parsed")
        scale = {"": 2**-20, "K": 2**-10, "M": 1, "G": 1024, "T": 1024**2}
        swap_mib = float(swap_match.group(1)) * scale[swap_match.group(2)]
        physical_bytes = _sysctl_integer("hw.memsize")
        page_size = _sysctl_integer("hw.pagesize")
        vm = _command(["vm_stat"])
        free_match = re.search(r"Pages free:\s+(\d+)", vm)
        inactive_match = re.search(r"Pages inactive:\s+(\d+)", vm)
        speculative_match = re.search(r"Pages speculative:\s+(\d+)", vm)
        if not all((free_match, inactive_match, speculative_match)):
            raise E2RunError("available physical memory could not be estimated")
        available = sum(int(match.group(1)) for match in
                        (free_match, inactive_match, speculative_match)) * page_size
        processes = _command(["ps", "-axo", "pid=,command="], timeout=15)
        active_workers = [line.strip() for line in processes.splitlines()
                          if any(name in line for name in WORKER_NAMES)]
        ollama = [line.strip() for line in processes.splitlines() if "ollama serve" in line]
        apps = _frontmost_apps()
        docker_proc = [line.strip() for line in processes.splitlines()
                       if any(name in line.lower() for name in
                              ("docker desktop", "com.docker.backend", "com.docker.vpnkit"))]
        if docker_proc:
            try:
                containers = _command(["docker", "--context", "desktop-linux", "ps", "-aq"], timeout=8).split()
                docker_status = "active"
            except Exception:
                containers, docker_status = None, "unavailable"
        else:
            containers, docker_status = [], "stopped"
        return {
            "observed_unix": time.time(), "boot_unix": _boot_unix(),
            "physical_memory_bytes": physical_bytes, "estimated_available_memory_bytes": available,
            "memory_pressure_level": pressure, "swap_used_mib": swap_mib,
            "free_disk_bytes": shutil.disk_usage(directory).free,
            "frontmost_apps": apps, "active_research_workers": active_workers,
            "active_ollama_processes": ollama, "docker_processes": docker_proc,
            "docker_query": docker_status,
            "research_containers": containers,
        }
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        raise E2RunError("resource snapshot is incomplete; E2 cannot start") from error


def _assert_clean_start(snapshot: dict, minimum_boot_unix: int):
    if snapshot["boot_unix"] <= minimum_boot_unix:
        raise E2ResourceStop("a genuinely fresh boot after the accepted E1 stop is required")
    if snapshot["memory_pressure_level"] >= 4:
        raise E2ResourceStop("initial macOS memory pressure is critical")
    if snapshot["free_disk_bytes"] < DISK_FLOOR_BYTES:
        raise E2ResourceStop("less than 15 GiB of free disk remains")
    if snapshot["frontmost_apps"] is None or not set(snapshot["frontmost_apps"]).issubset(ALLOWED_FRONTMOST_APPS):
        raise E2ResourceStop("unnecessary or unverifiable foreground applications remain open")
    if snapshot["active_research_workers"] or snapshot["active_ollama_processes"]:
        raise E2ResourceStop("a stale model, evaluator, runner, or Ollama process is active")
    if snapshot["docker_query"] != "stopped" or snapshot["research_containers"]:
        raise E2ResourceStop("unused Docker services remain active or a research container is present")


class ResourceGuard:
    def __init__(self, baseline: dict):
        self.baseline = baseline
        self.previous_high_swap = False

    def check(self, snapshot: dict):
        if snapshot["memory_pressure_level"] >= 4:
            raise E2ResourceStop("critical memory pressure during E2")
        if snapshot["free_disk_bytes"] < DISK_FLOOR_BYTES:
            raise E2ResourceStop("E2 disk floor was crossed")
        high = snapshot["swap_used_mib"] - self.baseline["swap_used_mib"] >= SWAP_GROWTH_MIB
        if high and self.previous_high_swap:
            raise E2ResourceStop("swap grew by at least 256 MiB in consecutive observations")
        self.previous_high_swap = high
        return snapshot


def _append(stream, value):
    stream.write(json.dumps(value, ensure_ascii=True, allow_nan=False,
                             separators=(",", ":"), sort_keys=True) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def _write_exclusive(path: Path, value):
    data = (json.dumps(value, ensure_ascii=True, allow_nan=False,
                       separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o600)
    return _sha(data)


def _iso_epoch(value):
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
    except (TypeError, ValueError) as error:
        raise E2RunError("frozen E2 registration has no valid fresh-boot threshold") from error


def validate_worker_denials(plan: dict, denied_paths) -> tuple[Path, ...]:
    """Require effective sandbox read denials to cover every frozen protected root."""
    try:
        denials = tuple(Path(path).resolve(strict=True) for path in denied_paths)
        roots = {role: Path(path).resolve(strict=True)
                 for role, path in plan["worker_protected_roots"].items()}
    except (OSError, KeyError, TypeError) as error:
        raise E2RunError("a registered E2 protected root or denial path is unavailable") from error
    if not denials or len(set(denials)) != len(denials):
        raise E2RunError("effective E2 worker read-denial paths are empty or duplicated")
    uncovered = [role for role, root in roots.items()
                 if not any(denial == root or denial in root.parents for denial in denials)]
    if uncovered:
        raise E2RunError("sandbox deny paths do not cover every registered protected root")
    return denials


def run_e2(plan_path: Path, *, model_path: Path, python_path: Path, output_dir: Path,
           denied_paths, resource_provider: Callable[[Path], dict] = resource_snapshot):
    plan, plan_sha = load_plan(plan_path)
    denied_paths = validate_worker_denials(plan, denied_paths)
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise E2RunError("refusing to overwrite or resume an E2 run directory")
    output_dir.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    baseline = resource_provider(output_dir.parent)
    gate = plan.get("resource_gate", {})
    if gate.get("fresh_boot_required") is not True:
        raise E2RunError("fresh-boot resource gate is absent from the E2 registration")
    minimum_boot = _iso_epoch(gate.get("requires_fresh_boot_after_utc"))
    _assert_clean_start(baseline, minimum_boot)
    from ciresearch.p1 import verify_model
    verify_model(Path(model_path), plan["model_files"])
    guard = ResourceGuard(baseline)
    output_dir.mkdir(mode=0o700, parents=True)
    (output_dir / "responses").mkdir(mode=0o700)
    ledger_path = output_dir / "ledger.jsonl"
    monitor_path = output_dir / "resource-monitor.jsonl"
    decision_path = output_dir / "decisions.jsonl"
    ledger = ledger_path.open("x", encoding="utf-8")
    monitor = monitor_path.open("x", encoding="utf-8")
    decisions = decision_path.open("x", encoding="utf-8")
    run_start = time.monotonic()
    deadline = run_start + WALL_SECONDS_CAP
    starts = output_tokens = input_tokens = parsed = invalid = 0
    last_sample = 0.0

    def sample_resource(force=False):
        nonlocal last_sample
        now = time.monotonic()
        if not force and now - last_sample < 5:
            return
        snapshot = resource_provider(output_dir)
        guard.check(snapshot)
        _append(monitor, {"event": "resource_sample", "elapsed_seconds": now - run_start,
                          "snapshot": snapshot})
        last_sample = now

    try:
        _append(ledger, {"event": "run_started", "plan_sha256": plan_sha,
                         "model_revision": plan["model_revision"],
                         "starting_environment": baseline,
                         "fresh_boot_threshold_unix": minimum_boot})
        with E2OfflineModel(python_path, model_path, output_dir, denied_paths) as model:
            ready = model.wait_ready(min(deadline, time.monotonic() + 120), sample_resource)
            _write_exclusive(output_dir / "model-runtime.json", ready)
            batches = []
            for call in plan["call_schedule"]:
                if not batches or batches[-1][0]["batch"] != call["batch"]:
                    batches.append([])
                batches[-1].append(call)
            for batch_number, calls in enumerate(batches):
                snapshot = resource_provider(output_dir)
                guard.check(snapshot)
                _append(ledger, {"event": "batch_start", "batch": batch_number,
                                 "snapshot": snapshot, "call_count": len(calls)})
                for call in calls:
                    if starts >= CALL_CAP or output_tokens >= OUTPUT_TOKEN_CAP:
                        raise E2RunError("registered E2 call or output-token cap reached")
                    if time.monotonic() >= deadline:
                        raise E2ResourceStop("registered 30-minute E2 wall cap reached")
                    if call["input_tokens"] + OUTPUT_PER_CALL > 8192:
                        raise E2RunError("frozen call exceeds model context after output reserve")
                    _append(ledger, {"event": "call_started", "sequence": call["sequence"],
                                     "call_id": call["call_id"], "task_id": call["task_id"],
                                     "arm": call["arm"], "seed": call["seed"],
                                     "prompt_sha256": call["prompt_sha256"],
                                     "input_tokens_registered": call["input_tokens"]})
                    starts += 1
                    try:
                        result = model.generate(call["prompt"], call["seed"],
                                                call["input_tokens"], deadline, sample_resource)
                    except Exception as error:
                        _append(ledger, {"event": "call_interrupted", "sequence": call["sequence"],
                                         "call_id": call["call_id"], "error_type": type(error).__name__,
                                         "model_calls_started": starts})
                        raise
                    raw_sha = _write_exclusive(output_dir / "responses" / f"{call['call_id']}.json", result)
                    output_count = result.get("output_tokens", result.get("observed_partial_tokens", 0))
                    if type(output_count) is not int or not 0 <= output_count <= OUTPUT_PER_CALL:
                        _append(ledger, {"event": "call_invalid_worker_counters",
                                         "call_id": call["call_id"], "response_sha256": raw_sha})
                        raise E2ModelError("worker output token count violates the per-call cap")
                    output_tokens += output_count
                    input_count = result.get("input_tokens")
                    if type(input_count) is int:
                        input_tokens += input_count
                    if result.get("status") != "ok":
                        _append(ledger, {"event": "call_infrastructure_failure",
                                         "call_id": call["call_id"], "response_sha256": raw_sha,
                                         "observed_partial_tokens": output_count})
                        raise E2ModelError("offline inference returned an infrastructure failure")
                    if (result.get("input_tokens") != call["input_tokens"]
                            or result.get("output_tokens") != output_count):
                        raise E2ModelError("actual worker token counters differ from the frozen call")
                    selector_choice = None
                    parse_status = "ok"
                    if result.get("finish_reason") == "length":
                        parse_status, invalid = "truncated", invalid + 1
                    else:
                        try:
                            ids = [row["candidate_id"] for row in call["candidate_map"]]
                            selector_choice = parse_selector_response(result.get("text"), ids)
                            parsed += 1
                        except E2Error:
                            parse_status, invalid = "invalid_response", invalid + 1
                    decision = {"call_id": call["call_id"], "task_id": call["task_id"],
                                "arm": call["arm"], "selection_status": parse_status,
                                "selected_candidate_id": selector_choice,
                                "finish_reason": result.get("finish_reason"),
                                "response_sha256": raw_sha}
                    _append(decisions, decision)
                    _append(ledger, {"event": "call_complete", "sequence": call["sequence"],
                                     "call_id": call["call_id"], "response_sha256": raw_sha,
                                     "input_tokens": input_count, "output_tokens": output_count,
                                     "parse_status": parse_status,
                                     "wall_seconds": result.get("wall_seconds")})
                _append(ledger, {"event": "batch_complete", "batch": batch_number,
                                 "snapshot": resource_provider(output_dir)})
        _append(ledger, {"event": "run_complete", "model_call_starts": starts,
                         "input_tokens": input_tokens, "output_tokens": output_tokens,
                         "valid_responses": parsed, "invalid_responses": invalid,
                         "elapsed_seconds": time.monotonic() - run_start})
    except BaseException as error:
        _append(ledger, {"event": "run_stopped", "error_type": type(error).__name__,
                         "reason": str(error), "model_call_starts": starts,
                         "input_tokens": input_tokens, "output_tokens": output_tokens,
                         "valid_responses": parsed, "invalid_responses": invalid,
                         "elapsed_seconds": time.monotonic() - run_start})
        raise
    finally:
        ledger.close()
        monitor.close()
        decisions.close()
        _write_manifest(output_dir)


def _write_manifest(directory: Path):
    entries = []
    for path in sorted(item for item in directory.rglob("*") if item.is_file()
                       and item.name != "SHA256SUMS"):
        entries.append(f"{_sha(path.read_bytes())}  {path.relative_to(directory).as_posix()}")
    data = ("\n".join(entries) + "\n").encode("utf-8")
    with (directory / "SHA256SUMS").open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    (directory / "SHA256SUMS").chmod(0o600)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run only the frozen E2 selector schedule")
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--deny-path", type=Path, action="append", required=True)
    args = parser.parse_args(argv)
    run_e2(args.plan, model_path=args.model, python_path=args.python,
           output_dir=args.output, denied_paths=args.deny_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
