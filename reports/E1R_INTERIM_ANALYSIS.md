# E1-R Interim Scientific Analysis

**Status:** Exploratory interim analysis; E1 remains incomplete.

**Analysis population:** 30 of 40 registered development tasks, eight checkpointed candidates per task.

**Decision:** Preserve the resource stop and return for researcher review. No additional E1 inference, candidate execution, E2 call, E3/E4 intervention, or confirmation access occurred in this analysis phase.

## Scope and evidence handling

The immutable E1 source records contain four original completed chunks and two completed continuation chunks. The combined analytical view contains 240 checkpointed candidates. A partial continuation chunk also contains 13 raw generation outputs; these remain preserved as generation-only evidence and are excluded from correctness, selection, and behavioral-cluster analyses. One started generation has no output and was not retried; 66 registered calls were never started. The 10 remaining registered tasks have no complete panels.

The original 20-task report remains unchanged. The continuation segment covers 10 completed tasks. It ran in a later session on the same boot under different resource conditions, so segment contrasts are descriptive and cannot identify an interruption or session effect. The combined results describe 30 tasks; they do not complete the registered 40-task E1 population.

Two endpoints are retained: **official-compatible**, using the approved EvalPlus amendment and registered official scoring rules; and **integrity-qualified**, applying the pre-generation reference-integrity qualifications to the same registered tasks and cases. No task, input, correctness criterion, or label was changed. The transport-limited task remains registered with unavailable full/H labels. Both reference-concern tasks remain qualified as registered. Missing labels are never counted automatically as model failures.

The unit is the task. The registered 2,000 task-level bootstrap replicates use the original frame of 20 HumanEval and 20 MBPP task slots per replicate, then report available-case estimates. Intervals are 95% task-bootstrap intervals. The linked safe aggregate contains all denominators, intervals, strata, and missingness bounds. Conservative 40-task bounds allow unavailable outcomes to take either value, with no missing-at-random assumption.

For prefix size k, **first** is observed first-candidate correctness. **Pass@k** is the registered unbiased combinatorial estimate from the complete eight-candidate bank under its stochastic-sampling assumptions; it is not first-candidate accuracy or empirical prefix oracle success. **Oracle-any** is the observed fraction of tasks with at least one correct candidate in that prefix.

## Combined 30-task results

Values are accuracy followed by the 95% task-bootstrap interval. Each official-compatible metric uses 29 tasks with complete official labels; each integrity-qualified metric uses 28 complete labels. One further official task and two qualified tasks are incomplete.

### Official-compatible endpoint

| k | First | Uniform random | Visible pass-count | Visible consensus | Oracle-any | Unbiased pass@k |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 51.7% [34.6, 69.2] | 51.7% [34.6, 69.2] | 51.7% [34.6, 69.2] | 51.7% [34.6, 69.2] | 51.7% [34.6, 69.2] | 62.5% [49.2, 75.5] |
| 2 | 51.7% [34.6, 69.2] | 58.6% [44.0, 73.5] | 65.5% [48.4, 82.1] | 62.1% [44.8, 79.2] | 72.4% [56.7, 88.0] | 74.4% [60.4, 87.0] |
| 4 | 51.7% [34.6, 69.2] | 61.2% [47.7, 75.0] | 72.4% [56.2, 87.5] | 65.5% [48.4, 82.1] | 79.3% [64.5, 93.1] | 81.1% [66.5, 94.0] |
| 8 | 51.7% [34.6, 69.2] | 62.5% [49.2, 75.5] | 72.4% [56.2, 87.5] | 72.4% [56.2, 87.5] | 82.8% [67.9, 96.2] | 82.8% [67.9, 96.2] |

### Integrity-qualified endpoint

| k | First | Uniform random | Visible pass-count | Visible consensus | Oracle-any | Unbiased pass@k |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 53.6% [36.0, 71.4] | 53.6% [36.0, 71.4] | 53.6% [36.0, 71.4] | 53.6% [36.0, 71.4] | 53.6% [36.0, 71.4] | 63.8% [50.0, 77.4] |
| 2 | 53.6% [36.0, 71.4] | 60.7% [46.3, 75.8] | 67.9% [50.0, 84.0] | 64.3% [46.4, 81.3] | 75.0% [58.6, 89.7] | 75.4% [61.0, 88.2] |
| 4 | 53.6% [36.0, 71.4] | 63.4% [49.3, 76.9] | 75.0% [58.6, 89.7] | 67.9% [50.0, 84.0] | 82.1% [66.7, 96.0] | 81.2% [66.1, 94.7] |
| 8 | 53.6% [36.0, 71.4] | 63.8% [50.0, 77.4] | 75.0% [58.6, 89.7] | 75.0% [58.6, 89.7] | 82.1% [66.7, 96.0] | 82.1% [66.7, 96.0] |

