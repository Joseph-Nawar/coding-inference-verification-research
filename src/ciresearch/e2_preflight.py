"""Build the label-blind, private E2 registration from frozen E1 artifacts.

This module reads only the validated E1 technical projection, the 30 completed
development prompts, cached V/D records, and registered D references. It never
opens ``sealed-labels.jsonl`` or computes a correctness endpoint.
"""
from dataclasses import asdict, dataclass
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Mapping, Sequence

from ciresearch.e1_data import chunk_indices
from ciresearch.e1_e2_feasibility import E2EvidenceView
from ciresearch.e2 import (
    ARMS,
    OUTPUT_RESERVE,
    E2Error,
    EligibleTask,
    build_selector_prompt,
    candidate_permutation,
    count_prompt_tokens,
    deterministic_baselines,
    freeze_balanced_sample,
    make_call_seed,
    score_cached_d_panel,
    score_unexecuted_d_panel,
)
from ciresearch.p1 import sha
from ciresearch.sandbox import validate_response
from ciresearch.smoke_data import ARCHIVES
from ciresearch.wire import WireError, pack, read_frame, unpack

SCHEMA = "ciresearch-e2-private-registration.v3"
NAMESPACE = "ciresearch-e2-sample-v1"
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024


class E2PreflightError(ValueError):
    """Frozen E1 artifacts cannot support a faithful label-blind E2 plan."""


