import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ciresearch.e2 import build_selector_prompt, make_call_seed
from ciresearch.e2_inference import WorkerRequestError, render_prompt_tokens, validate_request
from ciresearch.e2_model_host import E2ModelError, E2OfflineModel
from ciresearch.e2_prompts import E2_USER_PREFIX
from ciresearch.e2_runner import (
    E2RunError,
    E2ResourceStop,
    ResourceGuard,
    _sha,
    run_e2,
    validate_frozen_plan,
)
from ciresearch.wire import pack


class FakeTokenizer:
    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        self.messages = messages
        self.args = tokenize, add_generation_prompt
        return " ".join(message["content"] for message in messages)

    def encode(self, text, *, add_special_tokens):
        return text.split()


def synthetic_plan():
    namespace = "ciresearch-e2-sample-v1"
    model_revision = "synthetic-model-revision"
    candidates = [
        {"candidate_id": f"cand-{index}", "original_sample": index,
         "parse_status": "ok", "code": f"def solution(x): return x + {index}"}
        for index in range(4)
    ]
    visible = [{"pass_count": index, "case_count": 3, "passed": index == 3, "status": "complete"}
               for index in range(4)]
    diagnostic = {
        "inputs": [{"args": pack((1,))}],
        "candidate_results": [
            {"initialization": "ready", "cases": [
                {"execution_status": "ok", "value": pack(index), "args_after": pack([1])}]}
            for index in range(4)
        ],
    }
    expected = [pack(1)]
    comparisons = [{"cases": [{"execution_status": "ok", "comparison": "pass",
                                "input_mutated": False}]} for _ in range(4)]
    payloads = {
        arm: build_selector_prompt(
            arm, "Return x plus a constant.", candidates,
            visible=visible if arm in "BCD" else None,
            diagnostic=diagnostic if arm in "CD" else None,
            expected=expected if arm == "D" else None,
            comparisons=comparisons if arm == "D" else None)
        for arm in "ABCD"
    }
    token_counts = {arm: len(prompt.split()) for arm, prompt in payloads.items()}
    sample = []
    schedule = []
    seq = 0
    for batch in range(6):
        ids = [f"he-{batch}-a", f"he-{batch}-b", f"mb-{batch}-a", f"mb-{batch}-b"]
        rotation = batch % 4
        for pos, task_id in enumerate(ids):
            benchmark = "humaneval" if task_id.startswith("he-") else "mbpp"
            order = list("ABCD")
            offset = (pos + rotation) % 4
            arm_order = order[offset:] + order[:offset]
            sample.append({"task_id": task_id, "benchmark": benchmark, "batch": batch,
                           "batch_position": pos, "arm_order": arm_order})
            candidate_map = [
                {"display_index": index + 1, "candidate_id": f"{task_id}-cand-{index}",
                 "original_sample": row["original_sample"]}
                for index, row in enumerate(candidates)
            ]
            for arm in arm_order:
                prompt = payloads[arm]
                prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
                seed = make_call_seed(task_id, arm, model_revision, namespace)
                call_id = _sha(f"{namespace}\0call-v1\0{task_id}\0{arm}\0{seed}\0{prompt_hash}".encode())
                schedule.append({"sequence": seq, "call_id": call_id, "task_id": task_id,
                                 "benchmark": benchmark, "batch": batch, "arm": arm,
                                 "seed": seed, "candidate_map": [dict(row) for row in candidate_map],
                                 "prompt_sha256": prompt_hash, "input_tokens": token_counts[arm],
                                 "max_new_tokens": 128, "prompt": prompt})
                seq += 1
    return {
        "schema": "ciresearch-e2-private-registration.v3",
        "status": "technical_preflight_complete", "labels_read": False,
        "confirmation_accessed": False, "namespace": namespace,
        "protocol_sha256": "a" * 64, "config_sha256": "b" * 64,
        "runtime_dependency_lock_sha256": "c" * 64,
        "worker_protected_roots": {
            "e1_parent": "/private/e1-parent",
            "e1_continuation": "/private/e1-continuation",
            "dataset": "/private/benchmark-data",
            "e2_private": "/private/e2-artifacts",
        },
        "model_revision": model_revision, "model_files": {},
        "model_sampling": {"temperature": 0.7, "top_p": 0.95,
                           "max_new_tokens": 128, "context_limit": 8192, "input_limit": 8064},
        "caps": {"tasks": 24, "model_call_starts": 96, "output_tokens": 12288,
                 "empirical_seconds": 1800, "inference_streams": 1,
                 "minimum_free_disk_gib": 15, "batch_tasks": 4},
        "resource_gate": {"fresh_boot_required": True,
                          "requires_fresh_boot_after_utc": "2026-11-26T11:45:06Z",
                          "repeat_rebaseline_to_bypass_stop": False},
        "sample": sample, "call_schedule": schedule,
    }