At k=4, conservative 40-task bounds are 57.5–85.0% for official oracle-any and 52.5–80.0% for official pass-count; qualified bounds are 57.5–87.5% and 52.5–82.5%. The safe aggregate contains bounds for every registered metric and stratum.

### Headroom and paired selection changes

Headroom is oracle-any minus selected-candidate accuracy. Change is the task-paired selector accuracy minus first-candidate accuracy. Positive change favors the selector. Intervals are task-bootstrap intervals.

| Endpoint | k | Pass-count headroom | Consensus headroom | Pass-count change | Consensus change |
| --- | ---: | ---: | ---: | ---: | ---: |
| Official-compatible | 2 | 6.9% [0.0, 17.7] | 10.3% [0.0, 22.6] | 13.8% [3.2, 27.6] | 10.3% [0.0, 21.9] |
| Official-compatible | 4 | 6.9% [0.0, 17.7] | 13.8% [3.3, 27.6] | 20.7% [6.9, 36.4] | 13.8% [3.2, 27.6] |
| Official-compatible | 8 | 10.3% [0.0, 22.6] | 10.3% [0.0, 22.6] | 20.7% [6.9, 36.4] | 20.7% [6.9, 36.4] |
| Integrity-qualified | 2 | 7.1% [0.0, 18.2] | 10.7% [0.0, 23.8] | 14.3% [3.3, 28.6] | 10.7% [0.0, 22.9] |
| Integrity-qualified | 4 | 7.1% [0.0, 18.2] | 14.3% [3.3, 28.1] | 21.4% [7.1, 37.0] | 14.3% [3.3, 28.6] |
| Integrity-qualified | 8 | 7.1% [0.0, 18.2] | 7.1% [0.0, 18.2] | 21.4% [7.1, 37.0] | 21.4% [7.1, 37.0] |

The point estimates show selection opportunity in this partial sample: at k=8 oracle-any is 82.8% official-compatible and 82.1% qualified, while visible selectors reach 72.4% and 75.0%, respectively. Intervals and registered-population bounds remain broad. This does not identify why selection misses candidates.

### Benchmark-specific k=4

| Endpoint | Benchmark | Complete-label tasks | First | Pass-count | Consensus | Oracle-any | Pass@4 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Official-compatible | HumanEval | 14/15 | 71.4% | 85.7% | 78.6% | 92.9% | 92.6% |
| Official-compatible | MBPP | 15/15 | 33.3% | 60.0% | 53.3% | 66.7% | 70.5% |
| Integrity-qualified | HumanEval | 14/15 | 71.4% | 85.7% | 78.6% | 92.9% | 92.6% |
| Integrity-qualified | MBPP | 14/15 | 35.7% | 64.3% | 57.1% | 71.4% | 69.9% |

These small strata are descriptive, not evidence of a causal task-difficulty effect.

## Original and continuation segments

The original segment’s k=4 and k=8 estimates reproduce the previously published E1 review, which remains unchanged. The continuation row covers only 10 tasks. Full k=1,2,4,8 values, intervals, denominators, and strata for all scopes are in the aggregate file.

