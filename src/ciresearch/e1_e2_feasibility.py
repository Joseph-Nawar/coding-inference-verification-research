"""No-inference E2 feasibility from frozen first-four code and cached evidence."""
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import statistics
from types import MappingProxyType

from ciresearch.e1_continuation import _sha
from ciresearch.e1_data import chunk_indices, development_records
from ciresearch.e1_interim import InterimView
from ciresearch.sandbox import validate_response
from ciresearch.wire import WireError, pack, read_frame, unpack, write_frame

CONTEXT_LIMIT = 8192
OUTPUT_RESERVE = 128
E2_TASK_CAP = 24
ARMS = ("A", "B", "C", "D")
SELECTOR_SYSTEM = (
    "Review the task and candidate programs. Choose one candidate index. "
    "Return only that index. Do not modify or execute candidate code."
)


class E2FeasibilityError(ValueError):
    """Cached E1 data cannot support a faithful E2 feasibility calculation."""


@dataclass(frozen=True)
class E2TaskFeasibility:
    task_index: int
    technical_eligible: bool
    reasons: tuple
    condition_tokens: object
    d_case_count: int
    d_candidate_runs: int
    d_candidate_records: int
    d_distinct_behavior_signatures: int
    d_executed_candidates: int
    integrity_qualified_reference: bool


@dataclass(frozen=True)
class E2TechnicalAssessment:
    tasks: tuple
    eligible_task_indices: tuple
    available_first_four_pools: int
    usable_v_pools: int
    usable_d_pools: int
    all_arm_context_fit_pools: int
    context_summary: object
    costs: object
    model_revision: str
    tokenizer_revision: str


@dataclass(frozen=True)
class E2EvidenceView:
    """Only frozen generation, V, and path evidence; contains no correctness labels."""

    parent_root: Path
    continuation_root: Path
    original_tasks: tuple
    completed_tasks: tuple
    call_records: tuple
    visible_records: tuple


def e2_evidence_view(view: InterimView) -> E2EvidenceView:
    return E2EvidenceView(
        parent_root=view.parent_root,
        continuation_root=view.continuation_root,
        original_tasks=tuple(view.original_tasks),
        completed_tasks=tuple(view.completed_tasks),
        call_records=tuple(view.call_records),
        visible_records=tuple(view.visible_records),
    )


def _load_frames(path):
    try:
        with Path(path).open("rb") as stream:
            return [read_frame(line) for line in stream]
    except (OSError, WireError) as error:
        raise E2FeasibilityError(f"cached panel frame is invalid: {Path(path).name}") from error


def _load_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise E2FeasibilityError(f"cached artifact is invalid: {Path(path).name}") from error


def _token_count(tokenizer, user_content):
    chat = tokenizer.apply_chat_template(
        [{"role": "system", "content": SELECTOR_SYSTEM},
         {"role": "user", "content": user_content}],
        tokenize=False,
        add_generation_prompt=True,
    )
    return len(tokenizer.encode(chat, add_special_tokens=False))


def _condition_payloads(task_prompt, candidates, visible, d_inputs, d_outputs, expected,
                        comparison_value=True):
    base = {"task": task_prompt, "candidates": candidates}
    payloads = {"A": base}
    payloads["B"] = {**base, "visible_summary": visible}
    payloads["C"] = {**payloads["B"], "diagnostic": {"inputs": d_inputs, "outputs": d_outputs}}
    # Exact comparison labels are deliberately not read in the technical pass.
    comparisons = [[comparison_value for _ in expected] for _ in candidates]
    payloads["D"] = {**payloads["C"], "reference": {"expected": expected,
                                                          "comparison": comparisons}}
    return payloads


def _response_trace(path, expected_count):
    frames = _load_frames(path)
    if len(frames) != expected_count + 1 or frames[0].get("status") != "ready":
        raise E2FeasibilityError("cached D response coverage differs from its registered panel")
    trace = []
    signature_rows = []
    for response in frames[1:]:
        try:
            status, value, _args_after = validate_response(response)
        except Exception as error:
            raise E2FeasibilityError("cached D response has an unsupported typed representation") from error
        if status == "ok":
            packed = pack(value)
            trace.append({"status": status, "value": packed})
            signature_rows.append([status, packed])
        else:
            trace.append({"status": status})
            signature_rows.append([status, None])
    digest = hashlib.sha256(write_frame(signature_rows)).hexdigest()
    return tuple(trace), digest


