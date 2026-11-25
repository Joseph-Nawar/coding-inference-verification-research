# EvalPlus decision v1

25 November 2026 · P0 recovery · **TECHNICAL_BLOCKED** pending review of a narrow correction.

## Findings and decision

The proposed revision `26d6d00bb1fd0fa37f39c99d5290da67891d1c5e` contains the `find_zero` bookkeeping correction. Its 44-commit delta from v0.3.1 also changes verdicts under default timeout policy. The 1.25-second synthetic solution fails under the release and the fix commit. It passes under the proposed revision, where the default per-case floor increases from 1 to 4 seconds. The default directly affects the registered full-protocol endpoint and compute cap. I did not adopt the broad revision. [Comparison](https://github.com/evalplus/evalplus/compare/e5d0ed0bab96280b60b637ec7f15b5e4841b0cb2...26d6d00bb1fd0fa37f39c99d5290da67891d1c5e) · [Timeout change](https://github.com/evalplus/evalplus/commit/af491388b36f055e8d9a33c831f01645ba1fe856)

Proposed version `evalplus-0.3.1+research.findzero.1` would start from the immutable release and apply exactly the two insertions from `6eb1e199c2e370518e7bf3e8eee6322c2b23c89c`: record a successful case and increment progress before continuing. The patched checker file must have SHA-256 `3c833c39b842e33f251c83db4347e0a95191909f23b390c12d73ab29a28a4daf`. Keep release data, default timeout, CLI behavior and dependency policy, with a separate trusted comparator required for empirical use. This is a proposed change for approval. No amended benchmark scorer was installed. [Fix commit](https://github.com/evalplus/evalplus/commit/6eb1e199c2e370518e7bf3e8eee6322c2b23c89c)

Issue #334 was open at review. The reporter separately identified six failures in the published canonical reference under the existing polynomial residual rule. The synthetic fixture verifies the pass-recording fix and an invalid root rejection. Neither test evaluates any public issue input or benchmark reference. A prospective qualification is required before the affected task can be used in any later confirmatory design. Its task membership and detailed labels were not inspected. No benchmark input, threshold, label or split was changed. [Upstream issue](https://github.com/evalplus/evalplus/issues/334)

## Source audit

| Source | Checker SHA-256 | Config SHA-256 |
| --- | --- | --- |
| `e5d0ed0bab96280b60b637ec7f15b5e4841b0cb2` | `76857b678cddca08dcaf54d7927b9a77826715cf657654ca5baf6c2b267f4c34` | `dc14b4400cbf05d5bcab5b94d785f046cca22b0dbc10bc9756f8356dc42f18e3` |
| `6eb1e199c2e370518e7bf3e8eee6322c2b23c89c` | `3c833c39b842e33f251c83db4347e0a95191909f23b390c12d73ab29a28a4daf` | `dc14b4400cbf05d5bcab5b94d785f046cca22b0dbc10bc9756f8356dc42f18e3` |
| `26d6d00bb1fd0fa37f39c99d5290da67891d1c5e` | `3c833c39b842e33f251c83db4347e0a95191909f23b390c12d73ab29a28a4daf` | `d27099cc275ae6e64fb2c440643fc3b5d0952d1633db646e206b538517ffe6f2` |

The special-oracle source is byte-identical at all three revisions, SHA-256 `92b126b907ee493121b55de06f6a34058b6e18adc8cf1c48737eedcd83f24cdd`. The release and fix utilities are byte-identical with SHA-256 `0aec25f437dbc7637219ba749ba71921670e71cd2e70b1cc23988896c0754bb1`. The later utility hash is `5bf8925c8dd7c8f06b05c0ff4f28672e8e3b61d1b567b6a86b90e80bd8b780a4` and includes a Windows-specific relaxation of the upstream memory guard. This does not change the Linux guard path audited here. The broad revision adds provider options and removes `stop-sequencer` while adding `boto3` and `ollama` to base package metadata. It also changes CLI result naming, output selection and saved pass@k metadata. The synthetic checker subset pins NumPy and psutil wheels. It does not resolve the full evaluator dependency chain. [Source archives and fixture dependencies](../docs/08_evalplus_regression.md)

The oracle computes a polynomial residual for `find_zero`. Exact equality is generally checked first, followed by the same-type `allclose` fallback for nonzero tolerances. A float expected output can set the default tolerance to `1e-6` for subsequent cases in that invocation. MBPP special cases include rounded surface area, padded digit distance, set comparison, non-None, reference-or-zero `sum_div`, and the permissive `are_equivalent` check. A fresh process for each test would remove ordering, function globals and mutations retained during a panel. The reference helper deep-copies each input, while the checker invokes candidates in order and compares after candidate execution. A separated comparator must account for the effect of input mutation on oracles and report unsupported representations. In detailed mode an exception can fail one case and leave the rest evaluable. Upstream catches a per-case timed interrupt as a failed test, while a whole-check watchdog can yield a timeout. These distinctions do not change with the two-line correction. [Pinned checker](https://github.com/evalplus/evalplus/blob/e5d0ed0bab96280b60b637ec7f15b5e4841b0cb2/evalplus/eval/__init__.py)

## Synthetic checker evidence

17 fixtures ran against each of three upstream sources. All 51 assertions matched expected verdicts and detail vectors after environment probe correction.

| Fixture | v0.3.1 | Fix commit | Later proposal |
| --- | --- | --- | --- |
| Valid alternative polynomial root, fast and detailed | Fail with zero recorded results | Pass with both cases recorded | Pass with both cases recorded |
| Invalid polynomial root | Fails | Fails | Fails |
| Synthetic 1.25 s case, default floor | Fails at 1 s | Fails at 1 s | Passes at 4 s |
| Float within and outside tolerance, outer-type mismatch | Expected | Expected | Expected |
| Set alternative, reference-or-zero, non-None and permissive MBPP case | Expected | Expected | Expected |
| Global state and retained input mutation across ordered cases | Expected | Expected | Expected |
| Missing entry point, syntax error, exception followed by success, explicit per-case timeout | Expected | Expected | Expected |

The first invocation stopped before evaluator fixtures on an overly strict check that required the namespace to contain only one named interface. Linux exposes inactive tunnel devices in that namespace. A diagnostic recorded the interfaces. The corrected probe required loopback to be the only interface marked up and verified an empty IPv4 routing table. The Docker network configuration remained `none`. The failed run and the diagnostic log were retained. [Fixture source](../tests/evalplus_regression.py) · [Launcher](../tests/run_evalplus_regression.py)
