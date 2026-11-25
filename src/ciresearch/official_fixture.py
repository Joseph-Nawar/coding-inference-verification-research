"""Entrypoint of the dedicated trusted reference and authored-fixture container."""

import os
from pathlib import Path
import sys

from ciresearch.wire import MAX_FRAME, pack, read_frame, unpack, write_frame


def main():
    if sys.platform != "linux" or os.getuid() != 65532 or not Path("/.dockerenv").is_file():
        raise SystemExit("trusted fixture image required")
    from evalplus.eval import untrusted_check
    from evalplus.eval._special_oracle import MBPP_OUTPUT_NOT_NONE_TASKS
    from evalplus.gen.util import trusted_exec

    def receive():
        return read_frame(sys.stdin.buffer.readline(MAX_FRAME + 1))

    def send(value):
        sys.stdout.buffer.write(write_frame(value))
        sys.stdout.buffer.flush()

    init = receive()
    cases = []
    send({"status": "ready"})
    while frame := sys.stdin.buffer.readline(MAX_FRAME + 1):
        job = read_frame(frame)
        if "case" in job:
            cases.append(unpack(job["case"]))
            send({"status": "queued"})
        elif "reference" in job:
            expected, ref_time = trusted_exec(
                job["reference"], cases, init["entry"], record_time=True,
                output_not_none=init["dataset"] == "mbpp" and init["entry"] in MBPP_OUTPUT_NOT_NONE_TASKS,
            )
            send({"status": "reference_calculated"})
        elif "expected" in job:
            expected = [unpack(value) for value in job["expected"]]
            ref_time = [0.0] * len(cases)
            send({"status": "reference_loaded"})
        elif "index" in job:
            index = job["index"]
            send({"value": pack(expected[index]), "seconds": ref_time[index]})
        elif "fixture" in job:
            status, details = untrusted_check(
                init["dataset"], job["fixture"], cases, init["entry"], expected,
                init["atol"], ref_time, fast_check=False, min_time_limit=init["minimum"],
            )
            send({"status": status, "details": [bool(value) for value in details]})
        else:
            raise ValueError("invalid trusted-fixture request")


if __name__ == "__main__":
    main()
