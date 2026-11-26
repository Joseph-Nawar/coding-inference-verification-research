# E1-R Interim Decision Record

**Recorded:** 26 November 2026

**Decision:** Complete read-only E1-R interim analysis; preserve the E1 resource stop; return for researcher review.

**Research status:** E1 is incomplete; the program remains exploratory. No scientific NO-GO or change of research direction is recorded.

## Authorization and scope

The E1-R authorization permitted read-only validation of the accepted E1 evidence, lightweight interim-analysis implementation and synthetic tests, and E2 feasibility assessment. It set a hard limit of zero additional model calls and zero candidate executions. E2 calls, E3/E4 interventions, confirmation access, and E1 resumption were outside this authorization and were not performed.

The analysis includes only the 20 original tasks and 10 continuation tasks with six complete checkpoints. The 13 outputs from the later partial chunk are preserved as generation-only evidence and excluded from all correctness and selection metrics. The interrupted call was not retried. The original and continuation ledgers and manifests remain separate.

## Integrity and analytical record

The hash-bound original parent and continuation manifest validations passed. The interim validator rechecked six checkpoint artifacts, identities and order, freeze chronology, evidence coverage, raw generation artifacts and resource counters. It returned a frozen analytical view of 240 checkpointed candidates and did not include the partial chunk.

## Publication-only correction

The full public-history audit found that an older public E1 status file included the private original run-ledger SHA-256 commitment. The new public-tree copy removes that field while retaining aggregate counters and status. Existing public commits remain intact; no force rewrite is performed. The digest is not repeated in the E1-R report or source. Three existing model/configuration records contain public model-file checksums for reproducibility; no model weights or benchmark caches are included. The audit and its scope are recorded in [the E1-R publication audit](../reports/PUBLICATION_AUDIT_E1R.md).

The exact public checkout also exposed a source/test mismatch: the published continuation regression expected analyze_records in e1_analysis.py, while public main lacked it. The version already validated locally was backported to the publication tree. The focused test failed before the source correction and passed afterward; the full pinned-environment suite then passed with 80 tests, 69 passes, and 11 environment-gated skips. This analytical-source backport changes no experiment or scored result.

A fresh analysis exactly reproduced the preserved v2 aggregate using the registered full-population bootstrap frame: 2,000 task-level replicates, drawing 20 task slots per benchmark. The original 20-task values match the previously published original E1 report. The historical report and first v1 interim aggregate were not overwritten.

The v1 interim aggregate remains preserved but superseded: its bootstrap frame followed observed segment size rather than the registered 20-per-benchmark frame. The correction was recorded in the E1-R analytical amendment before inspecting metric estimates. This remains retrospective analysis because candidate generation, visible selection and correctness labels already existed.

The E2 technical eligibility implementation was corrected before its eligibility freeze to retain initialization-exception statuses as available recorded diagnostic evidence. This affects technical evidence classification only; it did not use correctness labels, add execution, or alter the frozen candidate bank.

A subsequent reporting-only extraction requested an interval key named ci_low, which the saved aggregate does not contain. That command failed before producing the intended table. The aggregate schema's interval field is ci95; reading it produced the report tables without changing any estimate or evidence. The failed extraction and corrected command are retained in the local diagnostic record.

## Findings and limitations

Across the 30-task interim population, 29 tasks have complete official labels and 28 have complete integrity-qualified labels. The original transport limitation and reference qualifications remain unchanged. At k=8 the official-compatible oracle-any point estimate is 82.8%, compared with 72.4% for each visible selector; intervals and 40-task missingness bounds remain wide. The first-four technical E2 pool contains 28 eligibles, including 11 mixed pools under each endpoint, with one integrity-qualified label-incomplete pool. These are exploratory descriptive results, not causal evidence about model reasoning.

The first-four E2 feasibility assessment found 13 HumanEval and 15 MBPP technical eligibles. It used a tokenizer context proxy, not a finalized E2 prompt. E1's public protocol has no prelocked E2 hash-order artifact, and the current inference worker is code-generation-only. No sample was chosen. A future E2 needs a prospective, label-blind ordering and prompt amendment, final context retest, and separate researcher authorization.

The continuation resource stop remains unchanged. The continuation was run on the same boot without restarting or closing applications; swap rose materially and persisted. The cause remains unresolved. No resource limit or security control was weakened.

## Researcher review request

E2 is recommended as the next investigation because it can compare evidence availability with interpretation on a fixed candidate bank and directly address competing H1/H3 explanations. Before any E2 calls, review and approve a prospective amendment for the hash order, exact benchmark balance, selector prompt/output protocol and resource preflight. E2–E4 and confirmation remain unauthorized pending that review.

Low model competence, small-sample uncertainty, missing labels, or a technical resource stop do not constitute a program NO-GO. All six hypotheses remain unresolved; E1 provides descriptive evidence most relevant to H1 and H3, while H2, H4, H5 and H6 require later controlled experiments.
