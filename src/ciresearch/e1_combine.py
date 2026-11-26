"""Read-only identity and checkpoint validation for the E1 parent and continuation."""
from dataclasses import dataclass
import json
import math
from pathlib import Path
import re

from ciresearch.e1_continuation import (
    COMPLETED_CHUNKS,
    CONTINUATION_CHUNKS,
    ContinuationError,
    ParentRun,
    _hash_tree,
    _sha,
    make_continuation_registration,
    parent_validation_pins,
    validate_parent,
    verify_segment_manifest,
)
from ciresearch.e1_data import chunk_indices


class CombinedPopulationError(ValueError):
    """The two E1 evidence segments do not cover the registered population exactly."""


@dataclass(frozen=True)
class CombinedRun:
    parent_root: Path
    continuation_root: Path
    task_ids: tuple
    candidate_ids: tuple
    chunks: tuple
    parent_ledger: tuple
    continuation_ledger: tuple
    visible_records: tuple
    decision_records: tuple
    label_records: tuple
    call_records: tuple
    generation_records: tuple
    segment_manifest_sha256: str


def _jsonl(path):
    try:
        return [json.loads(line) for line in path.read_text().splitlines()]
    except (OSError, json.JSONDecodeError) as error:
        raise CombinedPopulationError(f"invalid evidence file: {path.name}") from error


def _read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise CombinedPopulationError(f"invalid registration: {path.name}") from error


def _identity(row, kind):
    task, sample, candidate = row.get("task"), row.get("sample"), row.get("id")
    if type(task) is not int or type(sample) is not int or not 0 <= task < 40:
        raise CombinedPopulationError(f"{kind} contains an unexpected sample identity")
    if not 0 <= sample < 8 or not isinstance(candidate, str) or len(candidate) != 64:
        raise CombinedPopulationError(f"{kind} contains an unexpected sample identity")
    try:
        int(candidate, 16)
    except ValueError as error:
        raise CombinedPopulationError(f"{kind} contains an unexpected sample identity") from error
    return task, sample, candidate


def _records_by_identity(rows, expected, kind):
    found = {}
    order = []
    for row in rows:
        task, sample, candidate = _identity(row, kind)
        key = (task, sample)
        if key in found:
            raise CombinedPopulationError(f"duplicate {kind} candidate identity")
        found[key] = candidate
        order.append(key)
    if found != expected:
        raise CombinedPopulationError(f"{kind} identity coverage differs from the registered population")
    return order


def _registered_population(parent):
    registration = parent.registration
    groups = list(chunk_indices())
    ordered_pairs = [(task, sample) for group in groups for task in group for sample in range(8)]
    expected = {}
    for task, sample in ordered_pairs:
        seed = registration["seeds"][task][sample]
        candidate = _sha(f'{registration["run_id"]}|{task}|{sample}|{seed}'.encode())
        expected[(task, sample)] = candidate
    return groups, ordered_pairs, expected


def _check_panel_shapes(visible_rows, decision_rows, label_rows, expected, groups):
    if len(visible_rows) != len(expected):
        raise CombinedPopulationError("visible identity coverage is incomplete")
    if len(label_rows) != len(expected):
        raise CombinedPopulationError("sealed label coverage is incomplete")
    vis_order = _records_by_identity(visible_rows, expected, "visible evidence")
    label_order = _records_by_identity(label_rows, expected, "sealed label")
    if vis_order != list(expected) or label_order != list(expected):
        raise CombinedPopulationError("candidate evidence rows are out of registered task/sample order")
    for row in visible_rows:
        evidence = row.get("evidence")
        base = evidence.get("base") if isinstance(evidence, dict) else None
        if not isinstance(base, dict) or "pass" not in base or "v_count" not in base or "signature" not in base:
            raise CombinedPopulationError("visible evidence has an unsupported representation")
        if base["pass"] is not None and type(base["pass"]) is not bool:
            raise CombinedPopulationError("visible pass result is not a typed boolean or unavailable")
        if base["v_count"] is not None and (type(base["v_count"]) is not int or base["v_count"] < 0):
            raise CombinedPopulationError("visible pass count is malformed")
        if base["signature"] is not None and not isinstance(base["signature"], str):
            raise CombinedPopulationError("visible signature is malformed")
    for row in label_rows:
        for name in ("y", "h", "qualified_y"):
            value = row.get(name)
            if value is not None and type(value) is not bool:
                raise CombinedPopulationError(f"sealed {name} label is malformed")
        outcomes = row.get("outcomes")
        if not isinstance(outcomes, dict) or not isinstance(outcomes.get("plus"), dict):
            raise CombinedPopulationError("sealed label omits official plus-panel evidence")

    task_order = [task for group in groups for task in group]
    by_task = {}
    for row in decision_rows:
        task = row.get("task")
        if type(task) is not int or task not in set(task_order) or task in by_task:
            raise CombinedPopulationError("selection decision task identities are duplicated or unexpected")
        by_task[task] = row.get("decisions")
    if list(by_task) != task_order:
        raise CombinedPopulationError("selection decision identity coverage differs from registered tasks")
    for decision in by_task.values():
        if not isinstance(decision, dict) or set(decision) != {"1", "2", "4", "8"}:
            raise CombinedPopulationError("selection decisions omit a registered pool size")
        for key, selectors in decision.items():
            k = int(key)
            if (not isinstance(selectors, dict)
                    or set(selectors) != {"pass_count", "consensus"}):
                raise CombinedPopulationError("selection decision is malformed")
            for selected in selectors.values():
                if selected is not None and (type(selected) is not int or not 0 <= selected < k):
                    raise CombinedPopulationError("selection decision points outside its candidate prefix")