@dataclass(frozen=True)
class PreparedTechnicalTask:
    task_index: int
    task_id: str
    benchmark: str
    technical_eligible: bool
    reasons: tuple[str, ...]
    condition_tokens: Mapping[str, int]
    candidate_map: tuple[Mapping, ...]
    prompt_hashes: Mapping[str, str]
    prompts: Mapping[str, str]
    visible_scores: Mapping[str, int]
    diagnostic_scores: Mapping[str, Mapping]
    visible_signatures: Mapping[str, str | None]
    baselines: Mapping[str, object]
    mutation_sensitive: bool
    mutated_case_count: int


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_json(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise E2PreflightError(f"invalid E2 technical artifact: {path.name}") from error


def _read_frames(path: Path):
    try:
        with path.open("rb") as stream:
            frames = []
            for raw in stream:
                frames.append(read_frame(raw))
                if len(frames) > 4097:
                    raise E2PreflightError("cached diagnostic panel exceeds case-count cap")
            return frames
    except (OSError, WireError) as error:
        raise E2PreflightError(f"cached E1 frame is malformed: {path.name}") from error


def _completed_prompts(data_root: Path, split_sha256: str, task_indices: Sequence[int], prompt_hashes):
    """Read task prompts for completed dev indices only; never enumerate confirmation IDs."""
    split_path = data_root / "private-split.json"
    split_bytes = split_path.read_bytes()
    if _sha256_bytes(split_bytes) != split_sha256:
        raise E2PreflightError("private development split commitment mismatch")
    split = json.loads(split_bytes)
    development = {name: split[name]["development"]
                   for name in ("humaneval", "mbpp")}
    if any(len(development[name]) != 20 or len(set(development[name])) != 20
           for name in development):
        raise E2PreflightError("registered development index map is malformed")
    indices = tuple(task_indices)
    if len(indices) != len(set(indices)) or any(type(i) is not int or not 0 <= i < 40 for i in indices):
        raise E2PreflightError("completed E1 task indices are invalid")

    wanted: dict[str, dict[str, int]] = {"humaneval": {}, "mbpp": {}}
    for task_index in indices:
        benchmark = "humaneval" if task_index < 20 else "mbpp"
        local_index = task_index if task_index < 20 else task_index - 20
        wanted[benchmark][development[benchmark][local_index]] = task_index

    records = {}
    for benchmark, (archive_name, expected_sha) in ARCHIVES.items():
        archive = data_root / archive_name
        if archive.stat().st_size > MAX_ARCHIVE_BYTES or _sha256_bytes(archive.read_bytes()) != expected_sha:
            raise E2PreflightError(f"pinned benchmark archive mismatch: {archive_name}")
        keys = tuple(wanted[benchmark])
        pattern = re.compile(rb'"task_id"\s*:\s*"(' + b"|".join(
            re.escape(key.encode("utf-8")) for key in keys) + rb')"')
        found = set()
        with gzip.open(archive, "rb") as stream:
            for raw in stream:
                match = pattern.search(raw)
                if not match:
                    continue
                record = json.loads(raw)
                task_id = record.get("task_id")
                if task_id not in wanted[benchmark] or task_id in found:
                    raise E2PreflightError("unexpected or duplicated completed dev task record")
                task_index = wanted[benchmark][task_id]
                if sha(record["prompt"].encode("utf-8")) != prompt_hashes[task_index]:
                    raise E2PreflightError("completed task prompt differs from its E1 commitment")
                records[task_index] = (benchmark, record)
                found.add(task_id)
                if len(found) == len(keys):
                    break
        if found != set(keys):
            raise E2PreflightError("pinned archive omitted a completed development task")
    if set(records) != set(indices):
        raise E2PreflightError("completed task prompt coverage is incomplete")
    return records


def _response_observations(frames, case_count: int):
    if not frames:
        raise E2PreflightError("cached D candidate panel is empty")
    try:
        init_status = validate_response(frames[0], initializing=True)[0]
    except Exception as error:
        raise E2PreflightError("cached D initialization response is malformed") from error
    if init_status != "ready":
        if len(frames) != 1:
            raise E2PreflightError("failed D initialization unexpectedly has case responses")
        return {"initialization": init_status, "cases": []}
    if len(frames) != case_count + 1:
        raise E2PreflightError("cached D response count differs from the registered panel")
    cases = []
    for frame in frames[1:]:
        try:
            status, value, args_after = validate_response(frame)
        except Exception as error:
            raise E2PreflightError("cached D candidate output is malformed") from error
        if status == "ok":
            cases.append({"execution_status": status, "value": pack(value),
                          "args_after": pack(args_after)})
        else:
            cases.append({"execution_status": status})
    return {"initialization": "ready", "cases": cases}


def _visible_summary(evidence, parse_status: str, case_count: int) -> dict:
    """Normalize cached V evidence without calling an unavailable run incorrect."""
    if type(evidence) is not dict or type(case_count) is not int or case_count <= 0:
        raise E2PreflightError("registered visible panel or evidence is unavailable")
    if parse_status != "ok":
        if (evidence.get("reason") != parse_status or evidence.get("pass") is not False
                or evidence.get("v_count") != 0):
            raise E2PreflightError("candidate parse failure differs from cached V evidence")
        return {"pass_count": 0, "case_count": case_count, "passed": False,
                "status": "candidate_parse_failure"}
    initialization = evidence.get("initialization")
    if initialization in {"exception", "invalid_program"}:
        if (evidence.get("pass") is not False or evidence.get("v_count") != 0
                or evidence.get("details") != []):
            raise E2PreflightError("initialization failure differs from cached V evidence")
        status = "initialization_exception" if initialization == "exception" else "invalid_program"
        return {"pass_count": 0, "case_count": case_count, "passed": False, "status": status}
    details = evidence.get("details")
    count = evidence.get("v_count")
    passed = evidence.get("pass")
    if (initialization != "complete" or type(details) is not list or len(details) != case_count
            or any(type(value) is not bool for value in details)
            or type(count) is not int or count != sum(details)
            or type(passed) is not bool or passed != all(details)):
        raise E2PreflightError("visible evaluation is incomplete or malformed")
    return {"pass_count": count, "case_count": case_count, "passed": passed,
            "status": "complete"}


def _candidate_source(parse_status: str, code_record: dict) -> str:
    """Return the cached extracted source for every registered parse outcome."""
    if (parse_status not in {"ok", "invalid_syntax", "missing_entry", "truncated"}
            or type(code_record) is not dict or code_record.get("parse") != parse_status
            or type(code_record.get("code")) is not str):
        raise E2PreflightError("cached candidate source or parse status is unavailable")
    return code_record["code"]


def _prompt_token_reasons(tokens: dict) -> tuple[str, ...]:
    """Keep absent token counts distinct from prompts that exceed the cap."""
    if set(tokens) != set(ARMS):
        return ("final_prompt_set_incomplete",)
    if any(type(value) is not int or value < 0 for value in tokens.values()):
        return ("final_prompt_token_count_invalid",)
    if any(value + OUTPUT_RESERVE > 8192 for value in tokens.values()):
        return ("final_prompt_exceeds_context_allowance",)
    return ()


def _candidate_paths(view: E2EvidenceView, task_index: int, candidate_id: str):
    root = view.parent_root / "run" if task_index in set(view.original_tasks) else view.continuation_root
    chunk = next(i for i, group in enumerate(chunk_indices()) if task_index in group)
    return root / f"chunk-{chunk:02d}" / candidate_id


def _prepare_task(view: E2EvidenceView, task_index: int, benchmark: str, task: dict,
                  reference_record: dict, calls_by_pair: dict, visible_by_id: dict,
                  tokenizer) -> PreparedTechnicalTask:
    reasons = []
    calls = [calls_by_pair.get((task_index, sample)) for sample in range(4)]
    if any(row is None for row in calls):
        raise E2PreflightError("completed checkpoint lacks a first-four candidate identity")
    if [row["sample"] for row in calls] != list(range(4)):
        raise E2PreflightError("first-four candidate identities are not in registered order")

    displayed_ids = candidate_permutation([row["id"] for row in calls], str(task["task_id"]), NAMESPACE)
    id_to_call = {row["id"]: row for row in calls}
    candidate_map = []
    candidate_rows = []
    visible_rows = []
    visible_scores = {}
    visible_signatures = {}
    source_by_id = {}
    for candidate_id in displayed_ids:
        call = id_to_call[candidate_id]
        path = _candidate_paths(view, task_index, candidate_id)
        code_record = _read_json(path.with_name(path.name + "-code.json"))
        parse_status = call.get("parse")
        if code_record.get("parse") != parse_status:
            reasons.append("generation_parse_record_mismatch")
        try:
            code = _candidate_source(parse_status, code_record)
        except E2PreflightError:
            reasons.append("candidate_source_unavailable")
            code = None
        candidate_rows.append({"candidate_id": candidate_id, "original_sample": call["sample"],
                               "parse_status": parse_status,
                               "code": code})
        candidate_map.append({"display_index": len(candidate_map) + 1,
                              "candidate_id": candidate_id,
                              "original_sample": call["sample"]})
        source_by_id[candidate_id] = (parse_status, code, path)

        evidence = visible_by_id.get(candidate_id, {}).get("evidence", {}).get("base")
        # The caller installs the registered base-panel size on the task record.
        case_count = task.get("_e2_base_case_count")
        try:
            visible_summary = _visible_summary(evidence, parse_status, case_count)
        except E2PreflightError as error:
            reasons.append(f"visible_evidence_unavailable:{type(error).__name__}")
            visible_summary = {"pass_count": 0, "case_count": max(1, case_count or 1),
                               "passed": False, "status": "complete"}
        visible_rows.append(visible_summary)
        visible_scores[candidate_id] = visible_summary["pass_count"]
        signature = evidence.get("signature")
        visible_signatures[candidate_id] = signature if type(signature) is str else None

    ref = reference_record.get("references", {}).get("D")
    expected = ref.get("values") if type(ref) is dict else None
    if type(expected) is not list or not expected:
        reasons.append("registered_D_reference_unavailable")
        expected = []

    common_input_wires = None
    parsed_d_records = {}
    for candidate_id in displayed_ids:
        parse_status, _code, path = source_by_id[candidate_id]
        if parse_status != "ok":
            continue
        request_path = path.parent / (path.name + "-D") / "requests.jsonl"
        response_path = path.parent / (path.name + "-D") / "responses.jsonl"
        if not request_path.is_file() or not response_path.is_file():
            reasons.append("cached_D_candidate_panel_missing")
            continue
        requests = _read_frames(request_path)
        responses = _read_frames(response_path)
        if (not requests or set(requests[0]) != {"code", "entry"}
                or requests[0].get("code") != source_by_id[candidate_id][1]
                or requests[0].get("entry") != task["entry_point"]):
            reasons.append("cached_D_request_header_invalid")
            continue
        case_requests = requests[1:]
        if not case_requests:
            try:
                init = validate_response(responses[0], initializing=True)[0]
            except Exception:
                reasons.append("cached_D_initialization_missing_or_malformed")
                continue
            if init == "ready":
                reasons.append("cached_D_input_panel_missing_or_malformed")
                continue
            parsed_d_records[candidate_id] = (None, responses)
            continue
        if any(set(row) != {"args", "seconds"} for row in case_requests):
            reasons.append("cached_D_input_panel_missing_or_malformed")
            continue
        try:
            for row in case_requests:
                args = unpack(row["args"])
                if type(args) not in (list, tuple) or type(row["seconds"]) not in (int, float):
                    raise WireError("invalid D request shape")
        except (WireError, TypeError):
            reasons.append("cached_D_input_type_unsupported")
            continue
        input_wires = [row["args"] for row in case_requests]
        if common_input_wires is None:
            common_input_wires = input_wires
        elif input_wires != common_input_wires:
            reasons.append("cached_D_candidate_inputs_differ")
            continue
        parsed_d_records[candidate_id] = (input_wires, responses)

    if common_input_wires is None:
        reasons.append("no_cached_D_inputs")
        common_input_wires = []
    if expected and len(expected) != len(common_input_wires):
        reasons.append("D_reference_input_coverage_mismatch")

    diagnostic = None
    comparisons = None
    diagnostic_scores = {}
    if expected and common_input_wires and len(expected) == len(common_input_wires):
        diagnostic = {"inputs": [{"args": wire} for wire in common_input_wires],
                      "candidate_results": []}
        comparisons = []
        for candidate_id in displayed_ids:
            parse_status, _code, _path = source_by_id[candidate_id]
            if parse_status != "ok":
                result = score_unexecuted_d_panel(parse_status, len(expected))
                observed = {"initialization": "candidate_parse_failure", "cases": []}
            elif candidate_id in parsed_d_records:
                input_wires, response_frames = parsed_d_records[candidate_id]
                try:
                    observed = _response_observations(response_frames, len(expected))
                    result = score_cached_d_panel(
                        benchmark, task["entry_point"], task.get("atol", 0), expected,
                        response_frames, common_input_wires if input_wires is None else input_wires)
                except E2Error as error:
                    reasons.append(f"D_comparator_or_wire_invalid:{type(error).__name__}")
                    continue
            else:
                reasons.append("D_candidate_record_unavailable")
                continue
            diagnostic["candidate_results"].append(observed)
            comparisons.append({"cases": result["cases"]})
            diagnostic_scores[candidate_id] = result
        if len(diagnostic["candidate_results"]) != 4 or len(comparisons) != 4:
            reasons.append("D_candidate_coverage_incomplete")
            diagnostic = None
            comparisons = None

    prompts = {}
    tokens = {}
    if diagnostic is not None and comparisons is not None:
        for arm in ARMS:
            try:
                prompts[arm] = build_selector_prompt(
                    arm, task["prompt"], candidate_rows,
                    visible=visible_rows if arm in {"B", "C", "D"} else None,
                    diagnostic=diagnostic if arm in {"C", "D"} else None,
                    expected=expected if arm == "D" else None,
                    comparisons=comparisons if arm == "D" else None)
                tokens[arm] = count_prompt_tokens(tokenizer, prompts[arm], enforce_context=False)
            except E2Error as error:
                reasons.append(f"prompt_{arm}_invalid:{type(error).__name__}")
    reasons.extend(_prompt_token_reasons(tokens))
    tokens = {arm: tokens.get(arm, -1) for arm in ARMS}

    baselines = {}
    if set(diagnostic_scores) == set(displayed_ids):
        baselines = deterministic_baselines(
            [{"candidate_id": row["candidate_id"],
              "original_sample": row["original_sample"]} for row in candidate_rows],
            visible_scores,
            {candidate_id: diagnostic_scores[candidate_id] for candidate_id in displayed_ids},
            visible_signatures)
    else:
        reasons.append("deterministic_D_baseline_unavailable")

    mutation_rows = [case for result in diagnostic_scores.values() for case in result["cases"]]
    mutated_count = sum(case["input_mutated"] is True for case in mutation_rows)
    mutation_sensitive = any(result["mutation_sensitive"] for result in diagnostic_scores.values())
    # Candidate-reported mutation does not alter the registered comparator result.
    # It is retained as a technical-integrity flag for retrospective qualification.
    return PreparedTechnicalTask(
        task_index=task_index,
        task_id=str(task["task_id"]),
        benchmark=benchmark,
        technical_eligible=not reasons,
        reasons=tuple(sorted(set(reasons))),
        condition_tokens=tokens,
        candidate_map=tuple(candidate_map),
        prompt_hashes={arm: _sha256_bytes(prompts[arm].encode("utf-8")) for arm in prompts},
        prompts=prompts,
        visible_scores=visible_scores,
        diagnostic_scores=diagnostic_scores,
        visible_signatures=visible_signatures,
        baselines=baselines,
        mutation_sensitive=mutation_sensitive,
        mutated_case_count=mutated_count,
    )


def prepare_e2(view: E2EvidenceView, *, tokenizer, data_root: Path, private_root: Path,
               namespace: str = NAMESPACE) -> dict:
    """Return a private label-free E2 plan; no scorer labels are accepted by this API."""
    if not isinstance(view, E2EvidenceView):
        raise E2PreflightError("E2 requires the label-free technical evidence projection")
    if tuple(view.checkpoint_chunks) != (0, 1, 2, 3, 4, 5):
        raise E2PreflightError("E2 requires exactly the six validated completed E1 checkpoints")
    if len(view.completed_tasks) != 30 or len(set(view.completed_tasks)) != 30:
        raise E2PreflightError("E2 preparation requires exactly 30 unique checkpointed dev tasks")
    if not set(view.completed_tasks).issubset(set(view.original_tasks) | set(view.continuation_tasks)):
        raise E2PreflightError("completed E2 task set differs from the validated six checkpoints")
    registration = _read_json(view.parent_root / "registration.json")
    repository_root = Path(__file__).resolve().parents[2]
    try:
        protected_roots = {
            "e1_parent": str(view.parent_root.resolve(strict=True)),
            "e1_continuation": str(view.continuation_root.resolve(strict=True)),
            "dataset": str(Path(data_root).resolve(strict=True)),
            "e2_private": str(Path(private_root).resolve(strict=True)),
        }
    except OSError as error:
        raise E2PreflightError("a registered selector protected root is unavailable") from error
    if len(set(protected_roots.values())) != len(protected_roots):
        raise E2PreflightError("selector protected roots must be distinct")
    if namespace != NAMESPACE:
        raise E2PreflightError("E2 hash namespace differs from the prospective amendment")
    refs_path = view.parent_root / "qualified-reference.json"
    refs_bytes = refs_path.read_bytes()
    if _sha256_bytes(refs_bytes) != registration.get("audit_sha256"):
        raise E2PreflightError("registered development reference audit hash mismatch")
    refs_all = json.loads(refs_bytes)
    if type(refs_all) is not list or len(refs_all) != 40:
        raise E2PreflightError("registered development reference audit shape is invalid")
    tasks = _completed_prompts(data_root, registration["split_sha256"],
                               view.completed_tasks, registration["prompt_sha256"])
    calls_by_pair = {(row["task"], row["sample"]): row for row in view.call_records}
    visible_by_id = {row["id"]: row for row in view.visible_records}
    if len(calls_by_pair) != len(view.call_records) or len(visible_by_id) != len(view.visible_records):
        raise E2PreflightError("E1 technical evidence contains duplicate candidate identities")

    prepared = []
    for task_index in sorted(view.completed_tasks):
        benchmark, task = tasks[task_index]
        if benchmark not in {"humaneval", "mbpp"}:
            raise E2PreflightError("unregistered E2 benchmark")
        task = dict(task)
        task["_e2_base_case_count"] = refs_all[task_index].get("panel_sizes", {}).get("base")
        prepared.append(_prepare_task(view, task_index, benchmark, task,
                                      refs_all[task_index], calls_by_pair, visible_by_id, tokenizer))

    eligible = [row for row in prepared if row.technical_eligible]
    eligible_rows = [EligibleTask(row.task_id, row.benchmark, row.condition_tokens) for row in eligible]
    counts = {benchmark: sum(row.benchmark == benchmark for row in eligible)
              for benchmark in ("humaneval", "mbpp")}
    base = {
        "schema": SCHEMA,
        "status": "technical_preflight_complete" if all(count >= 12 for count in counts.values())
                  else "blocked_insufficient_balanced_technical_population",
        "labels_read": False,
        "confirmation_accessed": False,
        "namespace": namespace,
        "protocol_sha256": _sha256_bytes(
            (repository_root / "docs" / "18_E2_PREOUTCOME_INFORMATION_BOUNDARY_AMENDMENT_V4.md").read_bytes()),
        "config_sha256": _sha256_bytes((repository_root / "configs" / "e2-v4.yaml").read_bytes()),
        "parent_registration_sha256": _sha256_bytes((view.parent_root / "registration.json").read_bytes()),
        "model_revision": registration["model_revision"],
        "model_files": registration["model_files"],
        "tokenizer_files": {name: registration["model_files"][name]
                            for name in ("tokenizer.json", "tokenizer_config.json")},
        "runtime_dependency_lock_sha256": _sha256_bytes(
            (Path(__file__).resolve().parents[2] / "configs" / "p0-inference.lock").read_bytes()),
        "worker_protected_roots": protected_roots,
        "model_sampling": {"temperature": 0.7, "top_p": 0.95, "max_new_tokens": 128,
                           "context_limit": 8192, "input_limit": 8064},
        "caps": {"tasks": 24, "model_call_starts": 96, "output_tokens": 12288,
                 "empirical_seconds": 1800, "inference_streams": 1,
                 "minimum_free_disk_gib": 15, "batch_tasks": 4},
        "resource_gate": {
            "fresh_boot_required": True,
            "requires_fresh_boot_after_utc": "2026-11-26T11:45:06Z",
            "requires_closure_of_unnecessary_apps": True,
            "requires_no_stale_research_or_evaluator_processes": True,
            "requires_docker_stopped_when_feasible": True,
            "stop_on_critical_pressure": True,
            "swap_growth_mib": 256,
            "consecutive_high_swap_observations_to_stop": 2,
            "repeat_rebaseline_to_bypass_stop": False,
        },
        "parent_run_ledger_sha256": _sha256_bytes((view.parent_root / "run" / "ledger.jsonl").read_bytes()),
        "continuation_ledger_sha256": _sha256_bytes((view.continuation_root / "ledger.jsonl").read_bytes()),
        "completed_checkpoint_task_count": len(view.completed_tasks),
        "technical_population_counts": counts,
        "task_assessments": [asdict(row) for row in prepared],
        "task_hash_order": {},
        "sample": [],
        "call_schedule": [],
    }
    if not all(count >= 12 for count in counts.values()):
        return base

    # This consumes only label-free, final-prompt technical records.
    scheduled = freeze_balanced_sample(eligible_rows, namespace=namespace, per_benchmark=12)
    prepared_by_id = {row.task_id: row for row in eligible}
    ranked = {}
    for benchmark in ("humaneval", "mbpp"):
        ranked[benchmark] = [row.task_id for row in sorted(
            (row for row in eligible if row.benchmark == benchmark),
            key=lambda row: (hashlib.sha256(
                f"{namespace}\0task-order-v1\0{benchmark}\0{row.task_id}".encode()).digest(), row.task_id))]
    base["task_hash_order"] = ranked
    base["sample"] = [asdict(row) for row in scheduled]
    sequence = 0
    for row in scheduled:
        task = prepared_by_id[row.task_id]
        for arm in row.arm_order:
            seed = make_call_seed(row.task_id, arm, registration["model_revision"], namespace)
            prompt = task.prompts[arm]
            call_id = _sha256_bytes(
                f"{namespace}\0call-v1\0{row.task_id}\0{arm}\0{seed}\0{task.prompt_hashes[arm]}".encode())
            base["call_schedule"].append({
                "sequence": sequence,
                "call_id": call_id,
                "task_id": row.task_id,
                "benchmark": row.benchmark,
                "batch": row.batch,
                "batch_position": row.batch_position,
                "arm": arm,
                "seed": seed,
                "candidate_map": list(task.candidate_map),
                "prompt_sha256": task.prompt_hashes[arm],
                "input_tokens": dict(row.condition_tokens)[arm],
                "max_new_tokens": 128,
                "prompt": prompt,
            })
            sequence += 1
    return base


def write_private_registration(path: Path, registration: dict) -> str:
    """Create a new private registration file; never overwrite existing evidence."""
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    encoded = (json.dumps(registration, ensure_ascii=True, allow_nan=False,
                          separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
    try:
        with path.open("xb") as stream:
            stream.write(encoded)
    except FileExistsError as error:
        raise E2PreflightError("refusing to overwrite an existing E2 private registration") from error
    path.chmod(0o600)
    return _sha256_bytes(encoded)


def load_evidence_view(path: Path) -> E2EvidenceView:
    """Load an explicit technical projection; the schema has no label field."""
    value = _read_json(path)
    required = {"schema", "parent_root", "continuation_root", "original_tasks",
                "continuation_tasks", "completed_tasks", "checkpoint_chunks",
                "call_records", "visible_records"}
    if type(value) is not dict or set(value) != required or value.get("schema") != "ciresearch-e2-technical-view.v1":
        raise E2PreflightError("serialized E2 technical view has unexpected fields")
    return E2EvidenceView(
        parent_root=Path(value["parent_root"]),
        continuation_root=Path(value["continuation_root"]),
        original_tasks=tuple(value["original_tasks"]),
        continuation_tasks=tuple(value["continuation_tasks"]),
        completed_tasks=tuple(value["completed_tasks"]),
        checkpoint_chunks=tuple(value["checkpoint_chunks"]),
        call_records=tuple(value["call_records"]),
        visible_records=tuple(value["visible_records"]),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Prepare a label-blind private E2 registration")
    parser.add_argument("--technical-view", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    view = load_evidence_view(args.technical_view)
    registration = _read_json(view.parent_root / "registration.json")
    expected_model_files = registration.get("model_files")
    if type(expected_model_files) is not dict:
        raise E2PreflightError("E1 registration lacks the pinned model file manifest")
    from ciresearch.p1 import verify_model
    verify_model(args.model_root, expected_model_files)
    try:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(
            str(args.model_root), local_files_only=True, trust_remote_code=False)
    except Exception as error:
        raise E2PreflightError("pinned local tokenizer failed to load offline") from error
    plan = prepare_e2(view, tokenizer=tokenizer, data_root=args.data_root,
                      private_root=args.output.parent)
    digest = write_private_registration(args.output, plan)
    summary = {
        "status": plan["status"],
        "registration_sha256": digest,
        "labels_read": plan["labels_read"],
        "confirmation_accessed": plan["confirmation_accessed"],
        "completed_checkpoint_task_count": plan["completed_checkpoint_task_count"],
        "technical_population_counts": plan["technical_population_counts"],
        "sampled_task_count": len(plan["sample"]),
        "model_call_count": len(plan["call_schedule"]),
        "maximum_prompt_tokens": max((call["input_tokens"] for call in plan["call_schedule"]), default=None),
        "max_new_tokens": 128,
    }
    print(json.dumps(summary, sort_keys=True))
    return 0 if plan["status"] == "technical_preflight_complete" else 2


if __name__ == "__main__":
    sys.exit(main())
