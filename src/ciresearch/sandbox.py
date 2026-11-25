"""Host supervision for one ephemeral, ordered candidate panel."""

import fcntl
import json
import os
import re
import select
import subprocess
import tempfile
import time
import uuid

from ciresearch.wire import MAX_FRAME, WireError, pack, read_frame, unpack, write_frame

DOCKER = ("docker", "--context", "desktop-linux")
TMPFS = "rw,nosuid,nodev,noexec,size=64m,mode=1777"
MEMORY = 512 * 1024 * 1024
PROFILE = {
    "NetworkMode": "none", "ReadonlyRootfs": True, "Privileged": False, "CapDrop": ["ALL"],
    "SecurityOpt": ["no-new-privileges"], "PidsLimit": 32, "Memory": MEMORY, "MemorySwap": MEMORY,
    "NanoCpus": 1_000_000_000, "Tmpfs": {"/tmp": TMPFS},
}
FAILURES = {"timeout", "exception", "invalid_program", "output_limit", "memory_limit", "unsupported"}


class SandboxError(RuntimeError):
    pass


def docker(*args):
    completed = subprocess.run([*DOCKER, *args], text=True, capture_output=True, timeout=15)
    if completed.returncode:
        raise SandboxError(f"docker {args[0]} failed: {completed.stderr.strip()[:1600]}")
    return completed.stdout.strip()


def verify_profile(record, image):
    host = record["HostConfig"]
    if (any(host.get(k) != v for k, v in PROFILE.items())
            or any(host.get(k) for k in ("Binds", "Devices", "PidMode", "CapAdd", "VolumesFrom"))
            or host.get("IpcMode") == "host" or host.get("UTSMode") == "host"
            or host.get("LogConfig", {}).get("Type") != "none" or record["Mounts"]
            or record["Config"]["User"] != "65532:65532" or record["Image"] != image):
        raise SandboxError("container configuration did not match the registered profile")


