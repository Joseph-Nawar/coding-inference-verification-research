"""Host access to the trusted reference and pinned official fixture checker."""

import time

from ciresearch.sandbox import Container, SandboxError
from ciresearch.wire import pack, unpack


def reference_panel(image, evidence, dataset, entry, atol, minimum, cases,
                    *, reference=None, expected=None, fixtures=(), deadline=float("inf")):
    if (reference is None) == (expected is None):
        raise ValueError("provide exactly one fixture reference source")
    with Container(image, evidence) as container:
        def send(payload, maximum=5):
            return container.exchange(payload, min(deadline, time.monotonic() + maximum))

        if send({"dataset": dataset, "entry": entry,
                            "atol": atol, "minimum": minimum}) != {"status": "ready"}:
            raise SandboxError("trusted fixture did not initialize")
        for case in cases:
            if send({"case": pack(case)}) != {"status": "queued"}:
                raise SandboxError("trusted fixture did not queue test input")
        response = send({"reference": reference} if reference is not None else
                        {"expected": [pack(value) for value in expected]}, maximum=25)
        if response not in ({"status": "reference_calculated"}, {"status": "reference_loaded"}):
            raise SandboxError("reference calculation failed")
        rows = [send({"index": index}) for index in range(len(cases))]
        verdicts = [send({"fixture": fixture}, maximum=70) for fixture in fixtures]
    return [unpack(r["value"]) for r in rows], [r["seconds"] for r in rows], verdicts