| Scope / endpoint | k | First | Uniform | Pass-count | Consensus | Oracle-any | Pass@k |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Original 20 / official-compatible (n=19) | 4 | 47.4% | 61.8% | 68.4% | 63.2% | 78.9% | 81.9% |
| Original 20 / official-compatible (n=19) | 8 | 47.4% | 63.8% | 68.4% | 68.4% | 84.2% | 84.2% |
| Original 20 / integrity-qualified (n=18) | 4 | 50.0% | 65.3% | 72.2% | 66.7% | 83.3% | 82.1% |
| Original 20 / integrity-qualified (n=18) | 8 | 50.0% | 66.0% | 72.2% | 72.2% | 83.3% | 83.3% |
| Continuation 10 / official-compatible (n=10) | 4 | 60.0% | 60.0% | 80.0% | 70.0% | 80.0% | 79.7% |
| Continuation 10 / official-compatible (n=10) | 8 | 60.0% | 60.0% | 80.0% | 80.0% | 80.0% | 80.0% |
| Continuation 10 / integrity-qualified (n=10) | 4 | 60.0% | 60.0% | 80.0% | 70.0% | 80.0% | 79.7% |
| Continuation 10 / integrity-qualified (n=10) | 8 | 60.0% | 60.0% | 80.0% | 80.0% | 80.0% | 80.0% |

Do not compare the two segments as randomized or measured under the same resource/session state.

## Candidate-pool composition and behavioral evidence

“Incomplete” means at least one correctness label required for that endpoint is unavailable, not that the candidate failed.

| Endpoint | k | All correct | Mixed | All incorrect | Incomplete |
| --- | ---: | ---: | ---: | ---: | ---: |
| Official-compatible | 4 | 11 | 12 | 6 | 1 |
| Official-compatible | 8 | 10 | 14 | 5 | 1 |
| Integrity-qualified | 4 | 11 | 12 | 5 | 2 |
| Integrity-qualified | 8 | 10 | 13 | 5 | 2 |

On the official endpoint, 14/29 fully labeled eight-candidate pools were mixed, five were all incorrect and 10 all correct. There is no broad ceiling effect in this observed sample.

Visible behavior signatures were available for 29 tasks. At k=4 there were two mixed-correctness visible clusters of sizes three and four. At k=8 there were three, of sizes six, six and eight. For the qualified endpoint k=8 has two mixed clusters of sizes six and eight because some labels are unavailable. These clusters show candidates that current visible execution evidence does not distinguish; they do not establish semantic equivalence on all inputs.

Twenty-one of 120 first-four candidate slots and 46 of 240 first-eight slots lacked a usable visible signature. They are unavailable for cluster analysis, not assumed incorrect. There were four duplicate extracted-code copies beyond the first occurrence, across four tasks. The consensus baseline is a simple deterministic behavior-cluster selector, not a CodeT or S* reproduction.

## Verification evidence quality

False acceptance uses incorrect full-suite candidates as its denominator. False rejection uses correct full-suite candidates. “Incorrect given visible pass” conditions on visible acceptance. H failure among visible passes requires available H labels. Intervals resample tasks, not candidates.

| Endpoint | Y0,V0 | Y0,V1 | Y1,V0 | Y1,V1 | Y/V unavailable | False acceptance | False rejection | Incorrect given V pass | H fail given V pass |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Official-compatible | 57 | 30 | 0 | 145 | 8 | 30/87 = 34.5% [13.9, 53.9] | 0/145 = 0% | 30/175 = 17.1% [5.4, 30.1] | 29/175 = 16.6% [5.0, 29.5] |
| Integrity-qualified | 55 | 26 | 0 | 143 | 16 | 26/81 = 32.1% [10.6, 52.8] | 0/143 = 0% | 26/169 = 15.4% [4.1, 28.9] | 25/169 = 14.8% [3.6, 28.3] |

The visible pass set is nested within the full endpoint, so false rejection is structurally constrained. Zero observed false rejection is not independent evidence that V is a perfect verifier. In the qualified endpoint, 175 candidates visibly passed but only 169 had labels needed for conditional correctness/H analyses; the missing six are not imputed.

Special oracles remain in the official-compatible endpoint. Integrity-qualified estimates are presented alongside, not substituted for it. A visible output signature is not a correctness oracle: acceptable alternatives, special-oracle behavior, and unsupported representations can make different outputs both valid or leave a signature unavailable.

## Failure and availability distribution

These counts overlap and are not a partition of candidates.

