import unittest
from ciresearch.e1_data import unique_panels, chunk_indices
from ciresearch.e1_metrics import choose, pass_at_k


class E1Tests(unittest.TestCase):
    def test_balanced_chunks_preserve_order(self):
        grouped = list(chunk_indices())
        self.assertEqual([len(g) for g in grouped], [5] * 8)
        self.assertEqual([i for g in grouped for i in g if i < 20], list(range(20)))
        self.assertEqual([i for g in grouped for i in g if i >= 20], list(range(20, 40)))
        self.assertEqual([sum(i < 20 for i in g) for g in grouped], [3, 2] * 4)

    def test_distinct_d_and_h_distinguish_tuple_and_list(self):
        base = [[[0]], [[1]]]
        plus = [*base, [(1,)], [[1]], *[[i] for i in range(2, 20)]]
        diagnostic, heldout = unique_panels(base, plus)
        self.assertEqual(len(diagnostic), 8)
        self.assertEqual(len(heldout), 11)
        self.assertIn([(1,)], diagnostic + heldout)
        self.assertEqual(unique_panels([], [[0], [1]]), ([], []))

    def test_ties_and_missing_visible_evidence(self):
        rows = [{"v_count": 1, "signature": "a"}, {"v_count": 2, "signature": "b"},
                {"v_count": 2, "signature": "a"}, {"v_count": 0, "signature": None}]
        self.assertEqual(choose(rows), {"pass_count": 1, "consensus": 0})
        self.assertIsNone(choose([{"v_count": None, "signature": None}])["pass_count"])

    def test_pass_at_k_uses_full_bank(self):
        self.assertAlmostEqual(pass_at_k(8, 2, 4), 11/14)
        self.assertEqual(pass_at_k(8, 2, 8), 1.0)