def ready(fd, mode, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0 or not any(select.select(
            [fd] if mode == "r" else [], [fd] if mode == "w" else [], [], remaining)[:2]):
        raise SandboxError("supervisor deadline expired")


class Container:
    def __init__(self, image, evidence, *, entry_command=()):
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
            raise ValueError("immutable image ID required")
        self.image = image
        self.evidence = evidence
        self.entry_command = entry_command
        self.name = f"ciresearch-panel-{uuid.uuid4().hex}"
        self.process = None
        self.lock_fd = None
        self.requests = self.responses = None
        self.target = self.name
        self.buffer = b""

    def __enter__(self):
        self.evidence.mkdir(mode=0o700)
        lock = os.path.join(tempfile.gettempdir(), "ciresearch-panel.lock")
        self.lock_fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            os.close(self.lock_fd)
            self.lock_fd = None
            raise SandboxError("registered single-container concurrency limit") from exc
        try:
            local = json.loads(docker("image", "inspect", self.image))[0]
            if local["Id"] != self.image or local["Os"] != "linux" or local["Architecture"] != "arm64":
                raise SandboxError("expected immutable Linux ARM64 image")
            self.target = docker(
                "create", "--name", self.name, "--platform", "linux/arm64",
                "--pull", "never", "-i", "--network", "none", "--read-only", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges", "--user", "65532:65532",
                "--pids-limit", "32", "--memory", "512m", "--memory-swap", "512m",
                "--cpus", "1", "--tmpfs", f"/tmp:{TMPFS}", "--log-driver", "none",
                *self.entry_command, self.image,
            )
            inspected = docker("inspect", self.target)
            (self.evidence / "inspect.json").write_text(inspected + "\n")
            verify_profile(json.loads(inspected)[0], self.image)
            self.requests = (self.evidence / "requests.jsonl").open("xb")
            self.responses = (self.evidence / "responses.jsonl").open("xb")
            self.process = subprocess.Popen(
                [*DOCKER, "start", "--attach", "--interactive", self.target],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                bufsize=0,
            )
            os.set_blocking(self.process.stdin.fileno(), False)
            os.set_blocking(self.process.stdout.fileno(), False)
            return self
        except BaseException:
            self.close()
            raise

    def exchange(self, payload, deadline):
        if self.buffer:
            raise SandboxError("unsolicited frame before request")
        wire = memoryview(write_frame(payload))
        self.requests.write(wire)
        fd = self.process.stdin.fileno()
        while wire:
            ready(fd, "w", deadline)
            try:
                wire = wire[os.write(fd, wire):]
            except BlockingIOError:
                continue
            except BrokenPipeError as exc:
                raise SandboxError("candidate input pipe closed unexpectedly") from exc
        fd = self.process.stdout.fileno()
        while b"\n" not in self.buffer:
            ready(fd, "r", deadline)
            try:
                chunk = os.read(fd, min(4096, MAX_FRAME + 1 - len(self.buffer)))
            except BlockingIOError:
                continue
            if not chunk:
                raise SandboxError("candidate exited before reporting a result")
            self.responses.write(chunk)
            self.buffer += chunk
            if len(self.buffer) > MAX_FRAME:
                raise SandboxError("candidate output exceeded the frame cap")
        frame, _, self.buffer = self.buffer.partition(b"\n")
        if self.buffer:
            raise SandboxError("candidate emitted multiple or trailing frames")
        try:
            return read_frame(frame + b"\n")
        except WireError as exc:
            raise SandboxError("malformed candidate response") from exc

    def close(self):
        try:
            self.remove()
        finally:
            try:
                for stream in (self.requests, self.responses):
                    if stream is not None:
                        stream.close()
            finally:
                if self.lock_fd is not None:
                    os.close(self.lock_fd)
                    self.lock_fd = None

    def remove(self):
        if self.process is not None:
            self.process.stdin.close()
            if self.process.poll() is None:
                self.process.kill()
            self.process.wait(timeout=3)
            self.process.stdout.close()
        matching = docker("ps", "-aq", "--filter", f"name=^/{self.name}$")
        if matching:
            state = docker("inspect", "--format", "{{json .State}}", self.target)
            (self.evidence / "state-before-removal.json").write_text(state + "\n")
            docker("rm", "-f", self.target)
        if docker("ps", "-aq", "--filter", f"name=^/{self.name}$"):
            raise SandboxError("container cleanup failed")
        (self.evidence / "cleanup").write_text("verified\n")

    def __exit__(self, _kind, _exc, _tb):
        self.close()


def validate_response(response, initializing=False):
    if type(response) is not dict or type(response.get("status")) is not str:
        raise SandboxError("candidate sent an invalid response object")
    status = response["status"]
    if status == "ok" and not initializing and set(response) == {"status", "value", "args_after"}:
        try:
            args = unpack(response["args_after"])
            if type(args) not in (list, tuple):
                raise WireError("post-call positional arguments must be a sequence")
            return status, unpack(response["value"]), args
        except WireError as exc:
            raise SandboxError("invalid typed candidate response") from exc
    if set(response) == {"status"} and (status in FAILURES or (status == "ready" and initializing)):
        return status, None, None
    raise SandboxError("unexpected candidate response or status")


def run_panel(image, evidence, code, entry, cases, seconds, observe, *,
              hard_seconds=None, halt=lambda: False):
    """Send one input at a time. The callback never sends a verdict to the worker."""
    if len(cases) != len(seconds) or not seconds or any(t <= 0 for t in seconds):
        raise ValueError("panel timing mismatch")
    with Container(image, evidence) as container:
        now = time.monotonic()
        deadline = now + (min(60, sum(seconds)) + 3 if hard_seconds is None else hard_seconds)
        init = validate_response(container.exchange(
            {"code": code, "entry": entry}, min(now + 8, deadline)), initializing=True)
        if init[0] != "ready":
            return init[0]
        for index, (case, duration) in enumerate(zip(cases, seconds)):
            if halt():
                raise SandboxError("stage cancelled")
            limit = min(deadline, time.monotonic() + duration + 0.30)
            response = container.exchange({"args": pack(case), "seconds": duration}, limit)
            observe(index, *validate_response(response))
    return "complete"
