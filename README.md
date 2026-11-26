# Coding inference and verification research

This ongoing research program studies when additional inference helps short Python code generation and repair, and where the gains are lost. It uses local Apple Silicon, automated executable benchmarks and explicit boundaries between generation and evaluation. The work is exploratory and has not undergone peer review.

**Current status:** E1 remains incomplete after six of eight registered chunks (30 of 40 tasks). The original 20-task report and the later resource stop are preserved. A post-outcome E1-R interim analysis reports the 30 checkpointed tasks; 13 outputs from the interrupted partial chunk remain generation-only and are excluded from correctness analysis. The E1-R feasibility review made no additional model calls, candidate executions, E2 interventions, or confirmation access. All six hypotheses remain unresolved; E1 provides descriptive evidence most relevant to H1 and H3. See the [E1-R interim analysis](reports/E1R_INTERIM_ANALYSIS.md), [safe aggregate results](reports/E1R_INTERIM_AGGREGATES.json), [E2 feasibility report](reports/E2_FEASIBILITY_E1R.md), [publication audit](reports/PUBLICATION_AUDIT_E1R.md), [E1-R decision record](docs/14_e1r_decision_record.md), [original E1 review](reports/E1_REVIEW.md), [continuation resource report](reports/E1_CONTINUATION_RESOURCE_RECOVERY.md), and [resource-stop decision](docs/12_e1_continuation_stop.md).

**E2 status:** The final label-blind technical preflight supports a private balanced sample of 12 HumanEval+ and 12 MBPP+ tasks from the six validated E1 checkpoints. All 96 frozen prompts fit the registered context allowance. Selector inference has not started because the required fresh boot and application-closure gate was not met. No E2 outcomes were generated and H1–H6 remain unresolved. See the [E2 pre-inference report](reports/E2_PREINFERENCE_STATUS.md), [safe aggregates](reports/E2_PREINFERENCE_AGGREGATES.json), [protocol amendment v1](docs/15_E2_PROTOCOL_AMENDMENT_V1.md), [technical amendments v2](docs/16_E2_PREOUTCOME_TECHNICAL_AMENDMENT_V2.md) and [v3](docs/17_E2_PREOUTCOME_TECHNICAL_AMENDMENT_V3.md), [information-boundary amendment v4](docs/18_E2_PREOUTCOME_INFORMATION_BOUNDARY_AMENDMENT_V4.md), [decision record](docs/19_E2_PREINFERENCE_DECISION_RECORD.md), and [resolved E2 configuration](configs/e2-v4.yaml).

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