def _event_sequence(ledger, chunk, *, continuation):
    if continuation:
        decision_positions = [i for i, row in enumerate(ledger)
                              if row.get("chunk") == chunk and row.get("event") == "chunk_decisions_frozen"]
        label_positions = [i for i, row in enumerate(ledger)
                           if row.get("chunk") == chunk and row.get("event") == "chunk_labels_joined"]
        if decision_positions and label_positions and decision_positions[0] > label_positions[0]:
            raise CombinedPopulationError("labels were joined before visible decisions were frozen")
    relevant = [row["event"] for row in ledger if row.get("chunk") == chunk and row.get("event") in {
        "chunk_start", "chunk_bank_frozen", "chunk_decisions_frozen", "chunk_labels_joined", "chunk_checkpoint"
    }]
    if continuation:
        sequence = ["chunk_start", "chunk_bank_frozen", "chunk_decisions_frozen",
                    "chunk_labels_joined", "chunk_checkpoint"]
    else:
        sequence = ["chunk_start", "chunk_bank_frozen", "chunk_decisions_frozen", "chunk_checkpoint"]
    if relevant != sequence:
        raise CombinedPopulationError(f"chunk {chunk} checkpoint or information-boundary order is invalid")
    positions = {name: next(i for i, row in enumerate(ledger)
                            if row.get("chunk") == chunk and row.get("event") == name)
                 for name in sequence}
    if continuation and positions["chunk_decisions_frozen"] > positions["chunk_labels_joined"]:
        raise CombinedPopulationError("labels were joined before visible decisions were frozen")
    if not continuation:
        # Historical parent ledger predates an explicit label-join event; its pinned runner
        # emitted sealed-label rows only after chunk_decisions_frozen.
        if positions["chunk_decisions_frozen"] > positions["chunk_checkpoint"]:
            raise CombinedPopulationError("parent visible decisions were not frozen before its checkpoint")
    return positions


