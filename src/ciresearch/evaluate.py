"""Trusted scorer for one registered panel."""

from ciresearch.sandbox import SandboxError, run_panel
from ciresearch.scoring import Comparator


class EvaluationUnavailable(SandboxError):
    pass


def evaluate_panel(image, evidence, dataset, code, entry, atol, cases, expected, reference_times,
                   *, minimum=1.0, halt=lambda: False):
    if not len(cases) == len(expected) == len(reference_times):
        raise ValueError("incomplete reference panel")
    comparator = Comparator(dataset, entry, atol)
    details = []
    outcomes = []

    def record(index, status, value, args_after):
        outcomes.append(status)
        if status not in {"ok", "timeout", "exception"}:
            raise EvaluationUnavailable(f"case {index}: {status}")
        details.append(status == "ok" and comparator.compare(value, expected[index], args_after))

    result = run_panel(image, evidence, code, entry, cases,
                       [max(minimum, 4 * t) for t in reference_times], record, halt=halt)
    if result not in {"complete", "invalid_program", "exception"}:
        raise EvaluationUnavailable(f"candidate initialization: {result}")
    return {
        "status": "pass" if result == "complete" and all(details) else "fail",
        "details": details,
        "execution": outcomes,
        "initialization": result,
    }
