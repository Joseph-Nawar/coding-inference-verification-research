# E1-R Publication Audit

**Audit scope:** Existing public repository history plus the proposed E1-R milestone.

**Reviewed public base:** the expected main commit supplied for this milestone.

**Result:** Proposed E1-R files contain no identified private task/candidate identity, prompt, sealed label row, long candidate-code fragment, credential, personal email, machine-specific path, model weight/cache, or oversized artifact.

## Historical finding and treatment

The full-history scan found one older public status artifact containing a SHA-256 commitment to the private original E1 ledger. That file predates this milestone. The new public tree will remove the run-ledger digest while preserving its non-sensitive aggregate counters and status. Existing public commits will remain unchanged; the old digest remains in public history because the research repository history is being preserved and main will not be force-rewritten. The private ledger and its source-of-record manifest remain local.

Other hash matches were the public model-checkpoint file digests already used in the repository's model/configuration reproducibility records. No model weight files or benchmark caches were found. The new E1-R files add no private registration, split, prompt, candidate, or run-artifact digest.

The first test run in the separate publication checkout exposed a pre-existing source/test mismatch: a published continuation test imported analyze_records, which the public-main copy of e1_analysis.py did not define. The already-tested local implementation contains this reusable analysis API. I backported that safe source file into the publication tree. The focused regression failed with the missing import before the backport and passed after it. This is source-history reconciliation only; it does not change generation, scoring semantics, or E1 outcomes. The final pinned-environment suite in the exact publication checkout ran 80 tests: 69 passed and 11 environment-gated tests skipped.

## Scans

The audit covered all unique blobs reachable from public refs and the proposed source, tests, README, decision records, reports, aggregate JSON, and the analysis API backport. Protected canaries were derived locally from the development and confirmation membership strings, E1 candidate identities, development prompts, sealed-label rows, and long candidate source fragments. Confirmation benchmark records and outcomes were not opened.

| Check | Findings in proposed E1-R files |
| --- | ---: |
| Credential and secret patterns | 0 |
| Personal email addresses | 0 |
| Machine-specific absolute paths | 0 |
| Protected split/candidate identity matches | 0 |
| Exact development-prompt, sealed-label-row, or long candidate-code matches | 0 |
| Files over 10 MiB | 0 |

The public-history check also found no commit author/committer addresses outside GitHub noreply addresses. The existing public history is preserved. The new public milestone will be a direct child of the reviewed main tip and will not contain the private local branch ancestry. No standalone reuse license was added.

The historical status digest finding is recorded here rather than hidden. It is an already-public non-reversible commitment, not the ledger contents or correctness labels. The current public tree omits it; no force-push or historical rewrite was performed.