| Outcome | Count | Interpretation |
| --- | ---: | --- |
| Parse/extraction success | 232 | Checkpointed source passed extraction |
| Invalid syntax | 6 | Generation/extraction failure; not executed |
| Truncated | 2 | Incomplete generation; not retried |
| Missing entry point among checkpointed candidates | 0 | No such parse status in the checkpointed bank |
| Candidate records with initialization exception | 38 | Runtime initialization outcome |
| Candidate programs with incorrect observable output | 49 | At least one recorded base or plus output was incorrect |
| Incorrect base outputs | 60 / 997 executed cases | Case-level count |
| Incorrect plus outputs | 6,078 / 94,726 executed cases | Case-level count |
| Plus-case exception events | 670 across 8 candidate programs | Runtime failures; overlaps other outcomes |
| Plus-case timeout events | 2 across 1 candidate program | Runtime timeouts; no semantic bug taxonomy inferred |
| Evaluations unavailable | 7 candidate records | Reference/evaluator limitation |
| Official correctness labels unavailable | 8 candidate records | Includes registered transport limitation |
| Generation-only outputs in partial chunk | 13 | Preserved, not scored above |
| Interrupted generation with no output | 1 | Infrastructure interruption; not retried |
| Registered calls never started | 66 | No output exists |

The seven unavailable evaluations are separate from model failures. No semantic bug categories are inferred from execution results.

## Resource record

The cumulative E1 authorization remains 320 call starts, 245,760 output tokens and 3,600 seconds, with one inference stream, one evaluator worker, balanced five-task chunks and the original per-call limit. The stop remains part of the scientific record.

| Segment | Call starts | Completed outputs | Output tokens | Input tokens | Recorded execution time |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original 20 tasks | 160 | 160 | 41,376 | 18,904 | 1,112.966 s |
| Continuation segment | 94 | 93 | 28,836 | 13,571 | 732.233 s |
| Cumulative | 254 | 253 | 70,212 | 32,475 | 1,845.199 s |

Recorded input and output token totals exclude the interrupted call. The 13 partial-chunk outputs are included in generation totals but not in the 240-candidate analysis. The 66 unstarted calls remain authorized; the interrupted identity is not retried. Median measured prefill/decode throughput across checkpointed candidates was 958.8/61.3 tokens/s. Peak recorded MLX allocation was 2.17 GB and peak process RSS was 1.51 GB.

The continuation did not begin after a restart or closing applications. During its partial third chunk, swap increased by about 998 MiB over 66 seconds, pressure rose from level 1 to 2, and elevated swap persisted after cleanup. The cause is unidentified: snapshots cannot separate MLX, the Docker VM, trusted host allocations, accumulated system state, or unrelated applications. No resource gate was weakened. This technical stop is not scientific evidence for or against a hypothesis.

## Hypothesis portfolio

E1 is a shared-bank descriptive study. It can inform H1 and H3, but it is not an intervention test of all six hypotheses.

| Hypothesis | What E1-R establishes | Unresolved explanations | Discriminating next experiment |
| --- | --- | --- | --- |
| H1: generation headroom, behavioral identifiability, or evidence interpretation | 14/29 official eight-candidate pools are mixed; at k=8 oracle-any is 82.8% versus 72.4% for either visible selector. | The gap may reflect weak evidence, selector limits, ambiguous outputs, or sample variation; E1 does not isolate interpretation. | E2 fixed-bank A/B/C/D comparisons plus deterministic V and V+D selectors. |
| H2: feedback diversity, amount, or actionability | E1 supplies cached output evidence but has no repair intervention. | Evidence amount, diversity, actionability and repair capability remain confounded. | E3 feedback/context factorial, then matched-size feedback-diversity study if justified. |
| H3: weak/invalid verification and shared generator/verifier errors | Visible tests falsely accept 30/87 incorrect official candidates; two k=4 mixed-correctness visible clusters show ambiguity. | These data do not identify invalid-oracle or shared causal errors. | E2 tests evidence sufficiency; E4 varies discrimination and label validity on development panels. |
| H4: initial code context helps or anchors refinement | E1 does not revise candidates. | Context benefits, anchoring, and feedback interaction are unmeasured. | E3 randomized context × feedback conditions. |
| H5: refinement regresses initially correct programs | E1 performs no refinement. | Regression frequency and retention behavior are unknown. | E3 unconditional revision and visible-score retention conditions. |
| H6: bottlenecks vary with capability, difficulty, or budget | One model/configuration gives descriptive task variation only. | Capability interactions and model comparisons are unidentified. | Later matched multi-model, difficulty-stratified budget study. |

No hypothesis is declared failed or established. Low accuracy or task variation does not terminate the research program.

