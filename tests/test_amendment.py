import hashlib
import unittest

from ciresearch.amendment import amend_checker


class AmendmentTests(unittest.TestCase):
    def test_rejects_an_unverified_checker(self):
        with self.assertRaisesRegex(ValueError, "release checker hash"):
            amend_checker(b"unverified")

    def test_verifies_the_approved_digest(self):
        from pathlib import Path
        import os

        source = os.environ.get("CIRESEARCH_RELEASE_CHECKER")
        if not source:
            self.skipTest("set CIRESEARCH_RELEASE_CHECKER to the pinned release checker")
        before = Path(source).read_bytes()
        after = amend_checker(before)
        self.assertEqual(hashlib.sha256(after).hexdigest(),
                         "3c833c39b842e33f251c83db4347e0a95191909f23b390c12d73ab29a28a4daf")
        self.assertEqual(len(after.splitlines()) - len(before.splitlines()), 2)
