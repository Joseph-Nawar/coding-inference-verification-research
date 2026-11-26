"""Host supervisor for the E2 offline inference-only child process."""
import json
import os
from pathlib import Path
import select
import subprocess
import time
import uuid

from ciresearch.e2_inference import MAX_PROMPT_BYTES, MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES


class E2ModelError(RuntimeError):
    """Selector worker exited, violated its wire contract, or missed a deadline."""


class E2OfflineModel:
    def __init__(self, python: Path, model: Path, evidence: Path, denied_paths):
        self.python = Path(python).resolve(strict=True)
        self.model = Path(model).resolve(strict=True)
        self.evidence = Path(evidence).resolve(strict=True)
        deny = [Path(path).resolve(strict=True) for path in denied_paths]
        if not deny or any(path == self.model or path in self.model.parents for path in deny):
            raise E2ModelError("protected-path denial must be explicit and preserve the model directory")
        locations = " ".join(f"(subpath {json.dumps(str(path))})" for path in deny)
        self.profile = f"(version 1)(allow default)(deny network*)(deny file-read* {locations})"
        self.module_path = Path(__file__).resolve().parents[1]
        self.process = None
        self.stderr = None
        self.buffer = bytearray()

    def __enter__(self):
        stderr_path = self.evidence / f"e2-inference-stderr-{uuid.uuid4().hex}.log"
        self.stderr = stderr_path.open("xb")
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(self.model),
            "PYTHONPATH": str(self.module_path),
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "TOKENIZERS_PARALLELISM": "false",
        }
        try:
            self.process = subprocess.Popen(
                ["/usr/bin/sandbox-exec", "-p", self.profile, str(self.python), "-B",
                 "-m", "ciresearch.e2_inference", str(self.model)],
                env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr,
                bufsize=0)
            os.set_blocking(self.process.stdin.fileno(), False)
            os.set_blocking(self.process.stdout.fileno(), False)
        except BaseException:
            self.stderr.close()
            raise
        return self

    @staticmethod
    def _parse_frame(frame: bytes):
        try:
            value = json.loads(frame.decode("utf-8"), object_pairs_hook=_unique_object,
                               parse_constant=lambda _value: (_ for _ in ()).throw(
                                   E2ModelError("invalid worker JSON constant")))
        except (json.JSONDecodeError, UnicodeError, RecursionError) as error:
            raise E2ModelError("selector worker returned malformed JSON") from error
        if type(value) is not dict:
            raise E2ModelError("selector worker response must be a JSON object")
        return value

    def read(self, deadline, monitor=lambda: None):
        fd = self.process.stdout.fileno()
        while b"\n" not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise E2ModelError("selector inference deadline expired")
            readable, _, _ = select.select([fd], [], [], min(1.0, remaining))
            monitor()
            if not readable:
                if self.process.poll() is not None:
                    raise E2ModelError("selector worker exited before a complete response")
                continue
            try:
                chunk = os.read(fd, min(8192, MAX_RESPONSE_BYTES + 1 - len(self.buffer)))
            except BlockingIOError:
                continue
            if not chunk:
                raise E2ModelError("selector worker closed its response pipe")
            self.buffer.extend(chunk)
            if len(self.buffer) > MAX_RESPONSE_BYTES:
                raise E2ModelError("selector worker response exceeded the output cap")
        frame, _, trailing = self.buffer.partition(b"\n")
        if trailing:
            raise E2ModelError("selector worker emitted unsolicited or multiple frames")
        self.buffer.clear()
        return self._parse_frame(bytes(frame))

    def wait_ready(self, deadline, monitor=lambda: None):
        response = self.read(deadline, monitor)
        if (response.get("status") != "ready" or response.get("model_type") != "qwen2"
                or response.get("quantization_bits") != 4):
            raise E2ModelError("selector worker did not confirm the pinned local model")
        return response

    def generate(self, prompt: str, seed: int, input_tokens: int, deadline,
                 monitor=lambda: None):
        if type(prompt) is not str or len(prompt.encode("utf-8")) > MAX_PROMPT_BYTES:
            raise E2ModelError("frozen prompt is absent or exceeds the registered byte cap")
        request = json.dumps({"prompt": prompt, "seed": seed, "input_tokens": input_tokens},
                             ensure_ascii=False, allow_nan=False,
                             separators=(",", ":")).encode("utf-8") + b"\n"
        if len(request) > MAX_REQUEST_BYTES:
            raise E2ModelError("selector request frame exceeded its cap")
        view = memoryview(request)
        fd = self.process.stdin.fileno()
        while view:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise E2ModelError("selector request write deadline expired")
            _, writable, _ = select.select([], [fd], [], min(1.0, remaining))
            monitor()
            if not writable:
                continue
            try:
                view = view[os.write(fd, view):]
            except BlockingIOError:
                continue
            except BrokenPipeError as error:
                raise E2ModelError("selector worker closed its request pipe") from error
        return self.read(deadline, monitor)

    def close(self):
        if self.process is not None:
            try:
                self.process.stdin.close()
            except OSError:
                pass
            if self.process.poll() is None:
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=3)
            self.process.stdout.close()
            if self.process.poll() is None:
                raise E2ModelError("selector worker cleanup did not complete")
        if self.stderr is not None:
            self.stderr.close()

    def __exit__(self, _kind, _exc, _tb):
        self.close()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise E2ModelError("duplicate worker response key")
        result[key] = value
    return result
