"""Hash-bound validation and budget accounting for the registered E1 continuation."""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re

from ciresearch.e1_data import chunk_indices

TOTAL_CALLS = 320
TOTAL_OUTPUT_TOKENS = 245760
TOTAL_SECONDS = 3600.0
PER_CALL_OUTPUT_TOKENS = 768
COMPLETED_CHUNKS = (0, 1, 2, 3)
CONTINUATION_CHUNKS = (4, 5, 6, 7)
EXPECTED_RUN_ID = "E1-registered-bank-v1"
_PARENT_VALIDATION_PIN_ENV = {
    "ledger_sha256": "CIRESEARCH_E1_PARENT_LEDGER_SHA256",
    "manifest_sha256": "CIRESEARCH_E1_PARENT_MANIFEST_SHA256",
    "registration_sha256": "CIRESEARCH_E1_PARENT_REGISTRATION_SHA256",
    "reference_build_sha256": "CIRESEARCH_E1_REFERENCE_BUILD_SHA256",
    "checker_sha256": "CIRESEARCH_E1_CHECKER_SHA256",
}


class ContinuationError(ValueError):
    """The stopped E1 parent or its continuation request is not valid."""


def parent_validation_pins() -> dict[str, str]:
    """Read private parent integrity commitments from required local environment values."""
    pins = {}
    for name, env_name in _PARENT_VALIDATION_PIN_ENV.items():
        value = os.environ.get(env_name)
        if value is None or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ContinuationError(
                f"required local integrity pin {env_name} is missing or malformed")
        pins[name] = value
    return pins


@dataclass(frozen=True)
class ParentRun:
    root: Path
    registration: dict
    ledger_sha256: str
    manifest_sha256: str
    reference_build_sha256: str
    completed_chunks: tuple
    boundary_only_chunks: tuple
    remaining_chunks: tuple
    completed_tasks: tuple
    started_calls: int
    completed_calls: int
    output_tokens: int
    input_tokens: int
    elapsed_seconds: float
    remaining_calls: int
    remaining_output_tokens: int
    remaining_seconds: float
    max_output_tokens_by_call_cap: int


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _read_jsonl(path):
    try:
        return [json.loads(line) for line in path.read_text().splitlines()]
    except (OSError, json.JSONDecodeError) as error:
        raise ContinuationError(f"invalid evidence JSONL: {path.name}") from error


def _hash_tree(directory):
    directory = Path(directory)
    if directory.is_symlink():
        raise ContinuationError("reference build directory is a symlink")
    if not directory.is_dir():
        return None
    records = []
    for path in sorted(p for p in directory.rglob("*") if p.is_file()):
        if path.is_symlink():
            raise ContinuationError("reference build contains a symlink")
        relative = path.relative_to(directory).as_posix()
        records.append(f"{relative}\0{_sha(path.read_bytes())}\n")
    return _sha("".join(records).encode())


def _source_tree_sha256():
    source = Path(__file__).resolve().parent
    records = []
    for path in sorted(source.glob("*.py")):
        records.append(f"{path.name}\0{_sha(path.read_bytes())}\n")
    return _sha("".join(records).encode())


