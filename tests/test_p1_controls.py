import tempfile
from pathlib import Path
import unittest
from types import SimpleNamespace

from ciresearch.extract import extract
from ciresearch.p1 import panels, run


class P1ControlTests(unittest.TestCase):
    def test_extraction_retains_invalid_text_while_classifying(self):
        sample = "preface\n```python\ndef solve(x): return x\n```\nafter"
        self.assertEqual(extract(sample, "solve"), ("ok", "def solve(x): return x"))
        self.assertEqual(extract("def solve(:", "solve"), ("invalid_syntax", "def solve(:"))
        self.assertEqual(extract("value = 1", "solve"), ("missing_entry", "value = 1"))

    def test_panels_preserve_first_occurrences_and_exclude_visible(self):
        task = {"base_input": [[0]], "plus_input": [[i] for i in range(20)] + [[4]]}
        d, h = panels(task)
        self.assertEqual(len(d), 8)
        self.assertEqual(len(h), 11)
        self.assertEqual(set(d) | set(h), set(range(1, 20)))

    def test_empirical_entry_rejects_incomplete_gates(self):
        with tempfile.TemporaryDirectory() as temp:
            auth = Path(temp) / "authorization.json"
            auth.write_text('{"stage":"P1"}')
            with self.assertRaisesRegex(ValueError, "technical gates"):
                run(SimpleNamespace(authorization=auth))