class FakeModel:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def wait_ready(self, *_args):
        return {"status": "ready", "model_type": "qwen2", "quantization_bits": 4,
                "load_seconds": 0.01}

    def generate(self, _prompt, _seed, input_tokens, *_args):
        return {"status": "ok", "text": '{"choice":1}', "token_ids": [1],
                "input_tokens": input_tokens, "output_tokens": 1,
                "finish_reason": "stop", "wall_seconds": 0.01}


def good_snapshot():
    return {"boot_unix": 1795730000, "memory_pressure_level": 1,
            "free_disk_bytes": 20 * 2**30, "frontmost_apps": ["Finder", "Terminal"],
            "active_research_workers": [], "active_ollama_processes": [],
            "docker_query": "stopped", "research_containers": [], "swap_used_mib": 400.0}


def set_worker_roots(plan, root):
    roots = {}
    for role in ("e1_parent", "e1_continuation", "dataset", "e2_private"):
        path = root / role
        path.mkdir()
        roots[role] = str(path)
    plan["worker_protected_roots"] = roots
    return [Path(path) for path in roots.values()]


class E2WorkerBoundaryTests(unittest.TestCase):
    def test_worker_accepts_only_bounded_frozen_prompt_requests(self):
        prompt = E2_USER_PREFIX + '{"task":"task","candidates":[]}'
        request = (json.dumps({"prompt": prompt, "seed": 7, "input_tokens": 10}) + "\n").encode()
        self.assertEqual(validate_request(request)["seed"], 7)
        for invalid in (
            {"prompt": prompt, "seed": True, "input_tokens": 10},
            {"prompt": prompt, "seed": 7, "input_tokens": 8065},
            {"prompt": prompt, "seed": 7, "input_tokens": 10, "task_id": "hidden"},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(WorkerRequestError):
                validate_request((json.dumps(invalid) + "\n").encode())
        with self.assertRaises(WorkerRequestError):
            validate_request(b'{"prompt":"x","prompt":"y","seed":1,"input_tokens":1}\n')

    def test_worker_uses_shared_system_prompt_and_registered_context(self):
        tokenizer = FakeTokenizer()
        chat, tokens = render_prompt_tokens(tokenizer, "selector payload")
        self.assertEqual(tokenizer.messages[0]["content"],
                         __import__("ciresearch.e2_prompts", fromlist=["E2_SYSTEM_PROMPT"]).E2_SYSTEM_PROMPT)
        self.assertTrue(chat.endswith("selector payload"))
        self.assertGreater(len(tokens), 0)

    def test_model_host_denies_network_and_protected_reads_without_model_overlap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model, evidence, protected = root / "model", root / "evidence", root / "protected"
            model.mkdir(); evidence.mkdir(); protected.mkdir()
            host = E2OfflineModel(Path(sys.executable), model, evidence, [protected])
            self.assertIn("deny network*", host.profile)
            self.assertIn(str(protected), host.profile)
            with self.assertRaises(E2ModelError):
                E2OfflineModel(Path(sys.executable), model, evidence, [root])


class E2RunnerTests(unittest.TestCase):
    def test_frozen_plan_has_balanced_unique_calls_and_same_candidate_map(self):
        plan = synthetic_plan()
        validate_frozen_plan(plan)
        plan["call_schedule"][1]["candidate_map"][0]["candidate_id"] = "different"
        with self.assertRaises(Exception):
            validate_frozen_plan(plan)

    def test_frozen_plan_requires_versioned_protocol_and_config_hashes(self):
        plan = synthetic_plan()
        plan["protocol_sha256"] = "not-a-sha256"
        with self.assertRaises(E2RunError):
            validate_frozen_plan(plan)

    def test_runner_rejects_incomplete_registered_protected_read_denials(self):
        plan = synthetic_plan()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            set_worker_roots(plan, root)
            incomplete = root / "incomplete"
            incomplete.mkdir()
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan))
            resource_called = []

            def should_not_sample(_path):
                resource_called.append(True)
                raise AssertionError("resource gate must follow protected-path validation")

            with self.assertRaises(E2RunError):
                run_e2(plan_path, model_path=root / "no-model", python_path=Path(sys.executable),
                       output_dir=root / "run", denied_paths=[incomplete],
                       resource_provider=should_not_sample)
            self.assertEqual(resource_called, [])

    def test_repeated_swap_growth_stops_at_the_registered_guard(self):
        baseline = good_snapshot()
        guard = ResourceGuard(baseline)
        high = {**baseline, "swap_used_mib": baseline["swap_used_mib"] + 300}
        guard.check(high)
        with self.assertRaises(E2ResourceStop):
            guard.check(high)

    def test_stale_boot_stops_before_model_verification_or_loading(self):
        plan = synthetic_plan()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protected = set_worker_roots(plan, root)
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan))
            output = root / "run"
            stale = {**good_snapshot(), "boot_unix": 1795600000}
            with patch("ciresearch.e2_runner.E2OfflineModel", side_effect=AssertionError("must not load")), \
                 patch("ciresearch.p1.verify_model", side_effect=AssertionError("must not verify/load weights")):
                with self.assertRaises(E2ResourceStop):
                    run_e2(plan_path, model_path=root / "no-model", python_path=Path(sys.executable),
                           output_dir=output, denied_paths=protected,
                           resource_provider=lambda _path: stale)
            self.assertFalse(output.exists())

    def test_synthetic_call_ledger_covers_all_frozen_calls_without_retry(self):
        plan = synthetic_plan()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protected = set_worker_roots(plan, root)
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(plan))
            output = root / "runs" / "synthetic"
            with patch("ciresearch.e2_runner.E2OfflineModel", FakeModel), \
                 patch("ciresearch.p1.verify_model", return_value=None):
                run_e2(plan_path, model_path=root / "synthetic-model",
                       python_path=Path(sys.executable), output_dir=output,
                       denied_paths=protected,
                       resource_provider=lambda _path: good_snapshot())
            ledger = [json.loads(line) for line in (output / "ledger.jsonl").read_text().splitlines()]
            decisions = [json.loads(line) for line in (output / "decisions.jsonl").read_text().splitlines()]
            self.assertEqual(sum(row["event"] == "call_started" for row in ledger), 96)
            self.assertEqual(sum(row["event"] == "call_complete" for row in ledger), 96)
            self.assertEqual(sum(row["event"] == "run_complete" for row in ledger), 1)
            self.assertEqual(len(decisions), 96)
            self.assertEqual(len(list((output / "responses").glob("*.json"))), 96)
            self.assertTrue((output / "SHA256SUMS").is_file())
            self.assertEqual(json.loads((output / "responses" / (plan["call_schedule"][0]["call_id"] + ".json")).read_text())["text"],
                             '{"choice":1}')


if __name__ == "__main__":
    unittest.main()