def _verify_manifest(root):
    root = Path(root).resolve()
    manifest_path = root / "EVIDENCE_SHA256SUMS"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ContinuationError("evidence manifest is missing or unsafe")
    if any(path.is_symlink() for path in root.rglob("*")):
        raise ContinuationError("parent contains a symlink")
    manifest_bytes = manifest_path.read_bytes()
    expected = {}
    try:
        lines = manifest_bytes.decode("ascii").splitlines()
    except UnicodeDecodeError as error:
        raise ContinuationError("evidence manifest is not ASCII") from error
    for line in lines:
        fields = line.split(maxsplit=1)
        if len(fields) != 2 or not re.fullmatch(r"[0-9a-f]{64}", fields[0]):
            raise ContinuationError("evidence manifest has an invalid row")
        relative = fields[1].lstrip("*")
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise ContinuationError("evidence manifest path escapes parent root")
        if relative in expected:
            raise ContinuationError("evidence manifest has duplicate paths")
        target = root / path
        try:
            resolved = target.resolve(strict=True)
        except OSError as error:
            raise ContinuationError("evidence manifest names a missing artifact") from error
        if root not in resolved.parents or target.is_symlink() or not resolved.is_file():
            raise ContinuationError("evidence manifest path is unsafe")
        expected[relative] = fields[0]
    actual = {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file() and path != manifest_path
    }
    required = {
        "registration.json", "dev-selected.json", "static-audit.json", "qualified-reference.json",
        "run/ledger.jsonl", "run/visible.jsonl", "run/decisions.jsonl", "run/sealed-labels.jsonl",
    }
    if not required.issubset(expected):
        raise ContinuationError("manifest omits a required E1 registration or run artifact")
    unlisted = set(actual) - set(expected)
    if (any(not path.startswith("reference-build/") for path in unlisted)
            or any(path.startswith("run/") and path not in expected for path in actual)):
        raise ContinuationError("evidence manifest coverage differs from parent files")
    for relative, digest in expected.items():
        if _sha(actual[relative].read_bytes()) != digest:
            raise ContinuationError("evidence manifest hash mismatch")
    return _sha(manifest_bytes), _hash_tree(root / "reference-build")


