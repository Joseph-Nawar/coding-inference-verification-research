"""Host lifecycle and resource cap for the prompt-only macOS subprocess."""

import json
import os
from pathlib import Path
import subprocess
import time

from ciresearch.sandbox import ready
from ciresearch.wire import MAX_FRAME, read_frame, write_frame


class OfflineModel:
    def __init__(self, python, model, evidence, denied_paths):
        self.python = python
        self.model = model
        self.evidence = evidence
        self.module_path = Path(__file__).resolve().parents[1]
        # Quote data with JSON escaping before constructing a sandbox profile.
        locations = " ".join(f"(subpath {json.dumps(str(p.resolve()))})" for p in denied_paths)
        self.profile = f"(version 1)(allow default)(deny network*)(deny file-read* {locations})"

    def __enter__(self):
        self.stderr = (self.evidence / "inference-stderr.log").open("xb")
        env = {
            "PATH": "/usr/bin:/bin", "HOME": str(self.model.resolve()),
            "PYTHONPATH": str(self.module_path), "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1", "TOKENIZERS_PARALLELISM": "false",
        }
        self.stream = subprocess.Popen(
            ["/usr/bin/sandbox-exec", "-p", self.profile, str(self.python.absolute()),
             "-B", "-m", "ciresearch.inference", str(self.model.resolve())],
            env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr,
            bufsize=0,
        )
        return self

    def read(self, deadline):
        fd = self.stream.stdout.fileno()
        frame = bytearray()
        while not frame.endswith(b"\n"):
            ready(fd, "r", deadline)
            data = os.read(fd, min(4096, MAX_FRAME + 1 - len(frame)))
            if not data:
                raise RuntimeError("offline model exited early")
            frame.extend(data)
            if len(frame) > MAX_FRAME:
                raise RuntimeError("offline model response exceeds cap")
        return read_frame(bytes(frame))

    def generate(self, prompt, seed, deadline):
        self.stream.stdin.write(write_frame({"prompt": prompt, "seed": seed}))
        self.stream.stdin.flush()
        return self.read(deadline)

    def __exit__(self, _kind, _exc, _tb):
        self.stream.stdin.close()
        try:
            self.stream.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.stream.kill()
            self.stream.wait(timeout=5)
        self.stream.stdout.close()
        self.stderr.close()
