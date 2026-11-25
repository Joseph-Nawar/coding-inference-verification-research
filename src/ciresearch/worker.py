"""Candidate worker entry point. Run only inside the restricted ARM64 image."""

import contextlib
import ctypes
import errno
import io
import os
from pathlib import Path
import platform
import signal
import sys

from ciresearch.wire import MAX_FRAME, WireError, pack, read_frame, unpack, write_frame


class Filter(ctypes.Structure):
    _fields_ = [("code", ctypes.c_ushort), ("jt", ctypes.c_ubyte),
                ("jf", ctypes.c_ubyte), ("value", ctypes.c_uint)]


class FilterProgram(ctypes.Structure):
    _fields_ = [("length", ctypes.c_ushort), ("filters", ctypes.POINTER(Filter))]


def disable_exec():
    # ARM64 Linux syscall numbers for execve and execveat. Keep Docker's filter
    # and add an irreversible filter after starting the Python interpreter.
    instructions = (Filter * 5)(
        (0x20, 0, 0, 0),     # load syscall number
        (0x15, 1, 0, 221),   # execve
        (0x15, 0, 1, 281),   # execveat
        (0x06, 0, 0, 0x00050000 | errno.EPERM),
        (0x06, 0, 0, 0x7FFF0000),
    )
    program = FilterProgram(len(instructions), instructions)
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(22, 2, ctypes.byref(program), 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "failed to install worker seccomp filter")


class OutputLimit(Exception):
    pass


class CaseTimeout(Exception):
    pass


class OutputCounter(io.TextIOBase):
    def __init__(self):
        self.count = 0

    def write(self, value):
        self.count += len(value.encode("utf-8", "replace"))
        if self.count >= MAX_FRAME:
            raise OutputLimit
        return len(value)


def alarm_handler(_signal, _frame):
    raise CaseTimeout


def execute(function, args, duration):
    counter = OutputCounter()
    signal.signal(signal.SIGALRM, alarm_handler)
    try:
        signal.setitimer(signal.ITIMER_REAL, duration)
        with contextlib.redirect_stdout(counter), contextlib.redirect_stderr(counter):
            result = function(*args)
    except OutputLimit:
        return {"status": "output_limit"}
    except CaseTimeout:
        return {"status": "timeout"}
    except MemoryError:
        return {"status": "memory_limit"}
    except BaseException:
        return {"status": "exception"}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    if counter.count >= MAX_FRAME:
        return {"status": "output_limit"}
    try:
        response = {"status": "ok", "value": pack(result), "args_after": pack(args)}
        if len(write_frame(response)) + counter.count >= MAX_FRAME:
            return {"status": "output_limit"}
        return response
    except WireError:
        return {"status": "unsupported"}


def main():
    if (sys.platform != "linux" or platform.machine() != "aarch64" or os.getuid() != 65532
            or not Path("/.dockerenv").is_file()):
        raise SystemExit("restricted Linux ARM64 environment required")
    disable_exec()
    receive = sys.stdin.buffer
    send = sys.stdout.buffer
    sys.stdin = io.StringIO("")
    init = read_frame(receive.readline(MAX_FRAME + 1))
    if type(init) is not dict or set(init) != {"code", "entry"}:
        raise WireError("invalid initialization")
    namespace = {}
    counter = OutputCounter()
    try:
        with contextlib.redirect_stdout(counter), contextlib.redirect_stderr(counter):
            exec(compile(init["code"], "<candidate>", "exec"), namespace)
            function = namespace[init["entry"]]
    except OutputLimit:
        send.write(write_frame({"status": "output_limit"}))
        send.flush()
        return
    except MemoryError:
        send.write(write_frame({"status": "memory_limit"}))
        send.flush()
        return
    except (SyntaxError, KeyError):
        send.write(write_frame({"status": "invalid_program"}))
        send.flush()
        return
    except BaseException:
        send.write(write_frame({"status": "exception"}))
        send.flush()
        return
    if counter.count >= MAX_FRAME:
        send.write(write_frame({"status": "output_limit"}))
        send.flush()
        return
    send.write(write_frame({"status": "ready"}))
    send.flush()
    while frame := receive.readline(MAX_FRAME + 1):
        case = read_frame(frame)
        if type(case) is not dict or set(case) != {"args", "seconds"}:
            raise WireError("invalid case")
        args = unpack(case["args"])
        response = execute(function, args, case["seconds"])
        send.write(write_frame(response))
        send.flush()


if __name__ == "__main__":
    main()