def _cached_task_data(view, task, calls_by_pair, visible_by_id, task_prompt,
                      reference_record, tokenizer, chunk_by_task):
    source_root = (view.parent_root / "run" if task in set(view.original_tasks)
                   else view.continuation_root)
    chunk = chunk_by_task[task]
    candidates = []
    visible = []
    d_observations = []
    d_case_inputs = None
    d_reference = reference_record.get("references", {}).get("D")
    d_expected = d_reference.get("values", []) if isinstance(d_reference, dict) else []
    d_runs = 0
    d_records = 0
    signatures = set()
    reasons = []
    if not d_expected:
        reasons.append("no_registered_D_reference")

    for sample in range(4):
        call = calls_by_pair.get((task, sample))
        if call is None:
            reasons.append("missing_first_four_generation_record")
            continue
        candidate_id = call["id"]
        code_record = _load_json(source_root / f"chunk-{chunk:02d}" / f"{candidate_id}-code.json")
        code = code_record.get("code")
        parse_status = call.get("parse")
        if code_record.get("parse") != parse_status:
            reasons.append("generation_parse_record_mismatch")
        candidates.append({"index": sample + 1,
                           "parse_status": parse_status,
                           "code": code if parse_status == "ok" and isinstance(code, str) else None})

        visible_row = visible_by_id.get(candidate_id)
        visible_pass = visible_row.get("evidence", {}).get("base", {}).get("pass") if visible_row else None
        if type(visible_pass) is not bool:
            reasons.append("V_evidence_unavailable")
            visible.append({"index": sample + 1, "pass": None})
        else:
            visible.append({"index": sample + 1, "pass": visible_pass})

        if parse_status != "ok":
            d_observations.append({"index": sample + 1,
                                   "execution_status": f"not_executed:{parse_status}",
                                   "outputs": []})
            continue

        panel = source_root / f"chunk-{chunk:02d}" / f"{candidate_id}-D"
        requests_path, responses_path = panel / "requests.jsonl", panel / "responses.jsonl"
        if not requests_path.is_file() or not responses_path.is_file():
            reasons.append("cached_D_candidate_panel_missing")
            d_observations.append({"index": sample + 1, "execution_status": "cached_panel_missing",
                                   "outputs": []})
            continue
        requests = _load_frames(requests_path)
        if not requests or set(requests[0]) != {"code", "entry"} or requests[0].get("code") != code:
            reasons.append("cached_D_request_header_invalid")
            continue
        case_requests = requests[1:]
        response_frames = _load_frames(responses_path)
        if not response_frames:
            reasons.append("cached_D_response_missing")
            continue
        initial_status = response_frames[0].get("status")
        if not case_requests:
            if len(response_frames) == 1 and initial_status in {"exception", "invalid_program"}:
                d_records += 1
                signature = hashlib.sha256(write_frame([["initialization", initial_status]])).hexdigest()
                signatures.add(signature)
                d_observations.append({"index": sample + 1,
                                       "execution_status": f"initialization:{initial_status}",
                                       "outputs": [{"status": initial_status}]})
                continue
            reasons.append("cached_D_panel_has_no_inputs_or_valid_initialization_status")
            continue
        if initial_status != "ready":
            reasons.append("cached_D_initialization_status_mismatch")
            continue
        if len(case_requests) != len(d_expected):
            reasons.append("cached_D_input_coverage_mismatch")
            continue
        for request in case_requests:
            if set(request) != {"args", "seconds"}:
                reasons.append("cached_D_input_format_unsupported")
                break
            try:
                unpack(request["args"])
            except WireError:
                reasons.append("cached_D_input_type_unsupported")
                break
        request_bytes = tuple(write_frame({"args": row["args"]}) for row in case_requests)
        if d_case_inputs is None:
            d_case_inputs = request_bytes
        elif d_case_inputs != request_bytes:
            reasons.append("candidate_D_panels_use_different_inputs_or_order")
            continue

        trace, signature = _response_trace(responses_path, len(d_expected))
        d_runs += 1
        d_records += 1
        d_observations.append({"index": sample + 1, "execution_status": "cached",
                               "outputs": list(trace)})
        signatures.add(signature)

    if d_case_inputs is None:
        reasons.append("no_cached_D_inputs")
        d_inputs = []
    else:
        d_inputs = [json.loads(frame) for frame in d_case_inputs]
    try:
        for value in d_expected:
            unpack(value)
    except WireError:
        reasons.append("D_reference_output_type_unsupported")
    if d_expected and len(d_expected) != len(d_inputs):
        reasons.append("D_input_reference_count_mismatch")

    expected_values = list(d_expected)
    payloads_true = _condition_payloads(task_prompt, candidates, visible, d_inputs,
                                        d_observations, expected_values, True)
    payloads_false = _condition_payloads(task_prompt, candidates, visible, d_inputs,
                                         d_observations, expected_values, False)
    tokens = {arm: _token_count(tokenizer, json.dumps(payloads_true[arm], ensure_ascii=True,
                                                       separators=(",", ":")))
              for arm in ARMS}
    tokens["D"] = max(tokens["D"], _token_count(
        tokenizer, json.dumps(payloads_false["D"], ensure_ascii=True, separators=(",", ":"))))
    if len(candidates) != 4:
        reasons.append("first_four_candidate_bank_incomplete")
    if len(visible) != 4:
        reasons.append("first_four_V_summary_incomplete")
    usable_v = len(visible) == 4 and all(type(row.get("pass")) is bool for row in visible)
    expected_runs = sum(candidates[sample].get("parse_status") == "ok"
                        for sample in range(min(4, len(candidates))))
    usable_d = (bool(d_expected) and len(d_inputs) == len(d_expected)
                and d_records == expected_runs and expected_runs > 0 and d_runs > 0)
    fit = all(tokens[arm] + OUTPUT_RESERVE <= CONTEXT_LIMIT for arm in ARMS)
    if not usable_v:
        reasons.append("first_four_V_summary_unavailable")
    if not usable_d:
        reasons.append("first_four_D_evidence_unavailable")
    if not fit:
        reasons.append("one_or_more_conditions_exceed_context")
    return {
        "result": E2TaskFeasibility(
            task_index=task,
            technical_eligible=usable_v and usable_d and fit and not any(
                reason in {"candidate_D_panels_use_different_inputs_or_order",
                           "cached_D_input_coverage_mismatch", "cached_D_input_format_unsupported",
                           "cached_D_input_type_unsupported", "D_reference_output_type_unsupported",
                           "D_input_reference_count_mismatch", "cached_D_request_header_invalid"}
                for reason in reasons),
            reasons=tuple(sorted(set(reasons))),
            condition_tokens=MappingProxyType(tokens),
            d_case_count=len(d_inputs),
            d_candidate_runs=d_runs,
            d_candidate_records=d_records,
            d_distinct_behavior_signatures=len(signatures),
            d_executed_candidates=d_runs,
            integrity_qualified_reference=bool(reference_record.get("integrity")),
        ),
        "usable_v": usable_v,
        "usable_d": usable_d,
        "tokens": tokens,
    }