def write_segment_manifest(segment_root: Path) -> str:
    """Write a final write-once checksum manifest for a completed or stopped segment."""
    root = Path(segment_root).resolve()
    if not root.is_dir() or root.is_symlink():
        raise ContinuationError("continuation segment directory is missing or unsafe")
    manifest = root / "SEGMENT_SHA256SUMS"
    if manifest.exists() or manifest.is_symlink():
        raise ContinuationError("continuation segment manifest already exists")
    if any(path.is_symlink() for path in root.rglob("*")):
        raise ContinuationError("continuation segment contains a symlink")
    files = sorted(path for path in root.rglob("*") if path.is_file())
    lines = [f"{_sha(path.read_bytes())}  {path.relative_to(root).as_posix()}\n" for path in files]
    payload = "".join(lines).encode("ascii")
    fd = os.open(manifest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    return _sha(payload)


def verify_segment_manifest(segment_root: Path) -> str:
    """Verify full segment coverage and all immutable artifact hashes."""
    root = Path(segment_root).resolve()
    manifest = root / "SEGMENT_SHA256SUMS"
    if not manifest.is_file() or manifest.is_symlink():
        raise ContinuationError("continuation segment manifest is missing or unsafe")
    if any(path.is_symlink() for path in root.rglob("*")):
        raise ContinuationError("continuation segment contains a symlink")
    expected = {}
    try:
        lines = manifest.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise ContinuationError("continuation segment manifest is unreadable") from error
    for line in lines:
        fields = line.split(maxsplit=1)
        if len(fields) != 2 or not re.fullmatch(r"[0-9a-f]{64}", fields[0]):
            raise ContinuationError("continuation segment manifest row is malformed")
        relative = fields[1].lstrip("*")
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or not path.parts or relative in expected:
            raise ContinuationError("continuation segment manifest path is unsafe or duplicated")
        target = root / path
        try:
            resolved = target.resolve(strict=True)
        except OSError as error:
            raise ContinuationError("continuation segment manifest names a missing file") from error
        if root not in resolved.parents or not resolved.is_file():
            raise ContinuationError("continuation segment manifest path escapes its directory")
        expected[relative] = fields[0]
    actual = {path.relative_to(root).as_posix(): path for path in root.rglob("*")
              if path.is_file() and path != manifest}
    if set(actual) != set(expected):
        raise ContinuationError("continuation segment manifest coverage differs from segment files")
    for relative, digest in expected.items():
        if _sha(actual[relative].read_bytes()) != digest:
            raise ContinuationError("continuation segment artifact hash mismatch")
    return _sha(manifest.read_bytes())


def _verify_rows(path, expected_by_key, name):
    rows = _read_jsonl(path)
    actual = {}
    for row in rows:
        key = (row.get("task"), row.get("sample"))
        if key in actual:
            raise ContinuationError(f"duplicate {name} identity")
        actual[key] = row.get("id")
    if actual != expected_by_key:
        raise ContinuationError(f"{name} identities differ from registered calls")
    return rows


def validate_parent(parent_root: Path, expected_ledger_sha256: str, *,
                    expected_manifest_sha256=None, expected_registration_sha256=None,
                    expected_checker_sha256=None, expected_reference_build_sha256=None) -> ParentRun:
    """Validate the frozen 20-task resource-stopped E1 run without changing it."""
    root = Path(parent_root).resolve()
    if not re.fullmatch(r"[0-9a-f]{64}", expected_ledger_sha256 or ""):
        raise ContinuationError("expected parent ledger hash must be a SHA-256 digest")
    manifest_hash, reference_build_hash = _verify_manifest(root)
    if expected_manifest_sha256 and manifest_hash != expected_manifest_sha256:
        raise ContinuationError("parent evidence-manifest hash does not match authorization")
    if (expected_reference_build_sha256
            and reference_build_hash != expected_reference_build_sha256):
        raise ContinuationError("parent reference-build hash does not match authorization")
    registration_path = root / "registration.json"
    ledger_path = root / "run" / "ledger.jsonl"
    try:
        registration_bytes = registration_path.read_bytes()
        ledger_bytes = ledger_path.read_bytes()
        registration = json.loads(registration_bytes)
    except (OSError, json.JSONDecodeError) as error:
        raise ContinuationError("parent registration or ledger is unavailable") from error
    ledger_hash = _sha(ledger_bytes)
    if ledger_hash != expected_ledger_sha256:
        raise ContinuationError("parent ledger hash does not match authorization")
    if registration.get("stage") != "E1" or registration.get("run_id") != EXPECTED_RUN_ID:
        raise ContinuationError("parent is not the registered E1 candidate bank")
    if expected_registration_sha256 and _sha(registration_bytes) != expected_registration_sha256:
        raise ContinuationError("parent registration hash does not match authorization")
    if expected_checker_sha256:
        checker_path = root / "reference-build" / "evalplus" / "eval" / "__init__.py"
        if not checker_path.is_file() or _sha(checker_path.read_bytes()) != expected_checker_sha256:
            raise ContinuationError("approved patched EvalPlus checker hash mismatch")
    if registration.get("limits") != {"calls": TOTAL_CALLS, "output_tokens": TOTAL_OUTPUT_TOKENS,
                                       "seconds": TOTAL_SECONDS}:
        raise ContinuationError("parent registration has changed E1 caps")
    if registration.get("parameters") != {"temperature": 0.7, "top_p": 0.95, "max_tokens": 768}:
        raise ContinuationError("parent registration has changed generation parameters")
    if (not isinstance(registration.get("model_files"), dict)
            or not registration.get("model_revision")
            or not registration.get("candidate_image")
            or not registration.get("reference_image")
            or not isinstance(registration.get("prompt_sha256"), list)
            or len(registration["prompt_sha256"]) != 40
            or not isinstance(registration.get("analysis"), dict)):
        raise ContinuationError("parent registration omits a pinned model, prompt, image, or analysis binding")
    seeds = registration.get("seeds")
    if (not isinstance(seeds, list) or len(seeds) != 40
            or any(not isinstance(bank, list) or len(bank) != 8 or len(set(bank)) != 8 for bank in seeds)):
        raise ContinuationError("parent registration has incomplete candidate seeds")

    ledger = _read_jsonl(ledger_path)
    if not ledger or ledger[-1].get("event") != "stopped" or "resource" not in ledger[-1].get("reason", "").lower():
        raise ContinuationError("parent did not end at the registered resource stop")
    terminal = ledger[-1]
    if (terminal.get("calls") != 160 or terminal.get("tasks") != 20
            or terminal.get("tokens") != 41376 or terminal.get("elapsed_seconds") != 1112.9658796659987):
        raise ContinuationError("parent resource-stop counters differ from the accepted E1 record")
    chunks = list(chunk_indices())
    completed = set(chunks[0] + chunks[1] + chunks[2] + chunks[3])
    expected_pairs = {(task, sample) for task in completed for sample in range(8)}
    starts = [row for row in ledger if row.get("event") == "call_started"]
    calls = [row for row in ledger if row.get("event") == "call_complete"]
    for rows, label in ((starts, "started"), (calls, "completed")):
        ids = [row.get("id") for row in rows]
        pairs = [(row.get("task"), row.get("sample")) for row in rows]
        if len(ids) != len(set(ids)) or len(pairs) != len(set(pairs)):
            raise ContinuationError(f"duplicate {label} call identity")
        if len(rows) != 160 or set(pairs) != expected_pairs:
            raise ContinuationError(f"{label} call identities do not cover four registered chunks")
    expected_ids = {}
    for task, sample in expected_pairs:
        seed = seeds[task][sample]
        candidate_id = _sha(f"{registration['run_id']}|{task}|{sample}|{seed}".encode())
        expected_ids[(task, sample)] = candidate_id
    for row in starts:
        key = (row["task"], row["sample"])
        if row["id"] != expected_ids[key]:
            raise ContinuationError("started candidate identity differs from registration")
    for row in calls:
        key = (row["task"], row["sample"])
        if row.get("id") != expected_ids[key] or not 1 <= row.get("tokens", 0) <= PER_CALL_OUTPUT_TOKENS:
            raise ContinuationError("completed candidate identity or token count is invalid")
    if {row["id"] for row in starts} != {row["id"] for row in calls}:
        raise ContinuationError("started and completed call identities do not match")

    chunk_rows = {}
    for row in ledger:
        if "chunk" in row and row.get("event") in {
            "chunk_start", "chunk_bank_frozen", "chunk_decisions_frozen", "chunk_checkpoint"
        }:
            chunk_rows.setdefault(row["chunk"], []).append(row["event"])
    for chunk in COMPLETED_CHUNKS:
        if chunk_rows.get(chunk) != ["chunk_start", "chunk_bank_frozen", "chunk_decisions_frozen", "chunk_checkpoint"]:
            raise ContinuationError("completed chunk ledger order is invalid")
    if (set(chunk_rows) not in (set(COMPLETED_CHUNKS), set(COMPLETED_CHUNKS) | {4})
            or (4 in chunk_rows and chunk_rows[4] != ["chunk_start"])):
        raise ContinuationError("parent contains an unexpected or incomplete chunk")
    for row in ledger:
        if row.get("event") in {"start", "chunk_start", "chunk_checkpoint"}:
            environment = row.get("environment", {})
            if environment.get("container_ids") or environment.get("active_models"):
                raise ContinuationError("parent checkpoint records a live worker or runner")

    _verify_rows(root / "run" / "visible.jsonl", expected_ids, "visible evidence")
    _verify_rows(root / "run" / "sealed-labels.jsonl", expected_ids, "sealed labels")
    decision_rows = _read_jsonl(root / "run" / "decisions.jsonl")
    if len(decision_rows) != 20 or {row.get("task") for row in decision_rows} != completed:
        raise ContinuationError("visible selection decisions do not cover completed tasks")
    if sum(row["tokens"] for row in calls) != terminal["tokens"]:
        raise ContinuationError("parent generated-token counter does not reconcile")
    if sum(row["input_tokens"] for row in calls) != 18904:
        raise ContinuationError("parent input-token counter does not reconcile")

    remaining_calls = TOTAL_CALLS - len(calls)
    remaining_tokens = TOTAL_OUTPUT_TOKENS - terminal["tokens"]
    remaining_seconds = TOTAL_SECONDS - terminal["elapsed_seconds"]
    if (remaining_calls != 160 or remaining_tokens != 204384
            or abs(remaining_seconds - 2487.0341203340013) > 1e-9):
        raise ContinuationError("parent leaves a different E1 cumulative budget")
    return ParentRun(
        root=root,
        registration=registration,
        ledger_sha256=ledger_hash,
        manifest_sha256=manifest_hash,
        reference_build_sha256=reference_build_hash,
        completed_chunks=COMPLETED_CHUNKS,
        boundary_only_chunks=(4,) if 4 in chunk_rows else (),
        remaining_chunks=CONTINUATION_CHUNKS,
        completed_tasks=tuple(sorted(completed)),
        started_calls=len(starts),
        completed_calls=len(calls),
        output_tokens=terminal["tokens"],
        input_tokens=sum(row["input_tokens"] for row in calls),
        elapsed_seconds=terminal["elapsed_seconds"],
        remaining_calls=remaining_calls,
        remaining_output_tokens=remaining_tokens,
        remaining_seconds=remaining_seconds,
        max_output_tokens_by_call_cap=min(remaining_tokens, remaining_calls * PER_CALL_OUTPUT_TOKENS),
    )


def make_continuation_registration(parent: ParentRun, baseline: dict) -> dict:
    """Create the immutable private manifest to write before continuation starts."""
    required = {"pressure", "swap_mib", "free_bytes", "active_models", "container_ids"}
    if not required.issubset(baseline):
        raise ContinuationError("resource baseline is incomplete")
    if (baseline["pressure"] >= 4 or baseline["free_bytes"] < 15 * 2**30
            or baseline["active_models"] or baseline["container_ids"]):
        raise ContinuationError("resource or containment baseline gate failed")
    registered = parent.registration
    prompt_digest = _sha(json.dumps(registered["prompt_sha256"], separators=(",", ":")).encode())
    seed_digest = _sha(json.dumps(registered["seeds"], separators=(",", ":")).encode())
    return {
        "schema": "ciresearch.e1-continuation.v1",
        "segment_id": "E1-continuation-01",
        "parent_ledger_sha256": parent.ledger_sha256,
        "parent_manifest_sha256": parent.manifest_sha256,
        "parent_registration_sha256": _sha((parent.root / "registration.json").read_bytes()),
        "parent_reference_build_sha256": parent.reference_build_sha256,
        "parent_run_id": parent.registration["run_id"],
        "continuation_source_tree_sha256": _source_tree_sha256(),
        "source_bindings": {
            "model_revision": registered["model_revision"],
            "model_files": registered["model_files"],
            "candidate_image": registered["candidate_image"],
            "reference_image": registered["reference_image"],
            "split_sha256": registered["split_sha256"],
            "audit_sha256": registered["audit_sha256"],
            "generator_source_sha256": registered["generator_source_sha256"],
            "prompt_hashes_sha256": prompt_digest,
            "sampling_seeds_sha256": seed_digest,
            "parameters": registered["parameters"],
            "analysis": registered["analysis"],
        },
        "completed_chunks": list(parent.completed_chunks),
        "boundary_only_chunks": list(parent.boundary_only_chunks),
        "chunks": list(parent.remaining_chunks),
        "completed_calls_before": parent.completed_calls,
        "completed_output_tokens_before": parent.output_tokens,
        "elapsed_seconds_before": parent.elapsed_seconds,
        "caps": {
            "calls": parent.remaining_calls,
            "output_tokens": parent.remaining_output_tokens,
            "seconds": parent.remaining_seconds,
            "per_call_output_tokens": PER_CALL_OUTPUT_TOKENS,
            "effective_max_output_tokens": parent.max_output_tokens_by_call_cap,
        },
        "resource_baseline": baseline,
        "protocol": "original E1 registration unchanged; separate evidence segment after resource stop",
    }


def create_continuation_segment(segment_root: Path, parent: ParentRun, baseline: dict,
                                protected_paths, *, chunk_ids, task_ids, calls, tokens, seconds):
    """Create a new write-once segment registration after validating its full scope."""
    root = Path(segment_root).expanduser()
    if root.exists() or root.is_symlink():
        raise ContinuationError("continuation segment path already exists")
    if (parent.completed_chunks != COMPLETED_CHUNKS or parent.remaining_chunks != CONTINUATION_CHUNKS
            or parent.completed_calls != 160 or parent.remaining_calls != 160
            or parent.remaining_output_tokens != 204384
            or abs(parent.remaining_seconds - 2487.0341203340013) > 1e-9):
        raise ContinuationError("incomplete parent does not match the accepted stopped run")
    registration = make_continuation_registration(parent, baseline)
    if tuple(chunk_ids) != CONTINUATION_CHUNKS:
        raise ContinuationError("continuation chunk range differs from the four unexecuted chunks")
    if (calls, tokens, seconds) != (parent.remaining_calls, parent.remaining_output_tokens,
                                    parent.remaining_seconds):
        raise ContinuationError("continuation caps must equal the remaining cumulative E1 budget")

    groups = list(chunk_indices())
    expected_done = {task for group in groups[:4] for task in group}
    expected_remaining = [task for group in groups[4:] for task in group]
    if set(parent.completed_tasks) != expected_done:
        raise ContinuationError("incomplete parent task population")
    requested = tuple(task_ids)
    if len(requested) != len(set(requested)) or set(requested) & expected_done:
        raise ContinuationError("continuation task identity overlap with the parent")
    if requested != tuple(expected_remaining):
        raise ContinuationError("continuation task identities differ from registered chunk order")

    resolved_root = root.resolve()
    parent_root = parent.root.resolve()
    if (resolved_root == parent_root or parent_root in resolved_root.parents
            or resolved_root in parent_root.parents):
        raise ContinuationError("continuation segment must be separate from its parent")
    roots = [Path(item).expanduser().resolve() for item in protected_paths]
    raw_roots = [Path(os.path.abspath(Path(item).expanduser())) for item in protected_paths]
    raw_root = Path(os.path.abspath(root))
    if not roots or not any(resolved_root == item or item in resolved_root.parents for item in roots):
        raise ContinuationError("continuation segment must remain under a protected local path")
    if not any(parent_root == item or item in parent_root.parents for item in roots):
        raise ContinuationError("the parent evidence must remain denied to the candidate process")
    raw_candidates = [item for item in raw_roots if raw_root == item or item in raw_root.parents]
    if not raw_candidates:
        raise ContinuationError("continuation segment must remain under a protected local path")
    raw_ancestor = max(raw_candidates, key=lambda item: len(item.parts))

    expected_candidates = []
    for task in expected_remaining:
        for sample, seed in enumerate(parent.registration["seeds"][task]):
            cid = _sha(f'{parent.registration["run_id"]}|{task}|{sample}|{seed}'.encode())
            expected_candidates.append({"task": task, "sample": sample, "id": cid})
    registration["task_ids"] = expected_remaining
    registration["expected_candidates"] = expected_candidates

    try:
        root.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        cursor = raw_ancestor
        for component in raw_root.relative_to(raw_ancestor).parts:
            cursor = cursor / component
            if cursor.is_symlink():
                raise ContinuationError("continuation path contains a symlink")
        root.mkdir(mode=0o700)
        registration_path = root / "continuation-registration.json"
        payload = (json.dumps(registration, sort_keys=True, separators=(",", ":"), allow_nan=False)
                   + "\n").encode()
        fd = os.open(registration_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as error:
        raise ContinuationError("continuation registration already exists") from error
    return registration
