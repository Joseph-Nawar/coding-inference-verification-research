"""Verify and apply the researcher-approved EvalPlus source amendment."""

import hashlib
from pathlib import Path
import sys

RELEASE = "e5d0ed0bab96280b60b637ec7f15b5e4841b0cb2"
FIX = "6eb1e199c2e370518e7bf3e8eee6322c2b23c89c"
VERSION = "evalplus-0.3.1+research.findzero.1"
BEFORE = "76857b678cddca08dcaf54d7927b9a77826715cf657654ca5baf6c2b267f4c34"
AFTER = "3c833c39b842e33f251c83db4347e0a95191909f23b390c12d73ab29a28a4daf"


def amend_checker(source):
    if hashlib.sha256(source).hexdigest() != BEFORE:
        raise ValueError("release checker hash mismatch")
    assertion = b"                            assert abs(_poly(*inp, out)) <= atol\r\n"
    additions = b"                            details[i] = True\r\n                            progress.value += 1\r\n"
    patched = source.replace(assertion, assertion + additions, 1)
    if hashlib.sha256(patched).hexdigest() != AFTER:
        raise ValueError("approved patched checker hash mismatch")
    return patched


if __name__ == "__main__":
    original, destination = map(Path, sys.argv[1:])
    patched = amend_checker(original.read_bytes())
    with destination.open("xb") as handle:
        handle.write(patched)
