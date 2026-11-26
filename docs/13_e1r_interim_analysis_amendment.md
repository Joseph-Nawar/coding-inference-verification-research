# E1-R interim analysis amendment

**Decision date:** 26 November 2026

**Decision:** `REVISE_SETUP`

**Status:** Retrospective exploratory analysis authorized; no additional empirical execution.

## Scope and chronology

This amendment records the researcher authorization in E1-R. The E1 generation, visible-evidence selection, and checkpoint scoring decisions already occurred. The original 20-task results were previously analyzed and published; the continuation's two completed chunks and partial chunk-6 generations were already produced. Therefore this is a post-outcome analytical plan, not a preregistration and not a claim that analysis choices preceded all outcomes.

The amendment permits read-only evidence validation, synthetic tests, descriptive analyses of exactly the six complete chunks, and technical/retrospective E2 feasibility assessment. It authorizes zero additional empirical model calls, candidate executions, reference computations, or benchmark panels. E2–E4 interventions and confirmation access remain unauthorized.

## Evidence populations

The source of record remains the immutable original E1 run and continuation segment. Analysis populations are fixed as:

1. Original segment: its four already accepted checkpoint chunks (20 tasks).
2. Continuation segment: only its first two complete checkpoint chunks (10 tasks).
3. Combined interim population: those six chunks (30 tasks), reported against the original 40-task registration.

The analytical view must be constructed only after the original evidence manifest, parent registration, parent ledger, continuation registration, segment manifest, parent binding, chunk artifact hashes, identity ordering, freeze chronology, and resource counters validate. It includes only candidate records belonging to those six checkpoints. The existing complete-population validator remains strict and unchanged.

The 13 complete raw outputs from the incomplete next chunk remain generation-only evidence. They are not frozen as a candidate bank, selected, evaluated, or included in correctness metrics. The one started generation without a complete output remains an infrastructure-interrupted attempt with unavailable correctness and will not be retried. The 66 unstarted registered identities remain missing. The two historical resource stops are preserved as part of the research record.

## Registered analyses

Use the definitions in `docs/06_analysis.md` and `docs/10_e1_experiment.md`: nested prefixes `k = 1, 2, 4, 8`; first candidate, uniform expected selection, visible pass-count, visible behavioral consensus, empirical prefix oracle, unbiased pass@k where assumptions and labels permit, oracle headroom, and paired change from candidate zero. Report official-compatible and integrity-qualified endpoints separately. Report verification denominators, candidate-pool composition, visible behavioral clusters, duplicates, failures, benchmark-specific estimates, and task-level paired bootstrap percentile intervals.

For each observed population, reuse the registered bootstrap frame: 2,000 draws with 20 task slots sampled with replacement from each original 20-task benchmark stratum (the original 40 registered task identities), using seed 11252026. Candidate and panel records remain nested within task; metrics are computed only where the selected scope has valid records. Incomplete registered tasks are never treated as missing at random. Report available-case estimates and worst/best population bounds against all 40 registered tasks, including unavailable task labels in the bounds. Segment differences are descriptive and do not identify session effects or causal interruption effects.

Keep the registered eligibility qualifications unchanged. Report completed task checkpoints separately from tasks with complete official-compatible and integrity-qualified labels. Explain that false rejection against a full-suite endpoint containing visible tests is structurally constrained.

## E2 feasibility boundary

Technical eligibility is determined from frozen first-four candidate records and cached V/D evidence, before joining full correctness labels. Do not use outcome labels for future E2 task eligibility, ordering, sample selection, prompt construction, or selector inputs. Calculate offline token counts for registered conditions A–D using the pinned tokenizer/chat template without loading model weights or calling inference. Report context eligibility jointly across conditions, cached evidence availability, output representation limits, and whether valid D evidence can distinguish observed candidate behaviors. Gold correctness may be joined only afterward for clearly marked retrospective mixed-pool and missed-opportunity summaries.

Alternative valid outputs and evaluator qualifications limit what D can establish. Evidence separation is not semantic correctness. The existing offline inference boundary uses a fixed generation instruction and has not yet been shown to support selector prompts; any future adaptation requires a separately reviewed, narrowly scoped prompt-mode change and tests. No E2 selector call or intervention is authorized here.

## Decision record

This amendment makes no changes to task membership, prompt generation, candidate identity, scoring rules, endpoint definitions, or task eligibility. It does not supersede the original partial report, stopped-run ledgers, private evidence manifests, or public continuation report. The interim report must distinguish historical partial findings, newly analyzed checkpoint evidence, generation-only partial outputs, and remaining registered work.

## Analysis implementation correction v2

After writing the first private diagnostic aggregate, code review against the registered `e1_analysis.bootstrap_groups()` found that the interim implementation sampled only the observed segment tasks. That does not reuse the registered bootstrap frame. The first aggregate is retained privately as a superseded engineering artifact and is not used for results. The implementation now samples 20 slots from each original 20-task benchmark stratum per replicate, matching the registered procedure; unavailable and out-of-scope tasks contribute no metric value. This correction was made before reviewing any interim metric estimates, does not change the estimands or endpoint definitions, and will be reflected in a separately named v2 aggregate.
