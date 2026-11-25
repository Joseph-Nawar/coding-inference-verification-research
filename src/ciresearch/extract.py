"""Extract the first Python fenced block or a full raw program without executing it."""

import ast
import re

FENCE = re.compile(r"(?ms)^\s*```(?:python|py)?[ \t]*\r?\n(.*?)^\s*```[ \t]*$")


def extract(text, entry):
    block = FENCE.search(text)
    code = (block.group(1) if block else text).strip()
    try:
        parsed = ast.parse(code)
    except (SyntaxError, ValueError, RecursionError):
        return "invalid_syntax", code
    if not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
               and node.name == entry for node in parsed.body):
        return "missing_entry", code
    return "ok", code
