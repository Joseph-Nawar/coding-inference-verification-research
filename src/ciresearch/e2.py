"""Label-blind E2 sample, prompt, parser, and cached diagnostic helpers."""
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from typing import Mapping, Sequence

from ciresearch.sandbox import validate_response
from ciresearch.scoring import Comparator
from ciresearch.wire import WireError, pack, unpack
from ciresearch.e2_prompts import E2_SYSTEM_PROMPT, E2_USER_PREFIX

ARMS = ("A", "B", "C", "D")
BENCHMARKS = ("humaneval", "mbpp")
CONTEXT_LIMIT = 8192
OUTPUT_RESERVE = 128
MAX_PROMPT_BYTES = 1_000_000


class E2Error(ValueError):
    """A frozen E2 registration, prompt, response, or diagnostic record is invalid."""


@dataclass(frozen=True)
class EligibleTask:
    """A technical-only task record. It intentionally has no correctness-label fields."""

    task_id: str
    benchmark: str
    condition_tokens: Mapping[str, int]


@dataclass(frozen=True)
class ScheduledTask:
    task_id: str
    benchmark: str
    batch: int
    batch_position: int
    arm_order: tuple[str, str, str, str]
    condition_tokens: tuple[tuple[str, int], ...]


def _digest(namespace: str, *parts: object) -> bytes:
    if type(namespace) is not str or not namespace:
        raise E2Error("a nonempty frozen E2 namespace is required")
    value = "\0".join((namespace, *(str(part) for part in parts)))
    return hashlib.sha256(value.encode("utf-8")).digest()


def _check_task(task: EligibleTask) -> None:
    if not isinstance(task, EligibleTask):
        raise E2Error("E2 sample accepts only technical eligibility records")
    if type(task.task_id) is not str or not task.task_id:
        raise E2Error("task identity is missing")
    if task.benchmark not in BENCHMARKS:
        raise E2Error("task benchmark is not registered")
    if set(task.condition_tokens) != set(ARMS):
        raise E2Error("all four final condition token counts are required")
    if any(type(task.condition_tokens[arm]) is not int or task.condition_tokens[arm] < 0
           for arm in ARMS):
        raise E2Error("invalid final condition token count")
    if any(task.condition_tokens[arm] + OUTPUT_RESERVE > CONTEXT_LIMIT for arm in ARMS):
        raise E2Error("task exceeds an E2 condition context allowance")


def freeze_balanced_sample(eligible: Sequence[EligibleTask], *, namespace: str,
                           per_benchmark: int = 12) -> tuple[ScheduledTask, ...]:
    """Hash-rank the technical-only population, take a balanced sample, and freeze calls."""
    if type(per_benchmark) is not int or per_benchmark <= 0 or per_benchmark % 2:
        raise E2Error("balanced E2 sample size must be a positive even count per benchmark")
    rows = tuple(eligible)
    for row in rows:
        _check_task(row)
    ids = [row.task_id for row in rows]
    if len(ids) != len(set(ids)):
        raise E2Error("duplicate task identity in technical eligibility")
    selected: dict[str, list[EligibleTask]] = {}
    for benchmark in BENCHMARKS:
        ranked = sorted((row for row in rows if row.benchmark == benchmark),
                        key=lambda row: (_digest(namespace, "task-order-v1", benchmark, row.task_id),
                                         row.task_id))
        if len(ranked) < per_benchmark:
            raise E2Error("technical population cannot support the registered balanced sample")
        selected[benchmark] = ranked[:per_benchmark]

    output = []
    batch_count = per_benchmark // 2
    for batch in range(batch_count):
        members = selected["humaneval"][2 * batch:2 * batch + 2]
        members += selected["mbpp"][2 * batch:2 * batch + 2]
        ordered = sorted(members,
                         key=lambda row: (_digest(namespace, "batch-task-v1", batch, row.task_id),
                                          row.task_id))
        rotation = int.from_bytes(_digest(namespace, "arm-rotation-v1", batch)[:4], "big") % 4
        for position, row in enumerate(ordered):
            offset = (position + rotation) % 4
            arm_order = ARMS[offset:] + ARMS[:offset]
            output.append(ScheduledTask(
                task_id=row.task_id,
                benchmark=row.benchmark,
                batch=batch,
                batch_position=position,
                arm_order=arm_order,
                condition_tokens=tuple((arm, row.condition_tokens[arm]) for arm in ARMS),
            ))
    return tuple(output)


