"""Host access to the trusted reference and pinned official fixture checker."""

import time

from ciresearch.sandbox import Container, SandboxError
from ciresearch.wire import pack, unpack


def send(container, payload, maximum=5):
    return container.exchange(payload, time.monotonic() + maximum)


def reference_panel(image, evidence, dataset, entry, atol, minimum, cases,
                    *, reference=None, expected=None, fixtures=()):
    if (reference is None) == (expected is None):
        raise ValueError("provide exactly one fixture reference source")
    with Container(image, evidence) as container:
        if send(container, {"dataset": dataset, "entry": entry,
                            "atol": atol, "minimum": minimum}) != {"status": "ready"}:
            raise SandboxError("trusted fixture did not initialize")
        for case in cases:
            if send(container, {"case": pack(case)}) != {"status": "queued"}:
                raise SandboxError("trusted fixture did not queue test input")
        response = send(container, {"reference": reference} if reference is not None else
                        {"expected": [pack(value) for value in expected]}, maximum=25)
        if response not in ({"status": "reference_calculated"}, {"status": "reference_loaded"}):
            raise SandboxError("reference calculation failed")
        rows = [send(container, {"index": index}) for index in range(len(cases))]
        verdicts = [send(container, {"fixture": fixture}, maximum=70) for fixture in fixtures]
    return [unpack(r["value"]) for r in rows], [r["seconds"] for r in rows], verdicts