def _check_segment_ledger(ledger, registration, parent, expected, ordered_pairs):
    if not ledger or ledger[0].get("event") != "continuation_start":
        raise CombinedPopulationError("continuation ledger does not start with its parent binding")
    start = ledger[0]
    reg_hash = _sha((registration["_root"] / "continuation-registration.json").read_bytes())
    if (start.get("parent_ledger_sha256") != parent.ledger_sha256
            or start.get("registration_sha256") != reg_hash
            or start.get("starting_calls") != parent.completed_calls
            or start.get("starting_tokens") != parent.output_tokens
            or start.get("starting_input_tokens") != parent.input_tokens
            or start.get("starting_tasks") != len(parent.completed_tasks)
            or start.get("starting_elapsed_seconds") != parent.elapsed_seconds):
        raise CombinedPopulationError("continuation ledger is not bound to the stopped parent and budgets")
    if start.get("environment") != registration.get("resource_baseline"):
        raise CombinedPopulationError("continuation resource baseline changed after registration")
    if not ledger or ledger[-1].get("event") != "global_freeze":
        raise CombinedPopulationError("continuation is not a complete four-chunk freeze")

    groups = list(chunk_indices())
    segment_pairs = [(task, sample) for group in groups[4:] for task in group for sample in range(8)]
    segment_expected = {key: expected[key] for key in segment_pairs}
    starts = [row for row in ledger if row.get("event") == "call_started"]
    calls = [row for row in ledger if row.get("event") == "call_complete"]
    for rows, name in ((starts, "started"), (calls, "completed")):
        identities = [_identity(row, f"{name} call") for row in rows]
        keys = [(task, sample) for task, sample, _ in identities]
        if len(keys) != len(set(keys)):
            raise CombinedPopulationError(f"duplicate continuation {name} call candidate identity")
        if identities != [(task, sample, segment_expected[(task, sample)]) for task, sample in segment_pairs]:
            raise CombinedPopulationError(f"continuation {name} call identity coverage or order is invalid")
    for row in calls:
        if (type(row.get("tokens")) is not int or not 1 <= row["tokens"] <= 768
                or type(row.get("input_tokens")) is not int or row["input_tokens"] < 0):
            raise CombinedPopulationError("continuation call token count is invalid")

    checkpoints = [row for row in ledger if row.get("event") == "chunk_checkpoint"]
    if [row.get("chunk") for row in checkpoints] != list(CONTINUATION_CHUNKS):
        raise CombinedPopulationError("continuation checkpoints do not cover chunks 4–7 in order")
    for offset, chunk in enumerate(CONTINUATION_CHUNKS, start=1):
        positions = _event_sequence(ledger, chunk, continuation=True)
        group = groups[chunk]
        before = positions["chunk_start"]
        frozen = positions["chunk_bank_frozen"]
        if any(not before < i < frozen for i, row in enumerate(ledger)
               if row.get("event") in {"call_started", "call_complete"}
               and row.get("task") in group):
            raise CombinedPopulationError("candidate calls did not finish before the chunk bank froze")
        checkpoint = checkpoints[offset - 1]
        if checkpoint.get("completed_tasks") != 20 + 5 * offset:
            raise CombinedPopulationError("continuation checkpoint task counter is not cumulative")
        for event in ("chunk_start", "chunk_checkpoint"):
            row = next(r for r in ledger if r.get("chunk") == chunk and r.get("event") == event)
            environment = row.get("environment", {})
            if environment.get("container_ids") or environment.get("active_models"):
                raise CombinedPopulationError("continuation checkpoint records a live worker or runner")
        artifact_hash = _hash_tree(registration["_root"] / f"chunk-{chunk:02d}")
        if checkpoint.get("chunk_artifact_sha256") != artifact_hash:
            raise CombinedPopulationError("continuation chunk artifact hash differs from checkpoint")

    terminal = ledger[-1]
    segment_tokens = sum(row["tokens"] for row in calls)
    segment_input = sum(row.get("input_tokens", 0) for row in calls)
    elapsed = terminal.get("elapsed_seconds")
    segment_elapsed = terminal.get("segment_elapsed_seconds")
    counters = (terminal.get("calls"), terminal.get("segment_calls"), terminal.get("tokens"),
                terminal.get("input_tokens"), terminal.get("segment_tokens"),
                terminal.get("segment_input_tokens"), terminal.get("tasks"), terminal.get("segment_tasks"))
    if (any(type(value) is not int for value in counters)
            or not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed)
            or not isinstance(segment_elapsed, (int, float)) or not math.isfinite(segment_elapsed)
            or terminal.get("calls") != 320 or terminal.get("segment_calls") != 160
            or terminal.get("tokens") != parent.output_tokens + segment_tokens
            or terminal.get("input_tokens") != parent.input_tokens + segment_input
            or terminal.get("segment_tokens") != segment_tokens
            or terminal.get("segment_input_tokens") != segment_input
            or terminal.get("tasks") != 40 or terminal.get("segment_tasks") != 20
            or not 0 <= segment_elapsed <= parent.remaining_seconds
            or not parent.elapsed_seconds <= elapsed <= 3600
            or abs(terminal.get("elapsed_seconds", 0)
                   - (parent.elapsed_seconds + segment_elapsed)) > 1e-6):
        raise CombinedPopulationError("continuation final counters exceed or differ from cumulative E1 caps")
    return starts, calls