def candidate_permutation(candidate_ids: Sequence[str], task_id: str,
                          namespace: str) -> tuple[str, ...]:
    if type(task_id) is not str or not task_id or len(candidate_ids) != 4:
        raise E2Error("one task and exactly four candidates are required")
    if any(type(candidate_id) is not str or not candidate_id for candidate_id in candidate_ids):
        raise E2Error("candidate identity is missing")
    if len(set(candidate_ids)) != 4:
        raise E2Error("candidate identities must be unique")
    return tuple(sorted(candidate_ids,
                        key=lambda candidate_id: (_digest(namespace, "candidate-order-v1",
                                                           task_id, candidate_id), candidate_id)))


def make_call_seed(task_id: str, arm: str, model_revision: str, namespace: str) -> int:
    if type(task_id) is not str or not task_id or arm not in ARMS:
        raise E2Error("invalid task or arm for seed derivation")
    if type(model_revision) is not str or not model_revision:
        raise E2Error("pinned model revision is required for seed derivation")
    return int.from_bytes(_digest(namespace, "generation-seed-v1", task_id, arm,
                                  model_revision)[:4], "big")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise E2Error("duplicate JSON object key")
        result[key] = value
    return result


def parse_selector_response(raw: str, displayed_candidate_ids: Sequence[str]) -> str:
    """Parse the exact index-only JSON contract and map its one-based index to identity."""
    if type(raw) is not str or len(raw.encode("utf-8")) > 16_384:
        raise E2Error("selector response is absent or over the parser limit")
    if len(displayed_candidate_ids) != 4 or len(set(displayed_candidate_ids)) != 4:
        raise E2Error("four unique displayed candidate identities are required")
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object,
                           parse_constant=lambda _value: (_ for _ in ()).throw(E2Error("invalid JSON constant")))
    except (json.JSONDecodeError, UnicodeError, RecursionError) as error:
        raise E2Error("selector response is not strict JSON") from error
    if type(value) is not dict or set(value) != {"choice"}:
        raise E2Error("selector response must contain only the choice field")
    choice = value["choice"]
    if type(choice) is not int or not 1 <= choice <= 4:
        raise E2Error("selector choice must be an integer from 1 through 4")
    return displayed_candidate_ids[choice - 1]


def _safe_json(value) -> str:
    try:
        result = json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError, RecursionError) as error:
        raise E2Error("prompt evidence is not bounded JSON data") from error
    if len(result.encode("utf-8")) > MAX_PROMPT_BYTES:
        raise E2Error("prompt evidence exceeds the registered byte limit")
    return result


def _candidate_rows(candidates):
    if len(candidates) != 4:
        raise E2Error("exactly four candidates are required")
    rows = []
    seen_ids, seen_samples = set(), set()
    for displayed_index, candidate in enumerate(candidates, 1):
        if type(candidate) is not dict or set(candidate) != {
                "candidate_id", "original_sample", "parse_status", "code"}:
            raise E2Error("candidate prompt record has unauthorized fields")
        candidate_id = candidate["candidate_id"]
        sample = candidate["original_sample"]
        parse_status = candidate["parse_status"]
        code = candidate["code"]
        if (type(candidate_id) is not str or not candidate_id or type(sample) is not int
                or not 0 <= sample < 8 or sample in seen_samples or candidate_id in seen_ids):
            raise E2Error("candidate identity mapping is invalid")
        if type(parse_status) is not str or not parse_status:
            raise E2Error("candidate parse status is missing")
        if parse_status not in {"ok", "invalid_syntax", "missing_entry", "truncated"}:
            raise E2Error("candidate parse status is unsupported")
        if type(code) is not str:
            raise E2Error("candidate source text is unavailable")
        seen_ids.add(candidate_id)
        seen_samples.add(sample)
        rows.append({"index": displayed_index, "status": parse_status, "code": code})
    return rows


def _validate_visible(visible):
    if type(visible) is not list or len(visible) != 4:
        raise E2Error("four registered visible summaries are required")
    output = []
    for index, row in enumerate(visible, 1):
        if type(row) is not dict or set(row) != {
                "pass_count", "case_count", "passed", "status"}:
            raise E2Error("visible summary has unauthorized or missing fields")
        pass_count, case_count, all_pass = row["pass_count"], row["case_count"], row["passed"]
        status = row["status"]
        if status not in {"complete", "candidate_parse_failure", "initialization_exception",
                          "invalid_program"}:
            raise E2Error("visible result status is unsupported")
        if (type(pass_count) is not int or type(case_count) is not int or type(all_pass) is not bool
                or case_count <= 0 or pass_count < 0 or pass_count > case_count
                or all_pass != (pass_count == case_count)):
            raise E2Error("visible result count or pass flag is invalid")
        output.append({"index": index, "pass_count": pass_count, "case_count": case_count,
                       "passed": all_pass, "status": status})
    return output