## Integrity, amendments, and verification

The strict stopped-parent and continuation-manifest validators passed. The combined view rechecked parent commitments, checkpoint artifact hashes, identities/order, event chronology, coverage, raw generation artifacts and resource counters; it returned only the six complete checkpoints. The fresh aggregate exactly matches the preserved v2 registered-bootstrap aggregate. Historical manifests, ledgers, outputs, partial outputs and reports were not modified.

The v1 interim aggregate remains preserved as a superseded diagnostic because its bootstrap frame used observed segment sizes. The v2 analysis uses the registered 20-task-per-benchmark frame, covered by a synthetic parity test. The E2 technical draft was corrected before its eligibility freeze to retain initialization exception statuses as recorded D evidence. A reporting extraction also failed because it requested the wrong interval field; the saved schema uses ci95. That failure changed no evidence or estimates.

The synthetic E1-R tests cover interim validation, artifact tamper/identity/chronology failures, partial-chunk exclusion, bootstrap parity and separation of technical E2 evidence from retrospective labels. Full suite in the pinned scorer environment:

    PYTHONPATH=src python -m unittest discover -s tests -v

Result: 80 tests; 69 passed and 11 environment-gated tests skipped. The skipped tests require the pinned reference checker or live immutable candidate image; no generated code was executed in E1-R. Default unittest discovery found no tests and exited with status 5; the explicit tests start directory above is the valid run. Both attempts are retained locally.

## E2 feasibility and recommendation

The technical-only assessment found 30 complete first-four pools, 30 usable V summaries and 29 pools with usable cached D evidence. One additional pool exceeded the D-context limit. Twenty-eight pools meet the technical E2 conditions: 13 HumanEval and 15 MBPP, with four candidates, V/D evidence, and all four condition-size proxies within the 8,192-token context and 128-token output reserve.

Only after freezing these 28 eligibilities were labels joined for retrospective feasibility:

- Official first-four composition: 11 all-correct, 11 mixed, 6 all-incorrect.
- Integrity-qualified composition: 11 all-correct, 11 mixed, 5 all-incorrect, 1 incomplete.
- Among 22 eligible pools with a known correct candidate, pass-count missed one in 2; consensus missed one in 4.
- Distinct cached D behavior signatures across eligible pools: one in 13 tasks, two in 9, three in 5, and four in 1.

The token measurement is a context proxy using the frozen local tokenizer, generic selector message, cached task/code/V/D payloads and placeholder comparison booleans for D. No model weights were loaded and no selector output was generated. A/B fit all 30 measured pools; C fit 29; D fit 28. Across measured pools D reached 9,914 tokens, so one exceeds the 8,064-token input allowance. All 28 technical eligibles fit this proxy, but the actual E2 prompt is not registered. The current inference worker only emits code-generation prompts; a future E2 needs a selector prompt mode and prompt/context tests.

The original E2 protocol calls for the first 24 eligibles in a prelocked hash order, ideally balanced by benchmark. No such order artifact was found in the E1 registration or public protocol. Do not select tasks from retrospective correctness. If E2 is pursued, prospectively amend the protocol to set a label-blind deterministic hash order among the 13 HumanEval and 15 MBPP eligibles, specify a 12/12 sample, freeze the selector prompt and output parser, and recheck every condition context before any call.

At the original cap, 24 tasks require 96 calls and at most 12,288 output tokens. A balanced 12/12 subset has a four-arm input-token proxy expected near 161,160 tokens, with a combinatorial subset range of 136,206–173,961. At measured E1 medians this projects to about 168 seconds of prefill and up to 200 seconds of decoding at the output cap, roughly 6.1 minutes of token work before model startup, call overhead, evaluation and resource variance. This is a throughput projection, not an observed runtime or authorization. A fresh resource preflight is needed because the earlier swap event remains unexplained.

**Recommendation:** E2 has the highest immediate information value for H1/H3: the frozen first-four pools contain 11 mixed tasks, cached V/D evidence, and visible selectors sometimes miss known-correct candidates. E2 can compare evidence availability with interpretation under a fixed bank. The small sample, retrospective qualifications, proxy prompt and missing hash order mean E2 should not run as-is. Request a prospective protocol amendment and researcher authorization first. E2–E4 and confirmation remain unauthorized.