def validate_combined_population(parent: ParentRun, continuation_root: Path) -> CombinedRun:
    """Validate a complete E1 population without modifying either evidence segment."""
    try:
        current_parent = validate_parent(
            parent.root, parent.ledger_sha256,
            expected_manifest_sha256=parent.manifest_sha256,
            expected_registration_sha256=_sha((parent.root / "registration.json").read_bytes()),
        )
        manifest_hash = verify_segment_manifest(continuation_root)
    except (ContinuationError, OSError) as error:
        raise CombinedPopulationError(str(error)) from error
    if (current_parent.completed_chunks != parent.completed_chunks
            or current_parent.completed_calls != parent.completed_calls
            or current_parent.remaining_chunks != parent.remaining_chunks):
        raise CombinedPopulationError("parent evidence changed after initial validation")
    root = Path(continuation_root).resolve()
    registration = _read_json(root / "continuation-registration.json")
    registration["_root"] = root
    expected_registration = make_continuation_registration(parent, registration.get("resource_baseline"))
    if (registration.get("schema") != "ciresearch.e1-continuation.v1"
            or registration.get("parent_ledger_sha256") != parent.ledger_sha256
            or registration.get("parent_manifest_sha256") != parent.manifest_sha256
            or registration.get("parent_registration_sha256")
            != _sha((parent.root / "registration.json").read_bytes())
            or registration.get("parent_reference_build_sha256") != parent.reference_build_sha256
            or registration.get("parent_run_id") != parent.registration["run_id"]
            or registration.get("source_bindings") != expected_registration["source_bindings"]
            or registration.get("chunks") != list(CONTINUATION_CHUNKS)
            or registration.get("completed_chunks") != list(COMPLETED_CHUNKS)
            or registration.get("caps") != expected_registration["caps"]
            or registration.get("completed_output_tokens_before") != parent.output_tokens
            or registration.get("elapsed_seconds_before") != parent.elapsed_seconds
            or not re.fullmatch(r"[0-9a-f]{64}", registration.get("continuation_source_tree_sha256", ""))):
        raise CombinedPopulationError("continuation registration does not match the accepted parent")
    groups, ordered_pairs, expected = _registered_population(parent)
    expected_task_order = [task for group in groups[4:] for task in group]
    if registration.get("task_ids") != expected_task_order:
        raise CombinedPopulationError("continuation task identity coverage differs from the registered schedule")
    expected_segment_candidates = [
        {"task": task, "sample": sample, "id": expected[(task, sample)]}
        for task in expected_task_order for sample in range(8)
    ]
    if registration.get("expected_candidates") != expected_segment_candidates:
        raise CombinedPopulationError("continuation candidate identities differ from original seeds")
    if registration.get("completed_calls_before") != parent.completed_calls:
        raise CombinedPopulationError("continuation registration resets or misstates the cumulative call count")

    parent_root = parent.root
    parent_ledger = _jsonl(parent_root / "run" / "ledger.jsonl")
    segment_ledger = _jsonl(root / "ledger.jsonl")
    parent_visible = _jsonl(parent_root / "run" / "visible.jsonl")
    segment_visible = _jsonl(root / "visible.jsonl")
    parent_decisions = _jsonl(parent_root / "run" / "decisions.jsonl")
    segment_decisions = _jsonl(root / "decisions.jsonl")
    parent_labels = _jsonl(parent_root / "run" / "sealed-labels.jsonl")
    segment_labels = _jsonl(root / "sealed-labels.jsonl")
    _check_panel_shapes(parent_visible, parent_decisions, parent_labels,
                        {key: value for key, value in expected.items() if key[0] in parent.completed_tasks},
                        groups[:4])
    _check_panel_shapes(segment_visible, segment_decisions, segment_labels,
                        {key: value for key, value in expected.items() if key[0] in expected_task_order},
                        groups[4:])

    parent_call_rows = [row for row in parent_ledger if row.get("event") == "call_complete"]
    parent_started = [row for row in parent_ledger if row.get("event") == "call_started"]
    for rows, name in ((parent_started, "parent started"), (parent_call_rows, "parent completed")):
        observed = [_identity(row, name) for row in rows]
        expected_parent_pairs = [(task, sample) for group in groups[:4] for task in group for sample in range(8)]
        if observed != [(task, sample, expected[(task, sample)]) for task, sample in expected_parent_pairs]:
            raise CombinedPopulationError(f"{name} call identity coverage or order differs from registration")
    for chunk in COMPLETED_CHUNKS:
        _event_sequence(parent_ledger, chunk, continuation=False)

    segment_registration = dict(registration)
    segment_registration["_root"] = root
    segment_started, segment_calls = _check_segment_ledger(
        segment_ledger, segment_registration, parent, expected, ordered_pairs)
    _ = segment_started

    all_visible = parent_visible + segment_visible
    all_decisions = parent_decisions + segment_decisions
    all_labels = parent_labels + segment_labels
    _check_panel_shapes(all_visible, all_decisions, all_labels, expected, groups)
    all_call_rows = parent_call_rows + segment_calls
    all_started = parent_started + segment_started
    if (len(all_call_rows) != 320 or len(all_started) != 320
            or len({row["id"] for row in all_call_rows}) != 320
            or len({row["id"] for row in all_started}) != 320):
        raise CombinedPopulationError("combined identity coverage is not exactly 320 unique candidates")

    generation_records = []
    for root_path, rows in ((parent_root / "run", parent_call_rows), (root, segment_calls)):
        raw_files = {path.stem: path for path in root_path.glob("chunk-*/*.json")}
        for row in rows:
            candidate = row["id"]
            raw_path = raw_files.get(candidate)
            code_path = raw_files.get(candidate + "-code")
            if raw_path is None or code_path is None:
                raise CombinedPopulationError("a completed candidate lacks its raw generation or extracted code")
            raw = _read_json(raw_path)
            code_record = _read_json(code_path)
            code = code_record.get("code")
            if (not isinstance(code, str) or code_record.get("parse") != row.get("parse")
                    or _sha(code.encode()) != row.get("code_hash")):
                raise CombinedPopulationError("extracted candidate code differs from its ledger hash")
            if (raw.get("status") != "ok" or raw.get("output_tokens") != row.get("tokens")
                    or raw.get("input_tokens") != row.get("input_tokens")):
                raise CombinedPopulationError("raw generation counters differ from the candidate ledger")
            generation_records.append(raw)

    return CombinedRun(
        parent_root=parent_root,
        continuation_root=root,
        task_ids=tuple(range(40)),
        candidate_ids=tuple(expected[key] for key in ordered_pairs),
        chunks=tuple(range(8)),
        parent_ledger=tuple(parent_ledger),
        continuation_ledger=tuple(segment_ledger),
        visible_records=tuple(all_visible),
        decision_records=tuple(all_decisions),
        label_records=tuple(all_labels),
        call_records=tuple(all_call_rows),
        generation_records=tuple(generation_records),
        segment_manifest_sha256=manifest_hash,
    )