def _context_summary(results):
    output = {}
    for arm in ARMS:
        values = [row["tokens"][arm] for row in results if arm in row["tokens"]
                  and (arm in ("A", "B") or row["usable_d"])]
        ordered = sorted(values)
        def quantile(p):
            if not ordered:
                return None
            index = (len(ordered) - 1) * p
            low, high = int(index), min(len(ordered) - 1, int(index) + 1)
            return ordered[low] + (ordered[high] - ordered[low]) * (index - low)
        output[arm] = {
            "pools_measured": len(values),
            "median_input_tokens": statistics.median(values) if values else None,
            "p95_input_tokens": quantile(0.95),
            "maximum_input_tokens": max(values, default=None),
            "fits_with_128_output_reserve": sum(value + OUTPUT_RESERVE <= CONTEXT_LIMIT for value in values),
        }
    return output


def assess_e2_technical(view: E2EvidenceView, tokenizer, data_root):
    """Freeze technical E2 eligibility without reading any full correctness labels."""
    parent_registration = _load_json(view.parent_root / "registration.json")
    audit_records = _load_json(view.parent_root / "qualified-reference.json")
    if len(audit_records) != 40:
        raise E2FeasibilityError("registered development audit must contain 40 records")
    tasks = development_records(Path(data_root), parent_registration["split_sha256"])
    if len(tasks) != 40:
        raise E2FeasibilityError("development data loader returned an unexpected population")
    for index, (_benchmark, task) in enumerate(tasks):
        if _sha(task["prompt"].encode()) != parent_registration["prompt_sha256"][index]:
            raise E2FeasibilityError("development prompt differs from the frozen E1 commitment")

    chunks = list(chunk_indices())
    chunk_by_task = {task: chunk for chunk, members in enumerate(chunks) for task in members}
    calls = {(row["task"], row["sample"]): row for row in view.call_records}
    visible_by_id = {row["id"]: row for row in view.visible_records}
    results = []
    for task_index in view.completed_tasks:
        benchmark, task = tasks[task_index]
        # E2 sees exactly the task prompt frozen for E1. Candidate order is fixed here;
        # any later registered permutation must be chosen independently of correctness.
        first_four = {(task_index, sample): calls.get((task_index, sample)) for sample in range(4)}
        rows = _cached_task_data(
            view, task_index, calls, visible_by_id, task["prompt"],
            audit_records[task_index], tokenizer, chunk_by_task)
        result = rows["result"]
        # The pre-generation integrity qualification is descriptive; it does not alter
        # technical eligibility or the future task ordering.
        results.append({"result": result, "usable_v": rows["usable_v"],
                        "usable_d": rows["usable_d"], "tokens": rows["tokens"],
                        "benchmark": benchmark, "first_four_complete": all(first_four.values())})

    eligible = tuple(row["result"].task_index for row in results
                     if row["result"].technical_eligible and row["first_four_complete"])
    tokenizer_revision = parent_registration["model_revision"]
    return E2TechnicalAssessment(
        tasks=tuple(row["result"] for row in results),
        eligible_task_indices=eligible,
        available_first_four_pools=len(results),
        usable_v_pools=sum(row["usable_v"] for row in results),
        usable_d_pools=sum(row["usable_d"] for row in results),
        all_arm_context_fit_pools=sum(all(row["tokens"][arm] + OUTPUT_RESERVE <= CONTEXT_LIMIT
                                          for arm in ARMS) for row in results),
        context_summary=MappingProxyType(_context_summary(results)),
        costs=MappingProxyType({
            "eligible_tasks": len(eligible),
            "planned_tasks_at_original_cap": min(E2_TASK_CAP, len(eligible)),
            "calls_if_using_all_eligible_up_to_cap": 4 * min(E2_TASK_CAP, len(eligible)),
            "maximum_output_tokens_if_using_all_eligible_up_to_cap": 4 * min(E2_TASK_CAP, len(eligible)) * OUTPUT_RESERVE,
            "registered_call_cap": 96,
            "registered_output_token_cap": 12288,
        }),
        model_revision=parent_registration["model_revision"],
        tokenizer_revision=tokenizer_revision,
    )


