"""Synthetic-only tests for the read-only, incomplete-population E1 path."""
import unittest
from pathlib import Path
from types import MappingProxyType
import hashlib
import json
import tempfile

from ciresearch.e1_interim import (
    validate_interim_population,
    InterimView,
    InterimPopulationError,
    freeze_records,
    records_for_tasks,
    validate_chunk_events,
    validate_identity_rows,
    verify_checkpoint_artifact,
)
from ciresearch.e1_interim_analysis import analyze_interim
from ciresearch.e1_interim_analysis import _bootstrap
from ciresearch.e1_e2_feasibility import _condition_payloads, e2_evidence_view
from tests.test_e1_continuation import (
    synthetic_parent,
    synthetic_tree_hash,
    write_jsonl,
    write_segment_manifest,
)


def synthetic_stopped_segment(root):
    from ciresearch.e1_continuation import create_continuation_segment, validate_parent
    from ciresearch.e1_data import chunk_indices

    parent_root = root / "parent"
    parent_ledger_hash = synthetic_parent(parent_root)
    parent = validate_parent(parent_root, parent_ledger_hash)
    segment = root / "segment"
    groups = list(chunk_indices())
    remaining_tasks = tuple(task for group in groups[4:] for task in group)
    baseline = {"pressure": 2, "swap_mib": 700.0, "free_bytes": 40 * 2**30,
                "active_models": [], "container_ids": []}
    registration = create_continuation_segment(
        segment, parent, baseline, [root, parent_root], chunk_ids=(4, 5, 6, 7),
        task_ids=remaining_tasks, calls=160, tokens=204384, seconds=2487.0341203340013)
    reg_sha = hashlib.sha256((segment / "continuation-registration.json").read_bytes()).hexdigest()
    ledger = [{"event": "continuation_start", "parent_ledger_sha256": parent.ledger_sha256,
               "registration_sha256": reg_sha, "starting_calls": parent.completed_calls,
               "starting_tokens": parent.output_tokens, "starting_input_tokens": parent.input_tokens,
               "starting_tasks": len(parent.completed_tasks), "starting_elapsed_seconds": parent.elapsed_seconds,
               "environment": baseline}]
    visible, decisions, labels = [], [], []
    entries = registration["expected_candidates"]

    def add_generation(chunk, task, sample, *, complete=True):
        entry = next(row for row in entries if row["task"] == task and row["sample"] == sample)
        candidate = entry["id"]
        code = f"def solution(value): return {task + sample}"
        ledger.append({"event": "call_started", "task": task, "sample": sample, "id": candidate})
        if not complete:
            return
        ledger.append({"event": "call_complete", "task": task, "sample": sample, "id": candidate,
                       "parse": "ok", "code_hash": hashlib.sha256(code.encode()).hexdigest(),
                       "tokens": 10, "input_tokens": 20})
        directory = segment / f"chunk-{chunk:02d}"
        directory.mkdir(mode=0o700, exist_ok=True)
        (directory / f"{candidate}.json").write_text(json.dumps({
            "status": "ok", "output_tokens": 10, "input_tokens": 20,
            "prefill_tokens_per_second": 100.0, "decode_tokens_per_second": 50.0,
            "peak_mlx_bytes": 1000, "host_peak_rss_bytes": 2000, "wall_seconds": 0.2}))
        (directory / f"{candidate}-code.json").write_text(json.dumps({"parse": "ok", "code": code}))

    for offset, chunk in enumerate((4, 5), start=1):
        group = groups[chunk]
        ledger.append({"event": "chunk_start", "chunk": chunk,
                       "environment": {"container_ids": [], "active_models": []}})
        for task in group:
            for sample in range(8):
                add_generation(chunk, task, sample)
                entry = next(row for row in entries if row["task"] == task and row["sample"] == sample)
                truth = (task + sample) % 3 == 0
                visible.append({"task": task, "sample": sample, "id": entry["id"], "evidence": {
                    "base": {"pass": sample % 2 == 0, "v_count": int(sample % 2 == 0),
                             "signature": f"sig-{sample % 2}"}}})
                labels.append({"task": task, "sample": sample, "id": entry["id"], "y": truth,
                               "h": truth, "qualified_y": truth,
                               "outcomes": {"plus": {"pass": truth, "execution": [],
                                                      "details": [], "initialization": "complete"}}})
            decisions.append({"task": task, "decisions": {
                str(k): {"pass_count": 0, "consensus": 0} for k in (1, 2, 4, 8)}})
        ledger.extend([{"event": "chunk_bank_frozen", "chunk": chunk},
                       {"event": "chunk_decisions_frozen", "chunk": chunk},
                       {"event": "chunk_labels_joined", "chunk": chunk}])
        ledger.append({"event": "chunk_checkpoint", "chunk": chunk,
                       "completed_tasks": 20 + 5 * offset,
                       "chunk_artifact_sha256": synthetic_tree_hash(segment / f"chunk-{chunk:02d}"),
                       "environment": {"container_ids": [], "active_models": []}})

    ledger.append({"event": "chunk_start", "chunk": 6,
                   "environment": {"container_ids": [], "active_models": []}})
    for ordinal, entry in enumerate(row for row in entries if row["task"] in groups[6]):
        if ordinal == 14:
            break
        add_generation(6, entry["task"], entry["sample"], complete=ordinal < 13)
    terminal_calls = 254
    segment_completions = 93
    segment_tokens = segment_completions * 10
    segment_inputs = segment_completions * 20
    segment_elapsed = 100.0
    ledger.append({"event": "stopped", "calls": terminal_calls,
                   "segment_calls": 94, "tokens": parent.output_tokens + segment_tokens,
                   "input_tokens": parent.input_tokens + segment_inputs,
                   "segment_tokens": segment_tokens, "segment_input_tokens": segment_inputs,
                   "tasks": 30, "segment_tasks": 10,
                   "elapsed_seconds": parent.elapsed_seconds + segment_elapsed,
                   "segment_elapsed_seconds": segment_elapsed, "reason": "resource pressure"})
    write_jsonl(segment / "ledger.jsonl", ledger)
    write_jsonl(segment / "visible.jsonl", visible)
    write_jsonl(segment / "decisions.jsonl", decisions)
    write_jsonl(segment / "sealed-labels.jsonl", labels)
    write_segment_manifest(segment)
    pins = {"ledger_sha256": parent.ledger_sha256,
            "manifest_sha256": parent.manifest_sha256,
            "registration_sha256": hashlib.sha256((parent_root / "registration.json").read_bytes()).hexdigest(),
            "reference_build_sha256": None,
            "checker_sha256": None}
    return parent_root, segment, pins