def _validate_diagnostic(diagnostic):
    if type(diagnostic) is not dict or set(diagnostic) != {"inputs", "candidate_results"}:
        raise E2Error("diagnostic record has unauthorized or missing fields")
    inputs, candidates = diagnostic["inputs"], diagnostic["candidate_results"]
    if type(inputs) is not list or not inputs or type(candidates) is not list or len(candidates) != 4:
        raise E2Error("diagnostic inputs or candidate coverage is incomplete")
    for row in inputs:
        if type(row) is not dict or set(row) != {"args"}:
            raise E2Error("diagnostic input record is invalid")
        try:
            unpack(row["args"])
        except WireError as error:
            raise E2Error("diagnostic input is not a supported typed value") from error
    out = []
    for index, row in enumerate(candidates, 1):
        if type(row) is not dict or set(row) != {"initialization", "cases"}:
            raise E2Error("diagnostic candidate record has unauthorized fields")
        if type(row["initialization"]) is not str or type(row["cases"]) is not list:
            raise E2Error("diagnostic candidate status is invalid")
        if row["initialization"] == "ready" and len(row["cases"]) != len(inputs):
            raise E2Error("diagnostic response count differs from panel length")
        if row["initialization"] != "ready" and row["cases"]:
            raise E2Error("failed initialization cannot contain case outputs")
        normalized_cases = []
        for case in row["cases"]:
            if type(case) is not dict or set(case) - {"execution_status", "value", "args_after"}:
                raise E2Error("diagnostic case has unauthorized fields")
            if type(case.get("execution_status")) is not str:
                raise E2Error("diagnostic case execution status is missing")
            if case["execution_status"] == "ok" and set(case) != {
                    "execution_status", "value", "args_after"}:
                raise E2Error("successful diagnostic case lacks typed output or reported state")
            if case["execution_status"] != "ok" and set(case) != {"execution_status"}:
                raise E2Error("failed diagnostic case must not contain an output")
            if case["execution_status"] == "ok":
                try:
                    unpack(case["value"])
                    args_after = unpack(case["args_after"])
                except WireError as error:
                    raise E2Error("diagnostic output or execution state is not supported") from error
                if type(args_after) not in (list, tuple):
                    raise E2Error("reported post-call arguments are not a sequence")
            # The scorer validates and retains post-call state privately, but the
            # registered selector evidence exposes only outputs and statuses.
            normalized_cases.append(
                {"execution_status": case["execution_status"], "value": case["value"]}
                if case["execution_status"] == "ok" else
                {"execution_status": case["execution_status"]})
        out.append({"index": index, "initialization": row["initialization"],
                    "cases": normalized_cases})
    return {"inputs": inputs, "candidate_results": out}


