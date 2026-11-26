"""Read-only validation of the six complete checkpoints in a stopped E1 run.

This module is deliberately separate from ``e1_combine``: a stopped segment is
not a complete E1 population, and this path never changes that contract.
"""
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from types import MappingProxyType

from ciresearch.e1_combine import (
    _check_panel_shapes,
    _event_sequence,
    _hash_tree,
    _identity,
    _read_json,
    _jsonl as _read_jsonl,
    _registered_population,
)
from ciresearch.e1_continuation import (
    COMPLETED_CHUNKS,
    CONTINUATION_CHUNKS,
    ContinuationError,
    make_continuation_registration,
    validate_parent,
    verify_segment_manifest,
)
from ciresearch.e1_data import chunk_indices


class InterimPopulationError(ValueError):
    """The stopped evidence does not support the registered interim view."""


def freeze_records(value):
    """Recursively freeze JSON-compatible records for analytical handoff."""
    if isinstance(value, dict):
        return MappingProxyType({key: freeze_records(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze_records(item) for item in value)
    return value


def records_for_tasks(records, task_ids):
    """Copy only records whose task belongs to a validated checkpoint set."""
    allowed = frozenset(task_ids)
    return tuple(row for row in records if row.get("task") in allowed)


def verify_checkpoint_artifact(recorded_sha256, actual_sha256):
    if (not isinstance(recorded_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", recorded_sha256)
            or recorded_sha256 != actual_sha256):
        raise InterimPopulationError("checkpoint artifact hash differs from its ledger commitment")


def validate_identity_rows(rows, expected, name):
    """Require identity rows to match the exact registered sequence and IDs."""
    observed = []
    seen = set()
    for row in rows:
        task, sample, candidate_id = _identity(row, name)
        key = (task, sample)
        if key in seen:
            raise InterimPopulationError(f"duplicate {name} candidate identity")
        seen.add(key)
        observed.append((key, candidate_id))
    if observed != list(expected.items()):
        raise InterimPopulationError(f"{name} identity coverage or order differs from registration")


def validate_chunk_events(ledger, chunk, *, complete, continuation, task_ids=()):
    """Validate one checkpoint's freeze chronology, or a start-only partial chunk."""
    allowed = {
        "chunk_start", "chunk_bank_frozen", "chunk_decisions_frozen",
        "chunk_labels_joined", "chunk_checkpoint",
    }
    events = [row.get("event") for row in ledger
              if row.get("chunk") == chunk and row.get("event") in allowed]
    if not complete:
        if events != ["chunk_start"]:
            raise InterimPopulationError("partial chunk contains a freeze, decision, label, or checkpoint event")
        return
    expected = ["chunk_start", "chunk_bank_frozen", "chunk_decisions_frozen"]
    if continuation:
        expected.append("chunk_labels_joined")
    expected.append("chunk_checkpoint")
    if events != expected:
        raise InterimPopulationError(f"chunk {chunk} checkpoint event sequence is incomplete or out of order")
    positions = {event: next(i for i, row in enumerate(ledger)
                            if row.get("chunk") == chunk and row.get("event") == event)
                 for event in expected}
    if continuation and positions["chunk_decisions_frozen"] > positions["chunk_labels_joined"]:
        raise InterimPopulationError("visible decisions must freeze before labels are joined")
    start = positions["chunk_start"]
    bank = positions["chunk_bank_frozen"]
    task_scope = set(task_ids)
    for index, row in enumerate(ledger):
        belongs = row.get("chunk") == chunk or row.get("task") in task_scope
        if belongs and row.get("event") in {"call_started", "call_complete"}:
            if not start < index < bank:
                raise InterimPopulationError("candidate call occurred outside the unfrozen bank interval")


@dataclass(frozen=True)
class InterimView:
    """Deep-frozen records from only six complete, validated checkpoints."""

    parent_root: Path
    continuation_root: Path
    checkpoint_chunks: tuple
    original_tasks: tuple
    continuation_tasks: tuple
    completed_tasks: tuple
    parent_ledger: tuple
    continuation_ledger: tuple
    visible_records: tuple
    decision_records: tuple
    label_records: tuple
    call_records: tuple
    started_records: tuple
    generation_records: tuple
    segment_manifest_sha256: str
    generation_only_outputs: int
    interrupted_started_calls: int
    unstarted_registered_calls: int
    parent_output_tokens: int
    continuation_output_tokens: int
    cumulative_output_tokens: int
    parent_elapsed_seconds: float
    continuation_elapsed_seconds: float
    cumulative_elapsed_seconds: float


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _expected_registration(parent, registration, root):
    registration = dict(registration)
    registration["_root"] = root
    baseline = registration.get("resource_baseline")
    try:
        expected = make_continuation_registration(parent, baseline)
    except (ContinuationError, TypeError) as error:
        raise InterimPopulationError("continuation registration has an invalid resource baseline") from error
    if (registration.get("schema") != "ciresearch.e1-continuation.v1"
            or registration.get("segment_id") != "E1-continuation-01"
            or registration.get("parent_ledger_sha256") != parent.ledger_sha256
            or registration.get("parent_manifest_sha256") != parent.manifest_sha256
            or registration.get("parent_registration_sha256")
            != _sha((parent.root / "registration.json").read_bytes())
            or registration.get("parent_reference_build_sha256") != parent.reference_build_sha256
            or registration.get("parent_run_id") != parent.registration["run_id"]
            or registration.get("source_bindings") != expected["source_bindings"]
            or registration.get("chunks") != list(CONTINUATION_CHUNKS)
            or registration.get("completed_chunks") != list(parent.completed_chunks)
            or registration.get("boundary_only_chunks") != list(parent.boundary_only_chunks)
            or registration.get("caps") != expected["caps"]
            or registration.get("completed_calls_before") != parent.completed_calls
            or registration.get("completed_output_tokens_before") != parent.output_tokens
            or registration.get("elapsed_seconds_before") != parent.elapsed_seconds
            or not re.fullmatch(r"[0-9a-f]{64}", registration.get("continuation_source_tree_sha256", ""))):
        raise InterimPopulationError("continuation registration is not bound to the validated parent")
    return registration


def _check_parent_calls(parent, ledger, expected, groups):
    starts = [row for row in ledger if row.get("event") == "call_started"]
    completed = [row for row in ledger if row.get("event") == "call_complete"]
    task_order = [task for group in groups[:4] for task in group]
    pairs = [(task, sample) for task in task_order for sample in range(8)]
    registered = {key: expected[key] for key in pairs}
    validate_identity_rows(starts, registered, "parent started call")
    validate_identity_rows(completed, registered, "parent completed call")
    for chunk in COMPLETED_CHUNKS:
        _event_sequence(ledger, chunk, continuation=False)
    _validate_generation_files(parent.root / "run", completed)
    return starts, completed


def _validate_generation_files(run_root, calls, *, all_calls=None):
    raw_files = {path.stem: path for path in run_root.glob("chunk-*/*.json")}
    expected_ids = {row["id"] for row in (all_calls if all_calls is not None else calls)}
    observed_raw = {stem for stem in raw_files if re.fullmatch(r"[0-9a-f]{64}", stem)}
    observed_code = {stem[:-5] for stem in raw_files
                     if re.fullmatch(r"[0-9a-f]{64}-code", stem)}
    if observed_raw != expected_ids or observed_code != expected_ids:
        raise InterimPopulationError("candidate artifact identities differ from completed calls")
    records = []
    for row in calls:
        raw_path = raw_files.get(row["id"])
        code_path = raw_files.get(row["id"] + "-code")
        if raw_path is None or code_path is None:
            raise InterimPopulationError("completed candidate lacks its manifested generation artifacts")
        raw = _read_json(raw_path)
        code_record = _read_json(code_path)
        code = code_record.get("code")
        if (not isinstance(code, str) or code_record.get("parse") != row.get("parse")
                or _sha(code.encode()) != row.get("code_hash")
                or raw.get("status") != "ok"
                or raw.get("output_tokens") != row.get("tokens")
                or raw.get("input_tokens") != row.get("input_tokens")):
            raise InterimPopulationError("candidate generation artifacts differ from their ledger record")
        records.append(raw)
    return records


def _validate_resource_events(ledger, registration, parent, started, calls, checkpoints):
    if not ledger or ledger[0].get("event") != "continuation_start" or ledger[-1].get("event") != "stopped":
        raise InterimPopulationError("continuation ledger is not the registered stopped segment")
    start = ledger[0]
    registration_sha = _sha((Path(registration["_root"]) / "continuation-registration.json").read_bytes())
    if (start.get("parent_ledger_sha256") != parent.ledger_sha256
            or start.get("registration_sha256") != registration_sha
            or start.get("starting_calls") != parent.completed_calls
            or start.get("starting_tokens") != parent.output_tokens
            or start.get("starting_input_tokens") != parent.input_tokens
            or start.get("starting_tasks") != len(parent.completed_tasks)
            or start.get("starting_elapsed_seconds") != parent.elapsed_seconds
            or start.get("environment") != registration.get("resource_baseline")):
        raise InterimPopulationError("continuation start counters or parent binding differ from registration")

    terminal = ledger[-1]
    segment_tokens = sum(row.get("tokens", 0) for row in calls)
    segment_input = sum(row.get("input_tokens", 0) for row in calls)
    segment_elapsed = terminal.get("segment_elapsed_seconds")
    elapsed = terminal.get("elapsed_seconds")
    numeric = (segment_elapsed, elapsed)
    if (any(type(value) not in (int, float) or not math.isfinite(value) for value in numeric)
            or terminal.get("calls") != parent.completed_calls + len(started)
            or terminal.get("segment_calls") != len(started)
            or terminal.get("tokens") != parent.output_tokens + segment_tokens
            or terminal.get("input_tokens") != parent.input_tokens + segment_input
            or terminal.get("segment_tokens") != segment_tokens
            or terminal.get("segment_input_tokens") != segment_input
            or terminal.get("tasks") != len(parent.completed_tasks) + 10
            or terminal.get("segment_tasks") != 10
            or abs(elapsed - (parent.elapsed_seconds + segment_elapsed)) > 1e-6
            or elapsed > 3600 or segment_elapsed > parent.remaining_seconds
            or terminal.get("tokens") > 245760
            or segment_tokens > registration["caps"]["effective_max_output_tokens"]):
        raise InterimPopulationError("stopped continuation counters do not reconcile with registered caps")
    if [row.get("chunk") for row in checkpoints] != [4, 5]:
        raise InterimPopulationError("interim view must contain exactly continuation checkpoints 4 and 5")


def validate_interim_population(parent_root, continuation_root, pins):
    """Validate the stopped evidence and return only the six complete checkpoints.

    ``pins`` must contain the five values accepted by ``parent_validation_pins``.
    No files are changed and this function does not invoke an evaluator or model.
    """
    required = {"ledger_sha256", "manifest_sha256", "registration_sha256",
                "reference_build_sha256", "checker_sha256"}
    if not isinstance(pins, dict) or set(pins) != required:
        raise InterimPopulationError("all five authorized parent integrity pins are required")
    try:
        parent = validate_parent(
            Path(parent_root), pins["ledger_sha256"],
            expected_manifest_sha256=pins["manifest_sha256"],
            expected_registration_sha256=pins["registration_sha256"],
            expected_checker_sha256=pins["checker_sha256"],
            expected_reference_build_sha256=pins["reference_build_sha256"],
        )
        segment_root = Path(continuation_root).resolve()
        segment_manifest_sha = verify_segment_manifest(segment_root)
        registration_raw = _read_json(segment_root / "continuation-registration.json")
        registration = _expected_registration(parent, registration_raw, segment_root)
    except (ContinuationError, OSError) as error:
        raise InterimPopulationError(str(error)) from error

    groups, all_pairs, expected = _registered_population(parent)
    original_tasks = tuple(task for chunk in groups[:4] for task in chunk)
    continuation_tasks = tuple(task for chunk in groups[4:6] for task in chunk)
    completed_tasks = original_tasks + continuation_tasks
    registered_cont_tasks = tuple(task for chunk in groups[4:] for task in chunk)
    segment_pairs = [(task, sample) for task in registered_cont_tasks for sample in range(8)]
    registered_segment_candidates = [{"task": task, "sample": sample, "id": expected[(task, sample)]}
                                     for task, sample in segment_pairs]
    if (registration.get("task_ids") != list(registered_cont_tasks)
            or registration.get("expected_candidates") != registered_segment_candidates):
        raise InterimPopulationError("continuation identities differ from original registered order")

    parent_ledger = _read_jsonl(parent.root / "run" / "ledger.jsonl")
    segment_ledger = _read_jsonl(segment_root / "ledger.jsonl")
    parent_visible = _read_jsonl(parent.root / "run" / "visible.jsonl")
    segment_visible = _read_jsonl(segment_root / "visible.jsonl")
    parent_decisions = _read_jsonl(parent.root / "run" / "decisions.jsonl")
    segment_decisions = _read_jsonl(segment_root / "decisions.jsonl")
    parent_labels = _read_jsonl(parent.root / "run" / "sealed-labels.jsonl")
    segment_labels = _read_jsonl(segment_root / "sealed-labels.jsonl")

    parent_expected = {key: expected[key] for key in all_pairs if key[0] in original_tasks}
    interim_pairs = [(task, sample) for task in continuation_tasks for sample in range(8)]
    interim_expected = {key: expected[key] for key in interim_pairs}
    _check_panel_shapes(parent_visible, parent_decisions, parent_labels, parent_expected, groups[:4])
    _check_panel_shapes(segment_visible, segment_decisions, segment_labels, interim_expected, groups[4:6])

    parent_started, parent_calls = _check_parent_calls(parent, parent_ledger, expected, groups)
    starts = [row for row in segment_ledger if row.get("event") == "call_started"]
    calls = [row for row in segment_ledger if row.get("event") == "call_complete"]
    expected_started_pairs = segment_pairs[:94]
    expected_started = {key: expected[key] for key in expected_started_pairs}
    validate_identity_rows(starts, expected_started, "continuation started call")
    seen_completed = {(row.get("task"), row.get("sample")) for row in calls}
    if (len(calls) != 93 or not seen_completed.issubset(set(expected_started_pairs))
            or len(seen_completed) != len(calls)
            or len(set(expected_started_pairs) - seen_completed) != 1):
        raise InterimPopulationError("partial continuation must have 93 completions and one interrupted start")
    missing_pair = next(iter(set(expected_started_pairs) - seen_completed))
    if missing_pair[0] not in groups[6]:
        raise InterimPopulationError("interrupted call is outside the uncheckpointed chunk")
    expected_complete = {key: expected[key] for key in expected_started_pairs if key in seen_completed}
    validate_identity_rows(calls, expected_complete, "continuation completed call")

    completed_chunk_pairs = {key for key in interim_pairs}
    complete_calls = [row for row in calls if (row["task"], row["sample"]) in completed_chunk_pairs]
    partial_calls = [row for row in calls if row not in complete_calls]
    if len(complete_calls) != 80 or len(partial_calls) != 13:
        raise InterimPopulationError("completed checkpoints and generation-only outputs do not reconcile")

    checkpoints = [row for row in segment_ledger if row.get("event") == "chunk_checkpoint"]
    for chunk in COMPLETED_CHUNKS:
        validate_chunk_events(parent_ledger, chunk, complete=True, continuation=False,
                              task_ids=groups[chunk])
    for chunk in (4, 5):
        validate_chunk_events(segment_ledger, chunk, complete=True, continuation=True,
                              task_ids=groups[chunk])
    validate_chunk_events(segment_ledger, 6, complete=False, continuation=True)
    if any(row.get("chunk") == 7 for row in segment_ledger):
        raise InterimPopulationError("unexpected activity exists for the final registered chunk")

    for offset, chunk in enumerate((4, 5), start=1):
        event_start = next(row for row in segment_ledger
                           if row.get("event") == "chunk_start" and row.get("chunk") == chunk)
        checkpoint = next(row for row in checkpoints if row.get("chunk") == chunk)
        if checkpoint.get("completed_tasks") != 20 + 5 * offset:
            raise InterimPopulationError("continuation checkpoint task counter is incorrect")
        verify_checkpoint_artifact(checkpoint.get("chunk_artifact_sha256"),
                                   _hash_tree(segment_root / f"chunk-{chunk:02d}"))
        for row in (event_start, checkpoint):
            env = row.get("environment", {})
            if env.get("container_ids") or env.get("active_models"):
                raise InterimPopulationError("checkpoint records a live runner or inference process")
        if not (segment_ledger.index(event_start) < segment_ledger.index(checkpoint)):
            raise InterimPopulationError("checkpoint precedes its chunk start")

    _validate_resource_events(segment_ledger, registration, parent, starts, calls, checkpoints)
    parent_generations = _validate_generation_files(parent.root / "run", parent_calls)
    interim_generations = _validate_generation_files(segment_root, complete_calls, all_calls=calls)

    raw_files = {path.stem: path for path in segment_root.glob("chunk-*/*.json")}
    for row in partial_calls:
        candidate_id = row["id"]
        if candidate_id not in raw_files or candidate_id + "-code" not in raw_files:
            raise InterimPopulationError("generation-only output lacks its manifested raw/code artifacts")
        raw = _read_json(raw_files[candidate_id])
        code_record = _read_json(raw_files[candidate_id + "-code"])
        code = code_record.get("code")
        if (not isinstance(code, str) or _sha(code.encode()) != row.get("code_hash")
                or raw.get("status") != "ok" or raw.get("output_tokens") != row.get("tokens")
                or raw.get("input_tokens") != row.get("input_tokens")
                or code_record.get("parse") != row.get("parse")):
            raise InterimPopulationError("generation-only artifacts differ from their call ledger")
    interrupted_id = expected[missing_pair]
    if interrupted_id in raw_files or interrupted_id + "-code" in raw_files:
        raise InterimPopulationError("interrupted call unexpectedly has a complete output artifact")
    if len(starts) != 94 or len(calls) != 93 or len(segment_pairs) - len(starts) != 66:
        raise InterimPopulationError("continuation start, completion, and unstarted counters differ")

    def filtered(rows, tasks):
        return tuple(row for row in rows if row.get("task") in set(tasks))

    checkpoint_call_ids = {row["id"] for row in parent_calls + complete_calls}
    checkpoint_started = [row for row in parent_started + starts if row.get("id") in checkpoint_call_ids]
    return InterimView(
        parent_root=parent.root,
        continuation_root=segment_root,
        checkpoint_chunks=tuple(range(6)),
        original_tasks=original_tasks,
        continuation_tasks=continuation_tasks,
        completed_tasks=completed_tasks,
        parent_ledger=freeze_records(parent_ledger),
        continuation_ledger=freeze_records(segment_ledger),
        visible_records=freeze_records(parent_visible + segment_visible),
        decision_records=freeze_records(parent_decisions + segment_decisions),
        label_records=freeze_records(parent_labels + segment_labels),
        call_records=freeze_records(parent_calls + complete_calls),
        started_records=freeze_records(checkpoint_started),
        generation_records=freeze_records(parent_generations + interim_generations),
        segment_manifest_sha256=segment_manifest_sha,
        generation_only_outputs=len(partial_calls),
        interrupted_started_calls=1,
        unstarted_registered_calls=len(segment_pairs) - len(starts),
        parent_output_tokens=parent.output_tokens,
        continuation_output_tokens=sum(row["tokens"] for row in calls),
        cumulative_output_tokens=parent.output_tokens + sum(row["tokens"] for row in calls),
        parent_elapsed_seconds=parent.elapsed_seconds,
        continuation_elapsed_seconds=segment_ledger[-1]["segment_elapsed_seconds"],
        cumulative_elapsed_seconds=segment_ledger[-1]["elapsed_seconds"],
    )
