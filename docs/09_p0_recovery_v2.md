# P0 recovery v2 protocol amendment

25 November 2026. The researcher approved `evalplus-0.3.1+research.findzero.1` before any empirical generation or scoring. The only source changes are the two successful-check bookkeeping insertions from upstream commit `6eb1e199c2e370518e7bf3e8eee6322c2b23c89c`, applied to release commit `e5d0ed0bab96280b60b637ec7f15b5e4841b0cb2`. Source verification requires SHA-256 `76857b678cddca08dcaf54d7927b9a77826715cf657654ca5baf6c2b267f4c34` before and `3c833c39b842e33f251c83db4347e0a95191909f23b390c12d73ab29a28a4daf` afterward. The release inputs, reference labels, tolerances, dependency policy, and one-second timeout floor still apply. Issue #334 requires prospective qualification before confirmation. No protected task was opened to resolve it.

The engineering sequence is checksum-verified amendment, bounded typed panel protocol, restricted ARM64 candidate worker, separate trusted scoring, and synthetic and smoke-fixture parity. A worker loads the candidate once per panel and receives positional inputs one at a time. It receives no expected values, task IDs, comparison rules or future cases. The host validates each response before sending another case. Candidate control of its own result stream is a residual integrity limitation. The trusted scorer must distinguish unsupported values and process or protocol failures from model errors. Empirical P1 remains gated on technical acceptance. The approved scope is eight smoke tasks and at most 24 total model calls. The held-out and development boundaries remain in effect.

## Local reproduction

The amendment utility accepts an immutable verified release checker and creates a new output file. Stage the output at `evalplus/eval/__init__.py` only in a private copy of the pinned release archive. The patch utility verifies its two input/output hashes. The official fixture image also checks the resulting hash at build time.

```sh
PYTHONPATH=src python3 -m ciresearch.amendment path/to/release-checker.py path/to/patched-checker.py
```

[Full ARM64 evaluator lock](../configs/evaluator-arm64.lock) preserves upstream dependencies. Three release dependencies publish source distributions only. Download the five source-build inputs from their pinned PyPI packages and verify them with [the build input manifest](../configs/evaluator-source-build-sha256.txt). Use the [offline wheelhouse recipe](../sandbox/Dockerfile.evaluator-wheelhouse) with those five files as its entire build context. The resulting wheel hashes are in the full lock. The lock records the release distribution identity. The patched checker has a separate source identity and is copied from the approved source tree. The checker-only parity image installs the same pinned NumPy and psutil versions and imports the approved checker sources directly. The host comparator has a [separate ARM64 macOS NumPy lock](../configs/scorer-macos-arm64.lock).

Build the candidate image with the [candidate Dockerfile](../sandbox/Dockerfile.candidate). Its build context only needs `src/ciresearch/wire.py` and `src/ciresearch/worker.py`. Build the trusted fixture image using its [Dockerfile](../sandbox/Dockerfile.official-fixture) in a separate context with the patched checker, release config, special-oracle and utility modules, release license, reference helper `evalplus/gen/util/__init__.py`, two hash-verified wheels and `ciresearch/{wire,official_fixture}.py`. Use the lock from the original [fixture build guide](08_evalplus_regression.md) as `requirements.txt`. Build both with `--platform linux/arm64 --network none --pull=false` and retain the resulting image IDs.

Run standard-library tests using the host NumPy environment, preserving a new ignored evidence directory.

```sh
PYTHONPATH=src CIRESEARCH_RELEASE_CHECKER=path/to/release-checker.py \
  CIRESEARCH_CANDIDATE_IMAGE=sha256:<candidate-image-id> \
  CIRESEARCH_CANDIDATE_EVIDENCE=.research-private/new-containment-evidence \
  python3 -m unittest discover -s tests -p 'test_*.py' -v
```

For `tests/parity_v2.py` also supply `CIRESEARCH_OFFICIAL_IMAGE` and a fresh `CIRESEARCH_PARITY_EVIDENCE` path. Protected smoke-fixture inputs, implementation scaffolds, raw output and the empirical authorization records stay local. The empirical entry point rejects runs without validated image IDs, model file digests and all technical gates. It accepts only the pinned eight-task smoke audit. The planned smoke uses two samples per task plus one live seed replay, with no selector or repair calls. D/H results use the original plus-panel observations at the first occurrence of each typed unique input, so their comparison retains the original panel order.
