"""Bounded transport for a restricted set of exact Python builtin values."""

import json
import re

MAX_FRAME = 64 * 1024
MAX_DEPTH = 32
MAX_NODES = 30000

COLLECTIONS = {"l": list, "t": tuple, "S": set, "F": frozenset}
TAGS = {kind: tag for tag, kind in COLLECTIONS.items()}


class WireError(ValueError):
    pass


def reject_constant(_):
    raise WireError("invalid JSON constant")


def unique_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise WireError("duplicate frame key")
    return result


def read_frame(frame):
    if not frame.endswith(b"\n") or len(frame) > MAX_FRAME:
        raise WireError("invalid frame length or terminator")
    try:
        return json.loads(frame.decode("utf-8"), object_pairs_hook=unique_object,
                          parse_constant=reject_constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise WireError("malformed frame") from exc


def write_frame(payload):
    try:
        data = json.dumps(payload, ensure_ascii=True, allow_nan=False,
                          separators=(",", ":")).encode("ascii") + b"\n"
    except (ValueError, TypeError, RecursionError) as exc:
        raise WireError("invalid JSON payload") from exc
    if len(data) > MAX_FRAME:
        raise WireError("frame too large")
    return data


def traversal(operation):
    remaining = MAX_NODES

    def visit(value, depth=0):
        nonlocal remaining
        remaining -= 1
        if depth > MAX_DEPTH or remaining < 0:
            raise WireError("typed value exceeds depth or node budget")
        return operation(value, lambda child: visit(child, depth + 1))
    return visit


def encode(value, visit):
    kind = type(value)
    if value is None:
        return ["n"]
    if kind is bool:
        return ["b", value]
    if kind is str:
        return ["s", value]
    if kind is int:
        if value.bit_length() > 13000:
            raise WireError("integer outside wire budget")
        return ["i", str(value)]
    if kind is float:
        return ["f", value.hex()]
    if kind is complex:
        return ["c", value.real.hex(), value.imag.hex()]
    if kind is bytes:
        return ["B", value.hex()]
    if kind is dict:
        return ["d", [[visit(k), visit(v)] for k, v in value.items()]]
    if kind in TAGS:
        entries = [visit(item) for item in value]
        if kind in (set, frozenset):
            entries.sort(key=write_frame)
        return [TAGS[kind], entries]
    raise WireError("unsupported builtin type")


def decode(node, visit):
    if type(node) is not list or not node or type(node[0]) is not str:
        raise WireError("typed value must be a tagged list")
    tag = node[0]
    if tag == "n" and len(node) == 1:
        return None
    if tag == "c" and len(node) == 3 and all(type(i) is str and len(i) < 64 for i in node[1:]):
        return complex(*(float.fromhex(i) for i in node[1:]))
    if len(node) != 2:
        raise WireError("invalid arity")
    value = node[1]
    if tag == "b" and type(value) is bool:
        return value
    if tag == "s" and type(value) is str:
        return value
    if tag == "i" and type(value) is str and len(value) < 4000 and re.fullmatch(r"-?(?:0|[1-9][0-9]*)", value):
        return int(value)
    if tag == "f" and type(value) is str and len(value) < 64:
        return float.fromhex(value)
    if tag == "B" and type(value) is str and re.fullmatch(r"(?:[0-9a-f]{2})*", value):
        return bytes.fromhex(value)
    if type(value) is list:
        if tag in COLLECTIONS:
            return COLLECTIONS[tag](visit(item) for item in value)
        if tag == "d" and all(type(pair) is list and len(pair) == 2 for pair in value):
            result = {visit(k): visit(v) for k, v in value}
            if len(result) == len(value):
                return result
    raise WireError("unsupported or invalid typed value")


def pack(value):
    return traversal(encode)(value)


def unpack(node):
    try:
        return traversal(decode)(node)
    except (TypeError, ValueError, OverflowError) as exc:
        raise WireError("invalid typed value") from exc
