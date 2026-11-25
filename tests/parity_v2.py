"""Compare authored synthetic fixtures with the patched official checker."""

import json
import os
from pathlib import Path
import time

from ciresearch.evaluate import evaluate_panel
from ciresearch.fixture_client import reference_panel

# candidate body, inputs, trusted expected observations, expected per-case verdicts
FIXTURES = (
    ("float", "humaneval", "solve", 0, "return x", [[1.0000005], [1.001]], [1.0, 1.0], [True, False]),
    ("typed", "humaneval", "solve", 1e-6, "return (1.0000005,)", [[]], [[1.0]], [False]),
    ("root", "humaneval", "find_zero", 1e-6, "return x[0]", [[[-1, 0, 1]], [[0, 0, -1]]],
     [1.0, 1.0], [True, True]),
    ("mutated_root", "humaneval", "find_zero", 1e-6, "x[0] = 0; return 0",
     [[[-1, 0, 1]]], [1.0], [True]),
    ("failed_root", "humaneval", "find_zero", 1e-6, "return 0",
     [[[-1, 0, 1]]], [1.0], [False]),
    ("set", "mbpp", "similar_elements", 0, "return [2, 1, 2]", [[]], [[1, 2]], [True]),
    ("sum", "mbpp", "sum_div", 0, "return 0", [[6]], [12], [True]),
    ("presence", "mbpp", "check_str", 0, "return x", [["yes"], [None]], [True, True], [True, False]),
    ("permissive", "mbpp", "are_equivalent", 0, "return False", [[]], [True], [True]),
    ("surface", "mbpp", "surface_Area", 0.001, "return 13", [[2, 2]], [50], [True]),
    ("digit_distance", "mbpp", "digit_distance_nums", 0, "return 3",
     [[14, 2]], [90], [True]),
    ("exception", "humaneval", "solve", 0, "if x: return 2\nraise ValueError()", [[0], [1]], [0, 2],
     [False, True]),
    ("timeout", "humaneval", "solve", 0, "__import__('time').sleep(0.3); return 1", [[]], [1], [False]),
    ("ordered", "humaneval", "solve", 0,
     "solve.previous = getattr(solve, 'previous', []); x.append(1); solve.previous.append(x)\n"
     "return sum(map(len, solve.previous))",
     [[[1]], [[2, 3]]], [2, 5], [True, True]),
)


def main():
    evidence = Path(os.environ["CIRESEARCH_PARITY_EVIDENCE"])
    evidence.mkdir(mode=0o700)
    official_image = os.environ["CIRESEARCH_OFFICIAL_IMAGE"]
    candidate_image = os.environ["CIRESEARCH_CANDIDATE_IMAGE"]
    for name, dataset, entry, atol, body, cases, expected, verdict in FIXTURES:
        args = {0: "", 1: "x", 2: "x, y"}[len(cases[0])]
        code = f"def {entry}({args}):\n " + body.replace("\n", "\n ")
        start = time.monotonic()
        values, timing, [official] = reference_panel(
            official_image, evidence / f"{name}-official", dataset, entry, atol, 0.10,
            cases, expected=expected, fixtures=(code,),
        )
        separated = evaluate_panel(
            candidate_image, evidence / f"{name}-separated", dataset, code, entry, atol,
            cases, values, timing, minimum=0.10,
        )
        result = {"fixture": name, "official": official, "separated": separated,
                  "wall_seconds": time.monotonic() - start}
        print(json.dumps(result), flush=True)
        assert official["details"] == separated["details"] == verdict, result
        assert official["status"] == separated["status"], result


if __name__ == "__main__":
    main()
