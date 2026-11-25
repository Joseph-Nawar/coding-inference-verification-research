# Coding-model inference and verification — research program handoff

Version 0.1 | 2026-11-25 | Researcher decision required at each phase boundary

**Purpose:** understand why extra inference fails to improve Python code generation, and develop a valuable AI R&D contribution from evidence. This is an exploratory research program, not a preregistered confirmatory paper or a novelty claim.

## Start here
1. Create a new local repository (suggested name `coding-inference-verification-research`). Keep previous pilots unchanged.
2. Extract this directory into it, preserving paths. Read `AGENTS.md` and all `docs/`.
3. Give Codex `prompts/CODEX_START.md`. Only P0/P1 are initially authorized; subsequent commands require researcher approval.
4. Review `reports/P0_PREFLIGHT.md`, `reports/P1_SMOKE.md`, status JSON, and evidence manifests before approving any exploratory run.

## Files
- `docs/01_charter.md`: scope, research questions, phase decisions.
- `docs/02_literature.md`: reading/reproduction obligations and sources.
- `docs/03_data_and_evaluation.md`: task splits, information boundaries, correctness rules.
- `docs/04_security.md`: fail-closed execution contract.
- `docs/05_experiments.md`: shared candidate pool, four controlled experiments and follow-ups.
- `docs/06_analysis.md`: estimands, uncertainty, interpretation and decision rules.
- `docs/07_execution_and_artifacts.md`: staged implementation, resources, reporting and acceptance checks.
- `configs/exploration.yaml`: proposed numerical defaults and caps; review amendments before use.
- `templates/hypothesis_register.md`, `templates/decision_record.md`, `templates/experiment_record.md`: working research records.
- `prompts/CODEX_START.md`, `prompts/CODEX_EXPLORE_AFTER_APPROVAL.md`: gated handoffs.

No experiments have been run by the author of this package. Versions, model revisions, exact dataset sizes, compatibility, cost and licenses must be verified in P0. Keep all artifacts private/local by default. No push, paid APIs, or cloud computation is authorized.
