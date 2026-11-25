import math
import unittest

from ciresearch.wire import WireError, read_frame, write_frame, pack, unpack
from ciresearch.scoring import Comparator


class WireTests(unittest.TestCase):
    def test_round_trips_builtin_types(self):
        original = [True, 1, -0.0, math.inf, (1, 2), {3, 4}, {-1: 1j}, b"foo"]
        restored = unpack(read_frame(write_frame(pack(original))))
        self.assertEqual(restored, original)
        self.assertEqual(math.copysign(1, restored[2]), -1)
        self.assertIs(type(restored[0]), bool)
        self.assertIs(type(restored[4]), tuple)

    def test_rejects_malformed_or_excess_frames(self):
        for frame in (b"{}", b'{"a":1,"a":2}\n', b"NaN\n", b"x" * 65_537):
            with self.subTest(size=len(frame)), self.assertRaises(WireError):
                read_frame(frame)
        for value in (["list", []], {"unknown": 1}, ["i", "1_2"], [0], ["s", 4]):
            with self.subTest(value=value), self.assertRaises(WireError):
                unpack(value)

    def test_rejects_custom_objects_and_cycles(self):
        class Impostor(int):
            pass
        loop = []
        loop.append(loop)
        for value in (Impostor(2), loop):
            with self.assertRaises(WireError):
                pack(value)


class ScoringTests(unittest.TestCase):
    def test_mutation_sensitive_root_comparison(self):
        scorer = Comparator("humaneval", "find_zero", 1e-6)
        self.assertTrue(scorer.compare(-1, 1, [[-1, 0, 1]]))
        self.assertFalse(scorer.compare(0, 1, [[-1, 0, 1]]))

    def test_set_tolerance_and_types(self):
        self.assertTrue(Comparator("mbpp", "similar_elements", 0).compare([2, 1, 2], [1, 2], []))
        c = Comparator("humaneval", "solve", 0)
        self.assertTrue(c.compare(0.0000005, 0.0, []))
        self.assertFalse(c.compare((0.0000005,), [0.0], []))
        self.assertTrue(c.compare([0.0000005], [0.0], []))