class E1InterimPrimitiveTests(unittest.TestCase):
    def _synthetic_population(self):
        temporary = tempfile.TemporaryDirectory()
        parent, segment, pins = synthetic_stopped_segment(Path(temporary.name))
        return temporary, parent, segment, pins

    def _refresh_segment_manifest(self, segment):
        manifest = segment / "SEGMENT_SHA256SUMS"
        manifest.unlink()
        write_segment_manifest(segment)

    def test_validates_synthetic_six_checkpoint_interim_population(self):
        temporary, parent, segment, pins = self._synthetic_population()
        self.addCleanup(temporary.cleanup)
        view = validate_interim_population(parent, segment, pins)
        self.assertEqual(view.checkpoint_chunks, (0, 1, 2, 3, 4, 5))
        self.assertEqual(len(view.completed_tasks), 30)
        self.assertEqual(len(view.call_records), 240)
        self.assertEqual(view.generation_only_outputs, 13)
        self.assertEqual(view.interrupted_started_calls, 1)
        self.assertEqual(view.unstarted_registered_calls, 66)

    def test_high_level_validator_rejects_artifact_tampering(self):
        temporary, parent, segment, pins = self._synthetic_population()
        self.addCleanup(temporary.cleanup)
        path = segment / "visible.jsonl"
        path.write_text(path.read_text() + "{}\n")
        with self.assertRaisesRegex(ValueError, "artifact hash"):
            validate_interim_population(parent, segment, pins)

    def test_high_level_validator_rejects_duplicate_candidate_identity(self):
        temporary, parent, segment, pins = self._synthetic_population()
        self.addCleanup(temporary.cleanup)
        path = segment / "visible.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[0] = dict(rows[1])
        write_jsonl(path, rows)
        self._refresh_segment_manifest(segment)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_interim_population(parent, segment, pins)

    def test_high_level_validator_rejects_incomplete_checkpoint(self):
        temporary, parent, segment, pins = self._synthetic_population()
        self.addCleanup(temporary.cleanup)
        path = segment / "ledger.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows = [row for row in rows if not (row.get("event") == "chunk_checkpoint" and row.get("chunk") == 5)]
        write_jsonl(path, rows)
        self._refresh_segment_manifest(segment)
        with self.assertRaisesRegex(ValueError, "sequence|checkpoint"):
            validate_interim_population(parent, segment, pins)

    def test_high_level_validator_rejects_labels_joined_before_decisions(self):
        temporary, parent, segment, pins = self._synthetic_population()
        self.addCleanup(temporary.cleanup)
        path = segment / "ledger.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        decision = next(i for i, row in enumerate(rows)
                        if row.get("event") == "chunk_decisions_frozen" and row.get("chunk") == 4)
        label = next(i for i, row in enumerate(rows)
                     if row.get("event") == "chunk_labels_joined" and row.get("chunk") == 4)
        rows[decision], rows[label] = rows[label], rows[decision]
        write_jsonl(path, rows)
        self._refresh_segment_manifest(segment)
        with self.assertRaisesRegex(ValueError, "order"):
            validate_interim_population(parent, segment, pins)

    def test_bootstrap_matches_registered_full_population_draws(self):
        from ciresearch.e1_analysis import bootstrap_groups
        registered = bootstrap_groups()
        interim = _bootstrap(tuple(range(40)))
        self.assertTrue(all(draw == tuple(left + right)
                            for draw, (left, right) in zip(interim["overall"], registered)))
        self.assertTrue(all(draw == tuple(left)
                            for draw, (left, _right) in zip(interim["humaneval"], registered)))
        self.assertTrue(all(draw == tuple(right)
                            for draw, (_left, right) in zip(interim["mbpp"], registered)))

    def test_e2_conditions_add_only_registered_evidence_layers(self):
        payloads = _condition_payloads(
            "task", [{"index": 1, "code": "def f(): return 1"}],
            [{"index": 1, "pass": True}], [{"args": [["i", "1"]]}],
            [{"index": 1, "outputs": [{"status": "ok"}]}], [["i", "1"]])
        self.assertNotIn("visible_summary", payloads["A"])
        self.assertIn("visible_summary", payloads["B"])
        self.assertNotIn("reference", payloads["C"])
        self.assertIn("diagnostic", payloads["C"])
        self.assertIn("reference", payloads["D"])
        self.assertNotIn("correctness_labels", payloads["D"])
        self.assertEqual(payloads["D"]["reference"]["comparison"], [[True]])

    def test_accepts_exact_complete_continuation_event_order(self):
        ledger = [
            {"event": event, "chunk": 4}
            for event in ("chunk_start", "chunk_bank_frozen", "chunk_decisions_frozen",
                          "chunk_labels_joined", "chunk_checkpoint")
        ]
        validate_chunk_events(ledger, 4, complete=True, continuation=True)

    def test_rejects_label_join_before_visible_decisions(self):
        ledger = [
            {"event": event, "chunk": 4}
            for event in ("chunk_start", "chunk_bank_frozen", "chunk_labels_joined",
                          "chunk_decisions_frozen", "chunk_checkpoint")
        ]
        with self.assertRaisesRegex(InterimPopulationError, "order"):
            validate_chunk_events(ledger, 4, complete=True, continuation=True)

    def test_rejects_incomplete_chunk_as_checkpoint(self):
        ledger = [{"event": "chunk_start", "chunk": 5},
                  {"event": "chunk_bank_frozen", "chunk": 5}]
        with self.assertRaisesRegex(InterimPopulationError, "checkpoint"):
            validate_chunk_events(ledger, 5, complete=True, continuation=True)

    def test_accepts_only_start_event_for_partial_chunk(self):
        ledger = [{"event": "chunk_start", "chunk": 6}]
        validate_chunk_events(ledger, 6, complete=False, continuation=True)

    def test_rejects_frozen_or_scored_partial_chunk(self):
        ledger = [{"event": "chunk_start", "chunk": 6},
                  {"event": "chunk_bank_frozen", "chunk": 6}]
        with self.assertRaisesRegex(InterimPopulationError, "partial"):
            validate_chunk_events(ledger, 6, complete=False, continuation=True)

    def test_rejects_duplicate_candidate_identity(self):
        candidate = "a" * 64
        rows = [{"task": 8, "sample": 0, "id": candidate},
                {"task": 8, "sample": 0, "id": candidate}]
        with self.assertRaisesRegex(InterimPopulationError, "duplicate"):
            validate_identity_rows(rows, {(8, 0): candidate}, "candidate")

    def test_rejects_missing_or_altered_identity(self):
        rows = [{"task": 8, "sample": 0, "id": "b" * 64}]
        with self.assertRaisesRegex(InterimPopulationError, "coverage"):
            validate_identity_rows(rows, {(8, 0): "a" * 64}, "candidate")

    def test_rejects_altered_checkpoint_artifact_hash(self):
        with self.assertRaisesRegex(InterimPopulationError, "artifact hash"):
            verify_checkpoint_artifact("a" * 64, "b" * 64)

    def test_excludes_uncheckpointed_generation_records_from_analytic_view(self):
        rows = ({"task": task, "sample": sample} for task in (0, 1, 2) for sample in range(8))
        selected = records_for_tasks(rows, {0, 1})
        self.assertEqual(len(selected), 16)
        self.assertEqual({row["task"] for row in selected}, {0, 1})

    def test_analytical_records_are_deeply_immutable(self):
        frozen = freeze_records([{"task": 0, "values": [1, {"ok": True}]}])
        self.assertIsInstance(frozen, tuple)
        self.assertIsInstance(frozen[0], MappingProxyType)
        with self.assertRaises(TypeError):
            frozen[0]["task"] = 2
        with self.assertRaises(AttributeError):
            frozen[0]["values"].append(3)
        with self.assertRaises(TypeError):
            frozen[0]["values"][1]["ok"] = False

    def test_interim_analysis_uses_task_populations_and_registered_bounds(self):
        visible, decisions, labels, calls, generations = [], [], [], [], []
        for task in (0, 20):
            for sample in range(8):
                truth = task == 0 or sample % 2 == 0
                cid = f"{task:02x}{sample:02x}".ljust(64, "a")
                visible.append({"task": task, "sample": sample, "evidence": {"base": {
                    "pass": truth, "v_count": int(truth), "signature": "same" if sample % 2 else "other",
                    "execution": ["ok"], "details": [truth], "initialization": "complete"}}})
                labels.append({"task": task, "sample": sample, "y": truth, "h": truth,
                               "qualified_y": truth, "outcomes": {"plus": {
                                   "pass": truth, "execution": ["ok"], "details": [truth],
                                   "initialization": "complete"}}})
                calls.append({"task": task, "sample": sample, "code_hash": cid})
                generations.append({"prefill_tokens_per_second": 100.0,
                                    "decode_tokens_per_second": 50.0,
                                    "peak_mlx_bytes": 1000,
                                    "host_peak_rss_bytes": 2000,
                                    "wall_seconds": 0.2})
            decisions.append({"task": task, "decisions": {
                str(k): {"pass_count": 0, "consensus": 0} for k in (1, 2, 4, 8)}})
        view = InterimView(
            parent_root=Path("/synthetic-parent"),
            continuation_root=Path("/synthetic-continuation"),
            checkpoint_chunks=(0, 1, 2, 3, 4, 5), original_tasks=(0,),
            continuation_tasks=(20,), completed_tasks=(0, 20),
            parent_ledger=(), continuation_ledger=(),
            visible_records=freeze_records(visible), decision_records=freeze_records(decisions),
            label_records=freeze_records(labels), call_records=freeze_records(calls),
            started_records=(), generation_records=freeze_records(generations),
            segment_manifest_sha256="f" * 64, generation_only_outputs=13,
            interrupted_started_calls=1, unstarted_registered_calls=66,
            parent_output_tokens=1, continuation_output_tokens=2, cumulative_output_tokens=3,
            parent_elapsed_seconds=1.0, continuation_elapsed_seconds=2.0,
            cumulative_elapsed_seconds=3.0)
        result = analyze_interim(view, replicates=20)
        population = result["endpoints"]["official_compatible"]
        self.assertEqual(population["original_20"]["tasks"], 1)
        self.assertEqual(population["continuation_10"]["tasks"], 1)
        self.assertEqual(population["combined_30"]["tasks"], 2)
        metric = population["combined_30"]["strata"]["overall"]["metrics"]["8"]["first"]
        self.assertEqual(metric["denominator_tasks"], 2)
        self.assertEqual(metric["registered_population_bounds"], [0.05, 1.0])
        self.assertEqual(result["unavailable_or_uncheckpointed"]["generation_only_outputs_excluded_from_correctness"], 13)
        technical_view = e2_evidence_view(view)
        self.assertFalse(hasattr(technical_view, "label_records"))


if __name__ == "__main__":
    unittest.main()
