"""Trusted scorer for one registered panel."""

from ciresearch.sandbox import SandboxError, run_panel, validate_response
from ciresearch.scoring import Comparator
from ciresearch.wire import MAX_FRAME, read_frame


class EvaluationUnavailable(SandboxError):
    pass


def evaluate_panel(image, evidence, dataset, code, entry, atol, cases, expected, reference_times,
                   *, minimum=1.0, halt=lambda: False, hard_seconds=None):
    if not len(cases) == len(expected) == len(reference_times):
        raise ValueError("incomplete reference panel")
    outcomes = []

    def record(index, status, _value, _args_after):
        if status not in {"ok", "timeout", "exception"}:
            raise EvaluationUnavailable(f"case {index}: {status}")
        outcomes.append(status)

    result = run_panel(image, evidence, code, entry, cases,
                       [max(minimum, 4 * t) for t in reference_times], record, halt=halt, hard_seconds=hard_seconds)
    if result not in {"complete", "invalid_program", "exception"}:
        raise EvaluationUnavailable(f"candidate initialization: {result}")

    # Read expected outputs only after removal. Comparison work and verdicts
    # cannot change the timing of the next input sent to the candidate.
    details = []
    if result == "complete":
        comparator = Comparator(dataset, entry, atol)
        with (evidence / "responses.jsonl").open("rb") as transcript:
            if validate_response(read_frame(transcript.readline(MAX_FRAME + 1)), True)[0] != "ready":
                raise EvaluationUnavailable("missing initial response in transcript")
            for index, expected_status in enumerate(outcomes):
                status, value, args_after = validate_response(read_frame(transcript.readline(MAX_FRAME + 1)))
                if status != expected_status:
                    raise EvaluationUnavailable("transcript status changed")
                details.append(status == "ok" and comparator.compare(value, expected[index], args_after))
            if transcript.read(1):
                raise EvaluationUnavailable("unexpected transcript data")
    return {
        "status": "pass" if result == "complete" and all(details) else "fail",
        "details": details,
        "execution": outcomes,
        "initialization": result,
    }
