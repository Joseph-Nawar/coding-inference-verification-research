import unittest

from ciresearch.e2 import (
    E2Error,
    EligibleTask,
    build_selector_prompt,
    candidate_permutation,
    deterministic_baselines,
    freeze_balanced_sample,
    make_call_seed,
    parse_selector_response,
    score_cached_d_panel,
    score_unexecuted_d_panel,
)
from ciresearch.wire import pack


class E2RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.tasks = [
            EligibleTask(f"he-{index:02d}", "humaneval", {"A": 100, "B": 110, "C": 120, "D": 130})
            for index in range(13)
        ] + [
            EligibleTask(f"mbpp-{index:02d}", "mbpp", {"A": 100, "B": 110, "C": 120, "D": 130})
            for index in range(14)
        ]

    def test_freezes_deterministic_balanced_sample_and_arm_schedule(self):
        frozen = freeze_balanced_sample(self.tasks, namespace="synthetic-e2-v1")
        repeated = freeze_balanced_sample(list(reversed(self.tasks)), namespace="synthetic-e2-v1")
        self.assertEqual(frozen, repeated)
        self.assertEqual(len(frozen), 24)
        self.assertEqual(sum(task.benchmark == "humaneval" for task in frozen), 12)
        self.assertEqual(sum(task.benchmark == "mbpp" for task in frozen), 12)
        for offset in range(0, 24, 4):
            batch = frozen[offset:offset + 4]
            self.assertEqual(sum(task.benchmark == "humaneval" for task in batch), 2)
            for call_position in range(4):
                self.assertEqual({task.arm_order[call_position] for task in batch}, set("ABCD"))

    def test_insufficient_balanced_technical_population_fails_closed(self):
        with self.assertRaises(E2Error):
            freeze_balanced_sample(self.tasks[:11] + self.tasks[13:], namespace="synthetic-e2-v1")

    def test_candidate_permutation_and_call_seed_are_stable_and_distinct(self):
        ids = ["candidate-a", "candidate-b", "candidate-c", "candidate-d"]
        first = candidate_permutation(ids, "he-01", "synthetic-e2-v1")
        self.assertEqual(first, candidate_permutation(ids, "he-01", "synthetic-e2-v1"))
        self.assertEqual(set(first), set(ids))
        self.assertNotEqual(first, candidate_permutation(ids, "he-02", "synthetic-e2-v1"))
        seed = make_call_seed("he-01", "A", "model-rev", "synthetic-e2-v1")
        self.assertEqual(seed, make_call_seed("he-01", "A", "model-rev", "synthetic-e2-v1"))
        self.assertNotEqual(seed, make_call_seed("he-01", "B", "model-rev", "synthetic-e2-v1"))


class E2PromptTests(unittest.TestCase):
    def setUp(self):
        self.candidates = [
            {"candidate_id": "id-a", "original_sample": 0, "parse_status": "ok", "code": "def f(x): return x"},
            {"candidate_id": "id-b", "original_sample": 1, "parse_status": "invalid_syntax", "code": None},
            {"candidate_id": "id-c", "original_sample": 2, "parse_status": "ok", "code": "def f(x): return x + 1"},
            {"candidate_id": "id-d", "original_sample": 3, "parse_status": "ok", "code": "def f(x): return x"},
        ]
        self.visible = [{"pass_count": 2, "case_count": 3, "passed": False,
                         "status": "complete"} for _ in range(4)]
        self.diagnostic = {
            "inputs": [{"args": pack((1,))}],
            "candidate_results": [{"initialization": "ready", "cases": [
                {"execution_status": "ok", "value": pack(1), "args_after": pack([1])}]}
                for _ in range(4)],
        }
        self.expected = [pack(1)]
        self.comparisons = [{"cases": [{"execution_status": "ok", "comparison": "pass",
                                         "input_mutated": False}]}
                            for _ in range(4)]

    def test_conditions_add_only_the_registered_evidence(self):
        candidates = [dict(row) for row in self.candidates]
        candidates[1]["code"] = "def f(: pass"
        prompts = {
            "A": build_selector_prompt("A", "Return x unchanged.", candidates),
            "B": build_selector_prompt("B", "Return x unchanged.", candidates,
                                       visible=self.visible),
            "C": build_selector_prompt("C", "Return x unchanged.", candidates,
                                       visible=self.visible, diagnostic=self.diagnostic),
            "D": build_selector_prompt("D", "Return x unchanged.", candidates,
                                       visible=self.visible, diagnostic=self.diagnostic,
                                       expected=self.expected, comparisons=self.comparisons),
        }
        self.assertIn('"candidates"', prompts["A"])
        self.assertNotIn('"visible_results"', prompts["A"])
        self.assertNotIn('"diagnostic"', prompts["A"])
        self.assertIn('"visible_results"', prompts["B"])
        self.assertNotIn('"diagnostic"', prompts["B"])
        self.assertIn('"visible_results"', prompts["C"])
        self.assertIn('"diagnostic"', prompts["C"])
        self.assertNotIn('"expected_outputs"', prompts["C"])
        self.assertNotIn('"comparison_results"', prompts["C"])
        self.assertIn('"expected_outputs"', prompts["D"])
        self.assertIn('"comparison_results"', prompts["D"])
        self.assertNotIn('"input_mutated"', prompts["D"])
        self.assertNotIn('"args_after"', prompts["C"])
        for prompt in prompts.values():
            self.assertIn("Do not execute candidate code", prompt)
            self.assertIn("invalid_syntax", prompt)

    def test_prompt_builder_rejects_unregistered_or_hidden_fields(self):
        extra = {**self.diagnostic, "heldout_labels": [True]}
        with self.assertRaises(E2Error):
            build_selector_prompt("C", "task", self.candidates, visible=self.visible,
                                  diagnostic=extra)

    def test_parser_accepts_only_a_single_valid_choice_and_maps_identity(self):
        ordered_ids = ["id-c", "id-a", "id-d", "id-b"]
        self.assertEqual(parse_selector_response('{"choice":2}', ordered_ids), "id-a")
        for raw in ("1", '{"choice":true}', '{"choice":5}', '{"choice":1,"why":"x"}',
                    '```json\n{"choice":1}\n```', '{"choice":1,"choice":2}'):
            with self.subTest(raw=raw), self.assertRaises(E2Error):
                parse_selector_response(raw, ordered_ids)


