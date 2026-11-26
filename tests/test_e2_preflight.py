import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ciresearch.e2_preflight import (
    E2PreflightError,
    _completed_prompts,
    _candidate_source,
    _prompt_token_reasons,
    _response_observations,
    load_evidence_view,
    write_private_registration,
)
from ciresearch.wire import pack


class TinyTokenizer:
    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        self.messages = messages
        self.options = (tokenize, add_generation_prompt)
        return "|".join(message["content"] for message in messages)

    def encode(self, text, *, add_special_tokens):
        return text.split()


class E2PreflightTests(unittest.TestCase):
    def test_missing_prompt_tokens_are_not_misclassified_as_context_overflow(self):
        self.assertEqual(
            _prompt_token_reasons({"A": 500, "B": -1}),
            ("final_prompt_set_incomplete",),
        )
        self.assertEqual(
            _prompt_token_reasons({"A": 8065, "B": 500, "C": 500, "D": 500}),
            ("final_prompt_exceeds_context_allowance",),
        )

    def test_cached_source_is_kept_for_parse_failed_registered_candidates(self):
        invalid_source = "def solve(x):\n    return x +\n"
        self.assertEqual(
            _candidate_source("invalid_syntax", {"parse": "invalid_syntax", "code": invalid_source}),
            invalid_source,
        )
        self.assertEqual(
            _candidate_source("truncated", {"parse": "truncated", "code": "def solve(x):"}),
            "def solve(x):",
        )

    def test_development_prompt_loader_only_returns_requested_completed_indices(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = {
                "humaneval": [(f"he-{i}", f"prompt-he-{i}") for i in range(20)],
                "mbpp": [(f"mb-{i}", f"prompt-mb-{i}") for i in range(20)],
            }
            split = {
                "humaneval": {"development": [item[0] for item in rows["humaneval"]],
                              "confirmation": ["protected-he"]},
                "mbpp": {"development": [item[0] for item in rows["mbpp"]],
                         "confirmation": ["protected-mb"]},
            }
            split_bytes = json.dumps(split).encode()
            (root / "private-split.json").write_bytes(split_bytes)
            archives = {}
            prompt_hashes = ["0" * 64 for _ in range(40)]
            prompt_hashes[0] = hashlib.sha256(b"prompt-he-0").hexdigest()
            prompt_hashes[20] = hashlib.sha256(b"prompt-mb-0").hexdigest()
            for benchmark, filename, task_rows in (
                ("humaneval", "he.gz", rows["humaneval"]),
                ("mbpp", "mb.gz", rows["mbpp"]),
            ):
                archive = root / filename
                with gzip.open(archive, "wb") as stream:
                    for task_id, prompt in task_rows:
                        stream.write((json.dumps({"task_id": task_id, "prompt": prompt}) + "\n").encode())
                    stream.write((json.dumps({"task_id": "protected-" + benchmark, "prompt": "private"}) + "\n").encode())
                archives[benchmark] = (filename, hashlib.sha256(archive.read_bytes()).hexdigest())
            with patch("ciresearch.e2_preflight.ARCHIVES", archives):
                selected = _completed_prompts(
                    root, hashlib.sha256(split_bytes).hexdigest(), (0, 20), prompt_hashes)
            self.assertEqual(set(selected), {0, 20})
            self.assertEqual(selected[0][1]["task_id"], "he-0")
            self.assertEqual(selected[20][1]["task_id"], "mb-0")

    def test_response_observations_keep_typed_values_and_explicit_statuses(self):
        ok = {"status": "ok", "value": pack((1, 2)), "args_after": pack(([1],))}
        result = _response_observations([{"status": "ready"}, ok, {"status": "timeout"}], 2)
        self.assertEqual(result["initialization"], "ready")
        self.assertEqual(result["cases"][0]["execution_status"], "ok")
        self.assertEqual(result["cases"][1], {"execution_status": "timeout"})
        with self.assertRaises(E2PreflightError):
            _response_observations([{"status": "ready"}, {"status": "bad"}], 1)

    def test_serialized_technical_view_rejects_label_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "view.json"
            value = {"schema": "ciresearch-e2-technical-view.v1",
                     "parent_root": "/private/e1", "continuation_root": "/private/segment",
                     "original_tasks": [], "continuation_tasks": [], "completed_tasks": [],
                     "checkpoint_chunks": [], "call_records": [], "visible_records": [],
                     "label_records": []}
            path.write_text(json.dumps(value))
            with self.assertRaises(E2PreflightError):
                load_evidence_view(path)

    def test_private_registration_is_create_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registration.json"
            digest = write_private_registration(path, {"labels_read": False})
            self.assertEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest())
            with self.assertRaises(E2PreflightError):
                write_private_registration(path, {"labels_read": True})
            self.assertIn(b'"labels_read":false', path.read_bytes())


if __name__ == "__main__":
    unittest.main()