def retrospective_e2_summary(assessment: E2TechnicalAssessment, label_records,
                              decision_records=()):
    """Join correctness only after technical eligibility is frozen; never select tasks."""
    eligible = set(assessment.eligible_task_indices)
    by_task = {}
    for row in label_records:
        if row["task"] in eligible and row["sample"] < 4:
            by_task.setdefault(row["task"], []).append(row)
    composition = {
        "official_compatible": Counter(),
        "integrity_qualified": Counter(),
    }
    decisions = {row["task"]: row["decisions"].get("4", {})
                 for row in decision_records if row.get("task") in eligible}
    missed = Counter()
    for task in assessment.eligible_task_indices:
        rows = sorted(by_task.get(task, ()), key=lambda row: row["sample"])
        for endpoint, key in (("official_compatible", "y"),
                              ("integrity_qualified", "qualified_y")):
            labels = [row.get(key) for row in rows]
            if len(labels) != 4 or any(value is None for value in labels):
                composition[endpoint]["incomplete"] += 1
                continue
            if all(labels):
                composition[endpoint]["all_correct"] += 1
            elif any(labels):
                composition[endpoint]["mixed"] += 1
            else:
                composition[endpoint]["all_incorrect"] += 1
            if any(labels):
                for selector in ("pass_count", "consensus"):
                    selected = decisions.get(task, {}).get(selector)
                    if selected is None or type(selected) is not int or not 0 <= selected < 4:
                        missed[f"{endpoint}_{selector}_unavailable_or_invalid"] += 1
                    elif not labels[selected]:
                        missed[f"{endpoint}_{selector}_missed_available_correct_candidate"] += 1
    return {
        "technical_eligible_tasks": len(eligible),
        "retrospective_first_four_composition": {
            endpoint: dict(counts) for endpoint, counts in composition.items()},
        "retrospective_visible_selector_missed_opportunities": dict(missed),
        "selection_opportunities_are_retrospective_only": True,
    }