class E2DiagnosticScoringTests(unittest.TestCase):
    @staticmethod
    def response(value, args):
        return {"status": "ok", "value": pack(value), "args_after": pack(args)}

    def test_float_tolerance_is_applied_in_ordered_panel_semantics(self):
        rows = [{"status": "ready"}, self.response(1.0000005, [1]), self.response(2.0000005, [2])]
        result = score_cached_d_panel("humaneval", "f", 0, [pack(1.0), pack(2.0)], rows,
                                      [pack([1]), pack([2])])
        self.assertEqual(result["cases"], [
            {"execution_status": "ok", "comparison": "pass", "input_mutated": False},
            {"execution_status": "ok", "comparison": "pass", "input_mutated": False},
        ])
        self.assertEqual(result["pass_count"], 2)

    def test_alternative_valid_output_uses_the_registered_special_oracle(self):
        result = score_cached_d_panel("mbpp", "are_equivalent", 0, [pack("expected")],
                                      [{"status": "ready"}, self.response("valid alternative", [1])],
                                      [pack([1])])
        self.assertEqual(result["cases"], [{"execution_status": "ok", "comparison": "pass",
                                            "input_mutated": False}])

    def test_mutation_sensitive_find_zero_uses_reported_post_call_arguments(self):
        result = score_cached_d_panel("humaneval", "find_zero", 1e-6, [pack(None)],
                                      [{"status": "ready"}, self.response(0.0, [[0.0, 1.0]])],
                                      [pack([[1.0, 1.0]])])
        self.assertEqual(result["cases"], [{"execution_status": "ok", "comparison": "pass",
                                            "input_mutated": True}])
        self.assertTrue(result["mutation_sensitive"])

    def test_execution_failures_are_explicit_nonpassing_cases(self):
        rows = [{"status": "ready"}, self.response(1, [1]), {"status": "timeout"}]
        result = score_cached_d_panel("humaneval", "f", 0, [pack(1), pack(2)], rows,
                                      [pack([1]), pack([2])])
        self.assertEqual(result["cases"], [
            {"execution_status": "ok", "comparison": "pass", "input_mutated": False},
            {"execution_status": "timeout", "comparison": "not_comparable", "input_mutated": None},
        ])
        self.assertEqual(result["pass_count"], 1)
        init = score_cached_d_panel("humaneval", "f", 0, [pack(1)], [{"status": "exception"}],
                                    [pack([1])])
        self.assertEqual(init["initialization"], "exception")
        self.assertEqual(init["cases"], [
            {"execution_status": "initialization_exception", "comparison": "not_comparable",
             "input_mutated": None},
        ])

    def test_unexecuted_candidates_keep_explicit_noncomparable_d_statuses(self):
        result = score_unexecuted_d_panel("invalid_syntax", 3)
        self.assertEqual(result["initialization"], "candidate_parse_failure")
        self.assertEqual(result["pass_count"], 0)
        self.assertEqual(result["cases"], [
            {"execution_status": "initialization_candidate_parse_failure",
             "comparison": "not_comparable", "input_mutated": None}
        ] * 3)
        with self.assertRaises(E2Error):
            score_unexecuted_d_panel("ok", 3)

    def test_missing_or_malformed_cached_responses_fail_closed(self):
        with self.assertRaises(E2Error):
            score_cached_d_panel("humaneval", "f", 0, [pack(1), pack(2)], [{"status": "ready"}])
        with self.assertRaises(E2Error):
            score_cached_d_panel("humaneval", "f", 0, [pack(1)], [{"status": "ready"}, {"status": "ok"}])

    def test_deterministic_baseline_ties_use_original_candidate_identity(self):
        candidates = [
            {"candidate_id": "id-3", "original_sample": 3},
            {"candidate_id": "id-0", "original_sample": 0},
            {"candidate_id": "id-2", "original_sample": 2},
            {"candidate_id": "id-1", "original_sample": 1},
        ]
        v = {candidate["candidate_id"]: 2 for candidate in candidates}
        d = {candidate["candidate_id"]: {"pass_count": 1} for candidate in candidates}
        signatures = {candidate["candidate_id"]: "same" for candidate in candidates}
        result = deterministic_baselines(candidates, v, d, signatures)
        self.assertEqual(result["visible_pass_count"], "id-0")
        self.assertEqual(result["d_only_pass_count"], "id-0")
        self.assertEqual(result["v_plus_d_pass_count"], "id-0")
        self.assertEqual(result["visible_consensus"], "id-0")


if __name__ == "__main__":
    unittest.main()