def run_records(combined: CombinedRun):
    """Build an in-memory read-only analysis view, preserving each source ledger."""
    ledger = list(combined.parent_ledger) + list(combined.continuation_ledger)
    started = [row for row in ledger if row.get("event") == "call_started"]
    return (ledger, list(combined.visible_records), list(combined.decision_records),
            list(combined.label_records), list(combined.call_records), started,
            list(combined.generation_records))


def analyze_segments(runs):
    """Strictly validate and analyze the original parent, continuation, and combined view."""
    if len(runs) != 2:
        raise CombinedPopulationError("expected exactly the original parent and one continuation segment")
    from ciresearch.e1_analysis import analyze, analyze_records
    parent_root, continuation_root = map(Path, runs)
    try:
        pins = parent_validation_pins()
        parent = validate_parent(
            parent_root, pins["ledger_sha256"],
            expected_manifest_sha256=pins["manifest_sha256"],
            expected_registration_sha256=pins["registration_sha256"],
            expected_checker_sha256=pins["checker_sha256"],
            expected_reference_build_sha256=pins["reference_build_sha256"],
        )
        combined = validate_combined_population(parent, continuation_root)
    except ContinuationError as error:
        raise CombinedPopulationError(str(error)) from error
    parent_summary = analyze(parent_root / "run")
    continuation_summary = analyze(continuation_root)
    continuation_summary["wall_seconds"] = continuation_summary["segment_wall_seconds"]
    continuation_summary["cumulative_wall_seconds"] = continuation_summary["wall_seconds"] + parent.elapsed_seconds
    combined_records = run_records(combined)
    combined_summary = analyze_records(*combined_records)
    combined_summary["analysis_scope"] = "validated 40-task registered population"
    combined_summary["separate_segment_manifest_sha256"] = combined.segment_manifest_sha256
    return {
        "population_validation": {"task_count": len(combined.task_ids),
                                  "candidate_count": len(combined.candidate_ids),
                                  "chunks": list(combined.chunks),
                                  "parent_ledger_sha256": parent.ledger_sha256,
                                  "parent_manifest_sha256": parent.manifest_sha256,
                                  "continuation_manifest_sha256": combined.segment_manifest_sha256},
        "partial_parent": parent_summary,
        "continuation_segment": continuation_summary,
        "combined": combined_summary,
    }
