# Coding inference and verification research

This ongoing research program studies when additional inference helps short Python code generation and repair, and where the gains are lost. It uses local Apple Silicon, automated executable benchmarks and explicit boundaries between generation and evaluation. The work is exploratory and has not undergone peer review.

**Current status:** E1 remains incomplete after six of eight registered chunks (30 of 40 tasks). The original 20-task report and the later resource stop are preserved. A post-outcome E1-R interim analysis reports the 30 checkpointed tasks; 13 outputs from the interrupted partial chunk remain generation-only and are excluded from correctness analysis. The E1-R feasibility review made no additional model calls, candidate executions, E2 interventions, or confirmation access. All six hypotheses remain unresolved; E1 provides descriptive evidence most relevant to H1 and H3. See the [E1-R interim analysis](reports/E1R_INTERIM_ANALYSIS.md), [safe aggregate results](reports/E1R_INTERIM_AGGREGATES.json), [E2 feasibility report](reports/E2_FEASIBILITY_E1R.md), [publication audit](reports/PUBLICATION_AUDIT_E1R.md), [E1-R decision record](docs/14_e1r_decision_record.md), [original E1 review](reports/E1_REVIEW.md), [continuation resource report](reports/E1_CONTINUATION_RESOURCE_RECOVERY.md), and [resource-stop decision](docs/12_e1_continuation_stop.md).

**E2 status (27 November 2026):** The frozen 12/12 sample, prompts, call identities, candidate order, and 96-call schedule remain unchanged. The five historical private integrity pins were recovered from preserved local Git history; the pinned parent validator, continuation manifest, and six-checkpoint interim integrity checks passed, and the frozen private E2 registration remained unchanged. Selector inference is still blocked: the observed boot predates the registered fresh-boot threshold and the foreground-application closure condition was not established. No model calls, candidate executions, label joins, or confirmation accesses occurred. All six hypotheses remain unresolved. See the [E2 blocker-resolution addendum](reports/E2_BLOCKER_RESOLUTION_2026-11-27.md), the [historical E2 pre-inference report](reports/E2_PREINFERENCE_STATUS.md), [safe aggregates](reports/E2_PREINFERENCE_AGGREGATES.json), [protocol amendment v1](docs/15_E2_PROTOCOL_AMENDMENT_V1.md), [technical amendments v2](docs/16_E2_PREOUTCOME_TECHNICAL_AMENDMENT_V2.md) and [v3](docs/17_E2_PREOUTCOME_TECHNICAL_AMENDMENT_V3.md), [information-boundary amendment v4](docs/18_E2_PREOUTCOME_INFORMATION_BOUNDARY_AMENDMENT_V4.md), [decision record](docs/19_E2_PREINFERENCE_DECISION_RECORD.md), and [resolved E2 configuration](configs/e2-v4.yaml).

The public continuation source requires five local environment-provided integrity pins for validating the private stopped-run evidence. The publication-only refactor and its chronology are documented in the resource-stop decision; raw candidates, private commitments, and protected evaluation artifacts remain local.

## Hypotheses

| ID | Question |
| --- | --- |
| H1 | Are gains limited by candidate generation, discriminative evidence, or the model's interpretation of evidence? |
| H2 | Does feedback help because it carries distinct diagnostic information, because it carries more information, or because the model can act on it? |
| H3 | How do invalid, weak, or correlated generator and verifier signals affect selection? |
| H4 | When does initial code context help repair, and when does it anchor the model to a poor solution? |
| H5 | How often does refinement regress initially correct programs, and when can visible-evidence retention avoid it? |
| H6 | How do those bottlenecks vary with model capability, task difficulty and inference budget? |

## Roadmap

- P0 verifies provenance, licensing, split commitments, scoring semantics and resource limits. P1 validates the engineering pipeline on synthetic fixtures and a bounded eight-task smoke.
- E1 measures shared-pool headroom and deterministic selection. E2 varies the evidence shown to a selector while holding candidates fixed; it is approved conditional on the fresh-boot, resource, and integrity gates. E3 crosses initial-code context with visible feedback and measures regression. E4 separates test discrimination from label validity. E3, E4, and confirmation require separate researcher approval.
- Confirmation requires a separate registered design and protected tasks. Public benchmarks can still be familiar to pretrained models. [Charter](docs/01_charter.md) · [Experiment portfolio](docs/05_experiments.md) · [Analysis](docs/06_analysis.md)

## Reproduce the evaluator diagnostic

The fixture is synthetic and runs on an ARM64 Docker Desktop image pinned by digest. The reproduction guide specifies source archives, wheel hashes, build commands and restrictions. The image is dedicated to regression fixtures. The current protocol documents the production candidate container, scorer and technical entry gates. [Regression reproduction](docs/08_evalplus_regression.md) · [Proposed configuration](configs/p0-proposed.yaml) · [Security contract](docs/04_security.md)

Study protocols and decisions are in [docs](docs/), [reports](reports/) and the [literature matrix](reports/LITERATURE_MATRIX.md). Baseline P0 records reflect the original handoff scope. Later authorization allows publication of the audited project files. Protected split material, evaluator labels and raw run artifacts are local.