def build_selector_prompt(arm: str, task_prompt: str, candidates: Sequence[dict], *,
                          visible=None, diagnostic=None, expected=None, comparisons=None) -> str:
    if arm not in ARMS or type(task_prompt) is not str or not task_prompt.strip():
        raise E2Error("selector arm or task specification is invalid")
    payload = {"task": task_prompt, "candidates": _candidate_rows(candidates)}
    if arm in {"B", "C", "D"}:
        payload["visible_results"] = _validate_visible(visible)
    elif visible is not None:
        raise E2Error("visible results are not allowed in condition A")
    if arm in {"C", "D"}:
        payload["diagnostic"] = _validate_diagnostic(diagnostic)
    elif diagnostic is not None:
        raise E2Error("diagnostic data is not allowed in this condition")
    if arm == "D":
        if type(expected) is not list or len(expected) != len(payload["diagnostic"]["inputs"]):
            raise E2Error("D expected-output panel does not match cached inputs")
        try:
            for value in expected:
                unpack(value)
        except WireError as error:
            raise E2Error("D expected output is not a supported typed value") from error
        if type(comparisons) is not list or len(comparisons) != 4:
            raise E2Error("D comparison coverage is incomplete")
        normalized = []
        for index, row in enumerate(comparisons, 1):
            if type(row) is not dict or set(row) != {"cases"} or type(row["cases"]) is not list:
                raise E2Error("D comparison row is invalid")
            if len(row["cases"]) != len(expected):
                raise E2Error("D comparison case count differs from reference panel")
            observed = payload["diagnostic"]["candidate_results"][index - 1]
            if observed["initialization"] == "ready":
                expected_statuses = [case["execution_status"] for case in observed["cases"]]
            else:
                expected_statuses = [f"initialization_{observed['initialization']}"] * len(expected)
            cases = []
            for case_index, item in enumerate(row["cases"]):
                if type(item) is not dict or set(item) != {
                        "execution_status", "comparison", "input_mutated"}:
                    raise E2Error("D comparison record has unauthorized fields")
                if (type(item["execution_status"]) is not str
                        or item["comparison"] not in {"pass", "fail", "not_comparable"}
                        or item["input_mutated"] is not None
                        and type(item["input_mutated"]) is not bool):
                    raise E2Error("D comparison result is invalid")
                if item["execution_status"] != expected_statuses[case_index]:
                    raise E2Error("D comparison status does not match the cached execution record")
                if ((item["execution_status"] == "ok")
                        != (item["comparison"] in {"pass", "fail"})):
                    raise E2Error("only successful outputs may have a comparator verdict")
                if (item["execution_status"] == "ok") != (type(item["input_mutated"]) is bool):
                    raise E2Error("input-mutation evidence does not match output availability")
                cases.append(item)
            normalized.append({"index": index, "cases": [
                {"execution_status": item["execution_status"],
                 "comparison": item["comparison"]} for item in cases]})
        payload["expected_outputs"] = expected
        payload["comparison_results"] = normalized
    elif expected is not None or comparisons is not None:
        raise E2Error("reference outputs and comparison results are allowed only in D")
    rendered = E2_USER_PREFIX + _safe_json(payload)
    if len(rendered.encode("utf-8")) > MAX_PROMPT_BYTES:
        raise E2Error("rendered selector prompt exceeds the registered byte limit")
    return rendered


def count_prompt_tokens(tokenizer, prompt: str, *, enforce_context: bool = True) -> int:
    if type(prompt) is not str:
        raise E2Error("prompt must be text")
    try:
        chat = tokenizer.apply_chat_template(
            [{"role": "system", "content": E2_SYSTEM_PROMPT},
             {"role": "user", "content": prompt}],
            tokenize=False, add_generation_prompt=True)
        count = len(tokenizer.encode(chat, add_special_tokens=False))
    except Exception as error:
        raise E2Error("pinned tokenizer failed to render the selector prompt") from error
    if type(count) is not int or count < 0:
        raise E2Error("pinned tokenizer returned an invalid token count")
    if enforce_context and count + OUTPUT_RESERVE > CONTEXT_LIMIT:
        raise E2Error("final selector prompt exceeds the 8,064-token input allowance")
    return count


def score_cached_d_panel(dataset: str, entry: str, atol: float, expected_wire: Sequence,
                         response_frames: Sequence[dict], input_wires: Sequence | None = None) -> dict:
    """Apply the registered comparator to cached ordered D responses; never executes code."""
    if not expected_wire or type(expected_wire) not in (list, tuple):
        raise E2Error("cached D expected-output panel is empty or invalid")
    if input_wires is not None and len(input_wires) != len(expected_wire):
        raise E2Error("cached D input and reference coverage differ")
    if input_wires is not None:
        try:
            for value in input_wires:
                args = unpack(value)
                if type(args) not in (list, tuple):
                    raise WireError("D arguments must be a positional sequence")
        except WireError as error:
            raise E2Error("cached D input has an unsupported typed representation") from error
    try:
        expected = [unpack(value) for value in expected_wire]
    except WireError as error:
        raise E2Error("cached D reference output has an unsupported typed representation") from error
    if not response_frames:
        raise E2Error("cached D response panel is missing")
    try:
        initial = validate_response(response_frames[0], initializing=True)
    except Exception as error:
        raise E2Error("cached D initialization record is malformed") from error
    init_status = initial[0]
    if init_status != "ready":
        return {
            "initialization": init_status,
            "cases": [{"execution_status": f"initialization_{init_status}",
                       "comparison": "not_comparable", "input_mutated": None}
                      for _ in expected],
            "pass_count": 0,
            "mutation_sensitive": dataset == "humaneval" and entry == "find_zero",
        }
    if len(response_frames) != len(expected) + 1:
        raise E2Error("cached D response coverage differs from its reference panel")
    comparator = Comparator(dataset, entry, atol)
    results = []
    for index, (frame, reference) in enumerate(zip(response_frames[1:], expected)):
        try:
            status, value, args_after = validate_response(frame)
        except Exception as error:
            raise E2Error(f"cached D response {index} is malformed") from error
        if status == "ok":
            try:
                compared = comparator.compare(value, reference, args_after)
            except Exception as error:
                raise E2Error(f"registered diagnostic comparator failed at case {index}") from error
            mutated = (pack(args_after) != input_wires[index]) if input_wires is not None else None
            results.append({"execution_status": status,
                            "comparison": "pass" if compared else "fail",
                            "input_mutated": mutated})
        else:
            results.append({"execution_status": status, "comparison": "not_comparable",
                            "input_mutated": None})
    return {
        "initialization": "ready",
        "cases": results,
        "pass_count": sum(row["comparison"] == "pass" for row in results),
        "mutation_sensitive": dataset == "humaneval" and entry == "find_zero",
    }


