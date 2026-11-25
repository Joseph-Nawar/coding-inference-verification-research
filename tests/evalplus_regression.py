"""Run only the authored synthetic fixtures in the documented parity container."""

import os
import socket
from pathlib import Path
import sys
import time


SOURCES = {
    "e5d0ed0bab96280b60b637ec7f15b5e4841b0cb2": (False, 1.0),
    "6eb1e199c2e370518e7bf3e8eee6322c2b23c89c": (True, 1.0),
    "26d6d00bb1fd0fa37f39c99d5290da67891d1c5e": (True, 4.0),
}


def main(revision):
    if sys.platform != "linux" or os.getuid() != 65532 or not Path("/.dockerenv").is_file():
        raise SystemExit("Run this fixture only in its restricted Docker container")

    interfaces = {
        name: int(Path(f"/sys/class/net/{name}/flags").read_text(), 16)
        for _, name in socket.if_nameindex()
    }
    # Linux may create inactive tunnel devices in a fresh network namespace.
    assert sorted(name for name, flags in interfaces.items() if flags & 1) == ["lo"], interfaces
    assert not Path("/proc/net/route").read_text().splitlines()[1:]
    print(f"network interface flags={interfaces}", flush=True)
    assert not Path("/var/run/docker.sock").exists()
    proc_status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines())
    assert int(proc_status["CapEff"], 16) == 0
    assert proc_status["NoNewPrivs"].strip() == "1"
    assert proc_status["Seccomp"].strip() == "2"
    with open("/tmp/parity-probe", "x") as file:
        file.write("synthetic")
    try:
        Path("/outside-tmpfs-parity-probe").touch(exist_ok=False)
    except OSError:
        pass
    else:
        raise AssertionError("Write outside temporary filesystem unexpectedly succeeded")
    print("runtime: loopback-only, uid 65532, no effective capabilities, seccomp, tmpfs and no Docker socket", flush=True)

    fixed, expected_timeout = SOURCES[revision]
    sys.path.insert(0, f"/opt/evalplus-sources/{revision}")
    from evalplus.config import DEFAULT_MIN_TIME_LIMIT
    from evalplus.eval import untrusted_check

    assert DEFAULT_MIN_TIME_LIMIT == expected_timeout, DEFAULT_MIN_TIME_LIMIT
    print(f"revision={revision} default_min_seconds={DEFAULT_MIN_TIME_LIMIT}", flush=True)

    def check(name, code, inputs, expected, verdict, details, *, entry="solve",
              dataset="humaneval", atol=0, fast=False, default_timeout=False):
        options = {} if default_timeout else {"min_time_limit": 0.10}
        start = time.monotonic()
        result = untrusted_check(
            dataset, code, inputs, entry, expected, atol, [0.0] * len(inputs),
            fast_check=fast, **options,
        )
        result = result[0], [bool(item) for item in result[1]]
        print(f"{name}: {result!r} elapsed={time.monotonic() - start:.3f}s", flush=True)
        assert result == (verdict, details), (name, result, verdict, details)

    for fast in (False, True):
        output = ("pass", [True, True]) if fixed else ("fail", [])
        check(
            f"find_zero_alternative_root_fast_{fast}",
            "def find_zero(coefficients): return -1.0",
            [[[-1, 0, 1]], [[-1, 0, 1]]], [1.0, 1.0], *output,
            entry="find_zero", atol=1e-6, fast=fast,
        )
    check("find_zero_nonroot", "def find_zero(coefficients): return 0.0",
          [[[-1, 0, 1]]], [1.0], "fail", [False], entry="find_zero", atol=1e-6)
    check("float_tolerance", "def solve(): return 1.0 + 0.0000005",
          [[]], [1.0], "pass", [True])
    check("float_outside_tolerance", "def solve(): return 1.0001",
          [[]], [1.0], "fail", [False])
    check("float_container_type", "def solve(): return (1.0000005,)",
          [[]], [[1.0]], "fail", [False], atol=1e-6)
    check("mbpp_set_alternative", "def similar_elements(): return [2, 1, 2]",
          [[]], [[1, 2]], "pass", [True], entry="similar_elements", dataset="mbpp")
    check("mbpp_sum_div_alternative", "def sum_div(n): return 0",
          [[6]], [12], "pass", [True], entry="sum_div", dataset="mbpp")
    check("mbpp_non_none", "def check_str(): return 'sentinel'",
          [[]], [True], "pass", [True], entry="check_str", dataset="mbpp")
    check("mbpp_are_equivalent_permissive", "def are_equivalent(): return False",
          [[]], [True], "pass", [True], entry="are_equivalent", dataset="mbpp")
    check("ordered_state", "state = []\ndef solve(x):\n state.append(x)\n return len(state)",
          [[2], [3]], [1, 2], "pass", [True, True])
    check("mutation_visible_via_state",
          "previous = []\ndef solve(xs):\n xs.append(1)\n previous.append(xs)\n"
          " return sum(map(len, previous))",
          [[[0]], [[0, 0]]], [2, 5], "pass", [True, True])
    check("wrong_entry", "def different(): return 1", [[]], [1], "fail", [])
    check("syntax_error", "def solve(:", [[]], [1], "fail", [])
    check("exception_then_success",
          "def solve(x):\n if not x: raise ValueError('synthetic')\n return x",
          [[0], [1]], [0, 1], "fail", [False, True])
    check("explicit_timeout", "import time\ndef solve(): time.sleep(0.25); return 1",
          [[]], [1], "fail", [False])
    status, details = ("pass", [True]) if expected_timeout > 1 else ("fail", [False])
    check("default_timeout_drift", "import time\ndef solve(): time.sleep(1.25); return 1",
          [[]], [1], status, details, default_timeout=True)


if __name__ == "__main__":
    main(sys.argv[1])
