"""Benign containment fixtures using the production candidate image."""

import os
from pathlib import Path
import tempfile
import unittest

from ciresearch.evaluate import evaluate_panel
from ciresearch.sandbox import Container, SandboxError, docker, run_panel

IMAGE = os.environ.get("CIRESEARCH_CANDIDATE_IMAGE")
EVIDENCE = os.environ.get("CIRESEARCH_CANDIDATE_EVIDENCE")


@unittest.skipUnless(IMAGE and EVIDENCE, "set the immutable candidate image and evidence path")
class CandidateContainerTests(unittest.TestCase):
    def panel(self, suffix, code, cases, duration=0.25, *, hard=None):
        path = Path(EVIDENCE) / (self._testMethodName + suffix)
        found = []
        status = run_panel(IMAGE, path, code, "solve", cases, [duration] * len(cases),
                           lambda _, *result: found.append(result), hard_seconds=hard)
        self.assertEqual((path / "cleanup").read_text(), "verified\n")
        return status, found

    def test_order_and_state_reset(self):
        code = "cache = []\ndef solve(xs):\n xs.append(len(cache))\n cache.append(xs)\n return len(cache)"
        status, found = self.panel("-one", code, [[[2]], [[3]]])
        self.assertEqual((status, found), ("complete", [("ok", 1, [[2, 0]]), ("ok", 2, [[3, 1]])]))
        _, found = self.panel("-two", code, [[[0]]])
        self.assertEqual(found, [("ok", 1, [[0, 0]])])

    def test_exception_timeout_and_unsupported(self):
        code = """
def solve(x):
    if x == 0: raise ValueError("synthetic")
    if x == 1:
        while True: pass
    return object()
"""
        _, found = self.panel("", code, [[0], [1], [2]])
        self.assertEqual([item[0] for item in found], ["exception", "timeout", "unsupported"])

    def test_bad_program_and_flood(self):
        status, _ = self.panel("-syntax", "def solve(:", [[]])
        self.assertEqual(status, "invalid_program")
        _, found = self.panel("-flood", "def solve(): print('x'*70000)", [[]])
        self.assertEqual(found[0][0], "output_limit")

    def test_malformed_response_and_cleanup(self):
        with self.assertRaisesRegex(SandboxError, "frame|response"):
            self.panel("", "import os\ndef solve(): os.write(1, b'invalid-json\\n'); return 0", [[]])
        self.assertTrue((Path(EVIDENCE) / self._testMethodName / "cleanup").exists())

    def test_native_output_cap_and_cleanup(self):
        with self.assertRaisesRegex(SandboxError, "output exceeded"):
            self.panel("", "import os\ndef solve(): os.write(1, b'x'*70000); return 0", [[]])
        self.assertTrue((Path(EVIDENCE) / self._testMethodName / "cleanup").exists())

    def test_future_input_is_not_queued(self):
        code = "import select\ndef solve(x): return (x, bool(select.select([0], [], [], 0)[0]))"
        _, found = self.panel("", code, [[1], [2], [3]])
        self.assertEqual([result[1] for result in found], [(1, False), (2, False), (3, False)])

    def test_supervisor_expiry_and_cleanup(self):
        with self.assertRaisesRegex(SandboxError, "deadline expired"):
            self.panel("", "import time\ndef solve(): time.sleep(10)", [[]], 12, hard=0.6)
        self.assertTrue((Path(EVIDENCE) / self._testMethodName / "cleanup").exists())
        self.assertFalse(docker("ps", "-aq", "--filter", "name=ciresearch-panel-"))

    def test_single_container_concurrency_limit(self):
        folder = Path(EVIDENCE) / self._testMethodName
        folder.mkdir()
        with Container(IMAGE, folder / "holder"):
            with self.assertRaisesRegex(SandboxError, "concurrency limit"):
                with Container(IMAGE, folder / "blocked"):
                    self.fail("second panel was allowed")
        self.assertTrue((folder / "holder" / "cleanup").exists())

    def test_labels_are_read_only_after_container_removal(self):
        evidence = Path(EVIDENCE) / self._testMethodName

        class LabelCanary:
            def __len__(self):
                return 2

            def __getitem__(self, index):
                if not (evidence / "cleanup").exists():
                    raise AssertionError("protected label read during execution")
                return [1, 2][index]

        verdict = evaluate_panel(
            IMAGE, evidence, "humaneval", "def solve(x): return x", "solve", 0,
            [[1], [2]], LabelCanary(), [0.0, 0.0],
        )
        self.assertEqual(verdict["details"], [True, True])

    def test_containment_and_label_canaries(self):
        with tempfile.TemporaryDirectory() as parent:
            sentinel = Path(parent) / "host-canary"
            sentinel.write_text("reference-canary-value")
            code = """
import errno, os, socket, subprocess
from pathlib import Path
def solve(host):
    assert os.getuid() == 65532
    assert not Path(host).exists()
    assert not Path("/var/run/docker.sock").exists()
    assert not Path("/opt/evalplus-sources").exists()
    assert "CIRESEARCH_SECRET_CANARY" not in os.environ
    assert Path("/sys/fs/cgroup/memory.max").read_text().strip() == "536870912"
    assert Path("/sys/fs/cgroup/memory.swap.max").read_text().strip() == "0"
    assert Path("/sys/fs/cgroup/pids.max").read_text().strip() == "32"
    flags = {name: int(Path(f"/sys/class/net/{name}/flags").read_text(), 16)
             for _, name in socket.if_nameindex()}
    assert sorted(name for name, flag in flags.items() if flag & 1) == ["lo"]
    try:
        socket.create_connection(("192.0.2.1", 9), timeout=0.05)
    except OSError:
        pass
    else:
        return "unexpected network access"
    try:
        socket.getaddrinfo("p1-namespace-probe.invalid", None)
    except socket.gaierror:
        pass
    else:
        return "unexpected DNS result"
    status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines())
    assert int(status["CapEff"], 16) == 0
    assert status["NoNewPrivs"].strip() == "1"
    assert status["Seccomp"].strip() == "2"
    try:
        subprocess.run(["/bin/sh", "-c", "exit 0"], check=True)
    except PermissionError as exc:
        assert exc.errno == errno.EPERM
    else:
        return "unexpected shell access"
    Path("/tmp/synthetic").touch()
    try:
        Path("/synthetic").touch()
    except OSError:
        return "bounded"
"""
            os.environ["CIRESEARCH_SECRET_CANARY"] = "reference-canary-value"
            try:
                _, found = self.panel("", code, [[str(sentinel)]])
            finally:
                del os.environ["CIRESEARCH_SECRET_CANARY"]
        self.assertEqual(found[0][:2], ("ok", "bounded"))
        data = (Path(EVIDENCE) / self._testMethodName / "requests.jsonl").read_bytes()
        self.assertNotIn(b"reference-canary-value", data)
        self.assertEqual(len(data.splitlines()), 2)