def score_unexecuted_d_panel(parse_status: str, case_count: int) -> dict:
    """Represent a candidate that was not run because extraction/parsing failed."""
    if parse_status not in {"invalid_syntax", "missing_entry", "truncated"}:
        raise E2Error("only registered candidate parse failures may skip D execution")
    if type(case_count) is not int or case_count <= 0:
        raise E2Error("a positive cached D panel length is required")
    return {
        "initialization": "candidate_parse_failure",
        "cases": [{"execution_status": "initialization_candidate_parse_failure",
                   "comparison": "not_comparable", "input_mutated": None}
                  for _ in range(case_count)],
        "pass_count": 0,
        "mutation_sensitive": False,
    }


def deterministic_baselines(candidates: Sequence[dict], visible_counts: Mapping[str, int],
                             diagnostic_results: Mapping[str, Mapping],
                             signatures: Mapping[str, str | None]) -> dict:
    if len(candidates) != 4:
        raise E2Error("deterministic E2 baselines require four candidates")
    ids, samples = [], {}
    for row in candidates:
        if type(row) is not dict or set(row) - {"candidate_id", "original_sample"}:
            raise E2Error("baseline candidate identity is invalid")
        candidate_id, sample = row.get("candidate_id"), row.get("original_sample")
        if type(candidate_id) is not str or not candidate_id or type(sample) is not int:
            raise E2Error("baseline candidate identity is invalid")
        if candidate_id in ids or sample in samples:
            raise E2Error("baseline candidate identities must be unique")
        ids.append(candidate_id)
        samples[sample] = candidate_id
    if set(visible_counts) != set(ids) or set(diagnostic_results) != set(ids) or set(signatures) != set(ids):
        raise E2Error("baseline evidence must cover exactly the four candidates")
    for count in visible_counts.values():
        if type(count) is not int or count < 0:
            raise E2Error("visible pass count is invalid")
    d_counts = {}
    for candidate_id, result in diagnostic_results.items():
        if type(result) is not dict or type(result.get("pass_count")) is not int:
            raise E2Error("D pass-count evidence is unavailable")
        d_counts[candidate_id] = result["pass_count"]
    def choose(scores):
        return min(ids, key=lambda candidate_id: (-scores[candidate_id],
                                                   next(sample for sample, cid in samples.items()
                                                        if cid == candidate_id)))
    visible = dict(visible_counts)
    combined = {candidate_id: visible[candidate_id] + d_counts[candidate_id] for candidate_id in ids}
    counts = Counter(signature for signature in signatures.values() if signature is not None)
    consensus_ids = [candidate_id for candidate_id in ids if signatures[candidate_id] is not None]
    consensus = (min(consensus_ids, key=lambda candidate_id: (-counts[signatures[candidate_id]],
                                                               next(sample for sample, cid in samples.items()
                                                                    if cid == candidate_id)))
                 if consensus_ids else None)
    return {
        "first_candidate": samples[min(samples)],
        "visible_pass_count": choose(visible),
        "visible_consensus": consensus,
        "d_only_pass_count": choose(d_counts),
        "v_plus_d_pass_count": choose(combined),
        "visible_scores": visible,
        "d_scores": d_counts,
        "v_plus_d_scores": combined,
    }
