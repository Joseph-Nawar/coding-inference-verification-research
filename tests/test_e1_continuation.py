"""Synthetic-only integrity tests for immutable E1 continuation segments."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from dataclasses import replace
from types import SimpleNamespace

from ciresearch.e1_data import chunk_indices


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows))


def write_manifest(root):
    paths = sorted(p for p in root.rglob("*") if p.is_file() and p.name != "EVIDENCE_SHA256SUMS")
    lines = []
    for path in paths:
        lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root).as_posix()}\n")
    (root / "EVIDENCE_SHA256SUMS").write_text("".join(lines))


def write_segment_manifest(root):
    from ciresearch.e1_continuation import write_segment_manifest as write
    path = root / "SEGMENT_SHA256SUMS"
    if path.exists():
        path.unlink()
    return write(root)


def synthetic_tree_hash(directory):
    rows = []
    for path in sorted(p for p in directory.rglob("*") if p.is_file()):
        rows.append(f"{path.relative_to(directory).as_posix()}\0"
                    f"{hashlib.sha256(path.read_bytes()).hexdigest()}\n")
    return hashlib.sha256("".join(rows).encode()).hexdigest()


def synthetic_segment(root, parent, mutation=None):
    from ciresearch.e1_continuation import create_continuation_segment
    segment = root / "continuation"
    baseline = {"pressure": 2, "swap_mib": 700.0, "free_bytes": 40 * 2**30,
                "active_models": [], "container_ids": []}
    groups = list(chunk_indices())
    remaining_groups = groups[4:]
    tasks = tuple(task for group in remaining_groups for task in group)
    registration = create_continuation_segment(
        segment, parent, baseline, [root, parent.root], chunk_ids=(4, 5, 6, 7), task_ids=tasks,
        calls=160, tokens=204384, seconds=2487.0341203340013)
    raw_ledger = [{"event": "continuation_start", "parent_ledger_sha256": parent.ledger_sha256,
                   "registration_sha256": hashlib.sha256(
                       (segment / "continuation-registration.json").read_bytes()).hexdigest(),
                   "starting_calls": parent.completed_calls,
                   "starting_tokens": parent.output_tokens,
                   "starting_input_tokens": parent.input_tokens,
                   "starting_tasks": len(parent.completed_tasks),
                   "starting_elapsed_seconds": parent.elapsed_seconds,
                   "environment": baseline}]
    visible, decisions, labels = [], [], []
    expected = list(registration["expected_candidates"])
    selected_tasks = {}
    for chunk, group in enumerate(groups[4:], start=4):
        raw_ledger.append({"event": "chunk_start", "chunk": chunk,
                           "environment": {"pressure": 2, "swap_mib": 700.0,
                                           "free_bytes": 40 * 2**30,
                                           "active_models": [], "container_ids": []}})
        candidate_group = [r for r in expected if r["task"] in group]
        for entry in candidate_group:
            cid, task, sample = entry["id"], entry["task"], entry["sample"]
            code = f"def solution(x): return {task + sample}"
            raw_ledger.append({"event": "call_started", "task": task, "sample": sample, "id": cid})
            raw_ledger.append({"event": "call_complete", "task": task, "sample": sample, "id": cid,
                               "parse": "ok", "code_hash": hashlib.sha256(code.encode()).hexdigest(),
                               "tokens": 10, "input_tokens": 20})
            chunk_dir = segment / f"chunk-{chunk:02d}"
            chunk_dir.mkdir(mode=0o700, exist_ok=True)
            (chunk_dir / f"{cid}.json").write_text(json.dumps({
                "status": "ok", "output_tokens": 10, "input_tokens": 20,
                "prefill_tokens_per_second": 100.0, "decode_tokens_per_second": 50.0,
                "peak_mlx_bytes": 1000, "host_peak_rss_bytes": 2000, "wall_seconds": 0.2}))
            (chunk_dir / f"{cid}-code.json").write_text(json.dumps({"parse": "ok", "code": code}))
        if mutation == "duplicate_candidate" and chunk == 4:
            raw_ledger.append(dict(raw_ledger[-1]))
        raw_ledger.append({"event": "chunk_bank_frozen", "chunk": chunk})
        for task in group:
            selected_tasks[task] = True
            for sample in range(8):
                entry = next(r for r in expected if r["task"] == task and r["sample"] == sample)
                y = (task + sample) % 3 == 0
                v = sample % 2 == 0
                visible.append({"task": task, "sample": sample, "id": entry["id"], "evidence": {
                    "base": {"pass": v, "v_count": int(v), "signature": f"sig-{sample % 2}",
                             "execution": [], "details": [], "initialization": "complete"}}})
                labels.append({"task": task, "sample": sample, "id": entry["id"], "y": y,
                               "h": y, "qualified_y": y,
                               "outcomes": {"plus": {"pass": y, "execution": [], "details": [],
                                                      "initialization": "complete"}}})
            decisions.append({"task": task, "decisions": {
                str(k): {"pass_count": 0, "consensus": 0} for k in (1, 2, 4, 8)}})
        raw_ledger.append({"event": "chunk_decisions_frozen", "chunk": chunk})
        raw_ledger.append({"event": "chunk_labels_joined", "chunk": chunk})
        raw_ledger.append({"event": "chunk_checkpoint", "chunk": chunk,
                           "completed_tasks": 20 + 5 * (chunk - 3),
                           "chunk_artifact_sha256": synthetic_tree_hash(segment / f"chunk-{chunk:02d}"),
                           "environment": {"pressure": 2, "swap_mib": 700.0,
                                           "free_bytes": 40 * 2**30,
                                           "active_models": [], "container_ids": []},
                           "wall": 10.0, "forecast_seconds": 100.0,
                           "reference_audit_seconds": 86.0})
    if mutation == "missing_task":
        # Remove all candidate records for the final registered task.
        task = tasks[-1]
        raw_ledger = [r for r in raw_ledger if not (r.get("task") == task)]
        visible = [r for r in visible if r["task"] != task]
        labels = [r for r in labels if r["task"] != task]
        decisions = [r for r in decisions if r["task"] != task]
    if mutation == "unexpected_sample":
        raw_ledger.append({"event": "call_complete", "task": tasks[0], "sample": 8,
                           "id": "unexpected-sample"})
    if mutation == "incomplete_label":
        labels.pop()
    if mutation == "label_before_decision":
        decision_index = next(i for i, row in enumerate(raw_ledger)
                              if row["event"] == "chunk_decisions_frozen" and row["chunk"] == 4)
        label_index = next(i for i, row in enumerate(raw_ledger)
                           if row["event"] == "chunk_labels_joined" and row["chunk"] == 4)
        raw_ledger[decision_index], raw_ledger[label_index] = raw_ledger[label_index], raw_ledger[decision_index]
    if mutation == "checkpoint_artifact":
        artifact = next((segment / "chunk-04").glob("*.json"))
        artifact.write_text(artifact.read_text() + " ")
    raw_ledger.append({"event": "global_freeze", "calls": 320, "tokens": 42976,
                       "input_tokens": 22104,
                       "tasks": 40, "elapsed_seconds": 3599.9658796659987,
                       "segment_calls": 160, "segment_tokens": 1600,
                       "segment_input_tokens": 3200,
                       "segment_tasks": 20, "segment_elapsed_seconds": 2487.0})
    write_jsonl(segment / "ledger.jsonl", raw_ledger)
    write_jsonl(segment / "visible.jsonl", visible)
    write_jsonl(segment / "decisions.jsonl", decisions)
    write_jsonl(segment / "sealed-labels.jsonl", labels)
    write_segment_manifest(segment)
    if mutation == "manifest_artifact":
        (segment / "visible.jsonl").write_text((segment / "visible.jsonl").read_text() + "\n")
    return segment


def synthetic_parent(root, mutation=None):
    run = root / "run"
    run.mkdir(parents=True)
    seeds = [[task * 8 + sample + 1 for sample in range(8)] for task in range(40)]
    lock = {
        "stage": "E1",
        "run_id": "E1-registered-bank-v1",
        "model_revision": "sha256:" + "a" * 64,
        "model_files": {"model.safetensors": "b" * 64},
        "candidate_image": "sha256:" + "c" * 64,
        "reference_image": "sha256:" + "d" * 64,
        "split_sha256": "e" * 64,
        "audit_sha256": "f" * 64,
        "generator_source_sha256": "1" * 64,
        "prompt_sha256": ["2" * 64 for _ in range(40)],
        "seeds": seeds,
        "limits": {"calls": 320, "output_tokens": 245760, "seconds": 3600},
        "parameters": {"temperature": 0.7, "top_p": 0.95, "max_tokens": 768},
        "analysis": {"seed": 11252026, "stratified_bootstrap_replicates": 2000},
    }
    (root / "registration.json").write_text(json.dumps(lock, separators=(",", ":")))
    (root / "dev-selected.json").write_text("[]")
    (root / "static-audit.json").write_text("{}")
    (root / "qualified-reference.json").write_text("[]")
    ledger = [{"event": "start", "environment": {"container_ids": [], "active_models": []}}]
    visible, decisions, labels = [], [], []
    ordinal = 0
    completed = 0
    for chunk, tasks in enumerate(chunk_indices()):
        if chunk > 3:
            continue
        ledger.append({"event": "chunk_start", "chunk": chunk, "environment": {"container_ids": [], "active_models": []}})
        chunk_dir = run / f"chunk-{chunk:02d}"
        chunk_dir.mkdir()
        for task in tasks:
            for sample, seed in enumerate(seeds[task]):
                cid = hashlib.sha256(f"{lock['run_id']}|{task}|{sample}|{seed}".encode()).hexdigest()
                code = f"def solution(x): return {task + sample}"
                start = {"event": "call_started", "task": task, "sample": sample, "id": cid}
                token_count = 259 if ordinal < 96 else 258
                input_count = 119 if ordinal < 24 else 118
                done = {"event": "call_complete", "task": task, "sample": sample, "id": cid,
                        "parse": "ok", "tokens": token_count, "input_tokens": input_count,
                        "code_hash": hashlib.sha256(code.encode()).hexdigest()}
                if mutation != "missing_start" or ordinal != 0:
                    ledger.append(start)
                if mutation != "missing_complete" or ordinal != 0:
                    ledger.append(done)
                if mutation == "duplicate_start" and ordinal == 0:
                    ledger.append(start)
                (chunk_dir / f"{cid}.json").write_text(json.dumps({
                    "status": "ok", "output_tokens": token_count, "input_tokens": input_count,
                    "prefill_tokens_per_second": 100.0, "decode_tokens_per_second": 50.0,
                    "peak_mlx_bytes": 1000, "host_peak_rss_bytes": 2000, "wall_seconds": 0.2}))
                (chunk_dir / f"{cid}-code.json").write_text(json.dumps({"parse": "ok", "code": code}))
                visible.append({"task": task, "sample": sample, "id": cid,
                                "evidence": {"base": {"pass": True, "v_count": 1, "signature": "sig"}}})
                labels.append({"task": task, "sample": sample, "id": cid,
                               "y": True, "h": True, "qualified_y": True,
                               "outcomes": {"plus": {"pass": True, "execution": [], "details": [],
                                                      "initialization": "complete"}}})
                ordinal += 1
            decisions.append({"task": task, "decisions": {
                str(k): {"pass_count": 0, "consensus": 0} for k in (1, 2, 4, 8)}})
        ledger.extend([
            {"event": "chunk_bank_frozen", "chunk": chunk},
            {"event": "chunk_decisions_frozen", "chunk": chunk},
        ])
        completed += len(tasks)
        ledger.append({"event": "chunk_checkpoint", "chunk": chunk, "completed_tasks": completed,
                       "environment": {"container_ids": [], "active_models": []},
                       "forecast_seconds": 100.0, "reference_audit_seconds": 86.0})
    if mutation == "extra_chunk":
        ledger.extend([
            {"event": "chunk_start", "chunk": 4, "environment": {"container_ids": [], "active_models": []}},
            {"event": "chunk_checkpoint", "chunk": 4, "completed_tasks": 25,
             "environment": {"container_ids": [], "active_models": []}},
        ])
    else:
        # The accepted historical ledger made the boundary check for chunk 4,
        # then stopped before any registered calls were started.
        ledger.append({"event": "chunk_start", "chunk": 4,
                       "environment": {"container_ids": [], "active_models": []}})
    if mutation == "wrong_terminal":
        ledger.append({"event": "global_freeze", "calls": 160, "tokens": 41376,
                       "tasks": 20, "elapsed_seconds": 1112.9658796659987})
    else:
        ledger.append({"event": "stopped", "calls": 160, "tokens": 41376,
                       "tasks": 20, "elapsed_seconds": 1112.9658796659987,
                       "reason": "registered resource gate"})
    write_jsonl(run / "ledger.jsonl", ledger)
    write_jsonl(run / "visible.jsonl", visible)
    write_jsonl(run / "decisions.jsonl", decisions)
    write_jsonl(run / "sealed-labels.jsonl", labels)
    write_manifest(root)
    if mutation == "corrupt_artifact":
        with (run / "visible.jsonl").open("a") as stream:
            stream.write("{}\n")
    if mutation == "extra_reference_build":
        (root / "reference-build").mkdir()
        (root / "reference-build" / "locked-fixture.txt").write_text("separately pinned P0 fixture\n")
    if mutation == "extra_untracked":
        (root / "untracked.txt").write_text("must not be silently accepted\n")
    if mutation == "symlink_untracked":
        outside = root.parent / "outside-reference-build"
        outside.mkdir()
        (outside / "payload.txt").write_text("outside parent root\n")
        (root / "reference-build").mkdir()
        (root / "reference-build" / "external").symlink_to(outside, target_is_directory=True)
    return hashlib.sha256((run / "ledger.jsonl").read_bytes()).hexdigest()


class E1ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "e1"
        self.root.mkdir()
        self.parent_hash = synthetic_parent(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def validate(self, parent_hash=None):
        from ciresearch.e1_continuation import validate_parent
        return validate_parent(self.root, parent_hash or self.parent_hash)

    def test_valid_stopped_parent_binds_four_completed_chunks(self):
        parent = self.validate()
        self.assertEqual(parent.ledger_sha256, self.parent_hash)
        self.assertEqual(parent.completed_chunks, (0, 1, 2, 3))
        self.assertEqual(parent.boundary_only_chunks, (4,))
        self.assertEqual(parent.remaining_chunks, (4, 5, 6, 7))
        self.assertEqual(parent.remaining_calls, 160)
        self.assertEqual(parent.remaining_output_tokens, 204384)
        self.assertAlmostEqual(parent.remaining_seconds, 2487.0341203340013)

    def test_rejects_wrong_parent_hash(self):
        from ciresearch.e1_continuation import ContinuationError
        with self.assertRaisesRegex(ContinuationError, "ledger hash"):
            self.validate("0" * 64)

    def test_rejects_manifest_artifact_changes(self):
        from ciresearch.e1_continuation import ContinuationError
        with self.assertRaisesRegex(ContinuationError, "manifest"):
            synthetic_parent(self.root / "other", "corrupt_artifact")
            # Validate the altered fixture using its own ledger commitment.
            validate_parent = __import__("ciresearch.e1_continuation", fromlist=["validate_parent"]).validate_parent
            validate_parent(self.root / "other", hashlib.sha256(
                ((self.root / "other" / "run" / "ledger.jsonl").read_bytes())).hexdigest())

    def test_allows_separately_managed_p0_reference_build_directory(self):
        from ciresearch.e1_continuation import validate_parent
        root = Path(self.temp.name) / "reference-build"
        root.mkdir()
        ledger_hash = synthetic_parent(root, "extra_reference_build")
        self.assertEqual(validate_parent(root, ledger_hash).remaining_calls, 160)

    def test_rejects_reference_build_tree_hash_mismatch(self):
        from ciresearch.e1_continuation import ContinuationError, validate_parent
        root = Path(self.temp.name) / "changed-reference-build"
        root.mkdir()
        ledger_hash = synthetic_parent(root, "extra_reference_build")
        with self.assertRaisesRegex(ContinuationError, "reference-build hash"):
            validate_parent(root, ledger_hash, expected_reference_build_sha256="0" * 64)

    def test_rejects_unlisted_files_outside_reference_build(self):
        from ciresearch.e1_continuation import ContinuationError, validate_parent
        root = Path(self.temp.name) / "untracked"
        root.mkdir()
        ledger_hash = synthetic_parent(root, "extra_untracked")
        with self.assertRaisesRegex(ContinuationError, "manifest coverage"):
            validate_parent(root, ledger_hash)

    def test_rejects_symlinked_parent_artifact_directories(self):
        from ciresearch.e1_continuation import ContinuationError, validate_parent
        root = Path(self.temp.name) / "symlink"
        root.mkdir()
        ledger_hash = synthetic_parent(root, "symlink_untracked")
        with self.assertRaisesRegex(ContinuationError, "symlink"):
            validate_parent(root, ledger_hash)

    def test_rejects_missing_started_call(self):
        from ciresearch.e1_continuation import ContinuationError, validate_parent
        root = Path(self.temp.name) / "missing-start"
        root.mkdir()
        ledger_hash = synthetic_parent(root, "missing_start")
        with self.assertRaisesRegex(ContinuationError, "call identities"):
            validate_parent(root, ledger_hash)

    def test_rejects_started_call_without_completion(self):
        from ciresearch.e1_continuation import ContinuationError, validate_parent
        root = Path(self.temp.name) / "missing-done"
        root.mkdir()
        ledger_hash = synthetic_parent(root, "missing_complete")
        with self.assertRaisesRegex(ContinuationError, "call identities"):
            validate_parent(root, ledger_hash)

    def test_rejects_duplicate_call_identity(self):
        from ciresearch.e1_continuation import ContinuationError, validate_parent
        root = Path(self.temp.name) / "duplicate"
        root.mkdir()
        ledger_hash = synthetic_parent(root, "duplicate_start")
        with self.assertRaisesRegex(ContinuationError, "duplicate"):
            validate_parent(root, ledger_hash)

    def test_rejects_unexpected_completed_chunk(self):
        from ciresearch.e1_continuation import ContinuationError, validate_parent
        root = Path(self.temp.name) / "extra-chunk"
        root.mkdir()
        ledger_hash = synthetic_parent(root, "extra_chunk")
        with self.assertRaisesRegex(ContinuationError, "chunk"):
            validate_parent(root, ledger_hash)

    def test_rejects_parent_that_did_not_stop_at_resource_gate(self):
        from ciresearch.e1_continuation import ContinuationError, validate_parent
        root = Path(self.temp.name) / "not-stopped"
        root.mkdir()
        ledger_hash = synthetic_parent(root, "wrong_terminal")
        with self.assertRaisesRegex(ContinuationError, "resource stop"):
            validate_parent(root, ledger_hash)

    def test_continuation_registration_records_baseline_and_parent_hash(self):
        from ciresearch.e1_continuation import make_continuation_registration
        parent = self.validate()
        baseline = {"pressure": 2, "swap_mib": 629.69, "free_bytes": 40 * 2**30,
                    "active_models": [], "container_ids": []}
        record = make_continuation_registration(parent, baseline)
        self.assertEqual(record["parent_ledger_sha256"], self.parent_hash)
        self.assertEqual(record["chunks"], [4, 5, 6, 7])
        self.assertEqual(record["caps"], {"calls": 160, "output_tokens": 204384,
                                           "seconds": 2487.0341203340013,
                                           "per_call_output_tokens": 768,
                                           "effective_max_output_tokens": 122880})
        self.assertEqual(record["resource_baseline"], baseline)

    def create_segment(self, **overrides):
        from ciresearch.e1_continuation import create_continuation_segment
        parent = self.validate()
        segment = Path(self.temp.name) / "continuations" / "segment-01"
        baseline = {"pressure": 2, "swap_mib": 629.69, "free_bytes": 40 * 2**30,
                    "active_models": [], "container_ids": []}
        remaining = tuple(task for group in list(chunk_indices())[4:] for task in group)
        options = {"chunk_ids": (4, 5, 6, 7), "task_ids": remaining,
                   "calls": 160, "tokens": 204384, "seconds": 2487.0341203340013}
        baseline = overrides.pop("baseline", baseline)
        options.update(overrides)
        return create_continuation_segment(segment, parent, baseline, [Path(self.temp.name)], **options)

    def test_segment_registration_is_hash_bound_and_separate(self):
        record = self.create_segment()
        segment = Path(self.temp.name) / "continuations" / "segment-01"
        self.assertEqual(record["parent_ledger_sha256"], self.parent_hash)
        self.assertEqual(record["chunks"], [4, 5, 6, 7])
        self.assertEqual(len(record["expected_candidates"]), 160)
        self.assertEqual(record["task_ids"], [task for group in list(chunk_indices())[4:] for task in group])
        first = record["expected_candidates"][0]
        self.assertEqual(first["task"], record["task_ids"][0])
        self.assertEqual(first["sample"], 0)
        self.assertEqual(record["source_bindings"]["model_revision"], self.validate().registration["model_revision"])
        self.assertRegex(record["continuation_source_tree_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(json.loads((segment / "continuation-registration.json").read_text()), record)
        self.assertEqual((segment / "continuation-registration.json").stat().st_mode & 0o777, 0o600)

    def test_segment_refuses_an_existing_directory(self):
        from ciresearch.e1_continuation import ContinuationError
        segment = Path(self.temp.name) / "continuations" / "segment-01"
        segment.mkdir(parents=True)
        with self.assertRaisesRegex(ContinuationError, "already exists"):
            self.create_segment()

    def test_segment_rejects_overlapping_task_identity(self):
        from ciresearch.e1_continuation import ContinuationError
        with self.assertRaisesRegex(ContinuationError, "overlap"):
            self.create_segment(task_ids=tuple(range(19)) + (20,))

    def test_segment_rejects_incorrect_chunk_range(self):
        from ciresearch.e1_continuation import ContinuationError
        with self.assertRaisesRegex(ContinuationError, "chunk range"):
            self.create_segment(chunk_ids=(3, 4, 5, 6))

    def test_segment_rejects_reset_caps(self):
        from ciresearch.e1_continuation import ContinuationError
        for key, value in (("calls", 320), ("tokens", 245760), ("seconds", 3600)):
            with self.subTest(key=key), self.assertRaisesRegex(ContinuationError, "remaining cumulative"):
                self.create_segment(**{key: value})

    def test_segment_rejects_unstable_preflight(self):
        from ciresearch.e1_continuation import ContinuationError
        with self.assertRaisesRegex(ContinuationError, "baseline gate"):
            self.create_segment(baseline={"pressure": 4, "swap_mib": 900.0,
                                          "free_bytes": 40 * 2**30,
                                          "active_models": [], "container_ids": []})

    def test_segment_rejects_incomplete_parent(self):
        from ciresearch.e1_continuation import ContinuationError, create_continuation_segment
        parent = replace(self.validate(), completed_chunks=(0, 1, 2), remaining_chunks=(3, 4, 5, 6, 7))
        with self.assertRaisesRegex(ContinuationError, "incomplete parent"):
            create_continuation_segment(
                Path(self.temp.name) / "continuations" / "segment-01", parent,
                {"pressure": 2, "swap_mib": 629.69, "free_bytes": 40 * 2**30,
                 "active_models": [], "container_ids": []}, [Path(self.temp.name)],
                chunk_ids=(4, 5, 6, 7), task_ids=tuple(range(20)), calls=160,
                tokens=204384, seconds=2487.0341203340013)

    def test_segment_rejects_parent_not_denied_to_worker(self):
        from ciresearch.e1_continuation import ContinuationError, create_continuation_segment
        parent = self.validate()
        baseline = {"pressure": 2, "swap_mib": 629.69, "free_bytes": 40 * 2**30,
                    "active_models": [], "container_ids": []}
        with self.assertRaisesRegex(ContinuationError, "parent evidence"):
            create_continuation_segment(
                Path(self.temp.name) / "continuations" / "segment-01", parent, baseline,
                [Path(self.temp.name) / "continuations"],
                chunk_ids=(4, 5, 6, 7),
                task_ids=tuple(task for group in list(chunk_indices())[4:] for task in group),
                calls=160, tokens=204384, seconds=2487.0341203340013)

    def test_runner_rejects_mismatched_authorized_parent_hash_before_loading_inputs(self):
        from ciresearch.e1 import StopRun, run
        args = SimpleNamespace(continue_from=self.root, run=Path(self.temp.name) / "segment",
                               expected_parent_ledger_sha256="0" * 64)
        pins = {
            "CIRESEARCH_E1_PARENT_LEDGER_SHA256": "1" * 64,
            "CIRESEARCH_E1_PARENT_MANIFEST_SHA256": "2" * 64,
            "CIRESEARCH_E1_PARENT_REGISTRATION_SHA256": "3" * 64,
            "CIRESEARCH_E1_REFERENCE_BUILD_SHA256": "4" * 64,
            "CIRESEARCH_E1_CHECKER_SHA256": "5" * 64,
        }
        with patch.dict("os.environ", pins, clear=True):
            with self.assertRaisesRegex(StopRun, "approved stopped-parent ledger hash"):
                run(args)

    def test_runner_rejects_parent_hash_without_continuation_mode(self):
        from ciresearch.e1 import StopRun, run
        args = SimpleNamespace(run=Path(self.temp.name) / "run",
                               expected_parent_ledger_sha256="1" * 64)
        with self.assertRaisesRegex(StopRun, "requires --continue-from"):
            run(args)

    def test_continuation_forecast_uses_elapsed_work_and_only_future_tasks(self):
        from ciresearch.e1 import forecast_continuation_total
        tasks = [("humaneval" if i < 20 else "mbpp", None) for i in range(40)]
        groups = list(chunk_indices())
        forecast = forecast_continuation_total(
            100.0, {"humaneval": [20.0, 24.0], "mbpp": [10.0]},
            groups[5:], tasks, 5.0)
        self.assertEqual(forecast, 349.0)

    def validate_combined(self, mutation=None):
        from ciresearch.e1_combine import validate_combined_population
        parent = self.validate()
        segment = synthetic_segment(Path(self.temp.name), parent, mutation)
        return validate_combined_population(parent, segment)

    def test_combiner_accepts_exact_40_task_320_candidate_population(self):
        combined = self.validate_combined()
        self.assertEqual(len(combined.task_ids), 40)
        self.assertEqual(len(combined.candidate_ids), 320)
        self.assertEqual(combined.chunks, tuple(range(8)))

    def test_combined_analysis_keeps_first_candidate_distinct_from_unbiased_pass_at_one(self):
        from ciresearch.e1_analysis import analyze, analyze_records
        from ciresearch.e1_combine import run_records
        combined = self.validate_combined()
        parent_result = analyze(combined.parent_root / "run")
        continuation_result = analyze(combined.continuation_root)
        result = analyze_records(*run_records(combined))
        self.assertEqual(parent_result["complete_checkpoint_tasks"], 20)
        self.assertEqual(continuation_result["complete_checkpoint_tasks"], 20)
        self.assertEqual(result["complete_checkpoint_tasks"], 40)
        metrics = result["analyses"]["official_compatible"]["overall"]["metrics"]["1"]
        self.assertEqual(metrics["first"]["denominator_tasks"], 40)
        self.assertEqual(metrics["pass_at_k"]["denominator_tasks"], 40)
        self.assertNotEqual(metrics["first"]["point"], metrics["pass_at_k"]["point"])
        self.assertIn("full-suite endpoint contains", result["estimand_notes"]["false_rejection"])

    def test_combiner_rejects_missing_task(self):
        from ciresearch.e1_combine import CombinedPopulationError
        with self.assertRaisesRegex(CombinedPopulationError, "identity coverage"):
            self.validate_combined("missing_task")

    def test_combiner_rejects_duplicate_candidate(self):
        from ciresearch.e1_combine import CombinedPopulationError
        with self.assertRaisesRegex(CombinedPopulationError, "duplicate"):
            self.validate_combined("duplicate_candidate")

    def test_combiner_rejects_unexpected_sample(self):
        from ciresearch.e1_combine import CombinedPopulationError
        with self.assertRaisesRegex(CombinedPopulationError, "unexpected sample"):
            self.validate_combined("unexpected_sample")

    def test_combiner_rejects_incomplete_label_rows(self):
        from ciresearch.e1_combine import CombinedPopulationError
        with self.assertRaisesRegex(CombinedPopulationError, "label coverage"):
            self.validate_combined("incomplete_label")

    def test_combiner_rejects_labels_joined_before_decisions_freeze(self):
        from ciresearch.e1_combine import CombinedPopulationError
        with self.assertRaisesRegex(CombinedPopulationError, "before visible decisions"):
            self.validate_combined("label_before_decision")

    def test_combiner_rejects_checkpoint_artifact_digest_mismatch(self):
        from ciresearch.e1_combine import CombinedPopulationError
        with self.assertRaisesRegex(CombinedPopulationError, "chunk artifact hash"):
            self.validate_combined("checkpoint_artifact")

    def test_combiner_rejects_changed_file_after_final_manifest(self):
        from ciresearch.e1_combine import CombinedPopulationError
        with self.assertRaisesRegex(CombinedPopulationError, "artifact hash mismatch"):
            self.validate_combined("manifest_artifact")


class ParentValidationPinsTests(unittest.TestCase):
    def setUp(self):
        self.pins = {
            "CIRESEARCH_E1_PARENT_LEDGER_SHA256": "1" * 64,
            "CIRESEARCH_E1_PARENT_MANIFEST_SHA256": "2" * 64,
            "CIRESEARCH_E1_PARENT_REGISTRATION_SHA256": "3" * 64,
            "CIRESEARCH_E1_REFERENCE_BUILD_SHA256": "4" * 64,
            "CIRESEARCH_E1_CHECKER_SHA256": "5" * 64,
        }

    def test_parent_validation_pins_require_all_local_values(self):
        from ciresearch.e1_continuation import ContinuationError, parent_validation_pins
        with patch.dict("os.environ", self.pins, clear=True):
            del os.environ["CIRESEARCH_E1_CHECKER_SHA256"]
            with self.assertRaisesRegex(ContinuationError, "CIRESEARCH_E1_CHECKER_SHA256"):
                parent_validation_pins()

    def test_parent_validation_pins_reject_malformed_values(self):
        from ciresearch.e1_continuation import ContinuationError, parent_validation_pins
        malformed = dict(self.pins, CIRESEARCH_E1_PARENT_LEDGER_SHA256="../private")
        with patch.dict("os.environ", malformed, clear=True):
            with self.assertRaisesRegex(ContinuationError, "CIRESEARCH_E1_PARENT_LEDGER_SHA256"):
                parent_validation_pins()

    def test_parent_validation_pins_return_named_local_hashes(self):
        from ciresearch.e1_continuation import parent_validation_pins
        with patch.dict("os.environ", self.pins, clear=True):
            self.assertEqual(parent_validation_pins(), {
                "ledger_sha256": "1" * 64,
                "manifest_sha256": "2" * 64,
                "registration_sha256": "3" * 64,
                "reference_build_sha256": "4" * 64,
                "checker_sha256": "5" * 64,
            })


if __name__ == "__main__":
    unittest.main()
