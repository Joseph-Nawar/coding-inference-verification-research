# Coding inference and verification research

This ongoing research program studies when additional inference helps short Python code generation and repair, and where the gains are lost. It uses local Apple Silicon, automated executable benchmarks and explicit boundaries between generation and evaluation. The work is exploratory and has not undergone peer review.

**Current status:** The narrow EvalPlus amendment is approved and the separated scorer is in technical preflight. Synthetic checker diagnostics are separate from benchmark evidence. The eight-task P1 smoke is gated on evaluator validity, separated scoring, containment and parity. The six hypotheses remain untested. [Current evaluator protocol](docs/09_p0_recovery_v2.md)

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
- E1 measures shared-pool headroom and deterministic selection. E2 varies the evidence shown to a selector while holding candidates fixed. E3 crosses initial-code context with visible feedback and measures regression. E4 separates test discrimination from label validity. Each requires separate researcher approval.
- Confirmation requires a separate registered design and protected tasks. Public benchmarks can still be familiar to pretrained models. [Charter](docs/01_charter.md) · [Experiment portfolio](docs/05_experiments.md) · [Analysis](docs/06_analysis.md)

## Reproduce the evaluator diagnostic

The fixture is synthetic and runs on an ARM64 Docker Desktop image pinned by digest. The reproduction guide specifies source archives, wheel hashes, build commands and restrictions. The image is dedicated to regression fixtures. The current protocol documents the production candidate container, scorer and technical entry gates. [Regression reproduction](docs/08_evalplus_regression.md) · [Proposed configuration](configs/p0-proposed.yaml) · [Security contract](docs/04_security.md)

Study protocols and decisions are in [docs](docs/), [reports](reports/) and the [literature matrix](reports/LITERATURE_MATRIX.md). Baseline P0 records reflect the original handoff scope. Later authorization allows publication of the audited project files. Protected split material, evaluator labels and raw run artifacts are local.
